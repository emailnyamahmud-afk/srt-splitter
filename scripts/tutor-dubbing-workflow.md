# Tutor Lengkap Dubbing Mandarin → Jawa (Untuk Pemula)

Panduan step-by-step untuk dub video Mandarin ke Jawa. Cocok untuk yang **belum pernah pakai Python** atau command line. Aku tulis dengan asumsi user cuma biasa pakai browser dan klik-klik aplikasi.

**Total waktu setup:** 15 menit (sekali pakai)
**Total waktu per video 1 jam:** ~30 menit (setelah setup)

---

## 📌 Penjelasan Singkat (Baca Dulu 2 Menit)

### Python itu bukan aplikasi klik-klik

Python itu bahasa pemrograman. Script yang aku buat (`retime-video.py`, `separate-audio-sfx.py`) jalan di **Terminal** Mac — layar hitam dengan text, ketik command, tekan Enter.

Tenang, ini cuma untuk **produksi final** (Fase 4). Untuk translate + generate audio (Fase 2), user tetap pakai web app biasa di browser.

### Apa itu file JSON yang di-download dari DUB?

Dari web app Dubbing Mode, user download 3 file (dengan prefix, mis. `Season-1`):
```
Season-1-audio-jd-dub.wav    ← Audio dub natural (diputar di video final, jd = Jawa Dub project)
Season-1-srt-dub.srt         ← Subtitle dub dengan timing baru (rename ke srt-{lang}-dub.srt)
Season-1-retime-map.json     ← PETUNJUK untuk FFmpeg: timing cue dub mana ↔ cue ori mana
```

Setelah download, rename file supaya konsisten dengan bahasa test:
- sub-ID (Indonesia): `srt-id-dub.srt`, `audio-id-dub.wav`
- sub-Jawa: `srt-jw-dub.srt`, `audio-jw-dub.wav`
- (audio boleh tetap `audio-jd-dub.wav` — jd = "Jawa Dub" project, konstanta)

**JSON tidak user buka manual.** Itu dibaca otomatis oleh Python script `retime-video.py`. User cukup taruh di folder yang sama dengan file lainnya, lalu jalankan command — JSON akan dipakai otomatis.

### Apa itu FFmpeg dan Demucs?

- **FFmpeg** = alat gratis untuk memproses video/audio (cut, slow-mo, mix). Wajib install.
- **Demucs** = alat AI dari Meta untuk memisahkan suara dialog dari backsound. Opsional (cuma kalau MP4 punya backsound yang mau dipertahankan).

---

## 🛠️ Setup Sekali Pakai (15 Menit)

### Step 1: Buka Terminal Mac

- Tekan `Cmd + Spasi` → ketik "Terminal" → Enter
- Akan muncul layar hitam dengan tulisan: `user@MacBook ~ %`
- Itu disebut "prompt" — tempat user ketik command

### Step 2: Cek Python (biasanya sudah ada)

Ketik di Terminal, lalu Enter:
```bash
python3 --version
```

**Hasil yang diharapkan:**
```
Python 3.10.x
```

Kalau muncul `Python 2.7.x` atau versi lebih rendah dari 3.10, install ulang:
- Buka https://www.python.org/downloads/mac-osx/
- Download "macOS 64-bit universal2 installer"
- Double-click install

Kalau muncul `command not found: python3`, install via Homebrew:
```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
brew install python@3.10
```

### Step 3: Install FFmpeg (wajib)

FFmpeg = alat untuk proses video. Wajib install.

```bash
# Install Homebrew dulu kalau belum ada (kopi paste semua 1 baris):
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
```

Tunggu 2-5 menit sampai selesai. Lalu ketik:
```bash
# Install FFmpeg:
brew install ffmpeg
```

Tunggu 3-10 menit (download ~50MB).

Cek sukses:
```bash
ffmpeg -version
```

Kalau muncul banyak text mulai dengan `ffmpeg version 7.x.x`, **berhasil**.

### Step 4: Install Demucs (opsional, tapi recommended)

Demucs = alat AI untuk pisahkan suara dialog dari backsound. Opsional, tapi berguna kalau MP4 punya music/SFX yang ingin dipertahankan.

```bash
pip3 install demucs
```

Tunggu 3-5 menit (download model ~80MB pertama kali dipakai).

