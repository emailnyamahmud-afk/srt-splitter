#!/usr/bin/env python3
"""
pisah-kamus-bersih.py — Pisahkan kamus_bersih.json jadi 2 file:
1. kamus_bersih.json — HANYA entries dgn indo VALID (jangkar indo, 1 konsep 1 entry)
2. jv-lemma-raw.json — NETRAL true entries (word only, no indo) sebagai workspace

User: 'AI SALAH, 39k itu masih kotor bukan bersih.'

Bug: kamus_bersih.json sebelumnya berisi 49.445 entries, 38.463 NETRAL true (word only, no indo).
Itu bukan bersih — word aja, indo kosong, gak ada jangkar. Sampah dipindah tempat.

Fix:
- kamus_bersih.json = entries dgn indo VALID (R-48: indo jangkar)
  Total: ~10.982 entries (turun dari 49.445)
- jv-lemma-raw.json = NETRAL true entries (word only, no indo) — workspace untuk user isi indo manual
  Total: ~38.463 entries

R-54: kamus_bersih = HANYA entries dgn indo VALID. Tidak ada NETRAL true.
R-55: NETRAL true → workspace terpisah (jv-lemma-raw.json), bukan kamus_bersih.
"""

import json
import re
import sys
from pathlib import Path


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


def main():
    kamus_path = '/home/z/my-project/srt-splitter-clone/public/kamus_bersih.json'
    jv_raw_path = '/home/z/my-project/srt-splitter-clone/public/jv-lemma-raw.json'

    d = json.load(open(kamus_path))
    words = d['words']
    print(f'Loaded: {len(words):,} entries')

    # Split
    bersih_words = []
    jv_raw_words = []
    for w in words:
        indo = (w.get('indo') or '').strip()
        ngoko = (w.get('ngoko') or '').strip()
        krama = (w.get('krama') or '').strip()
        word = (w.get('word') or '').strip()

        if is_valid_indo(indo) and (ngoko or krama or word):
            # indo valid + punya jv → kamus_bersih
            bersih_words.append(w)
        elif word and not indo:
            # NETRAL true (word only) → jv-lemma-raw workspace
            jv_raw_words.append(w)
        else:
            # Edge case — indo tidak valid, skip
            print(f'  ⚠ #{w.get("entry_id")} indo={indo!r} ngoko={ngoko!r} krama={krama!r} word={word!r}')

    print(f'\nSplit:')
    print(f'  kamus_bersih (indo valid): {len(bersih_words):,}')
    print(f'  jv-lemma-raw (NETRAL true workspace): {len(jv_raw_words):,}')

    # Re-number kamus_bersih
    for i, w in enumerate(bersih_words, 1):
        w['entry_id'] = i

    # Save kamus_bersih (clean)
    d_bersih = {
        'metadata': {
            'version': 'v2 (Indo jangkar, NETRAL true dipisah)',
            'description': 'Kamus Jawa-Indonesia BERSIH (1 konsep 1 entry, indo jangkar)',
            'sources': ['sastra-jawa', 'milstrike', 'existing kamus_unified_draft (LENGKAP)', 'jv.wiktionary (cross-ref sinonim)'],
            'schema': {
                'fields': ['entry_id', 'indo (JANGKAR)', 'ngoko', 'krama', 'word (NETRAL)', 'keterangan', 'aksara', 'sumber', 'status'],
            },
            'stats': {
                'total': len(bersih_words),
            },
        },
        'words': bersih_words,
    }
    json.dump(d_bersih, open(kamus_path, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
    print(f'\n✅ Saved kamus_bersih: {kamus_path}')

    # Re-number jv-lemma-raw
    for i, w in enumerate(jv_raw_words, 1):
        w['entry_id'] = i

    # Save jv-lemma-raw (workspace)
    d_raw = {
        'metadata': {
            'version': 'v1 (jv.wiktionary lemma, NETRAL true workspace)',
            'description': 'Lemma Jawa dari jv.wiktionary (word only, belum ada indo) — workspace untuk user isi indo manual',
            'schema': {
                'fields': ['entry_id', 'word (JAWA LEMMA)', 'keterangan (raw jv.wiktionary)', 'sumber', 'status'],
            },
            'stats': {
                'total': len(jv_raw_words),
            },
        },
        'words': jv_raw_words,
    }
    json.dump(d_raw, open(jv_raw_path, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
    print(f'✅ Saved jv-lemma-raw: {jv_raw_path}')

    # Verify kamus_bersih — 0 NETRAL true, 0 duplikat indo
    print(f'\n=== VERIFY kamus_bersih ===')
    n_netral_true = sum(1 for w in bersih_words
        if (w.get('word') or '').strip()
        and not (w.get('ngoko') or '').strip()
        and not (w.get('krama') or '').strip()
        and not (w.get('indo') or '').strip())
    print(f'  NETRAL true (word only, no indo): {n_netral_true} (harus 0)')

    indos = [(w.get('indo') or '').strip().lower() for w in bersih_words]
    print(f'  Unique indo: {len(set(indos)):,}')
    print(f'  Total entries: {len(indos):,}')
    print(f'  Duplikat indo: {len(indos) - len(set(indos))}')

    # Stats kelengkapan kamus_bersih
    n_lengkap = sum(1 for w in bersih_words if (w.get('ngoko') or '').strip() and (w.get('krama') or '').strip() and (w.get('indo') or '').strip())
    n_netral_paired = sum(1 for w in bersih_words if (w.get('word') or '').strip() and not (w.get('ngoko') or '').strip() and not (w.get('krama') or '').strip() and (w.get('indo') or '').strip())
    n_ngoko_only = sum(1 for w in bersih_words if (w.get('ngoko') or '').strip() and not (w.get('krama') or '').strip() and (w.get('indo') or '').strip())
    n_krama_only = sum(1 for w in bersih_words if not (w.get('ngoko') or '').strip() and (w.get('krama') or '').strip() and (w.get('indo') or '').strip())

    print(f'\n  🟢 LENGKAP (ngoko+krama+indo): {n_lengkap:,}')
    print(f'  ⚠ NETRAL paired (word+indo):   {n_netral_paired:,}')
    print(f'  🔵 ngoko+indo (krama kosong):  {n_ngoko_only:,}')
    print(f'  🔵 krama+indo (ngoko kosong):  {n_krama_only:,}')


if __name__ == '__main__':
    main()
