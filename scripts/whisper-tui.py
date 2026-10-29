#!/usr/bin/env python3
"""
whisper-tui.py v2.0 — TUI generate SRT dari audio via whisper.cpp (Metal GPU native)

v2.0 BREAKING: Rewrite dari faster-whisper (Python) ke whisper.cpp (C++ CLI)
  - faster-whisper/CTranslate2 TIDAK support Metal di macOS (hanya iOS)
  - whisper.cpp pakai Metal native via ggml → GPU jalan di M1
  - User test: "ggml_metal_library_init: using embedded metal library" ✅
  - Performance: ~3-5x realtime (vs CPU faster-whisper ~1.65x)

v1.x (deprecated): pakai faster-whisper Python library (CPU only di macOS)

Workflow:
  yt-dlp → MP4 + MP3 (audio Mandarin/English/ID)
  whisper-tui → MP3 → SRT ori (.zh.srt / .en.srt / .id.srt)
  [USER] → Google Translate → SRT ori → SRT ID (.id.srt)
  edge-tts-tui → SRT ID → dub Indonesia
  mix-tui → MP4 + MP3 + dub + SRT ID → final video

Prerequisites:
  brew install whisper.cpp     # Metal GPU native
  brew install ffmpeg           # audio decode

Model: ggml-medium.bin (1.5 GB, default — akurasi bagus untuk Mandarin)
  Download: curl -L -o /Volumes/HDD/Dubbing/input/ggml-medium.bin \
    "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-medium.bin"

Install: pip3 install questionary (hanya untuk TUI, bukan whisper)
Usage: python3 whisper-tui.py
"""

import os
import sys
import time
import subprocess
import shutil
from pathlib import Path

try:
    import questionary
except ImportError:
    print('\n❌ pip3 install questionary')
    sys.exit(1)

VERSION = 'v2.0'


def clear_screen():
    os.system('clear' if os.name != 'nt' else 'cls')


def print_banner():
    clear_screen()
    print('╔' + '═' * 64 + '╗')
    print('║  🎤 Whisper TUI v2.0 — whisper.cpp (Metal GPU native)     ║')
    print('║  Generate SRT dari audio — M1 GPU acceleration           ║')
    print('╚' + '═' * 64 + '╝')
    print()


def find_whisper_cli():
    """Cari whisper-cli binary."""
    path = shutil.which('whisper-cli')
    if path:
        return path
    for loc in ['/opt/homebrew/bin/whisper-cli', '/usr/local/bin/whisper-cli']:
        if os.path.isfile(loc):
            return loc
    return None


def find_model():
    """Cari ggml model file (.bin) di lokasi umum."""
    search_dirs = [
        '/Volumes/HDD/Dubbing/input',
        os.path.expanduser('~/Dubbing'),
        os.path.expanduser('~/.cache/whisper'),
    ]
    for d in search_dirs:
        if not os.path.isdir(d):
            continue
        for f in sorted(os.listdir(d)):
            if f.startswith('ggml-') and f.endswith('.bin'):
                return os.path.join(d, f)
    return None


def find_files_in_dir(search_dir, extensions):
    files = []
    for ext in extensions:
        for f in os.listdir(search_dir) if os.path.isdir(search_dir) else []:
            if f.lower().endswith(f'.{ext}') or f.lower().endswith(f'.{ext.upper()}'):
                files.append(f)
    files.sort()
    return list(dict.fromkeys(files))


def select_file(prompt, extensions, search_dir=None, default=None):
    from config import INPUT_DIR, ensure_hdd
    if search_dir is None:
        if ensure_hdd():
            search_dir = str(INPUT_DIR)
        else:
            search_dir = os.getcwd()
    available = find_files_in_dir(search_dir, extensions)
    if not available:
        path = questionary.text(f'{prompt} (ketik path lengkap):', default=default or '').ask()
        return path
    choices = available + ['[Ketik path manual]']
    selected = questionary.select(prompt, choices=choices, default=available[0]).ask()
    if selected == '[Ketik path manual]':
        return questionary.text(f'{prompt} (ketik path lengkap):', default=default or '').ask()
    return os.path.join(search_dir, selected)


def format_duration(seconds):
    if seconds < 0:
        return '0s'
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    if h > 0:
        return f'{h}j {m}m {s}s'
    if m > 0:
        return f'{m}m {s}s'
    return f'{s}s'


def get_audio_duration(path):
    try:
        result = subprocess.run(
            ['ffprobe', '-v', 'error', '-show_entries', 'format=duration',
             '-of', 'default=noprint_wrappers=1:nokey=1', path],
            capture_output=True, text=True
        )
        return float(result.stdout.strip())
    except Exception:
        return 0


def sanitize_filename(name):
    import re
    name = re.sub(r'[\\/:*?"<>|]', '', name).strip()
    return name[:200] if len(name) > 200 else (name or 'audio')


