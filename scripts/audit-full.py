#!/usr/bin/env python3
"""Audit penuh kamus-jawa-draft.json — baca SEMUA 44.005 entries, cari pattern parsing tolol.

Tidak sampling. Baca semua. Output: laporan pattern anomaly per field.
"""
import json
from collections import Counter, defaultdict
from pathlib import Path

KAMUS = Path('/home/z/my-project/public/kamus-jawa-draft.json')

with open(KAMUS, 'r', encoding='utf-8') as f:
    data = json.load(f)

words = data['words']
total = len(words)
print(f'Total entries: {total:,}')
print(f'Baca semua entries, audit per field...\n')

# ============ AUDIT PER FIELD ============

# 1. word field — cari yang aneh (empty, contains comma, contains digit, sangat panjang)
print('=== 1. WORD field (NETRAL unassigned) ===')
word_anomalies = {
    'empty': 0,
    'has_comma': 0,           # word seharusnya 1 kata, bukan comma
    'has_digit': 0,           # word angka? mungkin is_angka entry
    'has_paren': 0,           # word dengan () artifact
    'has_curly': 0,           # word dengan {} artifact wiki
    'has_brackets': 0,        # word dengan [] artifact wiki
    'length_gt_30': 0,        # word sangat panjang (bukan 1 kata)
    'has_html': 0,            # word dengan < atau >
    'has_pipe': 0,            # word dengan |
    'has_double_space': 0,
}
for w in words:
    s = (w.get('word') or '').strip()
    if not s:
        word_anomalies['empty'] += 1
    if ',' in s: word_anomalies['has_comma'] += 1
    if any(c.isdigit() for c in s): word_anomalies['has_digit'] += 1
    if '(' in s or ')' in s: word_anomalies['has_paren'] += 1
    if '{' in s or '}' in s: word_anomalies['has_curly'] += 1
    if '[' in s or ']' in s: word_anomalies['has_brackets'] += 1
    if len(s) > 30: word_anomalies['length_gt_30'] += 1
    if '<' in s or '>' in s: word_anomalies['has_html'] += 1
    if '|' in s: word_anomalies['has_pipe'] += 1
    if '  ' in s: word_anomalies['has_double_space'] += 1

for k, v in word_anomalies.items():
    pct = v*100/total
    print(f'  {k:20} {v:>6,} ({pct:.2f}%)')

# 2. ngoko field — cari yang aneh
print('\n=== 2. NGOKO field (Jawa ngoko) ===')
ngoko_anomalies = {
    'empty': 0,
    'has_digit_in_word': 0,    # ngoko dengan angka
    'has_aksara_inside': 0,    # ngoko dengan aksara Jawa (ꦏꦸꦭ dll)
    'has_paren': 0,
    'has_curly': 0,
    'has_brackets': 0,
    'has_html': 0,
    'has_pipe': 0,
    'has_semicolon': 0,        # ; artifact definisi
    'has_period_inside': 0,    # . di tengah kata
    'has_space_comma': 0,      # " ," artifact
    'has_double_comma': 0,
    'length_gt_100': 0,
}
for w in words:
    s = (w.get('ngoko') or '').strip()
    if not s:
        ngoko_anomalies['empty'] += 1
        continue
    if any(c.isdigit() for c in s): ngoko_anomalies['has_digit_in_word'] += 1
    # Aksara Jawa unicode range: A980-A9DF
    if any(0xA980 <= ord(c) <= 0xA9DF for c in s): ngoko_anomalies['has_aksara_inside'] += 1
    if '(' in s or ')' in s: ngoko_anomalies['has_paren'] += 1
    if '{' in s or '}' in s: ngoko_anomalies['has_curly'] += 1
    if '[' in s or ']' in s: ngoko_anomalies['has_brackets'] += 1
    if '<' in s or '>' in s: ngoko_anomalies['has_html'] += 1
    if '|' in s: ngoko_anomalies['has_pipe'] += 1
    if ';' in s: ngoko_anomalies['has_semicolon'] += 1
    if '.,' in s or ',.' in s: ngoko_anomalies['has_period_inside'] += 1
    if ' ,' in s: ngoko_anomalies['has_space_comma'] += 1
    if ',,' in s: ngoko_anomalies['has_double_comma'] += 1
    if len(s) > 100: ngoko_anomalies['length_gt_100'] += 1

