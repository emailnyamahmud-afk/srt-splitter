"""srt-editor-tui — main TUI application.

Usage:
    python editor.py <srt-file>
    python editor.py <srt-file> --glossary glossary.json

Phase 1 (MVP): load SRT, list+detail view, inline edit, mark reviewed, save.
Phase 2 (glossary): bulk replace with glossary.
Phase 3 (search/jump): search text, jump to cue id, find&replace.
"""
from __future__ import annotations

import sys
import os
import time
import json
from pathlib import Path
from typing import List, Optional

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.widgets import (
    Header,
    Footer,
    ListView,
    ListItem,
    Label,
    RichLog,
    Input,
    Button,
    Static,
    TabbedContent,
    TabPane,
)
from textual.reactive import reactive
from textual.message import Message
from rich.text import Text as RichText

# Make sure we can import our parser
_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE.parent))

from srt_editor.parser import (
    Cue, load_srt, serialize_srt, save_srt,
    save_working_json, load_working_json,
)
from srt_editor.glossary import (
    Glossary, load_glossary, scan_cues_for_variants,
)


# Status indicator characters
ICON_OK = "✓"      # reviewed
ICON_FLAG = "!"    # flagged
ICON_CHANGED = "*" # changed
ICON_AUTO = "@"    # auto-fixed by glossary
ICON_NEW = " "     # untouched


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


def cue_list_label(c: Cue, idx: int) -> RichText:
    """One-line label for cue list."""
    icon = cue_status_char(c)
    # Truncate text to ~40 chars for list display
    snippet = c.current.replace("\n", " ")
    if len(snippet) > 40:
        snippet = snippet[:37] + "..."
    label = RichText.assemble(
        (f"{idx+1:>5} ", "dim"),
        (f"[{icon}] ", _icon_style(icon)),
        (snippet, _text_style(c)),
    )
    return label


def _icon_style(icon: str) -> str:
    return {
        ICON_OK: "green",
        ICON_FLAG: "red bold",
        ICON_CHANGED: "yellow",
        ICON_AUTO: "cyan",
        ICON_NEW: "dim",
    }.get(icon, "dim")


def _text_style(c: Cue) -> str:
    if c.flagged:
        return "red"
    if c.changed or c.auto_fixed:
        return "yellow"
    if c.reviewed:
        return "white"
    return "dim"


class CueChanged(Message):
    """Posted when a cue's text/status changes."""
    def __init__(self, cue_id: int) -> None:
        self.cue_id = cue_id
        super().__init__()


