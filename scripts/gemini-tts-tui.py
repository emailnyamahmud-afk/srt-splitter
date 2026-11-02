#!/usr/bin/env python3
"""
gemini-tts-tui.py v1.1 — TUI Generate TTS dengan Gemini TTS (gemini-3.8-flash-tts)

OPSI TAMBAHAN untuk pipeline dubbing — bukan pengganti edge-tts-tui.py.
edge-tts-tui.py v7.5 tetap production default (Indonesia saja, SRT + Narration).
gemini-tts-tui.py untuk skenario yang Edge TTS kurang bagus / tidak support:

  SRT MODE (Dub per cue dari subtitle):
    - Bahasa Indonesia (alternative ke edge-tts)
    - Bahasa Jawa (krama/ngoko) — Gemini lebih ekspresif dari Edge TTS
      → user sudah test Cruz + jawa-halus-mc, hasil bagus untuk MC/adat

  NARRATION MODE (1 naskah plain text → 1 WAV):
    - Bahasa Indonesia (alternative ke edge-tts narration)
    - Bahasa Jawa (krama) — user sudah test narasi Jawa, hasil bagus
    - Cocok untuk: naskah konten, video pendidikan, audio book

Kapan pakai Edge TTS (production default):
  - Bahasa Indonesia umum (cue-cue film/drama biasa) — free, unlimited, paralel
  - Butuh pitch adjustment presisi (Edge punya pitch slider)
  - Workflow produksi yang sudah jalan stabil

Compatible dengan mix-tui.py v3.10:
  - SRT mode output: HDD/tts/{prefix}-audio-id-dub.wav (sama edge-tts-tui)
    → mix-tui.py cari dub via glob non-recursive → langsung nemu
  - Narration mode output: HDD/tts/{naskah-stem}-narasi.wav
    → pakai untuk review-mix-tui.py (sama edge-tts narration)

Algorithm SRT mode (port dari edge-tts-tui.py v7.5 — identik, beda backend):
  1. Parse SRT → entries (start, end, text)
  2. Per cue: generate natural TTS (Gemini, rate +0%)
  3. Trim silence (asymmetric, voicertool pattern, -30 dB head/tail)
  4. Hitung need = naturalDur / cueDur
  5. Kalau need <= 1.0 → pakai natural
  6. Kalau need > 1.0 → re-generate dengan instruction "Bicara X% lebih cepat"
     (Gemini tidak punya parameter rate langsung — di-pass via instruction)
  7. Peak normalize -2 dBFS
  8. Stitch ke buffer pada cue.start (mix additive)
  9. Crossfade 150ms kalau audio overflow cue next
  10. Output: WAV 24kHz mono 16-bit

Algorithm Narration mode (port dari edge-tts-tui.py v7.5 main_narration):
  1. Read naskah.txt → split per paragraf (double newline)
     Kalau 1 paragraf > 5000 chars → split per kalimat panjang (≤3000 chars)
  2. Per paragraf: generate TTS (Gemini, rate dari pilihan user)
  3. Concat MP3 → WAV (ffmpeg, 48kHz stereo 16-bit)
  4. Output: 1 WAV panjang (48kHz stereo 16-bit)

PARALEL WORKFLOW (sama dengan edge-tts-tui v7.4):
  Lock file + PID + prefix auto-suggest + 429/RESOURCE_EXHAUSTED retry.

  Catatan Gemini free tier: ~5-15 RPM, ~100-250 RPD. Untuk 1 file SRT (rata-rata
  500-5000 cue), akan hit limit cepat. Pakai AI Pro / Cloud Billing kalau batch besar.

Install:
  pip3 install google-genai questionary numpy
  brew install ffmpeg

Env:
  GEMINI_API_KEY  — wajib. Dapatkan di https://aistudio.google.com/apikey
                    Taruh di HDD/Dubbing/.env (sama dengan Supabase credentials):
                      echo "GEMINI_API_KEY=AIza..." >> /Volumes/HDD/Dubbing/.env
                    config.py load_env() akan load otomatis saat TUI start.

Usage:
  python3 gemini-tts-tui.py
  (pilih SRT, output dir, voice, instruction template, cap → generate → WAV)

Output:
  {output_dir}/{prefix}-audio-id-dub.wav   (WAV 24kHz mono 16-bit)
  {output_dir}/.cache/{prefix}-cue-*.mp3   (per-cue cache, format WAV walau ext .mp3)
  {output_dir}/.{prefix}.lock              (lock file, auto-delete saat selesai)

Catatan file cache: gemini_tts_backend.generate_cue_tts simpan WAV (16-bit PCM)
  dengan extension .mp3 supaya pola cache tetap konsisten dengan edge-tts-tui.
  Decoder ffmpeg handle keduanya → tidak ada masalah.
"""

import os
import sys
import re
import shutil
import subprocess
import hashlib
import time
import wave
import struct
from pathlib import Path

# ============================================================
# Version + paralel constants (match edge-tts-tui.py v7.5 pattern)
# ============================================================

VERSION = 'v1.1'

# ============================================================
# Module-level lock state (match edge-tts-tui.py v7.4 pattern)
# ============================================================

_ACTIVE_LOCK = None

# Track missing deps
_MISSING_DEPS = []

try:
    import questionary
except ImportError:
    _MISSING_DEPS.append('questionary')

try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False
    _MISSING_DEPS.append('numpy')

# google-genai: cek via import-test, jangan import full dulu (lazy)
try:
    from google import genai  # noqa
    HAS_GENAI = True
