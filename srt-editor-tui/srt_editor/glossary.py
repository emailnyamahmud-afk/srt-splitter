"""Glossary loader & applier.

Glossary JSON format (machine-safe, no comments, no anchors):

{
  "version": 1,
  "entries": [
    {
      "canonical": "Lin Zhao",
      "variants": ["Lin Yanya", "Lin Yasi", "Peti mati Lin", "Peti mati Lin Ya"],
      "scope": "all"
    },
    ...
  ]
}

- canonical: the form we want to keep (case-sensitive exact match preserved)
- variants: list of strings to be replaced by canonical (case-sensitive exact substring)
- scope (optional): reserved for future; "all" or "names" or "terms"
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Dict, Optional, Iterable


@dataclass
class GlossaryEntry:
    canonical: str
    variants: List[str] = field(default_factory=list)
    scope: str = "all"

    def __post_init__(self):
        # Sort variants by length DESC so longer variants are replaced first
        # (prevents partial replacement of "Peti mati Lin Ya" before "Peti mati Lin")
        self.variants = sorted(set(self.variants), key=len, reverse=True)
        # Remove canonical from variants if accidentally included
        self.variants = [v for v in self.variants if v != self.canonical]

    def apply_to(self, text: str) -> tuple[str, int]:
        """Replace all variants in `text` with canonical. Returns (new_text, count)."""
        count = 0
        new_text = text
        for v in self.variants:
            if not v:
                continue
            # Use plain str.replace (literal, case-sensitive)
            n = new_text.count(v)
            if n > 0:
                new_text = new_text.replace(v, self.canonical)
                count += n
        return new_text, count


@dataclass
class Glossary:
    entries: List[GlossaryEntry] = field(default_factory=list)
    version: int = 1

    @property
    def by_canonical(self) -> Dict[str, GlossaryEntry]:
        return {e.canonical: e for e in self.entries}


def load_glossary(path: Path) -> Glossary:
    """Load glossary from JSON file. Strict validation, raises on malformed."""
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Glossary not found: {p}")

    raw = json.loads(p.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("Glossary root must be a JSON object")

    version = int(raw.get("version", 1))
    entries_raw = raw.get("entries", [])
    if not isinstance(entries_raw, list):
        raise ValueError("'entries' must be a list")

    entries = []
    for i, e in enumerate(entries_raw):
        if not isinstance(e, dict):
            raise ValueError(f"Entry {i}: must be object, got {type(e).__name__}")
        canonical = e.get("canonical")
        if not canonical or not isinstance(canonical, str):
            raise ValueError(f"Entry {i}: missing/invalid 'canonical'")
        variants = e.get("variants", [])
        if not isinstance(variants, list):
            raise ValueError(f"Entry {i}: 'variants' must be list")
        variants = [str(v) for v in variants if v]
        scope = str(e.get("scope", "all"))
        entries.append(GlossaryEntry(canonical=canonical, variants=variants, scope=scope))

    return Glossary(entries=entries, version=version)


def save_glossary(glossary: Glossary, path: Path) -> None:
    """Write glossary back to JSON (sorted, indented)."""
    data = {
        "version": glossary.version,
        "entries": [
            {
                "canonical": e.canonical,
                "variants": sorted(e.variants, key=len, reverse=True),
                "scope": e.scope,
            }
            for e in glossary.entries
        ],
    }
    Path(path).write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def scan_cues_for_variants(cues, glossary: Glossary) -> Dict[str, Dict[str, List[int]]]:
    """Scan all cues, find which ones contain which variants.

    Returns: {canonical: {variant_text: [cue_id, cue_id, ...]}}
    """
    result: Dict[str, Dict[str, List[int]]] = {}
    for entry in glossary.entries:
        result[entry.canonical] = {}
        for v in entry.variants:
            hits = []
            for c in cues:
                if v in c.current:
                    hits.append(c.id)
            if hits:
                result[entry.canonical][v] = hits
        # Remove empty entries
        if not result[entry.canonical]:
            del result[entry.canonical]
    return result


def count_variants_in_cues(cues, glossary: Glossary) -> Dict[str, int]:
    """Returns {canonical: total_replacements_count}."""
    out = {}
    for entry in glossary.entries:
        total = 0
        for c in cues:
            for v in entry.variants:
                total += c.current.count(v)
        out[entry.canonical] = total
    return out
