#!/usr/bin/env python3
"""
mix-audio-dub.py — Mix audio dub WAV dengan audio ori MP4 (SFX preserve + ducking)

Strategi baru (5 Okt 2026, setelah 20x test render video gagal):
  Video = ground truth (SRT ori 100% sync, TIDAK di-retim).
  Audio dub fit ke SRT ori dengan Smart Fit (web app mode ON).
  Audio ori MP4 dipertahankan (SFX, backsound) + di-duck saat dialog dub bicara.

Workflow:
  1. Web app mode ON + Smart Fit → download audio dub WAV (fit ke SRT ori)
  2. python3 mix-audio-dub.py → mix audio ori MP4 + audio dub WAV dengan ducking
  3. Output MP4: video stream copy (100% ori) + audio mix (SFX + dub)

Output 100% sync dengan video ori. Tidak ada slow-mo, tidak ada stop-motion,
tidak ada DTS warnings. Video ori utuh, audio dub + SFX mix.

Standar nama file:
  --mp4          mp4-ori-{name}.mp4       (video asli, punya audio ori + SFX)
  --audio-dub    audio-{lang}-dub.wav     (audio dub dari web app, fit SRT ori)
  --output       mp4-{lang}-final.mp4     (output: video ori + audio mix)

Usage:
  python3 mix-audio-dub.py \\
    --mp4 mp4-ori-test-7min.mp4 \\
    --audio-dub audio-id-dub.wav \\
    --output mp4-id-final.mp4 \\
    --ducking 12

Ducking options:
  --ducking 12    Volume SFX turun 12dB saat dialog dub bicara (default 12)
  --no-ducking    SFX dan dub sama keras (no sidechain)
  --sfx-only      Buang audio ori total, hanya audio dub (fallback)

Requirements: ffmpeg, Python 3.8+
"""

import argparse
import os
import shutil
import subprocess
import sys
import tempfile


def find_tool(name: str, custom_path: str = None) -> str:
    """Cari ffmpeg/ffprobe di PATH atau lokasi umum."""
    if custom_path:
        if os.path.isfile(custom_path) and os.access(custom_path, os.X_OK):
            return custom_path
        raise FileNotFoundError(f'{name} tidak ditemukan di: {custom_path}')
    path = shutil.which(name) or shutil.which(f'{name}.exe')
    if path:
        return path
    common_locs = {
        'ffmpeg': ['/usr/local/bin/ffmpeg', '/usr/bin/ffmpeg', '/opt/homebrew/bin/ffmpeg'],
        'ffprobe': ['/usr/local/bin/ffprobe', '/usr/bin/ffprobe', '/opt/homebrew/bin/ffprobe'],
    }
    for loc in common_locs.get(name, []):
        if os.path.isfile(loc):
            return loc
    raise FileNotFoundError(f'{name} tidak ditemukan di PATH. Install atau specify via --{name}.')


def get_audio_duration(ffprobe: str, path: str) -> float:
    """Probe audio duration."""
    result = subprocess.run([
        ffprobe, '-v', 'error', '-show_entries', 'format=duration',
        '-of', 'default=noprint_wrappers=1:nokey=1', path,
    ], capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f'ffprobe gagal baca durasi: {result.stderr.strip()[:200]}')
    dur_str = result.stdout.strip()
    if not dur_str:
        raise RuntimeError(f'ffprobe return durasi kosong untuk: {path}')
    try:
        return float(dur_str)
    except ValueError:
        raise RuntimeError(f'ffprobe return durasi invalid "{dur_str}" untuk: {path}')


