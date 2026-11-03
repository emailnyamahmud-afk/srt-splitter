#!/usr/bin/env python3
"""
talkinghead-tui.py v1.0 — TUI #16: Generate talking head video via SadTalker (Replicate)

OPSI TAMBAHAN untuk workflow konten (BUKAN pipeline dubbing).
Untuk dubbing per cue, pakai edge-tts-tui v7.5 (production default Indonesia)
atau gemini-tts-tui v1.1 (Indonesia + Jawa).

talkinghead-tui untuk workflow KONTEN (bukan film dubbing):
  - Foto green screen half-body (mis. Amat with blangkon + batik)
  - Audio narasi Jawa (dari gemini-tts-tui v1.1 Narration mode JV)
  - Output MP4 talking head dengan green screen DIPERTAHANKAN
  - User edit manual: chroma key → composite background → final YouTube konten

Workflow:
  naskah.txt → gemini-tts-tui v1.1 Narration mode (JV) → narasi-jawa.wav
                ↓
                + foto green screen (mis. amat-avatar.jpg)
                ↓
                talkinghead-tui v1.0 (Replicate SadTalker, preprocess=full, still, gfpgan)
                ↓
                → HDD/konten/{name}-talking-green.mp4 (green screen preserved)
                ↓
                User edit (Final Cut / DaVinci / Premiere):
                - Chroma key green
                - Composite dengan background baru (foto sejarah, kantor, dll)
                - Tambah text overlay (kalau perlu)
                → final-konten.mp4 (siap YouTube)

Kenapa Replicate (BUKAN M1 lokal)?
  - SadTalker di M1: Python 3.8 strict, banyak code hardcode CUDA, MPS support partial
    (Issue #526 open), speed lambat (community bilang "very slow")
  - Replicate: 17 detik per run, ~$0.05-0.20 per video, A100 80GB
  - Untuk konten sejarah (volume rendah-sedang), cloud lebih realistis

Install:
  pip3 install replicate requests questionary
  brew install ffmpeg  # sudah ada kalau pakai edge-tts-tui

Env:
  REPLICATE_API_TOKEN  — wajib. Dapatkan di https://replicate.com/account/api-tokens
                         (free $0.10 credit untuk test, lalu pay-as-you-go)
                         Taruh di HDD .env:
                           echo "REPLICATE_API_TOKEN=r8_xxx" >> /Volumes/HDD/Dubbing/.env
                         config.py load_env() akan load otomatis saat TUI start.

Usage:
  python3 talkinghead-tui.py
  (pilih source image, audio, mode → generate → MP4)

Output:
  {output_dir}/{audio-stem}-talking-green.mp4 (default: HDD/konten/)
  → Compatible dengan review-mix-tui #13 (kalau mau pakai background video,
    bukan static background)
  → Compatible dengan konten-tui #14 (kalau mau composite dengan Ken Burns images)

Status: ⚠ UNTESTED (code di GitHub, belum diuji di Mac) — sampai user VLC feedback OK
"""

import os
import sys
import shutil
from pathlib import Path

# ============================================================
# Version
# ============================================================

VERSION = 'v1.0'

# ============================================================
# Track missing deps
# ============================================================

_MISSING_DEPS = []

try:
    import questionary
except ImportError:
    _MISSING_DEPS.append('questionary')

# replicate + requests: cek via import-test, jangan import full dulu (lazy)
try:
    import replicate  # noqa
    HAS_REPLICATE = True
except ImportError:
    HAS_REPLICATE = False
    _MISSING_DEPS.append('replicate')

try:
    import requests  # noqa
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False
    _MISSING_DEPS.append('requests')

if _MISSING_DEPS:
    print()
    print('═' * 64)
    print('❌ Dependensi belum lengkap!')
    print('═' * 64)
    print()
    print(f'   Missing: {", ".join(_MISSING_DEPS)}')
    print()
    print('   Install dengan:')
    print()
    print('   pip3 install ' + ' '.join(_MISSING_DEPS))
    print()
    print('   Atau install semua deps sekaligus:')
    print()
    print('   pip3 install replicate requests questionary')
    print()
    print('   Kalau pip3 ditolak (Mac blocked), pakai --break-system-packages:')
    print()
    print('   pip3 install --break-system-packages replicate requests questionary')
    print()
    print('   Verifikasi:')
    print()
    print('   python3 -c "import replicate, requests, questionary; print(\'OK\')"')
    print()
    print('═' * 64)
    sys.exit(1)

