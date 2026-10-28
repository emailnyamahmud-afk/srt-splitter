# Scripts — SRT Splitter + Dubbing

Python TUI untuk workflow dubbing + kamus Jawa.

## 10 TUI

| # | TUI | Status |
|---|-----|--------|
| 1 | yt-dlp-tui.py v6.2 (MP4+MP3+SRT, cookies anti-bot YT/FB/TikTok/IG) | ✅ Production (FB+YT confirmed) |
| 2 | demucs-tui.py (M1 MPS) | ✅ Production |
| 3 | kamus-tui.py v16 | ✅ Production (audit) |
| 4 | Web app | ⚠ Prototype |
| 5 | SRT editor (web, pakai SRT ID) | ⏳ Pending |
| 6 | edge-tts-tui.py v7.4 (paralel-safe, lock file + 429 retry) | ✅ Production |
| 7 | mix-tui.py v3.8.2 | ✅ Production (all tested + logo + fade) |
| 8 | whisper-tui.py v1.1 (faster-whisper) | ✅ Production (SRT quality 90-95%) |
| 9 | srt-editor-tui.py v1.0.1 (fix typo SRT hasil translate) | ✅ Production |
| 10 | shorts-tui.py v1.0 (pecah MP4 jadi N shorts via JSON timestamps AI) | 🆕 New |

## Pipeline (3 alur)

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

> **srt-editor-tui.py** (TUI #9, opsional) untuk fix typo/konteks SRT hasil translate sebelum masuk edge-tts. Skip kalau SRT ori sudah clean.

## Scripts

### Pipeline

| Script | Fungsi | Output |
|--------|--------|--------|
| yt-dlp-tui.py v6.2 | Download MP4 + MP3 + SRT Indonesia | HDD/input/ |
| demucs-tui.py | Vocal separation (M1 MPS) | HDD/demucs/ |
| edge-tts-tui.py v7.4 | TTS generation (paralel-safe, lock file + 429 retry) | HDD/tts/ |
| mix-tui.py v3.7.6 | Final mix (6 mode, MUTE COMPLETE) | HDD/mix/ |

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
python3 edge-tts-tui.py        # 3. Generate dub dari .final.srt (atau SRT asli kalau sudah clean)
python3 mix-tui.py             # 4. Mix Mode E (Stream) / F (Burn)

# Alur PROPER (pakai Demucs)
python3 yt-dlp-tui.py
python3 srt-editor-tui.py      # fix typo SRT dulu kalau perlu
python3 demucs-tui.py          # 3. Split vokal dari SFX
python3 edge-tts-tui.py
python3 mix-tui.py             # 5. Mix Mode A (Stream) / B (Burn)

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

## shorts-tui.py v1.0

Pecah MP4 final (sudah vertikal + hardsub) jadi N shorts untuk YouTube
Shorts/TikTok/Reels. Pakai JSON timestamps dari ChatGPT/Claude/Gemini sebagai
"peta" potongan.

### Workflow

```
1. User paste SRT ke ChatGPT → minta "pilih 30 segment menarik untuk Shorts"
2. ChatGPT return JSON array: [{start, end, title}, ...]
3. User save JSON ke /Volumes/HDD/Dubbing/shorts/{film}.timestamps.json (folder yang sama dgn output, rapi)
4. python3 shorts-tui.py
   → pilih JSON + MP4 final (dari HDD/mix/) + output dir
   → TUI ffmpeg cut per segment (stream copy, ~0.5s per short)
   → 30 MP4 di HDD/shorts/{film-name}/short-001.mp4 s/d short-030.mp4
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
# Output: {prefix}-short-001.mp4 s/d {prefix}-short-030.mp4
```

### Prompt template untuk AI

Lihat `tutor-shorts-prompt.md` — 3 prompt templates (default 30 shorts,
custom jumlah, tema spesifik). Tinggal copy paste ke ChatGPT/Claude/Gemini.

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
| **Stream copy** (`-c copy`) | ~0.5s per short, 30 shorts = 15 detik | Mungkin ada keyframe glitch di detik 1 | ✅ Ya |
| Re-encode (`libx264 -crf 23`) | ~3-5s per short, 30 shorts = ~3 menit | Clean cut, no glitch | |

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
        └── S2-FB-Mandarin-short-030.mp4
```

JSON + output MP4 di folder yang sama (`shorts/`), ga campur folder lain.

### Validasi (yang TUI cek)

- JSON valid + punya `start` dan `end` (number)
- `end > start` (kalau salah → error)
- Durasi segment ≤ 60s (warning, tetap lanjut dengan konfirmasi)
- Segment overlap dengan sebelumnya (warning)
- End > durasi video total (warning)
- MP4 file ada dan tidak corrupt (ffprobe check)

## Struktur Path

```
SSD ~/Dubbing/           → scripts + venv + jv.wiktionary.json
HDD /Volumes/HDD/Dubbing/ → input/ demucs/ tts/ mix/ shorts/ .env
```

config.py handle path:
- `ensure_hdd()` — cek HDD ter-colok, buat subfolder
- `ensure_kamus()` — cek jv.wiktionary.json ada
- `load_env()` — load .env dari HDD
