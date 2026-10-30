# AGENTS.md

> Dibaca AI di awal setiap session. Update: 30 Okt 2026.

## Anti-Amnesia Protocol

1. Baca duluan: AGENTS.md, README.md, PROJECT_RULES.md, scripts/README.md, scripts/config.py
2. Jangan ngandalkan memory context — context panjang = amnesia
3. Setiap sesi WAJIB update docs + commit + push
4. Jangan tebak struktur folder — baca config.py
5. Cek git log untuk state terakhir

## Project: SRT Splitter + Dubbing Multi-Bahasa

Pipeline dubbing bahasa eksternal → Indonesia / Jawa / Sunda.
- ID: jalan end-to-end (12 TUI production)
- Jawa/Sunda: nunggu kamus Supabase

## 12 TUI

| # | TUI | Status |
|---|-----|--------|
| 1 | yt-dlp-tui v6.5 (MP4+MP3+multi-SRT ID+EN, default 1080p) | ✅ |
| 2 | demucs-tui | ✅ |
| 3 | kamus-tui v16 | ✅ (audit) |
| 4 | Web app | ⚠ Prototype |
| 5 | SRT editor (web) | ⏳ Pending |
| 6 | edge-tts-tui v7.4 (paralel-safe) | ✅ |
| 7 | mix-tui v3.10 (force 1080p + audio 48000Hz stereo) | ✅ |
| 8 | whisper-tui v2.0 (Metal GPU) | ✅ |
| 9 | srt-editor-tui v1.0.1 | ✅ |
| 10 | shorts-tui v1.1 (Shorts + Part) | ✅ |
| 11 | shorts-csv-tui v1.0 | ✅ |
| 12 | merge-tui v2.0 (full format detect, stream copy / standardize) | ✅ VLC confirmed |

## Struktur Folder

- SSD `~/Dubbing/` — scripts (.py) + venv + jv.wiktionary.json
- HDD `/Volumes/HDD/Dubbing/` — data (input, demucs, tts, mix, shorts, parts, merged, .env)
- `config.py` — `ensure_hdd()`, `INPUT_DIR`, `MIX_DIR`, `MERGED_DIR`, dll
- Workflow: `cd ~/Dubbing && source venv/bin/activate && python3 <tui>.py`

## Aturan

1. jv.wiktionary.json = SOURCE OF TRUTH
2. Supabase = kamus terverifikasi (user upload manual)
3. AI DILARANG parsing tolol / buang data / halu
4. Register (ngoko/krama) = tugas user, AI gak bisa
5. Data di HDD, scripts di SSD
6. Sebutan hormat Tiongkok (Nona/Tuan/Dokter/Paman) = PRESERVE, bukan mistranslate
7. GT input: SRT English (dari whisper-tui) → GT English→ID lebih akurat
8. **Standarisasi res+audio = kerjaan mix-tui v3.10**, bukan yt-dlp atau merge-tui
9. **merge-tui v2.0** = full format detect (6 properties) + stream copy (super cepat) / standardize (re-encode). VLC confirmed: sync 100%.
10. **fix-merge-audio.py = DELETED** (audio drift, failed experiment)

## Pipeline Final (confirmed end-to-end)

```
yt-dlp v6.5 (varies, multi-SRT ID+EN)
  → mix-tui v3.10 (force 1080p + audio 48000Hz stereo = STANDARDISASI)
    → merge-tui v2.0 (stream copy ~2 menit, no drift)
      → VLC: sync 100% ✅
```

## Status (30 Okt 2026)

- merge-tui v2.0: ✅ VLC confirmed (10 file × 24h, sync 100%, stream copy ~2 menit)
- mix-tui v3.10: ✅ force 1080p + audio 48000Hz stereo
- yt-dlp v6.5: ✅ multi-SRT ID+EN, default 1080p preferred
- Pipeline produksi: 6 film tested, all TUI production-ready
