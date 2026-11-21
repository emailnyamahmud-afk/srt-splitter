#!/usr/bin/env python3
"""Reproduce mix-tui subtitle filter error dengan SRT path berisi comma + !.
Test beberapa fix approach untuk cari yang jalan."""
import subprocess
import os
import sys

WORK = '/tmp/sub-escape-test'
os.makedirs(WORK, exist_ok=True)

# 1. Buat dummy MP4 (1 frame, 2s) — pakai lavfi testsrc
mp4 = f'{WORK}/input.mp4'
print("=== Buat dummy MP4 ===")
subprocess.run([
    'ffmpeg', '-y', '-f', 'lavfi', '-i', 'testsrc=size=320x240:duration=2',
    '-frames:v', '30', mp4
], capture_output=True)
print(f"  MP4: {mp4} ({os.path.getsize(mp4)} bytes)")

# 2. Buat SRT dengan comma + ! di filename (mirror case user)
srt_name = "S2 Kota kecil yang mengaku miskin penuh harta, raja datang diam-diam lalu marah besar!.id.srt"
srt_path = f'{WORK}/{srt_name}'
with open(srt_path, 'w') as f:
    f.write("1\n00:00:00,000 --> 00:00:02,000\nTest subtitle\n\n")
print(f"  SRT: {srt_path}")

force_style = ("Fontsize=18,PrimaryColour=&H00FFFFFF,OutlineColour=&H80000000,"
               "BorderStyle=1,Outline=2,Shadow=1,Alignment=2,MarginV=20,Justify=2")

# Approach A: escaping mix-tui saat ini (escape \ : ' TAPI bukan ,)
def escape_current(p):
    return p.replace('\\', '\\\\').replace(':', '\\:').replace("'", "\\'")

# Approach B: escape \ : ' , ; [ ] (semua filtergraph special chars)
def escape_all_nquotes(p):
    return (p.replace('\\', '\\\\').replace(':', '\\:').replace("'", "\\'")
             .replace(',', '\\,').replace(';', '\\;').replace('[', '\\[').replace(']', '\\]'))

# Approach C: single quote only (escape ' saja, biar quote protect sisanya)
def escape_squote_only(p):
    return p.replace("'", "\\'")

# Approach D: escape comma + colon, NO single quotes wrap
def escape_all_no_wrap(p):
    return (p.replace('\\', '\\\\').replace(':', '\\:').replace("'", "\\'")
             .replace(',', '\\,').replace(';', '\\;').replace('[', '\\[').replace(']', '\\]')
             .replace(' ', '\\ '))  # escape space juga

approaches = [
    ('A current (escape \\ : \', single-quote wrap)', escape_current, True),
    ('B escape-all + single-quote wrap', escape_all_nquotes, True),
    ('C single-quote only (escape \' saja)', escape_squote_only, True),
    ('D escape-all NO wrap (escape space jg)', escape_all_no_wrap, False),
    ('E escape-all + wrap + f= prefix', escape_all_nquotes, True),  # pakai f=
]

for name, esc_fn, use_quote in approaches:
    print(f"\n=== Approach {name} ===")
    srt_escaped = esc_fn(srt_path)
    if use_quote:
        if 'f= prefix' in name:
            flt = f"subtitles=f='{srt_escaped}':force_style='{force_style}'"
        else:
            flt = f"subtitles='{srt_escaped}':force_style='{force_style}'"
    else:
        flt = f"subtitles={srt_escaped}:force_style='{force_style}'"
    filter_complex = f"[0:v]{flt}[vout]"

    out = f'{WORK}/out_{name[:2]}.mp4'
    cmd = ['ffmpeg', '-y', '-i', mp4, '-filter_complex', filter_complex,
           '-map', '[vout]', '-map', '0:a?', '-frames:v', '5', out]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode == 0 and os.path.exists(out) and os.path.getsize(out) > 100:
        print(f"  ✓ SUCCESS ({os.path.getsize(out)} bytes)")
    else:
        # extract key error line
        err_lines = [l for l in r.stderr.split('\n') if 'Error' in l or 'No option' in l or 'Invalid' in l]
        print(f"  ✗ FAIL: {err_lines[0] if err_lines else r.stderr[-200:]}")
