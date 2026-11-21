#!/usr/bin/env python3
"""Test fix escaping untuk mix-tui subtitle filter.
Root cause: ffmpeg 9.x (Mac) berbeda parsing dgn 7.x (sandbox).
Comma di path SRT (harta, raja) break single-quote pairing di 9.x.
Fix: escape semua filtergraph special chars (\\ : ' , ; [ ])."""
import subprocess, os, wave

WORK = '/tmp/sub-escape-fix'
os.makedirs(WORK, exist_ok=True)

# Setup: dummy MP4 + SRT (comma + ! in name) + logo + 3 WAV
mp4 = f'{WORK}/input.mp4'
subprocess.run(['ffmpeg','-y','-f','lavfi','-i','testsrc=size=320x240:duration=2',
                '-frames:v','30', mp4], capture_output=True)

srt_name = "S2 Kota kecil yang mengaku miskin penuh harta, raja datang diam-diam lalu marah besar!.id.srt"
srt_path = f'{WORK}/{srt_name}'
with open(srt_path, 'w') as f:
    f.write("1\n00:00:00,000 --> 00:00:02,000\nTest subtitle comma path\n\n")

logo = f'{WORK}/logo.png'
subprocess.run(['ffmpeg','-y','-f','lavfi','-i','color=c=red:size=100x100:d=1',
                '-frames:v','1', logo], capture_output=True)

def mkwav(p, dur=2):
    with wave.open(p,'w') as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(48000)
        w.writeframes(b'\x00\x00' * 48000 * dur)
sfx, dub, env = f'{WORK}/sfx.wav', f'{WORK}/dub.wav', f'{WORK}/env.wav'
for p in [sfx, dub, env]: mkwav(p)

force_style = ("Fontsize=18,PrimaryColour=&H00FFFFFF,OutlineColour=&H80000000,"
               "BorderStyle=1,Outline=2,Shadow=1,Alignment=2,MarginV=20,Justify=2")

tw, th = 1080, 1920
scale_pre = (f'scale={tw}:{th}:force_original_aspect_ratio=decrease,'
             f'pad={tw}:{th}:(ow-iw)/2:(oh-ih)/2:color=black,setsar=1,')

def run_filter(label, escape_fn):
    srt_escaped = escape_fn(srt_path)
    subtitle_filter = f"[0:v]{scale_pre}subtitles='{srt_escaped}':force_style='{force_style}'[vsub]"
    logo_chain = f";[4:v]format=rgba,scale=100:100[logo_input];[vsub][logo_input]overlay=main_w-overlay_w-10:10[vout]"
    fc = subtitle_filter + logo_chain
    out = f'{WORK}/out_{label}.mp4'
    cmd = ['ffmpeg','-y','-i',mp4,'-i',sfx,'-i',dub,'-i',env,'-i',logo,
           '-filter_complex', fc, '-map','[vout]','-map','2:a:0',
           '-frames:v','5','-shortest', out]
    r = subprocess.run(cmd, capture_output=True, text=True)
    ok = r.returncode == 0 and os.path.exists(out) and os.path.getsize(out) > 100
    size = os.path.getsize(out) if os.path.exists(out) else 0
    if ok:
        print(f"  ✓ {label}: SUCCESS ({size} bytes)")
    else:
        err = [l for l in r.stderr.split('\n') if 'Error' in l or 'No option' in l or 'Invalid' in l]
        print(f"  ✗ {label}: FAIL ({err[0][:80] if err else 'no error line'})")
    return ok

print("=== Test escaping approaches (full filterchain: scale+subtitles+logo) ===\n")

# A: current mix-tui escaping (escape \ : ' only)
print("Approach A — current mix-tui (escape \\ : '):")
run_filter('A_current',
    lambda p: p.replace('\\','\\\\').replace(':','\\:').replace("'","\\'"))

# B: FIX — escape semua filtergraph special chars + option separator
print("\nApproach B — FIX (escape \\ : ' , ; [ ]):")
run_filter('B_fix',
    lambda p: (p.replace('\\','\\\\').replace(':','\\:').replace("'","\\'")
               .replace(',','\\,').replace(';','\\;').replace('[','\\[').replace(']','\\]')))

# C: escape comma only (isolate apakah comma culprit)
print("\nApproach C — current + escape comma saja:")
run_filter('C_comma_only',
    lambda p: p.replace('\\','\\\\').replace(':','\\:').replace("'","\\'").replace(',','\\,'))

# D: escape all, NO single quote wrap (pure escaping, no quote dependency)
print("\nApproach D — escape all NO wrap (escape space jg):")
def escape_no_wrap(p):
    return (p.replace('\\','\\\\').replace(':','\\:').replace("'","\\'")
            .replace(',','\\,').replace(';','\\;').replace('[','\\[').replace(']','\\]')
            .replace(' ','\\ '))
srt_escaped = escape_no_wrap(srt_path)
fc = f"[0:v]{scale_pre}subtitles={srt_escaped}:force_style='{force_style}'[vsub];[4:v]format=rgba,scale=100:100[logo_input];[vsub][logo_input]overlay=main_w-overlay_w-10:10[vout]"
out = f'{WORK}/out_D.mp4'
r = subprocess.run(['ffmpeg','-y','-i',mp4,'-i',sfx,'-i',dub,'-i',env,'-i',logo,
                    '-filter_complex', fc, '-map','[vout]','-map','2:a:0',
                    '-frames:v','5','-shortest', out], capture_output=True, text=True)
ok = r.returncode == 0 and os.path.exists(out) and os.path.getsize(out) > 100
print(f"  {'✓' if ok else '✗'} D: {'SUCCESS' if ok else 'FAIL'} ({os.path.getsize(out) if os.path.exists(out) else 0} bytes)")
if not ok:
    err = [l for l in r.stderr.split('\n') if 'Error' in l or 'No option' in l]
    for e in err[:2]: print(f"    {e[:100]}")

print("\n=== Verify subtitle ACTUALLY rendered (approach B output, check non-black pixels) ===")
import shutil
out_b = f'{WORK}/out_B_fix.mp4'
if os.path.exists(out_b):
    # extract frame + check if subtitle text present (non-black pixels in bottom area)
    frame = f'{WORK}/frame_B.jpg'
    subprocess.run(['ffmpeg','-y','-ss','0.5','-i',out_b,'-frames:v','1',frame],
                   capture_output=True)
    from PIL import Image
    im = Image.open(frame).convert('RGB')
    px = list(im.getdata())
    # subtitle biasanya putih/kontras di area bawah. Cek non-bg pixels.
    non_bg = sum(1 for r,g,b in px if not (r<30 and g<30 and b<30))
    total = len(px)
    print(f"  Frame B: {im.size}, non-black pixels: {non_bg}/{total} ({non_bg/total*100:.1f}%)")
    print(f"  {'✓ Subtitle rendered (non-black content present)' if non_bg > 100 else '⚠ Mungkin subtitle kosong'}")
