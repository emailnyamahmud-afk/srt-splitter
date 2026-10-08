# Scripts — SRT Splitter + Dubbing

Script Python untuk memproses SRT, generate audio, dan mix dub untuk dubbing Mandarin → Jawa/Indonesia.

## ⭐ Workflow Utama (yt-dlp → Demucs → Web → Mix)

Strategi (8 Okt 2026): Sumber terpisah sejak fase yt-dlp, MP3 320 kbps output Demucs (hemat ~10x storage), mix SFX + dub dengan ducking.

Lihat [`tutor-mode-on-workflow.md`](tutor-mode-on-workflow.md) + [`tutor-demucs-setup.md`](tutor-demucs-setup.md) untuk panduan lengkap.

## Quick Index

| Script | Untuk Apa | Status |
|---|---|---|
| **`yt-dlp-tui.py`** ⭐ | TUI Download YouTube (pilih resolusi 480/720/1080) + audio terpisah | ✅ Utama |
| **`demucs-tui.py`** ⭐ | TUI Demucs SFX separation → no_vocals.mp3 (MP3 320, MPS acceleration) | ✅ Utama |
| **`mix-tui.py`** ⭐ | TUI Mix MP4 + no_vocals + audio_dub (ducking sidechain) | ✅ Utama |
| **`kamus-tui.py`** ⭐ | TUI edit kamus Jawa v2 — menu pre-built, .env support, upload Supabase | ✅ Utama |
| **`srt-frequency-analyzer.py`** ⭐ | Analisis SRT → top 100 kata tak dikenal (pakai Supabase sebagai ground of truth) | ✅ Utama |
| `rapikan-jawa.py` | Rapikan ejaan Jawa di 1 file SRT | ✅ Utility |
| `split_srt.py` | Split SRT by durasi | ✅ Utility |
| `srt-to-audio.py` | Generate audio dari SRT (Edge TTS, alternatif lokal) | ✅ Utility |
| `parse-wiktionary-jv.py` | Parser v5: Wiktionary XML → kamus JSON (register tag + krama_inggil + xref) | ✅ Utility |
| `dubbing-tui.py` | TUI untuk Dubbing Mode (deprecated, backup) | ⚠️ Backup |
| `retime-video.py` | Retime MP4 (deprecated, 20x test gagal, backup) | ⚠️ Backup |

---

## ⭐ Workflow Utama (3 Fase, sumber terpisah)

```bash
# Setup (sekali saja)
brew install ffmpeg
pip3 install demucs questionary numpy

# Fase 1: Download dari YouTube (pilih resolusi 480/720/1080)
python3 scripts/yt-dlp-tui.py
# → mp4-ori.mp4 (video) + audio.wav (terpisah, untuk Demucs)

# Fase 2: SFX separation (Demucs, output MP3 320 kbps)
python3 scripts/demucs-tui.py
# → output/htdemucs/{namafile}/no_vocals.mp3 (SFX bersih, ~140 MB per 2 jam)
#   (vocals.wav auto-dihapus — tidak dipakai untuk dubbing)

# Fase 3a: Web app — Mode ON (Bahasa Indonesia, cara cepat)
# https://srt-splitter.vercel.app/
# Upload SRT ori → mode ON → Smart Fit (cap 2.0x) → pitch (-15Hz laki)
# Default voice: Dimas (laki) untuk semua cue
# → audio-id-dub.wav (dialog, 100% sync) — SUDAH JALAN

# Fase 3b: Web app — SRT editor (Bahasa Jawa, per cue)
# + Project Baru → upload SRT ID + SRT Jawa → simpan ke Supabase
# Edit cue (text/voice/ngoko/krama) → Preview per cue → Generate Full
# TODO: default voice Dimas otomatis untuk semua cue (sekarang klik manual)
#       Siti (perempuan) tetap manual via klik
# → audio-jw-dub.wav — code perlu dibereskan (web app side)
# Kamus Jawa di Supabase (progressif, 50 entries/minggu)

# Fase 4: Mix (~7 detik)
python3 scripts/mix-tui.py
# → mp4-id-final.mp4 (video ori + SFX bersih + dialog dub, 0 DTS warnings)
# Pilih: MP4 ori → no_vocals.mp3 → audio-id-dub.wav → ducking → output
```

Lihat [`tutor-mode-on-workflow.md`](tutor-mode-on-workflow.md) + [`tutor-demucs-setup.md`](tutor-demucs-setup.md) untuk detail.

