#!/usr/bin/env python3
"""
kamus-tui.py v9 — TUI edit kamus Jawa dengan menu pre-built (arrow keys, no jq needed)

User tinggal tab/panah, pilih menu:
  📊 Statistik kamus
  🔍 Search (cari kata)
  📋 Browse semua (pagination)
  ⭐ Browse entri dengan krama mapping (auto-filled)
  📝 Browse entri yang BELUM ada arti
  🎯 Browse per register (ngoko / krama / krama_inggil / kawi / umum)
  📊 Browse per kelengkapan (NETRAL / ngoko-only / paired / lengkap)
  🔍 Deteksi Duplikat (audit, JANGAN hapus, user putuskan)
  ☁  Upload ke Supabase (hanya yang sudah di-mark ready oleh user)
  ❌ Keluar

Edit per entri: ngoko, krama, krama_inggil, arti (Indonesia), register
  - keterangan JAWA read-only (JANGAN HAPUS)
  - register BISA di-edit (dropdown: ngoko/krama/krama_inggil/kawi/umum)
  - R-21: field 'word' otomatis kosong kalau paired (ngoko/krama terisi)
  - R-21: field 'word' terisi hanya untuk entries NETRAL (belum ada ngoko/krama)

Status tracking (R-12 compliance — JANGAN auto-set ready):
  status='draft' = default (belum di-mark ready oleh user)
  status='ready' = user EXPLICIT mark via menu 'Mark READY/DRAFT bulk'
  3-field lengkap (ngoko+krama+arti) TIDAK otomatis = ready

Merge: menu khusus, search kata 1 → search kata 2 → preview → konfirmasi
Upload: HANYA entries dengan status='ready' + 3-field lengkap (R-12)

Install: pip3 install questionary
Usage: python3 kamus-tui.py
"""

import os
import sys
import json
import subprocess
import textwrap
from pathlib import Path

try:
    import questionary
except ImportError:
    print('\n❌ pip3 install questionary')
    sys.exit(1)

# Kamus JSON path — R-22: kamus-jawa-draft.json = SATU-SATUNYA sumber (NETRAL).
# Schema konsep v6.1: {entry_id, word (R-21 netral), ngoko, krama, krama_inggil (R-17 kosong),
#   arti, keterangan, aksara, register, sumber, is_lemma, source_count, status}
# R-22: SEMUA raw files + parser scripts DIHAPUS. JANGAN merujuk raw (sampah parsing AI tolol).
# User fallback kalau nemu kata belum dikenali: https://kesakata.kemdikbud.go.id
KAMUS_PATH = Path.home() / 'Dubbing' / 'kamus-jawa-draft.json'

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
    """Cari kamus JSON di ~/Dubbing/kamus-jawa-draft.json (R-22: sumber tunggal NETRAL).

    R-22 compliance: SEMUA raw files DIHAPUS. Hanya kamus-jawa-draft.json.
    Kalau draft.json tidak ada, return None → load_kamus() tampilkan curl command.
    """
    if KAMUS_PATH.exists():
        return KAMUS_PATH
    return None


def load_kamus():
    """Load kamus-jawa-draft.json (R-22: sumber tunggal NETRAL)."""
    if not KAMUS_PATH.exists():
        print(f'\n❌ Kamus JSON tidak ditemukan: {KAMUS_PATH}')
        print(f'\n   R-22: kamus-jawa-draft.json = satu-satunya sumber (NETRAL).')
        print(f'\n   Download:')
        print(f'   curl -L -o ~/Dubbing/kamus-jawa-draft.json \\')
        print(f'     "https://raw.githubusercontent.com/emailnyamahmud-afk/srt-splitter/main/public/kamus-jawa-draft.json?v=26"')
        return None
    with open(KAMUS_PATH, 'r', encoding='utf-8') as f:
        return json.load(f)


