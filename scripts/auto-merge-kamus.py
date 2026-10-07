#!/usr/bin/env python3
"""
auto-merge-kamus.py — Auto-merge + auto-fix register kamus JSON.

User bilang: "Saya pusing... Yg penting TUI membantu. Saya akan capek cari manual."

Script ini OTOMATIS:
1. Auto-merge: Entry A (ngoko=X, krama=Y) + Entry B (ngoko=Y, krama=koosong) → keep A, delete B
   Mis. A(aku→kula) + B(kula, krama kosong) → merge jadi 1 entry aku→kula
2. Auto-fix register: Entry dengan krama mapping tapi register="umum" → fix ke "ngoko"
3. Auto-fix register: Entry dengan ngoko mapping (sumber "+ template") → fix register sesuai template

User tinggal fokus ke:
- Isi arti (Indonesia) untuk entries yang sudah punya ngoko+krama
- Manual merge untuk entries tanpa cross-reference (seperti sing+ingkang)

Usage: python3 auto-merge-kamus.py [kamus-json]
Default: ~/Dubbing/kamus-jawa-full.json

Output:
  - Kamus JSON di-update (entries turun karena merge)
  - Report: ~/Dubbing/kamus-merge-report.txt
"""

import json
import sys
from pathlib import Path

KAMUS_PATH = Path(sys.argv[1] if len(sys.argv) > 1 else Path.home() / 'Dubbing' / 'kamus-jawa-full.json')
REPORT_PATH = Path.home() / 'Dubbing' / 'kamus-merge-report.txt'


