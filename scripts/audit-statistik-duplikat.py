#!/usr/bin/env python3
"""audit-statistik-duplikat.py — Audit statistik + scan duplikat global kamus.

Logika sama persis dengan detect_duplicates() di kamus-tui.py:
- Tokenize ngoko/krama/arti/word (split comma, lowercase, skip 1-char)
- 4 kategori same-field duplikat (kata sama di field yang sama, beda entry)
- 6 kategori cross-field (kata di field1 entry A = field2 entry B, beda entry)

Output: statistik penuh + semua kategori duplikat dengan count.
"""
import json
from collections import defaultdict, Counter
from pathlib import Path

KAMUS = Path('/home/z/my-project/public/kamus-jawa-draft.json')

with open(KAMUS, 'r', encoding='utf-8') as f:
    data = json.load(f)

words = data['words']
total = len(words)
print(f'══════════════════════════════════════════════════════════════════════')
print(f'  AUDIT STATISTIK + SCAN DUPLIKAT GLOBAL — {total:,} entries')
print(f'══════════════════════════════════════════════════════════════════════')
print()

# ============ STATISTIK UMUM ============
print('=== STATISTIK UMUM ===')
print(f'  Total entries:    {total:,}')

# Komposisi kelengkapan
has_word = sum(1 for w in words if (w.get('word') or '').strip())
has_ngoko = sum(1 for w in words if (w.get('ngoko') or '').strip())
has_krama = sum(1 for w in words if (w.get('krama') or '').strip())
has_arti = sum(1 for w in words if (w.get('arti') or '').strip())
has_aksara = sum(1 for w in words if (w.get('aksara') or '').strip())
has_keterangan = sum(1 for w in words if (w.get('keterangan') or '').strip())

# NETRAL (R-21)
netral = sum(1 for w in words if (w.get('word') or '').strip() and not (w.get('ngoko') or '').strip() and not (w.get('krama') or '').strip())
paired_3field = sum(1 for w in words if (w.get('ngoko') or '').strip() and (w.get('krama') or '').strip() and (w.get('arti') or '').strip())
ngoko_only = sum(1 for w in words if (w.get('ngoko') or '').strip() and not (w.get('krama') or '').strip() and not (w.get('arti') or '').strip())
ngoko_krama = sum(1 for w in words if (w.get('ngoko') or '').strip() and (w.get('krama') or '').strip() and not (w.get('arti') or '').strip())
ngoko_arti = sum(1 for w in words if (w.get('ngoko') or '').strip() and not (w.get('krama') or '').strip() and (w.get('arti') or '').strip())
no_ngoko = sum(1 for w in words if not (w.get('ngoko') or '').strip())

print(f'\n  Field terisi:')
print(f'    word:        {has_word:>6,} ({has_word*100/total:.2f}%)')
print(f'    ngoko:       {has_ngoko:>6,} ({has_ngoko*100/total:.2f}%)')
print(f'    krama:       {has_krama:>6,} ({has_krama*100/total:.2f}%)')
print(f'    arti:        {has_arti:>6,} ({has_arti*100/total:.2f}%)')
print(f'    aksara:      {has_aksara:>6,} ({has_aksara*100/total:.2f}%)')
print(f'    keterangan:  {has_keterangan:>6,} ({has_keterangan*100/total:.2f}%)')

print(f'\n  Komposisi kelengkapan:')
print(f'    0. NETRAL (word+arti, ngoko+krama kosong): {netral:>6,} ({netral*100/total:.2f}%)')
print(f'    1. ngoko saja:                              {ngoko_only:>6,} ({ngoko_only*100/total:.2f}%)')
print(f'    2. ngoko + krama (perlu arti):              {ngoko_krama:>6,} ({ngoko_krama*100/total:.2f}%)')
print(f'    3. ngoko + arti (perlu krama):                {ngoko_arti:>6,} ({ngoko_arti*100/total:.2f}%)')
print(f'    4. ngoko + krama + arti (LENGKAP):           {paired_3field:>6,} ({paired_3field*100/total:.2f}%)')
print(f'    5. no ngoko (orphan):                       {no_ngoko:>6,} ({no_ngoko*100/total:.2f}%)')

