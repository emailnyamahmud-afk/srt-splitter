# SRT Splitter + Dubbing Jawa

Pipeline dubbing Mandarin→Jawa end-to-end. Web app + Python TUI.

**Live:** https://srt-splitter.vercel.app/

## Pipeline

```
yt-dlp-tui.py → demucs-tui.py → edge-tts-tui.py → SRT editor (web) → mix-tui.py
                                                      ↑
                                                kamus-tui.py
                                                      ↑
                                              jv.wiktionary.json
                                                      ↑
                                               Supabase (verified)
```

## Struktur Folder

```
SSD ~/Dubbing/                         ← scripts + venv (cepat)
├── yt-dlp-tui.py
├── demucs-tui.py
├── edge-tts-tui.py
├── mix-tui.py
├── kamus-tui.py
├── config.py                          ← base path (SSD vs HDD)
├── jv.wiktionary.json                 ← kamus (10MB, di SSD)
└── venv/

HDD /Volumes/HDD/Dubbing/              ← data (besar)
├── input/                             ← yt-dlp output (video, audio, srt)
├── demucs/                            ← no_vocals (300MB+)
├── tts/                               ← dub wav + cache (ratusan MB)
├── mix/                               ← final MP4 (2GB+)
└── .env                               ← Supabase credentials
```

Setup HDD:
```bash
mkdir -p /Volumes/HDD/Dubbing/{input,demucs,tts,mix}
```

## Komponen

### 1. yt-dlp-tui.py — Download video/audio
- M4A native (skip MP3 conversion)
- Subtitle JSON parser (SRT Indonesia otomatis)
- Default output: HDD/input/
- Install: `pip3 install yt-dlp`

### 2. demucs-tui.py — Vocal separation
- M1 MPS acceleration (~16 menit untuk 2 jam audio)
- Segment 4 (RAM aman 16GB, ~2x lebih lambat dari default)
- Output WAV → ffmpeg convert MP3 320kbps (streaming, RAM kecil)
- Auto-hapus vocals.wav + WAV setelah convert (storage aman)
- Cari audio di HDD/input/, output ke HDD/demucs/
- Auto-hapus vocals
- Install: `pip3 install torchaudio demucs`

### 3. edge-tts-tui.py — TTS generation (100% lokal)
- Edge TTS Python WebSocket v7.3.1 (bukan browser, no rate-limit)
- 4565 cue tested (Toko-buku, ~3 jam generate)
- Smart Fit algorithm (speedup + slowdown)
- Inline mix (RAM efficient untuk 5000+ cues)
- Cari SRT di HDD/input/, output ke HDD/tts/
- Output: dub-id.wav + subs-id.srt
- Install: `pip3 install edge-tts numpy`

### 4. SRT editor (web app)
- Split SRT per cue
- Translate Mandarin→Jawa (kamus lookup dari Supabase)
- Tambah kata baru → kamus-tui → jv.wiktionary.json
- Build: Next.js 16 + Vercel
- Repo: https://github.com/emailnyamahmud-afk/srt-splitter

### 5. mix-tui.py — Final mix
- Mode A: stream copy (~3 menit, no SRT burn)
- Mode B: burn SRT (~4 menit, M1 VideoToolbox 35x hardware)
- 4 posisi SRT (Opsi A/B/C/D, Justify=2 center)
- Cari MP4 di HDD/input/, SFX di HDD/demucs/, dub di HDD/tts/
- Output: HDD/mix/final.mp4
- Install: `brew install ffmpeg`

## Kamus

### jv.wiktionary.json — Lembar kerja (SOURCE OF TRUTH)
- 44.585 entries dari jv.wiktionary XML dump (parser BENAR)
- Field: word (lemma baku), definisi (arti Jawa), aksara, ngoko, krama, terjemahan_indo, keterangan
- 8.618 entries dgn indo (cross-ref master lama)
- 2.397 entries dgn register (dari template {{ngoko|}}/{{krama|}})
- 2.165 entries LENGKAP (indo + ngoko + krama)
- User validasi manual: isi indo (translate dari definisi Jawa), isi register (word→ngoko/krama)

### kamus-tui.py (v16) — Editor kamus
- Edit jv.wiktionary.json
- Search, browse, edit per entry
- Deteksi duplikat (lintas field, lintas entry)
- Audit flags (parser leak, indo long, word long, dll)
- Tambah entry baru (workflow SRT editor)
- Upload ke Supabase (hanya entries terverifikasi user)

### Supabase — Database kamus terverifikasi
- User upload manual setelah validasi satu-satu
- Schema: id, ngoko, aksara, krama, indo, keterangan, sumber, status, created_at, updated_at
- Ground of truth = Supabase (bukan JSON)

### parse-jv-wiktionary-v2.py — Parser XML dump
- Parse jv.wiktionary XML dump Wikimedia (44.585 entries)
- Ekstrak: word (lemma), aksara, kelas, definisi (arti Jawa), ngoko/krama (dari template)
- Template {{ngoko|krama_form}} = krama pasangan, title = ngoko
- Template {{krama|ngoko_form}} = ngoko pasangan, title = krama
- Source: https://dumps.wikimedia.org/jvwiktionary/latest/jvwiktionary-latest-pages-articles.xml.bz2

## Workflow

```bash
# Setup (sekali saja)
cd ~/Dubbing
source venv/bin/activate

# 1. Download
python3 yt-dlp-tui.py

# 2. Separasi vocal
python3 demucs-tui.py

# 3. Generate TTS
python3 edge-tts-tui.py

# 4. Edit SRT (web app)
#    https://srt-splitter.vercel.app/

# 5. Mix final
python3 mix-tui.py

# Kamus (sambil kerja)
python3 kamus-tui.py
```

## Download

```bash
cd ~/Dubbing
curl -L -o config.py "https://raw.githubusercontent.com/emailnyamahmud-afk/srt-splitter/main/scripts/config.py"
curl -L -o yt-dlp-tui.py "https://raw.githubusercontent.com/emailnyamahmud-afk/srt-splitter/main/scripts/yt-dlp-tui.py"
curl -L -o demucs-tui.py "https://raw.githubusercontent.com/emailnyamahmud-afk/srt-splitter/main/scripts/demucs-tui.py"
curl -L -o edge-tts-tui.py "https://raw.githubusercontent.com/emailnyamahmud-afk/srt-splitter/main/scripts/edge-tts-tui.py"
curl -L -o mix-tui.py "https://raw.githubusercontent.com/emailnyamahmud-afk/srt-splitter/main/scripts/mix-tui.py"
curl -L -o kamus-tui.py "https://raw.githubusercontent.com/emailnyamahmud-afk/srt-splitter/main/scripts/kamus-tui.py"
curl -L -o upload-supabase.py "https://raw.githubusercontent.com/emailnyamahmud-afk/srt-splitter/main/scripts/upload-supabase.py"
curl -L -o jv.wiktionary.json "https://raw.githubusercontent.com/emailnyamahmud-afk/srt-splitter/main/public/jv.wiktionary.json"
```
