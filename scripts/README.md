# Scripts — SRT Splitter + Dubbing Jawa

Script Python untuk memproses SRT, generate audio, dan mix dub untuk dubbing Mandarin → Jawa/Indonesia.

## ⭐ Workflow Utama (Mode ON + Smart Fit + mix-audio-dub.py)

Strategi baru (5 Okt 2026): Video = ground truth, audio dub fit ke SRT ori dengan Smart Fit, mix dengan audio ori MP4 (SFX preserve + ducking).

Lihat [`tutor-mode-on-workflow.md`](tutor-mode-on-workflow.md) untuk panduan lengkap.

## Quick Index

| Script | Untuk Apa | Kapan Dipakai |
|---|---|---|
| **`mix-audio-dub.py`** ⭐ | **Mix audio ori MP4 + audio dub WAV (SFX preserve + ducking)** | **Fase 2: workflow utama (mode ON + Smart Fit)** |
| `rapikan-jawa.py` | Rapikan ejaan Jawa di 1 file SRT | Setelah translate Mandarin → Jawa |
| `rapikan-jawa-semua-season.py` | Rapikan semua season S1-S6 sekaligus | Batch processing multiple SRT |
| `tambah-krama.py` | Tambah sentuhan krama inggil | Untuk dialog formal (kepada atasan, tamu) |
| `split_srt.py` | Split SRT by durasi | Sebelum upload ke web app kalau file besar |
| `srt-to-audio.py` | Generate audio dari SRT (Edge TTS) | Alternatif Python lokal (tanpa browser) |
| `retime-video.py` | Retime MP4 Mandarin → SRT Jawa (deprecated) | Backup untuk Dubbing Mode (20x test gagal) |
| `separate-audio-sfx.py` | Pisahkan vocals + SFX dari MP4 (Demucs) | Opsional, kalau butuh SFX bersih |
| `analyze-srt-density.py` | Analisis distribusi cue + robot ratio | Debug / optimasi TTS speed |
| `build_source_zip.py` | Build source code ZIP untuk download web | Maintainer only |

---

## ⭐ Workflow Utama (Mode ON + Smart Fit + mix-audio-dub.py)

```bash
# Setup (sekali saja)
brew install ffmpeg

# Fase 1: Web app (mode ON + Smart Fit)
# Upload SRT ori → mode ON → Smart Fit (default) → Generate → Download audio dub

# Fase 2: Python mix (~10 detik)
python3 scripts/mix-audio-dub.py \
  --mp4 mp4-ori-test-7min.mp4 \
  --audio-dub audio-id-dub.wav \
  --output mp4-id-final.mp4 \
  --ducking 12
```

Lihat [`tutor-mode-on-workflow.md`](tutor-mode-on-workflow.md) untuk detail.

---

## Workflow Lama (Dubbing Mode + render video, DEPRECATED)

Strategi lama: Dubbing Mode (audio natural, SRT baru) + retime-video.py (render video).
20x test gagal (stop-motion, DTS warnings, drift). Tetap di repo sebagai backup.

Lihat [`tutor-dubbing-workflow.md`](tutor-dubbing-workflow.md) untuk panduan lama.

---

## Detail Per Script

### 1. `mix-audio-dub.py` ⭐ — Mix audio dub + SFX preserve (Fase 2 workflow utama)

```bash
# Mode default (SFX preserve + ducking 12dB)
python3 scripts/mix-audio-dub.py \
  --mp4 mp4-ori-test-7min.mp4 \
  --audio-dub audio-id-dub.wav \
  --output mp4-id-final.mp4 \
  --ducking 12

# Mode no-ducking (SFX + dub sama keras)
python3 scripts/mix-audio-dub.py \
  --mp4 mp4-ori-test-7min.mp4 \
  --audio-dub audio-id-dub.wav \
  --output mp4-id-final.mp4 \
  --no-ducking

# Mode sfx-only (buang audio ori, hanya dub)
python3 scripts/mix-audio-dub.py \
  --mp4 mp4-ori-test-7min.mp4 \
  --audio-dub audio-id-dub.wav \
  --output mp4-id-final.mp4 \
  --sfx-only
```

Output: MP4 dengan video ori (100% sync, stream copy) + audio mix (SFX + dub).
Estimasi: ~10 detik untuk video 2.5 jam.

### 2. `rapikan-jawa.py` — Rapikan 1 file SRT

```bash
python3 scripts/rapikan-jawa.py
# Default: input upload/Season-2-jw.srt → output download/Season-2-jw-fixed.srt
```

### 3. `split_srt.py` — Split SRT by durasi

```bash
python3 scripts/split_srt.py input.srt output_dir PREFIX 30
# Split setiap 30 menit, output: PREFIX-01.srt, PREFIX-02.srt, dst.
```

### 4. `srt-to-audio.py` — Generate audio dari SRT (Python lokal)

```bash
python3 scripts/srt-to-audio.py subs.srt --on --voice id-ID-GadisNeural
# Output: audio.wav

# Mode OFF (natural sequential)
python3 scripts/srt-to-audio.py subs.srt --off --voice id-ID-ArdiNeural --speed 1.25
```

### 5. `retime-video.py` (DEPRECATED) — Retime MP4 ke SRT Jawa

Strategi lama, 20x test gagal. Tetap di repo sebagai backup.

```bash
python3 scripts/retime-video.py \
  --mp4 mp4-ori-test-5min.mp4 \
  --srt-original srt-id-original.srt \
  --srt-dub srt-id-dub.srt \
  --audio-dub audio-id-dub.wav \
  --output mp4-id-final.mp4 \
  --encoder h264_videotoolbox --workers 4
```

### 6. `separate-audio-sfx.py` — SFX separation dengan Demucs (opsional)

```bash
pip install demucs
python3 scripts/separate-audio-sfx.py \
  --mp4 mandarin.mp4 \
  --output-dir output/
```

---

## Catatan

- **Workflow utama**: Mode ON + Smart Fit (web) + mix-audio-dub.py (Python)
- **Workflow lama** (deprecated): Dubbing Mode + retime-video.py (20x test gagal)
- **Timestamps SRT TIDAK diubah** oleh `rapikan-jawa.py`, `tambah-krama.py`
- **Audio utuh 100%** — tidak ada potongan di TTS mode ON + Smart Fit (no truncate)
- Script aman dijalankan ulang (idempotent)
- File di folder `download/` dan `upload/` TIDAK di-commit ke GitHub (lihat `.gitignore`)