def mix_audio_dub(mp4_path, audio_dub_path, output_path, ffmpeg, ducking_db, sfx_only):
    """
    Mix audio ori MP4 + audio dub WAV dengan ducking (sidechain compression).

    Strategi:
    - Kalau --sfx-only: buang audio ori, hanya audio dub (fallback simple)
    - Kalau --no-ducking: SFX + dub sama keras (additive mix)
    - Kalau --ducking N: SFX di-duck N dB saat dialog dub bicara (sidechain gate)

    FFmpeg filter kompleks untuk ducking:
    [ori_audio]volume=1[sfx];                     # SFX dengan volume penuh
    [dub_audio]volume=1,asplit=2[dub][sidechain]; # dub + sidechain trigger
    [sfx][sidechain]sidechaincompress=threshold=0.05:ratio=10:attack=5:release=200[ducked_sfx];
    [ducked_sfx][dub]amix=inputs=2:duration=longest:normalize=0[out]

    threshold=0.05 (~-26dB) = saat dub di atas ini, SFX di-duck
    ratio=10 = ducking kuat (10:1 compression)
    attack=5ms = cepat duck saat dub mulai
    release=200ms = lambat recover setelah dub selesai (natural)
    """
    print(f'\n=== Mix audio dub + SFX preserve ===')
    print(f'  MP4 ori: {mp4_path}')
    print(f'  Audio dub: {audio_dub_path}')
    print(f'  Output: {output_path}')
    print(f'  Mode: {"SFX only (buang audio ori)" if sfx_only else f"Ducking {ducking_db}dB"}')

    if sfx_only:
        # Mode sfx-only: buang audio ori, hanya audio dub
        cmd = [
            ffmpeg, '-y',
            '-i', mp4_path,        # input 0: video + audio ori
            '-i', audio_dub_path,   # input 1: audio dub
            '-map', '0:v',          # video dari MP4 ori (stream copy)
            '-map', '1:a',          # audio dari dub (encode AAC)
            '-c:v', 'copy',
            '-c:a', 'aac', '-b:a', '192k',
            '-shortest',
            '-movflags', '+faststart',
            output_path,
        ]
    elif ducking_db <= 0:
        # No ducking: SFX + dub sama keras (additive)
        cmd = [
            ffmpeg, '-y',
            '-i', mp4_path,
            '-i', audio_dub_path,
            '-filter_complex',
            '[0:a]volume=1[sfx];[1:a]volume=1[dub];[sfx][dub]amix=inputs=2:duration=longest:normalize=0[aout]',
            '-map', '0:v',
            '-map', '[aout]',
            '-c:v', 'copy',
            '-c:a', 'aac', '-b:a', '192k',
            '-shortest',
            '-movflags', '+faststart',
            output_path,
        ]
    else:
        # Ducking: SFX di-duck saat dialog dub bicara (sidechain compression)
        # Konversi dB ke linear ratio (mis. -12dB → 0.251)
        duck_linear = 10 ** (-ducking_db / 20)
        # Sidechain threshold: ~-26dB (0.05 linear) — saat dub di atas ini, SFX di-duck
        # Make-up gain: +ducking_db (kompensasi untuk ducking)
        filter_complex = (
            f'[0:a]volume=1[sfx];'
            f'[1:a]volume=1,asplit=2[dub][sidechain];'
            f'[sfx][sidechain]sidechaincompress='
            f'threshold=0.05:'  # saat dub > -26dB, trigger ducking
            f'ratio={10 if ducking_db >= 10 else 5}:'  # 10:1 untuk ducking kuat
            f'attack=5:'  # 5ms attack (cepat duck saat dub mulai bicara)
            f'release=300:'  # 300ms release (lambat recover, natural)
            f'makeup={ducking_db}:'  # make-up gain untuk kompensasi
            f'[ducked_sfx];'
            f'[ducked_sfx][dub]amix=inputs=2:duration=longest:normalize=0[aout]'
        )
        cmd = [
            ffmpeg, '-y',
            '-i', mp4_path,
            '-i', audio_dub_path,
            '-filter_complex', filter_complex,
            '-map', '0:v',
            '-map', '[aout]',
            '-c:v', 'copy',
            '-c:a', 'aac', '-b:a', '192k',
            '-shortest',
            '-movflags', '+faststart',
            output_path,
        ]

    print(f'  → Running FFmpeg...')
    result = subprocess.run(cmd)
    if result.returncode != 0:
        print(f'\n✗ Mix gagal dengan code {result.returncode}')
        return False
    print(f'  ✓ Mix selesai')
    return True


