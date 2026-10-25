# SRT Splitter + Dubbing Jawa

Pipeline dubbing Mandarin→Jawa end-to-end. Web app + Python TUI.

**Live:** https://srt-splitter.vercel.app/

## 7 TUI

| # | TUI | Tugas | Status |
|---|-----|-------|--------|
| 1 | yt-dlp-tui.py v6 | Download MP4 + MP3 + SRT Indonesia | ✅ Production |
| 2 | demucs-tui.py | Split audio → no_vocals.mp3 (SFX bersih) | ✅ Production |
| 3 | kamus-tui.py | User edit kamus JSON manual (sebelum DB) | ✅ Production (audit) |
| 4 | Web app | Translate SRT Indonesia → Jawa (kamus Supabase) | ⚠ Prototype |
| 5 | SRT editor | Pakai SRT Indonesia (Jawa nunggu kamus+web) | ⏳ Pending |
| 6 | edge-tts-tui.py | Generate audio dub (5000+ cue, 2-5 jam) | ✅ Production |
| 7 | mix-tui.py v3.7.6 | Mix MP4 + audio → final video (6 mode) | ✅ Production (A/B/C/D/E/F tested) |

## Pipeline

```
[Alur PROPER]  yt-dlp → demucs → edge-tts → mix Full (A/B)        ~350 MB / ~2-4.5 GB
[Alur CEPAT]   yt-dlp → edge-tts → mix Simple (C/D)               ~350 MB / ~2-4.5 GB
[Alur MUTE]    yt-dlp → edge-tts → mix Original v3.7.6 (E/F)     ~1 GB / ~4.5 GB
```

## Struktur Folder

```
SSD ~/Dubbing/                       ← scripts + venv + jv.wiktionary.json (cepat)
├── yt-dlp-tui.py
├── demucs-tui.py
├── edge-tts-tui.py
├── mix-tui.py
├── kamus-tui.py
├── config.py                        ← base path (SSD vs HDD)
└── venv/

HDD /Volumes/HDD/Dubbing/            ← data (besar)
├── input/                           ← yt-dlp output (MP4, MP3, SRT)
├── demucs/                          ← no_vocals (300MB+)
├── tts/                             ← dub wav + cache
├── mix/                             ← final MP4 (output langsung ke sini, v3.7.4)
└── .env                             ← Supabase credentials
```

## mix-tui v3.7.6 — 6 mode

| # | Mode | Input | Output | Durasi | Cocok |
|---|------|-------|--------|--------|-------|
| A | Full + Stream | MP4+SFX+Dub | `-id-final.mp4` | ~3 min | Proper, no hardsub |
| B | Full + Burn | MP4+SFX+Dub | `-id-final-sub.mp4` | ~5 min | Proper + hardsub |
| C | Simple + Stream | MP4+Dub | `-id-simple.mp4` | ~1 min | Cepat, no SFX |
| D | Simple + Burn | MP4+Dub | `-id-simple-sub.mp4` | ~5 min | Cepat + hardsub |
| E | Original + Stream | MP4+MP3+Dub+SRT | `-id-orig.mp4` | ~4 min | MUTE, no hardsub ⭐ |
| F | Original + Burn | MP4+MP3+Dub+SRT | `-id-orig-sub.mp4` | ~14-27 min | MUTE + hardsub |

### Ducking strategy (3 jenis)

- **Full mode**: sidechain compress (ducking 6/12/18 dB, gradual)
- **Original mode v3.7.6**: amultiply + inverted envelope (MUTE COMPLETE saat cue)
  - SRT Indonesia → envelope WAV (0=cue mute, 1=gap normal)
  - MP3 ori × envelope = MUTE saat cue, NORMAL saat gap
  - Fade 1ms boundary, no click artifact
- **Simple mode**: no ducking (Dub copy as-is)

### Pilihan bitrate (Mode B/D/F — burn SRT wajib re-encode)

| Bitrate | Size (2 jam) | Status |
|---------|-------------|--------|
| 1 Mbps | ~1.2 GB | ✅ User confirmed > ori, hemat 51% |
| 1.5 Mbps | ~1.8 GB | Default (seimbang) |
| 2 Mbps | ~2.3 GB | Subtitle paling sharp |
| 4 Mbps | ~4.5 GB | HD-ready (1080p+) |

### Logo overlay (v3.8 NEW — Mode B/D/F only)

Auto-detect logo PNG transparan, burn ke top-right (10px margin) bersama subtitle.

**Cara pakai:**
1. Download logo (150×150 px, 24 KB, transparan):
   ```bash
   curl -L -o ~/Dubbing/logo.png "https://raw.githubusercontent.com/emailnyamahmud-afk/srt-splitter/main/public/logo.png"
   ```
2. Atau taruh logo custom di salah satu lokasi:
   - `~/Dubbing/logo.png` (SSD)
   - `/Volumes/HDD/Dubbing/input/logo.png` (HDD)
3. Jalankan mix-tui Mode Burn SRT (B/D/F) → logo auto-detect → burn top-right

**Note:** Mode Stream copy (A/C/E) tidak support logo (no re-encode). Logo hanya untuk Mode Burn SRT.

## Install

```bash
cd ~/Dubbing
source venv/bin/activate
pip3 install questionary edge-tts yt-dlp torchaudio demucs numpy
brew install ffmpeg
```

## Workflow

```bash
# Alur CEPAT (skip Demucs, MUTE COMPLETE)
python3 yt-dlp-tui.py        # 1. MP4 + MP3 + SRT
python3 edge-tts-tui.py      # 2. Dub dari SRT
python3 mix-tui.py           # 3. Mix Mode E/F (MUTE saat cue)

# Alur PROPER (pakai Demucs, clean sempurna)
python3 yt-dlp-tui.py
python3 demucs-tui.py        # 2. Split vokal dari SFX
python3 edge-tts-tui.py
python3 mix-tui.py           # 4. Mix Mode A/B

# Kamus (parallel)
python3 kamus-tui.py
```

## Kamus

- `jv.wiktionary.json` — 44.585 entries (SOURCE OF TRUTH, dari XML dump Wikimedia)
- `kamus-tui.py v16` — Editor TUI, validasi manual, mark READY, upload Supabase
- `Supabase` — DB kamus terverifikasi (user upload setelah audit)

## Download

```bash
cd ~/Dubbing
curl -L -o config.py "https://raw.githubusercontent.com/emailnyamahmud-afk/srt-splitter/main/scripts/config.py"
curl -L -o yt-dlp-tui.py "https://raw.githubusercontent.com/emailnyamahmud-afk/srt-splitter/main/scripts/yt-dlp-tui.py"
curl -L -o demucs-tui.py "https://raw.githubusercontent.com/emailnyamahmud-afk/srt-splitter/main/scripts/demucs-tui.py"
curl -L -o edge-tts-tui.py "https://raw.githubusercontent.com/emailnyamahmud-afk/srt-splitter/main/scripts/edge-tts-tui.py"
curl -L -o mix-tui.py "https://raw.githubusercontent.com/emailnyamahmud-afk/srt-splitter/main/scripts/mix-tui.py"
curl -L -o kamus-tui.py "https://raw.githubusercontent.com/emailnyamahmud-afk/srt-splitter/main/scripts/kamus-tui.py"
curl -L -o upload-supabase.py "https://raw.githubusercontent.com/emailnyamahmud-afk/srt-splitter/main/scripts/upload-supabase.py"
```
