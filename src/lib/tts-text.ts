// TTS Text-to-Audio — generate audio dari text panjang (bukan SRT).
//
// Support hingga 100,000 karakter. Split text jadi chunks (max 4500 char),
// generate TTS per chunk via Edge TTS, decode + concat + crossfade antar chunk.
//
// Cocok untuk: naskah pidato Jawa, panyandra, sambutan, narasi konten, dll.

'use client'

import { edgeTTS, EDGE_VOICES, DEFAULT_EDGE_VOICE } from './edge-tts'
import { decodeAudioBlob, toMono, encodeWav, downloadBlob as downloadBlobUtil, mixAudioInto, applyFadeOut, applyFadeIn } from './audio-utils'

const OUTPUT_SAMPLE_RATE = 24000
const MAX_CHARS_PER_CHUNK = 4500
const CROSSFADE_SAMPLES = Math.floor(0.1 * OUTPUT_SAMPLE_RATE) // 100ms crossfade

export interface TTSProgress {
  stage: 'idle' | 'chunking' | 'synthesizing' | 'stitching' | 'done' | 'error'
  message?: string
  percent?: number
  currentChunk?: number
  totalChunks?: number
}

export type ProgressCallback = (p: TTSProgress) => void

export interface TextToAudioOptions {
  text: string
  voice: string
  speed: number // 1.0 = natural, 1.25, 1.5, 2.0
}

export interface TextToAudioResult {
  blob: Blob
  sampleRate: number
  durationSec: number
  previewUrl: string
}

/**
 * Estimasi durasi audio dari text.
 * Indonesia/Jawa: ~12 chars per detik (rate natural).
 */
export function estimateDuration(text: string): number {
  return Math.max(text.length / 12, 1)
}

/**
 * Split text jadi chunks. Max 4500 char per chunk.
 * Split di akhir kalimat (titik, !, ?, newline) — jangan potong mid-sentence.
 */
export function splitTextIntoChunks(text: string): string[] {
  if (text.length <= MAX_CHARS_PER_CHUNK) {
    return [text]
  }

  const chunks: string[] = []
  let current = ''

  // Split by sentence enders: . ! ? 。 ！ ？ newline
  const sentences = text.split(/(?<=[.!?。！？\n])\s*/)

  for (const sentence of sentences) {
    // Kalau satu kalimat lebih panjang dari max, split paksa per kata
    if (sentence.length > MAX_CHARS_PER_CHUNK) {
      if (current) {
        chunks.push(current.trim())
        current = ''
      }
      const words = sentence.split(/\s+/)
      for (const word of words) {
        if (current.length + word.length + 1 > MAX_CHARS_PER_CHUNK) {
          if (current) chunks.push(current.trim())
          current = word
        } else {
          current += (current ? ' ' : '') + word
        }
      }
      continue
    }

    if (current.length + sentence.length + 1 > MAX_CHARS_PER_CHUNK) {
      if (current) chunks.push(current.trim())
      current = sentence
    } else {
      current += (current ? ' ' : '') + sentence
    }
  }

  if (current.trim()) chunks.push(current.trim())
  return chunks
}

/**
 * Format speed number ke Edge TTS rate percent string.
 * 1.0 = +0%, 1.5 = +50%, 2.0 = +100%
 */
function formatRate(speed: number): string {
  const percent = Math.round((speed - 1) * 100)
  return (percent >= 0 ? '+' : '') + percent + '%'
}

/**
 * Generate audio dari text panjang.
 * Split → generate per chunk → decode → concat → crossfade → WAV.
 */
