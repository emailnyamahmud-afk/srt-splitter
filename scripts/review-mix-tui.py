#!/usr/bin/env python3
"""
review-mix-tui.py v1.0 — TUI #13: Review film (potong adegan + narasi + overlay).

User workflow:
  cd ~/Dubbing && source venv/bin/activate
  python3 review-mix-tui.py

Input:
  1. MP4 (video source, resolusi bebas)
  2. timestamps.json (dari Z.ai skill, format: [{start, end, title}])
  3. narasi.wav (dari edge-tui narration mode)

Output:
  review-final.mp4 (video terpotong + audio narasi + text overlay per adegan)

4 fase:
  1. Potong MP4 per segment (stream copy, super cepat)
  2. Concat segments → 1 video (stream copy)
  3. Generate overlay SRT dari JSON (text per adegan, cumulative timestamps)
  4. Mix video + narasi + burn overlay SRT (VideoToolbox M1 GPU)

Install: pip3 install questionary
"""

import os
import sys
import re
import json
import time
import subprocess
import shutil
import tempfile
from pathlib import Path

try:
    import questionary
except ImportError:
    print('\n❌ pip3 install questionary')
    sys.exit(1)

sys.path.insert(0, str(Path(__file__).parent))
from config import ensure_hdd, INPUT_DIR, TTS_DIR, REVIEW_DIR

VERSION = 'v1.0'


# ============================================================
# Helpers
# ============================================================

def find_files_in_dir(search_dir, extensions):
    files = []
    for ext in extensions:
        for f in Path(search_dir).glob(f'*.{ext}'):
            files.append(f.name)
        for f in Path(search_dir).glob(f'*.{ext.upper()}'):
            files.append(f.name)
    files.sort()
    return list(dict.fromkeys(files))


def find_ffmpeg():
    path = shutil.which('ffmpeg')
    if path:
        return path
    for loc in ['/usr/local/bin/ffmpeg', '/usr/bin/ffmpeg', '/opt/homebrew/bin/ffmpeg']:
        if os.path.isfile(loc):
            return loc
    print('\n❌ ffmpeg belum terinstall. Install: brew install ffmpeg')
    sys.exit(1)


def find_ffprobe():
    path = shutil.which('ffprobe')
    if path:
        return path
    for loc in ['/usr/local/bin/ffprobe', '/usr/bin/ffprobe', '/opt/homebrew/bin/ffprobe']:
        if os.path.isfile(loc):
            return loc
    print('\n❌ ffprobe belum terinstall. Install: brew install ffmpeg')
    sys.exit(1)


def get_duration(ffprobe, path):
    if not os.path.isfile(path):
        return 0
    result = subprocess.run([
        ffprobe, '-v', 'error', '-show_entries', 'format=duration',
        '-of', 'default=noprint_wrappers=1:nokey=1', path,
    ], capture_output=True, text=True)
    try:
        return float(result.stdout.strip())
    except Exception:
        return 0


def get_resolution(ffprobe, path):
    if not os.path.isfile(path):
        return (0, 0)
    result = subprocess.run([
        ffprobe, '-v', 'error', '-select_streams', 'v:0',
        '-show_entries', 'stream=width,height',
        '-of', 'csv=s=x:p=0', path,
    ], capture_output=True, text=True)
    try:
        w_str, h_str = result.stdout.strip().split('x')
        return (int(w_str), int(h_str))
    except Exception:
        return (0, 0)


