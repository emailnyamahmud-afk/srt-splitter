#!/usr/bin/env python3
"""
srt-editor-tui.py — TUI editor untuk SRT hasil Google Translate / editsub.com

Pipeline dubbing Mandarin→Jawa sering dapet SRT Indonesia dari editsub.com atau
Google Translate. Hasilnya punya banyak masalah:
  - Nama orang muncul 5 variasi (Hongying / Elang Merah / Qin Hongying Nyonya Qin)
  - Mistranslate konyol: "cumming" (seharusnya "menarik pelatuk"),
    "payung emas" (seharusnya "obat luka emas"), "ayam panah" (panah otomatis)
  - Sulit track cue mana yang sudah di-review

TUI ini ngebantu:
  - Browse cues per halaman, edit inline (single-line atau via $EDITOR)
  - Mark reviewed / flag bermasalah
  - Glossary JSON: edit satu canonical → semua variant ter-replace otomatis
  - Search, jump-to-cue, find&replace
  - Auto-save working JSON (resume kapan saja)

Install:
  pip3 install questionary

Usage:
  python3 srt-editor-tui.py <srt-file>
  python3 srt-editor-tui.py <srt-file> --glossary glossary.json

Output:
  <stem>.final.srt      — output final (pakai ini untuk edge-tts / mix-tui)
  <stem>.srt.bak        — backup original (dibuat sekali saat save pertama)
  <stem>.working.json   — auto-save state untuk resume

Note:
  Glossary default sudah inline di script (19 entries dari review S2-FB-Mandarin.id.srt).
  Kalau punya glossary sendiri, pakai --glossary file.json.
  Format glossary JSON:
    {
      "version": 1,
      "entries": [
        {"canonical": "Lin Zhao", "variants": ["Lin Yanya", "Peti mati Lin"], "scope": "names"}
      ]
    }
"""

import os
import sys
import re
import json
import time
import shutil
import subprocess
import argparse
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import List, Optional, Dict, Any

# Questionary import dengan fallback message
try:
    import questionary
except ImportError:
    print('\n❌ pip3 install questionary')
    print('   lalu: python3 srt-editor-tui.py <srt-file>')
    sys.exit(1)


VERSION = "1.0.0"
PAGE_SIZE = 20  # cues per halaman di browse mode

# Status icons
ICON_OK = "✓"       # reviewed
ICON_FLAG = "!"     # flagged
ICON_CHANGED = "*"  # text berubah
ICON_AUTO = "@"     # auto-fixed by glossary
ICON_NEW = " "      # untouched


