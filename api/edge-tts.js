// Vercel Serverless Function: Edge TTS Proxy + FFmpeg audio sync
//
// Browser JavaScript cannot set the `Origin` header to chrome-extension://...
// (browser security restriction). Microsoft Edge TTS endpoint requires this
// specific Origin header, so we use this proxy to forward the request.
//
// Selain itu, server-side kita bisa pakai FFmpeg untuk time-stretch audio
// dengan pitch preservation (librubberband). Ini cara yang sama dengan
// Voicertool.com — audio fit ke cue duration, pitch natural, no chipmunk.
//
// POST /api/edge-tts
// Body: {
//   "text": "Halo",
//   "voice": "id-ID-GadisNeural",
//   "rate": "+0%",          // Edge TTS prosody rate (server-side)
//   "targetDuration": 5.0    // Target duration in seconds (FFmpeg atempo akan fit audio)
// }
// Response: audio/mp3 binary (duration = targetDuration, pitch natural)

import WebSocket from 'ws';
import crypto from 'crypto';
import { exec } from 'child_process';
import { promisify } from 'util';
import { tmpdir } from 'os';
import { join } from 'path';
import { writeFileSync, readFileSync, unlinkSync, existsSync } from 'fs';

const execAsync = promisify(exec);

const TRUSTED_CLIENT_TOKEN = '6A5AA1D4EAFF4E9FB37E23D68491D6F4';
const BASE_URL = 'speech.platform.bing.com/consumer/speech/synthesize/readaloud';
const WSS_URL = `wss://${BASE_URL}/edge/v1?TrustedClientToken=${TRUSTED_CLIENT_TOKEN}`;
const OUTPUT_FORMAT = 'audio-24khz-48kbitrate-mono-mp3';
const CHROMIUM_FULL_VERSION = '143.0.3650.75';
const CHROMIUM_MAJOR_VERSION = CHROMIUM_FULL_VERSION.split('.')[0];
const SEC_MS_GEC_VERSION = `1-${CHROMIUM_FULL_VERSION}`;
const WIN_EPOCH = 11644473600;
const S_TO_NS = 1e9;

function generateSecMsGec() {
  let ticks = Date.now() / 1000;
  ticks += WIN_EPOCH;
  ticks -= ticks % 300;
  ticks = ticks * (S_TO_NS / 100);
  return crypto.createHash('sha256').update(`${ticks.toFixed(0)}${TRUSTED_CLIENT_TOKEN}`, 'ascii').digest('hex').toUpperCase();
}

function noDashUuid() {
  return crypto.randomBytes(16).toString('hex');
}

function escapeXml(s) {
  return s.replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&apos;'}[c]));
}

function edgeTTS(text, voice = 'id-ID-GadisNeural', rate = '+0%', volume = '+0%', pitch = '+0Hz') {
  return new Promise((resolve, reject) => {
    const secMsGec = generateSecMsGec();
    const connId = noDashUuid();
    const requestId = noDashUuid();
    const muid = crypto.randomBytes(16).toString('hex').toUpperCase();
    const fullUrl = `${WSS_URL}&ConnectionId=${connId}&Sec-MS-GEC=${secMsGec}&Sec-MS-GEC-Version=${SEC_MS_GEC_VERSION}`;

    const ws = new WebSocket(fullUrl, {
      headers: {
        'Pragma': 'no-cache',
        'Cache-Control': 'no-cache',
        'Origin': 'chrome-extension://jdiccldimpdaibmpdkjnbmckianbfold',
        'User-Agent': `Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/${CHROMIUM_MAJOR_VERSION}.0.0.0 Safari/537.36 Edg/${CHROMIUM_MAJOR_VERSION}.0.0.0`,
        'Accept-Encoding': 'gzip, deflate, br, zstd',
        'Accept-Language': 'en-US,en;q=0.9',
        'Cookie': `muid=${muid};`,
      }
    });

    const chunks = [];
    const timeout = setTimeout(() => { try { ws.close(); } catch {}; reject(new Error('Edge TTS timeout (30s)')); }, 30000);

    ws.on('open', () => {
      const isoDate = new Date().toISOString().split('.')[0] + 'Z';
      const configMsg = `X-Timestamp:${isoDate}\r\nContent-Type:application/json; charset=utf-8\r\nPath:speech.config\r\n\r\n` + JSON.stringify({
        context: { synthesis: { audio: { metadataoptions: { sentenceBoundaryEnabled: 'false', wordBoundaryEnabled: 'false' }, outputFormat: OUTPUT_FORMAT } } }
      });
      ws.send(configMsg);

      setTimeout(() => {
        const ssml = `<speak version='1.0' xmlns='http://www.w3.org/2001/10/synthesis' xml:lang='en-US'><voice name='${voice}'><prosody pitch='${pitch}' rate='${rate}' volume='${volume}'>${escapeXml(text)}</prosody></voice></speak>`;
        const ssmlMsg = `X-RequestId:${requestId}\r\nContent-Type:application/ssml+xml\r\nX-Timestamp:${isoDate}\r\nPath:ssml\r\n\r\n${ssml}`;
        ws.send(ssmlMsg);
      }, 100);
    });

    ws.on('message', (data, isBinary) => {
      if (isBinary) {
        if (data.length < 2) return;
        const headerLen = data.readUInt16BE(0);
        if (headerLen <= 0 || headerLen > data.length) return;
        const header = data.slice(2, 2 + headerLen).toString('utf-8');
        if (header.includes('Path:audio')) {
          const audioStart = 2 + headerLen;
          if (audioStart < data.length) {
            chunks.push(data.slice(audioStart));
          }
        }
      } else {
        const text = data.toString();
        if (text.includes('Path:turn.end')) {
          clearTimeout(timeout);
          setTimeout(() => {
            try { ws.close(); } catch {}
            resolve(Buffer.concat(chunks));
          }, 200);
        }
      }
    });

    ws.on('error', (err) => {
      clearTimeout(timeout);
      reject(err);
    });
  });
}

