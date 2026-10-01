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
  EDGE_VOICES,
  DEFAULT_EDGE_VOICE,
  OPENAI_VOICES,
  DEFAULT_OPENAI_VOICE,
  OPENROUTER_MODELS,
  DEFAULT_OPENROUTER_MODEL,
  getOpenAIKey,
  setOpenAIKey,
  testOpenAIKey,
  getOpenRouterKey,
  setOpenRouterKey,
  testOpenRouterKey,
  getEdgeProxyUrl,
  setEdgeProxyUrl,
  type TTSProgress,
  type SplitResult,
  type Provider,
} from '@/lib/tts'
import JSZip from 'jszip'

interface TtsPanelProps {
  splitResult: SplitResult
  prefix: string
}

export function TtsPanel({ splitResult, prefix }: TtsPanelProps) {
  // Provider selection
  const [provider, setProvider] = useState<Provider>('edge')

  // Voice/model per provider
  const [edgeVoice, setEdgeVoice] = useState<string>(DEFAULT_EDGE_VOICE)
  const [kokoroVoice, setKokoroVoice] = useState<string>('pf_dora')
  const [kokoroSpeed, setKokoroSpeed] = useState<number>(1.0)
  const [openaiVoice, setOpenaiVoice] = useState<string>(DEFAULT_OPENAI_VOICE)
  const [openrouterModel, setOpenrouterModel] = useState<string>(DEFAULT_OPENROUTER_MODEL)
  const [openrouterVoice, setOpenrouterVoice] = useState<string>('alloy')

  const [respectTiming, setRespectTiming] = useState(true)
  const [progress, setProgress] = useState<TTSProgress>({ stage: 'idle' })
  const [lineProgress, setLineProgress] = useState<{ current: number; total: number; text: string } | null>(null)
  const [activePart, setActivePart] = useState<number | null>(null)
  const [audioCache, setAudioCache] = useState<Record<number, { blob: Blob; durationSec: number; previewUrl: string }>>({})

  // API key states
  const [openaiKey, setOpenaiKey] = useState<string>('')
  const [openrouterKey, setOpenrouterKey] = useState<string>('')
  const [showOpenAIInput, setShowOpenAIInput] = useState<boolean>(false)
  const [showOpenRouterInput, setShowOpenRouterInput] = useState<boolean>(false)
  const [openaiDraft, setOpenaiDraft] = useState<string>('')
  const [openrouterDraft, setOpenrouterDraft] = useState<string>('')
  const [isTestingOpenAI, setIsTestingOpenAI] = useState<boolean>(false)
  const [isTestingOpenRouter, setIsTestingOpenRouter] = useState<boolean>(false)

  useEffect(() => {
    const savedOpenAI = getOpenAIKey()
    if (savedOpenAI) setOpenaiKey(savedOpenAI)
    const savedOR = getOpenRouterKey()
    if (savedOR) setOpenrouterKey(savedOR)
  }, [])

  const saveOpenAIKey = useCallback(async (key: string, testIt: boolean = true) => {
    if (!key.trim()) {
      toast.error('API key tidak boleh kosong')
      return
    }
    if (testIt) {
      setIsTestingOpenAI(true)
      const tid = toast.loading('Test OpenAI key…')
      const result = await testOpenAIKey(key)
      setIsTestingOpenAI(false)
      if (!result.valid) {
        toast.error(`Gagal: ${result.error}`, { id: tid })
        return
      }
      toast.success('OpenAI key valid!', { id: tid })
    }
    setOpenAIKey(key.trim())
    setOpenAIKey(key.trim())
    setShowOpenAIInput(false)
  }, [])

  const saveOpenRouterKey = useCallback(async (key: string, testIt: boolean = true) => {
    if (!key.trim()) {
      toast.error('API key tidak boleh kosong')
      return
    }
    if (testIt) {
      setIsTestingOpenRouter(true)
      const tid = toast.loading('Test OpenRouter key…')
      const result = await testOpenRouterKey(key)
      setIsTestingOpenRouter(false)
      if (!result.valid) {
        toast.error(`Gagal: ${result.error}`, { id: tid })
        return
      }
      toast.success('OpenRouter key valid!', { id: tid })
    }
    setOpenRouterKey(key.trim())
    setOpenrouterKey(key.trim())
    setShowOpenRouterInput(false)
  }, [])

  const generatePart = useCallback(
    async (partIndex: number) => {
      const part = splitResult.parts[partIndex - 1]
      if (!part) return
      const apiKey = provider === 'openai' ? openaiKey : provider === 'openrouter' ? openrouterKey : undefined
      if (provider !== 'edge' && !apiKey) {
        toast.error(`Set API key ${provider} dulu`)
        if (provider === 'openai') setShowOpenAIInput(true)
        else setShowOpenRouterInput(true)
        return
      }
      const prev = audioCache[partIndex]
      if (prev?.previewUrl) revokePreviewUrl(prev.previewUrl)

      setActivePart(partIndex)
      setLineProgress(null)
      setProgress({ stage: 'synthesizing', message: `Generating part ${partIndex}…`, percent: 0 })
      const tid = toast.loading(`Generating audio untuk ${prefix}-${String(partIndex).padStart(2, '0')}.srt…`)
      try {
        const voice = provider === 'edge' ? edgeVoice : provider === 'kokoro' ? kokoroVoice : provider === 'openai' ? openaiVoice : openrouterVoice
        const result = await narratePart(part, {
          provider,
          voice,
          model: provider === 'openrouter' ? openrouterModel : undefined,
          apiKey,
          speed: provider === 'kokoro' ? kokoroSpeed : undefined,
          respectTiming,
          onModelProgress: provider === 'kokoro' ? (p) => setProgress(p) : undefined,
          onLineProgress: (current, total, text) => setLineProgress({ current, total, text }),
          onStage: (p) => setProgress(p),
        })
        setAudioCache((prev) => ({
          ...prev,
          [partIndex]: { blob: result.blob, durationSec: result.durationSec, previewUrl: result.previewUrl },
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
    [splitResult, provider, edgeVoice, openaiVoice, openrouterVoice, openrouterModel, openaiKey, openrouterKey, respectTiming, prefix, audioCache],
  )

  const generateAll = useCallback(async () => {
    const apiKey = provider === 'openai' ? openaiKey : provider === 'openrouter' ? openrouterKey : undefined
    if (provider !== 'edge' && !apiKey) {
      toast.error(`Set API key ${provider} dulu`)
      if (provider === 'openai') setShowOpenAIInput(true)
      else setShowOpenRouterInput(true)
      return
    }
    if (splitResult.parts.length === 0) return

    Object.values(audioCache).forEach((c) => c.previewUrl && revokePreviewUrl(c.previewUrl))
    setAudioCache({})

    setProgress({ stage: 'synthesizing', message: 'Mulai full narration…', percent: 0 })
    setLineProgress(null)
    const tid = toast.loading(`Generating full audio (${splitResult.parts.length} parts)…`)
    try {
      const results: { blob: Blob; durationSec: number; previewUrl: string }[] = []
      const voice = provider === 'edge' ? edgeVoice : provider === 'kokoro' ? kokoroVoice : provider === 'openai' ? openaiVoice : openrouterVoice
      for (let i = 0; i < splitResult.parts.length; i++) {
        setActivePart(i + 1)
        const result = await narratePart(splitResult.parts[i], {
          provider,
          voice,
          model: provider === 'openrouter' ? openrouterModel : undefined,
          apiKey,
          speed: provider === 'kokoro' ? kokoroSpeed : undefined,
          respectTiming,
          onModelProgress: provider === 'kokoro' ? (p) => setProgress(p) : undefined,
          onLineProgress: (current, total, text) => setLineProgress({ current, total, text }),
          onStage: (p) => setProgress(p),
        })
        results.push({ blob: result.blob, durationSec: result.durationSec, previewUrl: result.previewUrl })
        setAudioCache((prev) => ({
          ...prev,
          [i + 1]: { blob: result.blob, durationSec: result.durationSec, previewUrl: result.previewUrl },
        }))
        toast.loading(`Part ${i + 1}/${splitResult.parts.length} done`, { id: tid })
      }
      const zip = new JSZip()
      let totalDuration = 0
      for (let i = 0; i < results.length; i++) {
        zip.file(`${prefix}-${String(i + 1).padStart(2, '0')}.wav`, await results[i].blob.arrayBuffer())
        totalDuration += results[i].durationSec
      }
      downloadBlob(`${prefix}-audio.zip`, await zip.generateAsync({ type: 'blob', compression: 'STORE' }))
      toast.success(`Full narration (${formatDuration(totalDuration)}) — ZIP downloaded`, { id: tid })
    } catch (e) {
      console.error(e)
      toast.error('Full narration gagal: ' + (e as Error).message, { id: tid })
    } finally {
      setActivePart(null)
      setLineProgress(null)
    }
  }, [splitResult, provider, edgeVoice, openaiVoice, openrouterVoice, openrouterModel, openaiKey, openrouterKey, respectTiming, prefix, audioCache])

  const downloadPartAudio = useCallback(
    (partIndex: number) => {
      const cached = audioCache[partIndex]
      if (!cached) return
      downloadBlob(`${prefix}-${String(partIndex).padStart(2, '0')}.wav`, cached.blob)
      toast.success(`Mengunduh ${prefix}-${String(partIndex).padStart(2, '0')}.wav`)
    },
    [audioCache, prefix],
  )

  const isSynthesizing = progress.stage === 'synthesizing' || progress.stage === 'stitching'
  const needsApiKey = provider !== 'edge' && provider !== 'kokoro'
  const hasApiKey = provider === 'edge' || provider === 'kokoro' ? true : provider === 'openai' ? Boolean(openaiKey) : Boolean(openrouterKey)

  const providerInfo: Record<Provider, { name: string; cost: string; indonesia: string; keyUrl?: string; hasKey: boolean }> = {
    edge: { name: 'Edge TTS (Microsoft)', cost: 'GRATIS', indonesia: 'Native (Gadis/Ardi)', hasKey: true },
    kokoro: { name: 'Kokoro-82M (Offline)', cost: 'GRATIS (80MB model)', indonesia: 'Multilingual (acc pt/es/en)', hasKey: true },
    openai: { name: 'OpenAI TTS', cost: '$0.015/1k chars', indonesia: 'Natural (multilingual)', keyUrl: 'https://platform.openai.com/api-keys', hasKey: Boolean(openaiKey) },
    openrouter: { name: 'OpenRouter TTS', cost: 'Pay-per-use', indonesia: 'Bergantung model', keyUrl: 'https://openrouter.ai/keys', hasKey: Boolean(openrouterKey) },
  }

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
              Konversi subtitle ke audio narasi. Pilih provider: Edge (gratis, native Indonesia), OpenAI, atau OpenRouter (banyak model). Audio timing di-sync ke SRT. Preview audio sebelum download.
            </CardDescription>
          </div>
          <Badge variant={hasApiKey ? 'secondary' : 'destructive'} className="shrink-0">
            {hasApiKey ? (
              <>
                <CheckCircle2 className="size-3 mr-1" /> Ready
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
        {/* Provider Selector */}
        <div>
          <Label className="text-sm font-medium">TTS Provider</Label>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-2 mt-2">
            {(Object.keys(providerInfo) as Provider[]).map((p) => {
              const info = providerInfo[p]
              const selected = provider === p
              return (
                <button
                  key={p}
                  type="button"
                  onClick={() => setProvider(p)}
                  className={`text-left p-3 rounded-md border-2 transition-all ${selected ? 'border-purple-500 bg-purple-50 dark:bg-purple-950/30' : 'border-border hover:border-purple-300'}`}
                >
                  <div className="font-medium text-sm flex items-center gap-1.5">
                    {selected && <CheckCircle2 className="size-3.5 text-purple-600" />}
                    {info.name}
                  </div>
                  <div className="text-xs text-muted-foreground mt-1">
                    <div><strong>Cost:</strong> {info.cost}</div>
                    <div><strong>Indonesia:</strong> {info.indonesia}</div>
                  </div>
                </button>
              )
            })}
          </div>
        </div>

        {/* API Key section (only for OpenAI / OpenRouter) */}
        {provider === 'openai' && (
          <div className="rounded-lg border border-amber-200 dark:border-amber-800 p-4 bg-amber-50/30 dark:bg-amber-950/10">
            <div className="flex items-start justify-between gap-3 mb-2">
              <div className="flex-1">
                <h4 className="font-medium text-sm mb-1 flex items-center gap-1.5">
                  <Key className="size-3.5 text-amber-600" />
                  OpenAI API Key
                </h4>
                <p className="text-xs text-muted-foreground">
                  Get free $5 credit di{' '}
                  <a href="https://platform.openai.com/api-keys" target="_blank" rel="noreferrer" className="text-amber-700 dark:text-amber-400 underline inline-flex items-center gap-0.5">
                    platform.openai.com <ExternalLink className="size-3" />
                  </a>. Disimpan di browser (localStorage).
                </p>
              </div>
              {openaiKey && (
                <Button size="sm" variant="outline" onClick={() => { setShowOpenAIInput(!showOpenAIInput); setOpenaiDraft(openaiKey) }} className="h-7 text-xs">
                  {showOpenAIInput ? 'Tutup' : 'Ganti'}
                </Button>
              )}
            </div>
            {(!openaiKey || showOpenAIInput) && (
              <div className="mt-3 space-y-2">
                <Input type="password" value={openaiDraft} onChange={(e) => setOpenaiDraft(e.target.value)} placeholder="sk-..." className="font-mono text-sm" />
                <Button size="sm" onClick={() => saveOpenAIKey(openaiDraft, true)} disabled={isTestingOpenAI || !openaiDraft.trim()}>
                  {isTestingOpenAI ? <><Loader2 className="size-3.5 mr-1 animate-spin" /> Testing…</> : <><CheckCircle2 className="size-3.5 mr-1" /> Test & Save</>}
                </Button>
              </div>
            )}
          </div>
        )}

        {provider === 'openrouter' && (
          <div className="rounded-lg border border-amber-200 dark:border-amber-800 p-4 bg-amber-50/30 dark:bg-amber-950/10">
            <div className="flex items-start justify-between gap-3 mb-2">
              <div className="flex-1">
                <h4 className="font-medium text-sm mb-1 flex items-center gap-1.5">
                  <Key className="size-3.5 text-amber-600" />
                  OpenRouter API Key
                </h4>
                <p className="text-xs text-muted-foreground">
                  Get free $1 credit di{' '}
                  <a href="https://openrouter.ai/keys" target="_blank" rel="noreferrer" className="text-amber-700 dark:text-amber-400 underline inline-flex items-center gap-0.5">
                    openrouter.ai/keys <ExternalLink className="size-3" />
                  </a>. Satu key untuk akses OpenAI, ElevenLabs, MiniMax, dll.
                </p>
              </div>
              {openrouterKey && (
                <Button size="sm" variant="outline" onClick={() => { setShowOpenRouterInput(!showOpenRouterInput); setOpenrouterDraft(openrouterKey) }} className="h-7 text-xs">
                  {showOpenRouterInput ? 'Tutup' : 'Ganti'}
                </Button>
              )}
            </div>
            {(!openrouterKey || showOpenRouterInput) && (
              <div className="mt-3 space-y-2">
                <Input type="password" value={openrouterDraft} onChange={(e) => setOpenrouterDraft(e.target.value)} placeholder="sk-or-..." className="font-mono text-sm" />
                <Button size="sm" onClick={() => saveOpenRouterKey(openrouterDraft, true)} disabled={isTestingOpenRouter || !openrouterDraft.trim()}>
                  {isTestingOpenRouter ? <><Loader2 className="size-3.5 mr-1 animate-spin" /> Testing…</> : <><CheckCircle2 className="size-3.5 mr-1" /> Test & Save</>}
                </Button>
              </div>
            )}
          </div>
        )}

        {/* Voice/Model selector + timing toggle */}
        {hasApiKey && (
          <>
            <div className="grid gap-3 sm:grid-cols-2">
              {provider === 'edge' && (
                <div>
                  <Label htmlFor="edge-voice" className="text-xs">Voice Edge TTS</Label>
                  <select id="edge-voice" value={edgeVoice} onChange={(e) => setEdgeVoice(e.target.value)} className="flex h-9 w-full rounded-md border border-input bg-background px-3 py-1 text-xs mt-1">
                    {EDGE_VOICES.map((v) => <option key={v.name} value={v.name}>{v.label}</option>)}
                  </select>
                </div>
              )}
              {provider === 'kokoro' && (
                <div className="col-span-2 space-y-3 rounded-md border border-purple-200 dark:border-purple-800 p-3 bg-purple-50/30 dark:bg-purple-950/10">
                  <div>
                    <Label htmlFor="kokoro-voice" className="text-xs">Voice Kokoro (54 voices, multilingual)</Label>
                    <select id="kokoro-voice" value={kokoroVoice} onChange={(e) => setKokoroVoice(e.target.value)} className="flex h-9 w-full rounded-md border border-input bg-background px-3 py-1 text-xs mt-1">
                      <optgroup label="🇧🇷 Portugal (accent mirip Indonesia)">
                        <option value="pf_dora">Dora (female, natural) — paling cocok untuk Indonesia</option>
                      </optgroup>
                      <optgroup label="🇪🇸 Spanyol (accent mirip Indonesia)">
                        <option value="ef_dora">Dora (female)</option>
                      </optgroup>
                      <optgroup label="🇺🇸 English US">
                        <option value="af_heart">Heart (female, natural)</option>
                        <option value="af_bella">Bella (female, natural)</option>
                        <option value="af_nova">Nova (female)</option>
                        <option value="am_michael">Michael (male)</option>
                        <option value="am_adam">Adam (male)</option>
                      </optgroup>
                      <optgroup label="🇬🇧 English UK">
                        <option value="bf_emma">Emma (female)</option>
                        <option value="bm_george">George (male)</option>
                      </optgroup>
                      <optgroup label="🇫🇷 French">
                        <option value="ff_siwis">Siwis (female)</option>
                      </optgroup>
                      <optgroup label="🇨🇳 Mandarin">
                        <option value="zf_xiaoxiao">Xiaoxiao (female)</option>
                      </optgroup>
                      <optgroup label="🇯🇵 Japanese">
                        <option value="jf_alpha">Alpha (female)</option>
                      </optgroup>
                    </select>
                  </div>
                  <div>
                    <Label htmlFor="kokoro-speed" className="text-xs">Speed: {kokoroSpeed.toFixed(1)}x</Label>
                    <input
                      id="kokoro-speed"
                      type="range"
                      min={0.5}
                      max={2}
                      step={0.1}
                      value={kokoroSpeed}
                      onChange={(e) => setKokoroSpeed(Number(e.target.value))}
                      className="w-full mt-1"
                    />
                  </div>
                  <p className="text-xs text-muted-foreground">
                    <strong>Note:</strong> Kokoro tidak punya voice Indonesia native, tapi text Indonesia akan dibaca dengan accent dari voice yang dipilih. Pilih <strong>Dora (Portuguese)</strong> untuk accent paling mirip Indonesia.
                  </p>
                </div>
              )}
              {provider === 'openai' && (
                <div>
                  <Label htmlFor="openai-voice" className="text-xs">Voice OpenAI</Label>
                  <select id="openai-voice" value={openaiVoice} onChange={(e) => setOpenaiVoice(e.target.value)} className="flex h-9 w-full rounded-md border border-input bg-background px-3 py-1 text-xs mt-1">
                    {OPENAI_VOICES.map((v) => <option key={v.id} value={v.id}>{v.label}</option>)}
                  </select>
                </div>
              )}
              {provider === 'openrouter' && (
                <>
                  <div>
                    <Label htmlFor="or-model" className="text-xs">Model OpenRouter</Label>
                    <select id="or-model" value={openrouterModel} onChange={(e) => setOpenrouterModel(e.target.value)} className="flex h-9 w-full rounded-md border border-input bg-background px-3 py-1 text-xs mt-1">
                      {OPENROUTER_MODELS.map((m) => <option key={m.id} value={m.id}>{m.label}</option>)}
                    </select>
                  </div>
                  <div>
                    <Label htmlFor="or-voice" className="text-xs">Voice (tergantung model)</Label>
                    <select id="or-voice" value={openrouterVoice} onChange={(e) => setOpenrouterVoice(e.target.value)} className="flex h-9 w-full rounded-md border border-input bg-background px-3 py-1 text-xs mt-1">
                      <option value="alloy">Alloy (neutral)</option>
                      <option value="nova">Nova (female natural)</option>
                      <option value="shimmer">Shimmer (female clear)</option>
                      <option value="echo">Echo (male warm)</option>
                      <option value="fable">Fable (male narrative)</option>
                      <option value="onyx">Onyx (male deep)</option>
                    </select>
                  </div>
                </>
              )}
              <div className="flex items-end justify-between gap-3">
                <div>
                  <Label htmlFor="timing" className="text-xs">Sync timing ke SRT</Label>
                  <p className="text-xs text-muted-foreground mt-1">
                    ON: audio mulai di cue.start, push-back kalau overlap (audio utuh, pitch natural).
                    OFF: audio berurutan dengan 300ms gap.
                  </p>
                </div>
                <Switch id="timing" checked={respectTiming} onCheckedChange={setRespectTiming} />
              </div>
            </div>

            {/* Action buttons */}
            <div className="flex flex-wrap gap-2">
              <Button onClick={generateAll} disabled={isSynthesizing} size="sm">
                {isSynthesizing ? <><Loader2 className="size-3.5 mr-1 animate-spin" /> Generating…</> : <><AudioLines className="size-3.5 mr-1" /> Generate & Download ZIP ({splitResult.parts.length} parts)</>}
              </Button>
            </div>

            {/* Progress */}
            {(isSynthesizing || lineProgress) && (
              <div className="rounded-md border bg-white/50 dark:bg-slate-900/50 p-3 space-y-2">
                {progress.message && <p className="text-sm font-medium">{progress.message}</p>}
                {progress.percent !== undefined && <Progress value={progress.percent} className="h-2" />}
                {lineProgress && (
                  <p className="text-xs text-muted-foreground">Baris {lineProgress.current}/{lineProgress.total}: "{lineProgress.text.slice(0, 60)}{lineProgress.text.length > 60 ? '…' : ''}"</p>
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
                  <div key={idx} className="rounded-md border bg-card p-3 space-y-2">
                    <div className="flex items-center gap-2">
                      <div className="size-8 rounded-md bg-purple-100 dark:bg-purple-950/40 flex items-center justify-center shrink-0">
                        <span className="text-xs font-bold text-purple-700 dark:text-purple-400">{String(idx).padStart(2, '0')}</span>
                      </div>
                      <div className="min-w-0 flex-1">
                        <div className="text-sm font-medium truncate">{prefix}-{String(idx).padStart(2, '0')}.wav</div>
                        <div className="text-xs text-muted-foreground">
                          {part.entryCount} baris • {formatDuration(part.endSec - part.startSec)}
                          {cached && <span className="ml-2 text-purple-600">✓ {formatDuration(cached.durationSec)} audio</span>}
                        </div>
                      </div>
                      <Button size="sm" variant="outline" disabled={isSynthesizing} onClick={() => generatePart(idx)} className="h-8">
                        {isGenerating ? <Loader2 className="size-3 animate-spin" /> : <AudioLines className="size-3" />}
                      </Button>
                      {cached && (
                        <Button size="sm" variant="ghost" onClick={() => downloadPartAudio(idx)} className="h-8">
                          <Download className="size-3" />
                        </Button>
                      )}
                    </div>
                    {cached && (
                      <div className="mt-2 rounded-md bg-emerald-50/50 dark:bg-emerald-950/20 p-2">
                        <div className="flex items-center gap-1.5 text-xs text-emerald-700 dark:text-emerald-400 mb-1.5">
                          <Play className="size-3" /> Preview audio (dengar sebelum download)
                        </div>
                        <audio controls preload="metadata" src={cached.previewUrl} className="w-full h-9" />
                      </div>
                    )}
                  </div>
                )
              })}
            </div>
          </div>
        )}

        {/* Edge proxy URL config (only when on Edge provider + GitHub Pages deployment) */}
        {provider === 'edge' && typeof window !== 'undefined' && !window.location.origin.includes('vercel.app') && !window.location.origin.includes('localhost') && (
          <div className="rounded-lg border border-blue-200 dark:border-blue-800 p-3 bg-blue-50/30 dark:bg-blue-950/10">
            <Label htmlFor="edge-proxy" className="text-xs font-medium">
              Edge TTS Proxy URL (khusus GitHub Pages)
            </Label>
            <p className="text-xs text-muted-foreground mt-1 mb-2">
              ⚠️ Kalau pakai app dari GitHub Pages, Edge TTS butuh proxy (browser tidak bisa langsung ke Microsoft).
              <strong> Solusi: deploy ke Vercel</strong> → Edge TTS langsung jalan tanpa proxy.
              Atau paste URL Vercel proxy di sini.
            </p>
            <Input
              id="edge-proxy"
              type="text"
              defaultValue={typeof window !== 'undefined' ? getEdgeProxyUrl() : ''}
              placeholder="https://srt-splitter.vercel.app/api/edge-tts"
              className="text-xs"
              onBlur={(e) => {
                setEdgeProxyUrl(e.target.value)
                toast.success('Edge proxy URL disimpan')
              }}
            />
          </div>
        )}

        {/* Notice */}
        <div className="text-xs text-muted-foreground flex items-start gap-2 pt-1">
          <AlertCircle className="size-3.5 mt-0.5 shrink-0" />
          <span>
            <strong>Edge TTS (default):</strong> Gratis, native Indonesia (Gadis/Ardi). Pakai Vercel proxy (butuh internet).
            <br />
            <strong>OpenAI TTS:</strong> Premium, $0.015/1k chars. API key dari platform.openai.com.
            <br />
            <strong>OpenRouter TTS:</strong> Gateway ke banyak model (OpenAI, ElevenLabs, MiniMax). API key dari openrouter.ai/keys.
            <br />
            <strong>Timing sync:</strong> Audio 100% natural (tidak dipotong, tidak di-speed up). Kalau audio lebih panjang dari cue, cue berikutnya akan mulai setelah audio selesai (push-back). Pitch pasti natural.
          </span>
        </div>
      </CardContent>
    </Card>
  )
}
