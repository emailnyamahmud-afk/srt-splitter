'use client'

import { useState, useCallback } from 'react'
import { Languages, Loader2, CheckCircle2, ArrowRight } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Label } from '@/components/ui/label'
import { Badge } from '@/components/ui/badge'
import { Switch } from '@/components/ui/switch'
import { Progress } from '@/components/ui/progress'
import { toast } from 'sonner'
import {
  translateEntries,
  LANGUAGES,
  type TranslateProgress,
  type SrtEntry,
} from '@/lib/translate'

interface TranslatePanelProps {
  entries: SrtEntry[]
  onTranslated: (translatedEntries: SrtEntry[], fromLang: string, toLang: string) => void
}

export function TranslatePanel({ entries, onTranslated }: TranslatePanelProps) {
  const [fromLang, setFromLang] = useState<string>('auto')
  const [toLang, setToLang] = useState<string>('id')
  const [useOpenAI, setUseOpenAI] = useState(false)
  const [isTranslating, setIsTranslating] = useState(false)
  const [progress, setProgress] = useState<TranslateProgress | null>(null)

  const handleTranslate = useCallback(async () => {
    if (entries.length === 0) {
      toast.error('Upload SRT dulu')
      return
    }
    setIsTranslating(true)
    setProgress(null)
    const tid = toast.loading(`Translating ${entries.length} baris…`)
    try {
      const translated = await translateEntries(
        entries,
        fromLang,
        toLang,
        useOpenAI,
        undefined,
        (p) => setProgress(p),
      )
      onTranslated(translated, fromLang, toLang)
      toast.success(`Translated ${entries.length} baris dari ${LANGUAGES.find(l => l.code === fromLang)?.label || fromLang} → ${LANGUAGES.find(l => l.code === toLang)?.label || toLang}`, { id: tid })
    } catch (e) {
      toast.error('Translate gagal: ' + (e as Error).message, { id: tid })
    } finally {
      setIsTranslating(false)
      setProgress(null)
    }
  }, [entries, fromLang, toLang, useOpenAI, onTranslated])

  return (
    <Card className="border-blue-200 dark:border-blue-900/50 bg-blue-50/30 dark:bg-blue-950/10">
      <CardHeader>
        <div className="flex items-start justify-between gap-3">
          <div>
            <CardTitle className="text-lg flex items-center gap-2">
              <Languages className="size-5 text-blue-600" />
              Translate Subtitle
            </CardTitle>
            <CardDescription className="mt-1">
              Translate subtitle ke bahasa lain. Gratis (Google Translate) atau premium (OpenAI — kualitas lebih baik untuk Jawa).
            </CardDescription>
          </div>
          {entries.length > 0 && (
            <Badge variant="secondary" className="shrink-0">
              {entries.length} baris
            </Badge>
          )}
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* Language selectors */}
        <div className="grid gap-3 sm:grid-cols-2">
          <div>
            <Label htmlFor="from-lang" className="text-xs">Dari bahasa</Label>
            <select
              id="from-lang"
              value={fromLang}
              onChange={(e) => setFromLang(e.target.value)}
              className="flex h-9 w-full rounded-md border border-input bg-background px-3 py-1 text-xs mt-1"
            >
              {LANGUAGES.map((l) => (
                <option key={l.code} value={l.code}>{l.label}</option>
              ))}
            </select>
          </div>
          <div>
            <Label htmlFor="to-lang" className="text-xs">Ke bahasa</Label>
            <select
              id="to-lang"
              value={toLang}
              onChange={(e) => setToLang(e.target.value)}
              className="flex h-9 w-full rounded-md border border-input bg-background px-3 py-1 text-xs mt-1"
            >
              {LANGUAGES.filter(l => l.code !== 'auto').map((l) => (
                <option key={l.code} value={l.code}>{l.label}</option>
              ))}
            </select>
          </div>
        </div>

        {/* Quick presets */}
        <div className="flex flex-wrap gap-2">
          <Button size="sm" variant="outline" className="h-7 text-xs"
            onClick={() => { setFromLang('en'); setToLang('id') }}>
            EN → Indonesia
          </Button>
          <Button size="sm" variant="outline" className="h-7 text-xs"
            onClick={() => { setFromLang('id'); setToLang('jv') }}>
            Indonesia → Jawa
          </Button>
          <Button size="sm" variant="outline" className="h-7 text-xs"
            onClick={() => { setFromLang('jv'); setToLang('id') }}>
            Jawa → Indonesia
          </Button>
          <Button size="sm" variant="outline" className="h-7 text-xs"
            onClick={() => { setFromLang('id'); setToLang('en') }}>
            Indonesia → EN
          </Button>
        </div>

        {/* OpenAI toggle */}
        <div className="flex items-center justify-between gap-3 rounded-md border border-amber-200 dark:border-amber-800 p-3 bg-amber-50/30 dark:bg-amber-950/10">
          <div>
            <Label className="text-xs font-medium">Gunakan OpenAI (premium)</Label>
            <p className="text-xs text-muted-foreground mt-0.5">
              ON: kualitas lebih baik untuk Jawa/Sunda (pakai API key OpenAI). OFF: gratis (Google Translate).
            </p>
          </div>
          <Switch checked={useOpenAI} onCheckedChange={setUseOpenAI} />
        </div>

        {/* Translate button */}
        <Button onClick={handleTranslate} disabled={isTranslating || entries.length === 0} size="sm">
          {isTranslating ? (
            <>
              <Loader2 className="size-3.5 mr-1 animate-spin" /> Translating…
            </>
          ) : (
            <>
              <Languages className="size-3.5 mr-1" /> Translate {entries.length} baris
            </>
          )}
        </Button>

        {/* Progress */}
        {progress && (
          <div className="rounded-md border bg-white/50 dark:bg-slate-900/50 p-3 space-y-2">
            <div className="flex items-center gap-2 text-sm">
              <span className="font-medium">Baris {progress.current}/{progress.total}</span>
              <ArrowRight className="size-3 text-muted-foreground" />
              <span className="text-muted-foreground truncate">"{progress.text}"</span>
            </div>
            <Progress value={(progress.current / progress.total) * 100} className="h-2" />
          </div>
        )}
      </CardContent>
    </Card>
  )
}