except ImportError:
    HAS_GENAI = False
    _MISSING_DEPS.append('google-genai')

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
    print('   pip3 install google-genai questionary numpy')
    print()
    print('   Kalau pip3 ditolak (Mac blocked), pakai --break-system-packages:')
    print()
    print('   pip3 install --break-system-packages google-genai questionary numpy')
    print()
    print('   Verifikasi:')
    print()
    print('   python3 -c "import google.genai, questionary, numpy; print(\'OK\')"')
    print()
    print('═' * 64)
    sys.exit(1)

# ffmpeg wajib (dipakai untuk decode WAV → PCM)
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

# Import backend (lazy loader untuk genai/types)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gemini_tts_backend import (
    generate_cue_tts as generate_gemini_tts,
    GEMINI_VOICES,
    DEFAULT_VOICE,
    DEFAULT_INSTRUCTION,
    INSTRUCTION_TEMPLATES,
    instructions_for_language,
    MODEL,
    RATE_LIMIT_BACKOFF,
    OUTPUT_SAMPLE_RATE as GEMINI_OUTPUT_SR,
    _rate_to_instruction,
    _format_rate_instruction,
)


# ============================================================
# Constants — match edge-tts-tui.py untuk kompatibilitas mix-tui.py
# ============================================================

OUTPUT_SAMPLE_RATE = 24000
OUTPUT_CHANNELS = 1
OUTPUT_BITS = 16

CROSSFADE_MS = 150
TRIM_HEAD_DB = -30
TRIM_TAIL_DB = -30
TRIM_PADDING_MS = 30

NORMALIZE_DBFS = -2.0
NOISE_FLOOR_DB = -50.0


# ============================================================
# SRT parsing — port verbatim dari edge-tts-tui.py v7.5
# ============================================================

def parse_srt(content: str):
    """Parse SRT content → list of {index, start, end, textLines}."""
    entries = []
    content = content.replace('\r\n', '\n').replace('\r', '\n')
    blocks = re.split(r'\n\s*\n', content.strip())
    for block in blocks:
        lines = block.strip().split('\n')
        if len(lines) < 2:
            continue
        idx = 0
        if re.match(r'^\d+$', lines[0]):
            idx_line = int(lines[0])
            idx = idx_line - 1
            time_line = lines[1] if len(lines) > 1 else ''
            text_lines = lines[2:] if len(lines) > 2 else []
        else:
            time_line = lines[0]
            text_lines = lines[1:]
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
# Text normalization — port verbatim dari edge-tts-tui.py v7.5
# ============================================================

def normalize_tts_text(text: str) -> str:
    """Strip aksen Jawa (é/è/ê → e) + hapus tag HTML supaya TTS bisa baca."""
    return (
        text.replace('é', 'e').replace('è', 'e').replace('ê', 'e')
            .replace('É', 'E').replace('È', 'E').replace('Ê', 'E')
            .replace('<i>', '').replace('</i>', '')
            .replace('<b>', '').replace('</b>', '')
            .replace('<u>', '').replace('</u>', '')
    ).strip()


# ============================================================
# Audio decoding — WAV/MP3 → PCM via ffmpeg (port dari edge-tts-tui.py)
# ============================================================

def decode_audio_to_pcm(audio_path: str, target_sr: int = OUTPUT_SAMPLE_RATE):
    """Decode WAV/MP3 → mono PCM float32 di target sample rate via ffmpeg."""
    if not shutil.which('ffmpeg'):
        raise RuntimeError('ffmpeg tidak terinstall. Install: brew install ffmpeg')
    cmd = [
        'ffmpeg', '-v', 'error', '-i', audio_path,
        '-ac', '1', '-ar', str(target_sr),
        '-f', 's16le', '-acodec', 'pcm_s16le', '-',
    ]
    result = subprocess.run(cmd, capture_output=True)
    if result.returncode != 0:
        raise RuntimeError(f'ffmpeg decode gagal: {result.stderr.decode()}')
    audio = np.frombuffer(result.stdout, dtype=np.int16).astype(np.float32) / 32768.0
    return audio


# ============================================================
# Trim silence — asymmetric (port verbatim dari edge-tts-tui.py v7.5)
# ============================================================

def db_to_linear(db: float) -> float:
    return 10 ** (db / 20.0)


def trim_silence_asymmetric(audio, sr: int, padding_ms: int = TRIM_PADDING_MS):
    """
    Asymmetric trim:
    - Head: trim sampai level TRIM_HEAD_DB terlewati
    - Tail: trim sampai level TRIM_TAIL_DB terlewati (dari akhir)
    - Tambah padding di awal/akhir
    """
    if len(audio) == 0:
        return audio
    abs_audio = np.abs(audio)
    head_thresh = db_to_linear(TRIM_HEAD_DB)
    tail_thresh = db_to_linear(TRIM_TAIL_DB)

    head_idx = 0
    for i in range(len(abs_audio)):
        if abs_audio[i] > head_thresh:
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
    return audio[head_idx:tail_idx].copy()


# ============================================================
# Peak normalize (port verbatim dari edge-tts-tui.py v7.5)
# ============================================================

def peak_normalize(audio, target_db: float = NORMALIZE_DBFS, noise_floor_db: float = NOISE_FLOOR_DB):
    """Peak normalize ke target dBFS, skip kalau di bawah noise floor."""
    if len(audio) == 0:
        return audio
    peak = float(np.max(np.abs(audio)))
    if peak <= 0:
        return audio
    peak_db = 20 * np.log10(peak)
    if peak_db < noise_floor_db:
        return audio
    target_linear = db_to_linear(target_db)
    gain = target_linear / peak
    return (audio * gain).astype(np.float32)


# ============================================================
# Fade in/out untuk crossfade (port verbatim dari edge-tts-tui.py v7.5)
# ============================================================

