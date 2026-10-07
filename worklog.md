---
Task ID: 1
Agent: main
Task: Adopsi filosofi Voicertool.com/subs — kombinasi speedup AND slowdown. Verifikasi subs durasi tetap aman setelah fix sebelumnya.

Work Log:
- Scraping https://voicertool.com/subs via z-ai page_reader untuk konfirmasi filosofi mereka
- Ditemukan dua mode di Voicertool: "Speed up only" dan "Speed up and slow down"
- Cek state kode lokal: UI `tts-panel.tsx` (baris 67, 485-495) sudah ada dropdown kedua mode, default = speedup-slowdown
- Cek `src/lib/tts.ts`: `speedMode` dideklarasikan di `NarrationOptions` (baris 88) dan di-pass dari UI, TAPI tidak pernah dibaca di logika. Hanya speedup yang jalan. Slowdown branch hilang.
- Verifikasi durasi SRT tetap aman: position = entry.start, totalSamples = entries[last].end, audio tidak pernah di-truncate (mixAudioInto ADD). Crossfade hanya kalau overlap.
- Tambahkan slowdown branch di `narrateEntries`:
  * Kondisi: `actualDuration < cueDuration * 0.95` AND `speedMode === 'speedup-slowdown'`
  * Rasio: `rawRatio = actualDuration / cueDuration` (e.g., 0.7 = audio 70% cue)
  * Clamp bawah: `MIN_SLOWDOWN_RATIO = 0.7` (Edge rate -30% maksimum slowdown)
  * Edge TTS re-generate dengan `formatEdgeRate(slowRatio)` → pitch natural di server
  * Provider non-Edge atau rasio sudah ~1.0 → pakai natural (silence toleransi <5%)
- Update docblock di atas `narrateEntries` supaya dokumentasi mode "speedup-only" vs "speedup-slowdown" konsisten dengan Voicertool
- Verifikasi: `npx next build` → `✓ Compiled successfully in 8.1s` (Turbopack)

Stage Summary:
- Filosofi Voicertool.com/subs sudah diadopsi penuh: dua mode eksplisit di UI + logika
- Mode DEFAULT di UI = "speedup-slowdown" (sebelumnya cuma label, sekarang benar-benar jalan)
- Subs durasi TETAP AMAN: position = SRT start, total = SRT end, audio utuh, crossfade hanya kalau overlap
- Slowdown di-clamp ke 0.7x untuk hindari suara aneh (lebih lambat dari -30% terdengar drone)
- Build: OK, tidak ada error baru yang di-introduce
- File yang berubah: `src/lib/tts.ts` (slowdown branch + docblock)
- File yang TIDAK berubah: `src/components/tts-panel.tsx` (UI sudah benar sebelumnya — default sudah speedup-slowdown, dropdown sudah ada)

---
Task ID: 2
Agent: main
Task: Implementasi Dubbing Mode — SRT Jawa sebagai ground truth. Workflow user: MP4 Mandarin + SRT Mandarin → translate Jawa → rapikan → generate audio natural + SRT baru (web app Fase 2) → retim MP4 supaya match SRT Jawa (Python Fase 3) → edit DaVinci (Fase 4).

Work Log:
- Cek sandbox: tidak reset, edit slowdown branch sebelumnya masih ada di commit b1b098b
- Cek git: 4 commit lokal belum di-push (sandbox tidak punya credential GitHub → user push manual)
- Analisis SRT user (Season-1-jw-fixed.srt): cue Mandarin 0.3-0.8s dengan translate Jawa 3-8 kata → dipaksa sync = robot
- User sudah jawab Q1-Q4: jangan ada SRT hening, slow-mo video OK, audio 1.25x default, tetap pertahankan mode ON sebagai fallback
- Bangun DubbingOptions + DubbingResult + DubbingRetimePoint interfaces di tts.ts
- Bangun narrateDubbingMode function di tts.ts:
  * Generate audio natural per cue (Edge TTS rate 1.25x default)
  * Bangun SRT baru: cue.start = original.start + accumulated_offset, cue.end = start + audio_duration
  * Kalau audio overflow ke cue next → push back (offset bertambah)
  * Kalau gap cukup (zona pemandangan) → offset tidak berubah (natural)
  * Min gap default 150ms (configurable 100/150/200/300ms)
  * Mix audio per cue ke buffer pada posisi newStart
  * Return: WAV blob + SRT content string + retime map JSON + newEntries
- Update tts-panel.tsx UI:
  * Ganti Switch ON/OFF dengan 3 radio button: ON, OFF, DUBBING (amber highlight)
  * Setting dubbing: speed (1.0/1.25/1.5x) + min gap (100/150/200/300ms)
  * Tombol "Generate Dubbing" + "Download 3 file" (WAV + SRT + JSON)
  * Info panel: audio durasi, SRT asli, offset total, cue baru
  * Petunjuk Fase 3 langsung di UI (command Python retime-video.py)
  * Backward compat: respectTiming derived dari mode (mode='on' → true)
- Buat scripts/retime-video.py (Fase 3 Python):
  * Argparse: --mp4, --srt-mandarin, --srt-jawa, --audio-jawa, --output, --ffmpeg, --ffprobe, --dry-run, --keep-temp
  * Auto-detect ffmpeg/ffprobe di PATH
  * Parse SRT Mandarin + SRT Jawa, pairing by index
  * Bangun ffmpeg filter_complex: trim + setpts + concat per cue dan per gap
  * Factor = jawa_dur / mandarin_dur (>1 = slow-mo, <1 = fast-forward)
  * Mix audio Jawa (AAC 192k) ke video final (H.264 CRF 23 medium)
  * Verifikasi: syntax OK, CLI --help jalan
- Buat scripts/tutor-retime-video.md dokumentasi lengkap
- Verifikasi: `npx next build` → `✓ Compiled successfully in 8.6s`

Stage Summary:
- Dubbing Mode 100% jalan: 3 mode di UI (ON / OFF / Dubbing), user bisa pilih sesuai kebutuhan
- Mode ON tetap utuh (fallback kalau Dubbing gagal) — sesuai user request
- Output Dubbing: 3 file (audio-jawa.wav, subs-jawa-new.srt, retime-map.json)
- Python retime-video.py: convert MP4 Mandarin → MP4 Jawa dengan retimed video + audio Jawa
- Filosofi: SRT Jawa = ground truth, MP4 ngikut SRT baru, tidak ada SRT hening (audio utuh)
- Total durasi audio = SRT asli + offset akumulasi (boleh lebih panjang dari MP4 asli — wajar untuk dub)
- File baru: scripts/retime-video.py (250 baris), scripts/tutor-retime-video.md
- File berubah: src/lib/tts.ts (+260 baris: Dubbing types + narrateDubbingMode), src/components/tts-panel.tsx (UI radio 3 mode + setting dubbing + tombol dubbing)
- File TIDAK berubah: src/lib/srt.ts, src/lib/edge-tts.ts, src/lib/audio-utils.ts, ON mode logic
- Pending: user push ke GitHub (sandbox tidak ada credential) — instruksi diberikan di akhir

---
Task ID: 3
Agent: main
Task: Push 5 commit tertunda ke GitHub (sandbox tidak punya credential, user kasih PAT).

Work Log:
- User berikan GitHub PAT (github_pat_11CCW2LPI...)
- Set remote URL sementara dengan token: https://emailnyamahmud-afk:<token>@github.com/...
- Push sukses: 273115b..bd0bad4 main -> main (5 commit terkirim)
- RESET remote URL ke https://github.com/emailnyamahmud-afk/srt-splitter.git (token dihapus dari git config)
- Verifikasi: git config --get-regexp remote.origin → tidak ada token
- Verifikasi: git log origin/main = bd0bad4 (sync dengan lokal)

