#!/usr/bin/env python3
"""
build-kamus-bersih.py v2 — Gabung kamus-jawa-full.json + lemma jadi 1 kamus komprehensif

Strategi (sesuai user 9 Okt 2026):
  - Source JSON (full + lemma raw) JANGAN DIHAPUS — tetap utuh
  - 1 kamus bersih komprehensif: gabung sinonim jadi 1 konsep
  - Yang belum lengkap = PR bersama, isi bertahap
  - 0 drop, semua data dipertahankan

Group by konsep (3 strategi):
  1. Group by KRAMA: entries dengan krama sama = 1 konsep (sinonim ngoko digabung comma)
  2. Group by NGOKO: no-krama entries dengan ngoko sama = 1 konsep (sinonim/duplikat)
  3. (TIDAK ada orphan) — semua entries pasti punya ngoko

  ⚠ JANGAN group by keterangan — definisi Jawa bisa generic (mis. "ikan.")
    yang dipakai banyak entries beda konsep.

Merge lemma dengan full:
  - Lemma entries yang match full (by ngoko) → tambah arti Indonesia dari lemma
  - Lemma entries baru (no match) → jadi entries baru di kamus bersih

Conflict resolution:
  - Aksara: gabung comma kalau beda (sinonim aksara)
  - Keterangan: gabung "| " kalau beda (semua dipertahankan)
  - Krama: ambil yang paling panjang (banyak alias)
  - Arti: prefer dari lemma (Indonesia translation yang sudah ada)
  - Register: krama_inggil > krama > ngoko > umum (prioritas highest register)

Schema output:
  {
    "ngoko": "ika, iki, kaé, kiyé, kuwi",     ← sinonim comma
    "krama": "punika",                         ← sinonim comma
    "krama_inggil": "",                        ← (kalau ada)
    "arti": "ini, itu",                        ← Indonesia, dari lemma/isi user
    "keterangan": "panuduh marang... | iki. | iku.",  ← gabungan Jawa asli
    "aksara": "ꦲꦶꦏ",                          ← gabung comma kalau beda
    "register": "ngoko",                       ← dari Wiktionary
    "sumber": "jv.wiktionary.org + id.wiktionary.org",
    "is_lemma": true,                          ← tag: ada di jv:Lema?
    "lemma_words": "iki",                      ← match ke lemma mana?
    "source_count": 7                          ← berapa entries asli yang digabung
  }

Output:
  /home/z/my-project/public/kamus-jawa-draft.json  (kamus draft, banyak kosong, user isi bertahap)
  /home/z/my-project/public/kamus-jawa-draft-report.txt  (statistik)

Usage:
  python3 build-kamus-bersih.py
  python3 build-kamus-bersih.py --dry-run
"""

import json
import re
import argparse
from pathlib import Path
from collections import defaultdict

# ============================================================
# Config
# ============================================================
RAW_FULL = Path("/home/z/my-project/public/kamus-jawa-full.json")
RAW_LEMMA = Path("/home/z/my-project/download/kamus-jawa-lemma-raw.json")
RAW_MENDELEY = Path("/home/z/my-project/public/kamus-jawa-mendeley-raw.json")

OUT_DRAFT = Path("/home/z/my-project/public/kamus-jawa-draft.json")
OUT_REPORT = Path("/home/z/my-project/public/kamus-jawa-draft-report.txt")


# ============================================================
# Helpers
# ============================================================
def normalize_sinonim(value):
    """Split, trim, dedup, lowercase, join comma."""
    if not value:
        return ""
    parts = []
    seen = set()
    for w in value.split(","):
        w = w.strip().lower()
        if not w or "\n" in w or "|" in w or "[" in w or "{" in w:
            continue
        if w in seen:
            continue
        seen.add(w)
        parts.append(w)
    return ", ".join(parts)


def normalize_field_keep(value):
    """Trim + strip newline, preserve original case untuk arti/aksara/keterangan."""
    if not value:
        return ""
    return value.strip()


def merge_sinonim_field(existing, new_value):
    """Merge comma-separated sinonim dengan dedup."""
    existing = existing or ""
    new_value = new_value or ""
    combined = ""
    if existing:
        combined += existing + ", "
    if new_value:
        combined += new_value
    return normalize_sinonim(combined)


