# Progress Log — SRT Splitter + Dubbing Project

Dokumen ini catatan status project untuk AI / developer next time baca. Update setiap sesi kerja.

**Last updated:** 8 Oktober 2026, 03:30 WIB

---

## 📌 Quick Status

| Item | Status |
|---|---|
| Web app (srt-splitter.vercel.app) — Editor SRT Jawa (project-based) | ✅ Production ready |
| **Editor SRT Jawa (project-based + auto-save Supabase + multi-project)** | ✅ Deployed, user tinggal run migration v2+v3 |
| **Per-cue Preview + browser cache (IndexedDB)** | ✅ Deployed, test pending user |
| **Bidirectional alias lookup (source apapun → ngoko/krama)** | ✅ Deployed |
| **Auto-strip aksen Jawa di TTS (SRT final tetap utuh)** | ✅ Deployed |
| **Kamus schema v5 (register tag + krama_inggil + xref)** | ✅ Parser + web app code ready |
| **Kamus JSON 11MB track di GitHub + 1.3MB .gz** | ✅ User bisa download dari GitHub |
| **86MB wiktionary XML di-untrack (jangan commit)** | ✅ User re-download dari Wiktionary kalau butuh |
| **Mode ON + Smart Fit (video = ground truth)** | ✅ User rating 9/10 (cap 2.0x, pitch -15Hz laki) |
| **Python `demucs-tui.py` + `mix-audio-dub.py`** | ✅ Working (MILESTONE Test #25, 10000% sync) |
| **Test #25 workflow end-to-end (Demucs + mode ON + mix)** | ✅ MP4 profesional, 10000% sync |
| Pitch control (Edge TTS -10Hz laki, +10Hz perempuan) | ✅ Working, user pakai -15Hz |
| Dubbing Mode v2.0 + retime-video.py | ⚠️ Deprecated (20x test gagal, backup) |
| Repo audit (162 → 110 tracked files) | ✅ Done |
| User run migration v2+v3 SQL di Supabase | ⏳ Pending user |
| Kamus re-import ke Supabase (v5 schema) | ⏳ Pending user |
| Test full season S7-id (2.5 jam) | ⏳ Pending user |
| Workflow multi-bahasa (Jawa/Sunda/dll) | 🔜 Next step |

---

## 🎉 MILESTONE: Editor SRT Jawa Project-based (8 Okt 2026)

### Yang sudah jadi di web app (commits 911fee0 → 4972137)

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
- Cross-reference auto-fill: 55 ngoko entries dapat krama mapping gratis
- Parser: `scripts/parse-wiktionary-jv.py` v5 (343 lines)

**6. Kamus JSON di GitHub** (commit `4972137`)
- public/kamus-jawa-full.json (11MB, 44.585 entri) — TRACK di git
- public/kamus-jawa-full.json.gz (1.3MB compressed) — download cepat
- 86MB wiktionary XML → UNTRACK (user re-download dari Wiktionary kalau butuh)
- User di MacBook bisa download kamus dari GitHub, edit di VSCode, upload ke Supabase

---

## 🎉 MILESTONE LAMA: Workflow end-to-end SUKSES (Test #25, 6 Okt 2026 01:00 WIB)

**User feedback: "luar biasa, outputnya benar-benar mp4 profesional. SFX sangat bersih, audio Dub sangat bersih, 10000% Sync."**

### Workflow yang berhasil (3 fase):
```
Fase 0: demucs-tui.py → no_vocals.wav (SFX bersih, 61 detik MPS)
Fase 1: Web app mode ON + Smart Fit + pitch -15Hz → audio-id-dub.wav (9/10, 100% sync)
Fase 2: mix-audio-dub.py --sfx-wav → mp4-id-final.mp4 (7 detik, 0 DTS warnings)
```

### Test #25 metrics:
| Metric | Hasil |
|---|---|
| Demucs waktu | 61 detik (MPS, 7.30s/s processing) |
| Mix waktu | 6.81 detik (FFmpeg sidechain compression) |
| Total waktu | ~68 detik untuk 7.5 menit video |
| DTS warnings | 0 (clean stream copy, no concat) |
| Video sync | 100% ori (stream copy, no re-encode) |
| SFX | Bersih dari Demucs (no Mandarin vocals) |
| Dialog | Smart Fit + pitch -15Hz (9/10 user rating) |
| Output | 115.5 MB, 428.23s (7:08) |

---

## 🗄️ Supabase Schema (Migration v1 → v2 → v3)

### Migration v1 (initial)
- Tables: `srt_projects`, `srt_cues`, `kamus`
- RLS: allow_all (anonymous user ID)

### Migration v2 (commit `eb0ac16`)
- `srt_projects`: ADD `original_srt_id` TEXT (SRT Indonesia konteks)
- `srt_cues`: ADD `text_id` (Indonesia per cue) + `voice` (per-cue voice assignment)
- Triggers: auto-update `updated_at`
- SQL file: `scripts/supabase-migration-v2.sql`

### Migration v3 (commit `d6c228c`)
- `kamus`: ADD `krama_inggil` TEXT (kata krama inggil + alias)
- `kamus`: ADD `register` TEXT ('ngoko'|'krama'|'krama_inggil'|'kawi'|'umum')
- SQL file: `scripts/supabase-migration-v3.sql`

**User perlu run ketiga migration di Supabase SQL Editor**:
1. v1 (sudah di-run saat setup awal)
2. v2 (untuk Editor SRT Jawa project-based)
3. v3 (untuk kamus schema baru)

---

## 📚 Kamus Jawa — Format v5

### Schema
```json
{
  "ngoko": "sapa",          // ngoko word + alias (atau kosong kalau entry krama)
  "aksara": "ꦱꦥ",          // aksara Jawa
  "krama": "sinten",        // krama word + alias (atau kosong kalau entry ngoko)
  "krama_inggil": "",       // krama inggil word (v5)
  "arti": "",               // terjemahan Indonesia (user isi manual)
  "keterangan": "sinten; tembung pitakon...",  // definisi JAWA dari XML (JANGAN HAPUS)
  "register": "umum",       // 'ngoko'|'krama'|'krama_inggil'|'kawi'|'umum' (v5)
  "sumber": "jv.wiktionary.org + xref"
}
```

### Stats (44.585 entri)
- ngoko: 22.464
- umum: 19.807 (default, belum ada tag Wiktionary)
- kawi: 2.217
- krama_inggil: 95
- krama: 2

### Files
| File | Size | Status |
|---|---|---|
| `public/kamus-jawa-full.json` | 11MB | TRACK di git, user download dari GitHub |
| `public/kamus-jawa-full.json.gz` | 1.3MB | TRACK di git, download cepat |
| `public/kamus-jawa.json` | 21KB | TRACK di git, draft v4 lama (backup) |
| `upload/wiktionary/wiktionary-jv` | 86MB | UNTRACK (re-download dari Wiktionary) |

### Workflow user (MacBook)
1. Download `public/kamus-jawa-full.json.gz` dari GitHub (1.3MB)
2. Extract: `gunzip kamus-jawa-full.json.gz` → 11MB JSON
3. Edit di VSCode (cari entry, isi krama/arti)
4. Upload ke Supabase: `python3 scripts/edit-kamus.py import public/kamus-jawa-full.json`

---

## 🎯 PIVOT STRATEGI (5 Okt 2026, setelah 20x test render video gagal)

### Latar belakang
Setelah 20x test render video (`retime-video.py`) gagal (stop-motion, DTS warnings, drift, slow-mo ekstrim), user sadar:
- "justru yg penting di hulu = web dub kita. kalau durasi masih jadi penjara = apa gunanya?"
- "kita ubah video sebagai ground off truth = lalu kita optimalkan web TTS untuk generate audio sesuai srt ori?"
- "karena srt ori sudah sync dengan video ori, maka generate audio dengan timesmap ori = 100% sync"

### Strategi baru: Mode ON + Smart Fit (video = ground truth)

**Lama (Dubbing Mode + render video):**
```
SRT ori → translate → Dubbing Mode (audio natural, SRT baru) → retime-video.py (20x gagal)
```

**Baru (Mode ON + Smart Fit + mix):**
```
SRT ori → mode ON + Smart Fit (audio fit SRT ori, video 100% sync) → mix SFX (Demucs) → MP4 final
```

### Smart Fit algoritma
- audioRate = min(need, cap) per cue
- Cap default 2.0x (voicertool, user rating 8/10)
- Asymmetric trim (head -40dB aggressive, tail -49dB gentle)
- Crossfade 150ms, NO truncate
- Peak normalize -2 dBFS per cue

---

## 🛠️ Web App Architecture (8 Okt 2026)

### Komponen baru (commits 911fee0 → 4972137)

```
src/components/srt-editor-panel.tsx     1111 lines (project-based Dual SRT Editor)
src/lib/audio-cache.ts                  274 lines (IndexedDB utility)
src/lib/rapikan-jawa.ts                  341 lines (kamus + bidirectional lookup)
src/lib/supabase.ts                     530 lines (CRUD + dual project functions)
src/lib/tts.ts                         1628 lines (narrateSingleCue + stitchFullAudio + normalizeTtsText)
```

### Layout web app baru (8 Okt 2026)
```
Header (logo + title + 100% Sync badge)
Editor SRT Jawa (PRIMARY, border-2 indigo)
  - Empty state: + Project Baru + Buka Project + Recent projects
  - Active state: nama project + cue count + auto-save badge
  - TTS panel (purple): Generate Full + cache status
  - Cue list (30 per page): preview button + audio player + voice + ngoko/krama
--- Workflow Split / Translate / TTS (sekunder) ---
Split SRT upload (border-2 dashed amber)
  Settings + Translate + TTS panels
TTS Text ke Audio
Kamus Jawa Editor (jika Supabase ready)
Info section
Source code download
```

---

## 📁 File Path Conventions

User MacBook folder: `~/Dubbing/`
- `~/Dubbing/mp4-ori-{name}.mp4` — MP4 source
- `~/Dubbing/srt-{lang}-original.srt` — SRT source
- `~/Dubbing/audio-{lang}-dub.wav` — audio dub result
- `~/Dubbing/mp4-{lang}-final.mp4` — final output

Standar nama file:
| File | Format | Contoh |
|---|---|---|
| MP4 source | `mp4-ori-{name}.mp4` | `mp4-ori-test-7min.mp4` |
| SRT source | `srt-{lang}-original.srt` | `srt-id-original.srt` |
| Audio dub | `audio-{lang}-dub.wav` | `audio-id-dub.wav` |
| Output final | `mp4-{lang}-final.mp4` | `mp4-id-final.mp4` |

---

## 📝 Catatan untuk AI Next Time Buka

1. **Strategi pivot (5 Okt 2026)**: Mode ON + Smart Fit + mix-audio-dub.py = workflow utama. Dubbing Mode + retime-video.py = deprecated (20x test gagal).

2. **Editor SRT Jawa (8 Okt 2026)**: Project-based workflow. User run migration v2+v3 SQL di Supabase SQL Editor. Files:
   - `scripts/supabase-migration-v2.sql` (srt_projects + srt_cues)
   - `scripts/supabase-migration-v3.sql` (kamus: krama_inggil + register)

3. **Per-cue Preview + IndexedDB**: Audio cache persistent di browser. Cache valid kalau text+voice+pitch+cap sama. Generate Full pakai cache (hemat API call).

4. **Bidirectional alias lookup**: Source apapun (aku/inyong/kula/dalem) → convert ke ngoko/krama utama. Toggle Ngoko sekarang convert text (bukan cuma set status).

5. **Auto-strip aksen TTS**: `normalizeTtsText()` di tts.ts. SRT final tetap utuh (dengan aksen), text ke TTS di-strip. Edge TTS Jawa tidak bisa baca aksen (é/è/ê).

6. **Kamus v5**: Register tag Wiktionary ({{kn}}/{{kr}}/{{ki}}/{{ak}}) disimpan. Title di field yang benar. Cross-reference auto-fill (55 entries gratis). Parser: `scripts/parse-wiktionary-jv.py` v5.

7. **Smart Fit algoritma**: audioRate = min(need, cap). Cap default 2.0x. Asymmetric trim (head -40dB, tail -49dB). Crossfade 150ms, NO truncate.

8. **Filosofi**: "video = ground truth, audio dub fit ke SRT ori dengan Smart Fit". Bukan "audio bebas dari penjara SRT".

9. **User di MacBook, AI di sandbox**: User hanya bisa download dari GitHub. AI bisa akses file lokal di sandbox. Jangan gitignore file yang user butuh (kamus JSON), jangan track file yang user tidak butuh (wiktionary XML 86MB).

10. **Standar nama file** sudah diterapkan: `mp4-ori-`, `srt-{lang}-original.srt`, `audio-{lang}-dub.wav`, `mp4-{lang}-final.mp4`.

11. **Schema v2.0** (Dubbing Mode, deprecated): chunks, fittedCues, params, audioRate, videoRatio, status. Backward compat v1.0 dengan `points` alias.

12. **VoiceStudio riset**: 36 file di `/scripts/voicestudio-study/` (gitignored). Latest commit main = 990f0627. Lihat worklog Task 7-a.

13. **voicertool.com riset**: decoded srt.js (obfuscated). Asymmetric trim, cap 2.0x, ffmpeg.wasm atempo. Lihat worklog Task 8.

14. **mix-audio-dub.py**: sidechain compression, threshold=0.05, ratio=10, attack=5ms, release=300ms. Video stream copy.

15. **Filosofi user**: "ada uang atau tidak, tetap dikerjakan step by step, terdokumentasi rapi"

16. **Visi besar**: 700 bahasa Indonesia, 169 terancam punah. Project ini prototype digitalisasi. Lihat `docs/PROJECT_VISION.md`.

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
- **7 Okt 2026, 18:08 WIB**: Task 13 — Editor SRT Jawa pindah ke ATAS (PRIMARY) + 2 tombol upload side-by-side
- **8 Okt 2026, 02:00 WIB**: Task 14 — Project-based Dual SRT Editor (auto-save + multi-project + TTS mode ON)
- **8 Okt 2026, 02:45 WIB**: Task 15 — Per-cue preview + browser local audio cache (IndexedDB)
- **8 Okt 2026, 02:55 WIB**: Bidirectional alias lookup (source apapun → ngoko/krama utama)
- **8 Okt 2026, 03:05 WIB**: Auto-strip aksen Jawa di TTS (SRT final tetap utuh)
- **8 Okt 2026, 03:15 WIB**: Kamus schema v5 — register tag + krama_inggil + xref auto-fill
- **8 Okt 2026, 03:30 WIB**: Track kamus JSON di git + untrack 86MB wiktionary XML
- **Next update**: Setelah user run migration v2+v3 + test Editor SRT Jawa di production
