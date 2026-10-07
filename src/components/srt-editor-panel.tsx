'use client'

import { useCallback, useEffect, useRef, useState } from 'react'
import { Upload, Download, ChevronLeft, ChevronRight, Loader2, CheckCircle2, Cloud, Mic, FolderOpen, Plus, Trash2, Wand2, X, Eraser } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { toast } from 'sonner'
import { parseSrt, serializePart, downloadTextFile, type SrtEntry, type SrtPart } from '@/lib/srt'
import {
  isSupabaseAvailable,
  createDualProject,
  getProjectWithCues,
  updateCueFull,
  bumpProjectEdited,
  listProjects,
  deleteProject,
  type SrtProject,
} from '@/lib/supabase'
import {
  loadKamusJawa,
  convertRegister,
  stripAksenJawa,
  stripAksenFromEntries,
  type KamusJawa,
  type CueRegister,
} from '@/lib/rapikan-jawa'
import { narrateSingleCue, stitchFullAudio, type NarrationResult, type NarrationOptions, type Provider, type TTSProgress } from '@/lib/tts'
import { encodeWav } from '@/lib/audio-utils'
import {
  saveCueAudio, getCueAudio, deleteCueAudio, listCachedCueIndices,
  saveFullAudio, getFullAudio, getCacheSizeForProject,
} from '@/lib/audio-cache'

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

const STORAGE_KEY_PROJECT = 'srt-splitter-active-project'

