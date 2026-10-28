# AGENTS.md

> Dibaca AI di awal setiap session. Update: 26 Okt 2026.

## Project: SRT Splitter + Dubbing Jawa

Pipeline: yt-dlp → Demucs → srt-editor-tui → edge-tts → mix-tui → shorts-tui → shorts-csv-tui → YouTube Studio
Kamus: jv.wiktionary.json (lembar kerja) → Supabase (terverifikasi)
Shorts: Dola AI skill `shorts-json` (upload SRT → ketik "buat shorts" → JSON 60 segment)

## 11 TUI

| # | TUI | Status |
|---|-----|--------|
| 1 | yt-dlp-tui v6.2 (MP4+MP3+SRT, cookies anti-bot YT/FB/TikTok/IG) | ✅ Production (FB+YT confirmed) |
| 2 | demucs-tui | ✅ Production |
| 3 | kamus-tui v16 | ✅ Production (audit pending) |
| 4 | Web app | ⚠ Prototype |
| 5 | SRT editor (web, pakai SRT ID) | ⏳ Pending |
| 6 | edge-tts-tui v7.4 (paralel-safe, lock file, 429 retry) | ✅ Production |
| 7 | mix-tui v3.8.2 (6 mode, MUTE + logo + fade 100ms) | ✅ Production (all tested) |
| 8 | whisper-tui v1.1 (faster-whisper, SRT from audio) | ✅ Production (SRT quality 90-95%) |
| 9 | srt-editor-tui v1.0.1 (fix typo SRT hasil translate, glossary bulk replace) | ✅ Production |
| 10 | shorts-tui v1.0 (pecah MP4 final jadi N shorts via JSON timestamps AI) | ✅ Production (60/60 sukses, 94s total, stream copy) |
| 11 | shorts-csv-tui v1.0 (metadata CSV + manifest untuk YouTube Studio) | 🆕 New |

## Struktur Folder

- SSD `~/Dubbing/` — scripts (.py) + venv + jv.wiktionary.json
- HDD `/Volumes/HDD/Dubbing/` — data (input, demucs, tts, mix, .env)
- `config.py` — base path, `ensure_hdd()`, `ensure_kamus()`, `load_env()`

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

## Status (25 Okt 2026)

### Kamus
- 44.585 entries, 8.618 dengan indo (cross-ref), 2.165 lengkap 3-field
- User validasi manual di kamus-tui, mark READY, upload Supabase

### Pipeline produksi (6 film tested, 6 mode production-ready)
- yt-dlp v6.2 MP3 output: ✅ (FB+YT confirmed, cookies anti-bot)
- demucs v2 (segment 4, MPS): ✅
- edge-tts v7.4 (paralel-safe, lock file + 429 retry): ✅
- srt-editor-tui v1.0.1: ✅ (glossary 19 entries, 144 replacement di S2-FB-Mandarin)
- mix-tui v3.8.2: 6 mode production-ready + logo + fade 100ms
- shorts-tui v1.0: ✅ (60/60 sukses test, stream copy 94s total, JSON dari Dola skill shorts-json)
- shorts-csv-tui v1.0: ✅ (metadata CSV + manifest untuk YouTube Studio, test dengan S5 JSON 60 segment)

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
- User: workflow film berikutnya (pilih 1 dari 3 alur: PROPER/CEPAT/MUTE)
- User: Shorts pipeline (Dola → shorts-tui → shorts-csv-tui → YouTube Studio upload)
- AI: web app Jawa (TUI #4) — penyesuaian lookup kamus dari Supabase
- AI (optional): bug cosmetic (filename double `-id`, progress bar `ETA=?ss` glitch)

## Catatan PAT

PAT user exposure di chat (≥21x). User WAJIB revoke sebelum tidur:
→ GitHub → Settings → Developer settings → Personal access tokens → Revoke
