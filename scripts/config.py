#!/usr/bin/env python3
"""
config.py — Config base path untuk semua TUI.

User workflow: terminal di SSD ~/Dubbing/, data di /Volumes/HDD/Dubbing/

Struktur:
  SSD ~/Dubbing/             → scripts + venv (cepat)
  HDD /Volumes/HDD/Dubbing/  → data (input, demucs, tts, mix, kamus, .env)

Kalau HDD gak ter-colok, semua TUI tampilkan pesan "Colok HDD dulu".
"""

import os
from pathlib import Path

# Base paths
SSD_HOME = Path.home() / 'Dubbing'           # SSD (scripts + venv)
HDD_BASE = Path('/Volumes/HDD/Dubbing')      # HDD (data)

# Subfolder HDD
INPUT_DIR = HDD_BASE / 'input'               # yt-dlp output (video, audio, srt)
DEMUCS_DIR = HDD_BASE / 'demucs'             # demucs output (no_vocals.wav)
TTS_DIR = HDD_BASE / 'tts'                   # edge-tts output (dub.wav, subs.srt, cache)
MIX_DIR = HDD_BASE / 'mix'                   # mix-tui output (final.mp4)

# Kamus + config
KAMUS_JSON = SSD_HOME / 'jv.wiktionary.json' # Kamus di SSD (kecil, cepat load)
ENV_FILE = HDD_BASE / '.env'                 # Supabase credentials di HDD

# Scripts
SCRIPTS_DIR = SSD_HOME                       # scripts di SSD


def ensure_hdd():
    """Cek apakah HDD ter-colok. Kalau gak, tampilkan pesan."""
    if not HDD_BASE.exists():
        print('\n❌ HDD eksternal tidak ter-colok!')
        print(f'   Folder tidak ditemukan: {HDD_BASE}')
        print('   Colok HDD eksternal, lalu jalankan ulang.')
        return False
    
    # Buat subfolder kalau belum ada
    for d in [INPUT_DIR, DEMUCS_DIR, TTS_DIR, MIX_DIR]:
        d.mkdir(parents=True, exist_ok=True)
    return True


def ensure_kamus():
    """Cek apakah kamus JSON ada. Kalau gak, tampilkan download command."""
    if not KAMUS_JSON.exists():
        print(f'\n❌ Kamus tidak ditemukan: {KAMUS_JSON}')
        print('   Download:')
        print(f'   curl -L -o {KAMUS_JSON} \\')
        print(f'     "https://raw.githubusercontent.com/emailnyamahmud-afk/srt-splitter/main/public/jv.wiktionary.json"')
        return False
    return True


def load_env():
    """Load .env dari HDD (kalau ada)."""
    if not ENV_FILE.exists():
        return False
    with open(ENV_FILE, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, _, val = line.partition('=')
                os.environ[key.strip()] = val.strip()
    return True
