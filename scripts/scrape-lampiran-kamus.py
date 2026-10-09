#!/usr/bin/env python3
"""
scrape-lampiran-kamus.py — Scrape Lampiran:Kamus bahasa Jawa – bahasa Indonesia

Source: https://id.wiktionary.org/wiki/Lampiran:Kamus_bahasa_Jawa_–_bahasa_Indonesia
Total: 2.724 kata Jawa → Indonesia (claim wiki)
Format: "kataJawa (kelas): arti Indonesia"

Kelas kata (BONUS metadata):
  (t.a.) = tembung aran = kata benda
  (t.k.) = tembung kriya = kata kerja
  (t.s.) = tembung sipat = kata sifat
  (t.kr.) = tembung katrangan = kata keadaan
  (t.pw.) = tembung panguwuh = kata seru
  (t.pr.) = tembung pangarep = kata depan
  (t.py.) = tembung panyambung = kata sambung
  (t.g.) = tembung ganti = kata ganti
  (t.sd.) = tembung sandhangan = kata sandang
  (t.w.) = tembung wilangan = kata bilangan
  (K) = Krama (register halus)

Output: /home/z/my-project/public/lampiran-raw.json
Schema: {metadata, words: [{ngoko, arti, kelas, is_krama}]}

Usage:
  python3 scrape-lampiran-kamus.py
"""

import urllib.request
import re
import json
from pathlib import Path

URL = "https://id.wiktionary.org/wiki/Lampiran:Kamus_bahasa_Jawa_%E2%80%93_bahasa_Indonesia"
UA = "SrtSplitterBot/1.0 (https://github.com/emailnyamahmud-afk/srt-splitter; educational use)"
OUT = Path("/home/z/my-project/public/lampiran-raw.json")