for k, v in ngoko_anomalies.items():
    pct = v*100/total
    print(f'  {k:20} {v:>6,} ({pct:.2f}%)')

# 3. krama field — cari yang aneh
print('\n=== 3. KRAMA field (Jawa krama) ===')
krama_anomalies = dict(ngoko_anomalies)  # copy struktur
for k in krama_anomalies: krama_anomalies[k] = 0
for w in words:
    s = (w.get('krama') or '').strip()
    if not s:
        krama_anomalies['empty'] += 1
        continue
    if any(c.isdigit() for c in s): krama_anomalies['has_digit_in_word'] += 1
    if any(0xA980 <= ord(c) <= 0xA9DF for c in s): krama_anomalies['has_aksara_inside'] += 1
    if '(' in s or ')' in s: krama_anomalies['has_paren'] += 1
    if '{' in s or '}' in s: krama_anomalies['has_curly'] += 1
    if '[' in s or ']' in s: krama_anomalies['has_brackets'] += 1
    if '<' in s or '>' in s: krama_anomalies['has_html'] += 1
    if '|' in s: krama_anomalies['has_pipe'] += 1
    if ';' in s: krama_anomalies['has_semicolon'] += 1
    if '.,' in s or ',.' in s: krama_anomalies['has_period_inside'] += 1
    if ' ,' in s: krama_anomalies['has_space_comma'] += 1
    if ',,' in s: krama_anomalies['has_double_comma'] += 1
    if len(s) > 100: krama_anomalies['length_gt_100'] += 1

for k, v in krama_anomalies.items():
    pct = v*100/total
    print(f'  {k:20} {v:>6,} ({pct:.2f}%)')

# 4. arti field — KRITIS, harus Indonesia, bukan Jawa fallback
print('\n=== 4. ARTI field (Indonesia) — KRITIS, harus Indonesia bukan Jawa ===')
arti_anomalies = {
    'empty': 0,
    'equals_word': 0,          # arti = word (fallback tolol)
    'has_curly': 0,            # {{wiki artifact}}
    'has_brackets': 0,         # [[wiki link]]
    'has_html': 0,              # <sup> dll
    'has_paren_word': 0,       # "(kata benda)" definisi ensiklopedis
    'has_pipe': 0,             # | artifact
    'has_semicolon_multi': 0,  # ;>1 (multiple definitions)
    'length_gt_60': 0,          # terlalu panjang = definisi, bukan sinonim
    'length_gt_200': 0,
    'has_digit_word': 0,      # angka
    'has_aksara': 0,
    'has_newline': 0,           # \n artifact
}
arti_eq_word_sample = []
arti_long_sample = []
arti_wiki_sample = []
for w in words:
    s = (w.get('arti') or '').strip()
    word = (w.get('word') or '').strip()
    if not s:
        arti_anomalies['empty'] += 1
        continue
    if s == word and s:
        arti_anomalies['equals_word'] += 1
        if len(arti_eq_word_sample) < 5:
            arti_eq_word_sample.append((w.get('entry_id'), s, w.get('sumber', '')[:50]))
    if '{' in s or '}' in s:
        arti_anomalies['has_curly'] += 1
        if len(arti_wiki_sample) < 5:
            arti_wiki_sample.append((w.get('entry_id'), s[:80]))
    if '[' in s or ']' in s: arti_anomalies['has_brackets'] += 1
    if '<' in s or '>' in s: arti_anomalies['has_html'] += 1
    if '(' in s and ')' in s and any(c.isalpha() for c in s[s.find('('):s.find(')')+1]):
        arti_anomalies['has_paren_word'] += 1
    if '|' in s: arti_anomalies['has_pipe'] += 1
    if s.count(';') > 1: arti_anomalies['has_semicolon_multi'] += 1
    if len(s) > 60:
        arti_anomalies['length_gt_60'] += 1
        if len(arti_long_sample) < 5:
            arti_long_sample.append((w.get('entry_id'), s[:80]))
    if len(s) > 200: arti_anomalies['length_gt_200'] += 1
    if any(c.isdigit() for c in s): arti_anomalies['has_digit_word'] += 1
    if any(0xA980 <= ord(c) <= 0xA9DF for c in s): arti_anomalies['has_aksara'] += 1
    if '\n' in s: arti_anomalies['has_newline'] += 1

