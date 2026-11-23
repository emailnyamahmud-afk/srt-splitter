#!/usr/bin/env python3
"""supertonic-tts-tui.py v0.2 — TTS LOKAL via Supertone Supertonic 3 (TUI #20)

Subtitlekit.com pakai model ini (tts-supertonic) untuk Bahasa Indonesia.
Flow-matching latent TTS, ONNX, ~99M params, 10 voice builtin (M1-M5/F1-F5).
Deterministic (no drift) + cepat (RTF ~0.012-0.018 di M4 CPU = ~100x OmniVoice).

3 Mode (v0.2 — mode Standar tidak berubah, Pro tambahan):
- SRT Standar (6 step, existing): SRT → output → voice → smart fit → prefix → generate
  Output: HDD/tts/{prefix}-audio-id-dub.wav (24kHz mono 16-bit, mix-tui compat)
- SRT Pro (8 step, BARU v0.2): multi-voice auto-gender via inaSpeechSegmenter.
  Baca WAV original → deteksi gender per segment → map cue ke voice pria/wanita
  → tagged SRT preview → generate multi-voice (cue laki=M5, perempuan=F1 default).
  Output: HDD/tts/{prefix}-audio-id-dub.wav + {prefix}-tagged.srt (preview/edit)
- Narration mode (6 step): naskah → output → voice → speed → filename → generate
  Output: HDD/tts/{stem}-narasi.wav (48kHz stereo 16-bit, review-mix/konten compat)

Voice: 10 builtin (NO cloning):
  M1-M5 (Male), F1-F5 (Female) — fixed prototypes, always consistent.
  Pro mode: switch voice per cue FREE (get_voice_style cached, synthesize per-call).
Language: 31 ISO codes incl 'id' (Indonesian, WER 1.34). Default 'id'.

Backend: supertonic PyPI 1.3.x (pip install supertonic). Model ~400MB download
sekali ke ~/.cache/supertonic3/ (auto_download=True). 100% offline setelah itu.
Pro mode butuh tambahan: pip install inaSpeechSegmenter (TensorFlow ~700MB-1GB Mac).

Pipeline integrasi:
- SRT mode → feed mix-tui (sama dengan edge/piper/omnivoice SRT output)
- Narration mode → feed review-mix-tui / konten-tui / talkinghead / manim-shorts

Trade-off vs omnivoice-tts-tui:
  + ~100x faster (RTF 0.012 vs OmniVoice 7.9)
  + deterministic (fixed voices, no drift — fix OmniVoice berantakan)
  + ringan (99M params vs 3.27GB)
  + ID native (WER 1.34 kompetitif)
  - NO voice cloning (10 builtin voices, bukan ref WAV user)
  - 44100Hz native (resample ke 24kHz/48kHz)

Setup user (Mac ~/Dubbing/):
  pip3 install supertonic questionary numpy soundfile
  # First run: download ~400MB model (cached sekali)

Pakai:
  cd ~/Dubbing && source venv/bin/activate && python3 supertonic-tts-tui.py

Status: UNTESTED di Mac user. Sandbox: API verified (supertonic 1.3.1 install OK,
TTS.synthesize signature confirmed, 10 voices M1-M5/F1-F5, sample_rate dari config).
"""

import os
import sys
import time
import json
import wave
import struct
import hashlib
import argparse
import random
import io
from pathlib import Path

# ============================================================
# Config (port config.py user working dir)
# ============================================================
try:
    import config
    SSD_HOME = getattr(config, 'SSD_HOME', Path.home() / 'Dubbing')
    HDD_BASE = getattr(config, 'HDD_BASE', Path('/Volumes/HDD/Dubbing'))
    INPUT_DIR = getattr(config, 'INPUT_DIR', HDD_BASE / 'input')
    TTS_DIR = getattr(config, 'TTS_DIR', HDD_BASE / 'tts')
    ENV_FILE = getattr(config, 'ENV_FILE', HDD_BASE / '.env')
    def ensure_hdd():
        if hasattr(config, 'ensure_hdd'):
            return config.ensure_hdd()
        try:
            os.makedirs(TTS_DIR, exist_ok=True)
            return True
        except Exception:
            return False
except Exception:
    SSD_HOME = Path.home() / 'Dubbing'
    HDD_BASE = Path('/Volumes/HDD/Dubbing')
    INPUT_DIR = HDD_BASE / 'input'
    TTS_DIR = HDD_BASE / 'tts'
    ENV_FILE = HDD_BASE / '.env'
    def ensure_hdd():
        try:
            os.makedirs(TTS_DIR, exist_ok=True)
            return True
        except Exception:
            return False

# ============================================================
# Dependencies
# ============================================================
_MISSING_DEPS = []
try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False
    _MISSING_DEPS.append('numpy')

try:
    import questionary
    HAS_QUESTIONARY = True
except ImportError:
    HAS_QUESTIONARY = False
    _MISSING_DEPS.append('questionary')

try:
    from supertonic import TTS as SupertonicTTS
    HAS_SUPERTONIC = True
except ImportError:
    HAS_SUPERTONIC = False
    _MISSING_DEPS.append('supertonic')

try:
    import soundfile as sf
    HAS_SOUNDFILE = True
except ImportError:
    HAS_SOUNDFILE = False

if _MISSING_DEPS:
    print('❌ Missing dependencies:', ', '.join(_MISSING_DEPS))
    print('   Install: pip3 install', ' '.join(_MISSING_DEPS))
    sys.exit(1)

# ============================================================
# Constants
# ============================================================
VERSION = 'v0.1'

OUTPUT_SAMPLE_RATE = 24000   # SRT mode: mix-tui compat (resample dari supertonic native)
OUTPUT_CHANNELS = 1
OUTPUT_BITS = 16

NARR_SAMPLE_RATE = 48000     # Narration mode: stereo
NARR_CHANNELS = 2

CROSSFADE_MS = 150
TRIM_HEAD_DB = -30
TRIM_TAIL_DB = -30
TRIM_PADDING_MS = 30
NORMALIZE_DBFS = -2.0
NOISE_FLOOR_DB = -50.0

SMART_FIT_CAP_DEFAULT = 1.5
SMART_FIT_DEBUG = os.environ.get('SUPERTONIC_SMART_FIT_DEBUG') == '1'

# Supertonic params
DEFAULT_TOTAL_STEPS = int(os.environ.get('SUPERTONIC_STEPS', '8'))  # 5-12, default 8
DEFAULT_SPEED = 1.0  # natural (smart fit handles speedup)
SUPERTONIC_NATIVE_SR = 44100  # fallback; actual dari tts.sample_rate runtime

# 10 builtin voices Supertonic-3
VOICE_OPTIONS = [
    ('M1', 'Male 1 (default — pria netral)'),
    ('M2', 'Male 2 (pria)'),
    ('M3', 'Male 3 (pria)'),
    ('M4', 'Male 4 (pria)'),
    ('M5', 'Male 5 (pria)'),
    ('F1', 'Female 1 (perempuan netral)'),
    ('F2', 'Female 2 (perempuan)'),
    ('F3', 'Female 3 (perempuan)'),
    ('F4', 'Female 4 (perempuan)'),
    ('F5', 'Female 5 (perempuan)'),
]

# 31 languages Supertonic (id = Indonesian, WER 1.34)
LANGUAGE_OPTIONS = [
    ('id', 'Indonesian (default — WER 1.34)'),
    ('en', 'English'),
    ('ko', 'Korean'),
    ('ja', 'Japanese'),
    ('vi', 'Vietnamese'),
    ('es', 'Spanish'),
    ('fr', 'French'),
    ('de', 'German'),
    ('it', 'Italian'),
    ('pt', 'Portuguese'),
    ('ru', 'Russian'),
    ('ar', 'Arabic'),
    ('hi', 'Hindi'),
    ('zh', 'Chinese (Mandarin — use MOSS for cn gallery)'),
    ('na', 'auto (language-agnostic, multi-bahasa)'),
    ('[ketik kode ISO lain]', 'manual (bg/cs/da/el/et/fi/hr/hu/lt/lv/nl/pl/ro/sk/sl/sv/tr/uk)'),
]


