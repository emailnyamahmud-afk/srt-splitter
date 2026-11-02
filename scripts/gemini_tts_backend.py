#!/usr/bin/env python3
"""
gemini_tts_backend.py v1.0 — Backend Gemini TTS untuk gemini-tts-tui.py

Panggilan ke Google Gemini API (legacy endpoint generate_content_stream),
model gemini-3.8-flash-tts. Compatible 100% dengan kode yang user tes di
AI Studio (format prompt [INSTRUCTION] + [TEXT TO READ], PrebuiltVoiceConfig).

API:
  - Menggunakan client.models.generate_content_stream() (API LEGACY)
  - Format prompt: ## Transcript + [INSTRUCTION] + [TEXT TO READ]
  - Output: audio/L16;rate=24000 (raw PCM 16-bit 24kHz mono) → di-bungkus jadi WAV
  - Retry 429 / RESOURCE_EXHAUSTED dengan backoff (sama pola dengan edge-tts 429 retry)

Katalog voice: 30 prebuilt voice resmi Google + "Cruz" (Extended Voice Library,
yang user tes untuk Jawa halus — work, walau bukan di 30 resmi).

Install:
  pip3 install google-genai numpy

Env:
  GEMINI_API_KEY  — wajib. Dapatkan di https://aistudio.google.com/apikey
                    (free tier tersedia, ~5-15 RPM, ~100-250 RPD untuk preview model)

Usage (sebagai modul):
  from gemini_tts_backend import generate_cue_tts, GEMINI_VOICES, DEFAULT_INSTRUCTION_JAWA_HALUS

  ok = generate_cue_tts(
      text="Nuwun, kula nuwun.",
      voice="Cruz",
      instruction="Pria dewasa matang, tempo lambat, khidmat.",
      output_mp3="/path/to/cue-001.mp3",   # sebenarnya WAV (extension .mp3 utk compat dgn cache edge-tts-tui pattern)
      cue_idx=1,
  )

Usage (CLI standalone):
  export GEMINI_API_KEY=...
  python3 gemini_tts_backend.py "Nuwun, kula nuwun." --voice Cruz -o nuwun.wav
  python3 gemini_tts_backend.py --list-voices
"""

from __future__ import annotations

import argparse
import asyncio
import mimetypes
import os
import struct
import subprocess
import sys
import tempfile
import time
from typing import Optional

# Lazy import — supaya --list-voices dan --help jalan tanpa SDK terinstall.
genai = None
types = None
np = None


def _ensure_genai():
    global genai, types
    if genai is not None:
        return
    try:
        from google import genai as _genai
        from google.genai import types as _types
        genai = _genai
        types = _types
    except ImportError:
        print("Install google-genai: pip3 install google-genai", file=sys.stderr)
        sys.exit(1)


def _ensure_numpy():
    global np
    if np is not None:
        return
    try:
        import numpy as _np
        np = _np
    except ImportError:
        print("Install numpy: pip3 install numpy", file=sys.stderr)
        sys.exit(1)


# ============================================================
# Constants — match edge-tts-tui.py untuk kompatibilitas mix-tui.py
# ============================================================

OUTPUT_SAMPLE_RATE = 24000  # match edge-tts-tui + web app
OUTPUT_CHANNELS = 1
OUTPUT_BITS = 16

MODEL = "gemini-3.8-flash-tts"

# 429 / RESOURCE_EXHAUSTED backoff (detik). Sama pola dengan edge-tts-tui.py v7.4
# Kalau Gemini API rate-limit, backoff 30s → 60s → 120s → skip.
RATE_LIMIT_BACKOFF = [30, 60, 120]


# ============================================================
# Katalog voice + instruction templates
# ============================================================

