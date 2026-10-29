#!/usr/bin/env python3
"""Validate clean SRT vs input: timestamps, cue count, order must match EXACTLY."""
import re
from pathlib import Path

def parse_srt(text):
    text = text.replace('\r\n', '\n').replace('\r', '\n')
    blocks = re.split(r'\n\s*\n', text.strip())
    cues = []
    for block in blocks:
        block = block.strip()
        if not block:
            continue
        lines = block.split('\n')
        ts = re.search(r'(\d{2}:\d{2}:\d{2}[,.]\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2}[,.]\d{3})', '\n'.join(lines))
        if not ts:
            continue
        text_start = False
        text_lines = []
        for line in lines:
            if '-->' in line:
                text_start = True
                continue
            if text_start:
                text_lines.append(line)
        cues.append({
            'index': len(cues) + 1,
            'start': ts.group(1),
            'end': ts.group(2),
            'text': '\n'.join(text_lines).strip(),
        })
    return cues

orig = parse_srt(Path('/home/z/my-project/upload/folder/28d69ed4/S1 Lima Tentara.id.srt').read_text(encoding='utf-8-sig'))
clean = parse_srt(Path('/home/z/my-project/download/S1_Lima_Tentara.id.clean.srt').read_text(encoding='utf-8'))

print(f"Original cues : {len(orig)}")
print(f"Clean cues    : {len(clean)}")
assert len(orig) == len(clean), "CUE COUNT MISMATCH"

ts_mismatch = 0
order_mismatch = 0
text_changes = 0
for i, (o, c) in enumerate(zip(orig, clean)):
    if o['start'] != c['start'] or o['end'] != c['end']:
        ts_mismatch += 1
        if ts_mismatch <= 3:
            print(f"  TS mismatch cue {i+1}: {o['start']}→{c['start']} / {o['end']}→{c['end']}")
    if o['index'] != c['index']:
        order_mismatch += 1
    if o['text'] != c['text']:
        text_changes += 1

print(f"Timestamp mismatches : {ts_mismatch}  (must be 0)")
print(f"Order mismatches     : {order_mismatch}  (must be 0)")
print(f"Text changes         : {text_changes}/{len(orig)} cues")

if ts_mismatch == 0 and order_mismatch == 0 and len(orig) == len(clean):
    print("\n✅ VALIDATION PASSED — timestamps/count/order all preserved exactly.")
else:
    print("\n❌ VALIDATION FAILED — see issues above.")
