// TTS engine using OpenAI TTS API + audio timing sync.
//
// All TTS happens via REST API to OpenAI (CORS-enabled, works from any browser).
// Audio timing is synced to SRT: speed up if too long, pad silence if too short.
//
// Voices: alloy, echo, fable, onyx, nova, shimmer (multilingual, Indonesia natural)
// Output: WAV 24kHz mono, 16-bit PCM, durasi sync ke SRT asli.
//
// API key: user-provided, disimpan di localStorage, tidak pernah dikirim ke server kita.

'use client'

import type { SrtEntry, SrtPart } from './srt'
import {
  openaiTTS,
  OPENAI_VOICES,
  DEFAULT_OPENAI_VOICE,
  getApiKey,
  setApiKey as setApiKeyUtil,
  testApiKey,
  type OpenAIVoice,
} from './openai-tts'
import {
  decodeAudioBlob,
  adjustDuration,
  concatenateWithSilence,
  encodeWav,
  downloadBlob as downloadBlobUtil,
} from './audio-utils'

export { OPENAI_VOICES, DEFAULT_OPENAI_VOICE, type OpenAIVoice }
export { getApiKey, setApiKeyUtil as setApiKey, testApiKey }

const OUTPUT_SAMPLE_RATE = 24000

export interface TTSProgress {
  stage: 'idle' | 'synthesizing' | 'stitching' | 'done' | 'error'
  message?: string
  percent?: number // 0-100
}

export type ProgressCallback = (p: TTSProgress) => void

export interface NarrationOptions {
  voice: string
  apiKey: string
  respectTiming: boolean
  onLineProgress?: (current: number, total: number, text: string) => void
  onStage?: ProgressCallback
}

export interface NarrationResult {
  blob: Blob
  sampleRate: number
  durationSec: number
  previewUrl: string // Object URL for HTML5 audio preview
}

/**
 * Synthesize a single text chunk to MP3 via OpenAI TTS.
 */
export async function synthesizeText(
  text: string,
  voice: string,
  apiKey: string,
): Promise<{ audioBlob: Blob; mimeType: string }> {
  if (!text.trim()) {
    return { audioBlob: new Blob([]), mimeType: 'audio/mp3' }
  }
  const blob = await openaiTTS(text, voice, apiKey)
  return { audioBlob: blob, mimeType: 'audio/mp3' }
}

/**
 * Generate narration audio for a list of SRT entries, stitched into one WAV.
 * Returns blob + previewUrl (Object URL for HTML5 audio preview).
 */