def apply_fade_out(audio, fade_start: int, fade_end: int):
    """Apply linear fade out dari fade_start ke fade_end."""
    if fade_end <= fade_start or fade_end > len(audio):
        return audio
    fade_len = fade_end - fade_start
    fade = np.linspace(1.0, 0.0, fade_len, dtype=np.float32)
    audio[fade_start:fade_end] *= fade
    return audio


def apply_fade_in(audio, fade_start: int, fade_end: int):
    """Apply linear fade in dari fade_start ke fade_end."""
    if fade_end <= fade_start or fade_end > len(audio):
        return audio
    fade_len = fade_end - fade_start
    fade = np.linspace(0.0, 1.0, fade_len, dtype=np.float32)
    audio[fade_start:fade_end] *= fade
    return audio


# ============================================================
# Format rate (port dari edge-tts-tui.py v7.5 — pakai untuk instruction)
# ============================================================

def format_rate_str(ratio: float) -> str:
    """Convert ratio (1.5 = 150%) → rate string ('+50%')."""
    percent = int((ratio - 1.0) * 100)
    return f'+{percent}%' if percent >= 0 else f'{percent}%'


# ============================================================
# Smart Fit untuk 1 cue (Gemini version — pakai instruction, bukan pitch)
# ============================================================

def smart_fit_cue_gemini(
    text: str,
    cue_dur: float,
    voice: str,
    instruction: str,
    cap: float,
    cache_path: str,
    cache_key: str,
    cue_idx: int = 0,
    temperature: float = 1.0,
    model: str = MODEL,
):
    """
    Smart Fit untuk 1 cue (Gemini TTS):
    1. Generate natural (rate +0%)
    2. Trim + compute need
    3. Kalau need > 1.0 → re-generate dengan instruction "Bicara X% lebih cepat"
       (Gemini tidak punya parameter rate — pakai instruksi tempo di prompt)
    4. Peak normalize

    Returns: np.ndarray float32.
    """
    natural_cache = cache_path  # natural = cache utama
    smart_cache = cache_path.replace('.mp3', '_smart.mp3')

    # === Pass 1: natural ===
    if not (os.path.isfile(natural_cache) and os.path.getsize(natural_cache) > 0):
        ok = generate_gemini_tts(
            text, voice=voice, rate='+0%', instruction=instruction,
            output_mp3=natural_cache, cue_idx=cue_idx,
            temperature=temperature, model=model,
        )
        if not ok:
            raise RuntimeError(f'Pass 1 gagal untuk cue {cue_idx}')

    audio1 = decode_audio_to_pcm(natural_cache, OUTPUT_SAMPLE_RATE)
    natural_audio = trim_silence_asymmetric(audio1, OUTPUT_SAMPLE_RATE)
    natural_dur = len(natural_audio) / OUTPUT_SAMPLE_RATE
    need = natural_dur / max(0.001, cue_dur)

    if need <= 1.0:
        # Natural muat — pakai natural
        return peak_normalize(natural_audio)

    # === Pass 2: smart fit dengan rate ===
    audio_rate = min(need, cap)
    rate_str = format_rate_str(audio_rate)
    # Cache key untuk smart: text + voice + rate + instruction
    smart_cache_key = cache_key + f'_r{rate_str}'
    smart_cache_path = cache_path.replace('.mp3', f'_smart_{rate_str}.mp3')
    if not (os.path.isfile(smart_cache_path) and os.path.getsize(smart_cache_path) > 0):
        ok = generate_gemini_tts(
            text, voice=voice, rate=rate_str, instruction=instruction,
            output_mp3=smart_cache_path, cue_idx=cue_idx,
            temperature=temperature, model=model,
        )
        if not ok:
            # Fallback: pakai natural
            print(f'  ⚠ Pass 2 gagal cue {cue_idx} (rate={rate_str}), pakai natural')
            return peak_normalize(natural_audio)
    audio2 = decode_audio_to_pcm(smart_cache_path, OUTPUT_SAMPLE_RATE)
    smart_audio = trim_silence_asymmetric(audio2, OUTPUT_SAMPLE_RATE)
    return peak_normalize(smart_audio)


# ============================================================
# Mix into buffer (port verbatim dari edge-tts-tui.py v7.5)
# ============================================================

def mix_into_buffer(all_audio, audio, position: int,
                    fade_out_end: int = None, fade_in_start: int = None, fade_len: int = 0):
    """Mix ADD audio ke all_audio pada position, dengan optional fade. Inline mix."""
    end_pos = position + len(audio)
    if end_pos > len(all_audio):
        extra = np.zeros(end_pos - len(all_audio), dtype=np.float32)
        all_audio = np.concatenate([all_audio, extra])

    if fade_in_start is not None and fade_len > 0:
        local_fade_end = min(len(audio), fade_len)
        if local_fade_end > 0:
            apply_fade_in(audio, 0, int(local_fade_end))

    if fade_out_end is not None:
        local_fade_start = fade_out_end - position
        if local_fade_start < len(audio) and local_fade_start >= 0:
            apply_fade_out(audio, int(local_fade_start), int(len(audio)))

    all_audio[position:end_pos] += audio
    return all_audio


# ============================================================
# Encode WAV 24kHz mono 16-bit (port verbatim dari edge-tts-tui.py v7.5)
# ============================================================

