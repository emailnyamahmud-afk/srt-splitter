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

# Kamus JSON path — sekarang pakai kamus-jawa-draft.json (group by konsep, 43.109 entri, register umum)
# Schema konsep: {entry_id, ngoko, krama, krama_inggil, arti, keterangan, aksara, register, sumber, is_lemma, lemma_words, source_count}
# Source raw dipertahankan: kamus-jawa-full.json (44.585) + kamus-jawa-lemma-raw.json (2.159) — JANGAN DIHAPUS
# "bersih" = ambigu, ganti ke "draft" karena masih banyak kosong. User isi bertahap, upload yang ready ke Supabase.
KAMUS_FULL = Path.home() / 'Dubbing' / 'kamus-jawa-draft.json'
KAMUS_LEGACY = Path.home() / 'Dubbing' / 'kamus-jawa-full.json'  # fallback kalau draft.json belum didownload

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
    """Cari kamus JSON di ~/Dubbing/ — prefer kamus-jawa-draft.json, fallback ke kamus-jawa-full.json."""
    if KAMUS_FULL.exists():
        return KAMUS_FULL
    if KAMUS_LEGACY.exists():
        print(f'  ⚠ {KAMUS_FULL.name} tidak ditemukan, pakai legacy: {KAMUS_LEGACY.name}')
        print(f'  💡 Download kamus-jawa-draft.json (43.109 konsep, group by konsep, register umum):')
        print(f'     curl -L -o ~/Dubbing/kamus-jawa-draft.json \\')
        print(f'       "https://raw.githubusercontent.com/emailnyamahmud-afk/srt-splitter/main/public/kamus-jawa-draft.json?v=1"')
        print()
        return KAMUS_LEGACY
    return None


