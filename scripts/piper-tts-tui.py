#!/usr/bin/env python3
"""
piper-tts-tui.py v0.2 — TUI TTS LOKAL (offline) via Piper TTS (VITS neural, ONNX)

TUI #18 — OPSI TAMBAHAN untuk skenario OFFLINE murni (tanpa internet).
BUKAN pengganti edge-tts-tui v7.5 (tetap production default, Azure neural superior).

v0.2 (22 Nov 2026) — GPU Metal via CoreML EP:
  - Switch dari CLI subprocess (v0.1) → Python API (PiperVoice) supaya bisa
    pilih onnxruntime ExecutionProvider.
  - InferenceSession dibangun dengan providers=['CoreMLExecutionProvider',
    'CPUExecutionProvider'] → Metal GPU di Apple Silicon (M1/M2/M3), fallback
    CPU di Linux/Intel. Mac gak panas, lebih cepat (mirip mix-tui GPU path).
  - Model load SEKALI per session (v0.1 CLI reload model per cue = lambat).
    Speedup besar untuk SRT ribuan cue.
  - Output audio langsung float32 array (no temp WAV + ffmpeg decode roundtrip).

Adopsi dari 2 TUI existing (anti-amnesia pattern):
  - whisper-tui.py v2.1 → pattern LOCAL MODEL: find_voice_model() scan folder
    lokal untuk .onnx + .onnx.json pair (mirror find_model scan ggml-*.bin).
    whisper-tui pakai Metal via whisper.cpp native; piper-tts pakai Metal via
    onnxruntime CoreMLExecutionProvider.
  - edge-tts-tui.py v7.5 → algoritma TTS: parse_srt, smart_fit_cue (per-cue
    generate + stretch/compress fit durasi), trim/normalize/fade, mix_into_buffer,
    cache key + lock file, 2 mode (SRT + Narasi).

Backend: Piper TTS (pip install piper-tts) — VITS neural TTS, model ONNX dari
HuggingFace rhasspy/piper-voices. 100% offline setelah model download sekali.
Python API: PiperVoice.load() cuma support use_cuda (CUDA). Untuk CoreML/Metal
di M1, bypass load() — baca config JSON sendiri + bangun InferenceSession dengan
providers list (CoreML duluan, CPU fallback) + construct PiperVoice langsung.

Validasi approach: subtitlekit.com (web SRT-to-audio) pakai approach SAMA PERSIS
(model 93MB download sekali, cached, jalan offline, smart-fit per cue).

2 Mode (mirror edge-tts-tui v7.5):
  - SRT mode: SRT → HDD/tts/{prefix}-audio-id-dub.wav (24kHz mono 16-bit, mix-tui compatible)
  - Narration mode: naskah.txt → HDD/tts/{stem}-narasi.wav (48kHz stereo, review-mix/konten compatible)

Setup user (Mac ~/Dubbing/):
  pip3 install piper-tts questionary numpy huggingface_hub
  mkdir -p ~/Dubbing/piper-voices && cd ~/Dubbing/piper-voices
  # Download voice Indonesia (hanya id_ID-news_tts-medium yang tersedia di repo
  # resmi rhasspy/piper-voices per Nov 2026; curl -L kena "Entry not found"
  # karena HF LFS redirect, pakai huggingface_hub):
  python3 -c "
from huggingface_hub import hf_hub_download
import shutil, os
for path in [
    'id/id_ID/news_tts/medium/id_ID-news_tts-medium.onnx',
    'id/id_ID/news_tts/medium/id_ID-news_tts-medium.onnx.json',
]:
    p = hf_hub_download(repo_id='rhasspy/piper-voices', filename=path)
    shutil.copy(p, os.path.basename(p))
    print('downloaded', os.path.basename(p))
"

Pakai:
  cd ~/Dubbing && source venv/bin/activate && python3 piper-tts-tui.py

GPU check (verifikasi Metal aktif):
  python3 -c "import onnxruntime as ort; print(ort.get_available_providers())"
  → harus ada 'CoreMLExecutionProvider' di Mac M1. Kalau cuma CPUExecutionProvider,
    onnxruntime versi CPU-only (reinstall: pip3 install onnxruntime --force-reinstall).

Trade-off vs edge-tts-tui v7.5:
  + 100% offline (no internet, no API key, no 429 rate limit)
  + GPU Metal (CoreML EP) di M1 — Mac gak panas, cepat
  + Model load sekali (vs CLI reload per cue)
  - Voice ID terbatas: hanya id_ID-news_tts-medium di repo HF resmi (Nov 2026)
    — vs edge Ardi+Gadis neural. Voice lain (gadis/arjun/ayu) tidak ada di repo
    rhasspy/piper-voices (404 Entry not found). Cari mirror community kalau perlu.
  - Kualitas VITS bagus tapi sedikit di bawah Azure neural
  - Tidak support pitch (piper cuma length-scale + noise-scale)
"""

