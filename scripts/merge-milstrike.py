#!/usr/bin/env python3
"""
merge-milstrike.py v2 — Merge kamus milstrike_jv_id.json ke kamus_unified_draft.json

User requirement: "jika ada kata di milstrike = auto masuk ke ngoko-indo-krama,
jika kata sama = replace, jika kata beda tapi sama arti = sinonim = ditulis dengan koma."

Source milstrike_jv_id.json (1.836 entries, format {kata_jawa: indo_translation}):
  - Quality SANGAT BERSIH — terjemahan singkat 1-3 kata, bukan definisi panjang
  - Cross-reference lebih pintar dari AI parsing mentah

Strategy v2 (cross-reference per field):
  1. Build index per FIELD: word, ngoko, krama, indo (lowercase token)
  2. Untuk tiap milstrike (key, value):
     a. Tokenize key (split ',' dan ';')
     b. Match token di field word/ngoko/krama
     c. Action per match:
        - Match + indo KOSONG → FILL indo dengan milstrike value
        - Match + indo terisi + WORD_LEAK pattern (indo='word;definisi:')
          → REPLACE indo (milstrike lebih bersih)
        - Match + indo terisi OK → SKIP
     d. No match di word/ngoko/krama:
        - Cek value match di indo index (exact, lowercase)
          - Match → SINONIM: tambah key milstrike ke word field entry existing dengan koma
          - No match → ADD new entry

  3. Sinonim logic:
     - Key milstrike BEDA dari word/ngoko/krama existing
     - Tapi indo value SAMA dengan indo entry existing
     - → Key milstrike adalah variasi/spelling alternatif (sinonim lemma)
     - → Tambah ke word field entry existing dengan koma (R-21: word=NETRAL aman)
     - → Cek duplikat: kalau key sudah ada di word, skip

Safety:
  - Backup kamus ke .bak.<timestamp> sebelum merge
  - Auto-REPLACE hanya untuk word_leak pattern (label wiktionary mentah)
  - Tidak auto-replace indo yang sudah OK
  - R-12 compliance: status='draft' setelah merge
  - Dry-run mode default (--apply untuk eksekusi)

Usage:
  python3 merge-milstrike.py                    # dry-run, print report
  python3 merge-milstrike.py --apply            # eksekusi merge
  python3 merge-milstrike.py --milstrike path
  python3 merge-milstrike.py --kamus path
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
    """Tokenize key milstrike (sinonim: 'awakmu, sampean, koe' = kamu).
    Pisah by ',' dan ';'.
    """
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
    return [t.strip().lower() for t in value.split(',') if t.strip() and len(t.strip()) > 1]


def build_field_index(words):
    """Build index per field (lowercase token → list of entry_id).

    Index: word, ngoko, krama, indo — supaya bisa cross-reference per field.
    """
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
    """Cek apakah existing indo = 'word; definisi:' (label wiktionary mentah).
    Kalau iya, milstrike_value bisa replace jadi lebih bersih.
    """
    word = (entry.get('word') or '').strip().lower()
    indo = (entry.get('indo') or '').strip()
    if not word or not indo:
        return False
    indo_first = indo.split(';')[0].strip().lower()
    return indo_first == word and (';' in indo or ':' in indo)


def add_sinonim_to_word(entry, new_token):
    """Tambah new_token ke field word entry dengan koma (sinonim lemma).
    Cek duplikat dulu. Return True kalau ditambah.
    """
    word = (entry.get('word') or '').strip()
    existing_tokens = [t.strip().lower() for t in word.split(',') if t.strip()]
    if new_token.lower() in existing_tokens:
        return False  # Sudah ada, skip
    new_word = f'{word}, {new_token}' if word else new_token
    entry['word'] = new_word
    return True


def main():
    parser = argparse.ArgumentParser(description='Merge milstrike_jv_id.json ke kamus')
    parser.add_argument('--apply', action='store_true',
                        help='Eksekusi merge (default: dry-run)')
    parser.add_argument('--milstrike', default=None,
                        help='Path ke milstrike_jv_id.json')
    parser.add_argument('--kamus', default=None,
                        help='Path ke kamus_unified_draft.json')
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

    print('Bangun index per field (word, ngoko, krama, indo)...')
    idx = build_field_index(words)
    for f in ['word', 'ngoko', 'krama', 'indo']:
        print(f'  {f:6}: {len(idx[f]):,} token unik')
    print()

    # Action tracking
    fill_count = 0
    replace_count = 0  # auto-replace word_leak
    skip_count = 0
    sinonim_count = 0  # key beda + indo sama → tambah ke word
    add_count = 0

    fill_actions = []
    replace_actions = []
    skip_actions = []
    sinonim_actions = []
    add_actions = []

    # Build lookup: entry_id → entry (speed up)
    eid_to_entry = {w.get('entry_id'): w for w in words}

    for key, value in ms.items():
        value = (value or '').strip()
        if not value:
            continue
        key_tokens = tokenize_key(key)

        # Phase 1: Match di word/ngoko/krama (case insensitive)
        matched_entries = {}  # eid → set of fields yg match
        for tok in key_tokens:
            tl = tok.lower()
            for field in ['word', 'ngoko', 'krama']:
                if tl in idx[field]:
                    for eid in idx[field][tl]:
                        matched_entries.setdefault(eid, set())
                        matched_entries[eid].add(field)

        if matched_entries:
            # Sort by entry_id (ambil pertama untuk action)
            sorted_eids = sorted(matched_entries.keys())
            action_done = False
            for eid in sorted_eids:
                entry = eid_to_entry.get(eid)
                if not entry:
                    continue
                indo_existing = (entry.get('indo') or '').strip()
                if not indo_existing:
                    # Indo KOSONG → FILL
                    fill_actions.append((eid, key, value))
                    fill_count += 1
                    action_done = True
                    break
                elif is_word_leak_indo(entry, value):
                    # Indo existing = label wiktionary → REPLACE
                    replace_actions.append((eid, key, value, indo_existing))
                    replace_count += 1
                    action_done = True
                    break
                else:
                    # Indo existing OK → SKIP (log untuk audit)
                    skip_actions.append((eid, key, value, indo_existing))
                    skip_count += 1
                    action_done = True
                    break
            if action_done:
                continue

        # Phase 2: No match di word/ngoko/krama → cek SINONIM by indo
        value_lower = value.lower()
        if value_lower in idx['indo']:
            # Indo match → SINONIM candidate
            # Cari entry existing dengan indo SAMA, tambah key milstrike ke word
            for eid in idx['indo'][value_lower]:
                entry = eid_to_entry.get(eid)
                if not entry:
                    continue
                # Tambah key milstrike ke word (sinonim lemma)
                # Ambil token pertama dari key (kalau multi-token, user bisa edit nanti)
                primary_key = key_tokens[0]
                added = add_sinonim_to_word(entry, primary_key)
                if added:
                    sinonim_actions.append((eid, key, value, entry.get('word', '')))
                    sinonim_count += 1
                else:
                    # Sudah ada di word → skip
                    skip_actions.append((eid, key, value, '(sudah ada di word)'))
                    skip_count += 1
                action_done = True
                break
            if action_done:
                continue

        # Phase 3: No match sama sekali → ADD new entry
        add_actions.append((key, value))
        add_count += 1

    print('═══════════════════════════════════════════════════════════════')
    print('  📊 RINGKASAN MERGE v2 (cross-reference per field)')
    print('═══════════════════════════════════════════════════════════════')
    print(f'  ✅ FILL indo kosong (auto):                    {fill_count:5,}')
    print(f'  🔄 REPLACE word_leak pattern (auto, milstrike lebih bersih): {replace_count:5,}')
    print(f'  🔗 SINONIM (key beda, indo sama → tambah ke word): {sinonim_count:5,}')
    print(f'  ⏭ SKIP indo existing OK (audit manual optional): {skip_count:5,}')
    print(f'  ➕ ADD new entry (no match sama sekali):        {add_count:5,}')
    print(f'  ────────────────────────────────────────────────')
    print(f'  Total processed: {fill_count + replace_count + sinonim_count + skip_count + add_count:,}')
    print()

    # Sample FILL
    print('── Sample FILL (auto-isi indo kosong) ──')
    for eid, key, value in fill_actions[:8]:
        entry = eid_to_entry.get(eid, {})
        print(f"  #{eid} word={entry.get('word','')[:20]!r} ngoko={entry.get('ngoko','')[:15]!r} krama={entry.get('krama','')[:15]!r} → indo={value!r}")
    if len(fill_actions) > 8:
        print(f'  ... +{len(fill_actions) - 8} more')
    print()

    # Sample REPLACE
    print('── Sample REPLACE (auto-replace word_leak pattern) ──')
    for eid, key, value, existing in replace_actions[:10]:
        print(f"  #{eid} key={key!r}")
        print(f"    existing indo: {existing[:60]!r}")
        print(f"    milstrike    : {value[:60]!r}")
    if len(replace_actions) > 10:
        print(f'  ... +{len(replace_actions) - 10} more')
    print()

    # Sample SINONIM
    print('── Sample SINONIM (key beda + indo sama → tambah ke word) ──')
    for eid, key, value, new_word in sinonim_actions[:10]:
        print(f"  #{eid} milstrike[{key!r}={value!r}]")
        print(f"    word baru: {new_word[:80]!r}")
    if len(sinonim_actions) > 10:
        print(f'  ... +{len(sinonim_actions) - 10} more')
    print()

    # Sample ADD
    print('── Sample ADD new entry (no match sama sekali) ──')
    for key, value in add_actions[:8]:
        print(f"  word={key!r} → indo={value!r}")
    if len(add_actions) > 8:
        print(f'  ... +{len(add_actions) - 8} more')
    print()

    if not args.apply:
        print('🔍 DRY-RUN MODE — tidak ada perubahan.')
        print('   Untuk eksekusi: python3 merge-milstrike.py --apply')
        return

    # ===== APPLY =====
    print('═══════════════════════════════════════════════════════════════')
    print('  🚀 APPLY MERGE')
    print('═══════════════════════════════════════════════════════════════')

    # Backup
    backup_path = kamus_path.with_suffix('.json.bak.' + datetime.datetime.now().strftime('%Y%m%d_%H%M%S'))
    save_json(backup_path, kamus)
    print(f'  ✅ Backup kamus: {backup_path}')

    # Apply FILL
    print(f'  Apply FILL ({fill_count} entries)...')
    for eid, key, value in fill_actions:
        entry = eid_to_entry.get(eid)
        if not entry:
            continue
        entry['indo'] = value
        entry['status'] = 'draft'
        sumber = (entry.get('sumber') or '').strip()
        if 'milstrike' not in sumber:
            entry['sumber'] = (sumber + ' + milstrike').strip(' +') if sumber else 'milstrike'
    print(f'  ✅ FILL done')

    # Apply REPLACE (auto word_leak)
    print(f'  Apply REPLACE ({replace_count} entries, word_leak → milstrike)...')
    for eid, key, value, existing in replace_actions:
        entry = eid_to_entry.get(eid)
        if not entry:
            continue
        entry['indo'] = value
        entry['status'] = 'draft'
        sumber = (entry.get('sumber') or '').strip()
        if 'milstrike' not in sumber:
            entry['sumber'] = (sumber + ' + milstrike').strip(' +') if sumber else 'milstrike'
    print(f'  ✅ REPLACE done')

    # Apply SINONIM (tambah key ke word field existing)
    print(f'  Apply SINONIM ({sinonim_count} entries)...')
    # Re-run add_sinonim karena sebelumnya dry-run sudah modify entry in-memory
    for eid, key, value, _ in sinonim_actions:
        entry = eid_to_entry.get(eid)
        if not entry:
            continue
        # Tambah sumber milstrike
        sumber = (entry.get('sumber') or '').strip()
        if 'milstrike' not in sumber:
            entry['sumber'] = (sumber + ' + milstrike').strip(' +') if sumber else 'milstrike'
        # word sudah di-modify di phase 2 (dry-run) — tapi karena tidak save, harus apply lagi
        primary_key = tokenize_key(key)[0]
        add_sinonim_to_word(entry, primary_key)
        entry['status'] = 'draft'
    print(f'  ✅ SINONIM done')

    # Apply ADD (new entries)
    print(f'  Apply ADD ({add_count} new entries)...')
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
    print(f'  ✅ ADD done')

    # Save
    save_json(kamus_path, kamus)
    print(f'  ✅ Kamus saved: {kamus_path}')

    # Report
    report_path = kamus_path.parent / 'merge-milstrike-report.txt'
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write('Merge Milstrike Report v2 (cross-reference per field)\n')
        f.write(f'Date: {datetime.datetime.now().isoformat()}\n')
        f.write(f'Milstrike: {milstrike_path}\n')
        f.write(f'Kamus:     {kamus_path}\n\n')
        f.write(f'FILL auto (indo kosong di-isi): {fill_count}\n')
        f.write(f'REPLACE auto (word_leak pattern, milstrike lebih bersih): {replace_count}\n')
        f.write(f'SINONIM (key beda + indo sama → tambah ke word): {sinonim_count}\n')
        f.write(f'SKIP (indo existing OK): {skip_count}\n')
        f.write(f'ADD new entry: {add_count}\n\n')
        f.write('═══════════════════════════════════════════════════════════════\n')
        f.write('SKIP entries (indo existing OK, audit manual optional) — 15 sample:\n')
        for eid, key, value, existing in skip_actions[:15]:
            entry = eid_to_entry.get(eid, {})
            f.write(f'#{eid} word={entry.get("word","")!r} ngoko={entry.get("ngoko","")!r} krama={entry.get("krama","")!r}\n')
            f.write(f'  existing indo: {existing!r}\n')
            f.write(f'  milstrike    : {value!r}\n\n')
    print(f'  📄 Report: {report_path}')

    print()
    print('═══════════════════════════════════════════════════════════════')
    print(f'  ✅ MERGE SELESAI')
    print(f'  FILL: {fill_count} | REPLACE: {replace_count} | SINONIM: {sinonim_count} | ADD: {add_count}')
    print(f'  Total kamus: {len(words):,} (sebelum: {len(words) - add_count:,})')
    print(f'  Backup: {backup_path}')
    print(f'  Report: {report_path}')
    print('═══════════════════════════════════════════════════════════════')


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print('\n\n⏹ Dibatalkan.')
        sys.exit(130)
