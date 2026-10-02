// Audio processing utilities.
//
// Decode MP3 + encode WAV + crossfade mixing + download.

/**
 * Decode MP3 Blob ke AudioBuffer.
 * Sample rate 24000 untuk match Edge TTS output (24kHz MP3).
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
 * Apply linear fade out to the end of audio.
 * @param audio Audio samples
 * @param fadeStart Index where fade starts
 * @param fadeEnd Index where fade ends (volume = 0)
 */
export function applyFadeOut(audio: Float32Array, fadeStart: number, fadeEnd: number): void {
  const len = Math.min(fadeEnd, audio.length)
  for (let i = fadeStart; i < len; i++) {
    const t = (i - fadeStart) / (fadeEnd - fadeStart)
    audio[i] *= 1 - t
  }
}

/**
 * Apply linear fade in to the start of audio.
 * @param audio Audio samples
 * @param fadeStart Index where fade starts (volume = 0)
 * @param fadeEnd Index where fade ends (volume = 1)
 */
export function applyFadeIn(audio: Float32Array, fadeStart: number, fadeEnd: number): void {
  const len = Math.min(fadeEnd, audio.length)
  for (let i = fadeStart; i < len; i++) {
    const t = (i - fadeStart) / (fadeEnd - fadeStart)
    audio[i] *= t
  }
}

/**
 * Mix (overlay) audio segment into a buffer at a given position.
 * Samples are ADDED (not overwritten) — this allows crossfade overlap.
 *
 * @param buffer Target buffer (will be modified in-place)
 * @param audio Source audio to mix in
 * @param position Start position in target buffer (in samples)
 */
export function mixAudioInto(buffer: Float32Array, audio: Float32Array, position: number): void {
  const endPos = Math.min(position + audio.length, buffer.length)
  const copyLength = endPos - position
  if (copyLength <= 0) return
  for (let i = 0; i < copyLength; i++) {
    buffer[position + i] += audio[i]
  }
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
