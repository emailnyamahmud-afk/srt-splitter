#!/usr/bin/env python3
"""
merge-tui.py v1.0 — TUI #12: Gabungin multi-video jadi 1 panjang.

User workflow:
  cd ~/Dubbing && source venv/bin/activate
  python3 merge-tui.py

Input  : HDD/mix/*.mp4 (output mix-tui, sudah dub ID + burn sub ID)
Output : HDD/merged/merged_YYYYMMDD_HHMMSS.mp4

3 mode:
  [7] Stream copy (concat demuxer + -c copy) — super cepat, butuh codec+res+fps sama
  [8] Re-encode + pilih target res (1080p/720p/480p/custom) — kalau res beda
  [9] Re-encode pakai res file pertama

Pakai config.py (konsisten sama TUI lain).
"""
import os
import sys
import json
import subprocess
import tempfile
from datetime import datetime
from pathlib import Path

# Import config (sama kayak TUI lain)
sys.path.insert(0, str(Path(__file__).parent))
from config import (
    ensure_hdd, MIX_DIR, MERGED_DIR, HDD_BASE
)

VERSION = "1.0"


def probe(path):
    cmd = ['ffprobe', '-v', 'error', '-print_format', 'json',
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


def list_mix_files():
    """Glob MP4 di HDD/mix/ (bahan merge-tui)."""
    if not MIX_DIR.exists():
        return []
    return sorted(MIX_DIR.glob('*.mp4'))


def print_banner():
    print(f'\n=== merge-tui.py v{VERSION} — TUI #12 ===')
    print('Gabungin multi-video jadi 1 panjang')
    print(f'Input  : {MIX_DIR}')
    print(f'Output : {MERGED_DIR}\n')


def print_menu(files, output_path):
    print(f'\n--- MENU ---')
    print(f'  Files: {len(files)} | Output: {Path(output_path).name}')
    print()
    print('[1] Tambah file (ketik "mix" untuk list HDD/mix/*.mp4)')
    print('[2] List files + probe info')
    print('[3] Hapus file dari list')
    print('[4] Reorder file')
    print('[5] Pilih output path')
    print('[6] Auto-detect mode (rekomendasi)')
    print('[7] Merge: stream copy (super cepat, butuh res+codec sama)')
    print('[8] Merge: re-encode + pilih target res')
    print('[9] Merge: re-encode pakai res file pertama')
    print('[0] Keluar')


def add_file(files):
    print('\nTambah file video. Ketik path, atau drag-drop ke terminal.')
    print('Ketik "mix" untuk list HDD/mix/*.mp4. Kosongkan untuk selesai.')
    while True:
        try:
            p = input('  Path: ').strip().strip("'\"")
        except (EOFError, KeyboardInterrupt):
            break
        if not p:
            break
        if p.lower() == 'mix':
            mix_files = list_mix_files()
            if not mix_files:
                print(f'  (kosong — {MIX_DIR} gak ada MP4)')
                continue
            print(f'\n  --- HDD/mix/ MP4 files ---')
            for i, f in enumerate(mix_files, 1):
                print(f'  [{i}] {f.name}')
            try:
                n = input('  Pilih nomor (atau "all" untuk semua): ').strip()
                if n == 'all':
                    for f in mix_files:
                        info = probe(f)
                        if info and info['vcodec'] != '?':
                            files.append(info)
                            print(f'    + {f.name}')
                else:
                    n = int(n)
                    if 1 <= n <= len(mix_files):
                        info = probe(mix_files[n - 1])
                        if info:
                            files.append(info)
                            print(f'    + {mix_files[n-1].name}')
            except (ValueError, IndexError):
                print('  ❌ Input gak valid')
            continue
        p = os.path.expanduser(p)
        if not os.path.exists(p):
            print(f'  ❌ File gak ada: {p}')
            continue
        info = probe(p)
        if not info or info['vcodec'] == '?':
            print(f'  ❌ Bukan video valid: {p}')
            continue
        files.append(info)
        print(f'  + {info["name"]} | {info["width"]}x{info["height"]} | '
              f'{info["vcodec"]} | {fmt_dur(info["duration"])}')


def list_files(files):
    if not files:
        print('\n  (kosong)')
        return
    print(f'\n--- File list ({len(files)}) ---')
    total_dur = 0; total_size = 0
    for i, f in enumerate(files, 1):
        total_dur += f['duration']
        total_size += f['size_mb']
        print(f'  [{i}] {f["name"]}')
        print(f'      {f["width"]}x{f["height"]} @ {f["fps"]}fps | '
              f'{f["vcodec"]} + {f["acodec"]} | {fmt_dur(f["duration"])} | {fmt_size(f["size_mb"])}')
    print(f'\n  Total: {fmt_dur(total_dur)} | {fmt_size(total_size)}')


def remove_file(files):
    list_files(files)
    if not files:
        return
    try:
        n = input('\nNomor file untuk hapus (kosongkan batal): ').strip()
        if not n:
            return
        n = int(n)
        if 1 <= n <= len(files):
            removed = files.pop(n - 1)
            print(f'  ✓ Dihapus: {removed["name"]}')
    except (ValueError, IndexError):
        print('  ❌ Nomor gak valid')


def reorder(files):
    list_files(files)
    if not files:
        return
    try:
        idx = input('\nNomor file untuk pindah: ').strip()
        if not idx:
            return
        idx = int(idx)
        if not (1 <= idx <= len(files)):
            return
        new_pos = input(f'Pindah ke posisi (1..{len(files)}): ').strip()
        new_pos = int(new_pos)
        if not (1 <= new_pos <= len(files)):
            return
        item = files.pop(idx - 1)
        files.insert(new_pos - 1, item)
        print(f'  ✓ Dipindah ke posisi {new_pos}')
    except (ValueError, IndexError):
        print('  ❌ Input gak valid')


def pick_output(output_path):
    print(f'\nOutput path saat ini: {output_path}')
    p = input('Path output baru (kosongkan batal): ').strip().strip("'\"")
    if not p:
        return None
    p = os.path.expanduser(p)
    parent = os.path.dirname(p)
    if parent and not os.path.exists(parent):
        try:
            os.makedirs(parent, exist_ok=True)
        except OSError as e:
            print(f'  ❌ Gak bisa buat folder: {e}')
            return None
    return p


def auto_detect(files):
    if not files:
        print('\n  (kosong)')
        return None
    print('\n--- Auto-detect ---')
    res_set = set((f['width'], f['height']) for f in files)
    vcodec_set = set(f['vcodec'] for f in files)
    acodec_set = set(f['acodec'] for f in files)
    fps_set = set(f['fps'] for f in files)
    print(f'  Resolution: {len(res_set)} unique')
    for r in res_set:
        print(f'    - {r[0]}x{r[1]}')
    print(f'  Video codec: {vcodec_set}')
    print(f'  Audio codec: {acodec_set}')
    print(f'  FPS: {fps_set}')
    if len(res_set) == 1 and len(vcodec_set) == 1 and len(acodec_set) == 1:
        print('\n  ✅ Semua sama → mode [7] stream copy AMAN (super cepat, no re-encode)')
        return 'stream_copy'
    print('\n  ⚠️  Ada perbedaan → harus re-encode')
    print('  Rekomendasi: mode [8] pilih target res, atau [9] pakai res file pertama')
    return 'reencode'


def run_merge(cmd, total_duration_s, list_path=None):
    print('\n--- Run merge ---')
    print(f'  Total duration: {fmt_dur(total_duration_s)}')
    try:
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                text=True, bufsize=1)
    except FileNotFoundError:
        print('  ❌ ffmpeg gak ditemukan di PATH')
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
                            print(f'\r  [{bar}] {pct}% '
                                  f'({fmt_dur(cur)}/{fmt_dur(total_duration_s)})',
                                  end='', flush=True)
                            last_pct = pct
                    except ValueError:
                        pass
                elif k == 'progress' and v == 'end':
                    print(f'\r  [{"█" * 50}] 100% ({fmt_dur(total_duration_s)})')
                    break
        proc.wait()
    except KeyboardInterrupt:
        print('\n  ⚠️  Dibatalkan. Matiin ffmpeg...')
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
        return False
    if list_path and os.path.exists(list_path):
        os.unlink(list_path)
    if proc.returncode == 0:
        print('\n  ✅ Selesai!')
        return True
    print(f'\n  ❌ Gagal. Exit code: {proc.returncode}')
    return False


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
    return run_merge(cmd, total, list_path.name)