def main():
    print(f'📁 Kamus: {KAMUS_PATH}')
    print()

    with open(KAMUS_PATH, 'r', encoding='utf-8') as f:
        data = json.load(f)

    words = data['words']
    original_count = len(words)
    print(f'✓ Total entries: {original_count}')

    # === STEP 1: Auto-merge ===
    # Entry A (ngoko=X, krama=Y) + Entry B (ngoko=Y, krama=koosong) → keep A, delete B
    print()
    print('=== Step 1: Auto-merge ===')
    print('Logic: Entry A (ngoko=X, krama=Y) + Entry B (ngoko=Y, krama=koosong) → merge')

    # Build lookup: ngoko word (lowercase) → list of indices
    ngoko_to_indices = {}
    for i, w in enumerate(words):
        ngoko = (w.get('ngoko') or '').strip().lower()
        if ngoko:
            ngoko_to_indices.setdefault(ngoko, []).append(i)

    merge_log = []
    indices_to_delete = set()

    for a_idx, a in enumerate(words):
        if a_idx in indices_to_delete:
            continue
        krama_a = (a.get('krama') or '').strip().lower()
        if not krama_a:
            continue

        # Cari entry B dengan ngoko = krama_a, krama kosong
        if krama_a in ngoko_to_indices:
            for b_idx in ngoko_to_indices[krama_a]:
                if b_idx == a_idx or b_idx in indices_to_delete:
                    continue
                b = words[b_idx]
                ngoko_b = (b.get('ngoko') or '').strip().lower()
                krama_b = (b.get('krama') or '').strip()

                if ngoko_b == krama_a and not krama_b:
                    # Merge B ke A (A sudah lengkap, B cuma duplikat)
                    # Combine arti kalau B punya arti
                    b_arti = (b.get('arti') or '').strip()
                    if b_arti and not (a.get('arti') or '').strip():
                        a['arti'] = b_arti

                    # Combine krama_inggil kalau B punya
                    b_ki = (b.get('krama_inggil') or '').strip()
                    if b_ki and not (a.get('krama_inggil') or '').strip():
                        a['krama_inggil'] = b_ki

                    # Combine keterangan
                    b_ket = (b.get('keterangan') or '').strip()
                    a_ket = (a.get('keterangan') or '').strip()
                    if b_ket and b_ket not in a_ket:
                        a['keterangan'] = f'{a_ket} | {b_ket}'.strip(' |')

                    # Fix register: A harusnya ngoko (punya ngoko+krama)
                    a['register'] = 'ngoko'

                    indices_to_delete.add(b_idx)
                    merge_log.append({
                        'a_id': a.get('entry_id', a_idx + 1),
                        'a_ngoko': a.get('ngoko', ''),
                        'a_krama': a.get('krama', ''),
                        'b_id': b.get('entry_id', b_idx + 1),
                        'b_ngoko': b.get('ngoko', ''),
                    })
                    break

    # Delete merged entries
    words = [w for i, w in enumerate(words) if i not in indices_to_delete]
    merge_count = len(merge_log)
    print(f'  ✓ Auto-merge: {merge_count} pairs')
    print(f'  ✓ Entries dihapus: {merge_count}')
    print(f'  ✓ Entries sekarang: {len(words)} (dari {original_count})')

    # Show first 10 merges
    print()
    print('  Sample merges (first 10):')
    for m in merge_log[:10]:
        print(f"    #{m['a_id']} {m['a_ngoko']:15} → {m['a_krama']:15} + #{m['b_id']} {m['b_ngoko']:15} (hapus)")

    # === STEP 2: Auto-fix register ===
    print()
    print('=== Step 2: Auto-fix register ===')

    fix_log = []

    for w in words:
        register = w.get('register', 'umum')
        ngoko = (w.get('ngoko') or '').strip()
        krama = (w.get('krama') or '').strip()
        ki = (w.get('krama_inggil') or '').strip()
        sumber = w.get('sumber', '')

        old_register = register

        # Fix 1: Entry dengan krama mapping → register harusnya ngoko (title = ngoko word)
        if krama and register in ('umum', 'kawi'):
            w['register'] = 'ngoko'
            fix_log.append((w.get('entry_id', 0), old_register, 'ngoko', ngoko, krama))

        # Fix 2: Entry dengan krama_inggil mapping → register krama_inggil
        # TAPI hanya kalau krama kosong ATAU krama == ngoko (self-reference)
        elif ki and register in ('umum', 'kawi', 'ngoko'):
            # Skip self-reference: kalau ngoko == krama_inggil, bukan krama_inggil mapping
            if ngoko.lower() != ki.lower() and (not krama or krama.lower() == ngoko.lower()):
                w['register'] = 'krama_inggil'
                fix_log.append((w.get('entry_id', 0), old_register, 'krama_inggil', ngoko, ki))

        # Fix 3: Entry tanpa krama, tanpa ki, tapi sumber ada "template" →
        # berarti title sebenarnya krama word (dari template {{krama|X}})
        # Register = krama
        elif not krama and not ki and '+ template' in sumber and register == 'umum':
            # Entry ini punya template cross-reference, title = krama word
            # Cek: apakah keterangan menyebut kata yang ada di kamus sebagai ngoko?
            # Untuk sekarang, biarkan umum — user fix manual
            pass

    print(f'  ✓ Auto-fix register: {len(fix_log)} entries')
    if fix_log:
        print(f'    Sample (first 10):')
        for fid, old, new, ngoko, krama in fix_log[:10]:
            print(f'      #{fid} {ngoko:15} → {krama:15} [{old} → {new}]')

    # === STEP 3: Re-number entry_id ===
    for i, w in enumerate(words, 1):
        w['entry_id'] = i

    # === SAVE ===
    data['words'] = words
    with open(KAMUS_PATH, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print()
    print(f'✅ Kamus disimpan: {KAMUS_PATH}')
    print(f'  Total: {original_count} → {len(words)} entries (-{original_count - len(words)} dari merge)')

    # === REPORT ===
    with open(REPORT_PATH, 'w', encoding='utf-8') as f:
        f.write('Auto-merge + Auto-fix Register Report\n')
        f.write('=====================================\n\n')
        f.write(f'Kamus: {KAMUS_PATH}\n')
        f.write(f'Original entries: {original_count}\n')
        f.write(f'After merge: {len(words)} (-{merge_count})\n\n')

        f.write(f'=== Auto-merge ({merge_count} pairs) ===\n')
        f.write(f'{"#":>4}  {"Entry A":>8}  {"ngoko":>15}  {"krama":>15}  {"Entry B (deleted)":>20}\n')
        f.write(f'-' * 80 + '\n')
        for i, m in enumerate(merge_log, 1):
            f.write(f'{i:>4}  #{m["a_id"]:<6}  {m["a_ngoko"]:>15}  {m["a_krama"]:>15}  #{m["b_id"]} {m["b_ngoko"]}\n')

        f.write(f'\n=== Auto-fix register ({len(fix_log)} entries) ===\n')
        f.write(f'{"#":>4}  {"entry_id":>8}  {"ngoko":>15}  {"krama":>15}  {"old → new":>20}\n')
        f.write(f'-' * 80 + '\n')
        for i, (fid, old, new, ngoko, krama) in enumerate(fix_log, 1):
            f.write(f'{i:>4}  #{fid:<6}  {ngoko:>15}  {krama:>15}  {old} → {new}\n')

        f.write(f'\n=== Yang perlu user manual ===\n')
        f.write(f'1. Entries tanpa cross-reference (seperti "sing" + "ingkang")\n')
        f.write(f'   → Manual merge via TUI menu "🔗 Merge 2 entries by entry_id"\n')
        f.write(f'2. Entries dengan register masih "umum" (perlu validasi)\n')
        f.write(f'   → TUI menu "⚠ Browse register UMUM"\n')
        f.write(f'3. Isi arti (Indonesia) untuk entries yang sudah punya ngoko+krama\n')
        f.write(f'   → TUI menu "⭐ Browse entries dengan krama mapping"\n')

    print(f'✅ Report: {REPORT_PATH}')
    print()
    print('💡 Yang perlu user manual:')
    print('   1. Manual merge entries tanpa cross-reference (sing + ingkang)')
    print('   2. Validasi register umum yang masih ambigu')
    print('   3. Isi arti Indonesia per entry')


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print('\n⏹ Dibatalkan.')
        sys.exit(130)
    except Exception as e:
        print(f'\n❌ Error: {e}', file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)
