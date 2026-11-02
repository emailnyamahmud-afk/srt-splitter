# AGENTS.md

> Dibaca AI di awal setiap session. Update: 2 Nov 2026.

## Anti-Amnesia Protocol

1. Baca duluan: AGENTS.md, README.md, PROJECT_RULES.md, scripts/README.md, scripts/config.py
2. Jangan ngandalkan memory context — context panjang = amnesia
3. Setiap sesi WAJIB update docs + commit + push
4. Jangan tebak struktur folder — baca config.py LENGKAP (semua 11 path, bukan cuma `ensure_hdd` + `TTS_DIR`)
5. Cek git log untuk state terakhir
6. **TUI baru WAJIB update tabel "N TUI" di 4 docs: AGENTS.md, PROJECT_RULES.md, scripts/README.md, README.md root**
7. **Cek file yang sudah ada di repo (`git ls-tree origin/main scripts/`) sebelum pilih nomor TUI baru** — jangan pakai nomor yang sudah dipakai
8. **Workflow: AI sandbox → push GitHub → user pull → test → kalau error → AI fix → push GitHub**

## Project: SRT Splitter + Dubbing Multi-Bahasa

Pipeline dubbing bahasa eksternal → Indonesia / Jawa / Sunda.
- ID: jalan end-to-end (14 TUI production + 1 experimental)
- Jawa: pipeline dub (gemini-tts-tui v1.1 SRT mode) + narasi (gemini-tts-tui v1.1 Narration mode) jalan
- Sunda: nunggu kamus Supabase

## 15 TUI

| # | TUI | Status |
|---|-----|--------|
| 1 | yt-dlp-tui v6.5 (MP4+MP3+multi-SRT ID+EN, default 1080p) | ✅ |
| 2 | demucs-tui | ✅ |
| 3 | kamus-tui v16 | ✅ (audit) |
| 4 | Web app | ⚠ Prototype |
| 5 | SRT editor (web) | ⏳ Pending |
| 6 | edge-tts-tui v7.5 (SRT + Narasi mode, ID only, paralel-safe) | ✅ Production default |
| 7 | mix-tui v3.10 (force 1080p + audio 48000Hz stereo) | ✅ |
| 8 | whisper-tui v2.0 (Metal GPU) | ✅ |
| 9 | srt-editor-tui v1.0.1 | ✅ |
| 10 | shorts-tui v1.1 (Shorts + Part) | ✅ |
| 11 | shorts-csv-tui v1.0 | ✅ |
| 12 | merge-tui v2.0 (full format detect, stream copy / standardize) | ✅ VLC confirmed |
| 13 | review-mix-tui v1.0 (review film: potong + narasi + overlay) | ✅ Production |
| 14 | konten-tui v1.0 (konten sejarah: images → video + narasi + Ken Burns) | ✅ Production |
| 15 | **gemini-tts-tui v1.1** (SRT + Narasi, ID + JV, OPSI TAMBAHAN) | ⚠ EXPERIMENTAL |

## TUI #13: review-mix-tui v1.0 — Review film (production)

Input: MP4 + timestamps.json (dari Z.ai skill) + narasi.wav (dari edge-tui v7.5 / gemini-tui v1.1 Narration)
Output: `HDD/review/review-final.mp4` (video terpotong + audio narasi + text overlay per adegan)

4 fase: potong MP4 per segment → concat → generate overlay SRT → mix video + narasi + burn overlay.

## TUI #14: konten-tui v1.0 — Konten sejarah (production)

Input: narasi.wav + timestamps.json (dari Z.ai skill) + folder images (dari Google Flow) + (opsional) backsound.mp3
Output: `HDD/konten/konten-final.mp4` (1920x1080, Ken Burns effect, text overlay, audio narasi + backsound)

5 fase: load images → Ken Burns per image → overlay SRT → concat → mix video + narasi + backsound + burn overlay.

## TUI #15: gemini-tts-tui v1.1 — OPSI TAMBAHAN Gemini 3.8 Flash TTS

**BUKAN pengganti edge-tts-tui v7.5.** edge-tts-tui v7.5 tetap production default (Indonesia only).
gemini-tts-tui untuk skenario yang Edge kurang bagus / tidak support:
- Bahasa Jawa (krama/ngoko) — user sudah test Cruz + jawa-halus-mc, hasil bagus
- Karakter suara spesifik (MC/adat, narator dokuser, dialog dramatis)
- Bahasa eksotis (Italia, Jepang, dll) yang tidak ada di Edge TTS

