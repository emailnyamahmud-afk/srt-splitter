# PROJECT_RULES.md

> Aturan project. Baca tiap session sebelum kerja. Update: 2 Nov 2026.

## Pipeline

```
[PROPER]       yt-dlp → srt-editor → demucs → edge-tts → mix Full (A/B)
[CEPAT]        yt-dlp → srt-editor → edge-tts → mix Simple (C/D)
[MUTE]         yt-dlp → srt-editor → edge-tts → mix Original (E/F)
[SHORTS]       mix-tui → Dola AI → shorts-tui → shorts-csv-tui → YouTube
[MERGE]        mix-tui × N → merge-tui (stream copy) → 1 video panjang
[REVIEW]       edge-tts Narration (ID) → review-mix-tui (review film ID)
[KONTEN]       edge-tts Narration (ID) → konten-tui (konten sejarah ID)
[GEMINI-SRT]   yt-dlp → srt-editor → gemini-tts-tui (SRT mode, ID/JV) → mix-tui (opsional Jawa/karakter spesifik)
[GEMINI-NARASI] naskah.txt → gemini-tts-tui (Narration mode, ID/JV) → review-mix-tui / konten-tui (Jawa)
Kamus: kamus-tui → jv.wiktionary.json → Supabase
```

## 15 TUI

| # | TUI | Status |
|---|-----|--------|
| 1 | yt-dlp-tui v6.5 | ✅ (default 1080p, multi-SRT ID+EN) |
| 2 | demucs-tui | ✅ |
| 3 | kamus-tui v16 | ✅ (audit) |
| 4 | Web app | ⚠ Prototype |
| 5 | SRT editor (web) | ⏳ Pending |
| 6 | edge-tts-tui v7.5 | ✅ (SRT + Narasi, ID only, paralel-safe) — production default |
| 7 | mix-tui v3.10 | ✅ (force 1080p + audio 48000Hz) |
| 8 | whisper-tui v2.0 | ✅ (Metal GPU) |
| 9 | srt-editor-tui v1.0.1 | ✅ |
| 10 | shorts-tui v1.1 | ✅ |
| 11 | shorts-csv-tui v1.0 | ✅ |
| 12 | merge-tui v2.0 | ✅ (VLC confirmed, sync 100%) |
| 13 | review-mix-tui v1.0 | ✅ (review film: MP4 + JSON + narasi → final MP4) |
| 14 | konten-tui v1.0 | ✅ (konten sejarah: narasi + images → Ken Burns video) |
| 15 | **gemini-tts-tui v1.1** | ⚠ EXPERIMENTAL (SRT + Narasi, ID + JV, OPSI TAMBAHAN, butuh GEMINI_API_KEY) |

## Struktur Folder — 3 LOKASI BERBEDA (baca config.py LENGKAP)

### 1. Repo srt-splitter (folder git, untuk DEV — AI kerja di sini)

- Sandbox AI: `/home/z/my-project/`
- Mac user (kalau clone untuk dev): `~/srt-splitter/` atau lokasi git clone
- Berisi: `src/` (Next.js), `api/`, `scripts/` (TUI Python), `public/`, docs (.md), `package.json`
- AI kerja: edit `scripts/*.py` (TUI), edit docs, edit `src/` (web app), commit + push GitHub
- **AI TIDAK punya akses langsung ke `~/Dubbing/` user — kerja di repo path saja**

### 2. User working dir (tempat TUI jalan di Mac)

- SSD `~/Dubbing/` = scripts (.py, didownload dari repo via curl) + venv + jv.wiktionary.json
- HDD `/Volumes/HDD/Dubbing/` = data:
  - `input/` (yt-dlp), `demucs/` (vocal sep), `tts/` (edge-tts + gemini-tts output),
  - `mix/` (mix-tui final), `shorts/` (shorts-tui Shorts), `parts/` (shorts Part),
  - `merged/` (merge-tui), `review/` (review-mix-tui), `konten/` (konten-tui),
  - `.env` (Supabase + GEMINI_API_KEY)
- Workflow: `cd ~/Dubbing && source venv/bin/activate && python3 <tui>.py`

