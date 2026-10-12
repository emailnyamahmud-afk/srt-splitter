# AGENTS.md — SRT Splitter + Dubbing

> File ini dibaca AI otomatis di awal setiap session.
> Isinya: pre-session checklist + pointer ke rules + status pipeline terkini.

## Pre-session checklist (wajib, di awal chat pertama)

Saat user bilang **"baca AGENTS.md dan PROJECT_RULES.md"** (atau variasi: "mulai" / "baca dokumen" / chat pertama di session baru):

1. **Baca dokumen (wajib)** — baca full file ini, lalu:
   - `PROJECT_RULES.md` — **29 rules** project-specific (R-01 sampai R-29)
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

1. **`PROJECT_RULES.md`** — **29 rules** project-specific. Baca full sebelum kerja apapun.
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
   - R-28: Merge integrasi: KATA IDENTIK = merge jadi 1 entry. BEDA KATA = sinonim comma. DILARANG biarkan duplikat.
   - R-29: Duplikat = kata IDENTIK lintas entry. Bukan sinonim, bukan token sama di field beda.
2. **`README.md`** (root) — workflow 4 fase, 2 mode dubbing, status pipeline.
3. **`scripts/README.md`** — detail per Python script.
4. **`worklog.md`** — baca entry terakhir (Task ID + Stage Summary).

Kalau ada konflik antara dokumen, `PROJECT_RULES.md` menang.

## Status pipeline (12 Okt 2026, 23:45 WIB)

```
✅ Fase 1: yt-dlp v5     → S5-ori.mp4 (80 MB) + S5-ori-audio.m4a (126 MB) + S5-ori.id.srt (3866 cue, 2j 16m)
✅ Fase 2: Demucs        → no_vocals.mp3 (312 MB, MP3 320, 16m37s di M1 MPS)
✅ Fase 3a: edge-tts-tui.py (LOKAL — 100% sukses!)
   Hasil: S5-ori.id-audio-id-dub.wav (374.4 MB, WAV 24kHz mono 16-bit, 2j 16m 19s)
   Stat: 3865/3866 cue OK (99.97%), 1 gagal (Pass 1 error, no nomor cue di log)
   Cache: 7304 MP3 (100.5 MB) di ~/Dubbing/.cache/ — disimpan untuk resume + DaVinci manual
   Config: voice Ardi -10Hz, Smart Fit cap 2.0x, prefix S5-ori.id
   Waktu: ~3 jam (rate stabil 20 cue/menit, M1 16GB tidak panas)
⏳ Fase 3b: TTS Jawa     → audio-jw-dub.wav (web app SRT editor, nunggu code fix)
✅ Fase 4: mix-tui.py v3 (SELESAI — 2 mode tested)
   Mode A: Stream copy (3m 10s, 275 MB, no SRT)
     Output: S5-id-final.mp4
     Video stream copy (no re-encode) → 100% sync
   Mode B: Burn SRT Indonesia TOP (3m 53s, 2.1 GB, h264_videotoolbox M1)
     Output: S5-id-final-sub.mp4
     Speed: 35x real-time (M1 VideoToolbox hardware, tidak panas)
     SRT: font 18pt putih outline hitam, Alignment=8 top
   Status: user preview di VLC
```

### Catatan Fase 3a (edge-tts-tui.py lokal — S5 SELESAI)
- Web app Vercel Mode ON gagal 4x untuk S5 (SRT 2 jam, 3866 cue):
  1. Vercel maxDuration 60s → request >60s killed
  2. Microsoft Edge TTS rate-limit (429) setelah ribuan request cepat
  3. Smart Fit = 2x request per cue → 3866 × 2 = 7732 request ke Vercel
  4. ZIP building OOM (baseline 200 MB dari Supabase kamus + 700 MB ZIP peak)
- Solution: pindah generate TTS ke lokal Mac pakai edge-tts Python
  - WebSocket langsung ke Microsoft (no Vercel proxy)
  - No rate-limit (per-IP, tidak per-function seperti Vercel)
  - RAM ~750 MB untuk 5000 cue (pre-allocate buffer + inline mix)
  - Per-cue cache → resume kalau crash
- Hasil: 3865/3866 OK (99.97%) dalam ~3 jam, no Vercel limit
- Cache disimpan (No "Hapus cache?") untuk:
  - Resume kalau perlu regen
  - Mode manual DaVinci: drag MP3 per cue (nomor SRT) ke timeline

### Strategi 4-mode dubbing (user catatan 12 Okt 2026)

```
Mode 1: Manual DaVinci
  - Cache per-cue MP3 (nomor SRT) drag manual ke timeline
  - Pilih gender per cue (Ardi/Gadis) sesuai karakter dialog
  - Edit fine-tune: SFX level per scene, crossfade, ducking manual

Mode 2: TUI Gender Tag (NEXT — belum implementasi)
  - TUI baru: srt-gender-tui.py
  - Baca SRT → tag L/P per cue → save sidecar JSON
  - edge-tts-tui.py baca sidecar → voice Ardi/Gadis per cue
  - 1x generate = campuran gender otomatis

Mode 3: Cepat (DEFAULT — sudah jalan)
  - Default voice Ardi semua cue
  - mix-tui.py → output final ~2 menit
  - Tanpa DaVinci, langsung publish

Mode 4: Edit SRT Jawa (LONG-TERM — web app)
  - Web app SRT editor (per cue preview, multi-project)
  - Tag gender + bahasa Jawa (ngoko/krama)
  - Nunggu kamus clean (40k+ entries di JSON, Supabase grow 50/minggu)
```

