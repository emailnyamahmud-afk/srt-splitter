# Gemini TTS — OPSI TAMBAHAN untuk pipeline dubbing

> Status: **EXPERIMENTAL** v1.1 (2 Nov 2026). edge-tts-tui.py v7.5 tetap production default.
> 2 mode: **SRT** (Dub per cue) + **Narration** (1 naskah → 1 WAV). Indonesia + Jawa.

## TL;DR

```bash
# Setup (sekali saja)
echo "GEMINI_API_KEY=AIza..." >> /Volumes/HDD/Dubbing/.env
pip3 install google-genai

# Pakai
python3 gemini-tts-tui.py
# → Mode selection: SRT / Narration
# → SRT mode:        7 step TUI (SRT → output → bahasa → voice → instruction → Smart Fit → prefix)
# → Narration mode:  6 step TUI (naskah.txt → output → bahasa → voice → instruction → rate)
# → Output:
#     SRT:       HDD/tts/{prefix}-audio-id-dub.wav  (24kHz mono 16-bit, mix-tui compatible)
#     Narration:  HDD/tts/{stem}-narasi.wav           (48kHz stereo 16-bit, review-mix-tui compatible)
```

## 2 file yang ditambahkan (TIDAK ubah file lama)

| File | Fungsi |
|------|--------|
| `scripts/gemini-tts-tui.py` v1.1 | TUI utama 2-mode (SRT + Narration). Port algoritma audio dari `edge-tts-tui.py v7.5`. |
| `scripts/gemini_tts_backend.py` | Modul backend: panggilan ke Google Gemini API (legacy `generate_content_stream`), 31 voice (30 resmi + Cruz), 429/RESOURCE_EXHAUSTED retry, 8 instruction template (4 ID + 4 JV) + custom. |

**File lama yang TIDAK diubah**:
- `scripts/edge-tts-tui.py` v7.5 — production default (SRT + Narration mode, Indonesia only)
- `scripts/srt-to-audio.py` — versi lama
- `scripts/config.py` — dipakai apa adanya
- `scripts/mix-tui.py` — glob pattern `{prefix}-audio-id-dub.wav` match
- `scripts/review-mix-tui.py` — pakai `{stem}-narasi.wav`

## Kapan pakai Gemini vs Edge

| Skenario | Pakai | Alasan |
|----------|-------|--------|
| Bahasa Indonesia, SRT umum (cue film/drama) | **Edge TTS** | Free unlimited, paralel 2-3 instance, stabil |
| Bahasa Indonesia, narasi dokumenter | **Edge TTS** (v7.5 main_narration) | Production-tested |
| Bahasa Jawa, SRT (krama/ngoko) | **Gemini** | Cruz + jawa-halus-mc → user tested OK |
| Bahasa Jawa, narasi (konten, video pendidikan) | **Gemini** | User sudah test narasi Jawa, hasil bagus |
| Karakter spesifik (MC adat, dokuser, dialog dramatis) | **Gemini** | Instruction prompt lebih fleksibel dari Edge pitch slider |
| Bahasa eksotis (Italia, Jepang, dll) | **Gemini** | 130 bahasa, model dilatih cross-lingual |
| Batch besar (ratusan cue, banyak film) | **Edge TTS** | Gemini free tier ~5-15 RPM, ~100-250 RPD |
| Workflow produksi stabil Indonesia | **Edge TTS** | Production-tested, gak perlu API key |
| Butuh pitch adjustment presisi | **Edge TTS** | Edge punya pitch slider (-15Hz s/d +15Hz) |
| Butuh paralel 3 instance Mac 16GB | **Edge TTS** | Gemini rate-limit bikin paralel gak efektif di free tier |

## Cara pakai

### 1. Dapatkan API key
- Buka https://aistudio.google.com/apikey
- Create API key (free tier tersedia, no credit card)
- Copy API key (format `AIza...`)

### 2. Simpan API key di HDD `.env` (recommended)
```bash
echo "GEMINI_API_KEY=AIzaSy..." >> /Volumes/HDD/Dubbing/.env
# config.py load_env() akan load otomatis saat TUI start
```

Atau set di env session (sementara):
```bash
export GEMINI_API_KEY=AIzaSy...
```

### 3. Install dep
```bash
cd ~/Dubbing
source venv/bin/activate
pip3 install google-genai
# (questionary + numpy + ffmpeg sudah install untuk edge-tts-tui)
```

