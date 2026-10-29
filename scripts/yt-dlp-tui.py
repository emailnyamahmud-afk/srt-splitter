#!/usr/bin/env python3
"""
yt-dlp-tui.py v6.3 — TUI download YouTube/Facebook/TikTok/IG: video + audio + SRT

Perubahan v6.3 (29 Okt 2026):
  Default resolusi: 480p → 1080p preferred (untuk konsistensi pipeline mix-tui v3.9).
  - User feedback: "daripada ribet, paksa jadi 1080p di fase mix tui saja. Lebih mudah render di fase mix daripada repot yt-dlp dan repot merge. Jika dari mix sudah 1080p, maka merge cuma pake stream copy = 2-5 menit selesai."
  - v6.3: default "1080p preferred (download 1080p kalau ada, fallback best) — REKOMENDASI"
  - "1080p preferred" = bestvideo[height<=1080]/best (download 1080p kalau ada, fallback ke 720p/480p best available)
  - Tetap ada pilihan: 1080p strict, 720p, 480p, Best quality
  - "1080p strict" = bestvideo[height<=1080]/best[height<=1080] (hanya ≤1080p, no fallback ke best)
  - Untuk Demucs preview (file kecil): pilih 480p manual

Perubahan v6.2 (26 Okt 2026):
  FIX: YouTube sekarang sering kena "Sign in to confirm you're not a bot" (HTTP 429).
       V6 lama skip cookies untuk YouTube → rusak. V6.2 SELALU pakai cookies untuk
       SEMUA platform (YT, FB, IG, TikTok). Default Brave (user pakai Brave).
       Auto-detect browser yang tersedia, fallback ke Skip kalau ga ada.

v6 update: Output audio = MP3 (sebelumnya M4A native).
  - Pakai yt-dlp `-x --audio-format mp3` → download audio terbaik → convert MP3
  - Butuh ffmpeg terinstall (sudah di repo: `brew install ffmpeg`)
  - Quality: VBR best (~190 kbps), sedikit lebih rendah dari M4A tapi cukup untuk dubbing
  - Kompatibel dengan lebih banyak tool + ringkas

Pilihan resolusi v6.3: 1080p preferred (default), 1080p strict, 720p, 480p, Best quality
Output: 2 file = MP4 (video only) + MP3 (audio only, via yt-dlp convert)
SRT: list subtitle dari JSON metadata, user pilih Indonesia / lain / skip

Install: pip3 install yt-dlp questionary
Usage: python3 yt-dlp-tui.py
"""

import os
import sys
import subprocess
import re
import json
import shutil
from pathlib import Path

try:
    import questionary
except ImportError:
    print('\n❌ pip3 install questionary')
    sys.exit(1)


VERSION = 'v6.3'

# Browser support matrix (urutan = prioritas)
# Brave dipertama karena user pakai Brave (FB confirmed working)
SUPPORTED_BROWSERS = [
    ('Brave',   'brave',   '~/Library/Application Support/BraveSoftware/Brave-Browser'),
    ('Chrome',  'chrome',  '~/Library/Application Support/Google/Chrome'),
    ('Firefox', 'firefox', '~/Library/Application Support/Firefox'),
    ('Safari',  'safari',  '~/Library/Safari'),
    ('Edge',    'edge',    '~/Library/Application Support/Microsoft Edge'),
]


def check_ytdlp():
    path = shutil.which('yt-dlp') or shutil.which('yt-dlp.exe')
    if path:
        return path
    venv_path = os.path.join(os.path.dirname(sys.executable), 'yt-dlp')
    if os.path.isfile(venv_path) and os.access(venv_path, os.X_OK):
        return venv_path
    return None


def detect_installed_browsers():
    """Return list of (display_name, browser_id) yang profile-nya terdeteksi di Mac.
    Yt-dlp baca cookies dari profile path ini.
    """
    installed = []
    for display, browser_id, profile_path in SUPPORTED_BROWSERS:
        p = os.path.expanduser(profile_path)
        if os.path.exists(p):
            installed.append((display, browser_id))
    return installed


def sanitize_filename(name):
    name = re.sub(r'[\\/:*?"<>|]', '', name).strip()
    return name[:200] if len(name) > 200 else (name or 'video')


def list_subtitles(ytdlp, url, cookie_args):
    """Ambil daftar subtitle dari YouTube via --dump-json. Return [(code, name), ...].
    Sekarang pass cookie_args supaya bisa ambil subs dari video yang butuh login.
    """
    print('\n▶ Cek subtitle tersedia...')
    cmd = [ytdlp, '--dump-json', '--no-playlist', '--skip-download'] + cookie_args + [url]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if result.returncode != 0 or not result.stdout.strip():
            return []
        data = json.loads(result.stdout.splitlines()[0])
    except Exception:
        return []

    seen = {}
    for key in ('subtitles', 'automatic_captions'):
        for lang_code, tracks in data.get(key, {}).items():
            if lang_code and lang_code not in seen:
                name = lang_code
                if tracks and isinstance(tracks, list):
                    track_name = tracks[0].get('name', '') if isinstance(tracks[0], dict) else ''
                    name = track_name or lang_code
                seen[lang_code] = name
    return list(seen.items())


