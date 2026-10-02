# Edge TTS Proxy Deployment Guide

Browser JavaScript **tidak bisa langsung** connect ke Microsoft Edge TTS endpoint karena:
1. Microsoft check `Origin` header (hanya accept `chrome-extension://...`)
2. Browser JavaScript tidak bisa set `Origin` header manual (security restriction)

Solusinya: Deploy Edge TTS proxy ke Vercel (gratis, 100 serverless function executions/hari).

## Cara Deploy

### Opsi A: Deploy via Vercel CLI (paling cepat, ~2 menit)

```bash
# Install Vercel CLI
npm i -g vercel

# Clone repo, lalu di root folder:
cd srt-splitter
vercel

# Ikuti prompt:
# - Set up and deploy: Y
# - Which scope: pilih akun kamu
# - Link to existing project: N
# - Project name: srt-splitter (atau apapun)
# - Framework preset: Next.js
# Vercel akan deteksi api/edge-tts.js sebagai serverless function
```

### Opsi B: Deploy via GitHub Integration (auto-deploy)

1. Push repo ke GitHub (sudah kamu lakukan)
2. Buka https://vercel.com/new
3. Import repo `emailnyamahmud-afk/srt-splitter`
4. Vercel auto-deteksi `vercel.json` dan `api/edge-tts.js`
5. Klik **Deploy** — selesai dalam ~1 menit
6. Dapat URL seperti `https://srt-splitter-xxxxx.vercel.app`

### Setelah Deploy

**Jika pakai app dari GitHub Pages** (`https://emailnyamahmud-afk.github.io/srt-splitter/`):
1. Buka app
2. Pilih provider "Edge TTS" (default)
3. Di bawah voice selector, ada field **"Edge TTS Proxy URL"**
4. Paste URL Vercel kamu: `https://srt-splitter-xxxxx.vercel.app/api/edge-tts`
5. URL disimpan di localStorage (browser kamu)

**Jika pakai app dari Vercel langsung:**
- Tidak perlu set apapun, app akan otomatis pakai `/api/edge-tts` (same-origin)

## Verifikasi Proxy Berfungsi

```bash
# Test dengan curl
curl -X POST https://your-vercel-app.vercel.app/api/edge-tts \
  -H "Content-Type: application/json" \
  -d '{"text":"Halo, ini test","voice":"id-ID-GadisNeural"}' \
  --output test.mp3

file test.mp3
# Output: MPEG ADTS, layer III, v2, 48 kbps, 24 kHz, Monaural
```

## Cost

Vercel hobby plan: **GRATIS**
- 100 serverless function executions per hari
- 100 GB bandwidth per bulan
- Untuk SRT 1 jam (~300 baris × 1 request per baris) = 300 executions
- Kalau generate 3 SRT per hari = 900 executions → masih dalam free tier

## Troubleshooting

| Masalah | Solusi |
|---------|--------|
| HTTP 405 | Gunakan POST, bukan GET |
| HTTP 400 "Text required" | Body JSON harus ada field `text` |
| HTTP 502 "Edge TTS failed" | Microsoft rate limit, tunggu 1-2 menit |
| HTTP 500 function timeout | Function butuh <60 detik, text terlalu panjang (>5000 chars diblok) |
| Audio di-download tapi tidak bisa di-play | Cek file size — kalau 0 bytes, Microsoft reject |

## API Reference

### POST /api/edge-tts

**Request:**
```json
{
  "text": "Halo, selamat datang",
  "voice": "id-ID-GadisNeural",
  "rate": "+0%",
  "volume": "+0%",
  "pitch": "+0Hz"
}
```

**Response:** Binary MP3 audio (24kHz mono, 48kbps)

**CORS:** Open (`*`) — bisa dipanggil dari browser manapun

**Available voices:**
- `id-ID-GadisNeural` — Indonesia perempuan (default)
- `id-ID-ArdiNeural` — Indonesia laki-laki
- `en-US-AriaNeural`, `en-US-GuyNeural` — English US
- `en-AU-NatashaNeural` — English AU
- `zh-CN-XiaoxiaoNeural` — Mandarin
- `ja-JP-NanamiNeural` — Japanese
- `ko-KR-SunHiNeural` — Korean