def main():
    print_banner()

    # Check whisper-cli
    whisper_cli = find_whisper_cli()
    if not whisper_cli:
        print('❌ whisper-cli belum terinstall!')
        print('   Install: brew install whisper.cpp')
        sys.exit(1)
    print(f'whisper-cli: {whisper_cli}')

    # Check model
    model_path = find_model()
    if model_path:
        model_size = os.path.getsize(model_path) / 1024 / 1024 / 1024
        print(f'model:       {model_path} ({model_size:.1f} GB)')
    else:
        print('⚠ Model ggml-*.bin tidak ditemukan!')
        print('  Download medium model (1.5 GB, recommended untuk Mandarin):')
        print('  curl -L -o /Volumes/HDD/Dubbing/input/ggml-medium.bin \\')
        print('    "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-medium.bin"')
        # Allow manual input
        model_path = questionary.text('Path model .bin (ketik manual):').ask()
        if not model_path or not os.path.isfile(model_path):
            print('❌ Model tidak ditemukan. Download dulu.')
            sys.exit(1)
    print()

    # === Step 1: Pilih audio ===
    print('▶ Step 1/5: Pilih file audio')
    audio_path = select_file('Audio (MP3/M4A/WAV):', ['mp3', 'm4a', 'wav'])
    if not audio_path:
        print('Batal.')
        sys.exit(0)
    audio_path = os.path.expanduser(audio_path)
    if not os.path.isfile(audio_path):
        print(f'❌ File tidak ditemukan: {audio_path}')
        sys.exit(1)

    audio_size = os.path.getsize(audio_path) / 1024 / 1024
    audio_dur = get_audio_duration(audio_path)
    print(f'  ✓ {os.path.basename(audio_path)} ({audio_size:.1f} MB, {format_duration(audio_dur)})')
    print()

    # === Step 2: Pilih bahasa ===
    print('▶ Step 2/5: Pilih bahasa audio')
    lang_choice = questionary.select(
        'Bahasa audio:',
        choices=[
            'Mandarin (Chinese)',
            'English',
            'Indonesia',
            'Japanese',
            'Korean',
            'Auto-detect',
        ],
        default='Mandarin (Chinese)',
    ).ask()

    lang_map = {
        'Mandarin (Chinese)': 'zh',
        'English': 'en',
        'Indonesia': 'id',
        'Japanese': 'ja',
        'Korean': 'ko',
        'Auto-detect': 'auto',
    }
    lang_code = lang_map.get(lang_choice, 'auto')
    print(f'  ✓ {lang_choice}')
    print()

    # === Step 3: Pilih model ===
    print('▶ Step 3/5: Pilih model Whisper')
    # Detect available models
    model_dir = os.path.dirname(model_path)
    available_models = []
    if os.path.isdir(model_dir):
        for f in sorted(os.listdir(model_dir)):
            if f.startswith('ggml-') and f.endswith('.bin'):
                fpath = os.path.join(model_dir, f)
                fsize = os.path.getsize(fpath) / 1024 / 1024 / 1024
                name = f.replace('ggml-', '').replace('.bin', '')
                available_models.append((fpath, name, fsize))

    if len(available_models) > 1:
        model_choices = []
        for fpath, name, fsize in available_models:
            label = f'{name} ({fsize:.1f} GB)'
            if name == 'medium':
                label += ' — REKOMENDASI'
            model_choices.append(questionary.Choice(label, value=fpath))
        model_path = questionary.select('Model:', choices=model_choices,
                                        default=available_models[0][0] if available_models else model_path).ask()
    else:
        print(f'  ✓ {os.path.basename(model_path)} (hanya 1 model tersedia)')
    print(f'  ✓ {os.path.basename(model_path)}')
    print()

    # === Step 4: Pilih nama output SRT ===
    print('▶ Step 4/5: Pilih nama output SRT')
    base_name = Path(audio_path).stem
    ext_map = {'zh': '.zh', 'en': '.en', 'id': '.id', 'ja': '.ja', 'ko': '.ko', 'auto': ''}
    default_output = os.path.join(os.path.dirname(audio_path), f'{base_name}{ext_map.get(lang_code, "")}.srt')
    output_srt = questionary.text('Output SRT:', default=default_output).ask()
    if not output_srt:
        output_srt = default_output
    output_srt = os.path.expanduser(output_srt)
    # whisper.cpp output file (without extension)
    output_base = output_srt.replace('.srt', '')
    print(f'  ✓ {output_srt}')
    print()

    # === Step 5: Konfirmasi ===
    print('▶ Step 5/5: Konfirmasi')
    print()
    print('╔' + '═' * 64 + '╗')
    print('║  📋 Ringkasan:' + ' ' * 49 + '║')
    print('╠' + '═' * 64 + '╣')
    print(f'║  Audio   : {os.path.basename(audio_path)[:46]:<46}║')
    print(f'║  Size    : {f"{audio_size:.1f} MB":<46}║')
    print(f'║  Durasi  : {format_duration(audio_dur):<46}║')
    print(f'║  Bahasa  : {lang_choice[:46]:<46}║')
    print(f'║  Model   : {os.path.basename(model_path)[:46]:<46}║')
    print(f'║  Output  : {os.path.basename(output_srt)[:46]:<46}║')
    print(f'║  Engine  : {"whisper.cpp (auto Metal/CPU)":<46}║')
    # Estimasi: Metal ~3-5x realtime
    if audio_dur > 0:
        est_min = audio_dur / 60 / 3.5  # 3.5x realtime avg
        print(f'║  Estimasi: {f"~{int(est_min)} menit (Metal GPU ~3.5x realtime)":<46}║')
    print('╚' + '═' * 64 + '╝')
    print()
    print('  ℹ Whisper fokus: generate SRT ori (speech-to-text)')
    print('    Translate: USER lakukan manual via Google Translate')
    print()

    if not questionary.confirm('Mulai Whisper?', default=True).ask():
        print('Batal.')
        sys.exit(0)

    # === Run whisper.cpp ===
    print()
    print('═' * 64)
    print(f'🚀 Mulai Whisper... (model: {os.path.basename(model_path)}, bahasa: {lang_choice})')
    print('═' * 64)
    print()

    # Build whisper-cli command
    cmd = [
        whisper_cli,
        '-m', model_path,
        '-l', lang_code,
        '-f', audio_path,
        '-t', '8',          # 8 threads
        '-osrt',            # output SRT format
        '-of', output_base,  # output file (without extension)
    ]

    # Run with real-time output (stream stdout/stderr)
    print('▶ Running whisper-cli...')
    print(f'  Command: {" ".join(cmd[:4])}... -osrt -of {os.path.basename(output_base)}')
    print()
    start_time = time.time()

    process = None
    try:
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )

        cue_count = 0
        metal_detected = False
        for line in process.stdout:
            line = line.rstrip()
            # Detect Metal in startup log
            if 'metal' in line.lower():
                if not metal_detected:
                    metal_detected = True
                    print(f'  ✅ {line}')
                else:
                    # Skip verbose metal library compile logs
                    if 'ggml_metal_library_compile_all' in line:
                        continue
                    print(f'  ℹ {line}')
            elif 'whisper_model_load' in line or 'system_info' in line:
                print(f'  ℹ {line}')
            elif line.startswith('[') and '-->' in line:
                # Progress: [00:00:00.000 --> 00:00:10.000]
                cue_count += 1
                if cue_count % 50 == 0:
                    elapsed = time.time() - start_time
                    print(f'   [{cue_count} cues] elapsed: {format_duration(elapsed)} | last: {line[:60]}')
            elif line.strip():
                # Other output (errors, warnings, final result)
                if 'error' in line.lower() or 'Error' in line:
                    print(f'  ❌ {line}')
                else:
                    print(f'  {line}')

        process.wait()
        elapsed = time.time() - start_time

    except KeyboardInterrupt:
        print('\n\n⏹ Dibatalkan user.')
        if process:
            process.kill()
        sys.exit(130)
    except Exception as e:
        print(f'\n❌ Error: {e}')
        sys.exit(1)

    # === Hasil ===
    print()
    print('═' * 64)
    print('✅ SELESAI!\n')
    print(f'  Waktu: {format_duration(elapsed)}')

    if metal_detected:
        print(f'  Engine: whisper.cpp (Metal GPU) ✅')
        if audio_dur > 0:
            realtime_factor = audio_dur / elapsed
            print(f'  Speed:  {realtime_factor:.1f}x realtime')
    else:
        print(f'  Engine: whisper.cpp (CPU) ⚠ — Metal tidak terdeteksi')

    # Cek output file
    if os.path.isfile(output_srt):
        srt_size = os.path.getsize(output_srt) / 1024
        # Count cues
        with open(output_srt, 'r', encoding='utf-8') as f:
            cue_count = sum(1 for line in f if line.strip().isdigit())
        print(f'  Output: {output_srt}')
        print(f'  Size:   {srt_size:.1f} KB, {cue_count} cue')
    else:
        print(f'  ⚠ Output tidak ditemukan: {output_srt}')
        # Cek alternative extension
        alt = output_base + '.srt'
        if os.path.isfile(alt) and alt != output_srt:
            print(f'  ℹ Coba: {alt}')

    print()
    print('🎬 Langkah berikutnya:')
    print(f'   1. Cek SRT di: {output_srt}')
    print(f'   2. Translate manual via Google Translate (bukan tugas Whisper)')
    print(f'   3. edge-tts-tui: python3 edge-tts-tui.py')
    print('═' * 64)


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print('\n\n⏹ Dibatalkan user.')
        sys.exit(130)
    except Exception as e:
        print(f'\n❌ Error: {e}', file=sys.stderr)
        import traceback
        print(f'\nStack trace:\n{traceback.format_exc()[:2000]}', file=sys.stderr)
        sys.exit(1)
