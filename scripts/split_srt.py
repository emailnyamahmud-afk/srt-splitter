#!/usr/bin/env python3
"""Split an SRT file into multiple SRT files, each with a max duration of 60 minutes.
Timestamps in each new SRT file are reset to start at 00:00:00 so each part can be
used with the corresponding split video file independently.

Usage: python split_srt.py <input.srt> <output_dir> <prefix> [max_minutes]
"""
import os
import re
import sys
from pathlib import Path


def parse_time(ts: str) -> float:
    """Parse 'HH:MM:SS,mmm' into total seconds (float)."""
    h, m, rest = ts.split(":")
    s, ms = rest.split(",")
    return int(h) * 3600 + int(m) * 60 + int(s) + int(ms) / 1000.0


def format_time(seconds: float) -> str:
    """Format seconds (float) back into 'HH:MM:SS,mmm'."""
    if seconds < 0:
        seconds = 0
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    ms = int(round((seconds - int(seconds)) * 1000))
    if ms == 1000:  # rounding edge case
        s += 1
        ms = 0
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def parse_srt(path: Path):
    """Return list of (index, start_sec, end_sec, [text lines])."""
    content = path.read_text(encoding="utf-8-sig", errors="replace")
    # Normalize line endings
    content = content.replace("\r\n", "\n").replace("\r", "\n")
    blocks = re.split(r"\n\s*\n", content.strip())
    entries = []
    for blk in blocks:
        lines = [ln for ln in blk.split("\n") if ln.strip() != ""]
        if len(lines) < 2:
            continue
        # First line should be index (we'll regenerate anyway)
        # Second line is the time range
        # Find the line that has the time range pattern
        time_line_idx = None
        for i, ln in enumerate(lines):
            if "-->" in ln:
                time_line_idx = i
                break
        if time_line_idx is None:
            continue
        m = re.match(
            r"(\d{2}:\d{2}:\d{2},\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2},\d{3})",
            lines[time_line_idx].strip(),
        )
        if not m:
            continue
        start = parse_time(m.group(1))
        end = parse_time(m.group(2))
        text_lines = lines[time_line_idx + 1:]
        entries.append((start, end, text_lines))
    return entries


def split_and_write(entries, output_dir: Path, prefix: str, max_minutes: int = 60):
    max_seconds = max_minutes * 60
    # Determine total duration from the last entry's end time
    if not entries:
        print("No entries found.")
        return
    total_duration = entries[-1][1]
    print(f"Total duration: {format_time(total_duration)} ({total_duration:.2f}s)")

    # Determine number of parts
    n_parts = int(total_duration // max_seconds)
    if total_duration % max_seconds > 0:
        n_parts += 1
    print(f"Splitting into {n_parts} part(s) of max {max_minutes} minutes each.")

    part_idx = 1
    part_entries = []
    current_part_start = 0.0
    next_part_start = max_seconds

    def write_part(part_entries, part_idx, part_start):
        out_path = output_dir / f"{prefix}-{part_idx:02d}.srt"
        with out_path.open("w", encoding="utf-8") as f:
            for i, (start, end, text_lines) in enumerate(part_entries, 1):
                new_start = start - part_start
                new_end = end - part_start
                if new_start < 0:
                    new_start = 0
                f.write(f"{i}\n")
                f.write(f"{format_time(new_start)} --> {format_time(new_end)}\n")
                for tl in text_lines:
                    f.write(tl + "\n")
                f.write("\n")
        print(f"Wrote {out_path} ({len(part_entries)} entries, "
              f"duration {format_time(part_entries[-1][1] - part_start)})")

    for start, end, text_lines in entries:
        # If this entry starts at or after next_part_start and we already have
        # entries collected, flush current part.
        if part_entries and start >= next_part_start:
            write_part(part_entries, part_idx, current_part_start)
            part_idx += 1
            current_part_start = next_part_start
            next_part_start += max_seconds
            part_entries = []
        part_entries.append((start, end, text_lines))

    # Flush remaining
    if part_entries:
        write_part(part_entries, part_idx, current_part_start)

    print(f"\nDone. {part_idx} file(s) written to {output_dir}")


def main():
    if len(sys.argv) < 4:
        print("Usage: python split_srt.py <input.srt> <output_dir> <prefix> [max_minutes]")
        sys.exit(1)
    input_path = Path(sys.argv[1])
    output_dir = Path(sys.argv[2])
    prefix = sys.argv[3]
    max_minutes = int(sys.argv[4]) if len(sys.argv) >= 5 else 60

    output_dir.mkdir(parents=True, exist_ok=True)
    entries = parse_srt(input_path)
    print(f"Parsed {len(entries)} subtitle entries from {input_path}")
    split_and_write(entries, output_dir, prefix, max_minutes)


if __name__ == "__main__":
    main()
