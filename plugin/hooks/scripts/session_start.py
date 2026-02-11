#!/usr/bin/env python3
"""SessionStart / PreCompact hook for Memorable.

Outputs read instructions for seed files and context files so Claude
actively reads them with the Read tool, rather than passively receiving
content in a system reminder.
"""

import json
import re
import sys
from pathlib import Path

BASE_DIR = Path.home() / ".memorable"
SEEDS_DIR = BASE_DIR / "data" / "seeds"
FILES_DIR = BASE_DIR / "data" / "files"
CONFIG_PATH = BASE_DIR / "data" / "config.json"

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


def extract_at_depth(anchored_text: str, max_depth: int) -> str:
    """Extract content from anchored text up to max_depth, stripping markers."""
    if max_depth < 0:
        return anchored_text

    result = []
    pos = 0
    depth_stack = []

    for match in _ANCHOR_RE.finditer(anchored_text):
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
            pos = end
        else:
            if depth_stack:
                if depth_stack[-1] <= max_depth:
                    result.append(anchored_text[pos:start])
                depth_stack.pop()
            pos = end

    if depth_stack and depth_stack[-1] <= max_depth:
        result.append(anchored_text[pos:])
    elif not depth_stack:
        trailing = anchored_text[pos:].strip()
        if trailing:
            result.append(trailing)

    text = "".join(result).strip()
    text = re.sub(r" {2,}", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text


def prepare_context_file(filename: str, depth: int) -> str | None:
    """Prepare a context file for loading, returning the path to read.

    For anchored files with a specific depth, extracts content and writes
    a cached version. Returns the path Claude should read.
    """
    safe_filename = sanitize_filename(filename)
    if not safe_filename:
        return None

    raw_path = FILES_DIR / safe_filename
    anchored_path = FILES_DIR / f"{safe_filename}.anchored"

    # If anchored version exists and depth is set (not full/-1)
    if anchored_path.is_file() and depth >= 0:
        anchored_text = anchored_path.read_text(encoding="utf-8")
        extracted = extract_at_depth(anchored_text, depth)

        # Write to a cached extraction file
        cache_path = FILES_DIR / f".cache-{safe_filename}-depth{depth}.md"
        cache_path.write_text(extracted, encoding="utf-8")
        return str(cache_path)

    # Full depth or no anchored version — serve raw file
    if raw_path.is_file():
        return str(raw_path)

    return None


def collect_files(config: dict) -> list[str]:
    """Collect all files that should be read, in order."""
    paths = []

    # Core seed files
    for name in ("user.md", "agent.md", "now.md"):
        path = SEEDS_DIR / name
        if path.is_file():
            paths.append(str(path))

    # Additional context files from config
    for entry in config.get("context_files", []):
        if not entry.get("enabled", True):
            continue
        filename = sanitize_filename(entry.get("filename", ""))
        if not filename:
            continue

        # Skip if already covered by seeds above
        seed_path = SEEDS_DIR / filename
        if seed_path.is_file() and str(seed_path) in paths:
            continue

        depth = entry.get("depth", -1)
        prepared = prepare_context_file(filename, depth)
        if prepared:
            paths.append(prepared)
            continue

        # Fallback: check seeds dir
        if seed_path.is_file():
            paths.append(str(seed_path))

    return paths


def main():
    try:
        # Read stdin (hook input)
        try:
            json.loads(sys.stdin.read())
        except (json.JSONDecodeError, EOFError):
            pass

        is_compact = "--compact" in sys.argv
        config = load_config()
        files = collect_files(config)

        if not files:
            return

        if is_compact:
            print("[Memorable] Context recovery after compaction. Read these files:\n")
        else:
            print("[Memorable] BEFORE RESPONDING, read these files in order:\n")

        for i, path in enumerate(files, 1):
            print(f"{i}. Read {path}")

        print("\nDo NOT skip this. Do NOT respond before reading these files.")

    except Exception as e:
        log_path = BASE_DIR / "hook-errors.log"
        try:
            import time
            with open(log_path, "a") as f:
                f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] session_start: {e}\n")
        except Exception:
            pass


if __name__ == "__main__":
    main()
