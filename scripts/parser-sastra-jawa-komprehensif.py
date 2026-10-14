#!/usr/bin/env python3
"""
parser-sastra-jawa-komprehensif.py — Parser komprehensif anti-tolol untuk sastra-jawa dictionary.csv.

User: 'jika sumber sastra jawa ada 10k pasangan indo-jawa.
tapi kenapa parser tolol ai membuat pasangan indo jawa gak sampai 2k?
analisis mendalam sastra jawa, lalu buat plan parsing komprehensif anti tolol.'

Analisa pattern Javanese column sastra-jawa (11.093 rows):
- ends_with_period: 97.9% (hampir semua)
- has_jv_diacritic: 61.2% (é, è, ê — Jawa baku)
- pure_jv_clean: 37.9% (4.199 rows, yg HARUS tangkap)
- has_colon: 33.6% (':' separator contoh kalimat)
- has_semicolon: 31.7% (';' separator arti multi)
- has_indo_leak: 29.5% (meng-, di-, -nya, dll)
- has_kependekan: 26.5% (kc., bngs., ar., kyt.)
- has_paren: 20.2% ('()' keterangan)
- homonym_number: 8.3% (1, 2 di awal)
- homonym_roman: 5.3% (i, ii di awal)

Plan parser komprehensif (7 step):

Step 1: Hapus homonym Roman di awal (i, ii, iii, iv)
  'i awu, ii bapa.' → 'awu, bapa.'
Step 2: Hapus homonym Number di awal (1, 2, 3)
  '1 langgêng, 2 jaman 100 taun.' → 'langgêng, jaman 100 taun.'
Step 3: Hapus keterangan dalam kurung '(...)'
  'abah-abah (prabot, piranti).' → 'abah-abah'
Step 4: Hapus kependekan dgn titik (kc., bngs., ar., kyt., ent., tmr., up., bs., ke., k.)
  'kc. bêntara:' → 'bêntara:'
  'bngs. kura.' → 'kura.'
Step 5: Split ':' ambil KIRI (sinonim), buang kanan (contoh kalimat)
  'mengabui mata: ngapusi.' → 'mengabui mata' (akan di-skip indo leak)
  'ora prêduli; ora nggape; mengabi: madoni.' → split ':', ambil 'ora prêduli; ora nggape; mengabi'
Step 6: Split ';' (arti multi), gabung koma
  'langgêng, kalanggêngan; 2 jaman 100 taun.' (after step 2) → 'langgêng, kalanggêngan, jaman 100 taun'
Step 7: Hapus titik di akhir, split koma → token Jawa

Filter token (R-56):
- Skip Indonesia leak: meng-, di-, ter-, ber-, ke-...-an, pe-...-an, -nya, -kan, -i (suffix Indonesia)
- Skip < 2 char, > 25 char (kalimat)
- Skip kependekan konsonan semua
- Skip ada karakter aneh #*[]

Output: {indo_lower: set of jv_tokens_baku}

Usage:
  python3 parser-sastra-jawa-komprehensif.py                    # dry-run (statistik)
  python3 parser-sastra-jawa-komprehensif.py --apply            # save parsed output
"""

import os
import sys
import csv
import json
import re
import argparse
import unicodedata
from pathlib import Path
from collections import defaultdict, Counter


def strip_diacritics(s):
    nf = unicodedata.normalize('NFKD', s)
    return ''.join(c for c in nf if not unicodedata.combining(c)).lower()


# Indonesia leak patterns (R-56) — filter RILY Indonesia, BUKAN Jawa dgn prefix sama
INDO_LEAK_PATTERNS = [
    r'^meng\w+',    # meng- prefix (Indonesia), Jawa = 'ng-' beda
    r'^ber\w+',    # ber- prefix (Indonesia), Jawa gak ada
    r'^ter\w+',    # ter- prefix (Indonesia), Jawa gak ada
    r'^pen\w+',    # pen- prefix (Indonesia)
    r'\w+nya$',    # -nya suffix (Indonesia)
    r'\w+lah$',    # -lah suffix (Indonesia)
    r'\w+tah$',    # -tah suffix (Indonesia, partikel)
    r'\w+pun$',    # -pun suffix (Indonesia, partikel)
    # SKIP: ^di\w+ (Jawa passive = di- + root, BUKAN Indonesia leak)
    # SKIP: \w+kan$ (banyak Jawa ends -kan: 'pêlikan', 'sruwala+kan')
    # SKIP: ^ke\w+an$ (Jawa juga punya: 'kebagusan')
    # SKIP: ^pe\w+an$ (Jawa juga punya)
]
INDO_LEAK_RE = re.compile('|'.join(INDO_LEAK_PATTERNS))


