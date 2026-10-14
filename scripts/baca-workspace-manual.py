#!/usr/bin/env python3
"""
baca-workspace-manual.py — Baca manual 36.888 entries workspace, pisahkan:
- mana indo (cross-ref keterangan ke master)
- mana jawa ngoko (heuristic akhiran)
- mana krama (heuristic akhiran)
- kalau ragu → word

User: '36.888 = BACA MANUAL, PISAHKAN MANA INDO, MANA JAWA NGOKO,
MANA KRAMA (KALAU ENGGA BISA BEDAKAN NGOKO DAN KRAMA = MASUK WORD)'

Strategy:
1. Build master index: jv_token → indo (dari kamus_bersih master)
2. Untuk tiap workspace entry:
   - Keterangan punya arti Jawa (mis. 'prabot sarta bebakaling omah')
   - Ekstrak token Jawa pertama dari keterangan (split # koma)
   - Cross-ref token Jawa ke master jv_idx:
     - Match → ambil indo master → isi indo workspace
   - Tentukan register (ngoko/krama) dari heuristic akhiran:
     - -ipun, -ipun → krama
     - -a, -e, -i → ragu, masuk word
   - Kalau ragu register → word (NETRAL paired)
3. Anti-skip — semua tetap masuk, ragu → keterangan

R-66: Workspace cross-ref keterangan ke master utk ekstrak indo.
R-67: Register ragu → word (anti-skip, NETRAL paired).
"""

import json
import re
from collections import defaultdict


def is_valid_jv_token(tok):
    if not tok: return False
    tok = tok.strip().strip('.')
    if len(tok) < 2: return False
    if len(tok) > 25: return False
    if tok[0].isdigit(): return False
    if re.search(r'[*#\[\]{}]', tok): return False
    vowels = set('aeiouéèêěəôöāīū')
    has_vowel = any(c in vowels for c in tok.lower())
    if not has_vowel: return False
    return True


def guess_register(word):
    """Heuristic register berdasarkan akhiran Jawa."""
    if not word: return None
    w = word.lower().strip()
    # Krama inggil (akhir -ipun)
    if w.endswith(('ipun', '-ipun', 'ipunipun')):
        return 'krama'
    # Krama (akhir -en, -in) — tapi bisa juga ngoko
    # -an: bisa dua-duanya (skip)
    # -a, -e, -i: ragu (skip)
    # Krama inggil serapan Arab/Sanskrit: tidak bisa determine dari akhiran
    return None  # ragu → word


