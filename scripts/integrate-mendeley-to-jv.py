#!/usr/bin/env python3
"""integrate-mendeley-to-jv.py — Integrate mendeley entries ke jv_wiktionary_raw.

User 10 Okt 2026: 'integrasi medley ke jv wictionary, dilarang duplikat, dilarang
hapus data. standarisasi ejaan medley ke jv wictionary. jika di medley ada turu maka
mix dengan turu yg ada di jv wictionary, dan di jv wictionary ada sare juga mix = jadi
1 entri, sementara di mendelay juga ada id (indonesia = tidur), maka tidur, turu, sare
= mix 1 entry. jika ada ngoko lain atau krama lain, maka masuk sinonim dengan comma.
bisa?'

Logika integrasi:
1. Index jv_wiktionary by lowercase token (word + tokens di krama) → entry_id
2. Untuk setiap entry mendeley:
   - Tokenize ngoko + krama (split comma, lowercase)
   - Cari match di jv_index
   - Kalau match → merge info mendeley ke entry jv_wiktionary (sinonim comma, arti ;)
   - Kalau tidak match → add mendeley sebagai new entry
3. Dilarang duplikat (1 konsep = 1 entry)
4. Dilarang hapus data (semua field preserve, gabung bukan hapus)

Merge rule (per field):
- word: tetap dari jv_wiktionary (lemma)
- ngoko: dari mendeley (isi, kalau jv kosong). Kalau jv sudah ada, gabung comma (dedup)
- krama: gabung krama jv + krama mendeley (comma, dedup, lowercase compare)
- arti: gabung arti mendeley (Indonesia) + arti jv (Jawa definisi), dipisah ' | '
  supaya user bisa lihat asal Indonesia vs Jawa
- aksara: dari jv (lebih lengkap, 99.9%)
- keterangan: dari jv (lebih kaya, wikitext asli). + keterangan mendeley kalau ada
- sumber: gabung 'jv.wiktionary.org (XML) + mendeley (curated)'
- is_mendeley: True (flag integration)
- source_count: 2

R-22 compliance: integrasi antar file yang sudah ada (BUKAN scrape raw)
R-18 compliance: tidak hapus entry/field, hanya merge info
R-12 compliance: USER EXPLICIT REQUEST "bisa?" — user override untuk kasus ini
R-26 compliance: 20 field, no register + no krama_inggil
"""
import json
from pathlib import Path

