-- ============================================================
-- Migration v4 — DROP krama_inggil + register columns (R-26)
-- ============================================================
-- Run SQL ini di Supabase SQL Editor (Dashboard > SQL Editor > New query)
--
-- Perubahan:
-- 1. DROP kolom krama_inggil dari table kamus (R-26: krama_inggil sudah jadi sinonim di kolom krama)
-- 2. DROP kolom register dari table kamus (R-26: register 100% 'umum' tidak informatif)
--
-- Sebelum drop: pastikan krama_inggil values sudah di-merge ke krama (comma-separated)
-- Kalau krama_inggil masih ada nilai, merge dulu:
--   UPDATE kamus SET krama = CONCAT(krama, ', ', krama_inggil) WHERE krama_inggil != '';
--   (run ini SEBELUM DROP)
--
-- Setelah migrate, verifikasi:
--   SELECT column_name FROM information_schema.columns
--     WHERE table_name = 'kamus' ORDER BY ordinal_position;
--   (harus: id, ngoko, aksara, krama, arti, keterangan, sumber, status, created_at, updated_at)
-- ============================================================

-- Step 0: Merge krama_inggil values ke krama (jika ada)
UPDATE kamus
  SET krama = TRIM(BOTH ', ' FROM CONCAT(COALESCE(krama, ''), ', ', COALESCE(krama_inggil, '')))
  WHERE krama_inggil IS NOT NULL AND krama_inggil != '';

-- Step 1: DROP kolom krama_inggil
ALTER TABLE kamus
  DROP COLUMN IF EXISTS krama_inggil;

-- Step 2: DROP kolom register
ALTER TABLE kamus
  DROP COLUMN IF EXISTS register;

-- Step 3: Verifikasi (run setelah migrate, harus return 10 kolom tanpa krama_inggil + register)
-- SELECT column_name, data_type FROM information_schema.columns
--   WHERE table_name = 'kamus'
--   ORDER BY ordinal_position;
