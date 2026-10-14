#!/usr/bin/env python3
"""
merge-milstrike.py v3 — Merge kamus milstrike_jv_id.json ke kamus_unified.json
+ Standarisasi baku jv wiktionary
+ Auto-merge SEMUA duplikat lintas entry (1 KONSEP 1 ENTRY, hasil 0 duplikat)

User: 'parsing simpel saja:
  jika ada kata identik = merge,
  kalau sinonim = tulis koma, entah itu di ngoko, indo, krama.
  sehingga hasil apapun engga ada duplikat.
  Alasan apapun engga ada duplikat. karena sudah sinonim.
  jangan ada data yg dihapus, jika identik merge/rewrite itu wajar,
  jika konsep sama? tinggal masuk sinonim.'

Strategy v3:
1. STANDARISASI baku: milstrike jv_key → baku jv wiktionary
   - Build baku index dari word field kamus (sudah baku dari jv wiktionary raw)
   - Untuk tiap milstrike jv_key, cari match (case-insensitive + diacritic-insensitive)
   - Match single → replace dengan baku (mis. 'ampek' → 'ampèk')
   - Multi baku → ambil yg paling sering muncul di word field
   - No match → tetap apa adanya

2. MERGE milstrike ke kamus_unified:
   - Phase 1: jv_key baku match di SEMUA field existing (word/ngoko/krama)
     - indo kosong → FILL indo dengan milstrike value
     - indo word_leak pattern → REPLACE (auto, milstrike lebih bersih)
     - indo OK → SKIP
   - Phase 2: milstrike value match indo existing → SINONIM
     - Tambah jv_key baku ke word field (NETRAL, manusia tentukan register nanti)
   - Phase 3: tidak match → ADD new entry (word=jv_key baku, indo=value)

3. AUTO-MERGE SEMUA DUPLIKAT:
   - Build 1 index gabungan SEMUA field (word+ngoko+krama+indo)
   - Untuk tiap token di 2+ entries → merge otomatis (rewrite ke entry pertama)
   - 1 konsep 1 entry, multi sinonim dengan koma
   - Tidak ada data dihapus, hanya entry duplikat yg di-merge ke entry primary

R-29: TIDAK ADA SINONIM BEDA ENTRY — kalau kata sama di entry beda = duplikat → merge.
R-34: 1 KONSEP 1 ENTRY, sinonim dengan koma.
R-36: Tidak ada data dihapus. Identik → merge/rewrite. Konsep sama → sinonim.

Usage:
  python3 merge-milstrike.py                    # dry-run
  python3 merge-milstrike.py --apply            # eksekusi merge + auto-merge duplikat
  python3 merge-milstrike.py --apply --skip-auto-merge  # skip auto-merge duplikat
"""

import os
import sys
import json
import argparse
import datetime
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
    """Normalize + hapus diacritics (é→e, ê→e, è→e, etc)."""
    nf = unicodedata.normalize('NFKD', s)
    return ''.join(c for c in nf if not unicodedata.combining(c)).lower()


def tokenize_key(key):
    """Tokenize key milstrike (sinonim: 'awakmu, sampean, koe' = kamu)."""
    tokens = []
    for sep in [',', ';']:
        if sep in key:
            for tok in key.split(sep):
                tok = tok.strip()
                if tok and tok not in tokens:
                    tokens.append(tok)
    if not tokens:
        tokens = [key.strip()]
    return tokens


def tokenize_field(value):
    """Tokenize field value (pisah by comma)."""
    if not value:
        return []
    return [t.strip().lower() for t in value.split(',') if t.strip()]


def build_baku_index(words):
    """Build baku index dari word field kamus.
    Return:
      baku_idx: {stripped: Counter of baku forms}  (untuk voting multi-baku)
    """
    baku_idx = defaultdict(Counter)
    for w in words:
        word = (w.get('word') or '').strip()
        if not word: continue
        for tok in word.split(','):
            tok = tok.strip()
            if tok and len(tok) > 1:
                stripped = strip_diacritics(tok)
                baku_idx[stripped][tok] += 1
    return baku_idx