def fmt_dur(s):
    if not s:
        return '00:00:00'
    h = int(s // 3600); m = int((s % 3600) // 60); sec = int(s % 60)
    return f'{h:02d}:{m:02d}:{sec:02d}'


def fmt_size(mb):
    if mb < 1024:
        return f'{mb:.1f}MB'
    return f'{mb/1024:.2f}GB'


def ts_to_srt_time(seconds):
    """Convert float seconds → SRT timestamp (HH:MM:SS,mmm)."""
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    ms = int((seconds - int(seconds)) * 1000)
    return f'{h:02d}:{m:02d}:{s:02d},{ms:03d}'


def clear_screen():
    os.system('clear' if os.name != 'nt' else 'cls')


def print_banner():
    clear_screen()
    print('╔' + '═' * 64 + '╗')
    print(f'║  🎬 Review Film {VERSION} (TUI #13)' + ' ' * 36 + '║')
    print('║  Potong adegan + narasi + overlay text                 ║')
    print('╚' + '═' * 64 + '╝')
    print()


def run_progress(cmd, total_duration_s, list_path=None, label=''):
    """Run ffmpeg dengan progress bar sederhana."""
    try:
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                text=True, bufsize=1)
    except FileNotFoundError:
        print('  ❌ ffmpeg gak ditemukan')
        return False
    last_pct = -1
    try:
        for line in proc.stdout:
            line = line.rstrip()
            if not line or '=' not in line:
                continue
            k, v = line.split('=', 1)
            k = k.strip(); v = v.strip()
            if k == 'out_time_ms' and total_duration_s > 0:
                try:
                    cur = int(v) / 1_000_000
                    pct = min(int(cur * 100 / total_duration_s), 99)
                    if pct > last_pct:
                        bar = '█' * (pct // 2) + '░' * (50 - pct // 2)
                        prefix = f'  {label} ' if label else '  '
                        print(f'\r{prefix}[{bar}] {pct}% ({fmt_dur(cur)}/{fmt_dur(total_duration_s)})',
                              end='', flush=True)
                        last_pct = pct
                except ValueError:
                    pass
            elif k == 'progress' and v == 'end':
                print(f'\r  {label} [{"█" * 50}] 100% ({fmt_dur(total_duration_s)})' if label else f'\r  [{"█" * 50}] 100% ({fmt_dur(total_duration_s)})')
                break
        proc.wait()
    except KeyboardInterrupt:
        print('\n  ⚠ Dibatalkan')
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
        return False
    if list_path and os.path.exists(list_path):
        os.unlink(list_path)
    return proc.returncode == 0


def select_file(prompt, extensions, search_dirs):
    """Pick file dari multiple search dirs."""
    available = []
    for d in search_dirs:
        if d and Path(d).exists():
            for ext in extensions:
                for f in Path(d).glob(f'*.{ext}'):
                    available.append(str(f))
                for f in Path(d).glob(f'*.{ext.upper()}'):
                    available.append(str(f))
    available = sorted(set(available))
    if not available:
        path = questionary.text(f'{prompt} (ketik path lengkap):').ask()
        return path
    choices = [os.path.basename(f) for f in available] + ['[Ketik path manual]']
    sel = questionary.select(prompt, choices=choices, default=choices[0]).ask()
    if sel == '[Ketik path manual]':
        return questionary.text(f'{prompt} (ketik path lengkap):').ask()
    # Match basename → full path
    for f in available:
        if os.path.basename(f) == sel:
            return f
    return sel


def parse_timestamps_json(json_path):
    """Parse JSON timestamps. Format: [{start, end, title}, ...]."""
    with open(json_path, 'r', encoding='utf-8') as f:
        content = f.read().strip()
    if not content:
        raise ValueError('JSON file kosong')
    try:
        data = json.loads(content)
    except json.JSONDecodeError as e:
        raise ValueError(f'JSON parse gagal: {e}')
    # Handle wrapper
    if isinstance(data, dict):
        for key in ('segments', 'timestamps', 'cuts', 'data'):
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
            raise ValueError(f'Item {i+1} bukan object')
        if 'start' not in item or 'end' not in item:
            raise ValueError(f'Item {i+1} missing start/end')
        start = float(item['start'])
        end = float(item['end'])
        if end <= start:
            raise ValueError(f'Item {i+1}: end <= start')
        title = item.get('title', f'Adegan {i+1}').strip()
        if not title:
            title = f'Adegan {i+1}'
        segments.append({
            'start': start,
            'end': end,
            'title': title,
            'duration': end - start,
        })
    if not segments:
        raise ValueError('JSON kosong')
    return segments


def generate_overlay_srt(segments, output_path, display_seconds=5):
    """Generate SRT overlay dari JSON segments (cumulative timestamps for concatenated video).

    Text tampil display_seconds (default 5) di awal tiap adegan.
    """
    cumulative = 0.0
    srt_lines = []
    for i, seg in enumerate(segments, 1):
        start_ts = cumulative
        end_ts = cumulative + min(display_seconds, seg['duration'])
        srt_lines.append(str(i))
        srt_lines.append(f'{ts_to_srt_time(start_ts)} --> {ts_to_srt_time(end_ts)}')
        srt_lines.append(seg['title'])
        srt_lines.append('')
        cumulative += seg['duration']
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(srt_lines))
    return output_path


