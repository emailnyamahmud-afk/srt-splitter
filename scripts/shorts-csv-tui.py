#!/usr/bin/env python3
"""
shorts-csv-tui.py v1.0 — Generate metadata CSV + manifest untuk YouTube Studio upload

Workflow:
  1. Dola skill shorts-json → JSON (60 segment + title, dari SRT Indonesia)
  2. shorts-tui.py → 60 MP4 di HDD/shorts/{film}/
  3. shorts-csv-tui.py (TUI ini) → CSV + manifest text
  4. User drag 60 MP4 ke YouTube Studio (upload paralel)
  5. User copy-paste metadata dari manifest ke form YouTube per video

Input:
  - JSON timestamps (dari Dola, format: [{"start": float, "end": float, "title": "..."}])
  - MP4 folder (untuk verifikasi filename + match dengan JSON)

Output:
  - {film-name}.metadata.csv     — untuk buka di Excel/Numbers (kolom: filename, title, description, tags, category, schedule)
  - {film-name}.manifest.txt     — plain text untuk easy copy-paste di YouTube Studio

Format CSV (YouTube Studio):
  filename,title,description,tags,category,schedule
  short-001.mp4,"Title here","Description here","tag1,tag2,tag3",Entertainment,2026-10-30 12:00

Format manifest (plain text, copy-paste friendly):
  === SHORT 001 (short-001.mp4) ===
  Title:       Hari pertama jadi pejabat pasti dipersulit
  Description: Film S5 - Drama Mandarin Dub Indonesia.
               #shorts #drama #mandarin #dubbing #indonesia
  Tags:        drama, mandarin, shorts, dubbing, indonesia
  Schedule:    2026-10-30 12:00

Install:
  pip3 install questionary

Usage:
  python3 shorts-csv-tui.py
"""

import os
import sys
import json
import csv
import glob
import shutil
from pathlib import Path
from datetime import datetime, timedelta

try:
    import questionary
except ImportError:
    print('\n❌ pip3 install questionary')
    sys.exit(1)


VERSION = 'v1.0'


def clear_screen():
    os.system('clear' if os.name != 'nt' else 'cls')


def print_banner():
    clear_screen()
    pid_str = f'PID {os.getpid()}'
    title = f'📋 Metadata Generator {VERSION} ({pid_str})'
    pad_title = max(0, 66 - len(title) - 2)
    print('╔' + '═' * 64 + '╗')
    print('║  ' + title + ' ' * pad_title + '║')
    print('║  JSON → CSV + manifest untuk YouTube Studio upload      ║')
    print('╚' + '═' * 64 + '╝')
    print()


def find_files_in_dir(search_dir, extensions):
    """Glob files by extension (non-recursive)."""
    files = []
    for ext in extensions:
        for f in glob.glob(os.path.join(search_dir, f'*.{ext}')):
            files.append(os.path.basename(f))
        for f in glob.glob(os.path.join(search_dir, f'*.{ext.upper()}')):
            files.append(os.path.basename(f))
    files.sort()
    return list(dict.fromkeys(files))


def select_file(prompt, extensions, search_dir=None, default=None):
    """Pick file dari list, dengan fallback ketik manual."""
    if search_dir is None:
        search_dir = os.getcwd()
    available = find_files_in_dir(search_dir, extensions)
    if not available:
        path = questionary.text(f'{prompt} (ketik path lengkap):', default=default or '').ask()
        return path
    choices = available + ['[Ketik path manual]']
    selected = questionary.select(prompt, choices=choices, default=available[0]).ask()
    if selected == '[Ketik path manual]':
        return questionary.text(f'{prompt} (ketik path lengkap):', default=default or '').ask()
    return os.path.join(search_dir, selected)


def select_dir(prompt, search_dir=None, default=None):
    """Pick directory dari list."""
    if search_dir is None:
        search_dir = os.getcwd()
    # List subdirectories
    subdirs = []
    try:
        for d in sorted(os.listdir(search_dir)):
            full = os.path.join(search_dir, d)
            if os.path.isdir(full) and not d.startswith('.'):
                subdirs.append(d)
    except OSError:
        pass

    choices = [os.path.join(search_dir, s) for s in subdirs[:30]]
    if len(subdirs) > 30:
        choices.append(f'... +{len(subdirs)-30} more')
    choices.append(os.getcwd())
    choices.append('[Ketik path manual]')

    selected = questionary.select(prompt, choices=choices, default=choices[0]).ask()
    if selected == '[Ketik path manual]':
        return questionary.text(f'{prompt} (ketik path lengkap):', default=default or '').ask()
    return selected


