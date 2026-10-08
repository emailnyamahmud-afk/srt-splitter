#!/usr/bin/env python3
"""
yt-dlp-tui.py — TUI untuk download YouTube video (MP4 1080p H.264 + audio)

Download video YouTube dengan yt-dlp, output:
  - Video: H.264 1080p (format 137 = 1080p H.264)
  - Audio: m4a (format 140)
  - Merge: MP4 (video + audio digabung)

Install yt-dlp (sekali saja):
  pip3 install yt-dlp
  # Atau: pip3 install yt-dlp --break-system-packages
  # Atau: brew install yt-dlp

Usage:
  source venv/bin/activate  # kalau install di venv
  python3 yt-dlp-tui.py
  (pilih mode, paste URL YouTube, tunggu download)

Output:
  {title}.mp4 (video 1080p H.264 + audio, siap untuk workflow dubbing)

Tips:
  - Format 137 = 1080p H.264 (cepat decode di FFmpeg, cocok untuk Demucs)
  - Format 140 = audio m4a 128kbps
  - Kalau 1080p tidak ada, fallback ke 720p (format 136)
  - Kalau H.264 tidak ada, fallback ke format terbaik
"""

import os
import sys
import subprocess
import re
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
    print('║  📺 YouTube Downloader (TUI Mode)' + ' ' * 32 + '║')
    print('║  Download MP4 1080p H.264 + audio untuk dubbing' + ' ' * 16 + '║')
    print('╚' + '═' * 64 + '╝')
    print()


def check_ytdlp():
    """Cek apakah yt-dlp terinstall."""
    import shutil
    path = shutil.which('yt-dlp') or shutil.which('yt-dlp.exe')
    if path:
        return path
    # Coba di venv
    venv_path = os.path.join(os.path.dirname(sys.executable), 'yt-dlp')
    if os.path.isfile(venv_path) and os.access(venv_path, os.X_OK):
        return venv_path
    return None


def sanitize_filename(name):
    """Bersihkan karakter ilegal dari nama file."""
    # Hapus karakter yang tidak valid di macOS/Linux/Windows
    name = re.sub(r'[\\/:*?"<>|]', '', name)
    name = name.strip()
    # Limit panjang nama file
    if len(name) > 200:
        name = name[:200]
    return name or 'video'


