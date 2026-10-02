#!/usr/bin/env python3
"""
SRT to Audio — Python Lokal untuk MacBook
Generate audio dari SRT dengan Edge TTS (gratis, native Indonesia/Jawa).
Tanpa browser, tanpa server. 100% lokal.

Mode:
  ON  (--on)  : Audio fit ke cue duration (crossfade, durasi = SRT)
  OFF (--off) : Audio natural alami (sequential, utuh 100%)

Install:
  pip3 install edge-tts numpy

Usage:
  python3 srt-to-audio.py input.srt --on --voice id-ID-GadisNeural
  python3 srt-to-audio.py input.srt --off --voice jv-ID-SitiNeural --speed 1.5
"""

import argparse
import asyncio
import re
import struct
import sys
import os
from pathlib import Path

try:
    import edge_tts
except ImportError:
    print("Install edge-tts: pip3 install edge-tts")
    sys.exit(1)

try:
    import numpy as np
except ImportError:
    print("Install numpy: pip3 install numpy")
    sys.exit(1)


# === SRT PARSER ===

def parse_srt(filepath):
    """Parse SRT file → list of (index, start, end, text)."""
    with open(filepath, 'r', encoding='utf-8-sig') as f:
        content = f.read().strip()
    blocks = re.split(r'\n\s*\n', content)
    entries = []
    for block in blocks:
        lines = block.split('\n')
        if len(lines) < 2:
            continue
        # Find timestamp line
        time_line = None
        text_start = 0
        for i, line in enumerate(lines):
            if '-->' in line:
                time_line = line
                text_start = i + 1
                break
        if not time_line:
            continue
        # Parse timestamps
        m = re.match(r'(\d+):(\d+):(\d+)[,.](\d+)\s*-->\s*(\d+):(\d+):(\d+)[,.](\d+)', time_line)
        if not m:
            continue
        start = int(m[1]) * 3600 + int(m[2]) * 60 + int(m[3]) + int(m[4]) / 1000
        end = int(m[5]) * 3600 + int(m[6]) * 60 + int(m[7]) + int(m[8]) / 1000
        text = '\n'.join(lines[text_start:]).strip()
        entries.append((len(entries) + 1, start, end, text))
    return entries


# === EDGE TTS ===

async def generate_tts(text, voice, rate='+0%'):
    """Generate audio via Edge TTS, return numpy array (mono 24kHz)."""
    import tempfile
    tmp = tempfile.NamedTemporaryFile(suffix='.mp3', delete=False)
    tmp.close()
    try:
        communicate = edge_tts.Communicate(text, voice, rate=rate)
        await communicate.save(tmp.name)
        # Read MP3 and decode with ffmpeg
        import subprocess
        result = subprocess.run(
            ['ffmpeg', '-i', tmp.name, '-f', 's16le', '-ar', '24000', '-ac', '1', '-'],
            capture_output=True, timeout=30
        )
        if result.returncode != 0:
            print(f"  ffmpeg error: {result.stderr.decode()[:200]}", file=sys.stderr)
            return np.zeros(0, dtype=np.float32)
        # Convert bytes to float32
        audio_bytes = result.stdout
        samples = np.frombuffer(audio_bytes, dtype=np.int16).astype(np.float32) / 32768.0
        return samples
    finally:
        os.unlink(tmp.name)


# === CROSSFADE ===

def apply_fade_out(audio, fade_start, fade_end):
    """Linear fade out."""
    fade_end = min(fade_end, len(audio))
    if fade_end <= fade_start:
        return
    t = np.linspace(1.0, 0.0, fade_end - fade_start)
    audio[fade_start:fade_end] *= t


def apply_fade_in(audio, fade_start, fade_end):
    """Linear fade in."""
    fade_end = min(fade_end, len(audio))
    if fade_end <= fade_start:
        return
    t = np.linspace(0.0, 1.0, fade_end - fade_start)
    audio[fade_start:fade_end] *= t


def mix_into(buffer, audio, position):
    """Mix (ADD) audio into buffer at position."""
    end_pos = min(position + len(audio), len(buffer))
    copy_len = end_pos - position
    if copy_len <= 0:
        return
    buffer[position:end_pos] += audio[:copy_len]


# === WAV ENCODER ===

def encode_wav(samples, sample_rate=24000):
    """Encode numpy float32 to 16-bit WAV bytes."""
    samples = np.clip(samples, -1.0, 1.0)
    pcm = (samples * 32767).astype(np.int16)
    header = struct.pack('<4sI4s4sIHHIIHH4sI',
        b'RIFF', 36 + len(pcm) * 2, b'WAVE',
        b'fmt ', 16, 1, 1, sample_rate, sample_rate * 2, 2, 16,
        b'data', len(pcm) * 2
    )
    return header + pcm.tobytes()


# === MAIN PIPELINE ===

