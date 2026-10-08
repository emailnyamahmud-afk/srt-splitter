#!/usr/bin/env python3
"""
demucs-tui.py — TUI interaktif untuk Demucs SFX separation

Pisahkan vocals ori (akan dibuang) dari SFX/backsound (akan dipertahankan).
Hasil: no_vocals.wav (SFX bersih) → mix dengan audio dub dari web app.

Hardware acceleration di M1/M2/M3 (Apple Silicon):
  --device mps  (Metal Performance Shaders, 3-5x lebih cepat dari CPU)
  --device cpu  (fallback, kalau MPS bermasalah)

Install (sekali saja):
  pip3 install demucs
  # Atau: pip3 install demucs --break-system-packages (kalau Mac blocked pip)

Usage:
  python3 demucs-tui.py
  (pilih file pakai arrow keys, ikuti 6 step)

Output:
  output/{model}/{namafile}/no_vocals.wav  (SFX bersih, tanpa vocals ori)
  output/{model}/{namafile}/vocals.wav      (vocals ori, akan dibuang)

Workflow integrasi (mode ON + Smart Fit + mix):
  Fase 0: demucs-tui.py → no_vocals.wav (SFX bersih)
  Fase 1: Web app mode ON + Smart Fit → audio-id-dub.wav (dialog dub)
  Fase 2: mix-audio-dub.py --sfx-wav no_vocals.wav --audio-dub audio-id-dub.wav
"""

import os
import sys
import glob
import shutil
import subprocess
from pathlib import Path

try:
    import questionary
except ImportError:
    print('\n❌ Library "questionary" belum terinstall.')
    print('   Install dengan: pip3 install questionary')
    print('   Atau:           pip3 install questionary --break-system-packages')
    print()
    sys.exit(1)


# ============================================================
# Helper functions
# ============================================================

def clear_screen():
    os.system('clear' if os.name != 'nt' else 'cls')


def print_banner():
    clear_screen()
    print('╔' + '═' * 64 + '╗')
    print('║  🎵 Demucs SFX Separator (TUI Mode)' + ' ' * 25 + '║')
    print('║  Pisahkan vocals ori dari SFX (musik, efek, ambience)' + '   ' + '║')
    print('╚' + '═' * 64 + '╝')
    print()


def find_files_in_cwd(extensions):
    """Cari file dengan extension tertentu di current working dir."""
    files = []
    cwd = os.getcwd()
    for ext in extensions:
        for f in glob.glob(os.path.join(cwd, f'*.{ext}')):
            files.append(os.path.basename(f))
        for f in glob.glob(os.path.join(cwd, f'*.{ext.upper()}')):
            files.append(os.path.basename(f))
    files.sort()
    return files


def select_file(prompt, extensions, default=None):
    """Pilih file pakai questionary select (arrow keys)."""
    available = find_files_in_cwd(extensions)
    if not available:
        print(f'  ℹ Tidak ada file {" / ".join(extensions)} di folder ini.')
        path = questionary.text(
            f'{prompt} (ketik path lengkap):',
            default=default or '',
        ).ask()
        return path
    choices = available + ['[Ketik path manual]']
    selected = questionary.select(
        prompt,
        choices=choices,
        default=available[0] if available else choices[-1],
    ).ask()
    if selected == '[Ketik path manual]':
        return questionary.text(f'{prompt} (ketik path lengkap):', default=default or '').ask()
    return selected


def check_demucs():
    """Cek apakah Demucs terinstall."""
    demucs_bin = shutil.which('demucs') or shutil.which('demucs.exe')
    if not demucs_bin:
        print('❌ Demucs belum terinstall.')
        print()
        print('   Install dengan:')
        print('   pip3 install demucs')
        print('   # Atau: pip3 install demucs --break-system-packages')
        print()
        print('   Cek sukses: demucs --help')
        print()
        sys.exit(1)
    return demucs_bin


def detect_device():
    """Deteksi device optimal: MPS untuk Apple Silicon, CPU fallback."""
    # Cek apakah MPS tersedia (Apple Silicon)
    try:
        result = subprocess.run([
            sys.executable, '-c',
            'import torch; print("mps" if torch.backends.mps.is_available() else "cpu")'
        ], capture_output=True, text=True, timeout=5)
        if result.returncode == 0 and 'mps' in result.stdout:
            return 'mps'
    except Exception:
        pass
    return 'cpu'


