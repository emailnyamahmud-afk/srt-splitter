#!/usr/bin/env python3
"""mix-audiobook-tui.py v0.1 — Audiobook MP4 generator (TUI #21)

Text/WAV + thumbnail → MP4 dengan Ken Burns effect + burn subtitle.

3 Mode auto-detect per bab:
- Mode A (text→full): .txt/.md ada, .wav absent → supertonic TTS → WAV → whisper SRT → render
- Mode B (WAV→render): .wav ada, .srt absent → whisper SRT → render
- Mode C (ready): .wav + .srt ada → langsung render

Input:  HDD/input/audiobook/{judul}/season-N/S1_B001.{txt,md,wav,jpg,srt}
Output: HDD/audiobook/{judul}/season-N/S1_B001.mp4

Backend:
- supertonic (TTS lokal, deterministic, M5 voice default) — pip install supertonic
- whisper-cli (SRT gen, whisper.cpp Metal GPU) — brew install whisper.cpp
- ffmpeg (render: zoompan Ken Burns + subtitles burn + loudnorm -16 LUFS)

Resolution: auto-detect thumbnail aspect → vertical 1080x1920 / horizontal 1920x1080 / square 1080x1080
(default vertical, HP-friendly untuk YouTube)

Estimasi per bab 15 menit: supertonic ~11s + whisper ~3min + ffmpeg ~5min ≈ 8 menit
"""

import os
import sys
import re
import io
import wave
import subprocess
import shutil
import argparse
import time
import glob

try:
    import questionary
except ImportError:
    print('❌ questionary tidak terinstall. Install: pip install questionary')
    sys.exit(1)

try:
    from config import ensure_hdd, AUDIOBOOK_INPUT_DIR, AUDIOBOOK_DIR
except ImportError:
    print('❌ config.py tidak ditemukan. Pastikan config.py di folder yg sama.')
    sys.exit(1)


# ============================================================
# Constants
# ============================================================

NARR_SAMPLE_RATE = 48000      # supertonic narration output (stereo, project standard)
NARR_CHANNELS = 2
SUPERTONIC_NATIVE_SR = 44100  # supertonic native (resample ke 48kHz)
DEFAULT_VOICE = 'M5'          # laki netral (user pick Q4)
DEFAULT_STEPS = 8
DEFAULT_SPEED = 1.05
LUFS_TARGET = -16             # YouTube loudness target (user pick Q5)
RENDER_FPS = 30
MAX_CHUNK_CHARS = 1500        # supertonic per-call text limit safety
CROSSFADE_MS = 50             # antar chunk WAV

# Resolution map (auto-detect from thumbnail aspect)
RES_VERTICAL = (1080, 1920, 'vertical')
RES_HORIZONTAL = (1920, 1080, 'horizontal')
RES_SQUARE = (1080, 1080, 'square')


# ============================================================
# Helpers
# ============================================================

def clear_screen():
    os.system('cls' if os.name == 'nt' else 'clear')


def print_banner():
    print('╔' + '═' * 62 + '╗')
    print('║  📚 Mix Audiobook TUI v0.1 — Audiobook MP4 generator          ║')
    print('║  text/WAV + thumbnail → MP4 + Ken Burns + subtitle burn        ║')
    print('╚' + '═' * 62 + '╝')


