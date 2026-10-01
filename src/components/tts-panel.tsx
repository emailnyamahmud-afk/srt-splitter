'use client'

import { useState, useCallback, useEffect } from 'react'
import {
  AudioLines,
  Download,
  Loader2,
  AlertCircle,
  Volume2,
  Play,
  Key,
  ExternalLink,
  CheckCircle2,
  XCircle,
} from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Label } from '@/components/ui/label'
import { Badge } from '@/components/ui/badge'
import { Progress } from '@/components/ui/progress'
import { Switch } from '@/components/ui/switch'
import { Input } from '@/components/ui/input'
import { toast } from 'sonner'
import {
  narratePart,
  downloadBlob,
  formatDuration,
  revokePreviewUrl,
  OPENAI_VOICES,
  DEFAULT_OPENAI_VOICE,
  getApiKey,
  setApiKey,
  testApiKey,
  type TTSProgress,
  type SplitResult,
} from '@/lib/tts'
import JSZip from 'jszip'

interface TtsPanelProps {
  splitResult: SplitResult
  prefix: string
}

export function TtsPanel({ splitResult, prefix }: TtsPanelProps) {
  const [voice, setVoice] = useState<string>(DEFAULT_OPENAI_VOICE)
  const [respectTiming, setRespectTiming] = useState(true)
  const [progress, setProgress] = useState<TTSProgress>({ stage: 'idle' })
  const [lineProgress, setLineProgress] = useState<{ current: number; total: number; text: string } | null>(null)
  const [activePart, setActivePart] = useState<number | null>(null)
  const [audioCache, setAudioCache] = useState<Record<number, { blob: Blob; durationSec: number; previewUrl: string }>>({})

  // API key state
  const [apiKey, setApiKeyState] = useState<string>('')
  const [showApiKeyInput, setShowApiKeyInput] = useState<boolean>(false)
  const [apiKeyDraft, setApiKeyDraft] = useState<string>('')
  const [isTestingKey, setIsTestingKey] = useState<boolean>(false)
  const [keyTested, setKeyTested] = useState<boolean | null>(null)

  // Load saved API key on mount
  useEffect(() => {
    const saved = getApiKey()
    if (saved) {
      setApiKeyState(saved)
      setApiKeyDraft(saved)
      setKeyTested(true) // assume valid until proven otherwise
    } else {
      setShowApiKeyInput(true) // show input on first visit
    }
  }, [])

  const handleSaveApiKey = useCallback(async (key: string, testIt: boolean = true) => {
    const trimmed = key.trim()
    if (!trimmed) {
      toast.error('API key tidak boleh kosong')
      return
    }
    if (testIt) {
      setIsTestingKey(true)
      setKeyTested(null)
      const tid = toast.loading('Test API key…')
      const result = await testApiKey(trimmed)
      setIsTestingKey(false)
      if (!result.valid) {
        toast.error(`API key gagal: ${result.error}`, { id: tid })
        setKeyTested(false)
        return
      }
      toast.success('API key valid!', { id: tid })
      setKeyTested(true)
    }
    setApiKey(trimmed)
    setApiKeyState(trimmed)
    setShowApiKeyInput(false)
  }, [])

  const handleClearApiKey = useCallback(() => {
    setApiKey('')
    setApiKeyState('')
    setApiKeyDraft('')
    setKeyTested(null)
    setShowApiKeyInput(true)
    toast.info('API key dihapus. Silakan input key baru.')
  }, [])

  const generatePart = useCallback(
    async (partIndex: number) => {
      const part = splitResult.parts[partIndex - 1]
      if (!part) return
      if (!apiKey) {
        toast.error('Set OpenAI API key dulu')
        setShowApiKeyInput(true)
        return
      }
      // Revoke previous preview URL if any (memory cleanup)
      const prev = audioCache[partIndex]
      if (prev?.previewUrl) revokePreviewUrl(prev.previewUrl)

      setActivePart(partIndex)
      setLineProgress(null)
      setProgress({ stage: 'synthesizing', message: `Generating part ${partIndex}…`, percent: 0 })
      const tid = toast.loading(`Generating audio untuk ${prefix}-${String(partIndex).padStart(2, '0')}.srt…`)
      try {
        const result = await narratePart(part, {
          voice,
          apiKey,
          respectTiming,
          onLineProgress: (current, total, text) => setLineProgress({ current, total, text }),
          onStage: (p) => setProgress(p),
        })
        setAudioCache((prev) => ({
          ...prev,
          [partIndex]: {
            blob: result.blob,
            durationSec: result.durationSec,
            previewUrl: result.previewUrl,
          },
        }))
        toast.success(`Part ${partIndex} audio ready (${formatDuration(result.durationSec)}) — bisa preview di bawah`, { id: tid })
      } catch (e) {
        console.error(e)
        toast.error('TTS gagal: ' + (e as Error).message, { id: tid })
      } finally {
        setActivePart(null)
        setLineProgress(null)
      }
    },
    [splitResult, voice, apiKey, respectTiming, prefix, audioCache],
  )

  const generateAll = useCallback(async () => {
    if (!apiKey) {
      toast.error('Set OpenAI API key dulu')
      setShowApiKeyInput(true)
      return
    }
    if (splitResult.parts.length === 0) return

    // Cleanup previous previews
    Object.values(audioCache).forEach((c) => c.previewUrl && revokePreviewUrl(c.previewUrl))
    setAudioCache({})

    setProgress({ stage: 'synthesizing', message: 'Mulai full narration…', percent: 0 })
    setLineProgress(null)
    const tid = toast.loading(`Generating full audio (${splitResult.parts.length} parts)…`)
    try {
      const results: { blob: Blob; durationSec: number; previewUrl: string }[] = []
      for (let i = 0; i < splitResult.parts.length; i++) {
        setActivePart(i + 1)
        const result = await narratePart(splitResult.parts[i], {
          voice,
          apiKey,
          respectTiming,
          onLineProgress: (current, total, text) => setLineProgress({ current, total, text }),
          onStage: (p) => setProgress(p),
        })
        results.push({
          blob: result.blob,
          durationSec: result.durationSec,
          previewUrl: result.previewUrl,
        })
        setAudioCache((prev) => ({
          ...prev,
          [i + 1]: {
            blob: result.blob,
            durationSec: result.durationSec,
            previewUrl: result.previewUrl,
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
  }, [splitResult, voice, apiKey, respectTiming, prefix, audioCache])

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

  const isSynthesizing = progress.stage === 'synthesizing' || progress.stage === 'stitching'
  const hasApiKey = Boolean(apiKey)

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
              Konversi subtitle ke audio narasi. Pakai OpenAI TTS (Indonesia natural). Audio timing di-sync ke SRT. Preview audio sebelum download.
            </CardDescription>
          </div>
          <Badge variant={hasApiKey ? 'secondary' : 'destructive'} className="shrink-0">
            {hasApiKey ? (
              <>
                <CheckCircle2 className="size-3 mr-1" /> API Key Set
              </>
            ) : (
              <>
                <Key className="size-3 mr-1" /> No API Key
              </>
            )}
          </Badge>
        </div>
      </CardHeader>
      <CardContent className="space-y-5">
        {/* API Key section */}
        <div className="rounded-lg border border-amber-200 dark:border-amber-800 p-4 bg-amber-50/30 dark:bg-amber-950/10">
          <div className="flex items-start justify-between gap-3 mb-2">
            <div className="flex-1">
              <h4 className="font-medium text-sm mb-1 flex items-center gap-1.5">
                <Key className="size-3.5 text-amber-600" />
                OpenAI API Key
              </h4>
              <p className="text-xs text-muted-foreground">
                Butuh API key OpenAI untuk TTS. Get free $5 credit di{' '}
                <a
                  href="https://platform.openai.com/api-keys"
                  target="_blank"
                  rel="noreferrer"
                  className="text-amber-700 dark:text-amber-400 underline inline-flex items-center gap-0.5"
                >
                  platform.openai.com <ExternalLink className="size-3" />
                </a>. Key disimpan di browser (localStorage), tidak dikirim ke mana pun.
              </p>
            </div>
            {hasApiKey && (
              <Button size="sm" variant="outline" onClick={handleClearApiKey} className="h-7 text-xs">
                Ganti Key
              </Button>
            )}
          </div>

          {showApiKeyInput && (
            <div className="mt-3 space-y-2">
              <Input
                type="password"
                value={apiKeyDraft}
                onChange={(e) => setApiKeyDraft(e.target.value)}
                placeholder="sk-..."
                className="font-mono text-sm"
              />
              <div className="flex flex-wrap gap-2">
                <Button
                  size="sm"
                  onClick={() => handleSaveApiKey(apiKeyDraft, true)}
                  disabled={isTestingKey || !apiKeyDraft.trim()}
                >
                  {isTestingKey ? (
                    <>
                      <Loader2 className="size-3.5 mr-1 animate-spin" /> Testing…
                    </>
                  ) : (
                    <>
                      <CheckCircle2 className="size-3.5 mr-1" /> Test & Save
                    </>
                  )}
                </Button>
                {apiKeyDraft.trim() && apiKeyDraft !== apiKey && (
                  <Button size="sm" variant="ghost" onClick={() => handleSaveApiKey(apiKeyDraft, false)}>
                    Save tanpa test
                  </Button>
                )}
              </div>
              {keyTested === false && (
                <p className="text-xs text-red-600 flex items-center gap-1">
                  <XCircle className="size-3" /> API key gagal. Cek kembali key kamu.
                </p>
              )}
              {keyTested === true && apiKey && (
                <p className="text-xs text-emerald-600 flex items-center gap-1">
                  <CheckCircle2 className="size-3" /> API key valid.
                </p>
              )}
            </div>
          )}
        </div>

        {/* TTS settings (only when API key is set) */}
        {hasApiKey && (
          <>
            <div className="grid gap-3 sm:grid-cols-2">
              <div>
                <Label htmlFor="openai-voice" className="text-xs">Voice OpenAI TTS</Label>
                <select
                  id="openai-voice"
                  value={voice}
                  onChange={(e) => setVoice(e.target.value)}
                  className="flex h-9 w-full rounded-md border border-input bg-background px-3 py-1 text-xs mt-1"
                >
                  {OPENAI_VOICES.map((v) => (
                    <option key={v.id} value={v.id}>
                      {v.label} — {v.description}
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
            <div className="flex flex-wrap gap-2">
              <Button onClick={generateAll} disabled={isSynthesizing} size="sm">
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
          </>
        )}

        {/* Per-part list with audio preview */}
        {hasApiKey && splitResult.parts.length > 0 && (
          <div className="space-y-2">
            <h4 className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">
              Per Split File — Generate, Preview, Download
            </h4>
            <div className="space-y-3">
              {splitResult.parts.map((part) => {
                const idx = part.index
                const isGenerating = activePart === idx
                const cached = audioCache[idx]
                return (
                  <div
                    key={idx}
                    className="rounded-md border bg-card p-3 space-y-2"
                  >
                    <div className="flex items-center gap-2">
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
                    {/* Audio Preview Player */}
                    {cached && (
                      <div className="mt-2 rounded-md bg-emerald-50/50 dark:bg-emerald-950/20 p-2">
                        <div className="flex items-center gap-1.5 text-xs text-emerald-700 dark:text-emerald-400 mb-1.5">
                          <Play className="size-3" />
                          Preview audio (dengar sebelum download)
                        </div>
                        <audio
                          controls
                          preload="metadata"
                          src={cached.previewUrl}
                          className="w-full h-9"
                        />
                      </div>
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
            <strong>OpenAI TTS:</strong> Butuh API key + internet. Cost: $0.015/1k chars (model tts-1-hd) = ~$1 per 10 menit audio.
            <br />
            <strong>Timing sync:</strong> Audio tiap baris akan dipercepat (max 1.5x) kalau lebih panjang dari cue, atau di-pad silence kalau lebih pendek. Hasil audio = pas dengan timing SRT.
            <br />
            <strong>Preview:</strong> Setelah generate, audio player muncul untuk dengar sebelum download. Tidak perlu download dulu untuk cek hasil.
          </span>
        </div>
      </CardContent>
    </Card>
  )
}