def is_valid_indo(indo):
    """Filter indo (R-49 ketat)."""
    if not indo:
        return False
    indo = indo.strip()
    if len(indo) < 2:
        return False
    if re.search(r'[éèêěəôö]', indo):
        return False
    if re.search(r'[\u0600-\u06FF\u0750-\u077F\u0900-\u097F]', indo):
        return False
    if indo.rstrip().endswith(':') or indo.rstrip().endswith(';'):
        return False
    if re.match(r'^[:;|*#=()]', indo) or re.search(r'[:;|*#=()]$', indo):
        return False
    if '|' in indo or '====' in indo or 't=' in indo:
        return False
    if '#::' in indo or '#:' in indo:
        return False
    if '()' in indo or '(' in indo or ')' in indo:
        return False
    if 'Dari' in indo or 'dari' in indo:
        return False
    if len(indo) > 50:
        return False
    return True


def is_valid_jv_token(tok):
    """Filter jv token (R-56 ketat)."""
    if not tok:
        return False
    tok = tok.strip().strip('.')
    if len(tok) < 2:
        return False
    if len(tok) > 25:
        return False
    if tok[0].isdigit():
        return False
    if re.search(r'[*#\[\]{}]', tok):
        return False
    vowels = set('aeiouéèêěəôöāīū')
    has_vowel = any(c in vowels for c in tok.lower())
    if not has_vowel:
        return False
    # Skip Indonesia leak
    if INDO_LEAK_RE.search(tok):
        return False
    # Skip kependekan (huruf konsonan + titik pattern di awal)
    if re.match(r'^[a-z]{1,4}\.', tok):
        return False
    return True


