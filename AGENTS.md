# AGENTS.md — SRT Splitter + Dubbing

> File ini dibaca AI otomatis di awal setiap session.
> Isinya: pointer ke rules + status pipeline terkini.

## Baca dulu (wajib, tiap session)

1. **`PROJECT_RULES.md`** — 12 rules project-specific. Baca full sebelum kerja apapun.
2. **`README.md`** (root) — workflow 4 fase, 2 mode dubbing, status pipeline.
3. **`scripts/README.md`** — detail per Python script.

Kalau ada konflik antara dokumen, `PROJECT_RULES.md` menang.

## Status pipeline (8 Okt 2026)

```
✅ Fase 1: yt-dlp        → S3-ori.mp4 + S3-ori-audio.opus
✅ Fase 2: Demucs        → no_vocals.mp3 (293 MB, clean MP3 320)
⏳ Fase 3a: TTS ID       → audio-id-dub.wav (web Mode ON, jalan)
⏳ Fase 3b: TTS Jawa     → audio-jw-dub.wav (SRT editor, nunggu code fix)
⏳ Fase 4: mix-tui       → mp4-id-final.mp4 (nunggu dub ready)
```

## Marker status (konsisten di semua docs)

| Marker | Arti |
|---|---|
| ✅ | Sudah jalan, siap pakai |
| ⏳ | Nunggu sesuatu (dependency / user input) |
| ⚠️ | Deprecated / backup / ada masalah |
| ❌ | Gagal / blocker |
| 🔧 | Maintainer-only |

## Cara kerja kita

- User: Macbook lokal (bukan coder), interaksi via chat Z.ai
- AI: di sandbox Z.ai, akses file via tools
- Komunikasi: dokumentasi (README, scripts/README, PROJECT_RULES)
- Repo: GitHub `emailnyamahmud-afk/srt-splitter` → auto-deploy Vercel
- DB: Supabase (project + cues + kamus)
- Web app: https://srt-splitter.vercel.app/

## Aturan emas

1. **Baca docs dulu sebelum jawab.** User akan tanya "baca dokumentasi, cek sync" — jangan lupa.
2. **Update docs tiap workflow berubah.** Kalau gak update, next session akan lupa.
3. **Tanya kalau ragu, jangan asumsi.** User bukan coder, jawaban teknis perlu dikonfirmasi.
4. **Jangan eksekusi kalau diminta jangan.** User sering bilang "jangan eksekusi, edit code saja".
5. **Path file: wajib di `/home/z/my-project/`** untuk script, `/home/z/my-project/download/` untuk deliverable.

## Yang sedang nunggu

- `audio-id-dub.wav` dari web app Mode ON (Fase 3a)
- Code fix SRT editor Jawa: default voice Dimas otomatis untuk semua cue (Fase 3b)
- Kamus Jawa Supabase progressif (50 entries/minggu, target 2.000)
