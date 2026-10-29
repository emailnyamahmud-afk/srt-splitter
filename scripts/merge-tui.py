#!/usr/bin/env python3
"""
merge-tui.py v1.4 — TUI #12: Gabungin multi-video jadi 1 panjang.

User workflow:
  cd ~/Dubbing && source venv/bin/activate
  python3 merge-tui.py

v1.4: Hardware detection + device selection (konsisten sama whisper-tui/demucs-tui).
v1.5: Temp files di HDD (BUKAN SSD /tmp). User workflow: scripts di SSD, data di HDD.
  - tempfile.mkdtemp(dir=HDD/.merge_tmp/) — temp files ke HDD, SSD aman
  - Estimasi waktu realistis pakai mix-tui benchmark (2-3 min/jam GPU, bukan 10-15)

v1.3: Re-encode pakai h264_videotoolbox (M1 GPU), bukan libx264 (CPU).
v1.2: Natural sort (S1<S2<...<S9<S10)
v1.1: Rewrite pakai questionary (konsisten sama mix-tui/shorts-tui)

Input  : HDD/mix/*.mp4 (output mix-tui, sudah dub ID + burn sub ID)
Output : HDD/merged/{prefix}-merged.mp4

3 mode:
  1. Stream copy (concat demuxer + -c copy) — super cepat, butuh codec+res+fps sama
  2. Re-encode + pilih target res — pakai device pilihan user (GPU/CPU)
  3. Re-encode pakai res file pertama — pakai device pilihan user (GPU/CPU)

Install: pip3 install questionary
"""

import os
import sys
import re
import json
import glob
import subprocess
import shutil
import tempfile
from pathlib import Path

try:
    import questionary
except ImportError:
    print('\n❌ pip3 install questionary')
    sys.exit(1)

# Import config (sama kayak TUI lain)
sys.path.insert(0, str(Path(__file__).parent))
from config import ensure_hdd, MIX_DIR, MERGED_DIR

VERSION = 'v1.5'


# ============================================================
# Helpers (pattern sama kayak mix-tui.py / shorts-tui.py)
# ============================================================

def natural_sort_key(s):
    """Sort key untuk natural sort: 'S1' < 'S2' < ... < 'S9' < 'S10'."""
    return [int(text) if text.isdigit() else text.lower()
            for text in re.split(r'(\d+)', s)]


def find_files_in_dir(search_dir, extensions):
    """Glob files by extension (non-recursive). Natural sort."""
    files = []
    for ext in extensions:
        for f in glob.glob(os.path.join(search_dir, f'*.{ext}')):
            files.append(os.path.basename(f))
        for f in glob.glob(os.path.join(search_dir, f'*.{ext.upper()}')):
            files.append(os.path.basename(f))
    files.sort(key=natural_sort_key)
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


