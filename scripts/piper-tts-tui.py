#!/usr/bin/env python3
"""
piper-tts-tui.py v0.1 — TUI TTS LOKAL (offline) via Piper TTS (VITS neural, ONNX runtime)

TUI #18 — OPSI TAMBAHAN untuk skenario OFFLINE murni (tanpa internet).
BUKAN pengganti edge-tts-tui v7.5 (tetap production default, Azure neural superior).

Adopsi dari 2 TUI existing (anti-amnesia pattern):
  - whisper-tui.py v2.1 → pattern LOCAL MODEL: find_piper() binary + find_voice_model()
    scan folder lokal untuk model .onnx (mirror find_whisper_cli + find_model).
  - edge-tts-tui.py v7.5 → algoritma TTS: parse_srt, smart_fit_cue (per-cue generate +
    stretch/compress fit durasi), trim/normalize/fade, mix_into_buffer, cache, lock, 2 mode.

Backend: Piper TTS (pip install piper-tts) — VITS neural TTS, model ONNX dari
HuggingFace rhasspy/piper-voices. 100% offline setelah model download sekali.

Validasi approach: subtitlekit.com (web SRT-to-audio) pakai approach SAMA PERSIS
(model 93MB download sekali, cached, jalan offline di browser, smart-fit per cue).
Confirms Piper = pilihan benar untuk TTS lokal.

2 Mode (mirror edge-tts-tui v7.5):
  - SRT mode: SRT → HDD/tts/{prefix}-audio-id-dub.wav (24kHz mono 16-bit, mix-tui compatible)
  - Narration mode: naskah.txt → HDD/tts/{stem}-narasi.wav (48kHz stereo, review-mix/konten compatible)

Setup user (Mac ~/Dubbing/):
  pip3 install piper-tts questionary numpy     # piper-tts = Python package, provides `piper` CLI
  mkdir -p ~/Dubbing/piper-voices && cd ~/Dubbing/piper-voices
  # Download model Indonesia (id_ID-gadis-medium, perempuan, ~63MB):
  curl -LO https://huggingface.co/rhasspy/piper-voices/resolve/main/id/id_ID/gadis/medium/id_ID-gadis-medium.onnx
  curl -LO https://huggingface.co/rhasspy/piper-voices/resolve/main/id/id_ID/gadis/medium/id_ID-gadis-medium.onnx.json

Pakai:
  cd ~/Dubbing && source venv/bin/activate && python3 piper-tts-tui.py

Trade-off vs edge-tts-tui v7.5:
  + 100% offline (no internet, no API key, no 429 rate limit)
  + Latensi per cue ~0.3-0.5s (lokal, vs edge ~1-2s network)
  - Voice ID terbatas: gadis (perempuan), ml/MMS (netral) — vs edge Ardi+Gadis neural
  - Kualitas VITS bagus tapi sedikit di bawah Azure neural
  - Tidak support pitch (piper cuma length-scale + noise-scale)
"""

import os
import sys
import shutil
import time
import wave
import struct
import hashlib
import subprocess
import tempfile

# ============================================================
# Version
# ============================================================
VERSION = 'v0.1'

# ============================================================
# Dependency check
# ============================================================
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
    if not _MISSING_DEPS:
        print('⚠ numpy belum terinstall. Pakai pure Python (lambat untuk audio >2 jam).')
        print('   Install recommended: pip3 install numpy')
        print()
    else:
        _MISSING_DEPS.append('numpy')

# piper-tts package provides `piper` CLI binary. Kita pakai CLI (subprocess) bukan
# Python API, supaya pattern = mirror whisper-tui (binary CLI + model file lokal).
# Cek binary setelah import (binary ada di PATH setelah pip install piper-tts).
def _find_piper_binary():
    """Cari piper CLI binary. pip install piper-tts → binary `piper` di venv Scripts/bin."""
    path = shutil.which('piper')
    if path:
        return path
    # Fallback: cek venv path umum
    candidates = [
        os.path.join(sys.prefix, 'bin', 'piper'),
        os.path.join(os.path.expanduser('~/Dubbing/venv/bin'), 'piper'),
        '/opt/homebrew/bin/piper',
        '/usr/local/bin/piper',
    ]
    for c in candidates:
        if os.path.isfile(c):
            return c
    return None

PIPER_BINARY = _find_piper_binary()

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
    print('   Install semua deps sekaligus:')
    print()
    print('   pip3 install piper-tts questionary numpy')
    print()
    print('═' * 64)
    sys.exit(1)

if not PIPER_BINARY:
    print()
    print('═' * 64)
    print('❌ piper CLI binary tidak ditemukan!')
    print('═' * 64)
    print()
    print('   piper-tts Python package BELUM terinstall (provides `piper` CLI).')
    print()
    print('   Install:')
    print()
    print('   pip3 install piper-tts')
    print()
    print('   Verifikasi:')
    print()
    print('   piper --help')
    print()
    print('═' * 64)
    sys.exit(1)

# ffmpeg wajib (decode WAV → PCM resample 24000Hz)
if not shutil.which('ffmpeg'):
    print()
    print('═' * 64)
    print('❌ ffmpeg belum terinstall!')
    print('═' * 64)
    print()
    print('   brew install ffmpeg-full   # keg-only, full codec (lihat mix-tui v3.11.7)')
    print()
    print('═' * 64)
    sys.exit(1)


# ============================================================
# Constants — match edge-tts-tui v7.5 (mix-tui compatible)
# ============================================================
OUTPUT_SAMPLE_RATE = 24000  # SRT mode: match edge-tts-tui (mix-tui expects 24kHz)
OUTPUT_CHANNELS = 1         # mono
OUTPUT_BITS = 16            # 16-bit PCM

# Narration mode: 48kHz stereo (review-mix-tui / konten-tui compatible)
NARR_SAMPLE_RATE = 48000
NARR_CHANNELS = 2

CROSSFADE_MS = 150          # ms, match edge-tts-tui
TRIM_HEAD_DB = -30
TRIM_TAIL_DB = -45
TRIM_PADDING_MS = 50
NORMALIZE_DBFS = -3.0
NOISE_FLOOR_DB = -40.0

# Piper length-scale cap untuk smart-fit (mirror edge-tts cap=1.5)
# length_scale < 1.0 = faster/shorter. Cap 1.5x speedup → floor length_scale = 1/1.5 = 0.667.
SMART_FIT_CAP_DEFAULT = 1.5


