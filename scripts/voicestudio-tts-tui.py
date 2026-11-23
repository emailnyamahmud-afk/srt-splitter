#!/usr/bin/env python3
"""
voicestudio-tts-tui.py v1.0 — TTS via VoiceStudio local API (TUI #19)

Adaptasi edge-tts-tui v7.5 + VoiceStudio desktop app local HTTP API.
VoiceStudio jalan di localhost:3900 (app desktop terbuka), TUI panggil via
HTTP. 100% lokal, GPU Metal (CoreML) di Mac M1/M2, no API key, no rate limit.

Voice source: VoiceStudio /profiles (user sudah buat 4 voice: anton_id, sari_id,
anton_jw, sari_jw). TUI fetch list, user pilih.

2 Mode (mirror edge-tts-tui v7.5):
- SRT mode (6 step): SRT → output → voice → smart fit cap → prefix → generate
  Output: {TTS_DIR}/{prefix}-audio-id-dub.wav (24kHz mono 16-bit, mix-tui compatible)
- Narration mode (5 step): naskah.txt → output → voice → speed → filename
  Output: {TTS_DIR}/{stem}-narasi.wav (48kHz stereo 16-bit, review-mix/konten compatible)

Smart Fit: port edge-tts-tui algorithm. Pass 1 generate natural (speed=1.0),
kalau natural_dur > cue_dur → Pass 2 regenerate dengan speed=min(1.5, ratio).
Cap 1.5x default (sweet spot naturalness, match edge-tts user config).

Crossfade: port edge-tts-tui mix_into_buffer + piper iterasi 3 fix (fade_in cek
actual audio end + truncate overflow ke crossfade window 150ms).

Cache: per-cue WAV di {output_dir}/.cache/{prefix}-cue-{NNN}-{hash}.wav.
Resume support (kalau stop, lanjut dari cache). Cleanup prompt di akhir.

Pipeline integrasi (sama dengan edge-tts-tui v7.5):
- SRT mode → feed mix-tui (sama dengan edge-tts SRT output)
- Narration mode → feed review-mix-tui / konten-tui / talkinghead-tui / manim-shorts-tui

Setup user (Mac ~/Dubbing/):
  pip3 install questionary numpy
  # VoiceStudio desktop app: download dari https://voicestudio.sh, install, buka app
  # Buat voice profiles (anton_id, sari_id, anton_jw, sari_jw) via app UI
  # Pastikan app TERBUKA saat TUI dijalankan (API jalan di localhost:3900)

Pakai:
  cd ~/Dubbing && source venv/bin/activate && python3 voicestudio-tts-tui.py

Health check: TUI cek GET /health di startup. Kalau VoiceStudio belum jalan →
tolak + pesan jelas. Tidak bisa jalan tanpa app desktop terbuka.
"""

import os
import sys
import time
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import struct
import shutil
import io
import wave
import urllib.request
import urllib.error
from pathlib import Path

# ============================================================
# Version + constants
# ============================================================

VERSION = 'v1.0'
VOICESTUDIO_BASE = 'http://localhost:3900'
VOICESTUDIO_TIMEOUT = 10        # health/profiles
VOICESTUDIO_TTS_TIMEOUT = 180   # generate (per cue bisa lama kalau text panjang)

# Filter voice profile by name keyword (user's 4 voices). Kalau None → tampilkan semua.
VOICE_NAME_KEYWORDS = ['anton', 'sari']

_ACTIVE_LOCK = None
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
    print('═' * 64)
    sys.exit(1)


# Audio constants — match edge-tts-tui (mix-tui compatible)
OUTPUT_SAMPLE_RATE = 24000
OUTPUT_CHANNELS = 1
OUTPUT_BITS = 16

NARR_SAMPLE_RATE = 48000   # narration mode: 48kHz stereo
NARR_CHANNELS = 2

CROSSFADE_MS = 150
TRIM_HEAD_DB = -30
TRIM_TAIL_DB = -30
TRIM_PADDING_MS = 30
NORMALIZE_DBFS = -2.0
NOISE_FLOOR_DB = -50.0

SMART_FIT_CAP_DEFAULT = 1.5
SMART_FIT_DEBUG = os.environ.get('VS_SMART_FIT_DEBUG') == '1'

# Parallel generation: VoiceStudio local API handle concurrent requests (MPS
# pipeline). Default 3 workers (balance speed vs memory). Override via env
# VS_WORKERS=1 untuk sequential (debug), VS_WORKERS=4 untuk lebih agresif.
MAX_WORKERS = int(os.environ.get('VS_WORKERS', '3'))


# ============================================================
# VoiceStudio HTTP API client
# ============================================================

def voicestudio_health_check():
    """GET /health → return (ok, info_dict). info berisi device (metal/cuda/cpu)."""
    try:
        req = urllib.request.Request(
            f'{VOICESTUDIO_BASE}/health',
            headers={'Authorization': 'Bearer local'},
        )
        with urllib.request.urlopen(req, timeout=VOICESTUDIO_TIMEOUT) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            return True, data
    except urllib.error.URLError as e:
        return False, {'error': str(e.reason) if hasattr(e, 'reason') else str(e)}
    except Exception as e:
        return False, {'error': str(e)}