### 4. Jalankan TUI
```bash
cd ~/Dubbing
source venv/bin/activate
python3 gemini-tts-tui.py
# → Pilih Mode: SRT / Narration
```

### Mode 1: SRT (Dub per cue dari subtitle)

7 step TUI:

| Step | edge-tts-tui.py v7.5 SRT | gemini-tts-tui.py v1.1 SRT |
|------|---------------------------|----------------------------|
| 1 | Pilih SRT | Pilih SRT (sama) |
| 2 | Output dir | Output dir (sama) |
| 3 | Voice (4 Edge: Ardi/Gadis/Dimas/Siti) | **Bahasa** (Indonesia / Jawa) |
| 4 | Pitch (-15Hz s/d +15Hz) | **Voice** (31 Gemini: 30 resmi + Cruz) |
| 5 | Smart Fit cap | **Instruction** (filtered per bahasa pilihan step 3) |
| 6 | Prefix (lock file) | Smart Fit cap (default 1.5x) |
| 7 | — | Prefix (lock file, paralel-safe) |

Output: `HDD/tts/{prefix}-audio-id-dub.wav` (24kHz mono 16-bit)
→ mix-tui.py langsung nemu via glob

### Mode 2: Narration (1 naskah plain text → 1 WAV)

6 step TUI:

| Step | edge-tts-tui.py v7.5 Narration | gemini-tts-tui.py v1.1 Narration |
|------|--------------------------------|---------------------------------|
| 1 | Pilih naskah .txt | Pilih naskah .txt (sama) |
| 2 | Output WAV | Output WAV (sama) |
| 3 | Voice (4 Edge) | **Bahasa** (Indonesia / Jawa) |
| 4 | Rate (+0% / -10% / +10%) | **Voice** (31 Gemini) |
| 5 | (langsung generate) | **Instruction** (filtered per bahasa) |
| 6 | — | **Rate** (+0% / -10% / +10%) |

Algorithm:
1. Read naskah.txt → split per paragraf (double newline)
   Kalau 1 paragraf > 5000 chars → split per kalimat panjang (≤3000 chars)
2. Per paragraf: generate TTS via Gemini (rate dari pilihan user)
3. Concat MP3 → WAV (ffmpeg, **48kHz stereo 16-bit** — match edge-tts-tui narration output)
4. Output: `HDD/tts/{stem}-narasi.wav`

→ Pakai untuk `review-mix-tui.py` (mix MP4 + JSON + narasi.wav)

## Voice — 30 resmi Google + 1 tested

Default: **Cruz** (dari Extended Voice Library, TIDAK di 30 resmi — tapi user sudah tes untuk Jawa halus, work untuk MC/adat).

Kalau Cruz tiba-tiba error di API, fallback terdekat untuk "pria dewasa berwibawa":
1. **Charon** — Informative, pria tenang
2. **Schedar** — Even, pria stabil
3. **Alnilam** — Firm, pria tegas
4. **Rasalgethi** — Informative, pria informatif

Lihat daftar lengkap: `python3 gemini_tts_backend.py --list-voices`

## Instruction templates (8 + custom)

### Bahasa Indonesia (4)
- `default` — natural, netral
- `id-narasi` — narasi dokumenter (pria hangat)
- `id-narasi-w` — narasi dokumenter (wanita hangat)
- `id-dialog` — dialog dramatis natural

### Bahasa Jawa (4)
- `jawa-halus-mc` — Panatacara / MC adat (pria berwibawa, lambat khidmat) — user tested
- `jv-narasi` — narasi (pria hangat, sedang)
- `jv-narasi-w` — narasi (wanita hangat, sedang)
- `jv-dialog` — dialog dramatis natural

### Custom
- `custom` — ketik sendiri

TUI otomatis filter pilihan berdasarkan bahasa yang dipilih (Step 3 di SRT mode / Step 3 di Narration mode).

Lihat daftar: `python3 gemini_tts_backend.py --list-instructions`

## Algorithm (sama dengan edge-tts-tui.py v7.5, beda backend)

### SRT mode (10 langkah):
```
1. Parse SRT → entries (start, end, text)
2. Per cue: generate natural TTS (rate +0%)
3. Trim silence (asymmetric -30 dB head/tail, 30ms padding)
4. Hitung need = naturalDur / cueDur
5. Kalau need <= 1.0 → pakai natural
6. Kalau need > 1.0 → re-generate dengan rate = min(need, cap)
   • Edge: rate string "+50%" (parameter langsung)
   • Gemini: instruction "Bicara 50% lebih cepat" (via prompt)
7. Peak normalize -2 dBFS
8. Stitch ke buffer pada cue.start (mix additive)
9. Crossfade 150ms kalau audio overflow cue next
10. Output: WAV 24kHz mono 16-bit PCM
```