def merge_keterangan_field(existing, new_value):
    """Merge keterangan dengan ' | ' separator, dedup."""
    existing = (existing or "").strip()
    new_value = (new_value or "").strip()
    if not existing:
        return new_value
    if not new_value:
        return existing
    # Cek kalau new_value sudah ada di existing (substring)
    if new_value.lower() in existing.lower():
        return existing
    return f"{existing} | {new_value}"


def merge_aksara_field(existing, new_value):
    """Merge aksara comma-separated dengan dedup."""
    return merge_sinonim_field(existing, new_value)


def register_priority(register):
    """Prioritas register: krama_inggil > krama > ngoko > kawi > umum."""
    order = {"krama_inggil": 0, "krama": 1, "ngoko": 2, "kawi": 3, "umum": 4}
    return order.get((register or "umum").strip(), 99)


# ============================================================
# Load
# ============================================================
def load_json(path):
    if not path.exists():
        print(f"⚠ File tidak ditemukan: {path}")
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


# ============================================================
# Build konsep dari full.json
# ============================================================
def build_konsep_full(full_words):
    """Group entries di full.json by konsep.

    Strategy:
      1. Group by KRAMA (lowercase) — entries dengan krama sama = 1 konsep (sinonim ngoko)
      2. Group by NGOKO (lowercase, untuk no-krama) — entries dengan ngoko sama = 1 konsep
         (entries no-krama dengan ngoko sama bisa sinonim atau duplikat)
      3. Semua entries pasti masuk ke salah satu group (no orphan drop)

    ⚠ JANGAN group by keterangan — definisi Jawa bisa generic (mis. "ikan.") yang
      dipakai banyak entries beda konsep. Bikin 44 entries beda ikan jadi 1 konsep = SALAH.

    Returns: list of konsep dicts
    """
    print(f"\n🔍 Group {len(full_words):,} entries dari full.json by konsep...")

    # Build groups
    by_krama = defaultdict(list)
    by_ngoko_no_krama = defaultdict(list)

    for i, e in enumerate(full_words):
        krama = (e.get("krama", "") or "").strip().lower()
        ngoko = (e.get("ngoko", "") or "").strip().lower()

        if krama:
            by_krama[krama].append(e)
        elif ngoko:
            by_ngoko_no_krama[ngoko].append(e)
        # Edge case: no krama + no ngoko → skip (shouldn't happen, but safe)

    print(f"  Group by krama            : {len(by_krama):,} konsep (dari {sum(len(v) for v in by_krama.values()):,} entries)")
    print(f"  Group by ngoko (no-krama) : {len(by_ngoko_no_krama):,} konsep (dari {sum(len(v) for v in by_ngoko_no_krama.values()):,} entries)")

    # Build konsep dari setiap group
    konseps = []
    for krama, entries in by_krama.items():
        konsep = merge_full_entries(entries, group_by="krama")
        konsep["sumber"] = "jv.wiktionary.org (group by krama)"
        konseps.append(konsep)

    for ngoko, entries in by_ngoko_no_krama.items():
        konsep = merge_full_entries(entries, group_by="ngoko")
        konsep["sumber"] = "jv.wiktionary.org (group by ngoko)"
        konseps.append(konsep)

    print(f"  Total konsep dari full: {len(konseps):,}")
    return konseps


