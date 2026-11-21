#!/usr/bin/env python3
"""Test v3.11.6: ONE quote pair — path symlink UNQUOTED + force_style value QUOTED.
Root cause: '=' adalah level-1 special char. force_style value 'Fontsize=18' punya '='.
Tanpa quote, '=' terminate value. Quote lindungi '=' dan ','.
v3.11.0/v3.11.3 (DUA quote) fail karena 9.x merge. v3.11.6 (ONE quote) = no merge."""
import subprocess, os, wave, tempfile, uuid
from PIL import Image

WORK = '/tmp/v3116-test'
os.makedirs(WORK, exist_ok=True)
mp4 = f'{WORK}/input.mp4'
subprocess.run(['ffmpeg','-y','-f','lavfi','-i','testsrc=size=320x240:duration=2','-frames:v','60',mp4], capture_output=True)
mp4_vert = f'{WORK}/input_vert.mp4'
subprocess.run(['ffmpeg','-y','-f','lavfi','-i','testsrc=size=240x320:duration=2','-frames:v','60',mp4_vert], capture_output=True)
logo = f'{WORK}/logo.png'
subprocess.run(['ffmpeg','-y','-f','lavfi','-i','color=c=red:size=100x100:d=1','-frames:v','1',logo], capture_output=True)
def mkwav(p):
    with wave.open(p,'w') as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(48000); w.writeframes(b'\x00\x00'*48000*2)
sfx,dub,env = f'{WORK}/sfx.wav',f'{WORK}/dub.wav',f'{WORK}/env.wav'
for p in [sfx,dub,env]: mkwav(p)

srt_real = f'{WORK}/subtitle.srt'
with open(srt_real,'w') as f:
    f.write("1\n00:00:00,000 --> 00:00:02,000\nTest v3.11.6 one-quote\n\n")
symlink = os.path.join(tempfile.gettempdir(), f'mix_tui_sub_{uuid.uuid4().hex[:8]}.srt')
if os.path.lexists(symlink): os.remove(symlink)
os.symlink(srt_real, symlink)

# force_style value punya '=' (Fontsize=18) DAN ',' — keduanya level-1 special, HARUS quote
force_style = ("Fontsize=18,PrimaryColour=&H00FFFFFF,OutlineColour=&H80000000,"
               "BorderStyle=1,Outline=2,Shadow=1,Alignment=2,MarginV=20,Justify=2")

def run(label, mp4_in, scale_pre, with_logo):
    pre = f"[0:v]{scale_pre}" if scale_pre else "[0:v]"
    # v3.11.6: path UNQUOTED (symlink clean), force_style value QUOTED (one quote pair)
    if with_logo:
        flt = f"{pre}subtitles={symlink}:force_style='{force_style}'[vsub];[4:v]format=rgba,scale=100:100[logo_input];[vsub][logo_input]overlay=main_w-overlay_w-10:10[vout]"
        inputs = [mp4_in, sfx, dub, env, logo]
    else:
        flt = f"{pre}subtitles={symlink}:force_style='{force_style}'[vout]"
        inputs = [mp4_in, sfx, dub, env]
    out = f'{WORK}/out_{label}.mp4'
    cmd = ['ffmpeg','-y'] + sum([['-i',x] for x in inputs], []) + ['-filter_complex',flt,'-map','[vout]','-map','2:a:0','-frames:v','60','-shortest',out]
    r = subprocess.run(cmd, capture_output=True, text=True)
    ok = r.returncode == 0 and os.path.exists(out) and os.path.getsize(out) > 100
    if ok:
        frame = f'{WORK}/fr_{label}.jpg'
        subprocess.run(['ffmpeg','-y','-ss','0.5','-i',out,'-frames:v','1',frame], capture_output=True)
        im = Image.open(frame).convert('RGB'); w,h = im.size
        px = list(im.getdata())
        bottom = [px[i] for i in range(len(px)) if (i//w) > h*0.7]
        white = sum(1 for r,g,b in bottom if r>180 and g>180 and b>180)
        pct = white/len(bottom)*100 if bottom else 0
        print(f"  ✓ {label:30s} subtitle {pct:5.2f}% white")
    else:
        err = [l for l in r.stderr.split('\n') if 'No option' in l or 'Error' in l]
        print(f"  ✗ {label:30s} {err[0][:90] if err else 'unknown'}")

print("=== v3.11.6: ONE quote pair (path UNQUOTED symlink + force_style QUOTED) ===\n")
print(f"  Filter: subtitles={symlink}:force_style='Fontsize=18,...,Justify=2'")
print(f"  (Quote lindungi '=' dan ',' di force_style value. Path symlink clean UNQUOTED.)\n")

scale_none = ''
scale_force = 'scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2:color=black,setsar=1,'
scale_square = 'crop=min(iw\\,ih):min(iw\\,ih):(iw-min(iw\\,ih))/2:(ih-min(iw\\,ih))/2,scale=1080:1080,setsar=1,'

run('B no-scale no-logo', mp4, scale_none, False)
run('B no-scale +logo', mp4, scale_none, True)
run('B force-1080p no-logo', mp4, scale_force, False)
run('B force-1080p +logo', mp4, scale_force, True)
run('B 1:1-square no-logo', mp4_vert, scale_square, False)
run('B 1:1-square +logo', mp4_vert, scale_square, True)

if os.path.lexists(symlink): os.remove(symlink)
print("\n  Symlink cleaned up")
