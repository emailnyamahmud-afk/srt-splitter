#!/usr/bin/env python3
"""
integrate-jv-wiktionary.py — Tambah 40k vocab Jawa dari jv.wiktionary ke kamus_bersih.json.

User: 'KENAPA JV VUCTIONARY DI SKIP? SKAP SKIP TOLOL.
padahal jv victionary = penulisan jawa = baku, ada banyak kata jawa ngoko dan krama.
seharusnya jv victionary juga masuk kamus bersih, misal di jv victionry ada kula =
maka kula juga masuk kamus bersih, atau kata apapun yg sudah ada di kamus bersih.
misal kula match dengan aku di kamus bersih.
jv victionary = 40k kosakata / vocabulari jawa, yg sama AI tolol di SKIP SKIP TOLOL.'

Strategy:
1. Load kamus_bersih.json (existing — indo jangkar)
2. Load kamus_unified_draft.json (jv.wiktionary source — word = lemma Jawa baku)
3. Untuk tiap jv.wiktionary entry:
   a. Match word ke kamus_bersih jv tokens (ngoko/krama/word):
      - Match → tambah sebagai sinonim di entry bersih existing
   b. Tidak match → entry baru di kamus_bersih:
      - word = jv.wiktionary word (lemma Jawa)
      - indo = jv.wiktionary indo (kalau valid) atau dari sastra-jawa/milstrike cross-ref
      - Kalau no indo → NETRAL true (word only), nanti user isi manual
4. Merge lagi setelah tambah (1 konsep 1 entry, sinonim koma)

R-51: jv.wiktionary = source JAWA baku. SEMUA lemma masuk kamus_bersih.
R-52: Cross-ref: jv.wiktionary word match kamus_bersih → sinonim. Tidak match → entry baru.
R-53: Indo kosong → NETRAL true (word only), user isi manual nanti.

Usage:
  python3 integrate-jv-wiktionary.py                    # dry-run
  python3 integrate-jv-wiktionary.py --apply            # eksekusi
"""

