#!/usr/bin/env python3
"""
yt-dlp-tui.py v3 — TUI download YouTube dengan pilihan resolusi + output terpisah

Pilihan resolusi: 480p, 720p, 1080p, best
Output: 2 file = MP4 (video only) + m4a (audio only)
        atau 1 file = MP4 (merged video+audio)

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
    os.system('clear' if os.name != 'nt' else 'cls')
    print('╔' + '═' * 64 + '╗')
    print('║  📺 YouTube Downloader v3 (TUI)' + ' ' * 30 + '║')
    print('║  Pilihan resolusi + output MP4 + audio terpisah' + ' ' * 12 + '║')
    print('╚' + '═' * 64 + '╝')
    print()

    ytdlp = check_ytdlp()
    if not ytdlp:
        print('❌ yt-dlp belum terinstall. Install: pip3 install yt-dlp')
        sys.exit(1)

    print(f'yt-dlp: {ytdlp}\n')

    # Step 1: Resolusi
    res = questionary.select('Pilih resolusi:', choices=[
        '480p (file kecil, cepat download, cukup untuk dubbing)',
        '720p (sedang, rekomendasi)',
        '1080p (besar, kualitas terbaik)',
        'Best quality (auto, bisa AV1/VP9)',
        'Audio only (m4a 128kbps)',
    ], default='720p (sedang, rekomendasi)').ask()

    # Step 2: URL
    url = questionary.text('URL YouTube:').ask()
    if not url or not url.strip():
        sys.exit(0)
    url = url.strip()

    # Step 3: Output dir
    output_dir = questionary.text('Output dir:', default=os.path.expanduser('~/Dubbing')).ask()
    if not output_dir:
        output_dir = os.path.expanduser('~/Dubbing')
    output_dir = os.path.expanduser(output_dir)
    os.makedirs(output_dir, exist_ok=True)

    # Step 4: Nama file
    custom_name = questionary.text('Nama custom (kosong = judul YouTube):', default='').ask()
    if custom_name and custom_name.strip():
        custom_name = sanitize_filename(custom_name.strip())
    else:
        custom_name = None

    # Step 5: Output mode
    if 'Audio only' not in res:
        output_mode = questionary.select('Output:', choices=[
            'MP4 + audio terpisah (2 file: mp4 ori + m4a ori)',
            'MP4 saja (merged, 1 file)',
        ], default='MP4 + audio terpisah (2 file: mp4 ori + m4a ori)').ask()
    else:
        output_mode = 'Audio only'

    # Build format strings
    if '480p' in res:
        video_fmt = 'bestvideo[height<=480]/best[height<=480]'
    elif '720p' in res:
        video_fmt = 'bestvideo[height<=720]/best[height<=720]'
    elif '1080p' in res:
        video_fmt = 'bestvideo[height<=1080]/best[height<=1080]'
    else:
        video_fmt = 'bestvideo/best'
    audio_fmt = 'bestaudio/best'

    base_name = custom_name if custom_name else '%(title).200s'
    video_template = os.path.join(output_dir, f'{base_name}.%(ext)s')
    audio_template = os.path.join(output_dir, f'{base_name}-audio.%(ext)s')

    # Konfirmasi
    print('\n╔' + '═' * 64 + '╗')
    print('║  📋 Ringkasan:' + ' ' * 49 + '║')
    print('╠' + '═' * 64 + '╣')
    print(f'║  Resolusi: {res[:48]:<48}║')
    print(f'║  Output  : {output_mode[:48]:<48}║')
    print(f'║  URL     : {url[:48]:<48}║')
    print(f'║  Dir     : {output_dir[:48]:<48}║')
    print('╚' + '═' * 64 + '╝')

    if not questionary.confirm('\nLanjut download?', default=True).ask():
        sys.exit(0)

    print('\n' + '═' * 64)
    print('🚀 Download...')
    print('═' * 64 + '\n')

    if 'terpisah' in output_mode:
        # MODE TERPISAH: 2 command terpisah — JANGAN merge!
        # Command 1: video only (tanpa audio)
        print('▶ Download video (tanpa audio)...')
        cmd_video = [ytdlp, '-f', video_fmt, '-o', video_template,
                     '--no-playlist', '--newline', '--no-merge-output-format', url]
        try:
            subprocess.run(cmd_video)
        except KeyboardInterrupt:
            print('\n⏹ Dibatalkan.')
            sys.exit(130)

        # Command 2: audio only
        print('\n▶ Download audio (m4a)...')
        cmd_audio = [ytdlp, '-f', audio_fmt, '-o', audio_template,
                     '--no-playlist', '--newline', '--no-merge-output-format',
                     '--extract-audio', url]
        try:
            subprocess.run(cmd_audio)
        except KeyboardInterrupt:
            print('\n⏹ Dibatalkan.')
            sys.exit(130)

    elif 'Audio only' in res:
        # Audio only
        cmd = [ytdlp, '-f', audio_fmt, '-o', audio_template,
               '--no-playlist', '--newline', '--extract-audio', url]
        try:
            subprocess.run(cmd)
        except KeyboardInterrupt:
            print('\n⏹ Dibatalkan.')
            sys.exit(130)

    else:
        # MODE MERGED: 1 command, merge video+audio jadi 1 MP4
        cmd = [ytdlp, '-f', f'{video_fmt}+{audio_fmt}', '-o', video_template,
               '--no-playlist', '--newline', '--merge-output-format', 'mp4', url]
        try:
            subprocess.run(cmd)
        except KeyboardInterrupt:
            print('\n⏹ Dibatalkan.')
            sys.exit(130)

    # Hasil
    print('\n' + '═' * 64)
    print('✅ SELESAI!\n')
    mp4_files = sorted(Path(output_dir).glob('*.mp4'), key=os.path.getmtime, reverse=True)
    m4a_files = sorted(Path(output_dir).glob('*.m4a'), key=os.path.getmtime, reverse=True)
    webm_files = sorted(Path(output_dir).glob('*.webm'), key=os.path.getmtime, reverse=True)

    if mp4_files:
        size_mb = mp4_files[0].stat().st_size / 1024 / 1024
        print(f'📁 Video: {mp4_files[0].name} ({size_mb:.1f} MB)')
    if m4a_files:
        size_mb = m4a_files[0].stat().st_size / 1024 / 1024
        print(f'📁 Audio: {m4a_files[0].name} ({size_mb:.1f} MB)')
    if webm_files:
        size_mb = webm_files[0].stat().st_size / 1024 / 1024
        print(f'📁 Audio: {webm_files[0].name} ({size_mb:.1f} MB)')

    print('\n🎬 Langkah berikutnya:')
    print('   1. Demucs: python3 demucs-tui.py')
    print('   2. Web app: Editor SRT Jawa → generate TTS')
    print('   3. Mix: python3 mix-tui.py')
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
