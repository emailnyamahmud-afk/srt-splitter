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
  ngoko: string       // kata ngoko + alias (dipisah koma, mis. "aku, inyong, nyong")
  aksara: string      // aksara Jawa
  krama: string       // kata krama + alias (dipisah koma). Kosong = belum ada
  id: string          // terjemahan Indonesia. Kosong = belum ada
  keterangan: string  // definisi JAWA dari XML (membantu user isi id). JANGAN HAPUS
  sumber: string      // sumber data (mis. jv.wiktionary.org)
}

export interface KamusJawa {
  metadata: {
    version: string
    source: string
    entries: number
    note: string
    [key: string]: unknown  // untuk field tambahan di metadata
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
 * Load kamus Jawa dari Supabase (bukan dari JSON file — terlalu besar 9.6MB, crash browser)
 * User edit kamus lokal pakai VSCode, upload ke Supabase kalau sudah lengkap
 *
 * Fallback: kalau Supabase belum tersedia, return null (kamus check skip, semua kata dianggap OK)
 */
export async function loadKamusJawa(): Promise<KamusJawa | null> {
  try {
    const { isSupabaseAvailable } = await import('./supabase')
    if (!isSupabaseAvailable()) return null

    const { getSupabase } = await import('./supabase')
    const client = getSupabase()
    if (!client) return null

    // Load kamus dari Supabase (limit 10000 untuk performance)
    const { data, error } = await client
      .from('kamus')
      .select('ngoko, aksara, krama, arti, keterangan, sumber')
      .limit(10000)
      .order('ngoko', { ascending: true })

    if (error || !data || data.length === 0) {
      console.warn('[Kamus] Supabase load failed or empty:', error?.message)
      return null
    }

    // Map Supabase 'arti' → JSON 'id' (untuk konsisten dengan KamusEntry interface)
    const mappedWords = data.map((d: { ngoko: string; aksara: string; krama: string; arti: string; keterangan: string; sumber: string }) => ({
      ngoko: d.ngoko,
      aksara: d.aksara || '',
      krama: d.krama || '',
      id: d.arti || '',  // Supabase 'arti' → interface 'id'
      keterangan: d.keterangan || '',
      sumber: d.sumber || '',
    }))

    return {
      metadata: {
        version: 'supabase',
        source: 'Supabase PostgreSQL',
        entries: data.length,
        note: 'Kamus dari Supabase. User edit lokal, upload ke Supabase.',
      },
      words: mappedWords,
    }
  } catch (e) {
    console.warn('[Kamus] Load failed:', e)
    return null
  }
}

/**
 * Cek kata: apakah ada di kamus?
 * Case insensitive, strip punctuation
 * Support alias: ngoko field bisa "aku, inyong, nyong" → match per kata
 */
export function isWordInKamus(word: string, kamus: KamusJawa | null): boolean {
  if (!kamus) return true
  const cleanWord = word.toLowerCase().replace(/[^\wàáâãäåæçèéêëìíîïðñòóôõöøùúûüýþÿ]/g, '')
  if (!cleanWord) return true
  return kamus.words.some(entry => {
    // Split ngoko by koma untuk support alias
    const ngokoVariants = entry.ngoko.split(',').map(n => n.trim().toLowerCase())
    return ngokoVariants.includes(cleanWord)
  })
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
 * Suggest register untuk cue berdasarkan kata yang ada.
 * Simple: kalau ada kata dengan krama mapping → suggest krama
 * Kalau tidak ada krama mapping → suggest ngoko
 */
export function suggestRegister(text: string, kamus: KamusJawa | null): CueRegister {
  if (!kamus) return ''
  const words = text.toLowerCase().split(/\s+/)

  for (const word of words) {
    const cleanWord = word.replace(/[^\wàáâãäåæçèéêëìíîïðñòóôõöøùúûüýþÿ]/g, '')
    if (!cleanWord) continue
    // Cari entry yang ngoko-nya (dengan alias) cocok
    const entry = kamus.words.find(e => {
      const ngokoVariants = e.ngoko.split(',').map(n => n.trim().toLowerCase())
      return ngokoVariants.includes(cleanWord)
    })
    if (entry && entry.krama) {
      return 'krama'  // ada krama mapping → suggest krama
    }
  }
  return 'ngoko'
}

/**
 * Convert SRT text dari ngoko ke krama.
 * Pakai kamus: cari kata ngoko → ganti dengan krama.
 * Kalau krama kosong (belum ada mapping), biarkan apa adanya.
 */
export function convertRegister(
  text: string,
  _fromRegister: CueRegister,
  toRegister: CueRegister,
  kamus: KamusJawa | null,
): string {
  if (!kamus || !toRegister) return text
  if (toRegister !== 'krama' && toRegister !== 'krama_inggil') return text

  // Build lookup: ngoko word (dengan alias) → krama word (first variant)
  const lookup = new Map<string, string>()
  for (const entry of kamus.words) {
    if (!entry.krama) continue
    // Split ngoko by koma untuk alias
    const ngokoVariants = entry.ngoko.split(',').map(n => n.trim().toLowerCase())
    // Krama first variant (sebelum koma)
    const kramaFirst = entry.krama.split(',')[0].trim()
    for (const ngoko of ngokoVariants) {
      if (ngoko) lookup.set(ngoko, kramaFirst)
    }
  }

  if (lookup.size === 0) return text

  const words = text.split(/(\s+)/)
  const converted = words.map(w => {
    const cleanWord = w.toLowerCase().replace(/[^\wàáâãäåæçèéêëìíîïðñòóôõöøùúûüýþÿ]/g, '')
    if (!cleanWord) return w

    const replacement = lookup.get(cleanWord)
    if (replacement) {
      const isUpperCase = w[0] === w[0]?.toUpperCase() && w[0] !== w[0]?.toLowerCase()
      return isUpperCase ? replacement.charAt(0).toUpperCase() + replacement.slice(1) : replacement
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
