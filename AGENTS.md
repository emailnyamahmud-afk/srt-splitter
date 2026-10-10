# AGENTS.md — SRT Splitter + Dubbing

> File ini dibaca AI otomatis di awal setiap session.
> Isinya: pre-session checklist + pointer ke rules + status pipeline terkini.

## Pre-session checklist (wajib, di awal chat pertama)

Saat user bilang **"baca AGENTS.md dan PROJECT_RULES.md"** (atau variasi: "mulai" / "baca dokumen" / chat pertama di session baru):

1. **Baca dokumen (wajib)** — baca full file ini, lalu:
   - `PROJECT_RULES.md` — **27 rules** project-specific (R-01 sampai R-27)
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

1. **`PROJECT_RULES.md`** — **27 rules** project-specific. Baca full sebelum kerja apapun.
   - R-01 sampai R-15: workflow, docs, marker, kode
   - R-16: ejaan Jawa (é/è/ê, schwa polos)
   - R-17: skema field (krama_inggil masuk krama)
   - R-18: JANGAN HAPUS entry kamus (berlaku juga untuk FIELD — R-23)
   - R-19: parser AI tolol, audit suspect otomatis
   - R-20: kamus-draft.json = rujukan tunggal, raw = arsip
   - R-21: field 'word' = netral, belum terdefinisi
   - R-22: GIGO — AI tidak merujuk raw untuk audit/fix, bantu workflow saja
   - R-23: Standarisasi ≠ HAPUS field. R-18 berlaku untuk FIELD juga.
   - R-24: Statistik "arti 100% filled" MENIPU. Audit real Indonesia.
   - R-25: detect_duplicates WAJIB tampilkan word NETRAL.
   - R-26: register + krama_inggil DROPPED PERMANEN. Bukan hapus data, hapus kolom tolol.
   - R-27: Kerja bertahap per source. Filter subset PURE, jangan campur sampah merge AI.
2. **`README.md`** (root) — workflow 4 fase, 2 mode dubbing, status pipeline.
3. **`scripts/README.md`** — detail per Python script.
4. **`worklog.md`** — baca entry terakhir (Task ID + Stage Summary).

Kalau ada konflik antara dokumen, `PROJECT_RULES.md` menang.

## Status pipeline (10 Okt 2026)

```
✅ Fase 1: yt-dlp        → mp4-ori.mp4 + audio.wav (terpisah)
✅ Fase 2: Demucs        → no_vocals.mp3 (MP3 320 kbps, MPS acceleration)
⏳ Fase 3a: TTS ID       → audio-id-dub.wav (web Mode ON, jalan)
⏳ Fase 3b: TTS Jawa     → audio-jw-dub.wav (SRT editor, nunggu code fix)
⏳ Fase 4: mix-tui       → mp4-{lang}-final.mp4 (nunggu dub ready)
```

## Kamus Jawa status (v4.1, 10 Okt 2026 — 3 source integrated: jv_wiktionary + mendeley + id_wiktionary)

