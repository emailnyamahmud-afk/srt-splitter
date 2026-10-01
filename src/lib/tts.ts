// TTS engine using Microsoft Edge TTS (free neural voices) + audio timing sync.
//
// All TTS happens via WebSocket to Microsoft Edge's free endpoint (no API key).
// Audio timing is synced to SRT: speed up if too long, pad silence if too short.
//
// Voices: id-ID-Gadis (female), id-ID-Ardi (male) — Indonesian native neural.
// Also includes English, Mandarin, Japanese, Korean for cross-language subtitles.
//
// Output: 16-bit PCM WAV at 24kHz mono.

'use client'

import type { SrtEntry, SrtPart } from './srt'
import { edgeTTS, EDGE_VOICES, DEFAULT_EDGE_VOICE, type EdgeVoice } from './edge-tts'
import {
  decodeAudioBlob,
  adjustDuration,
  concatenateWithSilence,
  encodeWav,
  downloadBlob as downloadBlobUtil,
} from './audio-utils'

export { EDGE_VOICES, DEFAULT_EDGE_VOICE, type EdgeVoice }

const OUTPUT_SAMPLE_RATE = 24000

export interface TTSProgress {
  stage: 'loading' | 'idle' | 'synthesizing' | 'stitching' | 'done' | 'error'
  message?: string
  percent?: number // 0-100
}

export type ProgressCallback = (p: TTSProgress) => void

export interface NarrationOptions {
  voice: string
  // If true, audio is generated to fit each cue's exact duration.
  // - If TTS audio > cue duration: speed up audio to fit (max 1.5x)
  // - If TTS audio < cue duration: pad with silence to match end time
  respectTiming: boolean
  onLineProgress?: (current: number, total: number, text: string) => void
  onStage?: ProgressCallback
}

export interface NarrationResult {
  blob: Blob
  sampleRate: number
  durationSec: number
}

/**
 * Synthesize a single text chunk to MP3 via Edge TTS.
 */
export async function synthesizeText(
  text: string,
  voice: string = DEFAULT_EDGE_VOICE,
): Promise<{ audioBlob: Blob; mimeType: string }> {
  if (!text.trim()) {
    return { audioBlob: new Blob([]), mimeType: 'audio/mp3' }
  }
  const blob = await edgeTTS(text, voice)
  return { audioBlob: blob, mimeType: 'audio/mp3' }
}

/**
 * Generate narration audio for a list of SRT entries, stitched into one WAV.
 *
 * Each subtitle line is:
 * 1. Synthesized via Edge TTS → MP3
 * 2. Decoded to PCM
 * 3. Adjusted to fit cue duration (speed up if too long, pad silence if too short)
 * 4. Concatenated with silence padding between cues
 *
 * Output is exactly the same duration as the original SRT when respectTiming=true.
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
      // Empty cue — generate silence for full duration
      if (opts.respectTiming) {
        const cueDuration = entry.end - entry.start
        const silenceSamples = Math.floor(cueDuration * OUTPUT_SAMPLE_RATE)
        segments.push(new Float32Array(silenceSamples))
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
      // 1. Synthesize to MP3
      const { audioBlob } = await synthesizeText(text, opts.voice)
      if (audioBlob.size === 0) {
        throw new Error('Empty audio output')
      }

      // 2. Decode MP3 → AudioBuffer
      const audioBuffer = await decodeAudioBlob(audioBlob)

      // 3. Adjust duration to fit cue
      let adjusted: Float32Array
      if (opts.respectTiming) {
        const cueDuration = entry.end - entry.start
        // Pre-silence: gap from previous cue's end to this cue's start
        const prevEnd = i > 0 ? entries[i - 1].end : 0
        const gapBefore = Math.max(0, entry.start - prevEnd)
        silenceBefore.push(Math.floor(gapBefore * OUTPUT_SAMPLE_RATE))

        adjusted = await adjustDuration(audioBuffer, cueDuration, OUTPUT_SAMPLE_RATE, {
          maxSpeedUp: 1.5,
        })
      } else {
        silenceBefore.push(Math.floor(0.3 * OUTPUT_SAMPLE_RATE)) // 300ms gap
        // Just take mono, no duration adjustment
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
      // Insert silence for the cue duration so timing stays intact
      if (opts.respectTiming) {
        const cueDuration = entry.end - entry.start
        const silenceSamples = Math.floor(cueDuration * OUTPUT_SAMPLE_RATE)
        segments.push(new Float32Array(silenceSamples))
      } else {
        segments.push(new Float32Array(0))
      }
      silenceBefore.push(0)
    }
  }

  // SAFETY CHECK: If ALL lines failed, throw error
  if (successCount === 0) {
    throw new Error(
      `TTS gagal untuk semua ${total} baris. Error pertama: ${firstError || 'unknown'}. ` +
      `Coba refresh halaman, atau cek koneksi internet (Edge TTS butuh internet).`,
    )
  }

  if (failCount > 0) {
    console.warn(`TTS: ${successCount}/${total} berhasil, ${failCount} gagal. Audio untuk baris gagal akan diganti dengan silence.`)
  }

  opts.onStage?.({ stage: 'stitching', message: 'Menjahit audio…', percent: 90 })

  // Concatenate all segments with their pre-silence
  const allAudio = concatenateWithSilence(segments, silenceBefore, OUTPUT_SAMPLE_RATE)

  // If respectTiming, pad final audio to match total SRT duration
  if (opts.respectTiming) {
    const targetEnd = entries[entries.length - 1].end
    const currentDuration = allAudio.length / OUTPUT_SAMPLE_RATE
    if (currentDuration < targetEnd) {
      const pad = Math.floor((targetEnd - currentDuration) * OUTPUT_SAMPLE_RATE)
      const padded = new Float32Array(allAudio.length + pad)
      padded.set(allAudio, 0)
      opts.onStage?.({
        stage: 'stitching',
        message: `Padding ke ${targetEnd.toFixed(1)}s`,
        percent: 95,
      })
      const blob = encodeWav(padded, OUTPUT_SAMPLE_RATE)
      return { blob, sampleRate: OUTPUT_SAMPLE_RATE, durationSec: targetEnd }
    }
  }

  const blob = encodeWav(allAudio, OUTPUT_SAMPLE_RATE)
  const durationSec = allAudio.length / OUTPUT_SAMPLE_RATE
  opts.onStage?.({ stage: 'done', message: 'Narration selesai', percent: 100 })
  return { blob, sampleRate: OUTPUT_SAMPLE_RATE, durationSec }
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
 * Trigger a browser download for a Blob.
 */