Cek sukses:
```bash
demucs --help
```

Kalau muncul info help text, **berhasil**.

> **Catatan:** Demucs butuh Python 3.10+. Kalau install gagal, coba:
> ```bash
> pip3 install --upgrade pip
> pip3 install demucs --break-system-packages
> ```

### Step 5: Install questionary (untuk TUI interaktif — REKOMENDASI)

Library Python untuk TUI (Text User Interface) yang interaktif — pilih file pakai arrow keys, tidak perlu ketik command panjang.

```bash
pip3 install questionary
```

Cek sukses:
```bash
python3 -c "import questionary; print('OK')"
```

Kalau muncul `OK`, **berhasil**.

### ✅ Setup Selesai — Test Semua Sudah Jalan

Ketik di Terminal:
```bash
python3 --version
ffmpeg -version
demucs --help
python3 -c "import questionary; print('OK')"
```

Kalau semua perintah muncul output (tidak "command not found"), setup berhasil. Lanjut ke Fase 1.

---

## 📁 Fase 1: Siapkan Folder Kerja (5 Menit)

### Step 1: Buat folder khusus untuk dubbing

Buka Terminal, ketik (copy-paste):
```bash
mkdir -p ~/Dubbing
cd ~/Dubbing
```

Artinya: bikin folder bernama "Dubbing" di home directory, lalu masuk ke folder itu.

### Step 2: Copy file sumber ke folder Dubbing (dengan nama standar)

Standar nama file di folder Dubbing (biar tidak bingung):

| File | Format nama | Contoh |
|---|---|---|
| MP4 source | `mp4-ori-{name}.mp4` | `mp4-ori-test-5min.mp4`, `mp4-ori-S01E01.mp4` |
| SRT source (Indonesia) | `srt-id-original.srt` | timing Mandarin = "penjara" |
| SRT source (Mandarin) | `srt-mn-original.srt` | timing Mandarin = "penjara" |
| SRT dub result (dari web) | `srt-{lang}-dub.srt` | `srt-id-dub.srt`, `srt-jw-dub.srt` |
| Audio dub result (dari web) | `audio-{lang}-dub.wav` | `audio-id-dub.wav`, `audio-jw-dub.wav` |
| Output MP4 jawa | `mp4-{lang}-final.mp4` | `mp4-jw-final.mp4`, `mp4-id-final.mp4` |

Copy dari folder asli user, sambil rename ke standar:
```bash
# Copy MP4 source (ganti path sesuai lokasi user)
cp ~/Downloads/mandarin.mp4 ~/Dubbing/mp4-ori-test-5min.mp4

# Copy SRT Indonesia source (ganti path sesuai lokasi user)
cp ~/Downloads/original.srt ~/Dubbing/srt-id-original.srt
```

Cek isi folder:
```bash
ls ~/Dubbing
```

Harus muncul:
```
mp4-ori-test-5min.mp4    srt-id-original.srt
```

### Step 3: Download script Python dari GitHub

```bash
# Download retime-video.py, dubbing-tui.py, dan separate-audio-sfx.py dari repo
cd ~/Dubbing
curl -L -o retime-video.py https://raw.githubusercontent.com/emailnyamahmud-afk/srt-splitter/main/scripts/retime-video.py
curl -L -o dubbing-tui.py https://raw.githubusercontent.com/emailnyamahmud-afk/srt-splitter/main/scripts/dubbing-tui.py
curl -L -o separate-audio-sfx.py https://raw.githubusercontent.com/emailnyamahmud-afk/srt-splitter/main/scripts/separate-audio-sfx.py
```

Cek:
```bash
ls ~/Dubbing
```

Harus muncul:
```
mp4-ori-test-5min.mp4    srt-id-original.srt    retime-video.py    dubbing-tui.py    separate-audio-sfx.py
```

---

## 🌐 Fase 2: Web App (Sudah User Pahami)

### Step 1: Translate Mandarin → Jawa (opsional, kalau source = Mandarin)

1. Buka https://srt-splitter.vercel.app/
2. Upload `srt-mn-original.srt` (kalau source Mandarin) atau `srt-id-original.srt` (kalau source Indonesia)
3. Di panel Translate, pilih source `Chinese` → target `Jawa` (atau sesuai bahasa)
4. Klik Translate, tunggu 1-2 menit
5. Download hasil → simpan sebagai `srt-jw-original.srt` di folder `~/Dubbing/` (text Jawa, timing masih Mandarin = "penjara")