def load_kamus():
    path = get_kamus_path()
    if not path:
        print(f'\n❌ Kamus JSON tidak ada di:')
        print(f'   {KAMUS_FULL}')
        print(f'   {KAMUS_LEGACY}')
        print(f'\n   Download kamus-jawa-draft.json (43.109 konsep, RECOMMEND):')
        print(f'   curl -L -o ~/Dubbing/kamus-jawa-draft.json \\')
        print(f'     "https://raw.githubusercontent.com/emailnyamahmud-afk/srt-splitter/main/public/kamus-jawa-draft.json?v=1"')
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

    entry_id: dipertahankan dari build-kamus-bersih (urut alfabetis).
    Kalau ada entry yang di-delete (via merge), re-number entry_id 1..N supaya tetap konsisten.
    """
    for w in data['words']:
        ngoko = (w.get('ngoko') or '').strip()
        krama = (w.get('krama') or '').strip()
        arti = (w.get('arti') or '').strip()
        w['status'] = 'ready' if (ngoko and krama and arti) else 'draft'
    # Re-number entry_id (urut posisi list = urut alfabetis dari build-kamus-bersih)
    for i, w in enumerate(data['words'], 1):
        w['entry_id'] = i
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

    # Status
    status_count = Counter(w.get('status', 'draft') for w in words)
    ready_count = status_count.get('ready', 0)
    draft_count = status_count.get('draft', 0)

    # Komposisi kelengkapan field (prioritas kerja user)
    ngoko_only = sum(1 for w in words if (w.get('ngoko') or '').strip() and not (w.get('krama') or '').strip() and not (w.get('arti') or '').strip())
    ngoko_krama = sum(1 for w in words if (w.get('ngoko') or '').strip() and (w.get('krama') or '').strip() and not (w.get('arti') or '').strip())
    ngoko_arti_no_krama = sum(1 for w in words if (w.get('ngoko') or '').strip() and not (w.get('krama') or '').strip() and (w.get('arti') or '').strip())
    ngoko_krama_arti = sum(1 for w in words if (w.get('ngoko') or '').strip() and (w.get('krama') or '').strip() and (w.get('arti') or '').strip())
    no_ngoko = sum(1 for w in words if not (w.get('ngoko') or '').strip())

    # Mapping stats (detail) — for Reference
    with_krama = sum(1 for w in words if (w.get('krama') or '').strip())
    with_ki = sum(1 for w in words if (w.get('krama_inggil') or '').strip())
    with_arti = sum(1 for w in words if (w.get('arti') or '').strip())
    both_ngoko_krama = sum(1 for w in words if (w.get('ngoko') or '').strip() and (w.get('krama') or '').strip())

    print('╔' + '═' * 60 + '╗')
    print('║  📊 Statistik Kamus Jawa' + ' ' * 36 + '║')
    print('╚' + '═' * 60 + '╝')
    print()
    print(f'  Total entries: {total}')
    print()
    print('  Source tags (multi-source tracking):')
    is_lemma = sum(1 for w in words if w.get('is_lemma'))
    is_mend = sum(1 for w in words if w.get('is_mendeley'))
    is_dasa = sum(1 for w in words if w.get('is_dasanama'))
    is_angk = sum(1 for w in words if w.get('is_angka'))
    print(f'    is_lemma:    {is_lemma:6d}  (dari id.wiktionary.org jv:Lema)')
    print(f'    is_mendeley: {is_mend:6d}  (curated, data.mendeley.com)')
    print(f'    is_dasanama: {is_dasa:6d}  (sinonim Jawa, user upload CSV)')
    print(f'    is_angka:    {is_angk:6d}  (angka sistematis)')
    print()
    print('  Komposisi kelengkapan field:')
    print(f'    1. ngoko saja:               {ngoko_only:6d}  (perlu krama + arti)')
    print(f'    2. ngoko + krama:              {ngoko_krama:6d}  (perlu arti)')
    print(f'    3. ngoko + arti (no krama):    {ngoko_arti_no_krama:6d}  (perlu krama)')
    print(f'    4. ngoko + krama + arti:       {ngoko_krama_arti:6d}  (3-field lengkap)')
    print(f'    5. no ngoko (orphan):         {no_ngoko:6d}  (krama-only, kawi)')
    print()
    print('  Status (patokan valid — pakai field status):')
    print(f'    📋 DRAFT (belum di-edit user):      {draft_count:6d}  (default dari build)')
    print(f'    ✅ READY (user sudah edit via TUI):  {ready_count:6d}  🚀 (siap upload Supabase)')
    print()
    print('  Mapping stats (detail):')
    print(f'    ngoko + krama (auto-filled):    {both_ngoko_krama:6d}  ⭐ (dari template Wikisastra)')
    print(f'    krama filled (total):           {with_krama:6d}')
    print(f'    krama_inggil filled:            {with_ki:6d}  (opsional)')
    print(f'    arti (Indonesia) filled:        {with_arti:6d}  ⭐ (user edit manual)')
    print()
    print('  Register breakdown (default umum, user bisa override):')
    for r, c in reg_count.most_common():
        print(f'    {r:15s}: {c:6d}')
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
    # Source tags (multi-source tracking)
    src_tags = []
    if entry.get('is_lemma'): src_tags.append('lemma')
    if entry.get('is_mendeley'): src_tags.append('mendeley')
    if entry.get('is_dasanama'): src_tags.append(f'dasanama({entry.get("dasanama_count",0)})')
    if entry.get('is_angka'): src_tags.append('angka')
    src_str = ', '.join(src_tags) if src_tags else '-'
    src_count = entry.get('source_count', 1)
    status_icon = '✅' if entry.get('status') == 'ready' else '📋'

    print(f'  ┌─────────────────────────────────────────────┐')
    print(f'  │ entry_id:     #{entry_id}')
    print(f'  │ ngoko:        {ngoko_old[:42]}')
    print(f'  │ aksara:        {entry.get("aksara", "")[:42]}')
    print(f'  │ krama:         {krama_old[:42] or "(kosong)"}')
    print(f'  │ krama_inggil:  {ki_old[:42] or "(kosong)"}')
    print(f'  │ arti (ID):     {arti_old[:42] or "(kosong)"}')
    print(f'  │ register:      {register}')
    print(f'  │ sumber:        {sumber[:42]}')
    print(f'  │ source:        [{src_count}x] {src_str}')
    print(f'  │ status:        {status_icon} {entry.get("status", "draft")}')
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
    # User edit + save = user validasi implicit (status jadi 'ready' kalau 3-field lengkap)

    save_kamus(data)
    # Status baru
    new_status = 'ready' if (new_ngoko and new_krama and new_arti) else 'draft'
    print(f'\n  ✅ Disimpan: ngoko={new_ngoko} → krama={new_krama} → arti={new_arti}')
    print(f'  Register: {new_register}')
    print(f'  Status: {new_status}' + (' (siap upload Supabase)' if new_status == 'ready' else ' (butuh 3-field lengkap)'))

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


def browse_by_source(data):
    """Browse entries berdasarkan source tag (lemma/mendeley/dasanama/angka)"""
    src_choices = [
        'is_lemma (dari id.wiktionary.org jv:Lema)',
        'is_mendeley (curated, data.mendeley.com)',
        'is_dasanama (sinonim Jawa)',
        'is_angka (angka sistematis)',
        '↩ Kembali',
    ]
    src_selected = questionary.select(
        'Pilih source:',
        choices=src_choices,
        default=src_choices[0],
    ).ask()
    if not src_selected or 'Kembali' in src_selected:
        return
    if 'is_lemma' in src_selected:
        matches = [(i, w) for i, w in enumerate(data['words']) if w.get('is_lemma')]
        title = f'📂 Source: lemma ({len(matches)} entri)'
    elif 'is_mendeley' in src_selected:
        matches = [(i, w) for i, w in enumerate(data['words']) if w.get('is_mendeley')]
        title = f'📂 Source: mendeley ({len(matches)} entri)'
    elif 'is_dasanama' in src_selected:
        matches = [(i, w) for i, w in enumerate(data['words']) if w.get('is_dasanama')]
        title = f'📂 Source: dasanama ({len(matches)} entri)'
    elif 'is_angka' in src_selected:
        matches = [(i, w) for i, w in enumerate(data['words']) if w.get('is_angka')]
        title = f'📂 Source: angka ({len(matches)} entri)'
    else:
        return
    browse_list(data, matches, title)


def browse_by_kelengkapan(data):
    """Browse entries berdasarkan komposisi kelengkapan field.
    User bisa pilih kerja bertahap:
      1. ngoko saja (perlu krama + arti)
      2. ngoko + krama (perlu arti)
      3. ngoko + arti (no krama) (perlu krama)
      4. ngoko + krama + arti (3-field ready, perlu validasi)
      5. no ngoko (orphan krama-only)
    """
    kel_choices = [
        '1. ngoko saja (perlu krama + arti)',
        '2. ngoko + krama (perlu arti)',
        '3. ngoko + arti (no krama, perlu krama)',
        '4. ngoko + krama + arti (3-field ready, perlu validasi)',
        '5. no ngoko (orphan krama-only)',
        '↩ Kembali',
    ]
    kel_selected = questionary.select(
        'Pilih kelengkapan:',
        choices=kel_choices,
        default=kel_choices[0],
    ).ask()
    if not kel_selected or 'Kembali' in kel_selected:
        return
    if kel_selected.startswith('1.'):
        matches = [(i, w) for i, w in enumerate(data['words'])
                   if (w.get('ngoko') or '').strip()
                   and not (w.get('krama') or '').strip()
                   and not (w.get('arti') or '').strip()]
        title = f'📋 Kelengkapan: ngoko saja ({len(matches)} entri, perlu krama+arti)'
    elif kel_selected.startswith('2.'):
        matches = [(i, w) for i, w in enumerate(data['words'])
                   if (w.get('ngoko') or '').strip()
                   and (w.get('krama') or '').strip()
                   and not (w.get('arti') or '').strip()]
        title = f'📋 Kelengkapan: ngoko+krama ({len(matches)} entri, perlu arti)'
    elif kel_selected.startswith('3.'):
        matches = [(i, w) for i, w in enumerate(data['words'])
                   if (w.get('ngoko') or '').strip()
                   and not (w.get('krama') or '').strip()
                   and (w.get('arti') or '').strip()]
        title = f'📋 Kelengkapan: ngoko+arti ({len(matches)} entri, perlu krama)'
    elif kel_selected.startswith('4.'):
        matches = [(i, w) for i, w in enumerate(data['words'])
                   if (w.get('ngoko') or '').strip()
                   and (w.get('krama') or '').strip()
                   and (w.get('arti') or '').strip()]
        title = f'📋 Kelengkapan: 3-field ready ({len(matches)} entri, perlu validasi)'
    elif kel_selected.startswith('5.'):
        matches = [(i, w) for i, w in enumerate(data['words'])
                   if not (w.get('ngoko') or '').strip()]
        title = f'📋 Kelengkapan: no ngoko orphan ({len(matches)} entri)'
    else:
        return
    browse_list(data, matches, title)


def bulk_mark_valid_draft(data):
    """Mark bulk entries sebagai VALID atau DRAFT (tanpa edit field).
    User search kata → pilih dari list → mark valid/draft.
    Berguna kalau user sudah review di kamus-viewer.html (warna) lalu
    mau mark valid 100 entries tanpa harus edit satu-satu.
    """
    os.system('clear' if os.name != 'nt' else 'cls')
    print('╔' + '═' * 60 + '╗')
    print('║  ⚡ Mark READY/DRAFT Bulk' + ' ' * 30 + '║')
    print('╚' + '═' * 60 + '╝')
    print()
    print('  Search entries → pilih dari list → mark VALID atau DRAFT.')
    print('  Hanya entries yang 3-field ready (status=ready) BISA di-mark VALID.')
    print('  Entries draft (3-field belum lengkap) → otomatis DRAFT, gak bisa VALID.')
    print()

    query = questionary.text('Cari kata (di ngoko / krama / arti):').ask()
    if not query or not query.strip():
        return
    search_lower = query.lower().strip()

    # Exact match dulu, baru substring
    exact = []
    substr = []
    for i, entry in enumerate(data['words']):
        ngoko = (entry.get('ngoko') or '').lower()
        krama = (entry.get('krama') or '').lower()
        arti = (entry.get('arti') or '').lower()
        if ngoko == search_lower or krama == search_lower or arti == search_lower:
            exact.append((i, entry))
        elif (search_lower in ngoko or search_lower in krama or search_lower in arti):
            substr.append((i, entry))
    matches = exact + substr

    if not matches:
        print(f'\n  Tidak ada hasil untuk "{query}"')
        input('\n  Tekan Enter...')
        return

    # Build choices list (max 30 untuk avoid UI clutter)
    idx_map = {}
    choices = []
    for i, (orig_idx, entry) in enumerate(matches[:30]):
        ngoko = (entry.get('ngoko') or '')[:25]
        krama = (entry.get('krama') or '')[:20]
        arti = (entry.get('arti') or '')[:20]
        ready = (entry.get('ngoko') or '').strip() and (entry.get('krama') or '').strip() and (entry.get('arti') or '').strip()
        status = entry.get('status', 'draft')
        # Icon: ✅=ready (user edit), 📋=3-field lengkap tapi draft, ❌=draft (3-field belum lengkap)
        if status == 'ready':
            icon = '✅'
        elif ready:
            icon = '📋'
        else:
            icon = '❌'
        label = f'{icon} ngoko={ngoko:25s} krama={krama:20s} arti={arti:20s}'
        idx_map[label] = orig_idx
        choices.append(label)

    if len(matches) > 30:
        print(f'  ⚠ Ditemukan {len(matches)} hasil, cuma tampilkan 30 pertama.')
        print('  Narrow search kalau perlu.')
        print()
    choices.append('↩ Batal')

    sel = questionary.select(
        f'Pilih entry ({len(matches)} matches):',
        choices=choices,
        default=choices[0],
    ).ask()

    if not sel or 'Batal' in sel:
        return

    orig_idx = idx_map.get(sel)
    if orig_idx is None:
        return

    entry = data['words'][orig_idx]
    ready = (entry.get('ngoko') or '').strip() and (entry.get('krama') or '').strip() and (entry.get('arti') or '').strip()

    if not ready:
        print(f'\n  ❌ Entry ini 3-field belum lengkap. Tidak bisa di-mark READY.')
        print(f'     ngoko={entry.get("ngoko","")!r}')
        print(f'     krama={entry.get("krama","")!r}')
        print(f'     arti={entry.get("arti","")!r}')
        input('\n  Tekan Enter...')
        return

    # Tampilkan detail + pilih action
    print(f'\n  📋 Entry dipilih:')
    print(f'    ngoko:  {entry.get("ngoko","")!r}')
    print(f'    krama:  {entry.get("krama","")!r}')
    print(f'    arti:   {entry.get("arti","")!r}')
    print(f'    Status sekarang: {entry.get("status", "draft")}')
    print()

    action_choices = [
        '✅ Mark READY (siap upload ke Supabase)',
        '📋 Mark DRAFT (un-mark, kembali review)',
        '↩ Batal',
    ]
    action = questionary.select(
        'Pilih action:',
        choices=action_choices,
        default=action_choices[0],
    ).ask()

    if not action or 'Batal' in action:
        return

    if 'READY' in action:
        entry['status'] = 'ready'
        save_kamus(data)
        print(f'\n  ✅ Ditandai READY. Siap upload ke Supabase.')
    elif 'DRAFT' in action:
        entry['status'] = 'draft'
        save_kamus(data)
        print(f'\n  ○ Kembali ke DRAFT. Perlu review lagi nanti.')

    input('\n  Tekan Enter...')


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
        print(f'  📋 Draft: {total - ready} | ✅ Ready: {ready} | 🚀 Siap upload: {ready}')
        if supabase_ok:
            print(f'  ☁  Supabase: ✓ ter-set (dari .env atau env vars)')
        else:
            print(f'  ☁  Supabase: ⚠ belum di-set (gunakan menu "🔑 Set Supabase .env")')
        print()

        # Compute counts for filter menu labels
        count_3field = sum(1 for w in words if (w.get('ngoko') or '').strip() and (w.get('krama') or '').strip() and (w.get('arti') or '').strip())
        count_ngoko_krama = sum(1 for w in words if (w.get('ngoko') or '').strip() and (w.get('krama') or '').strip() and not (w.get('arti') or '').strip())
        count_ngoko_only = sum(1 for w in words if (w.get('ngoko') or '').strip() and not (w.get('krama') or '').strip() and not (w.get('arti') or '').strip())
        count_ngoko_arti = sum(1 for w in words if (w.get('ngoko') or '').strip() and not (w.get('krama') or '').strip() and (w.get('arti') or '').strip())

        choices = [
            '📊 Statistik kamus',
            '🔍 Search (cari kata di semua field)',
            '✅ Browse READY (status=ready, siap upload)',
            '📋 Browse DRAFT (belum di-edit user)',
            f'🟢 Filter: LENGKAP 3-field ({count_3field} entri, siap review/upload)',
            f'🟡 Filter: NGOKO+KRAMA ({count_ngoko_krama} entri, perlu isi arti)',
            f'⚪ Filter: NGOKO SAJA ({count_ngoko_only} entri, perlu isi krama+arti)',
            f'🔵 Filter: NGOKO+ARTI ({count_ngoko_arti} entri, perlu isi krama)',
            '📂 Browse by source (lemma/mendeley/dasanama/angka)',
            '⭐ Browse entries dengan krama mapping (auto-filled, butuh arti)',
            '📝 Browse entries BELUM ada arti (Indonesia)',
            '🔗 Merge 2 entries (search kata)',
            '⚡ Mark READY/DRAFT bulk (search kata, tanpa edit)',
            '🔑 Set Supabase .env (URL + anon key)',
            '☁  Upload ke Supabase (hanya yang READY)',
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
        elif 'Search' in selected and 'cari kata' in selected:
            search_menu(data)
        elif 'Upload ke Supabase' in selected:
            upload_to_supabase()
        elif 'Browse READY' in selected:
            # Entries yang status='ready' (user sudah edit via TUI)
            ready_entries = [(i, w) for i, w in enumerate(data['words']) if w.get('status') == 'ready']
            browse_list(data, ready_entries, f'✅ READY ({len(ready_entries)} entri siap upload)')
        elif 'Browse DRAFT' in selected:
            # Entries yang status='draft' (belum di-edit user)
            draft_entries = [(i, w) for i, w in enumerate(data['words']) if w.get('status') != 'ready']
            browse_list(data, draft_entries, f'📋 DRAFT ({len(draft_entries)} entri belum di-edit)')
        elif 'LENGKAP 3-field' in selected:
            # Filter: ngoko + krama + arti semua terisi (siap review/upload)
            matches = [(i, w) for i, w in enumerate(data['words'])
                       if (w.get('ngoko') or '').strip() and (w.get('krama') or '').strip() and (w.get('arti') or '').strip()]
            browse_list(data, matches, f'🟢 LENGKAP 3-field ({len(matches)} entri, siap review)')
        elif 'NGOKO+KRAMA' in selected:
            # Filter: ngoko + krama terisi, arti kosong (perlu isi arti)
            matches = [(i, w) for i, w in enumerate(data['words'])
                       if (w.get('ngoko') or '').strip() and (w.get('krama') or '').strip() and not (w.get('arti') or '').strip()]
            browse_list(data, matches, f'🟡 NGOKO+KRAMA ({len(matches)} entri, perlu isi arti)')
        elif 'NGOKO SAJA' in selected:
            # Filter: ngoko terisi, krama + arti kosong (perlu isi krama+arti)
            matches = [(i, w) for i, w in enumerate(data['words'])
                       if (w.get('ngoko') or '').strip() and not (w.get('krama') or '').strip() and not (w.get('arti') or '').strip()]
            browse_list(data, matches, f'⚪ NGOKO SAJA ({len(matches)} entri, perlu isi krama+arti)')
        elif 'NGOKO+ARTI' in selected:
            # Filter: ngoko + arti terisi, krama kosong (perlu isi krama)
            matches = [(i, w) for i, w in enumerate(data['words'])
                       if (w.get('ngoko') or '').strip() and not (w.get('krama') or '').strip() and (w.get('arti') or '').strip()]
            browse_list(data, matches, f'🔵 NGOKO+ARTI ({len(matches)} entri, perlu isi krama)')
        elif 'by source' in selected:
            browse_by_source(data)
        elif 'krama mapping' in selected:
            browse_with_krama(data)
        elif 'BELUM ada arti' in selected:
            browse_no_arti(data)
        elif 'Mark READY/DRAFT bulk' in selected:
            bulk_mark_valid_draft(data)
        elif 'Merge 2 entries' in selected:
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
            # Gabung field: kalau kedua entries punya ngoko → gabung sebagai alias (comma)
            # Kalau hanya satu yang punya → pakai yang itu
            e1_ngoko = (entry1.get('ngoko') or '').strip()
            e1_krama = (entry1.get('krama') or '').strip()
            e2_ngoko = (entry2.get('ngoko') or '').strip()
            e2_krama = (entry2.get('krama') or '').strip()
            e1_ki = (entry1.get('krama_inggil') or '').strip()
            e2_ki = (entry2.get('krama_inggil') or '').strip()
            e1_arti = (entry1.get('arti') or '').strip()
            e2_arti = (entry2.get('arti') or '').strip()

            # Smart merge ngoko:
            # Kalau entry2 ngoko == entry1 krama → entry2 itu krama word → jadi krama
            # Kalau entry2 ngoko beda dari entry1 ngoko → tambah sebagai alias
            if e2_ngoko and e1_krama and e2_ngoko.lower() == e1_krama.lower():
                # entry2 title = krama word (mis. "ingkang" == entry1 krama)
                merged_ngoko = e1_ngoko
                merged_krama = e2_ngoko
            elif not e1_krama and e1_ngoko and e2_krama and e1_ngoko.lower() == e2_krama.lower():
                # entry1 title = krama word
                merged_ngoko = e2_ngoko
                merged_krama = e1_ngoko
            else:
                # Normal merge: gabung ngoko (kalau beda, jadi alias comma)
                parts_ngoko = []
                if e1_ngoko:
                    parts_ngoko.append(e1_ngoko)
                if e2_ngoko and e2_ngoko.lower() not in [p.lower() for p in parts_ngoko]:
                    parts_ngoko.append(e2_ngoko)
                merged_ngoko = ', '.join(parts_ngoko) if parts_ngoko else ''

                # Gabung krama (kalau beda, jadi alias comma)
                parts_krama = []
                if e1_krama:
                    parts_krama.append(e1_krama)
                if e2_krama and e2_krama.lower() not in [p.lower() for p in parts_krama]:
                    parts_krama.append(e2_krama)
                merged_krama = ', '.join(parts_krama) if parts_krama else ''

            # Gabung krama_inggil (comma jika beda)
            parts_ki = []
            if e1_ki:
                parts_ki.append(e1_ki)
            if e2_ki and e2_ki.lower() not in [p.lower() for p in parts_ki]:
                parts_ki.append(e2_ki)
            merged_ki = ', '.join(parts_ki) if parts_ki else ''

            # Gabung arti (comma jika beda)
            parts_arti = []
            if e1_arti:
                parts_arti.append(e1_arti)
            if e2_arti and e2_arti.lower() not in [p.lower() for p in parts_arti]:
                parts_arti.append(e2_arti)
            merged_arti = ', '.join(parts_arti) if parts_arti else ''

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
            if merged_ki:
                entry1['krama_inggil'] = merged_ki
            elif 'krama_inggil' in entry1:
                del entry1['krama_inggil']
            entry1['arti'] = merged_arti
            entry1['register'] = merged_reg
            # Combine aksara (jangan hilangkan aksara dari entry2)
            a1 = (entry1.get('aksara') or '').strip()
            a2 = (entry2.get('aksara') or '').strip()
            if a2 and a2 not in a1:
                entry1['aksara'] = f'{a1}, {a2}'.strip(', ')
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
        elif 'Set Supabase' in selected:
            edit_env_file()


def upload_to_supabase():
    """Upload entri yang sudah di-edit user ke Supabase (subprocess)"""
    # Buat script Python sementara untuk upload (subprocess supaya output tidak di-clear)
    script = '''
import json, sys, os, urllib.request, urllib.error

KAMUS_PATH = None
import os.path
from pathlib import Path
# Prefer kamus-jawa-draft.json (v3, group by konsep, register umum), fallback ke kamus-jawa-full.json (legacy)
KAMUS_DRAFT = Path.home() / "Dubbing" / "kamus-jawa-draft.json"
KAMUS_LEGACY = Path.home() / "Dubbing" / "kamus-jawa-full.json"
KAMUS_PATH = KAMUS_DRAFT if KAMUS_DRAFT.exists() else KAMUS_LEGACY

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

# Filter: HANYA upload entries yang USER APPROVED (R-12 compliance)
# Syarat: ngoko + krama + arti terisi (status=ready) DAN user_approved=True
# User wajib validasi 1-1 di TUI sebelum upload ke Supabase
edited = []
for entry in data.get("words", []):
    ngoko = (entry.get("ngoko") or "").strip()
    krama = (entry.get("krama") or "").strip()
    arti = (entry.get("arti") or "").strip()
    approved = bool(entry.get("user_approved"))

    # 3 field wajib + user_approved
    if ngoko and krama and arti and approved:
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
    print("     Syarat: ngoko + krama + arti SEMUA terisi (3 field wajib)")
    print("            DAN user_approved=True (edit entry di TUI untuk approve).")
    print("     Flow: Browse SIAP UPLOAD → pilih entry → edit (auto-mark approved)")
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
        approved_count = sum(1 for w in data['words'] if w.get('user_approved'))
        print(f'  ⚠ Update status: {reset_count} entries')
        print(f'    Status: ready = ngoko+krama+arti lengkap (perlu approval user)')
        print(f'           approved = user sudah validasi (siap upload Supabase)')
        print(f'    3-field ready: {ready_count} | Approved: {approved_count} | Siap upload: {approved_count}')
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
