#!/usr/bin/env python3
"""baca-manual-batch-apply.py — Apply hasil baca manual per batch ke kamus_unified_draft.json.

Format: BATCH = list of (entry_id, ngoko, krama, indo, confidence, catatan)
- ngoko/krama: kosong kalau ragu register (skip, word tetap)
- indo: kosong kalau ragu arti total (skip)
- catatan: reasoning AI, simpan di field 'keterangan' akhiran [AI: ...]
"""

import json
import sys

BATCH = [
    # (entry_id, ngoko, krama, indo, confidence, catatan)
    (1, '', 'seramba', 'anak ke-4 laki-laki', 'HIGH',
     'anak+sekawan(empat,krama)+lanang(laki-laki)+kabeh semua'),
    (2, '', 'unting-unting', 'anak tunggal perempuan', 'HIGH',
     'anak+satunggal(satu,krama)+wadon+kabeh'),
    (3, '', 'kembang sepasang', 'anak kembar perempuan', 'MEDIUM',
     'RAGU: anak loro wadon kabeh — bisa kembar ATAU anak ke-2 perempuan (urutan kelahiran). Aku pilih kembar, user verifikasi.'),
    (4, '', 'pancagati', 'anak ke-5 perempuan', 'HIGH',
     'anak+lima+wadon+kabeh (pola sama dengan #1 seramba)'),
    (5, '', '', 'rakus', 'MEDIUM',
     'RAGU register. indo dari tansah(selalu)+kepéngin(ingin)+memangan(makan). Register "aang" skip — word tetap (NETRAL paired).'),
    (6, 'aba', '', 'suara; perintah', 'HIGH',
     'Dua arti: suara, perintah. Ada #:: Indonesia translation di keterangan (literal).'),
    (8, '', 'abad', 'abadi; abad (100 tahun)', 'HIGH',
     'langgeng=abadi, lestari, jaman 100 taun=abad. Serapan Arab=krama.'),
    (9, 'abah-abah', '', 'perabot; perkakas; lapak', 'HIGH',
     'prabot=perabot, piranti=perkakas, lapak. Reduplikasi=ngoko.'),
    (10, 'abahan', '', 'perabot kayu; yatim piatu', 'HIGH/MEDIUM',
     'Arti1 HIGH: prabot sarta bebakaling omah kreteg (perabot kayu). Arti2 MEDIUM: landhesaning wong kang ditugel guluné = kiasan yatim piatu (ayah meninggal). Akhiran -an=ngoko.'),
]


def main():
    kamus_path = sys.argv[1] if len(sys.argv) > 1 else '/home/z/my-project/srt-splitter-clone/public/kamus_unified_draft.json'
    d = json.load(open(kamus_path))
    words = d['words']

    n_changed = 0
    n_skip = 0
    for entry_id, ngoko, krama, indo, confidence, catatan in BATCH:
        w = next((x for x in words if x.get('entry_id') == entry_id), None)
        if not w:
            print(f'  ⚑ #{entry_id} tidak ditemukan')
            continue
        old_word = (w.get('word') or '').strip()
        old_ngoko = (w.get('ngoko') or '').strip()
        old_krama = (w.get('krama') or '').strip()
        old_indo = (w.get('indo') or '').strip()

        # Skip kalau entry sudah paired
        if old_ngoko or old_krama or old_indo:
            print(f'  ⚠ #{entry_id} sudah paired, skip')
            n_skip += 1
            continue

        # Skip kalau semua kosong (ragu total)
        if not ngoko and not krama and not indo:
            print(f'  ⏭ #{entry_id} {old_word!r} — skip total (ragu)')
            n_skip += 1
            continue

        # Apply
        if ngoko:
            w['ngoko'] = ngoko
            w['word'] = ''
        elif krama:
            w['krama'] = krama
            w['word'] = ''
        # Kalau hanya indo (register skip), word tetap (NETRAL paired)

        if indo:
            w['indo'] = indo

        # Catatan AI di akhir keterangan (raw jv wiktionary dipertahankan)
        ket = (w.get('keterangan') or '').strip()
        ai_note = f'\n\n[AI baca-manual: confidence={confidence} | {catatan}]'
        w['keterangan'] = ket + ai_note

        # Sumber tambah marker
        sumber = (w.get('sumber') or '').strip()
        if 'baca-manual' not in sumber:
            w['sumber'] = (sumber + ' + baca-manual').strip(' +') if sumber else 'baca-manual'

        w['status'] = 'draft'
        n_changed += 1
        print(f"  #{entry_id} word={old_word[:25]!r} → ngoko={w.get('ngoko','')!r} krama={w.get('krama','')!r} indo={w.get('indo','')!r} [{confidence}]")

    print()
    print(f'Changed: {n_changed}, Skip: {n_skip}')

    json.dump(d, open(kamus_path, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
    print(f'Saved: {kamus_path}')


if __name__ == '__main__':
    main()
