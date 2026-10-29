#!/usr/bin/env python3
"""AI-driven SRT cleaning — S1 Lima Tentara.

Process: baca SRT Indonesia (GT) + Mandarin (source), perbaiki per cue.
Batches 1-6: cues 1-300. Timestamps/structure preserved EXACTLY.

FIX (v2): bug offset di batch 2-4 lalu — keys 51-100 sebenarnya clean cues 101-150,
keys 101-150 sebenarnya clean cues 201-250, keys 151-200 sebenarnya clean cues 251-300.
Fixed: shift keys, add new cleanings untuk cues 51-100 dan 151-200.
"""
import re
from pathlib import Path

# === Cleaned text per cue ===
CLEAN_TEXT = {
    # === cues 1-50 (batch 1, original correct) ===
    1: "Kapten, Kapten, Tuan Magong, Saudara Chuan, kalian di mana?",
    2: "Jangan ribut, aku belum mati. Tetap waspada.",
    3: "Wang Haochuan, bagaimana kamu menyetir mobil itu?",
    4: "Kapten, aku tidak asal-asalan.",
    5: "Baru saja di depan",
    6: "Bukan lubang, tapi tiba-tiba ambles di tengah",
    7: "Mobil seluruhnya tersedot dengan kuat",
    8: "Aku cengkeram setir erat-erat, tetap tidak bisa",
    9: "Setirnya melayang sendiri",
    10: "Aku tidak kuat lagi",
    11: "Aku tidak ngerti aksen Mandarin Kanton Lei Xu",
    12: "Maaf, Kapten, aku gampang ngomong dialek begitu nggak fokus",
    13: "Kenapa kamu terlihat lebih muda dariku?",
    14: "Apa-apaan ini?",
    15: "Apa ini? Aku kena hantu ya?",
    16: "Jangan, kayak kemasukan setan",
    17: "Cari orang dulu. Ma Zhenbang dan Chen Su belum keluar",
    18: "Kok teriak? Hentikan teriakmu. Stop",
    19: "Tulang tuaku rasanya kembali muda",
    20: "Kenapa Chen Su belum keluar?",
    21: "Tadi mobil terguling keras sekali",
    22: "Chen Su tidur di tengah kursi belakang",
    23: "Terdadak di dalam",
    24: "Cepat",
    25: "Chen Su baik-baik saja? Dia pingsan?",
    26: "Kak, Dr. Chen",
    27: "Kita bisa menolong dengan tangan kosong",
    28: "Chen Su yang kalau memarahi orang, laki-laki kapok",
    29: "Kapten Lin, dia salah naik mobil?",
    30: "Sepertinya masih tidur",
    31: "Dr. Chen, jangan teriak. Kita semua satu tim",
    32: "Apalagi kamu",
    33: "Sekarang kita lagi bermimpi semua",
    34: "Cepatlah biasakan diri",
    35: "Lihat, aku Xie Changfeng",
    36: "Ini Kapten Lin, Tuan Ma, Saudara Chuan",
    37: "Nemo",
    38: "Pakai bahasa Mandarin",
    39: "Cek apakah aku lagi bermimpi",
    40: "Diam. Sekarang bukan waktunya bahas perubahan",
    41: "Faktanya sekarang,",
    42: "Kita tiba di tempat aneh",
    43: "Entah di mana ini",
    44: "Entah kita jadi apa",
    45: "Situasi sekarang mungkin bahaya",
    46: "Mobil terguling, sekitar tidak jelas",
    47: "Semua, segera siaga tempur",
    48: "Cek apakah kalian cedera",
    49: "Lalu cek peralatan",
    50: "Luka kamu sudah dibalut dan sembuh",

    # === cues 51-100 (NEW: cleaning of cues 51-100) ===
    51: "GPS nggak dapat sinyal satelit",
    52: "HP satelit Beidou nggak ada sinyal",
    53: "Bahkan di daerah pegunungan dataran tinggi",
    54: "Nggak mungkin semua tempat terpencil nggak ada sinyal",
    55: "Kayaknya ada yang mengambil alih tempat ini",
    56: "Dikeluarkan dari jaringan komunikasi",
    57: "Nggak usah diomong lagi",
    58: "Bawa semua barang dan perbekalan",
    59: "Ambil kunci mobil",
    60: "Tutup mobil militer pakai dahan pohon",
    61: "Kita harus cepat pergi dari sini",
    62: "Bagaimana tempat ini aneh banget?",
    63: "Kapten, mau dengar yang agak ngawur?",
    64: "Bicara",
    65: "Begini Kapten,",
    66: "Setelah aku amati dengan saksama",
    67: "Buat penilaian saksama",
    68: "Setelah pertimbangan matang",
    69: "Aku rasa",
    70: "Kamu kurangi nonton yang nggak penting",
    71: "Aku nggak ngomong sembarangan",
    72: "Lihat kita sekarang begini",
    73: "Harusnya mobil kita terguling",
    74: "Bahkan umur juga ikut balik",
    75: "Ini namanya terbang waktu",
    76: "Kamu panggil aku Congsheng",
    77: "Congsheng ke aku 10 tahun lalu",
    78: "Yang lain nggak usah",
    79: "Cuma di kepala aja udah worth it",
    80: "Berarti kamu harus jaga baik-baik",
    81: "Bisa jadi dua hari lagi rontok lagi",
    82: "Wang Haochuan, kamu bisa ngomong nggak?",
    83: "Kalau beneran time travel, nggak rugi juga",
    84: "Paling nggak kita jadi muda lagi",
    85: "Nggak lihat. Nggak lihat apa-apa.",
    86: "Maksudku,",
    87: "Intinya kita harus tahu kita time travel ke mana",
    88: "Xie Changfeng",
    89: "Awasi depan",
    90: "Diam",
    91: "Bocah ini kayak udah ngatur penyergapan.",
    92: "Kamu masih ketawa",
    93: "Coba biarkan benda ini meledak di depan muka kamu",
    94: "Bocah penembak jitu",
    95: "Kamu tadi,",
    96: "Hampir mati ketakutan kayak ayam",
    97: "Itu siaga taktis",
    98: "Waspada taktis",
    99: "Di sini pengalaman",
    100: "Jalan",

    # === cues 101-150 (SHIFTED from old keys 51-100; cleaning of cues 101-150) ===
    101: "Masih ada yang lain",
    102: "Binatangnya lebih dari satu jenis",
    103: "Tempat ini kebun binatang",
    104: "Tempat ini kawasan lindung, kan?",
    105: "Kenapa makhluk hidupnya banyak begini?",
    106: "Tidak ada orang",
    107: "Sepertinya aku belum pernah ke sini",
    108: "Tempat ini kelihatannya nggak jauh dari kita",
    109: "Tapi kelihatannya sudah lama meninggalkan kita",
    110: "Filsuf",
    111: "Terus jalan",
    112: "Di mana bajak lautnya?",
    113: "Urusan Mozis",
    114: "Aku cuma nanya",
    115: "Jujur nggak sampai dua detik",
    116: "Kamu sekarang masih di bawah umur?",
    117: "Sudah dewasa, kan?",
    118: "Nggak takut orang",
    119: "Bersembunyi",
    120: "Jangan panah",
    121: "Kita nggak akan melukainya",
    122: "Kalian jangan gugup",
    123: "Kita nggak ada niat jahat",
    124: "Cuma tersesat",
    125: "Lepaskan putriku",
    126: "Kita lepaskan dia",
    127: "Kalian turunkan panah",
    128: "Semua, jangan bertindak",
    129: "Changfeng",
    130: "Lepaskan dia",
    131: "Gadis kecil",
    132: "Kelincimu",
    133: "Sekarang",
    134: "Bisa ngomong sekarang",
    135: "Para pendekar",
    136: "Dari mana asalmu?",
    137: "Bagaimana kalian begini?",
    138: "Bang",
    139: "Bang",
    140: "Aku tanya dulu",
    141: "Tempat apa ini?",
    142: "Ini Longshan",
    143: "Wilayah Qinzhou",
    144: "Kenapa?",
    145: "Belum pernah dengar Qinzhou?",
    146: "Kalian bukan orang Dinasti Song?",
    147: "Bagaimana?",
    148: "Aku bilang apa tadi?",
    149: "Time travel",
    150: "Boleh kutanya,",

    # === cues 151-200 (NEW: cleaning of cues 151-200) ===
    151: "Tahun berapa sekarang?",
    152: "Tahun ke-4 Xuanhe",
    153: "Tahun ke-4",
    154: "Semuanya cocok",
    155: "Tahun 1122 M",
    156: "Ini wilayah Qinfeng",
    157: "Pasti wilayah Qintu",
    158: "Termasuk wilayah Jinglue",
    159: "Prefektur Qinzhou",
    160: "Betul",
    161: "Tempat ini memang wilayah Qinfeng",
    162: "Utusannya adalah Zhongshangong",
    163: "Sekaligus di Qinzhou",
    164: "Bang",
    165: "Sejujurnya",
    166: "Kita bukan orang sini",
    167: "Dari tempat sangat jauh",
    168: "Di jalan ada kejadian",
    169: "Tak sengaja masuk gunung ini",
    170: "Namaku Lin Zhao",
    171: "Yang ini,",
    172: "Semua temanku",
    173: "Xie Changfeng",
    174: "Wang Haochuan",
    175: "Ma Zhenbang",
    176: "Chen Su",
    177: "Namaku Xu",
    178: "Nama Sanhuai",
    179: "Ini putriku",
    180: "Xu Qinghe",
    181: "Itu muridku",
    182: "Li Er",
    183: "Beneran ada yang hangat",
    184: "Kalau kata Bang tadi,",
    185: "Sekarang tahun ke-4 Xuanhe",
    186: "Berarti sekarang",
    187: "Urusan kirim pasukan ke Liao lagi mendesak, kan?",
    188: "Pasukan Qinzhou",
    189: "Sebagian besar sudah ditarik ke utara",
    190: "Bareng pasukan Liao",
    191: "Kalau barat dengar kabar,",
    192: "Barat mungkin jadi berniat masuk",
    193: "Kamu paham banyak",
    194: "Sekarang baru bulan Mei",
    195: "Belum giliran mereka",
    196: "Waktu mereka keluar merampok",
    197: "Desa Qinghe kami",
    198: "Nggak jauh dari benteng Longcheng",
    199: "Kalau beneran ketemu",
    200: "Jejak penyerang barat",

    # === cues 201-250 (SHIFTED from old keys 101-150; cleaning of cues 201-250) ===
    201: "Ada suar sebagai tanda",
    202: "Tidak sampai",
    203: "Tidak sampai tanpa pertahanan",
    204: "Desa Qinghe",
    205: "Desanya nggak kecil",
    206: "Totalnya 66 kepala keluarga",
    207: "Orang Han dan Qiang sama-sama tinggal",
    208: "Sebelah timur desa kebanyakan orang Han",
    209: "Yang dekat lereng sebelah barat",
    210: "Ada orang Qiang",
    211: "Li Er adalah orang Qiang",
    212: "Belajar strategi denganku beberapa tahun",
    213: "Sekarang seperti anakku sendiri",
    214: "Pantas Kapten jadi ahli komando",
    215: "Pinter banget",
    216: "Tadi nggak cedera, kan?",
    217: "Hampir celaka",
    218: "Sudah sore nih",
    219: "Jam segini",
    220: "Di jalan gampang ketemu harimau",
    221: "Kalau mau turun gunung,",
    222: "Lebih baik cepat berangkat",
    223: "Diam. Lebih rendah",
    224: "Lebih cepat dari harimau",
    225: "Nggak ada yang perlu ditakuti",
    226: "Saudara Lin",
    227: "Senjatamu",
    228: "Itu Lei Xiang Nu?",
    229: "Semacam senjata api pertahanan diri",
    230: "Kenapa nggak diperiksa?",
    231: "Mekanismenya beda",
    232: "Nggak perlu diperiksa seperti biasa",
    233: "Ini di tempat kami",
    234: "Hukuman minimal tiga tahun",
    235: "Macan tutul ini untukmu",
    236: "Aduh, nggak enak nerima ini",
    237: "Kamu yang bunuh binatang ini",
    238: "Ini nggak berguna buat kami",
    239: "Anggap saja hadiah tamu menginap",
    240: "Saudara Lin",
    241: "Hatimu ini",
    242: "Xu catat di hati",
    243: "Di depan ada kuil dewa gunung",
    244: "Malam ini kita istirahat di sana",
    245: "Mereka orang Xixia atau Liao?",
    246: "Bukan keduanya",
    247: "Kita dari tempat yang jauh",
    248: "Lagipula bukan hantu gunung",
    249: "Di sana ada api suar",
    250: "Target",

    # === cues 251-300 (SHIFTED from old keys 151-200; cleaning of cues 251-300) ===
    251: "Pembunuhan tanpa pandang bulu",
    252: "Perintah eliminasi",
    253: "Konfirmasi",
    254: "Saudara-saudara",
    255: "Desanya terbakar semua",
    256: "Jadi jangan asal terjun",
    257: "Ngomong sambil jalan, jangan berhenti",
    258: "Berapa jalan masuk-keluar desa?",
    259: "Dua",
    260: "Pintu utama masuk desa",
    261: "Ikuti jalan gunung turun",
    262: "Belakang ada jalan tanah",
    263: "Memutar keluar dari desa,",
    264: "Belakang arah ke mana?",
    265: "Arah ke benteng Longcheng",
    266: "Jalan ke sana sempit",
    267: "Biasanya sepi",
    268: "Tapi kuda bisa lewat",
    269: "Nggak usah jaga pintu belakang",
    270: "Pegang pintu depan saja",
    271: "Kamu mau...",
    272: "Penyerang ini cari cepat",
    273: "Pintu belakang ke kem militer",
    274: "Mereka nggak berani lewat sana",
    275: "Jalan melarikan diri ya pintu utama",
    276: "Kita jebak mereka di desa",
    277: "Semua, perhatian!",
    278: "Chen Su",
    279: "Kamu bawa Qinghe",
    280: "Ikut Saudara Xu jaga belakang",
    281: "Jangan masuk pusat desa dulu",
    282: "Jangan masuk pusat desa dulu",
    283: "Tenangkan warga",
    284: "Jaga pintu desa",
    285: "Siapa yang lari keluar dari pintu desa,",
    286: "Periksa dulu apakah warga desa",
    287: "Atau penyerang",
    288: "Warga yang cedera",
    289: "Kamu rawat dulu",
    290: "Mengerti",
    291: "Li Er",
    292: "Pakai panah awasi pintu desa",
    293: "Penyerang yang lari keluar,",
    294: "Tembak langsung",
    295: "Baik",
    296: "Changfeng, Lao Ma",
    297: "Awasi atap dan lorong dua sisi",
    298: "Cari posisi serang dan bertahan dulu",
    299: "Ya",
    300: "Haochuan",

    # === cues 301-350 (batch 7) ===
    301: "Beri aku pistol",
    302: "Kamu menghadap aku",
    303: "Tembak peluru tali burst singkat",
    304: "Jangan tembak kudanya",
    305: "Setelah mulai,",
    306: "Tiga kata paling penting:",
    307: "Aku, kamu, kuda",
    308: "Saudara Xu",
    309: "Kalian tunggu sebentar",
    310: "Barang itu",
    311: "Mahal loh",
    312: "Perang sekomplit ini",
    313: "Aku 8 keturunan nggak pernah perang kayak gini",
    314: "Diam dong, bisa mati kalau ngomong terus",
    315: "Saudara Li",
    316: "Nggak bisa masuk",
    317: "Penyerang serang cepat, kuda cepat",
    318: "Kalau kelihatan, nyawa taruhan",
    319: "Kalian segelintir ini",
    320: "Masuk pun nggak bisa lari",
    321: "Kita nggak lari",
    322: "Merekalah yang harusnya lari",
    323: "Jangan gerak",
    324: "Miring kiri-kanan",
    325: "Bantuan datang!",
    326: "Udah tenang?",
    327: "Wulixun",
    328: "Panah terbang Lei Xiang Nu",
    329: "Buat kavaleri yang ngejar",
    330: "Kepala orang",
    331: "Kepala kuda ikut meledak",
    332: "Udah kena semua",
    333: "Buat apa tembak lagi",
    334: "Buang peluru",
    335: "Nggak aku tembak lagi, dia bakal jatuh",
    336: "Diam",
    337: "Kiri masih ada satu",
    338: "Satu lari",
    339: "Yang bisa berdiri, mundur",
    340: "Jangan berdiri di jalan",
    341: "Mundur, semua mundur",
    342: "Laki-laki ambil senjata, jangan ribut",
    343: "Kebajikan",
    344: "Zhou Lizheng",
    345: "Aduh, jangan begitu",
    346: "Boleh-boleh saja",
    347: "Mana nggak boleh",
    348: "Kalau bukan karena Bapak baik,",
    349: "Desa Qinghe kami berakhir",
    350: "Tua muda wanita anak-anak",
}