# ============================================================
# Find piper binary + voice model (mirror whisper-tui find_model)
# ============================================================

def find_piper():
    """Return piper CLI binary path."""
    return PIPER_BINARY


def find_voice_models(search_dirs=None):
    """Scan folder lokal untuk model Piper (.onnx + .onnx.json pair).
    Mirror whisper-tui find_model() — cari ggml-*.bin di folder umum.

    Return list of (model_path, config_path, voice_id) tuples.
    voice_id = basename tanpa .onnx (e.g. 'id_ID-gadis-medium').
    """
    if search_dirs is None:
        # Mirror whisper-tui search dirs + edge-tts config TTS_DIR
        try:
            from config import TTS_DIR, SSD_HOME
            search_dirs = [
                os.path.join(str(SSD_HOME), 'piper-voices'),
                os.path.join(str(SSD_HOME), 'piper-models'),
                str(TTS_DIR),
                os.path.expanduser('~/Dubbing/piper-voices'),
                os.path.expanduser('~/.local/share/piper-voices'),
            ]
        except ImportError:
            search_dirs = [
                os.path.expanduser('~/Dubbing/piper-voices'),
                os.path.expanduser('~/.local/share/piper-voices'),
                os.getcwd(),
            ]

    found = []
    seen = set()
    for d in search_dirs:
        if not d or not os.path.isdir(d):
            continue
        for root, dirs, files in os.walk(d):
            # Cek depth — jangan scan terlalu dalam (avoid venv dll)
            rel_depth = os.path.relpath(root, d).count(os.sep)
            if rel_depth > 3:
                dirs[:] = []
                continue
            # Skip venv / cache dirs
            dirs[:] = [x for x in dirs if x not in ('venv', '.cache', '__pycache__', 'node_modules', '.git')]
            for f in sorted(files):
                if f.endswith('.onnx') and not f.endswith('.onnx.json'):
                    model_path = os.path.join(root, f)
                    # config companion: same name + .json
                    config_candidates = [model_path + '.json']
                    # Juga cek pattern {stem}.onnx.json
                    stem = f[:-5]  # strip .onnx
                    config_candidates.append(os.path.join(root, stem + '.onnx.json'))
                    config_path = None
                    for c in config_candidates:
                        if os.path.isfile(c):
                            config_path = c
                            break
                    if config_path:
                        voice_id = stem
                        if voice_id not in seen:
                            seen.add(voice_id)
                            found.append((model_path, config_path, voice_id))
    return found


def label_for_voice(voice_id):
    """Human label untuk voice ID (e.g. id_ID-gadis-medium → 'Gadis — Indonesia, perempuan')."""
    vid = voice_id.lower()
    if 'gadis' in vid:
        return f'Gadis — Indonesia, perempuan ({voice_id})'
    if 'bahu' in vid:
        return f'Bahu — Indonesia, laki-laki ({voice_id})'
    if '-ml-' in vid or 'mms' in vid:
        return f'MMS Multilingual — Indonesia, netral ({voice_id})'
    if 'dimas' in vid:
        return f'Dimas — Indonesia, laki-laki ({voice_id})'
    if 'siti' in vid:
        return f'Siti — Indonesia, perempuan ({voice_id})'
    # Generic fallback
    parts = voice_id.split('-')
    return f'{voice_id}'


# ============================================================
# SRT parsing + formatting (port verbatim dari edge-tts-tui v7.5)
# ============================================================

def parse_srt(content: str):
    """Parse SRT content → list of {index, start, end, textLines}."""
    entries = []
    blocks = content.strip().replace('\r\n', '\n').replace('\r', '\n').split('\n\n')
    for block in blocks:
        lines = [l for l in block.split('\n') if l.strip()]
        if len(lines) < 2:
            continue
        # First line = index (optional, skip kalau bukan digit)
        idx = 0
        time_line_idx = 0
        if lines[0].strip().isdigit():
            idx = int(lines[0].strip())
            time_line_idx = 1
        if time_line_idx >= len(lines):
            continue
        time_line = lines[time_line_idx]
        if ' --> ' not in time_line:
            continue
        start_str, end_str = time_line.split(' --> ')[:2]
        start = _parse_time(start_str.strip())
        end = _parse_time(end_str.strip())
        if start is None or end is None:
            continue
        text_lines = lines[time_line_idx + 1:]
        entries.append({'index': idx, 'start': start, 'end': end, 'textLines': text_lines})
    return entries


def _parse_time(ts: str):
    """Parse SRT timestamp '00:01:23,456' → seconds float."""
    try:
        ts = ts.replace(',', '.')
        h, m, s = ts.split(':')
        return int(h) * 3600 + int(m) * 60 + float(s)
    except (ValueError, AttributeError):
        return None


def format_timestamp(seconds: float) -> str:
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = seconds % 60
    return f'{h:02d}:{m:02d}:{s:06.3f}'


def format_duration(seconds: float) -> str:
    if seconds < 0:
        seconds = 0
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    if h > 0:
        return f'{h}j {m}m {s}s'
    if m > 0:
        return f'{m}m {s}s'
    return f'{s}s'


def normalize_tts_text(text: str) -> str:
    """Normalize text untuk TTS: strip tags, collapse whitespace, dll (port edge-tts)."""
    import re
    # Strip HTML-ish tags <i>...</i>, <b>, dll
    text = re.sub(r'<[^>]+>', '', text)
    # Strip {...} style tags (ASS)
    text = re.sub(r'\{[^}]*\}', '', text)
    # Collapse whitespace
    text = ' '.join(text.split())
    return text.strip()


# ============================================================
# Audio processing (port verbatim dari edge-tts-tui v7.5)
# ============================================================