# 30 PREBUILT VOICE RESMI Google (per docs Sept 2026) — label deskripsi dari Google.
# Gender: P (Pria) / W (Wanita) / ? (Netral) — PERKIRAAN komunitas, bukan label resmi.
# Format: ("voice_name", "label", gender_hint, is_official)
GEMINI_VOICES = [
    # === Pria ===
    ("Puck",           "Puck — Upbeat, pria energik",                       "P", True),
    ("Charon",         "Charon — Informative, pria tenang/informatif",      "P", True),
    ("Fenrir",         "Fenrir — Excitable, pria dinamis",                  "P", True),
    ("Orus",           "Orus — Firm, pria tegas",                           "P", True),
    ("Enceladus",      "Enceladus — Breathy, pria breathy",                 "P", True),
    ("Iapetus",        "Iapetus — Clear, pria jelas",                      "P", True),
    ("Umbriel",        "Umbriel — Easy-going, pria santai",                "P", True),
    ("Algenib",        "Algenib — Gravelly, pria kasar",                    "P", True),
    ("Rasalgethi",    "Rasalgethi — Informative, pria informatif",          "P", True),
    ("Achernar",      "Achernar — Soft, pria lembut",                       "P", True),
    ("Alnilam",       "Alnilam — Firm, pria tegas mantap",                  "P", True),
    ("Schedar",       "Schedar — Even, pria stabil datar",                 "P", True),
    ("Zubenelgenubi", "Zubenelgenubi — Casual, pria santai",                "P", True),
    ("Sadachbia",     "Sadachbia — Lively, pria hidup",                     "P", True),
    ("Sadaltager",    "Sadaltager — Knowledgeable, pria berwibawa",        "P", True),
    # === Wanita ===
    ("Kore",           "Kore — Firm, wanita tegas",                         "W", True),
    ("Leda",           "Leda — Youthful, wanita muda",                      "W", True),
    ("Aoede",          "Aoede — Breezy, wanita segar",                     "W", True),
    ("Callirrhoe",     "Callirrhoe — Easy-going, wanita santai",            "W", True),
    ("Autonoe",        "Autonoe — Bright, wanita cerah",                   "W", True),
    ("Algieba",        "Algieba — Smooth, wanita halus",                    "W", True),
    ("Despina",        "Despina — Smooth, wanita halus",                    "W", True),
    ("Erinome",        "Erinome — Clear, wanita jelas",                     "W", True),
    ("Laomedeia",     "Laomedeia — Upbeat, wanita ceria",                  "W", True),
    ("Gacrux",         "Gacrux — Mature, wanita matang",                    "W", True),
    ("Pulcherrima",   "Pulcherrima — Forward, wanita maju",                 "W", True),
    ("Achird",         "Achird — Friendly, wanita ramah",                    "W", True),
    ("Vindemiatrix",  "Vindemiatrix — Gentle, wanita lembut",                "W", True),
    ("Sulafat",        "Sulafat — Warm, wanita hangat",                      "W", True),
    # === Netral ===
    ("Zephyr",         "Zephyr — Bright, netral cerah",                     "?", True),
    # === Extended (bukan di 30 resmi, tapi tested OK untuk Jawa) ===
    ("Cruz",           "Cruz — (Extended Library) pria dewasa hangat, TESTED untuk Jawa halus MC/adat", "P", False),
]

# Default voice — Cruz karena itu yang sudah user tes & hasilnya bagus di Jawa halus.
DEFAULT_VOICE = "Cruz"

# Default instruction: cukup netral, biar voice + instruction custom yang ngatur gaya.
DEFAULT_INSTRUCTION = (
    "Bacakan teks berikut secara natural, jelas, dengan artikulasi baik "
    "dan jeda napas yang pas pada tanda baca koma dan titik."
)