# === Default glossary (inline, dari review S2-FB-Mandarin.id.srt) ===
# 19 entries → terdeteksi 144 replacement di S2-FB-Mandarin.id.srt
DEFAULT_GLOSSARY = {
    "version": 1,
    "entries": [
        {"canonical": "Lin Zhao", "variants": [
            "Lin Yanya", "Lin Yasi", "Peti mati Lin", "Peti mati Lin Ya",
            "Lin Zhou", "Lin menertawakan peti mati",
            "Lin Penahanan di belakang aula", "Lin harus ditahan",
            "Lin ditahan dan semua orang ada di sini"
        ], "scope": "names"},
        {"canonical": "Xie Changfeng", "variants": [
            "Xie Zangfeng", "Xie Chaojin", "Xie Dutou", "Pelatih Xie", "Tuan Xie"
        ], "scope": "names"},
        {"canonical": "Wang Haochuan", "variants": ["Aokawa"], "scope": "names"},
        {"canonical": "Ma Zhenbang", "variants": ["Marco", "Ma Zhenzhuang"], "scope": "names"},
        {"canonical": "Chen Su", "variants": [
            "Chen Xinlang", "Saudari Chen Su", "Nyonya Chen", "Nona Chen", "Dokter Chen"
        ], "scope": "names"},
        {"canonical": "Qin Hongying", "variants": [
            "Hongying", "Elang Merah", "Red Eagle", "Qin Hongying Nyonya Qin"
        ], "scope": "names"},
        {"canonical": "Mu En", "variants": [
            "Bulan", "bulan mudu xu", "bulan yang rendah hati", "Mu Xunjian"
        ], "scope": "names"},
        {"canonical": "Yao Sihai", "variants": [
            "Butler Yao", "Yao Gu", "Yao Dadu", "Yao Zhong"
        ], "scope": "names"},
        {"canonical": "Zhou Lizheng", "variants": [
            "Zhou Laozhang", "Zhou Lao", "Paman Zhou"
        ], "scope": "names"},
        {"canonical": "Qin Fenglu", "variants": ["Qin Fengzhan", "Qin Fengjun"], "scope": "names"},
        {"canonical": "Xiangjun", "variants": [
            "Tentara Hunan", "tentara utang", "pemberontak debitur", "debitur",
            "Tentara debitur", "Tentara Xiangjun"
        ], "scope": "terms"},
        {"canonical": "panah otomatis", "variants": [
            "ayam panah", "ayam panah otomatis", "panah otomatis buatan pribadi"
        ], "scope": "terms"},
        {"canonical": "obat luka emas", "variants": [
            "payung emas", "payung tempat tidur emas", "payung emas buatan tangan"
        ], "scope": "terms"},
        {"canonical": "Jiedushi", "variants": ["dot polisi", "Qin Fenglu dot polisi"], "scope": "terms"},
        {"canonical": "menarik pelatuk", "variants": ["cumming", "melakukan cumming"], "scope": "terms"},
        {"canonical": "laras meledak", "variants": ["menggoreng permen"], "scope": "terms"},
        {"canonical": "pembalasan", "variants": ["retribusi"], "scope": "terms"},
        {"canonical": "akademi", "variants": ["universitas terkemuka", "SMP Desa"], "scope": "terms"},
        {"canonical": "Li Kui", "variants": [], "scope": "names"},
    ]
}


# === Parser SRT ===

TS_RE = re.compile(
    r"(\d{2}):(\d{2}):(\d{2})[,.](\d{3})\s*-->\s*(\d{2}):(\d{2}):(\d{2})[,.](\d{3})"
)


@dataclass
class Cue:
    id: int
    start: str
    end: str
    original: str
    current: str = ""
    reviewed: bool = False
    flagged: bool = False
    auto_fixed: bool = False
    note: str = ""

    def __post_init__(self):
        if not self.current:
            self.current = self.original

    @property
    def changed(self) -> bool:
        return self.current != self.original


def parse_srt(text: str) -> List[Cue]:
    """Parse SRT text → list of Cue. Tolerates BOM, CRLF, blank lines."""
    if text.startswith("\ufeff"):
        text = text.lstrip("\ufeff")
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    blocks = re.split(r"\n\s*\n", text.strip())
    cues: List[Cue] = []
    for block in blocks:
        block = block.strip()
        if not block:
            continue
        lines = block.split("\n")
        if len(lines) < 2:
            continue
        idx = 0
        ts_line_idx = 0
        try:
            int(lines[0].strip())
            idx = int(lines[0].strip())
            ts_line_idx = 1
        except ValueError:
            ts_line_idx = 0
        if ts_line_idx >= len(lines):
            continue
        ts_match = TS_RE.search(lines[ts_line_idx])
        if not ts_match:
            continue
        g = ts_match.groups()
        start = f"{g[0]}:{g[1]}:{g[2]},{g[3]}"
        end = f"{g[4]}:{g[5]}:{g[6]},{g[7]}"
        body = "\n".join(lines[ts_line_idx + 1:]).strip()
        cue_id = idx if idx else (len(cues) + 1)
        cues.append(Cue(id=cue_id, start=start, end=end, original=body, current=body))
    return cues


def serialize_srt(cues: List[Cue]) -> str:
    """Cues → SRT text (CRLF, SRT standard)."""
    out: List[str] = []
    for i, c in enumerate(cues, start=1):
        out.append(str(i))
        out.append(f"{c.start} --> {c.end}")
        body = c.current.strip() if c.current.strip() else c.original.strip()
        out.append(body)
        out.append("")
    return "\r\n".join(out) + "\r\n"


