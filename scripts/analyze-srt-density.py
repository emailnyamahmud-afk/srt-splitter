#!/usr/bin/env python3
"""
Analisis SRT Jawa user — hitung distribusi cue duration dan estimasi audio natural.
Tujuan: validasi apakah trim silence cukup, atau masalah sebenarnya di text length mismatch.
"""

import re
import sys
from pathlib import Path

def parse_srt(content):
    normalized = content.replace('\r\n', '\n').replace('\r', '\n').strip()
    blocks = re.split(r'\n\s*\n', normalized)
    entries = []
    for block in blocks:
        lines = [l for l in block.split('\n') if l.strip()]
        if not lines: continue
        time_idx = -1
        for i, line in enumerate(lines):
            if '-->' in line:
                time_idx = i
                break
        if time_idx == -1: continue
        m = re.match(r'(\d{1,2}:\d{2}:\d{2}[,.]\d{1,3})\s*-->\s*(\d{1,2}:\d{2}:\d{2}[,.]\d{1,3})', lines[time_idx])
        if not m: continue
        def parse_ts(ts):
            ts = ts.replace('.', ',')
            hms, ms = ts.split(',')
            h, mi, s = hms.split(':')
            return int(h)*3600 + int(mi)*60 + int(s) + int(ms)/1000
        start = parse_ts(m.group(1))
        end = parse_ts(m.group(2))
        text = '\n'.join(lines[time_idx + 1:]).strip()
        entries.append({'start': start, 'end': end, 'duration': end - start, 'text': text})
    return entries

# Hitung words per second heuristic untuk bahasa Jawa TTS
# Edge TTS Indonesia natural rate ≈ 2.5 kata/detik (krama inggil agak lambat)
# Dengan trim hening, mungkin 3 kata/detik
# Dengan rate +50% (1.5x) = 4.5 kata/detik
NATURAL_WPS = 2.5  # kata/detik natural
TRIMMED_WPS = 3.0  # setelah trim hening

def analyze(srt_path, label):
    print(f'\n=== {label}: {srt_path} ===')
    content = Path(srt_path).read_text(encoding='utf-8')
    entries = parse_srt(content)
    if not entries:
        print('Empty SRT')
        return

    durations = [e['duration'] for e in entries]
    word_counts = [len(e['text'].split()) for e in entries]
    char_counts = [len(e['text']) for e in entries]

    total_dur = sum(durations)
    total_words = sum(word_counts)
    total_chars = sum(char_counts)

    print(f'Total cues: {len(entries)}')
    print(f'Total duration: {total_dur:.1f}s ({total_dur/60:.1f}m)')
    print(f'Total words: {total_words}')
    print(f'Total chars: {total_chars}')
    print(f'Avg cue duration: {total_dur/len(entries):.2f}s')
    print(f'Avg words per cue: {total_words/len(entries):.1f}')
    print(f'Overall density: {total_words/total_dur:.2f} kata/detik (target ≤3.0 natural)')

    # Distribusi cue duration
    short = sum(1 for d in durations if d < 0.5)
    medium = sum(1 for d in durations if 0.5 <= d < 1.0)
    long_ = sum(1 for d in durations if 1.0 <= d < 2.0)
    very_long = sum(1 for d in durations if d >= 2.0)
    print(f'\nDistribusi cue duration:')
    print(f'  <0.5s (super pendek): {short} ({100*short/len(entries):.1f}%)')
    print(f'  0.5-1.0s (pendek): {medium} ({100*medium/len(entries):.1f}%)')
    print(f'  1.0-2.0s (normal): {long_} ({100*long_/len(entries):.1f}%)')
    print(f'  ≥2.0s (panjang): {very_long} ({100*very_long/len(entries):.1f}%)')

    # Estimasi: untuk tiap cue, berapa detik audio natural Edge TTS?
    # Asumsi: 2.5 kata/detik natural, setelah trim 3.0 kata/detik
    # Ratio = natural_audio / cue_duration
    print(f'\nEstimasi ratio speed-up (kalau pakai natural Edge TTS):')
    natural_ratios = []
    trimmed_ratios = []
    for e in entries:
        words = len(e['text'].split())
        natural_audio = words / NATURAL_WPS  # detik
        trimmed_audio = words / TRIMMED_WPS
        if e['duration'] > 0:
            natural_ratios.append(natural_audio / e['duration'])
            trimmed_ratios.append(trimmed_audio / e['duration'])

    def stats(arr):
        if not arr: return 'n/a'
        sorted_arr = sorted(arr)
        n = len(sorted_arr)
        median = sorted_arr[n//2]
        p90 = sorted_arr[int(n*0.9)]
        p95 = sorted_arr[int(n*0.95)]
        return f'median={median:.2f}, p90={p90:.2f}, p95={p95:.2f}, max={max(arr):.2f}'

    print(f'  Natural (2.5 wps): {stats(natural_ratios)}')
    print(f'  Trimmed (3.0 wps): {stats(trimmed_ratios)}')

    # Hitung berapa % cue yang akan jadi robot
    def pct_robot(arr, threshold=1.5):
        if not arr: return 0
        return 100 * sum(1 for r in arr if r > threshold) / len(arr)
    print(f'\n% cue yang akan ROBOT (ratio > 1.5x):')
    print(f'  Natural: {pct_robot(natural_ratios):.1f}%')
    print(f'  Trimmed: {pct_robot(trimmed_ratios):.1f}%')

    # Sample 10 cue terpendek + 10 cue terpadat
    print(f'\nSample 10 cue dengan ratio tertinggi (paling robot):')
    sorted_by_ratio = sorted(entries, key=lambda e: len(e['text'].split()) / e['duration'] if e['duration'] > 0 else 0, reverse=True)
    for e in sorted_by_ratio[:10]:
        words = len(e['text'].split())
        natural = words / NATURAL_WPS
        trimmed = words / TRIMMED_WPS
        ratio_n = natural / e['duration']
        ratio_t = trimmed / e['duration']
        print(f'  cue @ {e["start"]:.1f}s, dur={e["duration"]:.2f}s, words={words}, ratio_natural={ratio_n:.2f}x, ratio_trimmed={ratio_t:.2f}x')
        print(f'    text: "{e["text"][:80]}"')

if __name__ == '__main__':
    # Cek Season 1 dan Season 6 (terbaru)
    seasons = [
        '/home/z/my-project/download/Season-1-jw-fixed.srt',
        '/home/z/my-project/download/Season-6-jw-fixed.srt',
    ]
    for s in seasons:
        if Path(s).exists():
            analyze(s, Path(s).stem)
