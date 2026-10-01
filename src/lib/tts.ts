// Text-to-Speech engine using Transformers.js + MMS-TTS for Indonesian.
// All processing happens in the browser. Model is downloaded once (~100 MB)
// and cached in browser storage for offline use afterwards.
//
// Model: facebook/mms-tts-ind (Meta's Massively Multilingual Speech, VITS)
// Indonesian-only TTS, ~100 MB, Apache 2.0 license.
//
// Note: We originally tried Kokoro-82M (330 MB, 31 languages) but Transformers.js
// v4.3.0 doesn't yet include `style_text_to_speech_2` (Kokoro's architecture)
// in the text-to-speech pipeline task mapping. We use MMS-TTS-Ind which is
// natively supported via the VITS architecture and specifically trained for
// Indonesian, giving better quality for our use case anyway.

'use client'

import type {
  SrtEntry,
  SrtPart,
} from './srt'

// Lazy-loaded transformers.js to keep initial bundle small
type TextToSpeechPipeline = {
  (input: { text: string }): Promise<{ audio: Float32Array; sampling_rate: number }>
}

let _transformersPromise: Promise<typeof import('@huggingface/transformers')> | null = null
let _pipelinePromise: Promise<TextToSpeechPipeline> | null = null

async function getTransformers() {
  if (!_transformersPromise) {
    _transformersPromise = import('@huggingface/transformers')
  }
  return _transformersPromise
}

// MMS-TTS via Transformers.js. We use Xenova/mms-tts-eng (English) which is
// the most stable and most-tested VITS conversion available for browser usage.
// Text Indonesia akan terbaca dengan accent English, tapi setidaknya ADA SUARA
// (yang sebelumnya silent WAV).
//
// Bahasa Indonesia native (souba67/mms-tts-ind-ONNX) tidak stabil di transformers.js
// v3.7 / v4.3.0 — error "Tensor shape.Size() must be >= 0" di ONNX runtime.
// Kalau ada model Indonesia yang stabil nanti, ganti satu baris di bawah.
const MODEL_ID = 'Xenova/mms-tts-eng'

// MMS-TTS-Ind has a single default voice. We expose one option for clarity.
export const VOICES = [
  { id: 'default', label: 'English VITS (untuk text Indonesia, accent English)', lang: 'en' },
] as const

export const DEFAULT_VOICE = 'default'

export interface TTSProgress {
  stage: 'loading' | 'idle' | 'synthesizing' | 'stitching' | 'done' | 'error'
  message?: string
  percent?: number // 0-100
  modelBytesLoaded?: number
  modelBytesTotal?: number
}

export type ProgressCallback = (p: TTSProgress) => void

/**
 * Initialize the TTS pipeline. Downloads the model on first call (~100 MB).
 * Subsequent calls reuse the cached pipeline.
 */
export async function ensureTTSModel(onProgress?: ProgressCallback): Promise<TextToSpeechPipeline> {
  if (_pipelinePromise) return _pipelinePromise

  _pipelinePromise = (async () => {
    onProgress?.({ stage: 'loading', message: 'Loading transformers.js…' })
    const transformers = await getTransformers()
    const { pipeline, env } = transformers

    // Configure environment for browser usage
    env.allowLocalModels = false
    env.useBrowserCache = true
    env.allowRemoteModels = true

    onProgress?.({
      stage: 'loading',
      message: 'Downloading MMS-TTS-Eng model (~70 MB, first time only)…',
      percent: 0,
      modelBytesLoaded: 0,
      modelBytesTotal: 70 * 1024 * 1024,
    })

    const progress_callback = (data: unknown) => {
      const d = data as Record<string, unknown>
      const status = d.status as string
      if (status === 'progress') {
        const loaded = (d.loaded as number) || 0
        const total = (d.total as number) || 70 * 1024 * 1024
        const percent = total > 0 ? (loaded / total) * 100 : 0
        onProgress?.({
          stage: 'loading',
          message: `Downloading ${d.file as string}…`,
          percent,
          modelBytesLoaded: loaded,
          modelBytesTotal: total,
        })
      } else if (status === 'done') {
        onProgress?.({
          stage: 'loading',
          message: `Cached ${d.file as string}`,
          percent: 100,
        })
      } else if (status === 'ready') {
        onProgress?.({
          stage: 'idle',
          message: 'Model ready',
          percent: 100,
        })
      }
    }

    onProgress?.({ stage: 'loading', message: 'Initializing TTS pipeline…' })
    // Try quantized (q8) first - more stable in browser WASM, smaller download.
    // Fallback to fp32 if q8 fails.
    let pipe: TextToSpeechPipeline
    try {
      pipe = (await pipeline('text-to-speech', MODEL_ID, {
        dtype: 'q8',
        device: 'wasm',
        progress_callback,
      } as never)) as unknown as TextToSpeechPipeline
    } catch (e) {
      console.warn('q8 model load failed, trying fp32:', (e as Error).message)
      pipe = (await pipeline('text-to-speech', MODEL_ID, {
        dtype: 'fp32',
        device: 'wasm',
        progress_callback,
      } as never)) as unknown as TextToSpeechPipeline
    }

    onProgress?.({ stage: 'idle', message: 'Model ready', percent: 100 })
    return pipe
  })()

  return _pipelinePromise
}

