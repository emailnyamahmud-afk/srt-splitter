#!/usr/bin/env python3
"""Translate Season 1 Indonesia → Jawa, tulis output streaming."""
import re, json, urllib.request, urllib.parse, time, sys

def fix_indonesian(text):
    text = re.sub(r'\btak bisa\b', 'tidak bisa', text)
    text = re.sub(r'\btak akan\b', 'tidak akan', text)
    text = re.sub(r'\btak pernah\b', 'tidak pernah', text)
    return text

def translate_to_jv(text):
    if not text.strip():
        return text
    try:
        url = f'https://translate.googleapis.com/translate_a/single?client=gtx&sl=id&tl=jv&dt=t&q={urllib.parse.quote(text)}'
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode('utf-8'))
        result = ''
        if data and data[0]:
            for seg in data[0]:
                if seg and seg[0]:
                    result += seg[0]
        return result or text
    except:
        return text

def fix_jv(text):
    if not text.strip():
        return text
    fixes = [
        (r'\bdheweke\b', 'dhèwèké'), (r'\bkowe\b', 'kowé'), (r'\bkabeh\b', 'kabèh'),
        (r'\bmaneh\b', 'manèh'), (r'\bwae\b', 'waé'), (r'\bpungkasane\b', 'pungkasané'),
        (r'\bgedhe\b', 'gedhé'), (r'\bpengin\b', 'péngin'), (r'\bsedhela\b', 'sedhéla'),
        (r'\bkene\b', 'kéné'), (r'\bYagene\b', 'Yagéné'), (r'\bsacedhake\b', 'sacedhaké'),
        (r'\bserahke\b', 'serahké'), (r'\bomongke\b', 'omongaké'), (r'\bmutusake\b', 'mutusaké'),
        (r'\bmasrahake\b', 'masrahaké'), (r'\bkabupaten\b', 'kabupatén'), (r'\bgolek\b', 'golèk'),
        (r'\bkeluarga\b', 'kulawarga'), (r'\bKeluarga\b', 'Kulawarga'),
        (r'\brumah tangga\b', 'omah tangga'), (r'\bKahanane\b', 'Kahanané'),
        (r'\bPara bandit\b', 'Para begal'), (r'\bIng antarane\b', 'Ing antarané'),
        (r'\bkasep banget\b', 'késép banget'), (r'\bbales budi\b', 'wales budi'),
        (r'\bdaleme\b', 'dalemé'), (r'\bkepriye\b', 'kepriyé'), (r'\bpiye\b', 'piyé'),
        (r'\bSesuk esuk\b', 'Sesuk ésuk'), (r'\bsuwe\b(?=\s)', 'suwé'),
    ]
    for pattern, replacement in fixes:
        text = re.sub(pattern, replacement, text)
    return text

input_file = '/home/z/my-project/upload/Season-1.srt'
output_file = '/home/z/my-project/download/Season-1-jw.srt'

with open(input_file, 'r', encoding='utf-8') as f:
    content = f.read()

blocks = re.split(r'\n\s*\n', content.strip())
total = len(blocks)

with open(output_file, 'w', encoding='utf-8') as out:
    for i, block in enumerate(blocks):
        lines = block.split('\n')
        time_idx = None
        for j, line in enumerate(lines):
            if '-->' in line:
                time_idx = j
                break
        if time_idx is None:
            out.write(block + '\n\n')
            continue
        
        text_lines = lines[time_idx + 1:]
        text = '\n'.join(text_lines)
        
        # Fix ID → Translate → Fix Jawa
        text = fix_indonesian(text)
        text = translate_to_jv(text)
        text = fix_jv(text)
        
        new_lines = lines[:time_idx + 1] + text.split('\n')
        out.write('\n'.join(new_lines) + '\n\n')
        out.flush()
        
        if (i + 1) % 50 == 0:
            print(f'{i+1}/{total} ({(i+1)*100//total}%)', file=sys.stderr, flush=True)
        
        time.sleep(0.3)

print(f'Done! {total} entries', file=sys.stderr)
