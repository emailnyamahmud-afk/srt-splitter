# Scripts — SRT Splitter + Dubbing

Python TUI untuk workflow dubbing + kamus Jawa.

## 7 TUI — Status (24 Okt 2026)

| # | TUI | Status | Test |
|---|-----|--------|------|
| 1 | yt-dlp-tui.py | ✅ Production | 5+ film tested |
| 2 | demucs-tui.py | ✅ Production | Kepala-Perampok ~32 menit |
| 3 | kamus-tui.py (v16) | ✅ Production (audit) | 8.618 entries terbaca |
| 4 | Web app | ⚠ Prototype | Live di Vercel |
| 5 | SRT editor | ⏳ Pending | Pakai SRT Indonesia sementara |
| 6 | edge-tts-tui.py | ✅ Production | 4565 cue tested |
| 7 | mix-tui.py v3.5 | ✅ Production-ready | A,C,D tested |

## Pipeline (2 alur produksi)

### Simple mode — cepat, dialog dominan

```
yt-dlp-tui.py → edge-tts-tui.py → mix-tui.py (Mode C/D)
→ ~350 MB stream copy / ~1.2-2.3 GB burn SRT
→ sync 1000000%, tidak perlu DaVinci Resolve
```

Cocok untuk: preview cepat, film dialog dominan, audio dub Jawa yang sudah clean.

### Full mode — proper, dengan SFX

```
yt-dlp-tui.py → demucs-tui.py → edge-tts-tui.py → mix-tui.py (Mode A/B)
→ ~350 MB stream copy / ~1.2-4.5 GB burn SRT
→ dengan ducking sidechain, musik latar tetap ada
```

Cocok untuk: film action, musik latar penting, produksi "proper".

## Scripts

### Pipeline

| Script | Fungsi | Output |
|--------|--------|--------|
| yt-dlp-tui.py | Download video/audio + SRT Indonesia | HDD/input/ |
| demucs-tui.py | Vocal separation (M1 MPS, segment RAM aman) | HDD/demucs/ |
| edge-tts-tui.py | TTS generation (100% lokal, 5000+ cue) | HDD/tts/ |
| mix-tui.py v3.5 | Final mix video (4 mode + pilihan bitrate) | HDD/mix/ |

### Kamus

| Script | Fungsi |
|--------|--------|
| kamus-tui.py (v16) | TUI editor jv.wiktionary.json |
| config.py | Base path SSD/HDD + ensure_hdd/kamus + load_env |
| upload-supabase.py | Upload kamus terverifikasi ke Supabase |
| parse-jv-wiktionary-v2.py | Parser jv.wiktionary XML dump |
| srt-frequency-analyzer.py | Analisis frekuensi kata SRT |

### Tutor

| File | Isi |
|------|-----|
| tutor-demucs-setup.md | Setup Demucs M1 MPS |

## mix-tui v3.5 — 4 mode

| # | Mode Input | Mode Output | Output filename | Durasi | Size (2jam) |
|---|------------|-------------|-----------------|--------|-------------|
| A | Full (MP4+SFX+Dub) | Stream copy | `{prefix}-id-final.mp4` | ~3 menit | ~350 MB |
| B | Full (MP4+SFX+Dub) | Burn SRT | `{prefix}-id-final-sub.mp4` | ~5 menit | ~1.2-4.5 GB |
| C | Simple (MP4+Dub) | Stream copy | `{prefix}-id-simple.mp4` | ~1 menit | ~350 MB |
| D | Simple (MP4+Dub) | Burn SRT | `{prefix}-id-simple-sub.mp4` | ~5 menit | ~1.2-4.5 GB |

### Pilihan bitrate (Mode B & D, v3.5 NEW)

| Bitrate | Estimasi size (2 jam) | Status |
|---------|----------------------|--------|
| 1 Mbps | ~1.2 GB | ✅ User confirmed: kualitas > ori, hemat 51% |
| 1.5 Mbps | ~1.8 GB | Default v3.5 (seimbang) |
| 2 Mbps | ~2.3 GB | v3.4 behavior (subtitle paling sharp) |
| 4 Mbps | ~4.5 GB | HD-ready (source ori high quality) |

## Install

```bash
cd ~/Dubbing
source venv/bin/activate
pip3 install questionary edge-tts yt-dlp torchaudio demucs numpy
brew install ffmpeg
```

## Workflow

```bash
cd ~/Dubbing
source venv/bin/activate

# === Alur Simple (cepat, dialog dominan) ===
# 1. Download video + audio + SRT
python3 yt-dlp-tui.py

# 2. Skip demucs (tidak perlu untuk Simple mode)

# 3. Generate TTS dari SRT
python3 edge-tts-tui.py

# 4. Mix final video (Mode C: stream copy / Mode D: burn SRT)
python3 mix-tui.py

# === Alur Full (proper, dengan SFX) ===
# 1. Download
python3 yt-dlp-tui.py

# 2. Separasi vocal (SFX bersih)
python3 demucs-tui.py

# 3. Generate TTS
python3 edge-tts-tui.py

# 4. Mix final video (Mode A: stream copy / Mode B: burn SRT)
python3 mix-tui.py

# === Kamus (parallel, sambil kerja) ===
python3 kamus-tui.py
```

## Struktur Path

```
SSD ~/Dubbing/           → scripts + venv + jv.wiktionary.json
HDD /Volumes/HDD/Dubbing/ → input/ demucs/ tts/ mix/ .env
```

config.py handle path:
- `ensure_hdd()` — cek HDD ter-colok, buat subfolder
- `ensure_kamus()` — cek jv.wiktionary.json ada
- `load_env()` — load .env dari HDD
