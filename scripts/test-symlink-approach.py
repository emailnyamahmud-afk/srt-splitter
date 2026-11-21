#!/usr/bin/env python3
"""Test symlink approach: bypass escaping issue entirely.
Buat symlink /tmp/mix_sub_{rand}.srt → SRT path asli (comma, !, etc).
Filter pakai symlink path (clean, no special char) → no escaping needed.
Test dengan full filterchain mirror user case."""
import subprocess, os, wave, tempfile, uuid
from PIL import Image

WORK = '/tmp/symlink-test'
os.makedirs(WORK, exist_ok=True)

mp4 = f'{WORK}/input.mp4'
subprocess.run(['ffmpeg','-y','-f','lavfi','-i','testsrc=size=320x240:duration=2','-frames:v','60',mp4], capture_output=True)
logo = f'{WORK}/logo.png'
subprocess.run(['ffmpeg','-y','-f','lavfi','-i','color=c=red:size=100x100:d=1','-frames:v','1',logo], capture_output=True)
def mkwav(p):
    with wave.open(p,'w') as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(48000); w.writeframes(b'\x00\x00'*48000*2)
sfx,dub,env = f'{WORK}/sfx.wav',f'{WORK}/dub.wav',f'{WORK}/env.wav'
for p in [sfx,dub,env]: mkwav(p)

# SRT path dengan comma + ! (mirror user case)
srt_name = "S1 Kota kecil yang mengaku miskin penuh harta, raja datang diam-diam lalu marah besar!.id.srt"
srt_path = f'{WORK}/{srt_name}'
with open(srt_path,'w') as f:
    f.write("1\n00:00:00,000 --> 00:00:02,000\nTest subtitle symlink approach\n\n")

force_style = ("Fontsize=18,PrimaryColour=&H00FFFFFF,OutlineColour=&H80000000,"
               "BorderStyle=1,Outline=2,Shadow=1,Alignment=2,MarginV=20,Justify=2")
tw,th = 1080,1920
scale_pre = (f'scale={tw}:{th}:force_original_aspect_ratio=decrease,'
             f'pad={tw}:{th}:(ow-iw)/2:(oh-ih)/2:color=black,setsar=1,')

# === SYMLINK APPROACH ===
# Buat symlink dengan nama clean (no special char) → SRT path asli
tmpdir = tempfile.gettempdir()
symlink_path = os.path.join(tmpdir, f'mix_tui_sub_{uuid.uuid4().hex[:8]}.srt')
print(f"=== Symlink approach ===")
print(f"  SRT asli: {srt_path}")
print(f"  Symlink : {symlink_path}")

# Buat symlink (overwrite kalau ada)
if os.path.lexists(symlink_path):
    os.remove(symlink_path)
os.symlink(srt_path, symlink_path)
print(f"  Symlink created: {os.path.lexists(symlink_path)}")

# Verify symlink resolve ke SRT asli
resolved = os.path.realpath(symlink_path)
print(f"  Resolved: {resolved}")
print(f"  Symlink readable: {os.access(symlink_path, os.R_OK)}")

# Filter pakai symlink path — NO escaping needed (path clean, no special char)
# Path: /tmp/mix_tui_sub_xxxxxxxx.srt — cuma huruf, angka, slash, dot, underscore
subtitle_filter = f"[0:v]{scale_pre}subtitles='{symlink_path}':force_style='{force_style}'[vsub]"
logo_chain = f";[4:v]format=rgba,scale=100:100[logo_input];[vsub][logo_input]overlay=main_w-overlay_w-10:10[vout]"
fc = subtitle_filter + logo_chain

print(f"\n  Filter path: subtitles='{symlink_path}':force_style='...'")
print(f"  (clean path, no comma/!/special char — single-quote safe)")

out = f'{WORK}/out_symlink.mp4'
cmd = ['ffmpeg','-y','-i',mp4,'-i',sfx,'-i',dub,'-i',env,'-i',logo,
       '-filter_complex', fc, '-map','[vout]','-map','2:a:0',
       '-frames:v','60','-shortest', out]
r = subprocess.run(cmd, capture_output=True, text=True)
if r.returncode == 0 and os.path.exists(out):
    print(f"\n  ✓ Render SUCCESS ({os.path.getsize(out)} bytes)")
    # verify subtitle
    frame = f'{WORK}/frame.jpg'
    subprocess.run(['ffmpeg','-y','-ss','0.5','-i',out,'-frames:v','1',frame], capture_output=True)
    if os.path.exists(frame):
        im = Image.open(frame).convert('RGB')
        w,h = im.size
        px = list(im.getdata())
        bottom = [px[i] for i in range(len(px)) if (i//w) > h*0.7]
        white = sum(1 for r,g,b in bottom if r>180 and g>180 and b>180)
        print(f"  ✓ Subtitle rendered: {white} white pixels ({white/len(bottom)*100:.2f}%)")
else:
    err = [l for l in r.stderr.split('\n') if 'Error' in l or 'No option' in l]
    print(f"\n  ✗ FAIL: {err[0][:100] if err else 'unknown'}")

# Cleanup symlink
if os.path.lexists(symlink_path):
    os.remove(symlink_path)
    print(f"  Symlink cleaned up")
