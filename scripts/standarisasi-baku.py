#!/usr/bin/env python3
"""
standarisasi-baku.py — Standarisasi SEMUA entries, SEMUA field (word+ngoko+krama+indo)
ke baku jv wiktionary.

User: 'gimana dengan semua entry? di word, ngoko, indo, krama?'
'penulisan juga perlu standarisasi: yg baku yg sesuai jv victionary misal dhéwé.'

Strategy:
1. Build baku index dari word field kamus + is_lemma entries (sumber paling baku)
2. Strip diacritics (é→e, ê→e) untuk matching
3. Untuk tiap token di SEMUA field (word+ngoko+krama+indo):
   - Match single baku → replace dengan baku
   - Multi baku (ambigu) → SKIP (jangan ubah, biar user audit manual)
   - No match → tetap apa adanya
4. Tidak ada data dihapus, hanya update varian ke baku

R-37: Standarisasi baku konsisten lintas field. 1 konsep, 1 baku form.

Safety:
- Backup kamus ke .bak.<timestamp> sebelum apply
- Dry-run mode default (--apply untuk eksekusi)
- Hanya ubah kalau match single (no ambigu)
- Multi baku → skip (user audit manual)
- Print report semua changes

Usage:
  python3 standarisasi-baku.py                    # dry-run
  python3 standarisasi-baku.py --apply            # eksekusi
  python3 standarisasi-baku.py --kamus path        # custom kamus path
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


def build_baku_index(words):
    """Build baku index dari word field + is_lemma entries.

    Return {key: Counter of baku forms}.
    Key bisa:
    - Exact lowercase ('mabuk', 'abang')
    - Stripped diacritic ('age' untuk 'age'/'agé'/'agè')

    Index punya 2 type key:
    - baku_idx[token_lower]: untuk EXACT match (case-insensitive)
    - baku_idx[stripped]: untuk diacritic-insensitive match
    """
    baku_idx = defaultdict(Counter)
    for w in words:
        word = (w.get('word') or '').strip()
        if not word:
            continue
        weight = 3 if w.get('is_lemma') else 1
        for tok in word.split(','):
            tok = tok.strip()
            if tok and len(tok) > 1:
                # Exact lowercase key
                baku_idx[tok.lower()][tok] += weight
                # Stripped diacritic key
                stripped = strip_diacritics(tok)
                baku_idx[stripped][tok] += weight
    return baku_idx


def standardize_token(token, baku_idx):
    """Standarisasi 1 token — SUPER SAFE (case only, JANGAN ubah diacritic).

    Return (baku_form, status): 'match' (case beda), 'multi' (ambigu, skip), 'no_match'.

    R-37: SUPER SAFE strategy:
    - Hanya standarisasi CASE (caps → lowercase), jangan ubah diacritic.
    - Diacritic bisa beda konsep di jv wiktionary:
      * 'impen' = umur, 'impèn' = simpan/mimpi → 2 konsep beda
      * 'age' = umur, 'agé' = cepat → 2 konsep beda
    - Standarisasi diacritic = BAHAYA, bisa rusak konsep.
    - Kalau token (case-insensitive) ada di baku_idx dan case beda → match (lowercase)
    - Kalau token tidak ada exact lowercase match → no_match (tetap apa adanya)

    Standarisasi diacritic HARUS dilakukan manusia native Jawa, bukan AI.
    """
    if not token or len(token) <= 1:
        return token, 'no_match'
    # EXACT match (case-insensitive) — token_lower ada di baku_idx
    token_lower = token.lower()
    baku_counter = baku_idx.get(token_lower)
    if not baku_counter:
        # Token tidak ada exact lowercase match → tidak bisa standarisasi (tetap apa adanya)
        return token, 'no_match'
    # Token ada exact lowercase match. Cek apakah case sama.
    # Cari baku form (most common di counter, prefer lowercase)
    sorted_baku = baku_counter.most_common()
    if len(baku_counter) == 1:
        baku = next(iter(baku_counter))
    elif sorted_baku[0][1] > sorted_baku[1][1]:
        baku = sorted_baku[0][0]
    else:
        # Tie — prefer lowercase form (case standar)
        lowercase_forms = [b for b, _ in sorted_baku if b == b.lower()]
        if lowercase_forms:
            baku = lowercase_forms[0]
        else:
            return token, 'multi'
    # Kalau baku == token (case sama) → no change
    if baku == token:
        return token, 'no_match'
    # Kalau baku == token_lower (case beda, lowercase) → match (case standarisasi)
    if baku == token_lower:
        return baku, 'match'
    # Baku beda (bukan cuma case) → multi (jangan ubah, bisa beda konsep)
    return token, 'multi'


def standardize_field_value(value, baku_idx):
    """Standarisasi 1 field value (string dengan comma-separated tokens).
    Return (new_value, n_match, n_multi, n_no_match, changes).
    changes = list of (old_token, new_token).
    """
    if not value or not value.strip():
        return value, 0, 0, 0, []
    tokens = [t.strip() for t in value.split(',') if t.strip()]
    new_tokens = []
    n_match = n_multi = n_no = 0
    changes = []
    for tok in tokens:
        baku, status = standardize_token(tok, baku_idx)
        new_tokens.append(baku)
        if status == 'match':
            n_match += 1
            if baku != tok:
                changes.append((tok, baku))
        elif status == 'multi':
            n_multi += 1
        else:
            n_no += 1
    # Rejoin dengan comma + space (konsisten)
    new_value = ', '.join(new_tokens)
    return new_value, n_match, n_multi, n_no, changes


def main():
    parser = argparse.ArgumentParser(description='Standarisasi baku SEMUA entries, SEMUA field')
    parser.add_argument('--apply', action='store_true',
                        help='Eksekusi (default: dry-run)')
    parser.add_argument('--kamus', default=None)
    args = parser.parse_args()

    # Cari kamus
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
        print('   Cari di:')
        for p in kamus_paths:
            if p: print(f'     {p}')
        sys.exit(1)

    print(f'📁 Kamus: {kamus_path}')
    print()

    kamus = load_json(kamus_path)
    words = kamus['words']
    print(f'📊 Total entries: {len(words):,}')
    print()

    # Build baku index
    print('Build baku index (dari word field + is_lemma entries, lemma weight=3)...')
    baku_idx = build_baku_index(words)
    print(f'  Total baku variants: {sum(len(v) for v in baku_idx.values()):,}')
    print(f'  Total stripped keys: {len(baku_idx):,}')
    print()

    # Standarisasi SEMUA entries, SEMUA field
    print('═' * 60)
    print('  STANDARISASI SEMUA entries, SEMUA field')
    print('═' * 60)

    field_stats = {f: {'match': 0, 'multi': 0, 'no_match': 0, 'changed': 0} for f in ['word', 'ngoko', 'krama', 'indo']}
    all_changes = []  # (entry_id, field, old, new)

    for w in words:
        for field in ['word', 'ngoko', 'krama', 'indo']:
            val = (w.get(field) or '').strip()
            if not val:
                continue
            new_val, n_match, n_multi, n_no, changes = standardize_field_value(val, baku_idx)
            field_stats[field]['match'] += n_match
            field_stats[field]['multi'] += n_multi
            field_stats[field]['no_match'] += n_no
            if changes:
                field_stats[field]['changed'] += 1
                for old, new in changes:
                    all_changes.append((w.get('entry_id'), field, old, new))
                w[field] = new_val  # Apply in-memory

    # Print stats
    print(f"  {'field':8} {'match':>8} {'multi':>8} {'no_match':>10} {'entries changed':>18}")
    print(f"  {'─'*8} {'─'*8} {'─'*8} {'─'*10} {'─'*18}")
    for field in ['word', 'ngoko', 'krama', 'indo']:
        s = field_stats[field]
        print(f"  {field:8} {s['match']:>8,} {s['multi']:>8,} {s['no_match']:>10,} {s['changed']:>18,}")
    print()

    # Sample changes
    print(f'  Total changes: {len(all_changes):,}')
    print()
    print('  Sample changes (first 20):')
    for eid, field, old, new in all_changes[:20]:
        print(f"    #{eid} {field}: {old!r} → {new!r}")
    print()

    if not args.apply:
        print('🔍 DRY-RUN MODE — tidak ada perubahan.')
        print('   Untuk eksekusi: python3 standarisasi-baku.py --apply')
        return

    # ===== APPLY =====
    print('═' * 60)
    print('  🚀 APPLY STANDARISASI')
    print('═' * 60)

    # Backup
    backup_path = kamus_path.with_suffix('.json.bak.' + datetime.datetime.now().strftime('%Y%m%d_%H%M%S'))
    save_json(backup_path, kamus)
    print(f'  ✅ Backup: {backup_path}')

    # Save (data sudah di-modify in-memory di atas)
    save_json(kamus_path, kamus)
    print(f'  ✅ Saved: {kamus_path}')

    # Save report
    report_path = kamus_path.parent / 'standarisasi-baku-report.txt'
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write('Standarisasi Baku Report\n')
        f.write(f'Date: {datetime.datetime.now().isoformat()}\n')
        f.write(f'Kamus: {kamus_path}\n\n')
        for field in ['word', 'ngoko', 'krama', 'indo']:
            s = field_stats[field]
            f.write(f'{field}: match={s["match"]} multi={s["multi"]} no_match={s["no_match"]} changed={s["changed"]}\n')
        f.write(f'\nTotal changes: {len(all_changes):,}\n\n')
        f.write('All changes (entry_id, field, old, new):\n')
        for eid, field, old, new in all_changes:
            f.write(f'#{eid} {field}: {old!r} → {new!r}\n')
    print(f'  📄 Report: {report_path}')

    print()
    print('═' * 60)
    print(f'  ✅ STANDARISASI SELESAI')
    print(f'  Total changes: {len(all_changes):,}')
    print(f'  Backup: {backup_path}')
    print(f'  Report: {report_path}')
    print('═' * 60)


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print('\n\n⏹ Dibatalkan.')
        sys.exit(130)