async def process_srt(filepath, voice, mode_on, speed_mode, off_speed):
    entries = parse_srt(filepath)
    if not entries:
        print("Tidak ada subtitle valid.")
        return
    print(f"Total: {len(entries)} baris subtitle")
    print(f"Voice: {voice}")
    print(f"Mode: {'ON (sync ke SRT, crossfade)' if mode_on else 'OFF (natural, sequential)'}")
    if not mode_on and off_speed != 1.0:
        print(f"Speed: {off_speed}x")
    print()

    sample_rate = 24000
    segments = []  # (position, audio, cue_start, cue_end)
    total_duration = entries[-1][2]

    for i, (idx, start, end, text) in enumerate(entries):
        if not text.strip():
            continue
        print(f"\r[{i+1}/{len(entries)}] \"{text[:50]}{'...' if len(text)>50 else ''}\"", end='', flush=True)

        if mode_on:
            # === ON MODE: two-pass + crossfade ===
            cue_dur = end - start
            # Pass 1: natural
            audio1 = await generate_tts(text, voice, rate='+0%')
            if len(audio1) == 0:
                print(f"  SKIP (empty audio)", file=sys.stderr)
                continue
            actual_dur = len(audio1) / sample_rate

            if abs(actual_dur - cue_dur) < 0.05:
                # Close enough, use natural
                final_audio = audio1
            elif actual_dur > cue_dur:
                # Need speed up
                ratio = actual_dur / cue_dur
                rate_pct = round((ratio - 1) * 100)
                rate_str = f"+{rate_pct}%" if rate_pct >= 0 else f"{rate_pct}%%"
                final_audio = await generate_tts(text, voice, rate=rate_str)
            elif speed_mode == 'slowdown' and actual_dur < cue_dur:
                # Need slow down
                ratio = actual_dur / cue_dur
                rate_pct = round((ratio - 1) * 100)
                rate_str = f"{rate_pct}%"
                final_audio = await generate_tts(text, voice, rate=rate_str)
            else:
                # speedup-only + audio shorter → use natural
                final_audio = audio1

            position = int(start * sample_rate)
            cue_start = int(start * sample_rate)
            cue_end = int(end * sample_rate)
        else:
            # === OFF MODE: natural + optional speed ===
            rate_str = '+0%'
            if off_speed != 1.0:
                rate_pct = round((off_speed - 1) * 100)
                rate_str = f"+{rate_pct}%" if rate_pct >= 0 else f"{rate_pct}%"
            final_audio = await generate_tts(text, voice, rate=rate_str)
            if len(final_audio) == 0:
                continue
            # Sequential position
            if segments:
                position = segments[-1][0] + len(segments[-1][1]) + int(0.3 * sample_rate)
            else:
                position = 0
            cue_start = 0
            cue_end = 0

        segments.append((position, final_audio, cue_start, cue_end))

    print()
    print(f"\nStitching + crossfade...")

    # Calculate total length
    if mode_on:
        total_samples = int(total_duration * sample_rate)
    else:
        total_samples = max((s[0] + len(s[1]) for s in segments), default=0)

    all_audio = np.zeros(total_samples, dtype=np.float32)

    for i, (position, audio, cue_start, cue_end) in enumerate(segments):
        # Crossfade: if ON mode and audio extends beyond cue_end
        if mode_on and cue_end > 0:
            next_seg = segments[i + 1] if i + 1 < len(segments) else None
            if next_seg:
                overlap_start = cue_end
                overlap_end = min(position + len(audio), next_seg[0] + 100)
                if overlap_end > overlap_start and position + len(audio) > overlap_start:
                    fade_start = overlap_start - position
                    fade_end = min(len(audio), overlap_end - position)
                    if fade_end > fade_start:
                        apply_fade_out(audio, fade_start, fade_end)
                    # Fade in next segment
                    next_audio = next_seg[1]
                    fade_in_end = min(len(next_audio), fade_end - fade_start)
                    if fade_in_end > 0:
                        apply_fade_in(next_audio, 0, fade_in_end)

        mix_into(all_audio, audio, position)

    # Write WAV
    output = filepath.rsplit('.', 1)[0] + '-audio.wav'
    wav_bytes = encode_wav(all_audio, sample_rate)
    with open(output, 'wb') as f:
        f.write(wav_bytes)

    duration = len(all_audio) / sample_rate
    print(f"\nDone! Output: {output}")
    print(f"Duration: {int(duration//60)}m {int(duration%60)}s")
    print(f"File size: {len(wav_bytes) / 1024 / 1024:.1f} MB")


def main():
    parser = argparse.ArgumentParser(description='SRT to Audio — Python Lokal (Edge TTS)')
    parser.add_argument('input', help='File SRT input')
    parser.add_argument('--voice', default='id-ID-GadisNeural',
                        help='Voice (default: id-ID-GadisNeural)')
    parser.add_argument('--on', action='store_true', dest='mode_on',
                        help='ON mode: sync ke SRT, crossfade (durasi = SRT)')
    parser.add_argument('--off', action='store_false', dest='mode_on',
                        help='OFF mode: natural, sequential (default)')
    parser.add_argument('--speed-mode', default='slowdown', choices=['speedup', 'slowdown'],
                        help='ON mode: speedup only atau speedup+slowdown (default: slowdown)')
    parser.add_argument('--speed', type=float, default=1.0,
                        help='OFF mode: kecepatan 1.0/1.25/1.5/2.0 (default: 1.0)')
    parser.set_defaults(mode_on=False)

    args = parser.parse_args()

    if not Path(args.input).exists():
        print(f"File tidak ditemukan: {args.input}")
        sys.exit(1)

    asyncio.run(process_srt(
        args.input, args.voice, args.mode_on, args.speed_mode, args.speed
    ))


if __name__ == '__main__':
    main()
