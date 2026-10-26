"""Test glossary module end-to-end."""
import sys
sys.path.insert(0, "/home/z/my-project/srt-editor-tui")
from srt_editor.parser import load_srt
from srt_editor.glossary import load_glossary, scan_cues_for_variants, count_variants_in_cues
from pathlib import Path

cues = load_srt(Path("/home/z/my-project/srt-editor-tui/test-input.srt"))
gl = load_glossary(Path("/home/z/my-project/srt-editor-tui/sample-glossary.json"))

print(f"Loaded glossary with {len(gl.entries)} entries")
print(f"Cues to scan: {len(cues)}")

# Count matches
counts = count_variants_in_cues(cues, gl)
print("\nVariant counts per canonical:")
for canon, n in sorted(counts.items(), key=lambda x: -x[1]):
    if n > 0:
        print(f"  {canon:<25}  {n} hits")

# Detailed scan
print("\nDetailed scan (canonical -> variant -> cue IDs):")
matches = scan_cues_for_variants(cues, gl)
for canon, variants in matches.items():
    print(f"  {canon}:")
    for v, cue_ids in variants.items():
        sample = cue_ids[:3]
        more = f" +{len(cue_ids)-3} more" if len(cue_ids) > 3 else ""
        print(f"    '{v}' -> cues {sample}{more} ({len(cue_ids)} total)")

# Test applying one entry
print("\n--- Test apply one entry: 'menarik pelatuk' (fix 'cumming') ---")
entry = gl.by_canonical["menarik pelatuk"]
print(f"Entry canonical: {entry.canonical}")
print(f"Variants: {entry.variants}")
n_total = 0
for c in cues:
    new_text, n = entry.apply_to(c.current)
    if n > 0:
        n_total += n
        print(f"  Cue #{c.id}: '{c.original}' -> '{new_text}'")
        c.current = new_text
        c.auto_fixed = True
print(f"Total replacements: {n_total}")

# Test save end-to-end
from srt_editor.parser import save_srt, save_working_json
save_srt(cues, Path("/tmp/test-final.srt"))
save_working_json(cues, "test-input.srt", Path("/tmp/test-working.json"))
print("\nSaved test-final.srt and test-working.json")
import json
data = json.loads(Path("/tmp/test-working.json").read_text())
print(f"Stats: {data['stats']}")
