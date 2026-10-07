#!/usr/bin/env python3
"""
parse-wiktionary-jv.py v3 — Parse Wiktionary Jawa XML → kamus-jawa-full.json

Format lengkap (user 6 Okt 2026):
  Tiap entri: word (ngoko), krama, id (arti), aksara, keterangan (register tag dari source)
  krama = kosong untuk sebagian besar (Wiktionary tidak punya pasangan ngoko-krama)
  User isi krama manual di web Kamus Editor (simpan ke Supabase, status draft→clean)

Register tags dari Wiktionary:
  {{kn}} = ngoko (22.464 entri)
  {{kr}} = krama (0 entri — Wiktionary Jawa jarang pakai)
  {{ki}} = krama inggil (254 entri)
  {{ak}} = kawi (6.088 entri)
  (tanpa tag) = umum (tidak ada tag register)

Aksara Jawa di-extract dari {{sirah|jv|alt=ꦲꦧ}}
"""

import xml.etree.ElementTree as ET
import json
import re
import sys
from pathlib import Path

INPUT_XML = sys.argv[1] if len(sys.argv) > 1 else '/home/z/my-project/upload/wiktionary/wiktionary-jv'
OUTPUT_JSON = sys.argv[2] if len(sys.argv) > 2 else '/home/z/my-project/public/kamus-jawa-full.json'

NS = {'mw': 'http://www.mediawiki.org/xml/export-0.11/'}


def extract_aksara(wikitext):
    m = re.search(r'\{\{sirah\|jv[^}]*alt=([^\s|}]+)', wikitext)
    if m:
        return m.group(1)
    return ''


def extract_definitions(wikitext):
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
    try:
        with open('/home/z/my-project/public/kamus-jawa.json', encoding='utf-8') as f:
            data = json.load(f)
        mapping = {}
        for w in data['words']:
            word = w['word'].lower()
            krama = w.get('krama', '')
            krama_inggil = w.get('krama_inggil', '')
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

    krama_map = load_small_kamus()
    print(f'Kamus kecil mapping: {len(krama_map)} pasangan ngoko→krama')

    words = []
    stats = {'total': 0, 'jv': 0, 'with_defs': 0, 'with_krama': 0, 'with_aksara': 0}
    register_count = {'ngoko': 0, 'krama': 0, 'krama_inggil': 0, 'umum': 0, 'kawi': 0}

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

        # Extract aksara
        aksara = extract_aksara(wikitext)
        if aksara:
            stats['with_aksara'] += 1

        # Extract definitions
        defs = extract_definitions(wikitext)

        # Determine register (from tags)
        register = 'umum'
        if defs:
            register = defs[0]['register']  # pakai register dari definisi pertama
        register_count[register] = register_count.get(register, 0) + 1

        # Get meaning (first definition)
        meaning = defs[0]['meaning'] if defs else ''

        # Get krama from small kamus mapping
        krama_val = krama_map.get(title_text.lower(), '')
        if krama_val:
            stats['with_krama'] += 1

        if not defs:
            words.append({
                'word': title_text,
                'krama': krama_val,
                'id': '',
                'aksara': aksara,
                'keterangan': register,
            })
            continue

        stats['with_defs'] += 1

        words.append({
            'word': title_text,
            'krama': krama_val,
            'id': meaning,
            'aksara': aksara,
            'keterangan': register,  # ngoko, krama, krama_inggil, kawi, umum
        })

    words.sort(key=lambda w: w['word'])

    output = {
        'metadata': {
            'version': '3.0',
            'source': 'jv.wiktionary.org (Wikisastra)',
            'entries': len(words),
            'register_breakdown': register_count,
            'with_aksara': stats['with_aksara'],
            'with_krama': stats['with_krama'],
            'note': 'Format: word (ngoko), krama (kosong=belum ada, user isi manual), id (arti Jawa), aksara (Jawa script), keterangan (register tag dari Wiktionary). Aksén Jawa tidak dipakai untuk TTS.',
        },
        'words': words,
    }

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f'\n✅ Parsed:')
    print(f'   Total pages: {stats["total"]}')
    print(f'   Jawa entries: {stats["jv"]}')
    print(f'   With definitions: {stats["with_defs"]}')
    print(f'   With aksara: {stats["with_aksara"]}')
    print(f'   With krama mapping: {stats["with_krama"]}')
    print(f'   Total in JSON: {len(words)}')
    print(f'   Register breakdown:')
    for r, c in sorted(register_count.items(), key=lambda x: -x[1]):
        print(f'     {r}: {c}')
    print(f'   Output: {output_path}')
    print(f'   Size: {Path(output_path).stat().st_size / 1024 / 1024:.1f} MB')


if __name__ == '__main__':
    parse_xml_to_json(INPUT_XML, OUTPUT_JSON)