class EditorApp(App):
    """srt-editor-tui main app."""

    CSS = """
    #main {
        layout: vertical;
        height: 100%;
    }
    .status-bar {
        height: 1;
        background: $primary;
        color: $text;
        padding: 0 1;
    }
    #content {
        height: 1fr;
    }
    #cue-list {
        width: 50%;
        height: 100%;
        border: solid $primary;
    }
    #detail-pane {
        width: 50%;
        height: 100%;
        padding: 0 1;
        border: solid $primary;
    }
    #detail-header {
        height: 3;
        padding: 1 1;
        background: $boost;
    }
    #detail-original {
        height: auto;
        min-height: 3;
        padding: 1 1;
        background: $panel;
        color: $text-muted;
    }
    #detail-current {
        height: auto;
        min-height: 3;
        padding: 1 1;
        background: $panel;
        color: $text;
    }
    #detail-hints {
        height: 1fr;
        padding: 0 1;
    }
    .keybar {
        height: 1;
        background: $boost;
        color: $text-muted;
        padding: 0 1;
    }
    .help-text {
        padding: 1 2;
    }
    #edit-modal {
        width: 80;
        height: 16;
        border: solid $accent;
        background: $surface;
        padding: 1 2;
    }
    #edit-modal Input {
        margin: 1 0;
    }
    #jump-modal, #search-modal {
        width: 60;
        height: 12;
        border: solid $accent;
        background: $surface;
        padding: 1 2;
    }
    ListView > ListItem {
        padding: 0 1;
    }
    """

    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("e", "edit_cue", "Edit"),
        Binding("r", "revert_cue", "Revert"),
        Binding("m", "toggle_reviewed", "Mark"),
        Binding("f", "toggle_flag", "Flag"),
        Binding("n", "next_unreviewed", "Next►"),
        Binding("p", "prev_unreviewed", "Prev◄"),
        Binding("F2", "glossary", "Glossary"),
        Binding("F3", "search", "Search"),
        Binding("F5", "jump", "Jump"),
        Binding("F4", "find_replace", "Replace"),
        Binding("ctrl+s", "save", "Save"),
        Binding("ctrl+r", "reload", "Reload"),
        Binding("?", "help", "Help"),
    ]

    cues: reactive[List[Cue]] = reactive(list, layout=False)
    current_index: reactive[int] = reactive(0, always_update=True)
    source_path: reactive[Optional[Path]] = reactive(None)
    output_path: reactive[Optional[Path]] = reactive(None)
    working_path: reactive[Optional[Path]] = reactive(None)
    glossary: reactive[Optional[Glossary]] = reactive(None)
    last_save_ts: reactive[float] = reactive(0.0, layout=False)
    auto_save_pending: reactive[bool] = reactive(False, layout=False)

    def __init__(self, srt_path: Path, glossary_path: Optional[Path] = None):
        super().__init__()
        self.srt_path_input = srt_path
        self.glossary_path_input = glossary_path
        self.title = f"srt-editor-tui :: {srt_path.name}"

    # ---------- lifecycle ----------

    def on_mount(self) -> None:
        # Resolve paths
        self.source_path = self.srt_path_input
        # Output: insert "final" before extension
        stem = self.srt_path_input.stem
        suffix = self.srt_path_input.suffix  # .srt
        self.output_path = self.srt_path_input.with_name(f"{stem}.final{suffix}")
        self.working_path = self.srt_path_input.with_name(f"{stem}.working.json")

        # Load SRT (or resume from working JSON if exists)
        if self.working_path.exists():
            try:
                cues = load_working_json(self.working_path)
                self.notify(f"Resumed from {self.working_path.name}", title="Resume")
            except Exception:
                cues = load_srt(self.source_path)
        else:
            cues = load_srt(self.source_path)

        self.cues = cues

        # Load glossary if provided
        if self.glossary_path_input and self.glossary_path_input.exists():
            try:
                self.glossary = load_glossary(self.glossary_path_input)
                self.notify(f"Glossary loaded: {len(self.glossary.entries)} entries",
                            title="Glossary")
            except Exception as e:
                self.notify(f"Glossary load failed: {e}", severity="error")

        # Populate list view
        self._refresh_list()

        # Set up auto-save timer (every 30s if dirty)
        self.set_interval(30.0, self._auto_save_if_dirty)

    # ---------- compose ----------

    def compose(self) -> ComposeResult:
        yield Header(show_clock=False)
        with Vertical(id="main"):
            yield Static("", id="status-bar", classes="status-bar")
            with Horizontal(id="content"):
                yield ListView(id="cue-list")
                with VerticalScroll(id="detail-pane"):
                    yield Static("", id="detail-header")
                    yield Static("", id="detail-original")
                    yield Static("", id="detail-current")
                    yield Static("", id="detail-hints")
            yield Static("", id="keybar", classes="keybar")
        yield Footer()

    # ---------- after compose ----------

    def on_ready(self) -> None:
        self._refresh_status()
        self._refresh_keybar()
        # Focus list view, jump to first cue
        self.query_one("#cue-list", ListView).focus()
        self.current_index = 0

    # ---------- list view ----------

    def _refresh_list(self) -> None:
        """Rebuild the cue list view."""
        lv = self.query_one("#cue-list", ListView)
        lv.clear()
        for i, c in enumerate(self.cues):
            # ListItem requires Widget children, not bare RichText
            label = Label(cue_list_label(c, i), markup=False)
            lv.append(ListItem(label, id=f"cue-{i}"))

    def watch_current_index(self, idx: int) -> None:
        """When index changes, highlight and refresh detail."""
        if not self.cues:
            return
        idx = max(0, min(idx, len(self.cues) - 1))
        lv = self.query_one("#cue-list", ListView)
        try:
            lv.index = idx
        except Exception:
            pass
        self._refresh_detail()
        self._refresh_status()

    def on_list_view__selected(self, event: ListView.Selected) -> None:
        """User clicked a cue in the list."""
        item_id = event.item.id or ""
        if item_id.startswith("cue-"):
            self.current_index = int(item_id.split("-")[1])

    def on_list_view_highlighted(self, event) -> None:
        """Keyboard nav changed highlight."""
        if event.list_view.index is not None:
            self.current_index = event.list_view.index

    # ---------- detail pane ----------

    def _refresh_detail(self) -> None:
        if not self.cues or self.current_index >= len(self.cues):
            return
        c = self.cues[self.current_index]
        status = []
        if c.reviewed: status.append("✓reviewed")
        if c.flagged: status.append("!flagged")
        if c.auto_fixed: status.append("@auto-fixed")
        if c.changed: status.append("*changed")
        status_str = " ".join(status) if status else "(untouched)"

        header = (
            f"Cue #{c.id}  (idx {self.current_index+1}/{len(self.cues)})\n"
            f"{c.start} → {c.end}   [{status_str}]"
        )
        self.query_one("#detail-header", Static).update(header)

        # Original (with diff highlight)
        orig = RichText(f"ORIGINAL:\n{c.original}", style="dim")
        self.query_one("#detail-original", Static).update(orig)

        # Current
        cur_style = "yellow" if c.changed else ("green" if c.reviewed else "white")
        cur = RichText(f"CURRENT:\n{c.current}", style=cur_style)
        self.query_one("#detail-current", Static).update(cur)

        # Hints
        hints_lines = []
        if self.glossary:
            hints_lines.append("Glossary: loaded")
        hints_lines.append("")
        hints_lines.append("Keys: e=edit r=revert m=mark f=flag n/p=next/prev")
        hints_lines.append("      F2=glossary F3=search F5=jump F4=replace")
        hints_lines.append("      Ctrl+S=save ?=help q=quit")
        self.query_one("#detail-hints", Static).update("\n".join(hints_lines))

    # ---------- status bar ----------

    def _refresh_status(self) -> None:
        if not self.cues:
            self.query_one("#status-bar", Static).update("No cues loaded.")
            return
        total = len(self.cues)
        reviewed = sum(1 for c in self.cues if c.reviewed)
        flagged = sum(1 for c in self.cues if c.flagged)
        changed = sum(1 for c in self.cues if c.changed)
        pct = (reviewed / total * 100) if total else 0
        src = self.source_path.name if self.source_path else "?"
        out = self.output_path.name if self.output_path else "?"
        bar = f"Progress: {reviewed}/{total} [{pct:.0f}%]  Flagged:{flagged}  Changed:{changed}"
        path_info = f"{src} → {out}"
        self.query_one("#status-bar", Static).update(f"{path_info}  |  {bar}")

    def _refresh_keybar(self) -> None:
        self.query_one("#keybar", Static).update(
            "e:edit  r:revert  m:mark  f:flag  n:next►  p:prev◄  "
            "F2:glossary  F3:search  F5:jump  F4:replace  Ctrl+S:save  q:quit  ?:help"
        )

    # ---------- cue editing ----------

    def action_edit_cue(self) -> None:
        if not self.cues:
            return
        c = self.cues[self.current_index]
        self._open_edit_modal(c)

    def _open_edit_modal(self, c: Cue) -> None:
        """Open a modal to edit cue text."""
        from textual.screen import ModalScreen
        from textual.widgets import TextArea

        class EditScreen(ModalScreen):
            CSS = """
            EditScreen {
                align: center middle;
            }
            #edit-modal {
                width: 80;
                height: 18;
                border: solid $accent;
                background: $surface;
                padding: 1 2;
            }
            #edit-textarea {
                height: 8;
                margin: 1 0;
            }
            .edit-buttons {
                align-horizontal: center;
                height: 3;
            }
            .edit-buttons Button {
                margin: 0 1;
            }
            """

            def __init__(self, cue: Cue, on_save):
                super().__init__()
                self.cue = cue
                self.on_save = on_save

            def compose(self):
                with Vertical(id="edit-modal"):
                    yield Static(f"Edit Cue #{self.cue.id}", id="edit-title")
                    yield Static(f"{self.cue.start} → {self.cue.end}", id="edit-ts")
                    yield TextArea(self.cue.current, id="edit-textarea", soft_wrap=True)
                    with Horizontal(classes="edit-buttons"):
                        yield Button("Save (Enter)", id="btn-save", variant="success")
                        yield Button("Cancel (Esc)", id="btn-cancel", variant="default")

            BINDINGS = [
                Binding("escape", "cancel", "Cancel"),
                Binding("ctrl+s", "save", "Save"),
            ]

            def action_cancel(self):
                self.dismiss(None)

            def action_save(self):
                ta = self.query_one("#edit-textarea", TextArea)
                self.on_save(self.cue, ta.text)
                self.dismiss(True)

            def on_button_pressed(self, event):
                if event.button.id == "btn-save":
                    self.action_save()
                elif event.button.id == "btn-cancel":
                    self.action_cancel()

        def on_save(cue: Cue, new_text: str):
            cue.current = new_text.rstrip("\n")
            cue.reviewed = True
            self._after_cue_change(self.current_index)

        self.push_screen(EditScreen(c, on_save))

    def action_revert_cue(self) -> None:
        if not self.cues:
            return
        c = self.cues[self.current_index]
        if c.current != c.original:
            c.current = c.original
            c.auto_fixed = False
            self.notify(f"Cue #{c.id} reverted to original")
            self._after_cue_change(self.current_index)
        else:
            self.notify("Already at original", severity="warning")

    def action_toggle_reviewed(self) -> None:
        if not self.cues:
            return
        c = self.cues[self.current_index]
        c.reviewed = not c.reviewed
        self._after_cue_change(self.current_index)

    def action_toggle_flag(self) -> None:
        if not self.cues:
            return
        c = self.cues[self.current_index]
        c.flagged = not c.flagged
        self._after_cue_change(self.current_index)

    def action_next_unreviewed(self) -> None:
        """Jump to next unreviewed cue."""
        for i in range(self.current_index + 1, len(self.cues)):
            if not self.cues[i].reviewed and not self.cues[i].auto_fixed:
                self.current_index = i
                return
        self.notify("No more unreviewed cues ahead", severity="info")

    def action_prev_unreviewed(self) -> None:
        for i in range(self.current_index - 1, -1, -1):
            if not self.cues[i].reviewed and not self.cues[i].auto_fixed:
                self.current_index = i
                return
        self.notify("No more unreviewed cues behind", severity="info")

    def _after_cue_change(self, idx: int) -> None:
        self.auto_save_pending = True
        self._refresh_detail()
        self._refresh_status()
        # Update the list item label
        try:
            lv = self.query_one("#cue-list", ListView)
            # We can't easily update a single item, so refresh the whole list
            # (5162 items - this is fast enough)
            self._refresh_list()
            lv.index = idx
        except Exception:
            pass

    # ---------- save ----------

    def action_save(self) -> None:
        if not self.cues or not self.output_path:
            return
        # Backup original (one-time)
        bak = self.source_path.with_suffix(self.source_path.suffix + ".bak")
        if not bak.exists():
            bak.write_bytes(self.source_path.read_bytes())
        # Save final SRT
        save_srt(self.cues, self.output_path)
        # Save working JSON
        if self.working_path:
            save_working_json(self.cues, str(self.source_path.name), self.working_path)
        self.last_save_ts = time.time()
        self.auto_save_pending = False
        self.notify(
            f"Saved: {self.output_path.name}\nBackup: {bak.name}",
            title="Saved",
            timeout=3,
        )
        self._refresh_status()

    def _auto_save_if_dirty(self) -> None:
        """Called by timer. Auto-save working JSON only (not final SRT)."""
        if not self.auto_save_pending or not self.cues or not self.working_path:
            return
        try:
            save_working_json(self.cues, str(self.source_path.name), self.working_path)
            self.auto_save_pending = False
            self.last_save_ts = time.time()
        except Exception:
            pass  # silent fail; don't bother user with auto-save errors

    # ---------- glossary ----------

    def action_glossary(self) -> None:
        """Open glossary panel."""
        if not self.glossary:
            self.notify("No glossary loaded. Pass --glossary path.json", severity="warning")
            return
        self._open_glossary_modal()

    def _open_glossary_modal(self) -> None:
        from textual.screen import ModalScreen
        from textual.widgets import DataTable

        class GlossaryScreen(ModalScreen):
            CSS = """
            GlossaryScreen {
                align: center middle;
            }
            #glossary-modal {
                width: 100;
                height: 28;
                border: solid $accent;
                background: $surface;
                padding: 1 2;
            }
            #glossary-table {
                height: 1fr;
                margin: 1 0;
            }
            .glossary-buttons {
                align-horizontal: center;
                height: 3;
            }
            .glossary-buttons Button {
                margin: 0 1;
            }
            """

            def __init__(self, app_ref):
                super().__init__()
                self.app_ref = app_ref

            def compose(self):
                gl = self.app_ref.glossary
                with Vertical(id="glossary-modal"):
                    yield Static(
                        f"Glossary: {len(gl.entries)} entries — arrow keys to navigate, "
                        "Enter to apply all variants of selected entry, Esc to close",
                        id="glossary-title"
                    )
                    table = DataTable(id="glossary-table")
                    table.add_columns("Entry", "Canonical", "Variants", "Matches")
                    matches = scan_cues_for_variants(self.app_ref.cues, gl)
                    for ent in gl.entries:
                        variants_str = ", ".join(ent.variants[:3])
                        if len(ent.variants) > 3:
                            variants_str += f" (+{len(ent.variants)-3})"
                        n_match = sum(len(cues) for cues in matches.get(ent.canonical, {}).values())
                        table.add_row(
                            ent.canonical, ent.canonical, variants_str, str(n_match),
                            key=ent.canonical,
                        )
                    yield table
                    with Horizontal(classes="glossary-buttons"):
                        yield Button("Apply Selected (Enter)", id="btn-apply-one", variant="primary")
                        yield Button("Apply ALL", id="btn-apply-all", variant="warning")
                        yield Button("Close (Esc)", id="btn-close", variant="default")

            BINDINGS = [
                Binding("escape", "close", "Close"),
                Binding("enter", "apply_selected", "Apply Selected"),
            ]

            def action_close(self):
                self.dismiss(False)

            def action_apply_selected(self):
                self._apply_selected()

            def _apply_selected(self):
                table = self.query_one("#glossary-table", DataTable)
                if table.current_row is None:
                    self.app_ref.notify("Select a row first", severity="warning")
                    return
                canonical = table.coordinate_to_cell_key(
                    table.get_coordinate_at_row(table.current_row)
                ).row_key.value
                self.app_ref._apply_glossary_entry(canonical)
                self.app_ref.notify(f"Applied: {canonical}", title="Glossary")
                # Refresh modal? For now just dismiss.
                self.dismiss(True)

            def on_button_pressed(self, event):
                if event.button.id == "btn-apply-one":
                    self._apply_selected()
                elif event.button.id == "btn-apply-all":
                    self.app_ref._apply_glossary_all()
                    self.app_ref.notify("Applied all glossary entries", title="Glossary")
                    self.dismiss(True)
                elif event.button.id == "btn-close":
                    self.action_close()

        self.push_screen(GlossaryScreen(self))

    def _apply_glossary_entry(self, canonical: str) -> int:
        """Apply one glossary entry across all cues. Returns count of replacements."""
        if not self.glossary:
            return 0
        entry = self.glossary.by_canonical.get(canonical)
        if not entry:
            return 0
        count = 0
        for c in self.cues:
            new_text, n = entry.apply_to(c.current)
            if n > 0:
                c.current = new_text
                c.auto_fixed = True
                count += n
        self._after_cue_change(self.current_index)
        return count

    def _apply_glossary_all(self) -> int:
        total = 0
        for entry in self.glossary.entries:
            for c in self.cues:
                new_text, n = entry.apply_to(c.current)
                if n > 0:
                    c.current = new_text
                    c.auto_fixed = True
                    total += n
        self._after_cue_change(self.current_index)
        return total

    # ---------- search & jump ----------

    def action_search(self) -> None:
        self._open_search_modal()

    def _open_search_modal(self) -> None:
        from textual.screen import ModalScreen

        class SearchScreen(ModalScreen):
            CSS = """
            SearchScreen { align: center middle; }
            #search-modal {
                width: 70;
                height: 14;
                border: solid $accent;
                background: $surface;
                padding: 1 2;
            }
            #search-input { margin: 1 0; }
            .search-buttons { align-horizontal: center; height: 3; }
            .search-buttons Button { margin: 0 1; }
            """
            BINDINGS = [Binding("escape", "close", "Close"), Binding("enter", "do_search", "Search")]

            def __init__(self, app_ref):
                super().__init__()
                self.app_ref = app_ref

            def compose(self):
                with Vertical(id="search-modal"):
                    yield Static("Search (case-insensitive):", id="search-title")
                    yield Input(id="search-input", placeholder="Enter search text...")
                    yield Static("", id="search-result")
                    with Horizontal(classes="search-buttons"):
                        yield Button("Find Next (Enter)", id="btn-next", variant="primary")
                        yield Button("Close (Esc)", id="btn-close")

            def action_close(self):
                self.dismiss(None)

            def action_do_search(self):
                q = self.query_one("#search-input", Input).value.strip().lower()
                if not q:
                    return
                idx = self.app_ref._search_next(q, self.app_ref.current_index + 1)
                if idx >= 0:
                    self.app_ref.notify(f"Found at cue #{self.app_ref.cues[idx].id}")
                    self.app_ref.current_index = idx
                    self.dismiss(True)
                else:
                    self.query_one("#search-result", Static).update(
                        f"No match found after current position."
                    )

            def on_button_pressed(self, event):
                if event.button.id == "btn-next":
                    self.action_do_search()
                elif event.button.id == "btn-close":
                    self.action_close()

        self.push_screen(SearchScreen(self))

    def _search_next(self, query: str, start_idx: int) -> int:
        q = query.lower()
        for i in range(start_idx, len(self.cues)):
            if q in self.cues[i].current.lower():
                return i
        # Wrap around
        for i in range(0, min(start_idx, len(self.cues))):
            if q in self.cues[i].current.lower():
                return i
        return -1

    def action_jump(self) -> None:
        """Jump to cue by ID."""
        from textual.screen import ModalScreen

        class JumpScreen(ModalScreen):
            CSS = """
            JumpScreen { align: center middle; }
            #jump-modal {
                width: 50;
                height: 10;
                border: solid $accent;
                background: $surface;
                padding: 1 2;
            }
            #jump-input { margin: 1 0; }
            .jump-buttons { align-horizontal: center; height: 3; }
            .jump-buttons Button { margin: 0 1; }
            """
            BINDINGS = [Binding("escape", "close"), Binding("enter", "do_jump")]

            def __init__(self, app_ref):
                super().__init__()
                self.app_ref = app_ref

            def compose(self):
                with Vertical(id="jump-modal"):
                    yield Static(f"Jump to cue (1-{len(self.app_ref.cues)}):")
                    yield Input(id="jump-input", placeholder="Cue ID...", type="integer")
                    with Horizontal(classes="jump-buttons"):
                        yield Button("Go (Enter)", id="btn-go", variant="primary")
                        yield Button("Close (Esc)", id="btn-close")

            def action_close(self):
                self.dismiss(None)

            def action_do_jump(self):
                v = self.query_one("#jump-input", Input).value.strip()
                try:
                    cue_id = int(v)
                    # Find cue with this id (could be different from index due to renumbering)
                    for i, c in enumerate(self.app_ref.cues):
                        if c.id == cue_id:
                            self.app_ref.current_index = i
                            self.app_ref.notify(f"Jumped to cue #{cue_id} (idx {i})")
                            self.dismiss(True)
                            return
                    self.app_ref.notify(f"Cue #{cue_id} not found", severity="warning")
                except ValueError:
                    pass

            def on_button_pressed(self, event):
                if event.button.id == "btn-go":
                    self.action_do_jump()
                elif event.button.id == "btn-close":
                    self.action_close()

        self.push_screen(JumpScreen(self))

    def action_find_replace(self) -> None:
        """Simple find & replace across all cues."""
        from textual.screen import ModalScreen

        class ReplaceScreen(ModalScreen):
            CSS = """
            ReplaceScreen { align: center middle; }
            #replace-modal {
                width: 70;
                height: 18;
                border: solid $accent;
                background: $surface;
                padding: 1 2;
            }
            #replace-find { margin: 1 0 0 0; }
            #replace-with { margin: 0 0 1 0; }
            .replace-buttons { align-horizontal: center; height: 3; }
            .replace-buttons Button { margin: 0 1; }
            """
            BINDINGS = [Binding("escape", "close")]

            def __init__(self, app_ref):
                super().__init__()
                self.app_ref = app_ref

            def compose(self):
                with Vertical(id="replace-modal"):
                    yield Static("Find & Replace (case-sensitive, all cues):")
                    yield Input(id="replace-find", placeholder="Find...")
                    yield Input(id="replace-with", placeholder="Replace with...")
                    yield Static("", id="replace-info")
                    with Horizontal(classes="replace-buttons"):
                        yield Button("Replace All", id="btn-replace", variant="warning")
                        yield Button("Close (Esc)", id="btn-close")

            def action_close(self):
                self.dismiss(None)

            def on_button_pressed(self, event):
                if event.button.id == "btn-replace":
                    find = self.query_one("#replace-find", Input).value
                    repl = self.query_one("#replace-with", Input).value
                    if not find:
                        return
                    n = 0
                    for c in self.app_ref.cues:
                        if find in c.current:
                            c.current = c.current.replace(find, repl)
                            c.auto_fixed = True
                            n += c.original.count(find)  # rough count
                    self.app_ref._after_cue_change(self.app_ref.current_index)
                    self.query_one("#replace-info", Static).update(
                        f"Replaced. Affected cues updated."
                    )
                    self.app_ref.notify(f"Find/Replace done", title="Replace")
                elif event.button.id == "btn-close":
                    self.action_close()

        self.push_screen(ReplaceScreen(self))

    # ---------- help ----------

    def action_help(self) -> None:
        from textual.screen import ModalScreen

        class HelpScreen(ModalScreen):
            CSS = """
            HelpScreen { align: center middle; }
            #help-modal {
                width: 80;
                height: 24;
                border: solid $accent;
                background: $surface;
                padding: 1 2;
            }
            """
            BINDINGS = [Binding("escape", "close"), Binding("q", "close")]

            def compose(self):
                with VerticalScroll(id="help-modal"):
                    yield Static(
                        "[b]srt-editor-tui — Help[/b]\n\n"
                        "[b]Navigation[/b]\n"
                        "  ↑/↓ or j/k        Move selection in cue list\n"
                        "  n / p            Next/prev unreviewed cue\n"
                        "  F5               Jump to cue by ID\n\n"
                        "[b]Editing[/b]\n"
                        "  e                Edit current cue text (opens modal)\n"
                        "  r                Revert to original text\n"
                        "  m                Toggle 'reviewed' mark\n"
                        "  f                Toggle 'flagged' mark\n\n"
                        "[b]Glossary[/b]\n"
                        "  F2               Open glossary panel (apply canonical forms)\n\n"
                        "[b]Search & Replace[/b]\n"
                        "  F3               Search text (case-insensitive)\n"
                        "  F4               Find & Replace (all cues, case-sensitive)\n\n"
                        "[b]Save[/b]\n"
                        "  Ctrl+S           Save final SRT + working JSON\n"
                        "  (auto-save working JSON every 30s if dirty)\n\n"
                        "[b]Status icons[/b]\n"
                        "  ✓ reviewed   ! flagged   * changed\n"
                        "  @ auto-fixed by glossary\n\n"
                        "[b]Files[/b]\n"
                        "  Input:  your.srt\n"
                        "  Output: your.final.srt (saved on Ctrl+S)\n"
                        "  Backup: your.srt.bak (created on first save)\n"
                        "  Work:   your.working.json (auto-save state)\n\n"
                        "[b]Quit[/b]\n"
                        "  q                Quit (auto-saves working JSON first)\n\n"
                        "Press Esc or q to close this help.",
                        id="help-content",
                    )

            def action_close(self):
                self.dismiss(None)

        self.push_screen(HelpScreen())

    # ---------- reload ----------

    def action_reload(self) -> None:
        """Reload from working JSON (discard unsaved in-memory edits)."""
        if self.working_path and self.working_path.exists():
            try:
                self.cues = load_working_json(self.working_path)
                self._refresh_list()
                self.current_index = 0
                self.notify("Reloaded from working JSON")
            except Exception as e:
                self.notify(f"Reload failed: {e}", severity="error")
        else:
            self.notify("No working JSON to reload from", severity="warning")

    # ---------- quit ----------

    def action_quit(self) -> None:
        # Auto-save working JSON before quit if dirty
        if self.auto_save_pending and self.cues and self.working_path:
            try:
                save_working_json(self.cues, str(self.source_path.name), self.working_path)
            except Exception:
                pass
        super().action_quit()


def main():
    if len(sys.argv) < 2:
        print("Usage: python editor.py <srt-file> [--glossary glossary.json]")
        print("\nExample:")
        print("  python editor.py S2-FB-Mandarin.id.srt")
        print("  python editor.py S2-FB-Mandarin.id.srt --glossary my-glossary.json")
        sys.exit(1)

    srt_path = Path(sys.argv[1]).expanduser().resolve()
    if not srt_path.exists():
        print(f"Error: SRT file not found: {srt_path}")
        sys.exit(1)

    glossary_path = None
    if "--glossary" in sys.argv:
        idx = sys.argv.index("--glossary")
        if idx + 1 < len(sys.argv):
            glossary_path = Path(sys.argv[idx + 1]).expanduser().resolve()
            if not glossary_path.exists():
                print(f"Error: Glossary file not found: {glossary_path}")
                sys.exit(1)

    app = EditorApp(srt_path, glossary_path)
    app.run()


if __name__ == "__main__":
    main()
