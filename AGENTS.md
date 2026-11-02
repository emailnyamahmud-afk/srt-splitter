# AGENTS.md

> Dibaca AI di awal setiap session. Update: 2 Nov 2026.

## Anti-Amnesia Protocol

1. Baca duluan: AGENTS.md, README.md, PROJECT_RULES.md, scripts/README.md, scripts/config.py
2. Jangan ngandalkan memory context — context panjang = amnesia
3. Setiap sesi WAJIB update docs + commit + push
4. **Jangan tebak struktur folder — baca config.py LENGKAP (11 path constants, semua dipakai TUI berbeda)**
5. **Paham 3 LOKASI berbeda** (jangan campur aduk):
   - **Repo srt-splitter** (folder git, untuk DEV): sandbox AI `/home/z/my-project/`, Mac user `~/srt-splitter/` (kalau clone). Edit code + docs + push GitHub.
   - **User working dir** (tempat TUI jalan): Mac user `~/Dubbing/` (SSD, scripts + venv) + `/Volumes/HDD/Dubbing/` (HDD, data). Scripts didownload dari repo `scripts/*.py` via curl.
   - **Web app Vercel**: https://srt-splitter.vercel.app/ (deploy dari `src/` repo, terpisah dari TUI pipeline Dubbing).
6. Cek git log untuk state terakhir
7. **TUI baru WAJIB update tabel "N TUI" di 4 docs: AGENTS.md, PROJECT_RULES.md, scripts/README.md, README.md root**
8. **Cek file yang sudah ada di repo (`git ls-tree origin/main scripts/`) sebelum pilih nomor TUI baru** — jangan pakai nomor yang sudah dipakai
9. **Workflow: AI sandbox → push GitHub → user pull (kalau repo clone) / curl (kalau working dir) → test → kalau error → AI fix → push GitHub**
10. **AI kerja di repo** (`/home/z/my-project/` sandbox): edit `scripts/*.py` (TUI Python), edit docs, edit `src/` (web app Next.js), commit + push. **JANGAN** bikin file di `~/Dubbing/` (itu USER working dir, AI tidak punya akses langsung).


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

## Struktur Folder — 3 LOKASI BERBEDA (baca config.py LENGKAP)

### 1. Repo srt-splitter (folder git, untuk DEV — edit code + docs)

```
Sandbox AI:  /home/z/my-project/                      (Z.ai sandbox, clone dari GitHub)
Mac user:    ~/srt-splitter/ (atau lokasi git clone)  (untuk dev web app, kalau user clone)

Repo root:
├── README.md                          # docs root (web app + TUI overview)
├── AGENTS.md                          # docs untuk AI (baca tiap session)
├── PROJECT_RULES.md                   # aturan project
├── worklog.md                         # log semua perubahan
├── .env.example                       # template env (NEXT_PUBLIC_SUPABASE_*)
├── package.json                       # Next.js + deps web app
├── next.config.ts                     # Next.js config (Vercel deploy)
├── vercel.json                        # Vercel config
├── src/                               # Next.js web app (translate SRT Indonesia → Jawa via Supabase)
├── api/                               # Vercel serverless functions (edge-tts proxy dll)
├── public/                            # static assets + kamus JSON (jv.wiktionary.json dll)
├── scripts/                           # Python TUI (15 TUI) — DIDOWNLOAD USER ke ~/Dubbing/
│   ├── config.py                      # base path USER (~/Dubbing/ + /Volumes/HDD/Dubbing/)
│   ├── README.md                      # docs scripts (untuk user working dir ~/Dubbing/)
│   ├── yt-dlp-tui.py  # TUI #1
│   ├── demucs-tui.py  # TUI #2
│   ├── kamus-tui.py   # TUI #3
│   ├── edge-tts-tui.py v7.5  # TUI #6
│   ├── mix-tui.py    # TUI #7
│   ├── whisper-tui.py # TUI #8
│   ├── srt-editor-tui.py # TUI #9
│   ├── shorts-tui.py # TUI #10
│   ├── shorts-csv-tui.py # TUI #11
│   ├── merge-tui.py  # TUI #12
│   ├── review-mix-tui.py # TUI #13
│   ├── konten-tui.py # TUI #14
│   ├── gemini-tts-tui.py v1.1 # TUI #15 (BARU)
│   ├── gemini_tts_backend.py          # TUI #15 backend modul
│   ├── GEMINI_TTS.md                  # TUI #15 docs
│   └── ... (script kamus + tools lain)
├── srt-splitter-clone/                # git submodule (repo clone untuk eksperimen)
├── srt-splitter-work/                 # git submodule (repo working)
├── clean-srt/                         # project Python clean SRT (terpisah)
├── tool-results/                      # output dari tool AI (log)
└── upload/                            # upload user (SRT, audio, dll)
```

