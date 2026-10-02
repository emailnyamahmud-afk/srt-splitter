# SRT Splitter

Aplikasi web untuk split SRT, translate subtitle, dan generate audio TTS. 100% di browser, gratis.

**Live:** https://srt-splitter.vercel.app/

## Fitur

- **Split SRT** — by durasi (5m-5jam) atau by karakter (max 5000)
- **Translate** — EN→ID, ID→Jawa, Jawa→ID, dll (gratis Google Translate atau premium OpenAI)
- **TTS Audio** — Edge TTS (gratis, Indonesia/Jawa), OpenAI, OpenRouter, Kokoro
  - **ON mode**: sync ke SRT, crossfade (durasi = SRT, audio utuh)
  - **OFF mode**: natural alami, sequential, speed control (1.0x-2.0x)
- **Python lokal** — generate audio tanpa browser (lihat `scripts/tutor-python-lokal.md`)

## Stack

Next.js 16 + TypeScript + Tailwind CSS + shadcn/ui
Deploy: Vercel (app + Edge TTS proxy)

## Cara Pakai

### Web (Vercel)
1. Buka https://srt-splitter.vercel.app/
2. Upload SRT → split → download, atau translate, atau generate TTS

### Python Lokal (MacBook)
```bash
pip3 install edge-tts numpy
python3 scripts/srt-to-audio.py subs.srt --on --voice id-ID-GadisNeural
```
Lihat `scripts/tutor-python-lokal.md` untuk detail.

## Script Python

| File | Fungsi |
|------|--------|
| `srt-to-audio.py` | Generate audio dari SRT (Edge TTS, crossfade) |
| `rapikan-jawa.py` | Rapikan ejaan Jawa di 1 file SRT |
| `rapikan-jawa-semua-season.py` | Rapikan semua season S1-S6 |
| `tambah-krama.py` | Tambah sentuhan krama di bagian formal |
| `split_srt.py` | Split SRT by durasi |

## Deploy

### Vercel (auto-deploy)
1. Push ke GitHub
2. Vercel auto-deploy dari `main` branch
3. URL: https://srt-splitter.vercel.app/

### GitHub Pages (static, optional)
- Workflow: `.github/workflows/deploy.yml`
- Settings → Pages → Source: GitHub Actions
- URL: https://emailnyamahmud-afk.github.io/srt-splitter/

## Environment

- `GITHUB_REPOSITORY` — auto-set di GitHub Actions (untuk basePath)
- `VERCEL` — auto-set di Vercel

## License

Bebas dipakai untuk produksi sendiri.