def format_duration(seconds):
    if seconds < 60:
        return f'{seconds:.1f}s'
    m = int(seconds // 60)
    s = int(seconds % 60)
    if m < 60:
        return f'{m}m{s}s'
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    return f'{h}j{m}m{s}s'


def get_audio_duration(path):
    """ffprobe audio duration in seconds."""
    try:
        result = subprocess.run(
            ['ffprobe', '-v', 'error', '-show_entries', 'format=duration',
             '-of', 'default=noprint_wrappers=1:nokey=1', path],
            capture_output=True, text=True, timeout=30)
        return float(result.stdout.strip())
    except Exception:
        return 0.0


def find_whisper_cli():
    """Cari whisper-cli binary (mirror whisper-tui pattern)."""
    path = shutil.which('whisper-cli')
    if path:
        return path
    for loc in ['/opt/homebrew/bin/whisper-cli', '/usr/local/bin/whisper-cli']:
        if os.path.isfile(loc):
            return loc
    return None


def find_whisper_model():
    """Cari ggml model whisper.cpp (prefer large > medium > small > tiny)."""
    search_dirs = [
        os.path.expanduser('~/.cache/whisper'),
        os.path.expanduser('~/.cache/whisper.cpp'),
        '/Volumes/HDD/Dubbing/whisper-models',
        os.path.expanduser('~/Dubbing/whisper-models'),
    ]
    candidates = []
    for d in search_dirs:
        if os.path.isdir(d):
            candidates.extend(glob.glob(os.path.join(d, 'ggml-*.bin')))
            candidates.extend(glob.glob(os.path.join(d, '*.bin')))
    candidates = list(dict.fromkeys(candidates))  # dedup preserve order

    def size_rank(p):
        n = os.path.basename(p).lower()
        for i, s in enumerate(['large', 'medium', 'small', 'base', 'tiny']):
            if s in n:
                return i
        return 99

    candidates.sort(key=size_rank)
    return candidates[0] if candidates else None


def resample_audio(audio, src_sr, target_sr):
    """Resample float32 array src_sr → target_sr (linear interpolation, numpy)."""
    if src_sr == target_sr or len(audio) == 0:
        return audio
    try:
        import numpy as np
    except ImportError:
        return audio
    n_src = len(audio)
    n_tgt = int(n_src * target_sr / src_sr)
    if n_tgt <= 0:
        return np.zeros(0, dtype=np.float32)
    idx = np.linspace(0, n_src - 1, n_tgt)
    i0 = idx.astype(np.int32)
    i1 = np.minimum(i0 + 1, n_src - 1)
    frac = (idx - i0).astype(np.float32)
    out = audio[i0] * (1 - frac) + audio[i1] * frac
    return out.astype(np.float32)


def encode_wav(audio, sample_rate, channels, output_path):
    """Encode float32 array → WAV (16-bit PCM). audio shape: (samples,) mono or (samples,2) stereo."""
    try:
        import numpy as np
    except ImportError:
        print('❌ numpy tidak terinstall')
        return False
    audio = np.clip(audio, -1.0, 1.0)
    if channels == 2 and audio.ndim == 1:
        audio = np.stack([audio, audio], axis=1)
    pcm = (audio * 32767).astype(np.int16)
    buf = io.BytesIO()
    with wave.open(buf, 'wb') as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(pcm.tobytes())
    with open(output_path, 'wb') as f:
        f.write(buf.getvalue())
    return True


# ============================================================
# Markdown preprocessing → plain text untuk TTS
# ============================================================

def strip_markdown(content):
    """Convert markdown → plain text untuk TTS.
    - Strip YAML frontmatter (--- ... ---)
    - Strip heading # markers (keep text, replace · → ,)
    - Strip blockquote > markers (keep text)
    - Strip HR --- lines
    - Strip markdown link/image/bold/italic/code syntax
    - Preserve paragraph breaks (\\n\\n) sebagai pause cue
    Returns: plain text string.
    """
    # 1. Strip YAML frontmatter (--- ... ---)
    if content.lstrip().startswith('---'):
        content_l = content.lstrip()
        end = content_l.find('\n---', 3)
        if end != -1:
            content = content_l[end + 4:].lstrip()

    # 2. Strip HR lines (--- or *** or ___ alone on a line)
    content = re.sub(r'^[\-\*_]{3,}\s*$', '', content, flags=re.MULTILINE)

    # 3. Strip heading markers: # ## ### → keep text, replace · with ,
    def heading_repl(m):
        text = m.group(1).strip()
        text = text.replace('·', ',').replace('•', ',')
        return text
    content = re.sub(r'^#{1,6}\s+(.+)$', heading_repl, content, flags=re.MULTILINE)

    # 4. Strip blockquote markers
    content = re.sub(r'^>\s?', '', content, flags=re.MULTILINE)

    # 5. Strip images ![alt](url) → remove entirely
    content = re.sub(r'!\[[^\]]*\]\([^)]+\)', '', content)

    # 6. Strip markdown links [text](url) → text
    content = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', content)

    # 7. Strip bold/italic/code markers
    content = re.sub(r'\*\*([^*]+)\*\*', r'\1', content)
    content = re.sub(r'__([^_]+)__', r'\1', content)
    content = re.sub(r'(?<!\*)\*([^*]+)\*(?!\*)', r'\1', content)
    content = re.sub(r'`([^`]+)`', r'\1', content)

    # 8. Collapse 3+ newlines → 2 (paragraph break)
    content = re.sub(r'\n{3,}', '\n\n', content)

    return content.strip()


def chunk_paragraphs(text, max_chars=MAX_CHUNK_CHARS):
    """Split text jadi chunks per paragraph, merge short paragraphs sampai ~max_chars.
    Paragraph terlalu panjang → split per kalimat. Returns list of strings.
    """
    paragraphs = [p.strip() for p in text.split('\n\n') if p.strip()]
    chunks = []
    current = ''
    for p in paragraphs:
        if len(p) > max_chars:
            # paragraph too long — split by sentences
            if current:
                chunks.append(current)
                current = ''
            sentences = re.split(r'(?<=[.!?。！？])\s+', p)
            sbuf = ''
            for s in sentences:
                if len(sbuf) + len(s) + 1 > max_chars and sbuf:
                    chunks.append(sbuf)
                    sbuf = s
                else:
                    sbuf = (sbuf + ' ' + s).strip() if sbuf else s
            if sbuf:
                chunks.append(sbuf)
        elif len(current) + len(p) + 2 > max_chars and current:
            chunks.append(current)
            current = p
        else:
            current = (current + '\n\n' + p).strip() if current else p
    if current:
        chunks.append(current)
    return chunks


# ============================================================
# Thumbnail aspect detection
# ============================================================

def detect_thumb_resolution(thumb_path):
    """Baca aspect ratio thumbnail → return (w, h, orientation).
    vertical (h>w*1.1) → 1080x1920, horizontal (w>h*1.1) → 1920x1080, else square 1080x1080.
    Fallback vertical kalau PIL gagal.
    """
    try:
        from PIL import Image
        im = Image.open(thumb_path)
        w, h = im.size
        im.close()
    except Exception as e:
        print(f'  ⚠ Thumbnail tidak terbaca ({e}), default vertical 1080x1920')
        return RES_VERTICAL
    if h > w * 1.1:
        return RES_VERTICAL
    elif w > h * 1.1:
        return RES_HORIZONTAL
    else:
        return RES_SQUARE


# ============================================================
# Supertonic WAV generation (Narration mode)
# ============================================================

def generate_wav_supertonic(text, voice, out_wav, lang='id'):
    """Generate WAV via supertonic Narration mode.
    Chunk per paragraph → synthesize per chunk → concat w/ crossfade → resample 48kHz stereo → encode.
    Returns: (duration_sec, True) or (0, False) on failure.
    """
    try:
        from supertonic import TTS as SupertonicTTS
        import numpy as np
    except ImportError as e:
        print(f'  ❌ supertonic/numpy tidak terinstall: {e}')
        print('     Install: pip install supertonic numpy')
        return (0, False)

    chunks = chunk_paragraphs(text, max_chars=MAX_CHUNK_CHARS)
    if not chunks:
        print('  ❌ Text kosong setelah strip markdown')
        return (0, False)

    print(f'  Load supertonic model (first run download ~400MB, cached)...')
    try:
        tts = SupertonicTTS(auto_download=True)
        style = tts.get_voice_style(voice)
    except Exception as e:
        print(f'  ❌ supertonic load gagal: {e}')
        return (0, False)

    all_audio = []  # list of float32 mono arrays at SUPERTONIC_NATIVE_SR
    total_dur = 0.0
    for i, chunk in enumerate(chunks):
        try:
            # Mirror supertonic-tts-tui proven signature: verbose=False, NO silence_duration
            wav, dur = tts.synthesize(
                text=chunk, voice_style=style, total_steps=DEFAULT_STEPS,
                speed=DEFAULT_SPEED, lang=lang, verbose=False)
            # wav = np.ndarray mono float32 at SUPERTONIC_NATIVE_SR. dur = np.ndarray (BUKAN float).
            if wav is None or len(wav) == 0:
                continue
            audio_arr = wav
            if isinstance(audio_arr, list):
                audio_arr = np.array(audio_arr, dtype=np.float32)
            # Squeeze dims → mono 1D (mirror generate_cue_audio)
            if audio_arr.ndim > 1:
                audio_arr = audio_arr.squeeze()
                if audio_arr.ndim > 1:
                    audio_arr = audio_arr[0] if isinstance(audio_arr[0], np.ndarray) else audio_arr
            audio_arr = audio_arr.astype(np.float32)
            all_audio.append(audio_arr)
            # dur is np.ndarray → squeeze to scalar then float (avoid "only 0-dim" error)
            dur_f = float(np.squeeze(dur)) if hasattr(dur, 'shape') else float(dur)
            total_dur += dur_f
            print(f'  [{i + 1}/{len(chunks)}] {dur_f:.1f}s')
        except Exception as e:
            print(f'  ⚠ Chunk {i + 1} gagal: {e}')
            continue

    if not all_audio:
        return (0, False)

    # concat with crossfade (CROSSFADE_MS)
    crossfade_samples = int(SUPERTONIC_NATIVE_SR * CROSSFADE_MS / 1000)
    final = all_audio[0]
    for nxt in all_audio[1:]:
        if len(final) >= crossfade_samples and len(nxt) >= crossfade_samples:
            fade_out = np.linspace(1, 0, crossfade_samples, dtype=np.float32)
            fade_in = np.linspace(0, 1, crossfade_samples, dtype=np.float32)
            tail = final[-crossfade_samples:] * fade_out
            head = nxt[:crossfade_samples] * fade_in
            final = np.concatenate([final[:-crossfade_samples], tail + head, nxt[crossfade_samples:]])
        else:
            final = np.concatenate([final, nxt])

    # resample native → 48kHz
    if SUPERTONIC_NATIVE_SR != NARR_SAMPLE_RATE:
        final = resample_audio(final, SUPERTONIC_NATIVE_SR, NARR_SAMPLE_RATE)

    # encode WAV 48kHz stereo 16-bit
    ok = encode_wav(final, NARR_SAMPLE_RATE, NARR_CHANNELS, out_wav)
    if not ok:
        return (0, False)
    return (len(final) / NARR_SAMPLE_RATE, True)


# ============================================================
# Whisper SRT generation (subprocess call whisper-cli)
# ============================================================

def generate_srt_whisper(wav_path, out_srt, lang='id'):
    """Call whisper-cli binary → generate SRT from WAV. Returns True on success."""
    whisper_cli = find_whisper_cli()
    if not whisper_cli:
        print('  ❌ whisper-cli tidak terinstall')
        print('     Install: brew install whisper.cpp')
        return False
    model = find_whisper_model()
    if not model:
        print('  ❌ Model whisper.cpp tidak ditemukan (ggml-*.bin)')
        print('     Download: https://huggingface.co/ggerganog/whisper.cpp')
        print('     Taruh di ~/.cache/whisper/ atau ~/Dubbing/whisper-models/')
        return False

    output_base = out_srt[:-4] if out_srt.endswith('.srt') else out_srt
    cmd = [whisper_cli, '-m', model, '-l', lang, '-f', wav_path,
           '-t', '8', '-osrt', '-of', output_base]
    print(f'  whisper-cli: {os.path.basename(model)} → {os.path.basename(out_srt)}')
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=3600)
        if os.path.isfile(out_srt) and os.path.getsize(out_srt) > 0:
            return True
        print(f'  ⚠ whisper-cli selesai tapi SRT tidak ditemukan')
        if result.stderr:
            print(f'  stderr tail: ...{result.stderr[-300:]}')
        return False
    except subprocess.TimeoutExpired:
        print('  ⚠ whisper-cli timeout (1 jam)')
        return False
    except Exception as e:
        print(f'  ⚠ whisper-cli error: {e}')
        return False


