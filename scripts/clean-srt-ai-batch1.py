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
