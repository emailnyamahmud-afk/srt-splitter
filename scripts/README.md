# Scripts — SRT Splitter + Dubbing

Python TUI untuk workflow dubbing + kamus Jawa.

## 7 TUI

| # | TUI | Status |
|---|-----|--------|
| 1 | yt-dlp-tui.py v6 (MP3) | ✅ Production |
| 2 | demucs-tui.py (M1 MPS) | ✅ Production |
| 3 | kamus-tui.py v16 | ✅ Production (audit) |
| 4 | Web app | ⚠ Prototype |
| 5 | SRT editor | ⏳ Pending (pakai SRT ID) |
| 6 | edge-tts-tui.py v7.3.1 | ✅ Production |
| 7 | mix-tui.py v3.8.2 | ✅ Production (all tested + logo + fade) |

## Pipeline (3 alur)

### PROPER — clean sempurna (pakai Demucs)

```
yt-dlp → demucs → edge-tts → mix Full (A/B)
→ ~350 MB stream / ~2-4.5 GB burn
→ clean sempurna (no_vocals dari Demucs + ducking sidechain)
```

### CEPAT — dialog dominan (skip Demucs, no SFX)

```
yt-dlp → edge-tts → mix Simple (C/D)
→ ~350 MB stream / ~2-4.5 GB burn
→ no SFX layer, Dub copy as-is
```

### MUTE — skip Demucs, MUTE COMPLETE (v3.7.6)

```
yt-dlp → edge-tts → mix Original (E/F)
→ ~1 GB stream / ~4.5 GB burn
→ MP3 ori MUTE TOTAL saat cue (amultiply + SRT-driven envelope)
→ SFX/musik latar normal di gap
```

## Scripts

### Pipeline

| Script | Fungsi | Output |
|--------|--------|--------|
| yt-dlp-tui.py v6 | Download MP4 + MP3 + SRT Indonesia | HDD/input/ |
| demucs-tui.py | Vocal separation (M1 MPS) | HDD/demucs/ |
| edge-tts-tui.py | TTS generation (5000+ cue) | HDD/tts/ |
| mix-tui.py v3.7.6 | Final mix (6 mode, MUTE COMPLETE) | HDD/mix/ |

### Kamus

| Script | Fungsi |
|--------|--------|
| kamus-tui.py v16 | TUI editor jv.wiktionary.json |
| config.py | Base path SSD/HDD |
| upload-supabase.py | Upload kamus terverifikasi ke Supabase |
| parse-jv-wiktionary-v2.py | Parser jv.wiktionary XML |
| srt-frequency-analyzer.py | Analisis frekuensi kata SRT |

### Tutor

| File | Isi |
|------|-----|
| tutor-demucs-setup.md | Setup Demucs M1 MPS + kapan perlu/skip |

## mix-tui v3.8.2 — 6 mode + logo + smooth fade

| # | Mode | Ducking | Durasi |
|---|------|---------|--------|
| A | Full + Stream | sidechain | ~3 min |
| B | Full + Burn | sidechain | ~5 min |
| C | Simple + Stream | no ducking | ~1 min |
| D | Simple + Burn | no ducking | ~5 min |
| **E** | **Original + Stream** | **amultiply MUTE** ⭐ | ~4 min |
| F | Original + Burn | amultiply MUTE | ~5-27 min* |

### Bitrate (Mode B/D/F, burn SRT)

| Bitrate | Size (2 jam) |
|---------|-------------|
| 1 Mbps | ~1.2 GB (hemat, user confirmed > ori) |
| 1.5 Mbps | ~1.8 GB (default) |
| 2 Mbps | ~2.3 GB (subtitle sharp) |
| 4 Mbps | ~4.5 GB (HD-ready) |

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

# Alur CEPAT + MUTE (skip Demucs)
python3 yt-dlp-tui.py
python3 edge-tts-tui.py
python3 mix-tui.py     # Mode E (Stream) / F (Burn)

# Alur PROPER (pakai Demucs)
python3 yt-dlp-tui.py
python3 demucs-tui.py
python3 edge-tts-tui.py
python3 mix-tui.py     # Mode A (Stream) / B (Burn)

# Kamus (parallel)
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