def save_kamus(data):
    """Save ke JSON file + re-number entry_id (urut posisi list).

    R-12 compliance: JANGAN recompute status di sini.
      - status='ready' HANYA lewat menu 'Mark READY/DRAFT bulk' (user EXPLICIT approve).
      - 3-field lengkap TIDAK otomatis = ready.
      - save_kamus() pertahankan status existing (jangan timpa).

    entry_id: urut posisi list (1-indexed). Kalau ada entry di-delete (via merge),
    re-number entry_id 1..N supaya tetap konsisten.
    """
    # R-12: JANGAN auto-set status='ready'.
    # 3-field lengkap TIDAK otomatis = siap upload.
    # User harus EXPLICIT mark ready via menu "Mark READY/DRAFT bulk".
    # save_kamus() hanya pertahankan status existing (jangan recompute).
    # Re-number entry_id (urut posisi list)
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
    has_word = sum(1 for w in words if (w.get('word') or '').strip())
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
    has_word_netral = sum(1 for w in words if (w.get("word") or "").strip() and not (w.get("ngoko") or "").strip() and not (w.get("krama") or "").strip())
    print(f"    0. NETRAL (word+arti, ngoko+krama kosong): {has_word_netral:6d}  (per R-21, user tentukan ngoko/krama)")
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
    word_old = entry.get('word', '')
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

    # Netral indicator (per R-21)
    is_neutral = bool(word_old) and not ngoko_old
    netral_tag = ' [NETRAL — belum terdefinisi]' if is_neutral else ''

    print(f'  ┌─────────────────────────────────────────────┐')
    print(f'  │ entry_id:     #{entry_id}')
    print(f'  │ word:         {word_old[:42] or "(kosong)"}{netral_tag}')
    print(f'  │ ngoko:        {ngoko_old[:42] or "(kosong)"}')
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
    # Phase 6: pakai textwrap.fill() (sebelumnya 12 baris manual word-wrap)
    if ket:
        ket_lines = textwrap.wrap(
            ket, width=52,
            initial_indent='    ', subsequent_indent='    ',
            break_long_words=False, break_on_hyphens=False,
        )
        for kl in ket_lines[:6]:
            print(kl)
        if len(ket_lines) > 6:
            print(f'    ...({len(ket_lines) - 6} baris lagi)')
    print()

    # Edit fields
    print('  Edit (Enter=keep existing, type new value):')
    if is_neutral:
        print('  ⚠ Entry ini NETRAL (belum terdefinisi).')
        print('    - Isi ngoko kalau yakin ini kata ngoko')
        print('    - Isi krama kalau yakin ini kata krama')
        print('    - Isi arti kalau tahu arti Indonesia')
        print('    - Setelah 2 dari 3 terisi (paired), word otomatis kosong saat save')
        print()
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

    # R-21: word otomatis kosong kalau sudah paired (ngoko + krama atau ngoko + arti atau krama + arti)
    # TETAP dipertahankan kalau masih netral (belum ada pasangan)
    has_ng = bool(new_ngoko)
    has_kr = bool(new_krama) or bool(new_ki)
    has_ar = bool(new_arti)
    is_paired = (has_ng and has_kr) or (has_ng and has_ar) or (has_kr and has_ar)
    if is_paired and word_old:
        # User sudah defisini pasangan, word bisa kosong
        entry['word'] = ''
    elif not is_paired and not word_old and not has_ng and not has_kr and not has_ar:
        # Edge case: semua kosong, biarkan word kosong (R-18 tetap simpan entry)
        pass
    # R-12: status='draft' setelah edit. User harus EXPLICIT mark ready via menu.
    # 3-field lengkap TIDAK otomatis = siap upload.
    save_kamus(data)
    # Set status='draft' setelah edit (reset, user harus re-validate)
    entry['status'] = 'draft'
    print(f'\n  ✅ Disimpan: ngoko={new_ngoko} → krama={new_krama} → arti={new_arti}')
    print(f'  Register: {new_register}')
    has_3field = bool(new_ngoko and new_krama and new_arti)
    print(f'  Status: draft (3-field {"lengkap — bisa mark READY via menu" if has_3field else "belum lengkap"})')

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
        # Phase 2: pakai helper _entry_label (R-21: word tampil kalau NETRAL)
        label_to_idx = {}
        choices = []
        for orig_idx, entry in page:
            label, _ = _entry_label(orig_idx, entry)
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
                # Phase 1: search di list saat ini (entries_with_idx), bukan data global
                # Helper _search_entries expects data['words'] — buat mini-data dari list saat ini
                mini_data = {'words': [e for _, e in entries_with_idx]}
                mini_matches = _search_entries(
                    mini_data, search_query,
                    fields=['ngoko', 'krama', 'krama_inggil', 'arti'],
                )
                # Remap mini indices (0..N-1) ke orig_idx dari entries_with_idx
                orig_indices = [orig for orig, _ in entries_with_idx]
                filtered = [(orig_indices[mini_i], e) for mini_i, e in mini_matches]
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


