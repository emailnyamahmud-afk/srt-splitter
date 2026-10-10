#!/usr/bin/env python3
"""
duplikat-kata.py — Deteksi kata yang sama muncul di entry beda.

Input:  public/kamus-jawa-draft.json
Output: stdout (summary + sample) + /tmp/duplikat-kata.json (full report)

Logika:
1. Tokenisasi field ngoko, krama, arti (split by comma)
2. Strip whitespace, lowercase untuk case-insensitive compare
3. Untuk setiap token, catat entry_id + field tempat dia muncul
4. Token yang muncul di >1 entry = DUPlikat
5. Token yang muncul di >1 field di entry yang sama = CROSS-FIELD
6. Token yang muncul di field berbeda di entry beda = CROSS-FIELD-ENTRY

R-22: Hanya baca kamus-jawa-draft.json (sumber NETRAL). Tidak merujuk raw.
R-18: Tidak hapus entries, hanya audit + lapor.
"""

import json
import sys
import os
from collections import defaultdict
from pathlib import Path

KAMUS_PATH = Path(__file__).parent.parent / 'public' / 'kamus-jawa-draft.json'
OUTPUT_PATH = Path('/tmp/duplikat-kata.json')


def tokenize(s):
    """Tokenisasi field ngoko/krama/arti. Split by comma, strip, lowercase."""
    if not s:
        return []
    out = []
    for tok in s.split(','):
        t = tok.strip().lower()
        # Skip kosong, skip yang pure numeric (angka), skip yang panjang >50 (definisi ensiklopedis)
        if t and not t.isdigit() and len(t) <= 50:
            out.append(t)
    return out


