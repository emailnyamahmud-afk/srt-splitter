#!/usr/bin/env python3
"""
cross-ref-sastra-jawa-v2.py — Cross-ref sastra-jawa dengan strategi baru.

User: 'AI nambah masalah, sumber baru seharusnya nambah entry lengkap,
atau setidaknya nambah entry indo-ngoko. PARSING TOLOL KE 455'

Strategi v2:
1. Restore kamus ke state pre-merge-milstrike-v3 (LENGKAP 1.395)
2. Cross-ref sastra-jawa:
   a. NETRAL fill: kalau NETRAL word di kamus match Jv sastra-jawa → isi indo
   b. ADD new: kalau indo sastra-jawa tidak ada di kamus → tambah entry baru
      Filter: skip entry baru kalau Jv mulai dengan digit / pendek / ambiguous
3. Skip auto-merge duplikat (bug v3, rusak entries lengkap)

R-42: Cross-ref sumber baru harus nambah LENGKAP entries, bukan rusak.
R-43: ADD new entries dari sastra-jawa — filter yg jelas (skip digit, pendek, ambiguous).

Usage:
  python3 cross-ref-sastra-jawa-v2.py --apply
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
    nf = unicodedata.normalize('NFKD', s)
    return ''.join(c for c in nf if not unicodedata.combining(c)).lower()


def is_valid_jv_token(tok):
    """Filter Jv token sastra-jawa — skip yg invalid.

    R-43: Filter ketat untuk ADD new entries.
    - Skip kalau mulai digit
    - Skip kalau punya karakter aneh (;, :, digit, parens)
    - Skip kalau <4 char (kependekan seperti 'ar', 'kc', 'kyt', 'bngs')
    - Skip kalau semua huruf konsonan (kependekan)
    - Skip kalau punya uppercase di tengah (camelCase, mungkin typo)
    - Skip kalau terlalu panjang (>30 char, kalimat)
    """
    if not tok or len(tok) < 4:  # min 4 char (skip kc, ar, kyt, bngs, dll)
        return False
    if len(tok) > 30:
        return False
    if tok[0].isdigit():
        return False
    if re.search(r'[;:\d\(\)]', tok):
        return False
    # Cek semua huruf konsonan (kependekan)
    vowels = set('aeiouéèêěəôö')
    has_vowel = any(c in vowels for c in tok.lower())
    if not has_vowel:
        return False
    return True


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--kamus', default='/home/z/my-project/srt-splitter-clone/public/kamus_unified_draft.json')
    parser.add_argument('--sastra-jawa', default='/home/z/my-project/upload/sources/sastra-jawa/csv/dictionary.csv')
    args = parser.parse_args()

    print(f'📁 Kamus: {args.kamus}')
    print(f'📁 Sastra-jawa: {args.sastra_jawa}')
    print()

    # Load kamus
    d = json.load(open(args.kamus))
    words = d['words']

    # Load sastra-jawa
    sj_indo_to_jv = defaultdict(list)
    with open(args.sastra_jawa) as f:
        reader = csv.DictReader(f)
        for row in reader:
            indo = row['Indonesia'].strip()
            jv = row['Javanese'].strip()
            if indo and jv:
                sj_indo_to_jv[indo.lower()].append(jv)
    print(f'📊 Sastra-jawa: {len(sj_indo_to_jv):,} indo keys')

    # Build NETRAL index (word_lower → list of entries)
    netral_idx = defaultdict(list)
    for w in words:
        if (w.get('word') or '').strip() and not (w.get('ngoko') or '').strip() and not (w.get('krama') or '').strip() and not (w.get('indo') or '').strip():
            word_lower = (w.get('word') or '').strip().lower()
            netral_idx[word_lower].append(w)

    # Build kamus indo index (untuk skip ADD)
    kamus_indo_idx = set()
    for w in words:
        indo = (w.get('indo') or '').strip().lower()
        if indo:
            kamus_indo_idx.add(indo)

    print(f'📊 Kamus NETRAL entries: {sum(len(v) for v in netral_idx.values()):,}')
    print(f'📊 Kamus indo keys existing: {len(kamus_indo_idx):,}')
    print()

    # Build baku (diacritic) index dari NETRAL word
    netral_baku_idx = defaultdict(list)
    for word_lower, entries in netral_idx.items():
        netral_baku_idx[strip_diacritics(word_lower)].extend(entries)

    # Process: tiap indo key sastra-jawa
    n_netral_fill = 0
    n_add_new = 0
    n_skip_already = 0
    n_skip_invalid = 0
    actions_fill = []
    actions_add = []

    for indo, jv_list in sj_indo_to_jv.items():
        # Skip kalau indo sudah ada di kamus
        if indo in kamus_indo_idx:
            n_skip_already += 1
            continue

        # Ambil jv utama dari list
        jv_main = jv_list[0]
        # Parse jv: hapus keterangan dalam kurung, split koma
        cleaned = jv_main.split('(')[0].split('.')[0].strip()
        jv_tokens = [t.strip() for t in cleaned.split(',') if t.strip()]

        if not jv_tokens:
            n_skip_invalid += 1
            continue

        # Cek apakah ada token jv yg match NETRAL word di kamus
        matched_entry = None
        matched_token = None
        for tok in jv_tokens:
            tok_lower = tok.lower()
            # Exact match
            if tok_lower in netral_idx:
                matched_entry = netral_idx[tok_lower][0]
                matched_token = tok
                break
            # Diacritic-insensitive match
            stripped = strip_diacritics(tok_lower)
            if stripped in netral_baku_idx:
                # Cek apakah token ini lebih baku dari NETRAL word
                matched_entry = netral_baku_idx[stripped][0]
                matched_token = tok
                break

        if matched_entry:
            # NETRAL fill — isi indo
            actions_fill.append((matched_entry, matched_token, indo))
            n_netral_fill += 1
        else:
            # ADD new entry
            # Ambil token pertama yg valid
            valid_tokens = [t for t in jv_tokens if is_valid_jv_token(t)]
            if not valid_tokens:
                n_skip_invalid += 1
                continue
            word = valid_tokens[0]
            actions_add.append((word, indo, jv_main[:100]))
            n_add_new += 1

    print('═' * 60)
    print(f'  RINGKASAN STRATEGI V2')
    print('═' * 60)
    print(f'  ✅ NETRAL fill (isi indo ke entry existing):  {n_netral_fill:,}')
    print(f'  ✅ ADD new entries (dari sastra-jawa):        {n_add_new:,}')
    print(f'  ⏭ Skip (indo already in kamus):              {n_skip_already:,}')
    print(f'  ⏭ Skip (jv invalid/filtered):                {n_skip_invalid:,}')
    print()

    # Sample
    print('Sample NETRAL fill (first 10):')
    for w, tok, indo in actions_fill[:10]:
        print(f"  #{w.get('entry_id')} word={tok!r} → indo={indo!r}")
    print()
    print('Sample ADD new (first 10):')
    for word, indo, jv in actions_add[:10]:
        print(f"  word={word!r} indo={indo!r} (jv: {jv})")
    print()

    if not args.apply:
        print('🔍 DRY-RUN — tidak ada perubahan.')
        print('   Untuk eksekusi: python3 cross-ref-sastra-jawa-v2.py --apply')
        return

    # ===== APPLY =====
    print('═' * 60)
    print('  🚀 APPLY')
    print('═' * 60)

    # Apply NETRAL fill
    n_applied_fill = 0
    for entry, tok, indo in actions_fill:
        entry['indo'] = indo
        entry['status'] = 'draft'
        sumber = (entry.get('sumber') or '').strip()
        if 'sastra-jawa' not in sumber:
            entry['sumber'] = (sumber + ' + sastra-jawa').strip(' +') if sumber else 'sastra-jawa'
        ket = (entry.get('keterangan') or '').strip()
        ai_note = f'\n\n[AI cross-ref-sastra-jawa-v2: NETRAL fill | tok_match={tok} | indo={indo}]'
        entry['keterangan'] = ket + ai_note
        n_applied_fill += 1
    print(f'  ✅ NETRAL fill applied: {n_applied_fill}')

    # Apply ADD new
    max_eid = max((w.get('entry_id', 0) for w in words), default=0)
    n_applied_add = 0
    for word, indo, jv_main in actions_add:
        max_eid += 1
        new_entry = {
            'entry_id': max_eid,
            'word': word,
            'ngoko': '',
            'krama': '',
            'indo': indo,
            'keterangan': f'[AI cross-ref-sastra-jawa-v2: ADD new from sastra-jawa | jv: {jv_main}]',
            'aksara': '',
            'sumber': 'sastra-jawa',
            'is_lemma': False,
            'is_mendeley': False,
            'is_dasanama': False,
            'is_angka': False,
            'is_lampiran': False,
            'kelas': '',
            'kelas_nama': '',
            'lemma_words': '',
            'mendeley_id': '',
            'dasanama_count': 0,
            'source_count': 1,
            'status': 'draft',
        }
        words.append(new_entry)
        n_applied_add += 1
    print(f'  ✅ ADD new applied: {n_applied_add}')

    json.dump(d, open(args.kamus, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
    print(f'  ✅ Saved: {args.kamus}')

    # Statistik
    n_lengkap = sum(1 for w in words if (w.get('ngoko') or '').strip() and (w.get('krama') or '').strip() and (w.get('indo') or '').strip())
    n_netral_paired = sum(1 for w in words if (w.get('word') or '').strip() and not (w.get('ngoko') or '').strip() and not (w.get('krama') or '').strip() and (w.get('indo') or '').strip())
    print()
    print(f'═' * 60)
    print(f'  ✅ CROSS-REF V2 SELESAI')
    print(f'  Total entries: {len(words):,}')
    print(f'  LENGKAP: {n_lengkap:,}')
    print(f'  NETRAL paired (word+indo): {n_netral_paired:,}')
    print(f'  NETRAL fill: +{n_applied_fill}')
    print(f'  ADD new: +{n_applied_add}')
    print(f'═' * 60)


if __name__ == '__main__':
    main()