def standardize_token(token, baku_idx):
    """Standarisasi 1 token ke baku jv wiktionary.
    Return (baku_form, status) dimana status = 'match'|'multi'|'no_match'.
    """
    if not token or len(token) <= 1:
        return token, 'no_match'
    stripped = strip_diacritics(token)
    baku_counter = baku_idx.get(stripped)
    if not baku_counter:
        return token, 'no_match'
    if len(baku_counter) == 1:
        baku = next(iter(baku_counter))
        return baku, 'match'
    # Multi baku — voting (ambil yg paling sering muncul di word field)
    baku = baku_counter.most_common(1)[0][0]
    return baku, 'multi'


def standardize_key(key, baku_idx):
    """Standarisasi milstrike key (bisa multi-token) ke baku jv wiktionary."""
    tokens = tokenize_key(key)
    baku_tokens = []
    n_match = n_multi = n_no = 0
    for tok in tokens:
        baku, status = standardize_token(tok, baku_idx)
        baku_tokens.append(baku)
        if status == 'match': n_match += 1
        elif status == 'multi': n_multi += 1
        else: n_no += 1
    # Rejoin dengan separator original (kalau ada comma/semicolon)
    if ',' in key:
        return ', '.join(baku_tokens), n_match, n_multi, n_no
    elif ';' in key:
        return '; '.join(baku_tokens), n_match, n_multi, n_no
    else:
        return baku_tokens[0] if baku_tokens else key, n_match, n_multi, n_no


def build_field_index(words):
    """Build index per field (lowercase token → list of entry_ids)."""
    idx = {
        'word':  defaultdict(list),
        'ngoko': defaultdict(list),
        'krama': defaultdict(list),
        'indo':  defaultdict(list),
    }
    for w in words:
        eid = w.get('entry_id')
        for field in idx:
            val = (w.get(field) or '').strip()
            if not val:
                continue
            for tok in val.split(','):
                tok = tok.strip().lower()
                if tok and len(tok) > 1 and eid not in idx[field][tok]:
                    idx[field][tok].append(eid)
    return idx


def is_word_leak_indo(entry, milstrike_value):
    """Cek apakah existing indo = 'word; definisi:' (label wiktionary mentah)."""
    word = (entry.get('word') or '').strip().lower()
    indo = (entry.get('indo') or '').strip()
    if not word or not indo:
        return False
    indo_first = indo.split(';')[0].strip().lower()
    return indo_first == word and (';' in indo or ':' in indo)


def add_sinonim_to_field(entry, new_token, target_field):
    """Tambah new_token ke field (word/ngoko/krama) dengan koma (sinonim).
    Cek duplikat dulu. Return True kalau ditambah.
    """
    existing = (entry.get(target_field) or '').strip()
    existing_tokens = [t.strip().lower() for t in existing.split(',') if t.strip()]
    if new_token.lower() in existing_tokens:
        return False
    new_val = f'{existing}, {new_token}' if existing else new_token
    entry[target_field] = new_val
    return True


def merge_with_comma(a, b):
    """Gabung 2 string field dengan koma, dedupe case-insensitive."""
    if not a: return b
    if not b: return a
    tokens = [t.strip() for t in a.split(',') if t.strip()]
    existing_lower = set(t.lower() for t in tokens)
    for tok in b.split(','):
        tok = tok.strip()
        if tok and tok.lower() not in existing_lower:
            tokens.append(tok)
            existing_lower.add(tok.lower())
    return ', '.join(tokens)


def build_all_idx(words):
    """Build 1 index gabungan SEMUA field (lintas field, lintas entry).
    Return {token_lower: set of (eid, field)}.
    """
    all_idx = defaultdict(set)
    for w in words:
        eid = w.get('entry_id')
        if eid is None: continue
        for field in ['word', 'ngoko', 'krama', 'indo']:
            val = (w.get(field) or '').strip()
            if not val: continue
            for tok in val.split(','):
                tok = tok.strip().lower()
                if tok:
                    all_idx[tok].add((eid, field))
    return all_idx


