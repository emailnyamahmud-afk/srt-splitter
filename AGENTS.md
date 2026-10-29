# AGENTS.md

> Dibaca AI di awal setiap session. Update: 29 Okt 2026.

## Anti-Amnesia Protocol (WAJIB baca duluan)

AI sering amnesia tiap session. Untuk hindari:
1. **Baca duluan**: AGENTS.md (ini), README.md, PROJECT_RULES.md, scripts/README.md, scripts/config.py
2. **Jangan ngandalkan memory context** — context panjang = amnesia makin parah
3. **Setiap sesi WAJIB update docs + commit + push** selesai task, biar sesi berikutnya bisa baca
4. **Jangan tebak struktur folder** — baca config.py + README.md dulu
5. **Cek git log** untuk tau state terakhir project

## Project: SRT Splitter + Dubbing Multi-Bahasa

Pipeline dubbing bahasa eksternal (Mandarin, English, Jepang, Italia, dll) → Indonesia / Jawa / Sunda.
- ID: jalan end-to-end (12 TUI production)
- Jawa/Sunda: nunggu kamus Supabase selesai

Pipeline: yt-dlp → Demucs → srt-editor-tui → edge-tts → mix-tui → shorts-tui → shorts-csv-tui → YouTube Studio + merge-tui (gabungin multi-video)
Kamus: jv.wiktionary.json (lembar kerja) → Supabase (terverifikasi)
Shorts: Dola AI skill `shorts-json` (upload SRT → ketik "buat shorts" → JSON 60 segment)

## 12 TUI

| # | TUI | Status |
|---|-----|--------|
| 1 | yt-dlp-tui v6.2 (MP4+MP3+SRT, cookies anti-bot YT/FB/TikTok/IG) | ✅ Production (FB+YT confirmed) |
| 2 | demucs-tui | ✅ Production |
| 3 | kamus-tui v16 | ✅ Production (audit pending) |
| 4 | Web app | ⚠ Prototype |
| 5 | SRT editor (web, pakai SRT ID) | ⏳ Pending |
| 6 | edge-tts-tui v7.4 (paralel-safe, lock file, 429 retry) | ✅ Production |
| 7 | mix-tui v3.8.2 (6 mode, MUTE + logo + fade 100ms) | ✅ Production (all tested) |
| 8 | whisper-tui v2.0 (whisper.cpp, Metal GPU native, 5.3x realtime) | ✅ Production (Metal M1, 20 min for 2h audio) |
| 9 | srt-editor-tui v1.0.1 (fix typo SRT hasil translate, glossary bulk replace) | ✅ Production |
| 10 | shorts-tui v1.1 (pecah MP4: Shorts via AI JSON atau Part via SRT auto-split) | ✅ Production (Shorts 60/60 + Part auto-split) |
| 11 | shorts-csv-tui v1.0 (metadata CSV + manifest untuk YouTube Studio) | ✅ Production (test 60 segment, CSV 19.8 KB + manifest 30.4 KB) |
| 12 | merge-tui v1.0 (gabungin multi-video jadi 1 panjang, 3 mode) | ✅ Production (stream copy + re-encode) |

## Struktur Folder

- SSD `~/Dubbing/` — scripts (.py) + venv + jv.wiktionary.json
- HDD `/Volumes/HDD/Dubbing/` — data (input, demucs, tts, mix, shorts, parts, merged, .env)
- `config.py` — base path: `ensure_hdd()`, `ensure_kamus()`, `load_env()`, `INPUT_DIR`, `DEMUCS_DIR`, `TTS_DIR`, `MIX_DIR`, `SHORTS_DIR`, `PARTS_DIR`, `MERGED_DIR`
- Workflow: `cd ~/Dubbing && source venv/bin/activate && python3 <tui>.py` (BUKAN `python scripts/<tui>.py`)

## Aturan

1. jv.wiktionary.json = SOURCE OF TRUTH. DILARANG rusak data.
2. Supabase DB = kamus terverifikasi. User upload manual setelah validasi.
3. AI DILARANG parsing tolol. Baca manual per batch 100 entries kalau perlu.
4. AI DILARANG buang data. Ragu → keterangan, bukan hapus.
5. Register (ngoko/krama) = tugas user native Jawa. AI gak bisa.
6. 1 entry = 1 konsep. Sinonim = koma.
7. di- = pasif Jawa VALID. Bukan noise.
8. Kalau AI gak yakin → SKIP. Jangan halu.
9. Data di HDD, scripts di SSD. config.py handle path.
10. Ducking ≠ vocal removal. Untuk MUTE → pakai Demucs (Full mode) atau amultiply SRT-driven (Original v3.7.6).
11. Sebutan hormat (Nona Chen, Dokter Chen, Tuan Lin, Paman Zhou, dll) = valid budaya Tiongkok. BUKAN mistranslate. PRESERVE di clean-srt.
12. GT input preference: pakai SRT English (dari whisper-tui) untuk GT English→ID, lebih akurat dari Mandarin→ID.
13. clean-srt workflow: heuristic dulu untuk 2000+ cue, manual per-cue cuma untuk cue critical.

## merge-tui v1.0 — gabungin multi-video jadi 1 panjang

TUI #12. Input: `HDD/mix/*.mp4` (output mix-tui, sudah dub ID + burn sub). Output: `HDD/merged/merged_*.mp4`.

