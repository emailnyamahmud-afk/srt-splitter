# Scripts — SRT Splitter + Dubbing Multi-Bahasa

Python TUI untuk workflow dubbing bahasa eksternal (Mandarin, English, Jepang, Italia, dll) → Indonesia / Jawa / Sunda.

## 12 TUI

| # | TUI | Status |
|---|-----|--------|
| 1 | yt-dlp-tui.py v6.2 (MP4+MP3+SRT, cookies anti-bot YT/FB/TikTok/IG) | ✅ Production (FB+YT confirmed) |
| 2 | demucs-tui.py (M1 MPS) | ✅ Production |
| 3 | kamus-tui.py v16 | ✅ Production (audit) |
| 4 | Web app | ⚠ Prototype |
| 5 | SRT editor (web, pakai SRT ID) | ⏳ Pending |
| 6 | edge-tts-tui.py v7.4 (paralel-safe, lock file + 429 retry) | ✅ Production |
| 7 | mix-tui.py v3.8.2 | ✅ Production (all tested + logo + fade) |
| 8 | whisper-tui.py v2.0 (whisper.cpp, Metal GPU native) | ✅ Production (Metal M1, 5.3x realtime) |
| 9 | srt-editor-tui.py v1.0.1 (fix typo SRT hasil translate) | ✅ Production |
| 10 | shorts-tui.py v1.1 (Shorts via AI JSON atau Part via SRT auto-split) | ✅ Production (Shorts 60/60 + Part auto-split) |
| 11 | shorts-csv-tui.py v1.0 (metadata CSV + manifest untuk YouTube Studio) | ✅ Production (test 60 segment, CSV 19.8 KB + manifest 30.4 KB) |
| 12 | merge-tui.py v1.0 (gabungin multi-video jadi 1 panjang, 3 mode) | ✅ Production (stream copy + re-encode) |

## Pipeline (4 alur)

### PROPER — clean sempurna (pakai Demucs)

```
yt-dlp → srt-editor → demucs → edge-tts → mix Full (A/B)
→ ~350 MB stream / ~2-4.5 GB burn
→ clean sempurna (no_vocals dari Demucs + ducking sidechain)
```

### CEPAT — dialog dominan (skip Demucs, no SFX)

```
yt-dlp → srt-editor → edge-tts → mix Simple (C/D)
→ ~350 MB stream / ~2-4.5 GB burn
→ no SFX layer, Dub copy as-is
```

### MUTE — skip Demucs, MUTE COMPLETE (v3.7.6)

```
yt-dlp → srt-editor → edge-tts → mix Original (E/F)
→ ~1 GB stream / ~4.5 GB burn
→ MP3 ori MUTE TOTAL saat cue (amultiply + SRT-driven envelope)
→ SFX/musik latar normal di gap
```

### SHORTS — pecah MP4 final jadi 60 shorts (v1.0)

```
mix-tui output → Dola AI (skill shorts-json) → shorts-tui → shorts-csv-tui → YouTube Studio
→ Upload SRT ke Dola, ketik "buat shorts", dapat 60 segment JSON
→ shorts-tui: 60 MP4 (~94 detik, stream copy)
→ shorts-csv-tui: CSV + manifest (metadata untuk copy-paste YouTube)
→ User drag 60 MP4 ke YouTube Studio + copy-paste dari manifest
```

