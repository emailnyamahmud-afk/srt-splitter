# PROJECT_RULES.md

> Aturan project. Baca tiap session sebelum kerja. Update: 2 Nov 2026.

## Pipeline

```
[PROPER] yt-dlp → srt-editor → demucs → edge-tts → mix Full (A/B)
[CEPAT]  yt-dlp → srt-editor → edge-tts → mix Simple (C/D)
[MUTE]   yt-dlp → srt-editor → edge-tts → mix Original (E/F)
[SHORTS] mix-tui → Dola AI → shorts-tui → shorts-csv-tui → YouTube
[MERGE]  mix-tui × N → merge-tui (stream copy) → 1 video panjang
Kamus: kamus-tui → jv.wiktionary.json → Supabase

[GEMINI-SRT]    yt-dlp → srt-editor → gemini-tts-tui (SRT mode) → mix-tui (opsional Jawa/karakter spesifik)
[GEMINI-NARASI] naskah.txt → gemini-tts-tui (Narration mode) → review-mix-tui (konten sejarah/narasi)
```

## 13 TUI

| # | TUI | Status |
|---|-----|--------|
| 1 | yt-dlp-tui v6.5 | ✅ (default 1080p, multi-SRT ID+EN) |
| 2 | demucs-tui | ✅ |
| 3 | kamus-tui v16 | ✅ (audit) |
| 4 | Web app | ⚠ Prototype |
| 5 | SRT editor (web) | ⏳ Pending |
| 6 | edge-tts-tui v7.5 | ✅ (SRT + Narasi, ID only, paralel-safe) — production default |
| 7 | mix-tui v3.10 | ✅ (force 1080p + audio 48000Hz) |
| 8 | whisper-tui v2.0 | ✅ (Metal GPU) |
| 9 | srt-editor-tui v1.0.1 | ✅ |
| 10 | shorts-tui v1.1 | ✅ |
| 11 | shorts-csv-tui v1.0 | ✅ |
| 12 | merge-tui v2.0 | ✅ (VLC confirmed, sync 100%) |
| 13 | **gemini-tts-tui v1.1** | ⚠ EXPERIMENTAL (SRT + Narasi, ID + JV, OPSI TAMBAHAN, butuh GEMINI_API_KEY) |

## Struktur Folder

- SSD `~/Dubbing/` = scripts + venv + jv.wiktionary.json
- HDD `/Volumes/HDD/Dubbing/` = data (input, demucs, tts, mix, shorts, parts, merged, review, konten, .env)
- `config.py` = base path, dipakai semua TUI
- Workflow: `cd ~/Dubbing && source venv/bin/activate && python3 <tui>.py`

## Wajib

- Pakai config.py untuk path (SSD scripts, HDD data)
- Tunggu user VLC feedback sebelum declare "production-ready"
- Sebutan hormat Tiongkok = PRESERVE, bukan mistranslate
- Tiap sesi WAJIB update docs + commit + push (AGENTS.md, PROJECT_RULES.md, scripts/README.md, README.md, worklog.md)
- TUI baru → update tabel "TUI" di semua docs di atas
- **Standarisasi res+audio = kerjaan mix-tui v3.10**
- **merge-tui v2.0** = stream copy (no drift) jika format konsisten, standardize jika beda
- **fix-merge-audio.py = DELETED** (audio drift, failed experiment)
- **edge-tts-tui v7.5 = production default** (SRT + Narasi, Indonesia only, paralel-safe, no API key)
- **gemini-tts-tui v1.1 = OPSI TAMBAHAN** (SRT + Narasi, ID + JV, butuh GEMINI_API_KEY)
  - Output SRT mode: `HDD/tts/{prefix}-audio-id-dub.wav` (mix-tui compatible)
  - Output Narration mode: `HDD/tts/{stem}-narasi.wav` (review-mix-tui compatible)
  - Jangan hapus / ganti edge-tts-tui v7.5
  - Status EXPERIMENTAL sampai user VLC feedback OK

## Dilarang

- Parsing tolol / buang data / halu
- Tentukan register ngoko/krama (AI gak bisa)
- Translate Jawa→Indonesia otomatis
- Auto-set status='ready' tanpa user explicit mark
- Over-engineer (fix-merge-audio = contoh gagal)
- Hapus / ganti edge-tts-tui v7.5 dengan gemini-tts-tui (kedua TUI harus hidup berdampingan)
- Bikin TUI baru tanpa update docs utama (AGENTS/PROJECT_RULES/scripts/README/README root)
