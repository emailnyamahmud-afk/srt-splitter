#!/usr/bin/env python3
"""
retime-video-v2.py — Retime MP4 Mandarin supaya match SRT Jawa baru (SRT = ground truth)

Strategi v2 (SRT = Ground of Truth):
  1. Video MP4 di-retim: cue Mandarin di-slow-mo/fast-forward ke durasi cue Jawa
  2. Audio Jawa (WAV) menjadi audio utama
  3. SFX + backsound dari MP4 asli DIPERTAHANKAN (mixed di latar)
  4. Gap antar cue: video play normal, SFX + backsound tetap ada

Algoritma:
  1. Ekstrak audio dari MP4 asli → audio-original.wav
  2. (Opsional) Separasi audio-original dengan Demucs → vocals.mp4_original + sfx.mp4_original
  3. Bangun ffmpeg filter_complex:
     - Video: trim per cue + setpts (slow-mo) + concat
     - Audio SFX (dari MP4 asli atau Demucs output): trim per cue + atempo (slow-mo audio) + concat
  4. Mix: audio Jawa (dari Fase 2) + audio SFX (yang sudah di-retim)
  5. Output: mp4-jawa-final.mp4 (video retimed + audio Jawa + SFX backsound)

Usage:
  # Basic (tanpa SFX separation - audio Jawa + audio ori Mandarin di-duck)
  python3 retime-video-v2.py \
    --mp4 mandarin.mp4 \
    --srt-mandarin original.srt \
    --srt-jawa subs-jawa-new.srt \
    --audio-jawa audio-jawa.wav \
    --output mp4-jawa.mp4

  # Advanced (pakai Demucs untuk separate SFX)
  python3 retime-video-v2.py \
    --mp4 mandarin.mp4 \
    --srt-mandarin original.srt \
    --srt-jawa subs-jawa-new.srt \
    --audio-jawa audio-jawa.wav \
    --output mp4-jawa.mp4 \
    --separate-sfx \
    --sfx-ducking 0.3

Requirements:
  - ffmpeg (auto-detect atau --ffmpeg)
  - Python 3.8+
  - Optional: Demucs (pip install demucs) kalau pakai --separate-sfx

Catatan:
  - Kalau --separate-sfx: butuh Demucs (~80MB model download pertama kali)
  - Kalau tanpa --separate-sfx: audio ori di-duck (volume turun) saat cue Jawa bicara
  - Output selalu 1 MP4 dengan 1 audio track (Jawa + SFX mix)
"""

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


# ============================================================
# SRT parsing
# ============================================================

def parse_srt(content: str):
    """Parse SRT string jadi list of {index, start, end, text}."""
    normalized = content.replace('\r\n', '\n').replace('\r', '\n').strip()
    if not normalized:
        return []
    blocks = re.split(r'\n\s*\n', normalized)
    entries = []
    for block in blocks:
        lines = [l for l in block.split('\n') if l.strip()]
        if not lines:
            continue
        time_idx = -1
        for i, line in enumerate(lines):
            if '-->' in line:
                time_idx = i
                break
        if time_idx == -1:
            continue
        m = re.match(
            r'(\d{1,2}:\d{2}:\d{2}[,.]\d{1,3})\s*-->\s*(\d{1,2}:\d{2}:\d{2}[,.]\d{1,3})',
            lines[time_idx],
        )
        if not m:
            continue
        start = parse_time(m.group(1))
        end = parse_time(m.group(2))
        text = '\n'.join(lines[time_idx + 1:])
        entries.append({
            'index': len(entries) + 1,
            'start': start,
            'end': end,
            'text': text,
        })
    return entries


def parse_time(ts: str) -> float:
    """Parse 'HH:MM:SS,mmm' → seconds (float)."""
    ts = ts.replace('.', ',')
    hms, ms = ts.split(',') if ',' in ts else (ts, '0')
    h, m, s = hms.split(':')
    return int(h) * 3600 + int(m) * 60 + int(s) + int(ms) / 1000


