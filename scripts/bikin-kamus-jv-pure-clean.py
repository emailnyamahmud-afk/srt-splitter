#!/usr/bin/env python3
"""bikin-kamus-jv-pure-clean.py — Filter jv.wiktionary PURE yang BENAR-BENAR bersih
(1 lemma per field, no sinonim — karena dari raw internet = 1 lemma = 1 entry).

User 10 Okt 2026: 'salah, sinonim bagus bagian dari merge di sesi-sesi sebelumnya.
dari raw source internet = gak ada sinonim'

Audit sebelumnya salah: 219 entries jv PURE ngoko dengan 2+ sinonim = hasil merge
AI tolol dari sesi sebelumnya, BUKAN sinonim valid dari Wiktionary.

Output:
1. public/kamus_jv_ngoko_pure_clean.json — entries dengan 1 lemma per field (no comma)
2. public/kamus_jv_krama_pure_clean.json — entries dengan 1 lemma per field
3. public/kamus_jv_pure_suspect.json — entries dengan 2+ sinonim (rawan merge AI,
   user audit manual — R-18: tidak hapus, simpan terpisah)

R-22: filter dari kamus draft, BUKAN parsing ulang dari raw.
R-18: tidak hapus data. Entries suspect disimpan terpisah untuk audit user.
R-27: phase kerja bertahap per source.
"""
import json
from collections import Counter
from pathlib import Path

DRAFT = Path('/home/z/my-project/public/kamus-jawa-draft.json')

PURE_SOURCES = {
    'jv_ngoko': 'jv.wiktionary.org (group by ngoko)',
    'jv_krama': 'jv.wiktionary.org (group by krama)',
}


def has_comma(val):
    """Cek apakah field punya comma (2+ sinonim = merge AI suspect)."""
    if not val or not isinstance(val, str):
        return False
    return ',' in val.strip()


def count_tokens(val):
    """Hitung token comma-separated."""
    if not val:
        return 0
    return len([t for t in val.split(',') if t.strip()])


def main():
    print(f'→ Load kamus draft...')
    with open(DRAFT, 'r', encoding='utf-8') as f:
        data = json.load(f)

    words = data['words']
    print(f'  Total entries: {len(words):,}')
    print()

    # Filter per source
    for source_key, source_str in PURE_SOURCES.items():
        print(f'════════════════════════════════════════════════════════════')
        print(f'  Source: {source_key} ({source_str!r})')
        print(f'════════════════════════════════════════════════════════════')

        pure_entries = [w for w in words if w.get('sumber', '') == source_str]
        print(f'  Total entries jv PURE: {len(pure_entries):,}')

        # Pisahkan clean (1 lemma per field) vs suspect (2+ sinonim)
        clean_entries = []
        suspect_entries = []
        for w in pure_entries:
            # Cek ngoko, krama, word, lemma_words — ada comma = suspect merge AI
            fields_with_comma = []
            for f in ['word', 'ngoko', 'krama', 'lemma_words']:
                if has_comma(w.get(f, '')):
                    fields_with_comma.append(f)
            if fields_with_comma:
                suspect_entries.append((w, fields_with_comma))
            else:
                clean_entries.append(w)

        print(f'  CLEAN (1 lemma per field, no comma): {len(clean_entries):,}')
        print(f'  SUSPECT (2+ sinonim = merge AI):    {len(suspect_entries):,}')
        print()

        # Statistik suspect
        if suspect_entries:
            print(f'  Suspect breakdown per field:')
            field_counter = Counter()
            for w, fields in suspect_entries:
                for f in fields:
                    field_counter[f] += 1
            for f, c in field_counter.most_common():
                print(f'    {f:15} {c:>4} entries')
            print()

        # Write clean subset
        clean_path = Path(f'/home/z/my-project/public/kamus_{source_key}_pure_clean.json')
        subset = dict(data)
        subset['words'] = []
        for i, w in enumerate(clean_entries, 1):
            new_w = dict(w)
            new_w['entry_id'] = i
            subset['words'].append(new_w)
        subset['metadata'] = {
            **data.get('metadata', {}),
            'version': f'v1.0 ({source_key} pure clean — 1 lemma per field)',
            'description': f'jv.wiktionary PURE bersih — 1 lemma per field (no comma/sinonim). Filter: sumber exact + ngoko/krama/word/lemma_words tidak ada comma. Suspect merge AI (2+ sinonim) di file terpisah.',
            'source_filter': f"sumber == '{source_str}' AND no comma in word/ngoko/krama/lemma_words",
            'total_subset': len(clean_entries),
            'total_suspect': len(suspect_entries),
            'parent_file': 'kamus-jawa-draft.json',
        }

        with open(clean_path, 'w', encoding='utf-8') as f:
            json.dump(subset, f, ensure_ascii=False, indent=2)
        print(f'  ✅ Saved clean: {clean_path.name} ({clean_path.stat().st_size:,} bytes)')

        # Write suspect (file terpisah supaya user audit)
        if suspect_entries:
            suspect_path = Path(f'/home/z/my-project/public/kamus_{source_key}_pure_suspect.json')
            suspect_data = dict(data)
            suspect_data['words'] = []
            for i, (w, fields) in enumerate(suspect_entries, 1):
                new_w = dict(w)
                new_w['entry_id'] = i
                new_w['_suspect_fields'] = fields  # flag field mana yang comma
                suspect_data['words'].append(new_w)
            suspect_data['metadata'] = {
                **data.get('metadata', {}),
                'version': f'v1.0 ({source_key} pure SUSPECT — 2+ sinonim = merge AI suspect)',
                'description': f'jv.wiktionary PURE dengan 2+ sinonim (comma di word/ngoko/krama/lemma_words). Rawan merge AI tolol dari sesi sebelumnya. User audit manual via TUI, R-18: tidak hapus, simpan terpisah.',
                'source_filter': f"sumber == '{source_str}' AND comma in word/ngoko/krama/lemma_words",
                'total_suspect': len(suspect_entries),
                'parent_file': 'kamus-jawa-draft.json',
            }

            with open(suspect_path, 'w', encoding='utf-8') as f:
                json.dump(suspect_data, f, ensure_ascii=False, indent=2)
            print(f'  ✅ Saved suspect: {suspect_path.name} ({suspect_path.stat().st_size:,} bytes)')

        # Sample 3 entries clean
        print(f'\n  Sample 3 CLEAN entries:')
        for w in clean_entries[:3]:
            print(f'    entry_id={w.get("entry_id")}:')
            print(f'      word:   {w.get("word", "")!r}')
            print(f'      ngoko:  {w.get("ngoko", "")!r}')
            print(f'      krama:  {w.get("krama", "")!r}')
            print(f'      arti:   {w.get("arti", "")!r}')
            print(f'      aksara: {w.get("aksara", "")!r}')
            ket = w.get('keterangan', '')
            if ket:
                print(f'      keterangan: {ket[:120]!r}')

        # Sample 3 entries suspect
        if suspect_entries:
            print(f'\n  Sample 3 SUSPECT entries (rawan merge AI):')
            for w, fields in suspect_entries[:3]:
                print(f'    entry_id={w.get("entry_id")} (suspect fields: {fields}):')
                print(f'      word:   {w.get("word", "")!r}')
                print(f'      ngoko:  {w.get("ngoko", "")!r}')
                print(f'      krama:  {w.get("krama", "")!r}')
                print(f'      arti:   {w.get("arti", "")!r}')
                ket = w.get('keterangan', '')
                if ket:
                    print(f'      keterangan: {ket[:120]!r}')

        print()


if __name__ == '__main__':
    main()
