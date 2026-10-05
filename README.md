# SRT Splitter + Dubbing Jawa

Aplikasi web untuk split SRT, translate subtitle, dan **dubbing Mandarin → Jawa** dengan audio natural. 100% di browser, gratis. Workflow lengkap sampai retim video dengan FFmpeg.

**Live:** https://srt-splitter.vercel.app/
**Source:** https://github.com/emailnyamahmud-afk/srt-splitter

> **📖 Visi Project:** Bukan cuma dubbing Mandarin → Jawa. Ini prototype untuk **digitalisasi bahasa daerah Indonesia di era AI** (700 bahasa, 169 terancam punah). Lihat [`docs/PROJECT_VISION.md`](docs/PROJECT_VISION.md) untuk konteks lengkap + roadmap 2 tahun.

---

## Fitur Utama

### Web App (https://srt-splitter.vercel.app/)

| Fitur | Deskripsi |
|---|---|
| **Split SRT** | By durasi (5m-5jam) atau by karakter (max 5000) |
| **Translate** | EN→ID, ID→Jawa, Jawa→ID (gratis Google Translate atau premium OpenAI) |
| **TTS Mode ON + Smart Fit** ⭐ | Per-cue dynamic TTS speed (cap 2.0x, pitch preserved), asymmetric trim, crossfade, video = ground truth (100% sync) |
| **TTS Pitch Control** | -10Hz laki (lebih bas), +10Hz perempuan (lebih tinggi) — agar tidak "standar" |
| **TTS Mode ON Classic** | Speed up only / Speed up and slow down (Voicertool klasik) |
| **TTS Mode OFF** | Natural sequential, speed 1.0x-2.0x |
| **🔴 Dubbing Mode v2.0** | Audio natural → SRT baru → MP4 retimed (deprecated, 20x test gagal) |

### Python Scripts (lokal, untuk produksi final)

| Script | Fungsi |
|---|---|
| **`demucs-tui.py`** ⭐ | TUI Demucs SFX separation (MPS acceleration, ~1 menit untuk 7.5 menit audio) |
| **`mix-audio-dub.py`** ⭐ | Mix SFX bersih + audio dub dengan ducking sidechain (~7 detik, 0 DTS warnings) |
| `scripts/rapikan-jawa.py` | Rapikan ejaan Jawa di 1 file SRT |
| `scripts/rapikan-jawa-semua-season.py` | Rapikan semua season S1-S6 |
| `scripts/tambah-krama.py` | Tambah sentuhan krama di bagian formal |
| `scripts/srt-to-audio.py` | Generate audio dari SRT (Edge TTS, ON/OFF mode) |
| `scripts/split_srt.py` | Split SRT by durasi |
| `scripts/retime-video.py` | Retime MP4 (deprecated, 20x test gagal, backup) |
| `scripts/separate-audio-sfx.py` | Pisahkan vocals + SFX (Demucs CLI) |
| `scripts/analyze-srt-density.py` | Analisis distribusi cue + estimasi robot ratio |

---

## Workflow Dubbing Mandarin → Jawa (5 Fase)

```
Fase 1: Persiapan bahan (rename ke standar)
  mp4-ori-{name}.mp4       (MP4 source, mis. mp4-ori-test-5min.mp4)
  srt-{lang}-original.srt  (SRT source, mis. srt-id-original.srt, srt-mn-original.srt)
        ↓
Fase 2: Web app (translate + dubbing mode)
  Upload SRT ori → Translate (kalau perlu) → Dubbing Mode → Download 3 file
  Output: audio-jd-dub.wav + srt-dub.srt + retime-map.json
  Rename ke: audio-{lang}-dub.wav + srt-{lang}-dub.srt + retime-map.json
        ↓
Fase 3 (opsional): SFX Separation dengan Demucs
  Input: MP4 → Output: vocals-mandarin.wav + sfx-backsound.wav
        ↓
Fase 4: Retime Video dengan FFmpeg (Python lokal)
  Input: mp4-ori + srt-{lang}-original + srt-{lang}-dub + audio-{lang}-dub (+ SFX)
  Output: mp4-{lang}-final.mp4 (video slow-mo + audio dub + SFX preserve)
        ↓
Fase 5: Edit final di DaVinci Resolve (manual)
```

**Detail lengkap workflow:** [`scripts/tutor-dubbing-workflow.md`](scripts/tutor-dubbing-workflow.md)

**Standar nama file** (lihat tabel di `tutor-dubbing-workflow.md` Fase 1):

| File | Format nama | Contoh |
|---|---|---|
| MP4 source | `mp4-ori-{name}.mp4` | `mp4-ori-test-5min.mp4` |
| SRT source | `srt-{lang}-original.srt` | `srt-id-original.srt`, `srt-mn-original.srt` |
| SRT dub result | `srt-{lang}-dub.srt` | `srt-id-dub.srt`, `srt-jw-dub.srt` |
| Audio dub result | `audio-{lang}-dub.wav` | `audio-id-dub.wav`, `audio-jw-dub.wav` |
| Output MP4 final | `mp4-{lang}-final.mp4` | `mp4-jw-final.mp4`, `mp4-id-final.mp4` |

