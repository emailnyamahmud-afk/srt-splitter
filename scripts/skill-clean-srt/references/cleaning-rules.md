# Aturan Cleaning SRT

## Prioritas (urut dari yang paling penting)

1. **Timestamps SAMA PERSIS** — single source of truth, jangan ubah
2. **Cue count sama** — jangan tambah/hapus/gabung
3. **Urutan sama** — jangan reorder
4. **Nama orang/tempat preserved** — lihat glossary-names.md
5. **Mistranslate fixed** — lihat glossary-names.md untuk daftar
6. **Grammar diperbaiki** — natural Bahasa Indonesia
7. **Kalimat diperpendang** — tanpa mengubah makna

## Contoh Before/After

### Contoh 1: Mistranslate
**Input (GT):**
```
3
00:01:00,500 --> 00:01:01,500
Teruslah melakukan cumming
```
**Output (clean):**
```
3
00:01:00,500 --> 00:01:01,500
Teruslah menarik pelatuk
```

### Contoh 2: Nama orang
**Input (GT):**
```
7
00:01:21,250 --> 00:01:22,250
Saya ingin bertemu dengan kepala keluarga

8
00:01:22,050 --> 00:01:23,250
Nona nanti
```
**Output (clean):**
```
7
00:01:21,250 --> 00:01:22,250
Saya ingin bertemu dengan kepala keluarga

8
00:01:22,050 --> 00:01:23,250
Nona, nanti
```
*(Tidak ada perubahan — GT sudah benar. Keep as-is.)*

### Contoh 3: Grammar verbose
**Input (GT):**
```
45
00:01:31,579 --> 00:01:33,180
Ibumu hanyalah seorang selir
```
**Output (clean):**
```
45
00:01:31,579 --> 00:01:33,180
Ibumu hanyalah seorang selir
```
*(Tidak ada perubahan — sudah natural. Keep as-is.)*

### Contoh 4: Konteks dari Mandarin
**Input SRT Indonesia (GT):**
```
1728
01:00:23,500 --> 01:00:24,500
Teruslah melakukan cumming
```
**Input SRT Mandarin (referensi):**
```
1728
01:00:23,500 --> 01:00:24,500
继续扣
```
**Output (clean):**
```
1728
01:00:23,500 --> 01:00:24,500
Teruslah menarik pelatuk
```
*(Mandarin "扣" = trigger/pelatuk → confirms "cumming" is mistranslate)*

## Edge Cases

### Cue kosong / 1 kata
Jangan hapus cue kosong. Keep as-is (timestamp tetap, text tetap).

### Cue dengan text panjang banget
Jangan pecah jadi 2 cue. Keep as-is (timestamp tetap, text tetap).

### Cue dengan text aneh (glyph error, encoding)
Keep as-is. Jangan hapus. Tandai di notes (opsional).

### Cue yang GT translate jadi bahasa lain (mis. English, bukan Indonesia)
Keep as-is. Jangan translate ulang. Tandai di notes (opsional).

## Yang JANGAN Dilakukan

- Jangan translate dari Mandarin (itu tugas GT)
- Jangan generate SRT dari audio (itu tugas whisper-tui)
- Jangan ubah timestamps
- Jangan tambah/hapus cue
- Jangan ubah urutan
- Jangan halu (ragu → keep as-is)
