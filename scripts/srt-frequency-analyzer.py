#!/usr/bin/env python3
"""
srt-frequency-analyzer.py v2 — Analisis SRT Jawa, hitung frekuensi kata,
daftar top kata yang BELUM ada di kamus (prioritas user isi arti).

User story:
- SRT Jawa (hasil Google Translate) = campuran ngoko + krama + alias
- Kamus ground of truth = Supabase DB (yang user upload, mulai dari 2 entries)
- User mau tahu: kata apa yang sering muncul di SRT tapi belum ada di kamus DB?
  Itu prioritas untuk user isi arti + validasi krama mapping.

Filosofi (8 Okt 2026):
  - Supabase DB = ground of truth (yang user upload)
  - Kamus JSON lokal 44.585 entries = working draft di MacBook (untuk TUI edit)
  - Web app + analyzer HARUS pakai Supabase, bukan JSON lokal
  - Jadi analyzer fetch kamus dari Supabase REST API, bukan dari file JSON

Output:
  1. Top 100 kata paling sering di SRT (sudah ada di DB → ✓, belum → ⚠)
  2. List kata yang belum ada di DB, urut by frequency (paling sering di atas)
  3. Save ke file: ~/Dubbing/srt-freq-report.txt

Usage:
  python3 srt-frequency-analyzer.py [srt-file]
  Default:
    srt-file = ~/Dubbing/srt-id-srt-dub.srt
    Supabase credentials dari ~/Dubbing/.env (sama seperti kamus-tui.py)

Contoh:
  python3 srt-frequency-analyzer.py
  python3 srt-frequency-analyzer.py ~/Dubbing/S1-jw.srt
"""

import sys
import os
import re
import json
import argparse
import urllib.request
import urllib.error
from pathlib import Path
from collections import Counter

DEFAULT_SRT = Path.home() / 'Dubbing' / 'srt-id-srt-dub.srt'
DEFAULT_OUTPUT = Path.home() / 'Dubbing' / 'srt-freq-report.txt'
ENV_FILE = Path.home() / 'Dubbing' / '.env'


def load_env_file():
    """Load .env dari ~/Dubbing/.env (sama seperti kamus-tui.py)."""
    if not ENV_FILE.exists():
        return
    with open(ENV_FILE, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            if '=' in line:
                key, value = line.split('=', 1)
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                if key and key not in os.environ:
                    os.environ[key] = value


def parse_srt(srt_path):
    """Parse SRT, return list of text lines (tanpa timestamp, tanpa nomor cue)."""
    if not srt_path.exists():
        print(f'❌ SRT tidak ada: {srt_path}')
        return []

    with open(srt_path, 'r', encoding='utf-8') as f:
        content = f.read()

    text_lines = []
    blocks = re.split(r'\n\s*\n', content.strip())
    for block in blocks:
        lines = block.strip().split('\n')
        if len(lines) < 3:
            continue
        for line in lines[2:]:
            line = line.strip()
            if line and not line.isdigit() and '-->' not in line:
                text_lines.append(line)
    return text_lines


def tokenize(text_lines):
    """Tokenize text → list of kata (lowercase, strip punctuation)."""
    tokens = []
    word_pattern = re.compile(r"[àáâãäåæçèéêëìíîïðñòóôõöøùúûüýþÿa-zA-Z']+")
    for line in text_lines:
        words = word_pattern.findall(line)
        for w in words:
            w_lower = w.lower().strip("'")
            if w_lower and len(w_lower) > 0:
                tokens.append(w_lower)
    return tokens


def fetch_kamus_from_supabase():
    """Fetch kamus dari Supabase REST API (GROUND OF TRUTH).
    Returns: (set of known_words, list of entries_with_krama) atau (None, None) kalau gagal.
    """
    load_env_file()
    URL = os.environ.get('NEXT_PUBLIC_SUPABASE_URL', '')
    KEY = os.environ.get('NEXT_PUBLIC_SUPABASE_ANON_KEY', '')

    if not URL or not KEY:
        print(f'❌ Supabase belum di-set.')
        print(f'   Set di ~/Dubbing/.env (atau via kamus-tui.py menu "🔑 Set Supabase .env"):')
        print(f'     NEXT_PUBLIC_SUPABASE_URL=https://zdrgzbwjlrvyloxjdyfl.supabase.co')
        print(f'     NEXT_PUBLIC_SUPABASE_ANON_KEY=eyJxxx...')
        return None, None

    print(f'☁  Fetch kamus dari Supabase: {URL[:40]}...')

    headers = {
        'apikey': KEY,
        'Authorization': f'Bearer {KEY}',
    }
    # Select kolom yang diperlukan saja (hemat bandwidth)
    select_url = f'{URL}/rest/v1/kamus?select=ngoko,krama,krama_inggil,arti,register&order=ngoko&limit=50000'

    req = urllib.request.Request(select_url, headers=headers, method='GET')
    try:
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read().decode('utf-8'))
    except urllib.error.HTTPError as e:
        error_body = e.read().decode('utf-8', errors='replace')[:300]
        print(f'❌ HTTP {e.code}: {error_body}')
        return None, None
    except Exception as e:
        print(f'❌ Error: {e}')
        return None, None

    if not data:
        print(f'⚠ Supabase tabel kamus kosong. Upload dulu via kamus-tui.py.')
        return set(), []

    known_words = set()
    entries_with_krama = []

    for entry in data:
        ngoko = entry.get('ngoko', '') or ''
        krama = entry.get('krama', '') or ''
        ki = entry.get('krama_inggil', '') or ''
        arti = entry.get('arti', '') or ''

        # Tambah ngoko + alias ke known_words
        for n in ngoko.split(','):
            n = n.strip().lower()
            if n:
                known_words.add(n)
        # Tambah krama + alias
        for k in krama.split(','):
            k = k.strip().lower()
            if k:
                known_words.add(k)
        # Tambah krama_inggil + alias
        for k in ki.split(','):
            k = k.strip().lower()
            if k:
                known_words.add(k)

        # Track entries dengan krama mapping (untuk display)
        if krama:
            entries_with_krama.append({
                'ngoko': ngoko.split(',')[0].strip(),
                'krama': krama,
                'arti': arti,
                'register': entry.get('register', 'umum'),
            })

    return known_words, entries_with_krama


