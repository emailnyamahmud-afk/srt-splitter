# Scripts — SRT Splitter + Dubbing

Python TUI untuk workflow dubbing + kamus Jawa.

## Scripts

### Pipeline

| Script | Fungsi | Output |
|--------|--------|--------|
| yt-dlp-tui.py | Download video/audio + SRT | HDD/input/ |
| demucs-tui.py | Vocal separation (M1 MPS) | HDD/demucs/ |
| edge-tts-tui.py | TTS generation (100% lokal) | HDD/tts/ |
| mix-tui.py | Final mix video (stream/burn SRT) | HDD/mix/ |

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

# 1. Download video + audio + SRT
python3 yt-dlp-tui.py

# 2. Separasi vocal (SFX bersih)
python3 demucs-tui.py

# 3. Generate TTS dari SRT
python3 edge-tts-tui.py

# 4. Edit SRT di web app
#    https://srt-splitter.vercel.app/

# 5. Mix final video
python3 mix-tui.py

# Kamus (sambil kerja)
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
