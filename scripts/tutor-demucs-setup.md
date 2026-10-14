# Demucs Setup — MacBook M1

## Install

```bash
pip3 install torchaudio demucs
```

## Run

```bash
python3 demucs-tui.py
```

Pilih file audio → proses (~16 menit untuk 2 jam audio dgn MPS).

## Output

- `no_vocals.wav` — instrumental (SFX + music)
- `vocals.wav` — vocal (auto-dihapus setelah mix)

## Spec

- M1 MPS acceleration
- Model: htdemucs
- Memory: ~8GB untuk 2 jam audio