/**
 * Preprocess text for VITS TTS — improve success rate.
 * - Lowercase
 * - Keep only basic Latin alphanumeric + common punctuation
 * - Strip emojis and special unicode (VITS tokenizer can't handle them)
 * - Collapse whitespace
 * - Ensure minimum length (VITS needs at least ~5 chars)
 */
function preprocessText(text: string): string {
  if (!text) return ''
  let cleaned = text
    // Lowercase
    .toLowerCase()
    // Remove emoji and unicode symbols (VITS tokenizer can't handle them)
    .replace(/[\u{1F000}-\u{1FFFF}\u{2600}-\u{27BF}\u{1F100}-\u{1F1FF}\u{FE00}-\u{FE0F}]/gu, '')
    // Keep only Latin letters, digits, basic punctuation, and spaces
    .replace(/[^a-z0-9\s.,!?;:'"()-]/g, ' ')
    // Collapse whitespace
    .replace(/\s+/g, ' ')
    .trim()

  // If too short, pad with a neutral filler to avoid VITS shape error
  if (cleaned.length < 5) {
    cleaned = (cleaned + ' ').padEnd(8, 'a')
  }
  return cleaned
}

/**
 * Synthesize a single text chunk to audio.
 * Returns Float32Array PCM samples (mono) + sample rate.
 * Uses the configured MODEL_ID (default: Xenova/mms-tts-eng).
 */
export async function synthesizeText(
  text: string,
  _voice?: string,
): Promise<{ audio: Float32Array; sampleRate: number }> {
  const cleanText = preprocessText(text)
  const pipe = await ensureTTSModel()
  const out = await pipe({ text: cleanText })
  if (!out.audio || out.audio.length === 0) {
    throw new Error('Model returned empty audio (text might be too short or contain only unknown characters)')
  }
  return { audio: out.audio, sampleRate: out.sampling_rate }
}

/**
 * Compute total duration in seconds for a WAV blob at given sample rate.
 */
function pcmDuration(sec: number, samples: number): number {
  return samples / (sec || 22050)
}

/**
 * Encode Float32Array PCM samples to a 16-bit PCM WAV Blob (mono).
 */
export function encodeWav(samples: Float32Array, sampleRate: number): Blob {
  const numChannels = 1
  const bytesPerSample = 2
  const blockAlign = numChannels * bytesPerSample
  const dataSize = samples.length * bytesPerSample
  const buffer = new ArrayBuffer(44 + dataSize)
  const view = new DataView(buffer)

  // RIFF header
  writeString(view, 0, 'RIFF')
  view.setUint32(4, 36 + dataSize, true)
  writeString(view, 8, 'WAVE')

  // fmt sub-chunk
  writeString(view, 12, 'fmt ')
  view.setUint32(16, 16, true) // sub-chunk size
  view.setUint16(20, 1, true) // audio format = PCM
  view.setUint16(22, numChannels, true)
  view.setUint32(24, sampleRate, true)
  view.setUint32(28, sampleRate * blockAlign, true) // byte rate
  view.setUint16(32, blockAlign, true)
  view.setUint16(34, 16, true) // bits per sample

  // data sub-chunk
  writeString(view, 36, 'data')
  view.setUint32(40, dataSize, true)

  // PCM samples (16-bit signed little-endian)
  let offset = 44
  for (let i = 0; i < samples.length; i++) {
    let s = samples[i]
    s = Math.max(-1, Math.min(1, s))
    const v = s < 0 ? s * 0x8000 : s * 0x7fff
    view.setInt16(offset, v, true)
    offset += 2
  }

  return new Blob([buffer], { type: 'audio/wav' })
}

function writeString(view: DataView, offset: number, str: string) {
  for (let i = 0; i < str.length; i++) {
    view.setUint8(offset + i, str.charCodeAt(i))
  }
}

/**
 * Concatenate Float32Array samples with optional silence padding (in seconds).
 */
function concatWithSilence(
  segments: { audio: Float32Array; sampleRate: number }[],
  silenceSecBefore: number[],
  sampleRate: number,
): Float32Array {
  const silenceSamples = silenceSecBefore.map((s) => Math.floor(s * sampleRate))
  let totalLength = 0
  for (let i = 0; i < segments.length; i++) {
    totalLength += silenceSamples[i] + segments[i].audio.length
  }
  const out = new Float32Array(totalLength)
  let offset = 0
  for (let i = 0; i < segments.length; i++) {
    // Pre-silence (already initialized to 0)
    offset += silenceSamples[i]
    out.set(segments[i].audio, offset)
    offset += segments[i].audio.length
  }
  return out
}

export interface NarrationOptions {
  voice: string
  // If true, audio is generated to fit each cue's exact duration
  // (we synthesize normally and pad with silence to match end time).
  respectTiming: boolean
  // Called for each subtitle line processed
  onLineProgress?: (current: number, total: number, text: string) => void
  onStage?: ProgressCallback
}

export interface NarrationResult {
  blob: Blob
  sampleRate: number
  durationSec: number
}

/**
 * Generate narration audio for a list of SRT entries, stitched into one WAV.
 * Each line is synthesized separately, with silence padding to align to
 * the original SRT timing.
 *
 * IMPORTANT: If ALL lines fail to synthesize, throws Error so caller can
 * show a clear message instead of producing a silent WAV.
 */
export async function narrateEntries(
  entries: SrtEntry[],
  opts: NarrationOptions,
): Promise<NarrationResult> {
  if (entries.length === 0) throw new Error('No subtitles to narrate')

  opts.onStage?.({ stage: 'synthesizing', message: 'Starting synthesis…', percent: 0 })
  const total = entries.length
  let sampleRate = 22050
  const segments: { audio: Float32Array }[] = []
  const silenceBefore: number[] = []
  let successCount = 0
  let failCount = 0
  let firstError = ''

  for (let i = 0; i < entries.length; i++) {
    const entry = entries[i]
    const text = entry.textLines.join(' ').trim()
    if (!text) {
      segments.push({ audio: new Float32Array(0) })
      silenceBefore.push(opts.respectTiming ? Math.max(0, entry.start - (i > 0 ? entries[i - 1].end : 0)) : 0)
      opts.onLineProgress?.(i + 1, total, '(empty)')
      continue
    }

    opts.onLineProgress?.(i + 1, total, text.slice(0, 60))
    opts.onStage?.({
      stage: 'synthesizing',
      message: `Line ${i + 1}/${total}: "${text.slice(0, 40)}${text.length > 40 ? '…' : ''}"`,
      percent: (i / total) * 100,
    })

    try {
      const out = await synthesizeText(text, opts.voice)
      if (!out.audio || out.audio.length === 0) {
        throw new Error('Empty audio output from model')
      }
      sampleRate = out.sampleRate
      segments.push({ audio: out.audio })
      successCount++
      if (opts.respectTiming) {
        const prevEnd = i > 0 ? entries[i - 1].end : 0
        const gap = Math.max(0, entry.start - prevEnd)
        silenceBefore.push(gap)
      } else {
        silenceBefore.push(0.3) // 300ms gap between lines
      }
    } catch (e) {
      failCount++
      if (!firstError) firstError = (e as Error).message
      console.error('TTS failed for line', i, e)
      // Push empty segment + maintain timing (gap = full duration of this cue)
      segments.push({ audio: new Float32Array(0) })
      silenceBefore.push(0)
    }
  }

  // SAFETY CHECK: If ALL lines failed, throw error instead of producing silence.
  if (successCount === 0) {
    throw new Error(
      `TTS gagal untuk semua ${total} baris. Model tidak bisa menghasilkan audio. ` +
      `Error pertama: ${firstError || 'unknown'}. ` +
      `Coba refresh halaman dan reload model, atau gunakan subtitle dengan text lebih panjang.`,
    )
  }

  // If some lines failed, log warning
  if (failCount > 0) {
    console.warn(`TTS: ${successCount}/${total} baris berhasil, ${failCount} gagal. Audio hasil akan ada bagian yang hilang.`)
  }

  opts.onStage?.({ stage: 'stitching', message: 'Stitching audio…', percent: 90 })
  const allAudio = concatWithSilence(
    segments.map((s) => ({ audio: s.audio, sampleRate })),
    silenceBefore,
    sampleRate,
  )

  // Check that we actually have audio data, not just silence padding
  let maxAmplitude = 0
  for (let i = 0; i < allAudio.length; i++) {
    const abs = Math.abs(allAudio[i])
    if (abs > maxAmplitude) maxAmplitude = abs
  }

  if (maxAmplitude < 0.001) {
    // Audio is essentially silent
    throw new Error(
      `TTS menghasilkan audio yang hampir senyap (max amplitude: ${maxAmplitude}). ` +
      `Kemungkinan model gagal untuk semua baris subtitle. ` +
      `Coba refresh halaman, atau gunakan subtitle dengan text Indonesia yang lebih panjang.`,
    )
  }

  // If respectTiming, pad final audio to match total SRT duration
  if (opts.respectTiming) {
    const targetEnd = entries[entries.length - 1].end
    const currentDuration = allAudio.length / sampleRate
    if (currentDuration < targetEnd) {
      const pad = Math.floor((targetEnd - currentDuration) * sampleRate)
      const padded = new Float32Array(allAudio.length + pad)
      padded.set(allAudio, 0)
      // (rest stays 0 = silence)
      opts.onStage?.({
        stage: 'stitching',
        message: `Padding to ${targetEnd.toFixed(1)}s`,
        percent: 95,
      })
      const blob = encodeWav(padded, sampleRate)
      return { blob, sampleRate, durationSec: targetEnd }
    }
  }

  const blob = encodeWav(allAudio, sampleRate)
  const durationSec = allAudio.length / sampleRate
  opts.onStage?.({ stage: 'done', message: 'Narration complete', percent: 100 })
  return { blob, sampleRate, durationSec }
}

/**
 * Generate narration for one SRT split part.
 */
export async function narratePart(
  part: SrtPart,
  opts: NarrationOptions,
): Promise<NarrationResult> {
  return narrateEntries(part.entries, opts)
}

/**
 * Generate narration for ALL parts, returning one blob per part.
 * Useful for "generate full duration" workflow.
 */
export async function narrateAllParts(
  parts: SrtPart[],
  opts: NarrationOptions,
): Promise<NarrationResult[]> {
  const results: NarrationResult[] = []
  for (let i = 0; i < parts.length; i++) {
    opts.onStage?.({
      stage: 'synthesizing',
      message: `Part ${i + 1}/${parts.length}`,
      percent: (i / parts.length) * 100,
    })
    const result = await narratePart(parts[i], opts)
    results.push(result)
  }
  opts.onStage?.({ stage: 'done', message: 'All parts complete', percent: 100 })
  return results
}

/**
 * Trigger a browser download for a Blob.
 */
export function downloadBlob(filename: string, blob: Blob) {
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  setTimeout(() => URL.revokeObjectURL(url), 2000)
}

/**
 * Format seconds as "Xj Ym Zs" or "Ym Zs" or "Zs"
 */
export function formatDuration(sec: number): string {
  if (!isFinite(sec)) return '0s'
  const h = Math.floor(sec / 3600)
  const m = Math.floor((sec % 3600) / 60)
  const s = Math.floor(sec % 60)
  if (h > 0) return `${h}j ${m}m ${s}s`
  if (m > 0) return `${m}m ${s}s`
  return `${s}s`
}

/**
 * Format bytes as human-readable size.
 */
export function formatBytes(bytes: number): string {
  if (bytes === 0) return '0 B'
  const k = 1024
  const units = ['B', 'KB', 'MB', 'GB', 'TB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return `${(bytes / Math.pow(k, i)).toFixed(1)} ${units[i]}`
}

/**
 * Browser SpeechSynthesis API — untuk PREVIEW (dengar langsung).
 * Gratis, instant, tidak butuh download model. Di macOS ada voice
 * Indonesia "Damayanti" yang kualitas OK. Di Windows/Linux tergantung OS.
 *
 * Note: SpeechSynthesis TIDAK bisa di-capture ke file audio di kebanyakan
 * browser (security restriction). Untuk export ke file, gunakan VITS model.
 */
export interface BrowserVoice {
  voiceURI: string
  name: string
  lang: string
  localService: boolean
  default: boolean
}

export function getIndonesianBrowserVoices(): BrowserVoice[] {
  if (typeof window === 'undefined' || !window.speechSynthesis) return []
  const all = window.speechSynthesis.getVoices()
  return all
    .filter((v) => v.lang.toLowerCase().startsWith('id'))
    .map((v) => ({
      voiceURI: v.voiceURI,
      name: v.name,
      lang: v.lang,
      localService: v.localService,
      default: v.default,
    }))
}

export function getAllBrowserVoices(): BrowserVoice[] {
  if (typeof window === 'undefined' || !window.speechSynthesis) return []
  return window.speechSynthesis.getVoices().map((v) => ({
    voiceURI: v.voiceURI,
    name: v.name,
    lang: v.lang,
    localService: v.localService,
    default: v.default,
  }))
}

/**
 * Preview a subtitle line using browser SpeechSynthesis.
 * Returns a promise that resolves when the speech finishes.
 */
export function previewWithBrowserTTS(
  text: string,
  voiceURI?: string,
  rate = 1.0,
  pitch = 1.0,
): Promise<void> {
  return new Promise((resolve, reject) => {
    if (typeof window === 'undefined' || !window.speechSynthesis) {
      reject(new Error('Browser tidak mendukung SpeechSynthesis API'))
      return
    }
    // Cancel any pending speech
    window.speechSynthesis.cancel()

    const utterance = new SpeechSynthesisUtterance(text)
    utterance.rate = rate
    utterance.pitch = pitch
    utterance.lang = 'id-ID' // default to Indonesian

    // Find voice by URI, or default to Indonesian voice
    const allVoices = window.speechSynthesis.getVoices()
    let chosen: SpeechSynthesisVoice | undefined
    if (voiceURI) {
      chosen = allVoices.find((v) => v.voiceURI === voiceURI)
    }
    if (!chosen) {
      // Try Indonesian first
      chosen = allVoices.find((v) => v.lang.toLowerCase().startsWith('id'))
    }
    if (chosen) {
      utterance.voice = chosen
      utterance.lang = chosen.lang
    }

    utterance.onend = () => resolve()
    utterance.onerror = (e) => reject(new Error('SpeechSynthesis error: ' + e.error))
    window.speechSynthesis.speak(utterance)
  })
}

export function stopBrowserTTS() {
  if (typeof window !== 'undefined' && window.speechSynthesis) {
    window.speechSynthesis.cancel()
  }
}

/**
 * Check if browser has Indonesian voice available.
 */
export function hasIndonesianBrowserVoice(): boolean {
  if (typeof window === 'undefined' || !window.speechSynthesis) return false
  const voices = window.speechSynthesis.getVoices()
  return voices.some((v) => v.lang.toLowerCase().startsWith('id'))
}

/**
 * Some browsers (especially Chrome on first load) need a "voices changed"
 * event before voices are available. This function ensures voices are loaded.
 */
export function ensureBrowserVoicesLoaded(): Promise<BrowserVoice[]> {
  return new Promise((resolve) => {
    if (typeof window === 'undefined' || !window.speechSynthesis) {
      resolve([])
      return
    }
    let voices = window.speechSynthesis.getVoices()
    if (voices.length > 0) {
      resolve(voices.map((v) => ({
        voiceURI: v.voiceURI,
        name: v.name,
        lang: v.lang,
        localService: v.localService,
        default: v.default,
      })))
      return
    }
    // Wait for voiceschanged event
    window.speechSynthesis.onvoiceschanged = () => {
      voices = window.speechSynthesis.getVoices()
      resolve(voices.map((v) => ({
        voiceURI: v.voiceURI,
        name: v.name,
        lang: v.lang,
        localService: v.localService,
        default: v.default,
      })))
    }
    // Fallback timeout
    setTimeout(() => {
      voices = window.speechSynthesis.getVoices()
      resolve(voices.map((v) => ({
        voiceURI: v.voiceURI,
        name: v.name,
        lang: v.lang,
        localService: v.localService,
        default: v.default,
      })))
    }, 1000)
  })
}

// Re-export for compile-time check
export const _pcmDuration = pcmDuration
