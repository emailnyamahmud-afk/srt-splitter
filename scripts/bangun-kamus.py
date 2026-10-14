#!/usr/bin/env python3
"""
bangun-kamus.py — Build kamus baru dari source bersih dengan INDO sebagai JANGKAR.

User: 'ARSITEKTUR MASIH SAMPAH, BELUM BISA DIBACA MESIN.
BUAT SAJA JANGKARNYA INDO, LALU NGOKO DAN KRAMA ISI BERDASARKAN INDO.
1 KONSEP 1 ENTRY, KALAU BEDA KATA TULIS COMA (SINONIM).'

Arsitektur kamus:
- 1 entry = 1 konsep
- INDO = jangkar (unique key, case-insensitive)
- NGOKO = sinonim ngoko (kata kasar/biasa), koma-separated
- KRAMA = sinonim krama (kata halus), koma-separated
- WORD = sinonim NETRAL (belum tentukan register), koma-separated
- TIDAK ada duplikat konsep (1 indo = 1 entry)

Source bersih (prioritas):
1. sastra-jawa dictionary.csv (Indonesia → Javanese, BERSIH)
2. milstrike_jv_id.json (jv_key → indo, BERSIH)
3. kamus_unified_draft.json (HANYA entries LENGKAP 3-field — sebagai suplemen)

Skip data berantakan:
- jv.wiktionary raw entries (NETRAL, label leak, dll) — TIDAK dipakai sebagai source of truth
- Entries dgn indo = label leak (":", ";", dll)
- Entries dgn ngoko/krama = indo (Indonesia bocor ke jv field)

R-48: INDO adalah jangkar. 1 indo = 1 entry. NGOKO/KRAMA di-isi berdasarkan INDO.
R-49: Sinonim = koma. Kata beda, makna sama, 1 entry.
R-50: Skip data berantakan — bukan source of truth.

Usage:
  python3 bangun-kamus.py                    # dry-run
  python3 bangun-kamus.py --apply            # build kamus baru
  python3 bangun-kamus.py --output path      # custom output path
"""

import os
import sys
import csv
import json
import re
import argparse
import unicodedata
from pathlib import Path
from collections import defaultdict


def strip_diacritics(s):
    """Hapus diacritics (é→e, ê→e) — untuk baku matching."""
    nf = unicodedata.normalize('NFKD', s)
    return ''.join(c for c in nf if not unicodedata.combining(c)).lower()


def is_valid_indo(indo):
    """Filter indo — harus Indonesia valid, BUKAN Jawa/Arab/label leak.

    R-49: Filter ketat. Indo adalah JANGKAR kamus.
    """
    if not indo:
        return False
    indo = indo.strip()
    if len(indo) < 2:
        return False
    # Skip kalau ada diacritic Jawa (kolom Indonesia terkontaminasi Jawa)
    if re.search(r'[éèêěəôö]', indo):
        return False
    # Skip kalau ada karakter Arab/special
    if re.search(r'[\u0600-\u06FF\u0750-\u077F\u0900-\u097F]', indo):
        return False
    # Skip kalau ada label leak (: di akhir, ; ; ; ; ;)
    if indo.rstrip().endswith(':') or indo.rstrip().endswith(';'):
        return False
    # Skip kalau mulai/akhir dengan karakter aneh
    if re.match(r'^[:;|*#=()]', indo) or re.search(r'[:;|*#=()]$', indo):
        return False
    # Skip kalau ada `|` atau `====` (parser leak)
    if '|' in indo or '====' in indo or 't=' in indo:
        return False
    # Skip kalau ada `#::` (wiktionary parser leak)
    if '#::' in indo or '#:' in indo:
        return False
    # Skip kalau ada () di mana saja (wiktionary leak)
    if '()' in indo or '(' in indo or ')' in indo:
        return False
    # Skip kalau ada 'Dari' (etymology leak)
    if 'Dari' in indo or 'dari' in indo:
        return False
    # Skip kalau terlalu panjang (kalimat definisi, bukan terjemahan)
    if len(indo) > 50:
        return False
    return True


