#!/usr/bin/env python3
"""
build-kamus-bersih.py — Merge raw kamus + filter yang 3-field lengkap → kamus-jawa-bersih.json

Tujuan:
  Konsolidasi 2 file raw → 1 file bersih siap masuk database Supabase.

Input (raw):
  1. /home/z/my-project/public/kamus-jawa-full.json (44.585 entries, dari Wiktionary XML)
  2. /home/z/my-project/public/kamus-jawa-new-lemma.json (859 entries, dari scrape jv:Lema)

Output:
  1. /home/z/my-project/public/kamus-jawa-bersih.json
     — Entries dengan 3 field wajib LENGKAP: ngoko + krama + arti (Indonesia)
     — Plus keterangan asli (dipertahankan), aksara (bonus kalau ada)
     — Sinonim comma-separated, dedup, trimmed
     — Siap upload ke Supabase
  2. /home/z/my-project/public/kamus-jawa-draft.json
     — Entries dengan ngoko + arti (Indonesia) tapi krama kosong
     — User isi krama manual di kamus-tui.py → pindah ke bersih
  3. /home/z/my-project/public/kamus-jawa-bersih-report.txt
     — Statistik merge

Schema bersih (sesuai user spec 9 Okt 2026):
  {
    "ngoko": "aku, nyong, inyong",        # sinonim comma-separated
    "krama": "kula, dalem, abdi",          # sinonim comma-separated
    "arti": "aku, saya, gue, gua",         # sinonim Indonesia comma-separated
    "keterangan": "sesulih pandarbé...",   # asli dari Wiktionary Jawa, dipertahankan
    "aksara": "ꦲꦏꦸ",                     # bonus, kalau ada
    "sumber": "id.wiktionary.org + scrape jv:Lema"
  }

Filosofi:
  - Raw = working draft (44.585 + 859 = 45.444 entries, banyak field kosong)
  - Bersih = siap pakai (hanya 3-field lengkap, sinonim rapi)
  - Draft = staging area (user isi krama manual → pindah ke bersih)
  - Supabase DB = ground of truth (user upload bertahap, target 2.000 entries)

Usage:
  python3 build-kamus-bersih.py
  python3 build-kamus-bersih.py --dry-run
"""

import json
import re
from pathlib import Path
import argparse

# ============================================================
# Config
# ============================================================
RAW_FULL = Path("/home/z/my-project/public/kamus-jawa-full.json")
RAW_LEMMA = Path("/home/z/my-project/public/kamus-jawa-new-lemma.json")

OUT_BERSIH = Path("/home/z/my-project/public/kamus-jawa-bersih.json")
OUT_DRAFT = Path("/home/z/my-project/public/kamus-jawa-draft.json")
OUT_REPORT = Path("/home/z/my-project/public/kamus-jawa-bersih-report.txt")


# ============================================================
# Normalisasi sinonim
# ============================================================
def normalize_sinonim(value):
    """Normalize field comma-separated: split, trim, dedup, lowercase, join.

    Input: "Aku, Nyong,  Inyong , Aku"
    Output: "aku, nyong, inyong"
    """
    if not value:
        return ""
    parts = []
    seen = set()
    for w in value.split(","):
        w = w.strip().lower()
        # Skip empty, skip words with newline (multi-line leak dari definisi)
        if not w or "\n" in w or "|" in w or "[" in w or "{" in w:
            continue
        # Skip jika ada angka atau karakter aneh (artifact dari parser)
        if w in seen:
            continue
        seen.add(w)
        parts.append(w)
    return ", ".join(parts)


def clean_keterangan(value):
    """Clean keterangan: hapus sisa template/link, trim.

    Input: "{{banyumas}} terbuka lebar"
    Output: "terbuka lebar"
    """
    if not value:
        return ""
    # Hapus template {{...}} sederhana (1 level)
    v = re.sub(r"\{\{[^}]+\}\}", "", value)
    # Hapus link [[...]] → ambil text (boleh dengan pipe)
    v = re.sub(r"\[\[([^]|]+)\|([^]]+)\]\]", r"\2", v)
    v = re.sub(r"\[\[([^]]+)\]\]", r"\1", v)
    # Hapus sisa bracket aneh
    v = re.sub(r"\[\[?", "", v)
    v = v.strip().strip(";,. ").replace("  ", " ")
    # Trim per baris, max 10 baris
    lines = [ln.strip().strip(";,. ") for ln in v.split("\n") if ln.strip()]
    return "\n".join(lines[:10])