def format_time_ffmpeg(seconds: float) -> str:
    """Format seconds → 'HH:MM:SS.mmm' (untuk ffmpeg trim)."""
    if seconds < 0:
        seconds = 0
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    ms = int((seconds - int(seconds)) * 1000)
    return f'{h:02d}:{m:02d}:{s:02d}.{ms:03d}'


# ============================================================
# ffmpeg helpers
# ============================================================

def find_ffmpeg(custom_path: str = None) -> str:
    """Cari ffmpeg executable."""
    if custom_path:
        if os.path.isfile(custom_path) and os.access(custom_path, os.X_OK):
            return custom_path
        raise FileNotFoundError(f'ffmpeg tidak ditemukan di: {custom_path}')
    path = shutil.which('ffmpeg') or shutil.which('ffmpeg.exe')
    if path:
        return path
    for loc in ['/usr/local/bin/ffmpeg', '/usr/bin/ffmpeg', '/opt/homebrew/bin/ffmpeg',
                '/Applications/ffmpeg', 'C:\\ffmpeg\\bin\\ffmpeg.exe']:
        if os.path.isfile(loc):
            return loc
    raise FileNotFoundError(
        'ffmpeg tidak ditemukan di PATH. Install ffmpeg atau specify via --ffmpeg.'
    )


def find_ffprobe(custom_path: str = None) -> str:
    """Cari ffprobe executable."""
    if custom_path:
        if os.path.isfile(custom_path) and os.access(custom_path, os.X_OK):
            return custom_path
        raise FileNotFoundError(f'ffprobe tidak ditemukan di: {custom_path}')
    path = shutil.which('ffprobe') or shutil.which('ffprobe.exe')
    if path:
        return path
    for loc in ['/usr/local/bin/ffprobe', '/usr/bin/ffprobe', '/opt/homebrew/bin/ffprobe']:
        if os.path.isfile(loc):
            return loc
    raise FileNotFoundError('ffprobe tidak ditemukan di PATH')


def run_cmd(cmd: list, label: str = '', capture: bool = True):
    """Run command, print progress."""
    print(f'  → {label or " ".join(cmd[:3])}...')
    if capture:
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            print(f'  ✗ Error: {result.stderr[-500:]}', file=sys.stderr)
            raise RuntimeError(f'{cmd[0]} gagal: {result.stderr[-200:]}')
        return result.stdout
    else:
        result = subprocess.run(cmd)
        if result.returncode != 0:
            raise RuntimeError(f'{cmd[0]} gagal dengan code {result.returncode}')
        return ''


def get_mp4_duration(ffprobe: str, mp4_path: str) -> float:
    """Dapatkan durasi MP4 dalam detik."""
    out = run_cmd([
        ffprobe, '-v', 'error',
        '-show_entries', 'format=duration',
        '-of', 'default=noprint_wrappers=1:nokey=1',
        mp4_path,
    ], 'ffprobe duration')
    return float(out.strip())


def get_mp4_audio_streams(ffprobe: str, mp4_path: str) -> list:
    """Cek apakah MP4 punya audio stream."""
    out = run_cmd([
        ffprobe, '-v', 'error',
        '-show_entries', 'stream=index,codec_type,codec_name,channels',
        '-of', 'json',
        mp4_path,
    ], 'ffprobe streams')
    data = json.loads(out)
    return [s for s in data.get('streams', []) if s.get('codec_type') == 'audio']


# ============================================================
# Demucs SFX separation (optional)
# ============================================================