/**
 * Time-stretch audio ke target duration dengan FFmpeg atempo filter.
 * Pitch tetap natural (librubberband via atempo filter).
 *
 * @param {Buffer} mp3Buffer Source audio MP3
 * @param {number} targetDurationSec Target duration in seconds
 * @returns {Promise<Buffer>} MP3 audio dengan duration = targetDurationSec
 */
async function timeStretchAudio(mp3Buffer, targetDurationSec) {
  // Simpan ke file sementara
  const inFile = join(tmpdir(), `tts_in_${Date.now()}_${noDashUuid()}.mp3`);
  const outFile = join(tmpdir(), `tts_out_${Date.now()}_${noDashUuid()}.mp3`);

  try {
    writeFileSync(inFile, mp3Buffer);

    // Dapatkan durasi asli dengan ffprobe
    const { stdout: probeOut } = await execAsync(`ffprobe -v error -show_entries format=duration -of csv=p=0 "${inFile}"`);
    const sourceDuration = parseFloat(probeOut.trim());

    if (isNaN(sourceDuration) || sourceDuration <= 0) {
      return mp3Buffer; // Tidak bisa probe, return asli
    }

    // Kalau source duration sudah dekat target (±5%), return asli
    if (Math.abs(sourceDuration - targetDurationSec) < 0.05) {
      return mp3Buffer;
    }

    // Hitung atempo ratio
    // atempo range: 0.5-100.0 (tapi >2.0 mulai aneh, chain untuk >2.0)
    let ratio = sourceDuration / targetDurationSec;

    // Untuk ratio > 2.0, chain multiple atempo filters
    // e.g. ratio 4.0 → atempo=2.0,atempo=2.0
    let atempoChain = '';
    let remainingRatio = ratio;
    while (remainingRatio > 2.0) {
      atempoChain += 'atempo=2.0,';
      remainingRatio /= 2.0;
    }
    atempoChain += `atempo=${remainingRatio.toFixed(6)}`;

    // Untuk ratio < 0.5 (sangat lambat), juga chain
    while (remainingRatio < 0.5) {
      atempoChain = `atempo=0.5,` + atempoChain;
      remainingRatio /= 0.5;
    }

    // Run FFmpeg dengan atempo filter
    // -y: overwrite output
    // -i: input
    // -filter:a: audio filter (atempo = time-stretch with pitch preservation)
    // -b:a: bitrate
    const cmd = `ffmpeg -y -i "${inFile}" -filter:a "${atempoChain}" -b:a 48k -ar 24000 -ac 1 "${outFile}"`;
    await execAsync(cmd, { timeout: 30000 });

    if (!existsSync(outFile)) {
      return mp3Buffer; // FFmpeg gagal, return asli
    }

    const result = readFileSync(outFile);
    return result;
  } catch (e) {
    console.error('FFmpeg error:', e.message);
    return mp3Buffer; // Fallback: return audio asli
  } finally {
    try { unlinkSync(inFile); } catch {}
    try { unlinkSync(outFile); } catch {}
  }
}

export default async function handler(req, res) {
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'POST, OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type');

  if (req.method === 'OPTIONS') {
    return res.status(200).end();
  }

  if (req.method !== 'POST') {
    return res.status(405).json({ error: 'Method not allowed, use POST' });
  }

  const { text, voice, rate, volume, pitch, targetDuration } = req.body || {};

  if (!text || typeof text !== 'string') {
    return res.status(400).json({ error: 'Field "text" is required' });
  }

  if (text.length > 5000) {
    return res.status(400).json({ error: 'Text too long (max 5000 chars per request)' });
  }

  try {
    // Step 1: Generate audio dari Edge TTS dengan rate natural
    const audio = await edgeTTS(text, voice || 'id-ID-GadisNeural', rate, volume, pitch);

    // Step 2: Kalau ada targetDuration, time-stretch dengan FFmpeg atempo
    let finalAudio = audio;
    if (targetDuration && typeof targetDuration === 'number' && targetDuration > 0) {
      finalAudio = await timeStretchAudio(audio, targetDuration);
    }

    res.setHeader('Content-Type', 'audio/mpeg');
    res.setHeader('Content-Length', finalAudio.length);
    res.setHeader('Cache-Control', 'no-cache, no-store');
    res.status(200).send(finalAudio);
  } catch (e) {
    console.error('Edge TTS error:', e.message);
    res.status(502).json({ error: 'Edge TTS failed: ' + e.message });
  }
}
