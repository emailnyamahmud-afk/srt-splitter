#!/usr/bin/env python3
"""
retime-video.py — Retime MP4 Mandarin supaya timing-nya match SRT Jawa baru.

Fase 3 dari workflow dubbing Mandarin → Jawa:
  Fase 1: MP4 Mandarin + SRT Mandarin (sumber)
  Fase 2: Translate ke Jawa → Rapikan → Generate audio Jawa natural + SRT baru (web app)
  Fase 3: [SCRIPT INI] Retime MP4 Mandarin supaya match SRT Jawa → mix audio Jawa
  Fase 4: Edit final di DaVinci Resolve

Algoritma (Cut + Slow + Concat):
  1. Parse SRT Mandarin (timing asli) dan SRT Jawa (timing baru)
  2. Pair cue Mandarin ↔ Jawa berdasarkan index
  3. Untuk setiap cue:
     - Cut video dari cue Mandarin start ke end (durasi asli)
     - Slow-mo/fast-forward ke durasi cue Jawa (factor = jawa_dur / mandarin_dur)
     - Save sebagai segment_video_N.mp4 (video only, audio dibuang)
  4. Untuk setiap gap antar cue:
     - Cut gap dari MP4 Mandarin
     - Retime ke durasi gap Jawa (factor = jawa_gap / mandarin_gap)
     - Save sebagai segment_gap_N.mp4
  5. Concat semua segment jadi satu video stream
  6. Mix audio Jawa (WAV) ke video final
  7. Output: mp4-jawa.mp4

Usage:
  python retime-video.py \
    --mp4 mandarin.mp4 \
    --srt-mandarin original.srt \
    --srt-jawa subs-jawa-new.srt \
    --audio-jawa audio-jawa.wav \
    --output mp4-jawa.mp4

Requirements:
  - ffmpeg (coba auto-detect di PATH, atau specify via --ffmpeg)
  - Python 3.8+
  - Tidak perlu library tambahan — pakai subprocess + tempfile

Catatan:
  - Kalau factor > 1 (slow-mo): video melambat
  - Kalau factor < 1 (fast-forward): video cepat
  - Kalau factor ~1: tidak diubah (copy stream)
  - Kalau cue Jawa lebih pendek dari 0.05s → skip (terlalu pendek)
  - Kalau gap Jawa lebih pendek dari 0.05s → skip gap (langsung concat cue)
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
# SRT parsing (sederhana, tidak butuh library)
# ============================================================

def parse_srt(content: str):
    """Parse SRT string jadi list of {index, start, end, text} (start/end in seconds)."""
    normalized = content.replace('\r\n', '\n').replace('\r', '\n').strip()
    if not normalized:
        return []
    blocks = re.split(r'\n\s*\n', normalized)
    entries = []
    for block in blocks:
        lines = [l for l in block.split('\n') if l.strip()]
        if not lines:
            continue
        # Find time line
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


def format_time(seconds: float) -> str:
    """Format seconds → 'HH:MM:SS.mmm' (untuk ffmpeg)."""
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
    # Coba lokasi umum
    for loc in ['/usr/local/bin/ffmpeg', '/usr/bin/ffmpeg', '/opt/homebrew/bin/ffmpeg',
                '/Applications/ffmpeg', 'C:\\ffmpeg\\bin\\ffmpeg.exe']:
        if os.path.isfile(loc):
            return loc
    raise FileNotFoundError(
        'ffmpeg tidak ditemukan di PATH. Install ffmpeg atau specify via --ffmpeg.'
    )


def run_ffprobe(ffprobe: str, args: list) -> str:
    """Run ffprobe dan return stdout string."""
    cmd = [ffprobe] + args
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f'ffprobe gagal: {result.stderr}')
    return result.stdout.strip()


def get_mp4_duration(ffprobe: str, mp4_path: str) -> float:
    """Dapatkan durasi MP4 dalam detik."""
    out = run_ffprobe(ffprobe, [
        '-v', 'error',
        '-show_entries', 'format=duration',
        '-of', 'default=noprint_wrappers=1:nokey=1',
        mp4_path,
    ])
    return float(out)


# ============================================================
# Main: bangun ffmpeg filter complex
# ============================================================

def build_retime_filter(mandarin_entries, jawa_entries, mp4_duration):
    """
    Bangun ffmpeg filter_complex untuk retim video.
    
    Strategi: gunakan setpts + trip segments dengan trim dan concat.
    Setiap cue Mandarin di-trim, lalu di-setpts untuk slow-mo/fast-forward ke durasi Jawa.
    Setiap gap Mandarin di-trim, lalu di-setpts ke durasi gap Jawa.
    """
    filters = []
    concat_inputs = []
    
    # Map jawa entries by index (asumsi 1-to-1, kalau ada cue Jawa kosong → skip)
    # Jawa entries mungkin lebih sedikit dari Mandarin kalau ada cue kosong yang di-skip
    jawa_by_idx = {i: e for i, e in enumerate(jawa_entries)}
    
    last_end = 0.0  # posisi cursor di timeline Mandarin
    seg_idx = 0
    
    for i, m_entry in enumerate(mandarin_entries):
        # 1. Gap sebelum cue ini (dari last_end ke m_entry.start)
        gap_mandarin_dur = m_entry['start'] - last_end
        if gap_mandarin_dur > 0.01:
            # Cari gap duration di timeline Jawa (kalau ada cue Jawa i-1)
            if i > 0 and (i - 1) in jawa_by_idx:
                prev_j = jawa_by_idx[i - 1]
                # Gap Jawa = jawa[i].start - jawa[i-1].end
                if i in jawa_by_idx:
                    jawa_gap_dur = jawa_by_idx[i]['start'] - prev_j['end']
                else:
                    # Cue Jawa i tidak ada (kosong) → pakai gap sampai cue Jawa next yang ada
                    next_j = None
                    for k in range(i + 1, len(jawa_entries) + len(mandarin_entries)):
                        if k in jawa_by_idx:
                            next_j = jawa_by_idx[k]
                            break
                    if next_j:
                        jawa_gap_dur = next_j['start'] - prev_j['end']
                    else:
                        jawa_gap_dur = gap_mandarin_dur  # fallback
            else:
                # Cue pertama → gap dari 0 ke cue[0].start
                if i in jawa_by_idx:
                    jawa_gap_dur = jawa_by_idx[i]['start']
                else:
                    jawa_gap_dur = gap_mandarin_dur
            
            jawa_gap_dur = max(0.05, jawa_gap_dur)  # minimum 50ms
            factor = jawa_gap_dur / gap_mandarin_dur
            
            # Trim gap dari MP4
            filters.append(
                f'[0:v]trim=start={last_end:.3f}:end={m_entry["start"]:.3f},setpts=PTS-STARTPTS+0/TB,'
                f'setpts={1/factor}*PTS[gap_v{seg_idx}];'
            )
            concat_inputs.append(f'[gap_v{seg_idx}]')
            seg_idx += 1
        
        # 2. Cue itu sendiri
        if i in jawa_by_idx:
            j_entry = jawa_by_idx[i]
            cue_mandarin_dur = m_entry['end'] - m_entry['start']
            cue_jawa_dur = j_entry['end'] - j_entry['start']
            
            if cue_mandarin_dur > 0.01 and cue_jawa_dur > 0.01:
                factor = cue_jawa_dur / cue_mandarin_dur
                # Trim cue Mandarin, setpts untuk retim
                filters.append(
                    f'[0:v]trim=start={m_entry["start"]:.3f}:end={m_entry["end"]:.3f},'
                    f'setpts=PTS-STARTPTS,setpts={1/factor}*PTS[cue_v{seg_idx}];'
                )
                concat_inputs.append(f'[cue_v{seg_idx}]')
                seg_idx += 1
        
        last_end = m_entry['end']
    
    # 3. Gap setelah cue terakhir sampai akhir MP4
    if last_end < mp4_duration - 0.05:
        gap_dur = mp4_duration - last_end
        # Gap Jawa = sama dengan gap Mandarin (atau sedikit lebih panjang sesuai offset total)
        # Untuk simplicity, pakai gap asli
        factor = 1.0
        filters.append(
            f'[0:v]trim=start={last_end:.3f}:end={mp4_duration:.3f},'
            f'setpts=PTS-STARTPTS,setpts={1/factor}*PTS[tail_v{seg_idx}];'
        )
        concat_inputs.append(f'[tail_v{seg_idx}]')
        seg_idx += 1
    
    # Concat semua segment
    concat_str = ''.join(concat_inputs) + f'concat=n={seg_idx}:v=1:a=0[outv]'
    filter_complex = ''.join(filters) + concat_str
    return filter_complex


def main():
    parser = argparse.ArgumentParser(
        description='Retime MP4 Mandarin supaya match SRT Jawa baru (Dubbing Fase 3)',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Contoh:
  python retime-video.py \\
    --mp4 mandarin.mp4 \\
    --srt-mandarin original.srt \\
    --srt-jawa subs-jawa-new.srt \\
    --audio-jawa audio-jawa.wav \\
    --output mp4-jawa.mp4
        """,
    )
    parser.add_argument('--mp4', required=True, help='Path ke MP4 Mandarin asli')
    parser.add_argument('--srt-mandarin', required=True, help='Path ke SRT Mandarin asli')
    parser.add_argument('--srt-jawa', required=True, help='Path ke SRT Jawa baru (output Fase 2)')
    parser.add_argument('--audio-jawa', required=True, help='Path ke audio Jawa WAV (output Fase 2)')
    parser.add_argument('--output', required=True, help='Path output MP4 final')
    parser.add_argument('--ffmpeg', help='Path kustom ke ffmpeg (auto-detect kalau kosong)')
    parser.add_argument('--ffprobe', help='Path kustom ke ffprobe (auto-detect kalau kosong)')
    parser.add_argument('--dry-run', action='store_true', help='Print command tanpa eksekusi')
    parser.add_argument('--keep-temp', action='store_true', help='Keep temp files untuk debugging')
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
        ffprobe = find_ffprobe(args.ffprobe or ffmpeg.replace('ffmpeg', 'ffprobe'))
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
    
    print(f'SRT Mandarin: {len(mandarin_entries)} cues')
    print(f'SRT Jawa: {len(jawa_entries)} cues')
    
    if not mandarin_entries or not jawa_entries:
        print('Error: SRT kosong', file=sys.stderr)
        sys.exit(1)
    
    # Dapatkan durasi MP4
    mp4_duration = get_mp4_duration(ffprobe, args.mp4)
    print(f'MP4 durasi: {format_time(mp4_duration)}')
    
    # Bangun filter complex
    filter_complex = build_retime_filter(mandarin_entries, jawa_entries, mp4_duration)
    
    # Bangun command ffmpeg
    cmd = [
        ffmpeg,
        '-y',  # overwrite output
        '-i', args.mp4,
        '-i', args.audio_jawa,
        '-filter_complex', filter_complex,
        '-map', '[outv]',
        '-map', '1:a',
        '-c:v', 'libx264',
        '-preset', 'medium',  # balance speed vs quality
        '-crf', '23',  # quality (lower = better, 18-28 reasonable)
        '-c:a', 'aac',
        '-b:a', '192k',
        '-shortest',
        args.output,
    ]
    
    print('\n=== FFmpeg command ===')
    print(' '.join(cmd))
    print('=== End command ===\n')
    
    if args.dry_run:
        print('Dry run — command tidak dieksekusi.')
        return
    
    # Eksekusi
    print('Memulai retim video (mungkin butuh beberapa menit untuk file besar)...')
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    if result.returncode != 0:
        print('ffmpeg gagal:', file=sys.stderr)
        print(result.stderr, file=sys.stderr)
        sys.exit(1)
    
    # Verifikasi output
    if os.path.isfile(args.output):
        out_size = os.path.getsize(args.output)
        out_duration = get_mp4_duration(ffprobe, args.output)
        print(f'\n✓ Output: {args.output}')
        print(f'  Size: {out_size / 1024 / 1024:.1f} MB')
        print(f'  Duration: {format_time(out_duration)}')
        print(f'\n  → Buka di DaVinci Resolve untuk editing final.')
    else:
        print(f'Error: output tidak ditemukan: {args.output}', file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