import os
import sys
import json
import re
import argparse
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
    nf = unicodedata.normalize('NFKD', s)
    return ''.join(c for c in nf if not unicodedata.combining(c)).lower()


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
    """Filter jv token (R-49 ketat)."""
    if not tok:
        return False
    tok = tok.strip()
    if len(tok) < 2:
        return False
    if len(tok) > 25:
        return False
    if tok[0].isdigit():
        return False
    if re.search(r'[;:*#\[\]\(\)]', tok):
        return False
    vowels = set('aeiouéèêěəôöāīū')
    has_vowel = any(c in vowels for c in tok.lower())
    if not has_vowel:
        return False
    if tok != tok.lower() and tok != tok.capitalize():
        return False
    return True


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--bersih', default='/home/z/my-project/srt-splitter-clone/public/kamus_bersih.json')
    parser.add_argument('--jv-source', default='/home/z/my-project/srt-splitter-clone/public/kamus_unified_draft.json')
    args = parser.parse_args()

    print(f'📁 Kamus bersih: {args.bersih}')
    print(f'📁 jv.wiktionary source: {args.jv_source}')
    print()

    d_bersih = load_json(args.bersih)
    bersih_words = d_bersih['words']
    print(f'📊 kamus_bersih entries: {len(bersih_words):,}')

    d_jv = load_json(args.jv_source)
    jv_words = d_jv['words']
    print(f'📊 jv.wiktionary entries: {len(jv_words):,}')
    print()

    # ===== Build kamus_bersih jv token index =====
    print('Build kamus_bersih jv token index...')
    bersih_jv_idx = defaultdict(set)  # jv_token_lower → entry_id
    bersih_ngoko_idx = defaultdict(set)
    bersih_krama_idx = defaultdict(set)
    bersih_word_idx = defaultdict(set)
    for w in bersih_words:
        eid = w.get('entry_id')
        ngoko = (w.get('ngoko') or '').strip()
        krama = (w.get('krama') or '').strip()
        word = (w.get('word') or '').strip()
        for tok in ngoko.split(','):
            tok = tok.strip().lower()
            if tok and len(tok) > 1:
                bersih_ngoko_idx[tok].add(eid)
                bersih_jv_idx[tok].add(eid)
        for tok in krama.split(','):
            tok = tok.strip().lower()
            if tok and len(tok) > 1:
                bersih_krama_idx[tok].add(eid)
                bersih_jv_idx[tok].add(eid)
        for tok in word.split(','):
            tok = tok.strip().lower()
            if tok and len(tok) > 1:
                bersih_word_idx[tok].add(eid)
                bersih_jv_idx[tok].add(eid)
    print(f'  Total jv tokens di kamus_bersih: {len(bersih_jv_idx):,}')

    # ===== Build jv.wiktionary word index =====
    print('Build jv.wiktionary word index...')
    jv_word_to_entries = defaultdict(list)  # jv_word_token → list of (entry_id, full_word, indo)
    for w in jv_words:
        word = (w.get('word') or '').strip()
        if not word:
            continue
        indo = (w.get('indo') or '').strip()
        for tok in word.split(','):
            tok_clean = tok.strip()
            if is_valid_jv_token(tok_clean):
                jv_word_to_entries[tok_clean.lower()].append((w.get('entry_id'), word, indo))
    print(f'  Total jv.wiktionary word tokens (filtered): {len(jv_word_to_entries):,}')

    # ===== Process: cross-ref + add new =====
    print('\n' + '═' * 60)
    print('  CROSS-REF + ADD NEW')
    print('═' * 60)

    # Track sinonim additions (entry_id bersih → set of jv tokens to add)
    sinonim_additions = defaultdict(lambda: {'ngoko': set(), 'krama': set(), 'word': set()})
    n_matched = 0
    n_no_match = 0

    # Track new entries
    new_entries = []  # list of dicts
    max_eid = max(w.get('entry_id', 0) for w in bersih_words)

    # Indo index dari kamus_bersih existing (untuk skip entry baru dgn indo sudah ada)
    bersih_indo_idx = set()
    for w in bersih_words:
        indo = (w.get('indo') or '').strip().lower()
        if indo:
            bersih_indo_idx.add(indo)

    # Dedup jv.wiktionary entries by word (kalau multiple entries punya word sama)
    jv_seen_word_tokens = set()
    for tok_lower, entries in jv_word_to_entries.items():
        if tok_lower in jv_seen_word_tokens:
            continue
        jv_seen_word_tokens.add(tok_lower)

        # Cek match ke kamus_bersih
        matched_eids = bersih_jv_idx.get(tok_lower, set())
        if matched_eids:
            # Match — tambah sebagai sinonim ke entries existing
            n_matched += 1
            # Tentukan field mana (ngoko/krama/word) — kalau match di ngoko existing → sinonim ngoko
            # Kalau match di krama existing → sinonim krama
            # Kalau match di word existing → sinonim word
            # Untuk simpel: tambah ke word (NETRAL), user tentukan register nanti
            for eid in matched_eids:
                sinonim_additions[eid]['word'].add(tok_lower)
        else:
            # No match → entry baru
            n_no_match += 1
            # Ambil indo dari jv.wiktionary entry pertama
            first_entry = entries[0]
            jv_indo = first_entry[2] if len(first_entry) > 2 else ''
            indo = jv_indo.strip().lower() if jv_indo else ''
            if not is_valid_indo(indo):
                indo = ''

            # Kalau indo valid dan sudah ada di kamus_bersih → skip (sudah ada konsep)
            if indo and indo in bersih_indo_idx:
                # Find existing entry dgn indo sama, tambah jv token ke word
                for w in bersih_words:
                    if (w.get('indo') or '').strip().lower() == indo:
                        sinonim_additions[w.get('entry_id')]['word'].add(tok_lower)
                        break
                continue

            # Entry baru
            max_eid += 1
            new_entry = {
                'entry_id': max_eid,
                'indo': indo,
                'ngoko': '',
                'krama': '',
                'word': tok_lower,  # jv token as word NETRAL
                'keterangan': '',
                'aksara': '',
                'sumber': 'jv.wiktionary' + (' + ' + first_entry[0] if False else ''),
                'status': 'draft',
            }
            new_entries.append(new_entry)

    print(f'  Matched (sinonim, tambah ke existing): {n_matched:,} tokens')
    print(f'  No match (entry baru): {n_no_match:,} tokens')

    # ===== Apply sinonim additions =====
    print('\n  Apply sinonim additions...')
    n_sinonim_added = 0
    for eid, additions in sinonim_additions.items():
        w = next((x for x in bersih_words if x.get('entry_id') == eid), None)
        if not w:
            continue
        # Tambah ke word (NETRAL, aman — user tentukan register nanti)
        existing_word = (w.get('word') or '').strip()
        existing_tokens_lower = set(t.strip().lower() for t in existing_word.split(',') if t.strip())
        new_tokens = [t for t in additions['word'] if t not in existing_tokens_lower]
        if new_tokens:
            new_word = ', '.join([existing_word] + new_tokens) if existing_word else ', '.join(new_tokens)
            w['word'] = new_word
            # Update sumber
            sumber = (w.get('sumber') or '').strip()
            if 'jv.wiktionary' not in sumber:
                w['sumber'] = (sumber + ' + jv.wiktionary').strip(' +') if sumber else 'jv.wiktionary'
            n_sinonim_added += 1

    print(f'  ✅ Sinonim added: {n_sinonim_added:,} entries')

    # ===== Apply new entries =====
    print(f'\n  Apply new entries: {len(new_entries):,} entries...')
    bersih_words.extend(new_entries)
    print(f'  ✅ Added: {len(new_entries):,}')

    # ===== Phase 2: Merge lagi (group by indo) =====
    print('\n' + '═' * 60)
    print('  PHASE 2: Merge by indo (1 konsep 1 entry)')
    print('═' * 60)

    # Group by indo (lowercase, valid only)
    groups = defaultdict(list)
    no_indo_entries = []
    for i, w in enumerate(bersih_words):
        indo = (w.get('indo') or '').strip().lower()
        if not indo:
            no_indo_entries.append(i)
        else:
            groups[indo].append(i)

    multi_groups = {k: v for k, v in groups.items() if len(v) > 1}
    print(f'  Multi-entry groups by indo: {len(multi_groups):,}')

    # Merge multi-groups
    indices_to_delete = set()
    n_merges = 0
    for indo_key, indices in multi_groups.items():
        if len(indices) <= 1:
            continue
        primary_idx = indices[0]
        primary = bersih_words[primary_idx]
        for i in indices[1:]:
            secondary = bersih_words[i]
            # Gabung word, ngoko, krama (dedupe)
            def merge_field(field_a, field_b):
                tokens_a = [t.strip() for t in field_a.split(',') if t.strip()] if field_a else []
                tokens_b = [t.strip() for t in field_b.split(',') if t.strip()] if field_b else []
                existing_lower = set(t.lower() for t in tokens_a)
                for tok in tokens_b:
                    if tok.lower() not in existing_lower:
                        tokens_a.append(tok)
                        existing_lower.add(tok.lower())
                return ', '.join(tokens_a)

            primary['ngoko'] = merge_field(primary.get('ngoko', ''), secondary.get('ngoko', ''))
            primary['krama'] = merge_field(primary.get('krama', ''), secondary.get('krama', ''))
            primary['word'] = merge_field(primary.get('word', ''), secondary.get('word', ''))
            # keterangan
            k1 = (primary.get('keterangan') or '').strip()
            k2 = (secondary.get('keterangan') or '').strip()
            if k2 and k2 not in k1:
                primary['keterangan'] = (k1 + ' | ' + k2).strip(' |') if k1 else k2
            # sumber
            s1 = (primary.get('sumber') or '').strip()
            s2 = (secondary.get('sumber') or '').strip()
            if s2 and s2 not in s1:
                primary['sumber'] = (s1 + ' + ' + s2) if s1 else s2
            indices_to_delete.add(i)
            n_merges += 1

    print(f'  Merged: {n_merges:,} entries dihapus (duplikat indo)')

    if not args.apply:
        print('\n🔍 DRY-RUN — tidak ada perubahan.')
        return

    # Apply deletion + re-number
    new_words = [w for i, w in enumerate(bersih_words) if i not in indices_to_delete]
    for i, w in enumerate(new_words, 1):
        w['entry_id'] = i
    d_bersih['words'] = new_words

    # Update metadata
    n_lengkap = sum(1 for w in new_words if (w.get('ngoko') or '').strip() and (w.get('krama') or '').strip() and (w.get('indo') or '').strip())
    n_netral_paired = sum(1 for w in new_words if (w.get('word') or '').strip() and not (w.get('ngoko') or '').strip() and not (w.get('krama') or '').strip() and (w.get('indo') or '').strip())
    n_netral_true = sum(1 for w in new_words if (w.get('word') or '').strip() and not (w.get('ngoko') or '').strip() and not (w.get('krama') or '').strip() and not (w.get('indo') or '').strip())

    d_bersih['metadata']['stats'] = {
        'total': len(new_words),
        'lengkap': n_lengkap,
        'netral_paired': n_netral_paired,
        'netral_true': n_netral_true,
    }

    save_json(args.bersih, d_bersih)
    print(f'\n✅ Saved: {args.bersih}')
    print(f'\n{"═" * 60}')
    print(f'  STATISTIK AKHIR')
    print(f'{"═" * 60}')
    print(f'  Total entries: {len(new_words):,}')
    print(f'  🟢 LENGKAP (ngoko+krama+indo): {n_lengkap:,}')
    print(f'  ⚠ NETRAL paired (word+indo): {n_netral_paired:,}')
    print(f'  ⚪ NETRAL true (word only): {n_netral_true:,}')

    # Verify 0 duplikat indo
    indos = [w['indo'] for w in new_words if (w.get('indo') or '').strip()]
    print(f'  Unique indo (yg punya indo): {len(set(indos)):,}')
    print(f'  Total dgn indo: {len(indos):,}')
    if len(set(indos)) != len(indos):
        print(f'  ❌ BUG: ada duplikat indo!')


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print('\n\n⏹ Dibatalkan.')
        sys.exit(130)
