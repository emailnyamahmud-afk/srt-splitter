#!/usr/bin/env python3
"""
scrape-wiktionary-jv-lemma.py — Scrape Kategori:jv:Lema di id.wiktionary.org

Tujuan:
  Tambah kamus Jawa dari Wiktionary Indonesia (Kategori:jv:Lema — 2.187 lemma).
  Output: kamus-jawa-new.json berisi entry yang BELUM ada di kamus-jawa-full.json,
  siap user review di kamus-tui.py lalu upload ke Supabase.

Strategi:
  1. Ambil list title dari MediaWiki API categorymembers (500 per batch)
  2. Ambil wikitext via batch API (50 title per request) — efficient, ~44 request
  3. Parse wikitext setiap entry:
     - Section jv: (antara =={{bahasa|jv}}== sampai == bahasa lain ==)
     - register dari {{kn}} / {{kr}} / {{ki}} / {{ak}} tag
     - aksara dari {{kepala|jv|alt=XXX}} atau {{sirah|jv|alt=XXX}}
     - krama/ngoko cross-ref dari {{ngoko|...}} / {{krama|...}} / {{ki|...}}
     - definisi dari baris # (arti Indonesia + keterangan)
  4. Diff dengan kamus-jawa-full.json (44.585 entries existing)
  5. Output:
     - /home/z/my-project/download/kamus-jawa-lemma-raw.json (full scraped)
     - /home/z/my-project/download/kamus-jawa-new.json (hanya yang belum ada)
     - /home/z/my-project/download/kamus-jawa-scrape-report.txt (statistik)

Usage:
  python3 scrape-wiktionary-jv-lemma.py
  python3 scrape-wiktionary-jv-lemma.py --dry-run   # tanpa save
  python3 scrape-wiktionary-jv-lemma.py --batch-size 25  # default 50

Output fields (sesuai schema kamus v5):
  {
    "ngoko": "abot",
    "aksara": "ꦲꦧꦺꦴꦠ꧀",
    "krama": "awrat",
    "krama_inggil": "",
    "arti": "berat; tidak rela; parah",
    "keterangan": "definisi Jawa dari wikitext",
    "register": "ngoko",
    "sumber": "id.wiktionary.org Kategori:jv:Lema"
  }
"""

import urllib.request
import urllib.parse
import json
import re
import sys
import time
import argparse
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

# ============================================================
# Config
# ============================================================
UA = "SrtSplitterBot/1.0 (https://github.com/emailnyamahmud-afk/srt-splitter; educational use, kamus Jawa)"
API_BASE = "https://id.wiktionary.org/w/api.php"
CATEGORY = "Kategori:jv:Lema"
EXISTING_KAMUS = "/home/z/my-project/public/kamus-jawa-full.json"
OUT_DIR = Path("/home/z/my-project/download")
OUT_RAW = OUT_DIR / "kamus-jawa-lemma-raw.json"
OUT_NEW = OUT_DIR / "kamus-jawa-new.json"
OUT_REPORT = OUT_DIR / "kamus-jawa-scrape-report.txt"
DEFAULT_BATCH = 50  # MediaWiki API max: 50 titles per request (anonymous)
REQUEST_DELAY = 0.5  # detik antar request (polite, avoid 403)


# ============================================================
# Network helpers
# ============================================================
def api_get(params, timeout=20):
    """MediaWiki API GET request."""
    url = API_BASE + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def fetch_category_titles():
    """Ambil semua title di Kategori:jv:Lema via categorymembers API."""
    print(f"📋 Fetching titles from {CATEGORY}...")
    titles = []
    cmcontinue = ""
    batch = 0
    while True:
        batch += 1
        params = {
            "action": "query",
            "list": "categorymembers",
            "cmtitle": CATEGORY,
            "cmlimit": "500",
            "cmtype": "page",
            "cmprop": "title",
            "format": "json",
        }
        if cmcontinue:
            params["cmcontinue"] = cmcontinue
        d = api_get(params)
        members = d["query"]["categorymembers"]
        titles.extend(m["title"] for m in members)
        cont = d.get("continue", {}).get("cmcontinue")
        print(f"  Batch {batch}: +{len(members)} (total {len(titles)})")
        if not cont:
            break
        cmcontinue = cont
        time.sleep(REQUEST_DELAY)
    print(f"✓ Total {len(titles)} titles\n")
    return titles