# ============================================================
# Load raw
# ============================================================
def load_raw(path):
    """Load kamus JSON, return list of word entries.

    Format support:
      - {"metadata": {...}, "words": [...]} → ambil words
      - [...] → langsung
    """
    if not path.exists():
        print(f"⚠ File tidak ditemukan: {path}")
        return []
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, dict) and "words" in data:
        return data["words"]
    if isinstance(data, list):
        return data
    print(f"⚠ Format tidak dikenali di {path}: {type(data).__name__}")
    return []


# ============================================================
# Build bersih entry
# ============================================================
def build_entry(raw):
    """Build entry bersih dari raw. Return dict atau None kalau skip.

    Rules:
      - ngoko + arti wajib (arti = Indonesia translation)
      - krama: kalau ada → masuk 'bersih'. Kalau kosong → masuk 'draft'
      - keterangan + aksara dipertahankan
    """
    ngoko = normalize_sinonim(raw.get("ngoko", ""))
    krama = normalize_sinonim(raw.get("krama", ""))
    arti = normalize_sinonim(raw.get("arti", ""))
    keterangan = clean_keterangan(raw.get("keterangan", ""))
    aksara = raw.get("aksara", "").strip()
    sumber = raw.get("sumber", "Wiktionary")

    # Wajib: ngoko + arti (arti = Indonesia)
    if not ngoko or not arti:
        return None

    entry = {
        "ngoko": ngoko,
        "krama": krama,
        "arti": arti,
        "keterangan": keterangan,
        "aksara": aksara,
        "sumber": sumber,
    }
    return entry


# ============================================================
# Dedup bersih
# ============================================================
def dedup_bersih(entries):
    """Dedup entries by (ngoko, krama, arti) tuple. Keep first."""
    seen = set()
    unique = []
    for e in entries:
        key = (e["ngoko"], e["krama"], e["arti"])
        if key in seen:
            continue
        seen.add(key)
        unique.append(e)
    return unique