export async function textToAudio(
  opts: TextToAudioOptions,
  onProgress?: ProgressCallback,
): Promise<TextToAudioResult> {
  const text = opts.text.trim()
  if (!text) throw new Error('Text kosong')

  // Step 1: Chunking
  onProgress?.({ stage: 'chunking', message: 'Membagi text jadi chunks…' })
  const chunks = splitTextIntoChunks(text)
  const totalChunks = chunks.length

  onProgress?.({
    stage: 'chunking',
    message: `${totalChunks} chunk${totalChunks > 1 ? 's' : ''}, max ${MAX_CHARS_PER_CHUNK} char per chunk`,
    percent: 0,
    totalChunks,
  })

  // Step 2: Generate TTS per chunk
  const rate = formatRate(opts.speed)
  const segments: Float32Array[] = []

  for (let i = 0; i < chunks.length; i++) {
    const chunk = chunks[i]
    onProgress?.({
      stage: 'synthesizing',
      message: `Chunk ${i + 1}/${totalChunks}: "${chunk.slice(0, 50)}${chunk.length > 50 ? '…' : ''}"`,
      percent: (i / totalChunks) * 80,
      currentChunk: i + 1,
      totalChunks,
    })

    try {
      const blob = await edgeTTS(chunk, opts.voice, { rate })
      if (blob.size === 0) throw new Error('Empty audio output')

      const audioBuffer = await decodeAudioBlob(blob, OUTPUT_SAMPLE_RATE)
      const mono = toMono(audioBuffer)

      if (audioBuffer.sampleRate !== OUTPUT_SAMPLE_RATE) {
        // Resample if needed
        const ratio = OUTPUT_SAMPLE_RATE / audioBuffer.sampleRate
        const resampled = new Float32Array(Math.floor(mono.length * ratio))
        for (let j = 0; j < resampled.length; j++) {
          const srcIdx = j / ratio
          const idx0 = Math.floor(srcIdx)
          const idx1 = Math.min(idx0 + 1, mono.length - 1)
          const frac = srcIdx - idx0
          resampled[j] = mono[idx0] * (1 - frac) + mono[idx1] * frac
        }
        segments.push(resampled)
      } else {
        segments.push(mono)
      }
    } catch (e) {
      console.error(`TTS failed for chunk ${i + 1}:`, e)
      // Skip failed chunk, continue
    }
  }

  if (segments.length === 0) {
    throw new Error('Semua chunk gagal. Cek koneksi internet.')
  }

  // Step 3: Concatenate with crossfade
  onProgress?.({ stage: 'stitching', message: 'Menjahit + crossfade…', percent: 85 })

  // Calculate total length (with crossfade overlap)
  let totalLength = 0
  for (let i = 0; i < segments.length; i++) {
    totalLength += segments[i].length
    if (i > 0 && CROSSFADE_SAMPLES > 0) {
      totalLength -= CROSSFADE_SAMPLES // overlap region
    }
  }

  const allAudio = new Float32Array(totalLength)
  let position = 0

  for (let i = 0; i < segments.length; i++) {
    const seg = segments[i]

    if (i > 0 && CROSSFADE_SAMPLES > 0 && position > 0) {
      // Crossfade: fade out end of previous, fade in start of current
      // Previous segment tail is already in buffer, just add current with fade in
      const fadeLen = Math.min(CROSSFADE_SAMPLES, seg.length, position)
      applyFadeIn(seg, 0, fadeLen)
    }

    if (i < segments.length - 1 && CROSSFADE_SAMPLES > 0) {
      // Fade out tail of this segment (will overlap with next)
      const fadeStart = Math.max(0, seg.length - CROSSFADE_SAMPLES)
      applyFadeOut(seg, fadeStart, seg.length)
    }

    mixAudioInto(allAudio, seg, position)
    position += seg.length
    if (i < segments.length - 1 && CROSSFADE_SAMPLES > 0) {
      position -= CROSSFADE_SAMPLES // move back for overlap
    }
  }

  // Step 4: Encode WAV
  onProgress?.({ stage: 'done', message: 'Audio siap', percent: 100 })
  const blob = encodeWav(allAudio, OUTPUT_SAMPLE_RATE)
  const durationSec = allAudio.length / OUTPUT_SAMPLE_RATE

  return {
    blob,
    sampleRate: OUTPUT_SAMPLE_RATE,
    durationSec,
    previewUrl: URL.createObjectURL(blob),
  }
}

export function downloadBlob(filename: string, blob: Blob) {
  downloadBlobUtil(filename, blob)
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
  const units = ['B', 'KB', 'MB', 'GB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return `${(bytes / Math.pow(k, i)).toFixed(1)} ${units[i]}`
}
