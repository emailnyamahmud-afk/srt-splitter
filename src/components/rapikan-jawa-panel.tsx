'use client'

import { useCallback, useEffect, useRef, useState } from 'react'
import { FileText, Download, Eraser, BookOpen, CheckCircle2, AlertTriangle, Loader2, Save, Cloud } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Label } from '@/components/ui/label'
import { Badge } from '@/components/ui/badge'
import { ScrollArea } from '@/components/ui/scroll-area'
import { toast } from 'sonner'
import { parseSrt, serializePart, downloadTextFile, type SrtEntry, type SrtPart } from '@/lib/srt'
import {
  loadKamusJawa,
  checkUnknownWords,
  stripAksenFromEntries,
  suggestRegister,
  getRegisterLabel,
  getRegisterColor,
  convertEntriesRegister,
  type KamusJawa,
  type CueRegister,
  type RapikanResult,
} from '@/lib/rapikan-jawa'
import {
  isSupabaseAvailable,
  getAnonymousUserId,
  createProject,
  listProjects,
  saveCues,
  getCues,
  type SrtProject,
  type SrtCue,
} from '@/lib/supabase'

interface RapikanJawaPanelProps {
  entries: SrtEntry[]
  onUpdated: (entries: SrtEntry[]) => void
  prefix: string
}

