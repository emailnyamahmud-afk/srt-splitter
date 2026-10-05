# Tutor Workflow Mode ON + Smart Fit + mix-audio-dub.py

Panduan workflow dubbing baru (5 Okt 2026, setelah 20x test render video gagal).

**Strategi**: Video = ground truth (SRT ori 100% sync). Audio dub fit ke SRT ori dengan Smart Fit. Mix dengan audio ori MP4 (SFX preserve + ducking).

**Total waktu per video 5 menit**: ~3 menit (TTS web) + ~10 detik (mix Python) = ~3 menit
**Total waktu per video 2.5 jam**: ~30 menit (TTS web) + ~10 detik (mix Python) = ~30 menit

---

## 📌 Penjelasan Singkat

### Kenapa strategi baru?

Strategi lama (Dubbing Mode + render video) gagal 20x test:
- Stop-motion di cue pendek (setpts × factor = frame diulang)
- DTS warnings di concat segments
- Drift 35s dari -t margin bug
- Visual "kayak foto berhenti, diulang"

Strategi baru (Mode ON + Smart Fit + mix):
- Video 100% sync SRT ori (tidak di-retim)
- Audio dub fit ke SRT ori dengan per-cue dynamic TTS speed (pitch preserved)
- SFX ori MP4 dipertahankan + di-duck saat dialog bicara
- Workflow simpel: 2 fase (web + Python mix)

### Filosofi yang berubah

- **Lama**: "audio bebas dari penjara SRT" (audio natural, video ngikut → 20x gagal)
- **Baru**: "video = ground truth, audio dub fit ke SRT ori dengan Smart Fit"
- Smart Fit = per-cue dynamic TTS speed (Edge TTS server-side rate, pitch preserved, BUKAN atempo robot)
- Crossfade 150ms kalau audio overflow cue (tumpang tindih smooth, user accept)

---

## 🌐 Fase 1: Web App (Mode ON + Smart Fit)

### Step 1: Upload SRT ori

1. Buka https://srt-splitter.vercel.app/
2. Upload `srt-id-original.srt` (SRT Indonesia, timing Mandarin = "penjara")
3. Split SRT by durasi (mis. 30 menit per part) kalau file besar

### Step 2: Pilih mode ON + Smart Fit

1. Di panel TTS, pilih mode **ON** (default)
2. Smart Fit sudah ON (default), cap **2.0x** (default, voicertool cap)
3. Pilih voice:
   - `id-ID-ArdiNeural` (laki-laki)
   - `id-ID-GadisNeural` (perempuan)
4. (Opsional) Ganti cap ke 1.25x atau 1.5x kalau mau lebih natural (tapi user rating 8/10 di 2.0x)

### Step 3: Generate audio dub

1. Klik **Generate & Download ZIP**
2. Tunggu ~3 menit per 5 menit SRT (160 cues)
3. Download ZIP, extract
4. Rename file sesuai standar:
   - `{prefix}-01.wav` → `audio-id-dub.wav`
5. Cek audio dub di VLC:
   - Natural? (pitch preserved, bukan robot)
   - Durasi ≈ SRT ori? (fit timing)
   - Cue pendek agak cepat tapi natural? (Smart Fit speedup)
   - Tidak ada cue terpotong di akhir? (no truncate)

### ✅ Fase 1 Selesai — Cek File

```bash
ls ~/Dubbing
# Harus muncul:
# audio-id-dub.wav    srt-id-original.srt    mp4-ori-test-7min.mp4
```

---

## 🐍 Fase 2: Python Mix (mix-audio-dub.py)

### Step 1: Download script

```bash
cd ~/Dubbing
curl -L -o mix-audio-dub.py https://raw.githubusercontent.com/emailnyamahmud-afk/srt-splitter/main/scripts/mix-audio-dub.py
```

### Step 2: Jalankan mix

**Mode default (SFX preserve + ducking 12dB):**
```bash
python3 mix-audio-dub.py \
  --mp4 mp4-ori-test-7min.mp4 \
  --audio-dub audio-id-dub.wav \
  --output mp4-id-final.mp4 \
  --ducking 12
```