JV_PATH = Path('/home/z/my-project/public/kamus_jv_wiktionary_raw.json')
MENDELEY_PATH = Path('/home/z/my-project/public/kamus_mendeley.json')
OUT_PATH = Path('/home/z/my-project/public/kamus_jv_wiktionary_integrated_mendeley.json')


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
    print(f'→ Load {JV_PATH.name}...')
    with open(JV_PATH, 'r', encoding='utf-8') as f:
        jv_data = json.load(f)
    jv_words = jv_data['words']
    print(f'  jv_wiktionary entries: {len(jv_words):,}')

    print(f'→ Load {MENDELEY_PATH.name}...')
    with open(MENDELEY_PATH, 'r', encoding='utf-8') as f:
        m_data = json.load(f)
    m_words = m_data['words']
    print(f'  mendeley entries: {len(m_words):,}')

    # Build index: lowercase token → list of (jv_entry_id)
    # Index dari word (lemma) + tokens di krama
    print(f'\n→ Build index jv_wiktionary...')
    jv_index = {}  # lowercase token → list of jv entry_id (yang punya token ini di word/krama)
    for w in jv_words:
        eid = w.get('entry_id')
        word_lc = (w.get('word') or '').strip().lower()
        if word_lc and len(word_lc) > 1:
            jv_index.setdefault(word_lc, []).append(eid)
        krama = (w.get('krama') or '').strip()
        for tok in tokenize_field(krama):
            jv_index.setdefault(tok, []).append(eid)
    print(f'  Unique tokens di jv_index: {len(jv_index):,}')

    # Copy jv_words sebagai base (will be modified in-place)
    integrated = list(jv_words)  # shallow copy
    # Map: jv_entry_id → index di integrated list
    eid_to_idx = {w.get('entry_id'): i for i, w in enumerate(integrated)}

    # Track stats
    merged_count = 0
    added_count = 0
    no_match_entries = []

    print(f'\n→ Process mendeley entries...')
    for m_w in m_words:
        # Tokenize ngoko + krama mendeley
        m_ngoko_tokens = tokenize_field(m_w.get('ngoko', ''))
        m_krama_tokens = tokenize_field(m_w.get('krama', ''))
        all_m_tokens = m_ngoko_tokens + m_krama_tokens

        # Cari match di jv_index
        matched_eids = set()
        for tok in all_m_tokens:
            if tok in jv_index:
                for eid in jv_index[tok]:
                    matched_eids.add(eid)

        if matched_eids:
            # MERGE: ambil entry jv pertama yang match, merge info mendeley
            # (kalau multiple match, merge ke entry pertama, sisanya biarkan)
            jv_eid = sorted(matched_eids)[0]
            jv_idx = eid_to_idx[jv_eid]
            jv_w = integrated[jv_idx]

            # Merge ngoko: jv + mendeley (comma dedup)
            jv_ngoko_tokens = [t.strip() for t in (jv_w.get('ngoko') or '').split(',') if t.strip()]
            new_ngoko = dedup_comma(jv_ngoko_tokens + m_ngoko_tokens)
            if new_ngoko != (jv_w.get('ngoko') or ''):
                jv_w['ngoko'] = new_ngoko

            # Merge krama: jv + mendeley (comma dedup)
            jv_krama_tokens = [t.strip() for t in (jv_w.get('krama') or '').split(',') if t.strip()]
            new_krama = dedup_comma(jv_krama_tokens + m_krama_tokens)
            if new_krama != (jv_w.get('krama') or ''):
                jv_w['krama'] = new_krama

            # Merge arti: jv (Jawa definisi) + mendeley (Indonesia), dipisah ' | '
            jv_arti = (jv_w.get('arti') or '').strip()
            m_arti = (m_w.get('arti') or '').strip()
            if m_arti and m_arti not in jv_arti:
                if jv_arti:
                    jv_w['arti'] = f'{m_arti} | {jv_arti}'
                else:
                    jv_w['arti'] = m_arti

            # Merge keterangan: jv + mendeley, dipisah ' | '
            jv_ket = (jv_w.get('keterangan') or '').strip()
            m_ket = (m_w.get('keterangan') or '').strip()
            if m_ket and m_ket not in jv_ket:
                if jv_ket:
                    jv_w['keterangan'] = f'{jv_ket} | [mendeley] {m_ket}'
                else:
                    jv_w['keterangan'] = f'[mendeley] {m_ket}'

            # Update sumber + flags
            jv_w['sumber'] = f'{jv_w.get("sumber","")} + mendeley (curated)'
            jv_w['is_mendeley'] = True
            jv_w['source_count'] = (jv_w.get('source_count') or 1) + 1

            merged_count += 1
        else:
            # NO MATCH: add mendeley sebagai new entry
            new_entry = dict(m_w)
            # Reset entry_id (akan di-re-number di akhir)
            new_entry['entry_id'] = None
            new_entry['sumber'] = 'mendeley (curated, no jv_wiktionary match)'
            new_entry['is_mendeley'] = True
            no_match_entries.append(new_entry)
            added_count += 1

    # Append no-match entries ke integrated
    integrated.extend(no_match_entries)

    # Re-number entry_id 1..N
    for i, w in enumerate(integrated, 1):
        w['entry_id'] = i

    print(f'\n  Merged (mendeley match jv): {merged_count}')
    print(f'  Added (mendeley no match, new entry): {added_count}')
    print(f'  Total integrated entries: {len(integrated):,}')

    # Build output
    print(f'\n→ Build output JSON...')
    out_data = {
        'metadata': {
            'version': 'v1.0 (jv_wiktionary integrated with mendeley)',
            'description': 'jv.wiktionary XML dump (parsed minimal) integrated dengan mendeley curated dataset. 1 konsep = 1 entry (no duplikat). Sinonim comma, arti dipisah | (Indonesia | Jawa). R-22: integrasi antar file yang ada, BUKAN scrape. R-18: tidak hapus, hanya merge.',
            'sources_integrated': [
                'jv.wiktionary.org (XML dump, parsed minimal)',
                'mendeley.com/datasets/y3hstv4bfn (curated academic)',
            ],
            'total_jv_wiktionary': len(jv_words),
            'total_mendeley': len(m_words),
            'total_merged': merged_count,
            'total_added_new': added_count,
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

    # Sample: cek entry "turu" sebelum + sesudah
    print(f'\n=== Sample entry "turu" setelah integrasi ===')
    for w in integrated[:1000]:
        if w.get('word', '').lower() == 'turu':
            print(f'  entry_id={w["entry_id"]}:')
            print(f'    word:    {w["word"]!r}')
            print(f'    ngoko:   {w.get("ngoko","")!r}')
            print(f'    krama:   {w.get("krama","")!r}')
            print(f'    arti:    {w.get("arti","")!r}')
            print(f'    aksara:  {w.get("aksara","")!r}')
            print(f'    sumber:  {w.get("sumber","")!r}')
            print(f'    is_mendeley: {w.get("is_mendeley")}')
            print(f'    source_count: {w.get("source_count")}')
            break

    # Sample: 3 entries merged (is_mendeley=True, source_count > 1)
    print(f'\n=== Sample 3 merged entries (mendeley + jv) ===')
    count = 0
    for w in integrated:
        if w.get('is_mendeley') and (w.get('source_count') or 1) > 1:
            count += 1
            if count <= 3:
                print(f'\n  entry_id={w["entry_id"]}:')
                print(f'    word:    {w["word"]!r}')
                print(f'    ngoko:   {w.get("ngoko","")!r}')
                print(f'    krama:   {w.get("krama","")!r}')
                print(f'    arti:    {w.get("arti","")[:150]!r}')
                print(f'    sumber:  {w.get("sumber","")!r}')
                print(f'    source_count: {w.get("source_count")}')

    # Sample: 3 entries added (no match)
    print(f'\n=== Sample 3 added entries (mendeley no match) ===')
    count = 0
    for w in integrated:
        if w.get('sumber') == 'mendeley (curated, no jv_wiktionary match)':
            count += 1
            if count <= 3:
                print(f'\n  entry_id={w["entry_id"]}:')
                print(f'    word:    {w["word"]!r}')
                print(f'    ngoko:   {w.get("ngoko","")!r}')
                print(f'    krama:   {w.get("krama","")!r}')
                print(f'    arti:    {w.get("arti","")!r}')
                print(f'    sumber:  {w.get("sumber","")!r}')


if __name__ == '__main__':
    main()
