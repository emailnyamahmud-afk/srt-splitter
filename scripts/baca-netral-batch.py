#!/usr/bin/env python3
"""
baca-netral-batch.py — Baca entries NETRAL per batch, isi ngoko/krama/indo manual.

User: 'AI bisa naca manual? misal per batch, dimulai dari 50 entry/batch.
parsing gak ada gunanya, karena json sendiri belum jelas definisi, word itu netral,
tak terdefinisi apakah ngoko atau krama.
baca netral, jika tau ngoko, maka masukan ngoko, jika tau krama masukan ke krama,
jika tau terjemahan, maka tulis indo. itu dulu.
saya kerjakan candidate yg sudah ada pasangan indo-ngoko-krama,
ai kerjakan yg netral'

Strategy:
- Baca entries NETRAL (word terisi, ngoko+krama+indo kosong) per batch 50
- Untuk tiap entry:
  1. Baca keterangan jv wiktionary (Jawa-Indonesia)
  2. Ekstrak terjemahan Indonesia (kalau ada di keterangan)
  3. Cek word vs paired entries lain — kalau word muncul sebagai ngoko di entry lain → isi ngoko
     Kalau sebagai krama → isi krama
  4. Tentukan register (ngoko/krama) berdasarkan heuristic (akhiran, keterangan)
- Save hasil ke JSON baru + log changes

R-38: AI baca manual, per batch. Parsing tolol gak guna kalau definisi belum jelas.

Usage:
  python3 baca-netral-batch.py --batch 1       # kerjakan batch 1 (50 entries pertama)
  python3 baca-netral-batch.py --batch 2       # batch 2 (entries 51-100)
  python3 baca-netral-batch.py --batch 1 --apply  # eksekusi
  python3 baca-netral-batch.py --kamus path
"""

import os
import sys
import json
import argparse
import re
from pathlib import Path
from collections import defaultdict


def load_json(path):
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def save_json(path, data):
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def extract_indo_from_keterangan(keterangan):
    """Ekstrak terjemahan Indonesia dari keterangan jv wiktionary.

    Format jv wiktionary:
    '# arti jawa\n#: kalimat jawa\n#:: terjemahan Indonesia.\n'
    atau
    '# arti jawa\n# arti jawa lain\narti jawa\n'

    Strategy:
    1. Cari baris '#::' atau '::' → Indonesia translation
    2. Kalau ada kalimat Indonesia di keterangan, ambil
    3. Kalau hanya Jawa (tidak ada Indonesia), return None
    """
    if not keterangan:
        return None
    # Split by lines
    lines = keterangan.split('\n')
    # Pattern 1: #:: atau :: ( Indonesia translation after example)
    indo_translations = []
    for i, line in enumerate(lines):
        line = line.strip()
        if line.startswith('#::') or line.startswith('::'):
            # Indonesia translation
            text = line.lstrip('#:').strip()
            if text and not _is_jawa(text):
                indo_translations.append(text)
    if indo_translations:
        return '; '.join(indo_translations[:3])  # max 3 translations

    # Pattern 2: Tidak ada #:: — cek apakah ada kata Indonesia di keterangan
    # Hmm sulit tentukan. Skip kalau hanya Jawa.
    return None


def _is_jawa(text):
    """Heuristic: cek apakah text kemungkinan Jawa (bukan Indonesia).
    Indikator Jawa:
    - Ada diacritic jv (é, è, ê, ṇ, ḍ, ṭ, ḍh, ṣ)
    - Ada kata Jawa umum: ing, kang, sing, ora, ana, iku, iki, kuwi, banjur, lan, etc.
    """
    if not text:
        return False
    jawa_markers = ['ing ', 'kang ', 'sing ', 'ora ', 'ana ', 'iku ', 'iki ', 'kuwi ',
                    'banjur ', 'lan ', 'wis ', 'arep ', 'meh ', 'kanggo ', 'marang ',
                    'saka ', 'nanging ', 'amarga ', 'bisa ', 'kedah ', 'becik ',
                    'bakal ', 'sajroning ', 'satunggal', 'sakabat ', 'sedhih',
                    'éndah', 'ayu', 'bagus', 'umuk', 'kumingsun', 'lumpat',
                    'suara', 'perintah', 'langgeng', 'lestari', 'jaman',
                    'suwé', 'taun', 'prabot', 'piranti', 'lapak', 'bebakaling',
                    'omah', 'kreteg', 'landhesaning', 'ditugel', 'guluné',
                    'priyayi', 'hawa', 'nepsu', 'berkah', 'donga',
                    'anyar', 'enom', 'anèh', 'gumunaké',
                    'niyat', 'sediya', 'rukun', 'rujuk', 'pedhang',
                    'ginaran', 'landhéyan', 'gegaman',
                    'pangrasa', 'murka', 'éndah', 'pakurmatan', 'pangaji-aji',
                    'manuh', 'lumrah', 'carakan', 'Arab',
                    'daging', 'dibumboni', 'digaringaké', 'disuwir',
                    'tukang', 'tebas', 'rokok',
                    'ambaknéya', 'dupèh',
                    'putih', 'kuning', 'campur', 'endhog',
                    'sumorot', 'mawa', 'cahya',
                    'muncrat-muncrat', 'mancur-mancur',
                    'bubuk', 'rabuk',
                    'pirangbara',
                    'adawiyah', 'adaniyah',
                    'bayu', 'gedhé', 'dalan', 'getih', 'gulu',
                    'asor', 'nistha',
                    'pangaji-aji', 'kurmat',
                    'tatacara', 'kelumrah', 'wiwit', 'biyèn', 'mula', 'kalumrahan',
                    'pandonga', 'pamuji', 'pakurmatan', 'bebukaning', 'layang',
                    'nggegirisi', 'banget', 'keluwih-luwih',
                    'bendungan',
                    'gampang', 'ketemuné', 'golèk-golèkané', 'kerep', 'kesrambah',
                    'caket', 'cedhak',
                    'tanpa', 'karibedan',
                    'adhi',
                    'nanging', 'meksa',
                    'patrap', 'cara', 'adhuh',
                    'irig', 'dianggo', 'golèk', 'iwak',
                    'pasambat', 'lara', 'gumun',
                    'édhum', 'éyub',
                    'usel-uselan', 'arep', 'lelakèn', 'kéwan',
                    'mari', 'sedhih', 'lara', 'susah',
                    'sandhangan', 'becik',
                    'ngendel-endelaké', 'enggoné', 'rosa', 'kuwat', 'digdaya', 'kuwasa',
                    'kapinteraké', 'kaluwihané']
    text_lower = text.lower()
    # Cek diacritic jv
    if re.search(r'[éèêṇḍṭḥśṣ]', text):
        return True
    # Cek jawa markers
    for marker in jawa_markers:
        if marker in text_lower:
            return True
    return False


