# Scripts — SRT Splitter + Dubbing Multi-Bahasa

Python TUI untuk workflow dubbing bahasa eksternal → Indonesia / Jawa / Sunda.

## 13 TUI

| # | TUI | Status |
|---|-----|--------|
| 1 | yt-dlp-tui.py v6.5 (MP4+MP3+multi-SRT ID+EN, cookies anti-bot, default 1080p) | ✅ Production |
| 2 | demucs-tui.py (M1 MPS) | ✅ Production |
| 3 | kamus-tui.py v16 | ✅ Production (audit) |
| 4 | Web app | ⚠ Prototype |
| 5 | SRT editor (web) | ⏳ Pending |
| 6 | edge-tts-tui.py v7.5 (SRT + Narration mode, ID only, paralel-safe) | ✅ Production default |
| 7 | mix-tui.py v3.10 (force 1080p + audio 48000Hz stereo) | ✅ Production |
| 8 | whisper-tui.py v2.0 (whisper.cpp, Metal GPU) | ✅ Production |
| 9 | srt-editor-tui.py v1.0.1 (fix typo SRT translate) | ✅ Production |
| 10 | shorts-tui.py v1.1 (Shorts via AI JSON atau Part via SRT) | ✅ Production |
| 11 | shorts-csv-tui.py v1.0 (metadata CSV + manifest YouTube) | ✅ Production |
| 12 | merge-tui.py v2.0 (full format detect, stream copy / standardize) | ✅ Production (VLC confirmed) |
| 13 | **gemini-tts-tui.py v1.1** (SRT + Narasi, ID + JV, OPSI TAMBAHAN) | ⚠ Experimental |

## Pipeline

```
[PROPER] yt-dlp → srt-editor → demucs → edge-tts → mix Full (A/B)
[CEPAT]  yt-dlp → srt-editor → edge-tts → mix Simple (C/D)
[MUTE]   yt-dlp → srt-editor → edge-tts → mix Original (E/F)
[SHORTS] mix-tui → Dola AI → shorts-tui → shorts-csv-tui → YouTube Studio
[MERGE]  mix-tui × N → merge-tui (stream copy) → 1 video panjang
[GEMINI-SRT]    yt-dlp → srt-editor → gemini-tts-tui (SRT mode) → mix-tui (opsional Jawa/karakter)
[GEMINI-NARASI] naskah.txt → gemini-tts-tui (Narration mode) → review-mix-tui
```

## Scripts

| Script | Fungsi | Output |
|--------|--------|--------|
| yt-dlp-tui.py v6.5 | Download MP4 + MP3 + multi-SRT (ID+EN) | HDD/input/ |
| demucs-tui.py | Vocal separation (M1 MPS) | HDD/demucs/ |
| edge-tts-tui.py v7.5 | TTS SRT + Narasi (Indonesia, paralel-safe) | HDD/tts/ |
| gemini-tts-tui.py v1.1 | TTS SRT + Narasi (Indonesia + Jawa, OPSI TAMBAHAN) | HDD/tts/ |
| gemini_tts_backend.py | Backend modul untuk gemini-tts-tui (Gemini API legacy) | — |
| mix-tui.py v3.10 | Final mix (force 1080p, audio 48000Hz stereo) | HDD/mix/ |
| merge-tui.py v2.0 | Gabungin multi-video (stream copy / standardize) | HDD/merged/ |
| kamus-tui.py v16 | TUI editor jv.wiktionary.json | SSD |
| srt-editor-tui.py v1.0.1 | Fix typo SRT hasil translate | HDD/input/ |
| shorts-tui.py v1.1 | Pecah MP4 jadi shorts/parts | HDD/shorts/ |
| shorts-csv-tui.py v1.0 | Metadata CSV + manifest YouTube | HDD/shorts/ |
| whisper-tui.py v2.0 | Generate SRT dari audio (Metal GPU) | HDD/input/ |
| config.py | Base path SSD/HDD | — |
| upload-supabase.py | Upload kamus ke Supabase | — |
| GEMINI_TTS.md | Dokumentasi TUI #13 (cara pakai, kapan pakai) | — |

