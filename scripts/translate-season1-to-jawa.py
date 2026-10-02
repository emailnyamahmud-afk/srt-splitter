#!/usr/bin/env python3
"""Rapikan SRT Season 1 (Indonesia) → terjemahkan ke Jawa → rapikan Jawa.
Tanpa mengubah timestamps.

Pipeline:
1. Rapikan bahasa Indonesia (ejaan, tata bahasa)
2. Terjemahkan ke Jawa via Google Translate API (batch)
3. Rapikan hasil Jawa (ejaan aksén, kosakata)
"""
import re
import json
import urllib.request
import urllib.parse
import time
import sys

def fix_indonesian(text):
    """Perbaiki tata bahasa Indonesia."""
    if not text.strip():
        return text
    
    # Perbaiki ejaan umum
    text = re.sub(r'\bdiataranya\b', 'di antaranya', text)
    text = re.sub(r'\bdll\b', 'dan lain-lain', text)
    text = re.sub(r'\bdsb\b', 'dan sebagainya', text)
    
    # Konsistensi huruf besar di awal kalimat (biarkan saja, terlalu kompleks)
    
    # Perbaiki "tak" yang ambigu → "tidak" kalau konteks negatif
    # "tak bisa" → "tidak bisa"
    text = re.sub(r'\btak bisa\b', 'tidak bisa', text)
    text = re.sub(r'\btak akan\b', 'tidak akan', text)
    text = re.sub(r'\btak pernah\b', 'tidak pernah', text)
    text = re.sub(r'\btak bisa\b', 'tidak bisa', text)
    
    return text

def translate_to_javanese(text, from_lang='id'):
    """Terjemahkan ke Jawa via Google Translate API."""
    if not text.strip():
        return text
    
    try:
        url = f'https://translate.googleapis.com/translate_a/single?client=gtx&sl={from_lang}&tl=jv&dt=t&q={urllib.parse.quote(text)}'
        req = urllib.request.Request(url, headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        with urllib.request.urlopen(req, timeout=10) as response:
            data = json.loads(response.read().decode('utf-8'))
        
        translated = ''
        if data and data[0]:
            for segment in data[0]:
                if segment and segment[0]:
                    translated += segment[0]
        return translated or text
    except Exception as e:
        print(f'  Translate error: {e}', file=sys.stderr)
        return text  # fallback: pakai text asli

def fix_javanese(text):
    """Perbaiki ejaan Jawa."""
    if not text.strip():
        return text
    
    # Ejaan aksén
    text = re.sub(r'\bdheweke\b', 'dhèwèké', text)
    text = re.sub(r'\bkowe\b', 'kowé', text)
    text = re.sub(r'\bkabeh\b', 'kabèh', text)
    text = re.sub(r'\bmaneh\b', 'manèh', text)
    text = re.sub(r'\bwae\b', 'waé', text)
    text = re.sub(r'\bpungkasane\b', 'pungkasané', text)
    text = re.sub(r'\bgedhe\b', 'gedhé', text)
    text = re.sub(r'\bpengin\b', 'péngin', text)
    text = re.sub(r'\bsedhela\b', 'sedhéla', text)
    text = re.sub(r'\bkene\b', 'kéné', text)
    text = re.sub(r'\bYagene\b', 'Yagéné', text)
    text = re.sub(r'\bsacedhake\b', 'sacedhaké', text)
    text = re.sub(r'\bserahke\b', 'serahké', text)
    text = re.sub(r'\bomongke\b', 'omongaké', text)
    text = re.sub(r'\bmutusake\b', 'mutusaké', text)
    text = re.sub(r'\bmasrahake\b', 'masrahaké', text)
    text = re.sub(r'\bkabupaten\b', 'kabupatén', text)
    text = re.sub(r'\bgolek\b', 'golèk', text)
    text = re.sub(r'\bkeluarga\b', 'kulawarga', text)
    text = re.sub(r'\bKeluarga\b', 'Kulawarga', text)
    text = re.sub(r'\brumah tangga\b', 'omah tangga', text)
    text = re.sub(r'\bKahanane\b', 'Kahanané', text)
    text = re.sub(r'\bPara bandit\b', 'Para begal', text)
    text = re.sub(r'\bak\b(è|e)h\b', 'akèh', text)
    text = re.sub(r'\bIng antarane\b', 'Ing antarané', text)
    text = re.sub(r'\bkasep banget\b', 'késép banget', text)
    text = re.sub(r'\bbales budi\b', 'wales budi', text)
    text = re.sub(r'\bsuwe\b(?=\s)', 'suwé', text)
    text = re.sub(r'\bisa bertahan\b', 'bisa bertahan', text)
    text = re.sub(r'\bKuwat utawa ora\b', 'Kuwat apa ora', text)
    text = re.sub(r'\bdaleme\b', 'dalemé', text)
    text = re.sub(r'\bkepriye\b', 'kepriyé', text)
    text = re.sub(r'\bpiye\b', 'piyé', text)
    text = re.sub(r'\bSesuk esuk\b', 'Sesuk ésuk', text)
    
    return text

def process_srt(input_file, output_file, batch_size=10, delay=0.5):
    """Baca SRT, rapikan Indonesia, translate ke Jawa, rapikan Jawa, tulis output."""
    with open(input_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    blocks = re.split(r'\n\s*\n', content.strip())
    total = len(blocks)
    
    # Parse semua blocks
    parsed = []
    for block in blocks:
        lines = block.split('\n')
        if len(lines) < 2:
            parsed.append({'block': block, 'text': '', 'header': lines})
            continue
        
        time_line_idx = None
        for i, line in enumerate(lines):
            if '-->' in line:
                time_line_idx = i
                break
        
        if time_line_idx is None:
            parsed.append({'block': block, 'text': '', 'header': lines})
            continue
        
        text_lines = lines[time_line_idx + 1:]
        text = '\n'.join(text_lines)
        header = lines[:time_line_idx + 1]
        
        parsed.append({
            'header': header,
            'text': text,
            'text_lines': text_lines,
        })
    
    # Process: fix Indonesia → translate → fix Jawa
    translated_blocks = []
    for i, p in enumerate(parsed):
        if not p.get('text'):
            translated_blocks.append(p.get('block', ''))
            continue
        
        # Step 1: Rapikan Indonesia
        fixed_id = fix_indonesian(p['text'])
        
        # Step 2: Translate ke Jawa
        translated = translate_to_javanese(fixed_id)
        
        # Step 3: Rapikan Jawa
        fixed_jv = fix_javanese(translated)
        
        # Reconstruct block
        text_lines = fixed_jv.split('\n')
        new_lines = p['header'] + text_lines
        translated_blocks.append('\n'.join(new_lines))
        
        # Progress
        if (i + 1) % 100 == 0:
            print(f'  Progress: {i+1}/{total} ({(i+1)*100//total}%)', file=sys.stderr)
        
        # Delay untuk hindari rate limit
        time.sleep(delay)
    
    # Write output
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write('\n\n'.join(translated_blocks) + '\n')
    
    return len(translated_blocks)

if __name__ == '__main__':
    input_file = '/home/z/my-project/upload/Season-1.srt'
    output_file = '/home/z/my-project/download/Season-1-jw.srt'
    
    print(f'Processing {input_file}...')
    print(f'Output: {output_file}')
    print(f'Total entries: ~5100')
    print(f'Estimasi waktu: ~25-30 menit (delay 0.5s per entry)')
    print()
    
    count = process_srt(input_file, output_file, batch_size=10, delay=0.5)
    print(f'\nDone! Processed {count} entries')
    print(f'Output: {output_file}')
