// Simulate full pipeline: Edge TTS MP3 → decode (Web Audio) → encode WAV → cek sample rate
// Pakai Browser-like Web Audio API di Node.js (via @huggingface/transformers? atau manual)

import { readFileSync, writeFileSync } from 'fs';

// Baca MP3 yang sudah di-generate dari Edge TTS
const mp3 = readFileSync('/tmp/raw-edge-indonesia.mp3');
console.log('MP3 size:', mp3.length, 'bytes');

// ffprobe sudah konfirmasi: MP3 ini 24000 Hz, mono, 48 kbps

// === Simulasi browser Web Audio API decode + encode ===
// Karena Node.js tidak punya Web Audio API, kita pakai ffmpeg untuk decode ke PCM 24kHz
import { execSync } from 'child_process';

// Decode MP3 → raw PCM (24kHz, 16-bit signed, mono)
execSync('ffmpeg -y -i /tmp/raw-edge-indonesia.mp3 -ar 24000 -ac 1 -f s16le /tmp/decoded-pcm.raw 2>/dev/null');
const pcmRaw = readFileSync('/tmp/decoded-pcm.raw');
console.log('Decoded PCM size:', pcmRaw.length, 'bytes (= ', pcmRaw.length/2, 'samples)');

// Convert S16 LE → Float32 (seperti Web Audio API)
const samples = pcmRaw.length / 2;
const float32 = new Float32Array(samples);
for (let i = 0; i < samples; i++) {
  const v = pcmRaw.readInt16LE(i * 2);
  float32[i] = v / 32768;
}

// Encode Float32 → WAV (24kHz, 16-bit, mono) — sama seperti code saya
const sampleRate = 24000;
const wavBuf = new ArrayBuffer(44 + samples * 2);
const view = new DataView(wavBuf);
const writeStr = (off, s) => { for (let i = 0; i < s.length; i++) view.setUint8(off + i, s.charCodeAt(i)); };
writeStr(0, 'RIFF');
view.setUint32(4, 36 + samples * 2, true);
writeStr(8, 'WAVE');
writeStr(12, 'fmt ');
view.setUint32(16, 16, true);
view.setUint16(20, 1, true);
view.setUint16(22, 1, true);
view.setUint32(24, sampleRate, true);
view.setUint32(28, sampleRate * 2, true);
view.setUint16(32, 2, true);
view.setUint16(34, 16, true);
writeStr(36, 'data');
view.setUint32(40, samples * 2, true);
let offset = 44;
for (let i = 0; i < samples; i++) {
  const s = Math.max(-1, Math.min(1, float32[i]));
  view.setInt16(offset, s < 0 ? s * 0x8000 : s * 0x7fff, true);
  offset += 2;
}
writeFileSync('/tmp/output.wav', Buffer.from(wavBuf));
console.log('WAV output: /tmp/output.wav (' + wavBuf.byteLength + ' bytes)');

// Cek hasil dengan ffprobe
import { execSync as es } from 'child_process';
const probe = es('ffprobe -hide_banner /tmp/output.wav 2>&1', { encoding: 'utf8' });
console.log('--- ffprobe WAV output ---');
console.log(probe.split('\n').filter(l => l.includes('Audio') || l.includes('Duration')).join('\n'));