# Statistik "arti=word fallback"
arti_eq_word = sum(1 for w in words if (w.get('arti') or '').strip() == (w.get('word') or '').strip() and (w.get('arti') or '').strip())
arti_real = has_arti - arti_eq_word
print(f'\n  Analisa arti (CRITICAL):')
print(f'    arti total terisi:        {has_arti:>6,}')
print(f'    arti = word (fallback):   {arti_eq_word:>6,} ({arti_eq_word*100/total:.2f}%) — BUKAN Indonesia')
print(f'    arti Indonesia real:      {arti_real:>6,} ({arti_real*100/total:.2f}%) — paired + ngoko+arti')

# Source flags
print(f'\n  Source flags:')
for flag in ['is_lemma', 'is_mendeley', 'is_dasanama', 'is_angka', 'is_lampiran']:
    count = sum(1 for w in words if w.get(flag))
    print(f'    {flag:15} {count:>6,}')

# Status
print(f'\n  Status:')
status_count = Counter(w.get('status', 'draft') for w in words)
for s, c in status_count.most_common():
    print(f'    {s:15} {c:>6,}')

# Register
print(f'\n  Register (raw label):')
reg_count = Counter(w.get('register', '') for w in words)
for r, c in reg_count.most_common():
    print(f'    {r!r:20} {c:>6,}')

# Kelas
print(f'\n  Kelas (linguistik):')
kelas_count = Counter(w.get('kelas', '') for w in words)
for k, c in kelas_count.most_common(10):
    print(f'    {k!r:20} {c:>6,}')

# ============ SCAN DUPLIKAT ============
print(f'\n\n=== SCAN DUPLIKAT GLOBAL ===')

# Build index untuk semua field
ngoko_idx = defaultdict(list)
krama_idx = defaultdict(list)
word_idx = defaultdict(list)
arti_idx = defaultdict(list)

for i, k in enumerate(words):
    ng = (k.get('ngoko', '') or '').strip().lower()
    kr = (k.get('krama', '') or '').strip().lower()
    word = (k.get('word', '') or '').strip().lower()
    ar = (k.get('arti', '') or '').strip().lower()
    ar_raw = (k.get('arti', '') or '').strip()[:60]
    word_raw = (k.get('word', '') or '').strip()[:40]
    ket = (k.get('keterangan', '') or '').strip()[:60]
    eid = k.get('entry_id', '?')

    for t in ng.split(','):
        t = t.strip()
        if t and len(t) > 1:
            ngoko_idx[t].append((i, eid, ar_raw, ket, word_raw))
    for t in kr.split(','):
        t = t.strip()
        if t and len(t) > 1:
            krama_idx[t].append((i, eid, ar_raw, ket, word_raw))
    for t in word.split(','):
        t = t.strip()
        if t and len(t) > 1:
            word_idx[t].append((i, eid, ar_raw, ket, word_raw))
    for t in ar.split(','):
        t = t.strip()
        if t and len(t) > 1:
            arti_idx[t].append((i, eid, ar_raw, ket, word_raw))

# Total tokens per field
print(f'\n  Total tokens (split by comma):')
print(f'    ngoko:  {len(ngoko_idx):>6,} unique tokens (dari {has_ngoko:,} entries terisi)')
print(f'    krama:  {len(krama_idx):>6,} unique tokens (dari {has_krama:,} entries terisi)')
print(f'    word:   {len(word_idx):>6,} unique tokens (dari {has_word:,} entries terisi)')
print(f'    arti:   {len(arti_idx):>6,} unique tokens (dari {has_arti:,} entries terisi)')