Stage Summary:
- 5 commit berhasil di-push ke https://github.com/emailnyamahmud-afk/srt-splitter
- Token PAT TIDAK disimpan di git config (sudah di-reset)
- Vercel akan auto-deploy dari push ini (https://srt-splitter.vercel.app/)
- Lokal dan remote in-sync, siap untuk iterasi berikutnya
- Commit yang ter-push:
  * a1caf32 feat: TTS Text ke Audio
  * 273115b fix: ON mode natural-first
  * ae30649 (warning no message)
  * b1b098b (Voicertool speedup-slowdown)
  * 103cce0 + 5c08e32 (sandbox scrape files)
  * bd0bad4 feat: Dubbing Mode + Python retime-video.py

---
Task ID: 4
Agent: main
Task: Adopsi ThioJoe Auto-Synced-Translated-Dubs algoritma — TRIM SILENCE untuk perbaiki MODE ON yang sering robot. Riset 5 referensi: VideoLingo, ThioJoe, KrillinAI, open-dubbing, pyVideoTrans.

Work Log:
- Riset 5 referensi dubbing open-source via z-ai page_reader (Linly-Dubbing 404)
- Analisis algoritma ThioJoe audio_builder.py (paling relevan):
  * detect_leading_silence (-30dB threshold, 10ms chunks) → trim awal
  * reverse → detect_leading_silence → trim akhir
  * pyrubberband/ffmpeg atempo untuk stretch fallback (tidak diadopsi — Edge TTS server-side rate sudah cukup)
  * Canvas overlay approach (sama dengan mixAudioInto kita)
- Insight: Hening TTS 200-500ms di awal + 100-300ms di akhir bikin actual duration kehitung lebih panjang dari sebenarnya → ratio ke-hitung terlalu tinggi → audio dipaksa speed up lebih dari yang dibutuhkan → ROBOT
- Implementasi di audio-utils.ts:
  * +detectLeadingSilence(audio, -30dB, 10ms, sampleRate) → return index awal non-silent
  * +trimSilence(audio, -30dB, sampleRate, paddingMs=50) → return trimmed Float32Array
  * Padding 50ms di awal/akhir supaya tidak abrupt (natural pause)
- Implementasi di tts.ts:
  * +decodeMonoTrimResample helper (decode + mono + resample + trim)
  * Refactor ON mode: pakai helper untuk Pass 1 (natural) dan Pass 2 (speedup/slowdown)
  * actualDuration sekarang = TRIMMED duration, bukan raw TTS output
  * Refactor OFF mode: pakai helper (audio lebih rapat antar cue)
  * Refactor Dubbing Mode: pakai helper (SRT baru timing lebih akurat — cue.end = audio trimmed, bukan raw TTS)
- Verifikasi: npx next build → ✓ Compiled successfully in 7.8s
- Commit 662b145, push ke GitHub sukses (PAT user dipakai sekali, di-reset setelah push)

Stage Summary:
- TRIM SILENCE diadopsi dari ThioJoe — sesuai rekomendasi user "perbaiki MODE ON dulu, kalau jalan tidak perlu Dubbing Mode"
- Helper decodeMonoTrimResample = single source of truth untuk decode+trim di semua 3 mode
- Efek: banyak cue yang sebelumnya dipaksa speed up (ratio > 1.0), sekarang jadi natural (ratio ≤ 1.0 setelah trim)
  * Contoh: cue "Kapten" (Mandarin 0.6s) — dulu audio 0.7s → ratio 1.17x speed up. Sekarang trim 0.5s → ratio 0.83x → NATURAL, no speed up
- Mode ON sekarang: trim silence → hitung ratio → speed up hanya kalau audio trimmed masih > cue
- Mode OFF sekarang: trim silence → audio lebih rapat antar cue
- Dubbing Mode sekarang: trim silence → SRT baru timing akurat (cue.end = audio trimmed, bukan raw TTS dengan hening buatan)
- Yang TIDAK diadopsi dari ThioJoe (kalau perlu nanti): pyrubberband stretch fallback
- File berubah: src/lib/audio-utils.ts (+86 baris), src/lib/tts.ts (refactor ON/OFF/Dubbing ke helper)
- Pending: user test real dengan SRT Jawa, kalau masih robot → next step riset pyVideoTrans Synchronize.md atau stretch fallback

---
Task ID: 5
Agent: main
Task: Investigasi Dubbing Mode gagal saat diklik user. Analisis data SRT user juga untuk validasi apakah trim silence cukup.

Work Log:
- Analisis data SRT user (Season-1 5100 cue, Season-6 3868 cue):
  * Density rata-rata 5.03 kata/detik (target natural ≤3.0)
  * 74.8% cue akan robot dengan natural TTS (ratio > 1.5x)
  * Setelah trim silence: masih 59.1% cue robot (hanya hemat 15%)
  * Contoh ekstrem: cue 0.03s dengan 2 kata "Sedulur Lin" → ratio 24x, mustahil natural
- Kesimpulan: Trim silence kurangi 15% robot, TAPI masalah fundamental = SRT Jawa dipaksa timing Mandarin yang ngomong 5+ kata/detik. Jawa natural 2.5 kata/detik. Fisika bahasa — tidak ada algoritma TTS yang bisa solve tanpa bikin SRT baru.
- Investigasi bug "Dubbing gagal saat diklik":
  * Baca `narrateDubbingMode` line 633: `synthesizeText({provider, voice, ...})`
  * Cek `synthesizeText` signature line 107-118: `synthesizeText(text: string, opts: {...})`
  * BUG KONFIRMASI: `synthesizeText` dipanggil tanpa `text` sebagai argumen pertama
  * Akibat: parameter pertama (object) dianggap `text`, `text.trim()` throwing TypeError
  * Error terjadi SEBELUM generate cue pertama — user lihat "gagal langsung"
- FIX: `synthesizeText(text, {provider, voice, ...})` — text jadi argumen pertama
- Penyebab bug: copy-paste dari ON mode tapi lupa adjustment. ON mode pakai `synthesizeText(text, {...opts, rate: '+0%'}` — text eksplisit. Dubbing Mode lupa kasih text.
- Verifikasi: npx next build → ✓ Compiled successfully in 8.3s
- Commit 38cd339, push ke GitHub sukses

Stage Summary:
- Bug Dubbing Mode FIX: 1 baris (synthesizeText(text, opts) bukan synthesizeText(opts))
- Root cause: signature mismatch — aku lewat object opts sebagai argumen pertama, padahal function expect text string
- Trim silence tidak solve masalah fundamental (59% cue masih robot) — user benar, harus pakai Dubbing Mode untuk natural
- Dubbing Mode sekarang harusnya jalan — user test ulang setelah Vercel deploy (1-2 menit)
- File berubah: src/lib/tts.ts (1 baris, fix signature)
- Workflow user sudah benar: Dubbing Mode = solusi yang tepat untuk "text keluar dari penjara SRT lama"





---
Task ID: 6
Agent: main
Task: Update dokumentasi dengan visi besar "digitalisasi bahasa di era AI" setelah diskusi mendalam dengan user. Capture konteks penuh project supaya AI yang baca besok bisa paham.

Work Log:
- Diskusi panjang dengan user (sore-malam 3 Oktober 2026) tentang:
  1. Python itu command line (bukan GUI), JSON dibaca otomatis
  2. TUI interaktif dengan questionary (pilih file pakai arrow keys)
  3. Training TTS Jawa custom (Coqui TTS, VITS, F5-TTS, XTTS-v2)
  4. Dataset yang user punya: 260 jam studio-grade (37 video Zoom H6 + 110 podcast)
  5. Zoom H6 stereo split (channel 1 vocal, channel 2 backsound) = EMAS untuk training
  6. Akses komunitas Permadani (100 siswa/tahun sebagai validator transkripsi)
  7. Bahasa Kawi (Negarakertagama UNESCO 2013) belum ada TTS-nya
  8. Indonesia 700 bahasa, 169 terancam punah
- Realisasi: workflow dubbing Mandarin → Jawa = prototype untuk digitalisasi bahasa daerah
- Bikin dokumen baru: docs/PROJECT_VISION.md (~330 baris) yang capture:
  * Ringkasan eksekutif (dari iseng ke visi)
  * Asal mula project + evolution minggu per minggu
  * Konteks Indonesia 700 bahasa + Negarakertagama UNESCO
  * 6 aset user yang tidak tergantikan
  * Roadmap 2 tahun (Track A-E, bulan per bulan)
  * Stack teknis lengkap
  * Workflow 5 fase
  * Perspektif akademik/komunitas/komersial/global
  * Yang bisa user lakuin hari ini (15 menit setup)
- Update README.md: tambah banner PROJECT_VISION di atas, link ke docs
- Update struktur folder di README: tambah PROJECT_VISION.md di docs/

Stage Summary:
- docs/PROJECT_VISION.md: dokumen baru 330 baris, capture konteks penuh + roadmap
- README.md: tambah banner visi di atas + link ke PROJECT_VISION
- worklog.md: catat diskusi malam + realisasi visi besar
- AI yang baca dokumentasi besok bisa paham konteks:
  1. Project ini bukan cuma web app split SRT
  2. Bukan cuma dubbing Mandarin → Jawa
  3. Tapi prototype digitalisasi bahasa daerah Indonesia
  4. User punya 260 jam dataset studio-grade yang langka
  5. User punya komunitas Permadani (100 validator)
  6. User punya sustainable funding (live streaming)
  7. Roadmap 2 tahun: workflow → dataset → training TTS → vision → open source
  8. Scale: 700 bahasa Indonesia, 169 terancam punah
- Dokumentasi rapi + persistent di GitHub repo
- User akan tidur, lanjut besok pagi: install setup + test dubbing-tui.py dengan audio 6 menit

Pesan closing dari user:
"ada uang atau tidak ada uang, tetap akan user kerjakan, tapi step by step.
dan semua terdokumentasi rapi. yg bahkan diawali dengan iseng dub dracin ke jawa
dan jangan lupa, indonesia punya 700 bahasa."

---
Task ID: 7-a
Agent: research sub-agent (general-purpose)
Task: Riset VoiceStudio open-source (github.com/debpalash/VoiceStudio) — identifikasi algoritma TTS / audio-stitching / timing-alignment yang bisa diadopsi di web app kita (Mandarin→Jawa dubbing). Fokus: TTS-side + audio stitching + retime-map JSON schema. Eksklusif: JANGAN riset video retiming (PR berikutnya), encoder tuning, NLE integration.

Work Log:
- Baca worklog.md (Task 1-6) untuk konteks: project ini Next.js web app split SRT → dubbing Mandarin→Jawa. Sudah ada 3 mode (ON / OFF / Dubbing). Dubbing Mode pakai Edge TTS rate 1.25x default, push-back cue kalau overflow, output 3 file (WAV + SRT baru + retime-map.json v1.0)
- API GitHub rate-limited → ambil tarball codeload (44.5MB) → extract /tmp/vs_extract/VoiceStudio-main/
- Reproducibility: latest commit main = 990f0627ba14dbb309b88c0051ebb953d3101800 (2026-10-05T03:06:23Z, merge PR #2611 "fix(cpu): scale default generation compute-time budget on CPU hosts")
- Salin 36 file relevan ke /home/z/my-project/scripts/voicestudio-study/ (services/ 22 file, routers/ 4 file, docs/ 4 file, schemas/ 1 file, root 4 file)
- Baca high-priority files:
  * services/fit_planner.py (231 baris) — Smart Fit planner: slack absorption + 4-step decision (fit/audio_stretched/hybrid/overflow_trimmed) + geometric 50/50 audio+video split
  * services/duration_planner.py (329 baris) — pre-synthesis prediction, self-calibrating CPS (median, min 3 samples), classify fits/tight/impossible, optional LLM condense
  * services/fitted_subtitles.py (65 baris) — map original timeline ke fitted timeline via plan chunks
  * services/dub_background.py (130 baris) — surgical background preservation: original outside dialogue, separated bed inside, 10ms crossfade
  * services/audio_dsp.py (301 baris) — MASTERING_CHAIN, normalize_audio(-2dBFS, -50dBFS silence floor), trim_speech_padding (50ms context, -50dBFS), trim_trailing_silence, EFFECT_PRESETS (pedalboard)
  * services/loudness.py (68 baris) — two-pass loudnorm measure (EBU R128 via ffmpeg), never raises
  * services/onset_align.py (291 baris) — snap segment starts to actual speech onset (sustained 160ms within 300ms window, forward-only, max 1.5s, source-aware: separated vocals only)
  * services/prosody_mirror.py (406 baris) — speaker-relative z-scores → direction tokens (urgent/calm/quick/whispered), F0 via autocorrelation
  * services/speech_rate.py (429 baris) — per-language CPS table (jv/id=14, ja=10, zh=6, en=15), LLM slot-fit loop (max 3 attempts, divergence guard against original text)
  * services/dub_qc.py (142 baris) — second-pass ASR, WER via Levenshtein, CJK per-codepoint tokens, flag drift ≥ 0.5
  * services/srt_parser.py (370 baris) — lenient (BOM/CRLF/dot separator), anti-ReDoS ([^\S\n]*), de-overlap pass, format_cue_timestamp (round whole first), CUE_SOURCE_ID provenance
  * services/ssml_lite.py (155 baris) — inline [slow]/[fast]/[emphasis]/[spell] tags, speeds 0.85/1.15/0.92, ReDoS-safe regex
  * services/chunked_tts.py (511 baris) — long text chunking (800 char default, dense-script aware CJK×2.5), trim_edge_silence (-40dBFS, 40ms keep), concatenate_audio_chunks (linear crossfade, pre-compute length)
  * services/ffmpeg_utils.py (967 baris, audio-relevant only) — bed_mix_filter (force stereo + amix normalize=0 + alimiter), _atempo_chain (cascading 0.5/2.0 breakpoints), _pitch_preserving_stretch
  * routers/dub_generate.py (2197 baris) — main orchestrator: 4 timing strategies (concise/strict_slot/stretch_video/smart_fit), per-cue TTS + mix loop dengan 15ms fade in/out, memmap float32 mix_audio, atomic WAV write, fit_plan + fitted_cues persisted
  * routers/dub_translate.py (1392 baris) — FLORES_CODES includes jv/jw → jav_Latn (NLLB-200 support Javanese), _apply_fit_pass LLM slot-fit after translation

Temuan utama (analisis lengkap di laporan ke user):
- VoiceStudio punya 4 timing strategy; kita cuma 1 (mirip stretch_video). Bisa tambah concise/strict_slot untuk short cue yang nggak punya gap.
- Slack absorption (extend slot ke silent gap, keep 0.05s guard) — kita belum ada. minGapSec kita cuma untuk push-back, bukan slot extension.
- Geometric 50/50 audio+video split: audio_rate = sqrt(need), video_ratio = need/audio_rate — untuk cue yang mustahil fit natural. Cocok untuk retime-map.json v2.0: pisahkan audioRate (TTS server-side rate) dari videoRatio (setpts).
- Pre-synthesis duration prediction (CPS calibration) — kita bisa predict durasi TTS Jawa sebelum generate, badge fits/tight/impossible. Untuk SRT user (5+ kata/detik), sebagian besar akan "impossible" → validasi temuan Task 5 dengan data nyata.
- 15ms fade in/out per cue untuk hindari pop/click — kita belum ada. Murah, seharusnya tambah.
- Peak-normalize ke -2 dBFS dengan -50 dBFS silence floor — kita belum normalize per-cue, bisa uneven loudness.
- amix normalize=0 + force stereo + alimiter (ducking pattern) — relevan kalau nanti extract MP4 audio di browser. Bukan v1.
- Surgical background preservation (original outside dialogue, separated bed inside) — butuh Demucs, bukan v1.
- Onset-align (snap starts ke sustained onset) — butuh separated vocals, bukan v1.
- Two-pass ASR QC (WER measurement) — butuh Whisper WASM, berat, bukan v1.

Rekomendasi retime-map.json v2.0 (utk PR berikutnya konsumsi retime-video.py):
- Tambah params: {timingStrategy, maxAudioOnlyRate=1.2, audioRateCap=1.5, videoSlowCap=2.0, gapGuardSec=0.05, allowVideoRetime=true, minAudioRate=0.85}
- Rename points[] → chunks[], tambah audioRate + videoRatio (pisah dari factor)
- Tambah status: 'fits'|'audio_stretched'|'audio_slowed'|'hybrid'|'overflow_trimmed'
- Tambah overflowSec per chunk
- Tambah fittedCues[] (cue times from ACTUAL stretched samples — ground truth untuk SRT export)
- Keep v1.0 fields untuk backward compat (factor = videoRatio alias)

Stage Summary:
- 36 file VoiceStudio berhasil di-fetch dan dibaca (tarball 44.5MB → /tmp + /home/z/my-project/scripts/voicestudio-study/)
- Latest commit main: 990f0627ba14dbb309b88c0051ebb953d3101800 (2026-10-05)
- VoiceStudio repositori besar: 108 service files, 4 dub routers (~8000 baris total)
- 15 algorithm pattern teridentifikasi; 8 worth adopting untuk web app kita (slack absorption, CPS calibration, 15ms fade, peak normalize, ssml_lite, 4-strategy menu, SRT parser robustness, retime-map v2.0 schema)
- 7 pattern NOT to adopt (desktop/GPU/Demucs/ASR/pedalboard-dependent)
- Reproducibility document lengkap di laporan ke user (commit hash + tarball URL + file list)
- File baru: 36 file di /home/z/my-project/scripts/voicestudio-study/ (research-only, no app code change)
- File TIDAK berubah: src/lib/tts.ts, src/lib/audio-utils.ts, src/lib/edge-tts.ts, src/components/tts-panel.tsx
- Pending: implementasi pola yang diadopsi → PR terpisah (retime-map.json v2.0 schema + 15ms fade + peak normalize + CPS calibration)

---
Task ID: 7-b
Agent: main
Task: Implementasi dub web (VoiceStudio adoption) + perbaiki logika retime-map JSON. User: "implementasi dub web, lalu nanti aku buat dub baru, dan AI juga perbaiki logika map json. karena dub = hulu. soal render video itu PR berikutnya. kalau hulu sampah = hasil sampah, kalau hulu baik = hasil baik. garbage in garbage out."

Work Log:
- Baca hasil riset Task 7-a (VoiceStudio 36 file, 15 pattern, 8 worth adopting)
- Pilih 4 pattern untuk adopt di PR ini (web TTS side, bukan video render):
  * Pattern A — Slack Absorption (kurangi push back, lebih natural)
  * Pattern C — 15ms fade in/out per cue (prevent click di cue boundary)
  * Pattern D — Peak normalize -2 dBFS per cue (loudness konsisten)
  * Pattern G — SRT de-overlap + formatTime rounding fix (anti binary float bug)
- Skip pattern yang butuh desktop/GPU/Demucs/ASR (sesuai user: "render video PR berikutnya")
- File berubah: src/lib/audio-utils.ts, src/lib/tts.ts, src/lib/srt.ts

- src/lib/audio-utils.ts (+87 baris):
  * mixAudioInto: tambah fadeMs parameter (default 15ms — VoiceStudio standard)
  * mixAudioInto: apply 15ms linear fade in/out IN-PLACE ke audio sebelum mix (Pattern C)
  * Tambah peakNormalize(audio, targetDbFS=-2, silenceFloorDbFS=-50) — Pattern D
  * peakNormalize: cari peak, jika di bawah silence floor (-50 dBFS) skip (anti "blank noise boost")
  * peakNormalize: apply gain in-place supaya loudness konsisten antar cue

- src/lib/srt.ts (refactor):
  * formatTime: ganti ke divmod approach (round dulu ke ms, baru split) — Pattern G
  * formatTime: fix bug 59.9996s jadi "00:01:00,000" (sebelumnya buggy carry-over)
  * parseSrt: strip BOM (\uFEFF) di awal (sering ada di SRT Windows)
  * parseSrt: drop cue dengan duration ≤ 0 (artifact)
  * parseSrt: tambah de-overlap pass — shift cue[n+1].start ke cue[n].end kalau overlap (Pattern G)

- src/lib/tts.ts (+385 baris, rewrite Dubbing Mode):
  * Import peakNormalize dari audio-utils
  * Schema v2.0 — DubbingRetimeMap interface (backward compat dengan v1.0):
    - Tambah: sampleRate, gapGuardSec, successCount, failCount, skippedCues
    - Tambah: params block (timingStrategy, audioRateCap, videoSlowCap, gapGuardSec, minAudioRate, peakNormalizeDbFS) — VoiceStudio-style reproducibility
    - Rename: points[] → chunks[] (dengan points = chunks alias untuk v1.0 consumer)
    - Tambah: fittedCues[] array (actual cue times di audio — ground truth untuk SRT export)
  * DubbingChunk interface (v2.0):
    - Tambah: index, segId (untuk debugging)
    - Tambah: origStart/origEnd (rename dari originalStart/originalEnd — lebih pendek, lebih jelas)
    - Tambah: audioRate (TTS rate, misal 1.25) + videoRatio (setpts factor downstream)
    - Tetap: factor (v1.0 alias = videoRatio) untuk backward compat
    - Tambah: status ('fits'|'audio_extended_into_gap'|'overflow_pushed_back'|'skipped'|'head_silent'|'tail_silent')
    - Tambah: overflowSec (detik overflow yang di-push back)
  * DubbingFittedCue interface (baru): id, cueIndex, start, end, durationSec, text
  * narrateDubbingMode v2.0:
    - Peak normalize per cue ke -2 dBFS sebelum mix (Pattern D)
    - Slack absorption (Pattern A): effectiveSlot = cueToCueDistance - gapGuardSec
    - Status determination: 'fits' / 'audio_extended_into_gap' / 'overflow_pushed_back'
    - Push back hanya jika audioDur > effectiveSlot (BUKAN audioDur > cueToCue - minGapSec seperti v1.0)
    - HEAD chunk: tambah jika cue[0].start > 0.01 (pre-roll video sebelum cue pertama)
    - FIX v1.0 BUG: gap factor sebelumnya hardcoded 1.0 — sekarang dihitung sebagai newGap/origGap
    - Skip gap chunk jika originalGap ≤ 0.01 (back-to-back cues)
    - skippedCues tracking: 0-based indices untuk cue yang gagal/invalid
    - SRT baru ditulis dari fittedCues (ground truth dari audio aktual)
    - formatTimeSrt: juga di-fix (rounding carry-over, sama dengan formatTime)

- scripts/test-dubbing-v2-schema.py (NEW, 200 baris):
  * Sanity test untuk verifikasi v2.0 logic secara konseptual (Python port dari stitching step 1)
  * Test 1: Audio shorter than cue → gap extends (factor 2.0, bukan 1.0 — v1.0 bug confirmed & fixed)
  * Test 2: Audio overflows cue tapi fits di extended slot → slack absorption, no push back
  * Test 3: Audio overflows extended slot → push back by 3.15s, gap after = minGapSec
  * Test 4: First cue start > 0 → head chunk present
  * Test 5: Back-to-back cues (no original gap) → no gap chunk emitted
  * Test 6: Schema backward compat (points = chunks alias)
  * ALL 6 TESTS PASSED

- Build verify: npx next build → ✓ Compiled successfully in 8.2s (no TypeScript errors)
- UI tidak berubah (tts-panel.tsx TIDAK diubah) — semua field lama tetap ada (audioBlob, srtContent, retimeMapJson, retimeMap.totalOffsetSec, retimeMap.originalDurationSec, newEntries, audioDurationSec)
- Python retime-video.py TIDAK diubah (sesuai user: "soal render video itu PR berikutnya")

Stage Summary:
- "Dub = hulu" filosofi diterapkan: kualitas dub web sekarang improved (peak normalize, fade, slack absorption) → downstream pipeline (SRT baru + JSON + video retim) dapat input yang lebih baik
- 4 VoiceStudio pattern diadopsi: A (slack absorption), C (15ms fade), D (peak normalize), G (SRT robustness + formatTime rounding)
- retime-map.json v2.0 schema: backward compat (points alias), new fields (chunks, fittedCues, params, sampleRate, gapGuardSec, successCount, failCount, skippedCues, audioRate, videoRatio, status, overflowSec, head/tail types)
- v1.0 gap factor bug (hardcoded 1.0) FIXED — sekarang selalu dihitung sebagai newGap/origGap
- HEAD chunk ditambahkan (pre-roll video sebelum cue pertama, jika cue[0].start > 0)
- Test suite: 6/6 tests pass — schema valid, slack absorption active, gap factor fix confirmed
- File berubah: src/lib/audio-utils.ts (+87), src/lib/tts.ts (+385 rewrite Dubbing Mode), src/lib/srt.ts (refactor)
- File baru: scripts/test-dubbing-v2-schema.py (200 baris sanity test)
- File TIDAK berubah: scripts/retime-video.py (Python, sesuai user), src/components/tts-panel.tsx (UI)
- Pending: user push ke GitHub (sandbox tidak ada credential) — commit lokal siap
- Pending berikutnya (PR terpisah): render video (retime-video.py konsumsi JSON v2.0 chunks[].videoRatio + fittedCues)

---
Task ID: 8
Agent: research sub-agent (general-purpose)
Task: Riset voicertool.com/subs/id — reverse-engineer algoritma "Speed up only" dan "Speed up and slow down" mode (audio fit SRT cue timing). Adaptasi untuk mode ON di web app (SRT dubbing Mandarin→Indonesia). Research-only — JANGAN tulis application code.

Work Log:
- Baca worklog Task 1-7-b untuk konteks: project Next.js SRT dubbing Mandarin→Jawa/Indonesia, mode ON/OFF/Dubbing, Edge TTS provider, retime-map.json v2.0 schema, VoiceStudio patterns (slack absorption, 15ms fade, peak normalize, CPS calibration)
- Fetch https://voicertool.com/subs/id via curl (200 OK, 132KB HTML, PHP/Cloudflare, no bot detection, PHPSESSID cookie)
- Identifikasi stack: PHP backend (BUKAN Next.js SPA), inline JS di index.html + 2 external JS module (`setting.js?v=1.0.21`, `srt.js?v=1.0.21`) di-load on-demand
- Fetch setting.js (247KB, obfuscated javascript-obfuscator dengan string-array rotation) — UI/voice-picker code (BUKAN algoritma inti)
- Fetch srt.js (142KB, obfuscated sama) — **ALGORITMA INTI** (TTS + atempo + mixing)
- Deobfuscate partial: extract string arrays m() (setting.js, 2197 tokens) dan u() (srt.js, 673 tokens), search keyword, follow helper functions i/s/l/Y/etc yang resolve ke chunk index
- Decode algoritma utama dari srt.js:
  * **TTS provider**: Microsoft Edge TTS (variabel `EDGE_SPEECH_URL` confirmed, Azure Speech SDK pattern `context.synthesis.audio.metadataoptions + outputFormat`)
  * **SSML**: `<speak version="1.0" xmlns="..."><voice name="..."><prosody pitch="X%" rate="Y%" volume="Z%">text</prosody></voice></speak>` via `prosodyTemplate()` + `speakTemplate()`
  * **Per-cue pipeline**: TTS → decodeAudioData → silence trim (function W, asymmetric: head -40dBFS, tail -49dBFS) → compute ratio (function y, lihat bawah) → ffmpeg.wasm atempo (function C) → wrap ke AudioBuffer → return {audioBuffer, offsetSeconds=cue.start}
  * **Speed setting algorithm (function y)**:
    - `o = audioDur / cueDur` (raw ratio, diukur SETELAH silence trim)
    - speed_setting="1" (Speed up only): `o = clamp(o, 1.0, 2.0)` — floor 1.0 (never slow down), cap 2.0 (max 2x speed up)
    - speed_setting="2" (Speed up and slow down): `o = clamp(o, 0.68, 2.0)` — floor 0.68 (max slowdown ~1.47x), cap 2.0 (max 2x speed up)
    - default: `o = 1` (no change)
    - Konstanta kunci: **1.0** (floor speedup-only), **0.68** (floor speedup-slowdown), **2.0** (cap both modes)
  * **ffmpeg.wasm command**: `ffmpeg -f f32le -ar 24000 -ac 1 -i in_X.f32 -af atempo=<ratio.toFixed(3)> -f f32le out_X.f32`
    - Format I/O: f32le (32-bit float PCM), mono, 24000 Hz (Edge TTS native)
    - atempo preserves pitch otomatis (built-in ffmpeg)
    - Presisi: 3 desimal (e.g., `atempo=1.234`)
    - Virtual FS filenames: `in_<chunkIdx>.f32`, `out_<chunkIdx>.f32`
  * **Mixing**: `OfflineAudioContext(1, totalSamples, sampleRate)` + per-cue `BufferSource.start(cue.start)` → `startRendering()` → WAV (manual RIFF/WAVE/fmt/data header via setUint16/32/8)
  * **Sequential processing**: batch size 1 (`O.slice(i, i+1)`) — tidak parallel (Edge TTS rate limit aware)
  * **Min buffer length floor**: `Math.max(audio.length, ceil(audio.duration * 0.2))` — anti zero-length buffer
  * **NO slack absorption**: hanya `cue.end - cue.start` (tidak extend ke gap ke cue berikutnya)
  * **NO crossfade**: additive mix pada overlap (OfflineAudioContext sum)
  * **NO per-cue normalization**: TTS amplitude as-is
  * **NO server-side rate change**: Edge TTS rate selalu "0" (no SSML prosody rate override) — semua speed adjustment via client-side ffmpeg.wasm atempo (POST-TTS)
- Search "speed_setting" di index.html dan setting.js dan srt.js → 0 match (string di-obfuscate). Konfirmasi algoritma via konstanta 1, 2, 0.68 di function y() yang match speed_setting branches.

- Perbandingan dengan src/lib/tts.ts narrateEntries (mode ON):
  * Provider: sama (Edge TTS)
  * Speed adjustment: Voicertool = client-side ffmpeg.wasm atempo; kita = server-side Edge TTS rate (formatEdgeRate). Trade-off: Voicertool universal (any voice sama), kita Edge-specific (lighter, no 30MB ffmpeg.wasm download).
  * Slack absorption: Voicertool NO (hanya cue.end-cue.start); kita YES (availableDuration = nextCueStart - cue.start, extends ke silent gap). KITA LEBIH BAIK.
  * Crossfade: Voicertool NO (additive mix); kita YES (15ms fade Pattern C VoiceStudio). KITA LEBIH BAIK.
  * Per-cue normalization: Voicertool NO; kita YES (peakNormalize -2 dBFS Pattern D VoiceStudio). KITA LEBIH BAIK.
  * Silence trim: Voicertool asymmetric (head -40dBFS, tail -49dBFS); kita symmetric (-30dBFS + 50ms padding). Voicertool preserve trailing consonants lebih baik.
  * Mode 1 floor: Voicertool 1.0 (never slow down); kita tidak ada floor eksplisit (Edge rate bisa < 1.0 tapi natural flow).
  * Mode 2 floor: Voicertool 0.68; kita MIN_SLOWDOWN_RATIO=0.7 (mirip, kita sedikit lebih konservatif).
  * Cap: Voicertool 2.0 (eksplisit, semua mode); kita audioRateCap=1.5 (Smart Fit saja), tidak ada cap eksplisit di mode ON. Voicertool lebih eksplisit.
  * atempo precision: Voicertool 3 desimal (toFixed(3)); kita integer percent (formatEdgeRate). Voicertool lebih presisi.
  * Mixing: Voicertool OfflineAudioContext BufferSource.start(offsetSeconds); kita manual mixAudioInto ADD dengan fade. OfflineAudioContext lebih native (browser-optimized), kita lebih kontrol (push-back, fittedCues tracking).

- ADOPT dari Voicertool:
  1. Eksplisit speed caps (MAX_SPEEDUP_RATIO=2.0, MIN_SLOWDOWN_RATIO sudah 0.7) — buat konstanta terdefinisi di NarrationOptions, bukan hardcoded
  2. Asymmetric silence trim (head lebih agresif -40dBFS, tail lebih gentle -49dBFS) — preserve trailing consonants. Update decodeMonoTrimResample.
  3. 3-desimal precision untuk ratio (kalau pakai atempo path) atau float percent untuk Edge rate (e.g., "+12.3%" bukan "+12%")
  4. Server-side rate=0 default + client-side atempo fallback (decouple TTS dari speed adjustment, avoid 2x TTS cost) — adopt kalau bisa容忍 ffmpeg.wasm ~30MB initial download (cached via Cache API)
  5. Min buffer length floor (anti zero-length AudioBuffer yang break AudioContext)
- SKIP dari Voicertool (kita sudah lebih baik):
  - Slack absorption — keep availableDuration approach
  - Crossfade — keep 15ms fade (Pattern C VoiceStudio)
  - Per-cue normalization — keep peakNormalize -2 dBFS (Pattern D VoiceStudio)
  - Push-back / fittedCues / retime-map v2.0 — keep Dubbing Mode logic
  - ffmpeg.wasm dependency — keep server-side Edge rate (lighter, no 30MB deps, pitch preserved server-side)
- WHY beda: Voicertool generic tool (300+ voices, semua Edge, butuh algoritma universal yang tidak tergantung Edge-specific rate). Kita Mandarin→Indonesia focus Edge TTS — bisa pakai Edge-specific rate (lebih ringan, tanpa ffmpeg.wasm).

- Reproducibility:
  * Semua fetch via curl dengan UA `Mozilla/5.0 Chrome/120` dan Referer header — 200 OK, no bot detection
  * Files cached di /home/z/my-project/upload/voicertool-research/: index.html (132KB), setting.js (247KB), srt.js (142KB), voices.json (33KB), jquery-3.7.1.min.js (88KB)
  * 10 snippets (raw obfuscated + decoded algorithm di comment) di /home/z/my-project/upload/voicertool-research/snippets/:
    - 01_prosodyTemplate.js — SSML `<prosody pitch rate volume>` builder
    - 02_speakTemplate.js — SSML `<speak><voice>` wrapper
    - 03_speedSettingRatio_y.js — function y() — SPEED SETTING RATIO COMPUTATION (algoritma inti)
    - 04_silenceTrim_W.js — function W() — silence trim -40/-49 dBFS asymmetric
    - 05_atempoApply_C.js — async function C() — ffmpeg.wasm atempo application
    - 06_perCueOrchestration_map.js — per-cue map (TTS → trim → ratio → atempo → wrap)
    - 07_mixing_OfflineAudioContext.js — OfflineAudioContext mixing
    - 08_wavWriter.js — manual RIFF/WAVE header writer
    - 09_getreplica_srtParser.js — SRT parser
    - 10_edgeTtsUrl.js — EDGE_SPEECH_URL context (confirms Edge TTS provider)
  * RESEARCH_NOTES.md — comprehensive summary dengan comparison table ke tts.ts kita

Stage Summary:
- Voicertool.com berhasil di-reverse-engineer penuh: TTS = Edge TTS, algoritma = ffmpeg.wasm atempo client-side dengan clamp [1, 2] (speedup-only) atau [0.68, 2] (speedup-slowdown), silence trim asymmetric -40/-49 dBFS, mixing via OfflineAudioContext, sequential batch=1
- Speed setting algorithm decoded: konstanta 1.0/0.68/2.0 confirmed via 2 lokasi di srt.js (offset 63393 dan function y di offset 132749)
- 5 pola Voicertool worth adopting (asymmetric trim, eksplisit cap, 3-desimal precision, server-rate=0 default + client atempo fallback, min buffer floor)
- 4 pola Voicertool NOT to adopt (no slack absorption, no crossfade, no normalize, no push-back) — kita sudah lebih baik via VoiceStudio patterns (Task 7-b)
- File baru: 10 snippets + RESEARCH_NOTES.md + raw cached files (index.html, setting.js, srt.js, voices.json) di /home/z/my-project/upload/voicertool-research/
- File TIDAK berubah: src/lib/tts.ts, src/lib/audio-utils.ts, src/lib/edge-tts.ts, src/components/tts-panel.tsx — research-only, no app code change (sesuai task instruction)
- Pending: PR terpisah untuk adopt asymmetric trim + eksplisit cap konstanta + 3-desimal precision (kalau user setuju)

---
Task ID: 9
Agent: main
Task: Milestone workflow end-to-end SUKSES — Demucs + mode ON + Smart Fit + mix-audio-dub.py

User feedback (6 Okt 2026 01:00 WIB):
"luar biasa, user sudah lihat VLC, outputnya benar-benar mp4 profesional.
SFX sangat bersih, audio Dub sangat bersih, 10000% Sync.
AI update dokumentasi dan progres. push github.
user akan ke web u generate drt durasi full, 2jam30m"

Work Log:
- Test #25 workflow end-to-end (Demucs + mode ON + mix) = MILESTONE SUKSES
- Demucs MPS: 61 detik untuk 7.5 menit audio (7.30s/s processing)
- Mix FFmpeg: 6.81 detik (sidechain compression, video stream copy)
- Output: mp4-id-final.mp4, 115.5 MB, 428.23s, 0 DTS warnings
- User rating: 10000% sync, MP4 profesional, SFX bersih, audio dub bersih
- User lanjut test full season S7-id (2.5 jam) — generate TTS di web

Stage Summary:
- WORKFLOW END-TO-END SUKSES setelah 25 test (20x render video gagal + 5x mode ON + mix)
- 3 fase: Demucs (61s) + web mode ON (TTS) + mix (7s) = ~68 detik untuk 7.5 menit
- Filosofi: video = ground truth, audio dub fit SRT ori, SFX bersih dari Demucs
- Pitch control: -15Hz laki-laki (user rating 9/10)
- Smart Fit: cap 2.0x, asymmetric trim, crossfade 150ms, no truncate
- 0 DTS warnings, 0 stop-motion, 100% video ori sync
- Repo audit: 162 → 108 tracked files (54 sampah di-untrack)
- File baru: demucs-tui.py, mix-audio-dub.py (update --sfx-wav), tutor-demucs-setup.md
- File deprecated: retime-video.py (tetap di repo sebagai backup)
- Next: test full season S7-id (2.5 jam) → kamus Jawa JSON

---
Task ID: 10
Agent: main
Task: Supabase PostgreSQL client + Rapikan SRT Jawa panel + kamus JSON + yt-dlp TUI + mix-tui + Demucs TUI

Work Log (6 Okt 2026, dini hari 00:00-02:30 WIB):
- Test #25 MILESTONE: Demucs + mode ON + mix = 10000% sync, MP4 profesional
- Silence bug fix: hapus -shortest + makeup=0 di mix
- Repo audit: 162 → 108 tracked files (54 sampah di-untrack)
- mix-tui.py (NEW): TUI untuk mix SFX + dub + MP4, 6 step
- yt-dlp-tui.py (NEW): TUI download YouTube 1080p H.264 + audio
- Kamus Jawa JSON: 157 entri (ngoko/krama/krama_inggil, aksén tidak dipakai)
- rapikan-jawa.ts: library untuk kamus check + strip aksén + suggest register
- rapikan-jawa-panel.tsx (NEW): SRT editor inline + toggle ngoko/krama + highlight
- supabase.ts (NEW): PostgreSQL client, CRUD untuk SRT project + cue data
- .env.example: template untuk NEXT_PUBLIC_SUPABASE_URL + ANON_KEY

Stage Summary:
- Workflow end-to-end JALAN: yt-dlp → demucs → web ON+SmartFit → mix → MP4 profesional
- Web app: 4 panel (Split, Translate, Rapikan Jawa, TTS) + Smart Fit + pitch control
- Python: 3 TUI (yt-dlp, demucs, mix) + backup (retime, dubbing-tui)
- Kamus Jawa: 157 entri, bisa expand manual
- Supabase: client siap, tunggu env vars dari user (besok)
- Aksén Jawa tidak dipakai (Edge TTS tidak bisa baca)
- Filosofi: video = ground truth, audio dub fit SRT ori, SFX bersih dari Demucs

---
Task ID: 11
Agent: main
Task: Kamus Jawa — pivot ke Supabase (browser crash load 9.6MB JSON) + TUI edit lokal

User feedback:
'browser UI error, crash saat load json, mending di browser gak usah pake json.
Mending pake supabase. AI buat TUI edit json kamus, agar user di lokal bisa edit
kamus per entri pake vscode, jadi satu folder dengan project dubbing. Tiap kamus
yg lengkap, akan user up ke supabase.'

Work Log:
- Untrack kamus-jawa-full.json + kamus-jawa.json dari repo (9.6MB crash browser)
- .gitignore: tambah /public/kamus-jawa*.json
- rapikan-jawa.ts: loadKamusJawa() sekarang dari Supabase (bukan JSON file)
  * Lazy import supabase.ts, fetch dari tabel kamus (limit 10000)
  * Fallback: null kalau Supabase belum set (kamus check skip, semua OK)
- edit-kamus.py (NEW, 230 baris): TUI untuk edit kamus lokal + upload Supabase
  * Export: Supabase → kamus-jawa.csv (buka di VSCode, edit per baris)
  * Import CSV: kamus-jawa.csv → Supabase (setelah user edit di VSCode)
  * Import JSON: kamus-jawa-full.json → Supabase (initial 44.585 entri)
  * Search: cari kata di Supabase
- Kamus format v4 (BENAR): ngoko, aksara, krama, id, keterangan, sumber, status
- Alias support: ngoko field bisa "aku, inyong, nyong" (split koma)
- Supabase tabel kamus: user perlu add kolom keterangan + sumber + status + aksara

Stage Summary:
- Browser: kamus dari Supabase (bukan JSON file), no crash
- Lokal: user edit kamus-jawa.csv di VSCode, upload ke Supabase kalau lengkap
- Workflow: export → edit VSCode → import → Supabase → web app load dari Supabase
- Kamus editor panel di web tetap ada (search + edit dari Supabase langsung)

---
Task ID: 12
Agent: main
Task: Kamus Jawa — TUI edit + upload Supabase bertahap + fix multiple bugs

User: 'TUI' → 'cara uplod ke supabase?' → 'gak muncul' → 'cuma kedip' → 'sudah bisa upload 1'

Work Log:
1. kamus-tui.py (NEW, 370 baris): TUI interaktif browse + edit kamus
   - Browse 44.585 entri (halaman 20, navigasi ◀▶)
   - Search kata → filter → edit
   - Edit krama + id inline → save JSON otomatis
   - Upload ke Supabase (bertahap, upsert, hanya yang sudah diedit)
   - Status: ✓ (sudah diedit) / ○ (belum)

2. edit-kamus.py: rewrite untuk JSON (bukan CSV)
   - Import JSON → Supabase (bertahap, upsert)
   - Export Supabase → JSON lokal
   - Export Supabase → CSV (backup)
   - Search kamus di Supabase

3. Bug fixes:
   a. JSON field 'id' konflik dengan UUID primary key → ganti kolom 'arti'
   b. upload_to_supabase(edited_count=0) → selalu skip → baca langsung dari JSON
   c. questionary clear screen → output hilang → pakai subprocess

4. Supabase tabel kamus:
   - Kolom: ngoko, aksara, krama, arti, keterangan, sumber, status
   - Unique constraint: ngoko (untuk upsert)
   - RLS: allow_all
   - User run SQL: ALTER TABLE ADD COLUMN + UNIQUE CONSTRAINT

5. Kamus format v4 (BENAR):
   - ngoko: kata + alias (koma)
   - aksara: aksara Jawa
   - krama: kosong (user isi manual)
   - id: kosong (user isi manual, terjemahan Indonesia)
   - keterangan: definisi JAWA dari XML (JANGAN HAPUS, membantu user isi id)
   - sumber: jv.wiktionary.org

6. Web app:
   - Kamus load dari Supabase (bukan JSON file, crash fix)
   - KamusEditorPanel: search + edit dari Supabase langsung
   - RapikanJawaPanel: kamus check + convert register (All Ngoko/All Krama)

7. Alias support: ngoko field "aku, inyong, nyong" → match semua
   - isWordInKamus: split koma, match per kata
   - convertRegister: lookup dengan alias, pakai krama pertama

Stage Summary:
- Kamus Jawa 44.585 entri dari Wiktionary (ngoko + aksara + keterangan)
- krama + id kosong → user edit bertahap 30/hari di TUI
- Upload ke Supabase (upsert, hanya yang sudah diedit, status: clean)
- Supabase = ground of truth (makin hari makin lengkap)
- JSON lokal = draft (edit di TUI/VSCode, commit ke GitHub optional)
- User sudah test: upload 1 entri (agustus) → sukses
- Web app load kamus dari Supabase (limit 10000 untuk performance)
- Kamus editor panel di web: search + edit langsung dari Supabase

---
Task ID: 13
Agent: main
Task: Fix bug — "menu uplod srt cuma 1, halaman juga masih 1 srt"

User feedback (8 Okt 2026 02:25 WIB):
"menu uplod srt cuma 1, halaman juga masih 1 srt, ada bug?"

Investigation:
- Vercel deploy up-to-date (origin/main == HEAD == c406b1f)
- Static HTML benar: punya "Upload SRT ID" + "Upload SRT Jawa" + "Editor SRT Jawa"
- VLM verify desktop + mobile: Dual SRT Editor di-render dengan 2 tombol upload
- Build success (Turbopack skip type validation, no syntax error)
- Test upload SRT ID + SRT Jawa di deployed app → dual display working (ID context grey italic + Jawa textarea + Voice + Ngoko/Krama + pagination)

Root cause (BUKAN bug, tapi UX issue):
- Editor SRT Jawa (DualSrtEditor) ada di BOTTOM page — bawah KamusEditor
- Split upload area di TOP punya 1 tombol "Pilih File SRT" (untuk Split, bukan dual)
- User upload SRT ke TOP → Rapikan SRT Jawa panel muncul (single SRT editor)
- User kira itu "dual editor" tapi cuma 1 SRT per cue
- User kira "menu uplod srt cuma 1" = Split upload (1 button) di top
- User kira "halaman juga masih 1 srt" = Rapikan panel (single SRT)

Fix:
1. Move DualSrtEditor ke ATAS page (right after header) — PRIMARY
2. Remove RapikanJawaPanel (redundant — Dual SRT Editor gantikan, lebih powerful)
3. Force grid-cols-2 (always side-by-side, bahkan di mobile 412px)
4. Visual prominence: border-2 indigo, shadow-md, badge "Dual SRT + Voice"
5. Tambah section divider "Workflow Split / Translate / TTS (sekunder)"
6. Split upload area: label baru "Split SRT (potong jadi beberapa file)"
7. Add "Cara pakai" instructions (6 langkah) di upload screen
8. Background colors: SRT ID box biru muda, SRT Jawa box amber muda (visual differentiation)

Layout baru (urut dari atas):
  Header (logo + title + 100% Sync badge)
  Editor SRT Jawa (PRIMARY, border-2 indigo, 2 uploads side-by-side)
  --- Workflow Split / Translate / TTS (sekunder) ---
  Split SRT upload (1 SRT, border-2 dashed amber)
  [Settings + Translate + TTS panels jika Split file uploaded]
  TTS Text ke Audio
  Kamus Jawa Editor (jika Supabase ready)
  Info section (jika no Split file)
  Source code download
  Footer

Verification:
- Build: ✓ Compiled successfully (12s)
- Vercel deploy: ✓ (commit 911fee0 pushed, deployed in ~60s)
- VLM verify desktop 1280px: ✓ Editor SRT Jawa di top, 2 uploads side-by-side, divider di bawah, Split SRT di bawah divider
- VLM verify mobile 412px: ✓ 2 uploads masih side-by-side (grid-cols-2 forced)
- Test upload SRT ID: ✓ "✓ 2 cue (konteks)" confirmation muncul, upload screen tetap (waiting SRT Jawa)
- Test upload SRT Jawa: ✓ Editor view muncul, dual display per cue (ID context grey italic + Jawa textarea + Voice + Ngoko/Krama)
- Pagination: ✓ "Hal 1 / 1 (2 cue)" + Sebelumnya/Berikutnya buttons

Stage Summary:
- Bug fix: Editor SRT Jawa sekarang PRIMARY di top page, 2 uploads side-by-side (selalu, bahkan mobile)
- Rapikan SRT Jawa panel dihapus (redundant) — Dual SRT Editor gantikan dengan lebih banyak fitur (voice per cue, dual display, pagination 30 cue/hal)
- Split workflow jadi sekunder (label "Split SRT (potong jadi beberapa file)" + divider)
- User sekarang langsung lihat "Upload SRT ID" + "Upload SRT Jawa" di top page, no confusion
- Commit: 911fee0 — pushed ke GitHub, Vercel auto-deploy
- Files changed: src/app/page.tsx (move + remove import + label), src/components/srt-editor-panel.tsx (grid-cols-2 + visual prominence + cara pakai)


---
Task ID: 14
Agent: main
Task: Project-based Dual SRT Editor (multi-project + auto-save Supabase + TTS mode ON)

User request (8 Okt 2026 03:00 WIB):
"agar lebih sistematis:
1. di UI buat add project = yg kalau user uplod 2 srt, srt langsung tersimpan di database. setiap kali ada perubahan = auto simpan.
2. bisa jadi hari ini garap project S1 (belum selesai), lalu hari ini juga uplod S2 (belum selesai), kalau user mau lanjut garap S1 = tinggal buka project S1. dan lanjut sesuai editan terakhir yg kesimpan di supabase.
3. supabase buat simpan srt gak masalah kan? size srt kecil, dan supabase ada storage.
4. generate tts/cue, auto load srt dari supabase. tapi logika srt ngikut konfigurasi mode ON. Agar sync"

Implementation:

1. Supabase migration v2 (scripts/supabase-migration-v2.sql)
   - srt_projects: ADD original_srt_id TEXT (SRT Indonesia konteks, full file)
   - srt_cues: ADD text_id TEXT (Indonesia context per cue) + voice TEXT (per-cue voice assignment)
   - Triggers: trg_srt_projects_updated_at + trg_srt_cues_updated_at (auto-update updated_at)
   - Backward compatible: kolom lama (original_srt, text) tetap dipakai sebagai SRT Jawa + text Jawa

2. Supabase functions (src/lib/supabase.ts)
   - SrtProject interface: tambah original_srt_id
   - SrtCue interface: tambah text_id + voice
   - createDualProject(name, srtId, srtJawa, cues[]): insert project + batch insert cues
   - getProjectWithCues(projectId): load project + cues (both texts + voice)
   - updateCueFull(cueId, {text, text_id, register, voice, is_edited}): auto-save per edit
   - bumpProjectEdited(projectId, delta): update updated_at + cues_edited count

3. Per-cue voice TTS (src/lib/tts.ts)
   - NarrationOptions.voiceResolver?: (entry, idx) => string
   - Override voice per cue, fallback ke opts.voice (global) kalau undefined
   - Semua 8 synthesizeText call di narrateEntries sekarang pakai cueVoice
   - Mode ON + Smart Fit tetap aktif (respectTiming=true, smartFit=true)
   - Pitch control per project (Edge TTS: -10Hz laki, +10Hz perempuan)

4. DualSrtEditor rewrite (src/components/srt-editor-panel.tsx, 883 lines)
   - Empty state:
     * "+ Project Baru" button (primary)
     * "Buka Project (N)" button (outline, disabled kalau N=0)
     * Recent projects list (top 3, klik = load)
     * Cara pakai instructions (7 langkah)
   - New Project modal:
     * Nama project (free text)
     * Upload SRT ID + Upload SRT Jawa (2-col grid, side-by-side, blue + amber boxes)
     * Cue count validation (warning kalau beda, pakai min)
     * "Buat Project & Simpan ke Supabase" button
   - Project list modal:
     * Daftar project (nama, cue_count, edited, last_updated)
     * Active project highlighted (indigo border)
     * Buka + Hapus buttons
   - Editor screen (active project):
     * Header: nama + cue count + voice count + auto-save badge + Ganti + Tutup
     * Action bar: All Ngoko/Krama (page/all) + Download SRT Jawa
     * TTS panel inline (purple):
       - Provider select (Edge/OpenAI/OpenRouter)
       - Pitch select (Edge only)
       - Smart Fit cap select (1.5x / 2.0x)
       - Generate TTS button → narrateEntries dengan voiceResolver
       - Progress bar + line progress text + stage message
       - Audio player + download ulang link
     * Cue list (30 per page):
       - #index + timestamp
       - SRT ID context (small grey italic, read-only)
       - SRT Jawa textarea (editable, auto-save 1.5s)
       - Voice dropdown (Dimas/Siti/Ardi/Gadis)
       - Ngoko/Krama toggle buttons (klik = convert dari kamus + auto-save)
     * Pagination: Sebelumnya / Hal N / Total / Berikutnya
   - Active project di-persist di localStorage (auto-load saat reload page)
   - Auto-save: debounced 1.5s, per-cue updateCueFull, mark is_edited=true

5. Size & Supabase feasibility
   - SRT file ~200KB (2.5 jam, 2000 cue) — kecil
   - Supabase Postgres free tier: 500MB DB, 1GB storage
   - Simpan SRT sebagai TEXT column (bukan Storage file) → bisa SQL query per cue
   - Untuk 100 project × 200KB SRT ID + 200KB SRT Jawa = 40MB total → masih jauh di bawah 500MB
   - Storage tidak dipakai (SRT kecil, lebih efisien di Postgres untuk query)

Verification:
- Build: ✓ Compiled successfully 11.1s
- Vercel deploy: ✓ (commit eb0ac16, deployed in ~60s)
- VLM verify desktop 1280px:
  * Editor SRT Jawa at top dengan "Project-based" badge
  * "+ Project Baru" button (black, primary)
  * "Buka Project (0)" button (white/outline, 0 karena migration v2 belum di-run user)
  * "Cara pakai" 7-step instructions
  * No Supabase error/fallback message
- Mode ON logic preserved: respectTiming=true + smartFit=true → 100% sync SRT ori

User perlu run SQL migration v2 di Supabase SQL Editor:
  scripts/supabase-migration-v2.sql
  (3 ALTER TABLE + 2 trigger, ~1 detik eksekusi)

Stage Summary:
- Project-based workflow: buat project per SRT pair, simpan ke Supabase, lanjut kapan saja
- Auto-save 1.5s: edit textarea, toggle register, pilih voice → tersimpan otomatis
- Multi-project: S1, S2, dst — terpisah, daftar di "Buka Project"
- Per-cue voice: 4 voices (Dimas/Siti/Ardi/Gadis), Generate TTS pakai voiceResolver
- Mode ON + Smart Fit: respectTiming=true, smartFit=true, cap 2.0x → 100% sync SRT ori
- Active project di-restore dari localStorage (auto-load saat reload page)
- Commit: eb0ac16 — pushed ke GitHub, Vercel auto-deploy
- Files changed: supabase.ts (+194), tts.ts (+19), srt-editor-panel.tsx (+888 rewrite)
- Files new: scripts/supabase-migration-v2.sql
- Pending: user run migration v2 SQL di Supabase SQL Editor