import os
import sys
import json
import shutil
import time
import wave
import struct
import hashlib
from pathlib import Path

# ============================================================
# Version
# ============================================================
VERSION = 'v0.2'

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
        print('⚠ numpy belum terinstall. Install: pip3 install numpy')
        print()
    else:
        _MISSING_DEPS.append('numpy')

# piper Python package (provides PiperVoice + onnxruntime dependency)
try:
    import piper
    from piper import PiperVoice
    from piper.config import PiperConfig, SynthesisConfig
    HAS_PIPER = True
except ImportError:
    HAS_PIPER = False
    _MISSING_DEPS.append('piper-tts')

# onnxruntime (comes with piper-tts, check CoreML EP availability)
try:
    import onnxruntime as ort
    _ORT_PROVIDERS = ort.get_available_providers()
    _HAS_COREML = 'CoreMLExecutionProvider' in _ORT_PROVIDERS
except ImportError:
    _ORT_PROVIDERS = []
    _HAS_COREML = False
    _MISSING_DEPS.append('onnxruntime')

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
    print('   pip3 install piper-tts questionary numpy')
    print()
    print('═' * 64)
    sys.exit(1)


# ============================================================
# Constants — match edge-tts-tui v7.5 (mix-tui compatible)
# ============================================================
OUTPUT_SAMPLE_RATE = 24000  # SRT mode: match edge-tts-tui (mix-tui expects 24kHz)
OUTPUT_CHANNELS = 1
OUTPUT_BITS = 16

NARR_SAMPLE_RATE = 48000  # Narration mode: stereo
NARR_CHANNELS = 2

CROSSFADE_MS = 150
TRIM_HEAD_DB = -30
TRIM_TAIL_DB = -30          # match edge-tts-tui (was -45, kept too much trailing audio → overflow → numpuk)
TRIM_PADDING_MS = 30        # match edge-tts-tui (was 50, added too much padding)
NORMALIZE_DBFS = -2.0       # match edge-tts-tui (was -3.0)
NOISE_FLOOR_DB = -50.0      # match edge-tts-tui (was -40.0)

# Smart Fit cap — SELECT match edge-tts-tui (4 opsi). Default 1.5x = config
# clean yang user pakai (2x = cepat seperti robot, 1.25x = paling natural tapi
# sering overflow). VITS length-scale preserve pitch, jadi 1.5x tidak chipmunk.
# JANGAN default ke 2x/3x — 1.5x adalah sweet spot naturalness (user verified).
SMART_FIT_CAP_DEFAULT = 1.5
SMART_FIT_DEBUG = os.environ.get('PIPER_SMART_FIT_DEBUG') == '1'


# ============================================================
# GPU detection (CoreML EP = Metal di M1)
# ============================================================

def get_gpu_status():
    """Return (provider_label, has_coreml, providers_list)."""
    if _HAS_COREML:
        return ('CoreML (Metal GPU)', True, _ORT_PROVIDERS)
    return ('CPU', False, _ORT_PROVIDERS)


# ============================================================
# Voice model discovery (mirror whisper-tui find_model)
# ============================================================

def find_voice_models(search_dirs=None):
    """Scan folder lokal untuk model Piper (.onnx + .onnx.json pair).
    Return list of (model_path, config_path, voice_id).
    """
    if search_dirs is None:
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
            rel_depth = os.path.relpath(root, d).count(os.sep)
            if rel_depth > 3:
                dirs[:] = []
                continue
            dirs[:] = [x for x in dirs if x not in ('venv', '.cache', '__pycache__', 'node_modules', '.git')]
            for f in sorted(files):
                if f.endswith('.onnx') and not f.endswith('.onnx.json'):
                    model_path = os.path.join(root, f)
                    stem = f[:-5]
                    config_candidates = [
                        model_path + '.json',
                        os.path.join(root, stem + '.onnx.json'),
                    ]
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
    vid = voice_id.lower()
    if 'news_tts' in vid or 'news-tts' in vid:
        return f'News TTS — Indonesia, netral/news ({voice_id})'
    if 'gadis' in vid:
        return f'Gadis — Indonesia, perempuan ({voice_id})'
    if 'bahu' in vid:
        return f'Bahu — Indonesia, laki-laki ({voice_id})'
    if 'arjun' in vid:
        return f'Arjun — Indonesia, laki-laki ({voice_id})'
    if 'ayu' in vid:
        return f'Ayu — Indonesia, perempuan ({voice_id})'
    if 'sari' in vid:
        return f'Sari — Indonesia, perempuan ({voice_id})'
    if '-ml-' in vid or 'mms' in vid:
        return f'MMS Multilingual — Indonesia, netral ({voice_id})'
    if 'dimas' in vid:
        return f'Dimas — Indonesia, laki-laki ({voice_id})'
    if 'siti' in vid:
        return f'Siti — Indonesia, perempuan ({voice_id})'
    return voice_id