# ============================================================
# JSON parser (reuse dari shorts-tui.py)
# ============================================================

def parse_timestamps_json(json_path):
    """Parse JSON → list of {start, end, title}."""
    with open(json_path, 'r', encoding='utf-8') as f:
        content = f.read().strip()

    if not content:
        raise ValueError('JSON file kosong')

    try:
        data = json.loads(content)
    except json.JSONDecodeError as e:
        raise ValueError(f'JSON parse gagal: {e}')

    # Normalize format
    if isinstance(data, dict):
        for key in ('segments', 'shorts', 'timestamps', 'cuts', 'data'):
            if key in data and isinstance(data[key], list):
                data = data[key]
                break
        else:
            if 'start' in data and 'end' in data:
                data = [data]
            else:
                raise ValueError('JSON root bukan array')

    if not isinstance(data, list):
        raise ValueError('JSON bukan array')

    segments = []
    for i, item in enumerate(data):
        if not isinstance(item, dict):
            raise ValueError(f'Item {i+1} bukan object: {item!r}')
        if 'start' not in item or 'end' not in item:
            raise ValueError(f'Item {i+1} missing "start" atau "end"')

        start = float(item['start'])
        end = float(item['end'])

        if end <= start:
            raise ValueError(f'Item {i+1} end <= start: start={start}, end={end}')

        title = item.get('title', '').strip()
        if not title:
            title = f'Short {i+1}'

        segments.append({
            'start': start,
            'end': end,
            'title': title,
            'duration': end - start,
        })

    if not segments:
        raise ValueError('JSON kosong')

    return segments


# ============================================================
# Schedule generator
# ============================================================

def generate_schedule(n_segments, start_dt, interval_minutes):
    """Generate list of datetime objects, one per segment.

    Args:
        n_segments: jumlah segment
        start_dt: datetime awal
        interval_minutes: jarak antar publish (menit)

    Returns: list of datetime objects
    """
    schedule = []
    for i in range(n_segments):
        dt = start_dt + timedelta(minutes=interval_minutes * i)
        schedule.append(dt)
    return schedule


def format_schedule_for_csv(dt):
    """Format datetime untuk CSV: '2026-10-30 12:00'"""
    return dt.strftime('%Y-%m-%d %H:%M')


def format_schedule_for_manifest(dt):
    """Format datetime untuk manifest: '2026-10-30 12:00 (Rabu)'"""
    days_id = ['Sen', 'Sel', 'Rab', 'Kam', 'Jum', 'Sab', 'Min']
    day = days_id[dt.weekday()]
    return f'{dt.strftime("%Y-%m-%d %H:%M")} ({day})'


# ============================================================
# Description template (dengan placeholder)
# ============================================================

DEFAULT_DESC_TEMPLATE = (
    'Film {film_name} - Drama Mandarin Dub Indonesia.\n'
    '{title}\n'
    '\n'
    '#shorts #drama #mandarin #dubbing #indonesia'
)

DEFAULT_TAGS = 'drama, mandarin, shorts, dubbing, indonesia'
DEFAULT_CATEGORY = 'Entertainment'


def render_description(template, film_name, title):
    """Render description dengan placeholder {film_name} dan {title}."""
    desc = template.replace('{film_name}', film_name)
    desc = desc.replace('{title}', title)
    return desc


# ============================================================
# CSV + manifest generator
# ============================================================

