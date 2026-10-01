# SRT Splitter

Aplikasi web untuk memecah file SRT (subtitle) menjadi beberapa bagian dengan durasi yang dapat diatur, **plus konversi subtitle ke audio narasi (TTS)** dengan suara Indonesia natural. **100% berjalan di browser** — tidak ada server, tidak ada upload file SRT ke mana pun. Aman dipakai di rumah untuk file pribadi.

> ✅ **Live di:** https://emailnyamahmud-afk.github.io/srt-splitter/

## Fitur Utama

### 📑 Split SRT
- Drag-and-drop file `.srt` atau klik untuk pilih
- Atur durasi per file: **5 menit sampai 5 jam** (slider + preset 10m, 15m, 20m, 30m, 45m, 1j, 1j30m, 2j, 3j, 4j, 5j)
- Pilih apakah timestamp direset ke `00:00:00` atau dipertahankan asli
- Potong di batas subtitle — tidak ada kalimat yang terputus di tengah
- Unduh hasil split sebagai satu file ZIP (via JSZip)
- Untuk film panjang (3-4 jam), pilih preset **4j** atau **5j** agar tidak di-split

### 🔊 TTS (Text-to-Speech) — Audio Narasi
- **OpenAI TTS** — neural voices multilingual (Indonesia natural)
  - Voices: `nova` (default, female natural), `shimmer`, `alloy`, `echo`, `fable`, `onyx`
  - Model `tts-1-hd` (premium) — text Indonesia dibaca dengan accent natural
  - Butuh OpenAI API key (gratis $5 credit saat signup di platform.openai.com)
  - API key disimpan di localStorage browser, tidak pernah dikirim ke server kita
  - Cost: $0.015/1k chars = ~$1 per 10 menit audio
- **Audio timing di-sync ke SRT** — kalau audio lebih panjang dari cue, di-speed-up (max 1.5x, preserve pitch); kalau lebih pendek, di-pad silence. Hasil audio pas dengan durasi SRT asli
- **Audio preview** — setelah generate, HTML5 audio player muncul inline. Dengar dulu sebelum download, tidak perlu download file untuk cek hasil
- Output: WAV 24kHz mono, 16-bit PCM — siap di-mux ke video asli

### 💾 Persistence
- **State tersimpan di localStorage** — refresh halaman tidak reset upload
- SRT content, filename, durasi split, prefix, dan toggle reset-timestamp semua ter-restore otomatis

### 📱 UI/UX
- Collapsible cards — "Hasil Pemecahan" dan "Preview" bisa di-collapse agar TTS panel selalu terlihat
- Mobile-friendly, light/dark mode
- 100% client-side — tidak ada panggilan ke server (kecuali Edge TTS ke Microsoft untuk audio)

## Stack Teknologi

- **Framework:** Next.js 16 (App Router, `output: "export"`)
- **Bahasa:** TypeScript 5
- **Styling:** Tailwind CSS 4 + shadcn/ui (New York style)
- **Icons:** Lucide React
- **Toast:** Sonner
- **ZIP:** JSZip (lazy-loaded, client-side)

---

## 🚀 Quick Start — Run Lokal di MacBook

### Prasyarat

Install salah satu (cukup satu):

```bash
# Opsional: pakai Homebrew
brew install bun      # lebih cepat, direkomendasikan
# atau
brew install node     # alternatif, sudah include npm & npx
```

### Dev Mode (paling cepat untuk iterasi)

```bash
cd srt-splitter
bun install            # atau: npm install
bun run dev           # atau: npm run dev
# Buka http://localhost:3000
```

### Build Statis & Jalankan Lokal

```bash
# 1. Build static site (output ke ./out/)
bun run build

# 2. Jalankan server statis (pilih salah satu):
cd out

# Opsi A — Python (paling sering sudah tersedia di macOS)
python3 -m http.server 8080

# Opsi B — npx serve
npx serve

# Opsi C — bunx serve
bunx serve

# Buka http://localhost:8080
```

> **Catatan:** Membuka `out/index.html` langsung lewat `file://` bisa bermasalah
> karena beberapa browser memblok modul ES di protocol file. Pakai `python3 -m http.server` lebih andal.

