#!/usr/bin/env python3
"""
srt-frequency-analyzer.py — Analisis SRT Jawa, hitung frekuensi kata,
daftar top kata yang BELUM ada di kamus (prioritas user isi arti).

User story:
- SRT Jawa (hasil Google Translate) = campuran ngoko + krama + alias
- Kamus lokal = 44.585 entries (auto-fill ngoko-krama), tapi arti kosong semua
- User mau tahu: kata apa yang sering muncul di SRT tapi belum ada di kamus?
  Itu prioritas untuk user isi arti + validasi krama mapping.

Output:
  1. Top 100 kata paling sering di SRT (sudah ada di kamus → ✓, belum → ⚠)
  2. List kata yang belum ada di kamus, urut by frequency (paling sering di atas)
  3. Save ke file: ~/Dubbing/srt-freq-report.txt (untuk referensi user)

Usage:
  python3 srt-frequency-analyzer.py [srt-file] [--kamus kamus-jawa-full.json]
  Default:
    srt-file = ~/Dubbing/srt-id-srt-dub.srt (atau argumen pertama)
    kamus = ~/Dubbing/kamus-jawa-full.json

Contoh:
  python3 srt-frequency-analyzer.py
  python3 srt-frequency-analyzer.py ~/Dubbing/S1-jw.srt
  python3 srt-frequency-analyzer.py ~/Dubbing/S1-jw.srt --kamus ~/Dubbing/kamus-jawa-full.json
"""

import sys
import os
import re
import json
import argparse
from pathlib import Path
from collections import Counter

DEFAULT_SRT = Path.home() / 'Dubbing' / 'srt-id-srt-dub.srt'
DEFAULT_KAMUS = Path.home() / 'Dubbing' / 'kamus-jawa-full.json'
DEFAULT_OUTPUT = Path.home() / 'Dubbing' / 'srt-freq-report.txt'