def generate_csv(segments, mp4_filenames, film_name, desc_template, tags,
                 category, schedule, output_path):
    """Generate CSV file untuk YouTube Studio."""
    with open(output_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f, quoting=csv.QUOTE_MINIMAL)
        # Header
        writer.writerow(['filename', 'title', 'description', 'tags', 'category', 'schedule'])

        for i, seg in enumerate(segments):
            idx = i + 1
            # Match MP4 filename (shorts-tui output: {prefix}-short-{NNN}.mp4)
            mp4_name = mp4_filenames[i] if i < len(mp4_filenames) else f'short-{idx:03d}.mp4'

            title = seg['title']
            description = render_description(desc_template, film_name, title)
            sched = format_schedule_for_csv(schedule[i])

            writer.writerow([mp4_name, title, description, tags, category, sched])

    return os.path.getsize(output_path)


def generate_manifest(segments, mp4_filenames, film_name, desc_template, tags,
                      category, schedule, output_path):
    """Generate plain text manifest untuk easy copy-paste di YouTube Studio."""
    lines = []
    lines.append('=' * 70)
    lines.append(f'📋 METADATA MANIFEST — {film_name}')
    lines.append(f'   {len(segments)} shorts untuk YouTube Studio upload')
    lines.append(f'   Tags: {tags}')
    lines.append(f'   Category: {category}')
    lines.append('=' * 70)
    lines.append('')

    for i, seg in enumerate(segments):
        idx = i + 1
        mp4_name = mp4_filenames[i] if i < len(mp4_filenames) else f'short-{idx:03d}.mp4'

        title = seg['title']
        description = render_description(desc_template, film_name, title)
        sched = format_schedule_for_manifest(schedule[i])

        lines.append(f'--- SHORT {idx:03d} ({mp4_name}) ---')
        lines.append(f'Title:       {title}')
        lines.append(f'Description: {description.replace(chr(10), chr(10) + "             ")}')
        lines.append(f'Tags:        {tags}')
        lines.append(f'Category:    {category}')
        lines.append(f'Schedule:    {sched}')
        lines.append(f'Duration:    {seg["duration"]:.1f}s (start {seg["start"]:.1f}s, end {seg["end"]:.1f}s)')
        lines.append('')

    lines.append('=' * 70)
    lines.append(f'✅ Total: {len(segments)} shorts')
    lines.append(f'   Schedule: {format_schedule_for_manifest(schedule[0])} → {format_schedule_for_manifest(schedule[-1])}')
    lines.append('=' * 70)

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))

    return os.path.getsize(output_path)


# ============================================================
# Main TUI flow
# ============================================================

