# AGENTS.md

> Dibaca AI di awal setiap session. Update terakhir: 24 Okt 2026.

## Project: SRT Splitter + Dubbing Jawa

Pipeline: yt-dlp → Demucs → edge-tts → SRT editor (web) → mix-tui
Kamus: jv.wiktionary.json (lembar kerja) → Supabase (terverifikasi)

## 7 TUI — Tugas masing-masing (PERMANEN)

| # | TUI | Tugas | Status |
|---|-----|-------|--------|
| 1 | yt-dlp-tui.py | Download MP4 + audio MP3 + SRT Indonesia | ✅ Jalan |
| 2 | demucs-tui.py | Split audio → no_vocals.mp3 (SFX bersih) + vocals (auto-hapus) | ✅ Jalan |
| 3 | kamus-tui.py | User edit JSON kamus untuk kurasi manual (sebelum masuk DB) | ✅ Jalan (user audit) |
| 4 | Web app | Translate SRT Indonesia → Jawa (pakai kamus Supabase) | ⚠ Prototype (perlu penyesuaian) |
| 5 | SRT editor | Sementara pakai SRT Indonesia (SRT Jawa = nunggu kamus + web selesai) | ⏳ Pending |
| 6 | edge-tts-tui.py | Generate audio dub dari SRT (5000+ cue, 2-5 jam durasi) | ✅ Jalan |
| 7 | mix-tui.py v3.6.1 | Mix MP4 + audio → final video (6 mode + pilihan bitrate) | ✅ Production-ready (A/B/C/D rekomendasi) |

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
| `scripts/mix-tui.py` | Final mix video (v3.6.1 — 6 mode + pilihan bitrate, E/F not recommended) |
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

### mix-tui v3.6.1 (24 Okt 2026, commit feat v3.6.1 — Original mode NOT RECOMMENDED)
- v3.6.1 UPDATE: Original mode (E/F) NOT RECOMMENDED berdasarkan test user
  - User verdict: 'Mix mp4, mp3 ori dan dub = tidak rekomendet = suara asli tetap muncul
    bahkan saat dub bicara'
  - Penyebab: ducking sidechain compress CUMA turunkan volume MP3 ori, tidak hilangkan vokal asli
  - Solusi: untuk hasil proper → pakai Full mode (no_vocals dari Demucs hilangkan vokal asli)
  - Code tetap ada (untuk edge case kalau user ingin vokal asli + dub), tapi ada warning prompt
  - Step 1.5: pilihan Original mode diberi label '⚠ NOT RECOMMENDED'
  - Confirm dialog sebelum lanjut Original mode (default No)
- Verdict user final (3 mode):
  - Full (A/B) = proper, clean sempurna (REKOMENDASI)
  - Simple (C/D) = cepat, cukup untuk preview/dialog dominan (REKOMENDASI)
  - Original (E/F) = TIDAK direkomendasi (vokal asli mengganggu)
- 6 kombinasi mode (3 input × 2 output):
  - ✅ A. Full + Stream copy → `{prefix}-id-final.mp4` (5 film sukses, ~350 MB)
  - ⚠ B. Full + Burn SRT → `{prefix}-id-final-sub.mp4` (low risk, belum user test)
  - ✅ C. Simple + Stream copy → `{prefix}-id-simple.mp4` (sync 100%)
  - ✅ D. Simple + Burn SRT → `{prefix}-id-simple-sub.mp4` (1 Mbps user confirmed > ori)
  - ⚠ E. Original + Stream copy → `{prefix}-id-orig.mp4` (NOT RECOMMENDED, vokal asli terdengar)
  - ⚠ F. Original + Burn SRT → `{prefix}-id-orig-sub.mp4` (NOT RECOMMENDED, vokal asli terdengar)
- Ducking PERLU untuk Full + Original mode (SFX/musik latar tetap ada)
  - Tapi Original mode ducking tidak hilangkan vokal asli (cuma turunkan volume)
  - Hanya no_vocals dari Demucs (Full mode) yang benar-benar hilangkan vokal
- Ducking TIDAK PERLU untuk Simple mode (no SFX, dub copy as-is)
- v3.5: Step 4.8 — pilih video bitrate untuk Mode B & D (burn SRT wajib re-encode):
  - 1 Mbps → ~1.2 GB/2jam (USER CONFIRMED OK, kualitas > ori, hemat 51%)
  - 1.5 Mbps → ~1.8 GB/2jam (default v3.5, seimbang)
  - 2 Mbps → ~2.3 GB/2jam (v3.4 behavior, subtitle paling sharp)
  - 4 Mbps → ~4.5 GB/2jam (HD-ready, source ori high quality)
  - Mode A & C (stream copy) tidak perlu prompt — bitrate ikut MP4 ori
- M1 VideoToolbox 32-33x speed (konsisten) = 2.5 jam video di-encode ~4.5 menit
- User confirmed: pipeline Simple mode end-to-end = sync 1000000%, tidak perlu DaVinci Resolve

## Ducking — Best Practice (PERMANEN)

User pertanyaan: "Apa perlu ducking padahal no_vocals sudah clean dari Demucs?"

Jawaban: **PERLU untuk Full mode**, TIDAK PERLU untuk Simple mode.

Alasan:
- Demucs buang VOKAL ori, tapi SFX/musik latar TETAP ADA di no_vocals.mp3
- Saat dub Indonesia/Jawa bicara, musik latar bisa mendominasi (terutama scene action/emotional)
- Ducking = sidechain compress (turunkan volume SFX saat dub aktif) → standard industry
- Pilihan di mix-tui: 6/12/18 dB (default 12 dB = seimbang) atau 0 dB (no ducking)

Simple mode tidak ada SFX → ducking concept tidak apply → auto-skip.

## Next (lanjut besok)

- User: istirahat dulu, lanjut besok
- User: validasi kamus-tui (8.618 entries dengan indo) satu per satu, mark READY, upload Supabase
- User: validasi 231 entries ngoko+krama yang perlu indo manual
- AI (optional): tunggu user — kalau user mau test Mode B (Full + Burn SRT), low risk
- AI (optional): fix bug cosmetic
  - Filename double `-id` di `derive_default_output()` (S1-id.mp4 → S1-id-id-simple-sub.mp4)
  - Progress bar `ETA=0sss0ss` di akhir encoding (carriage return glitch)
- AI: web app Jawa (TUI #4) — penyesuaian lookup kamus dari Supabase (setelah kamus audit selesai)

## Catatan PAT (PERMANEN)

PAT user sudah exposure di chat (6x push hari ini). User WAJIB revoke sekarang:
→ GitHub → Settings → Developer settings → Personal access tokens → Revoke

Untuk push sesi berikutnya, user kirim PAT baru. Atau setup SSH key di sandbox
untuk permanent solution (lebih aman dari PAT).