def main():
    master_path = '/home/z/my-project/srt-splitter-clone/public/kamus_bersih.json'
    workspace_path = '/home/z/my-project/srt-splitter-clone/public/kamus-workspace.json'

    d_master = json.load(open(master_path))
    master_words = d_master['words']
    d_ws = json.load(open(workspace_path))
    ws = d_ws['words']

    print(f'Master: {len(master_words):,}')
    print(f'Workspace: {len(ws):,}')
    print()

    # Build master jv → indo index
    jv_to_indo = defaultdict(set)
    for w in master_words:
        indo = (w.get('indo') or '').strip().lower()
        if not indo: continue
        for field in ['ngoko', 'krama', 'word']:
            val = (w.get(field) or '').strip()
            if val:
                for tok in val.split(','):
                    tok = tok.strip().lower()
                    if tok and len(tok) > 1:
                        jv_to_indo[tok].add(indo)
    print(f'Master jv→indo index: {len(jv_to_indo):,} tokens')

    # Process workspace
    n_indo_extracted = 0       # indo di-ekstrak dari keterangan
    n_indo_kept = 0             # indo existing (leak fix) tetap
    n_register_ngoko = 0
    n_register_krama = 0
    n_register_word_ragu = 0    # ragu → word
    n_no_change = 0             # NETRAL true tetap

    for w in ws:
        word = (w.get('word') or '').strip()
        indo = (w.get('indo') or '').strip()
        keterangan = (w.get('keterangan') or '').strip()

        if indo:
            # Sudah ada indo (leak fix), tetap
            n_indo_kept += 1
            continue

        if not word:
            continue

        # Strategy 1: Ekstrak indo dari keterangan (cross-ref ke master)
        if keterangan:
            # Ambil token Jawa pertama dari keterangan (setelah #)
            # Pattern: '# arti Jawa' atau '# arti Jawa lain' atau multi-baris
            arti_jawa = re.sub(r'^#+\s*', '', keterangan.split('\n')[0]).strip()
            # Ambil token pertama (sebelum koma)
            tokens_ket = [t.strip() for t in arti_jawa.split(',')]
            for tok in tokens_ket:
                tok_clean = tok.strip().rstrip('.').strip()
                if not is_valid_jv_token(tok_clean):
                    continue
                # Cross-ref ke master
                if tok_clean.lower() in jv_to_indo:
                    indo_match = jv_to_indo[tok_clean.lower()]
                    # Ambil indo (max 3 utk hindari noise)
                    indo_chosen = '; '.join(sorted(indo_match)[:3])
                    w['indo'] = indo_chosen
                    w['status'] = 'draft'
                    sumber = (w.get('sumber') or '').strip()
                    if 'cross-ref-ket' not in sumber:
                        w['sumber'] = (sumber + ' + cross-ref-ket').strip(' +') if sumber else 'cross-ref-ket'
                    n_indo_extracted += 1
                    break

        # Strategy 2: Tentukan register dari heuristic akhiran
        primary_token = word.split(',')[0].strip()
        reg = guess_register(primary_token)
        if reg == 'krama' and (w.get('indo') or '').strip():
            # Move word → krama (paired)
            w['krama'] = primary_token
            w['word'] = ''
            n_register_krama += 1
        elif reg == 'ngoko' and (w.get('indo') or '').strip():
            w['ngoko'] = primary_token
            w['word'] = ''
            n_register_ngoko += 1
        else:
            # Ragu → tetap word (NETRAL paired kalau ada indo, atau NETRAL true)
            n_register_word_ragu += 1

    # Statistik
    n_with_indo = sum(1 for w in ws if (w.get('indo') or '').strip())
    n_netral_paired = sum(1 for w in ws
        if (w.get('word') or '').strip()
        and (w.get('indo') or '').strip()
        and not (w.get('ngoko') or '').strip()
        and not (w.get('krama') or '').strip())
    n_netral_true = sum(1 for w in ws
        if (w.get('word') or '').strip()
        and not (w.get('indo') or '').strip())
    n_indo_only = sum(1 for w in ws
        if (w.get('indo') or '').strip()
        and not (w.get('word') or '').strip()
        and not (w.get('ngoko') or '').strip()
        and not (w.get('krama') or '').strip())

    # Save
    json.dump({
        'metadata': {
            'version': 'v4 (post baca-manual cross-ref)',
            'description': 'Workspace post cross-ref keterangan + register heuristic',
            'stats': {
                'total': len(ws),
                'indo_extracted': n_indo_extracted,
                'register_ngoko': n_register_ngoko,
                'register_krama': n_register_krama,
                'register_word_ragu': n_register_word_ragu,
            },
        },
        'words': ws,
    }, open(workspace_path, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)

    print('\n═' * 60)
    print('  HASIL BACA WORKSPACE MANUAL')
    print('═' * 60)
    print(f'  Indo extracted (cross-ref keterangan ke master): {n_indo_extracted:,}')
    print(f'  Indo kept (leak fix existing): {n_indo_kept:,}')
    print(f'  Register ngoko (heuristic): {n_register_ngoko:,}')
    print(f'  Register krama (heuristic): {n_register_krama:,}')
    print(f'  Register word (ragu): {n_register_word_ragu:,}')
    print()
    print(f'  Workspace stat akhir:')
    print(f'    Total: {len(ws):,}')
    print(f'    Dgn indo: {n_with_indo:,}')
    print(f'    NETRAL paired (word+indo): {n_netral_paired:,}')
    print(f'    NETRAL true (no indo): {n_netral_true:,}')
    print(f'    indo only (no jv): {n_indo_only:,}')

    # Sample
    print('\n=== Sample entries dgn indo extracted ===')
    n_show = 0
    for w in ws:
        indo = (w.get('indo') or '').strip()
        word = (w.get('word') or '').strip()
        sumber = (w.get('sumber') or '').strip()
        if 'cross-ref-ket' in sumber:
            print(f"  #{w.get('entry_id')} word={word[:25]!r} indo={indo[:50]!r}")
            print(f"    sumber: {sumber[:60]!r}")
            n_show += 1
            if n_show >= 10: break


if __name__ == '__main__':
    main()
