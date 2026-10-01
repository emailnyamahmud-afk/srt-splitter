// Vercel Serverless Function: Edge TTS Proxy
//
// Browser JavaScript cannot set the `Origin` header to chrome-extension://...
// (browser security restriction). Microsoft Edge TTS endpoint requires this
// specific Origin header, so we use this proxy to forward the request.
//
// POST /api/edge-tts
// Body: { "text": "Halo", "voice": "id-ID-GadisNeural", "rate": "+0%" }
// Response: audio/mp3 binary

import WebSocket from 'ws';
import crypto from 'crypto';

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

      // speech.config message
      const configMsg = `X-Timestamp:${isoDate}\r\nContent-Type:application/json; charset=utf-8\r\nPath:speech.config\r\n\r\n` + JSON.stringify({
        context: { synthesis: { audio: { metadataoptions: { sentenceBoundaryEnabled: 'false', wordBoundaryEnabled: 'false' }, outputFormat: OUTPUT_FORMAT } } }
      });
      ws.send(configMsg);

      // SSML message (after 100ms to ensure config is processed first)
      setTimeout(() => {
        const ssml = `<speak version='1.0' xmlns='http://www.w3.org/2001/10/synthesis' xml:lang='en-US'><voice name='${voice}'><prosody pitch='${pitch}' rate='${rate}' volume='${volume}'>${escapeXml(text)}</prosody></voice></speak>`;
        const ssmlMsg = `X-RequestId:${requestId}\r\nContent-Type:application/ssml+xml\r\nX-Timestamp:${isoDate}\r\nPath:ssml\r\n\r\n${ssml}`;
        ws.send(ssmlMsg);
      }, 100);
    });

    ws.on('message', (data, isBinary) => {
      if (isBinary) {
        // Binary message format:
        //   <header_len: 2 bytes big-endian><header>\r\n<audio bytes>
        // Header uses \r\n line separators, ends with \r\n then audio data.
        if (data.length < 2) return;
        const headerLen = data.readUInt16BE(0);
        if (headerLen <= 0 || headerLen > data.length) return;
        const header = data.slice(2, 2 + headerLen).toString('utf-8');
        if (header.includes('Path:audio')) {
          // Audio starts immediately after the 2-byte length + header bytes.
          // The header itself ends with \r\n (already part of the header length).
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

export default async function handler(req, res) {
  // CORS for browser clients
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'POST, OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type');

  if (req.method === 'OPTIONS') {
    return res.status(200).end();
  }

  if (req.method !== 'POST') {
    return res.status(405).json({ error: 'Method not allowed, use POST' });
  }

  const { text, voice, rate, volume, pitch } = req.body || {};

  if (!text || typeof text !== 'string') {
    return res.status(400).json({ error: 'Field "text" is required' });
  }

  if (text.length > 5000) {
    return res.status(400).json({ error: 'Text too long (max 5000 chars per request)' });
  }

  try {
    const audio = await edgeTTS(text, voice || 'id-ID-GadisNeural', rate, volume, pitch);
    res.setHeader('Content-Type', 'audio/mpeg');
    res.setHeader('Content-Length', audio.length);
    res.setHeader('Cache-Control', 'no-cache, no-store');
    res.status(200).send(audio);
  } catch (e) {
    console.error('Edge TTS error:', e.message);
    res.status(502).json({ error: 'Edge TTS failed: ' + e.message });
  }
}
