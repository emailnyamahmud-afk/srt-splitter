#!/usr/bin/env python3
"""
add-entry-id.py — Tambah field entry_id (1-indexed) ke kamus-jawa-full.json
User bisa referensi entry by number untuk merge/validasi.

Usage: python3 add-entry-id.py [kamus-json]
Default: ~/Dubbing/kamus-jawa-full.json
"""

import json
import sys
from pathlib import Path

KAMUS_PATH = Path(sys.argv[1] if len(sys.argv) > 1 else Path.home() / 'Dubbing' / 'kamus-jawa-full.json')

print(f'📁 Kamus: {KAMUS_PATH}')

with open(KAMUS_PATH, 'r', encoding='utf-8') as f:
    data = json.load(f)

# Tambah entry_id (1-indexed) ke setiap entry
for i, w in enumerate(data['words'], 1):
    w['entry_id'] = i

with open(KAMUS_PATH, 'w', encoding='utf-8') as f:
    json.dump(data, f, ensure_ascii=False, indent=2)

print(f'✅ Tambah entry_id ke {len(data["words"])} entries')
print(f'   Entry #1: ngoko={data["words"][0].get("ngoko","")!r}')
print(f'   Entry #{len(data["words"])}: ngoko={data["words"][-1].get("ngoko","")!r}')
