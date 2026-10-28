#!/usr/bin/env python3
"""
shorts-tui.py v1.0 — Pecah MP4 final jadi N shorts (vertical, hardsub, sudah ada).

Workflow:
  1. User paste SRT Indonesia ke ChatGPT/Claude/Gemini/Dola AI → minta pilih 60 segment
     menarik untuk Shorts (max 60 detik per segment, mulai di awal cue)
     → AI return JSON array [{start, end, title}]
     → User save ke file, mis. HDD/shorts/S5-HQ.timestamps.json
  2. User jalankan shorts-tui.py:
     - Pick JSON timestamps (dari cwd + HDD)
     - Pick MP4 final (sudah vertikal 9:16, sudah hardsub Indonesia)
     - Pick output dir (default: HDD/shorts/{film-name}/)
     - TUI ffmpeg cut per segment (stream copy, super cepat)
  3. Output: N MP4 di folder per-film (default 60), siap upload YouTube Shorts/TikTok/Reels

Input MP4 harus SUDAH:
- Vertikal 9:16 (1080×1920 atau 720×1280)
- Hardsub Indonesia (Mode B/D/F dari mix-tui)

Output per short:
- Stream copy (-c copy) — no re-encode, super cepat (~0.5 detik per short)
- 60 shorts × 0.5s = ~2 menit total (default production: 60 shorts per film)

Format JSON (yang user kasih dari ChatGPT):
  [
    {"start": 12.5, "end": 65.3, "title": "Lin Zhao tiba di Qin family"},
    {"start": 145.2, "end": 198.7, "title": "Konfrontasi paman"},
    ...
  ]

Install:
  pip3 install questionary
  # ffmpeg wajib (sudah ada kalau pakai TUI lain)

Usage:
  python3 shorts-tui.py
"""

import os
import sys
import json
import subprocess
import shutil
from pathlib import Path
from typing import List, Dict, Optional, Tuple

try:
    import questionary
except ImportError:
    print('\n❌ pip3 install questionary')
    sys.exit(1)


VERSION = 'v1.0'

# Maximum duration untuk Shorts/TikTok/Reels (detik)
# YouTube Shorts: 60s, TikTok: 90s, Instagram Reels: 90s
# Default 60 (YouTube Shorts strict)
SHORT_MAX_DURATION = 60.0


def find_ffmpeg():
    """Cari ffmpeg di PATH atau lokasi umum Mac."""
    path = shutil.which('ffmpeg')
    if path:
        return path
    for loc in ['/usr/local/bin/ffmpeg', '/usr/bin/ffmpeg', '/opt/homebrew/bin/ffmpeg']:
        if os.path.isfile(loc):
            return loc
    return None


def find_ffprobe():
    """Cari ffprobe di PATH."""
    path = shutil.which('ffprobe')
    if path:
        return path
    for loc in ['/usr/local/bin/ffprobe', '/usr/bin/ffprobe', '/opt/homebrew/bin/ffprobe']:
        if os.path.isfile(loc):
            return loc
    return None


def sanitize_dirname(name: str) -> str:
    """Buat nama folder aman: alphanumeric + dash/underscore only."""
    import re
    name = re.sub(r'[\\/:*?"<>|]', '', name).strip()
    name = re.sub(r'\s+', '_', name)
    if len(name) > 80:
        name = name[:80]
    return name or 'shorts'


def find_files_in_dir(search_dir: str, extensions: List[str]) -> List[str]:
    """Glob files by extension (non-recursive, mirip mix-tui pattern)."""
    import glob
    files = []
    for ext in extensions:
        for f in glob.glob(os.path.join(search_dir, f'*.{ext}')):
            files.append(os.path.basename(f))
        for f in glob.glob(os.path.join(search_dir, f'*.{ext.upper()}')):
            files.append(os.path.basename(f))
    files.sort()
    return list(dict.fromkeys(files))


def select_file(prompt: str, extensions: List[str], search_dir: Optional[str] = None,
                default: Optional[str] = None) -> Optional[str]:
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


# ============================================================
# JSON timestamp parser + validator
# ============================================================

