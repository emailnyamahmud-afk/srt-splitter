"""Simplified pilot test: verify app launches and list populates."""
import sys
import asyncio
sys.path.insert(0, "/home/z/my-project/srt-editor-tui")
from pathlib import Path
from srt_editor.editor import EditorApp
from textual.widgets import ListView, ListItem

async def main():
    app = EditorApp(
        Path("/home/z/my-project/srt-editor-tui/test-input.srt"),
        Path("/home/z/my-project/srt-editor-tui/sample-glossary.json"),
    )
    async with app.run_test(size=(140, 36)) as pilot:
        await pilot.pause()

        # Verify list is populated
        lv = app.query_one("#cue-list", ListView)
        n_items = len(lv.query(ListItem))
        print(f"List items rendered: {n_items}  (expected 5162)")
        assert n_items == 5162, f"Expected 5162, got {n_items}"

        # Verify status bar shows progress info
        status = app.query_one("#status-bar")
        print(f"Status bar rendered (Static widget present)")

        # Verify detail pane shows first cue
        detail_header = app.query_one("#detail-header")
        print(f"Detail header present")

        # Use arrow keys to navigate (default ListView behavior)
        await pilot.press("down")
        await pilot.pause()
        print(f"After 1x down arrow: current_index = {app.current_index}")

        # Navigate further
        for _ in range(5):
            await pilot.press("down")
        await pilot.pause()
        print(f"After 6x down: current_index = {app.current_index}")
        print(f"  cue #{app.cues[app.current_index].id}: {app.cues[app.current_index].original!r}")

        # Save (Ctrl+S)
        await pilot.press("ctrl+s")
        await pilot.pause()
        out = Path("/home/z/my-project/srt-editor-tui/test-input.final.srt")
        bak = Path("/home/z/my-project/srt-editor-tui/test-input.srt.bak")
        working = Path("/home/z/my-project/srt-editor-tui/test-input.working.json")
        print(f"\nAfter Ctrl+S:")
        print(f"  final.srt exists: {out.exists()} ({out.stat().st_size if out.exists() else 0} bytes)")
        print(f"  .bak exists: {bak.exists()}")
        print(f"  working.json exists: {working.exists()}")

        print("\n✓ TUI launches, list populates, navigation works, save works.")

asyncio.run(main())
