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
  mixAudioInto,
  applyFadeOut,
  applyFadeIn,
  trimSilence,
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
  model?: string
  apiKey?: string
  speed?: number
  respectTiming: boolean
  speedMode?: 'speedup-only' | 'speedup-slowdown'
  offSpeed?: number // OFF mode: kecepatan multiplier (1.0 = natural, 1.25, 1.5, 2.0)
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
 * Decode synth result + convert ke mono + resample + TRIM SILENCE.
 *
 * Port dari ThioJoe trim_clip (audio_builder.py):
 * - detect_leading_silence → trim awal
 * - reverse → detect_leading_silence → trim akhir
 * - + 50ms padding di awal/akhir supaya tidak abrupt
 *
 * Returns Float32Array (resampled ke OUTPUT_SAMPLE_RATE, trimmed).
 */
async function decodeMonoTrimResample(
  synth: { audioBlob: Blob; mimeType: string; pcm?: Float32Array; sampleRate?: number },
  sampleRate: number = OUTPUT_SAMPLE_RATE,
  trimSilenceEnabled: boolean = true,
): Promise<{ audio: Float32Array; durationSec: number; rawDurationSec: number; trimmedDurationSec: number }> {
  let audioBuffer: AudioBuffer
  if (synth.pcm) {
    if (synth.pcm.length === 0) throw new Error('Empty audio output')
    const pcmSampleRate = synth.sampleRate || sampleRate
    const ctx = new AudioContext({ sampleRate: pcmSampleRate })
    audioBuffer = ctx.createBuffer(1, synth.pcm.length, pcmSampleRate)
    audioBuffer.copyToChannel(synth.pcm, 0)
    ctx.close()
  } else {
    if (synth.audioBlob.size === 0) throw new Error('Empty audio output')
    audioBuffer = await decodeAudioBlob(synth.audioBlob, sampleRate)
  }

  const rawDurationSec = audioBuffer.duration
  let mono = toMono(audioBuffer)
  if (audioBuffer.sampleRate !== sampleRate) {
    mono = linearResample(mono, audioBuffer.sampleRate, sampleRate)
  }

  let trimmed: Float32Array
  if (trimSilenceEnabled && mono.length > 0) {
    trimmed = trimSilence(mono, -30, sampleRate, 50)
  } else {
    trimmed = mono
  }
  const trimmedDurationSec = trimmed.length / sampleRate

  return {
    audio: trimmed,
    durationSec: trimmedDurationSec,
    rawDurationSec,
    trimmedDurationSec,
  }
}

/**
 * Speed up atau slow down TIDAK di client — OfflineAudioContext + preservePitch
 * TIDAK berfungsi di Brave. Return audio asli.
 *
 * Kita pakai TWO-PASS Edge TTS server-side rate instead.
 */
async function timeStretchClient(
  audioBuffer: AudioBuffer,
  _ratio: number,
  sampleRate: number,
): Promise<Float32Array> {
  // TIDAK speed up di client — preservePitch tidak berfungsi di OfflineAudioContext Brave
  // Return audio asli (natural). Speed up di-handle via TWO-PASS Edge TTS.
  const mono = toMono(audioBuffer)
  if (audioBuffer.sampleRate !== sampleRate) {
    return linearResample(mono, audioBuffer.sampleRate, sampleRate)
  }
  return mono
}

/**
 * Format ratio jadi Edge TTS rate percent string.
 * ratio 1.0 = +0%, 1.5 = +50%, 0.8 = -20%
 */
function formatEdgeRate(ratio: number): string {
  // Clamp ke range yang Edge TTS support: -50% sampai +200% (ratio 0.5-3.0)
  const clamped = Math.min(Math.max(ratio, 0.5), 3.0)
  const percent = Math.round((clamped - 1) * 100)
  return (percent >= 0 ? '+' : '') + percent + '%'
}

