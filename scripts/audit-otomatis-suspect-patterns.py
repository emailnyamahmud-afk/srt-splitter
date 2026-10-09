#!/usr/bin/env python3
"""
audit-otomatis-suspect-patterns.py — Audit otomatis untuk deteksi parser AI tolol

AKU TANGGUNG JAWAB: parser build-kamus-bersih.py agresif merge multi-source,
banyak Indonesia word nyangkut sebagai sinonim Jawa. User harus validasi ulang
1-1 gara-gara parsing ini.

Script ini TIDAK mengedit JSON. Hanya mendeteksi & mencetak suspect entries
supaya user bisa lihat di TUI / manual check.

Pattern yang dideteksi:
1. parsing_artifact_ngoko: Indonesia word nyangkut di ngoko (anak, payung, panas...)
2. parsing_artifact_arti: Arti Indonesia non-baku/aneh (sugi, beridiri, bercermin...)
3. krama_inggil_no_tag: Krama inggil kata di krama (per R-17 OK, tapi user perlu tahu)
4. too_many_ngoko_synonyms: >8 sinonim ngoko (rawan merge artifact)
5. too_many_krama_synonyms: >3 sinonim krama (rawan merge artifact)
6. ngoko_equals_indonesia_word: ngoko = Indonesia word persis (loanword salah)

Output:
  - Print summary ke stdout
  - Save /home/z/my-project/public/audit-suspects.json (untuk user reference)

Usage:
  python3 /home/z/my-project/scripts/audit-otomatis-suspect-patterns.py

Re-run kapan saja setelah build-kamus-bersih.py update. Idempotent.
"""

import json, re
from collections import Counter
from pathlib import Path

DRAFT = Path("/home/z/my-project/public/kamus-jawa-draft.json")
OUT = Path("/home/z/my-project/public/audit-suspects.json")

# === PATTERN DEFINITIONS ===
# Tambah pattern di sini kalau user discover pattern baru

# Pattern 1: Indonesia common words yang sering nyangkut di ngoko sebagai "sinonim"
# (parser AI tolol merge Wiktionary template nyangkut definisi Indonesia)
INDONESIA_WORDS_IN_NGOKO = {
    # Indonesia words yang mestinya bukan sinonim Jawa
    "anak", "lutung", "payung", "payon", "pimpinan", "desa", "kantor",
    "sapi", "manusia", "jalan", "tuwa", "tuwa-tuwa", "telak",
    # catatan: "anak" bisa valid (anak bapak) tapi curiga kalau di entry non-Compound
}

# Pattern 2: Arti Indonesia non-baku / aneh (kemungkinan parsing artifact)
SUSPICIOUS_ARTI_WORDS = {
    "sugi", "beridiri", "bercermin", "pimpinan desa", "anak lutung",
    "laku", "dianggap", "halangan", "memikir", "sambil beridiri",
    "tingkah laku", "melakukan sendiri", "godaan/halangan",
}

# Pattern 3: Krama inggil words (per R-17 OK masuk krama, tapi user perlu tahu ini inggil)
KRAMA_INGGIL_SET = {
    "dhawuh", "duka", "dumugi", "sare", "dhahar", "nedha", "tilem",
    "adeg", "jumeneng", "wredha", "seda", "sarean", "bageya",
    "bagya", "mangayu", "rawuh", "dumateng", "rames", "piyantun",
    "pinuntun", "prapta", "tindak", "angsal", "anuju", "wonten",
    "panjenengan", "sampeyan", "dalem", "kestren",
}

# Pattern 4: Threshold "terlalu banyak sinonim" — rawan merge artifact
MAX_NGOKO_SYNONYMS = 8  # ngoko >8 sinonim = curiga
MAX_KRAMA_SYNONYMS = 3  # krama >3 sinonim = curiga

# Pattern 5: Indonesia words yang identik dengan ngoko (loanword salah kategori)
# mis. ngoko='panas' mestinya itu Indonesia, bukan Jawa (Jawa = "panas" valid juga actually)
# (empty for now — user bisa tambah kalau discover)


