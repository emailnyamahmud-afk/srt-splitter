// Audio processing utilities for SRT-to-audio timing sync.
//
// Key features:
// - Decode MP3 → PCM (AudioBuffer)
// - Adjust audio duration to fit cue duration (speed up or pad silence)
// - Concatenate multiple audio segments with timing alignment
// - Encode final Float32Array PCM to 16-bit WAV

/**
 * Decode an MP3 Blob to an AudioBuffer using Web Audio API.
 * Use sampleRate 24000 to match Edge TTS output (24kHz MP3).
 * Without this, browser default (44100Hz) would resample and cause
 * pitch/speed mismatch when re-encoding to WAV.
 */
export async function decodeAudioBlob(blob: Blob, sampleRate: number = 24000): Promise<AudioBuffer> {
  const arrayBuffer = await blob.arrayBuffer()
  const ctx = new (window.AudioContext || (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext)({ sampleRate })
  try {
    const audioBuffer = await ctx.decodeAudioData(arrayBuffer)
    return audioBuffer
  } finally {
    ctx.close()
  }
}

/**
 * Get mono Float32Array from AudioBuffer (mix down channels if stereo).
 */
export function toMono(audioBuffer: AudioBuffer): Float32Array {
  const numChannels = audioBuffer.numberOfChannels
  if (numChannels === 1) {
    return audioBuffer.getChannelData(0).slice()
  }
  // Mix down to mono by averaging channels
  const length = audioBuffer.length
  const result = new Float32Array(length)
  for (let ch = 0; ch < numChannels; ch++) {
    const channelData = audioBuffer.getChannelData(ch)
    for (let i = 0; i < length; i++) {
      result[i] += channelData[i] / numChannels
    }
  }
  return result
}

/**
 * Speed up audio by a ratio using OfflineAudioContext.
 * Returns Float32Array at original sample rate, but shorter duration.
 *
 * @param audioBuffer Source audio
 * @param ratio Speed ratio (1.0 = normal, 1.5 = 1.5x faster, 2.0 = 2x faster)
 * @param sampleRate Output sample rate
 */
export async function speedUpAudio(
  audioBuffer: AudioBuffer,
  ratio: number,
  sampleRate: number,
): Promise<Float32Array> {
  const targetLength = Math.floor(audioBuffer.length / ratio)
  const offlineCtx = new OfflineAudioContext(1, targetLength, sampleRate)
  const source = offlineCtx.createBufferSource()
  source.buffer = audioBuffer
  source.playbackRate.value = ratio
  // Preserve pitch (so it doesn't sound like chipmunk)
  // Note: preservingPitch is not supported by all browsers. Try and fall back.
  try {
    // @ts-expect-error - preservePitch is non-standard but widely supported
    source.preservePitch = true
  } catch {
    // ignore
  }
  source.connect(offlineCtx.destination)
  source.start()
  const rendered = await offlineCtx.startRendering()
  return rendered.getChannelData(0)
}

/**
 * Pad audio with silence at the end to reach target length.
 */
export function padWithSilence(audio: Float32Array, targetSamples: number): Float32Array {
  if (audio.length >= targetSamples) {
    return audio.slice(0, targetSamples)
  }
  const result = new Float32Array(targetSamples)
  result.set(audio, 0)
  // Rest stays 0 (silence)
  return result
}

/**
 * Adjust audio duration to fit target duration (in seconds).
 *
 * Strategy (NO speed up to avoid pitch change — pitch stays natural):
 * - If audio longer than target: truncate (cut off the end)
 * - If audio shorter than target: pad with silence at end
 * - If equal: return as-is
 *
 * Why no speed up: `preservePitch` property is not universal across browsers
 * (Chrome: preservePitch, Safari: webkitPreservePitch, Firefox: preservesPitch).
 * If browser doesn't support, playbackRate would change pitch → "chipmunk voice".
 * Truncating keeps pitch 100% natural, only downside is audio may cut mid-sentence
 * if cue is shorter than TTS output.
 *
 * Returns Float32Array at given sampleRate.
 */
export async function adjustDuration(
  audioBuffer: AudioBuffer,
  targetDurationSec: number,
  sampleRate: number,
  _options: { maxSpeedUp?: number } = {},
): Promise<Float32Array> {
  const sourceDuration = audioBuffer.duration
  const targetSamples = Math.floor(targetDurationSec * sampleRate)

  if (sourceDuration <= 0) {
    return new Float32Array(targetSamples) // silence
  }

  // Get mono PCM at audioBuffer's native sample rate, then resample to target sample rate
  const mono = toMono(audioBuffer)

  // Simple linear resample if sample rates differ
  if (audioBuffer.sampleRate !== sampleRate) {
    const resampled = new Float32Array(targetSamples > 0 ? Math.floor(mono.length * sampleRate / audioBuffer.sampleRate) : 0)
    for (let i = 0; i < resampled.length; i++) {
      const srcIdx = i * audioBuffer.sampleRate / sampleRate
      const idx0 = Math.floor(srcIdx)
      const idx1 = Math.min(idx0 + 1, mono.length - 1)
      const frac = srcIdx - idx0
      resampled[i] = mono[idx0] * (1 - frac) + mono[idx1] * frac
    }
    // Truncate or pad to target
    return padWithSilence(resampled, targetSamples)
  }

  // Same sample rate — just truncate or pad
  return padWithSilence(mono, targetSamples)
}

/**
 * Concatenate Float32Array segments with optional silence padding (in samples).
 */
export function concatenateWithSilence(
  segments: Float32Array[],
  silenceSamplesBefore: number[],
  totalSampleRate: number,
): Float32Array {
  let totalLength = 0
  for (let i = 0; i < segments.length; i++) {
    totalLength += (silenceSamplesBefore[i] || 0) + segments[i].length
  }
  const out = new Float32Array(totalLength)
  let offset = 0
  for (let i = 0; i < segments.length; i++) {
    // Pre-silence (already 0)
    offset += silenceSamplesBefore[i] || 0
    out.set(segments[i], offset)
    offset += segments[i].length
  }
  return out
}

/**
 * Encode Float32Array PCM samples to a 16-bit PCM WAV Blob (mono).
 */
export function encodeWav(samples: Float32Array, sampleRate: number): Blob {
  const numChannels = 1
  const bytesPerSample = 2
  const blockAlign = numChannels * bytesPerSample
  const dataSize = samples.length * bytesPerSample
  const buffer = new ArrayBuffer(44 + dataSize)
  const view = new DataView(buffer)

  // RIFF header
  writeString(view, 0, 'RIFF')
  view.setUint32(4, 36 + dataSize, true)
  writeString(view, 8, 'WAVE')

  // fmt sub-chunk
  writeString(view, 12, 'fmt ')
  view.setUint32(16, 16, true)
  view.setUint16(20, 1, true)
  view.setUint16(22, numChannels, true)
  view.setUint32(24, sampleRate, true)
  view.setUint32(28, sampleRate * blockAlign, true)
  view.setUint16(32, blockAlign, true)
  view.setUint16(34, 16, true)

  // data sub-chunk
  writeString(view, 36, 'data')
  view.setUint32(40, dataSize, true)

  // PCM samples (16-bit signed little-endian)
  let offset = 44
  for (let i = 0; i < samples.length; i++) {
    let s = samples[i]
    s = Math.max(-1, Math.min(1, s))
    const v = s < 0 ? s * 0x8000 : s * 0x7fff
    view.setInt16(offset, v, true)
    offset += 2
  }

  return new Blob([buffer], { type: 'audio/wav' })
}

function writeString(view: DataView, offset: number, str: string) {
  for (let i = 0; i < str.length; i++) {
    view.setUint8(offset + i, str.charCodeAt(i))
  }
}

/**
 * Trigger a browser download for a Blob.
 */
export function downloadBlob(filename: string, blob: Blob) {
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  setTimeout(() => URL.revokeObjectURL(url), 2000)
}
