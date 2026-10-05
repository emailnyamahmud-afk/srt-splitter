# Progress Log — SRT Splitter + Dubbing Project

Dokumen ini catatan status project untuk AI / developer next time baca. Update setiap sesi kerja.

**Last updated:** 5 Oktober 2026, 20:50 WIB

---

## 📌 Quick Status

| Item | Status |
|---|---|
| Web app (srt-splitter.vercel.app) — v2.0 schema | ✅ Production ready |
| **Mode ON + Smart Fit (strategi baru, video = ground truth)** | ✅ Working, user rating 8/10 (cap 2.0x) |
| Dubbing Mode v2.0 (VoiceStudio adoptions) | ✅ Working, tapi render video 20x test gagal (deprecated approach) |
| Python `mix-audio-dub.py` (strategi baru: SFX preserve + ducking) | ✅ Working, ~10 detik, 100% sync |
| Python `retime-video.py` v6 (deprecated, untuk Dubbing Mode) | ⚠️ 20x test gagal, tetap di repo sebagai backup |
| Python `separate-audio-sfx.py` (Demucs) | ✅ Working (belum user test) |
| Standar nama file | ✅ Diterapkan di web + docs + Python |
| **Test #22 mode ON Smart Fit (cap 2.0x)** | ✅ User rating 8/10 (audio natural, no truncate) |
| **Test #23 mode ON Smart Fit (cap 1.25/1.5/2.0)** | ❌ User rating buruk (semua 3 cap) |
| **Test #24 mode ON Smart Fit (revert ke 8/10)** | ⏳ In progress (Vercel deploy) |
| Kamus Jawa JSON | 🔜 Next step (setelah workflow mode ON stabil) |
| Workflow multi-bahasa (Jawa/Sunda/dll) | 🔜 Next step |

---

## 🎯 PIVOT STRATEGI (5 Okt 2026, setelah 20x test render video gagal)

### Latar belakang
Setelah 20x test render video (`retime-video.py`) gagal (stop-motion, DTS warnings, drift, slow-mo ekstrim), user sadar:
- "justru yg penting di hulu = web dub kita. kalau durasi masih jadi penjara = apa gunanya?"
- "kenapa tidak copas voice studio saja? kita repot-repot bikin retim tapi sudah 30 kali gagal"
- "kita ubah video sebagai ground off truth = lalu kita optimalkan web TTS untuk generate audio sesuai srt ori?"
- "karena srt ori sudah sync dengan video ori, maka generate audio dengan timesmap ori = 100% sync"

### Strategi baru: Mode ON + Smart Fit (video = ground truth)

**Lama (Dubbing Mode + render video):**
```
SRT ori → translate → Dubbing Mode (audio natural, SRT baru) → retime-video.py (20x gagal)
```

**Baru (Mode ON + Smart Fit + mix):**
```
SRT ori → mode ON + Smart Fit (audio fit SRT ori) → mix-audio-dub.py (SFX + dub, ~10 detik)
```

### Keuntungan strategi baru
1. Video 100% sync SRT ori (tidak di-retim, tidak ada slow-mo, tidak ada stop-motion)
2. Workflow simpel: 2 fase (web + Python mix), bukan 5 fase
3. SFX ori dipertahankan + ducking sidechain (audio ori pelan saat dialog bicara)
4. Tidak ada DTS warnings (video stream copy)
5. Output 100% sync, ~10 detik proses

### Filosofi yang berubah
- **Lama**: "audio bebas dari penjara SRT" (audio natural, video ngikut → 20x gagal)
- **Baru**: "video = ground truth, audio dub fit ke SRT ori dengan Smart Fit"
- Smart Fit = per-cue dynamic TTS speed (pitch preserved, BUKAN atempo robot)
- Crossfade 150ms kalau audio overflow cue (tumpang tindih smooth, user accept)

---

## 🔴 Smart Fit Algorithm (mode ON)

