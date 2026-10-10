#!/usr/bin/env python3
"""bikin-kamus-lemma.py — Filter subset is_lemma=True dari kamus-jawa-draft.json.

Tujuan: kerja bertahap. Kamus draft = campur 5+ sumber (Wiktionary lemma,
Wiktionary ngoko, Mendeley, Dasanama, Lampiran, Angka). Banyak sumber = banyak
sampah. Lemma = sumber paling bersih (id.wiktionary.org Kategori:jv:Lema).

Output: public/kamus_lemma.json — subset dengan is_lemma=True saja.
Total entries: ~1.816 (dari audit sebelumnya).

R-22 compliance: TIDAK parsing dari raw. Hanya filter subset dari kamus draft
yang sudah ada. Data utuh, tidak diubah, hanya di-filter berdasarkan is_lemma.

R-18 compliance: TIDAK hapus entry. Kamus draft tetap utuh 44.005 entries
(di public/kamus-jawa-draft.json + backup .bak). kamus_lemma.json = file baru,
subset, untuk kerja bertahap.
"""
import json
from pathlib import Path

SRC = Path('/home/z/my-project/public/kamus-jawa-draft.json')
DST = Path('/home/z/my-project/public/kamus_lemma.json')

print(f'→ Load {SRC.name}...')
with open(SRC, 'r', encoding='utf-8') as f:
    data = json.load(f)

total = len(data['words'])
print(f'  Total entries (kamus draft): {total:,}')

# Filter is_lemma=True
lemma_words = [w for w in data['words'] if w.get('is_lemma')]
lemma_count = len(lemma_words)
print(f'  is_lemma=True:               {lemma_count:,} ({lemma_count*100/total:.2f}%)')

# Build subset kamus
subset = dict(data)
subset['words'] = lemma_words
subset['metadata'] = {
    **data.get('metadata', {}),
    'version': 'v1.0 (lemma subset)',
    'description': 'Kamus lemma-only — subset dari kamus-jawa-draft.json. Filter: is_lemma=True. Tujuan: kerja bertahap, mulai dari lemma bersih (id.wiktionary.org Kategori:jv:Lema), tidak tercampur sampah sumber lain (mendeley/dasanama/lampiran/angka).',
    'source_filter': 'is_lemma=True',
    'total_subset': lemma_count,
    'total_full': total,
    'parent_file': 'kamus-jawa-draft.json',
}

# Re-number entry_id supaya 1..N urut di subset
for i, w in enumerate(subset['words'], 1):
    w['entry_id'] = i

print(f'\n→ Write ke {DST.name}...')
with open(DST, 'w', encoding='utf-8') as f:
    json.dump(subset, f, ensure_ascii=False, indent=2)

size = DST.stat().st_size
print(f'  ✅ Saved: {DST}')
print(f'  Size: {size:,} bytes ({size/1024/1024:.2f} MB)')

# Verify: sample 3 entries
print(f'\n→ Sample 3 entries pertama dari kamus_lemma.json:')
for w in lemma_words[:3]:
    print(f'\n  entry_id={w["entry_id"]}:')
    print(f'    word:     {w.get("word", "")!r}')
    print(f'    ngoko:    {w.get("ngoko", "")!r}')
    print(f'    krama:    {w.get("krama", "")!r}')
    print(f'    arti:     {w.get("arti", "")!r}')
    print(f'    aksara:   {w.get("aksara", "")!r}')
    print(f'    sumber:   {w.get("sumber", "")[:80]!r}')
    print(f'    is_lemma: {w.get("is_lemma")}')
    ket = w.get('keterangan', '')
    if ket:
        print(f'    keterangan (first 200 chars):')
        for line in ket[:200].split('\n'):
            print(f'      {line}')

# Statistik kelengkapan subset lemma
print(f'\n→ Statistik kelengkapan subset lemma:')
n_paired = sum(1 for w in lemma_words if (w.get('ngoko') or '').strip() and (w.get('krama') or '').strip() and (w.get('arti') or '').strip())
n_netral = sum(1 for w in lemma_words if (w.get('word') or '').strip() and not (w.get('ngoko') or '').strip() and not (w.get('krama') or '').strip())
n_with_ket = sum(1 for w in lemma_words if (w.get('keterangan') or '').strip())
n_with_aksara = sum(1 for w in lemma_words if (w.get('aksara') or '').strip())
n_arti_real = sum(1 for w in lemma_words if (w.get('arti') or '').strip() and (w.get('arti') or '').strip() != (w.get('word') or '').strip())
n_arti_fallback = sum(1 for w in lemma_words if (w.get('arti') or '').strip() and (w.get('arti') or '').strip() == (w.get('word') or '').strip())

print(f'  Total entries:           {lemma_count:,}')
print(f'  PAIRED 3-field:           {n_paired:,} ({n_paired*100/lemma_count:.1f}%)')
print(f'  NETRAL (word+arti):       {n_netral:,} ({n_netral*100/lemma_count:.1f}%)')
print(f'  Punya keterangan:        {n_with_ket:,} ({n_with_ket*100/lemma_count:.1f}%)')
print(f'  Punya aksara:            {n_with_aksara:,} ({n_with_aksara*100/lemma_count:.1f}%)')
print(f'  arti Indonesia real:     {n_arti_real:,} ({n_arti_real*100/lemma_count:.1f}%)')
print(f'  arti = word fallback:    {n_arti_fallback:,} ({n_arti_fallback*100/lemma_count:.1f}%)')
