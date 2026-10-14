# AGENTS.md

> Dibaca AI di awal setiap session.

## Project: SRT Splitter + Dubbing Jawa

Pipeline: yt-dlp → Demucs → edge-tts → SRT editor (web) → mix-tui

## Aturan

1. jv.wiktionary.json = SOURCE OF TRUTH. Parsing dari XML dump Wikimedia. DILARANG rusak data.
2. Supabase DB = kamus terverifikasi. User upload manual setelah validasi.
3. AI DILARANG parsing tolol. Baca manual per batch 100 entries kalau perlu.
4. AI DILARANG buang data. Kalau ragu → keterangan, bukan hapus.
5. Register (ngoko/krama) = tugas user native Jawa. AI gak bisa.
6. Standarisasi penulisan = cross-ref jv.wiktionary (penulisan modern).
7. 1 entry = 1 konsep. Sinonim = koma.
8. di- = pasif Jawa VALID. Bukan noise.
9. Template {{ngoko|krama_form}} = krama pasangan, title = ngoko.
10. Kalau AI gak yakin → SKIP. Jangan halu.

## File penting

- `public/jv.wiktionary.json` — 44.585 entries (lembar kerja kamus)
- `scripts/kamus-tui.py` — TUI editor kamus (v15)
- `scripts/yt-dlp-tui.py` — download video/audio
- `scripts/demucs-tui.py` — vocal separation
- `scripts/edge-tts-tui.py` — TTS generation
- `scripts/mix-tui.py` — final mix video
- `scripts/upload-supabase.py` — upload kamus ke DB
- `scripts/parse-jv-wiktionary-v2.py` — parser jv.wiktionary XML (BENAR)

## Status

- jv.wiktionary.json: 44.585 entries, 99% definisi Jawa, 8.618 dgn indo, 2.397 dgn register
- Supabase: kosong (user upload setelah validasi)
- SRT editor web: live di Vercel
- Pipeline dubbing: tested end-to-end (S5, 2j 16m, 3866 cue)
