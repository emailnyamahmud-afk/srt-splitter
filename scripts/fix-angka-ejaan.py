#!/usr/bin/env python3
"""
fix-angka-ejaan.py — Koreksi ejaan Jawa di angka-raw.json

Aturan ejaan Jawa modern (PUEBI-style):
  é = /e/  close-mid  (wajib diakritik)
  è = /ɛ/  open-mid   (wajib diakritik)
  ê = /ə/  schwa      → modern tulis polos "e" (TANPA diakritik)

Sanskrit loans yang still punya /e/ close-mid:
  eka → éka (/eka/)

Fixes:
  1. angka 0:   krama "Nol"     → "nol"        (konsistensi lowercase)
  2. angka 1:   krama "eka"     → "éka"        (Sanskrit एक /eka/)
  3. angka 9:   ngoko "sanga, songo" → "sanga" (songo = KRAMA, user R-12)

Idempotent: re-run aman (cek dulu sebelum patch).
"""

import json
from pathlib import Path

ANGKA_RAW = Path("/home/z/my-project/public/angka-raw.json")


def main():
    if not ANGKA_RAW.exists():
        print(f"❌ File tidak ditemukan: {ANGKA_RAW}")
        return 1

    with open(ANGKA_RAW, "r", encoding="utf-8") as f:
        data = json.load(f)

    words = data["words"]
    print(f"Loaded: {len(words)} entries dari angka-raw.json (v{data['metadata'].get('version','?')})")

    fixes_applied = []
    skipped_already_fixed = []

    for i, w in enumerate(words):
        ket = w.get("keterangan", "")
        # Match "angka N" (atau "angka N. ...")
        import re
        m = re.match(r"angka (\d+)(\.|\s|$)", ket)
        if not m:
            continue
        n = int(m.group(1))

        # Fix 1: angka 0 — "Nol" → "nol"
        if n == 0:
            old_kr = w.get("krama", "")
            if old_kr == "Nol":
                w["krama"] = "nol"
                fixes_applied.append((n, "krama", "Nol", "nol"))
            elif old_kr == "nol":
                skipped_already_fixed.append((n, "krama already 'nol'"))

        # Fix 2: angka 1 — "eka" → "éka" (di krama field)
        if n == 1:
            kr = w.get("krama", "")
            if "eka" in kr:
                # Replace "eka" → "éka" tapi HATI-HATI: jangan replace "éka" yang sudah benar
                # dan jangan replace "sekawan" (mengandung "eka" substring)
                new_kr = []
                for token in kr.split(","):
                    t = token.strip()
                    if t == "eka":
                        new_kr.append("éka")
                        if t != "éka":
                            fixes_applied.append((n, "krama", "eka", "éka"))
                    else:
                        new_kr.append(t)
                w["krama"] = ", ".join(new_kr)
            # Cek juga ngoko kalau ada
            ng = w.get("ngoko", "")
            if "eka" in ng:
                new_ng = []
                for token in ng.split(","):
                    t = token.strip()
                    if t == "eka":
                        new_ng.append("éka")
                        if t != "éka":
                            fixes_applied.append((n, "ngoko", "eka", "éka"))
                    else:
                        new_ng.append(t)
                w["ngoko"] = ", ".join(new_ng)

        # Fix 3: angka 9 — hapus "songo" dari ngoko (songo = KRAMA)
        if n == 9:
            ng = w.get("ngoko", "")
            tokens = [t.strip() for t in ng.split(",") if t.strip()]
            if "songo" in tokens:
                # Remove "songo" (krama-only per user R-12)
                new_tokens = [t for t in tokens if t != "songo"]
                w["ngoko"] = ", ".join(new_tokens) if new_tokens else ""
                fixes_applied.append((n, "ngoko", "sanga, songo", "sanga"))
            else:
                if ng == "sanga":
                    skipped_already_fixed.append((n, "ngoko already 'sanga'"))

    print(f"\n=== FIXES APPLIED ({len(fixes_applied)}) ===")
    for fix in fixes_applied:
        print(f"  angka {fix[0]} {fix[1]}: {fix[2]!r} → {fix[3]!r}")

    print(f"\n=== ALREADY FIXED / SKIP ({len(skipped_already_fixed)}) ===")
    for s in skipped_already_fixed:
        print(f"  angka {s[0]}: {s[1]}")

    # Bump version
    old_ver = data["metadata"].get("version", "?")
    try:
        # numeric version bump
        parts = old_ver.split(".")
        if len(parts) == 2 and parts[0].isdigit() and parts[1].isdigit():
            new_ver = f"{parts[0]}.{int(parts[1]) + 1}"
        else:
            new_ver = old_ver + "+ejaan"
    except Exception:
        new_ver = old_ver + "+ejaan"
    data["metadata"]["version"] = new_ver
    data["metadata"]["last_fix"] = "fix-angka-ejaan.py: eka→éka, Nol→nol, songo dari ngoko→hapus"

    # Save
    with open(ANGKA_RAW, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"\n✓ Saved: {ANGKA_RAW} (v{old_ver} → v{new_ver})")
    return 0


if __name__ == "__main__":
    exit(main())