# Template instruksi yang sering dipakai di pipeline dubbing.
# Format: (key, label, instruction_text)
INSTRUCTION_TEMPLATES = [
    ("default",       "Default (natural, netral)",
     "Bacakan teks berikut secara natural, jelas, dengan artikulasi baik dan jeda napas yang pas pada tanda baca koma dan titik."),
    ("jawa-halus-mc", "Jawa halus — Panatacara / MC adat (pria berwibawa)",
     "Karakter Suara: Pria dewasa matang (usia sekitar 40-50 tahun), suara berat berwibawa (baritone), penutur asli bahasa Jawa halus. "
     "Gaya Bicara: Berperan sebagai \"Panatacara / Pranatacara Pamedhar Sabda\" profesional untuk acara resmi/adat Jawa. "
     "Tempo: Lambat, tenang, khidmat, dengan artikulasi vokal dan konsonan Jawa (seperti \"dha\", \"tha\", \"nga\") yang sangat jelas dan medok mantap. "
     "Berikan jeda napas yang pas dan anggun di setiap tanda koma dan titik."),
    ("id-narasi",     "Indonesia — narasi dokumenter (pria hangat)",
     "Karakter Suara: Pria dewasa hangat (usia 30-40 tahun), penutur asli bahasa Indonesia. "
     "Gaya Bicara: Narator dokumenter yang tenang, mengalir, dan menjaga jarak emosional. "
     "Tempo: Sedang, dengan artikulasi jelas dan jeda napas yang pas pada tanda baca."),
    ("id-narasi-w",   "Indonesia — narasi dokumenter (wanita hangat)",
     "Karakter Suara: Wanita dewasa hangat (usia 30-40 tahun), penutur asli bahasa Indonesia. "
     "Gaya Bicara: Narator dokumenter yang tenang, mengalir, dan menjaga jarak emosional. "
     "Tempo: Sedang, dengan artikulasi jelas dan jeda napas yang pas pada tanda baca."),
    ("id-dialog",     "Indonesia — dialog dramatis (natural)",
     "Karakter Suara: Penutur asli bahasa Indonesia, suara natural. "
     "Gaya Bicara: Dialog film/drama, bawa emosi sesuai konteks kalimat, tidak terlalu teatrikal. "
     "Tempo: Natural mengikuti pola percakapan, jeda napas mengikuti tanda baca."),
    ("custom",        "Custom (ketik sendiri)",
     None),  # None = minta user ketik
]


# ============================================================
# Util internal: prompt builder + WAV header
# ============================================================

def _build_prompt(text: str, instruction: str) -> str:
    """Format prompt resmi Gemini TTS: header + [INSTRUCTION] + [TEXT TO READ]."""
    return f"""## Transcript:
[INSTRUCTION]
{instruction}

[TEXT TO READ]
{text}"""


def _parse_audio_mime_type(mime_type: str) -> dict:
    """Ekstrak bits_per_sample dan rate dari MIME seperti 'audio/L16;rate=24000'."""
    bits_per_sample = 16
    rate = OUTPUT_SAMPLE_RATE
    for param in mime_type.split(";"):
        param = param.strip()
        if param.lower().startswith("rate="):
            try:
                rate = int(param.split("=", 1)[1])
            except (ValueError, IndexError):
                pass
        elif param.startswith("audio/L"):
            try:
                bits_per_sample = int(param.split("L", 1)[1])
            except (ValueError, IndexError):
                pass
    return {"bits_per_sample": bits_per_sample, "rate": rate}


def _pcm_to_wav(audio_data: bytes, mime_type: str) -> bytes:
    """Bungkus raw PCM (audio/L16) jadi WAV 16-bit mono."""
    p = _parse_audio_mime_type(mime_type)
    bits_per_sample = p["bits_per_sample"]
    sample_rate = p["rate"]
    num_channels = 1
    data_size = len(audio_data)
    bytes_per_sample = bits_per_sample // 8
    block_align = num_channels * bytes_per_sample
    byte_rate = sample_rate * block_align
    chunk_size = 36 + data_size
    header = struct.pack(
        "<4sI4s4sIHHIIHH4sI",
        b"RIFF", chunk_size, b"WAVE",
        b"fmt ", 16, 1, num_channels,
        sample_rate, byte_rate, block_align, bits_per_sample,
        b"data", data_size,
    )
    return header + audio_data


def _rate_to_instruction(rate: str, base_instruction: str) -> str:
    """Terjemahkan rate Edge-TTS-style ('+20%', '-10%') jadi instruksi tempo.

    Gemini TTS API legacy tidak punya parameter rate langsung. Tempo dikendalikan
    via instruksi di prompt. Ini pendekatan yang sama dengan edge-tts-tui.py Smart Fit
    (re-generate dengan rate beda), cuma beda mekanisme pass-nya.
    """
    if not rate or rate == "+0%":
        return base_instruction
    pct_str = rate.replace("%", "").replace("+", "")
    try:
        pct = int(pct_str)
    except ValueError:
        return base_instruction
    if pct == 0:
        return base_instruction
    if pct > 0:
        return base_instruction + f" Bicara sekitar {pct} persen lebih cepat dari tempo normal."
    else:
        return base_instruction + f" Bicara sekitar {abs(pct)} persen lebih lambat dari tempo normal."