def is_valid_jv_token(tok):
    """Filter Jv token — harus kata Jawa valid, bukan kalimat/kependekan.

    R-49: Jv token = sinonim kata, BUKAN kalimat.
    Skip kalau token = Indonesia (leak dari kolom Indonesia sastra-jawa).
    """
    if not tok:
        return False
    tok = tok.strip()
    if len(tok) < 2:
        return False
    if len(tok) > 25:
        return False  # kalimat
    if tok[0].isdigit():
        return False
    if re.search(r'[;:*#\[\]\(\)]', tok):
        return False
    # Cek punya vowel (bukan kependekan konsonan semua)
    vowels = set('aeiouéèêěəôöāīū')
    has_vowel = any(c in vowels for c in tok.lower())
    if not has_vowel:
        return False
    # Skip kalau ada karakter Indonesia leak (huruf kapital di tengah = kemungkinan typo/leak)
    if tok != tok.lower() and tok != tok.capitalize():
        # campuran case → skip
        return False
    return True


def parse_jv_field(jv_value):
    """Parse Jv field sastra-jawa — ambil token bersih.
    Format: "abah-abah (prabot, piranti)." atau "abot, awrat" atau "1 langgêng"
    """
    # Hapus keterangan dalam kurung
    cleaned = re.sub(r'\([^)]*\)', '', jv_value)
    # Hapus angka di awal (homonym marker)
    cleaned = re.sub(r'^\d+\s*', '', cleaned)
    # Split koma
    tokens = []
    for tok in cleaned.split(','):
        tok = tok.strip().rstrip('.')
        if is_valid_jv_token(tok):
            tokens.append(tok)
    return tokens


def load_sastra_jawa(path):
    """Load sastra-jawa dictionary → {indo_lower: set of jv_tokens}.
    Filter ketat (R-49).
    """
    sj = defaultdict(set)
    with open(path) as f:
        reader = csv.DictReader(f)
        for row in reader:
            indo_raw = row['Indonesia'].strip()
            jv_raw = row['Javanese'].strip()
            if not indo_raw or not jv_raw:
                continue
            indo = indo_raw.lower()
            if not is_valid_indo(indo):
                continue
            jv_tokens = parse_jv_field(jv_raw)
            for tok in jv_tokens:
                sj[indo].add(tok)
    return sj


def load_milstrike(path):
    """Load milstrike_jv_id.json → {indo_lower: set of jv_tokens}.
    Format: {jv_key: indo_value}. Bisa multi-token key (koma).
    """
    ms = defaultdict(set)
    data = json.load(open(path))
    for key, value in data.items():
        indo = (value or '').strip().lower()
        if not is_valid_indo(indo):
            continue
        # Parse key (bisa multi-token koma)
        jv_tokens = []
        for sep in [',', ';']:
            if sep in key:
                for t in key.split(sep):
                    t = t.strip()
                    if is_valid_jv_token(t):
                        jv_tokens.append(t)
                break
        if not jv_tokens:
            t = key.strip()
            if is_valid_jv_token(t):
                jv_tokens = [t]
        for tok in jv_tokens:
            ms[indo].add(tok)
    return ms


