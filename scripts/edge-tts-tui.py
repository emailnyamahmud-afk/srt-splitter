#!/usr/bin/env python3
"""
edge-tts-tui.py v7.4 — TUI Generate TTS dari SRT dengan Edge TTS (lokal, gratis)

v7.4 update (26 Okt 2026) — Paralel support:
  FIX: User mau generate 2 TTS paralel di Mac 16GB (jam 22:00 → pagi ready 2 file).
  Solusi: lock file + prefix auto-suggest + 429 retry + PID display.

  Strategi tetap flat di TTS_DIR (backward compatible dengan mix-tui.py v3.8.1
  yang cari dub di TTS_DIR root dengan glob non-recursive).

  Yang baru di v7.4:
  - Lock file: tts/.{prefix}.lock dengan PID — detect kalau prefix dipakai process lain
  - Prefix auto-suggest: kalau collision → tanya "ganti jadi {prefix}-2?"
  - PID display di header (tracking paralel di Activity Monitor)
  - 429 retry: 30s → 60s → 120s → skip + log (auto-recover kalau Microsoft throttle)
  - Lock file stale detection: kalau PID mati, hapus lock otomatis

v7.3.1 (sebelumnya):
  Pengganti Mode ON di web app untuk audio panjang (>30 menit).
  Web app Vercel punya limit:
  - maxDuration 60s per request
  - Microsoft Edge TTS rate-limit kalau banyak request cepat (429)
  - ZIP building OOM di browser
  - Tidak bisa resume kalau tab crash

  Algorithm (port dari web app src/lib/tts.ts narrateEntries Mode ON + Smart Fit):
  1. Parse SRT → entries (start, end, text)
  2. Per cue: generate natural TTS (rate +0%)
  3. Trim silence (asymmetric, voicertool pattern)
  4. Hitung need = naturalDur / cueDur
  5. Kalau need <= 1.0 → pakai natural
  6. Kalau need > 1.0 → re-generate dengan rate = min(need, cap)*100%
  7. Peak normalize -2 dBFS
  8. Stitch ke buffer pada cue.start (mix additive)
  9. Crossfade 150ms kalau audio overflow cue next
  10. Output: WAV 24kHz mono 16-bit

Per-cue cache di {output_dir}/.cache/{prefix}-cue-{NNN}-{hash}.mp3
- Kalau cache ada + text sama → skip generate (resume support)
- Kalau text beda → hapus cache lama, generate baru

PARALEL WORKFLOW (v7.4):
  2 instance dengan SRT berbeda → masing-masing punya prefix unik → aman
  2 instance dengan SRT sama → TUI auto-suggest prefix-2 → user tinggal Enter

  RAM per instance ~1.6 GB (untuk 4 jam audio)
  Mac 16GB: aman untuk 3 paralel (sisa ~11GB untuk OS + browser)
  Mac 8GB: batasi 2 paralel

Install:
  pip3 install edge-tts questionary
  # Optional: numpy untuk normalize (kalau tidak ada, pakai pure Python)

Usage:
  python3 edge-tts-tui.py
  (pilih SRT, output dir, voice, cap → generate → WAV)

Output:
  {output_dir}/{prefix}-audio-id-dub.wav   (WAV 24kHz mono 16-bit)
  {output_dir}/.cache/{prefix}-cue-*.mp3   (per-cue cache, bisa dihapus)
  {output_dir}/.{prefix}.lock              (lock file, auto-delete saat selesai)
"""

import os
import sys
import re
import json
import shutil
import subprocess
import hashlib
import time
import wave
import struct
from pathlib import Path
from datetime import datetime, timedelta

# === Version + paralel constants ===
VERSION = 'v7.4'
# 429 retry backoff schedule (detik). Total max ~3.5 menit per cue kalau semua gagal.
RATE_LIMIT_BACKOFF = [30, 60, 120]

# v7.4: Module-level lock state — di-set saat acquire_lock sukses,
# di-release saat main() selesai normal ATAU KeyboardInterrupt/exception.
# Format: (output_dir, prefix) atau None kalau belum acquire.
_ACTIVE_LOCK = None

# Track missing deps untuk pesan error komprehensif
_MISSING_DEPS = []

try:
    import questionary
except ImportError:
    _MISSING_DEPS.append('questionary')

try:
    import edge_tts
except ImportError:
    _MISSING_DEPS.append('edge-tts')

try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False
    if not _MISSING_DEPS:
        # numpy opsional — warning saja, bukan fatal
        print('⚠ numpy belum terinstall. Pakai pure Python (lambat untuk audio >2 jam).')
        print('   Install recommended: pip3 install numpy')
        print()
    else:
        # Kalau ada deps wajib yang missing, tampilkan numpy juga supaya user install sekali jalan
        _MISSING_DEPS.append('numpy')

if _MISSING_DEPS:
    print()
    print('═' * 64)
    print('❌ Dependensi belum lengkap!')
    print('═' * 64)
    print()
    print(f'   Missing: {", ".join(_MISSING_DEPS)}')
    print()
    print('   Install dengan:')
    print()
    print('   pip3 install ' + ' '.join(_MISSING_DEPS))
    print()
    print('   Atau install semua deps sekaligus:')
    print()
    print('   pip3 install edge-tts questionary numpy')
    print()
    print('   Kalau pip3 ditolak (Mac blocked), pakai --break-system-packages:')
    print()
    print('   pip3 install --break-system-packages edge-tts questionary numpy')
    print()
    print('   Verifikasi:')
    print()
    print('   python3 -c "import edge_tts, questionary, numpy; print(\'OK\')"')
    print()
    print('═' * 64)
    sys.exit(1)