### Narration mode (4 langkah, port dari edge-tts v7.5):
```
1. Read naskah.txt → split per paragraf (double newline)
   Kalau 1 paragraf > 5000 chars → split per kalimat (≤3000 chars)
2. Per paragraf: generate TTS (Gemini, rate dari pilihan user)
3. Concat MP3 → WAV (ffmpeg, 48kHz stereo 16-bit)
4. Output: 1 WAV panjang (48kHz stereo 16-bit)
```

## Paralel-safe (match edge-tts-tui v7.4)

Hanya SRT mode yang pakai lock file (paralel 2-3 instance). Narration mode = 1 file, tidak paralel.

- Lock file `tts/.{prefix}.lock` dengan PID
- Prefix auto-suggest kalau collision (`prefix-2`, `prefix-3`, ...)
- 429/RESOURCE_EXHAUSTED retry: 30s → 60s → 120s → skip + log
- Stale lock cleanup: PID mati → lock dihapus otomatis
- PID display di banner

**Catatan Gemini free tier**: ~5-15 RPM, ~100-250 RPD. Paralel instance hit quota yang sama → cepat kena limit. Berbeda dengan Edge TTS yang unlimited.

## Limit Gemini free tier (per Nov 2026)

| Tier | RPM | RPD | Cocok untuk |
|------|-----|-----|-------------|
| Free (AI Studio API key) | 5-15 | 100-250 | Test single, file pendek (<50 cue / narasi <10 paragraf) |
| AI Pro ($20/bln) | Higher quota di Playground | — | Iterasi cepat di Playground |
| Tier 1 (Cloud Billing) | 300 | 1000 | Batch sedang (50-500 cue / narasi 10-100 paragraf) |
| Tier 2 ($100+ spend) | 1000+ | 10000+ | Batch besar (ratusan file) |

Sumber: https://ai.google.dev/gemini-api/docs/rate-limits (cek resmi sebelum produksi)

## Output file (compatible dengan pipeline)

### SRT mode (compatible mix-tui.py):
```
HDD/tts/
├── {prefix}-audio-id-dub.wav          ← main output (24kHz mono 16-bit)
├── .cache/
│   ├── {prefix}-cue-0001-{hash}.mp3    ← per-cue cache (WAV walau ext .mp3)
│   ├── {prefix}-cue-0001-{hash}_smart_+50%.mp3  ← smart fit cache
│   └── ...
└── .{prefix}.lock                      ← lock file (auto-delete saat selesai)
```

### Narration mode (compatible review-mix-tui.py):
```
HDD/tts/
└── {naskah-stem}-narasi.wav            ← 1 WAV panjang (48kHz stereo 16-bit)
```

**Catatan cache SRT mode**: file simpan WAV (16-bit PCM) dengan extension `.mp3` supaya pola cache konsisten dengan `edge-tts-tui.py`. ffmpeg handle keduanya.

## Test di sandbox (sudah dilakukan)

```
✓ Syntax OK (ast.parse both files)
✓ Backend CLI: --list-voices (31 voice), --list-instructions (8 + custom)
✓ TUI no-API-key: error message jelas + instruksi setup
✓ SRT mode 7 step: SRT → output → bahasa → voice → instruction → Smart Fit → prefix → ringkasan
✓ Narration mode 6 step: naskah → output → bahasa → voice → instruction → rate → ringkasan
✓ Bahasa selection filter instruction template (id → 4 ID, jv → 4 JV)
✓ SRT ringkasan: Bahasa JV/Jawa muncul, Cruz + jawa-halus-mc default
✓ Narration ringkasan: Bahasa JV/Jawa muncul, 3 paragraf terdeteksi otomatis
✓ Lock file acquire/release/stale-detection (SRT mode) — match edge-tts v7.4
✓ Backend retry 429: 1+3=4 calls (retry 3x lalu fail)
✓ Backend non-429 error: fail fast (1 call, no retry)
✓ Backend 429 then success: 2 calls, output 48 KB WAV valid
✓ Audio utils: parse_srt, trim_silence_asymmetric, peak_normalize, mix_into_buffer — match edge-tts constants
```

