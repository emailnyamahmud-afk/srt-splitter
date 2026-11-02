# AGENTS.md

> Dibaca AI di awal setiap session. Update: 2 Nov 2026.

## Anti-Amnesia Protocol

1. Baca duluan: AGENTS.md, README.md, PROJECT_RULES.md, scripts/README.md, scripts/config.py
2. Jangan ngandalkan memory context — context panjang = amnesia
3. Setiap sesi WAJIB update docs + commit + push
4. Jangan tebak struktur folder — baca config.py
5. Cek git log untuk state terakhir
6. **TUI baru WAJIB update tabel "12 TUI" → "13 TUI" di AGENTS.md, PROJECT_RULES.md, scripts/README.md, README.md root**
7. **Workflow: AI sandbox → push GitHub → user pull → test → kalau error → AI fix → push GitHub**

## Project: SRT Splitter + Dubbing Multi-Bahasa

Pipeline dubbing bahasa eksternal → Indonesia / Jawa / Sunda.
- ID: jalan end-to-end (12 TUI production + 1 experimental)
- Jawa: pipeline dub (gemini-tts-tui v1.1 SRT mode) + narasi (gemini-tts-tui v1.1 Narration mode) jalan
- Sunda: nunggu kamus Supabase

## 13 TUI

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
| 13 | **gemini-tts-tui v1.1** (SRT + Narasi, ID + JV, OPSI TAMBAHAN) | ⚠ EXPERIMENTAL |

## TUI #13: gemini-tts-tui v1.1 — OPSI TAMBAHAN Gemini 3.8 Flash TTS

**BUKAN pengganti edge-tts-tui v7.5.** edge-tts-tui v7.5 tetap production default (Indonesia only).
gemini-tts-tui untuk skenario yang Edge kurang bagus / tidak support:
- Bahasa Jawa (krama/ngoko) — user sudah test Cruz + jawa-halus-mc, hasil bagus
- Karakter suara spesifik (MC/adat, narator dokuser, dialog dramatis)
- Bahasa eksotis (Italia, Jepang, dll) yang tidak ada di Edge TTS

**2 Mode (mirror edge-tts-tui v7.5 pattern)**:
- **SRT mode** (7 step TUI): SRT → output → bahasa → voice → instruction → Smart Fit → prefix
  → Output: `HDD/tts/{prefix}-audio-id-dub.wav` (24kHz mono 16-bit, mix-tui compatible)
- **Narration mode** (6 step TUI): naskah.txt → output → bahasa → voice → instruction → rate
  → Output: `HDD/tts/{stem}-narasi.wav` (48kHz stereo 16-bit, review-mix-tui compatible)

**Bahasa**: Indonesia (id) + Jawa (jv). Instruction template filter per bahasa pilihan.

**Setup**: `echo "GEMINI_API_KEY=AIza..." >> /Volumes/HDD/Dubbing/.env`
**Pakai**: `python3 gemini-tts-tui.py`
**Detail**: lihat `scripts/GEMINI_TTS.md`

## Struktur Folder

- SSD `~/Dubbing/` — scripts (.py) + venv + jv.wiktionary.json
- HDD `/Volumes/HDD/Dubbing/` — data:
  - `input/` (yt-dlp), `demucs/` (vocal separation), `tts/` (edge-tts + gemini-tts output),
  - `mix/` (mix-tui final MP4), `shorts/` (shorts-tui), `parts/` (shorts Part mode),
  - `merged/` (merge-tui), `review/` (review-mix-tui), `konten/` (konten-tui),
  - `.env` (Supabase + GEMINI_API_KEY)
- `config.py` — `ensure_hdd()`, `INPUT_DIR`, `TTS_DIR`, `MIX_DIR`, `MERGED_DIR`, `REVIEW_DIR`, `KONTEN_DIR`, dll
- Workflow: `cd ~/Dubbing && source venv/bin/activate && python3 <tui>.py`

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
11. **edge-tts-tui v7.5 = production default** (SRT + Narasi, ID only, paralel-safe)
12. **gemini-tts-tui v1.1 = OPSI TAMBAHAN** (SRT + Narasi, ID + JV, butuh GEMINI_API_KEY)
    - Jangan hapus / ganti edge-tts-tui v7.5
    - Status EXPERIMENTAL sampai user VLC feedback OK
    - File: `scripts/gemini-tts-tui.py` + `scripts/gemini_tts_backend.py` + `scripts/GEMINI_TTS.md`

## Pipeline Final (confirmed end-to-end)

```
yt-dlp v6.5 (varies, multi-SRT ID+EN)
  → mix-tui v3.10 (force 1080p + audio 48000Hz stereo = STANDARDISASI)
    → merge-tui v2.0 (stream copy ~2 menit, no drift)
      → VLC: sync 100% ✅
```

### Pipeline dengan Gemini (opsional, untuk Jawa / karakter spesifik):
```
yt-dlp v6.5 → srt-editor v1.0.1 → gemini-tts-tui v1.1 (SRT mode, JV) → mix-tui v3.10 → merge-tui v2.0
naskah.txt → gemini-tts-tui v1.1 (Narration mode, JV) → review-mix-tui → final MP4
```

## Status (2 Nov 2026)

- merge-tui v2.0: ✅ VLC confirmed (10 file × 24h, sync 100%, stream copy ~2 menit)
- mix-tui v3.10: ✅ force 1080p + audio 48000Hz stereo
- yt-dlp v6.5: ✅ multi-SRT ID+EN, default 1080p preferred
- edge-tts-tui v7.5: ✅ production default (SRT + Narasi, ID only)
- gemini-tts-tui v1.1: ⚠ EXPERIMENTAL (SRT + Narasi, ID + JV, opsional — butuh GEMINI_API_KEY)
- Pipeline produksi Indonesia: 6 film tested, all TUI production-ready
- Pipeline Jawa: experimental, tunggu user VLC feedback