def extract_indo_smart(keterangan):
    """Ekstrak Indonesia lebih smart. Cek apakah ada terjemahan Indonesia eksplisit.

    Jv wiktionary sering punya format:
    '# arti jawa\narti jawa\narti jawa | Terjemahan Indonesia | Dari, dari .'
    atau
    '#:: Indonesia translation after example'
    atau
    'arti jawa\narti jawa | Lihat .\n#indonesia\n*reconstructed'
    """
    if not keterangan:
        return None

    # Pattern 1: #:: Indonesia (definitely Indonesia, post-example)
    indo_from_examples = []
    lines = keterangan.split('\n')
    for line in lines:
        line = line.strip()
        if line.startswith('#::') or line.startswith('::'):
            text = line.lstrip('#:').strip()
            if text and not _is_jawa(text):
                indo_from_examples.append(text)
    if indo_from_examples:
        return '; '.join(indo_from_examples[:3])

    # Pattern 2: Cek bagian setelah '|' (sering ada Indonesia explanation)
    # Jawa | Indonesia | Lihat .\n#indonesia
    parts = keterangan.split('|')
    if len(parts) > 1:
        # Cek part-part yg bukan Jawa
        for part in parts:
            part = part.strip()
            # Buang 'Lihat .' dan 'Dari, dari .' dan '#...'
            cleaned = re.sub(r'Lihat \.|Dari,? dari \.?|#\w+', '', part).strip()
            if cleaned and not _is_jawa(cleaned) and len(cleaned) > 3:
                return cleaned[:80]

    # Pattern 3: Cek baris 'arti jawa\narti jawa\narti jawa' — semua Jawa, no Indonesia
    # Tidak bisa ekstrak Indonesia. Return None.
    return None


def detect_register(word, paired_idx):
    """Deteksi apakah word = ngoko atau krama berdasarkan paired entries lain.

    paired_idx = {
      'ngoko': {token_lower: set of entry_ids (yg sudah paired)},
      'krama': {token_lower: set of entry_ids},
    }

    Return: 'ngoko', 'krama', atau None (tidak ketahui)
    """
    if not word:
        return None
    word_lower = word.lower().strip()
    # Cek exact match di word field (bukan tokenized — word mungkin multi-token)
    # Tokenize word (split comma)
    tokens = [t.strip().lower() for t in word.split(',') if t.strip()]
    if not tokens:
        return None

    # Cek token pertama
    primary = tokens[0]
    if primary in paired_idx['ngoko']:
        return 'ngoko'
    if primary in paired_idx['krama']:
        return 'krama'

    # Heuristic berdasarkan akhiran kata Jawa krama:
    # - Akhiran -en, -an, -ipun, -ipun → sering krama
    # - Akhiran -a, -e, -i → bisa dua-duanya (skip, biar user tentukan)
    # - Kata serapan Arab/Sanskrit (Abadi, Abimana, Adigang, dll) → sering krama (krama inggil)
    if len(primary) > 3:
        if primary.endswith(('en', 'an', 'ipun', 'ipun', 'in', 'iken')):
            return 'krama'
    return None