**Mode no-ducking (SFX + dub sama keras):**
```bash
python3 mix-audio-dub.py \
  --mp4 mp4-ori-test-7min.mp4 \
  --audio-dub audio-id-dub.wav \
  --output mp4-id-final.mp4 \
  --no-ducking
```

**Mode sfx-only (buang audio ori, hanya dub):**
```bash
python3 mix-audio-dub.py \
  --mp4 mp4-ori-test-7min.mp4 \
  --audio-dub audio-id-dub.wav \
  --output mp4-id-final.mp4 \
  --sfx-only
```

### Step 3: Cek output

```bash
ls -lh mp4-id-final.mp4
# Harus muncul: mp4-id-final.mp4 (size ~100-200 MB untuk 7 menit)
```

### ✅ Fase 2 Selesai

Output: `mp4-id-final.mp4` dengan:
- Video stream copy (100% ori, tidak di-retim) → 100% sync
- Audio ori MP4 (SFX) di-duck 12dB saat dialog dub bicara
- Audio dub (Smart Fit, fit SRT ori) jadi foreground
- Durasi: sama dengan MP4 source (7:30)

---

## 🎬 Fase 3: Cek + Edit Final (DaVinci Resolve)

### Step 1: Cek di VLC

1. Buka `mp4-id-final.mp4` di VLC
2. Cek:
   - Video 100% sync (tidak ada slow-mo, tidak ada stop-motion)
   - Audio dub terdengar natural (Smart Fit, pitch preserved)
   - SFX ori terdengar (backsound drama, efek suara)
   - Saat dialog dub bicara, SFX pelan (ducking 12dB)
   - Saat hening, SFX kembali normal

### Step 2: Edit di DaVinci (opsional)

1. Buka DaVinci Resolve
2. Drag `mp4-id-final.mp4` ke timeline
3. Cek:
   - Video smooth (tidak ada frame drop, tidak ada DTS warnings)
   - Audio waveform: dub di foreground, SFX di background
4. Edit final (opsional):
   - Color grade
   - Tambah musik latar
   - Cut scene yang tidak perlu
5. Export final video

---

## 📋 Checklist Praktek untuk Audio 7 Menit (sub-ID test)

```bash
# 1. Setup folder (kalau belum ada)
mkdir -p ~/Dubbing
cd ~/Dubbing

# 2. Copy file sumber dengan nama standar
cp ~/Downloads/mandarin.mp4 mp4-ori-test-7min.mp4  # atau cut dengan ffmpeg -t 450
cp ~/Downloads/original.srt srt-id-original.srt

# 3. Cut MP4 ke 7.5 menit (cover 160 cues + cushion)
ffmpeg -y -i mandarin.mp4 -t 450 -c copy mp4-ori-test-7min.mp4

# 4. Web app: upload srt-id-original.srt → mode ON + Smart Fit → Generate → Download
#    Rename hasil: audio-id-dub.wav

# 5. Download mix-audio-dub.py
curl -L -o mix-audio-dub.py https://raw.githubusercontent.com/emailnyamahmud-afk/srt-splitter/main/scripts/mix-audio-dub.py

# 6. Cek folder
ls
# Harus muncul: audio-id-dub.wav  mp4-ori-test-7min.mp4  mix-audio-dub.py  srt-id-original.srt

# 7. Mix (default: SFX preserve + ducking 12dB)
python3 mix-audio-dub.py \
  --mp4 mp4-ori-test-7min.mp4 \
  --audio-dub audio-id-dub.wav \
  --output mp4-id-final.mp4 \
  --ducking 12

# 8. Buka hasil
open mp4-id-final.mp4
```

**Estimasi waktu untuk audio 7 menit:**
- Setup: 5 menit (sekali)
- Fase 1 (web TTS): ~3 menit
- Fase 2 (Python mix): ~10 detik
- **Total: ~10 menit untuk test pertama**

---

## ❓ FAQ

