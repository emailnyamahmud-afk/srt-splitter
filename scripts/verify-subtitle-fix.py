#!/usr/bin/env python3
"""Verify fix v3.11.1: escaping baru mix-tui (escape \\ : ' , ; [ ]).
Test dengan SRT path berisi comma + ! (mirror case user).
Pastikan subtitle ACTUALLY rendered (text visible di frame)."""
import subprocess, os, wave
from PIL import Image

WORK = '/tmp/sub-verify-fix'
os.makedirs(WORK, exist_ok=True)

# Setup
mp4 = f'{WORK}/input.mp4'
subprocess.run(['ffmpeg','-y','-f','lavfi','-i','testsrc=size=320x240:duration=2',
                '-frames:v','60', mp4], capture_output=True)  # 60 frames = 2s @ 30fps

srt_name = "S2 Kota kecil yang mengaku miskin penuh harta, raja datang diam-diam lalu marah besar!.id.srt"
srt_path = f'{WORK}/{srt_name}'
with open(srt_path, 'w') as f:
    f.write("1\n00:00:00,000 --> 00:00:02,000\nTest subtitle comma path\n\n")

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

# EXACT escaping baru mix-tui v3.11.1 (escape \ : ' , ; [ ])
srt_escaped = (srt_path
               .replace('\\', '\\\\')
               .replace(':', '\\:')
               .replace("'", "\\'")
               .replace(',', '\\,')
               .replace(';', '\\;')
               .replace('[', '\\[')
               .replace(']', '\\]'))

tw, th = 1080, 1920
scale_pre = (f'scale={tw}:{th}:force_original_aspect_ratio=decrease,'
             f'pad={tw}:{th}:(ow-iw)/2:(oh-ih)/2:color=black,setsar=1,')
subtitle_filter = f"[0:v]{scale_pre}subtitles='{srt_escaped}':force_style='{force_style}'[vsub]"
logo_chain = f";[4:v]format=rgba,scale=100:100[logo_input];[vsub][logo_input]overlay=main_w-overlay_w-10:10[vout]"
fc = subtitle_filter + logo_chain

out = f'{WORK}/out_fix.mp4'
cmd = ['ffmpeg','-y','-i',mp4,'-i',sfx,'-i',dub,'-i',env,'-i',logo,
       '-filter_complex', fc, '-map','[vout]','-map','2:a:0',
       '-frames:v','60','-shortest', out]
r = subprocess.run(cmd, capture_output=True, text=True)
print(f"=== Render dengan fix v3.11.1 ===")
print(f"  ffmpeg exit: {r.returncode}")
if r.returncode != 0:
    err = [l for l in r.stderr.split('\n') if 'Error' in l or 'No option' in l]
    for e in err[:3]: print(f"  ✗ {e[:100]}")
else:
    print(f"  ✓ Render SUCCESS ({os.path.getsize(out)} bytes)")

# Extract frame di tengah video (1s) — subtitle harusnya visible
frame = f'{WORK}/frame_1s.jpg'
subprocess.run(['ffmpeg','-y','-ss','1.0','-i',out,'-frames:v','1',frame],
               capture_output=True)
if os.path.exists(frame):
    im = Image.open(frame).convert('RGB')
    w, h = im.size
    px = list(im.getdata())
    # Subtitle di bottom area (Alignment=2, MarginV=20). Cek area bawah 30% frame.
    bottom_px = [px[i] for i in range(len(px)) if (i // w) > h * 0.7]
    non_bg_bottom = sum(1 for r,g,b in bottom_px if not (r<40 and g<40 and b<40))
    total_bottom = len(bottom_px)
    # Cek juga putih (text subtitle warna putih)
    white_bottom = sum(1 for r,g,b in bottom_px if r>180 and g>180 and b>180)
    print(f"\n=== Frame @1s verify subtitle rendered ===")
    print(f"  Frame size: {w}x{h}")
    print(f"  Bottom 30% area: {total_bottom} pixels")
    print(f"  Non-bg pixels di bottom: {non_bg_bottom} ({non_bg_bottom/total_bottom*100:.1f}%)")
    print(f"  White pixels di bottom (subtitle text): {white_bottom} ({white_bottom/total_bottom*100:.2f}%)")
    if white_bottom > 20:
        print(f"  ✓ SUBTITLE RENDERED (white text visible di bottom area)")
    else:
        print(f"  ⚠ Subtitle mungkin kosong (white pixels < 20)")

# Test edge cases: path dengan ; [ ] (robustness check)
print(f"\n=== Edge case test: path dengan ; [ ] ===")
edge_cases = [
    ("normal.srt", "normal"),
    ("path with,comma.srt", "comma"),
    ("path with;semicolon.srt", "semicolon"),
    ("path with[bracket].srt", "bracket"),
    ("path'all quotes.srt", "quote"),
]
for fname, label in edge_cases:
    p = f'{WORK}/{fname}'
    with open(p, 'w') as f:
        f.write("1\n00:00:00,000 --> 00:00:02,000\nTest\n\n")
    esc = (p.replace('\\','\\\\').replace(':','\\:').replace("'","\\'")
           .replace(',','\\,').replace(';','\\;').replace('[','\\[').replace(']','\\]'))
    fc2 = f"[0:v]subtitles='{esc}':force_style='{force_style}'[vout]"
    out2 = f'{WORK}/edge_{label}.mp4'
    r2 = subprocess.run(['ffmpeg','-y','-i',mp4,'-filter_complex',fc2,
                         '-map','[vout]','-frames:v','5',out2], capture_output=True, text=True)
    ok = r2.returncode == 0 and os.path.exists(out2) and os.path.getsize(out2) > 100
    print(f"  {'✓' if ok else '✗'} {label:10} ({fname[:30]:30}): {'OK' if ok else 'FAIL'}")
    if not ok:
        err = [l for l in r2.stderr.split('\n') if 'Error' in l or 'No option' in l]
        if err: print(f"      {err[0][:90]}")