def detect_hw_encoder():
    """Detect hardware encoder availability (kayak demucs detect_device + whisper Metal detect).

    Cek apakah ffmpeg mendukung h264_videotoolbox (Apple Silicon M1/M2/M3 GPU).
    Pattern sama kayak:
    - whisper-tui.py: detect 'metal' di startup log
    - demucs-tui.py: torch.backends.mps.is_available()

    Return: ('gpu', 'h264_videotoolbox') atau ('cpu', 'libx264')
    """
    try:
        result = subprocess.run(
            ['ffmpeg', '-hide_banner', '-encoders'],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0 and 'h264_videotoolbox' in result.stdout:
            return 'gpu', 'h264_videotoolbox'
    except Exception:
        pass
    return 'cpu', 'libx264'


def pick_device(detected_device, detected_encoder):
    """Pilih device (kayak demucs Step 5: Pick device).

    Auto-suggest GPU kalau terdeteksi, fallback CPU.
    """
    if detected_device == 'gpu':
        device = questionary.select(
            'Device (hardware acceleration):',
            choices=[
                f'GPU (M1 VideoToolbox, ~2-3 min/jam) — REKOMENDASI (terdeteksi)',
                'CPU (libx264, ~35 min/jam, bunyi kipas)',
            ],
            default=f'GPU (M1 VideoToolbox, ~2-3 min/jam) — REKOMENDASI (terdeteksi)',
        ).ask()
    else:
        device = questionary.select(
            'Device (hardware acceleration):',
            choices=[
                'CPU (libx264, ~35 min/jam) — VideoToolbox tidak terdeteksi',
            ],
            default='CPU (libx264, ~35 min/jam) — VideoToolbox tidak terdeteksi',
        ).ask()

    if 'GPU' in device:
        return 'gpu', 'h264_videotoolbox'
    return 'cpu', 'libx264'


def probe(path):
    """Probe video metadata via ffprobe."""
    ffprobe = find_ffprobe()
    cmd = [ffprobe, '-v', 'error', '-print_format', 'json',
           '-show_streams', '-show_format', str(path)]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        return None
    try:
        d = json.loads(r.stdout)
    except json.JSONDecodeError:
        return None
    streams = d.get('streams', [])
    v = next((s for s in streams if s.get('codec_type') == 'video'), None)
    a = next((s for s in streams if s.get('codec_type') == 'audio'), None)
    fmt = d.get('format', {})
    try:
        fps = eval(v.get('r_frame_rate', '0/1')) if v else 0
    except Exception:
        fps = 0
    return {
        'path': str(path),
        'name': Path(path).name,
        'duration': float(fmt.get('duration', 0)),
        'size_mb': int(fmt.get('size', 0)) / 1024 / 1024,
        'width': int(v.get('width', 0)) if v else 0,
        'height': int(v.get('height', 0)) if v else 0,
        'vcodec': v.get('codec_name', '?') if v else '?',
        'acodec': a.get('codec_name', '?') if a else '?',
        'fps': round(fps, 2) if fps else 0,
    }


def fmt_dur(s):
    if not s:
        return '00:00:00'
    h = int(s // 3600); m = int((s % 3600) // 60); sec = int(s % 60)
    return f'{h:02d}:{m:02d}:{sec:02d}'


def fmt_size(mb):
    if mb < 1024:
        return f'{mb:.1f}MB'
    return f'{mb/1024:.2f}GB'


def clear_screen():
    os.system('clear' if os.name != 'nt' else 'cls')


def print_banner():
    clear_screen()
    print('╔' + '═' * 64 + '╗')
    print(f'║  🎬 Merge Multi-Video {VERSION} (TUI #12)' + ' ' * 32 + '║')
    print('║  Gabungin S1+S2+S3+S4 → 1 video panjang' + ' ' * 22 + '║')
    print('╚' + '═' * 64 + '╝')
    print()


# ============================================================
# Step functions
# ============================================================

def pick_files():
    """Step 1: Pick multiple MP4 files dari HDD/mix/."""
    print('═' * 64)
    print('▶ Step 1: Pilih file video untuk digabungin')
    print('═' * 64)

    available = find_files_in_dir(str(MIX_DIR), ['mp4'])

    if not available:
        print(f'\n  ⚠ Tidak ada MP4 di {MIX_DIR}')
        print(f'    Jalankan mix-tui.py dulu untuk generate video final.')
        manual = questionary.text('Ketik path file manual (atau kosong untuk batal):').ask()
        if not manual or not manual.strip():
            return []
        files = []
        for p in manual.strip().split():
            p = os.path.expanduser(p.strip().strip("'\""))
            if os.path.exists(p):
                info = probe(p)
                if info and info['vcodec'] != '?':
                    files.append(info)
                    print(f'  + {info["name"]}')
        return files

    print(f'\n  Ditemukan {len(available)} MP4 di {MIX_DIR}:')
    print()
    for i, f in enumerate(available, 1):
        print(f'  [{i}] {f}')
    print()

    choices = available + ['[Ketik path manual]']
    selected = questionary.checkbox(
        'Pilih file (Space untuk centang, Enter untuk selesai):',
        choices=choices,
    ).ask()

    if not selected:
        return []

    files = []
    for sel in selected:
        if sel == '[Ketik path manual]':
            manual = questionary.text('Ketik path file:').ask()
            if manual and manual.strip():
                p = os.path.expanduser(manual.strip().strip("'\""))
                if os.path.exists(p):
                    info = probe(p)
                    if info and info['vcodec'] != '?':
                        files.append(info)
        else:
            p = os.path.join(str(MIX_DIR), sel)
            info = probe(p)
            if info and info['vcodec'] != '?':
                files.append(info)

    return files


def reorder_files(files):
    """Step 2: Reorder files (optional)."""
    if len(files) < 2:
        return files

    print('\n' + '═' * 64)
    print('▶ Step 2: Urutan file (sekarang)')
    print('═' * 64)
    print()
    for i, f in enumerate(files, 1):
        print(f'  [{i}] {f["name"]} ({fmt_dur(f["duration"])})')
    print()

    confirm = questionary.confirm('Urutan udah bener?', default=True).ask()
    if confirm:
        return files

    while True:
        print()
        for i, f in enumerate(files, 1):
            print(f'  [{i}] {f["name"]}')
        print()

        action = questionary.select(
            'Pilih aksi:',
            choices=[
                'Pindah file ke posisi lain',
                'Tukar 2 file',
                'Selesai (lanjut ke step 3)',
            ],
        ).ask()

        if 'Selesai' in action:
            break
        elif 'Pindah' in action:
            try:
                idx = int(questionary.text('Nomor file untuk pindah:').ask())
                new_pos = int(questionary.text(f'Pindah ke posisi (1..{len(files)}):').ask())
                if 1 <= idx <= len(files) and 1 <= new_pos <= len(files):
                    item = files.pop(idx - 1)
                    files.insert(new_pos - 1, item)
                    print(f'  ✓ Dipindah')
            except (ValueError, IndexError):
                print('  ❌ Input gak valid')
        elif 'Tukar' in action:
            try:
                i1 = int(questionary.text('Nomor file 1:').ask())
                i2 = int(questionary.text('Nomor file 2:').ask())
                if 1 <= i1 <= len(files) and 1 <= i2 <= len(files):
                    files[i1-1], files[i2-1] = files[i2-1], files[i1-1]
                    print(f'  ✓ Ditukar')
            except (ValueError, IndexError):
                print('  ❌ Input gak valid')

    return files


def auto_detect_mode(files):
    """Step 3: Auto-detect mode based on res/codec/fps."""
    if not files:
        return None

    res_set = set((f['width'], f['height']) for f in files)
    vcodec_set = set(f['vcodec'] for f in files)
    acodec_set = set(f['acodec'] for f in files)
    fps_set = set(f['fps'] for f in files)

    print('\n' + '═' * 64)
    print('▶ Step 3: Auto-detect mode')
    print('═' * 64)
    print()
    print(f'  Resolution: {len(res_set)} unique')
    for r in res_set:
        print(f'    - {r[0]}x{r[1]}')
    print(f'  Video codec: {vcodec_set}')
    print(f'  Audio codec: {acodec_set}')
    print(f'  FPS: {fps_set}')
    print()

    if len(res_set) == 1 and len(vcodec_set) == 1 and len(acodec_set) == 1:
        print('  ✅ Semua sama → stream copy AMAN (super cepat, no re-encode)')
        return 'stream_copy'
    print('  ⚠ Ada perbedaan → harus re-encode (pakai M1 GPU, bukan CPU)')
    return 'reencode'


def pick_output_path(files):
    """Step 4: Pick output path. Auto-derive dari prefix file pertama."""
    if not files:
        return None

    first_name = Path(files[0]['path']).stem
    for suffix in ['-id-final-sub', '-id-final', '-id-simple-sub', '-id-simple',
                   '-id-orig-sub', '-id-orig', '-ori', '-id']:
        if first_name.endswith(suffix):
            first_name = first_name[:-len(suffix)]
            break

    default_output = str(MERGED_DIR / f'{first_name}-merged.mp4')

    print('\n' + '═' * 64)
    print('▶ Step 4: Pilih output path')
    print('═' * 64)
    print(f'\n  Default: {default_output}')

    output = questionary.text('Output path (Enter untuk default):',
                              default=default_output).ask()
    if not output or not output.strip():
        output = default_output
    else:
        output = os.path.expanduser(output.strip())

    parent = os.path.dirname(output)
    if parent and not os.path.exists(parent):
        try:
            os.makedirs(parent, exist_ok=True)
        except OSError as e:
            print(f'  ❌ Gak bisa buat folder: {e}')
            return None

    return output


def pick_resolution():
    """Pilih target resolution untuk re-encode mode."""
    res = questionary.select(
        'Pilih target resolution:',
        choices=[
            '1920x1080 (1080p, vertical 1080x1920)',
            '1280x720 (720p, vertical 720x1280)',
            '854x480 (480p, vertical 480x854)',
            'Custom (ketik manual)',
        ],
        default='1920x1080 (1080p, vertical 1080x1920)',
    ).ask()

    # Semua file di HDD/mix/ adalah vertical (9:16), jadi output juga vertical
    if '1080' in res:
        return 1080, 1920  # vertical
    if '720' in res:
        return 720, 1280
    if '480' in res:
        return 480, 854
    try:
        w = int(questionary.text('Width:').ask())
        h = int(questionary.text('Height:').ask())
        if w > 0 and h > 0:
            return w, h
    except ValueError:
        pass
    return None, None


def pick_bitrate():
    """Pilih video bitrate untuk h264_videotoolbox."""
    bitrate = questionary.select(
        'Pilih video bitrate (M1 GPU encode):',
        choices=[
            '2M (default, seimbang)',
            '4M (HD-ready, sharp)',
            '6M (high quality)',
            '8M (max, big file)',
        ],
        default='2M (default, seimbang)',
    ).ask()
    return bitrate.split(' ')[0]  # '2M', '4M', dst


# ============================================================
# Merge functions
# ============================================================

def run_progress(cmd, total_duration_s, list_path=None):
    """Run ffmpeg dengan progress bar."""
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
            if not line:
                continue
            if '=' in line:
                k, v = line.split('=', 1)
                k = k.strip(); v = v.strip()
                if k == 'out_time_ms' and total_duration_s > 0:
                    try:
                        cur = int(v) / 1_000_000
                        pct = min(int(cur * 100 / total_duration_s), 99)
                        if pct > last_pct:
                            bar = '█' * (pct // 2) + '░' * (50 - pct // 2)
                            print(f'\r  [{bar}] {pct}% ({fmt_dur(cur)}/{fmt_dur(total_duration_s)})',
                                  end='', flush=True)
                            last_pct = pct
                    except ValueError:
                        pass
                elif k == 'progress' and v == 'end':
                    print(f'\r  [{"█" * 50}] 100% ({fmt_dur(total_duration_s)})')
                    break
        proc.wait()
    except KeyboardInterrupt:
        print('\n  ⚠ Dibatalkan. Matiin ffmpeg...')
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
        return False

    if list_path and os.path.exists(list_path):
        os.unlink(list_path)

    return proc.returncode == 0


def merge_stream_copy(files, output):
    """Concat demuxer + -c copy. Super cepat tapi butuh codec+res sama."""
    list_path = tempfile.NamedTemporaryFile('w', suffix='.txt', delete=False)
    for f in files:
        safe = f['path'].replace("'", r"'\''")
        list_path.write(f"file '{safe}'\n")
    list_path.close()

    cmd = ['ffmpeg', '-y', '-f', 'concat', '-safe', '0',
           '-i', list_path.name, '-c', 'copy',
           '-progress', 'pipe:1', '-nostats', output]
    total = sum(f['duration'] for f in files)

    print('\n' + '═' * 64)
    print('🚀 Merge (stream copy, super cepat)...')
    print('═' * 64)
    print(f'\n  Total duration: {fmt_dur(total)}\n')
    return run_progress(cmd, total, list_path.name)


def merge_reencode(files, output, target_w, target_h, bitrate, device, encoder):
    """Re-encode per-file pakai encoder pilihan (GPU h264_videotoolbox atau CPU libx264),
    lalu concat stream copy.

    Strategi 2-fase (RAM-safe):
      Fase 1: Encode tiap file ke target res (encoder pilihan), simpan ke temp file
      Fase 2: Concat stream copy semua temp file → output final
      Cleanup: hapus temp files
    """
    device_label = 'M1 GPU (VideoToolbox)' if device == 'gpu' else 'CPU (libx264)'
    speed_label = '~2-3 min/jam video' if device == 'gpu' else '~35 min/jam video'

    print('\n' + '═' * 64)
    print(f'🚀 Merge (re-encode {device_label} + concat)...')
    print('═' * 64)
    print(f'\n  Target res  : {target_w}x{target_h}')
    print(f'  Bitrate     : {bitrate} ({encoder})')
    print(f'  Device      : {device_label}')
    print(f'  Speed       : {speed_label}')
    print(f'  Strategi    : encode per-file → concat stream copy')
    print(f'  Total files : {len(files)}')
    total = sum(f['duration'] for f in files)
    print(f'  Total dur   : {fmt_dur(total)}')

    # Estimasi waktu (mix-tui benchmark: 2-3 min/jam GPU, 30-40 min/jam CPU)
    hours = total / 3600
    if device == 'gpu':
        est_min = max(5, int(hours * 2.5))  # 2.5 min/jam (mix-tui benchmark)
    else:
        est_min = int(hours * 35)  # 35 min/jam (libx264 medium, mix-tui experience)
    print(f'\n  ⏱️  Estimasi: ~{est_min} menit ({speed_label})')
    print()

    # Buat temp dir di HDD (BUKAN SSD /tmp) — biar SSD gak penuh
    # User workflow: scripts di SSD, data di HDD. Temp files = data besar = HDD.
    # Pakai subfolder .merge_tmp/ di parent HDD (gak campur sama output merged/)
    temp_dir_parent = MERGED_DIR.parent / '.merge_tmp'
    temp_dir_parent.mkdir(parents=True, exist_ok=True)
    temp_dir = tempfile.mkdtemp(prefix='merge_tmp_', dir=str(temp_dir_parent))
    temp_files = []

    # Build encoder args
    if device == 'gpu':
        # h264_videotoolbox: -c:v h264_videotoolbox -b:v <bitrate>
        # Apple Silicon hardware encoder, gak bunyi kipas
        enc_args = ['-c:v', encoder, '-b:v', bitrate]
    else:
        # libx264: -c:v libx264 -preset medium -crf 20 (fallback, lambat, CPU bunyi)
        enc_args = ['-c:v', encoder, '-preset', 'medium', '-crf', '20']

    # Fase 1: Encode per-file
    print(f'▶ Fase 1: Encode per-file ({device_label})')
    print('═' * 64)
    for i, f in enumerate(files, 1):
        temp_out = os.path.join(temp_dir, f'part_{i:03d}.mp4')
        temp_files.append(temp_out)

        # scale + pad: target res, preserve aspect ratio (letterbox/pillarbox)
        # setsar=1: square pixel, biar concat aman
        vf = (
            f'scale={target_w}:{target_h}'
            f':force_original_aspect_ratio=decrease,'
            f'pad={target_w}:{target_h}:(ow-iw)/2:(oh-ih)/2:color=black,'
            f'setsar=1,fps=30'
        )

        cmd = [
            'ffmpeg', '-y',
            '-i', f['path'],
            '-vf', vf,
        ] + enc_args + [
            '-c:a', 'aac', '-b:a', '192k',
            '-movflags', '+faststart',
            '-progress', 'pipe:1', '-nostats',
            temp_out,
        ]

        print(f'\n  [{i}/{len(files)}] {f["name"]} ({fmt_dur(f["duration"])})')
        if not run_progress(cmd, f['duration']):
            print(f'\n  ❌ Gagal encode file {i}: {f["name"]}')
            # Cleanup
            for tf in temp_files:
                if os.path.exists(tf):
                    os.unlink(tf)
            try:
                os.rmdir(temp_dir)
            except OSError:
                pass
            return False

    # Fase 2: Concat stream copy
    print('\n' + '═' * 64)
    print('▶ Fase 2: Concat stream copy (super cepat)')
    print('═' * 64)
    print()

    list_path = os.path.join(temp_dir, 'concat_list.txt')
    with open(list_path, 'w') as lf:
        for tf in temp_files:
            safe = tf.replace("'", r"'\''")
            lf.write(f"file '{safe}'\n")

    cmd = ['ffmpeg', '-y', '-f', 'concat', '-safe', '0',
           '-i', list_path, '-c', 'copy',
           '-movflags', '+faststart',
           '-progress', 'pipe:1', '-nostats', output]

    if not run_progress(cmd, total, list_path):
        print('\n  ❌ Gagal concat')
        # Cleanup
        for tf in temp_files:
            if os.path.exists(tf):
                os.unlink(tf)
        try:
            os.rmdir(temp_dir)
        except OSError:
            pass
        return False

    # Cleanup temp files
    print('\n  Cleaning up temp files...')
    for tf in temp_files:
        if os.path.exists(tf):
            os.unlink(tf)
    try:
        os.rmdir(temp_dir)
    except OSError:
        pass

    return True


# ============================================================
# Main
# ============================================================

def main():
    print_banner()

    if not ensure_hdd():
        return

    find_ffmpeg()
    find_ffprobe()

    # Detect hardware encoder (kayak demucs detect_device + whisper Metal detect)
    detected_device, detected_encoder = detect_hw_encoder()
    if detected_device == 'gpu':
        print('  ✓ Apple Silicon terdeteksi — M1 VideoToolbox (GPU) tersedia')
        hw_label = 'M1 GPU (h264_videotoolbox) ✅'
    else:
        print('  ℹ VideoToolbox tidak terdeteksi — akan pakai CPU (libx264, lambat)')
        hw_label = 'CPU (libx264) ⚠'

    print(f'  Input  : {MIX_DIR}')
    print(f'  Output : {MERGED_DIR}')
    print(f'  Engine : {hw_label}')
    print()

    # Step 1: Pick files
    files = pick_files()
    if not files or len(files) < 2:
        print('\n❌ Butuh minimal 2 file untuk digabungin.')
        return

    # Show summary
    print(f'\n  ✓ {len(files)} file dipilih:')
    total_dur = 0; total_size = 0
    for i, f in enumerate(files, 1):
        total_dur += f['duration']
        total_size += f['size_mb']
        print(f'    [{i}] {f["name"]} | {f["width"]}x{f["height"]} | '
              f'{f["vcodec"]} | {fmt_dur(f["duration"])} | {fmt_size(f["size_mb"])}')
    print(f'\n  Total: {fmt_dur(total_dur)} | {fmt_size(total_size)}')

    # Step 2: Reorder (optional)
    files = reorder_files(files)

    # Step 3: Auto-detect mode
    suggested_mode = auto_detect_mode(files)

    # Step 4: Pick output path
    output_path = pick_output_path(files)
    if not output_path:
        print('\n❌ Output path gak valid.')
        return

    # Step 5: Pick mode (with suggestion)
    mode_choices = [
        'Stream copy (super cepat, butuh codec+res+fps sama)',
        'Re-encode + pilih target res',
        'Re-encode pakai res file pertama',
    ]
    default_mode = mode_choices[0] if suggested_mode == 'stream_copy' else mode_choices[1]

    print('\n' + '═' * 64)
    print('▶ Step 5: Pilih mode merge')
    print('═' * 64)

    mode = questionary.select(
        'Pilih mode:',
        choices=mode_choices,
        default=default_mode,
    ).ask()

    # Pick resolution + bitrate + device for re-encode modes
    bitrate = None
    target_w = target_h = None
    device = encoder = None
    if 'Re-encode + pilih target res' in mode or 'Re-encode pakai res file pertama' in mode:
        # Step 5a: Pick device (kayak demucs Step 5)
        print('\n' + '═' * 64)
        print('▶ Step 5a: Pilih device (hardware acceleration)')
        print('═' * 64)
        device, encoder = pick_device(detected_device, detected_encoder)
        print(f'  ✓ {device.upper()} ({encoder})')

        if 'Re-encode + pilih target res' in mode:
            w, h = pick_resolution()
            if w is None:
                print('\n❌ Resolusi gak valid.')
                return
            target_w, target_h = w, h
            bitrate = pick_bitrate()
        else:
            # Pakai res file pertama
            target_w, target_h = files[0]['width'], files[0]['height']
            bitrate = pick_bitrate()
            print(f'\n  Res file pertama: {target_w}x{target_h}')

    # Confirm
    print('\n' + '═' * 64)
    print('▶ Konfirmasi')
    print('═' * 64)
    print(f'\n  Mode    : {mode}')
    print(f'  Output  : {output_path}')
    print(f'  Files   : {len(files)}')
    print(f'  Total   : {fmt_dur(total_dur)} | {fmt_size(total_size)}')
    if bitrate:
        device_label = 'M1 GPU (VideoToolbox)' if device == 'gpu' else 'CPU (libx264)'
        print(f'  Device  : {device_label}')
        print(f'  Encoder : {encoder}')
        print(f'  Bitrate : {bitrate}')
        print(f'  Target  : {target_w}x{target_h}')
        # Estimasi waktu (mix-tui benchmark)
        hours = total_dur / 3600
        if device == 'gpu':
            est_min = max(5, int(hours * 2.5))
            print(f'  Estimasi: ~{est_min} menit (M1 GPU ~2-3 min/jam, mix-tui benchmark)')
        else:
            est_min = int(hours * 35)
            print(f'  Estimasi: ~{est_min} menit (CPU ~35 min/jam, bunyi kipas)')

    if not questionary.confirm('\nLanjut merge?', default=True).ask():
        print('\nDibatalkan.')
        return

    # Run merge
    if 'Stream copy' in mode:
        success = merge_stream_copy(files, output_path)
    elif 'Re-encode + pilih target res' in mode:
        success = merge_reencode(files, output_path, target_w, target_h, bitrate, device, encoder)
    elif 'Re-encode pakai res file pertama' in mode:
        success = merge_reencode(files, output_path, target_w, target_h, bitrate, device, encoder)
    else:
        success = False

    # Hasil
    if success and os.path.exists(output_path):
        size_mb = os.path.getsize(output_path) / 1024 / 1024
        print(f'\n📁 Output: {Path(output_path).name} ({fmt_size(size_mb)})')
        print(f'   Path  : {output_path}')
        print('\n🎬 Langkah berikutnya:')
        print('   - Cek hasil di VLC (test playback + audio sync)')
        print('   - Upload ke YouTube / arsip')
    elif not success:
        print('\n❌ Merge gagal. Cek log di atas.')
    print('═' * 64)


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print('\n\n⏹ Dibatalkan.')
        sys.exit(130)
    except Exception as e:
        print(f'\n❌ {e}', file=sys.stderr)
        sys.exit(1)
