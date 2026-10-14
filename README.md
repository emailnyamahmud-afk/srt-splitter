# SRT Splitter + Dubbing Jawa

Aplikasi web + Python TUI untuk dubbing Mandarin→Jawa end-to-end.

**Live:** https://srt-splitter.vercel.app/

## Pipeline

```
yt-dlp → Demucs → edge-tts → SRT editor (web) → mix-tui
                                          ↑
                                     kamus-tui
                                          ↑
                                  jv.wiktionary.json
                                          ↑
                                  Supabase (verified)
```

## Komponen

### 1. yt-dlp-tui.py — Download video/audio
- M4A native (skip MP3 conversion)
- Subtitle JSON parser
- 4 voice choices
- Output: ~/Dubbing/

### 2. demucs-tui.py — Vocal separation
- M1 MPS acceleration (16m untuk 2 jam audio)
- Auto-hapus vocals.mp3
- Output: no_vocals.wav (instrumental)

### 3. edge-tts-tui.py — TTS generation (100% lokal)
- Edge TTS Python WebSocket (bukan browser)
- Smart Fit algorithm (speedup+slowdown)
- Inline mix (RAM efficient untuk 5000+ cues)
- Output: dub-id.wav + subs-id.srt

### 4. SRT editor (web app)
- Split SRT per cue
- Translate Mandarin→Jawa (kamus lookup)
- Add new entries to kamus via kamus-tui
- Build: Next.js + Vercel

### 5. mix-tui.py — Final mix
- Mode A: stream copy (3 menit, no SRT burn)
- Mode B: burn SRT (4 menit, M1 VideoToolbox 35x)
- 4 position options (Opsi A/B/C/D)
- Output: final MP4

## Kamus

### jv.wiktionary.json — Lembar kerja
- 44.585 entries dari jv.wiktionary XML dump (parser BENAR)
- Field: word (lemma baku), definisi (arti Jawa), aksara, ngoko, krama, terjemahan_indo, keterangan (raw wikitext)
- 8.618 entries dgn indo (cross-ref dari master lama)
- 2.397 entries dgn register (dari template {{ngoko|}}/{{krama|}})
- User validasi manual: isi indo (translate dari definisi Jawa), isi register (word→ngoko/krama)

### kamus-tui.py — Editor kamus
- Edit jv.wiktionary.json (lembar kerja)
- Search, browse, edit per entry
- Deteksi duplikat (lintas field, lintas entry)
- Audit flags (parser leak, indo long, word long, dll)
- Tambah entry baru (workflow SRT editor)
- Upload ke Supabase (hanya entries terverifikasi user)

### Supabase — Database kamus terverifikasi
- User upload manual setelah validasi satu-satu di jv.wiktionary.json
- Schema: id, ngoko, aksara, krama, indo, keterangan, sumber, status, created_at, updated_at
- Ground of truth = Supabase (bukan JSON)

## Download

```bash
# Scripts
curl -L -o yt-dlp-tui.py "https://raw.githubusercontent.com/emailnyamahmud-afk/srt-splitter/main/scripts/yt-dlp-tui.py"
curl -L -o demucs-tui.py "https://raw.githubusercontent.com/emailnyamahmud-afk/srt-splitter/main/scripts/demucs-tui.py"
curl -L -o edge-tts-tui.py "https://raw.githubusercontent.com/emailnyamahmud-afk/srt-splitter/main/scripts/edge-tts-tui.py"
curl -L -o mix-tui.py "https://raw.githubusercontent.com/emailnyamahmud-afk/srt-splitter/main/scripts/mix-tui.py"
curl -L -o kamus-tui.py "https://raw.githubusercontent.com/emailnyamahmud-afk/srt-splitter/main/scripts/kamus-tui.py"
curl -L -o upload-supabase.py "https://raw.githubusercontent.com/emailnyamahmud-afk/srt-splitter/main/scripts/upload-supabase.py"

# Kamus
curl -L -o jv.wiktionary.json "https://raw.githubusercontent.com/emailnyamahmud-afk/srt-splitter/main/public/jv.wiktionary.json"
```