**AI kerja di repo path** (sandbox `/home/z/my-project/` atau Mac user `~/srt-splitter/`):
- Edit code TUI Python di `scripts/*.py`
- Edit docs (AGENTS.md, README.md, PROJECT_RULES.md, scripts/README.md, worklog.md)
- Edit web app Next.js di `src/` + `api/`
- Commit + push ke GitHub (`git push origin main`)

### 2. User working dir (tempat TUI JALAN di Mac — BUKAN repo)

```
SSD ~/Dubbing/                          → scripts (.py) + venv + jv.wiktionary.json (cepat)
  ├── yt-dlp-tui.py                     # didownload dari scripts/ repo via curl
  ├── demucs-tui.py                     # didownload dari scripts/ repo via curl
  ├── kamus-tui.py                      # didownload dari scripts/ repo via curl
  ├── edge-tts-tui.py                   # didownload dari scripts/ repo via curl
  ├── mix-tui.py                        # didownload dari scripts/ repo via curl
  ├── whisper-tui.py                    # didownload dari scripts/ repo via curl
  ├── srt-editor-tui.py                 # didownload dari scripts/ repo via curl
  ├── shorts-tui.py                     # didownload dari scripts/ repo via curl
  ├── shorts-csv-tui.py                 # didownload dari scripts/ repo via curl
  ├── merge-tui.py                      # didownload dari scripts/ repo via curl
  ├── review-mix-tui.py                 # didownload dari scripts/ repo via curl
  ├── konten-tui.py                     # didownload dari scripts/ repo via curl
  ├── gemini-tts-tui.py                 # didownload dari scripts/ repo via curl
  ├── gemini_tts_backend.py             # didownload dari scripts/ repo via curl
  ├── config.py                         # didownload dari scripts/ repo via curl (BASE PATH USER)
  ├── jv.wiktionary.json                # kamus (download dari public/ repo)
  └── venv/                             # Python virtual env (pip3 install)

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
  └── .env                              # Supabase + GEMINI_API_KEY — config.ENV_FILE
```

**User pakai working dir** (Mac `~/Dubbing/` + HDD `/Volumes/HDD/Dubbing/`):
- `cd ~/Dubbing && source venv/bin/activate && python3 <tui>.py`
- TUI baca `config.py` → tahu path HDD → baca/tulis data di HDD subfolder
- Scripts di sini DIDOWNLOAD dari GitHub raw (`scripts/*.py`) via curl

### 3. Web app Vercel (deploy dari repo)

- URL: https://srt-splitter.vercel.app/
- Source: `src/` + `api/` di repo
- Fungsi: translate SRT Indonesia → Jawa via Supabase kamus (web app, BUKAN TUI)
- TIDAK ada hubungan langsung dengan TUI Dubbing — terpisah
- AI next session JANGAN pikir web app = TUI pipeline Dubbing

### config.py 11 path constants (semua untuk USER working dir)

```python
# config.py base path (dipakai TUI di ~/Dubbing/ USER, BUKAN di repo)
SSD_HOME = Path.home() / 'Dubbing'           # SSD scripts + venv + kamus
HDD_BASE = Path('/Volumes/HDD/Dubbing')      # HDD data besar
INPUT_DIR = HDD_BASE / 'input'               # TUI #1 yt-dlp output
DEMUCS_DIR = HDD_BASE / 'demucs'             # TUI #2 demucs output
TTS_DIR = HDD_BASE / 'tts'                   # TUI #6 edge-tts + TUI #15 gemini-tts output
MIX_DIR = HDD_BASE / 'mix'                   # TUI #7 mix-tui output
SHORTS_DIR = HDD_BASE / 'shorts'             # TUI #10 shorts-tui Shorts mode
PARTS_DIR = HDD_BASE / 'parts'               # TUI #10 shorts-tui Part mode
MERGED_DIR = HDD_BASE / 'merged'             # TUI #12 merge-tui output
REVIEW_DIR = HDD_BASE / 'review'             # TUI #13 review-mix-tui output
KONTEN_DIR = HDD_BASE / 'konten'             # TUI #14 konten-tui output
KAMUS_JSON = SSD_HOME / 'jv.wiktionary.json' # kamus SOURCE OF TRUTH (di SSD, cepat load)
ENV_FILE = HDD_BASE / '.env'                 # Supabase + GEMINI_API_KEY (di HDD)
SCRIPTS_DIR = SSD_HOME                       # scripts di SSD
```

