#!/usr/bin/env python3
"""
mix-tui.py v2 — TUI interaktif untuk mix MP4 + no_vocal + audio_dub

Workflow produksi (4 fase, bersih — sesuai v5 yt-dlp + edge-tts-tui):
  Fase 1: yt-dlp v5      → {name}.mp4 (video) + {name}-audio.m4a (native) + {name}.id.srt
  Fase 2: demucs-tui.py  → split {name}-audio.m4a → no_vocals.mp3 (MP3 320, SFX bersih)
                          + vocals.mp3 (auto-hapus, tidak dipakai)
  Fase 3a: edge-tts-tui.py (LOKAL — ganti web app Mode ON)
                        → {prefix}-audio-id-dub.wav (Bahasa Indonesia, full durasi)
  Fase 3b: web app SRT editor (Bahasa Jawa, per cue — nunggu code fix)
                        → audio-jw-dub.wav
  Fase 4: mix-tui.py v2 → MP4 + no_vocals.mp3 + audio_dub.wav → {prefix}-final.mp4

Mix ini selalu pakai 3 input:
  1. MP4 ori (video, dari yt-dlp v5)
  2. no_vocals (SFX bersih dari Demucs — MP3 320 kbps, vokal ori sudah dibuang)
  3. audio_dub.wav (dialog hasil dubbing dari edge-tts-tui.py atau web app Jawa)

Fitur v2:
  - Default output otomatis dari prefix MP4 (mis. S5-ori.mp4 → S5-ori-id-final.mp4)
  - Validasi semua input file exist sebelum eksekusi
  - Warning prominent kalau dub dur < 90% MP4 dur (kemungkinan generate gagal)
  - Progress bar FFmpeg real-time (size=, time=, bitrate=)
  - Header doc update: Fase 3a = edge-tts-tui.py (bukan web app Mode ON)

Output: MP4 durasi penuh. Setelah dub selesai, SFX tetap bermain (dub = hening).

Mode manual (DaVinci Resolve):
  1. Tarik mp4 ori ke timeline
  2. Tarik no_vocals.mp3 ke timeline
  3. Tarik wav dub (laki + perempuan) ke timeline
  4. Edit manual: mana suara laki (Dimas), mana perempuan (Siti)

Tips durasi:
  - Full season (2.5 jam): MP4 full + SFX full + dub full → 1 output
  - Pecah per episode (30 menit): split SRT dulu, generate per episode, mix per episode
  - Mix durasi penuh: output = MP4 durasi (bukan dub durasi). Setelah dub selesai, SFX tetap bermain.

Install: pip3 install questionary (di venv)
Usage: python3 mix-tui.py (pilih file pakai arrow keys)
"""

import os
import sys
import re
import glob
import subprocess
import time
from pathlib import Path

try:
    import questionary
except ImportError:
    print()
    print('═' * 64)
    print('❌ Dependensi belum lengkap!')
    print('═' * 64)
    print()
    print('   Missing: questionary')
    print()
    print('   Install dengan:')
    print()
    print('   pip3 install questionary')
    print()
    print('   Kalau Mac block, pakai:')
    print()
    print('   pip3 install --break-system-packages questionary')
    print()
    print('═' * 64)
    sys.exit(1)


def clear_screen():
    os.system('clear' if os.name != 'nt' else 'cls')


def print_banner():
    clear_screen()
    print('╔' + '═' * 64 + '╗')
    print('║  🎬 Mix MP4 + No-Vocal SFX + Audio Dub v2 (TUI)' + ' ' * 13 + '║')
    print('║  yt-dlp v5 → Demucs → edge-tts-tui → mix → final' + ' ' * 12 + '║')
    print('╚' + '═' * 64 + '╝')
    print()


