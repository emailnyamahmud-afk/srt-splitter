// Translation module — translate SRT text via Google Translate (gratis) atau OpenAI (premium).
//
// Support:
//   - English (en) → Indonesian (id)
//   - Indonesian (id) → Javanese (jv)
//   - Indonesian (id) → English (en)
//   - Javanese (jv) → Indonesian (id)
//   - Auto-detect → any language
//
// Gratis: Google Translate via Vercel function /api/translate
// Premium: OpenAI API (user punya API key)

'use client'

import type { SrtEntry } from './srt'
import { getApiKey as getOpenAIKey } from './openai-tts'

export interface LanguagePair {
  code: string
  label: string
}

export const LANGUAGES: LanguagePair[] = [
  { code: 'auto', label: 'Auto-detect' },
  { code: 'en', label: 'English' },
  { code: 'id', label: 'Indonesia' },
  { code: 'jv', label: 'Jawa' },
  { code: 'su', label: 'Sunda' },
  { code: 'ms', label: 'Melayu' },
  { code: 'zh', label: 'Mandarin' },
  { code: 'ja', label: 'Jepang' },
  { code: 'ko', label: 'Korea' },
  { code: 'ar', label: 'Arab' },
  { code: 'es', label: 'Spanyol' },
  { code: 'fr', label: 'Prancis' },
  { code: 'de', label: 'Jerman' },
  { code: 'nl', label: 'Belanda' },
  { code: 'pt', label: 'Portugis' },
  { code: 'ru', label: 'Rusia' },
  { code: 'th', label: 'Thai' },
  { code: 'vi', label: 'Vietnam' },
  { code: 'hi', label: 'Hindi' },
  { code: 'tr', label: 'Turki' },
]

/**
 * Translate text via Google Translate (gratis, via Vercel function).
 */
export async function translateText(
  text: string,
  from: string = 'auto',
  to: string = 'id',
): Promise<{ translated: string; detectedFrom: string }> {
  if (!text.trim()) {
    return { translated: text, detectedFrom: from }
  }

  const url = '/api/translate'
  const response = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ text, from, to }),
  })

  if (!response.ok) {
    let errorMsg = `HTTP ${response.status}`
    try {
      const err = await response.json()
      if (err.error) errorMsg = err.error
    } catch {}
    throw new Error(`Translate error: ${errorMsg}`)
  }

  const data = await response.json()
  return {
    translated: data.translated,
    detectedFrom: data.detectedFrom || from,
  }
}

/**
 * Translate text via OpenAI API (premium, user punya API key).
 * Kualitas lebih baik untuk bahasa daerah (Jawa, Sunda).
 */
export async function translateTextOpenAI(
  text: string,
  from: string,
  to: string,
  apiKey?: string,
): Promise<string> {
  if (!text.trim()) return text

  const key = apiKey || getOpenAIKey()
  if (!key) throw new Error('OpenAI API key belum diisi')

  const langName = LANGUAGES.find(l => l.code === to)?.label || to
  const fromName = LANGUAGES.find(l => l.code === from)?.label || from

  const prompt = `Translate the following text from ${fromName} to ${langName}. Only return the translated text, nothing else.\n\n${text}`

  const response = await fetch('https://api.openai.com/v1/chat/completions', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${key}`,
    },
    body: JSON.stringify({
      model: 'gpt-4o-mini',
      messages: [
        { role: 'system', content: `You are a professional translator. Translate from ${fromName} to ${langName}. Return only the translated text.` },
        { role: 'user', content: text },
      ],
      temperature: 0.3,
    }),
  })

  if (!response.ok) {
    throw new Error(`OpenAI translate error: HTTP ${response.status}`)
  }

  const data = await response.json()
  return data.choices?.[0]?.message?.content?.trim() || text
}

export interface TranslateProgress {
  current: number
  total: number
  text: string
}

/**
 * Translate semua subtitle entries.
 * Mengembalikan entries baru dengan text yang sudah di-translate.
 */
export async function translateEntries(
  entries: SrtEntry[],
  from: string,
  to: string,
  useOpenAI: boolean = false,
  apiKey?: string,
  onProgress?: (p: TranslateProgress) => void,
): Promise<SrtEntry[]> {
  const total = entries.length
  const translated: SrtEntry[] = []

  for (let i = 0; i < entries.length; i++) {
    const entry = entries[i]
    const originalText = entry.textLines.join('\n')

    onProgress?.({ current: i + 1, total, text: originalText.slice(0, 60) })

    let translatedText: string
    try {
      if (useOpenAI) {
        translatedText = await translateTextOpenAI(originalText, from, to, apiKey)
      } else {
        const result = await translateText(originalText, from, to)
        translatedText = result.translated
      }
    } catch (e) {
      console.error(`Translate failed for line ${i + 1}:`, e)
      translatedText = originalText // fallback: pakai text asli
    }

    translated.push({
      ...entry,
      textLines: translatedText.split('\n'),
    })
  }

  return translated
}