# ============================================================
# SRT parsing (port edge-tts-tui)
# ============================================================

def parse_srt(content):
    """Parse SRT → list of {start, end, textLines}.

    Standard SRT block:
        1                           ← cue number (SKIP)
        00:00:01,000 --> 00:00:03,000  ← timestamp
        Halo dunia                  ← text (KEEP, lines after timestamp only)

    Bug lama (v0.1): loop append SEMUA non-timestamp line ke text_lines,
    termasuk cue number → Supertonic baca "satu", "dua", ... di awal tiap cue.
    Fix: text_lines = lines[ts_idx+1:] (hanya lines SETELAH timestamp).
    """
    entries = []
    blocks = content.strip().split('\n\n')
    for block in blocks:
        lines = [l for l in block.split('\n') if l.strip()]
        if len(lines) < 2:
            continue
        # Find timestamp line index
        ts_idx = -1
        for i, line in enumerate(lines):
            if ' --> ' in line:
                ts_idx = i
                break
        if ts_idx < 0:
            continue  # no timestamp, skip block
        ts_line = lines[ts_idx]
        text_lines = lines[ts_idx + 1:]  # ONLY lines after timestamp (skip cue number)
        if not text_lines:
            continue
        try:
            start_str, end_str = ts_line.split(' --> ')
            start = _parse_time(start_str.strip())
            end = _parse_time(end_str.strip())
        except Exception:
            continue
        if start is None or end is None:
            continue
        entries.append({'start': start, 'end': end, 'textLines': text_lines})
    return entries


def _parse_time(ts):
    try:
        ts = ts.replace(',', '.')
        parts = ts.split(':')
        if len(parts) == 3:
            h, m, s = parts
            return int(h) * 3600 + int(m) * 60 + float(s)
        elif len(parts) == 2:
            m, s = parts
            return int(m) * 60 + float(s)
        else:
            return float(ts)
    except Exception:
        return None


def format_timestamp(seconds):
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = seconds % 60
    return f'{h:02d}:{m:02d}:{s:06.3f}'


