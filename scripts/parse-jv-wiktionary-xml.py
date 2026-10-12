#!/usr/bin/env python3
"""parse-jv-wiktionary-xml.py — Parse XML dump jv.wiktionary ke JSON standar.

Sumber: https://dumps.wikimedia.org/jvwiktionary/latest/jvwiktionary-latest-pages-articles.xml.bz2
File lokal: /tmp/wikt-raw/jv.xml (sudah di-download + extract)

Prinsip parsing MINIMAL (R-22 compliant — bukan AI scrape, dump resmi Wikimedia):
- 1 <page> dengan ns=0 (namespace utama, bukan Kategori/Parembugan) = 1 entry
- <title> = word (lemma asli, tanpa manipulasi)
- Extract dari <text> wiki markup:
  * {{sirah|jv|entry=...|alt=...|kelas=...}} → aksara + kelas
  * {{ngoko|...}} → krama (1 kata, TIDAK split comma)
  * {{inggil=...}} di template ngoko → krama_inggil (akan di-drop karena R-26)
  * # ... (definisi list) → arti (gabung baris dengan ; )
  * Sisa wikitext → keterangan (konteks penuh, untuk user verify)
- TIDAK ADA merge sinonim dari sumber beda
- TIDAK ADA comma split yang bikin 15 kata di 1 field
- TIDAK ADA AI tolol yang tebak-nebak

Output: public/kamus_jv_wiktionary_raw.json — 20 field standar match kamus draft (R-26)
"""
import json
import re
from pathlib import Path
import xml.etree.ElementTree as ET

XML_PATH = Path('/tmp/wikt-raw/jv.xml')
OUT_PATH = Path('/home/z/my-project/public/kamus_jv_wiktionary_raw.json')

# Namespace MediaWiki XML
NS = '{http://www.mediawiki.org/xml/export-0.11/}'


def parse_sirah_template(wikitext):
    """Extract aksara + kelas dari {{sirah|jv|entry=...|alt=...|kelas=...}}"""
    aksara = ''
    kelas = ''
    # Match: {{sirah|jv|entry=...|alt=...|kelas=...}}
    m = re.search(r'\{\{sirah\|jv[^}]*\}\}', wikitext)
    if m:
        tpl = m.group(0)
        # alt=aksara
        alt_m = re.search(r'\|alt=([^|}]+)', tpl)
        if alt_m:
            aksara = alt_m.group(1).strip()
        # kelas=...
        kelas_m = re.search(r'\|kelas=([^|}]+)', tpl)
        if kelas_m:
            kelas = kelas_m.group(1).strip()
    return aksara, kelas


def parse_ngoko_template(wikitext):
    """Extract krama + krama_inggil dari {{ngoko|krama|inggil=...}}
    
    Pattern:
      {{ngoko|nedha}}              → krama='nedha', inggil=''
      {{ngoko|nedha|inggil=dhahar}} → krama='nedha', inggil='dhahar'
      {{ngoko|inggil=saré}}         → krama='', inggil='saré'  (BUG SEBELUMNYA)
    """
    krama = ''
    krama_inggil = ''
    # Match full template {{ngoko|...}}
    m = re.search(r'\{\{ngoko\|([^}]*)\}\}', wikitext)
    if m:
        params = m.group(1)  # mis. "nedha|inggil=dhahar" atau "inggil=saré"
        # Split by | untuk dapat parameter list
        parts = params.split('|')
        for part in parts:
            part = part.strip()
            if not part:
                continue
            # Kalau part pakai "key=value"
            if '=' in part:
                key, val = part.split('=', 1)
                key = key.strip().lower()
                val = val.strip()
                if key == 'inggil':
                    krama_inggil = val
            else:
                # Parameter pertama = krama (kalau belum di-set)
                if not krama:
                    krama = part
    return krama, krama_inggil


