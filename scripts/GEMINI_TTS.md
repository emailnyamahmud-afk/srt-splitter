# Gemini TTS — OPSI TAMBAHAN untuk pipeline dubbing

> Status: **EXPERIMENTAL** v1.0 (2 Nov 2026). edge-tts-tui.py v7.5 tetap production default.
> Dipakai untuk skenario yang Edge TTS kurang bagus: Jawa halus, karakter spesifik, bahasa eksotis.

## TL;DR

```bash
# Setup (sekali saja)
echo "GEMINI_API_KEY=AIza..." >> /Volumes/HDD/Dubbing/.env
pip3 install google-genai

# Pakai (substitusi edge-tts-tui.py dengan gemini-tts-tui.py di workflow)
python3 gemini-tts-tui.py
# → 6 step TUI: SRT → output dir → voice → instruction → Smart Fit → prefix
# → Output: HDD/tts/{prefix}-audio-id-dub.wav (SAMA PERSIS dengan edge-tts-tui)
# → mix-tui.py langsung nemu, no change needed di step berikutnya
```

## 2 file yang ditambahkan (TIDAK ubah file lama)

| File | Fungsi |
|------|--------|
| `scripts/gemini-tts-tui.py` | TUI utama (questionary, lock file, Smart Fit, crossfade, peak normalize). Port algoritma audio dari `edge-tts-tui.py v7.5`, hanya beda backend TTS. |
| `scripts/gemini_tts_backend.py` | Modul backend: panggilan ke Google Gemini API (legacy endpoint `generate_content_stream`), 429/RESOURCE_EXHAUSTED retry, katalog 30 voice resmi + Cruz. |

**File lama yang TIDAK diubah**:
- `scripts/edge-tts-tui.py` — production default, tetap jalan
- `scripts/srt-to-audio.py` — versi lama, tetap utuh
- `scripts/config.py` — dipakai apa adanya (cuma load env + path)
- `scripts/mix-tui.py` — glob pattern `{prefix}-audio-id-dub.wav` sudah match, no change

## Kapan pakai Gemini vs Edge

