#!/usr/bin/env python3
"""
mix-tui.py — TUI interaktif untuk mix SFX + audio dub + MP4

Dua mode operasi (dipilih di Step 0):
  Mode A — MP4 dengan audio:  SFX = audio dari MP4 ori (vokal ori tetap ada)
          Pakai kalau sumber cuma MP4 (belum jalankan Demucs).
          Input : MP4 + audio_dub
          Step  : 5 (mp4 → dub → ducking → output → konfirmasi)

  Mode B — Sumber terpisah:   SFX = no_vocal.wav (clean, hasil Demucs)
          Pakai kalau sudah ada no_vocals.wav dari Demucs.
          Input : MP4 + no_vocal.wav + audio_dub
          Step  : 6 (mp4 → no_vocal → dub → ducking → output → konfirmasi)

Workflow 3 fase (mode cepat, Mode B):
  Fase 0: demucs-tui.py → no_vocals.wav (SFX bersih)
  Fase 1: Web app mode ON + Smart Fit → audio-id-dub.wav (dialog)
  Fase 2: mix-tui.py → mp4-id-final.mp4 (video ori + SFX + dub)

Workflow 2 fase (Mode A, tanpa Demucs):
  Fase 1: Web app mode ON + Smart Fit → audio-id-dub.wav (dialog)
  Fase 2: mix-tui.py → mp4-id-final.mp4 (video ori + audio ori + dub)
  ⚠ Audio ori (vokal) tetap terdengar sebagai SFX. Untuk hasil bersih, pakai Mode B.

Mode manual (DaVinci Resolve):
  1. Tarik mp4 ori ke timeline
  2. Tarik wav SFX (no_vocals.wav) ke timeline (Mode B)
  3. Tarik wav dub (laki + perempuan) ke timeline
  4. Edit manual: mana suara laki, mana perempuan

Tips durasi:
  - Full season (2.5 jam): MP4 full + SFX full + dub full → 1 output
  - Pecah per episode (30 menit): split SRT dulu, generate per episode, mix per episode
  - Mix durasi penuh: output = MP4 durasi (bukan dub durasi). Setelah dub selesai, SFX tetap bermain.

Install: pip3 install questionary (di venv)
Usage: python3 mix-tui.py (pilih file pakai arrow keys)
"""

import os
import sys
import glob
import subprocess
from pathlib import Path

try:
    import questionary
except ImportError:
    print('\n❌ Library "questionary" belum terinstall.')
    print('   Install dengan: pip3 install questionary')
    print()
    sys.exit(1)


def clear_screen():
    os.system('clear' if os.name != 'nt' else 'cls')


def print_banner():
    clear_screen()
    print('╔' + '═' * 64 + '╗')
    print('║  🎬 Mix Audio Dub + SFX + MP4 (TUI Mode)' + ' ' * 23 + '║')
    print('║  Mode A: MP4 dgn audio | Mode B: Sumber terpisah' + ' ' * 13 + '║')
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
    raise FileNotFoundError('ffmpeg tidak ditemukan di PATH. Install: brew install ffmpeg')


def find_ffprobe():
    import shutil
    path = shutil.which('ffprobe')
    if path:
        return path
    for loc in ['/usr/local/bin/ffprobe', '/usr/bin/ffprobe', '/opt/homebrew/bin/ffprobe']:
        if os.path.isfile(loc):
            return loc
    raise FileNotFoundError('ffprobe tidak ditemukan di PATH.')


def get_duration(ffprobe, path):
    result = subprocess.run([
        ffprobe, '-v', 'error', '-show_entries', 'format=duration',
        '-of', 'default=noprint_wrappers=1:nokey=1', path,
    ], capture_output=True, text=True)
    try:
        return float(result.stdout.strip())
    except Exception:
        return 0


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


def prompt_output(default_output='mp4-id-final.mp4'):
    """Prompt output filename, return string."""
    output = questionary.text('Output MP4:', default=default_output).ask()
    return output or default_output


