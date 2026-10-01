// OpenAI TTS — premium neural voices via REST API.
//
// Why OpenAI TTS (replacing Edge TTS):
//   Edge TTS uses WebSocket to Microsoft's endpoint, but browsers can't set
//   the `Origin` header to chrome-extension://... so Microsoft rejects the
//   connection. OpenAI TTS works directly from browser (CORS-enabled).
//
// Voices: alloy, echo, fable, onyx, nova, shimmer (model: tts-1-hd)
// Output: MP3 (24kHz mono) or WAV/Opus/FLAC
// Indonesia support: model is multilingual — text Indonesia dibaca natural
//   dengan accent yang sesuai (terutama voice 'nova' dan 'shimmer').
//
// Cost: $0.015/1k chars (tts-1-hd) — ~$1 per 67k chars = ~10 menit audio
// Free credit: $5 saat signup baru di https://platform.openai.com
//
// API key: disimpan di localStorage, tidak pernah dikirim ke server kita.

export interface OpenAIVoice {
  id: string
  label: string
  description: string
}

export const OPENAI_VOICES: OpenAIVoice[] = [
  { id: 'nova', label: 'Nova (Female, natural)', description: 'Natural untuk Indonesia, accent hangat' },
  { id: 'shimmer', label: 'Shimmer (Female, clear)', description: 'Jernih, cocok untuk narasi formal' },
  { id: 'alloy', label: 'Alloy (Neutral)', description: 'Netral gender, cocok untuk apapun' },
  { id: 'echo', label: 'Echo (Male, warm)', description: 'Laki-laki, hangat' },
  { id: 'fable', label: 'Fable (Male, narrative)', description: 'Laki-laki, cocok untuk cerita' },
  { id: 'onyx', label: 'Onyx (Male, deep)', description: 'Laki-laki, suara dalam' },
]

export const DEFAULT_OPENAI_VOICE = 'nova'

const API_URL = 'https://api.openai.com/v1/audio/speech'

const STORAGE_KEY_API_KEY = 'srt-splitter-openai-key'

/**
 * Get saved OpenAI API key from localStorage.
 */
export function getApiKey(): string {
  if (typeof window === 'undefined') return ''
  return localStorage.getItem(STORAGE_KEY_API_KEY) || ''
}

/**
 * Save OpenAI API key to localStorage.
 */
export function setApiKey(key: string): void {
  if (typeof window === 'undefined') return
  if (key.trim()) {
    localStorage.setItem(STORAGE_KEY_API_KEY, key.trim())
  } else {
    localStorage.removeItem(STORAGE_KEY_API_KEY)
  }
}

/**
 * Test if API key is valid by making a tiny TTS request.
 * Returns { valid: true } if valid, { valid: false, error: string } if not.
 */
export async function testApiKey(apiKey: string): Promise<{ valid: boolean; error?: string }> {
  if (!apiKey.trim()) {
    return { valid: false, error: 'API key kosong' }
  }
  try {
    const response = await fetch(API_URL, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${apiKey.trim()}`,
      },
      body: JSON.stringify({
        model: 'tts-1',
        voice: 'alloy',
        input: 'test',
        response_format: 'mp3',
      }),
    })
    if (response.ok) {
      return { valid: true }
    }
    if (response.status === 401) {
      return { valid: false, error: 'API key tidak valid (401 Unauthorized)' }
    }
    if (response.status === 429) {
      return { valid: false, error: 'Rate limit exceeded atau quota habis (429)' }
    }
    const text = await response.text().catch(() => '')
    return { valid: false, error: `HTTP ${response.status}: ${text.slice(0, 100)}` }
  } catch (e) {
    return { valid: false, error: (e as Error).message }
  }
}

/**
 * Synthesize text to MP3 via OpenAI TTS API.
 *
 * @param text Text to synthesize (any language, model is multilingual)
 * @param voice Voice ID (alloy, echo, fable, onyx, nova, shimmer)
 * @param apiKey OpenAI API key (starts with 'sk-...')
 * @param model Model to use ('tts-1' for fast/cheap, 'tts-1-hd' for premium)
 * @returns MP3 Blob (24kHz mono)
 */
export async function openaiTTS(
  text: string,
  voice: string = DEFAULT_OPENAI_VOICE,
  apiKey: string,
  model: string = 'tts-1-hd',
  speed: number = 1.0,
): Promise<Blob> {
  if (!apiKey.trim()) {
    throw new Error('OpenAI API key belum diisi. Klik "Set API Key" untuk input.')
  }
  if (!text.trim()) {
    return new Blob([])
  }

  const response = await fetch(API_URL, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${apiKey.trim()}`,
    },
    body: JSON.stringify({
      model,
      voice,
      input: text,
      response_format: 'mp3',
      speed, // Server-side speed change, pitch tetap natural
    }),
  })

  if (!response.ok) {
    if (response.status === 401) {
      throw new Error('API key tidak valid. Cek kembali key di https://platform.openai.com/api-keys')
    }
    if (response.status === 429) {
      throw new Error('Rate limit atau quota habis. Tunggu beberapa menit atau top up credit.')
    }
    if (response.status === 400) {
      const err = await response.json().catch(() => ({}))
      throw new Error(`Bad request: ${err.error?.message || 'text mungkin terlalu panjang'}`)
    }
    throw new Error(`OpenAI TTS error: HTTP ${response.status}`)
  }

  return await response.blob()
}