# ============================================================
# Render MP4 (ffmpeg: Ken Burns + burn subtitle + loudnorm)
# ============================================================

def render_mp4(thumb_path, wav_path, srt_path, out_mp4, resolution,
               ken_burns=True, burn_sub=True, lufs=LUFS_TARGET):
    """Render final MP4: thumbnail + Ken Burns + WAV audio + burn subtitle + loudnorm.
    Single ffmpeg run. Returns True on success.
    """
    w, h, orient = resolution
    total_dur = get_audio_duration(wav_path)
    if total_dur <= 0:
        print('  ❌ Tidak bisa baca durasi audio (ffprobe)')
        return False

    total_frames = int(total_dur * RENDER_FPS)

    # Ken Burns: very slow zoom 1.0→1.08 over full duration + slight pan
    if ken_burns and total_frames > 0:
        zoom_step = 0.08 / total_frames
        vf = (
            f"scale={w * 2}:{h * 2}:force_original_aspect_ratio=increase,"
            f"crop={w * 2}:{h * 2},"
            f"zoompan=z='min(zoom+{zoom_step:.10f},1.08)':"
            f"x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':"
            f"d={total_frames}:s={w}x{h}:fps={RENDER_FPS}"
        )
    else:
        vf = f"scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},setsar=1"

    # burn subtitle (libass)
    if burn_sub and srt_path and os.path.isfile(srt_path):
        srt_escaped = srt_path.replace("'", "\\'").replace(":", "\\:")
        force_style = ("FontName=Noto Sans SC,FontSize=22,"
                       "PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,"
                       "BorderStyle=1,Outline=2,Shadow=1,MarginV=40,Alignment=2")
        vf = f"{vf},subtitles='{srt_escaped}':force_style='{force_style}'"

    # loudnorm audio (-16 LUFS YouTube target)
    af = f"loudnorm=I={lufs}:TP=-1.5:LRA=11"

    cmd = [
        'ffmpeg', '-y',
        '-loop', '1', '-i', thumb_path,
        '-i', wav_path,
        '-vf', vf,
        '-af', af,
        '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-r', str(RENDER_FPS),
        '-c:a', 'aac', '-b:a', '192k', '-ar', '48000', '-ac', '2',
        '-shortest',
        out_mp4,
    ]

    print(f'  ffmpeg render: {w}x{h} {orient}, Ken Burns={"on" if ken_burns else "off"}, '
          f'burn_sub={"on" if burn_sub else "off"}, LUFS={lufs}')
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=7200)
        if os.path.isfile(out_mp4) and os.path.getsize(out_mp4) > 0:
            return True
        print(f'  ⚠ ffmpeg selesai tapi output tidak ada')
        if result.stderr:
            print(f'  stderr tail: ...{result.stderr[-500:]}')
        return False
    except subprocess.TimeoutExpired:
        print('  ⚠ ffmpeg timeout (2 jam)')
        return False
    except Exception as e:
        print(f'  ⚠ ffmpeg error: {e}')
        return False


