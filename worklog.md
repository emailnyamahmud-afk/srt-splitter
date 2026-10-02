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
