#!/usr/bin/env python3
"""bikin-kamus-mendeley.py — Filter PURE mendeley dari kamus-jawa-draft.json.

Tujuan: kerja bertahap. Mendeley dataset = curated (penelitian akademik),
paling terpercaya karena bukan parsing AI dari internet sampah.

Filter ketat:
  sumber = 'data.mendeley.com/datasets/y3hstv4bfn (new)' EXACTLY
  (tidak ada '+ wiktionary', '+ merge', '+ lampiran', dll — yang berarti
  sudah di-merge dengan sumber lain, rawan halu)

Output: public/kamus_mendeley.json — 145 entries PURE mendeley.

R-22: TIDAK parsing dari raw. Filter subset dari kamus draft yang sudah ada.
R-18: Kamus draft tetap utuh 44.005 (di .json + .bak). Kamus mendeley = file baru.
"""
import json
from pathlib import Path

SRC = Path('/home/z/my-project/public/kamus-jawa-draft.json')
DST = Path('/home/z/my-project/public/kamus_mendeley.json')
PURE_SUMBER = 'data.mendeley.com/datasets/y3hstv4bfn (new)'

print(f'→ Load {SRC.name}...')
with open(SRC, 'r', encoding='utf-8') as f:
    data = json.load(f)

total = len(data['words'])
print(f'  Total entries (kamus draft): {total:,}')

# Filter PURE mendeley (sumber exact match, no merge)
mendeley_words = [w for w in data['words'] if w.get('sumber', '') == PURE_SUMBER]
m_count = len(mendeley_words)
print(f'  PURE mendeley (sumber exact): {m_count:,} ({m_count*100/total:.2f}%)')

# Build subset
subset = dict(data)
subset['words'] = mendeley_words
subset['metadata'] = {
    **data.get('metadata', {}),
    'version': 'v1.0 (mendeley pure subset)',
    'description': 'Kamus Mendeley PURE — subset dari kamus-jawa-draft.json. Filter: sumber = "data.mendeley.com/datasets/y3hstv4bfn (new)" exact (no merge with wiktionary/lampiran/dasanama/lemma/angka). Mendeley = curated academic dataset, paling terpercaya, bukan parsing AI dari internet sampah.',
    'source_filter': f"sumber == '{PURE_SUMBER}'",
    'total_subset': m_count,
    'total_full': total,
    'parent_file': 'kamus-jawa-draft.json',
}

# Re-number entry_id
for i, w in enumerate(subset['words'], 1):
    w['entry_id'] = i

# Write
print(f'\n→ Write ke {DST.name}...')
with open(DST, 'w', encoding='utf-8') as f:
    json.dump(subset, f, ensure_ascii=False, indent=2)

size = DST.stat().st_size
print(f'  ✅ Saved: {DST}')
print(f'  Size: {size:,} bytes ({size/1024/1024:.2f} MB)')

# Statistik
print(f'\n→ Statistik kamus_mendeley.json:')
n_paired = sum(1 for w in mendeley_words if (w.get('ngoko') or '').strip() and (w.get('krama') or '').strip() and (w.get('arti') or '').strip())
n_with_ket = sum(1 for w in mendeley_words if (w.get('keterangan') or '').strip())
n_with_aksara = sum(1 for w in mendeley_words if (w.get('aksara') or '').strip())
n_with_mid = sum(1 for w in mendeley_words if (w.get('mendeley_id') or '').strip())

print(f'  Total entries:           {m_count:,}')
print(f'  PAIRED 3-field:           {n_paired:,} ({n_paired*100/m_count:.1f}%)')
print(f'  Punya keterangan:        {n_with_ket:,} ({n_with_ket*100/m_count:.1f}%)')
print(f'  Punya aksara:            {n_with_aksara:,} ({n_with_aksara*100/m_count:.1f}%)')
print(f'  Punya mendeley_id:       {n_with_mid:,} ({n_with_mid*100/m_count:.1f}%)')

# Sample 5
print(f'\n→ Sample 5 entries pertama:')
for w in mendeley_words[:5]:
    print(f'\n  entry_id={w["entry_id"]}:')
    print(f'    word:        {w.get("word", "")!r}')
    print(f'    ngoko:       {w.get("ngoko", "")!r}')
    print(f'    krama:       {w.get("krama", "")!r}')
    print(f'    arti:        {w.get("arti", "")!r}')
    print(f'    aksara:      {w.get("aksara", "")!r}')
    print(f'    mendeley_id: {w.get("mendeley_id", "")!r}')
    ket = w.get('keterangan', '')
    if ket:
        print(f'    keterangan:  {ket[:150]!r}')
    else:
        print(f'    keterangan:  (KOSONG)')
