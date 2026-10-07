#!/usr/bin/env python3
"""
edit-kamus.py — Edit kamus Jawa lokal (VSCode), upload ke Supabase

Workflow:
  1. Export: download kamus dari Supabase → kamus-jawa.csv (buka di VSCode)
  2. Edit: user edit krama + id di VSCode (CSV, mudah edit per baris)
  3. Import: upload kamus yang sudah diedit ke Supabase

Format CSV (bisa dibuka di VSCode, Excel, Google Sheets):
  ngoko,aksara,krama,id,keterangan,sumber,status
  aku,ꦲꦏꦸ,kula,saya,tetembung sesulih wong kang gunen,jv.wiktionary.org,clean
  arep,ꦲꦉꦥ꧀,,,"gelem (ngepèk, tuku lsp)",jv.wiktionary.org,draft

Install:
  pip3 install questionary supabase

Usage:
  source venv/bin/activate
  python3 edit-kamus.py
  (pilih mode: export / import / search)
"""

import os
import sys
import csv
import json
import subprocess
from pathlib import Path

try:
    import questionary
except ImportError:
    print('\n❌ pip3 install questionary')
    sys.exit(1)

KAMUS_FILE = Path.home() / 'Dubbing' / 'kamus-jawa.csv'

# Supabase config (dari env atau input user)
SUPABASE_URL = os.environ.get('NEXT_PUBLIC_SUPABASE_URL', '')
SUPABASE_KEY = os.environ.get('NEXT_PUBLIC_SUPABASE_ANON_KEY', '')


def get_supabase_config():
    global SUPABASE_URL, SUPABASE_KEY
    if SUPABASE_URL and SUPABASE_KEY:
        return SUPABASE_URL, SUPABASE_KEY
    print('\n⚠ Supabase belum di-set.')
    print('   Set env vars:')
    print('   export NEXT_PUBLIC_SUPABASE_URL=https://xxx.supabase.co')
    print('   export NEXT_PUBLIC_SUPABASE_ANON_KEY=eyJxxx')
    print()
    url = input('Supabase URL (Enter untuk skip): ').strip()
    key = input('Supabase anon key (Enter untuk skip): ').strip()
    if url: SUPABASE_URL = url
    if key: SUPABASE_KEY = key
    return SUPABASE_URL, SUPABASE_KEY


