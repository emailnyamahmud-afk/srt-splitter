# Scripts

Python TUI untuk workflow dubbing Mandarin→Jawa + kamus Jawa.

## Pipeline scripts

| Script | Fungsi | Output |
|--------|--------|--------|
| yt-dlp-tui.py | Download video/audio | ~/Dubbing/*.m4a |
| demucs-tui.py | Vocal separation | no_vocals.wav |
| edge-tts-tui.py | TTS generation | dub-id.wav + subs-id.srt |
| mix-tui.py | Final mix video | final.mp4 |

## Kamus scripts

| Script | Fungsi |
|--------|--------|
| kamus-tui.py | TUI editor kamus (v15) |
| parse-jv-wiktionary-v2.py | Parser jv.wiktionary XML (BENAR) |
| upload-supabase.py | Upload kamus terverifikasi ke DB |
| srt-frequency-analyzer.py | Analisis frekuensi kata SRT |

## Install

```bash
pip3 install questionary edge-tts yt-dlp
```

## Workflow

```bash
python3 yt-dlp-tui.py      # 1. Download
python3 demucs-tui.py      # 2. Separasi vocal
python3 edge-tts-tui.py    # 3. Generate TTS
# SRT editor web app       # 4. Edit SRT + translate
python3 mix-tui.py         # 5. Mix final video
```
