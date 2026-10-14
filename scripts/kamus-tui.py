#!/usr/bin/env python3
"""
kamus-tui.py v9 — TUI edit kamus Jawa dengan menu pre-built (arrow keys, no jq needed)

User tinggal tab/panah, pilih menu:
  📊 Statistik kamus
  🔍 Search (cari kata)
  📋 Browse semua (pagination)
  ⭐ Browse entri dengan krama mapping (auto-filled)
  📝 Browse entri yang BELUM ada indo
  📊 Browse per kelengkapan (NETRAL / ngoko-only / paired / lengkap)
  🔍 Deteksi Duplikat (audit, JANGAN hapus, user putuskan)
  ☁  Upload ke Supabase (hanya yang sudah di-mark ready oleh user)
  ❌ Keluar

Edit per entri: ngoko, krama, indo
  - keterangan JAWA read-only (JANGAN HAPUS)
  - R-21: field 'word' otomatis kosong kalau paired (ngoko/krama terisi)
  - R-21: field 'word' terisi hanya untuk entries NETRAL (belum ada ngoko/krama)

Status tracking (R-12 compliance — JANGAN auto-set ready):
  status='draft' = default (belum di-mark ready oleh user)
  status='ready' = user EXPLICIT mark via menu 'Mark READY/DRAFT bulk'
  3-field lengkap (ngoko+krama+indo) TIDAK otomatis = ready

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

# Kamus JSON path — R-22: kamus-jawa-draft.json = sumber utama NETRAL.
# R-26: 20 field per entry (drop register + krama_inggil).
# Schema v2.7 (10 Okt 2026): {entry_id, word (R-21 netral), ngoko, krama, arti,
#   keterangan, aksara, sumber, is_lemma, is_mendeley, is_dasanama, is_angka,
#   is_lampiran, kelas, kelas_nama, lemma_words, mendeley_id, dasanama_count,
#   source_count, status}
# R-22: SEMUA raw files + parser scripts DIHAPUS. JANGAN merujuk raw (sampah parsing AI tolol).
# User fallback kalau nemu kata belum dikenali: https://kesakata.kemdikbud.go.id
KAMUS_PATH = Path.home() / 'Dubbing' / 'kamus-jawa-draft.json'

# Multiple source files — user bisa pilih kerja dari subset mana.
# Default = kamus-jawa-draft.json (44.005 entries, semua sumber campur).
# Opsi lain = subset PURE per sumber, lebih bersih, kerja bertahap.
KAMUS_SOURCES = {
    'unified': {
        'path': Path.home() / 'Dubbing' / 'kamus_unified.json',
        'label': 'kamus_unified.json (46.929 entries — jv + mendeley + dasanama + lemma + lampiran + angka)',
        'desc': 'Kamus UTAMA — jv.wiktionary XML + mendeley + dasanama PURE + lemma PURE + lampiran PURE + angka PURE. 1 konsep = 1 entry. Skip kamus draft merged (sampah AI). Source paling lengkap + bersih.',
        'url': 'https://raw.githubusercontent.com/emailnyamahmud-afk/srt-splitter/main/public/kamus_unified.json?t=CMD_TIMESTAMP',
    },
}

# Default source: 'unified' (kamus UTAMA — jv + mendeley + dasanama + lemma + lampiran + angka).
# Bisa di-switch di runtime via menu "📂 Switch source JSON".
CURRENT_SOURCE = 'unified'

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
    """Cari kamus JSON aktif (CURRENT_SOURCE). Bisa draft atau mendeley subset.

    Return None kalau file tidak ada → load_kamus() tampilkan curl command.
    """
    src = KAMUS_SOURCES.get(CURRENT_SOURCE)
    if src and src['path'].exists():
        return src['path']
    return None


def select_kamus_source():
    """Menu pilih source JSON. User bisa switch antara kamus-jawa-draft.json
    (44.005 entries campur) dan kamus_mendeley.json (145 PURE mendeley).
    """
    global CURRENT_SOURCE
    os.system('clear' if os.name != 'nt' else 'cls')
    print('╔' + '═' * 60 + '╗')
    print('║  📂 Pilih Source Kamus JSON' + ' ' * 30 + '║')
    print('╚' + '═' * 60 + '╝')
    print()

    # Tampilkan status tiap source
    for key, src in KAMUS_SOURCES.items():
        path = src['path']
        exists = '✓ ada' if path.exists() else '✗ belum download'
        active = ' [ACTIVE]' if key == CURRENT_SOURCE else ''
        print(f'  {key:10} {exists:18} {src["label"]}{active}')
        print(f'             {src["desc"][:80]}')
        print()
        if not path.exists():
            # Tampilkan curl command
            url = src['url'].replace('CMD_TIMESTAMP', '$(date +%s)')
            print(f'             curl -L -H "Cache-Control: no-cache" -o {path.name} \\')
            print(f'               "{url}"')
            print()

    # Pilih source
    choices = []
    for key, src in KAMUS_SOURCES.items():
        marker = '✓' if key == CURRENT_SOURCE else ' '
        path = src['path']
        exists = 'ada' if path.exists() else 'BELUM DOWNLOAD'
        choices.append(f'{marker} {key:10} ({exists}) — {src["label"][:50]}')
    choices.append('↩ Kembali')

    sel = questionary.select('Pilih source (aktif ditandai ✓):', choices=choices, default=choices[0]).ask()
    if not sel or 'Kembali' in sel:
        return False

    # Parse selection
    for key in KAMUS_SOURCES:
        if sel.startswith(f'✓ {key}') or sel.startswith(f'  {key}') or sel.startswith(f' {key}'):
            if key != CURRENT_SOURCE:
                CURRENT_SOURCE = key
                print(f'\n  ✅ Source di-switch ke: {key}')
                print(f'     {KAMUS_SOURCES[key]["label"]}')
                input('\n  Tekan Enter...')
                return True  # signal reload needed
            return False
    return False


def load_kamus():
    """Load kamus JSON aktif (CURRENT_SOURCE)."""
    path = get_kamus_path()
    if not path:
        src = KAMUS_SOURCES.get(CURRENT_SOURCE, {})
        url = src.get('url', '').replace('CMD_TIMESTAMP', '$(date +%s)')
        print(f'\n❌ Kamus JSON tidak ditemukan: {src.get("path", KAMUS_PATH)}')
        print(f'\n   Source: {CURRENT_SOURCE}')
        print(f'\n   Download:')
        print(f'   curl -L -H "Cache-Control: no-cache" -o {src.get("path", KAMUS_PATH).name} \\')
        print(f'     "{url}"')
        return None
    with open(path, 'r', encoding='utf-8') as f:
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

    from collections import Counter
    # Status
    status_count = Counter(w.get('status', 'draft') for w in words)
    ready_count = status_count.get('ready', 0)
    draft_count = status_count.get('draft', 0)

    # Komposisi kelengkapan field (prioritas kerja user)
    has_word = sum(1 for w in words if (w.get('word') or '').strip())
    ngoko_only = sum(1 for w in words if (w.get('ngoko') or '').strip() and not (w.get('krama') or '').strip() and not (w.get('indo') or '').strip())
    ngoko_krama = sum(1 for w in words if (w.get('ngoko') or '').strip() and (w.get('krama') or '').strip() and not (w.get('indo') or '').strip())
    ngoko_arti_no_krama = sum(1 for w in words if (w.get('ngoko') or '').strip() and not (w.get('krama') or '').strip() and (w.get('indo') or '').strip())
    ngoko_krama_arti = sum(1 for w in words if (w.get('ngoko') or '').strip() and (w.get('krama') or '').strip() and (w.get('indo') or '').strip())
    no_ngoko = sum(1 for w in words if not (w.get('ngoko') or '').strip())

    # Mapping stats (detail) — for Reference
    with_krama = sum(1 for w in words if (w.get('krama') or '').strip())
    with_arti = sum(1 for w in words if (w.get('indo') or '').strip())
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
    print(f"    0. NETRAL (word+indo, ngoko+krama kosong): {has_word_netral:6d}  (per R-21, user tentukan ngoko/krama)")
    print(f'    1. ngoko saja:               {ngoko_only:6d}  (perlu krama + indo)')
    print(f'    2. ngoko + krama:              {ngoko_krama:6d}  (perlu indo)')
    print(f'    3. ngoko + indo (no krama):    {ngoko_arti_no_krama:6d}  (perlu krama)')
    print(f'    4. ngoko + krama + indo:       {ngoko_krama_arti:6d}  (3-field lengkap)')
    print(f'    5. no ngoko (orphan):         {no_ngoko:6d}  (krama-only, kawi)')
    print()
    print('  Status (patokan valid — pakai field status):')
    print(f'    📋 DRAFT (belum di-edit user):      {draft_count:6d}  (default dari build)')
    print(f'    ✅ READY (user sudah edit via TUI):  {ready_count:6d}  🚀 (siap upload Supabase)')
    print()
    print('  Mapping stats (detail):')
    print(f'    ngoko + krama (auto-filled):    {both_ngoko_krama:6d}  ⭐ (dari template Wikisastra)')
    print(f'    krama filled (total):           {with_krama:6d}')
    print(f'    indo filled:        {with_arti:6d}  ⭐ (user edit manual)')
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
    """Edit 1 entry: ngoko, krama, arti (3-bahasa). word = NETRAL."""
    entry = data['words'][idx]
    entry_id = entry.get('entry_id', idx + 1)
    word_old = entry.get('word', '')
    ngoko_old = entry.get('ngoko', '')
    krama_old = entry.get('krama', '')
    arti_old = entry.get('indo', '')
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
    print(f'  │ indo:     {arti_old[:42] or "(kosong)"}')
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
    new_arti = questionary.text('  indo:', default=arti_old).ask()

    if new_ngoko is None or new_krama is None or new_arti is None:
        print('\n  ⏹ Dibatalkan.')
        input('  Tekan Enter...')
        return

    # Strip
    new_ngoko = (new_ngoko or '').strip()
    new_krama = (new_krama or '').strip()
    new_arti = (new_arti or '').strip()
    # Cek perubahan
    changed = (
        new_ngoko != ngoko_old or
        new_krama != krama_old or
        new_arti != arti_old
    )

    if not changed:
        print('\n  (tidak ada perubahan)')
        input('\n  Tekan Enter...')
        return

    # Update entry
    entry['ngoko'] = new_ngoko
    entry['krama'] = new_krama
    entry['indo'] = new_arti

    # R-21: word otomatis kosong kalau sudah paired (ngoko + krama atau ngoko + arti atau krama + arti)
    # TETAP dipertahankan kalau masih netral (belum ada pasangan)
    has_ng = bool(new_ngoko)
    has_kr = bool(new_krama)
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
                    fields=['ngoko', 'krama', 'indo'],
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
                Pilihan valid: 'ngoko', 'krama', 'indo', 'word'
        exclude_idx: index yang di-skip (mis. untuk merge, skip entry pertama)

    Returns:
        list (idx, entry) — exact match dulu, substring kemudian.
        Konsisten dengan behavior lama (search_menu, browse_list search, bulk_mark, merge_2).
    """
    if fields is None:
        fields = ['ngoko', 'krama', 'indo']
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
    ar = (entry.get('indo', '') or '').strip()
    eid = entry.get('entry_id', orig_idx + 1)
    icon = '✓' if entry.get('status') == 'ready' else '○'

    # R-21: word first kalau NETRAL (belum terdefinisi)
    primary = word if (word and not ngoko) else ngoko
    label = f'{icon} #{eid:5d}. {(primary or "?")[:25]:25s}'
    if kr:
        label += f' → {kr[:15]:15s}'
    if ar:
        label += f' | {ar[:15]}'
    return label, orig_idx


