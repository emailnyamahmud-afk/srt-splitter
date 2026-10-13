-- ============================================================
-- Migration v4 — RENAME arti → indo, DROP register (R-26)
-- ============================================================
-- Run SQL ini di Supabase SQL Editor (Dashboard > SQL Editor > New query)
--
-- Perubahan:
-- 1. RENAME kolom arti → indo (terjemahan Indonesia, BUKAN definisi Jawa)
--    Alasan: 'arti' diisi AI dengan keterangan (halu), rename ke 'indo' supaya jelas
--    'indo' juga tidak konflik dengan 'id' (Supabase UUID PK)
-- 2. DROP kolom register (R-26: 1 entry = multi bahasa, register tidak relevan)
--
-- Catatan: krama_inggil TIDAK ADA di DB (tidak pernah di-add via migration v3)
-- → tidak perlu merge atau drop. krama_inggil sudah jadi sinonim di kolom krama.
--
-- Status: SUDAH DI-RUN 13 Okt 2026. Sukses.
-- ============================================================

-- Step 1: RENAME arti → indo
ALTER TABLE kamus
  RENAME COLUMN arti TO indo;

-- Step 2: DROP kolom register (kalau masih ada)
ALTER TABLE kamus
  DROP COLUMN IF EXISTS register;

-- Step 3: Verifikasi (run setelah migrate)
-- SELECT column_name FROM information_schema.columns
--   WHERE table_name = 'kamus' ORDER BY ordinal_position;
-- Harus return 10 kolom: id, ngoko, aksara, krama, indo, keterangan, sumber, status, created_at, updated_at