# ============================================================
# Load Piper voice with CoreML EP (bypass PiperVoice.load untuk GPU Metal)
# ============================================================

_VOICE_CACHE = {}


def load_piper_voice(model_path, config_path, use_gpu=True):
    """Load PiperVoice dengan ExecutionProvider pilihan.
    Bypass PiperVoice.load() (cuma support use_cuda) — bangun InferenceSession
    sendiri dengan providers=['CoreMLExecutionProvider', 'CPUExecutionProvider'].

    use_gpu=True + CoreML EP available → Metal GPU di M1.
    use_gpu=False atau no CoreML → CPU.
    """
    cache_key = (model_path, use_gpu)
    if cache_key in _VOICE_CACHE:
        return _VOICE_CACHE[cache_key]

    with open(config_path, 'r', encoding='utf-8') as f:
        config_dict = json.load(f)
    config = PiperConfig.from_dict(config_dict)

    if use_gpu and _HAS_COREML:
        # CoreML EP = Metal GPU di Apple Silicon. CoreML EP TIDAK accept
        # 'device_id' option (itu opsi CUDA). Pakai bare string, atau opsional
        # 'MLComputeUnits': 'All'/'CPUAndGPU'/'CPUOnly'/'CPUAndNeuralEngine'.
        # Default 'All' = GPU+ANE+CPU, paling cepat. Bare string = default juga.
        providers = [
            'CoreMLExecutionProvider',
            'CPUExecutionProvider',
        ]
    else:
        providers = ['CPUExecutionProvider']

    sess_options = ort.SessionOptions()
    sess_options.intra_op_num_threads = 4
    sess_options.inter_op_num_threads = 1

    session = ort.InferenceSession(
        model_path,
        sess_options=sess_options,
        providers=providers,
    )

    # Ambil EP ACTUAL dari session (bukan asumsi). CoreML bisa di-reject onnxruntime
    # kalau operator tertentu gak support → fallback CPU otomatis. Label harus jujur.
    actual_eps = session.get_providers()
    if 'CoreMLExecutionProvider' in actual_eps:
        ep_label = 'CoreML (Metal GPU)'
    else:
        ep_label = 'CPU (CoreML fallback)' if (_HAS_COREML and use_gpu) else 'CPU'
    voice = PiperVoice(
        session=session,
        config=config,
        espeak_data_dir=Path(piper.__path__[0]) / 'espeak-ng-data',
        download_dir=Path(os.getcwd()),
    )
    _VOICE_CACHE[cache_key] = (voice, config, ep_label, actual_eps)
    return voice, config, ep_label, actual_eps


# ============================================================
# SRT parsing + formatting (port verbatim dari edge-tts-tui v7.5)
# ============================================================

def parse_srt(content):
    entries = []
    blocks = content.strip().replace('\r\n', '\n').replace('\r', '\n').split('\n\n')
    for block in blocks:
        lines = [l for l in block.split('\n') if l.strip()]
        if len(lines) < 2:
            continue
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


def _parse_time(ts):
    try:
        ts = ts.replace(',', '.')
        h, m, s = ts.split(':')
        return int(h) * 3600 + int(m) * 60 + float(s)
    except (ValueError, AttributeError):
        return None


def format_timestamp(seconds):
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = seconds % 60
    return f'{h:02d}:{m:02d}:{s:06.3f}'


def format_duration(seconds):
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


def normalize_tts_text(text):
    import re
    text = re.sub(r'<[^>]+>', '', text)
    text = re.sub(r'\{[^}]*\}', '', text)
    text = ' '.join(text.split())
    return text.strip()


# ============================================================
# Audio processing (port dari edge-tts-tui v7.5 + resample helper)
# ============================================================

def resample_audio(audio, src_sr, target_sr):
    """Resample float32 array via linear interpolation (numpy). Cepat, cukup
    untuk TTS audio (tidak ada high-freq content)."""
    if src_sr == target_sr or len(audio) == 0:
        return audio
    if HAS_NUMPY:
        ratio = target_sr / src_sr
        new_len = int(len(audio) * ratio)
        if new_len < 1:
            return np.zeros(1, dtype=np.float32)
        indices = np.linspace(0, len(audio) - 1, new_len)
        lo = indices.astype(np.int32)
        hi = np.minimum(lo + 1, len(audio) - 1)
        frac = (indices - lo).astype(np.float32)
        return (audio[lo] * (1 - frac) + audio[hi] * frac).astype(np.float32)
    else:
        ratio = target_sr / src_sr
        new_len = int(len(audio) * ratio)
        resampled = []
        for i in range(new_len):
            src_idx = i / ratio
            lo = int(src_idx)
            hi = min(lo + 1, len(audio) - 1)
            frac = src_idx - lo
            resampled.append(audio[lo] * (1 - frac) + audio[hi] * frac)
        return resampled