def find_files_in_cwd(extensions):
    files = []
    cwd = os.getcwd()
    for ext in extensions:
        for f in glob.glob(os.path.join(cwd, f'*.{ext}')):
            files.append(os.path.basename(f))
        for f in glob.glob(os.path.join(cwd, f'*.{ext.upper()}')):
            files.append(os.path.basename(f))
    files.sort()
    return list(dict.fromkeys(files))  # deduplicate


def select_file(prompt, extensions, default=None):
    available = find_files_in_cwd(extensions)
    if not available:
        path = questionary.text(f'{prompt} (ketik path lengkap):', default=default or '').ask()
        return path
    choices = available + ['[Ketik path manual]']
    selected = questionary.select(prompt, choices=choices, default=available[0]).ask()
    if selected == '[Ketik path manual]':
        return questionary.text(f'{prompt} (ketik path lengkap):', default=default or '').ask()
    return selected


def find_ffmpeg():
    import shutil
    path = shutil.which('ffmpeg')
    if path:
        return path
    for loc in ['/usr/local/bin/ffmpeg', '/usr/bin/ffmpeg', '/opt/homebrew/bin/ffmpeg']:
        if os.path.isfile(loc):
            return loc
    print()
    print('═' * 64)
    print('❌ ffmpeg belum terinstall!')
    print('═' * 64)
    print()
    print('   Install dengan Homebrew:')
    print()
    print('   brew install ffmpeg')
    print()
    print('═' * 64)
    sys.exit(1)


def find_ffprobe():
    import shutil
    path = shutil.which('ffprobe')
    if path:
        return path
    for loc in ['/usr/local/bin/ffprobe', '/usr/bin/ffprobe', '/opt/homebrew/bin/ffprobe']:
        if os.path.isfile(loc):
            return loc
    print()
    print('═' * 64)
    print('❌ ffprobe belum terinstall! Install: brew install ffmpeg')
    print('═' * 64)
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


def validate_input_file(path, label):
    """Cek file exist + size > 0. Kalau tidak, exit dengan pesan jelas."""
    if not path or not path.strip():
        print(f'\n❌ File {label} tidak dipilih.')
        sys.exit(1)
    if not os.path.isfile(path):
        print(f'\n❌ File {label} tidak ditemukan: {path}')
        print(f'   Cek path dan pastikan file ada di folder.')
        sys.exit(1)
    size = os.path.getsize(path)
    if size == 0:
        print(f'\n❌ File {label} kosong (0 bytes): {path}')
        print(f'   Mungkin generate gagal. Coba generate ulang.')
        sys.exit(1)
    return True


def derive_default_output(mp4_path, lang='id'):
    """
    Derive default output filename dari MP4 input.
    Mis. S5-ori.mp4 → S5-ori-id-final.mp4
    """
    base = Path(mp4_path).stem
    # Hapus suffix -ori kalau ada (sesuai konvensi yt-dlp v5)
    if base.endswith('-ori'):
        base = base[:-4]
    return f'{base}-{lang}-final.mp4'


def format_duration(seconds: float) -> str:
    """Format seconds → HH:MM:SS untuk display."""
    if seconds < 0:
        return '0s'
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    if h > 0:
        return f'{h}j {m}m {s}s'
    if m > 0:
        return f'{m}m {s}s'
    return f'{s}s'


def parse_ffmpeg_progress(line: str, total_dur: float):
    """
    Parse FFmpeg stderr line untuk extract progress.
    Format: 'size=   102kB time=00:01:23.45 bitrate= 100.2kbits/s speed=2.5x'
    Returns: dict {time_sec, percent, size_kb, speed} atau None.
    """
    # Cari time= pattern
    m = re.search(r'time=(\d+):(\d+):(\d+(?:\.\d+)?)', line)
    if not m:
        return None
    h, mi, s = m.groups()
    time_sec = int(h) * 3600 + int(mi) * 60 + float(s)

    size_m = re.search(r'size=\s*(\d+)kB', line)
    size_kb = int(size_m.group(1)) if size_m else 0

    speed_m = re.search(r'speed=\s*([\d.]+)x', line)
    speed = float(speed_m.group(1)) if speed_m else 0

    percent = (time_sec / total_dur * 100) if total_dur > 0 else 0
    return {
        'time_sec': time_sec,
        'percent': min(percent, 100),
        'size_kb': size_kb,
        'speed': speed,
    }