# ffmpeg wajib (kalau user mau re-encode output nanti)
if not shutil.which('ffmpeg'):
    print()
    print('═' * 64)
    print('❌ ffmpeg belum terinstall!')
    print('═' * 64)
    print()
    print('   Install dengan Homebrew:')
    print()
    print('   brew install ffmpeg')
    print()
    print('   Verifikasi: ffmpeg -version')
    print()
    print('═' * 64)
    sys.exit(1)

# Import backend (lazy loader untuk replicate/requests)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from talkinghead_backend import (
    generate_talking_head,
    estimate_cost,
    get_audio_duration_seconds,
    A100_RATE_PER_SECOND,
    SADTALKER_PREPROCESS_MODES,
    ENHANCER_OPTIONS,
    DEFAULT_PREPROCESS,
    DEFAULT_ENHANCER,
    MODEL_ID,
    RETRY_BACKOFF,
)


# ============================================================
# TUI helpers (port dari edge-tts-tui.py v7.5)
# ============================================================

def clear_screen():
    os.system('clear' if os.name != 'nt' else 'cls')


def print_banner():
    clear_screen()
    pid_str = f'PID {os.getpid()}'
    title = f'🎙️  Talking Head TUI {VERSION} ({pid_str})'
    pad_title = max(0, 66 - len(title) - 2)
    print('╔' + '═' * 64 + '╗')
    print('║  ' + title + ' ' * pad_title + '║')
    print('║  TUI #16 | SadTalker via Replicate | green screen preserved' + ' ' * 3 + '║')
    print('╚' + '═' * 64 + '╝')
    print()
    print('  📋 Workflow:')
    print('     1. foto green screen + narasi-JV.wav → SadTalker (Replicate)')
    print('     2. Output MP4 dengan green screen DIPERTAHANKAN (preprocess=full)')
    print('     3. User edit manual: chroma key → composite background → final')
    print()
    print('  ⚠ Status: UNTESTED (code di GitHub, belum diuji di Mac)')
    print('  ⚠ Butuh: REPLICATE_API_TOKEN di /Volumes/HDD/Dubbing/.env')
    print('  ⚠ Cost: ~$0.05-0.20 per video (Replicate pay-as-you-go)')
    print()


def find_image_files(search_dirs):
    """Cari file image (.jpg/.png) di list directory."""
    files = []
    for d in search_dirs:
        if not Path(d).exists():
            continue
        for ext in ('jpg', 'jpeg', 'png'):
            for f in Path(d).glob(f'*.{ext}'):
                files.append(str(f))
            for f in Path(d).glob(f'*.{ext.upper()}'):
                files.append(str(f))
    # Dedupe + sort
    seen = set()
    unique = []
    for f in files:
        if f not in seen:
            seen.add(f)
            unique.append(f)
    return sorted(unique)


def find_audio_files(search_dirs):
    """Cari file audio (.wav) di list directory."""
    files = []
    for d in search_dirs:
        if not Path(d).exists():
            continue
        for ext in ('wav', 'WAV'):
            for f in Path(d).glob(f'*.{ext}'):
                files.append(str(f))
    # Dedupe + sort
    seen = set()
    unique = []
    for f in files:
        if f not in seen:
            seen.add(f)
            unique.append(f)
    return sorted(unique)


def format_duration(seconds: float) -> str:
    """Format detik → HH:MM:SS atau MM:SS untuk display."""
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


