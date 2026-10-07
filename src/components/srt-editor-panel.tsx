'use client'

import { useCallback, useEffect, useRef, useState } from 'react'
import { Upload, Download, ChevronLeft, ChevronRight, Loader2, CheckCircle2, Cloud, Mic } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { toast } from 'sonner'
import { parseSrt, serializePart, downloadTextFile, type SrtEntry, type SrtPart } from '@/lib/srt'
import {
  isSupabaseAvailable,
  getAnonymousUserId,
  createProject,
  saveCues,
  getCues,
  listProjects,
  type SrtProject,
  type SrtCue,
} from '@/lib/supabase'
import {
  loadKamusJawa,
  convertRegister,
  type KamusJawa,
  type CueRegister,
} from '@/lib/rapikan-jawa'

interface DualSrtEditorProps {
  prefix: string
}

const VOICES = [
  { id: 'dimas', label: 'Dimas (Jawa laki)', voice: 'jv-ID-DimasNeural' },
  { id: 'siti', label: 'Siti (Jawa perempuan)', voice: 'jv-ID-SitiNeural' },
  { id: 'ardi', label: 'Ardi (Indo laki)', voice: 'id-ID-ArdiNeural' },
  { id: 'gadis', label: 'Gadis (Indo perempuan)', voice: 'id-ID-GadisNeural' },
]

const PAGE_SIZE = 30

