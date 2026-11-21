# Scripts — SRT Splitter + Dubbing Multi-Bahasa

Python TUI untuk workflow dubbing bahasa eksternal → Indonesia / Jawa / Sunda.

## 17 TUI

| # | TUI | Status |
|---|-----|--------|
| 1 | yt-dlp-tui.py v6.5 (MP4+MP3+multi-SRT ID+EN, cookies anti-bot, default 1080p) | ✅ Production |
| 2 | demucs-tui.py (M1 MPS) | ✅ Production |
| 3 | kamus-tui.py v16 | ✅ Production (audit) |
| 4 | Web app | ⚠ Prototype |
| 5 | SRT editor (web) | ⏳ Pending |
| 6 | edge-tts-tui.py v7.5 (SRT + Narration mode, ID only, paralel-safe) | ✅ Production default |
| 7 | mix-tui.py v3.11 (force 1080p + audio 48000Hz stereo + 1:1 square mode) | ✅ Production (1:1 VLC confirmed 14 Nov 2026) |
| 8 | whisper-tui.py v2.1 (whisper.cpp, Metal GPU) | ✅ Production |
| 9 | srt-editor-tui.py v1.0.0 (fix typo SRT translate) | ✅ Production |
| 10 | shorts-tui.py v1.1 (Shorts via AI JSON atau Part via SRT) | ✅ Production |
| 11 | shorts-csv-tui.py v1.0 (metadata CSV + manifest YouTube) | ✅ Production |
| 12 | merge-tui.py v1.9 (full format detect, stream copy / standardize) | ✅ Production (VLC confirmed) |
| 13 | review-mix-tui.py v1.0 (review film: MP4 + JSON + narasi → final MP4) | ⚠ UNTESTED (code di GitHub, belum diuji di Mac) |
| 14 | konten-tui.py v1.0 (konten sejarah: narasi + images → Ken Burns video) | ⚠ UNTESTED (code di GitHub, belum diuji di Mac) |
| 15 | **gemini-tts-tui.py v1.1** (SRT + Narasi, ID + JV, OPSI TAMBAHAN) | ⚠ UNTESTED (code di GitHub, belum diuji di Mac) |
| 16 | **talkinghead-tui.py v1.0** (SadTalker via Replicate, green screen preserved) | ⚠ UNTESTED (code di GitHub, belum diuji di Mac) |
| 17 | **manim-shorts-tui.py v0.1** (WAV + SRT → infografis Shorts video, manim animation vertical 9:16) | ⚠ UNTESTED (sandbox OK 19 Nov 2026 + fix 21 Nov 2026, belum diuji di Mac) |

## Pipeline

```
[PROPER]       yt-dlp → srt-editor → demucs → edge-tts → mix Full (A/B)
[CEPAT]        yt-dlp → srt-editor → edge-tts → mix Simple (C/D)
[MUTE]         yt-dlp → srt-editor → edge-tts → mix Original (E/F)
[SHORTS]       mix-tui → Dola AI → shorts-tui → shorts-csv-tui → YouTube Studio
[MERGE]        mix-tui × N → merge-tui (stream copy) → 1 video panjang
[REVIEW]       edge-tts Narration (ID) → review-mix-tui (review film ID)
[KONTEN]       edge-tts Narration (ID) → konten-tui (konten sejarah ID)
[GEMINI-SRT]   yt-dlp → srt-editor → gemini-tts-tui (SRT mode, ID/JV) → mix-tui (opsional Jawa/karakter)
[GEMINI-NARASI] naskah.txt → gemini-tts-tui (Narration mode, ID/JV) → review-mix-tui / konten-tui (Jawa)
[TALKING-HEAD] naskah.txt → gemini-tts-tui Narration (JV) → talkinghead-tui v1.0 (Replicate SadTalker, preprocess=full) → MP4 green screen preserved → editor chroma key → final-konten.mp4
[MANIM-SHORTS] WAV narasi (edge-tts/gemini-tts Narration atau manual) + SRT (whisper-tui) → manim-shorts-tui v0.1 → HDD/manim-shorts/{stem}-shorts.mp4 (infografis Shorts vertical 9:16)
```

## Scripts