```
Total entries:           45.638 (20 field per entry, semua identik)
Version:                 v4.1 (definisi indo → keterangan, indo = terjemahan saja)
Size:                    34.25 MB

3 source integrated (NO kamus draft sampah):
  ✅ jv.wiktionary XML dump (parsed minimal) — 44.615 base
  ✅ mendeley curated academic — 145 (44 merged, 101 new)
  ✅ id.wiktionary XML dump (section Jawa) — 2.303 (1.363 merged, 940 new)

Source belum integrasi (phase berikutnya — sampah merge AI, perlu parse XML resmi):
  🔜 dasanama — ~427 entries (kamus draft, sampah)
  🔜 lampiran — ~2.151 entries (kamus draft, sampah)
  🔜 angka — ~1.008 entries (kamus draft, sampah)
  🔜 lemma — ~644 entries (kamus draft, sampah)

Field terisi:
  word:       45.518 (99.7%) — lemma Jawa (NETRAL unassigned)
  ngoko:         144 (0.3%) — dari mendeley
  krama:       1.530 (3.4%) — dari jv_wiktionary {{ngoko|...}} + mendeley + id_wiktionary
  indo:        1.963 (4.3%) — terjemahan Indonesia (mendeley + id_wiktionary)
  keterangan: 45.542 (99.8%) — definisi Jawa (jv) + definisi ID (id_wiktionary) preserve
  aksara:     44.585 (97.7%) — dari jv_wiktionary {{sirah|alt=...}}
  kelas:          55 (0.1%) — kelas kata linguistik (t.a., t.k., t.s.)

Komposisi kelengkapan:
  NETRAL (word, ngoko+krama kosong): 44.087 (96.6%)
  PAIRED 3-field (ngoko+krama+indo):    141 (0.3%) — siap upload Supabase
  indo only (no ngoko+krama):         1.622 (3.6%) — dari id_wiktionary

Source breakdown:
  jv only (XML dump):           43.256
  jv + id_wiktionary:            2.238
  jv + mendeley:                  137
  jv + mendeley + id_wiktionary:     7

Multi-source (source_count > 1): 1.363
Status: semua draft (user belum mark ready, R-12)
Ejaan (diakritik é/è/ê): 9.785 (21.4%)
Schema: 20 field, no register + no krama_inggil (R-26), arti → indo (rename)

TUI: kamus-tui.py v10 — compatible dengan field indo (bukan arti)
Upload: upload-supabase.py v3 — compatible dengan field indo (R-26)
DB Supabase: 10 kolom (post-R-26, DROP register + krama_inggil)
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
13. **JANGAN hapus field tanpa konfirmasi user (R-23).** Standarisasi ≠ hapus. R-18 berlaku untuk FIELD juga.
14. **Audit dulu sebelum klaim "100% filled" (R-24).** Cek isi, bukan cuma count.
15. **detect_duplicates WAJIB tampilkan word NETRAL (R-25).** Tanpa word, user tidak bisa putuskan merge.
16. **register + krama_inggil DROPPED PERMANEN (R-26).** register 100% 'umum' (label raw tolol), krama_inggil kosong by R-17. Bukan hapus data, hapus kolom tolol.
17. **Kerja bertahap per source (R-27).** Filter subset PURE per sumber, user kurasi 1-1 manual via TUI, jangan campur sampah merge AI.

## Yang sedang nunggu

- `audio-id-dub.wav` dari web app Mode ON (Fase 3a)
- Code fix SRT editor Jawa: default voice Dimas otomatis untuk semua cue (Fase 3b)
- Kamus Jawa Supabase progressif (50 entries/minggu, target 10.000 entries 3-pasangan terverifikasi)
- User validasi entries NETRAL (39.230) via TUI → isi ngoko/krama → status='ready' → upload Supabase
- User bersihkan duplikat via TUI menu 'Deteksi Duplikat' (JANGAN HAPUS otomatis, R-18)
- AI bantu workflow: statistik, scan pattern, compare draft vs DB (read-only). AI TIDAK upload.

## Phase kerja bertahap kamus (R-27, 10 Okt 2026)

| Phase | Source | Status |
|-------|--------|--------|
| 1 (NOW) | Mendeley PURE (145 entries) — `kamus_mendeley.json` | 🔄 User kurasi via TUI |
| 2 | Pure lemma — bikin `kamus_lemma_pure.json` | 🔜 Setelah phase 1 selesai |
| 3 | Pure lampiran — bikin `kamus_lampiran_pure.json` | 🔜 Setelah phase 2 selesai |
| 4 | Pure dasanama — bikin `kamus_dasanama_pure.json` | 🔜 Setelah phase 3 selesai |
| 5 | Pure angka — bikin `kamus_angka_pure.json` | 🔜 Setelah phase 4 selesai |
| 6 | Pure wiktionary ngoko | 🔜 Setelah phase 5 selesai |
| 7 | Pure wiktionary krama | 🔜 Setelah phase 6 selesai |
| Akhir | Merge manual hasil semua phase ke kamus draft | Setelah semua phase selesai |