| Mode | Kecepatan | Syarat |
|------|----------|--------|
| [7] Stream copy (concat demuxer + `-c copy`) | ⚡ super cepat | codec+res+fps sama |
| [8] Re-encode + pilih target res (1080p/720p/480p/custom) | 🐢 lambat | res beda |
| [9] Re-encode pakai res file pertama | 🐢 lambat | res beda, ikut file #1 |

Shortcut: ketik `mix` di menu [1] untuk list semua MP4 di `HDD/mix/` (auto-glob).

## mix-tui v3.7.6 — 6 mode

| # | Mode | Ducking | Use case |
|---|------|---------|----------|
| A | Full + Stream | sidechain compress | Proper, no hardsub |
| B | Full + Burn | sidechain compress | Proper + hardsub |
| C | Simple + Stream | no ducking | Cepat, no SFX |
| D | Simple + Burn | no ducking | Cepat + hardsub |
| **E** | **Original + Stream** | **amultiply MUTE COMPLETE** | **Cepat, MUTE, no hardsub** ⭐ |
| F | Original + Burn | amultiply MUTE COMPLETE | Cepat, MUTE + hardsub |

### v3.8.2 Logo + Fade (PERMANEN)
- v3.8: Logo PNG auto-detect, overlay top-right (Mode B/D/F only)
- v3.8.1: Fade 100ms smooth transition (fix "kaget" — user request "transisi mulus")
- v3.8.2: Logo scale 150→100px (user feedback "agak terlalu besar")
- User confirmed: "burn sub dan logo berjalan sempurna"

### v3.7.6 MUTE COMPLETE approach (PERMANEN)

User request: "MP3 ori MUTE TOTAL saat cue, NORMAL saat gap" (bukan reduksi gradual).
Fix: amultiply + inverted envelope WAV (sample-by-sample multiplication).
- envelope = 0.0 saat cue → MP3 ori × 0 = MUTE TOTAL
- envelope = 1.0 saat gap → MP3 ori × 1 = NORMAL
- Fade 1ms di boundary (avoid click)
- 1 SRT Indonesia untuk ducking + burn subtitle (timestamps identik SRT Mandarin)
- Test sandbox: MP3 ori mag 31 (TRUE MUTE, floating noise only)
- User VLC confirm: "mp3 suara ori hening saat dub id bicara"

### v3.7.4 output HDD (PERMANEN)

Default output: `/Volumes/HDD/Dubbing/mix/{filename}.mp4` (langsung ke HDD, no manual move).

## Status (29 Okt 2026)

### Kamus
- 44.585 entries, 8.618 dengan indo (cross-ref), 2.165 lengkap 3-field
- User validasi manual di kamus-tui, mark READY, upload Supabase

### Pipeline produksi (6 film tested, 6 mode production-ready)
- yt-dlp v6.2 MP3 output: ✅ (FB+YT confirmed, cookies anti-bot)
- demucs v2 (segment 4, MPS): ✅
- edge-tts v7.4 (paralel-safe, lock file + 429 retry): ✅
- srt-editor-tui v1.0.1: ✅ (glossary 19 entries, 144 replacement di S2-FB-Mandarin)
- mix-tui v3.8.2: 6 mode production-ready + logo + fade 100ms
- shorts-tui v1.1: ✅ (Shorts 60/60 sukses + Part mode auto-split SRT, stream copy)
- merge-tui v1.0: ✅ (gabungin multi-video jadi 1 panjang, 3 mode: stream copy/re-encode/res-first)
- shorts-csv-tui v1.0: ✅ (metadata CSV + manifest untuk YouTube Studio, test 60 segment S5, CSV 19.8 KB + manifest 30.4 KB)
- clean-srt v1.0 (hybrid): ✅ (manual cues 1-750 + heuristic cues 751-2857, 731/2857 changes, output ke clean-srt/S1_Lima_Tentara.id.clean.srt)

### Test results (PERMANEN — all 6 mode production-ready + logo + fade)
- A (Full + Stream): 5 film sukses (sebelum v3.7)
- B (Full + Burn): low risk, konsep sama dengan A + burn layer
- C (Simple + Stream): VLC sync 100%
- D (Simple + Burn): 1 Mbps user confirmed > ori (hemat 51%)
- E (Original + Stream v3.7.6): VLC confirmed MUTE COMPLETE ⭐
- F (Original + Burn v3.8.2): VLC confirmed burn sub + logo "sempurna" ⭐
  - 480p @ 2 Mbps: 5m 58s, 2152 MB, fade 100ms smooth, logo 100px top-right

## Next

- User: kamus audit (8.618 entries) → mark READY → upload Supabase
- User: workflow film berikutnya (pilih 1 dari 4 alur: PROPER/CEPAT/MUTE/MERGE)
- User: Shorts pipeline (Dola → shorts-tui → shorts-csv-tui → YouTube Studio upload)
- User: test merge-tui (S1+S2+S3+S4 → 1 video panjang)
- AI: web app Jawa (TUI #4) — penyesuaian lookup kamus dari Supabase
- AI (optional): bug cosmetic (filename double `-id`, progress bar `ETA=?ss` glitch)
- AI: clean-srt pending task — hapus honorific entries dari heuristic (Nona Chen, Dokter Chen, Paman Zhou = PRESERVE budaya Tiongkok)

## Catatan PAT

PAT user exposure di chat (≥21x). User WAJIB revoke sebelum tidur:
→ GitHub → Settings → Developer settings → Personal access tokens → Revoke