/**
 * Generate narration audio for SRT entries, stitched into one WAV.
 *
 * DUA MODE (filosofi Voicertool.com/subs):
 *
 * ON (respectTiming=true): audio fit ke cue duration, durasi = SRT
 * - TWO-PASS Edge TTS: generate natural → ukur → re-generate dengan rate kalau perlu
 * - Speed mode (opts.speedMode):
 *   • "speedup-only": speed up kalau audio lebih panjang dari cue,
 *     biarkan silence di akhir cue kalau lebih pendek (natural hening).
 *   • "speedup-slowdown" (DEFAULT — filosofi Voicertool kombinasi):
 *     speed up kalau lebih panjang, SLOW DOWN kalau lebih pendek —
 *     cue selalu terisi penuh, tidak ada silence.
 * - Clamp slowdown: minimum 0.7x (Edge rate -30%) supaya audio tidak kedengaran aneh.
 * - Audio DIPERTAHANKAN UTUH — TIDAK ADA TRUNCATION
 * - Kalau audio cue lebih panjang dari cue → tumpuk dengan CROSSFADE:
 *   cue N fade out di region overlap, cue N+1 fade in di region overlap
 * - Position = entry.start (SRT timing WAJIB)
 * - Total durasi = SRT end time
 *
 * OFF (respectTiming=false): audio natural alami (TANPA POTONGAN)
 * - Sequential playback, audio utuh 100%
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
  // Tiap segment: { position, audio, cueStart, cueEnd }
  const placedSegments: { position: number; audio: Float32Array; cueStart: number; cueEnd: number }[] = []
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
      let finalAudio: Float32Array
      let position: number

      if (opts.respectTiming) {
        // === ON MODE: TRIM SILENCE → NATURAL-FIRST + speed up only kalau tabrakan ===
        // Port dari ThioJoe audio_builder.py:
        // 1. Generate TTS natural
        // 2. TRIM SILENCE di awal/akhir (detect_leading_silence -30dB + 50ms padding)
        // 3. Hitung ratio berdasarkan TRIMMED duration (bukan raw TTS output)
        // 4. Kalau trimmed ≤ cue → pakai natural (tanpa speed up, tanpa silence buatan)
        // 5. Kalau trimmed > cue → speed up via Edge TTS server-side rate
        const cueDuration = entry.end - entry.start
        const cueStartSamples = Math.floor(entry.start * OUTPUT_SAMPLE_RATE)
        const cueEndSamples = Math.floor(entry.end * OUTPUT_SAMPLE_RATE)

        // Hitung ruang yang tersedia: dari entry.start sampai cue berikutnya mulai
        // Kalau ini cue terakhir, ruang = cue end (SRT duration)
        const nextEntryStart = (i + 1 < entries.length) ? entries[i + 1].start : entry.end
        const availableDuration = nextEntryStart - entry.start

        // PASS 1: Generate natural audio untuk ukur actual duration
        const synth1 = await synthesizeText(text, { ...opts, rate: '+0%', openaiSpeed: 1.0, speed: 1.0 })

        // Decode + mono + resample + TRIM SILENCE
        const pass1 = await decodeMonoTrimResample(synth1, OUTPUT_SAMPLE_RATE, true)
        const actualDuration = pass1.durationSec // TRIMMED duration (bukan raw TTS)

        // SKEMA 1: NATURAL-FIRST (untuk speedup-only)
        // Mode "speedup-only" (seperti Voicertool): biarkan silence di akhir cue kalau audio lebih pendek.
        // Mode "speedup-slowdown" (seperti Voicertool): kalau audio lebih pendek dari cue, SLOW DOWN supaya fit penuh.
        const speedMode = opts.speedMode || 'speedup-slowdown' // default = filosofi Voicertool kombinasi
        const MIN_SLOWDOWN_RATIO = 0.7 // batas bawah: audio tidak boleh lebih lambat dari 0.7x (kedengaran aneh kalau terlalu lambat)

        if (actualDuration <= cueDuration) {
          // Audio muat di cue (entry.start → entry.end)
          if (speedMode === 'speedup-slowdown' && actualDuration < cueDuration * 0.95) {
            // Mode Voicertool "speed up and slow down": SLOW DOWN untuk isi cue penuh (hilangkan silence)
            // Ratio: actualDuration / cueDuration (e.g., 0.7 → Edge rate = -30%)
            // Clamp ke MIN_SLOWDOWN_RATIO supaya tidak terlalu lambat
            const rawRatio = actualDuration / cueDuration
            const slowRatio = Math.max(rawRatio, MIN_SLOWDOWN_RATIO)
            // Edge TTS rate: ratio 0.7 → -30%, ratio 1.0 → +0%
            const edgeRate = formatEdgeRate(slowRatio)

            if (opts.provider === 'edge' && slowRatio < 0.97) {
              // Re-generate dengan Edge TTS server-side rate (pitch dipertahankan di server)
              const synthSlow = await synthesizeText(text, {
                ...opts,
                rate: edgeRate,
                openaiSpeed: slowRatio,
                speed: slowRatio,
              })
              // Pass 2 juga di-trim supaya konsisten
              const passSlow = await decodeMonoTrimResample(synthSlow, OUTPUT_SAMPLE_RATE, true)
              finalAudio = passSlow.audio
            } else {
              // Provider non-Edge atau ratio sudah dekat 1.0 → pakai natural (trimmed pass 1)
              finalAudio = pass1.audio
            }
          } else {
            // speedup-only: pakai natural yang sudah di-trim (hening asli TTS sudah hilang,
            // tapi kalau trimmed masih lebih pendek dari cue, sisanya tetap hening — itu natural SRT)
            finalAudio = pass1.audio
          }
        }
        // SKEMA 2: SPEED UP (kalau audio TIDAK muat di cue)
        else if (opts.provider === 'edge') {
          // Hitung ratio berdasarkan ruang tersedia, BUKAN cue duration saja.
          // Ruang = dari entry.start sampai cue berikutnya mulai (atau cue.end kalau terakhir).
          // Kalau ruang = 7s, audio = 10s → ratio = 10/7 = 1.43x
          // Kalau ruang = cue = 5s, audio = 10s → ratio = 10/5 = 2.0x
          const targetDuration = Math.max(cueDuration, availableDuration)
          const ratio = actualDuration / targetDuration
          const edgeRate = formatEdgeRate(ratio)

          // Kalau ratio kecil (audio sedikit lebih panjang dari ruang), pakai natural + crossfade
          if (ratio <= 1.1) {
            // Audio hanya sedikit lebih panjang — pakai natural (trimmed), crossfade handle
            finalAudio = pass1.audio
          } else {
            // Speed up needed — re-generate dengan Edge TTS server-side rate (pitch preserved)
            const synth2 = await synthesizeText(text, {
              ...opts,
              rate: edgeRate,
              openaiSpeed: ratio,
              speed: ratio,
            })
            // Pass 2 juga di-trim
            const pass2 = await decodeMonoTrimResample(synth2, OUTPUT_SAMPLE_RATE, true)
            finalAudio = pass2.audio
          }
        } else {
          // OpenAI/OpenRouter/Kokoro: pakai audio dari pass 1 (sudah natural + trimmed)
          finalAudio = pass1.audio
        }

        position = cueStartSamples
        cursor = position + finalAudio.length
      } else {
        // === OFF MODE: natural audio dengan optional speed multiplier (trim silence juga) ===
        const offSpeed = opts.offSpeed || 1.0
        let offRate = '+0%'
        let offOpenaiSpeed = 1.0
        let offKokoroSpeed = 1.0
        if (offSpeed !== 1.0) {
          offRate = formatEdgeRate(offSpeed)
          offOpenaiSpeed = offSpeed
          offKokoroSpeed = offSpeed
        }

        const synth = await synthesizeText(text, {
          ...opts,
          rate: offRate,
          openaiSpeed: offOpenaiSpeed,
          speed: offKokoroSpeed,
        })

        // OFF mode juga trim silence supaya audio lebih rapat antar cue (tidak ada hening buatan di awal/akhir)
        const off = await decodeMonoTrimResample(synth, OUTPUT_SAMPLE_RATE, true)
        finalAudio = off.audio
        position = cursor
        cursor = position + finalAudio.length
      }

      placedSegments.push({
        position,
        audio: finalAudio,
        cueStart: Math.floor(entry.start * OUTPUT_SAMPLE_RATE),
        cueEnd: Math.floor(entry.end * OUTPUT_SAMPLE_RATE),
      })
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

  opts.onStage?.({ stage: 'stitching', message: 'Menjahit audio + crossfade…', percent: 90 })

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

  // Build output dengan CROSSFADE
  const allAudio = new Float32Array(totalSamples)

  for (let i = 0; i < placedSegments.length; i++) {
    const seg = placedSegments[i]

    // Kalau ON mode dan audio extends beyond cueEnd (overlap dengan cue berikutnya)
    if (opts.respectTiming && seg.cueEnd > 0) {
      // Cek apakah ada cue berikutnya yang overlap
      const nextSeg = placedSegments[i + 1]
      if (nextSeg) {
        const overlapStart = seg.cueEnd // cue end = next cue start
        const overlapEnd = Math.min(seg.position + seg.audio.length, nextSeg.position + 100) // overlap region

        if (overlapEnd > overlapStart && seg.position + seg.audio.length > overlapStart) {
          // Ada overlap — apply fade out ke akhir cue ini
          const fadeStart = overlapStart - seg.position
          const fadeEnd = Math.min(seg.audio.length, overlapEnd - seg.position)
          if (fadeEnd > fadeStart) {
            applyFadeOut(seg.audio, fadeStart, fadeEnd)
          }

          // Apply fade in ke awal cue berikutnya
          const fadeInStart = 0
          const fadeInEnd = Math.min(nextSeg.audio.length, fadeEnd - fadeStart)
          if (fadeInEnd > fadeInStart) {
            applyFadeIn(nextSeg.audio, fadeInStart, fadeInEnd)
          }
        }
      }
    }

    // MIX audio ke buffer (ADD, bukan overwrite)
    mixAudioInto(allAudio, seg.audio, seg.position)
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

// ============================================================
// DUBBING MODE — SRT Jawa sebagai ground truth
// ============================================================
//
// Filosofi: Audio natural → SRT baru ngikut audio → MP4 ngikut SRT baru.
//
// Algoritma:
// 1. Generate audio natural per cue (Edge TTS rate 1.0x/1.25x/1.5x sesuai pilihan)
// 2. Bangun SRT baru: cue.start = original.start + accumulated_offset
//    cue.end = cue.start + audio_duration (audio utuh, tidak dipotong, tidak ditambah silence)
// 3. Kalau audio overflow ke cue asli berikutnya → offset bertambah
// 4. Kalau ada gap cukup (zona pemandangan) → offset tidak berubah (natural)
// 5. Min gap antar cue (default 150ms) — kalau audio cue[n] terlalu deket dengan cue[n+1].start,
//    push back cue[n+1] supaya ada jeda natural
//
// Output: 3 file
// - audio-jawa.wav (audio utuh natural, 24kHz mono)
// - subs-jawa-new.srt (SRT BARU dengan timing dari audio)
// - retime-map.json (peta retim video untuk ffmpeg)

export interface DubbingOptions {
  provider: Provider
  voice: string
  model?: string
  apiKey?: string
  speed?: number             // 1.0, 1.25, 1.5 (default 1.25x — bantu slow-mo video)
  minGapSec?: number         // default 0.15 (150ms)
  concurrency?: number       // default 3 — parallel generate untuk speed up
  onModelProgress?: (p: TTSProgress) => void
  onLineProgress?: (current: number, total: number, text: string) => void
  onStage?: ProgressCallback
}

export interface DubbingRetimePoint {
  cueIndex: number           // 0-based
  originalStart: number      // seconds
  originalEnd: number        // seconds
  newStart: number           // seconds (di SRT baru)
  newEnd: number             // seconds
  originalDuration: number   // seconds
  newDuration: number        // seconds
  factor: number             // newDuration / originalDuration (>1 = slow-mo, <1 = fast-forward)
  type: 'cue' | 'gap'        // cue = dialog, gap = jeda antar cue
  text?: string              // untuk cue
}

export interface DubbingResult {
  audioBlob: Blob
  audioDurationSec: number
  srtContent: string         // SRT baru dengan timing ngikut audio
  retimeMap: {
    version: string
    source: string           // info SRT asli
    speed: number
    minGapSec: number
    totalOffsetSec: number
    originalDurationSec: number
    newDurationSec: number
    points: DubbingRetimePoint[]
  }
  retimeMapJson: string      // JSON string siap download
  newEntries: { start: number; end: number; text: string }[]  // untuk preview UI
}

/**
 * Generate audio Jawa natural + bangun SRT baru dengan timing ngikut audio.
 * Audio utuh 100% (tidak dipotong, tidak ditambah silence).
 */