## Yang TIDAK saya lakukan (biar kamu putuskan)

1. **Update `README.md`, `AGENTS.md`, `PROJECT_RULES.md`, `scripts/README.md`** — saya tidak sentuh docs projectmu. Saran commit kalau kamu setuju pakai:
   - `scripts/README.md`: tambah row di tabel → "13 TUI: gemini-tts-tui v1.1 (experimental, 2 mode: SRT + Narasi, ID + JV)"
   - `README.md`: tambah section "TUI 13: gemini-tts-tui v1.1 — OPSI TAMBAHAN Gemini 3.8 Flash TTS"
   - `AGENTS.md`: update status table
   - `PROJECT_RULES.md`: tambah aturan "Gemini TTS = opsi tambahan (SRT + Narasi, ID + JV), Edge TTS = production default (SRT + Narasi, ID only)"

2. **Curl download command** di README — belum saya tambah. Saran:
   ```bash
   curl -L -o gemini-tts-tui.py "https://raw.githubusercontent.com/emailnyamahmud-afk/srt-splitter/main/scripts/gemini-tts-tui.py"
   curl -L -o gemini_tts_backend.py "https://raw.githubusercontent.com/emailnyamahmud-afk/srt-splitter/main/scripts/gemini_tts_backend.py"
   curl -L -o GEMINI_TTS.md "https://raw.githubusercontent.com/emailnyamahmud-afk/srt-splitter/main/scripts/GEMINI_TTS.md"
   ```

3. **`.env.example`** — belum saya tambah `GEMINI_API_KEY=` line. Saran:
   ```bash
   # Gemini TTS (opsional — untuk gemini-tts-tui.py)
   GEMINI_API_KEY=
   ```

## Test plan sebelum declare "production"

### SRT mode:
1. [ ] Test 1 SRT Indonesia (10 cue) → compare dengan edge-tts → cek quality beda
2. [ ] Test 1 SRT Jawa halus (10 cue) Cruz + jawa-halus-mc → cek quality (sesuai ekspektasi user dari AI Studio test)
3. [ ] Test 1 SRT panjang (500 cue) → cek rate limit, ETA, retry behavior
4. [ ] Test paralel 2 instance SRT di Mac 16GB → cek lock file + RAM
5. [ ] Test fallback voice kalau Cruz gagal (Charon/Schedar/Alnilam)
6. [ ] Test mix-tui.py Mode E (Original) dengan output Gemini SRT → cek sync + ducking
7. [ ] Test mix-tui.py Mode A (Full + Stream) → cek ducking sidechain
8. [ ] VLC playback test 1 file SRT full → cek audio quality end-to-end

### Narration mode:
9. [ ] Test 1 naskah Indonesia pendek (3 paragraf) → cek quality
10. [ ] Test 1 naskah Jawa pendek (3 paragraf) Cruz + jv-narasi → cek quality (sesuai ekspektasi user)
11. [ ] Test 1 naskah Jawa MC/adat Cruz + jawa-halus-mc → cek quality (sesuai user test di AI Studio)
12. [ ] Test 1 naskah panjang (>5000 chars, auto-split per kalimat) → cek split OK
13. [ ] Test review-mix-tui.py dengan output Gemini Narasi → cek sync + ducking
14. [ ] VLC playback test 1 file narasi full → cek audio quality

Setelah semua test lulus + user VLC feedback OK → update status ke "Production (experimental)" di docs.

## Anti-amnesia protocol (sesuai AGENTS.md)

Kalau AI di sesi berikutnya lupa context:
1. Baca `scripts/GEMINI_TTS.md` (file ini) dulu
2. Baca `scripts/gemini-tts-tui.py` baris 1-90 (docstring) untuk algoritma 2-mode
3. Baca `scripts/gemini_tts_backend.py` baris 1-80 untuk API kontrak
4. Baca `scripts/edge-tts-tui.py` baris 1-100 + baris 1160+ (main_narration) untuk pattern reference
5. **JANGAN** hapus/ubah `edge-tts-tui.py` v7.5 — tetap production default (SRT + Narration, ID only)
6. **JANGAN** ubah `config.py` — pakai apa adanya
7. Status TUI ini: **EXPERIMENTAL** sampai user VLC-feedback OK
8. **JANGAN** amnesia soal 2-mode: Gemini TUI = SRT + Narration, ID + JV
9. **JANGAN** amnesia soal workflow: AI sandbox → push GitHub → user pull → test → kalau error → AI fix → push GitHub
