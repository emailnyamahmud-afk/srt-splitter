# Progress Log — SRT Splitter + Dubbing Project

Dokumen ini catatan status project untuk AI / developer next time baca. Update setiap sesi kerja.

**Last updated:** 9 Oktober 2026, 17:00 WIB

---

## 📌 Quick Status

| Item | Status |
|---|---|
| **Web app Editor SRT Jawa (project-based + auto-save Supabase)** | ✅ Production ready |
| **Per-cue Preview + browser cache (IndexedDB)** | ✅ Deployed |
| **Bidirectional alias lookup (word + ngoko + krama + krama_inggil + arti)** | ✅ Deployed |
| **Auto-strip aksen Jawa di TTS (SRT final tetap utuh)** | ✅ Deployed |
| **UI panel "Top 100 Unknown Words" + badge per cue** | ✅ Deployed (8 Okt 2026) |
| **Kamus schema v6.1 (R-21: field 'word' netral + R-17: krama_inggil masuk krama)** | ✅ Code ready |
| **Kamus JSON 45.021 entries (5.803 paired + 39.216 NETRAL)** | ✅ User bisa download |
| **kamus-tui.py v2.3 (Phase 1-6 refactor + R-21 filter NETRAL)** | ✅ User bisa pakai |
| **upload-supabase.py (Phase 5, file terpisah)** | ✅ User bisa pakai |
| **audit-otomatis-suspect-patterns.py (R-19, 124 suspect)** | ✅ User bisa pakai |
| **Web app kamus READ-ONLY (jangan rusak kamus dari UI)** | ✅ Audited |
| **Mode ON + Smart Fit (video = ground truth)** | ✅ User rating 9/10 (cap 2.0x, pitch -15Hz laki) |
| **Python `demucs-tui.py` + `mix-tui.py`** | ✅ Working (MILESTONE Test #25, 10000% sync) |
| Pitch control (Edge TTS -10Hz laki, +10Hz perempuan) | ✅ Working, user pakai -15Hz |
| User run migration v2+v3 SQL di Supabase | ✅ Done (8 Okt 2026) |
| User upload 2 entries ke Supabase (test awal) | ✅ Done (8 Okt 2026) |
| User validasi entries NETRAL (39.216) via TUI | 🔄 In progress (R-21) |
| User validasi audit-suspects (124 entries) | 🔄 In progress (R-19) |
| Test full season S7-id (2.5 jam) | ⏳ Pending user |
| Workflow multi-bahasa (Jawa/Sunda/dll) | 🔜 Next step |

---

## 🎉 MILESTONE: Kamus Netral + R-21 + Repo Cleanup (9 Okt 2026)

### Commits terbaru (urut kronologis)

| Commit | Deskripsi |
|---|---|
| `5ded8ca` | R-16: fix ejaan angka (eka→éka, Nol→nol, songo dari ngoko→hapus) |
| `dd51227` | R-18: JANGAN HAPUS entry kamus (kosong/aksara/keterangan-only tetap disimpan) |
| `996a5c6` | R-19: audit otomatis 205 suspect entries (parser AI tolol detector) |
| `d79f22f` | R-20/R-21: netralisasi kamus-draft.json — 39.216 entries jadi 'word' netral |
| `866e010` | Repo cleanup: hapus 10 file besar (~14.5 MiB) dari GitHub |
| `a3cfb19` | TUI Phase 1: extract `_search_entries()` helper (4 lokasi duplikasi → 1 helper) |
| `d9dce1c` | TUI Phase 2: pakai `_entry_label()` di browse_list (R-21 word tampil) |
| `33689b6` | TUI Phase 3: tambah filter NETRAL di main_menu + browse_by_kelengkapan |
| `f1ec792` | TUI Phase 4: extract `merge_2_entries()` jadi fungsi terpisah (187 → 3 baris di main_menu) |
| `da155f5` | TUI Phase 5: pisah `upload-supabase.py` jadi file terpisah (170 baris) |
| `aff4666` | TUI Phase 6: polish `textwrap.wrap()` + main() read-only (no auto-save) |
| `8adcc16` | Update README + AGENTS.md + scripts/README.md dengan R-21 status |

### Yang sudah jadi (9 Okt 2026)

1. **R-16 — Ejaan Jawa (é/è/ê)**:
   - Audit 1009 entries angka-raw.json, fix 3 masalah
   - Sanskrit `eka` → `éka` (close-mid /e/)
   - `Nol` kapital → `nol` lowercase
   - `songo` di ngoko padahal = KRAMA → hapus
   - Schwa polos `e` (telu, enem, sepuluh) TETAP polos (modern Jawa TIDAK menandai schwa)
   - `séket` (50), `sèlawé` (25), `séwu` (1000), `limangéwu` (5000) — baku

2. **R-17 — krama_inggil masuk krama**:
   - Audit 955 Mendeley entries: 100% kramainggil SUDAH ter-merge ke krama di draft
   - Field `krama_inggil` di draft sengaja kosong BY DESIGN
   - Sample: `mangan` → krama=`nedha, dhahar` (kramainggil Dhahar masuk)
   - Skema final: ngoko + krama + arti (kramainggil sebagai sinonim di krama)

3. **R-18 — JANGAN HAPUS entry kamus**:
   - Filosofi user: data ada, lengkap atau tidak, valid atau tidak
   - JANGAN hapus entry meski kosong/aksara/keterangan-only
   - Aksi yang benar: fix (pindah ke keterangan, kosongkan arti artifact)
   - Pengecualian: duplikat persis (semua field identik)

4. **R-19 — Parser AI tolol detector**:
   - Audit 205 suspect entries dari 45.021 (post-neutralize: 124 entries)
   - Pattern: parsing_artifact_ngoko (Indonesia word nyangkut), parsing_artifact_arti,
     krama_inggil_no_tag (info), too_many_ngoko_synonyms, too_many_krama_synonyms
   - Script `audit-otomatis-suspect-patterns.py` (idempotent, TIDAK edit JSON)
   - Output: `audit-suspects.json` untuk user reference

5. **R-20 — kamus-draft.json = rujukan tunggal**:
   - `build-kamus-bersih.py` → `.DISABLED` + README besar "JANGAN RUN"
   - Raw files tetap ada sebagai ARSIP, BUKAN rujukan lagi
   - User fallback: kamus resmi Kemendikbud (https://kesakata.kemdikbud.go.id)

6. **R-21 — Field 'word' = netral**:
   - 39.216 entries ngoko-only/krama-only → pindah ke field 'word' (netral)
   - 5.803 paired (tetap di ngoko/krama/arti)
   - 2 empty (R-18 tetap disimpan)
   - Sample: angka 1-1000 = contoh 3-pasangan terdefinisi (AI belajar dari sini)
   - Workflow: edit entry → isi 2 dari 3 field (paired) → word otomatis kosong

7. **TUI Phase 1-6 refactor** (kamus-tui.py 1341 → 1282 baris):
   - Phase 1: `_search_entries()` helper (4 lokasi duplikasi → 1)
   - Phase 2: `_entry_label()` helper (R-21: word tampil di browse list)
   - Phase 3: filter NETRAL di main_menu + browse_by_kelengkapan
   - Phase 4: `merge_2_entries()` jadi fungsi terpisah (187 baris inline → fungsi)
   - Phase 5: `upload-supabase.py` jadi file terpisah (130 baris string → file 170 baris)
   - Phase 6: `textwrap.wrap()` + main() read-only (JANGAN auto-save)

8. **Repo cleanup** (GitHub size):
   - Hapus 10 file besar (~14.5 MiB): kamus-jawa-full.json 12M, screenshot, tool-results,
     upload/mendeley (duplikat), download/kamus-jawa-*, srt-splitter-source.zip
   - Update .gitignore: `/upload/*.png`, `/upload/mendeley/`, `*.zip`, `*.bak`
   - Tracked files: 149 → 139 (10 file besar dihapus dari git tracking)

### Filosofi yang dipelihara (9 Okt 2026)

1. **Jangan hapus data (R-18)** — data ada, lengkap atau tidak, valid atau tidak
2. **Jangan rebuild dari raw (R-20)** — kamus-draft.json = rujukan tunggal
3. **Jangan auto-fix data (R-19)** — bikin audit script + user validasi 1-1
4. **Netral > tebakan AI (R-21)** — entries belum berpasangan = field 'word', bukan asumsi ngoko
5. **Krama_inggil = sinonim krama (R-17)** — bukan field terpisah, masuk comma di krama
6. **Ejaan Jawa modern (R-16)** — é/è diakritik wajib, schwa polos `e` tanpa diakritik

---

## 📌 Quick Status

| Item | Status |
|---|---|
| **Web app Editor SRT Jawa (project-based + auto-save Supabase)** | ✅ Production ready |
| **Per-cue Preview + browser cache (IndexedDB)** | ✅ Deployed |
| **Bidirectional alias lookup (ngoko + krama + krama_inggil + arti)** | ✅ Deployed |
| **Auto-strip aksen Jawa di TTS (SRT final tetap utuh)** | ✅ Deployed |
| **UI panel "Top 100 Unknown Words" + badge per cue** | ✅ Deployed (8 Okt 2026) |
| **Kamus schema v5 (register tag + krama_inggil + arti alias)** | ✅ Code ready |
| **Kamus JSON 44.585 entries + 1.3MB .gz di GitHub** | ✅ User bisa download |
| **kamus-tui.py v2 (menu pre-built, .env support)** | ✅ User bisa pakai |
| **srt-frequency-analyzer.py (pakai Supabase sebagai ground truth)** | ✅ User bisa pakai |
| **Web app kamus READ-ONLY (jangan rusak kamus dari UI)** | ✅ Audited |
| **Mode ON + Smart Fit (video = ground truth)** | ✅ User rating 9/10 (cap 2.0x, pitch -15Hz laki) |
| **Python `demucs-tui.py` + `mix-tui.py`** | ✅ Working (MILESTONE Test #25, 10000% sync) |
| Pitch control (Edge TTS -10Hz laki, +10Hz perempuan) | ✅ Working, user pakai -15Hz |
| Dubbing Mode v2.0 + retime-video.py | ⚠️ Deprecated (20x test gagal, backup) |
| User run migration v2+v3 SQL di Supabase | ✅ Done (8 Okt 2026) |
| User upload 2 entries ke Supabase (test awal) | ✅ Done (8 Okt 2026) |
| User isi kamus bertahap (target 2.000 entries dengan arti) | 🔄 In progress |
| Test full season S7-id (2.5 jam) | ⏳ Pending user |
| Workflow multi-bahasa (Jawa/Sunda/dll) | 🔜 Next step |

---

## 🎉 MILESTONE: UI Kamus Integration (8 Okt 2026 malam)

### Commits terbaru (urut kronologis)

| Commit | Deskripsi |
|---|---|
| `250308f` | Hapus kamus-jawa.json lama (21KB draft v4) — bikin bingung |
| `ef05e9c` | kamus-tui.py v2 — menu pre-built (arrow keys, no jq needed) |
| `15c29a4` | .env file di ~/Dubbing/ untuk Supabase credentials (sekali set, jalan terus) |
| `c0c413d` | Fix Supabase PGRST102 — semua row harus punya keys yang sama |
| `b0f78ff` | Upload HANYA yang user edit manual (arti diisi), bukan auto-fill template |
| `b467dd3` | Upload HANYA entries ngoko+krama+arti lengkap (3 field wajib) |
| `b7329b8` | Fix menu "☁ Upload" bolak-balik ke edit (substring match bug) |
| `d9abf10` | Web app Kamus Editor pakai kolom "ngoko" + "arti" (konsisten dengan upload) |
| `21eccee` | Frequency analyzer + audit web app (kamus read-only) |
| `72eb8d8` | Frequency analyzer pakai Supabase DB (ground of truth), bukan JSON lokal |
| `e0f6cce` | arti (Indonesia) jadi alias source lookup — saya/aku/gue/ane → nyong/kula |
| `755250f` | UI SRT Editor — panel Top 100 Unknown Words + badge per cue |

### Yang sudah jadi

1. **kamus-tui.py v2** — TUI editor kamus dengan menu pre-built:
   - 📊 Statistik kamus
   - 🔍 Search di semua field (ngoko/krama/krama_inggil/arti/keterangan)
   - 🚀 Browse SIAP UPLOAD (ngoko+krama+arti lengkap)
   - ⭐ Browse entries dengan krama mapping (auto-filled, butuh arti)
   - 📝 Browse BELUM ada arti (Indonesia)
   - 🎯 Browse per register (ngoko/krama/krama_inggil/kawi/umum)
   - 🔑 Set Supabase .env (URL + anon key, sekali set)
   - ☁ Upload ke Supabase (hanya yang SIAP UPLOAD)
   - 💾 Save JSON (manual)
   - ❌ Keluar

2. **.env file di ~/Dubbing/** — Supabase credentials:
   - User set sekali via TUI menu "🔑 Set Supabase .env"
   - Setiap update TUI, credentials tetap ada (gak perlu set ulang)

3. **Upload logic** — 3 field WAJIB: ngoko + krama + arti:
   - Hanya entries dengan 3 field terisi yang di-upload
   - krama_inggil OPSIONAL (tidak semua kata punya)
   - Yang auto-fill template tanpa arti → TIDAK di-upload

4. **Web app Kamus Viewer (READ-ONLY)** — supabase.ts:
   - Hapus fungsi `importKamus` + `updateKamusEntry` (write functions)
   - Sekarang cuma ada: `searchKamus` (read), `countKamus` (read)
   - Filosofi: editing kamus = TUI lokal → upload ke Supabase
   - Web app cuma baca + lookup alias
   - Edit langsung di DB Supabase (Table Editor) untuk validasi level 2

5. **srt-frequency-analyzer.py** — pakai Supabase DB sebagai ground of truth:
   - Fetch kamus dari Supabase REST API (bukan JSON lokal)
   - Output: top 100 kata tak dikenal + suggestion (base + suffix)
   - Save ke `~/Dubbing/srt-freq-report.txt`

6. **Bidirectional alias lookup dengan arti**:
   - `arti` (Indonesia) juga jadi source alias
   - Source SRT = "saya"/"aku"/"gue"/"ane" → convert ke ngoko utama atau krama utama
   - Test 9/9 PASS (saya → nyong/ngoko, saya → kula/krama, gue → nyong, dst.)

7. **UI panel "Top 100 Unknown Words"**:
   - Collapsible panel (amber accent) di Editor SRT Jawa
   - List top 100 kata tak dikenal + frequency (×N)
   - Klik kata → copy ke clipboard
   - Tombol "Copy all (N)" untuk copy semua sekaligus
   - Helper: "Paste di kamus-tui.py → search → add entry"
   - Badge per cue "N tak dikenal" (amber border + AlertCircle icon)
   - Auto-update saat jawaEntries atau kamus berubah

---

## 🎉 MILESTONE LAMA: Editor SRT Jawa Project-based (8 Okt 2026 siang)

### Yang sudah jadi di web app (commits 911fee0 → 755250f)

**1. Project-based workflow** (commit `eb0ac16`)
- "+ Project Baru" — upload 2 SRT (ID + Jawa), simpan ke Supabase
- "Buka Project" — list semua project dengan last_updated
- Multi-project: S1 (unfinished), S2 (unfinished), tutup S2, buka S1, lanjut kapan saja
- Auto-save 1.5s (debounced) per edit cue (text, voice, register)

**2. Per-cue Preview + IndexedDB cache** (commit `b30538c`)
- "▶ Preview" button di setiap cue → generate TTS 1 cue, play inline di browser
- Audio cache di IndexedDB (persistent antar reload, survive browser close)
- Cache validation: text + voiceId + pitch + smartFitCap sama → instant play (no API call)
- "Generate Full" → pakai cache kalau valid (hemat Edge TTS API call)
- Full audio tersimpan di IndexedDB → reload page → audio masih ada

**3. Bidirectional alias lookup** (commit `316c0df`)
- Source apapun (aku/inyong/kula/dalem) → convert ke ngoko atau krama utama
- Toggle Ngoko sekarang convert text (bukan cuma set status)
- All Ngoko (page/all) → convert krama/alias balik ke ngoko utama

**4. Auto-strip aksen TTS** (commit `521337d`)
- `normalizeTtsText()` di tts.ts — strip é/è/ê → e sebelum kirim ke Edge TTS
- SRT final tetap utuh (dengan aksen, sesuai kaidah)
- 5 titik entry.textLines.join() pakai normalizeTtsText
- Tombol "Hapus Aksén (SRT)" opsional untuk normalisasi SRT permanen

**5. Kamus schema v5** (commit `d6c228c`)
- Register tag Wiktionary ({{kn}}/{{kr}}/{{ki}}/{{ak}}) sekarang disimpan ke JSON
- Title di field yang benar: ngoko field untuk ngoko, krama field untuk krama, dst
- Tambah kolom krama_inggil + register
- Cross-reference auto-fill dari template {{krama|X}} / {{ngoko|X}}: 2.123 entries
- Parser: `scripts/parse-wiktionary-jv.py` v5 (343 lines)

**6. Kamus JSON di GitHub** (commit `4972137`)
- public/kamus-jawa-full.json (11MB, 44.585 entri) — TRACK di git (kemudian DIHAPUS R-20)
- public/kamus-jawa-full.json.gz (1.3MB compressed) — download cepat (kemudian DIHAPUS R-20)
- 86MB wiktionary XML → UNTRACK (user re-download dari Wiktionary kalau butuh)
- User di MacBook bisa download kamus dari GitHub, edit di VSCode, upload ke Supabase

**Update R-20 (9 Okt 2026)**: kamus-jawa-full.json + .gz DIHAPUS dari GitHub.
Alasan: parser tolol merusak data, kamus-draft.json = rujukan tunggal.
Raw files tetap sebagai ARSIP lokal AI sandbox, bukan rujukan.
User fallback: https://kesakata.kemdikbud.go.id (kamus resmi Kemendikbud).

---

## 🎉 MILESTONE LAMA: Workflow end-to-end SUKSES (Test #25, 6 Okt 2026 01:00 WIB)

**User feedback: "luar biasa, outputnya benar-benar mp4 profesional. SFX sangat bersih, audio Dub sangat bersih, 10000% Sync."**

### Workflow yang berhasil (3 fase):
```
Fase 0: demucs-tui.py → no_vocals.wav (SFX bersih, 61 detik MPS)
Fase 1: Web app mode ON + Smart Fit + pitch -15Hz → audio-id-dub.wav (9/10, 100% sync)
Fase 2: mix-audio-dub.py --sfx-wav → mp4-id-final.mp4 (7 detik, 0 DTS warnings)
```

---

## 🗄️ Supabase Schema (Migration v1 → v2 → v3)

### Migration v1 (initial)
- Tables: `srt_projects`, `srt_cues`, `kamus`
- RLS: allow_all (anonymous user ID)

### Migration v2 (commit `eb0ac16`) — ✅ User sudah run
- `srt_projects`: ADD `original_srt_id` TEXT (SRT Indonesia konteks)
- `srt_cues`: ADD `text_id` (Indonesia per cue) + `voice` (per-cue voice assignment)
- Triggers: auto-update `updated_at`
- SQL file: `scripts/supabase-migration-v2.sql`

### Migration v3 (commit `d6c228c`) — ✅ User sudah run
- `kamus`: ADD `krama_inggil` TEXT (kata krama inggil + alias)
- `kamus`: ADD `register` TEXT ('ngoko'|'krama'|'krama_inggil'|'kawi'|'umum')
- SQL file: `scripts/supabase-migration-v3.sql`

---

## 📚 Kamus Jawa — Format v5

### Schema
```json
{
  "ngoko": "sapa",
  "aksara": "ꦱꦥ",
  "krama": "sinten",
  "krama_inggil": "",
  "arti": "",
  "keterangan": "sinten; tembung pitakon...",
  "register": "umum",
  "sumber": "jv.wiktionary.org + xref"
}
```

### Stats (44.585 entri)
- ngoko: 22.464
- umum: 19.807 (default, belum ada tag Wiktionary)
- kawi: 2.217
- krama_inggil: 95
- krama: 2

### Auto-fill dari template
- Template `{{ngoko|X}}` / `{{krama|X}}` / `{{ki|X}}` di Wiktionary → cross-reference
- 2.123 entries dengan ngoko+krama mapping (auto-filled)
- 254 entries dengan krama_inggil mapping

### Files di GitHub
| File | Size | Status |
|---|---|---|
| `public/kamus-jawa-draft.json` | 17MB | TRACK di git (R-20: rujukan tunggal) |
| `public/angka-raw.json` | 172KB | TRACK di git (angka 1-1000, v6.1) |
| `public/dasanama-raw.csv` | 48KB | TRACK di git (sinonim Jawa) |
| `public/kamus-jawa-mendeley-raw.json` | 148KB | TRACK di git (Mendeley krama+kramainggil) |
| `public/lampiran-raw.json` | 436KB | TRACK di git (Lampiran Kamus Jawa-Indonesia) |
| `public/lampiran-angka-raw.json` | 8KB | TRACK di git (Lampiran Nama angka) |
| `public/kamus-jawa-new-lemma.json` | 208KB | TRACK di git (id.wiktionary jv:Lema) |
| `public/audit-suspects.json` | 88KB | TRACK di git (R-19 suspect entries) |
| ~~`public/kamus-jawa-full.json`~~ | 12MB | DIHAPUS R-20 (LEGACY raw, BUKAN rujukan) |
| ~~`public/kamus-jawa-full.json.gz`~~ | 1.5MB | DIHAPUS R-20 (LEGACY backup, BUKAN rujukan) |

### Filosofi kamus (R-20, 9 Okt 2026)
- **Supabase DB = ground of truth** (yang user upload, mulai dari 2 entries)
- **kamus-jawa-draft.json = satu-satunya rujukan lokal** (45.021 entries, v2.3)
- **Raw files (kamus-jawa-full.json, lampiran-raw.json, dll) = ARSIP**, BUKAN rujukan lagi
- **Build script DISABLED** — parser tolol merusak data (R-19), JANGAN rebuild dari raw
- **Web app + analyzer** pakai Supabase, bukan JSON lokal
- **Web app READ-ONLY** untuk kamus (TIDAK edit dari UI) — editing via TUI lokal
- **Validasi level 2** = user edit langsung di DB Supabase (Table Editor) kalau ada keanehan
- **User fallback**: https://kesakata.kemdikbud.go.id (kamus resmi Kemendikbud) untuk kata belum dikenali

### Workflow user (MacBook) — R-20
1. Download `public/kamus-jawa-draft.json` dari GitHub (17MB, R-20: rujukan tunggal)
2. Edit di `kamus-tui.py` (cari entry, isi ngoko/krama/arti — 2 dari 3 → paired)
3. Upload ke Supabase (menu ☁ Upload, hanya yang user_approved=True — R-12)
4. Web app load dari Supabase → bisa convert cue (Krama/Ngoko)

---

## 🛠️ Web App Architecture (8 Okt 2026)

### Komponen utama
```
src/components/srt-editor-panel.tsx     1231 lines (project-based Dual SRT Editor)
src/components/kamus-editor-panel.tsx   ~140 lines (READ-ONLY Kamus Viewer)
src/lib/audio-cache.ts                  274 lines (IndexedDB utility)
src/lib/rapikan-jawa.ts                  377 lines (kamus + bidirectional lookup + getTopUnknownWords)
src/lib/supabase.ts                     ~580 lines (CRUD + dual project functions, kamus read-only)
src/lib/tts.ts                          1628 lines (narrateSingleCue + stitchFullAudio + normalizeTtsText)
```

### Layout web app (8 Okt 2026)
```
Header (logo + title + 100% Sync badge)
Editor SRT Jawa (PRIMARY, border-2 indigo)
  - Empty state: + Project Baru + Buka Project + Recent projects
  - Active state: nama project + cue count + auto-save badge
  - Action bar: All Ngoko/Krama + Hapus Aksen + Download SRT
  - ⚠ Unknown Words Panel (amber, collapsible, top 100)
  - TTS panel (purple): Generate Full + cache status
  - Cue list (30 per page): preview + audio player + voice + ngoko/krama
    - Badge per cue "N tak dikenal" (amber border kalau ada unknown)
--- Workflow Split / Translate / TTS (sekunder) ---
Split SRT upload (border-2 dashed amber)
  Settings + Translate + TTS panels
TTS Text ke Audio
Kamus Viewer (read-only)
Info section
Source code download
```

---

## 📁 File Path Conventions

User MacBook folder: `~/Dubbing/`
- `~/Dubbing/kamus-jawa-draft.json` — Kamus JSON v2.3 (45.021 entries, R-20: rujukan tunggal)
- `~/Dubbing/kamus-tui.py` — TUI editor kamus v2.3 (Phase 1-6 refactor)
- `~/Dubbing/upload-supabase.py` — Upload script (Phase 5, file terpisah)
- `~/Dubbing/srt-frequency-analyzer.py` — Analyzer SRT (pakai Supabase)
- `~/Dubbing/.env` — Supabase credentials (URL + anon key)
- `~/Dubbing/srt-freq-report.txt` — Output analyzer (top unknown words)
- `~/Dubbing/mp4-ori-{name}.mp4` — MP4 source
- `~/Dubbing/srt-{lang}-original.srt` — SRT source
- `~/Dubbing/audio-{lang}-dub.wav` — audio dub result
- `~/Dubbing/mp4-{lang}-final.mp4` — final output

---

## 📝 Catatan untuk AI Next Time Buka

1. **Strategi pivot (5 Okt 2026)**: Mode ON + Smart Fit + mix-audio-dub.py = workflow utama. Dubbing Mode + retime-video.py = deprecated (20x test gagal).

2. **Editor SRT Jawa (8 Okt 2026)**: Project-based workflow. User run migration v2+v3 SQL di Supabase SQL Editor. Files:
   - `scripts/supabase-migration-v2.sql` (srt_projects + srt_cues)
   - `scripts/supabase-migration-v3.sql` (kamus: krama_inggil + register)

3. **Per-cue Preview + IndexedDB**: Audio cache persistent di browser. Cache valid kalau text+voice+pitch+cap sama. Generate Full pakai cache (hemat API call).

4. **Bidirectional alias lookup**: Source apapun (aku/inyong/kula/dalem/saya/gue/ane) → convert ke ngoko/krama utama. **`arti` (Indonesia) juga jadi source alias** — kalau SRT source = "saya", convert ke ngoko "nyong" atau krama "kula".

5. **Auto-strip aksen TTS**: `normalizeTtsText()` di tts.ts. SRT final tetap utuh (dengan aksen), text ke TTS di-strip. Edge TTS Jawa tidak bisa baca aksen (é/è/ê).

6. **Kamus v5**: Register tag Wiktionary ({{kn}}/{{kr}}/{{ki}}/{{ak}}) disimpan. Title di field yang benar. Cross-reference auto-fill dari template (2.123 entries). Parser: `scripts/parse-wiktionary-jv.py` v5.

7. **Kamus DB = ground of truth**: Supabase DB (yang user upload, mulai dari 2 entries). Web app + analyzer pakai Supabase, bukan JSON lokal (44.585 entries cuma working draft).

8. **Web app READ-ONLY untuk kamus**: Editing kamus = TUI lokal (kamus-tui.py) + upload ke Supabase. Web app cuma baca (loadKamusJawa ke memory + searchKamus display). Jangan tambah fungsi edit kamus di UI.

9. **UI panel Top 100 Unknown Words**: Di Editor SRT Jawa, panel amber collapsible. List top 100 kata tak dikenal + frequency. Klik kata → copy. Tombol "Copy all" untuk batch copy. Badge per cue "N tak dikenal".

10. **Upload logic kamus-tui.py**: HANYA upload entries dengan ngoko+krama+arti lengkap (3 field wajib). krama_inggil opsional. Yang auto-fill template tanpa arti → TIDAK di-upload (belum divalidasi user).

11. **Smart Fit algoritma**: audioRate = min(need, cap). Cap default 2.0x. Asymmetric trim (head -40dB, tail -49dB). Crossfade 150ms, NO truncate.

12. **Filosofi**: "video = ground truth, audio dub fit ke SRT ori dengan Smart Fit". Kamus cuma menyelesaikan masalah konsistensi register. Manusia paham konteks (klik cue manual, nonton VLC).

13. **User di MacBook, AI di sandbox**: User hanya bisa download dari GitHub. AI bisa akses file lokal di sandbox. Jangan gitignore file yang user butuh (kamus JSON), jangan track file yang user tidak butuh (wiktionary XML 86MB).

14. **Standar nama file** sudah diterapkan: `mp4-ori-`, `srt-{lang}-original.srt`, `audio-{lang}-dub.wav`, `mp4-{lang}-final.mp4`.

15. **VoiceStudio riset**: 36 file di `/scripts/voicestudio-study/` (gitignored). Latest commit main = 990f0627. Lihat worklog Task 7-a.

16. **voicertool.com riset**: decoded srt.js (obfuscated). Asymmetric trim, cap 2.0x, ffmpeg.wasm atempo. Lihat worklog Task 8.

17. **mix-audio-dub.py**: sidechain compression, threshold=0.05, ratio=10, attack=5ms, release=300ms. Video stream copy.

18. **Filosofi user**: "ada uang atau tidak, tetap dikerjakan step by step, terdokumentasi rapi"

19. **Visi besar**: 700 bahasa Indonesia, 169 terancam punah. Project ini prototype digitalisasi. Lihat `docs/PROJECT_VISION.md`.

20. **Target realistis kamus**: 2.000 entries dengan arti sudah cukup untuk 90% SRT Jawa sehari-hari. 80/20 rule: 20% kata dipakai 80% waktu. Bertahap, 50 entries per minggu = 2.000 entries dalam 1 tahun.

---

## 📅 Timeline Update

- **4 Okt 2026, 21:00 WIB**: Initial PROGRESS.md, test #1-#8 render video rusak DTS
- **5 Okt 2026, 02:55 WIB**: render S7-id.mp4 full season SUKSES tapi video rusak (332 DTS warnings)
- **5 Okt 2026, 03:00-08:00 WIB**: 8 iterasi fix DTS (test #9-#14)
- **5 Okt 2026, 08:30 WIB**: Update PROGRESS.md — bug history + M1 optimization
- **5 Okt 2026, 10:00 WIB**: Dub web v2.0 ter-deploy (VoiceStudio adoptions + JSON v2.0 schema)
- **5 Okt 2026, 10:30 WIB**: Standar nama file diterapkan di web + docs + Python
- **5 Okt 2026, 11:00-18:00 WIB**: Test #15-#20 render video (semua gagal stop-motion)
- **5 Okt 2026, 18:30 WIB**: Pivot strategi — Mode ON + Smart Fit + mix-audio-dub.py
- **5 Okt 2026, 19:00 WIB**: Smart Fit di mode ON diimplementasi (VoiceStudio + voicertool adopsi)
- **5 Okt 2026, 20:00 WIB**: Test #22 mode ON Smart Fit cap 2.0x — user rating 8/10 ✓
- **5 Okt 2026, 20:30 WIB**: Test #23 mode ON Smart Fit cap 1.25/1.5/2.0 — user rating buruk
- **5 Okt 2026, 20:50 WIB**: Revert ke #22 (cap 2.0x default), test #24 in progress
- **6 Okt 2026, 01:00 WIB**: Test #25 MILESTONE — Demucs + mode ON + mix = 10000% sync, MP4 profesional
- **6 Okt 2026, 02:30 WIB**: Task 10-12 — Supabase, Kamus Jawa JSON, TUI tools
- **7 Okt 2026, 18:08 WIB**: Task 13 — Editor SRT Jawa pindah ke ATAS (PRIMARY)
- **8 Okt 2026, 02:00 WIB**: Task 14 — Project-based Dual SRT Editor (auto-save + multi-project + TTS mode ON)
- **8 Okt 2026, 02:45 WIB**: Task 15 — Per-cue preview + browser local audio cache (IndexedDB)
- **8 Okt 2026, 02:55 WIB**: Bidirectional alias lookup (source apapun → ngoko/krama utama)
- **8 Okt 2026, 03:05 WIB**: Auto-strip aksen Jawa di TTS (SRT final tetap utuh)
- **8 Okt 2026, 03:15 WIB**: Kamus schema v5 — register tag + krama_inggil + xref auto-fill
- **8 Okt 2026, 03:30 WIB**: Track kamus JSON di git + untrack 86MB wiktionary XML
- **8 Okt 2026, 19:00 WIB**: Kamus-tui.py v2 — menu pre-built + .env support
- **8 Okt 2026, 20:00 WIB**: User upload 2 entries ke Supabase (test awal sukses)
- **8 Okt 2026, 20:30 WIB**: Web app Kamus Viewer read-only (audit, hapus write functions)
- **8 Okt 2026, 21:00 WIB**: srt-frequency-analyzer.py pakai Supabase sebagai ground of truth
- **8 Okt 2026, 21:30 WIB**: arti (Indonesia) jadi alias source lookup (saya/aku/gue/ane → nyong/kula)
- **8 Okt 2026, 22:00 WIB**: UI panel Top 100 Unknown Words + badge per cue
- **Next update**: Setelah user selesai isi 100-200 entries kamus + test workflow end-to-end

---

## 🎉 MILESTONE: Kamus TUI + Aksara + 5k Cue Fix (8 Okt 2026 malam, sesi panjang)

### Commits (16 commits dalam 1 sesi: 0b94ed1 → 3586fad)

| Commit | Deskripsi |
|---|---|
| `0b94ed1` | Revert auto-merge script (AI ceroboh, merge tanpa baca definisi) |
| `6a25cba` | Hapus 159 krama_inggil self-reference (ngoko == krama_inggil) |
| `8f3fa78` | Hapus SEMUA krama_inggil (parser tidak reliable) → REVERT |
| `e883ff5` | Restore krama_inggil (95 entries) — datanya BENAR, cuma TERBALIK |
| `3e8ee46` | Fix 5 entries krama_inggil TERBALIK |
| `8158bd4` | Fix SEMUA 90 krama_inggil TERBALIK — ki→ngoko, krama tetap |
| `70c5eac` | Merge pakai SEARCH kata, bukan input entry_id |
| `7286b0a` | Fix teks menu merge — hapus "by entry_id" |
| `f312d1d` | Merge sederhana — search kata 1 → search kata 2 → preview |
| `5a0c1fe` | Search merge — exact match dulu |
| `1e8efeb` | SEMUA search — exact match dulu + hapus search di keterangan |
| `7eb30f6` | Audit TUI — 5 bug fix (status recompute, merge duplikat, exact match) |
| `d06165d` | Menu matching — hapus emoji dependency, pakai keyword unik |
| `b384aa7` | Merge — gabung aksara juga |
| `62b7416` | Merge — gabung sinonim sebagai alias (comma) |
| `bf07803` | Aksara Jawa jadi source alias — database baca aksara |
| `c888744` | Audit: hapus limit 50000 — database = ground of truth |
| `3586fad` | Fix 5k cue hanya 1k terbaca — Supabase REST API limit |

### Yang sudah jadi

1. **krama_inggil TERBALIK fix** — SEMUA 90 entries dibalik:
   - Parser {{ki}} tag salah: title ditaruh di ki field, padahal title = ngoko/krama
   - ki field → pindah ke ngoko field, krama tetap, hapus ki
   - User context: "dari akar tanya (id), takon (ngoko), taken (krama)"
   - Sekarang: 0 krama_inggil entries (semua jadi ngoko+krama yang benar)

2. **TUI merge** — search kata → pilih → preview → konfirmasi:
   - Smart merge: kalau entry2 ngoko == entry1 krama → krama word
   - Gabung sinonim sebagai alias (comma): "sing, kang" bukan ambil "sing"
   - Gabung aksara: "ꦱꦶꦁ, ꦲꦶꦁꦏꦁ" (keduanya disimpan)
   - Gabung keterangan: "ket1 | ket2"
   - Tidak perlu hafal entry_id — search by kata

3. **TUI audit** — 5 bug fix:
   - save_kamus: selalu recompute status (tidak skip yang sudah ada)
   - Hapus merge_entry duplikat (merge hanya via menu)
   - Semua search: exact match dulu, baru substring
   - Menu matching: keyword unik (tidak bergantung emoji)
   - Register bisa di-edit (dropdown)

4. **Aksara Jawa support**:
   - User: "database membaca sumber. urusan web mau ngolah jadi ngoko, krama,
     bahkan ke indonesia itu urusan database"
   - Filosofi: Google = translate cerdas (kalimat), database = translate
     deterministik (kata by kata, baku sesuai Wiktionary)
   - Aksara jadi source alias di: convertRegister, isWordInKamus, suggestRegister
   - Source "ꦲꦏꦸ" → convert ke ngoko → "aku", ke krama → "kula"

5. **Database audit** — 10 cek:
   - SEMUA 5 field jadi source alias (ngoko, krama, krama_inggil, arti, aksara)
   - Output = kata pertama (ngokoVariants[0] / kramaVariants[0])
   - Tidak ada write ke kamus (read-only)
   - Hapus limit 50000 — database = ground of truth
   - Unknown Words Panel ada (top 100 + badge per cue)

6. **5k cue bug fix**:
   - Bug 1: insert 5000 cues sekaligus → Supabase reject >1000 rows
   - Fix: batch insert 500 per request
   - Bug 2: select cues tidak ada .limit() → default 1000 rows
   - Fix: .limit(100000)
   - User verify: "5100 cue sudah terbaca di project 1" ✓

### Filosofi yang dipelajari (hard way)

1. **Jangan hapus data yang "salah"** — fix/biarkan untuk user validasi
   (User: "BUKAN SALAH, HANYA TERBALIK. KENAPA DIHAPUS?")

2. **AI tidak bisa auto-merge** tanpa memahami konteks definisi
   (User: "JANGAN SEMBARANGAN ASAL HAPUS DAN ASAL MERG")

3. **Database = ground of truth** — jangan filter/limit dari web app
   (User: "jangan ada code yg menganggu database, atau filter database")

4. **Web app harus manfaatkan SEMUA data** — ngoko, krama, krama_inggil,
   arti (Indonesia), aksara Jawa. Bukan cuma ngoko+krama.
   (User: "website terlalu BODOH, tidak memanfaatkan database")

5. **Merge harus search by kata**, bukan input angka
   (User: "lha caranya user tau id gimana? ada ribuan id")

6. **Search exact match dulu** — supaya "sing" tidak tenggelam di 112 hasil
   (User: "GAK MUNCUL, SYSTEM MERGE ANEH")

7. **Gabung sinonim sebagai alias** (comma), bukan ambil pertama
   (User: "maslah baru, kalau ada sinonim, harus merge lagi")

