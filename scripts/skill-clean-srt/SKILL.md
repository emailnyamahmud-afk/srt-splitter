---
name: clean-srt
description: >
  Clean dan rapikan SRT hasil Google Translate (Indonesia) untuk dubbing film Mandarin.
  Perbaiki tatabahasa, preserve nama orang/tempat, perpendang kalimat verbose,
  fix mistranslate, dan pastikan timestamps SAMA PERSIS dengan input.
  Gunakan skill ini ketika user upload file .srt dan minta "clean srt",
  "rapikan srt", "perbaiki terjemahan srt", atau bahas perbaikan subtitle.
---

# Skill: clean-srt

## Tujuan

User punya SRT Indonesia hasil Google Translate (sering ngawur: "cumming" → "menarik pelatuk",
"payung emas" → "obat luka emas", "Tentara Hunan" → "Xiangjun", dll).
Skill ini membersihkan SRT tersebut agar layak untuk dubbing Indonesia.

## Aturan MUTLAK (DILARANG DILANGGAR)

1. **Timestamps WAJIB sama persis dengan input** — jangan ubah 1ms pun
2. **Jumlah cue WAJIB sama** — jangan tambah/hapus/gabung cue
3. **Urutan cue WAJIB sama** — jangan reorder
4. **Format SRT WAJIB valid** — index, timestamp (`HH:MM:SS,mmm --> HH:MM:SS,mmm`), text, blank line

Jika AI ragu tentang suatu perubahan, LEAVE IT AS IS (keep GT terjemahan asli).
Lebih baik tidak berubah daripada berubah jadi salah.

## Input

User upload 1-2 file SRT:
- **SRT Indonesia** (hasil Google Translate) — WAJIB, ini yang di-clean
- **SRT Mandarin** (opsional, referensi sumber) — untuk verifikasi konteks

## Yang AI Kerjakan per Cue

### 1. Fix Tatabahasa Indonesia
- Subjek-predikat-objek yang rusak → perbaiki
- Kalimat literal/kaku → buat natural
- Contoh: "Tidak dapat dikatakan bahwa dia tidak mau" → "Dia tidak mau"

### 2. Preserve Nama Orang
Lihat `references/glossary-names.md` untuk daftar lengkap.
Nama yang HARUS dipertahankan (jangan diterjemahkan/disingkat):
- Lin Zhao (林昭) — karakter utama
- Xie Changfeng (谢长风) — komandan
- Wang Haochuan (王浩川) — ahli strategi
- Ma Zhenbang (马振邦) — ahli senjata
- Chen Su (陈素) — dokter perempuan
- Qin Hongying (秦红樱) — pejuang perempuan
- Mu En (慕恩) — mantan inspektur
- Li Kui (李奎) — prajurit
- Zhou Lizheng (周里正) — tetua desa

Jika nama muncul dengan variasi (mis. "Hongying" / "Elang Merah" / "Red Eagle"),
standarisasi ke bentuk canonical (lihat glossary).

### 3. Preserve Nama Tempat
Lihat `references/glossary-names.md` untuk daftar lengkap.
Tempat yang HARUS dipertahankan:
- Qinghe Village (青禾村) — desa utama
- Longcheng (龙城) — kota/kabupaten
- Qinzhou (秦州) — wilayah
- Qin family (秦家) — keluarga bangsawan
- Beijing (北京) — ibu kota

### 4. Fix Mistranslate Jelas
Contoh mistranslate yang HARUS diperbaiki:
- "payung emas" → "obat luka emas" (金创药, jin chuang yao)
- "ayam panah" → "panah otomatis" (机弩, ji nu — crossbow)
- "cumming" → "menarik pelatuk" (扣, kou — trigger)
- "Tentara Hunan" → "Xiangjun" (乡军 — bukan Provinsi Hunan)
- "Bulan" (sebagai nama orang) → "Mu En" (慕恩)
- "peti mati Lin" → "Lin Zhao" (押司 ≠ peti mati)
- "dot polisi" → "Jiedushi" (节度使 — Komisaris Militer)
- "menggoreng permen" → "laras meledak" (炸膛)
- "retribusi" → "pembalasan" (retribution ≠ retribusi/pungutan)

### 5. Perpendang Kalimat Verbose
GT sering bikin kalimat berbelit-belit. Perpendang tanpa mengubah makna:
- "Pada saat ini sekarang" → "Sekarang"
- "Tidak dapat dikatakan bahwa hal tersebut tidak mungkin" → "Tidak mustahil"
- "Adapun mengenai hal tersebut" → "Soal itu"

### 6. Konteks Scene
Pakai SRT Mandarin (jika ada) untuk verifikasi konteks:
- Cue yang ambigu di Indonesia → cek Mandarin asli
- Jika AI tidak bisa verifikasi → keep GT asli (jangan halu)

### 7. Jangan HALLUCINATE
- Jika ragu → keep terjemahan GT asli
- Jangan tambah info yang tidak ada di SRT
- Jangan hapus info yang ada di SRT
- Jangan ubah makna kalimat

## Output Format

SRT valid dengan format:
```
1
00:00:04,559 --> 00:00:05,960
Lebih stabil untuk masuk melalui pintu barat

2
00:00:05,960 --> 00:00:06,759
Hanya ada sedikit orang di sana
```

Timestamps WAJIB sama persis dengan input.
Cue count WAJIB sama.
Urutan WAJIB sama.

## Cara Kerja

1. Parse input SRT → list cue (index, start, end, text)
2. Untuk setiap cue:
   a. Baca text Indonesia (hasil GT)
   b. Jika ada SRT Mandarin: baca cue yang sama (match by index) untuk konteks
   c. Apply cleaning rules (grammar, names, mistranslate, shorten)
   d. Keep timestamp EXACTLY as-is
3. Output SRT clean dengan format valid

## Jika SRT Terlalu Panjang

Jika SRT > 500 cue:
- Proses per batch 100-200 cue
- Output per batch sebagai file terpisah (part-1.srt, part-2.srt, dst)
- Atau output inline per batch dalam chat
- User bisa merge manual atau pakai `cat part-*.srt > clean.srt`

## Yang TIDAK Dilakukan

- Tidak translate dari Mandarin ke Indonesia (itu tugas GT)
- Tidak generate SRT dari audio (itu tugas whisper-tui)
- Tidak generate TTS audio (itu tugas edge-tts-tui)
- Tidak mix video (itu tugas mix-tui)
- Tidak ubah timestamps
- Tidak tambah/hapus cue
- Tidak ubah urutan cue
