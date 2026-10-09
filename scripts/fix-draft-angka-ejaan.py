#!/usr/bin/env python3
"""
fix-draft-angka-ejaan.py — Propagasikan fix ejaan angka ke kamus-jawa-draft.json

Patch spesifik (idempotent):
  1. Entry ngoko='siji'         : krama ', eka,' atau ' eka,' → ' éka'
  2. Entry ngoko='sanga, songo' : ngoko → 'sanga'
  3. Entry ngoko='' krama='Nol'  : krama → 'nol'
"""

import json
from pathlib import Path

DRAFT = Path("/home/z/my-project/public/kamus-jawa-draft.json")


def fix_krama_eka(kr):
    """Replace 'eka' (alone, comma/space separated) → 'éka' in krama field."""
    if not kr:
        return kr, False
    tokens = [t.strip() for t in kr.split(",")]
    changed = False
    new_tokens = []
    for t in tokens:
        if t == "eka":
            new_tokens.append("éka")
            changed = True
        else:
            new_tokens.append(t)
    return ", ".join(new_tokens), changed


def fix_ngoko_songo(ng):
    """Remove 'songo' token from ngoko field (comma-separated)."""
    if not ng:
        return ng, False
    tokens = [t.strip() for t in ng.split(",") if t.strip()]
    if "songo" not in tokens:
        return ng, False
    new_tokens = [t for t in tokens if t != "songo"]
    return ", ".join(new_tokens) if new_tokens else "", True


def fix_krama_nol(kr):
    """Replace 'Nol' → 'nol' in krama field."""
    if kr == "Nol":
        return "nol", True
    return kr, False


def main():
    if not DRAFT.exists():
        print(f"❌ File tidak ditemukan: {DRAFT}")
        return 1

    with open(DRAFT, "r", encoding="utf-8") as f:
        data = json.load(f)

    konseps = data["words"]
    print(f"Loaded: {len(konseps):,} konseps dari draft")

    fixes = {"eka_to_éka": 0, "songo_removed": 0, "Nol_to_nol": 0}

    for i, k in enumerate(konseps):
        # Fix 1: krama "eka" → "éka" (hanya untuk angka 1 entry yang ngoko='siji')
        # Tapi jangan hanya batasi ke 'siji' — bisa ada entry lain dengan krama eka
        ng = k.get("ngoko", "") or ""
        kr = k.get("krama", "") or ""

        # Cek keterangan 'angka 1' untuk konfirmasi
        ket = k.get("keterangan", "") or ""
        is_angka_1 = "angka 1" in ket and "angka 1 " not in ket.replace("angka 1", "angka 1 ")  # quick check
        # Lebih aman: cek apakah ngoko='siji' dan arti='satu'
        if ng.strip().lower() == "siji" and "eka" in kr:
            new_kr, changed = fix_krama_eka(kr)
            if changed:
                k["krama"] = new_kr
                fixes["eka_to_éka"] += 1
                print(f"  [{i}] krama eka→éka: {kr!r} → {new_kr!r}")

        # Fix 2: ngoko "sanga, songo" → "sanga"
        if ng.strip().lower() == "sanga, songo":
            new_ng, changed = fix_ngoko_songo(ng)
            if changed:
                k["ngoko"] = new_ng
                fixes["songo_removed"] += 1
                print(f"  [{i}] ngoko songo dihapus: {ng!r} → {new_ng!r}")

        # Fix 3: krama "Nol" → "nol" (angka 0)
        if "angka 0" in ket and kr.strip() == "Nol":
            new_kr, changed = fix_krama_nol(kr)
            if changed:
                k["krama"] = new_kr
                fixes["Nol_to_nol"] += 1
                print(f"  [{i}] krama Nol→nol: {kr!r} → {new_kr!r}")

    print(f"\n=== FIXES APPLIED ===")
    for k, v in fixes.items():
        print(f"  {k}: {v}")

    # Bump version
    old_ver = data.get("metadata", {}).get("version", "?")
    try:
        parts = old_ver.split(".")
        if len(parts) == 2 and parts[0].isdigit() and parts[1].isdigit():
            new_ver = f"{parts[0]}.{int(parts[1]) + 1}"
        else:
            new_ver = old_ver + "+ejaan"
    except Exception:
        new_ver = old_ver + "+ejaan"
    data.setdefault("metadata", {})["version"] = new_ver
    data["metadata"]["last_fix"] = "fix-draft-angka-ejaan.py: eka→éka, songo dari ngoko→hapus, Nol→nol"

    with open(DRAFT, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"\n✓ Saved: {DRAFT} (v{old_ver} → v{new_ver})")
    return 0


if __name__ == "__main__":
    exit(main())