for k, v in arti_anomalies.items():
    pct = v*100/total
    print(f'  {k:25} {v:>6,} ({pct:.2f}%)')

print('\n  --- Sample arti=word (fallback tolol) ---')
for eid, s, sumb in arti_eq_word_sample:
    print(f'    entry_id={eid}: arti={s!r} sumber={sumb!r}')

print('\n  --- Sample arti dengan wiki artifact ({) ---')
for eid, s in arti_wiki_sample:
    print(f'    entry_id={eid}: arti={s!r}')

print('\n  --- Sample arti > 60 chars (definisi, bukan sinonim) ---')
for eid, s in arti_long_sample:
    print(f'    entry_id={eid}: arti={s!r}')

# 5. keterangan field
print('\n=== 5. KETERANGAN field (konteks Jawa) ===')
ket_anomalies = {
    'empty': 0,
    'has_curly': 0,
    'has_brackets': 0,
    'has_html': 0,
    'has_pipe': 0,
    'has_newline': 0,
    'has_wiki_template': 0,    # {{...}}
    'has_wiki_link': 0,         # [[...]]
    'has_html_tag': 0,          # <sup>, <br>, etc
    'length_gt_500': 0,
    'length_gt_2000': 0,
}
for w in words:
    s = (w.get('keterangan') or '').strip()
    if not s:
        ket_anomalies['empty'] += 1
        continue
    if '{' in s or '}' in s: ket_anomalies['has_curly'] += 1
    if '[' in s or ']' in s: ket_anomalies['has_brackets'] += 1
    if '<' in s or '>' in s: ket_anomalies['has_html'] += 1
    if '|' in s: ket_anomalies['has_pipe'] += 1
    if '\n' in s: ket_anomalies['has_newline'] += 1
    if '{{' in s and '}}' in s: ket_anomalies['has_wiki_template'] += 1
    if '[[' in s and ']]' in s: ket_anomalies['has_wiki_link'] += 1
    if '<sup>' in s or '<br' in s or '<ref' in s: ket_anomalies['has_html_tag'] += 1
    if len(s) > 500: ket_anomalies['length_gt_500'] += 1
    if len(s) > 2000: ket_anomalies['length_gt_2000'] += 1

for k, v in ket_anomalies.items():
    pct = v*100/total
    print(f'  {k:25} {v:>6,} ({pct:.2f}%)')

# 6. aksara field
print('\n=== 6. AKSARA field (aksara Jawa) ===')
aksara_anomalies = {
    'empty': 0,
    'has_latin': 0,             # ada huruf Latin (A-Z, a-z) di aksara
    'has_digit': 0,
    'has_comma': 0,             # multi aksara
    'length_gt_50': 0,
}
for w in words:
    s = (w.get('aksara') or '').strip()
    if not s:
        aksara_anomalies['empty'] += 1
        continue
    if any(c.isalpha() and ord(c) < 128 for c in s): aksara_anomalies['has_latin'] += 1
    if any(c.isdigit() for c in s): aksara_anomalies['has_digit'] += 1
    if ',' in s: aksara_anomalies['has_comma'] += 1
    if len(s) > 50: aksara_anomalies['length_gt_50'] += 1

for k, v in aksara_anomalies.items():
    pct = v*100/total
    print(f'  {k:20} {v:>6,} ({pct:.2f}%)')

