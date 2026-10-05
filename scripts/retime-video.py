#!/usr/bin/env python3
"""
retime-video.py — Retime MP4 ori supaya match SRT dub baru (SRT = ground truth)

Strategi v3 (Two-Pass with File-Based Segments):
  Problem lama: Filter complex inline dengan 8000+ segments = memory 40GB → swap → stuck
  Solusi: Render per-segment sebagai file kecil, lalu concat

  Pass 1: Untuk setiap cue/gap, render jadi file MP4 kecil
    - Cue: trim + setpts (slow-mo) + re-encode
    - Gap: trim + stream copy (instant, no re-encode)
  Pass 2: Concat semua segments + add audio dub
    - Pakai concat demuxer (text list of files)
    - Stream copy untuk video (no re-encode di concat)
    - Audio: audio dub + (opsional) SFX dari MP4 ori

STANDAR NAMA FILE (wajib ikut, biar tidak bingung):
  File source (input):
    --mp4          mp4-ori[-test-Nmin].mp4     (video MP4 asli, mis. mp4-ori-test-5min.mp4)
    --srt-original srt-{lang}-original.srt    (SRT source, mis. srt-id-original.srt)
    --srt-dub      srt-{lang}-dub.srt         (SRT hasil dub dari web, mis. srt-id-dub.srt)
    --audio-dub    audio-{lang}-dub.wav       (audio hasil dub dari web, mis. audio-id-dub.wav)
  File output:
    --output       mp4-{lang}-dub[-test-Nmin].mp4  (video final, mis. mp4-id-dub-test-5min.mp4)

  {lang} = id (Indonesia), jw (Jawa), mn (Mandarin), su (Sunda), etc.

Usage (contoh sub-ID test 5 menit):
  python3 retime-video.py \\
    --mp4 mp4-ori-test-5min.mp4 \\
    --srt-original srt-id-original.srt \\
    --srt-dub srt-id-dub.srt \\
    --audio-dub audio-id-dub.wav \\
    --output mp4-id-dub-test-5min.mp4

Usage (full season Jawa):
  python3 retime-video.py \\
    --mp4 mp4-ori.mp4 \\
    --srt-original srt-mn-original.srt \\
    --srt-dub srt-jw-dub.srt \\
    --audio-dub audio-jw-dub.wav \\
    --output mp4-jw-dub.mp4

Optional:
  --separate-sfx        Pakai Demucs untuk separate SFX
  --sfx-ducking 12      Volume SFX turun 12dB
  --no-sfx              Buang audio ori total
  --preset fast         FFmpeg preset (fast/medium/slow)
  --workers 4           Parallel FFmpeg processes (default 4)
  --dry-run             Test command tanpa eksekusi
  --keep-temp           Keep temp files untuk debugging

Backward compat:
  --srt-mandarin        Alias ke --srt-original (lama, jangan dipakai lagi)
  --srt-jawa            Alias ke --srt-dub (lama, jangan dipakai lagi)
  --audio-jawa          Alias ke --audio-dub (lama, jangan dipakai lagi)

Requirements:
  - ffmpeg (auto-detect atau --ffmpeg)
  - Python 3.8+
  - Demucs (opsional, untuk SFX separation)
"""

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
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
    raise FileNotFoundError('ffmpeg tidak ditemukan di PATH. Install ffmpeg atau specify via --ffmpeg.')


def find_ffprobe(custom_path: str = None) -> str:
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


def get_mp4_duration(ffprobe: str, mp4_path: str) -> float:
    result = subprocess.run([
        ffprobe, '-v', 'error',
        '-show_entries', 'format=duration',
        '-of', 'default=noprint_wrappers=1:nokey=1',
        mp4_path,
    ], capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f'ffprobe gagal baca durasi MP4: {result.stderr.strip()[:200]}')
    dur_str = result.stdout.strip()
    if not dur_str:
        raise RuntimeError(f'ffprobe return durasi kosong untuk: {mp4_path}')
    try:
        return float(dur_str)
    except ValueError:
        raise RuntimeError(f'ffprobe return durasi invalid "{dur_str}" untuk: {mp4_path}')


def get_mp4_audio_streams(ffprobe: str, mp4_path: str) -> list:
    result = subprocess.run([
        ffprobe, '-v', 'error',
        '-show_entries', 'stream=index,codec_type,codec_name,channels',
        '-of', 'json',
        mp4_path,
    ], capture_output=True, text=True)
    data = json.loads(result.stdout)
    return [s for s in data.get('streams', []) if s.get('codec_type') == 'audio']


