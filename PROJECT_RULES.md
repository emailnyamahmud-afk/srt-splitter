# PROJECT_RULES.md

> Aturan project. Baca tiap session sebelum kerja. Update: 24 Okt 2026.

## Pipeline

```
[Simple — cepat, dialog dominan]
  yt-dlp-tui.py → edge-tts-tui.py → mix-tui.py (Mode C/D)
  → ~350 MB stream copy / ~1.2-2.3 GB burn SRT
  → sync 1000000%, tidak perlu DaVinci Resolve

[Full — proper, dengan SFX]
  yt-dlp-tui.py → demucs-tui.py → edge-tts-tui.py → mix-tui.py (Mode A/B)
  → ~350 MB stream copy / ~1.2-4.5 GB burn SRT
  → dengan ducking sidechain, musik latar tetap ada

Kamus (sambil kerja, parallel):
  kamus-tui.py → jv.wiktionary.json → Supabase (terverifikasi)
```

## 7 TUI — Tugas masing-masing

| # | TUI | Tugas | Status |
|---|-----|-------|--------|
| 1 | yt-dlp-tui | Download MP4 + audio M4A + SRT Indonesia | ✅ Jalan |
| 2 | demucs-tui | Split audio → no_vocals.mp3 (SFX bersih) | ✅ Jalan |
| 3 | kamus-tui | User edit JSON kamus manual (sebelum masuk DB) | ✅ Jalan (audit) |
| 4 | Web app | Translate SRT Indonesia → Jawa (kamus Supabase) | ⚠ Prototype |
| 5 | SRT editor | Sementara pakai SRT Indonesia (Jawa nunggu kamus+web) | ⏳ Pending |
| 6 | edge-tts-tui | Generate audio dub dari SRT (5000+ cue) | ✅ Jalan |
| 7 | mix-tui v3.5 | Mix MP4 + audio → final video (4 mode + bitrate) | ✅ Production-ready |

## Struktur Folder

- SSD `~/Dubbing/` = scripts + venv + jv.wiktionary.json (kecil)
- HDD `/Volumes/HDD/Dubbing/` = data (input, demucs, tts, mix, .env)
- `config.py` = base path, dipakai semua TUI
- Kalau HDD gak ter-colok → fallback ke cwd (SSD)

## Rules Aktif

### Kamus
- R-12: status='ready' hanya dari user explicit mark
- R-21: word kosong kalau paired (ngoko/krama terisi)
- R-28: Duplikat = kata identik lintas entry, lintas field
- R-29: TIDAK ADA SINONIM BEDA ENTRY — 1 konsep 1 entry
- R-49: Filter ketat indo (no leak, no jv diacritic di kolom indo)
- R-58: Tidak ada skip. Ragu → keterangan.
- R-68: Baku Jawa = cross-ref jv.wiktionary
- R-69: Register (ngoko/krama) = tugas user native Jawa, AI gak bisa
- R-71: Parser jv.wiktionary BENAR — pahami format wiktionary
- R-73: Cross-ref penulisan + keterangan, BUKAN register
- R-22: GIGO — AI tidak merujuk raw untuk audit/fix

### Pipeline (mix-tui v3.5)
- Mode A: Full + Stream copy → ~3 menit, ~350 MB
- Mode B: Full + Burn SRT → ~5 menit, ~1.2-4.5 GB (pilih bitrate)
- Mode C: Simple + Stream copy → ~1 menit, ~350 MB (USER confirmed sync 100%)
- Mode D: Simple + Burn SRT → ~5 menit, ~1.2-4.5 GB (USER confirmed: 1 Mbps > ori)
- Default mode input = Full (backward compatible)
- Default bitrate (Mode B/D) = 1.5 Mbps (seimbang); 1 Mbps user-confirmed viable
- Ducking PERLU untuk Full mode (SFX tetap ada walau vokal dibuang Demucs)
- Ducking TIDAK PERLU untuk Simple mode (no SFX)

### Data
- jv.wiktionary.json = SOURCE OF TRUTH (44.585 entries dari XML dump)
- Supabase = kamus terverifikasi (user upload manual)
- AI DILARANG buang data. Ragu → keterangan.
- di- = pasif Jawa VALID. Bukan noise.

## Dilarang

- Parsing tolol (heuristic akhiran, regex agresif)
- Buang data tanpa alasan jelas
- Bikin entry baru di jv.wiktionary (dari XML, bukan AI)
- Tentukan register ngoko/krama (AI gak bisa)
- Translate Jawa→Indonesia otomatis (AI halu)
- Overwrite jv.wiktionary dgn parsing/master yg sampah
- Auto-set status='ready' tanpa user explicit mark

## Wajib

- Baca manual per batch 100 entries kalau perlu
- Cross-ref jv.wiktionary untuk penulisan baku
- Simpan keterangan raw utk user verify
- Anti-skip: semua entries tetap ada, ragu → keterangan
- Pakai config.py untuk path (SSD scripts, HDD data)
- Tunggu user VLC feedback sebelum declare "production-ready"