def auto_merge_all_duplicates(data, baku_idx):
    """Auto-merge SEMUA duplikat lintas entry (1 KONSEP 1 ENTRY).

    Strategy:
    - Build 1 index gabungan SEMUA field
    - Untuk tiap token di 2+ entries:
      - Merge entries ke 1 primary (ambil entry_id paling kecil)
      - Gabung word/ngoko/krama/indo dengan koma
      - Combine aksara + keterangan + sumber
      - Delete entries secondary
      - Re-number entry_id

    R-29: TIDAK ADA SINONIM BEDA ENTRY — kalau kata sama di entry beda = duplikat → merge.
    R-34: 1 KONSEP 1 ENTRY, sinonim dengan koma.
    R-36: Tidak ada data dihapus, hanya entry duplikat di-merge.

    Return: jumlah merge yg dilakukan.
    """
    words = data['words']
    n_merges = 0

    while True:
        all_idx = build_all_idx(words)
        # Cari token di 2+ entries
        dupes = {tok: locs for tok, locs in all_idx.items()
                 if len(set(eid for eid, _ in locs)) > 1}
        if not dupes:
            break

        # Ambil duplikat pertama (token dgn #entries terbanyak)
        sorted_dupes = sorted(dupes.items(),
                              key=lambda x: len(set(eid for eid, _ in x[1])),
                              reverse=True)
        tok, locations = sorted_dupes[0]
        unique_eids = sorted(set(eid for eid, _ in locations))
        if len(unique_eids) < 2:
            break

        # Primary = entry_id terkecil
        primary_eid = unique_eids[0]
        primary_idx = next(i for i, w in enumerate(words) if w.get('entry_id') == primary_eid)
        primary = words[primary_idx]

        # Merge SEMUA secondary ke primary
        for sec_eid in unique_eids[1:]:
            sec_idx = next(i for i, w in enumerate(words) if w.get('entry_id') == sec_eid)
            secondary = words[sec_idx]

            # Gabung SEMUA field dengan koma
            primary['word'] = merge_with_comma(primary.get('word', ''), secondary.get('word', ''))
            primary['ngoko'] = merge_with_comma(primary.get('ngoko', ''), secondary.get('ngoko', ''))
            primary['krama'] = merge_with_comma(primary.get('krama', ''), secondary.get('krama', ''))
            primary['indo'] = merge_with_comma(primary.get('indo', ''), secondary.get('indo', ''))

            # Combine aksara
            a1 = (primary.get('aksara') or '').strip()
            a2 = (secondary.get('aksara') or '').strip()
            if a2 and a2 not in a1:
                primary['aksara'] = merge_with_comma(a1, a2)

            # Combine keterangan
            k1 = (primary.get('keterangan') or '').strip()
            k2 = (secondary.get('keterangan') or '').strip()
            if k2 and k2 not in k1:
                primary['keterangan'] = f'{k1} | {k2}'.strip(' |') if k1 else k2

            # Sumber
            s1 = (primary.get('sumber') or '').strip()
            s2 = (secondary.get('sumber') or '').strip()
            if s2 and s2 not in s1:
                primary['sumber'] = f'{s1} + merge #{sec_eid}' if s1 else f'merge #{sec_eid}'

            # R-12: status='draft' setelah merge
            primary['status'] = 'draft'

            # Delete secondary
            del words[sec_idx]
            n_merges += 1

        # Re-number entry_id
        for i, w in enumerate(words, 1):
            w['entry_id'] = i

    return n_merges


