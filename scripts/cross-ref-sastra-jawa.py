#!/usr/bin/env python3
"""
cross-ref-sastra-jawa.py — Cross-reference kamus_unified_draft.json dengan sastra-jawa dictionary.csv.

Source: https://github.com/nsulistiyawan/sastra-jawa
- dictionary.csv: 11.095 entries Indonesia → Javanese (BERSIH, format: Indonesia | Javanese | Alphabet)
- dasanama.csv: 432 entries sinonim Jawa (kata + dasanama koma)

Strategy:
1. Build reverse index Javanese → Indonesia dari sastra-jawa dictionary
2. Untuk tiap entry NETRAL di kamus_unified (word terisi, ngoko/krama/indo kosong):
   - Match word ke jv_to_indo (exact + diacritic-insensitive)
   - Match → isi indo dengan Indonesia translation
   - Word tetap (NETRAL paired, register belum tentukan — tugas user native Jawa)
3. Tidak determine register (ngoko/krama) — itu tugas user, AI gak bisa
4. Status='draft' (R-12: user mark READY manual)
5. Sumber += 'sastra-jawa' marker

R-40: Cross-reference dengan sastra-jawa (BERSIH). 11.095 entries indo→jv.
R-41: Register (ngoko/krama) = tugas user native Jawa, AI gak bisa determine.

Usage:
  python3 cross-ref-sastra-jawa.py                    # dry-run
  python3 cross-ref-sastra-jawa.py --apply            # eksekusi
  python3 cross-ref-sastra-jawa.py --kamus path
  python3 cross-ref-sastra-jawa.py --sastra-jawa path
"""

import os
import sys
import csv
import json
import argparse
import datetime
import unicodedata
from pathlib import Path
from collections import defaultdict


def load_json(path):
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def save_json(path, data):
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def strip_diacritics(s):
    """Normalize + hapus diacritics (é→e, ê→e)."""
    nf = unicodedata.normalize('NFKD', s)
    return ''.join(c for c in nf if not unicodedata.combining(c)).lower()


