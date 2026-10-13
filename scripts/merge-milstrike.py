#!/usr/bin/env python3
"""
merge-milstrike.py — Merge kamus milstrike_jv_id.json ke kamus_unified_draft.json

Source milstrike_jv_id.json (1.836 entries, format {kata_jawa: indo_translation}):
  - Quality SANGAT BERSIH — terjemahan singkat (1-3 kata), bukan definisi panjang
  - Jauh lebih bagus dari jv.wiktionary parsing

Strategi merge:
  1. Match key milstrike dengan kamus existing (word/ngoko/krama, lowercase, tokenized)
  2. Match + indo KOSONG → auto-isi indo dengan milstrike value
     (735 entries — NETRAL → jadi word+indo, status='draft')
  3. Match + indo TERISI → SKIP, print ke report untuk user audit manual
     (426 entries — user putuskan apakah milstrike lebih bersih daripada existing)
  4. No match → ADD new entry (word=key, indo=value, sumber='milstrike', status='draft')
     (675 entries)

Safety:
  - Backup kamus ke .bak sebelum merge (auto)
  - Tidak ada auto-replace indo existing (hanya FILL kosong)
  - Tidak ada auto-set ready (R-12 compliance)
  - Dry-run mode default (--apply untuk eksekusi)

Usage:
  python3 merge-milstrike.py                    # dry-run, print report only
  python3 merge-milstrike.py --apply            # eksekusi merge
  python3 merge-milstrike.py --milstrike path  # custom milstrike path
  python3 merge-milstrike.py --kamus path       # custom kamus path
"""

import os
import sys
import json
import argparse
import datetime
from pathlib import Path
from collections import defaultdict


def load_json(path):
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def save_json(path, data):
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def tokenize_key(key):
    """Tokenize key milstrike (bisa multi-sinonim: 'awakmu, sampean, koe' = kamu).
    Pisah by ',' dan ';' dan ' ; ' (separator aneh di milstrike).
    """
    tokens = []
    for sep in [',', ';']:
        if sep in key:
            for tok in key.split(sep):
                tok = tok.strip()
                if tok and tok not in tokens:
                    tokens.append(tok)
    if not tokens:
        # Tidak ada separator, key utuh = 1 token
        tokens = [key.strip()]
    return tokens


def build_index(words):
    """Build lowercase token → list of entry_id. Cek field word/ngoko/krama."""
    index = defaultdict(list)
    for w in words:
        eid = w.get('entry_id')
        for field in ['word', 'ngoko', 'krama']:
            val = (w.get(field) or '').strip()
            if val:
                for tok in val.split(','):
                    tok = tok.strip().lower()
                    if tok and len(tok) > 1:
                        if eid not in index[tok]:
                            index[tok].append(eid)
    return index


def is_word_leak_indo(entry, milstrike_value):
    """Cek apakah existing indo = 'word; definisi:' (label wiktionary mentah).
    Kalau iya, milstrike_value bisa replace jadi lebih bersih.
    """
    word = (entry.get('word') or '').strip().lower()
    indo = (entry.get('indo') or '').strip()
    if not word or not indo:
        return False
    indo_first = indo.split(';')[0].strip().lower()
    return indo_first == word and (';' in indo or ':' in indo)


