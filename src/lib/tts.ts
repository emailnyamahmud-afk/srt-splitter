// TTS engine dengan multiple provider support + audio timing sync.
//
// Provider:
//   1. Edge TTS (default, gratis, native Indonesia: Gadis/Ardi)
//   2. OpenAI TTS (premium, API key, Indonesia natural)
//   3. OpenRouter TTS (gateway ke banyak model: OpenAI, ElevenLabs, MiniMax, dll)
//
// All TTS happens client-side. Edge TTS pakai WebSocket, OpenAI/OpenRouter pakai REST.
// Audio timing di-sync ke SRT: speed up if too long, pad silence if too short.

'use client'

import type { SrtEntry, SrtPart } from './srt'
import { edgeTTS, EDGE_VOICES, DEFAULT_EDGE_VOICE, type EdgeVoice, getEdgeProxyUrl, setEdgeProxyUrl } from './edge-tts'
import {
  openaiTTS,
  OPENAI_VOICES,
  DEFAULT_OPENAI_VOICE,
  getApiKey as getOpenAIKey,
  setApiKey as setOpenAIKey,
  testApiKey as testOpenAIKey,
  type OpenAIVoice,
} from './openai-tts'
import {
  openRouterTTS,
  OPENROUTER_MODELS,
  DEFAULT_OPENROUTER_MODEL,
  getApiKey as getOpenRouterKey,
  setApiKey as setOpenRouterKey,
  testApiKey as testOpenRouterKey,
  type OpenRouterModel,
} from './openrouter-tts'
import {
  ensureKokoroModel,
  synthesizeText as kokoroSynth,
  DEFAULT_KOKORO_VOICE,
  KOKORO_VOICES,
  type KokoroVoice,
} from './kokoro-tts'
import {
  decodeAudioBlob,
  concatenateWithSilence,
  encodeWav,
  downloadBlob as downloadBlobUtil,
} from './audio-utils'
import { adjustAudioDuration } from './time-stretch'

// Re-export semua yang dibutuhkan UI
export { EDGE_VOICES, DEFAULT_EDGE_VOICE, type EdgeVoice, getEdgeProxyUrl, setEdgeProxyUrl }
export { OPENAI_VOICES, DEFAULT_OPENAI_VOICE, type OpenAIVoice }
export { OPENROUTER_MODELS, DEFAULT_OPENROUTER_MODEL, type OpenRouterModel }
export { KOKORO_VOICES, DEFAULT_KOKORO_VOICE, type KokoroVoice }
export { OPENAI_VOICES as OPENAI_VOICE_OPTIONS }
export {
  getOpenAIKey,
  setOpenAIKey,
  testOpenAIKey,
  getOpenRouterKey,
  setOpenRouterKey,
  testOpenRouterKey,
}

export type Provider = 'edge' | 'kokoro' | 'openai' | 'openrouter'

const OUTPUT_SAMPLE_RATE = 24000

export interface TTSProgress {
  stage: 'idle' | 'synthesizing' | 'stitching' | 'done' | 'error'
  message?: string
  percent?: number
}

export type ProgressCallback = (p: TTSProgress) => void

