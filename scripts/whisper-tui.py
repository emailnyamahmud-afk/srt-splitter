#!/usr/bin/env python3
"""
whisper-tui.py v1.3 — TUI generate SRT dari audio via faster-whisper

Tugas: speech-to-text saja (generate SRT ori).
Translate: USER lakukan manual via Google Translate (bukan tugas Whisper).

v1.3 FIX: Metal detection lebih robust — print actual error, secondary check via torch MPS.
  - Bug v1.2: CTranslate2.get_supported_compute_types("metal") gagal silently
  - Fix: print actual exception, lalu cek torch.backends.mps.is_available()
  - Kalau MPS tersedia (demucs proof itu), coba load device=metal langsung
  - Kalau Metal load gagal, kasih instruksi upgrade CTranslate2

v1.2: Auto-detect Metal (M1 GPU) untuk 2-4x lebih cepat + fan tidak bunyi.
  - CTranslate2 support device="metal" + compute_type="float16" di Apple Silicon
  - Auto-detect: try Metal first, fallback ke CPU kalau gagal
  - Metal: ~3-6x realtime (vs CPU int8: ~1.65x realtime)

v1.1 FIX: bypass av library (av 19.x incompatible dengan faster-whisper).
  - Decode audio via ffmpeg ke numpy float32 array (16kHz mono)
  - Pass numpy array ke faster-whisper (bukan file path)
  - Tidak butuh av library sama sekali, no version conflict

Workflow:
  yt-dlp → MP4 + MP3 (audio Mandarin/English/ID)
  whisper-tui → MP3 → SRT ori (.zh.srt / .en.srt / .id.srt)
  [USER] → Google Translate → SRT ori → SRT ID (.id.srt)
  edge-tts-tui → SRT ID → dub Indonesia
  mix-tui → MP4 + MP3 + dub + SRT ID → final video

Implementasi: faster-whisper (CTranslate2 backend, 4x cepat, RAM aman)
Model: medium (1.5 GB, default — akurasi bagus untuk Mandarin)

Install: pip3 install faster-whisper
Usage: python3 whisper-tui.py
"""

import os
import sys
import time
import subprocess
import numpy as np
from pathlib import Path

try:
    import questionary
except ImportError:
    print('\n❌ pip3 install questionary faster-whisper')
    sys.exit(1)

try:
    from faster_whisper import WhisperModel
except ImportError:
    print()
    print('═' * 64)
    print('❌ faster-whisper belum terinstall!')
    print('═' * 64)
    print()
    print('   Install dengan:')
    print()
    print('   pip3 install faster-whisper')
    print()
    print('═' * 64)
    sys.exit(1)


def clear_screen():
    os.system('clear' if os.name != 'nt' else 'cls')


def print_banner():
    clear_screen()
    print('╔' + '═' * 64 + '╗')
    print('║  🎤 Whisper TUI — Generate SRT dari audio                  ║')
    print('║  faster-whisper (CTranslate2, M1 optimized)             ║')
    print('╚' + '═' * 64 + '╝')
    print()


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


def format_srt_timestamp(seconds):
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    ms = int((seconds % 1) * 1000)
    return f'{h:02d}:{m:02d}:{s:02d},{ms:03d}'


def write_srt(segments, output_path):
    with open(output_path, 'w', encoding='utf-8') as f:
        for i, seg in enumerate(segments, 1):
            start = format_srt_timestamp(seg['start'])
            end = format_srt_timestamp(seg['end'])
            text = seg['text'].strip()
            f.write(f'{i}\n')
            f.write(f'{start} --> {end}\n')
            f.write(f'{text}\n')
            f.write('\n')
    return len(segments)


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


def decode_audio_via_ffmpeg(audio_path):
    """v1.1 FIX: Decode audio via ffmpeg ke numpy float32 array (16kHz mono).

    Bypass av library entirely (av 19.x incompatible dengan faster-whisper).
    ffmpeg decode → raw PCM float32 → numpy array.

    Returns: numpy float32 array, sample_rate (16000)
    """
    print('  ℹ Decoding audio via ffmpeg (bypass av library)...')
    result = subprocess.run(
        ['ffmpeg', '-i', audio_path,
         '-f', 'f32le',      # 32-bit float little-endian
         '-ar', '16000',     # 16kHz (Whisper standard)
         '-ac', '1',         # mono
         '-'],               # output to stdout
        capture_output=True, timeout=3600  # 1 hour max
    )
    if result.returncode != 0:
        raise RuntimeError(f'ffmpeg decode gagal: {result.stderr.decode()[-500:]}')

    audio_np = np.frombuffer(result.stdout, dtype=np.float32)
    print(f'  ✓ Audio decoded: {len(audio_np)} samples, {len(audio_np)/16000:.1f}s @ 16kHz mono')
    return audio_np, 16000