def build_paired_idx(words):
    """Build index kata Jawa yg sudah paired (untuk register detection)."""
    idx = {'ngoko': defaultdict(set), 'krama': defaultdict(set)}
    for w in words:
        ngoko = (w.get('ngoko') or '').strip()
        krama = (w.get('krama') or '').strip()
        if ngoko:
            for tok in ngoko.split(','):
                tok = tok.strip().lower()
                if tok and len(tok) > 1:
                    idx['ngoko'][tok].add(w.get('entry_id'))
        if krama:
            for tok in krama.split(','):
                tok = tok.strip().lower()
                if tok and len(tok) > 1:
                    idx['krama'][tok].add(w.get('entry_id'))
    return idx


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--batch', type=int, default=1, help='Batch number (50 entries per batch)')
    parser.add_argument('--apply', action='store_true', help='Save changes')
    parser.add_argument('--kamus', default=None)
    args = parser.parse_args()

    # Cari kamus
    kamus_paths = [
        args.kamus,
        Path.home() / 'Dubbing' / 'kamus_unified_draft.json',
        Path(__file__).parent / 'kamus_unified_draft.json',
    ]
    kamus_path = None
    for p in kamus_paths:
        if p and Path(p).exists():
            kamus_path = Path(p)
            break
    if not kamus_path:
        print('❌ kamus_unified_draft.json tidak ditemukan.')
        sys.exit(1)

    print(f'📁 Kamus: {kamus_path}')
    print(f'📊 Batch: {args.batch} (entries {(args.batch-1)*50+1} s/d {args.batch*50})')
    print()

    kamus = load_json(kamus_path)
    words = kamus['words']

    # Identifikasi entries NETRAL
    netral_entries = [(i, w) for i, w in enumerate(words)
        if (w.get('word') or '').strip()
        and not (w.get('ngoko') or '').strip()
        and not (w.get('krama') or '').strip()
        and not (w.get('indo') or '').strip()]

    print(f'Total NETRAL: {len(netral_entries):,}')
    print()

    # Build paired_idx untuk register detection
    paired_idx = build_paired_idx(words)
    print(f'Paired ngoko tokens: {sum(len(v) for v in paired_idx["ngoko"].values()):,}')
    print(f'Paired krama tokens: {sum(len(v) for v in paired_idx["krama"].values()):,}')
    print()

    # Batch slice
    start = (args.batch - 1) * 50
    end = start + 50
    batch = netral_entries[start:end]

    print(f'═' * 60)
    print(f'  BATCH {args.batch}: {len(batch)} entries')
    print(f'═' * 60)
    print()

    # Process tiap entry
    changes = []
    for orig_idx, w in batch:
        word = (w.get('word') or '').strip()
        keterangan = (w.get('keterangan') or '').strip()
        eid = w.get('entry_id')

        # Step 1: Ekstrak indo dari keterangan
        indo = extract_indo_smart(keterangan)
        # Step 2: Deteksi register (ngoko/krama)
        register = detect_register(word, paired_idx)

        # Build change
        change = {
            'entry_id': eid,
            'word': word,
            'indo_extracted': indo,
            'register_detected': register,
            'keterangan_preview': keterangan[:80] if keterangan else '',
        }
        changes.append(change)

        # Apply (in-memory)
        if args.apply:
            if indo:
                w['indo'] = indo
            if register == 'ngoko':
                # Move word → ngoko
                w['ngoko'] = word
                w['word'] = ''  # R-21: paired → word kosong
            elif register == 'krama':
                w['krama'] = word
                w['word'] = ''

    # Print summary
    print(f"{'#':>5} {'word':<25} {'register':<10} {'indo':<40}")
    print(f"{'─'*5} {'─'*25} {'─'*10} {'─'*40}")
    for c in changes:
        word_short = c['word'][:25]
        reg = c['register_detected'] or '-'
        indo = (c['indo_extracted'] or '-')[:40]
        print(f"#{c['entry_id']:>4} {word_short:<25} {reg:<10} {indo:<40}")
    print()

    # Stats
    n_indo = sum(1 for c in changes if c['indo_extracted'])
    n_ngoko = sum(1 for c in changes if c['register_detected'] == 'ngoko')
    n_krama = sum(1 for c in changes if c['register_detected'] == 'krama')
    print(f'Stats batch {args.batch}:')
    print(f'  indo extracted: {n_indo}/50')
    print(f'  register ngoko: {n_ngoko}/50')
    print(f'  register krama: {n_krama}/50')
    print(f'  no change (word + no indo + no register): {50 - n_indo - n_ngoko - n_krama}/50')
    print()

    if not args.apply:
        print('🔍 DRY-RUN — tidak ada perubahan.')
        print('   Untuk eksekusi: python3 baca-netral-batch.py --batch 1 --apply')
        return

    # Save
    save_json(kamus_path, kamus)
    print(f'✅ Saved: {kamus_path}')
    print(f'   {n_indo} entries di-isi indo')
    print(f'   {n_ngoko} entries di-isi ngoko (word → ngoko, word kosong)')
    print(f'   {n_krama} entries di-isi krama (word → krama, word kosong)')


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print('\n\n⏹ Dibatalkan.')
        sys.exit(130)