def run_ffmpeg_with_progress(cmd, total_dur: float):
    """Jalankan FFmpeg dengan stderr parsing untuk progress bar real-time."""
    proc = subprocess.Popen(
        cmd,
        stderr=subprocess.PIPE,
        stdout=subprocess.DEVNULL,
        universal_newlines=True,
        bufsize=1,
    )
    last_print = 0
    start_time = time.time()
    for line in proc.stderr:
        progress = parse_ffmpeg_progress(line, total_dur)
        if progress and (time.time() - last_print) > 0.5:
            elapsed = time.time() - start_time
            elapsed_fmt = format_duration(elapsed)
            eta = (total_dur - progress['time_sec']) / max(0.1, progress['speed']) if progress['speed'] > 0 else 0
            eta_fmt = format_duration(eta) if eta > 0 else '?'
            size_mb = progress['size_kb'] / 1024
            # Print inline (carriage return supaya tidak numpuk baris)
            sys.stdout.write(
                f'\r  {progress["percent"]:5.1f}% | '
                f'time={format_duration(progress["time_sec"]):>8} / {format_duration(total_dur):>8} | '
                f'size={size_mb:6.1f} MB | '
                f'speed={progress["speed"]:.1f}x | '
                f'elapsed={elapsed_fmt} | ETA={eta_fmt}'
            )
            sys.stdout.flush()
            last_print = time.time()
    proc.wait()
    sys.stdout.write('\n')
    sys.stdout.flush()
    return proc.returncode


def prompt_ducking():
    """Prompt ducking level, return dB integer."""
    ducking_choices = [
        '12 dB (default, seimbang) — REKOMENDASI',
        '6 dB (SFX lebih keras)',
        '18 dB (SFX lebih pelan, dub dominan)',
        '0 dB / no ducking (SFX + dub sama keras)',
    ]
    ducking_choice = questionary.select('Ducking:', choices=ducking_choices, default=ducking_choices[0]).ask()
    if not ducking_choice:
        return 12
    return int(ducking_choice.split(' dB')[0])


def prompt_output(default_output):
    """Prompt output filename, return string."""
    output = questionary.text('Output MP4:', default=default_output).ask()
    return output or default_output


