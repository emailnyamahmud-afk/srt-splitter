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
  encodeWav,
  downloadBlob as downloadBlobUtil,
} from './audio-utils'

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
 * Parameter `rate` (0.5-2.0):
 * - 1.0 = normal speed
 * - 2.0 = 2x faster (audio lebih cepat, pitch tetap natural — server-side)
 * - 0.5 = 0.5x slower (audio lebih lambat, pitch tetap natural)
 *
 * Server-side rate change = pitch preservation 100% reliable di semua browser.
 * Tidak perlu client-side time-stretch (yang bug di Brave dll).
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
    speed?: number // untuk Kokoro (default 1.0)
    rate?: string // untuk Edge TTS (e.g. '+50%', '-10%')
    openaiSpeed?: number // untuk OpenAI/OpenRouter (0.25-4.0, default 1.0)
    onModelProgress?: (p: TTSProgress) => void
  },
): Promise<{ audioBlob: Blob; mimeType: string; pcm?: Float32Array; sampleRate?: number }> {
  if (!text.trim()) {
    return { audioBlob: new Blob([]), mimeType: 'audio/mp3' }
  }

  switch (opts.provider) {
    case 'edge': {
      // Edge TTS rate via SSML prosody rate parameter (server-side pitch preservation)
      const ratePercent = opts.rate || '+0%'
      return { audioBlob: await edgeTTS(text, opts.voice, { rate: ratePercent }), mimeType: 'audio/mp3' }
    }
    case 'kokoro': {
      // Kokoro speed parameter (server-side)
      await ensureKokoroModel(opts.onModelProgress)
      const speed = opts.speed || 1.0
      const result = await kokoroSynth(text, opts.voice || DEFAULT_KOKORO_VOICE, speed)
      return { audioBlob: new Blob([]), mimeType: 'audio/wav', pcm: result.audio, sampleRate: result.sampleRate }
    }
    case 'openai': {
      if (!opts.apiKey) throw new Error('OpenAI API key belum diisi')
      // OpenAI TTS speed parameter (0.25-4.0, server-side pitch preservation)
      const speed = opts.openaiSpeed || 1.0
      return {
        audioBlob: await openaiTTS(text, opts.voice, opts.apiKey!, 'tts-1-hd', speed),
        mimeType: 'audio/mp3',
      }
    }
    case 'openrouter': {
      if (!opts.apiKey) throw new Error('OpenRouter API key belum diisi')
      const speed = opts.openaiSpeed || 1.0
      return {
        audioBlob: await openRouterTTS(text, opts.model || 'openai/tts-1-hd', opts.voice, opts.apiKey!, speed),
        mimeType: 'audio/mp3',
      }
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
/**
 * Estimate rate untuk fit text ke cue duration.
 *
 * Heuristic: TTS natural speech rate ~13 chars/sec untuk Indonesia/English.
 * - kalau text 100 chars → natural duration ~7.7s
 * - kalau cue 5s → rate = 7.7/5 = 1.54x (faster)
 * - Edge TTS: rate percent = +54%
 * - OpenAI/Kokoro: speed = 1.54
 *
 * Clamp rate ke 0.7-2.5 (terlalu cepat/lambat tidak natural).
 */
function estimateRate(text: string, cueDurationSec: number, opts: NarrationOptions): {
  edgeRate: string
  openaiSpeed: number
  kokoroSpeed: number
} {
  const charsPerSec = 13 // rata-rata TTS Indonesia/English
  const naturalDuration = Math.max(text.length / charsPerSec, 0.5)
  const ratio = naturalDuration / cueDurationSec

  // Clamp 0.7-2.5 (jangan terlalu ekstrem)
  const clamped = Math.min(Math.max(ratio, 0.7), 2.5)

  // Edge TTS rate sebagai percent string
  // ratio 1.0 = +0%, ratio 1.5 = +50%, ratio 0.8 = -20%
  const edgePercent = Math.round((clamped - 1) * 100)
  const edgeRate = (edgePercent >= 0 ? '+' : '') + edgePercent + '%'

  return {
    edgeRate,
    openaiSpeed: clamped, // OpenAI TTS speed (0.25-4.0, 1.0 = normal)
    kokoroSpeed: clamped, // Kokoro speed (1.0 = normal)
  }
}

/**
 * Generate narration audio for SRT entries, stitched into one WAV.
 *
 * STRATEGY (server-side rate, durasi = SRT, pitch natural):
 * - Estimate rate dari text length vs cue duration (charsPerSec heuristic)
 * - Request TTS dengan rate parameter (server-side pitch preservation)
 *   - Edge TTS: SSML prosody rate '+XX%'
 *   - OpenAI TTS: speed parameter (0.25-4.0)
 *   - Kokoro: speed parameter
 * - Audio datang dengan durasi ~cue duration, pitch natural (server handle)
 * - Position di entry.start (SRT timing WAJIB)
 * - Total durasi = SRT end time
 * - Kalau audio masih beda sedikit: pad silence / truncate (pitch sudah natural)
 *
 * Aturan:
 * - Waktu SRT WAJIB (durasi audio = SRT duration)
 * - Suara natural (server-side pitch preservation, no chipmunk)
 * - Audio utuh (server-side rate, tidak truncate di kasus normal)
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
  // Position-based: tiap segment di-posisikan di entry.start, audio di-rate-fit ke cue duration
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
      // Hitung rate untuk fit audio ke cue duration (server-side pitch preservation)
      let synthOpts = opts
      if (opts.respectTiming) {
        const cueDuration = entry.end - entry.start
        const rate = estimateRate(text, cueDuration, opts)
        synthOpts = {
          ...opts,
          rate: rate.edgeRate,
          openaiSpeed: rate.openaiSpeed,
          speed: rate.kokoroSpeed,
        }
      }

      const synth = await synthesizeText(text, synthOpts)

      let rawAudio: Float32Array
      let audioSampleRate: number

      if (synth.pcm) {
        if (synth.pcm.length === 0) throw new Error('Empty audio output')
        rawAudio = synth.pcm
        audioSampleRate = synth.sampleRate || OUTPUT_SAMPLE_RATE
      } else {
        if (synth.audioBlob.size === 0) throw new Error('Empty audio output')
        const audioBuffer = await decodeAudioBlob(synth.audioBlob, OUTPUT_SAMPLE_RATE)
        audioSampleRate = audioBuffer.sampleRate
        rawAudio = new Float32Array(audioBuffer.length)
        audioBuffer.copyFromChannel(rawAudio, 0)
      }

      // Resample ke OUTPUT_SAMPLE_RATE jika perlu
      if (audioSampleRate !== OUTPUT_SAMPLE_RATE) {
        rawAudio = linearResample(rawAudio, audioSampleRate, OUTPUT_SAMPLE_RATE)
      }

      let finalAudio: Float32Array
      if (opts.respectTiming) {
        // Sync ke SRT: pad/truncate audio ke cue duration (pitch sudah natural via server rate)
        const cueDuration = entry.end - entry.start
        const targetSamples = Math.floor(cueDuration * OUTPUT_SAMPLE_RATE)
        if (rawAudio.length > targetSamples) {
          // Audio masih sedikit lebih panjang (estimasi tidak perfect) → truncate
          finalAudio = rawAudio.subarray(0, targetSamples)
        } else if (rawAudio.length < targetSamples) {
          // Audio lebih pendek → pad silence
          finalAudio = new Float32Array(targetSamples)
          finalAudio.set(rawAudio, 0)
        } else {
          finalAudio = rawAudio
        }
      } else {
        // No sync: audio natural utuh
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
