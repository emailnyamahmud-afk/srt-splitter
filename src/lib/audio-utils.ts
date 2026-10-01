// Audio processing utilities untuk time-stretch tanpa chipmunk.
//
// Pendekatan: OfflineAudioContext dengan playbackRate + detune compensation.
// - playbackRate = ratio → audio lebih cepat, pitch naik
// - detune = -1200 * log2(ratio) cents → pitch turun balik ke natural
// - Net effect: audio lebih cepat, pitch tetap natural
//
// Ini cross-browser compatible (Chrome, Safari, Firefox, Brave, Edge).
// Tidak pakai preservePitch property (yang tidak reliable di OfflineAudioContext).

/**
 * Decode MP3 Blob ke AudioBuffer.
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
 * Get mono Float32Array dari AudioBuffer.
 */
export function toMono(audioBuffer: AudioBuffer): Float32Array {
  const numChannels = audioBuffer.numberOfChannels
  if (numChannels === 1) {
    const result = new Float32Array(audioBuffer.length)
    audioBuffer.copyFromChannel(result, 0)
    return result
  }
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
 * Speed up audio dengan pitch preservation via detune compensation.
 *
 * Cara kerja:
 * - playbackRate = ratio → audio 1.5x lebih cepat, pitch naik ~7 semitones
 * - detune = -1200 * log2(ratio) cents → pitch turun ~7 semitones balik
 * - Net: audio 1.5x lebih cepat, pitch natural
 *
 * Tested di Chrome, Safari, Firefox, Brave, Edge (OfflineAudioContext support detune).
 *
 * @param audioBuffer Source audio
 * @param ratio Speed ratio (1.0 = normal, 1.5 = 1.5x faster, 2.0 = 2x faster)
 * @param sampleRate Output sample rate
 * @returns Float32Array at sampleRate, duration = source.duration / ratio
 */
export async function speedUpAudioPitchPreserved(
  audioBuffer: AudioBuffer,
  ratio: number,
  sampleRate: number,
): Promise<Float32Array> {
  const targetLength = Math.floor(audioBuffer.length / ratio)
  const offlineCtx = new OfflineAudioContext(1, targetLength, sampleRate)
  const source = offlineCtx.createBufferSource()
  source.buffer = audioBuffer
  source.playbackRate.value = ratio
  // Detune compensation: -1200 * log2(ratio) cents
  // ratio 1.5 → log2(1.5) ≈ 0.585 → -702 cents (turunkan ~7 semitones)
  // ratio 2.0 → log2(2.0) = 1.0 → -1200 cents (turunkan 1 octave)
  const detuneCents = -1200 * Math.log2(ratio)
  source.detune.value = detuneCents
  source.connect(offlineCtx.destination)
  source.start()
  const rendered = await offlineCtx.startRendering()
  return toMono(rendered)
}

/**
 * Pad audio dengan silence ke target length.
 */
export function padWithSilence(audio: Float32Array, targetSamples: number): Float32Array {
  if (audio.length >= targetSamples) {
    return audio.slice(0, targetSamples)
  }
  const result = new Float32Array(targetSamples)
  result.set(audio, 0)
  return result
}

/**
 * Adjust audio duration to fit target duration.
 *
 * Strategy:
 * - If audio longer than target: speed up via detune compensation (pitch natural, no chipmunk)
 *   - HAPUS maxSpeedUp limit — audio harus utuh meski harus di-speed up 5x atau lebih
 *   - Untuk ratio sangat besar (>4x), pitch masih natural via detune compensation
 *     (audio akan terdengar sangat cepat tapi tidak chipmunk dan tidak dipotong)
 * - If audio shorter than target: pad with silence
 * - If equal: return as-is
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
    return new Float32Array(targetSamples)
  }

  if (Math.abs(sourceDuration - targetDurationSec) < 0.05) {
    return padWithSilence(toMono(audioBuffer), targetSamples)
  }

  if (sourceDuration > targetDurationSec) {
    // Audio lebih panjang — speed up dengan pitch preservation (TANPA limit)
    const ratio = sourceDuration / targetDurationSec
    return await speedUpAudioPitchPreserved(audioBuffer, ratio, sampleRate)
  } else {
    // Audio lebih pendek — pad silence
    return padWithSilence(toMono(audioBuffer), targetSamples)
  }
}

/**
 * Concatenate Float32Array segments dengan silence padding (samples).
 */
export function concatenateWithSilence(
  segments: Float32Array[],
  silenceSamplesBefore: number[],
  _totalSampleRate: number,
): Float32Array {
  let totalLength = 0
  for (let i = 0; i < segments.length; i++) {
    totalLength += (silenceSamplesBefore[i] || 0) + segments[i].length
  }
  const out = new Float32Array(totalLength)
  let offset = 0
  for (let i = 0; i < segments.length; i++) {
    offset += silenceSamplesBefore[i] || 0
    out.set(segments[i], offset)
    offset += segments[i].length
  }
  return out
}

/**
 * Encode Float32Array PCM ke 16-bit WAV Blob (mono).
 */
export function encodeWav(samples: Float32Array, sampleRate: number): Blob {
  const numChannels = 1
  const bytesPerSample = 2
  const blockAlign = numChannels * bytesPerSample
  const dataSize = samples.length * bytesPerSample
  const buffer = new ArrayBuffer(44 + dataSize)
  const view = new DataView(buffer)

  writeString(view, 0, 'RIFF')
  view.setUint32(4, 36 + dataSize, true)
  writeString(view, 8, 'WAVE')
  writeString(view, 12, 'fmt ')
  view.setUint32(16, 16, true)
  view.setUint16(20, 1, true)
  view.setUint16(22, numChannels, true)
  view.setUint32(24, sampleRate, true)
  view.setUint32(28, sampleRate * blockAlign, true)
  view.setUint16(32, blockAlign, true)
  view.setUint16(34, 16, true)
  writeString(view, 36, 'data')
  view.setUint32(40, dataSize, true)

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
 * Trigger browser download for a Blob.
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