def parse_srt(text):
    text = text.replace('\r\n', '\n').replace('\r', '\n')
    blocks = re.split(r'\n\s*\n', text.strip())
    cues = []
    for block in blocks:
        block = block.strip()
        if not block:
            continue
        lines = block.split('\n')
        ts = re.search(r'(\d{2}:\d{2}:\d{2}[,.]\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2}[,.]\d{3})', '\n'.join(lines))
        if not ts:
            continue
        text_start = False
        text_lines = []
        for line in lines:
            if '-->' in line:
                text_start = True
                continue
            if text_start:
                text_lines.append(line)
        cues.append({
            'index': len(cues) + 1,
            'start': ts.group(1),
            'end': ts.group(2),
            'text': '\n'.join(text_lines).strip(),
        })
    return cues


def main():
    id_path = '/home/z/my-project/upload/folder/28d69ed4/S1 Lima Tentara.id.srt'
    out_path = '/home/z/my-project/clean-srt/S1_Lima_Tentara.id.clean.srt'

    id_text = Path(id_path).read_text(encoding='utf-8-sig')
    cues = parse_srt(id_text)
    print(f"Total cues: {len(cues)}")
    print(f"Cleaned so far: {len(CLEAN_TEXT)}")

    output_lines = []
    changes = 0
    for cue in cues:
        idx = cue['index']
        if idx in CLEAN_TEXT:
            new_text = CLEAN_TEXT[idx]
            if new_text != cue['text']:
                changes += 1
        else:
            new_text = cue['text']
        output_lines.append(str(idx))
        output_lines.append(f"{cue['start']} --> {cue['end']}")
        output_lines.append(new_text)
        output_lines.append('')

    Path(out_path).write_text('\n'.join(output_lines), encoding='utf-8')
    print(f"Total changes applied: {changes}")

    clean_cues = parse_srt(Path(out_path).read_text(encoding='utf-8'))
    assert len(clean_cues) == len(cues), "CUE COUNT MISMATCH"
    ts_mismatch = sum(1 for o, c in zip(cues, clean_cues)
                      if o['start'] != c['start'] or o['end'] != c['end'])
    print(f"Timestamp mismatch: {ts_mismatch} (must be 0)")
    print(f"✅ Validation passed" if ts_mismatch == 0 else "❌ FAILED")


if __name__ == '__main__':
    main()
