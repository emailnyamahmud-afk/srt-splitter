#!/usr/bin/env python3
"""Rapikan bahasa Jawa di semua SRT season tanpa mengubah timestamps."""
import re, sys

def fix_javanese(text):
    if not text.strip():
        return text
    
    # Hapus "(or)" pattern di Season 1
    text = re.sub(r'\s*\(or\)\s*', ' ', text)
    text = re.sub(r'\s+!', '!', text)
    text = re.sub(r'^[A-Za-z]+!\s+[A-Za-z]+!\s*$', lambda m: m.group(0).split('!')[0].strip() + '!', text)
    
    # Ejaan aksén
    fixes = [
        (r'\bdheweke\b', 'dhèwèké'),
        (r'\bkowe\b', 'kowé'),
        (r'\bkabeh\b', 'kabèh'),
        (r'\bmaneh\b', 'manèh'),
        (r'\bwae\b', 'waé'),
        (r'\bpungkasane\b', 'pungkasané'),
        (r'\bgedhe\b', 'gedhé'),
        (r'\bpengin\b', 'péngin'),
        (r'\bsedhela\b', 'sedhéla'),
        (r'\bkene\b', 'kéné'),
        (r'\bYagene\b', 'Yagéné'),
        (r'\bsacedhake\b', 'sacedhaké'),
        (r'\bserahke\b', 'serahké'),
        (r'\bomongke\b', 'omongaké'),
        (r'\bmutusake\b', 'mutusaké'),
        (r'\bmasrahake\b', 'masrahaké'),
        (r'\bkabupaten\b', 'kabupatén'),
        (r'\bgolek\b', 'golèk'),
        (r'\bkeluarga\b', 'kulawarga'),
        (r'\bKeluarga\b', 'Kulawarga'),
        (r'\brumah tangga\b', 'omah tangga'),
        (r'\bKahanane\b', 'Kahanané'),
        (r'\bPara bandit\b', 'Para begal'),
        (r'\bIng antarane\b', 'Ing antarané'),
        (r'\bkasep banget\b', 'késép banget'),
        (r'\bbales budi\b', 'wales budi'),
        (r'\bdaleme\b', 'dalemé'),
        (r'\bkepriye\b', 'kepriyé'),
        (r'\bpiye\b', 'piyé'),
        (r'\bSesuk esuk\b', 'Sesuk ésuk'),
        (r'\bsuwe\b(?=\s)', 'suwé'),
        (r'\bKuwat utawa ora\b', 'Kuwat apa ora'),
        (r'\bisa bertahan\b', 'bisa bertahan'),
        (r'\bak\b(è|e)h\b', 'akèh'),
        (r'\bdiuncalake\b', 'diuncalaké'),
        (r'\bslametake\b', 'slametaké'),
        (r'\bkedadeyan\b', 'kadadian'),
        (r'\bKepriye\b', 'Kepriyé'),
        (r'\bngilangi\b', 'ngilangi'),
        (r'\bnduweni\b', 'nduwèni'),
        (r'\bnggunakake\b', 'nganggo'),
        (r'\bnggawe\b', 'nggawé'),
        (r'\baku krungu\b', 'aku krungu'),
        (r'\bdipisahake\b', 'dipisahaké'),
        (r'\bnetepi\b', 'netepi'),
        (r'\bmlebu wilayah\b', 'mlebu wilayah'),
        (r'\bewonan\b', 'éwonan'),
        (r'\bmili\b', 'mili'),
        (r'\bnjaba\b', 'njaba'),
        (r'\bkutha\b', 'kutha'),
        (r'\bBisa uga ora\b', 'Bisa uga ora'),
        (r'\bngetokake\b', 'ngetokaké'),
        (r'\bwenihana\b', 'wenihana'),
        (r'\bsaktemene\b', 'satemené'),
        (r'\bWenehana\b', 'Wenèhana'),
        (r'\bnuntut\b', 'nuntut'),
        (r'\bkekuwatan\b', 'kekuwatan'),
        (r'\bsliramu\b', 'sliramu'),
        (r'\bnguji\b', 'nguji'),
        (r'\bpengintai\b', 'pengintai'),
        (r'\bngutus\b', 'ngutus'),
        (r'\bnjaga\b', 'njaga'),
        (r'\bmedeni\b', 'medeni'),
        (r'\bmbenerake\b', 'mbeneraké'),
        (r'\bnganti\b', 'nganti'),
        (r'\bmabuk\b', 'mabuk'),
        (r'\bwareg\b', 'wareg'),
        (r'\bpreduli\b', 'preduli'),
        (r'\bpanah\b', 'panah'),
        (r'\bkrungu\b', 'krungu'),
        (r'\bsethithik\b', 'sithik'),
        (r'\bsangisore\b', 'sangisoré'),
        (r'\bkekuasaan\b', 'kekuasaan'),
        (r'\bbarbar\b', 'barbar'),
        (r'\bDataran\b', 'Dataran'),
        (r'\bTengah\b', 'Tengah'),
        (r'\bTentara\b', 'Tentara'),
        (r'\bKekaisaran\b', 'Kekaisaran'),
        (r'\bwangsulan\b', 'wangsulan'),
        (r'\bMinangka\b', 'Minangka'),
        (r'\bGelar\b', 'Gelar'),
        (r'\bpengawas\b', 'pengawas'),
        (r'\bkudune\b', 'kuduné'),
        (r'\bsadurunge\b', 'sadurungé'),
        (r'\bawan\b', 'awan'),
        (r'\bSedulur\b', 'Sedulur'),
        (r'\blunggah\b', 'lunggah'),
        (r'\bnginep\b', 'nginep'),
        (r'\bsawetara\b', 'sawetara'),
        (r'\bdina\b', 'dina'),
        (r'\bTentang\b', 'Tentang'),
        (r'\bpreduli apa waé\b', 'preduli apa waé'),
    ]
    
    for pattern, replacement in fixes:
        text = re.sub(pattern, replacement, text)
    
    # Bersihkan multiple spaces
    text = re.sub(r'  +', ' ', text)
    text = re.sub(r'^\s+', '', text)
    text = re.sub(r'\s+$', '', text)
    
    return text

def process_srt(input_file, output_file):
    with open(input_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    blocks = re.split(r'\n\s*\n', content.strip())
    fixed_blocks = []
    
    for block in blocks:
        lines = block.split('\n')
        time_idx = None
        for i, line in enumerate(lines):
            if '-->' in line:
                time_idx = i
                break
        
        if time_idx is None:
            fixed_blocks.append(block)
            continue
        
        text_lines = lines[time_idx + 1:]
        fixed_text = [fix_javanese(tl) for tl in text_lines]
        new_lines = lines[:time_idx + 1] + fixed_text
        fixed_blocks.append('\n'.join(new_lines))
    
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write('\n\n'.join(fixed_blocks) + '\n')
    
    return len(fixed_blocks)

# Process semua season
seasons = [
    ('Season-1-jw.srt', 'Season-1-jw-fixed.srt'),
    ('Season-3-jw.srt', 'Season-3-jw-fixed.srt'),
    ('Season-4-jw.srt', 'Season-4-jw-fixed.srt'),
    ('Season-5-jw.srt', 'Season-5-jw-fixed.srt'),
    ('Season-6-jw.srt', 'Season-6-jw-fixed.srt'),
]

for src, dst in seasons:
    input_path = f'/home/z/my-project/upload/{src}'
    output_path = f'/home/z/my-project/download/{dst}'
    
    count = process_srt(input_path, output_path)
    print(f'{src} → {dst}: {count} entries')

print('\nDone!')