def db_to_linear(db):
    return 10 ** (db / 20.0)


def trim_silence_asymmetric(audio, sr, padding_ms=TRIM_PADDING_MS):
    if HAS_NUMPY:
        if len(audio) == 0:
            return np.zeros(0, dtype=np.float32)
        head_thresh = db_to_linear(TRIM_HEAD_DB)
        tail_thresh = db_to_linear(TRIM_TAIL_DB)
        abs_audio = np.abs(audio)
        head_idx = int(np.argmax(abs_audio > head_thresh))
        if abs_audio[head_idx] <= head_thresh:
            return np.zeros(0, dtype=np.float32)
        rev_abs = abs_audio[::-1]
        tail_idx_from_end = int(np.argmax(rev_abs > tail_thresh))
        tail_idx = len(audio) - tail_idx_from_end
        if tail_idx <= head_idx:
            return audio[head_idx:head_idx + 1]
        pad = int(sr * padding_ms / 1000)
        head = max(0, head_idx - pad)
        tail = min(len(audio), tail_idx + pad)
        return audio[head:tail].copy()
    else:
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


def peak_normalize(audio, target_db=NORMALIZE_DBFS, noise_floor_db=NOISE_FLOOR_DB):
    if HAS_NUMPY:
        if len(audio) == 0:
            return audio
        peak = float(np.max(np.abs(audio)))
        if peak < db_to_linear(noise_floor_db):
            return audio
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


def apply_fade_out(audio, fade_start, fade_end):
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


def apply_fade_in(audio, fade_start, fade_end):
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


def mix_into_buffer(all_audio, audio, position, fade_out_end=None, fade_in_start=None, fade_len=0):
    if len(audio) == 0:
        return all_audio
    end = position + len(audio)
    if fade_out_end is not None and end > fade_out_end:
        audio_len = len(audio)
        fade_start_in_audio = fade_out_end - position
        if fade_start_in_audio < audio_len:
            audio = apply_fade_out(
                audio.copy() if HAS_NUMPY else list(audio),
                fade_start_in_audio, audio_len,
            )
            end = position + len(audio)
    if fade_in_start is not None and fade_len > 0:
        audio = apply_fade_in(
            audio.copy() if HAS_NUMPY else list(audio),
            0, min(fade_len, len(audio)),
        )
    if end > len(all_audio):
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


def encode_wav(audio, sample_rate=OUTPUT_SAMPLE_RATE, channels=OUTPUT_CHANNELS, output_path=None):
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
                if channels == 2 and int_audio.ndim == 1:
                    int_audio = np.column_stack([int_audio, int_audio]).flatten()
                wf.writeframes(int_audio.tobytes())
            else:
                if channels == 2:
                    int_audio = b''.join(
                        struct.pack('<hh', v, v)
                        for v in struct.unpack(f'<{len(int_audio)//2}h', int_audio)
                    )
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
# Piper TTS generate (Python API, CoreML EP) — v0.2
# ============================================================

def format_length_scale(need, cap):
    """need (natural_dur/cue_dur) → piper length_scale.
    length_scale: <1.0 faster, >1.0 slower. need>1.0 (too long) → speedup → ls<1.
    """
    if need <= 1.0:
        return 1.0
    speedup = min(need, cap)
    return max(0.1, 1.0 / speedup)


def generate_cue_audio(text, voice, config, length_scale, target_sr=OUTPUT_SAMPLE_RATE):
    """Generate 1 cue via PiperVoice.synthesize (in-process, CoreML EP).
    Return float32 numpy array at target_sr, mono.

    voice.synthesize yields AudioChunk per sentence. Concatenate audio_float_array
    from each chunk, resample from model native sr → target_sr.
    """
    syn_config = SynthesisConfig(
        length_scale=length_scale,
        noise_scale=0.667,
        noise_w_scale=0.8,
        normalize_audio=True,
    )

    chunks_audio = []
    native_sr = None
    try:
        for chunk in voice.synthesize(text, syn_config=syn_config):
            if native_sr is None:
                native_sr = chunk.sample_rate
            if chunk.audio_float_array is not None and len(chunk.audio_float_array) > 0:
                chunks_audio.append(chunk.audio_float_array.astype(np.float32))
    except Exception as e:
        raise RuntimeError(f'Piper synthesize gagal: {e}')

    if not chunks_audio:
        return np.zeros(0, dtype=np.float32)

    if HAS_NUMPY:
        audio = np.concatenate(chunks_audio)
    else:
        audio = []
        for c in chunks_audio:
            audio.extend(c)

    if native_sr and native_sr != target_sr:
        audio = resample_audio(audio, native_sr, target_sr)
    return audio