## Struktur Path

```
SSD ~/Dubbing/           → scripts + venv + jv.wiktionary.json
HDD /Volumes/HDD/Dubbing/ → input/ demucs/ tts/ mix/ shorts/ parts/ merged/ review/ konten/ .env
```

config.py: `ensure_hdd()`, `ensure_kamus()`, `load_env()`, `INPUT_DIR`, `DEMUCS_DIR`, `TTS_DIR`, `MIX_DIR`, `SHORTS_DIR`, `PARTS_DIR`, `MERGED_DIR`, `REVIEW_DIR`, `KONTEN_DIR`

## Install

```bash
cd ~/Dubbing && source venv/bin/activate
pip3 install questionary edge-tts yt-dlp torchaudio demucs numpy google-genai
brew install ffmpeg
# GEMINI_API_KEY (opsional, untuk TUI #13):
echo "GEMINI_API_KEY=AIza..." >> /Volumes/HDD/Dubbing/.env
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

# Alur GEMINI (opsional — Jawa / karakter spesifik / narasi)
python3 gemini-tts-tui.py     # Mode: SRT (dub per cue) atau Narration (naskah → 1 WAV)
# Output: SRT → {prefix}-audio-id-dub.wav (mix-tui compatible)
#         Narasi → {stem}-narasi.wav (review-mix-tui compatible)

# Kamus (parallel)
python3 kamus-tui.py
```

## edge-tts-tui v7.5 — Production Default (SRT + Narasi)

2 mode (mirror edge-tts-tui v7.5 pattern):
- **SRT mode**: Dub per cue dari subtitle (Indonesia only)
- **Narration mode**: 1 naskah plain text → 1 WAV (Indonesia only)

Paralel-safe: 2-3 TTS paralel di terminal berbeda. Lock file detect prefix collision.

| Instance | RAM | Mac 16GB |
|----------|-----|---------|
| 1 | ~1.6 GB | Aman |
| 2 | ~3.2 GB | Aman |
| 3 | ~4.8 GB | Aman |

Free, no API key, unlimited. Cocok untuk produksi Indonesia stabil.

## gemini-tts-tui v1.1 — OPSI TAMBAHAN (SRT + Narasi, ID + JV)

⚠ EXPERIMENTAL. Bukan pengganti edge-tts-tui v7.5 (yang tetap production default).

2 mode (sama dengan edge-tts-tui v7.5):
- **SRT mode** (7 step TUI): SRT → output → bahasa → voice → instruction → Smart Fit → prefix
  → Output: `HDD/tts/{prefix}-audio-id-dub.wav` (24kHz mono 16-bit, mix-tui compatible)
- **Narration mode** (6 step TUI): naskah.txt → output → bahasa → voice → instruction → rate
  → Output: `HDD/tts/{stem}-narasi.wav` (48kHz stereo 16-bit, review-mix-tui compatible)

**Bahasa**: Indonesia (id) + Jawa (jv). Instruction template filter per bahasa.

**Kapan pakai**:
- Bahasa Jawa (krama/ngoko) — Cruz + jawa-halus-mc → user tested OK
- Karakter spesifik (MC/adat, narator dokuser, dialog dramatis)
- Bahasa eksotis (Italia, Jepang, dll) yang tidak ada di Edge TTS
- JANGAN pakai untuk produksi Indonesia umum (Edge TTS lebih stabil + free)

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

## srt-editor-tui v1.0.1

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

## merge-tui v2.0 — VLC CONFIRMED ✅

| Mode | Kecepatan | Syarat |
|------|----------|--------|
| Stream copy | ~2 menit (24 jam) | Semua format sama (6 properties) |
| Standardisasi | ~5-8 min/file (GPU) | Format beda → re-encode per-file |

Auto-detect 6 properties: res + vcodec + acodec + fps + sample_rate + channels.

Test result (30 Okt 2026): 10 file × 24h, sync 100%, stream copy ~2 menit.
