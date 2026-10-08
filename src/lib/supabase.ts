// Supabase client — untuk simpan SRT project + cue data ke PostgreSQL
//
// Setup (user):
//   1. Daftar supabase.com (free, no credit card)
//   2. Create project → dapat Project URL + anon key
//   3. Copy ke Vercel env vars:
//      NEXT_PUBLIC_SUPABASE_URL=https://xxx.supabase.co
//      NEXT_PUBLIC_SUPABASE_ANON_KEY=eyJxxx
//   4. Run SQL di Supabase SQL Editor (lihat dibawah)
//
// === Migration v1 (initial) ===
//
// CREATE TABLE srt_projects (
//   id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
//   user_id UUID,
//   name TEXT NOT NULL,
//   language TEXT DEFAULT 'jawa',
//   original_srt TEXT,           -- SRT Jawa (file yang diedit)
//   cue_count INT DEFAULT 0,
//   cues_edited INT DEFAULT 0,
//   created_at TIMESTAMPTZ DEFAULT now(),
//   updated_at TIMESTAMPTZ DEFAULT now()
// );
//
// CREATE TABLE srt_cues (
//   id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
//   project_id UUID REFERENCES srt_projects(id) ON DELETE CASCADE,
//   cue_index INT NOT NULL,
//   start_sec FLOAT NOT NULL,
//   end_sec FLOAT NOT NULL,
//   text TEXT NOT NULL,          -- text Jawa (yang diedit)
//   register TEXT DEFAULT '',
//   is_edited BOOLEAN DEFAULT false,
//   created_at TIMESTAMPTZ DEFAULT now(),
//   updated_at TIMESTAMPTZ DEFAULT now()
// );
//
// CREATE INDEX idx_srt_cues_project ON srt_cues(project_id);
// CREATE INDEX idx_srt_projects_user ON srt_projects(user_id);
//
// ALTER TABLE srt_projects ENABLE ROW LEVEL SECURITY;
// ALTER TABLE srt_cues ENABLE ROW LEVEL SECURITY;
// CREATE POLICY "allow_all_projects" ON srt_projects FOR ALL USING (true);
// CREATE POLICY "allow_all_cues" ON srt_cues FOR ALL USING (true);
//
// === Migration v2 (project-based Dual SRT Editor) ===
// Lihat scripts/supabase-migration-v2.sql
//
// ALTER TABLE srt_projects ADD COLUMN IF NOT EXISTS original_srt_id TEXT;
// ALTER TABLE srt_cues ADD COLUMN IF NOT EXISTS text_id TEXT, ADD COLUMN IF NOT EXISTS voice TEXT DEFAULT '';
//
// Fallback: kalau env vars tidak set, web app tetap jalan dengan localStorage

import { createClient, type SupabaseClient } from '@supabase/supabase-js'

export interface SrtProject {
  id: string
  user_id: string | null
  name: string
  language: string
  original_srt: string | null       // SRT Jawa (file yang diedit)
  original_srt_id: string | null   // SRT Indonesia (konteks, read-only) — Migration v2
  cue_count: number
  cues_edited: number
  created_at: string
  updated_at: string
}

export interface SrtCue {
  id: string
  project_id: string
  cue_index: number
  start_sec: number
  end_sec: number
  text: string          // text Jawa (yang diedit)
  text_id: string | null  // text Indonesia (konteks, read-only) — Migration v2
  register: string     // 'ngoko' | 'krama' | 'krama_inggil' | ''
  voice: string         // 'dimas' | 'siti' | 'ardi' | 'gadis' | '' — Migration v2
  is_edited: boolean
  created_at: string
  updated_at: string
}

// Singleton client (lazy init)
let _client: SupabaseClient | null = null
let _anonymousUserId: string | null = null

/**
 * Get Supabase client. Return null kalau env vars tidak set (fallback ke localStorage).
 */
export function getSupabase(): SupabaseClient | null {
  if (_client) return _client

  const url = process.env.NEXT_PUBLIC_SUPABASE_URL
  const anonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY

  if (!url || !anonKey) {
    return null  // Fallback: web app jalan tanpa Supabase (localStorage)
  }

  _client = createClient(url, anonKey, {
    auth: {
      persistSession: true,
      autoRefreshToken: true,
    },
  })

  return _client
}

/**
 * Check apakah Supabase tersedia (env vars set + client connectable)
 */
export function isSupabaseAvailable(): boolean {
  return getSupabase() !== null
}

