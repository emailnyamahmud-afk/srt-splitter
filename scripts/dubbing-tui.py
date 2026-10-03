#!/usr/bin/env python3
"""
dubbing-tui.py — Text User Interface untuk Fase 4 Dubbing Workflow

Aplikasi TUI interaktif untuk retim video Mandarin → Jawa.
User pilih file dengan arrow keys, tidak perlu ketik command panjang.

Requirements:
  - Python 3.8+
  - questionary: pip3 install questionary
  - retime-video.py (sibling script)
  - ffmpeg (auto-detect)

Usage:
  python3 dubbing-tui.py

Alur:
  1. Welcome screen
  2. Pilih MP4 Mandarin (arrow keys atau ketik manual)
  3. Pilih SRT Mandarin
  4. Pilih SRT Jawa (dari DUB web)
  5. Pilih Audio Jawa WAV (dari DUB web)
  6. Pilih output MP4
  7. Pilih mode SFX (basic / separate-sfx / no-sfx)
  8. Pilih SFX ducking level (kalau pakai SFX)
  9. Pilih action (dry-run / run)
  10. Ringkasan + konfirmasi
  11. Eksekusi: panggil retime-video.py dengan args yang sesuai
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
    print('   Atau:           pip3 install questionary --break-system-packages')
    print()
    sys.exit(1)


# ============================================================
# Helper functions
# ============================================================

def clear_screen():
    os.system('clear' if os.name != 'nt' else 'cls')


def print_banner():
    clear_screen()
    print('╔' + '═' * 64 + '╗')
    print('║  🎬 Dubbing Mandarin → Jawa (TUI Mode)' + ' ' * 25 + '║')
    print('║  Workflow: MP4 + SRT Mandarin + Audio Jawa → MP4 Final' + ' ' * 4 + '║')
    print('╚' + '═' * 64 + '╝')
    print()


def find_files_in_cwd(pattern: str, extensions: list) -> list:
    """Cari file dengan extension tertentu di current working dir."""
    files = []
    cwd = os.getcwd()
    for ext in extensions:
        # Pattern glob: *.ext di cwd
        for f in glob.glob(os.path.join(cwd, f'*.{ext}')):
            files.append(os.path.basename(f))
    # Sort alphabetically
    files.sort()
    return files


def select_file(prompt: str, extensions: list, default: str = None) -> str:
    """Pilih file pakai questionary select (arrow keys)."""
    available = find_files_in_cwd('*', extensions)

    if not available:
        # Tidak ada file dengan extension itu di cwd, pakai manual input
        print(f'  ℹ Tidak ada file {" / ".join(extensions)} di folder ini.')
        path = questionary.text(
            f'{prompt} (ketik path lengkap):',
            default=default or '',
        ).ask()
        return path

    # Tambahkan opsi manual
    choices = available + ['[Ketik path manual]']
    selected = questionary.select(
        prompt,
        choices=choices,
        default=available[0] if available else choices[-1],
    ).ask()

    if selected == '[Ketik path manual]':
        return questionary.text(
            f'{prompt} (ketik path lengkap):',
            default=default or '',
        ).ask()

    return selected


def check_script_exists(script_name: str) -> bool:
    """Cek apakah script sibling ada."""
    script_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), script_name)
    if not os.path.isfile(script_path):
        # Coba di cwd
        script_path = os.path.join(os.getcwd(), script_name)
    return os.path.isfile(script_path)


def run_retime_video(args: list, script_name: str = 'retime-video.py') -> int:
    """Panggil retime-video.py dengan args, return exit code."""
    # Cari script di sibling dir atau cwd
    script_dir = os.path.dirname(os.path.abspath(__file__))
    script_path = os.path.join(script_dir, script_name)
    if not os.path.isfile(script_path):
        script_path = os.path.join(os.getcwd(), script_name)

    if not os.path.isfile(script_path):
        print(f'\n❌ Script {script_name} tidak ditemukan.')
        print(f'   Cari di: {script_path}')
        return 1

    cmd = [sys.executable, script_path] + args
    print('\n' + '─' * 64)
    print('Menjalankan:')
    print(' '.join(cmd))
    print('─' * 64 + '\n')

    try:
        result = subprocess.run(cmd)
        return result.returncode
    except KeyboardInterrupt:
        print('\n\n⏹ Dibatalkan user.')
        return 130


# ============================================================
# Main TUI flow
# ============================================================

def main():
    print_banner()

    # Cek retime-video.py ada
    if not check_script_exists('retime-video.py'):
        print('❌ Script "retime-video.py" tidak ditemukan di folder ini.')
        print()
        print('Letakkan dubbing-tui.py dan retime-video.py di folder yang sama.')
        print('Download dari: https://github.com/emailnyamahmud-afk/srt-splitter/tree/main/scripts')
        print()
        sys.exit(1)

    print('📋 Step-by-step, ikuti petunjuk di layar.')
    print('   Navigasi: ↑↓ arrow keys, Enter konfirmasi, q batal')
    print()

    # Step 1: MP4 Mandarin
    print('▶ Step 1/8: Pilih file MP4 Mandarin asli')
    mp4 = select_file('MP4 Mandarin:', ['mp4', 'MP4'])
    if not mp4:
        print('Batal.')
        sys.exit(0)
    print(f'  ✓ {mp4}')
    print()

    # Step 2: SRT Mandarin
    print('▶ Step 2/8: Pilih file SRT Mandarin asli')
    srt_mandarin = select_file('SRT Mandarin:', ['srt', 'SRT'])
    if not srt_mandarin:
        print('Batal.')
        sys.exit(0)
    print(f'  ✓ {srt_mandarin}')
    print()

    # Step 3: SRT Jawa (dari DUB web)
    print('▶ Step 3/8: Pilih file SRT Jawa baru (dari DUB web)')
    srt_jawa = select_file(
        'SRT Jawa (biasanya berakhiran -subs-jawa-new.srt):',
        ['srt', 'SRT'],
    )
    if not srt_jawa:
        print('Batal.')
        sys.exit(0)
    print(f'  ✓ {srt_jawa}')
    print()

    # Step 4: Audio Jawa WAV
    print('▶ Step 4/8: Pilih file audio Jawa WAV (dari DUB web)')
    audio_jawa = select_file(
        'Audio Jawa WAV (biasanya berakhiran -audio-jawa.wav):',
        ['wav', 'WAV'],
    )
    if not audio_jawa:
        print('Batal.')
        sys.exit(0)
    print(f'  ✓ {audio_jawa}')
    print()

    # Step 5: Output MP4
    print('▶ Step 5/8: Pilih nama output MP4')
    output = questionary.text(
        'Nama file output MP4:',
        default='mp4-jawa.mp4',
    ).ask()
    if not output:
        print('Batal.')
        sys.exit(0)
    print(f'  ✓ {output}')
    print()

    # Step 6: Mode SFX
    print('▶ Step 6/8: Pilih mode SFX')
    sfx_mode = questionary.select(
        'Mode SFX:',
        choices=[
            'Mode A — Basic (audio ori di-duck, simpel) — REKOMENDASI',
            'Mode B — Separate SFX dengan Demucs (lebih bersih, butuh 10-20 menit)',
            'Mode C — Buang audio ori total (hanya audio Jawa)',
        ],
        default='Mode A — Basic (audio ori di-duck, simpel) — REKOMENDASI',
    ).ask()
    if not sfx_mode:
        print('Batal.')
        sys.exit(0)
    print(f'  ✓ {sfx_mode}')
    print()

    # Step 7: SFX ducking (kalau Mode A/B)
    ducking_db = 12  # default
    if 'Mode A' in sfx_mode or 'Mode B' in sfx_mode:
        print('▶ Step 7/8: Pilih SFX ducking level')
        ducking_choice = questionary.select(
            'SFX ducking (volume SFX turun saat audio Jawa bicara):',
            choices=[
                '-12 dB (default, seimbang) — REKOMENDASI',
                '-6 dB (SFX lebih keras)',
                '-18 dB (SFX pelan, audio Jawa dominan)',
                '-24 dB (hampir tidak ada SFX)',
                '0 dB (SFX dan audio Jawa sama keras)',
            ],
            default='-12 dB (default, seimbang) — REKOMENDASI',
        ).ask()
        if not ducking_choice:
            print('Batal.')
            sys.exit(0)
        # Parse angka dari string "-12 dB ..."
        ducking_db = int(ducking_choice.split(' dB')[0].lstrip('-'))
        print(f'  ✓ -{ducking_db} dB')
    else:
        print('▶ Step 7/8: Skip (Mode C, tidak ada SFX)')
    print()

    # Step 8: Action
    print('▶ Step 8/8: Pilih action')
    action = questionary.select(
        'Action:',
        choices=[
            '🔍 DRY-RUN (tes command tanpa proses — REKOMENDASI PERTAMA KALI)',
            '▶️  RUN (proses beneran, butuh 2-30 menit)',
            '❌ Batal',
        ],
        default='🔍 DRY-RUN (tes command tanpa proses — REKOMENDASI PERTAMA KALI)',
    ).ask()

    if not action or 'Batal' in action:
        print('Batal.')
        sys.exit(0)
    print(f'  ✓ {action}')
    print()

    # Build args
    args = [
        '--mp4', mp4,
        '--srt-mandarin', srt_mandarin,
        '--srt-jawa', srt_jawa,
        '--audio-jawa', audio_jawa,
        '--output', output,
    ]
    if 'Mode B' in sfx_mode:
        args.append('--separate-sfx')
        args.extend(['--sfx-ducking', str(ducking_db)])
    elif 'Mode C' in sfx_mode:
        args.append('--no-sfx')
    elif 'Mode A' in sfx_mode:
        args.extend(['--sfx-ducking', str(ducking_db)])

    is_dry_run = 'DRY-RUN' in action
    if is_dry_run:
        args.append('--dry-run')

    # Ringkasan
    print('╔' + '═' * 64 + '╗')
    print('║  📋 Ringkasan:' + ' ' * 49 + '║')
    print('╠' + '═' * 64 + '╣')
    print(f'║  MP4      : {mp4:<46}║')
    print(f'║  SRT M    : {srt_mandarin:<46}║')
    print(f'║  SRT J    : {srt_jawa:<46}║')
    print(f'║  Audio J  : {audio_jawa:<46}║')
    print(f'║  Output   : {output:<46}║')
    print(f'║  Mode     : {sfx_mode[:46]:<46}║')
    if 'Mode C' not in sfx_mode:
        print(f'║  Ducking  : -{ducking_db} dB' + ' ' * (46 - len(f'-{ducking_db} dB')) + '║')
    print(f'║  Action   : {"DRY-RUN" if is_dry_run else "RUN":<46}║')
    print('╚' + '═' * 64 + '╝')
    print()

    # Tampilkan command
    print('=== Command yang akan dijalankan ===')
    cmd_display = f'python3 retime-video.py \\\n'
    for arg in args:
        if arg.startswith('--'):
            cmd_display += f'  {arg} \\\n'
        else:
            cmd_display += f'  {arg} \\\n'
    cmd_display = cmd_display.rstrip('\\\n')
    print(cmd_display)
    print('=== End command ===')
    print()

    # Konfirmasi
    confirm = questionary.confirm(
        'Lanjut eksekusi?',
        default=True,
    ).ask()
    if not confirm:
        print('Batal.')
        sys.exit(0)

    # Eksekusi
    print('\n' + '═' * 64)
    print('🚀 Mulai eksekusi...')
    print('═' * 64 + '\n')

    exit_code = run_retime_video(args)

    print()
    if exit_code == 0:
        print('═' * 64)
        print('✅ SELESAI!')
        if is_dry_run:
            print()
            print('Dry-run sukses. Command valid dan siap dijalankan.')
            print()
            print('Untuk RUN beneran, jalankan ulang TUI ini dan pilih RUN.')
            print('Atau langsung dari terminal:')
            print()
            print(' '.join(['python3', 'retime-video.py'] + [a for a in args if a != '--dry-run']))
        else:
            print()
            output_path = os.path.join(os.getcwd(), output)
            if os.path.isfile(output_path):
                size_mb = os.path.getsize(output_path) / 1024 / 1024
                print(f'📁 File output: {output_path}')
                print(f'   Size: {size_mb:.1f} MB')
                print()
                print('Buka dengan:')
                print(f'  open "{output_path}"')
            print()
            print('Lanjut ke Fase 5: edit di DaVinci Resolve (opsional).')
        print('═' * 64)
    else:
        print('═' * 64)
        print(f'❌ GAGAL dengan exit code {exit_code}')
        print()
        print('Cek error message di atas. Umumnya:')
        print('  - File tidak ditemukan → cek path')
        print('  - FFmpeg error → cek apakah ffmpeg terinstall: ffmpeg -version')
        print('  - Demucs gagal → cek apakah demucs terinstall: demucs --help')
        print('═' * 64)

    sys.exit(exit_code)


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print('\n\n⏹ Dibatalkan user.')
        sys.exit(130)