def main():
    print_banner()

    print('📋 Mode: Mix cepat (TUI v2) — MP4 + SFX no-vocal + dub dengan ducking')
    print('   Mode manual (DaVinci): tarik file ke timeline, edit sendiri')
    print()
    print('   Navigasi: ↑↓ arrow keys, Enter konfirmasi, q batal')
    print()

    total = 6

    # Step 1: MP4 ori (video)
    print(f'▶ Step 1/{total}: Pilih file MP4 ori (video)')
    mp4 = select_file('MP4 ori (mis. S5-ori.mp4 dari yt-dlp v5):', ['mp4'])
    if not mp4:
        print('Batal.'); sys.exit(0)
    print(f'  ✓ {mp4}')
    print()

    # Step 2: no_vocals (SFX bersih dari Demucs)
    print(f'▶ Step 2/{total}: Pilih file SFX bersih (no_vocals.mp3 / .wav)')
    sfx_wav = select_file('SFX bersih (no_vocals dari demucs-tui):', ['mp3', 'wav', 'flac'])
    if not sfx_wav:
        print('Batal.'); sys.exit(0)
    print(f'  ✓ {sfx_wav}')
    print()

    # Step 3: Audio dub
    print(f'▶ Step 3/{total}: Pilih file audio dub WAV')
    audio_dub = select_file('Audio dub (mis. S5-ori.id-audio-id-dub.wav):', ['wav'])
    if not audio_dub:
        print('Batal.'); sys.exit(0)
    print(f'  ✓ {audio_dub}')
    print()

    # === Validasi semua input file exist (Bug #4 fix) ===
    print('▶ Validasi input file...')
    validate_input_file(mp4, 'MP4 ori')
    validate_input_file(sfx_wav, 'SFX no_vocals')
    validate_input_file(audio_dub, 'Audio dub')
    print('  ✓ Semua file valid')
    print()

    # Step 4: Ducking
    print(f'▶ Step 4/{total}: Pilih ducking level')
    ducking_db = prompt_ducking()
    print(f'  ✓ {ducking_db}dB')
    print()

    # Step 5: Output — default derive dari MP4 prefix (Bug #1 fix)
    print(f'▶ Step 5/{total}: Pilih nama output MP4')
    default_output = derive_default_output(mp4, lang='id')
    output = prompt_output(default_output)
    print(f'  ✓ {output}')
    print()

    # Step 6: Konfirmasi
    print(f'▶ Step 6/{total}: Konfirmasi')

    # Probe durations
    ffmpeg = find_ffmpeg()
    ffprobe = find_ffprobe()
    mp4_dur = get_duration(ffprobe, mp4)
    sfx_dur = get_duration(ffprobe, sfx_wav)
    dub_dur = get_duration(ffprobe, audio_dub)

    print()
    print('╔' + '═' * 64 + '╗')
    print('║  📋 Ringkasan:' + ' ' * 49 + '║')
    print('╠' + '═' * 64 + '╣')
    print(f'║  MP4      : {mp4[:46]:<46}║')
    print(f'║  SFX      : {sfx_wav[:46]:<46}║')
    print(f'║  Audio dub: {audio_dub[:46]:<46}║')
    print(f'║  Output   : {output[:46]:<46}║')
    print(f'║  Ducking  : {str(ducking_db) + " dB":<46}║')
    print(f'║  MP4 dur  : {format_duration(mp4_dur):<46}║')
    print(f'║  SFX dur  : {format_duration(sfx_dur):<46}║')
    print(f'║  Dub dur  : {format_duration(dub_dur):<46}║')
    print('╚' + '═' * 64 + '╝')
    print()

    # === Bug #5 fix: warning prominent kalau dub < 90% MP4 dur ===
    if mp4_dur > 0 and dub_dur > 0:
        ratio = dub_dur / mp4_dur
        if ratio < 0.9:
            print('═' * 64)
            print('⚠  WARNING: Audio dub lebih pendek dari MP4!')
            print('═' * 64)
            print(f'  MP4 dur : {format_duration(mp4_dur)}')
            print(f'  Dub dur : {format_duration(dub_dur)} ({ratio*100:.1f}% dari MP4)')
            print(f'  Setelah dub selesai (di {format_duration(dub_dur)}),')
            print(f'  hanya SFX yang bermain sampai MP4 selesai.')
            print()
            print(f'  Kemungkinan sebab:')
            print(f'   - Generate TTS gagal di tengah (cek .cache/ untuk resume)')
            print(f'   - SRT hanya sampai {format_duration(dub_dur)} (bukan masalah)')
            print()
            if not questionary.confirm('Tetap lanjut mix?', default=False).ask():
                print('Batal. Cek file dub dulu.'); sys.exit(0)
            print()
        elif ratio < 1.0:
            print(f'  ℹ Audio dub ({format_duration(dub_dur)}) sedikit lebih pendek dari MP4 ({format_duration(mp4_dur)}).')
            print(f'    Setelah dub selesai, hanya SFX yang bermain.')
            print()
    elif mp4_dur > 0 and dub_dur == 0:
        print(f'  ⚠ Audio dur 0 — mungkin file corrupt atau ffprobe gagal baca.')
        print()
        if not questionary.confirm('Tetap lanjut mix?', default=False).ask():
            sys.exit(0)
        print()

    confirm = questionary.confirm('Lanjut eksekusi?', default=True).ask()
    if not confirm:
        print('Batal.'); sys.exit(0)

    # Build FFmpeg command
    # Indeks input: 0=mp4 (video only), 1=sfx_wav, 2=audio_dub
    print('\n' + '═' * 64)
    print('🚀 Mulai mix...')
    print('═' * 64 + '\n')

    if ducking_db <= 0:
        # No ducking: additive mix (amix dengan normalize=0)
        filter_complex = (
            '[1:a]volume=1[sfx];'
            '[2:a]volume=1[dub];'
            '[sfx][dub]amix=inputs=2:duration=longest:normalize=0[aout]'
        )
    else:
        # Ducking: sidechain compression (no makeup gain, no -shortest)
        ratio = 10 if ducking_db >= 10 else 5
        filter_complex = (
            f'[1:a]volume=1[sfx];'
            f'[2:a]volume=1,asplit=2[dub][sidechain];'
            f'[sfx][sidechain]sidechaincompress='
            f'threshold=0.05:ratio={ratio}:attack=5:release=300'
            f'[ducked_sfx];'
            f'[ducked_sfx][dub]amix=inputs=2:duration=longest:normalize=0[aout]'
        )

    cmd = [ffmpeg, '-y', '-i', mp4, '-i', sfx_wav, '-i', audio_dub,
           '-filter_complex', filter_complex,
           '-map', '0:v', '-map', '[aout]',
           '-c:v', 'copy', '-c:a', 'aac', '-b:a', '192k',
           '-movflags', '+faststart', output]

    print(f'Command: ffmpeg -y -i [mp4] -i [sfx] -i [dub] -filter_complex ... -c:v copy -c:a aac -b:a 192k {output}')
    print()
    print('Progress:')
    print()

    try:
        # Bug #8 fix: progress bar real-time
        exit_code = run_ffmpeg_with_progress(cmd, mp4_dur)
    except KeyboardInterrupt:
        print('\n\n⏹ Dibatalkan user.')
        # Hapus output partial
        if os.path.isfile(output):
            try:
                os.unlink(output)
                print(f'Partial output dihapus: {output}')
            except OSError:
                pass
        sys.exit(130)

    print()
    if exit_code == 0 and os.path.isfile(output):
        out_size = os.path.getsize(output) / 1024 / 1024
        out_dur = get_duration(ffprobe, output)
        print('═' * 64)
        print('✅ SELESAI!')
        print(f'   Output: {output}')
        print(f'   Size: {out_size:.1f} MB')
        print(f'   Duration: {format_duration(out_dur)}')
        print()
        print('🎬 Langkah berikutnya:')
        print(f'   1. Preview: open {output} di QuickTime / VLC')
        print(f'   2. Kalau perlu edit (sfx level, dub per cue): DaVinci Resolve')
        print(f'   3. Upload: langsung publish ke platform (TikTok/IG/YouTube)')
        print(f'   4. Split per episode (opsional): ffmpeg -ss 0 -t 1800 -c copy ep01.mp4')
        print('═' * 64)
    else:
        print('═' * 64)
        print(f'❌ GAGAL dengan exit code {exit_code}')
        print()
        print('Cek error message di atas. Umumnya:')
        print('  - "No such file" → file input hilang atau path salah')
        print('  - "Invalid data found" → file corrupt, coba re-generate')
        print('  - "Cannot allocate memory" → audio terlalu panjang, split dulu')
        print('═' * 64)

    sys.exit(exit_code)


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print('\n\n⏹ Dibatalkan user.')
        sys.exit(130)
    except Exception as e:
        print(f'\n❌ Error: {e}', file=sys.stderr)
        import traceback
        print(f'\n{traceback.format_exc()[:500]}', file=sys.stderr)
        sys.exit(1)