def merge_full_entries(entries, group_by="krama"):
    """Merge multiple full entries jadi 1 konsep (sinonim comma).

    group_by:
      - "krama"  : entries dengan krama sama, gabung ngoko sebagai sinonim
      - "ngoko"  : entries dengan ngoko sama (no-krama), gabung keterangan + aksara
    """
    ngoko_parts = []
    krama_parts = []
    ki_parts = []
    aksara_parts = []
    keterangan_merged = ""
    # Register SEMUA = "umum" (jangan parse ngoko/krama dari Wiktionary — halusinasi/kesalahan parsing).
    # User bisa set manual di kamus-tui.py kalau perlu.
    register = "umum"

    for e in entries:
        n = (e.get("ngoko", "") or "").strip()
        k = (e.get("krama", "") or "").strip()
        ki = (e.get("krama_inggil", "") or "").strip()
        a = (e.get("aksara", "") or "").strip()
        ket = (e.get("keterangan", "") or "").strip()

        if n:
            ngoko_parts.append(n)
        if k:
            krama_parts.append(k)
        if ki:
            ki_parts.append(ki)
        if a:
            aksara_parts.append(a)
        if ket:
            keterangan_merged = merge_keterangan_field(keterangan_merged, ket)

    # Dedup sinonim per word (split by comma dulu, supaya "ika, iki" + "ika, iku"
    # → "ika, iki, iku" bukan "ika, iki, ika, iku")
    ngoko_words = []
    for p in ngoko_parts:
        for w in p.split(","):
            w = w.strip().lower()
            if w and w not in ngoko_words:
                ngoko_words.append(w)
    ngoko = ", ".join(ngoko_words)

    krama_words = []
    for p in krama_parts:
        for w in p.split(","):
            w = w.strip().lower()
            if w and w not in krama_words:
                krama_words.append(w)
    krama = ", ".join(krama_words)

    ki_words = []
    for p in ki_parts:
        for w in p.split(","):
            w = w.strip().lower()
            if w and w not in ki_words:
                ki_words.append(w)
    krama_inggil = ", ".join(ki_words)

    aksara_words = []
    for p in aksara_parts:
        for w in p.split(","):
            w = w.strip()
            if w and w not in aksara_words:
                aksara_words.append(w)
    aksara = ", ".join(aksara_words)

    return {
        "ngoko": ngoko,
        "krama": krama,
        "krama_inggil": krama_inggil,
        "arti": "",  # belum ada Indonesia, user isi
        "keterangan": keterangan_merged,
        "aksara": aksara,
        "register": register,
        "source_count": len(entries),
    }


def sort_konseps(konseps):
    """Sort alfabetis by primary ngoko, fallback ke krama kalau ngoko kosong."""

    def sort_key(k):
        n = (k.get("ngoko", "") or "").split(",")[0].strip().lower()
        if n:
            # Strip prefix "-" supaya "-a, -ake, aba, abab" urut natural
            return (0, n.lstrip("-"), n)
        # Fallback: ngoko kosong → sort by krama
        kr = (k.get("krama", "") or "").split(",")[0].strip().lower()
        return (1, kr.lstrip("-"), kr)

    return sorted(konseps, key=sort_key)


# ============================================================
# Merge lemma entries ke konsep existing (kalau match)
# ============================================================
def merge_lemma_to_konseps(konseps, lemma_words):
    """Untuk setiap lemma entry:
      - Cari konsep di full yang punya ngoko sama → tambah arti Indonesia dari lemma
      - Kalau gak match → bikin konsep baru
    """
    print(f"\n🔗 Merge {len(lemma_words):,} lemma entries ke konsep...")

    # Index konsep by primary ngoko (first word lowercase)
    konsep_by_ngoko = defaultdict(list)
    for i, k in enumerate(konseps):
        ngoko_first = (k.get("ngoko", "") or "").split(",")[0].strip().lower()
        if ngoko_first:
            konsep_by_ngoko[ngoko_first].append(i)

    matched = 0
    new_from_lemma = 0
    for lemma in lemma_words:
        lemma_ngoko = (lemma.get("ngoko", "") or "").strip().lower()
        lemma_arti = (lemma.get("arti", "") or "").strip()
        lemma_krama = (lemma.get("krama", "") or "").strip()
        lemma_aksara = (lemma.get("aksara", "") or "").strip()
        lemma_ket = (lemma.get("keterangan", "") or "").strip()

        # Cari konsep yang match (by first ngoko)
        matches = konsep_by_ngoko.get(lemma_ngoko, [])
        if matches:
            konsep_idx = matches[0]
            k = konseps[konsep_idx]

            # Tambah arti dari lemma (Indonesia) — prioritas lemma
            if lemma_arti and not k.get("arti"):
                k["arti"] = lemma_arti

            # Tambah krama dari lemma (kalau konsep belum punya)
            if lemma_krama and not k.get("krama"):
                k["krama"] = normalize_sinonim(lemma_krama)

            # Tambah aksara dari lemma (gabung)
            if lemma_aksara:
                k["aksara"] = merge_aksara_field(k.get("aksara", ""), lemma_aksara)

            # Tambah keterangan dari lemma (gabung)
            if lemma_ket:
                k["keterangan"] = merge_keterangan_field(k.get("keterangan", ""), lemma_ket)

            # Register tetap "umum" (jangan pakai lemma register — halusinasi/kesalahan parsing)
            # Tag is_lemma
            k["is_lemma"] = True
            k["lemma_words"] = lemma_ngoko
            k["source_count"] = k.get("source_count", 1) + 1

            matched += 1
        else:
            # Bikin konsep baru dari lemma
            new_konsep = {
                "ngoko": normalize_sinonim(lemma.get("ngoko", "")),
                "krama": normalize_sinonim(lemma.get("krama", "")),
                "krama_inggil": "",
                "arti": lemma_arti,
                "keterangan": lemma_ket,
                "aksara": lemma_aksara,
                "register": "umum",  # SEMUA umum (jangan parse — halusinasi)
                "sumber": "id.wiktionary.org Kategori:jv:Lema (new)",
                "is_lemma": True,
                "lemma_words": lemma_ngoko,
                "source_count": 1,
            }
            konseps.append(new_konsep)
            new_from_lemma += 1

    print(f"  Match & merge ke konsep existing: {matched:,}")
    print(f"  New konsep dari lemma (no match): {new_from_lemma:,}")
    return konseps


