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
  trimSilenceAsymmetric,
  peakNormalize,
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

  // === SMART FIT (mode ON) — adopsi VoiceStudio fit_planner + voicertool.com ===
  // Generate natural → measure → kalau overflow, re-generate dengan audioRate (TTS server-side, pitch preserved).
  // Video tetap 100% sync SRT ori (tidak di-retim). Crossfade kalau audio masih overflow.
  // Filosofi: audio dub fit ke SRT ori, video = ground truth (mode ON klasik).
  smartFit?: boolean                // default false. true: aktifkan Smart Fit per-cue dynamic speed.
  smartFitAudioRateCap?: number     // default 2.0 — batas atas TTS speed (pitch preserved). Voicertool cap.
  smartFitUseAsymmetricTrim?: boolean // default true — voicertool pattern: head -40dB aggressive, tail -49dB gentle.
  smartFitCrossfadeMs?: number       // default 150 — crossfade kalau audio overflow cue (tumpang tindih smooth ke cue next).
  smartFitNormalizeDbFS?: number     // default -2 — per-cue peak normalize untuk loudness konsisten.

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

      if (opts.respectTiming && opts.smartFit) {
        // === ON MODE + SMART FIT (VoiceStudio fit_planner + voicertool asymmetric trim) ===
        // Strategi baru (5 Okt 2026, setelah 20x test render gagal):
        // Video = ground truth (SRT ori). Audio dub fit ke SRT ori dengan Smart Fit.
        // Tidak perlu render video, video 100% sync.
        //
        // Algoritma:
        // 1. Generate natural TTS (speed 1.0)
        // 2. Asymmetric trim (head -40dB aggressive, tail -49dB gentle, voicertool pattern)
        // 3. Compute need = naturalDur / cueDur
        // 4. Kalau need <= 1.0 → pakai natural (no speedup)
        // 5. Kalau need > 1.0 → re-generate dengan audioRate = min(need, cap)
        //    - Edge TTS server-side rate (pitch preserved, BUKAN atempo robot)
        //    - Voicertool: cap 2.0. Kita: cap 1.5 (default, lebih konservatif natural)
        // 6. Kalau audio masih overflow cue (jarang, kalau cap < need):
        //    - Crossfade 150ms ke cue next (tumpang tindih smooth)
        //    - Atau kalau cue terakhir, potong audio ke cueEnd (accept truncation)
        // 7. Peak normalize -2 dBFS (loudness konsisten antar cue)
        const cueDuration = entry.end - entry.start
        const cueStartSamples = Math.floor(entry.start * OUTPUT_SAMPLE_RATE)
        const cueEndSamples = Math.floor(entry.end * OUTPUT_SAMPLE_RATE)
        const audioRateCap = opts.smartFitAudioRateCap ?? 2.0
        const useAsymTrim = opts.smartFitUseAsymmetricTrim ?? true
        const crossfadeMs = opts.smartFitCrossfadeMs ?? 150
        const normalizeDbFS = opts.smartFitNormalizeDbFS ?? -2

        // Pass 1: generate natural
        const synth1 = await synthesizeText(text, {
          ...opts, rate: '+0%', openaiSpeed: 1.0, speed: 1.0,
          onModelProgress: opts.onModelProgress,
        })
        const pass1 = await decodeMonoTrimResample(synth1, OUTPUT_SAMPLE_RATE, false)
        const naturalAudio = useAsymTrim
          ? trimSilenceAsymmetric(pass1.audio, OUTPUT_SAMPLE_RATE, 30)
          : trimSilence(pass1.audio, -30, OUTPUT_SAMPLE_RATE, 50)
        const naturalDur = naturalAudio.length / OUTPUT_SAMPLE_RATE
        const need = naturalDur / Math.max(0.001, cueDuration)

        if (need <= 1.0) {
          // Cue muat natural — pakai natural
          finalAudio = naturalAudio
        } else {
          // Smart Fit: re-generate dengan audioRate = min(need, cap)
          const audioRate = Math.min(need, audioRateCap)
          if (opts.provider === 'edge') {
            const synth2 = await synthesizeText(text, {
              ...opts, rate: formatEdgeRate(audioRate),
              onModelProgress: opts.onModelProgress,
            })
            const pass2 = await decodeMonoTrimResample(synth2, OUTPUT_SAMPLE_RATE, false)
            finalAudio = useAsymTrim
              ? trimSilenceAsymmetric(pass2.audio, OUTPUT_SAMPLE_RATE, 30)
              : trimSilence(pass2.audio, -30, OUTPUT_SAMPLE_RATE, 50)
          } else {
            const synth2 = await synthesizeText(text, {
              ...opts, openaiSpeed: audioRate,
              speed: opts.provider === 'kokoro' ? audioRate : undefined,
              onModelProgress: opts.onModelProgress,
            })
            const pass2 = await decodeMonoTrimResample(synth2, OUTPUT_SAMPLE_RATE, false)
            finalAudio = useAsymTrim
              ? trimSilenceAsymmetric(pass2.audio, OUTPUT_SAMPLE_RATE, 30)
              : trimSilence(pass2.audio, -30, OUTPUT_SAMPLE_RATE, 50)
          }
        }

        // Peak normalize (VoiceStudio Pattern D, opsional kalau normalizeDbFS = 0)
        if (normalizeDbFS < 0) {
          peakNormalize(finalAudio, normalizeDbFS, -50.0)
        }

        // JANGAN truncate audio ke cue + crossfade allowance.
        // FIX user feedback (5 Okt 2026): "banyak cue terpotong di akhir".
        // Sebelumnya truncate ke maxAllowedSamples = cue + 150ms crossfade.
        // Kalau audio Smart Fit (1.5x) masih 2x lebih panjang dari cue (need > 3.0),
        // audio dipotong → "terpotong di akhir".
        //
        // Sekarang: biarkan audio utuh. Crossfade di stitch step akan handle overlap.
        // Audio yang overflow ke cue next akan:
        // - Fade out di region overlap (150ms sebelum cue next start)
        // - Cue next fade in di awal
        // - Mix additive → tumpang tindih smooth
        //
        // Trade-off: kalau audio sangat panjang (need >> cap), bisa overlap banyak cue.
        // Tapi lebih baik tumpang tindih (user dengar dua cue sebentar) daripada terpotong.
        // User: "tumpang tindih kecil, tapi ini harga yg harus dibayar jika tak mau repot render."

        position = cueStartSamples
        cursor = position + finalAudio.length
      } else if (opts.respectTiming) {
        // === ON MODE LAMA: TRIM SILENCE → NATURAL-FIRST + speed up only kalau tabrakan ===
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
// DUBBING MODE — SRT Jawa sebagai ground truth (v2.0 schema)
// ============================================================
//
// Filosofi: Audio natural → SRT baru ngikut audio → MP4 ngikut SRT baru.
// "Dub = hulu" — kalau hulu sampah, hasil sampah. Kualitas dub menentukan kualitas
// seluruh pipeline (SRT baru + retime-map JSON + downstream video retim).
//
// VoiceStudio adopsi (PR ini):
//   Pattern A (Slack Absorption): slot cue extends ke dalam gap sampai gap - 50ms
//     guard. Push back HANYA kalau audio overflow melebihi slot extended.
//     Mengurangi jumlah push back → kurangi slow-mo video → lebih natural.
//   Pattern C (15ms fade in/out): di-aplikasikan via mixAudioInto (audio-utils).
//     Prevent audible click di cue boundary (plosive/breath patah tiba-tiba).
//   Pattern D (Peak normalize -2 dBFS): per-cue sebelum mix, loudness konsisten
//     antar cue. Silence floor -50 dBFS supaya tidak amplify hening.
//   Pattern G (SRT de-overlap + formatTime rounding): di srt.ts, bukan di sini.
//
// Algoritma:
// 1. Generate audio natural per cue (Edge TTS rate 1.0x/1.25x/1.5x sesuai pilihan)
// 2. Peak-normalize per cue ke -2 dBFS (loudness konsisten antar cue)
// 3. Bangun timeline baru:
//    - newStart = original.start + offset (offset mulai dari 0)
//    - newEnd = newStart + audioDur (audio utuh, tidak dipotong)
//    - Slack absorption: audio boleh overflow cue asli selama masih muat di
//      cue + gap - 50ms guard. Hanya kalau overflow slot extended, push back.
// 4. Bangun chunks[] untuk retime-map.json v2.0:
//    - 'head': pre-roll video sebelum cue pertama (jika cue[0].start > 0)
//    - 'cue': dialog dengan audioRate (TTS) + videoRatio (setpts downstream)
//    - 'gap': jeda antar cue, factor = newDuration / originalDuration (FIX v1.0 bug)
// 5. Bangun fittedCues[] — actual cue times di audio final (ground truth SRT baru)
//
// Output: 3 file
// - audio-jawa.wav (audio utuh natural, 24kHz mono, peak -2 dBFS, fade 15ms)
// - subs-jawa-new.srt (SRT BARU dengan timing dari fittedCues)
// - retime-map.json v2.0 (chunks + fittedCues + params + metadata)

export interface DubbingOptions {
  provider: Provider
  voice: string
  model?: string
  apiKey?: string
  speed?: number             // 1.0, 1.25, 1.5 (default 1.0x = natural). Ignored jika smartFit=true.
  smartFit?: boolean         // default false. Jika true: per-cue dynamic TTS speed (VoiceStudio fit_planner).
                              // Generate natural → measure → kalau overflow, re-generate dengan
                              // audioRate = min(sqrt(need), 1.5) (pitch preserved, bukan atempo robot).
                              // Video slow-mo capped di 2.0x. Stop-motion minimal.
  smartFitAudioRateCap?: number   // default 1.5 — batas atas TTS speed (pitch preserved)
  smartFitVideoSlowCap?: number   // default 2.0 — batas atas video slow-mo (setpts × ratio)
  minGapSec?: number         // default 0.15 (150ms) — min jeda antar cue SETELAH push back
  gapGuardSec?: number       // default 0.05 (50ms) — VoiceStudio slack absorption guard
  concurrency?: number       // default 3 — parallel generate untuk speed up
  peakNormalizeDbFS?: number // default -2 (dBFS) — VoiceStudio Pattern D
  onModelProgress?: (p: TTSProgress) => void
  onLineProgress?: (current: number, total: number, text: string) => void
  onStage?: ProgressCallback
}

// v2.0 chunk type — backward compatible dengan v1.0 'cue'/'gap', tambah 'head'/'tail'
export type DubbingChunkType = 'head' | 'cue' | 'gap' | 'tail'

export type DubbingChunkStatus =
  | 'fits'                    // audio muat di cue original, mungkin underrun (silence di akhir cue)
  | 'audio_extended_into_gap' // audio overflow cue TAPI muat di cue+gap-guard (slack absorption)
  | 'overflow_pushed_back'   // audio overflow slot extended, cue berikutnya di-push back
  | 'skipped'                 // cue gagal/invalid, skip di stitching
  | 'head_silent'             // pre-roll video sebelum cue pertama
  | 'tail_silent'             // post-roll video setelah cue terakhir (informational)

export interface DubbingChunk {
  // v2.0 — index 0-based, segId untuk debugging
  index: number
  segId: string               // e.g., "head", "cue-0042", "gap-0042"
  type: DubbingChunkType
  cueIndex?: number           // 0-based, hanya untuk 'cue'
  text?: string              // hanya untuk 'cue'

  // Timeline original (SRT Mandarin)
  origStart: number
  origEnd: number
  originalDuration: number   // = origEnd - origStart (untuk backward compat v1.0)

  // Timeline baru (SRT Jawa)
  newStart: number
  newEnd: number
  newDuration: number        // = newEnd - newStart

  // v2.0 — separasi audio vs video (VoiceStudio Pattern A)
  audioRate: number          // TTS rate yang dipakai (== speed, misal 1.25)
  videoRatio: number         // setpts factor untuk downstream retime-video.py

  // v1.0 backward compat — factor = newDuration / originalDuration (= videoRatio ketika audioRate=1.0)
  factor: number

  // v2.0 — status + overflow tracking
  status: DubbingChunkStatus
  overflowSec: number        // 0 = no overflow; >0 = berapa detik audio overflow yang di-push back
}

export interface DubbingFittedCue {
  id: string                // e.g., "cue-0042"
  cueIndex: number          // 0-based index di SRT asli
  start: number             // posisi aktual di audio final (seconds)
  end: number               // posisi aktual di audio final (seconds)
  durationSec: number       // = end - start
  text: string
}

export interface DubbingRetimeMap {
  version: string           // "2.0"
  source: string
  sampleRate: number        // 24000 (audio sample rate)
  speed: number             // TTS rate (audioRate global)
  minGapSec: number
  gapGuardSec: number       // slack absorption guard (default 0.05)
  totalOffsetSec: number    // total push back accumulated
  originalDurationSec: number  // SRT asli total durasi
  newDurationSec: number    // audio final durasi
  successCount: number
  failCount: number
  skippedCues: number[]     // 0-based indices of cues yang di-skip

  // VoiceStudio Pattern A — params block untuk reproducibility
  params: {
    timingStrategy: 'stretch_video'  // kita cuma support stretch_video (audio natural, video retimed)
    audioRateCap: number              // 1.5 — batas atas TTS rate (di UI cap 1.5x)
    videoSlowCap: number              // 2.0 — batas atas setpts factor (lebih dari ini = syrupy)
    gapGuardSec: number               // 0.05
    allowVideoRetime: true
    minAudioRate: number              // 1.0 — kita tidak pernah slow down audio (audio natural)
    peakNormalizeDbFS: number         // -2 dBFS
  }

  // v2.0 — chunks (v1.0 backward-compat: ada juga alias 'points' = chunks)
  chunks: DubbingChunk[]
  points: DubbingChunk[]    // ALIAS untuk backward compat (sama dengan chunks)

  // v2.0 — actual cue positions di audio (ground truth untuk SRT baru)
  fittedCues: DubbingFittedCue[]
}

// v1.0 backward compat — lama bernama DubbingRetimePoint
export type DubbingRetimePoint = DubbingChunk

export interface DubbingResult {
  audioBlob: Blob
  audioDurationSec: number
  srtContent: string         // SRT baru dengan timing ngikut audio
  retimeMap: DubbingRetimeMap
  retimeMapJson: string      // JSON string siap download
  newEntries: { start: number; end: number; text: string }[]  // untuk preview UI
}

/**
 * Generate audio Jawa natural + bangun SRT baru dengan timing ngikut audio.
 * Audio utuh 100% (tidak dipotong, tidak ditambah silence).
 *
 * v2.0 improvements vs v1.0:
 * - Slack absorption (VoiceStudio Pattern A): kurangi push back, lebih natural
 * - Peak normalize -2 dBFS per cue (Pattern D): loudness konsisten
 * - 15ms fade in/out di mix (Pattern C): no clicks di cue boundary
 * - Gap factor di-fix: sebelumnya hardcoded 1.0 (BUG), sekarang dihitung
 * - Head chunk: pre-roll video sebelum cue pertama (jika cue[0].start > 0)
 * - audioRate + videoRatio separasi (Pattern A)
 * - fittedCues array: ground truth untuk SRT baru
 * - params block: reproducibility (VoiceStudio-style)
 * - skippedCues tracking: transparency untuk cue yang gagal
 */
export async function narrateDubbingMode(
  entries: SrtEntry[],
  opts: DubbingOptions,
): Promise<DubbingResult> {
  if (entries.length === 0) throw new Error('No subtitles to narrate')

  // Default speed = 1.0 (NATURAL). User bilang dari awal: mau natural, video slow-mo OK.
  const speed = opts.speed ?? 1.0
  const minGapSec = opts.minGapSec ?? 0.15
  const gapGuardSec = opts.gapGuardSec ?? 0.05
  const peakDbFS = opts.peakNormalizeDbFS ?? -2.0
  const total = entries.length
  const concurrency = opts.concurrency ?? 3

  const edgeRate = formatEdgeRate(speed)
  const smartFit = opts.smartFit ?? false
  const audioRateCap = opts.smartFitAudioRateCap ?? 1.5
  const videoSlowCap = opts.smartFitVideoSlowCap ?? 2.0

  opts.onStage?.({ stage: 'synthesizing', message: smartFit ? 'Mulai Dubbing Smart Fit…' : 'Mulai Dubbing Mode…', percent: 0 })

  // Pre-allocate per-cue audio storage (parallel fill)
  // audioRate: TTS speed yang dipakai (1.0 = natural, 1.5 = 50% cepat pitch preserved)
  // Smart Fit: audioRate dynamic per cue. Default: speed global.
  const cueAudios: { pcm: Float32Array; durationSec: number; text: string; audioRate: number }[] = new Array(entries.length)
  for (let i = 0; i < entries.length; i++) {
    cueAudios[i] = { pcm: new Float32Array(0), durationSec: 0, text: '', audioRate: smartFit ? 1.0 : speed }
  }
  let successCount = 0
  let failCount = 0
  let firstError = ''
  let doneCount = 0
  let smartFitRegenCount = 0  // statistik: berapa cue yang di-regenerate dengan Smart Fit

  const generateOne = async (i: number) => {
    const entry = entries[i]
    const text = entry.textLines.join(' ').trim()
    const cueDur = entry.end - entry.start

    if (!text) {
      doneCount++
      opts.onLineProgress?.(doneCount, total, '(empty)')
      return
    }

    try {
      let finalAudio: Float32Array
      let finalDurationSec: number
      let finalAudioRate: number

      if (smartFit) {
        // === SMART FIT (VoiceStudio fit_planner adopsi) ===
        // Pass 1: generate natural (speed 1.0), measure actual duration
        const synth1 = await synthesizeText(text, {
          provider: opts.provider, voice: opts.voice, model: opts.model, apiKey: opts.apiKey,
          rate: opts.provider === 'edge' ? '+0%' : undefined,
          openaiSpeed: opts.provider !== 'edge' ? 1.0 : undefined,
          speed: opts.provider === 'kokoro' ? 1.0 : undefined,
          onModelProgress: opts.onModelProgress,
        })
        const dub1 = await decodeMonoTrimResample(synth1, OUTPUT_SAMPLE_RATE, true)
        const naturalDur = dub1.durationSec

        // Compute need: rasio natural audio vs cue ori
        const need = naturalDur / Math.max(0.001, cueDur)

        if (need <= 1.05) {
          // Cue muat natural — pakai natural (no speedup)
          finalAudio = dub1.audio
          finalDurationSec = naturalDur
          finalAudioRate = 1.0
        } else {
          // VoiceStudio fit_planner: geometric split
          // audioRate = min(sqrt(need), cap) — TTS server-side rate (pitch preserved, BUKAN atempo)
          // videoRatio = need / audioRate (akan dihitung di stitching)
          // Sisa overflow (need > audioRate × videoSlowCap) → tetap push back di stitching
          const audioRate = Math.min(Math.sqrt(need), audioRateCap)
          // Re-generate dengan audioRate (pitch preserved di server Edge TTS)
          if (opts.provider === 'edge') {
            const synth2 = await synthesizeText(text, {
              provider: opts.provider, voice: opts.voice, model: opts.model, apiKey: opts.apiKey,
              rate: formatEdgeRate(audioRate),
              onModelProgress: opts.onModelProgress,
            })
            const dub2 = await decodeMonoTrimResample(synth2, OUTPUT_SAMPLE_RATE, true)
            finalAudio = dub2.audio
            finalDurationSec = dub2.durationSec
            finalAudioRate = audioRate
            smartFitRegenCount++
          } else {
            // OpenAI/OpenRouter/Kokoro: pakai speed parameter
            const synth2 = await synthesizeText(text, {
              provider: opts.provider, voice: opts.voice, model: opts.model, apiKey: opts.apiKey,
              openaiSpeed: audioRate,
              speed: opts.provider === 'kokoro' ? audioRate : undefined,
              onModelProgress: opts.onModelProgress,
            })
            const dub2 = await decodeMonoTrimResample(synth2, OUTPUT_SAMPLE_RATE, true)
            finalAudio = dub2.audio
            finalDurationSec = dub2.durationSec
            finalAudioRate = audioRate
            smartFitRegenCount++
          }
        }
      } else {
        // === MODE LAMA: global speed (1.0, 1.25, 1.5) ===
        const synth = await synthesizeText(text, {
          provider: opts.provider, voice: opts.voice, model: opts.model, apiKey: opts.apiKey,
          rate: opts.provider === 'edge' ? edgeRate : undefined,
          openaiSpeed: opts.provider !== 'edge' ? speed : undefined,
          speed: opts.provider === 'kokoro' ? speed : undefined,
          onModelProgress: opts.onModelProgress,
        })
        const dub = await decodeMonoTrimResample(synth, OUTPUT_SAMPLE_RATE, true)
        finalAudio = dub.audio
        finalDurationSec = dub.durationSec
        finalAudioRate = speed
      }

      // VALIDATE durationSec
      const MAX_CUE_DURATION_SEC = 300
      if (!isFinite(finalDurationSec) || finalDurationSec <= 0 || finalDurationSec > MAX_CUE_DURATION_SEC) {
        console.warn(`[Dubbing] cue ${i} skip — invalid durationSec: ${finalDurationSec}`)
        failCount++
        if (!firstError) firstError = `cue ${i} durationSec invalid: ${finalDurationSec}`
        return
      }

      // VoiceStudio Pattern D: peak-normalize per cue ke -2 dBFS (in-place)
      peakNormalize(finalAudio, peakDbFS, -50.0)

      cueAudios[i] = { pcm: finalAudio, durationSec: finalDurationSec, text, audioRate: finalAudioRate }
      successCount++
    } catch (e) {
      failCount++
      if (!firstError) firstError = (e as Error).message
      cueAudios[i] = { pcm: new Float32Array(0), durationSec: 0, text, audioRate: smartFit ? 1.0 : speed }
      console.error('Dubbing TTS failed for line', i, e)
    } finally {
      doneCount++
      const msg = smartFit && cueAudios[i].audioRate > 1.0
        ? `Smart Fit ${doneCount}/${total} — "${text.slice(0, 30)}…" (${cueAudios[i].audioRate.toFixed(2)}x)`
        : `Dubbing ${doneCount}/${total} — "${text.slice(0, 40)}${text.length > 40 ? '…' : ''}"`
      opts.onLineProgress?.(doneCount, total, text.slice(0, 60))
      opts.onStage?.({ stage: 'synthesizing', message: msg, percent: (doneCount / total) * 90 })
    }
  }

  // Process in batches of `concurrency`
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

  // === STITCHING: bangun chunks + fittedCues + mix audio + encode WAV ===
  let indexedNewEntries: { start: number; end: number; text: string; cueIndex: number }[] = []
  let chunks: DubbingChunk[] = []
  let fittedCues: DubbingFittedCue[] = []
  let skippedCues: number[] = []
  let offset = 0
  let blob: Blob
  let audioDurationSec: number
  let srtContent: string
  let retimeMap: DubbingRetimeMap

  try {
    // Step 1: HEAD chunk (pre-roll video sebelum cue pertama, jika ada)
    // Python build_segment_tasks handle ini via last_end=0.0, tapi JSON perlu eksplisit
    // supaya downstream consumer (future) tidak perlu derivasi.
    const firstEntry = entries[0]
    if (firstEntry && firstEntry.start > 0.01) {
      const headDur = firstEntry.start
      chunks.push({
        index: chunks.length,
        segId: 'head',
        type: 'head',
        origStart: 0,
        origEnd: headDur,
        originalDuration: headDur,
        newStart: 0,
        newEnd: headDur,
        newDuration: headDur,
        audioRate: 1.0,
        videoRatio: 1.0,
        factor: 1.0,
        status: 'head_silent',
        overflowSec: 0,
      })
    }

    // Step 2: Bangun timeline baru per cue + gap
    console.log('[Dubbing] Stitching step 1: build timeline...', { totalCues: entries.length, successCount })
    for (let i = 0; i < entries.length; i++) {
      const entry = entries[i]
      const cueAudio = cueAudios[i]
      const text = entry.textLines.join(' ').trim()

      // Skip cue kosong atau invalid — track untuk skippedCues
      if (!text || !isFinite(cueAudio.durationSec) || cueAudio.durationSec <= 0) {
        skippedCues.push(i)
        continue
      }
      if (cueAudio.durationSec > 300) {
        console.warn(`[Dubbing] Stitching: cue ${i} durationSec ${cueAudio.durationSec}s > 300s, skip`)
        skippedCues.push(i)
        continue
      }

      const cueDur = entry.end - entry.start
      const audioDur = cueAudio.durationSec

      const newStart = entry.start + offset
      const newEnd = newStart + audioDur

      if (!isFinite(newEnd) || !isFinite(newStart)) {
        console.warn(`[Dubbing] Stitching: cue ${i} newStart/newEnd not finite: ${newStart}/${newEnd}, skip`)
        skippedCues.push(i)
        continue
      }
      // HARD CAP: kalau newEnd > 10 jam (36000s), skip + reset offset
      if (newEnd > 36000) {
        console.warn(`[Dubbing] Stitching: cue ${i} newEnd ${newEnd}s > 36000s (10 jam), skip + reset offset from ${offset} to 0`)
        offset = 0
        skippedCues.push(i)
        continue
      }

      indexedNewEntries.push({ start: newStart, end: newEnd, text, cueIndex: i })
      fittedCues.push({
        id: `cue-${String(i).padStart(4, '0')}`,
        cueIndex: i,
        start: newStart,
        end: newEnd,
        durationSec: audioDur,
        text,
      })

      // VoiceStudio Pattern A: status determination + slack absorption
      const nextEntry = entries[i + 1]
      const cueToCueDistance = nextEntry ? (nextEntry.start - entry.start) : Infinity
      const origGap = nextEntry ? (nextEntry.start - entry.end) : 0
      const effectiveSlot = nextEntry ? (cueToCueDistance - gapGuardSec) : Infinity

      let status: DubbingChunkStatus
      let overflowSec = 0

      if (!nextEntry) {
        // Last cue, no constraint
        status = 'fits'
      } else if (audioDur <= cueDur) {
        // Audio fits in cue original — mungkin underrun (silence di akhir cue)
        status = 'fits'
      } else if (audioDur <= effectiveSlot) {
        // VoiceStudio Pattern A: SLACK ABSORPTION
        // Audio overflow cue TAPI muat di cue + gap - guard (50ms clear sebelum next cue)
        // Tidak push back — video slow-mo di cue, gap menyusut naturally
        status = 'audio_extended_into_gap'
      } else {
        // Audio overflow slot extended → push back next cue
        // pushBack = audioDur - cueToCueDistance + minGapSec (gap after push back = minGapSec)
        const pushBack = audioDur - cueToCueDistance + minGapSec
        offset += Math.max(0, pushBack)
        overflowSec = Math.max(0, audioDur - effectiveSlot)
        status = 'overflow_pushed_back'
      }

      // videoRatio = audioDur / cueDur (>1 = slow-mo, <1 = fast-forward)
      // Smart Fit: audioRate dynamic per cue (dari cueAudios[i].audioRate)
      // Smart Fit: videoRatio capped di videoSlowCap (default 2.0) — sisanya push back di stitching
      const cueAudioRate = cueAudios[i].audioRate
      let videoRatio = audioDur / Math.max(0.001, cueDur)
      if (smartFit && videoRatio > videoSlowCap) {
        // Smart Fit: video slow-mo di-cap. Audio sudah di-speedup (audioRate),
        // video tetap slow-mo tapi capped. Sisa: audio lebih panjang dari video
        // bisa → akan di-handle push back di bawah (overflow_pushed_back).
        videoRatio = videoSlowCap
      }

      chunks.push({
        index: chunks.length,
        segId: `cue-${String(i).padStart(4, '0')}`,
        type: 'cue',
        cueIndex: i,
        text,
        origStart: entry.start,
        origEnd: entry.end,
        originalDuration: cueDur,
        newStart,
        newEnd,
        newDuration: audioDur,
        audioRate: cueAudioRate,
        videoRatio,
        factor: videoRatio, // backward compat v1.0
        status,
        overflowSec,
      })

      // Gap chunk (jika ada next cue DAN ada gap asli yang signifikan)
      if (nextEntry) {
        const gapOrigDuration = nextEntry.start - entry.end
        if (gapOrigDuration > 0.01) {
          // Compute gap in new timeline:
          // newGap = (nextEntry.start + offset_after) - newEnd
          //        = cueToCueDistance + (offset_after - offset_before) - audioDur
          //        = cueToCueDistance - audioDur + pushBack (if push back) or 0
          const newGapDuration = (nextEntry.start + offset) - newEnd

          // FIX v1.0 BUG: factor should be newGapDuration / originalGapDuration, NOT 1.0
          // v1.0 hardcoded factor=1.0 when "gap cukup" — itu salah kalau audio lebih
          // pendek dari cue (gap EXTENDS, not stays same). Sekarang: factor selalu dihitung.
          const gapFactor = newGapDuration / Math.max(0.001, gapOrigDuration)

          chunks.push({
            index: chunks.length,
            segId: `gap-${String(i).padStart(4, '0')}`,
            type: 'gap',
            cueIndex: i,
            origStart: entry.end,
            origEnd: nextEntry.start,
            originalDuration: gapOrigDuration,
            newStart: newEnd,
            newEnd: newEnd + newGapDuration,
            newDuration: newGapDuration,
            audioRate: 1.0,
            videoRatio: gapFactor,
            factor: gapFactor,
            status: status === 'overflow_pushed_back' ? 'overflow_pushed_back' : 'fits',
            overflowSec: status === 'overflow_pushed_back' ? overflowSec : 0,
          })
        }
      }
    }
    console.log('[Dubbing] Stitching step 1 done:', {
      indexedNewEntries: indexedNewEntries.length,
      offsetSec: offset,
      chunks: chunks.length,
      skippedCues: skippedCues.length,
    })

    // Step 2: Allocate audio buffer + mix
    // mixAudioInto sudah apply 15ms fade in/out (VoiceStudio Pattern C)
    const newDurationSec = indexedNewEntries.length > 0
      ? indexedNewEntries[indexedNewEntries.length - 1].end + 0.5
      : 0
    if (!isFinite(newDurationSec) || newDurationSec <= 0) {
      throw new Error(`newDurationSec invalid: ${newDurationSec} (indexedNewEntries: ${indexedNewEntries.length})`)
    }
    if (newDurationSec > 43200) {
      throw new Error(`newDurationSec ${newDurationSec}s > 12 jam — cue duration raksasa`)
    }
    const totalSamples = Math.floor(newDurationSec * OUTPUT_SAMPLE_RATE)
    console.log('[Dubbing] Stitching step 2: allocate buffer...', {
      newDurationSec, totalSamples, bytesMB: (totalSamples * 4 / 1024 / 1024).toFixed(1),
    })
    if (totalSamples <= 0 || !isFinite(totalSamples) || totalSamples > 2000000000) {
      throw new Error(`Invalid totalSamples: ${totalSamples} (newDurationSec=${newDurationSec})`)
    }
    const allAudio = new Float32Array(totalSamples)

    for (const newEntry of indexedNewEntries) {
      const cueAudio = cueAudios[newEntry.cueIndex]
      const position = Math.floor(newEntry.start * OUTPUT_SAMPLE_RATE)
      if (cueAudio.pcm.length > 0 && position < totalSamples) {
        // mixAudioInto signature: (buffer, audio, position, fadeMs=15, sampleRate=24000)
        // Fade diaplikasikan in-place ke cueAudio.pcm supaya cue lain tidak terpengaruh
        mixAudioInto(allAudio, cueAudio.pcm, position, 15, OUTPUT_SAMPLE_RATE)
      }
    }
    console.log('[Dubbing] Stitching step 2 done: audio mixed (15ms fade + peak normalize)')

    // Step 3: Encode WAV
    blob = encodeWav(allAudio, OUTPUT_SAMPLE_RATE)
    audioDurationSec = allAudio.length / OUTPUT_SAMPLE_RATE

    // Step 4: Bangun SRT string dari fittedCues (ground truth)
    srtContent = ''
    for (let i = 0; i < fittedCues.length; i++) {
      const c = fittedCues[i]
      srtContent += `${i + 1}\n`
      srtContent += `${formatTimeSrt(c.start)} --> ${formatTimeSrt(c.end)}\n`
      srtContent += c.text + '\n\n'
    }

    // Step 5: Bangun retime map v2.0
    retimeMap = {
      version: '2.0',
      source: `Original SRT: ${entries.length} cues`,
      sampleRate: OUTPUT_SAMPLE_RATE,
      speed,
      minGapSec,
      gapGuardSec,
      totalOffsetSec: offset,
      originalDurationSec: entries[entries.length - 1].end,
      newDurationSec: audioDurationSec,
      successCount,
      failCount,
      skippedCues,
      params: {
        timingStrategy: 'stretch_video',
        audioRateCap: 1.5,
        videoSlowCap: 2.0,
        gapGuardSec,
        allowVideoRetime: true,
        minAudioRate: 1.0,
        peakNormalizeDbFS: peakDbFS,
      },
      chunks,
      points: chunks, // ALIAS untuk backward compat v1.0 consumer
      fittedCues,
    }
    console.log('[Dubbing] Stitching step 5 done: retime-map v2.0 built', {
      version: retimeMap.version,
      chunks: chunks.length,
      fittedCues: fittedCues.length,
      totalOffsetSec: offset,
    })
  } catch (stitchError) {
    const errMsg = `Gagal di tahap stitching (95%): ${(stitchError as Error).message}. Stack: ${(stitchError as Error).stack?.slice(0, 200)}`
    console.error('[Dubbing] ' + errMsg, stitchError)
    throw new Error(errMsg)
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
 *
 * VoiceStudio Pattern G: round WHOLE value first, then split — supaya 59.9996s
 * tetap "00:00:59,999" (bukan "00:01:00,000" karena binary float precision bug).
 */
function formatTimeSrt(seconds: number): string {
  if (seconds < 0) seconds = 0
  let totalMs = Math.round(seconds * 1000)
  const h = Math.floor(totalMs / 3_600_000)
  totalMs -= h * 3_600_000
  const m = Math.floor(totalMs / 60_000)
  totalMs -= m * 60_000
  const s = Math.floor(totalMs / 1000)
  totalMs -= s * 1000
  const ms = totalMs
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
