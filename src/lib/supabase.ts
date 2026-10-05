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
// Table structure (run di Supabase SQL Editor):
//
// -- Table: srt_projects
// CREATE TABLE srt_projects (
//   id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
//   user_id UUID,  -- anonymous session ID (tidak perlu auth.users)
//   name TEXT NOT NULL,
//   language TEXT DEFAULT 'jawa',
//   original_srt TEXT,
//   cue_count INT DEFAULT 0,
//   cues_edited INT DEFAULT 0,
//   created_at TIMESTAMPTZ DEFAULT now(),
//   updated_at TIMESTAMPTZ DEFAULT now()
// );
//
// -- Table: srt_cues
// CREATE TABLE srt_cues (
//   id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
//   project_id UUID REFERENCES srt_projects(id) ON DELETE CASCADE,
//   cue_index INT NOT NULL,
//   start_sec FLOAT NOT NULL,
//   end_sec FLOAT NOT NULL,
//   text TEXT NOT NULL,
//   register TEXT DEFAULT '',
//   is_edited BOOLEAN DEFAULT false,
//   created_at TIMESTAMPTZ DEFAULT now(),
//   updated_at TIMESTAMPTZ DEFAULT now()
// );
//
// -- Index untuk query cepat
// CREATE INDEX idx_srt_cues_project ON srt_cues(project_id);
// CREATE INDEX idx_srt_projects_user ON srt_projects(user_id);
//
// -- RLS (Row Level Security) — anonymous, semua bisa akses (untuk sekarang)
// ALTER TABLE srt_projects ENABLE ROW LEVEL SECURITY;
// ALTER TABLE srt_cues ENABLE ROW LEVEL SECURITY;
// CREATE POLICY "allow_all_projects" ON srt_projects FOR ALL USING (true);
// CREATE POLICY "allow_all_cues" ON srt_cues FOR ALL USING (true);
//
// Fallback: kalau env vars tidak set, web app tetap jalan dengan localStorage
// (supabase.ts return null, rapikan-jawa-panel pakai entries state saja)

import { createClient, type SupabaseClient } from '@supabase/supabase-js'

export interface SrtProject {
  id: string
  user_id: string | null
  name: string
  language: string
  original_srt: string | null
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
  text: string
  register: string  // 'ngoko' | 'krama' | 'krama_inggil' | ''
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

  const { data, error } = await client
    .from('srt_cues')
    .select('*')
    .eq('project_id', projectId)
    .order('cue_index', { ascending: true })

  if (error) {
    console.error('[Supabase] getCues error:', error)
    return []
  }

  return data as SrtCue[]
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
