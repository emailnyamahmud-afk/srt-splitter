#!/usr/bin/env python3
"""cross-ref-ejaan-mendeley-jv.py — Cross-reference ejaan Mendeley vs jv.wiktionary dictionary.

User 10 Okt 2026: 'cros referensi dengan ejaan jv dictionary'

jv dictionary = jv.wiktionary.org (kamus Jawa Wiktionary, BUKAN lemma id.wiktionary).
Audit menunjukkan 46 dari 51 matches (90%) ejaan baku berasal dari jv.wiktionary PURE.

Script ini sebenarnya sama dengan cross-ref-ejaan-mendeley-lemma.py — broad index
sudah include jv.wiktionary. Tapi output sekarang explicitly tag sumber asal
ejaan baku (jv.wiktionary PURE / lemma PURE / lampiran PURE / dasanama PURE / merged).

R-22: cross-reference antar entries di kamus draft (BUKAN dari raw).
R-18: AI TIDAK auto-fix ejaan, hanya suggest dengan sumber asal.
R-16a: ejaan Jawa modern (é/è/ê). User native Jawa putuskan.
"""
import json
from collections import defaultdict, Counter
from pathlib import Path

DRAFT = Path('/home/z/my-project/public/kamus-jawa-draft.json')
MENDELEY = Path('/home/z/my-project/public/kamus_mendeley.json')
REPORT = Path('/home/z/my-project/public/cross-ref-ejaan-mendeley-jv.json')


def normalize_e_to_lowercase(s):
    """Normalize: lowercase + replace é/è/ê dengan e (untuk matching)."""
    if not s:
        return ''
    return s.lower().replace('é', 'e').replace('è', 'e').replace('ê', 'e')


def classify_source(s):
    """Classify sumber ke kategori PURE."""
    sl = s.lower()
    if 'jv.wiktionary' in s and 'merge' not in sl and 'mendeley' not in sl and 'lampiran' not in sl and 'dasanama' not in sl and 'jv:l' not in sl and 'angka' not in sl:
        return 'jv.wiktionary PURE'
    if 'id.wiktionary.org Kategori:jv:Lema (new)' in s:
        return 'lemma PURE'
    if 'mendeley' in s and 'merge' not in sl:
        return 'mendeley PURE'
    if 'lampiran' in s and 'merge' not in sl:
        return 'lampiran PURE'
    if 'dasanama' in s and 'merge' not in sl:
        return 'dasanama PURE'
    if 'angka' in s and 'merge' not in sl:
        return 'angka PURE'
    return 'merged/mixed'


# Load kamus draft
print(f'→ Load kamus draft...')
with open(DRAFT, 'r', encoding='utf-8') as f:
    draft_data = json.load(f)

# Build broad index: normalized → ejaan asli → set of source classes
print(f'→ Build broad index (all entries with diacritik, tag source class)...')
index = defaultdict(lambda: defaultdict(set))  # normalized → ejaan → {source classes}

for w in draft_data['words']:
    s = w.get('sumber', '')
    src_class = classify_source(s)
    for field in ['word', 'ngoko', 'krama']:
        val = (w.get(field) or '').strip()
        if not val:
            continue
        for tok in val.split(','):
            tok = tok.strip()
            if not tok or len(tok) < 2:
                continue
            if any(c in tok for c in ['é', 'è', 'ê']):
                normalized = normalize_e_to_lowercase(tok)
                index[normalized][tok].add(src_class)

# Statistik index
total_unique = len(index)
src_count = Counter()
for norm, ejaan_map in index.items():
    for ejaan, sources in ejaan_map.items():
        for s in sources:
            src_count[s] += 1
print(f'  Unique tokens dengan diakritik: {total_unique:,}')
for s, c in src_count.most_common():
    print(f'    {s:25} {c:>5}')
print()

# Load mendeley
print(f'→ Load mendeley...')
with open(MENDELEY, 'r', encoding='utf-8') as f:
    mendeley_data = json.load(f)

mendeley_words = mendeley_data['words']
print(f'  Mendeley entries: {len(mendeley_words):,}')
print()

# Cross-reference
print(f'→ Cross-reference Mendeley vs jv dictionary (broad index)...')
matches = []
total_checked = 0
for w in mendeley_words:
    for field in ['ngoko', 'krama']:
        val = (w.get(field) or '').strip()
        if not val:
            continue
        for tok in val.split(','):
            tok = tok.strip()
            if not tok or len(tok) < 2:
                continue
            total_checked += 1
            if any(c in tok for c in ['é', 'è', 'ê']):
                continue  # sudah baku
            normalized = normalize_e_to_lowercase(tok)
            if normalized in index:
                for baku_ejaan, sources in index[normalized].items():
                    if baku_ejaan.lower() != tok.lower():
                        matches.append({
                            'eid': w.get('entry_id'),
                            'field': field,
                            'mendeley_ejaan': tok,
                            'baku_ejaan': baku_ejaan,
                            'baku_sources': sorted(sources),
                            'mendeley_ngoko': w.get('ngoko', ''),
                            'mendeley_krama': w.get('krama', ''),
                            'mendeley_arti': w.get('arti', ''),
                        })

print(f'  Total tokens di Mendeley di-check: {total_checked:,}')
print(f'  Matches: {len(matches)}')
print()

# Source breakdown
print(f'=== Source breakdown (asal ejaan baku) ===')
src_counter = Counter()
for m in matches:
    for s in m['baku_sources']:
        src_counter[s] += 1
for s, c in src_counter.most_common():
    print(f'  {s:25} {c:>5}')
print()

# Tampilkan matches
print(f'=== {len(matches)} matches Mendeley (e polos) → baku (diakritik) ===')
print(f'User: baca konteks + sumber, apply manual via TUI (R-22: AI tidak auto-fix).')
print()
for i, m in enumerate(matches, 1):
    src_str = ', '.join(m['baku_sources'])
    print(f'{i:>3}. eid={m["eid"]:>3} [{m["field"]:6}] {m["mendeley_ejaan"]!r:25} → {m["baku_ejaan"]!r:25} ← {src_str}')

# Save report
print(f'\n→ Save report ke {REPORT.name}...')
with open(REPORT, 'w', encoding='utf-8') as f:
    json.dump({
        'summary': {
            'mendeley_count': len(mendeley_words),
            'broad_index_unique': total_unique,
            'matches_count': len(matches),
            'source_breakdown': dict(src_counter),
        },
        'matches': matches,
    }, f, ensure_ascii=False, indent=2)

print(f'  ✅ Saved: {REPORT} ({REPORT.stat().st_size:,} bytes)')
