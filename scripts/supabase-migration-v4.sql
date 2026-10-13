-- ============================================================
-- Migration v4 — RENAME arti → indo, DROP krama_inggil + register (R-26)
-- ============================================================
-- Run SQL ini di Supabase SQL Editor (Dashboard > SQL Editor > New query)
--
-- Perubahan:
-- 1. RENAME kolom arti → indo (terjemahan Indonesia, BUKAN definisi Jawa)
--    Alasan: 'arti' diisi AI dengan keterangan (halu), rename ke 'indo' supaya jelas
--    'indo' juga tidak konflik dengan 'id' (Supabase UUID PK)
-- 2. DROP kolom krama_inggil (R-26: krama_inggil jadi sinonim di kolom krama)
-- 3. DROP kolom register (R-26: 1 entry = multi bahasa, register tidak relevan)
--
-- Setelah migrate, verifikasi:
--   SELECT column_name FROM information_schema.columns
--     WHERE table_name = 'kamus' ORDER BY ordinal_position;
--   (harus: id, ngoko, aksara, krama, indo, keterangan, sumber, status, created_at, updated_at)
-- ============================================================

-- Step 0: Merge krama_inggil values ke krama (jika ada, sebelum DROP)
UPDATE kamus
  SET krama = TRIM(BOTH ', ' FROM CONCAT(COALESCE(krama, ''), ', ', COALESCE(krama_inggil, '')))
  WHERE krama_inggil IS NOT NULL AND krama_inggil != '';

-- Step 1: RENAME arti → indo
ALTER TABLE kamus
  RENAME COLUMN arti TO indo;

-- Step 2: DROP kolom krama_inggil
ALTER TABLE kamus
  DROP COLUMN IF EXISTS krama_inggil;

-- Step 3: DROP kolom register
ALTER TABLE kamus
  DROP COLUMN IF EXISTS register;

-- Step 4: Verifikasi (run setelah migrate)
-- SELECT column_name, data_type FROM information_schema.columns
--   WHERE table_name = 'kamus'
--   ORDER BY ordinal_position;
-- Harus return 10 kolom: id, ngoko, aksara, krama, indo, keterangan, sumber, status, created_at, updated_at