### Step 2: Rapikan tatabahasa Jawa (opsional)

```bash
cd ~/Dubbing
# Pakai script rapikan-jawa.py dari repo (download kalau belum ada)
curl -L -o rapikan-jawa.py https://raw.githubusercontent.com/emailnyamahmud-afk/srt-splitter/main/scripts/rapikan-jawa.py
python3 rapikan-jawa.py srt-jw-original.srt srt-jw-rapi.srt
```

### Step 3: Dubbing Mode di Web App

1. Upload `srt-jw-rapi.srt` (atau `srt-id-original.srt` untuk test sub-ID) ke web app
2. Pilih mode **🔴 DUBBING**
3. Pilih voice:
   - sub-ID test: `id-ID-GadisNeural` (perempuan) atau `id-ID-ArdiNeural` (laki-laki)
   - sub-Jawa test: `jv-ID-SitiNeural` (perempuan) atau `jv-ID-DimasNeural` (laki-laki)
4. Pilih speed:
   - **1.0x Natural** → paling natural, video slow-mo paling banyak (rekomendasi awal)
   - **1.25x** → kompromi (audio masih natural, video slow-mo kurang)
   - **1.5x** → paling sedikit slow-mo (audio agak cepat, masih jelas)
5. Klik **Generate Dubbing**, tunggu 1-3 menit per 5 menit SRT
6. Setelah selesai, klik **Download 3 file (WAV + SRT + JSON)**
7. Akan download 3 file — simpan semua di `~/Dubbing/`

### Step 4: Rename file hasil download ke standar

File dari web app akan bernama `{prefix}-audio-jd-dub.wav`, `{prefix}-srt-dub.srt`, `{prefix}-retime-map.json`. Rename supaya konsisten dengan bahasa test:

```bash
cd ~/Dubbing

# Contoh untuk sub-ID (ganti "Season" dengan prefix user, dan "id" sesuai bahasa)
mv Season-audio-jd-dub.wav audio-id-dub.wav
mv Season-srt-dub.srt     srt-id-dub.srt
mv Season-retime-map.json retime-map.json

# Contoh untuk sub-Jawa
# mv Season-audio-jd-dub.wav audio-jw-dub.wav
# mv Season-srt-dub.srt     srt-jw-dub.srt
# mv Season-retime-map.json retime-map.json
```

### ✅ Fase 2 Selesai — Cek Folder

```bash
ls ~/Dubbing
```

Harus muncul (untuk sub-ID test):
```
mp4-ori-test-5min.mp4    srt-id-original.srt    retime-video.py        separate-audio-sfx.py
srt-id-dub.srt          audio-id-dub.wav      dubbing-tui.py
retime-map.json
```

> **Catatan tentang retime-map.json:** File ini berisi petunjuk timing untuk FFmpeg (schema v2.0: chunks, fittedCues, params). User TIDak perlu buka atau baca file ini — Python script akan baca otomatis. Cukup taruh di folder yang sama.

---

## 🎬 Fase 4: Retime Video

Ada **2 cara** untuk jalankan retime video. Pilih salah satu:

### 🎯 Cara 1: Pakai TUI Interaktif (REKOMENDASI PEMULA)

TUI = Text User Interface. User pilih file pakai arrow keys, tidak perlu ketik command panjang.

```bash
cd ~/Dubbing
python3 dubbing-tui.py
```

Akan muncul menu interaktif:
```
╔══════════════════════════════════════════════════════════════════╗
║  🎬 Dubbing (TUI Mode)                                          ║
║  Workflow: MP4 + SRT ori + SRT dub + Audio dub → MP4 Final     ║
╚══════════════════════════════════════════════════════════════════╝

Step 1: Pilih file MP4 ori (mis. mp4-ori-test-5min.mp4)
┌─────────────────────────────────────────────┐
│ ❯ mp4-ori-test-5min.mp4                     │ ← arrow ↑↓ navigasi
│   mp4-ori-S01E01.mp4                         │
│   ~/Downloads/movie-3jam.mp4                │
│   [Ketik path manual]                       │
└─────────────────────────────────────────────┘
  ↑↓ Navigasi  Enter Konfirmasi
```

