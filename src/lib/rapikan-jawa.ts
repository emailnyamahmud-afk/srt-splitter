// Rapikan SRT Jawa — utility untuk editing SRT Jawa di web
//
// Konsep (user, 6 Okt 2026):
// - Bukan auto-rapikan, tapi SRT editor inline di web
// - User edit manual karena paham konteks (bawahan=krama, atasan=ngoko)
// - Aksén Jawa (é, è, ê) TIDAK dipakai — Edge TTS Jawa tidak bisa baca
// - Kamus check: highlight kata tidak dikenal
// - Per-cue toggle ngoko/krama (visual marker)
//
// Output: SRT Jawa yang siap untuk TTS (mode ON + Smart Fit)

export interface KamusEntry {
  word: string
  register: 'ngoko' | 'krama' | 'krama_inggil'
  meaning_id?: string
  krama?: string
  krama_inggil?: string
}

export interface KamusJawa {
  metadata: {
    version: string
    source: string
    register: string[]
    dialect: string
    entries: number
    note: string
  }
  words: KamusEntry[]
}

export interface RapikanResult {
  totalWords: number
  knownWords: number
  unknownWords: number
  unknownWordsList: { word: string; cueIndex: number; context: string }[]
}

/**
 * Load kamus Jawa dari public/kamus-jawa-full.json (44.585 kata dari Wiktionary Jawa)
 * Fallback ke public/kamus-jawa.json (157 entri) kalau full tidak ada
 */
export async function loadKamusJawa(): Promise<KamusJawa | null> {
  try {
    // Try full kamus first (44.585 entries)
    const response = await fetch('/kamus-jawa-full.json')
    if (response.ok) {
      const data = await response.json() as KamusJawa
      return data
    }
  } catch {
    // ignore, try fallback
  }

  // Fallback: small kamus (157 entries)
  try {
    const response = await fetch('/kamus-jawa.json')
    if (response.ok) {
      return await response.json() as KamusJawa
    }
  } catch {
    // ignore
  }

  return null
}

/**
 * Cek kata: apakah ada di kamus?
 * Case insensitive, strip punctuation
 */
export function isWordInKamus(word: string, kamus: KamusJawa | null): boolean {
  if (!kamus) return true // kalau kamus belum load, anggap semua OK
  const cleanWord = word.toLowerCase().replace(/[^\wàáâãäåæçèéêëìíîïðñòóôõöøùúûüýþÿ]/g, '')
  if (!cleanWord) return true // punctuation only = OK
  return kamus.words.some(entry => entry.word.toLowerCase() === cleanWord)
}

/**
 * Cek semua kata di SRT entries, return kata yang tidak dikenal
 */
export function checkUnknownWords(
  entries: { textLines: string[] }[],
  kamus: KamusJawa | null,
): RapikanResult {
  const unknownWordsList: { word: string; cueIndex: number; context: string }[] = []
  let totalWords = 0
  let knownWords = 0

  for (let i = 0; i < entries.length; i++) {
    const text = entries[i].textLines.join(' ')
    const words = text.split(/\s+/)
    for (const word of words) {
      const cleanWord = word.replace(/[^\wàáâãäåæçèéêëìíîïðñòóôõöøùúûüýþÿ]/g, '')
      if (!cleanWord) continue
      totalWords++
      if (isWordInKamus(cleanWord, kamus)) {
        knownWords++
      } else {
        unknownWordsList.push({
          word: cleanWord,
          cueIndex: i,
          context: text.slice(0, 80),
        })
      }
    }
  }

  return {
    totalWords,
    knownWords,
    unknownWords: unknownWordsList.length,
    unknownWordsList,
  }
}

/**
 * Hapus aksén Jawa (é, è, ê) → e polos
 * Edge TTS Jawa tidak bisa baca aksén dengan baik
 */
export function stripAksenJawa(text: string): string {
  return text
    .replace(/é/g, 'e')
    .replace(/è/g, 'e')
    .replace(/ê/g, 'e')
    .replace(/É/g, 'E')
    .replace(/È/g, 'E')
    .replace(/Ê/g, 'E')
}

/**
 * Hapus aksén dari semua text lines di entries (in-place)
 */
export function stripAksenFromEntries(entries: { textLines: string[] }[]): number {
  let count = 0
  for (const entry of entries) {
    for (let i = 0; i < entry.textLines.length; i++) {
      const original = entry.textLines[i]
      const stripped = stripAksenJawa(original)
      if (original !== stripped) {
        entry.textLines[i] = stripped
        count++
      }
    }
  }
  return count
}

/**
 * Register per-cue: ngoko, krama, atau kosong (belum ditentukan)
 * User toggle manual di UI, disimpan di metadata SRT (custom field)
 */
export type CueRegister = 'ngoko' | 'krama' | 'krama_inggil' | ''

/**
 * Get register label untuk display
 */
export function getRegisterLabel(register: CueRegister): string {
  switch (register) {
    case 'ngoko': return 'Ngoko'
    case 'krama': return 'Krama'
    case 'krama_inggil': return 'Krama Inggil'
    default: return '—'
  }
}

/**
 * Get register color untuk UI badge
 */