def load_srt(path: Path) -> List[Cue]:
    """Load SRT file → list of Cue. Try multiple encodings."""
    for enc in ("utf-8-sig", "utf-8", "latin-1"):
        try:
            text = Path(path).read_text(encoding=enc)
            return parse_srt(text)
        except UnicodeDecodeError:
            continue
    raise UnicodeDecodeError("utf-8", b"", 0, 1, f"Cannot decode {path}")


def save_srt(cues: List[Cue], path: Path) -> None:
    Path(path).write_text(serialize_srt(cues), encoding="utf-8")


def load_working_json(path: Path) -> List[Cue]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    cues: List[Cue] = []
    for d in data.get("cues", []):
        cues.append(Cue(
            id=d["id"], start=d["start"], end=d["end"],
            original=d["original"],
            current=d.get("current", d["original"]),
            reviewed=d.get("reviewed", False),
            flagged=d.get("flagged", False),
            auto_fixed=d.get("auto_fixed", False),
            note=d.get("note", ""),
        ))
    return cues


def save_working_json(cues: List[Cue], source: str, path: Path) -> None:
    data = {
        "source": source,
        "version": VERSION,
        "saved_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "stats": {
            "total": len(cues),
            "reviewed": sum(1 for c in cues if c.reviewed),
            "flagged": sum(1 for c in cues if c.flagged),
            "changed": sum(1 for c in cues if c.changed),
            "auto_fixed": sum(1 for c in cues if c.auto_fixed),
        },
        "cues": [asdict(c) for c in cues],
    }
    Path(path).write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")


# === Glossary ===

class GlossaryEntry:
    def __init__(self, canonical: str, variants: List[str], scope: str = "all"):
        self.canonical = canonical
        # Sort by length DESC → cegah partial replacement
        # ("Peti mati Lin Ya" diganti sebelum "Peti mati Lin")
        self.variants = sorted(set(variants), key=len, reverse=True)
        self.variants = [v for v in self.variants if v and v != self.canonical]
        self.scope = scope
        # Pre-compile case-insensitive regex untuk tiap variant
        self._patterns = [(v, re.compile(re.escape(v), re.IGNORECASE)) for v in self.variants]

    def apply_to(self, text: str) -> tuple:
        """Replace all variants in text → canonical (CASE-INSENSITIVE).

        Misal: variant 'payung emas' akan match 'Payung emas', 'PAYUNG EMAS', dst.
        Canonical case diambil dari glossary (bukan dari text input).
        """
        count = 0
        new_text = text
        for v, pattern in self._patterns:
            n = len(pattern.findall(new_text))
            if n > 0:
                new_text = pattern.sub(self.canonical, new_text)
                count += n
        return new_text, count


class Glossary:
    def __init__(self, entries: List[GlossaryEntry] = None, version: int = 1):
        self.entries = entries or []
        self.version = version

    @property
    def by_canonical(self) -> Dict[str, GlossaryEntry]:
        return {e.canonical: e for e in self.entries}


def load_glossary(path: Path) -> Glossary:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("Glossary root must be JSON object")
    entries: List[GlossaryEntry] = []
    for e in raw.get("entries", []):
        if not isinstance(e, dict):
            continue
        canonical = e.get("canonical")
        if not canonical:
            continue
        variants = e.get("variants", [])
        if not isinstance(variants, list):
            continue
        entries.append(GlossaryEntry(
            canonical=str(canonical),
            variants=[str(v) for v in variants if v],
            scope=str(e.get("scope", "all")),
        ))
    return Glossary(entries=entries, version=int(raw.get("version", 1)))


def glossary_from_default() -> Glossary:
    entries = []
    for e in DEFAULT_GLOSSARY["entries"]:
        entries.append(GlossaryEntry(
            canonical=e["canonical"],
            variants=e.get("variants", []),
            scope=e.get("scope", "all"),
        ))
    return Glossary(entries=entries, version=DEFAULT_GLOSSARY["version"])


def scan_cues_for_variants(cues: List[Cue], glossary: Glossary) -> Dict[str, Dict[str, List[int]]]:
    """Scan cues, return {canonical: {variant_text: [cue_ids]}}."""
    result: Dict[str, Dict[str, List[int]]] = {}
    for entry in glossary.entries:
        for v in entry.variants:
            hits = [c.id for c in cues if v in c.current]
            if hits:
                result.setdefault(entry.canonical, {})[v] = hits
    return result


