#!/usr/bin/env python3
"""cross-ref-ejaan-mendeley-lemma.py — Cross-reference ejaan Mendeley vs lemma.

Tujuan: cari kata Mendeley (e polos) yang punya ejaan baku (dengan diakritik) di lemma.
Output: list cross-reference, user review manual, apply via TUI (R-22: AI tidak auto-fix).

Logika:
1. Index kata Jawa di lemma PURE (lowercase normalisasi → ejaan asli dengan diakritik)
2. Untuk setiap entry Mendeley, tokenize ngoko + krama (split comma)
3. Cari token yang match lemma index, TAPI ejaannya beda (lemma pakai diakritik, mendeley e polos)
4. Output: list of (mendeley_eid, token, mendeley_ejaan, lemma_ejaan, full mendeley entry)

R-22: cross-reference antar file di kamus draft (lemma + mendeley), BUKAN dari raw.
R-18: tidak hapus data, hanya suggest ejaan. User apply manual via TUI.
R-16a: ejaan Jawa modern (é/è/ê). Schwa = e polos. Taling = é. Dialek = è.
"""
import json
from collections import defaultdict
from pathlib import Path

DRAFT = Path('/home/z/my-project/public/kamus-jawa-draft.json')
MENDELEY = Path('/home/z/my-project/public/kamus_mendeley.json')

# Load kamus draft (untuk extract lemma PURE)
print(f'→ Load kamus draft...')
with open(DRAFT, 'r', encoding='utf-8') as f:
    draft_data = json.load(f)

# Index lemma PURE: lowercase (e polos) → list of (ejaan asli, sumber)
# Key: token lowercase dengan "e" sebagai pengganti semua é/è/ê
# Value: list of ejaan asli dengan diakritik
lemma_index = defaultdict(set)  # normalized → {ejaan_asli_1, ejaan_asli_2, ...}

PURE_LEMMA_SUMBER = 'id.wiktionary.org Kategori:jv:Lema (new)'
lemma_pure = [w for w in draft_data['words'] if w.get('sumber', '') == PURE_LEMMA_SUMBER]
print(f'  PURE lemma entries: {len(lemma_pure):,}')

def normalize_e_to_lowercase(s):
    """Normalize: lowercase + replace é/è/ê dengan e (untuk matching)."""
    if not s:
        return ''
    return s.lower().replace('é', 'e').replace('è', 'e').replace('ê', 'e')

# Build broad index dari SEMUA kamus draft entries yang pakai diakritik
# (tidak hanya PURE lemma — PURE lemma hanya 19 unique, tidak ada match)
print(f'→ Build broad index dari kamus draft (semua entries dengan diakritik)...')
for w in draft_data['words']:
    for field in ['word', 'ngoko', 'krama']:
        val = (w.get(field) or '').strip()
        if not val:
            continue
        for tok in val.split(','):
            tok = tok.strip()
            if not tok or len(tok) < 2:
                continue
            has_diacritik = any(c in tok for c in ['é', 'è', 'ê'])
            if has_diacritik:
                normalized = normalize_e_to_lowercase(tok)
                lemma_index[normalized].add(tok)

print(f'  Unique tokens dengan diakritik (broad): {len(lemma_index):,}')
print()

# Load kamus mendeley
print(f'→ Load kamus mendeley...')
with open(MENDELEY, 'r', encoding='utf-8') as f:
    mendeley_data = json.load(f)

mendeley_words = mendeley_data['words']
print(f'  Mendeley entries: {len(mendeley_words):,}')
print()

# Cross-reference
print(f'→ Cross-reference Mendeley vs lemma (cari ejaan baku)...')
matches = []  # list of dict {eid, token, mendeley_ejaan, lemma_ejaan, mendeley_entry}
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
            # Skip kalau tok sudah pakai diakritik (sudah baku)
            if any(c in tok for c in ['é', 'è', 'ê']):
                continue
            # Normalize + cari di lemma index
            normalized = normalize_e_to_lowercase(tok)
            if normalized in lemma_index:
                lemma_ejaan_list = lemma_index[normalized]
                # Hanya match kalau ejaan lemma beda (ada diakritik)
                for lemma_ejaan in lemma_ejaan_list:
                    if lemma_ejaan != tok:  # beda ejaan
                        matches.append({
                            'eid': w.get('entry_id'),
                            'field': field,
                            'mendeley_ejaan': tok,
                            'lemma_ejaan': lemma_ejaan,
                            'mendeley_ngoko': w.get('ngoko', ''),
                            'mendeley_krama': w.get('krama', ''),
                            'mendeley_arti': w.get('arti', ''),
                        })

print(f'  Total tokens di Mendeley di-check: {total_checked:,}')
print(f'  Matches ketemu (mendeley e polos vs lemma diakritik): {len(matches)}')
print()

# Tampilkan semua matches (max 50 untuk readability)
print(f'=== CROSS-REFERENCE Mendeley → Lemma (ejaan baku) ===')
print(f'User: baca konteks, putuskan apply ejaan lemma ke mendeley via TUI.')
print()

for i, m in enumerate(matches[:50], 1):
    print(f'{i:>3}. entry_id={m["eid"]} [{m["field"]}]')
    print(f'     Mendeley: {m["mendeley_ejaan"]!r}')
    print(f'     Lemma:    {m["lemma_ejaan"]!r}')
    print(f'     Full Mendeley entry:')
    print(f'       ngoko: {m["mendeley_ngoko"]!r}')
    print(f'       krama: {m["mendeley_krama"]!r}')
    print(f'       arti:  {m["mendeley_arti"]!r}')
    print()

if len(matches) > 50:
    print(f'... +{len(matches) - 50} more matches')

# Save full report ke file
REPORT = Path('/home/z/my-project/public/cross-ref-ejaan-mendeley-lemma.json')
with open(REPORT, 'w', encoding='utf-8') as f:
    json.dump({
        'summary': {
            'lemma_pure_count': len(lemma_pure),
            'lemma_with_diacritik_unique': len(lemma_index),
            'mendeley_count': len(mendeley_words),
            'matches_count': len(matches),
        },
        'matches': matches,
    }, f, ensure_ascii=False, indent=2)
print(f'\nFull report: {REPORT}')