| Script | TUI # | Fungsi | Output |
|--------|-------|--------|--------|
| yt-dlp-tui.py v6.5 | 1 | Download MP4 + MP3 + multi-SRT (ID+EN) | HDD/input/ |
| demucs-tui.py | 2 | Vocal separation (M1 MPS) | HDD/demucs/ |
| kamus-tui.py v16 | 3 | TUI editor jv.wiktionary.json | SSD |
| edge-tts-tui.py v7.5 | 6 | TTS SRT + Narasi (Indonesia, paralel-safe) | HDD/tts/ |
| mix-tui.py v3.11 | 7 | Final mix (force 1080p, audio 48000Hz stereo, +1:1 square mode VLC confirmed) | HDD/mix/ |
| whisper-tui.py v2.1 | 8 | Generate SRT dari audio (Metal GPU) | HDD/input/ |
| srt-editor-tui.py v1.0.0 | 9 | Fix typo SRT hasil translate | HDD/input/ |
| shorts-tui.py v1.1 | 10 | Pecah MP4 jadi shorts/parts | HDD/shorts/ atau HDD/parts/ |
| shorts-csv-tui.py v1.0 | 11 | Metadata CSV + manifest YouTube | HDD/shorts/ |
| merge-tui.py v1.9 | 12 | Gabungin multi-video (stream copy / standardize) | HDD/merged/ |
| review-mix-tui.py v1.0 | 13 | Review film (MP4 + JSON + narasi → final MP4) | HDD/review/ |
| konten-tui.py v1.0 | 14 | Konten sejarah (narasi + images → Ken Burns video) | HDD/konten/ |
| gemini-tts-tui.py v1.1 | 15 | TTS SRT + Narasi (Indonesia + Jawa, OPSI TAMBAHAN) | HDD/tts/ |
| gemini_tts_backend.py | 15 | Backend modul untuk gemini-tts-tui (Gemini API legacy) | — |
| talkinghead-tui.py v1.0 | 16 | Talking head video (SadTalker via Replicate, green screen preserved) | HDD/konten/ |
| talkinghead_backend.py | 16 | Backend modul untuk talkinghead-tui (Replicate API) | — |
| manim-shorts-tui.py v0.1 | 17 | Shorts infografis (WAV + SRT → manim animation video vertical 9:16) | HDD/manim-shorts/ |
| config.py | — | Base path SSD/HDD | — |
| upload-supabase.py | — | Upload kamus ke Supabase | — |
| GEMINI_TTS.md | 15 | Dokumentasi TUI #15 (cara pakai, kapan pakai) | — |
| TALKINGHEAD.md | 16 | Dokumentasi TUI #16 (workflow green screen + Replicate) | — |

## Struktur Path (dari config.py)

```
SSD ~/Dubbing/                          → scripts + venv + jv.wiktionary.json
HDD /Volumes/HDD/Dubbing/              → input/ demucs/ tts/ mix/ shorts/ parts/ merged/ review/ konten/ .env
```

config.py menyediakan (baca LENGKAP sebelum kerja):
- `ensure_hdd()`, `ensure_kamus()`, `load_env()` — helper functions
- `SSD_HOME`, `HDD_BASE` — base paths
- `INPUT_DIR`, `DEMUCS_DIR`, `TTS_DIR`, `MIX_DIR`, `SHORTS_DIR`, `PARTS_DIR`,
  `MERGED_DIR`, `REVIEW_DIR`, `KONTEN_DIR` — 9 subfolder HDD
- `KAMUS_JSON`, `ENV_FILE`, `SCRIPTS_DIR` — config paths

### Tabel INPUT + OUTPUT per TUI (alur data lengkap)