# ============================================================
# Helper functions (Phase 1-2 simplification)
# ============================================================

def _search_entries(data, query, fields=None, exclude_idx=None):
    """Helper: search entries by query di fields tertentu.

    Args:
        data: kamus data dict (punya key 'words')
        query: kata yang dicari (akan di-lowercase + strip)
        fields: list field yang di-search. Default: ngoko, krama, arti (R-21: word opsional).
                Pilihan valid: 'ngoko', 'krama', 'krama_inggil', 'arti', 'word'
        exclude_idx: index yang di-skip (mis. untuk merge, skip entry pertama)

    Returns:
        list (idx, entry) — exact match dulu, substring kemudian.
        Konsisten dengan behavior lama (search_menu, browse_list search, bulk_mark, merge_2).
    """
    if fields is None:
        fields = ['ngoko', 'krama', 'arti']
    q = (query or '').lower().strip()
    if not q:
        return []
    exact, substr = [], []
    for i, e in enumerate(data['words']):
        if exclude_idx is not None and i == exclude_idx:
            continue
        values = [(e.get(f) or '').lower() for f in fields]
        if q in values:
            exact.append((i, e))
        elif any(q in v for v in values):
            substr.append((i, e))
    return exact + substr


def _entry_label(orig_idx, entry):
    """Build label untuk list (R-21: word first kalau NETRAL).

    Format: '{icon} #{eid:5d}. {primary:25s} → {krama:15s} | {arti:15}'
    - icon: ✓=ready, ○=draft
    - primary: word (kalau NETRAL) atau ngoko (kalau paired)
    - krama, arti: tampilkan kalau ada

    Returns:
        (label, orig_idx) — tuple untuk dipakai browse_list.
    """
    word = (entry.get('word', '') or '').strip()
    ngoko = (entry.get('ngoko', '') or '').strip()
    kr = (entry.get('krama', '') or '').strip()
    ar = (entry.get('arti', '') or '').strip()
    ki = (entry.get('krama_inggil', '') or '').strip()
    reg = (entry.get('register', 'umum') or 'umum').strip()
    eid = entry.get('entry_id', orig_idx + 1)
    icon = '✓' if entry.get('status') == 'ready' else '○'

    # R-21: word first kalau NETRAL (belum terdefinisi)
    primary = word if (word and not ngoko) else ngoko
    label = f'{icon} #{eid:5d}. {(primary or "?")[:25]:25s}'
    if kr:
        label += f' → {kr[:15]:15s}'
    if ki:
        label += f' | ki: {ki[:10]}'
    if ar:
        label += f' | {ar[:15]}'
    if reg != 'umum':
        label += f' [{reg}]'
    return label, orig_idx


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

    # Phase 1: pakai helper _search_entries (fields: ngoko, krama, krama_inggil, arti)
    matches = _search_entries(
        data, query,
        fields=['ngoko', 'krama', 'krama_inggil', 'arti'],
    )

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
      0. NETRAL (word+arti, ngoko+krama kosong) — per R-21, mayoritas entries
      1. ngoko saja (perlu krama + arti)
      2. ngoko + krama (perlu arti)
      3. ngoko + arti (no krama) (perlu krama)
      4. ngoko + krama + arti (3-field ready, perlu validasi)
      5. no ngoko (orphan krama-only)
    """
    kel_choices = [
        '0. ⚠ NETRAL (word+arti, ngoko+krama kosong — user tentukan ngoko/krama)',
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
    if kel_selected.startswith('0.'):
        # R-21: NETRAL entries (word terisi, ngoko+krama kosong, arti boleh terisi)
        matches = [(i, w) for i, w in enumerate(data['words'])
                   if (w.get('word') or '').strip()
                   and not (w.get('ngoko') or '').strip()
                   and not (w.get('krama') or '').strip()]
        title = f'⚠ Kelengkapan: NETRAL ({len(matches)} entri, user tentukan ngoko/krama)'
    elif kel_selected.startswith('1.'):
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

    # Phase 1: pakai helper _search_entries (default fields: ngoko, krama, arti)
    matches = _search_entries(data, query)

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


def merge_2_entries(data):
    """Merge 2 entries terpisah jadi 1 entry. Per Phase 4 — extract dari main_menu.

    Flow:
      1. Search entry pertama (cari kata)
      2. Search entry kedua (skip entry pertama)
      3. Preview hasil merge (smart ngoko/krama detection, gabung krama_inggil/arti comma)
      4. Konfirmasi → apply (simpan ke entry1, delete entry2, re-number entry_id)

    R-18 compliance: aksara + keterangan + sumber dari entry2 dipertahankan
    (dipindah ke entry1, bukan dihapus).

    R-21 compliance: word field TIDAK di-merge — pasca netral, word hanya untuk
    entries NETRAL. Entry1 + entry2 paired → word tetap kosong di hasil.
    """
    print('\n  ═══ MERGE 2 ENTRIES ═══')
    print('  Gabung 2 entries terpisah jadi 1 entry.')
    print('  Contoh: sing (entry terpisah) + ingkang (entry terpisah)')
    print('          → 1 entry: ngoko=sing, krama=ingkang, arti=yang')
    print()

    # Step 1: Search entry pertama
    q1 = questionary.text('1. Cari kata pertama (mis. "sing"):').ask()
    if not q1 or not q1.strip():
        return
    # Phase 1: pakai helper (fields: ngoko, krama only — merge tidak search arti/ki)
    m1 = _search_entries(data, q1, fields=['ngoko', 'krama'])
    if not m1:
        print(f'  ❌ Tidak ada hasil untuk "{q1}"')
        input('  Tekan Enter...')
        return

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
        return
    idx1 = idx_map1.get(sel1)
    if idx1 is None:
        return

    entry1 = data['words'][idx1]
    eid1 = entry1.get('entry_id', '?')
    print(f'\n  Entry 1: ngoko={entry1.get("ngoko","")!r} krama={entry1.get("krama","")!r} arti={entry1.get("arti","")!r}')

    # Step 2: Search entry kedua (skip entry pertama)
    q2 = questionary.text('\n2. Cari kata kedua (mis. "ingkang"):').ask()
    if not q2 or not q2.strip():
        return
    # Phase 1: pakai helper dengan exclude_idx=idx1
    m2 = _search_entries(data, q2, fields=['ngoko', 'krama'], exclude_idx=idx1)
    if not m2:
        print(f'  ❌ Tidak ada hasil untuk "{q2}"')
        input('  Tekan Enter...')
        return

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
        return
    idx2 = idx_map2.get(sel2)
    if idx2 is None:
        return

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
        return

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


def _show_cross_field(cross_dict, field1, field2):
    """Tampilkan cross-field duplikat — kata di field1 entry A = field2 entry B (beda entry).

    Pure detection: tunjukin fakta, BUKAN filter "valid" / "halu" / "bug".
    User baca konteks, putuskan manual (R-18: jangan hapus otomatis).
    """
    print(f'\n  Cross-field {field1}↔{field2} (kata di {field1} entry A = {field2} entry B, beda entry)')
    print(f'  Total: {len(cross_dict)} tokens')
    print()
    if not cross_dict:
        input('\n  Tekan Enter untuk kembali...')
        return
    # Sort by total entries (e1 + e2) terbanyak
    sorted_cross = sorted(cross_dict.items(),
                         key=lambda x: len(x[1][0]) + len(x[1][1]),
                         reverse=True)
    for token, (e1, e2) in sorted_cross[:50]:
        print(f"\n  '{token}' muncul di {field1} ({len(e1)} entries) dan {field2} ({len(e2)} entries):")
        for e in e1[:3]:
            print(f"    {field1:6} [{e[1]}] arti={e[2][:30]!r}")
        if len(e1) > 3:
            print(f"    ... +{len(e1) - 3} more di {field1}")
        for e in e2[:3]:
            print(f"    {field2:6} [{e[1]}] arti={e[2][:30]!r}")
        if len(e2) > 3:
            print(f"    ... +{len(e2) - 3} more di {field2}")
    print(f'\n  Total {field1}↔{field2}: {len(cross_dict)} tokens')
    print(f'  ⚠ JANGAN HAPUS otomatis. User baca konteks, edit manual via TUI.')
    input('\n  Tekan Enter untuk kembali...')


def detect_duplicates(data):
    """Deteksi duplikat di kamus — JANGAN HAPUS, hanya tunjukin ke user.

    User lihat duplikat, baca konteks, putuskan manual:
    - Sinonim valid? → biarkan
    - Sinonim salah (kita di arti='kamu')? → user edit/hapus token manual
    - Perlu merge? → user pakai menu Merge 2 entries

    Duplikat yang dideteksi:
    1. ngoko: kata yang sama muncul di ngoko multiple entries
    2. krama: kata yang sama muncul di krama multiple entries
    3. word: kata yang sama muncul di word multiple entries (NETRAL)
    4. cross-field: kata di ngoko entry A = krama entry B
    """
    from collections import defaultdict

    words = data['words']
    os.system('clear' if os.name != 'nt' else 'cls')
    print('╔' + '═' * 60 + '╗')
    print('║  🔍 Deteksi Duplikat (JANGAN HAPUS — user putuskan)' + ' ' * 6 + '║')
    print('╚' + '═' * 60 + '╝')
    print()
    print('  ⚠ Duplikat = JANGAN HAPUS otomatis (R-18).')
    print('  User baca konteks, putuskan manual:')
    print('    - Sinonim valid? → biarkan')
    print('    - Sinonim salah? → edit entry, hapus token')
    print('    - Perlu merge? → pakai menu Merge 2 entries')
    print()

    # Build index untuk semua field (ngoko, krama, arti, word)
    ngoko_idx = defaultdict(list)
    krama_idx = defaultdict(list)
    word_idx = defaultdict(list)
    arti_idx = defaultdict(list)

    for i, k in enumerate(words):
        ng = (k.get('ngoko', '') or '').strip().lower()
        kr = (k.get('krama', '') or '').strip().lower()
        word = (k.get('word', '') or '').strip().lower()
        ar = (k.get('arti', '') or '').strip().lower()
        ar_raw = (k.get('arti', '') or '').strip()[:60]  # Original case untuk display
        ket = (k.get('keterangan', '') or '').strip()[:60]
        eid = k.get('entry_id', '?')

        for t in ng.split(','):
            t = t.strip()
            if t and len(t) > 1:
                ngoko_idx[t].append((i, eid, ar_raw, ket))
        for t in kr.split(','):
            t = t.strip()
            if t and len(t) > 1:
                krama_idx[t].append((i, eid, ar_raw, ket))
        for t in word.split(','):
            t = t.strip()
            if t and len(t) > 1:
                word_idx[t].append((i, eid, ar_raw, ket))
        for t in ar.split(','):
            t = t.strip()
            if t and len(t) > 1:
                arti_idx[t].append((i, eid, ar_raw, ket))

    # Find dupes (kata sama di field yang sama, beda entry)
    dupes_ngoko = {t: v for t, v in ngoko_idx.items() if len(v) > 1}
    dupes_krama = {t: v for t, v in krama_idx.items() if len(v) > 1}
    dupes_word = {t: v for t, v in word_idx.items() if len(v) > 1}
    dupes_arti = {t: v for t, v in arti_idx.items() if len(v) > 1}

    # Cross-field helper: cari kata di idx1 yang juga ada di idx2 di entry beda
    def find_cross(idx1, idx2):
        cross = {}
        for t in idx1:
            if t in idx2:
                e1 = idx1[t]
                e2 = idx2[t]
                has_cross = False
                for a in e1:
                    for b in e2:
                        if a[0] != b[0]:
                            has_cross = True
                            break
                    if has_cross:
                        break
                if has_cross:
                    cross[t] = (e1, e2)
        return cross

    # All cross-field pairs (lintas definisi)
    cross_ng_kr = find_cross(ngoko_idx, krama_idx)
    cross_ng_ar = find_cross(ngoko_idx, arti_idx)
    cross_kr_ar = find_cross(krama_idx, arti_idx)
    cross_word_ng = find_cross(word_idx, ngoko_idx)
    cross_word_kr = find_cross(word_idx, krama_idx)
    cross_word_ar = find_cross(word_idx, arti_idx)

    total_cross = (len(cross_ng_kr) + len(cross_ng_ar) + len(cross_kr_ar) +
                   len(cross_word_ng) + len(cross_word_kr) + len(cross_word_ar))

    print(f'  📊 Duplikat ngoko (kata sama di ngoko, beda entry): {len(dupes_ngoko):>5} tokens')
    print(f'  📊 Duplikat krama (kata sama di krama, beda entry): {len(dupes_krama):>5} tokens')
    print(f'  📊 Duplikat word  (kata sama di word, beda entry):   {len(dupes_word):>5} tokens')
    print(f'  📊 Duplikat arti  (kata sama di arti, beda entry):  {len(dupes_arti):>5} tokens')
    print()
    print(f'  📊 Cross-field lintas definisi (total: {total_cross} tokens):')
    print(f'     ngoko↔krama:  {len(cross_ng_kr):>5} tokens')
    print(f'     ngoko↔arti:   {len(cross_ng_ar):>5} tokens')
    print(f'     krama↔arti:   {len(cross_kr_ar):>5} tokens')
    print(f'     word↔ngoko:   {len(cross_word_ng):>5} tokens (NETRAL duplikat di paired entry)')
    print(f'     word↔krama:  {len(cross_word_kr):>5} tokens (NETRAL duplikat di paired entry)')
    print(f'     word↔arti:   {len(cross_word_ar):>5} tokens (NETRAL duplikat di paired entry)')
    print()

    # Pilih kategori
    cat_choices = [
        f'1. Duplikat ngoko ({len(dupes_ngoko)} tokens)',
        f'2. Duplikat krama ({len(dupes_krama)} tokens)',
        f'3. Duplikat word ({len(dupes_word)} tokens)',
        f'4. Duplikat arti ({len(dupes_arti)} tokens)',
        f'5. Cross-field ngoko↔krama ({len(cross_ng_kr)} tokens)',
        f'6. Cross-field ngoko↔arti ({len(cross_ng_ar)} tokens)',
        f'7. Cross-field krama↔arti ({len(cross_kr_ar)} tokens)',
        f'8. Cross-field word↔ngoko/krama/arti ({len(cross_word_ng)+len(cross_word_kr)+len(cross_word_ar)} tokens, NETRAL duplikat)',
        '↩ Kembali',
    ]
    cat_sel = questionary.select('Pilih kategori duplikat:', choices=cat_choices, default=cat_choices[0]).ask()
    if not cat_sel or 'Kembali' in cat_sel:
        return

    # Tampilkan duplikat terpilih
    if cat_sel.startswith('1.'):
        dupes = dupes_ngoko
        field_name = 'ngoko'
    elif cat_sel.startswith('2.'):
        dupes = dupes_krama
        field_name = 'krama'
    elif cat_sel.startswith('3.'):
        dupes = dupes_word
        field_name = 'word'
    elif cat_sel.startswith('4.'):
        dupes = dupes_arti
        field_name = 'arti'
    elif cat_sel.startswith('5.'):
        _show_cross_field(cross_ng_kr, 'ngoko', 'krama')
        return
    elif cat_sel.startswith('6.'):
        _show_cross_field(cross_ng_ar, 'ngoko', 'arti')
        return
    elif cat_sel.startswith('7.'):
        _show_cross_field(cross_kr_ar, 'krama', 'arti')
        return
    elif cat_sel.startswith('8.'):
        # NETRAL duplikat di paired entry — gabung 3 pasangan
        print(f'\n  Cross-field word↔ngoko/krama/arti (NETRAL duplikat di paired entry)')
        print(f'  NETRAL = field "word" di JSON lokal (entry belum terdefinisi register)')
        print(f'  Pasangan: word↔ngoko ({len(cross_word_ng)}), word↔krama ({len(cross_word_kr)}), word↔arti ({len(cross_word_ar)})')
        print()
        combined = {}
        for token, (w_e, ng_e) in cross_word_ng.items():
            combined.setdefault(token, []).extend([('word', x) for x in w_e] + [('ngoko', x) for x in ng_e])
        for token, (w_e, kr_e) in cross_word_kr.items():
            combined.setdefault(token, []).extend([('word', x) for x in w_e] + [('krama', x) for x in kr_e])
        for token, (w_e, ar_e) in cross_word_ar.items():
            combined.setdefault(token, []).extend([('word', x) for x in w_e] + [('arti', x) for x in ar_e])
        sorted_comb = sorted(combined.items(), key=lambda x: len(set(e[1][0] for e in x[1])), reverse=True)
        for token, occ in sorted_comb[:50]:
            unique_entries = set(e[1][0] for e in occ)
            print(f"\n  '{token}' muncul di {len(unique_entries)} entries:")
            for field, (idx, eid, ar, ket) in occ[:6]:
                print(f"    {field:6} [{eid}] arti={ar[:30]!r}")
            if len(occ) > 6:
                print(f"    ... +{len(occ) - 6} more")
        print(f"\n  Total: {len(combined)} tokens")
        print(f'  ⚠ JANGAN HAPUS otomatis. User baca konteks, edit manual via TUI.')
        input('\n  Tekan Enter untuk kembali...')
        return

    # Tampilkan duplikat (sorted by jumlah entries terbanyak)
    sorted_dupes = sorted(dupes.items(), key=lambda x: len(x[1]), reverse=True)

    # Build list untuk browse
    print(f'\n  Menampilkan {min(50, len(sorted_dupes))} duplikat {field_name} teratas (dari {len(sorted_dupes)} total):')
    print()

    for token, entries in sorted_dupes[:50]:
        print(f"\n  '{token}' muncul di {len(entries)} entries:")
        for idx, eid, ar, ket in entries[:5]:
            print(f"    [{eid}] arti={ar[:30]!r}  ket={ket!r}")
        if len(entries) > 5:
            print(f"    ... +{len(entries) - 5} more")

    print(f"\n  Total duplikat {field_name}: {len(sorted_dupes)} tokens")
    print(f"  ⚠ JANGAN HAPUS otomatis. User baca konteks, edit manual via TUI.")
    input('\n  Tekan Enter untuk kembali...')


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
        print('║  📖 Kamus Jawa Editor (TUI v9)' + ' ' * 28 + '║')
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
        # R-21: NETRAL = word terisi (Jawa), ngoko+krama kosong (arti boleh terisi = ID)
        count_netral = sum(1 for w in words if (w.get('word') or '').strip() and not (w.get('ngoko') or '').strip() and not (w.get('krama') or '').strip())
        count_3field = sum(1 for w in words if (w.get('ngoko') or '').strip() and (w.get('krama') or '').strip() and (w.get('arti') or '').strip())
        count_ngoko_krama = sum(1 for w in words if (w.get('ngoko') or '').strip() and (w.get('krama') or '').strip() and not (w.get('arti') or '').strip())
        count_ngoko_only = sum(1 for w in words if (w.get('ngoko') or '').strip() and not (w.get('krama') or '').strip() and not (w.get('arti') or '').strip())
        count_ngoko_arti = sum(1 for w in words if (w.get('ngoko') or '').strip() and not (w.get('krama') or '').strip() and (w.get('arti') or '').strip())

        choices = [
            '📊 Statistik kamus',
            '🔍 Search (cari kata di semua field)',
            '✅ Browse READY (status=ready, siap upload)',
            '📋 Browse DRAFT (belum di-edit user)',
            f'⚠ Filter: NETRAL ({count_netral} entri, word+arti, ngoko+krama kosong — user tentukan — R-21)',
            f'🟢 Filter: LENGKAP 3-field ({count_3field} entri, siap review/upload)',
            f'🟡 Filter: NGOKO+KRAMA ({count_ngoko_krama} entri, perlu isi arti)',
            f'⚪ Filter: NGOKO SAJA ({count_ngoko_only} entri, perlu isi krama+arti)',
            f'🔵 Filter: NGOKO+ARTI ({count_ngoko_arti} entri, perlu isi krama)',
            '📂 Browse by source (lemma/mendeley/dasanama/angka)',
            '⭐ Browse entries dengan krama mapping (auto-filled, butuh arti)',
            '📝 Browse entries BELUM ada arti (Indonesia)',
            '🔗 Merge 2 entries (search kata)',
            '🔍 Deteksi duplikat (JANGAN HAPUS, user putuskan)',
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
        elif 'Filter: NETRAL' in selected:
            # R-21: NETRAL = word terisi (Jawa), ngoko+krama kosong (arti boleh terisi = ID)
            matches = [(i, w) for i, w in enumerate(data['words'])
                       if (w.get('word') or '').strip()
                       and not (w.get('ngoko') or '').strip()
                       and not (w.get('krama') or '').strip()]
            browse_list(data, matches, f'⚠ NETRAL ({len(matches)} entri, word+arti, ngoko+krama kosong — R-21)')
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
            # Phase 4: extract ke fungsi merge_2_entries() (line 785-984)
            merge_2_entries(data)
        elif 'Deteksi duplikat' in selected:
            detect_duplicates(data)
        elif 'Set Supabase' in selected:
            edit_env_file()


def upload_to_supabase():
    """Upload entri yang sudah di-edit user ke Supabase.

    Phase 5: logic upload dipindah ke scripts/upload-supabase.py (file terpisah).
    Fungsi ini sekarang jadi wrapper: cari file upload-supabase.py, jalankan
    sebagai subprocess supaya output tidak di-clear oleh TUI.

    Lokasi search:
      1. Sama dengan kamus-tui.py (recommended — user download bareng)
      2. ~/Dubbing/upload-supabase.py (kalau user download ke Dubbing/)

    Fallback kalau file tidak ditemukan: tampilkan pesan error + URL download.
    """
    # Cari file upload-supabase.py
    here = Path(__file__).parent / 'upload-supabase.py'
    dubbing = Path.home() / 'Dubbing' / 'upload-supabase.py'

    if here.exists():
        script_path = here
    elif dubbing.exists():
        script_path = dubbing
    else:
        print('\n  ❌ upload-supabase.py tidak ditemukan.')
        print(f'     Looked at:')
        print(f'       {here}')
        print(f'       {dubbing}')
        print()
        print('  Download dari GitHub:')
        print('  curl -L -o upload-supabase.py \\')
        print('    "https://raw.githubusercontent.com/emailnyamahmud-afk/srt-splitter/main/scripts/upload-supabase.py?v=2"')
        input('\n  Tekan Enter...')
        return

    # Jalankan sebagai subprocess
    subprocess.run([sys.executable, str(script_path)])


def main():
    os.system('clear' if os.name != 'nt' else 'cls')
    print('╔' + '═' * 60 + '╗')
    print('║  📖 Kamus Jawa Editor (TUI v9)' + ' ' * 28 + '║')
    print('║  Menu pre-built — arrow keys, no jq needed' + ' ' * 17 + '║')
    print('╚' + '═' * 60 + '╝')
    print()

    data = load_kamus()
    if not data:
        sys.exit(1)

    # Phase 6 + R-12 fix: read-only status check (JANGAN auto-save, JANGAN auto-ready)
    # 3-field lengkap TIDAK otomatis = ready. User harus EXPLICIT mark ready.
    ready_count = sum(
        1 for w in data['words']
        if (w.get('ngoko') or '').strip()
        and (w.get('krama') or '').strip()
        and (w.get('arti') or '').strip()
    )
    status_ready = sum(1 for w in data['words'] if w.get('status') == 'ready')
    # R-12: status='ready' HANYA dari user explicit mark via menu "Mark READY/DRAFT bulk"
    # 3-field lengkap = PERSYARATAN untuk ready, tapi bukan otomatis ready
    # R-21: NETRAL = word terisi (Jawa), ngoko+krama kosong (arti boleh terisi = ID)
    netral_count = sum(
        1 for w in data['words']
        if (w.get('word') or '').strip()
        and not (w.get('ngoko') or '').strip()
        and not (w.get('krama') or '').strip()
    )

    if ready_count != status_ready:
        # 3-field lengkap ≠ ready. User harus explicit mark ready.
        print(f'  ℹ {ready_count:,} entries 3-field lengkap, {status_ready} marked ready (user approved)')
        print(f'    3-field lengkap ≠ siap upload. User harus mark READY via menu.')
        print()
    print(f'  📊 Total: {len(data["words"]):,} | NETRAL: {netral_count:,} | 3-field: {ready_count:,} | Approved: {status_ready}')
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