def format_duration(seconds):
    if seconds < 60:
        return f'{seconds:.1f}s'
    m = int(seconds // 60)
    s = int(seconds % 60)
    if m < 60:
        return f'{m}m{s}s'
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    return f'{h}j{m}m{s}s'


def normalize_tts_text(text):
    text = text.strip()
    # Strip speaker labels like (M) / [F] / <name>
    import re
    text = re.sub(r'^[\(\[][^\)\]]*[\)\]]\s*', '', text)
    text = re.sub(r'^[A-Z]+:\s*', '', text)
    # Collapse whitespace
    text = re.sub(r'\s+', ' ', text)
    return text


# ============================================================
# Audio processing (port omnivoice-tts-tui)
# ============================================================

def resample_audio(audio, src_sr, target_sr):
    """Resample float32 array src_sr → target_sr (linear interpolation)."""
    if src_sr == target_sr or len(audio) == 0:
        return audio
    if not HAS_NUMPY:
        return audio
    n_src = len(audio)
    n_tgt = int(n_src * target_sr / src_sr)
    if n_tgt <= 0:
        return np.zeros(0, dtype=np.float32)
    idx = np.linspace(0, n_src - 1, n_tgt)
    i0 = idx.astype(np.int32)
    i1 = np.minimum(i0 + 1, n_src - 1)
    frac = (idx - i0).astype(np.float32)
    out = audio[i0] * (1 - frac) + audio[i1] * frac
    return out.astype(np.float32)


def db_to_linear(db):
    return 10 ** (db / 20.0)


def trim_silence_asymmetric(audio, sr, padding_ms=TRIM_PADDING_MS):
    """Trim leading/trailing silence below TRIM_HEAD_DB/TRIM_TAIL_DB."""
    if len(audio) == 0 or not HAS_NUMPY:
        return audio
    head_thr = db_to_linear(TRIM_HEAD_DB)
    tail_thr = db_to_linear(TRIM_TAIL_DB)
    abs_a = np.abs(audio)
    n = len(abs_a)
    # Head
    head_idx = 0
    for i in range(n):
        if abs_a[i] > head_thr:
            head_idx = i
            break
    # Tail
    tail_idx = n
    for i in range(n - 1, -1, -1):
        if abs_a[i] > tail_thr:
            tail_idx = i + 1
            break
    pad = int(sr * padding_ms / 1000)
    head_idx = max(0, head_idx - pad)
    tail_idx = min(n, tail_idx + pad)
    if tail_idx <= head_idx:
        return audio
    return audio[head_idx:tail_idx]


def peak_normalize(audio, target_db=NORMALIZE_DBFS, noise_floor_db=NOISE_FLOOR_DB):
    """Peak normalize ke target dBFS, noise gate di noise_floor."""
    if len(audio) == 0 or not HAS_NUMPY:
        return audio
    peak = np.max(np.abs(audio))
    if peak < db_to_linear(noise_floor_db):
        return audio  # below noise floor, leave
    target = db_to_linear(target_db)
    gain = target / peak if peak > 0 else 1.0
    return (audio * gain).astype(np.float32)


def apply_fade_out(audio, fade_start, fade_end):
    if fade_end <= fade_start or len(audio) == 0:
        return audio
    fade_start = max(0, min(fade_start, len(audio)))
    fade_end = max(0, min(fade_end, len(audio)))
    if fade_end <= fade_start:
        return audio
    n = fade_end - fade_start
    fade = np.linspace(1.0, 0.0, n, dtype=np.float32)
    out = audio.copy()
    out[fade_start:fade_end] *= fade
    return out


def apply_fade_in(audio, fade_start, fade_end):
    if fade_end <= fade_start or len(audio) == 0:
        return audio
    fade_start = max(0, min(fade_start, len(audio)))
    fade_end = max(0, min(fade_end, len(audio)))
    if fade_end <= fade_start:
        return audio
    n = fade_end - fade_start
    fade = np.linspace(0.0, 1.0, n, dtype=np.float32)
    out = audio.copy()
    out[fade_start:fade_end] *= fade
    return out


def mix_into_buffer(all_audio, audio, position, fade_out_end=None, fade_in_start=None, fade_len=0):
    """Mix audio ke all_audio di position. Crossfade in/out optional.

    fade_out_end: sample index di all_audio dimana fade-out DIMULAI (overlap
      region mulai). Audio dari fade_out_end sampai end-nya di-fade 1.0→0.0
      (omnivoice pattern — overlap tail fades out while next cue head fades in).
    fade_in_start: positional param (info). fade_in apply ke HEAD audio [0, fade_len].
    fade_len: panjang crossfade window.
    """
    if len(audio) == 0:
        return
    end = position + len(audio)
    # Fade out: dari fade_out_end (overlap start) sampai end audio (1.0 → 0.0)
    if fade_out_end is not None and end > fade_out_end:
        fade_start_in_audio = fade_out_end - position
        if 0 <= fade_start_in_audio < len(audio):
            audio = apply_fade_out(audio, fade_start_in_audio, len(audio))
            end = position + len(audio)
    # Fade in: head audio [0, fade_len] (0.0 → 1.0) — crossfade dengan prev cue tail
    if fade_len > 0:
        fi_end = min(fade_len, len(audio))
        if fi_end > 0:
            audio = apply_fade_in(audio, 0, fi_end)
    if end > len(all_audio):
        audio = audio[:len(all_audio) - position]
        end = position + len(audio)
    if end <= position:
        return
    all_audio[position:end] += audio


def encode_wav(audio, sample_rate, channels, output_path):
    """Encode float32 array → WAV (16-bit PCM)."""
    if HAS_NUMPY:
        audio = np.clip(audio, -1.0, 1.0)
        if channels == 2 and audio.ndim == 1:
            audio = np.stack([audio, audio], axis=1)
        pcm = (audio * 32767).astype(np.int16)
    else:
        pcm = audio
    buf = io.BytesIO()
    with wave.open(buf, 'wb') as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(pcm.tobytes() if HAS_NUMPY else bytes(pcm))
    with open(output_path, 'wb') as f:
        f.write(buf.getvalue())


# ============================================================
# Supertonic generate
# ============================================================

_tts_instance = None
_voice_styles = {}  # cache Style objects per voice_name


def load_supertonic_model():
    """Load Supertonic TTS model (auto_download ~400MB first run)."""
    global _tts_instance
    start = time.time()
    print(f'  Loading Supertonic 3 (auto_download jika perlu, cached ~/.cache/supertonic3/)...')
    _tts_instance = SupertonicTTS(auto_download=True)
    sr = getattr(_tts_instance, 'sample_rate', SUPERTONIC_NATIVE_SR)
    load_time = time.time() - start
    ep_label = f'ONNX CPU (native {sr}Hz)'
    return _tts_instance, load_time, ep_label, sr


def get_voice_style(voice_name):
    """Cache + return Style object untuk voice_name."""
    global _voice_styles
    if voice_name not in _voice_styles:
        _voice_styles[voice_name] = _tts_instance.get_voice_style(voice_name)
    return _voice_styles[voice_name]


def generate_cue_audio(text, voice_name, speed=1.0, lang='id', steps=DEFAULT_TOTAL_STEPS,
                       target_sr=OUTPUT_SAMPLE_RATE, native_sr=SUPERTONIC_NATIVE_SR):
    """Generate 1 cue via Supertonic. Return float32 numpy array at target_sr, mono."""
    style = get_voice_style(voice_name)
    wav, duration = _tts_instance.synthesize(
        text=text,
        voice_style=style,
        total_steps=steps,
        speed=speed,
        lang=lang,
        verbose=False,
    )
    # wav = np.ndarray (mono float32 at native_sr). duration = np.ndarray.
    if wav is None or len(wav) == 0:
        return np.zeros(0, dtype=np.float32)
    audio_arr = wav
    if isinstance(audio_arr, list):
        audio_arr = np.array(audio_arr, dtype=np.float32)
    # Squeeze dims → mono 1D
    if HAS_NUMPY and audio_arr.ndim > 1:
        audio_arr = audio_arr.squeeze()
        if audio_arr.ndim > 1:
            audio_arr = audio_arr[0] if isinstance(audio_arr[0], np.ndarray) else audio_arr
    audio_arr = audio_arr.astype(np.float32)
    # Resample native → target
    if native_sr != target_sr:
        audio_arr = resample_audio(audio_arr, native_sr, target_sr)
    return audio_arr


def format_speed(need, cap):
    """need (natural/cue) → Supertonic speed param (0.7-2.0)."""
    if need <= 1.0:
        return 1.0
    return min(need, cap, 2.0)


def compute_cache_key(text, voice_name, speed, lang, steps):
    """Hash text+voice+speed+lang+steps → cache key."""
    h = hashlib.md5()
    h.update(text.encode('utf-8'))
    h.update(f'|{voice_name}|{speed:.3f}|{lang}|{steps}'.encode('utf-8'))
    return h.hexdigest()[:16]


def smart_fit_cue(text, cue_dur, voice_name, cap, lang, steps, cache_dir,
                  cache_key, prefix, cue_idx, native_sr):
    """Smart fit: Pass 1 natural, kalau overflow > crossfade → Pass 2 speedup.

    Mirror omnivoice-tts-tui v0.7 threshold: regenerate HANYA kalau overflow
    melebihi crossfade window (150ms). need 1.0-1.15 (overflow kecil) → pakai
    natural, skip Pass 2. Cuts ~40-60% API calls.
    """
    natural_npy = os.path.join(cache_dir, f'{prefix}-cue-{cue_idx:04d}-{cache_key}.npy')
    if not (os.path.isfile(natural_npy) and os.path.getsize(natural_npy) > 0):
        audio = generate_cue_audio(text, voice_name, speed=1.0, lang=lang, steps=steps,
                                   target_sr=OUTPUT_SAMPLE_RATE, native_sr=native_sr)
        if len(audio) == 0:
            return np.zeros(0, dtype=np.float32)
        np.save(natural_npy, audio)
    natural_audio = np.load(natural_npy)
    natural_audio = trim_silence_asymmetric(natural_audio, OUTPUT_SAMPLE_RATE)
    natural_dur = len(natural_audio) / OUTPUT_SAMPLE_RATE
    need = natural_dur / max(0.001, cue_dur)

    # Threshold: regenerate hanya kalau overflow > crossfade window
    cue_samples = int(cue_dur * OUTPUT_SAMPLE_RATE)
    crossfade_samples = int(OUTPUT_SAMPLE_RATE * CROSSFADE_MS / 1000)
    overflow_samples = len(natural_audio) - cue_samples
    fits_in_crossfade = overflow_samples <= crossfade_samples

    if SMART_FIT_DEBUG:
        if overflow_samples <= 0:
            status = 'FIT'
        elif fits_in_crossfade:
            status = f'OVERFLOW+xfade need={need:.2f} (no regen)'
        else:
            status = f'OVERFLOW need={need:.2f} (regen)'
        print(f'  [cue {cue_idx}] dur={cue_dur:.2f}s nat={natural_dur:.2f}s {status}')

    if fits_in_crossfade:
        return peak_normalize(natural_audio)

    # Pass 2: speedup
    speed = format_speed(need, cap)
    if SMART_FIT_DEBUG:
        print(f'  [cue {cue_idx}] Pass 2: need={need:.2f} cap={cap} speed={speed:.2f}')
    smart_key = compute_cache_key(text, voice_name, speed, lang, steps)
    smart_npy = os.path.join(cache_dir, f'{prefix}-cue-{cue_idx:04d}-{smart_key}.npy')
    if not (os.path.isfile(smart_npy) and os.path.getsize(smart_npy) > 0):
        audio = generate_cue_audio(text, voice_name, speed=speed, lang=lang, steps=steps,
                                   target_sr=OUTPUT_SAMPLE_RATE, native_sr=native_sr)
        if len(audio) == 0:
            print(f'  ⚠ Pass 2 gagal cue {cue_idx} (speed={speed}), pakai natural')
            return peak_normalize(natural_audio)
        np.save(smart_npy, audio)
    smart_audio = np.load(smart_npy)
    smart_audio = trim_silence_asymmetric(smart_audio, OUTPUT_SAMPLE_RATE)
    return peak_normalize(smart_audio)


# ============================================================
# Lock (port piper-tts-tui)
# ============================================================

def _pid_alive(pid):
    try:
        os.kill(pid, 0)
        return True
    except (OSError, ProcessLookupError):
        return False


def lock_path_for(output_dir, prefix):
    return os.path.join(output_dir, f'.{prefix}.lock')


def acquire_lock(output_dir, prefix):
    lock_path = lock_path_for(output_dir, prefix)
    if os.path.isfile(lock_path):
        try:
            with open(lock_path, 'r') as f:
                pid = int(f.read().strip())
            if _pid_alive(pid):
                return False, f'Lock aktif (PID {pid}). Kalau yakin tidak ada proses lain: rm {lock_path}'
        except Exception:
            pass
    try:
        with open(lock_path, 'w') as f:
            f.write(str(os.getpid()))
        return True, lock_path
    except Exception as e:
        return False, f'Tidak bisa lock: {e}'


def release_lock(output_dir, prefix):
    try:
        os.unlink(lock_path_for(output_dir, prefix))
    except OSError:
        pass


def suggest_unique_prefix(output_dir, prefix, max_attempts=99):
    if not os.path.exists(os.path.join(output_dir, f'{prefix}-audio-id-dub.wav')):
        return prefix
    for i in range(2, max_attempts + 2):
        cand = f'{prefix}-{i}'
        if not os.path.exists(os.path.join(output_dir, f'{cand}-audio-id-dub.wav')):
            return cand
    return prefix


# ============================================================
# TUI helpers
# ============================================================

def clear_screen():
    os.system('cls' if os.name == 'nt' else 'clear')


def print_banner():
    print('╔' + '═' * 64 + '╗')
    print('║  🗣️  Supertonic TTS TUI v0.1 — subtitlekit model (Supertone 3) ║')
    print('║' + ' ' * 64 + '║')
    print('║  Backend : Supertonic 3 ONNX (~99M params, deterministic)      ║')
    print('║  Voices  : 10 builtin (M1-M5/F1-F5) — NO cloning, no drift     ║')
    print('║  Speed   : RTF ~0.012-0.018 M4 CPU (~100x OmniVoice)            ║')
    print('║  Pattern : edge-tts-tui v7.5 algoritma + supertonic engine     ║')
    print('╚' + '═' * 64 + '╝')
    print()


def find_srt_files(search_dir):
    if not os.path.isdir(search_dir):
        return []
    out = []
    for f in sorted(os.listdir(search_dir)):
        if f.lower().endswith(('.srt', '.final.srt')):
            out.append(f)
    return out


def prompt_language(default='id'):
    print('── Language ──')
    print('  Supertonic language= — kontrol phoneme + accent mapping.')
    print('  Default "id" untuk teks Indonesia (WER 1.34).')
    labels = [f'{code} — {desc}' for code, desc in LANGUAGE_OPTIONS]
    choice = questionary.select(
        'Language target teks:',
        choices=labels,
        default=next(l for l in labels if l.startswith(default + ' —')),
    ).ask()
    # extract code (first token before ' —')
    code = choice.split(' —')[0].strip()
    if code == '[ketik kode ISO lain]':
        code = questionary.text('Kode ISO (mis. nl, pl, sv):', default='nl').ask().strip()
    return code


# ============================================================
# Pro mode: gender detection + multi-voice (inaSpeechSegmenter)
# v0.2 — mode tambahan, main_srt (standar) tidak berubah
# ============================================================

def _srt_ts(sec):
    """SRT timestamp HH:MM:SS,mmm (comma, VLC standard)."""
    h = int(sec // 3600)
    m = int((sec % 3600) // 60)
    s = sec % 60
    return f'{h:02d}:{m:02d}:{int(s):02d},{int(round((s - int(s)) * 1000)):03d}'


def _detect_gender_segments(wav_path):
    """Run inaSpeechSegmenter on wav_path → list of (start, end, gender).
    gender = 'male' | 'female'. Returns [] on failure (caller exits with install hint).
    """
    try:
        from inaSpeechSegmenter import Segmenter
    except ImportError:
        print('  ❌ inaSpeechSegmenter tidak terinstall.')
        print('     Install: pip install inaSpeechSegmenter')
        print('     (butuh TensorFlow ~700MB-1GB di Mac M1; kalau bermasalah pakai mode Standar)')
        return []
    try:
        print(f'  Load inaSpeechSegmenter model (first run download ~200MB, cached)...')
        seg = Segmenter()
        print(f'  Analyze {os.path.basename(wav_path)} (bisa beberapa menit untuk file panjang)...')
        raw = seg(wav_path)  # list of (label, start, end)
    except Exception as e:
        print(f'  ❌ Gender detection error: {e}')
        return []
    gender_segs = [(float(s), float(e), lbl) for lbl, s, e in raw if lbl in ('male', 'female')]
    male_n = sum(1 for _, _, g in gender_segs if g == 'male')
    female_n = sum(1 for _, _, g in gender_segs if g == 'female')
    print(f'  ✓ {len(gender_segs)} gender segment ({male_n} male, {female_n} female)')
    return gender_segs


def _map_cues_to_voices(entries, gender_segs, male_voice, female_voice):
    """Map each SRT cue to male_voice/female_voice based on max overlap with gender segments.
    Cue tanpa overlap gender → default male_voice (user bisa edit tagged SRT).
    """
    cue_voices = []
    for entry in entries:
        cue_start, cue_end = entry['start'], entry['end']
        best_gender = None
        best_overlap = 0.0
        for gstart, gend, gender in gender_segs:
            ov = max(0.0, min(cue_end, gend) - max(cue_start, gstart))
            if ov > best_overlap:
                best_overlap = ov
                best_gender = gender
        if best_gender == 'female':
            cue_voices.append(female_voice)
        else:
            cue_voices.append(male_voice)  # male or no-overlap default
    return cue_voices


def _save_tagged_srt(entries, cue_voices, out_path):
    """Write tagged SRT (preview/edit-friendly). Tag [M5]/[F1] prepended ke tiap cue text.
    Human-readable preview — TUI internal pakai cue_voices list, bukan re-parse tag ini.
    """
    with open(out_path, 'w', encoding='utf-8') as f:
        for i, entry in enumerate(entries):
            tag = cue_voices[i]
            text = ' '.join(entry['textLines'])
            f.write(f'{i + 1}\n')
            f.write(f'{_srt_ts(entry["start"])} --> {_srt_ts(entry["end"])}\n')
            f.write(f'[{tag}] {text}\n\n')


def _run_generate(entries, cue_voices, output_dir, prefix, language, smart_fit, cap,
                  tts, ep_label, native_sr, load_time, total_dur, voice_display,
                  multi_voice=False):
    """Shared generate loop (dipakai main_srt_pro). cue_voices[i] = voice per cue.
    Acquire lock → per-cue TTS w/ smart_fit → mix inline → encode WAV → cleanup cache.
    Mirror main_srt inline loop (supertonic deterministic, no drift antar voice).
    """
    ok, lock_info = acquire_lock(output_dir, prefix)
    if not ok:
        print(f'❌ {lock_info}')
        sys.exit(1)
    try:
        print()
        print('═' * 64)
        tag = 'multi-voice auto-gender' if multi_voice else 'single voice'
        print(f'🚀 Mulai generate TTS (Supertonic 3 {ep_label}, {tag}) + mix inline...')
        print('═' * 64)
        print()

        cache_dir = os.path.join(output_dir, '.supertonic-cache')
        os.makedirs(cache_dir, exist_ok=True)

        total_samples = int(total_dur * OUTPUT_SAMPLE_RATE) + int(OUTPUT_SAMPLE_RATE * 2)
        all_audio = np.zeros(total_samples, dtype=np.float32)
        print(f'  Buffer: {total_samples} samples = {format_duration(total_samples/OUTPUT_SAMPLE_RATE)} = {total_samples*4/1024/1024:.0f} MB')
        print()

        success_count = 0
        fail_count = 0
        start_time = time.time()
        crossfade_samples = int(OUTPUT_SAMPLE_RATE * CROSSFADE_MS / 1000)
        prev_audio_end_samples = 0

        for i, entry in enumerate(entries):
            cue_idx = i + 1
            text = normalize_tts_text(' '.join(entry['textLines']))
            cue_dur = entry['end'] - entry['start']
            position = int(entry['start'] * OUTPUT_SAMPLE_RATE)
            next_entry = entries[i + 1] if i + 1 < len(entries) else None

            fade_in_start = None
            fade_len = 0
            if i > 0 and position < prev_audio_end_samples:
                overlap = prev_audio_end_samples - position
                fade_in_start = position
                fade_len = min(overlap, crossfade_samples)

            if not text:
                prev_audio_end_samples = max(prev_audio_end_samples, position)
                continue

            cache_key = compute_cache_key(text, cue_voices[i], 1.0, language, DEFAULT_TOTAL_STEPS)

            try:
                if smart_fit:
                    final_audio = smart_fit_cue(
                        text, cue_dur, cue_voices[i], cap, language, DEFAULT_TOTAL_STEPS,
                        cache_dir, cache_key, prefix, cue_idx, native_sr)
                else:
                    natural_npy = os.path.join(cache_dir, f'{prefix}-cue-{cue_idx:04d}-{cache_key}.npy')
                    if not (os.path.isfile(natural_npy) and os.path.getsize(natural_npy) > 0):
                        audio = generate_cue_audio(text, cue_voices[i], speed=1.0, lang=language,
                                                   steps=DEFAULT_TOTAL_STEPS, target_sr=OUTPUT_SAMPLE_RATE,
                                                   native_sr=native_sr)
                        if len(audio) == 0:
                            fail_count += 1
                            print(f'\n  ⚠ Cue {cue_idx} gagal (output kosong)')
                            continue
                        np.save(natural_npy, audio)
                    natural_audio = np.load(natural_npy)
                    natural_audio = trim_silence_asymmetric(natural_audio, OUTPUT_SAMPLE_RATE)
                    final_audio = peak_normalize(natural_audio)
            except Exception as e:
                print(f'\n  ⚠ Cue {cue_idx} gagal: {e}')
                fail_count += 1
                continue

            if len(final_audio) == 0:
                fail_count += 1
                continue

            this_audio_end = position + len(final_audio)

            fade_out_end = None
            if next_entry:
                next_start_samples = int(next_entry['start'] * OUTPUT_SAMPLE_RATE)
                if this_audio_end > next_start_samples:
                    fade_out_end = next_start_samples
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

            prev_audio_end_samples = this_audio_end
            success_count += 1

            if cue_idx % 5 == 0 or cue_idx == len(entries):
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

        final_end = int(total_dur * OUTPUT_SAMPLE_RATE) + int(OUTPUT_SAMPLE_RATE * 0.3)
        all_audio = all_audio[:final_end]

        output_path = os.path.join(output_dir, f'{prefix}-audio-id-dub.wav')
        print(f'  Encoding WAV {OUTPUT_SAMPLE_RATE}Hz mono → {output_path}...')
        encode_wav(all_audio, OUTPUT_SAMPLE_RATE, OUTPUT_CHANNELS, output_path)

        try:
            cache_files = [f for f in os.listdir(cache_dir) if f.startswith(prefix)]
            cache_size_mb = sum(os.path.getsize(os.path.join(cache_dir, f)) for f in cache_files) / 1024 / 1024
            if cache_files:
                if questionary.confirm(
                    f'Hapus cache ({len(cache_files)} NPY, {cache_size_mb:.1f} MB)? '
                    f'(No = simpan untuk resume kalau generate ulang SRT sama)',
                    default=False,
                ).ask():
                    for f in cache_files:
                        try:
                            os.unlink(os.path.join(cache_dir, f))
                        except OSError:
                            pass
                    try:
                        os.rmdir(cache_dir)
                    except OSError:
                        pass
                    print('  ✓ Cache dihapus')
                else:
                    print(f'  Cache disimpan: {cache_dir} ({cache_size_mb:.1f} MB)')
        except Exception:
            pass

        if os.path.isfile(output_path):
            size_mb = os.path.getsize(output_path) / 1024 / 1024
            print()
            print('═' * 64)
            print('✅ SELESAI!')
            print(f'   Output : {output_path}')
            print(f'   Size   : {size_mb:.1f} MB')
            print(f'   Format : {OUTPUT_SAMPLE_RATE}Hz mono 16-bit PCM (mix-tui compatible)')
            print(f'   Engine : Supertonic 3')
            print(f'   Voice  : {voice_display}')
            print(f'   Cues   : {success_count} ok / {fail_count} fail / {len(entries)} total')
            print(f'   Waktu  : {format_duration(elapsed)} (model load {load_time:.1f}s + generate)')
            print('═' * 64)
            print()
            print('🎬 Langkah berikutnya:')
            print(f'   1. Preview: open {output_path}')
            print(f'   2. Feed ke mix-tui (sama dengan edge-tts/piper/omnivoice SRT output)')
    finally:
        release_lock(output_dir, prefix)


def main_srt_pro():
    """Mode Pro: multi-voice auto-gender via inaSpeechSegmenter.
    Cue laki → voice pria (default M5), cue perempuan → voice wanita (default F1),
    auto-detect dari WAV original. Standar mode (main_srt) tidak berubah — ini mode tambahan.
    """
    print_banner()
    print('📋 Mode: SRT Pro (multi-voice auto-gender via inaSpeechSegmenter)')
    print('   Cue laki → voice pria, cue perempuan → voice wanita (auto-detect dari WAV original)')
    print('   Navigasi: ↑↓ arrow keys, Enter konfirmasi, Ctrl+C batal')
    print()

    # Step 1: SRT (Indonesia, dari pipeline)
    print('▶ Step 1/8: Pilih SRT (bahasa Indonesia)')
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
        srt_path = questionary.text(f'Tidak ada SRT di {default_srt_dir}. Ketik path lengkap:').ask()
    if not srt_path or not os.path.isfile(srt_path):
        print('❌ File SRT tidak ditemukan.')
        sys.exit(1)
    print(f'  ✓ {srt_path}')
    print()

    # Step 2: WAV original (untuk gender detection — audio source film)
    print('▶ Step 2/8: Pilih WAV original (audio source untuk gender detection)')
    default_wav_dir = default_srt_dir
    wav_files = sorted([f for f in os.listdir(default_wav_dir)
                        if f.lower().endswith(('.wav', '.mp3', '.m4a', '.aac', '.flac'))]) if os.path.isdir(default_wav_dir) else []
    if wav_files:
        wav_choice = questionary.select(
            f'File audio (ditemukan {len(wav_files)} di {default_wav_dir}):',
            choices=wav_files + ['[Ketik path manual]'],
            default=wav_files[0],
        ).ask()
        if wav_choice == '[Ketik path manual]':
            wav_path = questionary.text('Path audio:').ask()
        else:
            wav_path = os.path.join(default_wav_dir, wav_choice)
    else:
        wav_path = questionary.text(f'Tidak ada audio di {default_wav_dir}. Ketik path lengkap:').ask()
    if not wav_path or not os.path.isfile(wav_path):
        print('❌ File audio tidak ditemukan.')
        sys.exit(1)
    print(f'  ✓ {wav_path}')
    print()

    # Step 3: voice mapping (laki + perempuan)
    print('▶ Step 3/8: Pilih voice mapping')
    male_labels = [f'{c} — {d}' for c, d in VOICE_OPTIONS if c.startswith('M')]
    female_labels = [f'{c} — {d}' for c, d in VOICE_OPTIONS if c.startswith('F')]
    default_male = next((l for l in male_labels if l.startswith('M5')), male_labels[0])
    default_female = next((l for l in female_labels if l.startswith('F1')), female_labels[0])
    male_voice = questionary.select(
        'Voice laki-laki (M1-M5):', choices=male_labels, default=default_male,
    ).ask().split(' —')[0].strip()
    female_voice = questionary.select(
        'Voice perempuan (F1-F5):', choices=female_labels, default=default_female,
    ).ask().split(' —')[0].strip()
    print(f'  ✓ laki={male_voice}, perempuan={female_voice}')
    language = prompt_language(default='id')
    print(f'  ✓ language: {language}')
    print()

    # Step 4: Smart Fit cap
    print('▶ Step 4/8: Smart Fit cap')
    cap_choice = questionary.select(
        'Smart Fit cap (max speed):',
        choices=[
            '1.5x (clean, recommended)',
            '2.0x (cepat, sedikit robotik untuk cue padat)',
            '1.25x (paling natural, lebih sering overflow)',
            'OFF (no smart fit, natural only)',
        ],
        default='1.5x (clean, recommended)',
    ).ask()
    if 'OFF' in cap_choice:
        smart_fit = False
        cap = 1.0
    else:
        smart_fit = True
        cap = float(cap_choice.split('x')[0])
    print(f'  ✓ cap={cap}, smart_fit={smart_fit}')
    print()

    # Step 5: prefix
    print('▶ Step 5/8: Prefix output')
    default_prefix = os.path.splitext(os.path.basename(srt_path))[0]
    prefix = questionary.text('Prefix (output: {prefix}-audio-id-dub.wav + {prefix}-tagged.srt):', default=default_prefix).ask()
    if not prefix:
        prefix = default_prefix

    # Step 6: output dir
    print('▶ Step 6/8: Output directory')
    default_out = str(TTS_DIR)
    output_dir = questionary.text('Output directory:', default=default_out).ask()
    if not output_dir:
        output_dir = default_out
    os.makedirs(output_dir, exist_ok=True)
    prefix = suggest_unique_prefix(output_dir, prefix)
    print(f'  ✓ {prefix} → {output_dir}')
    print()

    # Step 7: gender detection + map cues
    print('▶ Step 7/8: Gender detection (inaSpeechSegmenter)')
    gender_segs = _detect_gender_segments(wav_path)
    if not gender_segs:
        sys.exit(1)

    with open(srt_path, 'r', encoding='utf-8-sig') as f:
        content = f.read()
    entries = parse_srt(content)
    if not entries:
        print('❌ SRT kosong/tidak terparse.')
        sys.exit(1)
    total_dur = entries[-1]['end']

    cue_voices = _map_cues_to_voices(entries, gender_segs, male_voice, female_voice)
    male_count = sum(1 for v in cue_voices if v == male_voice)
    female_count = sum(1 for v in cue_voices if v == female_voice)

    tagged_path = os.path.join(output_dir, f'{prefix}-tagged.srt')
    _save_tagged_srt(entries, cue_voices, tagged_path)
    print(f'  ✓ Tagged SRT (preview/edit): {tagged_path}')
    print(f'  Stats: {male_count} cue laki ({male_voice}), {female_count} cue perempuan ({female_voice})')
    print(f'  ⚠ Kalau detection salah, edit tagged SRT manual lalu pakai mode Standar dgn voice per-cue')
    print()
    print('  Contoh tagged SRT:')
    for i in range(min(3, len(entries))):
        print(f'    cue {i+1}: [{cue_voices[i]}] {" ".join(entries[i]["textLines"])[:50]}')
    print()

    # Step 8: load model + generate
    print('▶ Step 8/8: Load model Supertonic')
    tts, load_time, ep_label, native_sr = load_supertonic_model()
    print(f'  ✓ Model loaded ({load_time:.1f}s), {ep_label}')
    print(f'  Native SR: {native_sr}Hz → resample ke {OUTPUT_SAMPLE_RATE}Hz (mix-tui compat)')
    print()

    voice_display = f'{male_voice}+{female_voice} (auto-gender: {male_count}M/{female_count}F)'

    per_generate = 0.8
    pass2_ratio = 0.6 if smart_fit else 0.0
    est_total_sec = len(entries) * per_generate * (1 + pass2_ratio)

    print('═' * 64)
    print('📋 Ringkasan (Pro mode):')
    print('═' * 64)
    print(f'  SRT      : {os.path.basename(srt_path)}')
    print(f'  WAV ref  : {os.path.basename(wav_path)}')
    print(f'  Tagged   : {tagged_path}')
    print(f'  Output   : {os.path.join(output_dir, prefix + "-audio-id-dub.wav")}')
    print(f'  Voice    : {voice_display}')
    print(f'  Language : {language} (DI-LOCK)')
    print(f'  Engine   : Supertonic 3 ({ep_label})')
    print(f'  Smart Fit: {"ON" if smart_fit else "OFF"}, cap={cap}')
    print(f'  Cues     : {len(entries)}')
    print(f'  Durasi   : {format_duration(total_dur)}')
    print(f'  Estimasi : {format_duration(est_total_sec)}')
    print('═' * 64)
    print()
    print('⚠ Pro mode v0.2: gender detection via inaSpeechSegmenter (TF backend).')
    print('  Cue tanpa overlap gender → default laki. Edit tagged SRT untuk koreksi manual.')
    print('  Deterministic by design → no drift antar cue + antar voice.')
    print()

    if not questionary.confirm('Lanjut generate multi-voice?', default=True).ask():
        print('Batal. Tagged SRT tetap disimpan untuk review.')
        sys.exit(0)

    _run_generate(entries, cue_voices, output_dir, prefix, language, smart_fit, cap,
                  tts, ep_label, native_sr, load_time, total_dur, voice_display,
                  multi_voice=True)


# ============================================================
# SRT mode (6 step, mirror edge-tts-tui)
# ============================================================

def main_srt():
    print_banner()
    print('📋 Mode: SRT (dub per cue dari subtitle)')
    print('   Navigasi: ↑↓ arrow keys, Enter konfirmasi, Ctrl+C batal')
    print()

    # Step 1: SRT
    print('▶ Step 1/6: Pilih SRT')
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
        srt_path = questionary.text(f'Tidak ada SRT di {default_srt_dir}. Ketik path lengkap:').ask()
    if not srt_path or not os.path.isfile(srt_path):
        print('❌ File SRT tidak ditemukan.')
        sys.exit(1)
    print(f'  ✓ {srt_path}')
    print()

    # Step 2: output dir
    print('▶ Step 2/6: Output directory')
    default_out = str(TTS_DIR)
    output_dir = questionary.text('Output directory:', default=default_out).ask()
    if not output_dir:
        output_dir = default_out
    os.makedirs(output_dir, exist_ok=True)
    print(f'  ✓ {output_dir}')
    print()

    # Step 3: voice
    print('▶ Step 3/6: Pilih voice')
    voice_labels = [f'{code} — {desc}' for code, desc in VOICE_OPTIONS]
    voice_choice = questionary.select(
        f'Voice (10 builtin, NO cloning):',
        choices=voice_labels,
        default=voice_labels[0],
    ).ask()
    voice_name = voice_choice.split(' —')[0].strip()
    print(f'  ✓ {voice_name}')
    language = prompt_language(default='id')
    print(f'  ✓ language: {language}')
    print()

    # Step 4: Smart Fit cap
    print('▶ Step 4/6: Smart Fit cap')
    cap_choice = questionary.select(
        'Smart Fit cap (max speed):',
        choices=[
            '1.5x (clean, recommended)',
            '2.0x (cepat, sedikit robotik untuk cue padat)',
            '1.25x (paling natural, lebih sering overflow)',
            'OFF (no smart fit, natural only)',
        ],
        default='1.5x (clean, recommended)',
    ).ask()
    if 'OFF' in cap_choice:
        smart_fit = False
        cap = 1.0
    else:
        smart_fit = True
        cap = float(cap_choice.split('x')[0])
    print(f'  ✓ cap={cap}, smart_fit={smart_fit}')
    print()

    # Step 5: prefix
    print('▶ Step 5/6: Prefix output')
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

    # Step 6: load model
    print('▶ Step 6/6: Load model Supertonic')
    tts, load_time, ep_label, native_sr = load_supertonic_model()
    print(f'  ✓ Model loaded ({load_time:.1f}s), {ep_label}')
    print(f'  Native SR: {native_sr}Hz → resample ke {OUTPUT_SAMPLE_RATE}Hz (mix-tui compat)')
    print()

    # Estimasi waktu — Supertonic RTF ~0.012-0.018 M4 CPU.
    # Per cue ~0.5-1s (text 2-3s). Smart fit +80% cue Pass 2.
    per_generate = 0.8  # detik per generate (RTF 0.015 untuk text 2-3s)
    pass2_ratio = 0.6 if smart_fit else 0.0
    est_total_sec = len(entries) * per_generate * (1 + pass2_ratio)

    print('═' * 64)
    print('📋 Ringkasan:')
    print('═' * 64)
    print(f'  SRT      : {os.path.basename(srt_path)}')
    print(f'  Output   : {os.path.join(output_dir, prefix + "-audio-id-dub.wav")}')
    print(f'  Voice    : {voice_name} ({dict(VOICE_OPTIONS)[voice_name].split("(")[0].strip()})')
    print(f'  Language : {language} (DI-LOCK)')
    print(f'  Engine   : Supertonic 3 ({ep_label})')
    print(f'  Steps    : {DEFAULT_TOTAL_STEPS} (5=fast, 8=default, 12=high quality)')
    print(f'  Smart Fit: {"ON" if smart_fit else "OFF"}, cap={cap}')
    print(f'  Cues     : {len(entries)}')
    print(f'  Durasi   : {format_duration(total_dur)}')
    print(f'  Estimasi : {format_duration(est_total_sec)} (~100x OmniVoice)')
    print('═' * 64)
    print()
    print('⚠ NOTE v0.1: Supertonic = 10 fixed voices (NO cloning).')
    print('  Deterministic by design (fixed prototypes) → no drift antar cue.')
    print('  Smart Fit pakai speed= param Supertonic (Pass 2 regenerate jika overflow > crossfade).')
    print('  Override env: SUPERTONIC_STEPS=12 (kualitas), SUPERTONIC_SMART_FIT_DEBUG=1 (log)')
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
        print(f'🚀 Mulai generate TTS (Supertonic 3 {ep_label}) + mix inline...')
        print('═' * 64)
        print()

        cache_dir = os.path.join(output_dir, '.supertonic-cache')
        os.makedirs(cache_dir, exist_ok=True)

        total_samples = int(total_dur * OUTPUT_SAMPLE_RATE) + int(OUTPUT_SAMPLE_RATE * 2)
        all_audio = np.zeros(total_samples, dtype=np.float32)
        print(f'  Buffer: {total_samples} samples = {format_duration(total_samples/OUTPUT_SAMPLE_RATE)} = {total_samples*4/1024/1024:.0f} MB')
        print()

        success_count = 0
        fail_count = 0
        start_time = time.time()
        crossfade_samples = int(OUTPUT_SAMPLE_RATE * CROSSFADE_MS / 1000)
        prev_audio_end_samples = 0
        cue_voices = [voice_name] * len(entries)  # standard: same voice all cues (pro mode injects per-cue)

        for i, entry in enumerate(entries):
            cue_idx = i + 1
            text = normalize_tts_text(' '.join(entry['textLines']))
            cue_dur = entry['end'] - entry['start']
            position = int(entry['start'] * OUTPUT_SAMPLE_RATE)
            next_entry = entries[i + 1] if i + 1 < len(entries) else None

            fade_in_start = None
            fade_len = 0
            if i > 0 and position < prev_audio_end_samples:
                overlap = prev_audio_end_samples - position
                fade_in_start = position
                fade_len = min(overlap, crossfade_samples)

            if not text:
                prev_audio_end_samples = max(prev_audio_end_samples, position)
                continue

            cache_key = compute_cache_key(text, cue_voices[i], 1.0, language, DEFAULT_TOTAL_STEPS)

            try:
                if smart_fit:
                    final_audio = smart_fit_cue(
                        text, cue_dur, cue_voices[i], cap, language, DEFAULT_TOTAL_STEPS,
                        cache_dir, cache_key, prefix, cue_idx, native_sr)
                else:
                    natural_npy = os.path.join(cache_dir, f'{prefix}-cue-{cue_idx:04d}-{cache_key}.npy')
                    if not (os.path.isfile(natural_npy) and os.path.getsize(natural_npy) > 0):
                        audio = generate_cue_audio(text, cue_voices[i], speed=1.0, lang=language,
                                                   steps=DEFAULT_TOTAL_STEPS, target_sr=OUTPUT_SAMPLE_RATE,
                                                   native_sr=native_sr)
                        if len(audio) == 0:
                            fail_count += 1
                            print(f'\n  ⚠ Cue {cue_idx} gagal (output kosong)')
                            continue
                        np.save(natural_npy, audio)
                    natural_audio = np.load(natural_npy)
                    natural_audio = trim_silence_asymmetric(natural_audio, OUTPUT_SAMPLE_RATE)
                    final_audio = peak_normalize(natural_audio)
            except Exception as e:
                print(f'\n  ⚠ Cue {cue_idx} gagal: {e}')
                fail_count += 1
                continue

            if len(final_audio) == 0:
                fail_count += 1
                continue

            this_audio_end = position + len(final_audio)

            fade_out_end = None
            if next_entry:
                next_start_samples = int(next_entry['start'] * OUTPUT_SAMPLE_RATE)
                if this_audio_end > next_start_samples:
                    fade_out_end = next_start_samples
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

            prev_audio_end_samples = this_audio_end
            success_count += 1

            if cue_idx % 5 == 0 or cue_idx == len(entries):
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

        # Trim tail silence (buffer extra 2s)
        final_end = int(total_dur * OUTPUT_SAMPLE_RATE) + int(OUTPUT_SAMPLE_RATE * 0.3)
        all_audio = all_audio[:final_end]

        output_path = os.path.join(output_dir, f'{prefix}-audio-id-dub.wav')
        print(f'  Encoding WAV {OUTPUT_SAMPLE_RATE}Hz mono → {output_path}...')
        encode_wav(all_audio, OUTPUT_SAMPLE_RATE, OUTPUT_CHANNELS, output_path)

        # Cleanup cache
        try:
            cache_files = [f for f in os.listdir(cache_dir) if f.startswith(prefix)]
            cache_size_mb = sum(os.path.getsize(os.path.join(cache_dir, f)) for f in cache_files) / 1024 / 1024
            if cache_files:
                if questionary.confirm(
                    f'Hapus cache ({len(cache_files)} NPY, {cache_size_mb:.1f} MB)? '
                    f'(No = simpan untuk resume kalau generate ulang SRT sama)',
                    default=False,
                ).ask():
                    for f in cache_files:
                        try:
                            os.unlink(os.path.join(cache_dir, f))
                        except OSError:
                            pass
                    try:
                        os.rmdir(cache_dir)
                    except OSError:
                        pass
                    print('  ✓ Cache dihapus')
                else:
                    print(f'  Cache disimpan: {cache_dir} ({cache_size_mb:.1f} MB)')
        except Exception:
            pass

        if os.path.isfile(output_path):
            size_mb = os.path.getsize(output_path) / 1024 / 1024
            print()
            print('═' * 64)
            print('✅ SELESAI!')
            print(f'   Output : {output_path}')
            print(f'   Size   : {size_mb:.1f} MB')
            print(f'   Format : {OUTPUT_SAMPLE_RATE}Hz mono 16-bit PCM (mix-tui compatible)')
            print(f'   Engine : Supertonic 3')
            print(f'   Cues   : {success_count} ok / {fail_count} fail / {len(entries)} total')
            print(f'   Waktu  : {format_duration(elapsed)} (model load {load_time:.1f}s + generate)')
            print('═' * 64)
            print()
            print('🎬 Langkah berikutnya:')
            print(f'   1. Preview: open {output_path}')
            print('   2. Feed ke mix-tui (sama dengan edge-tts/piper/omnivoice SRT output)')

    finally:
        release_lock(output_dir, prefix)


# ============================================================
# Narration mode (6 step)
# ============================================================

def main_narration():
    print_banner()
    print('📋 Mode: Narasi (naskah → 1 WAV panjang)')
    print('   Navigasi: ↑↓ arrow keys, Enter konfirmasi, Ctrl+C batal')
    print()

    # Step 1: naskah
    print('▶ Step 1/6: Pilih naskah')
    if ensure_hdd():
        default_dir = str(INPUT_DIR)
    else:
        default_dir = os.getcwd()
    txt_files = []
    if os.path.isdir(default_dir):
        txt_files = sorted([f for f in os.listdir(default_dir) if f.lower().endswith('.txt')])
    if txt_files:
        txt_choice = questionary.select(
            f'Naskah (ditemukan {len(txt_files)} .txt di {default_dir}):',
            choices=txt_files + ['[Ketik path manual]'],
            default=txt_files[0],
        ).ask()
        if txt_choice == '[Ketik path manual]':
            naskah_path = questionary.text('Path naskah .txt:').ask()
        else:
            naskah_path = os.path.join(default_dir, txt_choice)
    else:
        naskah_path = questionary.text(f'Tidak ada .txt di {default_dir}. Ketik path lengkap:').ask()
    if not naskah_path or not os.path.isfile(naskah_path):
        print('❌ File naskah tidak ditemukan.')
        sys.exit(1)
    with open(naskah_path, 'r', encoding='utf-8-sig') as f:
        naskah = f.read()
    print(f'  ✓ {naskah_path} ({len(naskah)} chars)')
    print()

    # Step 2: output dir
    print('▶ Step 2/6: Output directory')
    default_out = str(TTS_DIR)
    output_dir = questionary.text('Output directory:', default=default_out).ask()
    if not output_dir:
        output_dir = default_out
    os.makedirs(output_dir, exist_ok=True)
    print(f'  ✓ {output_dir}')
    print()

    # Step 3: voice
    print('▶ Step 3/6: Pilih voice')
    voice_labels = [f'{code} — {desc}' for code, desc in VOICE_OPTIONS]
    voice_choice = questionary.select(
        f'Voice (10 builtin, NO cloning):',
        choices=voice_labels,
        default=voice_labels[0],
    ).ask()
    voice_name = voice_choice.split(' —')[0].strip()
    print(f'  ✓ {voice_name}')
    language = prompt_language(default='id')
    print(f'  ✓ language: {language}')
    print()

    # Step 4: speed
    print('▶ Step 4/6: Speed')
    speed_str = questionary.text('Speed (1.0=natural, 1.2=cepat, 0.9=pelan):', default='1.0').ask()
    try:
        speed = float(speed_str)
    except ValueError:
        speed = 1.0
    speed = max(0.7, min(speed, 2.0))
    print(f'  ✓ {speed}')
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
    print('▶ Step 6/6: Load model Supertonic')
    tts, load_time, ep_label, native_sr = load_supertonic_model()
    print(f'  ✓ Model loaded ({load_time:.1f}s), {ep_label}')
    print()

    import re
    sentences = re.split(r'(?<=[.!?。])\s+', naskah.strip())
    sentences = [s.strip() for s in sentences if s.strip()]
    if not sentences:
        print('❌ Naskah kosong.')
        sys.exit(1)

    print('═' * 64)
    print('📋 Ringkasan:')
    print('═' * 64)
    print(f'  Naskah   : {os.path.basename(naskah_path)} ({len(sentences)} kalimat)')
    print(f'  Voice    : {voice_name} ({dict(VOICE_OPTIONS)[voice_name].split("(")[0].strip()})')
    print(f'  Language : {language} (DI-LOCK)')
    print(f'  Engine   : Supertonic 3 ({ep_label})')
    print(f'  Speed    : {speed}')
    print(f'  Output   : {output_path} ({NARR_SAMPLE_RATE}Hz stereo)')
    print(f'  Steps    : {DEFAULT_TOTAL_STEPS}')
    print('═' * 64)
    print()

    if not questionary.confirm('Lanjut generate?', default=True).ask():
        print('Batal.')
        sys.exit(0)

    print(f'🚀 Mulai generate narasi (Supertonic 3 {ep_label})...')
    print()
    start_time = time.time()

    all_chunks = []
    for i, sent in enumerate(sentences):
        try:
            audio = generate_cue_audio(sent, voice_name, speed=speed, lang=language,
                                       steps=DEFAULT_TOTAL_STEPS, target_sr=NARR_SAMPLE_RATE,
                                       native_sr=native_sr)
        except Exception as e:
            print(f'\n  ⚠ Kalimat {i+1} gagal: {e}')
            continue
        if len(audio) == 0:
            continue
        audio = trim_silence_asymmetric(audio, NARR_SAMPLE_RATE)
        audio = peak_normalize(audio)
        sil = int(NARR_SAMPLE_RATE * 0.2)
        audio = np.concatenate([audio, np.zeros(sil, dtype=np.float32)])
        all_chunks.append(audio)
        if (i + 1) % 3 == 0 or i + 1 == len(sentences):
            elapsed = time.time() - start_time
            pct = (i + 1) / len(sentences) * 100
            sys.stdout.write(f'\r  [{i+1}/{len(sentences)}] {pct:5.1f}% | elapsed={format_duration(elapsed)}   ')
            sys.stdout.flush()

    print()
    elapsed = time.time() - start_time
    if not all_chunks:
        print('❌ Tidak ada audio di-generate.')
        sys.exit(1)
    final = np.concatenate(all_chunks)
    encode_wav(final, NARR_SAMPLE_RATE, NARR_CHANNELS, output_path)
    size_mb = os.path.getsize(output_path) / 1024 / 1024
    print()
    print('═' * 64)
    print('✅ SELESAI!')
    print(f'   Output : {output_path}')
    print(f'   Size   : {size_mb:.1f} MB')
    print(f'   Format : {NARR_SAMPLE_RATE}Hz stereo 16-bit PCM (review-mix/konten compatible)')
    print(f'   Engine : Supertonic 3')
    print(f'   Waktu  : {format_duration(elapsed)} (model load {load_time:.1f}s + generate)')
    print('═' * 64)
    print()
    print('🎬 Langkah berikutnya:')
    print(f'   1. Preview: open {output_path}')
    print('   2. Feed ke review-mix-tui / konten-tui / talkinghead-tui / manim-shorts-tui')


# ============================================================
# Main
# ============================================================

def main():
    parser = argparse.ArgumentParser(description='Supertonic TTS TUI — subtitlekit model lokal')
    parser.add_argument('--mode', choices=['srt', 'srt-pro', 'narasi'], help='Langsung ke mode (skip picker)')
    args = parser.parse_args()

    mode = args.mode
    if not mode:
        clear_screen()
        print_banner()
        mode = questionary.select(
            'Mode:',
            choices=[
                'SRT Standar (1 voice — dub per cue dari subtitle)',
                'SRT Pro (multi-voice auto-gender via inaSpeechSegmenter)',
                'Narasi (naskah → 1 WAV panjang)',
            ],
            default='SRT Standar (1 voice — dub per cue dari subtitle)',
        ).ask()
        if mode.startswith('SRT Pro'):
            mode = 'srt-pro'
        elif mode.startswith('SRT'):
            mode = 'srt'
        else:
            mode = 'narasi'

    if mode == 'srt':
        main_srt()
    elif mode == 'srt-pro':
        main_srt_pro()
    else:
        main_narration()


if __name__ == '__main__':
    main()