export async function narrateEntries(
  entries: SrtEntry[],
  opts: NarrationOptions,
): Promise<NarrationResult> {
  if (entries.length === 0) throw new Error('No subtitles to narrate')

  opts.onStage?.({ stage: 'synthesizing', message: 'Mulai synthesizing…', percent: 0 })
  const total = entries.length
  const segments: Float32Array[] = []
  const silenceBefore: number[] = []
  let successCount = 0
  let failCount = 0
  let firstError = ''

  for (let i = 0; i < entries.length; i++) {
    const entry = entries[i]
    const text = entry.textLines.join(' ').trim()

    if (!text) {
      if (opts.respectTiming) {
        const cueDuration = entry.end - entry.start
        segments.push(new Float32Array(Math.floor(cueDuration * OUTPUT_SAMPLE_RATE)))
        silenceBefore.push(0)
      } else {
        segments.push(new Float32Array(0))
        silenceBefore.push(0)
      }
      opts.onLineProgress?.(i + 1, total, '(empty)')
      continue
    }

    opts.onLineProgress?.(i + 1, total, text.slice(0, 60))
    opts.onStage?.({
      stage: 'synthesizing',
      message: `Baris ${i + 1}/${total}: "${text.slice(0, 40)}${text.length > 40 ? '…' : ''}"`,
      percent: (i / total) * 100,
    })

    try {
      // 1. Synthesize to MP3 via OpenAI
      const { audioBlob } = await synthesizeText(text, opts.voice, opts.apiKey)
      if (audioBlob.size === 0) {
        throw new Error('Empty audio output')
      }

      // 2. Decode MP3 → AudioBuffer
      const audioBuffer = await decodeAudioBlob(audioBlob)

      // 3. Adjust duration to fit cue
      let adjusted: Float32Array
      if (opts.respectTiming) {
        const cueDuration = entry.end - entry.start
        const prevEnd = i > 0 ? entries[i - 1].end : 0
        const gapBefore = Math.max(0, entry.start - prevEnd)
        silenceBefore.push(Math.floor(gapBefore * OUTPUT_SAMPLE_RATE))
        adjusted = await adjustDuration(audioBuffer, cueDuration, OUTPUT_SAMPLE_RATE, { maxSpeedUp: 1.5 })
      } else {
        silenceBefore.push(Math.floor(0.3 * OUTPUT_SAMPLE_RATE))
        const mono = new Float32Array(audioBuffer.length)
        audioBuffer.copyFromChannel(mono, 0)
        adjusted = mono
      }

      segments.push(adjusted)
      successCount++
    } catch (e) {
      failCount++
      if (!firstError) firstError = (e as Error).message
      console.error('TTS failed for line', i, e)
      if (opts.respectTiming) {
        const cueDuration = entry.end - entry.start
        segments.push(new Float32Array(Math.floor(cueDuration * OUTPUT_SAMPLE_RATE)))
      } else {
        segments.push(new Float32Array(0))
      }
      silenceBefore.push(0)
    }
  }

  if (successCount === 0) {
    throw new Error(
      `TTS gagal untuk semua ${total} baris. Error pertama: ${firstError || 'unknown'}. ` +
      `Cek API key OpenAI kamu atau koneksi internet.`,
    )
  }

  if (failCount > 0) {
    console.warn(`TTS: ${successCount}/${total} berhasil, ${failCount} gagal.`)
  }

  opts.onStage?.({ stage: 'stitching', message: 'Menjahit audio…', percent: 90 })
  const allAudio = concatenateWithSilence(segments, silenceBefore, OUTPUT_SAMPLE_RATE)

  if (opts.respectTiming) {
    const targetEnd = entries[entries.length - 1].end
    const currentDuration = allAudio.length / OUTPUT_SAMPLE_RATE
    if (currentDuration < targetEnd) {
      const pad = Math.floor((targetEnd - currentDuration) * OUTPUT_SAMPLE_RATE)
      const padded = new Float32Array(allAudio.length + pad)
      padded.set(allAudio, 0)
      opts.onStage?.({ stage: 'stitching', message: `Padding ke ${targetEnd.toFixed(1)}s`, percent: 95 })
      const blob = encodeWav(padded, OUTPUT_SAMPLE_RATE)
      const previewUrl = URL.createObjectURL(blob)
      return { blob, sampleRate: OUTPUT_SAMPLE_RATE, durationSec: targetEnd, previewUrl }
    }
  }

  const blob = encodeWav(allAudio, OUTPUT_SAMPLE_RATE)
  const durationSec = allAudio.length / OUTPUT_SAMPLE_RATE
  const previewUrl = URL.createObjectURL(blob)
  opts.onStage?.({ stage: 'done', message: 'Narration selesai', percent: 100 })
  return { blob, sampleRate: OUTPUT_SAMPLE_RATE, durationSec, previewUrl }
}

export async function narratePart(part: SrtPart, opts: NarrationOptions): Promise<NarrationResult> {
  return narrateEntries(part.entries, opts)
}

export function downloadBlob(filename: string, blob: Blob) {
  downloadBlobUtil(filename, blob)
}

/**
 * Revoke an Object URL (cleanup memory after audio is no longer needed).
 */
export function revokePreviewUrl(url: string) {
  try {
    URL.revokeObjectURL(url)
  } catch {
    // ignore
  }
}

export function formatDuration(sec: number): string {
  if (!isFinite(sec)) return '0s'
  const h = Math.floor(sec / 3600)
  const m = Math.floor((sec % 3600) / 60)
  const s = Math.floor(sec % 60)
  if (h > 0) return `${h}j ${m}m ${s}s`
  if (m > 0) return `${m}m ${s}s`
  return `${s}s`
}

export function formatBytes(bytes: number): string {
  if (bytes === 0) return '0 B'
  const k = 1024
  const units = ['B', 'KB', 'MB', 'GB', 'TB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return `${(bytes / Math.pow(k, i)).toFixed(1)} ${units[i]}`
}
