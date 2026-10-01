'use client'

import { useCallback, useMemo, useRef, useState } from 'react'
import {
  Upload,
  FileText,
  Scissors,
  Download,
  Clock,
  Hash,
  Film,
  Info,
  RefreshCw,
  Trash2,
  CheckCircle2,
} from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Switch } from '@/components/ui/switch'
import { Slider } from '@/components/ui/slider'
import { Badge } from '@/components/ui/badge'
import { Separator } from '@/components/ui/separator'
import { ScrollArea } from '@/components/ui/scroll-area'
import { toast } from 'sonner'
import { TtsPanel } from '@/components/tts-panel'
import {
  parseSrt,
  splitEntries,
  serializePart,
  downloadTextFile,
  downloadAllPartsAsZip,
  type SrtEntry,
  type SplitResult,
} from '@/lib/srt'

export default function Home() {
  const [file, setFile] = useState<File | null>(null)
  const [entries, setEntries] = useState<SrtEntry[]>([])
  const [fileName, setFileName] = useState<string>('')
  const [maxMinutes, setMaxMinutes] = useState<number>(30)
  const [prefix, setPrefix] = useState<string>('S6')
  const [resetTimestamps, setResetTimestamps] = useState<boolean>(false)
  const [isDragging, setIsDragging] = useState<boolean>(false)
  const [isZipping, setIsZipping] = useState<boolean>(false)
  const fileInputRef = useRef<HTMLInputElement>(null)

  const splitResult: SplitResult | null = useMemo(() => {
    if (entries.length === 0) return null
    return splitEntries(entries, {
      maxMinutes,
      prefix,
      resetTimestamps,
      splitOnBoundary: true,
    })
  }, [entries, maxMinutes, prefix, resetTimestamps])

  const handleFile = useCallback(async (f: File) => {
    if (!f.name.toLowerCase().endsWith('.srt')) {
      toast.error('File harus berekstensi .srt')
      return
    }
    try {
      const text = await f.text()
      const parsed = parseSrt(text)
      if (parsed.length === 0) {
        toast.error('Tidak ada subtitle valid ditemukan di file.')
        return
      }
      setFile(f)
      setEntries(parsed)
      // Auto-fill prefix from filename if it looks like a season code
      const baseName = f.name.replace(/\.srt$/i, '').replace(/\[.*?\]/g, '').trim()
      setPrefix(baseName.slice(0, 6) || 'S6')
      setFileName(f.name)
      toast.success(`Berhasil parsing ${parsed.length} subtitle.`)
    } catch (e) {
      console.error(e)
      toast.error('Gagal membaca file. Pastikan encoding UTF-8.')
    }
  }, [])

  const onDrop = useCallback(
    (e: React.DragEvent<HTMLDivElement>) => {
      e.preventDefault()
      setIsDragging(false)
      const f = e.dataTransfer.files?.[0]
      if (f) handleFile(f)
    },
    [handleFile],
  )

  const onInputChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const f = e.target.files?.[0]
      if (f) handleFile(f)
    },
    [handleFile],
  )

  const formatHMS = (sec: number): string => {
    const h = Math.floor(sec / 3600)
    const m = Math.floor((sec % 3600) / 60)
    const s = Math.floor(sec % 60)
    if (h > 0) return `${h}j ${m}m ${s}s`
    return `${m}m ${s}s`
  }

  const formatTS = (sec: number): string => {
    const h = Math.floor(sec / 3600)
    const m = Math.floor((sec % 3600) / 60)
    const s = Math.floor(sec % 60)
    return `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`
  }

  const reset = () => {
    setFile(null)
    setEntries([])
    setFileName('')
    if (fileInputRef.current) fileInputRef.current.value = ''
  }

  const totalDuration = entries.length > 0 ? entries[entries.length - 1].end : 0

  return (
    <div className="min-h-screen flex flex-col bg-gradient-to-br from-slate-50 to-slate-100 dark:from-slate-950 dark:to-slate-900">
      <header className="border-b bg-white/80 dark:bg-slate-900/80 backdrop-blur-sm sticky top-0 z-10">
        <div className="container mx-auto max-w-5xl px-4 py-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="size-10 rounded-xl bg-gradient-to-br from-amber-500 to-orange-600 flex items-center justify-center shadow-lg">
              <Scissors className="size-5 text-white" />
            </div>
            <div>
              <h1 className="text-xl font-bold tracking-tight">SRT Splitter</h1>
              <p className="text-xs text-muted-foreground">Pemecah file subtitle tanpa upload server</p>
            </div>
          </div>
          <Badge variant="secondary" className="hidden sm:flex">
            <CheckCircle2 className="size-3 mr-1" /> 100% Offline
          </Badge>
        </div>
      </header>

      <main className="container mx-auto max-w-5xl px-4 py-8 flex-1 space-y-6">
        {/* Upload area */}
        {!file && (
          <Card className="border-2 border-dashed hover:border-primary/50 transition-colors">
            <CardContent
              className="py-16 px-6 flex flex-col items-center justify-center text-center cursor-pointer"
              onClick={() => fileInputRef.current?.click()}
              onDragOver={(e) => {
                e.preventDefault()
                setIsDragging(true)
              }}
              onDragLeave={() => setIsDragging(false)}
              onDrop={onDrop}
            >
              <div
                className={`size-20 rounded-full bg-gradient-to-br from-amber-100 to-orange-100 dark:from-amber-950/40 dark:to-orange-950/40 flex items-center justify-center mb-6 transition-transform ${
                  isDragging ? 'scale-110' : ''
                }`}
              >
                <Upload className="size-8 text-amber-600" />
              </div>
              <h2 className="text-2xl font-semibold mb-2">Drop file .srt di sini</h2>
              <p className="text-muted-foreground mb-4 max-w-md">
                Klik untuk pilih file atau seret-dan-jatuhkan. Semua proses dilakukan di
                browser Anda — file tidak pernah dikirim ke server mana pun.
              </p>
              <Button size="lg">
                <FileText className="size-4 mr-2" /> Pilih File SRT
              </Button>
              <input
                ref={fileInputRef}
                type="file"
                accept=".srt"
                className="hidden"
                onChange={onInputChange}
              />
              <div className="mt-8 grid grid-cols-1 sm:grid-cols-3 gap-3 max-w-2xl text-left">
                <div className="flex items-start gap-2 text-sm">
                  <Clock className="size-4 text-amber-600 mt-0.5 shrink-0" />
                  <span>Bisa potong per 30 menit atau berapapun sesuai kebutuhan</span>
                </div>
                <div className="flex items-start gap-2 text-sm">
                  <Hash className="size-4 text-amber-600 mt-0.5 shrink-0" />
                  <span>Timestamp bisa dipertahankan atau direset ke 00:00:00</span>
                </div>
                <div className="flex items-start gap-2 text-sm">
                  <Film className="size-4 text-amber-600 mt-0.5 shrink-0" />
                  <span>Dipotong di batas subtitle, tidak ada teks yang rusak</span>
                </div>
              </div>
            </CardContent>
          </Card>
        )}

        {/* Main workspace */}
        {file && splitResult && (
          <>
            {/* File info + reset */}
            <Card>
              <CardHeader className="pb-4">
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0 flex-1">
                    <CardTitle className="text-base truncate">{fileName}</CardTitle>
                    <CardDescription className="mt-1 flex flex-wrap items-center gap-3">
                      <span className="flex items-center gap-1">
                        <Hash className="size-3" /> {entries.length} subtitle
                      </span>
                      <span className="flex items-center gap-1">
                        <Clock className="size-3" /> {formatHMS(totalDuration)}
                      </span>
                    </CardDescription>
                  </div>
                  <Button variant="ghost" size="sm" onClick={reset}>
                    <RefreshCw className="size-4 mr-1" /> File lain
                  </Button>
                </div>
              </CardHeader>
            </Card>

            {/* Settings */}
            <Card>
              <CardHeader>
                <CardTitle className="text-lg">Pengaturan Split</CardTitle>
                <CardDescription>
                  Atur durasi tiap file output dan opsi timestamp.
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-6">
                {/* Duration slider */}
                <div className="space-y-3">
                  <div className="flex items-center justify-between">
                    <Label className="text-sm font-medium">Durasi maksimal per file</Label>
                    <Badge variant="outline" className="font-mono">
                      {maxMinutes} menit
                    </Badge>
                  </div>
                  <Slider
                    value={[maxMinutes]}
                    onValueChange={(v) => setMaxMinutes(v[0])}
                    min={5}
                    max={120}
                    step={5}
                    className="w-full"
                  />
                  <div className="flex flex-wrap gap-2">
                    {[10, 15, 20, 30, 45, 60, 90].map((m) => (
                      <Button
                        key={m}
                        size="sm"
                        variant={maxMinutes === m ? 'default' : 'outline'}
                        onClick={() => setMaxMinutes(m)}
                        className="h-7 px-2 text-xs"
                      >
                        {m}m
                      </Button>
                    ))}
                  </div>
                </div>

                <Separator />

                {/* Prefix */}
                <div className="space-y-2">
                  <Label htmlFor="prefix" className="text-sm font-medium">
                    Prefix nama file
                  </Label>
                  <div className="flex items-center gap-2">
                    <Input
                      id="prefix"
                      value={prefix}
                      onChange={(e) => setPrefix(e.target.value.replace(/[^\w-]/g, ''))}
                      placeholder="S6"
                      className="max-w-[200px]"
                    />
                    <span className="text-sm text-muted-foreground font-mono">
                      → {prefix}-01.srt, {prefix}-02.srt, …
                    </span>
                  </div>
                </div>

                <Separator />

                {/* Reset timestamps */}
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <Label htmlFor="reset-ts" className="text-sm font-medium">
                      Reset timestamp per file ke 00:00:00
                    </Label>
                    <p className="text-xs text-muted-foreground mt-1">
                      Matikan untuk mempertahankan timestamp asli (cocok untuk dipasang
                      langsung ke video asli tanpa offset).
                    </p>
                  </div>
                  <Switch
                    id="reset-ts"
                    checked={resetTimestamps}
                    onCheckedChange={setResetTimestamps}
                  />
                </div>
              </CardContent>
            </Card>

            {/* Result overview */}
            <Card>
              <CardHeader>
                <div className="flex items-center justify-between">
                  <div>
                    <CardTitle className="text-lg">Hasil Pemecahan</CardTitle>
                    <CardDescription>
                      {splitResult.parts.length} file — dipotong di batas subtitle
                    </CardDescription>
                  </div>
                  <Button
                    size="sm"
                    disabled={isZipping}
                    onClick={async () => {
                      if (!splitResult) return
                      setIsZipping(true)
                      const tid = toast.loading('Membuat ZIP…')
                      try {
                        await downloadAllPartsAsZip(
                          splitResult.parts,
                          prefix,
                          resetTimestamps,
                        )
                        toast.success(`Mengunduh ${prefix}-split.zip`, {
                          id: tid,
                        })
                      } catch (e) {
                        console.error(e)
                        toast.error('Gagal membuat ZIP', { id: tid })
                      } finally {
                        setIsZipping(false)
                      }
                    }}
                  >
                    {isZipping ? (
                      <>
                        <RefreshCw className="size-4 mr-1 animate-spin" /> Mengemas…
                      </>
                    ) : (
                      <>
                        <Download className="size-4 mr-1" /> Unduh ZIP
                      </>
                    )}
                  </Button>
                </div>
              </CardHeader>
              <CardContent>
                <ScrollArea className="max-h-[480px] pr-3">
                  <div className="space-y-2">
                    {splitResult.parts.map((part) => {
                      const filename = `${prefix}-${String(part.index).padStart(2, '0')}.srt`
                      return (
                        <div
                          key={part.index}
                          className="flex items-center gap-3 p-3 rounded-lg border bg-card hover:shadow-sm transition-shadow"
                        >
                          <div className="size-10 rounded-md bg-gradient-to-br from-amber-100 to-orange-100 dark:from-amber-950/40 dark:to-orange-950/40 flex items-center justify-center shrink-0">
                            <span className="text-sm font-bold text-amber-700 dark:text-amber-400">
                              {String(part.index).padStart(2, '0')}
                            </span>
                          </div>
                          <div className="min-w-0 flex-1">
                            <div className="flex items-center gap-2 flex-wrap">
                              <span className="font-mono text-sm font-medium truncate">
                                {filename}
                              </span>
                              <Badge variant="secondary" className="text-xs">
                                {part.entryCount} subtitle
                              </Badge>
                            </div>
                            <div className="text-xs text-muted-foreground mt-0.5 font-mono">
                              {formatTS(part.startSec)} → {formatTS(part.endSec)}
                              <span className="mx-1.5">•</span>
                              durasi {formatHMS(part.durationSec)}
                            </div>
                          </div>
                          <Button
                            size="sm"
                            variant="outline"
                            onClick={() => {
                              const content = serializePart(part, resetTimestamps)
                              downloadTextFile(filename, content)
                              toast.success(`Mengunduh ${filename}`)
                            }}
                          >
                            <Download className="size-3.5" />
                          </Button>
                        </div>
                      )
                    })}
                  </div>
                </ScrollArea>
              </CardContent>
            </Card>

            {/* Preview of first part */}
            {splitResult.parts.length > 0 && (
              <Card>
                <CardHeader>
                  <CardTitle className="text-lg">
                    Preview: {prefix}-01.srt
                  </CardTitle>
                  <CardDescription>
                    3 subtitle pertama & terakhir dari file pertama.
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  <PreviewPart part={splitResult.parts[0]} resetTimestamps={resetTimestamps} />
                </CardContent>
              </Card>
            )}

            {/* TTS Panel - convert subtitles to audio */}
            <TtsPanel splitResult={splitResult} prefix={prefix} />
          </>
        )}

        {/* Info section */}
        {!file && (
          <Card className="bg-blue-50/50 dark:bg-blue-950/20 border-blue-200 dark:border-blue-900">
            <CardContent className="pt-6 pb-6">
              <div className="flex items-start gap-3">
                <Info className="size-5 text-blue-600 mt-0.5 shrink-0" />
                <div className="text-sm text-muted-foreground space-y-2">
                  <p>
                    <strong className="text-foreground">Cara pakai:</strong>{' '}
                    Seret file SRT ke area di atas atau klik untuk pilih file.
                    Atur durasi per file (default 30 menit), pilih apakah timestamp
                    direset ke 00:00:00 atau dipertahankan, lalu unduh per-file
                    atau semua sebagai satu file ZIP.
                  </p>
                  <p>
                    <strong className="text-foreground">Privacy:</strong> Aplikasi ini
                    bekerja 100% di browser. File subtitle Anda tidak dikirim ke mana
                    pun. Aman dipakai di rumah untuk file pribadi.
                  </p>
                  <p>
                    <strong className="text-foreground">Output:</strong> Setiap file
                    dipotong di batas subtitle (tidak memotong kalimat di tengah), jadi
                    tidak ada teks yang hilang atau rusak.
                  </p>
                </div>
              </div>
            </CardContent>
          </Card>
        )}

        {/* Source code download */}
        <Card className="border-amber-200 dark:border-amber-900/50 bg-amber-50/30 dark:bg-amber-950/10">
          <CardContent className="pt-6 pb-6">
            <div className="flex items-start gap-3">
              <Download className="size-5 text-amber-600 mt-0.5 shrink-0" />
              <div className="flex-1">
                <h3 className="font-semibold mb-1">Unduh Source Code</h3>
                <p className="text-sm text-muted-foreground mb-3">
                  Ingin menjalankan offline di MacBook atau deploy ke GitHub Pages?
                  Unduh source code lengkap (termasuk README & GitHub Actions workflow).
                </p>
                <div className="flex flex-wrap gap-2">
                  <a
                    href="srt-splitter-source.zip"
                    download
                    className="inline-flex items-center gap-1.5 px-3 py-1.5 text-sm rounded-md bg-amber-600 hover:bg-amber-700 text-white transition-colors"
                  >
                    <Download className="size-3.5" /> srt-splitter-source.zip
                  </a>
                  <a
                    href="https://github.com"
                    target="_blank"
                    rel="noreferrer"
                    className="inline-flex items-center gap-1.5 px-3 py-1.5 text-sm rounded-md border hover:bg-muted transition-colors"
                  >
                    GitHub Pages Guide →
                  </a>
                </div>
              </div>
            </div>
          </CardContent>
        </Card>
      </main>

      <footer className="border-t bg-white/60 dark:bg-slate-900/60 mt-auto">
        <div className="container mx-auto max-w-5xl px-4 py-4 text-center text-xs text-muted-foreground">
          SRT Splitter • Berjalan 100% di browser • Tanpa upload ke server
        </div>
      </footer>
    </div>
  )
}

