#!/usr/bin/env python3
"""
talkinghead_backend.py v1.0 — Backend SadTalker via Replicate untuk talkinghead-tui.py

Panggilan ke Replicate.com API (model cjwbw/sadtalker) untuk generate talking head
video dari 1 foto + 1 audio wav. Output MP4 dengan background dipertahankan
(pakai preprocess=full mode — green screen photo → green screen video).

Kenapa Replicate, bukan M1 lokal?
  - SadTalker di M1: Python 3.8 strict, banyak code hardcode CUDA, MPS support partial
    (Issue #526), speed lambat (community bilang "very slow")
  - Replicate: 17 detik per run, ~$0.05-0.20 per video, model A100 80GB
  - Untuk workflow konten sejarah (volume rendah-sedang), cloud lebih realistis

API:
  - Model: cjwbw/sadtalker (https://replicate.com/cjwbw/sadtalker)
  - Input: source_image (file), driven_audio (file),
           preprocess (full/extfull/crop/extcrop/resize, default full),
           still (bool, default True), enhancer (gfpgan/none, default gfpgan)
  - Output: URL MP4 → download ke local

Preprocess mode `full`:
  - Animasi wajah → paste back ke ORIGINAL background
  - Green screen photo → green screen video (siap chroma key manual di editor)
  - Quote sadtalker.ai/photo-to-video:
    "Animates the face region and seamlessly pastes it back onto the original
     high-resolution background. Preserves half-body composition, clothing,
     and office scenery."

Install:
  pip3 install replicate requests

Env:
  REPLICATE_API_TOKEN  — wajib. Dapatkan di https://replicate.com/account/api-tokens
                         (free $0.10 credit untuk test, lalu pay-as-you-go)

Usage (sebagai modul):
  from talkinghead_backend import generate_talking_head, SADTALKER_PREPROCESS_MODES

  ok = generate_talking_head(
      source_image_path="/path/to/amat-avatar.jpg",
      driven_audio_path="/path/to/narasi-jawa.wav",
      output_mp4_path="/path/to/amat-talking-green.mp4",
      preprocess="full",
      still=True,
      enhancer="gfpgan",
  )

Usage (CLI standalone):
  export REPLICATE_API_TOKEN=r8_xxx
  python3 talkinghead_backend.py --source amat-avatar.jpg --audio narasi.wav -o out.mp4
  python3 talkinghead_backend.py --list-modes
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from typing import Optional

# Lazy import — supaya --list-modes dan --help jalan tanpa replicate terinstall.
replicate = None
requests = None


def _ensure_replicate():
    """Lazy import replicate module."""
    global replicate
    if replicate is not None:
        return
    try:
        import replicate as _replicate
        replicate = _replicate
    except ImportError:
        print("Install replicate: pip3 install replicate", file=sys.stderr)
        sys.exit(1)


def _ensure_requests():
    """Lazy import requests (untuk download MP4 dari URL)."""
    global requests
    if requests is not None:
        return
    try:
        import requests as _requests
        requests = _requests
    except ImportError:
        print("Install requests: pip3 install requests", file=sys.stderr)
        sys.exit(1)


# ============================================================
# Constants
# ============================================================

# Replicate model ID untuk SadTalker
MODEL_ID = "cjwbw/sadtalker"

# Preprocess mode untuk SadTalker
# - full: ANIMASI wajah → paste back ke ORIGINAL background (recommended untuk green screen)
# - extfull: full + extra margin (untuk head tilt banyak)
# - crop: face only, no background (gak cocok untuk green screen workflow)
# - extcrop: crop + extra margin
# - resize: full image scale, animate di atasnya
SADTALKER_PREPROCESS_MODES = [
    ('full',     'full — animasi wajah → paste back ke original background (RECOMMENDED untuk green screen, preserve half-body + clothing)'),
    ('extfull',  'extfull — full + extra margin (untuk head tilt yang banyak, lebih natural)'),
    ('crop',     'crop — face only, no background (gak cocok untuk green screen workflow, output = face centered)'),
    ('extcrop',  'extcrop — crop + extra margin (lebih lega dari crop)'),
    ('resize',   'resize — full image scale, animate di atasnya (hybrid)'),
]

DEFAULT_PREPROCESS = 'full'

# Enhancer options
ENHANCER_OPTIONS = [
    ('gfpgan',   'gfpgan — tajpkan gigi + mata (RECOMMENDED, penting untuk clean chroma key)'),
    ('none',     'none — skip enhancement (lebih cepat, tapi wajah bisa blur)'),
]
DEFAULT_ENHANCER = 'gfpgan'

# Retry untuk Replicate API (timeout / rate limit / network error)
# Backoff: 10s → 30s → 60s → skip
RETRY_BACKOFF = [10, 30, 60]

# Timeout untuk Replicate API call (detik). SadTalker ~17 detik normal, max 5 menit.
REPLICATE_TIMEOUT = 300

# Timeout untuk download MP4 dari URL (detik)
DOWNLOAD_TIMEOUT = 120


# ============================================================
# Inti: panggil Replicate API + download MP4
# ============================================================

def _open_file_for_replicate(file_path: str):
    """Buka file sebagai file object untuk Replicate SDK."""
    return open(file_path, 'rb')


def generate_talking_head(
    source_image_path: str,
    driven_audio_path: str,
    output_mp4_path: str,
    preprocess: str = DEFAULT_PREPROCESS,
    still: bool = True,
    enhancer: str = DEFAULT_ENHANCER,
    verbose: bool = True,
) -> bool:
    """
    Generate talking head video via Replicate SadTalker.

    Parameters
    ----------
    source_image_path : str
        Path ke foto source (green screen photo, half-body recommended).
    driven_audio_path : str
        Path ke audio wav (dari gemini-tts-tui #15 Narration mode JV).
    output_mp4_path : str
        Path output MP4 (background green screen dipertahankan kalau preprocess=full).
    preprocess : str
        'full' (default, recommended untuk green screen), 'extfull', 'crop', 'extcrop', 'resize'.
    still : bool
        True = --still (kurangi gerakan kepala, cocok presenter formal).
        False = --no-still (lebih natural head movement, untuk dialog dramatis).
    enhancer : str
        'gfpgan' (default, tajpkan wajah) atau 'none'.
    verbose : bool
        True = print progress ke stdout.

    Return True kalau sukses, False kalau gagal setelah retry.
    """
    api_token = os.environ.get("REPLICATE_API_TOKEN")
    if not api_token:
        print("  ⚠ REPLICATE_API_TOKEN belum di-set (cek .env atau env var)",
              file=sys.stderr)
        return False

    if not os.path.isfile(source_image_path):
        print(f"  ⚠ Source image tidak ditemukan: {source_image_path}", file=sys.stderr)
        return False

    if not os.path.isfile(driven_audio_path):
        print(f"  ⚠ Driven audio tidak ditemukan: {driven_audio_path}", file=sys.stderr)
        return False

    if verbose:
        print(f"  [talkinghead] source: {os.path.basename(source_image_path)}")
        print(f"  [talkinghead] audio:  {os.path.basename(driven_audio_path)}")
        print(f"  [talkinghead] preprocess={preprocess}, still={still}, enhancer={enhancer}")
        print(f"  [talkinghead] output: {output_mp4_path}")

    _ensure_replicate()
    _ensure_requests()

    # Set API token
    import os as _os
    _os.environ['REPLICATE_API_TOKEN'] = api_token

    last_error = None
    for attempt in range(len(RETRY_BACKOFF) + 1):
        try:
            if verbose:
                print(f"  [talkinghead] Replicate API call (attempt {attempt + 1}/{len(RETRY_BACKOFF) + 1})...")

            # Buka file (Replicate SDK butuh file handle)
            with open(source_image_path, 'rb') as img_f, open(driven_audio_path, 'rb') as aud_f:
                # Replicate.run() — blocking sampai output ready
                output = replicate.run(
                    MODEL_ID,
                    input={
                        "source_image": img_f,
                        "driven_audio": aud_f,
                        "preprocess": preprocess,
                        "still": still,
                        "enhancer": enhancer,
                    },
                    timeout=REPLICATE_TIMEOUT,
                )

            # Output = URL string atau dict dengan 'video' key
            if isinstance(output, dict):
                video_url = output.get('video', output.get('url', ''))
            else:
                video_url = str(output)

            if not video_url or not video_url.startswith('http'):
                raise RuntimeError(f"Output URL tidak valid: {video_url}")

            if verbose:
                print(f"  [talkinghead] Download MP4 dari {video_url[:80]}...")

            # Download MP4
            mp4_bytes = _download_mp4(video_url)
            if not mp4_bytes:
                raise RuntimeError("Download MP4 gagal — bytes kosong")

            # Pastikan output dir exists
            out_dir = os.path.dirname(output_mp4_path)
            if out_dir:
                os.makedirs(out_dir, exist_ok=True)

            with open(output_mp4_path, 'wb') as f:
                f.write(mp4_bytes)

            if os.path.isfile(output_mp4_path) and os.path.getsize(output_mp4_path) > 0:
                if verbose:
                    size_mb = os.path.getsize(output_mp4_path) / 1024 / 1024
                    print(f"  [talkinghead] ✓ Output: {output_mp4_path} ({size_mb:.1f} MB)")
                return True

            raise RuntimeError("Output file tidak terbentuk / kosong")

        except Exception as e:
            last_error = e
            err_str = str(e).lower()
            # Detect retryable errors (timeout, network, 5xx, rate limit)
            is_retryable = (
                'timeout' in err_str or
                'timed out' in err_str or
                'connection' in err_str or
                'network' in err_str or
                '5xx' in err_str or
                '502' in err_str or
                '503' in err_str or
                '504' in err_str or
                'rate limit' in err_str or
                '429' in err_str
            )
            if not is_retryable:
                # Bukan retryable → langsung fail
                print(f"  ⚠ Replicate API gagal: {e}", file=sys.stderr)
                return False
            # Retryable → backoff + retry
            if attempt < len(RETRY_BACKOFF):
                wait_s = RETRY_BACKOFF[attempt]
                print(f"  ⏸ Retryable error (attempt {attempt + 1}). Tunggu {wait_s}s, retry...",
                      file=sys.stderr)
                time.sleep(wait_s)
                continue
            else:
                print(f"  ⚠ Replicate API gagal setelah {len(RETRY_BACKOFF)} retry: {last_error}",
                      file=sys.stderr)
                return False

    print(f"  ⚠ Replicate API gagal: {last_error}", file=sys.stderr)
    return False


def _download_mp4(url: str) -> bytes:
    """Download MP4 dari URL (Replicate return URL delivr)."""
    _ensure_requests()
    response = requests.get(url, stream=True, timeout=DOWNLOAD_TIMEOUT)
    if response.status_code != 200:
        raise RuntimeError(f"Download gagal HTTP {response.status_code}: {response.text[:200]}")
    return response.content


# ============================================================
# CLI standalone (untuk test cepat)
# ============================================================

def _print_modes():
    print("\nSadTalker preprocess modes (untuk talkinghead-tui.py):")
    print("-" * 90)
    for mode, desc in SADTALKER_PREPROCESS_MODES:
        marker = "  ← default" if mode == DEFAULT_PREPROCESS else ""
        print(f"  {mode:10s} — {desc}{marker}")
    print("-" * 90)
    print()
    print("Cocok untuk workflow green screen: 'full' (default) atau 'extfull'.")
    print("JANGAN pakai 'crop' untuk green screen — output = face only, no background.")
    print()


def _print_enhancers():
    print("\nEnhancer options:")
    print("-" * 90)
    for enh, desc in ENHANCER_OPTIONS:
        marker = "  ← default" if enh == DEFAULT_ENHANCER else ""
        print(f"  {enh:10s} — {desc}{marker}")
    print("-" * 90)
    print()


def main():
    parser = argparse.ArgumentParser(
        description='talkinghead_backend.py — Backend SadTalker via Replicate (standalone test)'
    )
    parser.add_argument('--source', '-s', default=None,
                        help='Source image (.jpg/.png, foto green screen half-body)')
    parser.add_argument('--audio', '-a', default=None,
                        help='Driven audio (.wav, dari gemini-tts-tui #15 Narration JV)')
    parser.add_argument('--output', '-o', default='./talking-head.mp4',
                        help='Output MP4 path (default: ./talking-head.mp4)')
    parser.add_argument('--preprocess', default=DEFAULT_PREPROCESS,
                        choices=[m[0] for m in SADTALKER_PREPROCESS_MODES],
                        help=f'Preprocess mode (default: {DEFAULT_PREPROCESS})')
    parser.add_argument('--still', dest='still', action='store_true', default=True,
                        help='--still mode (kurangi gerakan kepala, default)')
    parser.add_argument('--no-still', dest='still', action='store_false',
                        help='Non-still mode (lebih natural head movement)')
    parser.add_argument('--enhancer', default=DEFAULT_ENHANCER,
                        choices=[e[0] for e in ENHANCER_OPTIONS],
                        help=f'Enhancer (default: {DEFAULT_ENHANCER})')
    parser.add_argument('--list-modes', action='store_true',
                        help='Tampilkan daftar preprocess mode lalu keluar')
    parser.add_argument('--list-enhancers', action='store_true',
                        help='Tampilkan daftar enhancer lalu keluar')
    args = parser.parse_args()

    if args.list_modes:
        _print_modes()
        return
    if args.list_enhancers:
        _print_enhancers()
        return
    if not args.source or not args.audio:
        parser.error("--source dan --audio wajib (atau pakai --list-modes / --list-enhancers)")

    if not os.environ.get("REPLICATE_API_TOKEN"):
        print("ERROR: Set REPLICATE_API_TOKEN dulu. Dapatkan di "
              "https://replicate.com/account/api-tokens",
              file=sys.stderr)
        sys.exit(1)

    print(f"[talkinghead-backend] model={MODEL_ID}")
    ok = generate_talking_head(
        source_image_path=args.source,
        driven_audio_path=args.audio,
        output_mp4_path=args.output,
        preprocess=args.preprocess,
        still=args.still,
        enhancer=args.enhancer,
        verbose=True,
    )
    if not ok:
        print("ERROR: gagal generate.", file=sys.stderr)
        sys.exit(1)

    print(f"\n✓ Done! Output: {args.output}")
    print(f"  Size: {os.path.getsize(args.output) / 1024 / 1024:.1f} MB")
    print(f"  Preprocess: {args.preprocess}")
    print(f"  Still: {args.still}")
    print(f"  Enhancer: {args.enhancer}")
    print(f"\n🎬 Langkah berikutnya:")
    print(f"   1. Buka {args.output} di Final Cut / DaVinci / Premiere")
    print(f"   2. Chroma key green (hilangkan green screen)")
    print(f"   3. Composite dengan background baru (foto sejarah, kantor, dll)")
    print(f"   4. Tambah text overlay (kalau perlu)")
    print(f"   5. Export → final-konten.mp4 (siap YouTube)")


if __name__ == '__main__':
    main()
