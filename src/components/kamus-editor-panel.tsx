'use client'

// Kamus Viewer (READ-ONLY) — tampilkan kamus dari Supabase untuk verifikasi.
// User TIDAK bisa edit kamus dari web app. Editing hanya via TUI lokal (kamus-tui.py)
// + upload ke Supabase. Web app hanya baca + lookup alias untuk convertRegister.
//
// Catatan: fungsi updateKamusEntry + importKamus di supabase.ts sengaja tidak dipakai
// dari UI. Mereka tetap ada di lib untuk potential use case lain, tapi tidak
// di-import di panel ini.

import { useCallback, useEffect, useState } from 'react'
import { Search, CheckCircle2, Loader2, BookOpen, Eye } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Badge } from '@/components/ui/badge'
import { ScrollArea } from '@/components/ui/scroll-area'
import {
  isSupabaseAvailable,
  searchKamus,
  countKamus,
  type KamusEntry,
} from '@/lib/supabase'

export function KamusEditorPanel() {
  const [ready, setReady] = useState(false)
  const [searchQuery, setSearchQuery] = useState('')
  const [results, setResults] = useState<KamusEntry[]>([])
  const [totalCount, setTotalCount] = useState(0)
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    setReady(isSupabaseAvailable())
  }, [])

  useEffect(() => {
    if (!ready) return
    countKamus().then(c => setTotalCount(c))
  }, [ready])

  const handleSearch = useCallback(async () => {
    if (!searchQuery.trim() || !ready) return
    setLoading(true)
    const res = await searchKamus(searchQuery.trim(), 50)
    setResults(res)
    setLoading(false)
  }, [searchQuery, ready])

  if (!ready) return null

  return (
    <Card className="mt-4 border-emerald-200 dark:border-emerald-800">
      <CardHeader>
        <CardTitle className="text-lg flex items-center gap-2">
          <BookOpen className="size-5 text-emerald-600" />
          Kamus Jawa Viewer
          <Badge variant="outline" className="text-xs bg-emerald-50 dark:bg-emerald-950/30 ml-1">
            <Eye className="size-3 mr-1" /> Read-only
          </Badge>
        </CardTitle>
        <CardDescription>
          Lihat kamus dari Supabase (read-only). Edit kamus pakai TUI lokal (kamus-tui.py) → upload ke Supabase.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* Stats */}
        <div className="flex items-center gap-2 text-xs">
          <Badge variant="outline" className="bg-emerald-50 dark:bg-emerald-950/30">
            <CheckCircle2 className="size-3 mr-1" /> Total: {totalCount} entri
          </Badge>
        </div>

        {/* Search */}
        <div className="flex gap-2">
          <Input
            type="text"
            placeholder="Cari kata Jawa (mis. aku, arep, mangan)..."
            value={searchQuery}
            onChange={e => setSearchQuery(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && handleSearch()}
            className="flex-1"
          />
          <Button size="sm" onClick={handleSearch} disabled={loading}>
            {loading ? <Loader2 className="size-4 animate-spin" /> : <Search className="size-4" />}
          </Button>
        </div>

        {/* Results (read-only display) */}
        {results.length > 0 && (
          <ScrollArea className="h-[400px] rounded-md border">
            <div className="space-y-1 p-2">
              {results.map((entry) => (
                <div
                  key={entry.id}
                  className="rounded p-2 border"
                >
                  <div className="flex items-start gap-2">
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 flex-wrap">
                        <span className="font-mono font-bold text-sm">{entry.ngoko}</span>
                        <span className="text-muted-foreground">→</span>
                        <span className="text-sm">{entry.krama || '(kosong)'}</span>
                        {entry.krama_inggil && (
                          <Badge variant="outline" className="text-[10px] bg-purple-50 dark:bg-purple-950/30">
                            ki: {entry.krama_inggil}
                          </Badge>
                        )}
                      </div>
                      <div className="text-xs text-muted-foreground mt-0.5">
                        {entry.arti || '(tidak ada arti Indonesia)'}
                      </div>
                      {entry.keterangan && (
                        <div className="text-[10px] text-muted-foreground/70 italic mt-1 line-clamp-2">
                          {entry.keterangan}
                        </div>
                      )}
                    </div>
                    <div className="shrink-0">
                      <Badge
                        variant="outline"
                        className={`text-xs ${entry.status === 'clean' || entry.status === 'ready' ? 'bg-green-50 dark:bg-green-950/30' : 'bg-yellow-50 dark:bg-yellow-950/30'}`}
                      >
                        {entry.status === 'clean' || entry.status === 'ready' ? '✓ approved' : 'draft'}
                      </Badge>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </ScrollArea>
        )}

        {/* Empty state */}
        {results.length === 0 && searchQuery && !loading && (
          <div className="text-sm text-muted-foreground text-center py-4">
            Tidak ada hasil untuk &quot;{searchQuery}&quot;. Coba kata lain.
          </div>
        )}

        {/* Info */}
        <p className="text-xs text-muted-foreground">
          <strong>Cara pakai:</strong> Search kata → lihat entry (ngoko + krama + arti).
          Untuk edit/add entry: pakai <code>kamus-tui.py</code> di MacBook → upload ke Supabase.
          Web app cuma baca kamus, tidak edit. Edit langsung di DB Supabase juga bisa
          (validasi level 2 kalau ada keanehan terjemahan).
        </p>
      </CardContent>
    </Card>
  )
}