# ffmpeg juga wajib (dipakai untuk decode MP3 → PCM)
if not shutil.which('ffmpeg'):
    print()
    print('═' * 64)
    print('❌ ffmpeg belum terinstall!')
    print('═' * 64)
    print()
    print('   Install dengan Homebrew:')
    print()
    print('   brew install ffmpeg')
    print()
    print('   Verifikasi: ffmpeg -version')
    print()
    print('═' * 64)
    sys.exit(1)


# ============================================================
# Constants — match web app src/lib/tts.ts
# ============================================================

OUTPUT_SAMPLE_RATE = 24000  # match web app
OUTPUT_CHANNELS = 1       # mono
OUTPUT_BITS = 16           # 16-bit PCM

CROSSFADE_MS = 150          # ms, match web app
TRIM_HEAD_DB = -30          # dB, asymmetric trim head (web app: -30)
TRIM_TAIL_DB = -30          # dB, asymmetric trim tail (web app: -30)
TRIM_PADDING_MS = 30        # ms, padding setelah trim

NORMALIZE_DBFS = -2.0      # peak normalize target (match web app)
NOISE_FLOOR_DB = -50.0     # match web app

# Edge TTS voices — 4 pilihan (match web app EDGE_VOICES)
# Format label: nama + bahasa + gender, urutan: Indonesia dulu (laki-perempuan), lalu Jawa
EDGE_VOICES = [
    ('id-ID-ArdiNeural',  'Ardi  — Indonesia, laki-laki'),
    ('id-ID-GadisNeural', 'Gadis — Indonesia, perempuan'),
    ('jv-ID-DimasNeural', 'Dimas — Jawa, laki-laki'),
    ('jv-ID-SitiNeural',  'Siti  — Jawa, perempuan'),
]

DEFAULT_VOICE = 'id-ID-ArdiNeural'


# ============================================================
# SRT parsing — port dari src/lib/srt.ts
# ============================================================

def parse_srt(content: str):
    """Parse SRT content → list of {index, start, end, textLines}."""
    entries = []
    # Normalize line endings
    content = content.replace('\r\n', '\n').replace('\r', '\n')
    # Split by blank line
    blocks = re.split(r'\n\s*\n', content.strip())
    for block in blocks:
        lines = block.strip().split('\n')
        if len(lines) < 2:
            continue
        # Skip index line (optional)
        idx = 0
        if re.match(r'^\d+$', lines[0]):
            idx_line = int(lines[0])
            idx = idx_line - 1
            time_line = lines[1] if len(lines) > 1 else ''
            text_lines = lines[2:] if len(lines) > 2 else []
        else:
            time_line = lines[0]
            text_lines = lines[1:]
        # Parse time: 00:01:23,456 --> 00:01:25,789
        m = re.match(
            r'(\d{2}):(\d{2}):(\d{2})[,.](\d{3})\s*-->\s*(\d{2}):(\d{2}):(\d{2})[,.](\d{3})',
            time_line,
        )
        if not m:
            continue
        h1, m1, s1, ms1, h2, m2, s2, ms2 = map(int, m.groups())
        start = h1 * 3600 + m1 * 60 + s1 + ms1 / 1000.0
        end = h2 * 3600 + m2 * 60 + s2 + ms2 / 1000.0
        text = '\n'.join(text_lines).strip()
        if not text:
            continue
        entries.append({
            'index': idx,
            'start': start,
            'end': end,
            'textLines': text.split('\n'),
            'text': text,
        })
    return entries


def format_timestamp(seconds: float) -> str:
    """Format seconds → SRT timestamp (HH:MM:SS,mmm)."""
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    ms = int((seconds - int(seconds)) * 1000)
    return f'{h:02d}:{m:02d}:{s:02d},{ms:03d}'


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


# ============================================================
# Text normalization — match src/lib/tts.ts normalizeTtsText
# ============================================================

def normalize_tts_text(text: str) -> str:
    """Strip aksen Jawa (é/è/ê → e) supaya Edge TTS bisa baca."""
    return (
        text.replace('é', 'e').replace('è', 'e').replace('ê', 'e')
            .replace('É', 'E').replace('È', 'E').replace('Ê', 'E')
            .replace('<i>', '').replace('</i>', '')  # hapus tag italic
            .replace('<b>', '').replace('</b>', '')
            .replace('<u>', '').replace('</u>', '')
    ).strip()


# ============================================================
# Audio decoding — MP3 → PCM via ffmpeg
# ============================================================

def decode_mp3_to_pcm(mp3_path: str, target_sr: int = OUTPUT_SAMPLE_RATE) -> 'np.ndarray':
    """Decode MP3 → mono PCM float32 di target sample rate via ffmpeg."""
    if not shutil.which('ffmpeg'):
        raise RuntimeError('ffmpeg tidak terinstall. Install: brew install ffmpeg')
    # Pakai ffmpeg → raw PCM s16le mono
    cmd = [
        'ffmpeg', '-v', 'error', '-i', mp3_path,
        '-ac', '1', '-ar', str(target_sr),
        '-f', 's16le', '-acodec', 'pcm_s16le', '-',
    ]
    result = subprocess.run(cmd, capture_output=True)
    if result.returncode != 0:
        raise RuntimeError(f'ffmpeg decode gagal: {result.stderr.decode()}')
    # s16le → float32
    if HAS_NUMPY:
        audio = np.frombuffer(result.stdout, dtype=np.int16).astype(np.float32) / 32768.0
        return audio
    else:
        # Pure Python fallback (lambat)
        n = len(result.stdout) // 2
        samples = struct.unpack(f'<{n}h', result.stdout[:n * 2])
        return [s / 32768.0 for s in samples]


# ============================================================
# Trim silence — asymmetric (voicertool pattern)
# ============================================================