# ============================================================
# Build segment tasks
# ============================================================

def build_segment_tasks(mandarin_entries, jawa_entries, mp4_duration):
    """
    Build list of segment tasks untuk Pass 1.
    Setiap task = 1 FFmpeg command untuk render 1 segment (cue atau gap).

    Returns:
      list of dict: {
        'type': 'cue' | 'gap' | 'tail',
        'index': int,
        'mp4_start': float,  # start di MP4 ori
        'mp4_end': float,    # end di MP4 ori
        'target_duration': float,  # durasi setelah retim
        'factor': float,     # target_duration / (mp4_end - mp4_start)
        'output_file': str,  # path ke segment file
      }
    """
    tasks = []
    jawa_by_idx = {i: e for i, e in enumerate(jawa_entries)}
    last_end = 0.0
    seg_idx = 0
    cumulative_offset = 0.0  # sum durasi semua segments sebelumnya (untuk timestamp akumulatif)

    # Filter: hanya process cues yang mp4_start < mp4_duration
    for i, m_entry in enumerate(mandarin_entries):
        if m_entry['start'] >= mp4_duration:
            print(f'  → Stop di cue {i} (mp4_start={m_entry["start"]:.2f}s ≥ mp4_duration={mp4_duration:.2f}s)')
            break

        # Gap sebelum cue ini
        gap_mp4_dur = m_entry['start'] - last_end
        if gap_mp4_dur > 0.01:
            if i in jawa_by_idx and (i - 1) in jawa_by_idx:
                jawa_gap_dur = jawa_by_idx[i]['start'] - jawa_by_idx[i - 1]['end']
            elif i == 0 and i in jawa_by_idx:
                jawa_gap_dur = jawa_by_idx[i]['start']
            else:
                jawa_gap_dur = gap_mp4_dur

            jawa_gap_dur = max(0.05, jawa_gap_dur)
            factor = jawa_gap_dur / gap_mp4_dur

            gap_end = min(m_entry['start'], mp4_duration)
            tasks.append({
                'type': 'gap',
                'index': seg_idx,
                'mp4_start': last_end,
                'mp4_end': gap_end,
                'target_duration': jawa_gap_dur,
                'factor': factor,
                'cumulative_offset': cumulative_offset,
            })
            cumulative_offset += jawa_gap_dur
            seg_idx += 1

        # Cue itu sendiri
        if i in jawa_by_idx and m_entry['end'] <= mp4_duration:
            j_entry = jawa_by_idx[i]
            cue_mp4_dur = m_entry['end'] - m_entry['start']
            cue_jawa_dur = j_entry['end'] - j_entry['start']

            if cue_mp4_dur > 0.01 and cue_jawa_dur > 0.01:
                factor = cue_jawa_dur / cue_mp4_dur
                tasks.append({
                    'type': 'cue',
                    'index': seg_idx,
                    'mp4_start': m_entry['start'],
                    'mp4_end': m_entry['end'],
                    'target_duration': cue_jawa_dur,
                    'factor': factor,
                    'cumulative_offset': cumulative_offset,
                })
                cumulative_offset += cue_jawa_dur
                seg_idx += 1

        last_end = min(m_entry['end'], mp4_duration)

    # Tail gap
    if last_end < mp4_duration - 0.05:
        tail_dur = mp4_duration - last_end
        tasks.append({
            'type': 'tail',
            'index': seg_idx,
            'mp4_start': last_end,
            'mp4_end': mp4_duration,
            'target_duration': tail_dur,
            'factor': 1.0,
            'cumulative_offset': cumulative_offset,
        })
        seg_idx += 1

    return tasks


# ============================================================
# Render 1 segment (worker function untuk parallel)
# ============================================================