# ============================================================
# Load Mendeley dataset (Faisal Rahutomo et al, 2018)
# Format: {"employees": {"<firebase_id>": {indonesia, kramaalus, kramainggil, ngoko}}}
# Schema mapping (sesuai user spec 9 Okt 2026):
#   indonesia  → arti       (arti Indonesia, curated - BUKAN scrape)
#   ngoko      → ngoko
#   kramaalus + kramainggil → krama  (gabung comma sebagai sinonim)
# ============================================================
def load_mendeley_words(path):
    """Load Mendeley kamus-2cba6-export.json, return list of konsep-like entries.

    Output format sama dengan lemma_raw:
      [{ngoko, krama, arti, keterangan, aksara, register, sumber}, ...]
    """
    if not path.exists():
        print(f"⚠ Mendeley file tidak ditemukan: {path}")
        return []
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    employees = data.get("employees", {})
    if not isinstance(employees, dict):
        return []

    entries = []
    for fid, v in employees.items():
        ngoko = (v.get("ngoko", "") or "").strip()
        kramaalus = (v.get("kramaalus", "") or "").strip()
        kramainggil = (v.get("kramainggil", "") or "").strip()
        indonesia = (v.get("indonesia", "") or "").strip()
        if not ngoko or not indonesia:
            continue  # skip entries tanpa ngoko atau arti
        # Gabung kramaalus + kramainggil sebagai sinonim krama (sesuai user spec)
        krama_parts = []
        for k in (kramaalus, kramainggil):
            for w in (k or "").split(","):
                w = w.strip()
                if w and w.lower() not in [x.lower() for x in krama_parts]:
                    krama_parts.append(w)
        krama = ", ".join(krama_parts)
        entries.append({
            "ngoko": ngoko,
            "krama": krama,
            "arti": indonesia,
            "keterangan": "",  # Mendeley dataset tidak punya keterangan Jawa
            "aksara": "",
            "register": "umum",  # SEMUA umum (jangan parse — halusinasi)
            "sumber": f"data.mendeley.com/datasets/y3hstv4bfn (firebase_id={fid})",
            "_firebase_id": fid,
        })
    return entries


