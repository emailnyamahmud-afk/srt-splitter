# Progress Log — SRT Splitter + Dubbing Project

Dokumen ini catatan status project untuk AI / developer next time baca. Update setiap sesi kerja.

**Last updated:** 5 Oktober 2026, 01:00 WIB

---

## 📌 Quick Status

| Item | Status |
|---|---|
| Web app (srt-splitter.vercel.app) | ✅ Production ready |
| Dubbing Mode (SRT = ground truth) | ✅ Working, tested user |
| Python `dubbing-tui.py` (TUI) | ✅ Working, user tested |
| Python `retime-video.py` v3 (two-pass) | ✅ Working, user tested |
| Python `separate-audio-sfx.py` (Demucs) | ✅ Working (belum user test) |
| User test render S7-id.mp4 (2.5 jam) | ⏳ In progress (37% saat tulis ini) |
| Kamus Jawa JSON | 🔜 Next step (riset) |
| Workflow multi-bahasa (Jawa/Sunda/dll) | 🔜 Next step |

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

## 📊 Test User Saat Ini (5 Okt 2026)

### Setup
- MacBook Pro (Apple Silicon, M1/M2)
- Python 3.14.7 via Homebrew
- FFmpeg 9.0.2 via Homebrew
- venv di `~/Dubbing/venv/`
- File source: `mandarin.mp4` (1.94 GB, 2 jam 23 menit, 1440x2560 portrait)

### Workflow User
1. SRT Indonesia (sumber download, timing Mandarin = "penjara")
2. Web DUB mode → audio Indonesia + SRT Indonesia baru (timing natural)
3. Python TUI → render MP4 dengan timing SRT baru
4. Output: `S7-id.mp4` (2 jam 36 menit, +13 menit dari source)

### Hasil DUB Web App
- Speed: 1.25x (kompromi natural vs slow-mo video)
- Min gap: 100ms
- Total offset: +780s (audio 13 menit lebih panjang)
- Cue baru: 4132 (dari 4135 input, 3 cue skip)
- Audio quality: bagus, tidak robot

### Hasil Render (in progress saat tulis ini)
- Total segments: 8268 (4132 cue + 4135 gap + 1 tail)
- Re-encode: 7974 (slow-mo/fast-forward)
- Stream copy: 294 (gap dengan factor ~1.0)
- Preset: fast
- Workers: 4
- Progress: 3050/8268 (37%) di elapsed 1757s
- ETA: ~50 menit lagi
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
- `~/Dubbing/mandarin.mp4` (1.94 GB)
- `~/Dubbing/original.srt`
- `~/Dubbing/audio-jawa.wav` (449 MB)
- `~/Dubbing/subs-jawa-new.srt`
- `~/Dubbing/retime-map.json` (2.7 MB)
- `~/Dubbing/S7-id.mp4` (in progress)

Recording Zoom H6 (260 jam total, di luar repo):
- 37 video panatacara (~150 jam)
- 110 episode Kaladete Podcast (~110 jam)
- Akses komunitas Permadani (100 siswa/tahun validator)

---

## 📝 Catatan untuk AI Next Time Buka

1. **Jangan lupa**: User workflow sudah benar — SRT Indonesia DUB = ground truth, bukan translate Mandarin
2. **Test render user**: Sedang jalan (37% saat tulis ini), kemungkinan selesai dalam ~50 menit
3. **Next priority**: Kamus Jawa JSON (riset awal sudah ada di atas)
4. **Filosofi user**: "ada uang atau tidak, tetap dikerjakan step by step, terdokumentasi rapi"
5. **Visi besar**: 700 bahasa Indonesia, 169 terancam punah. Project ini prototype digitalisasi.
6. **Sandbox**: Code up-to-date dengan GitHub (commit `2791f98`). PAT user masih valid di `~/.git-credentials`.

---

## 📅 Timeline Update

- **5 Okt 2026, 01:00 WIB**: Initial PROGRESS.md dibuat, status render 37%
- **Next update**: Setelah render selesai + diskusi kamus Jawa