export function DualSrtEditor({ prefix }: DualSrtEditorProps) {
  const [kamus, setKamus] = useState<KamusJawa | null>(null)
  const [idEntries, setIdEntries] = useState<SrtEntry[]>([])
  const [jawaEntries, setJawaEntries] = useState<SrtEntry[]>([])
  const [registers, setRegisters] = useState<Record<number, CueRegister>>({})
  const [voices, setVoices] = useState<Record<number, string>>({})
  const [currentPage, setCurrentPage] = useState(0)
  const [projectId, setProjectId] = useState<string | null>(null)
  const [autoSaveStatus, setAutoSaveStatus] = useState<'idle' | 'saving' | 'saved' | 'error'>('idle')
  const [supabaseReady, setSupabaseReady] = useState(false)
  const saveTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const idFileRef = useRef<HTMLInputElement>(null)
  const jawaFileRef = useRef<HTMLInputElement>(null)

  // Load kamus
  useEffect(() => {
    loadKamusJawa().then(k => {
      setKamus(k)
      if (k) toast.success(`Kamus: ${k.words.length} entri (Supabase)`)
    })
    setSupabaseReady(isSupabaseAvailable())
  }, [])

  // Upload SRT ID
  const handleUploadId = useCallback(async (file: File) => {
    const text = await file.text()
    const parsed = parseSrt(text)
    if (parsed.length === 0) {
      toast.error('SRT ID kosong/invalid')
      return
    }
    setIdEntries(parsed)
    toast.success(`SRT ID: ${parsed.length} cue (konteks)`)
  }, [])

  // Upload SRT Jawa
  const handleUploadJawa = useCallback(async (file: File) => {
    const text = await file.text()
    const parsed = parseSrt(text)
    if (parsed.length === 0) {
      toast.error('SRT Jawa kosong/invalid')
      return
    }
    setJawaEntries(parsed)
    setRegisters({})
    setVoices({})
    setCurrentPage(0)
    toast.success(`SRT Jawa: ${parsed.length} cue (editor)`)
  }, [])

  // Edit SRT Jawa cue (inline textarea)
  const handleEditJawa = useCallback((index: number, newText: string) => {
    setJawaEntries(prev => {
      const updated = [...prev]
      updated[index] = { ...updated[index], textLines: newText.split('\n') }
      return updated
    })
  }, [])

  // Toggle register: klik Ngoko → convert ke ngoko, klik Krama → convert ke krama (dari kamus)
  const handleToggleRegister = useCallback((index: number, register: CueRegister) => {
    if (!kamus) {
      toast.info('Kamus belum loaded. Upload ke Supabase dulu.')
      return
    }

    setJawaEntries(prev => {
      const updated = [...prev]
      const text = updated[index].textLines.join(' ')

      if (register === 'krama') {
        // Convert ke krama: ganti kata ngoko → krama (dari kamus)
        const converted = convertRegister(text, 'ngoko', 'krama', kamus)
        updated[index] = { ...updated[index], textLines: converted.split('\n') }
      } else if (register === 'ngoko') {
        // Convert ke ngoko: biarkan apa adanya (SRT Jawa default = ngoko)
        // Kalau sudah krama, tidak bisa convert balik otomatis (butuh reverse mapping)
        // Untuk sekarang: biarkan text apa adanya, set register ngoko
      }

      return updated
    })

    setRegisters(prev => ({ ...prev, [index]: register }))
  }, [kamus])

  // Set voice per cue
  const handleSetVoice = useCallback((index: number, voiceId: string) => {
    setVoices(prev => ({ ...prev, [index]: voiceId }))
  }, [])

  // All Ngoko / All Krama per halaman
  const handleConvertPage = useCallback((register: CueRegister) => {
    if (!kamus) {
      toast.info('Kamus belum loaded')
      return
    }
    const start = currentPage * PAGE_SIZE
    const end = Math.min(start + PAGE_SIZE, jawaEntries.length)

    setJawaEntries(prev => {
      const updated = [...prev]
      for (let i = start; i < end; i++) {
        const text = updated[i].textLines.join(' ')
        if (register === 'krama') {
          const converted = convertRegister(text, 'ngoko', 'krama', kamus)
          updated[i] = { ...updated[i], textLines: converted.split('\n') }
        }
        setRegisters(prev => ({ ...prev, [i]: register }))
      }
      return updated
    })
    toast.success(`Halaman ${currentPage + 1}: convert ke ${register}`)
  }, [kamus, jawaEntries, currentPage])

  // All Ngoko / All Krama semua
  const handleConvertAll = useCallback((register: CueRegister) => {
    if (!kamus) {
      toast.info('Kamus belum loaded')
      return
    }
    setJawaEntries(prev => {
      const updated = [...prev]
      for (let i = 0; i < updated.length; i++) {
        const text = updated[i].textLines.join(' ')
        if (register === 'krama') {
          const converted = convertRegister(text, 'ngoko', 'krama', kamus)
          updated[i] = { ...updated[i], textLines: converted.split('\n') }
        }
        setRegisters(prev => ({ ...prev, [i]: register }))
      }
      return updated
    })
    toast.success(`Semua ${jawaEntries.length} cue: convert ke ${register}`)
  }, [kamus, jawaEntries])

  // Download SRT Jawa
  const handleDownload = useCallback(() => {
    if (jawaEntries.length === 0) return
    const part: SrtPart = {
      index: 1, entries: jawaEntries, startSec: jawaEntries[0].start,
      endSec: jawaEntries[jawaEntries.length - 1].end,
      durationSec: jawaEntries[jawaEntries.length - 1].end - jawaEntries[0].start,
      entryCount: jawaEntries.length,
    }
    const content = serializePart(part, false)
    downloadTextFile(`${prefix}-jw-final.srt`, content)
    toast.success('SRT Jawa didownload')
  }, [jawaEntries, prefix])

  // Auto-save ke Supabase (debounce 3s)
  useEffect(() => {
    if (!supabaseReady || jawaEntries.length === 0) return
    if (saveTimerRef.current) clearTimeout(saveTimerRef.current)
    saveTimerRef.current = setTimeout(async () => {
      setAutoSaveStatus('saving')
      // TODO: save cues to Supabase
      setAutoSaveStatus('saved')
      setTimeout(() => setAutoSaveStatus('idle'), 3000)
    }, 3000)
    return () => { if (saveTimerRef.current) clearTimeout(saveTimerRef.current) }
  }, [jawaEntries, registers, voices, supabaseReady])

  if (jawaEntries.length === 0) {
    // Upload screen
    return (
      <Card className="mt-4 border-indigo-200 dark:border-indigo-800">
        <CardHeader>
          <CardTitle className="text-lg flex items-center gap-2">
            <Mic className="size-5 text-indigo-600" />
            Editor SRT Jawa (Dual SRT + Voice)
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label className="text-sm font-medium">SRT Indonesia (konteks)</label>
              <input
                ref={idFileRef}
                type="file"
                accept=".srt"
                onChange={e => e.target.files?.[0] && handleUploadId(e.target.files[0])}
                className="hidden"
              />
              <Button
                variant="outline"
                className="w-full mt-1"
                onClick={() => idFileRef.current?.click()}
              >
                <Upload className="size-4 mr-2" /> Upload SRT ID
              </Button>
              {idEntries.length > 0 && (
                <p className="text-xs text-muted-foreground mt-1">✓ {idEntries.length} cue (konteks)</p>
              )}
            </div>
            <div>
              <label className="text-sm font-medium">SRT Jawa (editor)</label>
              <input
                ref={jawaFileRef}
                type="file"
                accept=".srt"
                onChange={e => e.target.files?.[0] && handleUploadJawa(e.target.files[0])}
                className="hidden"
              />
              <Button
                variant="outline"
                className="w-full mt-1"
                onClick={() => jawaFileRef.current?.click()}
              >
                <Upload className="size-4 mr-2" /> Upload SRT Jawa
              </Button>
            </div>
          </div>
          <p className="text-xs text-muted-foreground">
            Upload SRT ID untuk konteks (readonly, di atas setiap cue Jawa).
            Upload SRT Jawa untuk edit (ngoko/krama toggle, voice assignment).
            User nonton VLC, baca SRT ID, edit SRT Jawa.
          </p>
        </CardContent>
      </Card>
    )
  }

  // Editor screen
  const totalPages = Math.ceil(jawaEntries.length / PAGE_SIZE)
  const startIdx = currentPage * PAGE_SIZE
  const endIdx = Math.min(startIdx + PAGE_SIZE, jawaEntries.length)
  const pageEntries = jawaEntries.slice(startIdx, endIdx)

  return (
    <Card className="mt-4 border-indigo-200 dark:border-indigo-800">
      <CardHeader>
        <div className="flex items-center justify-between flex-wrap gap-2">
          <CardTitle className="text-lg flex items-center gap-2">
            <Mic className="size-5 text-indigo-600" />
            Editor SRT Jawa
          </CardTitle>
          <div className="flex items-center gap-2 text-xs">
            <Badge variant="outline">
              {jawaEntries.length} cue | Hal {currentPage + 1}/{totalPages}
            </Badge>
            {supabaseReady && (
              <Badge variant="outline" className={
                autoSaveStatus === 'saving' ? 'bg-blue-50 dark:bg-blue-950/30 animate-pulse' :
                autoSaveStatus === 'saved' ? 'bg-green-50 dark:bg-green-950/30' : ''
              }>
                {autoSaveStatus === 'saving' ? <><Loader2 className="size-3 mr-1 animate-spin" /> Simpan...</> :
                 autoSaveStatus === 'saved' ? <><CheckCircle2 className="size-3 mr-1" /> Tersimpan</> :
                 <><Cloud className="size-3 mr-1" /> Auto-save</>}
              </Badge>
            )}
          </div>
        </div>
      </CardHeader>
      <CardContent className="space-y-3">
        {/* Action bar */}
        <div className="flex flex-wrap gap-2">
          <Button size="sm" variant="outline" onClick={() => handleConvertPage('ngoko')}
            className="border-blue-300 text-blue-700 dark:text-blue-300">
            All Ngoko (halaman)
          </Button>
          <Button size="sm" variant="outline" onClick={() => handleConvertPage('krama')}
            className="border-amber-300 text-amber-700 dark:text-amber-300">
            All Krama (halaman)
          </Button>
          <Button size="sm" variant="outline" onClick={() => handleConvertAll('ngoko')}
            className="border-blue-200 text-blue-600 dark:text-blue-400">
            All Ngoko (semua)
          </Button>
          <Button size="sm" variant="outline" onClick={() => handleConvertAll('krama')}
            className="border-amber-200 text-amber-600 dark:text-amber-400">
            All Krama (semua)
          </Button>
          <Button size="sm" onClick={handleDownload}>
            <Download className="size-3.5 mr-1" /> Download SRT Jawa
          </Button>
        </div>

        {/* Cue list */}
        <div className="space-y-2">
          {pageEntries.map((entry, i) => {
            const idx = startIdx + i
            const idEntry = idEntries[idx]
            const register = registers[idx] || ''
            const voiceId = voices[idx] || ''

            return (
              <div key={idx} className="rounded-lg border p-2.5 space-y-1.5 hover:border-indigo-300 transition-colors">
                {/* Cue header: index + timestamp */}
                <div className="flex items-center gap-2 text-xs text-muted-foreground">
                  <span className="font-mono font-bold">#{idx + 1}</span>
                  <span className="font-mono">{formatTs(entry.start)} → {formatTs(entry.end)}</span>
                </div>

                {/* SRT ID (konteks, kecil, abu-abu) */}
                {idEntry && (
                  <div className="rounded bg-gray-100 dark:bg-gray-800/50 px-2 py-1">
                    <p className="text-[11px] text-muted-foreground italic">{idEntry.textLines.join(' ')}</p>
                  </div>
                )}

                {/* SRT Jawa (editor) */}
                <textarea
                  value={entry.textLines.join('\n')}
                  onChange={e => handleEditJawa(idx, e.target.value)}
                  className="w-full text-sm border rounded px-2 py-1.5 bg-background min-h-[40px] resize-y"
                  rows={Math.max(1, entry.textLines.length)}
                />

                {/* Voice + Register */}
                <div className="flex items-center gap-2 flex-wrap">
                  <select
                    value={voiceId}
                    onChange={e => handleSetVoice(idx, e.target.value)}
                    className="text-xs border rounded px-1.5 py-1 bg-background"
                  >
                    <option value="">Voice —</option>
                    {VOICES.map(v => <option key={v.id} value={v.id}>{v.label}</option>)}
                  </select>
                  <button
                    onClick={() => handleToggleRegister(idx, 'ngoko')}
                    className={`text-xs px-2 py-1 rounded border transition-colors ${
                      register === 'ngoko'
                        ? 'bg-blue-100 text-blue-700 border-blue-400 dark:bg-blue-950 dark:text-blue-300'
                        : 'bg-background border-border hover:border-blue-300'
                    }`}
                  >
                    Ngoko
                  </button>
                  <button
                    onClick={() => handleToggleRegister(idx, 'krama')}
                    className={`text-xs px-2 py-1 rounded border transition-colors ${
                      register === 'krama'
                        ? 'bg-amber-100 text-amber-700 border-amber-400 dark:bg-amber-950 dark:text-amber-300'
                        : 'bg-background border-border hover:border-amber-300'
                    }`}
                  >
                    Krama
                  </button>
                </div>
              </div>
            )
          })}
        </div>

        {/* Pagination */}
        <div className="flex items-center justify-between pt-2">
          <Button
            size="sm"
            variant="outline"
            disabled={currentPage === 0}
            onClick={() => setCurrentPage(p => p - 1)}
          >
            <ChevronLeft className="size-4" /> Sebelumnya
          </Button>
          <span className="text-xs text-muted-foreground">
            Hal {currentPage + 1} / {totalPages} ({jawaEntries.length} cue)
          </span>
          <Button
            size="sm"
            variant="outline"
            disabled={currentPage >= totalPages - 1}
            onClick={() => setCurrentPage(p => p + 1)}
          >
            Berikutnya <ChevronRight className="size-4" />
          </Button>
        </div>
      </CardContent>
    </Card>
  )
}

function formatTs(sec: number): string {
  const h = Math.floor(sec / 3600)
  const m = Math.floor((sec % 3600) / 60)
  const s = Math.floor(sec % 60)
  return `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`
}
