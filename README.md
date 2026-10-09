# SRT Splitter + Dubbing Jawa

Aplikasi web untuk split SRT, translate subtitle, dan **dubbing Mandarin → Jawa** dengan audio natural. 100% di browser, gratis. Workflow lengkap sampai mix video dengan FFmpeg.

**Live:** https://srt-splitter.vercel.app/
**Source:** https://github.com/emailnyamahmud-afk/srt-splitter

> **🤖 Untuk AI agent:** Baca [`AGENTS.md`](AGENTS.md) + [`PROJECT_RULES.md`](PROJECT_RULES.md) di awal setiap session. Berisi status pipeline + 21 aturan project-specific (R-01 sampai R-21: workflow, docs, marker, ejaan Jawa, netral data, no-delete).

> **📖 Visi Project:** Bukan cuma dubbing Mandarin → Jawa. Ini prototype untuk **digitalisasi bahasa daerah Indonesia di era AI** (700 bahasa, 169 terancam punah). Lihat [`docs/PROJECT_VISION.md`](docs/PROJECT_VISION.md) untuk konteks lengkap + roadmap 2 tahun.

---

## Fitur Utama

### Web App (https://srt-splitter.vercel.app/)

Aplikasi web punya **2 mode dubbing** sesuai bahasa target:

#### Mode ON — Bahasa Indonesia (cara cepat, SUDAH JALAN) ✅

Workflow lama, khusus dub Indonesia. Generate full durasi 1 klik, default voice Dimas untuk semua cue.

| Fitur | Deskripsi |
|---|---|
| **TTS Mode ON + Smart Fit** | Per-cue dynamic TTS speed (cap 2.0x, pitch preserved), 100% sync SRT ori |
| **TTS Pitch Control** | -10Hz laki (lebih bas), +10Hz perempuan (lebih tinggi) |
| **TTS Mode OFF** | Natural sequential, speed 1.0x-2.0x |
| **Default voice** | Dimas (laki-laki) untuk semua cue (auto) |
| **Output** | `audio-id-dub.wav` (1 klik generate full durasi) |
| **Status** | ✅ SUDAH JALAN — siap pakai untuk pipeline mix-tui.py |

#### Editor SRT Jawa — Bahasa Jawa (per cue, masa depan) ⏳

Workflow baru, project-based. Saat ini user masih klik per cue satu-satu untuk preview + generate.

| Fitur | Deskripsi |
|---|---|
| **Project-based workflow** | "+ Project Baru" → upload 2 SRT (ID + Jawa), simpan ke Supabase |
| **Multi-project** | S1 (unfinished), S2 (unfinished), tutup S2, buka S1, lanjut kapan saja |
| **Auto-save 1.5s** | Edit cue → simpan ke Supabase otomatis (debounced) |
| **Per-cue Preview** | "▶ Preview" → generate TTS 1 cue, play inline di browser |
| **Browser cache (IndexedDB)** | Audio tersimpan di browser, survive reload, no re-gen untuk cue yang sama |
| **Generate Full** | Pakai cache kalau valid (hemat API call) + auto-download WAV |
| **Bidirectional alias** | Source apapun (aku/inyong/kula/dalem/saya/gue/ane) → convert ke ngoko/krama utama |
| **Arti (Indonesia) alias** | "saya" → klik Ngoko → "nyong", klik Krama → "kula" (asalkan "saya" ada di arti alias) |
| **Per-cue voice** | Dimas/Siti (Jawa) — assign per cue |
| **Auto-strip aksen TTS** | é/è/ê → e otomatis saat TTS (SRT final tetap utuh dengan aksen) |
| **⚠ Top 100 Unknown Words** | Panel amber: list top 100 kata tak dikenal kamus + frequency + Copy all |
| **Badge per cue "N tak dikenal"** | Visual cue: cue mana yang perlu review (amber border) |
| **Output** | `audio-jw-dub.wav` |
| **Status** | ⏳ Code perlu dibereskan: default voice Dimas otomatis untuk semua cue |
| **Kamus Jawa** | Di Supabase, progressif (50 entries/minggu), target 10.000 entries 3-pasangan terverifikasi |

#### Split / Translate (SEKUNDER — utility)

| Fitur | Deskripsi |
|---|---|
| **Split SRT** | By durasi (5m-5jam) atau by karakter (max 5000) |
| **Translate** | EN→ID, ID→Jawa, Jawa→ID (gratis Google Translate atau premium OpenAI) |

