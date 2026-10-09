#!/usr/bin/env python3
"""
upload-supabase.py — Upload entri kamus ke Supabase (USER-TRIGGERED ONLY)

⚠ KRITIS — R-12 + R-18 + R-22 COMPLIANCE:
  - HANYA entries dengan status='ready' (USER EXPLICIT APPROVE via menu "Mark READY").
    3-field lengkap TIDAK otomatis = ready. User harus explicit mark ready di TUI.
  - JANGAN upload entries NETRAL (field 'word' terisi, ngoko kosong) — belum terdefinisi.
  - JANGAN upload entries dengan status='draft' — belum user validate.
  - JANGAN auto-run script ini. Hanya jalan kalau user klik menu '☁ Upload ke Supabase'
    di kamus-tui.py dan konfirmasi eksplisit (y/n) dengan preview entries.

R-21 compliance:
  - Field `word` di kamus-draft.json TIDAK di-upload (DB Supabase tidak punya kolom word).
  - Field `entry_id`, `is_angka`, `is_lemma`, `source_count` TIDAK di-upload (DB tidak punya).
  - Hanya upload: ngoko, aksara, krama, krama_inggil (R-17: kosong by design), arti,
    keterangan (R-18: pertahankan konteks), register, sumber, status.

DB Supabase struktur aktual (10 Okt 2026, verified via REST API):
  Table `kamus` (12 kolom):
    id (uuid, auto-gen), ngoko, aksara, krama, krama_inggil, arti, keterangan,
    register, sumber, status, created_at, updated_at
  Total rows saat ini: 0 (DB clean sejak task docs-update-v2.27)

Usage:
  # Dipanggil dari kamus-tui.py (menu '☁ Upload ke Supabase'):
  python3 upload-supabase.py

  # Standalone (env vars harus di-set):
  NEXT_PUBLIC_SUPABASE_URL=xxx NEXT_PUBLIC_SUPABASE_ANON_KEY=yyy python3 upload-supabase.py

Env vars (atau .env di ~/Dubbing/):
  NEXT_PUBLIC_SUPABASE_URL=https://xxx.supabase.co
  NEXT_PUBLIC_SUPABASE_ANON_KEY=eyJxxx...
"""

import json
import os
import sys
import urllib.request
import urllib.error
from pathlib import Path


