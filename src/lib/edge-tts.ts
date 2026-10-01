// Microsoft Edge TTS — free neural voices Indonesia native (Gadis/Ardi).
//
// Browser JavaScript cannot connect directly to speech.platform.bing.com because:
//   1. Microsoft requires Origin: chrome-extension://... (browser can't set this)
//   2. Requires Sec-MS-GEC token (based on Chromium version + SHA256)
//
// Solution: Use Vercel serverless proxy at /api/edge-tts
// The proxy runs Node.js, can set Origin header, and forwards request to Microsoft.
//
// Voices: id-ID-GadisNeural (female), id-ID-ArdiNeural (male) — natural Indonesia.
// Free, no API key, no authentication (proxy handles it).

export interface EdgeVoice {
  name: string
  label: string
  lang: string
  gender: 'Male' | 'Female'
}

export const EDGE_VOICES: EdgeVoice[] = [
  { name: 'id-ID-GadisNeural', label: '🇮🇩 Indonesia — Gadis (Perempuan)', lang: 'id-ID', gender: 'Female' },
  { name: 'id-ID-ArdiNeural', label: '🇮🇩 Indonesia — Ardi (Laki-laki)', lang: 'id-ID', gender: 'Male' },
  { name: 'jv-ID-SitiNeural', label: '🇮🇩 Jawa — Siti (Perempuan)', lang: 'jv-ID', gender: 'Female' },
  { name: 'jv-ID-DimasNeural', label: '🇮🇩 Jawa — Dimas (Laki-laki)', lang: 'jv-ID', gender: 'Male' },
]

export const DEFAULT_EDGE_VOICE = 'id-ID-GadisNeural'

// Detect environment: Vercel (production) or static GitHub Pages
function getProxyUrl(): string {
  if (typeof window === 'undefined') return '/api/edge-tts'
  // Check user-configured proxy URL first (highest priority — works on any deployment)
  const configured = localStorage.getItem('srt-splitter-edge-proxy-url')
  if (configured && configured.trim()) return configured.trim()
  // On Vercel: same-origin /api/edge-tts works
  const origin = window.location.origin
  if (origin.includes('vercel.app')) {
    return '/api/edge-tts'
  }
  // localhost dev: use default (will 404 unless user sets proxy URL)
  if (origin.includes('localhost') || origin.includes('127.0.0.1')) {
    return '/api/edge-tts'
  }
  // For GitHub Pages or other static: return /api/edge-tts as default
  // (User must set proxy URL in UI for this to actually work)
  return '/api/edge-tts'
}

export function getEdgeProxyUrl(): string {
  return getProxyUrl()
}

export function setEdgeProxyUrl(url: string): void {
  if (typeof window === 'undefined') return
  if (url.trim()) {
    localStorage.setItem('srt-splitter-edge-proxy-url', url.trim())
  } else {
    localStorage.removeItem('srt-splitter-edge-proxy-url')
  }
}

/**
 * Synthesize text via Edge TTS proxy.
 * Returns MP3 Blob (24kHz mono, 48kbps).
 *
 * @param opts.targetDuration Kalau diisi (detik), server akan time-stretch audio
 *   ke target duration dengan FFmpeg atempo (pitch natural, no chipmunk).
 */
export async function edgeTTS(
  text: string,
  voice: string = DEFAULT_EDGE_VOICE,
  opts: { rate?: string; volume?: string; pitch?: string } = {},
): Promise<Blob> {
  const { rate = '+0%', volume = '+0%', pitch = '+0Hz' } = opts
  if (!text.trim()) {
    return new Blob([])
  }

  const url = getProxyUrl()
  const response = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ text, voice, rate, volume, pitch }),
  })

  if (!response.ok) {
    let errorMsg = `HTTP ${response.status}`
    try {
      const err = await response.json()
      if (err.error) errorMsg = err.error
    } catch {
      // ignore parse error
    }
    throw new Error(`Edge TTS proxy error: ${errorMsg}`)
  }

  return await response.blob()
}

export async function edgeSynthesize(text: string, voice: string = DEFAULT_EDGE_VOICE): Promise<Blob> {
  return edgeTTS(text, voice, { rate: '+0%' })
}