def _format_rate_instruction(ratio: float) -> str:
    """Format rate instruction dari rasio (mirip format_edge_rate di edge-tts-tui).

    ratio > 1.0 = perlu cepat (audio lebih panjang dari cue)
    ratio < 1.0 = perlu lambat (audio lebih pendek dari cue, jarang dipakai)
    """
    if abs(ratio - 1.0) < 0.05:
        return "+0%"
    pct = round((ratio - 1.0) * 100)
    return f"+{pct}%" if pct >= 0 else f"{pct}%"


# ============================================================
# Inti: panggil Gemini TTS dan decode ke WAV bytes
# ============================================================

def _generate_wav_bytes_sync(
    text: str,
    voice: str,
    instruction: str,
    temperature: float,
    model: str,
    api_key: str,
) -> bytes:
    """Panggil API Gemini TTS streaming, kembalikan WAV bytes (16-bit mono 24kHz)."""
    _ensure_genai()
    client = genai.Client(api_key=api_key)

    prompt = _build_prompt(text, instruction)
    contents = [types.Content(
        role="user",
        parts=[types.Part.from_text(text=prompt)],
    )]
    config = types.GenerateContentConfig(
        temperature=temperature,
        response_modalities=["audio"],
        speech_config=types.SpeechConfig(
            voice_config=types.VoiceConfig(
                prebuilt_voice_config=types.PrebuiltVoiceConfig(
                    voice_name=voice
                )
            )
        ),
    )

    audio_data = bytearray()
    mime_type = ""

    for chunk in client.models.generate_content_stream(
        model=model,
        contents=contents,
        config=config,
    ):
        if chunk.parts is None:
            continue
        if chunk.parts[0].inline_data and chunk.parts[0].inline_data.data:
            inline = chunk.parts[0].inline_data
            audio_data.extend(inline.data)
            mime_type = inline.mime_type
        else:
            if t := chunk.text:
                print(f"  [gemini-tts] text chunk: {t}", file=sys.stderr)

    if not audio_data:
        raise RuntimeError("Gemini TTS mengembalikan audio kosong")

    # MIME 'audio/L16;rate=24000' tidak punya ekstensi standar → bungkus jadi WAV
    file_ext = mimetypes.guess_extension(mime_type) if mime_type else None
    if file_ext is None:
        return _pcm_to_wav(bytes(audio_data), mime_type or "audio/L16;rate=24000")
    return bytes(audio_data)


def _decode_wav_to_pcm(wav_bytes: bytes, target_sr: int = OUTPUT_SAMPLE_RATE):
    """Decode WAV bytes → np.float32 mono 24kHz via ffmpeg (sama pipeline edge_tts)."""
    _ensure_numpy()
    tmp = tempfile.NamedTemporaryFile(suffix='.wav', delete=False)
    tmp.write(wav_bytes)
    tmp.close()
    try:
        result = subprocess.run(
            ['ffmpeg', '-i', tmp.name,
             '-f', 's16le', '-ar', str(target_sr), '-ac', '1', '-'],
            capture_output=True, timeout=120
        )
        if result.returncode != 0:
            raise RuntimeError(f"ffmpeg error: {result.stderr.decode()[:200]}")
        return np.frombuffer(result.stdout, dtype=np.int16).astype(np.float32) / 32768.0
    finally:
        os.unlink(tmp.name)


def _encode_wav_file(samples, sample_rate: int, output_path: str):
    """Encode np.float32 → 16-bit PCM WAV file (untuk cache per-cue)."""
    _ensure_numpy()
    samples = np.clip(samples, -1.0, 1.0)
    pcm = (samples * 32767).astype(np.int16)
    header = struct.pack(
        '<4sI4s4sIHHIIHH4sI',
        b'RIFF', 36 + len(pcm) * 2, b'WAVE',
        b'fmt ', 16, 1, 1, sample_rate, sample_rate * 2, 2, 16,
        b'data', len(pcm) * 2
    )
    with open(output_path, 'wb') as f:
        f.write(header + pcm.tobytes())