# Find dupes same-field
dupes_ngoko = {t: v for t, v in ngoko_idx.items() if len(v) > 1}
dupes_krama = {t: v for t, v in krama_idx.items() if len(v) > 1}
dupes_word = {t: v for t, v in word_idx.items() if len(v) > 1}
dupes_arti = {t: v for t, v in arti_idx.items() if len(v) > 1}

print(f'\n  📊 Duplikat SAME-FIELD (kata sama di field yang sama, beda entry):')
print(f'    1. Duplikat ngoko:  {len(dupes_ngoko):>5,} tokens (dari {len(ngoko_idx):,} unique)')
print(f'    2. Duplikat krama:  {len(dupes_krama):>5,} tokens (dari {len(krama_idx):,} unique)')
print(f'    3. Duplikat word:   {len(dupes_word):>5,} tokens (dari {len(word_idx):,} unique)')
print(f'    4. Duplikat arti:  {len(dupes_arti):>5,} tokens (dari {len(arti_idx):,} unique)')

# Cross-field helper
def find_cross(idx1, idx2):
    cross = {}
    for t in idx1:
        if t in idx2:
            e1 = idx1[t]
            e2 = idx2[t]
            has_cross = False
            for a in e1:
                for b in e2:
                    if a[0] != b[0]:
                        has_cross = True
                        break
                if has_cross:
                    break
            if has_cross:
                cross[t] = (e1, e2)
    return cross

# All cross-field pairs
cross_ng_kr = find_cross(ngoko_idx, krama_idx)
cross_ng_ar = find_cross(ngoko_idx, arti_idx)
cross_kr_ar = find_cross(krama_idx, arti_idx)
cross_word_ng = find_cross(word_idx, ngoko_idx)
cross_word_kr = find_cross(word_idx, krama_idx)
cross_word_ar = find_cross(word_idx, arti_idx)

total_cross = (len(cross_ng_kr) + len(cross_ng_ar) + len(cross_kr_ar) +
               len(cross_word_ng) + len(cross_word_kr) + len(cross_word_ar))

print(f'\n  📊 Duplikat CROSS-FIELD (kata di field1 entry A = field2 entry B, beda entry):')
print(f'    5. ngoko↔krama:    {len(cross_ng_kr):>5,} tokens')
print(f'    6. ngoko↔arti:     {len(cross_ng_ar):>5,} tokens')
print(f'    7. krama↔arti:     {len(cross_kr_ar):>5,} tokens')
print(f'    8. word↔ngoko:      {len(cross_word_ng):>5,} tokens (NETRAL duplikat di paired)')
print(f'    9. word↔krama:     {len(cross_word_kr):>5,} tokens (NETRAL duplikat di paired)')
print(f'    10. word↔arti:     {len(cross_word_ar):>5,} tokens (NETRAL duplikat di paired)')
print(f'\n  TOTAL cross-field: {total_cross:,} tokens')

# Total summary
total_dupes = (len(dupes_ngoko) + len(dupes_krama) + len(dupes_word) + len(dupes_arti) +
               total_cross)
print(f'\n  📊 TOTAL semua duplikat (same-field + cross-field): {total_dupes:,} tokens')

# ============ TOP 20 PER KATEGORI ============
print(f'\n\n=== TOP 20 PER KATEGORI ===')

def print_top_dupes(label, dupes_dict, max_show=20):
    sorted_d = sorted(dupes_dict.items(), key=lambda x: len(x[1]), reverse=True)
    print(f'\n--- {label} (top {min(max_show, len(sorted_d))} dari {len(sorted_d):,}) ---')
    for token, entries in sorted_d[:max_show]:
        unique_eids = set(e[1] for e in entries)
        print(f"  '{token}' di {len(unique_eids)} entries:")

