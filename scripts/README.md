# Scripts — SRT Splitter + Dubbing

Script Python untuk workflow dubbing Mandarin → Jawa + edit kamus Jawa.

**R-22 compliance**: SEMUA parser/scraper/raw script DIHAPUS. Hanya workflow script aktif.
Raw files = sampah parsing AI tolol. Yang TINGGAL: kamus-jawa-draft.json (NETRAL).

## ⭐ Workflow Utama (Dubbing 4 Fase)

```bash
# Setup (sekali saja)
brew install ffmpeg
pip3 install demucs questionary numpy

# Fase 1: Download dari YouTube (v5)
python3 scripts/yt-dlp-tui.py
# → {name}.mp4 + {name}-audio.m4a (native M4A, no konversi MP3) + {name}.id.srt

# Fase 2: SFX separation (Demucs)
python3 scripts/demucs-tui.py
# → no_vocals.mp3 (MP3 320 kbps)

# Fase 3a: TTS Indonesia via edge-tts-tui.py (LOKAL — ganti web app Mode ON)
python3 scripts/edge-tts-tui.py
# → {prefix}-audio-id-dub.wav (full durasi, 1 file utuh)
# Kenapa lokal: web app Vercel rate-limit + OOM untuk SRT 2 jam 3000-5000 cue

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
| **`edge-tts-tui.py`** ⭐ | TUI Edge TTS lokal (Mode ON + Smart Fit, full durasi, ganti web app) | ✅ Utama |
| **`yt-dlp-tui.py`** ⭐ | TUI Download YouTube v5 (resolusi 480/720/1080 + M4A native + SRT Indonesia) | ✅ Utama |
| **`demucs-tui.py`** ⭐ | TUI Demucs SFX separation → no_vocals.mp3 (MP3 320, MPS) | ✅ Utama |
| **`mix-tui.py`** ⭐ | TUI Mix MP4 + no_vocals + audio_dub (ducking sidechain) | ✅ Utama |
| **`srt-frequency-analyzer.py`** ⭐ | Analisis SRT → top 100 kata tak dikenal (pakai Supabase) | ✅ Utama |

### Kamus Workflow Scripts

| Script | Untuk Apa | Status |
|---|---|---|
| **`kamus-tui.py`** ⭐ | TUI edit kamus Jawa v9 (22 field, 8 kategori duplikat, edit langsung dari list) | ✅ Utama |
| **`upload-supabase.py`** | Upload entries approved ke Supabase (user-triggered only, R-12) | ✅ Utama |
| **`audit-statistik-duplikat.py`** ⭐ | Audit statistik + scan duplikat global (read-only, 8 kategori, top 20 sample) | ✅ Audit |
| **`bersihkan-wiki-markup.py`** | Bersihkan wiki markup `[[..]]`, `{{..}}`, `<tag>` (R-18 no data loss) | ✅ Maintenance |
| `standarisasi-kamus.py` | Standarisasi v3.0 (HAPUS 13 field) — REVERTED, jangan pakai | ❌ REVERTED (R-23) |
| `standarisasi-kamus-v2.py` | Standarisasi PROPER (22 field, no data loss) — sudah di-apply, aman | ✅ Maintenance |

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

## Kamus Jawa Workflow (v2.6.1, post-wiki-markup-cleanup — 10 Okt 2026)

```bash
# Download (sekali saja) — R-22: hanya kamus-draft.json, raw dihapus
# Cache-buster: t=<timestamp> supaya gak ambil dari cache CDN
curl -L -H 'Cache-Control: no-cache' -o kamus-jawa-draft.json \
  "https://raw.githubusercontent.com/emailnyamahmud-afk/srt-splitter/main/public/kamus-jawa-draft.json?t=$(date +%s)"
curl -L -H 'Cache-Control: no-cache' -o kamus-tui.py \
  "https://raw.githubusercontent.com/emailnyamahmud-afk/srt-splitter/main/scripts/kamus-tui.py?t=$(date +%s)"