# === TUI helpers ===

def cue_status_char(c: Cue) -> str:
    if c.flagged:
        return ICON_FLAG
    if c.auto_fixed:
        return ICON_AUTO
    if c.reviewed:
        return ICON_OK
    if c.changed:
        return ICON_CHANGED
    return ICON_NEW


def cue_label(c: Cue, idx: int) -> str:
    icon = cue_status_char(c)
    snippet = c.current.replace("\n", " ")
    if len(snippet) > 50:
        snippet = snippet[:47] + "..."
    return f"[{icon}] #{c.id}  {snippet}"


def show_status_bar(cues: List[Cue], source_path: Path, output_path: Path) -> None:
    total = len(cues)
    reviewed = sum(1 for c in cues if c.reviewed)
    flagged = sum(1 for c in cues if c.flagged)
    changed = sum(1 for c in cues if c.changed)
    pct = (reviewed / total * 100) if total else 0
    print(f"📁 {source_path.name} → {output_path.name}")
    print(f"📊 Progress: {reviewed}/{total} [{pct:.0f}%]  Flagged:{flagged}  Changed:{changed}")
    print(f"   Icons: ✓reviewed  !flagged  *changed  @auto-fixed  (space)untouched")


def show_cue_detail(c: Cue, idx: int, total: int) -> None:
    status = []
    if c.reviewed: status.append("✓reviewed")
    if c.flagged: status.append("!flagged")
    if c.auto_fixed: status.append("@auto-fixed")
    if c.changed: status.append("*changed")
    status_str = " | ".join(status) if status else "(untouched)"
    print(f"\n{'─' * 70}")
    print(f"  Cue #{c.id}  (idx {idx+1}/{total})")
    print(f"  ⏱ {c.start} → {c.end}   [{status_str}]")
    print(f"{'─' * 70}")
    print(f"  ORIGINAL: {c.original}")
    if c.current != c.original:
        print(f"  CURRENT:  {c.current}")
    print(f"{'─' * 70}")


# === Editor (main TUI controller) ===

