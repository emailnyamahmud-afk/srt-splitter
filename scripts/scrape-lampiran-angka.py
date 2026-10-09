#!/usr/bin/env python3
"""
scrape-lampiran-angka.py — Scrape Lampiran:Nama_angka_dalam_bahasa_Jawa

Source: https://id.wiktionary.org/wiki/Lampiran:Nama_angka_dalam_bahasa_Jawa
Table 0: Satuan 1-10 (Kuna, Kawi, Krama, Ngoko)
Table 1: Belasan - Jutaan (Angka, Ngoko, Krama)

Output: /home/z/my-project/public/lampiran-angka-raw.json
"""

import urllib.request
import re
import json
from pathlib import Path

URL = "https://id.wiktionary.org/wiki/Lampiran:Nama_angka_dalam_bahasa_Jawa"
UA = "SrtSplitterBot/1.0 (https://github.com/emailnyamahmud-afk/srt-splitter; educational use)"
OUT = Path("/home/z/my-project/public/lampiran-angka-raw.json")

INDO = {
    1:"satu",2:"dua",3:"tiga",4:"empat",5:"lima",6:"enam",7:"tujuh",8:"delapan",
    9:"sembilan",10:"sepuluh",11:"sebelas",12:"dua belas",13:"tiga belas",
    14:"empat belas",15:"lima belas",16:"enam belas",17:"tujuh belas",
    18:"delapan belas",19:"sembilan belas",20:"dua puluh",21:"dua puluh satu",
    22:"dua puluh dua",23:"dua puluh tiga",24:"dua puluh empat",25:"dua puluh lima",
    26:"dua puluh enam",30:"tiga puluh",31:"tiga puluh satu",32:"tiga puluh dua",
    40:"empat puluh",41:"empat puluh satu",42:"empat puluh dua",
    50:"lima puluh",51:"lima puluh satu",52:"lima puluh dua",
    60:"enam puluh",61:"enam puluh satu",62:"enam puluh dua",
    70:"tujuh puluh",80:"delapan puluh",90:"sembilan puluh",
    100:"seratus",101:"seratus satu",102:"seratus dua",120:"seratus dua puluh",
    121:"seratus dua puluh satu",200:"dua ratus",500:"lima ratus",
    1000:"seribu",1001:"seribu satu",1002:"seribu dua",
    1500:"seribu lima ratus",1520:"seribu lima ratus dua puluh",
    1550:"seribu lima ratus lima puluh",1551:"seribu lima ratus lima puluh satu",
    2000:"dua ribu",5000:"lima ribu",10000:"sepuluh ribu",
    100000:"seratus ribu",500000:"lima ratus ribu",1000000:"satu juta",
}


def main():
    print(f"🌐 Fetching {URL}...")
    req = urllib.request.Request(URL, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as r:
        html = r.read().decode("utf-8")

    # Parse tabel
    tables = re.findall(r'<table[^>]*>(.*?)</table>', html, re.DOTALL)
    print(f"Tables found: {len(tables)}")

    entries = []

    # Table 0: Satuan 1-10
    if len(tables) >= 1:
        rows = re.findall(r'<tr[^>]*>(.*?)</tr>', tables[0], re.DOTALL)
        # Header: Bahasa, 1, 2, ..., 10
        # Rows: Kuna, Kawi, Krama, Ngoko, Ngoko(aksara)
        for row in rows:
            cells = re.findall(r'<t[dh][^>]*>(.*?)</t[dh]>', row, re.DOTALL)
            cells_clean = [re.sub(r'<[^>]+>', '', c).strip() for c in cells]
            if len(cells_clean) < 11:
                continue
            bahasa = cells_clean[0].lower()
            if bahasa in ('kuna', 'kawi', 'krama', 'ngoko'):
                for i in range(1, 11):
                    angka = i
                    word = cells_clean[i].strip()
                    if word:
                        entries.append({
                            "angka": angka,
                            "bahasa": bahasa,
                            "word": word.lower(),
                            "arti": INDO.get(angka, ""),
                        })

    # Table 1: Belasan - Jutaan
    if len(tables) >= 2:
        rows = re.findall(r'<tr[^>]*>(.*?)</tr>', tables[1], re.DOTALL)
        for row in rows:
            cells = re.findall(r'<t[dh][^>]*>(.*?)</t[dh]>', row, re.DOTALL)
            cells_clean = [re.sub(r'<[^>]+>', '', c).strip() for c in cells]
            if len(cells_clean) < 3:
                continue
            angka_str = cells_clean[0].replace('.', '').replace(',', '').strip()
            ngoko = cells_clean[1].strip()
            krama = cells_clean[2].strip()
            # Parse angka (bisa "1.000" atau "1.562.155")
            try:
                angka = int(angka_str)
            except ValueError:
                continue
            entries.append({
                "angka": angka,
                "ngoko": ngoko.lower(),
                "krama": krama.lower(),
                "arti": INDO.get(angka, ""),
            })

    print(f"Total entries: {len(entries)}")

    # Tampilkan sample
    print("\n=== Satuan (dari Table 0) ===")
    satuan = [e for e in entries if 'bahasa' in e]
    for e in satuan:
        print(f"  {e['angka']:3} {e['bahasa']:6} {e['word']:15} arti={e['arti']}")

    print("\n=== Belasan - Jutaan (dari Table 1) ===")
    belasan = [e for e in entries if 'ngoko' in e]
    for e in belasan[:30]:
        print(f"  {e['angka']:>10} ngoko={e['ngoko']:25} krama={e['krama']:30} arti={e['arti']}")

    # Save
    output = {
        "metadata": {
            "version": "1.0",
            "source": "id.wiktionary.org/wiki/Lampiran:Nama_angka_dalam_bahasa_Jawa",
            "description": "Nama angka dalam bahasa Jawa (satuan, belasan, puluhan, ratusan, ribuan, jutaan)",
            "entries": len(entries),
            "tables": {
                "table_0": "Satuan 1-10 (Kuna, Kawi, Krama, Ngoko)",
                "table_1": "Belasan - Jutaan (Angka, Ngoko, Krama)",
            },
        },
        "words": entries,
    }
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    print(f"\n✓ Save: {OUT} ({len(entries)} entries)")


if __name__ == "__main__":
    main()
