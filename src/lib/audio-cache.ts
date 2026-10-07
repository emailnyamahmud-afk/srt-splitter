// IndexedDB utility untuk cache per-cue + full audio di browser.
//
// Database: srt-splitter-audio
// Stores:
//   - cue-audio: key = `${projectId}:${cueIndex}`, value = { blob, sampleRate, durationSec, generatedAt, voice, text }
//   - full-audio: key = projectId, value = { blob, sampleRate, durationSec, generatedAt, cueCount, voiceSummary }
//
// Pakai IndexedDB (bukan localStorage) karena:
// - localStorage limit 5-10MB, indexedDB bisa ratusan MB-GB
// - IndexedDB bisa simpan Blob langsung (efficient, no base64 encoding)
// - Persist antar reload, survive browser close
//
// Public API:
//   - initAudioDb(): Promise<IDBDatabase>
//   - saveCueAudio(projectId, cueIndex, blob, meta): Promise<void>
//   - getCueAudio(projectId, cueIndex): Promise<CachedCueAudio | null>
//   - deleteCueAudio(projectId, cueIndex): Promise<void>
//   - listCueAudioForProject(projectId): Promise<number>  (count of cached cues)
//   - clearCueAudioForProject(projectId): Promise<void>
//   - saveFullAudio(projectId, blob, meta): Promise<void>
//   - getFullAudio(projectId): Promise<CachedFullAudio | null>
//   - clearAll(): Promise<void>

const DB_NAME = 'srt-splitter-audio'
const DB_VERSION = 1
const STORE_CUE = 'cue-audio'
const STORE_FULL = 'full-audio'

let _db: IDBDatabase | null = null

export function initAudioDb(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    if (_db) return resolve(_db)
    if (typeof indexedDB === 'undefined') {
      reject(new Error('IndexedDB tidak tersedia di environment ini'))
      return
    }
    const req = indexedDB.open(DB_NAME, DB_VERSION)
    req.onerror = () => reject(req.error)
    req.onsuccess = () => {
      _db = req.result
      resolve(_db)
    }
    req.onupgradeneeded = (e) => {
      const db = (e.target as IDBOpenDBRequest).result
      if (!db.objectStoreNames.contains(STORE_CUE)) {
        db.createObjectStore(STORE_CUE, { keyPath: 'key' })
      }
      if (!db.objectStoreNames.contains(STORE_FULL)) {
        db.createObjectStore(STORE_FULL, { keyPath: 'projectId' })
      }
    }
  })
}

export interface CachedCueAudio {
  key: string                  // `${projectId}:${cueIndex}`
  projectId: string
  cueIndex: number
  blob: Blob                   // WAV blob
  sampleRate: number
  durationSec: number
  generatedAt: number          // epoch ms
  voice: string                // voice ID yang dipakai (e.g. 'jv-ID-DimasNeural')
  voiceId: string              // voice short ID ('dimas', 'siti', dst.)
  text: string                 // text yang di-TTS (untuk verify cache valid)
  pitch: string                // pitch setting ('+0Hz', '-10Hz', dst.)
  smartFitCap: number          // Smart Fit cap yang dipakai
}

export interface CachedFullAudio {
  projectId: string
  blob: Blob
  sampleRate: number
  durationSec: number
  generatedAt: number
  cueCount: number
  voiceSummary: string         // ringkasan voice assignment (e.g. "Dimas: 50, Siti: 30")
}

function cueKey(projectId: string, cueIndex: number): string {
  return `${projectId}:${cueIndex}`
}

export async function saveCueAudio(
  projectId: string,
  cueIndex: number,
  blob: Blob,
  meta: { sampleRate: number; durationSec: number; voice: string; voiceId: string; text: string; pitch: string; smartFitCap: number },
): Promise<void> {
  const db = await initAudioDb()
  return new Promise((resolve, reject) => {
    const tx = db.transaction(STORE_CUE, 'readwrite')
    const value: CachedCueAudio = {
      key: cueKey(projectId, cueIndex),
      projectId,
      cueIndex,
      blob,
      sampleRate: meta.sampleRate,
      durationSec: meta.durationSec,
      generatedAt: Date.now(),
      voice: meta.voice,
      voiceId: meta.voiceId,
      text: meta.text,
      pitch: meta.pitch,
      smartFitCap: meta.smartFitCap,
    }
    const req = tx.objectStore(STORE_CUE).put(value)
    req.onerror = () => reject(req.error)
    req.onsuccess = () => resolve()
  })
}

export async function getCueAudio(projectId: string, cueIndex: number): Promise<CachedCueAudio | null> {
  const db = await initAudioDb()
  return new Promise((resolve, reject) => {
    const tx = db.transaction(STORE_CUE, 'readonly')
    const req = tx.objectStore(STORE_CUE).get(cueKey(projectId, cueIndex))
    req.onerror = () => reject(req.error)
    req.onsuccess = () => resolve(req.result || null)
  })
}

