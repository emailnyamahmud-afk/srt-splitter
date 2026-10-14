#!/usr/bin/env python3
"""
parse-jv-wiktionary-v2.py — Parser BENAR jv.wiktionary XML dump.

User: 'parsing ulang XML dengan BENAR.
untuk cross reff kosakata penulisan, keterangan (bukan cross reff register)
semua penulisan jawa merujuk ke jv dictionary, json dictionary harus ada kata jawa baku, keterangan.'

Format jv.wiktionary (VERIFIED dari XML):
  =={{basa|jv}}==       → section Jawa
  {{sirah|jv|alt=ꦲꦧꦁ|kelas=...|entry=...}}  → aksara + kelas + entry alternative
  {{-def-|jv}}          → awal definisi
  # arti Jawa            → definisi (list)
  {{kn}}                 → krama ngoko marker
  [[Kategori:...]]       → kategori (skip)
  {{sikil}}              → akhir section
  {{ngoko|...}}          → kata ngoko (jika ada)

Strategy:
1. Parse XML, ambil pages ns=0 dgn {{basa|jv}}
2. Untuk tiap page:
   - title = word (lemma baku Jawa)
   - aksara dari {{sirah|jv|alt=...}}
   - kelas dari {{sirah|jv|kelas=...}}
   - definisi: gabung baris yg mulai dgn # (arti Jawa)
   - keterangan: wikitext asli (untuk user verify)
3. Output: kata_jawa_baku.json
   - entry_id, word (lemma baku), aksara, kelas, definisi (Jawa), keterangan (raw wikitext)
4. Cross-ref ke master kamus_bersih untuk:
   - Penulisan baku (validasi word di master = word di jv.wiktionary)
   - Keterangan (isi definisi Jawa ke keterangan master)

R-71: Parsing jv.wiktionary BENAR — pahami format wiktionary (sirah, def, kn, sikil).
R-72: Output = kata Jawa baku + definisi + keterangan (BUKAN register — tugas user).
R-73: Cross-ref penulisan + keterangan, BUKAN register.
"""

import json
import re
import xml.etree.ElementTree as ET
from pathlib import Path
from collections import defaultdict

NS = '{http://www.mediawiki.org/xml/export-0.11/}'
XML_PATH = Path('/tmp/wikt-raw/jv.xml')
OUT_PATH = Path('/home/z/my-project/srt-splitter-clone/public/kata_jawa_baku.json')


def parse_sirah(wikitext):
    """Extract dari {{sirah|jv|alt=...|kelas=...|entry=...}}"""
    aksara = ''
    kelas = ''
    entry_alt = ''
    m = re.search(r'\{\{sirah\|jv[^}]*\}\}', wikitext)
    if m:
        tpl = m.group(0)
        alt_m = re.search(r'\|alt=([^|}]+)', tpl)
        if alt_m:
            aksara = alt_m.group(1).strip()
        kelas_m = re.search(r'\|kelas=([^|}]+)', tpl)
        if kelas_m:
            kelas = kelas_m.group(1).strip()
        entry_m = re.search(r'\|entry=([^|}]+)', tpl)
        if entry_m:
            entry_alt = entry_m.group(1).strip()
    return aksara, kelas, entry_alt


def parse_definisi(wikitext):
    """Extract definisi Jawa dari baris yg mulai dgn # (di dalam section {{basa|jv}}).
    
    Format:
      # arti Jawa
      #: contoh kalimat Jawa
      #:: terjemahan Indonesia
    
    Return:
      definisi_jawa: list of arti (baris # tanpa #: dan #::)
      terjemahan_indo: list of Indonesia translations (dari #::)
      contoh_jawa: list of contoh kalimat (dari #:)
    """
    definisi_jawa = []
    terjemahan_indo = []
    contoh_jawa = []
    
    lines = wikitext.split('\n')
    for line in lines:
        line_stripped = line.strip()
        # Definisi: # arti (bukan #: atau #::)
        if line_stripped.startswith('#') and not line_stripped.startswith('#:') and not line_stripped.startswith('#::'):
            # Hapus # di awal
            arti = line_stripped.lstrip('#').strip()
            # Hapus template {{...}} tapi simpan teks di dalamnya
            arti = re.sub(r'\{\{[^}]*\}\}', '', arti).strip()
            # Hapus [[Kategori:...]]
            arti = re.sub(r'\[\[Kategori:[^\]]*\]\]', '', arti).strip()
            # Hapus [[...]] tapi simpan teks link
            arti = re.sub(r'\[\[([^\]|]+)(\|[^\]]+)?\]\]', r'\1', arti).strip()
            if arti:
                definisi_jawa.append(arti)
        # Contoh kalimat: #: contoh Jawa
        elif line_stripped.startswith('#:') and not line_stripped.startswith('#::'):
            contoh = line_stripped.lstrip('#:').strip()
            contoh = re.sub(r'\{\{[^}]*\}\}', '', contoh).strip()
            if contoh:
                contoh_jawa.append(contoh)
        # Terjemahan Indonesia: #:: Indonesia
        elif line_stripped.startswith('#::'):
            indo = line_stripped.lstrip('#::').strip()
            if indo:
                terjemahan_indo.append(indo)
    
    return definisi_jawa, terjemahan_indo, contoh_jawa


