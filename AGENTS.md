# AGENTS.md

> Dibaca AI di awal setiap session. Update: 19 Nov 2026.

## Anti-Amnesia Protocol

1. Baca duluan: AGENTS.md, README.md, PROJECT_RULES.md, scripts/README.md, scripts/config.py
2. Jangan ngandalkan memory context — context panjang = amnesia
3. Setiap sesi WAJIB update docs + commit + push
4. **Jangan tebak struktur folder — baca config.py LENGKAP (11 path constants, semua dipakai TUI berbeda)**
5. **Paham 3 LOKASI berbeda** (jangan campur aduk):
   - **Repo srt-splitter** (folder git, untuk DEV): sandbox AI `/home/z/my-project/`, Mac user `~/srt-splitter/` (kalau clone). Edit code + docs + push GitHub.
   - **User working dir** (tempat TUI jalan): Mac user `~/Dubbing/` (SSD, scripts + venv) + `/Volumes/HDD/Dubbing/` (HDD, data). Scripts didownload dari repo `scripts/*.py` via curl.
   - **Web app Vercel**: https://srt-splitter.vercel.app/ (deploy dari `src/` repo, terpisah dari TUI pipeline Dubbing).
6. Cek git log untuk state terakhir
7. **TUI baru WAJIB update tabel "N TUI" di 4 docs: AGENTS.md, PROJECT_RULES.md, scripts/README.md, README.md root**
8. **Cek file yang sudah ada di repo (`git ls-tree origin/main scripts/`) sebelum pilih nomor TUI baru** — jangan pakai nomor yang sudah dipakai
9. **Workflow: AI sandbox → push GitHub → user pull (kalau repo clone) / curl (kalau working dir) → test → kalau error → AI fix → push GitHub**
10. **AI kerja di repo** (`/home/z/my-project/` sandbox): edit `scripts/*.py` (TUI Python), edit docs, edit `src/` (web app Next.js), commit + push. **JANGAN** bikin file di `~/Dubbing/` (itu USER working dir, AI tidak punya akses langsung).


## Project: SRT Splitter + Dubbing Multi-Bahasa

