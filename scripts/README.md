# Scripts — SRT Splitter + Dubbing Multi-Bahasa

Python TUI untuk workflow dubbing bahasa eksternal → Indonesia / Jawa / Sunda.

## 12 TUI

| # | TUI | Status |
|---|-----|--------|
| 1 | yt-dlp-tui.py v6.5 (MP4+MP3+multi-SRT ID+EN, cookies anti-bot, default 1080p) | ✅ Production |
| 2 | demucs-tui.py (M1 MPS) | ✅ Production |
| 3 | kamus-tui.py v16 | ✅ Production (audit) |
| 4 | Web app | ⚠ Prototype |
| 5 | SRT editor (web) | ⏳ Pending |
| 6 | edge-tts-tui.py v7.4 (paralel-safe, lock file + 429 retry) | ✅ Production |
| 7 | mix-tui.py v3.10 (force 1080p + audio 48000Hz stereo) | ✅ Production |
| 8 | whisper-tui.py v2.0 (whisper.cpp, Metal GPU) | ✅ Production |
| 9 | srt-editor-tui.py v1.0.1 (fix typo SRT translate) | ✅ Production |
| 10 | shorts-tui.py v1.1 (Shorts via AI JSON atau Part via SRT) | ✅ Production |
| 11 | shorts-csv-tui.py v1.0 (metadata CSV + manifest YouTube) | ✅ Production |
| 12 | merge-tui.py v2.0 (full format detect, stream copy / standardize) | ✅ Production (VLC confirmed) |

## Pipeline

```
[PROPER] yt-dlp → srt-editor → demucs → edge-tts → mix Full (A/B)
[CEPAT]  yt-dlp → srt-editor → edge-tts → mix Simple (C/D)
[MUTE]   yt-dlp → srt-editor → edge-tts → mix Original (E/F)
[SHORTS] mix-tui → Dola AI → shorts-tui → shorts-csv-tui → YouTube Studio
[MERGE]  mix-tui × N → merge-tui (stream copy) → 1 video panjang
```

## Scripts

| Script | Fungsi | Output |
|--------|--------|--------|
| yt-dlp-tui.py v6.5 | Download MP4 + MP3 + multi-SRT (ID+EN) | HDD/input/ |
| demucs-tui.py | Vocal separation (M1 MPS) | HDD/demucs/ |
| edge-tts-tui.py v7.4 | TTS generation (paralel-safe) | HDD/tts/ |
| mix-tui.py v3.10 | Final mix (force 1080p, audio 48000Hz stereo) | HDD/mix/ |
| merge-tui.py v2.0 | Gabungin multi-video (stream copy / standardize) | HDD/merged/ |
| kamus-tui.py v16 | TUI editor jv.wiktionary.json | SSD |
| srt-editor-tui.py v1.0.1 | Fix typo SRT hasil translate | HDD/input/ |
| shorts-tui.py v1.1 | Pecah MP4 jadi shorts/parts | HDD/shorts/ |
| shorts-csv-tui.py v1.0 | Metadata CSV + manifest YouTube | HDD/shorts/ |
| whisper-tui.py v2.0 | Generate SRT dari audio (Metal GPU) | HDD/input/ |
| config.py | Base path SSD/HDD | — |
| upload-supabase.py | Upload kamus ke Supabase | — |

## Struktur Path

```
SSD ~/Dubbing/           → scripts + venv + jv.wiktionary.json
HDD /Volumes/HDD/Dubbing/ → input/ demucs/ tts/ mix/ shorts/ parts/ merged/ .env
```

config.py: `ensure_hdd()`, `ensure_kamus()`, `load_env()`, `INPUT_DIR`, `DEMUCS_DIR`, `TTS_DIR`, `MIX_DIR`, `SHORTS_DIR`, `PARTS_DIR`, `MERGED_DIR`

## Install

```bash
cd ~/Dubbing && source venv/bin/activate
pip3 install questionary edge-tts yt-dlp torchaudio demucs numpy
brew install ffmpeg
```

## Workflow

```bash
cd ~/Dubbing && source venv/bin/activate

# Alur MUTE (skip Demucs, MUTE COMPLETE)
python3 yt-dlp-tui.py         # 1. MP4 + MP3 + multi-SRT (ID+EN)
python3 srt-editor-tui.py      # 2. Fix typo SRT (opsional)
python3 edge-tts-tui.py        # 3. Generate dub dari SRT
python3 mix-tui.py             # 4. Mix Mode F (force 1080p + audio 48000Hz)

# Alur MERGE (gabungin series)
python3 merge-tui.py           # 5. Stream copy (super cepat, ~2 menit)

# Alur SHORTS
python3 shorts-tui.py         # 6. Pecah jadi 60 shorts
python3 shorts-csv-tui.py      # 7. Metadata CSV + manifest

# Kamus (parallel)
python3 kamus-tui.py
```

## edge-tts v7.4 — Paralel Support

2-3 TTS paralel di terminal berbeda. Lock file detect prefix collision.

| Instance | RAM | Mac 16GB |
|----------|-----|---------|
| 1 | ~1.6 GB | Aman |
| 2 | ~3.2 GB | Aman |
| 3 | ~4.8 GB | Aman |

## srt-editor-tui v1.0.1

```bash
python3 srt-editor-tui.py                          # interaktif
python3 srt-editor-tui.py /path/to/file.id.srt     # eksplisit
# Output: .final.srt (untuk edge-tts), .srt.bak (backup), .working.json (auto-save)
```

Glossary: 11 names (Lin Zhao, Xie Changfeng, dll) + 8 terms (Xiangjun, Jiedushi, dll).

## shorts-tui v1.1

```bash
# 1. Upload SRT ke Dola AI → "buat shorts" → JSON 60 segment
# 2. python3 shorts-tui.py → 60 MP4 (~94 detik, stream copy)
# 3. python3 shorts-csv-tui.py → CSV + manifest
```

Test: 60/60 sukses, 56.5s total, 803.8 MB output.

## shorts-csv-tui v1.0

Generate CSV (Excel) + manifest text (copy-paste YouTube Studio).
Custom: film name, description template, tags, category, schedule, interval.

## merge-tui v2.0 — VLC CONFIRMED ✅

| Mode | Kecepatan | Syarat |
|------|----------|--------|
| Stream copy | ~2 menit (24 jam) | Semua format sama (6 properties) |
| Standardisasi | ~5-8 min/file (GPU) | Format beda → re-encode per-file |

Auto-detect 6 properties: res + vcodec + acodec + fps + sample_rate + channels.

Test result (30 Okt 2026): 10 file × 24h, sync 100%, stream copy ~2 menit.
