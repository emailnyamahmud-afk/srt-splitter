#!/usr/bin/env python3
"""
mix-tui.py v3.8.1 — TUI interaktif untuk mix MP4 + audio_dub (+ optional SFX/MP3 ori + optional SRT burn + logo overlay)

Workflow produksi (4 fase, bersih — sesuai v6 yt-dlp + edge-tts-tui):
  Fase 1: yt-dlp v6      → {name}.mp4 (video) + {name}-audio.mp3 (via yt-dlp convert) + {name}.id.srt
  Fase 2: demucs-tui.py  → split {name}-audio.mp3 → no_vocals.mp3 (MP3 320, SFX bersih)
                          + vocals.mp3 (auto-hapus, tidak dipakai)
  Fase 3a: edge-tts-tui.py (LOKAL — ganti web app Mode ON)
                        → {prefix}-audio-id-dub.wav (Bahasa Indonesia, full durasi)
  Fase 3b: web app SRT editor (Bahasa Jawa, per cue — nunggu code fix)
                        → audio-jw-dub.wav
  Fase 4: mix-tui.py v3.6 → 3 mode input × 2 mode output = 6 kombinasi
    Mode input (v3.6 NEW: + Original):
      - Full     = MP4 + no_vocals SFX (Demucs) + audio_dub (3 input, ducking, workflow existing)
      - Original = MP4 + MP3 ori (audio asli yt-dlp) + audio_dub (3 input, ducking saat dub bicara)
                   Cocok untuk produksi cepat tanpa Demucs, tapi tetap ada ducking
      - Simple   = MP4 + audio_dub saja (2 input, no SFX, no ducking, paling cepat)
    Mode output:
      - Stream copy = video copy (no re-encode), audio encode AAC → ~1-3 menit
      - Burn SRT    = re-encode video h264_videotoolbox + hardsub SRT → ~5 menit M1

    Hasil 6 kombinasi:
      A. Full     + Stream copy → {prefix}-id-final.mp4      (~3 menit, ~350 MB, no SRT)
      B. Full     + Burn SRT    → {prefix}-id-final-sub.mp4  (~5 menit, ~1.2-4.5 GB, hardsub)
      C. Simple   + Stream copy → {prefix}-id-simple.mp4    (~1 menit, ~350 MB, no SFX, no SRT)
      D. Simple   + Burn SRT    → {prefix}-id-simple-sub.mp4 (~5 menit, ~1.2-4.5 GB, hardsub, no SFX)
      E. Original + Stream copy → {prefix}-id-orig.mp4      (~3 menit, ~350 MB, MP3 ori+ducking)  ← v3.6 NEW
      F. Original + Burn SRT    → {prefix}-id-orig-sub.mp4  (~5 menit, ~1.2-4.5 GB, hardsub, MP3 ori+ducking) ← v3.6 NEW

v3.7.6 FIX: MUTE COMPLETE via amultiply + inverted envelope (ganti sidechain compress).
  - User feedback v3.7.5: "jangan over engineer dengan reduksi 50%, bahkan 20% tetap terdengar"
  - v3.7.5 cascade 2-stage sidechain masih gradual (67% reduction, masih ada 33% MP3 ori)
  - v3.7.6: amultiply (sample-by-sample multiplication) → MP3 ori * 0 = MUTE TOTAL saat cue
  - Envelope inverted: 0.0 saat cue (MUTE), 1.0 saat gap (NORMAL)
  - MP3_ori * envelope = MUTE saat cue, NORMAL saat gap
  - Test sandbox: MP3 ori cue reduction 99.9% (true MUTE, mag 154 = floating noise)
  - Fade 100ms di boundary untuk smooth transition (v3.8.1: 1ms→100ms, user request "transisi mulus")
  - Sederhana, no over-engineering, sesuai user request

v3.7.5 FIX: Cascade 2-stage sidechain compress + Dub boost 1.5x + envelope 44100 Hz.
  - v3.7.3 single-stage ratio=20 hanya reduce 50% — user lihat "MP3 ori makin keras"
  - Test sandbox: sidechain compress BEKERJA (50% reduction) tapi tidak cukup aggressive
  - v3.7.5 cascade 2-stage (20×20=400x effective ratio) → MP3 ori cue reduction 67%
  - Plus boost Dub volume 1.5x → Dub dominant saat cue, MP3 ori jadi background
  - Envelope sample rate default 44100 Hz (match dengan audio biasanya, lebih reliable)
  - Print cue coverage % — warning kalau >80% (film dialog sangat padat)
  - Test sandbox: FFT analysis confirm Dub dominant saat cue, MP3 ori dominant saat gap

v3.7.3 FIX: SRT-driven ducking pakai envelope WAV + sidechain compress (ganti nested if expression).
  - v3.7/3.7.1/3.7.2 pakai nested if expression → FFmpeg gagal parse untuk 4857 cues (exit code 8)
  - v3.7.3 fix: generate WAV envelope mono (100 Hz) berdasarkan SRT segments
    - envelope = 1.0 saat cue aktif (loud, trigger sidechain compress)
    - envelope = 0.0 saat gap (silent, MP3 ori normal)
    - Fade in/out 10ms di boundary untuk smooth transition
  - Pakai FFmpeg sidechaincompress dengan envelope sebagai sidechain input
  - Input index: 0=mp4, 1=sfx_wav, 2=audio_dub, 3=envelope_wav
  - FFmpeg command: -i mp4 -i sfx -i dub -i envelope.wav -filter_complex ...
  - Kelebihan: no expression size limit, no parse issue, works untuk any number of cues
  - Cleanup envelope WAV setelah FFmpeg selesai (success/fail/KeyboardInterrupt)

v3.7.1 SIMPLIFIKASI: 1 SRT Indonesia cukup untuk duck + burn (timestamps identik dengan SRT Mandarin).
  - User feedback v3.7: "SRT mandarin tak relevan, karena SRT id juga identik timesmapnya"
  - Fix: hapus Step 4.55 (SRT Mandarin prompt) → 1 SRT Indonesia di Step 4.6 untuk 2 tujuan
  - Original mode (E/F): SRT Indonesia = sumber ducking window + burn subtitle (kalau Burn SRT)
  - Mode F (Original + Burn): 1 SRT untuk 2 tujuan (duck + burn), bukan 2 SRT terpisah

v3.7 NEW: SRT-driven ducking untuk Original mode (fix masalah vokal asli v3.6).
  - User feedback v3.6: "suara asli tetap muncul bahkan saat dub bicara" — sidechain compress
    cuma turunkan volume, tidak hilangkan vokal Mandarin asli.
  - v3.7 fix: pakai SRT Indonesia (timestamps identik SRT Mandarin) sebagai pedoman ducking window
    - Setiap cue SRT = window duck MP3 ori (volume turun ke 6.25% = -24 dB)
    - Lead 100ms sebelum cue + tail 100ms setelah cue (smooth transition)
    - SFX/musik latar tetap normal di gap antar dialog (volume 100%)
  - FFmpeg filter: volume='if(between(t,start,end),0.0625,if(...,1.0))':eval=frame
    - eval=frame: per-frame evaluation untuk smooth transition (avoid click artifact)
  - Cocok untuk: produksi cepat skala besar (skip Demucs ~16 menit, tetap ada ducking proper)

v3.6 NEW: Original mode — MP4 + MP3 ori + Dub dengan ducking otomatis.
  - User request: "produksi cepat cukup mp4 ori, mp3 ori dan dub" tanpa Demucs
  - Ducking: saat dub bicara → MP3 ori (vokal+SFX+musik) volume turun otomatis (sidechain compress)
  - Bedanya dengan Full mode: Full pakai no_vocals (Demucs), Original pakai MP3 ori (skip Demucs)
  - Bedanya dengan Simple mode: Simple no ducking, Original ada ducking
  - Cocok untuk: produksi cepat, skip Demucs (~16 menit), tapi tetap ada ducking

v3.5: Step 4.8 — pilih video bitrate untuk Mode B & D (burn SRT).
  - Burn SRT wajib re-encode video → user pilih bitrate untuk hemat size.
  - Pilihan: 1 Mbps (~1.2 GB/2jam) / 1.5 Mbps (~1.8 GB/2jam, default) /
             2 Mbps (~2.3 GB/2jam, subtitle paling sharp) / 4 Mbps (~4.5 GB/2jam, HD-ready).
  - Default = 1.5 Mbps (compromise antara size dan quality untuk 480p + hardsub).
  - Mode A & C (stream copy) tidak perlu prompt — bitrate ikut MP4 ori (no re-encode).

v3.4: Step 1.5 — pilih mode input (Full / Simple / Original).
  - Default = Full (workflow existing teruji 5 film).
  - Simple = MP4 + Dub saja, no SFX, no ducking. Untuk preview cepat atau
    film yang SFX-nya sudah tidak dibutuhkan (mis. dialog dominan).
  - Audio Simple: copy dub as-is (no filter, no ducking). Dub dari edge-tts
    sudah di-mix dengan level OK oleh TTS engine.

v3.3 fix: Justify=2 (center horizontal) untuk SEMUA alignment.
  Bug: Alignment=5 (top) → text rata KIRI di libass default.
  Fix: tambah Justify=2 di force_style → text rata TENGAH.

v3.3 NEW: 4 opsi posisi di Step 4.7:
  - Opsi A: Bawah Mandarin — Alignment=2, MarginV=20 (Indonesia di paling bawah)  ← DEFAULT
  - Opsi D: Overlay atas Mandarin — Alignment=2, MarginV=60 (Indonesia di atas SRT Mandarin)
  - Opsi B: Atas frame — Alignment=5, MarginV=50 (jauh dari Mandarin)
  - Opsi C: Tengah video — Alignment=8, MarginV=0 (bisa nutup wajah)

v3.2 NEW: posisi default top:50 (bukan 20) supaya subtitle Indonesia tidak
  menempel ke atas. Format posisi baru: 'top:NN' (custom MarginV).

v3.1 fix: Alignment ASS spec yang benar:
  - top = Alignment=5 (sebelumnya 8 = middle, SALAH)
  - middle = Alignment=8
  - bottom = Alignment=2

v3 NEW: 2 mode mix (user pilih di step 4.5)
  Mode A: Stream copy (CEPAT ~3 menit, no SRT burn)
    - Video stream copy (no re-encode) → 100% sync, resolusi ori tetap
    - Output: {prefix}-id-final.mp4 (~275 MB untuk 2 jam video)
    - Cocok untuk: preview cepat, arsip, publish tanpa subtitle burn

  Mode B: Burn SRT Indonesia (LAMBAT ~3-5 menit di M1 VideoToolbox, BUKAN 30 menit)
    - Video re-encode pakai h264_videotoolbox (M1 GPU, BUKAN CPU)
    - SRT Indonesia burn hard-sub ke video (font 18pt, putih outline hitam)
    - Posisi default: TOP + MarginV=50 (tidak overlap SRT Mandarin di bottom)
    - Output: {prefix}-id-final-sub.mp4 (~2.1 GB untuk 2 jam video 480p @ 2 Mbps)
    - Cocok untuk: publish ke platform tanpa edit DaVinci

Kenapa burn SRT lokal (bukan DaVinci):
  - DaVinci minimum render 1080p → size GB-level, boros storage
  - DaVinci re-encode semua track → lama
  - mix-tui v3 mode B: tetap 480p, VideoToolbox hardware, hemat storage

Mix ini selalu pakai 3 input wajib:
  1. MP4 ori (video, dari yt-dlp v6)
  2. no_vocals (SFX bersih dari Demucs — MP3 320 kbps, vokal ori sudah dibuang)
  3. audio_dub.wav (dialog hasil dubbing dari edge-tts-tui.py atau web app Jawa)

Optional input (Mode B only):
  4. SRT Indonesia (dari yt-dlp v6, mis. S5-ori.id.srt)

Output: MP4 durasi penuh. Setelah dub selesai, SFX tetap bermain (dub = hening).

Install: pip3 install questionary (di venv)
Usage: python3 mix-tui.py (pilih file pakai arrow keys)
"""