### Q: Kenapa tidak pakai Dubbing Mode + retime-video.py lagi?

**A:** 20x test gagal. Stop-motion di cue pendek tidak bisa di-fix tanpa kompromi:
- atempo audio speedup = robot (kita tolak)
- LLM condense text = kembali ke penjara SRT (kita tolak)
- minterpolate = no-op dengan fps=30 SETELAH setpts
- tpad = PTS overflow di h264_videotoolbox

Mode ON + Smart Fit + mix = 100% sync, audio natural, SFX preserve, ~10 detik.

### Q: Kenapa cap 2.0x default?

**A:** User rating 8/10 di cap 2.0x. Test 1.25x dan 1.5x juga buruk (user feedback).
Voicertool.com juga pakai cap 2.0x. Pitch preserved di Edge TTS server, 2.0x masih natural.

### Q: Kalau audio dub masih terpotong di akhir?

**A:** Cek cap. Cap 2.0x = audio di-speedup max 2x. Kalau need > 2.0 (cue sangat pendek),
audio overflow ke cue next dengan crossfade 150ms (tumpang tindih smooth, no truncate).
User bilang "crossfade tidak masalah" — jadi ini OK.

### Q: Kalau SFX terlalu pelan/saat dialog?

**A:** Atur `--ducking`:
- `--ducking 12` (default): SFX turun 12dB saat dialog
- `--ducking 6`: SFX lebih keras (turun 6dB saja)
- `--ducking 18`: SFX lebih pelan (turun 18dB)
- `--no-ducking`: SFX dan dub sama keras (additive mix)
- `--sfx-only`: buang audio ori, hanya dub

### Q: Kalau audio dub lebih panjang dari MP4?

**A:** `mix-audio-dub.py` pakai `-shortest`, jadi output = MP4 durasi. Audio dub dipotong.
Tips: pakai MP4 source yang lebih panjang, atau audio dub yang lebih pendek (cap lebih tinggi).

### Q: Bisa pakai untuk bahasa lain (Jawa, Sunda, Bali)?

**A:** Ya. Ganti voice di web app:
- Jawa: `jv-ID-SitiNeural` (perempuan), `jv-ID-DimasNeural` (laki-laki)
- Sunda: `su-ID-SitiNeural` (perempuan), `su-ID-DimasNeural` (laki-laki)
- Bali: `bali-ID-SitiNeural` (perempuan) — kalau ada

Audio dub fit ke SRT ori (timing sama), mix dengan audio ori MP4. 100% sync.

---

## 🆘 Troubleshooting

### Error: `command not found: ffmpeg`

```bash
brew install ffmpeg
```

### Error: `FileNotFoundError: mp4-ori-test-7min.mp4`

```bash
cd ~/Dubbing
ls
```
Pastikan file ada.

### Audio dub terpotong di akhir

Cek cap di web app. Naikkan ke 2.0x kalau masih 1.25x atau 1.5x.
Atau cek SRT ori — kalau cue terakhir end > MP4 durasi, potong SRT.

### SFX tidak terdengar

Cek `--ducking` value. Default 12 = SFX turun 12dB saat dialog.
Kalau mau SFX lebih keras, pakai `--ducking 6` atau `--no-ducking`.

### Video tidak sync

Mode ON + Smart Fit = video = ground truth (100% sync SRT ori).
Kalau tidak sync, cek SRT ori — pastikan timing = timing video ori (bukan timing dub).

---

## 📚 Dokumentasi Tambahan

- `docs/PROGRESS.md` — status terkini + test history
- `docs/PROJECT_VISION.md` — visi digitalisasi bahasa + roadmap
- `scripts/tutor-dubbing-workflow.md` — workflow lama (Dubbing Mode + render video, deprecated)
- `scripts/tutor-python-lokal.md` — setup Python lokal
- `scripts/README.md` — index Python scripts

---

## 📅 Versi Dokumen

- Versi 1.0 — 5 Oktober 2026 (pivot strategi mode ON + Smart Fit + mix-audio-dub.py)
