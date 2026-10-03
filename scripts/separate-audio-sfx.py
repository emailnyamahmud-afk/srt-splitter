#!/usr/bin/env python3
"""
separate-audio-sfx.py — Pisahkan audio MP4 menjadi vocals + SFX (backsound)

Pakai Demucs (state-of-the-art source separation by Meta/Facebook Research).
Demucs model: htdemucs (Hybrid Transformer Demucs v4) — SDR 9.00 dB

Output:
  vocals.wav      — suara dialog Mandarin (akan dibuang, diganti audio Jawa)
  no_vocals.wav   — SFX + backsound + music (akan di-mix dengan audio Jawa)

Usage:
  python3 separate-audio-sfx.py --mp4 mandarin.mp4 --output-dir output/

Requirements:
  - ffmpeg (auto-detect atau --ffmpeg)
  - Demucs: pip install demucs
  - Python 3.8+
  - Pertama kali: butuh download model Demucs (~80MB)

Catatan:
  - Untuk file 90 menit: butuh 10-20 menit di MacBook M1/M2 (CPU)
  - Untuk GPU NVIDIA: butuh 2-5 menit
  - Output 44.1kHz stereo WAV (sesuai Demucs default)
"""

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path


def find_ffmpeg(custom_path: str = None) -> str:
    if custom_path:
        if os.path.isfile(custom_path) and os.access(custom_path, os.X_OK):
            return custom_path
        raise FileNotFoundError(f'ffmpeg tidak ditemukan di: {custom_path}')
    path = shutil.which('ffmpeg') or shutil.which('ffmpeg.exe')
    if path:
        return path
    for loc in ['/usr/local/bin/ffmpeg', '/usr/bin/ffmpeg', '/opt/homebrew/bin/ffmpeg']:
        if os.path.isfile(loc):
            return loc
    raise FileNotFoundError('ffmpeg tidak ditemukan di PATH')


def find_demucs() -> str:
    """Cari demucs CLI executable."""
    path = shutil.which('demucs') or shutil.which('demucs.exe')
    if path:
        return path
    # Coba via python module
    try:
        result = subprocess.run(
            [sys.executable, '-c', 'import demucs; print(demucs.__file__)'],
            capture_output=True, text=True,
        )
        if result.returncode == 0:
            return None  # pakai python -m demucs
    except:
        pass
    return None


