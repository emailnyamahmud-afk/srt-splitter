#!/usr/bin/env python3
"""
manim-shorts-tui.py v0.1 — TUI #17: Shorts infografis (WAV + SRT → manim video).

User workflow:
  cd ~/Dubbing && source venv/bin/activate
  python3 manim-shorts-tui.py

Input:
  1. WAV (dari edge-tts-tui Narration mode, gemini-tts-tui Narration mode,
     atau manual ElevenLabs — TUI nggak peduli sumber, cuma baca file WAV)
  2. SRT (dari whisper-tui #8 output, atau TTS-generated SRT)

Output:
  HDD/manim-shorts/{stem}-shorts.mp4
  (1080x1920 vertical, 30fps, h264, manim animation + WAV audio muxed)
  durasi = durasi WAV (video di-extend untuk match audio)

Fase:
  1. Parse SRT → segments [{start, end, text, duration}]
  2. Generate manim script temp (.py) dengan Scene per segment
     - Background charcoal #1C1C2E (manim signature dark)
     - Text Write animation + hold + FadeOut per segment
     - Adaptive font size (56/40/32 berdasarkan panjang text)
     - Gap handling (wait antar segment non-contiguous)
     - Final wait untuk match WAV duration
  3. Render manim → video-only MP4 (no audio)
  4. Mux video + WAV → final MP4 (ffmpeg, -c:v copy, -c:a aac)
  5. Cleanup temp files

Install:
  pip3 install manim questionary
  brew install cairo pango ffmpeg   # manim system deps (Mac)
  # Opsional (recommended): brew install font-noto-sans  # font default TUI ini

catatan:
  - manim CE 0.22.1+ (community edition). Nggak butuh LaTeX (pakai Text class Pango).
  - Render time ~1.6x realtime (30s video ≈ 50s render di M1).
  - Output vertical 9:16 untuk Shorts/Reels/TikTok.
"""

import os
import sys
import re
import json
import time
import subprocess
import shutil
import tempfile
from pathlib import Path

try:
    import questionary
except ImportError:
    print('\n❌ pip3 install questionary')
    sys.exit(1)

sys.path.insert(0, str(Path(__file__).parent))
from config import ensure_hdd, TTS_DIR, MANIM_SHORTS_DIR, INPUT_DIR

VERSION = 'v0.1'
OUTPUT_W = 1080
OUTPUT_H = 1920
FPS = 30
BG_COLOR = '#1C1C2E'   # manim signature dark charcoal
TEXT_COLOR = 'WHITE'
SCENE_NAME = 'ShortsScene'


# ============================================================
# Helpers (match konten-tui.py pattern)
# ============================================================

def find_ffmpeg():
    path = shutil.which('ffmpeg')
    if path:
        return path
    for loc in ['/usr/local/bin/ffmpeg', '/usr/bin/ffmpeg', '/opt/homebrew/bin/ffmpeg']:
        if os.path.isfile(loc):
            return loc
    print('\n❌ ffmpeg belum terinstall. Install: brew install ffmpeg')
    sys.exit(1)


def find_ffprobe():
    path = shutil.which('ffprobe')
    if path:
        return path
    for loc in ['/usr/local/bin/ffprobe', '/usr/bin/ffprobe', '/opt/homebrew/bin/ffprobe']:
        if os.path.isfile(loc):
            return loc
    print('\n❌ ffprobe belum terinstall. Install: brew install ffmpeg')
    sys.exit(1)


def find_manim():
    path = shutil.which('manim')
    if path:
        return path
    for loc in ['/usr/local/bin/manim', '/usr/bin/manim', '/opt/homebrew/bin/manim',
                os.path.expanduser('~/Dubbing/venv/bin/manim')]:
        if os.path.isfile(loc):
            return loc
    print('\n❌ manim belum terinstall. Install: pip3 install manim')
    print('   System deps (Mac): brew install cairo pango ffmpeg')
    sys.exit(1)


def get_duration(ffprobe, path):
    if not os.path.isfile(path):
        return 0
    result = subprocess.run([
        ffprobe, '-v', 'error', '-show_entries', 'format=duration',
        '-of', 'default=noprint_wrappers=1:nokey=1', path,
    ], capture_output=True, text=True)
    try:
        return float(result.stdout.strip())
    except Exception:
        return 0


