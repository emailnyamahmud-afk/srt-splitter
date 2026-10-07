# SRT Splitter + Dubbing Jawa

Aplikasi web untuk split SRT, translate subtitle, dan **dubbing Mandarin → Jawa** dengan audio natural. 100% di browser, gratis. Workflow lengkap sampai mix video dengan FFmpeg.

**Live:** https://srt-splitter.vercel.app/
**Source:** https://github.com/emailnyamahud-afk/srt-splitter

> **📖 Visi Project:** Bukan cuma dubbing Mandarin → Jawa. Ini prototype untuk **digitalisasi bahasa daerah Indonesia di era AI** (700 bahasa, 169 terancam punah). Lihat [`docs/PROJECT_VISION.md`](docs/PROJECT_VISION.md) untuk konteks lengkap + roadmap 2 tahun.

---

## Fitur Utama

### Web App (https://srt-splitter.vercel.app/)

#### Editor SRT Jawa (PRIMARY — project-based workflow) ⭐

| Fitur | Deskripsi |
|---|---|
| **Project-based workflow** | "+ Project Baru" → upload 2 SRT (ID + Jawa), simpan ke Supabase |
| **Multi-project** | S1 (unfinished), S2 (unfinished), tutup S2, buka S1, lanjut kapan saja |
| **Auto-save 1.5s** | Edit cue → simpan ke Supabase otomatis (debounced) |
| **Per-cue Preview** | "▶ Preview" → generate TTS 1 cue, play inline di browser |
| **Browser cache (IndexedDB)** | Audio tersimpan di browser, survive reload, no re-gen untuk cue yang sama |
| **Generate Full** | Pakai cache kalau valid (hemat API call) + auto-download WAV |
| **Bidirectional alias** | Source apapun (aku/inyong/kula/dalem) → convert ke ngoko/krama utama |
| **Per-cue voice** | Dimas/Siti (Jawa), Ardi/Gadis (Indonesia) — assign per cue |
| **Auto-strip aksen TTS** | é/è/ê → e otomatis saat TTS (SRT final tetap utuh dengan aksen) |
| **Mode ON + Smart Fit** | 100% sync SRT ori, cap 2.0x, asymmetric trim, crossfade 150ms |

#### Split / Translate / TTS (SEKUNDER — workflow lama)

| Fitur | Deskripsi |
|---|---|
| **Split SRT** | By durasi (5m-5jam) atau by karakter (max 5000) |
| **Translate** | EN→ID, ID→Jawa, Jawa→ID (gratis Google Translate atau premium OpenAI) |
| **TTS Mode ON + Smart Fit** | Per-cue dynamic TTS speed (cap 2.0x, pitch preserved) |
| **TTS Pitch Control** | -10Hz laki (lebih bas), +10Hz perempuan (lebih tinggi) |
| **TTS Mode OFF** | Natural sequential, speed 1.0x-2.0x |
| **🔴 Dubbing Mode v2.0** | Audio natural → SRT baru → MP4 retimed (deprecated, 20x test gagal) |

### Python Scripts (lokal, untuk produksi final)

| Script | Fungsi |
|---|---|
| **`demucs-tui.py`** ⭐ | TUI Demucs SFX separation (MPS acceleration, ~1 menit untuk 7.5 menit audio) |
| **`mix-tui.py`** ⭐ | TUI Mix SFX bersih + audio dub + MP4 (~7 detik, 0 DTS warnings) |
| **`yt-dlp-tui.py`** | TUI Download YouTube 1080p H.264 + audio |
| **`kamus-tui.py`** | TUI Browse + edit kamus Jawa (44.585 entri) + upload Supabase |
| **`edit-kamus.py`** | Edit kamus JSON di VSCode + import/export ke Supabase |
| **`parse-wiktionary-jv.py`** | Parser v5: Wiktionary XML → kamus JSON (register tag + krama_inggil + xref) |
| `scripts/rapikan-jawa.py` | Rapikan ejaan Jawa di 1 file SRT |
| `scripts/srt-to-audio.py` | Generate audio dari SRT (Edge TTS, ON/OFF mode) |
| `scripts/split_srt.py` | Split SRT by durasi |
| `scripts/retime-video.py` | Retime MP4 (deprecated, backup) |
| `scripts/analyze-srt-density.py` | Analisis distribusi cue + estimasi robot ratio |

