#!/usr/bin/env python3
"""
edit-kamus.py — Edit kamus Jawa lokal (JSON di VSCode), upload ke Supabase

Workflow:
  1. Import JSON lokal → Supabase (initial, 44.585 entri dari Wiktionary)
  2. Export Supabase → JSON lokal (kalau mau edit dari yang sudah ada)
  3. User edit JSON di VSCode (~/Dubbing/kamus-jawa.json)
  4. Import JSON lokal → Supabase (setelah edit, upload yang sudah lengkap)
  5. Kalau sudah lengkap → Supabase = ground of truth kamus

Format JSON (user edit di VSCode):
  {
    "metadata": { "version": "4.0", "entries": 44585 },
    "words": [
      {
        "ngoko": "aku, inyong, nyong",
        "aksara": "ꦲꦏꦸ",
        "krama": "kula, abdi, dalem",
        "id": "saya",
        "keterangan": "tetembung sesulih wong kang gunen",
        "sumber": "jv.wiktionary.org"
      }
    ]
  }

User flow:
  - JSON draft di ~/Dubbing/kamus-jawa.json (edit di VSCode, commit ke GitHub)
  - Kalau sudah lengkap → import ke Supabase (CSV export, ground of truth)

Install: pip3 install questionary
Usage: source venv/bin/activate && python3 edit-kamus.py
"""

import os
import sys
import json
import csv
import subprocess
from pathlib import Path

try:
    import questionary
except ImportError:
    print('\n❌ pip3 install questionary')
    sys.exit(1)

KAMUS_JSON = Path.home() / 'Dubbing' / 'kamus-jawa.json'
KAMUS_CSV = Path.home() / 'Dubbing' / 'kamus-jawa.csv'

SUPABASE_URL = os.environ.get('NEXT_PUBLIC_SUPABASE_URL', '')
SUPABASE_KEY = os.environ.get('NEXT_PUBLIC_SUPABASE_ANON_KEY', '')


def get_supabase_config():
    global SUPABASE_URL, SUPABASE_KEY
    if SUPABASE_URL and SUPABASE_KEY:
        return SUPABASE_URL, SUPABASE_KEY
    print('\n⚠ Supabase belum di-set.')
    print('   export NEXT_PUBLIC_SUPABASE_URL=https://xxx.supabase.co')
    print('   export NEXT_PUBLIC_SUPABASE_ANON_KEY=eyJxxx')
    print()
    url = input('Supabase URL (Enter untuk skip): ').strip()
    key = input('Supabase anon key (Enter untuk skip): ').strip()
    if url: SUPABASE_URL = url
    if key: SUPABASE_KEY = key
    return SUPABASE_URL, SUPABASE_KEY