def db_to_linear(db: float) -> float:
    return 10 ** (db / 20.0)


def trim_silence_asymmetric(audio: 'np.ndarray', sr: int, padding_ms: int = TRIM_PADDING_MS) -> 'np.ndarray':
    """
    Asymmetric trim:
    - Head: trim sampai level TRIM_HEAD_DB terlewati
    - Tail: trim sampai level TRIM_TAIL_DB terlewati (dari akhir)
    - Tambah padding di awal/akhir
    """
    if len(audio) == 0:
        return audio
    if HAS_NUMPY:
        abs_audio = np.abs(audio)
        head_thresh = db_to_linear(TRIM_HEAD_DB)
        tail_thresh = db_to_linear(TRIM_TAIL_DB)

        # Head: cari first sample yang > head_thresh
        head_idx = 0
        for i in range(len(abs_audio)):
            if abs_audio[i] > head_thresh:
                head_idx = i
                break
        # Tail: dari akhir, cari first sample yang > tail_thresh
        tail_idx = len(audio)
        for i in range(len(abs_audio) - 1, -1, -1):
            if abs_audio[i] > tail_thresh:
                tail_idx = i + 1
                break
        # Padding
        pad_samples = int(sr * padding_ms / 1000)
        head_idx = max(0, head_idx - pad_samples)
        tail_idx = min(len(audio), tail_idx + pad_samples)
        if tail_idx <= head_idx:
            return audio[:0]  # empty
        return audio[head_idx:tail_idx].copy()
    else:
        # Pure Python fallback
        abs_audio = [abs(x) for x in audio]
        head_thresh = db_to_linear(TRIM_HEAD_DB)
        tail_thresh = db_to_linear(TRIM_TAIL_DB)
        head_idx = 0
        for i, v in enumerate(abs_audio):
            if v > head_thresh:
                head_idx = i
                break
        tail_idx = len(audio)
        for i in range(len(abs_audio) - 1, -1, -1):
            if abs_audio[i] > tail_thresh:
                tail_idx = i + 1
                break
        pad_samples = int(sr * padding_ms / 1000)
        head_idx = max(0, head_idx - pad_samples)
        tail_idx = min(len(audio), tail_idx + pad_samples)
        if tail_idx <= head_idx:
            return audio[:0]
        return audio[head_idx:tail_idx]


# ============================================================
# Peak normalize — match src/lib/tts.ts peakNormalize
# ============================================================

def peak_normalize(audio: 'np.ndarray', target_db: float = NORMALIZE_DBFS, noise_floor_db: float = NOISE_FLOOR_DB) -> 'np.ndarray':
    """Peak normalize ke target dBFS, skip kalau di bawah noise floor."""
    if len(audio) == 0:
        return audio
    if HAS_NUMPY:
        peak = float(np.max(np.abs(audio)))
        if peak <= 0:
            return audio
        peak_db = 20 * np.log10(peak)
        if peak_db < noise_floor_db:
            return audio  # di bawah noise floor, skip
        target_linear = db_to_linear(target_db)
        gain = target_linear / peak
        return (audio * gain).astype(np.float32)
    else:
        peak = max(abs(x) for x in audio) if audio else 0
        if peak <= 0:
            return audio
        import math
        peak_db = 20 * math.log10(peak)
        if peak_db < noise_floor_db:
            return audio
        target_linear = db_to_linear(target_db)
        gain = target_linear / peak
        return [x * gain for x in audio]


# ============================================================
# Fade in/out untuk crossfade
# ============================================================

def apply_fade_out(audio: 'np.ndarray', fade_start: int, fade_end: int) -> 'np.ndarray':
    """Apply linear fade out dari fade_start ke fade_end."""
    if fade_end <= fade_start or fade_end > len(audio):
        return audio
    if HAS_NUMPY:
        fade_len = fade_end - fade_start
        fade = np.linspace(1.0, 0.0, fade_len, dtype=np.float32)
        audio[fade_start:fade_end] *= fade
    else:
        fade_len = fade_end - fade_start
        for i in range(fade_len):
            audio[fade_start + i] *= 1.0 - (i / fade_len)
    return audio


def apply_fade_in(audio: 'np.ndarray', fade_start: int, fade_end: int) -> 'np.ndarray':
    """Apply linear fade in dari fade_start ke fade_end."""
    if fade_end <= fade_start or fade_end > len(audio):
        return audio
    if HAS_NUMPY:
        fade_len = fade_end - fade_start
        fade = np.linspace(0.0, 1.0, fade_len, dtype=np.float32)
        audio[fade_start:fade_end] *= fade
    else:
        fade_len = fade_end - fade_start
        for i in range(fade_len):
            audio[fade_start + i] *= (i / fade_len)
    return audio


# ============================================================
# Format Edge TTS rate — match src/lib/tts.ts formatEdgeRate
# ============================================================

def format_edge_rate(ratio: float) -> str:
    """Convert ratio (1.5 = 150%) → Edge TTS rate string ('+50%')."""
    percent = int((ratio - 1.0) * 100)
    return f'+{percent}%' if percent >= 0 else f'{percent}%'


# ============================================================
# Generate 1 cue via Edge TTS (lokal)
# ============================================================