---

## Workflow Dubbing Mandarin → Jawa (3 Fase)

```
Fase 0 (opsional): SFX Separation dengan Demucs (Python lokal)
  Input: MP4 → Output: no_vocals.wav (SFX bersih)
        ↓
Fase 1: Web app Editor SRT Jawa (project-based + per-cue preview)
  + Project Baru → upload SRT ID + SRT Jawa → buat project (simpan ke Supabase)
  Edit cue (text/voice/ngoko/krama) → auto-save 1.5s
  Preview per cue → dengar di browser → cache ke IndexedDB
  Generate Full → stitch cached audio + crossfade → audio-{lang}-dub.wav
        ↓
Fase 2: Mix SFX + Dub (Python lokal, mix-tui.py)
  Input: mp4-ori + audio-{lang}-dub + no_vocals.wav (SFX)
  Output: mp4-{lang}-final.mp4 (video stream copy, 0 DTS warnings, 100% sync)
        ↓
Fase 3 (opsional): Edit final di DaVinci Resolve (manual)
```

**Total waktu untuk MP4 3 jam**: ~30-60 menit
- Fase 0: 5-10 menit (Demucs MPS, opsional)
- Fase 1: 20-40 menit (edit + preview + generate)
- Fase 2: ~10 detik (mix FFmpeg)
- Fase 3: 30-60 menit (edit manual, opsional)

---

## Setup

### 1. Supabase (untuk Editor SRT Jawa project-based)