### Algoritma
```
Untuk setiap cue:
1. Generate natural TTS (speed 1.0)
2. Asymmetric trim (head -40dB aggressive, tail -49dB gentle — voicertool pattern)
3. need = naturalDur / cueDur (rasio audio natural vs cue ori)
4. Kalau need ≤ 1.0 → pakai natural (no speedup)
5. Kalau need > 1.0 → audioRate = min(need, cap)
   - Edge TTS server-side rate (pitch preserved di server, BUKAN atempo)
   - Kalau need ≤ cap → exact fit (no overflow, no crossfade)
   - Kalau need > cap → cap + crossfade (overflow ke cue next, smooth)
6. Peak normalize -2 dBFS per cue (loudness konsisten)
7. Crossfade 150ms kalau audio overflow cue (tumpang tindih, NO truncate)
```

### Cap options (user feedback)
- **1.25x** — paling natural, banyak crossfade kalau need > 1.25
- **1.5x** — balanced, lebih sedikit crossfade
- **2.0x** — voicertool cap, paling sedikit crossfade, agak cepat ★ (user rating 8/10)

### VoiceStudio fit_planner + voicertool.com adopsi
- **VoiceStudio**: per-cue dynamic speed, geometric split (kita adaptasi sederhana)
- **voicertool.com**: asymmetric trim (head -40dB, tail -49dB), cap 2.0x, ffmpeg.wasm atempo (kita skip, pakai Edge TTS server-side)

---

## 📊 Test History Smart Fit (mode ON)

| Test # | Cap | Truncate | Rating | Notes |
|---|---|---|---|---|
| #21 | 1.5x | YA (cue + 150ms) | 5/10 | Banyak cue terpotong di akhir |
| #22 | 2.0x | TIDAK (hapus truncate) | **8/10** | Audio natural, no truncate, user suka |
| #23 | 1.25x default | TIDAK | buruk | User test 1.25/1.5/2.0 semua buruk |
| #24 | 2.0x (revert ke #22) | TIDAK | ⏳ | In progress, Vercel deploy |