def merge_mendeley_to_konseps(konseps, mendeley_words):
    """Merge Mendeley entries ke konsep existing (kalau match by ngoko).

    Mendeley punya arti Indonesia curated + krama (gabungan kramaalus+kramainggil).
    Strategi:
      - Match by ngoko pertama (lowercase)
      - Match → enrich:
          * arti: kalau kosong, isi dari Mendeley (curated, BUKAN scrape)
          * krama: gabung comma (sinonim baru dari Mendeley)
      - No match → bikin konsep baru
    """
    print(f"\n🔗 Merge {len(mendeley_words):,} Mendeley entries ke konsep...")

    # Index konsep by primary ngoko (first word lowercase)
    konsep_by_ngoko = defaultdict(list)
    for i, k in enumerate(konseps):
        ngoko_first = (k.get("ngoko", "") or "").split(",")[0].strip().lower()
        if ngoko_first:
            konsep_by_ngoko[ngoko_first].append(i)

    matched = 0
    enriched_arti = 0
    enriched_krama = 0
    new_from_mendeley = 0
    for entry in mendeley_words:
        mendeley_ngoko = (entry.get("ngoko", "") or "").strip().lower()
        mendeley_arti = (entry.get("arti", "") or "").strip()
        mendeley_krama = (entry.get("krama", "") or "").strip()
        mendeley_ket = (entry.get("keterangan", "") or "").strip()

        matches = konsep_by_ngoko.get(mendeley_ngoko, [])
        if matches:
            konsep_idx = matches[0]
            k = konseps[konsep_idx]

            # Enrich arti: prioritas Mendeley (curated Indonesia) > existing kosong
            if mendeley_arti and not k.get("arti"):
                k["arti"] = mendeley_arti
                enriched_arti += 1
            elif mendeley_arti and k.get("arti") and mendeley_arti.lower() not in k["arti"].lower():
                # Kalau existing ada arti beda → gabung sebagai sinonim arti
                k["arti"] = f"{k['arti']}; {mendeley_arti}"

            # Enrich krama: gabung comma (sinonim baru)
            if mendeley_krama:
                existing_krama = k.get("krama", "") or ""
                # Dedup word-level
                new_words = [w.strip().lower() for w in mendeley_krama.split(",") if w.strip()]
                old_words = [w.strip().lower() for w in existing_krama.split(",") if w.strip()]
                combined = []
                for w in old_words + new_words:
                    if w not in combined:
                        combined.append(w)
                new_krama = ", ".join(combined)
                if new_krama != existing_krama:
                    k["krama"] = new_krama
                    enriched_krama += 1

            # Tag is_mendeley + bump source_count
            k["is_mendeley"] = True
            k["mendeley_id"] = entry.get("_firebase_id", "")
            k["source_count"] = k.get("source_count", 1) + 1
            # Update sumber
            sumber = k.get("sumber", "")
            if "mendeley" not in sumber.lower():
                k["sumber"] = (sumber + " + mendeley" if sumber else "mendeley").strip(" +")

            matched += 1
        else:
            # Bikin konsep baru dari Mendeley
            new_konsep = {
                "ngoko": normalize_sinonim(entry.get("ngoko", "")),
                "krama": normalize_sinonim(entry.get("krama", "")),
                "krama_inggil": "",
                "arti": mendeley_arti,
                "keterangan": mendeley_ket,
                "aksara": "",
                "register": "umum",
                "sumber": "data.mendeley.com/datasets/y3hstv4bfn (new)",
                "is_mendeley": True,
                "mendeley_id": entry.get("_firebase_id", ""),
                "source_count": 1,
            }
            konseps.append(new_konsep)
            new_from_mendeley += 1

    print(f"  Match & enrich konsep existing: {matched:,}")
    print(f"    + enrich arti (yang kosong): {enriched_arti:,}")
    print(f"    + enrich krama (tambah sinonim): {enriched_krama:,}")
    print(f"  New konsep dari Mendeley (no match): {new_from_mendeley:,}")
    return konseps