#### Kamus Jawa Viewer (READ-ONLY) ⚠

| Fitur | Deskripsi |
|---|---|
| **Display kamus dari Supabase** | Search → lihat entry (word + ngoko + krama + arti + keterangan) |
| **Status badge** | ✓ approved (clean/ready) / draft (belum di-edit user) |
| **READ-ONLY** | Web app TIDAK edit kamus — editing via TUI lokal (kamus-tui.py) + upload ke Supabase |
| **Validasi level 2** | User edit langsung di Supabase Table Editor kalau ada keanehan |

### Python Scripts (lokal, untuk produksi final)

| Script | Fungsi |
|---|---|
| **`yt-dlp-tui.py`** ⭐ | TUI Download YouTube (pilih resolusi 480/720/1080) + audio terpisah |
| **`demucs-tui.py`** ⭐ | TUI Demucs SFX separation → no_vocals.mp3 (MP3 320 kbps, MPS acceleration) |
| **`mix-tui.py`** ⭐ | TUI Mix MP4 + no_vocals + audio_dub (~7 detik, 0 DTS warnings, ducking sidechain) |
| **`kamus-tui.py`** ⭐ | TUI edit kamus Jawa v2.6 — Phase 1-6 refactor, filter NETRAL, R-21 word field |
| **`upload-supabase.py`** | Upload entries approved ke Supabase (Phase 5, file terpisah, user-triggered only) |
| **`srt-frequency-analyzer.py`** | Analisis SRT → top 100 kata tak dikenal (pakai Supabase sebagai ground of truth) |
| **`supabase-migration-v2.sql`** | SQL: srt_projects + srt_cues (Editor SRT Jawa) |
| **`supabase-migration-v3.sql`** | SQL: kamus krama_inggil + register |

---

## Workflow Dubbing Mandarin → Jawa (4 Fase, sumber terpisah)

```
Fase 1: Download dari YouTube (yt-dlp-tui.py, Python lokal)
  Pilih resolusi (480/720/1080) → output: mp4-ori.mp4 + audio.wav (terpisah)
        ↓
Fase 2: SFX Separation dengan Demucs (demucs-tui.py, Python lokal)
  Input: audio.wav → Output: no_vocals.mp3 (SFX bersih, MP3 320 kbps)
        ↓
Fase 3a: Web app — Mode ON (Bahasa Indonesia, cara cepat) — SUDAH JALAN
  Upload SRT ori → mode ON → Smart Fit (cap 2.0x) → pitch (-15Hz laki)
  Default voice: Dimas untuk semua cue → audio-id-dub.wav (dialog, 100% sync)
        ↓
Fase 3b: Web app — SRT editor (Bahasa Jawa, per cue) — NUNGGU CODE FIX
  + Project Baru → upload SRT ID + SRT Jawa → simpan ke Supabase
  Edit cue (text/voice/ngoko/krama) → Preview per cue → Generate Full
  Output: audio-jw-dub.wav
  Kamus Jawa di Supabase (progressif, 50 entries/minggu)
        ↓
Fase 4: Mix SFX + Dub (mix-tui.py, Python lokal)
  Input: mp4-ori.mp4 + no_vocals.mp3 + audio-id-dub.wav (atau audio-jw-dub.wav)
  Output: mp4-{lang}-final.mp4 (video stream copy, 0 DTS warnings, 100% sync)
        ↓
Fase 5 (opsional): Edit final di DaVinci Resolve (manual)
```

---

## Setup

### 1. Supabase (untuk Editor SRT Jawa project-based)