def pick_cookies(url):
    """Prompt user untuk pilih cookies browser. Auto-detect yang terinstall.

    v6.2: SELALU prompt (untuk semua URL, termasuk YouTube).
    Default = browser pertama yang terdeteksi (Brave diprioritas).

    Return: list of args ['--cookies-from-browser', 'brave'] atau [] kalau Skip.
    """
    installed = detect_installed_browsers()
    is_yt = 'youtube.com' in url or 'youtu.be' in url

    if is_yt:
        print('\n  ℹ URL YouTube terdeteksi.')
        print('    YouTube sekarang sering kena "Sign in to confirm you\'re not a bot" (HTTP 429).')
        print('    FIX: login YouTube di browser dulu, lalu pakai cookies dari browser itu.\n')
    else:
        print('\n  ℹ URL non-YouTube — kemungkinan butuh login (cookies) untuk download.')
        print('    Pastikan sudah login ke platform tersebut di browser pilihan.\n')

    if not installed:
        print('  ⚠ Tidak ada browser terdeteksi di path Mac standar.')
        print('    Pilih Skip, atau ketik browser manual (brave/chrome/safari/firefox/edge).\n')
        choices = [
            'Skip (no cookies — YouTube mungkin gagal, FB/IG/TikTok pasti gagal)',
            'Ketik manual (mis. brave, chrome)',
        ]
    else:
        choices = []
        for display, browser_id in installed:
            # Default pilihan pertama (Brave diprioritas di SUPPORTED_BROWSERS)
            suffix = ' (default — login YT/FB/IG di sini dulu)' if browser_id == 'brave' else ''
            choices.append(f'{display}{suffix}')
        choices.append('Skip (no cookies — YouTube mungkin gagal, FB/IG/TikTok pasti gagal)')

    sel = questionary.select(
        'Pakai cookies dari browser?',
        choices=choices,
        default=choices[0],
    ).ask()

    if not sel or 'Skip' in sel:
        return []

    if 'Ketik manual' in sel:
        manual = questionary.text('Browser ID (brave/chrome/safari/firefox/edge):').ask()
        if manual and manual.strip():
            return ['--cookies-from-browser', manual.strip().lower()]
        return []

    # Match display name → browser_id
    for display, browser_id, _profile in SUPPORTED_BROWSERS:
        if sel.startswith(display):
            return ['--cookies-from-browser', browser_id]

    return []