export function DualSrtEditor({ prefix }: DualSrtEditorProps) {
  const [kamus, setKamus] = useState<KamusJawa | null>(null)
  // Current project state
  const [projectId, setProjectId] = useState<string | null>(null)
  const [projectName, setProjectName] = useState<string>('')
  const [idEntries, setIdEntries] = useState<SrtEntry[]>([])   // SRT Indonesia (read-only context)
  const [jawaEntries, setJawaEntries] = useState<SrtEntry[]>([]) // SRT Jawa (editor)
  const [registers, setRegisters] = useState<Record<number, CueRegister>>({})
  const [voices, setVoices] = useState<Record<number, string>>({})
  const [cueIdMap, setCueIdMap] = useState<Record<number, string>>({})  // cue_index → DB cue UUID
  const [currentPage, setCurrentPage] = useState(0)
  // UI state
  const [autoSaveStatus, setAutoSaveStatus] = useState<'idle' | 'saving' | 'saved' | 'error'>('idle')
  const [supabaseReady, setSupabaseReady] = useState(false)
  const [projects, setProjects] = useState<SrtProject[]>([])
  const [showNewProject, setShowNewProject] = useState(false)
  const [showProjectList, setShowProjectList] = useState(false)
  const [newProjectName, setNewProjectName] = useState('')
  const [newProjectIdSrt, setNewProjectIdSrt] = useState<string>('')
  const [newProjectJawaSrt, setNewProjectJawaSrt] = useState<string>('')
  const [newProjectIdCount, setNewProjectIdCount] = useState(0)
  const [newProjectJawaCount, setNewProjectJawaCount] = useState(0)
  // TTS state
  const [isGeneratingTts, setIsGeneratingTts] = useState(false)
  const [ttsProgress, setTtsProgress] = useState<{ current: number; total: number; text: string } | null>(null)
  const [ttsStage, setTtsStage] = useState<TTSProgress | null>(null)
  const [ttsResult, setTtsResult] = useState<NarrationResult | null>(null)
  const [ttsProvider, setTtsProvider] = useState<Provider>('edge')
  const [ttsPitch, setTtsPitch] = useState<string>('+0Hz')
  const [ttsSmartFitCap, setTtsSmartFitCap] = useState<number>(2.0)
  // Per-cue preview state
  const [previewingCue, setPreviewingCue] = useState<number | null>(null)  // cue index being generated
  const [cueAudioCache, setCueAudioCache] = useState<Record<number, { url: string; durationSec: number; voice: string }>>({})  // cue_index → preview URL
  const [cachedCueCount, setCachedCueCount] = useState(0)  // count of cues cached in IndexedDB
  const [cacheSizeMB, setCacheSizeMB] = useState(0)
  const [savedFullAudio, setSavedFullAudio] = useState<{ url: string; durationSec: number; cueCount: number; voiceSummary: string } | null>(null)
  // Refs
  const saveTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const pendingNewProjectIdRef = useRef<HTMLInputElement>(null)
  const pendingNewProjectJawaRef = useRef<HTMLInputElement>(null)

  // === Init: load kamus + check Supabase + restore active project ===
  useEffect(() => {
    loadKamusJawa().then(k => {
      setKamus(k)
      if (k) toast.success(`Kamus: ${k.words.length} entri (Supabase)`)
    })
    const ready = isSupabaseAvailable()
    setSupabaseReady(ready)
    if (ready) {
      refreshProjects()
      // Restore last active project from localStorage
      const lastProjectId = localStorage.getItem(STORAGE_KEY_PROJECT)
      if (lastProjectId) {
        loadProject(lastProjectId)
      }
    }
  }, [])

  const refreshProjects = useCallback(async () => {
    if (!isSupabaseAvailable()) return
    const projs = await listProjects()
    setProjects(projs)
  }, [])

  // Refresh per-cue audio cache count + cache size + full audio (untuk display)
  const refreshAudioCache = useCallback(async (pid: string | null) => {
    if (!pid) {
      setCachedCueCount(0)
      setCacheSizeMB(0)
      setSavedFullAudio(null)
      setCueAudioCache({})
      return
    }
    try {
      const { cueCount, totalBytes } = await getCacheSizeForProject(pid)
      setCachedCueCount(cueCount)
      setCacheSizeMB(totalBytes / (1024 * 1024))
      const full = await getFullAudio(pid)
      if (full) {
        setSavedFullAudio({
          url: URL.createObjectURL(full.blob),
          durationSec: full.durationSec,
          cueCount: full.cueCount,
          voiceSummary: full.voiceSummary,
        })
      } else {
        setSavedFullAudio(null)
      }
    } catch (e) {
      console.warn('refreshAudioCache failed:', e)
    }
  }, [])

  // === Create new project from 2 uploaded SRTs ===
  const handleStartNewProject = useCallback(async () => {
    if (!newProjectName.trim()) {
      toast.error('Nama project wajib diisi')
      return
    }
    if (!newProjectIdSrt || !newProjectJawaSrt) {
      toast.error('Upload SRT ID dan SRT Jawa dulu')
      return
    }
    if (newProjectIdCount !== newProjectJawaCount) {
      toast.warning(`Jumlah cue berbeda: ID=${newProjectIdCount}, Jawa=${newProjectJawaCount}. Pakai yang lebih kecil.`)
    }
    const minCues = Math.min(newProjectIdCount, newProjectJawaCount)

    const idParsed = parseSrt(newProjectIdSrt).slice(0, minCues)
    const jawaParsed = parseSrt(newProjectJawaSrt).slice(0, minCues)

    const cuesData = idParsed.map((idE, i) => ({
      cue_index: i,
      start_sec: idE.start,
      end_sec: idE.end,
      text: jawaParsed[i].textLines.join('\n'),
      text_id: idE.textLines.join('\n'),
      register: '',
      voice: '',
    }))

    setAutoSaveStatus('saving')
    const result = await createDualProject(newProjectName.trim(), newProjectIdSrt, newProjectJawaSrt, cuesData)
    if (!result) {
      toast.error('Gagal buat project. Cek Supabase migration v2.')
      setAutoSaveStatus('error')
      return
    }

    // Set as active project
    setProjectId(result.project.id)
    setProjectName(result.project.name)
    setIdEntries(idParsed)
    setJawaEntries(jawaParsed)
    setRegisters({})
    setVoices({})
    const newCueIdMap: Record<number, string> = {}
    result.cues.forEach((c, i) => { newCueIdMap[i] = c.id })
    setCueIdMap(newCueIdMap)
    setCurrentPage(0)
    setAutoSaveStatus('idle')
    setShowNewProject(false)
    setNewProjectName('')
    setNewProjectIdSrt('')
    setNewProjectJawaSrt('')
    setNewProjectIdCount(0)
    setNewProjectJawaCount(0)
    localStorage.setItem(STORAGE_KEY_PROJECT, result.project.id)
    toast.success(`Project "${result.project.name}" dibuat (${minCues} cue)`)
    refreshProjects()
    refreshAudioCache(result.project.id)
  }, [newProjectName, newProjectIdSrt, newProjectJawaSrt, newProjectIdCount, newProjectJawaCount, refreshAudioCache])

  // === Load existing project from DB ===
  const loadProject = useCallback(async (pid: string) => {
    setAutoSaveStatus('saving')
    const result = await getProjectWithCues(pid)
    if (!result) {
      toast.error('Gagal load project')
      setAutoSaveStatus('error')
      return
    }
    // Reconstruct SrtEntry[] from cues
    const idEntries: SrtEntry[] = result.cues.map(c => ({
      index: c.cue_index + 1,
      start: c.start_sec,
      end: c.end_sec,
      textLines: (c.text_id || '').split('\n'),
    }))
    const jawaEntries: SrtEntry[] = result.cues.map(c => ({
      index: c.cue_index + 1,
      start: c.start_sec,
      end: c.end_sec,
      textLines: c.text.split('\n'),
    }))
    const newRegisters: Record<number, CueRegister> = {}
    const newVoices: Record<number, string> = {}
    const newCueIdMap: Record<number, string> = {}
    result.cues.forEach((c, i) => {
      if (c.register) newRegisters[i] = c.register as CueRegister
      if (c.voice) newVoices[i] = c.voice
      newCueIdMap[i] = c.id
    })

    setProjectId(result.project.id)
    setProjectName(result.project.name)
    setIdEntries(idEntries)
    setJawaEntries(jawaEntries)
    setRegisters(newRegisters)
    setVoices(newVoices)
    setCueIdMap(newCueIdMap)
    setCurrentPage(0)
    setAutoSaveStatus('idle')
    setShowProjectList(false)
    localStorage.setItem(STORAGE_KEY_PROJECT, result.project.id)
    toast.success(`Project "${result.project.name}" loaded (${result.cues.length} cue)`)
    refreshAudioCache(result.project.id)
  }, [refreshAudioCache])

  // === Close current project (back to "new project" screen) ===
  const handleCloseProject = useCallback(() => {
    setProjectId(null)
    setProjectName('')
    setIdEntries([])
    setJawaEntries([])
    setRegisters({})
    setVoices({})
    setCueIdMap({})
    setCurrentPage(0)
    setTtsResult(null)
    setCueAudioCache({})
    setSavedFullAudio(null)
    setCachedCueCount(0)
    setCacheSizeMB(0)
    localStorage.removeItem(STORAGE_KEY_PROJECT)
  }, [])

  // === Delete project ===
  const handleDeleteProject = useCallback(async (pid: string, name: string) => {
    if (!confirm(`Hapus project "${name}"? Semua cue akan hilang.`)) return
    const ok = await deleteProject(pid)
    if (ok) {
      if (pid === projectId) handleCloseProject()
      refreshProjects()
      toast.success(`Project "${name}" dihapus`)
    } else {
      toast.error('Gagal hapus project')
    }
  }, [projectId, handleCloseProject, refreshProjects])

  // === Upload SRT for new project (handle text + parse) ===
  const handleUploadIdForNew = useCallback(async (file: File) => {
    const text = await file.text()
    const parsed = parseSrt(text)
    if (parsed.length === 0) {
      toast.error('SRT ID kosong/invalid')
      return
    }
    setNewProjectIdSrt(text)
    setNewProjectIdCount(parsed.length)
    toast.success(`SRT ID: ${parsed.length} cue`)
  }, [])

  const handleUploadJawaForNew = useCallback(async (file: File) => {
    const text = await file.text()
    const parsed = parseSrt(text)
    if (parsed.length === 0) {
      toast.error('SRT Jawa kosong/invalid')
      return
    }
    setNewProjectJawaSrt(text)
    setNewProjectJawaCount(parsed.length)
    toast.success(`SRT Jawa: ${parsed.length} cue`)
  }, [])

  // === Edit SRT Jawa cue (inline textarea) → debounced auto-save ===
  const handleEditJawa = useCallback((index: number, newText: string) => {
    setJawaEntries(prev => {
      const updated = [...prev]
      updated[index] = { ...updated[index], textLines: newText.split('\n') }
      return updated
    })
    // Mark for save
    markCueForSave(index, { text: newText })
  }, [])

  // Mark cue for save (debounced per cue)
  const pendingSavesRef = useRef<Record<number, { text?: string; text_id?: string; register?: string; voice?: string }>>({})
  const markCueForSave = useCallback((index: number, updates: { text?: string; text_id?: string; register?: string; voice?: string }) => {
    pendingSavesRef.current[index] = { ...pendingSavesRef.current[index], ...updates }
    // Debounced flush
    if (saveTimerRef.current) clearTimeout(saveTimerRef.current)
    saveTimerRef.current = setTimeout(flushPendingSaves, 1500)
  }, [])

  const flushPendingSaves = useCallback(async () => {
    if (!projectId || !supabaseReady) return
    const pending = pendingSavesRef.current
    const indices = Object.keys(pending).map(Number)
    if (indices.length === 0) {
      setAutoSaveStatus('idle')
      return
    }
    setAutoSaveStatus('saving')
    let okCount = 0
    for (const idx of indices) {
      const cueId = cueIdMap[idx]
      if (!cueId) continue
      const updates = { ...pending[idx], is_edited: true }
      const ok = await updateCueFull(cueId, updates)
      if (ok) {
        okCount++
        delete pending[idx]
      }
    }
    if (okCount > 0) {
      await bumpProjectEdited(projectId, 0)  // bump updated_at
      setAutoSaveStatus('saved')
      setTimeout(() => setAutoSaveStatus('idle'), 2000)
      refreshProjects()  // update sidebar timestamps
    } else {
      setAutoSaveStatus('error')
    }
  }, [projectId, supabaseReady, cueIdMap, refreshProjects])

  // === Toggle register: klik Ngoko → convert ke ngoko, klik Krama → convert ke krama ===
  const handleToggleRegister = useCallback((index: number, register: CueRegister) => {
    if (!kamus) {
      toast.info('Kamus belum loaded')
      return
    }
    setJawaEntries(prev => {
      const updated = [...prev]
      const text = updated[index].textLines.join(' ')
      // BIDIRECTIONAL: convert dari register apa pun ke target register
      // Source "aku"/"inyong"/"kula"/"dalem" → convert ke ngoko atau krama utama
      const converted = convertRegister(text, 'ngoko', register, kamus)
      updated[index] = { ...updated[index], textLines: converted.split('\n') }
      markCueForSave(index, { text: converted, register })
      return updated
    })
    setRegisters(prev => ({ ...prev, [index]: register }))
  }, [kamus, markCueForSave])

  // === Set voice per cue ===
  const handleSetVoice = useCallback((index: number, voiceId: string) => {
    setVoices(prev => ({ ...prev, [index]: voiceId }))
    markCueForSave(index, { voice: voiceId })
  }, [markCueForSave])

  // === All Ngoko / All Krama per halaman ===
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
        // BIDIRECTIONAL: convert ke ngoko atau krama utama (source apapun)
        const converted = convertRegister(text, 'ngoko', register, kamus)
        updated[i] = { ...updated[i], textLines: converted.split('\n') }
        markCueForSave(i, { text: converted, register })
        setRegisters(prev => ({ ...prev, [i]: register }))
      }
      return updated
    })
    toast.success(`Halaman ${currentPage + 1}: convert ke ${register}`)
  }, [kamus, jawaEntries, currentPage, markCueForSave])

  // === All Ngoko / All Krama semua ===
  const handleConvertAll = useCallback((register: CueRegister) => {
    if (!kamus) {
      toast.info('Kamus belum loaded')
      return
    }
    setJawaEntries(prev => {
      const updated = [...prev]
      for (let i = 0; i < updated.length; i++) {
        const text = updated[i].textLines.join(' ')
        // BIDIRECTIONAL: convert ke ngoko atau krama utama (source apapun)
        const converted = convertRegister(text, 'ngoko', register, kamus)
        updated[i] = { ...updated[i], textLines: converted.split('\n') }
        markCueForSave(i, { text: converted, register })
        setRegisters(prev => ({ ...prev, [i]: register }))
      }
      return updated
    })
    toast.success(`Semua ${jawaEntries.length} cue: convert ke ${register}`)
  }, [kamus, jawaEntries, markCueForSave])

  // === Download SRT Jawa ===
  const handleDownload = useCallback(() => {
    if (jawaEntries.length === 0) return
    const part: SrtPart = {
      index: 1, entries: jawaEntries, startSec: jawaEntries[0].start,
      endSec: jawaEntries[jawaEntries.length - 1].end,
      durationSec: jawaEntries[jawaEntries.length - 1].end - jawaEntries[0].start,
      entryCount: jawaEntries.length,
    }
    const content = serializePart(part, false)
    const safeName = projectName.replace(/[^a-zA-Z0-9-_]/g, '_') || prefix
    downloadTextFile(`${safeName}-jw-final.srt`, content)
    toast.success('SRT Jawa didownload')
  }, [jawaEntries, projectName, prefix])

  // === Hapus aksen Jawa di SRT final (é/è/ê → e) ===
  // Manual normalisasi SRT — hapus aksen permanen di text Jawa
  // Cocok untuk: SRT final yang mau langsung pakai (untuk VLC, untuk TTS yang tidak bisa baca aksen)
  // Note: TTS Preview/Generate Full SUDAH auto-strip aksen (tanpa ubah SRT) — tombol ini opsional untuk normalisasi SRT permanen
  const handleStripAksen = useCallback(() => {
    if (jawaEntries.length === 0) return
    if (!confirm('Hapus aksen Jawa (é/è/ê → e) di SRT final? TTS Preview/Generate Full sudah auto-strip tanpa ubah SRT, jadi ini opsional.')) return
    setJawaEntries(prev => {
      const updated = prev.map(e => ({
        ...e,
        textLines: [...e.textLines],
      }))
      const count = stripAksenFromEntries(updated)
      if (count > 0) {
        // Save semua cue yang berubah ke Supabase
        for (let i = 0; i < updated.length; i++) {
          if (updated[i].textLines.join('\n') !== prev[i].textLines.join('\n')) {
            markCueForSave(i, { text: updated[i].textLines.join('\n') })
          }
        }
        toast.success(`${count} line: aksen dihapus (é→e, è→e, ê→e)`)
      } else {
        toast.info('Tidak ada aksen Jawa di SRT')
      }
      return updated
    })
  }, [jawaEntries, markCueForSave])


  // === Generate TTS (mode ON + Smart Fit, per-cue voice) ===
  // Build common NarrationOptions (dipakai oleh per-cue preview + Generate Full)
  const buildTtsOpts = useCallback((onLineProgress?: (current: number, total: number, text: string) => void): NarrationOptions => {
    const defaultVoice = 'jv-ID-SitiNeural'
    const voiceResolver = (_entry: SrtEntry, idx: number) => {
      const voiceId = voices[idx]
      if (!voiceId) return defaultVoice
      const v = VOICES.find(x => x.id === voiceId)
      return v ? v.voice : defaultVoice
    }
    return {
      provider: ttsProvider,
      voice: defaultVoice,
      voiceResolver,
      respectTiming: true,  // MODE ON — fit ke SRT ori
      smartFit: true,
      smartFitAudioRateCap: ttsSmartFitCap,
      smartFitUseAsymmetricTrim: true,
      smartFitCrossfadeMs: 150,
      smartFitNormalizeDbFS: -2,
      pitch: ttsProvider === 'edge' ? ttsPitch : undefined,
      onLineProgress,
      onStage: (p) => setTtsStage(p),
    }
  }, [voices, ttsProvider, ttsPitch, ttsSmartFitCap])

  // === Per-cue preview: generate 1 cue TTS + play inline + cache ke IndexedDB ===
  const handlePreviewCue = useCallback(async (cueIndex: number) => {
    if (!projectId) return
    const entry = jawaEntries[cueIndex]
    if (!entry) return
    const text = entry.textLines.join(' ').trim()
    if (!text) {
      toast.info('Cue kosong, tidak ada yang di-preview')
      return
    }

    // Voice for this cue
    const voiceId = voices[cueIndex] || ''
    const voiceShort = voiceId || 'siti'  // default Siti
    const voiceFull = VOICES.find(v => v.id === voiceShort)?.voice || 'jv-ID-SitiNeural'

    // Check existing cache — kalau text + voice + pitch + cap sama, langsung play (no regen)
    try {
      const cached = await getCueAudio(projectId, cueIndex)
      if (cached && cached.text === text && cached.voiceId === voiceShort && cached.pitch === ttsPitch && cached.smartFitCap === ttsSmartFitCap) {
        // Cache valid — load ke memory cache + play
        const url = URL.createObjectURL(cached.blob)
        setCueAudioCache(prev => ({ ...prev, [cueIndex]: { url, durationSec: cached.durationSec, voice: cached.voiceId } }))
        toast.success(`Cue #${cueIndex + 1} dari cache (${cached.durationSec.toFixed(1)}s)`)
        return
      }
    } catch (e) {
      console.warn('getCueAudio failed:', e)
    }

    // Generate new audio
    setPreviewingCue(cueIndex)
    try {
      const nextEntryStart = (cueIndex + 1 < jawaEntries.length) ? jawaEntries[cueIndex + 1].start : entry.end
      const opts = buildTtsOpts()
      const result = await narrateSingleCue(entry, cueIndex, nextEntryStart, opts)

      // Encode WAV
      const blob = encodeWav(result.audio, result.sampleRate)

      // Save to IndexedDB
      await saveCueAudio(projectId, cueIndex, blob, {
        sampleRate: result.sampleRate,
        durationSec: result.fittedDurationSec,
        voice: voiceFull,
        voiceId: voiceShort,
        text,
        pitch: ttsPitch,
        smartFitCap: ttsSmartFitCap,
      })

      // Update memory cache + UI
      const url = URL.createObjectURL(blob)
      setCueAudioCache(prev => ({ ...prev, [cueIndex]: { url, durationSec: result.fittedDurationSec, voice: voiceShort } }))
      refreshAudioCache(projectId)
      toast.success(`Cue #${cueIndex + 1} preview ready (${result.fittedDurationSec.toFixed(1)}s, ${voiceShort})`)
    } catch (e) {
      console.error(e)
      toast.error(`Preview cue #${cueIndex + 1} gagal: ${(e as Error).message}`)
    } finally {
      setPreviewingCue(null)
    }
  }, [projectId, jawaEntries, voices, ttsPitch, ttsSmartFitCap, buildTtsOpts, refreshAudioCache])

  // === Generate Full Audio (Mode ON + Smart Fit, pakai cache kalau valid) ===
  const handleGenerateTts = useCallback(async () => {
    if (jawaEntries.length === 0 || !projectId) return
    setIsGeneratingTts(true)
    setTtsProgress({ current: 0, total: jawaEntries.length, text: 'Mulai...' })
    setTtsResult(null)
    try {
      const opts = buildTtsOpts((current, total, text) => {
        setTtsProgress({ current, total, text: text.slice(0, 60) })
      })

      // Build cached audios map (Float32Array per cue) — pakai cache kalau valid
      const cachedAudios = new Map<number, Float32Array>()
      const cachedIndices = await listCachedCueIndices(projectId)
      let cacheHits = 0
      let cacheMiss = 0
      for (let i = 0; i < jawaEntries.length; i++) {
        const entry = jawaEntries[i]
        const text = entry.textLines.join(' ').trim()
        if (!text) continue
        const voiceId = voices[i] || ''
        const voiceShort = voiceId || 'siti'
        const cached = await getCueAudio(projectId, i)
        if (cached && cachedIndices.has(i) && cached.text === text && cached.voiceId === voiceShort && cached.pitch === ttsPitch && cached.smartFitCap === ttsSmartFitCap) {
          // Cache valid — decode blob ke Float32Array
          try {
            const arrayBuf = await cached.blob.arrayBuffer()
            const audioCtx = new AudioContext({ sampleRate: cached.sampleRate })
            const audioBuffer = await audioCtx.decodeAudioData(arrayBuf)
            const float32 = audioBuffer.getChannelData(0)
            cachedAudios.set(i, new Float32Array(float32))
            audioCtx.close()
            cacheHits++
          } catch (e) {
            console.warn('Failed to decode cached audio for cue', i, e)
            cacheMiss++
          }
        } else {
          cacheMiss++
        }
      }
      toast.info(`Cache: ${cacheHits} hit, ${cacheMiss} miss (akan generate)`)

      // Stitch: pakai cache + generate missing
      const result = await stitchFullAudio(jawaEntries, cachedAudios, opts, (current, total, text) => {
        setTtsProgress({ current, total, text: text.slice(0, 60) })
      })
      setTtsResult(result)

      // Save full audio ke IndexedDB (browser local storage)
      const voiceCounts: Record<string, number> = {}
      jawaEntries.forEach((_, i) => {
        const v = voices[i] || 'siti'
        voiceCounts[v] = (voiceCounts[v] || 0) + 1
      })
      const voiceSummary = Object.entries(voiceCounts).map(([v, c]) => `${v}:${c}`).join(', ')
      await saveFullAudio(projectId, result.blob, {
        sampleRate: result.sampleRate,
        durationSec: result.durationSec,
        cueCount: jawaEntries.length,
        voiceSummary,
      })
      refreshAudioCache(projectId)

      // Auto-download WAV
      const safeName = (projectName || prefix).replace(/[^a-zA-Z0-9-_]/g, '_')
      const a = document.createElement('a')
      a.href = result.previewUrl
      a.download = `${safeName}-audio-dub.wav`
      document.body.appendChild(a)
      a.click()
      document.body.removeChild(a)
      toast.success(`TTS done: ${result.durationSec.toFixed(1)}s, ${jawaEntries.length} cue (cache: ${cacheHits}/${cacheHits + cacheMiss})`)
    } catch (e) {
      console.error(e)
      toast.error(`TTS gagal: ${(e as Error).message}`)
    } finally {
      setIsGeneratingTts(false)
      setTtsProgress(null)
      setTtsStage(null)
    }
  }, [jawaEntries, voices, ttsProvider, ttsPitch, ttsSmartFitCap, projectName, prefix, projectId, buildTtsOpts, refreshAudioCache])

  // ================================================================
  // RENDER
  // ================================================================

  // No Supabase → fallback message
  if (!supabaseReady) {
    return (
      <Card className="border-2 border-amber-300 dark:border-amber-700 shadow-md">
        <CardHeader className="pb-3">
          <CardTitle className="text-xl flex items-center gap-2">
            <Mic className="size-6 text-amber-600" />
            Editor SRT Jawa
          </CardTitle>
          <p className="text-sm text-muted-foreground mt-1">
            Set Supabase env vars (NEXT_PUBLIC_SUPABASE_URL + ANON_KEY) untuk pakai project-based editor.
            Lihat <code>scripts/supabase-migration-v2.sql</code> untuk setup.
          </p>
        </CardHeader>
      </Card>
    )
  }

  // === NEW PROJECT MODAL ===
  const newProjectModal = showNewProject && (
    <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4">
      <Card className="w-full max-w-2xl max-h-[90vh] overflow-y-auto">
        <CardHeader className="pb-3">
          <div className="flex items-center justify-between">
            <CardTitle className="text-lg flex items-center gap-2">
              <Plus className="size-5 text-indigo-600" /> Buat Project Baru
            </CardTitle>
            <Button size="sm" variant="ghost" onClick={() => setShowNewProject(false)}>
              <X className="size-4" />
            </Button>
          </div>
        </CardHeader>
        <CardContent className="space-y-4">
          <div>
            <label className="text-xs font-semibold uppercase tracking-wide">Nama Project</label>
            <input
              type="text"
              value={newProjectName}
              onChange={e => setNewProjectName(e.target.value)}
              placeholder="mis. S1-Ep1, S2-Ep3, atau nama file SRT"
              className="w-full mt-1 px-3 py-2 border rounded text-sm bg-background"
            />
            <p className="text-[11px] text-muted-foreground mt-1">Nama bebas, untuk identifikasi di daftar project.</p>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div className="rounded-lg border border-blue-200 dark:border-blue-800 p-3 bg-blue-50/30 dark:bg-blue-950/10">
              <label className="text-xs font-semibold text-blue-700 dark:text-blue-300 uppercase tracking-wide">1. SRT Indonesia</label>
              <p className="text-[11px] text-muted-foreground mb-2">Konteks (read-only)</p>
              <input
                ref={pendingNewProjectIdRef}
                type="file"
                accept=".srt"
                onChange={e => e.target.files?.[0] && handleUploadIdForNew(e.target.files[0])}
                className="hidden"
              />
              <Button variant="outline" className="w-full" size="sm" onClick={() => pendingNewProjectIdRef.current?.click()}>
                <Upload className="size-4 mr-2" /> Upload SRT ID
              </Button>
              {newProjectIdCount > 0 && (
                <p className="text-xs text-green-600 dark:text-green-400 mt-2">✓ {newProjectIdCount} cue</p>
              )}
            </div>
            <div className="rounded-lg border border-amber-200 dark:border-amber-800 p-3 bg-amber-50/30 dark:bg-amber-950/10">
              <label className="text-xs font-semibold text-amber-700 dark:text-amber-300 uppercase tracking-wide">2. SRT Jawa</label>
              <p className="text-[11px] text-muted-foreground mb-2">Editor (akan diedit)</p>
              <input
                ref={pendingNewProjectJawaRef}
                type="file"
                accept=".srt"
                onChange={e => e.target.files?.[0] && handleUploadJawaForNew(e.target.files[0])}
                className="hidden"
              />
              <Button variant="outline" className="w-full" size="sm" onClick={() => pendingNewProjectJawaRef.current?.click()}>
                <Upload className="size-4 mr-2" /> Upload SRT Jawa
              </Button>
              {newProjectJawaCount > 0 && (
                <p className="text-xs text-green-600 dark:text-green-400 mt-2">✓ {newProjectJawaCount} cue</p>
              )}
            </div>
          </div>
          {newProjectIdCount > 0 && newProjectJawaCount > 0 && newProjectIdCount !== newProjectJawaCount && (
            <p className="text-xs text-amber-600 dark:text-amber-400">
              ⚠ Jumlah cue berbeda. Akan pakai {Math.min(newProjectIdCount, newProjectJawaCount)} cue (yang lebih kecil).
            </p>
          )}
          <div className="flex gap-2 pt-2">
            <Button onClick={handleStartNewProject} disabled={!newProjectName.trim() || !newProjectIdSrt || !newProjectJawaSrt}>
              <Plus className="size-4 mr-1" /> Buat Project &amp; Simpan ke Supabase
            </Button>
            <Button variant="ghost" onClick={() => setShowNewProject(false)}>Batal</Button>
          </div>
        </CardContent>
      </Card>
    </div>
  )

  // === PROJECT LIST MODAL ===
  const projectListModal = showProjectList && (
    <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4">
      <Card className="w-full max-w-2xl max-h-[90vh] overflow-y-auto">
        <CardHeader className="pb-3">
          <div className="flex items-center justify-between">
            <CardTitle className="text-lg flex items-center gap-2">
              <FolderOpen className="size-5 text-indigo-600" /> Daftar Project ({projects.length})
            </CardTitle>
            <Button size="sm" variant="ghost" onClick={() => setShowProjectList(false)}>
              <X className="size-4" />
            </Button>
          </div>
        </CardHeader>
        <CardContent className="space-y-2">
          {projects.length === 0 ? (
            <p className="text-sm text-muted-foreground text-center py-8">
              Belum ada project. Klik <strong>+ Project Baru</strong> untuk buat.
            </p>
          ) : (
            projects.map(p => (
              <div key={p.id} className={`rounded-md border p-3 flex items-center justify-between gap-3 ${p.id === projectId ? 'border-indigo-400 bg-indigo-50/30 dark:bg-indigo-950/10' : 'border-border'}`}>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="font-medium truncate">{p.name}</span>
                    {p.id === projectId && <Badge variant="secondary" className="text-xs">aktif</Badge>}
                  </div>
                  <div className="text-xs text-muted-foreground mt-0.5">
                    {p.cue_count} cue • edited: {p.cues_edited} • {new Date(p.updated_at).toLocaleString('id-ID', { dateStyle: 'short', timeStyle: 'short' })}
                  </div>
                </div>
                <div className="flex gap-1">
                  <Button size="sm" variant="outline" onClick={() => loadProject(p.id)} disabled={p.id === projectId}>
                    <FolderOpen className="size-3.5 mr-1" /> Buka
                  </Button>
                  <Button size="sm" variant="ghost" onClick={() => handleDeleteProject(p.id, p.name)}>
                    <Trash2 className="size-3.5 text-red-500" />
                  </Button>
                </div>
              </div>
            ))
          )}
        </CardContent>
      </Card>
    </div>
  )

  // === Empty state (no active project) ===
  if (!projectId) {
    return (
      <>
        {newProjectModal}
        {projectListModal}
        <Card className="border-2 border-indigo-300 dark:border-indigo-700 shadow-md">
          <CardHeader className="pb-3">
            <CardTitle className="text-xl flex items-center gap-2">
              <Mic className="size-6 text-indigo-600" />
              Editor SRT Jawa
              <Badge variant="secondary" className="ml-1 text-xs">Project-based</Badge>
            </CardTitle>
            <p className="text-sm text-muted-foreground mt-1">
              Buat <strong>project</strong> per SRT pair (ID + Jawa). Semua editan auto-save ke Supabase. Bisa multi-project, lanjut kapan saja.
            </p>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="flex flex-wrap gap-2">
              <Button onClick={() => setShowNewProject(true)}>
                <Plus className="size-4 mr-2" /> Project Baru
              </Button>
              <Button variant="outline" onClick={() => { refreshProjects(); setShowProjectList(true) }} disabled={projects.length === 0}>
                <FolderOpen className="size-4 mr-2" /> Buka Project ({projects.length})
              </Button>
            </div>
            <div className="rounded-md bg-indigo-50/50 dark:bg-indigo-950/20 border border-indigo-100 dark:border-indigo-900 p-3 text-xs text-muted-foreground">
              <p className="font-medium text-foreground mb-1">Cara pakai:</p>
              <ol className="list-decimal list-inside space-y-0.5">
                <li>Klik <strong>+ Project Baru</strong></li>
                <li>Isi nama project (mis. <code>S1-Ep1</code>)</li>
                <li>Upload <strong>SRT ID</strong> (Indonesia, konteks) + <strong>SRT Jawa</strong> (editor)</li>
                <li>Klik <strong>Buat Project</strong> → tersimpan ke Supabase</li>
                <li>Edit cue, toggle Ngoko/Krama, pilih Voice — <strong>auto-save</strong> setiap 1.5s</li>
                <li>Klik <strong>▶ Preview</strong> per cue → dengar di browser, cache ke IndexedDB</li>
                <li>Setelah review semua cue, klik <strong>Generate Full</strong> → audio dub full (Mode ON + Smart Fit, sync 100%)</li>
                <li>Audio tersimpan di browser (IndexedDB), bisa tutup project + lanjut kapan saja</li>
              </ol>
            </div>
            {projects.length > 0 && (
              <div className="rounded-md border p-3">
                <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide mb-2">Project Terakhir</p>
                <div className="space-y-1">
                  {projects.slice(0, 3).map(p => (
                    <button key={p.id} onClick={() => loadProject(p.id)} className="w-full text-left rounded p-2 hover:bg-indigo-50 dark:hover:bg-indigo-950/30 transition-colors">
                      <div className="flex items-center justify-between gap-2">
                        <span className="text-sm font-medium truncate">{p.name}</span>
                        <span className="text-xs text-muted-foreground shrink-0">
                          {p.cue_count} cue • {new Date(p.updated_at).toLocaleDateString('id-ID')}
                        </span>
                      </div>
                    </button>
                  ))}
                </div>
              </div>
            )}
          </CardContent>
        </Card>
      </>
    )
  }

  // === Editor screen (active project) ===
  const totalPages = Math.ceil(jawaEntries.length / PAGE_SIZE)
  const startIdx = currentPage * PAGE_SIZE
  const endIdx = Math.min(startIdx + PAGE_SIZE, jawaEntries.length)
  const pageEntries = jawaEntries.slice(startIdx, endIdx)
  const cuesWithVoice = Object.values(voices).filter(v => v).length

  return (
    <>
      {newProjectModal}
      {projectListModal}
      <Card className="border-2 border-indigo-300 dark:border-indigo-700 shadow-md">
        <CardHeader className="pb-3">
          <div className="flex items-center justify-between flex-wrap gap-2">
            <div className="flex items-center gap-2 flex-wrap">
              <CardTitle className="text-xl flex items-center gap-2">
                <Mic className="size-6 text-indigo-600" />
                {projectName}
              </CardTitle>
              <Badge variant="secondary" className="text-xs">
                {jawaEntries.length} cue
              </Badge>
              <Badge variant="outline" className="text-xs">
                voice: {cuesWithVoice}/{jawaEntries.length}
              </Badge>
            </div>
            <div className="flex items-center gap-2 text-xs flex-wrap">
              <Badge variant="outline" className={
                autoSaveStatus === 'saving' ? 'bg-blue-50 dark:bg-blue-950/30 animate-pulse' :
                autoSaveStatus === 'saved' ? 'bg-green-50 dark:bg-green-950/30' :
                autoSaveStatus === 'error' ? 'bg-red-50 dark:bg-red-950/30' : ''
              }>
                {autoSaveStatus === 'saving' ? <><Loader2 className="size-3 mr-1 animate-spin" /> Simpan...</> :
                 autoSaveStatus === 'saved' ? <><CheckCircle2 className="size-3 mr-1" /> Tersimpan</> :
                 autoSaveStatus === 'error' ? <><X className="size-3 mr-1" /> Error</> :
                 <><Cloud className="size-3 mr-1" /> Auto-save</>}
              </Badge>
              <Button size="sm" variant="ghost" onClick={() => { refreshProjects(); setShowProjectList(true) }}>
                <FolderOpen className="size-3.5 mr-1" /> Ganti
              </Button>
              <Button size="sm" variant="ghost" onClick={handleCloseProject}>
                <X className="size-3.5 mr-1" /> Tutup
              </Button>
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
            <Button size="sm" variant="outline" onClick={handleStripAksen}
              className="border-purple-200 text-purple-600 dark:text-purple-400"
              title="Hapus aksen Jawa (é/è/ê → e) di SRT final. Edge TTS Jawa tidak bisa baca aksen. Auto-normalisasi juga dilakukan saat Preview/Generate TTS (tanpa ubah SRT final)."
            >
              <Eraser className="size-3.5 mr-1" /> Hapus Aksén (SRT)
            </Button>
            <Button size="sm" onClick={handleDownload}>
              <Download className="size-3.5 mr-1" /> Download SRT Jawa
            </Button>
          </div>

          {/* TTS panel */}
          <div className="rounded-md border border-purple-200 dark:border-purple-800 p-3 bg-purple-50/30 dark:bg-purple-950/10 space-y-2">
            <div className="flex items-center justify-between flex-wrap gap-2">
              <div className="flex items-center gap-2">
                <Wand2 className="size-4 text-purple-600" />
                <span className="text-sm font-medium">Generate TTS (Mode ON + Smart Fit, 100% sync)</span>
              </div>
              <div className="flex items-center gap-2">
                <select value={ttsProvider} onChange={e => setTtsProvider(e.target.value as Provider)} className="text-xs border rounded px-1.5 py-1 bg-background">
                  <option value="edge">Edge TTS</option>
                  <option value="openai">OpenAI (butuh key)</option>
                  <option value="openrouter">OpenRouter (butuh key)</option>
                </select>
                {ttsProvider === 'edge' && (
                  <select value={ttsPitch} onChange={e => setTtsPitch(e.target.value)} className="text-xs border rounded px-1.5 py-1 bg-background">
                    <option value="+0Hz">Pitch +0Hz (natural)</option>
                    <option value="-10Hz">Pitch -10Hz (laki bas)</option>
                    <option value="+10Hz">Pitch +10Hz (perempuan tinggi)</option>
                  </select>
                )}
                <select value={ttsSmartFitCap} onChange={e => setTtsSmartFitCap(Number(e.target.value))} className="text-xs border rounded px-1.5 py-1 bg-background">
                  <option value={1.5}>Smart Fit cap 1.5x</option>
                  <option value={2.0}>Smart Fit cap 2.0x</option>
                </select>
                <Button size="sm" onClick={handleGenerateTts} disabled={isGeneratingTts || jawaEntries.length === 0}>
                  {isGeneratingTts ? <><Loader2 className="size-3.5 mr-1 animate-spin" /> Generating...</> : <><Wand2 className="size-3.5 mr-1" /> Generate Full</>}
                </Button>
              </div>
            </div>
            {/* Audio cache status */}
            <div className="flex items-center gap-2 text-[11px] text-muted-foreground flex-wrap">
              <Badge variant="outline" className="text-[11px] bg-purple-50/50 dark:bg-purple-950/30">
                Preview cache: {cachedCueCount}/{jawaEntries.length} cue{cacheSizeMB > 0 ? ` · ${cacheSizeMB.toFixed(1)} MB` : ''}
              </Badge>
              {cachedCueCount === jawaEntries.length && jawaEntries.length > 0 && (
                <Badge variant="outline" className="text-[11px] bg-green-50 dark:bg-green-950/30 text-green-700 dark:text-green-300">
                  ✓ Semua cue di-preview — Generate Full akan cepat (no re-gen)
                </Badge>
              )}
              {savedFullAudio && (
                <Badge variant="outline" className="text-[11px] bg-blue-50/50 dark:bg-blue-950/30">
                  Full audio tersimpan: {savedFullAudio.durationSec.toFixed(1)}s · {savedFullAudio.voiceSummary}
                </Badge>
              )}
            </div>
            {isGeneratingTts && ttsProgress && (
              <div className="space-y-1">
                <div className="flex justify-between text-xs text-muted-foreground">
                  <span>Baris {ttsProgress.current}/{ttsProgress.total}</span>
                  <span>{ttsProgress.text}</span>
                </div>
                <div className="h-1.5 bg-purple-100 dark:bg-purple-900/30 rounded-full overflow-hidden">
                  <div className="h-full bg-purple-600 transition-all" style={{ width: `${(ttsProgress.current / Math.max(1, ttsProgress.total)) * 100}%` }} />
                </div>
                {ttsStage && <p className="text-[11px] text-muted-foreground">{ttsStage.message}</p>}
              </div>
            )}
            {ttsResult && !isGeneratingTts && (
              <div className="flex items-center gap-3 text-xs">
                <CheckCircle2 className="size-4 text-green-600" />
                <span>Audio: {ttsResult.durationSec.toFixed(1)}s • Sample rate: {ttsResult.sampleRate}Hz</span>
                <a href={ttsResult.previewUrl} download={`${projectName.replace(/[^a-zA-Z0-9-_]/g, '_')}-audio-dub.wav`} className="text-purple-600 underline">Download ulang</a>
                <audio controls src={ttsResult.previewUrl} className="h-7 flex-1 min-w-[200px]" />
              </div>
            )}
            {savedFullAudio && !ttsResult && (
              <div className="flex items-center gap-3 text-xs pt-1 border-t border-purple-100 dark:border-purple-900">
                <span className="text-muted-foreground">Full audio dari cache browser:</span>
                <audio controls src={savedFullAudio.url} className="h-7 flex-1 min-w-[200px]" />
                <a href={savedFullAudio.url} download={`${projectName.replace(/[^a-zA-Z0-9-_]/g, '_')}-audio-dub.wav`} className="text-purple-600 underline shrink-0">Download</a>
              </div>
            )}
          </div>

          {/* Cue list */}
          <div className="space-y-2">
            {pageEntries.map((entry, i) => {
              const idx = startIdx + i
              const idEntry = idEntries[idx]
              const register = registers[idx] || ''
              const voiceId = voices[idx] || ''
              const cueAudio = cueAudioCache[idx]
              const isPreviewing = previewingCue === idx

              return (
                <div key={idx} className="rounded-lg border p-2.5 space-y-1.5 hover:border-indigo-300 transition-colors">
                  <div className="flex items-center justify-between gap-2 text-xs text-muted-foreground">
                    <div className="flex items-center gap-2">
                      <span className="font-mono font-bold">#{idx + 1}</span>
                      <span className="font-mono">{formatTs(entry.start)} → {formatTs(entry.end)}</span>
                    </div>
                    <div className="flex items-center gap-1">
                      <button
                        onClick={() => handlePreviewCue(idx)}
                        disabled={isPreviewing}
                        className="text-xs px-2 py-0.5 rounded border bg-background hover:border-purple-400 hover:text-purple-700 dark:hover:text-purple-300 flex items-center gap-1 disabled:opacity-50"
                        title="Generate TTS untuk cue ini + play di browser + cache ke IndexedDB"
                      >
                        {isPreviewing ? (
                          <><Loader2 className="size-3 animate-spin" /> Generating...</>
                        ) : cueAudio ? (
                          <><span className="text-green-600">▶</span> Re-preview</>
                        ) : (
                          <>▶ Preview</>
                        )}
                      </button>
                    </div>
                  </div>
                  {idEntry && (
                    <div className="rounded bg-gray-100 dark:bg-gray-800/50 px-2 py-1">
                      <p className="text-[11px] text-muted-foreground italic">{idEntry.textLines.join(' ')}</p>
                    </div>
                  )}
                  <textarea
                    value={entry.textLines.join('\n')}
                    onChange={e => handleEditJawa(idx, e.target.value)}
                    className="w-full text-sm border rounded px-2 py-1.5 bg-background min-h-[40px] resize-y"
                    rows={Math.max(1, entry.textLines.length)}
                  />
                  {cueAudio && (
                    <div className="rounded bg-purple-50/50 dark:bg-purple-950/20 border border-purple-200 dark:border-purple-800 px-2 py-1.5 flex items-center gap-2">
                      <span className="text-[11px] text-purple-700 dark:text-purple-300 font-mono shrink-0">
                        ✓ {cueAudio.durationSec.toFixed(1)}s · {cueAudio.voice}
                      </span>
                      <audio controls src={cueAudio.url} className="h-7 flex-1 min-w-[150px]" />
                      <button
                        onClick={async () => {
                          if (!projectId) return
                          await deleteCueAudio(projectId, idx)
                          setCueAudioCache(prev => {
                            const updated = { ...prev }
                            delete updated[idx]
                            return updated
                          })
                          refreshAudioCache(projectId)
                          toast.success(`Cue #${idx + 1} cache dihapus`)
                        }}
                        className="text-xs text-red-500 hover:text-red-700 px-1"
                        title="Hapus cache audio cue ini"
                      >
                        ✕
                      </button>
                    </div>
                  )}
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
    </>
  )
}

function formatTs(sec: number): string {
  const h = Math.floor(sec / 3600)
  const m = Math.floor((sec % 3600) / 60)
  const s = Math.floor(sec % 60)
  return `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`
}