Ikuti 8 step di layar:
1. Pilih MP4 ori (mis. `mp4-ori-test-5min.mp4`)
2. Pilih SRT ori (mis. `srt-id-original.srt` atau `srt-mn-original.srt`)
3. Pilih SRT dub (mis. `srt-id-dub.srt` atau `srt-jw-dub.srt`)
4. Pilih Audio dub (mis. `audio-id-dub.wav` atau `audio-jw-dub.wav`)
5. Pilih nama output MP4 (default: `mp4-jw-final.mp4`)
6. Pilih mode SFX:
   - **Mode A — Basic** (audio ori di-duck) — REKOMENDASI
   - Mode B — Separate SFX dengan Demucs (lebih bersih)
   - Mode C — Buang audio ori total
7. Pilih SFX ducking level (default -12 dB, seimbang)
8. Pilih action:
   - **🔍 DRY-RUN** (tes command tanpa proses) — REKOMENDASI PERTAMA KALI
   - ▶️  RUN (proses beneran)

Setelah semua step, akan muncul:
```
╔══════════════════════════════════════════════════════════════════╗
║  📋 Ringkasan:                                                  ║
║  MP4      : mp4-ori-test-5min.mp4                              ║
║  SRT ori  : srt-id-original.srt                                 ║
║  SRT dub  : srt-id-dub.srt                                      ║
║  Audio    : audio-id-dub.wav                                    ║
║  Output   : mp4-jw-final.mp4                                    ║
║  ...                                                            ║
║  Action   : DRY-RUN                                            ║
╚══════════════════════════════════════════════════════════════════╝

=== Command yang akan dijalankan ===
python3 retime-video.py --mp4 mp4-ori-test-5min.mp4 --srt-original srt-id-original.srt ...

Konfirmasi? [Y/n]:
```

Tekan Y untuk lanjut, atau n untuk batal.

Kalau dry-run sukses, akan muncul:
```
✅ SELESAI!
Dry-run sukses. Command valid dan siap dijalankan.
Untuk RUN beneran, jalankan ulang TUI dan pilih RUN.
```

### 📝 Cara 2: Ketik Command Manual (untuk yang sudah mahir)

Kalau user sudah mahir dan mau cepat (tanpa TUI), ketik langsung:

**Mode A: Basic (tanpa SFX separation, paling simpel) — sub-ID test**

```bash
cd ~/Dubbing
python3 retime-video.py \
  --mp4 mp4-ori-test-5min.mp4 \
  --srt-original srt-id-original.srt \
  --srt-dub srt-id-dub.srt \
  --audio-dub audio-id-dub.wav \
  --output mp4-id-final.mp4
```

**Mode A: Basic — sub-Jawa test**

```bash
cd ~/Dubbing
python3 retime-video.py \
  --mp4 mp4-ori-test-5min.mp4 \
  --srt-original srt-mn-original.srt \
  --srt-dub srt-jw-dub.srt \
  --audio-dub audio-jw-dub.wav \
  --output mp4-jw-final.mp4
```

**Mode B: Advanced (dengan SFX separation via Demucs)**

```bash
cd ~/Dubbing
python3 retime-video.py \
  --mp4 mp4-ori-test-5min.mp4 \
  --srt-original srt-id-original.srt \
  --srt-dub srt-id-dub.srt \
  --audio-dub audio-id-dub.wav \
  --output mp4-id-final.mp4 \
  --separate-sfx \
  --sfx-ducking 12
```

**Dry-run (tes command tanpa proses):**

Tambah `--dry-run` di akhir command, contoh:
```bash
python3 retime-video.py \
  --mp4 mp4-ori-test-5min.mp4 \
  --srt-original srt-id-original.srt \
  --srt-dub srt-id-dub.srt \
  --audio-dub audio-id-dub.wav \
  --output mp4-id-final.mp4 \
  --dry-run
```

**Catatan**: argumen lama (`--srt-mandarin`, `--srt-jawa`, `--audio-jawa`) masih bisa dipakai sebagai alias (deprecated), tapi sebaiknya pakai yang baru (`--srt-original`, `--srt-dub`, `--audio-dub`).

