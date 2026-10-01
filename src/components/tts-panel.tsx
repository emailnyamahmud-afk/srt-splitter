'use client'

import { useState, useCallback, useEffect } from 'react'
import {
  AudioLines,
  Download,
  Loader2,
  AlertCircle,
  Volume2,
  VolumeX,
  Play,
  Square,
} from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Label } from '@/components/ui/label'
import { Badge } from '@/components/ui/badge'
import { Progress } from '@/components/ui/progress'
import { Switch } from '@/components/ui/switch'
import { toast } from 'sonner'
import {
  ensureTTSModel,
  narratePart,
  narrateAllParts,
  downloadBlob,
  formatDuration,
  formatBytes,
  VOICES,
  DEFAULT_VOICE,
  previewWithBrowserTTS,
  stopBrowserTTS,
  ensureBrowserVoicesLoaded,
  hasIndonesianBrowserVoice,
  type TTSProgress,
  type SplitResult,
} from '@/lib/tts'

interface TtsPanelProps {
  splitResult: SplitResult
  prefix: string
}

export function TtsPanel({ splitResult, prefix }: TtsPanelProps) {
  const [voice, setVoice] = useState<string>(DEFAULT_VOICE)
  const [respectTiming, setRespectTiming] = useState(true)
  const [modelReady, setModelReady] = useState(false)
  const [loadingModel, setLoadingModel] = useState(false)
  const [progress, setProgress] = useState<TTSProgress>({ stage: 'idle' })
  const [lineProgress, setLineProgress] = useState<{ current: number; total: number; text: string } | null>(null)
  const [activePart, setActivePart] = useState<number | null>(null)
  const [audioCache, setAudioCache] = useState<Record<number, { blob: Blob; durationSec: number; sampleRate: number }>>({})
  const [fullAudio, setFullAudio] = useState<{ blob: Blob; durationSec: number } | null>(null)

  // Preview mode (Browser SpeechSynthesis) — gratis, instant, no download
  const [browserVoiceURI, setBrowserVoiceURI] = useState<string>('')
  const [isPreviewing, setIsPreviewing] = useState(false)
  const [browserVoices, setBrowserVoices] = useState<{ voiceURI: string; name: string; lang: string }[]>([])
  const [previewRate, setPreviewRate] = useState(1.0)
  const [previewingLineIdx, setPreviewingLineIdx] = useState<number | null>(null)

  // Load browser voices on mount
  useEffect(() => {
    let mounted = true
    ensureBrowserVoicesLoaded().then((voices) => {
      if (!mounted) return
      setBrowserVoices(voices)
      // Default to Indonesian voice if available
      const indoVoice = voices.find((v) => v.lang.toLowerCase().startsWith('id'))
      if (indoVoice) {
        setBrowserVoiceURI(indoVoice.voiceURI)
      } else if (voices.length > 0) {
        setBrowserVoiceURI(voices[0].voiceURI)
      }
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

  const loadModel = useCallback(async () => {
    if (loadingModel || modelReady) return
    setLoadingModel(true)
    const tid = toast.loading('Downloading TTS model (~70 MB, one-time only)…')
    try {
      await ensureTTSModel((p) => {
        setProgress(p)
        if (p.stage === 'loading' && p.percent !== undefined) {
          toast.loading(`Downloading model… ${p.percent.toFixed(0)}%`, { id: tid })
        }
      })
      setModelReady(true)
      toast.success('TTS model ready! Will load instantly next time.', { id: tid })
    } catch (e) {
      console.error(e)
      toast.error('Failed to load TTS model: ' + (e as Error).message, { id: tid })
    } finally {
      setLoadingModel(false)
    }
  }, [loadingModel, modelReady])

  const generatePart = useCallback(
    async (partIndex: number) => {
      const part = splitResult.parts[partIndex - 1]
      if (!part) return
      if (!modelReady) {
        toast.error('Please load the TTS model first.')
        return
      }
      setActivePart(partIndex)
      setLineProgress(null)
      setProgress({ stage: 'synthesizing', message: `Generating part ${partIndex}…`, percent: 0 })
      const tid = toast.loading(`Generating audio for ${prefix}-${String(partIndex).padStart(2, '0')}.srt…`)
      try {
        const result = await narratePart(part, {
          voice,
          respectTiming,
          onLineProgress: (current, total, text) => {
            setLineProgress({ current, total, text })
          },
          onStage: (p) => {
            setProgress(p)
          },
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
        toast.error('TTS failed: ' + (e as Error).message, { id: tid })
      } finally {
        setActivePart(null)
        setLineProgress(null)
      }
    },
    [splitResult, modelReady, voice, respectTiming, prefix],
  )

  const generateAll = useCallback(async () => {
    if (!modelReady) {
      toast.error('Please load the TTS model first.')
      return
    }
    if (splitResult.parts.length === 0) return
    setProgress({ stage: 'synthesizing', message: 'Starting full narration…', percent: 0 })
    setLineProgress(null)
    const tid = toast.loading(`Generating full audio (${splitResult.parts.length} parts)…`)
    try {
      const results: { blob: Blob; durationSec: number; sampleRate: number }[] = []
      for (let i = 0; i < splitResult.parts.length; i++) {
        setActivePart(i + 1)
        const result = await narratePart(splitResult.parts[i], {
          voice,
          respectTiming,
          onLineProgress: (current, total, text) => {
            setLineProgress({ current, total, text })
          },
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
      // Concatenate all parts into one big WAV
      // (simple: just download each separately — concatenation requires decode which is heavier)
      // For "full audio" we offer ZIP of all parts:
      const JSZip = (await import('jszip')).default
      const zip = new JSZip()
      let totalDuration = 0
      for (let i = 0; i < results.length; i++) {
        const filename = `${prefix}-${String(i + 1).padStart(2, '0')}.wav`
        const buf = await results[i].blob.arrayBuffer()
        zip.file(filename, buf)
        totalDuration += results[i].durationSec
      }
      const zipBlob = await zip.generateAsync({ type: 'blob', compression: 'STORE' })
      setFullAudio({ blob: zipBlob, durationSec: totalDuration })
      toast.success(`Full narration ready (${formatDuration(totalDuration)} total)`, { id: tid })
    } catch (e) {
      console.error(e)
      toast.error('Full narration failed: ' + (e as Error).message, { id: tid })
    } finally {
      setActivePart(null)
      setLineProgress(null)
    }
  }, [splitResult, modelReady, voice, respectTiming, prefix])

  const downloadPartAudio = useCallback(
    (partIndex: number) => {
      const cached = audioCache[partIndex]
      if (!cached) return
      const filename = `${prefix}-${String(partIndex).padStart(2, '0')}.wav`
      downloadBlob(filename, cached.blob)
      toast.success(`Downloading ${filename}`)
    },
    [audioCache, prefix],
  )

  const downloadFullAudio = useCallback(() => {
    if (!fullAudio) return
    downloadBlob(`${prefix}-audio.zip`, fullAudio.blob)
    toast.success(`Downloading ${prefix}-audio.zip`)
  }, [fullAudio, prefix])

  const isLoading = loadingModel || (progress.stage === 'loading' && progress.percent !== undefined && progress.percent < 100)
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
              Konversi subtitle ke audio narasi. Pakai model MMS-TTS English (VITS, Meta) — text Indonesia akan terbaca dengan accent English. 100% offline setelah download.
            </CardDescription>
          </div>
          {modelReady && (
            <Badge variant="secondary" className="shrink-0">
              <Volume2 className="size-3 mr-1" /> Model Ready
            </Badge>
          )}
        </div>
      </CardHeader>
      <CardContent className="space-y-5">
        {/* Preview Mode - Browser SpeechSynthesis */}
        <div className="rounded-lg border border-emerald-200 dark:border-emerald-800/50 p-4 bg-emerald-50/30 dark:bg-emerald-950/10">
          <div className="flex items-start justify-between gap-3 mb-3">
            <div className="flex-1">
              <h4 className="font-medium text-sm mb-1 flex items-center gap-1.5">
                <Play className="size-3.5 text-emerald-600" />
                Preview Mode (Instant, Gratis)
              </h4>
              <p className="text-xs text-muted-foreground">
                Dengar langsung pakai voice browser. Di macOS ada voice Indonesia "Damayanti". Tidak bisa export ke file — untuk export pakai mode di bawah.
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
                +{splitResult.parts[0].entries.length - 5} baris lainnya (lihat di Per Split File)
              </span>
            )}
          </div>
        </div>

        {/* Model load section - Export mode */}
        {!modelReady && (
          <div className="rounded-lg border border-purple-200 dark:border-purple-800 p-4 bg-white/50 dark:bg-slate-900/50">
            <div className="flex items-start justify-between gap-3">
              <div className="flex-1">
                <h4 className="font-medium text-sm mb-1">Step 1: Download Model (untuk Export)</h4>
                <p className="text-xs text-muted-foreground">
                  One-time download (~70 MB) — model MMS-TTS English (VITS, Meta). Text Indonesia akan terbaca dengan accent English. Setelah download tersimpan di browser, offline selamanya.
                </p>
              </div>
              <Button size="sm" onClick={loadModel} disabled={isLoading}>
                {loadingModel ? (
                  <>
                    <Loader2 className="size-3.5 mr-1 animate-spin" /> Loading…
                  </>
                ) : (
                  <>
                    <Download className="size-3.5 mr-1" /> Download Model
                  </>
                )}
              </Button>
            </div>
            {loadingModel && progress.percent !== undefined && progress.percent < 100 && (
              <div className="mt-3">
                <Progress value={progress.percent} className="h-2" />
                <p className="text-xs text-muted-foreground mt-1.5">
                  {progress.message ?? 'Loading…'}{' '}
                  {progress.modelBytesLoaded && progress.modelBytesTotal
                    ? `${formatBytes(progress.modelBytesLoaded)} / ${formatBytes(progress.modelBytesTotal)}`
                    : `${progress.percent.toFixed(0)}%`}
                </p>
              </div>
            )}
          </div>
        )}

        {/* TTS settings (only when model ready) */}
        {modelReady && (
          <>
            <div className="grid gap-4 sm:grid-cols-2">
              <div className="space-y-2">
                <Label htmlFor="voice" className="text-sm font-medium">
                  Voice
                </Label>
                <select
                  id="voice"
                  value={voice}
                  onChange={(e) => setVoice(e.target.value)}
                  className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
                >
                  {VOICES.map((v) => (
                    <option key={v.id} value={v.id}>
                      {v.label}
                    </option>
                  ))}
                </select>
              </div>
              <div className="flex items-end justify-between gap-3">
                <div>
                  <Label htmlFor="timing" className="text-sm font-medium">
                    Sinkron dengan timing SRT
                  </Label>
                  <p className="text-xs text-muted-foreground mt-1">
                    ON: audio dipadding sesuai waktu mulai/akhir tiap baris.
                    OFF: baris-baris dibaca berurutan tanpa jeda.
                  </p>
                </div>
                <Switch id="timing" checked={respectTiming} onCheckedChange={setRespectTiming} />
              </div>
            </div>

            {/* Action buttons */}
            <div className="flex flex-wrap gap-2">
              <Button onClick={generateAll} disabled={isSynthesizing} size="sm">
                {isSynthesizing ? (
                  <>
                    <Loader2 className="size-3.5 mr-1 animate-spin" /> Generating…
                  </>
                ) : (
                  <>
                    <AudioLines className="size-3.5 mr-1" /> Generate Full Audio ({splitResult.parts.length} parts)
                  </>
                )}
              </Button>
              {fullAudio && (
                <Button onClick={downloadFullAudio} variant="outline" size="sm">
                  <Download className="size-3.5 mr-1" /> Download ZIP ({formatDuration(fullAudio.durationSec)})
                </Button>
              )}
            </div>

            {/* Progress display */}
            {(isSynthesizing || lineProgress) && (
              <div className="rounded-md border bg-white/50 dark:bg-slate-900/50 p-3 space-y-2">
                {progress.message && (
                  <p className="text-sm font-medium">{progress.message}</p>
                )}
                {progress.percent !== undefined && (
                  <Progress value={progress.percent} className="h-2" />
                )}
                {lineProgress && (
                  <p className="text-xs text-muted-foreground">
                    Line {lineProgress.current}/{lineProgress.total}: "{lineProgress.text.slice(0, 60)}{lineProgress.text.length > 60 ? '…' : ''}"
                  </p>
                )}
              </div>
            )}
          </>
        )}

        {/* Per-part list */}
        {modelReady && splitResult.parts.length > 0 && (
          <div className="space-y-2">
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
                      disabled={isSynthesizing}
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
        )}

        {/* Notice */}
        <div className="text-xs text-muted-foreground flex items-start gap-2 pt-1">
          <AlertCircle className="size-3.5 mt-0.5 shrink-0" />
          <span>
            TTS berjalan 100% di browser. Untuk durasi panjang (3-4 jam),
            biarkan tab terbuka. Mac dengan CPU idle dapat memproses ~30-60 detik
            audio per menit, jadi 3 jam subtitle butuh ~3-6 menit untuk selesai.
          </span>
        </div>
      </CardContent>
    </Card>
  )
}

// Suppress unused warning for VolumeX import (kept for future mute toggle)
export const _VolumeX = VolumeX