def search_menu(data):
    """Search kamus — exact match dulu, baru substring. Hanya di ngoko/krama/arti."""
    os.system('clear' if os.name != 'nt' else 'cls')
    print('╔' + '═' * 60 + '╗')
    print('║  🔍 Search Kamus' + ' ' * 44 + '║')
    print('╚' + '═' * 60 + '╝')
    print()

    query = questionary.text('Cari kata (di ngoko / krama / arti):').ask()
    if not query:
        return

    # Phase 1: pakai helper _search_entries (fields: ngoko, krama, arti)
    matches = _search_entries(
        data, query,
        fields=['ngoko', 'krama', 'indo'],
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
    matches = [(i, w) for i, w in enumerate(data['words']) if not (w.get('indo') or '').strip()]
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
      0. NETRAL (word+indo, ngoko+krama kosong) — per R-21, mayoritas entries
      1. ngoko saja (perlu krama + indo)
      2. ngoko + krama (perlu indo)
      3. ngoko + indo (no krama) (perlu krama)
      4. ngoko + krama + indo (3-field ready, perlu validasi)
      5. no ngoko (orphan krama-only)
    """
    kel_choices = [
        '0. ⚠ NETRAL (word+indo, ngoko+krama kosong — user tentukan ngoko/krama)',
        '1. ngoko saja (perlu krama + indo)',
        '2. ngoko + krama (perlu indo)',
        '3. ngoko + arti (no krama, perlu krama)',
        '4. ngoko + krama + indo (3-field ready, perlu validasi)',
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
                   and not (w.get('indo') or '').strip()]
        title = f'📋 Kelengkapan: ngoko saja ({len(matches)} entri, perlu krama+arti)'
    elif kel_selected.startswith('2.'):
        matches = [(i, w) for i, w in enumerate(data['words'])
                   if (w.get('ngoko') or '').strip()
                   and (w.get('krama') or '').strip()
                   and not (w.get('indo') or '').strip()]
        title = f'📋 Kelengkapan: ngoko+krama ({len(matches)} entri, perlu indo)'
    elif kel_selected.startswith('3.'):
        matches = [(i, w) for i, w in enumerate(data['words'])
                   if (w.get('ngoko') or '').strip()
                   and not (w.get('krama') or '').strip()
                   and (w.get('indo') or '').strip()]
        title = f'📋 Kelengkapan: ngoko+arti ({len(matches)} entri, perlu krama)'
    elif kel_selected.startswith('4.'):
        matches = [(i, w) for i, w in enumerate(data['words'])
                   if (w.get('ngoko') or '').strip()
                   and (w.get('krama') or '').strip()
                   and (w.get('indo') or '').strip()]
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
        arti = (entry.get('indo') or '')[:20]
        ready = (entry.get('ngoko') or '').strip() and (entry.get('krama') or '').strip() and (entry.get('indo') or '').strip()
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
    ready = (entry.get('ngoko') or '').strip() and (entry.get('krama') or '').strip() and (entry.get('indo') or '').strip()

    if not ready:
        print(f'\n  ❌ Entry ini 3-field belum lengkap. Tidak bisa di-mark READY.')
        print(f'     ngoko={entry.get("ngoko","")!r}')
        print(f'     krama={entry.get("krama","")!r}')
        print(f'     arti={entry.get("indo","")!r}')
        input('\n  Tekan Enter...')
        return

    # Tampilkan detail + pilih action
    print(f'\n  📋 Entry dipilih:')
    print(f'    ngoko:  {entry.get("ngoko","")!r}')
    print(f'    krama:  {entry.get("krama","")!r}')
    print(f'    arti:   {entry.get("indo","")!r}')
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


def do_merge_2_entries_by_idx(data, idx1, idx2, confirm_each=True):
    """Merge 2 entries by index → 1 entry dengan koma (sinonim).

    Logic:
    - Smart ngoko/krama detection (kalau entry2 ngoko == entry1 krama, swap)
    - Gabung ngoko/krama dengan koma (sinonim beda kata, 1 entry)
    - Gabung indo dengan koma
    - Combine aksara + keterangan + sumber (R-18 compliance)
    - Delete entry2, re-number entry_id
    - save_kamus (R-12: status='draft' setelah merge)

    Args:
      confirm_each: True = tampilkan preview + konfirmasi (interaktif)
                    False = silent merge (untuk bulk operation)

    Return: True kalau merge berhasil, False kalau batal.
    """
    if idx1 == idx2:
        print('  ⚑ Entry 1 dan 2 sama. Skip.')
        return False
    if idx1 >= len(data['words']) or idx2 >= len(data['words']):
        print('  ⚑ Index di luar range. Skip.')
        return False

    entry1 = data['words'][idx1]
    entry2 = data['words'][idx2]
    eid1 = entry1.get('entry_id', '?')
    eid2 = entry2.get('entry_id', '?')

    e1_ngoko = (entry1.get('ngoko') or '').strip()
    e1_krama = (entry1.get('krama') or '').strip()
    e1_word = (entry1.get('word') or '').strip()
    e2_ngoko = (entry2.get('ngoko') or '').strip()
    e2_krama = (entry2.get('krama') or '').strip()
    e2_word = (entry2.get('word') or '').strip()
    e1_indo = (entry1.get('indo') or '').strip()
    e2_indo = (entry2.get('indo') or '').strip()

    # Smart merge ngoko/krama
    if e2_ngoko and e1_krama and e2_ngoko.lower() == e1_krama.lower():
        merged_ngoko = e1_ngoko
        merged_krama = e2_ngoko
    elif not e1_krama and e1_ngoko and e2_krama and e1_ngoko.lower() == e2_krama.lower():
        merged_ngoko = e2_ngoko
        merged_krama = e1_ngoko
    else:
        # Normal merge: gabung dengan koma (R-29: sinonim = koma, 1 konsep 1 entry)
        def merge_with_comma(a, b):
            if not a: return b
            if not b: return a
            # Tokenize, dedupe case-insensitive, rejoin
            tokens = [t.strip() for t in a.split(',') if t.strip()]
            existing_lower = set(t.lower() for t in tokens)
            for tok in b.split(','):
                tok = tok.strip()
                if tok and tok.lower() not in existing_lower:
                    tokens.append(tok)
                    existing_lower.add(tok.lower())
            return ', '.join(tokens)

        merged_ngoko = merge_with_comma(e1_ngoko, e2_ngoko)
        merged_krama = merge_with_comma(e1_krama, e2_krama)

    # Merge word (NETRAL lemma) — gabung dengan koma
    def merge_word(a, b):
        if not a: return b
        if not b: return a
        tokens = [t.strip() for t in a.split(',') if t.strip()]
        existing_lower = set(t.lower() for t in tokens)
        for tok in b.split(','):
            tok = tok.strip()
            if tok and tok.lower() not in existing_lower:
                tokens.append(tok)
                existing_lower.add(tok.lower())
        return ', '.join(tokens)
    merged_word = merge_word(e1_word, e2_word)

    # Merge indo dengan koma
    def merge_indo(a, b):
        if not a: return b
        if not b: return a
        tokens = [t.strip() for t in a.split(',') if t.strip()]
        existing_lower = set(t.lower() for t in tokens)
        for tok in b.split(','):
            tok = tok.strip()
            if tok and tok.lower() not in existing_lower:
                tokens.append(tok)
                existing_lower.add(tok.lower())
        return ', '.join(tokens)
    merged_indo = merge_indo(e1_indo, e2_indo)

    # Preview
    if confirm_each:
        print(f'\n  ═══ HASIL MERGE #{eid1} + #{eid2} ═══')
        print(f'  word:  {merged_word!r}')
        print(f'  ngoko: {merged_ngoko!r}')
        print(f'  krama: {merged_krama!r}')
        print(f'  indo:  {merged_indo!r}')
        print(f'  Entry #{eid2} akan di-DELETE.')
        confirm = questionary.confirm('Konfirmasi merge?', default=False).ask()
        if not confirm:
            print('  ⏹ Dibatalkan.')
            return False

    # Apply
    entry1['word'] = merged_word
    entry1['ngoko'] = merged_ngoko
    entry1['krama'] = merged_krama
    entry1['indo'] = merged_indo
    # Combine aksara (R-18)
    a1 = (entry1.get('aksara') or '').strip()
    a2 = (entry2.get('aksara') or '').strip()
    if a2 and a2 not in a1:
        entry1['aksara'] = f'{a1}, {a2}'.strip(', ')
    # Combine keterangan (R-18)
    k1 = (entry1.get('keterangan') or '').strip()
    k2 = (entry2.get('keterangan') or '').strip()
    if k2 and k2 not in k1:
        entry1['keterangan'] = f'{k1} | {k2}'.strip(' |')
    # Sumber
    s1 = (entry1.get('sumber') or '').strip()
    s2 = (entry2.get('sumber') or '').strip()
    if s2 and s2 not in s1:
        entry1['sumber'] = f'{s1} + merge #{eid2}' if s1 else f'merge #{eid2}'
    # R-12: status='draft' setelah merge
    entry1['status'] = 'draft'

    # Delete entry2 — hati2 index (idx2 > idx1 supaya idx1 tidak shift)
    del_idx = max(idx1, idx2)
    del data['words'][del_idx]
    # Re-number entry_id
    for i, w in enumerate(data['words'], 1):
        w['entry_id'] = i

    save_kamus(data)
    if confirm_each:
        print(f'  ✅ Merge sukses: 1 konsep 1 entry (sinonim dengan koma)')
        print(f'  Entry #{eid2} di-DELETE. Total: {len(data["words"])}')
    return True


def merge_2_entries(data):
    """Merge 2 entries terpisah jadi 1 entry. Per Phase 4 — extract dari main_menu.

    Flow:
      1. Search entry pertama (cari kata)
      2. Search entry kedua (skip entry pertama)
      3. Preview hasil merge (smart ngoko/krama detection, gabung arti comma)
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
    print(f'\n  Entry 1: ngoko={entry1.get("ngoko","")!r} krama={entry1.get("krama","")!r} arti={entry1.get("indo","")!r}')

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

    success = do_merge_2_entries_by_idx(data, idx1, idx2, confirm_each=True)
    if success:
        input('  Tekan Enter...')


def add_new_entry(data):
    """Tambah entry baru via TUI — workflow SRT editor.

    Skenario: user kerja di SRT editor web app, nemu kata Jawa baru yg belum ada di kamus.
    Daripada edit JSON manual, user buka TUI → menu ini → input ngoko+krama+indo → save.

    Setelah save:
    - entry_id auto-generate (max + 1, akan re-number saat save_kamus)
    - word = '' (paired, R-21)
    - status = 'draft' (R-12: user harus explicit mark ready)
    - sumber = 'user_input' (tracking)
    - keterangan = '' (user bisa isi via edit_entry nanti)

    Defensive checks:
    - Cek duplikat dengan existing entries (warn user, tapi tetap allow save)
    - Validate: minimal ngoko ATAU krama + indo harus terisi (paired requirement)
    """
    os.system('clear' if os.name != 'nt' else 'cls')
    print('╔' + '═' * 60 + '╗')
    print('║  ➕ Tambah Entry Baru (workflow SRT editor)' + ' ' * 10 + '║')
    print('╚' + '═' * 60 + '╝')
    print()
    print('  Skenario: nemu kata baru di SRT editor, masukin ke kamus.')
    print('  Isi minimal ngoko ATAU krama + indo (paired requirement).')
    print('  word otomatis kosong (paired, R-21).')
    print('  status = draft (user harus mark READY via menu).')
    print()

    # Input fields
    ngoko = questionary.text('  ngoko (Enter=skip):', default='').ask()
    if ngoko is None: return
    ngoko = ngoko.strip()

    krama = questionary.text('  krama (Enter=skip):', default='').ask()
    if krama is None: return
    krama = krama.strip()

    indo = questionary.text('  indo (WAJIB):', default='').ask()
    if indo is None: return
    indo = indo.strip()

    keterangan = questionary.text('  keterangan (opsional):', default='').ask()
    if keterangan is None: return
    keterangan = keterangan.strip()

    # Validate: minimal paired requirement
    if not indo:
        print('\n  ⚑ indo WAJIB. Entry baru harus punya terjemahan Indonesia.')
        input('  Tekan Enter...')
        return
    if not ngoko and not krama:
        print('\n  ⚑ Minimal ngoko ATAU krama harus diisi.')
        print('    Kalau belum tahu ngoko/krama, isi word via edit setelah save.')
        input('  Tekan Enter...')
        return

    # Duplikat check (warn, tetap allow save)
    print('\n  Cek duplikat di entries existing...')
    words = data['words']
    potential_dupes = []
    new_tokens = []
    for val in [ngoko, krama]:
        if val:
            for tok in val.split(','):
                tok = tok.strip()
                if tok:
                    new_tokens.append(tok.lower())
    for w in words:
        for field in ['ngoko', 'krama', 'indo', 'word']:
            val = (w.get(field) or '').strip()
            if not val: continue
            for tok in val.split(','):
                tok = tok.strip().lower()
                if tok in new_tokens:
                    potential_dupes.append((w.get('entry_id', '?'), field, tok, w))
                    break  # 1 field match per entry cukup

    if potential_dupes:
        print(f'\n  ⚠ Ditemukan {len(potential_dupes)} entry mungkin duplikat:')
        for eid, field, tok, w in potential_dupes[:5]:
            print(f'    [{eid}] field={field} match={tok!r}')
            print(f'      word={w.get("word","")[:20]!r} ngoko={w.get("ngoko","")[:20]!r} krama={w.get("krama","")[:20]!r} indo={w.get("indo","")[:20]!r}')
        if len(potential_dupes) > 5:
            print(f'    ... +{len(potential_dupes) - 5} more')
        print()
        print('  ⚠ Tetap save? Kalau duplikat, lebih baik edit entry existing.')
        cont = questionary.confirm('  Tetap save entry baru?', default=False).ask()
        if not cont:
            print('\n  ⏹ Dibatalkan. Cek entry existing via menu Search.')
            input('  Tekan Enter...')
            return

    # Generate entry_id (max + 1, akan re-number saat save)
    max_eid = max((w.get('entry_id', 0) for w in words), default=0)
    new_entry = {
        'entry_id': max_eid + 1,
        'word': '',  # R-21: paired, word kosong
        'ngoko': ngoko,
        'krama': krama,
        'indo': indo,
        'keterangan': keterangan,
        'aksara': '',
        'sumber': 'user_input',
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
        'status': 'draft',  # R-12: user harus explicit mark ready
    }
    data['words'].append(new_entry)
    save_kamus(data)

    print(f'\n  ✅ Entry baru disimpan!')
    print(f'  entry_id (sementara): #{max_eid + 1} (akan re-number saat save)')
    print(f'  ngoko={ngoko!r}')
    print(f'  krama={krama!r}')
    print(f'  indo={indo!r}')
    print(f'  status=draft. Mark READY via menu ⚡ Mark READY/DRAFT bulk.')
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



def detect_duplicates(data):
    """Deteksi duplikat = kata IDENTIK lintas entry, di FIELD APA PUN (lintas field).

    R-28/R-29: Duplikat = kata IDENTIK muncul di 2+ entries. Bukan sinonim.
    R-29: TIDAK ADA SINONIM BEDA ENTRY — kalau kata sama di entry beda = duplikat.
    R-30: SCAN SEMUA entries (paired + netral). Netral juga data.
    R-32: 1 index gabungan SEMUA field (word+ngoko+krama+indo). SEMUA kata, TANPA filter.
          Tokenize comma di SEMUA field (termasuk word).
          Tag [P]/[N] di output supaya user tahu context.
          HAPUS filter field_choice — tampilkan SEMUA duplikat langsung.
    """
    words = data['words']
    os.system('clear' if os.name != 'nt' else 'cls')
    print('╔' + '═' * 60 + '╗')
    print('║  🔍 Deteksi Duplikat (lintas entry, SEMUA field)' + ' ' * 5 + '║')
    print('╚' + '═' * 60 + '╝')
    print()

    # R-32: Build 1 index gabungan SEMUA field (lintas field)
    # Pakai build_cross_entry_index (sama dengan audit_flags_menu) supaya konsisten
    cross_idx = build_cross_entry_index(words)
    all_idx, indo_idx = cross_idx

    # Filter: hanya token di 2+ entries (lintas field lintas entry)
    dupes = {}
    for tok, locations in all_idx.items():
        unique_eids = set(eid for eid, _ in locations)
        if len(unique_eids) > 1:
            dupes[tok] = locations

    print(f'  Total kata unik (SEMUA field gabungan): {len(all_idx):,}')
    print(f'  Duplikat (kata identik lintas entry, lintas field): {len(dupes):,}')
    print()

    if not dupes:
        print(f'  ✅ Tidak ada duplikat.')
        input('  Tekan Enter untuk kembali...')
        return

    # Tampilkan SEMUA duplikat langsung (R-33: TIDAK ada limit, TIDAK ada filter)
    # Sort by #entries descending (yg paling banyak duplikat di atas)
    sorted_dupes = sorted(dupes.items(),
                          key=lambda x: len(set(eid for eid, _ in x[1])),
                          reverse=True)
    for kata, locations in sorted_dupes:
        unique_eids = sorted(set(eid for eid, _ in locations))
        # Group by eid → fields where kata muncul
        eids_to_fields = {}
        for eid, field in locations:
            eids_to_fields.setdefault(eid, set()).add(field)
        print(f"\n  '{kata}' di {len(unique_eids)} entries:")
        for eid in unique_eids[:8]:
            w = next((x for x in words if x.get('entry_id') == eid), None)
            if w:
                # R-30: tag [P]=paired, [N]=netral
                tag = '[P]' if is_paired_entry(w) else '[N]'
                fields = sorted(eids_to_fields[eid])
                print(f"    {tag} [{eid}] fields={','.join(fields):20} word={w.get('word','')[:25]!r} ngoko={w.get('ngoko','')[:20]!r} krama={w.get('krama','')[:20]!r} indo={w.get('indo','')[:20]!r}")
        if len(unique_eids) > 8:
            print(f"    ... +{len(unique_eids) - 8} more")

    print(f'\n  ⚠ Duplikat = kata IDENTIK lintas entry, di FIELD APA PUN (lintas field).')
    print(f'  [P]=paired (indo+ngoko/krama) | [N]=netral (belum paired)')
    print(f'  R-29: TIDAK ADA SINONIM BEDA ENTRY — kalau kata sama di entry beda = duplikat.')
    print(f'  R-34: 1 KONSEP 1 ENTRY. Merge 2 entries jadi 1 dengan koma (sinonim).')
    print(f'  → Ketik kata duplikat untuk MERGE 2 entries.')
    print(f'  → Atau ketik entry_id untuk EDIT 1 entry.')
    print(f'  → Enter=kembali.')

    # Interactive: user input kata duplikat OR entry_id
    # Reload kamus karena merge bisa mengubah entry_id
    while True:
        ans = input(f'  kata (merge) / entry_id (edit) / Enter (kembali): ').strip()
        if not ans:
            break

        # Cek apakah ans adalah kata duplikat
        if ans.lower() in dupes:
            # MERGE 2 entries by duplikat kata
            locations = dupes[ans.lower()]
            unique_eids = sorted(set(eid for eid, _ in locations))
            print(f'\n  ═══ MERGE DUPlikat: {ans!r} ═══')
            print(f'  Pilih 2 entries untuk merge (sisanya akan tetap):')
            # List entries dengan duplikat
            choices = []
            eid_to_idx = {}
            for i, eid in enumerate(unique_eids):
                w = next((x for x in data['words'] if x.get('entry_id') == eid), None)
                if not w:
                    continue
                idx = next((j for j, x in enumerate(data['words']) if x.get('entry_id') == eid), -1)
                tag = '[P]' if is_paired_entry(w) else '[N]'
                label = f'{tag} #{eid} word={w.get("word","")[:20]!r} ngoko={w.get("ngoko","")[:20]!r} krama={w.get("krama","")[:20]!r} indo={w.get("indo","")[:20]!r}'
                eid_to_idx[label] = idx
                choices.append(label)
            if len(unique_eids) > 2:
                # Multi entries — user pilih 2
                choices.append('↩ Batal')
                sel1 = questionary.select('Pilih entry PRIMARY (akan di-keep):',
                                          choices=choices, default=choices[0]).ask()
                if not sel1 or 'Batal' in sel1:
                    continue
                idx1 = eid_to_idx[sel1]
                # Hapus pilihan pertama dari list
                remaining = [c for c in choices if c != sel1 and c != '↩ Batal']
                sel2 = questionary.select('Pilih entry SECONDARY (akan di-merge ke PRIMARY, lalu delete):',
                                          choices=remaining + ['↩ Batal'],
                                          default=remaining[0] if remaining else '↩ Batal').ask()
                if not sel2 or 'Batal' in sel2:
                    continue
                idx2 = eid_to_idx[sel2]
            else:
                # 2 entries — langsung merge
                idx1 = eid_to_idx[choices[0]]
                idx2 = eid_to_idx[choices[1]]

            success = do_merge_2_entries_by_idx(data, idx1, idx2, confirm_each=True)
            if success:
                # Reload dupes & words karena merge mengubah data
                words = data['words']
                cross_idx = build_cross_entry_index(words)
                all_idx, indo_idx = cross_idx
                dupes = {tok: locs for tok, locs in all_idx.items()
                         if len(set(eid for eid, _ in locs)) > 1}
                print(f'\n  📊 Duplikat tersisa: {len(dupes)}')
            input('  Tekan Enter untuk lanjut...')
            continue

        # Cek apakah ans adalah entry_id (angka)
        try:
            eid = int(ans)
        except ValueError:
            print(f'  ⚑ "{ans}" bukan kata duplikat dan bukan angka entry_id.')
            continue
        idx = next((i for i, w in enumerate(words) if w.get('entry_id') == eid), -1)
        if idx < 0:
            print(f'  ⚑ entry_id #{eid} tidak ditemukan.')
            continue
        edit_entry(data, idx)
        input('  Tekan Enter untuk lanjut (Enter kosong=kembali)...')


def compute_entry_flags(entry):
    """Heuristic flag audit — TIDAK auto-fix, hanya tandai entry mencurigakan.

    Return list of (flag_code, tier, msg).
    tier: 'HIGH' (🔴 wajib audit), 'MEDIUM' (🟡 perlu cek), 'LOW' (🟢 sanity).

    Berdasarkan analisa data kamus_unified_draft.json 43.630 entries:
    - Source jv.wiktionary punya format `lemma; definisi:` → sering leak ke field indo
    - AI infill batch 1-22 kadang isi definisi panjang, bukan terjemahan kata
    - Beberapa entry ngoko == krama (auto-copy suspect)
    - Karakter parser leak: `|`, `====`, `#`, `t=`, `kateg`, `mbledhos`
    """
    import re
    flags = []
    word = (entry.get('word') or '').strip()
    ngoko = (entry.get('ngoko') or '').strip()
    krama = (entry.get('krama') or '').strip()
    indo = (entry.get('indo') or '').strip()
    keterangan = (entry.get('keterangan') or '').strip()

    # ===== 🔴 HIGH (wajib audit) =====

    # SRC_LEAK: parser leak karakter wiktionary mentah — cek SEMUA field termasuk word
    src_leak_pattern = re.compile(r'[|====#]|t=|kateg|wuu|mbledhos|\{\{|\}\}')
    for field_name, val in [('word', word), ('indo', indo), ('ngoko', ngoko), ('krama', krama)]:
        if val and src_leak_pattern.search(val):
            flags.append(('SRC_LEAK', 'HIGH', f'field {field_name} ada parser leak wiktionary'))
            break  # 1 flag per kategori sudah cukup

    # WORD_LEAK_INDO: indo match `^word; ...` atau `word; ...:` (lemma wiktionary)
    # Contoh: word='abab' indo='abab; hawa mulut:' → label wiktionary mentah
    if word and indo:
        indo_first = indo.split(';')[0].strip().lower()
        if indo_first == word.lower() and (';' in indo or ':' in indo):
            flags.append(('WORD_LEAK_INDO', 'HIGH', f'indo = "word; definisi:" (label wiktionary mentah)'))

    # NGOKO_EQ_KRAMA: ngoko == krama (auto-copy suspect, harus beda register)
    if ngoko and krama and ngoko.lower() == krama.lower():
        flags.append(('NGOKO_EQ_KRAMA', 'HIGH', f'ngoko == krama = "{ngoko}" (suspect auto-copy)'))

    # INDO_LONG_DEF: indo panjang atau multi-token berlebih (kemungkinan kalimat definisi)
    if indo:
        if len(indo) > 30:
            flags.append(('INDO_LONG_DEF', 'HIGH', f'indo >30 char (kemungkinan kalimat definisi)'))
        else:
            # Hitung token (pisah koma)
            n_tok = len([t for t in indo.split(',') if t.strip()])
            if n_tok > 5:
                flags.append(('INDO_LONG_DEF', 'HIGH', f'indo {n_tok} token (suspect halu sinonim panjang)'))

    # WORD_LONG: word >25 char (kemungkinan kalimat/paragraf, bukan lemma kata)
    # Netral entries juga bisa kena — word dari wiktionary raw bisa panjang
    if word and len(word) > 25:
        flags.append(('WORD_LONG', 'HIGH', f'word >25 char: "{word[:40]}..." (suspect bukan lemma)'))

    # ===== 🟡 MEDIUM (perlu cek) =====

    # INDO_MULTI_SEMI: indo mengandung `;` ≥2 (kemungkinan multi-arti perlu dirapikan)
    if indo.count(';') >= 2:
        flags.append(('INDO_MULTI_SEMI', 'MEDIUM', f'indo ada {indo.count(";")} titik-koma (multi-arti?)'))

    # INDO_END_COLON: indo diakhiri `:` (format label wiktionary)
    if indo.endswith(':') or indo.rstrip().endswith(':'):
        flags.append(('INDO_END_COLON', 'MEDIUM', f'indo diakhiri ":" (label wiktionary format)'))

    # INDO_QUOTED: indo diapit tanda kutip/kurung (label leak)
    if (indo.startswith('"') and indo.endswith('"')) or \
       (indo.startswith("'") and indo.endswith("'")) or \
       (indo.startswith('(') and indo.endswith(')')):
        flags.append(('INDO_QUOTED', 'MEDIUM', f'indo diapit tanda/kurung (suspect label)'))

    # LONG_FIELD: ngoko atau krama sangat panjang (suspect kalimat, bukan kata)
    for field_name, val in [('ngoko', ngoko), ('krama', krama)]:
        if val and len(val) > 25:
            flags.append(('LONG_FIELD', 'MEDIUM', f'{field_name} >25 char: "{val[:40]}..."'))
            break

    # WORD_DIGIT: word ada digit (angka di lemma — suspect entry_id leak atau label)
    # Contoh word='1' atau word='abab2' — kemungkinan parsing error
    if word and re.search(r'\d', word):
        flags.append(('WORD_DIGIT', 'MEDIUM', f'word ada digit: "{word[:30]}"'))

    # WORD_MULTI_TOKEN: word punya >3 token dipisah spasi (suspect kalimat, bukan lemma)
    # Contoh: word='makan pada saat hari raya' (4 kata, bukan lemma)
    if word:
        n_space_tok = len([t for t in word.split() if t.strip()])
        if n_space_tok > 3:
            flags.append(('WORD_MULTI_TOKEN', 'MEDIUM', f'word {n_space_tok} kata (suspect bukan lemma)'))

    # ===== 🟡 MEDIUM — WORD_LEMMA_MULTI: word punya >3 lemma (suspect 2 konsep digabung dari parsing berantakan)
    # Contoh: #6865 word='ngimpi, supena, impen, impi' = 4 lemma
    #   ngimpi/supena/impi = konsep MIMPI, impen = konsep UMUR (halusinasi parsing)
    #   User edit manual: hapus 'impen' atau pecah jadi 2 entries
    # Bantu user prioritaskan audit entry berantakan
    if word:
        n_lemma = len([t for t in word.split(',') if t.strip()])
        if n_lemma > 3:
            flags.append(('WORD_LEMMA_MULTI', 'MEDIUM',
                          f'word punya {n_lemma} lemma (suspect 2 konsep digabung dari parsing wiktionary)'))

    # ===== 🟢 LOW (sanity check) =====

    # DIGIT_IN_FIELD: ngoko/krama ada digit (entry_id leak atau angka janggal)
    for field_name, val in [('ngoko', ngoko), ('krama', krama)]:
        if val and re.search(r'\d', val):
            # Exception: kata jawa bisa punya digit (mis. "sasi 12") — flag saja
            flags.append(('DIGIT_IN_FIELD', 'LOW', f'{field_name} ada digit: "{val[:30]}"'))
            break

    # WORD_NO_PAIR: word terisi, ngoko+krama kosong, indo kosong (entry NETRAL perlu pasangan)
    # Bukan masalah — ini workflow normal. SKIP flag.

    return flags


def build_cross_entry_index(words):
    """Build index lintas-entry untuk deteksi duplikat & sinonim.

    R-28/R-29: Duplikat = kata IDENTIK muncul di 2+ entries, di FIELD APA PUN (lintas field).
    R-29: TIDAK ADA SINONIM BEDA ENTRY — kalau kata sama di entry beda = duplikat.
    R-33: SEMUA ENTRY TANPA KECUALI. SEMUA token (termasuk 1-char). TANPA filter.

    Return:
      all_idx: {token_lower: set of (entry_id, field)} — index gabungan SEMUA field
      indo_idx: {indo_lower: set of entry_ids} — khusus untuk SINONIM_INDO detection
    """
    from collections import defaultdict
    all_idx = defaultdict(set)  # token → set of (eid, field)
    indo_idx = defaultdict(set)  # indo (lower) → set of eids (untuk SINONIM_INDO)
    for w in words:
        eid = w.get('entry_id')
        if eid is None: continue
        for field in ['word', 'ngoko', 'krama', 'indo']:
            val = (w.get(field) or '').strip()
            if not val: continue
            for tok in val.split(','):
                tok = tok.strip().lower()
                # R-33: SEMUA token, termasuk 1-char. TANPA filter length.
                if tok:
                    all_idx[tok].add((eid, field))
        indo = (w.get('indo') or '').strip()
        if indo:
            indo_idx[indo.lower()].add(eid)
    return all_idx, indo_idx


def compute_cross_entry_flags(entry, cross_idx):
    """Flag lintas-entry (butuh cross_idx dari build_cross_entry_index).

    Return list of (flag_code, tier, msg).

    Logika sama dengan merge-milstrike + R-28/R-29:
    - DUP_TOKEN (HIGH): token di SEMUA field (word/ngoko/krama/indo) muncul di 2+ entries LINTAS FIELD
      (kata identik di entry beda = duplikat, BUKAN sinonim beda entry)
    - SINONIM_INDO (MEDIUM): indo identik dengan entry lain → sinonim potensial (merge word dengan koma)

    User requirement: 'kata sama = replace, kata beda + sama arti = sinonim = koma'
    R-28: Duplikat = kata IDENTIK lintas entry. Bukan sinonim.
    R-29: TIDAK ADA SINONIM BEDA ENTRY — kalau kata sama di entry beda = duplikat.
    """
    flags = []
    eid = entry.get('entry_id')
    # cross_idx is tuple (all_idx, indo_idx)
    all_idx, indo_idx = cross_idx

    # ===== 🔴 HIGH (wajib audit) =====
    # DUP_TOKEN: token di SEMUA field (word/ngoko/krama/indo) muncul di 2+ entries LINTAS FIELD
    # R-33: SEMUA token, termasuk 1-char. TANPA filter length. SEMUA duplikat per entry.
    seen_tokens = set()
    for field in ['word', 'ngoko', 'krama', 'indo']:
        val = (entry.get(field) or '').strip()
        if not val: continue
        for tok in val.split(','):
            tok_lower = tok.strip().lower()
            if not tok_lower or tok_lower in seen_tokens: continue
            seen_tokens.add(tok_lower)
            locations = all_idx.get(tok_lower, set())
            unique_eids = set(loc_eid for loc_eid, _ in locations)
            if len(unique_eids) > 1:
                others = sorted(unique_eids - {eid})[:3]
                others_str = ','.join(str(o) for o in others)
                other_fields = set()
                for loc_eid, loc_field in locations:
                    if loc_eid != eid:
                        other_fields.add(loc_field)
                fields_str = ','.join(sorted(other_fields))
                flags.append(('DUP_TOKEN', 'HIGH',
                              f'token "{tok_lower}" di {field} juga di entry #{others_str} (di field: {fields_str})'))
                # TIDAK break — SEMUA duplikat per entry

    # ===== 🟡 MEDIUM (perlu cek) =====
    # SINONIM_INDO: indo identik dengan entry lain (case insensitive)
    # R-33: SEMUA indo, termasuk 1-char. TANPA filter length.
    indo = (entry.get('indo') or '').strip()
    if indo:
        indo_lower = indo.lower()
        eids = indo_idx.get(indo_lower, set())
        if len(eids) > 1:
            others = sorted(eids - {eid})[:3]
            others_str = ','.join(str(o) for o in others)
            flags.append(('SINONIM_INDO', 'MEDIUM',
                          f'indo "{indo[:40]}" juga di entry #{others_str} (sinonim potensial — merge dengan koma)'))

    return flags


def compute_all_flags(entry, cross_idx=None):
    """Combine per-entry flags + cross-entry flags (kalau cross_idx di-supply).

    Helper untuk audit_flags_menu + browse_list_with_flags.
    """
    flags = compute_entry_flags(entry)
    if cross_idx is not None:
        flags.extend(compute_cross_entry_flags(entry, cross_idx))
    return flags


def is_paired_entry(entry):
    """Entry 'paired' = sudah ada minimal ngoko+indo (terjemahan sudah diketahui).

    Return True kalau entry sudah punya pasangan terjemahan (siap audit).
    Skip entries NETRAL (word terisi, ngoko+krama kosong, indo kosong/tdk lengkap).

    Definisi 'paired':
      - ngoko+krama+indo terisi (LENGKAP), ATAU
      - ngoko+indo terisi (walau krama kosong, terjemahan sudah ada), ATAU
      - krama+indo terisi (walau ngoko kosong, terjemahan sudah ada)

    Bukan paired:
      - word + indo (NETRAL — indo belum tentu terjemahan word, bisa label wiktionary)
      - word only (NETRAL murni, belum diketahui)
      - ngoko only / krama only (belum ada terjemahan)
    """
    ngoko = (entry.get('ngoko') or '').strip()
    krama = (entry.get('krama') or '').strip()
    indo = (entry.get('indo') or '').strip()
    # Harus ada terjemahan (indo) + minimal 1 kata Jawa (ngoko ATAU krama)
    return bool(indo) and (bool(ngoko) or bool(krama))


def audit_flags_menu(data):
    """Menu audit: tampilkan entries dengan flag suspicious. User audit manual.

    TIDAK ada auto-fix. User pilih tier → browse list → edit_entry.

    R-30 fix: SCAN SEMUA entries (paired + netral). Netral juga data, perlu diaudit.
    R-31: Cross-entry audit (logika sama dengan merge-milstrike):
      - DUP_TOKEN_*: token di word/ngoko/krama muncul di 2+ entries → duplikat lintas entry
      - SINONIM_INDO: indo identik dengan entry lain → sinonim potensial (merge word dengan koma)

    Tier:
      🔴 HIGH  — wajib audit (parser leak, ngoko==krama, indo definisi panjang, dup_token lintas entry)
      🟡 MEDIUM — perlu cek (multi-`;`, diakhiri `:`, diapit kutip, field panjang, sinonim_indo)
      🟢 LOW   — sanity (digit di field kata)
    """
    os.system('clear' if os.name != 'nt' else 'cls')
    print('╔' + '═' * 60 + '╗')
    print('║  🔍 Audit Flags (heuristic, NO auto-fix)' + ' ' * 16 + '║')
    print('╚' + '═' * 60 + '╝')
    print()
    words = data['words']

    # R-31: Build cross-entry index sekali (untuk dup_token + sinonim_indo detection)
    print('  Build cross-entry index (1 index gabungan SEMUA field — logika R-28/R-29)...')
    cross_idx = build_cross_entry_index(words)
    all_idx, indo_idx = cross_idx
    n_dup_tokens = sum(1 for tok, locs in all_idx.items() if len(set(eid for eid,_ in locs)) > 1)
    n_sinonim_indo = sum(1 for indo, eids in indo_idx.items() if len(eids) > 1)
    print(f'  Token duplikat lintas entry (lintas field): {n_dup_tokens}')
    print(f'  Indo duplikat (sinonim potensial): {n_sinonim_indo}')
    print()

    # Compute flags untuk SEMUA entries (per-entry + cross-entry)
    print('  Hitung flag untuk semua entries...')
    flagged = {'HIGH': [], 'MEDIUM': [], 'LOW': []}
    flag_counts = {}
    for idx, w in enumerate(words):
        fl = compute_all_flags(w, cross_idx)
        if fl:
            tiers = set(t for _, t, _ in fl)
            for t in tiers:
                flagged[t].append((idx, w, [f for f in fl if f[1] == t]))
            for code, tier, _ in fl:
                flag_counts[code] = flag_counts.get(code, 0) + 1

    total_flagged = sum(len(v) for v in flagged.values())
    print(f'\r  Total entries: {len(words):,} | Flagged: {total_flagged:,}' + ' ' * 20)
    print(f'  🔴 HIGH (wajib audit):   {len(flagged["HIGH"]):,}')
    print(f'  🟡 MEDIUM (perlu cek):    {len(flagged["MEDIUM"]):,}')
    print(f'  🟢 LOW (sanity):         {len(flagged["LOW"]):,}')
    print()

    if not total_flagged:
        print('  ✅ Tidak ada entry ter-flag. Kamus clean menurut heuristic.')
        input('\n  Tekan Enter untuk kembali...')
        return

    # Detail per flag code — ambil tier dari compute_all_flags (single source of truth)
    code_to_tier = {}
    for w in words:
        for code, tier, _ in compute_all_flags(w, cross_idx):
            if code not in code_to_tier:
                code_to_tier[code] = tier
    print('  Detail per flag:')
    for code, count in sorted(flag_counts.items(), key=lambda x: -x[1]):
        tier = code_to_tier.get(code, 'HIGH')
        icon = '🔴' if tier == 'HIGH' else ('🟡' if tier == 'MEDIUM' else '🟢')
        print(f'    {icon} {code:20} {count:5} entri')
    print()

    # Pilih tier
    tier_choices = [
        f'🔴 HIGH ({len(flagged["HIGH"])} entri, wajib audit)',
        f'🟡 MEDIUM ({len(flagged["MEDIUM"])} entri, perlu cek)',
        f'🟢 LOW ({len(flagged["LOW"])} entri, sanity)',
        '📊 Semua flagged (sort by #flag)',
        '↩ Kembali',
    ]
    sel = questionary.select('Browse:', choices=tier_choices, default=tier_choices[0]).ask()
    if not sel or 'Kembali' in sel:
        return

    if 'HIGH' in sel:
        entries_with_idx = [(i, w) for i, w, _ in flagged['HIGH']]
        title = f'🔴 AUDIT HIGH ({len(entries_with_idx)} entri, wajib audit manual)'
    elif 'MEDIUM' in sel:
        entries_with_idx = [(i, w) for i, w, _ in flagged['MEDIUM']]
        title = f'🟡 AUDIT MEDIUM ({len(entries_with_idx)} entri, perlu cek)'
    elif 'LOW' in sel:
        entries_with_idx = [(i, w) for i, w, _ in flagged['LOW']]
        title = f'🟢 AUDIT LOW ({len(entries_with_idx)} entri, sanity)'
    else:
        all_flagged = []
        for tier_list in flagged.values():
            for i, w, fl in tier_list:
                all_flagged.append((i, w, fl))
        all_flagged.sort(key=lambda x: -len(x[2]))
        entries_with_idx = [(i, w) for i, w, _ in all_flagged]
        title = f'📊 SEMUA FLAGGED ({len(entries_with_idx)} entri, sort by #flag)'

    browse_list_with_flags(data, entries_with_idx, title, cross_idx=cross_idx)


def browse_list_with_flags(data, entries_with_idx, title, cross_idx=None):
    """Browse list dengan info flag di label (khusus audit menu).

    Sama seperti browse_list, tapi label tambahkan flag info:
      [P] [#123] 🔴2 INDO_LONG_DEF, SRC_LEAK | ngoko=...

    Args:
      cross_idx: optional, dari build_cross_entry_index. Kalau None, hanya compute_entry_flags.
                 Kalau supplied, pakai compute_all_flags (per-entry + cross-entry).
    """
    total = len(entries_with_idx)
    if total == 0:
        print(f'\n  Tidak ada entri untuk "{title}"')
        input('\n  Tekan Enter...')
        return

    page_size = 15  # Lebih sedikit per page karena label lebih panjang
    current_page = 0

    while True:
        start = current_page * page_size
        end = min(start + page_size, total)
        page = entries_with_idx[start:end]

        os.system('clear' if os.name != 'nt' else 'cls')
        print('╔' + '═' * 80 + '╗')
        print(f'║  {title[:78]}' + ' ' * max(0, 78 - len(title)) + '║')
        print(f'║  {total} entri | Hal {current_page + 1}/{(total + page_size - 1) // page_size}' + ' ' * max(0, 50 - len(str(total)) - len(str(current_page + 1)) - len(str((total + page_size - 1) // page_size))) + '║')
        print('╚' + '═' * 80 + '╝')
        print()

        label_to_idx = {}
        choices = []
        for orig_idx, entry in page:
            eid = entry.get('entry_id', orig_idx + 1)
            fl = compute_all_flags(entry, cross_idx) if cross_idx is not None else compute_entry_flags(entry)
            n_high = sum(1 for _, t, _ in fl if t == 'HIGH')
            n_med  = sum(1 for _, t, _ in fl if t == 'MEDIUM')
            n_low  = sum(1 for _, t, _ in fl if t == 'LOW')
            tier_icon = '🔴' if n_high else ('🟡' if n_med else '🟢')
            # Ambil flag codes singkat (top 2)
            codes = [c for c, _, _ in fl[:2]]
            codes_str = ','.join(codes) if codes else '-'
            # Field preview
            word = (entry.get('word') or '').strip()
            ngoko = (entry.get('ngoko') or '').strip()
            krama = (entry.get('krama') or '').strip()
            indo = (entry.get('indo') or '').strip()
            # Build label: [P/N] [#123] 🔴2 INDO_LONG_DEF | word=... ngoko=... krama=... indo=...
            # [P]=paired (indo+ngoko/krama), [N]=netral (belum paired)
            paired_tag = '[P]' if is_paired_entry(entry) else '[N]'
            preview_parts = []
            if word: preview_parts.append(f'word={word[:15]}')
            if ngoko: preview_parts.append(f'ngoko={ngoko[:15]}')
            if krama: preview_parts.append(f'krama={krama[:15]}')
            if indo: preview_parts.append(f'indo={indo[:20]}')
            preview = ' '.join(preview_parts)[:55]
            count_str = f'{n_high}H' if n_high else (f'{n_med}M' if n_med else f'{n_low}L')
            label = f'{paired_tag} [#{eid}] {tier_icon}{count_str} {codes_str:25} | {preview}'
            label_to_idx[label] = orig_idx
            choices.append(label)

        # Navigation
        nav = []
        if current_page > 0:
            nav.append('◀ Halaman sebelumnya')
        if end < total:
            nav.append('▶ Halaman berikutnya')
        nav.append('↩ Kembali ke menu utama')

        choices.extend(nav)

        selected = questionary.select(
            f'Pilih entri ([P]=paired | [N]=netral | 🔴HIGH/🟡MED/🟢LOW):',
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

        # Edit entry terpilih
        match_idx = label_to_idx.get(selected)
        if match_idx is not None:
            edit_entry(data, match_idx)


def main_menu(data):
    """Main menu — user pilih menu dengan arrow keys"""
    while True:
        os.system('clear' if os.name != 'nt' else 'cls')
        words = data['words']
        total = len(words)
        ready = sum(1 for w in words if w.get('status') == 'ready')
        with_arti = sum(1 for w in words if (w.get('indo') or '').strip())
        no_arti = sum(1 for w in words if not (w.get('indo') or '').strip())

        # Cek Supabase status
        supabase_ok = bool(os.environ.get('NEXT_PUBLIC_SUPABASE_URL') and os.environ.get('NEXT_PUBLIC_SUPABASE_ANON_KEY'))

        print('╔' + '═' * 60 + '╗')
        print('║  📖 Kamus Jawa Editor (TUI v14.1)' + ' ' * 24 + '║')
        print('║  Tab/panah untuk navigasi, Enter untuk pilih' + ' ' * 11 + '║')
        print('╚' + '═' * 60 + '╝')
        print()
        print(f'  📂 [{CURRENT_SOURCE}] {get_kamus_path()}')
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
        count_3field = sum(1 for w in words if (w.get('ngoko') or '').strip() and (w.get('krama') or '').strip() and (w.get('indo') or '').strip())
        count_ngoko_krama = sum(1 for w in words if (w.get('ngoko') or '').strip() and (w.get('krama') or '').strip() and not (w.get('indo') or '').strip())
        count_ngoko_only = sum(1 for w in words if (w.get('ngoko') or '').strip() and not (w.get('krama') or '').strip() and not (w.get('indo') or '').strip())
        count_ngoko_arti = sum(1 for w in words if (w.get('ngoko') or '').strip() and not (w.get('krama') or '').strip() and (w.get('indo') or '').strip())

        choices = [
            '📊 Statistik kamus',
            '🔍 Search (cari kata di semua field)',
            '✅ Browse READY (status=ready, siap upload)',
            '📋 Browse DRAFT (belum di-edit user)',
            f'⚠ Filter: NETRAL ({count_netral} entri, word+indo, ngoko+krama kosong — user tentukan — R-21)',
            f'🟢 Filter: LENGKAP 3-field ({count_3field} entri, siap review/upload)',
            f'🟡 Filter: NGOKO+KRAMA ({count_ngoko_krama} entri, perlu isi arti)',
            f'⚪ Filter: NGOKO SAJA ({count_ngoko_only} entri, perlu isi krama+arti)',
            f'🔵 Filter: NGOKO+ARTI ({count_ngoko_arti} entri, perlu isi krama)',
            '📂 Browse by source (lemma/mendeley/dasanama/angka)',
            '⭐ Browse entries dengan krama mapping (auto-filled, butuh arti)',
            '📝 Browse entries BELUM ada arti (Indonesia)',
            '🔗 Merge 2 entries (search kata)',
            '➕ Tambah Entry Baru (workflow SRT editor — nemu kata baru)',
            '🔍 Deteksi duplikat (SEMUA entries, SEMUA field, TANPA filter)',
            '🚩 Audit Flags (SEMUA entries — heuristic, NO auto-fix)',
            '⚡ Mark READY/DRAFT bulk (search kata, tanpa edit)',
            '🔑 Set Supabase .env (URL + anon key)',
            '☁  Upload ke Supabase (hanya yang READY)',
            '📂 Switch source JSON (draft / mendeley / dll)',
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
            browse_list(data, matches, f'⚠ NETRAL ({len(matches)} entri, word+indo, ngoko+krama kosong — R-21)')
        elif 'LENGKAP 3-field' in selected:
            # Filter: ngoko + krama + indo semua terisi (siap review/upload)
            matches = [(i, w) for i, w in enumerate(data['words'])
                       if (w.get('ngoko') or '').strip() and (w.get('krama') or '').strip() and (w.get('indo') or '').strip()]
            browse_list(data, matches, f'🟢 LENGKAP 3-field ({len(matches)} entri, siap review)')
        elif 'NGOKO+KRAMA' in selected:
            # Filter: ngoko + krama terisi, arti kosong (perlu isi arti)
            matches = [(i, w) for i, w in enumerate(data['words'])
                       if (w.get('ngoko') or '').strip() and (w.get('krama') or '').strip() and not (w.get('indo') or '').strip()]
            browse_list(data, matches, f'🟡 NGOKO+KRAMA ({len(matches)} entri, perlu isi arti)')
        elif 'NGOKO SAJA' in selected:
            # Filter: ngoko terisi, krama + arti kosong (perlu isi krama+arti)
            matches = [(i, w) for i, w in enumerate(data['words'])
                       if (w.get('ngoko') or '').strip() and not (w.get('krama') or '').strip() and not (w.get('indo') or '').strip()]
            browse_list(data, matches, f'⚪ NGOKO SAJA ({len(matches)} entri, perlu isi krama+arti)')
        elif 'NGOKO+ARTI' in selected:
            # Filter: ngoko + arti terisi, krama kosong (perlu isi krama)
            matches = [(i, w) for i, w in enumerate(data['words'])
                       if (w.get('ngoko') or '').strip() and not (w.get('krama') or '').strip() and (w.get('indo') or '').strip()]
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
        elif 'Tambah Entry Baru' in selected:
            add_new_entry(data)
        elif 'Deteksi duplikat' in selected:
            detect_duplicates(data)
        elif 'Audit Flags' in selected:
            audit_flags_menu(data)
        elif 'Set Supabase' in selected:
            edit_env_file()
        elif 'Switch source JSON' in selected:
            if select_kamus_source():
                # Reload data dari source baru
                new_data = load_kamus()
                if new_data:
                    # Update data reference di-loop
                    # Trick: replace content data dict dengan data baru
                    data.clear()
                    data.update(new_data)
                    print(f'\n  ✅ Kamus aktif: {KAMUS_SOURCES[CURRENT_SOURCE]["label"]}')
                    input('\n  Tekan Enter untuk lanjut...')


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
    print('║  📖 Kamus Jawa Editor (TUI v14.1)' + ' ' * 24 + '║')
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
        and (w.get('indo') or '').strip()
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