/**
 * Get anonymous user ID (persist di localStorage, buat baru kalau belum ada)
 * Supabase anonymous auth tidak perlu login, tapi data terisolasi per browser
 */
export function getAnonymousUserId(): string {
  if (_anonymousUserId) return _anonymousUserId

  if (typeof window === 'undefined') return 'server-side'

  const stored = localStorage.getItem('srt-splitter-anon-user-id')
  if (stored) {
    _anonymousUserId = stored
    return stored
  }

  // Generate new UUID (v4)
  const newId = crypto.randomUUID()
  localStorage.setItem('srt-splitter-anon-user-id', newId)
  _anonymousUserId = newId
  return newId
}

/**
 * Create new SRT project
 */
export async function createProject(
  name: string,
  language: string,
  originalSrt: string,
  cueCount: number,
): Promise<SrtProject | null> {
  const client = getSupabase()
  if (!client) return null

  const userId = getAnonymousUserId()

  const { data, error } = await client
    .from('srt_projects')
    .insert({
      user_id: userId,
      name,
      language,
      original_srt: originalSrt,
      cue_count: cueCount,
      cues_edited: 0,
    })
    .select()
    .single()

  if (error) {
    console.error('[Supabase] createProject error:', error)
    return null
  }

  return data as SrtProject
}

/**
 * List all projects for current anonymous user
 */
export async function listProjects(): Promise<SrtProject[]> {
  const client = getSupabase()
  if (!client) return []

  const userId = getAnonymousUserId()

  const { data, error } = await client
    .from('srt_projects')
    .select('*')
    .eq('user_id', userId)
    .order('updated_at', { ascending: false })

  if (error) {
    console.error('[Supabase] listProjects error:', error)
    return []
  }

  return data as SrtProject[]
}

/**
 * Get project by ID
 */
export async function getProject(projectId: string): Promise<SrtProject | null> {
  const client = getSupabase()
  if (!client) return null

  const { data, error } = await client
    .from('srt_projects')
    .select('*')
    .eq('id', projectId)
    .single()

  if (error) {
    console.error('[Supabase] getProject error:', error)
    return null
  }

  return data as SrtProject
}

/**
 * Save all cues for a project (batch insert)
 */
export async function saveCues(
  projectId: string,
  cues: { cue_index: number; start_sec: number; end_sec: number; text: string; register: string }[],
): Promise<boolean> {
  const client = getSupabase()
  if (!client) return false

  // Delete existing cues first (replace)
  await client.from('srt_cues').delete().eq('project_id', projectId)

  // Insert new cues
  const rows = cues.map(c => ({
    project_id: projectId,
    cue_index: c.cue_index,
    start_sec: c.start_sec,
    end_sec: c.end_sec,
    text: c.text,
    register: c.register,
    is_edited: false,
  }))

  const { error } = await client
    .from('srt_cues')
    .insert(rows)

  if (error) {
    console.error('[Supabase] saveCues error:', error)
    return false
  }

  // Update project timestamp
  await client
    .from('srt_projects')
    .update({ updated_at: new Date().toISOString() })
    .eq('id', projectId)

  return true
}

/**
 * Get all cues for a project
 */
export async function getCues(projectId: string): Promise<SrtCue[]> {
  const client = getSupabase()
  if (!client) return []

  // PAGINATION — Supabase default max rows = 1000
  let allCues: SrtCue[] = []
  const pageBatch = 1000
  let offset = 0
  let hasMore = true

  while (hasMore) {
    const { data, error } = await client
      .from('srt_cues')
      .select('*')
      .eq('project_id', projectId)
      .order('cue_index', { ascending: true })
      .range(offset, offset + pageBatch - 1)

    if (error) {
      console.error('[Supabase] getCues error (page ' + offset + '):', error)
      return allCues
    }

    if (data && data.length > 0) {
      allCues = allCues.concat(data as SrtCue[])
    }

    if (!data || data.length < pageBatch) {
      hasMore = false
    } else {
      offset += pageBatch
    }
  }

  return allCues
}

/**
 * Update single cue (auto-save per edit, debounce di caller)
 */
export async function updateCue(
  cueId: string,
  updates: { text?: string; register?: string; is_edited?: boolean },
): Promise<boolean> {
  const client = getSupabase()
  if (!client) return false

  const { error } = await client
    .from('srt_cues')
    .update({
      ...updates,
      updated_at: new Date().toISOString(),
    })
    .eq('id', cueId)

  if (error) {
    console.error('[Supabase] updateCue error:', error)
    return false
  }

  return true
}

/**
 * Delete project (cascade delete cues)
 */