Pipeline dubbing bahasa eksternal → Indonesia / Jawa / Sunda.
- ID: jalan end-to-end (12 TUI production + supertonic #20 production candidate + 6 untested: review-mix #13, konten #14, gemini-tts #15, talkinghead #16, manim-shorts #17, piper #18; voicestudio #19 SLOW, omnivoice DEPRECATED)
- Jawa: pipeline dub (gemini-tts-tui v1.1 SRT mode) + narasi (gemini-tts-tui v1.1 Narration mode) jalan
- Sunda: nunggu kamus Supabase

## 20 TUI

| # | TUI | Status |
|---|-----|--------|
| 1 | yt-dlp-tui v6.5 (MP4+MP3+multi-SRT ID+EN, default 1080p) | ✅ |
| 2 | demucs-tui | ✅ |
| 3 | kamus-tui v16 | ✅ (audit) |
| 4 | Web app | ⚠ Prototype |
| 5 | SRT editor (web) | ⏳ Pending |
| 6 | edge-tts-tui v7.5 (SRT + Narasi mode, ID only, paralel-safe) | ✅ Production default |
| 7 | mix-tui v3.11.7 (force 1080p + audio 48000Hz stereo + 1:1 square mode + fix ffmpeg-full keg-only path detection + stderr capture) | ✅ (1:1 VLC confirmed 14 Nov 2026; v3.11.7 fix ffmpeg 9.x Mac 21 Nov 2026) |
| 8 | whisper-tui v2.1 (Metal GPU) | ✅ |
| 9 | srt-editor-tui v1.0.0 | ✅ |
| 10 | shorts-tui v1.1 (Shorts + Part) | ✅ |
| 11 | shorts-csv-tui v1.0 | ✅ |
| 12 | merge-tui v1.9 (full format detect, stream copy / standardize) | ✅ VLC confirmed |
| 13 | review-mix-tui v1.0 (review film: potong + narasi + overlay) | ⚠ UNTESTED (code di GitHub, belum diuji di Mac) |
| 14 | konten-tui v1.0 (konten sejarah: images → video + narasi + Ken Burns) | ⚠ UNTESTED (code di GitHub, belum diuji di Mac) |
| 15 | **gemini-tts-tui v1.1** (SRT + Narasi, ID + JV, OPSI TAMBAHAN) | ⚠ UNTESTED (code di GitHub, belum diuji di Mac) |
| 16 | **talkinghead-tui v1.0** (SadTalker via Replicate, green screen preserved) | ⚠ UNTESTED (code di GitHub, belum diuji di Mac) |
| 17 | **manim-shorts-tui v0.1** (WAV + SRT → infografis Shorts video, manim animation) | ⚠ UNTESTED (sandbox OK 19 Nov 2026 + fix 21 Nov 2026, belum diuji di Mac) |
| 18 | **piper-tts-tui v0.2** (TTS LOKAL offline via Piper TTS VITS ONNX, GPU Metal CoreML EP, SRT + Narasi mode, Python API) | ⚠ UNTESTED (sandbox fungsi core OK 22 Nov 2026, generate test pending HF rate-limit sandbox, belum diuji di Mac) |
| 19 | **voicestudio-tts-tui v1.0** (TTS via VoiceStudio local API localhost:3900, 4 voice profile anton/sari ID+JV, GPU Metal CoreML) | ⚠ SLOW (user test 23 Nov 2026: suara bagus sesuai reff, tapi 16s SRT = 8 menit. VoiceStudio API per-cue HTTP overhead) |
| 20 | **supertonic-tts-tui v0.1** (TTS LOKAL Supertone Supertonic 3 ONNX, 10 voice builtin M1-M5/F1-F5, deterministic no drift, RTF ~0.012 = ~100x OmniVoice) | ✅ Production candidate (user VLC test 23 Nov 2026: sangat bagus, jauh lebih bagus dari edge-tts, ID laki+perempuan OK. 1jam SRT ~30menit. Pending long-cue test) |

**Eksperimen TTS (TIDAK bernomor, DEPRECATED):**
- `omnivoice-tts-tui.py v0.7` — ❌ DEPRECATED (user VLC test 23 Nov 2026: ref clone BERANTAKAN, v0.7 fix 3 lapis encode-once+pos_temp=0+guidance=3 TIDAK solve drift. Pakai supertonic-tts-tui #20 sebagai pengganti). Script tetap di repo untuk referensi.

## TUI #13: review-mix-tui v1.0 — Review film (UNTESTED, code di GitHub belum diuji di Mac)

Input: MP4 + timestamps.json (dari Z.ai skill) + narasi.wav (dari edge-tui v7.5 / gemini-tui v1.1 Narration)
Output: `HDD/review/review-final.mp4` (video terpotong + audio narasi + text overlay per adegan)

4 fase: potong MP4 per segment → concat → generate overlay SRT → mix video + narasi + burn overlay.

## TUI #14: konten-tui v1.0 — Konten sejarah (production)

Input: narasi.wav + timestamps.json (dari Z.ai skill) + folder images (dari Google Flow) + (opsional) backsound.mp3
Output: `HDD/konten/konten-final.mp4` (1920x1080, Ken Burns effect, text overlay, audio narasi + backsound)

5 fase: load images → Ken Burns per image → overlay SRT → concat → mix video + narasi + backsound + burn overlay.

## TUI #15: gemini-tts-tui v1.1 — OPSI TAMBAHAN Gemini 3.8 Flash TTS

**BUKAN pengganti edge-tts-tui v7.5.** edge-tts-tui v7.5 tetap production default (Indonesia only).
gemini-tts-tui untuk skenario yang Edge kurang bagus / tidak support:
- Bahasa Jawa (krama/ngoko) — user sudah test Cruz + jawa-halus-mc, hasil bagus
- Karakter suara spesifik (MC/adat, narator dokuser, dialog dramatis)
- Bahasa eksotis (Italia, Jepang, dll) yang tidak ada di Edge TTS

**2 Mode (mirror edge-tts-tui v7.5 pattern)**:
- **SRT mode** (7 step TUI): SRT → output → bahasa → voice → instruction → Smart Fit → prefix
  → Output: `HDD/tts/{prefix}-audio-id-dub.wav` (24kHz mono 16-bit, mix-tui compatible)
- **Narration mode** (6 step TUI): naskah.txt → output → bahasa → voice → instruction → rate
  → Output: `HDD/tts/{stem}-narasi.wav` (48kHz stereo 16-bit, review-mix-tui / konten-tui compatible)

**Bahasa**: Indonesia (id) + Jawa (jv). Instruction template filter per bahasa pilihan.

**Pipeline integrasi**:
- SRT mode → feed `mix-tui` (sama dengan edge-tts SRT output)
- Narration mode → feed `review-mix-tui` (review film) atau `konten-tui` (konten sejarah) atau `talkinghead-tui` (talking head video)
- Edge Narasi (ID) → review-mix-tui (review film ID) atau konten-tui (konten ID)
- Gemini Narasi (JV) → review-mix-tui (review film JV) atau konten-tui (konten JV) atau talkinghead-tui (talking head JV)

**Setup**: `echo "GEMINI_API_KEY=AIza..." >> /Volumes/HDD/Dubbing/.env`
**Pakai**: `python3 gemini-tts-tui.py`
**Detail**: lihat `scripts/GEMINI_TTS.md`

## TUI #16: talkinghead-tui v1.0 — SadTalker via Replicate (green screen preserved)

**BUKAN pipeline dubbing** — untuk workflow KONTEN (bukan film).
talkinghead-tui untuk bikin talking head video dari:
- Foto green screen half-body (mis. Amat dengan blangkon + batik)
- Audio narasi Jawa (dari gemini-tts-tui v1.1 Narration mode JV)

Output: MP4 talking head dengan **green screen DIPERTAHANKAN** (preprocess=full).
User edit manual: chroma key → composite background → final-konten.mp4 (siap YouTube).

**Backend**: Replicate.com `cjwbw/sadtalker` (A100 80GB, ~17 detik per run, ~$0.05-0.20 per video).
Kenapa cloud (BUKAN M1 lokal)? SadTalker di M1: Python 3.8 strict, hardcode CUDA, MPS support partial (Issue #526 open), community bilang "very slow". Effort install + patch tidak worth it.

**Preprocess mode `full`**: animasi wajah → paste back ke ORIGINAL background → green screen dipertahankan.
Alternatif mode `crop` = face only (gak cocok green screen).

**Setup**: `echo "REPLICATE_API_TOKEN=r8_xxx" >> /Volumes/HDD/Dubbing/.env`
**Pakai**: `python3 talkinghead-tui.py` (6 step TUI: foto → audio → output → preprocess → still → enhancer)
**Detail**: lihat `scripts/TALKINGHEAD.md`

## TUI #17: manim-shorts-tui v0.1 — Shorts infografis (WAV + SRT → manim video)

**Konten original (BUKAN dubbing).** Generate video Shorts vertical 9:16 dari WAV narasi + SRT, dengan animasi manim (premium look, gratis, tanpa model AI video mahal).

Input:
- WAV (dari edge-tts-tui Narration / gemini-tts-tui Narration / manual ElevenLabs)
- SRT (dari whisper-tui #8, atau TTS-generated SRT)

Output: `HDD/manim-shorts/{stem}-shorts.mp4` (1080x1920 vertical, 30fps, h264, manim animation + WAV audio muxed)

Cara kerja:
1. Parse SRT → segments [{start, end, text, duration}]
2. Generate manim script temp dengan Scene per segment (charcoal bg `#1C1C2E`, FadeIn whole text 0.3s + word-by-word highlight via t2c+Transform + FadeOut 0.2s, wrap_text ke multiple lines + adaptive font size 56/48/40)
3. Render manim → video-only MP4 (no audio)
4. Mux video + WAV → final MP4 (ffmpeg, video stream copy + audio aac)
5. Cleanup temp

Render time: ~0.9x realtime (30s video ≈ 26s render, sandbox Linux CPU-only tested 21 Nov 2026 fix clipping+highlight, commit 1623907). Di Mac M1 expected sama atau lebih cepat.

**Install**: `pip3 install manim questionary` + `brew install cairo pango ffmpeg` (Mac system deps). Nggak butuh LaTeX (pakai Text class Pango, bukan Tex/MathTex). Opsional: `brew install font-noto-sans` untuk font default TUI ini.
**Pakai**: `python3 manim-shorts-tui.py` (4 step TUI: WAV → SRT → output → konfirmasi)
**Sandbox tested**: 19 Nov 2026 (v0.1 initial) + 21 Nov 2026 (fix clipping+highlight, commit 1623907), dummy WAV 30s + 8 SRT segments → MP4 1.5MB, 30.0s perfect sync, h264 1080x1920 30fps + aac 48kHz stereo. Fix 21 Nov: edgeClip 0% (text fit width via wrap_text), highlight yellow berpindah per kata via t2c+Transform (manim CE Text set_color di slice NGGAK jalan, harus pakai t2c). Belum diuji di Mac user.

## TUI #18: piper-tts-tui v0.2 — TTS LOKAL offline (Piper VITS ONNX, GPU Metal)

**BUKAN pengganti edge-tts-tui v7.5.** edge-tts-tui v7.5 tetap production default (Azure neural superior, voice Ardi+Gadis). piper-tts-tui untuk skenario **OFFLINE murni** (tanpa internet sama sekali — mode pesawat, laut, hemat bandwidth).

**Adopsi dari 2 TUI existing (pattern hybrid):**
- whisper-tui v2.1 → pattern LOCAL MODEL: `find_piper()` binary CLI + `find_voice_models()` scan folder lokal untuk `.onnx` + `.onnx.json` pair (mirror `find_whisper_cli` + `find_model`).
- edge-tts-tui v7.5 → algoritma TTS: `parse_srt`, `smart_fit_cue` (per-cue generate + stretch/compress fit durasi), `trim_silence_asymmetric`/`peak_normalize`/`fade`, `mix_into_buffer`, cache key + lock file, 2 mode (SRT + Narasi).

**Backend**: Piper TTS (`pip install piper-tts`, v1.8.0) — VITS neural TTS, model ONNX dari HuggingFace `rhasspy/piper-voices`. 100% offline setelah model download sekali.

**v0.2 GPU Metal (CoreML EP)**: Switch dari CLI subprocess (v0.1) → Python API (`PiperVoice`) supaya bisa pilih onnxruntime ExecutionProvider. `PiperVoice.load()` cuma support `use_cuda` (CUDA) — untuk CoreML/Metal di M1, **bypass `load()`**: baca config JSON sendiri + bangun `onnxruntime.InferenceSession(providers=['CoreMLExecutionProvider', 'CPUExecutionProvider'])` + construct `PiperVoice(session=..., config=...)` langsung. CoreML EP = Metal GPU di Apple Silicon (M1/M2/M3), Mac gak panas, lebih cepat (mirip mix-tui GPU path). Fallback CPU otomatis kalau operator tertentu gak support CoreML. Bonus: model load SEKALI per session (v0.1 CLI reload model per cue = lambat) — speedup besar untuk SRT ribuan cue. Output audio langsung float32 array (no temp WAV + ffmpeg decode roundtrip). GPU check: `python3 -c "import onnxruntime;print(onnxruntime.get_available_providers())"` → harus ada `CoreMLExecutionProvider` di Mac M1.

**Validasi approach**: subtitlekit.com (web SRT-to-audio yang user temukan) pakai approach SAMA PERSIS — screenshot konfirmasi: "93 MB AI voice model downloads once, then stays cached, works with no internet connection" + "each cue's narration is stretched or compressed to fit the original cue duration". subtitlekit kemungkinan = Piper compiled ke WASM. TUI lokal kita pakai model yang sama persis, via binary Python (lebih cepat dari WASM browser, akses Metal GPU M1).

**2 Mode (mirror edge-tts-tui v7.5)**:
- **SRT mode** (7 step TUI): SRT → output → voice → rate (length-scale) → Smart Fit → prefix
  → Output: `HDD/tts/{prefix}-audio-id-dub.wav` (24kHz mono 16-bit, mix-tui compatible)
- **Narration mode** (6 step TUI): naskah.txt → output → voice → rate → filename
  → Output: `HDD/tts/{stem}-narasi.wav` (48kHz stereo 16-bit, review-mix/konten/talkinghead/manim-shorts compatible)

**Voice ID awal** (dari HuggingFace rhasspy/piper-voices):
- `id_ID-gadis-medium` (perempuan, ~63MB) ✅
- `id_ID-ml-medium` (MMS multilingual, netral, ~63MB) ✅
- (voice lain kalau di-download user ke ~/Dubbing/piper-voices/, auto-detect via find_voice_models)

**Jawa**: edge-tts-tui v7.5 sudah support JV (`jv-ID-DimasNeural` laki + `jv-ID-SitiNeural` perempuan). Piper TTS belum punya model JV (low-resource). piper-tts-tui fokus ID saja; JV tetap pakai edge-tts-tui.

**Trade-off vs edge-tts-tui v7.5**: + 100% offline (no internet/key/429), + latensi ~0.3-0.5s/cue (lokal vs ~1-2s network), - voice ID terbatas (gadis+MMS vs Ardi+Gadis neural), - kualitas VITS bagus tapi sedikit di bawah Azure, - tidak support pitch (piper cuma length-scale).

**Setup user** (Mac ~/Dubbing/):
```
pip3 install piper-tts questionary numpy     # piper-tts = Python package, provides `piper` CLI
mkdir -p ~/Dubbing/piper-voices && cd ~/Dubbing/piper-voices
curl -LO https://huggingface.co/rhasspy/piper-voices/resolve/main/id/id_ID/gadis/medium/id_ID-gadis-medium.onnx
curl -LO https://huggingface.co/rhasspy/piper-voices/resolve/main/id/id_ID/gadis/medium/id_ID-gadis-medium.onnx.json
```
**Pakai**: `cd ~/Dubbing && source venv/bin/activate && python3 piper-tts-tui.py`

**Sandbox tested**: 22 Nov 2026 — compile OK, fungsi core semua verified (parse_srt, normalize, cache_key, format_length_scale, find_voice_models scan, label_for_voice, piper CLI binary detect). End-to-end generate test BLOCKED karena HuggingFace rate-limit sandbox IP (429, sandbox tidak bisa download model 63MB). Generate test pending di Mac user (no rate limit di Mac).


## TUI #19: voicestudio-tts-tui v1.0 — TTS via VoiceStudio local API (SLOW)

**BUKAN production default.** VoiceStudio desktop app jalan di localhost:3900, TUI panggil via HTTP. 100% lokal, GPU Metal (CoreML) di Mac M1, no API key, no rate limit. Voice source: VoiceStudio `/profiles` (user sudah buat 4 voice: anton_id, sari_id, anton_jw, sari_jw).

**2 Mode (mirror edge-tts-tui v7.5)**:
- **SRT mode** (6 step): SRT → output → voice → smart fit cap → prefix → generate → Output: `HDD/tts/{prefix}-audio-id-dub.wav` (24kHz mono 16-bit, mix-tui compat)
- **Narration mode** (5 step): naskah.txt → output → voice → speed → filename → Output: `HDD/tts/{stem}-narasi.wav` (48kHz stereo 16-bit)

**User verdict 23 Nov 2026**: suara bagus sesuai reff di profil (VoiceStudio voice cloning works), TAPI **LAMBAT** — 16s SRT (10 cue) = 8 menit generate. Per-cue HTTP overhead ke VoiceStudio API. Edge-tts-tui v7.5 generate 2jam SRT = 3-5jam (TUI hidup), VoiceStudio sama lambatnya.

**Status**: ⚠ SLOW — tidak production. Voice cloning quality bagus tapi speed tidak viable untuk dubbing film panjang. Superseded oleh supertonic-tts-tui #20 (cepat + deterministic).

**Setup**: install VoiceStudio desktop app, buat voice profiles (anton_id, sari_id, anton_jw, sari_jw) via app GUI. App jalan di localhost:3900.
**Pakai**: `cd ~/Dubbing && source venv/bin/activate && python3 voicestudio-tts-tui.py`


## TUI #20: supertonic-tts-tui v0.1 — TTS LOKAL Supertone Supertonic 3 (PRODUCTION CANDIDATE)

**Model sama persis yg dipakai subtitlekit.com untuk Bahasa Indonesia** (`tts-supertonic`). Supertone Supertonic 3 — flow-matching latent TTS, ONNX, ~99M params, 10 voice builtin (M1-M5 male + F1-F5 female), deterministic (NO drift by design — fixed voice prototypes), 31 bahasa incl `id` (WER 1.34).

**User verdict 23 Nov 2026 (VLC confirmed)**:
- ✅ "Sangat bagus, jauh lebih bagus dari edge-tts"
- ✅ Audio ID bagus, baik laki (M1/M5) maupun perempuan (F1-F5)
- ✅ Cepat: 16s SRT (10 cue) = 9.6s generate (model cached). Skala 1jam SRT ~30menit = sekompetitif subtitlekit web (30menit), tanpa upload.
- ✅ Deterministic: cue 1 vs 5 vs 10 suara SAMA (no drift — fix masalah utama OmniVoice berantakan)
- ⏳ Pending: long-cue duration test (cue padat >5s)

**Backend**: `pip install supertonic` 1.3.x. Model ~400MB download sekali ke `~/.cache/supertonic3/` (auto_download=True). 100% offline setelah itu. API: `tts.synthesize(text, voice_style=style, total_steps=8, speed=1.0, lang='id')` → (wav, duration). Native 44100Hz, resample ke 24000Hz (SRT) / 48000Hz (narasi).

**2 Mode (mirror edge-tts-tui v7.5)**:
- **SRT mode** (6 step): SRT → output → voice (M1-M5/F1-F5) → smart fit → prefix → generate → Output: `HDD/tts/{prefix}-audio-id-dub.wav` (24kHz mono 16-bit, mix-tui compat)
- **Narration mode** (6 step): naskah.txt → output → voice → speed → filename → generate → Output: `HDD/tts/{stem}-narasi.wav` (48kHz stereo 16-bit, review-mix/konten/talkinghead/manim-shorts compat)

**Smart Fit** (mirror omnivoice v0.7 threshold): Pass 1 natural (speed=1.0), regenerate Pass 2 HANYA kalau overflow > crossfade window (150ms). Speed via Supertonic `speed=` param (0.7-2.0). Cuts ~40-60% API calls.

**Trade-off vs edge-tts-tui v7.5**: + ~100x faster (RTF 0.012-0.018 vs edge 3-5jam/2jam SRT), + deterministic (no drift), + ringan (99M params + 400MB vs edge online), + ID native (WER 1.34), - NO voice cloning (10 builtin voices, bukan ref WAV user), - 44100Hz native (resample ke 24kHz/48kHz).

**Trade-off vs omnivoice-tts-tui v0.7 (DEPRECATED)**: + deterministic (fix berantakan), + ~100x faster (RTF 0.012 vs OmniVoice 7.9 MPS), + ringan (400MB vs 3.27GB), - NO cloning (OmniVoice purports cloning tapi broken).

**Pipeline integrasi**:
- SRT mode → feed `mix-tui` (sama dengan edge/piper/omnivoice SRT output, 24kHz mono compat)
- Narration mode → feed `review-mix-tui` / `konten-tui` / `talkinghead-tui` / `manim-shorts-tui` (48kHz stereo compat)

**Setup user** (Mac ~/Dubbing/):
```
pip3 install supertonic questionary numpy soundfile
# First run: download ~400MB model (cached ~/.cache/supertonic3/, sekali saja)
```
**Pakai**: `cd ~/Dubbing && source venv/bin/activate && python3 supertonic-tts-tui.py`
**Env**: `SUPERTONIC_STEPS=12` (kualitas, 5=fast), `SUPERTONIC_SMART_FIT_DEBUG=1` (log fit)

**Sandbox tested 23 Nov 2026**: supertonic 1.3.1 install OK, API verified (TTS.synthesize signature, 10 voices M1-M5/F1-F5, sample_rate dari config). Mock test ALL 5 PASSED (generate+resample, smart_fit threshold, mix_into_buffer crossfade no numpuk, cache_key determinism, encode_wav 24kHz mono). Fix bug: parse_srt cue number bocor ke text (baca "satu", "dua" tiap cue) — root cause loop append semua non-timestamp line ke text_lines termasuk cue number; fix text_lines = lines[ts_idx+1:]. Commit `cb80ed6`.

**User Mac test 23 Nov 2026**: 2 run, dua-duanya sukses:
- Run 1 (M1, first run): model download 408.8s (6.8 menit, cached sekali), generate 10 cue 16.6s SRT = 12.6s, 0 fail, output 0.8MB 24kHz mono.
- Run 2 (M5, cached): model load 0.5s, generate 10 cue = 9.6s, 0 fail.
- VLC: suara bagus, konsisten antar cue (deterministic confirmed), ID laki+perempuan OK. Bug "satu/dua" fixed di run 2 setelah re-download parse_srt fix.


## Struktur Folder — 3 LOKASI BERBEDA (baca config.py LENGKAP)

### 1. Repo srt-splitter (folder git, untuk DEV — edit code + docs)

```
Sandbox AI:  /home/z/my-project/                      (Z.ai sandbox, clone dari GitHub)
Mac user:    ~/srt-splitter/ (atau lokasi git clone)  (untuk dev web app, kalau user clone)

Repo root:
├── README.md                          # docs root (web app + TUI overview)
├── AGENTS.md                          # docs untuk AI (baca tiap session)
├── PROJECT_RULES.md                   # aturan project
├── worklog.md                         # log semua perubahan
├── .env.example                       # template env (NEXT_PUBLIC_SUPABASE_*)
├── package.json                       # Next.js + deps web app
├── next.config.ts                     # Next.js config (Vercel deploy)
├── vercel.json                        # Vercel config
├── src/                               # Next.js web app (translate SRT Indonesia → Jawa via Supabase)
├── api/                               # Vercel serverless functions (edge-tts proxy dll)
├── public/                            # static assets + kamus JSON (jv.wiktionary.json dll)
├── scripts/                           # Python TUI (18 TUI) — DIDOWNLOAD USER ke ~/Dubbing/
│   ├── config.py                      # base path USER (~/Dubbing/ + /Volumes/HDD/Dubbing/)
│   ├── README.md                      # docs scripts (untuk user working dir ~/Dubbing/)
│   ├── yt-dlp-tui.py  # TUI #1
│   ├── demucs-tui.py  # TUI #2
│   ├── kamus-tui.py   # TUI #3
│   ├── edge-tts-tui.py v7.5  # TUI #6
│   ├── mix-tui.py    # TUI #7
│   ├── whisper-tui.py # TUI #8
│   ├── srt-editor-tui.py # TUI #9
│   ├── shorts-tui.py # TUI #10
│   ├── shorts-csv-tui.py # TUI #11
│   ├── merge-tui.py  # TUI #12
│   ├── review-mix-tui.py # TUI #13
│   ├── konten-tui.py # TUI #14
│   ├── gemini-tts-tui.py v1.1 # TUI #15 (BARU)
│   ├── gemini_tts_backend.py          # TUI #15 backend modul
│   ├── GEMINI_TTS.md                  # TUI #15 docs
│   ├── talkinghead-tui.py v1.0 # TUI #16 (BARU)
│   ├── talkinghead_backend.py         # TUI #16 backend modul (Replicate SadTalker)
│   ├── TALKINGHEAD.md                 # TUI #16 docs
│   ├── manim-shorts-tui.py v0.1 # TUI #17 (WAV+SRT → manim Shorts)
│   ├── piper-tts-tui.py v0.2 # TUI #18 (TTS LOKAL offline, Piper VITS ONNX, GPU Metal)
│   └── ... (script kamus + tools lain)
├── srt-splitter-clone/                # git submodule (repo clone untuk eksperimen)
├── srt-splitter-work/                 # git submodule (repo working)
├── clean-srt/                         # project Python clean SRT (terpisah)
├── tool-results/                      # output dari tool AI (log)
└── upload/                            # upload user (SRT, audio, dll)
```

**AI kerja di repo path** (sandbox `/home/z/my-project/` atau Mac user `~/srt-splitter/`):
- Edit code TUI Python di `scripts/*.py`
- Edit docs (AGENTS.md, README.md, PROJECT_RULES.md, scripts/README.md, worklog.md)
- Edit web app Next.js di `src/` + `api/`
- Commit + push ke GitHub (`git push origin main`)

### 2. User working dir (tempat TUI JALAN di Mac — BUKAN repo)

```
SSD ~/Dubbing/                          → scripts (.py) + venv + jv.wiktionary.json (cepat)
  ├── yt-dlp-tui.py                     # didownload dari scripts/ repo via curl
  ├── demucs-tui.py                     # didownload dari scripts/ repo via curl
  ├── kamus-tui.py                      # didownload dari scripts/ repo via curl
  ├── edge-tts-tui.py                   # didownload dari scripts/ repo via curl
  ├── mix-tui.py                        # didownload dari scripts/ repo via curl
  ├── whisper-tui.py                    # didownload dari scripts/ repo via curl
  ├── srt-editor-tui.py                 # didownload dari scripts/ repo via curl
  ├── shorts-tui.py                     # didownload dari scripts/ repo via curl
  ├── shorts-csv-tui.py                 # didownload dari scripts/ repo via curl
  ├── merge-tui.py                      # didownload dari scripts/ repo via curl
  ├── review-mix-tui.py                 # didownload dari scripts/ repo via curl
  ├── konten-tui.py                     # didownload dari scripts/ repo via curl
  ├── gemini-tts-tui.py                 # didownload dari scripts/ repo via curl
  ├── gemini_tts_backend.py             # didownload dari scripts/ repo via curl
  ├── talkinghead-tui.py                # didownload dari scripts/ repo via curl (TUI #16)
  ├── talkinghead_backend.py            # didownload dari scripts/ repo via curl (Replicate SadTalker)
  ├── manim-shorts-tui.py               # didownload dari scripts/ repo via curl (TUI #17)
  ├── piper-tts-tui.py                  # didownload dari scripts/ repo via curl (TUI #18, TTS lokal offline)
  ├── piper-voices/                     # model Piper ONNX (id_ID-gadis-medium.onnx + .json, download dari HF)
  ├── config.py                         # didownload dari scripts/ repo via curl (BASE PATH USER)
  ├── jv.wiktionary.json                # kamus (download dari public/ repo)
  └── venv/                             # Python virtual env (pip3 install)

HDD /Volumes/HDD/Dubbing/              → data (besar, dari config.py)
  ├── input/                            # yt-dlp output (MP4, MP3, SRT) — config.INPUT_DIR
  ├── demucs/                           # demucs output (no_vocals) — config.DEMUCS_DIR
  ├── tts/                              # edge-tts + gemini-tts output (dub.wav, narasi.wav, cache) — config.TTS_DIR
  ├── mix/                              # mix-tui output (final MP4) — config.MIX_DIR
  ├── shorts/                           # shorts-tui Shorts mode — config.SHORTS_DIR
  ├── parts/                            # shorts-tui Part mode — config.PARTS_DIR
  ├── merged/                           # merge-tui output (1 file panjang) — config.MERGED_DIR
  ├── review/                           # review-mix-tui output (review-final.mp4) — config.REVIEW_DIR
  ├── konten/                           # konten-tui output (konten-final.mp4) — config.KONTEN_DIR
  ├── manim-shorts/                     # manim-shorts-tui output (infografis Shorts) — config.MANIM_SHORTS_DIR
  └── .env                              # Supabase + GEMINI_API_KEY — config.ENV_FILE
```

**User pakai working dir** (Mac `~/Dubbing/` + HDD `/Volumes/HDD/Dubbing/`):
- `cd ~/Dubbing && source venv/bin/activate && python3 <tui>.py`
- TUI baca `config.py` → tahu path HDD → baca/tulis data di HDD subfolder
- Scripts di sini DIDOWNLOAD dari GitHub raw (`scripts/*.py`) via curl

### 3. Web app Vercel (deploy dari repo)

- URL: https://srt-splitter.vercel.app/
- Source: `src/` + `api/` di repo
- Fungsi: translate SRT Indonesia → Jawa via Supabase kamus (web app, BUKAN TUI)
- TIDAK ada hubungan langsung dengan TUI Dubbing — terpisah
- AI next session JANGAN pikir web app = TUI pipeline Dubbing

### config.py 12 path constants (semua untuk USER working dir)

```python
# config.py base path (dipakai TUI di ~/Dubbing/ USER, BUKAN di repo)
SSD_HOME = Path.home() / 'Dubbing'           # SSD scripts + venv + kamus
HDD_BASE = Path('/Volumes/HDD/Dubbing')      # HDD data besar
INPUT_DIR = HDD_BASE / 'input'               # TUI #1 yt-dlp output
DEMUCS_DIR = HDD_BASE / 'demucs'             # TUI #2 demucs output
TTS_DIR = HDD_BASE / 'tts'                   # TUI #6 edge-tts + #15 gemini-tts + #19 voicestudio + #20 supertonic output
MIX_DIR = HDD_BASE / 'mix'                   # TUI #7 mix-tui output
SHORTS_DIR = HDD_BASE / 'shorts'             # TUI #10 shorts-tui Shorts mode
PARTS_DIR = HDD_BASE / 'parts'               # TUI #10 shorts-tui Part mode
MERGED_DIR = HDD_BASE / 'merged'             # TUI #12 merge-tui output
REVIEW_DIR = HDD_BASE / 'review'             # TUI #13 review-mix-tui output
KONTEN_DIR = HDD_BASE / 'konten'             # TUI #14 konten-tui output
MANIM_SHORTS_DIR = HDD_BASE / 'manim-shorts' # TUI #17 manim-shorts-tui output
KAMUS_JSON = SSD_HOME / 'jv.wiktionary.json' # kamus SOURCE OF TRUTH (di SSD, cepat load)
ENV_FILE = HDD_BASE / '.env'                 # Supabase + GEMINI_API_KEY (di HDD)
SCRIPTS_DIR = SSD_HOME                       # scripts di SSD
```

- `ensure_hdd()` — cek HDD colok, bikin subfolder kalau belum ada
- `ensure_kamus()` — cek kamus JSON ada, tampilkan download command kalau gak ada
- `load_env()` — load `.env` dari HDD ke os.environ (Supabase + GEMINI_API_KEY)
- Workflow user: `cd ~/Dubbing && source venv/bin/activate && python3 <tui>.py`
- Kalau HDD tidak colok → TUI fallback ke cwd atau exit dengan pesan "Colok HDD"

### Tabel INPUT + OUTPUT per TUI (alur data lengkap)

| # | TUI | INPUT (dari mana) | OUTPUT (ke mana) |
|---|-----|------------------|------------------|
| 1 | yt-dlp-tui | URL YouTube/FB/TikTok/IG | `INPUT_DIR` (*.mp4, *.mp3, *.id.srt, *.en.srt) |
| 2 | demucs-tui | `INPUT_DIR` (*.mp3 dari yt-dlp) | `DEMUCS_DIR`/htdemucs/{prefix}-audio/no_vocals.mp3 |
| 3 | kamus-tui | `KAMUS_JSON` (jv.wiktionary.json di SSD) | Edit in-place + upload Supabase |
| 6 | edge-tts-tui SRT | `INPUT_DIR` (*.final.srt) | `TTS_DIR`/{prefix}-audio-id-dub.wav + cache + lock |
| 6 | edge-tts-tui Narasi | naskah.txt (cwd atau `REVIEW_DIR`) | `TTS_DIR`/{stem}-narasi.wav |
| 7 | mix-tui | `INPUT_DIR` (*.mp4, *.mp3) + `DEMUCS_DIR` (no_vocals) + `TTS_DIR` (*.wav dub) + `INPUT_DIR`/*.srt | `MIX_DIR`/{prefix}-id-*.mp4 |
| 8 | whisper-tui | `INPUT_DIR` (*.mp3 dari yt-dlp) | `INPUT_DIR`/{base}.zh.srt + {base}.en.srt |
| 9 | srt-editor-tui | `INPUT_DIR` (*.id.srt) | `INPUT_DIR`/{prefix}.final.srt + .srt.bak + .working.json |
| 10 | shorts-tui Shorts | `MIX_DIR` (*.mp4) + `SHORTS_DIR`/`MIX_DIR` (*.json dari Dola) | `SHORTS_DIR`/{film}/short-001.mp4 s/d short-N.mp4 |
| 10 | shorts-tui Part | `MIX_DIR` (*.mp4) + `INPUT_DIR`/`MIX_DIR` (*.srt) | `PARTS_DIR`/{film}/part-001.mp4 s/d part-N.mp4 |
| 11 | shorts-csv-tui | `SHORTS_DIR` (*.json dari Dola) + folder MP4 (shorts-tui output) | `SHORTS_DIR`/{film}.metadata.csv + {film}.manifest.txt |
| 12 | merge-tui | `MIX_DIR` (*.mp4 — multi-file) | `MERGED_DIR`/{first-name}-merged.mp4 |
| 13 | review-mix-tui | `INPUT_DIR`/`REVIEW_DIR` (*.mp4) + `INPUT_DIR`/`REVIEW_DIR` (*.json dari Z.ai) + `TTS_DIR`/`REVIEW_DIR` (*.wav narasi) | `REVIEW_DIR`/{mp4-stem}-review.mp4 |
| 14 | konten-tui | `TTS_DIR`/`KONTEN_DIR` (*.wav narasi) + `INPUT_DIR`/`KONTEN_DIR` (*.json) + `INPUT_DIR`/`KONTEN_DIR` (folder images) + `INPUT_DIR`/`KONTEN_DIR` (*.mp3 backsound, opsional) | `KONTEN_DIR`/konten-final.mp4 |
| 15 | gemini-tts-tui SRT | `INPUT_DIR` (*.srt) | `TTS_DIR`/{prefix}-audio-id-dub.wav + cache + lock |
| 15 | gemini-tts-tui Narasi | naskah.txt (`TTS_DIR`/`REVIEW_DIR`/cwd) | `TTS_DIR`/{stem}-narasi.wav |
| 16 | talkinghead-tui | `KONTEN_DIR`/`INPUT_DIR`/cwd (*.jpg/*.png foto green screen) + `TTS_DIR`/cwd (*.wav narasi JV) | `KONTEN_DIR`/{audio-stem}-talking-green.mp4 |
| 17 | manim-shorts-tui | `TTS_DIR`/`INPUT_DIR`/cwd (*.wav narasi) + `INPUT_DIR`/`TTS_DIR`/cwd (*.srt dari whisper-tui) | `MANIM_SHORTS_DIR`/{stem}-shorts.mp4 |
| 18 | piper-tts-tui SRT | `INPUT_DIR` (*.srt) | `TTS_DIR`/{prefix}-audio-id-dub.wav + cache + lock |
| 18 | piper-tts-tui Narasi | naskah.txt (`TTS_DIR`/cwd) | `TTS_DIR`/{stem}-narasi.wav |

### Pipeline alur data (visual flow)

```
yt-dlp-tui (#1)
    ↓ output ke INPUT_DIR
    ├── *.mp4, *.mp3, *.id.srt
    │
    ├──→ whisper-tui (#8) → INPUT_DIR/{base}.zh.srt + .en.srt
    ├──→ srt-editor-tui (#9) → INPUT_DIR/{prefix}.final.srt
    ├──→ demucs-tui (#2) → DEMUCS_DIR/.../no_vocals.mp3
    │
    ├──→ edge-tts-tui #6 SRT  ──┐
    ├──→ gemini-tts-tui #15 SRT ┤
    ├──→ supertonic-tts-tui #20 SRT ┤ (PRODUCTION candidate — user VLC confirmed 23 Nov 2026, ~100x edge speed)
    │   (input: INPUT_DIR/*.final.srt)
    │   (output: TTS_DIR/{prefix}-audio-id-dub.wav)
    │                              ↓
    │                              ↓ input mix-tui
    │                              ↓
    └──→ mix-tui (#7)
        (input: INPUT_DIR/*.mp4 + DEMUCS_DIR/no_vocals.mp3 + TTS_DIR/*.wav + INPUT_DIR/*.srt)
        ↓ output ke MIX_DIR/{prefix}-id-*.mp4
        │
        ├──→ merge-tui (#12) → MERGED_DIR/{first-name}-merged.mp4
        ├──→ shorts-tui #10 Shorts → SHORTS_DIR/{film}/short-*.mp4
        ├──→ shorts-tui #10 Part → PARTS_DIR/{film}/part-*.mp4
        └──→ shorts-csv-tui #11 → SHORTS_DIR/{film}.metadata.csv + .manifest.txt

edge-tts #6 Narasi ──┐
gemini-tts #15 Narasi ┤
    (input: naskah.txt)
    (output: TTS_DIR/{stem}-narasi.wav)
    ↓
    ├──→ review-mix-tui #13 (input juga: INPUT_DIR/*.mp4 + INPUT_DIR/*.json dari Z.ai)
    │   → REVIEW_DIR/{mp4-stem}-review.mp4
    │
    ├──→ konten-tui #14 (input juga: INPUT_DIR/*.json + folder images + optional backsound.mp3)
    │   → KONTEN_DIR/konten-final.mp4
    │
    └──→ talkinghead-tui #16 (input juga: KONTEN_DIR/INPUT_DIR/*.jpg foto green screen)
        → KONTEN_DIR/{audio-stem}-talking-green.mp4
        ↓
        User edit manual: chroma key → composite background → final-konten.mp4 (siap YouTube)
```

### Catatan path penting

- `INPUT_DIR` = sumber utama multifungsi: output yt-dlp + tempat user taruh file manual (foto green screen, JSON dari Dola/Z.ai, backsound.mp3, logo.png)
- `TTS_DIR` = output TUI TTS + input TUI downstream (mix-tui pakai dub, review/konten/talkinghead pakai narasi)
- `KONTEN_DIR` = output 2 TUI berbeda: konten-tui #14 (Ken Burns, video panjang) + talkinghead-tui #16 (talking head green screen)
- `REVIEW_DIR` = output review-mix-tui + tempat search input (user bisa pindah file ke sini)
- Fallback: kalau HDD tidak colok → TUI pakai cwd (current working directory)

## Aturan

1. jv.wiktionary.json = SOURCE OF TRUTH (kamus)
2. Supabase = kamus terverifikasi (user upload manual)
3. AI DILARANG parsing tolol / buang data / halu
4. Register (ngoko/krama) = tugas user, AI gak bisa
5. Data di HDD, scripts di SSD
6. Sebutan hormat Tiongkok (Nona/Tuan/Dokter/Paman) = PRESERVE, bukan mistranslate
7. GT input: SRT English (dari whisper-tui) → GT English→ID lebih akurat
8. **Standarisasi res+audio = kerjaan mix-tui v3.11** (mode 1:1 square baru = center crop untuk source vertical → IG feed), bukan yt-dlp atau merge-tui
9. **merge-tui v1.9** = full format detect (6 properties) + stream copy (super cepat) / standardize (re-encode). VLC confirmed: sync 100%.
10. **fix-merge-audio.py = DEPRECATED (masih ada di repo scripts/fix-merge-audio.py v1.4, tapi jangan pakai — gunakan merge-tui v1.9 audio stream copy)** (audio drift, failed experiment)
11. **edge-tts-tui v7.5 = production default** (SRT + Narasi, ID only, paralel-safe, no API key)
12. **review-mix-tui v1.0 = production** (TUI #13) — input narasi dari edge-tts / gemini-tts Narration
13. **konten-tui v1.0 = production** (TUI #14) — input narasi dari edge-tts / gemini-tts Narration
14. **gemini-tts-tui v1.1 = OPSI TAMBAHAN** (TUI #15, SRT + Narasi, ID + JV, butuh GEMINI_API_KEY)
    - Output SRT mode: `HDD/tts/{prefix}-audio-id-dub.wav` (mix-tui compatible)
    - Output Narration mode: `HDD/tts/{stem}-narasi.wav` (review-mix-tui / konten-tui compatible)
    - Jangan hapus / ganti edge-tts-tui v7.5
    - Status UNTESTED (code di GitHub, belum diuji di Mac) sampai user VLC feedback OK
15. **Repo srt-splitter ≠ User working dir Dubbing** (jangan campur aduk):
    - Repo: `~/srt-splitter/` (atau sandbox `/home/z/my-project/`) = tempat dev code + docs + commit + push
    - Working dir: `~/Dubbing/` (SSD scripts + venv) + `/Volumes/HDD/Dubbing/` (HDD data) = tempat user jalanin TUI
    - Scripts di repo `scripts/*.py` → user download ke `~/Dubbing/` via `curl -L -o ... https://raw.githubusercontent.com/.../main/scripts/...`
    - config.py di repo: base path USER (`~/Dubbing/` + `/Volumes/HDD/Dubbing/`), BUKAN path repo
    - AI TIDAK punya akses langsung ke `~/Dubbing/` user — AI kerja di repo path
16. **talkinghead-tui v1.0 = UNTESTED** (TUI #16, code di GitHub belum diuji di Mac)
    - Workflow KONTEN (bukan dubbing): foto green screen + narasi JV → talking head MP4
    - Backend: Replicate.com `cjwbw/sadtalker` (cloud, butuh `REPLICATE_API_TOKEN` di HDD .env)
    - Output: `HDD/konten/{name}-talking-green.mp4` (green screen preserved, preprocess=full)
    - User edit manual: chroma key → composite background → final-konten.mp4 (siap YouTube)
    - JANGAN auto-declare "Production" — tunggu user test di Mac + VLC feedback OK

## Pipeline Final (confirmed end-to-end)

### Pipeline Indonesia (production):
```
yt-dlp v6.5 → srt-editor v1.0.1 → edge-tts v7.5 SRT → mix-tui v3.11 → merge-tui v1.9
yt-dlp v6.5 → srt-editor v1.0.1 → supertonic-tts v0.1 SRT → mix-tui v3.11 → merge-tui v1.9  (PRODUCTION candidate — ~100x edge speed, deterministic)
                                                                                      ↘ shorts-tui → shorts-csv-tui → YouTube
edge-tts v7.5 Narasi (ID) → review-mix-tui v1.0 (review film ID)
edge-tts v7.5 Narasi (ID) → konten-tui v1.0 (konten sejarah ID)
supertonic-tts v0.1 Narasi (ID) → review-mix-tui v1.0 (review film ID — fast alternative)
supertonic-tts v0.1 Narasi (ID) → konten-tui v1.0 (konten sejarah ID — fast alternative)
```

### Pipeline Jawa (experimental, opsional via Gemini):
```
yt-dlp v6.5 → srt-editor v1.0.1 → gemini-tts-tui v1.1 SRT mode (JV) → mix-tui v3.11
naskah.txt → gemini-tts-tui v1.1 Narration mode (JV) → review-mix-tui v1.0 (review film JV)
naskah.txt → gemini-tts-tui v1.1 Narration mode (JV) → konten-tui v1.0 (konten sejarah JV)
naskah.txt → gemini-tts-tui v1.1 Narration mode (JV) → talkinghead-tui v1.0 (talking head JV, green screen) → editor chroma key → final-konten.mp4
```

## Status (3 Nov 2026, update 22 Nov 2026)

- merge-tui v1.9: ✅ VLC confirmed (10 file × 24h, sync 100%, stream copy ~2 menit)
- mix-tui v3.11.7: ✅ production (force 1080p + audio 48000Hz stereo + 1:1 square mode VLC confirmed 14 Nov 2026 — 2 test: (1) Mode F source 202x360 → 1080x1080 upscale 5.3x, 3j1m, 2789 MB, 19m2s, subs sharp; (2) Mode F source 1440x2560 4K → 1080x1080 downscale 1.33x, 2j30m, 2361 MB, 15m45s, speed 9.5x, background crisp + subs sharp. Resolusi rendah = sumber, bukan bug — high-res retest confirmed sharp. v3.11.7 fix 21 Nov 2026: ROOT CAUSE SEBENARNYA = ffmpeg build user TIDAK punya libass (config line tidak ada `--enable-libass`, formula `ffmpeg` regular minimal). BUKAN quoting/escaping (6x fix v3.11.0-v3.11.6 salah diagnosis — semua patch valid, tapi ffmpeg bahkan tidak kenal `subtitles` filter → "Unknown filter 'subtitles'" → error "No option name" cuma misleading parse error). User install `ffmpeg-full` (keg-only, binary ke `/opt/homebrew/opt/ffmpeg-full/bin/`, bukan symlink ke PATH). `shutil.which('ffmpeg')` gagal kalau script jalan dari GUI/IDE/cron (PATH tidak load). Fix: `find_ffmpeg()`/`find_ffprobe()` cek path explicit ffmpeg-full duluan sebelum `which()` + fallback. Bonus fix: `run_ffmpeg_with_progress` return tuple `(returncode, stderr_text)` — failure path pakai stderr asli dari run yang gagal (sebelumnya buggy: re-run cmd + timeout=30 → pasti timeout video panjang → "Tidak bisa capture stderr")).
- yt-dlp v6.5: ✅ multi-SRT ID+EN, default 1080p preferred
- edge-tts-tui v7.5: ✅ production default (SRT + Narasi, ID only, paralel-safe)
- review-mix-tui v1.0: ⚠ UNTESTED (TUI #13, code di GitHub belum diuji di Mac)
- konten-tui v1.0: ⚠ UNTESTED (TUI #14, code di GitHub belum diuji di Mac)
- gemini-tts-tui v1.1: ⚠ UNTESTED (TUI #15, code di GitHub belum diuji di Mac, SRT + Narasi, ID + JV, butuh GEMINI_API_KEY)
- talkinghead-tui v1.0: ⚠ UNTESTED (TUI #16, code di GitHub belum diuji di Mac, SadTalker via Replicate, butuh REPLICATE_API_TOKEN)
- manim-shorts-tui v0.1: ⚠ UNTESTED (TUI #17, sandbox pipeline OK 19 Nov 2026 + fix 21 Nov 2026 commit 1623907 — 30s dummy render 26s/0.9x realtime, 30.0s perfect sync, edgeClip 0% (text fit width), highlight yellow per kata via t2c+Transform, MP4 1.5MB valid. Belum diuji di Mac. Butuh manim CE + cairo + pango, NGGAK butuh LaTeX)
- piper-tts-tui v0.2: ⚠ UNTESTED (TUI #18, sandbox fungsi core OK 22 Nov 2026 — compile OK, parse_srt/normalize/cache_key/format_length_scale/find_voice_models/label_for_voice/resample_audio/peak_normalize semua verified. v0.2 GPU Metal: Python API (PiperVoice) + onnxruntime CoreMLExecutionProvider (bypass PiperVoice.load cuma support use_cuda) → Metal GPU di M1, fallback CPU. Model load sekali (vs v0.1 CLI reload per cue). _HAS_COREML False di sandbox Linux (expected, no CoreML EP) → True di Mac M1. End-to-end generate test BLOCKED: HuggingFace rate-limit sandbox IP (429, sandbox tidak bisa download model 63MB). Generate test pending di Mac user. Backend Piper TTS VITS ONNX via `pip install piper-tts` v1.8.0, model `id_ID-gadis-medium` dari HF rhasspy/piper-voices. Adopsi edge-tts-tui algoritma (smart_fit per cue, mix_into_buffer, cache .npy, lock, 2 mode) + whisper-tui local model pattern (find_voice_models scan .onnx). 100% offline. BUKAN pengganti edge-tts-tui v7.5 — opsi tambahan untuk skenario offline murni)
- voicestudio-tts-tui v1.0: ⚠ SLOW (TUI #19, user test 23 Nov 2026: suara bagus sesuai reff, tapi 16s SRT = 8 menit. VoiceStudio local API localhost:3900 per-cue HTTP overhead. Voice cloning works tapi speed tidak viable untuk film panjang. Superseded oleh supertonic #20)
- omnivoice-tts-tui v0.7: ❌ DEPRECATED (eksperimen TTS offline, TIDAK bernomor. User VLC test 23 Nov 2026: ref clone BERANTAKAN, v0.7 fix 3 lapis encode-once+pos_temp=0+guidance=3+seed TIDAK solve drift. Output audio berantakan, ref WAV gak fungsi. Pakai supertonic-tts-tui #20 sebagai pengganti — deterministic fixed voices, no drift, ~100x faster. Script tetap di repo untuk referensi, JANGAN pakai production)
- supertonic-tts-tui v0.1: ✅ Production candidate (TUI #20, user VLC test 23 Nov 2026: sangat bagus, jauh lebih bagus dari edge-tts, ID laki+perempuan OK. 1jam SRT ~30menit. Model sama persis subtitlekit.com untuk Indonesia. 10 voice builtin M1-M5/F1-F5 deterministic no drift. RTF ~0.012-0.018 M4 CPU = ~100x OmniVoice. Pending long-cue duration test. Sandbox API verified + mock test 5 PASSED + fix parse_srt cue number bocor commit cb80ed6. User Mac 2 run sukses: M1 first run 12.6s/10cue (download 408.8s cached), M5 cached 9.6s/10cue)
- Pipeline produksi Indonesia: 6 film tested, all TUI production-ready
- Pipeline Jawa: experimental, tunggu user VLC feedback

## Anti-amnesia untuk AI next session (Pelajaran 3 Nov 2026, update 19 Nov 2026)

### LOKASI (jangan campur aduk — kesalahan parah saya sebelumnya):

- **Repo srt-splitter** (folder git, untuk DEV): sandbox AI = `/home/z/my-project/`, Mac user (kalau clone) = `~/srt-splitter/` atau lokasi git clone lain. Berisi: `src/` (Next.js), `api/`, `scripts/` (TUI Python), `public/`, docs (.md), `package.json`. AI kerja di sini: edit code + docs + commit + push.
- **User working dir** (tempat TUI jalan di Mac): `~/Dubbing/` (SSD, scripts + venv + kamus) + `/Volumes/HDD/Dubbing/` (HDD, data). Scripts di sini DIDOWNLOAD dari repo `scripts/*.py` via curl. User jalanin: `cd ~/Dubbing && source venv/bin/activate && python3 <tui>.py`. **AI TIDAK punya akses langsung ke sini — kerja di repo path saja**.
- **Web app Vercel**: https://srt-splitter.vercel.app/, deploy dari `src/` repo, terpisah dari TUI pipeline Dubbing.

### config.py (di repo `scripts/config.py`, base path untuk USER working dir):

```python
SSD_HOME = Path.home() / 'Dubbing'           # SSD scripts + venv + kamus
HDD_BASE = Path('/Volumes/HDD/Dubbing')      # HDD data besar
INPUT_DIR, DEMUCS_DIR, TTS_DIR, MIX_DIR,     # 9 subfolder HDD
SHORTS_DIR, PARTS_DIR, MERGED_DIR,
REVIEW_DIR, KONTEN_DIR
KAMUS_JSON = SSD_HOME / 'jv.wiktionary.json' # kamus di SSD (cepat load)
ENV_FILE = HDD_BASE / '.env'                 # Supabase + GEMINI_API_KEY
SCRIPTS_DIR = SSD_HOME                       # scripts di SSD
```
- 11 path constants, semua untuk USER working dir, BUKAN repo path
- `ensure_hdd()` + `ensure_kamus()` + `load_env()` = helper functions

### TUI (ada 20, BUKAN 12/13/15/16/17/18):

- Jangan amnesia: ada **20 TUI** (#1-#20). Baca `git ls-tree origin/main scripts/` untuk verifikasi sebelum pilih nomor TUI baru
- TUI #13 = review-mix-tui (UNTESTED), TUI #14 = konten-tui (UNTESTED), TUI #15 = gemini-tts-tui (UNTESTED), TUI #16 = talkinghead-tui (UNTESTED), TUI #17 = manim-shorts-tui (UNTESTED sandbox OK), TUI #18 = piper-tts-tui (UNTESTED sandbox OK), TUI #19 = voicestudio-tts-tui (SLOW — user test 23 Nov 2026, suara bagus tapi 16s SRT = 8 menit), TUI #20 = supertonic-tts-tui (✅ Production candidate — user VLC test 23 Nov 2026 sangat bagus + cepat 1jam=30menit + deterministic no drift)
- `omnivoice-tts-tui.py v0.7` = EKSPERIMEN TIDAK bernomor, DEPRECATED (ref clone berantakan per user test 23 Nov 2026, v0.7 fix 3 lapis tidak solve drift). Header lama salah claim "TUI #19" (collision dgn voicestudio) — sudah diperbaiki. JANGAN pakai production, pakai supertonic #20.
- `REVIEW_DIR` di config.py untuk review-mix-tui (#13), `KONTEN_DIR` untuk konten-tui (#14) + talkinghead-tui (#16 output ke KONTEN_DIR), `MANIM_SHORTS_DIR` untuk manim-shorts-tui (#17)
- edge-tts-tui v7.5 Narration mode → feed review-mix-tui / konten-tui / manim-shorts-tui (BUKAN langsung ke user)
- gemini-tts-tui v1.1 Narration mode (JV) → alternatif feed untuk review-mix-tui / konten-tui / talkinghead-tui / manim-shorts-tui (bahasa Jawa)
- talkinghead-tui v1.0 (#16) = workflow KONTEN (BUKAN dubbing): foto green screen + narasi JV → SadTalker via Replicate → MP4 green screen preserved → user edit chroma key → final-konten.mp4
- TUI #16 backend = Replicate.com `cjwbw/sadtalker` (cloud), butuh `REPLICATE_API_TOKEN` di HDD .env (BUKAN M1 lokal — sadtalker lambat + MPS partial)
- manim-shorts-tui v0.1 (#17) = workflow KONTEN (BUKAN dubbing): WAV narasi + SRT → manim animation video Shorts vertical 9:16. Render ~0.9x realtime (post-fix 21 Nov 2026). Animasi: FadeIn whole text + word-by-word highlight (t2c+Transform, text full tetap visible). Butuh manim CE + cairo + pango (NGGAK butuh LaTeX). Input WAV dari edge-tts/gemini-tts Narration atau manual, SRT dari whisper-tui #8

### Workflow (kesalahan saya sebelumnya: tidak push):

- AI sandbox: kerja di repo → commit + push GitHub
- User: kalau repo clone → `git pull` (untuk dev web app) / kalau working dir → `curl -L -o ... https://raw.githubusercontent.com/.../main/scripts/<file>.py` (untuk pakai TUI)
- User test → kalau error → paste ke AI → AI fix di sandbox → push GitHub → user download lagi
- TIAP selesai task: WAJIB commit + push GitHub (jangan nunggu ditanya ulang)
- **CEK SYNC DI AWAL SESSION (pelajaran 19 Nov 2026)**: sandbox lokal bisa tertinggal dari GitHub origin/main karena environment di-recycle antar session. **SELALU** jalankan `git fetch origin && git log origin/main..main --oneline && git log main..origin/main --oneline` di awal session sebelum diagnose masalah sync. Kalau local tertinggal: `git reset --hard origin/main` (asalkan tidak ada working change penting). JANGAN asumsi "GitHub stale" hanya dari baca working copy lokal — GitHub selalu paling up-to-date karena setiap session WAJIB push. Kasus 19 Nov 2026: saya salah diagnose "GitHub v3.9" padahal GitHub sudah v3.11 (commit `bf3ab24`), hanya sandbox lokal yang belum fetch. User koreksi. Pelajaran: fetch dulu, baru bicara.

### mix-tui v3.11 mode 1:1 square (VLC confirmed 14 Nov 2026):

- **Mode 1:1 = PRODUCTION** (VLC confirmed). Bukan experimental lagi.
- Opsi `1:1 square (1080x1080)` muncul di Step 4.10 HANYA kalau source vertical (h > w).
- Filter: `crop=min(iw\,ih):min(iw\,ih):center, scale=1080:1080, setsar=1` → atas+bawah dipotong, **full width dipertahankan** (1080px). Untuk IG feed.
- Hanya jalur Burn SRT (Mode B/D/F, re-encode). Stream copy (A/C/E) tidak bisa (no filter).
- Source horizontal → opsi 1:1 tidak muncul, pakai force 1080p horizontal (1920x1080).
- **Return tuple 3-elemen**: `pick_force_resolution()` return `(w, h, is_square)`, BUKAN 2-tuple lama. Indexing `[0]/[1]` tetap jalan, tapi unpacking `tw, th = ...` harus jadi `tw, th, is_square = ...`.
- Escape koma ffmpeg: `min(iw\,ih)` di f-string Python = `min(iw\\,ih)` (backslash dobel). Tanpa escape, ffmpeg salah parse (koma = pemisah filter).
- **v3.11.7 fix (21 Nov 2026, commit `756caa4`): ffmpeg-full keg-only path detection + stderr capture — the REAL fix untuk ffmpeg 9.x Mac**. **ROOT CAUSE SEBENARNYA (BUKAN quoting/escaping)**: formula `ffmpeg` regular homebrew (9.0.2_1, 290 files, 53.9MB) TIDAK compile libass (config line: 11 `--enable-lib*` flags, TIDAK ADA `--enable-libass`). Tanpa libass → `subtitles` filter TIDAK ter-register → `ffmpeg -h filter=subtitles` = "Unknown filter 'subtitles'" → filtergraph error "No option name near '...'" (misleading, terlihat kayak quoting bug). **v3.11.0-v3.11.6 = 6x SALAH DIAGNOSIS** — semua patch quoting/escape/symlink/satu-quote/no-quote VALID secara syntax, tapi ffmpeg bahkan tidak sampai ke parsing option karena filter-nya tidak ada. Error identik walau quoting beda = bukan quoting issue. User install `ffmpeg-full` (keg-only, 47 deps include libass ✔) → binary ke `/opt/homebrew/opt/ffmpeg-full/bin/`, BUKAN symlink ke `/opt/homebrew/bin/` (Homebrew tidak symlink biar tidak bentrok formula `ffmpeg` biasa). `shutil.which('ffmpeg')` cuma nemu ffmpeg-full KALAU user export PATH manual + script jalan dari shell yang source `.zshrc`. Dari GUI/IDE/cron → `which()` gagal → fallback pakai ffmpeg regular (tanpa libass) → error lagi. **Fix v3.11.7**: (1) `find_ffmpeg()`/`find_ffprobe()` cek path explicit ffmpeg-full duluan (`/opt/homebrew/opt/ffmpeg-full/bin/ffmpeg` Apple Silicon + `/usr/local/opt/ffmpeg-full/bin/ffmpeg` Intel) sebelum `which()` + fallback list. Auto-detect tanpa edit `.zshrc`. (2) `run_ffmpeg_with_progress` return tuple `(returncode, stderr_text)` — caller failure path pakai stderr asli dari run yang gagal (sebelumnya buggy: re-run `cmd` + timeout=30 → pasti timeout video panjang → print "Tidak bisa capture stderr" → user tidak pernah lihat error asli). **PELAJARAN PENTING UNTUK AI NEXT SESSION**: (a) Kalau error IDENTIK walau fix berbeda (6x quoting patch hasil error sama persis) = BUKAN code issue, CEK ENVIRONMENT dulu (`ffmpeg -filters`, `ffmpeg -h filter=X`, config line `--enable-lib*`). (b) "No option name near 'X'" di ffmpeg = bisa berarti filter TIDAK ADA (Unknown filter), bukan cuma quoting bug. (c) `subtitles`/`ass` filter REQUIRES `--enable-libass` di config. Formula homebrew `ffmpeg` regular (minimal) TIDAK punya — user butuh `ffmpeg-full` (keg-only, path detection). (d) Jangan over-engineer tebak escape/quote 6x tanpa cek apakah filter-nya ada. (e) v3.11.0-v3.11.6 patch quoting TETAP ADA di git history (DEPRECATED tapi valid syntax) — patch v3.11.6 (one quote pair, canonical form) tetap benar untuk ffmpeg yang punya libass, tidak perlu revert. (f) Sebelum diagnose "sync problem" atau "quoting bug", SELALU cek `ffmpeg -filters | grep subtitles` + config line `--enable-libass` — 30 detik, hemat 6 round-trip user.
- **Resolusi output = fungsi sumber, BUKAN bug.** Source 202x360 → crop 202x202 → upscale 5.3x ke 1080x1080 = background soft (subtitle tetap sharp). Source 1440x2560 → crop 1440x1440 → downscale 1.33x ke 1080x1080 = background crisp + subtitle sharp. **VLC confirmed kedua kasus 14 Nov 2026.**
- Hasil test 14 Nov 2026 (2 run, dua-duanya VLC OK):
  - Run 1 (low-res): Mode F, source 202x360, 4182 cues, 3j1m32s video → 1080x1080, 2789 MB, encode 19m2s (speed 9.5x), subs sharp, ducking + hardsub + logo OK.
  - Run 2 (high-res 4K): Mode F, source 1440x2560, 5100 cues, 2j30m4s video → 1080x1080, 2361 MB, encode 15m45s (speed 9.5x), background crisp + subs sharp, ducking + hardsub + logo OK.
  - Bonus: 1:1 (1080x1080, 1.17MP) encode ~1.7x lebih cepat dari vertical 1080x1920 (2.07MP) — test salah-pilih 1080x1920 speed 6.1x vs 1:1 speed 10.5x.

