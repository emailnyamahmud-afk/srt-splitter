#!/usr/bin/env python3
"""
parse-wiktionary-jv.py v2 — Parse Wiktionary Jawa XML → kamus-jawa-full.json

Format sederhana (user 6 Okt 2026):
  Tiap entri: ngoko, krama, id (arti Indonesia)
  krama = prioritas: krama_inggil kalau ada, kalau tidak krama

Logic:
  1. Cari entry dengan {{basa|jv}} (bahasa Jawa)
  2. Cari definisi (arti) di section {{-def-|jv}}
  3. Tag {{kn}} = ngoko, arti Jawa di # baris
  4. Untuk krama: cari di kamus kecil (kamus-jawa.json) yang punya krama/krama_inggil field
  5. Kalau tidak ada pasangan krama di kamus kecil, krama = kosong (user isi manual nanti)
"""

import xml.etree.ElementTree as ET
import json
import re
import sys
from pathlib import Path

INPUT_XML = sys.argv[1] if len(sys.argv) > 1 else '/home/z/my-project/upload/wiktionary/wiktionary-jv'
OUTPUT_JSON = sys.argv[2] if len(sys.argv) > 2 else '/home/z/my-project/public/kamus-jawa-full.json'

NS = {'mw': 'http://www.mediawiki.org/xml/export-0.11/'}


def extract_definitions(wikitext):
    """Extract definisi dari section {{basa|jv}}."""
    jv_start = wikitext.find('{{basa|jv}}')
    if jv_start == -1:
        return []

    jv_section = wikitext[jv_start:]
    sikil = jv_section.find('{{sikil}}')
    if sikil != -1:
        jv_section = jv_section[:sikil]

    definitions = []
    lines = jv_section.split('\n')
    current_register = 'umum'

    for line in lines:
        line = line.strip()
        if '{{kn}}' in line:
            current_register = 'ngoko'
        elif '{{kr}}' in line and '{{ki}}' not in line:
            current_register = 'krama'
        elif '{{ki}}' in line:
            current_register = 'krama_inggil'
        elif '{{ak}}' in line:
            current_register = 'kawi'

        if line.startswith('#'):
            def_text = line[1:].strip()
            def_text = re.sub(r'\{\{[^}]*\}\}', '', def_text)
            def_text = re.sub(r'\[\[([^]]*)\]\]', r'\1', def_text)
            def_text = def_text.strip(' ,;').replace('  ', ' ')

            if def_text and len(def_text) > 1:
                definitions.append({
                    'register': current_register,
                    'meaning': def_text,
                })

    return definitions


def load_small_kamus():
    """Load kamus kecil untuk mapping ngoko→krama."""
    try:
        with open('/home/z/my-project/public/kamus-jawa.json', encoding='utf-8') as f:
            data = json.load(f)
        mapping = {}
        for w in data['words']:
            word = w['word'].lower()
            krama = w.get('krama', '')
            krama_inggil = w.get('krama_inggil', '')
            # Prioritas: krama_inggil kalau ada, kalau tidak krama
            krama_val = krama_inggil if krama_inggil else krama
            if krama_val:
                mapping[word] = krama_val
        return mapping
    except Exception:
        return {}


def parse_xml_to_json(xml_path, output_path):
    print(f'Parsing {xml_path}...')
    tree = ET.parse(xml_path)
    root = tree.getroot()

    # Load kamus kecil untuk mapping ngoko → krama
    krama_map = load_small_kamus()
    print(f'Kamus kecil mapping: {len(krama_map)} pasangan ngoko→krama')

    words = []
    stats = {'total': 0, 'jv': 0, 'with_defs': 0, 'with_krama': 0}

    for page in root.findall('.//mw:page', NS):
        stats['total'] += 1
        title = page.find('mw:title', NS)
        page_ns = page.find('mw:ns', NS)
        if title is None or page_ns is None or page_ns.text != '0':
            continue

        title_text = title.text
        if not title_text or len(title_text) > 100 or ':' in title_text or '/' in title_text:
            continue

        text_elem = page.find('.//mw:text', NS)
        if text_elem is None or not text_elem.text:
            continue

        wikitext = text_elem.text
        if '{{basa|jv}}' not in wikitext:
            continue

        stats['jv'] += 1
        defs = extract_definitions(wikitext)

        if not defs:
            # Entry tanpa definisi
            krama_val = krama_map.get(title_text.lower(), '')
            words.append({
                'word': title_text,
                'krama': krama_val,
                'id': '',
            })
            if krama_val:
                stats['with_krama'] += 1
            continue

        stats['with_defs'] += 1

        # Ambil definisi pertama sebagai arti (id)
        meaning = defs[0]['meaning'] if defs else ''

        # Cari krama dari kamus kecil
        krama_val = krama_map.get(title_text.lower(), '')
        if krama_val:
            stats['with_krama'] += 1

        words.append({
            'word': title_text,
            'krama': krama_val,
            'id': meaning,
        })

    # Sort by word
    words.sort(key=lambda w: w['word'])

    output = {
        'metadata': {
            'version': '2.0',
            'source': 'jv.wiktionary.org (Wikisastra)',
            'entries': len(words),
            'note': 'Format sederhana: word (ngoko), krama (prioritas krama_inggil), id (arti). Aksén Jawa tidak dipakai.',
        },
        'words': words,
    }

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f'\n✅ Parsed:')
    print(f'   Total pages: {stats["total"]}')
    print(f'   Jawa entries: {stats["jv"]}')
    print(f'   With definitions: {stats["with_defs"]}')
    print(f'   With krama mapping: {stats["with_krama"]}')
    print(f'   Total in JSON: {len(words)}')
    print(f'   Output: {output_path}')
    print(f'   Size: {Path(output_path).stat().st_size / 1024 / 1024:.1f} MB')


if __name__ == '__main__':
    parse_xml_to_json(INPUT_XML, OUTPUT_JSON)