export async function deleteCueAudio(projectId: string, cueIndex: number): Promise<void> {
  const db = await initAudioDb()
  return new Promise((resolve, reject) => {
    const tx = db.transaction(STORE_CUE, 'readwrite')
    const req = tx.objectStore(STORE_CUE).delete(cueKey(projectId, cueIndex))
    req.onerror = () => reject(req.error)
    req.onsuccess = () => resolve()
  })
}

export async function listCueAudioForProject(projectId: string): Promise<number> {
  const db = await initAudioDb()
  return new Promise((resolve, reject) => {
    const tx = db.transaction(STORE_CUE, 'readonly')
    const req = tx.objectStore(STORE_CUE).openCursor()
    let count = 0
    req.onerror = () => reject(req.error)
    req.onsuccess = () => {
      const cursor = req.result
      if (cursor) {
        const value = cursor.value as CachedCueAudio
        if (value.projectId === projectId) count++
        cursor.continue()
      } else {
        resolve(count)
      }
    }
  })
}

export async function listCachedCueIndices(projectId: string): Promise<Set<number>> {
  const db = await initAudioDb()
  return new Promise((resolve, reject) => {
    const tx = db.transaction(STORE_CUE, 'readonly')
    const req = tx.objectStore(STORE_CUE).openCursor()
    const indices = new Set<number>()
    req.onerror = () => reject(req.error)
    req.onsuccess = () => {
      const cursor = req.result
      if (cursor) {
        const value = cursor.value as CachedCueAudio
        if (value.projectId === projectId) indices.add(value.cueIndex)
        cursor.continue()
      } else {
        resolve(indices)
      }
    }
  })
}

export async function clearCueAudioForProject(projectId: string): Promise<void> {
  const db = await initAudioDb()
  return new Promise((resolve, reject) => {
    const tx = db.transaction(STORE_CUE, 'readwrite')
    const store = tx.objectStore(STORE_CUE)
    const req = store.openCursor()
    const keysToDelete: string[] = []
    req.onerror = () => reject(req.error)
    req.onsuccess = () => {
      const cursor = req.result
      if (cursor) {
        const value = cursor.value as CachedCueAudio
        if (value.projectId === projectId) keysToDelete.push(value.key)
        cursor.continue()
      } else {
        // Delete all collected keys
        let pending = keysToDelete.length
        if (pending === 0) { resolve(); return }
        keysToDelete.forEach(k => {
          const delReq = store.delete(k)
          delReq.onsuccess = () => {
            pending--
            if (pending === 0) resolve()
          }
          delReq.onerror = () => reject(delReq.error)
        })
      }
    }
  })
}

export async function saveFullAudio(
  projectId: string,
  blob: Blob,
  meta: { sampleRate: number; durationSec: number; cueCount: number; voiceSummary: string },
): Promise<void> {
  const db = await initAudioDb()
  return new Promise((resolve, reject) => {
    const tx = db.transaction(STORE_FULL, 'readwrite')
    const value: CachedFullAudio = {
      projectId,
      blob,
      sampleRate: meta.sampleRate,
      durationSec: meta.durationSec,
      generatedAt: Date.now(),
      cueCount: meta.cueCount,
      voiceSummary: meta.voiceSummary,
    }
    const req = tx.objectStore(STORE_FULL).put(value)
    req.onerror = () => reject(req.error)
    req.onsuccess = () => resolve()
  })
}

export async function getFullAudio(projectId: string): Promise<CachedFullAudio | null> {
  const db = await initAudioDb()
  return new Promise((resolve, reject) => {
    const tx = db.transaction(STORE_FULL, 'readonly')
    const req = tx.objectStore(STORE_FULL).get(projectId)
    req.onerror = () => reject(req.error)
    req.onsuccess = () => resolve(req.result || null)
  })
}

export async function clearAll(): Promise<void> {
  const db = await initAudioDb()
  return new Promise((resolve, reject) => {
    const tx = db.transaction([STORE_CUE, STORE_FULL], 'readwrite')
    tx.objectStore(STORE_CUE).clear()
    tx.objectStore(STORE_FULL).clear()
    tx.onerror = () => reject(tx.error)
    tx.oncomplete = () => resolve()
  })
}

/**
 * Hitung total size audio cache untuk project (untuk display "X MB cached")
 */
export async function getCacheSizeForProject(projectId: string): Promise<{ cueCount: number; totalBytes: number }> {
  const db = await initAudioDb()
  return new Promise((resolve, reject) => {
    const tx = db.transaction(STORE_CUE, 'readonly')
    const req = tx.objectStore(STORE_CUE).openCursor()
    let cueCount = 0
    let totalBytes = 0
    req.onerror = () => reject(req.error)
    req.onsuccess = () => {
      const cursor = req.result
      if (cursor) {
        const value = cursor.value as CachedCueAudio
        if (value.projectId === projectId) {
          cueCount++
          totalBytes += value.blob.size
        }
        cursor.continue()
      } else {
        resolve({ cueCount, totalBytes })
      }
    }
  })
}
