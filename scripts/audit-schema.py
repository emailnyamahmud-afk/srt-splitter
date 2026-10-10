#!/usr/bin/env python3
"""Audit schema kamus-jawa-draft.json — cek field mana yang ada/tidak di setiap entry.

Output: distribusi field + sample entries yang anomali (missing field / extra field).
"""
import json
from collections import Counter, defaultdict
from pathlib import Path

KAMUS = Path('/home/z/my-project/public/kamus-jawa-draft.json')

with open(KAMUS, 'r', encoding='utf-8') as f:
    data = json.load(f)

words = data['words']
print(f'Total entries: {len(words):,}')

# 1. Distribusi key di setiap entry
print('\n=== Distribusi key per entry ===')
key_counter = Counter()
for w in words:
    keys = tuple(sorted(w.keys()))
    key_counter[keys] += 1

for keys, count in key_counter.most_common():
    print(f'  {count:>6,} entries: {len(keys)} keys')
    print(f'    {", ".join(keys)}')

# 2. Field frequency (berapa entry yang punya field X)
print('\n=== Field frequency ===')
field_freq = Counter()
for w in words:
    for k in w.keys():
        field_freq[k] += 1

# Expected schema (per R-17, R-21, R-22)
expected = {
    'entry_id', 'word', 'ngoko', 'krama', 'krama_inggil', 'arti',
    'keterangan', 'aksara', 'register', 'sumber',
    'is_lemma', 'is_mendeley', 'is_dasanama', 'is_angka',
    'source_count', 'status',
}
for f, c in field_freq.most_common():
    marker = '✓' if f in expected else '⚠ EXTRA'
    print(f'  {marker} {f:18} {c:>6,} entries')

# 3. Anomali: entries tanpa field yang seharusnya ada
print('\n=== Anomali: entries tanpa field wajib ===')
wajib = ['entry_id', 'status']  # minimal
for field in expected:
    missing = sum(1 for w in words if field not in w)
    if missing:
        print(f'  {field:18} missing di {missing:>4} entries')

# 4. Sample entries yang schema-nya beda (anomali)
print('\n=== Sample anomali (entries dengan key set tidak standar) ===')
most_common_keys = key_counter.most_common(1)[0][0]
anomalies = []
for i, w in enumerate(words):
    keys = tuple(sorted(w.keys()))
    if keys != most_common_keys:
        anomalies.append((i, w, keys))

print(f'  Total entries dengan schema beda: {len(anomalies)}')
for i, w, keys in anomalies[:10]:
    eid = w.get('entry_id', '?')
    print(f'\n  entry_id={eid} (index {i}):')
    print(f'    keys: {keys}')
    print(f'    word: {(w.get("word","") or "")[:40]!r}')
    print(f'    ngoko: {(w.get("ngoko","") or "")[:40]!r}')
    print(f'    register: {w.get("register", "(TIDAK ADA)")!r}')

# 5. Distribusi nilai register (yang mau di-drop)
print('\n=== Distribusi nilai register (yang akan di-drop) ===')
reg_count = Counter(w.get('register', '(missing)') for w in words)
for r, c in reg_count.most_common():
    print(f'  {r!r:20} {c:>6,}')

# 6. Distribusi status
print('\n=== Distribusi status ===')
status_count = Counter(w.get('status', '(missing)') for w in words)
for s, c in status_count.most_common():
    print(f'  {s!r:20} {c:>6,}')

# 7. Cek entries dengan krama_inggil terisi (R-17: harusnya kosong, sudah masuk krama)
print('\n=== Entries dengan krama_inggil terisi (R-17: harus kosong) ===')
with_ki = sum(1 for w in words if (w.get('krama_inggil') or '').strip())
print(f'  {with_ki} entries')
if with_ki:
    for w in words:
        if (w.get('krama_inggil') or '').strip():
            eid = w.get('entry_id', '?')
            print(f'    entry_id={eid}: krama_inggil={w.get("krama_inggil")!r}')
            break  # sample 1

# 8. Type field (apakah ada yang non-string/non-int/non-bool?)
print('\n=== Type anomaly (cek apakah ada field yang tipe-nya aneh) ===')
type_anomaly = defaultdict(list)
for i, w in enumerate(words):
    for k, v in w.items():
        t = type(v).__name__
        if k in ('entry_id', 'source_count') and t != 'int':
            type_anomaly[k].append((i, t, v))
        elif k in ('is_lemma', 'is_mendeley', 'is_dasanama', 'is_angka') and t != 'bool':
            type_anomaly[k].append((i, t, v))
        elif k not in ('entry_id', 'source_count',
                       'is_lemma', 'is_mendeley', 'is_dasanama', 'is_angka') and t != 'str':
            type_anomaly[k].append((i, t, v))

for k, anomalies in type_anomaly.items():
    print(f'  {k}: {len(anomalies)} anomalies')
    for i, t, v in anomalies[:3]:
        w = words[i]
        eid = w.get('entry_id', '?')
        print(f'    entry_id={eid} type={t} value={v!r}')
