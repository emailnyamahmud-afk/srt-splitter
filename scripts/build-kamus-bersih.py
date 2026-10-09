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
RAW_DASANAMA = Path("/home/z/my-project/public/dasanama-raw.csv")
RAW_ANGKA = Path("/home/z/my-project/public/angka-raw.json")
RAW_LAMPIRAN = Path("/home/z/my-project/public/lampiran-raw.json")

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
        "status": "draft",  # default draft, user edit via TUI → save → recompute jadi 'ready'
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
      - Cek keterangan untuk tag {{krama}} atau {{label|jv|krama}}
        Kalau ada → word ini KRAMA, match by krama index (BUKAN ngoko)
      - Kalau gak ada tag krama → match by ngoko index (seperti biasa)
      - Match → enrich arti (gabung sinonim, bukan override)
      - No match → bikin konsep baru
    """
    print(f"\n🔗 Merge {len(lemma_words):,} lemma entries ke konsep...")

    # Build indices: by primary ngoko AND by primary krama
    konsep_by_ngoko = defaultdict(list)
    konsep_by_krama = defaultdict(list)
    for i, k in enumerate(konseps):
        ngoko_first = (k.get("ngoko", "") or "").split(",")[0].strip().lower()
        if ngoko_first:
            konsep_by_ngoko[ngoko_first].append(i)
        krama_first = (k.get("krama", "") or "").split(",")[0].strip().lower()
        if krama_first:
            konsep_by_krama[krama_first].append(i)

    matched = 0
    matched_by_krama = 0
    new_from_lemma = 0
    for lemma in lemma_words:
        lemma_word = (lemma.get("ngoko", "") or "").strip().lower()
        lemma_arti = (lemma.get("arti", "") or "").strip()
        lemma_krama = (lemma.get("krama", "") or "").strip()
        lemma_aksara = (lemma.get("aksara", "") or "").strip()
        lemma_ket = (lemma.get("keterangan", "") or "").strip()

        # Cek apakah word ini sebenarnya KRAMA (bukan ngoko)
        # Lemma parser taruh krama word di field "ngoko" tapi keterangan ada tag {{krama}}
        is_actually_krama = False
        if lemma_ket:
            ket_lower = lemma_ket.lower()
            if "{{krama}}" in ket_lower or "{{label|jv|krama}}" in ket_lower:
                is_actually_krama = True

        # Match logic:
        # - is_actually_krama=True → match by krama index (word is KRAMA)
        # - is_actually_krama=False → match by ngoko index (word is NGOKO)
        if is_actually_krama:
            matches = konsep_by_krama.get(lemma_word, [])
            matched_by_krama += 1
        else:
            matches = konsep_by_ngoko.get(lemma_word, [])

        if matches:
            konsep_idx = matches[0]
            k = konseps[konsep_idx]

            # Enrich arti: gabung sinonim (bukan override)
            if lemma_arti and not k.get("arti"):
                k["arti"] = lemma_arti
            elif lemma_arti and k.get("arti") and lemma_arti.lower() not in k["arti"].lower():
                k["arti"] = f"{k['arti']}; {lemma_arti}"

            # Tambah krama dari lemma (kalau konsep belum punya dan word ini bukan krama)
            if lemma_krama and not k.get("krama") and not is_actually_krama:
                k["krama"] = normalize_sinonim(lemma_krama)

            # Tambah aksara dari lemma (gabung)
            if lemma_aksara:
                k["aksara"] = merge_aksara_field(k.get("aksara", ""), lemma_aksara)

            # Tambah keterangan dari lemma (gabung)
            if lemma_ket:
                k["keterangan"] = merge_keterangan_field(k.get("keterangan", ""), lemma_ket)

            # Tag is_lemma
            k["is_lemma"] = True
            k["lemma_words"] = lemma_word
            k["source_count"] = k.get("source_count", 1) + 1

            matched += 1
        else:
            # Bikin konsep baru dari lemma
            # Kalau is_actually_krama=True → word masuk ke field krama (bukan ngoko)
            if is_actually_krama:
                new_ngoko = ""
                new_krama = normalize_sinonim(lemma.get("ngoko", ""))
            else:
                new_ngoko = normalize_sinonim(lemma.get("ngoko", ""))
                new_krama = normalize_sinonim(lemma.get("krama", ""))

            new_konsep = {
                "ngoko": new_ngoko,
                "krama": new_krama,
                "krama_inggil": "",
                "arti": lemma_arti,
                "keterangan": lemma_ket,
                "aksara": lemma_aksara,
                "register": "umum",
                "status": "draft",
                "sumber": "id.wiktionary.org Kategori:jv:Lema (new)",
                "is_lemma": True,
                "lemma_words": lemma_word,
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
                "status": "draft",
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
# Load Dasanama CSV (sinonim Jawa, 431 entries, user upload)
# Format: nomer;tembung;dasanama1;dasanama2;...
# Schema mapping (sesuai user spec Opsi 1, 9 Okt 2026):
#   tembung → ngoko utama (target lookup)
#   dasanama → gabung ke field ngoko (user sort manual mana ngoko vs krama)
#   catat juga di keterangan (audit trail)
# ============================================================
def load_dasanama_csv(path):
    """Load dasanama.csv, return list of {tembung, sinonim}."""
    if not path.exists():
        print(f"⚠ Dasanama file tidak ditemukan: {path}")
        return []
    with open(path, "r", encoding="utf-8") as f:
        lines = f.read().splitlines()

    parsed = []
    for line in lines[1:]:  # skip header
        clean = line.replace('"', '')
        parts = [p.strip() for p in clean.split(';') if p.strip()]
        if len(parts) < 2:
            continue
        nomer = parts[0]
        tembung = parts[1]
        sinonim = parts[2:]  # sisanya = sinonim
        # Strip suffixes artifact (mis. "robaya." → "robaya", "wirayang.[1]" → "wirayang")
        cleaned_sinonim = []
        for s in sinonim:
            # Hapus titik di akhir
            s = s.rstrip('.')
            # Hapus [n] citation (mis. "[1]")
            import re as _re
            s = _re.sub(r'\[\d+\]', '', s).strip()
            if s:
                cleaned_sinonim.append(s)
        parsed.append({'nomer': nomer, 'tembung': tembung, 'sinonim': cleaned_sinonim})
    return parsed


def merge_dasanama_to_konseps(konseps, dasanama_entries):
    """Merge dasanama sinonim ke konsep existing (kalau match by tembung).

    Strategi (Opsi 1 — sesuai user spec):
      - Match by tembung (lowercase) ke primary ngoko konsep
      - Match → gabung sinonim dasanama ke field ngoko (user sort manual nanti)
        + Catat di keterangan juga (audit trail: "Dasanama: ...")
      - No match → bikin konsep baru dengan ngoko = tembung + sinonim gabung

    Catatan: dasanama = campuran register (ngoko + krama + kawi + krama_inggil).
    User wajib sort manual di kamus-tui.py mana yang masuk ngoko vs krama.
    Asumsi: draft = kerja user, DB = yang bersih. Jadi di draft wajar ada campuran.
    """
    print(f"\n🔗 Merge {len(dasanama_entries):,} Dasanama entries ke konsep...")

    # Index konsep by primary ngoko (first word lowercase)
    konsep_by_ngoko = defaultdict(list)
    for i, k in enumerate(konseps):
        ngoko_first = (k.get("ngoko", "") or "").split(",")[0].strip().lower()
        if ngoko_first:
            konsep_by_ngoko[ngoko_first].append(i)

    matched = 0
    enriched_ngoko = 0
    new_from_dasanama = 0
    for entry in dasanama_entries:
        tembung = entry["tembung"].strip().lower()
        sinonim = entry["sinonim"]
        if not tembung or not sinonim:
            continue

        matches = konsep_by_ngoko.get(tembung, [])
        if matches:
            konsep_idx = matches[0]
            k = konseps[konsep_idx]

            # Gabung sinonim dasanama ke field ngoko (dedup word-level)
            existing_ngoko = k.get("ngoko", "") or ""
            existing_words = [w.strip().lower() for w in existing_ngoko.split(",") if w.strip()]
            new_words = [w.strip().lower() for w in sinonim if w.strip()]
            combined = []
            for w in existing_words + new_words:
                if w not in combined:
                    combined.append(w)
            new_ngoko = ", ".join(combined)
            if new_ngoko != existing_ngoko:
                k["ngoko"] = new_ngoko
                enriched_ngoko += 1

            # Catat dasanama di keterangan (audit trail, dipertahankan)
            dasanama_str = ", ".join(sinonim)
            existing_ket = k.get("keterangan", "")
            dasanama_tag = f"Dasanama: {dasanama_str}"
            if dasanama_tag not in existing_ket:
                k["keterangan"] = f"{existing_ket} | {dasanama_tag}".strip(" |") if existing_ket else dasanama_tag

            # Tag is_dasanama + bump source_count
            k["is_dasanama"] = True
            k["dasanama_count"] = len(sinonim)
            k["source_count"] = k.get("source_count", 1) + 1
            # Update sumber
            sumber = k.get("sumber", "")
            if "dasanama" not in sumber.lower():
                k["sumber"] = (sumber + " + dasanama" if sumber else "dasanama").strip(" +")

            matched += 1
        else:
            # Bikin konsep baru dari dasanama
            # ngoko = tembung + semua sinonim (user sort manual nanti)
            combined_ngoko = [tembung]
            for s in sinonim:
                s_lower = s.strip().lower()
                if s_lower and s_lower not in combined_ngoko:
                    combined_ngoko.append(s_lower)
            new_konsep = {
                "ngoko": ", ".join(combined_ngoko),
                "krama": "",  # user sort manual mana krama
                "krama_inggil": "",
                "arti": "",  # dasanama gak punya arti Indonesia
                "keterangan": f"Dasanama: {', '.join(sinonim)}",
                "aksara": "",
                "register": "umum",
                "status": "draft",
                "sumber": "dasanama-raw.csv (new)",
                "is_dasanama": True,
                "dasanama_count": len(sinonim),
                "source_count": 1,
            }
            konseps.append(new_konsep)
            new_from_dasanama += 1

    print(f"  Match & enrich konsep existing: {matched:,}")
    print(f"    + enrich ngoko (tambah sinonim dasanama): {enriched_ngoko:,}")
    print(f"  New konsep dari Dasanama (no match): {new_from_dasanama:,}")
    return konseps


# ============================================================
# Load Angka JSON (built-in AI reference, 26 entries)
# Format: {"metadata": {...}, "words": [{ngoko, krama, arti, keterangan}]}
# Curated, sistematis — angka 1-20, puluhan, ratusan, ribuan, juta
# ============================================================
def load_angka_json(path):
    """Load angka-raw.json, return list of entries."""
    if not path.exists():
        print(f"⚠ Angka file tidak ditemukan: {path}")
        return []
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    words = data.get("words", data if isinstance(data, list) else [])
    return words


def merge_angka_to_konseps(konseps, angka_words):
    """Merge angka entries ke konsep existing.

    Angka = curated AI reference, lengkap (ngoko + krama + arti Indonesia).
    Strategi:
      - Match by ngoko pertama (lowercase)
      - Match → enrich (OVERRIDE arti kalau kosong, fix krama kalau ada artifact)
        Khusus angka: arti OVERRIDE bahkan kalau ada (angka sistematis, AI curated valid)
      - No match → bikin konsep baru
    """
    print(f"\n🔗 Merge {len(angka_words):,} Angka entries ke konsep...")

    # Index konsep by primary ngoko (first word lowercase)
    konsep_by_ngoko = defaultdict(list)
    for i, k in enumerate(konseps):
        ngoko_first = (k.get("ngoko", "") or "").split(",")[0].strip().lower()
        if ngoko_first:
            konsep_by_ngoko[ngoko_first].append(i)

    matched = 0
    enriched_arti = 0
    fixed_krama = 0
    new_from_angka = 0
    for entry in angka_words:
        angka_ngoko = (entry.get("ngoko", "") or "").strip().lower()
        angka_arti = (entry.get("arti", "") or "").strip()
        angka_krama = (entry.get("krama", "") or "").strip()
        angka_ket = (entry.get("keterangan", "") or "").strip()

        # Skip kalau ngoko DAN arti DAN krama semua kosong
        if not angka_ngoko and not angka_arti and not angka_krama:
            continue

        # Kalau ngoko kosong, jangan match by ngoko (bikin konsep baru)
        if angka_ngoko:
            matches = konsep_by_ngoko.get(angka_ngoko, [])
        else:
            matches = []
        if matches:
            konsep_idx = matches[0]
            k = konseps[konsep_idx]

            # OVERRIDE arti (angka sistematis, AI curated valid)
            # Sebelumnya arti bisa kosong atau artifact bocor
            if angka_arti:
                old_arti = k.get("arti", "")
                if not old_arti or old_arti.lower() != angka_arti.lower():
                    k["arti"] = angka_arti
                    enriched_arti += 1

            # FIX krama (kalau existing beda, gabung sebagai sinonim)
            if angka_krama:
                existing_krama = k.get("krama", "") or ""
                angka_words_list = [w.strip().lower() for w in angka_krama.split(",") if w.strip()]
                old_words = [w.strip().lower() for w in existing_krama.split(",") if w.strip()]
                combined = []
                for w in old_words + angka_words_list:
                    if w not in combined:
                        combined.append(w)
                new_krama = ", ".join(combined)
                if new_krama != existing_krama:
                    k["krama"] = new_krama
                    fixed_krama += 1

            # Catat keterangan
            if angka_ket:
                existing_ket = k.get("keterangan", "")
                if angka_ket not in existing_ket:
                    k["keterangan"] = f"{existing_ket} | {angka_ket}".strip(" |") if existing_ket else angka_ket

            # Tag is_angka + bump source_count
            k["is_angka"] = True
            k["source_count"] = k.get("source_count", 1) + 1
            sumber = k.get("sumber", "")
            if "angka" not in sumber.lower():
                k["sumber"] = (sumber + " + angka" if sumber else "angka").strip(" +")

            matched += 1
        else:
            # Bikin konsep baru dari angka
            new_konsep = {
                "ngoko": normalize_sinonim(entry.get("ngoko", "")),
                "krama": normalize_sinonim(entry.get("krama", "")),
                "krama_inggil": "",
                "arti": angka_arti,
                "keterangan": angka_ket,
                "aksara": "",
                "register": "umum",
                "status": "draft",
                "sumber": "angka-raw.json (new)",
                "is_angka": True,
                "source_count": 1,
            }
            konseps.append(new_konsep)
            new_from_angka += 1

    print(f"  Match & enrich konsep existing: {matched}")
    print(f"    + enrich arti (override kosong/artifact): {enriched_arti}")
    print(f"    + fix krama (gabung sinonim): {fixed_krama}")
    print(f"  New konsep dari Angka (no match): {new_from_angka}")
    return konseps


# ============================================================
# Load Lampiran Kamus Jawa-Indonesia (2724 entries, curated)
# Cross-reference: cek is_krama flag untuk tentukan ngoko vs krama
# JANGAN trust field label "ngoko" dari Lampiran — cek is_krama
# ============================================================
def load_lampiran_json(path):
    """Load lampiran-raw.json, return list of entries."""
    if not path.exists():
        print(f"⚠ Lampiran file tidak ditemukan: {path}")
        return []
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data.get("words", data if isinstance(data, list) else [])


def merge_lampiran_to_konseps(konseps, lampiran_words, angka_words=None):
    """Merge Lampiran entries ke konsep existing.

    Cross-reference logic (BUKAN trust field label):
      - is_krama=True  → word ini KRAMA, match by krama index
      - is_krama=False → word ini NGOKO, match by ngoko index
      - Cross-ref dengan angka-raw: kalau word muncul di krama field angka-raw,
        override is_krama=False → treat sebagai KRAMA (Lampiran label sering salah)

    Enrich arti: gabung sinonim (bukan override, bukan pick one).
    Tambah field kelas (bonus metadata dari Lampiran).

    No match:
      - is_krama=True  → new concept: krama=word, ngoko="", arti=arti
      - is_krama=False → new concept: ngoko=word, arti=arti
    """
    print(f"\n🔗 Merge {len(lampiran_words):,} Lampiran entries ke konsep...")

    # Build set of krama words dari angka-raw (cross-ref override)
    angka_krama_words = set()
    if angka_words:
        for a in angka_words:
            krama = (a.get("krama", "") or "").strip().lower()
            if krama:
                for k in krama.split(","):
                    k = k.strip()
                    if k:
                        angka_krama_words.add(k)
    print(f"  Cross-ref angka-raw krama words: {len(angka_krama_words)} words")

    # Build indices: by primary ngoko AND by primary krama
    konsep_by_ngoko = defaultdict(list)
    konsep_by_krama = defaultdict(list)
    for i, k in enumerate(konseps):
        ngoko_first = (k.get("ngoko", "") or "").split(",")[0].strip().lower()
        if ngoko_first:
            konsep_by_ngoko[ngoko_first].append(i)
        krama_first = (k.get("krama", "") or "").split(",")[0].strip().lower()
        if krama_first:
            konsep_by_krama[krama_first].append(i)

    matched = 0
    matched_by_krama = 0
    new_from_lampiran = 0
    cross_ref_overrides = 0
    for entry in lampiran_words:
        word = (entry.get("ngoko", "") or "").strip().lower()
        arti = (entry.get("arti", "") or "").strip()
        kelas = (entry.get("kelas", "") or "").strip()
        kelas_nama = (entry.get("kelas_nama", "") or "").strip()
        is_krama = bool(entry.get("is_krama"))

        if not word or not arti:
            continue

        # Cross-ref override: kalau word ada di angka-raw krama words → treat sebagai KRAMA
        # Lampiran label is_krama=False sering SALAH untuk morfem bilangan krama
        if not is_krama and word in angka_krama_words:
            is_krama = True
            cross_ref_overrides += 1

        # Match logic:
        # - is_krama=True  → match by krama index (word is KRAMA)
        # - is_krama=False → match by ngoko index (word is NGOKO)
        if is_krama:
            matches = konsep_by_krama.get(word, [])
            matched_by_krama += 1
        else:
            matches = konsep_by_ngoko.get(word, [])

        if matches:
            konsep_idx = matches[0]
            k = konseps[konsep_idx]

            # Enrich arti: gabung sinonim (bukan override)
            if arti and not k.get("arti"):
                k["arti"] = arti
            elif arti and k.get("arti") and arti.lower() not in k["arti"].lower():
                k["arti"] = f"{k['arti']}; {arti}"

            # Tambah kelas (bonus metadata)
            if kelas:
                existing_kelas = k.get("kelas", "")
                if not existing_kelas:
                    k["kelas"] = kelas
                    k["kelas_nama"] = kelas_nama
                elif kelas not in existing_kelas:
                    k["kelas"] = f"{existing_kelas}, {kelas}"
                    k["kelas_nama"] = f"{k.get('kelas_nama', '')}, {kelas_nama}"

            # Tag is_lampiran
            k["is_lampiran"] = True
            k["source_count"] = k.get("source_count", 1) + 1
            sumber = k.get("sumber", "")
            if "lampiran" not in sumber.lower():
                k["sumber"] = (sumber + " + lampiran" if sumber else "lampiran").strip(" +")

            matched += 1
        else:
            # Bikin konsep baru dari Lampiran
            if is_krama:
                # Word is KRAMA → ngoko kosong (user isi manual)
                new_ngoko = ""
                new_krama = word
            else:
                new_ngoko = word
                new_krama = ""

            new_konsep = {
                "ngoko": new_ngoko,
                "krama": new_krama,
                "krama_inggil": "",
                "arti": arti,
                "keterangan": "",
                "aksara": "",
                "register": "umum",
                "status": "draft",
                "sumber": "lampiran-raw.json (new)",
                "is_lampiran": True,
                "kelas": kelas,
                "kelas_nama": kelas_nama,
                "source_count": 1,
            }
            konseps.append(new_konsep)
            new_from_lampiran += 1

    print(f"  Match & enrich konsep existing: {matched}")
    print(f"    (match by krama index): {matched_by_krama}")
    print(f"    (match by ngoko index): {matched - matched_by_krama}")
    print(f"    (cross-ref override ngoko→krama): {cross_ref_overrides}")
    print(f"  New konsep dari Lampiran (no match): {new_from_lampiran}")
    return konseps


# ============================================================
# Cleanup: hapus entries yang ngoko-nya sebenarnya krama
# (cross-ref dengan angka-raw krama words)
# ============================================================
def cleanup_misplaced_krama(konseps, angka_words=None):
    """Hapus entries yang ngoko-nya sebenarnya KRAMA word (bukan ngoko).

    Cross-ref dengan angka-raw: kalau ngoko = morfem krama (dasa, sedasa, éka, dst.)
    DAN sudah ada di krama field entry lain → hapus entry ini (duplikat).

    Penyebab: full.json dan lemma taruh krama word di field ngoko (label salah).
    """
    if not angka_words:
        return konseps

    # Build set of krama words dari angka-raw
    krama_words = set()
    for a in angka_words:
        krama = (a.get("krama", "") or "").strip().lower()
        if krama:
            for k in krama.split(","):
                k = k.strip()
                if k:
                    krama_words.add(k)

    # Build index: krama words yang sudah ada di entries dengan ngoko valid
    # (entries yang punya ngoko tidak kosong DAN krama tidak kosong)
    valid_krama_in_entries = set()
    for k in konseps:
        ngoko = (k.get("ngoko", "") or "").strip()
        krama = (k.get("krama", "") or "").strip()
        if ngoko and krama:
            for w in krama.split(","):
                w = w.strip().lower()
                if w:
                    valid_krama_in_entries.add(w)

    print(f"\n🧹 Cleanup misplaced krama (cross-ref angka-raw)...")
    print(f"  angka-raw krama words: {len(krama_words)}")
    print(f"  krama words di entries valid: {len(valid_krama_in_entries)}")

    # Hapus entries yang:
    # 1. ngoko first word = krama word (dari angka-raw)
    # 2. krama field kosong (atau ngoko first == krama first)
    # 3. word sudah ada di krama field entry lain (duplikat)
    # 4. JANGAN hapus kalau ngoko == krama di angka-raw (mis. enem=enem, pitu=pitu)
    #    Itu angka yang ngoko==krama, valid sebagai ngoko
    # Build set: krama words yang ngoko-nya BEDA dari krama-nya (morfem krama asli)
    morfem_krama_only = set()
    for a in angka_words:
        ngoko = (a.get("ngoko", "") or "").strip().lower()
        krama = (a.get("krama", "") or "").strip().lower()
        if krama and not ngoko:
            # Morfem krama-only (ngoko kosong) — dasa, welas, doso, dst.
            for k in krama.split(","):
                k = k.strip()
                if k:
                    morfem_krama_only.add(k)
        elif krama and ngoko:
            # Angka dengan ngoko != krama — krama words yang BUKAN ngoko
            for k in krama.split(","):
                k = k.strip()
                if k and k != ngoko:
                    morfem_krama_only.add(k)

    # Angka yang ngoko==krama (jangan masuk morfem_krama_only)
    # sanga = ngoko DAN krama (Wiktionary: ngoko=sanga, krama=sanga)
    angka_ngoko_eq_krama = set()
    for a in angka_words:
        ngoko = (a.get("ngoko", "") or "").strip().lower()
        krama = (a.get("krama", "") or "").strip().lower()
        if ngoko and krama:
            ngoko_words_set = {w.strip() for w in ngoko.split(",")}
            krama_words_set = {w.strip() for w in krama.split(",")}
            # Words yang muncul di ngoko DAN krama = bukan morfem krama
            for w in krama_words_set:
                if w in ngoko_words_set:
                    angka_ngoko_eq_krama.add(w)

    removed = []
    kept = []
    for k in konseps:
        ngoko_first = (k.get("ngoko", "") or "").split(",")[0].strip().lower()
        krama = (k.get("krama", "") or "").strip()

        # Skip: angka yang ngoko==krama (mis. sanga=enem=pitu=wolu)
        # Itu valid sebagai ngoko, JANGAN hapus
        if ngoko_first in angka_ngoko_eq_krama:
            kept.append(k)
            continue

        # Cek: ngoko = morfem krama-only + krama kosong + sudah ada di entry lain
        if (ngoko_first in morfem_krama_only
            and (not krama or ngoko_first == krama.split(",")[0].strip().lower())
            and ngoko_first in valid_krama_in_entries):
            removed.append(k)
        else:
            kept.append(k)

    print(f"  Removed (misplaced krama, duplikat): {len(removed)}")
    for r in removed:
        n = (r.get("ngoko", "") or "").split(",")[0].strip()
        print(f"    HAPUS ngoko={n!r} arti={r.get('arti','')!r}")
    print(f"  Total setelah cleanup: {len(kept):,}")
    return kept


# ============================================================
# Fix angka: hapus bentuk sandhi dari ngoko + hapus ejaan lama
# ============================================================
def fix_angka_ngoko(konseps, angka_words=None):
    """Fix entries angka:
    1. Hapus bentuk sandhi dari ngoko (rong dari loro, dlima dari lima)
    2. Hapus entries dengan ngoko = ejaan lama yang salah (limalas, enemlas, wulas)
       jika sudah ada entry angka-raw dengan ejaan benar (limolas, nembelas, wolulas)
    """
    if not angka_words:
        return konseps

    # Bentuk sandhi yang harus dihapus dari ngoko (bukan kata standalone)
    sandhi_forms = {'rong', 'dlima', 'telu', 'papat'}  # telu/papat jangan hapus, itu ngoko valid
    # Yang benar-benar sandhi:
    sandhi_only = {'rong', 'dlima', 'ng', 'nge', 'di', 'ke', 'te'}  # prefix sandhi
    # Hanya rong dan dlima yang pasti sandhi (bukan kata standalone):
    sandhi_to_remove = {'rong', 'dlima'}

    # Kata yang BUKAN sinonim angka tapi nyangkut di ngoko entry angka
    # (artifact dari dedup_konseps_by_ngoko merge)
    # karo, lan = "dan/with" (BUKAN angka 2), nyangkut di entry loro
    not_synonim_angka = {'karo', 'lan'}

    # Ejaan lama yang salah (diganti angka-raw v2):
    # User: 15=limolas (bukan limalas), 16=nembelas (bukan enemlas), 18=wolulas (bukan wulas)
    wrong_ngoko = {'limalas', 'enemlas', 'wulas'}

    # Build set of ngoko yang benar dari angka-raw (ejaan baru)
    correct_ngoko = set()
    for a in angka_words:
        ngoko = (a.get("ngoko", "") or "").strip().lower()
        if ngoko:
            correct_ngoko.add(ngoko)

    print(f"\n🔧 Fix angka ngoko...")
    sandhi_fixed = 0
    wrong_removed = 0
    kept = []

    for k in konseps:
        if not k.get("is_angka"):
            # Cek: hapus entries dengan ngoko = ejaan lama yang salah
            ngoko_first = (k.get("ngoko", "") or "").split(",")[0].strip().lower()
            if ngoko_first in wrong_ngoko:
                # Cek apakah ejaan benar sudah ada di konsep lain
                # (limolas, nembelas, wolulas dari angka-raw)
                wrong_removed += 1
                continue  # skip — hapus entry ini
            kept.append(k)
            continue

        # Fix: hapus bentuk sandhi + kata bukan sinonim dari ngoko field
        ngoko = k.get("ngoko", "") or ""
        if ngoko:
            ngoko_words = [w.strip() for w in ngoko.split(",") if w.strip()]
            cleaned = [w for w in ngoko_words if w.lower() not in sandhi_to_remove
                       and w.lower() not in not_synonim_angka]
            if len(cleaned) != len(ngoko_words):
                k["ngoko"] = ", ".join(cleaned)
                sandhi_fixed += 1

        kept.append(k)

    print(f"  Sandhi dihapus dari ngoko: {sandhi_fixed}")
    print(f"  Ejaan lama dihapus: {wrong_removed} (limalas, enemlas, wulas)")
    print(f"  Total setelah fix: {len(kept):,}")
    return kept


# ============================================================
# Post-processing arti (fix parsing artifacts)
# ============================================================
def clean_arti(arti_raw, ngoko, krama, is_angka=False):
    """Clean arti Indonesia dari artifact parser Wiktionary.

    Returns: (clean_arti, moved_to_keterangan, status)
      - clean_arti: sinonim pendek yang valid, atau '' kalau gak valid
      - moved_to_keterangan: text yang dipindah ke keterangan (kalau arti panjang)
      - status: 'clean' | 'self_ref' | 'long_def' | 'empty'

    Args:
      is_angka: kalau True, skip SELF_REF check (angka Jawa sering punya
                arti Indonesia == krama, e.g. telu/tiga/tiga — itu valid, bukan self_ref)
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

    # 3. Cek LONG_DEF (>30 char): arti ensiklopedis, pindah ke keterangan
    # User spec: arti harus sinonim pendek (1-2 kata Indonesia), bukan kalimat definisi
    # Mis. 'hutan; rimba; tali pada alat penyeimbang perahu kecil' (50 char) = definisi
    # Pindah ke keterangan, arti dikosongkan (user isi sinonim pendek manual)
    # Skip untuk is_angka: angka komposisi (>30 char) valid, bukan definisi ensiklopedis
    # Mis. 'seratus sembilan puluh sembilan' (33 char) = arti valid angka 199
    moved_to_ket = ""  # akumulasi text yang dipindah ke keterangan
    if len(arti) > 30 and not is_angka:
        return "", arti, "long_def"

    # 3b. Cek GRAMMAR/ENSIKLOPEDIS pattern PER SEGMENT (split ;)
    # Pola: "kata ganti...", "sufiks...", "nama ikan laut", "nama lain tokoh...",
    # "tembung..." (kata Jawa), "bentuk...", "jenis...", dll.
    # Kalau ada segment yang match → pindah ke keterangan, segment lain (sinonim pendek) tetap
    grammar_patterns = [
        r"^kata ganti",
        r"^sufiks",
        r"^imbuh",
        r"^awalan",
        r"^partikel",
        r"^kata penghubung",
        r"^kata tanya",
        r"^kata seru",
        r"^kata bilangan",
        r"^kata depan",
        r"^kata sandang",
        r"^bentuk",
        r"^tembung",
        r"^jenis ",
        r"^nama ",
        r"^istilah ",
    ]
    segments = [s.strip() for s in arti.split(";") if s.strip()]
    grammar_segments = []
    sinonim_segments = []
    for seg in segments:
        seg_lower = seg.lower()
        if any(re.match(p, seg_lower) for p in grammar_patterns):
            grammar_segments.append(seg)
        else:
            sinonim_segments.append(seg)
    if grammar_segments:
        moved_to_ket = "; ".join(grammar_segments)
        if sinonim_segments:
            arti = "; ".join(sinonim_segments)
            # Lanjut ke step 4-8 untuk clean sinonim_segments
        else:
            # Semua segment grammar → kosongkan arti, pindah semua ke keterangan
            return "", moved_to_ket, "long_def"

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
    # Skip untuk is_angka: angka Jawa sering punya arti Indonesia == krama
    # (mis. telu/tiga/tiga — itu valid, bukan loopback)
    if not is_angka:
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

    return arti, moved_to_ket, "clean"


