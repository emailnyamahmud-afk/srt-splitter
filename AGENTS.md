# AGENTS.md

> Dibaca AI di awal setiap session. Update terakhir: 24 Okt 2026.

## Project: SRT Splitter + Dubbing Jawa

Pipeline: yt-dlp → Demucs → edge-tts → SRT editor (web) → mix-tui
Kamus: jv.wiktionary.json (lembar kerja) → Supabase (terverifikasi)

## 7 TUI — Tugas masing-masing (PERMANEN)

| # | TUI | Tugas | Status |
|---|-----|-------|--------|
| 1 | yt-dlp-tui.py | Download MP4 + audio M4A + SRT Indonesia | ✅ Jalan |
| 2 | demucs-tui.py | Split audio → no_vocals.mp3 (SFX bersih) + vocals (auto-hapus) | ✅ Jalan |
| 3 | kamus-tui.py | User edit JSON kamus untuk kurasi manual (sebelum masuk DB) | ✅ Jalan (user audit) |
| 4 | Web app | Translate SRT Indonesia → Jawa (pakai kamus Supabase) | ⚠ Prototype (perlu penyesuaian) |
| 5 | SRT editor | Sementara pakai SRT Indonesia (SRT Jawa = nunggu kamus + web selesai) | ⏳ Pending |
| 6 | edge-tts-tui.py | Generate audio dub dari SRT (5000+ cue, 2-5 jam durasi) | ✅ Jalan |
| 7 | mix-tui.py v3.5 | Mix MP4 + audio → final video (4 mode + pilihan bitrate) | ✅ Production-ready (A,C,D tested) |

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
| `scripts/mix-tui.py` | Final mix video (v3.5 — 4 kombinasi mode + pilihan bitrate) |
| `scripts/upload-supabase.py` | Upload kamus ke DB |
| `scripts/parse-jv-wiktionary-v2.py` | Parser jv.wiktionary XML |

## Status (24 Okt 2026)

### Kamus
- jv.wiktionary.json: 44.585 entries, 99% definisi Jawa, 8.618 dgn indo, 2.397 dgn register, 2.165 LENGKAP
- Bug fix (24 Okt): kamus-tui.py normalisasi field `terjemahan_indo` → `indo` saat load (commit 38e1e9d). 8.618 entries sekarang terbaca di TUI.
- Supabase: kosong (user upload setelah validasi satu-satu)
- User akan lanjut validasi manual tiap entry di kamus-tui (besok, jeda istirahat)

### Pipeline produksi (5 film tested, end-to-end sempurna)
- yt-dlp-tui: ✅ Kepala-Perampok + 5 film lain
- demucs-tui v2: ✅ segment 4 (RAM aman), WAV→ffmpeg MP3 streaming
- edge-tts v7.3.1: ✅ 4565 cue tested (Toko-buku, ~3 jam generate)
- mix-tui v3.3 → v3.4 (24 Okt): 5 film sukses pakai Full + Stream copy

### mix-tui v3.5 (24 Okt 2026, commit feat v3.5 — pilihan bitrate)
- 4 kombinasi mode (2 input × 2 output):
  - ✅ A. Full + Stream copy → `{prefix}-id-final.mp4` (5 film sukses, ~350 MB)
  - ⚠ B. Full + Burn SRT → `{prefix}-id-final-sub.mp4` (low risk, belum user test)
  - ✅ C. Simple + Stream copy → `{prefix}-id-simple.mp4` (1 film sukses: S10-ORI 352.7 MB, 1m 16s, sync 100%)
  - ✅ D. Simple + Burn SRT → `{prefix}-id-simple-sub.mp4` (1 film sukses: S10-ORI 2356 MB @ 2Mbps, 4m 57s, VLC OK)
- Default = Full (backward compatible)
- Ducking PERLU untuk Full mode (SFX/musik latar dari Demucs tetap ada walau vokal dibuang)
- Ducking TIDAK PERLU untuk Simple mode (no SFX, dub copy as-is)
- v3.5 NEW: Step 4.8 — pilih video bitrate untuk Mode B & D (burn SRT wajib re-encode):
  - 1 Mbps → ~1.2 GB/2jam (hemat, quality OK untuk 480p hardsub)
  - 1.5 Mbps → ~1.8 GB/2jam (default, seimbang) — REKOMENDASI
  - 2 Mbps → ~2.3 GB/2jam (current behavior, subtitle paling sharp)
  - 4 Mbps → ~4.5 GB/2jam (HD-ready, kalau source ori high quality)
  - Mode A & C (stream copy) tidak perlu prompt — bitrate ikut MP4 ori
- M1 VideoToolbox 35x hardware = 2.5 jam video di-encode 5 menit (bukan 30 menit estimasi)
- Code audited: py_compile OK, 8 kombinasi (4 bitrate × 2 burn mode) terbentuk benar

## Ducking — Best Practice (PERMANEN)

User pertanyaan: "Apa perlu ducking padahal no_vocals sudah clean dari Demucs?"

Jawaban: **PERLU untuk Full mode**, TIDAK PERLU untuk Simple mode.

Alasan:
- Demucs buang VOKAL ori, tapi SFX/musik latar TETAP ADA di no_vocals.mp3
- Saat dub Indonesia/Jawa bicara, musik latar bisa mendominasi (terutama scene action/emotional)
- Ducking = sidechain compress (turunkan volume SFX saat dub aktif) → standard industry
- Pilihan di mix-tui: 6/12/18 dB (default 12 dB = seimbang) atau 0 dB (no ducking)

Simple mode tidak ada SFX → ducking concept tidak apply → auto-skip.

## Next

- User: test mix-tui v3.4 Mode C & D di Mac (git pull + python3 mix-tui.py)
- User: validasi kamus-tui (8.618 entries dengan indo) satu per satu, mark READY, upload Supabase
- User: validasi 231 entries ngoko+krama yang perlu indo manual
- AI: tunggu feedback user setelah test Mode C/D
- AI: web app Jawa (TUI #4) — penyesuaian lookup kamus dari Supabase
