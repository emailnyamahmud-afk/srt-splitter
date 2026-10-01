// OpenRouter TTS — unified API for many TTS models.
//
// OpenRouter adalah gateway ke berbagai model AI termasuk TTS. Pakai satu API key
// untuk akses banyak model: OpenAI TTS, ElevenLabs, MiniMax, dll.
//
// Endpoint: https://openrouter.ai/api/v1/audio/speech (OpenAI-compatible)
// API key: https://openrouter.ai/keys
// Free credit: $1 saat signup (cukup untuk ~67k chars atau ~10 menit audio)
//
// Indonesia support: tergantung model. OpenAI TTS-1-HD natural untuk Indonesia.
// MiniMax Speech-01-Turbo juga mendukung Indonesia dengan baik.

export interface OpenRouterModel {
  id: string
  label: string
  description: string
}

export const OPENROUTER_MODELS: OpenRouterModel[] = [
  { id: 'openai/tts-1-hd', label: 'OpenAI TTS-1 HD (Premium)', description: 'Natural multilingual, Indonesia bagus' },
  { id: 'openai/tts-1', label: 'OpenAI TTS-1 (Standard)', description: 'Lebih cepat, lebih murah' },
  { id: 'minimax/speech-01-turbo', label: 'MiniMax Speech-01 Turbo', description: 'Indonesia bagus, lebih murah' },
  { id: 'minimax/speech-02-hd', label: 'MiniMax Speech-02 HD', description: 'HD quality, lebih mahal' },
  { id: 'elevenlabs/eleven-turbo-v2-5', label: 'ElevenLabs Turbo v2.5', description: 'Voice cloning capability' },
  { id: 'elevenlabs/eleven-v3', label: 'ElevenLabs V3', description: 'Highest quality' },
]

export const DEFAULT_OPENROUTER_MODEL = 'openai/tts-1-hd'

const API_URL = 'https://openrouter.ai/api/v1/audio/speech'
const STORAGE_KEY_API_KEY = 'srt-splitter-openrouter-key'

/**
 * Get saved OpenRouter API key from localStorage.
 */
export function getApiKey(): string {
  if (typeof window === 'undefined') return ''
  return localStorage.getItem(STORAGE_KEY_API_KEY) || ''
}

/**
 * Save OpenRouter API key to localStorage.
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
        model: DEFAULT_OPENROUTER_MODEL,
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
    if (response.status === 402 || response.status === 429) {
      return { valid: false, error: 'Credit habis atau rate limit (402/429)' }
    }
    const text = await response.text().catch(() => '')
    return { valid: false, error: `HTTP ${response.status}: ${text.slice(0, 100)}` }
  } catch (e) {
    return { valid: false, error: (e as Error).message }
  }
}

/**
 * Synthesize text to MP3 via OpenRouter TTS API.
 *
 * @param text Text to synthesize
 * @param model Model ID (e.g. 'openai/tts-1-hd')
 * @param voice Voice ID (alloy, echo, fable, onyx, nova, shimmer untuk OpenAI)
 * @param apiKey OpenRouter API key
 * @returns MP3 Blob
 */
export async function openRouterTTS(
  text: string,
  model: string,
  voice: string,
  apiKey: string,
): Promise<Blob> {
  if (!apiKey.trim()) {
    throw new Error('OpenRouter API key belum diisi. Klik "Set API Key" untuk input.')
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
    }),
  })

  if (!response.ok) {
    if (response.status === 401) {
      throw new Error('OpenRouter API key tidak valid. Cek di https://openrouter.ai/keys')
    }
    if (response.status === 402) {
      throw new Error('Credit OpenRouter habis. Top up di https://openrouter.ai/credits')
    }
    if (response.status === 429) {
      throw new Error('Rate limit atau quota habis. Tunggu beberapa menit.')
    }
    if (response.status === 400) {
      const err = await response.json().catch(() => ({}))
      throw new Error(`Bad request: ${err.error?.message || 'model/voice tidak valid'}`)
    }
    throw new Error(`OpenRouter TTS error: HTTP ${response.status}`)
  }

  return await response.blob()
}