import os
import sys
import re
import glob
import subprocess
import time
from pathlib import Path

try:
    import questionary
except ImportError:
    print()
    print('═' * 64)
    print('❌ Dependensi belum lengkap!')
    print('═' * 64)
    print()
    print('   Missing: questionary')
    print()
    print('   Install dengan:')
    print()
    print('   pip3 install questionary')
    print()
    print('   Kalau Mac block, pakai:')
    print()
    print('   pip3 install --break-system-packages questionary')
    print()
    print('═' * 64)
    sys.exit(1)


def clear_screen():
    os.system('clear' if os.name != 'nt' else 'cls')


def print_banner():
    clear_screen()
    print('╔' + '═' * 64 + '╗')
    print('║  🎬 Mix MP4 + No-Vocal SFX + Audio Dub v2 (TUI)' + ' ' * 13 + '║')
    print('║  yt-dlp v6 → Demucs → edge-tts-tui → mix → final' + ' ' * 12 + '║')
    print('╚' + '═' * 64 + '╝')
    print()


def find_files_in_dir(search_dir, extensions):
    files = []
    for ext in extensions:
        for f in glob.glob(os.path.join(search_dir, f'*.{ext}')):
            files.append(os.path.basename(f))
        for f in glob.glob(os.path.join(search_dir, f'*.{ext.upper()}')):
            files.append(os.path.basename(f))
    files.sort()
    return list(dict.fromkeys(files))  # deduplicate


def select_file(prompt, extensions, search_dir=None, default=None):
    from config import INPUT_DIR, DEMUCS_DIR, TTS_DIR, ensure_hdd
    if search_dir is None:
        # Default: cari di HDD subfolder yg relevan
        if ensure_hdd():
            search_dir = str(INPUT_DIR)
        else:
            search_dir = os.getcwd()
    available = find_files_in_dir(search_dir, extensions)
    if not available:
        path = questionary.text(f'{prompt} (ketik path lengkap):', default=default or '').ask()
        return path
    choices = available + ['[Ketik path manual]']
    selected = questionary.select(prompt, choices=choices, default=available[0]).ask()
    if selected == '[Ketik path manual]':
        return questionary.text(f'{prompt} (ketik path lengkap):', default=default or '').ask()
    return os.path.join(search_dir, selected)


def find_ffmpeg():
    import shutil
    path = shutil.which('ffmpeg')
    if path:
        return path
    for loc in ['/usr/local/bin/ffmpeg', '/usr/bin/ffmpeg', '/opt/homebrew/bin/ffmpeg']:
        if os.path.isfile(loc):
            return loc
    print()
    print('═' * 64)
    print('❌ ffmpeg belum terinstall!')
    print('═' * 64)
    print()
    print('   Install dengan Homebrew:')
    print()
    print('   brew install ffmpeg')
    print()
    print('═' * 64)
    sys.exit(1)


def find_ffprobe():
    import shutil
    path = shutil.which('ffprobe')
    if path:
        return path
    for loc in ['/usr/local/bin/ffprobe', '/usr/bin/ffprobe', '/opt/homebrew/bin/ffprobe']:
        if os.path.isfile(loc):
            return loc
    print()
    print('═' * 64)
    print('❌ ffprobe belum terinstall! Install: brew install ffmpeg')
    print('═' * 64)
    sys.exit(1)


def get_duration(ffprobe, path):
    if not os.path.isfile(path):
        return 0
    result = subprocess.run([
        ffprobe, '-v', 'error', '-show_entries', 'format=duration',
        '-of', 'default=noprint_wrappers=1:nokey=1', path,
    ], capture_output=True, text=True)
    try:
        return float(result.stdout.strip())
    except Exception:
        return 0


def validate_input_file(path, label):
    """Cek file exist + size > 0. Kalau tidak, exit dengan pesan jelas."""
    if not path or not path.strip():
        print(f'\n❌ File {label} tidak dipilih.')
        sys.exit(1)
    if not os.path.isfile(path):
        print(f'\n❌ File {label} tidak ditemukan: {path}')
        print(f'   Cek path dan pastikan file ada di folder.')
        sys.exit(1)
    size = os.path.getsize(path)
    if size == 0:
        print(f'\n❌ File {label} kosong (0 bytes): {path}')
        print(f'   Mungkin generate gagal. Coba generate ulang.')
        sys.exit(1)
    return True


def derive_default_output(mp4_path, lang='id'):
    """
    Derive default output filename dari MP4 input.
    Mis. S5-ori.mp4 → S5-ori-id-final.mp4
    """
    base = Path(mp4_path).stem
    # Hapus suffix -ori kalau ada (sesuai konvensi yt-dlp v6)
    if base.endswith('-ori'):
        base = base[:-4]
    return f'{base}-{lang}-final.mp4'


def format_duration(seconds: float) -> str:
    """Format seconds → HH:MM:SS untuk display."""
    if seconds < 0:
        return '0s'
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    if h > 0:
        return f'{h}j {m}m {s}s'
    if m > 0:
        return f'{m}m {s}s'
    return f'{s}s'


def parse_ffmpeg_progress(line: str, total_dur: float):
    """
    Parse FFmpeg stderr line untuk extract progress.
    Format: 'size=   102kB time=00:01:23.45 bitrate= 100.2kbits/s speed=2.5x'
    Returns: dict {time_sec, percent, size_kb, speed} atau None.
    """
    # Cari time= pattern
    m = re.search(r'time=(\d+):(\d+):(\d+(?:\.\d+)?)', line)
    if not m:
        return None
    h, mi, s = m.groups()
    time_sec = int(h) * 3600 + int(mi) * 60 + float(s)

    size_m = re.search(r'size=\s*(\d+)kB', line)
    size_kb = int(size_m.group(1)) if size_m else 0

    speed_m = re.search(r'speed=\s*([\d.]+)x', line)
    speed = float(speed_m.group(1)) if speed_m else 0

    percent = (time_sec / total_dur * 100) if total_dur > 0 else 0
    return {
        'time_sec': time_sec,
        'percent': min(percent, 100),
        'size_kb': size_kb,
        'speed': speed,
    }


def run_ffmpeg_with_progress(cmd, total_dur: float):
    """
    Jalankan FFmpeg dengan stderr parsing untuk progress bar real-time.
    Pakai threading untuk baca stderr line-by-line — hindari deadlock
    yang bisa terjadi kalau FFmpeg output > 64KB pipe buffer (Mac default).
    """
    import threading
    import queue

    proc = subprocess.Popen(
        cmd,
        stderr=subprocess.PIPE,
        stdout=subprocess.DEVNULL,
        universal_newlines=True,
        bufsize=1,
    )

    # Thread pembaca stderr → queue (avoid deadlock)
    line_queue: queue.Queue = queue.Queue()
    reader_done = threading.Event()

    def stderr_reader():
        try:
            for line in proc.stderr:
                line_queue.put(line)
        finally:
            reader_done.set()

    reader_thread = threading.Thread(target=stderr_reader, daemon=True)
    reader_thread.start()

    last_print = 0
    start_time = time.time()

    # Loop baca queue sampai FFmpeg selesai + queue kosong
    while True:
        try:
            line = line_queue.get(timeout=0.1)
        except queue.Empty:
            # Cek apakah FFmpeg sudah selesai + reader selesai + queue kosong
            if proc.poll() is not None and reader_done.is_set() and line_queue.empty():
                break
            continue

        progress = parse_ffmpeg_progress(line, total_dur)
        if progress and (time.time() - last_print) > 0.5:
            elapsed = time.time() - start_time
            elapsed_fmt = format_duration(elapsed)
            eta = (total_dur - progress['time_sec']) / max(0.1, progress['speed']) if progress['speed'] > 0 else 0
            eta_fmt = format_duration(eta) if eta > 0 else '?'
            size_mb = progress['size_kb'] / 1024
            # Print inline (carriage return supaya tidak numpuk baris)
            sys.stdout.write(
                f'\r  {progress["percent"]:5.1f}% | '
                f'time={format_duration(progress["time_sec"]):>8} / {format_duration(total_dur):>8} | '
                f'size={size_mb:6.1f} MB | '
                f'speed={progress["speed"]:.1f}x | '
                f'elapsed={elapsed_fmt} | ETA={eta_fmt}'
            )
            sys.stdout.flush()
            last_print = time.time()

    proc.wait()
    reader_thread.join(timeout=2)
    sys.stdout.write('\n')
    sys.stdout.flush()
    return proc.returncode


def prompt_ducking():
    """Prompt ducking level, return dB integer."""
    ducking_choices = [
        '12 dB (default, seimbang) — REKOMENDASI',
        '6 dB (SFX lebih keras)',
        '18 dB (SFX lebih pelan, dub dominan)',
        '0 dB / no ducking (SFX + dub sama keras)',
    ]
    ducking_choice = questionary.select('Ducking:', choices=ducking_choices, default=ducking_choices[0]).ask()
    if not ducking_choice:
        return 12
    return int(ducking_choice.split(' dB')[0])