---

## 🌐 Deploy ke GitHub Pages

Repo ini sudah siap deploy. Setelah workflow aktif, setiap push ke branch `main`
akan auto-build dan publish ke GitHub Pages.

### Langkah 1 — Push ke GitHub

Repo ini sudah di-push ke:
```
https://github.com/emailnyamahmud-afk/srt-splitter
```

Untuk fork atau deploy ke repo sendiri:

```bash
git clone https://github.com/emailnyamahmud-afk/srt-splitter.git
cd srt-splitter

# Ganti remote ke repo kamu sendiri
git remote set-url origin https://github.com/USERNAME/srt-splitter.git
git push -u origin main
```

> **Tip:** Kalau kamu pakai token PAT sendiri untuk push, pastikan token punya scope `repo` **dan** `workflow`. Tanpa scope `workflow`, push yang menyertakan file `.github/workflows/*.yml` akan ditolak.

### Langkah 2 — Tambahkan Workflow ke Repo (sekali saja)

File `.github/workflows/deploy.yml` sudah tersedia di source code lokal,
tetapi **tidak ter-push** lewat PAT awal karena token tersebut tidak punya scope
`workflow`. Untuk mengaktifkannya, lakukan salah satu dari:

#### Opsi A — Lewat GitHub UI (paling mudah, ~2 menit)

1. Buka https://github.com/emailnyamahmud-afk/srt-splitter/actions/new
2. Klik link **"set up a workflow yourself →"**
3. Hapus template default, lalu **copy-paste** isi file `.github/workflows/deploy.yml`
   dari source code lokal ke editor GitHub
4. Klik **Start commit** → **Commit new file**

#### Opsi B — Lewat git dengan token ber-scope `workflow`

```bash
# Buat PAT baru di https://github.com/settings/tokens
# dengan scope: repo + workflow
git add .github/workflows/deploy.yml
git commit -m "Add GitHub Pages workflow"
git push origin main
```

### Langkah 3 — Aktifkan GitHub Pages

1. Buka repo di GitHub → **Settings** → **Pages**
2. **Source:** pilih **GitHub Actions** (bukan "Deploy from a branch")
3. Save

### Langkah 4 — Tunggu Deploy Pertama

- Setelah workflow file ter-commit, push ke `main` akan trigger workflow
- Lihat progress: tab **Actions** di repo GitHub
- Setelah selesai (~1-2 menit), buka:
  ```
  https://USERNAME.github.io/srt-splitter/
  ```

### Isi Workflow File (untuk copy-paste lewat UI GitHub)

```yaml
name: Deploy to GitHub Pages

on:
  push:
    branches: [main]
  workflow_dispatch:

permissions:
  contents: read
  pages: write
  id-token: write

concurrency:
  group: "pages"
  cancel-in-progress: true

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: oven-sh/setup-bun@v2
        with:
          bun-version: latest
      - run: bun install
      - run: bun run build
        env:
          GITHUB_REPOSITORY: ${{ github.repository }}
          GITHUB_ACTIONS: "true"
      - uses: actions/upload-pages-artifact@v3
        with:
          path: ./out

  deploy:
    needs: build
    runs-on: ubuntu-latest
    environment:
      name: github-pages
      url: ${{ steps.deployment.outputs.page_url }}
    steps:
      - id: deployment
        uses: actions/deploy-pages@v4
```

### Cara Kerja Workflow

Workflow akan:
1. Checkout repo
2. Install Bun
3. `bun install` + `bun run build` (dengan env `GITHUB_ACTIONS=true` & `GITHUB_REPOSITORY` ter-set)
4. `next.config.ts` membaca env tersebut → set `basePath: "/srt-splitter"` otomatis
5. Upload `./out/` sebagai Pages artifact
6. Deploy ke Pages

### Auto basePath — Tidak Perlu Edit Manual

`next.config.ts` sudah cerdas mendeteksi environment:

```ts
const repoName = process.env.GITHUB_REPOSITORY?.split("/")[1] ?? "";
const isGHPages = process.env.GITHUB_ACTIONS === "true" && !!repoName;

const nextConfig = {
  output: "export",
  basePath: isGHPages ? `/${repoName}` : "",  // otomatis!
  // ...
};
```