def fmt_dur(s):
    if not s:
        return '00:00:00'
    h = int(s // 3600); m = int((s % 3600) // 60); sec = int(s % 60)
    return f'{h:02d}:{m:02d}:{sec:02d}'


def fmt_size(mb):
    if mb < 1024:
        return f'{mb:.1f}MB'
    return f'{mb/1024:.2f}GB'


def clear_screen():
    os.system('clear' if os.name != 'nt' else 'cls')


def print_banner():
    clear_screen()
    print('╔' + '═' * 64 + '╗')
    print(f'║  🎬 Manim Shorts {VERSION} (TUI #17)' + ' ' * 34 + '║')
    print('║  WAV + SRT → Infografis Video (vertical 9:16)      ║')
    print('╚' + '═' * 64 + '╝')
    print()


def select_file(prompt, extensions, search_dirs):
    available = []
    for d in search_dirs:
        if d and Path(d).exists():
            for ext in extensions:
                for f in Path(d).glob(f'*.{ext}'):
                    available.append(str(f))
                for f in Path(d).glob(f'*.{ext.upper()}'):
                    available.append(str(f))
    available = sorted(set(available))
    if not available:
        path = questionary.text(f'{prompt} (ketik path lengkap):').ask()
        return path
    choices = [os.path.basename(f) for f in available] + ['[Ketik path manual]']
    sel = questionary.select(prompt, choices=choices, default=choices[0]).ask()
    if sel == '[Ketik path manual]':
        return questionary.text(f'{prompt} (ketik path lengkap):').ask()
    for f in available:
        if os.path.basename(f) == sel:
            return f
    return sel


# ============================================================
# SRT parser
# ============================================================

def parse_srt_time(ts):
    """Parse SRT timestamp 'HH:MM:SS,mmm' → seconds (float)."""
    ts = ts.strip()
    m = re.match(r'(\d+):(\d+):(\d+)[,.](\d+)', ts)
    if not m:
        raise ValueError(f'Format waktu SRT gak valid: {ts}')
    h, mi, s, ms = int(m.group(1)), int(m.group(2)), int(m.group(3)), int(m.group(4))
    return h * 3600 + mi * 60 + s + ms / 1000.0


def parse_srt(srt_path):
    """Parse SRT file → list of {start, end, text, duration}.

    Standard SRT format:
      1
      00:00:00,000 --> 00:00:02,500
      Halo selamat datang

      2
      ...
    """
    with open(srt_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # Normalize line endings, split by blank lines into blocks
    content = content.replace('\r\n', '\n').replace('\r', '\n')
    blocks = re.split(r'\n\s*\n', content.strip())

    segments = []
    for block in blocks:
        lines = [ln for ln in block.split('\n') if ln.strip()]
        if len(lines) < 2:
            continue
        # Find the timestamp line (contains -->)
        ts_line = None
        ts_idx = -1
        for i, ln in enumerate(lines):
            if '-->' in ln:
                ts_line = ln
                ts_idx = i
                break
        if not ts_line:
            continue
        parts = ts_line.split('-->')
        if len(parts) != 2:
            continue
        try:
            start = parse_srt_time(parts[0])
            end = parse_srt_time(parts[1])
        except ValueError:
            continue
        if end <= start:
            continue
        # Text = lines after timestamp line
        text_lines = lines[ts_idx + 1:]
        text = ' '.join(text_lines).strip()
        if not text:
            continue
        segments.append({
            'start': round(start, 3),
            'end': round(end, 3),
            'text': text,
            'duration': round(end - start, 3),
        })

    if not segments:
        raise ValueError('SRT kosong atau gak ada segment valid')
    return segments


# ============================================================
# Manim script generator
# ============================================================

MANIM_SCRIPT_TEMPLATE = '''#!/usr/bin/env python3
"""Auto-generated by manim-shorts-tui.py — jangan edit manual."""
from manim import Scene, Text, FadeIn, FadeOut, ORIGIN, config, WHITE, YELLOW, Transform

config.pixel_width = {W}
config.pixel_height = {H}
config.frame_rate = {FPS}
config.background_color = "{BG}"

SEGMENTS = {SEGMENTS_REPR}
WAV_DURATION = {WAV_DURATION}


def wrap_text(s, max_chars):
    """Wrap text ke multiple lines, max max_chars per line. Return list of lines."""
    words = s.split()
    lines = []
    line = ""
    for w in words:
        if line and len(line) + 1 + len(w) <= max_chars:
            line += " " + w
        elif not line:
            line = w
        else:
            lines.append(line)
            line = w
    if line:
        lines.append(line)
    return lines


class {SCENE_NAME}(Scene):
    def construct(self):
        current = 0.0
        for seg in SEGMENTS:
            # Gap sebelum segment (silence antar cue)
            gap = seg["start"] - current
            if gap > 0.05:
                self.wait(gap)
                current = seg["start"]

            dur = seg["duration"]
            text_str = seg["text"]

            # Wrap text agar fit width (hindari clipping kiri/kanan)
            # Coba font 56 dgn max 22 chars/line; kalau >3 lines, turun ke 40 dgn max 30
            lines = wrap_text(text_str, 22)
            if len(lines) <= 2:
                fs = 56
            elif len(lines) <= 3:
                fs = 48
                lines = wrap_text(text_str, 26)
            else:
                fs = 40
                lines = wrap_text(text_str, 30)

            wrapped = "\\n".join(lines)
            text = Text(wrapped, font="Noto Sans", font_size=fs, color=WHITE,
                        line_spacing=1.3)
            text.move_to(ORIGIN)

            # FadeIn whole text (fast) — full text visible immediately (BUKAN Write stroke-by-stroke)
            fadein_t = min(0.3, dur * 0.1)
            fadeout_t = min(0.2, dur * 0.08)
            highlight_dur = max(0.0, dur - fadein_t - fadeout_t)

            self.play(FadeIn(text), run_time=fadein_t)

            # Word-by-word highlight via t2c + Transform
            # Text full tetap visible (all white), highlight berpindah per kata
            # Catatan: manim CE Text (Pango SVG) set_color di submobject/slice NGGAK jalan,
            # harus pakai t2c parameter (text-to-color) + Transform antar coloring
            seg_words = wrapped.split()
            num_w = len(seg_words)
            if num_w > 0 and highlight_dur > 0.3:
                per_word = min(highlight_dur / num_w, 1.5)
                for word in seg_words:
                    t_next = Text(wrapped, font="Noto Sans", font_size=fs, color=WHITE,
                                  line_spacing=1.3, t2c={{word: YELLOW}})
                    t_next.move_to(ORIGIN)
                    self.play(Transform(text, t_next), run_time=per_word)
                used = per_word * num_w
                remaining = highlight_dur - used
                if remaining > 0.1:
                    self.wait(remaining)
            elif highlight_dur > 0.05:
                self.wait(highlight_dur)

            self.play(FadeOut(text), run_time=fadeout_t)
            current = seg["end"]

        # Extend video untuk match WAV duration (kalau ada tail silence)
        tail = WAV_DURATION - current
        if tail > 0.1:
            self.wait(tail)
'''


def generate_manim_script(segments, wav_duration, output_path):
    """Generate manim Python script dengan SEGMENTS + WAV_DURATION baked in."""
    # Build segments repr (list of dict) — safe escaping via repr
    segs_repr = '[' + ',\n    '.join(repr(s) for s in segments) + '\n]'
    script = MANIM_SCRIPT_TEMPLATE.format(
        W=OUTPUT_W,
        H=OUTPUT_H,
        FPS=FPS,
        BG=BG_COLOR,
        SEGMENTS_REPR=segs_repr,
        WAV_DURATION=round(wav_duration, 3),
        SCENE_NAME=SCENE_NAME,
    )
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(script)
    return output_path


# ============================================================
# Render + mux
# ============================================================

def render_manim(manim_bin, script_path, media_dir):
    """Render manim script → return path to output MP4 (or None on failure).

    manim CLI: manim --disable_caching --media_dir {dir} --format mp4 {script} {scene}
    Output: {media_dir}/videos/{script_stem}/{quality}/{scene}.mp4
    """
    cmd = [
        manim_bin,
        '--disable_caching',
        '--media_dir', str(media_dir),
        '--format', 'mp4',
        str(script_path),
        SCENE_NAME,
    ]
    print(f'  Render manim: {" ".join(cmd[:3])} ... {SCENE_NAME}')
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    except subprocess.TimeoutExpired:
        print('  ❌ manim render timeout (>10 menit)')
        return None
    except FileNotFoundError:
        print('  ❌ manim binary gak ditemukan')
        return None

    if result.returncode != 0:
        print('  ❌ manim render gagal')
        stderr_tail = result.stderr.strip().split('\n')[-15:] if result.stderr else []
        for line in stderr_tail:
            print(f'     {line}')
        return None

    # Find output MP4 — glob media_dir/videos/**/*.mp4, exclude partial_movie_files
    candidates = []
    for mp4 in Path(media_dir).rglob('*.mp4'):
        if 'partial_movie_files' in str(mp4):
            continue
        candidates.append(str(mp4))

    if not candidates:
        print('  ❌ manim output MP4 gak ditemukan')
        # Show last stdout lines for debug
        stdout_tail = result.stdout.strip().split('\n')[-10:] if result.stdout else []
        for line in stdout_tail:
            print(f'     {line}')
        return None

    # Pick the one named after SCENE_NAME if multiple
    scene_mp4 = None
    for c in candidates:
        if Path(c).stem == SCENE_NAME:
            scene_mp4 = c
            break
    return scene_mp4 or candidates[0]


def mux_audio_video(ffmpeg, video_path, wav_path, output_path):
    """Mux video (no audio) + WAV → final MP4. Video stream copy, audio aac."""
    cmd = [
        ffmpeg, '-y',
        '-i', video_path,
        '-i', wav_path,
        '-c:v', 'copy',
        '-c:a', 'aac', '-b:a', '192k', '-ar', '48000', '-ac', '2',
        '-movflags', '+faststart',
        '-shortest',
        output_path,
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    except subprocess.TimeoutExpired:
        print('  ❌ mux timeout')
        return False
    if result.returncode != 0:
        print('  ❌ mux gagal')
        print(f'     {result.stderr.strip().split(chr(10))[-5:]}')
        return False
    return os.path.exists(output_path)


# ============================================================
# Main
# ============================================================

def main():
    print_banner()

    if not ensure_hdd():
        return

    ffmpeg = find_ffmpeg()
    ffprobe = find_ffprobe()
    manim_bin = find_manim()

    print(f'  Output : {MANIM_SHORTS_DIR}')
    print(f'  Format : {OUTPUT_W}x{OUTPUT_H} (vertical 9:16), {FPS}fps')
    print(f'  Style  : manim (charcoal bg, Write animation)')
    print()

    # Step 1: Pilih WAV
    print('▶ Step 1: Pilih WAV (narasi)')
    wav_path = select_file('WAV narasi:', ['wav'], [str(TTS_DIR), str(INPUT_DIR), os.getcwd()])
    if not wav_path or not os.path.isfile(wav_path):
        print(f'  ❌ File gak ditemukan: {wav_path}')
        return
    wav_dur = get_duration(ffprobe, wav_path)
    print(f'  ✓ {os.path.basename(wav_path)} ({fmt_dur(wav_dur)})')
    print()

    # Step 2: Pilih SRT
    print('▶ Step 2: Pilih SRT (timed text)')
    srt_path = select_file('SRT:', ['srt'], [str(INPUT_DIR), str(TTS_DIR), os.getcwd()])
    if not srt_path or not os.path.isfile(srt_path):
        print(f'  ❌ File gak ditemukan: {srt_path}')
        return
    try:
        segments = parse_srt(srt_path)
    except ValueError as e:
        print(f'  ❌ {e}')
        return
    total_seg_dur = sum(s['duration'] for s in segments)
    srt_end = segments[-1]['end']
    print(f'  ✓ {os.path.basename(srt_path)} ({len(segments)} segments, last cue end {fmt_dur(srt_end)})')
    print()

    # Step 3: Preview + sanity check
    print('▶ Step 3: Preview segments')
    print(f'  {"#":<4} {"Start":<10} {"End":<10} {"Dur":<8} {"Text (truncated)":<40}')
    print(f'  {"-"*4} {"-"*10} {"-"*10} {"-"*8} {"-"*40}')
    for i, seg in enumerate(segments[:10], 1):
        txt = seg['text'][:37] + '...' if len(seg['text']) > 40 else seg['text']
        print(f'  {i:<4} {fmt_dur(seg["start"]):<10} {fmt_dur(seg["end"]):<10} {seg["duration"]:<8.1f} {txt}')
    if len(segments) > 10:
        print(f'  ... dan {len(segments) - 10} segment lainnya')
    print()

    # Sanity: SRT total vs WAV duration
    if abs(srt_end - wav_dur) > 5:
        print(f'  ⚠ SRT end ({fmt_dur(srt_end)}) vs WAV dur ({fmt_dur(wav_dur)}) beda jauh!')
        print(f'    Video akan di-extend ke {fmt_dur(wav_dur)} (match WAV).')
    print()

    # Step 4: Output path
    wav_stem = Path(wav_path).stem
    default_output = str(MANIM_SHORTS_DIR / f'{wav_stem}-shorts.mp4')
    print('▶ Step 4: Output path')
    output = questionary.text('Output path (Enter untuk default):', default=default_output).ask()
    if not output or not output.strip():
        output = default_output
    else:
        output = os.path.expanduser(output.strip())
    parent = os.path.dirname(output)
    if parent and not os.path.exists(parent):
        os.makedirs(parent, exist_ok=True)
    print(f'  ✓ {output}')
    print()

    # Step 5: Konfirmasi
    print('═' * 64)
    print('▶ Konfirmasi')
    print('═' * 64)
    print(f'\n  WAV      : {os.path.basename(wav_path)} ({fmt_dur(wav_dur)})')
    print(f'  SRT      : {os.path.basename(srt_path)} ({len(segments)} segments)')
    print(f'  Output   : {output}')
    print(f'  Format   : {OUTPUT_W}x{OUTPUT_H} vertical, {FPS}fps')
    print(f'  Style    : manim Write animation, charcoal bg')
    print(f'  Est. render: ~{int(wav_dur * 1.6)}s (1.6x realtime)')

    if not questionary.confirm('\nLanjut render?', default=True).ask():
        print('Dibatalkan.')
        return

    # Temp dir di HDD parent (besar, cepat)
    temp_dir_parent = MANIM_SHORTS_DIR.parent / '.manim_shorts_tmp'
    temp_dir_parent.mkdir(parents=True, exist_ok=True)
    temp_dir = tempfile.mkdtemp(prefix='manim_shorts_', dir=str(temp_dir_parent))
    media_dir = Path(temp_dir) / 'media'
    script_path = os.path.join(temp_dir, 'scene_script.py')

    # ============================================================
    # Fase 1: Generate manim script
    # ============================================================
    print('\n' + '═' * 64)
    print('▶ Fase 1: Generate manim script')
    print('═' * 64)
    try:
        generate_manim_script(segments, wav_dur, script_path)
        print(f'  ✓ {os.path.basename(script_path)} ({len(segments)} segments baked in)')
    except Exception as e:
        print(f'  ❌ Generate script gagal: {e}')
        shutil.rmtree(temp_dir, ignore_errors=True)
        return
    print()

    # ============================================================
    # Fase 2: Render manim → video-only MP4
    # ============================================================
    print('▶ Fase 2: Render manim (video-only)')
    print('═' * 64)
    t0 = time.time()
    video_mp4 = render_manim(manim_bin, script_path, media_dir)
    render_time = time.time() - t0
    if not video_mp4:
        print(f'\n  ❌ Render gagal (setelah {fmt_dur(render_time)})')
        shutil.rmtree(temp_dir, ignore_errors=True)
        return
    video_dur = get_duration(ffprobe, video_mp4)
    video_size_mb = os.path.getsize(video_mp4) / 1024 / 1024
    print(f'\n  ✓ {os.path.basename(video_mp4)} ({fmt_size(video_size_mb)}, {fmt_dur(video_dur)}, render {fmt_dur(render_time)})')
    print()

    # ============================================================
    # Fase 3: Mux video + WAV → final MP4
    # ============================================================
    print('▶ Fase 3: Mux video + WAV → final MP4')
    print('═' * 64)
    if not mux_audio_video(ffmpeg, video_mp4, wav_path, output):
        print('\n  ❌ Mux gagal')
        shutil.rmtree(temp_dir, ignore_errors=True)
        return
    print(f'  ✓ {os.path.basename(output)}')
    print()

    # ============================================================
    # Cleanup temp
    # ============================================================
    print('▶ Cleanup temp files...')
    shutil.rmtree(temp_dir, ignore_errors=True)
    print('  ✓ temp dir dibersihkan')
    print()

    # ============================================================
    # Hasil
    # ============================================================
    if os.path.exists(output):
        size_mb = os.path.getsize(output) / 1024 / 1024
        out_dur = get_duration(ffprobe, output)
        print('═' * 64)
        print(f'\n📁 Output: {os.path.basename(output)} ({fmt_size(size_mb)})')
        print(f'   Path   : {output}')
        print(f'   Durasi : {fmt_dur(out_dur)}')
        print(f'   Res    : {OUTPUT_W}x{OUTPUT_H} (vertical 9:16)')
        print(f'   Segments: {len(segments)} (manim Write animation)')
        print(f'   Render : {fmt_dur(render_time)} ({render_time/max(out_dur,1):.1f}x realtime)')
        print(f'\n🎬 VLC test:')
        print(f'   - Play dari awal → text Write animation per cue')
        print(f'   - Cek audio sync → narasi cocok visual text')
        print(f'   - Cek transisi → FadeOut antar cue (mulus)')
    else:
        print('\n  ❌ Output gak ditemukan')
    print('═' * 64)


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print('\n⏹ Dibatalkan.')
        sys.exit(130)
    except Exception as e:
        print(f'\n❌ {e}', file=sys.stderr)
        import traceback
        print(f'\n{traceback.format_exc()[:500]}', file=sys.stderr)
        sys.exit(1)
