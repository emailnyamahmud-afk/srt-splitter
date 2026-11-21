#!/usr/bin/env python3
"""Test fix v3.11.2: buang single-quote di SRT path, escape semua special char.
Root cause v3.11.1: escape comma dlm single-quote NGGAK solve ffmpeg 9.x
(quote pairing sendiri yg break). Approach baru: NO single-quote di path,
escape \ : ' , ; [ ] — filtergraph parser handle via escape, bukan quote."""
import subprocess, os, wave
from PIL import Image

WORK = '/tmp/sub-fix-v3112'
os.makedirs(WORK, exist_ok=True)

mp4 = f'{WORK}/input.mp4'
subprocess.run(['ffmpeg','-y','-f','lavfi','-i','testsrc=size=320x240:duration=2',
                '-frames:v','60', mp4], capture_output=True)

srt_name = "S1 Kota kecil yang mengaku miskin penuh harta, raja datang diam-diam lalu marah besar!.id.srt"
srt_path = f'{WORK}/{srt_name}'
with open(srt_path, 'w') as f:
    f.write("1\n00:00:00,000 --> 00:00:02,000\nTest subtitle v3.11.2\n\n")

logo = f'{WORK}/logo.png'
subprocess.run(['ffmpeg','-y','-f','lavfi','-i','color=c=red:size=100x100:d=1',
                '-frames:v','1', logo], capture_output=True)

def mkwav(p):
    with wave.open(p,'w') as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(48000)
        w.writeframes(b'\x00\x00' * 48000 * 2)
sfx, dub, env = f'{WORK}/sfx.wav', f'{WORK}/dub.wav', f'{WORK}/env.wav'
for p in [sfx, dub, env]: mkwav(p)

force_style = ("Fontsize=18,PrimaryColour=&H00FFFFFF,OutlineColour=&H80000000,"
               "BorderStyle=1,Outline=2,Shadow=1,Alignment=2,MarginV=20,Justify=2")

tw, th = 1080, 1920
scale_pre = (f'scale={tw}:{th}:force_original_aspect_ratio=decrease,'
             f'pad={tw}:{th}:(ow-iw)/2:(oh-ih)/2:color=black,setsar=1,')

def escape_all(p):
    """Escape semua filtergraph + option special chars, NO single-quote wrap."""
    return (p.replace('\\', '\\\\').replace(':', '\\:').replace("'", "\\'")
            .replace(',', '\\,').replace(';', '\\;').replace('[', '\\[').replace(']', '\\]'))

def run(label, path_filter_fmt):
    """path_filter_fmt: format string for subtitles filter (use {srt} and {fs} placeholders)."""
    srt_escaped = escape_all(srt_path)
    flt = path_filter_fmt.format(srt=srt_escaped, fs=force_style)
    subtitle_filter = f"[0:v]{scale_pre}{flt}[vsub]"
    logo_chain = f";[4:v]format=rgba,scale=100:100[logo_input];[vsub][logo_input]overlay=main_w-overlay_w-10:10[vout]"
    fc = subtitle_filter + logo_chain
    out = f'{WORK}/out_{label}.mp4'
    cmd = ['ffmpeg','-y','-i',mp4,'-i',sfx,'-i',dub,'-i',env,'-i',logo,
           '-filter_complex', fc, '-map','[vout]','-map','2:a:0',
           '-frames:v','60','-shortest', out]
    r = subprocess.run(cmd, capture_output=True, text=True)
    ok = r.returncode == 0 and os.path.exists(out) and os.path.getsize(out) > 100
    size = os.path.getsize(out) if os.path.exists(out) else 0
    if ok:
        print(f"  ✓ {label}: SUCCESS ({size} bytes)")
    else:
        err = [l for l in r.stderr.split('\n') if 'Error' in l or 'No option' in l or 'Invalid' in l]
        print(f"  ✗ {label}: FAIL — {err[0][:90] if err else 'no error line'}")
    return ok, out

print("=== Test 3 approach (sandbox 7.x — verify correctness, 9.x behavior inferred) ===\n")

# v3.11.1 (current — single-quote wrap + escape all) — INI YANG FAIL DI USER
print("v3.11.1 — single-quote wrap + escape all (FAIL di 9.x user):")
run('v3111_quote_wrap', "subtitles='{srt}':force_style='{fs}'")

# v3.11.2 FIX — NO single-quote di path, escape all. force_style tetap quoted.
print("\nv3.11.2 FIX — NO single-quote path, escape all, force_style quoted:")
ok_v3112, out_v3112 = run('v3112_no_quote', "subtitles={srt}:force_style='{fs}'")

# v3.11.2 alt — NO single-quote di path MAUPUN force_style, escape all di keduanya
print("\nv3.11.2 alt — NO single-quote sama sekali, escape all path + force_style:")
fs_escaped = force_style.replace(',', '\\,')  # escape comma di force_style
run('v3112_no_quote_alt', f"subtitles={{srt}}:force_style={fs_escaped}")

# Verify subtitle render untuk v3.11.2
if ok_v3112:
    print("\n=== Verify subtitle rendered (v3.11.2 no-quote path) ===")
    frame = f'{WORK}/frame_v3112.jpg'
    subprocess.run(['ffmpeg','-y','-ss','0.5','-i',out_v3112,'-frames:v','1',frame],
                   capture_output=True)
    if os.path.exists(frame):
        im = Image.open(frame).convert('RGB')
        w, h = im.size
        px = list(im.getdata())
        bottom_px = [px[i] for i in range(len(px)) if (i // w) > h * 0.7]
        white = sum(1 for r,g,b in bottom_px if r>180 and g>180 and b>180)
        total = len(bottom_px)
        print(f"  Frame: {w}x{h}, white pixels di bottom 30%: {white}/{total} ({white/total*100:.2f}%)")
        print(f"  {'✓ Subtitle RENDERED' if white > 20 else '⚠ Subtitle kosong'}")

# Edge cases untuk v3.11.2 (no-quote approach)
print("\n=== Edge cases v3.11.2 (no-quote path) ===")
edge = [
    ("normal.srt", "normal"),
    ("path,comma.srt", "comma"),
    ("path;semicolon.srt", "semicolon"),
    ("path[bracket].srt", "bracket"),
    ("path'quote.srt", "quote"),
    ("path with !exclaim.srt", "exclaim"),
    ("path with everything !, ;[].srt", "all"),
]
for fname, label in edge:
    p = f'{WORK}/{fname}'
    with open(p, 'w') as f:
        f.write("1\n00:00:00,000 --> 00:00:02,000\nTest\n\n")
    esc = escape_all(p)
    fc = f"[0:v]subtitles={esc}:force_style='{force_style}'[vout]"
    out = f'{WORK}/edge_{label}.mp4'
    r = subprocess.run(['ffmpeg','-y','-i',mp4,'-filter_complex',fc,
                        '-map','[vout]','-frames:v','5',out], capture_output=True, text=True)
    ok = r.returncode == 0 and os.path.exists(out) and os.path.getsize(out) > 100
    print(f"  {'✓' if ok else '✗'} {label:10} ({fname[:35]:35}): {'OK' if ok else 'FAIL'}")
    if not ok:
        err = [l for l in r.stderr.split('\n') if 'Error' in l or 'No option' in l]
        if err: print(f"      {err[0][:90]}")