def parse_ngoko_krama(wikitext):
    """Extract ngoko/krama dari template {{ngoko|...}} atau {{krama|...}} kalau ada."""
    ngoko = ''
    krama = ''
    # {{ngoko|kata}} atau {{krama|kata}}
    ngoko_m = re.search(r'\{\{ngoko\|([^}]+)\}\}', wikitext)
    if ngoko_m:
        ngoko = ngoko_m.group(1).strip()
    krama_m = re.search(r'\{\{krama\|([^}]+)\}\}', wikitext)
    if krama_m:
        krama = krama_m.group(1).strip()
    return ngoko, krama


def main():
    print(f'📁 XML: {XML_PATH}')
    print(f'📁 Output: {OUT_PATH}')
    print()
    
    tree = ET.parse(str(XML_PATH))
    root = tree.getroot()
    
    entries = []
    n_jv = 0
    n_with_def = 0
    n_with_indo = 0
    n_with_ngoko = 0
    
    for page in root.findall(f'{NS}page'):
        ns_el = page.find(f'{NS}ns')
        if ns_el is None or ns_el.text != '0':
            continue
        
        title_el = page.find(f'{NS}title')
        if title_el is None:
            continue
        title = title_el.text.strip()
        
        # Skip "Main Page" dan special pages
        if title in ('Main Page',):
            continue
        
        rev = page.find(f'{NS}revision')
        if rev is None:
            continue
        text_el = rev.find(f'{NS}text')
        if text_el is None:
            continue
        wikitext = text_el.text or ''
        
        # Cek apakah ada section Jawa
        if '{{basa|jv}}' not in wikitext:
            continue
        
        n_jv += 1
        
        # Parse sirah
        aksara, kelas, entry_alt = parse_sirah(wikitext)
        
        # Parse definisi
        definisi, terjemahan_indo, contoh = parse_definisi(wikitext)
        
        # Parse ngoko/krama (kalau ada template eksplisit)
        ngoko, krama = parse_ngoko_krama(wikitext)
        
        # Word baku = title (lemma asli jv.wiktionary)
        word = title
        
        if definisi:
            n_with_def += 1
        if terjemahan_indo:
            n_with_indo += 1
        if ngoko or krama:
            n_with_ngoko += 1
        
        entry = {
            'entry_id': n_jv,
            'word': word,  # lemma baku jv.wiktionary
            'aksara': aksara,
            'kelas': kelas,
            'definisi': ' | '.join(definisi) if definisi else '',  # arti Jawa
            'terjemahan_indo': ' | '.join(terjemahan_indo) if terjemahan_indo else '',  # Indonesia dari #::
            'contoh_jawa': ' | '.join(contoh) if contoh else '',
            'ngoko': ngoko,  # dari template {{ngoko|...}} kalau ada
            'krama': krama,  # dari template {{krama|...}} kalau ada
            'keterangan': wikitext[:2000],  # raw wikitext (untuk user verify)
        }
        entries.append(entry)
    
    # Save
    output = {
        'metadata': {
            'version': 'v1 (parser BENAR jv.wiktionary XML)',
            'description': 'Kata Jawa baku dari jv.wiktionary XML dump — penulisan baku + definisi + keterangan',
            'source': 'jv.wiktionary-latest-pages-articles.xml',
            'stats': {
                'total_jv_entries': n_jv,
                'with_definisi': n_with_def,
                'with_terjemahan_indo': n_with_indo,
                'with_ngoko_krama_template': n_with_ngoko,
            },
        },
        'words': entries,
    }
    json.dump(output, open(OUT_PATH, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
    
    print(f'═' * 60)
    print(f'  HASIL PARSING jv.wiktionary XML (BENAR)')
    print(f'═' * 60)
    print(f'  Total jv entries: {n_jv:,}')
    print(f'  Dgn definisi (arti Jawa): {n_with_def:,}')
    print(f'  Dgn terjemahan Indonesia (#::): {n_with_indo:,}')
    print(f'  Dgn template ngoko/krama: {n_with_ngoko:,}')
    print(f'\n  Output: {OUT_PATH}')
    print()
    
    # Sample
    print('=== Sample 10 entries ===')
    for e in entries[:10]:
        print(f"  #{e['entry_id']} word={e['word']!r}")
        print(f"    aksara={e['aksara']!r} kelas={e['kelas']!r}")
        print(f"    definisi={e['definisi'][:80]!r}")
        print(f"    indo={e['terjemahan_indo'][:60]!r}")
        print(f"    ngoko={e['ngoko']!r} krama={e['krama']!r}")
        print()


if __name__ == '__main__':
    main()