def generate_cue_tts(text: str, voice: str, rate: str, pitch: str, output_mp3: str,
                     cue_idx: int = 0) -> bool:
    """Generate 1 cue via edge_tts Python → MP3 file. Return True sukses.

    v7.4: Auto-retry kalau kena 429 (rate limit Microsoft).
    Backoff schedule: 30s → 60s → 120s → skip + log.
    """
    import asyncio

    last_error = None
    for attempt in range(len(RATE_LIMIT_BACKOFF) + 1):  # 1 initial + 3 retries
        try:
            communicate = edge_tts.Communicate(text, voice, rate=rate, pitch=pitch)
            async def _save():
                await communicate.save(output_mp3)
            asyncio.run(_save())
            if os.path.isfile(output_mp3) and os.path.getsize(output_mp3) > 0:
                return True
            # File kosong/gagal tapi no exception → treat as error
            raise RuntimeError('output MP3 kosong atau tidak terbentuk')
        except Exception as e:
            last_error = e
            err_str = str(e).lower()
            # Detect rate limit (429) — Edge TTS Python pakai berbagai pesan
            is_rate_limit = (
                '429' in err_str or
                'rate limit' in err_str or
                'too many requests' in err_str or
                'throttle' in err_str
            )
            if not is_rate_limit:
                # Bukan rate limit → jangan retry, langsung fail
                print(f'  ⚠ Edge TTS gagal cue {cue_idx}: {e}')
                return False
            # Rate limit → retry dengan backoff
            if attempt < len(RATE_LIMIT_BACKOFF):
                wait_s = RATE_LIMIT_BACKOFF[attempt]
                print(f'  ⏸ Cue {cue_idx} kena rate limit (429). Tunggu {wait_s}s, retry {attempt+1}/{len(RATE_LIMIT_BACKOFF)}...')
                time.sleep(wait_s)
                continue
            else:
                print(f'  ⚠ Edge TTS gagal cue {cue_idx} setelah {len(RATE_LIMIT_BACKOFF)} retry: {last_error}')
                return False

    print(f'  ⚠ Edge TTS gagal cue {cue_idx}: {last_error}')
    return False


# ============================================================
# Smart Fit untuk 1 cue
# ============================================================

def smart_fit_cue(
    text: str,
    cue_dur: float,
    voice: str,
    pitch: str,
    cap: float,
    cache_path: str,
    cache_key: str,
    cue_idx: int = 0,
) -> 'np.ndarray':
    """
    Smart Fit untuk 1 cue:
    1. Generate natural (rate +0%)
    2. Trim + compute need
    3. Kalau need > 1.0 → re-generate dengan rate = min(need, cap)
    4. Peak normalize
    Returns: Float32Array (atau list kalau no numpy)
    """
    natural_mp3 = cache_path  # natural = cache utama
    smart_mp3 = cache_path.replace('.mp3', '_smart.mp3')

    # === Pass 1: natural ===
    if not (os.path.isfile(natural_mp3) and os.path.getsize(natural_mp3) > 0):
        ok = generate_cue_tts(text, voice, '+0%', pitch, natural_mp3, cue_idx=cue_idx)
        if not ok:
            raise RuntimeError(f'Pass 1 gagal untuk cue {cue_idx}')

    audio1 = decode_mp3_to_pcm(natural_mp3, OUTPUT_SAMPLE_RATE)
    natural_audio = trim_silence_asymmetric(audio1, OUTPUT_SAMPLE_RATE)
    natural_dur = len(natural_audio) / OUTPUT_SAMPLE_RATE
    need = natural_dur / max(0.001, cue_dur)

    if need <= 1.0:
        # Natural muat — pakai natural
        return peak_normalize(natural_audio)
    # === Pass 2: smart fit dengan rate ===
    audio_rate = min(need, cap)
    rate_str = format_edge_rate(audio_rate)
    # Cache key untuk smart: text + rate
    smart_cache_key = cache_key + f'_r{rate_str}'
    if not (os.path.isfile(smart_mp3) and os.path.getsize(smart_mp3) > 0):
        ok = generate_cue_tts(text, voice, rate_str, pitch, smart_mp3, cue_idx=cue_idx)
        if not ok:
            # Fallback: pakai natural
            print(f'  ⚠ Pass 2 gagal cue {cue_idx} (rate={rate_str}), pakai natural')
            return peak_normalize(natural_audio)
    audio2 = decode_mp3_to_pcm(smart_mp3, OUTPUT_SAMPLE_RATE)
    smart_audio = trim_silence_asymmetric(audio2, OUTPUT_SAMPLE_RATE)
    return peak_normalize(smart_audio)


# ============================================================
# Stitch — port dari src/lib/tts.ts narrateEntries
# ============================================================

def mix_into_buffer(all_audio, audio, position: int, fade_out_end: int = None, fade_in_start: int = None, fade_len: int = 0):
    """
    Mix ADD audio ke all_audio pada position, dengan optional fade.
    Inline mix — tidak simpan audio di array terpisah (RAM efficient untuk 5000 cue).

    fade_out_end: kalau di-set (samples, position-end dalam koordinat all_audio),
                  apply fade out dari fade_out_start_sample sampai sini di koordinat audio lokal.
    fade_in_start: kalau di-set (samples, position dalam koordinat all_audio),
                   apply fade in dari sini sampai fade_len samples di audio lokal.
    """
    end_pos = position + len(audio)
    # Extend buffer kalau overflow
    if end_pos > len(all_audio):
        if HAS_NUMPY:
            extra = np.zeros(end_pos - len(all_audio), dtype=np.float32)
            all_audio = np.concatenate([all_audio, extra])
        else:
            all_audio.extend([0.0] * (end_pos - len(all_audio)))

    # Fade in head (kalau audio ini overlap dengan prev)
    if fade_in_start is not None and fade_len > 0:
        # fade_in_start di koordinat all_audio, position adalah audio start
        # audio[0:fade_len] di-fade in
        local_fade_end = min(len(audio), fade_len)
        if local_fade_end > 0:
            apply_fade_in(audio, 0, int(local_fade_end))

    # Fade out tail (kalau audio ini overlap dengan next)
    if fade_out_end is not None:
        # fade_out_end di koordinat all_audio
        # fade out dari (fade_out_end - position) ke len(audio)
        local_fade_start = fade_out_end - position
        if local_fade_start < len(audio) and local_fade_start >= 0:
            apply_fade_out(audio, int(local_fade_start), int(len(audio)))

    # Mix ADD
    if HAS_NUMPY:
        all_audio[position:end_pos] += audio
    else:
        for j, v in enumerate(audio):
            all_audio[position + j] += v
    return all_audio