export function RapikanJawaPanel({ entries, onUpdated, prefix }: RapikanJawaPanelProps) {
  const [kamus, setKamus] = useState<KamusJawa | null>(null)
  const [loadingKamus, setLoadingKamus] = useState(true)
  const [rapikanResult, setRapikanResult] = useState<RapikanResult | null>(null)
  const [cueRegisters, setCueRegisters] = useState<Record<number, CueRegister>>({})
  const [editingIndex, setEditingIndex] = useState<number | null>(null)
  const [editedText, setEditedText] = useState<string>('')
  const [showUnknownWords, setShowUnknownWords] = useState(false)
  const scrollRef = useRef<HTMLDivElement>(null)

  // Supabase state
  const [supabaseReady, setSupabaseReady] = useState(false)
  const [currentProjectId, setCurrentProjectId] = useState<string | null>(null)
  const [projects, setProjects] = useState<SrtProject[]>([])
  const [autoSaveStatus, setAutoSaveStatus] = useState<'idle' | 'saving' | 'saved' | 'error'>('idle')
  const saveTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const cueIdMapRef = useRef<Record<number, string>>({}) // cue_index → cue UUID

  // Load kamus on mount
  useEffect(() => {
    loadKamusJawa().then(k => {
      setKamus(k)
      setLoadingKamus(false)
      if (k) {
        toast.success(`Kamus Jawa loaded: ${k.words.length} entri`)
      } else {
        toast.error('Gagal load kamus Jawa')
      }
    })
    // Check Supabase availability
    setSupabaseReady(isSupabaseAvailable())
  }, [])

  // Load projects list when Supabase is ready
  useEffect(() => {
    if (!supabaseReady) return
    listProjects().then(projs => {
      setProjects(projs)
    })
  }, [supabaseReady])

  // Auto-save: debounce 2 detik setelah entries atau registers berubah
  const autoSave = useCallback(async () => {
    if (!supabaseReady || entries.length === 0) return

    // Kalau belum ada project, create baru
    let projectId = currentProjectId
    if (!projectId) {
      setAutoSaveStatus('saving')
      const originalSrt = entries.map((e, i) =>
        `${i + 1}\n${Math.floor(e.start / 3600)}:${Math.floor((e.start % 3600) / 60)}:${Math.floor(e.start % 60)},000 --> ${Math.floor(e.end / 3600)}:${Math.floor((e.end % 3600) / 60)}:${Math.floor(e.end % 60)},000\n${e.textLines.join('\n')}\n`
      ).join('\n')
      const proj = await createProject(
        `${prefix}-jawa`,
        'jawa',
        originalSrt,
        entries.length,
      )
      if (proj) {
        projectId = proj.id
        setCurrentProjectId(proj.id)
        setProjects(prev => [proj, ...prev])
      } else {
        setAutoSaveStatus('error')
        return
      }
    }

    // Save cues
    setAutoSaveStatus('saving')
    const cuesToSave = entries.map((e, i) => ({
      cue_index: i,
      start_sec: e.start,
      end_sec: e.end,
      text: e.textLines.join('\n'),
      register: cueRegisters[i] || '',
    }))
    const ok = await saveCues(projectId!, cuesToSave)
    if (ok) {
      setAutoSaveStatus('saved')
      // Auto-clear "saved" badge after 3 seconds
      setTimeout(() => setAutoSaveStatus('idle'), 3000)
    } else {
      setAutoSaveStatus('error')
    }
  }, [supabaseReady, entries, currentProjectId, cueRegisters, prefix])

  // Debounce auto-save (2 detik setelah perubahan)
  useEffect(() => {
    if (!supabaseReady || entries.length === 0) return
    if (saveTimerRef.current) clearTimeout(saveTimerRef.current)
    saveTimerRef.current = setTimeout(() => {
      autoSave()
    }, 2000)
    return () => {
      if (saveTimerRef.current) clearTimeout(saveTimerRef.current)
    }
  }, [entries, cueRegisters, supabaseReady, autoSave])

  // Check unknown words when entries change
  const runCheck = useCallback(() => {
    if (entries.length === 0 || !kamus) return
    const result = checkUnknownWords(entries, kamus)
    setRapikanResult(result)
  }, [entries, kamus])

  useEffect(() => {
    if (kamus && entries.length > 0) {
      runCheck()
    }
  }, [kamus, entries, runCheck])

  // Strip aksén from all entries
  const handleStripAksen = useCallback(() => {
    if (entries.length === 0) return
    const newEntries = entries.map(e => ({
      ...e,
      textLines: [...e.textLines],
    }))
    const count = stripAksenFromEntries(newEntries)
    onUpdated(newEntries)
    if (count > 0) {
      toast.success(`${count} aksén Jawa dihapus (é→e, è→e, ê→e)`)
    } else {
      toast.info('Tidak ada aksén Jawa yang perlu dihapus')
    }
    runCheck()
  }, [entries, onUpdated, runCheck])

  // Edit cue inline
  const startEdit = useCallback((index: number) => {
    setEditingIndex(index)
    setEditedText(entries[index].textLines.join('\n'))
  }, [entries])

  const saveEdit = useCallback(() => {
    if (editingIndex === null) return
    const newEntries = [...entries]
    newEntries[editingIndex] = {
      ...newEntries[editingIndex],
      textLines: editedText.split('\n'),
    }
    onUpdated(newEntries)
    setEditingIndex(null)
    toast.success(`Cue ${editingIndex + 1} diperbarui`)
    runCheck()
  }, [editingIndex, editedText, entries, onUpdated, runCheck])

  const cancelEdit = useCallback(() => {
    setEditingIndex(null)
    setEditedText('')
  }, [])

  // Toggle register per cue
  const toggleRegister = useCallback((index: number, register: CueRegister) => {
    setCueRegisters(prev => ({
      ...prev,
      [index]: prev[index] === register ? '' : register,
    }))
  }, [])

  // Auto-suggest registers for all cues
  const autoSuggestRegisters = useCallback(() => {
    if (!kamus || entries.length === 0) return
    const newRegisters: Record<number, CueRegister> = {}
    for (let i = 0; i < entries.length; i++) {
      const text = entries[i].textLines.join(' ')
      const suggested = suggestRegister(text, kamus)
      if (suggested) newRegisters[i] = suggested
    }
    setCueRegisters(newRegisters)
    toast.success(`Auto-suggest: ${Object.keys(newRegisters).length} cues detected`)
  }, [entries, kamus])

  // Convert all entries to specific register
  const handleConvertRegister = useCallback((toRegister: CueRegister) => {
    if (entries.length === 0 || !kamus) return
    const newEntries = entries.map(e => ({
      ...e,
      textLines: [...e.textLines],
    }))
    const count = convertEntriesRegister(newEntries, 'ngoko', toRegister, kamus)
    onUpdated(newEntries)
    // Set all registers to target
    const newRegisters: Record<number, CueRegister> = {}
    for (let i = 0; i < entries.length; i++) {
      newRegisters[i] = toRegister
    }
    setCueRegisters(newRegisters)
    if (count > 0) {
      toast.success(`${count} cue dikonversi ke ${getRegisterLabel(toRegister)}`)
    } else {
      toast.info('Tidak ada kata yang bisa dikonversi (mungkin kamus belum lengkap)')
    }
    runCheck()
  }, [entries, kamus, onUpdated, runCheck])

  // Download SRT rapi
  const handleDownload = useCallback(() => {
    if (entries.length === 0) return
    const part: SrtPart = {
      index: 1,
      entries,
      startSec: entries[0].start,
      endSec: entries[entries.length - 1].end,
      durationSec: entries[entries.length - 1].end - entries[0].start,
      entryCount: entries.length,
    }
    const content = serializePart(part, false)
    downloadTextFile(`${prefix}-jw-rapi.srt`, content)
    toast.success('SRT Jawa rapi didownload')
  }, [entries, prefix])

  if (entries.length === 0) return null

  return (
    <Card className="mt-4 border-amber-200 dark:border-amber-800">
      <CardHeader>
        <CardTitle className="text-lg flex items-center gap-2">
          <BookOpen className="size-5 text-amber-600" />
          Rapikan SRT Jawa
        </CardTitle>
        <CardDescription>
          Edit SRT Jawa manual + toggle ngoko/krama per cue + kamus check
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* Kamus + Supabase status */}
        <div className="flex flex-wrap items-center gap-2 text-xs">
          {loadingKamus ? (
            <><Loader2 className="size-3.5 animate-spin" /> Loading kamus...</>
          ) : kamus ? (
            <Badge variant="outline" className="bg-amber-50 dark:bg-amber-950/30">
              <CheckCircle2 className="size-3 mr-1" /> Kamus: {kamus.words.length} entri
            </Badge>
          ) : (
            <Badge variant="outline" className="bg-red-50 dark:bg-red-950/30">
              <AlertTriangle className="size-3 mr-1" /> Kamus tidak loaded
            </Badge>
          )}
          {rapikanResult && (
            <>
              <Badge variant="outline" className="bg-green-50 dark:bg-green-950/30">
                ✓ {rapikanResult.knownWords} kata dikenal
              </Badge>
              {rapikanResult.unknownWords > 0 && (
                <Badge variant="outline" className="bg-red-50 dark:bg-red-950/30 cursor-pointer"
                  onClick={() => setShowUnknownWords(!showUnknownWords)}>
                  <AlertTriangle className="size-3 mr-1" /> {rapikanResult.unknownWords} kata asing
                </Badge>
              )}
            </>
          )}
          {/* Supabase auto-save status */}
          {supabaseReady ? (
            <Badge variant="outline" className={
              autoSaveStatus === 'saving' ? 'bg-blue-50 dark:bg-blue-950/30 animate-pulse' :
              autoSaveStatus === 'saved' ? 'bg-green-50 dark:bg-green-950/30' :
              autoSaveStatus === 'error' ? 'bg-red-50 dark:bg-red-950/30' :
              'bg-gray-50 dark:bg-gray-900/30'
            }>
              {autoSaveStatus === 'saving' ? <><Loader2 className="size-3 mr-1 animate-spin" /> Menyimpan...</> :
               autoSaveStatus === 'saved' ? <><CheckCircle2 className="size-3 mr-1" /> Tersimpan</> :
               autoSaveStatus === 'error' ? <><AlertTriangle className="size-3 mr-1" /> Error simpan</> :
               <><Cloud className="size-3 mr-1" /> Auto-save siap</>}
            </Badge>
          ) : (
            <Badge variant="outline" className="bg-gray-50 dark:bg-gray-900/30 text-muted-foreground">
              <Cloud className="size-3 mr-1 opacity-50" /> Supabase belum set (localStorage)
            </Badge>
          )}
        </div>

        {/* Action buttons */}
        <div className="flex flex-wrap gap-2">
          <Button size="sm" variant="outline" onClick={handleStripAksen}>
            <Eraser className="size-3.5 mr-1" /> Hapus Aksén (é→e)
          </Button>
          <Button size="sm" variant="outline" onClick={autoSuggestRegisters} disabled={!kamus}>
            <CheckCircle2 className="size-3.5 mr-1" /> Auto-suggest Register
          </Button>
          <Button size="sm" sizeVariant="sm" variant="outline" onClick={() => handleConvertRegister('ngoko')} disabled={!kamus}
            className="border-blue-300 text-blue-700 dark:text-blue-300">
            All Ngoko
          </Button>
          <Button size="sm" variant="outline" onClick={() => handleConvertRegister('krama')} disabled={!kamus}
            className="border-amber-300 text-amber-700 dark:text-amber-300">
            All Krama
          </Button>
          <Button size="sm" variant="outline" onClick={() => handleConvertRegister('krama_inggil')} disabled={!kamus}
            className="border-purple-300 text-purple-700 dark:text-purple-300">
            All Krama Inggil
          </Button>
          <Button size="sm" onClick={handleDownload}>
            <Download className="size-3.5 mr-1" /> Download SRT Rapi
          </Button>
        </div>

        {/* Unknown words report */}
        {showUnknownWords && rapikanResult && rapikanResult.unknownWordsList.length > 0 && (
          <div className="rounded-md border border-red-200 dark:border-red-800 p-3 bg-red-50/30 dark:bg-red-950/10">
            <p className="text-xs font-medium text-red-700 dark:text-red-400 mb-2">
              Kata tidak dikenal di kamus ({rapikanResult.unknownWords} kata):
            </p>
            <ScrollArea className="h-32">
              <div className="space-y-1 text-xs">
                {rapikanResult.unknownWordsList.slice(0, 100).map((w, i) => (
                  <div key={i} className="flex gap-2">
                    <span className="font-mono font-bold text-red-600 dark:text-red-400">{w.word}</span>
                    <span className="text-muted-foreground">— cue {w.cueIndex + 1}: "{w.context}"</span>
                  </div>
                ))}
                {rapikanResult.unknownWordsList.length > 100 && (
                  <p className="text-muted-foreground italic">
                    ...dan {rapikanResult.unknownWordsList.length - 100} lainnya
                  </p>
                )}
              </div>
            </ScrollArea>
          </div>
        )}

        {/* SRT Editor */}
        <div className="rounded-md border p-3 space-y-2 max-h-[500px] overflow-y-auto">
          {entries.map((entry, i) => {
            const register = cueRegisters[i] || ''
            const suggested = kamus ? suggestRegister(entry.textLines.join(' '), kamus) : ''
            const isEditing = editingIndex === i
            const text = entry.textLines.join(' ')
            // Highlight unknown words
            const words = text.split(' ')
            const highlightedText = words.map((word, wi) => {
              const cleanWord = word.replace(/[^\w]/g, '')
              const isKnown = kamus ? kamus.words.some(e => e.word.toLowerCase() === cleanWord.toLowerCase()) : true
              return isKnown ? word : `<span class="text-red-600 dark:text-red-400 font-semibold">${word}</span>`
            }).join(' ')

            return (
              <div key={i} className={`rounded p-2 ${isEditing ? 'border-2 border-amber-400 bg-amber-50/30 dark:bg-amber-950/10' : 'border'}`}>
                <div className="flex items-start gap-2">
                  {/* Cue number + timestamp */}
                  <div className="text-xs text-muted-foreground shrink-0 w-20">
                    <div className="font-mono font-bold">{i + 1}</div>
                    <div className="font-mono">
                      {Math.floor(entry.start / 60)}:{String(Math.floor(entry.start % 60)).padStart(2, '0')}
                    </div>
                  </div>

                  {/* Text */}
                  <div className="flex-1 min-w-0">
                    {isEditing ? (
                      <div className="space-y-2">
                        <textarea
                          value={editedText}
                          onChange={e => setEditedText(e.target.value)}
                          className="w-full text-sm border rounded p-2 bg-background"
                          rows={Math.min(4, editedText.split('\n').length)}
                          autoFocus
                        />
                        <div className="flex gap-2">
                          <Button size="sm" onClick={saveEdit} className="h-7 text-xs">Simpan</Button>
                          <Button size="sm" variant="outline" onClick={cancelEdit} className="h-7 text-xs">Batal</Button>
                        </div>
                      </div>
                    ) : (
                      <p
                        className="text-sm cursor-text hover:bg-muted/30 rounded px-1 py-0.5"
                        onClick={() => startEdit(i)}
                        dangerouslySetInnerHTML={{ __html: highlightedText }}
                      />
                    )}
                  </div>

                  {/* Register toggle */}
                  <div className="shrink-0 flex flex-col gap-1">
                    <Badge
                      className={`text-xs cursor-pointer ${register === 'ngoko' ? getRegisterColor('ngoko') : 'bg-gray-100 text-gray-400 dark:bg-gray-800'}`}
                      onClick={() => toggleRegister(i, 'ngoko')}
                    >
                      N
                    </Badge>
                    <Badge
                      className={`text-xs cursor-pointer ${register === 'krama' ? getRegisterColor('krama') : 'bg-gray-100 text-gray-400 dark:bg-gray-800'}`}
                      onClick={() => toggleRegister(i, 'krama')}
                    >
                      K
                    </Badge>
                    <Badge
                      className={`text-xs cursor-pointer ${register === 'krama_inggil' ? getRegisterColor('krama_inggil') : 'bg-gray-100 text-gray-400 dark:bg-gray-800'}`}
                      onClick={() => toggleRegister(i, 'krama_inggil')}
                    >
                      KI
                    </Badge>
                  </div>
                </div>

                {/* Suggested register */}
                {!isEditing && suggested && !register && (
                  <div className="ml-22 text-xs text-muted-foreground mt-1 pl-22">
                    <span className="italic">Suggest: </span>
                    <span className={`font-medium ${getRegisterColor(suggested)} px-1 rounded`}>
                      {getRegisterLabel(suggested)}
                    </span>
                  </div>
                )}
              </div>
            )
          })}
        </div>

        {/* Info */}
        <p className="text-xs text-muted-foreground">
          <strong>Cara pakai:</strong> Klik cue untuk edit inline. Toggle N=ngoko, K=krama, KI=krama inggil.
          Kata merah = tidak dikenal di kamus. Klik "Hapus Aksén" untuk hapus é/è/ê (Edge TTS tidak bisa baca).
          Setelah selesai, klik "Download SRT Rapi" → lanjut ke TTS mode ON + Smart Fit.
        </p>
      </CardContent>
    </Card>
  )
}