def fetch_wikitext_batch(titles):
    """Fetch wikitext untuk list title (batch max 50). Returns dict {title: wikitext}."""
    params = {
        "action": "query",
        "prop": "revisions",
        "titles": "|".join(titles),
        "rvprop": "content",
        "rvslots": "main",
        "format": "json",
    }
    try:
        d = api_get(params, timeout=30)
    except Exception as e:
        print(f"  ⚠ Error fetching batch: {e}")
        return {}
    out = {}
    pages = d.get("query", {}).get("pages", {})
    for pageid, page in pages.items():
        title = page.get("title", "")
        revs = page.get("revisions", [])
        if not revs:
            continue
        content = revs[0].get("slots", {}).get("main", {}).get("*", "")
        if content:
            out[title] = content
    return out


# ============================================================
# Wikitext parser (reuse logic dari parse-wiktionary-jv.py)
# ============================================================
def extract_jv_section(wikitext):
    """Ambil section jv: saja (antara =={{bahasa|jv}}== sampai == bahasa lain ==)."""
    # Pattern: =={{bahasa|jv}}== sampai =={{bahasa|...}}== berikutnya
    # Beberapa entry pakai {{basa|jv}} (lama) atau {{bahasa|jv}} (baru)
    m = re.search(r'==\s*\{\{(?:bahasa|basa)\|jv\}\}\s*==(.*?)(?==\s*\{\{(?:bahasa|basa)\|[^}]+\}\}\s*==|\Z)',
                  wikitext, re.DOTALL)
    if m:
        return m.group(1)
    return ""


def extract_aksara(jv_section):
    """Aksara Jawa dari {{kepala|jv|alt=XXX}} atau {{sirah|jv|alt=XXX}}."""
    m = re.search(r'\{\{(?:kepala|sirah)\|jv[^}]*alt=([^\s|}]+)', jv_section)
    if m:
        return m.group(1)
    return ""


def detect_register(jv_section):
    """Deteksi register dari tag {{kn}} / {{kr}} / {{ki}} / {{ak}}.

    Prioritas: {{kn}} > {{ki}} > {{ak}} > umum
    """
    if "{{kn}}" in jv_section or "{{ngoko}}" in jv_section:
        return "ngoko"
    if "{{kr}}" in jv_section or "{{krama}}" in jv_section:
        return "krama"
    if "{{ki}}" in jv_section:
        return "krama_inggil"
    if "{{ak}}" in jv_section:
        return "kawi"
    return "umum"


def extract_template_xrefs(jv_section):
    """Parse template {{ngoko|word}}, {{krama|word1|word2}}, {{ki|word}}.

    Templates ini adalah cross-reference antar register:
      {{ngoko|abrit}}  → "entry ini punya ngoko equivalent = abrit"
      {{krama|abang}}  → "entry ini punya krama equivalent = abang"

    Returns dict {ngoko: [], krama: [], krama_inggil: []}
    """
    refs = {"ngoko": [], "krama": [], "krama_inggil": []}
    patterns = [
        (r'\{\{ngoko\|([^}]+)\}\}', "ngoko"),
        (r'\{\{krama\|([^}]+)\}\}', "krama"),
        (r'\{\{ki\|([^}]+)\}\}', "krama_inggil"),
    ]
    for pattern, ref_type in patterns:
        for m in re.finditer(pattern, jv_section, re.IGNORECASE):
            params = m.group(1).split("|")
            for p in params:
                word = p.strip()
                if "=" in word or word.startswith(":") or not word:
                    continue
                if word not in refs[ref_type]:
                    refs[ref_type].append(word)
    return refs