def separate_sfx_with_demucs(mp4_path: str, work_dir: str) -> dict:
    """
    Pisahkan audio MP4 menjadi vocals + no_vocals (SFX/backsound) dengan Demucs.
    Returns: {'vocals': path, 'no_vocals': path}
    """
    print('\n=== SFX Separation dengan Demucs ===')
    # Cek demucs installed
    demucs_bin = shutil.which('demucs') or shutil.which('demucs.exe')
    if not demucs_bin:
        print('  ⚠ Demucs tidak ditemukan. Install dengan: pip install demucs')
        print('  → Skip SFX separation, fallback ke audio-ori ducking mode')
        return None

    # Extract audio dari MP4 dulu
    audio_ori = os.path.join(work_dir, 'audio-original.wav')
    ffmpeg = find_ffmpeg()
    run_cmd([
        ffmpeg, '-y', '-i', mp4_path,
        '-vn',  # no video
        '-acodec', 'pcm_s16le',
        '-ar', '44100',
        '-ac', '2',
        audio_ori,
    ], 'extract audio dari MP4')

    # Run Demucs
    print('  → Run Demucs (mungkin butuh 5-15 menit untuk file besar)...')
    demucs_out_dir = os.path.join(work_dir, 'demucs-output')
    os.makedirs(demucs_out_dir, exist_ok=True)
    cmd = [
        demucs_bin,
        '--two-stems', 'vocals',  # split jadi vocals + no_vocals
        '-o', demucs_out_dir,
        audio_ori,
    ]
    result = subprocess.run(cmd)
    if result.returncode != 0:
        print(f'  ✗ Demucs gagal. Fallback ke audio-ori ducking mode')
        return None

    # Demucs output: demucs-output/<filename>/vocals.wav + no_vocals.wav
    base_name = os.path.splitext(os.path.basename(audio_ori))[0]
    vocals_path = os.path.join(demucs_out_dir, base_name, 'vocals.wav')
    no_vocals_path = os.path.join(demucs_out_dir, base_name, 'no_vocals.wav')

    if not os.path.isfile(vocals_path) or not os.path.isfile(no_vocals_path):
        print(f'  ✗ Output Demucs tidak ditemukan. Fallback ke ducking mode')
        return None

    print(f'  ✓ Vocals: {vocals_path}')
    print(f'  ✓ SFX/backsound: {no_vocals_path}')
    return {'vocals': vocals_path, 'no_vocals': no_vocals_path}


# ============================================================
# Build ffmpeg filter_complex untuk retim
# ============================================================

