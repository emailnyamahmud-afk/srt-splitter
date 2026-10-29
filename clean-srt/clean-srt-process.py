#!/usr/bin/env python3
"""Clean SRT Indonesia hasil Google Translate menggunakan glossary + rules."""
import re
import sys
import json
from pathlib import Path

# === Glossary ===
REPLACEMENTS = [
    # Names (longer first to avoid partial match)
    ("Peti mati Lin Ya", "Lin Zhao"),
    ("Peti mati Lin", "Lin Zhao"),
    ("Lin menertawakan peti mati", "Lin Zhao"),
    ("Lin Yanya", "Lin Zhao"),
    ("Lin Yasi", "Lin Zhao"),
    ("Lin Zhou", "Lin Zhao"),
    ("Xie Zangfeng", "Xie Changfeng"),
    ("Xie Chaojin", "Xie Changfeng"),
    ("Xie Dutou", "Xie Changfeng"),
    ("Pelatih Xie", "Xie Changfeng"),
    ("Aokawa", "Wang Haochuan"),
    ("Ma Zhenzhuang", "Ma Zhenbang"),
    ("Marco", "Ma Zhenbang"),
    ("Chen Xinlang", "Chen Su"),
    ("Saudari Chen Su", "Chen Su"),
    ("Nyonya Chen", "Chen Su"),
    ("Nona Chen", "Chen Su"),
    ("Dokter Chen", "Chen Su"),
    ("Elang Merah", "Qin Hongying"),
    ("Red Eagle", "Qin Hongying"),
    ("Qin Hongying Nyonya Qin", "Qin Hongying"),
    # "Bulan" → "Mu En" only as name, NOT as month/moon
    # Handled separately in clean_text() with context check
    ("bulan mudu xu", "Mu En"),
    ("bulan yang rendah hati", "Mu En"),
    ("Mu Xunjian", "Mu En"),
    ("Butler Yao", "Yao Sihai"),
    ("Yao Gu", "Yao Sihai"),
    ("Yao Dadu", "Yao Sihai"),
    ("Yao Zhong", "Yao Sihai"),
    ("Zhou Laozhang", "Zhou Lizheng"),
    ("Zhou Lao", "Zhou Lizheng"),
    ("Paman Zhou", "Zhou Lizheng"),
    ("Qin Fengzhan", "Qin Fenglu"),
    ("Qin Fengjun", "Qin Fenglu"),
    # Terms
    ("Tentara Hunan", "Xiangjun"),
    ("tentara utang", "Xiangjun"),
    ("pemberontak debitur", "Xiangjun"),
    ("Tentara debitur", "Xiangjun"),
    ("ayam panah otomatis", "panah otomatis"),
    ("ayam panah", "panah otomatis"),
    ("payung tempat tidur emas", "obat luka emas"),
    ("payung emas buatan tangan", "obat luka emas"),
    ("payung emas", "obat luka emas"),
    ("dot polisi", "Jiedushi"),
    ("Qin Fenglu dot polisi", "Jiedushi"),
    ("Qin Fenglu dot", "Jiedushi"),
    ("cumming", "menarik pelatuk"),
    ("melakukan cumming", "menarik pelatuk"),
    ("menggoreng permen", "laras meledak"),
    ("retribusi", "pembalasan"),
    ("universitas terkemuka", "akademi"),
    ("SMP Desa", "akademi"),
]

# Case-insensitive replacements
REPLACEMENTS_CI = {old: new for old, new in REPLACEMENTS}


def parse_srt(text):
    """Parse SRT → list of (index, start, end, text)."""
    text = text.replace('\r\n', '\n').replace('\r', '\n')
    blocks = re.split(r'\n\s*\n', text.strip())
    cues = []
    for block in blocks:
        block = block.strip()
        if not block:
            continue
        lines = block.split('\n')
        ts_match = re.search(
            r'(\d{2}:\d{2}:\d{2}[,.]\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2}[,.]\d{3})',
            '\n'.join(lines)
        )
        if not ts_match:
            continue
        start = ts_match.group(1)
        end = ts_match.group(2)
        # Find text lines (after timestamp line)
        text_start = False
        text_lines = []
        for line in lines:
            if '-->' in line:
                text_start = True
                continue
            if text_start:
                text_lines.append(line)
        text = '\n'.join(text_lines).strip()
        cues.append((len(cues) + 1, start, end, text))
    return cues


def clean_text(text):
    """Apply glossary replacements (case-insensitive) + context-aware Bulan→Mu En."""
    result = text
    for old, new in REPLACEMENTS_CI.items():
        if old.lower() in result.lower():
            import re as re2
            result = re2.sub(re2.escape(old), new, result, flags=re2.IGNORECASE)

    # Context-aware: "Bulan" → "Mu En" only when it's a person's name
    # NOT when it means "month" (bulan Mei = May) or "moon" (bulan purnama)
    months = ['Januari', 'Februari', 'Maret', 'April', 'Mei', 'Juni',
              'Juli', 'Agustus', 'September', 'Oktober', 'November', 'Desember']
    moon_words = ['purnama', 'sabit', 'terang', 'gelap', 'mati', 'baru']

    # Find standalone "Bulan" (capitalized, as a name)
    # Check if it's followed by a month name → skip
    words = result.split()
    for i, w in enumerate(words):
        if w == 'Bulan':
            # Check next word
            next_word = words[i + 1] if i + 1 < len(words) else ''
            # Don't replace if followed by month name
            if next_word in months:
                continue
            # Don't replace if followed by moon-related word
            if next_word.lower() in moon_words:
                continue
            # Don't replace if preceded by time-related words
            prev_word = words[i - 1] if i > 0 else ''
            if prev_word.lower() in ['tiap', 'setiap', 'dalam', 'pada', 'di']:
                continue
            # Replace — it's a name
            words[i] = 'Mu En'

    result = ' '.join(words)
    return result


def main():
    id_path = '/home/z/my-project/upload/folder/28d69ed4/S1 Lima Tentara.id.srt'
    zh_path = '/home/z/my-project/upload/folder/d818d15e/S1 Lima Tentara.zh.srt'

    id_text = Path(id_path).read_text(encoding='utf-8-sig')
    zh_text = Path(zh_path).read_text(encoding='utf-8-sig')

    id_cues = parse_srt(id_text)
    zh_cues = parse_srt(zh_text)

    print(f"ID cues: {len(id_cues)}")
    print(f"ZH cues: {len(zh_cues)}")

    # Clean ID cues
    changes = 0
    output_lines = []
    for i, (idx, start, end, text) in enumerate(id_cues):
        original = text
        cleaned = clean_text(text)
        if cleaned != original:
            changes += 1
        # Write SRT format
        output_lines.append(str(i + 1))
        output_lines.append(f"{start} --> {end}")
        output_lines.append(cleaned)
        output_lines.append("")

    output = '\n'.join(output_lines)
    output_path = '/home/z/my-project/download/S1_Lima_Tentara.id.clean.srt'
    Path(output_path).write_text(output, encoding='utf-8')

    print(f"\nChanges: {changes}/{len(id_cues)} cues modified")
    print(f"Output: {output_path}")
    print(f"Size: {Path(output_path).stat().st_size / 1024:.1f} KB")

    # Show sample changes
    print("\n=== Sample changes (first 20) ===")
    for i, (idx, start, end, text) in enumerate(id_cues[:200]):
        cleaned = clean_text(text)
        if cleaned != text:
            print(f"  Cue {i+1}:")
            print(f"    BEFORE: {text[:80]}")
            print(f"    AFTER:  {cleaned[:80]}")


if __name__ == '__main__':
    main()
