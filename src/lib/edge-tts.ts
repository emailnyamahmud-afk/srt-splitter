// Microsoft Edge TTS — free neural voices via WebSocket.
//
// Uses the same endpoint Microsoft Edge browser uses for "Read Aloud" feature.
// Free, no API key, no authentication. Supports Indonesian native neural voices:
//   - id-ID-Ardi (male)
//   - id-ID-Gadis (female)
//
// Audio format: MP3 (24kHz, 48kbps, mono)
//
// Reference: https://github.com/ryu0221/edge-tts (and similar open-source impls)

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

/**
 * Generate a UUID v4 for request IDs.
 */
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
 *
 * Returns: MP3 Blob (24kHz mono, 48kbps)
 *
 * @param text  Text to synthesize (any language — Edge TTS handles many scripts)
 * @param voice  Voice ID (e.g. 'id-ID-Gadis')
 * @param rate  Speech rate as percentage string, e.g. '+0%' (normal), '+20%' (faster), '-10%' (slower)
 * @param volume  Volume as percentage string, e.g. '+0%'
 * @param pitch  Pitch adjustment, e.g. '+0Hz'
 */
export async function edgeTTS(
  text: string,
  voice: string = DEFAULT_EDGE_VOICE,
  opts: { rate?: string; volume?: string; pitch?: string } = {},
): Promise<Blob> {
  const { rate = '+0%', volume = '+0%', pitch = '+0Hz' } = opts

  return new Promise((resolve, reject) => {
    const ws = new WebSocket(WS_URL)
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

    // Timeout safety (30s)
    const timeout = setTimeout(() => {
      fail(new Error('Edge TTS timeout (30s) — cek koneksi internet'))
    }, 30000)

    ws.onopen = () => {
      // Send config message
      const configMsg = buildMessage(
        'speechconfig',
        JSON.stringify({
          context: {
            synthesis: {
              audio: {
                metadataoptions: {
                  sentenceBoundaryEnabled: 'false',
                  wordBoundaryEnabled: 'false',
                },
                outputFormat: OUTPUT_FORMAT,
              },
            },
          },
        }),
        'application/json; charset=utf-8',
      )
      ws.send(configMsg)

      // Send SSML message
      const ssml = `<speak version='1.0' xmlns='http://www.w3.org/2001/10/synthesis' xml:lang='en-US'><voice name='${voice}'><prosody pitch='${pitch}' rate='${rate}' volume='${volume}'>${escapeXml(text)}</prosody></voice></speak>`
      const requestId = uuid()
      const ssmlMsg = buildMessage('ssml', ssml, 'application/ssml+xml', requestId)
      ws.send(ssmlMsg)
    }

    ws.onmessage = (event) => {
      if (typeof event.data === 'string') {
        // Text message — check for turn.end
        if (event.data.includes('Path:turn.end')) {
          clearTimeout(timeout)
          const blob = new Blob(audioChunks, { type: 'audio/mp3' })
          finish(blob)
        }
      } else {
        // Binary message — parse headers + audio
        const data = new Uint8Array(event.data)
        // Find end of header (CRLF CRLF = 13 10 13 10)
        const headerEnd = findHeaderEnd(data)
        if (headerEnd === -1) return
        const headerStr = new TextDecoder('utf-8').decode(data.slice(0, headerEnd))
        if (headerStr.includes('Path:audio')) {
          // Body starts after the CRLFCRLF
          const body = data.slice(headerEnd + 4)
          if (body.length > 0) {
            audioChunks.push(body)
          }
        }
      }
    }

    ws.onerror = () => {
      clearTimeout(timeout)
      fail(new Error('Edge TTS WebSocket error — cek koneksi internet atau firewall'))
    }

    ws.onclose = (e) => {
      clearTimeout(timeout)
      // If closed before turn.end with no audio, fail
      if (!settled && audioChunks.length === 0) {
        fail(new Error(`Edge TTS connection closed (code ${e.code}): ${e.reason || 'unknown reason'}`))
      } else if (!settled) {
        // We have audio but didn't get turn.end — use what we have
        const blob = new Blob(audioChunks, { type: 'audio/mp3' })
        finish(blob)
      }
    }
  })
}

/**
 * Build a WebSocket message with text headers and optional body.
 * Format: header1\r\nheader2\r\n...\r\n\r\nbody
 */
function buildMessage(path: string, body: string, contentType: string, requestId?: string): string {
  const timestamp = new Date().toISOString()
  const lines: string[] = [
    `X-Timestamp:${timestamp}`,
    `Content-Type:${contentType}`,
    `Path:${path}`,
  ]
  if (requestId) {
    lines.unshift(`X-RequestId:${requestId}`)
  }
  return lines.join('\r\n') + '\r\n\r\n' + body
}

/**
 * Find end of HTTP-like headers in binary message.
 * Looks for \r\n\r\n (CRLF CRLF).
 */
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

/**
 * Convenience: synthesize a single subtitle line.
 * Returns MP3 Blob.
 */
export async function edgeSynthesize(
  text: string,
  voice: string = DEFAULT_EDGE_VOICE,
): Promise<Blob> {
  return edgeTTS(text, voice, { rate: '+0%' })
}
