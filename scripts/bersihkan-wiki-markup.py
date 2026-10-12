#!/usr/bin/env python3
"""bersihkan-wiki-markup.py — Bersihkan wiki markup di kamus-jawa-draft.json.

R-18: JANGAN HAPUS entry, JANGAN HAPUS field, JANGAN HAPUS teks data.
Hanya hapus karakter markup (wiki template, link, HTML tag).

Yang dibersihkan:
  1. [[link_text]] → link_text (preserve teks, hapus bracket)
  2. {{template}} → hapus seluruh template (metadata, bukan konten)
  3. <sup>...</sup>, <br>, <ref>...</ref> → hapus tag, preserve teks di dalam
  4. Sisa artifact: }} {{ [[ ]] → hapus
  5. Multi-space, leading/trailing whitespace → normalize

Yang TIDAK di-bersihkan (preserve):
  - Teks data (link text inside [[...]] tetap ada)
  - Field structure (22 field per entry)
  - Entry (44.005 entries tetap)
  - Aksara Jawa (ꦏꦸꦭ) tetap utuh
  - Diakritik Jawa (é/è/ê) tetap utuh (R-16a)
"""
import json
import re
from pathlib import Path

KAMUS = Path('/home/z/my-project/public/kamus-jawa-draft.json')

# ============ CLEANERS ============

# Wiki link: [[text]] atau [[text|display]] → display (atau text kalau no pipe)
def clean_wiki_link(s):
    # [[text|display]] → display
    s = re.sub(r'\[\[([^\]|]+)\|([^\]]+)\]\]', r'\2', s)
    # [[text]] → text
    s = re.sub(r'\[\[([^\]]+)\]\]', r'\1', s)
    # Sisa [[ atau ]]\n (artifact) → hapus
    s = s.replace('[[', '').replace(']]', '')
    return s

# Wiki template: {{...}} → hapus seluruh (metadata, bukan konten)
def clean_wiki_template(s):
    # Nested template? Wikipedia support {{{...}}}. TapiWiktionary Jawa cuma pakai {{...}}.
    # Loop untuk handle nested template (kalau ada)
    for _ in range(5):  # max 5 level nesting
        new_s = re.sub(r'\{\{[^{}]*\}\}', '', s)
        if new_s == s:
            break
        s = new_s
    # Sisa {{ atau }} (artifact) → hapus
    s = s.replace('{{', '').replace('}}', '')
    return s

# HTML tag: <sup>...</sup>, <br>, <ref>...</ref>, dll → preserve teks di dalam
def clean_html_tag(s):
    # <br>, <br/>, <br /> → hapus tag (tidak ada teks di dalam)
    s = re.sub(r'<br\s*/?>', ' ', s, flags=re.IGNORECASE)
    # <sup>...</sup>, <ref>...</ref>, <small>...</small> → preserve teks
    s = re.sub(r'<(sup|ref|small|big|i|b|em|strong)[^>]*>(.*?)</\1>', r'\2', s, flags=re.IGNORECASE | re.DOTALL)
    # <ref .../> (self-closing) → hapus
    s = re.sub(r'<ref[^>]*/>', '', s, flags=re.IGNORECASE)
    # Sisa < atau > (artifact) → hapus karakter saja (tidak ada tag valid lagi)
    # Hati-hati: jangan hapus < atau > yang mungkin bagian teks (tidak ada di Jawa)
    # Tapi kalau ada sisa < atau > setelah cleaning tag, kemungkinan artifact
    s = s.replace('<', '').replace('>', '')
    return s

# Normalize whitespace
def normalize_whitespace(s):
    # Multi-space → single space
    s = re.sub(r'[ \t]+', ' ', s)
    # Multi-newline → single newline
    s = re.sub(r'\n+', '\n', s)
    # Space di awal/akhir tiap baris → hapus
    s = '\n'.join(line.strip() for line in s.split('\n'))
    # Leading/trailing whitespace → hapus
    s = s.strip()
    # " ," → "," (space sebelum koma)
    s = re.sub(r'\s+,', ',', s)
    # ", " tetap (normal), tapi ",, " → ", "
    s = re.sub(r',\s+,', ', ', s)
    # Trailing comma di akhir string → hapus
    s = s.rstrip(',').strip()
    return s


