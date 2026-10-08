-- ============================================================
-- Migration v2 — Project-based Dual SRT Editor
-- ============================================================
-- Run SQL ini di Supabase SQL Editor (Dashboard > SQL Editor > New query)
--
-- Perubahan:
-- 1. srt_projects: tambah kolom original_srt_id (SRT Indonesia konteks)
-- 2. srt_cues: tambah kolom text_id (Indonesia konteks per cue) + voice (per-cue voice assignment)
--
-- Backward compatible: kolom lama (original_srt, text) tetap dipakai sebagai SRT Jawa + text Jawa
-- ============================================================

-- Step 1: Tambah kolom ke srt_projects
ALTER TABLE srt_projects
  ADD COLUMN IF NOT EXISTS original_srt_id TEXT;

-- Step 2: Tambah kolom ke srt_cues
ALTER TABLE srt_cues
  ADD COLUMN IF NOT EXISTS text_id TEXT,
  ADD COLUMN IF NOT EXISTS voice TEXT DEFAULT '';

-- Step 3: Index untuk query cepat (kalau belum ada)
CREATE INDEX IF NOT EXISTS idx_srt_cues_project ON srt_cues(project_id);
CREATE INDEX IF NOT EXISTS idx_srt_projects_user ON srt_projects(user_id);

-- Step 4: Update timestamp trigger (optional, supaya updated_at auto-update)
-- Kalau sudah ada trigger dari migration v1, skip bagian ini
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = now();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_srt_projects_updated_at ON srt_projects;
CREATE TRIGGER trg_srt_projects_updated_at
  BEFORE UPDATE ON srt_projects
  FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS trg_srt_cues_updated_at ON srt_cues;
CREATE TRIGGER trg_srt_cues_updated_at
  BEFORE UPDATE ON srt_cues
  FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- ============================================================
-- Verifikasi (run setelah migrate, harus return data):
-- SELECT column_name, data_type FROM information_schema.columns
--   WHERE table_name IN ('srt_projects', 'srt_cues')
--   ORDER BY table_name, ordinal_position;
-- ============================================================