# ============================================================
# Per-bab orchestration
# ============================================================

def detect_bab_mode(stem, input_dir):
    """Detect processing mode per bab berdasarkan file yg ada.
    Mode A: .txt/.md ada, .wav absent → text→full
    Mode B: .wav ada, .srt absent → wav→render (gen SRT)
    Mode C: .wav + .srt ada → ready (skip gen)
    Returns: (mode, files_dict)
    """
    txt = os.path.join(input_dir, stem + '.txt')
    md = os.path.join(input_dir, stem + '.md')
    wav = os.path.join(input_dir, stem + '.wav')
    srt = os.path.join(input_dir, stem + '.srt')
    jpg = os.path.join(input_dir, stem + '.jpg')
    png = os.path.join(input_dir, stem + '.png')

    thumb = jpg if os.path.isfile(jpg) else (png if os.path.isfile(png) else None)
    text_file = txt if os.path.isfile(txt) else (md if os.path.isfile(md) else None)
    has_wav = os.path.isfile(wav)
    has_srt = os.path.isfile(srt)

    if text_file and not has_wav:
        return ('A', {'text': text_file, 'wav': wav, 'srt': srt, 'thumb': thumb})
    elif has_wav and not has_srt:
        return ('B', {'text': text_file, 'wav': wav, 'srt': srt, 'thumb': thumb})
    elif has_wav and has_srt:
        return ('C', {'text': text_file, 'wav': wav, 'srt': srt, 'thumb': thumb})
    else:
        return (None, {})


