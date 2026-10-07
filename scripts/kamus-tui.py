#!/usr/bin/env python3
"""
kamus-tui.py — TUI edit kamus Jawa (interactive, arrow keys)

User flow:
  1. Buka kamus-jawa.json (lokal, 44.585 entri)
  2. Search / browse → pilih entri → edit krama + id
  3. Save (update JSON lokal)
  4. Upload ke Supabase (bertahap, hanya yang sudah diedit)

Install: pip3 install questionary
Usage: source venv/bin/activate && python3 kamus-tui.py
"""

import os
import sys
import json
from pathlib import Path

try:
    import questionary
except ImportError:
    print('\n❌ pip3 install questionary')
    sys.exit(1)

KAMUS_JSON = Path.home() / 'Dubbing' / 'kamus-jawa.json'
SUPABASE_URL = os.environ.get('NEXT_PUBLIC_SUPABASE_URL', '')
SUPABASE_KEY = os.environ.get('NEXT_PUBLIC_SUPABASE_ANON_KEY', '')


def load_kamus():
    if not KAMUS_JSON.exists():
        print(f'❌ {KAMUS_JSON} tidak ada.')
        print(f'   Download: curl -L -o ~/Dubbing/kamus-jawa.json')
        print(f'   https://raw.githubusercontent.com/emailnyamahmud-afk/srt-splitter/b7423eb/public/kamus-jawa-full.json')
        return None
    with open(KAMUS_JSON, 'r', encoding='utf-8') as f:
        return json.load(f)


