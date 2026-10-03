# Tutor: Workflow Dubbing Mandarin → Jawa (Fase 1-4)

Panduan lengkap untuk dub video Mandarin ke Jawa dengan audio natural, SFX preserve, dan video slow-mo otomatis.

## Arsitektur Workflow

```
┌─────────────────────────────────────────────────────────────────┐
│ Fase 1: Persiapan bahan                                         │
│   MP4 Mandarin + SRT Mandarin (sumber)                          │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ Fase 2: Web app (https://srt-splitter.vercel.app/)              │
│   - Translate SRT Mandarin → Jawa                                │
│   - Rapikan tatabahasa Jawa (script Python)                      │
│   - Dubbing Mode: audio natural → SRT baru → retime-map JSON    │
│   Output: audio-jawa.wav + subs-jawa-new.srt + retime-map.json  │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ Fase 3 (opsional): SFX Separation dengan Demucs                 │
│   - Input: MP4 Mandarin                                         │
│   - Output: vocals-mandarin.wav (dibuang) + sfx-backsound.wav   │
│   - Berguna kalau MP4 punya backsound yang ingin dipertahankan  │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ Fase 4: Retime Video dengan FFmpeg (Python lokal)              │
│   - Input: MP4 + SRT Mandarin + SRT Jawa + audio Jawa (+ SFX)  │
│   - Output: mp4-jawa.mp4 (video slow-mo + audio Jawa + SFX)    │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ Fase 5: Edit final di DaVinci Resolve (manual)                  │
│   - Tambah musik, efek, color grade                             │
│   - Export final video                                          │
└─────────────────────────────────────────────────────────────────┘
```

## Prerequisite

### Untuk Fase 2 (Web app)
- Browser modern (Chrome, Firefox, Safari, Edge)
- Internet connection (Edge TTS butuh proxy Vercel)
- Tidak perlu install apapun

### Untuk Fase 3-4 (Python lokal)
- Python 3.8+
- ffmpeg (`brew install ffmpeg` di Mac, `sudo apt install ffmpeg` di Linux)
- Demucs (opsional, untuk SFX separation): `pip install demucs`

Cek install:
```bash
python3 --version
ffmpeg -version
ffprobe -version
demucs --help  # opsional
```

## Fase 1: Persiapan Bahan

Siapkan:
- `mandarin.mp4` — video Mandarin asli
- `original.srt` — subtitle Mandarin (dari sumber, atau generate dengan Whisper)

Untuk generate SRT dari MP4 (kalau belum punya):
```bash
# Pakai OpenAI Whisper (local)
pip install openai-whisper
whisper mandarin.mp4 --model medium --language zh --output_format srt

# Output: mandarin.srt
```

## Fase 2: Web App (https://srt-splitter.vercel.app/)

### Step 2.1: Translate Mandarin → Jawa
1. Buka https://srt-splitter.vercel.app/
2. Upload `original.srt`
3. Di panel Translate, pilih source `Chinese` → target `Jawa`
4. Klik Translate
5. Download hasil translate

### Step 2.2: Rapikan tatabahasa Jawa (opsional)
- Pakai script `rapikan-jawa.py` lokal
- Lihat dokumentasi di `scripts/tutor-python-lokal.md`

### Step 2.3: Dubbing Mode
1. Upload SRT Jawa yang sudah diterjemahkan + dirapikan
2. Di panel TTS, pilih mode **🔴 DUBBING**
3. Pilih voice (default: `id-ID-GadisNeural` untuk perempuan, `id-ID-ArdiNeural` untuk laki-laki)
4. Pilih speed:
   - **1.0x Natural** — paling natural, video paling banyak slow-mo (rekomendasi untuk hasil terbaik)
   - **1.25x** — kompromi, kurangi slow-mo
   - **1.5x** — paling sedikit slow-mo, mungkin agak robot
