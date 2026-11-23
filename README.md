# SRT Splitter + Dubbing Multi-Bahasa

Pipeline dubbing bahasa eksternal (Mandarin, English, Jepang, Italia, dll) → Indonesia / Jawa / Sunda. Web app + Python TUI.

ID jalan end-to-end (12 TUI production + 5 untested). Jawa jalan via Gemini TTS (gemini-tts-tui v1.1 SRT + Narasi). Talking head via SadTalker Replicate (talkinghead-tui v1.0). Shorts infografis via manim (manim-shorts-tui v0.1). Sunda nunggu kamus Supabase selesai.

**Live:** https://srt-splitter.vercel.app/

## 20 TUI

| # | TUI | Tugas | Status |
|---|-----|-------|--------|
| 1 | yt-dlp-tui.py v6.5 | Download MP4 + MP3 + multi-SRT (ID+EN, default 1080p preferred) | ✅ Production (v6.5 multi-SRT) |
| 2 | demucs-tui.py | Split audio → no_vocals.mp3 (SFX bersih) | ✅ Production |
| 3 | kamus-tui.py | User edit kamus JSON manual (sebelum DB) | ✅ Production (audit) |
| 4 | Web app | Translate SRT Indonesia → Jawa (kamus Supabase) | ⚠ Prototype |
| 5 | SRT editor (web) | Pakai SRT Indonesia (Jawa nunggu kamus+web) | ⏳ Pending |
| 6 | edge-tts-tui.py v7.5 | TTS SRT + Narration (Indonesia, paralel-safe, lock file, 429 retry) | ✅ Production default |
| 7 | mix-tui.py v3.11 | Mix MP4 + audio → final video (6 mode + logo + fade + force 1080p + audio 48000 Hz stereo + 1:1 square mode) | ✅ Production (1:1 VLC confirmed 14 Nov 2026) |
| 8 | whisper-tui.py v2.1 | Generate SRT dari audio (whisper.cpp, Metal GPU M1) | ✅ Production (Metal GPU, 5.3x realtime, 20 min for 2h audio) |
| 9 | srt-editor-tui.py v1.0.0 | Fix typo/konteks SRT hasil translate (glossary + bulk replace) | ✅ Production |
| 10 | shorts-tui.py v1.1 | Pecah MP4 final jadi N shorts (JSON dari AI) atau N parts (SRT auto-split) | ✅ Production (Shorts 60/60 + Part mode auto-split) |
| 11 | shorts-csv-tui.py v1.0 | Generate metadata CSV + manifest untuk YouTube Studio | ✅ Production (test 60 segment, CSV 19.8 KB + manifest 30.4 KB) |
| 12 | merge-tui.py v1.9 | Gabungin multi-video jadi 1 panjang (full format detect, stream copy / standardize) | ✅ Production (VLC confirmed, sync 100%) |
| 13 | review-mix-tui.py v1.0 | Review film (MP4 + JSON + narasi → final MP4, VideoToolbox M1 GPU) | ⚠ UNTESTED (code di GitHub, belum diuji di Mac) |
| 14 | konten-tui.py v1.0 | Konten sejarah (narasi + images → Ken Burns video 1920x1080) | ⚠ UNTESTED (code di GitHub, belum diuji di Mac) |
| 15 | **gemini-tts-tui.py v1.1** | TTS SRT + Narasi (Indonesia + Jawa, OPSI TAMBAHAN, butuh GEMINI_API_KEY) | ⚠ UNTESTED (code di GitHub belum diuji di Mac) |
| 16 | **talkinghead-tui.py v1.0** | Talking head video (foto green screen + narasi JV via SadTalker Replicate, green screen preserved) | ⚠ UNTESTED (code di GitHub belum diuji di Mac) |
| 17 | **manim-shorts-tui.py v0.1** | Shorts infografis (WAV + SRT → manim animation video vertical 9:16, premium look gratis) | ⚠ UNTESTED (sandbox OK 19 Nov 2026 + fix 21 Nov 2026, belum diuji di Mac) |
| 18 | **piper-tts-tui.py v0.2** | TTS LOKAL offline (Piper VITS ONNX, GPU Metal CoreML, SRT + Narasi mode) | ⚠ UNTESTED (sandbox OK 22 Nov 2026, generate test pending HF rate-limit, belum diuji di Mac) |
| 19 | **voicestudio-tts-tui.py v1.0** | TTS via VoiceStudio local API (localhost:3900, 4 voice profile anton/sari ID+JV, GPU Metal) | ⚠ SLOW (user test 23 Nov 2026: suara bagus tapi 16s SRT = 8 menit. Superseded #20) |
| 20 | **supertonic-tts-tui.py v0.1** | TTS LOKAL Supertone Supertonic 3 ONNX (10 voice M1-M5/F1-F5 deterministic, model sama subtitlekit.com, ~100x edge speed) | ✅ Production candidate (user VLC 23 Nov 2026: sangat bagus, ID laki+perempuan OK, 1jam SRT ~30menit. Pending long-cue) |

**Eksperimen DEPRECATED:** `omnivoice-tts-tui.py v0.7` — ❌ ref clone berantakan (user VLC 23 Nov 2026, v0.7 fix tidak solve drift). Pakai supertonic #20.

## Pipeline

```
[Alur PROPER]       yt-dlp → srt-editor → demucs → edge-tts → mix Full (A/B)  ~350 MB / ~2-4.5 GB
[Alur CEPAT]        yt-dlp → srt-editor → edge-tts → mix Simple (C/D)     ~350 MB / ~2-4.5 GB
[Alur MUTE]         yt-dlp → srt-editor → edge-tts → mix Original v3.7.6 (E/F)  ~1 GB / ~4.5 GB
[Alur SHORTS]       mix-tui → shorts-tui (via Dola JSON) → shorts-csv-tui → YouTube Studio  ~15 detik / ~2 menit
[Alur MERGE]        mix-tui × N → merge-tui → 1 video panjang (stream copy / re-encode)
[Alur REVIEW]       edge-tts Narration (ID) → review-mix-tui (review film ID)
[Alur KONTEN]       edge-tts Narration (ID) → konten-tui (konten sejarah ID)
[Alur GEMINI-SRT]   yt-dlp → srt-editor → gemini-tts-tui (SRT mode, ID/JV) → mix-tui  (opsional: Jawa/karakter spesifik)
[Alur GEMINI-NARASI] naskah.txt → gemini-tts-tui (Narration mode, ID/JV) → review-mix-tui / konten-tui  (Jawa)
[Alur TALKING-HEAD] naskah.txt → gemini-tts-tui Narration (JV) → talkinghead-tui v1.0 (Replicate SadTalker, preprocess=full) → MP4 green screen preserved → editor chroma key → final-konten.mp4
[Alur MANIM-SHORTS] WAV narasi (edge-tts/gemini-tts Narration) + SRT (whisper-tui) → manim-shorts-tui v0.1 → HDD/manim-shorts/{stem}-shorts.mp4 (infografis Shorts vertical)
```

> **merge-tui** (TUI #12): gabungin output mix-tui (sudah dub ID + burn sub) dari beberapa film/season jadi 1 video panjang. 3 mode: stream copy (super cepat) / re-encode + target res / re-encode pakai res file pertama.

> **srt-editor-tui.py** (TUI #9, opsional) untuk fix typo/konteks SRT hasil translate sebelum masuk edge-tts / gemini-tts. Skip kalau SRT ori sudah clean.
>
> **Shorts pipeline** (TUI #10 + #11): mix-tui output → Dola AI skill `shorts-json` (upload SRT, ketik "buat shorts", dapat 60 segment JSON) → shorts-tui.py (pecah MP4, ~94s) → shorts-csv-tui.py (metadata CSV + manifest untuk YouTube Studio).
>
> **review-mix-tui** (TUI #13): review film dengan narasi. Input: MP4 + timestamps.json (dari Z.ai skill) + narasi.wav (dari edge-tui v7.5 Narasi ID atau gemini-tui v1.1 Narasi JV). Output: `HDD/review/review-final.mp4`.
>
> **konten-tui** (TUI #14): konten sejarah dengan Ken Burns effect. Input: narasi.wav + timestamps.json + folder images (Google Flow) + (opsional) backsound.mp3. Output: `HDD/konten/konten-final.mp4` (1920x1080).
>
> **gemini-tts-tui.py** (TUI #15, OPSI TAMBAHAN): alternatif edge-tts untuk skenario yang Edge kurang bagus. 2 mode: SRT (Indonesia + Jawa) + Narasi (Indonesia + Jawa). Pakai Gemini 3.8 Flash TTS, butuh `GEMINI_API_KEY` di `.env`. Narasi output → feed review-mix-tui / konten-tui / talkinghead-tui (untuk bahasa Jawa). Detail: `scripts/GEMINI_TTS.md`.
>
> **talkinghead-tui.py** (TUI #16, OPSI TAMBAHAN untuk workflow KONTEN, bukan dubbing): 1 foto green screen + 1 audio narasi JV → talking head MP4 dengan **green screen DIPERTAHANKAN** (preprocess=full mode). Backend: Replicate.com `cjwbw/sadtalker` (cloud A100, ~17 detik per run, ~$0.05-0.20 per video). User edit manual: chroma key → composite background → final-konten.mp4 (siap YouTube). Butuh `REPLICATE_API_TOKEN` di `.env`. Detail: `scripts/TALKINGHEAD.md`.

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

## srt-editor-tui v1.0.0 — fix typo SRT hasil translate

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

## merge-tui v1.9 — gabungin multi-video jadi 1 panjang

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

## gemini-tts-tui v1.1 — TUI #15 OPSI TAMBAHAN Gemini 3.8 Flash TTS (SRT + Narasi, ID + JV)

⚠ **EXPERIMENTAL** — edge-tts-tui v7.5 tetap production default (Indonesia only).
gemini-tts-tui untuk skenario yang Edge kurang bagus / tidak support.

### 2 Mode (mirror edge-tts-tui v7.5 pattern)

**SRT mode** (7 step TUI): SRT → output → bahasa → voice → instruction → Smart Fit → prefix
→ Output: `HDD/tts/{prefix}-audio-id-dub.wav` (24kHz mono 16-bit, mix-tui compatible)

**Narration mode** (6 step TUI): naskah.txt → output → bahasa → voice → instruction → rate
→ Output: `HDD/tts/{stem}-narasi.wav` (48kHz stereo 16-bit, review-mix-tui compatible)

### Bahasa: Indonesia (id) + Jawa (jv)

Instruction template filter per bahasa pilihan (4 ID + 4 JV + custom).

### Kapan pakai
- Bahasa Jawa (krama/ngoko) — Cruz + jawa-halus-mc → user tested OK di AI Studio
- Karakter suara spesifik (MC/adat, narator dokuser, dialog dramatis)
- Bahasa eksotis (Italia, Jepang, dll) yang tidak ada di Edge TTS
- JANGAN pakai untuk produksi Indonesia umum (Edge TTS lebih stabil + free)

### Setup & pakai
```bash
# Setup (sekali saja)
echo "GEMINI_API_KEY=AIza..." >> /Volumes/HDD/Dubbing/.env
pip3 install google-genai

# Pakai
cd ~/Dubbing && source venv/bin/activate
python3 gemini-tts-tui.py
# → Mode selection: SRT / Narration
```

Detail lengkap: lihat [scripts/GEMINI_TTS.md](scripts/GEMINI_TTS.md).

## talkinghead-tui v1.0 — TUI #16 OPSI TAMBAHAN (SadTalker via Replicate, green screen preserved)

⚠ **UNTESTED** (code di GitHub, belum diuji di Mac). Untuk workflow **KONTEN** (bukan dubbing).

### Workflow:
```
naskah.txt → gemini-tts-tui v1.1 Narration (JV) → narasi-jawa.wav
              ↓
              + foto green screen half-body (mis. Amat dengan blangkon + batik)
              ↓
              talkinghead-tui v1.0 (Replicate SadTalker, preprocess=full, still, gfpgan)
              ↓
              → HDD/konten/{name}-talking-green.mp4 (green screen DIPERTAHANKAN)
              ↓
              User edit manual (Final Cut / DaVinci / Premiere):
              - Chroma key green → hilang
              - Composite dengan background baru (foto sejarah, kantor adat, dll)
              - Tambah text overlay (opsional)
              → final-konten.mp4 (siap YouTube)
```

### Kenapa Replicate (BUKAN M1 lokal)?
SadTalker di M1: Python 3.8 strict, hardcode CUDA, MPS support partial (Issue #526 open), community bilang "very slow". Effort install + patch tidak worth it.

Replicate cloud: A100 80GB, ~17 detik per run, ~$0.05-0.20 per video. Untuk workflow konten (volume rendah-sedang) = sangat reasonable.

### Setup & pakai:
```bash
# Setup (sekali saja)
echo "REPLICATE_API_TOKEN=r8_xxx..." >> /Volumes/HDD/Dubbing/.env
pip3 install replicate requests

# Pakai
cd ~/Dubbing && source venv/bin/activate
python3 talkinghead-tui.py
# → 6 step TUI: source image → driven audio → output → preprocess → still → enhancer
```

### Preprocess mode:
- **full** (default, recommended): Animasi wajah → paste back ke ORIGINAL background → green screen DIPERTAHANKAN
- extfull: full + extra margin (untuk head tilt banyak)
- crop/extcrop: face only (gak cocok green screen — output = face centered)

Detail lengkap: lihat [scripts/TALKINGHEAD.md](scripts/TALKINGHEAD.md).

## manim-shorts-tui v0.1 — TUI #17 Shorts infografis (WAV + SRT → manim video)

⚠ **UNTESTED** — sandbox pipeline OK 19 Nov 2026 + fix clipping+highlight 21 Nov 2026 (commit 1623907), belum diuji di Mac user.

Generate video Shorts vertical 9:16 dari WAV narasi + SRT, dengan animasi manim (premium look, gratis, tanpa model AI video mahal).

### Cara kerja

1. Input WAV (edge-tts/gemini-tts Narration atau manual) + SRT (whisper-tui #8 output)
2. Parse SRT → segments [{start, end, text}]
3. Generate manim script temp (charcoal bg `#1C1C2E`, FadeIn whole text 0.3s + word-by-word highlight via t2c+Transform (yellow per kata, text full tetap visible) + FadeOut 0.2s per segment, wrap_text + adaptive font size 56/48/40)
4. Render manim → video-only MP4 (no audio)
5. Mux video + WAV → final MP4 (ffmpeg, video stream copy + audio aac)

Output: `HDD/manim-shorts/{stem}-shorts.mp4` (1080x1920 vertical, 30fps, h264 + aac 48kHz stereo)

### Render time

~0.9x realtime (30s video ≈ 26s render). Sandbox test 21 Nov 2026 (fix clipping+highlight, commit 1623907): dummy WAV 30s + 8 SRT segments → MP4 1.5MB, 30.0s perfect sync, render 26s. edgeClip 0% (text fit width), highlight yellow 0.03-0.07% per word.

### Setup & pakai

```bash
# Setup (sekali saja)
pip3 install manim questionary
brew install cairo pango ffmpeg         # manim system deps (Mac)
# Opsional: brew install font-noto-sans  # font default TUI ini
# NGGAK butuh LaTeX (pakai Text class Pango, bukan Tex/MathTex)

# Pakai
cd ~/Dubbing && source venv/bin/activate
python3 manim-shorts-tui.py
# → Step 1: pilih WAV (narasi)
# → Step 2: pilih SRT (timed text)
# → Step 3: preview segments + total duration
# → Step 4: output path (default HDD/manim-shorts/{stem}-shorts.mp4)
# → Konfirmasi → render → mux → MP4 final
```

### Pipeline integrasi

```
edge-tts Narration (ID) ──┐
gemini-tts Narration (JV) ┤──→ manim-shorts-tui #17 (input juga: SRT dari whisper-tui #8)
manual ElevenLabs WAV     ┘    → HDD/manim-shorts/{stem}-shorts.mp4
```

Konten original (BUKAN dubbing workflow). Cocok untuk Shorts infografis/edukasi 30-40s.

## mix-tui v3.11 — 6 mode + logo + force 1080p + audio 48000Hz + 1:1 square mode (VLC confirmed)

> **v3.11 (14 Nov 2026):** mode baru `1:1 square (1080x1080)` — center crop source vertical
> (atas+bawah dipotong, full width dipertahankan) untuk IG feed. Hanya muncul kalau source
> vertical (h > w), hanya jalur Burn SRT (B/D/F). Mode lama tidak dihapus.
> **Status: ✅ VLC confirmed 14 Nov 2026** (2 test, dua-duanya OK):
> (1) Mode F source 202x360 (low-res) → 1080x1080 upscale 5.3x, 3j1m, 2789 MB, 19m2s, subs sharp;
> (2) Mode F source 1440x2560 (4K high-res) → 1080x1080 downscale 1.33x, 2j30m, 2361 MB, 15m45s,
> background crisp + subs sharp, ducking + hardsub + logo OK. Resolusi output = fungsi sumber
> (bukan bug): low-res source = soft background, high-res source = crisp. 1:1 encode ~1.7x
> lebih cepat dari vertical 1080x1920 (1.17MP vs 2.07MP per frame).

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
pip3 install questionary edge-tts yt-dlp torchaudio demucs numpy faster-whisper google-genai replicate requests
brew install ffmpeg
# Optional (TUI #15 gemini-tts-tui): set GEMINI_API_KEY
echo "GEMINI_API_KEY=AIza..." >> /Volumes/HDD/Dubbing/.env
# Optional (TUI #16 talkinghead-tui): set REPLICATE_API_TOKEN
echo "REPLICATE_API_TOKEN=r8_xxx..." >> /Volumes/HDD/Dubbing/.env
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

# Alur TALKING-HEAD (workflow konten — foto green screen + narasi JV)
python3 gemini-tts-tui.py    # Narration mode (JV) → narasi-jawa.wav
python3 talkinghead-tui.py   # foto green screen + narasi-JV → {stem}-talking-green.mp4
# Edit manual: chroma key di DaVinci/Premiere → composite background → final-konten.mp4

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
curl -L -o gemini-tts-tui.py "https://raw.githubusercontent.com/emailnyamahmud-afk/srt-splitter/main/scripts/gemini-tts-tui.py"
curl -L -o gemini_tts_backend.py "https://raw.githubusercontent.com/emailnyamahmud-afk/srt-splitter/main/scripts/gemini_tts_backend.py"
curl -L -o talkinghead-tui.py "https://raw.githubusercontent.com/emailnyamahmud-afk/srt-splitter/main/scripts/talkinghead-tui.py"
curl -L -o talkinghead_backend.py "https://raw.githubusercontent.com/emailnyamahmud-afk/srt-splitter/main/scripts/talkinghead_backend.py"
curl -L -o manim-shorts-tui.py "https://raw.githubusercontent.com/emailnyamahmud-afk/srt-splitter/main/scripts/manim-shorts-tui.py"
```