def parse_definisi(wikitext):
    """Extract definisi dari # ... (list). Gabung baris dengan ; jika multi."""
    arti_list = []
    lines = wikitext.split('\n')
    for line in lines:
        stripped = line.strip()
        # Definisi dimulai dengan # di awal baris
        if stripped.startswith('#'):
            # Remove leading # dan strip
            def_text = stripped.lstrip('#').strip()
            # Hilangkan wiki template inline {{...}} tapi preserve teks dalam
            def_text = re.sub(r'\{\{[^}]*\}\}', '', def_text).strip()
            # Hilangkan wiki link [[...]] → text (handle Kategori:, :, |)
            # [[Kategori:Sukerta]] → '' (hapus, kategori bukan konten)
            def_text = re.sub(r'\[\[(Kategori|Category):[^\]]*\]\]', '', def_text, flags=re.IGNORECASE).strip()
            # [[text|display]] → display
            def_text = re.sub(r'\[\[([^]|]+)\|([^\]]+)\]\]', r'\2', def_text).strip()
            # [[text]] → text
            def_text = re.sub(r'\[\[([^\]]+)\]\]', r'\1', def_text).strip()
            # Hilangkan ''' bold '''
            def_text = def_text.replace("'''", "").strip()
            # Hilangkan '' italic ''
            def_text = def_text.replace("''", "").strip()
            # Multi-space → single
            def_text = re.sub(r'\s+', ' ', def_text).strip()
            # Skip empty after cleanup
            if def_text:
                arti_list.append(def_text)
    return '; '.join(arti_list) if arti_list else ''


def build_keterangan(wikitext):
    """Full wikitext asli untuk konteks user (preserve semua)."""
    # Hilangkan template sirah, ngoko, basa, def, sikil (header)
    # Tapi keep semua definisi + konteks
    # Untuk display TUI, keterangan = wikitext cleaned tanpa header template
    lines = wikitext.split('\n')
    cleaned = []
    skip_header = True
    for line in lines:
        stripped = line.strip()
        # Skip section header template
        if stripped.startswith('{{basa|') or stripped.startswith('{{-def-|') or stripped.startswith('{{sikil}}'):
            continue
        if stripped.startswith('{{sirah|'):
            continue
        cleaned.append(line)
    return '\n'.join(cleaned).strip()


def parse_xml_to_entries(xml_path):
    """Parse XML, return list of entry dict (20 field standar)."""
    entries = []
    print(f'→ Parse {xml_path}...')
    
    # Parse XML secara streaming (file 86 MB)
    context = ET.iterparse(str(xml_path), events=('end',))
    
    pages_count = 0
    lemma_count = 0
    skipped_ns = 0
    skipped_redirect = 0
    skipped_empty = 0
    
    for event, elem in context:
        if elem.tag != f'{NS}page':
            continue
        pages_count += 1
        
        # Get ns (namespace) — hanya ns=0 (main namespace)
        ns_elem = elem.find(f'{NS}ns')
        if ns_elem is None or ns_elem.text != '0':
            skipped_ns += 1
            elem.clear()
            continue
        
        # Get title
        title_elem = elem.find(f'{NS}title')
        if title_elem is None:
            skipped_empty += 1
            elem.clear()
            continue
        title = title_elem.text or ''
        title = title.strip()
        
        # Skip redirect (judul diawali #REDIRECT)
        text_elem = elem.find(f'.//{NS}text')
        if text_elem is None or not text_elem.text:
            skipped_empty += 1
            elem.clear()
            continue
        wikitext = text_elem.text
        
        if wikitext.strip().upper().startswith('#REDIRECT') or wikitext.strip().upper().startswith('#ALIH'):
            skipped_redirect += 1
            elem.clear()
            continue
        
        # Skip pages tanpa {{sirah|jv (bukan lemma Jawa)
        if '{{sirah|jv' not in wikitext:
            skipped_empty += 1
            elem.clear()
            continue
        
        lemma_count += 1
        
        # Parse template
        aksara, kelas = parse_sirah_template(wikitext)
        krama, krama_inggil = parse_ngoko_template(wikitext)
        arti = parse_definisi(wikitext)
        keterangan = build_keterangan(wikitext)
        
        # R-17: krama_inggil masuk ke krama (comma). Ini bukan merge AI tolol —
        # info dari 1 template {{ngoko|krama|inggil=...}} = 1 entry.
        if krama_inggil:
            if krama:
                krama = f'{krama}, {krama_inggil}'
            else:
                # Kasus {{ngoko|inggil=saré}} — hanya krama_inggil, krama kosong
                krama = krama_inggil
        
        # Build entry 20 field standar (R-26 compliant, no register + no krama_inggil)
        # Field order match kamus-jawa-draft.json v2.7
        entry = {
            'entry_id': lemma_count,  # akan di-re-number di akhir
            'word': title,
            'ngoko': '',  # lemma = title, ngoko field kosong (match pattern NETRAL)
            'krama': krama,  # dari {{ngoko|...}}
            'arti': arti,  # dari # definisi
            'keterangan': keterangan,
            'aksara': aksara,  # dari {{sirah|alt=...}}
            'sumber': 'jv.wiktionary.org (XML dump, parsed minimal)',
            'is_lemma': True,
            'is_mendeley': False,
            'is_dasanama': False,
            'is_angka': False,
            'is_lampiran': False,
            'kelas': kelas,
            'kelas_nama': '',  # kelas_nama di-drop di wiktionary raw (sudah ada di kelas)
            'lemma_words': title,  # = word
            'mendeley_id': '',
            'dasanama_count': 0,
            'source_count': 1,
            'status': 'draft',
        }
        entries.append(entry)
        
        # Clear elem supaya memory tidak penuh
        elem.clear()
        
        if lemma_count % 5000 == 0:
            print(f'  Parsed {lemma_count} lemma entries...')
    
    print(f'\n  Total <page> elements: {pages_count:,}')
    print(f'  Lemma entries (ns=0 + sirah|jv + no redirect): {lemma_count:,}')
    print(f'  Skipped (non-ns=0):                          {skipped_ns:,}')
    print(f'  Skipped (redirect/empty/no sirah|jv):          {skipped_empty:,}')
    print(f'  Skipped (redirect):                          {skipped_redirect:,}')
    return entries