curl -L -H 'Cache-Control: no-cache' -o upload-supabase.py \
  "https://raw.githubusercontent.com/emailnyamahmud-afk/srt-splitter/main/scripts/upload-supabase.py?t=$(date +%s)"

# Setup .env (sekali saja via TUI menu "🔑 Set Supabase .env")
python3 kamus-tui.py

# Statistik startup: Total | NETRAL | 3-field ready | Status ready
# Menu utama → "⚠ Filter: NETRAL" → browse 39.216 entries word-only
# Edit entry → isi ngoko/krama/arti (2 dari 3 → paired) → save
# Setelah 3-field lengkap → status 'ready' → siap upload Supabase

# Menu "☁ Upload ke Supabase" → konfirmasi 'y' eksplisit → upload batch 500
```

### Aturan kamus (R-12 sampai R-25)

- **R-12**: User wajib validasi 1-1 sebelum upload Supabase (status='ready')
- **R-16**: Raw files DIHAPUS dari repo (R-22 override)
- **R-16a**: Ejaan Jawa (panduan teknis, AI tidak audit ejaan dari raw)
- **R-17**: krama_inggil masuk field krama (sinonim comma)
- **R-18**: JANGAN HAPUS entry kamus (kosong/aksara/keterangan-only tetap disimpan). Berlaku juga untuk FIELD (R-23).
- **R-19**: Parser AI tolol, raw = sampah
- **R-20**: kamus-draft.json = rujukan tunggal, raw = DIHAPUS
- **R-21**: field 'word' = netral, belum terdefinisi register
- **R-22**: GIGO — AI tidak merujuk raw untuk audit/fix, bantu workflow saja
- **R-23**: Standarisasi ≠ HAPUS field. R-18 berlaku untuk FIELD juga. Backup + audit dulu, baru eksekusi.
- **R-24**: Statistik "arti 100% filled" MENIPU. Audit real Indonesia: 4.771 entries (10.84%) Indonesia real, 39.231 (89.15%) fallback=word.
- **R-25**: detect_duplicates WAJIB tampilkan word NETRAL. 8 kategori lintas entry + lintas field, edit langsung dari list.

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

### `edge-tts-tui.py` ⭐ — Edge TTS Lokal (ganti web app Mode ON)

```bash
python3 scripts/edge-tts-tui.py
# Step 1: pilih SRT Indonesia (dari yt-dlp, mis. S5-ori.id.srt)
# Step 2: output dir (default sama dengan SRT)
# Step 3: voice → Ardi (laki) / Gadis (perempuan) / Dimas (Jawa laki) / Siti (Jawa perempuan)
# Step 4: pitch → -10Hz (laki) / +10Hz (perempuan) / +0Hz (natural)
# Step 5: Smart Fit cap → 2.0x (default, voicertool cap)
# Step 6: prefix (default: nama SRT tanpa extension)
# Output: {prefix}-audio-id-dub.wav (WAV 24kHz mono 16-bit, full durasi 1 file utuh)
# Cache: .cache/{prefix}-cue-{NNN}-{hash}.mp3 (per-cue, resume support)
```

**Kenapa lokal (bukan web app)?**
- Web app Vercel maxDuration 60s, rate-limit setelah ribuan request
- Microsoft Edge TTS rate-limit (429 Too Many Requests) untuk request cepat berturut
- Web app ZIP building OOM untuk SRT > 30 menit
- Lokal: tidak ada limit, tidak ada rate-limit, tidak ada ZIP

**RAM untuk 5000 cue (2 jam):**
- Buffer: 700 MB (float32, pre-allocate sekali)
- Per cue: 200 KB (sementara, free setelah mix)
- Peak: ~750 MB — AMAN di Mac 16 GB

**Logika (Mode ON + Smart Fit, port dari web app):**
1. Per cue: generate natural TTS (rate +0%)
2. Asymmetric trim silence (head -30dB, tail -30dB)
3. Compute need = naturalDur / cueDur
4. Kalau need > 1.0 → re-generate dengan rate = min(need, cap)*100%
   - Pitch preserved (Edge TTS server-side rate)
5. Peak normalize -2 dBFS
6. Mix ADD ke buffer pada cue.start (inline, no segments array)
7. Crossfade 150ms kalau overlap dengan cue next

### `yt-dlp-tui.py` ⭐ — Download TUI (v5)

```bash
python3 scripts/yt-dlp-tui.py
# Pilih: URL YouTube → resolusi (480/720/1080) → nama custom → SRT Indonesia
# Output: {name}.mp4 (video) + {name}-audio.m4a (audio native YouTube) + {name}.id.srt
# v5: M4A native (skip konversi MP3, hemat ~15s + disk), subtitle parser JSON (count benar)
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

