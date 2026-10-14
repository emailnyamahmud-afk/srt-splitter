#!/usr/bin/env python3
"""
baca-netral-batch1-apply.py — Hasil baca manual batch 1 (50 entries NETRAL pertama).

User: 'AI bisa baca manual? misal per batch, dimulai dari 50 entry/batch.
baca netral, jika tau ngoko, maka masukan ngoko, jika tau krama masukan ke krama,
jika tau terjemahan, maka tulis indo. itu dulu.'

Batch 1: 50 entries NETRAL pertama (entry_id 1-68, skip yg sudah paired).
Aku baca keterangan jv wiktionary + pengetahuan Jawa-Indonesia.

Format data = [(entry_id, ngoko, krama, indo)]
"""

import json
from pathlib import Path

# Hasil baca manual batch 1
# Format: (entry_id, ngoko, krama, indo)
# Register:
#   - ngoko = kata Jawa ngoko (kasar/biasa)
#   - krama = kata Jawa krama (halus) — termasuk krama inggil dari serapan Sanskrit/Arab
#   - None (kosong) = skip (reconstructed/tidak jelas)
# Kalau ngoko terisi → word jadi kosong (R-21: paired → word kosong)
# Kalau krama terisi → word jadi kosong

BATCH_1 = [
    # entry_id, ngoko, krama, indo
    (1, '', 'seramba', 'anak keempat laki-laki'),  # krama, kata khas
    (2, '', 'unting-unting', 'anak tunggal perempuan'),  # krama
    (3, '', 'kembang sepasang', 'anak kembar perempuan'),  # krama
    (4, '', 'pancagati', 'anak kelima perempuan'),  # krama
    (5, '', 'aang', 'rakus'),  # krama, "tansah kepéngin memangan"
    (6, 'aba', '', 'suara; perintah'),  # ngoko, contoh: "Abané manukmu" = suara
    (8, '', 'abad', 'abadi; abad (100 tahun)'),  # krama, serapan Arab
    (9, 'abah-abah', '', 'perabot; lapak'),  # ngoko
    (10, 'abahan', '', 'perabot kayu'),  # ngoko (-an, ngoko)
    (14, '', 'abikara', 'pejabat; orang terpelajar'),  # krama
    (15, '', 'abilasa', 'hawa nafsu'),  # krama
    (16, '', 'abimana', 'sombong'),  # krama
    (17, '', 'abimantrana', 'berkah; doa'),  # krama
    (18, '', 'abinawa', 'baru; aneh'),  # krama
    (20, '', 'abipraya', 'niat; rukun'),  # krama
    (21, '', 'abir', 'pedang Tionghoa'),  # skip register (serapan, jangan tebak)
    (22, '', 'abirama', 'indah; murka'),  # krama
    (23, '', 'abirupa', 'indah'),  # krama
    (24, 'abis', '', 'habis'),  # ngoko
    (25, '', 'abiwada', 'penghormatan'),  # krama
    (26, '', 'abiyasa', 'biasa'),  # krama
    (27, '', 'abjad', 'huruf Arab'),  # skip register (serapan)
    (28, 'abon', '', 'abon (daging suwir); tukang rokok'),  # ngoko
    (29, '', '', ''),  # abong-abong — reconstructed (*), skip
    (30, 'abor', '', 'telur campur (busuk)'),  # ngoko
    (32, 'abra', '', 'bersinar'),  # ngoko
    (34, 'abrat-abrat', '', 'muncrat-muncrat'),  # ngoko
    (38, 'abuk', '', 'bubuk; rabuk'),  # ngoko
    (41, '', '', ''),  # abèn-abèn — reconstructed (*), skip
    (43, '', 'adabiyah', 'Adabiyah (nama)'),  # krama, nama
    (44, '', '', 'nadi di leher'),  # adaini — skip register (kata khas)
    (45, '', 'adama', 'hina'),  # krama
    (48, '', 'adara', 'penghormatan'),  # krama
    (50, 'adat', '', 'adat; tata cara'),  # ngoko
    (51, '', 'adangiyah', 'pujian'),  # krama
    (52, '', 'adbuta', 'berlebihan'),  # krama
    (53, 'adha', '', 'bendungan'),  # ngoko
    (54, 'adhakan', '', 'dekat; mudah'),  # ngoko
    (55, 'adhangan', '', 'tanpa pilih kasih'),  # ngoko
    (57, '', 'adhik', 'adik'),  # krama (lebih halus dari adhi)
    (58, '', '', ''),  # adhing — "nanging meksa" (konjungsi), skip
    (59, 'adho', '', 'cara'),  # ngoko
    (60, 'adhong', '', 'alat cari ikan'),  # ngoko
    (61, 'adhuh', '', 'aduh (seruan sakit)'),  # ngoko
    (62, 'adhum', '', 'redup; payung'),  # ngoko
    (63, 'adhèg', '', 'kandang hewan'),  # ngoko
    (64, 'adhèng', '', 'sembuh sedih'),  # ngoko
    (66, '', 'adibusana', 'pakaian bagus'),  # krama
    (67, '', 'adigang', 'sombong kuat'),  # krama
    (68, '', 'adiguna', 'sombong pintar'),  # krama
]