def decode_audio_to_pcm(audio_path: str, target_sr: int = OUTPUT_SAMPLE_RATE) -> 'np.ndarray':
    """Decode audio file (WAV/MP3/etc) → PCM float32 numpy array via ffmpeg.
    Port dari edge-tts-tui decode_mp3_to_pcm, generalized (piper output WAV, edge output MP3).
    """
    if HAS_NUMPY:
        cmd = [
            'ffmpeg', '-i', audio_path,
            '-f', 'f32le',         # raw float32 little-endian
            '-acodec', 'pcm_f32le',
            '-ar', str(target_sr),
            '-ac', '1',            # mono
            '-y', '-loglevel', 'error',
            'pipe:1',
        ]
        result = subprocess.run(cmd, capture_output=True)
        if result.returncode != 0 or len(result.stdout) == 0:
            raise RuntimeError(f'ffmpeg decode gagal: {result.stderr.decode("utf-8", errors="replace")[:200]}')
        audio = np.frombuffer(result.stdout, dtype=np.float32)
        if len(audio) == 0:
            raise RuntimeError('ffmpeg decode: output kosong')
        return audio
    else:
        # Pure Python fallback (slow): pakai wave module untuk WAV
        with wave.open(audio_path, 'rb') as wf:
            n = wf.getnframes()
            raw = wf.readframes(n)
            sw = wf.getsampwidth()
            sr = wf.getframerate()
        if sw == 2:
            data = list(struct.unpack(f'<{n}h', raw))
            data = [v / 32768.0 for v in data]
        elif sw == 1:
            data = [(b - 128) / 128.0 for b in raw]
        else:
            raise RuntimeError(f'unsupported sample width: {sw}')
        # Resample naive (linear) kalau sr != target_sr
        if sr != target_sr:
            ratio = target_sr / sr
            new_n = int(len(data) * ratio)
            resampled = []
            for i in range(new_n):
                src_idx = i / ratio
                lo = int(src_idx)
                hi = min(lo + 1, len(data) - 1)
                frac = src_idx - lo
                resampled.append(data[lo] * (1 - frac) + data[hi] * frac)
            data = resampled
        return data


def db_to_linear(db: float) -> float:
    return 10 ** (db / 20.0)


def trim_silence_asymmetric(audio: 'np.ndarray', sr: int, padding_ms: int = TRIM_PADDING_MS) -> 'np.ndarray':
    """Trim silence head (head -30dB) + tail (-45dB) dengan padding kecil."""
    if HAS_NUMPY:
        head_thresh = db_to_linear(TRIM_HEAD_DB)
        tail_thresh = db_to_linear(TRIM_TAIL_DB)
        abs_audio = np.abs(audio)
        # Head
        head_idx = np.argmax(abs_audio > head_thresh)
        if abs_audio[head_idx] <= head_thresh:
            # All silence
            return np.zeros(0, dtype=np.float32) if hasattr(audio, 'dtype') else []
        # Tail
        rev_abs = abs_audio[::-1]
        tail_idx_from_end = np.argmax(rev_abs > tail_thresh)
        tail_idx = len(audio) - tail_idx_from_end
        if tail_idx <= head_idx:
            return audio[head_idx:head_idx + 1] if len(audio) > head_idx else np.zeros(0, dtype=np.float32)
        pad = int(sr * padding_ms / 1000)
        head = max(0, head_idx - pad)
        tail = min(len(audio), tail_idx + pad)
        return audio[head:tail].copy()
    else:
        # Pure Python
        head_thresh = db_to_linear(TRIM_HEAD_DB)
        tail_thresh = db_to_linear(TRIM_TAIL_DB)
        abs_audio = [abs(v) for v in audio]
        head_idx = 0
        for i, v in enumerate(abs_audio):
            if v > head_thresh:
                head_idx = i
                break
        tail_idx = len(audio) - 1
        for i in range(len(abs_audio) - 1, -1, -1):
            if abs_audio[i] > tail_thresh:
                tail_idx = i
                break
        if tail_idx <= head_idx:
            return audio[head_idx:head_idx + 1]
        pad = int(sr * padding_ms / 1000)
        head = max(0, head_idx - pad)
        tail = min(len(audio), tail_idx + pad + 1)
        return audio[head:tail]


def peak_normalize(audio: 'np.ndarray', target_db: float = NORMALIZE_DBFS, noise_floor_db: float = NOISE_FLOOR_DB) -> 'np.ndarray':
    """Peak normalize ke target dBFS, skip kalau di bawah noise floor."""
    if HAS_NUMPY:
        if len(audio) == 0:
            return audio
        peak = float(np.max(np.abs(audio)))
        if peak < db_to_linear(noise_floor_db):
            return audio  # below noise floor, skip
        target = db_to_linear(target_db)
        gain = target / max(peak, 1e-9)
        return (audio * gain).astype(np.float32)
    else:
        if len(audio) == 0:
            return audio
        peak = max(abs(v) for v in audio)
        if peak < db_to_linear(noise_floor_db):
            return audio
        target = db_to_linear(target_db)
        gain = target / max(peak, 1e-9)
        return [v * gain for v in audio]


def apply_fade_out(audio, fade_start: int, fade_end: int):
    """Linear fade out dari fade_start ke fade_end."""
    if fade_end <= fade_start or len(audio) == 0:
        return audio
    fade_len = fade_end - fade_start
    if HAS_NUMPY:
        fade = np.linspace(1.0, 0.0, fade_len, dtype=np.float32)
        audio[fade_start:fade_end] *= fade
        return audio
    else:
        for i in range(fade_len):
            idx = fade_start + i
            if idx < len(audio):
                audio[idx] *= (1.0 - i / fade_len)
        return audio


def apply_fade_in(audio, fade_start: int, fade_end: int):
    if fade_end <= fade_start or len(audio) == 0:
        return audio
    fade_len = fade_end - fade_start
    if HAS_NUMPY:
        fade = np.linspace(0.0, 1.0, fade_len, dtype=np.float32)
        audio[fade_start:fade_end] *= fade
        return audio
    else:
        for i in range(fade_len):
            idx = fade_start + i
            if idx < len(audio):
                audio[idx] *= (i / fade_len)
        return audio


def mix_into_buffer(all_audio, audio, position: int, fade_out_end: int = None, fade_in_start: int = None, fade_len: int = 0):
    """Mix ADD audio ke all_audio pada position, dengan optional fade."""
    if len(audio) == 0:
        return all_audio
    end = position + len(audio)
    # Fade out tail kalau extend past next cue
    if fade_out_end is not None and end > fade_out_end:
        audio_len = len(audio)
        fade_start_in_audio = fade_out_end - position
        if fade_start_in_audio < audio_len:
            audio = apply_fade_out(audio.copy() if HAS_NUMPY else list(audio), fade_start_in_audio, audio_len)
            end = position + len(audio)
    # Fade in head kalau overlap dengan prev
    if fade_in_start is not None and fade_len > 0:
        audio = apply_fade_in(audio.copy() if HAS_NUMPY else list(audio), 0, min(fade_len, len(audio)))

    if end > len(all_audio):
        # Truncate ke buffer (jangan overflow)
        audio = audio[:len(all_audio) - position]
        end = len(all_audio)
    if position < 0:
        audio = audio[-position:]
        position = 0

    if HAS_NUMPY:
        all_audio[position:end] += audio
    else:
        for i in range(len(audio)):
            all_audio[position + i] += audio[i]
    return all_audio


