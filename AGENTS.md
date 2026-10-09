# AGENTS.md — SRT Splitter + Dubbing

> File ini dibaca AI otomatis di awal setiap session.
> Isinya: pre-session checklist + pointer ke rules + status pipeline terkini.

## Pre-session checklist (wajib, di awal chat pertama)

Saat user bilang **"baca AGENTS.md dan PROJECT_RULES.md"** (atau variasi: "mulai" / "baca dokumen" / chat pertama di session baru):

1. **Baca dokumen (wajib)** — baca full file ini, lalu:
   - `PROJECT_RULES.md` — **21 rules** project-specific (R-01 sampai R-21)
   - `README.md` (root) — workflow 4 fase + status
   - `scripts/README.md` — detail per script (kalau kerja Python)
   - `worklog.md` — baca entry terakhir untuk konteks task sebelumnya

2. **Cek git sync (wajib)**:
   ```bash
   git fetch origin
   git status -sb
   ```
   - `## main` (no diff) → up-to-date, lanjut
   - `## main...origin/main [behind N]` → `git pull origin main`, lanjut
   - `## main...origin/main [ahead N]` → tanya user "push N commit?", jangan auto-push
   - `## main...origin/main [diverged]` → tanya user, jangan auto-resolve

3. **Lapor status pipeline** ke user (1 tabel, pakai marker konsisten).

Setelah checklist selesai, AI siap kerja. Tidak perlu ulang di chat berikutnya di session yang sama.

## Baca dulu (wajib, tiap session)

1. **`PROJECT_RULES.md`** — **22 rules** project-specific. Baca full sebelum kerja apapun.
   - R-01 sampai R-15: workflow, docs, marker, kode
   - R-16: ejaan Jawa (é/è/ê, schwa polos)
   - R-17: skema field (krama_inggil masuk krama)
   - R-18: JANGAN HAPUS entry kamus
   - R-19: parser AI tolol, audit suspect otomatis
   - R-20: kamus-draft.json = rujukan tunggal, raw = arsip
   - R-21: field 'word' = netral, belum terdefinisi
   - R-22: GIGO — AI tidak merujuk raw untuk audit/fix, bantu workflow saja
2. **`README.md`** (root) — workflow 4 fase, 2 mode dubbing, status pipeline.
3. **`scripts/README.md`** — detail per Python script.
4. **`worklog.md`** — baca entry terakhir (Task ID + Stage Summary).

Kalau ada konflik antara dokumen, `PROJECT_RULES.md` menang.

## Status pipeline (9 Okt 2026)

```
✅ Fase 1: yt-dlp        → mp4-ori.mp4 + audio.wav (terpisah)
✅ Fase 2: Demucs        → no_vocals.mp3 (MP3 320 kbps, MPS acceleration)
⏳ Fase 3a: TTS ID       → audio-id-dub.wav (web Mode ON, jalan)
⏳ Fase 3b: TTS Jawa     → audio-jw-dub.wav (SRT editor, nunggu code fix)
⏳ Fase 4: mix-tui       → mp4-{lang}-final.mp4 (nunggu dub ready)
```

## Kamus Jawa status (v2.3, 9 Okt 2026)

```
Total entries:           45.021
✅ PAIRED (terdefinisi):    5.803  (12.9%)  ← ngoko+krama/arti atau krama+arti
⚠ NETRAL (word-only):    39.216  (87.1%)  ← R-21: belum terdefinisi, user validasi manual
✅ Empty (R-18 tetap):        2  (0.0%)

Angka 1-1000: 100% 3-pasangan terdefinisi (contoh sederhana untuk AI belajar)
Krama terisi: 3.493 (7.76%) — dari Mendeley (krama+kramainggil), Wiktionary, Lampiran
Audit suspect: 124 entries (R-19) — user validasi ulang 1-1
Build script: DISABLED (R-20) — parser tolol merusak data
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
- Komunikasi: dokumentasi (README, scripts/README, PROJECT_RULES, worklog)
- Repo: GitHub `emailnyamahmud-afk/srt-splitter` → auto-deploy Vercel
- DB: Supabase (project + cues + kamus)
- Web app: https://srt-splitter.vercel.app/

## Aturan emas

1. **Baca docs dulu sebelum jawab.** User akan tanya "baca dokumentasi, cek sync" — jangan lupa.
2. **Update docs tiap workflow berubah.** Kalau gak update, next session akan lupa.
3. **Tanya kalau ragu, jangan asumsi.** User bukan coder, jawaban teknis perlu dikonfirmasi.
4. **Jangan eksekusi kalau diminta jangan.** User sering bilang "jangan eksekusi, edit code saja".
5. **Path file: wajib di `/home/z/my-project/`** untuk script, `/home/z/my-project/download/` untuk deliverable.
6. **Git sync tiap session start.** Pull kalau behind, tanya kalau ahead, jangan auto-push.
7. **JANGAN HAPUS entry kamus (R-18).** Data ada, lengkap atau tidak, valid atau tidak.
8. **JANGAN rebuild dari raw (R-20).** kamus-draft.json = rujukan tunggal, raw = arsip.
9. **JANGAN auto-fix data (R-18).** Bikin audit script + user validasi 1-1 via TUI.
10. **JANGAN merujuk raw untuk audit/fix (R-22).** GIGO — raw = sampah parsing tolol AI.
11. **JANGAN upload ke DB tanpa konfirmasi user (R-12).** Hanya user 'y' eksplisit.
12. **JANGAN ngeyel dengan pengetahuan Jawa AI.** Otak AI = dilatih sampah internet.

## Yang sedang nunggu

- `audio-id-dub.wav` dari web app Mode ON (Fase 3a)
- Code fix SRT editor Jawa: default voice Dimas otomatis untuk semua cue (Fase 3b)
- Kamus Jawa Supabase progressif (50 entries/minggu, target 10.000 entries 3-pasangan terverifikasi dalam 1-6 bulan)
- User validasi entries NETRAL (39.216) via TUI → status 'ready' → upload Supabase
- AI bantu workflow: statistik, scan pattern, compare draft vs DB (read-only). AI TIDAK upload.
