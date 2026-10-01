// Kokoro TTS — High-quality browser-based TTS using kokoro-js library
//
// Reference: SubtitleKit.com pakai library yang sama.
// Library: kokoro-js (npm package by hexgrad/Xenova)
// Model: onnx-community/Kokoro-82M-v1.0-ONNX (~330MB FP32, ~80MB Q8)
// Voices: 54 voices (English, Spanish, French, Hindi, Italian, Japanese, Portuguese, Mandarin)
//
// Indonesia: Kokoro model multilingual, text Indonesia bisa di-baca dengan voice multilingual
//   Best for Indonesia: pf_dora (Portuguese female), ef_dora (Spanish female), af_heart (English female natural)
//
// Runs entirely in browser dengan WASM/WebGPU. 100% offline setelah download model.
// Butuh COI serviceworker (sudah ada di repo) untuk SharedArrayBuffer (multi-thread WASM).

'use client'

import type { SrtEntry, SrtPart } from './srt'
import {
  decodeAudioBlob,
  adjustDuration,
  concatenateWithSilence,
  encodeWav,
  downloadBlob as downloadBlobUtil,
} from './audio-utils'

const OUTPUT_SAMPLE_RATE = 24000

// Dynamic import di browser-only (avoid SSR — kokoro-js pakai path/fs yang tidak ada di server)
// Pakai variable specifier supaya bundler tidak tree-shake
const KOKORO_MODULE = 'kokoro-js'
const loadKokoroLib = async () => {
  const mod = await import(/* @vite-ignore */ KOKORO_MODULE)
  return mod
}

// Lazy-loaded TTS instance (model load is heavy, only do on demand)
let _ttsInstance: Promise<KokoroTTSInstance> | null = null

interface KokoroTTSInstance {
  generate(text: string, opts: { voice: string; speed?: number }): Promise<{ audio: Float32Array; sampling_rate: number }>
  voices: Record<string, { name: string; language: string; gender: string }>
}

export interface KokoroVoice {
  id: string
  label: string
  language: string
  gender: string
}

// Curated list untuk Indonesia-friendly voices (Kokoro tidak punya voice Indonesia native,
// tapi beberapa voice multilingual bisa baca text Indonesia dengan accent yang reasonable).
export const KOKORO_VOICES: KokoroVoice[] = [
  { id: 'pf_dora', label: '🇧🇷 Dora (Portuguese female) — accent mirip Indonesia', language: 'pt-br', gender: 'Female' },
  { id: 'ef_dora', label: '🇪🇸 Dora (Spanish female) — accent mirip Indonesia', language: 'es', gender: 'Female' },
  { id: 'af_heart', label: '🇺🇸 Heart (English female, natural)', language: 'en-us', gender: 'Female' },
  { id: 'af_bella', label: '🇺🇸 Bella (English female, natural)', language: 'en-us', gender: 'Female' },
  { id: 'af_nova', label: '🇺🇸 Nova (English female)', language: 'en-us', gender: 'Female' },
  { id: 'am_michael', label: '🇺🇸 Michael (English male)', language: 'en-us', gender: 'Male' },
  { id: 'am_adam', label: '🇺🇸 Adam (English male)', language: 'en-us', gender: 'Male' },
  { id: 'bf_emma', label: '🇬🇧 Emma (British English female)', language: 'en-gb', gender: 'Female' },
  { id: 'bm_george', label: '🇬🇧 George (British English male)', language: 'en-gb', gender: 'Male' },
  { id: 'ff_siwis', label: '🇫🇷 Siwis (French female)', language: 'fr-fr', gender: 'Female' },
  { id: 'zf_xiaoxiao', label: '🇨🇳 Xiaoxiao (Mandarin female)', language: 'zh-cn', gender: 'Female' },
  { id: 'jf_alpha', label: '🇯🇵 Alpha (Japanese female)', language: 'ja', gender: 'Female' },
]

export const DEFAULT_KOKORO_VOICE = 'pf_dora'

const MODEL_ID = 'onnx-community/Kokoro-82M-v1.0-ONNX'

export interface TTSProgress {
  stage: 'loading' | 'idle' | 'synthesizing' | 'stitching' | 'done' | 'error'
  message?: string
  percent?: number
  modelBytesLoaded?: number
  modelBytesTotal?: number
}

export type ProgressCallback = (p: TTSProgress) => void

let _modelLoadingProgress: ProgressCallback | null = null
let _modelReady = false

/**
 * Load Kokoro model. ~330MB FP32 or ~80MB Q8 (default).
 * Cached di browser Cache API (COI required untuk SharedArrayBuffer).
 */