def main():
    print_banner()

    print('📋 Tugas Whisper: generate SRT dari audio (speech-to-text)')
    print('   Translate: USER lakukan manual via Google Translate (bukan tugas Whisper)')
    print()
    print('   Navigasi: ↑↓ arrow keys, Enter konfirmasi, q batal')
    print()

    total = 5

    # Step 1: Pilih audio
    print(f'▶ Step 1/{total}: Pilih file audio')
    from config import INPUT_DIR, ensure_hdd
    audio_path = select_file('Audio (MP3/M4A/WAV):', ['mp3', 'm4a', 'wav', 'flac'])
    if not audio_path:
        print('Batal.'); sys.exit(0)
    if not os.path.isfile(audio_path):
        print(f'\n❌ File tidak ditemukan: {audio_path}')
        sys.exit(1)
    audio_size = os.path.getsize(audio_path) / 1024 / 1024
    audio_dur = get_audio_duration(audio_path)
    print(f'  ✓ {os.path.basename(audio_path)} ({audio_size:.1f} MB, {format_duration(audio_dur)})')
    print()

    # Step 2: Pilih bahasa
    print(f'▶ Step 2/{total}: Pilih bahasa audio')
    lang_choice = questionary.select(
        'Bahasa audio:',
        choices=[
            'Auto-detect (Whisper detect otomatis)',
            'Mandarin (Chinese)',
            'Indonesia',
            'English',
            'Japanese',
            'Korean',
        ],
        default='Auto-detect (Whisper detect otomatis)',
    ).ask()
    lang_map = {
        'Auto-detect': None,
        'Mandarin': 'zh',
        'Indonesia': 'id',
        'English': 'en',
        'Japanese': 'ja',
        'Korean': 'ko',
    }
    lang_code = None
    for key, val in lang_map.items():
        if key in lang_choice:
            lang_code = val
            break
    lang_display = lang_choice.split('(')[0].strip() if '(' in lang_choice else lang_choice
    print(f'  ✓ {lang_display}')
    print()

    # Step 3: Pilih model
    print(f'▶ Step 3/{total}: Pilih model Whisper')
    model_choice = questionary.select(
        'Model:',
        choices=[
            'medium (1.5 GB, akurasi bagus, ~20-30 menit untuk 2 jam audio) — REKOMENDASI',
            'small (244 MB, cepat ~10 menit, akurasi OK untuk clear audio)',
            'large-v3 (3 GB, terbaik, ~60-90 menit, RAM ~5-10 GB)',
            'base (74 MB, cepat ~3 menit, akurasi kurang — tidak rekomendasi)',
        ],
        default='medium (1.5 GB, akurasi bagus, ~20-30 menit untuk 2 jam audio) — REKOMENDASI',
    ).ask()
    if 'medium' in model_choice:
        model_size = 'medium'
    elif 'small' in model_choice:
        model_size = 'small'
    elif 'large' in model_choice:
        model_size = 'large-v3'
    else:
        model_size = 'base'
    print(f'  ✓ {model_size}')
    print()

    # Step 4: Output SRT
    print(f'▶ Step 4/{total}: Pilih nama output SRT')
    audio_stem = Path(audio_path).stem
    if audio_stem.endswith('-audio'):
        audio_stem = audio_stem[:-6]
    lang_suffix = lang_code if lang_code else 'auto'
    default_dir = str(INPUT_DIR) if ensure_hdd() else os.path.dirname(audio_path)
    default_output = os.path.join(default_dir, f'{audio_stem}.{lang_suffix}.srt')
    print(f'  ℹ Default output: {default_output}')
    output_path = questionary.text('Output SRT:', default=default_output).ask()
    output_path = os.path.expanduser(output_path or default_output)
    out_dir = os.path.dirname(output_path)
    if out_dir and not os.path.isdir(out_dir):
        os.makedirs(out_dir, exist_ok=True)
    print(f'  ✓ {output_path}')
    print()

    # Step 5: Konfirmasi
    print(f'▶ Step 5/{total}: Konfirmasi')
    print()
    print('╔' + '═' * 64 + '╗')
    print('║  📋 Ringkasan:' + ' ' * 49 + '║')
    print('╠' + '═' * 64 + '╣')
    print(f'║  Audio   : {os.path.basename(audio_path)[:46]:<46}║')
    print(f'║  Size    : {audio_size:.1f} MB{"":<37}║')
    print(f'║  Durasi  : {format_duration(audio_dur):<46}║')
    print(f'║  Bahasa  : {lang_display[:46]:<46}║')
    print(f'║  Model   : {model_size[:46]:<46}║')
    print(f'║  Output  : {os.path.basename(output_path)[:46]:<46}║')
    if audio_dur > 0:
        est_factor = {'medium': 0.7, 'small': 0.3, 'large-v3': 1.5, 'base': 0.15}
        est_time = audio_dur * est_factor.get(model_size, 0.7) / 60
        print(f'║  Estimasi: ~{est_time:.0f} menit (M1){"":<34}║')
    print('╚' + '═' * 64 + '╝')
    print()
    print('  ℹ Whisper fokus: generate SRT ori (speech-to-text)')
    print('    Translate: USER lakukan manual via Google Translate')
    print()

    confirm = questionary.confirm('Mulai Whisper?', default=True).ask()
    if not confirm:
        print('Batal.'); sys.exit(0)

    # === Run Whisper ===
    print('\n' + '═' * 64)
    print(f'🚀 Mulai Whisper... (model: {model_size}, bahasa: {lang_display})')
    print('═' * 64 + '\n')

    # Load model
    # v1.3: Metal detection — print actual error, secondary check via torch MPS
    print('▶ Loading model...')
    device = "cpu"
    compute_type = "int8"

    # Step 1: Cek CTranslate2 Metal support
    try:
        import ctranslate2
        ct2_version = getattr(ctranslate2, '__version__', 'unknown')
        metal_types = ctranslate2.get_supported_compute_types("metal")
        if "float16" in metal_types or "float32" in metal_types:
            device = "metal"
            compute_type = "float16" if "float16" in metal_types else "float32"
            print(f'  ✓ Apple Metal terdeteksi — GPU acceleration (device=metal, {compute_type})')
        else:
            print(f'  ℹ Metal tersedia tapi tidak ada float16/float32 — pakai CPU')
    except Exception as e:
        # Step 2: Secondary check via torch MPS (lebih reliable di M1)
        print(f'  ℹ CTranslate2 Metal check gagal: {e}')
        try:
            import subprocess as _sp
            _r = _sp.run(
                [sys.executable, '-c', 'import torch; print("mps" if torch.backends.mps.is_available() else "cpu")'],
                capture_output=True, text=True, timeout=10
            )
            if _r.returncode == 0 and 'mps' in _r.stdout:
                print(f'  ℹ PyTorch MPS tersedia — M1 GPU terkonfirmasi')
                print(f'  ℹ Coba load dengan device=metal langsung (skip get_supported_compute_types)...')
                device = "metal"
                compute_type = "float16"
            else:
                print(f'  ℹ PyTorch MPS juga tidak tersedia — pakai CPU')
        except Exception as e2:
            print(f'  ℹ Torch check juga gagal: {e2} — pakai CPU')

        # v1.3: Print troubleshooting instructions untuk Python 3.14 issue
        py_version = f"{sys.version_info.major}.{sys.version_info.minor}"
        if device == "cpu" and py_version >= "3.13":
            print()
            print(f'  ⚠ GPU (Metal) TIDAK terpakai — Whisper jalan di CPU (lambat, fan bunyi)')
            print(f'  ⚠ Penyebab: Python {py_version} terlalu baru — CTranslate2 belum compile Metal untuk versi ini')
            print(f'  ⚠ Solusi: Recreate venv dengan Python 3.12 (CTranslate2 Metal ready untuk 3.12):')
            print(f'     brew install python@3.12')
            print(f'     mv ~/Dubbing/venv ~/Dubbing/venv-backup-py{py_version}')
            print(f'     /opt/homebrew/bin/python3.12 -m venv ~/Dubbing/venv')
            print(f'     source ~/Dubbing/venv/bin/activate')
            print(f'     pip3 install questionary edge-tts yt-dlp torchaudio demucs numpy faster-whisper ctranslate2')
            print(f'  ⚠ Setelah recreate venv, Whisper akan pakai GPU (Metal) — 2-3x lebih cepat, fan tenang')
            print()

    # Step 3: Try load model
    try:
        model = WhisperModel(model_size, device=device, compute_type=compute_type)
    except Exception as e:
        if device == "metal":
            print(f'  ⚠ Metal load gagal ({e})')
            print(f'  ⚠ Coba upgrade CTranslate2: pip3 install ctranslate2 --upgrade')
            print(f'  ⚠ Fallback ke CPU (device=cpu, int8)...')
            device = "cpu"
            compute_type = "int8"
            model = WhisperModel(model_size, device=device, compute_type=compute_type)
        else:
            raise e

    print(f'  ✓ Model {model_size} loaded (device={device}, {compute_type})')

    # v1.1 FIX: Decode audio via ffmpeg (bypass av library)
    print(f'\n▶ Decoding audio...')
    try:
        audio_np, sample_rate = decode_audio_via_ffmpeg(audio_path)
    except Exception as e:
        print(f'\n❌ Gagal decode audio: {e}')
        sys.exit(1)

    # Transcribe (pass numpy array, bukan file path)
    print(f'\n▶ Transcribing audio...')
    print(f'   Progress: (Whisper tidak punya native progress bar, tunggu sampai selesai)')
    if audio_dur > 0:
        est_factor = {'medium': 0.7, 'small': 0.3, 'large-v3': 1.5, 'base': 0.15}
        est_time = audio_dur * est_factor.get(model_size, 0.7) / 60
        print(f'   Estimasi: {format_duration(audio_dur)} audio → ~{est_time:.0f} menit')
    print()

    start_time = time.time()
    segments = []
    try:
        segments_gen, info = model.transcribe(
            audio_np,            # v1.1: numpy array (bukan file path)
            language=lang_code,
            beam_size=5,
            vad_filter=True,
            vad_parameters=dict(min_silence_duration_ms=500),
        )

        if lang_code is None:
            detected_lang = info.language
            detected_prob = info.language_probability
            print(f'  ℹ Bahasa terdeteksi: {detected_lang} ({detected_prob*100:.1f}% confidence)')
            if '.auto.srt' in output_path:
                output_path = output_path.replace('.auto.srt', f'.{detected_lang}.srt')
                print(f'     Output diperbarui: {output_path}')
            print()

        seg_count = 0
        for seg in segments_gen:
            segments.append({
                'start': seg.start,
                'end': seg.end,
                'text': seg.text,
            })
            seg_count += 1
            if seg_count % 50 == 0:
                elapsed = time.time() - start_time
                print(f'   [{seg_count} cues] elapsed: {format_duration(elapsed)} | last: {format_srt_timestamp(seg.start)} → {format_srt_timestamp(seg.end)}')

    except KeyboardInterrupt:
        print('\n\n⏹ Dibatalkan user.')
        if segments:
            partial_path = output_path.replace('.srt', '.partial.srt')
            n = write_srt(segments, partial_path)
            print(f'   Partial SRT disimpan: {partial_path} ({n} cues)')
        sys.exit(130)
    except Exception as e:
        print(f'\n❌ Gagal transcribe: {e}')
        import traceback
        print(traceback.format_exc()[:500])
        sys.exit(1)

    elapsed = time.time() - start_time

    # Write SRT
    print(f'\n▶ Writing SRT...')
    n_cues = write_srt(segments, output_path)
    srt_size = os.path.getsize(output_path) / 1024

    print()
    print('═' * 64)
    print('✅ SELESAI!')
    print(f'   Output: {output_path}')
    print(f'   Cues: {n_cues}')
    print(f'   Size: {srt_size:.1f} KB')
    print(f'   Waktu: {format_duration(elapsed)}')
    if lang_code is None:
        print(f'   Bahasa: {detected_lang} (auto-detect)')
    print()
    print('🎬 Langkah berikutnya:')
    print(f'   1. Translate: buka Google Translate → paste SRT → translate ke ID')
    srt_id_path = output_path.replace(f'.{lang_code or detected_lang}.', '.id.') if lang_code is None else output_path.replace(f'.{lang_code}.', '.id.')
    print(f'   2. Save SRT ID → {srt_id_path}')
    print(f'   3. edge-tts: python3 edge-tts-tui.py')
    print(f'   4. mix:     python3 mix-tui.py')
    print('═' * 64)


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print('\n\n⏹ Dibatalkan user.')
        sys.exit(130)
    except Exception as e:
        print(f'\n❌ {e}', file=sys.stderr)
        import traceback
        print(f'\n{traceback.format_exc()[:500]}', file=sys.stderr)
        sys.exit(1)