def main():
    parser = argparse.ArgumentParser(description='Merge milstrike + auto-merge duplikat')
    parser.add_argument('--apply', action='store_true',
                        help='Eksekusi merge (default: dry-run)')
    parser.add_argument('--skip-auto-merge', action='store_true',
                        help='Skip auto-merge duplikat setelah merge milstrike')
    parser.add_argument('--milstrike', default=None)
    parser.add_argument('--kamus', default=None)
    args = parser.parse_args()

    # Cari milstrike file
    milstrike_paths = [
        args.milstrike,
        Path.home() / 'Dubbing' / 'milstrike_jv_id.json',
        Path(__file__).parent / 'milstrike_jv_id.json',
    ]
    milstrike_path = None
    for p in milstrike_paths:
        if p and Path(p).exists():
            milstrike_path = Path(p)
            break
    if not milstrike_path:
        print('❌ milstrike_jv_id.json tidak ditemukan.')
        sys.exit(1)

    # Cari kamus file
    kamus_paths = [
        args.kamus,
        Path.home() / 'Dubbing' / 'kamus_unified_draft.json',
        Path.home() / 'Dubbing' / 'kamus_unified.json',
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

    print(f'📁 Milstrike: {milstrike_path}')
    print(f'📁 Kamus:     {kamus_path}')
    print()

    ms = load_json(milstrike_path)
    kamus = load_json(kamus_path)
    words = kamus['words']

    print(f'📊 Milstrike entries: {len(ms):,}')
    print(f'📊 Kamus entries:     {len(words):,}')
    print()

    # ============ STEP 1: STANDARISASI BAKU ============
    print('═' * 60)
    print('  STEP 1: STANDARISASI milstrike jv_key ke baku jv wiktionary')
    print('═' * 60)
    baku_idx = build_baku_index(words)
    print(f'  Total baku variants di kamus word field: {sum(len(v) for v in baku_idx.values()):,}')

    # Standarisasi tiap milstrike key
    ms_baku = {}  # key_baku → value
    n_match = n_multi = n_no = 0
    samples_standar = []
    for key, value in ms.items():
        baku_key, m, mu, no = standardize_key(key, baku_idx)
        n_match += m
        n_multi += mu
        n_no += no
        ms_baku[baku_key] = value
        if (m > 0 or mu > 0) and len(samples_standar) < 10:
            if key != baku_key:
                samples_standar.append((key, baku_key))

    print(f'  Match baku (single): {n_match:,}')
    print(f'  Multi baku (voting):  {n_multi:,}')
    print(f'  No match (tetap):    {n_no:,}')
    print()
    print('  Sample standarisasi:')
    for orig, baku in samples_standar:
        print(f"    {orig!r} → {baku!r}")
    print()

    # ============ STEP 2: MERGE milstrike ke kamus ============
    print('═' * 60)
    print('  STEP 2: MERGE milstrike (baku) ke kamus_unified')
    print('═' * 60)
    idx = build_field_index(words)
    eid_to_entry = {w.get('entry_id'): w for w in words}

    fill_count = replace_count = skip_count = sinonim_count = add_count = 0
    fill_actions = []
    replace_actions = []
    sinonim_actions = []
    add_actions = []

    for key_baku, value in ms_baku.items():
        value = (value or '').strip()
        if not value:
            continue
        key_tokens = tokenize_key(key_baku)

        # Phase 1: Match di word/ngoko/krama
        matched_entries = {}
        for tok in key_tokens:
            tl = tok.lower()
            for field in ['word', 'ngoko', 'krama']:
                if tl in idx[field]:
                    for eid in idx[field][tl]:
                        matched_entries.setdefault(eid, set())
                        matched_entries[eid].add(field)

        if matched_entries:
            sorted_eids = sorted(matched_entries.keys())
            for eid in sorted_eids:
                entry = eid_to_entry.get(eid)
                if not entry:
                    continue
                indo_existing = (entry.get('indo') or '').strip()
                if not indo_existing:
                    fill_actions.append((eid, key_baku, value))
                    fill_count += 1
                    break
                elif is_word_leak_indo(entry, value):
                    replace_actions.append((eid, key_baku, value, indo_existing))
                    replace_count += 1
                    break
                else:
                    skip_count += 1
                    break
            continue

        # Phase 2: SINONIM by indo match
        value_lower = value.lower()
        if value_lower in idx['indo']:
            for eid in idx['indo'][value_lower]:
                entry = eid_to_entry.get(eid)
                if not entry:
                    continue
                primary_key = key_tokens[0]
                # Default target = word (NETRAL, manusia tentukan register nanti)
                added = add_sinonim_to_field(entry, primary_key, 'word')
                if added:
                    sinonim_actions.append((eid, key_baku, value))
                    sinonim_count += 1
                else:
                    skip_count += 1
                break
            continue

        # Phase 3: ADD new entry
        add_actions.append((key_baku, value))
        add_count += 1

    print(f'  ✅ FILL indo kosong (NETRAL→paired):     {fill_count:5,}')
    print(f'  🔄 REPLACE word_leak (auto, milstrike lebih bersih): {replace_count:5,}')
    print(f'  🔗 SINONIM (key beda, indo sama → koma di word): {sinonim_count:5,}')
    print(f'  ⏭ SKIP indo existing OK:                {skip_count:5,}')
    print(f'  ➕ ADD new entry (no match):            {add_count:5,}')
    print()

    # ============ STEP 3: AUTO-MERGE SEMUA DUPLIKAT ============
    print('═' * 60)
    print('  STEP 3: AUTO-MERGE SEMUA duplikat lintas entry')
    print('═' * 60)
    # Preview duplikat sekarang (TANPA apply merge milstrike dulu — estimasi)
    all_idx_pre = build_all_idx(words)
    dupes_pre = {tok: locs for tok, locs in all_idx_pre.items()
                 if len(set(eid for eid, _ in locs)) > 1}
    print(f'  Duplikat saat ini (pre-merge milstrike): {len(dupes_pre):,} token')
    print()

    if not args.apply:
        print('🔍 DRY-RUN MODE — tidak ada perubahan.')
        print('   Untuk eksekusi: python3 merge-milstrike.py --apply')
        return

    # ===== APPLY =====
    print('═' * 60)
    print('  🚀 APPLY MERGE')
    print('═' * 60)

    # Backup
    backup_path = kamus_path.with_suffix('.json.bak.' + datetime.datetime.now().strftime('%Y%m%d_%H%M%S'))
    save_json(backup_path, kamus)
    print(f'  ✅ Backup: {backup_path}')

    # Apply FILL
    print(f'  Apply FILL ({fill_count})...')
    for eid, key, value in fill_actions:
        entry = eid_to_entry.get(eid)
        if not entry: continue
        entry['indo'] = value
        entry['status'] = 'draft'
        sumber = (entry.get('sumber') or '').strip()
        if 'milstrike' not in sumber:
            entry['sumber'] = (sumber + ' + milstrike').strip(' +') if sumber else 'milstrike'

    # Apply REPLACE
    print(f'  Apply REPLACE ({replace_count})...')
    for eid, key, value, _ in replace_actions:
        entry = eid_to_entry.get(eid)
        if not entry: continue
        entry['indo'] = value
        entry['status'] = 'draft'
        sumber = (entry.get('sumber') or '').strip()
        if 'milstrike' not in sumber:
            entry['sumber'] = (sumber + ' + milstrike').strip(' +') if sumber else 'milstrike'

    # Apply SINONIM
    print(f'  Apply SINONIM ({sinonim_count})...')
    for eid, key, value in sinonim_actions:
        entry = eid_to_entry.get(eid)
        if not entry: continue
        primary_key = tokenize_key(key)[0]
        add_sinonim_to_field(entry, primary_key, 'word')
        entry['status'] = 'draft'
        sumber = (entry.get('sumber') or '').strip()
        if 'milstrike' not in sumber:
            entry['sumber'] = (sumber + ' + milstrike').strip(' +') if sumber else 'milstrike'

    # Apply ADD
    print(f'  Apply ADD ({add_count})...')
    max_eid = max((w.get('entry_id', 0) for w in words), default=0)
    for key, value in add_actions:
        max_eid += 1
        new_entry = {
            'entry_id': max_eid,
            'word': key,
            'ngoko': '',
            'krama': '',
            'indo': value,
            'keterangan': '',
            'aksara': '',
            'sumber': 'milstrike',
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

    save_json(kamus_path, kamus)
    print(f'  ✅ Saved (post-milstrike): {kamus_path}')
    print(f'  Total entries: {len(words):,} (sebelum: 43.630, +{add_count})')
    print()

    # Step 3: Auto-merge SEMUA duplikat
    if not args.skip_auto_merge:
        print(f'  Auto-merge SEMUA duplikat...')
        # Reload kamus
        kamus = load_json(kamus_path)
        n_merges = auto_merge_all_duplicates(kamus, baku_idx)
        save_json(kamus_path, kamus)
        print(f'  ✅ Auto-merge done: {n_merges} entries di-merge ke primary')
        print(f'  Total entries: {len(kamus["words"]):,} (setelah auto-merge)')

        # Final check: masih ada duplikat?
        all_idx_post = build_all_idx(kamus['words'])
        dupes_post = {tok: locs for tok, locs in all_idx_post.items()
                      if len(set(eid for eid, _ in locs)) > 1}
        print(f'  Duplikat tersisa: {len(dupes_post):,}  (target: 0)')
        if dupes_post:
            print(f'  ⚠ Masih ada duplikat — mungkin edge case (multi-token, etc). Cek manual via kamus-tui.')
    else:
        print(f'  Skip auto-merge (--skip-auto-merge)')

    print()
    print('═' * 60)
    print(f'  ✅ MERGE SELESAI')
    print(f'  FILL: {fill_count} | REPLACE: {replace_count} | SINONIM: {sinonim_count} | ADD: {add_count}')
    print(f'  Backup: {backup_path}')
    print('═' * 60)


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print('\n\n⏹ Dibatalkan.')
        sys.exit(130)