# 7. sumber field
print('\n=== 7. SUMBER field ===')
sumber_anomalies = {
    'empty': 0,
    'has_merge': 0,             # mengandung 'merge'
    'has_lampiran': 0,
    'has_mendeley': 0,
    'has_wiktionary': 0,
    'has_dasanama': 0,
    'has_angka': 0,
    'multi_source': 0,          # ada '+' (multi-source)
}
for w in words:
    s = (w.get('sumber') or '').strip()
    if not s:
        sumber_anomalies['empty'] += 1
        continue
    if 'merge' in s: sumber_anomalies['has_merge'] += 1
    if 'lampiran' in s: sumber_anomalies['has_lampiran'] += 1
    if 'mendeley' in s: sumber_anomalies['has_mendeley'] += 1
    if 'wiktionary' in s: sumber_anomalies['has_wiktionary'] += 1
    if 'dasanama' in s: sumber_anomalies['has_dasanama'] += 1
    if 'angka' in s.lower(): sumber_anomalies['has_angka'] += 1
    if '+' in s: sumber_anomalies['multi_source'] += 1

for k, v in sumber_anomalies.items():
    pct = v*100/total
    print(f'  {k:20} {v:>6,} ({pct:.2f}%)')

# 8. register field
print('\n=== 8. REGISTER field ===')
reg_count = Counter(w.get('register', '') for w in words)
for r, c in reg_count.most_common():
    print(f'  {r!r:25} {c:>6,}')

# 9. kelas field
print('\n=== 9. KELAS field ===')
kelas_count = Counter(w.get('kelas', '') for w in words)
for k, c in kelas_count.most_common(15):
    print(f'  {k!r:25} {c:>6,}')

# 10. krama_inggil — harus kosong by R-17
print('\n=== 10. KRAMA_INGGIL field (R-17: harus kosong) ===')
ki_count = sum(1 for w in words if (w.get('krama_inggil') or '').strip())
print(f'  Terisi: {ki_count} (R-17: harus 0)')

# 11. Status
print('\n=== 11. STATUS field ===')
status_count = Counter(w.get('status', '') for w in words)
for s, c in status_count.most_common():
    print(f'  {s!r:20} {c:>6,}')

# 12. is_* flags
print('\n=== 12. is_* source flags ===')
for flag in ['is_lemma', 'is_mendeley', 'is_dasanama', 'is_angka', 'is_lampiran']:
    count = sum(1 for w in words if w.get(flag))
    print(f'  {flag:20} {count:>6,}')

# 13. lemma_words, mendeley_id, dasanama_count, source_count
print('\n=== 13. Field metadata lain ===')
for f in ['lemma_words', 'mendeley_id', 'dasanama_count', 'source_count']:
    count = sum(1 for w in words if (w.get(f) or '') != '' and w.get(f) not in (0, None, False))
    print(f'  {f:20} {count:>6,} entries terisi')

print('\n=== SUMMARY: pattern parsing tolol ===')
print(f'  arti=word fallback (NETRAL, bukan Indonesia): {arti_anomalies["equals_word"]:,}')
print(f'  arti > 60 char (definisi, bukan sinonim):       {arti_anomalies["length_gt_60"]:,}')
print(f'  arti wiki artifact {{}}:                          {arti_anomalies["has_curly"]:,}')
print(f'  arti wiki link [[]]:                              {arti_anomalies["has_brackets"]:,}')
print(f'  arti HTML <:                                     {arti_anomalies["has_html"]:,}')
print(f'  keterangan wiki template {{{{}}}}:                  {ket_anomalies["has_wiki_template"]:,}')
print(f'  keterangan wiki link [[[]]]:                       {ket_anomalies["has_wiki_link"]:,}')
print(f'  keterangan HTML tag <:                            {ket_anomalies["has_html_tag"]:,}')
print(f'  keterangan > 500 char (terlalu panjang):          {ket_anomalies["length_gt_500"]:,}')