def main():
    import sys
    kamus_path = sys.argv[1] if len(sys.argv) > 1 else '/home/z/my-project/srt-splitter-clone/public/kamus_unified_draft.json'
    kamus = json.load(open(kamus_path))
    words = kamus['words']

    print(f'📊 Total entries sebelum: {len(words):,}')
    print(f'📋 Batch 1: 50 entries manual')
    print()

    n_changed = 0
    n_ngoko = n_krama = n_indo_only = n_skip = 0

    for entry_id, ngoko, krama, indo in BATCH_1:
        w = next((x for x in words if x.get('entry_id') == entry_id), None)
        if not w:
            print(f'  ⚑ #{entry_id} tidak ditemukan')
            continue

        old_word = (w.get('word') or '').strip()
        old_ngoko = (w.get('ngoko') or '').strip()
        old_krama = (w.get('krama') or '').strip()
        old_indo = (w.get('indo') or '').strip()

        # Skip kalau entry sudah paired (ada ngoko/krama/indo existing)
        if old_ngoko or old_krama or old_indo:
            print(f'  ⚠ #{entry_id} sudah paired, skip')
            n_skip += 1
            continue

        # Skip kalau tidak ada perubahan
        if not ngoko and not krama and not indo:
            print(f'  ⏭ #{entry_id} {old_word!r} — skip (reconstructed/unclear)')
            n_skip += 1
            continue

        # Apply changes
        if ngoko:
            w['ngoko'] = ngoko
            w['word'] = ''  # R-21: paired → word kosong
            n_ngoko += 1
        elif krama:
            w['krama'] = krama
            w['word'] = ''  # R-21: paired → word kosong
            n_krama += 1
        elif indo:
            # Hanya indo terisi (register tidak diketahui)
            w['indo'] = indo
            # word tetap (NETRAL, belum tentukan register)
            n_indo_only += 1

        # Indo di-isi kalau ada
        if indo:
            w['indo'] = indo

        # Sumber tambah 'baca-manual'
        sumber = (w.get('sumber') or '').strip()
        if 'baca-manual' not in sumber:
            w['sumber'] = (sumber + ' + baca-manual-batch1').strip(' +') if sumber else 'baca-manual-batch1'

        # Status = draft (R-12)
        w['status'] = 'draft'
        n_changed += 1

        # Print
        new_ngoko = w.get('ngoko','').strip()
        new_krama = w.get('krama','').strip()
        new_indo = w.get('indo','').strip()
        print(f"  #{entry_id} word={old_word[:25]!r} → ngoko={new_ngoko!r} krama={new_krama!r} indo={new_indo!r}")

    print()
    print(f'═' * 60)
    print(f'  BATCH 1 SUMMARY')
    print(f'═' * 60)
    print(f'  Changed: {n_changed}/50')
    print(f'  ngoko diisi: {n_ngoko}')
    print(f'  krama diisi: {n_krama}')
    print(f'  indo only (register skip): {n_indo_only}')
    print(f'  skip (reconstructed/unclear): {n_skip}')

    # Save
    json.dump(kamus, open(kamus_path, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
    print(f'\n✅ Saved: {kamus_path}')
    print(f'📊 Total entries: {len(words):,}')


if __name__ == '__main__':
    main()