def main():
    os.system('clear' if os.name != 'nt' else 'cls')
    print('╔' + '═' * 64 + '╗')
    print('║  📺 Downloader ' + VERSION + ' (TUI)' + ' ' * (44 - len(VERSION)) + '║')
    print('║  MP4 + MP3 + SRT • YouTube/FB/TikTok/IG (cookies)       ║')
    print('╚' + '═' * 64 + '╝')
    print()

    ytdlp = check_ytdlp()
    if not ytdlp:
        print('❌ yt-dlp belum terinstall. Install: pip3 install yt-dlp')
        sys.exit(1)

    print(f'yt-dlp: {ytdlp}\n')

    # Step 1: URL
    url = questionary.text('URL video (YouTube/Facebook/TikTok/dll):').ask()
    if not url or not url.strip():
        sys.exit(0)
    url = url.strip()

    # Step 1.5: Cookies — SELALU prompt (v6.2 fix)
    cookie_args = pick_cookies(url)
    if cookie_args:
        print(f'  → Cookies: {cookie_args[1]}')
    else:
        print('  → Cookies: Skip (rawak untuk YouTube sekarang)')
    print()

    # Step 2: Resolusi
    # v6.3: Default ganti dari 480p ke "1080p preferred" (untuk konsistensi pipeline mix-tui v3.9 force 1080p).
    #   - "1080p preferred" = bestvideo[height<=1080]/best → download 1080p kalau ada, fallback ke best available
    #   - "1080p strict" = bestvideo[height<=1080]/best[height<=1080] → hanya ≤1080p, no fallback
    #   - Untuk Demucs preview (file kecil): pilih 480p manual
    res = questionary.select('Pilih resolusi:', choices=[
        '1080p preferred (download 1080p kalau ada, fallback best) — REKOMENDASI',
        '1080p strict (hanya ≤1080p, no fallback)',
        '720p (sedang)',
        '480p (file kecil, cepat, untuk Demucs preview)',
        'Best quality (auto, bisa AV1/VP9)',
    ], default='1080p preferred (download 1080p kalau ada, fallback best) — REKOMENDASI').ask()

    # Step 3: Output dir (default: HDD)
    try:
        from config import INPUT_DIR, ensure_hdd
        default_dir = str(INPUT_DIR) if ensure_hdd() else os.path.expanduser('~/Dubbing')
    except ImportError:
        default_dir = os.path.expanduser('~/Dubbing')
    output_dir = questionary.text('Output dir:', default=default_dir).ask()
    if not output_dir:
        output_dir = default_dir
    output_dir = os.path.expanduser(output_dir)
    os.makedirs(output_dir, exist_ok=True)

    # Step 4: Nama file
    custom_name = questionary.text('Nama custom (kosong = judul asli):', default='').ask()
    if custom_name and custom_name.strip():
        custom_name = sanitize_filename(custom_name.strip())
    else:
        custom_name = None

    # Step 5: SRT Indonesia
    subs = list_subtitles(ytdlp, url, cookie_args)

    srt_choice = 'Skip (download SRT dari eksternal)'
    if subs:
        id_subs = [s for s in subs if s[0].lower() in ('id', 'in', 'ind')]
        sub_choices = []
        if id_subs:
            sub_choices.append(f'Download SRT Indonesia ({id_subs[0][0]})')
        sub_choices.append('Skip (download SRT dari eksternal)')
        sub_choices.append('Pilih subtitle lain:')
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
        print('  ⚠ Tidak ada subtitle tersedia. Download SRT dari eksternal.')
        srt_choice = 'Skip (download SRT dari eksternal)'

    # Build format strings
    # v6.3: tambah "1080p preferred" (fallback best) vs "1080p strict" (no fallback)
    if '1080p preferred' in res:
        # Download 1080p kalau ada, fallback ke best available (e.g., 720p/360p kalau 1080p gak ada)
        video_fmt = 'bestvideo[height<=1080]/best'
    elif '1080p strict' in res:
        # Hanya ≤1080p, no fallback ke best (kalau 1080p gak ada, error atau skip)
        video_fmt = 'bestvideo[height<=1080]/best[height<=1080]'
    elif '480p' in res:
        video_fmt = 'bestvideo[height<=480]/best[height<=480]'
    elif '720p' in res:
        video_fmt = 'bestvideo[height<=720]/best[height<=720]'
    elif '1080p' in res:  # legacy fallback kalau ada pilihan "1080p" tanpa qualifier
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
    cookie_label = cookie_args[1] if cookie_args else 'Skip'
    print(f'║  Cookies : {cookie_label[:48]:<48}║')
    print('║  Output  : MP4 (video) + MP3 (audio) terpisah' + ' ' * 8 + '║')
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
                 '--no-playlist', '--newline'] + cookie_args + [url]
    try:
        subprocess.run(cmd_video)
    except KeyboardInterrupt:
        print('\n⏹ Dibatalkan.')
        sys.exit(130)

    # Download audio (MP3, via yt-dlp post-process convert)
    print('\n▶ Download audio (MP3 via yt-dlp convert)...')
    cmd_audio = [ytdlp, '-f', 'bestaudio/best',
                 '-x', '--audio-format', 'mp3',
                 '--audio-quality', '0',
                 '-o', audio_template,
                 '--no-playlist', '--newline'] + cookie_args + [url]
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
                       '--no-playlist'] + cookie_args + [url]
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

    found_video = found_audio = found_srt = None
    if custom_name:
        v_match = list(Path(output_dir).glob(f'{custom_name}.mp4'))
        a_match = list(Path(output_dir).glob(f'{custom_name}-audio.mp3')) + \
                  list(Path(output_dir).glob(f'{custom_name}-audio.m4a')) + \
                  list(Path(output_dir).glob(f'{custom_name}-audio.webm'))
        s_match = list(Path(output_dir).glob(f'{custom_name}*.srt'))
        if v_match: found_video = max(v_match, key=os.path.getmtime)
        if a_match: found_audio = max(a_match, key=os.path.getmtime)
        if s_match: found_srt = max(s_match, key=os.path.getmtime)
    else:
        mp4 = sorted(Path(output_dir).glob('*.mp4'), key=os.path.getmtime, reverse=True)
        aud = sorted(list(Path(output_dir).glob('*.mp3')) + list(Path(output_dir).glob('*.m4a')),
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
    print('   1. Demucs:    python3 demucs-tui.py')
    print('   2. SRT edit:  python3 srt-editor-tui.py  (fix typo kalau dari translate)')
    print('   3. TTS:       python3 edge-tts-tui.py')
    print('   4. Mix:       python3 mix-tui.py')
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