def main():
    print_banner()

    # Cek yt-dlp
    ytdlp = check_ytdlp()
    if not ytdlp:
        print('❌ yt-dlp belum terinstall.')
        print()
        print('   Install dengan:')
        print('   pip3 install yt-dlp')
        print('   # Atau: pip3 install yt-dlp --break-system-packages')
        print('   # Atau: brew install yt-dlp')
        print()
        sys.exit(1)

    print(f'yt-dlp: {ytdlp}')
    print()
    print('📋 Step-by-step, ikuti petunjuk di layar.')
    print('   Navigasi: ↑↓ arrow keys, Enter konfirmasi, q batal')
    print()

    # Step 1: Mode download
    print('▶ Step 1/5: Pilih mode download')
    mode = questionary.select(
        'Mode:',
        choices=[
            '1080p H.264 + audio (REKOMENDASI untuk dubbing) — format 137+140',
            '720p H.264 + audio (lebih kecil, cepat download) — format 136+140',
            'Best quality (auto, bisa AV1/VP9) — tidak rekomendasi untuk dubbing',
            'Audio only (m4a 128kbps) — kalau cuma butuh audio',
        ],
        default='1080p H.264 + audio (REKOMENDASI untuk dubbing) — format 137+140',
    ).ask()
    print(f'  ✓ {mode}')
    print()

    # Step 2: URL YouTube
    print('▶ Step 2/5: Masukkan URL YouTube')
    url = questionary.text(
        'URL YouTube (paste link video):',
    ).ask()
    if not url or not url.strip():
        print('Batal.')
        sys.exit(0)
    url = url.strip()
    print(f'  ✓ {url}')
    print()

    # Step 3: Output directory
    print('▶ Step 3/5: Pilih output directory')
    output_dir = questionary.text(
        'Output directory (default: ~/Dubbing):',
        default=os.path.expanduser('~/Dubbing'),
    ).ask()
    if not output_dir:
        output_dir = os.path.expanduser('~/Dubbing')
    output_dir = os.path.expanduser(output_dir)
    os.makedirs(output_dir, exist_ok=True)
    print(f'  ✓ {output_dir}')
    print()

    # Step 4: Rename output (opsional)
    print('▶ Step 4/5: Rename output (opsional)')
    custom_name = questionary.text(
        'Nama file custom (kosongkan = pakai judul YouTube):',
        default='',
    ).ask()
    if custom_name and custom_name.strip():
        custom_name = sanitize_filename(custom_name.strip())
        print(f'  ✓ {custom_name}.mp4')
    else:
        custom_name = None
        print(f'  ✓ (pakai judul YouTube)')
    print()

    # Step 5: Konfirmasi
    print('▶ Step 5/5: Konfirmasi')

    # Build yt-dlp command
    if '1080p' in mode:
        format_str = '137+140/bestvideo+bestaudio/best'
        # 137 = 1080p H.264, 140 = audio m4a
        # Fallback: bestvideo+bestaudio, lalu best
    elif '720p' in mode:
        format_str = '136+140/bestvideo[height<=720]+bestaudio/best[height<=720]/best'
        # 136 = 720p H.264, 140 = audio m4a
    elif 'Audio only' in mode:
        format_str = '140/bestaudio'
    else:
        # Best quality (auto)
        format_str = 'bestvideo+bestaudio/best'

    # Output template
    if custom_name:
        output_template = os.path.join(output_dir, f'{custom_name}.%(ext)s')
    else:
        output_template = os.path.join(output_dir, '%(title).200s.%(ext)s')

    cmd = [
        ytdlp,
        '-f', format_str,
        '-o', output_template,
        '--no-playlist',
        '--newline',  # satu baris progress, mudah dibaca
    ]

    # Mode "terpisah": jangan merge, pakai -k untuk keep file asli
    # Mode "merged": merge video+audio jadi 1 MP4
    if 'terpisah' in output_mode:
        # Download video dan audio terpisah, KEEP file asli (jangan delete)
        cmd.append('-k')  # keep original files after merge
        # JANGAN pakai --merge-output-format (biarkan video + audio tetap terpisah)
        # Tapi yt-dlp tetap merge kalau format berbeda — gunakan 2 command terpisah
    else:
        cmd.extend(['--merge-output-format', 'mp4'])

    # Konfirmasi
    print()
    print('╔' + '═' * 64 + '╗')
    print('║  📋 Ringkasan:' + ' ' * 49 + '║')
    print('╠' + '═' * 64 + '╣')
    print(f'║  Mode   : {mode[:46]:<46}║')
    print(f'║  URL    : {url[:46]:<46}║')
    print(f'║  Output : {output_dir[:46]:<46}║')
    if custom_name:
        print(f'║  Nama   : {custom_name[:46]:<46}║')
    print('╚' + '═' * 64 + '╝')
    print()
    print('=== Command yang akan dijalankan ===')
    print(f'yt-dlp -f "{format_str}" --merge-output-format mp4 -o "{output_template}" {url}')
    print('=== End command ===')
    print()

    confirm = questionary.confirm('Lanjut download?', default=True).ask()
    if not confirm:
        print('Batal.')
        sys.exit(0)

    # Eksekusi
    print('\n' + '═' * 64)
    print('🚀 Mulai download...')
    print('═' * 64 + '\n')

    if 'terpisah' in output_mode:
        # MODE TERPISAH: download video dan audio sebagai 2 file terpisah
        base_name = custom_name if custom_name else '%(title).200s'
        video_template = os.path.join(output_dir, f'{base_name}.%(ext)s')
        audio_template = os.path.join(output_dir, f'{base_name}-audio.%(ext)s')

        # Command 1: video only
        if '480p' in res:
            video_fmt = 'bestvideo[height<=480]/best[height<=480]'
        elif '720p' in res:
            video_fmt = 'bestvideo[height<=720]/best[height<=720]'
        elif '1080p' in res:
            video_fmt = 'bestvideo[height<=1080]/best[height<=1080]'
        else:
            video_fmt = 'bestvideo/best'

        print('▶ Download video (tanpa audio)...')
        cmd_video = [ytdlp, '-f', video_fmt, '-o', video_template, '--no-playlist', '--newline', url]
        try:
            subprocess.run(cmd_video)
        except KeyboardInterrupt:
            print('\n⏹ Dibatalkan.')
            sys.exit(130)

        # Command 2: audio only
        print('\n▶ Download audio (m4a)...')
        cmd_audio = [ytdlp, '-f', 'bestaudio/best', '-o', audio_template, '--no-playlist', '--newline', '--extract-audio', url]
        try:
            subprocess.run(cmd_audio)
        except KeyboardInterrupt:
            print('\n⏹ Dibatalkan.')
            sys.exit(130)

        exit_code = 0
    else:
        # MODE MERGED: 1 command, merge video+audio jadi 1 MP4
        cmd.extend([url])
        try:
            result = subprocess.run(cmd)
            exit_code = result.returncode
        except KeyboardInterrupt:
            print('\n\n⏹ Dibatalkan user.')
            sys.exit(130)

    print()
    if exit_code == 0:
        print('═' * 64)
        print('✅ SELESAI!')
        print()
        # Cari file output
        mp4_files = sorted(Path(output_dir).glob('*.mp4'), key=os.path.getmtime, reverse=True)
        if mp4_files:
            latest = mp4_files[0]
            size_mb = latest.stat().st_size / 1024 / 1024
            print(f'📁 Output: {latest}')
            print(f'   Size: {size_mb:.1f} MB')
            print()
            print('🎬 Langkah berikutnya (workflow dubbing):')
            print()
            print('   1. Rename ke standar: mv "{}" mp4-ori-{{name}}.mp4'.format(latest.name))
            print('   2. Demucs: python3 demucs-tui.py (pilih MP4 ini)')
            print('   3. Web app: mode ON + Smart Fit → audio-id-dub.wav')
            print('   4. Mix: python3 mix-tui.py')
        print('═' * 64)
    else:
        print('═' * 64)
        print(f'❌ GAGAL dengan exit code {exit_code}')
        print()
        print('Cek error message di atas. Umumnya:')
        print('  - URL salah → paste URL lengkap (https://www.youtube.com/watch?v=...)')
        print('  - Format tidak ada → coba mode "Best quality"')
        print('  - Rate limit → tunggu 1-2 menit, coba lagi')
        print('  - ffmpeg belum install → brew install ffmpeg')
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