def main():
    if not XML_PATH.exists():
        print(f'❌ XML tidak ada: {XML_PATH}')
        print(f'   Download dulu:')
        print(f'   curl -L -o /tmp/wikt-raw/jv.xml.bz2 \\')
        print(f'     "https://dumps.wikimedia.org/jvwiktionary/latest/jvwiktionary-latest-pages-articles.xml.bz2"')
        print(f'   bunzip2 /tmp/wikt-raw/jv.xml.bz2')
        return
    
    entries = parse_xml_to_entries(XML_PATH)
    
    # Build output JSON
    print(f'\n→ Build output JSON...')
    data = {
        'metadata': {
            'version': 'v1.0 (jv wiktionary XML dump, parsed minimal)',
            'description': 'Kamus Jawa dari jv.wiktionary.org (Wikisastra) XML dump. Parsing minimal: 1 lemma = 1 entry, TIDAK ADA merge sinonim. Sumber resmi Wikimedia dumps, BUKAN scrape AI. 20 field standar match kamus-jawa-draft.json v2.7 (R-26 compliant).',
            'source_url': 'https://dumps.wikimedia.org/jvwiktionary/latest/jvwiktionary-latest-pages-articles.xml.bz2',
            'source_size_compressed': '8.5 MB',
            'source_size_extracted': '86 MB',
            'parser': 'parse-jv-wiktionary-xml.py (parsing minimal, no merge)',
            'schema_version': 'v2.7 (R-26 drop register + krama_inggil)',
            'total_entries': len(entries),
        },
        'words': entries,
    }
    
    # Write
    print(f'→ Write ke {OUT_PATH.name}...')
    with open(OUT_PATH, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    
    size = OUT_PATH.stat().st_size
    print(f'  ✅ Saved: {OUT_PATH}')
    print(f'  Size: {size:,} bytes ({size/1024/1024:.2f} MB)')
    
    # Sample 3 entries
    print(f'\n→ Sample 3 entries:')
    for w in entries[:3]:
        print(f'\n  entry_id={w["entry_id"]}:')
        print(f'    word:    {w["word"]!r}')
        print(f'    aksara:  {w["aksara"]!r}')
        print(f'    kelas:   {w["kelas"]!r}')
        print(f'    krama:   {w["krama"]!r}')
        print(f'    arti:    {w["arti"]!r}')
        ket = w['keterangan']
        if ket:
            print(f'    keterangan (first 200): {ket[:200]!r}')


if __name__ == '__main__':
    main()
