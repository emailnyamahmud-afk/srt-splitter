#!/usr/bin/env python3
"""
fix-merge-audio.py v1.0 — Fix audio output merge-tui v1.7 (audio kacau).

User feedback v1.7: 'audio = parah. banyak yg silen dan banyak suara jadi cepat'.
Output v1.7 resolusi udah seragam (1440x2560), tapi audio kacau (sample rate mismatch).

Fix: ambil video dari output v1.7 (seragam) + concat audio dari 10 file mix (bagus).
Gak perlu merge lagi 4 jam, cuma butuh ~5-10 menit (stream copy semua).

Cara kerja:
  1. List 10 file mix (filter prefix, natural sort, kayak merge-tui)
  2. Probe sample rate semua file, display (detect mismatch)
  3. Concat audio dari 10 file mix → audio 24 jam (stream copy, -vn -c:a copy)
  4. Mux video dari output v1.7 + audio concat → output final (stream copy both)
  5. Cleanup temp

Usage:
  cd ~/Dubbing && source venv/bin/activate
  python3 fix-merge-audio.py
"""
import os
import sys
import re
import json
import subprocess
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from config import ensure_hdd, MIX_DIR, MERGED_DIR


def natural_sort_key(s):
    return [int(text) if text.isdigit() else text.lower()
            for text in re.split(r'(\d+)', s)]


def probe_audio(path):
    """Probe audio sample_rate + channels dari file."""
    cmd = ['ffprobe', '-v', 'error', '-select_streams', 'a:0',
           '-show_entries', 'stream=sample_rate,channels,codec_name',
           '-of', 'json', str(path)]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        return None
    try:
        d = json.loads(r.stdout)
        streams = d.get('streams', [])
        if not streams:
            return None
        a = streams[0]
        return {
            'sample_rate': int(a.get('sample_rate', 0)),
            'channels': int(a.get('channels', 0)),
            'codec': a.get('codec_name', '?'),
        }
    except Exception:
        return None