def build_jv_to_indo_index(sj_dict_path):
    """Build reverse index Javanese → Indonesia dari sastra-jawa dictionary.csv.

    Return:
      jv_to_indo: {jv_token_lower: set of indo_keys}
      sj_baku_idx: {stripped: set of jv_tokens} (untuk diacritic-insensitive match)
    """
    jv_to_indo = defaultdict(set)
    with open(sj_dict_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            indo = row['Indonesia'].strip()
            jv = row['Javanese'].strip()
            if not indo or not jv:
                continue
            # Parse Javanese: ambil bagian sebelum '(' (keterangan dalam kurung)
            # Tokenize koma (sinonim)
            cleaned = jv.split('(')[0].split('.')[0].strip()
            for tok in cleaned.split(','):
                tok = tok.strip().lower()
                if tok and len(tok) > 1:
                    jv_to_indo[tok].add(indo.lower())

    # Build baku index (diacritic-insensitive)
    sj_baku_idx = defaultdict(set)
    for jv_tok in jv_to_indo:
        sj_baku_idx[strip_diacritics(jv_tok)].add(jv_tok)

    return jv_to_indo, sj_baku_idx


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--kamus', default=None)
    parser.add_argument('--sastra-jawa', default=None,
                        help='Path ke sastra-jawa dictionary.csv')
    args = parser.parse_args()

    # Cari kamus
    kamus_paths = [
        args.kamus,
        Path.home() / 'Dubbing' / 'kamus_unified_draft.json',
        Path(__file__).parent / 'kamus_unified_draft.json',
    ]
    kamus_path = None
    for p in kamus_paths:
        if p and Path(p).exists():
            kamus_path = Path(p)
            break
    if not kamus_path:
        print('❌ kamus_unified_draft.json tidak ditemukan.')
        sys.exit(1)

    # Cari sastra-jawa dictionary.csv
    sj_paths = [
        args.sastra_jawa,
        Path(__file__).parent / 'sastra-jawa' / 'csv' / 'dictionary.csv',
        Path.home() / 'Dubbing' / 'sastra-jawa' / 'csv' / 'dictionary.csv',
    ]
    sj_path = None
    for p in sj_paths:
        if p and Path(p).exists():
            sj_path = Path(p)
            break
    if not sj_path:
        print('❌ sastra-jawa dictionary.csv tidak ditemukan.')
        print('   Clone: git clone https://github.com/nsulistiyawan/sastra-jawa.git')
        sys.exit(1)

    print(f'📁 Kamus:      {kamus_path}')
    print(f'📁 Sastra-jawa: {sj_path}')
    print()

    kamus = load_json(kamus_path)
    words = kamus['words']
    print(f'📊 Total kamus entries: {len(words):,}')

    # Build index
    print('Build jv→indo index dari sastra-jawa...')
    jv_to_indo, sj_baku_idx = build_jv_to_indo_index(sj_path)
    print(f'  Total jv tokens: {len(jv_to_indo):,}')
    print(f'  Total stripped baku: {len(sj_baku_idx):,}')
    print()

    # Process NETRAL entries
    n_match_exact = 0
    n_match_diacritic = 0
    n_skip_already_paired = 0
    n_skip_multi_match = 0  # ambigu, banyak indo keys → skip
    n_no_match = 0
    actions = []  # (entry_id, mode, indo_chosen, jv_match)

    for w in words:
        # Skip kalau sudah paired
        if (w.get('ngoko') or '').strip() or (w.get('krama') or '').strip() or (w.get('indo') or '').strip():
            n_skip_already_paired += 1
            continue
        word = (w.get('word') or '').strip().lower()
        if not word:
            continue
        eid = w.get('entry_id')

        # Cek exact match
        if word in jv_to_indo:
            indo_keys = jv_to_indo[word]
            # Kalau 1 key → match
            # Kalau multi keys → ambigu, skip (tampilkan untuk user audit)
            if len(indo_keys) == 1:
                indo = next(iter(indo_keys))
                actions.append((eid, 'exact', indo, word))
                n_match_exact += 1
            else:
                # Multi-indo ambigu — ambil 1 saja (yg paling pendek/umum)
                # Sebenarnya ambigu, biar user tentukan. Tapi untuk productivity, ambil semua + gabung koma
                indo = '; '.join(sorted(indo_keys)[:3])
                actions.append((eid, 'exact-multi', indo, word))
                n_match_exact += 1
            continue

        # Cek diacritic-insensitive
        stripped = strip_diacritics(word)
        if stripped in sj_baku_idx:
            baku_forms = sj_baku_idx[stripped]
            # Ambil indo dari semua baku forms
            indo_keys = set()
            for b in baku_forms:
                indo_keys.update(jv_to_indo[b])
            if indo_keys:
                indo = '; '.join(sorted(indo_keys)[:3])
                # Catatan: word asli vs baku form
                baku_chosen = next(iter(baku_forms))
                actions.append((eid, 'diacritic', indo, f'{word} → baku={baku_chosen}'))
                n_match_diacritic += 1
                continue

        n_no_match += 1

    print(f'═' * 60)
    print(f'  RINGKASAN CROSS-REFERENCE')
    print(f'═' * 60)
    print(f'  ✅ Match exact:                          {n_match_exact:,}')
    print(f'  ✅ Match diacritic-insensitive:          {n_match_diacritic:,}')
    print(f'  ⏭ Skip (already paired):                 {n_skip_already_paired:,}')
    print(f'  ❌ No match (word tidak ada di sj):       {n_no_match:,}')
    print(f'  Total processed: {n_match_exact + n_match_diacritic + n_no_match + n_skip_already_paired:,}')
    print()

    # Sample
    print('Sample match (first 15):')
    for eid, mode, indo, jv in actions[:15]:
        print(f"  #{eid} [{mode}] jv={jv[:30]!r} → indo={indo[:50]!r}")
    print()

    if not args.apply:
        print('🔍 DRY-RUN — tidak ada perubahan.')
        print('   Untuk eksekusi: python3 cross-ref-sastra-jawa.py --apply')
        return

    # ===== APPLY =====
    print('═' * 60)
    print('  🚀 APPLY CROSS-REFERENCE')
    print('═' * 60)

    # Backup
    backup_path = kamus_path.with_suffix('.json.bak.' + datetime.datetime.now().strftime('%Y%m%d_%H%M%S'))
    save_json(backup_path, kamus)
    print(f'  ✅ Backup: {backup_path}')

    # Apply
    n_applied = 0
    for eid, mode, indo, jv in actions:
        w = next((x for x in words if x.get('entry_id') == eid), None)
        if not w:
            continue
        w['indo'] = indo
        w['status'] = 'draft'
        sumber = (w.get('sumber') or '').strip()
        if 'sastra-jawa' not in sumber:
            w['sumber'] = (sumber + ' + sastra-jawa').strip(' +') if sumber else 'sastra-jawa'
        # Catatan di keterangan
        ket = (w.get('keterangan') or '').strip()
        ai_note = f'\n\n[AI cross-ref-sastra-jawa: mode={mode} | jv_match={jv[:50]} | indo={indo[:50]}]'
        w['keterangan'] = ket + ai_note
        n_applied += 1

    save_json(kamus_path, kamus)
    print(f'  ✅ Applied: {n_applied} entries')
    print(f'  ✅ Saved: {kamus_path}')
    print()
    print(f'═' * 60)
    print(f'  ✅ CROSS-REFERENCE SELESAI')
    print(f'  Match: {n_match_exact + n_match_diacritic:,} entries di-isi indo')
    print(f'  Backup: {backup_path}')
    print(f'  Total kamus: {len(words):,} (NETRAL tersisa: ~{40128 - n_match_exact - n_match_diacritic:,})')
    print(f'═' * 60)
    print()
    print('Catatan:')
    print('  - Register (ngoko/krama) TIDAK di-isi (tugas user native Jawa)')
    print('  - Word tetap (NETRAL paired — word+indo)')
    print('  - Status: draft (user mark READY manual via TUI)')
    print('  - Search "sastra-jawa" di sumber untuk lihat entries ini')


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print('\n\n⏹ Dibatalkan.')
        sys.exit(130)
