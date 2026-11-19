#!/usr/bin/env python3
"""
test-manim-shorts.py — Test harness untuk manim-shorts-tui.py core pipeline.

Bypass questionary interactive prompts (sandbox nggak bisa prompt).
Test core functions langsung: parse_srt → generate_manim_script → render_manim → mux.

Dummy data:
  - WAV 30s (sine tone via ffmpeg) — simulasi TTS narasi
  - SRT manual 8 segments (infografis tema, match POC)
"""
import os
import sys
import subprocess
import tempfile
import shutil
from pathlib import Path

# Import dari manim-shorts-tui.py (filename ada hyphen, pakai importlib)
import importlib.util
_spec = importlib.util.spec_from_file_location(
    "manim_shorts_tui", Path(__file__).parent / "manim-shorts-tui.py")
mod = importlib.util.module_from_spec(_spec)
sys.modules["manim_shorts_tui"] = mod
_spec.loader.exec_module(mod)
from manim_shorts_tui import (
    parse_srt, generate_manim_script, render_manim, mux_audio_video,
    get_duration, find_ffmpeg, find_ffprobe, find_manim, fmt_dur, fmt_size,
    OUTPUT_W, OUTPUT_H, FPS, SCENE_NAME,
)

TEST_DIR = Path('/tmp/test-manim-shorts')
WAV_PATH = TEST_DIR / 'narasi-30s.wav'
SRT_PATH = TEST_DIR / 'narasi-30s.srt'
OUTPUT_PATH = TEST_DIR / 'output' / 'narasi-30s-shorts.mp4'

# Dummy SRT content — 8 segments, infografis tema, total ~30s
SRT_CONTENT = """1
00:00:00,000 --> 00:00:03,000
Statistik penduduk bahasa Jawa

2
00:00:03,000 --> 00:00:06,500
84 juta penutur aktif di Indonesia

3
00:00:06,500 --> 00:00:10,000
Menyebar di Jawa Tengah, Yogyakarta, dan Jawa Timur

4
00:00:10,000 --> 00:00:14,000
Bahasa ibu untuk mayoritas warga

5
00:00:14,000 --> 00:00:18,000
Punya tingkatan krama dan ngoko

6
00:00:18,000 --> 00:00:22,000
Krama untuk hormat, ngoko untuk akrab

7
00:00:22,000 --> 00:00:26,000
Sumber data Badan Pusat Statistik 2020

8
00:00:26,000 --> 00:00:30,000
Bahasa hidup dan terus berkembang
"""


def setup_dummy_data(ffmpeg):
    """Buat dummy WAV 30s (sine tone) + SRT manual."""
    TEST_DIR.mkdir(parents=True, exist_ok=True)
    (TEST_DIR / 'output').mkdir(exist_ok=True)

    # Generate WAV 30s sine tone (440Hz, audible for sync check)
    if not WAV_PATH.exists():
        print(f'  Generate dummy WAV 30s: {WAV_PATH}')
        cmd = [ffmpeg, '-y',
               '-f', 'lavfi', '-i', 'sine=frequency=440:duration=30',
               '-ac', '1', '-ar', '48000',
               '-c:a', 'pcm_s16le',
               str(WAV_PATH)]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            print(f'  ❌ ffmpeg gagal generate WAV: {result.stderr[-200:]}')
            return False

    # Write SRT manual
    print(f'  Write dummy SRT: {SRT_PATH}')
    SRT_PATH.write_text(SRT_CONTENT, encoding='utf-8')

    return WAV_PATH.exists() and SRT_PATH.exists()


def test_parse_srt(ffprobe):
    """Test 1: parse SRT → segments."""
    print('\n▶ Test 1: parse_srt()')
    segments = parse_srt(str(SRT_PATH))
    assert len(segments) == 8, f'Expected 8 segments, got {len(segments)}'
    assert segments[0]['start'] == 0.0
    assert segments[0]['text'] == 'Statistik penduduk bahasa Jawa'
    assert segments[-1]['end'] == 30.0
    total_dur = sum(s['duration'] for s in segments)
    print(f'  ✓ {len(segments)} segments parsed, total dur {fmt_dur(total_dur)}, last end {fmt_dur(segments[-1]["end"])}')
    # Print first 3
    for i, s in enumerate(segments[:3], 1):
        txt = s['text'][:40]
        print(f'    [{i}] {fmt_dur(s["start"])}→{fmt_dur(s["end"])} ({s["duration"]:.1f}s) {txt}')
    return segments