def print_top_cross(label, cross_dict, max_show=20):
    sorted_c = sorted(cross_dict.items(),
                     key=lambda x: len(x[1][0]) + len(x[1][1]),
                     reverse=True)
    print(f'\n--- {label} (top {min(max_show, len(sorted_c))} dari {len(sorted_c):,}) ---')
    for token, (e1, e2) in sorted_c[:max_show]:
        print(f"  '{token}' di {len(e1)} entries (field1) + {len(e2)} entries (field2):")

print_top_dupes('1. Duplikat ngoko', dupes_ngoko)
print_top_dupes('2. Duplikat krama', dupes_krama)
print_top_dupes('3. Duplikat word (NETRAL)', dupes_word)
print_top_dupes('4. Duplikat arti (Indonesia)', dupes_arti)
print_top_cross('5. Cross ngoko↔krama', cross_ng_kr)
print_top_cross('6. Cross ngoko↔arti', cross_ng_ar)
print_top_cross('7. Cross krama↔arti', cross_kr_ar)
print_top_cross('8. Cross word↔ngoko (NETRAL paired)', cross_word_ng)
print_top_cross('9. Cross word↔krama (NETRAL paired)', cross_word_kr)
print_top_cross('10. Cross word↔arti (NETRAL paired)', cross_word_ar)

# ============ SAMPLE DETAIL 5 PER KATEGORI ============
print(f'\n\n=== SAMPLE DETAIL (5 per kategori) ===')

def print_sample_same_field(label, dupes_dict, field_name, max_show=5):
    sorted_d = sorted(dupes_dict.items(), key=lambda x: len(x[1]), reverse=True)
    print(f'\n--- {label} ---')
    for token, entries in sorted_d[:max_show]:
        print(f"\n  Token: '{token}'")
        for idx, eid, ar, ket, word_raw in entries[:5]:
            print(f"    [{eid}] word={word_raw!r} arti={ar[:50]!r}")
            if ket:
                print(f"          ket={ket[:60]!r}")

def print_sample_cross(label, cross_dict, field1, field2, max_show=5):
    sorted_c = sorted(cross_dict.items(),
                     key=lambda x: len(x[1][0]) + len(x[1][1]),
                     reverse=True)
    print(f'\n--- {label} ---')
    for token, (e1, e2) in sorted_c[:max_show]:
        print(f"\n  Token: '{token}'")
        for idx, eid, ar, ket, word_raw in e1[:3]:
            print(f"    {field1:6} [{eid}] word={word_raw!r} arti={ar[:50]!r}")
        for idx, eid, ar, ket, word_raw in e2[:3]:
            print(f"    {field2:6} [{eid}] word={word_raw!r} arti={ar[:50]!r}")

print_sample_same_field('1. Duplikat ngoko', dupes_ngoko, 'ngoko')
print_sample_same_field('2. Duplikat krama', dupes_krama, 'krama')
print_sample_same_field('3. Duplikat word (NETRAL)', dupes_word, 'word')
print_sample_same_field('4. Duplikat arti (Indonesia)', dupes_arti, 'arti')
print_sample_cross('5. Cross ngoko↔krama', cross_ng_kr, 'ngoko', 'krama')
print_sample_cross('6. Cross ngoko↔arti', cross_ng_ar, 'ngoko', 'arti')
print_sample_cross('7. Cross krama↔arti', cross_kr_ar, 'krama', 'arti')
print_sample_cross('8. Cross word↔ngoko (NETRAL paired)', cross_word_ng, 'word', 'ngoko')
print_sample_cross('9. Cross word↔krama (NETRAL paired)', cross_word_kr, 'word', 'krama')
print_sample_cross('10. Cross word↔arti (NETRAL paired)', cross_word_ar, 'word', 'arti')

print(f'\n\n═══════════════════════════════════════════════════════════════════')
print(f'  AUDIT SELESAI — {total:,} entries dipindai, {total_dupes:,} duplikat terdeteksi')
print(f'═══════════════════════════════════════════════════════════════════')
