#!/usr/bin/env python3
"""cross-ref-ejaan-mendeley-all-fields.py — Cross-reference ejaan Mendeley vs
SEMUA field kamus draft (word, ngoko, krama, lemma_words, arti, keterangan).

User 10 Okt 2026: 'jangan hanya ngoko dan krama, karena di jv wictionary,
masih banyak yg umum, ejaan umum belum masuk parsing ejaan.'

Sebelumnya cross-ref hanya index word+ngoko+krama (9.837 unique tokens).
Sekarang index SEMUA field yang punya teks Jawa:
- word (8.785 unique tokens dengan diakritik)
- ngoko (882)
- krama (425)
- lemma_words (62)
- arti (8.764) — bisa berisi kata Jawa karena fallback=word
- keterangan (7.610) — konteks Jawa, banyak ejaan baku

Total broad index: ~26.000+ unique tokens (vs 9.837 sebelumnya).

Untuk field lemma list (word, ngoko, krama, lemma_words): split comma.
Untuk field kalimat (arti, keterangan): regex extract kata dengan diakritik.

R-22: cross-reference antar entries di kamus draft, BUKAN dari raw.
R-18: AI TIDAK auto-fix ejaan, hanya suggest dengan sumber asal.
R-16a: ejaan Jawa modern (é/è/ê). User native Jawa putuskan.
"""
import json
import re
from collections import defaultdict, Counter
from pathlib import Path

DRAFT = Path('/home/z/my-project/public/kamus-jawa-draft.json')
MENDELEY = Path('/home/z/my-project/public/kamus_mendeley.json')
REPORT = Path('/home/z/my-project/public/cross-ref-ejaan-mendeley-all-fields.json')

# Field yang berisi lemma list (split comma)
LEMMA_FIELDS = ['word', 'ngoko', 'krama', 'lemma_words']
# Field yang berisi kalimat/definisi (regex extract kata dengan diakritik)
SENTENCE_FIELDS = ['arti', 'keterangan']

# Regex: kata dengan diakritik é/è/ê (word boundary, alphanumeric + diakritik)
DIACRITIK_PATTERN = re.compile(r'\b\w*[éèê]\w*\b', re.IGNORECASE)


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


def extract_tokens_with_diacritik(val, is_lemma_field):
    """Extract tokens dengan diakritik dari value.
    
    Untuk lemma field (word/ngoko/krama/lemma_words): split comma, strip.
    Untuk sentence field (arti/keterangan): regex extract kata dengan diakritik.
    """
    if not val or not isinstance(val, str):
        return []
    tokens = []
    if is_lemma_field:
        for tok in val.split(','):
            tok = tok.strip()
            if tok and len(tok) > 1 and any(c in tok for c in ['é', 'è', 'ê']):
                tokens.append(tok)
    else:
        # Sentence field: extract kata dengan diakritik
        for tok in DIACRITIK_PATTERN.findall(val):
            if len(tok) > 1:
                tokens.append(tok)
    return tokens


# Load kamus draft
print(f'→ Load kamus draft...')
with open(DRAFT, 'r', encoding='utf-8') as f:
    draft_data = json.load(f)

# Build broad index: normalized → ejaan asli → set of source classes
# Track juga asal field (word/ngoko/krama/lemma_words/arti/keterangan)
print(f'→ Build broad index dari SEMUA field dengan teks Jawa...')
index = defaultdict(lambda: defaultdict(set))  # normalized → ejaan → {source classes}
field_token_count = Counter()  # field → count of tokens with diakritik

for w in draft_data['words']:
    s = w.get('sumber', '')
    src_class = classify_source(s)
    
    for field in LEMMA_FIELDS + SENTENCE_FIELDS:
        val = w.get(field, '')
        is_lemma = field in LEMMA_FIELDS
        tokens = extract_tokens_with_diacritik(val, is_lemma)
        for tok in tokens:
            field_token_count[field] += 1
            normalized = normalize_e_to_lowercase(tok)
            index[normalized][tok].add(src_class)

# Statistik index
total_unique = len(index)
print(f'  Unique tokens dengan diakritik (SEMUA field): {total_unique:,}')
print(f'  Token count per field:')
for f, c in field_token_count.most_common():
    print(f'    {f:15} {c:>6,}')

# Source breakdown di index
src_count = Counter()
for norm, ejaan_map in index.items():
    for ejaan, sources in ejaan_map.items():
        for s in sources:
            src_count[s] += 1
print(f'\n  Source breakdown di index:')
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

# Cross-reference: cek token di ngoko + krama Mendeley vs broad index
print(f'→ Cross-reference Mendeley (ngoko + krama) vs broad index SEMUA field...')
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

# Source breakdown di matches
print(f'=== Source breakdown (asal ejaan baku di matches) ===')
src_counter = Counter()
for m in matches:
    for s in m['baku_sources']:
        src_counter[s] += 1
for s, c in src_counter.most_common():
    print(f'  {s:25} {c:>5}')
print()

# Compare dengan cross-ref sebelumnya (51 matches)
print(f'=== Comparison ===')
print(f'  Cross-ref sebelumnya (word+ngoko+krama only): 51 matches')
print(f'  Cross-ref sekarang (SEMUA field):              {len(matches)} matches')
print()

# Tampilkan matches baru (yang tidak ada di 51 sebelumnya)
# Load old report untuk compare
old_report_path = Path('/home/z/my-project/public/cross-ref-ejaan-mendeley-jv.json')
if old_report_path.exists():
    with open(old_report_path, 'r', encoding='utf-8') as f:
        old_report = json.load(f)
    old_keys = set((m['eid'], m['field'], m['mendeley_ejaan'], m['baku_ejaan'] if 'baku_ejaan' in m else m.get('lemma_ejaan', '')) for m in old_report['matches'])
    new_matches = [m for m in matches if (m['eid'], m['field'], m['mendeley_ejaan'], m['baku_ejaan']) not in old_keys]
    print(f'  NEW matches (tidak ada di report sebelumnya): {len(new_matches)}')
    print()
    if new_matches:
        print(f'=== NEW matches (ejaan baku dari arti/keterangan/lemma_words) ===')
        for i, m in enumerate(new_matches, 1):
            src_str = ', '.join(m['baku_sources'])
            print(f'{i:>3}. eid={m["eid"]:>3} [{m["field"]:6}] {m["mendeley_ejaan"]!r:25} → {m["baku_ejaan"]!r:25} ← {src_str}')

# Save report
print(f'\n→ Save report ke {REPORT.name}...')
with open(REPORT, 'w', encoding='utf-8') as f:
    json.dump({
        'summary': {
            'mendeley_count': len(mendeley_words),
            'broad_index_unique_all_fields': total_unique,
            'field_token_count': dict(field_token_count),
            'matches_count': len(matches),
            'source_breakdown': dict(src_counter),
        },
        'matches': matches,
    }, f, ensure_ascii=False, indent=2)

print(f'  ✅ Saved: {REPORT} ({REPORT.stat().st_size:,} bytes)')