def encode_wav(audio, sample_rate: int = OUTPUT_SAMPLE_RATE, output_path: str = None):
    """Encode Float32Array → WAV 16-bit PCM."""
    clipped = np.clip(audio, -1.0, 1.0)
    int_audio = (clipped * 32767).astype(np.int16)

    if output_path:
        with wave.open(output_path, 'wb') as wf:
            wf.setnchannels(OUTPUT_CHANNELS)
            wf.setsampwidth(OUTPUT_BITS // 8)
            wf.setframerate(sample_rate)
            wf.writeframes(int_audio.tobytes())
        return None
    else:
        import io
        buf = io.BytesIO()
        with wave.open(buf, 'wb') as wf:
            wf.setnchannels(OUTPUT_CHANNELS)
            wf.setsampwidth(OUTPUT_BITS // 8)
            wf.setframerate(sample_rate)
            wf.writeframes(int_audio.tobytes())
        return buf.getvalue()


# ============================================================
# TUI helpers (port dari edge-tts-tui.py v7.5)
# ============================================================

def clear_screen():
    os.system('clear' if os.name != 'nt' else 'cls')


def print_banner():
    clear_screen()
    pid_str = f'PID {os.getpid()}'
    title = f'🎙️  Gemini TTS {VERSION} ({pid_str})'
    pad_title = max(0, 66 - len(title) - 2)
    print('╔' + '═' * 64 + '╗')
    print('║  ' + title + ' ' * pad_title + '║')
    print('║  OPSI TAMBAHAN | Gemini 3.8 Flash TTS | 2 mode: SRT + Narasi' + ' ' * 5 + '║')
    print('╚' + '═' * 64 + '╝')
    print()
    print('  ⚠ edge-tts-tui.py tetap production default. Pakai TUI ini untuk:')
    print('     • Jawa halus (krama/ngoko) — Gemini lebih ekspresif dari Edge TTS')
    print('     • Karakter suara spesifik (Cruz, narasi dokuser, dialog dramatis)')
    print('     • Bahasa eksotis (Italia, Jepang, dll) yang tidak ada di Edge TTS')
    print()
    print('  📋 2 Mode:')
    print('     • SRT       — Dub per cue dari subtitle (output: {prefix}-audio-id-dub.wav)')
    print('     • Narration — 1 naskah plain text → 1 WAV (output: {stem}-narasi.wav)')
    print()


def find_srt_files(search_dir):
    """Cari file SRT di directory."""
    files = []
    for ext in ('srt', 'SRT'):
        for f in Path(search_dir).glob(f'*.{ext}'):
            files.append(f.name)
    files.sort()
    return files


def compute_cache_key(text: str, voice: str, instruction: str) -> str:
    """Hash text + voice + instruction → cache key (untuk validasi cache)."""
    h = hashlib.md5(f'{text}|{voice}|{instruction[:200]}'.encode()).hexdigest()[:12]
    return h


# ============================================================
# Lock file helpers (port verbatim dari edge-tts-tui.py v7.4)
# ============================================================

def _pid_alive(pid: int) -> bool:
    """Cek apakah process PID masih berjalan. Cross-platform (Mac/Linux)."""
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
        return True
    except (ProcessLookupError, PermissionError):
        return False
    except OSError:
        return False


def lock_path_for(output_dir: str, prefix: str) -> str:
    """Path ke lock file: {output_dir}/.{prefix}.lock"""
    return os.path.join(output_dir, f'.{prefix}.lock')


def acquire_lock(output_dir: str, prefix: str) -> tuple:
    """Coba acquire lock. Return (success, lock_path, holder_pid)."""
    global _ACTIVE_LOCK
    lock_path = lock_path_for(output_dir, prefix)

    if os.path.isfile(lock_path):
        try:
            with open(lock_path, 'r') as f:
                content = f.read().strip()
            holder_pid = int(content.split('\n')[0]) if content else 0
        except (ValueError, IOError):
            holder_pid = 0

        if holder_pid and _pid_alive(holder_pid):
            return (False, lock_path, holder_pid)

        try:
            os.remove(lock_path)
        except OSError:
            pass

    try:
        with open(lock_path, 'w') as f:
            f.write(f'{os.getpid()}\n{int(time.time())}\n')
        _ACTIVE_LOCK = (output_dir, prefix)
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

    if holder_pid == os.getpid():
        try:
            os.remove(lock_path)
        except OSError:
            pass
    _ACTIVE_LOCK = None


def suggest_unique_prefix(output_dir: str, prefix: str, max_attempts: int = 99) -> str:
    """Cari prefix unik dengan suffix -2, -3, -4... sampai lock kosong."""
    candidate = prefix
    n = 2
    while n <= max_attempts:
        lock_path = lock_path_for(output_dir, candidate)
        if not os.path.isfile(lock_path):
            return candidate
        try:
            with open(lock_path, 'r') as f:
                holder_pid = int(f.read().strip().split('\n')[0])
            if not _pid_alive(holder_pid):
                return candidate
        except (ValueError, IOError):
            return candidate
        candidate = f'{prefix}-{n}'
        n += 1
    return f'{prefix}-{int(time.time())}'


# ============================================================
# Main TUI flow
# ============================================================

def main():
    print_banner()

    # === Cek GEMINI_API_KEY (load .env dari config.py kalau ada) ===
    if not os.environ.get('GEMINI_API_KEY'):
        try:
            from config import load_env, ENV_FILE
            if load_env():
                print(f'  ✓ Loaded .env dari {ENV_FILE}')
            else:
                print(f'  ⚠ .env tidak ditemukan di {ENV_FILE}')
        except ImportError:
            print('  ⚠ config.py tidak ditemukan (jalankan dari ~/Dubbing/ dengan config.py tersedia)')

    if not os.environ.get('GEMINI_API_KEY'):
        print()
        print('═' * 64)
        print('❌ GEMINI_API_KEY belum di-set!')
        print('═' * 64)
        print()
        print('   Dapatkan API key di: https://aistudio.google.com/apikey')
        print('   (Free tier tersedia untuk AI Studio API key)')
        print()
        print('   Set di env (session sementara):')
        print('     export GEMINI_API_KEY=AIza...')
        print()
        print('   Atau simpan permanen di HDD .env (recommended):')
        print('     echo "GEMINI_API_KEY=AIza..." >> /Volumes/HDD/Dubbing/.env')
        print('   (config.py load_env() akan load otomatis saat TUI start)')
        print()
        print('═' * 64)
        sys.exit(1)
    print(f'  ✓ GEMINI_API_KEY: {os.environ.get("GEMINI_API_KEY", "")[:8]}...')
    print()

    print('📋 Pilihan: ikuti petunjuk di layar.')
    print('   Navigasi: ↑↓ arrow keys, Enter konfirmasi, Ctrl+C batal')
    print()

    # === Mode selection — mirror edge-tts-tui.py v7.5 pattern ===
    mode = questionary.select(
        'Mode:',
        choices=[
            'SRT (dub per cue dari subtitle) — Indonesia + Jawa',
            'Narration (1 naskah plain text → 1 WAV) — Indonesia + Jawa',
        ],
        default='SRT (dub per cue dari subtitle) — Indonesia + Jawa',
    ).ask()

    if 'Narration' in mode:
        main_narration()
        return

    # === SRT mode (existing main flow) ===
    print()

    # === Step 1: Pilih SRT (default: HDD/input/) ===
    print('▶ Step 1/7: Pilih SRT')
    try:
        from config import INPUT_DIR, TTS_DIR, ensure_hdd
        hdd_ok = ensure_hdd()
        if hdd_ok:
            default_srt_dir = str(INPUT_DIR)
        else:
            default_srt_dir = os.getcwd()
    except ImportError:
        # Kalau config.py tidak ada, fallback ke cwd
        default_srt_dir = os.getcwd()
        TTS_DIR = Path(os.getcwd()) / 'tts-output'

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

    # === Step 2: Output dir (default: HDD/tts/) ===
    print('▶ Step 2/7: Pilih output directory')
    if isinstance(TTS_DIR, Path) and TTS_DIR.exists():
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

    # === Step 3: Bahasa ===
    print('▶ Step 3/7: Pilih bahasa')
    bahasa_choice = questionary.select(
        'Bahasa naskah/SRT:',
        choices=[
            'Indonesia (id)',
            'Jawa (jv) — krama/ngoko',
        ],
        default='Indonesia (id)',
    ).ask()
    lang_code = 'id' if 'Indonesia' in bahasa_choice else 'jv'
    print(f'  ✓ {lang_code}')
    print()

    # === Step 4: Voice ===
    print('▶ Step 4/7: Pilih voice')
    voice_labels = [v[1] for v in GEMINI_VOICES]
    voice_label = questionary.select(
        'Voice (Gemini prebuilt — 30 resmi + Cruz):',
        choices=voice_labels,
        default=[v[1] for v in GEMINI_VOICES if v[0] == DEFAULT_VOICE][0],
    ).ask()
    voice = GEMINI_VOICES[voice_labels.index(voice_label)][0]
    print(f'  ✓ {voice}')
    print()

    # === Step 5: Instruction template (filtered per bahasa) ===
    print('▶ Step 5/7: Pilih instruksi gaya bicara')
    inst_choices = instructions_for_language(lang_code)
    inst_labels = [t[1] for t in inst_choices]
    inst_label = questionary.select(
        f'Instruction template (karakter + tempo + gaya bicara, {lang_code}):',
        choices=inst_labels,
        default=inst_labels[0],
    ).ask()
    chosen_template = inst_choices[inst_labels.index(inst_label)]
    inst_key = chosen_template[0]

    if inst_key == 'custom':
        # User ketik instruction sendiri
        instruction = questionary.text(
            'Ketik instruksi (karakter, tempo, artikulasi):',
            default='Bacakan teks berikut secara natural, jelas, dengan artikulasi baik.',
        ).ask()
        if not instruction:
            instruction = DEFAULT_INSTRUCTION
    else:
        instruction = chosen_template[2]
    print(f'  ✓ {inst_key}: {instruction[:70]}{"..." if len(instruction) > 70 else ""}')
    print()

    # === Step 6: Smart Fit cap ===
    print('▶ Step 6/7: Smart Fit cap')
    cap_choice = questionary.select(
        'Smart Fit cap (max audio rate — Gemini pakai instruksi tempo):',
        choices=[
            '1.5x (recommended untuk Gemini — instruksinya lebih efektif daripada Edge rate)',
            '2.0x (voicertool cap, agak aggressive untuk Gemini)',
            '1.25x (paling natural, lebih sering overflow)',
            'OFF (no smart fit, natural only)',
        ],
        default='1.5x (recommended untuk Gemini — instruksinya lebih efektif daripada Edge rate)',
    ).ask()
    if 'OFF' in cap_choice:
        smart_fit = False
        cap = 1.0
    else:
        smart_fit = True
        cap = float(cap_choice.split('x')[0])
    print(f'  ✓ cap={cap}, smart_fit={smart_fit}')
    print()

    # === Step 7: Prefix (dengan lock file check — paralel-safe) ===
    print('▶ Step 7/7: Prefix nama file')
    base_name = Path(srt_path).stem
    prefix = questionary.text(
        'Prefix (default: nama SRT tanpa extension):',
        default=base_name,
    ).ask()
    if not prefix:
        prefix = base_name
    print(f'  ✓ {prefix}')

    # Lock file check
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
        release_lock(output_dir, prefix)
        sys.exit(1)
    total_dur = entries[-1]['end']
    print(f'  ✓ {len(entries)} cue, total durasi {format_duration(total_dur)}')
    print()

    # === Estimasi waktu ===
    # Gemini API lokal: ~1-3s per cue (network latency + Gemini processing)
    # Smart Fit 1.5x → rata-rata 1.5-4s per cue (kalau 50% butuh pass 2)
    est_per_cue = 2.0 if smart_fit else 1.5
    est_total_sec = len(entries) * est_per_cue
    print(f'  Estimasi: ~{format_duration(est_total_sec)} ({len(entries)} cue × ~{est_per_cue}s)')
    print(f'  ⚠ Gemini free tier: ~5-15 RPM, ~100-250 RPD. Batch besar perlu AI Pro / Cloud Billing.')
    print()

    # === Konfirmasi ===
    print('╔' + '═' * 64 + '╗')
    print('║  📋 Ringkasan (SRT mode):' + ' ' * 39 + '║')
    print('╠' + '═' * 64 + '╣')
    print(f'║  SRT     : {os.path.basename(srt_path)[:46]:<46}║')
    print(f'║  Output  : {output_dir[:46]:<46}║')
    print(f'║  Bahasa  : {lang_code.upper() + " — " + ("Indonesia" if lang_code == "id" else "Jawa"):44}║')
    print(f'║  Voice   : {voice[:46]:<46}║')
    print(f'║  Instruksi: {inst_key[:45]:<46}║')
    print(f'║  SmartFit: {"ON, cap=" + str(cap) if smart_fit else "OFF":<46}║')
    print(f'║  Prefix  : {prefix[:46]:<46}║')
    print(f'║  Cues    : {len(entries):<46}║')
    print(f'║  Durasi  : {format_duration(total_dur):<46}║')
    print(f'║  Estimasi: {format_duration(est_total_sec):<46}║')
    print('╚' + '═' * 64 + '╝')
    print()

    if not questionary.confirm('Lanjut generate?', default=True).ask():
        print('Batal.')
        release_lock(output_dir, prefix)
        sys.exit(0)

    # === Generate per cue + mix inline ===
    print('\n' + '═' * 64)
    print('🚀 Mulai generate TTS + mix inline...')
    print('═' * 64 + '\n')

    cache_dir = os.path.join(output_dir, '.cache')
    os.makedirs(cache_dir, exist_ok=True)

    total_samples = int(total_dur * OUTPUT_SAMPLE_RATE)
    all_audio = np.zeros(total_samples, dtype=np.float32)
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

        prev_entry = entries[i - 1] if i > 0 else None
        fade_in_start = None
        fade_len = 0
        if prev_entry:
            prev_end_samples = int(prev_entry['end'] * OUTPUT_SAMPLE_RATE)
            if position < prev_end_samples:
                fade_in_start = position
                fade_len = min(crossfade_samples, prev_end_samples - position)

        next_entry = entries[i + 1] if i + 1 < len(entries) else None
        next_start_samples = int(next_entry['start'] * OUTPUT_SAMPLE_RATE) if next_entry else None
        fade_out_end = None

        if not text:
            continue

        cache_key = compute_cache_key(text, voice, instruction)
        cache_path = os.path.join(cache_dir, f'{prefix}-cue-{cue_idx:04d}-{cache_key}.mp3')

        cached_audio = None
        if os.path.isfile(cache_path) and os.path.getsize(cache_path) > 0:
            try:
                audio1 = decode_audio_to_pcm(cache_path, OUTPUT_SAMPLE_RATE)
                natural_audio = trim_silence_asymmetric(audio1, OUTPUT_SAMPLE_RATE)
                natural_dur = len(natural_audio) / OUTPUT_SAMPLE_RATE
                need = natural_dur / max(0.001, cue_dur)
                if not smart_fit or need <= 1.0:
                    cached_audio = peak_normalize(natural_audio)
                    final_audio = cached_audio
            except Exception as e:
                print(f'  ⚠ Cache corrupt cue {cue_idx}, regenerate: {e}')

        if cached_audio is None:
            try:
                if smart_fit:
                    final_audio = smart_fit_cue_gemini(
                        text, cue_dur, voice, instruction, cap,
                        cache_path, cache_key, cue_idx=cue_idx,
                    )
                else:
                    if not (os.path.isfile(cache_path) and os.path.getsize(cache_path) > 0):
                        if not generate_gemini_tts(
                            text, voice=voice, rate='+0%', instruction=instruction,
                            output_mp3=cache_path, cue_idx=cue_idx,
                        ):
                            raise RuntimeError('Gemini TTS gagal')
                    audio1 = decode_audio_to_pcm(cache_path, OUTPUT_SAMPLE_RATE)
                    natural_audio = trim_silence_asymmetric(audio1, OUTPUT_SAMPLE_RATE)
                    final_audio = peak_normalize(natural_audio)
            except Exception as e:
                fail_count += 1
                if not first_error:
                    first_error = str(e)
                print(f'  [{cue_idx}/{len(entries)}] ❌ {text[:30]:<30} | {e}')
                continue

        if next_entry and position + len(final_audio) > next_start_samples:
            fade_out_end = next_start_samples

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
        release_lock(output_dir, prefix)
        sys.exit(1)

    # === Encode WAV ===
    print('▶ Encode WAV...')
    print(f'  Buffer durasi: {format_duration(total_dur)}')
    print(f'  RAM buffer: ~{len(all_audio) * 4 / 1024 / 1024:.0f} MB (float32)')
    print()

    output_wav = os.path.join(output_dir, f'{prefix}-audio-id-dub.wav')
    encode_wav(all_audio, OUTPUT_SAMPLE_RATE, output_wav)
    del all_audio

    file_size_mb = os.path.getsize(output_wav) / 1024 / 1024
    print(f'  ✓ Output: {output_wav}')
    print(f'  ✓ Size: {file_size_mb:.1f} MB')
    print(f'  ✓ WAV 24kHz mono 16-bit PCM')
    print()

    # === Cleanup cache (opsional) ===
    cache_files = [f for f in os.listdir(cache_dir) if f.startswith(prefix)]
    cache_size_mb = sum(os.path.getsize(os.path.join(cache_dir, f)) for f in cache_files) / 1024 / 1024
    if cache_files and questionary.confirm(f'Hapus cache ({len(cache_files)} file, {cache_size_mb:.1f} MB)?', default=False).ask():
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
    print(f'     → SFX: output/htdemucs/{prefix}-audio/no_vocals.mp3 (kalau pakai Demucs)')
    print(f'     → Dub: {os.path.basename(output_wav)}')
    print(f'     → Output: {prefix}-id-final.mp4')
    print('═' * 64)

    # Release lock file (normal exit)
    release_lock(output_dir, prefix)


# ============================================================
# v1.1: Narration mode — 1 naskah plain text → 1 WAV
# Port dari edge-tts-tui.py v7.5 main_narration, adaptasi untuk Gemini TTS.
# Beda dengan SRT mode: gak ada timing constraint, gak butuh Smart Fit,
# gak butuh lock file (1 file, bukan paralel), output 48kHz stereo 16-bit.
# ============================================================

def main_narration():
    """Mode narration: input = naskah.txt, output = 1 WAV panjang.

    Split per paragraf, generate TTS per paragraf via Gemini, concat → 1 WAV.
    Gak butuh SRT (gak ada timing constraint).
    Support Indonesia + Jawa (instruction template filtered per bahasa).
    """
    print('\n🎙️  Narration Mode (v1.1)')
    print('   Input: naskah plain text → Output: 1 WAV panjang')
    print()

    try:
        from config import TTS_DIR, REVIEW_DIR, ensure_hdd
    except ImportError:
        TTS_DIR = Path(os.getcwd()) / 'tts-output'
        REVIEW_DIR = Path(os.getcwd()) / 'review'
        def ensure_hdd():
            return False

    if ensure_hdd():
        default_search = str(TTS_DIR)
        default_out = str(TTS_DIR)
    else:
        default_search = os.getcwd()
        default_out = os.getcwd()

    # Step 1: Pilih naskah.txt
    print('▶ Step 1/6: Pilih naskah (.txt)')
    txt_files = []
    for d in [default_search, str(REVIEW_DIR), os.getcwd()]:
        if Path(d).exists():
            for f in Path(d).glob('*.txt'):
                txt_files.append(str(f))
    txt_files = sorted(set(txt_files))
    if txt_files:
        choices = [os.path.basename(f) for f in txt_files] + ['[Ketik path manual]']
        sel = questionary.select('Naskah:', choices=choices, default=choices[0]).ask()
        if sel == '[Ketik path manual]':
            naskah_path = questionary.text('Path naskah:').ask()
        else:
            naskah_path = ''
            for f in txt_files:
                if os.path.basename(f) == sel:
                    naskah_path = f
                    break
    else:
        naskah_path = questionary.text('Tidak ada .txt. Ketik path lengkap:').ask()
    if not naskah_path or not os.path.isfile(naskah_path):
        print('❌ File naskah tidak ditemukan.')
        return
    print(f'  ✓ {naskah_path}')
    print()

    # Step 2: Output dir + filename
    print('▶ Step 2/6: Output')
    naskah_stem = Path(naskah_path).stem
    default_wav = os.path.join(default_out, f'{naskah_stem}-narasi.wav')
    output_wav = questionary.text('Output WAV:', default=default_wav).ask()
    if not output_wav:
        output_wav = default_wav
    os.makedirs(os.path.dirname(output_wav) or '.', exist_ok=True)
    print(f'  ✓ {output_wav}')
    print()

    # Step 3: Bahasa
    print('▶ Step 3/6: Bahasa')
    bahasa_choice = questionary.select(
        'Bahasa naskah:',
        choices=[
            'Indonesia (id)',
            'Jawa (jv) — krama/ngoko',
        ],
        default='Indonesia (id)',
    ).ask()
    lang_code = 'id' if 'Indonesia' in bahasa_choice else 'jv'
    print(f'  ✓ {lang_code}')
    print()

    # Step 4: Voice
    print('▶ Step 4/6: Voice')
    voice_labels = [v[1] for v in GEMINI_VOICES]
    voice_label = questionary.select(
        'Voice (Gemini prebuilt — 30 resmi + Cruz):',
        choices=voice_labels,
        default=[v[1] for v in GEMINI_VOICES if v[0] == DEFAULT_VOICE][0],
    ).ask()
    voice = GEMINI_VOICES[voice_labels.index(voice_label)][0]
    print(f'  ✓ {voice}')
    print()

    # Step 5: Instruction template (filtered per bahasa)
    print('▶ Step 5/6: Instruksi gaya bicara')
    inst_choices = instructions_for_language(lang_code)
    inst_labels = [t[1] for t in inst_choices]
    inst_label = questionary.select(
        f'Instruction template ({lang_code}):',
        choices=inst_labels,
        default=inst_labels[0],
    ).ask()
    chosen_template = inst_choices[inst_labels.index(inst_label)]
    inst_key = chosen_template[0]
    if inst_key == 'custom':
        instruction = questionary.text(
            'Ketik instruksi:',
            default='Bacakan teks berikut secara natural, jelas, dengan artikulasi baik.',
        ).ask()
        if not instruction:
            instruction = DEFAULT_INSTRUCTION
    else:
        instruction = chosen_template[2]
    print(f'  ✓ {inst_key}: {instruction[:70]}{"..." if len(instruction) > 70 else ""}')
    print()

    # Step 6: Rate
    print('▶ Step 6/6: Rate (instruksi tempo)')
    rate_choice = questionary.select(
        'Rate:',
        choices=[
            '+0% (natural — recommended)',
            '-10% (sedikit lambat — untuk MC/adat)',
            '+10% (sedikit cepat)',
        ],
        default='+0% (natural — recommended)',
    ).ask()
    if '+10' in rate_choice:
        rate = '+10%'
    elif '-10' in rate_choice:
        rate = '-10%'
    else:
        rate = '+0%'
    print(f'  ✓ {rate}')
    print()

    # Read naskah
    with open(naskah_path, 'r', encoding='utf-8') as f:
        naskah = f.read().strip()
    if not naskah:
        print('❌ Naskah kosong.')
        return

    # Split per paragraf (double newline)
    paragraphs = [p.strip() for p in naskah.split('\n\n') if p.strip()]
    # Kalau hanya 1 paragraf (no double newline), split per kalimat panjang
    if len(paragraphs) == 1 and len(paragraphs[0]) > 5000:
        sentences = re.split(r'(?<=[.!?])\s+', paragraphs[0])
        paragraphs = []
        buf = ''
        for s in sentences:
            if len(buf) + len(s) > 3000:
                if buf:
                    paragraphs.append(buf)
                buf = s
            else:
                buf += ' ' + s if buf else s
        if buf:
            paragraphs.append(buf)

    print(f'  Naskah: {len(naskah)} chars → {len(paragraphs)} paragraf')
    total_chars = sum(len(p) for p in paragraphs)
    print(f'  Total chars: {total_chars}')
    print()

    # Konfirmasi
    print('═' * 64)
    print(f'  📋 Ringkasan (Narration mode):')
    print(f'  Naskah    : {os.path.basename(naskah_path)}')
    print(f'  Output    : {output_wav}')
    print(f'  Bahasa    : {lang_code.upper()} — {"Indonesia" if lang_code == "id" else "Jawa"}')
    print(f'  Voice     : {voice}')
    print(f'  Instruksi : {inst_key}')
    print(f'  Rate      : {rate}')
    print(f'  Paragraf  : {len(paragraphs)}')
    print('═' * 64)
    if not questionary.confirm('\nLanjut generate?', default=True).ask():
        print('Dibatalkan.')
        return

    # Generate TTS per paragraf
    print('\n🚀 Generate narasi (Gemini TTS)...')
    print('═' * 64)

    import tempfile
    temp_dir = tempfile.mkdtemp(prefix='gemini_narration_tmp_')
    temp_files = []  # WALAUPUN EXT .mp3, ISI = WAV 16-bit mono 24kHz (backend kita encode WAV)

    for i, para in enumerate(paragraphs, 1):
        mp3_path = os.path.join(temp_dir, f'narration_{i:04d}.mp3')
        temp_files.append(mp3_path)

        print(f'\n  [{i}/{len(paragraphs)}] Paragraf {i} ({len(para)} chars)')
        success = generate_gemini_tts(
            para, voice=voice, rate=rate, instruction=instruction,
            output_mp3=mp3_path, cue_idx=i,
        )
        if not success:
            print(f'  ❌ Gagal generate paragraf {i}')
            for f in temp_files:
                if os.path.exists(f):
                    os.unlink(f)
            try:
                os.rmdir(temp_dir)
            except OSError:
                pass
            return

    print(f'\n  ✓ {len(temp_files)} paragraf selesai')

    # Concat → WAV (48kHz stereo 16-bit — match edge-tts-tui v7.5 narration output)
    print('\n▶ Concat → WAV')
    concat_list = os.path.join(temp_dir, 'concat_list.txt')
    with open(concat_list, 'w') as f:
        for mp3 in temp_files:
            safe = mp3.replace("'", r"'\''")
            f.write(f"file '{safe}'\n")

    ffmpeg = shutil.which('ffmpeg') or '/opt/homebrew/bin/ffmpeg'
    cmd = [ffmpeg, '-y', '-f', 'concat', '-safe', '0',
           '-i', concat_list,
           '-ar', '48000', '-ac', '2',
           '-c:a', 'pcm_s16le',
           output_wav]
    print(f'  ffmpeg concat → {output_wav}')
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    if result.returncode != 0:
        print(f'  ❌ Gagal concat: {result.stderr[-500:]}')
        for mp3 in temp_files:
            if os.path.exists(mp3):
                os.unlink(mp3)
        if os.path.exists(concat_list):
            os.unlink(concat_list)
        try:
            os.rmdir(temp_dir)
        except OSError:
            pass
        return

    # Cleanup temp
    for mp3 in temp_files:
        if os.path.exists(mp3):
            os.unlink(mp3)
    if os.path.exists(concat_list):
        os.unlink(concat_list)
    try:
        os.rmdir(temp_dir)
    except OSError:
        pass

    # Hasil
    if os.path.exists(output_wav):
        size_mb = os.path.getsize(output_wav) / 1024 / 1024
        print(f'\n📁 Output: {os.path.basename(output_wav)} ({size_mb:.1f} MB)')
        print(f'   Path   : {output_wav}')
        print(f'\n🎬 Langkah berikutnya:')
        print(f'   python3 review-mix-tui.py  → mix MP4 + JSON + narasi.wav')
    else:
        print('\n  ❌ Output gak ditemukan')
    print('═' * 64)


# ============================================================
# KeyboardInterrupt handler — release lock + cleanup
# ============================================================

def _cleanup_handler(signum, frame):
    """Ctrl+C → release lock file sebelum exit."""
    if _ACTIVE_LOCK is not None:
        output_dir, prefix = _ACTIVE_LOCK
        print(f'\n⚠ Ctrl+C terdeteksi. Releasing lock: {prefix}')
        release_lock(output_dir, prefix)
    print('Batal oleh user.')
    sys.exit(1)


import signal
signal.signal(signal.SIGINT, _cleanup_handler)


if __name__ == '__main__':
    main()
