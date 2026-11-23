# PROJECT_RULES.md

> Aturan project. Baca tiap session sebelum kerja. Update: 19 Nov 2026.

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
[TALKING-HEAD] naskah.txt → gemini-tts-tui Narration (JV) → talkinghead-tui v1.0 (Replicate SadTalker, preprocess=full) → MP4 green screen preserved → editor chroma key → final-konten.mp4
Kamus: kamus-tui → jv.wiktionary.json → Supabase
```

## 20 TUI

| # | TUI | Status |
|---|-----|--------|
| 1 | yt-dlp-tui v6.5 | ✅ (default 1080p, multi-SRT ID+EN) |
| 2 | demucs-tui | ✅ |
| 3 | kamus-tui v16 | ✅ (audit) |
| 4 | Web app | ⚠ Prototype |
| 5 | SRT editor (web) | ⏳ Pending |
| 6 | edge-tts-tui v7.5 | ✅ (SRT + Narasi, ID only, paralel-safe) — production default |
| 7 | mix-tui v3.11 | ✅ (force 1080p + audio 48000Hz + 1:1 square VLC confirmed 14 Nov 2026) |
| 8 | whisper-tui v2.1 | ✅ (Metal GPU) |
| 9 | srt-editor-tui v1.0.0 | ✅ |
| 10 | shorts-tui v1.1 | ✅ |
| 11 | shorts-csv-tui v1.0 | ✅ |
| 12 | merge-tui v1.9 | ✅ (VLC confirmed, sync 100%) |
| 13 | review-mix-tui v1.0 | ⚠ UNTESTED (review film: MP4 + JSON + narasi → final MP4, code di GitHub belum diuji di Mac) |
| 14 | konten-tui v1.0 | ⚠ UNTESTED (konten sejarah: narasi + images → Ken Burns video, code di GitHub belum diuji di Mac) |
| 15 | **gemini-tts-tui v1.1** | ⚠ UNTESTED (SRT + Narasi, ID + JV, OPSI TAMBAHAN, butuh GEMINI_API_KEY, code di GitHub belum diuji di Mac) |
| 16 | **talkinghead-tui v1.0** | ⚠ UNTESTED (SadTalker via Replicate, green screen preserved, butuh REPLICATE_API_TOKEN, code di GitHub belum diuji di Mac) |
| 17 | **manim-shorts-tui v0.1** | ⚠ UNTESTED (Shorts infografis: WAV + SRT → manim video vertical 9:16, sandbox OK 19 Nov 2026 + fix 21 Nov 2026 commit 1623907, code di GitHub belum diuji di Mac) |
| 18 | **piper-tts-tui v0.2** | ⚠ UNTESTED (TTS LOKAL offline Piper VITS ONNX, GPU Metal CoreML, sandbox fungsi core OK 22 Nov 2026, generate test pending HF rate-limit, code di GitHub belum diuji di Mac) |
| 19 | **voicestudio-tts-tui v1.0** | ⚠ SLOW (TTS via VoiceStudio local API localhost:3900, 4 voice profile anton/sari ID+JV. User test 23 Nov 2026: suara bagus sesuai reff, tapi 16s SRT = 8 menit. Superseded oleh supertonic #20) |
| 20 | **supertonic-tts-tui v0.1** | ✅ Production candidate (TTS LOKAL Supertone Supertonic 3 ONNX, 10 voice builtin M1-M5/F1-F5 deterministic no drift, RTF ~0.012 = ~100x OmniVoice. User VLC test 23 Nov 2026: sangat bagus, jauh lebih bagus dari edge-tts, ID laki+perempuan OK, 1jam SRT ~30menit. Pending long-cue test) |

**Eksperimen TTS (TIDAK bernomor, DEPRECATED):** `omnivoice-tts-tui.py v0.7` — ❌ DEPRECATED (ref clone berantakan per user VLC test 23 Nov 2026, v0.7 fix 3 lapis tidak solve drift). Pakai supertonic #20.

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
- **Standarisasi res+audio = kerjaan mix-tui v3.11** (mode 1:1 square = center crop source vertical → 1080x1080 IG feed, VLC confirmed 14 Nov 2026)
- **merge-tui v1.9** = stream copy (no drift) jika format konsisten, standardize jika beda
- **fix-merge-audio.py = DEPRECATED (masih ada di repo scripts/fix-merge-audio.py v1.4, tapi jangan pakai — gunakan merge-tui v1.9 audio stream copy)** (audio drift, failed experiment)
- **edge-tts-tui v7.5 = production default** (SRT + Narasi, Indonesia only, paralel-safe, no API key)
- **review-mix-tui v1.0 = UNTESTED** (TUI #13, code di GitHub belum diuji di Mac) — input narasi dari edge-tts v7.5 / gemini-tts-tui v1.1 Narration
- **konten-tui v1.0 = UNTESTED** (TUI #14, code di GitHub belum diuji di Mac) — input narasi dari edge-tts v7.5 / gemini-tts-tui v1.1 Narration
- **gemini-tts-tui v1.1 = OPSI TAMBAHAN** (TUI #15, SRT + Narasi, ID + JV, butuh GEMINI_API_KEY)
  - Output SRT mode: `HDD/tts/{prefix}-audio-id-dub.wav` (mix-tui compatible)
  - Output Narration mode: `HDD/tts/{stem}-narasi.wav` (review-mix-tui / konten-tui / talkinghead-tui compatible)
  - Jangan hapus / ganti edge-tts-tui v7.5
  - Status UNTESTED (code di GitHub, belum diuji di Mac) sampai user VLC feedback OK
- **talkinghead-tui v1.0 = OPSI TAMBAHAN** (TUI #16, workflow KONTEN bukan dubbing, SadTalker via Replicate)
  - Input: foto green screen half-body + narasi JV wav (dari gemini-tts-tui #15 Narration)
  - Backend: Replicate.com `cjwbw/sadtalker` (cloud, butuh `REPLICATE_API_TOKEN` di HDD .env)
  - Output: `HDD/konten/{name}-talking-green.mp4` (green screen preserved, preprocess=full)
  - User edit manual: chroma key → composite background → final-konten.mp4 (siap YouTube)
  - JANGAN install SadTalker lokal di M1 (Python 3.8 strict, hardcode CUDA, MPS partial, very slow) — pakai Replicate cloud
  - Status UNTESTED sampai user VLC feedback OK
- **supertonic-tts-tui v0.1 = PRODUCTION CANDIDATE** (TUI #20, TTS LOKAL Supertone Supertonic 3 ONNX, model sama subtitlekit.com untuk Indonesia)
  - 10 voice builtin M1-M5/F1-F5 deterministic (NO cloning, NO drift by design — fix masalah OmniVoice berantakan)
  - RTF ~0.012-0.018 M4 CPU = ~100x OmniVoice, ~100x VoiceStudio. 1jam SRT ~30menit (sekompetitif subtitlekit web tanpa upload)
  - User VLC test 23 Nov 2026: sangat bagus, jauh lebih bagus dari edge-tts, ID laki+perempuan OK. Pending long-cue test.
  - Output SRT mode: `HDD/tts/{prefix}-audio-id-dub.wav` (24kHz mono, mix-tui compatible)
  - Output Narration mode: `HDD/tts/{stem}-narasi.wav` (48kHz stereo, review-mix/konten/talkinghead/manim-shorts compatible)
  - Backend: `pip install supertonic` 1.3.x, model ~400MB cached `~/.cache/supertonic3/` (auto_download, sekali saja)
  - NO voice cloning (10 builtin voices) — trade-off vs VoiceStudio/OmniVoice yg purport cloning
- **voicestudio-tts-tui v1.0 = SLOW** (TUI #19, VoiceStudio local API localhost:3900, 4 voice profile anton/sari ID+JV)
  - User test 23 Nov 2026: suara bagus sesuai reff, tapi 16s SRT = 8 menit (per-cue HTTP overhead). Tidak viable untuk film panjang.
  - Superseded oleh supertonic #20 (cepat + deterministic). Voice cloning works tapi speed block.
- **omnivoice-tts-tui v0.7 = DEPRECATED** (eksperimen TIDAK bernomor, ref clone berantakan)
  - User VLC test 23 Nov 2026: ref clone BERANTAKAN, v0.7 fix 3 lapis (encode-once + pos_temp=0 + guidance=3 + seed) TIDAK solve drift
  - Header lama salah claim "TUI #19" (collision dgn voicestudio) — sudah diperbaiki ke DEPRECATED
  - JANGAN pakai production. Pakai supertonic #20 sebagai pengganti. Script tetap di repo untuk referensi.

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
- **Auto-declare TUI baru = "Production"** — TUI baru WAJIB status UNTESTED sampai user test di Mac + VLC feedback OK. Setelah OK baru status Production.
- **Install SadTalker lokal di M1** — lambat + buggy, pakai Replicate cloud (TUI #16 pakai `cjwbw/sadtalker`)
