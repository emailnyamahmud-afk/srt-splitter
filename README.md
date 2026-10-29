# SRT Splitter + Dubbing Multi-Bahasa

Pipeline dubbing bahasa eksternal (Mandarin, English, Jepang, Italia, dll) → Indonesia / Jawa / Sunda. Web app + Python TUI.

ID jalan end-to-end (12 TUI production). Jawa/Sunda nunggu kamus Supabase selesai.

**Live:** https://srt-splitter.vercel.app/

## 12 TUI

| # | TUI | Tugas | Status |
|---|-----|-------|--------|
| 1 | yt-dlp-tui.py v6.2 | Download MP4 + MP3 + SRT (YT/FB/TikTok/IG + cookies anti-bot) | ✅ Production (FB+YT confirmed) |
| 2 | demucs-tui.py | Split audio → no_vocals.mp3 (SFX bersih) | ✅ Production |
| 3 | kamus-tui.py | User edit kamus JSON manual (sebelum DB) | ✅ Production (audit) |
| 4 | Web app | Translate SRT Indonesia → Jawa (kamus Supabase) | ⚠ Prototype |
| 5 | SRT editor (web) | Pakai SRT Indonesia (Jawa nunggu kamus+web) | ⏳ Pending |
| 6 | edge-tts-tui.py v7.4 (paralel-safe, lock file, 429 retry) | ✅ Production |
| 7 | mix-tui.py v3.8.2 | Mix MP4 + audio → final video (6 mode + logo + fade) | ✅ Production (all tested) |
| 8 | whisper-tui.py v2.0 | Generate SRT dari audio (whisper.cpp, Metal GPU M1) | ✅ Production (Metal GPU, 5.3x realtime, 20 min for 2h audio) |
| 9 | srt-editor-tui.py v1.0.1 | Fix typo/konteks SRT hasil translate (glossary + bulk replace) | ✅ Production |
| 10 | shorts-tui.py v1.1 | Pecah MP4 final jadi N shorts (JSON dari AI) atau N parts (SRT auto-split) | ✅ Production (Shorts 60/60 + Part mode auto-split) |
| 11 | shorts-csv-tui.py v1.0 | Generate metadata CSV + manifest untuk YouTube Studio | ✅ Production (test 60 segment, CSV 19.8 KB + manifest 30.4 KB) |
| 12 | merge-tui.py v1.1 | Gabungin multi-video (S1-S4) jadi 1 video panjang | ✅ Production (questionary, checkbox multi-select) |

## Pipeline

```
[Alur PROPER]  yt-dlp → srt-editor → demucs → edge-tts → mix Full (A/B)  ~350 MB / ~2-4.5 GB
[Alur CEPAT]   yt-dlp → srt-editor → edge-tts → mix Simple (C/D)     ~350 MB / ~2-4.5 GB
[Alur MUTE]    yt-dlp → srt-editor → edge-tts → mix Original v3.7.6 (E/F)  ~1 GB / ~4.5 GB
[Alur SHORTS]  mix-tui → shorts-tui (via Dola JSON) → shorts-csv-tui → YouTube Studio  ~15 detik / ~2 menit
[Alur MERGE]   mix-tui × N → merge-tui → 1 video panjang (stream copy / re-encode)
```