def merge_reencode(files, output, target_w=None, target_h=None):
    """Re-encode dengan scale target. Res output sama untuk semua."""
    n = len(files)
    parts = []
    for i in range(n):
        if target_w and target_h:
            parts.append(
                f'[{i}:v]scale={target_w}:{target_h}'
                f':force_original_aspect_ratio=decrease,'
                f'pad={target_w}:{target_h}:(ow-iw)/2:(oh-ih)/2,'
                f'setsar=1[v{i}]'
            )
        else:
            parts.append(f'[{i}:v]setsar=1[v{i}]')
    v_inputs = ''.join(f'[v{i}]' for i in range(n))
    parts.append(f'{v_inputs}concat=n={n}:v=1:a=0[vout]')
    a_inputs = ''.join(f'[{i}:a]' for i in range(n))
    parts.append(f'{a_inputs}concat=n={n}:v=0:a=1[aout]')
    filt = ';'.join(parts)
    cmd = ['ffmpeg', '-y']
    for f in files:
        cmd += ['-i', f['path']]
    cmd += ['-filter_complex', filt, '-map', '[vout]', '-map', '[aout]',
            '-c:v', 'libx264', '-preset', 'medium', '-crf', '20',
            '-c:a', 'aac', '-b:a', '192k',
            '-progress', 'pipe:1', '-nostats', output]
    total = sum(f['duration'] for f in files)
    return run_merge(cmd, total)


