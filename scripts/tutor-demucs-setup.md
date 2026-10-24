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

## Kapan perlu Demucs?

Demucs HANYA perlu untuk **Full mode** di mix-tui.py (Mode A & B):
- Pisahkan vokal ori dari SFX/musik latar
- no_vocals.mp3 dipakai sebagai SFX layer di mix dengan ducking
- Cocok untuk film action / musik latar penting / produksi "proper"

## Kapan SKIP Demucs?

Untuk **Simple mode** di mix-tui.py (Mode C & D):
- Langsung pakai MP4 ori (vokal masih ada, tapi tidak dipakai — di-replace dub)
- Mix hanya MP4 + dub, tanpa SFX layer
- Cocok untuk preview cepat / film dialog dominan
- Sync 1000000%, tidak perlu DaVinci Resolve

User workflow:
- Dialog dominan → skip demucs → mix Simple mode (Mode C/D)
- Hasil "proper" dengan SFX → jalankan demucs → mix Full mode (Mode A/B)