### 3. Web app Vercel (deploy dari repo `src/`)

- URL: https://srt-splitter.vercel.app/
- Fungsi: translate SRT Indonesia → Jawa via Supabase (web app, BUKAN TUI)
- TIDAK ada hubungan langsung dengan TUI pipeline Dubbing

### config.py (di repo `scripts/config.py`, base path USER working dir)

11 path constants, semua untuk USER working dir, BUKAN repo path:
`SSD_HOME`, `HDD_BASE`, `INPUT_DIR`, `DEMUCS_DIR`, `TTS_DIR`, `MIX_DIR`,
`SHORTS_DIR`, `PARTS_DIR`, `MERGED_DIR`, `REVIEW_DIR`, `KONTEN_DIR`,
`KAMUS_JSON`, `ENV_FILE`, `SCRIPTS_DIR`

Helper: `ensure_hdd()`, `ensure_kamus()`, `load_env()`


## Wajib

- Pakai config.py untuk path (SSD scripts, HDD data)
- Baca config.py LENGKAP sebelum kerja (jangan asumsi)
- Tunggu user VLC feedback sebelum declare "production-ready"
- Sebutan hormat Tiongkok = PRESERVE, bukan mistranslate
- Tiap sesi WAJIB update docs + commit + push (AGENTS.md, PROJECT_RULES.md, scripts/README.md, README.md, worklog.md)
- TUI baru → update tabel "N TUI" di semua docs di atas. Cek `git ls-tree origin/main scripts/` untuk nomor TUI terakhir
- **Standarisasi res+audio = kerjaan mix-tui v3.10**
- **merge-tui v2.0** = stream copy (no drift) jika format konsisten, standardize jika beda
- **fix-merge-audio.py = DELETED** (audio drift, failed experiment)
- **edge-tts-tui v7.5 = production default** (SRT + Narasi, Indonesia only, paralel-safe, no API key)
- **review-mix-tui v1.0 = production** (TUI #13) — input narasi dari edge-tts v7.5 / gemini-tts-tui v1.1 Narration
- **konten-tui v1.0 = production** (TUI #14) — input narasi dari edge-tts v7.5 / gemini-tts-tui v1.1 Narration
- **gemini-tts-tui v1.1 = OPSI TAMBAHAN** (TUI #15, SRT + Narasi, ID + JV, butuh GEMINI_API_KEY)
  - Output SRT mode: `HDD/tts/{prefix}-audio-id-dub.wav` (mix-tui compatible)
  - Output Narration mode: `HDD/tts/{stem}-narasi.wav` (review-mix-tui / konten-tui compatible)
  - Jangan hapus / ganti edge-tts-tui v7.5
  - Status EXPERIMENTAL sampai user VLC feedback OK

## Dilarang

- Parsing tolol / buang data / halu
- Tentukan register ngoko/krama (AI gak bisa)
- Translate Jawa→Indonesia otomatis
- Auto-set status='ready' tanpa user explicit mark
- Over-engineer (fix-merge-audio = contoh gagal)
- Hapus / ganti edge-tts-tui v7.5 dengan gemini-tts-tui (kedua TUI harus hidup berdampingan)
- Bikin TUI baru tanpa cek file yang sudah ada di repo (jangan pakai nomor TUI yang sudah dipakai)
- Bikin TUI baru tanpa update docs utama (AGENTS/PROJECT_RULES/scripts/README/README root/worklog)
- Asumsi struktur folder tanpa baca config.py LENGKAP (11 path constants, semua dipakai TUI berbeda)
- **Campur aduk repo srt-splitter dengan user working dir `~/Dubbing/`** — repo = folder git untuk dev, working dir = tempat TUI jalan, scripts didownload dari repo via curl
- **Bikin file di `~/Dubbing/`** — itu user working dir, AI kerja di repo path (`/home/z/my-project/` sandbox atau `~/srt-splitter/` Mac dev)
- **Pikir web app Vercel = TUI Dubbing** — web app terpisah, translate SRT via Supabase, BUKAN pipeline TUI