def append_cost_log(log_path: str, source_image: str, audio_path: str,
                    audio_dur: float, gpu_seconds, cost_usd: float,
                    preprocess: str, still: bool, enhancer: str,
                    output_path: str):
    """Append entry ke log file cost (CSV-like format, 1 line per run).

    Format: timestamp | source | audio | audio_dur | gpu_s | cost | mode | output
    """
    from datetime import datetime
    ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    gpu_str = f"{gpu_seconds:.1f}" if gpu_seconds is not None else "unknown"
    cost_str = f"{cost_usd:.4f}" if cost_usd is not None else "unknown"
    mode_str = f"{preprocess}+still={still}+{enhancer}"
    line = (f"{ts} | {os.path.basename(source_image)} | {os.path.basename(audio_path)} | "
            f"{audio_dur:.1f}s audio | {gpu_str}s GPU | ${cost_str} | {mode_str} | {output_path}\n")
    try:
        os.makedirs(os.path.dirname(log_path) or '.', exist_ok=True)
        with open(log_path, 'a', encoding='utf-8') as f:
            f.write(line)
        return True
    except OSError as e:
        print(f"  ⚠ Gagal tulis cost log: {e}", file=sys.stderr)
        return False


def read_cost_log_summary(log_path: str):
    """Baca log file cost, return summary {runs, total_cost, avg_cost}.

    Return None kalau file tidak ada / kosong.
    """
    if not os.path.isfile(log_path):
        return None
    try:
        with open(log_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        if not lines:
            return None
        runs = 0
        total_cost = 0.0
        for line in lines:
            # Format: ts | source | audio | Xs audio | Ys GPU | $Z | mode | output
            parts = line.split(' | ')
            if len(parts) >= 6:
                runs += 1
                cost_str = parts[5].strip().lstrip('$')
                try:
                    total_cost += float(cost_str)
                except ValueError:
                    pass  # 'unknown' cost → skip
        return {
            'runs': runs,
            'total_cost': total_cost,
            'avg_cost': total_cost / runs if runs > 0 else 0,
        }
    except OSError:
        return None


# ============================================================
# Main TUI flow — 6 step
# ============================================================

def main():
    print_banner()

    # === Cek REPLICATE_API_TOKEN (load .env dari config.py kalau ada) ===
    if not os.environ.get('REPLICATE_API_TOKEN'):
        try:
            from config import load_env, ENV_FILE
            if load_env():
                print(f'  ✓ Loaded .env dari {ENV_FILE}')
            else:
                print(f'  ⚠ .env tidak ditemukan di {ENV_FILE}')
        except ImportError:
            print('  ⚠ config.py tidak ditemukan (jalankan dari ~/Dubbing/ dengan config.py tersedia)')

    if not os.environ.get('REPLICATE_API_TOKEN'):
        print()
        print('═' * 64)
        print('❌ REPLICATE_API_TOKEN belum di-set!')
        print('═' * 64)
        print()
        print('   Dapatkan API token di: https://replicate.com/account/api-tokens')
        print('   (free $0.10 credit untuk test, lalu pay-as-you-go)')
        print()
        print('   Set di env (session sementara):')
        print('     export REPLICATE_API_TOKEN=r8_xxxxx')
        print()
        print('   Atau simpan permanen di HDD .env (recommended):')
        print('     echo "REPLICATE_API_TOKEN=r8_xxx" >> /Volumes/HDD/Dubbing/.env')
        print('   (config.py load_env() akan load otomatis saat TUI start)')
        print()
        print('═' * 64)
        sys.exit(1)
    print(f'  ✓ REPLICATE_API_TOKEN: {os.environ.get("REPLICATE_API_TOKEN", "")[:10]}...')
    print()

    print('📋 Pilihan: ikuti petunjuk di layar.')
    print('   Navigasi: ↑↓ arrow keys, Enter konfirmasi, Ctrl+C batal')
    print()

    # === Setup paths dari config.py ===
    try:
        from config import KONTEN_DIR, TTS_DIR, INPUT_DIR, ensure_hdd
        hdd_ok = ensure_hdd()
    except ImportError:
        # Fallback kalau config.py tidak ada (sandbox / cwd)
        KONTEN_DIR = Path(os.getcwd()) / 'konten'
        TTS_DIR = Path(os.getcwd()) / 'tts'
        INPUT_DIR = Path(os.getcwd()) / 'input'
        hdd_ok = False

    default_search_imgs = [str(KONTEN_DIR), str(INPUT_DIR), os.getcwd()] if hdd_ok else [os.getcwd()]
    default_search_audios = [str(TTS_DIR), os.getcwd()] if hdd_ok else [os.getcwd()]
    default_out_dir = str(KONTEN_DIR) if hdd_ok else os.getcwd()

    # === Step 1: Pilih source image (foto green screen) ===
    print('▶ Step 1/6: Pilih source image (foto green screen half-body)')
    img_files = find_image_files(default_search_imgs)
    if img_files:
        img_choices = [os.path.basename(f) for f in img_files] + ['[Ketik path manual]']
        img_choice = questionary.select(
            f'Source image (ditemukan {len(img_files)} di {", ".join(default_search_imgs)}):',
            choices=img_choices,
            default=img_choices[0],
        ).ask()
        if img_choice == '[Ketik path manual]':
            source_image = questionary.text('Path source image:').ask()
        else:
            source_image = ''
            for f in img_files:
                if os.path.basename(f) == img_choice:
                    source_image = f
                    break
    else:
        source_image = questionary.text(
            f'Tidak ada image di {default_search_imgs}. Ketik path lengkap:',
            default='',
        ).ask()
    if not source_image or not os.path.isfile(source_image):
        print('❌ File source image tidak ditemukan.')
        sys.exit(1)
    print(f'  ✓ {source_image}')
    print()

    # === Step 2: Pilih driven audio (narasi wav) ===
    print('▶ Step 2/6: Pilih driven audio (.wav, narasi dari gemini-tts-tui #15)')
    aud_files = find_audio_files(default_search_audios)
    if aud_files:
        aud_choices = [os.path.basename(f) for f in aud_files] + ['[Ketik path manual]']
        aud_choice = questionary.select(
            f'Driven audio (ditemukan {len(aud_files)} di {", ".join(default_search_audios)}):',
            choices=aud_choices,
            default=aud_choices[0],
        ).ask()
        if aud_choice == '[Ketik path manual]':
            driven_audio = questionary.text('Path driven audio:').ask()
        else:
            driven_audio = ''
            for f in aud_files:
                if os.path.basename(f) == aud_choice:
                    driven_audio = f
                    break
    else:
        driven_audio = questionary.text(
            f'Tidak ada .wav di {default_search_audios}. Ketik path lengkap:',
            default='',
        ).ask()
    if not driven_audio or not os.path.isfile(driven_audio):
        print('❌ File driven audio tidak ditemukan.')
        sys.exit(1)
    print(f'  ✓ {driven_audio}')
    print()

    # === Step 3: Output MP4 path ===
    print('▶ Step 3/6: Pilih output MP4 path')
    audio_stem = Path(driven_audio).stem
    default_output = os.path.join(default_out_dir, f'{audio_stem}-talking-green.mp4')
    output_mp4 = questionary.text(
        'Output MP4 (background green screen akan dipertahankan):',
        default=default_output,
    ).ask()
    if not output_mp4:
        output_mp4 = default_output
    os.makedirs(os.path.dirname(output_mp4) or '.', exist_ok=True)
    print(f'  ✓ {output_mp4}')
    print()

    # === Step 4: Preprocess mode ===
    print('▶ Step 4/6: Pilih preprocess mode SadTalker')
    preprocess_labels = [f'{m[0]:10s} — {m[1]}' for m in SADTALKER_PREPROCESS_MODES]
    preprocess_label = questionary.select(
        'Preprocess mode (full = RECOMMENDED untuk green screen):',
        choices=preprocess_labels,
        default=[l for l in preprocess_labels if l.startswith('full')][0],
    ).ask()
    preprocess = preprocess_label.split(' — ')[0].strip()
    print(f'  ✓ {preprocess}')
    if preprocess in ('crop', 'extcrop'):
        print(f'  ⚠ Warning: {preprocess} mode = face only, green screen akan hilang!')
        print(f'    Untuk green screen workflow, pakai "full" atau "extfull".')
        confirm = questionary.confirm('Lanjut dengan crop mode?', default=False).ask()
        if not confirm:
            print('Batal.')
            sys.exit(0)
    print()

    # === Step 5: Still mode ===
    print('▶ Step 5/6: Pilih still mode (gerakan kepala)')
    still_choice = questionary.select(
        'Still mode:',
        choices=[
            'yes — --still (kurangi gerakan kepala, cocok presenter formal dengan tangan clasped)',
            'no  --no-still (lebih natural head movement, untuk dialog dramatis)',
        ],
        default='yes — --still (kurangi gerakan kepala, cocok presenter formal dengan tangan clasped)',
    ).ask()
    still = 'yes' in still_choice
    print(f'  ✓ still={still}')
    print()

    # === Step 6: Enhancer ===
    print('▶ Step 6/6: Pilih enhancer')
    enhancer_labels = [f'{e[0]:10s} — {e[1]}' for e in ENHANCER_OPTIONS]
    enhancer_label = questionary.select(
        'Enhancer (gfpgan = tajpkan gigi + mata, penting untuk clean chroma key):',
        choices=enhancer_labels,
        default=enhancer_labels[0],
    ).ask()
    enhancer = enhancer_label.split(' — ')[0].strip()
    print(f'  ✓ {enhancer}')
    print()

    # === Baca durasi audio untuk estimasi cost ===
    audio_dur = get_audio_duration_seconds(driven_audio)
    audio_dur_str = format_duration(audio_dur) if audio_dur > 0 else '(tidak terdeteksi)'

    # === Estimasi cost SEBELUM run ===
    if audio_dur > 0:
        est = estimate_cost(audio_dur, preprocess, still, enhancer)
        est_min_cost = est['min_cost_usd']
        est_max_cost = est['max_cost_usd']
        est_min_gpu = est['min_gpu_seconds']
        est_max_gpu = est['max_gpu_seconds']
    else:
        est_min_cost = est_max_cost = None
        est_min_gpu = est_max_gpu = None

    # === Ringkasan + Estimasi SEBELUM ===
    print('╔' + '═' * 64 + '╗')
    print('║  📋 Ringkasan:' + ' ' * 49 + '║')
    print('╠' + '═' * 64 + '╣')
    print(f'║  Source : {os.path.basename(source_image)[:46]:<46}║')
    print(f'║  Audio  : {os.path.basename(driven_audio)[:46]:<46}║')
    print(f'║  Output : {output_mp4[:46]:<46}║')
    print(f'║  Mode   : {preprocess[:46]:<46}║')
    print(f'║  Still  : {str(still)[:46]:<46}║')
    print(f'║  Enhanc : {enhancer[:46]:<46}║')
    print(f'║  Model  : {"Replicate cjwbw/sadtalker"[:46]:<46}║')
    print('╚' + '═' * 64 + '╝')
    print()
    print(f'  📊 Audio durasi: {audio_dur_str}' + (f' ({audio_dur:.1f}s)' if audio_dur > 0 else ''))
    if est_min_cost is not None:
        print(f'  💰 ESTIMASI biaya (A100 80GB = ${A100_RATE_PER_SECOND:.4f}/detik):')
        print(f'     GPU time: {est_min_gpu:.0f}s - {est_max_gpu:.0f}s (mode: {preprocess}+still={still}+{enhancer})')
        print(f'     Cost   : ${est_min_cost:.3f} - ${est_max_cost:.3f}')
        print(f'     (rata-rata ~${(est_min_cost + est_max_cost) / 2:.3f})')
    else:
        print(f'  ⚠ Estimasi skip — durasi audio tidak terdeteksi (lihat ffprobe)')
    print()
    print(f'  ⚠ Output akan punya GREEN SCREEN preserved → siap chroma key manual')
    print()

    # Tampilkan spending history dari log file (kalau ada)
    cost_log_path = os.path.join(os.path.dirname(output_mp4) or '.', '.talkinghead-costs.log')
    spending = read_cost_log_summary(cost_log_path)
    if spending:
        print(f'  📁 Spending history (dari {os.path.basename(cost_log_path)}):')
        print(f'     Total {spending["runs"]} run, total cost ${spending["total_cost"]:.3f}, rata-rata ${spending["avg_cost"]:.3f}/run')
        print()

    if not questionary.confirm('Lanjut generate?', default=True).ask():
        print('Batal.')
        sys.exit(0)

    # === Generate via Replicate ===
    print('\n' + '═' * 64)
    print(f'🚀 Generate talking head via Replicate (model: {MODEL_ID})...')
    print('═' * 64 + '\n')

    result = generate_talking_head(
        source_image_path=source_image,
        driven_audio_path=driven_audio,
        output_mp4_path=output_mp4,
        preprocess=preprocess,
        still=still,
        enhancer=enhancer,
        verbose=True,
    )

    if not result.get('success'):
        print()
        print('═' * 64)
        print(f'❌ Gagal generate. {result.get("error", "")}')
        print('═' * 64)
        sys.exit(1)

    # === Real cost SESUDAH run ===
    gpu_s = result.get('gpu_seconds')
    cost_usd = result.get('cost_usd')
    wall_s = result.get('wall_clock_seconds', 0)
    size_mb = result.get('output_size_mb', 0)

    # Append ke log file
    append_cost_log(
        log_path=cost_log_path,
        source_image=source_image,
        audio_path=driven_audio,
        audio_dur=audio_dur if audio_dur > 0 else 0.0,
        gpu_seconds=gpu_s,
        cost_usd=cost_usd if cost_usd is not None else 0.0,
        preprocess=preprocess, still=still, enhancer=enhancer,
        output_path=output_mp4,
    )

    # Bandingkan estimasi vs real (untuk feedback akurasi)
    print()
    print('═' * 64)
    print('✅ SELESAI!')
    print(f'  ⏱ Wall-clock total: {wall_s:.1f}s')
    if gpu_s is not None:
        print(f'  📊 GPU time (Replicate): {gpu_s:.1f}s')
        print(f'  💰 REAL cost: {gpu_s:.1f} × ${A100_RATE_PER_SECOND:.4f} = ${cost_usd:.4f}')
        # Bandingkan estimasi
        if est_min_cost is not None:
            if cost_usd < est_min_cost:
                print(f'     (lebih MURAH dari estimasi min ${est_min_cost:.3f} — bagus!)')
            elif cost_usd > est_max_cost:
                print(f'     (lebih MAHAL dari estimasi max ${est_max_cost:.3f} — multiplier update?)')
            else:
                print(f'     (dalam range estimasi ${est_min_cost:.3f}-${est_max_cost:.3f} — akurat ✓)')
    else:
        print(f'  ⚠ GPU time tidak tersedia dari Replicate metrics (cek dashboard)')
        print(f'     Lihat: https://replicate.com/predictions → cari run terbaru → "Compute time"')
    print(f'  📁 Output: {output_mp4}')
    print(f'  📦 Size: {size_mb:.1f} MB')
    print()

    # Tampilkan log file path + total spending
    print(f'  📝 Cost log: {cost_log_path}')
    spending_now = read_cost_log_summary(cost_log_path)
    if spending_now:
        print(f'     Total {spending_now["runs"]} run, total ${spending_now["total_cost"]:.3f}, rata-rata ${spending_now["avg_cost"]:.3f}/run')
    print()
    print('🎬 Langkah berikutnya (chroma key manual):')
    print('   1. Buka output MP4 di Final Cut / DaVinci / Premiere')
    print('   2. Tambah chroma key effect (hilangkan green screen)')
    print('   3. Composite dengan background baru:')
    print('      - Foto sejarah (untuk konten tokoh/sejarah)')
    print('      - Kantor / ruang adat (untuk MC Jawa)')
    print('      - Video B-roll (untuk konten dokumenter)')
    print('   4. Tambah text overlay (judul, nama tokoh, dll) — opsional')
    print('   5. Export → final-konten.mp4 (siap upload YouTube)')
    print()
    print('   Atau pakai workflow berikut (kalau background = static image):')
    print('   - background.jpg → konten-tui #14 (Ken Burns effect)')
    print('   - background.mp4 → review-mix-tui #13 (mix dengan video source)')
    print('═' * 64)


# ============================================================
# KeyboardInterrupt handler
# ============================================================

def _cleanup_handler(signum, frame):
    """Ctrl+C → exit."""
    print('\n\n⏹ Dibatalkan user.')
    sys.exit(1)


import signal
signal.signal(signal.SIGINT, _cleanup_handler)


if __name__ == '__main__':
    main()
