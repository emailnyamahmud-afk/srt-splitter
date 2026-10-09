# Scripts — SRT Splitter + Dubbing

Script Python untuk memproses SRT, generate audio, mix dub, dan **edit kamus Jawa** untuk dubbing Mandarin → Jawa/Indonesia.

## ⭐ Workflow Utama (yt-dlp → Demucs → Web → Mix)

Strategi (9 Okt 2026): Sumber terpisah sejak fase yt-dlp, MP3 320 kbps output Demucs (hemat ~10x storage), mix SFX + dub dengan ducking.

Lihat [`tutor-mode-on-workflow.md`](tutor-mode-on-workflow.md) + [`tutor-demucs-setup.md`](tutor-demucs-setup.md) untuk panduan lengkap.

## Quick Index

### Workflow Dubbing (Fase 1-4)

| Script | Untuk Apa | Status |
|---|---|---|
| **`yt-dlp-tui.py`** ⭐ | TUI Download YouTube (pilih resolusi 480/720/1080) + audio terpisah | ✅ Utama |
| **`demucs-tui.py`** ⭐ | TUI Demucs SFX separation → no_vocals.mp3 (MP3 320, MPS acceleration) | ✅ Utama |
| **`mix-tui.py`** ⭐ | TUI Mix MP4 + no_vocals + audio_dub (ducking sidechain) | ✅ Utama |
| `srt-frequency-analyzer.py` ⭐ | Analisis SRT → top 100 kata tak dikenal (pakai Supabase) | ✅ Utama |

### Kamus Jawa Editor & Tools

| Script | Untuk Apa | Status |
|---|---|---|
| **`kamus-tui.py`** ⭐ | TUI edit kamus Jawa v2.3 (Phase 1-6 refactor, R-21 word field) | ✅ Utama |
| **`upload-supabase.py`** ⭐ | Upload entries approved ke Supabase (Phase 5, file terpisah) | ✅ Utama |
| `audit-otomatis-suspect-patterns.py` | R-19 audit suspect entries (124 paired suspect) | ✅ Audit |
| `neutralize-kamus-draft.py` | R-21 netralisasi entries belum berpasangan → field 'word' | ✅ Utility |
| `fix-angka-5-native-jawa.py` | R-22 fix angka 5/15/25/50 per native Jawa 7 varian (HANYA apply ke draft) | ✅ Utility |

### DISABLED (R-20 + R-22: raw = sampah, jangan run)

| Script | Status | Catatan |
|---|---|---|
| `build-kamus-bersih.py.DISABLED` | ⚠️ DISABLED | R-20: parser tolol merusak data |
| `parse-wiktionary-jv.py.DISABLED` | ⚠️ DISABLED | R-22: generator kamus-jawa-full.json (raw sampah) |
| `scrape-wiktionary-jv-lemma.py.DISABLED` | ⚠️ DISABLED | R-22: generator raw sampah |
| `scrape-lampiran-kamus.py.DISABLED` | ⚠️ DISABLED | R-22: generator raw sampah |
| `scrape-lampiran-angka.py.DISABLED` | ⚠️ DISABLED | R-22: generator raw sampah |
| `add-entry-id.py.DISABLED` | ⚠️ DISABLED | R-22: modifikasi kamus-jawa-full.json (legacy) |
| `fix-angka-ejaan.py.DISABLED` | ⚠️ DISABLED | R-22: apply ke angka-raw (raw = sampah) |
| `fix-draft-angka-ejaan.py.DISABLED` | ⚠️ DISABLED | R-22: apply ke angka-raw (raw = sampah) |
| `fix-dhingkluk.py.DISABLED` | ⚠️ DISABLED | R-22: one-off fix, sudah di-apply, tidak perlu run lagi |

### SQL Migrations (Supabase)

| File | Untuk Apa |
|---|---|
| `supabase-migration-v2.sql` | srt_projects + srt_cues (Editor SRT Jawa project-based) |
| `supabase-migration-v3.sql` | kamus: krama_inggil + register |

### DISABLED (R-20 — JANGAN RUN)

| Script | Status | Catatan |
|---|---|---|
| `build-kamus-bersih.py.DISABLED` | ⚠️ DISABLED | R-20: parser tolol merusak data. Kamus-draft.json = rujukan tunggal. Lihat `build-kamus-bersih.py.DISABLED.README.md` |

---

## ⭐ Workflow Utama (4 Fase, sumber terpisah)

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