def pick_resolution():
    print('\n--- Pilih target resolution ---')
    print('[1] 1920x1080 (1080p)')
    print('[2] 1280x720 (720p)')
    print('[3] 854x480 (480p)')
    print('[4] Custom')
    try:
        n = input('Pilih: ').strip()
    except (EOFError, KeyboardInterrupt):
        return None, None
    if n == '1':
        return 1920, 1080
    if n == '2':
        return 1280, 720
    if n == '3':
        return 854, 480
    if n == '4':
        try:
            w = int(input('Width: ').strip())
            h = int(input('Height: ').strip())
            if w > 0 and h > 0:
                return w, h
        except ValueError:
            pass
    return None, None


def main():
    print_banner()
    # Cek HDD colok (kayak TUI lain)
    if not ensure_hdd():
        return
    # Cek ffmpeg
    try:
        subprocess.run(['ffmpeg', '-version'], capture_output=True, check=True)
        subprocess.run(['ffprobe', '-version'], capture_output=True, check=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        print('❌ ffmpeg/ffprobe gak ditemukan. Install dulu:')
        print('   brew install ffmpeg')
        return

    files = []
    default_name = f'merged_{datetime.now().strftime("%Y%m%d_%H%M%S")}.mp4'
    output_path = str(MERGED_DIR / default_name)

    while True:
        print_menu(files, output_path)
        try:
            choice = input('\nPilih: ').strip()
        except (EOFError, KeyboardInterrupt):
            print('\nKeluar.')
            break
        if choice == '0':
            print('Keluar.')
            break
        elif choice == '1':
            add_file(files)
        elif choice == '2':
            list_files(files)
        elif choice == '3':
            remove_file(files)
        elif choice == '4':
            reorder(files)
        elif choice == '5':
            new = pick_output(output_path)
            if new:
                output_path = new
                print(f'  ✓ Output: {output_path}')
        elif choice == '6':
            auto_detect(files)
        elif choice == '7':
            if not files:
                print('  ❌ Tambah file dulu')
                continue
            if len(files) < 2:
                print('  ❌ Butuh minimal 2 file')
                continue
            print(f'\n  Mode: stream copy (super cepat, no re-encode)')
            print(f'  Output: {output_path}')
            if input('  Lanjut? (y/N): ').strip().lower() == 'y':
                merge_stream_copy(files, output_path)
        elif choice == '8':
            if not files:
                print('  ❌ Tambah file dulu')
                continue
            if len(files) < 2:
                print('  ❌ Butuh minimal 2 file')
                continue
            w, h = pick_resolution()
            if w is None:
                continue
            print(f'\n  Mode: re-encode + scale to {w}x{h}')
            print(f'  Output: {output_path}')
            if input('  Lanjut? (y/N): ').strip().lower() == 'y':
                merge_reencode(files, output_path, w, h)
        elif choice == '9':
            if not files:
                print('  ❌ Tambah file dulu')
                continue
            if len(files) < 2:
                print('  ❌ Butuh minimal 2 file')
                continue
            w, h = files[0]['width'], files[0]['height']
            print(f'\n  Mode: re-encode pakai res file pertama: {w}x{h}')
            print(f'  Output: {output_path}')
            if input('  Lanjut? (y/N): ').strip().lower() == 'y':
                merge_reencode(files, output_path, w, h)
        else:
            print('Pilihan gak valid')


if __name__ == '__main__':
    main()