def main():
    if not KAMUS_PATH.exists():
        print(f'❌ Tidak ketemu: {KAMUS_PATH}')
        sys.exit(1)

    print(f'→ Load {KAMUS_PATH.name}...')
    with open(KAMUS_PATH, 'r', encoding='utf-8') as f:
        data = json.load(f)
    words = data.get('words', [])
    print(f'  Total entries: {len(words):,}')

    # Index: token -> list of (entry_id, field, raw_word_field)
    # raw_word_field = isi field 'word' (NETRAL label) untuk konteks
    index = defaultdict(list)  # token -> [(entry_id, field, word_field)]
    print(f'→ Tokenisasi ngoko/krama/arti...')

    for i, w in enumerate(words, 1):
        entry_id = w.get('entry_id', i)
        word_field = (w.get('word') or '').strip()  # NETRAL label
        for field in ('ngoko', 'krama', 'arti'):
            for tok in tokenize(w.get(field, '')):
                index[tok].append((entry_id, field, word_field))

    # Filter: token yang muncul di >1 entry (atau >1 field di entry beda)
    print(f'→ Filter duplikat...')
    dup_entries = {}  # token -> list of (entry_id, field, word)
    dup_cross_field = {}  # token muncul di >1 field di entry beda

    for tok, occurrences in index.items():
        if len(occurrences) < 2:
            continue
        # Cek berapa entry unik
        unique_entries = set((eid, fld) for eid, fld, _ in occurrences)
        if len(unique_entries) < 2:
            continue
        dup_entries[tok] = occurrences
        # Cek cross-field (muncul di ngoko + krama, atau ngoko + arti, atau krama + arti)
        fields_in_dup = set(fld for _, fld, _ in occurrences)
        if len(fields_in_dup) > 1:
            dup_cross_field[tok] = occurrences

    print(f'')
    print(f'══════════════════════════════════════════════════════════════')
    print(f'  HASIL DETEKSI DUPLIKAT KATA (cross-entry)')
    print(f'══════════════════════════════════════════════════════════════')
    print(f'')
    print(f'  Total tokens di kamus:   {len(index):>10,}')
    print(f'  Token unik (1 entry):    {len(index) - len(dup_entries):>10,}')
    print(f'  Token duplikat (>1 entry): {len(dup_entries):>9,}')
    print(f'    - di field yang sama beda entry: {len(dup_entries) - len(dup_cross_field):>9,}')
    print(f'    - di field BEDA beda entry:       {len(dup_cross_field):>9,}')
    print(f'')

    # Sort by jumlah entry (paling banyak duplikat di atas)
    sorted_dup = sorted(dup_entries.items(), key=lambda x: -len(set(eid for eid, _, _ in x[1])))

    print(f'  TOP 30 token duplikat (paling banyak di entry beda):')
    print(f'  ─────────────────────────────────────────────────────────')
    print(f'  {"token":<25} {"#entries":>9} {"#occ":>6}  field distribution')
    print(f'  {"─"*25} {"─"*9} {"─"*6}  {"─"*30}')
    for tok, occ in sorted_dup[:30]:
        unique_eids = set(eid for eid, _, _ in occ)
        field_dist = defaultdict(int)
        for _, fld, _ in occ:
            field_dist[fld] += 1
        fd_str = ', '.join(f'{f}={n}' for f, n in sorted(field_dist.items()))
        print(f'  {tok[:25]:<25} {len(unique_eids):>9} {len(occ):>6}  {fd_str}')
    print(f'')

    # Cross-field sample (paling seru — token muncul di ngoko + krama di entry beda)
    print(f'  TOP 20 CROSS-FIELD (token di field BEDA di entry beda):')
    print(f'  ─────────────────────────────────────────────────────────')
    print(f'  {"token":<25} {"#entries":>9}  field distribution')
    print(f'  {"─"*25} {"─"*9}  {"─"*30}')
    sorted_cross = sorted(dup_cross_field.items(), key=lambda x: -len(set(eid for eid, _, _ in x[1])))
    for tok, occ in sorted_cross[:20]:
        unique_eids = set(eid for eid, _, _ in occ)
        field_dist = defaultdict(int)
        for _, fld, _ in occ:
            field_dist[fld] += 1
        fd_str = ', '.join(f'{f}={n}' for f, n in sorted(field_dist.items()))
        print(f'  {tok[:25]:<25} {len(unique_eids):>9}  {fd_str}')
    print(f'')

    # Detail sample 5 cross-field entries
    print(f'  DETAIL 5 cross-field (token di ngoko + krama di entry beda):')
    print(f'  ─────────────────────────────────────────────────────────')
    for tok, occ in sorted_cross[:5]:
        print(f'\n  Token: "{tok}"')
        for eid, fld, word_field in occ[:8]:
            # Find the entry to see context
            entry = words[eid - 1] if 1 <= eid <= len(words) else None
            if entry:
                ngoko = (entry.get('ngoko') or '')[:40]
                krama = (entry.get('krama') or '')[:40]
                arti = (entry.get('arti') or '')[:40]
                word = (entry.get('word') or '')[:30]
                print(f'    entry_id={eid:<6} field={fld:<6} word="{word}"')
                print(f'      ngoko: {ngoko}')
                print(f'      krama: {krama}')
                print(f'      arti:  {arti}')

    # Save full report
    report = {
        'summary': {
            'total_tokens': len(index),
            'duplicates_total': len(dup_entries),
            'duplicates_same_field': len(dup_entries) - len(dup_cross_field),
            'duplicates_cross_field': len(dup_cross_field),
        },
        'top_100_dup': [
            {
                'token': tok,
                'entries': list(set(eid for eid, _, _ in occ)),
                'occurrences': [{'entry_id': eid, 'field': fld, 'word': w} for eid, fld, w in occ],
            }
            for tok, occ in sorted_dup[:100]
        ],
        'cross_field': [
            {
                'token': tok,
                'entries': list(set(eid for eid, _, _ in occ)),
                'field_distribution': dict(sorted({fld for _, fld, _ in occ})),
                'occurrences': [{'entry_id': eid, 'field': fld, 'word': w} for eid, fld, w in occ],
            }
            for tok, occ in sorted_cross[:100]
        ],
    }
    with open(OUTPUT_PATH, 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(f'\n  Full report: {OUTPUT_PATH}')
    print(f'  Total duplikat (cross-entry): {len(dup_entries):,} tokens')


if __name__ == '__main__':
    main()