def build_filter_complex(mandarin_entries, jawa_entries, mp4_duration, has_audio_ori, ducking_db):
    """
    Bangun ffmpeg filter_complex dengan strategi SRT = ground truth.

    Untuk setiap cue:
    - Video: trim dari cue.start_mandarin ke cue.end_mandarin, lalu setpts ke durasi cue Jawa
    - Audio (SFX): sama, trim + atempo untuk slow-mo audio

    Untuk setiap gap antar cue:
    - Video: trim gap asli, setpts ke durasi gap Jawa
    - Audio: sama, trim + atempo

    Final: concat semua segment → output video + audio (SFX)
    Audio Jawa di-mix terpisah (lewat -map)
    """
    filters = []
    concat_v_inputs = []
    concat_a_inputs = []
    seg_idx = 0

    # Mapping cue Jawa by index (asumsi 1-to-1 dengan cue Mandarin)
    jawa_by_idx = {i: e for i, e in enumerate(jawa_entries)}

    last_end = 0.0

    for i, m_entry in enumerate(mandarin_entries):
        # 1. Gap sebelum cue ini
        gap_mandarin_dur = m_entry['start'] - last_end
        if gap_mandarin_dur > 0.01:
            # Cari gap duration di timeline Jawa
            if i in jawa_by_idx and (i - 1) in jawa_by_idx:
                jawa_gap_dur = jawa_by_idx[i]['start'] - jawa_by_idx[i - 1]['end']
            elif i == 0 and i in jawa_by_idx:
                jawa_gap_dur = jawa_by_idx[i]['start']
            else:
                jawa_gap_dur = gap_mandarin_dur  # fallback

            jawa_gap_dur = max(0.05, jawa_gap_dur)
            factor = jawa_gap_dur / gap_mandarin_dur

            # Trim video gap
            filters.append(
                f'[0:v]trim=start={last_end:.3f}:end={m_entry["start"]:.3f},'
                f'setpts=PTS-STARTPTS,setpts={1/factor:.6f}*PTS[gap_v{seg_idx}];'
            )
            concat_v_inputs.append(f'[gap_v{seg_idx}]')

            # Trim audio gap (SFX)
            if has_audio_ori:
                filters.append(
                    f'[0:a]atrim=start={last_end:.3f}:end={m_entry["start"]:.3f},'
                    f'asetpts=PTS-STARTPTS,atempo={factor:.6f}[gap_a{seg_idx}];'
                )
                concat_a_inputs.append(f'[gap_a{seg_idx}]')
            seg_idx += 1

        # 2. Cue itu sendiri
        if i in jawa_by_idx:
            j_entry = jawa_by_idx[i]
            cue_mandarin_dur = m_entry['end'] - m_entry['start']
            cue_jawa_dur = j_entry['end'] - j_entry['start']

            if cue_mandarin_dur > 0.01 and cue_jawa_dur > 0.01:
                factor = cue_jawa_dur / cue_mandarin_dur
                # Trim video cue
                filters.append(
                    f'[0:v]trim=start={m_entry["start"]:.3f}:end={m_entry["end"]:.3f},'
                    f'setpts=PTS-STARTPTS,setpts={1/factor:.6f}*PTS[cue_v{seg_idx}];'
                )
                concat_v_inputs.append(f'[cue_v{seg_idx}]')

                # Trim audio cue (SFX) - kalau factor > 2x, pakai atempo chain (max 2x per filter)
                if has_audio_ori:
                    if factor <= 2.0:
                        atempo_filter = f'atempo={factor:.6f}'
                    elif factor <= 4.0:
                        atempo_filter = f'atempo=2.0,atempo={factor/2.0:.6f}'
                    else:
                        # atempo max 100x tapi quality turun
                        atempo_filter = f'atempo=2.0,atempo=2.0,atempo={factor/4.0:.6f}'
                    filters.append(
                        f'[0:a]atrim=start={m_entry["start"]:.3f}:end={m_entry["end"]:.3f},'
                        f'asetpts=PTS-STARTPTS,{atempo_filter}[cue_a{seg_idx}];'
                    )
                    concat_a_inputs.append(f'[cue_a{seg_idx}]')
                seg_idx += 1

        last_end = m_entry['end']

    # 3. Tail gap (setelah cue terakhir sampai akhir MP4)
    if last_end < mp4_duration - 0.05:
        gap_dur = mp4_duration - last_end
        # Gap tail di SRT baru: ambil dari newEnd cue terakhir sampai newDurationSec
        # Untuk simplicity, pakai gap asli (factor 1.0)
        filters.append(
            f'[0:v]trim=start={last_end:.3f}:end={mp4_duration:.3f},'
            f'setpts=PTS-STARTPTS,setpts=1.0*PTS[tail_v{seg_idx}];'
        )
        concat_v_inputs.append(f'[tail_v{seg_idx}]')

        if has_audio_ori:
            filters.append(
                f'[0:a]atrim=start={last_end:.3f}:end={mp4_duration:.3f},'
                f'asetpts=PTS-STARTPTS[tail_a{seg_idx}];'
            )
            concat_a_inputs.append(f'[tail_a{seg_idx}]')
        seg_idx += 1

    # Concat semua segment
    n_v = len(concat_v_inputs)
    n_a = len(concat_a_inputs)

    concat_v_str = ''.join(concat_v_inputs) + f'concat=n={n_v}:v=1:a=0[outv];'
    filters.append(concat_v_str)

    if has_audio_ori and n_a > 0:
        concat_a_str = ''.join(concat_a_inputs) + f'concat=n={n_a}:v=0:a=1[outa_sfx];'
        filters.append(concat_a_str)

    # Mix: audio Jawa (input 2) + SFX (outa_sfx) dengan ducking
    # Ducking: SFX volume turun saat audio Jawa bicara
    # Gunakan sidechaincompress untuk auto-ducking
    if has_audio_ori and n_a > 0:
        # sidechaincompress: SFX (outa_sfx) di-duck oleh audio Jawa (1:a dari input 2)
        # level SFX turun -X dB saat audio Jawa aktif
        # Tapi karena SFX sudah di-retim per cue, kita pakai simple volume adjustment
        ducking_factor = 10 ** (-ducking_db / 20)  # convert dB to amplitude
        filters.append(
            f'[outa_sfx]volume={ducking_factor:.4f}[outa_sfx_ducked];'
        )
        # Mix: audio Jawa (input 1:a) + SFX ducked
        filters.append(
            f'[1:a][outa_sfx_ducked]amix=inputs=2:duration=first:dropout_transition=0:normalize=0[outa];'
        )

    filter_complex = ''.join(filters)
    return filter_complex


