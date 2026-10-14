# PROJECT_RULES.md

> Aturan project. Baca tiap session.

## Pipeline

yt-dlp → Demucs → edge-tts → SRT editor (web) → mix-tui

Kamus: jv.wiktionary.json (lembar kerja) → Supabase (terverifikasi)

## R-01 sampai R-73 (rules aktif)

- R-12: status='ready' hanya dari user explicit mark
- R-21: word kosong kalau paired (ngoko/krama terisi)
- R-28: Duplikat = kata identik lintas entry, lintas field
- R-29: TIDAK ADA SINONIM BEDA ENTRY — 1 konsep 1 entry
- R-49: Filter ketat indo (no leak, no jv diacritic di kolom indo)
- R-58: Tidak ada skip. Ragu → keterangan.
- R-61: 1 file kamus, integrasi semua sumber
- R-68: Baku Jawa = cross-ref jv.wiktionary
- R-69: Register = tugas user native Jawa
- R-71: Parser jv.wiktionary BENAR — pahami format wiktionary
- R-73: Cross-ref penulisan + keterangan, BUKAN register

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
