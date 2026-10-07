#!/usr/bin/env python3
"""
parse-wiktionary-jv.py v5 — Parse Wiktionary Jawa XML → kamus-jawa-full.json

FIX v5 (8 Okt 2026, user feedback 'kamus json membingungkan = semua kosakata
didestinasikan sebagai ngoko, padahal ada kosakata yg krama'):

Bug v4: title SELALU di field ngoko, walau Wiktionary tagged {{kr}} (krama)
       atau {{ki}} (krama inggil). Register info dihitung statistik tapi
       tidak disimpan ke JSON.

Fix v5:
  1. Save register tag ({{kn}}, {{kr}}, {{ki}}, {{ak}}) ke field baru 'register'
  2. Put title di field yang benar sesuai register:
       {{kn}}  → ngoko field
       {{kr}}  → krama field
       {{ki}}  → krama_inggil field (NEW)
       {{ak}}  → kawi field (NEW, info saja)
       (umum) → ngoko field (default — tidak ada tag)
  3. Parse cross-references '*Jawa ngoko: [[sapa]]' / '*Jawa krama: [[sinten]]'
     untuk auto-fill mapping kebalikannya.
  4. Tambah kolom krama_inggil + kawi + register

Format BENAR v5:
  Tiap entri:
    ngoko         = kata ngoko + alias (atau KOSONG kalau entry ini krama/krama_inggil)
    aksara        = aksara Jawa
    krama         = kata krama + alias (atau KOSONG kalau entry ini ngoko)
    krama_inggil  = kata krama inggil + alias (NEW)
    kawi          = kata kawi (NEW, info saja)
    arti          = terjemahan Indonesia. KOSONG (user isi manual).
    keterangan    = definisi dari XML (bahasa JAWA, bukan Indonesia). JANGAN HAPUS.
    register      = register asli dari Wiktionary: 'ngoko'|'krama'|'krama_inggil'|'kawi'|'umum'
    sumber        = sumber data (mis. jv.wiktionary.org)

Sebelum v5 (44.585 entri semua di ngoko):
  Entry "sinten" (Wiktionary tag {{kr}}) → {ngoko: "sinten", krama: ""}  ❌
  Entry "kula"   (Wiktionary tag {{kr}}) → {ngoko: "kula", krama: ""}    ❌
  Entry "panjenengan" (Wiktionary tag {{ki}}) → {ngoko: "panjenengan", krama: ""}  ❌

Sesudah v5:
  Entry "sinten" → {ngoko: "", krama: "sinten", register: "krama"}        ✓
  Entry "kula"   → {ngoko: "", krama: "kula", register: "krama"}          ✓
  Entry "panjenengan" → {ngoko: "", krama_inggil: "panjenengan", register: "krama_inggil"}  ✓
  Entry "aku"    → {ngoko: "aku", krama: "", register: "ngoko"}            ✓

Plus cross-reference (kalau entry "sinten" punya baris '*Jawa ngoko: [[sapa]]'):
  Entry "sinten" → {ngoko: "sapa", krama: "sinten", register: "krama",
                    keterangan: "...", sumber: "jv.wiktionary.org + xref"}  ✓ bonus mapping!

Usage:
  python3 parse-wiktionary-jv.py [input.xml] [output.json]

Default:
  input  = /home/z/my-project/upload/wiktionary/wiktionary-jv
  output = /home/z/my-project/public/kamus-jawa-full.json
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

    for line in lines:
        line = line.strip()
        if line.startswith('#'):
            def_text = line[1:].strip()
            def_text = re.sub(r'\{\{[^}]*\}\}', '', def_text)
            def_text = re.sub(r'\[\[([^]]*)\]\]', r'\1', def_text)
            def_text = def_text.strip(' ,;').replace('  ', ' ')

            if def_text and len(def_text) > 1:
                definitions.append(def_text)

    return definitions


def detect_register(wikitext):
    """Deteksi register dari tag Wiktionary di section Jawa.

    Returns:
      'ngoko'         — kalau ada {{kn}} di section Jawa
      'krama_inggil'  — kalau ada {{ki}} TAPI tidak ada {{kn}}
      'kawi'          — kalau ada {{ak}} TAPI tidak ada {{kn}}/{{ki}}
      'umum'          — tidak ada tag (default)
    """
    jv_start = wikitext.find('{{basa|jv}}')
    if jv_start == -1:
        return 'umum'

    jv_section = wikitext[jv_start:]
    sikil = jv_section.find('{{sikil}}')
    if sikil != -1:
        jv_section = jv_section[:sikil]

    if '{{kn}}' in jv_section:
        return 'ngoko'
    if '{{ki}}' in jv_section:
        return 'krama_inggil'
    if '{{ak}}' in jv_section:
        return 'kawi'
    return 'umum'


def detect_dual_register(wikitext):
    """Cek apakah entry punya multiple register tags sekaligus.

    Beberapa entry punya {{kn}} + {{ki}} = kata yang sama dipakai untuk ngoko
    DAN krama inggil (mis. "panjenengan" bisa ngoko formal atau krama inggil).

    Returns set of register yang dimiliki entry ini.
    """
    jv_start = wikitext.find('{{basa|jv}}')
    if jv_start == -1:
        return set()

    jv_section = wikitext[jv_start:]
    sikil = jv_section.find('{{sikil}}')
    if sikil != -1:
        jv_section = jv_section[:sikil]

    registers = set()
    if '{{kn}}' in jv_section:
        registers.add('ngoko')
    if '{{ki}}' in jv_section:
        registers.add('krama_inggil')
    if '{{ak}}' in jv_section:
        registers.add('kawi')
    return registers


def extract_template_words(wikitext):
    """Parse template {{ngoko|word}}, {{krama|word1|word2|...}}, {{ki|word}} di section Jawa.

    Templates ini adalah cross-reference antar register:
      {{ngoko|abrit}}  → "entry ini ngoko, krama equivalent adalah abrit"
      {{krama|abang}}  → "entry ini krama, ngoko equivalent adalah abang"
      {{krama|ayo|enya|mara}} → "entry ini krama, ngoko equivalents: ayo, enya, mara"

    Returns dict: {ngoko: [...], krama: [...], krama_inggil: [...]}
    """
    jv_start = wikitext.find('{{basa|jv}}')
    if jv_start == -1:
        return {'ngoko': [], 'krama': [], 'krama_inggil': []}

    jv_section = wikitext[jv_start:]
    sikil = jv_section.find('{{sikil}}')
    if sikil != -1:
        jv_section = jv_section[:sikil]

    refs = {'ngoko': [], 'krama': [], 'krama_inggil': []}

    # Pattern: {{ngoko|word1|word2|...}}, {{krama|word1|word2|...}}, {{ki|word1|word2|...}}
    # Capture all parameters (dipisah |)
    patterns = [
        (r'\{\{ngoko\|([^}]+)\}\}', 'ngoko'),
        (r'\{\{krama\|([^}]+)\}\}', 'krama'),
        (r'\{\{ki\|([^}]+)\}\}', 'krama_inggil'),
    ]

    for pattern, ref_type in patterns:
        for m in re.finditer(pattern, jv_section, re.IGNORECASE):
            # Split parameters by |, ambil semua word
            params = m.group(1).split('|')
            for param in params:
                word = param.strip()
                # Skip parameter yang ada '=' (named parameter mis. alt=ꦲꦧꦁ)
                if '=' in word:
                    continue
                # Skip namespace prefixes
                if word.startswith(':'):
                    continue
                # Skip empty
                if not word:
                    continue
                if word not in refs[ref_type]:
                    refs[ref_type].append(word)

    return refs


def extract_cross_references(wikitext):
    """Parse cross-references '*Jawa ngoko: [[sapa]]' / '*Jawa krama: [[sinten]]'.

    Cari di SELURUH wikitext (bukan hanya section Jawa), karena cross-references
    biasanya muncul di section 'Basa liyane' (other languages translations).

    Returns dict dengan keys: ngoko, krama, krama_inggil (masing-masing list of words).
    """
    refs = {'ngoko': [], 'krama': [], 'krama_inggil': []}

    patterns = [
        (r'\*\s*Jawa\s+ngoko\s*:\s*\[\[([^\]]+)\]\]', 'ngoko'),
        (r'\*\s*Jawa\s+krama\s+inggil\s*:\s*\[\[([^\]]+)\]\]', 'krama_inggil'),
        (r'\*\s*Jawa\s+krama\s*:\s*\[\[([^\]]+)\]\]', 'krama'),
    ]

    for pattern, ref_type in patterns:
        for m in re.finditer(pattern, wikitext, re.IGNORECASE):
            word = m.group(1).strip()
            # Filter: skip words with '|' (e.g., [[sapa|sapa]])
            if '|' in word:
                word = word.split('|')[0].strip()
            # Skip non-Jawa (e.g., [[:jv:wétan]] — prefixed with namespace)
            if word.startswith(':'):
                continue
            if word and word not in refs[ref_type]:
                refs[ref_type].append(word)

    return refs


def parse_xml_to_json(xml_path, output_path):
    print(f'Parsing {xml_path}...')
    tree = ET.parse(xml_path)
    root = tree.getroot()

    words = []
    stats = {
        'total': 0, 'jv': 0, 'with_defs': 0, 'with_aksara': 0,
        'with_xref': 0, 'with_xref_filled': 0, 'wikisastra_pages': 0,
    }
    register_count = {'ngoko': 0, 'krama': 0, 'krama_inggil': 0, 'kawi': 0, 'umum': 0}

    # === Phase 1: Process Wikisastra:Bausastra Jawa/* pages — build xref map ===
    # Pages seperti "Wikisastra:Bausastra Jawa/sapa" berisi cross-reference
    # '*Jawa ngoko: [[sapa]]' + '*Jawa krama: [[sinten]]' → mapping ngoko↔krama
    xref_map = {}  # ngoko_word → {krama: [...], krama_inggil: [...]}

    for page in root.findall('.//mw:page', NS):
        title = page.find('mw:title', NS)
        if title is None or not title.text:
            continue
        title_text = title.text

        # Hanya proses "Wikisastra:Bausastra Jawa/<word>" pages
        if 'Wikisastra:Bausastra Jawa/' not in title_text:
            continue

        text_elem = page.find('.//mw:text', NS)
        if text_elem is None or not text_elem.text:
            continue

        wikitext = text_elem.text
        stats['wikisastra_pages'] += 1

        # Extract source word dari title (e.g., "Wikisastra:Bausastra Jawa/sapa" → "sapa")
        source_word = title_text.split('Wikisastra:Bausastra Jawa/')[-1].strip()
        if not source_word or ':' in source_word or '/' in source_word:
            continue

        xrefs = extract_cross_references(wikitext)

        # Build xref map: prefer using the ngoko word from xref as the KEY
        # (kalau xref punya "*Jawa ngoko: [[sapa]]", pakai "sapa" sebagai key,
        #  bukan source_word dari title — karena title bisa berupa kata Indonesia
        #  seperti "siapa" padahal ngoko asli = "sapa")
        krama_list = xrefs['krama']
        krama_inggil_list = xrefs['krama_inggil']
        ngoko_list = xrefs['ngoko']

        # Tentukan ngoko key:
        # - Kalau ada xref ngoko → pakai xref ngoko word (lebih reliable)
        # - Kalau tidak ada xref ngoko → pakai source_word dari title (asumsi: source = ngoko)
        if ngoko_list:
            # Pakai xref ngoko sebagai key (bukan source_word dari title)
            for ngoko_word in ngoko_list:
                if ngoko_word not in xref_map:
                    xref_map[ngoko_word] = {'krama': [], 'krama_inggil': []}
                for krama_word in krama_list:
                    if krama_word and krama_word not in xref_map[ngoko_word]['krama']:
                        xref_map[ngoko_word]['krama'].append(krama_word)
                for ki_word in krama_inggil_list:
                    if ki_word and ki_word not in xref_map[ngoko_word]['krama_inggil']:
                        xref_map[ngoko_word]['krama_inggil'].append(ki_word)
        else:
            # Tidak ada xref ngoko — pakai source_word dari title sebagai ngoko
            if source_word not in xref_map:
                xref_map[source_word] = {'krama': [], 'krama_inggil': []}
            for krama_word in krama_list:
                if krama_word and krama_word not in xref_map[source_word]['krama']:
                    xref_map[source_word]['krama'].append(krama_word)
            for ki_word in krama_inggil_list:
                if ki_word and ki_word not in xref_map[source_word]['krama_inggil']:
                    xref_map[source_word]['krama_inggil'].append(ki_word)

    print(f'   Wikisastra xref map: {len(xref_map)} ngoko entries with krama mapping')

    # === Phase 2: Process ns=0 pages (utama — definisi kata Jawa) ===
    # Build reverse lookup: krama_word → ngoko_word, krama_inggil_word → ngoko_word
    # (untuk deteksi: kalau title di ns=0 ada di krama/krama_inggil xref, register harusnya krama/krama_inggil)
    krama_to_ngoko = {}
    krama_inggil_to_ngoko = {}
    for ngoko_word, xref in xref_map.items():
        for krama_word in xref['krama']:
            krama_to_ngoko[krama_word] = ngoko_word
        for ki_word in xref['krama_inggil']:
            krama_inggil_to_ngoko[ki_word] = ngoko_word

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

        # Detect register dari tag Wiktionary (single-tag detection)
        register = detect_register(wikitext)

        # Detect dual register (entries with {{kn}} + {{ki}} = kata yang sama untuk ngoko DAN krama inggil)
        dual_registers = detect_dual_register(wikitext)
        is_dual_ngoko_krama_inggil = 'ngoko' in dual_registers and 'krama_inggil' in dual_registers

        # FIX: kalau register='umum' TAPI title ada di krama_to_ngoko atau krama_inggil_to_ngoko,
        # berarti title ini sebenarnya adalah kata krama/krama_inggil (bukan ngoko)
        # Override register ke krama/krama_inggil
        if register == 'umum':
            if title_text in krama_to_ngoko:
                register = 'krama'
            elif title_text in krama_inggil_to_ngoko:
                register = 'krama_inggil'

        # Extract template cross-references: {{ngoko|word}}, {{krama|word}}, {{ki|word}}
        # SEMANTIK WIKISASTRA (ditemukan 8 Okt 2026 setelah user complaint):
        #   {{ngoko|X}} di entry Y → Y adalah ngoko, X adalah krama equivalent
        #   {{krama|X}} di entry Y → Y adalah krama, X adalah ngoko equivalent
        #   {{ki|X}} di entry Y → Y adalah krama_inggil, X adalah ngoko equivalent
        # Jadi template name = register entry ini sendiri, parameter = register kebalikannya
        template_refs = extract_template_words(wikitext)

        # Override register berdasarkan template (lebih reliable daripada tag {{kn}}/{{ki}})
        if template_refs['krama'] and register == 'umum':
            # {{krama|X}} → entry ini krama
            register = 'krama'
        elif template_refs['krama_inggil'] and register == 'umum':
            # {{ki|X}} → entry ini krama_inggil
            register = 'krama_inggil'
        elif template_refs['ngoko'] and register == 'umum':
            # {{ngoko|X}} → entry ini ngoko
            register = 'ngoko'

        register_count[register] = register_count.get(register, 0) + 1

        # Format v5: put title di field yang benar sesuai register
        ngoko = ''
        krama = ''
        krama_inggil = ''

        if is_dual_ngoko_krama_inggil:
            # Entry ini dipakai untuk ngoko DAN krama_inggil (mis. "panjenengan")
            # Title goes to BOTH fields
            ngoko = title_text
            krama_inggil = title_text
        elif register == 'ngoko' or register == 'umum':
            ngoko = title_text
        elif register == 'krama':
            krama = title_text
        elif register == 'krama_inggil':
            krama_inggil = title_text

        # === AUTO-FILL MAPPING dari template (semantik Wikisastra) ===
        # {{ngoko|X}} di entry Y → Y adalah ngoko, X adalah krama equivalent → set krama=X
        # {{krama|X}} di entry Y → Y adalah krama, X adalah ngoko equivalent → set ngoko=X
        # {{ki|X}} di entry Y → Y adalah krama_inggil, X adalah ngoko equivalent → set ngoko=X
        #
        # Catatan: entry bisa punya multiple sub-entries dengan register berbeda
        # (mis. "mangga" num=2 krama + num=3 ngoko). Template tetap dipakai untuk
        # fill cross-reference field, bahkan kalau register title sudah di-set
        # dari sub-entry lain.
        #
        # ANTI SELF-REFERENCE: jangan set krama=title kalau title sudah di ngoko field
        # (mis. "mangga" punya {{kn}} (ngoko) + {{krama|ayo}} (krama sub-entry) →
        # ngoko=mangga, krama=ayo — bukan krama=mangga)
        sumber_mod = SOURCE_NAME
        if template_refs['ngoko']:
            # Entry Y is ngoko (confirmed), X is krama equivalent
            # Title sudah di ngoko field (dari register detection), sekarang fill krama
            if not krama:
                krama = ', '.join(template_refs['ngoko'])
                sumber_mod = f'{SOURCE_NAME} + template'
                stats['with_xref_filled'] += 1
        if template_refs['krama']:
            # Entry Y is krama (confirmed), X is ngoko equivalent
            # Set ngoko = X (cross-reference)
            if not ngoko:
                ngoko = ', '.join(template_refs['krama'])
                sumber_mod = f'{SOURCE_NAME} + template'
                stats['with_xref_filled'] += 1
            # Set krama = title ONLY if ngoko is not title (avoid self-reference)
            # Mis. entry "abrit" (no {{kn}}, only {{krama|abang}}) → ngoko=abang, krama=abrit (title)
            # Mis. entry "mangga" (has {{kn}} + {{krama|ayo}}) → ngoko=mangga (title from {{kn}}),
            #   krama=ayo (from template) — JANGAN set krama=mangga (self-reference)
            if not krama and ngoko != title_text and register != 'ngoko':
                krama = title_text
                sumber_mod = f'{SOURCE_NAME} + template'
                stats['with_xref_filled'] += 1
        if template_refs['krama_inggil']:
            # Entry Y is krama_inggil (confirmed), X is ngoko equivalent
            if not ngoko:
                ngoko = ', '.join(template_refs['krama_inggil'])
                sumber_mod = f'{SOURCE_NAME} + template'
                stats['with_xref_filled'] += 1
            # Set krama_inggil = title ONLY if ngoko is not title (avoid self-reference)
            if not krama_inggil and ngoko != title_text and register != 'ngoko':
                krama_inggil = title_text
                sumber_mod = f'{SOURCE_NAME} + template'
                stats['with_xref_filled'] += 1

        # Bonus: pakai xref_map (dari Wikisastra pages) untuk auto-fill mapping kalau template tidak ada
        # HANYA fill field yang masih kosong — jangan overwrite field yang sudah di-set dari title/template
        if ngoko and ngoko in xref_map:
            xref = xref_map[ngoko]
            if xref['krama'] and not krama:
                krama = ', '.join(xref['krama'])
                sumber_mod = f'{SOURCE_NAME} + xref'
                stats['with_xref_filled'] += 1
            if xref['krama_inggil'] and not krama_inggil:
                krama_inggil = ', '.join(xref['krama_inggil'])
                sumber_mod = f'{SOURCE_NAME} + xref'
                stats['with_xref_filled'] += 1
        # Kalau title adalah krama DAN ngoko masih kosong, cek reverse map
        # JANGAN overwrite ngoko yang sudah di-set dari title
        elif krama and not ngoko and krama in krama_to_ngoko:
            ngoko = krama_to_ngoko[krama]
            sumber_mod = f'{SOURCE_NAME} + xref'
            stats['with_xref_filled'] += 1
        elif krama_inggil and not ngoko and krama_inggil in krama_inggil_to_ngoko:
            ngoko = krama_inggil_to_ngoko[krama_inggil]
            sumber_mod = f'{SOURCE_NAME} + xref'
            stats['with_xref_filled'] += 1

        # KETERANGAN = definisi JAWA dari XML (JANGAN HAPUS, membantu user isi id)
        keterangan = '; '.join(defs) if defs else ''
        if defs:
            stats['with_defs'] += 1

        # Format BENAR v5
        entry = {
            'ngoko': ngoko,
            'aksara': aksara,
            'krama': krama,
            'arti': '',              # KOSONG — user isi manual (terjemahan Indonesia)
            'keterangan': keterangan,
            'register': register,
            'sumber': sumber_mod,
        }
        # Hanya simpan krama_inggil kalau tidak kosong (hemat space)
        if krama_inggil:
            entry['krama_inggil'] = krama_inggil
        words.append(entry)

    # Sort by register priority (ngoko dulu, lalu krama, lalu krama_inggil, lalu kawi, lalu umum)
    register_order = {'ngoko': 0, 'umum': 1, 'krama': 2, 'krama_inggil': 3, 'kawi': 4}
    words.sort(key=lambda w: (
        register_order.get(w.get('register', 'umum'), 99),
        w.get('ngoko') or w.get('krama') or w.get('krama_inggil') or w.get('kawi') or '',
    ))

    # Tambah entry_id (1-indexed) supaya user bisa referensi by number
    # Berguna untuk merge entries (mis. "sing" entry #123 + "ingkang" entry #456 → 1 entry)
    for i, w in enumerate(words, 1):
        w['entry_id'] = i

    output = {
        'metadata': {
            'version': '5.0',
            'source': SOURCE_NAME,
            'entries': len(words),
            'register_breakdown': register_count,
            'with_aksara': stats['with_aksara'],
            'with_keterangan': stats['with_defs'],
            'with_xref': stats['with_xref'],
            'with_xref_filled': stats['with_xref_filled'],
            'note': (
                'Format v5: ngoko/krama/krama_inggil di field yang benar sesuai register tag Wiktionary. '
                'Cross-reference auto-fill (mis. entry "sinten" dengan xref "*Jawa ngoko: [[sapa]]" → '
                '{ngoko:"sapa", krama:"sinten"}). Aksén Jawa tidak dipakai untuk TTS (auto-strip). '
                'arti kosong — user isi manual. keterangan = definisi JAWA dari XML (JANGAN HAPUS).'
            ),
        },
        'words': words,
    }

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f'\n✅ Parsed v5:')
    print(f'   Total pages: {stats["total"]}')
    print(f'   Jawa entries: {stats["jv"]}')
    print(f'   With keterangan (def Jawa): {stats["with_defs"]}')
    print(f'   With aksara: {stats["with_aksara"]}')
    print(f'   With xref: {stats["with_xref"]} ({stats["with_xref_filled"]} auto-filled mapping)')
    print(f'   Total in JSON: {len(words)}')
    print(f'   Register breakdown (TITLE register, bukan total mapping):')
    for r, c in sorted(register_count.items(), key=lambda x: -x[1]):
        print(f'     {r:15s}: {c:6d}')
    print(f'   arti: 0 (kosong, user isi manual)')
    print(f'   Output: {output_path}')
    print(f'   Size: {Path(output_path).stat().st_size / 1024 / 1024:.1f} MB')


if __name__ == '__main__':
    parse_xml_to_json(INPUT_XML, OUTPUT_JSON)
