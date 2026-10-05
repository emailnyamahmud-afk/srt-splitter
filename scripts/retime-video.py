#!/usr/bin/env python3
"""
retime-video.py — Retime MP4 ori supaya match SRT dub (SRT dub = ground truth)

Strategi: Two-pass rendering
  Pass 1: Render per-segment jadi file MP4 kecil (parallel workers)
    - Cue: trim + setpts (slow-mo) + re-encode
    - Gap: trim + stream copy (instant)
  Pass 2: Concat semua segments + add audio dub (stream copy, ~3 detik)

Standar nama file:
  --mp4          mp4-ori-{name}.mp4       (video asli)
  --srt-original srt-{lang}-original.srt  (SRT source, timing Mandarin = "penjara")
  --srt-dub      srt-{lang}-dub.srt       (SRT dub dari web, timing natural)
  --audio-dub    audio-{lang}-dub.wav     (audio dub dari web, natural)
  --output       mp4-{lang}-final.mp4     (output final)

  {lang} = id, jw, mn, su, bali, etc.

Usage (sub-ID test 5 menit):
  python3 retime-video.py \\
    --mp4 mp4-ori-test-5min.mp4 \\
    --srt-original srt-id-original.srt \\
    --srt-dub srt-id-dub.srt \\
    --audio-dub audio-id-dub.wav \\
    --output mp4-id-final.mp4 \\
    --encoder h264_videotoolbox --workers 4

Requirements: ffmpeg, ffprobe, Python 3.8+
"""

import argparse
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from concurrent.futures import ProcessPoolExecutor, as_completed


# ============================================================
# SRT parsing
# ============================================================

