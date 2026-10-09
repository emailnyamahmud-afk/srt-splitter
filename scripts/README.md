# Scripts — SRT Splitter + Dubbing

Script Python untuk workflow dubbing Mandarin → Jawa + edit kamus Jawa.

**R-22 compliance**: SEMUA parser/scraper/raw script DIHAPUS. Hanya workflow script aktif.
Raw files = sampah parsing AI tolol. Yang TINGGAL: kamus-jawa-draft.json (NETRAL).

## ⭐ Workflow Utama (Dubbing 4 Fase)

```bash
# Setup (sekali saja)
brew install ffmpeg
pip3 install demucs questionary numpy

# Fase 1: Download dari YouTube
python3 scripts/yt-dlp-tui.py
# → mp4-ori.mp4 + audio.wav

# Fase 2: SFX separation (Demucs)
python3 scripts/demucs-tui.py
# → no_vocals.mp3 (MP3 320 kbps)

# Fase 3a: Web app Mode ON (Indonesia) — SUDAH JALAN
# https://srt-splitter.vercel.app/
# → audio-id-dub.wav

# Fase 3b: Web app SRT editor (Jawa) — NUNGGU CODE FIX
# → audio-jw-dub.wav

# Fase 4: Mix (~7 detik)
python3 scripts/mix-tui.py
# → mp4-{lang}-final.mp4
```

Lihat [`tutor-mode-on-workflow.md`](tutor-mode-on-workflow.md) + [`tutor-demucs-setup.md`](tutor-demucs-setup.md) untuk detail.

## Quick Index

### Workflow Scripts

| Script | Untuk Apa | Status |
|---|---|---|
| **`yt-dlp-tui.py`** ⭐ | TUI Download YouTube (pilih resolusi 480/720/1080) + audio terpisah | ✅ Utama |
| **`demucs-tui.py`** ⭐ | TUI Demucs SFX separation → no_vocals.mp3 (MP3 320, MPS) | ✅ Utama |
| **`mix-tui.py`** ⭐ | TUI Mix MP4 + no_vocals + audio_dub (ducking sidechain) | ✅ Utama |
| **`srt-frequency-analyzer.py`** ⭐ | Analisis SRT → top 100 kata tak dikenal (pakai Supabase) | ✅ Utama |

### Kamus Workflow Scripts

| Script | Untuk Apa | Status |
|---|---|---|
| **`kamus-tui.py`** ⭐ | TUI edit kamus Jawa v2.6 (Phase 1-6 refactor, R-21 word field) | ✅ Utama |
| **`upload-supabase.py`** | Upload entries approved ke Supabase (user-triggered only, R-12) | ✅ Utama |

### SQL Migrations (Supabase)

| File | Untuk Apa |
|---|---|
| `supabase-migration-v2.sql` | srt_projects + srt_cues (Editor SRT Jawa project-based) |
| `supabase-migration-v3.sql` | kamus krama_inggil + register |

### Dokumentasi

- `tutor-mode-on-workflow.md` — panduan workflow Mode ON
- `tutor-demucs-setup.md` — setup Demucs M1 16GB
- `tutor-python-lokal.md` — setup Python lokal
- `README.md` — file ini

---

## Kamus Jawa Workflow (v2.6, post-R-22)

```bash
# Download (sekali saja) — R-22: hanya kamus-draft.json, raw dihapus
curl -L -o kamus-jawa-draft.json \
  "https://raw.githubusercontent.com/emailnyamahmud-afk/srt-splitter/main/public/kamus-jawa-draft.json?v=26"
curl -L -o kamus-tui.py \
  "https://raw.githubusercontent.com/emailnyamahmud-afk/srt-splitter/main/scripts/kamus-tui.py?v=8"
curl -L -o upload-supabase.py \
  "https://raw.githubusercontent.com/emailnyamahmud-afk/srt-splitter/main/scripts/upload-supabase.py?v=2"

# Setup .env (sekali saja via TUI menu "🔑 Set Supabase .env")
python3 kamus-tui.py

# Statistik startup: Total | NETRAL | 3-field ready | Status ready
# Menu utama → "⚠ Filter: NETRAL" → browse 39.216 entries word-only
# Edit entry → isi ngoko/krama/arti (2 dari 3 → paired) → save
# Setelah 3-field lengkap → status 'ready' → siap upload Supabase

# Menu "☁ Upload ke Supabase" → konfirmasi 'y' eksplisit → upload batch 500
```

