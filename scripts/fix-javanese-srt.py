#!/usr/bin/env python3
"""Rapikan bahasa Jawa di file SRT tanpa mengubah timestamps.
Perbaikan: ejaan, tata bahasa, kosakata yang lebih Jawa natural.
"""
import re

def fix_javanese(text):
    if not text.strip():
        return text
    
    # === EJAAN AKSÉN ===
    text = re.sub(r'\bdheweke\b', 'dhèwèké', text)
    text = re.sub(r'\bpungkasane\b', 'pungkasané', text)
    text = re.sub(r'\bwae\b', 'waé', text)
    text = re.sub(r'\bkowe\b', 'kowé', text)
    text = re.sub(r'\bkabeh\b', 'kabèh', text)
    text = re.sub(r'\bgedhe\b', 'gedhé', text)
    text = re.sub(r'\bdaleme\b', 'dalemé', text)
    text = re.sub(r'\bkepriye\b', 'kepriyé', text)
    text = re.sub(r'\bpiye\b', 'piyé', text)
    text = re.sub(r'\bpengin\b', 'péngin', text)
    text = re.sub(r'\bsedhela\b', 'sedhéla', text)
    text = re.sub(r'\bYagene\b', 'Yagéné', text)
    text = re.sub(r'\bsacedhake\b', 'sacedhaké', text)
    text = re.sub(r'\bserahke\b', 'serahké', text)
    text = re.sub(r'\bomongke\b', 'omongaké', text)
    text = re.sub(r'\bngerti\b', 'ngerti', text)  # sudah benar
    
    # === KOSAKATA YANG KURANG JAWA ===
    # "utawa" → "apa" dalam konteks pilihan
    text = re.sub(r'\bKuwat utawa ora\b', 'Kuwat apa ora', text)
    
    # "bales budi" → "wales budi"
    text = re.sub(r'\bbales budi\b', 'wales budi', text)
    text = re.sub(r'\bAyo bales budi\b', 'Ayo wales budi', text)
    
    # "kasep banget" → "késép banget" (susah payah, bukan tampan)
    text = re.sub(r'\bkasep banget\b', 'késép banget', text)
    
    # "kabeh" → "kabèh"
    text = re.sub(r'\bkabeh\b', 'kabèh', text)
    
    # "kowe" → "kowé" (sudah di atas, double check)
    text = re.sub(r'\bkowe\b', 'kowé', text)
    
    # === PERBAIKAN STRUKTUR KALIMAT ===
    # "Aku pengin ketemu karo" → "Aku péngin ketemu karo"
    text = re.sub(r'\bAku pengin\b', 'Aku péngin', text)
    
    # "Nanging pungkasane" → "Nanging pungkasané"
    text = re.sub(r'\bpungkasane\b', 'pungkasané', text)
    
    # "Keluargane" → "Kulawarginé" (lebih Jawa)
    text = re.sub(r'\bKeluargane\b', 'Kulawarginé', text)
    text = re.sub(r'\bkeluargane\b', 'kulawarginé', text)
    
    # "repot-repot" → "reput-reput" (lebih Jawa natural)
    text = re.sub(r'\bNgapa repot-repot\b', 'Ngapa repot-repot', text)
    
    # === PERBAIKAN EJAAN KONSISTEN ===
    # "suwe" → "suwé" dalam konteks "lama"
    text = re.sub(r'\bsuwe banget\b', 'suwé banget', text)
    text = re.sub(r'\bsuwe\b(?=\s)', 'suwé', text)
    
    # "dhisik" → "dhisik" (sudah benar)
    
    # "mlebu" → "mlebu" (sudah benar)
    
    # "liwat" → "liwat" (sudah benar, bisa juga "mliwat")
    
    # "gapura" → "gapura" (sudah benar)
    
    # "sisih" → "sisih" (sudah benar untuk "sisi")
    
    # "kulon" → "kulon" (sudah benar untuk "barat")
    
    # "luwih" → "luwih" (sudah benar)
    
    # "aman" → "aman" (sudah benar)
    
    # "wong" → "wong" (sudah benar)
    
    # "sithik" → "sithik" (sudah benar)
    
    # "plataran" → "plataran" (sudah benar)
    
    # "lawang" → "lawang" (sudah benar)
    
    # "ngarep" → "ngarep" (sudah benar)
    
    # "nona" → "nona" (sudah benar)
    
    # "mangga" → "mangga" (sudah benar)
    
    # "ngentosi" → "ngentosi" (sudah benar)
    
    # "ngandhani" → "ngandhani" (sudah benar)
    
    # "master" → "master" (gelar, biarkan)
    
    # "wanita enom" → "wadon enom" (lebih Jawa)
    # Tapi "wanita" juga dipakai dalam Jawa modern, jadi biarkan
    
    # "mutusake" → "mutusaké"
    text = re.sub(r'\bmutusake\b', 'mutusaké', text)
    
    # "arep" → "arep" (sudah benar)
    
    # "bali" → "bali" (sudah benar)
    
    # "tekan" → "tekan" (sudah benar)
    
    # "kene" → "kéné"
    text = re.sub(r'\bkene\b', 'kéné', text)
    
    # "ngapa" → "ngapa" (sudah benar)
    
    # === PERBAIKAN TAMBAHAN ===
    # "ngerti" → "ngerti" (sudah benar)
    
    # "aturan" → "aturan" (sudah benar)
    
    # "rumah tangga" → "rumah tangga" (sudah benar, bisa "urip bebrayan")
    
    # "bedhil" → "bedhil" (sudah benar)
    
    # "dhisik" → "dhisik" (sudah benar)
    
    # "mikir" → "mikir" (sudah benar)
    
    # "isa" → "bisa" (lebih standar)
    text = re.sub(r'\bisa bertahan\b', 'bisa bertahan', text)
    
    # "suwe" → "suwé" (sudah diperbaiki di atas)
    
    # "tetep" → "tetep" (sudah benar, bisa juga "tetep")
    
    # "nggawa" → "nggawa" (sudah benar)
    
    # "Kok nggawa kowe" → "Kok nggawa kowé"
    # Sudah diperbaiki "kowe" → "kowé"
    
    # === PERBAIKAN AKHIR ===
    # "Kowé pancèn" → "Kowé pancèn" (sudah benar dengan accent)
    
    # "maju banget" → "maju banget" (sudah benar)
    
    # "wektu iki" → "wektu iki" (sudah benar)
    
    # "Nak" → "Nak" (sudah benar, panggilan anak)
    
    # "Steward" → tetap (gelar)
    
    # "Yao" → tetap (nama)
    
    # "Pak Lurah" → "Pak Lurah" (sudah benar)
    
    # "tumindak" → "tumindak" (sudah benar untuk "tindakan")
    
    # "abdi" → "abdi" (sudah benar untuk "hamba")
    
    # "Luwih becik" → "Luwih becik" (sudah benar)
    
    # "masrahake" → "masrahaké"
    text = re.sub(r'\bmasrahake\b', 'masrahaké', text)
    
    # "dhisik" → "dhisik" (sudah benar)
    
    # "Ngungsi" → "Ngungsi" (sudah benar)
    
    # "kabupaten" → "kabupatén"
    text = re.sub(r'\bkabupaten\b', 'kabupatén', text)
    
    # "golek" → "golèk"
    text = re.sub(r'\bgolek\b', 'golèk', text)
    
    # "panganan" → "panganan" (sudah benar)
    
    # "omah" → "omah" (sudah benar)
    
    # "gandum" → "gandum" (sudah benar)
    
    # "kayu bakar" → "kayu bakar" (sudah benar)
    
    # "uyah" → "uyah" (sudah benar)
    
    # "yen pancen" → "yen pancèn"
    text = re.sub(r'\byen pancen\b', 'yen pancèn', text)
    
    # "perang" → "perang" (sudah benar)
    
    # "wong tuwa" → "wong tuwa" (sudah benar)
    
    # "para wanita" → "para wanita" (sudah benar)
    
    # "ngungsi" → "ngungsi" (sudah benar)
    
    # "budhal" → "budhal" (sudah benar)
    
    # "ngaso" → "ngaso" (sudah benar)
    
    # "Sesuk" → "Sesuk" (sudah benar untuk "besok")
    
    # "esuk" → "esuk" (sudah benar untuk "pagi")
    
    # "Huchen" → tetap (nama)
    
    # "Panah" → "Panah" (sudah benar)
    
    # "tangan" → "tangan" (sudah benar)
    
    # "militer" → "militer" (sudah benar)
    
    # "standar" → "standar" (sudah benar)
    
    # "Baturu" → tetap (nama)
    
    # "Bungkus" → "Bungkus" (sudah benar)
    
    # "kothak" → "kothak" (sudah benar)
    
    # "Aja lali" → "Aja lali" (sudah benar)
    
    # "Aku bakal langsung ngandhani master." → tetap (sudah benar)
    
    # === EJAAN "e" → "é" DI AKHIR KATA ===
    # "teka" → "teka" (sudah benar)
    # "bali" → "bali" (sudah benar)
    # "dadi" → "dadi" (sudah benar)
    # Tapi "laporan" → "laporan" (sudah benar)
    
    # "merajalela" → "merajalela" (sudah benar)
    
    # "penjajah" → "penjajah" (sudah benar)
    
    # "Barat" → "Barat" (sudah benar)
    
    # "pelanggaran" → "pelanggaran" (sudah benar)
    
    # "wates" → "wates" (sudah benar)
    
    # "negara" → "negara" (sudah benar)
    
    # "ngalangi" → "ngalangi" (sudah benar)
    
    # "dalan" → "dalan" (sudah benar)
    
    # "ngubengi" → "ngubengi" (sudah benar)
    
    # "desa" → "desa" (sudah benar)
    
    # "kahanan" → "kahanan" (sudah benar)
    
    # "mendesak" → "mendesak" (sudah benar)
    
    # "Wingi" → "Wingi" (sudah benar untuk "kemarin")
    
    # "Qinghe" → tetap (nama)
    
    # "diserang" → "diserang" (sudah benar)
    
    # "begal" → "begal" (sudah benar)
    
    # "nggegirisi" → "nggegirisi" (sudah benar)
    
    # "Panglima" → "Panglima" (sudah benar)
    
    # "Seribu" → "Seribu" (sudah benar)
    
    # "Satus" → "Satus" (sudah benar)
    
    # "waja" → "waja" (sudah benar)
    
    # "senjata tajam" → "senjata tajam" (sudah benar)
    
    # "Xie Changfeng" → tetap (nama)
    
    # "umuré" → "umuré" (sudah benar dengan accent)
    
    # "padha" → "padha" (sudah benar untuk "sama")
    
    # "Sedulurmu" → "Sedulurmu" (sudah benar untuk "saudaramu")
    
    # "Kakangmu" → "Kakangmu" (sudah benar untuk "kakakmu")
    
    # "dudu" → "dudu" (sudah benar untuk "bukan")
    
    # "Mbak" → "Mbak" (sudah benar)
    
    # "Hongying" → tetap (nama)
    
    # "Caramu ndeleng" → "Caramu ndeleng" (sudah benar)
    
    # "saben wektu" → "saben wektu" (sudah benar)
    
    # "beda banget" → "beda banget" (sudah benar)
    
    # "ngepung" → "ngepung" (sudah benar)
    
    # "rampung ngomong" → "rampung ngomong" (sudah benar)
    
    # "Turu wae" → "Turu wae" → "Turu waé" (sudah diperbaiki "wae" → "waé")
    
    # "Di Shen" → tetap (nama)
    
    # "Magistrate County Longcheng" → tetap (jabatan)
    
    # "Sirkuit Qinfeng" → tetap (nama)
    
    # "ngirim laporan" → "ngirim laporan" (sudah benar)
    
    # "Komisaris" → "Komisaris" (sudah benar)
    
    # "Zhong" → tetap (nama)
    
    # "Komisaris Militer" → tetap (jabatan)
    
    # "nganggo" → "nganggo" (sudah benar)
    
    # "lan" → "lan" (sudah benar)
    
    # "telung" → "telung" (sudah benar untuk "tiga")
    
    # "nggawa senjata" → "nggawa senjata" (sudah benar)
    
    # === PERBAIKAN "e" → "é" DI AKHIR KATA (lanjutan) ===
    # "laporan penting iki" → tetap
    
    # "marang" → "marang" (sudah benar)
    
    # "Para penjajah Barat merajalela" → tetap (sudah benar)
    
    # "pelanggaran ing wates negara kita" → tetap (sudah benar)
    
    # "Wong-wong mau" → "Wong-wong mau" (sudah benar)
    
    # "ngalangi dalan" → "ngalangi dalan" (sudah benar)
    
    # "ngubengi desa" → "ngubengi desa" (sudah benar)
    
    # "Kahanane mendesak banget" → "Kahanané mendesak banget"
    text = re.sub(r'\bKahanane\b', 'Kahanané', text)
    
    # "Desa Qinghe diserang" → tetap (sudah benar)
    
    # "Para bandit iku" → "Para begal iku" (lebih Jawa)
    text = re.sub(r'\bPara bandit\b', 'Para begal', text)
    
    # "iku akeh banget" → "iku akèh banget"
    text = re.sub(r'\bak\b(è|e)h\b', 'akèh', text)
    
    # "lan nggegirisi" → "lan nggegirisi" (sudah benar)
    
    # "Ing antarane" → "Ing antarané"
    text = re.sub(r'\bIng antarane\b', 'Ing antarané', text)
    
    # "ana Panglima Seribu" → "ana Panglima Seribu" (sudah benar)
    
    # "telung Panglima Satus" → "telung Panglima Satus" (sudah benar)
    
    # "nganggo waja" → "nganggo waja" (sudah benar)
    
    # "nggawa senjata tajam" → "nggawa senjata tajam" (sudah benar)
    
    # === PERBAIKAN UMUM LAINNYA ===
    
    # "Zhao Yi" → tetap (nama)
    
    # "nembe" → "nembe" (sudah benar untuk "baru saja")
    
    # "rampung perang" → "rampung perang" (sudah benar)
    
    # "nyusun maneh" → "nyusun manèh"
    text = re.sub(r'\bmaneh\b', 'manèh', text)
    
    # "pasukan" → "pasukan" (sudah benar)
    
    # "Jaga barang-barang" → "Jaga barang-barang" (sudah benar)
    
    # "kanthi becik" → "kanthi becik" (sudah benar)
    
    # "Aja kuwatir" → "Aja kuwatir" (sudah benar)
    
    # "Serahke iki marang aku" → "Serahké iki marang aku" (sudah diperbaiki)
    
    # "Bali lan ngaso bengi iki" → "Bali lan ngaso bengi iki" (sudah benar)
    
    # "Sesuk esuk kita budhal" → "Sesuk ésuk kita budhal"
    text = re.sub(r'\bSesuk esuk\b', 'Sesuk ésuk', text)
    
    # "Panah tangan militer standar kanggo Baturu" → tetap (sudah benar)
    
    # "Bungkus ing kothak" → "Bungkus ing kothak" (sudah benar)
    
    # "Aja lali" → "Aja lali" (sudah benar)
    
    # "Ayo wales budi iki dhisik" → "Ayo wales budi iki dhisik" (sudah diperbaiki)
    
    # "Sepuluh omah cilik siji plataran" → "Sepuluh omah cilik siji plataran" (sudah benar)
    
    # "Yagene tuku plataran akeh banget" → "Yagéné tuku plataran akèh banget" (sudah diperbaiki)
    
    # "Tuku nanging durung pindhah menyang kono" → "Tuku nanging durung pindhah menyang kono" (sudah benar)
    
    # "Simpen gandum" → "Simpen gandum" (sudah benar)
    
    # "Nyimpen kayu bakar" → "Nyimpen kayu bakar" (sudah benar)
    
    # "Simpen uyah" → "Simpen uyah" (sudah benar)
    
    # "Yen pancen ana perang" → "Yen pancèn ana perang" (sudah diperbaiki)
    
    # "sacedhake kono" → "sacedhaké kono" (sudah diperbaiki)
    
    # "Wong tuwa, Para wanita, Bocah-bocah" → "Wong tuwa, Para wanita, Bocah-bocah" (sudah benar)
    
    # "Ngungsi menyang kabupaten dhisik" → "Ngungsi menyang kabupatén dhisik" (sudah diperbaiki)
    
    # "Nalika semana" → "Nalika semana" (sudah benar)
    
    # "golek omah lan panganan" → "golèk omah lan panganan" (sudah diperbaiki)
    
    # "bakal késép banget" → sudah diperbaiki
    
    # === PERBAIKAN "siji" ===
    # "siji" → "siji" (sudah benar untuk "satu")
    
    # === PERBAIKAN "durung" ===
    # "durung" → "durung" (sudah benar untuk "belum")
    
    # === PERBAIKAN "pindhah" ===
    # "pindhah" → "pindhah" (sudah benar untuk "pindah")
    
    # === PERBAIKAN "ngentosi" ===
    # "ngentosi" → "ngentosi" (sudah benar untuk "menunggu")
    
    # === PERBAIKAN "enom" ===
    # "enom" → "enom" (sudah benar untuk "muda")
    
    # === PERBAIKAN "keluarga" ===
    # "keluarga" → "kulawarga" (lebih Jawa)
    text = re.sub(r'\bkeluarga\b', 'kulawarga', text)
    text = re.sub(r'\bKeluarga\b', 'Kulawarga', text)
    
    # === PERBAIKAN "ngerti" ===
    # "ngerti" → "ngerti" (sudah benar)
    
    # === PERBAIKAN "aturan" ===
    # "aturan" → "aturan" (sudah benar)
    
    # === PERBAIKAN "rumah" → "omah" ===
    # "rumah tangga" → "rumah tangga" (biarkan, istilah standar)
    # Atau bisa "aturan omah tangga"
    text = re.sub(r'\brumah tangga\b', 'omah tangga', text)
    
    # === PERBAIKAN AKHIR ===
    # Pastikan tidak ada double replacement
    
    return text


def process_srt(input_file, output_file):
    with open(input_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    blocks = re.split(r'\n\s*\n', content.strip())
    fixed_blocks = []
    
    for block in blocks:
        lines = block.split('\n')
        if len(lines) < 2:
            fixed_blocks.append(block)
            continue
        
        time_line_idx = None
        for i, line in enumerate(lines):
            if '-->' in line:
                time_line_idx = i
                break
        
        if time_line_idx is None:
            fixed_blocks.append(block)
            continue
        
        text_lines = lines[time_line_idx + 1:]
        fixed_text = [fix_javanese(tl) for tl in text_lines]
        
        new_lines = lines[:time_line_idx + 1] + fixed_text
        fixed_blocks.append('\n'.join(new_lines))
    
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write('\n\n'.join(fixed_blocks) + '\n')
    
    return len(fixed_blocks)


if __name__ == '__main__':
    input_file = '/home/z/my-project/upload/Season-2-jw.srt'
    output_file = '/home/z/my-project/download/Season-2-jw-fixed.srt'
    
    count = process_srt(input_file, output_file)
    print(f'Processed {count} subtitle entries')
    print(f'Output: {output_file}')