# Fase 3a: Web app — Mode ON (Bahasa Indonesia, cara cepat)
# https://srt-splitter.vercel.app/
# Upload SRT ori → mode ON → Smart Fit (cap 2.0x) → pitch (-15Hz laki)
# → audio-id-dub.wav (dialog, 100% sync) — SUDAH JALAN

# Fase 3b: Web app — SRT editor (Bahasa Jawa, per cue) — NUNGGU CODE FIX
# + Project Baru → upload SRT ID + SRT Jawa → simpan ke Supabase
# → audio-jw-dub.wav — code perlu dibereskan (web app side)

# Fase 4: Mix (~7 detik)
python3 scripts/mix-tui.py
# → mp4-id-final.mp4 (video ori + SFX bersih + dialog dub, 0 DTS warnings)
```

Lihat [`tutor-mode-on-workflow.md`](tutor-mode-on-workflow.md) + [`tutor-demucs-setup.md`](tutor-demucs-setup.md) untuk detail.

---

## Kamus Jawa Workflow (v2.3, post-R-21 netral)

```bash
# Download (sekali saja) — R-20: kamus-draft.json = rujukan tunggal
curl -L -o kamus-jawa-draft.json \
  "https://raw.githubusercontent.com/emailnyamahmud-afk/srt-splitter/main/public/kamus-jawa-draft.json?v=23"
curl -L -o kamus-tui.py \
  "https://raw.githubusercontent.com/emailnyamahmud-afk/srt-splitter/main/scripts/kamus-tui.py?v=7"
curl -L -o upload-supabase.py \
  "https://raw.githubusercontent.com/emailnyamahmud-afk/srt-splitter/main/scripts/upload-supabase.py?v=1"
curl -L -o audit-suspects.json \
  "https://raw.githubusercontent.com/emailnyamahmud-afk/srt-splitter/main/public/audit-suspects.json?v=2"

# Setup .env (sekali saja via TUI menu "🔑 Set Supabase .env")
python3 kamus-tui.py

# Statistik startup: Total | NETRAL | 3-field ready | Approved
# Menu utama → "⚠ Filter: NETRAL" → browse 39.216 entries word-only
# Edit entry → isi ngoko/krama/arti (2 dari 3 → paired, word otomatis kosong)
# Setelah 3-field lengkap → status 'ready' → siap upload Supabase

# Menu "☁ Upload ke Supabase" → upload entries dengan user_approved=True (R-12)