# ============================================================
# Main
# ============================================================

def main():
    parser = argparse.ArgumentParser(
        description='Retime MP4 Mandarin → SRT Jawa (SRT = Ground of Truth) + preserve SFX',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Contoh basic (audio Jawa + audio ori di-duck):
  python3 retime-video-v2.py \\
    --mp4 mandarin.mp4 \\
    --srt-mandarin original.srt \\
    --srt-jawa subs-jawa-new.srt \\
    --audio-jawa audio-jawa.wav \\
    --output mp4-jawa.mp4

Contah advanced (Demucs SFX separation):
  python3 retime-video-v2.py \\
    --mp4 mandarin.mp4 \\
    --srt-mandarin original.srt \\
    --srt-jawa subs-jawa-new.srt \\
    --audio-jawa audio-jawa.wav \\
    --output mp4-jawa.mp4 \\
    --separate-sfx \\
    --sfx-ducking 0.3
        """,
    )
    parser.add_argument('--mp4', required=True, help='Path ke MP4 Mandarin asli')
    parser.add_argument('--srt-mandarin', required=True, help='Path ke SRT Mandarin asli')
    parser.add_argument('--srt-jawa', required=True, help='Path ke SRT Jawa baru (output Fase 2)')
    parser.add_argument('--audio-jawa', required=True, help='Path ke audio Jawa WAV (output Fase 2)')
    parser.add_argument('--output', required=True, help='Path output MP4 final')
    parser.add_argument('--ffmpeg', help='Path kustom ke ffmpeg')
    parser.add_argument('--ffprobe', help='Path kustom ke ffprobe')
    parser.add_argument('--separate-sfx', action='store_true',
                        help='Pakai Demucs untuk separate SFX dari vocals Mandarin (lebih bersih)')
    parser.add_argument('--sfx-ducking', type=float, default=12.0,
                        help='Volume SFX di-duck (dB). Default 12 (SFX -12dB saat audio Jawa)')
    parser.add_argument('--no-sfx', action='store_true',
                        help='Buang audio ori total (hanya audio Jawa)')
    parser.add_argument('--dry-run', action='store_true', help='Print command tanpa eksekusi')
    parser.add_argument('--keep-temp', action='store_true', help='Keep temp files untuk debugging')
    parser.add_argument('--preset', default='medium',
                        choices=['ultrafast', 'superfast', 'veryfast', 'fast', 'medium', 'slow', 'slower'],
                        help='FFmpeg x264 preset (default: medium). fast=lebih cepat, kualitas sedikit turun. slow=lebih bagus, lebih lama.')
    args = parser.parse_args()

    # Validate inputs
    for label, path in [
        ('MP4', args.mp4),
        ('SRT Mandarin', args.srt_mandarin),
        ('SRT Jawa', args.srt_jawa),
        ('Audio Jawa', args.audio_jawa),
    ]:
        if not os.path.isfile(path):
            print(f'Error: {label} tidak ditemukan: {path}', file=sys.stderr)
            sys.exit(1)

    # Find ffmpeg/ffprobe
    try:
        ffmpeg = find_ffmpeg(args.ffmpeg)
        ffprobe = find_ffprobe(args.ffprobe)
    except FileNotFoundError as e:
        print(f'Error: {e}', file=sys.stderr)
        sys.exit(1)

    print(f'ffmpeg: {ffmpeg}')
    print(f'ffprobe: {ffprobe}')

    # Parse SRT
    with open(args.srt_mandarin, 'r', encoding='utf-8') as f:
        mandarin_entries = parse_srt(f.read())
    with open(args.srt_jawa, 'r', encoding='utf-8') as f:
        jawa_entries = parse_srt(f.read())

    print(f'\nSRT Mandarin: {len(mandarin_entries)} cues')
    print(f'SRT Jawa: {len(jawa_entries)} cues')

    if not mandarin_entries or not jawa_entries:
        print('Error: SRT kosong', file=sys.stderr)
        sys.exit(1)

    # Dapatkan info MP4
    mp4_duration = get_mp4_duration(ffprobe, args.mp4)
    audio_streams = get_mp4_audio_streams(ffprobe, args.mp4)
    has_audio_ori = (not args.no_sfx) and len(audio_streams) > 0

    print(f'MP4 durasi: {format_time_ffmpeg(mp4_duration)}')
    print(f'Audio streams di MP4: {len(audio_streams)}')
    print(f'SFX preserve: {"YA" if has_audio_ori else "TIDAK"}')
    if has_audio_ori:
        print(f'SFX ducking: -{args.sfx_ducking} dB')

    # Mode SFX separation dengan Demucs (optional)
    work_dir = tempfile.mkdtemp(prefix='retime-v2-')
    print(f'\nWork directory: {work_dir}')

    sfx_audio_path = None
    if args.separate_sfx:
        demucs_result = separate_sfx_with_demucs(args.mp4, work_dir)
        if demucs_result:
            sfx_audio_path = demucs_result['no_vocals']
            # Override: pakai no_vocals.wav dari Demucs sebagai audio SFX
            # (akan di-mix di ffmpeg command terpisah)
            print(f'  → Pakai SFX dari Demucs: {sfx_audio_path}')

    # Bangun filter complex
    if sfx_audio_path:
        # Mode Demucs: input 0 = MP4 (video only), input 1 = audio Jawa, input 2 = SFX dari Demucs
        # SFX dari Demucs TIDAK perlu di-retim (sudah full timeline MP4 asli)
        # Tapi harus di-stretch ke timeline Jawa baru...
        # Untuk simplicity: pakai simple volume ducking saja
        # TODO: implement retim untuk SFX Demucs (complex, butuh 2-pass)
        print('  → Mode Demucs: implementasi sederhana (SFX volume ducking tanpa retim)')
        print('  → Note: SFX mungkin tidak perfect sync dengan video retimed')
        # Build command dengan SFX dari Demucs (tidak di-retim, simple volume)
        cmd = build_command_with_demucs_sfx(
            ffmpeg, args, ffmpeg_input_mp4=args.mp4,
            audio_jawa=args.audio_jawa,
            sfx_path=sfx_audio_path,
            mandarin_entries=mandarin_entries,
            jawa_entries=jawa_entries,
            mp4_duration=mp4_duration,
            ducking_db=args.sfx_ducking,
        )
    else:
        # Mode basic: audio ori MP4 di-duck saat audio Jawa bicara
        filter_complex = build_filter_complex(
            mandarin_entries, jawa_entries, mp4_duration,
            has_audio_ori=has_audio_ori, ducking_db=args.sfx_ducking,
        )

        # Build command — kalau filter complex panjang (>100KB), pakai file approach
        # untuk hindari "Argument list too long" error di macOS (limit ~256KB)
        filter_size = len(filter_complex)
        use_filter_file = filter_size > 100_000  # 100KB threshold

        cmd = [
            ffmpeg,
            '-y',
            '-i', args.mp4,           # input 0: MP4 (video + audio ori)
            '-i', args.audio_jawa,    # input 1: audio Jawa
        ]

        if use_filter_file:
            # Write filter_complex ke file temp, FFmpeg baca dari file
            filter_file = os.path.join(work_dir, 'filter_complex.txt')
            with open(filter_file, 'w') as f:
                f.write(filter_complex)
            print(f'\n  → Filter complex: {filter_size/1024:.1f} KB (besar), pakai file approach')
            print(f'  → Filter file: {filter_file}')
            cmd.extend(['-filter_complex_script_filename', filter_file])
        else:
            cmd.extend(['-filter_complex', filter_complex])

        cmd.extend(['-map', '[outv]'])
        if has_audio_ori:
            cmd.extend(['-map', '[outa]'])
        else:
            cmd.extend(['-map', '1:a'])  # audio Jawa only
        cmd.extend([
            '-c:v', 'libx264',
            '-preset', args.preset,
            '-crf', '23',
            '-c:a', 'aac',
            '-b:a', '192k',
            '-shortest',
            args.output,
        ])

    print('\n=== FFmpeg command ===')
    print(' '.join(cmd[:5]) + ' \\')
    for arg in cmd[5:]:
        if arg.startswith('[') or arg.startswith('-'):
            print(f'  {arg} \\')
        else:
            print(f'  {arg}')
    print('=== End command ===\n')

    if args.dry_run:
        print('Dry run — command tidak dieksekusi.')
        if not args.keep_temp:
            shutil.rmtree(work_dir, ignore_errors=True)
        return

    # Eksekusi
    print('Memulai retim video (mungkin butuh beberapa menit untuk file besar)...')
    try:
        result = subprocess.run(cmd)
        if result.returncode != 0:
            print(f'\nffmpeg gagal dengan code {result.returncode}', file=sys.stderr)
            sys.exit(1)
    except KeyboardInterrupt:
        print('\nDibatalkan user.')
        sys.exit(130)

    # Verifikasi output
    if os.path.isfile(args.output):
        out_size = os.path.getsize(args.output)
        out_duration = get_mp4_duration(ffprobe, args.output)
        print(f'\n✓ Output: {args.output}')
        print(f'  Size: {out_size / 1024 / 1024:.1f} MB')
        print(f'  Duration: {format_time_ffmpeg(out_duration)}')
        print(f'\n  → Buka di DaVinci Resolve untuk editing final.')
        print(f'  → Audio: Jawa + SFX backsound (di-duck -{args.sfx_ducking}dB)')
    else:
        print(f'Error: output tidak ditemukan: {args.output}', file=sys.stderr)
        sys.exit(1)

    # Cleanup
    if not args.keep_temp:
        shutil.rmtree(work_dir, ignore_errors=True)
        print(f'  (Temp files dihapus. Pakai --keep-temp untuk debugging.)')


def build_command_with_demucs_sfx(
    ffmpeg, args, ffmpeg_input_mp4, audio_jawa, sfx_path,
    mandarin_entries, jawa_entries, mp4_duration, ducking_db,
):
    """
    Build ffmpeg command untuk mode Demucs SFX separation.
    Input 0: MP4 (video + audio ori)
    Input 1: Audio Jawa
    Input 2: SFX dari Demucs (no_vocals.wav)

    Strategi: video di-retim per cue (seperti mode basic), TAPI audio SFX dari Demucs
    TIDAK di-retim (timeline SFX = timeline MP4 asli).
    Untuk simplicity, SFX dari Demucs di-volume ducking saja (tidak sync perfect).
    """
    filters = []
    concat_v_inputs = []
    seg_idx = 0

    jawa_by_idx = {i: e for i, e in enumerate(jawa_entries)}
    last_end = 0.0

    for i, m_entry in enumerate(mandarin_entries):
        # Gap sebelum cue
        gap_mandarin_dur = m_entry['start'] - last_end
        if gap_mandarin_dur > 0.01:
            if i in jawa_by_idx and (i - 1) in jawa_by_idx:
                jawa_gap_dur = jawa_by_idx[i]['start'] - jawa_by_idx[i - 1]['end']
            elif i == 0 and i in jawa_by_idx:
                jawa_gap_dur = jawa_by_idx[i]['start']
            else:
                jawa_gap_dur = gap_mandarin_dur
            jawa_gap_dur = max(0.05, jawa_gap_dur)
            factor = jawa_gap_dur / gap_mandarin_dur
            filters.append(
                f'[0:v]trim=start={last_end:.3f}:end={m_entry["start"]:.3f},'
                f'setpts=PTS-STARTPTS,setpts={1/factor:.6f}*PTS[gap_v{seg_idx}];'
            )
            concat_v_inputs.append(f'[gap_v{seg_idx}]')
            seg_idx += 1

        # Cue
        if i in jawa_by_idx:
            j_entry = jawa_by_idx[i]
            cue_mandarin_dur = m_entry['end'] - m_entry['start']
            cue_jawa_dur = j_entry['end'] - j_entry['start']
            if cue_mandarin_dur > 0.01 and cue_jawa_dur > 0.01:
                factor = cue_jawa_dur / cue_mandarin_dur
                filters.append(
                    f'[0:v]trim=start={m_entry["start"]:.3f}:end={m_entry["end"]:.3f},'
                    f'setpts=PTS-STARTPTS,setpts={1/factor:.6f}*PTS[cue_v{seg_idx}];'
                )
                concat_v_inputs.append(f'[cue_v{seg_idx}]')
                seg_idx += 1

        last_end = m_entry['end']

    # Tail
    if last_end < mp4_duration - 0.05:
        filters.append(
            f'[0:v]trim=start={last_end:.3f}:end={mp4_duration:.3f},'
            f'setpts=PTS-STARTPTS,setpts=1.0*PTS[tail_v{seg_idx}];'
        )
        concat_v_inputs.append(f'[tail_v{seg_idx}]')
        seg_idx += 1

    # Concat video
    n_v = len(concat_v_inputs)
    filters.append(''.join(concat_v_inputs) + f'concat=n={n_v}:v=1:a=0[outv];')

    # Audio: SFX dari Demucs di-volume ducking + audio Jawa di-mix
    # SFX dari Demucs tidak di-retim (timeline asli MP4), tapi audio Jawa sync dengan video retimed
    # Issue: timeline SFX = timeline MP4 asli (5m 39s), tapi video retimed = 7m+
    # Solusi: stretch SFX dengan atempo agar match video duration baru
    # atempo factor = new_duration / old_duration
    new_duration = max(jawa_by_idx[i]['end'] for i in jawa_by_idx if i in jawa_by_idx) if jawa_by_idx else mp4_duration
    sfx_stretch_factor = new_duration / mp4_duration
    ducking_factor = 10 ** (-ducking_db / 20)

    filters.append(f'[2:a]atempo={sfx_stretch_factor:.6f},volume={ducking_factor:.4f}[sfx_ducked];')
    filters.append(f'[1:a][sfx_ducked]amix=inputs=2:duration=first:dropout_transition=0:normalize=0[outa];')

    filter_complex = ''.join(filters)

    return [
        ffmpeg,
        '-y',
        '-i', ffmpeg_input_mp4,
        '-i', audio_jawa,
        '-i', sfx_path,
        '-filter_complex', filter_complex,
        '-map', '[outv]',
        '-map', '[outa]',
        '-c:v', 'libx264',
        '-preset', args.preset,
        '-crf', '23',
        '-c:a', 'aac',
        '-b:a', '192k',
        '-shortest',
        args.output,
    ]


if __name__ == '__main__':
    main()