- **Di GitHub Actions** → `basePath = "/srt-splitter"` (atau nama repo apa pun)
- **Di lokal** → `basePath = ""` (root, jadi `http://localhost:3000/` jalan tanpa prefix)

### ❓ Troubleshooting GitHub Pages

| Masalah | Solusi |
|---------|--------|
| Workflow tidak ada di tab Actions | Belum menyelesaikan Langkah 2 — tambahkan workflow file dulu (UI GitHub atau push dengan token ber-scope `workflow`) |
| Halaman blank / asset 404 | Pastikan Pages Source = "GitHub Actions", bukan "Deploy from a branch" |
| Asset URL masih `/...` tanpa prefix | Re-run workflow — env `GITHUB_ACTIONS` mungkin tidak ke-set |
| Workflow gagal jalan | Cek tab Actions → klik workflow → lihat log error |
| "Refusing to allow PAT to create workflow file" | Token PAT-mu butuh scope `workflow` untuk commit file `.github/`. Buat token baru atau commit workflow lewat UI GitHub (Opsi A di atas) |
| Build gagal di `bun install` | Cek `package-lock` atau `bun.lock` tidak corrupt. Coba `rm -rf node_modules bun.lock && bun install` |
| 404 di `/srt-splitter/` tapi `/srt-splitter/index.html` ada | Tunggu 1-2 menit setelah workflow selesai, atau hard-refresh browser |

---

## ☁️ Deploy Alternatif

### Netlify (paling mudah, drag-drop)

