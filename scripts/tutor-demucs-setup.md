# Demucs SFX Separator — Setup & Workflow untuk MacBook M1 16GB

Panduan install + operasikan Demucs di M1 dengan MPS (Metal Performance Shaders) acceleration.

---

## 📌 Kenapa Demucs?

Audio ori MP4 drama Mandarin punya:
- **Vocals Mandarin** (dialog asli — akan dibuang)
- **SFX/backsound** (musik, efek, ambience — akan dipertahankan)

Tanpa Demucs, `mix-audio-dub.py` mix audio ori MP4 + dub → saat hening, **Mandarin vocals masih kedengaran**.

Dengan Demucs:
- `no_vocals.wav` = SFX bersih (musik + efek, tanpa Mandarin vocals)
- Mix dengan dub → hasil profesional, Mandarin hilang total

---

## 🛠️ Setup Sekali Pakai (~5 menit)

### Step 1: Buka Terminal + buat venv

```bash
# Bikin folder Dubbing kalau belum ada
mkdir -p ~/Dubbing
cd ~/Dubbing

# Bikin venv (virtual environment)
python3 -m venv venv

# Aktifkan venv (prompt berubah jadi (venv) di kiri)
source venv/bin/activate
```

Setelah aktif, prompt terminal jadi:
```
(venv) macbookpro@MacBooks-MacBook-Pro-4 Dubbing %
```

### Step 2: Install Demucs + questionary (di venv)

```bash
# Pastikan venv aktif (lihat (venv) di kiri prompt)
pip3 install demucs questionary
```

Tunggu 3-5 menit (download PyTorch + Demucs ~500MB).

### Step 3: Cek install sukses

```bash
demucs --help
python3 -c "import torch; print('MPS available:', torch.backends.mps.is_available())"
```

**Hasil yang diharapkan:**
```
MPS available: True
```

Kalau `MPS available: True` → M1 GPU acceleration siap.
Kalau `False` → fallback ke CPU (lebih lambat, tapi tetap jalan).

### Step 4: Download TUI script

```bash
curl -L -o demucs-tui.py https://raw.githubusercontent.com/emailnyamahmud-afk/srt-splitter/main/scripts/demucs-tui.py
curl -L -o mix-audio-dub.py https://raw.githubusercontent.com/emailnyamahmud-afk/srt-splitter/main/scripts/mix-audio-dub.py
```

### ✅ Setup Selesai

Cek folder:
```bash
ls ~/Dubbing
# Harus muncul: venv/  demucs-tui.py  mix-audio-dub.py
```

---

## 🚀 Operasional (setiap kali mau pakai)

### Step 1: Aktifkan venv

```bash
cd ~/Dubbing
source venv/bin/activate
```

**PENTING**: venv HARUS aktif (lihat `(venv)` di kiri prompt) sebelum jalankan Demucs.
Kalau tidak aktif, `demucs` command tidak akan ditemukan.

### Step 2: Jalankan Demucs TUI

```bash
python3 demucs-tui.py
```

Ikuti 6 step di layar (arrow keys, Enter):
1. Pilih file MP4/audio ori (mis. `mp4-ori-test-7min.mp4`)
2. Output directory (default: `./output`)
3. Model: `htdemucs` (default, cepat) atau `htdemucs_ft` (kualitas terbaik)
4. Mode: `two-stems vocals` (★ rekomendasi untuk dubbing)
5. Device: `mps` (★ auto-detect Apple Silicon)
6. Konfirmasi → Enter untuk mulai

### Step 3: Tunggu proses

| Audio durasi | MPS (M1 GPU) | CPU (fallback) |
|---|---|---|
| 7.5 menit | ~2-3 menit | ~5-8 menit |
| 30 menit | ~7-10 menit | ~20-30 menit |
| 90 menit | ~20-30 menit | ~60-90 menit |
| 2.5 jam | ~50-75 menit | ~150-200 menit |

M1 16GB unified memory = GPU langsung akses RAM, no bottleneck. Estimasi di atas untuk M1 16GB.

### Step 4: Cek output

```bash
ls output/htdemucs/mp4-ori-test-7min/
# Harus muncul:
# no_vocals.wav  (SFX bersih, tanpa Mandarin vocals — PAKAI INI)
# vocals.wav     (Mandarin vocals asli — BUANG)
```

### ✅ Demucs Selesai

`no_vocals.wav` = SFX bersih, siap di-mix dengan audio dub.

---

## 🎬 Workflow Lengkap (Demucs + Web + Mix)

```
Fase 0: Demucs SFX separation (opsional, untuk SFX bersih)
  (venv) python3 demucs-tui.py
  → output/htdemucs/{namafile}/no_vocals.wav (SFX bersih)

Fase 1: Web app (mode ON + Smart Fit)
  https://srt-splitter.vercel.app/
  Upload srt-id-original.srt → mode ON + Smart Fit (cap 2.0x) + pitch (-15Hz laki)
  → audio-id-dub.wav (dialog Indonesia/Jawa, 100% sync SRT ori)

Fase 2: Python mix (~10 detik)
  (venv) python3 mix-audio-dub.py \
    --mp4 mp4-ori-test-7min.mp4 \
    --audio-dub audio-id-dub.wav \
    --sfx-wav output/htdemucs/mp4-ori-test-7min/no_vocals.wav \
    --output mp4-id-final.mp4 \
    --ducking 12
```

### Output: `mp4-id-final.mp4`
- Video: 100% ori (stream copy, tidak di-retim)
- SFX: dari Demucs `no_vocals.wav` (bersih, tanpa Mandarin vocals)
- Dialog: dari web app (Smart Fit, pitch -15Hz, 100% sync)
- Ducking: SFX di-duck 12dB saat dialog bicara