def extract_jvword_template(jv_section):
    """Parse template {{jvword|k=awrat|n=abot}} (krama=k, ngoko=n).

    Pattern ini sering di entry yang punya pasangan ngoko+krama dalam satu halaman.
    """
    refs = {"ngoko": [], "krama": [], "krama_inggil": []}
    m = re.search(r'\{\{jvword[^}]*\}\}', jv_section)
    if m:
        tpl = m.group(0)
        # Extract k= and n= parameters
        mk = re.search(r'k=([^|}]+)', tpl)
        mn = re.search(r'n=([^|}]+)', tpl)
        if mk:
            k_word = mk.group(1).strip()
            if k_word and k_word not in refs["krama"]:
                refs["krama"].append(k_word)
        if mn:
            n_word = mn.group(1).strip()
            if n_word and n_word not in refs["ngoko"]:
                refs["ngoko"].append(n_word)
    return refs


def extract_definitions(jv_section):
    """Extract definisi dari baris # (arti Indonesia + keterangan Jawa).

    Returns (arti, keterangan) tuple:
      - arti: Indonesia translation, comma-separated
      - keterangan: full raw definitions (Jawa/Indonesia mix), newline-separated
    """
    arti_parts = []
    keterangan_parts = []
    lines = jv_section.split("\n")
    for line in lines:
        line = line.rstrip()
        # Skip contoh (#:) dan sub-definitions (##, ###)
        if line.startswith("#:") or line.startswith("##") or line.startswith("#*"):
            continue
        # Hanya baris # (definition utama)
        if line.startswith("#") and not line.startswith("##"):
            def_text = line[1:].strip()
            # Strip template {{...}}
            def_text_clean = re.sub(r'\{\{[^}]*\}\}', '', def_text)
            # Strip link [[...]] → keep text
            def_text_clean = re.sub(r'\[\[([^]]*)\]\]', r'\1', def_text_clean)
            def_text_clean = re.sub(r"\[\[([^|]+)\|([^]]+)\]\]", r"\2", def_text_clean)
            def_text_clean = def_text_clean.strip(" ,;.").replace("  ", " ")
            if def_text_clean and len(def_text_clean) > 1:
                arti_parts.append(def_text_clean)
                keterangan_parts.append(def_text)
    arti = "; ".join(arti_parts[:3])  # max 3 arti utama
    keterangan = "\n".join(keterangan_parts[:10])
    return arti, keterangan