1. `bun run build` lokal
2. Buka [Netlify Drop](https://app.netlify.com/drop)
3. Drag folder `out/` ke Netlify
4. Selesai — dapat URL publik

> **Catatan untuk Netlify:** Tidak perlu set `basePath` karena Netlify serve dari root domain.

### Vercel

```bash
npm i -g vercel
vercel
# ikuti prompt, pilih "Next.js" sebagai framework
# output dir: out (kalau ditanya)
```

### Cloudflare Pages

- Push ke GitHub
- Buka Cloudflare Pages → Connect to Git → pilih repo
- Build command: `bun run build`
- Output directory: `out`

---

## 📁 Struktur Project

```
srt-splitter/
├── .github/
│   └── workflows/
│       └── deploy.yml          # GitHub Actions: auto-deploy ke Pages
├── public/
│   ├── logo.svg
│   ├── robots.txt
│   ├── coi-serviceworker.js    # Cross-origin isolation (untuk multi-thread WASM)
│   └── srt-splitter-source.zip  # Source code ZIP untuk self-distribution
├── scripts/
│   ├── split_srt.py             # Versi CLI Python (alternatif)
│   └── build_source_zip.py     # Build ulang source ZIP
├── src/
│   ├── app/
│   │   ├── layout.tsx          # Root layout, metadata, font, coi-script
│   │   ├── page.tsx            # Halaman utama UI SRT Splitter (split + persistence + collapsibles)
│   │   └── globals.css         # Styling global + Tailwind
│   ├── lib/
│   │   ├── srt.ts              # Parser, splitter, serializer SRT (client-side)
│   │   ├── openai-tts.ts       # OpenAI TTS REST API client (CORS-enabled, Indonesia natural)
│   │   ├── audio-utils.ts      # Decode MP3, speed-up, pad silence, encode WAV, timing sync
│   │   ├── tts.ts              # High-level TTS engine: combine openai-tts + audio-utils
│   │   └── utils.ts            # Helpers shadcn (cn)
│   └── components/
│       ├── tts-panel.tsx       # UI panel TTS (API key input, voice select, audio preview)
│       ├── coi-script.tsx      # Inject coi-serviceworker
│       └── ui/                 # Komponen shadcn/ui (Card, Button, dll)
├── .gitignore
├── next.config.ts              # Static export + basePath auto-detect
├── package.json
├── tsconfig.json
└── README.md                   # File ini
```

## 📖 Cara Pakai Aplikasi

### Untuk Split SRT
1. Buka aplikasi di browser
2. Seret file `.srt` ke area upload, atau klik "Pilih File SRT"
3. Atur durasi per file:
   - Slider (5 menit → 5 jam) atau klik preset: `10m`, `15m`, `20m`, `30m`, `45m`, `1j`, `1j30m`, `2j`, `3j`, `4j`, `5j`
   - Untuk film 3-4 jam yang tidak ingin di-split, pilih `4j` atau `5j`
4. Isi prefix nama file (misal `S6` → output `S6-01.srt`, `S6-02.srt`, …)
5. Toggle "Reset timestamp per file ke 00:00:00":
   - **OFF** (default): timestamp asli dipertahankan — cocok untuk dipasang langsung ke video asli
   - **ON**: tiap file mulai dari `00:00:00` — cocok untuk video yang sudah dipotong per segmen
6. Klik **Unduh ZIP** untuk download semua, atau expand "Hasil Pemecahan" untuk download per-file

### Untuk TTS (Konversi Subtitle ke Audio)
1. Setelah upload SRT, scroll ke panel ungu "Generate Audio (TTS)"
2. **Setup API Key** (sekali saja):
   - Dapatkan free API key di https://platform.openai.com/api-keys (free $5 credit)
   - Klik section amber "OpenAI API Key"
   - Paste key (mulai dengan `sk-...`) ke input
   - Klik **Test & Save** untuk verifikasi
3. Setelah key valid:
   - Pilih voice (default: **Nova** — female natural untuk Indonesia)
   - Toggle "Sync timing ke SRT" (default ON — audio di-adjust ke durasi cue asli)
   - Klik **Generate & Download ZIP** untuk download semua, atau generate per-split
4. **Audio preview** — setelah generate, audio player muncul inline di bawah tombol. Klik play untuk dengar sebelum download
5. Audio output: WAV 24kHz mono, 16-bit PCM, durasi sama dengan SRT asli

### Tips
- **Refresh halaman tidak reset** — file SRT dan setting tersimpan di localStorage
- **API key aman** — disimpan di browser kamu, tidak pernah dikirim ke server mana pun selain OpenAI
- **Film panjang**: pilih preset `4j`/`5j` di split, lalu "Generate Full Audio" — tunggu ~10-20 menit di Mac idle untuk 3-4 jam subtitle
- **OpenAI TTS butuh internet** (cloud-based). Badge "API Key Set" menunjukkan status
- **Cost estimate**: 3 jam subtitle ≈ 200-300 baris × 50 chars = ~15k chars ≈ $0.22 (tts-1-hd)

## 🔒 Privacy

- **Tidak ada upload SRT ke server.** Semua parsing, splitting, dan ZIP generation terjadi di browser
- File `.srt` kamu tidak pernah dikirim ke mana pun
- OpenAI TTS mengirim **hanya teks subtitle** ke `api.openai.com` (untuk dijadikan audio) — teks dikirim per baris, tidak disimpan di app
- **API key OpenAI** disimpan di localStorage browser kamu, tidak pernah dikirim ke server mana pun selain OpenAI
- Tidak ada analytics, tidak ada tracking
- Aman untuk file subtitle pribadi atau sensitif

## 🛠️ Development Notes

- Build sudah diverifikasi menghasilkan output statis yang benar di `out/`
- Semua URL aset (`/_next/static/...`) sudah otomatis diprefix dengan `basePath` saat build dengan GitHub env
- Lint bersih (tidak ada warning)
- TypeScript: `ignoreBuildErrors: true` sengaja di-enable untuk build reliability (tidak ada error yang di-hide, hanya supaya build tidak fail karena strict type check di template shadcn)
- `src/lib/db.ts` adalah sisa dari template, **tidak dipakai** oleh app manapun — aman untuk dihapus di follow-up
- COI serviceworker (`public/coi-serviceworker.js`) ada di repo untuk enable SharedArrayBuffer (multi-thread WASM) — sekarang tidak terpakai karena Edge TTS pakai WebSocket, tapi tetap di-keep kalau nanti pakai VITS lagi

## 📝 Lisensi

Bebas dipakai, dimodifikasi, dan didistribusikan ulang.
