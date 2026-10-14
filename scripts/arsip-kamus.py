#!/usr/bin/env python3
"""
arsip-kamus.py v3 — Rebuild kamus jadi 1 konsep 1 entry.

User: 'KITA HARUS UBAH ARSITEKTUR KAMUS:
1. YG USER MAU SEDERHANA = KAMUS INDO-NGOKO-KRAMA
2. 1 ENTRY = 1 KONSEP, KATA BEDA, MAKNA SAMA = MASUK SEBAGAI SINONIM
3. SEMENTARA ADA 47K DATA = INI CAMPURAN NGOKO & KRAMA, MUNGKIN JUGA INDO

APA SUSAHNYA BIKIN 1 ENTRY 1 KONSEP? APA SUSAHNYA BIKIN GAK ADA YG DUPLIKAT?
APA SUSAHNYA BIKIN STANDARISASI PENULISAN?'

Arsitektur kamus:
- 1 entry = 1 konsep
- Fields utama: ngoko, krama, indo
- Sinonim (kata beda makna sama) = koma di field yg sesuai
- word (NETRAL) = sinonim yg belum tentukan register (untuk user tentukan nanti)
- TIDAK ada duplikat konsep lintas entry

Strategy:
Phase 1: Group SEMUA entries by indo (case-insensitive) → merge sinonim
  - Untuk tiap group >1 entry: merge jadi 1 entry
  - ngoko = gabung ngoko semua entries (koma, dedupe)
  - krama = gabung krama semua entries (koma, dedupe)
  - word = gabung word NETRAL semua entries (koma, dedupe)
  - indo = indo (ambil 1)
  - Combine aksara, keterangan, sumber
  - Delete entries duplikat
Phase 2: NETRAL fill dari sastra-jawa (filter ketat)
  - Untuk entry NETRAL true (word only, belum indo):
    - Cari word di sastra-jawa jv_to_indo (exact + diacritic)
    - Match → isi indo
  - Filter ketat: skip jv di kolom Indonesia sastra-jawa (é, è, ê diacritic)
  - Skip kalau indo punya karakter Arab
Phase 3: Merge lagi setelah NETRAL fill (group by indo)
Phase 4: Standarisasi penulisan case (lowercase untuk semua)

R-45: Arsitektur kamus = 1 entry 1 konsep. Sinonim koma. Tidak duplikat.
R-46: Skip data gak berguna lebih baik dari pada masuk noise ke kamus.
R-47: Standarisasi penulisan = tugas native Jawa (diacritic), AI hanya case.

Usage:
  python3 arsip-kamus.py                    # dry-run (Phase 1 only, no sastra-jawa)
  python3 arsip-kamus.py --apply             # eksekusi Phase 1-4
  python3 arsip-kamus.py --kamus path
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


def load_json(path):
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def save_json(path, data):
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def strip_diacritics(s):
    nf = unicodedata.normalize('NFKD', s)
    return ''.join(c for c in nf if not unicodedata.combining(c)).lower()


def merge_with_comma(*values):
    """Gabung multi-string dengan koma, dedupe case-insensitive."""
    tokens = []
    existing_lower = set()
    for v in values:
        if not v: continue
        for tok in str(v).split(','):
            tok = tok.strip()
            if tok and tok.lower() not in existing_lower:
                tokens.append(tok)
                existing_lower.add(tok.lower())
    return ', '.join(tokens)


def merge_entries(entries):
    """Merge multiple entries jadi 1 entry (1 konsep 1 entry, sinonim koma).

    Return merged entry.
    """
    if len(entries) == 1:
        return entries[0]
    primary = entries[0]  # first entry as primary
    # Gabung semua fields
    ngoko = merge_with_comma(*[(e.get('ngoko') or '').strip() for e in entries])
    krama = merge_with_comma(*[(e.get('krama') or '').strip() for e in entries])
    word = merge_with_comma(*[(e.get('word') or '').strip() for e in entries])
    indo = (primary.get('indo') or '').strip() or next((e.get('indo','').strip() for e in entries if e.get('indo')), '')

    primary['ngoko'] = ngoko
    primary['krama'] = krama
    primary['word'] = word
    primary['indo'] = indo

    # Combine aksara
    aksara = merge_with_comma(*[(e.get('aksara') or '').strip() for e in entries])
    primary['aksara'] = aksara

    # Combine keterangan (pakai | separator)
    kets = [(e.get('keterangan') or '').strip() for e in entries if (e.get('keterangan') or '').strip()]
    if kets:
        primary['keterangan'] = ' | '.join(kets)

    # Combine sumber
    sumbers = [(e.get('sumber') or '').strip() for e in entries if (e.get('sumber') or '').strip()]
    if sumbers:
        seen = set()
        unique = []
        for s in sumbers:
            if s not in seen:
                seen.add(s)
                unique.append(s)
        primary['sumber'] = ' + '.join(unique)

    # status = draft (R-12)
    primary['status'] = 'draft'
    return primary


def group_by_indo(words):
    """Group entries by indo (case-insensitive). Return {indo_lower: list of indices}."""
    groups = defaultdict(list)
    for i, w in enumerate(words):
        indo = (w.get('indo') or '').strip()
        if indo:
            groups[indo.lower()].append(i)
    return groups


def is_valid_indo_sastra_jawa(indo):
    """Filter indo sastra-jawa — skip yg invalid (R-46).

    Skip kalau:
    - <3 char
    - Punya diacritic jv (é, è, ê) — itu Jawa di kolom Indonesia
    - Punya karakter Arab/special
    - == jv sastra-jawa (kata Jawa di kolom Indonesia)
    """
    if not indo or len(indo) < 3:
        return False
    # Skip kalau ada diacritic Jawa (kolom Indonesia terkontaminasi Jawa)
    if re.search(r'[éèêěəôö]', indo):
        return False
    # Skip kalau ada karakter Arab/special
    if re.search(r'[\u0600-\u06FF\u0750-\u077F]', indo):
        return False
    # Skip kalau ada karakter aneh
    if re.search(r'[;:*]', indo):
        return False
    return True


def build_sj_jv_to_indo(sj_path):
    """Build jv_to_indo index dari sastra-jawa dictionary.csv.
    Filter ketat — skip indo invalid (R-46).
    """
    jv_to_indo = defaultdict(set)
    with open(sj_path) as f:
        reader = csv.DictReader(f)
        for row in reader:
            indo_raw = row['Indonesia'].strip()
            jv_raw = row['Javanese'].strip()
            if not indo_raw or not jv_raw:
                continue
            indo = indo_raw.lower()
            if not is_valid_indo_sastra_jawa(indo):
                continue
            # Parse Jv: hapus keterangan dalam kurung, split koma
            cleaned = jv_raw.split('(')[0].split('.')[0].strip()
            for tok in cleaned.split(','):
                tok = tok.strip().lower()
                if tok and len(tok) > 1:
                    jv_to_indo[tok].add(indo)
    return jv_to_indo


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--kamus', default='/home/z/my-project/srt-splitter-clone/public/kamus_unified_draft.json')
    parser.add_argument('--sastra-jawa', default='/home/z/my-project/upload/sources/sastra-jawa/csv/dictionary.csv')
    args = parser.parse_args()

    print(f'📁 Kamus: {args.kamus}')
    print()

    d = load_json(args.kamus)
    words = d['words']
    print(f'📊 Total entries: {len(words):,}')

    # ===== Phase 1: Group by indo, merge sinonim =====
    print('\n' + '═' * 60)
    print('  PHASE 1: Group by indo, merge sinonim (1 konsep 1 entry)')
    print('═' * 60)

    groups = group_by_indo(words)
    multi_groups = {k: v for k, v in groups.items() if len(v) > 1}
    print(f'  Total groups by indo: {len(groups):,}')
    print(f'  Multi-entry groups (>1 entry dgn indo sama): {len(multi_groups):,}')

    # Merge multi-groups
    indices_to_delete = set()
    n_merges = 0
    for indo_key, indices in multi_groups.items():
        # Skip kalau hanya 1 entry
        if len(indices) <= 1:
            continue
        entries = [words[i] for i in indices]
        merged = merge_entries(entries)
        # Mark all except first for deletion
        for i in indices[1:]:
            indices_to_delete.add(i)
        n_merges += len(indices) - 1

    print(f'  Entries akan di-merge: {n_merges:,}')
    print(f'  Entries akan di-delete (duplikat): {len(indices_to_delete):,}')

    if not args.apply:
        print('\n🔍 DRY-RUN Phase 1 — tidak ada perubahan.')

    if args.apply:
        # Apply Phase 1
        new_words = [w for i, w in enumerate(words) if i not in indices_to_delete]
        # Re-number entry_id
        for i, w in enumerate(new_words, 1):
            w['entry_id'] = i
        d['words'] = new_words
        words = new_words
        print(f'  ✅ Phase 1 done. Total: {len(words):,}')

    # ===== Phase 2: NETRAL fill dari sastra-jawa =====
    if args.apply:
        print('\n' + '═' * 60)
        print('  PHASE 2: NETRAL fill dari sastra-jawa (filter ketat R-46)')
        print('═' * 60)

        # Build jv_to_indo dari sastra-jawa
        print('  Build jv_to_indo dari sastra-jawa...')
        jv_to_indo = build_sj_jv_to_indo(args.sastra_jawa)
        print(f'  Total jv tokens (filtered): {len(jv_to_indo):,}')

        # Build baku (diacritic) index
        sj_baku_idx = defaultdict(set)
        for tok in jv_to_indo:
            sj_baku_idx[strip_diacritics(tok)].add(tok)

        # Untuk tiap entry NETRAL true (word only, belum indo)
        n_netral_fill = 0
        n_netral_fill_skip = 0
        for w in words:
            word = (w.get('word') or '').strip()
            if not word: continue
            if (w.get('ngoko') or '').strip() or (w.get('krama') or '').strip() or (w.get('indo') or '').strip():
                continue  # already paired

            word_lower = word.lower()
            # Exact match
            if word_lower in jv_to_indo:
                indo_keys = jv_to_indo[word_lower]
                # Ambil indo pertama (atau semua kalau multi)
                indo = '; '.join(sorted(indo_keys)[:3])
                w['indo'] = indo
                w['status'] = 'draft'
                sumber = (w.get('sumber') or '').strip()
                if 'sastra-jawa' not in sumber:
                    w['sumber'] = (sumber + ' + sastra-jawa').strip(' +') if sumber else 'sastra-jawa'
                n_netral_fill += 1
                continue
            # Diacritic match
            stripped = strip_diacritics(word_lower)
            if stripped in sj_baku_idx:
                baku_forms = sj_baku_idx[stripped]
                indo_keys = set()
                for b in baku_forms:
                    indo_keys.update(jv_to_indo[b])
                if indo_keys:
                    indo = '; '.join(sorted(indo_keys)[:3])
                    w['indo'] = indo
                    w['status'] = 'draft'
                    sumber = (w.get('sumber') or '').strip()
                    if 'sastra-jawa' not in sumber:
                        w['sumber'] = (sumber + ' + sastra-jawa').strip(' +') if sumber else 'sastra-jawa'
                    n_netral_fill += 1
                    continue
            n_netral_fill_skip += 1

        print(f'  ✅ NETRAL fill: {n_netral_fill:,} entries')
        print(f'  ⏭ Skip (no match in sastra-jawa): {n_netral_fill_skip:,}')

        # ===== Phase 3: Merge lagi setelah NETRAL fill =====
        print('\n' + '═' * 60)
        print('  PHASE 3: Merge lagi setelah NETRAL fill (group by indo)')
        print('═' * 60)

        groups2 = group_by_indo(words)
        multi_groups2 = {k: v for k, v in groups2.items() if len(v) > 1}
        print(f'  Multi-entry groups (post NETRAL fill): {len(multi_groups2):,}')

        indices_to_delete2 = set()
        n_merges2 = 0
        for indo_key, indices in multi_groups2.items():
            if len(indices) <= 1:
                continue
            entries = [words[i] for i in indices]
            merged = merge_entries(entries)
            for i in indices[1:]:
                indices_to_delete2.add(i)
            n_merges2 += len(indices) - 1

        new_words2 = [w for i, w in enumerate(words) if i not in indices_to_delete2]
        for i, w in enumerate(new_words2, 1):
            w['entry_id'] = i
        d['words'] = new_words2
        words = new_words2
        print(f'  ✅ Phase 3 done. Total: {len(words):,}')

        # ===== Phase 4: Standarisasi case =====
        print('\n' + '═' * 60)
        print('  PHASE 4: Standarisasi case (lowercase, R-47)')
        print('═' * 60)
        n_case_fix = 0
        for w in words:
            for field in ['ngoko', 'krama', 'indo', 'word']:
                val = (w.get(field) or '').strip()
                if not val: continue
                # Cek kalau ada uppercase
                tokens = [t.strip() for t in val.split(',') if t.strip()]
                new_tokens = []
                changed = False
                for tok in tokens:
                    if tok != tok.lower() and tok == tok.capitalize():
                        # Capitalized → lowercase
                        new_tokens.append(tok.lower())
                        changed = True
                    else:
                        new_tokens.append(tok)
                if changed:
                    w[field] = ', '.join(new_tokens)
                    n_case_fix += 1
        print(f'  ✅ Case fix: {n_case_fix:,} entries')

        # Save
        save_json(args.kamus, d)
        print(f'\n✅ Saved: {args.kamus}')

    # ===== Statistik akhir =====
    n_lengkap = sum(1 for w in words if (w.get('ngoko') or '').strip() and (w.get('krama') or '').strip() and (w.get('indo') or '').strip())
    n_netral_paired = sum(1 for w in words if (w.get('word') or '').strip() and not (w.get('ngoko') or '').strip() and not (w.get('krama') or '').strip() and (w.get('indo') or '').strip())
    n_word_only = sum(1 for w in words if (w.get('word') or '').strip() and not (w.get('ngoko') or '').strip() and not (w.get('krama') or '').strip() and not (w.get('indo') or '').strip())
    n_other = len(words) - n_lengkap - n_netral_paired - n_word_only

    print('\n' + '═' * 60)
    print(f'  STATISTIK AKHIR')
    print('═' * 60)
    print(f'  Total entries: {len(words):,}')
    print(f'  🟢 LENGKAP (ngoko+krama+indo): {n_lengkap:,}')
    print(f'  ⚠ NETRAL paired (word+indo):  {n_netral_paired:,}')
    print(f'  ⚪ NETRAL true (word only):    {n_word_only:,}')
    print(f'  ❓ other:                       {n_other:,}')
    print('═' * 60)


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print('\n\n⏹ Dibatalkan.')
        sys.exit(130)
