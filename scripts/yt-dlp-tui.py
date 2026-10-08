#!/usr/bin/env python3
"""
yt-dlp-tui.py v2 — TUI download YouTube dengan pilihan resolusi

Pilihan resolusi: 480p, 720p, 1080p, best
Output: 2 file = MP4 (video+audio merged) + audio ori (m4a)

Install: pip3 install yt-dlp
Usage: python3 yt-dlp-tui.py
"""

import os
import sys
import subprocess
import re
from pathlib import Path

try:
    import questionary
except ImportError:
    print('\n❌ pip3 install questionary')
    sys.exit(1)


def clear_screen():
    os.system('clear' if os.name != 'nt' else 'cls')


def check_ytdlp():
    import shutil
    path = shutil.which('yt-dlp') or shutil.which('yt-dlp.exe')
    if path:
        return path
    venv_path = os.path.join(os.path.dirname(sys.executable), 'yt-dlp')
    if os.path.isfile(venv_path) and os.access(venv_path, os.X_OK):
        return venv_path
    return None


def sanitize_filename(name):
    name = re.sub(r'[\\/:*?"<>|]', '', name).strip()
    return name[:200] if len(name) > 200 else (name or 'video')


def main():
    clear_screen()
    print('╔' + '═' * 64 + '╗')
    print('║  📺 YouTube Downloader v2 (TUI)' + ' ' * 30 + '║')
    print('║  Pilihan resolusi + output MP4 + audio terpisah' + ' ' * 12 + '║')
    print('╚' + '═' * 64 + '╝')
    print()

    ytdlp = check_ytdlp()
    if not ytdlp:
        print('❌ yt-dlp belum terinstall. Install: pip3 install yt-dlp')
        sys.exit(1)

    print(f'yt-dlp: {ytdlp}\n')

    # Step 1: Resolusi
    print('▶ Step 1/5: Pilih resolusi')
    res = questionary.select(
        'Resolusi:',
        choices=[
            '480p (file kecil, cepat download, cukup untuk dubbing)',
            '720p (sedang, rekomendasi)',
            '1080p (besar, kualitas terbaik)',
            'Best quality (auto, bisa AV1/VP9)',
            'Audio only (m4a 128kbps)',
        ],
        default='720p (sedang, rekomendasi)',
    ).ask()

    # Step 2: URL
    print(f'\n  ✓ {res}\n')
    print('▶ Step 2/5: Masukkan URL YouTube')
    url = questionary.text('URL YouTube:').ask()
    if not url or not url.strip():
        sys.exit(0)
    url = url.strip()
    print(f'  ✓ {url}\n')

    # Step 3: Output dir
    print('▶ Step 3/5: Output directory')
    output_dir = questionary.text('Output dir:', default=os.path.expanduser('~/Dubbing')).ask()
    if not output_dir:
        output_dir = os.path.expanduser('~/Dubbing')
    output_dir = os.path.expanduser(output_dir)
    os.makedirs(output_dir, exist_ok=True)
    print(f'  ✓ {output_dir}\n')

    # Step 4: Nama file
    print('▶ Step 4/5: Nama file (opsional)')
    custom_name = questionary.text('Nama custom (kosong = judul YouTube):', default='').ask()
    if custom_name and custom_name.strip():
        custom_name = sanitize_filename(custom_name.strip())
    else:
        custom_name = None
    print(f'  ✓ {custom_name or "(judul YouTube)"}\n')

    # Step 5: Output mode — MP4 merged saja, atau MP4 + audio terpisah
    print('▶ Step 5/5: Output mode')
    if 'Audio only' not in res:
        output_mode = questionary.select(
            'Output:',
            choices=[
                'MP4 + audio terpisah (2 file: mp4 ori + m4a ori)',
                'MP4 saja (merged, 1 file)',
            ],
            default='MP4 + audio terpisah (2 file: mp4 ori + m4a ori)',
        ).ask()
    else:
        output_mode = 'Audio only'
    print(f'  ✓ {output_mode}\n')

    # Build format string
    if '480p' in res:
        format_str = 'bestvideo[height<=480]+bestaudio/best[height<=480]/best'
    elif '720p' in res:
        format_str = 'bestvideo[height<=720]+bestaudio/best[height<=720]/best'
    elif '1080p' in res:
        format_str = 'bestvideo[height<=1080]+bestaudio/best[height<=1080]/best'
    elif 'Audio only' in res:
        format_str = 'bestaudio/best'
    else:
        format_str = 'bestvideo+bestaudio/best'

    # Output template
    if custom_name:
        base_name = custom_name
    else:
        base_name = '%(title).200s'

    if 'terpisah' in output_mode:
        # Download video dan audio terpisah, lalu merge
        output_template = os.path.join(output_dir, f'{base_name}.%(ext)s')
    else:
        output_template = os.path.join(output_dir, f'{base_name}.%(ext)s')

    # Build command
    cmd = [
        ytdlp,
        '-f', format_str,
        '--merge-output-format', 'mp4',
        '-o', output_template,
        '--no-playlist',
        '--newline',
    ]

    # Konfirmasi
    print('╔' + '═' * 64 + '╗')
    print('║  📋 Ringkasan:' + ' ' * 49 + '║')
    print('╠' + '═' * 64 + '╣')
    print(f'║  Resolusi: {res[:48]:<48}║')
    print(f'║  Output  : {output_mode[:48]:<48}║')
    print(f'║  URL     : {url[:48]:<48}║')
    print(f'║  Dir     : {output_dir[:48]:<48}║')
    print('╚' + '═' * 64 + '╝')
    print()

    confirm = questionary.confirm('Lanjut download?', default=True).ask()
    if not confirm:
        sys.exit(0)

    # Eksekusi
    print('\n' + '═' * 64)
    print('🚀 Download...')
    print('═' * 64 + '\n')

    cmd.append(url)

    try:
        result = subprocess.run(cmd)
        exit_code = result.returncode
    except KeyboardInterrupt:
        print('\n⏹ Dibatalkan.')
        sys.exit(130)

    print()
    if exit_code == 0:
        print('═' * 64)
        print('✅ SELESAI!')
        print()
        # Cari file output
        mp4_files = sorted(Path(output_dir).glob('*.mp4'), key=os.path.getmtime, reverse=True)
        m4a_files = sorted(Path(output_dir).glob('*.m4a'), key=os.path.getmtime, reverse=True)

        if mp4_files:
            latest = mp4_files[0]
            size_mb = latest.stat().st_size / 1024 / 1024
            print(f'📁 MP4: {latest.name} ({size_mb:.1f} MB)')
        if m4a_files:
            latest_m4a = m4a_files[0]
            size_mb = latest_m4a.stat().st_size / 1024 / 1024
            print(f'📁 Audio: {latest_m4a.name} ({size_mb:.1f} MB)')

        print()
        print('🎬 Langkah berikutnya:')
        print('   1. Demucs: python3 demucs-tui.py')
        print('   2. Web app: Editor SRT Jawa → generate TTS')
        print('   3. Mix: python3 mix-tui.py')
        print('═' * 64)
    else:
        print(f'❌ GAGAL (exit {exit_code})')
        print('Cek error di atas. Umumnya: URL salah, format tidak ada, rate limit.')

    sys.exit(exit_code)


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print('\n⏹ Dibatalkan.')
        sys.exit(130)
    except Exception as e:
        print(f'\n❌ {e}', file=sys.stderr)
        sys.exit(1)
