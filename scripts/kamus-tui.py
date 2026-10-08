#!/usr/bin/env python3
"""
kamus-tui.py v2 — TUI edit kamus Jawa dengan menu pre-built (arrow keys, no jq needed)

User tinggal tab/panah, pilih menu:
  📊 Statistik kamus
  🔍 Search (cari kata)
  📋 Browse semua (pagination)
  ⭐ Browse entri dengan krama mapping (auto-filled)
  📝 Browse entri yang BELUM ada arti
  🎯 Browse per register (ngoko / krama / krama_inggil / kawi / umum)
  ☁  Upload ke Supabase (hanya yang sudah diedit user)
  ❌ Keluar

Edit per entri: ngoko, krama, krama_inggil, arti (Indonesia)
  - keterangan JAWA read-only (JANGAN HAPUS)
  - register read-only (info dari Wiktionary)

Status tracking:
  status='draft' = belum di-edit user (hanya auto-filled dari template)
  status='clean' = sudah di-edit user (arti diisi, atau krama_inggil ditambah)

Edit per entri: ngoko, krama, krama_inggil, arti (Indonesia), register
  - keterangan JAWA read-only (JANGAN HAPUS)
  - register BISA di-edit (dropdown: ngoko/krama/krama_inggil/kawi/umum)

Merge: menu khusus, search kata 1 → search kata 2 → preview → konfirmasi
Upload: HANYA entries dengan ngoko+krama+arti lengkap (3 field wajib)

Install: pip3 install questionary
Usage: python3 kamus-tui.py
"""

import os
import sys
import json
import subprocess
import tempfile
from pathlib import Path

try:
    import questionary
except ImportError:
    print('\n❌ pip3 install questionary')
    sys.exit(1)

# Kamus JSON path — hanya kamus-jawa-full.json (v5, 44.585 entri)
KAMUS_FULL = Path.home() / 'Dubbing' / 'kamus-jawa-full.json'

# .env file di ~/Dubbing/ — user simpan Supabase URL + anon key di sini
# Format .env:
#   NEXT_PUBLIC_SUPABASE_URL=https://xxx.supabase.co
#   NEXT_PUBLIC_SUPABASE_ANON_KEY=eyJxxx...
ENV_FILE = Path.home() / 'Dubbing' / '.env'


