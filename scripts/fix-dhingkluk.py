#!/usr/bin/env python3
"""
fix-dhingkluk.py — Patch khusus dhingkluk (R-12 violation fix per user 9 Okt 2026)

User konfirmasi:
  - dhingkluk arti = "menunduk"
  - Long form ("tunduk/menghadap ke bawah; menunduk") dipindah ke keterangan
  - User akan isi/edit manual nanti via TUI

Idempotent.
"""

import json
from pathlib import Path

DRAFT = Path("/home/z/my-project/public/kamus-jawa-draft.json")


def main():
    if not DRAFT.exists():
        print(f"❌ File tidak ditemukan: {DRAFT}")
        return 1

    with open(DRAFT, "r", encoding="utf-8") as f:
        data = json.load(f)

    konseps = data["words"]
    print(f"Loaded: {len(konseps):,} konseps dari draft")

    fixed = 0
    for i, k in enumerate(konseps):
        ng = (k.get("ngoko", "") or "").strip().lower()
        if ng != "dhingkluk":
            continue

        # Found dhingkluk entry
        old_arti = (k.get("arti", "") or "").strip()
        old_ket = (k.get("keterangan", "") or "").strip()

        print(f"\n=== BEFORE (index {i}) ===")
        print(f"  ngoko:      {k.get('ngoko','')!r}")
        print(f"  krama:      {k.get('krama','')!r}")
        print(f"  arti:       {old_arti!r}  ({len(old_arti)} chars)")
        print(f"  keterangan: {old_ket!r}")

        # Apply fix per user instruction:
        # - arti = "menunduk" (per user)
        # - keterangan: append long form for user reference (user isi manual nanti)
        new_arti = "menunduk"
        long_form = "tunduk/menghadap ke bawah; menunduk"  # dari arti lama

        # Gabung keterangan lama + long form (kalau ada)
        if old_ket:
            # Cek dulu kalau long_form sudah ada di keterangan
            if long_form.lower() not in old_ket.lower():
                new_ket = f"{old_ket} | {long_form}"
            else:
                new_ket = old_ket
        else:
            new_ket = long_form

        k["arti"] = new_arti
        k["keterangan"] = new_ket
        fixed += 1

        print(f"\n=== AFTER (index {i}) ===")
        print(f"  ngoko:      {k.get('ngoko','')!r}")
        print(f"  krama:      {k.get('krama','')!r}")
        print(f"  arti:       {k.get('arti','')!r}  ({len(k.get('arti',''))} chars)")
        print(f"  keterangan: {k.get('keterangan','')!r}")

    if fixed == 0:
        print("\n⚠ Tidak ada entry 'dhingkluk' ditemukan — sudah fixed?")
        return 1

    # Bump version
    old_ver = data.get("metadata", {}).get("version", "?")
    try:
        parts = old_ver.split(".")
        if len(parts) == 2 and parts[0].isdigit() and parts[1].isdigit():
            new_ver = f"{parts[0]}.{int(parts[1]) + 1}"
        else:
            new_ver = old_ver + "+dhingkluk"
    except Exception:
        new_ver = old_ver + "+dhingkluk"
    data.setdefault("metadata", {})["version"] = new_ver
    data["metadata"]["last_fix"] = "fix-dhingkluk.py: arti='menunduk', long form ke keterangan (per user 9 Okt 2026)"

    with open(DRAFT, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"\n✓ Saved: {DRAFT} (v{old_ver} → v{new_ver}) — {fixed} entry fixed")
    return 0


if __name__ == "__main__":
    exit(main())