# ============================================================
# Post-processing arti (fix parsing artifacts)
# ============================================================
def clean_arti(arti_raw, ngoko, krama):
    """Clean arti Indonesia dari artifact parser Wiktionary.

    Returns: (clean_arti, moved_to_keterangan, status)
      - clean_arti: sinonim pendek yang valid, atau '' kalau gak valid
      - moved_to_keterangan: text yang dipindah ke keterangan (kalau arti panjang)
      - status: 'clean' | 'self_ref' | 'long_def' | 'empty'
    """
    if not arti_raw or not arti_raw.strip():
        return "", "", "empty"

    arti = arti_raw.strip()

    # 1. Strip <br> dan newline → ; (multiple definitions)
    arti = re.sub(r"<br\s*/?>", ";", arti, flags=re.IGNORECASE)
    arti = arti.replace("\n", ";").replace("\r", ";")

    # 2. Strip "():", "(): " patterns (artifact template Wiktionary)
    # Mis. "() besar" → "besar", "(mampu)" → drop, "bisa (mampu)" → "bisa"
    # Hapus "()" dan "()" saja (artinya kosong, artifact)
    arti = re.sub(r"\(\s*\)", "", arti)
    # Untuk "word (keterangan)" — pertahankan word, drop paren jika word ada
    # Mis. "bisa (mampu)" → "bisa" (karena "bisa" = ngoko, parentheses = context)
    # Tapi "berat (tentang pikiran)" → "berat" (drop context)

    # 3. Cek LONG_DEF (>60 char): arti ensiklopedis, pindah ke keterangan
    if len(arti) > 60:
        return "", arti, "long_def"

    # 4. Strip parenthetical (sekarang setelah long_def check, sisanya pendek dengan paren)
    # Mis. "bisa (mampu)" → "bisa", "berat (tentang pikiran, perasaan)" → "berat"
    arti_no_paren = re.sub(r"\s*\([^)]*\)", "", arti).strip(" ,;:.")
    if arti_no_paren:
        arti = arti_no_paren

    # 5. Strip colon artifact: "dadi; jadi:" → "jadi"
    # Pattern: text:other_text → ambil last segment (yang valid Indonesia)
    if ":" in arti:
        parts = [p.strip(" ,;.") for p in arti.split(":") if p.strip(" ,;.")]
        if parts:
            arti = parts[-1]

    # 6. Split by ; atau , → dedup (case-insensitive)
    parts = [p.strip(" ,;.").lower() for p in re.split(r"[;,\n]", arti) if p.strip(" ,;.\n")]
    seen = []
    for p in parts:
        if p and p not in seen:
            seen.append(p)
    arti = "; ".join(seen) if seen else ""

    # 7. SELF_REF: kalau arti = ngoko atau krama (loopback), kosongkan
    ngoko_first = ngoko.split(",")[0].strip().lower()
    krama_first = krama.split(",")[0].strip().lower() if krama else ""
    if arti:
        arti_words = [w.strip() for w in arti.split(";")]
        # Kalau semua arti_words == ngoko atau krama → self_ref
        if all(w == ngoko_first or w == krama_first for w in arti_words):
            return "", arti_raw, "self_ref"
        # Kalau ada arti_word yang self_ref → drop yang self_ref, sisanya tetap
        non_self = [w for w in arti_words if w != ngoko_first and w != krama_first]
        if non_self and len(non_self) < len(arti_words):
            arti = "; ".join(non_self)

    # 8. Capitalization: lowercase kecuali proper noun
    # Proper noun: kata pertama capitalize dan tidak ada di dict common words
    # Untuk simplisitas: lowercase semua (user bisa fix di kamus-tui.py kalau proper noun)
    # Tapi pertahankan "Belanda", "Indonesia" dll yang jelas proper noun
    proper_nouns = {"belanda", "indonesia", "jawa", "sunda", "bali", "ramadan"}
    if arti and arti.split()[0].lower() not in proper_nouns and len(arti.split()) <= 2:
        # Jangan lowercase kalau single word capitalized (kemungkinan proper noun)
        if arti[0].isupper() and arti[1:].islower() and " " not in arti:
            pass  # biarkan proper noun
        else:
            arti = arti[0].lower() + arti[1:] if arti else arti

    if not arti:
        return "", arti_raw, "empty"

    return arti, "", "clean"


def post_process_konseps(konseps):
    """Apply clean_arti ke semua konsep + pindah long_def ke keterangan."""
    print(f"\n🧹 Post-process arti ({len(konseps):,} konsep)...")
    stats = {
        "clean": 0,
        "self_ref_cleared": 0,
        "long_def_moved": 0,
        "empty": 0,
        "paren_stripped": 0,
        "colon_stripped": 0,
        "dup_deduped": 0,
    }

    for k in konseps:
        arti_raw = k.get("arti", "")
        ngoko = k.get("ngoko", "")
        krama = k.get("krama", "")
        if not arti_raw:
            stats["empty"] += 1
            continue

        original_arti = arti_raw
        clean, moved, status = clean_arti(arti_raw, ngoko, krama)

        if status == "long_def":
            # Pindah arti panjang ke keterangan (gabung dengan existing keterangan)
            existing_ket = k.get("keterangan", "")
            if moved and moved not in existing_ket:
                k["keterangan"] = f"{existing_ket} | {moved}".strip(" |") if existing_ket else moved
            k["arti"] = ""  # kosongkan, user isi manual nanti
            stats["long_def_moved"] += 1
        elif status == "self_ref":
            # Self-ref = arti cuma ulang ngoko/krama, BUKAN Indonesia
            # Kosongkan, user isi manual
            k["arti"] = ""
            stats["self_ref_cleared"] += 1
        elif status == "empty":
            k["arti"] = ""
            stats["empty"] += 1
        else:
            # Clean atau setelah fix
            k["arti"] = clean
            stats["clean"] += 1
            # Count berapa perubahan yang dilakukan
            if "(" in original_arti or ")" in original_arti:
                stats["paren_stripped"] += 1
            if ":" in original_arti:
                stats["colon_stripped"] += 1
            # Cek dup
            parts = [p.strip().lower() for p in re.split(r"[;,]", original_arti) if p.strip()]
            if len(parts) > len(set(parts)):
                stats["dup_deduped"] += 1

    print(f"  Clean (siap upload betulan): {stats['clean']}")
    print(f"  Self-ref cleared (arti = ngoko/krama, kosongkan): {stats['self_ref_cleared']}")
    print(f"  Long-def moved ke keterangan: {stats['long_def_moved']}")
    print(f"  Empty (no arti from source): {stats['empty']}")
    print(f"  Paren stripped: {stats['paren_stripped']}")
    print(f"  Colon stripped: {stats['colon_stripped']}")
    print(f"  Dup deduped: {stats['dup_deduped']}")
    return konseps