def load_env_file():
    """Load .env file dari ~/Dubbing/.env (kalau ada).
    Supaya user tidak perlu set env vars manual tiap kali update kamus-tui.py.
    Format .env:
      NEXT_PUBLIC_SUPABASE_URL=https://xxx.supabase.co
      NEXT_PUBLIC_SUPABASE_ANON_KEY=eyJxxx...
    """
    if not ENV_FILE.exists():
        return False
    try:
        with open(ENV_FILE, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                # Skip comment dan empty line
                if not line or line.startswith('#'):
                    continue
                # Parse KEY=VALUE
                if '=' in line:
                    key, value = line.split('=', 1)
                    key = key.strip()
                    value = value.strip().strip('"').strip("'")
                    # Hanya set kalau belum ada di os.environ (os.environ lebih prioritas)
                    if key and key not in os.environ:
                        os.environ[key] = value
        return True
    except Exception as e:
        print(f'  ⚠ Gagal load .env: {e}')
        return False


# Load .env di awal (sebelum SUPABASE_URL/KEY di-read)
load_env_file()

SUPABASE_URL = os.environ.get('NEXT_PUBLIC_SUPABASE_URL', '')
SUPABASE_KEY = os.environ.get('NEXT_PUBLIC_SUPABASE_ANON_KEY', '')


def get_kamus_path():
    """Cari kamus JSON di ~/Dubbing/"""
    if KAMUS_FULL.exists():
        return KAMUS_FULL
    return None


def load_kamus():
    path = get_kamus_path()
    if not path:
        print(f'\n❌ Kamus JSON tidak ada di:')
        print(f'   {KAMUS_FULL}')
        print(f'\n   Download:')
        print(f'   curl -L -o ~/Dubbing/kamus-jawa-full.json.gz \\')
        print(f'     https://github.com/emailnyamahmud-afk/srt-splitter/raw/main/public/kamus-jawa-full.json.gz')
        print(f'   gunzip ~/Dubbing/kamus-jawa-full.json.gz')
        return None
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def save_kamus(data):
    """Save ke JSON file + recompute status untuk SEMUA entries.

    Status logic:
    - 'ready' = ngoko + krama + arti SEMUA terisi → siap upload ke Supabase
    - 'draft' = belum lengkap

    SELALU recompute status setiap save (jangan skip yang sudah punya status).
    User edit arti → status harus recompute dari draft → ready.
    """
    for w in data['words']:
        ngoko = (w.get('ngoko') or '').strip()
        krama = (w.get('krama') or '').strip()
        arti = (w.get('arti') or '').strip()
        w['status'] = 'ready' if (ngoko and krama and arti) else 'draft'
    path = get_kamus_path()
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def show_stats(data):
    """Tampilkan statistik kamus"""
    os.system('clear' if os.name != 'nt' else 'cls')
    words = data['words']
    total = len(words)

    # Register breakdown
    from collections import Counter
    reg_count = Counter(w.get('register', 'umum') for w in words)

    # Mapping stats
    with_krama = sum(1 for w in words if (w.get('krama') or '').strip())
    with_ki = sum(1 for w in words if (w.get('krama_inggil') or '').strip())
    with_arti = sum(1 for w in words if (w.get('arti') or '').strip())
    both_ngoko_krama = sum(1 for w in words if (w.get('ngoko') or '').strip() and (w.get('krama') or '').strip())
    ready_count = sum(1 for w in words if w.get('status') == 'ready')

    # Status
    status_count = Counter(w.get('status', 'draft') for w in words)

    print('╔' + '═' * 60 + '╗')
    print('║  📊 Statistik Kamus Jawa' + ' ' * 36 + '║')
    print('╚' + '═' * 60 + '╝')
    print()
    print(f'  Total entries: {total}')
    print()
    print('  Register breakdown:')
    for r, c in reg_count.most_common():
        print(f'    {r:15s}: {c:6d}')
    print()
    print('  Mapping stats:')
    print(f'    ngoko + krama (auto-filled):    {both_ngoko_krama:6d}  ⭐ (dari template Wikisastra)')
    print(f'    krama filled:                   {with_krama:6d}')
    print(f'    krama_inggil filled:            {with_ki:6d}  (opsional)')
    print(f'    arti (Indonesia) filled:        {with_arti:6d}  ⭐ (user edit manual)')
    print(f'    SIAP UPLOAD (3 field lengkap): {ready_count:6d}  🚀')
    print()
    print('  Status (untuk upload):')
    for s, c in status_count.most_common():
        icon = '🚀' if s == 'ready' else '○'
        print(f'    {icon} {s:10s}: {c:6d}')
    print()
    print(f'  Sumber file: {get_kamus_path()}')
    print()
    input('  Tekan Enter untuk kembali...')


def edit_entry(data, idx):
    """Edit 1 entry: ngoko, krama, krama_inggil, arti, register + merge dengan entry lain"""
    entry = data['words'][idx]
    entry_id = entry.get('entry_id', idx + 1)
    ngoko_old = entry.get('ngoko', '')
    krama_old = entry.get('krama', '')
    ki_old = entry.get('krama_inggil', '')
    arti_old = entry.get('arti', '')
    register = entry.get('register', 'umum')
    ket = entry.get('keterangan', '')
    sumber = entry.get('sumber', '')

    os.system('clear' if os.name != 'nt' else 'cls')
    print('╔' + '═' * 60 + '╗')
    print(f'║  ✏️  Edit Entry #{entry_id}' + ' ' * (44 - len(str(entry_id))) + '║')
    print('╚' + '═' * 60 + '╝')
    print()
    print(f'  ┌─────────────────────────────────────────────┐')
    print(f'  │ entry_id:     #{entry_id}')
    print(f'  │ ngoko:        {ngoko_old[:42]}')
    print(f'  │ aksara:        {entry.get("aksara", "")[:42]}')
    print(f'  │ krama:         {krama_old[:42] or "(kosong)"}')
    print(f'  │ krama_inggil:  {ki_old[:42] or "(kosong)"}')
    print(f'  │ arti (ID):     {arti_old[:42] or "(kosong)"}')
    print(f'  │ register:      {register}')
    print(f'  │ sumber:        {sumber[:42]}')
    print(f'  └─────────────────────────────────────────────┘')
    print()
    print('  📖 Keterangan (definisi JAWA — JANGAN HAPUS, bantu isi arti):')
    # Wrap keterangan to 50 chars per line
    ket_lines = []
    if ket:
        words = ket.split()
        line = '    '
        for word in words:
            if len(line) + len(word) + 1 > 56:
                ket_lines.append(line)
                line = '    ' + word
            else:
                line += (' ' + word if line.strip() else word)
        if line.strip():
            ket_lines.append(line)
    for kl in ket_lines[:6]:
        print(kl)
    if len(ket_lines) > 6:
        print(f'    ...({len(ket_lines) - 6} baris lagi)')
    print()

    # Edit fields
    print('  Edit (Enter=keep existing, type new value):')
    new_ngoko = questionary.text('  ngoko:', default=ngoko_old).ask()
    new_krama = questionary.text('  krama:', default=krama_old).ask()
    new_ki = questionary.text('  krama_inggil:', default=ki_old).ask()
    new_arti = questionary.text('  arti (Indonesia):', default=arti_old).ask()

    # Register dropdown — user bisa fix register (mis. 'ingkang' dari umum → krama)
    register_choices = ['ngoko', 'krama', 'krama_inggil', 'kawi', 'umum']
    register_default = register if register in register_choices else 'umum'
    new_register = questionary.select(
        '  register:',
        choices=register_choices,
        default=register_default,
    ).ask()

    if new_ngoko is None or new_krama is None or new_ki is None or new_arti is None or new_register is None:
        print('\n  ⏹ Dibatalkan.')
        input('  Tekan Enter...')
        return

    # Strip
    new_ngoko = (new_ngoko or '').strip()
    new_krama = (new_krama or '').strip()
    new_ki = (new_ki or '').strip()
    new_arti = (new_arti or '').strip()
    new_register = (new_register or 'umum').strip()

    # Cek perubahan
    changed = (
        new_ngoko != ngoko_old or
        new_krama != krama_old or
        new_ki != ki_old or
        new_arti != arti_old or
        new_register != register
    )

    if not changed:
        print('\n  (tidak ada perubahan)')
        input('\n  Tekan Enter...')
        return

    # Update entry
    entry['ngoko'] = new_ngoko
    entry['krama'] = new_krama
    if new_ki:
        entry['krama_inggil'] = new_ki
    elif 'krama_inggil' in entry:
        del entry['krama_inggil']
    entry['arti'] = new_arti
    entry['register'] = new_register  # update register
    # Status auto-detect di save_kamus (ngoko+krama+arti semua terisi → 'ready')

    save_kamus(data)
    # Status baru
    new_status = 'ready' if (new_ngoko and new_krama and new_arti) else 'draft'
    print(f'\n  ✅ Disimpan: ngoko={new_ngoko} → krama={new_krama} → arti={new_arti}')
    print(f'  Register: {new_register}')
    print(f'  Status: {new_status}' + (' (siap upload)' if new_status == 'ready' else ' (butuh arti dulu)'))

    input('\n  Tekan Enter...')


def browse_list(data, entries_with_idx, title):
    """Browse list of entries (idx, entry) dengan pagination"""
    total = len(entries_with_idx)
    if total == 0:
        print(f'\n  Tidak ada entri untuk "{title}"')
        input('\n  Tekan Enter...')
        return

    page_size = 20
    current_page = 0

    while True:
        start = current_page * page_size
        end = min(start + page_size, total)
        page = entries_with_idx[start:end]

        os.system('clear' if os.name != 'nt' else 'cls')
        print('╔' + '═' * 60 + '╗')
        print(f'║  {title[:58]}' + ' ' * max(0, 58 - len(title)) + '║')
        print(f'║  {total} entri | Hal {current_page + 1}/{(total + page_size - 1) // page_size}' + ' ' * max(0, 30 - len(str(total)) - len(str(current_page + 1)) - len(str((total + page_size - 1) // page_size))) + '║')
        print('╚' + '═' * 60 + '╝')
        print()

        # Build label → idx mapping (untuk lookup saat select)
        label_to_idx = {}
        choices = []
        for orig_idx, entry in page:
            ngoko = entry.get('ngoko', '') or entry.get('krama', '') or ''
            ngoko_display = ngoko[:25]
            krama = entry.get('krama', '') or ''
            ki = entry.get('krama_inggil', '') or ''
            arti = entry.get('arti', '') or ''
            status = entry.get('status', 'draft')
            register = entry.get('register', 'umum')
            entry_id = entry.get('entry_id', orig_idx + 1)
            icon = '✓' if status == 'ready' else '○'

            # Build unique label — tampilkan entry_id (dari JSON) supaya user bisa referensi
            label = f'{icon} #{entry_id:5d}. {ngoko_display:25s}'
            if krama:
                label += f' → {krama[:15]:15s}'
            if ki:
                label += f' | ki: {ki[:10]}'
            if arti:
                label += f' | {arti[:15]}'
            # Tampilkan register kalau bukan default (umum)
            if register != 'umum':
                label += f' [{register}]'
            label_to_idx[label] = orig_idx
            choices.append(label)

        # Navigation
        nav = []
        if current_page > 0:
            nav.append('◀ Halaman sebelumnya')
        if end < total:
            nav.append('▶ Halaman berikutnya')
        nav.append('🔍 Search di list ini')
        nav.append('↩ Kembali ke menu utama')

        choices.extend(nav)

        selected = questionary.select(
            f'Pilih entri (✓=sudah diedit, ○=belum):',
            choices=choices,
            default=choices[0],
        ).ask()

        if not selected or 'Kembali ke menu' in selected:
            return

        if 'sebelumnya' in selected:
            current_page = max(0, current_page - 1)
            continue

        if 'berikutnya' in selected:
            current_page += 1
            continue

        if 'Search' in selected:
            search_query = questionary.text('Cari kata di list ini:').ask()
            if search_query:
                search_lower = search_query.lower().strip()
                # Exact match dulu, baru substring (sama seperti search_menu)
                exact_f = []
                substr_f = []
                for i, e in entries_with_idx:
                    ngoko = (e.get('ngoko', '') or '').lower()
                    krama = (e.get('krama', '') or '').lower()
                    ki = (e.get('krama_inggil', '') or '').lower()
                    arti = (e.get('arti', '') or '').lower()
                    if ngoko == search_lower or krama == search_lower or ki == search_lower or arti == search_lower:
                        exact_f.append((i, e))
                    elif (search_lower in ngoko or search_lower in krama or
                          search_lower in ki or search_lower in arti):
                        substr_f.append((i, e))
                filtered = exact_f + substr_f
                if filtered:
                    browse_list(data, filtered, f'🔍 Search "{search_query}"')
                else:
                    print(f'\n  Tidak ada hasil untuk "{search_query}"')
                    input('\n  Tekan Enter...')
            continue

        # Find which entry was selected (lookup di label_to_idx)
        match_idx = label_to_idx.get(selected)
        if match_idx is not None:
            edit_entry(data, match_idx)


def search_menu(data):
    """Search kamus — exact match dulu, baru substring. Hanya di ngoko/krama/krama_inggil/arti."""
    os.system('clear' if os.name != 'nt' else 'cls')
    print('╔' + '═' * 60 + '╗')
    print('║  🔍 Search Kamus' + ' ' * 44 + '║')
    print('╚' + '═' * 60 + '╝')
    print()

    query = questionary.text('Cari kata (di ngoko / krama / arti):').ask()
    if not query:
        return

    search_lower = query.lower().strip()
    # Exact match dulu (ngoko/krama/krama_inggil/arti persis = kata), baru substring
    # TIDAK search di keterangan (terlalu banyak noise)
    exact = []
    substr = []
    for i, entry in enumerate(data['words']):
        ngoko = (entry.get('ngoko') or '').lower()
        krama = (entry.get('krama') or '').lower()
        ki = (entry.get('krama_inggil') or '').lower()
        arti = (entry.get('arti') or '').lower()
        if ngoko == search_lower or krama == search_lower or ki == search_lower or arti == search_lower:
            exact.append((i, entry))
        elif (search_lower in ngoko or search_lower in krama or
              search_lower in ki or search_lower in arti):
            substr.append((i, entry))
    matches = exact + substr

    if not matches:
        print(f'\n  Tidak ada hasil untuk "{query}"')
        input('\n  Tekan Enter...')
        return

    browse_list(data, matches, f'🔍 Search "{query}"')


def browse_with_krama(data):
    """Browse entries yang sudah ada krama mapping (auto-filled)"""
    matches = [(i, w) for i, w in enumerate(data['words']) if (w.get('krama') or '').strip()]
    browse_list(data, matches, '⭐ Entries dengan krama mapping (auto-filled)')


def browse_no_arti(data):
    """Browse entries yang BELUM ada arti (Indonesia)"""
    matches = [(i, w) for i, w in enumerate(data['words']) if not (w.get('arti') or '').strip()]
    browse_list(data, matches, '📝 Entries BELUM ada arti (Indonesia)')


def browse_by_register(data, register):
    """Browse entries berdasarkan register"""
    matches = [(i, w) for i, w in enumerate(data['words']) if w.get('register', 'umum') == register]
    browse_list(data, matches, f'🎯 Register: {register} ({len(matches)} entri)')


def edit_env_file():
    """Buka/edit file .env di ~/Dubbing/ untuk set Supabase credentials.
    Kalau belum ada, buat template otomatis.
    """
    print('\n  📁 .env file: ' + str(ENV_FILE))
    print()

    if ENV_FILE.exists():
        # Tampilkan isi yang sudah ada (sensor key)
        with open(ENV_FILE, 'r', encoding='utf-8') as f:
            content = f.read()
        # Sensor anon key (tampilkan 10 char pertama + ...)
        lines = content.split('\n')
        print('  Isi sekarang:')
        for line in lines:
            if line.startswith('NEXT_PUBLIC_SUPABASE_ANON_KEY='):
                # Sensor: tampilkan URL saja, bukan key lengkap
                key_val = line.split('=', 1)[1] if '=' in line else ''
                if len(key_val) > 15:
                    print(f'    NEXT_PUBLIC_SUPABASE_ANON_KEY={key_val[:10]}...{key_val[-4:]} (hidden)')
                else:
                    print('    NEXT_PUBLIC_SUPABASE_ANON_KEY=... (hidden)')
            else:
                print(f'    {line}')
        print()
        edit_now = questionary.confirm('Edit .env sekarang?', default=False).ask()
        if not edit_now:
            return
    else:
        # Buat template
        print('  .env belum ada. Bikin sekarang?')
        create = questionary.confirm('Buat .env baru?', default=True).ask()
        if not create:
            return
        template = """# Supabase credentials untuk kamus-tui.py
# Dapatkan dari: https://supabase.com/dashboard/project/xxx/settings/api
NEXT_PUBLIC_SUPABASE_URL=https://zdrgzbwjlrvyloxjdyfl.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=
"""
        with open(ENV_FILE, 'w', encoding='utf-8') as f:
            f.write(template)
        print(f'\n  ✅ Template dibuat: {ENV_FILE}')
        print('  Sekarang edit isi file .env:')
        print()

    # Input URL
    url_input = questionary.text(
        'NEXT_PUBLIC_SUPABASE_URL:',
        default=os.environ.get('NEXT_PUBLIC_SUPABASE_URL', 'https://zdrgzbwjlrvyloxjdyfl.supabase.co')
    ).ask()
    if url_input is None:
        return
    url_input = url_input.strip()

    # Input anon key (password style — tampilkan * saat user ketik, agar aman)
    existing_key = os.environ.get('NEXT_PUBLIC_SUPABASE_ANON_KEY', '')
    key_default = existing_key if existing_key else ''
    key_input = questionary.text(
        'NEXT_PUBLIC_SUPABASE_ANON_KEY (paste di sini):',
        default=key_default,
    ).ask()
    if key_input is None:
        return
    key_input = key_input.strip()

    if not url_input or not key_input:
        print('\n  ⚠ URL dan ANON KEY wajib diisi.')
        input('  Tekan Enter...')
        return

    # Write ke .env
    with open(ENV_FILE, 'w', encoding='utf-8') as f:
        f.write('# Supabase credentials untuk kamus-tui.py\n')
        f.write('# Dapatkan dari: https://supabase.com/dashboard/project/xxx/settings/api\n')
        f.write(f'NEXT_PUBLIC_SUPABASE_URL={url_input}\n')
        f.write(f'NEXT_PUBLIC_SUPABASE_ANON_KEY={key_input}\n')

    # Update os.environ juga (supaya bisa upload langsung tanpa restart)
    os.environ['NEXT_PUBLIC_SUPABASE_URL'] = url_input
    os.environ['NEXT_PUBLIC_SUPABASE_ANON_KEY'] = key_input

    print(f'\n  ✅ .env disimpan: {ENV_FILE}')
    print(f'  → URL: {url_input[:40]}...')
    print(f'  → KEY: {key_input[:10]}...{key_input[-4:]} (hidden)')
    print()
    print('  Sekarang upload ke Supabase akan langsung jalan.')
    input('  Tekan Enter...')


def main_menu(data):
    """Main menu — user pilih menu dengan arrow keys"""
    while True:
        os.system('clear' if os.name != 'nt' else 'cls')
        words = data['words']
        total = len(words)
        ready = sum(1 for w in words if w.get('status') == 'ready')
        with_arti = sum(1 for w in words if (w.get('arti') or '').strip())
        no_arti = sum(1 for w in words if not (w.get('arti') or '').strip())

        # Cek Supabase status
        supabase_ok = bool(os.environ.get('NEXT_PUBLIC_SUPABASE_URL') and os.environ.get('NEXT_PUBLIC_SUPABASE_ANON_KEY'))

        print('╔' + '═' * 60 + '╗')
        print('║  📖 Kamus Jawa Editor (TUI v2)' + ' ' * 28 + '║')
        print('║  Tab/panah untuk navigasi, Enter untuk pilih' + ' ' * 11 + '║')
        print('╚' + '═' * 60 + '╝')
        print()
        print(f'  📂 {get_kamus_path()}')
        print(f'  📊 Total: {total} | arti diisi: {with_arti} | belum ada arti: {no_arti}')
        print(f'  🚀 Siap upload (ngoko+krama+arti lengkap): {ready}')
        if supabase_ok:
            print(f'  ☁  Supabase: ✓ ter-set (dari .env atau env vars)')
        else:
            print(f'  ☁  Supabase: ⚠ belum di-set (gunakan menu "🔑 Set Supabase .env")')
        print()

        choices = [
            '📊 Statistik kamus',
            '🔍 Search (cari kata di semua field)',
            '🚀 Browse SIAP UPLOAD (ngoko+krama+arti lengkap)',
            '⭐ Browse entries dengan krama mapping (auto-filled, butuh arti)',
            '📝 Browse entries BELUM ada arti (Indonesia)',
            '⚠ Browse register UMUM (perlu validasi)',
            '🎯 Browse per register (ngoko/krama/krama_inggil/kawi/umum)',
            '🔗 Merge 2 entries (search kata)',
            '🔑 Set Supabase .env (URL + anon key)',
            '☁  Upload ke Supabase (hanya yang SIAP UPLOAD)',
            '💾 Save JSON (manual)',
            '❌ Keluar',
        ]

        selected = questionary.select(
            'Menu:',
            choices=choices,
            default=choices[0],
        ).ask()

        if not selected or 'Keluar' in selected:
            break

        if 'Statistik' in selected:
            show_stats(data)
        elif 'Search' in selected:
            search_menu(data)
        elif '☁' in selected and 'Upload' in selected:
            # Upload ke Supabase — check PERTAMA (sebelum 'SIAP UPLOAD' matching)
            # karena menu upload text-nya mengandung 'SIAP UPLOAD' juga
            upload_to_supabase()
        elif '🚀' in selected and 'SIAP UPLOAD' in selected:
            # Browse SIAP UPLOAD (ngoko+krama+arti lengkap)
            ready_entries = [(i, w) for i, w in enumerate(data['words']) if w.get('status') == 'ready']
            browse_list(data, ready_entries, f'🚀 Siap Upload ({len(ready_entries)} entri lengkap)')
        elif '⚠' in selected and 'UMUM' in selected:
            # Browse register umum — perlu validasi manual (17.812 entries)
            umum_entries = [(i, w) for i, w in enumerate(data['words']) if w.get('register', 'umum') == 'umum']
            browse_list(data, umum_entries, f'⚠ Register UMUM ({len(umum_entries)} entries — perlu validasi)')
        elif 'krama mapping' in selected:
            browse_with_krama(data)
        elif 'BELUM ada arti' in selected:
            browse_no_arti(data)
        elif 'per register' in selected:
            register_choices = ['ngoko', 'krama', 'krama_inggil', 'kawi', 'umum', '↩ Kembali']
            reg_selected = questionary.select(
                'Pilih register:',
                choices=register_choices,
                default=register_choices[0],
            ).ask()
            if reg_selected and 'Kembali' not in reg_selected:
                browse_by_register(data, reg_selected)
        elif '🔗' in selected and 'Merge' in selected:
            # Merge 2 entries — LANGSUNG: search kata 1 → search kata 2 → preview → konfirmasi
            print('\n  ═══ MERGE 2 ENTRIES ═══')
            print('  Gabung 2 entries terpisah jadi 1 entry.')
            print('  Contoh: sing (entry terpisah) + ingkang (entry terpisah)')
            print('          → 1 entry: ngoko=sing, krama=ingkang, arti=yang')
            print()

            # Step 1: Search entry pertama
            q1 = questionary.text('1. Cari kata pertama (mis. "sing"):').ask()
            if not q1 or not q1.strip():
                continue
            q1_lower = q1.lower().strip()
            # Exact match dulu (ngoko atau krama persis = kata), baru substring
            exact_m1 = []
            substr_m1 = []
            for i, w in enumerate(data['words']):
                ngoko = (w.get('ngoko') or '').lower()
                krama = (w.get('krama') or '').lower()
                if ngoko == q1_lower or krama == q1_lower:
                    exact_m1.append((i, w))
                elif q1_lower in ngoko or q1_lower in krama:
                    substr_m1.append((i, w))
            m1 = exact_m1 + substr_m1  # exact dulu, baru substring
            if not m1:
                print(f'  ❌ Tidak ada hasil untuk "{q1}"')
                input('  Tekan Enter...')
                continue

            idx_map1 = {}
            choices1 = []
            for orig_idx, w in m1[:20]:
                ngoko = (w.get('ngoko') or '').strip()[:25]
                krama = (w.get('krama') or '').strip()[:20]
                eid = w.get('entry_id', '?')
                label = f'#{eid:>5} {ngoko:25s} → {krama:20s}'
                idx_map1[label] = orig_idx
                choices1.append(label)
            choices1.append('↩ Batal')
            sel1 = questionary.select('Pilih entry pertama:', choices=choices1, default=choices1[0]).ask()
            if not sel1 or 'Batal' in sel1:
                continue
            idx1 = idx_map1.get(sel1)
            if idx1 is None:
                continue

            entry1 = data['words'][idx1]
            eid1 = entry1.get('entry_id', '?')
            print(f'\n  Entry 1: ngoko={entry1.get("ngoko","")!r} krama={entry1.get("krama","")!r} arti={entry1.get("arti","")!r}')

            # Step 2: Search entry kedua
            q2 = questionary.text('\n2. Cari kata kedua (mis. "ingkang"):').ask()
            if not q2 or not q2.strip():
                continue
            q2_lower = q2.lower().strip()
            # Exact match dulu, baru substring
            exact_m2 = []
            substr_m2 = []
            for i, w in enumerate(data['words']):
                if i == idx1:
                    continue
                ngoko = (w.get('ngoko') or '').lower()
                krama = (w.get('krama') or '').lower()
                if ngoko == q2_lower or krama == q2_lower:
                    exact_m2.append((i, w))
                elif q2_lower in ngoko or q2_lower in krama:
                    substr_m2.append((i, w))
            m2 = exact_m2 + substr_m2  # exact dulu, baru substring
            if not m2:
                print(f'  ❌ Tidak ada hasil untuk "{q2}"')
                input('  Tekan Enter...')
                continue

            idx_map2 = {}
            choices2 = []
            for orig_idx, w in m2[:20]:
                ngoko = (w.get('ngoko') or '').strip()[:25]
                krama = (w.get('krama') or '').strip()[:20]
                eid = w.get('entry_id', '?')
                label = f'#{eid:>5} {ngoko:25s} → {krama:20s}'
                idx_map2[label] = orig_idx
                choices2.append(label)
            choices2.append('↩ Batal')
            sel2 = questionary.select('Pilih entry kedua:', choices=choices2, default=choices2[0]).ask()
            if not sel2 or 'Batal' in sel2:
                continue
            idx2 = idx_map2.get(sel2)
            if idx2 is None:
                continue

            entry2 = data['words'][idx2]
            eid2 = entry2.get('entry_id', '?')
            print(f'\n  Entry 2: ngoko={entry2.get("ngoko","")!r} krama={entry2.get("krama","")!r} arti={entry2.get("arti","")!r}')

            # Step 3: Preview merge
            # Smart merge: gabung field yang tidak kosong
            merged_ngoko = (entry1.get('ngoko') or '').strip() or (entry2.get('ngoko') or '').strip()
            merged_krama = (entry1.get('krama') or '').strip() or (entry2.get('krama') or '').strip()
            # Kalau entry1 ngoko == entry2 krama (atau sebaliknya), itu pasangan yang sama
            # Kalau entry1 ngoko kosong tapi entry2 krama = entry1 ngoko → pakai entry2 ngoko
            e1_ngoko = (entry1.get('ngoko') or '').strip()
            e1_krama = (entry1.get('krama') or '').strip()
            e2_ngoko = (entry2.get('ngoko') or '').strip()
            e2_krama = (entry2.get('krama') or '').strip()

            # Kalau entry2 ngoko kosong tapi entry2 ada krama = entry1 ngoko → entry2 itu krama word
            # Hasil: ngoko=entry1.ngoko, krama=entry2.ngoko (krama word)
            if not e2_krama and e2_ngoko and e1_krama and e2_ngoko.lower() == e1_krama.lower():
                merged_ngoko = e1_ngoko
                merged_krama = e2_ngoko  # entry2 title = krama word
            elif not e1_krama and e1_ngoko and e2_krama and e1_ngoko.lower() == e2_krama.lower():
                merged_ngoko = e2_ngoko
                merged_krama = e1_ngoko  # entry1 title = krama word

            merged_arti = (entry1.get('arti') or '').strip() or (entry2.get('arti') or '').strip()

            # Register: krama_inggil > krama > ngoko > umum
            reg_order = {'krama_inggil': 0, 'krama': 1, 'ngoko': 2, 'kawi': 3, 'umum': 4}
            r1 = entry1.get('register', 'umum')
            r2 = entry2.get('register', 'umum')
            merged_reg = r1 if reg_order.get(r1, 99) < reg_order.get(r2, 99) else r2

            print(f'\n  ═══ HASIL MERGE ═══')
            print(f'  ngoko:    {merged_ngoko!r}')
            print(f'  krama:    {merged_krama!r}')
            print(f'  arti:     {merged_arti!r}  (kosong = isi nanti)')
            print(f'  register: {merged_reg}')
            print(f'  Entry #{eid2} akan di-DELETE.')
            print()

            # Step 4: Konfirmasi
            confirm = questionary.confirm('Konfirmasi merge?', default=False).ask()
            if not confirm:
                print('  ⏹ Dibatalkan.')
                input('  Tekan Enter...')
                continue

            # Apply: simpan ke entry1, delete entry2
            entry1['ngoko'] = merged_ngoko
            entry1['krama'] = merged_krama
            entry1['arti'] = merged_arti
            entry1['register'] = merged_reg
            # Combine keterangan
            k1 = (entry1.get('keterangan') or '').strip()
            k2 = (entry2.get('keterangan') or '').strip()
            if k2 and k2 not in k1:
                entry1['keterangan'] = f'{k1} | {k2}'.strip(' |')
            # Sumber
            s1 = (entry1.get('sumber') or '').strip()
            s2 = (entry2.get('sumber') or '').strip()
            if s2 and s2 not in s1:
                entry1['sumber'] = f'{s1} + merge #{eid2}'

            # Delete entry2
            del data['words'][idx2]

            # Re-number entry_id
            for i, w in enumerate(data['words'], 1):
                w['entry_id'] = i

            save_kamus(data)
            print(f'\n  ✅ Merge sukses!')
            print(f'  Hasil: ngoko={merged_ngoko!r} krama={merged_krama!r} arti={merged_arti!r}')
            print(f'  Entry #{eid2} di-DELETE. Total: {len(data["words"])}')
            print(f'  Sekarang isi arti: menu 📝 Browse BELUM ada arti → search kata → edit')
            input('  Tekan Enter...')
        elif '🔑' in selected and 'Supabase .env' in selected:
            edit_env_file()
        elif 'Save JSON' in selected:
            save_kamus(data)
            print('\n  ✅ JSON disimpan')
            input('  Tekan Enter...')


def upload_to_supabase():
    """Upload entri yang sudah di-edit user ke Supabase (subprocess)"""
    # Buat script Python sementara untuk upload (subprocess supaya output tidak di-clear)
    script = '''
import json, sys, os, urllib.request, urllib.error

KAMUS_PATH = None
import os.path
from pathlib import Path
KAMUS_PATH = Path.home() / "Dubbing" / "kamus-jawa-full.json"

URL = os.environ.get("NEXT_PUBLIC_SUPABASE_URL", "")
KEY = os.environ.get("NEXT_PUBLIC_SUPABASE_ANON_KEY", "")

if not URL or not KEY:
    print("\\n  ❌ Supabase belum di-set.")
    print()
    print("  Cara 1: Buat file .env di ~/Dubbing/ (RECOMMEND, sekali buat, jalan terus):")
    print()
    print('    nano ~/Dubbing/.env')
    print()
    print('  Isi file .env:')
    print('    NEXT_PUBLIC_SUPABASE_URL=https://xxx.supabase.co')
    print('    NEXT_PUBLIC_SUPABASE_ANON_KEY=eyJxxx...')
    print()
    print("  Save (Ctrl+X, Y, Enter)")
    print()
    print("  Cara 2: Set env vars manual di terminal (hilang saat terminal close):")
    print('  export NEXT_PUBLIC_SUPABASE_URL="https://xxx.supabase.co"')
    print('  export NEXT_PUBLIC_SUPABASE_ANON_KEY="eyJxxx..."')
    input("\\n  Tekan Enter...")
    sys.exit(1)

if not KAMUS_PATH:
    print(f"\\n  ❌ Kamus JSON tidak ada di ~/Dubbing/")
    input("\\n  Tekan Enter...")
    sys.exit(1)

print(f"\\n  → Load kamus: {KAMUS_PATH}")
with open(KAMUS_PATH, "r", encoding="utf-8") as f:
    data = json.load(f)

# Filter: HANYA upload entries yang SIAP UPLOAD
# Yaitu: ngoko + krama + arti SEMUA terisi (3 field wajib lengkap)
# krama_inggil OPSIONAL (include kalau ada)
# Yang auto-fill krama tanpa arti TIDAK di-upload (belum divalidasi user)
edited = []
for entry in data.get("words", []):
    ngoko = (entry.get("ngoko") or "").strip()
    krama = (entry.get("krama") or "").strip()
    arti = (entry.get("arti") or "").strip()

    # 3 field wajib: ngoko + krama + arti semua harus terisi
    if ngoko and krama and arti:
        ki = (entry.get("krama_inggil") or "").strip()
        register = (entry.get("register") or "").strip()
        # SEMUA row harus punya keys yang sama (Supabase PGRST102: all keys must match)
        row = {
            "ngoko": ngoko,
            "aksara": entry.get("aksara", ""),
            "krama": krama,
            "krama_inggil": ki,        # opsional, kosong kalau tidak ada
            "arti": arti,
            "keterangan": entry.get("keterangan", ""),
            "register": register,      # kosong/umum kalau tidak ada
            "sumber": entry.get("sumber", "jv.wiktionary.org"),
            "status": "ready",
        }
        edited.append(row)

if not edited:
    print("  ⚠ Tidak ada entri yang SIAP UPLOAD.")
    print("     Syarat: ngoko + krama + arti SEMUA terisi (3 field wajib).")
    print("     krama_inggil opsional.")
    print("     Edit dulu di TUI: browse → pilih entri → isi arti Indonesia")
    input("\\n  Tekan Enter...")
    sys.exit(0)

print(f"  → {len(edited)} entri akan di-upload")
print(f"  → Supabase: {URL[:40]}...")
print()

headers = {
    "apikey": KEY,
    "Authorization": f"Bearer {KEY}",
    "Content-Type": "application/json",
    "Prefer": "resolution=merge-duplicates,return=minimal",
}

batch_size = 500
success = 0
failed = 0
for i in range(0, len(edited), batch_size):
    batch = edited[i:i + batch_size]
    batch_json = json.dumps(batch)
    ins_url = f"{URL}/rest/v1/kamus"
    ins_req = urllib.request.Request(
        ins_url,
        data=batch_json.encode("utf-8"),
        headers=headers,
        method="POST",
    )
    try:
        urllib.request.urlopen(ins_req)
        success += len(batch)
        print(f"  → {success}/{len(edited)}...", end="\\r")
    except urllib.error.HTTPError as e:
        failed += len(batch)
        error_body = e.read().decode("utf-8", errors="replace")[:300]
        print(f"\\n  ❌ HTTP {e.code}: {error_body}")
        break
    except Exception as e:
        failed += len(batch)
        print(f"\\n  ❌ Error: {e}")
        break

print(f"\\n  ✅ Upload: {success} sukses, {failed} gagal")
input("\\n  Tekan Enter untuk kembali...")
'''

    # Tulis script sementara
    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False, dir='/tmp') as f:
        f.write(script)
        temp_path = f.name

    try:
        # Jalankan di subprocess
        subprocess.run([sys.executable, temp_path])
    finally:
        os.unlink(temp_path)


def main():
    os.system('clear' if os.name != 'nt' else 'cls')
    print('╔' + '═' * 60 + '╗')
    print('║  📖 Kamus Jawa Editor (TUI v2)' + ' ' * 28 + '║')
    print('║  Menu pre-built — arrow keys, no jq needed' + ' ' * 17 + '║')
    print('╚' + '═' * 60 + '╝')
    print()

    data = load_kamus()
    if not data:
        sys.exit(1)

    # Update status semua entries berdasarkan kelengkapan field
    # Status 'ready' = ngoko + krama + arti semua terisi
    # Status 'draft' = belum lengkap
    reset_count = 0
    for w in data['words']:
        ngoko = (w.get('ngoko') or '').strip()
        krama = (w.get('krama') or '').strip()
        arti = (w.get('arti') or '').strip()
        old_status = w.get('status', 'draft')
        new_status = 'ready' if (ngoko and krama and arti) else 'draft'
        if old_status != new_status:
            w['status'] = new_status
            reset_count += 1
    if reset_count > 0:
        save_kamus(data)
        ready_count = sum(1 for w in data['words'] if w.get('status') == 'ready')
        print(f'  ⚠ Update status: {reset_count} entries')
        print(f'    Status: ready = ngoko+krama+arti lengkap (siap upload)')
        print(f'           draft = belum lengkap (butuh arti)')
        print(f'    Siap upload: {ready_count} entries')
        print()

    main_menu(data)

    print('\nSelesai. Sampai jumpa!')


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print('\n\n⏹ Dibatalkan.')
        sys.exit(130)
    except Exception as e:
        print(f'\n❌ Error: {e}', file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)
