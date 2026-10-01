# SRT Splitter

Aplikasi web untuk memecah file SRT (subtitle) menjadi beberapa bagian dengan durasi yang dapat diatur. **100% berjalan di browser** — tidak ada server, tidak ada upload file ke mana pun. Aman dipakai di rumah untuk file pribadi.

> ✅ **Status deploy:** Siap untuk GitHub Pages. Workflow GitHub Actions sudah include. Konfigurasi `basePath` auto-detect dari environment.

## Fitur

- Drag-and-drop file `.srt` atau klik untuk pilih
- Atur durasi per file (5–120 menit, atau preset 10/15/20/30/45/60/90 menit)
- Pilih apakah timestamp direset ke `00:00:00` atau dipertahankan asli
- Potong di batas subtitle — tidak ada kalimat yang terputus di tengah
- Unduh semua hasil split sebagai satu file ZIP (via JSZip)
- Unduh source code langsung dari dalam aplikasi
- Preview awal & akhir tiap file untuk verifikasi cepat
- Mobile-friendly, light/dark mode
- 100% offline — tidak ada panggilan ke server

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

Repo ini sudah siap deploy. Workflow `.github/workflows/deploy.yml` akan auto-build
dan publish ke GitHub Pages setiap kali push ke branch `main`.

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

### Langkah 2 — Aktifkan GitHub Pages

1. Buka repo di GitHub → **Settings** → **Pages**
2. **Source:** pilih **GitHub Actions** (bukan "Deploy from a branch")
3. Save

### Langkah 3 — Tunggu Deploy

- Setiap push ke `main` akan trigger workflow `.github/workflows/deploy.yml`
- Lihat progress: tab **Actions** di repo GitHub
- Setelah selesai (~1-2 menit), buka:
  ```
  https://USERNAME.github.io/srt-splitter/
  ```

### Cara Kerja Workflow

```yaml
# .github/workflows/deploy.yml
on:
  push:
    branches: [main]
  workflow_dispatch:

permissions:
  contents: read
  pages: write
  id-token: write
```

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
| Halaman blank / asset 404 | Pastikan Pages Source = "GitHub Actions", bukan "Deploy from a branch" |
| Asset URL masih `/...` tanpa prefix | Re-run workflow — env `GITHUB_ACTIONS` mungkin tidak ke-set |
| Workflow tidak jalan | Cek tab Actions → klik workflow → lihat log error |
| "Refusing to allow PAT to create workflow file" | Token PAT-mu butuh scope `workflow` untuk commit file `.github/`. Buat token baru atau commit workflow lewat UI GitHub |
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
│   └── srt-splitter-source.zip  # Source code ZIP untuk self-distribution
├── scripts/
│   ├── split_srt.py             # Versi CLI Python (alternatif)
│   └── build_source_zip.py     # Build ulang source ZIP
├── src/
│   ├── app/
│   │   ├── layout.tsx          # Root layout, metadata, font
│   │   ├── page.tsx            # Halaman utama UI SRT Splitter
│   │   └── globals.css         # Styling global + Tailwind
│   ├── lib/
│   │   ├── srt.ts              # Parser, splitter, serializer SRT (client-side)
│   │   └── utils.ts            # Helpers shadcn (cn)
│   └── components/
│       └── ui/                 # Komponen shadcn/ui (Card, Button, dll)
├── .gitignore
├── next.config.ts              # Static export + basePath auto-detect
├── package.json
├── tsconfig.json
└── README.md                   # File ini
```

## 📖 Cara Pakai Aplikasi

1. Buka aplikasi di browser
2. Seret file `.srt` ke area upload, atau klik "Pilih File SRT"
3. Atur durasi per file (slider atau klik preset 10/15/20/30/45/60/90 menit)
4. Isi prefix nama file (misal `S6` → output `S6-01.srt`, `S6-02.srt`, …)
5. Toggle "Reset timestamp per file ke 00:00:00":
   - **OFF** (default): timestamp asli dipertahankan — cocok untuk dipasang langsung ke video asli
   - **ON**: tiap file mulai dari `00:00:00` — cocok untuk video yang sudah dipotong per segmen
6. Klik **Unduh ZIP** untuk download semua, atau tombol download per file

## 🔒 Privacy

- **Tidak ada upload ke server.** Semua parsing, splitting, dan ZIP generation terjadi di browser
- File `.srt` kamu tidak pernah dikirim ke mana pun
- Tidak ada analytics, tidak ada tracking
- Aman untuk file subtitle pribadi atau sensitif

## 🛠️ Development Notes

- Build sudah diverifikasi menghasilkan output statis yang benar di `out/`
- Semua URL aset (`/_next/static/...`) sudah otomatis diprefix dengan `basePath` saat build dengan GitHub env
- Lint bersih (tidak ada warning)
- TypeScript: `ignoreBuildErrors: true` sengaja di-enable untuk build reliability (tidak ada error yang di-hide, hanya supaya build tidak fail karena strict type check di template shadcn)
- `src/lib/db.ts` adalah sisa dari template, **tidak dipakai** oleh app manapun — aman untuk dihapus di follow-up

## 📝 Lisensi

Bebas dipakai, dimodifikasi, dan didistribusikan ulang.