# ============================================================
# Smart Fit (port edge-tts-tui, cache .npy array bukan WAV)
# ============================================================

def smart_fit_cue(text, cue_dur, voice, config, cap, cache_dir, cache_key, prefix, cue_idx,
                  baseline_ls=1.0):
    """Smart Fit 1 cue:
    1. Cache check: natural .npy (baseline_ls) ada?
    2. Generate natural (baseline_ls) kalau belum → trim → compute need
    3. need <= 1.0 → peak normalize natural
    4. need > 1.0 → generate speedup (ls = baseline_ls/speedup) → trim → peak normalize
    """
    natural_npy = os.path.join(cache_dir, f'{prefix}-cue-{cue_idx:04d}-{cache_key}.npy')

    # Pass 1: natural (baseline_ls)
    if not (os.path.isfile(natural_npy) and os.path.getsize(natural_npy) > 0):
        audio = generate_cue_audio(text, voice, config, baseline_ls)
        if len(audio) == 0:
            raise RuntimeError(f'Pass 1 gagal cue {cue_idx} (output kosong)')
        if HAS_NUMPY:
            np.save(natural_npy, audio)
        else:
            import pickle
            with open(natural_npy, 'wb') as f:
                pickle.dump(audio, f)

    if HAS_NUMPY:
        natural_audio_raw = np.load(natural_npy)
    else:
        import pickle
        with open(natural_npy, 'rb') as f:
            natural_audio_raw = pickle.load(f)

    natural_audio = trim_silence_asymmetric(natural_audio_raw, OUTPUT_SAMPLE_RATE)
    natural_dur = len(natural_audio) / OUTPUT_SAMPLE_RATE
    need = natural_dur / max(0.001, cue_dur)

    if SMART_FIT_DEBUG:
        fit_status = 'FIT' if need <= 1.0 else f'OVERFLOW need={need:.2f}'
        print(f'  [cue {cue_idx}] dur={cue_dur:.2f}s nat={natural_dur:.2f}s {fit_status}')

    if need <= 1.0:
        return peak_normalize(natural_audio)

    # Pass 2: speedup
    speedup = min(need, cap)
    total_ls = max(0.1, baseline_ls / speedup)
    if SMART_FIT_DEBUG:
        print(f'  [cue {cue_idx}] Pass 2: need={need:.2f} cap={cap} speedup={speedup:.2f} ls={total_ls:.3f}')
    smart_key = cache_key + f'_ls{total_ls:.4f}'
    smart_npy = os.path.join(cache_dir, f'{prefix}-cue-{cue_idx:04d}-{smart_key}.npy')

    if not (os.path.isfile(smart_npy) and os.path.getsize(smart_npy) > 0):
        try:
            smart_audio_raw = generate_cue_audio(text, voice, config, total_ls)
            if len(smart_audio_raw) == 0:
                print(f'  ⚠ Pass 2 gagal cue {cue_idx} (ls={total_ls}, output kosong), pakai natural')
                return peak_normalize(natural_audio)
            if HAS_NUMPY:
                np.save(smart_npy, smart_audio_raw)
            else:
                import pickle
                with open(smart_npy, 'wb') as f:
                    pickle.dump(smart_audio_raw, f)
        except Exception as e:
            print(f'  ⚠ Pass 2 gagal cue {cue_idx} (ls={total_ls}): {e}, pakai natural')
            return peak_normalize(natural_audio)

    if HAS_NUMPY:
        smart_audio_raw = np.load(smart_npy)
    else:
        import pickle
        with open(smart_npy, 'rb') as f:
            smart_audio_raw = pickle.load(f)
    smart_audio = trim_silence_asymmetric(smart_audio_raw, OUTPUT_SAMPLE_RATE)
    return peak_normalize(smart_audio)


# ============================================================
# Cache key + lock (port edge-tts-tui)
# ============================================================

def compute_cache_key(text, voice_id, length_scale=1.0):
    h = hashlib.sha256()
    h.update(text.encode('utf-8'))
    h.update(voice_id.encode('utf-8'))
    h.update(f'{length_scale:.4f}'.encode('utf-8'))
    return h.hexdigest()[:16]


def _pid_alive(pid):
    try:
        os.kill(pid, 0)
        return True
    except (OSError, ProcessLookupError):
        return False


def lock_path_for(output_dir, prefix):
    return os.path.join(output_dir, f'.{prefix}.piper.lock')


def acquire_lock(output_dir, prefix):
    lock_path = lock_path_for(output_dir, prefix)
    if os.path.isfile(lock_path):
        try:
            with open(lock_path, 'r') as f:
                pid = int(f.read().strip())
            if _pid_alive(pid):
                return (False, f'Lock aktif (PID {pid}). Instance lain jalan untuk prefix "{prefix}".')
        except (ValueError, IOError):
            pass
    try:
        with open(lock_path, 'w') as f:
            f.write(str(os.getpid()))
        return (True, lock_path)
    except IOError as e:
        return (False, f'Tidak bisa tulis lock: {e}')


