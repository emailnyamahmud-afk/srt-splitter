# ⚠ JANGAN RUN SCRIPT INI — DISABLED PER R-20

**Status**: DISABLED pada 9 Okt 2026 (commit neutralize-kamus-draft.py)

**Alasan**: 
- Parser script ini agresif merge multi-source (Wiktionary + Mendeley + Lampiran + Dasanama)
- Banyak Indonesia word nyangkut sebagai "sinonim Jawa" → DATA RUSAK
- Mis. `kula` (asli KRAMA) di-tag sebagai NGOKO di entry 18196 — halu
- Parser AI tolol ikut definisi yang salah → cascade rusak

**Pasca-neutralize (v2.3+)**:
- `kamus-jawa-draft.json` = **SATU-SATUNYA rujukan** untuk AI & TUI
- Field `word` = entri NETRAL (belum terdefinisi register)
- Field `ngoko`/`krama`/`arti` hanya diisi untuk entries yang SUDAH PAIRED:
  - `ngoko + krama` (pasangan ngoko-krama)
  - `ngoko + arti` (pasangan ID-ngoko)
  - `krama + arti` (pasangan ID-krama, no ngoko)
  - `ngoko + krama + arti` (3-pasangan lengkap)

**Raw files tetap ada** di `public/` sebagai ARSIP (R-16 jangan hapus):
- `kamus-jawa-full.json` (44.585, jv.wiktionary)
- `kamus-jawa-new-lemma.json` (859, id.wiktionary)
- `kamus-jawa-mendeley-raw.json` (955, Mendeley)
- `dasanama-raw.csv` (431, sinonim)
- `lampiran-raw.json` (2.724, Lampiran Kamus)
- `lampiran-angka-raw.json` (66, Lampiran Nama angka)
- `angka-raw.json` (1.009, angka + user validated)

TAPI raw **BUKAN rujukan lagi**. Jangan rebuild dari raw. Jangan parse raw. Jangan merge raw ke draft.

**Yang BOLEH dilakukan dengan raw**:
- Read-only untuk referensi konteks (mis. lihat keterangan asli)
- Cross-check kalau user tanya "data ini dari mana?"
- Archive — bukan untuk rebuild

**Yang DILARANG**:
- `python3 scripts/build-kamus-bersih.py.DISABLED` (akan overwrite kamus-draft.json dengan data rusak lagi)
- Modifikasi raw files (kecuali tambah data baru, R-16)
- Bikin script baru yang parse raw dengan parser tolol lama

**Kalau butuh tambah data baru**:
1. User edit langsung di `kamus-tui.py` (manual via TUI)
2. Atau AI bantu cari di kamus resmi Kemendikbud (https://kesakata.kemdikbud.go.id)
3. Atau AI bantu cross-reference Wiktionary ONLINE untuk 1 entry spesifik (bukan batch parse)

**Tanggung jawab**: AI akui parser ini tolol, merusak data, user harus validasi ulang 1-1.
Lihat R-19 di PROJECT_RULES.md untuk audit suspect pattern.

---

Jika BENAR-BENAR perlu rebuild (mis. ada raw data baru yang ingin di-merge):
1. Diskusi dengan user dulu
2. Buat script BARU dengan parser yang lebih hati-hati (jangan agresif merge)
3. Test pada sample kecil dulu (10 entries), user validasi
4. Baru scale up

Untuk sekarang: **kamus-draft.json v2.3+ = source of truth, jangan rebuild**.
