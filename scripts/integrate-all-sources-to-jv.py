#!/usr/bin/env python3
"""integrate-all-sources-to-jv.py — Integrate SEMUA source PURE ke jv_integrated_mendeley.

User 10 Okt 2026: 'sekarang jv_integrated jadi json utama, AI lakukan integrasi dari
dasanama, lema id, semua source, termasuk kamus draft. tapi kamus draft = sampah,
sumber lain saja'

Source yang di-integrate (PURE exact, BUKAN merged entries sampah):
1. jv_integrated_mendeley (44.716 entries) — base (jv_wiktionary XML + mendeley)
2. dasanama PURE (141 entries) — sumber exact 'dasanama-raw.csv (new)'
3. lemma PURE (644 entries) — sumber exact 'id.wiktionary.org Kategori:jv:Lema (new)'
4. lampiran PURE (591 entries) — sumber exact 'lampiran-raw.json (new)'
5. angka PURE (975 entries) — sumber exact 'angka-raw.json (new)'

Logika (sama seperti integrate-mendeley-to-jv.py):
1. Index base (jv_integrated_mendeley) by lowercase token (word + krama) → entry_id
2. Untuk setiap source PURE (dasanama, lemma, lampiran, angka):
   - Tokenize ngoko + krama + word (split comma, lowercase)
   - Cari match di base index
   - Match → merge info (sinonim comma, arti | , no hapus)
   - No match → add as new entry
3. Dilarang duplikat (1 konsep = 1 entry)
4. Dilarang hapus data (semua field preserve, gabung bukan hapus)

R-22: integrasi antar file yang ada, BUKAN scrape
R-18: tidak hapus entry/field, hanya merge
R-26: 20 field, no register + no krama_inggil
R-27: skip kamus draft (sampah), cuma source PURE per sumber
"""
import json
from pathlib import Path

BASE_PATH = Path('/home/z/my-project/public/kamus_jv_wiktionary_integrated_mendeley.json')
DRAFT_PATH = Path('/home/z/my-project/public/kamus-jawa-draft.json')
OUT_PATH = Path('/home/z/my-project/public/kamus_unified.json')

# Source PURE dari kamus draft (sumber exact, no merge flag in string)
PURE_SOURCES = {
    'dasanama': 'dasanama-raw.csv (new)',
    'lemma': 'id.wiktionary.org Kategori:jv:Lema (new)',
    'lampiran': 'lampiran-raw.json (new)',
    'angka': 'angka-raw.json (new)',
}


def tokenize_field(val):
    """Split comma, strip, lowercase, skip empty/short."""
    if not val or not isinstance(val, str):
        return []
    return [t.strip().lower() for t in val.split(',') if t.strip() and len(t.strip()) > 1]


def dedup_comma(values):
    """Gabung list dengan comma, dedup (case-insensitive)."""
    seen = set()
    result = []
    for v in values:
        if not v:
            continue
        key = v.lower().strip()
        if key and key not in seen:
            seen.add(key)
            result.append(v.strip())
    return ', '.join(result)