# ============================================================
def compute_stats(konseps):
    stats = {
        "total_konsep": len(konseps),
        "with_krama": sum(1 for k in konseps if (k.get("krama") or "").strip()),
        "with_arti": sum(1 for k in konseps if (k.get("arti") or "").strip()),
        "with_keterangan": sum(1 for k in konseps if (k.get("keterangan") or "").strip()),
        "with_aksara": sum(1 for k in konseps if (k.get("aksara") or "").strip()),
        "is_lemma": sum(1 for k in konseps if k.get("is_lemma")),
        "ready_3_field": sum(
            1 for k in konseps
            if (k.get("ngoko") or "").strip()
            and (k.get("krama") or "").strip()
            and (k.get("arti") or "").strip()
        ),
        "draft_2_field": sum(
            1 for k in konseps
            if (k.get("ngoko") or "").strip()
            and (k.get("arti") or "").strip()
            and not (k.get("krama") or "").strip()
        ),
    }
    return stats


def print_samples(konseps, n=5):
    """Print sample konsep untuk verifikasi."""
    print(f"\n📋 Sample {n} konsep pertama (urut alfabetis):")
    for k in konseps[:n]:
        print(f"  ngoko: {k.get('ngoko', '')!r}")
        print(f"    krama: {k.get('krama', '')!r}")
        print(f"    arti: {k.get('arti', '')[:60]!r}")
        print(f"    aksara: {k.get('aksara', '')!r}")
        print(f"    register: {k.get('register', '')} | source_count: {k.get('source_count', 1)}")
        print()

    # Print top 5 konsep dengan sinonim terbanyak
    print(f"📋 Top 5 konsep dengan sinonim terbanyak:")
    sorted_by_count = sorted(konseps, key=lambda x: -x.get("source_count", 1))
    for k in sorted_by_count[:5]:
        print(f"  ngoko: {k.get('ngoko', '')!r}")
        print(f"    krama: {k.get('krama', '')!r}")
        print(f"    source_count: {k.get('source_count', 1)} (entries asli yang digabung)")


