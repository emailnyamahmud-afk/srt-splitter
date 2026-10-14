# AGENTS.md

> Dibaca AI di awal setiap session. Update terakhir: 15 Okt 2026.

## Project: SRT Splitter + Dubbing Jawa

Pipeline: yt-dlp → Demucs → edge-tts → SRT editor (web) → mix-tui
Kamus: jv.wiktionary.json (lembar kerja) → Supabase (terverifikasi)

## Struktur Folder

- SSD `~/Dubbing/` — scripts (.py) + venv + jv.wiktionary.json (kecil, cepat)
- HDD `/Volumes/HDD/Dubbing/` — data besar (input, demucs, tts, mix, .env)
- `config.py` — base path, `ensure_hdd()`, `ensure_kamus()`, `load_env()`

## Aturan

1. jv.wiktionary.json = SOURCE OF TRUTH. Parsing dari XML dump Wikimedia. DILARANG rusak data.
2. Supabase DB = kamus terverifikasi. User upload manual setelah validasi.
3. AI DILARANG parsing tolol. Baca manual per batch 100 entries kalau perlu.
4. AI DILARANG buang data. Kalau ragu → keterangan, bukan hapus.
5. Register (ngoko/krama) = tugas user native Jawa. AI gak bisa.
6. Standarisasi penulisan = cross-ref jv.wiktionary (penulisan modern).
7. 1 entry = 1 konsep. Sinonim = koma.
8. di- = pasif Jawa VALID. Bukan noise. Jangan buang.
9. Template {{ngoko|krama_form}} = krama pasangan, title = ngoko.
10. Kalau AI gak yakin → SKIP. Jangan halu.
11. Data di HDD, scripts di SSD. config.py handle path.
12. Kalau HDD gak ter-colok, fallback ke cwd.

## File Penting

| File | Fungsi |
|------|--------|
| `public/jv.wiktionary.json` | 44.585 entries (lembar kerja kamus) |
| `scripts/config.py` | Base path SSD/HDD |
| `scripts/kamus-tui.py` | TUI editor kamus (v16) |
| `scripts/yt-dlp-tui.py` | Download video/audio |
| `scripts/demucs-tui.py` | Vocal separation |
| `scripts/edge-tts-tui.py` | TTS generation |
| `scripts/mix-tui.py` | Final mix video |
| `scripts/upload-supabase.py` | Upload kamus ke DB |
| `scripts/parse-jv-wiktionary-v2.py` | Parser jv.wiktionary XML |

## Status (15 Okt 2026)

- jv.wiktionary.json: 44.585 entries, 99% definisi Jawa, 8.618 dgn indo, 2.397 dgn register, 2.165 LENGKAP
- Supabase: kosong (user upload setelah validasi)
- SRT editor web: live di https://srt-splitter.vercel.app/
- Pipeline dubbing ID: tested end-to-end (S5, 2j 16m, 3866 cue)
- Semua TUI updated dgn config.py (HDD path)
- yt-dlp-tui.py tested: ✅ Toko-buku.mp4 + m4a + srt ke HDD/input/

## Next

- User: test workflow end-to-end ID (demucs → edge-tts → mix)
- User: validasi jv.wiktionary.json manual di kamus-tui (isi indo + register)
- AI: update SRT editor web utk lookup kamus dari Supabase
