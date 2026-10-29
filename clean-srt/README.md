# clean-srt/

Hasil cleaning SRT Indonesia (Google Translate) untuk dubbing film Mandarin **S1 Lima Tentara** (Season 1).

## File di folder ini

| File | Ukuran | Keterangan |
|------|--------|-----------|
| `S1_Lima_Tentara.id.clean.srt` | ~186 KB | **OUTPUT FINAL** — SRT Indonesia yang sudah di-clean, siap untuk dubbing |
| `S1_Lima_Tentara.id.srt` | ~186 KB | INPUT — SRT Indonesia hasil Google Translate (raw) |
| `S1_Lima_Tentara.zh.srt` | ~152 KB | REFERENSI — SRT Mandarin asli (sumber terjemahan) |
| `clean-srt-process.py` | ~6.5 KB | Script Python yang melakukan cleaning deterministic |

## Statistik

- **Total cue**: 2857
- **Cue diubah**: 14 (0.49%) — hanya cue dengan mistranslate/name yang terdeteksi otomatis
- **Timestamps**: SAMA PERSIS dengan input (validated, 0 mismatch)
- **Cue count**: SAMA (2857 = 2857, validated)
- **Urutan cue**: SAMA (validated)

## Apa yang di-clean (deterministic, oleh script)

### 1. Standardisasi nama orang (variants → canonical)

| Original (GT) | Cleaned |
|---------------|---------|
| Nona Chen | Chen Su |
| Nyonya Chen | Chen Su |
| Dokter Chen | Chen Su |
| Saudari Chen Su | Chen Su |
| Chen Xinlang | Chen Su |
| Elang Merah / Red Eagle | Qin Hongying |
| Aokawa | Wang Haochuan |
| Marco / Ma Zhenzhuang | Ma Zhenbang |
| Peti mati Lin / Lin Yanya / Lin Yasi / Lin Zhou | Lin Zhao |
| Xie Zangfeng / Xie Chaojin / Xie Dutou / Pelatih Xie | Xie Changfeng |
| Bulan (sebagai nama, bukan bulan/moon) | Mu En |
| Zhou Laozhang / Zhou Lao / Paman Zhou | Zhou Lizheng |
| Butler Yao / Yao Gu / Yao Dadu / Yao Zhong | Yao Sihai |
| Qin Fengzhan / Qin Fengjun | Qin Fenglu |

### 2. Fix mistranslate jelas

| Original (GT) | Cleaned | Mandarin | Note |
|---------------|---------|----------|------|
| cumming / melakukan cumming | menarik pelatuk | 扣 (kou) | trigger |
| payung emas / payung tempat tidur emas | obat luka emas | 金创药 | jin chuang yao |
| ayam panah / ayam panah otomatis | panah otomatis | 机弩 | ji nu (crossbow) |
| Tentara Hunan / tentara utang / pemberontak debitur | Xiangjun | 乡军 | bukan Provinsi Hunan |
| dot polisi / Qin Fenglu dot | Jiedushi | 节度使 | Komisaris Militer |
| menggoreng permen | laras meledak | 炸膛 | zha tang |
| retribusi | pembalasan | retribution | bukan "pungutan" |
| universitas terkemuka / SMP Desa | akademi | — | — |

### 3. Bulan → Mu En (context-aware)

Script hanya mengganti "Bulan" menjadi "Mu En" jika:
- Bukan diikuti nama bulan (Januari, Februari, ..., Desember)
- Bukan diikuti kata terkait moon (purnama, sabit, terang, gelap, mati, baru)
- Bukan didahului kata waktu (tiap, setiap, dalam, pada, di)

## Cara kerja script

```bash
python clean-srt-process.py
```

Script akan:
1. Parse input `S1_Lima_Tentara.id.srt` → 2857 cue (index, start, end, text)
2. Untuk setiap cue, apply replacement glossary (case-insensitive)
3. Apply context-aware "Bulan" → "Mu En" (hanya jika name, bukan month/moon)
4. Validate: timestamps/count/order SAMA PERSIS dengan input
5. Output `S1_Lima_Tentara.id.clean.srt`

## Limitations (yang TIDAK dikerjakan script)

Script ini hanya **deterministic replacements** — dia mengenali pattern spesifik dari glossary. Yang TIDAK dikerjakan:

1. **Perbaikan tatabahasa Indonesia** — kalimat kaku/verbose GT tetap apa adanya
   - Contoh tidak diperbaiki: "Aku bahkan tidak bisa membiarkan tanganku tetap berada di setir"
2. **Perpendang kalimat verbose** — kalimat berbelit-belit tetap panjang
3. **Konteks scene verification** — script tidak cross-check dengan Mandarin untuk cue ambigu
4. **Fix mistranslate baru** — hanya mistranslate yang sudah di-catalog di glossary yang diperbaiki
5. **Nama baru** — hanya nama yang sudah di glossary yang distandardisasi

Untuk cleaning lebih dalam (grammar, verbose, konteks), perlu manual review per cue oleh AI/human. Skill `clean-srt` di Z.ai bisa dipakai untuk itu, tapi untuk 2857 cue, batch processing deterministic ini adalah baseline yang reliable.

## Reproducibility

```bash
# Dari root repo
python clean-srt/clean-srt-process.py
# Output: download/S1_Lima_Tentara.id.clean.srt
```

Untuk validasi:
```bash
python scripts/clean-srt-validate.py
# Harus output: ✅ VALIDATION PASSED
```

## Source files

- Input ID SRT: `upload/folder/28d69ed4/S1 Lima Tentara.id.srt` (user upload via Z.ai cloud)
- Input ZH SRT: `upload/folder/d818d15e/S1 Lima Tentara.zh.srt` (user upload via Z.ai cloud)
- Skill reference: `skills/clean-srt/` (atau backup `scripts/skill-clean-srt/`)

---

Generated: 2026-10-29
Cleaner: clean-srt-process.py v1.0 (deterministic glossary replacement)
Validator: clean-srt-validate.py