| # | TUI | INPUT (dari mana) | OUTPUT (ke mana) |
|---|-----|------------------|------------------|
| 1 | yt-dlp-tui | URL YouTube/FB/TikTok/IG | `INPUT_DIR` (*.mp4, *.mp3, *.id.srt, *.en.srt) |
| 2 | demucs-tui | `INPUT_DIR` (*.mp3 dari yt-dlp) | `DEMUCS_DIR`/htdemucs/{prefix}-audio/no_vocals.mp3 |
| 3 | kamus-tui | `KAMUS_JSON` (jv.wiktionary.json di SSD) | Edit in-place + upload Supabase |
| 6 | edge-tts-tui SRT | `INPUT_DIR` (*.final.srt) | `TTS_DIR`/{prefix}-audio-id-dub.wav + cache + lock |
| 6 | edge-tts-tui Narasi | naskah.txt (cwd atau `REVIEW_DIR`) | `TTS_DIR`/{stem}-narasi.wav |
| 7 | mix-tui | `INPUT_DIR` (*.mp4, *.mp3) + `DEMUCS_DIR` (no_vocals) + `TTS_DIR` (*.wav dub) + `INPUT_DIR`/*.srt | `MIX_DIR`/{prefix}-id-*.mp4 |
| 8 | whisper-tui | `INPUT_DIR` (*.mp3 dari yt-dlp) | `INPUT_DIR`/{base}.zh.srt + {base}.en.srt |
| 9 | srt-editor-tui | `INPUT_DIR` (*.id.srt) | `INPUT_DIR`/{prefix}.final.srt + .srt.bak + .working.json |
| 10 | shorts-tui Shorts | `MIX_DIR` (*.mp4) + `SHORTS_DIR`/`MIX_DIR` (*.json dari Dola) | `SHORTS_DIR`/{film}/short-001.mp4 s/d short-N.mp4 |
| 10 | shorts-tui Part | `MIX_DIR` (*.mp4) + `INPUT_DIR`/`MIX_DIR` (*.srt) | `PARTS_DIR`/{film}/part-001.mp4 s/d part-N.mp4 |
| 11 | shorts-csv-tui | `SHORTS_DIR` (*.json dari Dola) + folder MP4 (shorts-tui output) | `SHORTS_DIR`/{film}.metadata.csv + {film}.manifest.txt |
| 12 | merge-tui | `MIX_DIR` (*.mp4 — multi-file) | `MERGED_DIR`/{first-name}-merged.mp4 |
| 13 | review-mix-tui | `INPUT_DIR`/`REVIEW_DIR` (*.mp4) + `INPUT_DIR`/`REVIEW_DIR` (*.json dari Z.ai) + `TTS_DIR`/`REVIEW_DIR` (*.wav narasi) | `REVIEW_DIR`/{mp4-stem}-review.mp4 |
| 14 | konten-tui | `TTS_DIR`/`KONTEN_DIR` (*.wav narasi) + `INPUT_DIR`/`KONTEN_DIR` (*.json) + `INPUT_DIR`/`KONTEN_DIR` (folder images) + `INPUT_DIR`/`KONTEN_DIR` (*.mp3 backsound, opsional) | `KONTEN_DIR`/konten-final.mp4 |
| 15 | gemini-tts-tui SRT | `INPUT_DIR` (*.srt) | `TTS_DIR`/{prefix}-audio-id-dub.wav + cache + lock |
| 15 | gemini-tts-tui Narasi | naskah.txt (`TTS_DIR`/`REVIEW_DIR`/cwd) | `TTS_DIR`/{stem}-narasi.wav |
| 16 | talkinghead-tui | `KONTEN_DIR`/`INPUT_DIR`/cwd (*.jpg/*.png foto green screen) + `TTS_DIR`/cwd (*.wav narasi JV) | `KONTEN_DIR`/{audio-stem}-talking-green.mp4 |
| 17 | manim-shorts-tui | `TTS_DIR`/`INPUT_DIR`/cwd (*.wav narasi) + `INPUT_DIR`/`TTS_DIR`/cwd (*.srt dari whisper-tui) | `MANIM_SHORTS_DIR`/{stem}-shorts.mp4 |

### Pipeline alur data (visual flow)

```
yt-dlp-tui (#1)
    ↓ output ke INPUT_DIR
    ├── *.mp4, *.mp3, *.id.srt
    │
    ├──→ whisper-tui (#8) → INPUT_DIR/{base}.zh.srt + .en.srt
    ├──→ srt-editor-tui (#9) → INPUT_DIR/{prefix}.final.srt
    ├──→ demucs-tui (#2) → DEMUCS_DIR/.../no_vocals.mp3
    │
    ├──→ edge-tts-tui #6 SRT  ──┐
    ├──→ gemini-tts-tui #15 SRT ┤
    │   (input: INPUT_DIR/*.final.srt)
    │   (output: TTS_DIR/{prefix}-audio-id-dub.wav)
    │                              ↓
    │                              ↓ input mix-tui
    │                              ↓
    └──→ mix-tui (#7)
        (input: INPUT_DIR/*.mp4 + DEMUCS_DIR/no_vocals.mp3 + TTS_DIR/*.wav + INPUT_DIR/*.srt)
        ↓ output ke MIX_DIR/{prefix}-id-*.mp4
        │
        ├──→ merge-tui (#12) → MERGED_DIR/{first-name}-merged.mp4
        ├──→ shorts-tui #10 Shorts → SHORTS_DIR/{film}/short-*.mp4
        ├──→ shorts-tui #10 Part → PARTS_DIR/{film}/part-*.mp4
        └──→ shorts-csv-tui #11 → SHORTS_DIR/{film}.metadata.csv + .manifest.txt

edge-tts #6 Narasi ──┐
gemini-tts #15 Narasi ┤
    (input: naskah.txt)
    (output: TTS_DIR/{stem}-narasi.wav)
    ↓
    ├──→ review-mix-tui #13 (input juga: INPUT_DIR/*.mp4 + INPUT_DIR/*.json dari Z.ai)
    │   → REVIEW_DIR/{mp4-stem}-review.mp4
    │
    ├──→ konten-tui #14 (input juga: INPUT_DIR/*.json + folder images + optional backsound.mp3)
    │   → KONTEN_DIR/konten-final.mp4
    │
    └──→ talkinghead-tui #16 (input juga: KONTEN_DIR/INPUT_DIR/*.jpg foto green screen)
        → KONTEN_DIR/{audio-stem}-talking-green.mp4
        ↓
        User edit manual: chroma key → composite background → final-konten.mp4 (siap YouTube)

    └──→ manim-shorts-tui #17 (input juga: SRT dari whisper-tui #8)
        → MANIM_SHORTS_DIR/{stem}-shorts.mp4 (infografis Shorts vertical 9:16)
```

### Catatan path penting

- `INPUT_DIR` = sumber utama multifungsi: output yt-dlp + tempat user taruh file manual (foto green screen, JSON dari Dola/Z.ai, backsound.mp3, logo.png)
- `TTS_DIR` = output TUI TTS + input TUI downstream (mix-tui pakai dub, review/konten/talkinghead/manim-shorts pakai narasi)
- `KONTEN_DIR` = output 2 TUI berbeda: konten-tui #14 (Ken Burns, video panjang) + talkinghead-tui #16 (talking head green screen)
- `MANIM_SHORTS_DIR` = output manim-shorts-tui #17 (infografis Shorts vertical, WAV+SRT→manim video)
- `REVIEW_DIR` = output review-mix-tui + tempat search input (user bisa pindah file ke sini)
- Fallback: kalau HDD tidak colok → TUI pakai cwd (current working directory)

## Install

```bash
cd ~/Dubbing && source venv/bin/activate
pip3 install questionary edge-tts yt-dlp torchaudio demucs numpy google-genai replicate requests
brew install ffmpeg
# Optional (TUI #15 gemini-tts-tui): set GEMINI_API_KEY
echo "GEMINI_API_KEY=AIza..." >> /Volumes/HDD/Dubbing/.env
# Optional (TUI #16 talkinghead-tui): set REPLICATE_API_TOKEN
echo "REPLICATE_API_TOKEN=r8_xxx..." >> /Volumes/HDD/Dubbing/.env
```

## Workflow

```bash
cd ~/Dubbing && source venv/bin/activate

# Alur MUTE (skip Demucs, MUTE COMPLETE)
python3 yt-dlp-tui.py         # 1. MP4 + MP3 + multi-SRT (ID+EN)
python3 srt-editor-tui.py      # 2. Fix typo SRT (opsional)
python3 edge-tts-tui.py        # 3. Generate dub dari SRT (default production, Indonesia)
python3 mix-tui.py             # 4. Mix Mode F (force 1080p + audio 48000Hz)

# Alur MERGE (gabungin series)
python3 merge-tui.py           # 5. Stream copy (super cepat, ~2 menit)

# Alur SHORTS
python3 shorts-tui.py         # 6. Pecah jadi 60 shorts
python3 shorts-csv-tui.py      # 7. Metadata CSV + manifest

# Alur REVIEW (review film dengan narasi)
python3 edge-tts-tui.py       # Narasi mode (ID) → narasi-ID.wav
python3 review-mix-tui.py     # MP4 + JSON + narasi → review-final.mp4

# Alur KONTEN (konten sejarah dengan Ken Burns)
python3 edge-tts-tui.py       # Narasi mode (ID) → narasi-ID.wav
python3 konten-tui.py         # narasi + images + backsound → konten-final.mp4

# Alur GEMINI (opsional — Jawa / karakter spesifik / narasi Jawa)
python3 gemini-tts-tui.py     # Mode: SRT (dub per cue) atau Narration (naskah → 1 WAV)
# Output: SRT → {prefix}-audio-id-dub.wav (mix-tui compatible)
#         Narasi → {stem}-narasi.wav (review-mix-tui / konten-tui / talkinghead-tui compatible)

# Alur TALKING-HEAD (workflow konten — foto green screen + narasi JV)
python3 gemini-tts-tui.py     # Narration mode (JV) → narasi-jawa.wav
python3 talkinghead-tui.py    # foto green screen + narasi-JV → {stem}-talking-green.mp4
# Output: HDD/konten/{stem}-talking-green.mp4 (green screen preserved, preprocess=full)
# Edit manual: chroma key di DaVinci/Premiere → composite background → final-konten.mp4

# Kamus (parallel)
python3 kamus-tui.py
```

## edge-tts-tui v7.5 — Production Default (SRT + Narasi)

2 mode (mirror pattern):
- **SRT mode**: Dub per cue dari subtitle (Indonesia only)
- **Narration mode**: 1 naskah plain text → 1 WAV (Indonesia only) → feed review-mix-tui / konten-tui

Paralel-safe: 2-3 TTS paralel di terminal berbeda. Lock file detect prefix collision.

| Instance | RAM | Mac 16GB |
|----------|-----|---------|
| 1 | ~1.6 GB | Aman |
| 2 | ~3.2 GB | Aman |
| 3 | ~4.8 GB | Aman |

Free, no API key, unlimited. Cocok untuk produksi Indonesia stabil.

## review-mix-tui v1.0 — TUI #13 (UNTESTED, code di GitHub belum diuji di Mac)

Review film: potong adegan + narasi + text overlay.

Input:
1. MP4 (video source, resolusi bebas)
2. timestamps.json (dari Z.ai skill, format: `[{start, end, title}]`)
3. narasi.wav (dari edge-tui v7.5 Narasi ID atau gemini-tui v1.1 Narasi JV)

Output: `HDD/review/review-final.mp4` (video terpotong + audio narasi + text overlay per adegan)

4 fase: potong MP4 per segment (stream copy) → concat → generate overlay SRT → mix video + narasi + burn overlay (VideoToolbox M1 GPU).

## konten-tui v1.0 — TUI #14 (UNTESTED, code di GitHub belum diuji di Mac)

Konten sejarah: images → video + narasi + Ken Burns effect.

Input:
1. narasi.wav (dari edge-tui v7.5 Narasi ID atau gemini-tui v1.1 Narasi JV)
2. timestamps.json (dari Z.ai skill, format: `[{start, end, image_prompt, title}]`)
3. Folder images (01.jpg, 02.jpg, ... dari Google Flow)
4. (opsional) backsound.mp3 (dari Suno atau sumber lain)

Output: `HDD/konten/konten-final.mp4` (1920x1080, Ken Burns effect, text overlay, audio narasi + backsound)

5 fase: load images (urut sesuai JSON match by index) → Ken Burns per image (zoompan alternate zoom-in/zoom-out) → overlay SRT (3 detik tampil) → concat all image videos → mix video + narasi + backsound + burn overlay.

## gemini-tts-tui v1.1 — TUI #15 OPSI TAMBAHAN (SRT + Narasi, ID + JV)

⚠ UNTESTED (code di GitHub, belum diuji di Mac). Bukan pengganti edge-tts-tui v7.5 (yang tetap production default).

2 mode (sama dengan edge-tts-tui v7.5):
- **SRT mode** (7 step TUI): SRT → output → bahasa → voice → instruction → Smart Fit → prefix
  → Output: `HDD/tts/{prefix}-audio-id-dub.wav` (24kHz mono 16-bit, mix-tui compatible)
- **Narration mode** (6 step TUI): naskah.txt → output → bahasa → voice → instruction → rate
  → Output: `HDD/tts/{stem}-narasi.wav` (48kHz stereo 16-bit, review-mix-tui / konten-tui compatible)

**Bahasa**: Indonesia (id) + Jawa (jv). Instruction template filter per bahasa.

**Kapan pakai**:
- Bahasa Jawa (krama/ngoko) — Cruz + jawa-halus-mc → user tested OK
- Karakter spesifik (MC/adat, narator dokuser, dialog dramatis)
- Bahasa eksotis (Italia, Jepang, dll) yang tidak ada di Edge TTS
- JANGAN pakai untuk produksi Indonesia umum (Edge TTS lebih stabil + free)

**Pipeline integrasi**:
- SRT mode (JV) → `mix-tui` (final film Jawa)
- Narration mode (JV) → `review-mix-tui` (review film Jawa) atau `konten-tui` (konten sejarah Jawa)

**Setup**: `echo "GEMINI_API_KEY=AIza..." >> /Volumes/HDD/Dubbing/.env`
**Pakai**: `python3 gemini-tts-tui.py`
**Detail lengkap**: lihat `scripts/GEMINI_TTS.md`

### Voice — 30 resmi Google + 1 tested

Default: **Cruz** (Extended Voice Library, TIDAK di 30 resmi tapi user tested OK untuk Jawa).
Fallback kalau Cruz gagal: Charon, Schedar, Alnilam, Rasalgethi.
Lihat: `python3 gemini_tts_backend.py --list-voices`

### Instruction templates (8 + custom, filter per bahasa)

- Indonesia: default, id-narasi, id-narasi-w, id-dialog
- Jawa: jawa-halus-mc, jv-narasi, jv-narasi-w, jv-dialog
- Custom: ketik sendiri
- Lihat: `python3 gemini_tts_backend.py --list-instructions`

### Limit Gemini free tier

| Tier | RPM | RPD | Cocok untuk |
|------|-----|-----|-------------|
| Free (AI Studio) | 5-15 | 100-250 | Test single, file pendek |
| AI Pro ($20/bln) | Higher di Playground | — | Iterasi cepat |
| Tier 1 (Cloud Billing) | 300 | 1000 | Batch sedang |
| Tier 2 ($100+ spend) | 1000+ | 10000+ | Batch besar |

## talkinghead-tui v1.0 — TUI #16 OPSI TAMBAHAN (SadTalker via Replicate, green screen preserved)

⚠ UNTESTED (code di GitHub, belum diuji di Mac). Untuk workflow KONTEN (BUKAN dubbing).

### Workflow:
```
naskah.txt → gemini-tts-tui v1.1 Narration (JV) → narasi-jawa.wav
              ↓
              + foto green screen half-body (mis. amat-avatar.jpg)
              ↓
              talkinghead-tui v1.0 (Replicate SadTalker, preprocess=full, still, gfpgan)
              ↓
              → HDD/konten/{name}-talking-green.mp4 (green screen DIPERTAHANKAN)
              ↓
              User edit manual (DaVinci / Final Cut / Premiere):
              - Chroma key green → hilang
              - Composite dengan background baru (foto sejarah, kantor, dll)
              - Tambah text overlay (opsional)
              → final-konten.mp4 (siap YouTube)
```

### 6 step TUI:
| Step | Pilihan | Default |
|------|---------|---------|
| 1 | Source image (.jpg/.png, foto green screen half-body) | Glob dari `HDD/konten/`, `HDD/input/`, cwd |
| 2 | Driven audio (.wav, dari gemini-tts-tui #15 Narration JV) | Glob dari `HDD/tts/`, cwd |
| 3 | Output MP4 path | `HDD/konten/{audio-stem}-talking-green.mp4` |
| 4 | Preprocess mode (full/extfull/crop/extcrop/resize) | **full** (recommended untuk green screen) |
| 5 | Still mode (yes/no) | **yes** (kurangi gerakan kepala, cocok presenter formal) |
| 6 | Enhancer (gfpgan/none) | **gfpgan** (tajpkan gigi + mata, penting untuk clean chroma key) |

### Kenapa Replicate (BUKAN M1 lokal)?
- SadTalker di M1: Python 3.8 strict, hardcode CUDA, MPS support partial (Issue #526 open)
- Replicate: A100 80GB, ~17 detik per run, ~$0.05-0.20 per video
- Untuk workflow konten (volume rendah-sedang) = sangat reasonable

### Setup & pakai:
```bash
# Set REPLICATE_API_TOKEN di HDD .env
echo "REPLICATE_API_TOKEN=r8_xxx" >> /Volumes/HDD/Dubbing/.env
pip3 install replicate requests

# Pakai
cd ~/Dubbing && source venv/bin/activate
python3 talkinghead-tui.py
```

### Preprocess mode:
- **full** (default): Animasi wajah → paste back ke original background → green screen DIPERTAHANKAN
- extfull: full + extra margin (untuk head tilt banyak)
- crop/extcrop: face only (gak cocok green screen — output = face centered)
- resize: full image scale, animate di atasnya (hybrid)

### Limit Replicate (per Nov 2026):
| Tier | Cost | Cocok untuk |
|------|------|-------------|
| Free credit | $0.10 | Test 2-5 video short |
| Pay-as-you-go | ~$0.05-0.20 per video | Konten sesekali |
| Volume besar | butuh multiple tokens | Paralel banyak video |

Detail lengkap: lihat `scripts/TALKINGHEAD.md`

## manim-shorts-tui v0.1 — TUI #17 Shorts infografis (WAV + SRT → manim video)

⚠ **UNTESTED** — sandbox pipeline OK 19 Nov 2026, belum diuji di Mac user.

Generate video Shorts vertical 9:16 dari WAV narasi + SRT, dengan animasi manim (premium look, gratis, tanpa model AI video mahal).

### Cara kerja
1. Input WAV (edge-tts/gemini-tts Narration atau manual ElevenLabs) + SRT (whisper-tui #8)
2. Parse SRT → segments [{start, end, text}]
3. Generate manim script temp (charcoal bg `#1C1C2E`, FadeIn whole text 0.3s + word-by-word highlight via t2c+Transform (yellow berpindah per kata, text full tetap visible) + FadeOut 0.2s per segment, wrap_text ke multiple lines + adaptive font size 56/48/40)
4. Render manim → video-only MP4 (no audio)
5. Mux video + WAV → final MP4 (ffmpeg, video stream copy + audio aac 48kHz stereo)

Output: `HDD/manim-shorts/{stem}-shorts.mp4` (1080x1920 vertical, 30fps, h264)

### Render time
~0.9x realtime (30s video ≈ 26s render, sedikit lebih lambat dari v0.1 19s karena extra Text objects + Transforms per word untuk highlight). Sandbox test 21 Nov 2026 (fix clipping+highlight, commit 1623907): dummy WAV 30s + 8 SRT segments → MP4 1.5MB, 30.0s (perfect sync), render 26s. edgeClip 0% (text fit width, nggak terpotong), highlight yellow 0.03-0.07% per word terdeteksi.

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

## srt-editor-tui v1.0.0

```bash
python3 srt-editor-tui.py                          # interaktif
python3 srt-editor-tui.py /path/to/file.id.srt     # eksplisit
# Output: .final.srt (untuk edge-tts / gemini-tts), .srt.bak (backup), .working.json (auto-save)
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

## merge-tui v1.9 — VLC CONFIRMED ✅

| Mode | Kecepatan | Syarat |
|------|----------|--------|
| Stream copy | ~2 menit (24 jam) | Semua format sama (6 properties) |
| Standardisasi | ~5-8 min/file (GPU) | Format beda → re-encode per-file |

Auto-detect 6 properties: res + vcodec + acodec + fps + sample_rate + channels.

Test result (30 Okt 2026): 10 file × 24h, sync 100%, stream copy ~2 menit.
