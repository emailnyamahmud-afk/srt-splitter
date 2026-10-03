# Tutor: Retime Video Mandarin → Jawa (Fase 3)

Script `retime-video.py` mengubah MP4 Mandarin asli supaya timing-nya match dengan SRT Jawa baru. Hasil akhir: MP4 dengan video retimed + audio Jawa dub, siap diedit di DaVinci Resolve.

## Prerequisite

1. **ffmpeg** terinstall
   - **macOS:** `brew install ffmpeg`
   - **Linux:** `sudo apt install ffmpeg` atau `sudo dnf install ffmpeg`
   - **Windows:** download dari [ffmpeg.org](https://ffmpeg.org/download.html), extract, tambahkan ke PATH

   Cek dengan:
   ```bash
   ffmpeg -version
   ffprobe -version
   ```

2. **Python 3.8+**
   - Cek dengan: `python3 --version`
   - Tidak perlu install library tambahan — script pakai `subprocess` bawaan Python

## Persiapan File

Pastikan 4 file ini sudah siap di satu folder (misal `dubbing/`):

```
dubbing/
├── mandarin.mp4              # MP4 Mandarin asli (sumber)
├── original.srt              # SRT Mandarin (dari Fase 1)
├── subs-jawa-new.srt         # SRT Jawa BARU (dari web app Fase 2)
└── audio-jawa.wav            # Audio Jawa natural (dari web app Fase 2)
```

**Cara dapat `subs-jawa-new.srt` dan `audio-jawa.wav`:**
1. Buka https://srt-splitter.vercel.app/
2. Upload SRT Jawa (yang sudah diterjemahkan + dirapikan)
3. Di panel TTS, pilih mode **🔴 DUBBING — SRT baru**
4. Pilih voice (default: `id-ID-Ardi` untuk narator laki-laki, `id-ID-Gadis` untuk perempuan)
5. Pilih kecepatan audio (default: **1.25x** — rekomendasi)
6. Pilih min gap (default: **150ms** — natural percakapan)
7. Klik **Generate Dubbing**
8. Setelah selesai, klik **Download 3 file (WAV + SRT + JSON)**
9. Akan dapat 3 file:
   - `{prefix}-audio-jawa.wav` → rename jadi `audio-jawa.wav`
   - `{prefix}-subs-jawa-new.srt` → rename jadi `subs-jawa-new.srt`
   - `{prefix}-retime-map.json` → (opsional, untuk debugging)

## Cara Pakai

### Command dasar

```bash
cd dubbing/
python3 /path/ke/scripts/retime-video.py \
  --mp4 mandarin.mp4 \
  --srt-mandarin original.srt \
  --srt-jawa subs-jawa-new.srt \
  --audio-jawa audio-jawa.wav \
  --output mp4-jawa.mp4
```

### Dry run (test command tanpa eksekusi)

```bash
python3 scripts/retime-video.py \
  --mp4 mandarin.mp4 \
  --srt-mandarin original.srt \
  --srt-jawa subs-jawa-new.srt \
  --audio-jawa audio-jawa.wav \
  --output mp4-jawa.mp4 \
  --dry-run
```

### Custom ffmpeg path (kalau tidak di PATH)

```bash
python3 scripts/retime-video.py \
  --mp4 mandarin.mp4 \
  --srt-mandarin original.srt \
  --srt-jawa subs-jawa-new.srt \
  --audio-jawa audio-jawa.wav \
  --output mp4-jawa.mp4 \
  --ffmpeg /usr/local/bin/ffmpeg \
  --ffprobe /usr/local/bin/ffprobe
```

## Output

Setelah selesai, akan ada file `mp4-jawa.mp4` dengan:
- **Video:** Retime dari MP4 Mandarin supaya match SRT Jawa (slow-mo di cue dialog pendek)
- **Audio:** Audio Jawa dari `audio-jawa.wav` (192 kbps AAC)
- **Quality:** CRF 23 (default, balance quality vs size)
- **Codec video:** H.264 (kompatibel dengan DaVinci Resolve, Premiere, Final Cut, dll)

## Yang terjadi di balik layar

Script bekerja dengan strategi **Cut + Slow + Concat**:

1. **Parse SRT Mandarin & SRT Jawa** — pairing cue by index (asumsi 1-to-1)
2. **Per cue:**
   - Cut video dari `cue.start_mandarin` ke `cue.end_mandarin`
   - Retime ke durasi cue Jawa pakai `setpts` (factor = jawa_dur / mandarin_dur)
   - Kalau factor > 1 → video slow-mo (melambat)
   - Kalau factor < 1 → video fast-forward (lebih cepat)
3. **Per gap (jeda antar cue):**
   - Cut video gap dari MP4 asli
   - Retime ke durasi gap Jawa
4. **Concat semua segment** jadi satu video stream
5. **Mix audio Jawa** ke video final
6. **Encode** dengan H.264 + AAC

## Troubleshooting

### Error: "ffmpeg tidak ditemukan"
Install ffmpeg atau specify path via `--ffmpeg /path/to/ffmpeg`.

### Error: "ffprobe gagal"
Pastikan ffprobe terinstall bersama ffmpeg (biasanya satu bundle). Specify path via `--ffprobe /path/to/ffprobe`.

### Output video terlalu besar
Ganti `-preset medium` jadi `-preset fast` di script, atau tingkatkan `-crf` ke 25-28.

### Output video lambat di-render
Untuk video 3 jam, butuh sekitar 30-60 menit di MacBook M1/M2. Untuk lebih cepat, gunakan `--preset ultrafast` (kualitas turun).

### Audio tidak match dengan video
Kemungkinan SRT Jawa dan audio Jawa tidak sync. Pastikan kedua file dari sesi generate yang sama di web app.

### Cue Jawa lebih pendek dari cue Mandarin (fast-forward video)
Ini wajar. Misal cue Mandarin 3s "Bagaimana kabarmu hari ini?" translate Jawa "Pripun kabar?" audio natural 1.5s. Video akan di-fast-forward 2x di cue itu. Kalau terlalu cepat, naikkan speed audio ke 1.0x di web app (audio lebih panjang, video lebih natural).

### Cue Jawa lebih panjang dari cue Mandarin (slow-mo video)
Ini yang paling sering terjadi (Jawa lebih panjang dari Mandarin). Wajar. Audio 1.25x sudah membantu mengurangi slow-mo. Kalau masih terlalu lambat, naikkan ke 1.5x (tapi audio bisa terdengar sedikit robot).

## Workflow lengkap (Fase 1-4)

```
Fase 1 (Sumber):
  - Dapat MP4 Mandarin
  - Dapat/ekstrak SRT Mandarin (misal dengan whisper, atau dari sumber)

Fase 2 (Web app — https://srt-splitter.vercel.app/):
  - Upload SRT Mandarin
  - Translate ke Jawa (panel Translate)
  - Rapikan tatabahasa Jawa (script rapikan-jawa.py lokal)
  - Upload SRT Jawa yang sudah rapi
  - Panel TTS → pilih mode 🔴 DUBBING
  - Generate → download 3 file (WAV + SRT + JSON)

Fase 3 (Python lokal — script ini):
  - Jalankan retime-video.py dengan 4 input
  - Output: mp4-jawa.mp4 (video retimed + audio Jawa)

Fase 4 (DaVinci Resolve):
  - Import mp4-jawa.mp4
  - Edit final (tambah musik, efek, color grade, dll)
  - Export final video
```

## FAQ

**Q: Bisakah audio Jawa dipisah dari video untuk editing terpisah?**
A: Ya. Edit script, ubah baris `-map '1:a'` untuk pakai audio asli MP4, atau skip `-shortest` supaya audio panjang mengikuti video.

**Q: Bagaimana kalau ada cue Jawa yang hilang (kosong)?**
A: Script handle dengan skip cue kosong — gap di timeline Jawa diperluas untuk cue yang hilang.

**Q: Bisakah pakai SRT VTT bukan SRT?**
A: Script support SRT format. Untuk VTT, convert dulu ke SRT (banyak converter online).

**Q: Kenapa output video tidak ada audio Mandarin asli?**
A: Strategi default = replace total (audio Mandarin dibuang, audio Jawa 100%). Kalau mau mix (ducking), edit script dan tambah filter `sidechaincompress` untuk ducking.

**Q: Bagaimana kalau total offset besar (misal +300s untuk 3 jam video)?**
A: Wajar — video akan jadi 3 jam 5 menit. Audio Jawa natural lebih panjang dari Mandarin. Bisa kurangi offset dengan naikkan speed audio ke 1.5x (tapi kualitas audio turun).
