# SRT Splitter + Dubbing Jawa

Pipeline dubbing Mandarin→Jawa end-to-end. Web app + Python TUI.

**Live:** https://srt-splitter.vercel.app/

## 7 TUI — Tugas masing-masing

| # | TUI | Tugas | Status |
|---|-----|-------|--------|
| 1 | `yt-dlp-tui.py` | Download MP4 + audio MP3 + SRT Indonesia | ✅ Production |
| 2 | `demucs-tui.py` | Split audio → no_vocals.mp3 (SFX bersih) + vocals (auto-hapus) | ✅ Production |
| 3 | `kamus-tui.py` | User edit JSON kamus untuk kurasi manual (sebelum masuk DB) | ✅ Production (user audit) |
| 4 | Web app (srt-splitter) | Translate SRT Indonesia → Jawa (pakai kamus Supabase) | ⚠ Prototype (perlu penyesuaian) |
| 5 | SRT editor | Sementara pakai SRT Indonesia (SRT Jawa = nunggu kamus + web selesai) | ⏳ Pending |
| 6 | `edge-tts-tui.py` | Generate audio dub dari SRT (5000+ cue, 2-5 jam durasi) | ✅ Production |
| 7 | `mix-tui.py` v3.7.1 | Mix MP4 + audio → final video (6 mode + SRT-driven ducking + bitrate) | ✅ Production-ready (A/B/C/D tested, E/F baru v3.7.1) |

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

Catatan: Sementara SRT pake Indonesia (kalau SRT Jawa = harus selesai kamus + web). Edge-tts-tui generate dub dari SRT Indonesia. Mix-tui jahit MP4 + no_vocals + dub → final video.

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
- MP4 (video) + MP3 (audio via yt-dlp convert, VBR best quality)
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

### 5. mix-tui.py v3.7.1 — Final mix (6 mode + SRT-driven ducking + pilihan bitrate)

User pilih 3 mode input × 2 mode output = 6 kombinasi:

| # | Mode Input | Mode Output | Output filename | Status |
|---|------------|-------------|-----------------|--------|
| A | Full (MP4+SFX+Dub) | Stream copy | `{prefix}-id-final.mp4` | ✅ **REKOMENDASI proper**, 5 film sukses, clean sempurna |
| B | Full (MP4+SFX+Dub) | Burn SRT | `{prefix}-id-final-sub.mp4` | ✅ REKOMENDASI proper + hardsub |
| C | Simple (MP4+Dub) | Stream copy | `{prefix}-id-simple.mp4` | ✅ **REKOMENDASI cepat**, sync 100% |
| D | Simple (MP4+Dub) | Burn SRT | `{prefix}-id-simple-sub.mp4` | ✅ REKOMENDASI cepat + hardsub |
| E | Original (MP4+MP3 ori+Dub) | Stream copy | `{prefix}-id-orig.mp4` | ✅ **REKOMENDASI cepat**, v3.7.1 SRT-driven ducking |
| F | Original (MP4+MP3 ori+Dub) | Burn SRT | `{prefix}-id-orig-sub.mp4` | ✅ REKOMENDASI cepat + hardsub, v3.7.1 SRT-driven ducking |

**v3.7.1 SIMPLIFIKASI: 1 SRT Indonesia cukup** (timestamps identik dengan SRT Mandarin):
- v3.7 awalnya butuh 2 SRT terpisah (SRT Mandarin untuk duck + SRT Indonesia untuk burn)
- v3.7.1: 1 SRT Indonesia dipakai untuk 2 tujuan (duck + burn)
- User feedback: "SRT mandarin tak relevan, karena SRT id juga identik timesmapnya"

**v3.7 update: Original mode REKOMENDASI lagi** (fix masalah v3.6 vokal asli bocor):
- v3.6 pakai sidechain compress → vokal asli Mandarin tetap terdengar (cuma turunkan volume, tidak hilang)
- v3.7/v3.7.1 pakai **SRT-driven ducking**: SRT Indonesia = window duck MP3 ori
  - Saat cue SRT aktif → MP3 ori volume turun ke 6.25% (-24 dB, hampir mute)
  - Lead 100ms + tail 100ms (smooth transition)
  - SFX/musik latar tetap normal di gap antar dialog
- Cocok untuk: produksi cepat skala besar (skip Demucs ~16 menit/film)

**Verdict user (sebelum v3.7):**
- Mode A/B (Full) = paling baik, clean benar-benar sempurna (no_vocals dari Demucs)
- Mode C/D (Simple) = versi cepat, cukup untuk preview/dialog dominan
- Mode E/F (Original) = v3.6 NOT RECOMMENDED → v3.7.1 fix dengan SRT-driven ducking (REKOMENDASI lagi)

- Default mode = Full (workflow existing, 5 film sukses)
- Simple mode = MP4 + Dub saja, no SFX, no ducking. Untuk preview cepat / film dialog dominan.
- Original mode (v3.7.1) = MP4 + MP3 ori + Dub + 1 SRT Indonesia (untuk duck + burn). Skip Demucs, vokal asli di-duck sesuai cue SRT.
- Burn SRT: 4 posisi (Opsi A/B/C/D, Justify=2 center), M1 VideoToolbox 35x hardware
- **Video bitrate (v3.5 NEW)**: pilihan untuk Mode B & D & F (burn SRT wajib re-encode)
  - 1 Mbps → ~1.2 GB/2jam (hemat, quality OK untuk 480p hardsub)
  - 1.5 Mbps → ~1.8 GB/2jam (default, seimbang)
  - 2 Mbps → ~2.3 GB/2jam (subtitle paling sharp)
  - 4 Mbps → ~4.5 GB/2jam (HD-ready, kalau source ori high quality)
- Ducking: 3 strategy (v3.7.1)
  - Full mode: sidechain compress (existing, pilih 6/12/18 dB)
  - Original mode (v3.7.1): SRT-driven volume expression (-24 dB fixed, lead/tail 100ms)
  - Simple mode: auto-skip (no SFX, no ducking concept)
- Cari MP4 di HDD/input/, SFX di HDD/demucs/, MP3 ori di HDD/input/, dub di HDD/tts/, SRT Indonesia di HDD/input/
- Output: HDD/mix/
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
