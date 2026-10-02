# Python Lokal — SRT to Audio (MacBook)

Generate audio dari SRT tanpa browser. Pakai Edge TTS (gratis, native Indonesia/Jawa).

## Install (sekali saja)

```bash
# Install Python 3 (sudah ada di macOS)
python3 --version

# Install dependencies
pip3 install edge-tts numpy

# Cek ffmpeg sudah ada (sudah pre-install di macOS)
ffmpeg -version
```

Kalau `pip3` error, pakai:
```bash
python3 -m pip install edge-tts numpy
```

## Cara Pakai

### Mode ON (sync ke SRT, crossfade)
Audio fit ke cue duration, durasi = SRT, transisi halus (crossfade).
```bash
python3 scripts/srt-to-audio.py subs.srt --on --voice id-ID-GadisNeural
```

### Mode OFF (natural, sequential)
Audio natural alami, utuh 100%, durasi bisa beda dari SRT.
```bash
python3 scripts/srt-to-audio.py subs.srt --off --voice id-ID-GadisNeural
```

### Mode OFF + Speed
Audio natural tapi lebih cepat (pitch tetap natural).
```bash
python3 scripts/srt-to-audio.py subs.srt --off --voice id-ID-GadisNeural --speed 1.5
```

### Mode ON + Speed Mode
```bash
# Speed up and slow down (audio selalu fit ke cue)
python3 scripts/srt-to-audio.py subs.srt --on --voice id-ID-GadisNeural --speed-mode slowdown

# Speed up only (kalau audio lebih pendek, biarkan silence)
python3 scripts/srt-to-audio.py subs.srt --on --voice id-ID-GadisNeural --speed-mode speedup
```

## Voice yang Tersedia

| Voice | Bahasa | Gender |
|-------|--------|--------|
| `id-ID-GadisNeural` | Indonesia | Perempuan |
| `id-ID-ArdiNeural` | Indonesia | Laki-laki |
| `jv-ID-SitiNeural` | Jawa | Perempuan |
| `jv-ID-DimasNeural` | Jawa | Laki-laki |

Lihat semua voice: `python3 -c "import edge_tts; import asyncio; asyncio.run(edge_tts.list_voices())" | grep -i "id\|jv"`

## Output

File output: `input-audio.wav` (sama folder dengan input)
- Format: WAV 24kHz mono 16-bit PCM
- Siap di-mux ke video dengan ffmpeg

## Mux ke Video (opsional)

```bash
ffmpeg -i video.mp4 -i subs-audio.wav -c:v copy -c:a aac -map 0:v -map 1:a output.mp4
```

## Contoh Lengkap

```bash
# 1. Generate audio dari SRT Jawa
python3 scripts/srt-to-audio.py Season-1-jw-fixed.srt --on --voice jv-ID-SitiNeural

# 2. Mux ke video
ffmpeg -i video.mp4 -i Season-1-jw-fixed-audio.wav -c:v copy -c:a aac -map 0:v -map 1:a output-jawa.mp4
```
