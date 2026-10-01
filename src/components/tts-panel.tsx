'use client'

import { useState, useCallback, useEffect } from 'react'
import {
  AudioLines,
  Download,
  Loader2,
  AlertCircle,
  Volume2,
  Play,
  Square,
  Wifi,
  WifiOff,
} from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Label } from '@/components/ui/label'
import { Badge } from '@/components/ui/badge'
import { Progress } from '@/components/ui/progress'
import { Switch } from '@/components/ui/switch'
import { toast } from 'sonner'
import {
  narratePart,
  downloadBlob,
  formatDuration,
  EDGE_VOICES,
  DEFAULT_EDGE_VOICE,
  previewWithBrowserTTS,
  stopBrowserTTS,
  ensureBrowserVoicesLoaded,
  type TTSProgress,
  type SplitResult,
} from '@/lib/tts'
import JSZip from 'jszip'

interface TtsPanelProps {
  splitResult: SplitResult
  prefix: string
}

export function TtsPanel({ splitResult, prefix }: TtsPanelProps) {
  const [voice, setVoice] = useState<string>(DEFAULT_EDGE_VOICE)
  const [respectTiming, setRespectTiming] = useState(true)
  const [progress, setProgress] = useState<TTSProgress>({ stage: 'idle' })
  const [lineProgress, setLineProgress] = useState<{ current: number; total: number; text: string } | null>(null)
  const [activePart, setActivePart] = useState<number | null>(null)
  const [audioCache, setAudioCache] = useState<Record<number, { blob: Blob; durationSec: number; sampleRate: number }>>({})
  const [isOnline, setIsOnline] = useState(true)

  // Preview mode (Browser SpeechSynthesis) — instant, no internet
  const [browserVoiceURI, setBrowserVoiceURI] = useState<string>('')
  const [isPreviewing, setIsPreviewing] = useState(false)
  const [browserVoices, setBrowserVoices] = useState<{ voiceURI: string; name: string; lang: string }[]>([])
  const [previewRate, setPreviewRate] = useState(1.0)
  const [previewingLineIdx, setPreviewingLineIdx] = useState<number | null>(null)

  // Track online status (Edge TTS needs internet)
  useEffect(() => {
    const updateOnline = () => setIsOnline(navigator.onLine)
    updateOnline()
    window.addEventListener('online', updateOnline)
    window.addEventListener('offline', updateOnline)
    return () => {
      window.removeEventListener('online', updateOnline)
      window.removeEventListener('offline', updateOnline)
    }
  }, [])

  // Load browser voices for Preview Mode
  useEffect(() => {
    let mounted = true
    ensureBrowserVoicesLoaded().then((voices) => {
      if (!mounted) return
      setBrowserVoices(voices)
      const indoVoice = voices.find((v) => v.lang.toLowerCase().startsWith('id'))
      if (indoVoice) setBrowserVoiceURI(indoVoice.voiceURI)
      else if (voices.length > 0) setBrowserVoiceURI(voices[0].voiceURI)
    })
    return () => {
      mounted = false
      stopBrowserTTS()
    }
  }, [])

  const previewLine = useCallback(
    async (text: string, lineIdx?: number) => {
      if (!text.trim()) return
      try {
        setIsPreviewing(true)
        setPreviewingLineIdx(lineIdx ?? null)
        await previewWithBrowserTTS(text, browserVoiceURI, previewRate)
      } catch (e) {
        toast.error('Preview gagal: ' + (e as Error).message)
      } finally {
        setIsPreviewing(false)
        setPreviewingLineIdx(null)
      }
    },
    [browserVoiceURI, previewRate],
  )

  const stopPreview = useCallback(() => {
    stopBrowserTTS()
    setIsPreviewing(false)
    setPreviewingLineIdx(null)
  }, [])

  const generatePart = useCallback(
    async (partIndex: number) => {
      const part = splitResult.parts[partIndex - 1]
      if (!part) return
      if (!isOnline) {
        toast.error('Edge TTS butuh internet. Cek koneksi kamu.')
        return
      }
      setActivePart(partIndex)
      setLineProgress(null)
      setProgress({ stage: 'synthesizing', message: `Generating part ${partIndex}…`, percent: 0 })
      const tid = toast.loading(`Generating audio untuk ${prefix}-${String(partIndex).padStart(2, '0')}.srt…`)
      try {
        const result = await narratePart(part, {
          voice,
          respectTiming,
          onLineProgress: (current, total, text) => setLineProgress({ current, total, text }),
          onStage: (p) => setProgress(p),
        })
        setAudioCache((prev) => ({
          ...prev,
          [partIndex]: {
            blob: result.blob,
            durationSec: result.durationSec,
            sampleRate: result.sampleRate,
          },
        }))
        toast.success(`Part ${partIndex} audio ready (${formatDuration(result.durationSec)})`, { id: tid })
      } catch (e) {
        console.error(e)
        toast.error('TTS gagal: ' + (e as Error).message, { id: tid })
      } finally {
        setActivePart(null)
        setLineProgress(null)
      }
    },
    [splitResult, voice, respectTiming, prefix, isOnline],
  )

  const generateAll = useCallback(async () => {
    if (!isOnline) {
      toast.error('Edge TTS butuh internet. Cek koneksi kamu.')
      return
    }
    if (splitResult.parts.length === 0) return
    setProgress({ stage: 'synthesizing', message: 'Mulai full narration…', percent: 0 })
    setLineProgress(null)
    const tid = toast.loading(`Generating full audio (${splitResult.parts.length} parts)…`)
    try {
      const results: { blob: Blob; durationSec: number; sampleRate: number }[] = []
      for (let i = 0; i < splitResult.parts.length; i++) {
        setActivePart(i + 1)
        const result = await narratePart(splitResult.parts[i], {
          voice,
          respectTiming,
          onLineProgress: (current, total, text) => setLineProgress({ current, total, text }),
          onStage: (p) => setProgress(p),
        })
        results.push({
          blob: result.blob,
          durationSec: result.durationSec,
          sampleRate: result.sampleRate,
        })
        setAudioCache((prev) => ({
          ...prev,
          [i + 1]: {
            blob: result.blob,
            durationSec: result.durationSec,
            sampleRate: result.sampleRate,
          },
        }))
        toast.loading(`Part ${i + 1}/${splitResult.parts.length} done`, { id: tid })
      }
      // Bundle all parts into ZIP
      const zip = new JSZip()
      let totalDuration = 0
      for (let i = 0; i < results.length; i++) {
        const filename = `${prefix}-${String(i + 1).padStart(2, '0')}.wav`
        const buf = await results[i].blob.arrayBuffer()
        zip.file(filename, buf)
        totalDuration += results[i].durationSec
      }
      const zipBlob = await zip.generateAsync({ type: 'blob', compression: 'STORE' })
      downloadBlob(`${prefix}-audio.zip`, zipBlob)
      toast.success(`Full narration (${formatDuration(totalDuration)}) — ZIP downloaded`, { id: tid })
    } catch (e) {
      console.error(e)
      toast.error('Full narration gagal: ' + (e as Error).message, { id: tid })
    } finally {
      setActivePart(null)
      setLineProgress(null)
    }
  }, [splitResult, voice, respectTiming, prefix, isOnline])

  const downloadPartAudio = useCallback(
    (partIndex: number) => {
      const cached = audioCache[partIndex]
      if (!cached) return
      const filename = `${prefix}-${String(partIndex).padStart(2, '0')}.wav`
      downloadBlob(filename, cached.blob)
      toast.success(`Mengunduh ${filename}`)
    },
    [audioCache, prefix],
  )

  const downloadAllAsZip = useCallback(async () => {
    if (Object.keys(audioCache).length === 0) {
      toast.error('Belum ada audio yang di-generate. Klik generate dulu.')
      return
    }
    const zip = new JSZip()
    let totalDuration = 0
    for (const [idxStr, data] of Object.entries(audioCache)) {
      const idx = Number(idxStr)
      const filename = `${prefix}-${String(idx).padStart(2, '0')}.wav`
      const buf = await data.blob.arrayBuffer()
      zip.file(filename, buf)
      totalDuration += data.durationSec
    }
    const zipBlob = await zip.generateAsync({ type: 'blob', compression: 'STORE' })
    downloadBlob(`${prefix}-audio.zip`, zipBlob)
    toast.success(`Downloaded ZIP (${Object.keys(audioCache).length} files, ${formatDuration(totalDuration)})`)
  }, [audioCache, prefix])

  const isSynthesizing = progress.stage === 'synthesizing' || progress.stage === 'stitching'

  return (
    <Card className="border-purple-200 dark:border-purple-900/50 bg-purple-50/30 dark:bg-purple-950/10">
      <CardHeader>
        <div className="flex items-start justify-between gap-3">
          <div>
            <CardTitle className="text-lg flex items-center gap-2">
              <AudioLines className="size-5 text-purple-600" />
              Generate Audio (TTS)
            </CardTitle>
            <CardDescription className="mt-1">
              Konversi subtitle ke audio. Pakai Microsoft Edge TTS (neural voices, gratis, native Indonesia). Audio timing di-sync ke SRT.
            </CardDescription>
          </div>
          <Badge variant={isOnline ? 'secondary' : 'destructive'} className="shrink-0">
            {isOnline ? (
              <>
                <Wifi className="size-3 mr-1" /> Online
              </>
            ) : (
              <>
                <WifiOff className="size-3 mr-1" /> Offline
              </>
            )}
          </Badge>
        </div>
      </CardHeader>
      <CardContent className="space-y-5">
        {/* Preview Mode - Browser SpeechSynthesis */}
        <div className="rounded-lg border border-emerald-200 dark:border-emerald-800/50 p-4 bg-emerald-50/30 dark:bg-emerald-950/10">
          <div className="flex items-start justify-between gap-3 mb-3">
            <div className="flex-1">
              <h4 className="font-medium text-sm mb-1 flex items-center gap-1.5">
                <Play className="size-3.5 text-emerald-600" />
                Preview Mode (Instant, Offline)
              </h4>
              <p className="text-xs text-muted-foreground">
                Dengar langsung pakai voice browser (di macOS: Damayanti Indonesia native). Tidak butuh internet, tidak bisa export ke file.
              </p>
            </div>
            {isPreviewing && (
              <Button size="sm" variant="outline" onClick={stopPreview}>
                <Square className="size-3.5 mr-1" /> Stop
              </Button>
            )}
          </div>
          <div className="grid gap-3 sm:grid-cols-2">
            <div>
              <Label htmlFor="browser-voice" className="text-xs">Voice browser</Label>
              <select
                id="browser-voice"
                value={browserVoiceURI}
                onChange={(e) => setBrowserVoiceURI(e.target.value)}
                className="flex h-9 w-full rounded-md border border-input bg-background px-3 py-1 text-xs mt-1"
              >
                {browserVoices.length === 0 && <option>Loading voices…</option>}
                {browserVoices.map((v) => (
                  <option key={v.voiceURI} value={v.voiceURI}>
                    {v.name} ({v.lang}){v.lang.toLowerCase().startsWith('id') ? ' ★' : ''}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <Label htmlFor="preview-rate" className="text-xs">Speed: {previewRate.toFixed(1)}x</Label>
              <input
                id="preview-rate"
                type="range"
                min={0.5}
                max={2}
                step={0.1}
                value={previewRate}
                onChange={(e) => setPreviewRate(Number(e.target.value))}
                className="w-full mt-2"
              />
            </div>
          </div>
          <div className="mt-3 flex flex-wrap gap-2">
            {splitResult.parts[0]?.entries.slice(0, 5).map((entry, i) => {
              const text = entry.textLines.join(' ').trim()
              if (!text) return null
              return (
                <Button
                  key={i}
                  size="sm"
                  variant="outline"
                  disabled={isPreviewing}
                  onClick={() => previewLine(text, i)}
                  className="h-7 text-xs"
                >
                  {isPreviewing && previewingLineIdx === i ? (
                    <Loader2 className="size-3 mr-1 animate-spin" />
                  ) : (
                    <Play className="size-3 mr-1" />
                  )}
                  Baris {i + 1}
                </Button>
              )
            })}
            {splitResult.parts[0] && splitResult.parts[0].entries.length > 5 && (
              <span className="text-xs text-muted-foreground self-center">
                +{splitResult.parts[0].entries.length - 5} baris lainnya
              </span>
            )}
          </div>
        </div>

        {/* Export Mode - Edge TTS */}
        <div className="rounded-lg border border-purple-200 dark:border-purple-800 p-4 bg-white/50 dark:bg-slate-900/50">
          <div className="flex items-start justify-between gap-3 mb-3">
            <div className="flex-1">
              <h4 className="font-medium text-sm mb-1 flex items-center gap-1.5">
                <Volume2 className="size-3.5 text-purple-600" />
                Export Mode (Edge TTS, native Indonesia)
              </h4>
              <p className="text-xs text-muted-foreground">
                Microsoft Edge TTS neural voices (id-ID-Gadis/Ardi) — kualitas cloud, gratis. Audio timing di-sync ke SRT. Butuh internet.
              </p>
            </div>
          </div>

          <div className="grid gap-3 sm:grid-cols-2 mb-3">
            <div>
              <Label htmlFor="edge-voice" className="text-xs">Voice Edge TTS</Label>
              <select
                id="edge-voice"
                value={voice}
                onChange={(e) => setVoice(e.target.value)}
                className="flex h-9 w-full rounded-md border border-input bg-background px-3 py-1 text-xs mt-1"
              >
                {EDGE_VOICES.map((v) => (
                  <option key={v.name} value={v.name}>
                    {v.label}
                  </option>
                ))}
              </select>
            </div>
            <div className="flex items-end justify-between gap-3">
              <div>
                <Label htmlFor="timing" className="text-xs">Sync timing ke SRT</Label>
                <p className="text-xs text-muted-foreground mt-1">
                  ON: audio dipas/dipercepat sesuai cue. OFF: baris dibaca back-to-back.
                </p>
              </div>
              <Switch id="timing" checked={respectTiming} onCheckedChange={setRespectTiming} />
            </div>
          </div>

          {/* Action buttons */}
          <div className="flex flex-wrap gap-2 mb-3">
            <Button onClick={generateAll} disabled={isSynthesizing || !isOnline} size="sm">
              {isSynthesizing ? (
                <>
                  <Loader2 className="size-3.5 mr-1 animate-spin" /> Generating…
                </>
              ) : (
                <>
                  <AudioLines className="size-3.5 mr-1" /> Generate & Download ZIP ({splitResult.parts.length} parts)
                </>
              )}
            </Button>
            {Object.keys(audioCache).length > 0 && (
              <Button onClick={downloadAllAsZip} variant="outline" size="sm">
                <Download className="size-3.5 mr-1" /> Download ZIP ({Object.keys(audioCache).length} files)
              </Button>
            )}
          </div>

          {/* Progress */}
          {(isSynthesizing || lineProgress) && (
            <div className="rounded-md border bg-white/50 dark:bg-slate-900/50 p-3 space-y-2">
              {progress.message && <p className="text-sm font-medium">{progress.message}</p>}
              {progress.percent !== undefined && <Progress value={progress.percent} className="h-2" />}
              {lineProgress && (
                <p className="text-xs text-muted-foreground">
                  Baris {lineProgress.current}/{lineProgress.total}: "{lineProgress.text.slice(0, 60)}{lineProgress.text.length > 60 ? '…' : ''}"
                </p>
              )}
            </div>
          )}

          {/* Per-part list */}
          <div className="space-y-2 mt-3">
            <h4 className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">
              Per Split File
            </h4>
            <div className="max-h-80 overflow-y-auto pr-1 space-y-2">
              {splitResult.parts.map((part) => {
                const idx = part.index
                const isGenerating = activePart === idx
                const cached = audioCache[idx]
                return (
                  <div
                    key={idx}
                    className="flex items-center gap-2 p-2.5 rounded-md border bg-card hover:shadow-sm transition-shadow"
                  >
                    <div className="size-8 rounded-md bg-purple-100 dark:bg-purple-950/40 flex items-center justify-center shrink-0">
                      <span className="text-xs font-bold text-purple-700 dark:text-purple-400">
                        {String(idx).padStart(2, '0')}
                      </span>
                    </div>
                    <div className="min-w-0 flex-1">
                      <div className="text-sm font-medium truncate">
                        {prefix}-{String(idx).padStart(2, '0')}.wav
                      </div>
                      <div className="text-xs text-muted-foreground">
                        {part.entryCount} baris • {formatDuration(part.endSec - part.startSec)} durasi
                        {cached && <span className="ml-2 text-purple-600">✓ {formatDuration(cached.durationSec)} audio</span>}
                      </div>
                    </div>
                    <Button
                      size="sm"
                      variant="outline"
                      disabled={isSynthesizing || !isOnline}
                      onClick={() => generatePart(idx)}
                      className="h-8"
                    >
                      {isGenerating ? (
                        <Loader2 className="size-3 animate-spin" />
                      ) : (
                        <AudioLines className="size-3" />
                      )}
                    </Button>
                    {cached && (
                      <Button
                        size="sm"
                        variant="ghost"
                        onClick={() => downloadPartAudio(idx)}
                        className="h-8"
                      >
                        <Download className="size-3" />
                      </Button>
                    )}
                  </div>
                )
              })}
            </div>
          </div>
        </div>

        {/* Notice */}
        <div className="text-xs text-muted-foreground flex items-start gap-2 pt-1">
          <AlertCircle className="size-3.5 mt-0.5 shrink-0" />
          <span>
            <strong>Timing sync:</strong> Audio tiap baris akan dipercepat (max 1.5x) kalau lebih panjang dari cue, atau diberi silence kalau lebih pendek. Hasil audio = pas dengan timing SRT asli.
            <br />
            <strong>Internet:</strong> Edge TTS butuh internet (cloud-based). Preview Mode bisa offline.
            <br />
            <strong>Durasi panjang (3-4 jam):</strong> Bisa generate full durasi. Mac idle bisa proses ~30-60 detik audio per menit.
          </span>
        </div>
      </CardContent>
    </Card>
  )
}