def import_json_to_supabase():
    """Import JSON lokal → Supabase (bertahap, upsert bukan replace all)

    User edit 30 entri/hari di VSCode, import ke Supabase.
    Yang sudah ada di Supabase: update kalau berubah.
    Yang belum ada: insert baru.
    Yang belum diedit (krama/id kosong): skip (jangan overwrite yang sudah ada).
    """
    url, key = get_supabase_config()
    if not url or not key:
        print('❌ Supabase belum di-set.')
        return False

    json_path = questionary.text(
        'Path JSON (default: ~/Dubbing/kamus-jawa.json):',
        default=str(KAMUS_JSON),
    ).ask()
    if not json_path:
        json_path = KAMUS_JSON
    json_path = Path(os.path.expanduser(json_path))

    if not json_path.exists():
        print(f'❌ File tidak ada: {json_path}')
        return False

    print(f'\n=== Import {json_path.name} → Supabase (bertahap, upsert) ===')

    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    entries = data.get('words', [])
    print(f'  → {len(entries)} total entries di JSON')

    if len(entries) == 0:
        print('  ⚠ JSON kosong.')
        return False

    import urllib.request
    import urllib.parse
    headers = {
        'apikey': key,
        'Authorization': f'Bearer {key}',
        'Content-Type': 'application/json',
        'Prefer': 'resolution=merge-duplicates,return=minimal',  # upsert mode
    }

    # Filter: hanya entri yang SUDAH DIEDIT (krama ATAU id tidak kosong)
    # Entry yang krama+id kosong = belum diedit, skip (jangan overwrite Supabase)
    edited_entries = []
    skipped = 0
    for entry in entries:
        krama = (entry.get('krama') or '').strip()
        id_val = (entry.get('id') or '').strip()
        if krama or id_val:
            # Pastikan field lengkap
            edited_entries.append({
                'ngoko': entry.get('ngoko', ''),
                'aksara': entry.get('aksara', ''),
                'krama': krama,
                'arti': id_val,  # JSON field 'id' → Supabase kolom 'arti'
                'keterangan': entry.get('keterangan', ''),
                'sumber': entry.get('sumber', 'jv.wiktionary.org'),
                'status': 'clean',  # sudah diedit user = clean
            })
        else:
            skipped += 1

    if not edited_entries:
        print(f'  ⚠ Tidak ada entri yang sudah diedit (krama/id kosong semua).')
        print(f'     Edit dulu di VSCode: code {json_path}')
        print(f'     Isi krama + id, lalu import lagi.')
        return False

    print(f'  → {len(edited_entries)} entri sudah diedit (akan di-upsert)')
    print(f'  → {skipped} entri belum diedit (skip, jangan overwrite)')
    print(f'  → Status: clean (approved user)')
    print()

    # Upsert in batches (500 per batch)
    batch_size = 500
    success = 0
    failed = 0
    for i in range(0, len(edited_entries), batch_size):
        batch = edited_entries[i:i + batch_size]
        batch_json = json.dumps(batch)
        ins_url = f'{url}/rest/v1/kamus'
        ins_req = urllib.request.Request(
            ins_url,
            data=batch_json.encode('utf-8'),
            headers=headers,
            method='POST',
        )
        try:
            urllib.request.urlopen(ins_req)
            success += len(batch)
            print(f'  → Upserted {success}/{len(edited_entries)}...', end='\r')
        except Exception as e:
            failed += len(batch)
            if failed <= 3:
                print(f'\n  ⚠ Batch {i} failed: {e}')

    print(f'\n✅ Import bertahap selesai:')
    print(f'   Upserted: {success} entri (status: clean)')
    print(f'   Failed: {failed}')
    print(f'   Skipped: {skipped} (belum diedit, tidak di-upload)')
    print(f'   Supabase makin lengkap. Web app akan pakai yang clean.')
    return True


def export_supabase_to_json():
    """Export Supabase → JSON lokal (untuk edit di VSCode)"""
    url, key = get_supabase_config()
    if not url or not key:
        print('❌ Supabase belum di-set.')
        return False

    print(f'\n=== Export Supabase → {KAMUS_JSON} ===')

    import urllib.request
    headers = {'apikey': key, 'Authorization': f'Bearer {key}'}

    all_entries = []
    offset = 0
    limit = 1000

    while True:
        api_url = f'{url}/rest/v1/kamus?select=ngoko,aksara,krama,id,keterangan,sumber&order=ngoko&limit={limit}&offset={offset}'
        req = urllib.request.Request(api_url, headers=headers)
        try:
            with urllib.request.urlopen(req) as resp:
                data = json.loads(resp.read())
                if not data:
                    break
                all_entries.extend(data)
                print(f'  → Fetched {len(all_entries)} entries...', end='\r')
                if len(data) < limit:
                    break
                offset += limit
        except Exception as e:
            print(f'\n❌ Error: {e}')
            return False

    if not all_entries:
        print('  ⚠ Kamus kosong di Supabase.')
        return False

    # Write JSON
    output = {
        'metadata': {
            'version': '4.0',
            'source': 'Supabase export',
            'entries': len(all_entries),
            'note': 'Edit di VSCode, lalu import ke Supabase kalau sudah lengkap.',
        },
        'words': all_entries,
    }

    KAMUS_JSON.parent.mkdir(parents=True, exist_ok=True)
    with open(KAMUS_JSON, 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f'\n✅ Exported {len(all_entries)} entries → {KAMUS_JSON}')
    print(f'   Buka di VSCode: code {KAMUS_JSON}')
    print(f'   Edit krama + id per entri.')
    print(f'   Lalu: python3 edit-kamus.py → Import JSON → Supabase')
    return True