def main():
    parser = argparse.ArgumentParser(
        description='Mix audio dub WAV dengan audio ori MP4 (SFX preserve + ducking)',
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument('--mp4', required=True,
                        help='MP4 ori (video + audio ori SFX). Standar: mp4-ori-{name}.mp4')
    parser.add_argument('--audio-dub', required=True,
                        help='Audio dub WAV (fit SRT ori, dari web app mode ON + Smart Fit)')
    parser.add_argument('--output', required=True,
                        help='Output MP4 final. Standar: mp4-{lang}-final.mp4')
    parser.add_argument('--ffmpeg', help='Path kustom ke ffmpeg')
    parser.add_argument('--ffprobe', help='Path kustom ke ffprobe')
    parser.add_argument('--ducking', type=float, default=12.0,
                        help='Volume SFX turun N dB saat dialog dub bicara (default 12)')
    parser.add_argument('--no-ducking', action='store_true',
                        help='SFX dan dub sama keras (no sidechain, additive mix)')
    parser.add_argument('--sfx-only', action='store_true',
                        help='Buang audio ori total, hanya audio dub (fallback simple)')
    args = parser.parse_args()

    # Validate inputs
    for label, path in [('MP4 ori', args.mp4), ('Audio dub', args.audio_dub)]:
        if not os.path.isfile(path):
            print(f'Error: {label} tidak ditemukan: {path}', file=sys.stderr)
            sys.exit(1)

    # Find tools
    try:
        ffmpeg = find_tool('ffmpeg', args.ffmpeg)
        ffprobe = find_tool('ffprobe', args.ffprobe)
    except FileNotFoundError as e:
        print(f'Error: {e}', file=sys.stderr)
        sys.exit(1)

    print(f'ffmpeg: {ffmpeg}')
    print(f'ffprobe: {ffprobe}')

    # Probe durations
    mp4_dur = get_audio_duration(ffprobe, args.mp4)
    dub_dur = get_audio_duration(ffprobe, args.audio_dub)
    print(f'\nMP4 durasi: {mp4_dur:.2f}s')
    print(f'Audio dub durasi: {dub_dur:.2f}s')
    if dub_dur > mp4_dur + 1.0:
        print(f'⚠ Audio dub ({dub_dur:.1f}s) lebih panjang dari MP4 ({mp4_dur:.1f}s).')
        print(f'  Output akan dipotong ke MP4 durasi (-shortest).')
        print(f'  Tips: pakai MP4 source yang lebih panjang, atau audio dub yang lebih pendek.')

    # Mix
    success = mix_audio_dub(
        args.mp4, args.audio_dub, args.output,
        ffmpeg, args.ducking if not args.no_ducking else 0,
        args.sfx_only,
    )
    if not success:
        print('\n❌ Mix gagal.')
        sys.exit(1)

    # Verify output
    if os.path.isfile(args.output):
        out_size = os.path.getsize(args.output)
        out_duration = get_audio_duration(ffprobe, args.output)
        print(f'\n✅ Output: {args.output}')
        print(f'   Size: {out_size / 1024 / 1024:.1f} MB')
        print(f'   Duration: {out_duration:.2f}s')
        print(f'\n   → Buka di DaVinci Resolve untuk editing final.')
    else:
        print(f'\n❌ Output tidak ditemukan: {args.output}', file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print('\n\n⏹ Dibatalkan user.')
        sys.exit(130)
    except RuntimeError as e:
        print(f'\n❌ Error: {e}', file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f'\n❌ Error tidak terduga: {e}', file=sys.stderr)
        import traceback
        print(f'\nStack trace:\n{traceback.format_exc()[:1000]}', file=sys.stderr)
        sys.exit(1)
