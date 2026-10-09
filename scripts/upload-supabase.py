#!/usr/bin/env python3
"""
upload-supabase.py — Upload entri kamus yang sudah user-approved ke Supabase

Phase 5: extract dari kamus-tui.py (sebelumnya inline 130 baris string di dalam
fungsi upload_to_supabase()). Sekarang file terpisah, bisa di-test standalone.

Compliance:
- R-12: HANYA upload entries dengan user_approved=True (user wajib validasi 1-1)
- R-18: tidak hapus data lokal, hanya upload yang approved
- R-21: word field TIDAK di-upload (hanya ngoko+krama+arti+keterangan+aksara)

Usage:
  # Dipanggil dari kamus-tui.py:
  python3 upload-supabase.py

  # Atau standalone (env vars harus di-set):
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


def main():
    load_env_file()

    # R-20: kamus-jawa-draft.json = SATU-SATUNYA rujukan.
    # JANGAN fallback ke kamus-jawa-full.json (legacy, raw arsip, BUKAN rujukan).
    kamus_path = Path.home() / "Dubbing" / "kamus-jawa-draft.json"

    url = os.environ.get("NEXT_PUBLIC_SUPABASE_URL", "")
    key = os.environ.get("NEXT_PUBLIC_SUPABASE_ANON_KEY", "")

    if not url or not key:
        print("\n  ❌ Supabase belum di-set.")
        print()
        print("  Cara 1: Buat file .env di ~/Dubbing/ (RECOMMEND, sekali buat, jalan terus):")
        print()
        print('    nano ~/Dubbing/.env')
        print()
        print('  Isi file .env:')
        print('    NEXT_PUBLIC_SUPABASE_URL=https://xxx.supabase.co')
        print('    NEXT_PUBLIC_SUPABASE_ANON_KEY=eyJxxx...')
        print()
        print("  Save (Ctrl+X, Y, Enter)")
        print()
        print("  Cara 2: Set env vars manual di terminal (hilang saat terminal close):")
        print('  export NEXT_PUBLIC_SUPABASE_URL="https://xxx.supabase.co"')
        print('  export NEXT_PUBLIC_SUPABASE_ANON_KEY="eyJxxx..."')
        input("\n  Tekan Enter...")
        sys.exit(1)

    if not kamus_path.exists():
        print("\n  ❌ Kamus JSON tidak ada di ~/Dubbing/")
        input("\n  Tekan Enter...")
        sys.exit(1)

    print(f"\n  → Load kamus: {kamus_path}")
    with open(kamus_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Filter: HANYA upload entries yang USER APPROVED (R-12 compliance)
    # Syarat: ngoko + krama + arti terisi (status=ready) DAN user_approved=True
    # User wajib validasi 1-1 di TUI sebelum upload ke Supabase
    edited = []
    for entry in data.get("words", []):
        ngoko = (entry.get("ngoko") or "").strip()
        krama = (entry.get("krama") or "").strip()
        arti = (entry.get("arti") or "").strip()
        approved = bool(entry.get("user_approved"))

        # 3 field wajib + user_approved
        if ngoko and krama and arti and approved:
            ki = (entry.get("krama_inggil") or "").strip()
            register = (entry.get("register") or "").strip()
            # SEMUA row harus punya keys yang sama (Supabase PGRST102: all keys must match)
            row = {
                "ngoko": ngoko,
                "aksara": entry.get("aksara", ""),
                "krama": krama,
                "krama_inggil": ki,        # opsional, kosong kalau tidak ada
                "arti": arti,
                "keterangan": entry.get("keterangan", ""),
                "register": register,      # kosong/umum kalau tidak ada
                "sumber": entry.get("sumber", "jv.wiktionary.org"),
                "status": "ready",
            }
            edited.append(row)

    if not edited:
        print("  ⚠ Tidak ada entri yang SIAP UPLOAD.")
        print("     Syarat: ngoko + krama + arti SEMUA terisi (3 field wajib)")
        print("            DAN user_approved=True (edit entry di TUI untuk approve).")
        print("     Flow: Browse SIAP UPLOAD → pilih entry → edit (auto-mark approved)")
        input("\n  Tekan Enter...")
        sys.exit(0)

    print(f"  → {len(edited)} entri akan di-upload")
    print(f"  → Supabase: {url[:40]}...")
    print()

    headers = {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "Prefer": "resolution=merge-duplicates,return=minimal",
    }

    batch_size = 500
    success = 0
    failed = 0
    for i in range(0, len(edited), batch_size):
        batch = edited[i:i + batch_size]
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
            print(f"  → {success}/{len(edited)}...", end="\r")
        except urllib.error.HTTPError as e:
            failed += len(batch)
            error_body = e.read().decode("utf-8", errors="replace")[:300]
            print(f"\n  ❌ HTTP {e.code}: {error_body}")
            break
        except Exception as e:
            failed += len(batch)
            print(f"\n  ❌ Error: {e}")
            break

    print(f"\n  ✅ Upload: {success} sukses, {failed} gagal")
    input("\n  Tekan Enter untuk kembali...")


if __name__ == "__main__":
    main()
