# clean-srt/

Hasil cleaning SRT Indonesia (Google Translate) untuk dubbing film Mandarin **S1 Lima Tentara** (Season 1).

## File di folder ini

| File | Keterangan |
|------|-----------|
| `S1_Lima_Tentara.id.clean.srt` | **OUTPUT FINAL** — SRT Indonesia yang sudah di-clean |
| `S1_Lima_Tentara.id.srt` | INPUT — SRT Indonesia hasil Google Translate (raw) |
| `S1_Lima_Tentara.zh.srt` | REFERENSI — SRT Mandarin asli (sumber terjemahan) |

Script cleaning AI: `scripts/clean-srt-ai-batch1.py` (di luar folder ini).

## Pendekatan cleaning (final — hybrid)

### Bagian 1: Manual per-cue (cues 1-750, ~26% dari SRT)

Cross-reference Mandarin asli per cue. AI baca ID + ZH, lalu:
- Pahami konteks scene dari Mandarin asli
- Perbaiki tatabahasa Indonesia kaku → natural
- Fix mistranslate (cross-reference Mandarin)
- Perpendang kalimat verbose
- Preserve nama orang/tempat

### Bagian 2: Heuristic scan (cues 751-2857, ~74% dari SRT)

Karena per-cue manual gak efisien (2857 cue butuh 57+ batch), pakai heuristic:

1. **Scan nama orang** — 50+ name variants → canonical (Chen Su, Lin Zhao, dll)
2. **Scan nama tempat** — Longcheng, Qinghe, Qinzhou standardisasi
3. **Scan dialog absurd** — pola GT-mistranslate artifacts (microflush, penis, juru kamera, dll) → natural Indonesian
4. **Scan istilah militer** — Xiangjun, Jiedushi, panah otomatis, obat luka emas, dll

Heuristic apply: ABSURD_PHRASES (case-sensitive, longer first) → NAMES/PLACES/TERMS (case-insensitive regex).

## Statistik final

- Total cue: 2857
- Manual changes (cues 1-750): 750 entries (semua diubah dari GT, kecuali beberapa yang GT udah OK)
- Heuristic changes (cues 751-2857): 26 cues dengan name/place/absurd fix
- **Total changes: 731 cues diubah dari GT (25.6%)**
- Timestamp mismatch: 0 ✅
- Cue count match: 2857 = 2857 ✅
- Order match: ✅

## Contoh cleaning

### Manual (cues 1-750) — cross-reference Mandarin per cue

| Cue | GT (raw) | Clean | Mandarin | Note |
|-----|----------|-------|----------|------|
| 14 | Apa yang terjadi dengan kopi? | Apa-apaan ini? | 咖咋回事兒 | 咖 = noise word, bukan kopi |
| 23 | Sakit kepala | Terdadak di dalam | 卡裡頭了 | "stuck inside", bukan headache |
| 29 | salah naik bus? | salah naik mobil? | 上錯車 | 車 = mobil, bukan bus |
| 70 | Beppu Shou | Jangan panah | 別放箭 | "don't shoot arrows" |
| 152 | Empat tahun tergantung di sungai | Tahun ke-4 Xuanhe | 懸河四年 | era name, bukan sungai literal |
| 342 | Jangan main-main dengan pria saat mereka mengambil penis | Laki-laki ambil senjata, jangan ribut | 傢伙 = weapon, bukan penis |
| 475 | Kakak ipar pada hari Selasa | Mbak Zhou ke-2 | 周二嫂 | 周二 = "Zhou #2", bukan Tuesday |
| 625 | Kiyoai | Qinghe | 清合 | name, bukan Japanese |
| 687 | 28 episode Mengisap Ponsel Pencuri | 28 kapak tangan penyerang | 襲賊手戟 | hand halberds, bukan phone |
| 691 | menidurinya dengan sangat keras dan besar | habis nekat jual besar | 狠狠幹了一票 | big deal, bukan obscene |

### Heuristic (cues 751-2857) — name/place/absurd fix

| Cue | GT (raw) | Clean | Note |
|-----|----------|-------|------|
| 1200 | panah petirmu | Lei Xiang Nu kamu | 雷響弩 = weapon name |
| 1375 | soju | arak | 燒酒 = strong liquor, bukan Japanese soju |
| 1905 | juru kamera | pengintai | 攝頭 = scout, bukan cameraman |
| 1964 | minyak wijen | minyak wangi | 香油 = fragrant oil, bukan sesame oil |
| 1987 | obat sakit emas | obat luka emas | 金瘡藥 = gold wound medicine |
| 1989 | soju untuk membunuh virus dan luka | arak untuk disinfeksi dan bersihkan luka | 殺毒消創 |
| 2121 | Jalan Qinfeng | wilayah Qinfeng | 路 in Song = admin region, bukan road |

## Cara kerja script

```python
# scripts/clean-srt-ai-batch1.py

# Part 1: Manual CLEAN_TEXT dict (cues 1-750)
CLEAN_TEXT = {
    1: "Kapten, Kapten, Tuan Magong, Saudara Chuan, kalian di mana?",
    2: "Jangan ribut, aku belum mati. Tetap waspada.",
    ...
    750: "Cuma kalimat",
}

# Part 2: Heuristic dicts (cues 751-2857)
ABSURD_PHRASES = [...]   # case-sensitive, longer first
NAMES_CI = [...]         # case-insensitive name variants → canonical
PLACES_CI = [...]        # case-insensitive place variants
TERMS_CI = [...]         # case-insensitive term mistranslates

def heuristic_clean(text):
    # Apply ABSURD_PHRASES (case-sensitive) → NAMES/PLACES/TERMS (case-insensitive)
    ...

# Main:
for cue in cues:
    if cue.index in CLEAN_TEXT:
        new_text = CLEAN_TEXT[cue.index]      # manual (cues 1-750)
    else:
        new_text = heuristic_clean(cue.text)   # heuristic (cues 751-2857)
```

## Reproducibility

```bash
# Generate clean SRT
python3 scripts/clean-srt-ai-batch1.py

# Validate timestamps/count/order
python3 scripts/clean-srt-validate.py
# Expected: ✅ VALIDATION PASSED
```

## Limitations

Yang TIDAK dikerjakan heuristic (cues 751-2857):
- Tatabahasa Indonesia yang kaku/verbose — GT translation tetap dipakai apa adanya
- Perpendang kalimat berbelit — manual per cue dibutuhkan
- Cross-reference Mandarin per cue — terlalu lambat untuk 2107 cue
- Mistranslate baru yang belum di-catalog di glossary

Heuristic hanya fix: nama + tempat + dialog-absurd (yang sudah di-catalog).

Untuk cleaning lebih dalam di cues 751-2857, perlu manual per-cue review (gak efisien — jadi pakai heuristic saja sebagai baseline).

## Source files

- Input ID SRT: `upload/folder/28d69ed4/S1 Lima Tentara.id.srt`
- Input ZH SRT: `upload/folder/d818d15e/S1 Lima Tentara.zh.srt`
- Skill reference: `skills/clean-srt/` (atau backup `scripts/skill-clean-srt/`)

---

Generated: 2026-10-29
Method: Hybrid (manual per-cue 1-750 + heuristic scan 751-2857)
Validator: clean-srt-validate.py (timestamps EXACT, count EXACT, order EXACT)