function PreviewPart({
  part,
  resetTimestamps,
}: {
  part: SplitResult['parts'][number]
  resetTimestamps: boolean
}) {
  const offset = resetTimestamps ? part.startSec : 0
  const firstThree = part.entries.slice(0, 3)
  const lastThree = part.entries.slice(-3)

  const fmt = (sec: number) => {
    const s = Math.max(0, sec - offset)
    const h = Math.floor(s / 3600)
    const m = Math.floor((s % 3600) / 60)
    const sec2 = Math.floor(s % 60)
    const ms = Math.round((s - Math.floor(s)) * 1000)
    return `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}:${String(sec2).padStart(2, '0')},${String(ms).padStart(3, '0')}`
  }

  const renderItem = (entry: SrtEntry, idx: number) => (
    <div key={idx} className="text-sm">
      <div className="font-mono text-xs text-muted-foreground mb-0.5">
        {fmt(entry.start)} → {fmt(entry.end)}
      </div>
      <div>{entry.textLines.join(' ')}</div>
    </div>
  )

  return (
    <div className="grid gap-4 md:grid-cols-2">
      <div>
        <h4 className="text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-2">
          Awal file
        </h4>
        <div className="space-y-3">{firstThree.map(renderItem)}</div>
      </div>
      <div>
        <h4 className="text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-2">
          Akhir file
        </h4>
        <div className="space-y-3">{lastThree.map(renderItem)}</div>
      </div>
    </div>
  )
}
