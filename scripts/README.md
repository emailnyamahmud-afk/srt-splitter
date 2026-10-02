# Scripts — SRT Splitter

Script Python untuk memproses file SRT (subtitle). Semua script tidak mengubah timestamps SRT.

## Daftar Script

### 1. `rapikan-jawa.py`
Rapikan bahasa Jawa di satu file SRT (ejaan, tata bahasa, kosakata).

```bash
python3 scripts/rapikan-jawa.py
# Input: /home/z/my-project/upload/Season-2-jw.srt
# Output: /home/z/my-project/download/Season-2-jw-fixed.srt
```

Ubah `input_file` dan `output_file` di dalam script sesuai kebutuhan.

### 2. `rapikan-jawa-semua-season.py`
Rapikan bahasa Jawa di SEMUA season sekaligus (S1-S6).

```bash
python3 scripts/rapikan-jawa-semua-season.py
# Input: /home/z/my-project/upload/Season-*-jw.srt
# Output: /home/z/my-project/download/Season-*-jw-fixed.srt
```

Perbaikan yang dilakukan:
- Hapus "(or)" dan duplikat di Season 1
- Ejaan aksén: `kowe` → `kowé`, `dheweke` → `dhèwèké`, `kabeh` → `kabèh`
- Kosakata: `keluarga` → `kulawarga`, `rumah tangga` → `omah tangga`, `bandit` → `begal`
- Ejaan: `pengin` → `péngin`, `sedhela` → `sedhéla`, `kene` → `kéné`

### 3. `tambah-krama.py`
Tambah sentuhan bahasa krama di bagian yang tepat (kepada atasan, situasi formal).

```bash
python3 scripts/tambah-krama.py
# Process semua Season 1-6 yang sudah dirapikan
```

Perbaikan yang dilakukan:
- `Kapten, aku` → `Kapten, kula`
- `Pak, aku` → `Pak, kula`
- `Aku mohon` → `Kula nyuwun`
- `mangga, gusti` → `Mangga, Gusti`
- `inggih` di awal → `Inggih`
- `mangga` di awal → `Mangga`

### 4. `split_srt.py`
Split file SRT menjadi beberapa bagian dengan durasi yang dapat diatur.

```bash
python3 scripts/split_srt.py input.srt output_dir PREFIX 30
# Split setiap 30 menit, output: PREFIX-01.srt, PREFIX-02.srt, dst.
```

### 5. `build_source_zip.py`
Build source code ZIP untuk distribusi (dipakai oleh Next.js app).

```bash
python3 scripts/build_source_zip.py
# Output: /home/z/my-project/download/srt-splitter-source.zip
```

## Cara Pakai

1. Letakkan file SRT Jawa di folder `upload/`
2. Jalankan `rapikan-jawa-semua-season.py` untuk rapikan semua
3. Jalankan `tambah-krama.py` untuk tambah sentuhan krama
4. File hasil ada di folder `download/`

## Catatan

- **Timestamps TIDAK diubah** — semua timing tetap sama persis
- Script aman dijalankan ulang (idempotent)
- File di folder `download/` tidak di-push ke GitHub (hanya script yang di-push)