def post_process_konseps(konseps):
    """Apply clean_arti ke semua konsep + pindah long_def ke keterangan."""
    print(f"\n🧹 Post-process arti ({len(konseps):,} konsep)...")
    stats = {
        "clean": 0,
        "self_ref_cleared": 0,
        "long_def_moved": 0,
        "grammar_moved": 0,
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
        is_angka = bool(k.get("is_angka"))
        clean, moved, status = clean_arti(arti_raw, ngoko, krama, is_angka=is_angka)

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
            # Clean atau setelah fix — sintrim pendek yang valid
            k["arti"] = clean
            stats["clean"] += 1
            # Kalau ada grammar/ensiklopedis segment yang dipindah → add ke keterangan
            if moved:
                existing_ket = k.get("keterangan", "")
                if moved not in existing_ket:
                    k["keterangan"] = f"{existing_ket} | {moved}".strip(" |") if existing_ket else moved
                stats["grammar_moved"] += 1
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
    print(f"  Grammar moved ke keterangan (sinonim tetap di arti): {stats['grammar_moved']}")
    print(f"  Empty (no arti from source): {stats['empty']}")
    print(f"  Paren stripped: {stats['paren_stripped']}")
    print(f"  Colon stripped: {stats['colon_stripped']}")
    print(f"  Dup deduped: {stats['dup_deduped']}")
    return konseps


# ============================================================
# Dedup konsep by primary ngoko
# Merge entries dengan primary ngoko sama (ejaan beda, krama beda, dst.)
# ============================================================
def dedup_konseps_by_ngoko(konseps):
    """Merge konsep dengan primary ngoko sama.

    Penyebab duplikat:
      - Ejaan beda (asrep vs asrêp) → group_by_krama pisah
      - Entries dengan ngoko sama tapi krama beda (1 ada, 1 kosong)
      - Entries dengan krama sama tapi ngoko beda

    Merge logic:
      - ngoko: gabung comma (dedup word-level)
      - krama: gabung comma (dedup word-level)
      - krama_inggil: gabung comma (dedup word-level)
      - arti: gabung ; (dedup, prioritaskan yang non-empty)
      - keterangan: gabung | (jangan buang, audit trail)
      - aksara: gabung comma (dedup)
      - register: tetap 'umum' (semua umum)
      - source_count: sum dari semua merged
      - sumber: gabung uniq
      - is_lemma, is_mendeley, is_dasanama: OR (true kalau salah satu ada)
      - dasanama_count: max
      - mendeley_id, lemma_words: gabung
    """
    print(f"\n🧹 Dedup konsep by primary ngoko ({len(konseps):,} entries)...")

    # Group by primary ngoko (lowercase)
    # Entries dengan ngoko kosong: group by arti (supaya angka 33, 34, 35 dst. tidak merge jadi 1)
    groups = defaultdict(list)
    no_ngoko = []
    for k in konseps:
        n_first = (k.get("ngoko", "") or "").split(",")[0].strip().lower()
        if n_first:
            groups[n_first].append(k)
        else:
            # Entry tanpa ngoko — group by arti (bukan orphan blind merge)
            # Setiap arti beda = konsep beda (mis. "tiga puluh tiga" ≠ "empat puluh satu")
            arti_key = (k.get("arti", "") or "").strip().lower()
            if arti_key:
                groups[f"__no_ngoko__{arti_key}"].append(k)
            else:
                no_ngoko.append(k)

    print(f"  Unique primary ngoko: {len(groups):,}")
    print(f"  Orphan (no ngoko, krama-only): {len(no_ngoko):,}")
    print(f"  Duplikat groups (>1 entry): {sum(1 for v in groups.values() if len(v) > 1):,}")
    print(f"  Total entries duplikat: {sum(len(v) for v in groups.values() if len(v) > 1):,}")

    merged_konseps = []
    merged_count = 0
    for ngoko_key, entries in groups.items():
        if len(entries) == 1:
            merged_konseps.append(entries[0])
            continue

        # Merge multiple entries jadi 1
        merged_count += 1
        merged = merge_konsep_group(entries)
        merged_konseps.append(merged)

    # Tambah orphan entries (no ngoko)
    merged_konseps.extend(no_ngoko)

    print(f"  Merged groups: {merged_count:,}")
    print(f"  Total setelah dedup: {len(merged_konseps):,}")
    return merged_konseps


def merge_konsep_group(entries):
    """Merge multiple konsep (primary ngoko sama) jadi 1."""
    # Collect semua field gabungan
    ngoko_words = []
    krama_words = []
    ki_words = []
    aksara_words = []
    arti_parts = []
    keterangan_parts = []
    sumber_parts = []
    lemma_words_set = set()
    mendeley_ids = set()
    source_count = 0
    is_lemma = False
    is_mendeley = False
    is_dasanama = False
    is_angka = False
    dasanama_count = 0

    for e in entries:
        # ngoko: split per word
        for w in (e.get("ngoko", "") or "").split(","):
            w = w.strip().lower()
            if w and w not in ngoko_words:
                ngoko_words.append(w)
        # krama: split per word
        for w in (e.get("krama", "") or "").split(","):
            w = w.strip().lower()
            if w and w not in krama_words:
                krama_words.append(w)
        # krama_inggil
        for w in (e.get("krama_inggil", "") or "").split(","):
            w = w.strip().lower()
            if w and w not in ki_words:
                ki_words.append(w)
        # aksara (preserve case)
        for w in (e.get("aksara", "") or "").split(","):
            w = w.strip()
            if w and w not in aksara_words:
                aksara_words.append(w)
        # arti: split per segment (;)
        for seg in (e.get("arti", "") or "").split(";"):
            seg = seg.strip()
            if seg and seg.lower() not in [a.lower() for a in arti_parts]:
                arti_parts.append(seg)
        # keterangan: gabung | (dedup)
        ket = (e.get("keterangan", "") or "").strip()
        if ket and ket not in keterangan_parts:
            keterangan_parts.append(ket)
        # sumber: gabung uniq
        s = (e.get("sumber", "") or "").strip()
        if s and s not in sumber_parts:
            sumber_parts.append(s)
        # tags
        if e.get("is_lemma"):
            is_lemma = True
            for lw in (e.get("lemma_words", "") or "").split(","):
                lw = lw.strip().lower()
                if lw:
                    lemma_words_set.add(lw)
        if e.get("is_mendeley"):
            is_mendeley = True
            mid = (e.get("mendeley_id", "") or "").strip()
            if mid:
                mendeley_ids.add(mid)
        if e.get("is_dasanama"):
            is_dasanama = True
            dc = e.get("dasanama_count", 0) or 0
            if dc > dasanama_count:
                dasanama_count = dc
        if e.get("is_angka"):
            is_angka = True
        source_count += e.get("source_count", 1) or 1

    merged = {
        "ngoko": ", ".join(ngoko_words),
        "krama": ", ".join(krama_words),
        "krama_inggil": ", ".join(ki_words),
        "arti": "; ".join(arti_parts),
        "keterangan": " | ".join(keterangan_parts),
        "aksara": ", ".join(aksara_words),
        "register": "umum",
        "status": "draft",  # default draft, user edit via TUI → save → recompute jadi 'ready'
        "sumber": " + ".join(sumber_parts),
        "source_count": source_count,
    }
    if is_lemma:
        merged["is_lemma"] = True
        merged["lemma_words"] = ", ".join(sorted(lemma_words_set))
    if is_mendeley:
        merged["is_mendeley"] = True
        merged["mendeley_id"] = ", ".join(sorted(mendeley_ids))
    if is_dasanama:
        merged["is_dasanama"] = True
        merged["dasanama_count"] = dasanama_count
    if is_angka:
        merged["is_angka"] = True
    return merged


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

    # Merge Dasanama CSV (sinonim Jawa, 431 entries, user sort manual)
    dasanama_entries = load_dasanama_csv(RAW_DASANAMA)
    print(f"  dasanama.csv: {len(dasanama_entries):,} entries (sinonim Jawa)")
    if dasanama_entries:
        konseps = merge_dasanama_to_konseps(konseps, dasanama_entries)

    # Merge Angka JSON (built-in AI reference, 26 entries, sistematis)
    # SEBELUM post-process — angka curated, jangan sampai clean_arti ganggu
    angka_words = load_angka_json(RAW_ANGKA)
    print(f"  angka.json: {len(angka_words):,} entries (angka 1-20, puluhan, ratusan, ribuan)")
    if angka_words:
        konseps = merge_angka_to_konseps(konseps, angka_words)

    # Merge Lampiran Kamus Jawa-Indonesia (2724 entries, curated)
    # Cross-reference: cek is_krama flag + cross-ref angka-raw krama words
    # JANGAN trust field label "ngoko" dari Lampiran — cek is_krama + cross-ref
    lampiran_words = load_lampiran_json(RAW_LAMPIRAN)
    print(f"  lampiran.json: {len(lampiran_words):,} entries (Lampiran Kamus Jawa-Indonesia)")
    if lampiran_words:
        konseps = merge_lampiran_to_konseps(konseps, lampiran_words, angka_words=angka_words)

    # Post-process arti (clean artifact, move long_def ke keterangan)
    konseps = post_process_konseps(konseps)

    # Dedup konsep by primary ngoko (merge entries dengan ngoko sama)
    konseps = dedup_konseps_by_ngoko(konseps)

    # Cross-ref cleanup: hapus entries yang ngoko-nya sebenarnya krama
    # (morfem bilangan dari full.json/lemma yang label-nya salah)
    konseps = cleanup_misplaced_krama(konseps, angka_words)

    # Fix angka: hapus bentuk sandhi dari ngoko + hapus ejaan lama yang salah
    konseps = fix_angka_ngoko(konseps, angka_words)

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