### `kamus-tui.py` ⭐ — Kamus Jawa Editor TUI v9 (10 Okt 2026)

```bash
python3 scripts/kamus-tui.py
# 22 field per entry (standarisasi PROPER, R-23)
# Statistik startup: Total + NETRAL + 3-field ready + Status ready
# Menu utama (17 menu):
#   - Statistik kamus (source tags, kelengkapan, register, status)
#   - Search (cari kata di ngoko/krama/krama_inggil/arti)
#   - Browse READY/DRAFT/NETRAL/LNGKAP/NGOKO+KRAMA/NGOKO SAJA/NGOKO+ARTI
#   - Browse by source (lemma/mendeley/dasanama/angka)
#   - Browse with krama mapping, BELUM ada arti
#   - Merge 2 entries (search kata, preview, konfirmasi)
#   - 🔍 Deteksi duplikat (8 kategori, R-25: word NETRAL tampil)
#   - Mark READY/DRAFT bulk (search kata, tanpa edit)
#   - Set Supabase .env (URL + anon key)
#   - Upload ke Supabase (hanya status='ready')
#
# Deteksi duplikat — 8 kategori (lintas entry + lintas field):
#   1. Duplikat ngoko (same field, beda entry)
#   2. Duplikat krama
#   3. Duplikat word (NETRAL)
#   4. Duplikat arti (Indonesia)
#   5. Cross ngoko↔krama
#   6. Cross ngoko↔arti
#   7. Cross krama↔arti
#   8. Cross word↔ngoko/krama/arti (NETRAL duplikat di paired entry)
#
# User bisa ketik entry_id langsung dari list duplikat → edit_entry jalan
# → save → kembali ke list (tidak perlu balik menu utama)
```

### `audit-statistik-duplikat.py` ⭐ — Audit Statistik + Scan Duplikat Global

```bash
python3 scripts/audit-statistik-duplikat.py
# Output: statistik penuh + scan 3.275 duplikat (877 same-field + 2.398 cross-field)
# Logika sama persis dengan detect_duplicates() di TUI
# Top 20 + sample 5 per kategori
# Read-only, tidak modifikasi kamus
```

### `bersihkan-wiki-markup.py` — Bersihkan Wiki Markup (R-18 no data loss)

```bash
python3 scripts/bersihkan-wiki-markup.py
# Bersihkan: [[link]] → link, {{template}} → hapus, <tag> → hapus tag preserve teks
# Normalize whitespace, trailing comma
# Backup dulu, baru eksekusi. Verify 0 data hilang.
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
- **Kamus Jawa** — v2.6.1 (10 Okt 2026): 22 field standar, 44.005 entries, 2.937 paired + 39.230 NETRAL + 1.766 ngoko+arti
- **Audit**: 3.275 duplikat terdeteksi (877 same-field + 2.398 cross-field)
- **Arti real**: 4.771 entries (10.84%) Indonesia real, 39.231 (89.15%) fallback=word
- R-22: SEMUA raw + parser script DIHAPUS. Hanya workflow script aktif.
- R-23: Standarisasi ≠ hapus field. R-18 berlaku untuk FIELD juga.
- R-25: detect_duplicates WAJIB tampilkan word NETRAL.
