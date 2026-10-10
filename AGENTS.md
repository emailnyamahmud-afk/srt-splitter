# AGENTS.md — SRT Splitter + Dubbing

> File ini dibaca AI otomatis di awal setiap session.
> Isinya: pre-session checklist + pointer ke rules + status pipeline terkini.

## Pre-session checklist (wajib, di awal chat pertama)

Saat user bilang **"baca AGENTS.md dan PROJECT_RULES.md"** (atau variasi: "mulai" / "baca dokumen" / chat pertama di session baru):

1. **Baca dokumen (wajib)** — baca full file ini, lalu:
   - `PROJECT_RULES.md` — **26 rules** project-specific (R-01 sampai R-26)
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

1. **`PROJECT_RULES.md`** — **26 rules** project-specific. Baca full sebelum kerja apapun.
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

## Kamus Jawa status (v2.7, 10 Okt 2026 — post-R-26 drop register + krama_inggil)

```
Total entries:           44.005 (20 field per entry, semua identik — drop register + krama_inggil)
✅ PAIRED 3-field:        2.937  (6.67%)  ← ngoko+krama+arti lengkap
🟡 NGOKO+ARTI:           1.766  (4.01%)  ← perlu krama
⚠ NETRAL (word+arti):   39.230  (89.15%) ← arti=word (fallback), user tentukan ngoko/krama

Analisa arti (CRITICAL — statistik 'arti 100% filled' MENIPU, R-24):
  arti total terisi:        44.002 (99.99%)
  arti = word (fallback):  39.231 (89.15%) — BUKAN Indonesia, cuma copy word
  arti Indonesia real:     4.771 (10.84%) — paired + ngoko+arti (valid)
  → User verifikasi 1-1 via TUI. Fallback = alat marking NETRAL.

Field terisi (20 field per entry, R-26 drop register + krama_inggil):
  word:        39.231 (89.15%) — NETRAL unassigned
  ngoko:        4.704 (10.69%)
  krama:        3.006 (6.83%)
  arti:        44.002 (99.99%) — lihat analisa di atas
  aksara:      41.350 (93.97%)
  keterangan:  42.924 (97.54%)
  register:    DROPPED (R-26: 100% 'umum' tidak informatif)
  krama_inggil: DROPPED (R-17: 0 entries terisi, sudah masuk krama)
  kelas:         1.404 (3.20%) — kelas kata linguistik (t.a., t.k., t.s., dll)

Source flags:
  is_lemma:    1.816 (4.13%)  is_mendeley:   814 (1.85%)
  is_dasanama:   427 (0.97%)  is_angka:    1.008 (2.29%)
  is_lampiran: 2.151 (4.89%)

Duplikat (audit global 10 Okt 2026 — 3.275 tokens):
  Same-field (877):
    ngoko:  211   krama:  192   word:  61   arti:  413
  Cross-field (2.398):
    ngoko↔krama: 140   ngoko↔arti: 730   krama↔arti: 277
    word↔ngoko:  581   word↔krama: 258   word↔arti: 412
  → user bersihkan via TUI menu 'Deteksi Duplikat' (JANGAN HAPUS otomatis, R-18)

Wiki markup cleaning (10 Okt 2026):
  - 1.918 entries dibersihkan (960 wiki link, 628 template, 18 HTML, 311 whitespace)
  - 0 data hilang (R-18 compliance)
  - Hapus: [[...]] bracket, {{...}} template, <sup>/<br> tag
  - Preserve: link text, teks data, aksara, diakritik Jawa

DB Supabase (post-R-26 standardisasi):
  Table `kamus` (10 kolom):
    id (uuid, auto-gen), ngoko, aksara, krama, arti, keterangan,
    sumber, status, created_at, updated_at
  → register + krama_inggil DROPPED dari DB (R-26)
  → user run SQL DROP COLUMN untuk standardisasi DB

Build script: DISABLED (R-20) — parser tolol merusak data
Audit script: scripts/audit-statistik-duplikat.py (jalan kapan saja, read-only)
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

## Yang sedang nunggu

- `audio-id-dub.wav` dari web app Mode ON (Fase 3a)
- Code fix SRT editor Jawa: default voice Dimas otomatis untuk semua cue (Fase 3b)
- Kamus Jawa Supabase progressif (50 entries/minggu, target 10.000 entries 3-pasangan terverifikasi)
- User validasi entries NETRAL (39.230) via TUI → isi ngoko/krama → status='ready' → upload Supabase
- User bersihkan duplikat via TUI menu 'Deteksi Duplikat' (JANGAN HAPUS otomatis, R-18)
- AI bantu workflow: statistik, scan pattern, compare draft vs DB (read-only). AI TIDAK upload.