def load_env_file():
    """Load .env dari ~/Dubbing/.env kalau ada."""
    env_file = Path.home() / 'Dubbing' / '.env'
    if not env_file.exists():
        return
    with open(env_file, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            if '=' in line:
                key, value = line.split('=', 1)
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                if key and key not in os.environ:
                    os.environ[key] = value


def collect_ready_entries(data):
    """Filter entries yang status='ready' (R-12: user EXPLICIT approve via menu).

    Returns:
        list of dict (DB-ready rows) — hanya entries dengan:
        - status == 'ready' (USER EXPLICIT mark via menu "Mark READY/DRAFT bulk")
        - ngoko + krama + arti SEMUA terisi (3-field lengkap)
    """
    ready = []
    skipped_draft = 0
    skipped_netral = 0
    skipped_incomplete = 0

    for entry in data.get("words", []):
        ngoko = (entry.get("ngoko") or "").strip()
        krama = (entry.get("krama") or "").strip()
        arti = (entry.get("arti") or "").strip()
        word = (entry.get("word") or "").strip()
        status = (entry.get("status") or "draft").strip().lower()

        # R-21: NETRAL entries (word terisi, ngoko kosong) → skip, belum terdefinisi
        if word and not ngoko:
            skipped_netral += 1
            continue

        # 3-field wajib
        if not (ngoko and krama and arti):
            skipped_incomplete += 1
            continue

        # R-12: HANYA status='ready' (user EXPLICIT mark via menu, bukan auto dari 3-field)
        if status != "ready":
            skipped_draft += 1
            continue

        # Build row (hanya kolom yang ada di DB)
        ki = (entry.get("krama_inggil") or "").strip()
        register = (entry.get("register") or "umum").strip()
        sumber = (entry.get("sumber") or "kamus-jawa-draft.json (R-22)").strip()
        row = {
            "ngoko": ngoko,
            "aksara": entry.get("aksara", ""),
            "krama": krama,
            "krama_inggil": ki,        # R-17: kosong by design (kramainggil masuk krama)
            "arti": arti,
            "keterangan": entry.get("keterangan", ""),
            "register": register,
            "sumber": sumber,
            "status": "ready",        # DB status (mirror dari draft)
        }
        ready.append(row)

    return ready, {
        "skipped_draft": skipped_draft,
        "skipped_netral": skipped_netral,
        "skipped_incomplete": skipped_incomplete,
    }


def confirm_upload(ready_entries, stats, url):
    """Tampilkan preview + konfirmasi eksplisit sebelum upload.

    User harus ketik 'y' untuk lanjut. Apapun selain 'y' = batal.
    """
    print()
    print("  " + "═" * 58)
    print("  ⚠  KONFIRMASI UPLOAD KE SUPABASE  ⚠")
    print("  " + "═" * 58)
    print()
    print(f"  📊 Stats draft kamus-jawa-draft.json:")
    print(f"     Total entries ready (akan di-upload): {len(ready_entries):>6,}")
    print(f"     Skipped (status='draft', belum user approve): {stats['skipped_draft']:>6,}")
    print(f"     Skipped (NETRAL/word-only, belum terdefinisi): {stats['skipped_netral']:>6,}")
    print(f"     Skipped (3-field belum lengkap):              {stats['skipped_incomplete']:>6,}")
    print()
    print(f"  🎯 Target: {url[:50]}")
    print(f"     Table: kamus")
    print(f"     Mode: INSERT (bukan upsert — duplikat ngoko akan jadi 2 row)")
    print()

    if len(ready_entries) == 0:
        print("  ❌ Tidak ada entries untuk di-upload. Batal.")
        input("\n  Tekan Enter...")
        return False

    # Tampilkan sample 5 entries yang akan di-upload
    print("  📖 Sample 5 entries yang akan di-upload:")
    print()
    for i, row in enumerate(ready_entries[:5], 1):
        print(f"    {i}. ngoko:  {row['ngoko'][:35]!r}")
        print(f"       krama: {row['krama'][:35]!r}")
        print(f"       arti:  {row['arti'][:35]!r}")
        print(f"       register: {row['register']}  sumber: {row['sumber'][:30]!r}")
        print()

    if len(ready_entries) > 5:
        print(f"    ... +{len(ready_entries) - 5} entries lagi")
        print()

    print("  ⚠ PERINGATAN:")
    print("     - Script akan INSERT row baru ke table kamus di Supabase.")
    print("     - TIDAK ada undo. Kalau upload duplikat, harus hapus manual di Supabase Table Editor.")
    print("     - Pastikan kamu sudah validasi entries INI sebelum upload (R-12).")
    print("     - R-22: SEMUA raw + parser DIHAPUS, jangan rebuild dari raw (sampah parsing tolol).")
    print()
    print("  Ketik 'y' untuk konfirmasi upload, atau apapun untuk batal.")
    answer = input("  > ").strip().lower()
    return answer == 'y'


def do_upload(ready_entries, url, key):
    """POST entries ke Supabase REST API dalam batch 500."""
    headers = {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        # Hapus 'Prefer: resolution=merge-duplicates' karena:
        # - Tabel kamus TIDAK punya unique constraint selain id (uuid PK)
        # - merge-duplicates = upsert, tapi tanpa unique constraint = tidak merge, insert biasa
        # - Pakai return=minimal untuk hemat bandwidth
        "Prefer": "return=minimal",
    }

    batch_size = 500
    success = 0
    failed = 0
    failed_batch_error = None

    for i in range(0, len(ready_entries), batch_size):
        batch = ready_entries[i:i + batch_size]
        batch_json = json.dumps(batch)
        ins_url = f"{url}/rest/v1/kamus"
        ins_req = urllib.request.Request(
            ins_url,
            data=batch_json.encode("utf-8"),
            headers=headers,
            method="POST",
        )
        try:
            urllib.request.urlopen(ins_req)
            success += len(batch)
            print(f"  → {success}/{len(ready_entries)} uploaded...", end="\r")
        except urllib.error.HTTPError as e:
            failed += len(batch)
            error_body = e.read().decode("utf-8", errors="replace")[:500]
            print(f"\n  ❌ HTTP {e.code} (batch {i//batch_size + 1}): {error_body}")
            failed_batch_error = (e.code, error_body)
            break
        except Exception as e:
            failed += len(batch)
            print(f"\n  ❌ Error (batch {i//batch_size + 1}): {e}")
            failed_batch_error = (None, str(e))
            break

    print()
    print(f"\n  ✅ Upload selesai: {success} sukses, {failed} gagal")
    if failed_batch_error:
        print(f"     First error: HTTP {failed_batch_error[0]} — {failed_batch_error[1][:200]}")
    return success, failed


def main():
    load_env_file()

    # R-22: kamus-jawa-draft.json = SATU-SATUNYA sumber (NETRAL).
    kamus_path = Path.home() / "Dubbing" / "kamus-jawa-draft.json"

    url = os.environ.get("NEXT_PUBLIC_SUPABASE_URL", "")
    key = os.environ.get("NEXT_PUBLIC_SUPABASE_ANON_KEY", "")

    if not url or not key:
        print("\n  ❌ Supabase belum di-set.")
        print()
        print("  Cara 1: Buat file .env di ~/Dubbing/ (RECOMMEND):")
        print('    nano ~/Dubbing/.env')
        print('  Isi:')
        print('    NEXT_PUBLIC_SUPABASE_URL=https://xxx.supabase.co')
        print('    NEXT_PUBLIC_SUPABASE_ANON_KEY=eyJxxx...')
        print()
        print("  Cara 2: Set env vars manual:")
        print('  export NEXT_PUBLIC_SUPABASE_URL="https://xxx.supabase.co"')
        print('  export NEXT_PUBLIC_SUPABASE_ANON_KEY="eyJxxx..."')
        input("\n  Tekan Enter...")
        sys.exit(1)

    if not kamus_path.exists():
        print(f"\n  ❌ Kamus JSON tidak ditemukan: {kamus_path}")
        print(f"     R-22: kamus-jawa-draft.json = satu-satunya sumber (NETRAL).")
        print(f"     Download: curl -L -o ~/Dubbing/kamus-jawa-draft.json \"https://raw.githubusercontent.com/emailnyamahmud-afk/srt-splitter/main/public/kamus-jawa-draft.json?v=26\"")
        input("\n  Tekan Enter...")
        sys.exit(1)

    print(f"\n  → Load kamus: {kamus_path}")
    with open(kamus_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Step 1: Filter entries ready (R-12: status='ready' = user explicit approve)
    ready_entries, stats = collect_ready_entries(data)

    # Step 2: Konfirmasi eksplisit (R-12: AI DILARANG upload tanpa konfirmasi user)
    if not confirm_upload(ready_entries, stats, url):
        print("\n  ⏹ Dibatalkan oleh user. Tidak ada data di-upload.")
        input("\n  Tekan Enter...")
        return

    # Step 3: Upload (batch 500)
    print(f"\n  🚀 Mengupload {len(ready_entries)} entries...")
    success, failed = do_upload(ready_entries, url, key)

    input("\n  Tekan Enter untuk kembali...")


if __name__ == "__main__":
    main()