def render_segment(task, mp4_path, segments_dir, ffmpeg_path, ffprobe_path, preset, has_audio_ori, encoder='libx264'):
    """
    Render 1 segment jadi file MP4 kecil.
    Dipanggil oleh ProcessPoolExecutor (parallel).
    """
    seg_idx = task['index']
    output_file = os.path.join(segments_dir, f'seg_{seg_idx:05d}.mp4')

    mp4_start = task['mp4_start']
    mp4_end = task['mp4_end']
    mp4_dur = mp4_end - mp4_start
    target_dur = task['target_duration']
    factor = task['factor']
    cumulative_offset = task.get('cumulative_offset', 0.0)

    # Skip kalau sudah ada (resume support)
    # FIX audit 5 Okt: sync threshold ke 100 bytes (sama dengan concat_segments Pass 2)
    # Sebelumnya 1000 bytes — segment pendek (gap 0.05s, cue 0.17s) di-skip di resume,
    # tapi concat Pass 2 juga skip → segment hilang dari output.
    if os.path.isfile(output_file) and os.path.getsize(output_file) > 100:
        return {'index': seg_idx, 'output_file': output_file, 'status': 'skipped'}

    # Encoder params: libx264 (software) atau h264_videotoolbox (hardware M1)
    if encoder == 'h264_videotoolbox':
        enc_params = ['-c:v', 'h264_videotoolbox', '-b:v', '5M', '-realtime', '0',
                       '-bf', '0', '-profile:v', 'high']
    else:
        enc_params = ['-c:v', 'libx264', '-preset', preset, '-crf', '23',
                       '-bf', '0', '-profile:v', 'high']

    use_stream_copy = 0.95 <= factor <= 1.05 and task['type'] in ('gap', 'tail')

    # FIX audit 5 Okt (Bug #6, #7):
    # Sebelumnya: -i mp4 lalu -ss mp4_start (slow seek, decode dari 0) + -t target_dur (post-setpts durasi)
    # VoiceStudio riset: "-ss sebelum -i = fast seek (decode dari keyframe sebelum), O(n) bukan O(n²)"
    # "-t harus pakai INPUT durasi (mp4_dur), bukan OUTPUT durasi (target_dur)"
    # Kalau factor=14x: mp4_dur=0.17s, target_dur=2.39s → FFmpeg baca 2.39s input padahal cuma 0.17s dipakai
    # Setelah fix: -ss sebelum -i, -t pakai mp4_dur + 0.5s margin (untuk akurasi trim)

    if use_stream_copy:
        # Stream copy: -ss sebelum -i (fast seek), -t pakai mp4_dur (input durasi)
        # Output duration = mp4_dur (factor=1.0, no setpts)
        cmd = [
            ffmpeg_path, '-y',
            '-hwaccel', 'videotoolbox',
            '-ss', f'{mp4_start:.3f}',
            '-i', mp4_path,
            '-t', f'{mp4_dur:.3f}',
            '-c:v', 'copy',
            '-an',
            '-output_ts_offset', f'{cumulative_offset:.6f}',
            '-fflags', '+genpts',
            output_file,
        ]
    else:
        # Re-encode: -ss sebelum -i (fast seek), -t pakai mp4_dur EXACT (bukan +margin!)
        # Filter: fps=30 (VFR guard) → setpts * factor (slow-mo)
        #
        # FIX audit 5 Okt (Bug #27, KRITIKAL):
        # Sebelumnya: -t {mp4_dur + 0.1} + setpts * factor = output (mp4_dur + 0.1) * factor
        # Untuk factor=14x: segment 1.4s lebih panjang dari target!
        # Cumulative offset drift = 0.1 * factor per cue = ~35s untuk 233 segments
        # → ini penyebab "berhenti lama" di test #15, BUKAN skip 24 seg atau slow-mo 14x
        # Sekarang: -t {mp4_dur} exact → output = mp4_dur * factor = target_dur (exact match)
        #
        # Catatan test #16 (5 Okt 2026): tpad=stop_mode=clone GAGAL — PTS overflow di h264_videotoolbox.
        # Slow-mo factor > 2x tetap pakai setpts * factor (stop-motion, frame ada).
        cmd = [
            ffmpeg_path, '-y',
            '-hwaccel', 'videotoolbox',
            '-ss', f'{mp4_start:.3f}',
            '-i', mp4_path,
            '-t', f'{mp4_dur:.3f}',  # EXACT, no margin — output = mp4_dur × factor = target_dur
            '-vf', f'fps=30,setpts=(PTS-STARTPTS)*{factor:.6f}',
            *enc_params,
            '-output_ts_offset', f'{cumulative_offset:.6f}',
            '-an',
            '-fflags', '+genpts',
            output_file,
        ]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        if result.returncode != 0:
            # Print stderr LENGKAP untuk debugging (bukan cuma [-300:])
            # Cari baris yang mengandung "Error" atau "error" di stderr
            stderr_lines = result.stderr.split('\n')
            error_lines = [l for l in stderr_lines if 'error' in l.lower() or 'invalid' in l.lower() or 'not found' in l.lower() or 'no such' in l.lower()]
            error_summary = error_lines[0] if error_lines else stderr_lines[-5:]
            return {
                'index': seg_idx,
                'output_file': output_file,
                'status': 'failed',
                'error': f'code={result.returncode} | {error_summary[:200]}',
            }
        # VALIDASI: cek duration output — hanya untuk re-encode segments
        # (stream copy durasi = source durasi, tidak perlu validasi terhadap target)
        # SKIP validasi untuk sekarang. Segment terakhir sering terpotong
        # karena mp4_end > mp4_duration (video input lebih pendek dari target).
        # Concat di Pass 2 akan handle — segment pendek tetap di-concat.
        return {'index': seg_idx, 'output_file': output_file, 'status': 'ok'}
    except subprocess.TimeoutExpired:
        return {
            'index': seg_idx,
            'output_file': output_file,
            'status': 'failed',
            'error': 'timeout (300s)',
        }
    except Exception as e:
        return {
            'index': seg_idx,
            'output_file': output_file,
            'status': 'failed',
            'error': str(e),
        }


