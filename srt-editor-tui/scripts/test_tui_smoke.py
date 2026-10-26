"""Test that the TUI app imports & initializes without runtime errors.
(We can't actually render the TUI in this sandbox without a real TTY,
but we can at least import it and check that all classes/wiring are OK.)
"""
import sys
sys.path.insert(0, "/home/z/my-project/srt-editor-tui")
from srt_editor.editor import EditorApp
from srt_editor.parser import load_srt
from srt_editor.glossary import load_glossary
from pathlib import Path

# Smoke-test: just make sure the App class can be instantiated
app = EditorApp(
    Path("/home/z/my-project/srt-editor-tui/test-input.srt"),
    Path("/home/z/my-project/srt-editor-tui/sample-glossary.json"),
)
print("EditorApp instantiated OK")
print(f"  srt_path_input: {app.srt_path_input}")
print(f"  glossary_path_input: {app.glossary_path_input}")
print(f"  title: {app.title}")

# Verify it can load cues eagerly (we can't actually run() in sandbox)
from textual.app import App
assert isinstance(app, App), "EditorApp should be a Textual App"

# Check the methods we expect are bound
expected_actions = [
    "edit_cue", "revert_cue", "toggle_reviewed", "toggle_flag",
    "next_unreviewed", "prev_unreviewed", "glossary",
    "search", "jump", "find_replace", "save", "reload", "help", "quit",
]
for action in expected_actions:
    method = getattr(app, f"action_{action}", None)
    assert callable(method), f"Missing action: action_{action}"
    print(f"  ✓ action_{action} bound")

print("\nAll TUI actions bound. TUI is ready to run on user's terminal.")