# ============================================================
# Main
# ============================================================

def main():
    print_banner()

    if not ensure_hdd():
        return

    ffmpeg = find_ffmpeg()
    ffprobe = find_ffprobe()

    print(f'  Output : {REVIEW_DIR}')
    print()

    # Step 1: Pilih MP4 source
    print('▶ Step 1: Pilih MP4 source (video asli)')
    mp4 = select_file('MP4 source:', ['mp4'], [str(INPUT_DIR), str(REVIEW_DIR), os.getcwd()])
    if not mp4 or not os.path.isfile(mp4):
        print(f'  ❌ File gak ditemukan: {mp4}')
        return
    mp4_dur = get_duration(ffprobe, mp4)
    mp4_w, mp4_h = get_resolution(ffprobe, mp4)
    print(f'  ✓ {os.path.basename(mp4)} ({mp4_w}x{mp4_h}, {fmt_dur(mp4_dur)})')
    print()

    # Step 2: Pilih timestamps.json
    print('▶ Step 2: Pilih timestamps.json (dari Z.ai skill)')
    json_path = select_file('JSON timestamps:', ['json'], [str(INPUT_DIR), str(REVIEW_DIR), os.getcwd()])
    if not json_path or not os.path.isfile(json_path):
        print(f'  ❌ File gak ditemukan: {json_path}')
        return
    try:
        segments = parse_timestamps_json(json_path)
    except ValueError as e:
        print(f'  ❌ {e}')
        return
    total_review_dur = sum(s['duration'] for s in segments)
    print(f'  ✓ {os.path.basename(json_path)} ({len(segments)} adegan, total {fmt_dur(total_review_dur)})')
    for i, s in enumerate(segments, 1):
        print(f'    [{i}] {fmt_dur(s["start"])}-{fmt_dur(s["end"])} ({fmt_dur(s["duration"])}) — {s["title"]}')
    print()

    # Step 3: Pilih narasi.wav
    print('▶ Step 3: Pilih narasi.wav (dari edge-tui narration mode)')
    narasi = select_file('Narasi WAV:', ['wav'], [str(TTS_DIR), str(REVIEW_DIR), os.getcwd()])
    if not narasi or not os.path.isfile(narasi):
        print(f'  ❌ File gak ditemukan: {narasi}')
        return
    narasi_dur = get_duration(ffprobe, narasi)
    print(f'  ✓ {os.path.basename(narasi)} ({fmt_dur(narasi_dur)})')
    print()

    # Step 4: Output path
    mp4_stem = Path(mp4).stem
    default_output = str(REVIEW_DIR / f'{mp4_stem}-review.mp4')
    print('▶ Step 4: Output path')
    output = questionary.text('Output path (Enter untuk default):', default=default_output).ask()
    if not output or not output.strip():
        output = default_output
    else:
        output = os.path.expanduser(output.strip())
    parent = os.path.dirname(output)
    if parent and not os.path.exists(parent):
        os.makedirs(parent, exist_ok=True)
    print(f'  ✓ {output}')
    print()

    # Step 5: Konfirmasi
    print('═' * 64)
    print('▶ Konfirmasi')
    print('═' * 64)
    print(f'\n  Video    : {os.path.basename(mp4)} ({mp4_w}x{mp4_h}, {fmt_dur(mp4_dur)})')
    print(f'  Segments : {len(segments)} adegan (total {fmt_dur(total_review_dur)})')
    print(f'  Narasi   : {os.path.basename(narasi)} ({fmt_dur(narasi_dur)})')
    print(f'  Output   : {output}')

    # Warning kalau durasi narasi vs total adegan beda jauh
    if abs(narasi_dur - total_review_dur) > 30:
        print(f'\n  ⚠ Durasi narasi ({fmt_dur(narasi_dur)}) vs total adegan ({fmt_dur(total_review_dur)}) beda jauh!')
        print(f'    Audio narasi mungkin lebih cepat/lambat dari video.')

    if not questionary.confirm('\nLanjut review mix?', default=True).ask():
        print('Dibatalkan.')
        return

    # Temp dir di HDD (BUKAN SSD)
    temp_dir_parent = REVIEW_DIR.parent / '.review_tmp'
    temp_dir_parent.mkdir(parents=True, exist_ok=True)
    temp_dir = tempfile.mkdtemp(prefix='review_tmp_', dir=str(temp_dir_parent))

    # ============================================================
    # Fase 1: Potong MP4 per segment (stream copy, super cepat)
    # ============================================================
    print('\n' + '═' * 64)
    print('▶ Fase 1: Potong MP4 per segment (stream copy)')
    print('═' * 64)
    print()

    temp_parts = []
    for i, seg in enumerate(segments, 1):
        part_path = os.path.join(temp_dir, f'part_{i:03d}.mp4')
        temp_parts.append(part_path)
        seg_dur = seg['duration']
        print(f'  [{i}/{len(segments)}] {seg["title"]} ({fmt_dur(seg_dur)})')

        cmd = [ffmpeg, '-y',
               '-ss', str(seg['start']),
               '-to', str(seg['end']),
               '-i', mp4,
               '-c', 'copy',
               '-avoid_negative_ts', 'make_zero',
               '-movflags', '+faststart',
               '-progress', 'pipe:1', '-nostats',
               part_path]

        if not run_progress(cmd, seg_dur, label=f'[{i}/{len(segments)}]'):
            print(f'\n  ❌ Gagal potong segment {i}: {seg["title"]}')
            # Cleanup
            for tf in temp_parts:
                if os.path.exists(tf):
                    os.unlink(tf)
            try:
                os.rmdir(temp_dir)
            except OSError:
                pass
            return
    print()

    # ============================================================
    # Fase 2: Concat segments → 1 video (stream copy)
    # ============================================================
    print('▶ Fase 2: Concat segments (stream copy)')
    print('═' * 64)

    concat_list = os.path.join(temp_dir, 'concat_list.txt')
    with open(concat_list, 'w') as f:
        for tf in temp_parts:
            safe = tf.replace("'", r"'\''")
            f.write(f"file '{safe}'\n")

    concat_output = os.path.join(temp_dir, 'concatenated.mp4')
    cmd = [ffmpeg, '-y', '-f', 'concat', '-safe', '0',
           '-i', concat_list, '-c', 'copy',
           '-movflags', '+faststart',
           '-progress', 'pipe:1', '-nostats', concat_output]

    if not run_progress(cmd, total_review_dur):
        print('\n  ❌ Gagal concat')
        for tf in temp_parts:
            if os.path.exists(tf):
                os.unlink(tf)
        if os.path.exists(concat_list):
            os.unlink(concat_list)
        if os.path.exists(concat_output):
            os.unlink(concat_output)
        try:
            os.rmdir(temp_dir)
        except OSError:
            pass
        return
    print()

    # ============================================================
    # Fase 3: Generate overlay SRT dari JSON
    # ============================================================
    print('▶ Fase 3: Generate overlay SRT (text per adegan)')
    print('═' * 64)
    overlay_srt = os.path.join(temp_dir, 'overlay.srt')
    generate_overlay_srt(segments, overlay_srt, display_seconds=5)
    print(f'  ✓ {len(segments)} cues overlay (text tampil 5 detik per adegan)')
    print()

    # ============================================================
    # Fase 4: Mix video + narasi + burn overlay SRT
    # ============================================================
    print('▶ Fase 4: Mix video + narasi + overlay (VideoToolbox M1)')
    print('═' * 64)

    # Escape path untuk subtitles filter
    srt_escaped = overlay_srt.replace('\\', '\\\\').replace(':', '\\:').replace("'", "\\'")

    # Style: font 24pt, putih outline hitam, top-center, 5 detik per adegan
    force_style = (
        "Fontsize=24,"
        "PrimaryColour=&H00FFFFFF,"
        "OutlineColour=&H80000000,"
        "BorderStyle=1,"
        "Outline=2,"
        "Shadow=1,"
        "Alignment=8,"
        "MarginV=40,"
        "Justify=2"
    )

    subtitle_filter = f"[0:v]subtitles='{srt_escaped}':force_style='{force_style}'[vout]"

    cmd = [ffmpeg, '-y',
           '-i', concat_output,
           '-i', narasi,
           '-filter_complex', subtitle_filter,
           '-map', '[vout]', '-map', '1:a',
           '-c:v', 'h264_videotoolbox', '-b:v', '2M',
           '-c:a', 'aac', '-b:a', '192k', '-ar', '48000', '-ac', '2',
           '-movflags', '+faststart',
           '-progress', 'pipe:1', '-nostats',
           output]

    if not run_progress(cmd, total_review_dur):
        print('\n  ❌ Gagal mix video + narasi')
        # Cleanup
        for tf in temp_parts:
            if os.path.exists(tf):
                os.unlink(tf)
        if os.path.exists(concat_list):
            os.unlink(concat_list)
        if os.path.exists(concat_output):
            os.unlink(concat_output)
        if os.path.exists(overlay_srt):
            os.unlink(overlay_srt)
        try:
            os.rmdir(temp_dir)
        except OSError:
            pass
        return

    # ============================================================
    # Cleanup temp files
    # ============================================================
    print('\n▶ Cleanup temp files...')
    for tf in temp_parts:
        if os.path.exists(tf):
            os.unlink(tf)
    if os.path.exists(concat_list):
        os.unlink(concat_list)
    if os.path.exists(concat_output):
        os.unlink(concat_output)
    if os.path.exists(overlay_srt):
        os.unlink(overlay_srt)
    try:
        os.rmdir(temp_dir)
    except OSError:
        pass

    # ============================================================
    # Hasil
    # ============================================================
    if os.path.exists(output):
        size_mb = os.path.getsize(output) / 1024 / 1024
        out_dur = get_duration(ffprobe, output)
        out_w, out_h = get_resolution(ffprobe, output)
        print(f'\n📁 Output: {os.path.basename(output)} ({fmt_size(size_mb)})')
        print(f'   Path   : {output}')
        print(f'   Durasi : {fmt_dur(out_dur)}')
        print(f'   Res    : {out_w}x{out_h}')
        print(f'   Segments: {len(segments)} adegan')
        print(f'   Overlay : text per adegan (5 detik tampil)')
        print(f'\n🎬 VLC test:')
        print(f'   - Play dari awal → narasi + overlay text harus muncul')
        print(f'   - Cek transisi antar adegan → harus mulus')
        print(f'   - Cek audio sync → narasi cocok visual')
    else:
        print('\n  ❌ Output gak ditemukan')
    print('═' * 64)


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print('\n⏹ Dibatalkan.')
        sys.exit(130)
    except Exception as e:
        print(f'\n❌ {e}', file=sys.stderr)
        import traceback
        print(f'\n{traceback.format_exc()[:500]}', file=sys.stderr)
        sys.exit(1)
