// Time-stretch audio tanpa ubah pitch, pakai SoundTouchJS.
//
// API SoundTouchJS yang benar:
// - Stretch: pipe yang prosess audio dengan tempo change tanpa pitch change
// - SimpleFilter: filter yang wrap pipe + source audio, handle buffering
// - WebAudioBufferSource: wrap AudioBuffer-like untuk jadi source
//
// Penting: Stretch butuh sampleRate parameter di setParameters() untuk
// kalkulasi window size yang optimal. Default 44100, harus diset ke sample rate asli.

import { Stretch, SimpleFilter, WebAudioBufferSource } from 'soundtouchjs'

interface AudioBufferLike {
  numberOfChannels: number
  sampleRate: number
  length: number
  getChannelData(channel: number): Float32Array
}

function makeAudioBufferLike(audio: Float32Array, sampleRate: number): AudioBufferLike {
  return {
    numberOfChannels: 1,
    sampleRate,
    length: audio.length,
    getChannelData: () => audio,
  }
}

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
    return padOrTruncate(audio, Math.floor(targetDurationSec * sourceSampleRate))
  }

  // Calculate tempo ratio (1.0 = normal, >1.0 = faster/shorter, <1.0 = slower/longer)
  const tempo = sourceDuration / targetDurationSec

  // Setup Stretch (pipe) — ini yang process tempo change tanpa pitch change
  const stretch = new Stretch(false)
  stretch.setParameters(sourceSampleRate, 0, 0, 0) // default sequence/seekwindow/overlap
  stretch.tempo = tempo

  // Wrap Float32Array jadi AudioBuffer-like untuk WebAudioBufferSource
  const audioBufferLike = makeAudioBufferLike(audio, sourceSampleRate)
  const source = new WebAudioBufferSource(audioBufferLike)

  // SimpleFilter wrap pipe + source, handle buffering
  const filter = new SimpleFilter(source, stretch)

  // Calculate output length
  const targetSamples = Math.floor(targetDurationSec * sourceSampleRate)
  const output = new Float32Array(targetSamples)

  // Extract samples (SimpleFilter akan process dan fill output)
  filter.extract(output, targetSamples)

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
 * - If audio longer: time-stretch (faster, pitch preserved via SoundTouchJS)
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
  const maxSpeedUp = options.maxSpeedUp ?? 2.5
  const sourceDuration = audio.length / sourceSampleRate
  const targetSamples = Math.floor(targetDurationSec * sourceSampleRate)

  if (sourceDuration <= 0) {
    return new Float32Array(targetSamples) // silence
  }

  if (Math.abs(sourceDuration - targetDurationSec) < 0.05) {
    return padOrTruncate(audio, targetSamples)
  }

  if (sourceDuration > targetDurationSec) {
    const ratio = sourceDuration / targetDurationSec
    if (ratio <= maxSpeedUp) {
      return timeStretchAudio(audio, sourceSampleRate, targetDurationSec)
    } else {
      const stretchedDuration = sourceDuration / maxSpeedUp
      const stretched = timeStretchAudio(audio, sourceSampleRate, stretchedDuration)
      return padOrTruncate(stretched, targetSamples)
    }
  } else {
    return padOrTruncate(audio, targetSamples)
  }
}
