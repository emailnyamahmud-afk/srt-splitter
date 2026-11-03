# Talking Head TUI #16 — SadTalker via Replicate (green screen preserved)

> Status: **UNTESTED** v1.0 (3 Nov 2026, code di GitHub, belum diuji di Mac).
> Untuk workflow KONTEN (bukan pipeline dubbing). Pakai foto green screen + narasi JV → talking head video.

## TL;DR

```bash
# Setup (sekali saja)
echo "REPLICATE_API_TOKEN=r8_xxx" >> /Volumes/HDD/Dubbing/.env
pip3 install replicate requests questionary

# Pakai
cd ~/Dubbing && source venv/bin/activate
python3 talkinghead-tui.py
# → 6 step TUI: foto green screen → narasi-JV.wav → output path → preprocess → still → enhancer
# → Output: HDD/konten/{audio-stem}-talking-green.mp4 (green screen DIPERTAHANKAN)
# → Edit manual: chroma key → composite background → final-konten.mp4
```

## 2 file yang ditambahkan (TIDAK ubah file lama)

| File | Fungsi |
|------|--------|
| `scripts/talkinghead-tui.py` v1.0 | TUI utama (6 step questionary). Cari foto + audio, pilih preprocess mode, panggil backend. |
| `scripts/talkinghead_backend.py` | Backend modul: panggilan ke Replicate API (model `cjwbw/sadtalker`), retry timeout/network, download MP4. |

**File lama yang TIDAK diubah**: semua 15 TUI lain, config.py, mix-tui.py, review-mix-tui.py, konten-tui.py, gemini-tts-tui.py — semua utuh.

## Workflow untuk konten (BUKAN dubbing)

```
[STEP 1] naskah.txt (Jawa halus, mis. naskah sejarah / MC adat)
    ↓ gemini-tts-tui v1.1 Narration mode (JV, Cruz + jawa-halus-mc)
    → narasi-jawa.wav (HDD/tts/)

[STEP 2] foto green screen half-body (mis. amat-avatar.jpg)
    + narasi-jawa.wav
    ↓ talkinghead-tui v1.0 (preprocess=full, still, gfpgan)
    → HDD/konten/{name}-talking-green.mp4
      (background green screen DIPERTAHANKAN, wajah bicara sync)

[STEP 3] User edit manual di editor (Final Cut / DaVinci / Premiere):
    - Chroma key green (hilangkan green screen)
    - Composite dengan background baru:
      • Foto sejarah (untuk konten tokoh/sejarah)
      • Kantor / ruang adat (untuk MC Jawa)
      • Video B-roll (untuk konten dokumenter)
    - Tambah text overlay (judul, nama tokoh, dll) — opsional
    - Export → final-konten.mp4 (siap YouTube)
```

## Kenapa Replicate (BUKAN M1 lokal)?

SadTalker di M1 sangat bermasalah:
- Python 3.8 strict (versi baru break `basicsr`, `dlib`)
- Banyak code hardcode `cuda:0` / `.cuda()` → perlu manual patch ke `mps` atau `cpu`
- Tidak ada `requirements_macOS.txt` resmi (beda dengan LivePortrait)
- Issue GitHub #526 (MPS support partial) masih open
- Community bilang "runs very slow" di M1 — artikel optimization "3-5x speedup" = baseline lambat
- Estimasi M1 lokal: 2-5 menit per 1 menit video (512px)