export async function deleteProject(projectId: string): Promise<boolean> {
  const client = getSupabase()
  if (!client) return false

  const { error } = await client
    .from('srt_projects')
    .delete()
    .eq('id', projectId)

  if (error) {
    console.error('[Supabase] deleteProject error:', error)
    return false
  }

  return true
}

/**
 * Update project metadata (name, cues_edited count)
 */
export async function updateProject(
  projectId: string,
  updates: { name?: string; cues_edited?: number },
): Promise<boolean> {
  const client = getSupabase()
  if (!client) return false

  const { error } = await client
    .from('srt_projects')
    .update({
      ...updates,
      updated_at: new Date().toISOString(),
    })
    .eq('id', projectId)

  if (error) {
    console.error('[Supabase] updateProject error:', error)
    return false
  }

  return true
}

// ============================================================
// Dual SRT Project (Migration v2 — project-based workflow)
// ============================================================

/**
 * Create new Dual SRT project (SRT ID + SRT Jawa).
 * Simpan original_srt_id (Indonesia) + original_srt (Jawa) + insert cues dengan text_id + text_jawa.
 *
 * @param name Project name (e.g. "S1-Ep1")
 * @param originalSrtId Konteks SRT Indonesia (full file content)
 * @param originalSrtJawa Editor SRT Jawa (full file content)
 * @param cues Array of cues dengan {cue_index, start_sec, end_sec, text (Jawa), text_id (ID), register, voice}
 */
export async function createDualProject(
  name: string,
  originalSrtId: string,
  originalSrtJawa: string,
  cues: { cue_index: number; start_sec: number; end_sec: number; text: string; text_id: string; register?: string; voice?: string }[],
): Promise<{ project: SrtProject; cues: SrtCue[] } | null> {
  const client = getSupabase()
  if (!client) return null

  const userId = getAnonymousUserId()

  // Step 1: Create project
  const { data: projData, error: projError } = await client
    .from('srt_projects')
    .insert({
      user_id: userId,
      name,
      language: 'jawa',
      original_srt: originalSrtJawa,
      original_srt_id: originalSrtId,
      cue_count: cues.length,
      cues_edited: 0,
    })
    .select()
    .single()

  if (projError || !projData) {
    console.error('[Supabase] createDualProject: project insert error:', projError)
    return null
  }

  const project = projData as SrtProject

  // Step 2: Insert cues (batch — 500 per request, Supabase REST API limit ~1000 rows)
  const cueRows = cues.map(c => ({
    project_id: project.id,
    cue_index: c.cue_index,
    start_sec: c.start_sec,
    end_sec: c.end_sec,
    text: c.text,
    text_id: c.text_id,
    register: c.register || '',
    voice: c.voice || '',
    is_edited: false,
  }))

  const batchSize = 100  // Supabase REST API limit ~1000 rows, tapi text panjang → 100 per batch lebih aman
  let allCueData: SrtCue[] = []
  let insertError: { message: string } | null = null

  for (let i = 0; i < cueRows.length; i += batchSize) {
    const batch = cueRows.slice(i, i + batchSize)
    const { data: batchData, error: batchErr } = await client
      .from('srt_cues')
      .insert(batch)
      .select()

    if (batchErr) {
      console.error('[Supabase] createDualProject: cues insert error (batch):', batchErr)
      insertError = batchErr
      break
    }
    if (batchData) {
      allCueData = allCueData.concat(batchData as SrtCue[])
    }
  }

  if (insertError) {
    return { project, cues: allCueData }
  }

  return { project, cues: allCueData }
}

/**
 * Get project + all cues (including text_id dan voice).
 * Untuk load existing project ke editor.
 */
export async function getProjectWithCues(projectId: string): Promise<{ project: SrtProject; cues: SrtCue[] } | null> {
  const client = getSupabase()
  if (!client) return null

  // Get project
  const { data: projData, error: projError } = await client
    .from('srt_projects')
    .select('*')
    .eq('id', projectId)
    .single()

  if (projError || !projData) {
    console.error('[Supabase] getProjectWithCues: project error:', projError)
    return null
  }

  // Get cues — PAGINATION karena Supabase PostgREST default max rows = 1000
  // .limit(100000) TIDAK BERFUNGSI (PostgREST override)
  // Pakai .range() untuk fetch per batch 1000
  let allCues: SrtCue[] = []
  const pageBatch = 1000
  let offset = 0
  let hasMore = true

  while (hasMore) {
    const { data: pageData, error: pageError } = await client
      .from('srt_cues')
      .select('*')
      .eq('project_id', projectId)
      .order('cue_index', { ascending: true })
      .range(offset, offset + pageBatch - 1)

    if (pageError) {
      console.error('[Supabase] getProjectWithCues: cues error (page ' + offset + '):', pageError)
      return { project: projData as SrtProject, cues: allCues }
    }

    if (pageData && pageData.length > 0) {
      allCues = allCues.concat(pageData as SrtCue[])
    }

    if (!pageData || pageData.length < pageBatch) {
      hasMore = false
    } else {
      offset += pageBatch
    }
  }

  return { project: projData as SrtProject, cues: allCues }
}

