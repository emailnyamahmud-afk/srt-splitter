"""Test parser with the real SRT file."""
import sys
sys.path.insert(0, "/home/z/my-project/srt-editor-tui")
from srt_editor.parser import load_srt, serialize_srt, save_working_json, parse_srt
from pathlib import Path
import json

cues = load_srt(Path("/home/z/my-project/srt-editor-tui/test-input.srt"))
print(f"Loaded {len(cues)} cues")
print(f"First cue: id={cues[0].id} start={cues[0].start} end={cues[0].end}")
print(f"  text: {cues[0].original!r}")
print(f"Last cue: id={cues[-1].id} start={cues[-1].start} end={cues[-1].end}")
print(f"  text: {cues[-1].original!r}")

# Find cue 1728 (the "cumming" one)
for c in cues:
    if c.id == 1728:
        print(f"\nCue 1728 found: {c.original!r}")
        break

# Test round-trip
out = serialize_srt(cues)
cues2 = parse_srt(out)
print(f"\nRound-trip OK: {len(cues2)} cues (was {len(cues)})")
print(f"Round-trip cue 1728 text: {cues2[1727].original!r}")

# Save working JSON
save_working_json(cues, "test-input.srt", Path("/tmp/test-working.json"))
data = json.loads(Path("/tmp/test-working.json").read_text())
print(f"\nWorking JSON stats: {data['stats']}")
