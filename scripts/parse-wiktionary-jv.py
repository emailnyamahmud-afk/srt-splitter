#!/usr/bin/env python3
"""
parse-wiktionary-jv.py — Parse Wiktionary Jawa XML → kamus-jawa-full.json

Input:  jvwiktionary XML dump (83MB, 90846 pages, 44585 Jawa entries)
Output: public/kamus-jawa-full.json (ngoko, krama, krama_inggil, meaning_id)

Format wikitext Jawa yang di-parse:
  =={{basa|jv}}==                                    → section bahasa Jawa
  {{sirah|jv|entry=aba|alt=ꦲꦧ|kelas=}}              → entry + aksara + kelas
  {{-def-|jv}}                                        → section definisi
  # {{kn}} swara, ujar.                               → definisi ngoko (kn = krama:ngoko)
  # {{kr}} tansah kepéngin memangan                    → definisi krama (kr = krama)
  # {{ki}} ...                                         → krama inggil (ki)
  # {{ak}} langgeng, lestari.                           → aksara/aksara kuna
  # anak sekawan lanang kabeh                          → definisi tanpa tag = umum

Tag register:
  {{kn}} = ngoko (krama:ngoko) — kata ngoko + krama-nya
  {{kr}} = krama
  {{ki}} = krama inggil
  {{ak}} = aksara kuna / kawi
  (tanpa tag) = umum (bisa ngoko atau krama)

Output JSON format:
  {
    "metadata": { "version": "2.0", "source": "jv.wiktionary.org", "entries": N },
    "words": [
      {
        "word": "aba",
        "register": "ngoko",          // ngoko, krama, krama_inggil, umum
        "meaning_id": "swara, ujar",  // definisi dalam bahasa Jawa/Indonesia
        "aksara": "ꦲꦧ",              // aksara Jawa (opsional)
        "kelas": ""                   // kelas kata (opsional)
      }
    ]
  }
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
    """Extract aksara Jawa dari {{sirah|jv|alt=ꦲꦧ}} atau {{sirah|jv|entry=x|alt=ꦲꦧ}}"""
    m = re.search(r'\{\{sirah\|jv[^}]*alt=([^\s|}]+)', wikitext)
    if m:
        return m.group(1)
    return ''


def extract_kelas(wikitext):
    """Extract kelas kata dari {{sirah|jv|...|kelas=...}}"""
    m = re.search(r'\{\{sirah\|jv[^}]*kelas=([^\s|}]+)', wikitext)
    if m:
        return m.group(1)
    return ''


def extract_definitions(wikitext):
    """
    Extract definisi dari section {{basa|jv}}.
    Return list of { register, meaning }.
    """
    # Cari section =={{basa|jv}}==
    jv_start = wikitext.find('{{basa|jv}}')
    if jv_start == -1:
        return []

    # Section Jawa: dari {{basa|jv}} sampai {{sikil}} atau end
    jv_section = wikitext[jv_start:]
    sikil = jv_section.find('{{sikil}}')
    if sikil != -1:
        jv_section = jv_section[:sikil]

    definitions = []
    lines = jv_section.split('\n')

    current_register = 'umum'
    for line in lines:
        line = line.strip()

        # Deteksi tag register
        if '{{kn}}' in line:
            current_register = 'ngoko'
        elif '{{kr}}' in line and '{{ki}}' not in line:
            current_register = 'krama'
        elif '{{ki}}' in line:
            current_register = 'krama_inggil'
        elif '{{ak}}' in line:
            current_register = 'kawi'

        # Cari line definisi (dimulai dengan #)
        if line.startswith('#'):
            # Hapus # di awal
            def_text = line[1:].strip()
            # Hapus template tags {{...}} tapi simpan text di dalamnya
            # {{kn}} → hapus, tapi [[kata]] → simpan
            def_text = re.sub(r'\{\{[^}]*\}\}', '', def_text)
            def_text = re.sub(r'\[\[([^]]*)\]\]', r'\1', def_text)  # [[kata]] → kata
            def_text = def_text.strip(' ,;')
            def_text = def_text.replace('  ', ' ')

            if def_text and len(def_text) > 1:
                definitions.append({
                    'register': current_register,
                    'meaning': def_text,
                })

    return definitions


def parse_xml_to_json(xml_path, output_path):
    print(f'Parsing {xml_path}...')
    tree = ET.parse(xml_path)
    root = tree.getroot()

    words = []
    stats = {'total': 0, 'jv': 0, 'with_defs': 0}
    register_stats = {'ngoko': 0, 'krama': 0, 'krama_inggil': 0, 'umum': 0, 'kawi': 0}

    for page in root.findall('.//mw:page', NS):
        stats['total'] += 1
        title = page.find('mw:title', NS)
        page_ns = page.find('mw:ns', NS)
        if title is None or page_ns is None or page_ns.text != '0':
            continue

        title_text = title.text
        if not title_text or len(title_text) > 100:
            continue

        # Skip pages with special characters in title (templates, etc)
        if ':' in title_text or '/' in title_text:
            continue

        text_elem = page.find('.//mw:text', NS)
        if text_elem is None or not text_elem.text:
            continue

        wikitext = text_elem.text

        # Cek apakah ada section Jawa
        if '{{basa|jv}}' not in wikitext:
            continue

        stats['jv'] += 1

        # Extract aksara + kelas
        aksara = extract_aksara(wikitext)
        kelas = extract_kelas(wikitext)

        # Extract definitions
        defs = extract_definitions(wikitext)

        if not defs:
            # Entry tanpa definisi, tetap simpan dengan meaning kosong
            words.append({
                'word': title_text,
                'register': 'umum',
                'meaning_id': '',
                'aksara': aksara,
                'kelas': kelas,
            })
            register_stats['umum'] += 1
            continue

        stats['with_defs'] += 1

        # Jika ada multiple definitions dengan register berbeda,
        # buat entry terpisah per register
        seen_registers = set()
        for d in defs:
            register = d['register']
            meaning = d['meaning']

            # Avoid duplicates (same word + same register)
            key = (title_text, register)
            if key in seen_registers:
                # Append to existing meaning
                for w in words:
                    if w['word'] == title_text and w['register'] == register:
                        w['meaning_id'] += '; ' + meaning
                        break
                continue
            seen_registers.add(key)

            words.append({
                'word': title_text,
                'register': register,
                'meaning_id': meaning,
                'aksara': aksara,
                'kelas': kelas,
            })
            register_stats[register] = register_stats.get(register, 0) + 1

    # Sort by word
    words.sort(key=lambda w: w['word'])

    # Write JSON
    output = {
        'metadata': {
            'version': '2.0',
            'source': 'jv.wiktionary.org (Wikisastra)',
            'dialect': 'jawa_tengah',
            'entries': len(words),
            'unique_words': len(set(w['word'] for w in words)),
            'register_breakdown': register_stats,
            'note': 'Aksén Jawa (é, è, ê) tidak dipakai — Edge TTS tidak bisa baca. Pakai e polos.',
            'parsed_from': 'jvwiktionary XML dump (95321 pages, 44585 Jawa entries)',
        },
        'words': words,
    }

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f'\n✅ Parsed {stats["total"]} pages')
    print(f'   Jawa entries: {stats["jv"]}')
    print(f'   With definitions: {stats["with_defs"]}')
    print(f'   Total words in JSON: {len(words)}')
    print(f'   Unique words: {len(set(w["word"] for w in words))}')
    print(f'   Register breakdown:')
    for r, c in sorted(register_stats.items(), key=lambda x: -x[1]):
        print(f'     {r}: {c}')
    print(f'   Output: {output_path}')
    print(f'   Size: {Path(output_path).stat().st_size / 1024 / 1024:.1f} MB')


if __name__ == '__main__':
    parse_xml_to_json(INPUT_XML, OUTPUT_JSON)
