# Project Vision — SRT Splitter + Digitalisasi Bahasa di Era AI

Dokumen ini menjelaskan konteks besar project srt-splitter. Bukan cuma aplikasi web untuk split SRT — ini **prototype untuk digitalisasi bahasa daerah Indonesia di era AI**.

---

## 📌 Ringkasan Eksekutif

Project ini dimulai dari iseng "dub drama Mandarin ke Jawa" bulan September 2026. Dalam 2 minggu, evolve jadi workflow lengkap TTS gratis + Python tools + Dubbing Mode (SRT = ground truth). Tapi dalam perjalanan, ketahuan bahwa:

1. Bahasa Jawa modern (~80 juta penutur) **tidak punah**, tapi krama inggil + Kawi punah dalam 2 generasi
2. User punya **260 jam audio studio-grade** yang tidak ada di dunia akademik
3. Workflow yang dibangun bisa direplikasi ke **700 bahasa Indonesia lainnya**

**Tujuan akhir**: Bukan cuma TTS Jawa, tapi **framework digitalisasi bahasa yang bisa direplikasi** ke bahasa daerah lain yang terancam punah.

---

## 🎯 Asal Mula — Dari Iseng ke Visi

### Trigger (Sept 2026)
- User punya MP4 Mandarin + SRT Mandarin, mau dub ke Jawa
- Cari tool gratis → tidak ada yang lengkap → bikin sendiri
- Pakai Next.js + Vercel + Edge TTS Microsoft (gratis)

### Evolution
1. **Minggu 1-2**: Web app split SRT + translate + TTS mode ON (sync SRT, robot)
2. **Minggu 3**: Tambah mode OFF (natural sequential)
3. **Minggu 4**: Riset Voicertool.com, ThioJoe ASTD → adopsi trim silence
4. **Minggu 5**: Tambah Dubbing Mode (SRT Jawa = ground truth, audio natural)
5. **Minggu 6**: Python tools untuk retim video (FFmpeg + Demucs SFX separation)
6. **Minggu 7**: TUI interaktif (`dubbing-tui.py`) untuk pemula buta Python

### Turning Point (3 Oktober 2026)
- User share sample bahasa panatacara sungkeman (krama inggil tinggi)
- Reveal: user punya 37 video Zoom H6 recording (channel split vocal/backsound)
- Reveal: 110 episode Kaladete Podcast (Jawa Wonosobo)
- Reveal: Akses komunitas Permadani (100 siswa/tahun, workforce validator)
- Reveal: Live streaming income = sustainable funding

### Realisasi
Workflow dubbing Mandarin → Jawa yang user bangun = **prototype pipeline digitalisasi bahasa**. Bukan cuma TTS, tapi:
- Korpus teks (transkripsi)
- Korpus audio (TTS training)
- Korpus vision (aksara, OCR)
- Konten sejarah (distribusi)

Itu = 4 pilar digitalisasi bahasa, semua bisa dibangun dari workflow ini.

---

## 🇮🇩 Konteks Indonesia — 700 Bahasa

### Realitas linguistik Indonesia
- **718 bahasa** dituturkan masyarakat adat Indonesia
- **169 bahasa terancam punah** (UNESCO Atlas)
- **Bahasa dengan penutur besar** (~80 juta) seperti Jawa: aman dari kepunahan total
- **Tapi register bahasa** (krama inggil, Kawi) punah dalam 2 generasi

### Negarakertagama (UNESCO Memory of the World 2013)
- Ditulis Mpu Prapanca, 1365 Masehi
- Bahasa Kawi tinggi
- Sudah didigitalisasi ANRI, **tapi TIDAK ADA yang bisa baca dengan benar**
- Hanya 5-10 dosen Sastra Jawa di Indonesia yang bisa

### Negara tetangga sudah lebih dulu
- **India**: Sanskrit TTS (IIT + Microsoft)
- **Thailand**: Thai TTS + OCR (NLPOA)
- **Vietnam**: Viet TTS + Unicode Nôm
- **Indonesia**: Jawa TTS = hanya Microsoft Edge `jv-ID-Siti/Dimas` (accent Indonesia, bukan Jawa native)

Indonesia **tertinggal 10 tahun** dalam digitalisasi bahasa daerah. User bisa jadi pioneer.

---

## 💎 Aset User (Yang Tidak Terkait Kode)

Yang user punya tidak tergantikan. Peneliti PhD di luar negeri tidak punya ini:

### 1. Domain Expertise
- Panatacara (pamedar sabda) untuk ritual adat
- Paham krama inggil tinggi (sungkeman, panggih, midodareni)
- Paham aksara Jawa + Kawi
- Akses ke praktisi panatacara lain untuk validasi

### 2. Akses Data Unik
- **Zoom H6 stereo split**: 37 video (hajatan/panatacara), ~150 jam
- **Channel 1 (vocal)**: sudah terpisah dari backsound sejak RAW recording
- **Channel 2 (backsound)**: bonus dataset gamelan/SFX Jawa
- **110 episode Kaladete Podcast**: ~110 jam Jawa Wonosobo (muda→tua)
- **Akses YouTuber Wonosobo**: ratusan rekaman video