> **merge-tui** (TUI #12): gabungin output mix-tui (sudah dub ID + burn sub) dari beberapa film/season jadi 1 video panjang. 3 mode: stream copy (super cepat) / re-encode + target res / re-encode pakai res file pertama.

> **srt-editor-tui.py** (TUI #9, opsional) untuk fix typo/konteks SRT hasil translate sebelum masuk edge-tts. Skip kalau SRT ori sudah clean.
>
> **Shorts pipeline** (TUI #10 + #11): mix-tui output → Dola AI skill `shorts-json` (upload SRT, ketik "buat shorts", dapat 60 segment JSON) → shorts-tui.py (pecah MP4, ~94s) → shorts-csv-tui.py (metadata CSV + manifest untuk YouTube Studio).

## Struktur Folder

```
SSD ~/Dubbing/                       ← scripts + venv + jv.wiktionary.json (cepat)
├── yt-dlp-tui.py
├── demucs-tui.py
├── edge-tts-tui.py
├── mix-tui.py
├── kamus-tui.py
├── srt-editor-tui.py                ← fix typo SRT hasil translate (new)
├── config.py                        ← base path (SSD vs HDD)
└── venv/

HDD /Volumes/HDD/Dubbing/            ← data (besar)
├── input/                           ← yt-dlp output (MP4, MP3, SRT)
├── demucs/                          ← no_vocals (300MB+)
├── tts/                             ← dub wav + cache
├── mix/                             ← final MP4 (output langsung ke sini, v3.7.4)
├── shorts/                          ← shorts-tui Shorts: JSON + MP4 (subfolder per film)
├── parts/                           ← shorts-tui Part: MP4 4-5 min per part (TikTok playlist)
├── merged/                          ← merge-tui output: 1 video panjang (gabungan S1-S4)
└── .env                             ← Supabase credentials
```

## srt-editor-tui v1.0.1 — fix typo SRT hasil translate

```bash
cd ~/Dubbing && source venv/bin/activate
python3 srt-editor-tui.py                                     # interaktif, pilih SRT dari list
python3 srt-editor-tui.py /Volumes/HDD/Dubbing/input/S2-FB-Mandarin.id.srt
# Output: S2-FB-Mandarin.id.final.srt → pakai untuk edge-tts-tui
```

Detail lengkap: lihat [scripts/README.md](scripts/README.md#srt-editor-tui-v101).

## shorts-tui v1.1 — pecah MP4 jadi Shorts (AI JSON) atau Parts (SRT auto-split)

```bash
cd ~/Dubbing && source venv/bin/activate

# 1. User paste SRT ke ChatGPT/Claude/Gemini/Dola AI → minta "pilih 60 segment menarik"
#    → AI return JSON: [{"start": 12.5, "end": 65.3, "title": "..."}, ...]
#    → save ke /Volumes/HDD/Dubbing/shorts/{film}.timestamps.json (folder yang sama dgn output, rapi)
#    (prompt template: tutor-shorts-prompt.md)

# 2. Pecah MP4 final jadi 60 shorts
python3 shorts-tui.py
# → pilih JSON timestamps + MP4 final (dari HDD/mix/, sudah vertikal+hardsub)
# → output: HDD/shorts/{film-name}/short-001.mp4 s/d short-060.mp4
# ~2 menit untuk 60 shorts (stream copy, no re-encode)
```

Detail lengkap: lihat [scripts/README.md](scripts/README.md#shorts-tui-v10) + [tutor-shorts-prompt.md](scripts/tutor-shorts-prompt.md).

## merge-tui v1.0 — gabungin multi-video jadi 1 panjang

```bash
cd ~/Dubbing && source venv/bin/activate
python3 merge-tui.py
# → Input: HDD/mix/*.mp4 (output mix-tui, sudah dub ID + burn sub ID)
# → Output: HDD/merged/merged_YYYYMMDD_HHMMSS.mp4
# 3 mode:
#   [7] Stream copy (super cepat, butuh res+codec sama)
#   [8] Re-encode + target res (kalau beda)
#   [9] Re-encode pakai res file pertama
# Shortcut: ketik "mix" di menu [1] untuk list semua MP4 di HDD/mix/
```

Detail lengkap: lihat [scripts/README.md](scripts/README.md#merge-tui-v10).

## shorts-csv-tui v1.0 — metadata CSV + manifest untuk YouTube Studio

```bash
cd ~/Dubbing && source venv/bin/activate
python3 shorts-csv-tui.py
# → Step 1: pilih JSON timestamps (dari Dola)
# → Step 2: pilih folder MP4 (dari shorts-tui output)
# → Step 3-7: film name, template, tags, schedule, output
# → Output: {film}.metadata.csv (untuk Excel) + {film}.manifest.txt (copy-paste YouTube)
```

Workflow end-to-end Shorts:
1. Dola: upload SRT → ketik "buat shorts" → JSON 60 segment
2. `shorts-tui.py` → 60 MP4 (~94 detik, stream copy)
3. `shorts-csv-tui.py` → CSV + manifest (BARU)
4. Drag 60 MP4 ke YouTube Studio + copy-paste metadata dari manifest

Detail lengkap: lihat [scripts/README.md](scripts/README.md#shorts-csv-tui-v10).

## mix-tui v3.8.2 — 6 mode + logo + smooth fade

| # | Mode | Input | Output | Durasi | Cocok |
|---|------|-------|--------|--------|-------|
| A | Full + Stream | MP4+SFX+Dub | `-id-final.mp4` | ~3 min | Proper, no hardsub |
| B | Full + Burn | MP4+SFX+Dub | `-id-final-sub.mp4` | ~5 min | Proper + hardsub |
| C | Simple + Stream | MP4+Dub | `-id-simple.mp4` | ~1 min | Cepat, no SFX |
| D | Simple + Burn | MP4+Dub | `-id-simple-sub.mp4` | ~5 min | Cepat + hardsub |
| E | Original + Stream | MP4+MP3+Dub+SRT | `-id-orig.mp4` | ~4 min | MUTE, no hardsub ⭐ |
| F | Original + Burn | MP4+MP3+Dub+SRT | `-id-orig-sub.mp4` | ~5-27 min* | MUTE + hardsub |

* Mode F durasi: 480p ~5min, 720p ~10min, 1080p ~27min (tergantung resolusi + bitrate)

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

### Logo overlay (v3.8 NEW, v3.8.2 scale 100px — Mode B/D/F only)

Auto-detect logo PNG transparan, burn ke top-right (100×100 px, 10px margin) bersama subtitle. User confirmed "berjalan sempurna".

**Cara pakai:**
1. Download logo channel (150×150 px, 49 KB, transparan, sudah di-crop):
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
pip3 install questionary edge-tts yt-dlp torchaudio demucs numpy faster-whisper
brew install ffmpeg
```

## Workflow

```bash
# Alur CEPAT (skip Demucs, MUTE COMPLETE)
python3 yt-dlp-tui.py         # 1. MP4 + MP3 + SRT (cookies anti-bot)
python3 srt-editor-tui.py     # 2. Fix typo/konteks SRT (opsional)
python3 edge-tts-tui.py       # 3. Dub dari SRT (paralel 2 TTS di VS Code)
python3 mix-tui.py            # 4. Mix Mode E/F (MUTE saat cue)

# Alur SHORTS (setelah mix selesai)
# 1. Upload SRT ke Dola AI → ketik "buat shorts" → download JSON
# 2. python3 shorts-tui.py     # → 60 MP4 (~94 detik)
# 3. python3 shorts-csv-tui.py # → CSV + manifest (metadata untuk YouTube)
# 4. Drag 60 MP4 ke YouTube Studio + copy-paste dari manifest

# Alur MERGE (gabungin S1-S4 jadi 1 video panjang)
python3 merge-tui.py          # Input: HDD/mix/*.mp4 → Output: HDD/merged/merged_*.mp4

# Alur PROPER (pakai Demucs, clean sempurna)
python3 yt-dlp-tui.py
python3 srt-editor-tui.py     # fix typo SRT dulu kalau perlu
python3 demucs-tui.py        # 3. Split vokal dari SFX
python3 edge-tts-tui.py
python3 mix-tui.py            # 5. Mix Mode A/B

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
curl -L -o whisper-tui.py "https://raw.githubusercontent.com/emailnyamahmud-afk/srt-splitter/main/scripts/whisper-tui.py"
curl -L -o srt-editor-tui.py "https://raw.githubusercontent.com/emailnyamahmud-afk/srt-splitter/main/scripts/srt-editor-tui.py"
curl -L -o shorts-tui.py "https://raw.githubusercontent.com/emailnyamahmud-afk/srt-splitter/main/scripts/shorts-tui.py"
curl -L -o shorts-csv-tui.py "https://raw.githubusercontent.com/emailnyamahmud-afk/srt-splitter/main/scripts/shorts-csv-tui.py"
curl -L -o tutor-shorts-prompt.md "https://raw.githubusercontent.com/emailnyamahmud-afk/srt-splitter/main/scripts/tutor-shorts-prompt.md"
curl -L -o upload-supabase.py "https://raw.githubusercontent.com/emailnyamahmud-afk/srt-splitter/main/scripts/upload-supabase.py"
curl -L -o merge-tui.py "https://raw.githubusercontent.com/emailnyamahmud-afk/srt-splitter/main/scripts/merge-tui.py"
```
