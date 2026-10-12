#!/usr/bin/env python3
"""
yt-dlp-tui.py v4 — TUI download YouTube dengan pilihan resolusi + output terpisah + SRT

Pilihan resolusi: 480p, 720p, 1080p, best
Output: 2 file = MP4 (video only) + MP3 (audio only, 128kbps)
SRT: list subtitle tersedia, user pilih SRT Indonesia (atau skip kalau tidak ada)

Install: pip3 install yt-dlp questionary
Usage: python3 yt-dlp-tui.py
"""

import os
import sys
import subprocess
import re
import json
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


def list_subtitles(ytdlp, url):
    """List subtitle tersedia di YouTube. Return list of (lang_code, lang_name)."""
    print('\n▶ Cek subtitle tersedia...')
    cmd = [ytdlp, '--list-subs', '--print', '%(subtitles)s', url]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        # Parse output — cari baris dengan format "lang_code  lang_name  ext"
        subs = []
        for line in result.stdout.split('\n'):
            line = line.strip()
            if not line or line.startswith('Language') or line.startswith('['):
                continue
            # Format: "id  Indonesian  vtt, ttml" atau "id  Indonesian  vtt"
            parts = line.split()
            if len(parts) >= 2:
                lang_code = parts[0]
                lang_name = parts[1]
                # Skip auto-generated marker
                if lang_code and lang_name:
                    subs.append((lang_code, lang_name))
        return subs
    except Exception:
        return []