def process_bab(stem, input_dir, output_dir, voice, ken_burns, burn_sub,
                force_regen_srt, force_regen_wav, lang='id'):
    """Process single bab. Returns True on success."""
    mode, files = detect_bab_mode(stem, input_dir)
    if mode is None:
        print(f'  ❌ {stem}: tidak ada .txt/.md/.wav — skip')
        return False
    if not files.get('thumb'):
        print(f'  ⚠ {stem}: tidak ada thumbnail (.jpg/.png) — skip')
        return False

    print(f'\n▶ {stem} (mode {mode})')

    # Mode A: gen WAV from text (atau force_regen_wav)
    if (mode == 'A' or (force_regen_wav and files.get('text'))):
        if not files.get('text'):
            print(f'  ⚠ {stem}: force_regen_wav tapi tidak ada .txt/.md')
        else:
            with open(files['text'], 'r', encoding='utf-8') as f:
                content = f.read()
            plain = strip_markdown(content)
            if not plain:
                print(f'  ❌ {stem}: text kosong setelah strip markdown')
                return False
            dur, ok = generate_wav_supertonic(plain, voice, files['wav'], lang=lang)
            if not ok:
                print(f'  ❌ {stem}: supertonic gen gagal')
                return False
            print(f'  ✓ WAV: {dur:.1f}s → {os.path.basename(files["wav"])}')

    # gen SRT if absent or force (mode A/B)
    need_srt = (mode in ('A', 'B')) or force_regen_srt
    burn_sub_this = burn_sub
    if need_srt and not os.path.isfile(files['srt']):
        if not os.path.isfile(files['wav']):
            print(f'  ❌ {stem}: WAV tidak ada untuk gen SRT')
            return False
        ok = generate_srt_whisper(files['wav'], files['srt'], lang=lang)
        if not ok:
            print(f'  ⚠ {stem}: SRT gen gagal — render tanpa subtitle')
            burn_sub_this = False
        else:
            print(f'  ✓ SRT: {os.path.basename(files["srt"])}')

    # detect resolution from thumbnail
    resolution = detect_thumb_resolution(files['thumb'])
    w, h, orient = resolution
    print(f'  Resolution: {w}x{h} ({orient})')

    # render
    out_mp4 = os.path.join(output_dir, stem + '.mp4')
    ok = render_mp4(files['thumb'], files['wav'], files['srt'], out_mp4,
                    resolution, ken_burns=ken_burns, burn_sub=burn_sub_this)
    if ok:
        size_mb = os.path.getsize(out_mp4) / 1024 / 1024
        print(f'  ✓ MP4: {size_mb:.1f} MB → {out_mp4}')
        return True
    else:
        print(f'  ❌ {stem}: render gagal')
        return False