def voicestudio_list_profiles():
    """GET /profiles → list voice profiles. Return list of {profile_id, name, ...}."""
    try:
        req = urllib.request.Request(
            f'{VOICESTUDIO_BASE}/profiles',
            headers={'Authorization': 'Bearer local'},
        )
        with urllib.request.urlopen(req, timeout=VOICESTUDIO_TIMEOUT) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            # Format bisa list atau {profiles: [...]}
            if isinstance(data, list):
                return data
            if isinstance(data, dict):
                return data.get('profiles', data.get('voices', []))
            return []
    except Exception:
        return []


def _extract_audio_bytes(raw):
    """Robust: response bisa raw WAV bytes (RIFF), JSON {audio: base64}, atau raw audio.
    Verified dari OpenAPI spec VoiceStudio 0.5.8 — response 200 schema generic {},
    jadi handle 3 kasus: RIFF header → WAV langsung; JSON → extract base64; else raw."""
    if not raw or len(raw) < 4:
        return raw
    # Case 1: raw WAV (RIFF header)
    if raw[:4] == b'RIFF':
        return raw
    # Case 2: JSON response (mungkin {audio: base64, ...} atau {data: ...})
    if raw[:1] in (b'{', b'['):
        try:
            data = json.loads(raw.decode('utf-8', errors='replace'))
            # Cari field audio base64 di beberapa nama umum
            for key in ('audio', 'data', 'wav', 'content', 'bytes'):
                if isinstance(data, dict) and key in data:
                    val = data[key]
                    if isinstance(val, str):
                        import base64
                        return base64.b64decode(val)
                    if isinstance(val, (bytes, bytearray)):
                        return bytes(val)
            # Kalau JSON tapi tidak ada field audio → error informatif
            raise RuntimeError(f'Response JSON tanpa field audio. Keys: {list(data.keys()) if isinstance(data, dict) else type(data)}')
        except (json.JSONDecodeError, UnicodeDecodeError):
            pass  # bukan JSON valid → lanjut case 3
    # Case 3: raw audio bytes lain (mp3 ID3, dll) → return as-is
    return raw


def voicestudio_generate_speech(text, voice_id, speed=1.0, fmt='wav'):
    """POST /v1/audio/speech → return audio bytes (WAV/MP3/PCM, atau None kalau gagal).

    OpenAI-compatible endpoint. Body JSON:
      {model: tts-1, voice: profile_id|name, input: text, response_format: wav, speed: speed}
    Voice param: profile ID atau profile name (case-insensitive, ID wins) — per OpenAPI spec.
    Response: raw audio bytes (RIFF WAV kalau fmt=wav). Robust handler untuk JSON base64.
    No auth needed (local API, no security scheme per OpenAPI spec).
    """
    body = json.dumps({
        'model': 'tts-1',
        'voice': voice_id,
        'input': text,
        'response_format': fmt,
        'speed': speed,
    }).encode('utf-8')
    req = urllib.request.Request(
        f'{VOICESTUDIO_BASE}/v1/audio/speech',
        data=body,
        headers={
            'Authorization': 'Bearer local',
            'Content-Type': 'application/json',
        },
        method='POST',
    )
    try:
        with urllib.request.urlopen(req, timeout=VOICESTUDIO_TTS_TIMEOUT) as resp:
            raw = resp.read()
            return _extract_audio_bytes(raw)
    except urllib.error.HTTPError as e:
        err_body = ''
        try:
            err_body = e.read().decode('utf-8', errors='replace')[:300]
        except Exception:
            pass
        raise RuntimeError(f'HTTP {e.code}: {err_body}')
    except urllib.error.URLError as e:
        raise RuntimeError(f'URL error: {e.reason if hasattr(e, "reason") else e}')


# ============================================================
# WAV decode + resample (replace edge-tts decode_mp3_to_pcm)
# ============================================================

def resample_linear(arr, from_sr, to_sr):
    """Resample float32 array linear interpolation (no scipy needed)."""
    if from_sr == to_sr or len(arr) == 0:
        return arr
    n_out = int(len(arr) * to_sr / from_sr)
    if n_out < 1:
        n_out = 1
    indices = np.linspace(0, len(arr) - 1, n_out)
    return np.interp(indices, np.arange(len(arr)), arr).astype(np.float32)


def decode_wav_bytes_to_pcm(wav_bytes, target_sr=OUTPUT_SAMPLE_RATE):
    """Decode WAV bytes → float32 numpy array (mono, target_sr Hz)."""
    buf = io.BytesIO(wav_bytes)
    with wave.open(buf, 'rb') as wf:
        channels = wf.getnchannels()
        sampwidth = wf.getsampwidth()
        sr = wf.getframerate()
        n_frames = wf.getnframes()
        frames = wf.readframes(n_frames)

    # Convert bytes → float32
    if sampwidth == 2:
        arr = np.frombuffer(frames, dtype=np.int16).astype(np.float32) / 32768.0
    elif sampwidth == 4:
        arr = np.frombuffer(frames, dtype=np.int32).astype(np.float32) / 2147483648.0
    elif sampwidth == 1:
        arr = (np.frombuffer(frames, dtype=np.uint8).astype(np.float32) - 128.0) / 128.0
    else:
        raise RuntimeError(f'sampwidth {sampwidth} tidak didukung')

    # Stereo → mono (average channels)
    if channels > 1 and len(arr) % channels == 0:
        arr = arr.reshape(-1, channels).mean(axis=1)

    # Resample ke target_sr
    if sr != target_sr:
        arr = resample_linear(arr, sr, target_sr)

    return arr


# ============================================================
# SRT parsing (port edge-tts-tui)
# ============================================================