def fetch_html():
    print(f"🌐 Fetching Lampiran:Kamus bahasa Jawa – bahasa Indonesia...")
    req = urllib.request.Request(URL, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8")


def parse_entries(html):
    """Parse semua <li> entries di mw-parser-output.

    Format:
      "kataJawa (kelas): arti Indonesia"      — format standar
      "kataJawa (t.s.) (K): arti"             — krama di akhir
      "kataJawa: arti"                        — tanpa kelas
      "kataJawa\nkataJawa2 (t.k.): arti"      — multiple entries per <li>

    Kelas kata:
      (t.a.) = tembung aran = kata benda
      (t.k.) = tembung kriya = kata kerja
      (t.s.) = tembung sipat = kata sifat
      (t.kr.) = tembung katrangan = kata keadaan
      (t.pw.) = tembung panguwuh = kata seru
      (t.pr.) = tembung pangarep = kata depan
      (t.py.) = tembung panyambung = kata sambung
      (t.g.) = tembung ganti = kata ganti
      (t.sd.) = tembung sandhangan = kata sandang
      (t.w.) = tembung wilangan = kata bilangan
      (K) = Krama (register halus)
    """
    start = html.find("mw-parser-output")
    if start < 0:
        print("⚠ mw-parser-output tidak ditemukan")
        return []

    content = html[start:]
    matches = re.findall(r"<li[^>]*>(.*?)</li>", content, re.DOTALL)

    valid_kelas = {
        "t.a.": "tembung aran (kata benda)",
        "t.k.": "tembung kriya (kata kerja)",
        "t.s.": "tembung sipat (kata sifat)",
        "t.kr.": "tembung katrangan (kata keadaan)",
        "t.pw.": "tembung panguwuh (kata seru)",
        "t.pr.": "tembung pangarep (kata depan)",
        "t.py.": "tembung panyambung (kata sambung)",
        "t.g.": "tembung ganti (kata ganti)",
        "t.sd.": "tembung sandhangan (kata sandang)",
        "t.w.": "tembung wilangan (kata bilangan)",
        "K": "krama",
        "tsb": "tidak standar",
        # Alias typo yang sering muncul di wiki
        "t.a": "tembung aran (kata benda)",
        "t.k": "tembung kriya (kata kerja)",
        "t.s": "tembung sipat (kata sifat)",
        "t.kr": "tembung katrangan (kata keadaan)",
        "t.pw": "tembung panguwuh (kata seru)",
        "t.pr": "tembung pangarep (kata depan)",
        "t.py": "tembung panyambung (kata sambung)",
        "t.g": "tembung ganti (kata ganti)",
        "t.sd": "tembung sandhangan (kata sandang)",
        "t.w": "tembung wilangan (kata bilangan)",
        "tk.": "tembung kriya (kata kerja)",
        "ta, ts": "tembung aran+sipat",
        "ta": "tembung aran (kata benda)",
        "ts": "tembung sipat (kata sifat)",
        "t.pb": "tembung pambanding (kata banding)",
    }

    # Normalize kelas: hapus typo, fallback ke kelas baku
    def normalize_kelas(kelas_raw):
        """Normalize kelas — handle typo di wiki."""
        kelas = kelas_raw.strip()
        # Strip prefix "{", "(", "Templat:", "}}", ")"
        kelas = kelas.lstrip("{(").rstrip("})")
        # Strip "Templat:" prefix
        kelas = kelas.replace("Templat:", "").strip()
        # Strip trailing dot (untuk kelas yang tidak ada titik)
        # Ambil first word kalau ada comma (multi-kelas)
        if "," in kelas:
            kelas = kelas.split(",")[0].strip()
        # Normalize: t.k → t.k.
        if kelas in ("t.a", "t.k", "t.s", "t.kr", "t.pw", "t.pr", "t.py", "t.g", "t.sd", "t.w"):
            kelas = kelas + "."
        return kelas

    # Skip nav items (selalu mulai dengan kata-kata ini)
    nav_items = (
        "Bantuan", "Embassy", "Tentang Wikikamus", "Lampiran", "Pembicaraan",
        "Baca", "Lihat sumber", "Lihat riwayat", "Buat akun", "Masuk log",
        "Menyumbang", "Bak pasir", "Unduh Wikikamus", "Kebijakan dan pedoman",
        "Warung Kopi", "Kategori:", "Istimewa:", "Wikikamus:", "Halaman",
    )

    parsed = []
    skipped_count = 0

    # Pattern khusus untuk entries typo wiki parah:
    # - "kata (t.s.)) arti"        (kurung tutup dobel)
    # - "kata (t.a.: arti"         (kurung tutup ilang)
    # - "[[kata](t.k.)]: arti"     (bracket rusak)
    # - "kata t.s.): arti"         (kurung buka ilang)
    # - "kata (keterangan)"        (arti di dalam kurung)
    # - "kata (keterangan), arti"   (arti di luar kurung)
    pattern_broken_paren = re.compile(
        r"^([a-zA-ZĕĕêêèéÉíàáâãäåæçìíîïðñòóôõöøùúûüýþÿ'\-\.\s/]+?)\s*\((t\.[a-z]+\.?)\s*[:\)]]+\s*(.+?)\)?$"
    )
    pattern_no_open_paren = re.compile(
        r"^([a-zA-ZĕĕêêèéÉíàáâãäåæçìíîïðñòóôõöøùúûüýþÿ'\-\.\s/]+?)\s+(t\.[a-z]+\.?)\)\s*:?\s*(.+)$"
    )
    pattern_bracket_rusak = re.compile(
        r"^\[+\*?\*?\[?([a-zA-ZĕĕêêèéÉíàáâãäåæçìíîïðñòóôõöøùúûüýþÿ'\-\.\s/]+?)\]?\s*\(([^)]+)\)\]?:\s*(.+)$"
    )
    pattern_paren_arti_only = re.compile(
        r"^([a-zA-ZĕĕêêèéÉíàáâãäåæçìíîïðñòóôõöøùúûüýþÿ'\-\.\s/]+?)\s*\(([^tK][^)]*)\)\s*,?\s*(.*)$"
    )
    pattern_multi_koma = re.compile(
        r"^([a-zA-ZĕĕêêèéÉíàáâãäåæçìíîïðñòóôõöøùúûüýþÿ'\-\.\s/]+?)\s*:\s*(.+)$"
    )

    # Patterns (urutan trial, paling spesifik dulu):
    # 1. "kata (K) (kelas): arti"  — krama dulu, kelas di belakang
    # 2. "kata (kelas) (K): arti"  — kelas dulu, krama di belakang
    # 3. "kata (kelas): arti"      — format standar
    # 4. "kata (kelas) arti"       — tanpa colon (hanya spasi)
    # 5. "kata: arti"              — tanpa kelas
    # Allow slash (/) dan comma (,) di kata untuk handle: "delok/deleng", "gawa, nggawa"
    KATA_PATTERN = r"[a-zA-ZĕĕêêèéÉíàáâãäåæçìíîïðñòóôõöøùúûüýþÿ'\-\.\s/,]+?"
    pattern_k_kelas = re.compile(rf"^({KATA_PATTERN})\s*\(K\)\s*\(([^)]+)\)\s*:?\s*(.+)$")
    pattern_kelas_k = re.compile(rf"^({KATA_PATTERN})\s*\(([^)]+)\)\s*\(K\)\s*:?\s*(.+)$")
    pattern_kelas = re.compile(rf"^({KATA_PATTERN})\s*\(([^)]+)\)\s*:\s*(.+)$")
    pattern_kelas_no_colon = re.compile(rf"^({KATA_PATTERN})\s*\(([^)]+)\)\s+(.+)$")
    pattern_no_kelas = re.compile(rf"^({KATA_PATTERN})\s*:\s*(.+)$")

    for m in matches:
        text = re.sub(r"<[^>]+>", "", m).strip()
        if not text or len(text) > 500:
            continue
        if text.startswith(nav_items):
            continue

        # Handle multiple entries per <li> (split by \n dan ;)
        # Pattern: "kata1 (kelas): arti1; kata2 (kelas): arti2"
        # Split by ; kalau ada (K) setelahnya, untuk entries multi-krama
        sub_entries = []
        for s in text.split("\n"):
            s = s.strip()
            if not s:
                continue
            # Cek apakah ada ; dengan (K) atau (kelas) setelahnya (multi-entry)
            # Mis. "antuk (t.k.) dapat; pikantuk (K): mendapatkan"
            # Simple split: split by " ; " kalau ada (K) atau (t.X) di belakang
            if ";" in s and re.search(r';\s*[a-zA-Z]+\s*\(', s):
                # Multi-entry, split by ;
                parts = re.split(r'\s*;\s*(?=[a-zA-Z])', s)
                sub_entries.extend([p.strip() for p in parts if p.strip()])
            else:
                sub_entries.append(s)
        
        for sub in sub_entries:
            if len(sub) > 300:
                continue
            # Strip "Templat:" prefix di kelas
            sub_clean = sub.replace("Templat:", "").replace("}}", "").replace("{{", "")

            # Try patterns berurutan (paling spesifik dulu)
            # 1. kata (K) (kelas): arti  — krama + kelas
            match = pattern_k_kelas.match(sub_clean)
            if match:
                kata = match.group(1).strip()
                kelas_raw = match.group(2).strip()
                arti = match.group(3).strip()
                is_krama = True
            else:
                # 2. kata (kelas) (K): arti  — kelas + krama
                match = pattern_kelas_k.match(sub_clean)
                if match:
                    kata = match.group(1).strip()
                    kelas_raw = match.group(2).strip()
                    arti = match.group(3).strip()
                    is_krama = True
                else:
                    # 3. kata (kelas): arti  — format standar
                    match = pattern_kelas.match(sub_clean)
                    if match:
                        kata = match.group(1).strip()
                        kelas_raw = match.group(2).strip()
                        arti = match.group(3).strip()
                        is_krama = kelas_raw == "K"
                    else:
                        # 4. kata (kelas) arti  — tanpa colon
                        match = pattern_kelas_no_colon.match(sub_clean)
                        if match:
                            kata = match.group(1).strip()
                            kelas_raw = match.group(2).strip()
                            arti = match.group(3).strip()
                            is_krama = kelas_raw == "K"
                        else:
                            # 5. kata: arti  — tanpa kelas
                            match = pattern_no_kelas.match(sub_clean)
                            if match:
                                kata = match.group(1).strip()
                                kelas_raw = ""
                                arti = match.group(2).strip()
                                is_krama = False
                            else:
                                # 6. Pattern khusus typo parah:
                                # - "kata (t.a.: arti" (kurung tutup ilang)
                                # - "kata (t.s.)) arti" (kurung tutup dobel)
                                # - "kata t.s.): arti" (kurung buka ilang)
                                match = pattern_broken_paren.match(sub_clean) or \
                                        pattern_no_open_paren.match(sub_clean)
                                if match:
                                    kata = match.group(1).strip()
                                    kelas_raw = match.group(2).strip()
                                    arti = match.group(3).strip().rstrip(")]")
                                    is_krama = kelas_raw == "K"
                                else:
                                    # 7. Pattern bracket rusak: "[[kata](t.k.)]: arti"
                                    match = pattern_bracket_rusak.match(sub_clean)
                                    if match:
                                        kata = match.group(1).strip().strip("[]")
                                        kelas_raw = match.group(2).strip()
                                        arti = match.group(3).strip()
                                        is_krama = kelas_raw == "K"
                                    else:
                                        # 8. Pattern arti di kurung: "kata (keterangan)"
                                        # Mis. "bunga (uang)" → kata=bunga, arti=uang
                                        match = pattern_paren_arti_only.match(sub_clean)
                                        if match:
                                            kata = match.group(1).strip()
                                            paren = match.group(2).strip()
                                            extra = match.group(3).strip()
                                            kelas_raw = ""
                                            arti = paren
                                            if extra:
                                                arti = f"{paren}; {extra}"
                                            is_krama = False
                                        else:
                                            skipped_count += 1
                                            continue

            # Normalize kelas (handle typo wiki)
            kelas = normalize_kelas(kelas_raw) if kelas_raw else ""

            # Validate kelas (kalau ada)
            # JANGAN skip entries kalau kelas tidak valid — itu typo wiki,
            # entries-nya (ngoko + arti) tetap valid. Pakai kelas='tsb' (tidak standar).
            if kelas and kelas not in valid_kelas:
                kelas = "tsb"  # fallback ke tsb, jangan skip entries

            # Skip kalau kata kosong atau arti kosong
            if not kata or not arti:
                skipped_count += 1
                continue

            # Strip [contoh] dari arti (bukan skip, cuma bersihkan)
            # Mis. 'memberi [eg. atur pambagya: memberi sambutan]' → 'memberi'
            arti = re.sub(r"\s*\[[^\]]*\]\s*", " ", arti).strip()

            parsed.append({
                "ngoko": kata.lower(),
                "arti": arti,
                "kelas": kelas,
                "kelas_nama": valid_kelas.get(kelas, "krama" if is_krama else "tidak standar"),
                "is_krama": is_krama,
            })

    print(f"✓ Parsed: {len(parsed)} entries")
    print(f"  Krama (K): {sum(1 for p in parsed if p['is_krama'])}")
    print(f"  Skipped: {skipped_count}")

    # Build legend (11 kelas kata + K)
    legend = {
        "t.a.": "tembung aran (kata benda)",
        "t.k.": "tembung kriya (kata kerja)",
        "t.s.": "tembung sipat (kata sifat)",
        "t.kr.": "tembung katrangan (kata keadaan)",
        "t.pw.": "tembung panguwuh (kata seru)",
        "t.pr.": "tembung pangarep (kata depan)",
        "t.py.": "tembung panyambung (kata sambung)",
        "t.g.": "tembung ganti (kata ganti)",
        "t.sd.": "tembung sandhangan (kata sandang)",
        "t.w.": "tembung wilangan (kata bilangan)",
        "K": "krama",
    }
    return parsed, legend


def main():
    html = fetch_html()
    entries, legend = parse_entries(html)

    # Stats per kelas
    from collections import Counter
    kelas_dist = Counter(p["kelas"] for p in entries)
    print("\nDistribusi kelas kata:")
    for k, c in kelas_dist.most_common():
        print(f"  {k:8}: {c}")

    # Sample
    print(f"\nSample 20 entries:")
    for p in entries[:20]:
        is_k = " [K]" if p["is_krama"] else ""
        print(f"  {p['ngoko']:25} ({p['kelas']:8}){is_k} → {p['arti']!r}")

    # Save dengan legend di metadata
    output = {
        "metadata": {
            "version": "1.0",
            "source": "id.wiktionary.org/wiki/Lampiran:Kamus_bahasa_Jawa_–_bahasa_Indonesia",
            "description": "Lampiran Kamus bahasa Jawa – bahasa Indonesia (2724 kata)",
            "entries": len(entries),
            "kelas_breakdown": dict(kelas_dist),
            "kelas_legend": legend,  # 11 kelas kata (tembung aran, kriya, dst.)
        },
        "words": entries,
    }
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    print(f"\n✓ Save: {OUT} ({len(entries)} entries)")
    if legend:
        print(f"✓ Legend kelas kata (11 entries) — disimpan di metadata.kelas_legend:")
        for k, v in legend.items():
            print(f"    {k}: {v}")


if __name__ == "__main__":
    main()