def main():
    parser = argparse.ArgumentParser(
        description='Pisahkan audio MP4 → vocals + SFX dengan Demucs',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Contoh:
  python3 separate-audio-sfx.py --mp4 mandarin.mp4 --output-dir output/

Install Demucs dulu:
  pip install demucs

Atau dengan GPU (lebih cepat):
  pip install demucs torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121
        """,
    )
    parser.add_argument('--mp4', required=True, help='Path ke MP4 input')
    parser.add_argument('--output-dir', default='./output', help='Directory output (default: ./output)')
    parser.add_argument('--ffmpeg', help='Path kustom ke ffmpeg')
    parser.add_argument('--two-stems', default='vocals',
                        help='Mode 2-stem (default: vocals → vocals + no_vocals). Alternatif: drums, bass, other')
    parser.add_argument('--model', default='htdemucs',
                        help='Demucs model (default: htdemucs). Alternatif: htdemucs_ft, mdx, mdx_extra')
    parser.add_argument('--keep-intermediate', action='store_true',
                        help='Keep audio-original.wav (intermediate file)')
    args = parser.parse_args()

    # Validate
    if not os.path.isfile(args.mp4):
        print(f'Error: MP4 tidak ditemukan: {args.mp4}', file=sys.stderr)
        sys.exit(1)

    # Find tools
    try:
        ffmpeg = find_ffmpeg(args.ffmpeg)
    except FileNotFoundError as e:
        print(f'Error: {e}', file=sys.stderr)
        sys.exit(1)

    demucs_bin = find_demucs()
    if not demucs_bin:
        print('Error: Demucs tidak ditemukan. Install dengan:')
        print('  pip install demucs')
        print('Atau:')
        print('  pip install demucs torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121')
        sys.exit(1)

    print(f'ffmpeg: {ffmpeg}')
    print(f'demucs: {demucs_bin} atau python -m demucs')
    print(f'model: {args.model}')
    print(f'two-stems: {args.two_stems}')

    # Prepare output dir
    os.makedirs(args.output_dir, exist_ok=True)
    work_dir = os.path.join(args.output_dir, 'work')
    os.makedirs(work_dir, exist_ok=True)

    # Step 1: Extract audio dari MP4
    audio_ori = os.path.join(work_dir, 'audio-original.wav')
    print(f'\n=== Step 1: Extract audio dari MP4 ===')
    cmd = [
        ffmpeg, '-y', '-i', args.mp4,
        '-vn',
        '-acodec', 'pcm_s16le',
        '-ar', '44100',
        '-ac', '2',
        audio_ori,
    ]
    print(f'  → {" ".join(cmd)}')
    result = subprocess.run(cmd)
    if result.returncode != 0:
        print('  ✗ Gagal extract audio', file=sys.stderr)
        sys.exit(1)
    print(f'  ✓ Audio ori: {audio_ori}')

    # Step 2: Run Demucs
    print(f'\n=== Step 2: Run Demucs (model: {args.model}) ===')
    print('  → Pertama kali: download model ~80MB')
    print('  → Proses: 10-20 menit di CPU, 2-5 menit di GPU')

    demucs_cmd = [demucs_bin, '--two-stems', args.two_stems, '-n', args.model, '-o', work_dir, audio_ori]
    print(f'  → {" ".join(demucs_cmd)}')
    result = subprocess.run(demucs_cmd)
    if result.returncode != 0:
        print('  ✗ Demucs gagal. Coba install ulang:', file=sys.stderr)
        print('  pip install --upgrade demucs')
        sys.exit(1)

    # Demucs output: work_dir/audio-original/<two-stems>.wav + no_<two-stems>.wav
    base_name = os.path.splitext(os.path.basename(audio_ori))[0]
    stem_path = os.path.join(work_dir, base_name, f'{args.two_stems}.wav')
    no_stem_path = os.path.join(work_dir, base_name, f'no_{args.two_stems}.wav')

    if not os.path.isfile(stem_path) or not os.path.isfile(no_stem_path):
        print(f'  ✗ Output Demucs tidak ditemukan:', file=sys.stderr)
        print(f'    Expected: {stem_path}')
        print(f'    Expected: {no_stem_path}')
        print(f'    Files in work dir:')
        for f in Path(work_dir).rglob('*.wav'):
            print(f'      {f}')
        sys.exit(1)

    # Step 3: Copy output ke output dir
    print(f'\n=== Step 3: Copy output ===')
    if args.two_stems == 'vocals':
        vocals_out = os.path.join(args.output_dir, 'vocals-mandarin.wav')
        sfx_out = os.path.join(args.output_dir, 'sfx-backsound.wav')
    else:
        vocals_out = os.path.join(args.output_dir, f'{args.two_stems}.wav')
        sfx_out = os.path.join(args.output_dir, f'no_{args.two_stems}.wav')

    shutil.copy2(stem_path, vocals_out)
    shutil.copy2(no_stem_path, sfx_out)

    print(f'  ✓ Vocals (akan dibuang): {vocals_out}')
    print(f'  ✓ SFX/backsound (akan di-mix): {sfx_out}')

    # Cleanup intermediate
    if not args.keep_intermediate:
        os.remove(audio_ori)
        shutil.rmtree(os.path.join(work_dir, base_name), ignore_errors=True)
        # Demucs creates intermediate dirs, cleanup if empty
        try:
            os.rmdir(work_dir)
        except OSError:
            pass

    print(f'\n✓ Selesai. Output di: {args.output_dir}')
    print(f'\nGunakan SFX di retime-video-v2.py:')
    print(f'  python3 retime-video-v2.py \\')
    print(f'    --mp4 {args.mp4} \\')
    print(f'    --srt-mandarin original.srt \\')
    print(f'    --srt-jawa subs-jawa-new.srt \\')
    print(f'    --audio-jawa audio-jawa.wav \\')
    print(f'    --output mp4-jawa.mp4 \\')
    print(f'    --separate-sfx')
    # Note: --separate-sfx di retime-video-v2.py akan auto-run Demucs
    # Tapi kalau user sudah punya sfx-backsound.wav, bisa langsung pakai


if __name__ == '__main__':
    main()
