#!/usr/bin/env python3
"""
fix-merge-audio.py v1.3 — Fix audio output merge-tui v1.7 (audio kacau).

User feedback v1.7: 'audio = parah. banyak yg silen dan banyak suara jadi cepat'.
Output v1.7 resolusi udah seragam (1440x2560), tapi audio kacau (sample rate mismatch).

Fix: ambil video dari output v1.7 (seragam) + concat audio dari file mix (bagus, re-encode normalize).
Gak perlu merge lagi 4 jam, cuma butuh ~30-45 menit (audio re-encode 1x, video stream copy).

v1.3: Fix questionary default bug — pakai Choice(checked=True) (reliable, bukan default list).
v1.2: Re-encode audio ke 48000 Hz stereo saat concat (normalize sample rate mismatch).
v1.1: questionary (auto-detect prefix, gak perlu ketik).

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

try:
    import questionary
except ImportError:
    print('\n❌ pip3 install questionary')
    sys.exit(1)

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


def fmt_dur(s):
    if not s:
        return '00:00:00'
    h = int(s // 3600); m = int((s % 3600) // 60); sec = int(s % 60)
    return f'{h:02d}:{m:02d}:{sec:02d}'


def fmt_size(mb):
    if mb < 1024:
        return f'{mb:.1f}MB'
    return f'{mb/1024:.2f}GB'


def detect_prefix(files):
    """Auto-detect common prefix dari list file.

    Untuk '5 Tentara Modern di Dinasty Song S1.mp4' dan S2..S10,
    common prefix = '5 Tentara Modern di Dinasty Song S' (tanpa digit terakhir).
    Tapi user mau lebih simple: detect prefix yang menghasilkan grup file.

    Strategi: ambil prefix terpanjang yang muncul di semua file, lalu truncate ke kata terakhir
    sebelum digit pertama yang beda.
    """
    if not files:
        return ''
    # Ambil common prefix
    common = os.path.commonprefix([f.name for f in files])
    # Truncate ke kata terakhir (potong di separator terakhir yang bukan digit)
    # Mis. '5 Tentara Modern di Dinasty Song S1' → truncate ke '5 Tentara Modern di Dinasty Song'
    # Cari digit terakhir di common prefix, truncate sampai sana
    match = re.search(r'(.+?)(\d+)?$', common.rstrip())
    if match:
        return match.group(1).rstrip()
    return common.rstrip()


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
                        print(f'\r  [{bar}] {pct}% ({fmt_dur(cur)}/{fmt_dur(total_dur)})',
                              end='', flush=True)
                        last_pct = pct
                except ValueError:
                    pass
            elif k == 'progress' and v == 'end':
                print(f'\r  [{"█" * 50}] 100% ({fmt_dur(total_dur)})')
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
        if temp_dir.exists() and not any(temp_dir.iterdir()):
            temp_dir.rmdir()
    except OSError:
        pass


def main():
    print('╔' + '═' * 64 + '╗')
    print('║  🔧 Fix Merge Audio v1.3 (fix v1.7 audio kacau)            ║')
    print('║  Mux video v1.7 + audio normalize (re-encode 48000 Hz)    ║')
    print('╚' + '═' * 64 + '╝')
    print()

    if not ensure_hdd():
        return

    # Step 1: Auto-list file mix dengan questionary checkbox (kayak merge-tui)
    print('▶ Step 1: Pilih file mix (audio bagus)')
    all_mix = sorted(MIX_DIR.glob('*.mp4'), key=lambda p: natural_sort_key(p.name))
    if not all_mix:
        print(f'  ❌ Tidak ada MP4 di {MIX_DIR}')
        return

    print(f'  Ditemukan {len(all_mix)} MP4 di {MIX_DIR}')
    print()

    # Auto-detect prefix untuk suggest
    suggested_prefix = detect_prefix(all_mix[:10])  # ambil 10 pertama buat detect
    print(f'  Auto-detected prefix: "{suggested_prefix}"')

    # Filter file mix yang match prefix (untuk auto-tercentang)
    matching = [f for f in all_mix if f.name.startswith(suggested_prefix)] if suggested_prefix else []
    matching_names = {f.name for f in matching}
    print(f'  Files match prefix: {len(matching)}')
    print()

    # v1.3 FIX: pakai Choice(checked=True) bukan default list (questionary bug)
    # Build choices: setiap file mix + flag checked kalau match prefix
    from questionary import Choice
    file_choices = [
        Choice(f.name, checked=(f.name in matching_names))
        for f in all_mix
    ] + [Choice('[Ketik path manual]', checked=False)]

    # Pakai questionary checkbox untuk multi-select (default via Choice.checked)
    selected = questionary.checkbox(
        'Pilih file mix (Space untuk centang, Enter untuk selesai):',
        choices=file_choices,
    ).ask()

    if not selected:
        print('  Dibatalkan.')
        return

    # Build mix_files list
    mix_files = []
    for sel in selected:
        if sel == '[Ketik path manual]':
            manual = questionary.text('Ketik path file:').ask()
            if manual and manual.strip():
                p = os.path.expanduser(manual.strip().strip("'\""))
                if os.path.exists(p):
                    mix_files.append(Path(p))
        else:
            mix_files.append(MIX_DIR / sel)

    # Natural sort lagi biar urutan bener
    mix_files.sort(key=lambda p: natural_sort_key(p.name))

    if len(mix_files) < 2:
        print(f'\n  ❌ Butuh minimal 2 file mix')
        return

    print(f'\n  ✓ {len(mix_files)} file mix dipilih:')
    total_dur = 0
    for i, f in enumerate(mix_files, 1):
        dur = probe_dur(f)
        total_dur += dur
        size_mb = f.stat().st_size / 1024 / 1024
        print(f'    [{i}] {f.name} | {fmt_dur(dur)} | {fmt_size(size_mb)}')
    print(f'    Total: {fmt_dur(total_dur)}')
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

    # Step 3: Pilih file merge v1.7 (output yang audio-nya kacau) pakai questionary
    print('▶ Step 3: Pilih file merge v1.7 (audio kacau)')
    merged_files = sorted(MERGED_DIR.glob('*.mp4'), key=lambda p: natural_sort_key(p.name))
    if not merged_files:
        print(f'  ❌ Tidak ada file di {MERGED_DIR}')
        return

    merged_choices = [f.name for f in merged_files]
    sel_name = questionary.select(
        'Pilih file merge (audio kacau):',
        choices=merged_choices,
        default=merged_choices[0],
    ).ask()

    if not sel_name:
        print('  Dibatalkan.')
        return
    merge_v17 = str(MERGED_DIR / sel_name)
    size_gb = os.path.getsize(merge_v17) / 1024 / 1024 / 1024
    print(f'  ✓ {sel_name} ({size_gb:.2f} GB)')
    print()

    # Step 4: Output path (auto-derive, questionary text dengan default)
    merge_stem = Path(merge_v17).stem
    default_output = str(MERGED_DIR / f'{merge_stem}-fixed.mp4')
    print('▶ Step 4: Output path')
    output_path = questionary.text(
        'Output path (Enter untuk default):',
        default=default_output,
    ).ask()
    if not output_path or not output_path.strip():
        output_path = default_output
    else:
        output_path = os.path.expanduser(output_path.strip())
    print(f'  ✓ {output_path}')
    print()

    # Konfirmasi
    print('═' * 64)
    print(f'  Video source : {Path(merge_v17).name} (seragam, audio kacau)')
    print(f'  Audio source : {len(mix_files)} file mix (audio bagus)')
    print(f'  Output       : {Path(output_path).name}')
    print(f'  Strategi     : concat audio mix (re-encode normalize) → mux video v1.7 + audio')
    print(f'  Estimasi    : ~30-45 menit (audio re-encode 1x, video stream copy)')
    print('═' * 64)
    if not questionary.confirm('\nLanjut?', default=True).ask():
        print('Dibatalkan.')
        return

    # Step 5: Concat audio dari file mix (v1.2: re-encode normalize sample rate)
    # Bug v1.0: stream copy concat = sample rate campur (24000, 44100, 48000 Hz) → VLC kacau
    # Fix v1.2: -c:a aac -b:a 192k -ar 48000 -ac 2 (normalize semua file ke konsisten)
    print('\n▶ Step 5: Concat audio dari file mix (re-encode normalize 48000 Hz stereo)')
    temp_dir = MERGED_DIR.parent / '.merge_tmp'
    temp_dir.mkdir(parents=True, exist_ok=True)
    audio_list = temp_dir / 'audio_list.txt'
    audio_concat = temp_dir / 'audio_concat.aac'

    with open(audio_list, 'w') as f:
        for mix in mix_files:
            safe = str(mix).replace("'", r"'\''")
            f.write(f"file '{safe}'\n")

    print(f'  Concat {len(mix_files)} file audio (re-encode aac 192k 48000 Hz stereo)...')
    print(f'  Estimasi: ~30-45 menit (audio re-encode 24 jam, single pass)')
    cmd = ['ffmpeg', '-y', '-f', 'concat', '-safe', '0',
           '-i', str(audio_list),
           '-vn',  # no video
           '-c:a', 'aac', '-b:a', '192k',  # re-encode normalize
           '-ar', '48000', '-ac', '2',     # 48000 Hz stereo konsisten
           '-progress', 'pipe:1', '-nostats',
           str(audio_concat)]
    if not run_progress(cmd, total_dur):
        print('\n  ❌ Gagal concat audio')
        cleanup(temp_dir, [audio_list, audio_concat])
        return
    audio_size = audio_concat.stat().st_size / 1024 / 1024 / 1024
    print(f'  ✓ Audio concat: {audio_concat.name} ({audio_size:.2f} GB, 48000 Hz stereo)')
    print()

    # Step 6: Mux video dari merge v1.7 + audio concat → output final
    print('▶ Step 6: Mux video v1.7 + audio concat (stream copy both)')
    print(f'  Video: {Path(merge_v17).name} (stream copy)')
    print(f'  Audio: {audio_concat.name} (stream copy, sudah 48000 Hz stereo)')
    cmd = ['ffmpeg', '-y',
           '-i', merge_v17,
           '-i', str(audio_concat),
           '-map', '0:v', '-map', '1:a',
           '-c:v', 'copy', '-c:a', 'copy',
           '-movflags', '+faststart',
           '-progress', 'pipe:1', '-nostats',
           output_path]
    if not run_progress(cmd, total_dur):
        print('\n  ❌ Gagal mux video + audio')
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
        print(f'   - Seek ke akhir → audio harus sync')
    else:
        print('  ❌ Output gak ditemukan')
    print('═' * 64)


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print('\n⏹ Dibatalkan.')
        sys.exit(130)
    except Exception as e:
        print(f'\n❌ {e}', file=sys.stderr)
        sys.exit(1)
