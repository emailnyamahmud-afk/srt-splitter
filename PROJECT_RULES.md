# PROJECT_RULES.md

> Aturan project. Baca tiap session sebelum kerja. Update: 15 Okt 2026.

## Pipeline

```
yt-dlp-tui.py → demucs-tui.py → edge-tts-tui.py → SRT editor (web) → mix-tui.py
                                                      ↑
                                               kamus-tui.py → jv.wiktionary.json → Supabase
```

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

### Pipeline
- yt-dlp: M4A native, output ke HDD/input/
- Demucs: MPS acceleration, output ke HDD/demucs/
- edge-tts: 100% lokal (Edge TTS WebSocket), output ke HDD/tts/
- mix: Mode A stream copy / Mode B burn SRT, output ke HDD/mix/

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

## Wajib

- Baca manual per batch 100 entries kalau perlu
- Cross-ref jv.wiktionary untuk penulisan baku
- Simpan keterangan raw utk user verify
- Anti-skip: semua entries tetap ada, ragu → keterangan
- Pakai config.py untuk path (SSD scripts, HDD data)
