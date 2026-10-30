# PROJECT_RULES.md

> Aturan project. Baca tiap session sebelum kerja. Update: 30 Okt 2026.

## Pipeline

```
[PROPER] yt-dlp → srt-editor → demucs → edge-tts → mix Full (A/B)
[CEPAT]  yt-dlp → srt-editor → edge-tts → mix Simple (C/D)
[MUTE]   yt-dlp → srt-editor → edge-tts → mix Original (E/F)
[SHORTS] mix-tui → Dola AI → shorts-tui → shorts-csv-tui → YouTube
[MERGE]  mix-tui × N → merge-tui (stream copy) → 1 video panjang
Kamus: kamus-tui → jv.wiktionary.json → Supabase
```

## 12 TUI

| # | TUI | Status |
|---|-----|--------|
| 1 | yt-dlp-tui v6.5 | ✅ (default 1080p, multi-SRT ID+EN) |
| 2 | demucs-tui | ✅ |
| 3 | kamus-tui v16 | ✅ (audit) |
| 4 | Web app | ⚠ Prototype |
| 5 | SRT editor (web) | ⏳ Pending |
| 6 | edge-tts-tui v7.4 | ✅ (paralel-safe) |
| 7 | mix-tui v3.10 | ✅ (force 1080p + audio 48000Hz) |
| 8 | whisper-tui v2.0 | ✅ (Metal GPU) |
| 9 | srt-editor-tui v1.0.1 | ✅ |
| 10 | shorts-tui v1.1 | ✅ |
| 11 | shorts-csv-tui v1.0 | ✅ |
| 12 | merge-tui v2.0 | ✅ (VLC confirmed, sync 100%) |

## Struktur Folder

- SSD `~/Dubbing/` = scripts + venv + jv.wiktionary.json
- HDD `/Volumes/HDD/Dubbing/` = data (input, demucs, tts, mix, shorts, parts, merged, .env)
- `config.py` = base path, dipakai semua TUI
- Workflow: `cd ~/Dubbing && source venv/bin/activate && python3 <tui>.py`

## Wajib

- Pakai config.py untuk path (SSD scripts, HDD data)
- Tunggu user VLC feedback sebelum declare "production-ready"
- Sebutan hormat Tiongkok = PRESERVE, bukan mistranslate
- Tiap sesi WAJIB update docs + commit + push
- **Standarisasi res+audio = kerjaan mix-tui v3.10**
- **merge-tui v2.0** = stream copy (no drift) jika format konsisten, standardize jika beda
- **fix-merge-audio.py = DELETED** (audio drift, failed experiment)

## Dilarang

- Parsing tolol / buang data / halu
- Tentukan register ngoko/krama (AI gak bisa)
- Translate Jawa→Indonesia otomatis
- Auto-set status='ready' tanpa user explicit mark
- Over-engineer (fix-merge-audio = contoh gagal)