# ============================================================
# Build kamus entry
# ============================================================
def parse_entry(title, wikitext):
    """Parse wikitext satu entry jadi kamus record.

    Returns dict sesuai schema v5, atau None kalau bukan entry jv.
    """
    jv_section = extract_jv_section(wikitext)
    if not jv_section:
        return None  # entry ini gak punya section jv

    register = detect_register(jv_section)
    aksara = extract_aksara(jv_section)
    xrefs_tpl = extract_template_xrefs(jv_section)
    xrefs_jvw = extract_jvword_template(jv_section)
    # Merge xrefs
    krama_xrefs = xrefs_tpl["krama"] + xrefs_jvw["krama"]
    ngoko_xrefs = xrefs_tpl["ngoko"] + xrefs_jvw["ngoko"]
    ki_xrefs = xrefs_tpl["krama_inggil"] + xrefs_jvw["krama_inggil"]

    arti, keterangan = extract_definitions(jv_section)

    # Build entry sesuai register
    ngoko = ""
    krama = ""
    krama_inggil = ""

    if register == "ngoko":
        ngoko = title
        if krama_xrefs:
            krama = ", ".join(krama_xrefs)
    elif register == "krama":
        krama = title
        if ngoko_xrefs:
            ngoko = ", ".join(ngoko_xrefs)
    elif register == "krama_inggil":
        krama_inggil = title
        if ngoko_xrefs:
            ngoko = ", ".join(ngoko_xrefs)
        if krama_xrefs:
            krama = ", ".join(krama_xrefs)
    else:  # umum
        ngoko = title
        if krama_xrefs:
            krama = ", ".join(krama_xrefs)

    # Tambah krama_inggil cross-ref kalau ada
    if ki_xrefs and not krama_inggil:
        krama_inggil = ", ".join(ki_xrefs)

    # Bug fix: hapus self-reference (kalau krama/ngoko sama dengan title,
    # itu artifact dari template {{krama|word}} yang muncul di entry word sendiri)
    if krama:
        krama_words = [w.strip() for w in krama.split(",") if w.strip().lower() != title.lower()]
        krama = ", ".join(krama_words) if krama_words else ""
    if ngoko and register != "ngoko" and ngoko != title:
        ngoko_words = [w.strip() for w in ngoko.split(",") if w.strip().lower() != title.lower()]
        ngoko = ", ".join(ngoko_words) if ngoko_words else ""

    return {
        "ngoko": ngoko,
        "aksara": aksara,
        "krama": krama,
        "krama_inggil": krama_inggil,
        "arti": arti,
        "keterangan": keterangan,
        "register": register,
        "sumber": "id.wiktionary.org Kategori:jv:Lema",
        "_title": title,  # untuk tracking, hapus sebelum output
    }


# ============================================================
# Diff vs existing kamus
# ============================================================
def load_existing_kamus():
    """Load kamus-jawa-full.json, return set of known ngoko/krama keys.

    Format kamus: {"metadata": {...}, "words": [{ngoko, krama, ...}, ...]}
    """
    path = Path(EXISTING_KAMUS)
    if not path.exists():
        print(f"⚠ Existing kamus tidak ditemukan: {path}")
        return set()
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    # Handle 2 format: {metadata, words} atau list langsung
    if isinstance(data, dict) and "words" in data:
        existing = data["words"]
    elif isinstance(data, list):
        existing = data
    else:
        print(f"⚠ Format kamus tidak dikenali: {type(data).__name__}")
        return set()
    known = set()
    for e in existing:
        if not isinstance(e, dict):
            continue
        for field in ("ngoko", "krama", "krama_inggil"):
            v = e.get(field, "")
            if not v:
                continue
            # Split alias (comma) dan lowercase untuk key
            for w in v.split(","):
                w = w.strip().lower()
                if w:
                    known.add(w)
    print(f"✓ Existing kamus: {len(existing)} entries, {len(known)} unique keys\n")
    return known


def is_new_entry(entry, known_keys):
    """Cek apakah entry ini belum ada di kamus existing."""
    title = entry.get("_title", "").lower()
    if title and title in known_keys:
        return False
    # Cek juga alias di ngoko/krama
    for field in ("ngoko", "krama", "krama_inggil"):
        v = entry.get(field, "")
        if not v:
            continue
        for w in v.split(","):
            w = w.strip().lower()
            if w and w in known_keys:
                return False
    return True


