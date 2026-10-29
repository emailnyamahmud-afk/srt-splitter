#!/usr/bin/env python3
"""AI-driven SRT cleaning — S1 Lima Tentara.

Process: baca SRT Indonesia (GT) + Mandarin (source), perbaiki per cue:
- Grammar Indonesia natural
- Fix mistranslate (cross-reference Mandarin)
- Perpendang kalimat verbose
- Preserve nama orang/tempat

Batch 1: cues 1-50.
Timestamps/structure preserved EXACTLY (validated).
"""
import re
from pathlib import Path

# === Cleaned text per cue (batch 1: cues 1-50) ===
# Processed by AI with Mandarin cross-reference.
# Format: {cue_index: "cleaned text"}
CLEAN_TEXT = {
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
    print(f"Cleaned this batch: {len(CLEAN_TEXT)}")

    output_lines = []
    changes = 0
    for cue in cues:
        idx = cue['index']
        if idx in CLEAN_TEXT:
            new_text = CLEAN_TEXT[idx]
            if new_text != cue['text']:
                changes += 1
        else:
            new_text = cue['text']  # Keep GT original for unprocessed cues
        output_lines.append(str(idx))
        output_lines.append(f"{cue['start']} --> {cue['end']}")
        output_lines.append(new_text)
        output_lines.append('')

    Path(out_path).write_text('\n'.join(output_lines), encoding='utf-8')
    print(f"Changes applied: {changes}")
    print(f"Output: {out_path}")

    # Validate
    clean_cues = parse_srt(Path(out_path).read_text(encoding='utf-8'))
    assert len(clean_cues) == len(cues), "CUE COUNT MISMATCH"
    ts_mismatch = sum(1 for o, c in zip(cues, clean_cues)
                      if o['start'] != c['start'] or o['end'] != c['end'])
    print(f"Timestamp mismatch: {ts_mismatch} (must be 0)")
    print(f"✅ Validation passed" if ts_mismatch == 0 else "❌ FAILED")


if __name__ == '__main__':
    main()
