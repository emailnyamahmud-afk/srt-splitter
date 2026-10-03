# Scripts — SRT Splitter + Dubbing Jawa

Script Python untuk memproses SRT, generate audio, dan retim video untuk dubbing Mandarin → Jawa.

## Quick Index

| Script | Untuk Apa | Kapan Dipakai |
|---|---|---|
| `rapikan-jawa.py` | Rapikan ejaan Jawa di 1 file SRT | Setelah translate Mandarin → Jawa |
| `rapikan-jawa-semua-season.py` | Rapikan semua season S1-S6 sekaligus | Batch processing multiple SRT |
| `tambah-krama.py` | Tambah sentuhan krama inggil | Untuk dialog formal (kepada atasan, tamu) |
| `split_srt.py` | Split SRT by durasi | Sebelum upload ke web app kalau file besar |
| `srt-to-audio.py` | Generate audio dari SRT (Edge TTS) | Alternatif Python lokal (tanpa browser) |
| `retime-video.py` | Retime MP4 Mandarin → SRT Jawa | **Fase 4: dubbing workflow** |
| `separate-audio-sfx.py` | Pisahkan vocals + SFX dari MP4 (Demucs) | **Fase 3 (opsional): preserve backsound** |
| `analyze-srt-density.py` | Analisis distribusi cue + robot ratio | Debug / optimasi TTS speed |
| `build_source_zip.py` | Build source code ZIP untuk download web | Maintainer only |

---

## Workflow Lengkap Dubbing

Lihat [`tutor-dubbing-workflow.md`](tutor-dubbing-workflow.md) untuk panduan 5 fase lengkap.

Quick start:

```bash
# Setup (sekali saja)
brew install ffmpeg
pip3 install edge-tts numpy demucs  # demucs opsional

# Fase 4: Retime video (mode basic, tanpa SFX separation)
python3 scripts/retime-video.py \
  --mp4 mandarin.mp4 \
  --srt-mandarin original.srt \
  --srt-jawa subs-jawa-new.srt \
  --audio-jawa audio-jawa.wav \
  --output mp4-jawa.mp4

# Fase 4: Mode advanced (dengan SFX separation)
python3 scripts/retime-video.py \
  --mp4 mandarin.mp4 \
  --srt-mandarin original.srt \
  --srt-jawa subs-jawa-new.srt \
  --audio-jawa audio-jawa.wav \
  --output mp4-jawa.mp4 \
  --separate-sfx \
  --sfx-ducking 12
```

---

## Detail Per Script

### 1. `rapikan-jawa.py` — Rapikan 1 file SRT

```bash
python3 scripts/rapikan-jawa.py
# Default: input upload/Season-2-jw.srt → output download/Season-2-jw-fixed.srt
```

Ubah `input_file` dan `output_file` di dalam script sesuai kebutuhan.

### 2. `rapikan-jawa-semua-season.py` — Rapikan batch S1-S6

```bash
python3 scripts/rapikan-jawa-semua-season.py
# Input: upload/Season-*-jw.srt
# Output: download/Season-*-jw-fixed.srt
```

Perbaikan yang dilakukan:
- Hapus "(or)" dan duplikat di Season 1
- Ejaan aksén: `kowe` → `kowé`, `dheweke` → `dhèwèké`, `kabeh` → `kabèh`
- Kosakata: `keluarga` → `kulawarga`, `rumah tangga` → `omah tangga`, `bandit` → `begal`
- Ejaan: `pengin` → `péngin`, `sedhela` → `sedhéla`, `kene` → `kéné`

### 3. `tambah-krama.py` — Tambah krama inggil

```bash
python3 scripts/tambah-krama.py
# Process semua Season 1-6 yang sudah dirapikan
```