---

## 📊 M1 16GB Performance

### Demucs (htdemucs, two-stems vocals)

| Audio | CPU | MPS | Speedup |
|---|---|---|---|
| 7.5 menit | 5-8 menit | **2-3 menit** | 2.5x |
| 30 menit | 20-30 menit | **7-10 menit** | 3x |
| 90 menit | 60-90 menit | **20-30 menit** | 3x |
| 2.5 jam | 150-200 menit | **50-75 menit** | 3x |

### Memory usage (M1 16GB unified)

| Mode | RAM | GPU | Status |
|---|---|---|---|
| htdemucs (CPU) | ~4-6 GB | 0 | OK 16GB |
| htdemucs (MPS) | ~2-3 GB | ~4-6 GB | OK 16GB |
| htdemucs_ft (MPS) | ~3-4 GB | ~6-8 GB | OK 16GB (batas) |
| Full 4-stems (MPS) | ~3 GB | ~6 GB | OK 16GB |

M1 16GB cukup untuk semua mode. Tidak perlu chunking audio.

### Mix-audio-dub.py

| Audio | Waktu | Memory |
|---|---|---|
| 7.5 menit | ~10 detik | <1 GB |
| 2.5 jam | ~30 detik | <1 GB |

Mix pakai FFmpeg sidechain compression, ringan. Video stream copy (no re-encode).

---

## ❓ FAQ

### Q: Kenapa harus pakai venv?

**A:** Demucs butuh PyTorch + dependencies besar (~500MB). venv isolasi supaya tidak konflik dengan Python sistem Mac. Tanpa venv, `pip3 install` bisa ditolak macOS ("externally-managed-environment").

### Q: Bagaimana cara keluar dari venv?

```bash
deactivate
```

Prompt kembali normal (tanpa `(venv)`).

### Q: Bagaimana cara update Demucs?

```bash
source venv/bin/activate
pip3 install --upgrade demucs
```

### Q: MPS error / crash, apa solusi?

Fallback ke CPU:
```bash
python3 demucs-tui.py
# Step 5: pilih 'cpu' (bukan 'mps')
```

Atau command langsung:
```bash
demucs --device cpu --two-stems vocals -n htdemucs -o output mp4-ori-test-7min.mp4
```

### Q: Audio terlalu panjang, memory habis?

M1 16GB seharusnya cukup untuk audio 2.5 jam. Tapi kalau crash:
1. Split audio jadi chunk 30-60 menit
2. Jalankan Demucs per chunk
3. Concat hasil `no_vocals.wav` dengan FFmpeg

### Q: Model mana yang terbaik?

| Model | Kualitas | Kecepatan | Cocok untuk |
|---|---|---|---|
| `htdemucs` | Bagus | Cepat | Default, produksi cepat |
| `htdemucs_ft` | Terbaik | 2x lebih lambat | Final production, kualitas max |
| `mdx` | Menengah | Paling cepat | Test cepat, prototype |

Untuk produksi drama: `htdemucs` cukup. Untuk hasil terbaik: `htdemucs_ft`.

### Q: Kalau tidak install Demucs, apa dampaknya?

`mix-audio-dub.py` tetap jalan tanpa Demucs, tapi pakai audio ori MP4 (dengan Mandarin vocals). Saat hening, Mandarin vocals masih kedengaran. Untuk hasil profesional, pakai Demucs.

---

## 🆘 Troubleshooting

### Error: `command not found: demucs`

Venv belum aktif. Jalankan:
```bash
source venv/bin/activate
```
Pastikan `(venv)` muncul di kiri prompt.

### Error: `No module named 'torch'`

Install ulang di venv:
```bash
source venv/bin/activate
pip3 install torch torchaudio
```

### Error: `MPS not available`

M1/M2/M3 seharusnya support MPS. Cek:
```bash
python3 -c "import torch; print(torch.backends.mps.is_available())"
```
Kalau `False`, fallback ke CPU. Tidak masalah, hanya lebih lambat.

### Error: `externally-managed-environment` saat pip install

Mac blocked pip install. Pakai venv (sudah ada di setup), atau:
```bash
pip3 install demucs --break-system-packages
```

### Demucs proses terlalu lama

1. Pakai model `htdemucs` (bukan `htdemucs_ft`)
2. Pakai device `mps` (bukan `cpu`)
3. Split audio jadi chunk kalau > 90 menit

---

## 📁 Struktur Folder Setelah Workflow

```
~/Dubbing/
├── venv/                                    # Python virtual environment
├── demucs-tui.py                           # TUI Demucs separator
├── mix-audio-dub.py                        # Mix SFX + dub
├── mp4-ori-test-7min.mp4                   # MP4 source (7:30, H.264)
├── srt-id-original.srt                     # SRT Indonesia source (160 cues)
├── audio-id-dub.wav                        # Audio dub (dari web app, mode ON + Smart Fit)
├── output/                                  # Output Demucs
│   └── htdemucs/
│       └── mp4-ori-test-7min/
│           ├── no_vocals.wav                # SFX bersih (PAKAI INI)
│           └── vocals.wav                  # Mandarin vocals (BUANG)
└── mp4-id-final.mp4                        # HASIL AKHIR (video ori + SFX bersih + dialog dub)
```

---

## 📅 Versi Dokumen

- Versi 1.0 — 5 Oktober 2026 (Demucs TUI + M1 16GB setup + workflow lengkap)