def prompt_video_bitrate():
    """Prompt video bitrate untuk burn SRT mode (Mode B & D).

    v3.5 NEW: User bisa pilih bitrate untuk hemat size.
    Burn SRT wajib re-encode video → bitrate target menentukan output size.

    Return: string ffmpeg format ('1M', '1.5M', '2M', atau '4M').

    Estimasi size untuk 2 jam video (480p):
      - 1 Mbps   → ~1.2 GB (hemat, quality masih OK untuk subtitle 480p)
      - 1.5 Mbps → ~1.8 GB (seimbang, rekomendasi default)
      - 2 Mbps   → ~2.3 GB (current behavior, paling aman untuk subtitle sharp)
      - 4 Mbps   → ~4.5 GB (HD-ready, kalau source ori high quality)

    Default = 1.5 Mbps (compromise antara size dan quality untuk 480p + hardsub).
    Catatan: Mode A & C (stream copy) tidak perlu prompt — bitrate ikut MP4 ori.
    """
    bitrate_choices = [
        '1.5 Mbps (seimbang ~1.8 GB/2jam, rekomendasi default) — REKOMENDASI',
        '1 Mbps (hemat ~1.2 GB/2jam, quality masih OK untuk 480p hardsub)',
        '2 Mbps (current default ~2.3 GB/2jam, subtitle paling sharp)',
        '4 Mbps (HD-ready ~4.5 GB/2jam, kalau source ori high quality)',
    ]
    bitrate_choice = questionary.select('Video bitrate (Mode burn SRT):', choices=bitrate_choices, default=bitrate_choices[0]).ask()
    if not bitrate_choice:
        return '1.5M'
    # Parse pilihan → string ffmpeg format
    if bitrate_choice.startswith('1 Mbps'):
        return '1M'
    elif bitrate_choice.startswith('1.5 Mbps'):
        return '1.5M'
    elif bitrate_choice.startswith('2 Mbps'):
        return '2M'
    elif bitrate_choice.startswith('4 Mbps'):
        return '4M'
    return '1.5M'


def prompt_output(default_output):
    """Prompt output filename, return string."""
    output = questionary.text('Output MP4:', default=default_output).ask()
    return output or default_output


def parse_srt_for_ducking(srt_path, lead_ms=100, tail_ms=100):
    """Parse SRT → list of (start_sec, end_sec) untuk ducking segments.

    v3.7 NEW: SRT-driven ducking untuk Original mode.
    Setiap cue SRT (Mandarin ori) = window duck MP3 ori.
    Lead 100ms: duck sebelum dialog mulai (smooth transition, avoid click).
    Tail 100ms: duck setelah dialog berakhir (avoid abrupt cut).

    Returns:
      list of (start_sec, end_sec) tuples, sorted by start.
      Empty list kalau SRT tidak ada / parse error.
    """
    if not srt_path or not os.path.isfile(srt_path):
        return []

    segments = []
    # Pattern: 00:00:05,000 --> 00:00:06,500
    cue_pattern = re.compile(
        r'(\d{2}):(\d{2}):(\d{2})[,.](\d{3})\s*-->\s*(\d{2}):(\d{2}):(\d{2})[,.](\d{3})'
    )
    try:
        with open(srt_path, 'r', encoding='utf-8') as f:
            content = f.read()
        for match in cue_pattern.finditer(content):
            h1, m1, s1, ms1, h2, m2, s2, ms2 = match.groups()
            start_sec = int(h1) * 3600 + int(m1) * 60 + int(s1) + int(ms1) / 1000
            end_sec = int(h2) * 3600 + int(m2) * 60 + int(s2) + int(ms2) / 1000
            # Apply lead/tail
            duck_start = max(0, start_sec - lead_ms / 1000)
            duck_end = end_sec + tail_ms / 1000
            if duck_end > duck_start:
                segments.append((duck_start, duck_end))
    except Exception as e:
        print(f'  ⚠ Gagal parse SRT untuk ducking: {e}')
        return []
    # Sort by start time
    segments.sort(key=lambda x: x[0])
    return segments


def build_srt_ducking_filter(segments, duck_volume=0.0625, total_dur=0, output_dir=None):
    """Build FFmpeg volume filter expression dari SRT duck segments.

    v3.7 NEW: Build dynamic volume expression berdasarkan SRT timestamps.
    v3.7.2 FIX: Kalau expression >LIMIT_ARG_BYTES (~100 KB), tulis ke file temp
               supaya tidak kena OS arg limit (~128 KB). Pakai -filter_complex_script.

    Format: if(between(t,4.9,6.6),0.0625,if(between(t,23.1,25.2),0.0625,...,1.0))

    Args:
      segments: list of (start_sec, end_sec) tuples dari parse_srt_for_ducking
      duck_volume: volume saat duck (0.0625 = -24 dB, hampir mute)
      total_dur: total durasi MP4 (untuk info display only)
      output_dir: directory untuk file temp (kalau None → pakai default tempdir)

    Returns:
      Tuple (filter_inline, filter_file):
        - filter_inline: string untuk dipakai langsung di -filter_complex (kalau <= limit)
        - filter_file: path file temp berisi full filter_complex (kalau > limit, dipakai dengan -filter_complex_script)

      Salah satu akan None. Caller harus cek:
        if filter_file: pakai -filter_complex_script filter_file
        else: pakai -filter_complex filter_inline
    """
    if not segments:
        # No SRT cues → no ducking, MP3 ori penuh
        return '[1:a]volume=1[sfx_ducked]', None

    # Build nested if expression, mulai dari default 1.0 (volume normal)
    # Iterasi dari cue TERAKHIR → FIRST supaya nested if benar
    # Format: if(between(t,start,end),duck,if(between(...),duck,...,1.0))
    expr = '1.0'  # default volume (normal, no duck)
    for start, end in reversed(segments):
        s = round(start, 3)
        e = round(end, 3)
        expr = f'if(between(t,{s},{e}),{duck_volume},{expr})'
    # eval=frame: evaluate per-frame (setiap audio sample chunk) untuk smooth transition
    volume_filter = f"[1:a]volume='{expr}':eval=frame[sfx_ducked]"

    # OS arg limit ~128 KB, pakai threshold 100 KB (margin safety)
    # Kalau expression > limit → tulis ke file temp, pakai -filter_complex_script
    ARG_LIMIT_BYTES = 100 * 1024  # 100 KB threshold

    if len(volume_filter) > ARG_LIMIT_BYTES:
        # Expression terlalu besar untuk arg → tulis ke file temp
        # File akan berisi FULL filter_complex (audio + subtitle kalau ada)
        # Tapi function ini hanya return volume_filter, caller gabung dengan audio mix
        # Jadi return (None, volume_filter) — caller handle file writing
        if len(segments) > 500:
            print(f'  ℹ Filter expression besar ({len(volume_filter) // 1024} KB, {len(segments)} cues).')
            print(f'    Pakai -filter_complex_script (file temp) supaya tidak kena OS arg limit.')
        return None, volume_filter  # filter_inline None, filter_file = filter string (caller write to file)
    else:
        # Inline OK
        return volume_filter, None


def write_filter_complex_to_file(filter_complex_str, output_dir=None):
    """Tulis filter_complex ke file temp untuk -filter_complex_script.

    v3.7.2 NEW: Handle filter expression yang melebihi OS arg limit (~128 KB).
    Tulis ke file temp, pakai -filter_complex_script filename.

    Args:
      filter_complex_str: full filter_complex string (audio + subtitle)
      output_dir: directory untuk file temp (kalau None → pakai tempfile.gettempdir())

    Returns:
      Path file temp (caller pakai dengan -filter_complex_script <path>).
      Caller WAJIB hapus file setelah FFmpeg selesai.
    """
    import tempfile
    if output_dir is None:
        output_dir = tempfile.gettempdir()
    # Generate unique filename
    fd, filepath = tempfile.mkstemp(prefix='mix_tui_filter_', suffix='.txt', dir=output_dir)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            f.write(filter_complex_str)
    except Exception as e:
        os.unlink(filepath)
        raise e
    return filepath


def generate_duck_envelope_wav(segments, total_dur, output_path, duck_value=0.0, normal_value=1.0,
                                fade_ms=100, sample_rate=44100):
    """Generate WAV envelope untuk amultiply ducking (MUTE COMPLETE approach).

    v3.7.6 NEW: Hard mute approach (bukan sidechain compress gradual reduction).
    v3.7.5 update: cascade 2-stage sidechain compress masih gradual (67% reduction).
    User mau: MUTE COMPLETE saat cue (volume 0), NORMAL saat gap (volume 1).

    Approach: amultiply filter
      - envelope_inverted = 1.0 saat GAP (MP3 ori normal)
      - envelope_inverted = 0.0 saat CUE (MP3 ori MUTE complete)
      - MP3_ori * envelope_inverted = MP3_ori saat gap, 0 (mute) saat cue

    Logic:
      - envelope = normal_value (1.0) saat GAP → MP3 ori normal
      - envelope = duck_value (0.0) saat CUE → MP3 ori MUTE
      - Fade 100ms di boundary untuk smooth transition (v3.8.1: 1ms→100ms, user request "transisi mulus")

    Args:
      segments: list of (start_sec, end_sec) dari parse_srt_for_ducking
      total_dur: total durasi audio (detik)
      output_path: path output WAV file
      duck_value: value saat cue aktif (0.0 = MUTE, default v3.7.6 inverted)
      normal_value: value saat gap (1.0 = NORMAL, default v3.7.6 inverted)
      fade_ms: fade in/out duration di boundary cue (default 1ms, fast transition)
      sample_rate: sample rate envelope (default 44100, match audio)

    Returns:
      Path output WAV file (caller cleanup setelah FFmpeg selesai)
      Return None kalau segments kosong atau error.
    """
    if not segments or total_dur <= 0:
        return None

    try:
        import wave
        import struct

        # Generate envelope signal (mono, sample_rate Hz)
        n_samples = int(total_dur * sample_rate) + sample_rate  # +1s buffer
        envelope = [normal_value] * n_samples  # default = normal (1.0)

        # Fade samples (1ms = ~44 samples @ 44100 Hz)
        fade_samples = max(1, int(fade_ms * sample_rate / 1000))

        for start, end in segments:
            start_idx = max(0, int(start * sample_rate))
            end_idx = min(n_samples, int(end * sample_rate))
            if end_idx <= start_idx:
                continue

            # Set duck value (0.0 = MUTE) saat cue aktif
            for i in range(start_idx, end_idx):
                # Fade in (start) dan fade out (end) untuk smooth transition
                fade_in = (i - start_idx) / fade_samples  # 0 → 1 dalam fade_samples
                fade_out = (end_idx - 1 - i) / fade_samples  # 1 → 0 dalam fade_samples
                fade_factor = min(1.0, fade_in, fade_out)
                # Interpolasi: normal (1.0) → duck (0.0) saat fade_factor 0
                # saat fade_factor 1 → full duck (0.0)
                # saat fade_factor 0 → normal (1.0)
                envelope[i] = normal_value + (duck_value - normal_value) * fade_factor

        # Convert float (0.0-1.0) ke int16 (0 to 32767)
        # amultiply butuh range 0-32767 (0 = mute, 32767 = full volume)
        samples_int16 = []
        for v in envelope:
            v_clamped = max(0.0, min(1.0, v))  # clamp 0.0-1.0
            samples_int16.append(int(v_clamped * 32767))

        # Write WAV (mono, 16-bit PCM, sample_rate Hz)
        with wave.open(output_path, 'w') as w:
            w.setnchannels(1)
            w.setsampwidth(2)  # 16-bit
            w.setframerate(sample_rate)
            w.writeframes(struct.pack(f'<{len(samples_int16)}h', *samples_int16))

        return output_path

    except Exception as e:
        print(f'  ⚠ Gagal generate envelope WAV: {e}')
        return None


