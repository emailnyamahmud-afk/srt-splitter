#!/usr/bin/env python3
"""
konten-tui.py v1.0 — TUI #14: Konten sejarah (images → video + narasi + Ken Burns).

User workflow:
  cd ~/Dubbing && source venv/bin/activate
  python3 konten-tui.py

Input:
  1. narasi.wav (dari edge-tui v7.5 narration mode)
  2. timestamps.json (dari Z.ai skill, format: [{start, end, image_prompt, title}])
  3. Folder images (01.jpg, 02.jpg, ... dari Google Flow)
  4. (opsional) backsound.mp3 (dari Suno atau sumber lain)

Output:
  konten-final.mp4 (1920x1080, Ken Burns effect, text overlay, audio narasi + backsound)

Fase:
  1. Load images, urutin sesuai JSON (match by index)
  2. Generate Ken Burns video per image (zoompan, alternate zoom-in/zoom-out)
  3. Generate overlay SRT dari JSON (text per segment, 3 detik tampil)
  4. Concat all image videos → 1 video
  5. Mix video + narasi + backsound + burn overlay SRT

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
from config import ensure_hdd, TTS_DIR, KONTEN_DIR, INPUT_DIR

VERSION = 'v1.0'
OUTPUT_W = 1920
OUTPUT_H = 1080


# ============================================================
# Helpers
# ============================================================

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
    print(f'║  📚 Konten Sejarah {VERSION} (TUI #14)' + ' ' * 32 + '║')
    print('║  Images → Video + Ken Burns + Narasi                ║')
    print('╚' + '═' * 64 + '╝')
    print()


def natural_sort_key(s):
    return [int(text) if text.isdigit() else text.lower()
            for text in re.split(r'(\d+)', s)]


def parse_content_json(json_path):
    """Parse JSON timestamps for konten.
    Format: [{start, end, image_prompt, title}, ...]
    """
    with open(json_path, 'r', encoding='utf-8') as f:
        content = f.read().strip()
    if not content:
        raise ValueError('JSON file kosong')
    try:
        data = json.loads(content)
    except json.JSONDecodeError as e:
        raise ValueError(f'JSON parse gagal: {e}')
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
        title = item.get('title', f'Segment {i+1}').strip()
        if not title:
            title = f'Segment {i+1}'
        image_prompt = item.get('image_prompt', '').strip()
        segments.append({
            'start': start,
            'end': end,
            'title': title,
            'image_prompt': image_prompt,
            'duration': end - start,
        })
    if not segments:
        raise ValueError('JSON kosong')
    return segments


def select_file(prompt, extensions, search_dirs):
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
    for f in available:
        if os.path.basename(f) == sel:
            return f
    return sel


def run_progress(cmd, total_duration_s, label=''):
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
                prefix = f'  {label} ' if label else '  '
                print(f'\r{prefix}[{"█" * 50}] 100% ({fmt_dur(total_duration_s)})')
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
    return proc.returncode == 0


def generate_overlay_srt(segments, output_path, display_seconds=3):
    """Generate SRT overlay — text tampil display_seconds di awal tiap segment."""
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

    print(f'  Output : {KONTEN_DIR}')
    print(f'  Format : {OUTPUT_W}x{OUTPUT_H} (horizontal)')
    print()

    # Step 1: Pilih narasi.wav
    print('▶ Step 1: Pilih narasi.wav')
    narasi = select_file('Narasi WAV:', ['wav'], [str(TTS_DIR), str(KONTEN_DIR), os.getcwd()])
    if not narasi or not os.path.isfile(narasi):
        print(f'  ❌ File gak ditemukan: {narasi}')
        return
    narasi_dur = get_duration(ffprobe, narasi)
    print(f'  ✓ {os.path.basename(narasi)} ({fmt_dur(narasi_dur)})')
    print()

    # Step 2: Pilih timestamps.json
    print('▶ Step 2: Pilih timestamps.json')
    json_path = select_file('JSON timestamps:', ['json'], [str(INPUT_DIR), str(KONTEN_DIR), os.getcwd()])
    if not json_path or not os.path.isfile(json_path):
        print(f'  ❌ File gak ditemukan: {json_path}')
        return
    try:
        segments = parse_content_json(json_path)
    except ValueError as e:
        print(f'  ❌ {e}')
        return
    total_dur = sum(s['duration'] for s in segments)
    print(f'  ✓ {os.path.basename(json_path)} ({len(segments)} segments, total {fmt_dur(total_dur)})')
    print()

    # Step 3: Pilih folder images
    print('▶ Step 3: Pilih folder images')
    # Auto-suggest folders with images
    image_folders = []
    for d in [str(INPUT_DIR), str(KONTEN_DIR), os.getcwd()]:
        if Path(d).exists():
            for sub in Path(d).iterdir():
                if sub.is_dir():
                    imgs = list(sub.glob('*.jpg')) + list(sub.glob('*.JPG')) + \
                           list(sub.glob('*.png')) + list(sub.glob('*.PNG'))
                    if imgs:
                        image_folders.append(str(sub))
            # Also check root
            imgs = list(Path(d).glob('*.jpg')) + list(Path(d).glob('*.JPG')) + \
                       list(Path(d).glob('*.png')) + list(Path(d).glob('*.PNG'))
            if imgs and d not in image_folders:
                image_folders.append(d)

    if image_folders:
        choices = sorted(set(image_folders)) + ['[Ketik path manual]']
        sel = questionary.select('Folder images:', choices=choices, default=choices[0]).ask()
        if sel == '[Ketik path manual]':
            image_dir = questionary.text('Path folder:').ask()
        else:
            image_dir = sel
    else:
        image_dir = questionary.text('Tidak ada folder images. Ketik path folder:').ask()

    if not image_dir or not Path(image_dir).exists():
        print(f'  ❌ Folder gak ditemukan: {image_dir}')
        return

    # Find images in folder (natural sort)
    images = []
    for ext in ['jpg', 'JPG', 'jpeg', 'JPEG', 'png', 'PNG']:
        images.extend(Path(image_dir).glob(f'*.{ext}'))
    images = sorted(set(images), key=lambda p: natural_sort_key(p.name))

    if not images:
        print(f'  ❌ Tidak ada image di {image_dir}')
        return
    print(f'  ✓ {image_dir} ({len(images)} images)')
    for i, img in enumerate(images[:5], 1):
        print(f'    [{i}] {img.name}')
    if len(images) > 5:
        print(f'    ... dan {len(images) - 5} lainnya')
    print()

    # Check: jumlah images vs segments
    if len(images) < len(segments):
        print(f'  ⚠ Images ({len(images)}) < Segments ({len(segments)})!')
        print(f'    Image akan diulang untuk segment yang kurang.')
    elif len(images) > len(segments):
        print(f'  ⚠ Images ({len(images)}) > Segments ({len(segments)})!')
        print(f'    Image berlebih akan diabaikan.')
    print()

    # Step 4: Backsound (opsional)
    print('▶ Step 4: Backsound (opsional)')
    use_backsound = questionary.confirm('Pakai backsound?', default=False).ask()
    backsound_path = None
    if use_backsound:
        backsound_path = select_file('Backsound MP3:', ['mp3'], [str(INPUT_DIR), str(KONTEN_DIR), os.getcwd()])
        if not backsound_path or not os.path.isfile(backsound_path):
            print(f'  ⚠ File gak ditemukan, skip backsound')
            backsound_path = None
        else:
            print(f'  ✓ {os.path.basename(backsound_path)}')
    print()

    # Step 5: Output path
    narasi_stem = Path(narasi).stem
    default_output = str(KONTEN_DIR / f'{narasi_stem}-konten.mp4')
    print('▶ Step 5: Output path')
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

    # Step 6: Konfirmasi
    print('═' * 64)
    print('▶ Konfirmasi')
    print('═' * 64)
    print(f'\n  Narasi   : {os.path.basename(narasi)} ({fmt_dur(narasi_dur)})')
    print(f'  Segments : {len(segments)} (total {fmt_dur(total_dur)})')
    print(f'  Images   : {len(images)} dari {os.path.basename(image_dir)}')
    print(f'  Output   : {output}')
    print(f'  Format   : {OUTPUT_W}x{OUTPUT_H} (horizontal)')
    print(f'  Ken Burns: zoom-in/zoom-out alternate')
    print(f'  Overlay  : text per segment (3 detik tampil)')
    if backsound_path:
        print(f'  Backsound: {os.path.basename(backsound_path)} (-18dB)')

    # Warning
    if abs(narasi_dur - total_dur) > 30:
        print(f'\n  ⚠ Durasi narasi ({fmt_dur(narasi_dur)}) vs total segments ({fmt_dur(total_dur)}) beda jauh!')

    if not questionary.confirm('\nLanjut?', default=True).ask():
        print('Dibatalkan.')
        return

    # Temp dir di HDD
    temp_dir_parent = KONTEN_DIR.parent / '.konten_tmp'
    temp_dir_parent.mkdir(parents=True, exist_ok=True)
    temp_dir = tempfile.mkdtemp(prefix='konten_tmp_', dir=str(temp_dir_parent))

    # ============================================================
    # Fase 1: Generate Ken Burns video per image
    # ============================================================
    print('\n' + '═' * 64)
    print('▶ Fase 1: Generate Ken Burns video per image')
    print('═' * 64)
    print()

    temp_videos = []
    for i, seg in enumerate(segments, 1):
        # Match image to segment (cycle if fewer images)
        img_idx = (i - 1) % len(images)
        img_path = str(images[img_idx])
        video_path = os.path.join(temp_dir, f'img_{i:04d}.mp4')
        temp_videos.append(video_path)
        seg_dur = seg['duration']

        # Alternate zoom-in (ganjil) and zoom-out (genap)
        if i % 2 == 1:
            # Zoom in: scale up slowly
            zoom_filter = (
                f"scale={OUTPUT_W*2}:{OUTPUT_H*2}:force_original_aspect_ratio=increase,"
                f"crop={OUTPUT_W*2}:{OUTPUT_H*2},"
                f"zoompan=z='min(zoom+0.0015,1.5)':d={int(seg_dur*30)}:s={OUTPUT_W}x{OUTPUT_H}:fps=30"
            )
        else:
            # Zoom out: start zoomed in, scale down slowly
            zoom_filter = (
                f"scale={OUTPUT_W*2}:{OUTPUT_H*2}:force_original_aspect_ratio=increase,"
                f"crop={OUTPUT_W*2}:{OUTPUT_H*2},"
                f"zoompan=z='if(eq(on,1),1.5,max(1.001,zoom-0.0015))':d={int(seg_dur*30)}:s={OUTPUT_W}x{OUTPUT_H}:fps=30"
            )

        print(f'  [{i}/{len(segments)}] {seg["title"]} ({fmt_dur(seg_dur)}, {os.path.basename(img_path)})')

        cmd = [ffmpeg, '-y',
               '-loop', '1', '-i', img_path,
               '-vf', zoom_filter,
               '-t', str(seg_dur),
               '-c:v', 'h264_videotoolbox', '-b:v', '2M',
               '-pix_fmt', 'yuv420p',
               '-movflags', '+faststart',
               '-progress', 'pipe:1', '-nostats',
               video_path]

        if not run_progress(cmd, seg_dur, label=f'[{i}/{len(segments)}]'):
            print(f'\n  ❌ Gagal generate image video {i}')
            for tv in temp_videos:
                if os.path.exists(tv):
                    os.unlink(tv)
            try:
                os.rmdir(temp_dir)
            except OSError:
                pass
            return
    print()

    # ============================================================
    # Fase 2: Generate overlay SRT
    # ============================================================
    print('▶ Fase 2: Generate overlay SRT')
    print('═' * 64)
    overlay_srt = os.path.join(temp_dir, 'overlay.srt')
    generate_overlay_srt(segments, overlay_srt, display_seconds=3)
    print(f'  ✓ {len(segments)} cues overlay (text tampil 3 detik per segment)')
    print()

    # ============================================================
    # Fase 3: Concat image videos → 1 video
    # ============================================================
    print('▶ Fase 3: Concat image videos')
    print('═' * 64)
    concat_list = os.path.join(temp_dir, 'concat_list.txt')
    with open(concat_list, 'w') as f:
        for tv in temp_videos:
            safe = tv.replace("'", r"'\''")
            f.write(f"file '{safe}'\n")

    concat_output = os.path.join(temp_dir, 'concatenated.mp4')
    cmd = [ffmpeg, '-y', '-f', 'concat', '-safe', '0',
           '-i', concat_list, '-c', 'copy',
           '-movflags', '+faststart',
           '-progress', 'pipe:1', '-nostats', concat_output]

    if not run_progress(cmd, total_dur):
        print('\n  ❌ Gagal concat')
        for tv in temp_videos:
            if os.path.exists(tv):
                os.unlink(tv)
        if os.path.exists(concat_list):
            os.unlink(concat_list)
        if os.path.exists(overlay_srt):
            os.unlink(overlay_srt)
        try:
            os.rmdir(temp_dir)
        except OSError:
            pass
        return
    print()

    # ============================================================
    # Fase 4: Mix video + narasi + backsound + burn overlay SRT
    # ============================================================
    print('▶ Fase 4: Mix video + narasi + overlay (final)')
    print('═' * 64)

    # Escape path
    srt_escaped = overlay_srt.replace('\\', '\\\\').replace(':', '\\:').replace("'", "\\'")
    force_style = (
        "Fontsize=28,"
        "PrimaryColour=&H00FFFFFF,"
        "OutlineColour=&H80000000,"
        "BorderStyle=1,"
        "Outline=2,"
        "Shadow=1,"
        "Alignment=8,"
        "MarginV=50,"
        "Justify=2"
    )

    if backsound_path:
        # Video + narasi + backsound (3 inputs)
        # Narasi: -0dB (dominant), Backsound: -18dB (background)
        subtitle_filter = f"[0:v]subtitles='{srt_escaped}':force_style='{force_style}'[vout]"
        audio_filter = "[1:a]volume=1.0[nar];[2:a]volume=0.126[bg];[nar][bg]amix=inputs=2:duration=longest[aout]"

        cmd = [ffmpeg, '-y',
               '-i', concat_output,
               '-i', narasi,
               '-i', backsound_path,
               '-filter_complex', subtitle_filter + ';' + audio_filter,
               '-map', '[vout]', '-map', '[aout]',
               '-c:v', 'h264_videotoolbox', '-b:v', '2M',
               '-c:a', 'aac', '-b:a', '192k', '-ar', '48000', '-ac', '2',
               '-movflags', '+faststart',
               '-progress', 'pipe:1', '-nostats',
               output]
    else:
        # Video + narasi only (2 inputs)
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

    if not run_progress(cmd, total_dur):
        print('\n  ❌ Gagal mix final')
        # Cleanup
        for tv in temp_videos:
            if os.path.exists(tv):
                os.unlink(tv)
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
    # Cleanup
    # ============================================================
    print('\n▶ Cleanup temp files...')
    for tv in temp_videos:
        if os.path.exists(tv):
            os.unlink(tv)
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
        print(f'\n📁 Output: {os.path.basename(output)} ({fmt_size(size_mb)})')
        print(f'   Path   : {output}')
        print(f'   Durasi : {fmt_dur(out_dur)}')
        print(f'   Res    : {OUTPUT_W}x{OUTPUT_H}')
        print(f'   Images : {len(images)} (Ken Burns effect)')
        print(f'   Overlay: {len(segments)} text segments')
        if backsound_path:
            print(f'   Backsound: {os.path.basename(backsound_path)}')
        print(f'\n🎬 VLC test:')
        print(f'   - Play dari awal → narasi + Ken Burns + text overlay')
        print(f'   - Cek transisi antar image → smooth fade')
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