# ============================================================
# Encode WAV 24kHz mono 16-bit
# ============================================================

def encode_wav(audio, sample_rate: int = OUTPUT_SAMPLE_RATE, output_path: str = None):
    """Encode Float32Array → WAV 16-bit PCM. Return bytes kalau output_path=None."""
    if HAS_NUMPY:
        # Clip + convert to int16
        clipped = np.clip(audio, -1.0, 1.0)
        int_audio = (clipped * 32767).astype(np.int16)
    else:
        int_audio = []
        for v in audio:
            v = max(-1.0, min(1.0, v))
            int_audio.append(int(v * 32767))
        int_audio = struct.pack(f'<{len(int_audio)}h', *int_audio)

    if output_path:
        with wave.open(output_path, 'wb') as wf:
            wf.setnchannels(OUTPUT_CHANNELS)
            wf.setsampwidth(OUTPUT_BITS // 8)
            wf.setframerate(sample_rate)
            if HAS_NUMPY:
                wf.writeframes(int_audio.tobytes())
            else:
                wf.writeframes(int_audio)
        return None
    else:
        # Return bytes
        import io
        buf = io.BytesIO()
        with wave.open(buf, 'wb') as wf:
            wf.setnchannels(OUTPUT_CHANNELS)
            wf.setsampwidth(OUTPUT_BITS // 8)
            wf.setframerate(sample_rate)
            if HAS_NUMPY:
                wf.writeframes(int_audio.tobytes())
            else:
                wf.writeframes(int_audio)
        return buf.getvalue()


# ============================================================
# TUI helpers
# ============================================================

def clear_screen():
    os.system('clear' if os.name != 'nt' else 'cls')


def print_banner():
    clear_screen()
    # v7.4: tampilkan version + PID untuk tracking paralel
    pid_str = f'PID {os.getpid()}'
    title = f'🎙️  Edge TTS Lokal {VERSION} ({pid_str})'
    pad_title = max(0, 66 - len(title) - 2)
    print('╔' + '═' * 64 + '╗')
    print('║  ' + title + ' ' * pad_title + '║')
    print('║  Mode ON + Smart Fit | 100% lokal | paralel-safe (v7.4)' + ' ' * 2 + '║')
    print('╚' + '═' * 64 + '╝')
    print()


def find_srt_files(search_dir):
    """Cari file SRT di directory."""
    files = []
    for ext in ('srt', 'SRT'):
        for f in Path(search_dir).glob(f'*.{ext}'):
            files.append(f.name)
    files.sort()
    return files


def compute_cache_key(text: str, voice: str, pitch: str) -> str:
    """Hash text + voice + pitch → cache key (untuk validasi cache)."""
    h = hashlib.md5(f'{text}|{voice}|{pitch}'.encode()).hexdigest()[:12]
    return h


# ============================================================
# Lock file helpers (v7.4 — paralel support)
# ============================================================

def _pid_alive(pid: int) -> bool:
    """Cek apakah process PID masih berjalan. Cross-platform (Mac/Linux)."""
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)  # signal 0 = cek existence, no kill
        return True
    except (ProcessLookupError, PermissionError):
        return False
    except OSError:
        return False


def lock_path_for(output_dir: str, prefix: str) -> str:
    """Path ke lock file: {output_dir}/.{prefix}.lock"""
    return os.path.join(output_dir, f'.{prefix}.lock')


def acquire_lock(output_dir: str, prefix: str) -> tuple:
    """Coba acquire lock untuk prefix di output_dir.

    Return (success: bool, lock_path: str, holder_pid: int).
    holder_pid = PID pemegang lock saat ini (kalau success=False).

    Side effect: kalau success, set module-level _ACTIVE_LOCK supaya
    KeyboardInterrupt handler bisa release di cleanup.
    """
    global _ACTIVE_LOCK
    lock_path = lock_path_for(output_dir, prefix)

    # Cek apakah lock file ada
    if os.path.isfile(lock_path):
        try:
            with open(lock_path, 'r') as f:
                content = f.read().strip()
            holder_pid = int(content.split('\n')[0]) if content else 0
        except (ValueError, IOError):
            holder_pid = 0

        # Cek apakah PID holder masih alive
        if holder_pid and _pid_alive(holder_pid):
            return (False, lock_path, holder_pid)

        # PID mati → stale lock, hapus
        try:
            os.remove(lock_path)
        except OSError:
            pass

    # Tulis lock file baru dengan PID + timestamp
    try:
        with open(lock_path, 'w') as f:
            f.write(f'{os.getpid()}\n{int(time.time())}\n')
        _ACTIVE_LOCK = (output_dir, prefix)  # v7.4: register untuk cleanup
        return (True, lock_path, os.getpid())
    except OSError as e:
        print(f'  ⚠ Gagal tulis lock file: {e}')
        return (False, lock_path, 0)


def release_lock(output_dir: str, prefix: str) -> None:
    """Hapus lock file kalau masih punya kita (PID match)."""
    global _ACTIVE_LOCK
    lock_path = lock_path_for(output_dir, prefix)
    if not os.path.isfile(lock_path):
        _ACTIVE_LOCK = None
        return
    try:
        with open(lock_path, 'r') as f:
            content = f.read().strip()
        holder_pid = int(content.split('\n')[0]) if content else 0
    except (ValueError, IOError):
        holder_pid = 0

    # Hanya hapus kalau PID match (jangan hapus lock milik process lain)
    if holder_pid == os.getpid():
        try:
            os.remove(lock_path)
        except OSError:
            pass
    _ACTIVE_LOCK = None


def suggest_unique_prefix(output_dir: str, prefix: str, max_attempts: int = 99) -> str:
    """Cari prefix unik dengan suffix -2, -3, -4... sampai lock kosong.

    Return prefix yang available (atau prefix-asli kalau ga ada collision).
    """
    candidate = prefix
    n = 2
    while n <= max_attempts:
        lock_path = lock_path_for(output_dir, candidate)
        if not os.path.isfile(lock_path):
            return candidate
        # Lock ada, cek apakah PID alive
        try:
            with open(lock_path, 'r') as f:
                holder_pid = int(f.read().strip().split('\n')[0])
            if not _pid_alive(holder_pid):
                # Stale lock, candidate tersedia
                return candidate
        except (ValueError, IOError):
            return candidate
        # PID alive → coba suffix berikutnya
        candidate = f'{prefix}-{n}'
        n += 1
    return f'{prefix}-{int(time.time())}'  # Fallback unik dengan timestamp


# ============================================================
# Main TUI flow
# ============================================================

def main():
    print_banner()

    print('📋 Pilihan: ikuti petunjuk di layar.')
    print('   Navigasi: ↑↓ arrow keys, Enter konfirmasi, Ctrl+C batal')
    print()

    # Step 1: Pilih SRT (default: HDD/input/)
    print('▶ Step 1/6: Pilih SRT')
    from config import INPUT_DIR, TTS_DIR, ensure_hdd
    if ensure_hdd():
        default_srt_dir = str(INPUT_DIR)
    else:
        default_srt_dir = os.getcwd()
    srt_files = find_srt_files(default_srt_dir)
    if srt_files:
        srt_choice = questionary.select(
            f'File SRT (ditemukan {len(srt_files)} di {default_srt_dir}):',
            choices=srt_files + ['[Ketik path manual]'],
            default=srt_files[0],
        ).ask()
        if srt_choice == '[Ketik path manual]':
            srt_path = questionary.text('Path SRT:').ask()
        else:
            srt_path = os.path.join(default_srt_dir, srt_choice)
    else:
        srt_path = questionary.text(
            f'Tidak ada SRT di {default_srt_dir}. Ketik path lengkap:',
            default='',
        ).ask()
    if not srt_path or not os.path.isfile(srt_path):
        print('❌ File SRT tidak ditemukan.')
        sys.exit(1)
    print(f'  ✓ {srt_path}')
    print()

    # Step 2: Output dir (default: HDD/tts/)
    print('▶ Step 2/6: Pilih output directory')
    if ensure_hdd():
        default_out = str(TTS_DIR)
    else:
        default_out = os.path.dirname(os.path.abspath(srt_path))
    output_dir = questionary.text(
        'Output directory:',
        default=default_out,
    ).ask()
    if not output_dir:
        output_dir = default_out
    os.makedirs(output_dir, exist_ok=True)
    print(f'  ✓ {output_dir}')
    print()

    # Step 3: Voice
    print('▶ Step 3/6: Pilih voice')
    voice_labels = [v[1] for v in EDGE_VOICES]
    voice_label = questionary.select(
        'Voice:',
        choices=voice_labels,
        default=voice_labels[0],
    ).ask()
    voice = EDGE_VOICES[voice_labels.index(voice_label)][0]
    print(f'  ✓ {voice}')
    print()

    # Step 4: Pitch
    print('▶ Step 4/6: Pitch adjustment')
    pitch_choice = questionary.select(
        'Pitch (Edge TTS prosody pitch):',
        choices=[
            '+0Hz (natural)',
            '-10Hz (laki, lebih bas)',
            '-15Hz (laki, lebih bas lagi)',
            '+10Hz (perempuan, lebih tinggi)',
            '+15Hz (perempuan, lebih tinggi lagi)',
        ],
        default='+0Hz (natural)',
    ).ask()
    pitch = pitch_choice.split(' ')[0]
    print(f'  ✓ {pitch}')
    print()

    # Step 5: Smart Fit cap
    print('▶ Step 5/6: Smart Fit cap')
    cap_choice = questionary.select(
        'Smart Fit cap (max audio rate):',
        choices=[
            '2.0x (voicertool cap, default)',
            '1.5x (lebih konservatif natural)',
            '1.25x (paling natural, lebih sering overflow)',
            'OFF (no smart fit, natural only)',
        ],
        default='2.0x (voicertool cap, default)',
    ).ask()
    if 'OFF' in cap_choice:
        smart_fit = False
        cap = 1.0
    else:
        smart_fit = True
        cap = float(cap_choice.split('x')[0])
    print(f'  ✓ cap={cap}, smart_fit={smart_fit}')
    print()

    # Step 6: Prefix (dengan lock file check — v7.4 paralel-safe)
    print('▶ Step 6/6: Prefix nama file')
    base_name = Path(srt_path).stem
    prefix = questionary.text(
        'Prefix (default: nama SRT tanpa extension):',
        default=base_name,
    ).ask()
    if not prefix:
        prefix = base_name
    print(f'  ✓ {prefix}')

    # v7.4: Lock file check — kalau prefix lagi dipakai process lain, auto-suggest unik
    success, lock_path, holder_pid = acquire_lock(output_dir, prefix)
    if not success:
        suggested = suggest_unique_prefix(output_dir, prefix)
        print(f'\n  ⚠ Prefix "{prefix}" lagi dipakai process lain (PID {holder_pid}).')
        print(f'    Kalau dipaksa → 2 instance akan saling overwrite file output + cache rusak.')
        use_suggested = questionary.confirm(
            f'  Ganti prefix jadi "{suggested}"? (recommended untuk paralel)',
            default=True,
        ).ask()
        if use_suggested:
            prefix = suggested
            # Acquire lock untuk prefix baru
            success, lock_path, holder_pid = acquire_lock(output_dir, prefix)
            if not success:
                print(f'  ❌ Prefix "{suggested}" juga dipakai. Batal.')
                sys.exit(1)
            print(f'  ✓ Prefix: {prefix}')
        else:
            print('  ❌ Batal. Pakai prefix lain atau tunggu process lain selesai.')
            sys.exit(1)
    print(f'  🔒 Lock acquired: {os.path.basename(lock_path)} (PID {os.getpid()})')
    print()

    # === Parse SRT ===
    print('▶ Parse SRT...')
    with open(srt_path, 'r', encoding='utf-8') as f:
        srt_content = f.read()
    entries = parse_srt(srt_content)
    if not entries:
        print('❌ Tidak ada entry valid di SRT.')
        sys.exit(1)
    total_dur = entries[-1]['end']
    print(f'  ✓ {len(entries)} cue, total durasi {format_duration(total_dur)}')
    print()

    # === Estimasi waktu ===
    # Lokal: ~0.3s per cue (no network latency), Smart Fit 2x → 0.6s avg
    # Kalau 50% cue butuh smart fit: 0.45s avg
    est_per_cue = 0.45 if smart_fit else 0.3
    est_total_sec = len(entries) * est_per_cue
    print(f'  Estimasi: ~{format_duration(est_total_sec)} ({len(entries)} cue × ~{est_per_cue}s)')
    print()

    # === Konfirmasi ===
    print('╔' + '═' * 64 + '╗')
    print('║  📋 Ringkasan:' + ' ' * 49 + '║')
    print('╠' + '═' * 64 + '╣')
    print(f'║  SRT     : {os.path.basename(srt_path)[:46]:<46}║')
    print(f'║  Output  : {output_dir[:46]:<46}║')
    print(f'║  Voice   : {voice[:46]:<46}║')
    print(f'║  Pitch   : {pitch[:46]:<46}║')
    print(f'║  SmartFit: {"ON, cap=" + str(cap) if smart_fit else "OFF":<46}║')
    print(f'║  Prefix  : {prefix[:46]:<46}║')
    print(f'║  Cues    : {len(entries):<46}║')
    print(f'║  Durasi  : {format_duration(total_dur):<46}║')
    print(f'║  Estimasi: {format_duration(est_total_sec):<46}║')
    print('╚' + '═' * 64 + '╝')
    print()

    if not questionary.confirm('Lanjut generate?', default=True).ask():
        print('Batal.')
        sys.exit(0)

    # === Generate per cue + mix inline (RAM efficient untuk 5000 cue) ===
    print('\n' + '═' * 64)
    print('🚀 Mulai generate TTS + mix inline...')
    print('═' * 64 + '\n')

    cache_dir = os.path.join(output_dir, '.cache')
    os.makedirs(cache_dir, exist_ok=True)

    # Pre-allocate buffer (1 WAV utuh, full durasi)
    total_samples = int(total_dur * OUTPUT_SAMPLE_RATE)
    if HAS_NUMPY:
        all_audio = np.zeros(total_samples, dtype=np.float32)
    else:
        all_audio = [0.0] * total_samples
    print(f'  Buffer pre-allocate: {total_samples} samples = {total_dur/3600:.1f} jam = {total_samples * 4 / 1024 / 1024:.0f} MB')
    print()

    success_count = 0
    fail_count = 0
    first_error = ''
    start_time = time.time()
    crossfade_samples = int(OUTPUT_SAMPLE_RATE * CROSSFADE_MS / 1000)

    for i, entry in enumerate(entries):
        cue_idx = i + 1
        text = normalize_tts_text(' '.join(entry['textLines']))
        cue_dur = entry['end'] - entry['start']
        position = int(entry['start'] * OUTPUT_SAMPLE_RATE)
        cue_end_samples = int(entry['end'] * OUTPUT_SAMPLE_RATE)

        # Cek overlap dengan prev (untuk fade in head)
        prev_entry = entries[i - 1] if i > 0 else None
        fade_in_start = None
        fade_len = 0
        if prev_entry:
            prev_end_samples = int(prev_entry['end'] * OUTPUT_SAMPLE_RATE)
            if position < prev_end_samples:
                # Prev audio extends past this cue start → fade in head
                fade_in_start = position
                fade_len = min(crossfade_samples, prev_end_samples - position)

        # Cek overlap dengan next (untuk fade out tail) — kita belum tahu panjang audio next
        # Tapi kita tahu next cue start. Kalau audio kita extends past next start → fade out tail
        next_entry = entries[i + 1] if i + 1 < len(entries) else None
        fade_out_end = None
        if next_entry:
            next_start_samples = int(next_entry['start'] * OUTPUT_SAMPLE_RATE)
            # fade_out_end = next cue start (di koordinat all_audio)
            # Nanti di mix_into_buffer, fade out dari (next_start - position) ke len(audio)

        if not text:
            # Empty cue — skip (buffer tetap kosong di region ini)
            continue

        # Cache path
        cache_key = compute_cache_key(text, voice, pitch)
        cache_path = os.path.join(cache_dir, f'{prefix}-cue-{cue_idx:04d}-{cache_key}.mp3')

        # Cek cache: kalau ada + valid → skip generate
        cached_audio = None
        if os.path.isfile(cache_path) and os.path.getsize(cache_path) > 0:
            try:
                audio1 = decode_mp3_to_pcm(cache_path, OUTPUT_SAMPLE_RATE)
                natural_audio = trim_silence_asymmetric(audio1, OUTPUT_SAMPLE_RATE)
                natural_dur = len(natural_audio) / OUTPUT_SAMPLE_RATE
                need = natural_dur / max(0.001, cue_dur)
                if not smart_fit or need <= 1.0:
                    cached_audio = peak_normalize(natural_audio)
                    final_audio = cached_audio
            except Exception as e:
                print(f'  ⚠ Cache corrupt cue {cue_idx}, regenerate: {e}')

        if cached_audio is None:
            # Generate
            try:
                if smart_fit:
                    final_audio = smart_fit_cue(text, cue_dur, voice, pitch, cap, cache_path, cache_key, cue_idx=cue_idx)
                else:
                    if not (os.path.isfile(cache_path) and os.path.getsize(cache_path) > 0):
                        if not generate_cue_tts(text, voice, '+0%', pitch, cache_path, cue_idx=cue_idx):
                            raise RuntimeError('Edge TTS gagal')
                    audio1 = decode_mp3_to_pcm(cache_path, OUTPUT_SAMPLE_RATE)
                    natural_audio = trim_silence_asymmetric(audio1, OUTPUT_SAMPLE_RATE)
                    final_audio = peak_normalize(natural_audio)
            except Exception as e:
                fail_count += 1
                if not first_error:
                    first_error = str(e)
                print(f'  [{cue_idx}/{len(entries)}] ❌ {text[:30]:<30} | {e}')
                continue

        # Cek apakah audio extends past next cue start → set fade_out_end
        if next_entry and position + len(final_audio) > next_start_samples:
            fade_out_end = next_start_samples

        # Mix inline ke buffer (tidak simpan di segments array)
        all_audio = mix_into_buffer(
            all_audio, final_audio, position,
            fade_out_end=fade_out_end,
            fade_in_start=fade_in_start,
            fade_len=fade_len,
        )

        success_count += 1
        elapsed = time.time() - start_time
        eta = (elapsed / max(1, success_count + fail_count)) * (len(entries) - cue_idx)
        status = 'cache' if cached_audio is not None else '✓'
        print(f'  [{cue_idx}/{len(entries)}] {status} {text[:40]:<40} | ETA {format_duration(eta)}')

        # Free memory
        del final_audio
        if cached_audio is not None:
            del cached_audio

    print()
    print('═' * 64)
    print(f'📊 Generate: {success_count} OK, {fail_count} gagal dari {len(entries)} cue')
    if fail_count > 0:
        print(f'   First error: {first_error}')
    print()

    if success_count == 0:
        print('❌ Semua cue gagal. Cek error di atas.')
        sys.exit(1)

    # === Encode WAV ===
    print('▶ Encode WAV...')
    print(f'  Buffer durasi: {format_duration(total_dur)}')
    print(f'  RAM buffer: ~{len(all_audio) * 4 / 1024 / 1024:.0f} MB (float32)')
    print()

    output_wav = os.path.join(output_dir, f'{prefix}-audio-id-dub.wav')
    encode_wav(all_audio, OUTPUT_SAMPLE_RATE, output_wav)
    del all_audio  # free RAM

    file_size_mb = os.path.getsize(output_wav) / 1024 / 1024
    print(f'  ✓ Output: {output_wav}')
    print(f'  ✓ Size: {file_size_mb:.1f} MB')
    print(f'  ✓ WAV 24kHz mono 16-bit PCM')
    print()

    # Cleanup cache (opsional)
    cache_files = [f for f in os.listdir(cache_dir) if f.startswith(prefix)]
    cache_size_mb = sum(os.path.getsize(os.path.join(cache_dir, f)) for f in cache_files) / 1024 / 1024
    if cache_files and questionary.confirm(f'Hapus cache ({len(cache_files)} MP3, {cache_size_mb:.1f} MB)?', default=False).ask():
        for f in cache_files:
            os.unlink(os.path.join(cache_dir, f))
        try:
            os.rmdir(cache_dir)
        except OSError:
            pass
        print('  ✓ Cache dihapus')
    else:
        print(f'  Cache disimpan: {cache_dir} ({cache_size_mb:.1f} MB)')
        print(f'  Kalau generate ulang SRT sama → cache dipakai (resume)')

    print()
    print('═' * 64)
    print('✅ SELESAI!')
    print()
    print('🎬 Langkah berikutnya (workflow mix-tui.py):')
    print(f'   python3 mix-tui.py')
    print(f'     → MP4: {prefix}.mp4 (video dari yt-dlp)')
    print(f'     → SFX: output/htdemucs/{prefix}-audio/no_vocals.mp3')
    print(f'     → Dub: {os.path.basename(output_wav)}')
    print(f'     → Output: {prefix}-id-final.mp4')
    print('═' * 64)

    # v7.4: Release lock file (normal exit)
    release_lock(output_dir, prefix)


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print('\n\n⏹ Dibatalkan user.')
        # v7.4: Release lock file kalau ada
        if _ACTIVE_LOCK:
            try:
                release_lock(_ACTIVE_LOCK[0], _ACTIVE_LOCK[1])
                print(f'  🔒 Lock file di-release.')
            except Exception:
                pass
        sys.exit(130)
    except Exception as e:
        print(f'\n❌ Error: {e}', file=sys.stderr)
        import traceback
        print(f'\nStack trace:\n{traceback.format_exc()[:2000]}', file=sys.stderr)
        # v7.4: Release lock file kalau ada (crash safety)
        if _ACTIVE_LOCK:
            try:
                release_lock(_ACTIVE_LOCK[0], _ACTIVE_LOCK[1])
                print(f'  🔒 Lock file di-release (crash cleanup).', file=sys.stderr)
            except Exception:
                pass
        sys.exit(1)
