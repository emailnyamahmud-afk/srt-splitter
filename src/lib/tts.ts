// TTS engine dengan multiple provider support + audio timing sync.
//
// DUA MODE:
//   ON (respectTiming=true): audio fit ke cue duration (durasi = SRT)
//     - Server-side rate (Edge TTS prosody rate / OpenAI speed / Kokoro speed)
//     - Pitch natural di server — 100% reliable di semua browser
//     - Position = entry.start (SRT timing WAJIB)
//     - Total durasi = SRT end time
//   OFF (respectTiming=false): audio natural alami (TANPA POTONGAN)
//     - Generate TTS natural (no rate change)
//     - Sequential playback (position = cursor, satu demi satu)
//     - Audio utuh 100% (no truncate, no pad)
//     - Total durasi = sum semua audio (boleh lebih panjang/pendek dari SRT)

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
  toMono,
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
  apiKey?: string
  speed?: number // untuk Kokoro (default 1.0, hanya dipakai kalau respectTiming=false)
  respectTiming: boolean
  speedMode?: 'speedup-only' | 'speedup-slowdown' // ON mode: speed up only, atau speed up + slow down
  onModelProgress?: (p: TTSProgress) => void
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
 * Synthesize text. Edge TTS: natural rate (rate='+0%').
 * Speed up/slow down di-handle client-side dengan OfflineAudioContext + preservePitch.
 */
export async function synthesizeText(
  text: string,
  opts: {
    provider: Provider
    voice: string
    model?: string
    apiKey?: string
    speed?: number           // Kokoro speed (default 1.0)
    rate?: string             // Edge TTS prosody rate (default '+0%' = natural)
    openaiSpeed?: number      // OpenAI/OpenRouter speed (0.25-4.0)
    onModelProgress?: (p: TTSProgress) => void
  },
): Promise<{ audioBlob: Blob; mimeType: string; pcm?: Float32Array; sampleRate?: number }> {
  if (!text.trim()) {
    return { audioBlob: new Blob([]), mimeType: 'audio/mp3' }
  }

  switch (opts.provider) {
    case 'edge':
      // Edge TTS: natural rate, speed up di-handle client-side
      return {
        audioBlob: await edgeTTS(text, opts.voice, { rate: opts.rate || '+0%' }),
        mimeType: 'audio/mp3',
      }
    case 'kokoro': {
      await ensureKokoroModel(opts.onModelProgress)
      const speed = opts.speed || 1.0
      const result = await kokoroSynth(text, opts.voice || DEFAULT_KOKORO_VOICE, speed)
      return { audioBlob: new Blob([]), mimeType: 'audio/wav', pcm: result.audio, sampleRate: result.sampleRate }
    }
    case 'openai':
      if (!opts.apiKey) throw new Error('OpenAI API key belum diisi')
      return {
        audioBlob: await openaiTTS(text, opts.voice, opts.apiKey!, 'tts-1-hd', opts.openaiSpeed || 1.0),
        mimeType: 'audio/mp3',
      }
    case 'openrouter':
      if (!opts.apiKey) throw new Error('OpenRouter API key belum diisi')
      return {
        audioBlob: await openRouterTTS(text, opts.model || 'openai/tts-1-hd', opts.voice, opts.apiKey!, opts.openaiSpeed || 1.0),
        mimeType: 'audio/mp3',
      }
    default:
      throw new Error(`Unknown provider: ${opts.provider}`)
  }
}

/**
 * Speed up atau slow down audio di client dengan OfflineAudioContext + preservePitch.
 * TANPA detune (detune membatalkan speed up — bug sebelumnya).
 *
 * @param audioBuffer Source audio
 * @param ratio > 1.0 = speed up (lebih cepat), < 1.0 = slow down (lebih lambat)
 * @param sampleRate Output sample rate
 */
async function timeStretchClient(
  audioBuffer: AudioBuffer,
  ratio: number,
  sampleRate: number,
): Promise<Float32Array> {
  const targetLength = Math.floor(audioBuffer.length / ratio)
  const offlineCtx = new OfflineAudioContext(1, targetLength, sampleRate)
  const source = offlineCtx.createBufferSource()
  source.buffer = audioBuffer
  source.playbackRate.value = ratio
  // Set SEMUA preservePitch variants — browser pakai yang dia kenal
  const anySource = source as unknown as {
    preservePitch?: boolean
    webkitPreservePitch?: boolean
    preservesPitch?: boolean
  }
  try { anySource.preservePitch = true } catch { /* ignore */ }
  try { anySource.webkitPreservePitch = true } catch { /* ignore */ }
  try { anySource.preservesPitch = true } catch { /* ignore */ }
  // TIDAK pakai detune — detune membatalkan speed up!
  source.connect(offlineCtx.destination)
  source.start()
  const rendered = await offlineCtx.startRendering()
  return toMono(rendered)
}