export function downloadBlob(filename: string, blob: Blob) {
  downloadBlobUtil(filename, blob)
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

// ============== Browser SpeechSynthesis (Preview Mode) ==============
// Untuk preview cepat tanpa internet/generate file. Pakai voice browser.

export interface BrowserVoice {
  voiceURI: string
  name: string
  lang: string
  localService: boolean
  default: boolean
}

export function getIndonesianBrowserVoices(): BrowserVoice[] {
  if (typeof window === 'undefined' || !window.speechSynthesis) return []
  return window.speechSynthesis
    .getVoices()
    .filter((v) => v.lang.toLowerCase().startsWith('id'))
    .map((v) => ({
      voiceURI: v.voiceURI,
      name: v.name,
      lang: v.lang,
      localService: v.localService,
      default: v.default,
    }))
}

export function previewWithBrowserTTS(
  text: string,
  voiceURI?: string,
  rate = 1.0,
  pitch = 1.0,
): Promise<void> {
  return new Promise((resolve, reject) => {
    if (typeof window === 'undefined' || !window.speechSynthesis) {
      reject(new Error('Browser tidak mendukung SpeechSynthesis'))
      return
    }
    window.speechSynthesis.cancel()
    const utterance = new SpeechSynthesisUtterance(text)
    utterance.rate = rate
    utterance.pitch = pitch
    utterance.lang = 'id-ID'
    const allVoices = window.speechSynthesis.getVoices()
    let chosen: SpeechSynthesisVoice | undefined
    if (voiceURI) {
      chosen = allVoices.find((v) => v.voiceURI === voiceURI)
    }
    if (!chosen) {
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

export function ensureBrowserVoicesLoaded(): Promise<BrowserVoice[]> {
  return new Promise((resolve) => {
    if (typeof window === 'undefined' || !window.speechSynthesis) {
      resolve([])
      return
    }
    let voices = window.speechSynthesis.getVoices()
    if (voices.length > 0) {
      resolve(voices.map(mapVoice))
      return
    }
    window.speechSynthesis.onvoiceschanged = () => {
      voices = window.speechSynthesis.getVoices()
      resolve(voices.map(mapVoice))
    }
    setTimeout(() => {
      voices = window.speechSynthesis.getVoices()
      resolve(voices.map(mapVoice))
    }, 1000)
  })
}

function mapVoice(v: SpeechSynthesisVoice): BrowserVoice {
  return {
    voiceURI: v.voiceURI,
    name: v.name,
    lang: v.lang,
    localService: v.localService,
    default: v.default,
  }
}
