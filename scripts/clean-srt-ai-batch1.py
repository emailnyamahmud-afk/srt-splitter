#!/usr/bin/env python3
"""AI-driven SRT cleaning — S1 Lima Tentara.

Process: baca SRT Indonesia (GT) + Mandarin (source), perbaiki per cue.
Batch 1-2: cues 1-100. Timestamps/structure preserved EXACTLY.
"""
import re
from pathlib import Path

# === Cleaned text per cue ===
CLEAN_TEXT = {
    # === Batch 1: cues 1-50 ===
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

    # === Batch 2: cues 51-100 ===
    51: "Masih ada yang lain",
    52: "Binatangnya lebih dari satu jenis",
    53: "Tempat ini kebun binatang",
    54: "Tempat ini kawasan lindung, kan?",
    55: "Kenapa makhluk hidupnya banyak begini?",
    56: "Tidak ada orang",
    57: "Sepertinya aku belum pernah ke sini",
    58: "Tempat ini kelihatannya nggak jauh dari kita",
    59: "Tapi kelihatannya sudah lama meninggalkan kita",
    60: "Filsuf",
    61: "Terus jalan",
    62: "Di mana bajak lautnya?",
    63: "Urusan Mozis",
    64: "Aku cuma nanya",
    65: "Jujur nggak sampai dua detik",
    66: "Kamu sekarang masih di bawah umur?",
    67: "Sudah dewasa, kan?",
    68: "Nggak takut orang",
    69: "Bersembunyi",
    70: "Jangan panah",
    71: "Kita nggak akan melukainya",
    72: "Kalian jangan gugup",
    73: "Kita nggak ada niat jahat",
    74: "Cuma tersesat",
    75: "Lepaskan putriku",
    76: "Kita lepaskan dia",
    77: "Kalian turunkan panah",
    78: "Semua, jangan bertindak",
    79: "Changfeng",
    80: "Lepaskan dia",
    81: "Gadis kecil",
    82: "Kelincimu",
    83: "Sekarang",
    84: "Bisa ngomong sekarang",
    85: "Para pendekar",
    86: "Dari mana asalmu?",
    87: "Bagaimana kalian begini?",
    88: "Bang",
    89: "Bang",
    90: "Aku tanya dulu",
    91: "Tempat apa ini?",
    92: "Ini Longshan",
    93: "Wilayah Qinzhou",
    94: "Kenapa?",
    95: "Belum pernah dengar Qinzhou?",
    96: "Kalian bukan orang Dinasti Song?",
    97: "Bagaimana?",
    98: "Aku bilang apa tadi?",
    99: "Time travel",
    100: "Boleh kutanya,",

    # === Batch 3: cues 101-150 ===
    101: "Ada suar sebagai tanda",
    102: "Tidak sampai",
    103: "Tidak sampai tanpa pertahanan",
    104: "Desa Qinghe",
    105: "Desanya nggak kecil",
    106: "Totalnya 66 kepala keluarga",
    107: "Orang Han dan Qiang sama-sama tinggal",
    108: "Sebelah timur desa kebanyakan orang Han",
    109: "Yang dekat lereng sebelah barat",
    110: "Ada orang Qiang",
    111: "Li Er adalah orang Qiang",
    112: "Belajar strategi denganku beberapa tahun",
    113: "Sekarang seperti anakku sendiri",
    114: "Pantas Kapten jadi ahli komando",
    115: "Pinter banget",
    116: "Tadi nggak cedera, kan?",
    117: "Hampir celaka",
    118: "Sudah sore nih",
    119: "Jam segini",
    120: "Di jalan gampang ketemu harimau",
    121: "Kalau mau turun gunung,",
    122: "Lebih baik cepat berangkat",
    123: "Diam. Lebih rendah",
    124: "Lebih cepat dari harimau",
    125: "Nggak ada yang perlu ditakuti",
    126: "Saudara Lin",
    127: "Senjatamu",
    128: "Itu Lei Xiang Nu?",
    129: "Semacam senjata api pertahanan diri",
    130: "Kenapa nggak diperiksa?",
    131: "Mekanismenya beda",
    132: "Nggak perlu diperiksa seperti biasa",
    133: "Ini di tempat kami",
    134: "Hukuman minimal tiga tahun",
    135: "Macan tutul ini untukmu",
    136: "Aduh, nggak enak nerima ini",
    137: "Kamu yang bunuh binatang ini",
    138: "Ini nggak berguna buat kami",
    139: "Anggap saja hadiah tamu menginap",
    140: "Saudara Lin",
    141: "Hatimu ini",
    142: "Xu catat di hati",
    143: "Di depan ada kuil dewa gunung",
    144: "Malam ini kita istirahat di sana",
    145: "Mereka orang Xixia atau Liao?",
    146: "Bukan keduanya",
    147: "Kita dari tempat yang jauh",
    148: "Lagipula bukan hantu gunung",
    149: "Di sana ada api suar",
    150: "Target",

    # === Batch 4: cues 151-200 ===
    151: "Pembunuhan tanpa pandang bulu",
    152: "Perintah eliminasi",
    153: "Konfirmasi",
    154: "Saudara-saudara",
    155: "Desanya terbakar semua",
    156: "Jadi jangan asal terjun",
    157: "Ngomong sambil jalan, jangan berhenti",
    158: "Berapa jalan masuk-keluar desa?",
    159: "Dua",
    160: "Pintu utama masuk desa",
    161: "Ikuti jalan gunung turun",
    162: "Belakang ada jalan tanah",
    163: "Memutar keluar dari desa,",
    164: "Belakang arah ke mana?",
    165: "Arah ke benteng Longcheng",
    166: "Jalan ke sana sempit",
    167: "Biasanya sepi",
    168: "Tapi kuda bisa lewat",
    169: "Nggak usah jaga pintu belakang",
    170: "Pegang pintu depan saja",
    171: "Kamu mau...",
    172: "Penyerang ini cari cepat",
    173: "Pintu belakang ke kem militer",
    174: "Mereka nggak berani lewat sana",
    175: "Jalan melarikan diri ya pintu utama",
    176: "Kita jebak mereka di desa",
    177: "Semua, perhatian!",
    178: "Chen Su",
    179: "Kamu bawa Qinghe",
    180: "Ikut Saudara Xu jaga belakang",
    181: "Jangan masuk pusat desa dulu",
    182: "Jangan masuk pusat desa dulu",
    183: "Tenangkan warga",
    184: "Jaga pintu desa",
    185: "Siapa yang lari keluar dari pintu desa,",
    186: "Periksa dulu apakah warga desa",
    187: "Atau penyerang",
    188: "Warga yang cedera",
    189: "Kamu rawat dulu",
    190: "Mengerti",
    191: "Li Er",
    192: "Pakai panah awasi pintu desa",
    193: "Penyerang yang lari keluar,",
    194: "Tembak langsung",
    195: "Baik",
    196: "Changfeng, Lao Ma",
    197: "Awasi atap dan lorong dua sisi",
    198: "Cari posisi serang dan bertahan dulu",
    199: "Ya",
    200: "Haochuan",
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