**2 Mode (mirror edge-tts-tui v7.5 pattern)**:
- **SRT mode** (7 step TUI): SRT → output → bahasa → voice → instruction → Smart Fit → prefix
  → Output: `HDD/tts/{prefix}-audio-id-dub.wav` (24kHz mono 16-bit, mix-tui compatible)
- **Narration mode** (6 step TUI): naskah.txt → output → bahasa → voice → instruction → rate
  → Output: `HDD/tts/{stem}-narasi.wav` (48kHz stereo 16-bit, review-mix-tui / konten-tui compatible)

**Bahasa**: Indonesia (id) + Jawa (jv). Instruction template filter per bahasa pilihan.

**Pipeline integrasi**:
- SRT mode → feed `mix-tui` (sama dengan edge-tts SRT output)
- Narration mode → feed `review-mix-tui` (review film) atau `konten-tui` (konten sejarah)
- Edge Narasi (ID) → review-mix-tui (review film ID) atau konten-tui (konten ID)
- Gemini Narasi (JV) → review-mix-tui (review film JV) atau konten-tui (konten JV)

**Setup**: `echo "GEMINI_API_KEY=AIza..." >> /Volumes/HDD/Dubbing/.env`
**Pakai**: `python3 gemini-tts-tui.py`
**Detail**: lihat `scripts/GEMINI_TTS.md`

## Struktur Folder (baca config.py LENGKAP)

```
SSD ~/Dubbing/                          → scripts (.py) + venv + jv.wiktionary.json (cepat)
  ├── yt-dlp-tui.py                     # TUI #1
  ├── demucs-tui.py                     # TUI #2
  ├── kamus-tui.py                      # TUI #3
  ├── edge-tts-tui.py                   # TUI #6
  ├── mix-tui.py                        # TUI #7
  ├── whisper-tui.py                    # TUI #8
  ├── srt-editor-tui.py                 # TUI #9
  ├── shorts-tui.py                     # TUI #10
  ├── shorts-csv-tui.py                 # TUI #11
  ├── merge-tui.py                      # TUI #12
  ├── review-mix-tui.py                 # TUI #13
  ├── konten-tui.py                     # TUI #14
  ├── gemini-tts-tui.py                 # TUI #15 (BARU)
  ├── gemini_tts_backend.py             # TUI #15 backend modul
  ├── GEMINI_TTS.md                     # TUI #15 docs
  ├── config.py                         # base path (SSD scripts, HDD data)
  └── venv/

HDD /Volumes/HDD/Dubbing/              → data (besar, dari config.py)
  ├── input/                            # yt-dlp output (MP4, MP3, SRT) — config.INPUT_DIR
  ├── demucs/                           # demucs output (no_vocals) — config.DEMUCS_DIR
  ├── tts/                              # edge-tts + gemini-tts output (dub.wav, narasi.wav, cache) — config.TTS_DIR
  ├── mix/                              # mix-tui output (final MP4) — config.MIX_DIR
  ├── shorts/                           # shorts-tui Shorts mode — config.SHORTS_DIR
  ├── parts/                            # shorts-tui Part mode — config.PARTS_DIR
  ├── merged/                           # merge-tui output (1 file panjang) — config.MERGED_DIR
  ├── review/                           # review-mix-tui output (review-final.mp4) — config.REVIEW_DIR
  ├── konten/                           # konten-tui output (konten-final.mp4) — config.KONTEN_DIR
  ├── jv.wiktionary.json (di SSD!)      # kamus SOURCE OF TRUTH — config.KAMUS_JSON (SSD_HOME)
  └── .env                              # Supabase + GEMINI_API_KEY — config.ENV_FILE
```

- Workflow user: `cd ~/Dubbing && source venv/bin/activate && python3 <tui>.py`
- `config.py` — `ensure_hdd()`, `ensure_kamus()`, `load_env()`, plus 11 path constants
- Kalau HDD tidak colok → semua TUI fallback ke cwd (atau exit dengan pesan "Colok HDD")

## Aturan