def analyze(srt_path, output_path):
    print(f'📁 SRT: {srt_path}')
    print()

    # Fetch kamus dari Supabase (GROUND OF TRUTH)
    known_words, entries_with_krama = fetch_kamus_from_supabase()
    if known_words is None:
        return

    print(f'✓ Kamus DB (Supabase): {len(known_words)} kata dikenal (ngoko + krama + alias)')
    print(f'  Total entries di DB: {len(entries_with_krama)} (yang punya krama mapping)')
    print()

    # Parse SRT
    text_lines = parse_srt(srt_path)
    if not text_lines:
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

    print(f'📊 Kata Dikenal DB: {len(known_freq)} unique ({sum(known_freq.values())} total)')
    print(f'📊 Kata TIDAK dikenal: {len(unknown_freq)} unique ({sum(unknown_freq.values())} total)')
    if tokens:
        coverage = 100 * sum(known_freq.values()) / len(tokens)
        type_coverage = 100 * len(known_freq) / max(1, unique_words)
        print(f'   Coverage: {coverage:.1f}% token, {type_coverage:.1f}% type')
    print()

    # Top 50 kata yang dikenal (sudah ada di DB)
    print('=' * 70)
    print('TOP 50 KATA DIKENAL DB (paling sering muncul di SRT):')
    print('=' * 70)
    print(f'{"#":>4}  {"Freq":>5}  {"Kata":<20}  Status')
    print('-' * 70)
    for i, (word, count) in enumerate(sorted(known_freq.items(), key=lambda x: -x[1])[:50], 1):
        # Cek apakah ada krama mapping
        has_krama = any(
            e['ngoko'].lower() == word or word in [k.strip().lower() for k in e['krama'].split(',')]
            for e in entries_with_krama
        )
        status = '✓ krama mapping' if has_krama else '○ ngoko saja'
        print(f'{i:>4}  {count:>5}  {word:<20}  {status}')
    print()

    # Top 100 kata yang TIDAK dikenal (prioritas user add ke kamus)
    print('=' * 70)
    print('TOP 100 KATA TIDAK DIKENAL DB (prioritas add ke kamus + isi arti):')
    print('=' * 70)
    print(f'{"#":>4}  {"Freq":>5}  {"Kata":<25}  Suggestion')
    print('-' * 70)

    unknown_top = sorted(unknown_freq.items(), key=lambda x: -x[1])[:100]
    for i, (word, count) in enumerate(unknown_top, 1):
        # Suggest: cek apakah mirip dengan yang ada di kamus (base + suffix, reduplication)
        suggestion = ''
        if '-' in word:
            base = word.split('-')[0]
            if base in known_words:
                suggestion = f'base "{base}" ada di DB, mungkin reduplikasi'
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
        f.write(f'Kamus source: Supabase DB (GROUND OF TRUTH)\n')
        f.write(f'\n')

        f.write(f'STATS:\n')
        f.write(f'  Total kata di SRT: {len(tokens)}\n')
        f.write(f'  Unique words: {unique_words}\n')
        f.write(f'  Kata dikenal DB: {len(known_freq)}')
        if tokens:
            f.write(f' ({100 * sum(known_freq.values()) / max(1, len(tokens)):.1f}% token)\n')
        else:
            f.write(f'\n')
        f.write(f'  Kata TIDAK dikenal: {len(unknown_freq)}')
        if tokens:
            f.write(f' ({100 * sum(unknown_freq.values()) / max(1, len(tokens)):.1f}% token)\n')
        else:
            f.write(f'\n')
        f.write(f'  Coverage type: {100 * len(known_freq) / max(1, unique_words):.1f}%\n\n')

        f.write(f'TOP 50 KATA DIKENAL DB:\n')
        f.write(f'{"#":>4}  {"Freq":>5}  {"Kata":<20}  Status\n')
        f.write(f'-' * 70 + '\n')
        for i, (word, count) in enumerate(sorted(known_freq.items(), key=lambda x: -x[1])[:50], 1):
            has_krama = any(
                e['ngoko'].lower() == word or word in [k.strip().lower() for k in e['krama'].split(',')]
                for e in entries_with_krama
            )
            status = '✓ krama mapping' if has_krama else '○ ngoko saja'
            f.write(f'{i:>4}  {count:>5}  {word:<20}  {status}\n')
        f.write('\n')

        f.write(f'TOP 200 KATA TIDAK DIKENAL DB (prioritas add ke kamus):\n')
        f.write(f'{"#":>4}  {"Freq":>5}  {"Kata":<25}  Suggestion\n')
        f.write(f'-' * 70 + '\n')
        for i, (word, count) in enumerate(sorted(unknown_freq.items(), key=lambda x: -x[1])[:200], 1):
            suggestion = ''
            if '-' in word:
                base = word.split('-')[0]
                if base in known_words:
                    suggestion = f'base "{base}" ada di DB'
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
    print(f'   2. Cari top kata "TIDAK dikenal" — itu prioritas')
    print(f'   3. Di kamus-tui.py: Search kata → edit entry (isi ngoko + krama + arti)')
    print(f'   4. Upload ke Supabase (menu ☁ Upload)')
    print(f'   5. Run analyzer lagi → kata sekarang dikenali → coverage naik')


def main():
    parser = argparse.ArgumentParser(
        description='SRT Frequency Analyzer — pakai Supabase DB sebagai ground of truth',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Contoh:
  python3 srt-frequency-analyzer.py
  python3 srt-frequency-analyzer.py ~/Dubbing/S1-jw.srt

Note: Kamus di-fetch dari Supabase DB (yang user upload via kamus-tui.py).
      Bukan dari kamus-jawa-full.json lokal (itu cuma working draft untuk TUI edit).
        """,
    )
    parser.add_argument('srt', nargs='?', default=str(DEFAULT_SRT),
                        help=f'File SRT (default: {DEFAULT_SRT})')
    parser.add_argument('--output', default=str(DEFAULT_OUTPUT),
                        help=f'Output report (default: {DEFAULT_OUTPUT})')
    args = parser.parse_args()

    srt_path = Path(args.srt).expanduser()
    output_path = Path(args.output).expanduser()

    if not srt_path.exists():
        print(f'❌ SRT tidak ada: {srt_path}')
        print(f'   Pakai: python3 srt-frequency-analyzer.py <srt-file>')
        sys.exit(1)

    analyze(srt_path, output_path)


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