(di mana `{lang}` = `id` untuk Indonesia, `jw` untuk Jawa, `su` untuk Sunda, dst.)

**Estimasi waktu** untuk MP4 3 jam:
- Fase 1: 5 menit
- Fase 2: 15-30 menit (translate + dubbing)
- Fase 3: 10-20 menit (Demucs di CPU, opsional)
- Fase 4: 30-90 menit (ffmpeg render)
- Fase 5: 30-60 menit (edit manual)
- **Total: 90-180 menit**

---

## Stack Teknologi

### Web App
- Next.js 16 + TypeScript + Tailwind CSS 4 + shadcn/ui
- Deploy: Vercel (app + Edge TTS proxy + Google Translate proxy)
- Edge TTS via Vercel serverless function (`api/edge-tts.js`)
- Google Translate via Vercel function (`api/translate.js`)

### Python Scripts
- Python 3.8+
- FFmpeg (auto-detect atau specify via `--ffmpeg`)
- Demucs (opsional, untuk SFX separation): `pip install demucs`

---

## Cara Pakai

### Quick Start: Web App

1. Buka https://srt-splitter.vercel.app/
2. Upload SRT → split → download, atau translate, atau generate TTS

### Quick Start: Python Lokal (MacBook)

```bash
# Setup (sekali saja)
brew install ffmpeg
pip3 install edge-tts numpy

# Generate audio dari SRT (ON mode)
python3 scripts/srt-to-audio.py subs.srt --on --voice id-ID-GadisNeural
```

Lihat [`scripts/tutor-python-lokal.md`](scripts/tutor-python-lokal.md) untuk detail.

### Full Dubbing Workflow

Lihat [`scripts/tutor-dubbing-workflow.md`](scripts/tutor-dubbing-workflow.md) untuk panduan lengkap 5 fase.

---

## Struktur Folder

```
srt-splitter/
├── README.md                    # Dokumen ini
├── api/                         # Vercel serverless functions
│   ├── edge-tts.js              # Edge TTS proxy (Microsoft)
│   ├── translate.js              # Google Translate proxy
│   └── health.js                 # Health check
├── docs/                        # Dokumentasi teknis + visi
│   ├── PROJECT_VISION.md         # 📖 Visi digitalisasi bahasa + roadmap 2 tahun
│   └── EDGE_TTS_PROXY.md         # Cara kerja Edge TTS proxy
├── scripts/                     # Python scripts (lokal)
│   ├── README.md                 # Index script Python
│   ├── tutor-dubbing-workflow.md # Workflow lengkap dubbing
│   ├── tutor-python-lokal.md     # Setup Python lokal
│   ├── tutor-dubbing-workflow.md     # Tutor retime-video.py
│   ├── retime-video.py        # Retime MP4 ke SRT Jawa
│   ├── separate-audio-sfx.py     # SFX separation dengan Demucs
│   ├── srt-to-audio.py           # Generate audio dari SRT
│   ├── rapikan-jawa.py           # Rapikan ejaan Jawa
│   ├── rapikan-jawa-semua-season.py
│   ├── tambah-krama.py           # Tambah krama inggil
│   ├── split_srt.py              # Split SRT
│   ├── analyze-srt-density.py    # Analisis distribusi cue
│   └── build_source_zip.py       # Build source zip untuk download
├── src/                         # Next.js source code
│   ├── app/                      # App router
│   ├── lib/                      # Library (TTS, SRT parser, audio utils)
│   ├── components/               # React components
│   └── hooks/                    # Custom hooks
└── public/                       # Static assets
    ├── logo.svg
    ├── robots.txt
    └── srt-splitter-source.zip   # Source code zip untuk download
```

---

## Deploy

### Vercel (auto-deploy, default)
1. Push ke GitHub `main` branch
2. Vercel auto-deploy
3. URL: https://srt-splitter.vercel.app/

### GitHub Pages (static, optional)
- Workflow: `.github/workflows/main.yml`
- Settings → Pages → Source: GitHub Actions
- URL: https://emailnyamahmud-afk.github.io/srt-splitter/

### Lokal (dev)
```bash
bun install
bun run dev
# Buka http://localhost:3000
```

---

## Environment Variables

Tidak perlu environment variables untuk web app. Edge TTS proxy pakai hardcoded Microsoft token (gratis, no auth).

Untuk OpenAI/OpenRouter TTS, user isi API key di UI (disimpan di localStorage browser, tidak pernah dikirim ke server).

---

## License

Bebas dipakai untuk produksi sendiri. Atribusi dihargai tapi tidak wajib.

---

## Credits

Teknologi yang dipakai:
- **Edge TTS** — Microsoft neural voices (gratis, native Indonesia/Jawa)
- **Demucs** — Source separation by Meta/Facebook Research
- **FFmpeg** — Video/audio processing
- **ThioJoe ASTD** — Inspirasi trim silence + two-pass TTS
- **pyVideoTrans** — Inspirasi workflow dubbing