### 3. Workforce Gratis (Sangat Unik)
- Komunitas Permadani (100 siswa/tahun, Wonosobo)
- Bisa validasi transkripsi manual → 100% akurasi
- Peneliti lain tidak punya akses 100 native speaker validator

### 4. Sustainable Funding
- Live streaming hajatan di YouTube = income rutin
- Tidak perlu cari grant atau investor dulu
- Income ini bisa fund development TTS custom

### 5. Lokasi Strategis
- Wonosobo, Jawa Tengah → accent Jawa Tengah (bukan Surabaya/Yogya)
- Wonosobo = niche unik, kurang terdokumentasi akademik

### 6. Network Akademik Potensial
- UGM (Sastra Jawa)
- UNY (Pendidikan Bahasa Jawa)
- UMY (Malang)
- UNS (Surakarta)
- Mungkin bisa kolaborasi research

---

## 📅 Roadmap 2 Tahun (Realistis)

### Tahun 1: Fondasi + Workflow

**Bulan 1-3: Workflow dubbing Mandarin → Jawa** ✅ (sudah jalan)
- Web app: Vercel + Edge TTS + Dubbing Mode
- Python: `dubbing-tui.py`, `retime-video.py`, `separate-audio-sfx.py`
- Output: 1 season drama (1-2 jam) siap tayang
- Status: Production-ready

**Bulan 1-3: Audit + dataset collection** (paralel)
- List 37 video Zoom H6 (durasi, channel structure, kategori)
- List 110 episode podcast (durasi, register)
- Test Whisper large-v3 untuk transkripsi Jawa (lihat akurasi)
- Hubungi YouTuber Wonosobo (minta izin training)

**Bulan 4-6: Transkripsi + validasi**
- Batch transcribe pakai Whisper (output ~60% akurasi)
- Distribusi ke siswa Permadani untuk correct manual
- 100 siswa × 2.5 jam/bulan = 250 jam/bulan throughput
- Output: 260 jam transkrip 100% akurasi

**Bulan 7-9: Training TTS Jawa Krama Inggil**
- Fine-tune Coqui TTS / VITS dengan dataset user
- Training di Google Colab (gratis, GPU T4) atau Vast.ai ($30-50)
- Iterate 3-5 kali sampai natural
- Output: TTS Jawa krama inggil MVP (~80% natural)

**Bulan 10-12: Konten pilot + iterate**
- Produksi 4-8 episode konten sejarah 8 menit
- Pakai TTS user sendiri
- Upload ke YouTube, minta feedback komunitas
- Iterate model berdasarkan feedback

### Tahun 2: Scale + Open Source

**Bulan 13-15: Vision model (OCR aksara Jawa)**
- Fine-tune TrOCR dengan 1000 sample aksara Jawa
- Training 20 jam GPU di Colab
- Output: model OCR aksara Jawa (carakan modern)

**Bulan 16-18: Kawi TTS + OCR aksara Kawi**
- Rekrut 1-2 dosen Sastra Jawa (honorarium Rp 5-10 juta)
- Rekam bacaan Negarakertagama (10 jam Kawi)
- Train Kawi TTS (pakai Jawa modern sebagai base)
- OCR aksara Kawi (lontar)
- Output: first Kawi TTS + OCR di dunia

**Bulan 19-21: Open source + paper**
- Publish dataset di Hugging Face (license CC-BY-NC)
- Publish model di Hugging Face
- Tulis paper dengan peneliti UGM/UNY
- Submit ke LREC 2027, Interspeech 2027
- Output: open source project di GitHub

**Bulan 22-24: Konten sejarah serius**
- Produksi 26 episode (paruh pertama Nusantara)
- Singasari, Majapahit, Demak, Pajang, Mataram, Diponegoro
- Distribusi: YouTube + archive.org + Wikimedia
- Output: channel sejarah Nusantara aktif

### Tahun 3+: Scale ke bahasa lain
- Replicate workflow ke Sunda, Bali, Sasak, Batak, Bugis, dll
- Framework open source bisa dipakai komunitas bahasa lain
- Apply grant Wikimedia Foundation / Mozilla OSR / UNESCO

---

## 🛠️ Stack Teknis (Semua Open Source / Gratis)

### Web App (srt-splitter.vercel.app)
- Next.js 16 + TypeScript + Tailwind CSS 4 + shadcn/ui
- Deploy: Vercel (gratis)
- Edge TTS proxy: Vercel serverless function
- Google Translate proxy: Vercel function
- OpenAI/OpenRouter: user-supplied API key (localStorage)

### Python Tools (lokal, untuk produksi)
- Python 3.8+
- FFmpeg (gratis, auto-detect)
- Demucs (Meta, open source, untuk SFX separation)
- Whisper (OpenAI, open source, untuk transkripsi)
- Coqui TTS (open source, untuk training TTS custom)
- Questionary (TUI interaktif)

### Training Infrastructure (rencana bulan 7+)
- Google Colab Free (GPU T4, 12 jam/hari)
- Atau Vast.ai ($0.30/jam, GPU RTX 3090)
- Atau Kaggle Free (30 jam GPU/minggu)