1. Daftar [supabase.com](https://supabase.com) (free, no credit card)
2. Create project → dapat Project URL + anon key
3. Set Vercel env vars:
   ```
   NEXT_PUBLIC_SUPABASE_URL=https://xxx.supabase.co
   NEXT_PUBLIC_SUPABASE_ANON_KEY=eyJxxx
   ```
4. Run SQL migrations di Supabase SQL Editor:
   - `scripts/supabase-migration-v2.sql` (srt_projects + srt_cues untuk Editor)
   - `scripts/supabase-migration-v3.sql` (kamus: krama_inggil + register)

### 2. Kamus Jawa (download dari GitHub)

R-22: **kamus-jawa-draft.json = satu-satunya sumber (NETRAL)**. Semua raw files + parser scripts DIHAPUS dari repo — isinya parsing AI tolol.

```bash
# Download kamus draft (17MB, v2.27 — merge 611 duplikat + fallback arti=word)
curl -L -o kamus-jawa-draft.json \
  "https://raw.githubusercontent.com/emailnyamahmud-afk/srt-splitter/main/public/kamus-jawa-draft.json?v=27"

# Download TUI editor (v9, menu Deteksi Duplikat + filter NETRAL)
curl -L -o kamus-tui.py \
  "https://raw.githubusercontent.com/emailnyamahmud-afk/srt-splitter/main/scripts/kamus-tui.py?v=9"

# Download upload script (Phase 5, user-triggered only, R-12 konfirmasi 'y')
curl -L -o upload-supabase.py \
  "https://raw.githubusercontent.com/emailnyamahmud-afk/srt-splitter/main/scripts/upload-supabase.py?v=2"

# Download audit duplikat (catatan, bukan perintah hapus)
curl -L -o duplikat-audit.json \
  "https://raw.githubusercontent.com/emailnyamahmud-afk/srt-splitter/main/public/duplikat-audit.json?v=1"
```

> ⚠ **R-22: SEMUA raw files + parser scripts DIHAPUS dari repo.**
> Raw files (kamus-jawa-full.json, angka-raw.json, lampiran-raw.json, dasanama-raw.csv, dll) = HASIL PARSING AI TOLOL dari internet sampah. Semua dihapus permanen.
> Yang TINGGAL hanya `public/kamus-jawa-draft.json` (NETRAL — buta, word tanpa definisi, BUKAN sumber kebenaran).
> User fallback kalau nemu kata belum dikenali: cari manual di https://kesakata.kemdikbud.go.id.

### 3. Python Lokal (untuk Demucs + Mix)

```bash
# Setup (sekali saja)
brew install ffmpeg
pip3 install edge-tts numpy questionary

# Optional: Demucs untuk SFX separation
pip3 install demucs
```

Lihat [`scripts/tutor-python-lokal.md`](scripts/tutor-python-lokal.md) untuk detail.

---

## Kamus Jawa

### Filosofi (R-20 + R-21)

- **Supabase DB = ground of truth** (yang user upload, mulai dari 2 entries, tumbuh bertahap)
- **kamus-jawa-draft.json = satu-satunya rujukan lokal** (R-20) — raw files hanya arsip
- **Web app + analyzer pakai Supabase**, bukan JSON lokal
- **Web app READ-ONLY** untuk kamus — editing via TUI lokal → upload ke Supabase
- **Validasi level 2** = user edit langsung di DB Supabase (Table Editor) kalau ada keanehan
- **R-21: entries belum berpasangan = field 'word' (netral)** — data jujur, bukan tebakan AI

### Schema v6.1 (45.021 entries, post-R-21 netral)

```json
{
  "word": "kula",          // NETRAL — belum terdefinisi (R-21), kosong kalau sudah paired
  "ngoko": "",             // ngoko + sinonim (koma) — diisi kalau paired
  "aksara": "ꦏꦸꦭ",        // aksara Jawa (PERTAHANKAN, R-18)
  "krama": "",             // krama + kramainggil + sinonim (koma) — diisi kalau paired
  "arti": "",               // terjemahan Indonesia — diisi kalau paired
  "keterangan": "aku, -ku; dak-, tak-; ...",  // definisi JAWA + Indonesia (JANGAN HAPUS, R-18)
  "register": "umum",       // ngoko|krama|krama_inggil|kawi|umum
  "sumber": "jv.wiktionary.org + xref",
  "is_angka": false,        // true untuk angka 1-1000
  "status": "draft"        // draft|ready (user validate via TUI)
}
```

### Stats (v2.27, post-merge + scan + fallback)

```
Total entries:           44.004 (setelah merge 611 duplikat)
✅ PAIRED 3-field:        2.936  (6.7%)  ← ngoko+krama+arti lengkap
⚠ NETRAL (word+arti):   39.230  (89.2%)  ← arti=word (fallback), user tentukan ngoko/krama
✅ Empty (R-18 tetap):        2  (0.0%)

Arti terisi:    44.002 (100%)  ← semua entries punya arti minimal (fallback=word)
Ngoko terisi:   4.703 (10.7%)
Krama terisi:   3.005 (6.8%)
Keterangan:     42.925 (97.5%)  ← PETUNJUK konteks dari scrap
Duplikat arti:      0  ← sudah merge
Duplikat ngoko:   211 tokens  ← user bersihkan via TUI (menu Deteksi Duplikat)
Duplikat krama:   192 tokens
Cross-field:      140 tokens

Angka 1-1000 (contoh 3-pasangan terdefinisi):
  Coverage: 1000/1000 (100%) — ngoko+krama+arti semua terisi
  Ejaan baku v6.3: limo (5), limolas (15), sèlawé+selawe (25), séket+seket (50)
  panca+ponco = sinonim Sanskrit, TETAP (R-18 jangan hapus)
```

### Menu TUI (kamus-tui.py v9)

```
📊 Statistik kamus
🔍 Search (cari kata di semua field)
✅ Browse READY (status=ready, siap upload)
📋 Browse DRAFT (belum di-edit user)
⚠ Filter: NETRAL (39.230 entri, word+arti, user tentukan ngoko/krama)
🟢 Filter: LENGKAP 3-field (2.936 entri, siap review/upload)
🟡 Filter: NGOKO+KRAMA (perlu isi arti)
⚪ Filter: NGOKO SAJA (perlu isi krama+arti)
🔵 Filter: NGOKO+ARTI (perlu isi krama)
📂 Browse by source (lemma/mendeley/dasanama/angka)
⭐ Browse entries dengan krama mapping
📝 Browse entries BELUM ada arti
🔗 Merge 2 entries (search kata)
🔍 Deteksi duplikat (JANGAN HAPUS, user putuskan)
⚡ Mark READY/DRAFT bulk
🔑 Set Supabase .env
☁  Upload ke Supabase (hanya yang READY)
❌ Keluar
```

### Bidirectional alias lookup (di web app)

- Source: word + ngoko + krama + krama_inggil + **arti (Indonesia)** alias
- Mis. user isi entry: `word=""`, `ngoko="Nyong, Aku, Inyong"`, `krama="Kula, Dalem"`, `arti="Saya, Aku, Gue, Gua, Ane"`
- Source SRT = "saya" → klik Ngoko → "Nyong", klik Krama → "Kula"
- Source SRT = "gue" → klik Ngoko → "Nyong", klik Krama → "Kula"
- Source SRT = "kula" → klik Ngoko → "Nyong"

### Workflow user (MacBook)

```bash
cd ~/Dubbing

# 1. Download kamus draft + TUI + upload script (lihat section Setup)
# 2. Set Supabase credentials (sekali saja via TUI menu "🔑 Set Supabase .env")
python3 kamus-tui.py

# 3. Statistik startup akan tampil: Total | NETRAL | 3-field ready | Approved
# 4. Menu utama → pilih "⚠ Filter: NETRAL (39216 entri)" → browse entries word-only
# 5. Pilih 1 entry → edit → isi ngoko/krama/arti (2 dari 3 → paired) → save
#    word otomatis kosong saat paired (R-21)
# 6. Setelah 3-field lengkap → status 'ready' → siap upload Supabase
# 7. Menu "☁ Upload ke Supabase" → upload entries dengan user_approved=True (R-12)
```

### User fallback (kalau nemu kata belum dikenali)

Per R-22: cari manual di kamus resmi Kemendikbud:
- https://kesakata.kemdikbud.go.id
- https://bahasa.kemdikbud.go.id
- Wiktionary online langsung (jangan batch scrape)

Setelah ketemu → user edit manual via TUI, AI bantu tapi jangan auto-merge (R-18 — jangan hapus).

---

## Stack Teknologi

### Web App
- Next.js 16 + TypeScript + Tailwind CSS 4 + shadcn/ui
- Deploy: Vercel (app + Edge TTS proxy + Google Translate proxy)
- Supabase PostgreSQL (project + cues + kamus)
- IndexedDB (browser local audio cache)

### Python Scripts
- Python 3.8+
- FFmpeg (auto-detect)
- Demucs (Meta, open source, untuk SFX separation, MPS acceleration di Apple Silicon)
- Edge TTS (Microsoft, gratis, native Indonesia/Jawa)
- Questionary (TUI interaktif)

### Storage
- Supabase PostgreSQL free tier (500MB DB) — project + cues + kamus (ground of truth)
- IndexedDB browser (ratusan MB) — audio cache per cue + full audio
- GitHub repo — `public/kamus-jawa-draft.json` (17MB NETRAL) untuk user download

---

## Struktur Folder

```
srt-splitter/
├── README.md                            # Dokumen ini
├── AGENTS.md                            # Entry file AI agent
├── PROJECT_RULES.md                     # 22 aturan project (R-01 sampai R-22)
├── worklog.md                           # Work log multi-agent (append-only)
├── docs/                                # Dokumentasi teknis + visi
│   ├── PROJECT_VISION.md                # Visi digitalisasi bahasa + roadmap 2 tahun
│   ├── PROGRESS.md                      # Status project + timeline
│   └── EDGE_TTS_PROXY.md                # Cara kerja Edge TTS proxy
├── scripts/                             # Python scripts + SQL migrations (R-22: hanya workflow, raw dihapus)
│   ├── kamus-tui.py                     # TUI edit kamus v2.6 (Phase 1-6 refactor)
│   ├── upload-supabase.py               # Upload script (Phase 5, user-triggered only)
│   ├── yt-dlp-tui.py + demucs-tui.py + mix-tui.py  # Dubbing workflow
│   ├── srt-frequency-analyzer.py        # Analyzer SRT (pakai DB Supabase)
│   ├── supabase-migration-v2.sql + v3.sql  # SQL DB
│   ├── tutor-*.md + README.md           # Dokumentasi
├── src/                                 # Next.js source code
├── api/                                 # Vercel serverless functions
└── public/                              # Static assets (R-22: hanya 1 kamus + web assets)
    ├── kamus-jawa-draft.json            # Kamus v2.6 (17MB, NETRAL — rujukan tunggal)
    ├── kamus-viewer.html                # Kamus viewer (web, read-only)
    ├── logo.svg + coi-serviceworker.js + robots.txt  # Web assets
```

---

## Deploy

### Vercel (auto-deploy, default)
1. Push ke GitHub `main` branch
2. Vercel auto-deploy
3. URL: https://srt-splitter.vercel.app/

### Lokal (dev)
```bash
bun install
bun run dev
# Buka http://localhost:3000
```

---

## Environment Variables

```
NEXT_PUBLIC_SUPABASE_URL=https://xxx.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=eyJxxx
```

Set di Vercel dashboard (Project Settings → Environment Variables).

Edge TTS proxy pakai hardcoded Microsoft token (gratis, no auth). OpenAI/OpenRouter TTS pakai user API key di UI (localStorage).

---

## Status Project

Lihat [`docs/PROGRESS.md`](docs/PROGRESS.md) untuk:
- Quick status table (apa yang sudah jadi, apa yang pending)
- Milestone terbaru (R-21 netral kamus, Phase 1-6 TUI refactor, 9 Okt 2026)
- Catatan untuk AI next time buka
- Timeline update lengkap

Lihat [`worklog.md`](worklog.md) untuk:
- Work log per Task ID (multi-agent, append-only)
- Stage summary tiap task
- Pending items

---

## License

Bebas dipakai untuk produksi sendiri. Atribusi dihargai tapi tidak wajib.

---

## Credits

Teknologi yang dipakai:
- **Edge TTS** — Microsoft neural voices (gratis, native Indonesia/Jawa)
- **Demucs** — Source separation by Meta/Facebook Research
- **FFmpeg** — Video/audio processing
- **Supabase** — PostgreSQL + Auth + Storage
- **ThioJoe ASTD** — Inspirasi trim silence + two-pass TTS
- **VoiceStudio** — Inspirasi Smart Fit algorithm
- **voicertool.com** — Inspirasi asymmetric trim + cap 2.0x
- **Wiktionary Jawa** — Source kamus (44.585 entri awal, sekarang 45.021 setelah merge + R-21 netral)
- **Mendeley Dataset** — Faisal Rahutomo et al, 2018 (krama + kramainggil pair, 955 entries)
- **Lampiran Kamus Jawa-Indonesia** — Wiktionary (2.724 entries)
- **Lampiran:Nama_angka_dalam_bahasa_Jawa** — Wiktionary (66 entries, ground truth angka)
- **Kamendikbud** — https://kesakata.kemdikbud.go.id (user fallback untuk kata belum dikenali, R-20)