---

## Multi-bahasa Output (rencana masa depan)

Setelah audio-jw-dub.wav ready (nunggu SRT editor fix + kamus Supabase lengkap):

| Opsi | Bentuk | Cocok untuk |
|---|---|---|
| **A. Multi-track MP4** | 1 file, switch audio di player (DVD-style) | Arsip & VLC playback |
| **B. File terpisah** | 2 MP4 (mp4-id-final + mp4-jw-final) | Upload TikTok/IG per bahasa |
| **C. Hybrid** | 1 MP4 default ID + sidecar wav Jawa | Bandwidth efficient |

Belum diimplementasi di mix-tui.py (single-bahasa dulu sampai Jawa ready).

---

## Mode Manual (DaVinci Resolve)

Kalau mau edit manual (laki + perempuan, cut scene, dll):
1. Buka DaVinci Resolve
2. Tarik `mp4-ori.mp4` ke timeline (video + audio ori)
3. Tarik `no_vocals.mp3` ke timeline (SFX bersih dari Demucs)
4. Tarik `audio-id-dub.wav` ke timeline (dialog dub dari web app)
5. Edit manual: mana suara laki (Dimas), mana perempuan (Siti), ducking SFX, dll

---

## Deprecated (Backup, tetap di repo)

- `retime-video.py` — 20x test gagal (stop-motion), tetap sebagai backup untuk Dubbing Mode
- `dubbing-tui.py` — TUI untuk retime-video.py, deprecated

---

## Detail Per Script

### `yt-dlp-tui.py` ⭐ — Download TUI

```bash
python3 scripts/yt-dlp-tui.py
# Pilih: URL YouTube → resolusi (480/720/1080) → format H.264 + audio terpisah
# Output: mp4-ori.mp4 (video) + audio.wav (untuk Demucs)
```

### `demucs-tui.py` ⭐ — SFX separation TUI

```bash
source venv/bin/activate  # aktifkan venv dulu
python3 scripts/demucs-tui.py
# 6 step: file, output, model, mode, device (mps), konfirmasi
# Output: no_vocals.mp3 (SFX bersih, MP3 320 kbps, ~140 MB per 2 jam)
#         (vocals.wav + vocals.mp3 auto-dihapus — tidak dipakai untuk dubbing)
```

Lihat [`tutor-demucs-setup.md`](tutor-demucs-setup.md) untuk setup M1 16GB.

**Kenapa MP3 320 bukan WAV?**
- WAV 16-bit stereo 44.1kHz untuk audio 2 jam ≈ 1.3 GB
- MP3 320 kbps untuk audio 2 jam ≈ 140 MB (90% lebih kecil)
- Source biasanya sudah lossy (Opus/MP3 dari yt-dlp) → MP3 320 cukup
- SFX = musik/efek/ambience (bukan dialog) → ear tidak sensitif seperti vocal

### `mix-tui.py` ⭐ — Mix TUI

```bash
python3 scripts/mix-tui.py
# 6 step: MP4 ori, no_vocals (mp3/wav/flac), audio dub, ducking, output, konfirmasi
# Output: mp4-id-final.mp4 (video stream copy + SFX + dub, 0 DTS warnings)
```

### `kamus-tui.py` ⭐ — Kamus Jawa Editor TUI

```bash
python3 scripts/kamus-tui.py
# Browse → pilih entry → isi krama + arti (status jadi 'ready')
# Menu "☁ Upload ke Supabase" — hanya yang ngoko+krama+arti lengkap
```

### `srt-frequency-analyzer.py` ⭐ — Frequency Analyzer

```bash
python3 scripts/srt-frequency-analyzer.py ~/Dubbing/S1-jw.srt
# Output: ~/Dubbing/srt-freq-report.txt (top 100 kata tak dikenal + frequency)
# User copy list → paste di kamus-tui.py → search + add entry
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

- **Workflow utama**: yt-dlp (Fase 1) → demucs-tui.py (Fase 2) → web Mode ON (Fase 3a) → mix-tui.py (Fase 4)
- **Multi-bahasa**: Mode ON untuk ID (sudah jalan), SRT editor untuk Jawa (nunggu code fix + kamus)
- **Mode manual**: DaVinci Resolve (tarik file ke timeline, edit sendiri)
- **Audio utuh 100%** — tidak ada potongan di TTS mode ON + Smart Fit (no truncate)
- Script aman dijalankan ulang (idempotent)