5. Pilih min gap (default 150ms — natural percakapan)
6. Klik **Generate Dubbing**
7. Setelah selesai, klik **Download 3 file (WAV + SRT + JSON)**
8. Akan dapat:
   - `{prefix}-audio-jawa.wav` → rename jadi `audio-jawa.wav`
   - `{prefix}-subs-jawa-new.srt` → rename jadi `subs-jawa-new.srt`
   - `{prefix}-retime-map.json` → rename jadi `retime-map.json`

## Fase 3: SFX Separation (Opsional, untuk preserve backsound)

Pisahkan audio MP4 menjadi vocals (dibuang) + SFX (dipertahankan).

```bash
# Install Demucs (sekali saja)
pip install demucs

# Run separation
python3 scripts/separate-audio-sfx.py \
  --mp4 mandarin.mp4 \
  --output-dir output/

# Output:
# output/vocals-mandarin.wav  (akan dibuang)
# output/sfx-backsound.wav    (akan di-mix dengan audio Jawa)
```

**Estimasi waktu:**
- File 90 menit, MacBook M1/M2 CPU: 10-20 menit
- File 90 menit, GPU NVIDIA: 2-5 menit

**Kapan perlu SFX separation?**
- ✅ MP4 punya backsound/music yang ingin dipertahankan
- ✅ MP4 punya SFX (ledakan, langkah kaki, dll) yang penting untuk scene
- ❌ MP4 hanya dialog tanpa backsound → skip Fase 3, langsung Fase 4

## Fase 4: Retime Video dengan FFmpeg

### Mode A: Basic (tanpa SFX separation)
Audio ori MP4 di-duck (volume turun) saat audio Jawa bicara. Cocok untuk MP4 dengan dialog dominant.

```bash
python3 scripts/retime-video.py \
  --mp4 mandarin.mp4 \
  --srt-mandarin original.srt \
  --srt-jawa subs-jawa-new.srt \
  --audio-jawa audio-jawa.wav \
  --output mp4-jawa.mp4 \
  --sfx-ducking 12
```

**Parameter:**
- `--sfx-ducking 12` — volume SFX turun 12dB saat audio Jawa bicara (default)
- `--no-sfx` — buang audio ori total (hanya audio Jawa)
- `--dry-run` — print command tanpa eksekusi (test dulu)
- `--keep-temp` — keep temp files untuk debugging

### Mode B: Advanced (dengan SFX separation via Demucs)

```bash
python3 scripts/retime-video.py \
  --mp4 mandarin.mp4 \
  --srt-mandarin original.srt \
  --srt-jawa subs-jawa-new.srt \
  --audio-jawa audio-jawa.wav \
  --output mp4-jawa.mp4 \
  --separate-sfx \
  --sfx-ducking 12
```

Script akan auto-run Demucs untuk separate SFX, lalu mix dengan audio Jawa.

### Estimasi waktu Fase 4
- File 90 menit, mode basic: 30-60 menit (ffmpeg render)
- File 90 menit, mode advanced: 60-90 menit (Demucs + ffmpeg)
- CPU: butuh 4-8 GB RAM untuk file besar

## Fase 5: Edit Final di DaVinci Resolve

1. Import `mp4-jawa.mp4` ke DaVinci Resolve
2. Cek hasil:
   - Video slow-mo di cue pendek (wajar, sudah di-retim match audio Jawa)
   - Audio Jawa natural, tidak robot
   - SFX backsound masih ada (jika mode B)
3. Edit final (opsional):
   - Tambah musik latar
   - Color grade
   - Cut scene yang tidak perlu
4. Export final video

## Troubleshooting

### Error: "ffmpeg tidak ditemukan"
Install ffmpeg:
```bash
# Mac
brew install ffmpeg

# Linux
sudo apt install ffmpeg  # Debian/Ubuntu
sudo dnf install ffmpeg   # Fedora

# Windows
# Download dari https://ffmpeg.org/download.html
```