def find_logo_file():
    """Cari logo PNG di lokasi default (auto-detect).

    v3.8 NEW: Logo overlay untuk Mode Burn SRT (B/D/F).
    Auto-detect di lokasi berikut (urutan prioritas):
      1. HDD/input/logo.png (kalau HDD ter-colok)
      2. ~/Dubbing/logo.png (SSD)

    User tinggal taruh file "logo.png" di salah satu lokasi.
    Logo akan di-burn ke top-right video (10px margin).

    Returns:
      Path logo PNG (string) kalau ditemukan, None kalau tidak ada.
    """
    candidates = []

    # Priority 1: HDD/input/logo.png (kalau HDD ter-colok)
    try:
        from config import INPUT_DIR, ensure_hdd
        if ensure_hdd():
            candidates.append(INPUT_DIR / 'logo.png')
    except Exception:
        pass

    # Priority 2: ~/Dubbing/logo.png (SSD)
    candidates.append(Path.home() / 'Dubbing' / 'logo.png')

    for path in candidates:
        if path.is_file():
            return str(path)
    return None


def build_logo_overlay_filter(logo_path, logo_input_index, base_filter_output_label, final_output_label,
                               logo_size=100):
    """Build FFmpeg overlay filter untuk burn logo PNG ke video.

    v3.8 NEW: Chain subtitle + logo overlay untuk Mode Burn SRT.
    v3.8.2: Tambah scale filter (default 100px, user feedback "agak terlalu besar").
    Logo di-burn ke top-right (10px margin dari kanan atas).

    Args:
      logo_path: path ke file logo PNG
      logo_input_index: index input logo di FFmpeg cmd (mis. 3 untuk input ke-4)
      base_filter_output_label: label output dari filter sebelumnya (mis. 'vsub' dari subtitle)
      final_output_label: label output final (mis. 'vout')
      logo_size: ukuran logo dalam pixel (default 100, sebelumnya 150 — user feedback "terlalu besar")

    Returns:
      Tuple (overlay_filter_str, logo_path):
        - overlay_filter_str: string filter overlay untuk di-chain ke filter_complex
        - logo_path: path logo (untuk dijadikan input FFmpeg)
    """
    if not logo_path or not os.path.isfile(logo_path):
        return None, None

    # v3.8.2: scale logo ke logo_size px (default 100, dari 150 — user feedback "terlalu besar")
    # format=rgba → preserve transparan alpha channel
    # scale=100:100 → resize logo ke 100x100 px (regardless of original file size)
    # overlay=main_w-overlay_w-10:10 → top-right, 10px margin
    overlay_filter = (
        f'[{logo_input_index}:v]format=rgba,scale={logo_size}:{logo_size}[logo_input];'
        f'[{base_filter_output_label}][logo_input]overlay=main_w-overlay_w-10:10[{final_output_label}]'
    )
    return overlay_filter, logo_path