export function getRegisterColor(register: CueRegister): string {
  switch (register) {
    case 'ngoko': return 'bg-blue-100 text-blue-800 dark:bg-blue-950 dark:text-blue-300'
    case 'krama': return 'bg-amber-100 text-amber-800 dark:bg-amber-950 dark:text-amber-300'
    case 'krama_inggil': return 'bg-purple-100 text-purple-800 dark:bg-purple-950 dark:text-purple-300'
    default: return 'bg-gray-100 text-gray-500 dark:bg-gray-800 dark:text-gray-400'
  }
}

/**
 * Suggest register untuk kata-kata di cue
 * Kalau cue punya kata krama/krama_inggil → suggest krama
 * Kalau cuma kata ngoko → suggest ngoko
 * Hanya saran, user final decision
 */
export function suggestRegister(text: string, kamus: KamusJawa | null): CueRegister {
  if (!kamus) return ''
  const words = text.toLowerCase().split(/\s+/)
  let hasKrama = false
  let hasKramaInggil = false
  let hasNgoko = false

  for (const word of words) {
    const cleanWord = word.replace(/[^\wàáâãäåæçèéêëìíîïðñòóôõöøùúûüýþÿ]/g, '')
    if (!cleanWord) continue
    const entries = kamus.words.filter(e => e.word.toLowerCase() === cleanWord)
    for (const entry of entries) {
      if (entry.register === 'krama_inggil') hasKramaInggil = true
      else if (entry.register === 'krama') hasKrama = true
      else if (entry.register === 'ngoko') hasNgoko = true
    }
  }

  if (hasKramaInggil) return 'krama_inggil'
  if (hasKrama) return 'krama'
  if (hasNgoko) return 'ngoko'
  return ''
}

/**
 * Convert SRT text dari satu register ke register lain.
 * Contoh: "aku arep mangan" (ngoko) → "kula badhe nedha" (krama)
 *
 * Pakai kamus untuk cari pasangan kata:
 *   ngoko → krama: cari entry dengan register=ngoko, ambil krama field
 *   krama → ngoko: cari entry dengan register=krama, ambil word as ngoko
 *
 * Kalau kata tidak ada di kamus atau tidak ada pasangan, biarkan apa adanya.
 */
export function convertRegister(
  text: string,
  fromRegister: CueRegister,
  toRegister: CueRegister,
  kamus: KamusJawa | null,
): string {
  if (!kamus || !fromRegister || !toRegister || fromRegister === toRegister) {
    return text
  }

  // Build lookup map: word → target register equivalent
  const lookup = new Map<string, string>()

  for (const entry of kamus.words) {
    const word = entry.word.toLowerCase()
    if (!word) continue

    if (fromRegister === 'ngoko' && entry.register === 'ngoko') {
      // ngoko → krama: cari krama equivalent
      if (toRegister === 'krama' && entry.krama) {
        lookup.set(word, entry.krama)
      } else if (toRegister === 'krama_inggil' && entry.krama_inggil) {
        lookup.set(word, entry.krama_inggil)
      }
    } else if (fromRegister === 'krama' && entry.register === 'krama') {
      // krama → ngoko: cari ngoko equivalent (word di entry krama = kata krama)
      // Tapi kamus Wiktionary jarang punya tag krama, jadi ini mungkin terbatas
      if (toRegister === 'ngoko') {
        // Cari entry ngoko yang punya krama = word ini
        const ngokoEntry = kamus.words.find(
          e => e.register === 'ngoko' && e.krama?.toLowerCase() === word
        )
        if (ngokoEntry) {
          lookup.set(word, ngokoEntry.word)
        }
      }
    }
  }

  if (lookup.size === 0) return text

  // Replace words in text
  const words = text.split(/(\s+)/) // split tapi simpan whitespace
  const converted = words.map(w => {
    const cleanWord = w.toLowerCase().replace(/[^\wàáâãäåæçèéêëìíîïðñòóôõöøùúûüýþÿ]/g, '')
    if (!cleanWord) return w

    const replacement = lookup.get(cleanWord)
    if (replacement) {
      // Preserve case + surrounding punctuation
      const isUpperCase = w[0] === w[0]?.toUpperCase()
      const prefix = w.slice(0, w.length - cleanWord.length - (w.endsWith(cleanWord) ? 0 : 0))
      const suffix = ''
      const result = replacement
      return isUpperCase ? result.charAt(0).toUpperCase() + result.slice(1) : result
    }
    return w
  })

  return converted.join('')
}

/**
 * Convert semua entries dari satu register ke register lain (in-place)
 * Return jumlah kata yang diubah
 */
export function convertEntriesRegister(
  entries: { textLines: string[] }[],
  fromRegister: CueRegister,
  toRegister: CueRegister,
  kamus: KamusJawa | null,
): number {
  let count = 0
  for (const entry of entries) {
    for (let i = 0; i < entry.textLines.length; i++) {
      const original = entry.textLines[i]
      const converted = convertRegister(original, fromRegister, toRegister, kamus)
      if (original !== converted) {
        entry.textLines[i] = converted
        count++
      }
    }
  }
  return count
}