export async function ensureKokoroModel(onProgress?: ProgressCallback): Promise<KokoroTTSInstance> {
  if (_ttsInstance) return _ttsInstance

  _modelLoadingProgress = onProgress || null

  _ttsInstance = (async () => {
    onProgress?.({ stage: 'loading', message: 'Loading kokoro-js library…', percent: 0 })
    const kokoroModule = await loadKokoroLib()
    const KokoroTTS = (kokoroModule as unknown as { default?: unknown; KokoroTTS?: unknown }).default ?? (kokoroModule as unknown as { KokoroTTS?: unknown }).KokoroTTS ?? kokoroModule
    onProgress?.({ stage: 'loading', message: 'Downloading Kokoro-82M model (~80 MB Q8, first time only)…', percent: 5 })

    const progress_callback = (data: unknown) => {
      const d = data as Record<string, unknown>
      const status = d.status as string
      if (status === 'progress') {
        const loaded = (d.loaded as number) || 0
        const total = (d.total as number) || 80 * 1024 * 1024
        const percent = 5 + (loaded / total) * 90 // 5-95%
        onProgress?.({
          stage: 'loading',
          message: `Downloading ${d.file as string}…`,
          percent,
          modelBytesLoaded: loaded,
          modelBytesTotal: total,
        })
      } else if (status === 'done') {
        onProgress?.({ stage: 'loading', message: `Cached ${d.file as string}`, percent: 95 })
      } else if (status === 'ready') {
        onProgress?.({ stage: 'idle', message: 'Model ready', percent: 100 })
      }
    }

    onProgress?.({ stage: 'loading', message: 'Initializing Kokoro TTS pipeline…', percent: 95 })
    const tts = (await KokoroTTS.from_pretrained(MODEL_ID, {
      dtype: 'q8', // Quantized untuk ukuran kecil (~80MB) dan loading cepat
      device: 'wasm', // WebGPU belum stabil di semua browser
      progress_callback,
    })) as unknown as KokoroTTSInstance

    _modelReady = true
    onProgress?.({ stage: 'idle', message: 'Model ready', percent: 100 })
    return tts
  })()

  return _ttsInstance
}

export function isKokoroModelReady(): boolean {
  return _modelReady
}

export interface NarrationOptions {
  voice: string
  respectTiming: boolean
  onLineProgress?: (current: number, total: number, text: string) => void
  onStage?: ProgressCallback
}

export interface NarrationResult {
  blob: Blob
  sampleRate: number
  durationSec: number
  previewUrl: string
}

/**
 * Synthesize single text to Float32Array PCM.
 */
export async function synthesizeText(
  text: string,
  voice: string = DEFAULT_KOKORO_VOICE,
  speed: number = 1.0,
): Promise<{ audio: Float32Array; sampleRate: number }> {
  if (!text.trim()) {
    return { audio: new Float32Array(0), sampleRate: OUTPUT_SAMPLE_RATE }
  }
  const tts = await ensureKokoroModel()
  const result = await tts.generate(text, { voice, speed })
  return { audio: result.audio, sampleRate: result.sampling_rate }
}

/**
 * Generate narration audio for SRT entries, stitched into one WAV.
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
        segments.push(new Float32Array(Math.floor((entry.end - entry.start) * OUTPUT_SAMPLE_RATE)))
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
      const { audio } = await synthesizeText(text, opts.voice)
      if (audio.length === 0) throw new Error('Empty audio output')

      let adjusted: Float32Array
      if (opts.respectTiming) {
        const cueDuration = entry.end - entry.start
        const prevEnd = i > 0 ? entries[i - 1].end : 0
        silenceBefore.push(Math.floor(Math.max(0, entry.start - prevEnd) * OUTPUT_SAMPLE_RATE))
        // adjustDuration expects AudioBuffer, but we have raw Float32Array
        // Simple: if audio longer than cue, truncate; if shorter, pad silence
        const targetSamples = Math.floor(cueDuration * OUTPUT_SAMPLE_RATE)
        if (audio.length > targetSamples) {
          adjusted = audio.slice(0, targetSamples)
        } else if (audio.length < targetSamples) {
          adjusted = new Float32Array(targetSamples)
          adjusted.set(audio, 0)
        } else {
          adjusted = audio
        }
      } else {
        silenceBefore.push(Math.floor(0.3 * OUTPUT_SAMPLE_RATE))
        adjusted = audio
      }

      segments.push(adjusted)
      successCount++
    } catch (e) {
      failCount++
      if (!firstError) firstError = (e as Error).message
      console.error('Kokoro TTS failed for line', i, e)
      if (opts.respectTiming) {
        segments.push(new Float32Array(Math.floor((entry.end - entry.start) * OUTPUT_SAMPLE_RATE)))
      } else {
        segments.push(new Float32Array(0))
      }
      silenceBefore.push(0)
    }
  }

  if (successCount === 0) {
    throw new Error(
      `Kokoro TTS gagal untuk semua ${total} baris. Error: ${firstError || 'unknown'}. ` +
      `Pastikan model sudah di-download dan COI serviceworker aktif.`,
    )
  }

  if (failCount > 0) {
    console.warn(`Kokoro: ${successCount}/${total} berhasil, ${failCount} gagal.`)
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
      return { blob, sampleRate: OUTPUT_SAMPLE_RATE, durationSec: targetEnd, previewUrl: URL.createObjectURL(blob) }
    }
  }

  const blob = encodeWav(allAudio, OUTPUT_SAMPLE_RATE)
  const durationSec = allAudio.length / OUTPUT_SAMPLE_RATE
  opts.onStage?.({ stage: 'done', message: 'Narration selesai', percent: 100 })
  return { blob, sampleRate: OUTPUT_SAMPLE_RATE, durationSec, previewUrl: URL.createObjectURL(blob) }
}

export async function narratePart(part: SrtPart, opts: NarrationOptions): Promise<NarrationResult> {
  return narrateEntries(part.entries, opts)
}

export function downloadBlob(filename: string, blob: Blob) {
  downloadBlobUtil(filename, blob)
}

export function revokePreviewUrl(url: string) {
  try { URL.revokeObjectURL(url) } catch {}
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

// Suppress unused warning
export const _decodeAudioBlob = decodeAudioBlob
export const _adjustDuration = adjustDuration