### Status implementasi 4 mode

| Mode | Status | Tool |
|------|--------|------|
| 1 (Manual DaVinci) | ✅ Bisa sekarang | Cache MP3 per cue + DaVinci |
| 2 (Gender Tag TUI) | ⏳ TODO — spesifikasi draft | srt-gender-tui.py (belum ada) |
| 3 (Cepat) | ✅ Jalan (S5 test) | edge-tui.py + mix-tui.py v2.1 |
| 4 (Web Jawa) | ⏳ Nunggu code fix | srt-splitter.vercel.app (SRT editor) |

### Audit mix-tui.py v2.1 (commit 152bd82)
9 bug di-fix (8 bug awal + 1 bug tersembunyi deadlock):
1. Default output otomatis dari prefix MP4 (S5-ori.mp4 → S5-ori-id-final.mp4)
2. Header doc update: Fase 1 m4a native (bukan audio.wav), Fase 3a edge-tts-tui (bukan web app)
3. Validasi input file exist + size > 0 sebelum eksekusi
4. Warning prominent kalau dub dur < 90% MP4 dur
5. Pesan akhir 4 opsi (preview/edit/upload/split)
6. Progress bar FFmpeg real-time (%, time, size, speed, ETA)
7. Hapus output partial kalau Ctrl+C (no corrupt file)
8. Dependencies check + ffmpeg/ffprobe dengan pesan install jelas
9. Threading stderr reader — hindari deadlock kalau FFmpeg output > 64KB pipe buffer


## Kamus Jawa status (v5.3, 10 Okt 2026 — 3 source + merge sinonim jadi 1 entry)

```
Total entries:           43.630 (20 field per entry, semua identik)
Version:                 v5.3 (merge sinonim jadi 1 entry, standardisasi sumber + ejaan)
Size:                    25.5 MB
Duplikat:                1 (minor, user verifikasi manual)

3 source integrated (NO kamus draft sampah):
  ✅ jv.wiktionary XML dump (parsed minimal) — 44.615 base
  ✅ mendeley curated academic — 145 (44 merged, 101 new)
  ✅ id.wiktionary XML dump (section Jawa) — 2.303 (1.363 merged, 940 new)

Merge sinonim jadi 1 entry (R-28):
  1.502 clusters, 1.898 entries di-merge
  1.514 entries dengan word comma (sinonim)
  word + keterangan = alat bantu untuk user isi indo/ngoko/krama

Source belum integrasi (phase berikutnya — sampah merge AI, perlu parse XML resmi):
  🔜 dasanama — ~427 entries (kamus draft, sampah)
  🔜 lampiran — ~2.151 entries (kamus draft, sampah)
  🔜 angka — ~1.008 entries (kamus draft, sampah)
  🔜 lemma — ~644 entries (kamus draft, sampah)

Field terisi:
  word:       43.533 (99.8%) — lemma Jawa + sinonim comma (alat bantu)
  ngoko:       1.396 (3.2%) — dari jv_wiktionary + mendeley
  krama:       1.396 (3.2%) — dari jv_wiktionary + mendeley
  indo:        1.468 (3.4%) — terjemahan Indonesia (mendeley + id_wiktionary)
  keterangan: 43.475 (99.6%) — definisi Jawa + Indonesia (alat bantu)
  aksara:     42.904 (98.3%) — dari jv_wiktionary
  kelas:          46 (0.1%) — kelas kata linguistik

Komposisi kelengkapan:
  NETRAL (word, ngoko+krama kosong): 42.213 (96.8%)
  PAIRED 3-field:                      323 (0.7%) — siap upload Supabase
  ngoko+krama (no indo):             1.073 (2.5%)
  indo only (no ngoko+krama):        1.145 (2.6%)

Source breakdown:
  jv only (XML dump):           41.564
  jv + id_wiktionary:            1.924
  jv + mendeley:                  131
  jv + id_wiktionary + mendeley:    11

Multi-source (source_count ≥ 2): 2.342
Status: semua draft (user belum mark ready, R-12)
Schema: 20 field, no register + no krama_inggil (R-26), arti → indo (rename)
Sumber baku: jv.wiktionary.org (XML dump) + id.wiktionary.org (XML dump) + mendeley.com (curated)
Ejaan: mendeley distandardisasi ke jv.wiktionary baku (28 tokens)

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
18. **Merge integrasi: KATA IDENTIK = merge jadi 1 entry (R-28).** BEDA KATA = sinonim comma. DILARANG biarkan kata identik di 2+ entries (itu = duplikat).
19. **Duplikat = kata IDENTIK lintas entry (R-29).** Bukan sinonim, bukan token sama di field beda. Kalau dalam 1 entry beda kata = itu sinonim.

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