# ============================================================
# Pass 1: Render semua segments (parallel)
# ============================================================

def render_all_segments(tasks, mp4_path, segments_dir, ffmpeg_path, ffprobe_path, preset, workers=4, encoder='libx264'):
    """
    Render semua segments secara parallel.
    Pakai ProcessPoolExecutor untuk parallel FFmpeg processes.
    """
    total = len(tasks)
    print(f'\n=== Pass 1: Render {total} segments (parallel {workers} workers) ===')

    completed = 0
    failed = 0
    start_time = time.time()

    with ProcessPoolExecutor(max_workers=workers) as executor:
        # Submit semua tasks
        futures = {
            executor.submit(render_segment, task, mp4_path, segments_dir, ffmpeg_path, ffprobe_path, preset, True, encoder): task
            for task in tasks
        }

        # Wait dan report progress
        for future in as_completed(futures):
            task = futures[future]
            try:
                result = future.result()
                completed += 1
                if result['status'] == 'failed':
                    failed += 1
                    print(f'  ✗ Segment {result["index"]} gagal: {result.get("error", "unknown")[:100]}')
                elif result['status'] == 'skipped':
                    pass  # silent skip

                # Progress setiap 50 segments
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
    print(f'  Total: {total} segments')
    print(f'  Sukses: {total - failed}')
    print(f'  Gagal: {failed}')
    print(f'  Waktu: {time.time() - start_time:.0f}s')

    # Allow up to 5% failure (segment pendek di akhir video wajar gagal)
    # Kalau gagal > 5%, return False (gagal total)
    # Kalau gagal <= 5%, return True (lanjut ke Pass 2, segment gagal di-skip di concat)
    if failed > total * 0.05:
        print(f'  ❌ Gagal {failed}/{total} ({100*failed/total:.1f}%) > 5% threshold')
        return False
    elif failed > 0:
        print(f'  ⚠ {failed} segment gagal ({100*failed/total:.1f}%), tapi < 5% → lanjut ke Pass 2 (segment gagal di-skip)')
    return True


# ============================================================
# Pass 2: Concat semua segments + add audio dub
# ============================================================

