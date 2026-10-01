// Microsoft Edge TTS — free neural voices via WebSocket.
//
// Free, no API key, no authentication. Indonesian native neural voices:
//   - id-ID-Ardi (male)
//   - id-ID-Gadis (female)
//
// Audio format: MP3 (24kHz, 48kbps, mono)
//
// Note: Endpoint requires the TrustedClientToken in URL (Microsoft's Read Aloud token).
// Works from any browser that allows WebSocket connections to speech.platform.bing.com.

export interface EdgeVoice {
  name: string
  label: string
  lang: string
  gender: 'Male' | 'Female'
}

export const EDGE_VOICES: EdgeVoice[] = [
  { name: 'id-ID-Gadis', label: '🇮🇩 Indonesia — Gadis (Perempuan)', lang: 'id-ID', gender: 'Female' },
  { name: 'id-ID-Ardi', label: '🇮🇩 Indonesia — Ardi (Laki-laki)', lang: 'id-ID', gender: 'Male' },
  { name: 'en-US-AriaNeural', label: '🇺🇸 English US — Aria (Female)', lang: 'en-US', gender: 'Female' },
  { name: 'en-US-GuyNeural', label: '🇺🇸 English US — Guy (Male)', lang: 'en-US', gender: 'Male' },
  { name: 'en-AU-NatashaNeural', label: '🇦🇺 English AU — Natasha (Female)', lang: 'en-AU', gender: 'Female' },
  { name: 'zh-CN-XiaoxiaoNeural', label: '🇨🇳 Mandarin — Xiaoxiao (Female)', lang: 'zh-CN', gender: 'Female' },
  { name: 'ja-JP-NanamiNeural', label: '🇯🇵 Japanese — Nanami (Female)', lang: 'ja-JP', gender: 'Female' },
  { name: 'ko-KR-SunHiNeural', label: '🇰🇷 Korean — Sun-Hi (Female)', lang: 'ko-KR', gender: 'Female' },
]

export const DEFAULT_EDGE_VOICE = 'id-ID-Gadis'

const WS_URL =
  'wss://speech.platform.bing.com/consumer/speech/synthesize/readaloud/edge/v1?TrustedClientToken=6A5AA1D4EAFF4E9FB37E23D68491D6F4'

const OUTPUT_FORMAT = 'audio-24khz-48kbitrate-mono-mp3'

function uuid(): string {
  if (typeof crypto !== 'undefined' && crypto.randomUUID) {
    return crypto.randomUUID()
  }
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (c) => {
    const r = (Math.random() * 16) | 0
    const v = c === 'x' ? r : (r & 0x3) | 0x8
    return v.toString(16)
  })
}

/**
 * Synthesize text to speech using Microsoft Edge TTS.
 * Returns MP3 Blob (24kHz mono, 48kbps).
 */
export async function edgeTTS(
  text: string,
  voice: string = DEFAULT_EDGE_VOICE,
  opts: { rate?: string; volume?: string; pitch?: string } = {},
): Promise<Blob> {
  const { rate = '+0%', volume = '+0%', pitch = '+0Hz' } = opts

  return new Promise((resolve, reject) => {
    let ws: WebSocket
    try {
      ws = new WebSocket(WS_URL)
    } catch (e) {
      reject(new Error('Tidak bisa buka WebSocket ke Edge TTS: ' + (e as Error).message))
      return
    }
    ws.binaryType = 'arraybuffer'

    const audioChunks: Uint8Array[] = []
    let settled = false

    const cleanup = () => {
      ws.onmessage = null
      ws.onerror = null
      ws.onclose = null
      if (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CONNECTING) {
        try {
          ws.close()
        } catch {
          // ignore
        }
      }
    }

    const finish = (blob: Blob) => {
      if (settled) return
      settled = true
      cleanup()
      resolve(blob)
    }

    const fail = (err: Error) => {
      if (settled) return
      settled = true
      cleanup()
      reject(err)
    }

    const timeout = setTimeout(() => {
      fail(new Error('Edge TTS timeout (30s) — cek koneksi internet'))
    }, 30000)

    ws.onopen = () => {
      // Send config
      const configMsg =
        'Content-Type:application/json; charset=utf-8\r\nPath:speechconfig\r\n\r\n' +
        JSON.stringify({
          context: {
            synthesis: {
              audio: {
                metadataoptions: { sentenceBoundaryEnabled: 'false', wordBoundaryEnabled: 'false' },
                outputFormat: OUTPUT_FORMAT,
              },
            },
          },
        })
      ws.send(configMsg)

      // Send SSML
      const requestId = uuid()
      const ssml = `<speak version='1.0' xmlns='http://www.w3.org/2001/10/synthesis' xml:lang='en-US'><voice name='${voice}'><prosody pitch='${pitch}' rate='${rate}' volume='${volume}'>${escapeXml(text)}</prosody></voice></speak>`
      const ssmlMsg = `X-RequestId:${requestId}\r\nContent-Type:application/ssml+xml\r\nPath:ssml\r\n\r\n${ssml}`
      ws.send(ssmlMsg)
    }

    ws.onmessage = (event) => {
      if (typeof event.data === 'string') {
        if (event.data.includes('Path:turn.end')) {
          clearTimeout(timeout)
          const blob = new Blob(audioChunks, { type: 'audio/mp3' })
          finish(blob)
        }
      } else {
        const data = new Uint8Array(event.data)
        const headerEnd = findHeaderEnd(data)
        if (headerEnd === -1) return
        const headerStr = new TextDecoder('utf-8').decode(data.slice(0, headerEnd))
        if (headerStr.includes('Path:audio')) {
          const body = data.slice(headerEnd + 4)
          if (body.length > 0) {
            audioChunks.push(body)
          }
        }
      }
    }

    ws.onerror = () => {
      clearTimeout(timeout)
      fail(new Error('Edge TTS WebSocket error — browser mungkin blokir koneksi ke speech.platform.bing.com'))
    }

    ws.onclose = (e) => {
      clearTimeout(timeout)
      if (!settled && audioChunks.length === 0) {
        fail(new Error(`Edge TTS ditutup (code ${e.code}): ${e.reason || 'koneksi gagal'}`))
      } else if (!settled) {
        const blob = new Blob(audioChunks, { type: 'audio/mp3' })
        finish(blob)
      }
    }
  })
}

function findHeaderEnd(data: Uint8Array): number {
  for (let i = 0; i < data.length - 3; i++) {
    if (data[i] === 13 && data[i + 1] === 10 && data[i + 2] === 13 && data[i + 3] === 10) {
      return i
    }
  }
  return -1
}

function escapeXml(s: string): string {
  return s
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&apos;')
}

export async function edgeSynthesize(text: string, voice: string = DEFAULT_EDGE_VOICE): Promise<Blob> {
  return edgeTTS(text, voice, { rate: '+0%' })
}
