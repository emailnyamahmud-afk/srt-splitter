# PROJECT_RULES.md

> Aturan project. Baca tiap session sebelum kerja. Update: 26 Okt 2026.

## Pipeline

```
[PROPER] yt-dlp → demucs → edge-tts → mix Full (A/B)         clean sempurna
[CEPAT]  yt-dlp → edge-tts → mix Simple (C/D)                no SFX
[MUTE]   yt-dlp → edge-tts → mix Original v3.7.6 (E/F)       skip Demucs, MUTE COMPLETE

Kamus (parallel): kamus-tui → jv.wiktionary.json → Supabase
```

## 9 TUI

| # | TUI | Status |
|---|-----|--------|
| 1 | yt-dlp-tui v6.2 | ✅ Production (FB+YT confirmed) |
| 2 | demucs-tui | ✅ Production |
| 3 | kamus-tui v16 | ✅ Production (audit) |
| 4 | Web app | ⚠ Prototype |
| 5 | SRT editor (web, pakai SRT ID) | ⏳ Pending |
| 6 | edge-tts-tui v7.4 (paralel-safe, lock file + 429 retry) | ✅ Production |
| 7 | mix-tui v3.8.2 | ✅ Production (all tested + logo + fade) |
| 8 | whisper-tui v1.1 | ✅ Production (SRT quality 90-95%) |
| 9 | srt-editor-tui v1.0.1 | ✅ Production (fix typo SRT translate) |

## Struktur Folder

- SSD `~/Dubbing/` = scripts + venv + jv.wiktionary.json (kecil)
- HDD `/Volumes/HDD/Dubbing/` = data (input, demucs, tts, mix, .env)
- `config.py` = base path, dipakai semua TUI
- Kalau HDD gak ter-colok → fallback ke cwd (SSD)

## Rules Aktif

### Kamus
- R-12: status='ready' hanya dari user explicit mark
- R-21: word kosong kalau paired (ngoko/krama terisi)
- R-29: TIDAK ADA SINONIM BEDA ENTRY — 1 konsep 1 entry
- R-49: Filter ketat indo (no leak, no jv diacritic di kolom indo)
- R-58: Tidak ada skip. Ragu → keterangan.
- R-69: Register (ngoko/krama) = tugas user native Jawa, AI gak bisa
- R-22: GIGO — AI tidak merujuk raw untuk audit/fix

### Pipeline (mix-tui v3.8.2 — based on v3.7.6 MUTE base)
- Mode A/B (Full): sidechain compress ducking (gradual, pakai no_vocals Demucs)
- Mode C/D (Simple): no ducking (Dub copy as-is)
- Mode E/F (Original v3.7.6): amultiply MUTE COMPLETE (skip Demucs)
  - SRT Indonesia → envelope WAV inverted (0=cue, 1=gap)
  - MP3 ori × envelope = MUTE TOTAL saat cue, NORMAL saat gap
  - 1 SRT untuk ducking + burn (timestamps identik SRT Mandarin)
- Output: langsung ke HDD (v3.7.4), no manual move
- Bitrate (Mode B/D/F): 1 Mbps (hemat), 1.5 (default), 2 (sharp), 4 (HD-ready)

### Data
- jv.wiktionary.json = SOURCE OF TRUTH (44.585 entries dari XML dump)
- Supabase = kamus terverifikasi (user upload manual)
- AI DILARANG buang data. Ragu → keterangan.
- di- = pasif Jawa VALID. Bukan noise.

## Dilarang

- Parsing tolol (heuristic akhiran, regex agresif)
- Buang data tanpa alasan jelas
- Tentukan register ngoko/krama (AI gak bisa)
- Translate Jawa→Indonesia otomatis (AI halu)
- Auto-set status='ready' tanpa user explicit mark
- Pakai sidechain compress untuk MUTE (wrong tool, gradual reduction only)
  → Untuk MUTE: Demucs (Full mode) atau amultiply SRT-driven (Original v3.7.6)

## Wajib

- Baca manual per batch 100 entries kalau perlu
- Cross-ref jv.wiktionary untuk penulisan baku
- Simpan keterangan raw utk user verify
- Pakai config.py untuk path (SSD scripts, HDD data)
- Tunggu user VLC feedback sebelum declare "production-ready"
- Untuk MUTE TOTAL: pakai amultiply + inverted envelope (v3.7.6)
