# SRT Splitter — Source Code

Aplikasi web untuk memecah file SRT (subtitle) menjadi beberapa bagian dengan durasi yang dapat diatur. 100% berjalan di browser, tanpa server, tanpa upload file ke mana pun.

## Fitur

- Drag-and-drop file `.srt`
- Atur durasi per file (5–120 menit, atau preset 10/15/20/30/45/60/90 menit)
- Pilih apakah timestamp direset ke `00:00:00` atau dipertahankan asli
- Potong di batas subtitle — tidak ada kalimat yang terputus
- Unduh semua sebagai satu file ZIP
- Preview awal & akhir tiap file
- Mobile-friendly, light/dark mode
- 100% offline — tidak ada panggilan ke server

## Stack Teknologi

- Next.js 16 (App Router, static export mode)
- TypeScript 5
- Tailwind CSS 4
- shadcn/ui (komponen UI)
- JSZip (untuk membuat ZIP di browser)
- Sonner (toast notifications)
- Lucide React (icons)

---

## Cara 1 — Run Lokal di MacBook

### Prasyarat
Install salah satu (cukup satu):
- [Node.js](https://nodejs.org/) v20+ (sudah include `npx`)
- atau [Bun](https://bun.sh/) — lebih cepat

```bash
# Pakai Homebrew (kalau belum punya bun)
brew install bun
# atau
brew install node
```

### Jalankan Dev Server
```bash
# 1. Buka folder source code
cd srt-splitter

# 2. Install dependencies
bun install
# atau: npm install

# 3. Jalankan dev server
bun run dev
# atau: npm run dev

# 4. Buka browser ke
# http://localhost:3000
```

### Build Static untuk Dipakai Lokal
```bash
bun run build
# Output ada di folder out/
# Lalu jalankan server statis:
cd out
python3 -m http.server 8080
# atau
npx serve
# Buka http://localhost:8080
```

---

## Cara 2 — Deploy ke GitHub Pages

### Langkah-langkah

1. **Buat repo baru di GitHub** (misal: `srt-splitter`).

2. **Push source code ke repo:**
```bash
cd srt-splitter
git init
git add .
git commit -m "Initial commit: SRT Splitter"
git branch -M main
git remote add origin https://github.com/USERNAME/srt-splitter.git
git push -u origin main
```

3. **Tambahkan workflow GitHub Actions.**
Buat file `.github/workflows/deploy.yml`:
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

4. **Edit `next.config.ts`** untuk GitHub Pages (kalau repo tidak di root domain):
```ts
// tambahkan basePath jika deploy ke https://USERNAME.github.io/srt-splitter/
const nextConfig: NextConfig = {
  output: "export",
  basePath: "/srt-splitter",  // ganti dengan nama repo
  images: { unoptimized: true },
  trailingSlash: true,
  // ...
};
```

5. **Aktifkan GitHub Pages:**
   - Buka repo → **Settings** → **Pages**
   - **Source:** pilih **GitHub Actions**
   - Tunggu workflow selesai, lalu buka URL `https://USERNAME.github.io/srt-splitter/`

---

## Cara 3 — Deploy Alternatif

### Netlify (paling mudah, drag-drop)
1. Jalankan `bun run build` lokal
2. Buka [Netlify Drop](https://app.netlify.com/drop)
3. Drag folder `out/` ke Netlify
4. Selesai — dapat URL publik

### Vercel
```bash
npm i -g vercel
vercel
# ikuti prompt, pilih "Next.js" sebagai framework
```

### Cloudflare Pages
- Push ke GitHub
- Buka Cloudflare Pages → Connect to Git
- Build command: `bun run build`
- Output directory: `out`

---

## Struktur Project

```
srt-splitter/
├── src/
│   ├── app/
│   │   ├── layout.tsx     # Root layout, font, metadata
│   │   ├── page.tsx       # Halaman utama UI SRT Splitter
│   │   └── globals.css    # Styling global + Tailwind
│   ├── lib/
│   │   ├── srt.ts         # Parser, splitter, serializer SRT (client-side)
│   │   └── utils.ts       # Helpers shadcn
│   └── components/
│       └── ui/            # Komponen shadcn/ui (Card, Button, dll)
├── next.config.ts         # Static export config
├── package.json
└── README.md              # File ini
```

## Cara Pakai Aplikasi

1. Buka aplikasi di browser.
2. Seret file `.srt` ke area upload, atau klik "Pilih File SRT".
3. Atur durasi per file (slider atau preset).
4. Isi prefix nama file (misal `S6` → `S6-01.srt`, `S6-02.srt`, …).
5. Toggle "Reset timestamp per file ke 00:00:00":
   - **OFF** (default): timestamp asli dipertahankan — cocok untuk video asli.
   - **ON**: tiap file mulai `00:00:00` — cocok untuk video yang sudah dipotong.
6. Klik "Unduh ZIP" untuk download semua, atau tombol download per file.

## Lisensi

Bebas dipakai, dimodifikasi, dan didistribusikan ulang.
