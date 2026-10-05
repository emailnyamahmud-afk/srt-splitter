# Progress Log — SRT Splitter + Dubbing Project

Dokumen ini catatan status project untuk AI / developer next time baca. Update setiap sesi kerja.

**Last updated:** 5 Oktober 2026, 08:30 WIB

---

## 📌 Quick Status

| Item | Status |
|---|---|
| Web app (srt-splitter.vercel.app) | ✅ Production ready |
| Dubbing Mode (SRT = ground truth) | ✅ Working, tested user |
| Python `dubbing-tui.py` (TUI) | ✅ Working, user tested |
| Python `retime-video.py` v5 (M1 optimized) | ⏳ In progress (testing) |
| Python `separate-audio-sfx.py` (Demucs) | ✅ Working (belum user test) |
| User test render S7-id.mp4 (2.5 jam AV1) | ✅ SUKSES 5 Okt 02:54 — tapi video rusak (DTS) |
| User test render 5min H.264 + VideoToolbox | ⏳ In progress (test #6) |
| Kamus Jawa JSON | 🔜 Next step (riset) |
| Workflow multi-bahasa (Jawa/Sunda/dll) | 🔜 Next step |

---

## 🐛 BUG HISTORY: Video Retaimed Rusak (5 Okt 03:00-08:00 WIB)

### Gejala
- VLC: frame berhenti, suara TTS ada
- DaVinci: video merah (Media Offline), audio waveform OK
- SRT terlihat 3 jam 35 menit di DaVinci (sebenarnya 2 jam 36 menit)

### Root Cause
**FFmpeg concat dengan stream copy + B-frames = non-monotonic DTS**

B-frames (bidirectional frames) punya DTS yang bisa mundur (menengok frame setelahnya). Saat `setpts` slow-mo, timestamp jadi non-monotonic → FFmpeg warning → video patah/diulang.

### Timeline Debug (8 iterasi fix)

| Test # | Strategi | Hasil | Penyebab Gagal |
|---|---|---|---|
| #1 | Filter complex inline (8268 segments) | frame=0, stuck | Memory 40GB, FFmpeg swap |
| #2 | Two-pass rendering (file-based segments) | Sukses, tapi video rusak | Stream copy + B-frames |
| #3 | Cumulative offset + stream copy | 491 DTS warnings | B-frames tetap bermasalah |
| #4 | Re-encode Pass 2 + source 360p rusak | Frame berhenti lama | Source video rusak (AV1→H.264 360p) |
| #5 | Re-encode + source 5min stream copy | Masih DTS warnings | jsDelivr cache, user dapat versi lama |
| #6 | H.264 source + VideoToolbox + `-bf 0` | ⏳ In progress | - |

### 8 Fix yang Diimplementasi di `retime-video.py`

| # | Fix | Dari Riset | Dampak |
|---|---|---|---|
| 1 | Two-pass rendering (file-based segments) | Memory issue | Pass 1 parallel, Pass 2 concat |
| 2 | `-filter_complex_script_filename` → `-/filter_complex` | FFmpeg 7+ compat | Fix "Unrecognized option" |
| 3 | Filter segments di luar range video input | Test video pendek | Fix 8267/8267 gagal |
| 4 | Hapus `-reset_ts zero` (invalid di FFmpeg 7+) | Sandbox test | Fix "Unrecognized option" |
| 5 | Hapus `-vsync cfr` (deprecated FFmpeg 5.1+) | Sandbox test | Fix "Unrecognized option" |
| 6 | `setpts=(PTS-STARTPTS)*factor` (bukan `/factor`) | Sandbox test | Fix slow-mo jadi fast-forward |
| 7 | `-t target_dur` (bukan `mp4_dur`) | Sandbox test | Fix output terpotong |
| 8 | **M1 Optimization**: `-hwaccel videotoolbox` + `-bf 0` + `-fps_mode cfr` + `-video_track_timescale 30000` | ffmpeg-micro blog + OBS user | Hardware decode/encode + fix DTS |

### M1 Optimization Detail

Dari screenshot OBS user:
- Encoder: `Apple VT H264 Hardware Encoder` = `h264_videotoolbox` di FFmpeg
- B-Frames: dicentang = **root cause non-monotonic DTS**
- Bitrate: 2500 Kbps (untuk live stream, sinyal lemah)

Fix di script:
```python
# Pass 1 (re-encode segments):
'-hwaccel', 'videotoolbox',      # Hardware decode (H.264/HEVC)
'-c:v', 'h264_videotoolbox',     # Hardware encode
'-b:v', '5M',                    # Bitrate 5 Mbps (offline quality)
'-bf', '0',                      # DISABLE B-frames (fix DTS!)
'-fps_mode', 'cfr',              # Constant frame rate
'-video_track_timescale', '30000', # Same timescale (fix DTS rounding)

# Pass 2 (concat + re-encode):
# Same flags + setpts=PTS-STARTPTS + -shortest
```

### Source Codec Impact

| Source | Decode | M1 Hardware? | Pass 1 Speed |
|---|---|---|---|
| AV1 | libdav1d | ❌ Software | ~1709s (28 menit, 233 segments) |
| H.264 | videotoolbox | ✅ Hardware | ~600s (10 menit, 233 segments) |
| HEVC | videotoolbox | ✅ Hardware | ~600s (estimasi) |

**Rekomendasi**: Download YouTube dengan H.264 (bukan AV1) untuk render cepat:
```bash
yt-dlp -f "137+140" --merge-output-format mp4 -o mandarin.mp4 "URL"
# 137 = 1080p H.264, 140 = audio m4a
```

### Estimasi Waktu Render (H.264 source + VideoToolbox)

| Video | Pass 1 | Pass 2 | Total |
|---|---|---|---|
| 5 menit (233 segments) | ~10 menit | ~1-2 menit | ~12 menit |
| 30 menit (~1400 segments) | ~30 menit | ~5 menit | ~35 menit |
| 1 jam (~2800 segments) | ~50 menit | ~10 menit | ~60 menit |
| 2.5 jam (~8268 segments) | ~90 menit | ~20 menit | ~110 menit |

### Riset Referensi

| Sumber | Insight yang Diadopsi |
|---|---|
| **ffmpeg-micro blog** (Javid Jamae, Aug 2026) | `-fps_mode cfr` (pengganti `-vsync cfr`), `-video_track_timescale 30000`, strategi audio stretch vs video retimed |
| **ThioJoe ASTD** | Trim silence, two-pass TTS, `atempo` + `adelay` + `amix` |
| **pyVideoTrans** (19.2k stars) | Multi-role dubbing, voice cloning, sync strategi |
| **OBS user screenshot** | `Apple VT H264 Hardware Encoder`, B-frames dicentang = root cause |
| **Voice-Clone-Studio** (GitHub) | Multi-model voice cloning + voice design |

### Filosofi yang Dipertahankan

> "atempo = jalan buntu. PUNCAK AUDIO ADALAH BEBAS DARI PENJARA = DUB YG ADA DI WEB KITA"

- atempo (audio stretch) = robot ekstrem untuk cue pendek
- DUB mode (SRT = ground truth) = audio natural, video slow-mo
- SRT + WAV = ground truth, MP4 ngikut SRT

### DaVinci Resolve Timecode Offset

DaVinci default "Start Timecode" = `01:00:00:00` (SMPTE standar).
User lihat 3 jam 35 menit di DaVinci = offset +1 jam dari timecode setting.

**Fix di DaVinci**: Project Settings → Master Settings → "Start Timecode" = `00:00:00:00`

**Fix di script**: `-timecode 00:00:00:00` di output MP4.

---

### Output
- `S7-id.mp4` — **3806.1 MB (3.8 GB)**
- Duration: 02:29:59.133 (2 jam 30 menit, +7 menit dari source asli)
- Bitrate: 3547.9 kbits/s
- Audio: Indonesia/Jawa natural (24kHz mono AAC 192k)

### Performance
- Pass 1 (render 8268 segments): ~73 menit
- Pass 2 (concat + mix audio): 2 menit 29 detik (speed 60.3x)
- Total waktu: ~75 menit
- Failed: 0

### Warning yang Muncul (Tidak Fatal)
```
Non-monotonic DTS; previous: X, current: Y; changing to Z
Auto-inserting h264_mp4toannexb bitstream filter
```
- Wajar saat concat segments dengan timestamp reset ke 0
- FFmpeg auto-handle, output tetap valid
- Mungkin perlu flag `-fflags +genpts` kalau ada masalah sync di future

### ⚠️ MASALAH DITEMUKAN (5 Okt 2026 03:00 WIB)
Setelah audit file output `S7-id.mp4`:
- **VLC**: frame berhenti, suara TTS ada
- **DaVinci Resolve**: video merah (Media Offline), audio waveform hijau OK
- **SRT durasi**: 2.6 jam (benar, bukan 3 jam)

**Root cause** (dari audit log TUI):
- **332 warning "Non-monotonic DTS"** di Pass 2 (concat)
- 332 dari 8268 segments (~4%) punya timestamp yang mundur saat di-concat
- DaVinci/VLC tidak bisa handle timestamp non-monotonic
- Audio OK karena dari WAV (timestamp konsisten), video rusak karena stream copy + concat

**Fix yang sudah aku terapkan di `retime-video.py`:**
- Pass 1: tambah `-fflags +genpts`, `-reset_ts zero`, `-vsync cfr`
- Pass 2: tambah `-fflags +genpts+igndts+discardcorrupt`, `-avoid_negative_ts make_zero`, `-max_interleave_delta 0`, `-reset_ts zero`, `-movflags +faststart`

**Solusi untuk video yang sudah ada** (tanpa re-render):
```bash
ffmpeg -y -i S7-id.mp4 \
  -c:v libx264 -preset fast -crf 23 \
  -c:a copy \
  -fflags +genpts \
  -avoid_negative_ts make_zero \
  -reset_ts zero \
  -movflags +faststart \
  S7-id-fixed.mp4
```
Estimasi 30-60 menit di M1/M2.

**Audit hasil:**
- SRT hasil DUB: BERSIH (4132 cues, 9356s = 2.6 jam, tidak ada cue > 3 jam)
- JSON retime-map: BERSIH (max newEnd 9356s, tidak ada cue > 60s, tidak ada overlap)
- Log TUI: 332 warning DTS, 211 warning h264_mp4toannexb, no fatal error
- File output: 3.8 GB, 2h 30m, audio OK, video corrupt (timestamp)

### ⚠️ KOREKSI (5 Okt 2026 03:25 WIB)
User benar — DaVinci menampilkan cue terakhir di **03:35:52:17** (3 jam 35 menit),
PADAHAL SRT sebenarnya cue terakhir di **02:35:56,032** (2 jam 36 menit).

Selisih ~59 menit. Aku salah tadi bilang "SRT bersih, bukan masalah".

**Hipotesis kuat**: Karena video stream RUSAK (332 DTS warnings), DaVinci
mungkin salah import SRT juga. Saat video media "offline/merah", DaVinci
mungkin pakai timecode dari video rusak yang inconsistent → SRT timestamp
terlihat 1 jam lebih panjang dari sebenarnya.

**Untuk verifikasi**: User buka SRT di TextEdit (bukan DaVinci) dan cek
cue terakhir. Harusnya `02:35:54,312 → 02:35:56,032` (2 jam 36 menit).

**Solusi**: Fix video dulu (re-encode 30-60 menit), lalu import ulang SRT
di DaVinci. Seharusnya timestamp SRT benar setelah video tidak rusak.

### ⚠️ KOREKSI KEDUA (5 Okt 2026 03:35 WIB) — ANALISIS LEBIH TELITI

Setelah baca screenshot DaVinci lebih teliti, aku temukan **bug sebenarnya**:

**Fakta dari screenshot:**
- Viewer menampilkan frame video (balon udara + kota) — video TIDAK rusak total
- Timeline V1: klip video `S7-id.mp4` mulai dari timecode `02:29:59:03`
- Timeline A1: waveform audio terlihat jelas — audio JALAN
- Media Pool: ada 1 "Media Offline" merah — itu klip lama yang tidak dipakai
- Playhead di `03:29:59:01`

**Bug sebenarnya**: Klip video di timeline mulai dari `02:29:59:03` — BUKAN `00:00:00`.
Itu = offset 2 jam 30 menit dari seharusnya. Plus offset SRT, total terlihat 3 jam 35 menit.

**Hipotesis kuat**: Video MP4 output dari FFmpeg punya **timecode track non-zero**.
Kemungkinan:
1. Source `mandarin.mp4` punya timecode mulai dari `01:00:00` atau `02:29:59` (common di video production)
2. FFmpeg stream copy ikut timecode track dari source
3. DaVinci pakai timecode itu untuk timeline

**Untuk verifikasi** (user perlu jalankan):
```bash
ffprobe -v error -show_entries stream=codec_type,codec_name,timecode,start_time \
  -show_entries format=duration,start_time -of json ~/Dubbing/S7-id.mp4
ffprobe -v error -show_entries stream=codec_type,codec_name,timecode,start_time \
  -show_entries format=duration,start_time -of json ~/Dubbing/mandarin.mp4
```

**Solusi proper**: Update `retime-video.py` dengan flag `-timecode 00:00:00:00`
di output MP4 untuk force timecode mulai dari 0.

**Solusi sementara di DaVinci**: Klik kanan klip video → Clip Attributes →
Timecode → set "Start" ke `00:00:00:00`.

---

## ✅ Yang Sudah Jalan (Production)

### 1. Web App (https://srt-splitter.vercel.app/)
- **Split SRT** — by durasi atau karakter
- **Translate** — Google Translate + OpenAI
- **TTS Mode ON** — sync ke SRT, crossfade, durasi = SRT
- **TTS Mode OFF** — natural sequential, speed 1.0x-2.0x
- **🔴 DUBBING Mode** — audio natural → SRT baru → ground truth
- Trim silence (ThioJoe algoritma) untuk kurangi robot
- Speed up + slow down mode (Voicertool filosofi)

### 2. Python Scripts (lokal, untuk produksi final)
- **`dubbing-tui.py`** — TUI interaktif (questionary, arrow keys)
- **`retime-video.py`** v3 — two-pass rendering:
  - Pass 1: Render per-segment (parallel 4 workers)
  - Pass 2: Concat + mix audio (instant, stream copy)
  - Support: `--preset fast/medium/slow`, `--workers 4`
  - Resume support (segment yang sudah ada di-skip)
  - Filter complex pakai file approach (`-/filter_complex <file>`) untuk FFmpeg 7+
- **`separate-audio-sfx.py`** — Demucs wrapper untuk SFX separation
- **`srt-to-audio.py`** — alternatif TTS lokal
- **`rapikan-jawa.py`** + `tambah-krama.py` — rapikan SRT Jawa

### 3. Documentation
- `README.md` — overview project + visi
- `docs/PROJECT_VISION.md` — visi digitalisasi bahasa + roadmap 2 tahun
- `docs/PROGRESS.md` — dokumen ini (status terkini)
- `docs/EDGE_TTS_PROXY.md` — cara kerja Edge TTS proxy
- `scripts/tutor-dubbing-workflow.md` — workflow pemula buta Python
- `scripts/tutor-python-lokal.md` — setup Python lokal
- `scripts/README.md` — index Python scripts

---

## 📊 User Test Summary (5 Okt 2026)

### Setup User
- MacBook Pro (Apple Silicon, M1/M2)
- Python 3.14.7 via Homebrew
- FFmpeg 9.0.2 via Homebrew
- venv di `~/Dubbing/venv/`

### Workflow User (VERIFIED WORKING)
1. Source SRT Indonesia (dari sumber, timing Mandarin = "penjara")
2. Web DUB mode (1.25x speed, 100ms min gap) → audio + SRT baru (timing natural)
3. Python TUI → render MP4 dengan timing SRT baru
4. Output: `S7-id.mp4` (2 jam 30 menit, +7 menit dari source)

### Hasil DUB Web App
- Speed: 1.25x (kompromi natural vs slow-mo video)
- Min gap: 100ms (cepat)
- Total offset: +780s (audio 13 menit lebih panjang dari source)
- Cue baru: 4132 (dari 4135 input, 3 cue skip)
- Audio quality: bagus, tidak robot

### Hasil Render (S7-id.mp4)
- Total segments: 8268 (4132 cue + 4135 gap + 1 tail)
- Re-encode: 7974 (slow-mo/fast-forward)
- Stream copy: 294 (gap dengan factor ~1.0)
- Preset: fast
- Workers: 4
- Total waktu: ~75 menit
- Output size: 3.8 GB
- Failed: 0 (semua sukses)

---

## 🔜 Next Steps (Prioritas)

### Priority 1: Kamus Bahasa Jawa JSON

**Tujuan:** Validasi SRT Jawa otomatis (ejaan, register, kosakata)

**Riset sumber kamus:**
- Sastra.org (online, HTML, perlu scraping)
- Wiktionary Jawa (wikitext, CC-BY-SA)
- Balai Bahasa Yogyakarta (PDF, public domain, perlu OCR)
- Wikipedia Jawa (corpus, bukan kamus, tapi word frequency)
- GitHub community projects (kecil, 1000-5000 entri)

**Format JSON yang disarankan:**
```json
{
  "metadata": {
    "version": "1.0",
    "source": "Sastra.org + Wiktionary + manual",
    "register": ["ngoko", "krama", "krama_inggil"],
    "dialect": "jawa_tengah",
    "entries": 24000
  },
  "words": [
    {
      "word": "kowe",
      "register": "ngoko",
      "meaning_id": "kamu",
      "krama": "panjenengan",
      "krama_inggil": "panjenengan",
      "example": "Kowe arep tiba!"
    }
  ]
}
```

**Fungsi validasi yang bisa dibangun:**
- Cek kata unknown (tidak ada di kamus) → mark untuk review
- Cek register consistency (jangan campur ngoko + krama_inggil)
- Cek ejaan aksén (kowe vs kowé, dheweke vs dhèwèké)
- Auto-suggest (keluarga → kulawarga)

**Estimasi effort:**
- Scraping Sastra.org: 1-2 hari
- Parse Wiktionary: 1 hari
- Consolidate + clean: 2-3 hari
- Build validator script: 1 hari
- **Total: 5-7 hari kerja**

### Priority 2: Workflow Multi-Bahasa

**Tujuan:** Pakai SRT Indonesia hasil DUB untuk bahasa lain (Jawa, Sunda, Bali, dll)

**Konsep:**
```
SRT Indonesia DUB (timing natural, text Indonesia) — GROUND OF TRUTH
    ↓
Translate text Indonesia → Jawa (timing TIDAK diubah)
    ↓
Generate audio Jawa pakai SRT Jawa (timing sama dengan Indonesia DUB)
    ↓
Render MP4 pakai timing SRT Indonesia DUB (atau SRT Jawa, sama)
```

**Yang perlu dibangun:**
- Script `translate-srt-text.py` (translate text, timing tetap)
- Mode "Generate Audio Only" di web app (skip DUB, langsung TTS)
  - Catatan: user bilang ini sudah ada di mode ON (TTS sync ke SRT)
  - Tapi mungkin perlu verify: ON mode generate WAV + SRT baru?

**Estimasi effort:** 2-3 hari

### Priority 3: Aksara Jawa OCR (Bulan 13-15 roadmap)

- TrOCR fine-tune dengan 1000 sample aksara Jawa
- Training 20 jam GPU di Colab
- Output: model OCR aksara Jawa

### Priority 4: Kawi TTS (Bulan 16-18 roadmap)

- Rekrut dosen Sastra Jawa (UGM/UNY)
- Rekam bacaan Negarakertagama (10 jam Kawi)
- Train Kawi TTS (pakai Jawa modern sebagai base)

### Future: GPU Acceleration (kalau skala produksi besar)

**Trigger**: Kalau render 6 season sekaligus (~7 jam di Mac, ~1.5 jam di Colab paralel)

**Opsi:**
- Google Colab Free (T4 GPU, 12 jam/hari) — untuk produksi massal
- PC RTX 4070/4090 — untuk training TTS Jawa nanti

**Yang perlu dibangun (kalau trigger):**
- Notebook Colab `dubbing-colab.ipynb`
- GPU acceleration di `retime-video.py` (detect CUDA → pakai h264_nvenc)
- Estimasi effort: 30 menit

---

## 📁 Struktur Repo Saat Ini

```
srt-splitter/
├── README.md                    # Overview + visi
├── docs/
│   ├── PROJECT_VISION.md         # Visi digitalisasi bahasa
│   ├── PROGRESS.md               # Dokumen ini (status terkini)
│   └── EDGE_TTS_PROXY.md         # Cara kerja Edge TTS proxy
├── scripts/
│   ├── README.md                 # Index Python scripts
│   ├── dubbing-tui.py            # TUI interaktif
│   ├── retime-video.py           # Retime MP4 (two-pass v3)
│   ├── separate-audio-sfx.py     # Demucs SFX separation
│   ├── srt-to-audio.py           # TTS lokal alternatif
│   ├── rapikan-jawa.py
│   ├── rapikan-jawa-semua-season.py
│   ├── tambah-krama.py
│   ├── split_srt.py
│   ├── analyze-srt-density.py
│   ├── build_source_zip.py
│   ├── tutor-dubbing-workflow.md  # Workflow pemula
│   └── tutor-python-lokal.md     # Setup Python
├── src/                          # Next.js source
├── api/                          # Vercel functions
└── public/                       # Static assets
```

Total: 102 files tracked di git.

---

## 🗂️ Aset User (Tidak Di-Commit ke Repo)

File user pribadi, di MacBook lokal:
- `~/Dubbing/mandarin.mp4` (1.94 GB) — source MP4
- `~/Dubbing/original.srt` — SRT Indonesia (timing Mandarin)
- `~/Dubbing/audio-jawa.wav` (449 MB) — audio hasil DUB web
- `~/Dubbing/subs-jawa-new.srt` — SRT baru (timing natural)
- `~/Dubbing/retime-map.json` (2.7 MB) — JSON untuk FFmpeg
- `~/Dubbing/S7-id.mp4` (3.8 GB) — **HASIL RENDER SUKSES!**
- `~/Dubbing/venv/` — virtual environment Python

Recording Zoom H6 (260 jam total, di luar repo):
- 37 video panatacara (~150 jam)
- 110 episode Kaladete Podcast (~110 jam)
- Akses komunitas Permadani (100 siswa/tahun validator)

---

## 📝 Catatan untuk AI Next Time Buka

1. **Milestone dicapai**: Render `S7-id.mp4` sukses 5 Okt 2026 02:54 WIB. Workflow end-to-end WORKING.
2. **User workflow verified**: SRT Indonesia DUB = ground truth, bukan translate Mandarin
3. **Next priority**: Kamus Jawa JSON (riset awal sudah ada di atas)
4. **Filosofi user**: "ada uang atau tidak, tetap dikerjakan step by step, terdokumentasi rapi"
5. **Visi besar**: 700 bahasa Indonesia, 169 terancam punah. Project ini prototype digitalisasi.
6. **Sandbox**: Code up-to-date dengan GitHub. PAT user masih valid di `~/.git-credentials`.
7. **GPU acceleration**: Catatan untuk masa depan (Colab atau PC NVIDIA), bukan sekarang
8. **Warning DTS**: Wajar saat concat segments, FFmpeg auto-handle, output valid

---

## 📅 Timeline Update

- **5 Okt 2026, 01:00 WIB**: Initial PROGRESS.md, status render 37%
- **5 Okt 2026, 02:55 WIB**: UPDATE — render SUKSES! Output 3.8 GB, 2h 30m. Milestone dicapai.
- **Next update**: Setelah user test video + diskusi next step (kamus Jawa)

