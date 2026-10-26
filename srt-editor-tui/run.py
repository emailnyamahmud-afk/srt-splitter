#!/usr/bin/env python3
"""Entry point: run srt-editor-tui.

Usage:
    ./run.py <srt-file> [--glossary glossary.json]

Or:
    python3 run.py <srt-file> [--glossary glossary.json]
"""
import sys
from pathlib import Path

# Add this folder to path so we can import srt_editor package
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from srt_editor.editor import main

if __name__ == "__main__":
    main()