# ============================================================
# Main
# ============================================================
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    print("📦 Loading source JSON...")
    full = load_json(RAW_FULL)
    lemma_raw = load_json(RAW_LEMMA)
    if not full or not lemma_raw:
        return

    full_words = full["words"] if isinstance(full, dict) and "words" in full else full
    lemma_words = lemma_raw if isinstance(lemma_raw, list) else lemma_raw.get("words", [])
    print(f"  full.json: {len(full_words):,} entries (jv.wiktionary.org)")
    print(f"  lemma-raw: {len(lemma_words):,} entries (id.wiktionary.org jv:Lema)")

    # Build konsep dari full
    konseps = build_konsep_full(full_words)

    # Merge lemma
    konseps = merge_lemma_to_konseps(konseps, lemma_words)

    # Merge Mendeley dataset (curated Indonesia + krama gabungan kramaalus+kramainggil)
    mendeley_words = load_mendeley_words(RAW_MENDELEY)
    print(f"  mendeley.json: {len(mendeley_words):,} entries (data.mendeley.com/datasets/y3hstv4bfn)")
    if mendeley_words:
        konseps = merge_mendeley_to_konseps(konseps, mendeley_words)

    # Post-process arti (clean artifact, move long_def ke keterangan)
    konseps = post_process_konseps(konseps)

    # Sort alfabetis
    print(f"\n🔤 Sort {len(konseps):,} konsep alfabetis by ngoko pertama...")
    konseps = sort_konseps(konseps)

    # Assign entry_id (1-indexed, urut alfabetis)
    print(f"🔢 Assign entry_id 1..{len(konseps):,}...")
    for i, k in enumerate(konseps, 1):
        k["entry_id"] = i

    # Compute stats
    stats = compute_stats(konseps)
    print(f"\n📊 Hasil:")
    for k, v in stats.items():
        print(f"  {k:20s}: {v:,}")
    print_samples(konseps)

    if args.dry_run:
        print("\n⚠ Dry run, tidak save file")
        return

    # Save
    output = {
        "metadata": {
            "version": "2.0",
            "description": "Kamus Jawa komprehensif — group by konsep, gabung sinonim",
            "sources": [
                f"jv.wiktionary.org ({len(full_words):,} entries, raw preserved)",
                f"id.wiktionary.org Kategori:jv:Lema ({len(lemma_words):,} entries, raw preserved)",
            ],
            "total_konsep": stats["total_konsep"],
            "schema": {
                "ngoko": "sinonim ngoko comma-separated",
                "krama": "sinonim krama comma-separated",
                "krama_inggil": "krama inggil (opsional)",
                "arti": "terjemahan Indonesia comma-separated",
                "keterangan": "definisi Jawa asli dari Wiktionary (gabungan, dipertahankan)",
                "aksara": "aksara Jawa (gabung comma kalau beda)",
                "register": "ngoko|krama|krama_inggil|kawi|umum",
                "sumber": "sumber data konsep ini",
                "is_lemma": "true kalau ada di jv:Lema (prioritas kerja)",
                "lemma_words": "word di lemma yang match konsep ini",
                "source_count": "jumlah entries asli yang digabung jadi 1 konsep",
            },
            "stats": stats,
            "workflow": [
                "1. Raw (full + lemma) dipertahankan utuh — JANGAN DIHAPUS",
                "2. Kamus bersih = group by konsep + gabung sinonim",
                "3. Yang belum lengkap (arti/krama) = PR bersama, isi bertahap",
                "4. Target: 2.000 entries dengan 3-field lengkap dalam 1 tahun (50/minggu)",
                "5. Upload yang lengkap ke Supabase (DB = ground of truth)",
            ],
        },
        "words": konseps,
    }
    with open(OUT_DRAFT, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    print(f"\n✓ Save: {OUT_DRAFT} ({len(konseps):,} konsep)")

    # Report
    with open(OUT_REPORT, "w", encoding="utf-8") as f:
        f.write("Build Kamus DRAFT Report\n")
        f.write("=" * 60 + "\n\n")
        f.write("Source (JANGAN DIHAPUS, tetap utuh):\n")
        f.write(f"  kamus-jawa-full.json        : {len(full_words):>7,} entries (jv.wiktionary.org)\n")
        f.write(f"  kamus-jawa-lemma-raw.json   : {len(lemma_words):>7,} entries (id.wiktionary.org jv:Lema)\n\n")
        f.write("Output:\n")
        f.write(f"  kamus-jawa-draft.json       : {stats['total_konsep']:>7,} konsep (group by konsep + sinonim)\n\n")
        f.write("Stats:\n")
        for k, v in stats.items():
            f.write(f"  {k:25s}: {v:>7,}\n")
        f.write("\nRegister: SEMUA 'umum' (jangan parse ngoko/krama dari Wiktionary — halusinasi/kesalahan parsing).\n")
        f.write("  User bisa set manual di kamus-tui.py kalau perlu.\n\n")
        f.write("Workflow:\n")
        f.write("  1. Raw preserved (full + lemma) — JANGAN DIHAPUS\n")
        f.write("  2. Kamus draft = 1 file komprehensif, group by konsep, register umum\n")
        f.write("  3. Sinonim digabung comma (ngoko, krama, arti)\n")
        f.write("  4. Keterangan Jawa asli dipertahankan (gabung '|')\n")
        f.write("  5. Aksara Jawa digabung comma kalau beda\n")
        f.write("  6. Yang belum lengkap = PR bersama, isi bertahap\n")
        f.write("  7. Target: 2.000 entries 3-field lengkap dalam 1 tahun (50/minggu)\n")
        f.write("  8. Upload yang lengkap ke Supabase (DB = ground of truth)\n")
    print(f"✓ Save: {OUT_REPORT}")


if __name__ == "__main__":
    main()