def release_lock(output_dir, prefix):
    lock_path = lock_path_for(output_dir, prefix)
    try:
        if os.path.isfile(lock_path):
            os.unlink(lock_path)
    except OSError:
        pass


def suggest_unique_prefix(output_dir, prefix, max_attempts=99):
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
    gpu_label, has_coreml, _ = get_gpu_status()
    gpu_line = f'GPU: {gpu_label}'
    print('╔' + '═' * 64 + '╗')
    print('║  🗣️  Piper TTS TUI v0.2 — TTS LOKAL OFFLINE (VITS neural)   ║')
    print('║' + ' ' * 64 + '║')
    print(f'║  Backend : Piper TTS (ONNX) + {gpu_line:<37}║')
    print('║  Pattern : whisper-tui (local model) + edge-tts algoritma   ║')
    print('╚' + '═' * 64 + '╝')
    if not has_coreml and sys.platform == 'darwin':
        print()
        print('⚠ CoreMLExecutionProvider TIDAK terdeteksi (CPU mode).')
        print('  Di Mac M1, reinstall onnxruntime untuk aktifkan Metal GPU:')
        print('  pip3 install onnxruntime --force-reinstall')
        print('  Verify: python3 -c "import onnxruntime;print(onnxruntime.get_available_providers())"')
        print('  Harus ada "CoreMLExecutionProvider".')
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

    # Cari voice model
    voices = find_voice_models()
    if not voices:
        print()
        print('═' * 64)
        print('❌ Tidak ada model Piper ditemukan!')
        print('═' * 64)
        print()
        print('   Download voice Indonesia (id_ID-news_tts-medium, satu-satunya')
        print('   yang tersedia di repo HF resmi Nov 2026) ke ~/Dubbing/piper-voices/:')
        print()
        print('   pip3 install huggingface_hub')
        print('   mkdir -p ~/Dubbing/piper-voices && cd ~/Dubbing/piper-voices')
        print('   python3 -c "from huggingface_hub import hf_hub_download as d; import shutil,os; \\')
        print('     [shutil.copy(d(repo_id=\\\"rhasspy/piper-voices\\\", filename=p), os.path.basename(p)) \\')
        print('      for p in [\\\"id/id_ID/news_tts/medium/id_ID-news_tts-medium.onnx\\", \\')
        print('                \\\"id/id_ID/news_tts/medium/id_ID-news_tts-medium.onnx.json\\\"]]"')
        print()
        print('═' * 64)
        sys.exit(1)

    # Step 1: SRT
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

    # Step 2: output dir
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

    # Step 3: voice
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

    # Step 4: rate baseline
    print('▶ Step 4/7: Rate baseline (length-scale)')
    rate_choice = questionary.select(
        'Rate (1.0 = natural, >1.0 pelan/panjang, <1.0 cepat):',
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

    # Step 5: Smart Fit cap — SELECT match edge-tts-tui (4 opsi, default 1.5x)
    print('▶ Step 5/7: Smart Fit cap')
    cap_choice = questionary.select(
        'Smart Fit cap (max audio rate):',
        choices=[
            '1.5x (clean, recommended — match edge-tts user config)',
            '2.0x (voicertool cap, cepat seperti robot)',
            '1.25x (paling natural, lebih sering overflow)',
            'OFF (no smart fit, natural only)',
        ],
        default='1.5x (clean, recommended — match edge-tts user config)',
    ).ask()
    if 'OFF' in cap_choice:
        smart_fit = False
        cap = 1.0
    else:
        smart_fit = True
        cap = float(cap_choice.split('x')[0])
    print(f'  ✓ cap={cap}, smart_fit={smart_fit}')
    print()

    # Step 6: prefix
    print('▶ Step 6/7: Prefix output')
    default_prefix = os.path.splitext(os.path.basename(srt_path))[0]
    prefix = questionary.text('Prefix (output: {prefix}-audio-id-dub.wav):', default=default_prefix).ask()
    if not prefix:
        prefix = default_prefix
    prefix = suggest_unique_prefix(output_dir, prefix)
    print(f'  ✓ {prefix}')
    print()

    # Parse SRT
    with open(srt_path, 'r', encoding='utf-8-sig') as f:
        content = f.read()
    entries = parse_srt(content)
    if not entries:
        print('❌ SRT kosong/tidak terparse.')
        sys.exit(1)
    total_dur = entries[-1]['end']

    # Step 7: load model (show GPU status)
    print('▶ Step 7/7: Load model Piper')
    print(f'  Loading {os.path.basename(model_path)}...')
    t0 = time.time()
    voice, pconfig, ep_label, actual_eps = load_piper_voice(model_path, config_path, use_gpu=True)
    load_time = time.time() - t0
    print(f'  ✓ Model loaded ({load_time:.1f}s)')
    print(f'    ExecutionProvider: {ep_label} (actual: {", ".join(actual_eps)})')
    print()

    # Estimasi
    gpu_label, has_coreml, _ = get_gpu_status()
    est_per_cue = 0.15 if has_coreml else 0.4
    est_total_sec = len(entries) * est_per_cue
    if smart_fit:
        est_total_sec *= 1.3

    print('═' * 64)
    print('📋 Ringkasan:')
    print('═' * 64)
    print(f'  SRT      : {os.path.basename(srt_path)}')
    print(f'  Output   : {os.path.join(output_dir, prefix + "-audio-id-dub.wav")}')
    print(f'  Voice    : {voice_id}')
    print(f'  EP       : {ep_label}')
    print(f'  L-scale  : {baseline_ls} (baseline)')
    print(f'  Smart Fit: {"ON" if smart_fit else "OFF"}, cap={cap}')
    print(f'  Cues     : {len(entries)}')
    print(f'  Durasi   : {format_duration(total_dur)}')
    print(f'  Estimasi : {format_duration(est_total_sec)} ({gpu_label})')
    print('═' * 64)
    print()

    if not questionary.confirm('Lanjut generate?', default=True).ask():
        print('Batal.')
        sys.exit(0)

    ok, lock_info = acquire_lock(output_dir, prefix)
    if not ok:
        print(f'❌ {lock_info}')
        sys.exit(1)

    try:
        print()
        print('═' * 64)
        print(f'🚀 Mulai generate TTS (Piper {ep_label}) + mix inline...')
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

        # Track actual audio end (bukan SRT cue end) untuk crossfade simetris.
        # edge-tts-tui cek prev_entry['end'] (SRT time) — OK untuk Azure (audio
        # pacing pas, jarang overflow). Tapi piper VITS sering lebih panjang dari
        # cue → overflow past SRT cue end. Kalau fade_in cek SRT time (bukan
        # actual audio), tidak trigger → cue B main full volume di atas overflow
        # cue A → SUARA NUMPUK. Fix: track prev_audio_end_samples = position +
        # len(final_audio), pakai untuk fade_in condition + fade_len.
        prev_audio_end_samples = 0

        for i, entry in enumerate(entries):
            cue_idx = i + 1
            text = normalize_tts_text(' '.join(entry['textLines']))
            cue_dur = entry['end'] - entry['start']
            position = int(entry['start'] * OUTPUT_SAMPLE_RATE)

            # Fade in head: crossfade dengan prev ACTUAL audio (bukan SRT time).
            # Kalau prev audio overflow ke region cue ini → fade in head agar
            # transisi halus (A fade out + B fade in = crossfade simetris).
            fade_in_start = None
            fade_len = 0
            if i > 0 and position < prev_audio_end_samples:
                overlap = prev_audio_end_samples - position
                fade_in_start = position
                fade_len = min(overlap, crossfade_samples)

            next_entry = entries[i + 1] if i + 1 < len(entries) else None
            # fade_out_end di-set SETELAH generate (conditional on actual overflow),
            # mirror edge-tts-tui pattern (line 1081-1083).

            if not text:
                # Empty cue — skip, tapi update prev_audio_end (tidak ada audio baru)
                prev_audio_end_samples = max(prev_audio_end_samples, position)
                continue

            cache_key = compute_cache_key(text, voice_id, baseline_ls)

            try:
                if smart_fit:
                    final_audio = smart_fit_cue(
                        text, cue_dur, voice, pconfig, cap,
                        cache_dir, cache_key, prefix, cue_idx, baseline_ls=baseline_ls,
                    )
                else:
                    natural_npy = os.path.join(cache_dir, f'{prefix}-cue-{cue_idx:04d}-{cache_key}.npy')
                    if not (os.path.isfile(natural_npy) and os.path.getsize(natural_npy) > 0):
                        audio = generate_cue_audio(text, voice, pconfig, baseline_ls)
                        if len(audio) == 0:
                            fail_count += 1
                            continue
                        if HAS_NUMPY:
                            np.save(natural_npy, audio)
                    if HAS_NUMPY:
                        raw = np.load(natural_npy)
                    else:
                        import pickle
                        with open(natural_npy, 'rb') as f:
                            raw = pickle.load(f)
                    natural_audio = trim_silence_asymmetric(raw, OUTPUT_SAMPLE_RATE)
                    final_audio = peak_normalize(natural_audio)
            except Exception as e:
                print(f'\n  ⚠ Cue {cue_idx} gagal: {e}')
                fail_count += 1
                continue

            # Track actual audio end SEBELUM fade_out (untuk crossfade cue berikutnya)
            this_audio_end = position + len(final_audio)

            # Fade out tail: kalau audio extends past next cue start → fade out
            # dari next_start ke audio_end. Conditional on ACTUAL overflow.
            # TRUNCATION: cap overflow ke crossfade window (next_start +
            # crossfade_samples) supaya crossfade simetris 150ms, bukan overlap
            # panjang yang bikin numpuk. Tanpa truncate, fade_out cover full
            # overflow (bisa 1-2s) tapi fade_in cuma 150ms → region 150ms-end
            # still numpuk (prev fading + next full volume).
            # Dengan truncate: prev faded 150ms + next faded 150ms = clean crossfade.
            # Tradeoff: kata di tail overflow terpotong. Tapi smart_fit cap 2.0
            # sudah minimize overflow (need>2.0 jarang). Untuk kasus extreme,
            # user naikkan cap ke 2.5-3.0.
            fade_out_end = None
            if next_entry:
                next_start_samples = int(next_entry['start'] * OUTPUT_SAMPLE_RATE)
                if this_audio_end > next_start_samples:
                    fade_out_end = next_start_samples
                    # Truncate audio ke next_start + crossfade_samples
                    max_end = next_start_samples + crossfade_samples
                    if this_audio_end > max_end:
                        cut_idx = max_end - position
                        if 0 < cut_idx < len(final_audio):
                            final_audio = final_audio[:cut_idx]
                            this_audio_end = position + len(final_audio)
                            if SMART_FIT_DEBUG:
                                print(f'  [cue {cue_idx}] TRUNCATE overflow to {crossfade_samples/OUTPUT_SAMPLE_RATE:.3f}s window')

            mix_into_buffer(all_audio, final_audio, position,
                            fade_out_end=fade_out_end, fade_in_start=fade_in_start, fade_len=fade_len)

            # Update prev_audio_end untuk cue berikutnya (actual audio end,
            # bukan SRT cue end — supaya fade_in trigger kalau ada overflow)
            prev_audio_end_samples = this_audio_end
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
            print(f'   EP     : {ep_label}')
            print(f'   Cues   : {success_count} ok / {fail_count} fail / {len(entries)} total')
            print(f'   Waktu  : {format_duration(elapsed)} (model load {load_time:.1f}s + generate)')
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


# ============================================================
# Narration mode (mirror edge-tts-tui main_narration, 48kHz stereo)
# ============================================================

def main_narration():
    print('═' * 64)
    print('🎙️  Narration Mode — naskah plain text → 1 WAV (48kHz stereo)')
    print('═' * 64)
    print()

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

    # Step 5: filename
    print('▶ Step 5/6: Output filename')
    stem = os.path.splitext(os.path.basename(naskah_path))[0]
    default_name = f'{stem}-narasi.wav'
    out_name = questionary.text('Output filename:', default=default_name).ask()
    if not out_name:
        out_name = default_name
    output_path = os.path.join(output_dir, out_name)
    print(f'  ✓ {output_path}')
    print()

    # Step 6: load model
    print('▶ Step 6/6: Load model Piper')
    print(f'  Loading {os.path.basename(model_path)}...')
    t0 = time.time()
    voice, pconfig, ep_label, actual_eps = load_piper_voice(model_path, config_path, use_gpu=True)
    load_time = time.time() - t0
    print(f'  ✓ Model loaded ({load_time:.1f}s), EP: {ep_label}')
    print()

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
    print(f'  EP       : {ep_label}')
    print(f'  L-scale  : {length_scale}')
    print(f'  Output   : {output_path} (48kHz stereo)')
    print('═' * 64)
    print()

    if not questionary.confirm('Lanjut generate?', default=True).ask():
        print('Batal.')
        sys.exit(0)

    print(f'🚀 Mulai generate narasi (Piper {ep_label})...')
    print()
    start_time = time.time()

    all_chunks = []
    for i, sent in enumerate(sentences):
        try:
            audio = generate_cue_audio(sent, voice, pconfig, length_scale, target_sr=NARR_SAMPLE_RATE)
        except Exception as e:
            print(f'\n  ⚠ Kalimat {i+1} gagal: {e}')
            continue
        if len(audio) == 0:
            continue
        audio = trim_silence_asymmetric(audio, NARR_SAMPLE_RATE)
        audio = peak_normalize(audio)
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
        print(f'   EP     : {ep_label}')
        print(f'   Waktu  : {format_duration(elapsed)} (model load {load_time:.1f}s + generate)')
        print()
        print('🎬 Langkah berikutnya:')
        print(f'   Feed ke review-mix-tui / konten-tui / talkinghead-tui / manim-shorts-tui')
        print('═' * 64)


# ============================================================
# Entry
# ============================================================

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print('\n\n⏹ Dibatalkan user.')
        sys.exit(130)