### Aturan kamus (R-12 sampai R-22)

- **R-12**: User wajib validasi 1-1 sebelum upload Supabase (status='ready')
- **R-16**: Raw files DIHAPUS dari repo (R-22 override)
- **R-16a**: Ejaan Jawa (panduan teknis, AI tidak audit ejaan dari raw)
- **R-17**: krama_inggil masuk field krama (sinonim comma)
- **R-18**: JANGAN HAPUS entry kamus (kosong/aksara/keterangan-only tetap disimpan)
- **R-19**: Parser AI tolol, raw = sampah
- **R-20**: kamus-draft.json = rujukan tunggal, raw = DIHAPUS
- **R-21**: field 'word' = netral, belum terdefinisi register
- **R-22**: GIGO — AI tidak merujuk raw untuk audit/fix, bantu workflow saja

### User fallback (kata belum dikenali)

Per R-22: cari manual di kamus resmi Kemendikbud:
- https://kesakata.kemdikbud.go.id
- https://bahasa.kemdikbud.go.id
- Wiktionary online langsung (jangan batch scrape)

---

## Multi-bahasa Output (rencana masa depan)

Setelah audio-jw-dub.wav ready:

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
```

### `mix-tui.py` ⭐ — Mix TUI

```bash
python3 scripts/mix-tui.py
# 6 step: MP4 ori, no_vocals (mp3/wav/flac), audio dub, ducking, output, konfirmasi
# Output: mp4-id-final.mp4 (video stream copy + SFX + dub, 0 DTS warnings)
```

### `kamus-tui.py` ⭐ — Kamus Jawa Editor TUI v2.6

```bash
python3 scripts/kamus-tui.py
# Phase 1-6 refactor: helper _search_entries, _entry_label, filter NETRAL,
# merge_2_entries terpisah, upload via upload-supabase.py, textwrap
# Statistik startup: Total + NETRAL + 3-field ready + Status ready
# Menu: Search, Browse READY/DRAFT, Filter NETRAL/3-field/NGOKO+KRAMA/etc,
#        Merge 2 entries, Mark READY bulk, Set Supabase .env, Upload
```

### `upload-supabase.py` ⭐ — Upload ke Supabase

```bash
python3 upload-supabase.py
# Dipanggil dari kamus-tui.py (wrapper) atau standalone
# Filter: HANYA entries dengan status='ready' (R-12: user explicit approve via TUI)
# Konfirmasi: user harus ketik 'y' eksplisit sebelum POST
# Batch POST 500 entries per request ke Supabase REST API
```

### `srt-frequency-analyzer.py` ⭐ — Frequency Analyzer

```bash
python3 srt-frequency-analyzer.py ~/Dubbing/S1-jw.srt
# Output: ~/Dubbing/srt-freq-report.txt (top 100 kata tak dikenal + frequency)
# Pakai Supabase DB sebagai ground of truth (bukan JSON lokal)
# User copy list → paste di kamus-tui.py → search + add entry
```

---

## Catatan

- **Workflow utama**: yt-dlp (Fase 1) → demucs-tui.py (Fase 2) → web Mode ON (Fase 3a) → mix-tui.py (Fase 4)
- **Multi-bahasa**: Mode ON untuk ID (sudah jalan), SRT editor untuk Jawa (nunggu code fix + kamus)
- **Mode manual**: DaVinci Resolve (tarik file ke timeline, edit sendiri)
- **Audio utuh 100%** — tidak ada potongan di TTS mode ON + Smart Fit (no truncate)
- **Kamus Jawa** — v2.6 (post-R-22 raw dihapus), 45.021 entries, 5.803 paired + 39.216 NETRAL
- R-22: SEMUA raw + parser script DIHAPUS. Hanya workflow script aktif.