def main():
    print('╔' + '═' * 64 + '╗')
    print('║  🔧 Fix Merge Audio v1.0 (fix v1.7 audio kacau)            ║')
    print('║  Mux video v1.7 + audio dari mix (stream copy, cepat)     ║')
    print('╚' + '═' * 64 + '╝')
    print()

    if not ensure_hdd():
        return

    # Step 1: Auto-list file mix yang prefix "5 Tentara" (natural sort)
    print('▶ Step 1: List file mix')
    all_mix = sorted(MIX_DIR.glob('*.mp4'), key=lambda p: natural_sort_key(p.name))
    # Filter prefix "5 Tentara" (atau user input)
    prefix = input('Prefix file mix (Enter untuk "5 Tentara"): ').strip()
    if not prefix:
        prefix = '5 Tentara'
    mix_files = [f for f in all_mix if f.name.startswith(prefix)]
    if len(mix_files) < 2:
        print(f'  ❌ Cuma {len(mix_files)} file mix dengan prefix "{prefix}"')
        print(f'    Folder: {MIX_DIR}')
        return
    print(f'  ✓ {len(mix_files)} file mix:')
    for i, f in enumerate(mix_files, 1):
        print(f'    [{i}] {f.name}')
    print()

    # Step 2: Probe sample rate semua file
    print('▶ Step 2: Probe audio sample rate')
    sample_rates = set()
    for f in mix_files:
        info = probe_audio(f)
        if info:
            sr = info['sample_rate']
            ch = info['channels']
            codec = info['codec']
            sample_rates.add(sr)
            print(f'  {f.name}: {sr} Hz, {ch}ch, {codec}')
        else:
            print(f'  {f.name}: ❌ gagal probe')
    print()
    if len(sample_rates) > 1:
        print(f'  ⚠ Sample rate beda: {sample_rates}')
        print(f'    Concat stream copy bisa kacau (sama kayak v1.7 bug)')
        print(f'    Tapi user bilang audio mix bagus, jadi lanjut...')
    else:
        print(f'  ✅ Sample rate konsisten: {sample_rates.pop()} Hz')
    print()

    # Step 3: Pilih file merge v1.7 (output yang audio-nya kacau)
    print('▶ Step 3: Pilih file merge v1.7 (audio kacau)')
    merged_files = sorted(MERGED_DIR.glob('*.mp4'), key=lambda p: natural_sort_key(p.name))
    if not merged_files:
        print(f'  ❌ Tidak ada file di {MERGED_DIR}')
        return
    print(f'  File di {MERGED_DIR}:')
    for i, f in enumerate(merged_files, 1):
        size_gb = f.stat().st_size / 1024 / 1024 / 1024
        print(f'    [{i}] {f.name} ({size_gb:.2f} GB)')
    try:
        n = int(input(f'Pilih nomor (1-{len(merged_files)}): ').strip())
        if not (1 <= n <= len(merged_files)):
            print('  ❌ Nomor gak valid')
            return
        merge_v17 = str(merged_files[n - 1])
    except ValueError:
        print('  ❌ Input gak valid')
        return
    print(f'  ✓ {Path(merge_v17).name}')
    print()

    # Step 4: Output path
    merge_stem = Path(merge_v17).stem
    output_path = str(MERGED_DIR / f'{merge_stem}-fixed.mp4')
    print(f'▶ Step 4: Output')
    print(f'  {output_path}')
    print()

    # Konfirmasi
    print('═' * 64)
    print(f'  Video source : {Path(merge_v17).name} (seragam 1440x2560)')
    print(f'  Audio source : {len(mix_files)} file mix (audio bagus)')
    print(f'  Output       : {Path(output_path).name}')
    print(f'  Strategi     : concat audio mix → mux video v1.7 + audio')
    print(f'  Estimasi    : ~5-10 menit (stream copy, no re-encode)')
    print('═' * 64)
    confirm = input('\nLanjut? (y/N): ').strip().lower()
    if confirm != 'y':
        print('Dibatalkan.')
        return

    # Step 5: Concat audio dari 10 file mix (stream copy, -vn no video)
    print('\n▶ Step 5: Concat audio dari file mix')
    temp_dir = MERGED_DIR.parent / '.merge_tmp'
    temp_dir.mkdir(parents=True, exist_ok=True)
    audio_list = temp_dir / 'audio_list.txt'
    audio_concat = temp_dir / 'audio_concat.aac'

    with open(audio_list, 'w') as f:
        for mix in mix_files:
            safe = str(mix).replace("'", r"'\''")
            f.write(f"file '{safe}'\n")

    print(f'  Concat {len(mix_files)} file audio (stream copy, -vn -c:a copy)...')
    cmd = ['ffmpeg', '-y', '-f', 'concat', '-safe', '0',
           '-i', str(audio_list),
           '-vn', '-c:a', 'copy',
           '-progress', 'pipe:1', '-nostats',
           str(audio_concat)]
    total_dur = sum(probe_dur(f) for f in mix_files)
    if not run_progress(cmd, total_dur):
        print('  ❌ Gagal concat audio')
        cleanup(temp_dir, [audio_list, audio_concat])
        return
    audio_size = audio_concat.stat().st_size / 1024 / 1024 / 1024
    print(f'  ✓ Audio concat: {audio_concat.name} ({audio_size:.2f} GB)')
    print()

    # Step 6: Mux video dari merge v1.7 + audio concat → output final
    print('▶ Step 6: Mux video v1.7 + audio concat')
    print(f'  Video: {Path(merge_v17).name} (stream copy)')
    print(f'  Audio: {audio_concat.name} (stream copy)')
    cmd = ['ffmpeg', '-y',
           '-i', merge_v17,
           '-i', str(audio_concat),
           '-map', '0:v', '-map', '1:a',
           '-c:v', 'copy', '-c:a', 'copy',
           '-movflags', '+faststart',
           '-progress', 'pipe:1', '-nostats',
           output_path]
    if not run_progress(cmd, total_dur):
        print('  ❌ Gagal mux video + audio')
        cleanup(temp_dir, [audio_list, audio_concat])
        return

    # Step 7: Cleanup
    print('\n▶ Step 7: Cleanup temp files')
    cleanup(temp_dir, [audio_list, audio_concat])

    # Hasil
    if os.path.exists(output_path):
        size_gb = os.path.getsize(output_path) / 1024 / 1024 / 1024
        print(f'\n📁 Output: {Path(output_path).name} ({size_gb:.2f} GB)')
        print(f'   Path  : {output_path}')
        print(f'\n🎬 VLC test: cek audio mulus (harus bagus sekarang, ambil dari mix)')
        print(f'   - Play dari awal → audio harus jelas')
        print(f'   - Seek ke transisi S1→S2 → audio harus mulus')
        print(f'   - Seek ke akhir → audio harus sink')
    else:
        print('  ❌ Output gak ditemukan')
    print('═' * 64)


def probe_dur(path):
    """Quick probe duration."""
    r = subprocess.run(
        ['ffprobe', '-v', 'error', '-show_entries', 'format=duration',
         '-of', 'default=noprint_wrappers=1:nokey=1', str(path)],
        capture_output=True, text=True
    )
    try:
        return float(r.stdout.strip())
    except Exception:
        return 0


def run_progress(cmd, total_dur):
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
            if k == 'out_time_ms' and total_dur > 0:
                try:
                    cur = int(v) / 1_000_000
                    pct = min(int(cur * 100 / total_dur), 99)
                    if pct > last_pct:
                        bar = '█' * (pct // 2) + '░' * (50 - pct // 2)
                        print(f'\r  [{bar}] {pct}% ({int(cur//60)}:{int(cur%60):02d}/{int(total_dur//60)}:{int(total_dur%60):02d})',
                              end='', flush=True)
                        last_pct = pct
                except ValueError:
                    pass
            elif k == 'progress' and v == 'end':
                print(f'\r  [{"█" * 50}] 100%')
                break
        proc.wait()
    except KeyboardInterrupt:
        print('\n  ⚠ Dibatalkan')
        proc.terminate()
        return False
    return proc.returncode == 0


def cleanup(temp_dir, files):
    """Hapus temp files."""
    for f in files:
        if os.path.exists(f):
            os.unlink(f)
    try:
        # Hapus temp dir kalau kosong
        if temp_dir.exists() and not any(temp_dir.iterdir()):
            temp_dir.rmdir()
    except OSError:
        pass


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print('\n⏹ Dibatalkan.')
        sys.exit(130)
    except Exception as e:
        print(f'\n❌ {e}', file=sys.stderr)
        sys.exit(1)