# ============================================================
# Public API: generate_cue_tts — drop-in replacement untuk edge-tts generate_cue_tts
# ============================================================

def generate_cue_tts(
    text: str,
    voice: str,
    rate: str,
    instruction: str,
    output_mp3: str,
    cue_idx: int = 0,
    temperature: float = 1.0,
    model: str = MODEL,
) -> bool:
    """Generate 1 cue via Gemini TTS → save ke output_mp3 (sebenarnya WAV 16-bit mono 24kHz).

    Output format: WAV (WAV header + PCM). File extension pakai .mp3 untuk kompatibilitas
    dengan pola cache edge-tts-tui.py (yang menulis MP3) — agar mix-tui.py dan cache
    mechanism tetap konsisten. Decoder ffmpeg handle keduanya.

    v1.0 retry: auto-retry kalau kena 429 / RESOURCE_EXHAUSTED.
    Backoff: 30s → 60s → 120s → skip + log.

    Return True kalau sukses, False kalau gagal setelah retry.
    """
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print(f"  ⚠ GEMINI_API_KEY belum di-set (cue {cue_idx})", file=sys.stderr)
        return False

    final_instruction = _rate_to_instruction(rate, instruction)

    last_error = None
    for attempt in range(len(RATE_LIMIT_BACKOFF) + 1):
        try:
            # Jalankan blocking Gemini call (async-friendly via asyncio.to_thread)
            wav_bytes = asyncio.run(_generate_wav_bytes_sync_async(
                text, voice, final_instruction, temperature, model, api_key,
            ))
            if not wav_bytes:
                raise RuntimeError("output WAV kosong")

            # Decode WAV → numpy float32 (mono 24kHz)
            samples = _decode_wav_to_pcm(wav_bytes, OUTPUT_SAMPLE_RATE)
            if len(samples) == 0:
                raise RuntimeError("decode WAV menghasilkan audio kosong")

            # Encode ulang ke WAV file di output_mp3 (cache compatible pattern)
            _encode_wav_file(samples, OUTPUT_SAMPLE_RATE, output_mp3)
            if os.path.isfile(output_mp3) and os.path.getsize(output_mp3) > 0:
                return True
            raise RuntimeError("output file tidak terbentuk / kosong")

        except Exception as e:
            last_error = e
            err_str = str(e).lower()
            # Detect rate limit (429, RESOURCE_EXHAUSTED, quota, throttle)
            is_rate_limit = (
                '429' in err_str or
                'resource_exhausted' in err_str or
                'rate limit' in err_str or
                'quota' in err_str or
                'too many requests' in err_str or
                'throttle' in err_str
            )
            if not is_rate_limit:
                # Bukan rate limit → jangan retry, langsung fail
                print(f"  ⚠ Gemini TTS gagal cue {cue_idx}: {e}", file=sys.stderr)
                return False
            # Rate limit → retry dengan backoff
            if attempt < len(RATE_LIMIT_BACKOFF):
                wait_s = RATE_LIMIT_BACKOFF[attempt]
                print(f"  ⏸ Cue {cue_idx} kena rate limit (429/RESOURCE_EXHAUSTED). "
                      f"Tunggu {wait_s}s, retry {attempt+1}/{len(RATE_LIMIT_BACKOFF)}...",
                      file=sys.stderr)
                time.sleep(wait_s)
                continue
            else:
                print(f"  ⚠ Gemini TTS gagal cue {cue_idx} setelah {len(RATE_LIMIT_BACKOFF)} retry: {last_error}",
                      file=sys.stderr)
                return False

    print(f"  ⚠ Gemini TTS gagal cue {cue_idx}: {last_error}", file=sys.stderr)
    return False


async def _generate_wav_bytes_sync_async(*args):
    """Wrapper async untuk _generate_wav_bytes_sync (jalankan di thread pool)."""
    return await asyncio.to_thread(_generate_wav_bytes_sync, *args)


# ============================================================
# CLI standalone (untuk test cepat, bukan untuk pipeline production)
# ============================================================

