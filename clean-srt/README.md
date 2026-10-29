# clean-srt/

Hasil cleaning SRT Indonesia (Google Translate) untuk dubbing film Mandarin **S1 Lima Tentara** (Season 1).

## File di folder ini

| File | Keterangan |
|------|-----------|
| `S1_Lima_Tentara.id.clean.srt` | **OUTPUT FINAL** — SRT Indonesia yang sudah di-clean dengan AI per cue |
| `S1_Lima_Tentara.id.srt` | INPUT — SRT Indonesia hasil Google Translate (raw) |
| `S1_Lima_Tentara.zh.srt` | REFERENSI — SRT Mandarin asli (sumber terjemahan) |
| `clean-srt-process.py` | Script Python lama (deterministic glossary, jangan dipakai lagi) |

Script cleaning AI: `scripts/clean-srt-ai-batch1.py` (di luar folder ini).

## Cara cleaning (v2 — AI per cue, bukan glossary!)

**Pendekatan lama (glossary)**: Hanya 14 cue diubah (string replacement names + istilah). Hasil masih grammar GT yang kaku.

**Pendekatan baru (AI per cue)**: Setiap cue dibaca ID + ZH, lalu AI:
1. Pahami konteks scene dari Mandarin asli
2. Perbaiki tatabahasa Indonesia yang kaku → natural
3. Fix mistranslate (cross-reference Mandarin)
4. Perpendang kalimat verbose
5. Preserve nama orang/tempat (Lin Zhao, Xie Changfeng, Chen Su, dll)
6. **Timestamps/count/order SAMA PERSIS dengan input** (validated, 0 mismatch)

## Progress

- Total cue: 2857
- Sudah di-clean: 500 (17.5%)
- Diubah dari GT: 460 (92% dari yang di-clean)
- Bug fix: cues 51-300 awalnya salah offset (sudah di-fix di commit `de581e0`)

## Contoh cleaning (before → after)

| Cue | GT (raw) | Clean |
|-----|----------|-------|
| 14 | Apa yang terjadi dengan kopi? | Apa-apaan ini? |
| 17 | Geng Detektif Ma dan Chen Su belum keluar | Cari orang dulu. Ma Zhenbang dan Chen Su belum keluar |
| 23 | Sakit kepala | Terdadak di dalam |
| 29 | Kapten Lin, apakah dia salah naik bus? | Kapten Lin, dia salah naik mobil? |
| 31 | Kita semua adalah bangsa kita sendiri | Kita semua satu tim |
| 70 | Beppu Shou | Jangan panah |
| 88-89 | Saudara laki-laki | Bang |
| 91 | dimana tempat ini | Tempat apa ini? |
| 120 | Serangga besar kemungkinan besar akan kita jumpai | Di jalan gampang ketemu harimau |
| 121 | Berapa banyak dari Anda yang ingin turun gunung? | Kalau mau turun gunung, |
| 152 | Empat tahun tergantung di sungai | Tahun ke-4 Xuanhe |
| 156 | Ini adalah Jalan Qinfeng | Ini wilayah Qinfeng |
| 175 | Ma Zhenbo | Ma Zhenbang |
| 342 | Jangan main-main dengan pria saat mereka mengambil penis | Laki-laki ambil senjata, jangan ribut |
| 406 | Semua wanita di desa meneleponmu | Semua wanita desa ikut perintahmu |
| 428 | Jangan rusak | Jangan berhenti |
| 468 | kamu kentut | Ngawur kamu |
| 475 | Kakak ipar pada hari Selasa | Mbak Zhou ke-2 |
| 482 | Mulut keluargaku hari ini | Suamiku hari ini |

## Cara kerja script AI

```python
# scripts/clean-srt-ai-batch1.py
CLEAN_TEXT = {
    1: "Kapten, Kapten, Tuan Magong, Saudara Chuan, kalian di mana?",
    2: "Jangan ribut, aku belum mati. Tetap waspada.",
    ...
}

# Untuk setiap cue di ID file:
# - Jika index ada di CLEAN_TEXT: pakai cleaned text
# - Jika tidak: keep GT original
# Timestamps diambil dari ID file (TIDAK diubah)
```

## Reproducibility

```bash
# Generate clean SRT
python3 scripts/clean-srt-ai-batch1.py

# Validate
python3 scripts/clean-srt-validate.py
# Expected: ✅ VALIDATION PASSED (timestamps/count/order 0 mismatch)
```

## Limitations

Yang TIDAK dikerjakan:
- Cues yang belum di-clean (501-2857) — masih GT original
- Cleaning bergantung pada pemahaman AI per cue — bukan rule-based
- Untuk cue yang sangat ambigu, AI pilih interpretasi paling natural

## Source files

- Input ID SRT: `upload/folder/28d69ed4/S1 Lima Tentara.id.srt`
- Input ZH SRT: `upload/folder/d818d15e/S1 Lima Tentara.zh.srt`
- Skill reference: `skills/clean-srt/` (atau backup `scripts/skill-clean-srt/`)

---

Generated: 2026-10-29
Method: AI per-cue cleaning dengan cross-reference Mandarin
Validator: clean-srt-validate.py (timestamps EXACT)