| Skenario | Pakai | Alasan |
|----------|-------|--------|
| Bahasa Indonesia umum (cue film/drama biasa) | **Edge TTS** | Free unlimited, paralel 2-3 instance, stabil |
| Jawa halus (krama inggil, MC/adat) | **Gemini** | Cruz voice + instruksi MC Jawa → hasil bagus (user tested di AI Studio) |
| Karakter spesifik (narator dokuser, dialog dramatis) | **Gemini** | Instruction prompt lebih fleksibel dari Edge pitch slider |
| Bahasa eksotis (Italia, Jepang, dll) | **Gemini** | 130 bahasa, model dilatih cross-lingual |
| Batch besar (ratusan cue, banyak film) | **Edge TTS** | Gemini free tier ~5-15 RPM, ~100-250 RPD |
| Workflow produksi stabil | **Edge TTS** | Production-tested, gak perlu API key |
| Butuh pitch adjustment presisi | **Edge TTS** | Edge punya pitch slider (`-15Hz` sampai `+15Hz`), Gemini pakai instruksi bahasa natural |
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
```

6 step TUI (mirip edge-tts-tui.py, beda step 3 & 4):

| Step | edge-tts-tui.py | gemini-tts-tui.py |
|------|-----------------|-------------------|
| 1 | Pilih SRT | Pilih SRT (sama) |
| 2 | Output dir | Output dir (sama) |
| 3 | Voice (4 Edge: Ardi/Gadis/Dimas/Siti) | Voice (31 Gemini: 30 resmi + Cruz) |
| 4 | Pitch (`+0Hz` / `-10Hz` / `-15Hz` / `+10Hz` / `+15Hz`) | Instruction template (default / jawa-halus-mc / id-narasi / id-narasi-w / id-dialog / custom) |
| 5 | Smart Fit cap | Smart Fit cap (default 1.5x untuk Gemini, 2.0x untuk Edge) |
| 6 | Prefix (lock file check) | Prefix (lock file check, sama) |

### 5. Lanjut workflow mix-tui (TIDAK ada perubahan)
```bash
python3 mix-tui.py
# → pilih MP4 (yt-dlp output)
# → pilih SFX (Demucs output, opsional)
# → pilih Dub: {prefix}-audio-id-dub.wav (Gemini output, glob nemu otomatis)
# → Output: {prefix}-id-final.mp4
```

## Voice — 30 resmi Google + 1 tested

Default: **Cruz** (dari Extended Voice Library, TIDAK di 30 resmi — tapi user sudah tes untuk Jawa halus, work untuk MC/adat).

Kalau Cruz tiba-tiba error di API, fallback terdekat untuk "pria dewasa berwibawa":
1. **Charon** — Informative, pria tenang
2. **Schedar** — Even, pria stabil
3. **Alnilam** — Firm, pria tegas
4. **Rasalgethi** — Informative, pria informatif

Lihat daftar lengkap: `python3 gemini_tts_backend.py --list-voices`

## Instruction templates

5 template siap pakai + custom:
- `default` — natural, netral
- `jawa-halus-mc` — Panatacara / MC adat (pria berwibawa, tempo lambat, khidmat)
- `id-narasi` — narasi dokumenter (pria hangat)
- `id-narasi-w` — narasi dokumenter (wanita hangat)
- `id-dialog` — dialog dramatis natural
- `custom` — ketik sendiri

Lihat daftar: `python3 gemini_tts_backend.py --list-instructions`

## Algoritma (sama dengan edge-tts-tui.py v7.5, beda backend)

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

## Paralel-safe (match edge-tts-tui v7.4)

- Lock file `tts/.{prefix}.lock` dengan PID
- Prefix auto-suggest kalau collision (`prefix-2`, `prefix-3`, ...)
- 429/RESOURCE_EXHAUSTED retry: 30s → 60s → 120s → skip + log
- Stale lock cleanup: PID mati → lock dihapus otomatis
- PID display di banner (tracking di Activity Monitor)

**Catatan Gemini free tier**: ~5-15 RPM, ~100-250 RPD. Untuk paralel 2-3 instance berjalan bersamaan, tiap instance hit quota yang sama → cepat kena limit. Berbeda dengan Edge TTS yang unlimited (paralel aman 2-3 instance di Mac 16GB).

## Limit Gemini free tier (per Nov 2026)

| Tier | RPM | RPD | Cocok untuk |
|------|-----|-----|-------------|
| Free (AI Studio API key) | 5-15 | 100-250 | Test single, file pendek (<50 cue) |
| AI Pro ($20/bln) | Higher quota di Playground | — | Iterasi cepat di Playground |
| Tier 1 (Cloud Billing) | 300 | 1000 | Batch sedang (50-500 cue) |
| Tier 2 ($100+ spend) | 1000+ | 10000+ | Batch besar (ratusan file) |

Sumber: https://ai.google.dev/gemini-api/docs/rate-limits (cek resmi sebelum produksi)

## Output file (compatible mix-tui.py)

```
HDD/tts/
├── {prefix}-audio-id-dub.wav          ← main output (24kHz mono 16-bit)
├── .cache/
│   ├── {prefix}-cue-0001-{hash}.mp3    ← per-cue cache (format WAV walau ext .mp3)
│   ├── {prefix}-cue-0001-{hash}_smart_+50%.mp3  ← smart fit cache (kalau pass 2)
│   └── ...
└── .{prefix}.lock                      ← lock file (auto-delete saat selesai)
```

**Catatan file cache**: `gemini_tts_backend.generate_cue_tts` simpan WAV (16-bit PCM) dengan extension `.mp3` supaya pola cache tetap konsisten dengan `edge-tts-tui.py`. Decoder ffmpeg handle keduanya. Cache ini cuma dipakai untuk resume (generate ulang SRT sama → skip API call).

## Test di sandbox (sudah dilakukan)

```
✓ Syntax OK (ast.parse both files)
✓ Backend CLI: --list-voices (31 voice), --list-instructions (6 template)
✓ TUI no-API-key: error message jelas + instruksi setup
✓ SRT parsing: 3 cue → 3 entries, timestamps benar
✓ Cache key: text+voice+instruction → key konsisten, beda input → beda key
✓ Lock file: acquire / release / stale-detection bekerja
✓ Suggest unique prefix: collision → "prefix-2"
✓ Decode WAV → PCM float32: peak benar (0.5)
✓ Trim silence asymmetric: 72000 → 25440 samples (-30 dB threshold)
✓ Peak normalize: peak 0.794 = exactly -2 dBFS (match edge-tts constants)
✓ Backend retry 429: 1+3=4 calls (retry 3x lalu fail)
✓ Backend non-429 error: fail fast (1 call, no retry)
✓ Backend 429 then success: 2 calls, output 48 KB WAV valid
✓ TUI 6-step flow: SRT → output → voice → instruction → Smart Fit → prefix → ringkasan
✓ TUI abort di konfirmasi: lock file di-release, cleanup OK
```

## Yang TIDAK saya lakukan (biar kamu putuskan)

1. **Update `README.md`, `AGENTS.md`, `PROJECT_RULES.md`, `scripts/README.md`** — saya tidak sentuh docs projectmu. Saran commit kalau kamu setuju pakai:
   - `scripts/README.md`: tambah row di tabel "12 TUI" → "13 TUI" dengan `gemini-tts-tui v1.0 (experimental)`
   - `README.md`: tambah section "TUI 13: gemini-tts-tui v1.0 — OPSI TAMBAHAN" di bawah section "12 TUI"
   - `AGENTS.md`: update status table
   - `PROJECT_RULES.md`: tambah aturan "Gemini TTS = opsi tambahan, Edge TTS = production default"

2. **Curl download command** di README — belum saya tambah. Kalau mau:
   ```bash
   curl -L -o gemini-tts-tui.py "https://raw.githubusercontent.com/emailnyamahmud-afk/srt-splitter/main/scripts/gemini-tts-tui.py"
   curl -L -o gemini_tts_backend.py "https://raw.githubusercontent.com/emailnyamahmud-afk/srt-splitter/main/scripts/gemini_tts_backend.py"
   ```

3. **Commit + push** — kamu yang lakukan setelah test di Mac-mu. Pakai commit message:
   ```
   feat: TUI #13 gemini-tts-tui v1.0 — OPSI TAMBAHAN Gemini 3.8 Flash TTS

   - gemini-tts-tui.py: TUI utama, port algoritma edge-tts-tui v7.5
   - gemini_tts_backend.py: backend Gemini API legacy, 429 retry
   - Output: {prefix}-audio-id-dub.wav (compatible mix-tui.py)
   - Status: EXPERIMENTAL, edge-tts-tui tetap production default
   ```

4. **`.env.example`** — belum saya tambah `GEMINI_API_KEY=...` line. Saran tambah:
   ```bash
   # Gemini TTS (opsional — untuk gemini-tts-tui.py)
   # Dapatkan di https://aistudio.google.com/apikey
   GEMINI_API_KEY=
   ```

## Test plan sebelum declare "production"

1. [ ] Test 1 file SRT pendek (~10 cue) dengan voice Cruz + jawa-halus-mc → cek audio quality
2. [ ] Test 1 file SRT panjang (~500 cue) → cek rate limit, ETA, retry behavior
3. [ ] Test paralel 2 instance di Mac 16GB → cek lock file + RAM
4. [ ] Test fallback voice kalau Cruz gagal (Charon/Schedar/Alnilam)
5. [ ] Test mix-tui.py Mode E (Original) dengan output Gemini → cek sync + ducking
6. [ ] Test mix-tui.py Mode A (Full + Stream) dengan output Gemini → cek ducking sidechain
7. [ ] VLC playback test 1 file full → cek audio quality end-to-end
8. [ ] Bandingkan quality Edge vs Gemini untuk 3 scene berbeda (Indonesia umum, Jawa halus, narasi)

Setelah semua test lulus + user VLC feedback OK → update status ke "Production (experimental)" di docs.

## Anti-amnesia protocol (sesuai AGENTS.md)

Kalau AI di sesi berikutnya lupa context:
1. Baca `scripts/GEMINI_TTS.md` (file ini) dulu
2. Baca `scripts/gemini-tts-tui.py` baris 1-60 (docstring) untuk algoritma
3. Baca `scripts/gemini_tts_backend.py` baris 1-50 untuk API kontrak
4. Baca `scripts/edge-tts-tui.py` baris 1-100 untuk pattern reference
5. **JANGAN** hapus/ubah `edge-tts-tui.py` — tetap production default
6. **JANGAN** ubah `config.py` — pakai apa adanya
7. Status TUI ini: **EXPERIMENTAL** sampai user VLC-feedback OK