def main():
    print_banner()

    print('📋 Mode: Mix cepat (TUI v2) — MP4 + SFX no-vocal + dub dengan ducking')
    print('   Mode manual (DaVinci): tarik file ke timeline, edit sendiri')
    print()
    print('   Navigasi: ↑↓ arrow keys, Enter konfirmasi, q batal')
    print()

    total = 6

    # Step 1: MP4 ori (video) — cari di HDD/input/
    print(f'▶ Step 1/{total}: Pilih file MP4 ori (video)')
    from config import INPUT_DIR, DEMUCS_DIR, TTS_DIR, MIX_DIR, ensure_hdd
    mp4 = select_file('MP4 ori (mis. S5-ori.mp4):', ['mp4'], search_dir=str(INPUT_DIR) if ensure_hdd() else None)
    if not mp4:
        print('Batal.'); sys.exit(0)
    print(f'  ✓ {mp4}')
    print()

    # Step 1.5: Mode input (v3.4: Full/Simple, v3.6: + Original, v3.7: Original SRT-driven ducking)
    # v3.7 update: Original mode sekarang REKOMENDASI lagi — SRT-driven ducking fix masalah vokal asli.
    # SRT Mandarin → duck window (volume 6.25% = -24 dB saat dialog Mandarin).
    # SFX/musik latar tetap normal di gap antar dialog.
    print(f'▶ Step 1.5/{total}: Pilih mode input')
    mode_input_choice = questionary.select(
        'Mode input:',
        choices=[
            'Full (MP4 + SFX no_vocals + Dub) — REKOMENDASI proper, clean sempurna (perlu Demucs)',
            'Original (MP4 + MP3 ori + Dub + SRT-duck) — REKOMENDASI cepat, skip Demucs, v3.7 NEW',
            'Simple (MP4 + Dub saja, no SFX) — REKOMENDASI cepat, untuk preview/dialog dominan',
        ],
        default='Full (MP4 + SFX no_vocals + Dub) — REKOMENDASI proper, clean sempurna (perlu Demucs)',
    ).ask()
    simple_mode = 'Simple' in mode_input_choice
    original_mode = 'Original' in mode_input_choice
    # Full mode = bukan Simple AND bukan Original
    if simple_mode:
        mode_label_display = 'Simple (MP4 + Dub, no SFX)'
    elif original_mode:
        mode_label_display = 'Original (MP4 + MP3 ori + Dub, SRT-driven ducking)'
    else:
        mode_label_display = 'Full (MP4 + SFX + Dub)'
    print(f'  ✓ {mode_label_display}')
    if original_mode:
        # v3.7.1: Original mode sekarang REKOMENDASI (SRT-driven ducking fix v3.6 vokal issue)
        # v3.7.1 SIMPLIFIKASI: 1 SRT Indonesia cukup untuk duck + burn (timestamps identik dengan SRT Mandarin)
        print('  ℹ  v3.7.1: Original mode pakai SRT-driven ducking (SRT Indonesia = window duck).')
        print('      Saat dialog aktif (cue SRT) → MP3 ori volume turun ke 6.25% (-24 dB, hampir mute).')
        print('      SFX/musik latar tetap normal di gap antar dialog.')
        print('      1 SRT Indonesia dipakai untuk: ducking (saat cue aktif) + burn subtitle (kalau Burn SRT mode).')
    print()

    # Step 2: SFX/audio input — tergantung mode
    # - Full: no_vocals.mp3 dari Demucs (cari di HDD/demucs/)
    # - Original: MP3 ori dari yt-dlp (cari di HDD/input/)
    # - Simple: skip (no SFX layer)
    sfx_wav = None  # tetap pakai nama lama supaya FFmpeg cmd downstream tidak banyak ubah
    if simple_mode:
        print(f'▶ Step 2/{total}: [SKIP] Simple mode — no SFX input')
        print()
    elif original_mode:
        # v3.6 NEW: Original mode — pakai MP3 ori (audio asli dari yt-dlp, termasuk vokal + SFX + musik)
        # Sumber: HDD/input/ (sama dengan MP4 ori, bukan HDD/demucs/ seperti no_vocals)
        print(f'▶ Step 2/{total}: Pilih file MP3 ori (audio asli dari yt-dlp)')
        sfx_wav = select_file('MP3 ori (audio asli):', ['mp3', 'm4a', 'wav'], search_dir=str(INPUT_DIR) if ensure_hdd() else None)
        if not sfx_wav:
            print('Batal.'); sys.exit(0)
        print(f'  ✓ {sfx_wav}')
        print()
    else:
        # Full mode: no_vocals dari Demucs
        print(f'▶ Step 2/{total}: Pilih file SFX bersih (no_vocals.mp3 / .wav)')
        sfx_wav = select_file('SFX bersih (no_vocals):', ['mp3', 'wav', 'flac'], search_dir=str(DEMUCS_DIR) if ensure_hdd() else None)
        if not sfx_wav:
            print('Batal.'); sys.exit(0)
        print(f'  ✓ {sfx_wav}')
        print()

    # Step 3: Audio dub — cari di HDD/tts/
    print(f'▶ Step 3/{total}: Pilih file audio dub WAV')
    audio_dub = select_file('Audio dub (mis. S5-ori.id-audio-id-dub.wav):', ['wav'], search_dir=str(TTS_DIR) if ensure_hdd() else None)
    if not audio_dub:
        print('Batal.'); sys.exit(0)
    print(f'  ✓ {audio_dub}')
    print()

    # === Validasi semua input file exist (Bug #4 fix) ===
    print('▶ Validasi input file...')
    validate_input_file(mp4, 'MP4 ori')
    if not simple_mode:
        # Full mode: sfx_wav = no_vocals; Original mode: sfx_wav = MP3 ori
        label = 'MP3 ori' if original_mode else 'SFX no_vocals'
        validate_input_file(sfx_wav, label)
    validate_input_file(audio_dub, 'Audio dub')
    print('  ✓ Semua file valid')
    print()

    # Step 4: Ducking — skip kalau Simple (no SFX) ATAU Original (SRT-driven, prompt SRT di Step 4.6)
    # v3.6: Original mode pakai ducking (sama dengan Full)
    # v3.7: Original mode SRT-driven (Step 4.6, SRT Indonesia untuk duck + burn), bukan sidechain prompt
    # v3.7.1: 1 SRT Indonesia untuk duck + burn (timestamps identik dengan SRT Mandarin)
    ducking_db = 0
    if simple_mode:
        print(f'▶ Step 4/{total}: [SKIP] Simple mode — no ducking (dub copy as-is)')
        print()
    elif original_mode:
        # v3.7.1: Original mode pakai SRT-driven ducking, level fixed (-24 dB)
        # SRT Indonesia (Step 4.6 nanti) = sumber ducking window (timestamps identik dengan SRT Mandarin)
        print(f'▶ Step 4/{total}: [v3.7.1] Original mode pakai SRT-driven ducking (-24 dB fixed)')
        print('  Duck level fixed: 6.25% volume (-24 dB) saat cue SRT Indonesia aktif')
        print('  Lead 100ms + tail 100ms untuk smooth transition')
        print('  SRT Indonesia dipilih di Step 4.6 (nanti) — dipakai untuk duck + burn (kalau Burn SRT)')
        print()
    else:
        # Full mode: prompt ducking level (existing behavior, sidechain compress)
        print(f'▶ Step 4/{total}: Pilih ducking level')
        ducking_db = prompt_ducking()
        print(f'  ✓ {ducking_db}dB')
        print()

    # Step 4.5: Mode mix (NEW v3) — stream copy cepat vs burn SRT
    print(f'▶ Step 4.5/{total}: Pilih mode mix')
    mode_choice = questionary.select(
        'Mode mix:',
        choices=[
            'Stream copy (CEPAT ~3 menit, no SRT burn) — REKOMENDASI default',
            'Burn SRT Indonesia (LAMBAT ~30 menit, VideoToolbox M1 hardware)',
        ],
        default='Stream copy (CEPAT ~3 menit, no SRT burn) — REKOMENDASI default',
    ).ask()
    burn_srt = 'Burn SRT' in mode_choice
    print(f'  ✓ {"Burn SRT (encode ulang video)" if burn_srt else "Stream copy (3 menit)"}')
    print()

    # Step 4.6: SRT Indonesia untuk ducking (Original mode) dan/atau burn (Mode B/D/F)
    # v3.7.1 SIMPLIFIKASI: 1 SRT Indonesia cukup untuk 2 tujuan (duck + burn)
    #   - SRT Indonesia timestamps identik dengan SRT Mandarin (translation dari source sama)
    #   - Jadi duck window dari SRT Indonesia = duck window yang sama dengan kalau pakai SRT Mandarin
    #   - User feedback: "SRT mandarin tak relevan, karena SRT id juga identik timesmapnya"
    # Logic:
    #   - Original mode (Mode E/F): wajib SRT Indonesia (untuk ducking)
    #   - burn_srt (Mode B/D/F): wajib SRT Indonesia (untuk burn subtitle)
    #   - Original + Burn SRT (Mode F): SRT yang sama untuk duck + burn
    #   - Simple + Stream copy (Mode C): tidak butuh SRT
    #   - Full + Stream copy (Mode A): tidak butuh SRT
    srt_path = None  # SRT Indonesia (untuk duck + burn)
    duck_segments = None  # Segments untuk SRT-driven ducking (Original mode only)
    srt_position = 'top'  # default top supaya tidak overlap SRT Mandarin (kalau ada di video ori)
    video_bitrate = None  # Bitrate untuk burn SRT (Mode B/D/F only)
    need_srt_for_duck = original_mode  # Original mode butuh SRT untuk ducking
    need_srt_for_burn = burn_srt       # Burn SRT butuh SRT untuk hardsub
    if need_srt_for_duck or need_srt_for_burn:
        # Tentukan label prompt berdasarkan use case
        if need_srt_for_duck and need_srt_for_burn:
            # Mode F: Original + Burn SRT → 1 SRT untuk 2 tujuan
            prompt_label = 'File SRT Indonesia (untuk ducking + burn subtitle)'
        elif need_srt_for_duck:
            # Mode E: Original + Stream copy → SRT untuk ducking saja (no burn)
            prompt_label = 'File SRT Indonesia (untuk ducking MP3 ori)'
        else:
            # Mode B/D: Burn SRT saja (Full atau Simple), SRT untuk burn
            prompt_label = 'File SRT Indonesia (untuk burn subtitle)'
        print(f'▶ Step 4.6/{total}: Pilih SRT Indonesia')
        srt_path = select_file(prompt_label, ['srt'], search_dir=str(INPUT_DIR) if ensure_hdd() else None)
        if not srt_path:
            print('Batal.'); sys.exit(0)
        validate_input_file(srt_path, 'SRT Indonesia')
        print(f'  ✓ {srt_path}')

        # Parse SRT → duck segments kalau Original mode (untuk SRT-driven ducking)
        if original_mode:
            duck_segments = parse_srt_for_ducking(srt_path, lead_ms=100, tail_ms=100)
            print(f'  ℹ Parsed {len(duck_segments)} cues → ducking windows (untuk MP3 ori ducking)')
            if not duck_segments:
                print('  ⚠ Warning: Tidak ada cue di SRT. Ducking tidak akan bekerja (MP3 ori penuh).')
        print()

        # Step 4.7: Posisi SRT — hanya kalau burn_srt (untuk hardsub position)
        if burn_srt:
            print(f'▶ Step 4.7/{total}: Pilih posisi SRT Indonesia')
            # v3.3: Opsi A (di bawah Mandarin) + Opsi D (overlay di atas Mandarin)
            # Plus Justify=2 (center horizontal, fix bug rata kiri di Alignment=5)
            # SRT Mandarin biasanya hard-burn di bottom video ori (1-2 line)
            pos_choice = questionary.select(
                'Posisi SRT Indonesia:',
                choices=[
                    'Opsi A: Bawah Mandarin — Indonesia di paling bawah (REKOMENDASI)',
                    'Opsi D: Overlay atas Mandarin — Indonesia langsung di atas SRT Mandarin (offset 60px)',
                    'Opsi B: Atas frame — Indonesia di atas, jauh dari Mandarin',
                    'Opsi C: Tengah video — Indonesia di middle frame (bisa nutup wajah)',
                    'Custom margin (input manual MarginV pixel)',
                ],
                default='Opsi A: Bawah Mandarin — Indonesia di paling bawah (REKOMENDASI)',
            ).ask()
            if 'Opsi A' in pos_choice:
                # Indonesia di paling bawah, SRT Mandarin di atasnya (di bottom video ori)
                # Alignment=2 (bottom), MarginV=20 (menempel ke bawah)
                # Risk: jika SRT Mandarin 2 line, Indonesia bisa overlap. Tapi video ori
                # biasanya SRT Mandarin tidak terlalu ke bawah (ada margin built-in).
                srt_position = 'bottom:20'
            elif 'Opsi D' in pos_choice:
                # Indonesia langsung di atas Mandarin (overlay, di bottom region tapi offset)
                # Alignment=2 (bottom), MarginV=60 (turun lebih, di atas Mandarin)
                srt_position = 'bottom:60'
            elif 'Opsi B' in pos_choice:
                # Indonesia di atas frame, jauh dari Mandarin
                # Alignment=5 (top), MarginV=50 (buffer dari atas)
                srt_position = 'top:50'
            elif 'Opsi C' in pos_choice:
                # Middle video
                srt_position = 'middle'
            else:
                margin_v = questionary.text('MarginV (pixel, default 40):', default='40').ask()
                try:
                    srt_position = f'custom:{int(margin_v)}'
                except ValueError:
                    srt_position = 'custom:40'
            print(f'  ✓ {srt_position}')
            print()

            # Step 4.8: Video bitrate (v3.5) — muncul kalau burn_srt=True (Mode B/D/F)
            # Burn SRT wajib re-encode video → user pilih bitrate untuk hemat size
            # Mode A/C/E (stream copy) tidak perlu prompt — bitrate ikut MP4 ori
            print(f'▶ Step 4.8/{total}: Pilih video bitrate (untuk burn SRT)')
            video_bitrate = prompt_video_bitrate()
            print(f'  ✓ {video_bitrate}')
            print()

            # Step 4.9: Logo auto-detect (v3.8 NEW, muncul kalau burn_srt)
            # User tinggal taruh file "logo.png" di ~/Dubbing/ atau HDD/input/
            # Logo akan di-burn ke top-right video (10px margin)
            # Kalau tidak ada → skip logo (subtitle only, existing behavior)
            print(f'▶ Step 4.9/{total}: Logo detection (auto-detect)')
            logo_path = find_logo_file()
            if logo_path:
                logo_size_kb = os.path.getsize(logo_path) / 1024
                print(f'  ✓ Logo ditemukan: {logo_path} ({logo_size_kb:.1f} KB)')
                print(f'    Posisi: top-right (10px margin dari kanan atas)')
                print(f'    Size: 100x100 px (v3.8.2: scale di FFmpeg, sebelumnya 150px)')
                print(f'    Logo akan di-burn bersama subtitle')
            else:
                print(f'  ℹ Tidak ada logo di default path')
                print(f'    Untuk burn logo, taruh file "logo.png" di ~/Dubbing/ atau HDD/input/')
            print()
    # else: Mode A/C/E (Stream copy) — tidak ada Step 4.6/4.7/4.8/4.9 (no SRT needed for A/C, SRT only for duck in E)
    # Catatan: Mode E (Original + Stream copy) sudah dapat SRT di Step 4.6 untuk ducking, no need Step 4.7/4.8/4.9


    # Step 5: Output — default derive dari MP4 prefix (Bug #1 fix)
    # v3.4: suffix berdasarkan mode input (Full/Simple) + mode output (Stream/Burn)
    # v3.6: tambah Original mode → suffix -id-orig / -id-orig-sub
    # v3.7.4 FIX: default output pakai FULL PATH ke MIX_DIR (HDD), bukan hanya filename
    #            (sebelumnya output disimpan di cwd = SSD, user harus move manual ke HDD)
    print(f'▶ Step 5/{total}: Pilih nama output MP4')
    default_output = derive_default_output(mp4, lang='id')
    base = Path(default_output).stem  # tanpa .mp4
    # Suffix logic:
    # - Full + Stream copy: {prefix}-id-final.mp4 (existing, no change)
    # - Full + Burn SRT:    {prefix}-id-final-sub.mp4 (existing, no change)
    # - Simple + Stream:    {prefix}-id-simple.mp4 (v3.4)
    # - Simple + Burn SRT: {prefix}-id-simple-sub.mp4 (v3.4)
    # - Original + Stream:  {prefix}-id-orig.mp4 (v3.6 NEW)
    # - Original + Burn SRT: {prefix}-id-orig-sub.mp4 (v3.6 NEW)
    if original_mode:
        # Original mode: replace -final dengan -orig (atau -orig-sub kalau burn)
        if base.endswith('-id-final'):
            base = base[:-9]  # hapus -id-final
        if burn_srt:
            default_output = f'{base}-id-orig-sub.mp4'
        else:
            default_output = f'{base}-id-orig.mp4'
    elif simple_mode and burn_srt:
        # Simple + Burn: replace -final dengan -simple-sub
        if base.endswith('-id-final'):
            base = base[:-9]  # hapus -id-final
        default_output = f'{base}-id-simple-sub.mp4'
    elif simple_mode and not burn_srt:
        # Simple + Stream: replace -final dengan -simple
        if base.endswith('-id-final'):
            base = base[:-9]
        default_output = f'{base}-id-simple.mp4'
    elif burn_srt:
        # Full + Burn SRT (existing): -id-final-sub
        default_output = f'{base}-sub.mp4'
    # else: Full + Stream copy (existing): pakai default_output apa adanya (-id-final)

    # v3.7.4 FIX: prepend MIX_DIR (HDD) ke default_output
    # Sebelumnya: default = "S5-ori-id-final.mp4" → disimpan di cwd (SSD)
    # Sekarang: default = "/Volumes/HDD/Dubbing/mix/S5-ori-id-final.mp4" → disimpan di HDD
    # User tetap bisa edit prompt untuk path lain (mis. ke SSD kalau mau)
    if ensure_hdd():
        # HDD available → pakai MIX_DIR (HDD path dari config.py)
        default_output = str(MIX_DIR / default_output)
        print(f'  ℹ Default output: {default_output}')
        print(f'    (HDD path dari config.py — output langsung ke HDD, tidak perlu move manual)')
    else:
        # HDD tidak ter-colok → fallback ke cwd (SSD)
        print(f'  ⚠ HDD tidak ter-colok, output ke cwd (SSD): {default_output}')
        print(f'    Move manual ke HDD setelah selesai, atau colok HDD dulu.')

    output = prompt_output(default_output)
    # Expand user (~ → home) kalau ada, normalize path
    output = os.path.expanduser(output)
    # Pastikan directory output ada (buat kalau perlu)
    output_dir = os.path.dirname(output)
    if output_dir and not os.path.isdir(output_dir):
        try:
            os.makedirs(output_dir, exist_ok=True)
            print(f'  ℹ Created output dir: {output_dir}')
        except OSError as e:
            print(f'  ⚠ Gagal buat output dir: {e}')
    print(f'  ✓ {output}')
    print()

    # Step 6: Konfirmasi
    print(f'▶ Step 6/{total}: Konfirmasi')

    # Probe durations
    ffmpeg = find_ffmpeg()
    ffprobe = find_ffprobe()
    mp4_dur = get_duration(ffprobe, mp4)
    sfx_dur = get_duration(ffprobe, sfx_wav) if sfx_wav else 0
    dub_dur = get_duration(ffprobe, audio_dub)

    print()
    print('╔' + '═' * 64 + '╗')
    print('║  📋 Ringkasan:' + ' ' * 49 + '║')
    print('╠' + '═' * 64 + '╣')
    print(f'║  MP4      : {mp4[:46]:<46}║')
    if simple_mode:
        print(f'║  SFX      : [SKIP — Simple mode, no SFX]                    ║')
    elif original_mode:
        print(f'║  MP3 ori  : {sfx_wav[:46]:<46}║')  # ganti label 'SFX' jadi 'MP3 ori' untuk Original mode
    else:
        print(f'║  SFX      : {sfx_wav[:46]:<46}║')
    print(f'║  Audio dub: {audio_dub[:46]:<46}║')
    print(f'║  Output   : {output[:46]:<46}║')
    if simple_mode:
        print(f'║  Ducking  : [SKIP — dub copy as-is]                       ║')
    elif original_mode:
        # v3.7: Original mode pakai SRT-driven ducking (-24 dB fixed)
        duck_info = f'SRT-driven -24 dB ({len(duck_segments) if duck_segments else 0} cues)'
        print(f'║  Ducking  : {duck_info[:46]:<46}║')
    else:
        print(f'║  Ducking  : {str(ducking_db) + " dB":<46}║')
    if simple_mode:
        mode_input_label = 'Simple (no SFX)'
    elif original_mode:
        mode_input_label = 'Original (SRT-driven duck)'
    else:
        mode_input_label = 'Full (SFX+Dub)'
    mode_output_label = f'Burn SRT {srt_position}' if burn_srt else 'Stream copy'
    mode_label = f'{mode_input_label} | {mode_output_label}'
    print(f'║  Mode     : {mode_label[:46]:<46}║')
    # v3.7.1: 1 SRT Indonesia untuk duck + burn (kalau Original mode atau burn_srt)
    if srt_path:
        # Tentukan label berdasarkan use case
        if original_mode and burn_srt:
            srt_label = 'SRT duck+burn'
        elif original_mode:
            srt_label = 'SRT duck  '
        else:
            srt_label = 'SRT burn  '
        print(f'║  {srt_label}: {os.path.basename(srt_path)[:46]:<46}║')
    if burn_srt and video_bitrate:
        # v3.5: tampilkan video bitrate kalau burn SRT (Mode B/D/F)
        bitrate_display = f'{video_bitrate} (target bitrate)'
        print(f'║  Bitrate  : {bitrate_display[:46]:<46}║')
    # v3.8: tampilkan Logo bar kalau ada (Mode B/D/F dengan logo)
    if logo_path:
        print(f'║  Logo     : {os.path.basename(logo_path)[:46]:<46}║')
    print(f'║  MP4 dur  : {format_duration(mp4_dur):<46}║')
    if not simple_mode:
        # Original mode: label durasi = 'MP3 ori dur'; Full mode: 'SFX dur'
        dur_label = 'MP3 dur' if original_mode else 'SFX dur'
        print(f'║  {dur_label}  : {format_duration(sfx_dur):<46}║')
    print(f'║  Dub dur  : {format_duration(dub_dur):<46}║')
    print('╚' + '═' * 64 + '╝')
    print()

    # === Bug #5 fix: warning prominent kalau dub < 90% MP4 dur ===
    # v3.4: kalau Simple mode (no SFX), warning lebih kritikal karena
    # setelah dub selesai → SILENCE (bukan SFX) sampai MP4 selesai.
    # v3.6: Original mode — MP3 ori (vokal+SFX) tetap bermain setelah dub selesai (sama dengan Full mode)
    if mp4_dur > 0 and dub_dur > 0:
        ratio = dub_dur / mp4_dur
        if ratio < 0.9:
            print('═' * 64)
            print('⚠  WARNING: Audio dub lebih pendek dari MP4!')
            print('═' * 64)
            print(f'  MP4 dur : {format_duration(mp4_dur)}')
            print(f'  Dub dur : {format_duration(dub_dur)} ({ratio*100:.1f}% dari MP4)')
            print(f'  Setelah dub selesai (di {format_duration(dub_dur)}),')
            if simple_mode:
                print(f'  → SILENCE (tidak ada SFX) sampai MP4 selesai!')
                print(f'    Simple mode tidak ada SFX fallback — dub harus full durasi.')
            else:
                # Full mode (SFX) atau Original mode (MP3 ori vokal+musik) tetap bermain
                if original_mode:
                    print(f'  → MP3 ori (vokal+SFX+musik) tetap bermain sampai MP4 selesai.')
                    print(f'    Original mode: dialog asli vokal Mandarin akan terdengar setelah dub selesai.')
                else:
                    print(f'  → hanya SFX (no_vocals) yang bermain sampai MP4 selesai.')
            print()
            print(f'  Kemungkinan sebab:')
            print(f'   - Generate TTS gagal di tengah (cek .cache/ untuk resume)')
            print(f'   - SRT hanya sampai {format_duration(dub_dur)} (bukan masalah)')
            print()
            if not questionary.confirm('Tetap lanjut mix?', default=False).ask():
                print('Batal. Cek file dub dulu.'); sys.exit(0)
            print()
        elif ratio < 1.0:
            print(f'  ℹ Audio dub ({format_duration(dub_dur)}) sedikit lebih pendek dari MP4 ({format_duration(mp4_dur)}).')
            if simple_mode:
                print(f'    Setelah dub selesai → SILENCE sampai MP4 selesai.')
            else:
                print(f'    Setelah dub selesai, hanya SFX yang bermain.')
            print()
    elif mp4_dur > 0 and dub_dur == 0:
        print(f'  ⚠ Audio dur 0 — mungkin file corrupt atau ffprobe gagal baca.')
        print()
        if not questionary.confirm('Tetap lanjut mix?', default=False).ask():
            sys.exit(0)
        print()

    confirm = questionary.confirm('Lanjut eksekusi?', default=True).ask()
    if not confirm:
        print('Batal.'); sys.exit(0)

    # === Build FFmpeg command (v3.4: 4 kombinasi mode) ===
    # Indeks input:
    # - Full mode:     0=mp4 (video), 1=sfx_wav (no_vocals), 2=audio_dub
    # - Original mode: 0=mp4 (video), 1=sfx_wav (MP3 ori), 2=audio_dub
    # - Simple mode:   0=mp4 (video), 1=audio_dub (NO SFX)
    if simple_mode:
        mode_input_name = 'Simple'
    elif original_mode:
        mode_input_name = 'Original'
    else:
        mode_input_name = 'Full'
    mode_name = f'{mode_input_name} + {"Burn SRT" if burn_srt else "Stream copy"}'
    print('\n' + '═' * 64)
    print(f'🚀 Mulai mix... (mode: {mode_name})')
    print('═' * 64 + '\n')

    # Audio filter build — v3.7: 3 jenis ducking strategy
    # - Simple mode: dub copy as-is (no filter, no ducking)
    # - Full mode: sidechain compress (existing, ducking_db dari prompt)
    # - Original mode v3.7.3: SRT-driven ducking via envelope WAV + sidechain compress
    #   (sebelumnya v3.7 pakai nested if expression, FFmpeg gagal parse untuk 4857 cues)
    audio_filter = None
    envelope_wav_path = None  # v3.7.3: path file envelope WAV (cleanup setelah FFmpeg)
    if simple_mode:
        # Simple: no audio filter (dub copy as-is)
        pass
    elif original_mode:
        # v3.7.6 NEW: MUTE COMPLETE via amultiply + inverted envelope
        # v3.7.5 cascade sidechain masih gradual (67% reduction) — user mau MUTE TOTAL
        # v3.7.6: amultiply (multiply sample-by-sample) → MP3 ori * 0 = MUTE saat cue
        # Test sandbox: MP3 ori cue reduction 99.9% (mag 154 floating noise, true MUTE)
        # Saat cue aktif → envelope=0 → MP3 ori * 0 = MUTE complete
        # Saat gap → envelope=1 → MP3 ori * 1 = NORMAL
        # v3.8.1: 100ms smooth fade di boundary (user request "transisi mulus, jangan kaget")
        # Input index: 0=mp4, 1=sfx_wav (MP3 ori), 2=audio_dub, 3=envelope_wav (inverted: 0=cue, 1=gap)
        if duck_segments:
            import tempfile
            # Generate envelope WAV INVERTED (0=cue mute, 1=gap normal) untuk amultiply
            envelope_wav_path = tempfile.mktemp(prefix='mix_tui_envelope_', suffix='.wav')
            print(f'  📄 Generate envelope WAV untuk SRT-driven MUTE (amultiply approach)...')
            envelope_wav_path = generate_duck_envelope_wav(
                duck_segments, mp4_dur, envelope_wav_path,
                duck_value=0.0, normal_value=1.0,  # INVERTED: 0=cue (mute), 1=gap (normal)
                fade_ms=100, sample_rate=44100  # v3.8.1: 100ms smooth fade (sebelumnya 1ms hard switch)
            )
            if envelope_wav_path:
                envelope_size_kb = os.path.getsize(envelope_wav_path) / 1024
                total_cue_dur = sum(e - s for s, e in duck_segments)
                cue_coverage = total_cue_dur / mp4_dur * 100 if mp4_dur > 0 else 0
                print(f'     ✓ {envelope_wav_path}')
                print(f'     Size: {envelope_size_kb:.1f} KB ({len(duck_segments)} cues, {mp4_dur:.0f}s audio)')
                print(f'     Cue coverage: {total_cue_dur:.0f}s / {mp4_dur:.0f}s = {cue_coverage:.1f}%')
                if cue_coverage > 80:
                    print(f'     ⚠ Warning: Cue coverage >80% — film dialog sangat padat.')
                    print(f'       MP3 ori akan sering di-MUTE, mungkin tidak ada banyak gap "normal".')
                # v3.7.6: amultiply (hard mute, no gradual reduction)
                # [1:a] = MP3 ori, [3:a] = envelope_inverted (0=cue, 1=gap)
                # amultiply: sample-by-sample multiplication
                # MP3_ori * envelope = MP3_ori saat gap (1), 0 saat cue (MUTE)
                # Need aformat untuk match sample format + channel layout
                audio_filter = (
                    f'[1:a]aformat=sample_fmts=s16:channel_layouts=mono[mp3_fmt];'
                    f'[3:a]aformat=sample_fmts=s16:channel_layouts=mono[env_fmt];'
                    f'[mp3_fmt][env_fmt]amultiply[sfx_muted];'
                    f'[2:a]volume=1[dub];'
                    f'[sfx_muted][dub]amix=inputs=2:duration=longest:normalize=0[aout]'
                )
                print(f'  ℹ v3.7.6: amultiply hard mute (MUTE COMPLETE saat cue, NORMAL saat gap)')
                print(f'     MP3 ori * envelope_inverted = MUTE saat cue, normal saat gap')
                print(f'     Fade 100ms di boundary untuk smooth transition (v3.8.1: transisi mulus, no "kaget")')
            else:
                # Fallback: no ducking (kalau envelope generate gagal)
                print(f'  ⚠ Envelope generate gagal, fallback: no ducking (MP3 ori penuh)')
                audio_filter = (
                    '[1:a]volume=1[sfx];'
                    '[2:a]volume=1[dub];'
                    '[sfx][dub]amix=inputs=2:duration=longest:normalize=0[aout]'
                )
        else:
            # No SRT cues → no ducking (fallback)
            audio_filter = (
                '[1:a]volume=1[sfx];'
                '[2:a]volume=1[dub];'
                '[sfx][dub]amix=inputs=2:duration=longest:normalize=0[aout]'
            )
    else:
        # Full mode: sidechain compress (existing behavior)
        if ducking_db <= 0:
            audio_filter = (
                '[1:a]volume=1[sfx];'
                '[2:a]volume=1[dub];'
                '[sfx][dub]amix=inputs=2:duration=longest:normalize=0[aout]'
            )
        else:
            ratio_compress = 10 if ducking_db >= 10 else 5
            audio_filter = (
                f'[1:a]volume=1[sfx];'
                f'[2:a]volume=1,asplit=2[dub][sidechain];'
                f'[sfx][sidechain]sidechaincompress='
                f'threshold=0.05:ratio={ratio_compress}:attack=5:release=300'
                f'[ducked_sfx];'
                f'[ducked_sfx][dub]amix=inputs=2:duration=longest:normalize=0[aout]'
            )

    # v3.7.3: Hapus filter_file_path logic (diganti dengan envelope WAV approach)
    # Original mode sekarang pakai envelope WAV + sidechain compress (no big expression)
    # audio_filter sudah inline kecil (~150 chars), no need for file temp

    if not burn_srt:
        # === Stream copy (3 menit, no SRT) — Mode A/C/E ===
        if not simple_mode:
            # Full + Stream copy (A) / Original + Stream copy (E): 3 input + audio filter
            # v3.7.3: Original mode butuh input ke-4 (envelope WAV) untuk sidechain compress
            if original_mode and envelope_wav_path:
                # Mode E dengan envelope WAV → 4 input (mp4 + sfx + dub + envelope)
                cmd = [ffmpeg, '-y', '-i', mp4, '-i', sfx_wav, '-i', audio_dub, '-i', envelope_wav_path,
                       '-filter_complex', audio_filter,
                       '-map', '0:v', '-map', '[aout]',
                       '-c:v', 'copy', '-c:a', 'aac', '-b:a', '192k',
                       '-movflags', '+faststart', output]
                print(f'Command: ffmpeg -i mp4 -i sfx -i dub -i envelope -filter_complex ... -c:v copy -c:a aac -b:a 192k {output}')
            else:
                # Mode A (Full) atau Mode E tanpa envelope (fallback) → 3 input
                filter_complex = audio_filter
                cmd = [ffmpeg, '-y', '-i', mp4, '-i', sfx_wav, '-i', audio_dub,
                       '-filter_complex', filter_complex,
                       '-map', '0:v', '-map', '[aout]',
                       '-c:v', 'copy', '-c:a', 'aac', '-b:a', '192k',
                       '-movflags', '+faststart', output]
                print(f'Command: ffmpeg ... -c:v copy -c:a aac -b:a 192k {output}')
        else:
            # Simple + Stream copy (C): 2 input (mp4 + dub), no filter, dub copy as-is
            cmd = [ffmpeg, '-y', '-i', mp4, '-i', audio_dub,
                   '-map', '0:v', '-map', '1:a',
                   '-c:v', 'copy', '-c:a', 'aac', '-b:a', '192k',
                   '-movflags', '+faststart', output]
            print(f'Command: ffmpeg ... -c:v copy -c:a aac -b:a 192k {output} (Simple, no SFX, no filter)')
    else:
        # === Burn SRT (re-encode video, VideoToolbox M1 hardware) — Mode B/D/F ===
        # Build subtitle filter dengan force_style untuk posisi + style
        # ASS Alignment (libass/ffmpeg spec, verified 13 Okt 2026):
        #   1 = bottom-left, 2 = bottom-center, 3 = bottom-right
        #   4 = top-left,    5 = top-center,    6 = top-right  ← TOP pakai 5 (BUKAN 8)
        #   7 = middle-left, 8 = middle-center, 9 = middle-right  ← MIDDLE pakai 8
        # Bug v3.0: Alignment=8 untuk top → SALAH (aktual middle)
        # Fix v3.1: top → Alignment=5, middle → Alignment=8
        # v3.2: format posisi 'top:NN' (custom MarginV)
        # v3.3: format 'bottom:NN' + Justify=2 (fix bug rata kiri di Alignment=5)
        #   Justify=0 (left), 1 (right), 2 (center). Default libass:
        #   - Alignment=2 → center (default OK)
        #   - Alignment=5 → LEFT (BUG, harus pakai Justify=2 untuk center)
        if srt_position.startswith('top:'):
            alignment = 5
            margin_v = int(srt_position.split(':')[1])
        elif srt_position == 'top':
            alignment = 5
            margin_v = 20
        elif srt_position.startswith('bottom:'):
            alignment = 2
            margin_v = int(srt_position.split(':')[1])
        elif srt_position == 'bottom':
            alignment = 2
            margin_v = 20
        elif srt_position == 'middle':
            alignment = 8
            margin_v = 0
        else:
            # custom:XXXX — user input margin pixel, default bottom alignment
            alignment = 2
            margin_v = int(srt_position.split(':')[1]) if ':' in srt_position else 40

        # Escape path untuk filter subtitles (escape colon, backslash, dan single quote)
        srt_escaped = srt_path.replace('\\', '\\\\').replace(':', '\\:').replace("'", "\\'")

        # Style ASS: font 18, putih outline hitam, Alignment + MarginV
        # FontName biarkan default (sans-serif), FontSize=18
        # Outline=2 (outline tebal), BorderStyle=1 (outline + shadow)
        # Shadow=1 (shadow 1 pixel)
        # Justify=2 (center horizontal) — fix bug Alignment=5 rata kiri (v3.3)
        #   Justify=0 (left), 1 (right), 2 (center)
        #   Default libass: Alignment=2 → center OK, Alignment=5 → LEFT (bug)
        #   Pakai Justify=2 untuk SEMUA alignment supaya text selalu center horizontal
        force_style = (
            f"Fontsize=18,"
            f"PrimaryColour=&H00FFFFFF,"  # putih (ASS BGR: &H00BBGGRR)
            f"OutlineColour=&H80000000,"  # hitam semi-transparan
            f"BorderStyle=1,"
            f"Outline=2,"
            f"Shadow=1,"
            f"Alignment={alignment},"
            f"MarginV={margin_v},"
            f"Justify=2"  # v3.3 fix: rata tengah horizontal (fix rata kiri di Alignment=5)
        )

        # Filter: [0:v] + subtitles → [vout]
        # subtitles filter butuh file path (escape), force_style untuk styling
        # v3.8: kalau ada logo, chain subtitle + overlay → output label 'vout' (tetap sama)
        if logo_path:
            # v3.8: Chain subtitle + logo overlay
            # [0:v]subtitles='...'[vsub];[vsub][logo_idx:v]overlay=top-right[vout]
            # Logo input index tergantung mode (Mode F: 4, Mode B/D: 3 atau 2)
            subtitle_filter = f"[0:v]subtitles='{srt_escaped}':force_style='{force_style}'[vsub]"
            # Logo overlay akan ditambah di cmd build (perlu tahu index input logo)
        else:
            # No logo → subtitle only (existing behavior)
            subtitle_filter = f"[0:v]subtitles='{srt_escaped}':force_style='{force_style}'[vout]"

        if not simple_mode:
            # Full + Burn SRT (B) / Original + Burn SRT (F): 3 input + audio_filter + subtitle_filter
            # v3.7.3: Original mode butuh input ke-4 (envelope WAV) untuk sidechain compress
            # v3.8: kalau ada logo, tambah 1 input lagi (logo PNG)
            if original_mode and envelope_wav_path:
                # Mode F dengan envelope WAV → 4 input (mp4 + sfx + dub + envelope)
                # v3.8: + logo → 5 input (mp4 + sfx + dub + envelope + logo)
                if logo_path:
                    # Mode F + logo: 5 input
                    # Input index: 0=mp4, 1=sfx, 2=dub, 3=envelope, 4=logo
                    overlay_filter, _ = build_logo_overlay_filter(
                        logo_path, logo_input_index=4,
                        base_filter_output_label='vsub', final_output_label='vout'
                    )
                    filter_complex = audio_filter + ';' + subtitle_filter + ';' + overlay_filter
                    cmd = [ffmpeg, '-y', '-i', mp4, '-i', sfx_wav, '-i', audio_dub,
                           '-i', envelope_wav_path, '-i', logo_path,
                           '-filter_complex', filter_complex,
                           '-map', '[vout]', '-map', '[aout]',
                           '-c:v', 'h264_videotoolbox', '-b:v', video_bitrate,
                           '-c:a', 'aac', '-b:a', '192k',
                           '-movflags', '+faststart', output]
                else:
                    # Mode F tanpa logo → 4 input (existing)
                    filter_complex = audio_filter + ';' + subtitle_filter
                    cmd = [ffmpeg, '-y', '-i', mp4, '-i', sfx_wav, '-i', audio_dub, '-i', envelope_wav_path,
                           '-filter_complex', filter_complex,
                           '-map', '[vout]', '-map', '[aout]',
                           '-c:v', 'h264_videotoolbox', '-b:v', video_bitrate,
                           '-c:a', 'aac', '-b:a', '192k',
                           '-movflags', '+faststart', output]
            else:
                # Mode B (Full) atau Mode F tanpa envelope (fallback) → 3 input
                # v3.8: + logo → 4 input (mp4 + sfx + dub + logo)
                if logo_path:
                    # Mode B + logo: 4 input
                    # Input index: 0=mp4, 1=sfx, 2=dub, 3=logo
                    overlay_filter, _ = build_logo_overlay_filter(
                        logo_path, logo_input_index=3,
                        base_filter_output_label='vsub', final_output_label='vout'
                    )
                    filter_complex = audio_filter + ';' + subtitle_filter + ';' + overlay_filter
                    cmd = [ffmpeg, '-y', '-i', mp4, '-i', sfx_wav, '-i', audio_dub,
                           '-i', logo_path,
                           '-filter_complex', filter_complex,
                           '-map', '[vout]', '-map', '[aout]',
                           '-c:v', 'h264_videotoolbox', '-b:v', video_bitrate,
                           '-c:a', 'aac', '-b:a', '192k',
                           '-movflags', '+faststart', output]
                else:
                    # Mode B tanpa logo → 3 input (existing)
                    filter_complex = audio_filter + ';' + subtitle_filter
                    cmd = [ffmpeg, '-y', '-i', mp4, '-i', sfx_wav, '-i', audio_dub,
                           '-filter_complex', filter_complex,
                           '-map', '[vout]', '-map', '[aout]',
                           '-c:v', 'h264_videotoolbox', '-b:v', video_bitrate,
                           '-c:a', 'aac', '-b:a', '192k',
                           '-movflags', '+faststart', output]
        else:
            # Simple + Burn SRT (D): 2 input + subtitle_filter only (no audio filter)
            # Audio dub map langsung (index 1), tidak ada audio processing
            # v3.8: + logo → 3 input (mp4 + dub + logo)
            if logo_path:
                # Mode D + logo: 3 input
                # Input index: 0=mp4, 1=dub, 2=logo
                overlay_filter, _ = build_logo_overlay_filter(
                    logo_path, logo_input_index=2,
                    base_filter_output_label='vsub', final_output_label='vout'
                )
                filter_complex = subtitle_filter + ';' + overlay_filter
                cmd = [ffmpeg, '-y', '-i', mp4, '-i', audio_dub, '-i', logo_path,
                       '-filter_complex', filter_complex,
                       '-map', '[vout]', '-map', '1:a',
                       '-c:v', 'h264_videotoolbox', '-b:v', video_bitrate,
                       '-c:a', 'aac', '-b:a', '192k',
                       '-movflags', '+faststart', output]
            else:
                # Mode D tanpa logo → 2 input (existing)
                filter_complex = subtitle_filter
                cmd = [ffmpeg, '-y', '-i', mp4, '-i', audio_dub,
                       '-filter_complex', filter_complex,
                       '-map', '[vout]', '-map', '1:a',
                       '-c:v', 'h264_videotoolbox', '-b:v', video_bitrate,
                       '-c:a', 'aac', '-b:a', '192k',
                       '-movflags', '+faststart', output]

        print(f'Command: ffmpeg ... -c:v h264_videotoolbox -b:v {video_bitrate} -c:a aac -b:a 192k {output}')
        print(f'  SRT path : {srt_path}')
        print(f'  Posisi   : {srt_position} (Alignment={alignment}, MarginV={margin_v})')
        print(f'  Style    : font 18pt, putih outline hitam, VideoToolbox M1 hardware')
        if simple_mode:
            mode_print = 'Simple (no SFX)'
        elif original_mode:
            mode_print = 'Original (MP3 ori+Dub, ducking)'
        else:
            mode_print = 'Full (SFX+Dub)'
        print(f'  Mode     : {mode_print}')
        print(f'  Bitrate  : {video_bitrate} (target) — size estimasi {"~1.2 GB/2jam" if video_bitrate == "1M" else "~1.8 GB/2jam" if video_bitrate == "1.5M" else "~2.3 GB/2jam" if video_bitrate == "2M" else "~4.5 GB/2jam"}')
        print(f'  Estimasi : ~4-6 menit untuk 2 jam video (M1 VideoToolbox 35x hardware)')
    print()
    print('Progress:')
    print()

    try:
        # Bug #8 fix: progress bar real-time
        exit_code = run_ffmpeg_with_progress(cmd, mp4_dur)
    except KeyboardInterrupt:
        print('\n\n⏹ Dibatalkan user.')
        # Hapus output partial
        if os.path.isfile(output):
            try:
                os.unlink(output)
                print(f'Partial output dihapus: {output}')
            except OSError:
                pass
        # v3.7.3: cleanup envelope WAV temp file (kalau ada)
        if envelope_wav_path and os.path.isfile(envelope_wav_path):
            try:
                os.unlink(envelope_wav_path)
            except OSError:
                pass
        sys.exit(130)

    # v3.7.3: cleanup envelope WAV temp file setelah FFmpeg selesai (success atau fail)
    if envelope_wav_path and os.path.isfile(envelope_wav_path):
        try:
            os.unlink(envelope_wav_path)
        except OSError:
            pass

    print()
    if exit_code == 0 and os.path.isfile(output):
        out_size = os.path.getsize(output) / 1024 / 1024
        out_dur = get_duration(ffprobe, output)
        print('═' * 64)
        print('✅ SELESAI!')
        print(f'   Output: {output}')
        print(f'   Size: {out_size:.1f} MB')
        print(f'   Duration: {format_duration(out_dur)}')
        print()
        print('🎬 Langkah berikutnya:')
        print(f'   1. Preview: open {output} di QuickTime / VLC')
        print(f'   2. Kalau perlu edit (sfx level, dub per cue): DaVinci Resolve')
        print(f'   3. Upload: langsung publish ke platform (TikTok/IG/YouTube)')
        print(f'   4. Split per episode (opsional): ffmpeg -ss 0 -t 1800 -c copy ep01.mp4')
        print('═' * 64)
    else:
        print('═' * 64)
        print(f'❌ GAGAL dengan exit code {exit_code}')
        print()
        # v3.7.3: jalankan ulang FFmpeg dengan stderr di-print untuk debug
        print('🔍 FFmpeg stderr (untuk debug):')
        print('─' * 64)
        try:
            debug_cmd = cmd + ['-v', 'error']  # verbose error
            # Hapus output file dari cmd supaya tidak overwrite existing
            # Cari output path (argumen terakhir yang bukan flag)
            # Sebenarnya cmd terakhir = output, kita ganti ke /dev/null untuk debug
            # Tapi lebih simple: jalankan ulang, capture stderr, print
            debug_result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            # Print stderr (FFmpeg error messages)
            stderr_lines = debug_result.stderr.strip().split('\n')
            # Print last 30 lines supaya tidak terlalu panjang
            for line in stderr_lines[-30:]:
                print(f'  {line}')
        except Exception as e:
            print(f'  Tidak bisa capture stderr: {e}')
        print('─' * 64)
        print()
        print('Cek error message di atas. Umumnya:')
        print('  - "No such file" → file input hilang atau path salah')
        print('  - "Invalid data found" → file corrupt, coba re-generate')
        print('  - "Cannot allocate memory" → audio terlalu panjang, split dulu')
        print('  - "Filter not found" → nama filter salah atau ffmpeg versi lama')
        print('  - "Invalid argument" → filter syntax error')
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
