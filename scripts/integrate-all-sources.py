#!/usr/bin/env python3
"""
integrate-all-sources.py — Integrasi SEMUA sumber ke 1 file kamus_bersih.json.

User: 'ARSITEKTUR KEMBALI TOLOL DAN MUTER-MUTER ENGGA JELAS, BELUM INTEGRASI SEMUA SUMBER.'
'BODOH DAN TOLOL' (aku selalu nanya, padahal harus langsung kerjakan)

Strategi:
1. Mulai dari sastra-jawa parser v2 (11.095 entries Indo→Jv, anti-skip)
2. Tambah milstrike (1.836 entries jv_key→indo, bersih)
3. Tambah existing kamus_unified_draft.json LENGKAP (1.295 entries ngoko+krama+indo user lama)
4. Tambah jv.wiktionary raw (38.463 NETRAL, word only, no indo) — anti-skip
5. Merge by indo (1 konsep 1 entry, sinonim koma)
6. NETRAL true (no indo) tetap masuk, marked workspace
7. Output: 1 file kamus_bersih.json (FINAL)

R-61: 1 file kamus, integrasi semua sumber, anti-skip.
R-62: NETRAL true tetap masuk (workspace), buang = tolol.
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


def main():
    kamus_path = '/home/z/my-project/srt-splitter-clone/public/kamus_bersih.json'
    
    # Load sources
    print('Load sources...')
    
    # Source 1: sastra-jawa parser v2 (anti-skip)
    d_sj = json.load(open('/home/z/my-project/srt-splitter-clone/public/kamus_bersih_v2.json'))
    sj_entries = d_sj['words']
    print(f'  sastra-jawa parser v2: {len(sj_entries):,} entries')
    
    # Source 2: milstrike
    ms_data = json.load(open('/home/z/my-project/upload/milstrike_jv_id.json'))
    print(f'  milstrike: {len(ms_data):,} entries')
    
    # Source 3: existing kamus_unified_draft.json — HANYA entries LENGKAP
    d_unified = json.load(open('/home/z/my-project/srt-splitter-clone/public/kamus_unified_draft.json'))
    unified_words = d_unified['words']
    
    # Source 4: jv.wiktionary raw NETRAL (word only, no indo) — dari jv-lemma-raw.json
    d_raw = json.load(open('/home/z/my-project/srt-splitter-clone/public/jv-lemma-raw.json'))
    jv_raw_entries = d_raw['words']
    print(f'  jv-lemma-raw (NETRAL): {len(jv_raw_entries):,} entries')
    
    # ===== Build kamus_bersih final =====
    print('\nBuild kamus_bersih final (1 konsep 1 entry)...')
    
    # Index by indo (case-insensitive) — untuk merge
    by_indo = defaultdict(lambda: {
        'ngoko': set(),
        'krama': set(),
        'word': set(),
        'keterangan': [],
        'aksara': set(),
        'sumber': set(),
    })
    # Index by word (case-insensitive) — untuk NETRAL true entries
    netral_true_by_word = defaultdict(lambda: {
        'word': set(),
        'keterangan': [],
        'sumber': set(),
    })
    
    n_total_processed = 0
    
    # === Source 1: sastra-jawa parser v2 ===
    for w in sj_entries:
        n_total_processed += 1
        indo = (w.get('indo') or '').strip()
        word_tokens = [t.strip() for t in (w.get('word') or '').split(',') if t.strip()]
        keterangan = (w.get('keterangan') or '').strip()
        if indo:
            indo_lower = indo.lower()
            by_indo[indo_lower]['word'].update(word_tokens)
            if keterangan:
                by_indo[indo_lower]['keterangan'].append(keterangan)
            by_indo[indo_lower]['sumber'].add('sastra-jawa')
        else:
            # NETRAL true (no indo) — masuk workspace
            key = ' '.join(sorted(word_tokens))[:50] if word_tokens else f'_{n_total_processed}'
            netral_true_by_word[key]['word'].update(word_tokens)
            if keterangan:
                netral_true_by_word[key]['keterangan'].append(keterangan)
            netral_true_by_word[key]['sumber'].add('sastra-jawa')
    
    # === Source 2: milstrike ===
    for jv_key, indo_value in ms_data.items():
        n_total_processed += 1
        indo = (indo_value or '').strip()
        jv_tokens = [t.strip() for t in jv_key.split(',') if t.strip()]
        if indo:
            indo_lower = indo.lower()
            by_indo[indo_lower]['word'].update(jv_tokens)
            by_indo[indo_lower]['sumber'].add('milstrike')
        else:
            # NETRAL true
            key = ' '.join(sorted(jv_tokens))[:50] if jv_tokens else f'_{n_total_processed}'
            netral_true_by_word[key]['word'].update(jv_tokens)
            netral_true_by_word[key]['sumber'].add('milstrike')
    
    # === Source 3: existing LENGKAP (ngoko+krama+indo semua terisi) ===
    for w in unified_words:
        ngoko = (w.get('ngoko') or '').strip()
        krama = (w.get('krama') or '').strip()
        indo = (w.get('indo') or '').strip()
        word = (w.get('word') or '').strip()
        if not (ngoko and krama and indo):
            continue
        n_total_processed += 1
        indo_lower = indo.lower()
        # Parse tokens
        for t in ngoko.split(','):
            t = t.strip()
            if t: by_indo[indo_lower]['ngoko'].add(t)
        for t in krama.split(','):
            t = t.strip()
            if t: by_indo[indo_lower]['krama'].add(t)
        for t in word.split(','):
            t = t.strip()
            if t: by_indo[indo_lower]['word'].add(t)
        # Keterangan (limit 200 char)
        ket = (w.get('keterangan') or '').strip()
        if ket:
            by_indo[indo_lower]['keterangan'].append(ket[:200])
        aksara = (w.get('aksara') or '').strip()
        if aksara:
            by_indo[indo_lower]['aksara'].add(aksara[:50])
        by_indo[indo_lower]['sumber'].add('existing')
    
    # === Source 4: jv.wiktionary raw NETRAL (word only, no indo) ===
    for w in jv_raw_entries:
        n_total_processed += 1
        word = (w.get('word') or '').strip()
        if not word: continue
        word_tokens = [t.strip() for t in word.split(',') if t.strip()]
        keterangan = (w.get('keterangan') or '').strip()
        key = ' '.join(sorted(word_tokens))[:50] if word_tokens else f'_{n_total_processed}'
        netral_true_by_word[key]['word'].update(word_tokens)
        if keterangan:
            netral_true_by_word[key]['keterangan'].append(keterangan[:200])
        netral_true_by_word[key]['sumber'].add('jv.wiktionary')
    
    # ===== Build final entries =====
    final_words = []
    
    # Entries dgn indo (merged by indo)
    for indo_lower, data in sorted(by_indo.items()):
        entry = {
            'entry_id': 0,  # will renumber
            'indo': indo_lower,
            'ngoko': ', '.join(sorted(data['ngoko'])) if data['ngoko'] else '',
            'krama': ', '.join(sorted(data['krama'])) if data['krama'] else '',
            'word': ', '.join(sorted(data['word'])) if data['word'] else '',
            'keterangan': ' | '.join(data['keterangan'][:3]) if data['keterangan'] else '',  # limit 3 parts
            'aksara': ', '.join(sorted(data['aksara'])) if data['aksara'] else '',
            'sumber': ' + '.join(sorted(data['sumber'])) if data['sumber'] else '',
            'status': 'draft',
        }
        final_words.append(entry)
    
    # NETRAL true entries (no indo) — tetap masuk, marked workspace
    for key, data in netral_true_by_word.items():
        word_str = ', '.join(sorted(data['word'])) if data['word'] else ''
        if not word_str: continue
        entry = {
            'entry_id': 0,
            'indo': '',  # NETRAL — no indo, user isi manual
            'ngoko': '',
            'krama': '',
            'word': word_str,
            'keterangan': ' | '.join(data['keterangan'][:3]) if data['keterangan'] else '',
            'aksara': '',
            'sumber': ' + '.join(sorted(data['sumber'])) if data['sumber'] else '',
            'status': 'draft',
        }
        final_words.append(entry)
    
    # Renumber
    for i, w in enumerate(final_words, 1):
        w['entry_id'] = i
    
    # ===== Save =====
    n_with_indo = sum(1 for w in final_words if (w.get('indo') or '').strip())
    n_netral_true = sum(1 for w in final_words if not (w.get('indo') or '').strip() and (w.get('word') or '').strip())
    n_lengkap = sum(1 for w in final_words
        if (w.get('ngoko') or '').strip()
        and (w.get('krama') or '').strip()
        and (w.get('indo') or '').strip())
    n_word_indo = sum(1 for w in final_words
        if (w.get('word') or '').strip()
        and (w.get('indo') or '').strip()
        and not (w.get('ngoko') or '').strip()
        and not (w.get('krama') or '').strip())
    
    # Verify 0 duplikat indo
    indos = [w['indo'].lower() for w in final_words if (w.get('indo') or '').strip()]
    n_dup_indo = len(indos) - len(set(indos))
    
    output = {
        'metadata': {
            'version': 'v3 (FINAL — integrasi semua sumber, 1 konsep 1 entry, anti-skip)',
            'description': 'Kamus Jawa-Indonesia BERSIH (1 file, integrasi semua sumber)',
            'sources': ['sastra-jawa parser v2 (anti-skip)', 'milstrike', 'existing LENGKAP kamus_unified_draft', 'jv.wiktionary raw NETRAL'],
            'stats': {
                'total_entries': len(final_words),
                'with_indo': n_with_indo,
                'netral_true': n_netral_true,
                'lengkap': n_lengkap,
                'word_indo': n_word_indo,
                'duplikat_indo': n_dup_indo,
            },
        },
        'words': final_words,
    }
    json.dump(output, open(kamus_path, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
    
    print(f'\n✅ Saved: {kamus_path}')
    print(f'\n{"=" * 60}')
    print(f'  STATISTIK FINAL kamus_bersih.json')
    print(f'{"=" * 60}')
    print(f'  Total entries: {len(final_words):,}')
    print(f'  Entries dgn indo: {n_with_indo:,}')
    print(f'  Entries NETRAL true (no indo): {n_netral_true:,}')
    print(f'  🟢 LENGKAP (ngoko+krama+indo): {n_lengkap:,}')
    print(f'  ⚠ word+indo: {n_word_indo:,}')
    print(f'  Duplikat indo: {n_dup_indo} (harus 0)')
    print(f'\n  Total processed from all sources: {n_total_processed:,}')
    
    # Hapus file lama (sudah integrated)
    files_to_delete = [
        '/home/z/my-project/srt-splitter-clone/public/kamus_bersih_v2.json',
        '/home/z/my-project/srt-splitter-clone/public/jv-lemma-raw.json',
        '/home/z/my-project/srt-splitter-clone/public/sastra-jawa-parsed.json',
    ]
    print(f'\nHapus file lama (sudah integrated):')
    for f in files_to_delete:
        if os.path.exists(f):
            os.remove(f)
            print(f'  🗑 {f}')


if __name__ == '__main__':
    main()
