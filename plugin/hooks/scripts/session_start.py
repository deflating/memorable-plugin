#!/usr/bin/env python3
"""SessionStart / PreCompact hook for Memorable.

Outputs:
1. Current date/time context
2. Instructions to read seed files
3. Most salient session notes
"""

import json
import sys
import time
from datetime import datetime
from pathlib import Path

from note_maintenance import load_all_notes, run_hierarchical_consolidation
from note_selection import format_notes, select_notes
from now_builder import maybe_update_now_md

BASE_DIR = Path.home() / ".memorable"
DATA_DIR = BASE_DIR / "data"
SEEDS_DIR = DATA_DIR / "seeds"
CONFIG_PATH = DATA_DIR / "config.json"


def load_config() -> dict:
    try:
        if CONFIG_PATH.exists():
            return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except Exception:
        pass
    return {}


def core_seed_paths() -> list[str]:
    if not SEEDS_DIR.is_dir():
        return []
    return sorted(
        str(p) for p in SEEDS_DIR.glob("*.md")
        if p.is_file() and not p.name.startswith(".") and ".sync-conflict" not in p.name
    )


def consume_hook_input():
    try:
        json.loads(sys.stdin.read())
    except (json.JSONDecodeError, EOFError):
        return


def print_time_context():
    now = datetime.now()
    day_name = now.strftime("%A")
    date_str = now.strftime("%-d %B %Y")
    time_str = now.strftime("%-I:%M %p").lower()
    print(f"[Memorable] It's {day_name} {date_str}, {time_str} AEDT.\n")


def print_seed_instructions(is_compact: bool):
    paths = core_seed_paths()
    if not paths:
        return
    header = "[Memorable] Context recovery after compaction. Read these files:\n"
    if not is_compact:
        header = "[Memorable] BEFORE RESPONDING, read these files in order:\n"
    print(header)
    for i, path in enumerate(paths, 1):
        print(f"{i}. Read {path} (core seed)")
    print("\nDo NOT skip this. Do NOT respond before reading these files.")


def print_selected_notes():
    notes_dir = DATA_DIR / "notes"
    if not notes_dir.exists():
        return
    entries = load_all_notes(notes_dir)
    if not entries:
        return
    entries = run_hierarchical_consolidation(notes_dir, entries)
    selected = select_notes(entries)
    if not selected:
        return
    maybe_update_now_md([entry for _, entry in selected])
    formatted = format_notes(selected)
    print(f"\n[Memorable] Most salient session notes ({len(entries)} total in {notes_dir}/):")
    print(formatted)
    print(f"To read a note: grep {notes_dir}/ for its session ID. To search by topic: grep by keyword.")


def log_error(error: Exception):
    log_path = BASE_DIR / "hook-errors.log"
    try:
        with open(log_path, "a") as f:
            f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] session_start: {error}\n")
    except Exception:
        pass


def main():
    try:
        consume_hook_input()
        is_compact = "--compact" in sys.argv
        print_time_context()
        print_seed_instructions(is_compact)
        print_selected_notes()
    except Exception as error:
        log_error(error)


if __name__ == "__main__":
    main()
