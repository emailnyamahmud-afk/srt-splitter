#!/usr/bin/env python3
"""
standardize-baku-jv.py — Standardize penulisan Jawa di master cross-ref ke jv.wiktionary.

User: 'TOLOL = penulisan cross reff ke jv victionary,
penulisan di jv victionary = penulisan jawa modern.'

Strategy (BENAR — bukan heuristic tolol):
1. Build baku index dari jv.wiktionary word field (45.181 tokens baku)
2. Untuk tiap token di master word/ngoko/krama field:
   - Exact lowercase match di jv.wiktionary → sudah baku, pakai apa adanya
   - Diacritic-insensitive match (strip_diacritics) → ambil baku form jv.wiktionary
   - No match → tetap apa adanya (AI gak bisa tentukan)
3. NO heuristic akhiran tolol (krama vs ngoko)
4. NO register determination (tugas user native Jawa)

Yang aku kerjakan: STANDARDIZE penulisan baku Jawa cross-ref jv.wiktionary.
Yang aku gak kerjakan: tentukan register (ngoko/krama).

R-68: Baku Jawa = cross-ref jv.wiktionary. Bukan heuristic.
R-69: Register (ngoko/krama) = tugas user native Jawa, AI gak bisa.
"""

import json
import unicodedata
from collections import defaultdict, Counter


def strip_diacritics(s):
    nf = unicodedata.normalize('NFKD', s)
    return ''.join(c for c in nf if not unicodedata.combining(c)).lower()


def main():
    # Build baku index dari jv.wiktionary (kamus_unified_draft.json word field)
    d_uni = json.load(open('/home/z/my-project/srt-splitter-clone/public/kamus_unified_draft.json'))
    uni_words = d_uni['words']

    baku_idx = defaultdict(Counter)
    for w in uni_words:
        word = (w.get('word') or '').strip()
        if not word: continue
        for tok in word.split(','):
            tok = tok.strip()
            if tok and len(tok) > 1:
                stripped = strip_diacritics(tok)
                baku_idx[stripped][tok] += 1

    print(f'Baku index jv.wiktionary: {len(baku_idx):,} stripped keys')

    # Load master
    d_m = json.load(open('/home/z/my-project/srt-splitter-clone/public/kamus_bersih.json'))
    master = d_m['words']

    def standardize_token(tok):
        """Standardize 1 token ke baku jv.wiktionary (penulisan modern)."""
        if not tok: return tok
        tok = tok.strip()
        stripped = strip_diacritics(tok)
        baku_counter = baku_idx.get(stripped)
        if not baku_counter:
            return tok  # no baku found — tetap
        # Exact match (case-insensitive)
        for baku_form in baku_counter:
            if baku_form.lower() == tok.lower():
                return baku_form  # pakai baku form
        # Diacritic-insensitive — ambil baku form
        if len(baku_counter) == 1:
            return next(iter(baku_counter))
        # Multi baku form — voting (paling sering muncul)
        sorted_baku = baku_counter.most_common()
        if sorted_baku[0][1] > sorted_baku[1][1]:
            return sorted_baku[0][0]
        # Tie — prefer form dgn diacritic (lebih spesifik)
        has_diacritic = [b for b, c in sorted_baku if b != strip_diacritics(b)]
        if len(has_diacritic) == 1:
            return has_diacritic[0]
        # Masih ambigu — tetap (user tentukan)
        return tok

    # Process tiap master entry — standardize word/ngoko/krama field
    n_tokens_changed = 0
    n_entries_changed = 0

    for w in master:
        entry_changed = False
        for field in ['word', 'ngoko', 'krama']:
            val = (w.get(field) or '').strip()
            if not val: continue
            tokens = [t.strip() for t in val.split(',') if t.strip()]
            new_tokens = []
            for tok in tokens:
                baku = standardize_token(tok)
                if baku != tok:
                    n_tokens_changed += 1
                    entry_changed = True
                new_tokens.append(baku)
            # Dedupe case-insensitive (preserve first baku form)
            seen = set()
            unique = []
            for t in new_tokens:
                if t.lower() not in seen:
                    seen.add(t.lower())
                    unique.append(t)
            w[field] = ', '.join(unique)
        if entry_changed:
            n_entries_changed += 1

    # Save
    json.dump(d_m, open('/home/z/my-project/srt-splitter-clone/public/kamus_bersih.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=2)

    print(f'\n✅ Standardize baku jv.wiktionary:')
    print(f'  Tokens changed: {n_tokens_changed:,}')
    print(f'  Entries changed: {n_entries_changed:,}')
    print(f'  Total entries: {len(master):,}')

    # Sample
    print('\n=== Sample 15 entries changed ===')
    n_show = 0
    for w in master:
        sumber = (w.get('sumber') or '').strip()
        # Cari entries dgn sumber sastra-jawa (yg word pasti banyak berubah)
        if 'sastra-jawa' not in sumber: continue
        word = (w.get('word') or '').strip()
        if not word: continue
        # Cek apakah word punya diacritic (yg udah standardize)
        if 'ê' in word or 'é' in word or 'è' in word:
            print(f"  #{w.get('entry_id')} word={word[:80]!r}")
            print(f"    indo={w.get('indo','')!r}")
            n_show += 1
            if n_show >= 15: break


if __name__ == '__main__':
    main()