Perbaikan yang dilakukan:
- `Kapten, aku` → `Kapten, kula`
- `Pak, aku` → `Pak, kula`
- `Aku mohon` → `Kula nyuwun`
- `mangga, gusti` → `Mangga, Gusti`
- `inggih` di awal → `Inggih`
- `mangga` di awal → `Mangga`

### 4. `split_srt.py` — Split SRT by durasi

```bash
python3 scripts/split_srt.py input.srt output_dir PREFIX 30
# Split setiap 30 menit, output: PREFIX-01.srt, PREFIX-02.srt, dst.
```

### 5. `srt-to-audio.py` — Generate audio dari SRT (Python lokal)

Alternatif Python untuk generate audio tanpa browser. Cocok untuk batch processing atau kalau web app lambat.

```bash
python3 scripts/srt-to-audio.py subs.srt --on --voice id-ID-GadisNeural
# Output: audio.wav

# Mode OFF (natural sequential)
python3 scripts/srt-to-audio.py subs.srt --off --voice id-ID-ArdiNeural --speed 1.25
```

Lihat [`tutor-python-lokal.md`](tutor-python-lokal.md) untuk detail setup.

### 6. `retime-video.py` — Retime MP4 ke SRT Jawa (Fase 4)

Script utama untuk dubbing. Strategi: **SRT Jawa = ground truth**, MP4 di-retim supaya match.

```bash
# Mode basic (audio ori di-duck)
python3 scripts/retime-video.py \
  --mp4 mandarin.mp4 \
  --srt-mandarin original.srt \
  --srt-jawa subs-jawa-new.srt \
  --audio-jawa audio-jawa.wav \
  --output mp4-jawa.mp4 \
  --sfx-ducking 12  # SFX volume turun 12dB saat audio Jawa bicara

# Mode tanpa SFX (audio Jawa only)
python3 scripts/retime-video.py \
  --mp4 mandarin.mp4 \
  --srt-mandarin original.srt \
  --srt-jawa subs-jawa-new.srt \
  --audio-jawa audio-jawa.wav \
  --output mp4-jawa.mp4 \
  --no-sfx

# Dry-run (cek command tanpa eksekusi)
python3 scripts/retime-video.py ... --dry-run
```

Lihat [`tutor-dubbing-workflow.md`](tutor-dubbing-workflow.md) untuk detail.

### 7. `separate-audio-sfx.py` — SFX separation dengan Demucs (Fase 3 opsional)

Pisahkan audio MP4 menjadi vocals (dibuang) + SFX/backsound (dipertahankan).

```bash
# Install Demucs dulu
pip install demucs

# Run separation
python3 scripts/separate-audio-sfx.py \
  --mp4 mandarin.mp4 \
  --output-dir output/

# Output:
# output/vocals-mandarin.wav  (akan dibuang)
# output/sfx-backsound.wav    (akan di-mix dengan audio Jawa)
```

Estimasi waktu:
- File 90 menit, MacBook M1/M2 CPU: 10-20 menit
- File 90 menit, GPU NVIDIA: 2-5 menit

### 8. `analyze-srt-density.py` — Analisis distribusi cue

Untuk debug dan optimasi. Hitung berapa cue yang akan jadi robot dengan TTS natural.

```bash
python3 scripts/analyze-srt-density.py
# Default: analisis Season-1 dan Season-6 dari /home/z/my-project/download/
```

Output: distribusi cue duration, estimasi ratio speed-up, % cue yang akan robot.

### 9. `build_source_zip.py` — Build source zip (maintainer)

```bash
python3 scripts/build_source_zip.py
# Output: download/srt-splitter-source.zip
```

---

## Catatan

- **Timestamps SRT TIDAK diubah** oleh `rapikan-jawa.py`, `tambah-krama.py` — hanya text yang diperbaiki
- **Audio utuh 100%** — tidak ada potongan di TTS
- Script aman dijalankan ulang (idempotent)
- File di folder `download/` dan `upload/` TIDAK di-commit ke GitHub (lihat `.gitignore`)