# ============================================================
# Main
# ============================================================
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    print("📦 Loading raw kamus...")
    full_words = load_raw(RAW_FULL)
    lemma_words = load_raw(RAW_LEMMA)
    print(f"  kamus-jawa-full.json: {len(full_words)} entries")
    print(f"  kamus-jawa-new-lemma.json: {len(lemma_words)} entries")
    print()

    # Merge semua
    all_raw = full_words + lemma_words
    print(f"  Total raw: {len(all_raw)} entries")
    print()

    # Filter
    bersih = []
    draft = []
    skipped = 0
    for raw in all_raw:
        if not isinstance(raw, dict):
            skipped += 1
            continue
        entry = build_entry(raw)
        if entry is None:
            skipped += 1
            continue
        if entry["krama"]:
            bersih.append(entry)
        else:
            draft.append(entry)
    print(f"🔍 Filter results:")
    print(f"  Bersih (ngoko + krama + arti lengkap): {len(bersih)}")
    print(f"  Draft (ngoko + arti, krama kosong)    : {len(draft)}")
    print(f"  Skipped (gak punya ngoko atau arti)   : {skipped}")
    print()

    # Dedup
    bersih = dedup_bersih(bersih)
    draft = dedup_bersih(draft)
    print(f"  Setelah dedup:")
    print(f"    Bersih: {len(bersih)}")
    print(f"    Draft : {len(draft)}")
    print()

    # Stats
    stats = {
        "input_full": len(full_words),
        "input_lemma": len(lemma_words),
        "input_total": len(all_raw),
        "bersih_count": len(bersih),
        "draft_count": len(draft),
        "skipped": skipped,
        "bersih_with_aksara": sum(1 for e in bersih if e["aksara"]),
        "bersih_with_keterangan": sum(1 for e in bersih if e["keterangan"]),
        "draft_with_aksara": sum(1 for e in draft if e["aksara"]),
        "draft_with_keterangan": sum(1 for e in draft if e["keterangan"]),
    }

    # Sample
    print("📋 Sample bersih (5 pertama):")
    for e in bersih[:5]:
        print(f"  ngoko={e['ngoko']!r}, krama={e['krama']!r}, arti={e['arti']!r}")
        if e["aksara"]:
            print(f"    aksara={e['aksara']!r}")
    print()
    print("📋 Sample draft (5 pertama):")
    for e in draft[:5]:
        print(f"  ngoko={e['ngoko']!r}, krama=(KOSONG), arti={e['arti']!r}")

    if args.dry_run:
        print("\n⚠ Dry run, tidak save file")
        return

    # Save
    bersih_output = {
        "metadata": {
            "version": "1.0",
            "source": "merged kamus-jawa-full.json + kamus-jawa-new-lemma.json",
            "description": "Entries dengan 3 field wajib lengkap (ngoko + krama + arti Indonesia)",
            "entries": len(bersih),
            "with_aksara": stats["bersih_with_aksara"],
            "with_keterangan": stats["bersih_with_keterangan"],
            "schema": {
                "ngoko": "sinonim comma-separated",
                "krama": "sinonim comma-separated",
                "arti": "sinonim Indonesia comma-separated",
                "keterangan": "asli dari Wiktionary Jawa, dipertahankan",
                "aksara": "aksara Jawa (opsional, bonus)",
                "sumber": "sumber data entry ini",
            },
        },
        "words": bersih,
    }
    with open(OUT_BERSIH, "w", encoding="utf-8") as f:
        json.dump(bersih_output, f, ensure_ascii=False, indent=2)
    print(f"\n✓ Save bersih: {OUT_BERSIH} ({len(bersih)} entries)")

    draft_output = {
        "metadata": {
            "version": "1.0",
            "source": "merged kamus-jawa-full.json + kamus-jawa-new-lemma.json",
            "description": "Entries dengan ngoko + arti Indonesia, TAPI krama masih kosong",
            "entries": len(draft),
            "with_aksara": stats["draft_with_aksara"],
            "with_keterangan": stats["draft_with_keterangan"],
            "note": "User isi krama manual di kamus-tui.py → pindah ke kamus-jawa-bersih.json",
        },
        "words": draft,
    }
    with open(OUT_DRAFT, "w", encoding="utf-8") as f:
        json.dump(draft_output, f, ensure_ascii=False, indent=2)
    print(f"✓ Save draft: {OUT_DRAFT} ({len(draft)} entries)")

    # Report
    with open(OUT_REPORT, "w", encoding="utf-8") as f:
        f.write("Build Kamus Bersih Report\n")
        f.write("=" * 50 + "\n\n")
        f.write("Input:\n")
        f.write(f"  kamus-jawa-full.json       : {stats['input_full']:>7} entries\n")
        f.write(f"  kamus-jawa-new-lemma.json   : {stats['input_lemma']:>7} entries\n")
        f.write(f"  Total raw                  : {stats['input_total']:>7} entries\n\n")
        f.write("Output:\n")
        f.write(f"  kamus-jawa-bersih.json      : {stats['bersih_count']:>7} entries (3-field lengkap)\n")
        f.write(f"    dengan aksara             : {stats['bersih_with_aksara']:>7}\n")
        f.write(f"    dengan keterangan         : {stats['bersih_with_keterangan']:>7}\n")
        f.write(f"  kamus-jawa-draft.json       : {stats['draft_count']:>7} entries (krama kosong)\n")
        f.write(f"    dengan aksara             : {stats['draft_with_aksara']:>7}\n")
        f.write(f"    dengan keterangan         : {stats['draft_with_keterangan']:>7}\n")
        f.write(f"  Skipped (gak punya ngoko/arti): {stats['skipped']:>7}\n\n")
        f.write("Schema bersih (sesuai user spec 9 Okt 2026):\n")
        f.write("  ngoko      = sinonim comma-separated (e.g. 'aku, nyong, inyong')\n")
        f.write("  krama      = sinonim comma-separated (e.g. 'kula, dalem, abdi')\n")
        f.write("  arti       = sinonim Indonesia comma-separated (e.g. 'aku, saya, gue, gua')\n")
        f.write("  keterangan = asli Wiktionary Jawa, dipertahankan\n")
        f.write("  aksara     = aksara Jawa (bonus, opsional)\n")
        f.write("  sumber     = sumber data\n\n")
        f.write("Workflow:\n")
        f.write("  1. Raw (full + lemma) → build-kamus-bersih.py → bersih + draft\n")
        f.write("  2. User isi krama di draft via kamus-tui.py → pindah ke bersih\n")
        f.write("  3. Bersih → upload ke Supabase (DB = ground of truth)\n")
        f.write("  4. Target realistis: 2.000 entries bersih dalam 1 tahun (50/minggu)\n")
    print(f"✓ Save report: {OUT_REPORT}")


if __name__ == "__main__":
    main()