export async function narrateDubbingMode(
  entries: SrtEntry[],
  opts: DubbingOptions,
): Promise<DubbingResult> {
  if (entries.length === 0) throw new Error('No subtitles to narrate')

  const speed = opts.speed ?? 1.25
  const minGapSec = opts.minGapSec ?? 0.15
  const total = entries.length
  const concurrency = opts.concurrency ?? 3 // parallel generate untuk speed up

  // Edge TTS rate: 1.0x = +0%, 1.25x = +25%, 1.5x = +50%
  const edgeRate = formatEdgeRate(speed)

  opts.onStage?.({ stage: 'synthesizing', message: 'Mulai Dubbing Mode…', percent: 0 })

  // Simpan audio per cue + durasi aktual (pre-allocate untuk parallel fill)
  const cueAudios: { pcm: Float32Array; durationSec: number; text: string }[] = new Array(entries.length)
  for (let i = 0; i < entries.length; i++) {
    cueAudios[i] = { pcm: new Float32Array(0), durationSec: 0, text: '' }
  }
  let successCount = 0
  let failCount = 0
  let firstError = ''
  let doneCount = 0

  // Helper untuk generate 1 cue
  const generateOne = async (i: number) => {
    const entry = entries[i]
    const text = entry.textLines.join(' ').trim()

    if (!text) {
      doneCount++
      opts.onLineProgress?.(doneCount, total, '(empty)')
      return
    }

    try {
      const synth = await synthesizeText(text, {
        provider: opts.provider,
        voice: opts.voice,
        model: opts.model,
        apiKey: opts.apiKey,
        rate: opts.provider === 'edge' ? edgeRate : undefined,
        openaiSpeed: opts.provider !== 'edge' ? speed : undefined,
        speed: opts.provider === 'kokoro' ? speed : undefined,
        onModelProgress: opts.onModelProgress,
      })

      // Decode + mono + resample + TRIM SILENCE
      const dub = await decodeMonoTrimResample(synth, OUTPUT_SAMPLE_RATE, true)
      cueAudios[i] = { pcm: dub.audio, durationSec: dub.durationSec, text }
      successCount++
    } catch (e) {
      failCount++
      if (!firstError) firstError = (e as Error).message
      cueAudios[i] = { pcm: new Float32Array(0), durationSec: 0, text }
      console.error('Dubbing TTS failed for line', i, e)
    } finally {
      doneCount++
      // Update progress per cue complete (lebih sering dari sebelumnya)
      opts.onLineProgress?.(doneCount, total, text.slice(0, 60))
      opts.onStage?.({
        stage: 'synthesizing',
        message: `Dubbing ${doneCount}/${total} cues — "${text.slice(0, 40)}${text.length > 40 ? '…' : ''}"`,
        percent: (doneCount / total) * 90, // max 90% (10% untuk stitching)
      })
    }
  }

  // Process in batches of `concurrency` (parallel within batch, sequential across batches)
  // Edge TTS via Vercel proxy: 3 concurrent aman (Microsoft rate limit ~10 req/sec)
  for (let i = 0; i < entries.length; i += concurrency) {
    const batch = []
    for (let j = i; j < Math.min(i + concurrency, entries.length); j++) {
      batch.push(generateOne(j))
    }
    await Promise.all(batch)
  }

  if (successCount === 0) {
    throw new Error(
      `TTS gagal untuk semua ${total} baris. Error: ${firstError || 'unknown'}. ` +
      (opts.provider === 'edge'
        ? 'Coba ganti ke provider OpenAI atau OpenRouter.'
        : 'Cek API key atau koneksi internet.'),
    )
  }

  opts.onStage?.({ stage: 'stitching', message: 'Bangun SRT baru + stitch audio…', percent: 95 })

  // Bangun SRT baru + retime map + audio buffer
  let offset = 0 // akumulasi pergeseran timeline (detik)
  const indexedNewEntries: { start: number; end: number; text: string; cueIndex: number }[] = []
  const retimePoints: DubbingRetimePoint[] = []

  for (let i = 0; i < entries.length; i++) {
    const entry = entries[i]
    const cueAudio = cueAudios[i]
    const text = entry.textLines.join(' ').trim()

    if (!text || cueAudio.durationSec === 0) continue

    // Cue baru: start = original.start + offset
    const newStart = entry.start + offset
    const newEnd = newStart + cueAudio.durationSec
    indexedNewEntries.push({ start: newStart, end: newEnd, text, cueIndex: i })

    retimePoints.push({
      cueIndex: i,
      originalStart: entry.start,
      originalEnd: entry.end,
      newStart,
      newEnd,
      originalDuration: entry.end - entry.start,
      newDuration: cueAudio.durationSec,
      factor: cueAudio.durationSec / Math.max(0.001, entry.end - entry.start),
      type: 'cue',
      text,
    })

    // Cek gap ke cue asli berikutnya
    const nextEntry = entries[i + 1]
    if (nextEntry) {
      const gapToNext = nextEntry.start - newEnd

      if (gapToNext < minGapSec) {
        // Audio overflow → push back cue berikutnya
        const pushBack = minGapSec - gapToNext
        offset += pushBack

        retimePoints.push({
          cueIndex: i,
          originalStart: entry.end,
          originalEnd: nextEntry.start,
          newStart: newEnd,
          newEnd: newEnd + (nextEntry.start - entry.end) + pushBack,
          originalDuration: nextEntry.start - entry.end,
          newDuration: (nextEntry.start - entry.end) + pushBack,
          factor: ((nextEntry.start - entry.end) + pushBack) / Math.max(0.001, nextEntry.start - entry.end),
          type: 'gap',
        })
      } else {
        // Gap cukup → tidak push back, offset tidak berubah
        retimePoints.push({
          cueIndex: i,
          originalStart: entry.end,
          originalEnd: nextEntry.start,
          newStart: newEnd,
          newEnd: newEnd + (nextEntry.start - entry.end),
          originalDuration: nextEntry.start - entry.end,
          newDuration: nextEntry.start - entry.end,
          factor: 1.0,
          type: 'gap',
        })
      }
    }
  }

  // Total durasi audio = newEnd cue terakhir + tail 0.5s
  const newDurationSec = indexedNewEntries.length > 0
    ? indexedNewEntries[indexedNewEntries.length - 1].end + 0.5
    : 0
  const totalSamples = Math.floor(newDurationSec * OUTPUT_SAMPLE_RATE)
  const allAudio = new Float32Array(totalSamples)

  // Mix audio per cue ke buffer pada posisi newStart
  for (const newEntry of indexedNewEntries) {
    const cueAudio = cueAudios[newEntry.cueIndex]
    const position = Math.floor(newEntry.start * OUTPUT_SAMPLE_RATE)
    if (cueAudio.pcm.length > 0 && position < totalSamples) {
      mixAudioInto(allAudio, cueAudio.pcm, position)
    }
  }

  // Encode WAV
  const blob = encodeWav(allAudio, OUTPUT_SAMPLE_RATE)
  const audioDurationSec = allAudio.length / OUTPUT_SAMPLE_RATE

  // Bangun SRT content string
  let srtContent = ''
  for (let i = 0; i < indexedNewEntries.length; i++) {
    const e = indexedNewEntries[i]
    srtContent += `${i + 1}\n`
    srtContent += `${formatTimeSrt(e.start)} --> ${formatTimeSrt(e.end)}\n`
    srtContent += e.text + '\n\n'
  }

  // Bangun retime map
  const retimeMap = {
    version: '1.0',
    source: `Original SRT: ${entries.length} cues`,
    speed,
    minGapSec,
    totalOffsetSec: offset,
    originalDurationSec: entries[entries.length - 1].end,
    newDurationSec: audioDurationSec,
    points: retimePoints,
  }

  opts.onStage?.({ stage: 'done', message: 'Dubbing selesai', percent: 100 })

  return {
    audioBlob: blob,
    audioDurationSec,
    srtContent,
    retimeMap,
    retimeMapJson: JSON.stringify(retimeMap, null, 2),
    newEntries: indexedNewEntries.map(({ start, end, text }) => ({ start, end, text })),
  }
}

/**
 * Format waktu SRT: "HH:MM:SS,mmm"
 */
function formatTimeSrt(seconds: number): string {
  if (seconds < 0) seconds = 0
  const h = Math.floor(seconds / 3600)
  const m = Math.floor((seconds % 3600) / 60)
  const s = Math.floor(seconds % 60)
  let ms = Math.round((seconds - Math.floor(seconds)) * 1000)
  if (ms === 1000) {
    ms = 0
  }
  return `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')},${String(ms).padStart(3, '0')}`
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