def _print_voices():
    print("\nPrebuilt voices untuk gemini-3.8-flash-tts:")
    print("-" * 100)
    print(f"  {'Voice':18s} {'G':2s} {'O':2s}  Deskripsi (G=Gender, O=Official30)")
    print("-" * 100)
    for name, label, gender, is_official in GEMINI_VOICES:
        o_mark = "✓" if is_official else "-"
        default_tag = "  ← default" if name == DEFAULT_VOICE else ""
        print(f"  {name:18s} {gender:2s} {o_mark:2s}  {label}{default_tag}")
    print("-" * 100)
    print("G = Gender: P=Pria, W=Wanita, ?=Netral (PERKIRAAN komunitas — bukan label resmi Google)")
    print("O = Official: ✓ = bagian dari 30 prebuilt voice resmi Google")
    print()
    print("Saran pemilihan voice untuk Jawa halus MC/adat (pria berwibawa):")
    print("  1. Cruz       ← default, yg sudah kamu tes (work, walau bukan di 30 resmi)")
    print("  2. Charon     ← Informative, pria, tenang")
    print("  3. Schedar    ← Even, pria, stabil")
    print("  4. Alnilam    ← Firm, pria, tegas")
    print("  5. Rasalgethi ← Informative, pria")
    print()


def _print_instructions():
    print("\nInstruction templates yang tersedia di gemini-tts-tui.py:")
    print("-" * 80)
    for key, label, _ in INSTRUCTION_TEMPLATES:
        print(f"  {key:18s} — {label}")
    print("-" * 80)
    print()


def main():
    parser = argparse.ArgumentParser(
        description='gemini_tts_backend.py — Backend Gemini TTS untuk 1 cue (standalone test)'
    )
    parser.add_argument('text', nargs='?', default=None,
                        help='Teks yang akan dibacakan')
    parser.add_argument('-o', '--output', default='./output.wav',
                        help='Output WAV file (default: ./output.wav)')
    parser.add_argument('--voice', default=DEFAULT_VOICE,
                        help=f'Prebuilt voice (default: {DEFAULT_VOICE})')
    parser.add_argument('--rate', default='+0%',
                        help='Tempo "+0%%", "+20%%", "-10%%" (di-pass via instruksi)')
    parser.add_argument('--instruction', default=DEFAULT_INSTRUCTION,
                        help='Instruksi gaya bicara (lebih panjang = lebih spesifik)')
    parser.add_argument('--temperature', type=float, default=1.0,
                        help='Kreativitas suara (default 1.0)')
    parser.add_argument('--model', default=MODEL,
                        help=f'Gemini TTS model (default: {MODEL})')
    parser.add_argument('--list-voices', action='store_true',
                        help='Tampilkan daftar voice lalu keluar')
    parser.add_argument('--list-instructions', action='store_true',
                        help='Tampilkan daftar instruction template lalu keluar')
    args = parser.parse_args()

    if args.list_voices:
        _print_voices()
        return
    if args.list_instructions:
        _print_instructions()
        return
    if not args.text:
        parser.error("text wajib (atau pakai --list-voices / --list-instructions)")

    if not os.environ.get("GEMINI_API_KEY"):
        print("ERROR: Set GEMINI_API_KEY dulu. Dapatkan di https://aistudio.google.com/apikey",
              file=sys.stderr)
        sys.exit(1)

    print(f"[gemini-tts-backend] voice={args.voice}  rate={args.rate}  temp={args.temperature}")
    print(f"[gemini-tts-backend] text: {args.text[:80]}{'...' if len(args.text)>80 else ''}")

    ok = generate_cue_tts(
        args.text, voice=args.voice, rate=args.rate,
        instruction=args.instruction, output_mp3=args.output,
        cue_idx=1, temperature=args.temperature, model=args.model,
    )
    if not ok:
        print("ERROR: gagal generate.", file=sys.stderr)
        sys.exit(1)

    if not os.path.isfile(args.output):
        print(f"ERROR: file tidak terbentuk: {args.output}", file=sys.stderr)
        sys.exit(1)

    print(f"\nDone! Output: {args.output}")
    print(f"Size: {os.path.getsize(args.output) / 1024:.1f} KB")
    print(f"Voice: {args.voice}")


if __name__ == '__main__':
    main()
