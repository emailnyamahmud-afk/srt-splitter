// Test Edge TTS proxy + cek sample rate MP3
import http from 'http';
import WebSocket from 'ws';
import crypto from 'crypto';
import { writeFileSync } from 'fs';

const TRUSTED_CLIENT_TOKEN = '6A5AA1D4EAFF4E9FB37E23D68491D6F4';
const BASE_URL = 'speech.platform.bing.com/consumer/speech/synthesize/readaloud';
const WSS_URL = 'wss://' + BASE_URL + '/edge/v1?TrustedClientToken=' + TRUSTED_CLIENT_TOKEN;
const OUTPUT_FORMAT = 'audio-24khz-48kbitrate-mono-mp3';
const CHROMIUM_FULL_VERSION = '143.0.3650.75';
const CHROMIUM_MAJOR_VERSION = CHROMIUM_FULL_VERSION.split('.')[0];
const SEC_MS_GEC_VERSION = '1-' + CHROMIUM_FULL_VERSION;
const WIN_EPOCH = 11644473600;
const S_TO_NS = 1e9;

function genSec() {
  let t = Date.now() / 1000;
  t += WIN_EPOCH;
  t -= t % 300;
  t = t * (S_TO_NS / 100);
  return crypto.createHash('sha256').update(t.toFixed(0) + TRUSTED_CLIENT_TOKEN, 'ascii').digest('hex').toUpperCase();
}
function noDash() { return crypto.randomBytes(16).toString('hex'); }
function escXml(s) { return s.replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&apos;'}[c])); }

function edgeTTS(text, voice) {
  voice = voice || 'id-ID-GadisNeural';
  return new Promise((resolve, reject) => {
    const url = WSS_URL + '&ConnectionId=' + noDash() + '&Sec-MS-GEC=' + genSec() + '&Sec-MS-GEC-Version=' + SEC_MS_GEC_VERSION;
    const ws = new WebSocket(url, {
      headers: {
        'Origin': 'chrome-extension://jdiccldimpdaibmpdkjnbmckianbfold',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/' + CHROMIUM_MAJOR_VERSION + '.0.0.0 Safari/537.36 Edg/' + CHROMIUM_MAJOR_VERSION + '.0.0.0',
        'Cookie': 'muid=' + crypto.randomBytes(16).toString('hex').toUpperCase() + ';',
      }
    });
    const chunks = [];
    const t = setTimeout(() => { try{ws.close();}catch{}; reject(new Error('timeout')); }, 30000);
    ws.on('open', () => {
      const iso = new Date().toISOString().split('.')[0] + 'Z';
      const config = 'X-Timestamp:' + iso + '\r\nContent-Type:application/json; charset=utf-8\r\nPath:speech.config\r\n\r\n' + JSON.stringify({context:{synthesis:{audio:{metadataoptions:{sentenceBoundaryEnabled:'false',wordBoundaryEnabled:'false'},outputFormat:OUTPUT_FORMAT}}}});
      ws.send(config);
      setTimeout(() => {
        const ssml = "<speak version='1.0' xmlns='http://www.w3.org/2001/10/synthesis' xml:lang='en-US'><voice name='" + voice + "'><prosody pitch='+0Hz' rate='+0%' volume='+0%'>" + escXml(text) + '</prosody></voice></speak>';
        const ssmlMsg = 'X-RequestId:' + noDash() + '\r\nContent-Type:application/ssml+xml\r\nX-Timestamp:' + iso + '\r\nPath:ssml\r\n\r\n' + ssml;
        ws.send(ssmlMsg);
      }, 100);
    });
    ws.on('message', (data, isBinary) => {
      if (isBinary) {
        if (data.length < 2) return;
        const hl = data.readUInt16BE(0);
        if (hl <= 0 || hl > data.length) return;
        const h = data.slice(2, 2+hl).toString('utf-8');
        if (h.includes('Path:audio')) {
          const as = 2 + hl;
          if (as < data.length) chunks.push(data.slice(as));
        }
      } else if (data.toString().includes('Path:turn.end')) {
        clearTimeout(t);
        setTimeout(() => { try{ws.close();}catch{}; resolve(Buffer.concat(chunks)); }, 200);
      }
    });
    ws.on('error', (e) => { clearTimeout(t); reject(e); });
  });
}

const server = http.createServer(async (req, res) => {
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'POST, OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type');
  if (req.method === 'OPTIONS') { res.writeHead(200).end(); return; }
  if (req.method !== 'POST' || req.url !== '/api/edge-tts') {
    res.writeHead(405, {'Content-Type':'application/json'}).end(JSON.stringify({error:'POST /api/edge-tts'}));
    return;
  }
  let body = '';
  for await (const chunk of req) body += chunk;
  try {
    const { text, voice } = JSON.parse(body);
    const audio = await edgeTTS(text, voice);
    res.writeHead(200, {'Content-Type':'audio/mpeg'}).end(audio);
  } catch (e) {
    res.writeHead(502, {'Content-Type':'application/json'}).end(JSON.stringify({error:e.message}));
  }
});

server.listen(3001, async () => {
  console.log('Proxy listening on :3001');
  try {
    console.log('Generating Indonesia test audio...');
    const audio = await edgeTTS('Selamat datang di aplikasi pemecah subtitle untuk diubah menjadi suara dengan kualitas natural menggunakan voice Indonesia perempuan.', 'id-ID-GadisNeural');
    writeFileSync('/tmp/raw-edge-indonesia.mp3', audio);
    console.log('Saved /tmp/raw-edge-indonesia.mp3 (' + audio.length + ' bytes)');
  } catch (e) {
    console.error('Test failed:', e.message);
  }
});