def parse_timestamps_json(json_path: str) -> List[Dict]:
    """Parse JSON file → list of {start, end, title}.

    Format:
      [{"start": 12.5, "end": 65.3, "title": "..."}, ...]

    Atau kalau user kasih format lain (mis. SRT-like), tetap normalisasi.
    """
    with open(json_path, 'r', encoding='utf-8') as f:
        content = f.read().strip()

    if not content:
        raise ValueError('JSON file kosong')

    # Coba parse sebagai JSON
    try:
        data = json.loads(content)
    except json.JSONDecodeError as e:
        raise ValueError(f'JSON parse gagal: {e}')

    # Normalize format
    if isinstance(data, dict):
        # Mungkin {"segments": [...]} atau {"shorts": [...]}
        for key in ('segments', 'shorts', 'timestamps', 'cuts', 'data'):
            if key in data and isinstance(data[key], list):
                data = data[key]
                break
        else:
            # Single segment di root
            if 'start' in data and 'end' in data:
                data = [data]
            else:
                raise ValueError('JSON root bukan array. Expected [{"start": ..., "end": ...}]')

    if not isinstance(data, list):
        raise ValueError('JSON bukan array. Expected [{"start": ..., "end": ...}]')

    segments = []
    for i, item in enumerate(data):
        if not isinstance(item, dict):
            raise ValueError(f'Item {i+1} bukan object: {item!r}')
        if 'start' not in item or 'end' not in item:
            raise ValueError(f'Item {i+1} missing "start" atau "end": {item!r}')

        start = item['start']
        end = item['end']

        # Coerce to float
        try:
            start = float(start)
            end = float(end)
        except (TypeError, ValueError):
            raise ValueError(f'Item {i+1} start/end bukan angka: start={start!r}, end={end!r}')

        if start < 0 or end < 0:
            raise ValueError(f'Item {i+1} start/end negatif: start={start}, end={end}')

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
        raise ValueError('JSON kosong — tidak ada segment')

    return segments


def validate_segments(segments: List[Dict], video_duration: Optional[float] = None) -> List[Tuple[int, str]]:
    """Validasi setiap segment. Return list (index, warning) untuk yang bermasalah."""
    warnings = []
    for i, seg in enumerate(segments):
        idx = i + 1
        # Cek durasi vs max shorts
        if seg['duration'] > SHORT_MAX_DURATION:
            warnings.append((idx, f"Durasi {seg['duration']:.1f}s > max {SHORT_MAX_DURATION}s Shorts"))
        # Cek overlap dengan seg sebelumnya (optional warning)
        if i > 0 and seg['start'] < segments[i-1]['end']:
            warnings.append((idx, f"Overlap dengan segment sebelumnya (start {seg['start']} < prev end {segments[i-1]['end']})"))
        # Cek kalau ada video_duration dan seg melampaui
        if video_duration and seg['end'] > video_duration:
            warnings.append((idx, f"End {seg['end']} > durasi video {video_duration}"))
    return warnings


# ============================================================
# ffprobe untuk durasi video
# ============================================================

def get_video_duration(ffprobe_path: str, video_path: str) -> Optional[float]:
    """Ambil durasi video via ffprobe. Return detik atau None kalau gagal."""
    try:
        result = subprocess.run(
            [ffprobe_path, '-v', 'error', '-show_entries', 'format=duration',
             '-of', 'default=noprint_wrappers=1:nokey=1', video_path],
            capture_output=True, text=True, timeout=15
        )
        if result.returncode == 0 and result.stdout.strip():
            return float(result.stdout.strip())
    except (ValueError, subprocess.TimeoutExpired):
        pass
    return None


# ============================================================
# ffmpeg cut per segment (stream copy)
# ============================================================

