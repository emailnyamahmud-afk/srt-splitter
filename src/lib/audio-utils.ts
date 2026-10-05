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
 * VoiceStudio Pattern C: 15ms linear fade in/out applied per-cue sebelum mix
 * untuk prevent audible click di cue boundary (plosive/breath patah tiba-tiba).
 * Fade diaplikasikan ke `audio` IN-PLACE sebelum di-mix.
 * Kalau audio lebih pendek dari 2× fade, fade di-skip (tidak ada ruang).
 *
 * @param buffer Target buffer (will be modified in-place)
 * @param audio Source audio to mix in (akan di-fade in-place)
 * @param position Start position in target buffer (in samples)
 * @param fadeMs Fade duration in milliseconds (default 15ms — VoiceStudio standard)
 * @param sampleRate Sample rate (default 24000)
 */
export function mixAudioInto(
  buffer: Float32Array,
  audio: Float32Array,
  position: number,
  fadeMs: number = 15,
  sampleRate: number = 24000,
): void {
  // VoiceStudio Pattern C: 15ms fade in/out untuk prevent clicks
  // Diaplikasikan in-place ke audio (bukan ke buffer) supaya cue lain tidak terpengaruh
  const fadeSamples = Math.floor((fadeMs / 1000) * sampleRate)
  if (audio.length > fadeSamples * 2 && fadeSamples > 0) {
    // Fade in: 0 → 1 linear
    for (let i = 0; i < fadeSamples; i++) {
      audio[i] *= i / fadeSamples
    }
    // Fade out: 1 → 0 linear
    for (let i = 0; i < fadeSamples; i++) {
      audio[audio.length - fadeSamples + i] *= (fadeSamples - i) / fadeSamples
    }
  }

  const endPos = Math.min(position + audio.length, buffer.length)
  const copyLength = endPos - position
  if (copyLength <= 0) return
  for (let i = 0; i < copyLength; i++) {
    buffer[position + i] += audio[i]
  }
}

/**
 * Peak-normalize audio ke target dBFS, dengan silence floor guard.
 * Port dari VoiceStudio audio_dsp.normalize_audio (Pattern D).
 *
 * - Target default -2 dBFS (0.794 linear) — broadcast standar, headroom untuk limiter.
 * - Silence floor -50 dBFS (0.00316 linear) — kalau audio di bawah ini, dianggap hening,
 *   JANGAN di-amplify (anti "blank noise boost" bug).
 * - Operasi in-place (audio di-modifikasi langsung).
 *
 * Use case: per-cue normalize sebelum mix supaya loudness konsisten antar cue.
 * Tanpa ini, cue yang dirender pelan jadi tenggelam, cue kencang jadi mendominasi.
 *
 * @param audio Float32Array (akan di-modifikasi in-place)
 * @param targetDbFS Target loudness dalam dBFS (default -2)
 * @param silenceFloorDbFS Floor di bawah ini = jangan normalize (default -50)
 */
export function peakNormalize(
  audio: Float32Array,
  targetDbFS: number = -2.0,
  silenceFloorDbFS: number = -50.0,
): void {
  if (audio.length === 0) return

  // Cari peak absolute
  let maxVal = 0
  for (let i = 0; i < audio.length; i++) {
    const abs = Math.abs(audio[i])
    if (abs > maxVal) maxVal = abs
  }

  // Silence floor guard — kalau peak di bawah floor, skip normalize
  const silenceFloor = Math.pow(10, silenceFloorDbFS / 20) // -50dB → 0.00316
  if (maxVal <= silenceFloor) return

  // Hitung gain untuk capai target
  const targetAmp = Math.pow(10, targetDbFS / 20) // -2dB → 0.794
  const gain = targetAmp / maxVal

  // Apply gain in-place
  for (let i = 0; i < audio.length; i++) {
    audio[i] *= gain
  }
}

/**
 * Detect leading silence — find index of first non-silent sample.
 * Port dari pydub.detect_leading_silence (ThioJoe audio_builder.py).
 *
 * Sample dianggap silent kalau |amplitude| < threshold.
 * Threshold default -30dB → amplitude 0.0316.
 *
 * @param audio Audio samples (Float32Array, -1.0 to 1.0)
 * @param thresholdDb Threshold dalam dB (default -30dB)
 * @param chunkSizeMs Chunk size untuk scan (default 10ms)
 * @param sampleRate Sample rate (default 24000)
 * @returns Index sample pertama yang non-silent (atau audio.length kalau all silent)
 */
export function detectLeadingSilence(
  audio: Float32Array,
  thresholdDb: number = -30,
  chunkSizeMs: number = 10,
  sampleRate: number = 24000,
): number {
  const threshold = Math.pow(10, thresholdDb / 20) // -30dB → 0.0316
  const chunkSize = Math.floor(sampleRate * chunkSizeMs / 1000) // 10ms chunks

  for (let i = 0; i < audio.length; i += chunkSize) {
    const end = Math.min(i + chunkSize, audio.length)
    // Cek apakah ada sample di chunk ini yang melebihi threshold
    for (let j = i; j < end; j++) {
      if (Math.abs(audio[j]) > threshold) {
        return i // Awal chunk ini = awal non-silent
      }
    }
  }
  return audio.length // All silent
}

/**
 * Trim leading & trailing silence dari audio.
 * Port dari ThioJoe trim_clip (audio_builder.py).
 *
 * @param audio Audio samples (Float32Array)
 * @param thresholdDb Threshold dB (default -30dB)
 * @param sampleRate Sample rate (default 24000)
 * @param paddingMs Padding hening minimal di awal/akhir (default 50ms — natural pause)
 * @returns Trimmed Float32Array (slice dari audio)
 */
export function trimSilence(
  audio: Float32Array,
  thresholdDb: number = -30,
  sampleRate: number = 24000,
  paddingMs: number = 50,
): Float32Array {
  if (audio.length === 0) return audio

  // Trim leading silence
  const start = detectLeadingSilence(audio, thresholdDb, 10, sampleRate)

  // Trim trailing silence: scan dari belakang
  const threshold = Math.pow(10, thresholdDb / 20)
  const chunkSize = Math.floor(sampleRate * 10 / 1000) // 10ms
  let end = audio.length
  for (let i = audio.length; i > 0; i -= chunkSize) {
    const chunkStart = Math.max(0, i - chunkSize)
    let found = false
    for (let j = chunkStart; j < i; j++) {
      if (Math.abs(audio[j]) > threshold) {
        end = i
        found = true
        break
      }
    }
    if (found) break
  }

  // Kalau semua silent, return 50ms hening (avoid empty)
  if (start >= end) {
    return audio.slice(0, Math.min(audio.length, Math.floor(sampleRate * 0.05)))
  }

  // Tambahkan padding (50ms) di awal/akhir supaya tidak abrupt
  const paddingSamples = Math.floor(sampleRate * paddingMs / 1000)
  const paddedStart = Math.max(0, start - paddingSamples)
  const paddedEnd = Math.min(audio.length, end + paddingSamples)

  return audio.slice(paddedStart, paddedEnd)
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
