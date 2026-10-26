"""SRT parser & serializer.

Handles SRT <-> in-memory cue list conversion. Pure stdlib, no dependencies.
"""

from __future__ import annotations

import re
import json
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import List, Optional, Dict, Any


# Timestamp regex: 00:01:23,456 --> 00:01:25,789
TS_RE = re.compile(
    r"(\d{2}):(\d{2}):(\d{2})[,.](\d{3})\s*-->\s*(\d{2}):(\d{2}):(\d{2})[,.](\d{3})"
)


@dataclass
class Cue:
    """One subtitle cue."""
    id: int                       # original SRT index (1-based)
    start: str                    # "HH:MM:SS,mmm"
    end: str                      # "HH:MM:SS,mmm"
    original: str                 # text as loaded
    current: str = ""             # editable text (defaults to original)
    reviewed: bool = False        # user marked as reviewed
    flagged: bool = False         # user marked as flagged (problem)
    auto_fixed: bool = False      # changed by glossary apply
    note: str = ""                # optional user note

    def __post_init__(self):
        if not self.current:
            self.current = self.original

    @property
    def changed(self) -> bool:
        return self.current != self.original

    @property
    def start_ms(self) -> int:
        return _ts_to_ms(self.start)

    @property
    def end_ms(self) -> int:
        return _ts_to_ms(self.end)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def _ts_to_ms(ts: str) -> int:
    """'HH:MM:SS,mmm' -> milliseconds int."""
    h, m, s, ms = re.match(r"(\d{2}):(\d{2}):(\d{2}),(\d{3})", ts).groups()
    return int(h) * 3600000 + int(m) * 60000 + int(s) * 1000 + int(ms)


def _ms_to_ts(ms: int) -> str:
    h = ms // 3600000
    ms %= 3600000
    m = ms // 60000
    ms %= 60000
    s = ms // 1000
    ms %= 1000
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def parse_srt(text: str) -> List[Cue]:
    """Parse SRT text -> list of Cue. Tolerates BOM, CRLF, blank lines."""
    if text.startswith("\ufeff"):
        text = text.lstrip("\ufeff")
    # Normalize line endings
    text = text.replace("\r\n", "\n").replace("\r", "\n")

    # Split into cue blocks. A block starts with a number line on its own.
    blocks = re.split(r"\n\s*\n", text.strip())
    cues: List[Cue] = []
    for block in blocks:
        block = block.strip()
        if not block:
            continue
        lines = block.split("\n")
        if len(lines) < 2:
            continue
        # First line: index (sometimes missing in malformed files)
        idx = 0
        ts_line_idx = 0
        try:
            int(lines[0].strip())
            idx = int(lines[0].strip())
            ts_line_idx = 1
        except ValueError:
            # No index line; ts is on line 0
            ts_line_idx = 0

        if ts_line_idx >= len(lines):
            continue

        ts_match = TS_RE.search(lines[ts_line_idx])
        if not ts_match:
            continue

        g = ts_match.groups()
        start = f"{g[0]}:{g[1]}:{g[2]},{g[3]}"
        end = f"{g[4]}:{g[5]}:{g[6]},{g[7]}"

        text_lines = lines[ts_line_idx + 1:]
        body = "\n".join(text_lines).strip()

        cue_id = idx if idx else (len(cues) + 1)
        cues.append(Cue(
            id=cue_id,
            start=start,
            end=end,
            original=body,
            current=body,
        ))
    return cues


def serialize_srt(cues: List[Cue]) -> str:
    """Cues -> SRT text. Always 1-based, sequential, CRLF line ending (SRT standard)."""
    out_lines: List[str] = []
    for i, c in enumerate(cues, start=1):
        out_lines.append(str(i))
        out_lines.append(f"{c.start} --> {c.end}")
        # Use current text (edited), fall back to original
        body = c.current.strip() if c.current.strip() else c.original.strip()
        out_lines.append(body)
        out_lines.append("")  # blank line separator
    # CRLF join, end with single newline
    return "\r\n".join(out_lines) + "\r\n"


def load_srt(path: Path) -> List[Cue]:
    """Load SRT file -> list of Cue."""
    # Try common encodings
    for enc in ("utf-8-sig", "utf-8", "latin-1"):
        try:
            text = Path(path).read_text(encoding=enc)
            return parse_srt(text)
        except UnicodeDecodeError:
            continue
    raise UnicodeDecodeError("utf-8", b"", 0, 1, f"Cannot decode {path}")


def save_srt(cues: List[Cue], path: Path) -> None:
    """Serialize cues -> SRT file (UTF-8, no BOM)."""
    Path(path).write_text(serialize_srt(cues), encoding="utf-8")


def load_working_json(path: Path) -> List[Cue]:
    """Load auto-save working JSON -> list of Cue."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    cues = []
    for d in data.get("cues", []):
        cues.append(Cue(
            id=d["id"],
            start=d["start"],
            end=d["end"],
            original=d["original"],
            current=d.get("current", d["original"]),
            reviewed=d.get("reviewed", False),
            flagged=d.get("flagged", False),
            auto_fixed=d.get("auto_fixed", False),
            note=d.get("note", ""),
        ))
    return cues


def save_working_json(cues: List[Cue], source: str, path: Path) -> None:
    """Save working state as JSON (for auto-save + resume)."""
    data = {
        "source": source,
        "stats": {
            "total": len(cues),
            "reviewed": sum(1 for c in cues if c.reviewed),
            "flagged": sum(1 for c in cues if c.flagged),
            "changed": sum(1 for c in cues if c.changed),
            "auto_fixed": sum(1 for c in cues if c.auto_fixed),
        },
        "cues": [c.to_dict() for c in cues],
    }
    Path(path).write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