def parse_jv_field_komprehensif(jv_raw):
    """Parser komprehensif 7-step untuk Javanese column sastra-jawa.

    Return: set of jv tokens baku.
    """
    if not jv_raw:
        return set()
    s = jv_raw.strip()

    # Step 1: Hapus homonym Roman di awal (i, ii, iii, iv — case insensitive)
    s = re.sub(r'^i{1,4}\s+', '', s, flags=re.IGNORECASE)
    s = re.sub(r'^i{1,4}\s+', '', s, flags=re.IGNORECASE)  # second pass kalau ada multi

    # Step 2: Hapus homonym Number di awal (1, 2, 3, ...)
    # Pattern: '1 langgêng, 2 jaman' atau '1/10 dhuwit'
    # Ambil semua, hapus nomor + spasi di awal tiap segment
    s = re.sub(r'^\d+\s+', '', s)
    # Hapus nomor homonym di tengah setelah koma/semicolon
    s = re.sub(r'([,;])\s*\d+\s+', r'\1 ', s)

    # Step 3: Hapus keterangan dalam kurung (...)
    s = re.sub(r'\([^)]*\)', '', s)
    # Hapus sisa () kosong
    s = re.sub(r'\(\s*\)', '', s)

    # Step 4: Hapus kependekan dgn titik (kc., bngs., ar., kyt., ent., tmr., up., bs., ke., k.)
    # Pattern: word(2-5 char) + titik + space
    s = re.sub(r'\b(kc|bngs|ar|kyt|ent|tmr|up|bs|ke|k|ii|iii|iv|lnj|wrt|kr|br|jlr|np|bhs)\.\s*', '', s, flags=re.IGNORECASE)
    # Hapus juga kalau ada kependekan di akhir sebelum titik
    s = re.sub(r'\s+(kc|bngs|ar|kyt|ent|tmr|up|bs|ke|k)\.$', '', s, flags=re.IGNORECASE)

    # Step 5: Split ':' — ambil keduanya (kiri = sinonim, kanan = contoh/sinonim alternatif)
    # 'mengabui mata: ngapusi.' → tokens: ['mengabui mata' (skip indo leak), 'ngapusi' (valid Jawa)]
    # 'abdi: batur.' → tokens: ['abdi', 'batur']
    # Untuk tiap segment ':' split, proses terpisah
    if ':' in s:
        colon_parts = s.split(':')
        # Gabung kembali dengan koma separator
        s = ', '.join(p.strip() for p in colon_parts if p.strip())

    # Step 6: Split ';' (arti multi) — gabung koma
    s = s.replace(';', ',')

    # Step 7: Hapus titik di akhir, split koma → token
    s = s.rstrip('.').strip()
    tokens = []
    for tok in s.split(','):
        tok = tok.strip().rstrip('.').strip()
        if is_valid_jv_token(tok):
            tokens.append(tok.lower())
    return set(tokens)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--sastra-jawa', dest='sastra_jawa', default='/home/z/my-project/upload/sources/sastra-jawa/csv/dictionary.csv')
    parser.add_argument('--output', default='/home/z/my-project/upload/sources/sastra-jawa/sastra-jawa-parsed.json')
    args = parser.parse_args()

    print(f'📁 Source: {args.sastra_jawa}')
    print(f'📁 Output:  {args.output}')
    print()

    # Load + parse
    n_total = 0
    n_indo_valid = 0
    n_indo_invalid = 0
    n_jv_extracted = 0
    n_jv_empty = 0
    parsed = defaultdict(set)  # indo_lower → set of jv tokens
    samples_success = []
    samples_fail_indo = []
    samples_fail_jv = []

    with open(args.sastra_jawa) as f:
        reader = csv.DictReader(f)
        for row in reader:
            n_total += 1
            indo_raw = row['Indonesia'].strip()
            jv_raw = row['Javanese'].strip()
            if not indo_raw or not jv_raw:
                continue

            indo = indo_raw.lower()
            if not is_valid_indo(indo):
                n_indo_invalid += 1
                if len(samples_fail_indo) < 10:
                    samples_fail_indo.append((indo_raw, jv_raw[:60]))
                continue
            n_indo_valid += 1

            jv_tokens = parse_jv_field_komprehensif(jv_raw)
            if jv_tokens:
                parsed[indo].update(jv_tokens)
                n_jv_extracted += 1
                if len(samples_success) < 15:
                    samples_success.append((indo, jv_raw[:80], sorted(jv_tokens)))
            else:
                n_jv_empty += 1
                if len(samples_fail_jv) < 15:
                    samples_fail_jv.append((indo, jv_raw[:80]))

    print('═' * 60)
    print('  STATISTIK PARSER KOMPREHENSIF')
    print('═' * 60)
    print(f'  Total rows:                {n_total:,}')
    print(f'  Indo valid:                {n_indo_valid:,}')
    print(f'  Indo invalid (skip):       {n_indo_invalid:,}')
    print(f'  JV tokens extracted:        {n_jv_extracted:,} entries')
    print(f'  JV empty (filter all):     {n_jv_empty:,} entries')
    print(f'  Total unique indo parsed:  {len(parsed):,}')
    print(f'  Total unique jv tokens:    {sum(len(v) for v in parsed.values()):,}')
    print()

    print('=== Sample SUCCESS (15) ===')
    for indo, jv_raw, jv_tokens in samples_success:
        print(f"  indo={indo!r}")
        print(f"    jv_raw: {jv_raw!r}")
        print(f"    tokens: {jv_tokens}")
    print()

    print('=== Sample FAIL indo (10) ===')
    for indo, jv in samples_fail_indo:
        print(f"  indo={indo!r} jv={jv!r}")
    print()

    print('=== Sample FAIL jv (15) — indo valid tapi jv gak ada token valid ===')
    for indo, jv in samples_fail_jv:
        print(f"  indo={indo!r}")
        print(f"    jv_raw: {jv!r}")

    if not args.apply:
        print('\n🔍 DRY-RUN — tidak ada perubahan.')
        return

    # Apply: save parsed output
    output = {
        'metadata': {
            'version': 'v1 (parser komprehensif 7-step)',
            'source': 'sastra-jawa dictionary.csv',
            'total_rows': n_total,
            'total_indo_valid': n_indo_valid,
            'total_parsed': len(parsed),
            'total_jv_tokens': sum(len(v) for v in parsed.values()),
        },
        'parsed': {indo: sorted(tokens) for indo, tokens in sorted(parsed.items())},
    }
    json.dump(output, open(args.output, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
    print(f'\n✅ Saved: {args.output}')


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print('\n\n⏹ Dibatalkan.')
        sys.exit(130)