1. Daftar [supabase.com](https://supabase.com) (free, no credit card)
2. Create project → dapat Project URL + anon key
3. Set Vercel env vars:
   ```
   NEXT_PUBLIC_SUPABASE_URL=https://xxx.supabase.co
   NEXT_PUBLIC_SUPABASE_ANON_KEY=eyJxxx
   ```
4. Run SQL migrations di Supabase SQL Editor:
   - `scripts/supabase-migration-v2.sql` (srt_projects + srt_cues untuk Editor)
   - `scripts/supabase-migration-v3.sql` (kamus: krama_inggil + register)

### 2. Kamus Jawa (download dari GitHub)

```bash
# Download compressed kamus (1.3MB)
curl -L -o kamus-jawa-full.json.gz \
  https://github.com/emailnyamahud-afk/srt-splitter/raw/main/public/kamus-jawa-full.json.gz

# Extract ke 11MB
gunzip kamus-jawa-full.json.gz

# Import ke Supabase (butuh Python + env vars)
python3 scripts/edit-kamus.py import kamus-jawa-full.json
```

### 3. Python Lokal (untuk Demucs + Mix)

```bash
# Setup (sekali saja)
brew install ffmpeg
pip3 install edge-tts numpy questionary

# Optional: Demucs untuk SFX separation
pip3 install demucs
```

Lihat [`scripts/tutor-python-lokal.md`](scripts/tutor-python-lokal.md) untuk detail.

---

## Kamus Jawa

Kamus berisi **44.585 entri** dari Wiktionary Jawa, dengan struktur v5:

```json
{
  "ngoko": "sapa",          // kata ngoko + alias (koma)
  "aksara": "ꦱꦥ",          // aksara Jawa
  "krama": "sinten",        // kata krama + alias
  "krama_inggil": "",       // krama inggil (v5)
  "arti": "",               // terjemahan Indonesia (user isi manual)
  "keterangan": "...",      // definisi JAWA dari XML (JANGAN HAPUS)
  "register": "umum",       // ngoko|krama|krama_inggil|kawi|umum (v5)
  "sumber": "jv.wiktionary.org + xref"
}
```

**Bidirectional lookup**: source apapun (aku/inyong/kula/dalem) → convert ke ngoko atau krama utama.

**Edit workflow** (MacBook):
1. Download `public/kamus-jawa-full.json.gz` dari GitHub
2. Extract: `gunzip kamus-jawa-full.json.gz`
3. Edit di VSCode (cari entry, isi krama/arti)
4. Upload ke Supabase: `python3 scripts/edit-kamus.py import kamus-jawa-full.json`

---

## Stack Teknologi

### Web App
- Next.js 16 + TypeScript + Tailwind CSS 4 + shadcn/ui
- Deploy: Vercel (app + Edge TTS proxy + Google Translate proxy)
- Supabase PostgreSQL (project + cues + kamus)
- IndexedDB (browser local audio cache)

### Python Scripts
- Python 3.8+
- FFmpeg (auto-detect)
- Demucs (Meta, open source, untuk SFX separation, MPS acceleration di Apple Silicon)
- Edge TTS (Microsoft, gratis, native Indonesia/Jawa)
- Questionary (TUI interaktif)

### Storage
- Supabase PostgreSQL free tier (500MB DB) — project + cues + kamus
- IndexedDB browser (ratusan MB) — audio cache per cue + full audio
- GitHub repo — kamus JSON (11MB + 1.3MB gz) untuk user download

---

## Struktur Folder

```
srt-splitter/
├── README.md                    # Dokumen ini
├── docs/                         # Dokumentasi teknis + visi
│   ├── PROJECT_VISION.md         # 📖 Visi digitalisasi bahasa + roadmap 2 tahun
│   ├── PROGRESS.md               # 📊 Status project + timeline
│   └── EDGE_TTS_PROXY.md         # Cara kerja Edge TTS proxy
├── scripts/                      # Python scripts + SQL migrations
│   ├── parse-wiktionary-jv.py    # Parser v5 (Wiktionary XML → kamus JSON)
│   ├── edit-kamus.py             # Import/export kamus ke Supabase
│   ├── kamus-tui.py              # TUI browse + edit kamus
│   ├── demucs-tui.py             # TUI Demucs SFX separation
│   ├── mix-tui.py                # TUI Mix SFX + dub + MP4
│   ├── yt-dlp-tui.py             # TUI download YouTube
│   ├── supabase-migration-v2.sql # SQL: srt_projects + srt_cues
│   ├── supabase-migration-v3.sql # SQL: kamus krama_inggil + register
│   └── ...                       # Lainnya lihat scripts/README.md
├── src/                          # Next.js source code
│   ├── app/                      # App router
│   ├── lib/                      # Library (TTS, SRT, audio cache, kamus, supabase)
│   └── components/               # React components (DualSrtEditor, KamusEditor, dst)
└── public/                       # Static assets
    ├── logo.svg
    ├── kamus-jawa-full.json       # Kamus v5 (11MB, user download)
    ├── kamus-jawa-full.json.gz    # Kamus v5 compressed (1.3MB)
    └── kamus-jawa.json            # Draft v4 lama (21KB, backup)
```

---

## Deploy

### Vercel (auto-deploy, default)
1. Push ke GitHub `main` branch
2. Vercel auto-deploy
3. URL: https://srt-splitter.vercel.app/

### Lokal (dev)
```bash
bun install
bun run dev
# Buka http://localhost:3000
```

---

## Environment Variables

```
NEXT_PUBLIC_SUPABASE_URL=https://xxx.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=eyJxxx
```

Set di Vercel dashboard (Project Settings → Environment Variables).

Edge TTS proxy pakai hardcoded Microsoft token (gratis, no auth). OpenAI/OpenRouter TTS pakai user API key di UI (localStorage).

---

## Status Project

Lihat [`docs/PROGRESS.md`](docs/PROGRESS.md) untuk:
- Quick status table (apa yang sudah jadi, apa yang pending)
- Milestone terbaru (Editor SRT Jawa project-based, 8 Okt 2026)
- Catatan untuk AI next time buka
- Timeline update lengkap

---

## License

Bebas dipakai untuk produksi sendiri. Atribusi dihargai tapi tidak wajib.

---

## Credits

Teknologi yang dipakai:
- **Edge TTS** — Microsoft neural voices (gratis, native Indonesia/Jawa)
- **Demucs** — Source separation by Meta/Facebook Research
- **FFmpeg** — Video/audio processing
- **Supabase** — PostgreSQL + Auth + Storage
- **ThioJoe ASTD** — Inspirasi trim silence + two-pass TTS
- **VoiceStudio** — Inspirasi Smart Fit algorithm
- **voicertool.com** — Inspirasi asymmetric trim + cap 2.0x
- **Wiktionary Jawa** — Source kamus (44.585 entri)