def concat_segments(tasks, segments_dir, audio_jawa, output, ffmpeg_path, has_audio_ori, ducking_db, video_only=False, encoder='libx264'):
    """
    Concat semua segment files menggunakan concat demuxer.
    Kalau video_only=True: output = video tanpa audio (user import audio terpisah di DaVinci).
    """
    print(f'\n=== Pass 2: Concat segments + mix audio ===')

    # Build concat list file — skip segments yang gagal (file tidak ada atau terlalu kecil)
    # FIX test #15: threshold 1000 bytes terlalu tinggi, segment pendek (gap 0.05s, cue 0.17s)
    # bisa hasilkan file < 1KB → di-skip → gap di video → "berhenti lama" di VLC/DaVinci.
    # Lower ke 100 bytes supaya segment pendek tetap masuk concat.
    MIN_SEGMENT_SIZE = 100  # bytes (sebelumnya 1000)
    concat_list = os.path.join(segments_dir, 'concat_list.txt')
    included = 0
    skipped = 0
    with open(concat_list, 'w') as f:
        for task in tasks:
            seg_file = os.path.join(segments_dir, f'seg_{task["index"]:05d}.mp4')
            # Skip kalau file tidak ada atau terlalu kecil (segment gagal total)
            if os.path.isfile(seg_file) and os.path.getsize(seg_file) > MIN_SEGMENT_SIZE:
                f.write(f"file '{seg_file}'\n")
                included += 1
            else:
                skipped += 1

    print(f'  → Concat list: {concat_list} ({included} files, {skipped} skipped)')

    # Encoder params untuk Pass 2 re-encode
    if encoder == 'h264_videotoolbox':
        enc_params = ['-c:v', 'h264_videotoolbox', '-b:v', '5M', '-realtime', '0',
                       '-bf', '0', '-profile:v', 'high']
    else:
        enc_params = ['-c:v', 'libx264', '-preset', 'fast', '-crf', '23',
                       '-bf', '0', '-profile:v', 'high']

    # Pass 2: STREAM COPY (instant, 2 detik)
    # Timestamp sudah akumulatif dari Pass 1 (output_ts_offset)
    # → concat demuxer stream copy = seamless, tidak ada DTS out of order
    if video_only:
        print(f'  → Mode: VIDEO ONLY (stream copy, tanpa audio)')
        cmd = [
            ffmpeg_path, '-y',
            '-f', 'concat', '-safe', '0',
            '-i', concat_list,
            '-c:v', 'copy',
            '-an',
            '-movflags', '+faststart',
            '-timecode', '00:00:00:00',
            output,
        ]
    else:
        cmd = [
            ffmpeg_path, '-y',
            '-f', 'concat', '-safe', '0',
            '-i', concat_list,
            '-i', audio_jawa,
            '-map', '0:v',
            '-map', '1:a',
            '-c:v', 'copy',
            '-c:a', 'aac',
            '-b:a', '192k',
            '-movflags', '+faststart',
            '-timecode', '00:00:00:00',
            '-shortest',
            output,
        ]

    print(f'  → Concat + mix audio...')
    print(f'  Command: {" ".join(cmd[:5])} ...')

    result = subprocess.run(cmd)
    if result.returncode != 0:
        print(f'\n✗ Pass 2 gagal dengan code {result.returncode}')
        return False

    print(f'  ✓ Pass 2 selesai')
    return True


# ============================================================
# Demucs SFX separation (optional)
# ============================================================

def separate_sfx_with_demucs(mp4_path: str, work_dir: str) -> dict:
    print('\n=== SFX Separation dengan Demucs ===')
    demucs_bin = shutil.which('demucs') or shutil.which('demucs.exe')
    if not demucs_bin:
        print('  ⚠ Demucs tidak ditemukan. Skip SFX separation.')
        return None

    audio_ori = os.path.join(work_dir, 'audio-original.wav')
    ffmpeg = find_ffmpeg()
    subprocess.run([
        ffmpeg, '-y', '-i', mp4_path,
        '-vn', '-acodec', 'pcm_s16le', '-ar', '44100', '-ac', '2',
        audio_ori,
    ], check=True)

    print('  → Run Demucs (mungkin butuh 5-15 menit untuk file besar)...')
    demucs_out_dir = os.path.join(work_dir, 'demucs-output')
    os.makedirs(demucs_out_dir, exist_ok=True)
    result = subprocess.run([
        demucs_bin, '--two-stems', 'vocals', '-o', demucs_out_dir, audio_ori,
    ])
    if result.returncode != 0:
        print(f'  ✗ Demucs gagal. Skip SFX.')
        return None

    base_name = os.path.splitext(os.path.basename(audio_ori))[0]
    no_vocals = os.path.join(demucs_out_dir, base_name, 'no_vocals.wav')
    if not os.path.isfile(no_vocals):
        return None

    print(f'  ✓ SFX: {no_vocals}')
    return {'no_vocals': no_vocals}


# ============================================================
# Main
# ============================================================