/**
 * Generate narration audio for SRT entries, stitched into one WAV.
 *
 * DUA MODE:
 *
 * ON (respectTiming=true): audio fit ke cue duration (durasi = SRT)
 * - Generate Edge TTS natural (rate='+0%', pitch natural dari server)
 * - Decode audio, ukur actual duration
 * - Kalau audio != cue duration: speed up/slow down di client dengan
 *   OfflineAudioContext + preservePitch (semua 3 varian, TANPA detune)
 *   Pitch natural, audio fit ke cue, no chipmunk
 * - Position = entry.start (SRT timing WAJIB)
 * - Total durasi = SRT end time
 *
 * OFF (respectTiming=false): audio natural alami (TANPA POTONGAN)
 * - Generate TTS natural (no rate change)
 * - Sequential playback (position = cursor, satu demi satu)
 * - Audio utuh 100% (no truncate, no pad)
 * - Total durasi = sum semua audio
 *
 * Output: WAV 24kHz mono 16-bit PCM.
 */
export async function narrateEntries(
  entries: SrtEntry[],
  opts: NarrationOptions,
): Promise<NarrationResult> {
  if (entries.length === 0) throw new Error('No subtitles to narrate')

  opts.onStage?.({ stage: 'synthesizing', message: 'Mulai synthesizing…', percent: 0 })
  const total = entries.length
  const placedSegments: { position: number; audio: Float32Array }[] = []
  let cursor = 0
  let successCount = 0
  let failCount = 0
  let firstError = ''

  for (let i = 0; i < entries.length; i++) {
    const entry = entries[i]
    const text = entry.textLines.join(' ').trim()

    if (!text) {
      if (opts.respectTiming) {
        cursor = Math.max(cursor, Math.floor(entry.end * OUTPUT_SAMPLE_RATE))
      } else {
        cursor += Math.floor(0.3 * OUTPUT_SAMPLE_RATE)
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
      // Generate TTS natural (no rate change — rate='+0%' default)
      const synth = await synthesizeText(text, opts)

      let audioBuffer: AudioBuffer

      if (synth.pcm) {
        // Kokoro: buat AudioBuffer dari PCM
        if (synth.pcm.length === 0) throw new Error('Empty audio output')
        const pcmSampleRate = synth.sampleRate || OUTPUT_SAMPLE_RATE
        const ctx = new AudioContext({ sampleRate: pcmSampleRate })
        audioBuffer = ctx.createBuffer(1, synth.pcm.length, pcmSampleRate)
        audioBuffer.copyToChannel(synth.pcm, 0)
        ctx.close()
      } else {
        // Edge/OpenAI/OpenRouter: decode MP3 ke AudioBuffer
        if (synth.audioBlob.size === 0) throw new Error('Empty audio output')
        audioBuffer = await decodeAudioBlob(synth.audioBlob, OUTPUT_SAMPLE_RATE)
      }

      let finalAudio: Float32Array
      let position: number

      if (opts.respectTiming) {
        // === ON MODE: speed up/slow down di client, sync ke SRT ===
        const cueDuration = entry.end - entry.start
        const actualDuration = audioBuffer.duration

        if (Math.abs(actualDuration - cueDuration) < 0.05) {
          // Sudah dekat cue duration — pakai asli
          finalAudio = toMono(audioBuffer)
          // Resample ke OUTPUT_SAMPLE_RATE kalau perlu
          if (audioBuffer.sampleRate !== OUTPUT_SAMPLE_RATE) {
            finalAudio = linearResample(finalAudio, audioBuffer.sampleRate, OUTPUT_SAMPLE_RATE)
          }
        } else if (actualDuration > cueDuration) {
          // Audio lebih panjang → SPEED UP (ratio > 1.0)
          const ratio = actualDuration / cueDuration
          finalAudio = await timeStretchClient(audioBuffer, ratio, OUTPUT_SAMPLE_RATE)
        } else {
          // Audio lebih pendek dari cue
          if (opts.speedMode === 'speedup-slowdown') {
            // Slow down (ratio < 1.0) untuk fit ke cue
            const ratio = actualDuration / cueDuration
            finalAudio = await timeStretchClient(audioBuffer, ratio, OUTPUT_SAMPLE_RATE)
          } else {
            // Speed up only: pad silence
            finalAudio = toMono(audioBuffer)
            if (audioBuffer.sampleRate !== OUTPUT_SAMPLE_RATE) {
              finalAudio = linearResample(finalAudio, audioBuffer.sampleRate, OUTPUT_SAMPLE_RATE)
            }
            const cueSamples = Math.floor(cueDuration * OUTPUT_SAMPLE_RATE)
            const padded = new Float32Array(cueSamples)
            padded.set(finalAudio, 0)
            finalAudio = padded
          }
        }

        position = Math.floor(entry.start * OUTPUT_SAMPLE_RATE)
      } else {
        // === OFF MODE: natural audio, sequential playback ===
        finalAudio = toMono(audioBuffer)
        if (audioBuffer.sampleRate !== OUTPUT_SAMPLE_RATE) {
          finalAudio = linearResample(finalAudio, audioBuffer.sampleRate, OUTPUT_SAMPLE_RATE)
        }
        position = cursor
        cursor = position + finalAudio.length
      }

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

  // Hitung total samples
  let totalSamples: number
  if (opts.respectTiming) {
    totalSamples = Math.floor(entries[entries.length - 1].end * OUTPUT_SAMPLE_RATE)
  } else {
    let maxEnd = 0
    for (const seg of placedSegments) {
      maxEnd = Math.max(maxEnd, seg.position + seg.audio.length)
    }
    totalSamples = maxEnd
  }

  // Build output
  const allAudio = new Float32Array(totalSamples)
  for (const seg of placedSegments) {
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