# ============================================================
# TUI navigation helpers
# ============================================================

def find_audiobook_judul():
    """Browse AUDIOBOOK_INPUT_DIR for judul folders."""
    if not os.path.isdir(AUDIOBOOK_INPUT_DIR):
        return []
    return sorted([d for d in os.listdir(AUDIOBOOK_INPUT_DIR)
                   if os.path.isdir(os.path.join(AUDIOBOOK_INPUT_DIR, d))])


def find_seasons(judul_dir):
    """Browse judul folder for season-N folders."""
    if not os.path.isdir(judul_dir):
        return []
    return sorted([d for d in os.listdir(judul_dir)
                   if os.path.isdir(os.path.join(judul_dir, d)) and d.lower().startswith('season')])


def find_babs(season_dir):
    """Find bab stems in season dir (files with .wav/.txt/.md)."""
    if not os.path.isdir(season_dir):
        return []
    stems = set()
    for f in os.listdir(season_dir):
        for ext in ('.wav', '.txt', '.md'):
            if f.lower().endswith(ext):
                stems.add(os.path.splitext(f)[0])
    return sorted(stems)


# ============================================================
# Main TUI
# ============================================================

def main():
    parser = argparse.ArgumentParser(description='Mix Audiobook TUI — audiobook MP4 generator (TUI #21)')
    parser.add_argument('--voice', default=DEFAULT_VOICE,
                        help=f'Supertonic voice (M1-M5/F1-F5, default {DEFAULT_VOICE})')
    parser.add_argument('--no-ken-burns', action='store_true', help='Static thumbnail (no Ken Burns motion)')
    parser.add_argument('--no-burn-sub', action='store_true', help='Don\'t burn subtitle')
    parser.add_argument('--force-regen-srt', action='store_true', help='Force regenerate SRT from WAV')
    parser.add_argument('--force-regen-wav', action='store_true', help='Force regenerate WAV from text')
    args = parser.parse_args()

    clear_screen()
    print_banner()
    print('📋 Mode: Audiobook MP4 generator (text/WAV + thumbnail → MP4 + Ken Burns + subtitle)')
    print('   Navigasi: ↑↓ arrow keys, Enter konfirmasi, Ctrl+C batal')
    print()

    if not ensure_hdd():
        sys.exit(1)
    os.makedirs(AUDIOBOOK_INPUT_DIR, exist_ok=True)

    # Step 1: judul
    print('▶ Step 1/5: Pilih judul audiobook')
    juduls = find_audiobook_judul()
    if juduls:
        judul = questionary.select(
            f'Judul (ditemukan {len(juduls)} di {AUDIOBOOK_INPUT_DIR}):',
            choices=juduls + ['[Ketik nama baru]'],
            default=juduls[0],
        ).ask()
        if judul == '[Ketik nama baru]':
            judul = questionary.text('Nama judul:').ask()
    else:
        judul = questionary.text(f'Tidak ada judul di {AUDIOBOOK_INPUT_DIR}. Ketik nama:').ask()
    if not judul:
        sys.exit(1)
    judul_dir = os.path.join(str(AUDIOBOOK_INPUT_DIR), judul)
    os.makedirs(judul_dir, exist_ok=True)
    print(f'  ✓ {judul}')
    print()

    # Step 2: season
    print('▶ Step 2/5: Pilih season')
    seasons = find_seasons(judul_dir)
    if seasons:
        season = questionary.select(
            f'Season (ditemukan {len(seasons)}):',
            choices=seasons + ['[Ketik nama baru, mis. season-1]'],
            default=seasons[0],
        ).ask()
        if season == '[Ketik nama baru, mis. season-1]':
            season = questionary.text('Nama season:', default='season-1').ask()
    else:
        season = questionary.text('Nama season:', default='season-1').ask()
    if not season:
        sys.exit(1)
    season_dir = os.path.join(judul_dir, season)
    os.makedirs(season_dir, exist_ok=True)
    print(f'  ✓ {season}')
    print()

    # Step 3: bab scope
    print('▶ Step 3/5: Pilih bab')
    babs = find_babs(season_dir)
    if not babs:
        print(f'❌ Tidak ada bab di {season_dir}')
        print('   Taruh file per bab: {stem}.txt/.md + {stem}.jpg + (optional .wav/.srt)')
        print('   Contoh: S1_B001.txt + S1_B001.jpg')
        sys.exit(1)
    scope = questionary.select(
        f'Bab scope ({len(babs)} bab ditemukan):',
        choices=[
            f'Batch semua bab ({len(babs)})',
            'Pilih bab tunggal',
        ],
        default=f'Batch semua bab ({len(babs)})',
    ).ask()
    if scope.startswith('Batch'):
        selected = babs
    else:
        bab = questionary.select('Pilih bab:', choices=babs, default=babs[0]).ask()
        selected = [bab]
    preview = ', '.join(selected[:3]) + ('...' if len(selected) > 3 else '')
    print(f'  ✓ {len(selected)} bab: {preview}')
    print()

    # Step 4: options
    print('▶ Step 4/5: Options')
    voice = args.voice or DEFAULT_VOICE
    ken_burns = not args.no_ken_burns
    burn_sub = not args.no_burn_sub
    print(f'  Voice        : {voice}')
    print(f'  Ken Burns    : {"ON" if ken_burns else "OFF"}')
    print(f'  Burn subtitle: {"ON" if burn_sub else "OFF"}')
    print(f'  Force SRT    : {"YES" if args.force_regen_srt else "no"}')
    print(f'  Force WAV    : {"YES" if args.force_regen_wav else "no"}')
    print()

    # Step 5: output + confirm
    print('▶ Step 5/5: Output + konfirmasi')
    output_dir = os.path.join(str(AUDIOBOOK_DIR), judul, season)
    os.makedirs(output_dir, exist_ok=True)
    print(f'  Output: {output_dir}')
    print()

    print('═' * 64)
    print('📋 Ringkasan:')
    print('═' * 64)
    print(f'  Judul   : {judul}')
    print(f'  Season  : {season}')
    print(f'  Bab     : {len(selected)} ({preview})')
    print(f'  Voice   : {voice} (supertonic)')
    print(f'  Visual  : {"Ken Burns (slow zoom 1.0→1.08)" if ken_burns else "Static thumbnail"}')
    print(f'  Subtitle: {"burn (libass)" if burn_sub else "no burn"}')
    print(f'  Audio   : loudnorm {LUFS_TARGET} LUFS (YouTube target), AAC 192k 48kHz stereo')
    print(f'  Output  : {output_dir}')
    print('═' * 64)
    print()
    print('⚠ Mode auto-detect per bab:')
    print('  A = .txt/.md ada (→ supertonic WAV → whisper SRT → render)')
    print('  B = .wav ada, .srt absent (→ whisper SRT → render)')
    print('  C = .wav + .srt ada (→ langsung render)')
    print('  Thumbnail .jpg/.png wajib per bab. Resolution auto-detect dari aspect.')
    print()

    if not questionary.confirm('Lanjut render?', default=True).ask():
        print('Batal.')
        sys.exit(0)

    # process
    ok_count = 0
    fail_count = 0
    start = time.time()
    for stem in selected:
        try:
            if process_bab(stem, season_dir, output_dir, voice, ken_burns, burn_sub,
                           args.force_regen_srt, args.force_regen_wav):
                ok_count += 1
            else:
                fail_count += 1
        except KeyboardInterrupt:
            print('\n⚠ Dihentikan user')
            break
        except Exception as e:
            print(f'\n⚠ {stem} error: {e}')
            fail_count += 1

    elapsed = time.time() - start
    print()
    print('═' * 64)
    print(f'✅ SELESAI: {ok_count} ok / {fail_count} fail / {len(selected)} total ({format_duration(elapsed)})')
    print(f'   Output: {output_dir}')
    print('═' * 64)
    print()
    print('🎬 Langkah berikutnya:')
    print(f'   1. Preview MP4 di {output_dir}')
    print(f'   2. Upload ke YouTube (audiobook vertical, HP-friendly)')


if __name__ == '__main__':
    main()