def main():
    os.system('clear' if os.name != 'nt' else 'cls')
    print('╔' + '═' * 64 + '╗')
    print('║  📺 YouTube Downloader v4 (TUI)' + ' ' * 30 + '║')
    print('║  Resolusi + MP4 + MP3 terpisah + SRT Indonesia' + ' ' * 13 + '║')
    print('╚' + '═' * 64 + '╝')
    print()

    ytdlp = check_ytdlp()
    if not ytdlp:
        print('❌ yt-dlp belum terinstall. Install: pip3 install yt-dlp')
        sys.exit(1)

    print(f'yt-dlp: {ytdlp}\n')

    # Step 1: URL
    url = questionary.text('URL YouTube:').ask()
    if not url or not url.strip():
        sys.exit(0)
    url = url.strip()

    # Step 2: Resolusi
    res = questionary.select('Pilih resolusi:', choices=[
        '480p (file kecil, cepat, aman untuk Demucs)',
        '720p (sedang, rekomendasi)',
        '1080p (besar, kualitas terbaik)',
        'Best quality (auto, bisa AV1/VP9)',
    ], default='480p (file kecil, cepat, aman untuk Demucs)').ask()

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

    # Step 5: SRT Indonesia
    print('\n▶ Cek subtitle tersedia di YouTube...')
    subs = list_subtitles(ytdlp, url)

    srt_choice = 'Skip (download SRT dari eksternal)'
    if subs:
        # Cari Indonesia
        id_subs = [s for s in subs if s[0].lower() in ('id', 'in', 'ind')]
        sub_choices = []
        if id_subs:
            sub_choices.append(f'Download SRT Indonesia ({id_subs[0][0]})')
        sub_choices.append('Skip (download SRT dari eksternal)')
        sub_choices.append('Pilih subtitle lain:')
        srt_choice = questionary.select(
            f'Subtitle tersedia ({len(subs)} bahasa):',
            choices=sub_choices,
            default=sub_choices[0] if id_subs else sub_choices[0]
        ).ask()

        if 'Pilih subtitle lain' in srt_choice:
            # List semua subtitle
            all_sub_choices = [f'{code} — {name}' for code, name in subs]
            all_sub_choices.append('Skip')
            sel = questionary.select('Pilih subtitle:', choices=all_sub_choices).ask()
            if sel and 'Skip' not in sel:
                srt_choice = f'Download SRT {sel.split(" — ")[0]}'
            else:
                srt_choice = 'Skip'
    else:
        print('  ⚠ Tidak ada subtitle di YouTube. Download SRT dari eksternal.')
        srt_choice = 'Skip (download SRT dari eksternal)'

    # Build format strings
    if '480p' in res:
        video_fmt = 'bestvideo[height<=480]/best[height<=480]'
    elif '720p' in res:
        video_fmt = 'bestvideo[height<=720]/best[height<=720]'
    elif '1080p' in res:
        video_fmt = 'bestvideo[height<=1080]/best[height<=1080]'
    else:
        video_fmt = 'bestvideo/best'

    base_name = custom_name if custom_name else '%(title).200s'
    video_template = os.path.join(output_dir, f'{base_name}.%(ext)s')
    audio_template = os.path.join(output_dir, f'{base_name}-audio.%(ext)s')

    # Konfirmasi
    print('\n╔' + '═' * 64 + '╗')
    print('║  📋 Ringkasan:' + ' ' * 49 + '║')
    print('╠' + '═' * 64 + '╣')
    print(f'║  Resolusi: {res[:48]:<48}║')
    print(f'║  Output  : MP4 (video) + MP3 (audio) terpisah' + ' ' * 9 + '║')
    print(f'║  SRT     : {srt_choice[:48]:<48}║')
    print(f'║  URL     : {url[:48]:<48}║')
    print(f'║  Dir     : {output_dir[:48]:<48}║')
    print('╚' + '═' * 64 + '╝')

    if not questionary.confirm('\nLanjut download?', default=True).ask():
        sys.exit(0)

    print('\n' + '═' * 64)
    print('🚀 Download...')
    print('═' * 64 + '\n')

    # Download video (tanpa audio)
    print('▶ Download video (MP4, tanpa audio)...')
    cmd_video = [ytdlp, '-f', video_fmt, '-o', video_template,
                 '--no-playlist', '--newline', url]
    try:
        subprocess.run(cmd_video)
    except KeyboardInterrupt:
        print('\n⏹ Dibatalkan.')
        sys.exit(130)

    # Download audio (MP3, 128kbps)
    print('\n▶ Download audio (MP3 128kbps)...')
    # YouTube tidak punya MP3 langsung. Source: m4a (AAC, ~60MB) atau webm (Opus, ~122MB)
    # Prefer m4a (lebih kecil, download cepat), convert ke MP3 128kbps
    cmd_audio = [ytdlp, '-f', 'bestaudio[ext=m4a]/bestaudio/best', '-o', audio_template,
                 '--no-playlist', '--newline',
                 '--extract-audio', '--audio-format', 'mp3', '--audio-quality', '128K',
                 url]
    try:
        subprocess.run(cmd_audio)
    except KeyboardInterrupt:
        print('\n⏹ Dibatalkan.')
        sys.exit(130)

    # Download SRT kalau dipilih
    if 'Skip' not in srt_choice and 'eksternal' not in srt_choice.lower():
        # Extract lang code
        srt_lang = None
        if 'Indonesia' in srt_choice:
            srt_lang = 'id'
        elif 'Download SRT' in srt_choice:
            srt_lang = srt_choice.replace('Download SRT ', '').strip()

        if srt_lang:
            print(f'\n▶ Download SRT ({srt_lang})...')
            srt_template = os.path.join(output_dir, f'{base_name}.%(ext)s')
            cmd_srt = [ytdlp, '--write-sub', '--sub-lang', srt_lang,
                       '--sub-format', 'srt', '--skip-download',
                       '-o', srt_template,
                       '--no-playlist', url]
            try:
                subprocess.run(cmd_srt)
            except KeyboardInterrupt:
                print('\n⏹ Dibatalkan SRT.')
            except Exception as e:
                print(f'\n⚠ Gagal download SRT: {e}')
                print('   Download SRT dari eksternal (mis. subscene.com, opensubtitles.org)')

    # Hasil
    print('\n' + '═' * 64)
    print('✅ SELESAI!\n')
    mp4_files = sorted(Path(output_dir).glob('*.mp4'), key=os.path.getmtime, reverse=True)
    mp3_files = sorted(Path(output_dir).glob('*.mp3'), key=os.path.getmtime, reverse=True)
    srt_files = sorted(Path(output_dir).glob('*.srt'), key=os.path.getmtime, reverse=True)

    if mp4_files:
        size_mb = mp4_files[0].stat().st_size / 1024 / 1024
        print(f'📁 Video: {mp4_files[0].name} ({size_mb:.1f} MB)')
    if mp3_files:
        size_mb = mp3_files[0].stat().st_size / 1024 / 1024
        print(f'📁 Audio: {mp3_files[0].name} ({size_mb:.1f} MB)')
    if srt_files:
        print(f'📁 SRT:   {srt_files[0].name}')

    if not srt_files:
        print('\n⚠ SRT belum ada. Download dari eksternal:')
        print('   - https://subscene.com')
        print('   - https://www.opensubtitles.org')
        print('   - https://goblinsub.com')

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