# ============================================================
# Main
# ============================================================
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="Tanpa save file")
    parser.add_argument("--batch-size", type=int, default=DEFAULT_BATCH)
    parser.add_argument("--limit", type=int, help="Hanya proses N entry pertama (debug)")
    args = parser.parse_args()

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    # 1. Fetch titles
    titles = fetch_category_titles()
    if args.limit:
        titles = titles[:args.limit]
        print(f"⚠ Limit: hanya proses {len(titles)} entry pertama\n")

    # 2. Fetch wikitext in batches
    print(f"🌐 Fetching wikitext ({len(titles)} titles, batch {args.batch_size})...")
    all_wikitexts = {}
    for i in range(0, len(titles), args.batch_size):
        batch_titles = titles[i:i+args.batch_size]
        print(f"  Batch {i//args.batch_size + 1}/{(len(titles)-1)//args.batch_size + 1}: {len(batch_titles)} titles")
        result = fetch_wikitext_batch(batch_titles)
        all_wikitexts.update(result)
        time.sleep(REQUEST_DELAY)
    print(f"✓ Got wikitext untuk {len(all_wikitexts)}/{len(titles)} entries\n")

    # 3. Parse setiap entry
    print("🔍 Parsing entries...")
    parsed = []
    skipped_no_jv = 0
    for title in titles:
        wt = all_wikitexts.get(title, "")
        if not wt:
            continue
        entry = parse_entry(title, wt)
        if entry is None:
            skipped_no_jv += 1
            continue
        parsed.append(entry)
    print(f"✓ Parsed {len(parsed)} entries (skip {skipped_no_jv} non-jv)\n")

    # 4. Diff vs existing
    print("🔍 Compare dengan kamus existing...")
    known_keys = load_existing_kamus()
    new_entries = []
    for entry in parsed:
        if is_new_entry(entry, known_keys):
            new_entries.append(entry)
    print(f"✓ New entries (belum ada di kamus): {len(new_entries)}\n")

    # 5. Stats
    stats = {
        "total_scraped": len(titles),
        "with_wikitext": len(all_wikitexts),
        "parsed_jv": len(parsed),
        "skipped_no_jv": skipped_no_jv,
        "new_entries": len(new_entries),
        "with_aksara": sum(1 for e in new_entries if e["aksara"]),
        "with_arti": sum(1 for e in new_entries if e["arti"]),
        "with_krama": sum(1 for e in new_entries if e["krama"]),
        "with_krama_inggil": sum(1 for e in new_entries if e["krama_inggil"]),
        "by_register": {},
    }
    for e in new_entries:
        r = e["register"]
        stats["by_register"][r] = stats["by_register"].get(r, 0) + 1

    # 6. Save output
    if args.dry_run:
        print("⚠ Dry run, tidak save file")
    else:
        # Strip _title sebelum save
        for e in parsed:
            e.pop("_title", None)
        for e in new_entries:
            e.pop("_title", None)

        with open(OUT_RAW, "w", encoding="utf-8") as f:
            json.dump(parsed, f, ensure_ascii=False, indent=2)
        print(f"✓ Save raw: {OUT_RAW} ({len(parsed)} entries)")

        with open(OUT_NEW, "w", encoding="utf-8") as f:
            json.dump(new_entries, f, ensure_ascii=False, indent=2)
        print(f"✓ Save new: {OUT_NEW} ({len(new_entries)} entries)")

        with open(OUT_REPORT, "w", encoding="utf-8") as f:
            f.write("Scrape Report Wiktionary Kategori:jv:Lema\n")
            f.write("=" * 50 + "\n\n")
            for k, v in stats.items():
                if isinstance(v, dict):
                    f.write(f"{k}:\n")
                    for sub_k, sub_v in v.items():
                        f.write(f"  {sub_k:20s}: {sub_v}\n")
                else:
                    f.write(f"{k:25s}: {v}\n")
            f.write("\n")
            f.write(f"Source       : {CATEGORY}\n")
            f.write(f"Existing kamus: {EXISTING_KAMUS}\n")
            f.write(f"Output raw   : {OUT_RAW}\n")
            f.write(f"Output new   : {OUT_NEW}\n")
        print(f"✓ Save report: {OUT_REPORT}")

    # Print summary
    print("\n" + "=" * 50)
    print("📊 STATISTIK:")
    for k, v in stats.items():
        if isinstance(v, dict):
            print(f"  {k}:")
            for sk, sv in v.items():
                print(f"    {sk:20s}: {sv}")
        else:
            print(f"  {k:25s}: {v}")
    print("=" * 50)


if __name__ == "__main__":
    main()