class Editor:
    def __init__(self, srt_path: Path, glossary_path: Optional[Path] = None):
        self.source_path = Path(srt_path).expanduser().resolve()
        stem = self.source_path.stem
        suffix = self.source_path.suffix
        self.output_path = self.source_path.with_name(f"{stem}.final{suffix}")
        self.working_path = self.source_path.with_name(f"{stem}.working.json")
        self.bak_path = self.source_path.with_name(f"{stem}{suffix}.bak")

        # Load cues (resume dari working JSON kalau ada)
        if self.working_path.exists():
            try:
                self.cues = load_working_json(self.working_path)
                print(f"📂 Resumed from {self.working_path.name} ({len(self.cues)} cues)")
            except Exception:
                self.cues = load_srt(self.source_path)
                print(f"📂 Loaded {len(self.cues)} cues from SRT")
        else:
            self.cues = load_srt(self.source_path)
            print(f"📂 Loaded {len(self.cues)} cues from SRT")

        # Load glossary (file or default)
        if glossary_path:
            try:
                self.glossary = load_glossary(glossary_path)
                print(f"📚 Glossary from file: {len(self.glossary.entries)} entries")
            except Exception as e:
                print(f"⚠️  Glossary file error: {e}")
                print(f"📚 Falling back to default glossary")
                self.glossary = glossary_from_default()
        else:
            self.glossary = glossary_from_default()
            print(f"📚 Default glossary: {len(self.glossary.entries)} entries (inline)")

        self.dirty = False
        self.current_idx = 0

    def run(self):
        while True:
            try:
                self.show_main_menu()
            except KeyboardInterrupt:
                print("\n\n👋 Interrupt → auto-save working JSON...")
                self._auto_save()
                print("👋 Bye!")
                sys.exit(0)

    def show_main_menu(self):
        print("\n" + "=" * 70)
        show_status_bar(self.cues, self.source_path, self.output_path)
        print()

        choices = [
            questionary.Choice(f"📋  Browse cues (dari #{self.cues[self.current_idx].id})", value="browse"),
            questionary.Choice("🔢  Jump to cue by ID", value="jump"),
            questionary.Choice("🔍  Search text", value="search"),
            questionary.Choice("🔄  Find & Replace (semua cue)", value="replace"),
            questionary.Choice(f"📚  Glossary ({len(self.glossary.entries)} entries)", value="glossary"),
            questionary.Choice("⏭  Next unreviewed", value="next_unreviewed"),
            questionary.Choice("💾  Save (final.srt + working.json + .bak)", value="save"),
            questionary.Choice("🚪  Quit", value="quit"),
        ]
        action = questionary.select(
            "Menu:", choices=choices, use_arrow_keys=True
        ).ask()

        if action is None or action == "quit":
            if self.dirty:
                keep = questionary.confirm("Save changes before quit?", default=True).ask()
                if keep:
                    self.save()
            print("👋 Bye!")
            sys.exit(0)
        elif action == "browse":
            self.browse_cues()
        elif action == "jump":
            self.jump_to_cue()
        elif action == "search":
            self.search_cues()
        elif action == "replace":
            self.find_replace()
        elif action == "glossary":
            self.glossary_menu()
        elif action == "next_unreviewed":
            self.goto_next_unreviewed()
        elif action == "save":
            self.save()

    # ---------- browse ----------

    def browse_cues(self):
        page = self.current_idx // PAGE_SIZE
        while True:
            start = page * PAGE_SIZE
            end = min(start + PAGE_SIZE, len(self.cues))
            print(f"\n📦 Halaman {page+1} (idx {start+1}-{end} dari {len(self.cues)})")

            choices = []
            for i in range(start, end):
                choices.append(questionary.Choice(cue_label(self.cues[i], i), value=i))
            choices.append(questionary.Choice("⬅  Prev page", value="prev"))
            choices.append(questionary.Choice("➡  Next page", value="next"))
            choices.append(questionary.Choice("⬆  Back to menu", value="back"))

            sel = questionary.select(
                "Pilih cue (Enter=view):", choices=choices,
                default=start, use_arrow_keys=True,
            ).ask()

            if sel is None or sel == "back":
                return
            elif sel == "prev":
                page = max(0, page - 1)
            elif sel == "next":
                max_page = (len(self.cues) - 1) // PAGE_SIZE
                page = min(max_page, page + 1)
            else:
                self.current_idx = sel
                self.view_cue(sel)
                page = self.current_idx // PAGE_SIZE

    def view_cue(self, idx: int):
        while True:
            c = self.cues[idx]
            show_cue_detail(c, idx, len(self.cues))

            choices = [
                questionary.Choice("✏️  Edit text", value="edit"),
                questionary.Choice("↩  Revert to original", value="revert"),
                questionary.Choice("✓  Toggle reviewed (m)", value="mark"),
                questionary.Choice("❗ Toggle flag (f)", value="flag"),
                questionary.Choice("↓  Next cue", value="next"),
                questionary.Choice("↑  Prev cue", value="prev"),
                questionary.Choice("⬆  Back to list", value="back"),
            ]
            action = questionary.select(
                "Action:", choices=choices, use_arrow_keys=True
            ).ask()

            if action is None or action == "back":
                return
            elif action == "edit":
                self.edit_cue(idx)
            elif action == "revert":
                if c.current != c.original:
                    c.current = c.original
                    c.auto_fixed = False
                    self.dirty = True
                    print(f"  ↩ Reverted to original")
                else:
                    print("  (already at original)")
            elif action == "mark":
                c.reviewed = not c.reviewed
                self.dirty = True
                print(f"  reviewed = {c.reviewed}")
            elif action == "flag":
                c.flagged = not c.flagged
                self.dirty = True
                print(f"  flagged = {c.flagged}")
            elif action == "next":
                idx = min(len(self.cues) - 1, idx + 1)
                self.current_idx = idx
            elif action == "prev":
                idx = max(0, idx - 1)
                self.current_idx = idx

    def edit_cue(self, idx: int):
        c = self.cues[idx]
        # Single-line cue → questionary.text langsung
        # Multi-line cue → pilih mode (external $EDITOR / single-line)
        if "\n" in c.current:
            print(f"\n  ⚠️  Cue #{c.id} multi-line. Current:")
            for i, line in enumerate(c.current.split("\n"), 1):
                print(f"    {i}: {line}")
            choice = questionary.select(
                "Mode edit:",
                choices=[
                    questionary.Choice("Open in $EDITOR (vim/nano/etc)", value="editor"),
                    questionary.Choice("Edit single line (newlines → space)", value="single"),
                    questionary.Choice("Cancel", value="cancel"),
                ]
            ).ask()
            if choice == "editor":
                self._edit_via_external_editor(idx)
            elif choice == "single":
                new_text = questionary.text(
                    "New text:", default=c.current.replace("\n", " ")
                ).ask()
                if new_text and new_text != c.current:
                    c.current = new_text
                    c.reviewed = True
                    self.dirty = True
                    print(f"  ✓ Updated")
                else:
                    print("  (no change)")
            else:
                print("  (cancelled)")
        else:
            new_text = questionary.text("New text:", default=c.current).ask()
            if new_text is not None and new_text != c.current:
                c.current = new_text
                c.reviewed = True
                self.dirty = True
                print(f"  ✓ Updated")
            else:
                print("  (no change)")

    def _edit_via_external_editor(self, idx: int):
        c = self.cues[idx]
        editor = os.environ.get("EDITOR") or os.environ.get("VISUAL") or "nano"
        tmpfile = Path(f"/tmp/srt-edit-{c.id}-{int(time.time())}.txt")
        try:
            tmpfile.write_text(c.current, encoding="utf-8")
            subprocess.run([editor, str(tmpfile)], check=True)
            new_text = tmpfile.read_text(encoding="utf-8").rstrip("\n")
            if new_text and new_text != c.current:
                c.current = new_text
                c.reviewed = True
                self.dirty = True
                print(f"  ✓ Updated via {editor}")
            else:
                print("  (no change)")
        except Exception as e:
            print(f"  ❌ Editor error: {e}")
        finally:
            tmpfile.unlink(missing_ok=True)

    # ---------- jump / search / replace ----------

    def jump_to_cue(self):
        v = questionary.text(
            f"Jump to cue ID (1-{self.cues[-1].id}):"
        ).ask()
        if not v:
            return
        try:
            cue_id = int(v)
            for i, c in enumerate(self.cues):
                if c.id == cue_id:
                    self.current_idx = i
                    self.view_cue(i)
                    return
            print(f"  ❌ Cue #{cue_id} not found")
        except ValueError:
            print("  ❌ Invalid number")

    def search_cues(self):
        q = questionary.text("Search (case-insensitive):").ask()
        if not q:
            return
        q = q.lower()
        matches = [(i, c) for i, c in enumerate(self.cues) if q in c.current.lower()]
        if not matches:
            print(f"  ❌ No match for '{q}'")
            return
        print(f"\n  Found {len(matches)} matches")
        choices = [questionary.Choice(f"#{c.id}  {c.current[:60]}", value=i)
                   for i, c in matches[:30]]
        if len(matches) > 30:
            choices.append(questionary.Choice(
                f"... +{len(matches)-30} more (refine search)", value=None))
        choices.append(questionary.Choice("⬆  Back", value="back"))
        sel = questionary.select("Jump to:", choices=choices).ask()
        if sel is None or sel == "back":
            return
        self.current_idx = sel
        self.view_cue(sel)

    def find_replace(self):
        find = questionary.text("Find (case-sensitive):").ask()
        if not find:
            return
        repl = questionary.text("Replace with:").ask()
        if repl is None:
            return
        n_affected = 0
        for c in self.cues:
            if find in c.current:
                new = c.current.replace(find, repl)
                if new != c.current:
                    c.current = new
                    c.auto_fixed = True
                    n_affected += 1
        self.dirty = True
        print(f"  ✓ Replaced in {n_affected} cues")

    # ---------- glossary ----------

    def glossary_menu(self):
        matches = scan_cues_for_variants(self.cues, self.glossary)
        if not matches:
            print("\n  ✨ No glossary variants found in cues. All clean!")
            return
        print(f"\n📚 Glossary matches ({len(matches)} entries with hits):")
        choices = []
        for canonical, variants in matches.items():
            entry = self.glossary.by_canonical[canonical]
            total = sum(len(cues) for cues in variants.values())
            v_str = ", ".join(entry.variants[:3])
            if len(entry.variants) > 3:
                v_str += f" (+{len(entry.variants)-3})"
            label = f"{canonical}  [{v_str}]  → {total} hits"
            choices.append(questionary.Choice(label, value=canonical))
        choices.append(questionary.Choice("🌟 Apply ALL glossary entries", value="__ALL__"))
        choices.append(questionary.Choice("⬆  Back", value="back"))

        sel = questionary.select("Apply entry:", choices=choices).ask()
        if sel is None or sel == "back":
            return
        elif sel == "__ALL__":
            total_n = 0
            for entry in self.glossary.entries:
                for c in self.cues:
                    new, n = entry.apply_to(c.current)
                    if n > 0:
                        c.current = new
                        c.auto_fixed = True
                        total_n += n
            self.dirty = True
            print(f"  ✓ Applied all glossary. {total_n} replacements.")
        else:
            entry = self.glossary.by_canonical[sel]
            n_total = 0
            for c in self.cues:
                new, n = entry.apply_to(c.current)
                if n > 0:
                    c.current = new
                    c.auto_fixed = True
                    n_total += n
            self.dirty = True
            print(f"  ✓ Applied '{sel}'. {n_total} replacements.")

    def goto_next_unreviewed(self):
        for i in range(self.current_idx + 1, len(self.cues)):
            if not self.cues[i].reviewed and not self.cues[i].auto_fixed:
                self.current_idx = i
                print(f"  → Jumped to cue #{self.cues[i].id}")
                self.view_cue(i)
                return
        print("  ✅ No more unreviewed cues ahead")

    # ---------- save ----------

    def save(self):
        if not self.bak_path.exists():
            shutil.copy(self.source_path, self.bak_path)
        save_srt(self.cues, self.output_path)
        save_working_json(self.cues, self.source_path.name, self.working_path)
        self.dirty = False
        print(f"\n  💾 Saved:")
        print(f"     • {self.output_path.name}  (final, pakai ini untuk edge-tts/mix-tui)")
        print(f"     • {self.bak_path.name}  (backup original)")
        print(f"     • {self.working_path.name}  (resume state)")

    def _auto_save(self):
        if self.dirty and self.working_path:
            try:
                save_working_json(self.cues, self.source_path.name, self.working_path)
                self.dirty = False
                print(f"  💾 Auto-saved working JSON")
            except Exception as e:
                print(f"  ⚠️  Auto-save failed: {e}")


