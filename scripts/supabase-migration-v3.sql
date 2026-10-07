-- ============================================================
-- Migration v3 — Kamus schema upgrade (krama_inggil + register columns)
-- ============================================================
-- Run SQL ini di Supabase SQL Editor (Dashboard > SQL Editor > New query)
--
-- Perubahan:
-- 1. kamus: tambah kolom krama_inggil (kata krama inggil + alias)
-- 2. kamus: tambah kolom register ('ngoko'|'krama'|'krama_inggil'|'kawi'|'umum')
--
-- Backward compatible: kolom lama (ngoko, krama, arti, keterangan, sumber) tetap dipakai
-- Kolom baru krama_inggil + register bisa kosong (default: krama_inggil='', register='umum')
--
-- Setelah migrate, jalankan Python script untuk re-import kamus:
--   python3 scripts/parse-wiktionary-jv.py input.xml output.json
--   python3 scripts/edit-kamus.py import output.json
-- ============================================================

-- Step 1: Tambah kolom krama_inggil ke kamus
ALTER TABLE kamus
  ADD COLUMN IF NOT EXISTS krama_inggil TEXT DEFAULT '';

-- Step 2: Tambah kolom register ke kamus
ALTER TABLE kamus
  ADD COLUMN IF NOT EXISTS register TEXT DEFAULT 'umum';

-- Step 3: Verifikasi (run setelah migrate)
-- SELECT column_name, data_type, column_default
--   FROM information_schema.columns
--   WHERE table_name = 'kamus'
--   ORDER BY ordinal_position;

-- Expected output (10 kolom):
--   id           | uuid          | gen_random_uuid()
--   ngoko        | text         |
--   aksara       | text         |
--   krama        | text         |
--   krama_inggil | text         | ''                 ← NEW
--   arti         | text         |
--   keterangan   | text         |
--   register     | text         | 'umum'             ← NEW
--   sumber       | text         |
--   status       | text         |
--   created_at   | timestamp    | now()
--   updated_at   | timestamp    | now()

-- Step 4 (optional, setelah re-import): cek distribusi register
-- SELECT register, COUNT(*) FROM kamus GROUP BY register ORDER BY count DESC;
-- Expected:
--   ngoko         | ~22000
--   umum          | ~19000
--   kawi          | ~2200
--   krama_inggil  | ~95
--   krama         | ~2

-- ============================================================
-- Catatan untuk re-import kamus (Python):
-- 1. Re-parse XML: python3 scripts/parse-wiktionary-jv.py
--    → generate kamus-jawa-full.json v5 (44.585 entri, dengan krama_inggil + register)
-- 2. Backup existing user edits (kalau ada):
--    python3 scripts/edit-kamus.py export
--    → backup ke kamus-jawa-backup.json
-- 3. Re-import kamus baru (UPGRADE, bukan REPLACE):
--    python3 scripts/edit-kamus.py import public/kamus-jawa-full.json
--    → upsert semua entri (existing user edits di arti/krama dipertahankan
--      kalau ngoko word sama — pakai UPSERT dengan ON CONFLICT)
-- ============================================================
