"""Test srt-editor-tui single-file: parser, glossary, serialize. Tanpa TTY."""
import sys
import importlib.util
from pathlib import Path

sys.path.insert(0, "/home/z/my-project/scripts")

# Import module (file dengan dash di nama → pakai importlib)
spec = importlib.util.spec_from_file_location(
    "srt_editor_tui", "/home/z/my-project/scripts/srt-editor-tui.py"
)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

# Test 1: parser
print("=== Test 1: Parser ===")
src = Path("/home/z/my-project/test-sample.srt")
cues = mod.load_srt(src)
print(f"Loaded {len(cues)} cues")
assert len(cues) == 9, f"Expected 9, got {len(cues)}"
print(f"First: id={cues[0].id} start={cues[0].start} text={cues[0].original!r}")
print(f"Cue 3 (cumming): {cues[2].original!r}")
assert "cumming" in cues[2].original, "Expected 'cumming' in cue 3"

# Test 2: round-trip serialize
print("\n=== Test 2: Round-trip serialize ===")
out = mod.serialize_srt(cues)
cues2 = mod.parse_srt(out)
assert len(cues2) == 9, f"Round-trip lost cues: {len(cues2)}"
print(f"Round-trip OK: {len(cues2)} cues preserved")

# Test 3: default glossary
print("\n=== Test 3: Default glossary (19 entries) ===")
gl = mod.glossary_from_default()
print(f"Default glossary entries: {len(gl.entries)}")
assert len(gl.entries) == 19, f"Expected 19, got {len(gl.entries)}"

# Test 4: scan cues for variants
print("\n=== Test 4: Scan cues for variants ===")
matches = mod.scan_cues_for_variants(cues, gl)
print(f"Entries with hits: {len(matches)}")
for canonical, variants in matches.items():
    print(f"  {canonical}:")
    for v, cue_ids in variants.items():
        print(f"    '{v}' → cues {cue_ids}")

# Test 5: apply one entry (cumming → menarik pelatuk)
print("\n=== Test 5: Apply 'menarik pelatuk' ===")
entry = gl.by_canonical["menarik pelatuk"]
print(f"  Variants: {entry.variants}")
n_total = 0
for c in cues:
    new_text, n = entry.apply_to(c.current)
    if n > 0:
        n_total += n
        print(f"  Cue #{c.id}: '{c.original}' → '{new_text}'")
        c.current = new_text
        c.auto_fixed = True
print(f"Total replacements: {n_total}")
assert n_total >= 1
assert cues[2].current == "Teruslah menarik pelatuk"

# Test 6: apply all glossary
print("\n=== Test 6: Apply ALL glossary ===")
gl = mod.glossary_from_default()
cues = mod.load_srt(src)  # reset
total_n = 0
for entry in gl.entries:
    for c in cues:
        new, n = entry.apply_to(c.current)
        if n > 0:
            c.current = new
            c.auto_fixed = True
            total_n += n
print(f"Total replacements across all entries: {total_n}")
# Test sample punya: cumming, payung emas, ayam panah, Bulan, Aokawa, Peti mati Lin, Lin menertawakan peti mati
# Expected ~7 hits minimum
assert total_n >= 7, f"Expected ≥7 total replacements, got {total_n}"

n_auto = sum(1 for c in cues if c.auto_fixed)
print(f"  auto_fixed cues: {n_auto}")

# Verify expected replacements
assert cues[2].current == "Teruslah menarik pelatuk", f"cumming not fixed: {cues[2].current}"
assert cues[3].current == "obat luka emas", f"payung emas not fixed: {cues[3].current}"
assert cues[4].current == "panah otomatis", f"ayam panah not fixed: {cues[4].current}"
assert cues[5].current == "Mu En", f"Bulan not fixed: {cues[5].current}"
assert cues[6].current == "Wang Haochuan", f"Aokawa not fixed: {cues[6].current}"
print("  ✓ All glossary replacements verified")

# Test 7: save final SRT + working JSON
print("\n=== Test 7: Save ===")
out_path = Path("/home/z/my-project/test-sample.final.srt")
work_path = Path("/home/z/my-project/test-sample.working.json")
mod.save_srt(cues, out_path)
mod.save_working_json(cues, src.name, work_path)
print(f"  Saved: {out_path.name} ({out_path.stat().st_size} bytes)")
print(f"  Saved: {work_path.name} ({work_path.stat().st_size} bytes)")

# Verify saved SRT
saved_text = out_path.read_text()
assert "cumming" not in saved_text, "cumming still in saved file!"
assert "menarik pelatuk" in saved_text, "menarik pelatuk missing from saved file!"
print(f"  Re-parse OK: 'cumming' gone, 'menarik pelatuk' present ✓")

# Test 8: load working JSON (resume)
print("\n=== Test 8: Resume from working JSON ===")
cues_resume = mod.load_working_json(work_path)
assert len(cues_resume) == 9
n_auto_resume = sum(1 for c in cues_resume if c.auto_fixed)
print(f"  Resumed {len(cues_resume)} cues, {n_auto_resume} auto_fixed")
assert n_auto_resume == n_auto, f"Resume lost state: {n_auto_resume} vs {n_auto}"

# Test 9: revert one cue
print("\n=== Test 9: Revert ===")
cues_resume[2].current = cues_resume[2].original
cues_resume[2].auto_fixed = False
assert cues_resume[2].current == "Teruslah melakukan cumming"
assert cues_resume[2].changed == False
print(f"  Revert OK: cue 3 back to '{cues_resume[2].current}'")

# Cleanup
out_path.unlink()
work_path.unlink()
print("\n" + "=" * 60)
print("✅ ALL TESTS PASSED — srt-editor-tui.py single-file siap pakai")
print("=" * 60)