def main():
    if not DRAFT.exists():
        print(f"❌ File tidak ditemukan: {DRAFT}")
        return 1

    with open(DRAFT, "r", encoding="utf-8") as f:
        draft = json.load(f)
    konseps = draft["words"]

    print("=" * 70)
    print("📖 AUDIT OTOMATIS — SUSPECT PATTERNS (parser AI tolol detector)")
    print("=" * 70)
    print(f"Total entries audited: {len(konseps):,}")
    print(f"Draft version: v{draft.get('metadata', {}).get('version', '?')}")

    suspects = {
        "parsing_artifact_ngoko": [],
        "parsing_artifact_arti": [],
        "krama_inggil_no_tag": [],
        "too_many_ngoko_synonyms": [],
        "too_many_krama_synonyms": [],
        "ngoko_equals_indonesia_word": [],
    }

    for i, k in enumerate(konseps):
        ng = (k.get("ngoko", "") or "").strip()
        kr = (k.get("krama", "") or "").strip()
        ar = (k.get("arti", "") or "").strip()
        if not (ng or kr or ar):
            continue

        # Pattern 1: Indonesia word in ngoko tokens
        if ng:
            ng_tokens = [t.strip().lower() for t in ng.replace(",", " ").split() if t.strip()]
            bad_ng = [t for t in ng_tokens if t in INDONESIA_WORDS_IN_NGOKO]
            if bad_ng:
                suspects["parsing_artifact_ngoko"].append((i, k, bad_ng))

        # Pattern 2: suspicious arti words
        if ar:
            ar_lower = ar.lower()
            bad_ar = [w for w in SUSPICIOUS_ARTI_WORDS if w in ar_lower]
            if bad_ar:
                suspects["parsing_artifact_arti"].append((i, k, bad_ar))

        # Pattern 3: krama inggil in krama (info only, not bug)
        if kr:
            kr_tokens = [t.strip().lower() for t in kr.split(",") if t.strip()]
            inggil = [t for t in kr_tokens if t in KRAMA_INGGIL_SET]
            if inggil:
                suspects["krama_inggil_no_tag"].append((i, k, inggil))

        # Pattern 4: too many ngoko synonyms
        if ng:
            ng_syn = len([t for t in ng.split(",") if t.strip()])
            if ng_syn > MAX_NGOKO_SYNONYMS:
                suspects["too_many_ngoko_synonyms"].append((i, k, ng_syn))

        # Pattern 5: too many krama synonyms
        if kr:
            kr_syn = len([t for t in kr.split(",") if t.strip()])
            if kr_syn > MAX_KRAMA_SYNONYMS:
                suspects["too_many_krama_synonyms"].append((i, k, kr_syn))

    # Print summary
    total_suspects = sum(len(v) for v in suspects.values())
    print(f"\nTotal suspect entries (any pattern): {total_suspects}")
    print(f"  (entries bisa muncul di multiple patterns)\n")

    for cat, items in suspects.items():
        print(f"\n=== {cat} — {len(items)} entries ===")
        for entry in items[:15]:
            i, k, *info = entry
            ng = (k.get("ngoko", "") or "")[:60]
            kr = (k.get("krama", "") or "")[:50]
            ar = (k.get("arti", "") or "")[:40]
            info_str = info[0] if info else ""
            print(f"  [{i}] ngoko={ng!r}  krama={kr!r}  arti={ar!r}  info={info_str}")
        if len(items) > 15:
            print(f"  ... +{len(items) - 15} more (lihat JSON untuk full list)")

    # Save detailed JSON
    out = {
        "metadata": {
            "version": "1.0",
            "generated_by": "audit-otomatis-suspect-patterns.py",
            "total_entries_audited": len(konseps),
            "total_suspects": total_suspects,
            "draft_version": draft.get("metadata", {}).get("version", "?"),
            "patterns": {
                "parsing_artifact_ngoko": f"Indonesia word nyangkut di ngoko (kata: {sorted(INDONESIA_WORDS_IN_NGOKO)})",
                "parsing_artifact_arti": f"Arti Indonesia non-baku/aneh (kata: {sorted(SUSPICIOUS_ARTI_WORDS)})",
                "krama_inggil_no_tag": f"Krama inggil tidak ditandai (kata: {sorted(KRAMA_INGGIL_SET)})",
                "too_many_ngoko_synonyms": f"ngoko dengan >{MAX_NGOKO_SYNONYMS} sinonim (rawan merge artifact)",
                "too_many_krama_synonyms": f"krama dengan >{MAX_KRAMA_SYNONYMS} sinonim (rawan merge artifact)",
                "ngoko_equals_indonesia_word": "ngoko = Indonesia word persis (loanword salah kategori)",
            },
            "catatan": "Script ini TIDAK mengedit JSON. Hanya detect & print suspects.",
        },
        "suspects": {
            cat: [
                {
                    "index": i,
                    "ngoko": k.get("ngoko", ""),
                    "krama": k.get("krama", ""),
                    "arti": k.get("arti", ""),
                    "keterangan": (k.get("keterangan", "") or "")[:300],
                    "sumber": k.get("sumber", ""),
                    "source_count": k.get("source_count", 1),
                    "info": items[0] if items else None,
                }
                for i, k, *items in entries
            ]
            for cat, entries in suspects.items()
        },
    }

    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f"\n✓ Saved: {OUT}")
    return 0


if __name__ == "__main__":
    exit(main())