def parse_srt(srt_path):
    """Parse SRT, return list of text lines (tanpa timestamp, tanpa nomor cue)."""
    if not srt_path.exists():
        print(f'❌ SRT tidak ada: {srt_path}')
        return []

    with open(srt_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # Pattern: skip nomor cue, skip timestamp line, ambil text
    # SRT format:
    #   1
    #   00:00:01,000 --> 00:00:05,000
    #   Text line 1
    #   Text line 2
    #   <empty line>
    text_lines = []
    blocks = re.split(r'\n\s*\n', content.strip())
    for block in blocks:
        lines = block.strip().split('\n')
        if len(lines) < 3:
            continue
        # Skip first 2 lines (nomor + timestamp)
        for line in lines[2:]:
            line = line.strip()
            if line and not line.isdigit() and '-->' not in line:
                text_lines.append(line)
    return text_lines


def tokenize(text_lines):
    """Tokenize text → list of kata (lowercase, strip punctuation)."""
    tokens = []
    # Pattern: ambil word characters (termasuk aksen Jawa), strip punctuation
    word_pattern = re.compile(r"[àáâãäåæçèéêëìíîïðñòóôõöøùúûüýþÿa-zA-Z']+")
    for line in text_lines:
        words = word_pattern.findall(line)
        for w in words:
            w_lower = w.lower().strip("'")
            if w_lower and len(w_lower) > 0:
                tokens.append(w_lower)
    return tokens


def load_kamus_set(kamus_path):
    """Load kamus, return SET of all known words (ngoko + krama + krama_inggil + alias)."""
    if not kamus_path.exists():
        print(f'❌ Kamus tidak ada: {kamus_path}')
        print(f'   Download: curl -L -o ~/Dubbing/kamus-jawa-full.json.gz \\')
        print(f'     https://github.com/emailnyamahmud-afk/srt-splitter/raw/main/public/kamus-jawa-full.json.gz')
        print(f'   gunzip ~/Dubbing/kamus-jawa-full.json.gz')
        return set(), []

    with open(kamus_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    known_words = set()
    entries_with_krama = []  # entries yang punya krama mapping (auto-filled)

    for entry in data.get('words', []):
        # Tambah ngoko + alias ke known_words
        ngoko = entry.get('ngoko', '') or ''
        for n in ngoko.split(','):
            n = n.strip().lower()
            if n:
                known_words.add(n)

        # Tambah krama + alias
        krama = entry.get('krama', '') or ''
        for k in krama.split(','):
            k = k.strip().lower()
            if k:
                known_words.add(k)

        # Tambah krama_inggil + alias
        ki = entry.get('krama_inggil', '') or ''
        for k in ki.split(','):
            k = k.strip().lower()
            if k:
                known_words.add(k)

        # Track entries dengan krama mapping (untuk suggest user isi arti)
        if krama:
            entries_with_krama.append({
                'ngoko': ngoko.split(',')[0].strip(),
                'krama': krama,
                'arti': entry.get('arti', ''),
                'register': entry.get('register', 'umum'),
            })

    return known_words, entries_with_krama


def analyze(srt_path, kamus_path, output_path):
    print(f'📁 SRT: {srt_path}')
    print(f'📁 Kamus: {kamus_path}')
    print()

    # Load kamus
    known_words, entries_with_krama = load_kamus_set(kamus_path)
    print(f'✓ Kamus: {len(known_words)} kata dikenal (ngoko + krama + alias)')
    print(f'  Dengan krama mapping (auto-filled): {len(entries_with_krama)} entries')
    print()

    # Parse SRT
    text_lines = parse_srt(srt_path)
    if not text_lines:
        print('❌ Tidak ada text di SRT')
        return
    print(f'✓ SRT: {len(text_lines)} text lines')

    # Tokenize
    tokens = tokenize(text_lines)
    print(f'✓ Tokenized: {len(tokens)} kata total')
    print()

    # Hitung frequency
    freq = Counter(tokens)
    unique_words = len(freq)
    print(f'✓ Unique words: {unique_words}')
    print()

    # Klasifikasi: known vs unknown
    known_freq = {w: c for w, c in freq.items() if w in known_words}
    unknown_freq = {w: c for w, c in freq.items() if w not in known_words}

    print(f'📊 Kata Dikenal kamus: {len(known_freq)} unique ({sum(known_freq.values())} total)')
    print(f'📊 Kata TIDAK dikenal: {len(unknown_freq)} unique ({sum(unknown_freq.values())} total)')
    print(f'   Coverage: {100 * sum(known_freq.values()) / max(1, len(tokens)):.1f}% token, '
          f'{100 * len(known_freq) / max(1, unique_words):.1f}% type')
    print()

    # Top 50 kata yang dikenal (sudah ada di kamus)
    print('=' * 70)
    print('TOP 50 KATA DIKENAL KAMUS (paling sering muncul di SRT):')
    print('=' * 70)
    print(f'{"#":>4}  {"Freq":>5}  {"Kata":<20}  Status')
    print('-' * 70)
    for i, (word, count) in enumerate(sorted(known_freq.items(), key=lambda x: -x[1])[:50], 1):
        # Cek apakah ada krama mapping
        has_krama = any(e['ngoko'].lower() == word or word in e['krama'].lower().split(',')
                       for e in entries_with_krama if e['ngoko'].lower() == word)
        status = '✓ krama mapping' if has_krama else '○ ngoko saja'
        print(f'{i:>4}  {count:>5}  {word:<20}  {status}')
    print()

    # Top 100 kata yang TIDAK dikenal (prioritas user add ke kamus)
    print('=' * 70)
    print('TOP 100 KATA TIDAK DIKENAL (prioritas add ke kamus + isi arti):')
    print('=' * 70)
    print(f'{"#":>4}  {"Freq":>5}  {"Kata":<25}  Suggestion')
    print('-' * 70)

    unknown_top = sorted(unknown_freq.items(), key=lambda x: -x[1])[:100]
    for i, (word, count) in enumerate(unknown_top, 1):
        # Suggest: kalau kata mirip dengan yang ada di kamus (e.g. plural, reduplication)
        suggestion = ''
        # Cek reduplication (mangan-mangan, sega-sega)
        if '-' in word:
            base = word.split('-')[0]
            if base in known_words:
                suggestion = f'base "{base}" ada di kamus, mungkin reduplikasi'
        # Cek plural/possessive (-ku, -mu, -ne, -e)
        for suffix in ['-ku', '-mu', '-ne', '-e', '-na', '-ana', '-aken', '-an']:
            if word.endswith(suffix):
                base = word[:-len(suffix)]
                if base in known_words:
                    suggestion = f'base "{base}" + suffix {suffix}'
                    break
        print(f'{i:>4}  {count:>5}  {word:<25}  {suggestion}')
    print()

    # Save report ke file
    print('=' * 70)
    print(f'Menyimpan laporan ke: {output_path}')
    print('=' * 70)

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(f'SRT Frequency Analyzer Report\n')
        f.write(f'============================\n\n')
        f.write(f'SRT: {srt_path}\n')
        f.write(f'Kamus: {kamus_path}\n')
        f.write(f'Tanggal: {Path().resolve()}\n\n')

        f.write(f'STATS:\n')
        f.write(f'  Total kata di SRT: {len(tokens)}\n')
        f.write(f'  Unique words: {unique_words}\n')
        f.write(f'  Kata dikenal kamus: {len(known_freq)} ({100 * sum(known_freq.values()) / max(1, len(tokens)):.1f}% token)\n')
        f.write(f'  Kata TIDAK dikenal: {len(unknown_freq)} ({100 * sum(unknown_freq.values()) / max(1, len(tokens)):.1f}% token)\n')
        f.write(f'  Coverage: {100 * len(known_freq) / max(1, unique_words):.1f}% type\n\n')

        f.write(f'TOP 50 KATA DIKENAL KAMUS:\n')
        f.write(f'{"#":>4}  {"Freq":>5}  {"Kata":<20}  Status\n')
        f.write(f'-' * 70 + '\n')
        for i, (word, count) in enumerate(sorted(known_freq.items(), key=lambda x: -x[1])[:50], 1):
            has_krama = any(e['ngoko'].lower() == word for e in entries_with_krama)
            status = '✓ krama mapping' if has_krama else '○ ngoko saja'
            f.write(f'{i:>4}  {count:>5}  {word:<20}  {status}\n')
        f.write('\n')

        f.write(f'TOP 200 KATA TIDAK DIKENAL (prioritas add ke kamus):\n')
        f.write(f'{"#":>4}  {"Freq":>5}  {"Kata":<25}  Suggestion\n')
        f.write(f'-' * 70 + '\n')
        for i, (word, count) in enumerate(sorted(unknown_freq.items(), key=lambda x: -x[1])[:200], 1):
            suggestion = ''
            if '-' in word:
                base = word.split('-')[0]
                if base in known_words:
                    suggestion = f'base "{base}" ada di kamus'
            for suffix in ['-ku', '-mu', '-ne', '-e', '-na', '-ana', '-aken', '-an']:
                if word.endswith(suffix):
                    base = word[:-len(suffix)]
                    if base in known_words:
                        suggestion = f'base "{base}" + {suffix}'
                        break
            f.write(f'{i:>4}  {count:>5}  {word:<25}  {suggestion}\n')

    print(f'\n✅ Laporan tersimpan: {output_path}')
    print(f'   Buka di VSCode atau text editor untuk lihat full list')
    print()
    print(f'💡 Workflow berikutnya:')
    print(f'   1. Buka laporan: code {output_path}')
    print(f'   2. Cari top kata "TIDAK dikenal" di kamus-tui.py')
    print(f'   3. Add entry baru (ngoko + krama + arti) untuk kata tersebut')
    print(f'   4. Upload ke Supabase')
    print(f'   5. Reload Editor SRT Jawa → kamus refresh → kata sekarang dikenali')


def main():
    parser = argparse.ArgumentParser(
        description='SRT Frequency Analyzer — prioritaskan kata untuk isi kamus',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Contoh:
  python3 srt-frequency-analyzer.py
  python3 srt-frequency-analyzer.py ~/Dubbing/S1-jw.srt
  python3 srt-frequency-analyzer.py ~/Dubbing/S1-jw.srt --kamus ~/Dubbing/kamus-jawa-full.json
        """,
    )
    parser.add_argument('srt', nargs='?', default=str(DEFAULT_SRT),
                        help=f'File SRT (default: {DEFAULT_SRT})')
    parser.add_argument('--kamus', default=str(DEFAULT_KAMUS),
                        help=f'File kamus JSON (default: {DEFAULT_KAMUS})')
    parser.add_argument('--output', default=str(DEFAULT_OUTPUT),
                        help=f'Output report (default: {DEFAULT_OUTPUT})')
    args = parser.parse_args()

    srt_path = Path(args.srt).expanduser()
    kamus_path = Path(args.kamus).expanduser()
    output_path = Path(args.output).expanduser()

    if not srt_path.exists():
        print(f'❌ SRT tidak ada: {srt_path}')
        print(f'   Pakai: python3 srt-frequency-analyzer.py <srt-file>')
        sys.exit(1)

    analyze(srt_path, kamus_path, output_path)


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print('\n⏹ Dibatalkan.')
        sys.exit(130)
    except Exception as e:
        print(f'\n❌ Error: {e}', file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)