### Error: "Demucs tidak ditemukan"
Install Demucs:
```bash
pip install demucs

# Atau dengan GPU (NVIDIA):
pip install demucs torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121
```

### Demucs running lambat
- Untuk file besar (>90 menit), butuh banyak RAM
- GPU NVIDIA lebih cepat 5-10x dari CPU
- Alternatif: pakai mode basic (tanpa Demucs) jika tidak butuh SFX preserve

### Video slow-mo terlalu janggal
- Naikkan speed di Fase 2 (1.0 → 1.25 atau 1.5) — kurangi slow-mo video
- Trade-off: audio mungkin sedikit robot di cue pendek

### Audio Jawa tidak sync dengan video
- Pastikan SRT Jawa dan audio Jawa dari sesi generate yang sama di web app
- Cek `retime-map.json` — total offset harus wajar (~30% dari durasi SRT asli)

### File MP4 output terlalu besar
- Naikkan CRF: `--crf 28` (lebih kecil, kualitas turun)
- Pakai preset `fast` (lebih cepat, file sedikit lebih besar)

### ffmpeg command error
- Pakai `--dry-run` untuk lihat command tanpa eksekusi
- Cek log stderr di terminal

## Contoh Workflow Lengkap (3 jam MP4)

```bash
# Persiapan folder
mkdir dubbing && cd dubbing

# Copy file sumber
cp ~/Downloads/mandarin.mp4 .
cp ~/Downloads/original.srt .

# Fase 2 (di web app):
# Upload original.srt → Translate ke Jawa → Download 3 file
# Rename:
mv *-audio-jawa.wav audio-jawa.wav
mv *-subs-jawa-new.srt subs-jawa-new.srt
mv *-retime-map.json retime-map.json

# Fase 3 (opsional): SFX separation
python3 scripts/separate-audio-sfx.py \
  --mp4 mandarin.mp4 \
  --output-dir output/

# Fase 4: Retime video
python3 scripts/retime-video.py \
  --mp4 mandarin.mp4 \
  --srt-mandarin original.srt \
  --srt-jawa subs-jawa-new.srt \
  --audio-jawa audio-jawa.wav \
  --output mp4-jawa.mp4 \
  --separate-sfx \
  --sfx-ducking 12

# Fase 5 (opsional): Edit di DaVinci Resolve
# Import mp4-jawa.mp4 → Edit → Export
```

## FAQ

**Q: Bisakah saya skip Fase 3 (SFX separation)?**
A: Ya. Kalau MP4 hanya dialog tanpa backsound penting, langsung Fase 4 dengan mode basic. Audio ori akan di-duck (volume turun) saat audio Jawa bicara.

**Q: Bisakah saya pakai audio Jawa tanpa video retimed?**
A: Ya. Download audio-jawa.wav saja, pakai sebagai dub track terpisah. Tapi video tidak akan sync dengan audio Jawa.

**Q: Berapa lama total workflow untuk 3 jam MP4?**
A:
- Fase 1: 5 menit (whisper generate SRT)
- Fase 2: 15-30 menit (translate + rapikan + dubbing mode)
- Fase 3: 10-20 menit (Demucs di CPU) — opsional
- Fase 4: 30-90 menit (ffmpeg + Demucs ulang kalau mode B)
- Fase 5: 30-60 menit (edit manual di DaVinci)
- **Total: 90-180 menit untuk 3 jam MP4**

**Q: Bisakah workflow ini untuk bahasa lain selain Jawa?**
A: Ya. Translate ke bahasa apapun (Sunda, Batak, Bali, dll) — Edge TTS support 70+ bahasa.

**Q: Apakah video slow-mo terlihat janggal?**
A: Untuk cue pendek (1-2 kata), video akan slow-mo 2-3x. Viewer mungkin sadar. Untuk hasil terbaik, pakai speed 1.25x atau 1.5x (kompromi natural vs slow-mo).