# ============================================================
# Main TUI flow
# ============================================================

def main():
    print_banner()

    # Cek Demucs terinstall
    demucs_bin = check_demucs()
    print(f'Demucs: {demucs_bin}')

    # Cek device
    detected_device = detect_device()
    if detected_device == 'mps':
        print('✓ Apple Silicon terdeteksi — MPS (Metal) acceleration tersedia')
    else:
        print('ℹ MPS tidak tersedia — akan pakai CPU (lebih lambat)')
    print()

    print('📋 Step-by-step, ikuti petunjuk di layar.')
    print('   Navigasi: ↑↓ arrow keys, Enter konfirmasi, q batal')
    print()

    # Step 1: Pilih file audio/video
    print('▶ Step 1/6: Pilih file MP4/audio ori')
    input_file = select_file(
        'File MP4/audio ori (mis. mp4-ori-test-7min.mp4):',
        ['mp4', 'wav', 'm4a', 'flac', 'mp3', 'opus', 'webm', 'ogg'],
    )
    if not input_file:
        print('Batal.')
        sys.exit(0)
    print(f'  ✓ {input_file}')
    print()

    # Step 2: Pilih output directory
    print('▶ Step 2/6: Pilih output directory')
    output_dir = questionary.text(
        'Output directory (default: ./output):',
        default='./output',
    ).ask()
    if not output_dir:
        output_dir = './output'
    print(f'  ✓ {output_dir}')
    print()

    # Step 3: Pilih model
    print('▶ Step 3/6: Pilih model Demucs')
    model = questionary.select(
        'Model:',
        choices=[
            'htdemucs (default, cepat, kualitas bagus) — REKOMENDASI',
            'htdemucs_ft (fine-tuned, lebih lambat, kualitas terbaik)',
            'mdx (legacy, paling cepat, kualitas menengah)',
        ],
        default='htdemucs (default, cepat, kualitas bagus) — REKOMENDASI',
    ).ask()
    model_name = model.split(' ')[0]  # 'htdemucs', 'htdemucs_ft', 'mdx'
    print(f'  ✓ {model_name}')
    print()

    # Step 4: Pilih mode
    print('▶ Step 4/6: Pilih mode separation')
    mode = questionary.select(
        'Mode:',
        choices=[
            'two-stems vocals (CEPAT, rekomendasi untuk dubbing) — REKOMENDASI',
            'four-stems (drums/bass/other/vocals, untuk music production)',
        ],
        default='two-stems vocals (CEPAT, rekomendasi untuk dubbing) — REKOMENDASI',
    ).ask()
    use_two_stems = 'two-stems' in mode
    print(f'  ✓ {"two-stems vocals" if use_two_stems else "four-stems"}')
    print()

    # Step 5: Pilih device
    print('▶ Step 5/6: Pilih device (hardware acceleration)')
    if detected_device == 'mps':
        device = questionary.select(
            'Device:',
            choices=[
                f'mps (Apple GPU, 3-5x cepat) — REKOMENDASI (terdeteksi)',
                'cpu (fallback, kalau MPS bermasalah)',
            ],
            default=f'mps (Apple GPU, 3-5x cepat) — REKOMENDASI (terdeteksi)',
        ).ask()
    else:
        device = questionary.select(
            'Device:',
            choices=[
                'cpu (MPS tidak terdeteksi, pakai CPU)',
            ],
            default='cpu (MPS tidak terdeteksi, pakai CPU)',
        ).ask()
    device_name = device.split(' ')[0]  # 'mps' atau 'cpu'
    print(f'  ✓ {device_name}')
    print()

    # Step 6: Konfirmasi
    print('▶ Step 6/6: Konfirmasi')

    # Estimasi waktu (rough, berdasarkan audio durasi)
    input_size_mb = os.path.getsize(input_file) / 1024 / 1024 if os.path.isfile(input_file) else 0
    if device_name == 'mps':
        est_min = max(2, int(input_size_mb / 10))  # rough: 10MB per menit MPS
        est_label = f'~{est_min} menit (MPS)'
    else:
        est_min = max(5, int(input_size_mb / 4))  # rough: 4MB per menit CPU
        est_label = f'~{est_min} menit (CPU)'

    print()
    print('╔' + '═' * 64 + '╗')
    print('║  📋 Ringkasan:' + ' ' * 49 + '║')
    print('╠' + '═' * 64 + '╣')
    print(f'║  Input  : {input_file[:46]:<46}║')
    print(f'║  Output : {output_dir[:46]:<46}║')
    print(f'║  Model  : {model_name[:46]:<46}║')
    print(f'║  Mode   : {"two-stems vocals" if use_two_stems else "four-stems":<46}║')
    print(f'║  Device : {device_name[:46]:<46}║')
    print(f'║  Estimasi: {est_label[:46]:<46}║')
    print('╚' + '═' * 64 + '╝')
    print()

    # Tampilkan command yang akan dijalankan
    cmd_args = ['-n', model_name, '--device', device_name, '-o', output_dir]
    if use_two_stems:
        cmd_args.extend(['--two-stems', 'vocals'])
    cmd_args.append(input_file)

    print('=== Command yang akan dijalankan ===')
    print(f'demucs {" ".join(cmd_args)}')
    print('=== End command ===')
    print()

    # Konfirmasi
    confirm = questionary.confirm('Lanjut eksekusi?', default=True).ask()
    if not confirm:
        print('Batal.')
        sys.exit(0)

    # Eksekusi
    print('\n' + '═' * 64)
    print('🚀 Mulai Demucs separation...')
    print('═' * 64 + '\n')

    cmd = [demucs_bin] + cmd_args
    try:
        result = subprocess.run(cmd)
        exit_code = result.returncode
    except KeyboardInterrupt:
        print('\n\n⏹ Dibatalkan user.')
        sys.exit(130)

    print()
    if exit_code == 0:
        print('═' * 64)
        print('✅ SELESAI!')
        print()
        # Cek output file
        base_name = Path(input_file).stem
        # Demucs output: {output_dir}/{model}/{base_name}/no_vocals.wav
        model_output_dir = Path(output_dir) / model_name / base_name
        if use_two_stems:
            no_vocals = model_output_dir / 'no_vocals.wav'
            vocals = model_output_dir / 'vocals.wav'
            if no_vocals.exists():
                size_mb = no_vocals.stat().st_size / 1024 / 1024
                print(f'📁 Output:')
                print(f'   SFX (no_vocals.wav): {no_vocals} ({size_mb:.1f} MB)')
                print(f'   → Pakai ini untuk mix-audio-dub.py --sfx-wav')
            if vocals.exists():
                size_mb = vocals.stat().st_size / 1024 / 1024
                print(f'   Vocals ori (vocals.wav): {vocals} ({size_mb:.1f} MB)')
                print(f'   → Bisa dibuang (tidak dipakai untuk dubbing)')
        else:
            # four-stems
            stems = ['drums', 'bass', 'other', 'vocals']
            print(f'📁 Output (4 stems):')
            for stem in stems:
                stem_path = model_output_dir / f'{stem}.wav'
                if stem_path.exists():
                    size_mb = stem_path.stat().st_size / 1024 / 1024
                    print(f'   {stem}.wav: {stem_path} ({size_mb:.1f} MB)')

        print()
        print('═' * 64)
        print('🎬 Langkah berikutnya (workflow mode ON + Smart Fit):')
        print()
        print('   1. Web app: mode ON + Smart Fit → generate audio-id-dub.wav')
        print('   2. Python mix:')
        if use_two_stems and no_vocals.exists():
            print(f'      python3 mix-audio-dub.py \\')
            print(f'        --mp4 {input_file} \\')
            print(f'        --audio-dub audio-id-dub.wav \\')
            print(f'        --sfx-wav {no_vocals} \\')
            print(f'        --output mp4-id-final.mp4')
        print('═' * 64)
    else:
        print('═' * 64)
        print(f'❌ GAGAL dengan exit code {exit_code}')
        print()
        print('Cek error message di atas. Umumnya:')
        print('  - "No module named torch" → pip3 install torch')
        print('  - MPS error → coba --device cpu (fallback)')
        print('  - Memory error → audio terlalu panjang, split dulu')
        print('═' * 64)

    sys.exit(exit_code)


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print('\n\n⏹ Dibatalkan user.')
        sys.exit(130)
    except Exception as e:
        print(f'\n❌ Error tidak terduga: {e}', file=sys.stderr)
        import traceback
        print(f'\nStack trace:\n{traceback.format_exc()[:1000]}', file=sys.stderr)
        sys.exit(1)