> **srt-editor-tui.py** (TUI #9, opsional) untuk fix typo/konteks SRT hasil translate sebelum masuk edge-tts. Skip kalau SRT ori sudah clean.

### MERGE — gabungin multi-video jadi 1 panjang (v1.0)

```
mix-tui output × N → merge-tui → 1 video panjang
 Input: HDD/mix/*.mp4 (sudah dub ID + burn sub ID)
 Output: HDD/merged/merged_YYYYMMDD_HHMMSS.mp4
 3 mode: stream copy (super cepat) / re-encode + target res / re-encode pakai res file pertama
 Shortcut: ketik "mix" di menu [1] untuk list semua MP4 di HDD/mix/
```

> **merge-tui.py** (TUI #12): gabungin S1+S2+S3+S4 jadi 1 video panjang. Pakai ffmpeg concat demuxer (stream copy) atau re-encode (kalau res beda).

## Scripts

### Pipeline

| Script | Fungsi | Output |
|--------|--------|--------|
| yt-dlp-tui.py v6.2 | Download MP4 + MP3 + SRT Indonesia | HDD/input/ |
| demucs-tui.py | Vocal separation (M1 MPS) | HDD/demucs/ |
| edge-tts-tui.py v7.4 | TTS generation (paralel-safe, lock file + 429 retry) | HDD/tts/ |
| mix-tui.py v3.7.6 | Final mix (6 mode, MUTE COMPLETE) | HDD/mix/ |
| merge-tui.py v1.0 | Gabungin multi-video jadi 1 panjang (3 mode) | HDD/merged/ |

### Kamus

| Script | Fungsi |
|--------|--------|
| kamus-tui.py v16 | TUI editor jv.wiktionary.json |
| config.py | Base path SSD/HDD |
| upload-supabase.py | Upload kamus terverifikasi ke Supabase |
| parse-jv-wiktionary-v2.py | Parser jv.wiktionary XML |
| srt-frequency-analyzer.py | Analisis frekuensi kata SRT |

### Tutor

| File | Isi |
|------|-----|
| tutor-demucs-setup.md | Setup Demucs M1 MPS + kapan perlu/skip |

## mix-tui v3.8.2 — 6 mode + logo + smooth fade

| # | Mode | Ducking | Durasi |
|---|------|---------|--------|
| A | Full + Stream | sidechain | ~3 min |
| B | Full + Burn | sidechain | ~5 min |
| C | Simple + Stream | no ducking | ~1 min |
| D | Simple + Burn | no ducking | ~5 min |
| **E** | **Original + Stream** | **amultiply MUTE** ⭐ | ~4 min |
| F | Original + Burn | amultiply MUTE | ~5-27 min* |

### Bitrate (Mode B/D/F, burn SRT)

| Bitrate | Size (2 jam) |
|---------|-------------|
| 1 Mbps | ~1.2 GB (hemat, user confirmed > ori) |
| 1.5 Mbps | ~1.8 GB (default) |
| 2 Mbps | ~2.3 GB (subtitle sharp) |
| 4 Mbps | ~4.5 GB (HD-ready) |

## Install

```bash
cd ~/Dubbing
source venv/bin/activate
pip3 install questionary edge-tts yt-dlp torchaudio demucs numpy
brew install ffmpeg
```

## Workflow

```bash
cd ~/Dubbing
source venv/bin/activate

# Alur CEPAT + MUTE (skip Demucs)
python3 yt-dlp-tui.py         # 1. MP4 + MP3 + SRT (cookies anti-bot YT/FB/TikTok/IG)
python3 srt-editor-tui.py      # 2. Fix typo SRT hasil translate (opsional, kalau dari editsub/Google Translate)
python3 edge-tts-tui.py        # 3. Generate dub dari .final.srt (paralel 2 TTS di VS Code)
python3 mix-tui.py             # 4. Mix Mode E (Stream) / F (Burn)

# Alur PROPER (pakai Demucs)
python3 yt-dlp-tui.py
python3 srt-editor-tui.py      # fix typo SRT dulu kalau perlu
python3 demucs-tui.py          # 3. Split vokal dari SFX
python3 edge-tts-tui.py
python3 mix-tui.py             # 5. Mix Mode A (Stream) / B (Burn)

# Alur SHORTS (setelah mix selesai)
# 1. Upload SRT ke Dola AI → ketik "buat shorts" → download JSON (60 segment)
python3 shorts-tui.py         # 2. Pecah MP4 jadi 60 shorts (~94 detik, stream copy)
python3 shorts-csv-tui.py     # 3. Generate CSV + manifest (metadata untuk YouTube)
# 4. Drag 60 MP4 ke YouTube Studio + copy-paste dari manifest

# Alur MERGE (gabungin S1-S4 jadi 1 video panjang)
python3 merge-tui.py          # Input: HDD/mix/*.mp4 → Output: HDD/merged/merged_*.mp4
# Ketik "mix" di menu [1] untuk list semua MP4 di HDD/mix/

# Kamus (parallel)
python3 kamus-tui.py
```

## edge-tui v7.4 — Paralel Support

Generate 2-3 TTS sekaligus di terminal berbeda. Cocok untuk workflow "malam
tinggal generate → tidur → pagi ready 2 file dub".

### Cara paralel (zero code change)

```bash
# Terminal 1:
cd ~/Dubbing && source venv/bin/activate
python3 edge-tts-tui.py
# → pilih SRT A → pilih output dir → prefix default = nama SRT A

# Terminal 2 (tab baru atau window baru):
python3 edge-tts-tui.py
# → pilih SRT B (BEDA file SRT!) → prefix default = nama SRT B
# → kalau SRT sama, TUI auto-suggest prefix-2 → Enter saja
```

### Yang baru di v7.4

| Fitur | Manfaat |
|-------|---------|
| **Lock file** (`tts/.{prefix}.lock`) | Detect kalau prefix lagi dipakai process lain |
| **Prefix auto-suggest** | Kalau collision → tanya "ganti jadi {prefix}-2?" → Enter saja |
| **PID display** di header | Tracking paralel di Activity Monitor (PID xxxxx) |
| **429 retry** | Auto-recover kalau Microsoft throttle (30s → 60s → 120s → skip) |
| **Stale lock cleanup** | PID mati → lock file lama dihapus otomatis |

### RAM per instance (untuk 4 jam audio)

| Instance paralel | RAM total | Mac 16GB | Mac 8GB |
|------------------|----------|----------|---------|
| 1 | ~1.6 GB | Aman | Aman |
| 2 (recommended) | ~3.2 GB | Aman (sisa ~13 GB) | Riskan |
| 3 | ~4.8 GB | Aman (sisa ~11 GB) | Bahaya |

### Compatibility dengan mix-tui.py

Output tetap di `tts/{prefix}-audio-id-dub.wav` (flat di TTS_DIR root, BUKAN
subfolder). `mix-tui.py` cari dub pakai glob non-recursive → langsung nemu.

Cek RAM free sebelum paralel:
```bash
vm_stat | head -5  # Mac
# atau buka Activity Monitor → Memory
```

## srt-editor-tui.py v1.0.1

TUI editor untuk SRT hasil Google Translate / editsub.com. Buka SRT → browse per
halaman → edit inline → mark reviewed / flag → glossary bulk replace → save final.

### Cara pakai

```bash
cd ~/Dubbing
source venv/bin/activate

# Mode interaktif (pilih SRT dari list — glob dari cwd + HDD)
python3 srt-editor-tui.py

# Mode eksplisit (path SRT beneran)
python3 srt-editor-tui.py /Volumes/HDD/Dubbing/input/S2-FB-Mandarin.id.srt

# Pakai glossary sendiri (override default inline)
python3 srt-editor-tui.py /Volumes/HDD/Dubbing/input/S2-FB-Mandarin.id.srt \
    --glossary ~/Dubbing/my-glossary.json
```

### Workflow di pipeline dubbing

```bash
# Setelah dapet SRT Indonesia dari editsub.com / Google Translate
python3 srt-editor-tui.py /Volumes/HDD/Dubbing/input/S2-FB-Mandarin.id.srt
# → di TUI: F2 (glossary) → Apply ALL → review manual cue-cue problem → Ctrl-C / Save
# → output: /Volumes/HDD/Dubbing/input/S2-FB-Mandarin.id.final.srt

# Pakai final.srt untuk edge-tts
python3 edge-tts-tui.py
# → pilih file: S2-FB-Mandarin.id.final.srt
```

### Output (di folder yang sama dengan input)

| File | Tujuan |
|------|--------|
| `<stem>.final.srt` | **Output final** — pakai untuk edge-tts / mix-tui |
| `<stem>.srt.bak` | Backup original (dibuat 1x saat save pertama) |
| `<stem>.working.json` | Auto-save state — resume kapan saja |

### Menu TUI

| Key | Aksi |
|-----|------|
| ↑/↓ | Pilih cue (dalam browse mode) |
| Enter | View cue detail |
| `e` | Edit text (single-line, atau buka $EDITOR untuk multi-line) |
| `r` | Revert ke original |
| `m` | Toggle "reviewed" (sudah diperiksa) |
| `f` | Toggle "flagged" (tandai bermasalah) |
| `n` | Lompat ke cue berikutnya yang belum di-review |

### Status icons

| Icon | Arti |
|------|------|
| ` ` (kosong) | Belum disentuh |
| `✓` | Reviewed |
| `!` | Flagged (masalah) |
| `*` | Changed (text berubah) |
| `@` | Auto-fixed by glossary |

### Glossary default (inline, 19 entries)

Dari review S2-FB-Mandarin.id.srt (5162 cues):

- **Names** (11): Lin Zhao, Xie Changfeng, Wang Haochuan, Ma Zhenbang, Chen Su,
  Qin Hongying, Mu En, Yao Sihai, Zhou Lizheng, Qin Fenglu, Li Kui
- **Terms** (8): Xiangjun, panah otomatis, obat luka emas, Jiedushi,
  menarik pelatuk, laras meledak, pembalasan, akademi

Match case-insensitive (regex IGNORECASE), jadi "Payung emas" dan "payung emas"
sama-sama ter-replace.

### Format glossary JSON (untuk override)

```json
{
  "version": 1,
  "entries": [
    {
      "canonical": "Lin Zhao",
      "variants": ["Lin Yanya", "Peti mati Lin"],
      "scope": "names"
    }
  ]
}
```

- `canonical`: bentuk yang diinginkan (final)
- `variants`: bentuk-bentuk salah yang akan diganti dengan canonical
- `scope`: info saja, tidak mempengaruhi behavior ("names" / "terms" / "all")

### Resume (kalau quit tanpa save)

TUI auto-save ke `.working.json` setiap save / Ctrl-C. Buka lagi file SRT yang
sama → auto-resume (progress tidak hilang).

Mau mulai dari awal (reset progress)? Hapus `<stem>.working.json`, TUI akan load
dari `.srt` original.

## merge-tui.py v1.0 — TUI #12: gabungin multi-video jadi 1 panjang

Gabungin output mix-tui (sudah dub ID + burn sub ID) dari beberapa film/season
jadi 1 video panjang. Pakai ffmpeg concat demuxer (stream copy) atau re-encode
(kalau res beda).

### Cara pakai

```bash
cd ~/Dubbing
source venv/bin/activate
python3 merge-tui.py
# [1] Tambah file: ketik "mix" untuk list HDD/mix/*.mp4 (auto-glob), atau ketik path manual
# [6] Auto-detect: cek res/codec/fps semua file, rekomendasi mode
# [7] Stream copy (super cepat, butuh codec+res+fps sama)
# [8] Re-encode + pilih target res (1080p/720p/480p/custom) — kalau res beda
# [9] Re-encode pakai res file pertama
# Output: HDD/merged/merged_YYYYMMDD_HHMMSS.mp4 (default)
```

### 3 mode

| Mode | Kecepatan | Syarat | Kapan dipakai |
|------|----------|--------|--------------|
| [7] Stream copy (concat demuxer + `-c copy`) | super cepat (no re-encode) | codec+res+fps sama | S1-S4 dari source sama, mix-tui Mode sama |
| [8] Re-encode + pilih target res | lambat | res beda | S1-S4 dari source beda, mau output standard 1080p/720p |
| [9] Re-encode pakai res file pertama | lambat | res beda, ikut file #1 | S1-S4 dari source beda, mau ikut res file pertama |

### Auto-detect (menu [6])

Probe semua file, bandingin res/codec/fps:
- Semua sama → rekomendasi mode [7] stream copy (super cepat, no re-encode)
- Ada perbedaan → rekomendasi mode [8] atau [9] (re-encode wajib)

### Progress bar

Pakai `ffmpeg -progress pipe:1`, parse `out_time_ms` vs total duration → live progress bar.

### Output

Default: `HDD/merged/merged_YYYYMMDD_HHMMSS.mp4` (folder `merged/` dibuat auto oleh `ensure_hdd()`).
Bisa ganti via menu [5].

## shorts-tui.py v1.0 — ✅ Production

Pecah MP4 final (sudah vertikal + hardsub) jadi N shorts untuk YouTube
Shorts/TikTok/Reels. Pakai JSON timestamps dari ChatGPT/Claude/Gemini/Dola AI
sebagai "peta" potongan.

### Test Result (28 Okt 2026)
- ✅ Test 1: 30/30 sukses (film S5, 56.5s total, 235.8 MB output)
- ✅ Test 2: 60/60 sukses (film S5, 94.1s total, 803.8 MB output) — default production
- ✅ Stream copy ~1.6 detik per short (lebih cepat dari estimasi 0.5s)
- ✅ Avg durasi 50.7s/short (maksimum mendekati 60s, optimize untuk retention tinggi)
- ✅ Stream copy glitch: tidak ada (VLC-validated user)
- ✅ JSON dari Dola skill `shorts-json` (60 segment, 0 warning, hook di awal kalimat)

### Workflow

```
1. User paste SRT ke ChatGPT/Claude/Gemini/Dola AI → minta "pilih 60 segment menarik untuk Shorts"
2. ChatGPT return JSON array: [{start, end, title}, ...]
3. User save JSON ke /Volumes/HDD/Dubbing/shorts/{film}.timestamps.json (folder yang sama dgn output, rapi)
4. python3 shorts-tui.py
   → pilih JSON + MP4 final (dari HDD/mix/) + output dir
   → TUI ffmpeg cut per segment (stream copy, ~0.5s per short)
   → 60 MP4 di HDD/shorts/{film-name}/short-001.mp4 s/d short-060.mp4
5. Upload ke YouTube Shorts/TikTok/Reels
```

### Cara pakai

```bash
cd ~/Dubbing
source venv/bin/activate
python3 shorts-tui.py
# Step 1: pilih JSON timestamps (dari cwd + HDD)
# Step 2: pilih MP4 final (dari HDD/mix/)
# Step 3: output dir (default: HDD/shorts/{film-name}/ — subfolder per film)
# Step 4: mode cut (default: stream copy, super cepat)
# Output: {prefix}-short-001.mp4 s/d {prefix}-short-N.mp4 (N = jumlah segment di JSON, default 60)
```

### Prompt template untuk AI

Lihat `tutor-shorts-prompt.md` — 3 prompt templates (default 60 shorts,
custom jumlah, tema spesifik). Tinggal copy paste ke ChatGPT/Claude/Gemini/Dola AI.

### Format JSON (input dari AI)

```json
[
  {"start": 12.5, "end": 65.3, "title": "Lin Zhao tiba di Qin family"},
  {"start": 145.2, "end": 198.7, "title": "Konfrontasi paman"},
  ...
]
```

- `start`, `end`: detik (float)
- `title`: opsional (default: "Short N" kalau kosong)
- Wrapper alternatif: `{"segments": [...]}` juga diterima

### Cut mode

| Mode | Kecepatan | Kualitas | Default |
|------|-----------|----------|---------|
| **Stream copy** (`-c copy`) | ~0.5s per short, 60 shorts = ~2 menit | Mungkin ada keyframe glitch di detik 1 | ✅ Ya |
| Re-encode (`libx264 -crf 23`) | ~3-5s per short, 60 shorts = ~5 menit | Clean cut, no glitch | |

### Output structure

```
HDD/Dubbing/
├── input/        ← yt-dlp output (MP4 + MP3 + SRT)
├── demucs/       ← no_vocals
├── tts/          ← dub WAV
├── mix/          ← MP4 final (input untuk shorts-tui)
└── shorts/        ← shorts-tui: JSON + MP4 output
    ├── S2-FB-Mandarin.timestamps.json   ← JSON timestamps (input dari AI)
    └── S2-FB-Mandarin/                  ← subfolder per film (output MP4)
        ├── S2-FB-Mandarin-short-001.mp4
        ├── S2-FB-Mandarin-short-002.mp4
        ├── ...
        └── S2-Melintas-Zaman-short-060.mp4
```

JSON + output MP4 di folder yang sama (`shorts/`), ga campur folder lain.

### Validasi (yang TUI cek)

- JSON valid + punya `start` dan `end` (number)
- `end > start` (kalau salah → error)
- Durasi segment ≤ 60s (warning, tetap lanjut dengan konfirmasi)
- Segment overlap dengan sebelumnya (warning)
- End > durasi video total (warning)
- MP4 file ada dan tidak corrupt (ffprobe check)

## shorts-csv-tui.py v1.0

Generate metadata CSV + manifest text dari JSON timestamps (Dola output) untuk
copy-paste saat upload manual di YouTube Studio.

### Workflow

```
1. Dola skill shorts-json → JSON (60 segment + title, dari SRT Indonesia)
2. shorts-tui.py → 60 MP4 di HDD/shorts/{film}/
3. shorts-csv-tui.py (TUI ini) → CSV + manifest text
4. User drag 60 MP4 ke YouTube Studio (upload paralel)
5. User copy-paste metadata dari manifest ke form YouTube per video
```

### Cara pakai

```bash
cd ~/Dubbing
source venv/bin/activate
python3 shorts-csv-tui.py
# Step 1: pilih JSON timestamps (dari HDD/shorts/)
# Step 2: pilih folder MP4 (dari shorts-tui output)
# Step 3: nama film (untuk template description)
# Step 4: description template (placeholder {film_name}, {title})
# Step 5: tags + category (default: drama,mandarin,shorts + Entertainment)
# Step 6: schedule (default: besok 12:00, interval 1 jam)
# Step 7: output CSV + manifest
```

### Output

| File | Format | Tujuan |
|------|--------|--------|
| `{film}.metadata.csv` | CSV (filename, title, description, tags, category, schedule) | Buka di Excel/Numbers |
| `{film}.manifest.txt` | Plain text, copy-paste friendly | Copy-paste di YouTube Studio per video |

### Custom yang user bisa set

- **Film name** (untuk description template)
- **Description template** (placeholder `{film_name}`, `{title}`)
- **Tags** (default: `drama, mandarin, shorts, dubbing, indonesia`)
- **Category** (Entertainment / Film & Animation / People & Blogs / Comedy / Education)
- **Schedule start** (default: besok 12:00)
- **Interval** (30 menit / 1 jam / 2 jam / 3 jam / 6 jam / 1 hari)

## Struktur Path

```
SSD ~/Dubbing/           → scripts + venv + jv.wiktionary.json
HDD /Volumes/HDD/Dubbing/ → input/ demucs/ tts/ mix/ shorts/ parts/ merged/ .env
```

config.py handle path:
- `ensure_hdd()` — cek HDD ter-colok, buat subfolder (input, demucs, tts, mix, shorts, parts, merged)
- `ensure_kamus()` — cek jv.wiktionary.json ada
- `load_env()` — load .env dari HDD
- Vars: `INPUT_DIR`, `DEMUCS_DIR`, `TTS_DIR`, `MIX_DIR`, `SHORTS_DIR`, `PARTS_DIR`, `MERGED_DIR`
