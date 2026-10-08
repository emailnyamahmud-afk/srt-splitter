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
  ngoko: string       // kata ngoko + alias (dipisah koma, mis. "aku, inyong, nyong"). KOSONG kalau entry ini krama/krama_inggil
  aksara: string      // aksara Jawa
  krama: string       // kata krama + alias (dipisah koma). KOSONG kalau entry ini ngoko
  krama_inggil: string  // kata krama inggil + alias. KOSONG kalau tidak ada (v5)
  id: string          // terjemahan Indonesia + alias (dipisah koma, mis. "saya, aku, gue, gua, ane"). Kosong = belum ada.
                      // Dipakai sebagai alias source lookup juga — kalau SRT source ada kata "saya",
                      // convert ke ngoko utama atau krama utama.
  keterangan: string  // definisi JAWA dari XML (membantu user isi id). JANGAN HAPUS
  register: string    // register asli dari Wiktionary: 'ngoko'|'krama'|'krama_inggil'|'kawi'|'umum' (v5)
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

    // Load kamus dari Supabase — prioritas: status='ready'/'clean' (user-approved) dulu,
    // lalu yang ada krama mapping (auto-filled). Limit tinggi supaya cukup untuk 5-10k entries
    // yang user isi + auto-fill dari Wiktionary.
    // Limit 50000 = cukup untuk 44.585 entries Wiktionary (kalau user upload semua).
    const { data, error } = await client
      .from('kamus')
      .select('ngoko, aksara, krama, krama_inggil, arti, keterangan, register, sumber')
      .limit(50000)
      .order('ngoko', { ascending: true })

    if (error || !data || data.length === 0) {
      console.warn('[Kamus] Supabase load failed or empty:', error?.message)
      return null
    }

    // Map Supabase 'arti' → JSON 'id' (untuk konsisten dengan KamusEntry interface)
    const mappedWords = data.map((d: { ngoko: string; aksara: string; krama: string; krama_inggil?: string; arti: string; keterangan: string; register?: string; sumber: string }) => ({
      ngoko: d.ngoko || '',
      aksara: d.aksara || '',
      krama: d.krama || '',
      krama_inggil: d.krama_inggil || '',  // v5 — kosong kalau kolom tidak ada (backward compat)
      id: d.arti || '',  // Supabase 'arti' → interface 'id'
      keterangan: d.keterangan || '',
      register: d.register || 'umum',  // v5 — default 'umum' kalau kolom tidak ada
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
 * Case insensitive, strip punctuation.
 * BIDIRECTIONAL: cek alias di field ngoko DAN krama (kalau ada).
 *   Mis. kamus: ngoko="aku, inyong, nyong", krama="kula, dalem"
 *   → "aku", "inyong", "nyong", "kula", "dalem" semua dianggap KNOWN.
 */
export function isWordInKamus(word: string, kamus: KamusJawa | null): boolean {
  if (!kamus) return true
  const cleanWord = word.toLowerCase().replace(/[^\wàáâãäåæçèéêëìíîïðñòóôõöøùúûüýþÿ]/g, '')
  if (!cleanWord) return true
  // Juga cek word as-is (untuk aksara Jawa yang case-sensitive, tidak perlu lowercase)
  return kamus.words.some(entry => {
    const ngokoVariants = entry.ngoko.split(',').map(n => n.trim().toLowerCase())
    if (ngokoVariants.includes(cleanWord)) return true
    if (entry.krama) {
      const kramaVariants = entry.krama.split(',').map(k => k.trim().toLowerCase())
      if (kramaVariants.includes(cleanWord)) return true
    }
    if (entry.krama_inggil) {
      const kiVariants = entry.krama_inggil.split(',').map(k => k.trim().toLowerCase())
      if (kiVariants.includes(cleanWord)) return true
    }
    if (entry.id) {
      const artiVariants = entry.id.split(',').map(a => a.trim().toLowerCase())
      if (artiVariants.includes(cleanWord)) return true
    }
    // Aksara Jawa juga jadi known words (case-sensitive, tidak lowercase)
    if (entry.aksara) {
      const aksaraVariants = entry.aksara.split(',').map(a => a.trim())
      if (aksaraVariants.includes(word) || aksaraVariants.some(a => a.toLowerCase() === cleanWord)) return true
    }
    return false
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
 * Hitung top N kata tak dikenal kamus (urut by frequency).
 * Untuk display di Editor SRT Jawa: user tahu kata mana yang sering muncul
 * tapi belum ada di kamus → prioritas add ke kamus.
 *
 * @param entries SRT entries
 * @param kamus Kamus object (dari loadKamusJawa, in-memory)
 * @param topN Default 100
 * @returns Array of {word, freq, cueIndices: number[]} — urut by freq desc
 */
export function getTopUnknownWords(
  entries: { textLines: string[] }[],
  kamus: KamusJawa | null,
  topN: number = 100,
): { word: string; freq: number; cueIndices: number[] }[] {
  if (!kamus) return []

  const freqMap = new Map<string, { freq: number; cueIndices: Set<number> }>()

  for (let i = 0; i < entries.length; i++) {
    const text = entries[i].textLines.join(' ')
    const words = text.split(/\s+/)
    for (const word of words) {
      const cleanWord = word.toLowerCase().replace(/[^\wàáâãäåæçèéêëìíîïðñòóôõöøùúûüýþÿ]/g, '')
      if (!cleanWord) continue
      // Skip kalau dikenal kamus (cek kata asli juga untuk aksara)
      if (isWordInKamus(word, kamus) || isWordInKamus(cleanWord, kamus)) continue
      // Tambah ke freqMap
      if (!freqMap.has(cleanWord)) {
        freqMap.set(cleanWord, { freq: 0, cueIndices: new Set() })
      }
      const entry = freqMap.get(cleanWord)!
      entry.freq++
      entry.cueIndices.add(i)
    }
  }

  // Sort by freq desc, lalu alphabet
  const sorted = Array.from(freqMap.entries())
    .map(([word, { freq, cueIndices }]) => ({
      word,
      freq,
      cueIndices: Array.from(cueIndices).sort((a, b) => a - b),
    }))
    .sort((a, b) => {
      if (b.freq !== a.freq) return b.freq - a.freq
      return a.word.localeCompare(b.word)
    })

  return sorted.slice(0, topN)
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
    // BIDIRECTIONAL: cari entry yang ngoko-nya, krama-nya, krama_inggil-nya, arti-nya, ATAU aksara-nya cocok
    const entry = kamus.words.find(e => {
      const ngokoVariants = e.ngoko.split(',').map(n => n.trim().toLowerCase())
      if (ngokoVariants.includes(cleanWord)) return true
      if (e.krama) {
        const kramaVariants = e.krama.split(',').map(k => k.trim().toLowerCase())
        if (kramaVariants.includes(cleanWord)) return true
      }
      if (e.krama_inggil) {
        const kiVariants = e.krama_inggil.split(',').map(k => k.trim().toLowerCase())
        if (kiVariants.includes(cleanWord)) return true
      }
      if (e.id) {
        const artiVariants = e.id.split(',').map(a => a.trim().toLowerCase())
        if (artiVariants.includes(cleanWord)) return true
      }
      // Aksara Jawa
      if (e.aksara) {
        const aksaraVariants = e.aksara.split(',').map(a => a.trim())
        if (aksaraVariants.includes(word) || aksaraVariants.some(a => a.toLowerCase() === cleanWord)) return true
      }
      return false
    })
    if (entry) {
      // Suggest register berdasarkan field yang ada:
      // - Kalau ada krama_inggil → suggest krama_inggil (paling sopan)
      // - Kalau ada krama → suggest krama
      // - Kalau ngoko saja → suggest ngoko
      if (entry.krama_inggil) return 'krama_inggil'
      if (entry.krama) return 'krama'
      return 'ngoko'
    }
  }
  return 'ngoko'
}

/**
 * Convert SRT text dari register apa pun ke target register (ngoko atau krama).
 * BIDIRECTIONAL: lookup source word di alias ngoko + alias krama.
 *   Source "aku" / "inyong" / "nyong" / "kula" / "dalem" semua dikenali.
 * Kalau convert ke krama → return krama pertama (utama).
 * Kalau convert ke ngoko → return ngoko pertama (utama).
 * Kalau source word tidak ada di kamus → biarkan apa adanya.
 */
export function convertRegister(
  text: string,
  _fromRegister: CueRegister,
  toRegister: CueRegister,
  kamus: KamusJawa | null,
): string {
  if (!kamus || !toRegister) return text
  if (toRegister !== 'ngoko' && toRegister !== 'krama' && toRegister !== 'krama_inggil') return text

  // Build lookup BIDIRECTIONAL: semua alias (ngoko + krama + krama_inggil + arti + aksara) → target word utama
  // Mis. kamus: ngoko="Nyong, Aku, Inyong", krama="Kula, Dalem", arti="Saya, Aku, Gue, Ane", aksara="ꦲꦏꦸ, ꦲꦶꦚꦺꦴꦁ"
  //   toRegister=krama → {nyong→kula, aku→kula, inyong→kula, kula→kula, dalem→kula,
  //                        saya→kula, gue→kula, gua→kula, ane→kula,
  //                        ꦲꦏꦸ→kula, ꦲꦶꦚꦺꦴꦁ→kula} (semua source termasuk aksara → krama utama)
  //
  // Catatan: arti (Indonesia) + aksara Jawa juga jadi source alias.
  // Kalau SRT source = "saya" → convert ke ngoko → "nyong", ke krama → "kula".
  // Kalau SRT source = "ꦲꦏꦸ" (aksara) → convert ke ngoko → "aku", ke krama → "kula".
  // Kalau SRT source = "ꦏꦸꦭ" (aksara kula) → convert ke ngoko → "aku".
  const lookup = new Map<string, string>()
  for (const entry of kamus.words) {
    const ngokoVariants = entry.ngoko.split(',').map(n => n.trim().toLowerCase()).filter(Boolean)
    const kramaVariants = entry.krama
      ? entry.krama.split(',').map(k => k.trim().toLowerCase()).filter(Boolean)
      : []
    const kramaIngilVariants = entry.krama_inggil
      ? entry.krama_inggil.split(',').map(k => k.trim().toLowerCase()).filter(Boolean)
      : []
    const artiVariants = entry.id
      ? entry.id.split(',').map(a => a.trim().toLowerCase()).filter(Boolean)
      : []
    // Aksara Jawa juga jadi source alias (split per koma, jangan lowercase — aksara case-sensitive)
    const aksaraVariants = entry.aksara
      ? entry.aksara.split(',').map(a => a.trim()).filter(Boolean)
      : []
    const allVariants = [...ngokoVariants, ...kramaVariants, ...kramaIngilVariants, ...artiVariants, ...aksaraVariants]

    // Target word utama sesuai register tujuan
    let targetWord = ''
    if (toRegister === 'ngoko') {
      targetWord = ngokoVariants[0] || ''
    } else if (toRegister === 'krama') {
      // Target = krama pertama. Kalau entry tidak punya krama, skip (tidak bisa convert ke krama)
      targetWord = kramaVariants[0] || ''
    } else if (toRegister === 'krama_inggil') {
      // Target = krama_inggil pertama. Kalau tidak ada, fallback ke krama pertama.
      targetWord = kramaIngilVariants[0] || kramaVariants[0] || ''
    }
    if (!targetWord) continue

    // Mapping: semua alias (ngoko + krama + krama_inggil + arti) → target word utama
    for (const variant of allVariants) {
      lookup.set(variant, targetWord)
    }
  }

  if (lookup.size === 0) return text

  const words = text.split(/(\s+)/)
  const converted = words.map(w => {
    const cleanWord = w.toLowerCase().replace(/[^\wàáâãäåæçèéêëìíîïðñòóôõöøùúûüýþÿ]/g, '')
    if (!cleanWord) return w

    const replacement = lookup.get(cleanWord)
    if (replacement) {
      // Preserve capitalization
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
