// Time-stretch audio tanpa ubah pitch, pakai SoundTouchJS.
//
// SoundTouchJS adalah port JavaScript dari library SoundTouch C++ yang
// specifically dirancang untuk time-stretching (ubah durasi) tanpa ubah pitch.
// Pure JS, cross-browser, tidak bergantung pada preservePitch property
// (yang tidak reliable di OfflineAudioContext).
//
// Use case: Audio TTS 8 detik, cue SRT 5 detik.
// Time-stretch 8/5 = 1.6x lebih cepat, pitch tetap natural.
// Audio fit ke cue duration, tidak dipotong, pitch natural di semua browser.

import { SoundTouch, SimpleFilter, WebAudioBufferSource } from 'soundtouchjs'

/**
 * Time-stretch Float32Array audio untuk fit target duration.
 *
 * @param audio Source audio (Float32Array PCM mono)
 * @param sourceSampleRate Sample rate source audio
 * @param targetDurationSec Target duration in seconds
 * @returns Float32Array at sourceSampleRate with duration = targetDurationSec
 */
export function timeStretchAudio(
  audio: Float32Array,
  sourceSampleRate: number,
  targetDurationSec: number,
): Float32Array {
  if (audio.length === 0) {
    return new Float32Array(Math.floor(targetDurationSec * sourceSampleRate))
  }

  const sourceDuration = audio.length / sourceSampleRate
  if (Math.abs(sourceDuration - targetDurationSec) < 0.05) {
    // Within 50ms — no stretch needed, just pad/truncate
    return padOrTruncate(audio, Math.floor(targetDurationSec * sourceSampleRate))
  }

  // Calculate tempo ratio (1.0 = normal, >1.0 = faster/shorter, <1.0 = slower/longer)
  const tempo = sourceDuration / targetDurationSec

  // Setup SoundTouch
  const soundTouch = new SoundTouch()
  soundTouch.tempo = tempo
  soundTouch.pitchSemitones = 0 // No pitch change
  soundTouch.rate = 1.0 // No sample rate change

  // Source: Float32Array → WebAudioBufferSource
  const source = new WebAudioBufferSource(audio, audio.length)

  // Filter untuk process audio
  const filter = new SimpleFilter(soundTouch, source)

  // Calculate output length
  const targetSamples = Math.floor(targetDurationSec * sourceSampleRate)
  const output = new Float32Array(targetSamples)

  // Extract samples (SoundTouchJS akan process dan fill output)
  const samplesExtracted = filter.extract(output, targetSamples)

  // Kalau SoundTouchJS extract kurang dari target, pad dengan silence
  if (samplesExtracted < targetSamples) {
    // output sudah otomatis zero-filled oleh Float32Array constructor
  }

  return output
}

/**
 * Pad audio dengan silence atau truncate ke target length.
 */
function padOrTruncate(audio: Float32Array, targetLength: number): Float32Array {
  if (audio.length === targetLength) return audio
  if (audio.length > targetLength) {
    return audio.subarray(0, targetLength)
  }
  const result = new Float32Array(targetLength)
  result.set(audio, 0)
  return result
}

/**
 * Adjust audio duration to fit target duration.
 * - If audio longer: time-stretch (faster, pitch preserved)
 * - If audio shorter: pad with silence
 * - If equal: return as-is
 *
 * Returns Float32Array at sourceSampleRate.
 */
export function adjustAudioDuration(
  audio: Float32Array,
  sourceSampleRate: number,
  targetDurationSec: number,
  options: { maxSpeedUp?: number } = {},
): Float32Array {
  const maxSpeedUp = options.maxSpeedUp ?? 2.5 // Allow up to 2.5x speed up
  const sourceDuration = audio.length / sourceSampleRate
  const targetSamples = Math.floor(targetDurationSec * sourceSampleRate)

  if (sourceDuration <= 0) {
    return new Float32Array(targetSamples) // silence
  }

  if (Math.abs(sourceDuration - targetDurationSec) < 0.05) {
    return padOrTruncate(audio, targetSamples)
  }

  if (sourceDuration > targetDurationSec) {
    // Audio lebih panjang — time-stretch untuk fit
    const ratio = sourceDuration / targetDurationSec
    if (ratio <= maxSpeedUp) {
      // Time-stretch ke target duration
      return timeStretchAudio(audio, sourceSampleRate, targetDurationSec)
    } else {
      // Edge case: ratio > maxSpeedUp. Time-stretch ke maxSpeedUp, lalu truncate sisanya.
      // Misal: audio 10 detik, cue 2 detik, maxSpeedUp 2.5x → 4 detik. Truncate ke 2 detik.
      const stretchedDuration = sourceDuration / maxSpeedUp
      const stretched = timeStretchAudio(audio, sourceSampleRate, stretchedDuration)
      return padOrTruncate(stretched, targetSamples)
    }
  } else {
    // Audio lebih pendek — pad dengan silence
    return padOrTruncate(audio, targetSamples)
  }
}
