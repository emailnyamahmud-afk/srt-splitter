# Demucs Setup — MacBook M1

## Install

```bash
cd ~/Dubbing
source venv/bin/activate
pip3 install torchaudio demucs
```

## Run

```bash
python3 demucs-tui.py
```

Pilih file audio dari HDD/input/ → proses (~16 menit untuk 2 jam audio dgn MPS).

## Output

- `HDD/demucs/htdemucs/{namafile}/no_vocals.wav` — instrumental (SFX + music)
- `HDD/demucs/htdemucs/{namafile}/vocals.wav` — vocal (auto-dihapus)

## Spec

- M1 MPS (Metal Performance Shaders) acceleration
- Model: htdemucs (default, cepat, kualitas bagus)
- Memory: ~8GB untuk 2 jam audio
- Output: MP3 320kbps (lebih kecil dari WAV)