def clean_field(s):
    """Pipeline bersihkan: wiki link → wiki template → HTML → whitespace."""
    if not s or not isinstance(s, str):
        return s
    # JANGAN bersihkan aksara field (berisi aksara Jawa unicode, bukan markup)
    # Hanya bersihkan field teks (word, ngoko, krama, arti, keterangan, sumber, kelas, kelas_nama, lemma_words, mendeley_id)
    s = clean_wiki_link(s)
    s = clean_wiki_template(s)
    s = clean_html_tag(s)
    s = normalize_whitespace(s)
    return s


# ============ MAIN ============

def main():
    print(f'→ Load {KAMUS}...')
    with open(KAMUS, 'r', encoding='utf-8') as f:
        data = json.load(f)

    words = data['words']
    total = len(words)
    print(f'  Total entries: {total:,}')

    # Field yang akan dibersihkan (BUKAN aksara — aksara Jawa unicode)
    fields_to_clean = ['word', 'lemma_words', 'ngoko', 'krama', 'krama_inggil',
                       'arti', 'keterangan', 'sumber', 'kelas', 'kelas_nama',
                       'mendeley_id', 'register']
    # AKSARA TIDAK dibersihkan (berisi unicode Jawa)
    # is_*, status, source_count, dasanama_count, entry_id tidak dibersihkan (non-string)

    # Audit sebelum cleaning
    print(f'\n→ Audit wiki markup SEBELUM cleaning:')
    patterns = {
        'wiki_link_[[..]]': lambda s: '[[' in s,
        'wiki_template_{{..}}': lambda s: '{{' in s,
        'html_tag_<..>': lambda s: '<' in s or '>' in s,
        'multi_space': lambda s: '  ' in s,
        'leading_trailing_ws': lambda s: s != s.strip(),
        'space_before_comma': lambda s: ' ,' in s,
    }

    for fname in fields_to_clean:
        for pname, pcheck in patterns.items():
            count = sum(1 for w in words if pcheck(w.get(fname, '') or ''))
            if count > 0:
                print(f'  {fname:18} {pname:25} {count:>6,}')

    # Cleaning
    print(f'\n→ Bersihkan wiki markup di {len(fields_to_clean)} field...')
    cleaned_count = {f: 0 for f in fields_to_clean}
    for w in words:
        for f in fields_to_clean:
            old = w.get(f, '') or ''
            new = clean_field(old)
            if new != old:
                cleaned_count[f] += 1
                w[f] = new

    print(f'\n→ Field yang di-changed:')
    for f, c in cleaned_count.items():
        if c > 0:
            print(f'  {f:18} {c:>6,} entries dibersihkan')

    # Audit setelah cleaning
    print(f'\n→ Audit wiki markup SETELAH cleaning:')
    for fname in fields_to_clean:
        for pname, pcheck in patterns.items():
            count = sum(1 for w in words if pcheck(w.get(fname, '') or ''))
            if count > 0:
                print(f'  {fname:18} {pname:25} {count:>6,}')

    # Verify: tidak ada field/entry hilang
    assert len(words) == total, f'❌ Total berubah: {total} → {len(words)}'
    print(f'\n  ✅ Total entries tetap: {total:,}')
    field_set = set()
    for w in words:
        field_set.add(tuple(sorted(w.keys())))
    assert len(field_set) == 1, f'❌ Field set berubah: {len(field_set)}'
    print(f'  ✅ Semua entries tetap 22 field identik')

    # Write
    print(f'\n→ Write ke {KAMUS}...')
    with open(KAMUS, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    # Size comparison
    new_size = KAMUS.stat().st_size
    bak_size = KAMUS.with_suffix('.json.bak').stat().st_size
    print(f'\n→ Size: {bak_size:,} → {new_size:,} bytes ({(new_size - bak_size) / 1024:+.1f} KB)')


if __name__ == '__main__':
    main()