# Re-run audit kapan saja:
python3 audit-otomatis-suspect-patterns.py
# → Output: audit-suspects.json (124 suspect entries untuk user validasi ulang)
```

### Aturan kamus (R-12 sampai R-21)

- **R-12**: User wajib validasi 1-1 sebelum upload Supabase
- **R-16**: Ejaan Jawa — diakritik é/è wajib, schwa polos "e"
- **R-17**: krama_inggil masuk field krama (sinonim comma)
- **R-18**: JANGAN HAPUS entry kamus (kosong/aksara/keterangan-only tetap disimpan)
- **R-19**: Parser AI tolol, audit suspect otomatis (124 entries)
- **R-20**: kamus-draft.json = rujukan tunggal, raw = arsip, build-kamus-bersih.py DISABLED
- **R-21**: field 'word' = netral, belum terdefinisi register

### User fallback (kata belum dikenali)

Per R-20: cari manual di kamus resmi Kemendikbud:
- https://kesakata.kemdikbud.go.id
- https://bahasa.kemdikbud.go.id
- Wiktionary online langsung (jangan batch scrape)

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

Lihat [`tutor-demucs-setup.md`](tutor-demucs-setup.md) untuk setup M1 16GB.

### `mix-tui.py` ⭐ — Mix TUI

```bash
python3 scripts/mix-tui.py
# 6 step: MP4 ori, no_vocals (mp3/wav/flac), audio dub, ducking, output, konfirmasi
# Output: mp4-id-final.mp4 (video stream copy + SFX + dub, 0 DTS warnings)
```

### `kamus-tui.py` ⭐ — Kamus Jawa Editor TUI v2.3

```bash
python3 scripts/kamus-tui.py
# Phase 1-6 refactor: helper _search_entries, _entry_label, filter NETRAL,
# merge_2_entries terpisah, upload via upload-supabase.py, textwrap
# Statistik startup: Total + NETRAL + 3-field ready + Approved
# Menu: Search, Browse READY/DRAFT, Filter NETRAL/3-field/NGOKO+KRAMA/etc,
#        Merge 2 entries, Mark READY bulk, Set Supabase .env, Upload
```

### `upload-supabase.py` ⭐ — Upload ke Supabase (Phase 5)

```bash
python3 upload-supabase.py
# Dipanggil dari kamus-tui.py (wrapper) atau standalone
# Filter: HANYA entries dengan user_approved=True (R-12 compliance)
# Batch POST 500 entries per request ke Supabase REST API
```

### `audit-otomatis-suspect-patterns.py` — Audit suspect (R-19)

```bash
python3 audit-otomatis-suspect-patterns.py
# Output: public/audit-suspects.json
# Pattern: parsing_artifact_ngoko (Indonesia word nyangkut),
#          parsing_artifact_arti (arti non-baku), krama_inggil_no_tag,
#          too_many_ngoko_synonyms (>8), too_many_krama_synonyms (>3)
```

### `srt-frequency-analyzer.py` ⭐ — Frequency Analyzer

```bash
python3 srt-frequency-analyzer.py ~/Dubbing/S1-jw.srt
# Output: ~/Dubbing/srt-freq-report.txt (top 100 kata tak dikenal + frequency)
# User copy list → paste di kamus-tui.py → search + add entry
```

### `parse-wiktionary-jv.py` — Parser Wiktionary XML (R-20: ARSIP, bukan rujukan)

```bash
python3 scripts/parse-wiktionary-jv.py
# Input: jv.wiktionary XML dump → Output: kamus-jawa-full.json (44.585 entries)
# Parser v5: register tag + krama_inggil + xref
# ⚠ R-20: Output ini = ARSIP raw, BUKAN rujukan. Jangan rebuild kamus-draft.json dari sini.
#   Build script (build-kamus-bersih.py.DISABLED) sudah di-disable — parser tolol merusak data.
```

### `scrape-lampiran-kamus.py` — Scraper Lampiran Kamus

```bash
python3 scripts/scrape-lampiran-kamus.py
# Source: id.wiktionary.org Lampiran Kamus Jawa-Indonesia
# Output: lampiran-raw.json (2.724 entries)
```

### `scrape-lampiran-angka.py` — Scraper Lampiran Nama Angka

```bash
python3 scripts/scrape-lampiran-angka.py
# Source: id.wiktionary.org Lampiran:Nama_angka_dalam_bahasa_Jawa
# Output: lampiran-angka-raw.json (66 entries, ground truth angka 1-1000)
```

### `scrape-wiktionary-jv-lemma.py` — Scraper jv:Lema

```bash
python3 scripts/scrape-wiktionary-jv-lemma.py
# Source: id.wiktionary.org Kategori:jv:Lema
# Output: kamus-jawa-new-lemma.json (859 entries)
```

### `neutralize-kamus-draft.py` — R-21 Netralisasi

```bash
python3 scripts/neutralize-kamus-draft.py
# Entries belum berpasangan (ngoko-only atau krama-only) → pindah ke field 'word'
# Sudah dijalankan sekali (v2.2 → v2.3), idempotent
```

### `fix-angka-ejaan.py` — R-16 Ejaan Angka

```bash
python3 scripts/fix-angka-ejaan.py
# Fix 3 masalah: eka→éka, Nol→nol, songo dari ngoko→hapus
# Idempotent — re-run aman
```

### `fix-dhingkluk.py` — R-12 Fix dhingkluk

```bash
python3 scripts/fix-dhingkluk.py
# Fix 1 entry: dhingkluk arti 'menunduk', long form pindah ke keterangan
# Per user konfirmasi 9 Okt 2026
```

---

## Catatan

- **Workflow utama**: yt-dlp (Fase 1) → demucs-tui.py (Fase 2) → web Mode ON (Fase 3a) → mix-tui.py (Fase 4)
- **Multi-bahasa**: Mode ON untuk ID (sudah jalan), SRT editor untuk Jawa (nunggu code fix + kamus)
- **Mode manual**: DaVinci Resolve (tarik file ke timeline, edit sendiri)
- **Audio utuh 100%** — tidak ada potongan di TTS mode ON + Smart Fit (no truncate)
- **Kamus Jawa** — v2.3 (post-R-21 netral), 45.021 entries, 5.803 paired + 39.216 NETRAL
- Script aman dijalankan ulang (idempotent) — kecuali `build-kamus-bersih.py.DISABLED` (R-20: JANGAN RUN)
