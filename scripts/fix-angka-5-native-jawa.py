#!/usr/bin/env python3
"""
fix-angka-5-native-jawa.py — Fix angka 5, 15, 25, 50 per native Jawa 7 varian

User 9 Okt 2026 (native Jawa, paham 7 varian: ngoko, ngapak, krama lugu,
krama inggil, dialek Wonosobo, dialek Banyumas):

  angka 5:
    ngoko = 'limo'              (dari 'lima' — native casual/dialek Banyumas)
    krama = 'gangsal'           (dari 'gangsal, ponco, panca' —Wiktionary cocok)
    arti  = 'lima'              (tetap)

  angka 15:
    ngoko = 'limolas'           (dari 'limalas, limolas' — user pilih limolas)
    krama = 'gangsal welas'     (tetap)
    arti  = 'lima belas'        (tetap)

  angka 25:
    ngoko = 'sèlawé, selawe'    (baku + sinonim, dari 'sèlawé' saja)
    krama = 'selangkung'        (tetap)
    arti  = 'dua puluh lima'    (tetap)

  angka 50:
    ngoko = 'séket, seket'      (baku + sinonim, dari 'séket' saja)
    krama = 'séket'             (tetap — bukan bug, native Jawa bilang memang sama)
    arti  = 'lima puluh'        (tetap)

Komposisi (35, 45, 55, 115, dst.) TIDAK diubah — user: 'yg lain benar'.
Komposisi tetap pakai 'lima' (formal numeral), bukan 'limo' (casual standalone).

Idempotent. Apply ke angka-raw.json + kamus-jawa-draft.json.
"""

import json
from pathlib import Path

ANGKA_RAW = Path("/home/z/my-project/public/angka-raw.json")
DRAFT = Path("/home/z/my-project/public/kamus-jawa-draft.json")


# Fix specification per user
FIXES = {
    5: {"ngoko": "limo", "krama": "gangsal", "arti": "lima"},
    15: {"ngoko": "limolas", "krama": "gangsal welas", "arti": "lima belas"},
    25: {"ngoko": "sèlawé, selawe", "krama": "selangkung", "arti": "dua puluh lima"},
    50: {"ngoko": "séket, seket", "krama": "séket", "arti": "lima puluh"},
}


def fix_angka_raw():
    """Apply 4 fixes ke angka-raw.json."""
    with open(ANGKA_RAW, "r", encoding="utf-8") as f:
        data = json.load(f)

    words = data["words"]
    print(f"Loaded angka-raw.json: {len(words)} entries (v{data['metadata'].get('version','?')})")

    fixed = []
    for w in words:
        ket = w.get("keterangan", "")
        # Match "angka N" or "angka N. ..."
        import re
        m = re.match(r"angka (\d+)(\.|\s|$)", ket)
        if not m:
            continue
        n = int(m.group(1))
        if n not in FIXES:
            continue

        old_ng = w.get("ngoko", "")
        old_kr = w.get("krama", "")
        old_ar = w.get("arti", "")
        new = FIXES[n]

        if old_ng != new["ngoko"] or old_kr != new["krama"] or old_ar != new["arti"]:
            print(f"\n  angka {n}:")
            print(f"    BEFORE: ngoko={old_ng!r}  krama={old_kr!r}  arti={old_ar!r}")
            w["ngoko"] = new["ngoko"]
            w["krama"] = new["krama"]
            w["arti"] = new["arti"]
            print(f"    AFTER:  ngoko={w['ngoko']!r}  krama={w['krama']!r}  arti={w['arti']!r}")
            fixed.append(n)

    # Bump version
    old_ver = data["metadata"].get("version", "?")
    try:
        parts = old_ver.split(".")
        if len(parts) == 2 and parts[0].isdigit() and parts[1].isdigit():
            new_ver = f"{parts[0]}.{int(parts[1]) + 1}"
        else:
            new_ver = old_ver + "+native"
    except Exception:
        new_ver = old_ver + "+native"
    data["metadata"]["version"] = new_ver
    data["metadata"]["last_fix"] = "fix-angka-5-native-jawa.py: angka 5/15/25/50 per native Jawa 7 varian"

    with open(ANGKA_RAW, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"\n✓ angka-raw.json: {len(fixed)} entries fixed (v{old_ver} → v{new_ver})")
    return fixed


def fix_draft():
    """Apply same 4 fixes ke kamus-jawa-draft.json (entries dengan keterangan 'angka N')."""
    with open(DRAFT, "r", encoding="utf-8") as f:
        data = json.load(f)

    konseps = data["words"]
    print(f"\nLoaded kamus-jawa-draft.json: {len(konseps):,} entries (v{data.get('metadata',{}).get('version','?')})")

    import re
    fixed = []
    for i, k in enumerate(konseps):
        ket = k.get("keterangan", "") or ""
        # Cari pattern "angka N" atau "| angka N" atau "... | angka N | ..."
        m = re.search(r"\bangka (\d+)\b", ket)
        if not m:
            continue
        n = int(m.group(1))
        if n not in FIXES:
            continue

        old_ng = (k.get("ngoko", "") or "").strip()
        old_kr = (k.get("krama", "") or "").strip()
        old_ar = (k.get("arti", "") or "").strip()
        new = FIXES[n]

        if old_ng != new["ngoko"] or old_kr != new["krama"] or old_ar != new["arti"]:
            print(f"\n  [{i}] angka {n}:")
            print(f"    BEFORE: ngoko={old_ng!r}  krama={old_kr!r}  arti={old_ar!r}")
            k["ngoko"] = new["ngoko"]
            k["krama"] = new["krama"]
            k["arti"] = new["arti"]
            print(f"    AFTER:  ngoko={k['ngoko']!r}  krama={k['krama']!r}  arti={k['arti']!r}")
            fixed.append((i, n))

    # Bump version
    old_ver = data.get("metadata", {}).get("version", "?")
    try:
        parts = old_ver.split(".")
        if len(parts) == 2 and parts[0].isdigit() and parts[1].isdigit():
            new_ver = f"{parts[0]}.{int(parts[1]) + 1}"
        else:
            new_ver = old_ver + "+native"
    except Exception:
        new_ver = old_ver + "+native"
    data.setdefault("metadata", {})["version"] = new_ver
    data["metadata"]["last_fix"] = "fix-angka-5-native-jawa.py: angka 5/15/25/50 per native Jawa 7 varian"

    with open(DRAFT, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"\n✓ kamus-jawa-draft.json: {len(fixed)} entries fixed (v{old_ver} → v{new_ver})")
    return fixed


def main():
    print("="*70)
    print("📖 Fix angka 5/15/25/50 per native Jawa 7 varian")
    print("="*70)
    print()
    print("User confirmation (native Jawa, 7 varian: ngoko/ngapak/krama lugu/")
    print("krama inggil/dialek Wonosobo/dialek Banyumas):")
    print()
    for n, f in FIXES.items():
        print(f"  angka {n}: ngoko={f['ngoko']!r}  krama={f['krama']!r}  arti={f['arti']!r}")
    print()
    print("Komposisi (35, 45, 55, 115, dst.) TIDAK diubah — 'yg lain benar'.")
    print()

    fixed_raw = fix_angka_raw()
    fixed_draft = fix_draft()

    print()
    print(f"=== SUMMARY ===")
    print(f"  angka-raw.json: {len(fixed_raw)} entries fixed: {fixed_raw}")
    print(f"  kamus-jawa-draft.json: {len(fixed_draft)} entries fixed: {[n for _, n in fixed_draft]}")


if __name__ == "__main__":
    main()
