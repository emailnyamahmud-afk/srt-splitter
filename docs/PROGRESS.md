# Progress Log — SRT Splitter + Dubbing Project

Dokumen ini catatan status project untuk AI / developer next time baca. Update setiap sesi kerja.

**Last updated:** 5 Oktober 2026, 11:30 WIB

---

## 📌 Quick Status

| Item | Status |
|---|---|
| Web app (srt-splitter.vercel.app) — v2.0 schema | ✅ Production ready, dub v2.0 tested user |
| Dubbing Mode v2.0 (VoiceStudio adoptions: slack abs, peak norm, 15ms fade, SRT de-overlap) | ✅ Working, tested user (160 cues sub-ID) |
| Python `dubbing-tui.py` (TUI) | ✅ Working, pakai argumen baru `--srt-original/--srt-dub/--audio-dub` |
| Python `retime-video.py` v6 (cap slow-mo 2x + tpad freeze) | ⏳ In progress (test #16 jalan) |
| Python `separate-audio-sfx.py` (Demucs) | ✅ Working (belum user test) |
| Standar nama file: `mp4-ori-`, `srt-{lang}-original.srt`, `srt-{lang}-dub.srt`, `audio-{lang}-dub.wav`, `mp4-{lang}-final.mp4` | ✅ Diterapkan di web + docs + Python |
| Test #15 sub-ID (5 menit, 160 cues, H.264 + VideoToolbox) | ⚠️ DTS=0 durasi=5:24 OK, TAPI visual rusak (skip 24 seg + slow-mo 14x stop-motion) |
| Test #16 sub-ID (5 menit, 160 cues, fix tpad + skip 100B) | ⏳ In progress (Pass 1 0%) |
| Kamus Jawa JSON | 🔜 Next step (besok, setelah dub render jalan) |
| Workflow multi-bahasa (Jawa/Sunda/dll) | 🔜 Next step |

---

## 🐛 BUG HISTORY: Video Retaimed Rusak — Test #1 sampai #15 (4-5 Okt 2026)

### Test timeline singkat

| Test # | Strategi | Hasil |
|---|---|---|
| #1-#3 (4 Okt) | Filter complex inline → two-pass rendering | Memory 40GB, DTS non-monotonic |
| #4-#8 (4 Okt malam) | Re-encode Pass 2 + flag berbagai | DTS warnings 332-491, video rusak |
| #9-#14 (5 Okt pagi) | `-bf 0` + `-fps_mode cfr` + `-video_track_timescale 30000` + cumulative offset | DTS warnings turun tapi masih ada |
| #15 (5 Okt 11:00) | cumulative offset + `output_ts_offset` + `fps=30` VFR guard + stream copy Pass 2 + `-bf 0` | **DTS=0, durasi=5:24 OK, TAPI visual rusak** (skip 24 seg + slow-mo 14x stop-motion weird) |
| #16 (5 Okt 11:30) | + cap slow-mo 2x + `tpad=stop_mode=clone` freeze + skip threshold 1000→100 bytes | ⏳ In progress |

### Bug test #15 (2 masalah baru setelah DTS fix)

1. **Skip 24/233 segments (10.3%)**: threshold `os.path.getsize > 1000` terlalu tinggi. Segment pendek (gap 0.05s, cue 0.17s dengan source 5 frame H.264) hasilkan file < 1KB → di-skip → gap di video stream → VLC/DaVinci "berhenti lama" saat jump.

2. **Slow-mo ekstrim (factor > 2x)**: `setpts=(PTS-STARTPTS)*14` untuk cue 0.17s → audio 2.39s = 5 frame diulang 14x = stop-motion weird. User lihat "kayak foto berhenti lama, ada yg diulang-ulang".

### Fix test #16 (commit `09234ac`, 5 Okt 11:30)

1. **Lower skip threshold** 1000 → 100 bytes. Segment pendek tetap masuk concat.

2. **Cap slow-mo 2x + tpad freeze** untuk cue dengan factor > 2x:
   ```python
   MAX_SLOWMO_FACTOR = 2.0
   if factor > MAX_SLOWMO_FACTOR and task['type'] == 'cue':
       capped_dur = mp4_dur * MAX_SLOWMO_FACTOR
       freeze_dur = target_dur - capped_dur
       vf = f'fps=30,setpts=(PTS-STARTPTS)*2.0,tpad=stop_mode=clone:stop_duration={freeze_dur}'
   ```
   Hasil: 0.34s slow-mo 2x (smooth, 10 frame) + 2.05s freeze di last frame. Lebih halus daripada 5 frame diulang 14x.
   Hanya berlaku untuk cue (bukan gap/tail). Gap tetap pakai setpts normal.

---

## 📚 Sebelumnya: Bug History Detail (Test #1-#8)

### Gejala lama
- VLC: frame berhenti, suara TTS ada
- DaVinci: video merah (Media Offline), audio waveform OK
- SRT terlihat 3 jam 35 menit di DaVinci (sebenarnya 2 jam 36 menit)

### Root Cause
**FFmpeg concat dengan stream copy + B-frames = non-monotonic DTS**

B-frames (bidirectional frames) punya DTS yang bisa mundur (menengok frame setelahnya). Saat `setpts` slow-mo, timestamp jadi non-monotonic → FFmpeg warning → video patah/diulang.

### Timeline Debug (8 iterasi fix, 4 Okt 21:00 → 5 Okt 03:00 WIB)

| Test # | Strategi | Hasil | Penyebab Gagal |
|---|---|---|---|
| #1 | Filter complex inline (8268 segments) | frame=0, stuck | Memory 40GB, FFmpeg swap |
| #2 | Two-pass rendering (file-based segments) | Sukses, tapi video rusak | Stream copy + B-frames |
| #3 | Cumulative offset + stream copy | 491 DTS warnings | B-frames tetap bermasalah |
| #4 | Re-encode Pass 2 + source 360p rusak | Frame berhenti lama | Source video rusak (AV1→H.264 360p) |
| #5 | Re-encode + source 5min stream copy | Masih DTS warnings | jsDelivr cache, user dapat versi lama |
| #6 | H.264 source + VideoToolbox + `-bf 0` | Masih DTS warnings | -fps_mode cfr + -video_track_timescale konflik |
| #7-#8 | Hapus -fps_mode cfr + -video_track_timescale | Masih DTS warnings | setpts=PTS-STARTPTS di Pass 2 hapus concat offset |
| #9 | Stream copy Pass 2 + B-frames enabled | Non-monotonic DTS 11299 frame dup | B-frames + stream copy |
| #10 | Stream copy Pass 2 + `-bf 0` | DTS warnings 0, durasi OK | ✓ Fix DTS, tapi visual masih jelek (test #15 issue) |

### 8 Fix yang Diimplementasi di `retime-video.py` (lama)

| # | Fix | Dari Riset | Dampak |
|---|---|---|---|
| 1 | Two-pass rendering (file-based segments) | Memory issue | Pass 1 parallel, Pass 2 concat |
| 2 | `-filter_complex_script_filename` → `-/filter_complex` | FFmpeg 7+ compat | Fix "Unrecognized option" |
| 3 | Filter segments di luar range video input | Test video pendek | Fix 8267/8267 gagal |
| 4 | Hapus `-reset_ts zero` (invalid di FFmpeg 7+) | Sandbox test | Fix "Unrecognized option" |
| 5 | Hapus `-vsync cfr` (deprecated FFmpeg 5.1+) | Sandbox test | Fix "Unrecognized option" |
| 6 | `setpts=(PTS-STARTPTS)*factor` (bukan `/factor`) | Sandbox test | Fix slow-mo jadi fast-forward |
| 7 | `-t target_dur` (bukan `mp4_dur`) | Sandbox test | Fix output terpotong |
| 8 | **M1 Optimization**: `-hwaccel videotoolbox` + `-bf 0` + `fps=30` + `output_ts_offset` | ffmpeg-micro + VoiceStudio | Hardware decode/encode + fix DTS + VFR guard + cumulative offset |

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
'-vf', 'fps=30,setpts=(PTS-STARTPTS)*{factor}',  # VFR guard
'-output_ts_offset', '{cumulative_offset}',     # Cumulative timestamp

# Pass 2 (concat + stream copy):
'-c:v', 'copy',                  # No re-encode
'-bf', '0',                      # Inherited from Pass 1 segments
'-shortest',                     # Stop saat audio dub habis
'-timecode', '00:00:00:00',      # Fix DaVinci timecode offset
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
| 5 menit (233 segments) | ~10 menit | ~3 detik | ~10 menit |
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
| **VoiceStudio** (github.com/debpalash/VoiceStudio, commit 990f0627, 5 Okt 2026) | Pattern A (slack abs), C (15ms fade), D (peak norm -2dBFS), G (SRT de-overlap). Riset 36 file di `/scripts/voicestudio-study/`. |

### Filosofi yang Dipertahankan

> "atempo = jalan buntu. PUNCAK AUDIO ADALAH BEBAS DARI PENJARA = DUB YG ADA DI WEB KITA"

- atempo (audio stretch) = robot ekstrem untuk cue pendek
- DUB mode (SRT = ground truth) = audio natural, video slow-mo
- SRT + WAV = ground truth, MP4 ngikut SRT
- "Dub = hulu. Kalau hulu sampah = hasil sampah, kalau hulu baik = hasil baik."

### DaVinci Resolve Timecode Offset

DaVinci default "Start Timecode" = `01:00:00:00` (SMPTE standar).
User lihat 3 jam 35 menit di DaVinci = offset +1 jam dari timecode setting.

**Fix di DaVinci**: Project Settings → Master Settings → "Start Timecode" = `00:00:00:00`
**Fix di script**: `-timecode 00:00:00:00` di output MP4 (sudah ada sejak test #10).

---

## ✅ Yang Sudah Jalan (Production)

### 1. Web App (https://srt-splitter.vercel.app/)
- **Split SRT** — by durasi atau karakter
- **Translate** — Google Translate + OpenAI
- **TTS Mode ON** — sync ke SRT, crossfade, durasi = SRT
- **TTS Mode OFF** — natural sequential, speed 1.0x-2.0x
- **🔴 DUBBING Mode v2.0** — audio natural → SRT baru → ground truth
  - VoiceStudio Pattern A: slack absorption (extend slot ke gap-guard 50ms)
  - VoiceStudio Pattern C: 15ms fade in/out per cue (prevent click)
  - VoiceStudio Pattern D: peak normalize -2 dBFS per cue (loudness konsisten)
  - VoiceStudio Pattern G: SRT de-overlap + BOM strip + formatTime rounding fix
  - Schema v2.0: chunks, fittedCues, params, sampleRate, gapGuardSec, skippedCues, audioRate, videoRatio, status, overflowSec, head/tail types
  - Backward compat v1.0: `points` = `chunks` alias, `factor` = `videoRatio` alias
- Trim silence (ThioJoe algoritma) untuk kurangi robot
- Speed up + slow down mode (Voicertool filosofi)
- Standar nama file download: `{prefix}-audio-jd-dub.wav`, `{prefix}-srt-dub.srt`, `{prefix}-retime-map.json`

### 2. Python Scripts (lokal, untuk produksi final)
- **`dubbing-tui.py`** — TUI interaktif (questionary, arrow keys), pakai argumen baru
- **`retime-video.py`** v6 — two-pass rendering:
  - Pass 1: Render per-segment (parallel 4 workers) dengan `-bf 0` + `output_ts_offset` + `fps=30` VFR guard
  - Pass 1: Cap slow-mo 2x + `tpad=stop_mode=clone` freeze untuk cue factor > 2x (FIX test #15)
  - Pass 2: Concat + stream copy + mix audio (instant, ~3 detik)
  - Pass 2: Skip threshold 100 bytes (FIX test #15, sebelumnya 1000)
  - Support: `--srt-original/--srt-dub/--audio-dub` (baru) + `--srt-mandarin/--srt-jawa/--audio-jawa` (alias deprecated)
  - Support: `--preset fast/medium/slow`, `--workers 4`, `--encoder h264_videotoolbox`, `--video-only`
  - Resume support (segment yang sudah ada di-skip)
- **`separate-audio-sfx.py`** — Demucs wrapper untuk SFX separation
- **`srt-to-audio.py`** — alternatif TTS lokal
- **`rapikan-jawa.py`** + `tambah-krama.py` — rapikan SRT Jawa
- **`test-dubbing-v2-schema.py`** — sanity test untuk v2.0 schema (6/6 tests pass)

### 3. Documentation
- `README.md` — overview project + visi + standar nama file
- `docs/PROJECT_VISION.md` — visi digitalisasi bahasa + roadmap 2 tahun
- `docs/PROGRESS.md` — dokumen ini (status terkini)
- `docs/EDGE_TTS_PROXY.md` — cara kerja Edge TTS proxy
- `scripts/tutor-dubbing-workflow.md` — workflow pemula buta Python (Fase 1-5 + FAQ + Checklist)
- `scripts/tutor-python-lokal.md` — setup Python lokal
- `scripts/README.md` — index Python scripts
- `worklog.md` — log development lengkap (Task 1-7)

---

## 📊 User Test Summary

### Setup User
- MacBook Pro (Apple Silicon, M1/M2)
- Python 3.14.7 via Homebrew
- FFmpeg 9.0.2 via Homebrew
- venv di `~/Dubbing/venv/`

### Test #15 (5 Okt 2026 11:00 WIB) — sub-ID 5 menit
- SRT ori: 160 cues (srt-id-original.srt, split 5 menit pertama)
- SRT dub: 160 cues (srt-id-dub.srt, dari DUB web v2.0)
- Audio dub: 7:23 (audio-id-dub.wav, dari DUB web v2.0)
- MP4 source: 5 menit (mp4-ori-test-5min.mp4, H.264)
- Total segments: 233 (116 cue + 116 gap + 1 tail)
- Re-encode: 215, Stream copy: 18
- Pass 1: 1147s (~19 menit), 0 gagal
- Pass 2: stream copy, ~3 detik, 0 DTS warnings ✓
- Output: mp4-id-final.mp4, 175.9 MB, durasi 5:24 ✓
- Skip: 24/233 segments (10.3%) — BUG
- Visual: "kayak foto berhenti lama, diulang" — BUG slow-mo 14x stop-motion

### Test #16 (5 Okt 2026 11:30 WIB) — sub-ID 5 menit, fix tpad + skip 100B
- Status: ⏳ In progress (Pass 1 0%)
- Fix: cap slow-mo 2x + tpad freeze untuk cue factor > 2x, skip threshold 1000→100 bytes

---

## 🔜 Next Steps (Prioritas)

### Priority 1: Render video jalan (test #16 → #17 kalau perlu)
- Target: video smooth, no "foto berhenti", no stop-motion weird
- Kalau tpad fix jalan → lanjut ke test full season (S7-id, 2.5 jam)
- Kalau masih gagal → riset alternatif (minterpolate frame blending, atau re-encode Pass 2 penuh)

### Priority 2: Kamus Bahasa Jawa JSON (besok, setelah render jalan)
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

**Estimasi effort:** 5-7 hari kerja

### Priority 3: Workflow Multi-Bahasa (setelah kamus Jawa)
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

**Estimasi effort:** 2-3 hari

### Priority 4: Aksara Jawa OCR (Bulan 13-15 roadmap)
- TrOCR fine-tune dengan 1000 sample aksara Jawa
- Training 20 jam GPU di Colab

### Priority 5: Kawi TTS (Bulan 16-18 roadmap)
- Rekrut dosen Sastra Jawa (UGM/UNY)
- Rekam bacaan Negarakertagama (10 jam Kawi)
- Train Kawi TTS (pakai Jawa modern sebagai base)

### Future: GPU Acceleration (kalau skala produksi besar)
**Trigger**: Kalau render 6 season sekaligus (~7 jam di Mac, ~1.5 jam di Colab paralel)
**Opsi:** Google Colab Free (T4 GPU) atau PC RTX 4070/4090

---

## 🗂️ Aset User (Tidak Di-Commit ke Repo)

File user pribadi, di MacBook lokal (dengan standar nama):
- `~/Dubbing/mp4-ori-test-5min.mp4` — source MP4 (5 menit test, H.264)
- `~/Dubbing/srt-id-original.srt` — SRT Indonesia source (160 cues, 5 menit pertama)
- `~/Dubbing/srt-id-dub.srt` — SRT dub result (160 cues, dari DUB web v2.0)
- `~/Dubbing/audio-id-dub.wav` — audio dub result (7:23, dari DUB web v2.0)
- `~/Dubbing/retime-map.json` — JSON v2.0 (chunks + fittedCues + params, dari DUB web)
- `~/Dubbing/mp4-id-final.mp4` — HASIL RENDER test #15 (175.9 MB, 5:24, visual rusak)
- `~/Dubbing/venv/` — virtual environment Python

Standar nama file (konvensi project):
| File | Format | Contoh |
|---|---|---|
| MP4 source | `mp4-ori-{name}.mp4` | `mp4-ori-test-5min.mp4` |
| SRT source | `srt-{lang}-original.srt` | `srt-id-original.srt`, `srt-mn-original.srt` |
| SRT dub | `srt-{lang}-dub.srt` | `srt-id-dub.srt`, `srt-jw-dub.srt` |
| Audio dub | `audio-{lang}-dub.wav` | `audio-id-dub.wav`, `audio-jw-dub.wav` |
| Output final | `mp4-{lang}-final.mp4` | `mp4-id-final.mp4`, `mp4-jw-final.mp4` |

Recording Zoom H6 (260 jam total, di luar repo):
- 37 video panatacara (~150 jam)
- 110 episode Kaladete Podcast (~110 jam)
- Akses komunitas Permadani (100 siswa/tahun validator)

---

## 📝 Catatan untuk AI Next Time Buka

1. **Test #15 milestone**: DTS warnings = 0 (fix DTS complete), durasi 5:24 OK. Tapi visual masih rusak karena skip 10.3% + slow-mo 14x stop-motion. Test #16 jalan dengan fix tpad + skip 100B.
2. **Filosofi**: "dub = hulu" — kualitas dub web menentukan kualitas seluruh pipeline. Garbage in = garbage out.
3. **Standar nama file** sudah diterapkan: `mp4-ori-`, `srt-{lang}-original.srt`, `srt-{lang}-dub.srt`, `audio-{lang}-dub.wav`, `mp4-{lang}-final.mp4`.
4. **Schema v2.0** sudah ter-deploy: chunks, fittedCues, params, sampleRate, gapGuardSec, skippedCues, audioRate, videoRatio, status, overflowSec, head/tail types. Backward compat v1.0 dengan `points` alias.
5. **Python argumen baru**: `--srt-original`/`--srt-dub`/`--audio-dub` (standar), `--srt-mandarin`/`--srt-jawa`/`--audio-jawa` (alias deprecated, masih jalan).
6. **Next priority**: Kalau test #16 sukses → test full season S7-id. Kalau gagal → riset minterpolate atau re-encode Pass 2 penuh. Setelah render jalan → baru kerjakan kamus Jawa (besok).
7. **Filosofi user**: "ada uang atau tidak, tetap dikerjakan step by step, terdokumentasi rapi"
8. **Visi besar**: 700 bahasa Indonesia, 169 terancam punah. Project ini prototype digitalisasi.
9. **Sandbox**: Code up-to-date dengan GitHub. PAT user cached di credential helper.
10. **VoiceStudio riset**: 36 file di `/scripts/voicestudio-study/` (gitignored). Latest commit main = 990f0627. Lihat worklog Task 7-a untuk detail 15 pattern + 8 worth adopting.

---

## 📅 Timeline Update

- **4 Okt 2026, 21:00 WIB**: Initial PROGRESS.md, test #1-#8 (video rusak DTS)
- **5 Okt 2026, 02:55 WIB**: UPDATE — render S7-id.mp4 full season SUKSES 3.8GB 2h30m, tapi video rusak (332 DTS warnings, timecode offset)
- **5 Okt 2026, 03:00-08:00 WIB**: 8 iterasi fix DTS (test #9-#14)
- **5 Okt 2026, 08:30 WIB**: Update PROGRESS.md — bug history + M1 optimization + riset referensi
- **5 Okt 2026, 10:00 WIB**: Dub web v2.0 ter-deploy (VoiceStudio adoptions + JSON v2.0 schema)
- **5 Okt 2026, 10:30 WIB**: Standar nama file diterapkan di web + docs + Python
- **5 Okt 2026, 11:00 WIB**: Test #15 sub-ID 5 menit — DTS=0 OK, durasi 5:24 OK, TAPI visual rusak (skip 24 seg + slow-mo 14x stop-motion)
- **5 Okt 2026, 11:30 WIB**: Test #16 sub-ID 5 menit — fix tpad + skip 100B (commit `09234ac`), in progress
- **Next update**: Setelah test #16 selesai + audit visual

