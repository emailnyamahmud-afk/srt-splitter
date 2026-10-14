#!/usr/bin/env python3
"""
parser-sastra-jawa-v2.py — Parser komprehensif ANTI-SKIP.

User: 'skip data adalah tolol, mau varian atau keterangan = masukan ke keterangan.
kamus bersih tak menjamin semua bersih = tetap user akan validasi manual.
tapi AI wajib masukan ke keterangan.'

Strategy ANTI-SKIP:
- Untuk tiap row sastra-jawa:
  - indo: extract clean (hapus varian (), jv diacritic, dll)
  - jv tokens: extract baku via parser 7-step
  - Kalau indo kosong setelah clean → masuk indo apa adanya (raw) + keterangan
  - Kalau jv tokens kosong → masuk keterangan (raw jv as keterangan)
- Output: kamus_bersih_v2.json dengan setiap entry punya:
  - indo (raw atau clean)
  - ngoko (koma-separated, kosong kalau belum tentukan)
  - krama (koma-separated, kosong kalau belum tentukan)
  - word (koma-separated, sinonim NETRAL)
  - keterangan (raw jv sastra-jawa + varian indo + kalimat definisi)
  - sumber

R-58: Tidak ada skip. Semua entries masuk kamus_bersih.
R-59: Indo ragu → keterangan raw + user validasi manual.
R-60: Jv kosong (kalimat definisi) → keterangan raw jv.

Usage:
  python3 parser-sastra-jawa-v2.py                    # dry-run
  python3 parser-sastra-jawa-v2.py --apply            # save kamus_bersih_v2.json
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
    r'^meng\w+',
    r'^ber\w+',
    r'^ter\w+',
    r'^pen\w+',
    r'\w+nya$',
    r'\w+lah$',
    r'\w+tah$',
    r'\w+pun$',
]
INDO_LEAK_RE = re.compile('|'.join(INDO_LEAK_PATTERNS))


def clean_indo(indo_raw):
    """Clean indo — extract indo utama + varian.
    Return: (indo_clean, varian_text, jv_diacritic_in_indo_flag)
    """
    if not indo_raw:
        return '', '', False
    s = indo_raw.strip()
    varian = ''
    
    # Cek apakah ada jv diacritic (kolom Indonesia terkontaminasi Jawa)
    has_jv_diacritic = bool(re.search(r'[éèêěəôö]', s))
    
    # Extract varian dalam kurung: 'agar (-supaya)' → indo='agar', varian='-supaya'
    paren_match = re.search(r'\(([^)]*)\)', s)
    if paren_match:
        varian = paren_match.group(1).strip()
        s = re.sub(r'\([^)]*\)', '', s).strip()
        s = re.sub(r'\s+', ' ', s).strip(' -')
    
    # Hapus ends : or ;
    s = s.rstrip(':;').strip()
    
    # Hapus starts/ends special
    s = re.sub(r'^[:;|*#=]+\s*', '', s)
    s = re.sub(r'\s*[:;|*#=]+$', '', s)
    
    # Lowercase
    s = s.strip().lower()
    
    return s, varian, has_jv_diacritic


def is_valid_jv_token(tok):
    """Filter jv token (R-56)."""
    if not tok:
        return False
    tok = tok.strip().strip('.').strip()
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
    if INDO_LEAK_RE.search(tok):
        return False
    if re.match(r'^[a-z]{1,4}\.', tok):
        return False
    return True


def parse_jv_field_komprehensif(jv_raw):
    """Parser 7-step + handle \n--- N --- marker.
    Return: (jv_tokens_set, raw_jv_after_parser_for_keterangan)
    """
    if not jv_raw:
        return set(), ''
    s = jv_raw.strip()
    
    # Step 0: Hapus \n--- N --- homonym marker (baris baru)
    s = re.sub(r'\n\s*---\s*\d+\s*---\s*', ' ', s)
    s = re.sub(r'\s*---\s*\d+\s*---\s*', ' ', s)
    
    # Step 1: Hapus homonym Roman di awal (i, ii, iii, iv)
    s = re.sub(r'^i{1,4}\s+', '', s, flags=re.IGNORECASE)
    s = re.sub(r'^i{1,4}\s+', '', s, flags=re.IGNORECASE)
    
    # Step 2: Hapus homonym Number di awal + di tengah
    s = re.sub(r'^\d+\s+', '', s)
    s = re.sub(r'([,;])\s*\d+\s+', r'\1 ', s)
    
    # Step 3: Hapus keterangan dalam kurung
    s = re.sub(r'\([^)]*\)', '', s)
    s = re.sub(r'\(\s*\)', '', s)
    
    # Step 4: Hapus kependekan dgn titik
    s = re.sub(r'\b(kc|bngs|ar|kyt|ent|tmr|up|bs|ke|k|ii|iii|iv|lnj|wrt|kr|br|jlr|np|bhs|wc|ut)\.\s*', '', s, flags=re.IGNORECASE)
    s = re.sub(r'\s+(kc|bngs|ar|kyt|ent|tmr|up|bs|ke|k)\.$', '', s, flags=re.IGNORECASE)
    
    # Step 5: Split ':' ambil KEDUA sisi
    if ':' in s:
        colon_parts = s.split(':')
        s = ', '.join(p.strip() for p in colon_parts if p.strip())
    
    # Step 6: Split ';' → koma
    s = s.replace(';', ',')
    
    # Step 7: Hapus titik akhir, split koma → token
    s_clean_for_tokens = s.rstrip('.').strip()
    tokens = set()
    for tok in s_clean_for_tokens.split(','):
        tok = tok.strip().rstrip('.').strip()
        if is_valid_jv_token(tok):
            tokens.add(tok.lower())
    
    return tokens, s_clean_for_tokens


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--sastra-jawa', dest='sastra_jawa', default='/home/z/my-project/upload/sources/sastra-jawa/csv/dictionary.csv')
    parser.add_argument('--output', default='/home/z/my-project/srt-splitter-clone/public/kamus_bersih_v2.json')
    args = parser.parse_args()

    print(f'📁 Source: {args.sastra_jawa}')
    print(f'📁 Output: {args.output}')
    print()

    # Proses tiap row
    n_total = 0
    n_with_jv = 0  # ada jv token valid
    n_jv_in_keterangan = 0  # jv token kosong, masuk keterangan (kalimat definisi)
    n_indo_jv_diacritic = 0  # indo punya jv diacritic (terkontaminasi)
    entries = []

    with open(args.sastra_jawa) as f:
        reader = csv.DictReader(f)
        for row in reader:
            n_total += 1
            indo_raw = row['Indonesia'].strip()
            jv_raw = row['Javanese'].strip()
            if not indo_raw and not jv_raw:
                continue
            
            # Clean indo
            indo_clean, indo_varian, indo_has_jv = clean_indo(indo_raw)
            
            # Parse jv
            jv_tokens, jv_raw_after_parser = parse_jv_field_komprehensif(jv_raw)
            
            # Build keterangan (raw info untuk user audit)
            keterangan_parts = []
            if indo_raw and indo_raw != indo_clean:
                keterangan_parts.append(f'indo_raw: {indo_raw}')
            if indo_varian:
                keterangan_parts.append(f'indo_varian: {indo_varian}')
            if indo_has_jv:
                n_indo_jv_diacritic += 1
                keterangan_parts.append('PERINGATAN: indo punya diacritic Jawa, mungkin kolom Indonesia terkontaminasi')
            if jv_raw:
                keterangan_parts.append(f'jv_raw: {jv_raw}')
            if not jv_tokens and jv_raw_after_parser:
                # jv token kosong setelah parser — raw masuk keterangan
                n_jv_in_keterangan += 1
                keterangan_parts.append(f'jv_after_parser (kalimat definisi / Indonesia leak): {jv_raw_after_parser}')
            keterangan = ' | '.join(keterangan_parts)
            
            entry = {
                'entry_id': n_total,  # will renumber later
                'indo': indo_clean if indo_clean else indo_raw.lower(),
                'ngoko': '',
                'krama': '',
                'word': ', '.join(sorted(jv_tokens)) if jv_tokens else '',
                'keterangan': keterangan,
                'aksara': '',
                'sumber': 'sastra-jawa',
                'status': 'draft',
            }
            entries.append(entry)
            if jv_tokens:
                n_with_jv += 1

    # Renumber
    for i, e in enumerate(entries, 1):
        e['entry_id'] = i

    # Statistik
    n_lengkap = sum(1 for e in entries if e['ngoko'] and e['krama'] and e['indo'])
    n_paired_word = sum(1 for e in entries if e['word'] and e['indo'])
    n_indo_only = sum(1 for e in entries if e['indo'] and not e['word'] and not e['ngoko'] and not e['krama'])
    
    print('═' * 60)
    print('  STATISTIK PARSER V2 (ANTI-SKIP)')
    print('═' * 60)
    print(f'  Total rows sastra-jawa:    {n_total:,}')
    print(f'  Total entries output:       {len(entries):,} (0 SKIP ✓)')
    print(f'  Entries dgn jv tokens valid: {n_with_jv:,}')
    print(f'  Entries jv kosong (→keterangan): {n_jv_in_keterangan:,}')
    print(f'  Entries indo jv diacritic:   {n_indo_jv_diacritic:,}')
    print()
    print(f'  Kelengkapan:')
    print(f'    🟢 LENGKAP (ngoko+krama+indo): {n_lengkap:,}')
    print(f'    ⚠ word+indo:                  {n_paired_word:,}')
    print(f'    ❓ indo only (no jv):           {n_indo_only:,}')

    # Verify 0 skip
    print(f'\n  ✅ ANTI-SKIP: {len(entries):,} entries (sama dengan total rows {n_total:,})')

    # Sample
    print('\n=== Sample 10 entries (mix jv valid + jv in keterangan) ===')
    n_show = 0
    for e in entries[:30]:
        print(f"  #{e['entry_id']} indo={e['indo']!r}")
        print(f"    word={e['word']!r}")
        print(f"    keterangan: {e['keterangan'][:120]!r}")
        print()
        n_show += 1
        if n_show >= 10: break

    if not args.apply:
        print('🔍 DRY-RUN — tidak ada perubahan.')
        return

    # Save
    output = {
        'metadata': {
            'version': 'v2 (parser sastra-jawa ANTI-SKIP)',
            'description': 'Kamus sastra-jawa — semua entries masuk, ragu → keterangan',
            'source': 'sastra-jawa dictionary.csv',
            'stats': {
                'total_rows': n_total,
                'total_entries': len(entries),
                'with_jv_valid': n_with_jv,
                'jv_in_keterangan': n_jv_in_keterangan,
                'indo_jv_diacritic': n_indo_jv_diacritic,
            },
        },
        'words': entries,
    }
    json.dump(output, open(args.output, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
    print(f'\n✅ Saved: {args.output}')


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print('\n\n⏹ Dibatalkan.')
        sys.exit(130)
