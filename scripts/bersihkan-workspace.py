#!/usr/bin/env python3
"""
bersihkan-workspace.py — Bersihkan kamus-workspace cross-reference kamus_bersih master.

User: 'Sementara 12k kamus bersih jadi master,
sekarang bersihkan netral di kamus workspace,
yg indo masuk indo, yg jawa masuk ngoko atau krama, jika ragu masuk word.'

Strategy:
1. Load kamus_bersih (master) — 12.753 entries
2. Load kamus-workspace — 38.463 entries (NETRAL true)
3. Untuk tiap workspace entry:
   a. Cek word di master jv_idx (sinonim):
      - Match → tambah word ke master entry (sinonim)
   b. Cek word di master indo_idx (Indonesia leak):
      - Match → hapus word dari workspace, masuk ke indo workspace
      - (word workspace = Indonesia, bukan Jawa — leak dari sastra-jawa/milstrike)
   c. No match → tetap di workspace (NETRAL true, akan jadi entry baru)
4. Has workspace baru:
   - NETRAL true (word only) — entries yg word JAWA, no match di master
   - Indo only — entries yg word = Indonesia (leak fix), indo tetap valid
5. Update master: tambah sinonim word dari workspace match

R-63: Workspace cross-ref master. Sinonim masuk word master.
R-64: Indonesia leak di word → hapus word, indo tetap valid.
R-65: No match → tetap workspace (NETRAL true), register ragu = word.
"""

import json
from collections import defaultdict