def parse_srt(content):
    entries = []
    blocks = content.strip().split('\n\n')
    for block in blocks:
        lines = [l for l in block.strip().split('\n') if l.strip()]
        if len(lines) < 2:
            continue
        # Cari line timestamp (format: 00:00:01,234 --> 00:00:05,678)
        ts_idx = -1
        for i, line in enumerate(lines):
            if '-->' in line:
                ts_idx = i
                break
        if ts_idx < 0:
            continue
        ts_line = lines[ts_idx]
        parts = ts_line.split('-->')
        if len(parts) != 2:
            continue

        def parse_ts(ts):
            ts = ts.strip()
            try:
                h, m, rest = ts.split(':')
                s, ms = rest.split(',')
                return int(h) * 3600 + int(m) * 60 + float(s) + int(ms) / 1000.0
            except Exception:
                try:
                    h, m, s = ts.split(':')
                    return int(h) * 3600 + int(m) * 60 + float(s)
                except Exception:
                    return 0.0

        start = parse_ts(parts[0])
        end = parse_ts(parts[1])
        text_lines = lines[ts_idx + 1:]
        if start < end and text_lines:
            entries.append({'start': start, 'end': end, 'textLines': text_lines})
    return entries


def format_duration(seconds):
    if seconds < 60:
        return f'{seconds:.1f}s'
    m = int(seconds // 60)
    s = seconds % 60
    return f'{m}j{m}s' if False else f'{m}m{s:.0f}s'


# ============================================================
# Text normalize (port edge-tts-tui)
# ============================================================

def normalize_tts_text(text):
    text = text.replace('\n', ' ').replace('\r', ' ')
    text = ' '.join(text.split())
    return text.strip()


# ============================================================
# Audio processing (port edge-tts-tui)
# ============================================================

def db_to_linear(db):
    return 10.0 ** (db / 20.0)


def trim_silence_asymmetric(audio, sr, padding_ms=TRIM_PADDING_MS):
    if len(audio) == 0:
        return audio
    head_thresh = db_to_linear(TRIM_HEAD_DB)
    tail_thresh = db_to_linear(TRIM_TAIL_DB)
    abs_audio = np.abs(audio)

    # Head trim
    head_idx = 0
    for i in range(len(abs_audio)):
        if abs_audio[i] > head_thresh:
            head_idx = i
            break
    # Tail trim
    tail_idx = len(abs_audio)
    for i in range(len(abs_audio) - 1, -1, -1):
        if abs_audio[i] > tail_thresh:
            tail_idx = i + 1
            break

    trimmed = audio[head_idx:tail_idx]
    pad = int(sr * padding_ms / 1000)
    if pad > 0:
        trimmed = np.concatenate([np.zeros(pad, dtype=np.float32), trimmed, np.zeros(pad, dtype=np.float32)])
    return trimmed


def peak_normalize(audio, target_db=NORMALIZE_DBFS, noise_floor_db=NOISE_FLOOR_DB):
    if len(audio) == 0:
        return audio
    peak = np.max(np.abs(audio))
    noise_floor = db_to_linear(noise_floor_db)
    if peak < noise_floor:
        return audio
    target = db_to_linear(target_db)
    gain = target / peak
    return (audio * gain).astype(np.float32)


def apply_fade_out(audio, fade_start, fade_end):
    if fade_start >= fade_end or fade_start >= len(audio) or fade_end <= 0:
        return audio
    fade_start = max(0, fade_start)
    fade_end = min(len(audio), fade_end)
    n = fade_end - fade_start
    if n <= 0:
        return audio
    fade = np.linspace(1.0, 0.0, n, dtype=np.float32)
    out = audio.copy()
    out[fade_start:fade_end] *= fade
    return out


def apply_fade_in(audio, fade_start, fade_end):
    if fade_start >= fade_end or fade_start >= len(audio) or fade_end <= 0:
        return audio
    fade_start = max(0, fade_start)
    fade_end = min(len(audio), fade_end)
    n = fade_end - fade_start
    if n <= 0:
        return audio
    fade = np.linspace(0.0, 1.0, n, dtype=np.float32)
    out = audio.copy()
    out[fade_start:fade_end] *= fade
    return out


# ============================================================
# TTS generate 1 cue (replace edge-tts generate_cue_tts)
# ============================================================

def generate_cue_tts(text, voice_id, speed, output_wav, cue_idx=0):
    """Generate 1 cue via VoiceStudio /v1/audio/speech → WAV file. Return True sukses."""
    try:
        wav_bytes = voicestudio_generate_speech(text, voice_id, speed=speed, fmt='wav')
        if not wav_bytes or len(wav_bytes) < 44:
            raise RuntimeError('output WAV kosong atau tidak terbentuk')
        with open(output_wav, 'wb') as f:
            f.write(wav_bytes)
        return True
    except Exception as e:
        print(f'  ⚠ VoiceStudio gagal cue {cue_idx}: {e}')
        return False


# ============================================================
# Smart Fit (port edge-tts-tui, speed replaces rate)
# ============================================================

def smart_fit_cue(text, cue_dur, voice_id, cap, cache_dir, cache_key, prefix, cue_idx):
    """Smart Fit untuk 1 cue:
    1. Generate natural (speed=1.0)
    2. Trim + compute need = natural_dur / cue_dur
    3. need > 1.0 → regenerate dengan speed = min(need, cap)
    4. Peak normalize
    """
    natural_wav = os.path.join(cache_dir, f'{prefix}-cue-{cue_idx:04d}-{cache_key}.wav')
    smart_wav = os.path.join(cache_dir, f'{prefix}-cue-{cue_idx:04d}-{cache_key}_s{cap}.wav')

    # Pass 1: natural
    if not (os.path.isfile(natural_wav) and os.path.getsize(natural_wav) > 0):
        if not generate_cue_tts(text, voice_id, 1.0, natural_wav, cue_idx=cue_idx):
            raise RuntimeError(f'Pass 1 gagal cue {cue_idx}')

    with open(natural_wav, 'rb') as f:
        wav_bytes = f.read()
    audio1 = decode_wav_bytes_to_pcm(wav_bytes, OUTPUT_SAMPLE_RATE)
    natural_audio = trim_silence_asymmetric(audio1, OUTPUT_SAMPLE_RATE)
    natural_dur = len(natural_audio) / OUTPUT_SAMPLE_RATE
    need = natural_dur / max(0.001, cue_dur)

    # Threshold: regenerate HANYA kalau overflow melebihi crossfade window.
    # Mix loop truncate audio ke next_start + crossfade_samples, jadi audio
    # sampai cue_dur + crossfade tidak ada audible cut. need 1.0-1.15 (overflow
    # kecil) → pakai natural, hemat 1 API call (Pass 2 skip). cuts ~40-60% calls.
    cue_samples = int(cue_dur * OUTPUT_SAMPLE_RATE)
    crossfade_samples = int(OUTPUT_SAMPLE_RATE * CROSSFADE_MS / 1000)
    overflow_samples = len(natural_audio) - cue_samples
    fits_in_crossfade = overflow_samples <= crossfade_samples

    if SMART_FIT_DEBUG:
        if overflow_samples <= 0:
            fit_status = 'FIT'
        elif fits_in_crossfade:
            fit_status = f'OVERFLOW+xfade need={need:.2f} (no regen)'
        else:
            fit_status = f'OVERFLOW need={need:.2f} (regen)'
        print(f'  [cue {cue_idx}] dur={cue_dur:.2f}s nat={natural_dur:.2f}s {fit_status}')

    if fits_in_crossfade:
        return peak_normalize(natural_audio)

    # Pass 2: smart fit dengan speed (overflow melebihi crossfade window)
    speed = min(need, cap)
    if SMART_FIT_DEBUG:
        print(f'  [cue {cue_idx}] Pass 2: need={need:.2f} cap={cap} speed={speed:.2f}')

    if not (os.path.isfile(smart_wav) and os.path.getsize(smart_wav) > 0):
        if not generate_cue_tts(text, voice_id, speed, smart_wav, cue_idx=cue_idx):
            print(f'  ⚠ Pass 2 gagal cue {cue_idx} (speed={speed}), pakai natural')
            return peak_normalize(natural_audio)

    with open(smart_wav, 'rb') as f:
        wav_bytes = f.read()
    audio2 = decode_wav_bytes_to_pcm(wav_bytes, OUTPUT_SAMPLE_RATE)
    smart_audio = trim_silence_asymmetric(audio2, OUTPUT_SAMPLE_RATE)
    return peak_normalize(smart_audio)


# ============================================================
# Parallel cue worker (Phase 1: generate, thread-safe via cache files)
# ============================================================

def _generate_cue_worker(args):
    """Worker: generate 1 cue → return (i, final_audio or None, error_str).

    Thread-safe: setiap cue punya cache file unik ({prefix}-cue-{NNN}-{hash}.wav),
    jadi concurrent worker tidak bentrok. smart_fit_cue cek cache dulu sebelum
    call API. Return audio array (float32) atau None+error.
    """
    i, entry, voice_id, cap, smart_fit, cache_dir, prefix = args
    cue_idx = i + 1
    text = normalize_tts_text(' '.join(entry['textLines']))
    cue_dur = entry['end'] - entry['start']

    if not text:
        return (i, None, None)  # empty cue, skip di mix phase

    cache_key = compute_cache_key(text, voice_id, 1.0)
    try:
        if smart_fit:
            final_audio = smart_fit_cue(text, cue_dur, voice_id, cap, cache_dir, cache_key, prefix, cue_idx)
        else:
            natural_wav = os.path.join(cache_dir, f'{prefix}-cue-{cue_idx:04d}-{cache_key}.wav')
            if not (os.path.isfile(natural_wav) and os.path.getsize(natural_wav) > 0):
                if not generate_cue_tts(text, voice_id, 1.0, natural_wav, cue_idx=cue_idx):
                    raise RuntimeError('VoiceStudio gagal')
            with open(natural_wav, 'rb') as f:
                wav_bytes = f.read()
            audio1 = decode_wav_bytes_to_pcm(wav_bytes, OUTPUT_SAMPLE_RATE)
            natural_audio = trim_silence_asymmetric(audio1, OUTPUT_SAMPLE_RATE)
            final_audio = peak_normalize(natural_audio)
        return (i, final_audio, None)
    except Exception as e:
        return (i, None, str(e))


# ============================================================
# Mix inline + crossfade (port edge-tts + piper iterasi 3 truncation fix)
# ============================================================

def mix_into_buffer(all_audio, audio, position, fade_out_end=None, fade_in_start=None, fade_len=0):
    """Mix ADD audio ke all_audio pada position, dengan optional fade."""
    if len(audio) == 0:
        return all_audio
    end_pos = position + len(audio)
    if end_pos > len(all_audio):
        extra = np.zeros(end_pos - len(all_audio), dtype=np.float32)
        all_audio = np.concatenate([all_audio, extra])

    if fade_in_start is not None and fade_len > 0:
        local_fade_end = min(len(audio), fade_len)
        if local_fade_end > 0:
            audio = apply_fade_in(audio, 0, int(local_fade_end))

    if fade_out_end is not None and end_pos > fade_out_end:
        fade_start_in_audio = fade_out_end - position
        if fade_start_in_audio < len(audio):
            audio = apply_fade_out(audio, int(fade_start_in_audio), int(len(audio)))

    all_audio[position:end_pos] += audio
    return all_audio


# ============================================================
# Encode WAV
# ============================================================

def encode_wav(audio, sample_rate=OUTPUT_SAMPLE_RATE, channels=OUTPUT_CHANNELS, output_path=None):
    clipped = np.clip(audio, -1.0, 1.0)
    int_audio = (clipped * 32767).astype(np.int16)

    # Mono → stereo kalau channels=2
    if channels == 2 and len(int_audio.shape) == 1:
        int_audio = np.column_stack([int_audio, int_audio]).flatten()

    with wave.open(output_path, 'wb') as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(OUTPUT_BITS // 8)
        wf.setframerate(sample_rate)
        wf.writeframes(int_audio.tobytes())


# ============================================================
# TUI helpers
# ============================================================

def clear_screen():
    os.system('clear' if os.name != 'nt' else 'cls')


def print_banner():
    clear_screen()
    title = f'🎙️  VoiceStudio TTS TUI {VERSION}'
    pad_title = max(0, 66 - len(title) - 2)
    print('╔' + '═' * 64 + '╗')
    print('║  ' + title + ' ' * pad_title + '║')
    print('║  Local API localhost:3900 | Metal GPU | Smart Fit 1.5x      ║')
    print('║  Adaptasi edge-tts-tui v7.5 | 100% lokal, no API key        ║')
    print('╚' + '═' * 64 + '╝')
    print()


def find_srt_files(search_dir):
    files = []
    for ext in ('srt', 'SRT'):
        for f in Path(search_dir).glob(f'*.{ext}'):
            files.append(f.name)
    files.sort()
    return files


def compute_cache_key(text, voice_id, speed):
    h = hashlib.md5(f'{text}|{voice_id}|{speed:.2f}'.encode()).hexdigest()
    return h[:12]


# ============================================================
# Lock file (paralel-safe, port edge-tts-tui)
# ============================================================

def _pid_alive(pid):
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
        return True
    except (ProcessLookupError, PermissionError, OSError):
        return False


def lock_path_for(output_dir, prefix):
    return os.path.join(output_dir, f'.{prefix}.lock')


def acquire_lock(output_dir, prefix):
    global _ACTIVE_LOCK
    lock_path = lock_path_for(output_dir, prefix)
    if os.path.isfile(lock_path):
        try:
            with open(lock_path, 'r') as f:
                holder_pid = int(f.read().strip())
            if _pid_alive(holder_pid):
                return False, lock_path, holder_pid
        except (ValueError, OSError):
            pass
    try:
        with open(lock_path, 'w') as f:
            f.write(str(os.getpid()))
        _ACTIVE_LOCK = (output_dir, prefix)
        return True, lock_path, os.getpid()
    except OSError as e:
        return False, lock_path, -1


def release_lock(output_dir, prefix):
    global _ACTIVE_LOCK
    lock_path = lock_path_for(output_dir, prefix)
    try:
        if os.path.isfile(lock_path):
            with open(lock_path, 'r') as f:
                pid = int(f.read().strip())
            if pid == os.getpid():
                os.unlink(lock_path)
    except (ValueError, OSError):
        pass
    _ACTIVE_LOCK = None


# ============================================================
# Voice picker (VoiceStudio /profiles)
# ============================================================

def pick_voice(profiles):
    """Filter + display voice profiles. Return (voice_param, label) atau None.

    voice_param: dikirim ke /v1/audio/speech voice field. Per OpenAPI spec 0.5.8,
    voice param accept profile ID atau profile NAME (case-insensitive, ID wins).
    Jadi kalau field id tidak ada, pakai name (tetap valid).
    """
    if not profiles:
        print('  ❌ Tidak ada voice profile di VoiceStudio.')
        print('     Buat voice dulu via VoiceStudio app (anton_id, sari_id, anton_jw, sari_jw).')
        return None

    # Debug: dump keys profile pertama supaya user tahu struktur asli VoiceStudio
    if SMART_FIT_DEBUG and profiles:
        first = profiles[0]
        keys = list(first.keys()) if isinstance(first, dict) else type(first)
        print(f'  [debug] profile[0] keys: {keys}')
        print(f'  [debug] profile[0] sample: {str(first)[:200]}')

    # Normalisasi: pastikan list of dict
    if isinstance(profiles, dict):
        # Mungkin {profiles: [...]} atau {voices: [...]}
        profiles = profiles.get('profiles') or profiles.get('voices') or list(profiles.values())

    # Filter by keyword (anton, sari) kalau ada match. Kalau tidak → semua.
    filtered = []
    for p in profiles:
        if not isinstance(p, dict):
            continue
        name = str(p.get('name') or p.get('label') or p.get('id') or p.get('profile_id') or '').lower()
        if any(kw in name for kw in VOICE_NAME_KEYWORDS):
            filtered.append(p)
    if not filtered:
        filtered = [p for p in profiles if isinstance(p, dict)]

    # Build (voice_param, label). voice_param = id atau name (spec accept keduanya).
    labels = []
    for p in filtered:
        pid = p.get('id') or p.get('profile_id') or p.get('name')
        name = p.get('name') or p.get('label') or pid
        lang = p.get('language') or p.get('lang') or ''
        # voice_param: prefer id, fallback name (spec accept name case-insensitive)
        voice_param = pid
        label = f'{name}'
        if pid and pid != name:
            label += f' ({pid})'
        if lang:
            label += f' [{lang}]'
        labels.append((voice_param, label))

    if not labels:
        print('  ❌ Voice profile tidak punya field id/name.')
        print(f'     Profile sample: {str(profiles[:1])[:300]}')
        return None

    label_strs = [l[1] for l in labels]
    choice = questionary.select(
        f'Voice ({len(labels)} profile ditemukan di VoiceStudio):',
        choices=label_strs,
        default=label_strs[0],
    ).ask()
    idx = label_strs.index(choice)
    return labels[idx]


# ============================================================
# SRT mode main (6 step)
# ============================================================

def main():
    print_banner()

    # Health check di startup — tolak kalau VoiceStudio belum jalan
    print('▶ Health check VoiceStudio...')
    ok, info = voicestudio_health_check()
    if not ok:
        print()
        print('═' * 64)
        print('❌ VoiceStudio app belum jalan!')
        print('═' * 64)
        print()
        print('   TUI ini butuh VoiceStudio desktop app terbuka (API di localhost:3900).')
        print()
        print('   Cara fix:')
        print('   1. Buka VoiceStudio app (dari Applications / Launchpad)')
        print('   2. Pastikan app tetap terbuka (tray icon aktif di menu bar)')
        print('   3. Jalankan TUI ini lagi: python3 voicestudio-tts-tui.py')
        print()
        print(f'   Detail error: {info.get("error", "unknown")[:200]}')
        print()
        print('═' * 64)
        sys.exit(1)

    device = info.get('device') or info.get('engine') or 'unknown'
    print(f'  ✓ VoiceStudio jalan (device: {device})')
    print()

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

    # === SRT mode ===
    try:
        from config import INPUT_DIR, TTS_DIR, ensure_hdd

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
            srt_path = questionary.text(f'Tidak ada SRT di {default_srt_dir}. Ketik path:', default='').ask()
        if not srt_path or not os.path.isfile(srt_path):
            print('❌ File SRT tidak ditemukan.')
            sys.exit(1)
        print(f'  ✓ {srt_path}')
        print()

        # Step 2: Output dir
        print('▶ Step 2/6: Output directory')
        if ensure_hdd():
            default_out = str(TTS_DIR)
        else:
            default_out = os.path.dirname(os.path.abspath(srt_path))
        output_dir = questionary.text('Output directory:', default=default_out).ask()
        if not output_dir:
            output_dir = default_out
        os.makedirs(output_dir, exist_ok=True)
        print(f'  ✓ {output_dir}')
        print()

        # Step 3: Voice
        print('▶ Step 3/6: Pilih voice (fetch VoiceStudio /profiles)')
        profiles = voicestudio_list_profiles()
        voice_pick = pick_voice(profiles)
        if not voice_pick:
            sys.exit(1)
        voice_id, voice_label = voice_pick
        print(f'  ✓ {voice_id}')
        print()

        # Step 4: Smart Fit cap
        print('▶ Step 4/6: Smart Fit cap')
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

        # Step 5: Prefix
        print('▶ Step 5/6: Prefix output')
        default_prefix = os.path.splitext(os.path.basename(srt_path))[0]
        prefix = questionary.text(
            f'Prefix (output: {{prefix}}-audio-id-dub.wav):',
            default=default_prefix,
        ).ask()
        if not prefix:
            prefix = default_prefix
        # Lock check
        ok_lock, lock_path, holder_pid = acquire_lock(output_dir, prefix)
        if not ok_lock:
            print(f'  ⚠ Lock aktif untuk prefix "{prefix}" (PID {holder_pid}).')
            print(f'     Kalau yakin tidak ada proses lain, hapus: rm {lock_path}')
            sys.exit(1)
        print(f'  ✓ {prefix}')
        print()

        # Step 6: Generate
        print('▶ Step 6/6: Generate')
        with open(srt_path, 'r', encoding='utf-8') as f:
            content = f.read()
        entries = parse_srt(content)
        if not entries:
            print('❌ Tidak ada cue di SRT.')
            sys.exit(1)

        total_dur = entries[-1]['end'] - entries[0]['start']
        cache_dir = os.path.join(output_dir, '.cache')
        os.makedirs(cache_dir, exist_ok=True)

        print()
        print('═' * 64)
        print('📋 Ringkasan:')
        print('═' * 64)
        print(f'  SRT      : {os.path.basename(srt_path)}')
        print(f'  Output   : {os.path.join(output_dir, prefix + "-audio-id-dub.wav")}')
        print(f'  Voice    : {voice_id}')
        print(f'  Device   : {device}')
        print(f'  Rate     : natural (smart fit handles speedup)')
        print(f'  Smart Fit: {"ON" if smart_fit else "OFF"}, cap={cap}')
        print(f'  Workers  : {MAX_WORKERS} (parallel, env VS_WORKERS)')
        print(f'  Cues     : {len(entries)}')
        print(f'  Durasi   : {format_duration(total_dur)}')
        print('═' * 64)
        print()

        confirm = questionary.confirm('Lanjut generate?', default=True).ask()
        if not confirm:
            print('⏹ Dibatalkan.')
            return

        print()
        print('═' * 64)
        print(f'🚀 Mulai generate TTS (VoiceStudio {device}, {MAX_WORKERS} parallel workers)...')
        print('═' * 64)
        print()

        all_audio = np.zeros(int(total_dur * OUTPUT_SAMPLE_RATE) + int(OUTPUT_SAMPLE_RATE * 2), dtype=np.float32)
        success_count = 0
        fail_count = 0
        first_error = ''
        start_time = time.time()
        crossfade_samples = int(OUTPUT_SAMPLE_RATE * CROSSFADE_MS / 1000)
        n_entries = len(entries)

        # ============================================================
        # Phase 1: PARALLEL generate semua cue (ThreadPoolExecutor).
        # VoiceStudio local API handle concurrent requests (MPS pipeline).
        # Cache file unik per cue → thread-safe. Worker return audio array.
        # ============================================================
        print(f'⚡ Phase 1/2: Generate {n_entries} cue paralel ({MAX_WORKERS} workers)...')
        print()
        worker_args = [(i, entries[i], voice_id, cap, smart_fit, cache_dir, prefix) for i in range(n_entries)]
        cue_audios = {}  # i → (audio or None, error or None)

        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as ex:
            futures = {ex.submit(_generate_cue_worker, arg): arg[0] for arg in worker_args}
            done = 0
            for fut in as_completed(futures):
                i, audio, err = fut.result()
                cue_audios[i] = (audio, err)
                done += 1
                elapsed = time.time() - start_time
                pct = done / n_entries * 100
                eta = (elapsed / done) * (n_entries - done) if done > 0 else 0
                status = '❌' if err else ('⏭' if audio is None else '✓')
                sys.stdout.write(
                    f'\r  [{done}/{n_entries}] {pct:5.1f}% {status} | '
                    f'elapsed={format_duration(elapsed)} | ETA={format_duration(eta)}   '
                )
                sys.stdout.flush()

        print()
        gen_elapsed = time.time() - start_time
        print(f'  ✓ Phase 1 selesai: {format_duration(gen_elapsed)}')
        print()

        # ============================================================
        # Phase 2: SEQUENTIAL mix (crossfade + truncate, pure numpy, cepat).
        # Harus sequential karena position/crossfade depend on prev audio end.
        # ============================================================
        print(f'🎚 Phase 2/2: Mix inline + crossfade...')
        prev_audio_end_samples = 0

        for i, entry in enumerate(entries):
            cue_idx = i + 1
            text = normalize_tts_text(' '.join(entry['textLines']))
            cue_dur = entry['end'] - entry['start']
            position = int(entry['start'] * OUTPUT_SAMPLE_RATE)
            next_entry = entries[i + 1] if i + 1 < len(entries) else None

            audio, err = cue_audios.get(i, (None, None))

            if err:
                fail_count += 1
                if not first_error:
                    first_error = err
                print(f'  [{cue_idx}/{n_entries}] ❌ {text[:30]:<30} | {err}')
                prev_audio_end_samples = max(prev_audio_end_samples, position)
                continue

            if audio is None:
                # empty cue (no text)
                prev_audio_end_samples = max(prev_audio_end_samples, position)
                continue

            final_audio = audio
            this_audio_end = position + len(final_audio)

            # fade_in kalau overlap dengan prev audio end
            fade_in_start = None
            fade_len = 0
            if i > 0 and position < prev_audio_end_samples:
                overlap = prev_audio_end_samples - position
                fade_in_start = position
                fade_len = min(overlap, crossfade_samples)

            # Truncate overflow ke crossfade window (simetris crossfade, no numpuk)
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

        print()
        print()
        elapsed = time.time() - start_time
        print(f'  ✓ Selesai generate: {success_count} cue ok, {fail_count} fail ({format_duration(elapsed)})')
        if fail_count > 0:
            print(f'  ⚠ First error: {first_error}')

        output_path = os.path.join(output_dir, f'{prefix}-audio-id-dub.wav')
        print(f'  Encoding WAV → {output_path}...')
        encode_wav(all_audio, OUTPUT_SAMPLE_RATE, OUTPUT_CHANNELS, output_path)

        # Cleanup cache (port edge-tts-tui)
        try:
            cache_files = [f for f in os.listdir(cache_dir) if f.startswith(prefix)]
            cache_size_mb = sum(os.path.getsize(os.path.join(cache_dir, f)) for f in cache_files) / 1024 / 1024
            if cache_files:
                if questionary.confirm(
                    f'Hapus cache ({len(cache_files)} WAV, {cache_size_mb:.1f} MB)? '
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
                    print(f'  Kalau generate ulang SRT sama → cache dipakai (resume)')
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
            print(f'   Device : {device}')
            print(f'   Voice  : {voice_id}')
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
        print('   Cache disimpan — jalankan lagi dengan SRT + prefix sama untuk resume.')
    finally:
        if _ACTIVE_LOCK:
            release_lock(_ACTIVE_LOCK[0], _ACTIVE_LOCK[1])


# ============================================================
# Narration mode main (5 step)
# ============================================================

def main_narration():
    try:
        from config import TTS_DIR, ensure_hdd

        # Step 1: naskah
        print('▶ Step 1/5: Pilih naskah (.txt)')
        if ensure_hdd():
            default_dir = str(TTS_DIR)
        else:
            default_dir = os.getcwd()
        txt_files = sorted([f.name for f in Path(default_dir).glob('*.txt')])
        if txt_files:
            txt_choice = questionary.select(
                f'File naskah (ditemukan {len(txt_files)} di {default_dir}):',
                choices=txt_files + ['[Ketik path manual]'],
                default=txt_files[0],
            ).ask()
            if txt_choice == '[Ketik path manual]':
                naskah_path = questionary.text('Path naskah:').ask()
            else:
                naskah_path = os.path.join(default_dir, txt_choice)
        else:
            naskah_path = questionary.text(f'Tidak ada .txt di {default_dir}. Ketik path:', default='').ask()
        if not naskah_path or not os.path.isfile(naskah_path):
            print('❌ File naskah tidak ditemukan.')
            sys.exit(1)
        print(f'  ✓ {naskah_path}')
        print()

        # Step 2: Output dir
        print('▶ Step 2/5: Output directory')
        if ensure_hdd():
            default_out = str(TTS_DIR)
        else:
            default_out = os.path.dirname(os.path.abspath(naskah_path))
        output_dir = questionary.text('Output directory:', default=default_out).ask()
        if not output_dir:
            output_dir = default_out
        os.makedirs(output_dir, exist_ok=True)
        print(f'  ✓ {output_dir}')
        print()

        # Step 3: Voice
        print('▶ Step 3/5: Pilih voice')
        profiles = voicestudio_list_profiles()
        voice_pick = pick_voice(profiles)
        if not voice_pick:
            sys.exit(1)
        voice_id, voice_label = voice_pick
        print(f'  ✓ {voice_id}')
        print()

        # Step 4: Speed
        print('▶ Step 4/5: Speed (narration, no smart fit)')
        speed_choice = questionary.select(
            'Speed (1.0 = natural):',
            choices=[
                '1.0x (natural)',
                '1.1x (sedikit cepat)',
                '0.9x (sedikit pelan)',
                '[Ketik manual]',
            ],
            default='1.0x (natural)',
        ).ask()
        if speed_choice == '[Ketik manual]':
            sp_str = questionary.text('Speed (0.25 - 4.0):', default='1.0').ask()
            try:
                speed = float(sp_str)
            except ValueError:
                speed = 1.0
        else:
            speed = float(speed_choice.split('x')[0])
        print(f'  ✓ speed={speed}')
        print()

        # Step 5: filename + generate
        print('▶ Step 5/5: Filename output')
        default_stem = os.path.splitext(os.path.basename(naskah_path))[0]
        filename = questionary.text('Filename (tanpa .wav):', default=default_stem + '-narasi').ask()
        if not filename:
            filename = default_stem + '-narasi'

        with open(naskah_path, 'r', encoding='utf-8') as f:
            naskah = f.read()
        text = normalize_tts_text(naskah)
        if not text:
            print('❌ Naskah kosong.')
            sys.exit(1)

        output_path = os.path.join(output_dir, f'{filename}.wav')

        print()
        print('═' * 64)
        print('📋 Ringkasan:')
        print('═' * 64)
        print(f'  Naskah  : {os.path.basename(naskah_path)}')
        print(f'  Output  : {output_path}')
        print(f'  Voice   : {voice_id}')
        print(f'  Speed   : {speed}')
        print(f'  Chars   : {len(text)}')
        print('═' * 64)
        print()

        confirm = questionary.confirm('Lanjut generate?', default=True).ask()
        if not confirm:
            return

        print()
        print(f'🚀 Generate narration via VoiceStudio...')
        start_time = time.time()

        # Chunk kalau terlalu panjang (VoiceStudio max_chunk_chars default 800)
        CHUNK = 800
        chunks = [text[i:i+CHUNK] for i in range(0, len(text), CHUNK)]
        all_audio = np.array([], dtype=np.float32)

        for ci, chunk in enumerate(chunks):
            print(f'  Chunk {ci+1}/{len(chunks)} ({len(chunk)} chars)...')
            wav_bytes = voicestudio_generate_speech(chunk, voice_id, speed=speed, fmt='wav')
            audio = decode_wav_bytes_to_pcm(wav_bytes, NARR_SAMPLE_RATE)
            audio = trim_silence_asymmetric(audio, NARR_SAMPLE_RATE)
            all_audio = np.concatenate([all_audio, audio])

        encode_wav(all_audio, NARR_SAMPLE_RATE, NARR_CHANNELS, output_path)
        elapsed = time.time() - start_time

        if os.path.isfile(output_path):
            size_mb = os.path.getsize(output_path) / 1024 / 1024
            print()
            print('═' * 64)
            print('✅ SELESAI!')
            print(f'   Output : {output_path}')
            print(f'   Size   : {size_mb:.1f} MB')
            print(f'   Format : {NARR_SAMPLE_RATE}Hz stereo 16-bit PCM (review-mix/konten compatible)')
            print(f'   Voice  : {voice_id}')
            print(f'   Waktu  : {format_duration(elapsed)}')
            print()
            print('🎬 Langkah berikutnya:')
            print(f'   Feed ke review-mix-tui / konten-tui / talkinghead-tui / manim-shorts-tui')
            print('═' * 64)
        else:
            print('❌ Output tidak terbentuk.')

    except KeyboardInterrupt:
        print('\n\n⏹ Dibatalkan user.')
    finally:
        if _ACTIVE_LOCK:
            release_lock(_ACTIVE_LOCK[0], _ACTIVE_LOCK[1])


# ============================================================
# Entry
# ============================================================

if __name__ == '__main__':
    main()