export interface NarrationOptions {
  provider: Provider
  voice: string
  model?: string // untuk OpenRouter
  apiKey?: string // untuk OpenAI/OpenRouter (Edge dan Kokoro tidak butuh)
  speed?: number // untuk Kokoro (default 1.0)
  respectTiming: boolean
  onModelProgress?: (p: TTSProgress) => void // untuk Kokoro download model progress
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
 * Synthesize text menggunakan provider yang dipilih.
 *
 * Note: Untuk Kokoro, kita return WAV (PCM Float32) bukan MP3 karena Kokoro
 * native output adalah PCM. NarrateEntries akan handle konversi ke WAV.
 */
export async function synthesizeText(
  text: string,
  opts: {
    provider: Provider
    voice: string
    model?: string
    apiKey?: string
    speed?: number
    onModelProgress?: (p: TTSProgress) => void
  },
): Promise<{ audioBlob: Blob; mimeType: string; pcm?: Float32Array; sampleRate?: number }> {
  if (!text.trim()) {
    return { audioBlob: new Blob([]), mimeType: 'audio/mp3' }
  }

  switch (opts.provider) {
    case 'edge':
      return { audioBlob: await edgeTTS(text, opts.voice), mimeType: 'audio/mp3' }
    case 'kokoro': {
      // Use static import (already at top of file)
      await ensureKokoroModel(opts.onModelProgress)
      const result = await kokoroSynth(text, opts.voice || DEFAULT_KOKORO_VOICE, opts.speed || 1.0)
      // Return empty Blob (not used) + raw PCM
      return { audioBlob: new Blob([]), mimeType: 'audio/wav', pcm: result.audio, sampleRate: result.sampleRate }
    }
    case 'openai':
      if (!opts.apiKey) throw new Error('OpenAI API key belum diisi')
      return {
        audioBlob: await openaiTTS(text, opts.voice, opts.apiKey!),
        mimeType: 'audio/mp3',
      }
    case 'openrouter':
      if (!opts.apiKey) throw new Error('OpenRouter API key belum diisi')
      return {
        audioBlob: await openRouterTTS(text, opts.model || 'openai/tts-1-hd', opts.voice, opts.apiKey!),
        mimeType: 'audio/mp3',
      }
    default:
      throw new Error(`Unknown provider: ${opts.provider}`)
  }
}

/**
 * Generate narration audio for SRT entries, stitched into one WAV.
 *
 * STRATEGY (audio fit ke cue, pitch natural, durasi = SRT):
 * - Setiap audio TTS di-time-stretch untuk FIT ke cue duration (entry.end - entry.start)
 * - Time-stretch pakai SoundTouchJS — ubah durasi TANPA ubah pitch
 *   Audio 8 detik → fit ke cue 5 detik → audio 5 detik (pitch tetap natural)
 * - Audio diposisikan di entry.start (SRT timing WAJIB)
 * - Total durasi = SRT end time (terpaksa, tidak ada push-back)
 *
 * Aturan:
 * - Waktu SRT WAJIB (audio = SRT duration)
 * - Suara natural (pitch tidak berubah, no chipmunk)
 * - Audio utuh (SoundTouchJS time-stretch, tidak truncate di kasus normal)
 *
 * Output: WAV 24kHz mono 16-bit PCM, durasi = SRT asli.
 */
export async function narrateEntries(
  entries: SrtEntry[],
  opts: NarrationOptions,
): Promise<NarrationResult> {
  if (entries.length === 0) throw new Error('No subtitles to narrate')

  opts.onStage?.({ stage: 'synthesizing', message: 'Mulai synthesizing…', percent: 0 })
  const total = entries.length
  // Position-based: tiap segment di-posisikan di entry.start, audio di-time-stretch ke cue duration
  const placedSegments: { position: number; audio: Float32Array }[] = []
  let successCount = 0
  let failCount = 0
  let firstError = ''

  for (let i = 0; i < entries.length; i++) {
    const entry = entries[i]
    const text = entry.textLines.join(' ').trim()

    if (!text) {
      // Empty cue: no audio, position advance to entry.end
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
      const synth = await synthesizeText(text, opts)

      let rawAudio: Float32Array
      let audioSampleRate: number

      if (synth.pcm) {
        // Kokoro: langsung pakai PCM
        if (synth.pcm.length === 0) throw new Error('Empty audio output')
        rawAudio = synth.pcm
        audioSampleRate = synth.sampleRate || OUTPUT_SAMPLE_RATE
      } else {
        // Edge/OpenAI/OpenRouter: decode MP3
        if (synth.audioBlob.size === 0) throw new Error('Empty audio output')
        const audioBuffer = await decodeAudioBlob(synth.audioBlob, OUTPUT_SAMPLE_RATE)
        audioSampleRate = audioBuffer.sampleRate
        rawAudio = new Float32Array(audioBuffer.length)
        audioBuffer.copyFromChannel(rawAudio, 0)
      }

      // Resample ke OUTPUT_SAMPLE_RATE jika perlu
      if (audioSampleRate !== OUTPUT_SAMPLE_RATE) {
        rawAudio = linearResample(rawAudio, audioSampleRate, OUTPUT_SAMPLE_RATE)
        audioSampleRate = OUTPUT_SAMPLE_RATE
      }

      let finalAudio: Float32Array

      if (opts.respectTiming) {
        // SYNC KE SRT: time-stretch audio ke cue duration (entry.end - entry.start)
        const cueDuration = entry.end - entry.start
        finalAudio = adjustAudioDuration(rawAudio, audioSampleRate, cueDuration, { maxSpeedUp: 2.5 })
      } else {
        // No sync: audio natural utuh dengan 300ms gap
        finalAudio = rawAudio
      }

      // Position di entry.start (SRT timing WAJIB)
      const position = Math.floor(entry.start * OUTPUT_SAMPLE_RATE)
      placedSegments.push({ position, audio: finalAudio })

      successCount++
    } catch (e) {
      failCount++
      if (!firstError) firstError = (e as Error).message
      console.error('TTS failed for line', i, e)
      // Skip — tidak ada audio untuk cue ini
    }
  }

  if (successCount === 0) {
    throw new Error(
      `TTS gagal untuk semua ${total} baris. Error: ${firstError || 'unknown'}. ` +
      (opts.provider === 'edge'
        ? 'Coba ganti ke provider OpenAI atau OpenRouter.'
        : 'Cek API key atau koneksi internet.'),
    )
  }

  if (failCount > 0) {
    console.warn(`TTS: ${successCount}/${total} berhasil, ${failCount} gagal.`)
  }

  opts.onStage?.({ stage: 'stitching', message: 'Menjahit audio…', percent: 90 })

  // Total durasi = SRT end time (WAJIB, tidak boleh lebih)
  const srtEnd = entries[entries.length - 1].end
  const totalSamples = Math.floor(srtEnd * OUTPUT_SAMPLE_RATE)

  // Build output Float32Array dengan audio di posisi absolut
  const allAudio = new Float32Array(totalSamples)
  for (const seg of placedSegments) {
    // Copy audio ke posisi (truncate kalau melebihi totalSamples)
    const endPos = Math.min(seg.position + seg.audio.length, totalSamples)
    const copyLength = endPos - seg.position
    if (copyLength > 0) {
      allAudio.set(seg.audio.subarray(0, copyLength), seg.position)
    }
  }

  const blob = encodeWav(allAudio, OUTPUT_SAMPLE_RATE)
  const durationSec = allAudio.length / OUTPUT_SAMPLE_RATE
  opts.onStage?.({ stage: 'done', message: 'Narration selesai', percent: 100 })
  return { blob, sampleRate: OUTPUT_SAMPLE_RATE, durationSec, previewUrl: URL.createObjectURL(blob) }
}

/**
 * Linear resample Float32Array dari sample rate asal ke target.
 */
function linearResample(audio: Float32Array, fromRate: number, toRate: number): Float32Array {
  if (fromRate === toRate) return audio
  const ratio = toRate / fromRate
  const targetLength = Math.floor(audio.length * ratio)
  const result = new Float32Array(targetLength)
  for (let i = 0; i < targetLength; i++) {
    const srcIdx = i / ratio
    const idx0 = Math.floor(srcIdx)
    const idx1 = Math.min(idx0 + 1, audio.length - 1)
    const frac = srcIdx - idx0
    result[i] = audio[idx0] * (1 - frac) + audio[idx1] * frac
  }
  return result
}

export async function narratePart(part: SrtPart, opts: NarrationOptions): Promise<NarrationResult> {
  return narrateEntries(part.entries, opts)
}

export function downloadBlob(filename: string, blob: Blob) {
  downloadBlobUtil(filename, blob)
}

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