- `ensure_hdd()` — cek HDD colok, bikin subfolder kalau belum ada
- `ensure_kamus()` — cek kamus JSON ada, tampilkan download command kalau gak ada
- `load_env()` — load `.env` dari HDD ke os.environ (Supabase + GEMINI_API_KEY)
- Workflow user: `cd ~/Dubbing && source venv/bin/activate && python3 <tui>.py`
- Kalau HDD tidak colok → TUI fallback ke cwd atau exit dengan pesan "Colok HDD"

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
15. **Repo srt-splitter ≠ User working dir Dubbing** (jangan campur aduk):
    - Repo: `~/srt-splitter/` (atau sandbox `/home/z/my-project/`) = tempat dev code + docs + commit + push
    - Working dir: `~/Dubbing/` (SSD scripts + venv) + `/Volumes/HDD/Dubbing/` (HDD data) = tempat user jalanin TUI
    - Scripts di repo `scripts/*.py` → user download ke `~/Dubbing/` via `curl -L -o ... https://raw.githubusercontent.com/.../main/scripts/...`
    - config.py di repo: base path USER (`~/Dubbing/` + `/Volumes/HDD/Dubbing/`), BUKAN path repo
    - AI TIDAK punya akses langsung ke `~/Dubbing/` user — AI kerja di repo path

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

### LOKASI (jangan campur aduk — kesalahan parah saya sebelumnya):

- **Repo srt-splitter** (folder git, untuk DEV): sandbox AI = `/home/z/my-project/`, Mac user (kalau clone) = `~/srt-splitter/` atau lokasi git clone lain. Berisi: `src/` (Next.js), `api/`, `scripts/` (TUI Python), `public/`, docs (.md), `package.json`. AI kerja di sini: edit code + docs + commit + push.
- **User working dir** (tempat TUI jalan di Mac): `~/Dubbing/` (SSD, scripts + venv + kamus) + `/Volumes/HDD/Dubbing/` (HDD, data). Scripts di sini DIDOWNLOAD dari repo `scripts/*.py` via curl. User jalanin: `cd ~/Dubbing && source venv/bin/activate && python3 <tui>.py`. **AI TIDAK punya akses langsung ke sini — kerja di repo path saja**.
- **Web app Vercel**: https://srt-splitter.vercel.app/, deploy dari `src/` repo, terpisah dari TUI pipeline Dubbing.

### config.py (di repo `scripts/config.py`, base path untuk USER working dir):

```python
SSD_HOME = Path.home() / 'Dubbing'           # SSD scripts + venv + kamus
HDD_BASE = Path('/Volumes/HDD/Dubbing')      # HDD data besar
INPUT_DIR, DEMUCS_DIR, TTS_DIR, MIX_DIR,     # 9 subfolder HDD
SHORTS_DIR, PARTS_DIR, MERGED_DIR,
REVIEW_DIR, KONTEN_DIR
KAMUS_JSON = SSD_HOME / 'jv.wiktionary.json' # kamus di SSD (cepat load)
ENV_FILE = HDD_BASE / '.env'                 # Supabase + GEMINI_API_KEY
SCRIPTS_DIR = SSD_HOME                       # scripts di SSD
```
- 11 path constants, semua untuk USER working dir, BUKAN repo path
- `ensure_hdd()` + `ensure_kamus()` + `load_env()` = helper functions

### TUI (ada 15, BUKAN 12/13):

- Jangan amnesia: ada 15 TUI. Baca `git ls-tree origin/main scripts/` untuk verifikasi sebelum pilih nomor TUI baru
- TUI #13 = review-mix-tui (production), TUI #14 = konten-tui (production), TUI #15 = gemini-tts-tui (experimental)
- `REVIEW_DIR` di config.py untuk review-mix-tui (#13), `KONTEN_DIR` untuk konten-tui (#14)
- edge-tts-tui v7.5 Narration mode → feed review-mix-tui / konten-tui (BUKAN langsung ke user)
- gemini-tts-tui v1.1 Narration mode (JV) → alternatif feed untuk review-mix-tui / konten-tui (bahasa Jawa)

### Workflow (kesalahan saya sebelumnya: tidak push):

- AI sandbox: kerja di repo → commit + push GitHub
- User: kalau repo clone → `git pull` (untuk dev web app) / kalau working dir → `curl -L -o ... https://raw.githubusercontent.com/.../main/scripts/<file>.py` (untuk pakai TUI)
- User test → kalau error → paste ke AI → AI fix di sandbox → push GitHub → user download lagi
- TIAP selesai task: WAJIB commit + push GitHub (jangan nunggu ditanya ulang)

