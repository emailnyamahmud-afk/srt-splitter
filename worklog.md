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