### Estimasi Waktu Fase 4

| Durasi MP4 | Mode A (basic) | Mode B (Demucs + FFmpeg) |
|---|---|---|
| 6 menit | 1-2 menit | 5-10 menit |
| 30 menit | 10-20 menit | 20-40 menit |
| 1 jam | 30-60 menit | 60-90 menit |
| 3 jam | 90-180 menit | 180-300 menit |

Tunggu sampai muncul:
```
✓ Output: mp4-id-final.mp4 (atau mp4-jw-final.mp4)
  Size: XX MB
  Duration: HH:MM:SS
```

### ✅ Fase 4 Selesai

File `mp4-id-final.mp4` (atau `mp4-jw-final.mp4`) ada di `~/Dubbing/`. Buka dengan QuickTime atau DaVinci untuk cek hasil.

---

## 🎨 Fase 5: Edit Final di DaVinci Resolve (Manual)

1. Buka DaVinci Resolve
2. Drag `mp4-jw-final.mp4` (atau `mp4-id-final.mp4`) ke timeline
3. Cek:
   - **Audio dub** natural (tidak robot)
   - **Video slow-mo** di cue pendek (wajar, supaya match audio dub)
   - **SFX/backsound** masih ada (kalau pakai mode B)
4. Edit final (opsional):
   - Color grade
   - Tambah musik latar
   - Cut scene yang tidak perlu
5. Export final video

---

## ❓ FAQ Pemula

### Q: Saya takut salah ketik command. Aman?

**A:** Aman. Command Python cuma baca argumen, tidak hapus file user. Kalau typo, akan muncul error message — baca, perbaiki, jalankan ulang. Tidak ada data hilang.

### Q: Kenapa harus pakai Terminal? Tidak ada aplikasi GUI?

**A:** Buat GUI butuh waktu develop 1-2 minggu lagi. Untuk sekarang, command line cukup. Setelah user berhasi sekali, tinggal save command di Notes, copy-paste untuk video berikutnya.

### Q: Boleh pakai VS Code atau editor lain?

**A:** Boleh. Buka VS Code → Terminal → New Terminal → ketik command sama.

### Q: Apa arti tanda `\` di akhir baris command?

**A:** Itu artinya "command lanjut ke baris berikutnya". Bisa juga ditulis 1 baris saja:
```bash
python3 retime-video.py --mp4 mp4-ori-test-5min.mp4 --srt-original srt-id-original.srt --srt-dub srt-id-dub.srt --audio-dub audio-id-dub.wav --output mp4-id-final.mp4
```

### Q: JSON itu apa? Harus saya buka?

**A:** JSON (JavaScript Object Notation) itu format text untuk data terstruktur. **User TIDAK perlu buka file JSON.** Itu dibaca otomatis oleh Python script. Cukup taruh di folder yang sama.

### Q: Kalau Demucs gagal install, masih bisa pakai?

**A:** Bisa. Skip Fase 3 (SFX separation), langsung Fase 4 mode A (basic). Audio ori MP4 akan di-duck saja (volume turun saat audio Jawa bicara). Backsound masih kedengaran, cuma tidak se-bersih mode Demucs.

### Q: Video final saya kenapa slow-mo di beberapa scene?

**A:** Itu wajar. Karena audio dub lebih panjang dari cue ori asli, video harus melambat supaya timing-nya match. Kalau slow-mo terlalu janggal, naikkan speed di Fase 2 (1.0x → 1.25x atau 1.5x).

### Q: Audio dub terdengar robot di beberapa cue?

**A:** Kalau pakai speed 1.0x, seharusnya tidak ada robot. Tapi kalau ada, kemungkinan Edge TTS proxy error — coba generate ulang di web app. Atau pakai 1.5x (audio lebih cepat tapi tetap jelas).

### Q: Saya mau coba dulu dengan audio 6 menit, kira-kira cepat?

**A:** Cepat. Untuk audio 6 menit:
- Fase 3 (Demucs, opsional): 2-5 menit
- Fase 4 (FFmpeg retim): 1-3 menit
- Total: 3-8 menit

Sangat cocok untuk test awal.

---

## 🆘 Troubleshooting

### Error: `command not found: python3`