# === Argparse + main ===

def main():
    parser = argparse.ArgumentParser(
        description=f"srt-editor-tui v{VERSION} — TUI editor untuk file SRT hasil translate",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Contoh:
  python3 srt-editor-tui.py subs.id.srt
  python3 srt-editor-tui.py subs.id.srt --glossary my-glossary.json

Output:
  <stem>.final.srt      — output final
  <stem>.srt.bak        — backup original (1x saat save pertama)
  <stem>.working.json   — auto-save state untuk resume
""",
    )
    parser.add_argument("srt", help="Path file SRT untuk di-edit")
    parser.add_argument(
        "--glossary",
        help="Path file glossary JSON (opsional, kalau kosong pakai default inline)"
    )
    args = parser.parse_args()

    srt = Path(args.srt).expanduser().resolve()
    if not srt.exists():
        print(f"❌ File tidak ditemukan: {srt}")
        sys.exit(1)

    print(f"\n🎬 srt-editor-tui v{VERSION}")
    print(f"📄 {srt.name}\n")

    glossary_path = None
    if args.glossary:
        glossary_path = Path(args.glossary).expanduser().resolve()
        if not glossary_path.exists():
            print(f"⚠️  Glossary tidak ditemukan: {glossary_path}")
            print(f"📚 Pakai default glossary saja")
            glossary_path = None

    editor = Editor(srt, glossary_path)
    editor.run()


if __name__ == "__main__":
    main()