def parse_srt(content: str):
    """Parse SRT string → list of {index, start, end, text}."""
    normalized = content.replace('\r\n', '\n').replace('\r', '\n').strip()
    if not normalized:
        return []
    entries = []
    for block in re.split(r'\n\s*\n', normalized):
        lines = [l for l in block.split('\n') if l.strip()]
        if not lines:
            continue
        time_idx = next((i for i, l in enumerate(lines) if '-->' in l), -1)
        if time_idx == -1:
            continue
        m = re.match(
            r'(\d{1,2}:\d{2}:\d{2}[,.]\d{1,3})\s*-->\s*(\d{1,2}:\d{2}:\d{2}[,.]\d{1,3})',
            lines[time_idx],
        )
        if not m:
            continue
        entries.append({
            'index': len(entries) + 1,
            'start': parse_time(m.group(1)),
            'end': parse_time(m.group(2)),
            'text': '\n'.join(lines[time_idx + 1:]),
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
# FFmpeg helpers
# ============================================================

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


def get_mp4_duration(ffprobe: str, mp4_path: str) -> float:
    """Probe MP4 duration. Raise RuntimeError kalau gagal."""
    result = subprocess.run([
        ffprobe, '-v', 'error', '-show_entries', 'format=duration',
        '-of', 'default=noprint_wrappers=1:nokey=1', mp4_path,
    ], capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f'ffprobe gagal baca durasi: {result.stderr.strip()[:200]}')
    dur_str = result.stdout.strip()
    if not dur_str:
        raise RuntimeError(f'ffprobe return durasi kosong untuk: {mp4_path}')
    try:
        return float(dur_str)
    except ValueError:
        raise RuntimeError(f'ffprobe return durasi invalid "{dur_str}" untuk: {mp4_path}')


def get_mp4_audio_streams(ffprobe: str, mp4_path: str) -> list:
    """Probe MP4 audio streams."""
    result = subprocess.run([
        ffprobe, '-v', 'error', '-show_entries', 'stream=index,codec_type',
        '-of', 'json', mp4_path,
    ], capture_output=True, text=True)
    if result.returncode != 0:
        return []
    import json
    data = json.loads(result.stdout)
    return [s for s in data.get('streams', []) if s.get('codec_type') == 'audio']


# ============================================================
# Build segment tasks (Pass 1 plan)
# ============================================================

def build_segment_tasks(ori_entries, dub_entries, mp4_duration):
    """
    Bangun list segment tasks untuk Pass 1.
    Pairing by index: dub[i] ↔ ori[i]. Stop di cue yang mp4_start >= mp4_duration.

    Returns list of dict dengan keys:
      type, index, mp4_start, mp4_end, target_duration, factor, cumulative_offset
    """
    tasks = []
    dub_by_idx = {i: e for i, e in enumerate(dub_entries)}
    last_end = 0.0
    seg_idx = 0
    cumulative_offset = 0.0

    for i, m_entry in enumerate(ori_entries):
        if m_entry['start'] >= mp4_duration:
            print(f'  → Stop di cue {i} (mp4_start={m_entry["start"]:.2f}s ≥ mp4_duration={mp4_duration:.2f}s)')
            break

        # Gap sebelum cue ini (jika ada)
        gap_mp4_dur = m_entry['start'] - last_end
        if gap_mp4_dur > 0.01:
            if i in dub_by_idx and (i - 1) in dub_by_idx:
                dub_gap_dur = dub_by_idx[i]['start'] - dub_by_idx[i - 1]['end']
            elif i == 0 and i in dub_by_idx:
                dub_gap_dur = dub_by_idx[i]['start']
            else:
                dub_gap_dur = gap_mp4_dur

            dub_gap_dur = max(0.05, dub_gap_dur)
            gap_end = min(m_entry['start'], mp4_duration)
            tasks.append({
                'type': 'gap', 'index': seg_idx,
                'mp4_start': last_end, 'mp4_end': gap_end,
                'target_duration': dub_gap_dur,
                'factor': dub_gap_dur / gap_mp4_dur,
                'cumulative_offset': cumulative_offset,
            })
            cumulative_offset += dub_gap_dur
            seg_idx += 1

        # Cue itu sendiri (hanya kalau mp4_end <= mp4_duration)
        if i in dub_by_idx and m_entry['end'] <= mp4_duration:
            j_entry = dub_by_idx[i]
            cue_mp4_dur = m_entry['end'] - m_entry['start']
            cue_dub_dur = j_entry['end'] - j_entry['start']
            if cue_mp4_dur > 0.01 and cue_dub_dur > 0.01:
                tasks.append({
                    'type': 'cue', 'index': seg_idx,
                    'mp4_start': m_entry['start'], 'mp4_end': m_entry['end'],
                    'target_duration': cue_dub_dur,
                    'factor': cue_dub_dur / cue_mp4_dur,
                    'cumulative_offset': cumulative_offset,
                })
                cumulative_offset += cue_dub_dur
                seg_idx += 1

        last_end = min(m_entry['end'], mp4_duration)

    # Tail gap (post-roll video setelah cue terakhir)
    if last_end < mp4_duration - 0.05:
        tail_dur = mp4_duration - last_end
        tasks.append({
            'type': 'tail', 'index': seg_idx,
            'mp4_start': last_end, 'mp4_end': mp4_duration,
            'target_duration': tail_dur, 'factor': 1.0,
            'cumulative_offset': cumulative_offset,
        })

    return tasks


# ============================================================
# Render 1 segment (worker function untuk parallel Pass 1)
# ============================================================

def render_segment(task, mp4_path, segments_dir, ffmpeg_path, preset, encoder):
    """Render 1 segment jadi file MP4 kecil. Dipanggil oleh ProcessPoolExecutor."""
    seg_idx = task['index']
    output_file = os.path.join(segments_dir, f'seg_{seg_idx:05d}.mp4')

    mp4_start = task['mp4_start']
    mp4_dur = task['mp4_end'] - mp4_start
    factor = task['factor']
    cumulative_offset = task['cumulative_offset']

    # Resume support: skip kalau segment sudah ada (> 100 bytes)
    if os.path.isfile(output_file) and os.path.getsize(output_file) > 100:
        return {'index': seg_idx, 'status': 'skipped'}

    # Encoder params + hwaccel
    # FIX bug #12: -hwaccel videotoolbox hanya untuk h264_videotoolbox (Mac M1/M2 hardware).
    # Untuk libx264 (software), JANGAN pakai -hwaccel videotoolbox (gagal di Linux/non-Mac).
    if encoder == 'h264_videotoolbox':
        hwaccel_args = ['-hwaccel', 'videotoolbox']
        enc_params = ['-c:v', 'h264_videotoolbox', '-b:v', '5M',
                      '-realtime', '0', '-bf', '0', '-profile:v', 'high']
    else:
        hwaccel_args = []  # software decode untuk libx264
        enc_params = ['-c:v', 'libx264', '-preset', preset, '-crf', '23',
                      '-bf', '0', '-profile:v', 'high']

    use_stream_copy = 0.95 <= factor <= 1.05 and task['type'] in ('gap', 'tail')

    # FIX bug #6 (fast seek): -ss SEBELUM -i, bukan sesudah → O(n) bukan O(n²)
    # FIX bug #7 (correct -t): pakai mp4_dur (input durasi), BUKAN target_dur (output)
    # FIX bug #27 (KRITIKAL): -t EXACT mp4_dur, NO margin → output = mp4_dur × factor = target_dur
    #   Sebelumnya -t {mp4_dur + 0.1} → drift 0.1×factor per segment = ~35s untuk 233 seg
    if use_stream_copy:
        cmd = [
            ffmpeg_path, '-y',
            *hwaccel_args,
            '-ss', f'{mp4_start:.3f}',
            '-i', mp4_path,
            '-t', f'{mp4_dur:.3f}',
            '-c:v', 'copy', '-an',
            '-output_ts_offset', f'{cumulative_offset:.6f}',
            '-fflags', '+genpts',
            output_file,
        ]
    else:
        # Re-encode: setpts × factor (slow-mo) + fps=30 SETELAH setpts (CFR output)
        #
        # FIX bug #28 (test #18, 5 Okt): stop-motion "patah-patah" di mayoritas cue.
        # Sebelumnya: 'fps=30,setpts=...' — fps=30 SEBELUM setpts = no-op untuk source 30fps.
        # setpts × factor bikin output VFR (20fps untuk factor 1.5x, 10fps untuk 3x).
        # Pass 2 concat stream copy → frame rate berubah-ubah di tengah video → VLC/DaVinci
        # tidak handle → "patah-patah".
        #
        # FIX: fps=30 SETELAH setpts. Setiap segment CFR 30fps, frame duplikasi smooth.
        # VoiceStudio pattern: out_fps resample di akhir (post-concat).
        # Kita pakai per-segment karena Pass 2 stream copy (tidak ada filter).
        #
        # tpad GAGAL di h264_videotoolbox (PTS overflow, test #16) → jangan pakai tpad.
        cmd = [
            ffmpeg_path, '-y',
            *hwaccel_args,
            '-ss', f'{mp4_start:.3f}',
            '-i', mp4_path,
            '-t', f'{mp4_dur:.3f}',
            '-vf', f'setpts=(PTS-STARTPTS)*{factor:.6f},fps=30',
            *enc_params,
            '-output_ts_offset', f'{cumulative_offset:.6f}',
            '-an', '-fflags', '+genpts',
            output_file,
        ]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        if result.returncode != 0:
            # FIX audit: stderr FFmpeg sering cuma print "Error opening output file"
            # tanpa root cause. Cari baris dengan "Error", "Device", "Cannot", "Failed" juga.
            stderr_lines = result.stderr.split('\n')
            err_lines = [l for l in stderr_lines
                         if any(k in l.lower() for k in
                                ['error', 'invalid', 'not found', 'no such',
                                 'cannot', 'device', 'failed', 'no device'])]
            err = err_lines[0] if err_lines else stderr_lines[-5:]
            # Print stderr LENGKAP untuk debugging (last 500 chars)
            stderr_tail = result.stderr[-500:] if result.stderr else ''
            return {'index': seg_idx, 'status': 'failed',
                    'error': f'code={result.returncode} | {str(err)[:200]}',
                    'stderr_tail': stderr_tail}
        return {'index': seg_idx, 'status': 'ok'}
    except subprocess.TimeoutExpired:
        return {'index': seg_idx, 'status': 'failed', 'error': 'timeout (300s)'}
    except Exception as e:
        return {'index': seg_idx, 'status': 'failed', 'error': str(e)}


# ============================================================
# Pass 1: Render semua segments (parallel)
# ============================================================

def render_all_segments(tasks, mp4_path, segments_dir, ffmpeg_path, preset, workers, encoder):
    """Render semua segments secara parallel. Allow up to 5% failure."""
    total = len(tasks)
    print(f'\n=== Pass 1: Render {total} segments (parallel {workers} workers) ===')
    completed = 0
    failed = 0
    start_time = time.time()

    with ProcessPoolExecutor(max_workers=workers) as executor:
        futures = {
            executor.submit(render_segment, task, mp4_path, segments_dir,
                             ffmpeg_path, preset, encoder): task
            for task in tasks
        }
        for future in as_completed(futures):
            try:
                result = future.result()
                completed += 1
                if result['status'] == 'failed':
                    failed += 1
                    print(f'  ✗ Segment {result["index"]} gagal: {result.get("error", "unknown")[:100]}')
                    # Print stderr tail untuk debugging root cause (mis. "No device" untuk videotoolbox)
                    if result.get('stderr_tail'):
                        print(f'    stderr: {result["stderr_tail"][-200:].strip()}')
                if completed % 50 == 0 or completed == total:
                    elapsed = time.time() - start_time
                    rate = completed / elapsed if elapsed > 0 else 0
                    eta = (total - completed) / rate if rate > 0 else 0
                    print(f'  → {completed}/{total} segments ({100*completed/total:.1f}%) — '
                          f'elapsed {elapsed:.0f}s, ETA {eta:.0f}s, failed {failed}')
            except Exception as e:
                failed += 1
                print(f'  ✗ Task exception: {e}')

    print(f'\n=== Pass 1 selesai ===')
    print(f'  Total: {total} | Sukses: {total - failed} | Gagal: {failed} | Waktu: {time.time() - start_time:.0f}s')

    if failed > total * 0.05:
        print(f'  ❌ Gagal {failed}/{total} ({100*failed/total:.1f}%) > 5% threshold')
        return False
    if failed > 0:
        print(f'  ⚠ {failed} segment gagal ({100*failed/total:.1f}%), tapi < 5% → lanjut ke Pass 2')
    return True


# ============================================================
# Pass 2: Concat semua segments + add audio dub
# ============================================================

def concat_segments(tasks, segments_dir, audio_dub, output, ffmpeg_path):
    """Concat semua segment files + mix audio dub. Stream copy video, AAC audio."""
    print(f'\n=== Pass 2: Concat segments + mix audio ===')

    # Build concat list — skip segment yang gagal (< 100 bytes)
    MIN_SIZE = 100  # FIX test #15: threshold 1000 terlalu tinggi, segment pendek < 1KB di-skip
    concat_list = os.path.join(segments_dir, 'concat_list.txt')
    included = 0
    skipped = 0
    with open(concat_list, 'w') as f:
        for task in tasks:
            seg_file = os.path.join(segments_dir, f'seg_{task["index"]:05d}.mp4')
            if os.path.isfile(seg_file) and os.path.getsize(seg_file) > MIN_SIZE:
                f.write(f"file '{seg_file}'\n")
                included += 1
            else:
                skipped += 1

    print(f'  → Concat list: {concat_list} ({included} files, {skipped} skipped)')

    # Pass 2: stream copy video + AAC audio dub
    # Timestamp sudah akumulatif dari Pass 1 (output_ts_offset) → concat seamless
    cmd = [
        ffmpeg_path, '-y',
        '-f', 'concat', '-safe', '0', '-i', concat_list,
        '-i', audio_dub,
        '-map', '0:v', '-map', '1:a',
        '-c:v', 'copy',
        '-c:a', 'aac', '-b:a', '192k',
        '-movflags', '+faststart',
        '-timecode', '00:00:00:00',
        '-shortest',
        output,
    ]

    print(f'  → Concat + mix audio...')
    result = subprocess.run(cmd)
    if result.returncode != 0:
        print(f'\n✗ Pass 2 gagal dengan code {result.returncode}')
        return False
    print(f'  ✓ Pass 2 selesai')
    return True


# ============================================================
# Main
# ============================================================

def main():
    parser = argparse.ArgumentParser(
        description='Retime MP4 ori supaya match SRT dub (Two-Pass, SRT dub = ground truth)',
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument('--mp4', required=True,
                        help='MP4 ori (video asli). Standar: mp4-ori-{name}.mp4')
    parser.add_argument('--srt-original', required=True,
                        help='SRT ori (source subtitle, timing "penjara"). Standar: srt-{lang}-original.srt')
    parser.add_argument('--srt-dub', required=True,
                        help='SRT dub (hasil dub dari web). Standar: srt-{lang}-dub.srt')
    parser.add_argument('--audio-dub', required=True,
                        help='Audio dub WAV (hasil dub dari web). Standar: audio-{lang}-dub.wav')
    parser.add_argument('--output', required=True,
                        help='Output MP4 final. Standar: mp4-{lang}-final.mp4')
    parser.add_argument('--ffmpeg', help='Path kustom ke ffmpeg')
    parser.add_argument('--ffprobe', help='Path kustom ke ffprobe')
    parser.add_argument('--dry-run', action='store_true', help='Print plan tanpa eksekusi')
    parser.add_argument('--keep-temp', action='store_true', help='Keep temp files untuk debugging')
    parser.add_argument('--preset', default='fast',
                        choices=['ultrafast', 'superfast', 'veryfast', 'fast', 'medium', 'slow', 'slower'],
                        help='FFmpeg x264 preset (default: fast)')
    parser.add_argument('--workers', type=int, default=4,
                        help='Parallel FFmpeg processes (default 4, max 8 untuk M1/M2)')
    parser.add_argument('--encoder', default='libx264',
                        choices=['libx264', 'h264_videotoolbox'],
                        help='Video encoder: libx264 (software) atau h264_videotoolbox (hardware M1/M2)')
    args = parser.parse_args()

    # Validate inputs
    for label, path in [('MP4 ori', args.mp4), ('SRT ori', args.srt_original),
                       ('SRT dub', args.srt_dub), ('Audio dub', args.audio_dub)]:
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

    # Parse SRT
    with open(args.srt_original, 'r', encoding='utf-8') as f:
        ori_entries = parse_srt(f.read())
    with open(args.srt_dub, 'r', encoding='utf-8') as f:
        dub_entries = parse_srt(f.read())

    print(f'\nSRT ori: {len(ori_entries)} cues ({args.srt_original})')
    print(f'SRT dub: {len(dub_entries)} cues ({args.srt_dub})')

    if not ori_entries or not dub_entries:
        print('Error: SRT kosong', file=sys.stderr)
        sys.exit(1)

    # Get MP4 info
    mp4_duration = get_mp4_duration(ffprobe, args.mp4)
    audio_streams = get_mp4_audio_streams(ffprobe, args.mp4)
    print(f'MP4 durasi: {format_time_ffmpeg(mp4_duration)}')
    print(f'MP4 audio streams: {len(audio_streams)}')
    print(f'Audio dub: {"YA (audio ori MP4 di-drop, hanya audio dub)" if audio_streams else "TIDAK"}')
    print(f'Encoder: {args.encoder} | Preset: {args.preset} | Workers: {args.workers}')

    # Build segment tasks
    tasks = build_segment_tasks(ori_entries, dub_entries, mp4_duration)
    print(f'\nTotal segments: {len(tasks)}')
    print(f'  Cue: {sum(1 for t in tasks if t["type"] == "cue")}')
    print(f'  Gap: {sum(1 for t in tasks if t["type"] == "gap")}')
    print(f'  Tail: {sum(1 for t in tasks if t["type"] == "tail")}')
    reencode_count = sum(1 for t in tasks
                         if not (0.95 <= t['factor'] <= 1.05 and t['type'] in ('gap', 'tail')))
    print(f'  Re-encode (slow-mo/fast): {reencode_count}')
    print(f'  Stream copy (instant): {len(tasks) - reencode_count}')

    if args.dry_run:
        print('\n=== DRY RUN ===')
        print(f'Plan: render {len(tasks)} segments di {args.workers} workers paralel')
        print(f'Output: {args.output}')
        print(f'\nSample tasks (first 5):')
        for t in tasks[:5]:
            print(f'  {t["type"]:5s} seg_{t["index"]:05d} | mp4 {t["mp4_start"]:.2f}-{t["mp4_end"]:.2f} '
                  f'({t["mp4_end"]-t["mp4_start"]:.2f}s) → target {t["target_duration"]:.2f}s '
                  f'(factor {t["factor"]:.2f}x)')
        print(f'\nDry run — tidak eksekusi.')
        return

    # Setup work directory
    work_dir = tempfile.mkdtemp(prefix='retime-v3-')
    segments_dir = os.path.join(work_dir, 'segments')
    os.makedirs(segments_dir, exist_ok=True)
    print(f'\nWork directory: {work_dir}')
    print(f'Segments directory: {segments_dir}')

    # Pass 1: Render semua segments
    success = render_all_segments(tasks, args.mp4, segments_dir, ffmpeg,
                                  args.preset, args.workers, args.encoder)
    if not success:
        print('\n❌ Pass 1 gagal. Beberapa segment gagal di-render.')
        print('Coba jalankan ulang (resume support — segment yang sudah ada akan di-skip).')
        if not args.keep_temp:
            print(f'Temp files: {work_dir} (pakai --keep-temp untuk inspect)')
        sys.exit(1)

    # Pass 2: Concat + mix audio
    success = concat_segments(tasks, segments_dir, args.audio_dub, args.output, ffmpeg)
    if not success:
        print('\n❌ Pass 2 gagal.')
        if not args.keep_temp:
            shutil.rmtree(work_dir, ignore_errors=True)
        sys.exit(1)

    # Verify output
    if os.path.isfile(args.output):
        out_size = os.path.getsize(args.output)
        out_duration = get_mp4_duration(ffprobe, args.output)
        print(f'\n✅ Output: {args.output}')
        print(f'   Size: {out_size / 1024 / 1024:.1f} MB')
        print(f'   Duration: {format_time_ffmpeg(out_duration)}')
        print(f'\n   → Buka di DaVinci Resolve untuk editing final.')
    else:
        print(f'\n❌ Output tidak ditemukan: {args.output}', file=sys.stderr)
        if not args.keep_temp:
            shutil.rmtree(work_dir, ignore_errors=True)
        sys.exit(1)

    # Cleanup
    if not args.keep_temp:
        shutil.rmtree(work_dir, ignore_errors=True)
        print(f'   (Temp files dihapus. Pakai --keep-temp untuk debugging.)')


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