def main():
    print_banner()

    # === Step 1: Pick JSON ===
    print('▶ Step 1/7: Pilih JSON timestamps (dari Dola skill)')
    from config import SHORTS_DIR, ensure_hdd
    hdd_ok = ensure_hdd()

    json_search_dirs = [os.getcwd()]
    if hdd_ok:
        json_search_dirs.append(str(SHORTS_DIR))

    json_choice = questionary.select(
        'Cari JSON di folder mana?',
        choices=json_search_dirs + ['[Ketik path manual]'],
        default=json_search_dirs[0],
    ).ask()

    if json_choice == '[Ketik path manual]':
        json_path = questionary.text('Path JSON:').ask()
    else:
        json_path = select_file('Pilih JSON timestamps:', ['json'], search_dir=json_choice)

    if not json_path:
        print('Batal.')
        sys.exit(0)

    json_path = os.path.expanduser(json_path)
    if not os.path.isfile(json_path):
        print(f'❌ File tidak ditemukan: {json_path}')
        sys.exit(1)

    print(f'  ✓ {os.path.basename(json_path)}')

    # Parse JSON
    try:
        segments = parse_timestamps_json(json_path)
    except ValueError as e:
        print(f'\n❌ JSON parse gagal: {e}')
        sys.exit(1)

    print(f'  ✓ {len(segments)} segment ditemukan')
    print()

    # === Step 2: Pick MP4 folder ===
    print('▶ Step 2/7: Pilih folder MP4 (output dari shorts-tui)')
    if hdd_ok:
        default_mp4_dir = str(SHORTS_DIR)
    else:
        default_mp4_dir = os.getcwd()

    mp4_dir = select_dir(
        'Pilih folder MP4:',
        search_dir=str(SHORTS_DIR) if hdd_ok else os.getcwd(),
        default=default_mp4_dir,
    )

    if not mp4_dir or not os.path.isdir(mp4_dir):
        print(f'❌ Folder tidak ditemukan: {mp4_dir}')
        sys.exit(1)

    print(f'  ✓ {mp4_dir}')

    # List MP4 files di folder
    mp4_files = sorted(glob.glob(os.path.join(mp4_dir, '*.mp4')))
    mp4_filenames = [os.path.basename(f) for f in mp4_files]
    print(f'  ✓ {len(mp4_filenames)} MP4 ditemukan')

    if len(mp4_filenames) != len(segments):
        print(f'  ⚠ Jumlah MP4 ({len(mp4_filenames)}) ≠ jumlah segment ({len(segments)})')
        print(f'    Aku tetap generate CSV dengan filename yang ada (sisanya pakai short-NNN.mp4)')
    print()

    # === Step 3: Film name ===
    print('▶ Step 3/7: Nama film (untuk template description)')
    # Default: nama folder MP4 atau nama JSON
    default_film = os.path.basename(mp4_dir.rstrip('/'))
    film_name = questionary.text(
        'Nama film:',
        default=default_film,
    ).ask()
    if not film_name:
        film_name = default_film
    print(f'  ✓ {film_name}')
    print()

    # === Step 4: Description template ===
    print('▶ Step 4/7: Template description (placeholder: {film_name}, {title})')
    print(f'  Default:')
    print(f'    Film {{film_name}} - Drama Mandarin Dub Indonesia.')
    print(f'    {{title}}')
    print(f'    ')
    print(f'    #shorts #drama #mandarin #dubbing #indonesia')
    use_default_desc = questionary.confirm('Pakai template default?', default=True).ask()

    if use_default_desc:
        desc_template = DEFAULT_DESC_TEMPLATE
    else:
        desc_template = questionary.text(
            'Custom template (use {film_name} dan {title}):',
            default=DEFAULT_DESC_TEMPLATE,
        ).ask()
        if not desc_template:
            desc_template = DEFAULT_DESC_TEMPLATE

    # Preview
    preview_desc = render_description(desc_template, film_name, segments[0]['title'])
    print(f'  Preview (segment 1):')
    for line in preview_desc.split('\n')[:4]:
        print(f'    {line}')
    print()

    # === Step 5: Tags + category ===
    print('▶ Step 5/7: Tags + category')
    tags = questionary.text(
        'Tags (pisah dengan koma):',
        default=DEFAULT_TAGS,
    ).ask()
    if not tags:
        tags = DEFAULT_TAGS
    print(f'  ✓ Tags: {tags}')

    category = questionary.select(
        'Category (YouTube):',
        choices=['Entertainment', 'Film & Animation', 'People & Blogs', 'Comedy', 'Education'],
        default=DEFAULT_CATEGORY,
    ).ask()
    print(f'  ✓ Category: {category}')
    print()

    # === Step 6: Schedule ===
    print('▶ Step 6/7: Schedule (mulai kapan + interval)')
    # Default: besok 12:00
    tomorrow = datetime.now() + timedelta(days=1)
    default_start = tomorrow.replace(hour=12, minute=0, second=0, microsecond=0)
    default_start_str = default_start.strftime('%Y-%m-%d %H:%M')

    start_str = questionary.text(
        f'Schedule mulai (YYYY-MM-DD HH:MM):',
        default=default_start_str,
    ).ask()
    if not start_str:
        start_dt = default_start
    else:
        try:
            start_dt = datetime.strptime(start_str, '%Y-%m-%d %H:%M')
        except ValueError:
            print(f'❌ Format salah. Pakai: YYYY-MM-DD HH:MM (mis. {default_start_str})')
            sys.exit(1)

    print(f'  ✓ Mulai: {format_schedule_for_manifest(start_dt)}')

    interval = questionary.select(
        'Interval antar publish:',
        choices=['30 menit', '1 jam', '2 jam', '3 jam', '6 jam', '1 hari (24 jam)'],
        default='1 jam',
    ).ask()

    # Parse interval
    interval_map = {
        '30 menit': 30,
        '1 jam': 60,
        '2 jam': 120,
        '3 jam': 180,
        '6 jam': 360,
        '1 hari (24 jam)': 1440,
    }
    interval_min = interval_map.get(interval, 60)
    print(f'  ✓ Interval: {interval}')
    print()

    # Generate schedule
    schedule = generate_schedule(len(segments), start_dt, interval_min)

    # === Step 7: Output ===
    print('▶ Step 7/7: Output file')
    safe_film = film_name.replace(' ', '_').replace('/', '_')[:60]
    default_csv = os.path.join(mp4_dir, f'{safe_film}.metadata.csv')
    default_manifest = os.path.join(mp4_dir, f'{safe_film}.manifest.txt')

    csv_path = questionary.text('CSV output:', default=default_csv).ask()
    if not csv_path:
        csv_path = default_csv

    manifest_path = questionary.text('Manifest output:', default=default_manifest).ask()
    if not manifest_path:
        manifest_path = default_manifest

    print(f'  ✓ CSV: {os.path.basename(csv_path)}')
    print(f'  ✓ Manifest: {os.path.basename(manifest_path)}')
    print()

    # === Summary ===
    total_dur = sum(s['duration'] for s in segments)
    last_sched = schedule[-1]
    print('╔' + '═' * 64 + '╗')
    print('║  📋 Ringkasan:' + ' ' * 49 + '║')
    print('╠' + '═' * 64 + '╣')
    print(f'║  JSON    : {os.path.basename(json_path)[:46]:<46}║')
    print(f'║  MP4 dir : {os.path.basename(mp4_dir)[:46]:<46}║')
    print(f'║  Film    : {film_name[:46]:<46}║')
    print(f'║  Segments: {len(segments):<46}║')
    print(f'║  Durasi  : {total_dur:.1f}s ({total_dur/60:.1f} menit){" " * (46-len(f"{total_dur:.1f}s ({total_dur/60:.1f} menit)"))}║')
    print(f'║  Mulai   : {format_schedule_for_csv(start_dt)[:46]:<46}║')
    print(f'║  Akhir   : {format_schedule_for_csv(last_sched)[:46]:<46}║')
    print(f'║  Interval: {interval[:46]:<46}║')
    print(f'║  Tags    : {tags[:46]:<46}║')
    print(f'║  CSV     : {os.path.basename(csv_path)[:46]:<46}║')
    print(f'║  Manifest: {os.path.basename(manifest_path)[:46]:<46}║')
    print('╚' + '═' * 64 + '╝')

    if not questionary.confirm('\nLanjut generate?', default=True).ask():
        print('Batal.')
        sys.exit(0)

    # === Generate ===
    print('\n' + '═' * 64)
    print('🚀 Generate CSV + manifest...')
    print('═' * 64)

    csv_size = generate_csv(segments, mp4_filenames, film_name, desc_template,
                            tags, category, schedule, csv_path)
    print(f'  ✓ CSV: {csv_path} ({csv_size/1024:.1f} KB)')

    manifest_size = generate_manifest(segments, mp4_filenames, film_name, desc_template,
                                      tags, category, schedule, manifest_path)
    print(f'  ✓ Manifest: {manifest_path} ({manifest_size/1024:.1f} KB)')

    print()
    print('═' * 64)
    print('✅ SELESAI!\n')
    print(f'  📁 CSV:      {csv_path}')
    print(f'  📁 Manifest: {manifest_path}')
    print()
    print('🎬 Langkah berikutnya:')
    print(f'   1. Buka YouTube Studio (studio.youtube.com)')
    print(f'   2. Drag {len(segments)} MP4 dari: {mp4_dir}')
    print(f'   3. Buka manifest.txt, copy-paste per video:')
    print(f'      - Title dari manifest')
    print(f'      - Description dari manifest')
    print(f'      - Tags dari manifest')
    print(f'      - Schedule: set manual (atau copy dari CSV)')
    print(f'   4. Set visibility = Schedule, paste waktu dari manifest')
    print('═' * 64)


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print('\n\n⏹ Dibatalkan user.')
        sys.exit(130)
    except Exception as e:
        print(f'\n❌ Error: {e}', file=sys.stderr)
        import traceback
        print(f'\nStack trace:\n{traceback.format_exc()[:2000]}', file=sys.stderr)
        sys.exit(1)