Python belum terinstall. Install:
```bash
brew install python@3.10
```

### Error: `command not found: ffmpeg`

FFmpeg belum terinstall. Install:
```bash
brew install ffmpeg
```

### Error: `command not found: demucs`

Demucs belum terinstall. Install:
```bash
pip3 install demucs
```

### Error: `FileNotFoundError: mp4-ori-test-5min.mp4`

User tidak di folder yang benar. Ketik:
```bash
cd ~/Dubbing
ls
```
Pastikan file `mp4-ori-test-5min.mp4` (atau nama MP4 source user) ada.

### Error: `Edge TTS proxy error`

Web app gagal generate audio. Coba:
1. Refresh browser
2. Generate ulang
3. Ganti voice (coba `id-ID-ArdiNeural`)

### FFmpeg render lambat

Normal. Untuk file besar, butuh banyak CPU. Tips:
- Tutup aplikasi lain
- Pakai preset `fast`: tambah `--preset fast` di command (kualitas turun sedikit, lebih cepat)

### Output video gelap / tidak ada audio

Cek:
- `mp4-jw-final.mp4` (atau `mp4-id-final.mp4`) benar ada di folder?
- File size > 1 MB?
- Coba buka dengan VLC player (kadang QuickTime bermasalah)

---

## 📋 Checklist Praktek untuk Audio 5 Menit (sub-ID test)

Test user dengan audio 5 menit yang sudah di-generate dari DUB web:

```bash
# 1. Setup folder
mkdir -p ~/Dubbing
cd ~/Dubbing

# 2. Copy file sumber dengan nama standar (ganti path sesuai lokasi user)
cp ~/Downloads/mandarin.mp4 mp4-ori-test-5min.mp4
cp ~/Downloads/original.srt srt-id-original.srt

# 3. Copy 3 file dari DUB web (audio-jd-dub.wav, srt-dub.srt, retime-map.json)
#    Bisa drag dari Finder ke folder Dubbing, atau:
cp ~/Downloads/Season-audio-jd-dub.wav audio-id-dub.wav
cp ~/Downloads/Season-srt-dub.srt           srt-id-dub.srt
cp ~/Downloads/Season-retime-map.json       retime-map.json

# 4. Download script Python
curl -L -o retime-video.py https://raw.githubusercontent.com/emailnyamahmud-afk/srt-splitter/main/scripts/retime-video.py

# 5. Cek folder
ls
# Harus muncul: audio-id-dub.wav  mp4-ori-test-5min.mp4  srt-id-original.srt  retime-map.json  retime-video.py  srt-id-dub.srt

# 6. Dry-run (test command)
python3 retime-video.py \
  --mp4 mp4-ori-test-5min.mp4 \
  --srt-original srt-id-original.srt \
  --srt-dub srt-id-dub.srt \
  --audio-dub audio-id-dub.wav \
  --output mp4-id-final.mp4 \
  --dry-run

# 7. Kalau dry-run OK, run beneran
python3 retime-video.py \
  --mp4 mp4-ori-test-5min.mp4 \
  --srt-original srt-id-original.srt \
  --srt-dub srt-id-dub.srt \
  --audio-dub audio-id-dub.wav \
  --output mp4-id-final.mp4 \
  --encoder h264_videotoolbox \
  --workers 4

# 8. Buka hasil
open mp4-id-final.mp4
```

**Estimasi waktu untuk audio 5 menit (H.264 + VideoToolbox M1):**
- Setup: 15 menit (sekali)
- Fase 1-2: 10 menit (kalau sudah punya audio dari DUB web)
- Fase 4: 5-8 menit
- **Total: ~30 menit untuk test pertama**

Kalau sukses, user bisa langsung pakai workflow ini untuk video 1 jam, 3 jam, dst. Cuma beda di waktu rendering FFmpeg.

---

## 📚 Dokumentasi Tambahan

- **`scripts/README.md`** — index semua Python script
- **`scripts/tutor-python-lokal.md`** — setup Python untuk `srt-to-audio.py` (alternatif kalau web app lambat)
- **`docs/EDGE_TTS_PROXY.md`** — cara kerja Edge TTS proxy (teknis)

Kalau ada pertanyaan, tanya. Kalau ada error, copy pesan error ke AI untuk dianalisis.