def cut_segment_stream_copy(ffmpeg: str, video: str, start: float, end: float,
                            output: str) -> Tuple[bool, str]:
    """Cut 1 segment dengan stream copy (no re-encode, super cepat).

    ffmpeg quirk: `-ss` sebelum `-i` interpretasi `-to` jadi offset dari seek,
    bukan timestamp absolut. Fix: taruh `-i` pertama, baru `-ss` `-to` setelahnya.

    Return (success, message).
    """
    cmd = [
        ffmpeg,
        '-i', video,
        '-ss', f'{start:.3f}',
        '-to', f'{end:.3f}',
        '-c', 'copy',
        '-avoid_negative_ts', 'make_zero',
        '-y',  # overwrite output
        output,
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        if result.returncode != 0:
            return (False, f'ffmpeg error: {result.stderr[:300]}')
        if not os.path.isfile(output) or os.path.getsize(output) < 1024:
            return (False, 'Output file kosong atau tidak terbentuk')
        return (True, f'OK ({os.path.getsize(output)/1024/1024:.1f} MB)')
    except subprocess.TimeoutExpired:
        return (False, 'ffmpeg timeout (120s)')
    except Exception as e:
        return (False, f'Exception: {e}')


def cut_segment_reencode(ffmpeg: str, video: str, start: float, end: float,
                         output: str) -> Tuple[bool, str]:
    """Cut 1 segment dengan re-encode (clean cut, ~3-5 detik per short).

    ffmpeg quirk: sama dengan stream_copy, `-i` dulu baru `-ss -to`.

    Return (success, message).
    """
    cmd = [
        ffmpeg,
        '-i', video,
        '-ss', f'{start:.3f}',
        '-to', f'{end:.3f}',
        '-c:v', 'libx264', '-crf', '23', '-preset', 'fast',
        '-c:a', 'aac', '-b:a', '128k',
        '-movflags', '+faststart',
        '-y',
        output,
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        if result.returncode != 0:
            return (False, f'ffmpeg error: {result.stderr[:300]}')
        if not os.path.isfile(output) or os.path.getsize(output) < 1024:
            return (False, 'Output file kosong atau tidak terbentuk')
        return (True, f'OK ({os.path.getsize(output)/1024/1024:.1f} MB)')
    except subprocess.TimeoutExpired:
        return (False, 'ffmpeg timeout (300s)')
    except Exception as e:
        return (False, f'Exception: {e}')


# ============================================================
# Main TUI flow
# ============================================================

def clear_screen():
    os.system('clear' if os.name != 'nt' else 'cls')


def print_banner():
    clear_screen()
    pid_str = f'PID {os.getpid()}'
    title = f'✂️  Shorts Splitter {VERSION} ({pid_str})'
    pad_title = max(0, 66 - len(title) - 2)
    print('╔' + '═' * 64 + '╗')
    print('║  ' + title + ' ' * pad_title + '║')
    print('║  Pecah MP4 final jadi N shorts (stream copy, cepat)    ║')
    print('╚' + '═' * 64 + '╝')
    print()


def main():
    print_banner()

    # Check ffmpeg
    ffmpeg = find_ffmpeg()
    if not ffmpeg:
        print('❌ ffmpeg belum terinstall. Install: brew install ffmpeg')
        sys.exit(1)

    ffprobe = find_ffprobe()
    print(f'ffmpeg:  {ffmpeg}')
    print(f'ffprobe: {ffprobe or "(tidak ada — skip cek durasi)"}')
    print()

    # === Step 1: Pick JSON timestamps ===
    print('▶ Step 1/4: Pilih file JSON timestamps (dari ChatGPT/Claude/Gemini)')
    # Search di cwd + HDD/shorts/ + HDD/mix/ (taruh JSON di HDD/shorts/ supaya rapi)
    from config import MIX_DIR, SHORTS_DIR, ensure_hdd, HDD_BASE
    hdd_ok = ensure_hdd()

    # Search JSON prioritas: cwd → SHORTS_DIR → MIX_DIR (HDD_BASE root dibuang, biar rapi)
    json_search_dirs = [os.getcwd()]
    if hdd_ok:
        json_search_dirs.append(str(SHORTS_DIR))
        json_search_dirs.append(str(MIX_DIR))

    json_choices_dirs = json_search_dirs
    json_path = None
    json_choice = questionary.select(
        'Cari JSON di folder mana?',
        choices=json_choices_dirs + ['[Ketik path manual]'],
        default=json_choices_dirs[0],
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

    # Parse + validate JSON
    try:
        segments = parse_timestamps_json(json_path)
    except ValueError as e:
        print(f'\n❌ JSON parse gagal: {e}')
        print(f'   Format yang diharapkan:')
        print(f'   [{{"start": 12.5, "end": 65.3, "title": "..."}}, ...]')
        sys.exit(1)

    print(f'  ✓ {len(segments)} segment ditemukan')
    print()

    # === Step 2: Pick MP4 final ===
    print('▶ Step 2/4: Pilih MP4 final (sudah vertikal 9:16, sudah hardsub)')
    if hdd_ok:
        mp4_search = str(MIX_DIR)
    else:
        mp4_search = os.getcwd()
    mp4_choice = questionary.select(
        f'Cari MP4 di folder mana?',
        choices=[mp4_search, os.getcwd(), '[Ketik path manual]'],
        default=mp4_search,
    ).ask()

    if mp4_choice == '[Ketik path manual]':
        mp4_path = questionary.text('Path MP4:').ask()
    else:
        mp4_path = select_file('Pilih MP4 final:', ['mp4'], search_dir=mp4_choice)

    if not mp4_path:
        print('Batal.')
        sys.exit(0)

    mp4_path = os.path.expanduser(mp4_path)
    if not os.path.isfile(mp4_path):
        print(f'❌ File tidak ditemukan: {mp4_path}')
        sys.exit(1)

    mp4_size_mb = os.path.getsize(mp4_path) / 1024 / 1024
    print(f'  ✓ {os.path.basename(mp4_path)} ({mp4_size_mb:.1f} MB)')

    # Cek durasi video via ffprobe
    video_duration = None
    if ffprobe:
        video_duration = get_video_duration(ffprobe, mp4_path)
        if video_duration:
            print(f'  ✓ Durasi video: {video_duration:.1f}s ({video_duration/60:.1f} menit)')
    print()

    # === Validate segments vs video duration ===
    warnings = validate_segments(segments, video_duration)
    if warnings:
        print('  ⚠ Warnings:')
        for idx, msg in warnings:
            print(f'    Segment {idx}: {msg}')
        proceed = questionary.confirm('\n  Lanjut meski ada warning?', default=True).ask()
        if not proceed:
            print('Batal.')
            sys.exit(0)
        print()

    # === Step 3: Output dir (default: HDD/shorts/{film-name}/) ===
    print('▶ Step 3/4: Pilih output dir')
    film_name = sanitize_dirname(Path(mp4_path).stem)
    if hdd_ok:
        default_output_dir = os.path.join(str(SHORTS_DIR), film_name)
    else:
        default_output_dir = os.path.join(os.getcwd(), 'shorts', film_name)
    output_dir = questionary.text(
        'Output dir (default: subfolder per film):',
        default=default_output_dir,
    ).ask()
    if not output_dir:
        output_dir = default_output_dir
    output_dir = os.path.expanduser(output_dir)
    os.makedirs(output_dir, exist_ok=True)
    print(f'  ✓ {output_dir}')
    print()

    # === Step 4: Cut mode + title prefix ===
    print('▶ Step 4/4: Pilih mode cut')
    cut_mode = questionary.select(
        'Mode cut:',
        choices=[
            'Stream copy (cepat, ~0.5s per short, mungkin ada keyframe glitch)',
            'Re-encode (clean, ~3-5s per short, total ~3 menit)',
        ],
        default='Stream copy (cepat, ~0.5s per short, mungkin ada keyframe glitch)',
    ).ask()

    is_stream_copy = 'Stream copy' in cut_mode
    print(f'  ✓ {"Stream copy" if is_stream_copy else "Re-encode"}')
    print()

    title_prefix = questionary.text(
        'Title prefix untuk output file (default: nama MP4):',
        default=film_name,
    ).ask()
    if not title_prefix:
        title_prefix = film_name
    print(f'  ✓ {title_prefix}')
    print()

    # === Summary + confirm ===
    total_dur = sum(s['duration'] for s in segments)
    print('╔' + '═' * 64 + '╗')
    print('║  📋 Ringkasan:' + ' ' * 49 + '║')
    print('╠' + '═' * 64 + '╣')
    print(f'║  JSON    : {os.path.basename(json_path)[:46]:<46}║')
    print(f'║  MP4     : {os.path.basename(mp4_path)[:46]:<46}║')
    print(f'║  Segments: {len(segments):<46}║')
    print(f'║  Total   : {total_dur:.1f}s ({total_dur/60:.1f} menit){" " * (46-len(f"{total_dur:.1f}s ({total_dur/60:.1f} menit)"))}║')
    print(f'║  Mode    : {"stream copy" if is_stream_copy else "re-encode"}{" " * (46-len("stream copy" if is_stream_copy else "re-encode"))}║')
    print(f'║  Dir     : {os.path.basename(output_dir)[:46]:<46}║')
    print(f'║  Prefix  : {title_prefix[:46]:<46}║')
    print('╚' + '═' * 64 + '╝')

    if not questionary.confirm('\nLanjut split?', default=True).ask():
        print('Batal.')
        sys.exit(0)

    # === Execute ffmpeg per segment ===
    print('\n' + '═' * 64)
    print('🚀 Mulai split...')
    print('═' * 64 + '\n')

    success_count = 0
    fail_count = 0
    first_error = ''
    start_time = os.path.time() if hasattr(os, 'time') else __import__('time').time()
    import time as time_mod
    start_time = time_mod.time()

    for i, seg in enumerate(segments):
        idx = i + 1
        # Output filename: {prefix}-short-{NNN}.mp4 (3-digit padding)
        output_file = os.path.join(output_dir, f'{title_prefix}-short-{idx:03d}.mp4')

        # Estimate ETA
        elapsed = time_mod.time() - start_time
        eta = (elapsed / max(1, idx)) * (len(segments) - idx) if idx > 0 else 0

        print(f'  [{idx}/{len(segments)}] {seg["start"]:.1f}-{seg["end"]:.1f}s ({seg["duration"]:.1f}s) | ETA {eta:.0f}s')

        if is_stream_copy:
            ok, msg = cut_segment_stream_copy(ffmpeg, mp4_path, seg['start'], seg['end'], output_file)
        else:
            ok, msg = cut_segment_reencode(ffmpeg, mp4_path, seg['start'], seg['end'], output_file)

        if ok:
            success_count += 1
            print(f'    ✓ {msg}')
        else:
            fail_count += 1
            if not first_error:
                first_error = msg
            print(f'    ❌ {msg}')

    # === Summary ===
    total_elapsed = time_mod.time() - start_time
    print('\n' + '═' * 64)
    print('✅ SELESAI!\n')
    print(f'  Sukses: {success_count}/{len(segments)} shorts')
    print(f'  Gagal:  {fail_count}/{len(segments)} shorts')
    print(f'  Waktu:  {total_elapsed:.1f}s')
    if first_error:
        print(f'  Error pertama: {first_error[:80]}')
    print()

    # List output files
    if success_count > 0:
        print(f'📁 Output di: {output_dir}')
        output_files = sorted(Path(output_dir).glob(f'{title_prefix}-short-*.mp4'))
        total_size_mb = sum(f.stat().st_size for f in output_files) / 1024 / 1024
        print(f'   {len(output_files)} file, total {total_size_mb:.1f} MB')
        if len(output_files) <= 5:
            for f in output_files:
                print(f'   • {f.name}')
        else:
            for f in output_files[:3]:
                print(f'   • {f.name}')
            print(f'   ... ({len(output_files)-6} more)')
            for f in output_files[-3:]:
                print(f'   • {f.name}')

    print()
    print('🎬 Langkah berikutnya:')
    print(f'   1. Cek hasil di: {output_dir}')
    print(f'   2. Upload ke YouTube Shorts / TikTok / Reels')
    print(f'   3. Title suggestion dari JSON: {os.path.basename(json_path)}')
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