def main():
    master_path = '/home/z/my-project/srt-splitter-clone/public/kamus_bersih.json'
    workspace_path = '/home/z/my-project/srt-splitter-clone/public/kamus-workspace.json'

    # Load
    d_master = json.load(open(master_path))
    master_words = d_master['words']
    d_ws = json.load(open(workspace_path))
    ws_words = d_ws['words']

    print(f'Master kamus_bersih: {len(master_words):,}')
    print(f'Workspace: {len(ws_words):,}')
    print()

    # Build master indexes
    master_indo_idx = {}
    master_jv_idx = defaultdict(set)
    master_eid_to_w = {w.get('entry_id'): w for w in master_words}
    for w in master_words:
        eid = w.get('entry_id')
        indo = (w.get('indo') or '').strip().lower()
        if indo:
            master_indo_idx[indo] = w
        for field in ['ngoko', 'krama', 'word']:
            val = (w.get(field) or '').strip()
            if val:
                for tok in val.split(','):
                    tok = tok.strip().lower()
                    if tok:
                        master_jv_idx[tok].add(eid)

    # Process workspace
    n_match_jv = 0          # match jv di master → sinonim ke word master
    n_indo_leak = 0         # word workspace = indo master → hapus word, masuk indo only
    n_no_match = 0          # tetap workspace NETRAL true
    n_indo_already = 0      # workspace punya indo (no word)

    # Track sinonim additions ke master
    master_additions = defaultdict(set)  # entry_id → set of tokens to add

    # Build new workspace
    new_ws_words = []

    for w in ws_words:
        eid_ws = w.get('entry_id')
        word = (w.get('word') or '').strip()
        indo = (w.get('indo') or '').strip()
        keterangan = (w.get('keterangan') or '').strip()
        sumber = (w.get('sumber') or '').strip()

        if indo:
            # Indo only entry (dari sastra-jawa v2 jv empty)
            new_ws_words.append(w)
            n_indo_already += 1
            continue

        if not word:
            # Empty entry — skip (anti-skip gak boleh ada empty)
            continue

        # Tokenize word
        tokens = [t.strip().lower() for t in word.split(',') if t.strip()]
        match_master_eids = set()
        leak_tokens = []
        jv_tokens = []

        for tok in tokens:
            if tok in master_jv_idx:
                # Match jv di master → sinonim
                match_master_eids.update(master_jv_idx[tok])
                jv_tokens.append(tok)
            elif tok in master_indo_idx:
                # Token = indo di master → Indonesia leak
                leak_tokens.append(tok)
            else:
                # No match — tetap jv token
                jv_tokens.append(tok)

        if match_master_eids:
            # Sinonim ke master — tambah jv_tokens ke word master
            n_match_jv += 1
            for master_eid in match_master_eids:
                master_additions[master_eid].update(jv_tokens)
            # Workspace entry dihapus (sudah masuk master)
        elif leak_tokens:
            # Indonesia leak — hapus word, masuk indo only
            n_indo_leak += 1
            new_entry = {
                'entry_id': 0,  # renumber nanti
                'indo': leak_tokens[0],  # ambil token pertama sbg indo
                'ngoko': '',
                'krama': '',
                'word': '',  # hapus (Indonesia leak)
                'keterangan': keterangan + ' | [LEAK FIX: word asli=' + word + ']' if keterangan else '[LEAK FIX: word asli=' + word + ']',
                'aksara': '',
                'sumber': sumber,
                'status': 'draft',
            }
            new_ws_words.append(new_entry)
        else:
            # No match — tetap workspace NETRAL true
            n_no_match += 1
            new_ws_words.append(w)

    # Apply additions ke master
    n_master_updated = 0
    for master_eid, tokens in master_additions.items():
        w = master_eid_to_w.get(master_eid)
        if not w: continue
        existing_word = (w.get('word') or '').strip()
        existing_tokens = set(t.strip().lower() for t in existing_word.split(',') if t.strip())
        new_tokens = [t for t in tokens if t not in existing_tokens]
        if new_tokens:
            # Tambah ke word
            if existing_word:
                w['word'] = existing_word + ', ' + ', '.join(sorted(new_tokens))
            else:
                w['word'] = ', '.join(sorted(new_tokens))
            # Update sumber
            sumber = (w.get('sumber') or '').strip()
            if 'workspace' not in sumber:
                w['sumber'] = (sumber + ' + workspace').strip(' +') if sumber else 'workspace'
            n_master_updated += 1

    # Renumber workspace
    for i, w in enumerate(new_ws_words, 1):
        w['entry_id'] = i

    # Save
    json.dump({
        'metadata': {
            'version': 'v3 (post cross-ref master)',
            'description': 'Kamus BERSIH master (post cross-ref workspace)',
            'stats': {'total': len(master_words)},
        },
        'words': master_words,
    }, open(master_path, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)

    json.dump({
        'metadata': {
            'version': 'v3 (post cross-ref master)',
            'description': 'Workspace NETRAL true + indo only (post cross-ref)',
            'stats': {'total': len(new_ws_words)},
        },
        'words': new_ws_words,
    }, open(workspace_path, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)

    print('═' * 60)
    print('  HASIL BERSIHKAN WORKSPACE')
    print('═' * 60)
    print(f'  Match jv di master (sinonim): {n_match_jv:,} → tambah ke word master')
    print(f'  Indonesia leak fix: {n_indo_leak:,} → hapus word, masuk indo only')
    print(f'  No match (tetap NETRAL true): {n_no_match:,}')
    print(f'  Indo already (dari v2): {n_indo_already:,}')
    print(f'  Master updated (sinonim tambah): {n_master_updated:,}')
    print()
    print(f'  Master kamus_bersih: {len(master_words):,} (updated)')
    print(f'  Workspace baru: {len(new_ws_words):,}')
    print(f'    - NETRAL true (no match): {n_no_match:,}')
    print(f'    - Indo only (leak fix + v2): {n_indo_leak + n_indo_already:,}')

    # Statistik akhir master
    n_lengkap = sum(1 for w in master_words if (w.get('ngoko') or '').strip() and (w.get('krama') or '').strip() and (w.get('indo') or '').strip())
    n_word_indo = sum(1 for w in master_words if (w.get('word') or '').strip() and (w.get('indo') or '').strip() and not (w.get('ngoko') or '').strip() and not (w.get('krama') or '').strip())
    print(f'\n=== Master kamus_bersih updated ===')
    print(f'  Total: {len(master_words):,}')
    print(f'  🟢 LENGKAP: {n_lengkap:,}')
    print(f'  ⚠ word+indo: {n_word_indo:,}')


if __name__ == '__main__':
    main()
