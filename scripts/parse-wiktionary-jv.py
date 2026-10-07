#!/usr/bin/env python3
"""
parse-wiktionary-jv.py v4 — Parse Wiktionary Jawa XML → kamus-jawa-full.json

Format BENAR (user 6 Okt 2026, AI ceroboh sebelumnya):
  Tiap entri:
    ngoko      = kata ngoko + alias (dipisah koma). Dari XML title.
    aksara     = aksara Jawa. Dari XML {{sirah|jv|alt=...}}.
    krama      = kata krama + alias. KOSONG (user isi manual di Kamus Editor).
    id         = terjemahan Indonesia. KOSONG (user isi manual).
    keterangan = definisi dari XML (bahasa JAWA, bukan Indonesia).
                 JANGAN HAPUS — membantu user untuk isi id.
    sumber     = sumber data (mis. jv.wiktionary.org)

User sejak awal bilang:
  'kamus ada ngoko, krama, id, keterangan, aksara'
  'belum semua translate' (id kosong, user isi manual)
  'keterangan dari XML yg ai salah kaprah tulis sebagai id'
  'INI JANGAN HAPUS, KARENA MEMBANTU USER UNTUK ISI ID'

Register tags dari XML Wiktionary:
  {{kn}} = ngoko (22.240 entri) → keterangan = definisi Jawa
  {{ki}} = krama inggil (77 entri) → keterangan = definisi Jawa
  {{ak}} = kawi (2.352 entri) → keterangan = definisi Jawa
  (tanpa tag) = umum → keterangan = definisi Jawa
"""

import xml.etree.ElementTree as ET
import json
import re
import sys
from pathlib import Path

INPUT_XML = sys.argv[1] if len(sys.argv) > 1 else '/home/z/my-project/upload/wiktionary/wiktionary-jv'
OUTPUT_JSON = sys.argv[2] if len(sys.argv) > 2 else '/home/z/my-project/public/kamus-jawa-full.json'
SOURCE_NAME = 'jv.wiktionary.org (Wikisastra)'

NS = {'mw': 'http://www.mediawiki.org/xml/export-0.11/'}


def extract_aksara(wikitext):
    m = re.search(r'\{\{sirah\|jv[^}]*alt=([^\s|}]+)', wikitext)
    if m:
        return m.group(1)
    return ''


def extract_definitions(wikitext):
    """Extract definisi JAWA (bukan Indonesia) dari section {{basa|jv}}."""
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
                definitions.append(def_text)

    return definitions


def parse_xml_to_json(xml_path, output_path):
    print(f'Parsing {xml_path}...')
    tree = ET.parse(xml_path)
    root = tree.getroot()

    words = []
    stats = {'total': 0, 'jv': 0, 'with_defs': 0, 'with_aksara': 0}
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

        # Extract aksara Jawa
        aksara = extract_aksara(wikitext)
        if aksara:
            stats['with_aksara'] += 1

        # Extract definitions (KETERANGAN — definisi dalam bahasa JAWA, bukan Indonesia)
        defs = extract_definitions(wikitext)

        # Determine register tag dari XML
        register = 'umum'
        if defs:
            # Cari tag di section Jawa
            jv_start = wikitext.find('{{basa|jv}}')
            jv_section = wikitext[jv_start:]
            sikil = jv_section.find('{{sikil}}')
            if sikil != -1:
                jv_section = jv_section[:sikil]
            if '{{kn}}' in jv_section:
                register = 'ngoko'
            elif '{{kr}}' in jv_section and '{{ki}}' not in jv_section:
                register = 'krama'
            elif '{{ki}}' in jv_section:
                register = 'krama_inggil'
            elif '{{ak}}' in jv_section:
                register = 'kawi'

        register_count[register] = register_count.get(register, 0) + 1

        # KETERANGAN = definisi JAWA dari XML (JANGAN HAPUS, membantu user isi id)
        keterangan = '; '.join(defs) if defs else ''
        if defs:
            stats['with_defs'] += 1

        # Format BENAR:
        # ngoko      = title (kata Jawa dari XML)
        # aksara     = aksara Jawa
        # krama      = KOSONG (user isi manual)
        # id         = KOSONG (user isi manual, terjemahan Indonesia)
        # keterangan = definisi JAWA dari XML (membantu user untuk isi id)
        # sumber     = jv.wiktionary.org
        words.append({
            'ngoko': title_text,
            'aksara': aksara,
            'krama': '',           # KOSONG — user isi manual
            'id': '',              # KOSONG — user isi manual (terjemahan Indonesia)
            'keterangan': keterangan,
            'sumber': SOURCE_NAME,
        })

    # Sort by ngoko
    words.sort(key=lambda w: w['ngoko'])

    output = {
        'metadata': {
            'version': '4.0',
            'source': SOURCE_NAME,
            'entries': len(words),
            'register_breakdown': register_count,
            'with_aksara': stats['with_aksara'],
            'with_keterangan': stats['with_defs'],
            'note': 'Format: ngoko, aksara, krama (kosong=user isi), id (kosong=user isi), keterangan (definisi JAWA dari XML, JANGAN HAPUS), sumber. Aksén Jawa tidak dipakai untuk TTS.',
        },
        'words': words,
    }

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f'\n✅ Parsed v4:')
    print(f'   Total pages: {stats["total"]}')
    print(f'   Jawa entries: {stats["jv"]}')
    print(f'   With keterangan (def Jawa): {stats["with_defs"]}')
    print(f'   With aksara: {stats["with_aksara"]}')
    print(f'   Total in JSON: {len(words)}')
    print(f'   Register breakdown:')
    for r, c in sorted(register_count.items(), key=lambda x: -x[1]):
        print(f'     {r}: {c}')
    print(f'   krama: 0 (kosong, user isi manual)')
    print(f'   id: 0 (kosong, user isi manual)')
    print(f'   Output: {output_path}')
    print(f'   Size: {Path(output_path).stat().st_size / 1024 / 1024:.1f} MB')


if __name__ == '__main__':
    parse_xml_to_json(INPUT_XML, OUTPUT_JSON)