Replicate cloud:
- Model: `cjwbw/sadtalker` (https://replicate.com/cjwbw/sadtalker)
- Hardware: A100 80GB
- Speed: **~17 detik per run** (vs 2-5 menit M1 lokal)
- Cost: ~$0.05-0.20 per video (pay-as-you-go, free $0.10 credit untuk test)
- Untuk workflow konten sejarah (volume rendah-sedang) = sangat reasonable

## Cara pakai

### 1. Dapatkan Replicate API token
- Buka https://replicate.com/account/api-tokens
- Sign up (free $0.10 credit untuk test)
- Generate API token (format `r8_xxx...`)

### 2. Simpan API token di HDD `.env` (recommended)
```bash
echo "REPLICATE_API_TOKEN=r8_xxx..." >> /Volumes/HDD/Dubbing/.env
# config.py load_env() akan load otomatis saat TUI start
```

Atau set di env session (sementara):
```bash
export REPLICATE_API_TOKEN=r8_xxx...
```

### 3. Install dep
```bash
cd ~/Dubbing && source venv/bin/activate
pip3 install replicate requests questionary
# ffmpeg sudah install kalau pakai edge-tts-tui / mix-tui
```

### 4. Jalankan TUI
```bash
cd ~/Dubbing && source venv/bin/activate
python3 talkinghead-tui.py
```

6 step TUI:

| Step | Pilihan | Default |
|------|---------|---------|
| 1 | Source image (.jpg/.png, foto green screen half-body) | Glob dari `HDD/konten/`, `HDD/input/`, cwd |
| 2 | Driven audio (.wav, dari gemini-tts-tui #15 Narration JV) | Glob dari `HDD/tts/`, cwd |
| 3 | Output MP4 path | `HDD/konten/{audio-stem}-talking-green.mp4` |
| 4 | Preprocess mode (full / extfull / crop / extcrop / resize) | **full** (recommended untuk green screen) |
| 5 | Still mode (yes / no) | **yes** (kurangi gerakan kepala, cocok presenter formal) |
| 6 | Enhancer (gfpgan / none) | **gfpgan** (tajpkan gigi + mata, penting untuk clean chroma key) |

### 5. Edit manual (chroma key)
Output MP4 = talking head dengan green screen DIPERTAHANKAN. User edit di:
- **DaVinci Resolve** (free, recommended untuk Mac)
- Final Cut Pro
- Adobe Premiere
- CapCut

Langkah:
1. Tambah chroma key effect (DaVinci: `OFX > ResolveFX Chroma Keyer`)
2. Pick green screen (drop eyedropper ke green)
3. Composite dengan background baru
4. Tambah text overlay (opsional)
5. Export → `final-konten.mp4` (siap upload YouTube)

## Preprocess mode — penjelasan detail

| Mode | Behavior | Cocok untuk green screen? |
|------|----------|---------------------------|
| `full` (default) | Animasi wajah → paste back ke ORIGINAL background | ✅ Green screen dipertahankan |
| `extfull` | full + extra margin (untuk head tilt banyak) | ✅ Green screen dipertahankan |
| `crop` | Face only, no background | ❌ Green screen hilang, output = face centered |
| `extcrop` | crop + extra margin | ❌ Green screen hilang |
| `resize` | Full image scale, animate di atasnya | ⚠ Hybrid, tidak ideal |

**Saran**: untuk workflow green screen, selalu pakai `full` (default). Kalau head tilt terlalu banyak di pinggir frame, ganti ke `extfull`. JANGAN pakai `crop` / `extcrop` untuk green screen.

## Still mode

- **yes** (`--still`): Kurangi gerakan kepala. Cocok untuk:
  - Presenter formal (tangan clasped di depan, postur kaku)
  - Foto dengan tangan terlihat (gerakan kepala kecil = tangan tidak banyak gerak)
  - Narasi dokuser / MC adat
- **no** (`--no-still`): Lebih natural head movement. Cocok untuk:
  - Dialog dramatis (memerankan emosi)
  - Foto close-up wajah (tanpa tangan)
  - Storytelling dengan ekspresi banyak

## Enhancer

- **gfpgan** (default): Tajpkan gigi + mata. Penting untuk green screen workflow:
  - Setelah chroma key, edge wajah harus tajam (kalau blur, fringe hijau kelihatan)
  - GFPGAN face restoration = quality 512px, detail gigi + mata crisp
- **none**: Skip enhancement. Lebih cepat ~30%, tapi wajah bisa blur di output.

## Limit Replicate (per Nov 2026)

- Free credit: $0.10 untuk test (~2-5 video short)
- Pay-as-you-go: ~$0.05-0.20 per video (tergantung durasi)
- Concurrency: 1 request per token (paralel butuh multiple tokens)
- Timeout: API call max 5 menit (sudah handle di backend)
- Untuk video narasi 10 menit: cost ~$1-3 per video (masih murah untuk konten sesekali)

## Output file (compatible dengan pipeline lain)

```
HDD/konten/
└── {audio-stem}-talking-green.mp4    ← talking head dengan green screen preserved
                                          ↓
                                       User edit manual (chroma key + composite)
                                          ↓
                                       final-konten.mp4 (siap YouTube)
```

**Kompatibel dengan**:
- `konten-tui v1.0` (#14) — kalau mau pakai background = static image (Ken Burns)
- `review-mix-tui v1.0` (#13) — kalau mau pakai background = video B-roll
- `mix-tui v3.10` (#7) — kalau mau burn text overlay + force 1080p

## Test di sandbox (sudah dilakukan)

```
✓ Syntax OK (ast.parse both files)
✓ Backend CLI: --list-modes (5 preprocess mode), --list-enhancers (2 option)
✓ TUI no-API-key: error message jelas + instruksi setup
✓ TUI 6 step flow: foto green screen → narasi.wav → output → preprocess → still → enhancer
✓ Ringkasan: rapi, semua parameter tampil
✓ Konfirmasi abort: TUI exit cleanly
✓ Backend retry: timeout/network/5xx → 10s/30s/60s backoff, non-retryable → fail fast
```

## Test plan sebelum declare "production"

1. [ ] Test 1 video pendek (10 detik narasi Jawa) dengan foto `amat-avatar.jpg` → cek hasil SadTalker
2. [ ] Cek green screen masih preserved (bukan hitam/bukan crop face only)
3. [ ] Cek lip sync audio Jawa (Cruz + jawa-halus-mc hasilnya bagus?)
4. [ ] Cek quality GFPGAN (gigi + mata tajam?)
5. [ ] Chroma key di DaVinci/Premiere → background bersih gak ada green fringe?
6. [ ] Composite dengan background baru (coba 1 background sejarah) → cek hasil
7. [ ] Test fallback: kalau Replicate API timeout/error → retry behavior OK?
8. [ ] Test paralel: 2 instance talkinghead-tui (kalau Replicate API support concurrency — butuh multiple tokens)
9. [ ] Cost tracking: berapa $ per 1 video 10 menit? 1 menit?
10. [ ] VLC playback test final-konten.mp4 → cek audio quality end-to-end

Setelah semua test lulus + user VLC feedback OK → update status ke "Production" di docs.

## Yang TIDAK saya lakukan (biar kamu putuskan)

1. **Implementasi alternatif M1 lokal**: SadTalker / Wav2Lip / Hallo — tidak saya kerjakan karena:
   - SadTalker M1: effort install + patch CUDA→MPS tidak worth it (community bilang very slow)
   - Wav2Lip: user feedback "ekspresi cuma mulut, gak bagus" (ekspresi kepala terbatas)
   - Hallo: perlu test MPS support dulu
   Kalau Anda mau saya kerjakan salah satu → kasih tahu.

2. **Backend lokal fallback**: TUI #16 cuma pakai Replicate. Kalau Replicate down / quota habis →
   user tidak bisa generate. Saran: bikin flag `--backend local-replicate | local-wav2lip | local-sadtalker`
   — TAPI tunggu sampai ada need + user test dulu.

3. **`.env.example`**: belum saya tambah `REPLICATE_API_TOKEN=` line. Saran tambah:
   ```bash
   # Talking Head TUI #16 (opsional — untuk talkinghead-tui.py via Replicate SadTalker)
   REPLICATE_API_TOKEN=
   ```

4. **TUI #16 dalam pipeline docs**: sudah saya tambah section "TALKING-HEAD" di pipeline. Kalau Anda
   mau tambah workflow alternatif (mis. HeyGen cloud / Hedra) → saran bikin TUI baru #17.

## Anti-amnesia protocol (sesuai AGENTS.md)

Kalau AI di sesi berikutnya lupa context:
1. Baca `scripts/TALKINGHEAD.md` (file ini) dulu
2. Baca `scripts/talkinghead-tui.py` baris 1-50 (docstring) untuk workflow
3. Baca `scripts/talkinghead_backend.py` baris 1-50 untuk API kontrak
4. **JANGAN** hapus/ubah `edge-tts-tui.py` v7.5 — tetap production default (SRT + Narasi, ID only)
5. **JANGAN** hapus/ubah `gemini-tts-tui.py` v1.1 — TUI #15, Narration mode JV feed TUI #16
6. Status TUI #16: **UNTESTED** (code di GitHub, belum diuji di Mac) sampai user VLC-feedback OK
7. **JANGAN** amnesia soal workflow: TUI #16 = workflow KONTEN (bukan dubbing), foto green screen + narasi JV
8. **JANGAN** amnesia soal preprocess mode: `full` = preserve green screen, `crop` = face only (gak cocok green screen)
9. **JANGAN** amnesia soal workflow: AI sandbox → push GitHub → user pull → test → kalau error → AI fix → push
