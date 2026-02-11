#!/usr/bin/env python3
"""SessionStart / PreCompact hook for Memorable.

Outputs read instructions for seed files and context files so Claude
actively reads them with the Read tool, rather than passively receiving
content in a system reminder. Also surfaces session notes with a recency
ceiling: the most recent notes are always included regardless of salience.
"""

import json
import re
import sys
from pathlib import Path

from note_maintenance import (
    ARCHIVE_AFTER_DAYS,
    ARCHIVE_DIRNAME,
    archive_low_salience_notes,
    load_all_notes,
    run_hierarchical_consolidation,
)
from note_selection import MIN_SALIENCE, effective_salience, format_notes, select_notes
from now_builder import AUTO_NOW_MARKER, maybe_update_now_md

BASE_DIR = Path.home() / ".memorable"
DATA_DIR = BASE_DIR / "data"
SEEDS_DIR = DATA_DIR / "seeds"
FILES_DIR = DATA_DIR / "files"
CONFIG_PATH = DATA_DIR / "config.json"

ANCHOR = "\u2693"
_ANCHOR_RE = re.compile(ANCHOR + r"([0-3]\ufe0f\u20e3)?")


def load_config() -> dict:
    try:
        if CONFIG_PATH.exists():
            return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except Exception:
        pass
    return {}


def sanitize_filename(filename: str) -> str:
    """Keep only safe filename characters."""
    return "".join(c for c in filename if c.isalnum() or c in "-_.").strip()


def apply_anchor_marker(
    match: re.Match,
    anchored_text: str,
    max_depth: int,
    result: list[str],
    depth_stack: list[int],
    pos: int,
) -> int:
    level_str = match.group(1)
    start = match.start()
    end = match.end()
    if level_str:
        level = int(level_str[0])
        if depth_stack and depth_stack[-1] <= max_depth:
            result.append(anchored_text[pos:start])
        elif not depth_stack and pos == 0:
            before = anchored_text[:start].strip()
            if before:
                result.append(before + " ")
        depth_stack.append(level)
        return end
    if depth_stack and depth_stack[-1] <= max_depth:
        result.append(anchored_text[pos:start])
    if depth_stack:
        depth_stack.pop()
    return end


def append_trailing_extracted_text(
    anchored_text: str,
    max_depth: int,
    result: list[str],
    depth_stack: list[int],
    pos: int,
):
    if depth_stack and depth_stack[-1] <= max_depth:
        result.append(anchored_text[pos:])
        return
    if not depth_stack:
        trailing = anchored_text[pos:].strip()
        if trailing:
            result.append(trailing)


def compact_extracted_text(parts: list[str]) -> str:
    text = "".join(parts).strip()
    text = re.sub(r" {2,}", " ", text)
    return re.sub(r"\n{3,}", "\n\n", text)


def extract_at_depth(anchored_text: str, max_depth: int) -> str:
    """Extract content from anchored text up to max_depth, stripping markers."""
    if max_depth < 0:
        return anchored_text
    result = []
    pos = 0
    depth_stack = []
    for match in _ANCHOR_RE.finditer(anchored_text):
        pos = apply_anchor_marker(match, anchored_text, max_depth, result, depth_stack, pos)
    append_trailing_extracted_text(anchored_text, max_depth, result, depth_stack, pos)
    return compact_extracted_text(result)


def prepare_context_file(filename: str, depth: int) -> str | None:
    safe_filename = sanitize_filename(filename)
    if not safe_filename:
        return None
    raw_path = FILES_DIR / safe_filename
    anchored_path = FILES_DIR / f"{safe_filename}.anchored"
    if anchored_path.is_file() and depth >= 0:
        anchored_text = anchored_path.read_text(encoding="utf-8")
        extracted = extract_at_depth(anchored_text, depth)
        cache_path = FILES_DIR / f".cache-{safe_filename}-depth{depth}.md"
        cache_path.write_text(extracted, encoding="utf-8")
        return str(cache_path)
    if raw_path.is_file():
        return str(raw_path)
    return None


def core_seed_paths() -> list[str]:
    paths = []
    for name in ("user.md", "agent.md", "now.md"):
        path = SEEDS_DIR / name
        if path.is_file():
            paths.append(str(path))
    return paths


def resolve_context_entry_path(entry: dict, existing_paths: set[str]) -> str | None:
    if not isinstance(entry, dict):
        return None
    if not entry.get("enabled", True):
        return None
    filename = sanitize_filename(entry.get("filename", ""))
    if not filename:
        return None
    seed_path = SEEDS_DIR / filename
    if seed_path.is_file() and str(seed_path) in existing_paths:
        return None
    prepared = prepare_context_file(filename, entry.get("depth", -1))
    if prepared:
        return prepared
    if seed_path.is_file():
        return str(seed_path)
    return None


def parse_context_depth(value, fallback: int = -1) -> int:
    try:
        depth = int(value)
    except (TypeError, ValueError):
        return fallback
    if depth in (-1, 0, 1, 2, 3):
        return depth
    return fallback


def collect_files(config: dict) -> list[str]:
    paths = core_seed_paths()
    seen = set(paths)
    entries = config.get("context_files", [])
    if not isinstance(entries, list):
        return paths
    for entry in entries:
        if isinstance(entry, dict):
            entry = dict(entry)
            entry["depth"] = parse_context_depth(entry.get("depth", -1), -1)
        resolved = resolve_context_entry_path(entry, seen)
        if not resolved:
            continue
        paths.append(resolved)
        seen.add(resolved)
    return paths


def consume_hook_input():
    try:
        json.loads(sys.stdin.read())
    except (json.JSONDecodeError, EOFError):
        return


def print_context_instructions(files: list[str], is_compact: bool):
    header = "[Memorable] Context recovery after compaction. Read these files:\n"
    if not is_compact:
        header = "[Memorable] BEFORE RESPONDING, read these files in order:\n"
    print(header)
    for i, path in enumerate(files, 1):
        print(f"{i}. Read {path}")
    print("\nDo NOT skip this. Do NOT respond before reading these files.")


def print_selected_notes_section():
    notes_dir = BASE_DIR / "data" / "notes"
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


def print_memorable_search_hint():
    print("\n[Memorable] To search past sessions and observations, use the `memorable_search` MCP tool or the /memorable-search skill.")
    print("Use this when the user references past conversations, asks \"do you remember...\", or when you need historical context.")


def log_session_start_error(error: Exception):
    log_path = BASE_DIR / "hook-errors.log"
    try:
        import time
        with open(log_path, "a") as f:
            f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] session_start: {error}\n")
    except Exception:
        pass


def main():
    try:
        consume_hook_input()
        is_compact = "--compact" in sys.argv
        config = load_config()
        files = collect_files(config)
        if not files:
            return
        print_context_instructions(files, is_compact)
        print_selected_notes_section()
        print_memorable_search_hint()
    except Exception as error:
        log_session_start_error(error)


if __name__ == "__main__":
    main()
