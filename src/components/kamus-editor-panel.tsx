'use client'

import { useCallback, useEffect, useState } from 'react'
import { Search, Edit3, CheckCircle2, AlertTriangle, Loader2, BookOpen } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Badge } from '@/components/ui/badge'
import { ScrollArea } from '@/components/ui/scroll-area'
import { toast } from 'sonner'
import {
  isSupabaseAvailable,
  searchKamus,
  updateKamusEntry,
  countKamus,
  type KamusEntry,
} from '@/lib/supabase'

export function KamusEditorPanel() {
  const [ready, setReady] = useState(false)
  const [searchQuery, setSearchQuery] = useState('')
  const [results, setResults] = useState<KamusEntry[]>([])
  const [totalCount, setTotalCount] = useState(0)
  const [editingId, setEditingId] = useState<string | null>(null)
  const [editKrama, setEditKrama] = useState('')
  const [editId, setEditId] = useState('')
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

  const startEdit = useCallback((entry: KamusEntry) => {
    setEditingId(entry.id)
    setEditKrama(entry.krama || '')
    setEditId(entry.id || '')
  }, [])

  const saveEdit = useCallback(async () => {
    if (!editingId) return
    const ok = await updateKamusEntry(editingId, {
      krama: editKrama,
      id: editId,
      status: 'clean',  // user edit = clean (approved)
    })
    if (ok) {
      // Update local results
      setResults(prev => prev.map(r =>
        r.id === editingId ? { ...r, krama: editKrama, id: editId, status: 'clean' } : r
      ))
      toast.success('Kamus diperbarui (status: clean)')
    } else {
      toast.error('Gagal simpan kamus')
    }
    setEditingId(null)
  }, [editingId, editKrama, editId])

  if (!ready) return null

  return (
    <Card className="mt-4 border-emerald-200 dark:border-emerald-800">
      <CardHeader>
        <CardTitle className="text-lg flex items-center gap-2">
          <BookOpen className="size-5 text-emerald-600" />
          Kamus Jawa Editor
        </CardTitle>
        <CardDescription>
          Edit krama + arti (id) permanen ke Supabase. Status: draft (belum diedit) → clean (fix, approved).
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

        {/* Results */}
        {results.length > 0 && (
          <ScrollArea className="h-[400px] rounded-md border">
            <div className="space-y-1 p-2">
              {results.map((entry) => (
                <div
                  key={entry.id}
                  className={`rounded p-2 ${editingId === entry.id ? 'border-2 border-emerald-400 bg-emerald-50/30' : 'border'}`}
                >
                  {editingId === entry.id ? (
                    // Edit mode
                    <div className="space-y-2">
                      <div className="text-sm font-medium">{entry.word}</div>
                      <div className="grid grid-cols-2 gap-2">
                        <div>
                          <Label className="text-xs">Krama</Label>
                          <Input
                            value={editKrama}
                            onChange={e => setEditKrama(e.target.value)}
                            placeholder="kata krama"
                            className="h-8 text-sm"
                          />
                        </div>
                        <div>
                          <Label className="text-xs">Arti (id)</Label>
                          <Input
                            value={editId}
                            onChange={e => setEditId(e.target.value)}
                            placeholder="arti dalam Indonesia"
                            className="h-8 text-sm"
                          />
                        </div>
                      </div>
                      <div className="flex gap-2">
                        <Button size="sm" onClick={saveEdit} className="h-7 text-xs">Simpan (clean)</Button>
                        <Button size="sm" variant="outline" onClick={() => setEditingId(null)} className="h-7 text-xs">Batal</Button>
                      </div>
                    </div>
                  ) : (
                    // View mode
                    <div className="flex items-start gap-2">
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2">
                          <span className="font-mono font-bold text-sm">{entry.word}</span>
                          <span className="text-muted-foreground">→</span>
                          <span className="text-sm">{entry.krama || '(kosong)'}</span>
                        </div>
                        <div className="text-xs text-muted-foreground mt-0.5">
                          {entry.id || '(tidak ada arti)'}
                        </div>
                      </div>
                      <div className="shrink-0 flex items-center gap-2">
                        <Badge
                          variant="outline"
                          className={`text-xs ${entry.status === 'clean' ? 'bg-green-50 dark:bg-green-950/30' : 'bg-yellow-50 dark:bg-yellow-950/30'}`}
                        >
                          {entry.status === 'clean' ? '✓ clean' : 'draft'}
                        </Badge>
                        <Button
                          size="sm"
                          variant="ghost"
                          onClick={() => startEdit(entry)}
                          className="h-7 px-2"
                        >
                          <Edit3 className="size-3.5" />
                        </Button>
                      </div>
                    </div>
                  )}
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
          <strong>Cara pakai:</strong> Cari kata → klik edit → isi krama + arti → Simpan (status: clean).
          Data tersimpan permanen di Supabase. Draft = belum diedit, Clean = sudah fix (approved user).
        </p>
      </CardContent>
    </Card>
  )
}
