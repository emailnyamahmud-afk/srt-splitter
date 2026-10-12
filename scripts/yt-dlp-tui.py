#!/usr/bin/env python3
"""
yt-dlp-tui.py v5 — TUI download YouTube: video + audio + SRT

Pilihan resolusi: 480p, 720p, 1080p, best
Output: 2 file = MP4 (video only) + M4A (audio only, native YouTube)
SRT: list subtitle dari JSON metadata, user pilih Indonesia / lain / skip

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
    """Ambil daftar subtitle dari YouTube via --dump-json. Return [(code, name), ...]."""
    print('\n▶ Cek subtitle tersedia...')
    cmd = [ytdlp, '--dump-json', '--no-playlist', '--skip-download', url]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if result.returncode != 0 or not result.stdout.strip():
            return []
        data = json.loads(result.stdout.splitlines()[0])
    except Exception:
        return []

    # Hitung bahasa unik dari subtitles + automatic_captions
    seen = {}
    for key in ('subtitles', 'automatic_captions'):
        for lang_code, tracks in data.get(key, {}).items():
            if lang_code and lang_code not in seen:
                # Ambil nama bahasa dari track pertama jika ada, fallback ke code
                name = lang_code
                if tracks and isinstance(tracks, list):
                    ext = tracks[0].get('ext', '') if isinstance(tracks[0], dict) else ''
                    # Coba ambil name dari data track (kalau ada 'name' field)
                    track_name = tracks[0].get('name', '') if isinstance(tracks[0], dict) else ''
                    name = track_name or lang_code
                seen[lang_code] = name
    return list(seen.items())


def main():
    os.system('clear' if os.name != 'nt' else 'cls')
    print('╔' + '═' * 64 + '╗')
    print('║  📺 YouTube Downloader v5 (TUI)' + ' ' * 31 + '║')
    print('║  Resolusi + MP4 + M4A terpisah + SRT Indonesia' + ' ' * 14 + '║')
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
    subs = list_subtitles(ytdlp, url)

    srt_choice = 'Skip (download SRT dari eksternal)'
    if subs:
        # Cari Indonesia (kode: id, in, ind)
        id_subs = [s for s in subs if s[0].lower() in ('id', 'in', 'ind')]
        sub_choices = []
        if id_subs:
            sub_choices.append(f'Download SRT Indonesia ({id_subs[0][0]})')
        sub_choices.append('Skip (download SRT dari eksternal)')
        sub_choices.append('Pilih subtitle lain:')
        # Default: Indonesia kalau ada, kalau tidak skip
        default_idx = 0 if id_subs else 1
        srt_choice = questionary.select(
            f'Subtitle tersedia ({len(subs)} bahasa):',
            choices=sub_choices,
            default=sub_choices[default_idx]
        ).ask()

        if 'Pilih subtitle lain' in srt_choice:
            all_sub_choices = [f'{code} — {name}' for code, name in sorted(subs)]
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
    print('║  Output  : MP4 (video) + M4A (audio) terpisah' + ' ' * 8 + '║')
    print(f'║  SRT     : {srt_choice[:48]:<48}║')
    print(f'║  URL     : {url[:48]:<48}║')
    print(f'║  Dir     : {output_dir[:48]:<48}║')
    print('╚' + '═' * 64 + '╝')

    if not questionary.confirm('\nLanjut download?', default=True).ask():
        sys.exit(0)

    print('\n' + '═' * 64)
    print('🚀 Download...')
    print('═' * 64 + '\n')

    # Download video (MP4, tanpa audio)
    print('▶ Download video (MP4, tanpa audio)...')
    cmd_video = [ytdlp, '-f', video_fmt, '-o', video_template,
                 '--no-playlist', '--newline', url]
    try:
        subprocess.run(cmd_video)
    except KeyboardInterrupt:
        print('\n⏹ Dibatalkan.')
        sys.exit(130)

    # Download audio (M4A native, tanpa konversi)
    # YouTube sudah punya m4a (AAC) — skip konversi MP3 (hemat waktu + disk + quality)
    # Demucs, ffmpeg, whisper, dll semua bisa baca m4a langsung
    print('\n▶ Download audio (M4A native)...')
    cmd_audio = [ytdlp, '-f', 'bestaudio[ext=m4a]/bestaudio/best',
                 '-o', audio_template,
                 '--no-playlist', '--newline', url]
    try:
        subprocess.run(cmd_audio)
    except KeyboardInterrupt:
        print('\n⏹ Dibatalkan.')
        sys.exit(130)

    # Download SRT kalau dipilih
    if 'Skip' not in srt_choice and 'eksternal' not in srt_choice.lower():
        srt_lang = None
        if 'Indonesia' in srt_choice:
            srt_lang = 'id'
        elif 'Download SRT' in srt_choice:
            srt_lang = srt_choice.replace('Download SRT ', '').strip()

        if srt_lang:
            print(f'\n▶ Download SRT ({srt_lang})...')
            srt_template = os.path.join(output_dir, f'{base_name}.%(ext)s')
            cmd_srt = [ytdlp, '--write-sub', '--sub-lang', srt_lang,
                       '--sub-format', 'srt', '--convert-subs', 'srt',
                       '--skip-download',
                       '-o', srt_template,
                       '--no-playlist', url]
            try:
                subprocess.run(cmd_srt)
            except KeyboardInterrupt:
                print('\n⏹ Dibatalkan SRT.')
            except Exception as e:
                print(f'\n⚠ Gagal download SRT: {e}')
                print('   Download SRT dari eksternal (mis. subscene.com, opensubtitles.org)')

    # Hasil — pakai base_name spesifik (bukan "file terbaru"), supaya tidak salah tampil
    print('\n' + '═' * 64)
    print('✅ SELESAI!\n')

    # Cari file berdasarkan base_name yang dipakai. Kalau custom_name None, kita tidak
    # tahu judul asli — fallback ke "file terbaru" tapi filter ekstensi.
    found_video = found_audio = found_srt = None
    if custom_name:
        # Filter exact match by base_name
        v_match = list(Path(output_dir).glob(f'{custom_name}.mp4'))
        a_match = list(Path(output_dir).glob(f'{custom_name}-audio.m4a')) + \
                  list(Path(output_dir).glob(f'{custom_name}-audio.mp4')) + \
                  list(Path(output_dir).glob(f'{custom_name}-audio.webm'))
        s_match = list(Path(output_dir).glob(f'{custom_name}*.srt'))
        if v_match: found_video = max(v_match, key=os.path.getmtime)
        if a_match: found_audio = max(a_match, key=os.path.getmtime)
        if s_match: found_srt = max(s_match, key=os.path.getmtime)
    else:
        # Fallback: file terbaru per ekstensi
        mp4 = sorted(Path(output_dir).glob('*.mp4'), key=os.path.getmtime, reverse=True)
        aud = sorted(list(Path(output_dir).glob('*.m4a')) + list(Path(output_dir).glob('*.mp3')),
                     key=os.path.getmtime, reverse=True)
        srt = sorted(Path(output_dir).glob('*.srt'), key=os.path.getmtime, reverse=True)
        if mp4: found_video = mp4[0]
        if aud: found_audio = aud[0]
        if srt: found_srt = srt[0]

    if found_video:
        size_mb = found_video.stat().st_size / 1024 / 1024
        print(f'📁 Video: {found_video.name} ({size_mb:.1f} MB)')
    else:
        print('⚠ Video tidak ditemukan. Cek log yt-dlp di atas.')

    if found_audio:
        size_mb = found_audio.stat().st_size / 1024 / 1024
        print(f'📁 Audio: {found_audio.name} ({size_mb:.1f} MB)')
    else:
        print('⚠ Audio tidak ditemukan. Cek log yt-dlp di atas.')

    if found_srt:
        print(f'📁 SRT:   {found_srt.name}')
    else:
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