def main():
    parser = argparse.ArgumentParser(description='Merge milstrike_jv_id.json ke kamus')
    parser.add_argument('--apply', action='store_true',
                        help='Eksekusi merge (default: dry-run)')
    parser.add_argument('--milstrike', default=None,
                        help='Path ke milstrike_jv_id.json (default: cari di beberapa lokasi)')
    parser.add_argument('--kamus', default=None,
                        help='Path ke kamus_unified_draft.json (default: cari di beberapa lokasi)')
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
        print('   Cari di:')
        for p in milstrike_paths:
            if p: print(f'     {p}')
        print('   Letakkan file di ~/Dubbing/milstrike_jv_id.json atau pakai --milstrike <path>')
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
        print('   Cari di:')
        for p in kamus_paths:
            if p: print(f'     {p}')
        sys.exit(1)

    print(f'📁 Milstrike: {milstrike_path}')
    print(f'📁 Kamus:     {kamus_path}')
    print()

    # Load
    ms = load_json(milstrike_path)
    kamus = load_json(kamus_path)
    words = kamus['words']

    print(f'📊 Milstrike entries: {len(ms):,}')
    print(f'📊 Kamus entries:     {len(words):,}')
    print()

    # Build index kamus
    print('Bangun index kamus...')
    index = build_index(words)
    print(f'  Total token unik di kamus: {len(index):,}')
    print()

    # Match logic
    fill_count = 0           # Match + indo kosong → auto-fill
    replace_candidates = 0    # Match + indo terisi + word_leak → bisa replace
    skip_count = 0           # Match + indo terisi + tidak word_leak → skip
    add_count = 0            # No match → add new

    fill_actions = []        # (entry_id, key, value)
    replace_actions = []      # (entry_id, key, milstrike_value, existing_indo)
    skip_actions = []
    add_actions = []          # (key, value)

    for key, value in ms.items():
        value = (value or '').strip()
        if not value:
            continue
        # Tokenize key milstrike (sinonim bisa multi-token)
        key_tokens = tokenize_key(key)
        matched_entries = set()
        for tok in key_tokens:
            tok_lower = tok.lower()
            if tok_lower in index:
                for eid in index[tok_lower]:
                    matched_entries.add(eid)

        if matched_entries:
            # Match — pilih entry pertama untuk action (kalau multi-match, log di report)
            for eid in sorted(matched_entries):
                entry = next(w for w in words if w.get('entry_id') == eid)
                indo_existing = (entry.get('indo') or '').strip()
                if not indo_existing:
                    # Indo kosong → FILL
                    fill_actions.append((eid, key, value))
                    fill_count += 1
                    break  # Hanya fill entry pertama yg match
                elif is_word_leak_indo(entry, value):
                    # Indo existing = label wiktionary → milstrike lebih bersih
                    replace_actions.append((eid, key, value, indo_existing))
                    replace_candidates += 1
                    break
                else:
                    # Indo existing OK → skip (tapi log untuk audit)
                    skip_actions.append((eid, key, value, indo_existing))
                    skip_count += 1
                    break
        else:
            # No match → ADD new entry
            add_actions.append((key, value))
            add_count += 1

    print('═══════════════════════════════════════════════════════════════')
    print('  📊 RINGKASAN MERGE')
    print('═══════════════════════════════════════════════════════════════')
    print(f'  ✅ FILL indo kosong (auto, NETRAL→paired):     {fill_count:5,}')
    print(f'  🔄 REPLACE candidate (word_leak, audit manual): {replace_candidates:5,}')
    print(f'  ⏭ SKIP indo existing (audit manual):          {skip_count:5,}')
    print(f'  ➕ ADD new entry (auto, dari milstrike):        {add_count:5,}')
    print(f'  ────────────────────────────────────────────────')
    print(f'  Total processed: {fill_count + replace_candidates + skip_count + add_count:,}')
    print()

    # Sample FILL
    print('── Sample FILL (auto-isi indo kosong) ──')
    for eid, key, value in fill_actions[:10]:
        entry = next(w for w in words if w.get('entry_id') == eid)
        print(f"  #{eid} word={entry.get('word','')[:20]!r} → indo={value!r}")
    if len(fill_actions) > 10:
        print(f'  ... +{len(fill_actions) - 10} more')
    print()

    # Sample REPLACE candidate
    print('── Sample REPLACE candidate (audit manual, milstrike lebih bersih) ──')
    for eid, key, value, existing in replace_actions[:15]:
        print(f"  #{eid} key={key!r}")
        print(f"    existing indo: {existing[:60]!r}")
        print(f"    milstrike    : {value[:60]!r}")
    if len(replace_actions) > 15:
        print(f'  ... +{len(replace_actions) - 15} more')
    print()

    # Sample ADD
    print('── Sample ADD new entry (dari milstrike) ──')
    for key, value in add_actions[:10]:
        print(f"  word={key!r} → indo={value!r}")
    if len(add_actions) > 10:
        print(f'  ... +{len(add_actions) - 10} more')
    print()

    # Dry-run check
    if not args.apply:
        print('🔍 DRY-RUN MODE — tidak ada perubahan.')
        print('   Untuk eksekusi: python3 merge-milstrike.py --apply')
        return

    # ===== APPLY =====
    print('═══════════════════════════════════════════════════════════════')
    print('  🚀 APPLY MERGE')
    print('═══════════════════════════════════════════════════════════════')

    # Backup kamus
    backup_path = kamus_path.with_suffix('.json.bak.' + datetime.datetime.now().strftime('%Y%m%d_%H%M%S'))
    save_json(backup_path, kamus)
    print(f'  ✅ Backup kamus: {backup_path}')

    # Apply FILL (auto-isi indo kosong)
    print(f'  Apply FILL ({fill_count} entries)...')
    filled = 0
    for eid, key, value in fill_actions:
        entry = next(w for w in words if w.get('entry_id') == eid)
        # Set indo, status='draft' (R-12 compliance)
        entry['indo'] = value
        entry['status'] = 'draft'
        # Tambah sumber milstrike kalau belum ada
        sumber = (entry.get('sumber') or '').strip()
        if 'milstrike' not in sumber:
            entry['sumber'] = (sumber + ' + milstrike').strip(' +') if sumber else 'milstrike'
        filled += 1
    print(f'  ✅ FILL done: {filled}')

    # Apply ADD (new entries)
    print(f'  Apply ADD ({add_count} new entries)...')
    max_eid = max((w.get('entry_id', 0) for w in words), default=0)
    added = 0
    for key, value in add_actions:
        max_eid += 1
        new_entry = {
            'entry_id': max_eid,
            'word': key,  # Key apa adanya (multi-token user bisa edit nanti)
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
        added += 1
    print(f'  ✅ ADD done: {added}')

    # Save kamus
    save_json(kamus_path, kamus)
    print(f'  ✅ Kamus saved: {kamus_path}')

    # Save report untuk REPLACE candidates (user audit manual)
    report_path = kamus_path.parent / 'merge-milstrike-report.txt'
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write('Merge Milstrike Report\n')
        f.write(f'Date: {datetime.datetime.now().isoformat()}\n')
        f.write(f'Milstrike: {milstrike_path}\n')
        f.write(f'Kamus:     {kamus_path}\n\n')
        f.write(f'FILL auto (indo kosong di-isi): {fill_count}\n')
        f.write(f'ADD new entry: {add_count}\n')
        f.write(f'REPLACE candidates (audit manual): {replace_candidates}\n')
        f.write(f'SKIP (indo existing OK): {skip_count}\n\n')
        f.write('═══════════════════════════════════════════════════════════════\n')
        f.write('REPLACE CANDIDATES — user audit manual di kamus-tui:\n')
        f.write('Pattern: existing indo = "word; definisi:" (label wiktionary mentah)\n')
        f.write('Action: ganti dengan milstrike value (lebih bersih)\n\n')
        for eid, key, value, existing in replace_actions:
            entry = next(w for w in words if w.get('entry_id') == eid)
            f.write(f'#{eid} word={entry.get("word","")!r}\n')
            f.write(f'  existing indo: {existing!r}\n')
            f.write(f'  milstrike    : {value!r}\n')
            f.write(f'  → Replace? Search entry #{eid} di kamus-tui, edit indo field\n\n')
        f.write('═══════════════════════════════════════════════════════════════\n')
        f.write('SKIP (indo existing OK, milstrike tidak lebih bersih) — 15 sample:\n')
        for eid, key, value, existing in skip_actions[:15]:
            entry = next(w for w in words if w.get('entry_id') == eid)
            f.write(f'#{eid} word={entry.get("word","")!r}\n')
            f.write(f'  existing indo: {existing!r}\n')
            f.write(f'  milstrike    : {value!r}\n\n')
    print(f'  📄 Report: {report_path}')

    print()
    print('═══════════════════════════════════════════════════════════════')
    print(f'  ✅ MERGE SELESAI')
    print(f'  FILL: {fill_count} | ADD: {add_count} | REPLACE candidates: {replace_candidates}')
    print(f'  Total kamus sekarang: {len(words):,} (sebelum: {len(words) - added:,})')
    print(f'  Backup: {backup_path}')
    print(f'  Report: {report_path}')
    print('═══════════════════════════════════════════════════════════════')
    print()
    print('Next:')
    print('  1. Buka kamus-tui.py → menu 🚩 Audit Flags → HIGH')
    print('     Word_leak_indo entries bisa di-replace pakai milstrike (lihat report)')
    print('  2. 735 entries NETRAL sekarang jadi word+indo (status=draft)')
    print('     Browse via menu "Filter: NETRAL" atau cari word+indo')
    print('  3. 675 entries baru dari milstrike — cek via Search "milstrike" di sumber')
    print('  4. Kalau salah, restore dari backup: ')


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print('\n\n⏹ Dibatalkan.')
        sys.exit(130)