def test_generate_script(segments, wav_dur):
    """Test 2: generate manim script."""
    print('\n▶ Test 2: generate_manim_script()')
    script_path = str(TEST_DIR / 'scene_script.py')
    generate_manim_script(segments, wav_dur, script_path)
    assert os.path.exists(script_path)
    # Verify script content has key elements
    content = Path(script_path).read_text()
    assert 'class ShortsScene(Scene)' in content
    assert 'SEGMENTS' in content
    assert 'WAV_DURATION = 30' in content
    assert 'config.pixel_width = 1080' in content
    assert 'config.pixel_height = 1920' in content
    print(f'  ✓ {os.path.basename(script_path)} generated ({len(content)} bytes)')
    print(f'    Contains: ShortsScene class, {len(segments)} segments, WAV_DURATION={wav_dur}')
    return script_path


def test_render(manim_bin, script_path):
    """Test 3: render manim → video MP4."""
    print('\n▶ Test 3: render_manim()')
    media_dir = TEST_DIR / 'media'
    if media_dir.exists():
        shutil.rmtree(media_dir)
    import time
    t0 = time.time()
    video_mp4 = render_manim(manim_bin, script_path, media_dir)
    render_time = time.time() - t0
    assert video_mp4, 'render_manim returned None'
    assert os.path.exists(video_mp4)
    print(f'  ✓ Render OK ({fmt_dur(render_time)})')
    print(f'    Output: {video_mp4}')
    return video_mp4, render_time


def test_mux(ffmpeg, video_mp4, wav_path):
    """Test 4: mux video + WAV → final MP4."""
    print('\n▶ Test 4: mux_audio_video()')
    ok = mux_audio_video(ffmpeg, video_mp4, str(wav_path), str(OUTPUT_PATH))
    assert ok, 'mux failed'
    assert OUTPUT_PATH.exists()
    size_mb = OUTPUT_PATH.stat().st_size / 1024 / 1024
    print(f'  ✓ Mux OK: {OUTPUT_PATH.name} ({fmt_size(size_mb)})')
    return str(OUTPUT_PATH)


def test_verify_output(ffprobe, output_path, wav_dur, render_time):
    """Test 5: verify output MP4 — duration, resolution, audio stream."""
    print('\n▶ Test 5: verify output MP4')
    dur = get_duration(ffprobe, output_path)
    size_mb = os.path.getsize(output_path) / 1024 / 1024

    # Check video stream
    result = subprocess.run([
        ffprobe, '-v', 'error', '-select_streams', 'v:0',
        '-show_entries', 'stream=width,height,codec_name,r_frame_rate',
        '-of', 'default=noprint_wrappers=1', output_path,
    ], capture_output=True, text=True)
    print(f'    Video stream: {result.stdout.strip()}')

    # Check audio stream
    result_a = subprocess.run([
        ffprobe, '-v', 'error', '-select_streams', 'a:0',
        '-show_entries', 'stream=codec_name,sample_rate,channels',
        '-of', 'default=noprint_wrappers=1', output_path,
    ], capture_output=True, text=True)
    print(f'    Audio stream: {result_a.stdout.strip()}')

    print(f'\n  Durasi : {fmt_dur(dur)} (WAV {fmt_dur(wav_dur)})')
    print(f'  Size   : {fmt_size(size_mb)}')
    print(f'  Render : {fmt_dur(render_time)} ({render_time/max(dur,1):.1f}x realtime)')

    # Assertions
    assert dur > 28, f'Duration too short: {dur}'
    assert dur < 32, f'Duration too long: {dur}'
    assert 'h264' in result.stdout or 'h264' in result.stdout.lower()
    assert result_a.stdout.strip(), 'No audio stream'

    print('  ✓ Output valid: duration ~30s, video+audio streams present')


def main():
    print('═' * 64)
    print('  Test manim-shorts-tui.py core pipeline')
    print('═' * 64)

    ffmpeg = find_ffmpeg()
    ffprobe = find_ffprobe()
    manim_bin = find_manim()

    # Setup
    print('\n▶ Setup: dummy WAV 30s + SRT 8 segments')
    if not setup_dummy_data(ffmpeg):
        print('❌ Setup gagal')
        return
    wav_dur = get_duration(ffprobe, str(WAV_PATH))
    print(f'  ✓ WAV {fmt_dur(wav_dur)}, SRT ready')

    # Run tests
    segments = test_parse_srt(ffprobe)
    script_path = test_generate_script(segments, wav_dur)
    video_mp4, render_time = test_render(manim_bin, script_path)
    test_mux(ffmpeg, video_mp4, str(WAV_PATH))
    test_verify_output(ffprobe, str(OUTPUT_PATH), wav_dur, render_time)

    print('\n' + '═' * 64)
    print('  ✅ ALL TESTS PASSED')
    print('═' * 64)
    print(f'\n  Output: {OUTPUT_PATH}')
    print(f'  Render: {fmt_dur(render_time)} for 30s video ({render_time/30:.1f}x realtime)')
    print(f'\n  Next: extract frames untuk visual check')


if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        print(f'\n❌ TEST FAILED: {e}')
        import traceback
        print(traceback.format_exc())
        sys.exit(1)