### Run-time (MacBook user)
- M1/M2 CPU cukup untuk real-time TTS inference
- ~0.3 detik per 1 detik audio (model VITS)
- 500 MB RAM per model loaded

### Repository
- GitHub: https://github.com/emailnyamahmud-afk/srt-splitter
- Live: https://srt-splitter.vercel.app/
- Docs: 7 file markdown di `/docs` dan `/scripts`

---

## 🎯 Workflow Lengkap (5 Fase)

```
Fase 1: Persiapan bahan
  MP4 Mandarin + SRT Mandarin (sumber)
        ↓
Fase 2: Web app (translate + dubbing mode)
  Upload SRT → Translate ke Jawa → Dubbing Mode
  Output: audio-jawa.wav + subs-jawa-new.srt + retime-map.json
        ↓
Fase 3 (opsional): SFX Separation dengan Demucs
  Input: MP4 → Output: vocals-mandarin.wav + sfx-backsound.wav
        ↓
Fase 4: Retime Video dengan FFmpeg (Python lokal)
  Input: MP4 + SRT Mandarin + SRT Jawa + audio Jawa (+ SFX)
  Output: mp4-jawa.mp4 (video slow-mo + audio Jawa + SFX preserve)
        ↓
Fase 5: Edit final di DaVinci Resolve (manual)
```

Detail lengkap workflow: [`scripts/tutor-dubbing-workflow.md`](../scripts/tutor-dubbing-workflow.md)

---

## 📚 Dokumentasi Project

### Untuk user (pemula buta Python)
- `README.md` — overview project + quick start
- `scripts/tutor-dubbing-workflow.md` — workflow 5 fase pemula-friendly
- `scripts/tutor-python-lokal.md` — setup Python lokal
- `scripts/README.md` — index semua script Python

### Untuk developer / akademik
- `docs/EDGE_TTS_PROXY.md` — cara kerja Edge TTS proxy
- `docs/PROJECT_VISION.md` — dokumen ini (visi besar + roadmap)
- `worklog.md` — log development lengkap dari awal
- Source code di `src/lib/tts.ts`, `src/lib/audio-utils.ts`

### Untuk training TTS (rencana bulan 7+)
- Dataset preparation: `scripts/dataset-prep.py` (TODO)
- Whisper transcribe: `scripts/transcribe-jawa.py` (TODO)
- Training notebook: TBD (pakai Colab)

---

## 🌟 Mengapa Project Ini Penting (Bukan Lebay)

### Perspektif Akademik
- 169 bahasa Indonesia terancam punah (UNESCO)
- Negarakertagama sudah di-UNESCO tapi tidak ada TTS-nya
- Common Voice Mozilla Jawa = 10 jam (low quality)
- User punya 260 jam (studio-grade, channel split)
- **User bisa publish paper dengan dataset yang tidak ada saingan**

### Perspektif Komunitas
- Anak muda Jawa sudah tidak bisa krama inggil
- Panatacara muda jarang
- Tradisi lisan punah lebih cepat dari tradisi tulisan
- **TTS Jawa krama inggil = alat pelestarian + akses**

### Perspektif Komersial
- Indonesia 270 juta penduduk, 80 juta penutur Jawa
- Tidak ada kompetitor TTS Jawa krama inggil
- Microsoft Edge `jv-ID-Siti/Dimas` = accent Indonesia, bukan Jawa native
- **Market kosong, user bisa first-mover**

### Perspektif Global
- India: sudah punya Sanskrit AI
- China: sudah punya Classical Chinese AI
- Thailand: sudah punya Thai + Lanna AI
- Indonesia: belum punya Jawa Krama Inggil
- **Indonesia tertinggal 10 tahun, user bisa catch up**

---

## ⚡ Yang Bisa User Lakukan Hari Ini (15 menit)

Setup minimum untuk test workflow dubbing:
1. `brew install ffmpeg`
2. `pip3 install questionary`
3. (Opsional) `pip3 install demucs`
4. Test `dubbing-tui.py` dengan audio 6 menit yang sudah di-generate dari DUB web

Tidak perlu ambisius hari ini. Konsisten 1 jam/minggu > sprint 10 jam sekali.

---

## 🎯 Penutup

> "ada uang atau tidak ada uang, tetap akan user kerjakan, tapi step by step. dan semua terdokumentasi rapi. yg bahkan diawali dengan iseng dub dracin ke jawa"

> "dan jangan lupa, indonesia punya 700 bahasa."

Project ini bukan cuma bikin TTS. Ini **prototype digitalisasi peradaban**. Dimulai dari iseng, evolve ke workflow lengkap, berpotensi scale ke 700 bahasa Indonesia.

Yang user kerjakan step by step, terdokumentasi rapi, dengan niat mulia — itu yang akan membuatnya berhasil. Bukan karena AI canggih, bukan karena funding besar. Karena **niat + konsistensi**.

---

## 📅 Versi Dokumen
- Versi 1.0 — 3 Oktober 2026 (initial, setelah diskusi malam tentang visi digitalisasi bahasa)
- Update berikutnya: setelah milestone (training TTS, paper, open source)