def load_existing_lengkap(path):
    """Load kamus_unified_draft.json, ambil HANYA entries LENGKAP 3-field.
    Return {indo_lower: {ngoko: set, krama: set, word: set, ...}}.
    """
    d = json.load(open(path))
    words = d['words']
    existing = {}
    for w in words:
        ngoko = (w.get('ngoko') or '').strip()
        krama = (w.get('krama') or '').strip()
        indo = (w.get('indo') or '').strip()
        word = (w.get('word') or '').strip()
        if not (ngoko and krama and indo):
            continue
        indo_lower = indo.lower()
        if not is_valid_indo(indo_lower):
            continue
        # Parse tokens
        ngoko_tokens = set(t for t in ngoko.split(',') if is_valid_jv_token(t))
        krama_tokens = set(t for t in krama.split(',') if is_valid_jv_token(t))
        word_tokens = set(t for t in word.split(',') if is_valid_jv_token(t))
        if indo_lower not in existing:
            existing[indo_lower] = {
                'ngoko': set(),
                'krama': set(),
                'word': set(),
                'keterangan': '',
                'aksara': '',
                'sumber': '',
            }
        existing[indo_lower]['ngoko'].update(ngoko_tokens)
        existing[indo_lower]['krama'].update(krama_tokens)
        existing[indo_lower]['word'].update(word_tokens)
        # Combine keterangan (limit)
        ket = (w.get('keterangan') or '').strip()
        if ket:
            if existing[indo_lower]['keterangan']:
                existing[indo_lower]['keterangan'] += ' | ' + ket[:200]
            else:
                existing[indo_lower]['keterangan'] = ket[:200]
        aksara = (w.get('aksara') or '').strip()
        if aksara:
            existing[indo_lower]['aksara'] = aksara[:50]
        sumber = (w.get('sumber') or '').strip()
        if sumber:
            if existing[indo_lower]['sumber']:
                existing[indo_lower]['sumber'] += ' + ' + sumber
            else:
                existing[indo_lower]['sumber'] = sumber
    return existing


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--output', default='/home/z/my-project/srt-splitter-clone/public/kamus_bersih.json',
                        help='Output path kamus baru')
    parser.add_argument('--sastra-jawa', default='/home/z/my-project/upload/sources/sastra-jawa/csv/dictionary.csv')
    parser.add_argument('--milstrike', default='/home/z/my-project/upload/milstrike_jv_id.json')
    parser.add_argument('--existing', default='/home/z/my-project/srt-splitter-clone/public/kamus_unified_draft.json',
                        help='Existing kamus (ambil entries LENGKAP saja)')
    args = parser.parse_args()

    print(f'📁 Sastra-jawa:  {args.sastra_jawa}')
    print(f'📁 Milstrike:    {args.milstrike}')
    print(f'📁 Existing:     {args.existing}')
    print(f'📁 Output:        {args.output}')
    print()

    # ===== Step 1: Load sources =====
    print('═' * 60)
    print('  STEP 1: Load sources (filter ketat R-49)')
    print('═' * 60)

    print('  Loading sastra-jawa dictionary...')
    sj = load_sastra_jawa(args.sastra_jawa)
    print(f'    ✅ {len(sj):,} indo keys (filtered)')

    print('  Loading milstrike...')
    ms = load_milstrike(args.milstrike)
    print(f'    ✅ {len(ms):,} indo keys (filtered)')

    print('  Loading existing LENGKAP entries...')
    existing = load_existing_lengkap(args.existing)
    print(f'    ✅ {len(existing):,} indo keys (LENGKAP 3-field only)')

    # ===== Step 2: Merge by indo (1 konsep 1 entry) =====
    print('\n' + '═' * 60)
    print('  STEP 2: Merge by INDO (1 konsep 1 entry, R-48)')
    print('═' * 60)

    # Gabungkan semua indo keys dari 3 sources
    all_indos = set(sj.keys()) | set(ms.keys()) | set(existing.keys())
    print(f'  Total unique indo keys: {len(all_indos):,}')
    print(f'    Sastra-jawa only: {len(set(sj.keys()) - set(ms.keys()) - set(existing.keys())):,}')
    print(f'    Milstrike only: {len(set(ms.keys()) - set(sj.keys()) - set(existing.keys())):,}')
    print(f'    Existing only: {len(set(existing.keys()) - set(sj.keys()) - set(ms.keys())):,}')
    print(f'    Multiple sources (overlap): {len(set(sj.keys()) & set(ms.keys())) + len(set(sj.keys()) & set(existing.keys())) + len(set(ms.keys()) & set(existing.keys())) - 2*len(set(sj.keys()) & set(ms.keys()) & set(existing.keys())):,}')

    # Build kamus baru: 1 indo = 1 entry
    new_entries = {}
    n_overlap_all_three = 0
    for indo in sorted(all_indos):
        # Gabung jv tokens dari semua source
        sj_tokens = sj.get(indo, set())
        ms_tokens = ms.get(indo, set())
        existing_data = existing.get(indo, {})

        ngoko_tokens = set()
        krama_tokens = set()
        word_tokens = set()

        # Dari existing (LENGKAP) — ngoko/krama/word sudah ter-klasifikasi
        ngoko_tokens.update(existing_data.get('ngoko', set()))
        krama_tokens.update(existing_data.get('krama', set()))
        word_tokens.update(existing_data.get('word', set()))

        # Dari sastra-jawa + milstrike: jv tokens belum tentukan register → masuk word (NETRAL)
        # Tapi kalau token sudah ada di ngoko/krama existing → skip (sudah ter-klasifikasi)
        all_classified = ngoko_tokens | krama_tokens
        for tok in sj_tokens | ms_tokens:
            if tok not in all_classified:
                word_tokens.add(tok)

        keterangan = existing_data.get('keterangan', '')
        aksara = existing_data.get('aksara', '')
        sumber_parts = []
        if existing_data.get('sumber'):
            sumber_parts.append('existing')
        if indo in sj:
            sumber_parts.append('sastra-jawa')
        if indo in ms:
            sumber_parts.append('milstrike')
        sumber = ' + '.join(sumber_parts)

        if sj_tokens and ms_tokens and existing_data:
            n_overlap_all_three += 1

        new_entries[indo] = {
            'ngoko': ', '.join(sorted(ngoko_tokens)),
            'krama': ', '.join(sorted(krama_tokens)),
            'word': ', '.join(sorted(word_tokens)),
            'indo': indo,
            'keterangan': keterangan,
            'aksara': aksara,
            'sumber': sumber,
            'status': 'draft',
        }

    print(f'\n  ✅ Built {len(new_entries):,} entries (1 konsep 1 entry)')
    print(f'  Overlap all 3 sources: {n_overlap_all_three}')

    # Statistik kelengkapan
    n_lengkap = sum(1 for e in new_entries.values() if e['ngoko'] and e['krama'])
    n_ngoko_only = sum(1 for e in new_entries.values() if e['ngoko'] and not e['krama'])
    n_krama_only = sum(1 for e in new_entries.values() if e['krama'] and not e['ngoko'])
    n_word_only = sum(1 for e in new_entries.values() if e['word'] and not e['ngoko'] and not e['krama'])
    n_empty = sum(1 for e in new_entries.values() if not e['ngoko'] and not e['krama'] and not e['word'])

    print(f'\n  Statistik kelengkapan:')
    print(f'    🟢 LENGKAP (ngoko+krama+indo): {n_lengkap:,}')
    print(f'    🔵 ngoko+indo (krama kosong): {n_ngoko_only:,}')
    print(f'    🔵 krama+indo (ngoko kosong): {n_krama_only:,}')
    print(f'    ⚪ word+indo (NETRAL):        {n_word_only:,}')
    print(f'    ❓ indo only:                  {n_empty:,}')

    # Sample
    print('\n  Sample entries:')
    for i, (indo, e) in enumerate(sorted(new_entries.items())):
        if i >= 10:
            break
        print(f"    indo={indo!r}")
        print(f"      ngoko={e['ngoko']!r} krama={e['krama']!r} word={e['word']!r}")
        print(f"      sumber={e['sumber']!r}")

    if not args.apply:
        print('\n🔍 DRY-RUN — tidak ada perubahan.')
        print('   Untuk eksekusi: python3 bangun-kamus.py --apply')
        return

    # ===== APPLY =====
    print('\n' + '═' * 60)
    print('  🚀 APPLY: Build kamus baru')
    print('═' * 60)

    # Format kamus: {metadata, words}
    new_kamus = {
        'metadata': {
            'version': 'v1 ( Indo sebagai jangkar, R-48)',
            'description': 'Kamus Jawa-Indonesia (1 konsep 1 entry, sinonim koma)',
            'sources': ['sastra-jawa dictionary.csv (bersih)', 'milstrike_jv_id.json (bersih)', 'kamus_unified_draft.json LENGKAP entries (suplemen)'],
            'schema': {
                'fields': ['entry_id', 'indo (JANGKAR)', 'ngoko', 'krama', 'word (NETRAL)', 'keterangan', 'aksara', 'sumber', 'status'],
            },
            'stats': {
                'total': len(new_entries),
                'lengkap': n_lengkap,
                'ngoko_only': n_ngoko_only,
                'krama_only': n_krama_only,
                'word_only': n_word_only,
                'indo_only': n_empty,
            },
        },
        'words': [],
    }

    # Sort by indo for stable entry_id
    for i, (indo, e) in enumerate(sorted(new_entries.items()), 1):
        entry = {
            'entry_id': i,
            'indo': e['indo'],
            'ngoko': e['ngoko'],
            'krama': e['krama'],
            'word': e['word'],
            'keterangan': e['keterangan'],
            'aksara': e['aksara'],
            'sumber': e['sumber'],
            'status': 'draft',
        }
        new_kamus['words'].append(entry)

    save_json(args.output, new_kamus)
    print(f'  ✅ Saved: {args.output}')
    print(f'  Total entries: {len(new_kamus["words"]):,}')

    # Verify no duplikat indo
    indos = [w['indo'] for w in new_kamus['words']]
    print(f'  Unique indo: {len(set(indos)):,} (harus = total entries)')
    if len(set(indos)) != len(indos):
        print(f'  ❌ BUG: ada duplikat indo!')


def save_json(path, data):
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print('\n\n⏹ Dibatalkan.')
        sys.exit(130)