/**
 * Update single cue (full fields untuk auto-save per edit).
 * Update: text (Jawa), text_id (kalau user edit konteks), register, voice, is_edited.
 */
export async function updateCueFull(
  cueId: string,
  updates: { text?: string; text_id?: string; register?: string; voice?: string; is_edited?: boolean },
): Promise<boolean> {
  const client = getSupabase()
  if (!client) return false

  const updatePayload: Record<string, unknown> = { ...updates, updated_at: new Date().toISOString() }

  const { error } = await client
    .from('srt_cues')
    .update(updatePayload)
    .eq('id', cueId)

  if (error) {
    console.error('[Supabase] updateCueFull error:', error)
    return false
  }

  return true
}

/**
 * Increment project's cues_edited count + bump updated_at (kalau user edit cue).
 */
export async function bumpProjectEdited(projectId: string, cuesEditedDelta: number): Promise<boolean> {
  const client = getSupabase()
  if (!client) return false

  // Get current count, then update (atomic kalau pakai RPC, tapi simple approach dulu)
  const { data: proj } = await client
    .from('srt_projects')
    .select('cues_edited')
    .eq('id', projectId)
    .single()

  const current = proj?.cues_edited || 0
  const newCount = Math.max(current, current + cuesEditedDelta)

  const { error } = await client
    .from('srt_projects')
    .update({
      cues_edited: newCount,
      updated_at: new Date().toISOString(),
    })
    .eq('id', projectId)

  if (error) {
    console.error('[Supabase] bumpProjectEdited error:', error)
    return false
  }

  return true
}

// ============================================================
// Kamus table — READ-ONLY functions
// ============================================================
// Filosofi (8 Okt 2026): Web app TIDAK edit kamus. Editing hanya via TUI lokal
// (kamus-tui.py) → upload ke Supabase. Web app hanya:
//   - loadKamusJawa (di rapikan-jawa.ts): load kamus ke memory untuk convertRegister
//   - searchKamus: search kamus di DB (untuk display)
//   - countKamus: hitung total entries
// Untuk edit langsung di DB, user bisa pakai Supabase Table Editor (validasi level 2).

export interface KamusEntry {
  id: string
  ngoko: string          // kata ngoko + alias (dipisah koma)
  aksara: string         // aksara Jawa
  krama: string          // kata krama + alias
  krama_inggil: string   // krama inggil (opsional, kosong kalau tidak ada)
  arti: string           // terjemahan Indonesia
  keterangan: string     // definisi JAWA dari XML (bantu user isi arti)
  register: string      // 'ngoko'|'krama'|'krama_inggil'|'kawi'|'umum'
  sumber: string         // sumber data (mis. jv.wiktionary.org)
  status: string         // 'draft' (belum diedit) | 'ready' (siap upload) | 'clean' (sudah fix)
  created_at: string
  updated_at: string
}

/**
 * Search kamus entries (with pagination) — READ-ONLY
 */
export async function searchKamus(
  query: string,
  limit: number = 20,
): Promise<KamusEntry[]> {
  const client = getSupabase()
  if (!client) return []

  // Search di kolom ngoko (bukan word) — konsisten dengan upload dari kamus-tui.py
  // dan loadKamusJawa di rapikan-jawa.ts
  const { data, error } = await client
    .from('kamus')
    .select('*')
    .ilike('ngoko', `%${query}%`)
    .limit(limit)
    .order('ngoko', { ascending: true })

  if (error) {
    console.error('[Supabase] searchKamus error:', error)
    return []
  }

  return data as KamusEntry[]
}

/**
 * Count total kamus entries — READ-ONLY
 */
export async function countKamus(): Promise<number> {
  const client = getSupabase()
  if (!client) return 0

  const { count, error } = await client
    .from('kamus')
    .select('*', { count: 'exact', head: true })

  if (error) {
    console.error('[Supabase] countKamus error:', error)
    return 0
  }

  return count || 0
}