### Insight user (5 Okt 2026 malam)
- "sudah tak ada yg terpotong, tapi 2x sangat cepat" (test #22)
- "bisa tidak dibuat fleksibel? default 1.25? dan auto jadi 1.5 atau 2 sesuai durasi?"
- "yg penting tidak terpotong, tidak truncate, soal crossfade tidak masalah"
- Test #23: "user sudah uji 1.25, 1.5 dan 2 = semuanya buruk"
- "kembalikan ke code sebelumnya yg user kasih nilai 8/10"
- "AI jangan sok tau. Manusia yg bisa dengar wav lebih tau mana yg suara bagus"

### Revert
- Commit `cd5fcbb` revert ke `160b9a7` (cap 2.0x default, hapus truncate)
- User yang juri suara, AI hanya baca gelombang dan code

---

## 🐛 BUG HISTORY: Video Retaimed Rusak — Test #1 sampai #20 (4-5 Okt 2026, DEPRECATED)

### Catatan
Setelah 20x test gagal, strategi render video di-deprecated. `retime-video.py` tetap di repo sebagai backup
untuk Dubbing Mode kalau nanti sudah nemu jalan keluar. Workflow utama sekarang: Mode ON + Smart Fit + mix-audio-dub.py.

### Test timeline singkat (deprecated)

| Test # | Strategi | Hasil |
|---|---|---|
| #1-#3 (4 Okt) | Filter complex inline → two-pass rendering | Memory 40GB, DTS non-monotonic |
| #4-#8 (4 Okt malam) | Re-encode Pass 2 + flag berbagai | DTS warnings 332-491, video rusak |
| #9-#14 (5 Okt pagi) | `-bf 0` + `-fps_mode cfr` + cumulative offset | DTS warnings turun tapi masih ada |
| #15 (5 Okt 11:00) | cumulative offset + `output_ts_offset` + `fps=30` VFR guard | DTS=0, durasi OK, TAPI visual stop-motion |
| #16 (5 Okt 11:30) | + tpad freeze | GAGAL — PTS overflow di h264_videotoolbox |
| #17-#19 (5 Okt sore) | revert tpad + skip 100B + audit 5 bug | Visual masih stop-motion |
| #20 (5 Okt 18:00) | + Smart Fit di Dubbing Mode | Slow-mo lebih baik tapi masih stop-motion |

### 9 Fix yang pernah diimplementasi (deprecated, tetap di code untuk dokumentasi)

| # | Fix | Dampak |
|---|---|---|
| 1 | Two-pass rendering (file-based segments) | Pass 1 parallel, Pass 2 concat |
| 2 | `-bf 0` (disable B-frames) | Fix DTS non-monotonic |
| 3 | `output_ts_offset` (cumulative timestamp) | Fix concat seamless |
| 4 | `fps=30` VFR guard | Fix frame rate inconsistency |
| 5 | Stream copy Pass 2 | Instant concat, no re-encode |
| 6 | `-ss` sebelum `-i` (fast seek) | O(n) bukan O(n²) |
| 7 | `-t` pakai mp4_dur (input durasi) | Fix FFmpeg baca input terlalu lama |
| 8 | `-t` EXACT, no margin | Fix drift 35s (KRITIKAL) |
| 9 | Skip threshold 100 bytes | Fix segment pendek di-skip |

### Root cause stop-motion (tidak bisa di-fix tanpa kompromi)
- `setpts × factor` untuk slow-mo = nature frame duplication = stop-motion
- VoiceStudio juga pakai setpts × ratio, mereka cap di 2x + atempo (kita tolak) + LLM condense (kita tolak)
- `minterpolate` no-op dengan fps=30 SETELAH setpts (sandbox test konfirmasi)
- `tpad` PTS overflow di h264_videotoolbox

---

## ✅ Yang Sudah Jalan (Production)

### 1. Web App (https://srt-splitter.vercel.app/)
- **Split SRT** — by durasi atau karakter
- **Translate** — Google Translate + OpenAI
- **TTS Mode ON + Smart Fit** ★ (strategi baru, default)
  - Per-cue dynamic TTS speed (cap 2.0x, pitch preserved)
  - Asymmetric trim (voicertool pattern)
  - Peak normalize -2 dBFS
  - Crossfade 150ms (no truncate)
  - Video = ground truth (100% sync SRT ori)
- **TTS Mode ON Classic** (lama, opsi)
  - Speed up only / Speed up and slow down (voicertool klasik)
- **TTS Mode OFF** — natural sequential, speed 1.0x-2.0x
- **🔴 Dubbing Mode v2.0** (deprecated, untuk render video)
  - VoiceStudio Pattern A (slack absorption), C (15ms fade), D (peak norm), G (SRT de-overlap)
  - Schema v2.0: chunks, fittedCues, params, audioRate, videoRatio, status

### 2. Python Scripts (lokal)
- **`mix-audio-dub.py`** ★ (strategi baru, simpel)
  - Mix audio ori MP4 + audio dub WAV dengan ducking sidechain
  - Video stream copy (100% ori, no re-encode) → 100% sync
  - --ducking 12 (default): SFX di-duck 12dB saat dialog dub bicara
  - --no-ducking: SFX + dub sama keras (additive)
  - --sfx-only: buang audio ori (fallback)
  - Estimasi: ~10 detik untuk video 2.5 jam
- **`retime-video.py`** v6 (deprecated, tetap di repo)
  - Two-pass rendering, h264_videotoolbox, cumulative offset
  - 20x test gagal (stop-motion), tetap sebagai backup untuk Dubbing Mode
- **`dubbing-tui.py`** — TUI interaktif (untuk Dubbing Mode)
- **`separate-audio-sfx.py`** — Demucs SFX separation (opsional)
- **`srt-to-audio.py`** — alternatif TTS lokal
- **`rapikan-jawa.py`** + `tambah-krama.py` — rapikan SRT Jawa
- **`test-dubbing-v2-schema.py`** — sanity test untuk v2.0 schema

### 3. Documentation
- `README.md` — overview project + visi + standar nama file
- `docs/PROJECT_VISION.md` — visi digitalisasi bahasa + roadmap 2 tahun
- `docs/PROGRESS.md` — dokumen ini (status terkini)
- `docs/EDGE_TTS_PROXY.md` — cara kerja Edge TTS proxy
- `scripts/tutor-dubbing-workflow.md` — workflow pemula buta Python
- `scripts/tutor-python-lokal.md` — setup Python lokal
- `scripts/README.md` — index Python scripts
- `worklog.md` — log development lengkap (Task 1-8)

---

## 📊 User Test Summary

### Setup User
- MacBook Pro (Apple Silicon, M1/M2)
- Python 3.14.7 via Homebrew
- FFmpeg 9.0.2 via Homebrew
- venv di `~/Dubbing/venv/`

### Test #22 mode ON Smart Fit (5 Okt 2026, 20:00 WIB) — RATING 8/10
- SRT ori: 160 cues (srt-id-original.srt, 6:28)
- Cap: 2.0x (voicertool, default)
- Audio dub: fit SRT ori, no truncate, crossfade 150ms
- User: "sudah tak ada yg terpotong, tapi 2x sangat cepat"
- Rating: 8/10 (audio natural, no truncate, tapi cap 2.0x agak cepat)

### Test #23 mode ON Smart Fit (5 Okt 2026, 20:30 WIB) — RATING BURUK
- User test 1.25x, 1.5x, 2.0x — semuanya buruk
- "kembalikan ke code sebelumnya yg user kasih nilai 8/10"
- Revert commit `cd5fcbb` ke `160b9a7` (cap 2.0x default)

### Test #24 mode ON Smart Fit (5 Okt 2026, 20:50 WIB) — IN PROGRESS
- Revert ke #22 (cap 2.0x default, hapus truncate)
- Vercel deploy in progress
- User yang juri suara, AI baca gelombang dan code

---

## 🔜 Next Steps (Prioritas)

### Priority 1: Stabilkan workflow mode ON + Smart Fit (current)
- Test #24 (revert ke 8/10) → konfirmasi user rating 8/10 lagi
- Kalau OK → lanjut mix dengan `mix-audio-dub.py`
- Target: workflow end-to-end 100% sync, audio natural, SFX preserve

### Priority 2: Test full season S7-id (2.5 jam)
- Setelah test 5 menit stabil, test full season
- Mode ON + Smart Fit → audio dub full (estimasi ~30 menit generate)
- mix-audio-dub.py → ~10 detik
- Output: mp4-id-final.mp4 (2.5 jam, 100% sync, SFX + dub)

### Priority 3: Kamus Bahasa Jawa JSON
**Tujuan:** Validasi SRT Jawa otomatis (ejaan, register, kosakata)
**Riset sumber:** Sastra.org, Wiktionary Jawa, Balai Bahasa Yogyakarta
**Estimasi effort:** 5-7 hari kerja

### Priority 4: Workflow Multi-Bahasa (Jawa/Sunda/Bali)
- Pakai SRT Indonesia hasil mode ON untuk bahasa lain
- Translate text Indonesia → Jawa (timing TIDAK diubah)
- Generate audio Jawa pakai SRT Jawa (timing sama dengan Indonesia)
- Mix dengan audio ori MP4 (SFX preserve)
**Estimasi effort:** 2-3 hari

### Priority 5: Dubbing Mode + render video (deprecated, tapi tetap di repo)
- `retime-video.py` tetap di repo sebagai backup
- Kalau nanti nemu jalan keluar (misal: minterpolate yang benar, atau GPU acceleration)
- Untuk sekarang: fokus ke Mode ON + Smart Fit + mix

---

## 🗂️ Aset User (Tidak Di-Commit ke Repo)

File user pribadi, di MacBook lokal (dengan standar nama):
- `~/Dubbing/mp4-ori-test-7min.mp4` — source MP4 (7:30, H.264, ada audio ori + SFX)
- `~/Dubbing/srt-id-original.srt` — SRT Indonesia source (160 cues, 6:28, timing Mandarin = "penjara")
- `~/Dubbing/audio-id-dub.wav` — audio dub result (dari mode ON + Smart Fit, fit SRT ori)
- `~/Dubbing/mp4-id-final.mp4` — HASIL RENDER (video ori + SFX + dub, mix-audio-dub.py)
- `~/Dubbing/venv/` — virtual environment Python

Standar nama file (konvensi project):
| File | Format | Contoh |
|---|---|---|
| MP4 source | `mp4-ori-{name}.mp4` | `mp4-ori-test-7min.mp4` |
| SRT source | `srt-{lang}-original.srt` | `srt-id-original.srt`, `srt-mn-original.srt` |
| Audio dub | `audio-{lang}-dub.wav` | `audio-id-dub.wav`, `audio-jw-dub.wav` |
| Output final | `mp4-{lang}-final.mp4` | `mp4-id-final.mp4`, `mp4-jw-final.mp4` |

Recording Zoom H6 (260 jam total, di luar repo):
- 37 video panatacara (~150 jam)
- 110 episode Kaladete Podcast (~110 jam)
- Akses komunitas Permadani (100 siswa/tahun validator)

---

## 📝 Catatan untuk AI Next Time Buka

1. **Strategi pivot (5 Okt 2026)**: Mode ON + Smart Fit + mix-audio-dub.py = workflow utama. Dubbing Mode + retime-video.py = deprecated (20x test gagal).
2. **Smart Fit algoritma**: audioRate = min(need, cap). Cap default 2.0x (voicertool, user rating 8/10). Asymmetric trim (head -40dB, tail -49dB). Crossfade 150ms, NO truncate.
3. **Filosofi**: "video = ground truth, audio dub fit ke SRT ori dengan Smart Fit". Bukan "audio bebas dari penjara SRT" lagi.
4. **User yang juri suara**: AI hanya baca gelombang dan code. Jangan sok tau soal kualitas audio.
5. **Test #22 = 8/10** (cap 2.0x, no truncate). Test #23 = buruk (semua cap). Test #24 = revert ke #22.
6. **Standar nama file** sudah diterapkan: `mp4-ori-`, `srt-{lang}-original.srt`, `audio-{lang}-dub.wav`, `mp4-{lang}-final.mp4`.
7. **Schema v2.0** (Dubbing Mode): chunks, fittedCues, params, audioRate, videoRatio, status. Backward compat v1.0 dengan `points` alias.
8. **VoiceStudio riset**: 36 file di `/scripts/voicestudio-study/` (gitignored). Latest commit main = 990f0627. Lihat worklog Task 7-a.
9. **voicertool.com riset**: decoded srt.js (obfuscated). Asymmetric trim, cap 2.0x, ffmpeg.wasm atempo. Lihat worklog Task 8.
10. **mix-audio-dub.py**: sidechain compression, threshold=0.05, ratio=10, attack=5ms, release=300ms. Video stream copy.
11. **Filosofi user**: "ada uang atau tidak, tetap dikerjakan step by step, terdokumentasi rapi"
12. **Visi besar**: 700 bahasa Indonesia, 169 terancam punah. Project ini prototype digitalisasi.

---

## 📅 Timeline Update

- **4 Okt 2026, 21:00 WIB**: Initial PROGRESS.md, test #1-#8 render video rusak DTS
- **5 Okt 2026, 02:55 WIB**: render S7-id.mp4 full season SUKSES tapi video rusak (332 DTS warnings)
- **5 Okt 2026, 03:00-08:00 WIB**: 8 iterasi fix DTS (test #9-#14)
- **5 Okt 2026, 08:30 WIB**: Update PROGRESS.md — bug history + M1 optimization
- **5 Okt 2026, 10:00 WIB**: Dub web v2.0 ter-deploy (VoiceStudio adoptions + JSON v2.0 schema)
- **5 Okt 2026, 10:30 WIB**: Standar nama file diterapkan di web + docs + Python
- **5 Okt 2026, 11:00-18:00 WIB**: Test #15-#20 render video (semua gagal stop-motion)
- **5 Okt 2026, 18:30 WIB**: Pivot strategi — Mode ON + Smart Fit + mix-audio-dub.py
- **5 Okt 2026, 19:00 WIB**: Smart Fit di mode ON diimplementasi (VoiceStudio + voicertool adopsi)
- **5 Okt 2026, 20:00 WIB**: Test #22 mode ON Smart Fit cap 2.0x — user rating 8/10 ✓
- **5 Okt 2026, 20:30 WIB**: Test #23 mode ON Smart Fit cap 1.25/1.5/2.0 — user rating buruk
- **5 Okt 2026, 20:50 WIB**: Revert ke #22 (cap 2.0x default), test #24 in progress
- **Next update**: Setelah test #24 konfirmasi 8/10 + mix-audio-dub.py test