def save_kamus(data):
    with open(KAMUS_JSON, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def upload_to_supabase(edited_count):
    if not SUPABASE_URL or not SUPABASE_KEY:
        print('\n  ⚠ Supabase belum di-set. Skip upload.')
        print('   export NEXT_PUBLIC_SUPABASE_URL=...')
        print('   export NEXT_PUBLIC_SUPABASE_ANON_KEY=...')
        return False

    if edited_count == 0:
        print('\n  ⚠ Tidak ada entri yang diedit. Skip upload.')
        return False

    print(f'\n  → Upload {edited_count} entri ke Supabase...')

    import urllib.request
    # Load JSON lagi, filter yang sudah diedit
    with open(KAMUS_JSON, 'r', encoding='utf-8') as f:
        data = json.load(f)

    edited = []
    for entry in data['words']:
        krama = (entry.get('krama') or '').strip()
        id_val = (entry.get('id') or '').strip()
        if krama or id_val:
            edited.append({
                'ngoko': entry.get('ngoko', ''),
                'aksara': entry.get('aksara', ''),
                'krama': krama,
                'id': id_val,
                'keterangan': entry.get('keterangan', ''),
                'sumber': entry.get('sumber', 'jv.wiktionary.org'),
                'status': 'clean',
            })

    if not edited:
        print('  ⚠ Tidak ada entri clean. Skip.')
        return False

    headers = {
        'apikey': SUPABASE_KEY,
        'Authorization': f'Bearer {SUPABASE_KEY}',
        'Content-Type': 'application/json',
        'Prefer': 'resolution=merge-duplicates,return=minimal',
    }

    batch_size = 500
    success = 0
    failed = 0
    for i in range(0, len(edited), batch_size):
        batch = edited[i:i + batch_size]
        batch_json = json.dumps(batch)
        ins_url = f'{SUPABASE_URL}/rest/v1/kamus'
        ins_req = urllib.request.Request(
            ins_url,
            data=batch_json.encode('utf-8'),
            headers=headers,
            method='POST',
        )
        try:
            urllib.request.urlopen(ins_req)
            success += len(batch)
            print(f'  → {success}/{len(edited)}...', end='\r')
        except Exception as e:
            failed += len(batch)
            if failed <= 3:
                print(f'\n  ⚠ Batch failed: {e}')

    print(f'\n  ✅ Upload: {success} sukses, {failed} gagal')
    return True


def browse_kamus(data):
    words = data['words']
    total = len(words)
    page_size = 20
    current_page = 0
    edited_count = 0

    while True:
        start = current_page * page_size
        end = min(start + page_size, total)
        page_entries = words[start:end]

        os.system('clear' if os.name != 'nt' else 'cls')
        print('╔' + '═' * 64 + '╗')
        print('║  📖 Kamus Jawa — Browse & Edit' + ' ' * 36 + '║')
        print(f'║  {total} entri | Halaman {current_page + 1}/{(total + page_size - 1) // page_size} | Edited: {edited_count}' + ' ' * max(0, 12 - len(str(edited_count))) + '║')
        print('╚' + '═' * 64 + '╝')
        print()

        # Build choices
        choices = []
        for i, entry in enumerate(page_entries):
            idx = start + i
            ngoko = entry.get('ngoko', '')[:25]
            krama = entry.get('krama', '') or ''
            id_val = entry.get('id', '') or ''
            ket = entry.get('keterangan', '')[:40]

            if krama or id_val:
                status = '✓'
            else:
                status = '○'

            label = f'{status} {idx + 1:5d}. {ngoko:25s} → {krama:15s} | {id_val:15s}'
            if not krama and not id_val and ket:
                label += f'  [{ket}]'

            choices.append(label)

        # Navigation
        nav = []
        if current_page > 0:
            nav.append('◀ Halaman sebelumnya')
        if end < total:
            nav.append('▶ Halaman berikutnya')
        nav.append('🔍 Search')
        nav.append('☁  Upload ke Supabase')
        nav.append('❌ Keluar')

        choices.extend(nav)

        selected = questionary.select(
            'Pilih entri (✓=sudah diedit, ○=belum):',
            choices=choices,
            default=choices[0],
        ).ask()

        if not selected or 'Keluar' in selected:
            break

        if 'sebelumnya' in selected:
            current_page -= 1
            continue

        if 'berikutnya' in selected:
            current_page += 1
            continue

        if 'Search' in selected:
            search_query = questionary.text('Cari kata:').ask()
            if search_query:
                search_kamus(data, search_query.strip(), edited_count)
            continue

        if 'Upload' in selected:
            upload_to_supabase(edited_count)
            continue

        # Edit entri yang dipilih
        match_idx = None
        for i, label in enumerate(choices[:len(page_entries)]):
            if selected == label:
                match_idx = start + i
                break

        if match_idx is not None:
            entry = words[match_idx]
            ngoko = entry.get('ngoko', '')
            aksara = entry.get('aksara', '')
            krama_old = entry.get('krama', '')
            id_old = entry.get('id', '')
            ket = entry.get('keterangan', '')

            print(f'\n  ┌─────────────────────────────────────────┐')
            print(f'  │ ngoko:      {ngoko[:37]}')
            print(f'  │ aksara:     {aksara[:37]}')
            print(f'  │ krama:      {krama_old[:37] or "(kosong)"}')
            print(f'  │ id:         {id_old[:37] or "(kosong)"}')
            print(f'  │ keterangan: {ket[:37]}')
            print(f'  └─────────────────────────────────────────┘')

            new_krama = questionary.text('Krama (Enter=skip):', default=krama_old).ask()
            if new_krama is not None:
                new_krama = new_krama.strip()
            new_id = questionary.text('Id/Indonesia (Enter=skip):', default=id_old).ask()
            if new_id is not None:
                new_id = new_id.strip()

            if new_krama != krama_old or new_id != id_old:
                entry['krama'] = new_krama
                entry['id'] = new_id
                save_kamus(data)
                edited_count += 1
                print(f'\n  ✅ Disimpan: {ngoko} → krama={new_krama}, id={new_id}')
            else:
                print('\n  (tidak ada perubahan)')

            input('\n  Tekan Enter untuk kembali...')


def search_kamus(data, query, edited_count):
    words = data['words']
    query_lower = query.lower()

    matches = []
    for i, entry in enumerate(words):
        ngoko = entry.get('ngoko', '').lower()
        if query_lower in ngoko:
            matches.append((i, entry))

    if not matches:
        print(f'\n  Tidak ada hasil untuk "{query}"')
        input('\n  Tekan Enter untuk kembali...')
        return

    # Show results
    os.system('clear' if os.name != 'nt' else 'cls')
    print(f'🔍 Hasil pencarian "{query}": {len(matches)} entri')
    print()

    choices = []
    for idx, entry in matches[:50]:  # max 50 results
        ngoko = entry.get('ngoko', '')[:25]
        krama = entry.get('krama', '') or ''
        id_val = entry.get('id', '') or ''
        ket = entry.get('keterangan', '')[:40]

        status = '✓' if (krama or id_val) else '○'
        label = f'{status} {idx + 1:5d}. {ngoko:25s} → {krama:15s} | {id_val:15s}'
        if not krama and not id_val and ket:
            label += f'  [{ket}]'
        choices.append(label)

    choices.append('❌ Kembali')

    selected = questionary.select(
        'Pilih entri untuk edit:',
        choices=choices,
        default=choices[0],
    ).ask()

    if not selected or 'Kembali' in selected:
        return

    # Find which entry
    for match in matches[:50]:
        match_idx = match[0]
        entry = match[1]
        ngoko = entry.get('ngoko', '')[:25]
        krama = entry.get('krama', '') or ''
        id_val = entry.get('id', '') or ''
        ket = entry.get('keterangan', '')[:40]
        label = f'{"✓" if (krama or id_val) else "○"} {match_idx + 1:5d}. {ngoko:25s} → {krama:15s} | {id_val:15s}'
        if not krama and not id_val and ket:
            label += f'  [{ket}]'
        if selected == label:
            # Edit
            krama_old = entry.get('krama', '')
            id_old = entry.get('id', '')

            print(f'\n  ┌─────────────────────────────────────────┐')
            print(f'  │ ngoko:      {entry.get("ngoko", "")[:37]}')
            print(f'  │ aksara:     {entry.get("aksara", "")[:37]}')
            print(f'  │ krama:      {krama_old[:37] or "(kosong)"}')
            print(f'  │ id:         {id_old[:37] or "(kosong)"}')
            print(f'  │ keterangan: {entry.get("keterangan", "")[:37]}')
            print(f'  └─────────────────────────────────────────┘')

            new_krama = questionary.text('Krama (Enter=skip):', default=krama_old).ask()
            if new_krama is not None:
                new_krama = new_krama.strip()
            new_id = questionary.text('Id/Indonesia (Enter=skip):', default=id_old).ask()
            if new_id is not None:
                new_id = new_id.strip()

            if new_krama != krama_old or new_id != id_old:
                entry['krama'] = new_krama
                entry['id'] = new_id
                save_kamus(data)
                print(f'\n  ✅ Disimpan: {entry.get("ngoko", "")} → krama={new_krama}, id={new_id}')
            else:
                print('\n  (tidak ada perubahan)')

            input('\n  Tekan Enter untuk kembali...')
            break


def main():
    os.system('clear' if os.name != 'nt' else 'cls')
    print('╔' + '═' * 64 + '╗')
    print('║  📖 Kamus Jawa Editor (TUI)' + ' ' * 38 + '║')
    print('║  Browse → edit krama + id → upload Supabase' + ' ' * 24 + '║')
    print('╚' + '═' * 64 + '╝')
    print()

    data = load_kamus()
    if not data:
        sys.exit(1)

    total = len(data['words'])
    edited = sum(1 for w in data['words'] if (w.get('krama') or '').strip() or (w.get('id') or '').strip())

    print(f'  Kamus: {KAMUS_JSON}')
    print(f'  Total: {total} entri')
    print(f'  Sudah diedit: {edited} ({100 * edited // total}%)')
    print(f'  Belum diedit: {total - edited}')
    print()

    browse_kamus(data)

    print('\nSelesai.')


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print('\n\n⏹ Dibatalkan.')
        sys.exit(130)
    except Exception as e:
        print(f'\n❌ Error: {e}', file=sys.stderr)
        sys.exit(1)
