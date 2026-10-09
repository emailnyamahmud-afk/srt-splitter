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
        "t.a.": "kata benda",
        "t.k.": "kata kerja",
        "t.s.": "kata sifat",
        "t.kr.": "kata keadaan",
        "t.pw.": "kata seru",
        "t.pr.": "kata depan",
        "t.py.": "kata sambung",
        "t.g.": "kata ganti",
        "t.sd.": "kata sandang",
        "t.w.": "kata bilangan",
        "K": "krama",
        "tsb": "tidak standar",
        # Alias typo yang sering muncul di wiki
        "t.a": "kata benda",  # tanpa titik akhir
        "t.k": "kata kerja",
        "t.s": "kata sifat",
        "t.kr": "kata keadaan",
        "t.pw": "kata seru",
        "t.pr": "kata depan",
        "t.py": "kata sambung",
        "t.g": "kata ganti",
        "t.sd": "kata sandang",
        "t.w": "kata bilangan",
        "tk.": "kata kerja",  # typo
        "ta, ts": "kata benda+sifat",  # multi-kelas
        "ta": "kata benda",
        "ts": "kata sifat",
        "t.pb": "kata banding",  # tidak standar tapi ada di wiki
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

    # Patterns: 1. (kelas) (K): arti  2. (kelas): arti  3. tanpa kelas: arti
    pattern_kelas_k = re.compile(
        r"^([a-zA-ZĕĕêêèéÉíàáâãäåæçìíîïðñòóôõöøùúûüýþÿ'\-\.\s]+?)\s*\(([^)]+)\)\s*\(K\)\s*:\s*(.+)$"
    )
    pattern_kelas = re.compile(
        r"^([a-zA-ZĕĕêêèéÉíàáâãäåæçìíîïðñòóôõöøùúûüýþÿ'\-\.\s]+?)\s*\(([^)]+)\)\s*:\s*(.+)$"
    )
    pattern_no_kelas = re.compile(
        r"^([a-zA-ZĕĕêêèéÉíàáâãäåæçìíîïðñòóôõöøùúûüýþÿ'\-\.\s]+?)\s*:\s*(.+)$"
    )

    for m in matches:
        text = re.sub(r"<[^>]+>", "", m).strip()
        if not text or len(text) > 500:
            continue
        if text.startswith(nav_items):
            continue

        # Handle multiple entries per <li> (split by \n)
        sub_entries = [s.strip() for s in text.split("\n") if s.strip()]
        for sub in sub_entries:
            if len(sub) > 300:
                continue
            # Strip "Templat:" prefix di kelas
            sub_clean = sub.replace("Templat:", "").replace("}}", "").replace("{{", "")

            # Try pattern 1: "kata (kelas) (K): arti"
            match = pattern_kelas_k.match(sub_clean)
            if match:
                kata = match.group(1).strip()
                kelas_raw = match.group(2).strip()
                arti = match.group(3).strip()
                is_krama = True
            else:
                # Try pattern 2: "kata (kelas): arti"
                match = pattern_kelas.match(sub_clean)
                if match:
                    kata = match.group(1).strip()
                    kelas_raw = match.group(2).strip()
                    arti = match.group(3).strip()
                    is_krama = kelas_raw == "K"
                else:
                    # Try pattern 3: "kata: arti" (tanpa kelas)
                    match = pattern_no_kelas.match(sub_clean)
                    if match:
                        kata = match.group(1).strip()
                        kelas_raw = ""
                        arti = match.group(2).strip()
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
    return parsed


def main():
    html = fetch_html()
    entries = parse_entries(html)

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

    # Save
    output = {
        "metadata": {
            "version": "1.0",
            "source": "id.wiktionary.org/wiki/Lampiran:Kamus_bahasa_Jawa_–_bahasa_Indonesia",
            "description": "Lampiran Kamus bahasa Jawa – bahasa Indonesia (2724 kata)",
            "entries": len(entries),
            "kelas_breakdown": dict(kelas_dist),
        },
        "words": entries,
    }
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    print(f"\n✓ Save: {OUT} ({len(entries)} entries)")


if __name__ == "__main__":
    main()