def export_from_supabase():
    """Download kamus dari Supabase → kamus-jawa.csv"""
    url, key = get_supabase_config()
    if not url or not key:
        print('❌ Supabase belum di-set. Skip export.')
        return False

    print(f'\n=== Export kamus dari Supabase → {KAMUS_FILE} ===')

    # Fetch all kamus entries (paginated)
    import urllib.request
    headers = {
        'apikey': key,
        'Authorization': f'Bearer {key}',
    }

    all_entries = []
    offset = 0
    limit = 1000

    while True:
        api_url = f'{url}/rest/v1/kamus?select=ngoko,aksara,krama,id,keterangan,sumber,status&order=ngoko&limit={limit}&offset={offset}'
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
            print(f'\n❌ Error fetching: {e}')
            return False

    if not all_entries:
        print('  ⚠ Kamus kosong di Supabase. Mungkin belum di-import.')
        print('  Jalankan: python3 edit-kamus.py → pilih "Import dari JSON lokal"')
        return False

    # Write CSV
    KAMUS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(KAMUS_FILE, 'w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=['ngoko', 'aksara', 'krama', 'id', 'keterangan', 'sumber', 'status'])
        writer.writeheader()
        for entry in all_entries:
            writer.writerow({
                'ngoko': entry.get('ngoko', ''),
                'aksara': entry.get('aksara', ''),
                'krama': entry.get('krama', ''),
                'id': entry.get('id', ''),
                'keterangan': entry.get('keterangan', ''),
                'sumber': entry.get('sumber', ''),
                'status': entry.get('status', 'draft'),
            })

    print(f'\n✅ Exported {len(all_entries)} entries → {KAMUS_FILE}')
    print(f'   Buka di VSCode: code {KAMUS_FILE}')
    print(f'   Edit kolom krama + id, save.')
    print(f'   Lalu jalankan: python3 edit-kamus.py → Import ke Supabase')
    return True


def import_to_supabase():
    """Upload kamus-jawa.csv → Supabase"""
    url, key = get_supabase_config()
    if not url or not key:
        print('❌ Supabase belum di-set. Skip import.')
        return False

    if not KAMUS_FILE.exists():
        print(f'❌ File tidak ada: {KAMUS_FILE}')
        print(f'   Jalankan export dulu: python3 edit-kamus.py → Export dari Supabase')
        return False

    print(f'\n=== Import {KAMUS_FILE} → Supabase ===')

    # Read CSV
    entries = []
    with open(KAMUS_FILE, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            entries.append({
                'ngoko': row.get('ngoko', ''),
                'aksara': row.get('aksara', ''),
                'krama': row.get('krama', ''),
                'id': row.get('id', ''),
                'keterangan': row.get('keterangan', ''),
                'sumber': row.get('sumber', 'jv.wiktionary.org'),
                'status': row.get('status', 'draft'),
            })

    print(f'  → {len(entries)} entries dari CSV')

    # Delete existing + insert (replace all)
    import urllib.request
    headers = {
        'apikey': key,
        'Authorization': f'Bearer {key}',
        'Content-Type': 'application/json',
    }

    # Delete all existing
    print('  → Hapus kamus lama...')
    del_url = f'{url}/rest/v1/kamus?neq=ngoko'
    del_req = urllib.request.Request(del_url, method='DELETE', headers=headers)
    try:
        urllib.request.urlopen(del_req)
    except Exception as e:
        print(f'  ⚠ Delete warning: {e}')

    # Insert in batches (500 per batch)
    batch_size = 500
    success = 0
    failed = 0
    for i in range(0, len(entries), batch_size):
        batch = entries[i:i + batch_size]
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
            print(f'  → Imported {success}/{len(entries)}...', end='\r')
        except Exception as e:
            failed += len(batch)
            print(f'\n  ⚠ Batch {i} failed: {e}')

    print(f'\n✅ Import selesai: {success} sukses, {failed} gagal')
    return True


def import_from_json():
    """Import kamus-jawa-full.json lokal → Supabase (initial import 44.585 entri)"""
    url, key = get_supabase_config()
    if not url or not key:
        print('❌ Supabase belum di-set. Skip import.')
        return False

    json_path = Path.home() / 'Dubbing' / 'kamus-jawa-full.json'
    if not json_path.exists():
        # Cari di project folder
        json_path = Path('/home/z/my-project/public/kamus-jawa-full.json')
    if not json_path.exists():
        print(f'❌ File tidak ada: kamus-jawa-full.json')
        print(f'   Download dari: curl -L -o ~/Dubbing/kamus-jawa-full.json')
        print(f'   https://raw.githubusercontent.com/emailnyamahmud-afk/srt-splitter/main/public/kamus-jawa-full.json')
        return False

    print(f'\n=== Import {json_path.name} → Supabase (initial) ===')

    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    entries = data.get('words', [])
    print(f'  → {len(entries)} entries dari JSON')

    import urllib.request
    headers = {
        'apikey': key,
        'Authorization': f'Bearer {key}',
        'Content-Type': 'application/json',
    }

    # Insert in batches
    batch_size = 500
    success = 0
    failed = 0
    for i in range(0, len(entries), batch_size):
        batch = entries[i:i + batch_size]
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
            print(f'  → Imported {success}/{len(entries)} ({100*success//len(entries)}%)...', end='\r')
        except Exception as e:
            failed += len(batch)
            if failed <= 3:
                print(f'\n  ⚠ Batch {i} failed: {e}')

    print(f'\n✅ Import selesai: {success} sukses, {failed} gagal')
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
    api_url = f'{url}/rest/v1/kamus?select=ngoko,aksara,krama,id,keterangan,status&ngoko=ilike.{encoded}&limit=20'
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
        status = entry.get('status', 'draft')
        print(f'  {ngoko:20s} → {krama:15s} | id: {id_val:20s} | {status}')
        if ket:
            print(f'    keterangan: {ket[:80]}')


def main():
    print('╔' + '═' * 64 + '╗')
    print('║  📖 Kamus Jawa Editor (TUI)' + ' ' * 38 + '║')
    print('║  Edit lokal (VSCode), upload ke Supabase' + ' ' * 26 + '║')
    print('╚' + '═' * 64 + '╝')
    print()

    mode = questionary.select(
        'Mode:',
        choices=[
            'Export dari Supabase → CSV lokal (buka di VSCode)',
            'Import CSV lokal → Supabase (setelah edit)',
            'Import dari JSON lokal → Supabase (initial 44.585 entri)',
            'Search kamus di Supabase',
            '❌ Keluar',
        ],
    ).ask()

    if 'Export' in mode:
        export_from_supabase()
    elif 'Import CSV' in mode:
        import_to_supabase()
    elif 'Import dari JSON' in mode:
        import_from_json()
    elif 'Search' in mode:
        search_kamus()
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