def export_supabase_to_csv():
    """Export Supabase → CSV (untuk backup atau import ke aplikasi lain)"""
    url, key = get_supabase_config()
    if not url or not key:
        print('❌ Supabase belum di-set.')
        return False

    print(f'\n=== Export Supabase → {KAMUS_CSV} (CSV) ===')

    import urllib.request
    headers = {'apikey': key, 'Authorization': f'Bearer {key}'}

    all_entries = []
    offset = 0
    limit = 1000

    while True:
        api_url = f'{url}/rest/v1/kamus?select=ngoko,aksara,krama,id,keterangan,sumber&order=ngoko&limit={limit}&offset={offset}'
        req = urllib.request.Request(api_url, headers=headers)
        try:
            with urllib.request.urlopen(req) as resp:
                data = json.loads(resp.read())
                if not data:
                    break
                all_entries.extend(data)
                print(f'  → Fetched {len(all_entries)} entries...', end='\r')
                if len(data) < limit:
                    break
                offset += limit
        except Exception as e:
            print(f'\n❌ Error: {e}')
            return False

    if not all_entries:
        print('  ⚠ Kamus kosong di Supabase.')
        return False

    KAMUS_CSV.parent.mkdir(parents=True, exist_ok=True)
    with open(KAMUS_CSV, 'w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=['ngoko', 'aksara', 'krama', 'id', 'keterangan', 'sumber'])
        writer.writeheader()
        for entry in all_entries:
            writer.writerow(entry)

    print(f'\n✅ Exported {len(all_entries)} entries → {KAMUS_CSV}')
    return True


def search_kamus():
    """Search kamus di Supabase"""
    url, key = get_supabase_config()
    if not url or not key:
        print('❌ Supabase belum di-set.')
        return

    query = questionary.text('Cari kata:').ask()
    if not query:
        return

    import urllib.request, urllib.parse
    encoded = urllib.parse.quote(f'%{query}%')
    api_url = f'{url}/rest/v1/kamus?select=ngoko,aksara,krama,id,keterangan,sumber&ngoko=ilike.{encoded}&limit=20'
    headers = {'apikey': key, 'Authorization': f'Bearer {key}'}
    req = urllib.request.Request(api_url, headers=headers)

    try:
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read())
    except Exception as e:
        print(f'❌ Error: {e}')
        return

    if not data:
        print(f'Tidak ada hasil untuk "{query}"')
        return

    print(f'\n=== {len(data)} hasil untuk "{query}" ===')
    for entry in data:
        ngoko = entry.get('ngoko', '')
        krama = entry.get('krama', '') or '(kosong)'
        id_val = entry.get('id', '') or '(kosong)'
        ket = entry.get('keterangan', '') or ''
        print(f'  {ngoko:20s} → krama: {krama:15s} | id: {id_val}')
        if ket:
            print(f'    keterangan: {ket[:80]}')


def open_in_vscode():
    """Buka kamus-jawa.json di VSCode"""
    if not KAMUS_JSON.exists():
        print(f'❌ {KAMUS_JSON} belum ada. Export dari Supabase dulu.')
        return
    print(f'  → Buka {KAMUS_JSON} di VSCode...')
    try:
        subprocess.run(['code', str(KAMUS_JSON)], check=False)
    except FileNotFoundError:
        print(f'  ⚠ VSCode "code" command tidak ditemukan.')
        print(f'     Buka manual: open {KAMUS_JSON}')


def main():
    print('╔' + '═' * 64 + '╗')
    print('║  📖 Kamus Jawa Editor (TUI)' + ' ' * 38 + '║')
    print('║  Edit JSON lokal (VSCode), upload ke Supabase' + ' ' * 22 + '║')
    print('╚' + '═' * 64 + '╝')
    print()
    print('  JSON draft: ~/Dubbing/kamus-jawa.json (edit di VSCode)')
    print('  Supabase: ground of truth (kalau sudah lengkap)')
    print()

    mode = questionary.select(
        'Mode:',
        choices=[
            'Import JSON lokal → Supabase (initial atau setelah edit)',
            'Export Supabase → JSON lokal (untuk edit di VSCode)',
            'Export Supabase → CSV (backup, kalau sudah lengkap)',
            'Search kamus di Supabase',
            'Buka kamus-jawa.json di VSCode',
            '❌ Keluar',
        ],
    ).ask()

    if 'Import JSON' in mode:
        import_json_to_supabase()
    elif 'Export Supabase → JSON' in mode:
        export_supabase_to_json()
    elif 'Export Supabase → CSV' in mode:
        export_supabase_to_csv()
    elif 'Search' in mode:
        search_kamus()
    elif 'VSCode' in mode:
        open_in_vscode()
    else:
        print('Keluar.')


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print('\n\n⏹ Dibatalkan.')
        sys.exit(130)
    except Exception as e:
        print(f'\n❌ Error: {e}', file=sys.stderr)
        sys.exit(1)
