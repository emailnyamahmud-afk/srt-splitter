---
name: sejarah-script
description: >
  Generate naskah narasi + image prompts untuk konten sejarah (video 10-60 menit).
  User upload source sejarah (artikel, Wikipedia, buku) + topik tokoh/peristiwa.
  AI baca source, cari tambahan info (web search), generate 2 output:
  (1) naskah.txt — naskah narasi bahasa Indonesia (10-60 menit),
  (2) content-timestamps.json [{start, end, image_prompt, title}] — tiap 10 detik = 1 image prompt.
  Gunakan skill ini ketika user upload source sejarah dan minta "sejarah script",
  "bikin konten sejarah", "naskah sejarah", atau bahas konten edukasi sejarah.
---

# Skill: sejarah-script

## Tujuan

User mau bikin video konten sejarah (horizontal YouTube, 10-60 menit).
Video dibuat dari still images (Google Flow) + narasi TTS + Ken Burns effect.
User kasih source sejarah → AI generate naskah + image prompts.

## Input

User upload:
- **Source sejarah** (plain text, .txt) — artikel, Wikipedia, buku, atau ketik manual (WAJIB)
- **Topik** (di chat) — nama tokoh/peristiwa (mis. "Soekarno", "Perang Diponegoro")

## Yang AI Kerjakan

### 1. Baca Source + Cari Tambahan
- Baca source yang user upload
- Web search untuk tambahan info (kronologi, fakta penting, kutipan)
- Verifikasi fakta (jangan halu)

### 2. Generate naskah.txt
Naskah narasi konten sejarah, bahasa Indonesia, format plain text.

Struktur naskah:
```
[OPENING/HOOK]
Halo, kali ini kita bahas [topik]. Tahukah kamu bahwa [fakta menarik]?

[LATAR BELAKANG]
[topik dalam konteks sejarah, 1-2 paragraf]

[KRONOLOGI/PERISTIWA]
[urutan peristiwa penting, per paragraf]

[ANALISIS/DISKUSI]
[analisis singkat, dampak, relevansi masa kini]

[ penutup]
Sekian konten kali ini, sampai jumpa.
```

Aturan naskah:
- Bahasa Indonesia natural (kayak YouTuber edukasi, gak kaku)
- 1 narasi panjang (bukan per cue)
- Pisah per paragraf dengan double newline (\n\n)
- Target: 10 menit = ~1500 kata, 30 menit = ~4500 kata, 60 menit = ~9000 kata
- Sebut nama tokoh, tahun, tempat dengan jelas
- Beri opini/analisis (bukan cuma deskripsi)

### 3. Generate content-timestamps.json
Tiap 10 detik = 1 segment = 1 image prompt.

Format JSON array:
```json
[
  {"start": 0, "end": 10, "image_prompt": "Portrait of young Soekarno in 1940s, formal suit, black and white photography", "title": "Soekarno Muda"},
  {"start": 10, "end": 20, "image_prompt": "Indonesian independence proclamation ceremony, 1945, crowd cheering", "title": "Proklamasi"},
  {"start": 20, "end": 30, "image_prompt": "Map of Indonesia showing Jakarta, historical style", "title": "Jakarta 1945"},
  ...
]
```

Aturan JSON:
- `start`, `end`: detik (float) — tiap 10 detik, naik berurutan
- `image_prompt`: prompt untuk Google Flow (deskripsi visual, bahasa English lebih baik)
- `title`: judul singkat segment (muncul sebagai text overlay di video)
- Total durasi harus cocok dengan durasi naskah (estimasi: 150 kata/menit)
- 10 menit = ~60 segments, 30 menit = ~180 segments, 60 menit = ~360 segments

### 4. Image Prompt Strategy
- Portrait tokoh: "[nama], [era], [deskripsi pakaian], [style photography]"
- Adegan peristiwa: "[peristiwa], [tahun], [lokasi], [style]"
- Peta/infografis: "Map of [lokasi], [era], [style]"
- Kutipan: "[tokoh], [pose], [background]"
- Variasi style: "oil painting", "watercolor", "historical photograph", "cinematic"
- Hindari: text dalam image, wajah tokoh yang gak akurat (pakai silhouette/back view kalau ragu)

## Output

AI generate 2 file:
1. `content-naskah.txt` — naskah narasi (untuk edge-tui v7.5 narration mode)
2. `content-timestamps.json` — image prompts + timestamps (untuk konten-tui.py + Google Flow)

## Yang TIDAK Dilakukan

- Tidak generate video (itu tugas konten-tui.py)
- Tidak generate TTS (itu tugas edge-tui v7.5)
- Tidak generate images (itu tugas Google Flow)
- Tidak halu (jangan ada fakta yang dibuat-buat)
