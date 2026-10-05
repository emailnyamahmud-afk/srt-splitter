# Scripts — SRT Splitter + Dubbing

Script Python untuk memproses SRT, generate audio, dan mix dub untuk dubbing Mandarin → Jawa/Indonesia.

## ⭐ Workflow Utama (Mode ON + Smart Fit + Demucs + Mix)

Strategi (5 Okt 2026): Video = ground truth, audio dub fit ke SRT ori dengan Smart Fit, SFX bersih dari Demucs, mix dengan ducking.

Lihat [`tutor-mode-on-workflow.md`](tutor-mode-on-workflow.md) + [`tutor-demucs-setup.md`](tutor-demucs-setup.md) untuk panduan lengkap.

## Quick Index

| Script | Untuk Apa | Status |
|---|---|---|
| **`demucs-tui.py`** ⭐ | TUI Demucs SFX separation (MPS acceleration) | ✅ Utama |
| **`mix-tui.py`** ⭐ | TUI Mix SFX + audio dub + MP4 (ducking sidechain) | ✅ Utama |
| `rapikan-jawa.py` | Rapikan ejaan Jawa di 1 file SRT | ✅ Utility |
| `rapikan-jawa-semua-season.py` | Rapikan semua season S1-S6 sekaligus | ✅ Utility |
| `tambah-krama.py` | Tambah sentuhan krama inggil | ✅ Utility |
| `split_srt.py` | Split SRT by durasi | ✅ Utility |
| `srt-to-audio.py` | Generate audio dari SRT (Edge TTS, alternatif lokal) | ✅ Utility |
| `analyze-srt-density.py` | Analisis distribusi cue + robot ratio | ✅ Debug |
| `dubbing-tui.py` | TUI untuk Dubbing Mode (deprecated, backup) | ⚠️ Backup |
| `retime-video.py` | Retime MP4 (deprecated, 20x test gagal, backup) | ⚠️ Backup |
| `build_source_zip.py` | Build source ZIP untuk download web | 🔧 Maintainer |

---

## ⭐ Workflow Utama (3 Fase)

```bash
# Setup (sekali saja)
brew install ffmpeg
pip3 install demucs questionary numpy

# Fase 0: SFX separation (Demucs, ~1 menit untuk 7.5 menit MPS)
python3 scripts/demucs-tui.py
# → output/htdemucs/{namafile}/no_vocals.wav (SFX bersih)

# Fase 1: Web app (mode ON + Smart Fit + pitch)
# https://srt-splitter.vercel.app/
# Upload SRT ori → mode ON → Smart Fit (cap 2.0x) → pitch (-15Hz laki)
# → audio-id-dub.wav (dialog, 100% sync)

# Fase 2: Mix (~7 detik)
python3 scripts/mix-tui.py
# → mp4-id-final.mp4 (video ori + SFX bersih + dialog dub, 0 DTS warnings)
```

Lihat [`tutor-mode-on-workflow.md`](tutor-mode-on-workflow.md) + [`tutor-demucs-setup.md`](tutor-demucs-setup.md) untuk detail.

---

## Mode Manual (DaVinci Resolve)

Kalau mau edit manual (laki + perempuan, cut scene, dll):
1. Buka DaVinci Resolve
2. Tarik `mp4-ori.mp4` ke timeline (video + audio ori)
3. Tarik `no_vocals.wav` ke timeline (SFX bersih dari Demucs)
4. Tarik `audio-id-dub.wav` ke timeline (dialog dub dari web app)
5. Edit manual: mana suara laki, mana perempuan, ducking SFX, dll

---

## Deprecated (Backup, tetap di repo)

- `retime-video.py` — 20x test gagal (stop-motion), tetap sebagai backup untuk Dubbing Mode
- `dubbing-tui.py` — TUI untuk retime-video.py, deprecated

---

## Detail Per Script

### `demucs-tui.py` ⭐ — SFX separation TUI

```bash
source venv/bin/activate  # aktifkan venv dulu
python3 scripts/demucs-tui.py
# 6 step: file, output, model, mode, device (mps), konfirmasi
# Output: no_vocals.wav (SFX bersih) + vocals.wav (buang)
```

Lihat [`tutor-demucs-setup.md`](tutor-demucs-setup.md) untuk setup M1 16GB.

### `mix-tui.py` ⭐ — Mix TUI

```bash
python3 scripts/mix-tui.py
# 6 step: MP4 ori, audio dub, SFX source, ducking, output, konfirmasi
# Output: mp4-id-final.mp4 (video stream copy + SFX + dub, 0 DTS warnings)
```

### `rapikan-jawa.py` — Rapikan SRT Jawa

```bash
python3 scripts/rapikan-jawa.py
# Default: input upload/Season-2-jw.srt → output download/Season-2-jw-fixed.srt
```

### `split_srt.py` — Split SRT by durasi

```bash
python3 scripts/split_srt.py input.srt output_dir PREFIX 30
# Split setiap 30 menit, output: PREFIX-01.srt, PREFIX-02.srt, dst.
```

### `srt-to-audio.py` — Generate audio dari SRT (Python lokal)

```bash
python3 scripts/srt-to-audio.py subs.srt --on --voice id-ID-GadisNeural
```

### `retime-video.py` (deprecated) — Retime MP4

Backup, 20x test gagal. Untuk Dubbing Mode kalau nanti nemu jalan keluar.

---

## Catatan

- **Workflow utama**: demucs-tui.py (Fase 0) + web mode ON (Fase 1) + mix-tui.py (Fase 2)
- **Mode manual**: DaVinci Resolve (tarik file ke timeline, edit sendiri)
- **Audio utuh 100%** — tidak ada potongan di TTS mode ON + Smart Fit (no truncate)
- Script aman dijalankan ulang (idempotent)