def main():
    print_banner()

    print('📋 Mode: Mix cepat (TUI) — video + SFX + dub dengan ducking')
    print('   Mode manual (DaVinci): tarik file ke timeline, edit sendiri')
    print()
    print('   Navigasi: ↑↓ arrow keys, Enter konfirmasi, q batal')
    print()

    # Step 0: Pilih mode
    print('▶ Step 0: Pilih mode mix')
    mode_choices = [
        'Mode B: Sumber terpisah (MP4 + no_vocal + dub) — clean, hasil Demucs — REKOMENDASI',
        'Mode A: MP4 dengan audio (SFX dari MP4 ori) — quick, vokal ori tetap ada',
    ]
    mode_choice = questionary.select('Mode mix:', choices=mode_choices, default=mode_choices[0]).ask()
    if not mode_choice:
        print('Batal.'); sys.exit(0)

    is_mode_b = 'Mode B' in mode_choice
    mode_label = 'Mode B (sumber terpisah)' if is_mode_b else 'Mode A (MP4 dengan audio)'
    print(f'  ✓ {mode_label}')
    print()

    # Shared state
    mp4 = None
    sfx_wav = None  # None in Mode A → SFX dari MP4 ori
    audio_dub = None
    ducking_db = 12
    output = 'mp4-id-final.mp4'

    if is_mode_b:
        # ─────────────────────────────────────────────────────────────────
        # Mode B: Sumber terpisah (6 langkah)
        # ─────────────────────────────────────────────────────────────────
        total = 6

        # Step 1: MP4 ori (video)
        print(f'▶ Step 1/{total}: Pilih file MP4 ori (video)')
        mp4 = select_file('MP4 ori (mis. mp4-ori-full.mp4):', ['mp4'])
        if not mp4:
            print('Batal.'); sys.exit(0)
        print(f'  ✓ {mp4}')
        print()

        # Step 2: no_vocal.wav (SFX bersih)
        print(f'▶ Step 2/{total}: Pilih file no_vocal.wav (SFX bersih dari Demucs)')
        sfx_wav = select_file('SFX bersih (no_vocals.wav):', ['wav'])
        if not sfx_wav:
            print('Batal.'); sys.exit(0)
        print(f'  ✓ {sfx_wav}')
        print()

        # Step 3: Audio dub
        print(f'▶ Step 3/{total}: Pilih file audio dub WAV')
        audio_dub = select_file('Audio dub (mis. audio-id-dub.wav, audio-jw-dub.wav):', ['wav'])
        if not audio_dub:
            print('Batal.'); sys.exit(0)
        print(f'  ✓ {audio_dub}')
        print()

        # Step 4: Ducking
        print(f'▶ Step 4/{total}: Pilih ducking level')
        ducking_db = prompt_ducking()
        print(f'  ✓ {ducking_db}dB')
        print()

        # Step 5: Output
        print(f'▶ Step 5/{total}: Pilih nama output MP4')
        output = prompt_output(output)
        print(f'  ✓ {output}')
        print()

        # Step 6: Konfirmasi
        print(f'▶ Step 6/{total}: Konfirmasi')

    else:
        # ─────────────────────────────────────────────────────────────────
        # Mode A: MP4 dengan audio (5 langkah)
        # ─────────────────────────────────────────────────────────────────
        total = 5

        # Step 1: MP4 (with audio)
        print(f'▶ Step 1/{total}: Pilih file MP4 ori (dengan audio)')
        mp4 = select_file('MP4 ori (mis. mp4-ori-full.mp4, mp4-ori-test-7min.mp4):', ['mp4'])
        if not mp4:
            print('Batal.'); sys.exit(0)
        print(f'  ✓ {mp4}')
        print()

        # Step 2: Audio dub
        print(f'▶ Step 2/{total}: Pilih file audio dub WAV')
        audio_dub = select_file('Audio dub (mis. audio-id-dub.wav, audio-jw-dub.wav):', ['wav'])
        if not audio_dub:
            print('Batal.'); sys.exit(0)
        print(f'  ✓ {audio_dub}')
        print()

        # Step 3: Ducking
        print(f'▶ Step 3/{total}: Pilih ducking level')
        ducking_db = prompt_ducking()
        print(f'  ✓ {ducking_db}dB')
        print()

        # Step 4: Output
        print(f'▶ Step 4/{total}: Pilih nama output MP4')
        output = prompt_output(output)
        print(f'  ✓ {output}')
        print()

        # Step 5: Konfirmasi
        print(f'▶ Step 5/{total}: Konfirmasi')

    # ─────────────────────────────────────────────────────────────────────
    # Probe durations untuk ringkasan
    # ─────────────────────────────────────────────────────────────────────
    ffmpeg = find_ffmpeg()
    ffprobe = find_ffprobe()
    mp4_dur = get_duration(ffprobe, mp4)
    dub_dur = get_duration(ffprobe, audio_dub)

    print()
    print('╔' + '═' * 64 + '╗')
    print('║  📋 Ringkasan:' + ' ' * 49 + '║')
    print('╠' + '═' * 64 + '╣')
    print(f'║  Mode     : {mode_label[:46]:<46}║')
    print(f'║  MP4      : {mp4[:46]:<46}║')
    if sfx_wav:
        print(f'║  SFX      : {sfx_wav[:46]:<46}║')
    else:
        print(f'║  SFX      : {"(dari MP4 ori, vokal ori masih ada)":<46}║')
    print(f'║  Audio dub: {audio_dub[:46]:<46}║')
    print(f'║  Output   : {output[:46]:<46}║')
    print(f'║  Ducking  : {str(ducking_db) + " dB":<46}║')
    print(f'║  MP4 dur  : {mp4_dur:.1f}s' + ' ' * (46 - len(f'{mp4_dur:.1f}s')) + '║')
    print(f'║  Dub dur  : {dub_dur:.1f}s' + ' ' * (46 - len(f'{dub_dur:.1f}s')) + '║')
    print('╚' + '═' * 64 + '╝')
    print()

    if not is_mode_b:
        print('  ⚠ Mode A: audio ori (vokal) tetap terdengar sebagai SFX.')
        print('           Untuk hasil bersih, jalankan Demucs dulu → pakai Mode B.')
        print()

    if dub_dur < mp4_dur - 1:
        print(f'  ℹ Audio dub ({dub_dur:.1f}s) lebih pendek dari MP4 ({mp4_dur:.1f}s).')
        print(f'    Setelah dub selesai, hanya SFX yang bermain (dub = hening).')
        print(f'    Output = MP4 durasi penuh ({mp4_dur:.1f}s).')
        print()

    confirm = questionary.confirm('Lanjut eksekusi?', default=True).ask()
    if not confirm:
        print('Batal.'); sys.exit(0)

    # ─────────────────────────────────────────────────────────────────────
    # Build FFmpeg command
    # ─────────────────────────────────────────────────────────────────────
    print('\n' + '═' * 64)
    print('🚀 Mulai mix...')
    print('═' * 64 + '\n')

    # Catatan indeks input:
    #  - Mode A: 0=mp4 (audio=0:a sebagai SFX), 1=audio_dub
    #  - Mode B: 0=mp4 (video only, audio di-ignore), 1=sfx_wav (SFX), 2=audio_dub
    if ducking_db <= 0:
        # No ducking: additive mix (amix dengan normalize=0)
        if sfx_wav:
            # Mode B no ducking
            filter_complex = (
                '[1:a]volume=1[sfx];'
                '[2:a]volume=1[dub];'
                '[sfx][dub]amix=inputs=2:duration=longest:normalize=0[aout]'
            )
            cmd = [ffmpeg, '-y', '-i', mp4, '-i', sfx_wav, '-i', audio_dub,
                   '-filter_complex', filter_complex,
                   '-map', '0:v', '-map', '[aout]',
                   '-c:v', 'copy', '-c:a', 'aac', '-b:a', '192k',
                   '-movflags', '+faststart', output]
        else:
            # Mode A no ducking (SFX = audio MP4 ori)
            filter_complex = (
                '[0:a]volume=1[sfx];'
                '[1:a]volume=1[dub];'
                '[sfx][dub]amix=inputs=2:duration=longest:normalize=0[aout]'
            )
            cmd = [ffmpeg, '-y', '-i', mp4, '-i', audio_dub,
                   '-filter_complex', filter_complex,
                   '-map', '0:v', '-map', '[aout]',
                   '-c:v', 'copy', '-c:a', 'aac', '-b:a', '192k',
                   '-movflags', '+faststart', output]
    else:
        # Ducking: sidechain compression (FIX: no makeup gain, no -shortest)
        ratio = 10 if ducking_db >= 10 else 5
        if sfx_wav:
            # Mode B with ducking
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
        else:
            # Mode A with ducking (SFX = audio MP4 ori)
            filter_complex = (
                f'[0:a]volume=1[sfx];'
                f'[1:a]volume=1,asplit=2[dub][sidechain];'
                f'[sfx][sidechain]sidechaincompress='
                f'threshold=0.05:ratio={ratio}:attack=5:release=300'
                f'[ducked_sfx];'
                f'[ducked_sfx][dub]amix=inputs=2:duration=longest:normalize=0[aout]'
            )
            cmd = [ffmpeg, '-y', '-i', mp4, '-i', audio_dub,
                   '-filter_complex', filter_complex,
                   '-map', '0:v', '-map', '[aout]',
                   '-c:v', 'copy', '-c:a', 'aac', '-b:a', '192k',
                   '-movflags', '+faststart', output]

    print(f'Command: {" ".join(cmd[:5])} ...')
    print()

    try:
        result = subprocess.run(cmd)
        exit_code = result.returncode
    except KeyboardInterrupt:
        print('\n\n⏹ Dibatalkan user.')
        sys.exit(130)

    print()
    if exit_code == 0 and os.path.isfile(output):
        out_size = os.path.getsize(output) / 1024 / 1024
        out_dur = get_duration(ffprobe, output)
        print('═' * 64)
        print('✅ SELESAI!')
        print(f'   Output: {output}')
        print(f'   Size: {out_size:.1f} MB')
        print(f'   Duration: {out_dur:.1f}s')
        print()
        print('🎬 Langkah berikutnya:')
        print('   Mode cepat (TUI): selesai → buka di VLC')
        print('   Mode manual (DaVinci): tarik mp4 ori + SFX + dub ke timeline')
        print('═' * 64)
    else:
        print('═' * 64)
        print(f'❌ GAGAL dengan exit code {exit_code}')
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
