'use client'

import { useState, useCallback, useMemo } from 'react'
import {
  Mic,
  Download,
  Loader2,
  AlertCircle,
  Play,
} from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Label } from '@/components/ui/label'
import { Badge } from '@/components/ui/badge'
import { Progress } from '@/components/ui/progress'
import { Textarea } from '@/components/ui/textarea'
import { toast } from 'sonner'
import {
  textToAudio,
  downloadBlob,
  formatDuration,
  formatBytes,
  estimateDuration,
  splitTextIntoChunks,
  type TTSProgress,
} from '@/lib/tts-text'
import { EDGE_VOICES, DEFAULT_EDGE_VOICE } from '@/lib/edge-tts'

const STORAGE_KEY = 'srt-splitter-tts-text-v1'

export function TtsTextPanel() {
  const [text, setText] = useState<string>('')
  const [voice, setVoice] = useState<string>('jv-ID-SitiNeural')
  const [speed, setSpeed] = useState<number>(1.0)
  const [progress, setProgress] = useState<TTSProgress>({ stage: 'idle' })
  const [isGenerating, setIsGenerating] = useState(false)
  const [audioResult, setAudioResult] = useState<{ blob: Blob; durationSec: number; previewUrl: string; size: number } | null>(null)

  // Load saved text on mount
  useMemo(() => {
    if (typeof window === 'undefined') return
    const saved = localStorage.getItem(STORAGE_KEY)
    if (saved) setText(saved)
  }, [])

  // Save text to localStorage
  const handleTextChange = (value: string) => {
    setText(value)
    if (value.trim()) {
      try { localStorage.setItem(STORAGE_KEY, value) } catch {}
    } else {
      try { localStorage.removeItem(STORAGE_KEY) } catch {}
    }
  }

  const estDuration = estimateDuration(text)
  const chunks = useMemo(() => text.trim() ? splitTextIntoChunks(text.trim()) : [], [text])

  const handleGenerate = useCallback(async () => {
    if (!text.trim()) {
      toast.error('Text tidak boleh kosong')
      return
    }
    setIsGenerating(true)
    setAudioResult(null)
    setProgress({ stage: 'chunking', message: 'Membagi text…' })
    const tid = toast.loading('Memulai generate…')
    try {
      const result = await textToAudio(
        { text: text.trim(), voice, speed },
        (p) => {
          setProgress(p)
          if (p.stage === 'synthesizing' && p.currentChunk && p.totalChunks) {
            toast.loading(`Chunk ${p.currentChunk}/${p.totalChunks}…`, { id: tid })
          }
        }
      )
      setAudioResult({
        blob: result.blob,
        durationSec: result.durationSec,
        previewUrl: result.previewUrl,
        size: result.blob.size,
      })
      toast.success(`Audio ready (${formatDuration(result.durationSec)}, ${formatBytes(result.blob.size)})`, { id: tid })
    } catch (e) {
      console.error(e)
      toast.error('TTS gagal: ' + (e as Error).message, { id: tid })
    } finally {
      setIsGenerating(false)
    }
  }, [text, voice, speed])

  const handleDownload = useCallback(() => {
    if (!audioResult) return
    const filename = `tts-jawa-${Date.now()}.wav`
    downloadBlob(filename, audioResult.blob)
    toast.success(`Download ${filename}`)
  }, [audioResult])

  return (
    <Card className="border-teal-200 dark:border-teal-900/50 bg-teal-50/30 dark:bg-teal-950/10">
      <CardHeader>
        <div className="flex items-start justify-between gap-3">
          <div>
            <CardTitle className="text-lg flex items-center gap-2">
              <Mic className="size-5 text-teal-600" />
              TTS Text ke Audio
            </CardTitle>
            <CardDescription className="mt-1">
              Paste naskah (krama inggil, pidato, panyandra, narasi) → generate audio. Support hingga 100,000 karakter.
            </CardDescription>
          </div>
          {text.trim() && (
            <Badge variant="secondary" className="shrink-0">
              {text.length.toLocaleString()} char
            </Badge>
          )}
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* Textarea */}
        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <Label htmlFor="tts-text" className="text-xs">Naskah (bahasa Jawa/Indonesia)</Label>
            <span className="text-xs text-muted-foreground">
              {text.length.toLocaleString()} / 100,000 karakter
            </span>
          </div>
          <Textarea
            id="tts-text"
            value={text}
            onChange={(e) => handleTextChange(e.target.value.slice(0, 100000))}
            placeholder={`Bapak-bapak, ibu-ibu ingkang kinurmatan, saha para tamu ingkang dipun hormati…

Monggo, kula aturaken panyandra ing dinten menika...

(Paste naskah Jawa krama inggil di sini)`}
            className="min-h-[200px] font-mono text-sm"
            maxLength={100000}
          />
        </div>

        {/* Voice + Speed */}
        <div className="grid gap-3 sm:grid-cols-2">
          <div>
            <Label htmlFor="tts-voice" className="text-xs">Voice</Label>
            <select
              id="tts-voice"
              value={voice}
              onChange={(e) => setVoice(e.target.value)}
              className="flex h-9 w-full rounded-md border border-input bg-background px-3 py-1 text-xs mt-1"
            >
              <optgroup label="🇮🇩 Jawa">
                <option value="jv-ID-SitiNeural">Siti (Perempuan, Jawa)</option>
                <option value="jv-ID-DimasNeural">Dimas (Laki-laki, Jawa)</option>
              </optgroup>
              <optgroup label="🇮🇩 Indonesia">
                <option value="id-ID-GadisNeural">Gadis (Perempuan, Indonesia)</option>
                <option value="id-ID-ArdiNeural">Ardi (Laki-laki, Indonesia)</option>
              </optgroup>
            </select>
          </div>
          <div>
            <Label htmlFor="tts-speed" className="text-xs">Kecepatan</Label>
            <select
              id="tts-speed"
              value={speed}
              onChange={(e) => setSpeed(Number(e.target.value))}
              className="flex h-9 w-full rounded-md border border-input bg-background px-3 py-1 text-xs mt-1"
            >
              <option value={1.0}>1.0x — Natural</option>
              <option value={1.25}>1.25x — 25% lebih cepat</option>
              <option value={1.5}>1.5x — 50% lebih cepat</option>
              <option value={2.0}>2.0x — 2x lebih cepat</option>
            </select>
          </div>
        </div>

        {/* Estimasi */}
        {text.trim() && (
          <div className="flex flex-wrap gap-2 text-xs text-muted-foreground">
            <Badge variant="outline" className="text-xs">
              Estimasi: ~{formatDuration(estDuration)}
            </Badge>
            {chunks.length > 1 && (
              <Badge variant="outline" className="text-xs">
                {chunks.length} chunks
              </Badge>
            )}
          </div>
        )}

        {/* Generate button */}
        <div className="flex flex-wrap gap-2">
          <Button onClick={handleGenerate} disabled={isGenerating || !text.trim()} size="sm">
            {isGenerating ? (
              <>
                <Loader2 className="size-3.5 mr-1 animate-spin" /> Generating…
              </>
            ) : (
              <>
                <Mic className="size-3.5 mr-1" /> Generate Audio
              </>
            )}
          </Button>
          {audioResult && (
            <Button onClick={handleDownload} variant="outline" size="sm">
              <Download className="size-3.5 mr-1" /> Download WAV ({formatBytes(audioResult.size)})
            </Button>
          )}
        </div>

        {/* Progress */}
        {(isGenerating || progress.stage !== 'idle') && progress.message && (
          <div className="rounded-md border bg-white/50 dark:bg-slate-900/50 p-3 space-y-2">
            <p className="text-sm font-medium">{progress.message}</p>
            {progress.percent !== undefined && <Progress value={progress.percent} className="h-2" />}
          </div>
        )}

        {/* Audio Preview */}
        {audioResult && (
          <div className="rounded-md bg-emerald-50/50 dark:bg-emerald-950/20 p-3">
            <div className="flex items-center gap-1.5 text-xs text-emerald-700 dark:text-emerald-400 mb-2">
              <Play className="size-3" /> Preview audio ({formatDuration(audioResult.durationSec)})
            </div>
            <audio
              controls
              preload="metadata"
              src={audioResult.previewUrl}
              className="w-full h-9"
            />
          </div>
        )}

        {/* Notice */}
        <div className="text-xs text-muted-foreground flex items-start gap-2">
          <AlertCircle className="size-3.5 mt-0.5 shrink-0" />
          <span>
            Text di-split per 4500 karakter (limit Edge TTS), lalu digabung dengan crossfade. Naskah tersimpan di browser (localStorage).
          </span>
        </div>
      </CardContent>
    </Card>
  )
}
