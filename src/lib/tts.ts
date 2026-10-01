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

// MMS-TTS-Ind — Meta's Massively Multilingual Speech, Indonesian voice.
// VITS architecture, supported by transformers.js v3+ out of the box.
// Pre-converted to ONNX by souba67 for in-browser usage.
const MODEL_ID = 'souba67/mms-tts-ind-ONNX'

// MMS-TTS-Ind has a single default voice. We expose one option for clarity.
export const VOICES = [
  { id: 'default', label: 'Indonesia (MMS default voice)', lang: 'id-ID' },
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
      message: 'Downloading MMS-TTS-Indonesia model (~100 MB, first time only)…',
      percent: 0,
      modelBytesLoaded: 0,
      modelBytesTotal: 100 * 1024 * 1024,
    })

    const progress_callback = (data: unknown) => {
      const d = data as Record<string, unknown>
      const status = d.status as string
      if (status === 'progress') {
        const loaded = (d.loaded as number) || 0
        const total = (d.total as number) || 100 * 1024 * 1024
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
    const pipe = (await pipeline('text-to-speech', MODEL_ID, {
      dtype: 'fp32',
      device: 'wasm',
      progress_callback,
    } as never)) as unknown as TextToSpeechPipeline

    onProgress?.({ stage: 'idle', message: 'Model ready', percent: 100 })
    return pipe
  })()

  return _pipelinePromise
}

/**
 * Synthesize a single text chunk to audio.
 * Returns Float32Array PCM samples (mono) + sample rate.
 */
export async function synthesizeText(
  text: string,
  _voice?: string,
): Promise<{ audio: Float32Array; sampleRate: number }> {
  const pipe = await ensureTTSModel()
  const out = await pipe({ text })
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
      sampleRate = out.sampleRate
      segments.push({ audio: out.audio })
      if (opts.respectTiming) {
        const prevEnd = i > 0 ? entries[i - 1].end : 0
        const gap = Math.max(0, entry.start - prevEnd)
        silenceBefore.push(gap)
      } else {
        silenceBefore.push(0.3) // 300ms gap between lines
      }
    } catch (e) {
      console.error('TTS failed for line', i, e)
      segments.push({ audio: new Float32Array(0) })
      silenceBefore.push(0)
    }
  }

  opts.onStage?.({ stage: 'stitching', message: 'Stitching audio…', percent: 90 })
  const allAudio = concatWithSilence(
    segments.map((s) => ({ audio: s.audio, sampleRate })),
    silenceBefore,
    sampleRate,
  )

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

// Re-export for compile-time check
export const _pcmDuration = pcmDuration