1. jv.wiktionary.json = SOURCE OF TRUTH (kamus)
2. Supabase = kamus terverifikasi (user upload manual)
3. AI DILARANG parsing tolol / buang data / halu
4. Register (ngoko/krama) = tugas user, AI gak bisa
5. Data di HDD, scripts di SSD
6. Sebutan hormat Tiongkok (Nona/Tuan/Dokter/Paman) = PRESERVE, bukan mistranslate
7. GT input: SRT English (dari whisper-tui) → GT English→ID lebih akurat
8. **Standarisasi res+audio = kerjaan mix-tui v3.10**, bukan yt-dlp atau merge-tui
9. **merge-tui v2.0** = full format detect (6 properties) + stream copy (super cepat) / standardize (re-encode). VLC confirmed: sync 100%.
10. **fix-merge-audio.py = DELETED** (audio drift, failed experiment)
11. **edge-tts-tui v7.5 = production default** (SRT + Narasi, ID only, paralel-safe, no API key)
12. **review-mix-tui v1.0 = production** (TUI #13) — input narasi dari edge-tts / gemini-tts Narration
13. **konten-tui v1.0 = production** (TUI #14) — input narasi dari edge-tts / gemini-tts Narration
14. **gemini-tts-tui v1.1 = OPSI TAMBAHAN** (TUI #15, SRT + Narasi, ID + JV, butuh GEMINI_API_KEY)
    - Output SRT mode: `HDD/tts/{prefix}-audio-id-dub.wav` (mix-tui compatible)
    - Output Narration mode: `HDD/tts/{stem}-narasi.wav` (review-mix-tui / konten-tui compatible)
    - Jangan hapus / ganti edge-tts-tui v7.5
    - Status EXPERIMENTAL sampai user VLC feedback OK

## Pipeline Final (confirmed end-to-end)

### Pipeline Indonesia (production):
```
yt-dlp v6.5 → srt-editor v1.0.1 → edge-tts v7.5 SRT → mix-tui v3.10 → merge-tui v2.0
                                                                                      ↘ shorts-tui → shorts-csv-tui → YouTube
edge-tts v7.5 Narasi (ID) → review-mix-tui v1.0 (review film ID)
edge-tts v7.5 Narasi (ID) → konten-tui v1.0 (konten sejarah ID)
```

### Pipeline Jawa (experimental, opsional via Gemini):
```
yt-dlp v6.5 → srt-editor v1.0.1 → gemini-tts-tui v1.1 SRT mode (JV) → mix-tui v3.10
naskah.txt → gemini-tts-tui v1.1 Narration mode (JV) → review-mix-tui v1.0 (review film JV)
naskah.txt → gemini-tts-tui v1.1 Narration mode (JV) → konten-tui v1.0 (konten sejarah JV)
```

## Status (2 Nov 2026)

- merge-tui v2.0: ✅ VLC confirmed (10 file × 24h, sync 100%, stream copy ~2 menit)
- mix-tui v3.10: ✅ force 1080p + audio 48000Hz stereo
- yt-dlp v6.5: ✅ multi-SRT ID+EN, default 1080p preferred
- edge-tts-tui v7.5: ✅ production default (SRT + Narasi, ID only, paralel-safe)
- review-mix-tui v1.0: ✅ production (TUI #13)
- konten-tui v1.0: ✅ production (TUI #14)
- gemini-tts-tui v1.1: ⚠ EXPERIMENTAL (TUI #15, SRT + Narasi, ID + JV, opsional — butuh GEMINI_API_KEY)
- Pipeline produksi Indonesia: 6 film tested, all TUI production-ready
- Pipeline Jawa: experimental, tunggu user VLC feedback

## Anti-amnesia untuk AI next session (Pelajaran 2 Nov 2026)

- Jangan amnesia: ada 15 TUI, BUKAN 12/13. Baca `git ls-tree origin/main scripts/` untuk verifikasi
- Jangan amnesia: TUI #13 = review-mix-tui (production), TUI #14 = konten-tui (production), TUI #15 = gemini-tts-tui (experimental)
- Jangan amnesia: `REVIEW_DIR` di config.py untuk review-mix-tui, `KONTEN_DIR` untuk konten-tui
- Jangan amnesia: edge-tts-tui v7.5 Narration mode → feed review-mix-tui / konten-tui (BUKAN langsung ke user)
- Jangan amnesia: gemini-tts-tui v1.1 Narration mode (JV) → alternatif feed untuk review-mix-tui / konten-tui (bahasa Jawa)
- Jangan amnesia: baca config.py LENGKAP, ada 11 path constants, semua dipakai TUI berbeda
- Jangan amnesia: workflow = AI sandbox → push GitHub → user pull → test → kalau error → AI fix → push