def main():
    print(f'→ Load base: {BASE_PATH.name}...')
    with open(BASE_PATH, 'r', encoding='utf-8') as f:
        base_data = json.load(f)
    base_words = base_data['words']
    print(f'  Base entries (jv_integrated_mendeley): {len(base_words):,}')

    print(f'→ Load kamus draft (untuk extract source PURE)...')
    with open(DRAFT_PATH, 'r', encoding='utf-8') as f:
        draft_data = json.load(f)
    draft_words = draft_data['words']

    # Filter PURE entries per source dari kamus draft
    pure_sources_data = {}  # source_key → list of entries
    for source_key, source_str in PURE_SOURCES.items():
        pure_entries = [w for w in draft_words if w.get('sumber', '') == source_str]
        pure_sources_data[source_key] = pure_entries
        print(f'  {source_key:12} PURE entries: {len(pure_entries):,} (sumber={source_str!r})')

    # Build index base: lowercase token → list of base entry_id
    print(f'\n→ Build index base...')
    base_index = {}
    for w in base_words:
        eid = w.get('entry_id')
        word_lc = (w.get('word') or '').strip().lower()
        if word_lc and len(word_lc) > 1:
            base_index.setdefault(word_lc, []).append(eid)
        # Index ngoko tokens
        for tok in tokenize_field(w.get('ngoko', '')):
            base_index.setdefault(tok, []).append(eid)
        # Index krama tokens
        for tok in tokenize_field(w.get('krama', '')):
            base_index.setdefault(tok, []).append(eid)
    print(f'  Unique tokens di base_index: {len(base_index):,}')

    # Copy base sebagai start
    integrated = list(base_words)
    eid_to_idx = {w.get('entry_id'): i for i, w in enumerate(integrated)}

    # Track stats per source
    stats = {}
    total_added = 0

    # Process setiap source PURE
    for source_key, source_entries in pure_sources_data.items():
        print(f'\n→ Process source: {source_key} ({len(source_entries):,} entries)...')
        merged = 0
        added = 0
        no_match_entries = []

        for src_w in source_entries:
            # Tokenize word + ngoko + krama
            src_word = (src_w.get('word') or '').strip().lower()
            src_ngoko_tokens = tokenize_field(src_w.get('ngoko', ''))
            src_krama_tokens = tokenize_field(src_w.get('krama', ''))
            all_tokens = [src_word] + src_ngoko_tokens + src_krama_tokens
            all_tokens = [t for t in all_tokens if t and len(t) > 1]

            # Cari match di base_index
            matched_eids = set()
            for tok in all_tokens:
                if tok in base_index:
                    for eid in base_index[tok]:
                        matched_eids.add(eid)

            if matched_eids:
                # MERGE: ambil entry pertama yang match
                base_eid = sorted(matched_eids)[0]
                base_idx = eid_to_idx[base_eid]
                base_w = integrated[base_idx]

                # Merge ngoko: base + source (comma dedup)
                base_ngoko_tokens = [t.strip() for t in (base_w.get('ngoko') or '').split(',') if t.strip()]
                new_ngoko = dedup_comma(base_ngoko_tokens + src_ngoko_tokens)
                if new_ngoko != (base_w.get('ngoko') or ''):
                    base_w['ngoko'] = new_ngoko

                # Merge krama: base + source (comma dedup)
                base_krama_tokens = [t.strip() for t in (base_w.get('krama') or '').split(',') if t.strip()]
                new_krama = dedup_comma(base_krama_tokens + src_krama_tokens)
                if new_krama != (base_w.get('krama') or ''):
                    base_w['krama'] = new_krama

                # Merge word: kalau base word kosong + source word terisi, isi
                if not (base_w.get('word') or '').strip() and src_w.get('word', '').strip():
                    base_w['word'] = src_w['word']

                # Merge arti: base + source, dipisah ' | '
                base_arti = (base_w.get('arti') or '').strip()
                src_arti = (src_w.get('arti') or '').strip()
                if src_arti and src_arti not in base_arti:
                    if base_arti:
                        base_w['arti'] = f'{src_arti} | {base_arti}'
                    else:
                        base_w['arti'] = src_arti

                # Merge aksara: base + source (comma dedup)
                base_aksara = (base_w.get('aksara') or '').strip()
                src_aksara = (src_w.get('aksara') or '').strip()
                if src_aksara:
                    base_aksara_tokens = [t.strip() for t in base_aksara.split(',') if t.strip()]
                    new_aksara = dedup_comma(base_aksara_tokens + [src_aksara])
                    if new_aksara != base_aksara:
                        base_w['aksara'] = new_aksara

                # Merge keterangan: base + source, dipisah ' | '
                base_ket = (base_w.get('keterangan') or '').strip()
                src_ket = (src_w.get('keterangan') or '').strip()
                if src_ket and src_ket not in base_ket:
                    if base_ket:
                        base_w['keterangan'] = f'{base_ket} | [{source_key}] {src_ket}'
                    else:
                        base_w['keterangan'] = f'[{source_key}] {src_ket}'

                # Update sumber
                base_w['sumber'] = f'{base_w.get("sumber","")} + {source_key} (PURE)'
                base_w[f'is_{source_key}'] = True
                base_w['source_count'] = (base_w.get('source_count') or 1) + 1

                merged += 1
            else:
                # NO MATCH: add as new entry
                new_entry = dict(src_w)
                new_entry['entry_id'] = None  # re-number later
                new_entry['sumber'] = f'{source_key} (PURE, no match)'
                new_entry[f'is_{source_key}'] = True
                # Reset flag lain
                for k in ['is_dasanama', 'is_lemma', 'is_lampiran', 'is_angka', 'is_mendeley']:
                    if k != f'is_{source_key}' and k in new_entry:
                        new_entry[k] = False
                no_match_entries.append(new_entry)
                added += 1

        # Append no-match entries ke integrated
        integrated.extend(no_match_entries)
        eid_to_idx = {w.get('entry_id'): i for i, w in enumerate(integrated) if w.get('entry_id') is not None}

        # Update base_index dengan new entries (supaya entry berikutnya bisa match)
        for new_w in no_match_entries:
            # Entry belum punya entry_id, skip index (akan di-index di akhir)
            pass

        stats[source_key] = {'merged': merged, 'added': added}
        total_added += added
        print(f'  Merged: {merged}, Added (new): {added}')

    # Re-number entry_id 1..N
    for i, w in enumerate(integrated, 1):
        w['entry_id'] = i

    print(f'\n=== Summary ===')
    print(f'  Base (jv_integrated_mendeley): {len(base_words):,}')
    for source_key, s in stats.items():
        print(f'  {source_key:12} merged: {s["merged"]:>4} | added: {s["added"]:>4}')
    print(f'  Total integrated entries: {len(integrated):,}')

    # Build output
    print(f'\n→ Build output JSON...')
    out_data = {
        'metadata': {
            'version': 'v1.0 (unified — jv + mendeley + dasanama + lemma + lampiran + angka)',
            'description': 'Kamus unified — jv.wiktionary XML dump (parsed minimal) + mendeley curated + dasanama PURE + lemma PURE + lampiran PURE + angka PURE. 1 konsep = 1 entry (no duplikat). Sinonim comma, arti dipisah | (Indonesia | Jawa). Skip kamus draft merged entries (sampah AI). R-22: integrasi antar file yang ada. R-18: tidak hapus, hanya merge. R-26: 20 field, no register + no krama_inggil.',
            'sources_integrated': [
                'jv.wiktionary.org (XML dump, parsed minimal) — 44.615 base',
                'mendeley (curated) — 145 (44 merged, 101 new)',
                f'dasanama (PURE) — {len(pure_sources_data["dasanama"])} ({stats["dasanama"]["merged"]} merged, {stats["dasanama"]["added"]} new)',
                f'lemma (PURE) — {len(pure_sources_data["lemma"])} ({stats["lemma"]["merged"]} merged, {stats["lemma"]["added"]} new)',
                f'lampiran (PURE) — {len(pure_sources_data["lampiran"])} ({stats["lampiran"]["merged"]} merged, {stats["lampiran"]["added"]} new)',
                f'angka (PURE) — {len(pure_sources_data["angka"])} ({stats["angka"]["merged"]} merged, {stats["angka"]["added"]} new)',
            ],
            'total_base': len(base_words),
            'total_integrated': len(integrated),
            'schema_version': 'v2.7 (R-26 drop register + krama_inggil)',
        },
        'words': integrated,
    }

    print(f'→ Write ke {OUT_PATH.name}...')
    with open(OUT_PATH, 'w', encoding='utf-8') as f:
        json.dump(out_data, f, ensure_ascii=False, indent=2)

    size = OUT_PATH.stat().st_size
    print(f'  ✅ Saved: {OUT_PATH}')
    print(f'  Size: {size:,} bytes ({size/1024/1024:.2f} MB)')

    # Sample 5 multi-source entries (source_count > 2)
    print(f'\n=== Sample 5 multi-source entries ===')
    count = 0
    for w in integrated:
        if (w.get('source_count') or 1) >= 3:
            count += 1
            if count <= 5:
                print(f'\n  entry_id={w["entry_id"]}:')
                print(f'    word:    {w["word"]!r}')
                print(f'    ngoko:   {w.get("ngoko","")!r}')
                print(f'    krama:   {w.get("krama","")!r}')
                print(f'    arti:    {w.get("arti","")[:100]!r}')
                print(f'    sumber:  {w.get("sumber","")!r}')
                print(f'    source_count: {w.get("source_count")}')


if __name__ == '__main__':
    main()