def encode_wav(audio, sample_rate: int = OUTPUT_SAMPLE_RATE, channels: int = OUTPUT_CHANNELS, output_path: str = None):
    """Encode float32 → WAV 16-bit PCM."""
    if HAS_NUMPY:
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
            wf.setnchannels(channels)
            wf.setsampwidth(OUTPUT_BITS // 8)
            wf.setframerate(sample_rate)
            if HAS_NUMPY:
                # Kalau stereo + 1D audio, duplikasi ke 2 channel
                if channels == 2 and int_audio.ndim == 1:
                    int_audio = np.column_stack([int_audio, int_audio]).flatten()
                wf.writeframes(int_audio.tobytes())
            else:
                if channels == 2:
                    int_audio = b''.join(struct.pack('<hh', v, v) for v in struct.unpack(f'<{len(int_audio)//2}h', int_audio))
                wf.writeframes(int_audio)
        return None
    else:
        import io
        buf = io.BytesIO()
        with wave.open(buf, 'wb') as wf:
            wf.setnchannels(channels)
            wf.setsampwidth(OUTPUT_BITS // 8)
            wf.setframerate(sample_rate)
            if HAS_NUMPY:
                wf.writeframes(int_audio.tobytes())
            else:
                wf.writeframes(int_audio)
        return buf.getvalue()


# ============================================================
# Piper TTS generate (backend swap dari edge_tts)
# ============================================================

def format_length_scale(need: float, cap: float) -> float:
    """Konversi need ratio (natural_dur/cue_dur) → piper length_scale.
    length_scale: >1.0 = slower (longer), <1.0 = faster (shorter).
    Inverse dari edge-tts rate (rate>1 = faster).

    need>1.0 (audio terlalu panjang) → speedup → length_scale < 1.0.
    length_scale = max(1.0/need, 1.0/cap) — cap limit speedup.
    Contoh: need=1.5, cap=1.5 → length_scale = max(0.667, 0.667) = 0.667 (1.5x faster).
    """
    if need <= 1.0:
        return 1.0  # natural, no change
    speedup = min(need, cap)
    return max(0.1, 1.0 / speedup)  # floor 0.1 (10x) safety


def generate_cue_tts(text: str, model_path: str, config_path: str,
                     length_scale: float, output_wav: str, cue_idx: int = 0) -> bool:
    """Generate 1 cue via piper CLI → WAV file. Return True sukses.

    piper -m model.onnx -c config.json -f out.wav -i text.txt --length-scale X
    """
    # Write text ke temp file (piper -i baca dari file)
    text_fd, text_path = tempfile.mkstemp(suffix='.txt', prefix=f'piper_cue{cue_idx:04d}_')
    try:
        with os.fdopen(text_fd, 'w', encoding='utf-8') as f:
            f.write(text)
        cmd = [
            PIPER_BINARY,
            '-m', model_path,
            '-c', config_path,
            '-i', text_path,
            '-f', output_wav,
            '--length-scale', f'{length_scale:.4f}',
        ]
        try:
            result = subprocess.run(cmd, capture_output=True, timeout=60)
        except subprocess.TimeoutExpired:
            print(f'  ⚠ Piper timeout cue {cue_idx} (60s)')
            return False
        if result.returncode != 0:
            err = result.stderr.decode('utf-8', errors='replace')[:200]
            print(f'  ⚠ Piper gagal cue {cue_idx}: {err}')
            return False
        if not (os.path.isfile(output_wav) and os.path.getsize(output_wav) > 0):
            print(f'  ⚠ Piper cue {cue_idx}: output WAV kosong/tidak terbentuk')
            return False
        return True
    finally:
        try:
            os.unlink(text_path)
        except OSError:
            pass


# ============================================================
# Smart Fit (port edge-tts-tui, swap rate → length_scale)
# ============================================================

def smart_fit_cue(
    text: str,
    cue_dur: float,
    model_path: str,
    config_path: str,
    cap: float,
    cache_path: str,        # natural WAV cache (length_scale=1.0)
    cache_key: str,
    cue_idx: int = 0,
) -> 'np.ndarray':
    """Smart Fit untuk 1 cue:
    1. Generate natural (length_scale=1.0)
    2. Trim + compute need
    3. Kalau need > 1.0 → re-generate dengan length_scale = format_length_scale(need, cap)
    4. Peak normalize
    """
    smart_wav = cache_path.replace('.wav', '_smart.wav')

    # === Pass 1: natural (length_scale=1.0) ===
    if not (os.path.isfile(cache_path) and os.path.getsize(cache_path) > 0):
        ok = generate_cue_tts(text, model_path, config_path, 1.0, cache_path, cue_idx=cue_idx)
        if not ok:
            raise RuntimeError(f'Pass 1 gagal untuk cue {cue_idx}')

    audio1 = decode_audio_to_pcm(cache_path, OUTPUT_SAMPLE_RATE)
    natural_audio = trim_silence_asymmetric(audio1, OUTPUT_SAMPLE_RATE)
    natural_dur = len(natural_audio) / OUTPUT_SAMPLE_RATE
    need = natural_dur / max(0.001, cue_dur)

    if need <= 1.0:
        return peak_normalize(natural_audio)

    # === Pass 2: smart fit dengan length_scale ===
    ls = format_length_scale(need, cap)
    smart_cache_key = cache_key + f'_ls{ls:.4f}'
    if not (os.path.isfile(smart_wav) and os.path.getsize(smart_wav) > 0):
        ok = generate_cue_tts(text, model_path, config_path, ls, smart_wav, cue_idx=cue_idx)
        if not ok:
            print(f'  ⚠ Pass 2 gagal cue {cue_idx} (ls={ls}), pakai natural')
            return peak_normalize(natural_audio)
    audio2 = decode_audio_to_pcm(smart_wav, OUTPUT_SAMPLE_RATE)
    smart_audio = trim_silence_asymmetric(audio2, OUTPUT_SAMPLE_RATE)
    return peak_normalize(smart_audio)


# ============================================================
# Cache key + lock (port edge-tts-tui)
# ============================================================

def compute_cache_key(text: str, model_name: str, length_scale: float = 1.0) -> str:
    h = hashlib.sha256()
    h.update(text.encode('utf-8'))
    h.update(model_name.encode('utf-8'))
    h.update(f'{length_scale:.4f}'.encode('utf-8'))
    return h.hexdigest()[:16]


def _pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except (OSError, ProcessLookupError):
        return False


def lock_path_for(output_dir: str, prefix: str) -> str:
    return os.path.join(output_dir, f'.{prefix}.piper.lock')


def acquire_lock(output_dir: str, prefix: str) -> tuple:
    """Acquire lock file untuk paralel-safe (anti bentrok multi-instance)."""
    lock_path = lock_path_for(output_dir, prefix)
    if os.path.isfile(lock_path):
        try:
            with open(lock_path, 'r') as f:
                pid = int(f.read().strip())
            if _pid_alive(pid):
                return (False, f'Lock aktif (PID {pid}). Instance lain sedang jalan untuk prefix "{prefix}".')
        except (ValueError, IOError):
            pass  # stale lock, overwrite
    try:
        with open(lock_path, 'w') as f:
            f.write(str(os.getpid()))
        return (True, lock_path)
    except IOError as e:
        return (False, f'Tidak bisa tulis lock: {e}')


def release_lock(output_dir: str, prefix: str) -> None:
    lock_path = lock_path_for(output_dir, prefix)
    try:
        if os.path.isfile(lock_path):
            os.unlink(lock_path)
    except OSError:
        pass


def suggest_unique_prefix(output_dir: str, prefix: str, max_attempts: int = 99) -> str:
    if not os.path.isfile(os.path.join(output_dir, f'{prefix}-audio-id-dub.wav')):
        return prefix
    for i in range(2, max_attempts + 1):
        cand = f'{prefix}-{i}'
        if not os.path.isfile(os.path.join(output_dir, f'{cand}-audio-id-dub.wav')):
            return cand
    return prefix + '-' + str(int(time.time()))


# ============================================================
# TUI helpers
# ============================================================

def clear_screen():
    os.system('clear' if os.name != 'nt' else 'cls')


def print_banner():
    print('╔' + '═' * 64 + '╗')
    print('║  🗣️  Piper TTS TUI v0.1 — TTS LOKAL OFFLINE (VITS neural)   ║')
    print('║' + ' ' * 64 + '║')
    print('║  Backend : Piper TTS (ONNX) — 100% offline                  ║')
    print('║  Pattern : adopsi whisper-tui (local model) + edge-tts algoritma ║')
    print('╚' + '═' * 64 + '╝')
    print()


def find_srt_files(search_dir):
    if not os.path.isdir(search_dir):
        return []
    files = [f for f in os.listdir(search_dir) if f.lower().endswith('.srt')]
    files.sort()
    return files


# ============================================================
# SRT mode (mirror edge-tts-tui main, 7 step)
# ============================================================

def main():
    print_banner()
    print('📋 Pilihan: ikuti petunjuk di layar.')
    print('   Navigasi: ↑↓ arrow keys, Enter konfirmasi, Ctrl+C batal')
    print()

    # Mode selection (mirror edge-tts v7.5)
    mode = questionary.select(
        'Mode:',
        choices=[
            'SRT (dub per cue dari subtitle)',
            'Narration (1 naskah plain text → 1 WAV)',
        ],
        default='SRT (dub per cue dari subtitle)',
    ).ask()

    if 'Narration' in mode:
        main_narration()
        return

    # === Cari voice model duluan (mirror whisper-tui find_model) ===
    voices = find_voice_models()
    if not voices:
        print()
        print('═' * 64)
        print('❌ Tidak ada model Piper ditemukan!')
        print('═' * 64)
        print()
        print('   Download model Indonesia ke ~/Dubbing/piper-voices/:')
        print()
        print('   mkdir -p ~/Dubbing/piper-voices && cd ~/Dubbing/piper-voices')
        print('   curl -LO https://huggingface.co/rhasspy/piper-voices/resolve/main/id/id_ID/gadis/medium/id_ID-gadis-medium.onnx')
        print('   curl -LO https://huggingface.co/rhasspy/piper-voices/resolve/main/id/id_ID/gadis/medium/id_ID-gadis-medium.onnx.json')
        print()
        print('═' * 64)
        sys.exit(1)

    # === Step 1: Pilih SRT ===
    print('▶ Step 1/7: Pilih SRT')
    try:
        from config import INPUT_DIR, TTS_DIR, ensure_hdd
        if ensure_hdd():
            default_srt_dir = str(INPUT_DIR)
        else:
            default_srt_dir = os.getcwd()
    except ImportError:
        default_srt_dir = os.getcwd()
        TTS_DIR = os.getcwd()

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
        srt_path = questionary.text(f'Tidak ada SRT di {default_srt_dir}. Ketik path lengkap:').ask()
    if not srt_path or not os.path.isfile(srt_path):
        print('❌ File SRT tidak ditemukan.')
        sys.exit(1)
    print(f'  ✓ {srt_path}')
    print()

    # === Step 2: Output dir ===
    print('▶ Step 2/7: Output directory')
    try:
        default_out = str(TTS_DIR)
    except NameError:
        default_out = os.path.dirname(os.path.abspath(srt_path))
    output_dir = questionary.text('Output directory:', default=default_out).ask()
    if not output_dir:
        output_dir = default_out
    os.makedirs(output_dir, exist_ok=True)
    print(f'  ✓ {output_dir}')
    print()

    # === Step 3: Voice (piper local model) ===
    print('▶ Step 3/7: Pilih voice (model Piper lokal)')
    voice_labels = [label_for_voice(v[2]) for v in voices]
    voice_choice = questionary.select(
        f'Voice ({len(voices)} model ditemukan):',
        choices=voice_labels,
        default=voice_labels[0],
    ).ask()
    model_path, config_path, voice_id = voices[voice_labels.index(voice_choice)]
    print(f'  ✓ {voice_id}')
    print(f'    model : {model_path}')
    print(f'    config: {config_path}')
    print()

    # === Step 4: Length-scale baseline (rate) ===
    print('▶ Step 4/7: Rate baseline (length-scale)')
    rate_choice = questionary.select(
        'Rate (1.0 = natural, >1.0 = lebih pelan/panjang, <1.0 = lebih cepat):',
        choices=[
            '1.00 (natural)',
            '0.90 (sedikit cepat)',
            '1.10 (sedikit pelan)',
            '1.20 (lebih pelan)',
            '[Ketik manual]',
        ],
        default='1.00 (natural)',
    ).ask()
    if rate_choice == '[Ketik manual]':
        ls_str = questionary.text('Length-scale (0.1 - 3.0):', default='1.0').ask()
        try:
            baseline_ls = float(ls_str)
        except ValueError:
            baseline_ls = 1.0
    else:
        baseline_ls = float(rate_choice.split(' ')[0])
    print(f'  ✓ length-scale baseline = {baseline_ls}')
    print()

    # === Step 5: Smart Fit ===
    print('▶ Step 5/7: Smart Fit')
    smart_fit = questionary.confirm(
        'Aktifkan Smart Fit? (re-generate cue yang terlalu panjang dengan rate lebih cepat agar fit durasi SRT)',
        default=True,
    ).ask()
    cap = SMART_FIT_CAP_DEFAULT
    if smart_fit:
        cap_str = questionary.text(
            f'Max speedup cap (default {SMART_FIT_CAP_DEFAULT}, contoh 1.5 = max 1.5x lebih cepat):',
            default=str(SMART_FIT_CAP_DEFAULT),
        ).ask()
        try:
            cap = float(cap_str)
        except ValueError:
            cap = SMART_FIT_CAP_DEFAULT
    print(f'  ✓ Smart Fit: {"ON" if smart_fit else "OFF"}, cap={cap}')
    print()

    # === Step 6: Prefix ===
    print('▶ Step 6/7: Prefix output')
    default_prefix = os.path.splitext(os.path.basename(srt_path))[0]
    prefix = questionary.text('Prefix (output: {prefix}-audio-id-dub.wav):', default=default_prefix).ask()
    if not prefix:
        prefix = default_prefix
    prefix = suggest_unique_prefix(output_dir, prefix)
    print(f'  ✓ {prefix}')
    print()

    # === Parse SRT ===
    with open(srt_path, 'r', encoding='utf-8-sig') as f:
        content = f.read()
    entries = parse_srt(content)
    if not entries:
        print('❌ SRT kosong/tidak terparse.')
        sys.exit(1)
    total_dur = entries[-1]['end']

    # Estimasi (piper lokal ~0.3-0.5x realtime per cue, tanpa network)
    est_per_cue = 0.4
    est_total_sec = len(entries) * est_per_cue
    if smart_fit:
        est_total_sec *= 1.3  # extra pass untuk cue yang need>1.0

    print('═' * 64)
    print('📋 Ringkasan:')
    print('═' * 64)
    print(f'  SRT      : {os.path.basename(srt_path)}')
    print(f'  Output   : {os.path.join(output_dir, prefix + "-audio-id-dub.wav")}')
    print(f'  Voice    : {voice_id}')
    print(f'  L-scale  : {baseline_ls} (baseline)')
    print(f'  Smart Fit: {"ON" if smart_fit else "OFF"}, cap={cap}')
    print(f'  Cues     : {len(entries)}')
    print(f'  Durasi   : {format_duration(total_dur)}')
    print(f'  Estimasi : {format_duration(est_total_sec)} (lokal, ~0.4s/cue)')
    print('═' * 64)
    print()

    if not questionary.confirm('Lanjut generate?', default=True).ask():
        print('Batal.')
        sys.exit(0)

    # === Lock (paralel-safe) ===
    ok, lock_info = acquire_lock(output_dir, prefix)
    if not ok:
        print(f'❌ {lock_info}')
        sys.exit(1)

    try:
        # === Generate per cue + mix inline ===
        print()
        print('═' * 64)
        print('🚀 Mulai generate TTS (Piper lokal) + mix inline...')
        print('═' * 64)
        print()

        cache_dir = os.path.join(output_dir, '.cache')
        os.makedirs(cache_dir, exist_ok=True)

        total_samples = int(total_dur * OUTPUT_SAMPLE_RATE)
        if HAS_NUMPY:
            all_audio = np.zeros(total_samples, dtype=np.float32)
        else:
            all_audio = [0.0] * total_samples
        print(f'  Buffer: {total_samples} samples = {total_dur/3600:.1f}j = {total_samples*4/1024/1024:.0f} MB')
        print()

        success_count = 0
        fail_count = 0
        start_time = time.time()
        crossfade_samples = int(OUTPUT_SAMPLE_RATE * CROSSFADE_MS / 1000)

        for i, entry in enumerate(entries):
            cue_idx = i + 1
            text = normalize_tts_text(' '.join(entry['textLines']))
            cue_dur = entry['end'] - entry['start']
            position = int(entry['start'] * OUTPUT_SAMPLE_RATE)

            # Fade overlap handling
            prev_entry = entries[i - 1] if i > 0 else None
            fade_in_start = None
            fade_len = 0
            if prev_entry:
                prev_end_samples = int(prev_entry['end'] * OUTPUT_SAMPLE_RATE)
                if position < prev_end_samples:
                    fade_in_start = position
                    fade_len = min(crossfade_samples, prev_end_samples - position)

            next_entry = entries[i + 1] if i + 1 < len(entries) else None
            fade_out_end = None
            if next_entry:
                fade_out_end = int(next_entry['start'] * OUTPUT_SAMPLE_RATE)

            if not text:
                continue

            cache_key = compute_cache_key(text, voice_id, baseline_ls)
            cache_path = os.path.join(cache_dir, f'{prefix}-cue-{cue_idx:04d}-{cache_key}.wav')

            # Baseline length-scale diterapkan ke natural cache (kalau != 1.0)
            natural_ls = baseline_ls

            cached_audio = None
            if os.path.isfile(cache_path) and os.path.getsize(cache_path) > 0:
                try:
                    audio1 = decode_audio_to_pcm(cache_path, OUTPUT_SAMPLE_RATE)
                    natural_audio = trim_silence_asymmetric(audio1, OUTPUT_SAMPLE_RATE)
                    natural_dur = len(natural_audio) / OUTPUT_SAMPLE_RATE
                    need = natural_dur / max(0.001, cue_dur)
                    if not smart_fit or need <= 1.0:
                        cached_audio = peak_normalize(natural_audio)
                except Exception as e:
                    print(f'  ⚠ Cache corrupt cue {cue_idx}, regenerate: {e}')

            if cached_audio is None:
                try:
                    if smart_fit:
                        # Smart fit: pass 1 natural (baseline_ls), pass 2 speedup kalau need>1.0
                        # Note: smart_fit_cue pakai natural_ls=1.0 internal; kalau baseline_ls != 1.0,
                        # apply baseline ke smart result via post-process speed (kompleks). Untuk v0.1,
                        # baseline_ls != 1.0 + smart_fit → smart_fit pakai baseline_ls sebagai natural.
                        final_audio = _smart_fit_cue_with_baseline(
                            text, cue_dur, model_path, config_path, baseline_ls, cap,
                            cache_path, cache_key, cue_idx=cue_idx,
                        )
                    else:
                        if not (os.path.isfile(cache_path) and os.path.getsize(cache_path) > 0):
                            if not generate_cue_tts(text, model_path, config_path, natural_ls, cache_path, cue_idx=cue_idx):
                                fail_count += 1
                                continue
                        audio1 = decode_audio_to_pcm(cache_path, OUTPUT_SAMPLE_RATE)
                        natural_audio = trim_silence_asymmetric(audio1, OUTPUT_SAMPLE_RATE)
                        final_audio = peak_normalize(natural_audio)
                except Exception as e:
                    print(f'  ⚠ Cue {cue_idx} gagal: {e}')
                    fail_count += 1
                    continue
            else:
                final_audio = cached_audio

            mix_into_buffer(all_audio, final_audio, position,
                            fade_out_end=fade_out_end, fade_in_start=fade_in_start, fade_len=fade_len)
            success_count += 1

            if cue_idx % 10 == 0 or cue_idx == len(entries):
                elapsed = time.time() - start_time
                pct = cue_idx / len(entries) * 100
                eta = (elapsed / cue_idx) * (len(entries) - cue_idx) if cue_idx > 0 else 0
                sys.stdout.write(
                    f'\r  [{cue_idx}/{len(entries)}] {pct:5.1f}% | '
                    f'ok={success_count} fail={fail_count} | '
                    f'elapsed={format_duration(elapsed)} | ETA={format_duration(eta)}   '
                )
                sys.stdout.flush()

        print()
        elapsed = time.time() - start_time
        print()
        print(f'  ✓ Selesai generate: {success_count} cue ok, {fail_count} fail ({format_duration(elapsed)})')

        # === Encode output ===
        output_path = os.path.join(output_dir, f'{prefix}-audio-id-dub.wav')
        print(f'  Encoding WAV → {output_path}...')
        encode_wav(all_audio, OUTPUT_SAMPLE_RATE, OUTPUT_CHANNELS, output_path)

        if os.path.isfile(output_path):
            size_mb = os.path.getsize(output_path) / 1024 / 1024
            print()
            print('═' * 64)
            print('✅ SELESAI!')
            print(f'   Output : {output_path}')
            print(f'   Size   : {size_mb:.1f} MB')
            print(f'   Format : {OUTPUT_SAMPLE_RATE}Hz mono 16-bit PCM (mix-tui compatible)')
            print(f'   Cues   : {success_count} ok / {fail_count} fail / {len(entries)} total')
            print(f'   Waktu  : {format_duration(elapsed)}')
            print()
            print('🎬 Langkah berikutnya:')
            print(f'   1. Preview: open {output_path}')
            print(f'   2. Feed ke mix-tui (sama dengan edge-tts SRT output)')
            print('═' * 64)
        else:
            print('❌ Output tidak terbentuk.')

    except KeyboardInterrupt:
        print('\n\n⏹ Dibatalkan user.')
    finally:
        release_lock(output_dir, prefix)


def _smart_fit_cue_with_baseline(text, cue_dur, model_path, config_path, baseline_ls, cap,
                                  cache_path, cache_key, cue_idx=0):
    """Smart fit dengan baseline length-scale diterapkan.
    Pass 1: natural = baseline_ls (bukan 1.0). need diukur relatif.
    Pass 2: speedup tambahan kalau masih need>1.0.
    """
    if not (os.path.isfile(cache_path) and os.path.getsize(cache_path) > 0):
        if not generate_cue_tts(text, model_path, config_path, baseline_ls, cache_path, cue_idx=cue_idx):
            raise RuntimeError(f'Pass 1 gagal cue {cue_idx}')

    audio1 = decode_audio_to_pcm(cache_path, OUTPUT_SAMPLE_RATE)
    natural_audio = trim_silence_asymmetric(audio1, OUTPUT_SAMPLE_RATE)
    natural_dur = len(natural_audio) / OUTPUT_SAMPLE_RATE
    need = natural_dur / max(0.001, cue_dur)

    if need <= 1.0:
        return peak_normalize(natural_audio)

    # Pass 2: speedup tambahan. Total length_scale = baseline_ls / speedup
    speedup = min(need, cap)
    total_ls = max(0.1, baseline_ls / speedup)
    smart_wav = cache_path.replace('.wav', f'_smart_ls{total_ls:.4f}.wav')
    if not (os.path.isfile(smart_wav) and os.path.getsize(smart_wav) > 0):
        if not generate_cue_tts(text, model_path, config_path, total_ls, smart_wav, cue_idx=cue_idx):
            print(f'  ⚠ Pass 2 gagal cue {cue_idx} (ls={total_ls}), pakai natural')
            return peak_normalize(natural_audio)
    audio2 = decode_audio_to_pcm(smart_wav, OUTPUT_SAMPLE_RATE)
    smart_audio = trim_silence_asymmetric(audio2, OUTPUT_SAMPLE_RATE)
    return peak_normalize(smart_audio)


# ============================================================
# Narration mode (mirror edge-tts-tui main_narration, 48kHz stereo)
# ============================================================

def main_narration():
    print('═' * 64)
    print('🎙️  Narration Mode — naskah plain text → 1 WAV (48kHz stereo)')
    print('═' * 64)
    print()

    # Voice model
    voices = find_voice_models()
    if not voices:
        print('❌ Tidak ada model Piper ditemukan. Download model dulu.')
        sys.exit(1)

    # Step 1: naskah
    print('▶ Step 1/6: Pilih naskah (.txt)')
    try:
        from config import TTS_DIR, REVIEW_DIR, ensure_hdd
        if ensure_hdd():
            default_dirs = [str(REVIEW_DIR), str(TTS_DIR)]
        else:
            default_dirs = [os.getcwd()]
    except ImportError:
        default_dirs = [os.getcwd()]
        TTS_DIR = os.getcwd()

    txt_files = []
    for d in default_dirs:
        if os.path.isdir(d):
            txt_files.extend(os.path.join(d, f) for f in os.listdir(d) if f.lower().endswith('.txt'))
    if txt_files:
        txt_files.sort()
        rel_files = [os.path.relpath(f) for f in txt_files]
        choice = questionary.select(
            f'Naskah (ditemukan {len(txt_files)}):',
            choices=rel_files + ['[Ketik path manual]'],
            default=rel_files[0],
        ).ask()
        if choice == '[Ketik path manual]':
            naskah_path = questionary.text('Path naskah .txt:').ask()
        else:
            naskah_path = choice
    else:
        naskah_path = questionary.text('Path naskah .txt:').ask()
    if not naskah_path or not os.path.isfile(naskah_path):
        print('❌ File naskah tidak ditemukan.')
        sys.exit(1)
    with open(naskah_path, 'r', encoding='utf-8-sig') as f:
        naskah = f.read()
    print(f'  ✓ {naskah_path} ({len(naskah)} chars)')
    print()

    # Step 2: output
    print('▶ Step 2/6: Output directory')
    try:
        default_out = str(TTS_DIR)
    except NameError:
        default_out = os.path.dirname(os.path.abspath(naskah_path))
    output_dir = questionary.text('Output directory:', default=default_out).ask()
    if not output_dir:
        output_dir = default_out
    os.makedirs(output_dir, exist_ok=True)
    print(f'  ✓ {output_dir}')
    print()

    # Step 3: voice
    print('▶ Step 3/6: Voice')
    voice_labels = [label_for_voice(v[2]) for v in voices]
    voice_choice = questionary.select(f'Voice ({len(voices)} model):', choices=voice_labels, default=voice_labels[0]).ask()
    model_path, config_path, voice_id = voices[voice_labels.index(voice_choice)]
    print(f'  ✓ {voice_id}')
    print()

    # Step 4: length-scale
    print('▶ Step 4/6: Rate (length-scale)')
    ls_str = questionary.text('Length-scale (1.0=natural, 0.9=cepat, 1.1=pelan):', default='1.0').ask()
    try:
        length_scale = float(ls_str)
    except ValueError:
        length_scale = 1.0
    print(f'  ✓ {length_scale}')
    print()

    # Step 5: output filename
    print('▶ Step 5/6: Output filename')
    stem = os.path.splitext(os.path.basename(naskah_path))[0]
    default_name = f'{stem}-narasi.wav'
    out_name = questionary.text('Output filename:', default=default_name).ask()
    if not out_name:
        out_name = default_name
    output_path = os.path.join(output_dir, out_name)
    print(f'  ✓ {output_path}')
    print()

    # Split naskah jadi kalimat (piper proses per kalimat, concat hasil)
    import re
    sentences = re.split(r'(?<=[.!?。])\s+', naskah.strip())
    sentences = [s.strip() for s in sentences if s.strip()]
    if not sentences:
        print('❌ Naskah kosong.')
        sys.exit(1)

    print('═' * 64)
    print('📋 Ringkasan:')
    print(f'  Naskah   : {os.path.basename(naskah_path)} ({len(sentences)} kalimat)')
    print(f'  Voice    : {voice_id}')
    print(f'  L-scale  : {length_scale}')
    print(f'  Output   : {output_path} (48kHz stereo)')
    print('═' * 64)
    print()

    if not questionary.confirm('Lanjut generate?', default=True).ask():
        print('Batal.')
        sys.exit(0)

    print('🚀 Mulai generate narasi (Piper lokal)...')
    print()
    start_time = time.time()

    # Generate per kalimat, concat
    all_chunks = []
    tmp_dir = tempfile.mkdtemp(prefix='piper_narr_')
    try:
        for i, sent in enumerate(sentences):
            chunk_wav = os.path.join(tmp_dir, f'chunk_{i:05d}.wav')
            ok = generate_cue_tts(sent, model_path, config_path, length_scale, chunk_wav, cue_idx=i + 1)
            if not ok:
                continue
            audio = decode_audio_to_pcm(chunk_wav, NARR_SAMPLE_RATE)
            audio = trim_silence_asymmetric(audio, NARR_SAMPLE_RATE)
            audio = peak_normalize(audio)
            # Tambah silence antar kalimat (200ms)
            sil = int(NARR_SAMPLE_RATE * 0.2)
            if HAS_NUMPY:
                audio = np.concatenate([audio, np.zeros(sil, dtype=np.float32)])
            else:
                audio = audio + [0.0] * sil
            all_chunks.append(audio)
            if (i + 1) % 5 == 0 or i + 1 == len(sentences):
                elapsed = time.time() - start_time
                pct = (i + 1) / len(sentences) * 100
                sys.stdout.write(f'\r  [{i+1}/{len(sentences)}] {pct:5.1f}% | elapsed={format_duration(elapsed)}   ')
                sys.stdout.flush()
        print()
        print()

        if not all_chunks:
            print('❌ Tidak ada chunk berhasil di-generate.')
            sys.exit(1)

        # Concat
        if HAS_NUMPY:
            final = np.concatenate(all_chunks)
        else:
            final = []
            for c in all_chunks:
                final.extend(c)

        encode_wav(final, NARR_SAMPLE_RATE, NARR_CHANNELS, output_path)
        elapsed = time.time() - start_time

        if os.path.isfile(output_path):
            size_mb = os.path.getsize(output_path) / 1024 / 1024
            print('═' * 64)
            print('✅ SELESAI!')
            print(f'   Output : {output_path}')
            print(f'   Size   : {size_mb:.1f} MB')
            print(f'   Format : {NARR_SAMPLE_RATE}Hz stereo 16-bit PCM (review-mix/konten-tui compatible)')
            print(f'   Waktu  : {format_duration(elapsed)}')
            print()
            print('🎬 Langkah berikutnya:')
            print(f'   Feed ke review-mix-tui / konten-tui / talkinghead-tui / manim-shorts-tui')
            print('═' * 64)
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


# ============================================================
# Entry
# ============================================================

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print('\n\n⏹ Dibatalkan user.')
        sys.exit(130)
