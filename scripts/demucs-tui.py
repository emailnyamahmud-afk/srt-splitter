#!/usr/bin/env python3
"""
demucs-tui.py — TUI interaktif untuk Demucs SFX separation

Pisahkan vocals ori (akan dibuang) dari SFX/backsound (akan dipertahankan).
Hasil: no_vocals.mp3 (SFX bersih) → mix dengan audio dub dari web app.

Output format: MP3 320 kbps (hemat space ~10x dibanding WAV).
  - WAV 16-bit stereo 44.1kHz untuk audio 2 jam ≈ 1.3 GB
  - MP3 320 kbps untuk audio 2 jam ≈ 140 MB (90% lebih kecil)
  - Source biasanya sudah lossy (Opus/MP3 dari yt-dlp) → MP3 320 cukup
  - SFX = musik/efek/ambience (bukan dialog) → ear tidak sensitif seperti vocal

Vocals ori auto-dihapus setelah separation selesai (tidak dipakai untuk dubbing).
Demucs --mp3 flag menggantikan WAV dengan MP3 (bukan menambah), jadi output hanya .mp3.

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
  output/{model}/{namafile}/no_vocals.mp3  (SFX bersih, MP3 320 kbps)
  (vocals.mp3 auto-dihapus setelah separation — tidak dipakai untuk dubbing)

Workflow integrasi (3 fase, bersih):
  Fase 1: yt-dlp         → download MP4 (video) + audio.wav (terpisah)
  Fase 2: demucs-tui.py  → split audio.wav → no_vocals.mp3 (MP3 320, SFX bersih)
                           + vocals.mp3 (auto-hapus, tidak dipakai)
  Fase 3: mix-tui.py    → MP4 + no_vocals.mp3 + audio_dub → mp4-id-final.mp4

Sumber audio_dub (web app Dubbing, 2 mode):
  - Mode ON (lama)  → Bahasa Indonesia, generate full durasi 1 klik,
                      default voice Dimas, output audio-id-dub.wav
                      Status: SUDAH JALAN
  - SRT editor      → Bahasa Jawa, per cue (klik satu-satu)
                      TODO: default Dimas otomatis, Siti manual per cue
                      Output: audio-jw-dub.wav
                      Status: code perlu dibereskan (web app side)
                      Kamus Jawa di Supabase (progressif)

Multi-bahasa output (rencana masa depan, setelah Jawa ready):
  A. Multi-track MP4  — 1 file, switch audio di player (DVD-style)
  B. File terpisah    — 2 MP4 (mp4-id-final + mp4-jw-final)
  C. Hybrid           — 1 MP4 default ID + sidecar wav Jawa
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
    print('║  🎵 Demucs SFX Separator (TUI Mode v2)' + ' ' * 25 + '║')
    print('║  Output MP3 320kbps | vocals ori auto-hapus' + ' ' * 18 + '║')
    print('╚' + '═' * 64 + '╝')
    print()


def find_files_in_dir(search_dir, extensions):
    """Cari file dengan extension tertentu di directory."""
    files = []
    for ext in extensions:
        for f in glob.glob(os.path.join(search_dir, f'*.{ext}')):
            files.append(os.path.basename(f))
        for f in glob.glob(os.path.join(search_dir, f'*.{ext.upper()}')):
            files.append(os.path.basename(f))
    files.sort()
    return files


def select_file(prompt, extensions, search_dir=None, default=None):
    """Pilih file pakai questionary select (arrow keys)."""
    from config import INPUT_DIR, ensure_hdd
    if search_dir is None:
        if ensure_hdd():
            search_dir = str(INPUT_DIR)
        else:
            search_dir = os.getcwd()
    available = find_files_in_dir(search_dir, extensions)
    if not available:
        print(f'  ℹ Tidak ada file {" / ".join(extensions)} di {search_dir}')
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
    # Return full path
    return os.path.join(search_dir, selected)


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
    print('▶ Step 1/7: Pilih file MP4/audio ori')
    input_file = select_file(
        'File MP4/audio ori (mis. mp4-ori-test-7min.mp4):',
        ['mp4', 'wav', 'm4a', 'flac', 'mp3', 'opus', 'webm', 'ogg'],
    )
    if not input_file:
        print('Batal.')
        sys.exit(0)
    print(f'  ✓ {input_file}')
    print()

    # Step 2: Pilih output directory (default: HDD/demucs/)
    print('▶ Step 2/7: Pilih output directory')
    from config import DEMUCS_DIR, ensure_hdd
    default_out = str(DEMUCS_DIR) if ensure_hdd() else './output'
    output_dir = questionary.text(
        'Output directory:',
        default=default_out,
    ).ask()
    if not output_dir:
        output_dir = default_out
    print(f'  ✓ {output_dir}')
    print()

    # Step 3: Pilih model
    print('▶ Step 3/7: Pilih model Demucs')
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
    print('▶ Step 4/7: Pilih mode separation')
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

    # Step 5: Pilih device (hardware acceleration)
    print('▶ Step 5/7: Pilih device (hardware acceleration)')
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

    # Step 6: Pilih segment size (RAM control)
    print('▶ Step 6/7: Pilih segment size (kontrol RAM)')
    segment_choice = questionary.select(
        'Segment size:',
        choices=[
            '3.9 detik (RAM aman, 2x lebih lambat) — REKOMENDASI 16GB',
            '7.8 detik (default, RAM spike di 100%)',
        ],
        default='3.9 detik (RAM aman, 2x lebih lambat) — REKOMENDASI 16GB',
    ).ask()
    segment_size = segment_choice.split(' ')[0]
    print(f'  ✓ segment={segment_size}')
    print()

    # Step 7: Konfirmasi
    print('▶ Step 7/7: Konfirmasi')

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
    print(f'║  Segment: {segment_size + " detik":<46}║')
    print(f'║  Estimasi: {est_label[:46]:<46}║')
    print('╚' + '═' * 64 + '╝')
    print()

    # Tampilkan command yang akan dijalankan
    # Output WAV (bukan MP3) — encode MP3 pakai ffmpeg setelah Demucs (RAM aman)
    cmd_args = ['-n', model_name, '--device', device_name, '--segment', segment_size,
                '-o', output_dir]
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
        print('✅ Demucs separation selesai!')
        print()
        # Cek output file (WAV, bukan MP3)
        base_name = Path(input_file).stem
        model_output_dir = Path(output_dir) / model_name / base_name
        if use_two_stems:
            no_vocals_wav = model_output_dir / 'no_vocals.wav'
            vocals_wav = model_output_dir / 'vocals.wav'
            
            # Auto-hapus vocals.wav (tidak dipakai untuk dubbing)
            if vocals_wav.exists():
                try:
                    v_size = vocals_wav.stat().st_size / 1024 / 1024
                    vocals_wav.unlink()
                    print(f'🗑 Auto-hapus vocals.wav ({v_size:.1f} MB)')
                except OSError as e:
                    print(f'⚠ Gagal hapus vocals.wav: {e}')
            
            if no_vocals_wav.exists():
                wav_size = no_vocals_wav.stat().st_size / 1024 / 1024
                print(f'📁 WAV output: {no_vocals_wav} ({wav_size:.1f} MB)')
                
                # Convert WAV → MP3 pakai ffmpeg (streaming, RAM kecil)
                no_vocals_mp3 = model_output_dir / 'no_vocals.mp3'
                print()
                print('🔄 Convert WAV → MP3 320kbps (ffmpeg streaming)...')
                ffmpeg_bin = shutil.which('ffmpeg')
                if not ffmpeg_bin:
                    print('⚠ ffmpeg tidak ditemukan, WAV tetap ada (tidak di-convert)')
                else:
                    ffmpeg_cmd = [
                        ffmpeg_bin, '-y', '-i', str(no_vocals_wav),
                        '-codec:a', 'libmp3lame', '-b:a', '320k',
                        str(no_vocals_mp3)
                    ]
                    try:
                        subprocess.run(ffmpeg_cmd, capture_output=True)
                        if no_vocals_mp3.exists():
                            mp3_size = no_vocals_mp3.stat().st_size / 1024 / 1024
                            print(f'✅ MP3: {no_vocals_mp3} ({mp3_size:.1f} MB)')
                            # Hapus WAV setelah convert
                            no_vocals_wav.unlink()
                            print(f'🗑 Hapus WAV ({wav_size:.1f} MB) — storage aman')
                        else:
                            print('⚠ Convert gagal, WAV tetap ada')
                    except Exception as e:
                        print(f'⚠ Convert gagal: {e}, WAV tetap ada')
                
                print()
                print(f'   SFX (no_vocals.mp3): {no_vocals_mp3}')
                print(f'   → Pakai ini untuk mix-tui.py (pilih file SFX)')
        else:
            # four-stems
            stems = ['drums', 'bass', 'other', 'vocals']
            print(f'📁 Output (4 stems, WAV):')
            for stem in stems:
                stem_wav = model_output_dir / f'{stem}.wav'
                if stem_wav.exists():
                    size_mb = stem_wav.stat().st_size / 1024 / 1024
                    print(f'   {stem}.wav: {stem_wav} ({size_mb:.1f} MB)')
            # Auto-hapus vocals.wav
            vocals_wav = model_output_dir / 'vocals.wav'
            if vocals_wav.exists():
                try:
                    v_size = vocals_wav.stat().st_size / 1024 / 1024
                    vocals_wav.unlink()
                    print(f'   🗑 Auto-hapus vocals.wav ({v_size:.1f} MB)')
                except OSError as e:
                    print(f'   ⚠ Gagal hapus vocals.wav: {e}')

        print()
        print('═' * 64)
        print('🎬 Langkah berikutnya:')
        print()
        print('   1. edge-tts: python3 edge-tts-tui.py')
        print('   2. mix:      python3 mix-tui.py')
        if use_two_stems and no_vocals_mp3.exists():
            input_path = Path(input_file)
            base = input_path.stem
            if base.endswith('-audio'):
                mp4_name = base[:-6] + '.mp4'
            else:
                mp4_name = base + '.mp4'
            print(f'      → MP4: {mp4_name}  (video dari yt-dlp)')
            print(f'      → SFX: {no_vocals_mp3.name}  ({no_vocals_mp3.parent}/)')
            print(f'      → Dub: audio-id-dub.wav  (dari edge-tts-tui.py)')
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
