#!/usr/bin/env python3
"""
neutralize-kamus-draft.py — Netralisasi kamus-jawa-draft.json per user 9 Okt 2026

User: 'DATA kamus draf json sudah rusak, dengan mendefiniskan ngoko - padahal belum diketahui.
bersihkan data kamus draft yg belum berpasangan jadi word umum (netral), saya dan ai belum tau
ini ngoko atau bukan. setidaknya data jujur.'

User: 'pasca data json jadi netral, maka referensi ke raw = tidak berlaku, karena kalau raw
masih ada definisi, di next sesi AI akan halu lagi dengan parsing tolol.'

Skema baru:
  - Entries PAIRED (ngoko + krama/arti): TETAP di ngoko (sudah terdefinisi)
  - Entries NGOKO-ONLY (no krama/arti): pindah ngoko → 'word' (netral), kosongkan ngoko
  - Entries KRAMA-ONLY (no ngoko/arti): pindah krama → 'word' (netral), kosongkan krama
  - Entries ARTI-ONLY: pindah ke 'word' (jarang, 0 entries)
  - Entries KRAMA+ARTI (no ngoko): TETAP di krama (paired)
  - EMPTY entries: TETAP (R-18 jangan hapus)

PERTAHANKAN: keterangan (Jawa+Indonesia), aksara, sumber, is_lemma flag, source_count
UBAH: register → 'umum' untuk entries yang pindah ke word (netral)

Field baru: 'word' (string netral, belum terdefinisi register)

Pasca eksekusi:
  - Build script (build-kamus-bersih.py) HARUS di-disable (rename .DISABLED)
  - Kamus-draft.json = satu-satunya rujukan
  - Raw files tetap ada sebagai arsip (R-16 jangan hapus), tapi bukan rujukan

Idempotent: re-run aman (cek dulu apakah sudah punya field 'word').
"""

import json
from pathlib import Path

DRAFT = Path("/home/z/my-project/public/kamus-jawa-draft.json")


def main():
    if not DRAFT.exists():
        print(f"❌ File tidak ditemukan: {DRAFT}")
        return 1

    with open(DRAFT, "r", encoding="utf-8") as f:
        data = json.load(f)

    konseps = data["words"]
    total = len(konseps)
    print(f"Loaded: {total:,} entries dari draft v{data.get('metadata',{}).get('version','?')}")

    # Cek idempotency: kalau ada field 'word' di semua entries, sudah pernah run
    sample_word = sum(1 for k in konseps[:100] if (k.get('word','') or '').strip())
    if sample_word > 50:
        print(f"\n⚠ Sudah punya field 'word' di {sample_word}/100 sample — mungkin sudah pernah run.")
        print(f"   Untuk re-run, hapus field 'word' dulu atau skip entries yang sudah punya 'word'.")
        # Tetap lanjut, tapi skip entries yang sudah ada 'word'

    # Stats sebelum
    cat = {
        'paired_ngoko': 0,      # ngoko + krama/arti — TETAP
        'paired_krama': 0,      # krama + arti (no ngoko) — TETAP di krama
        'ngoko_only_moved': 0,  # → word
        'krama_only_moved': 0,  # → word
        'arti_only_moved': 0,   # → word
        'empty_kept': 0,        # TETAP (R-18)
        'word_already_set': 0,  # sudah punya 'word' (idempotent skip)
    }

    for i, k in enumerate(konseps):
        ng = (k.get("ngoko", "") or "").strip()
        kr = (k.get("krama", "") or "").strip()
        ar = (k.get("arti", "") or "").strip()
        existing_word = (k.get("word", "") or "").strip()

        has_ng = bool(ng)
        has_kr = bool(kr)
        has_ar = bool(ar)
        has_word = bool(existing_word)

        if has_word:
            cat['word_already_set'] += 1
            continue

        if has_ng and (has_kr or has_ar):
            # PAIRED — tetap di ngoko
            cat['paired_ngoko'] += 1
            continue

        if has_kr and has_ar and not has_ng:
            # krama + arti (no ngoko) — TETAP di krama
            cat['paired_krama'] += 1
            continue

        if not has_ng and not has_kr and not has_ar:
            # EMPTY — TETAP (R-18)
            cat['empty_kept'] += 1
            continue

        # Cases to NEUTRALIZE: pindah ke 'word'
        if has_ng and not has_kr and not has_ar:
            # ngoko-only → word
            k["word"] = ng
            k["ngoko"] = ""
            k["register"] = "umum"
            cat['ngoko_only_moved'] += 1
            continue

        if has_kr and not has_ng and not has_ar:
            # krama-only → word
            k["word"] = kr
            k["krama"] = ""
            k["register"] = "umum"
            cat['krama_only_moved'] += 1
            continue

        if has_ar and not has_ng and not has_kr:
            # arti-only → word (jarang)
            k["word"] = ar  # Hmm, arti Indonesia jadi 'word'? Aku skip ini, biarkan arti tetap
            # Actually: arti Indonesia = BUKAN kata Jawa netral. Skip, biarkan di arti.
            # Delete the word I just set
            k["word"] = ""
            cat['arti_only_moved'] += 1  # count, tapi tidak pindah
            continue

    print(f"\n=== NEUTRALIZATION STATS ===")
    for k, v in cat.items():
        print(f"  {k:<25} {v:>7,}")

    # Bump version
    old_ver = data.get("metadata", {}).get("version", "?")
    try:
        parts = old_ver.split(".")
        if len(parts) == 2 and parts[0].isdigit() and parts[1].isdigit():
            new_ver = f"{parts[0]}.{int(parts[1]) + 1}"
        else:
            new_ver = old_ver + "+neutral"
    except Exception:
        new_ver = old_ver + "+neutral"
    data.setdefault("metadata", {})["version"] = new_ver
    data["metadata"]["last_fix"] = (
        "neutralize-kamus-draft.py: entries belum berpasangan → 'word' (netral). "
        "Pasca ini: build-kamus-bersih.py DISABLED, kamus-draft.json = rujukan tunggal."
    )
    data["metadata"]["schema"] = "v3: word (netral) + ngoko + krama + arti (paired only)"

    # Save
    with open(DRAFT, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"\n✓ Saved: {DRAFT} (v{old_ver} → v{new_ver})")
    print(f"\n⚠ NEXT: rename build-kamus-bersih.py → build-kamus-bersih.py.DISABLED")
    print(f"   supaya AI next sesi tidak rebuild dari raw (yang masih punya definisi salah).")
    print(f"   Kamus-draft.json = satu-satunya rujukan.")
    return 0


if __name__ == "__main__":
    exit(main())