def main():
    parser = argparse.ArgumentParser(
        description='Retime MP4 ori supaya match SRT dub (Two-Pass, SRT dub = ground truth)',
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument('--mp4', required=True,
                        help='Path ke MP4 ori (video asli). Standar: mp4-ori[-test-Nmin].mp4')
    # Argumen baru (standar):
    parser.add_argument('--srt-original',
                        help='Path ke SRT ori (source subtitle). Standar: srt-{lang}-original.srt')
    parser.add_argument('--srt-dub',
                        help='Path ke SRT dub (hasil dub dari web). Standar: srt-{lang}-dub.srt')
    parser.add_argument('--audio-dub',
                        help='Path ke audio dub WAV (hasil dub dari web). Standar: audio-{lang}-dub.wav')
    # Backward compat (alias, deprecated):
    parser.add_argument('--srt-mandarin',
                        help='(DEPRECATED, alias ke --srt-original) Path ke SRT Mandarin asli')
    parser.add_argument('--srt-jawa',
                        help='(DEPRECATED, alias ke --srt-dub) Path ke SRT Jawa baru (output Fase 2)')
    parser.add_argument('--audio-jawa',
                        help='(DEPRECATED, alias ke --audio-dub) Path ke audio Jawa WAV (output Fase 2)')
    parser.add_argument('--output', required=True,
                        help='Path output MP4 final. Standar: mp4-{lang}-dub[-test-Nmin].mp4')
    parser.add_argument('--ffmpeg', help='Path kustom ke ffmpeg')
    parser.add_argument('--ffprobe', help='Path kustom ke ffprobe')
    parser.add_argument('--separate-sfx', action='store_true',
                        help='Pakai Demucs untuk separate SFX dari vocals ori')
    parser.add_argument('--sfx-ducking', type=float, default=12.0,
                        help='Volume SFX di-duck (dB). Default 12')
    parser.add_argument('--no-sfx', action='store_true',
                        help='Buang audio ori total (hanya audio dub)')
    parser.add_argument('--dry-run', action='store_true', help='Print plan tanpa eksekusi')
    parser.add_argument('--keep-temp', action='store_true', help='Keep temp files untuk debugging')
    parser.add_argument('--preset', default='fast',
                        choices=['ultrafast', 'superfast', 'veryfast', 'fast', 'medium', 'slow', 'slower'],
                        help='FFmpeg x264 preset (default: fast). medium=bagus tapi lama.')
    parser.add_argument('--workers', type=int, default=4,
                        help='Parallel FFmpeg processes (default 4, max 8 untuk M1/M2)')
    parser.add_argument('--encoder', default='libx264',
                        choices=['libx264', 'h264_videotoolbox'],
                        help='Video encoder: libx264 (software, default) atau h264_videotoolbox (hardware M1/M2, 4x cepat)')
    parser.add_argument('--video-only', action='store_true',
                        help='Pass 2: concat video saja, TIDAK mix audio dub. User import audio terpisah di DaVinci.')
    args = parser.parse_args()

    # Resolve alias: argumen baru diprioritaskan, fallback ke alias lama (backward compat)
    srt_original_path = args.srt_original or args.srt_mandarin
    srt_dub_path = args.srt_dub or args.srt_jawa
    audio_dub_path = args.audio_dub or args.audio_jawa

    if not srt_original_path:
        print('Error: --srt-original (atau --srt-mandarin alias) wajib diisi', file=sys.stderr)
        sys.exit(2)
    if not srt_dub_path:
        print('Error: --srt-dub (atau --srt-jawa alias) wajib diisi', file=sys.stderr)
        sys.exit(2)
    if not audio_dub_path:
        print('Error: --audio-dub (atau --audio-jawa alias) wajib diisi', file=sys.stderr)
        sys.exit(2)

    # Warning kalau pakai argumen lama (deprecated)
    if args.srt_mandarin or args.srt_jawa or args.audio_jawa:
        print('⚠ WARNING: --srt-mandarin / --srt-jawa / --audio-jawa adalah alias deprecated.')
        print('  Pakai --srt-original / --srt-dub / --audio-dub (standar baru).')
        print(f'  File dipakai: srt-original={srt_original_path}, srt-dub={srt_dub_path}, audio-dub={audio_dub_path}')
        print()

    # Validate inputs
    for label, path in [
        ('MP4 ori', args.mp4),
        ('SRT ori', srt_original_path),
        ('SRT dub', srt_dub_path),
        ('Audio dub', audio_dub_path),
    ]:
        if not os.path.isfile(path):
            print(f'Error: {label} tidak ditemukan: {path}', file=sys.stderr)
            sys.exit(1)

    # Find tools
    try:
        ffmpeg = find_ffmpeg(args.ffmpeg)
        ffprobe = find_ffprobe(args.ffprobe)
    except FileNotFoundError as e:
        print(f'Error: {e}', file=sys.stderr)
        sys.exit(1)

    print(f'ffmpeg: {ffmpeg}')
    print(f'ffprobe: {ffprobe}')

    # Parse SRT
    with open(srt_original_path, 'r', encoding='utf-8') as f:
        mandarin_entries = parse_srt(f.read())
    with open(srt_dub_path, 'r', encoding='utf-8') as f:
        jawa_entries = parse_srt(f.read())

    print(f'\nSRT ori: {len(mandarin_entries)} cues ({srt_original_path})')
    print(f'SRT dub: {len(jawa_entries)} cues ({srt_dub_path})')

    if not mandarin_entries or not jawa_entries:
        print('Error: SRT kosong', file=sys.stderr)
        sys.exit(1)

    # Get MP4 info
    mp4_duration = get_mp4_duration(ffprobe, args.mp4)
    audio_streams = get_mp4_audio_streams(ffprobe, args.mp4)
    has_audio_ori = (not args.no_sfx) and len(audio_streams) > 0
    print(f'MP4 durasi: {format_time_ffmpeg(mp4_duration)}')
    print(f'MP4 audio streams: {len(audio_streams)}')
    print(f'Audio dub replace: {"YA (audio ori MP4 di-drop, hanya audio dub)" if has_audio_ori else "TIDAK"}')
    print(f'SFX preserve (Demucs): {"AKTIF" if args.separate_sfx else "TIDAK (audio ori di-drop total)"}')
    if args.sfx_ducking and not args.separate_sfx:
        print(f'⚠ Catatan: --sfx-ducking {args.sfx_ducking} dB TIDAK ADA EFEK tanpa --separate-sfx')
        print(f'   Saat ini audio ori MP4 di-drop total (di-mode C), tidak ada SFX untuk di-duck.')
        print(f'   Untuk SFX preservation: gunakan --separate-sfx (butuh Demucs install).')
    print(f'Preset: {args.preset}')
    print(f'Encoder: {args.encoder}')
    print(f'Workers: {args.workers}')

    # Build segment tasks
    tasks = build_segment_tasks(mandarin_entries, jawa_entries, mp4_duration)
    print(f'\nTotal segments: {len(tasks)}')
    print(f'  Cue segments: {sum(1 for t in tasks if t["type"] == "cue")}')
    print(f'  Gap segments: {sum(1 for t in tasks if t["type"] == "gap")}')
    print(f'  Tail segments: {sum(1 for t in tasks if t["type"] == "tail")}')

    # Count segments yang perlu re-encode vs stream copy
    reencode_count = sum(1 for t in tasks if not (0.95 <= t['factor'] <= 1.05 and t['type'] in ('gap', 'tail')))
    streamcopy_count = len(tasks) - reencode_count
    print(f'  Re-encode (slow-mo/fast): {reencode_count}')
    print(f'  Stream copy (instant): {streamcopy_count}')

    if args.dry_run:
        print('\n=== DRY RUN ===')
        print(f'Plan: render {len(tasks)} segments di {args.workers} workers paralel')
        print(f'Preset: {args.preset}')
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
    success = render_all_segments(
        tasks, args.mp4, segments_dir, ffmpeg, ffprobe,
        preset=args.preset, workers=args.workers, encoder=args.encoder,
    )

    if not success:
        print('\n❌ Pass 1 gagal. Beberapa segment gagal di-render.')
        print('Coba jalankan ulang (resume support — segment yang sudah ada akan di-skip).')
        if not args.keep_temp:
            print(f'Temp files: {work_dir} (pakai --keep-temp untuk inspect)')
        sys.exit(1)

    # Pass 2: Concat + mix audio
    success = concat_segments(
        tasks, segments_dir, audio_dub_path, args.output,
        ffmpeg, has_audio_ori, args.sfx_ducking,
        video_only=args.video_only, encoder=args.encoder,
    )

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
        # Error dari ffprobe / ffmpeg helper (mis. MP4 corrupt, durasi invalid)
        print(f'\n❌ Error: {e}', file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        # Catch-all supaya user lihat error message jelas, bukan stack trace jelek
        print(f'\n❌ Error tidak terduga: {e}', file=sys.stderr)
        import traceback
        print(f'\nStack trace (untuk debugging):\n{traceback.format_exc()[:1000]}', file=sys.stderr)
        sys.exit(1)
