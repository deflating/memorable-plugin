#!/usr/bin/env python3
"""SessionStart / PreCompact hook for Memorable.

Outputs read instructions for seed files and semantic context files.
For semantic documents, prefer using the MCP tool `memorable_get_document_level`
to read only the selected level. Fallback: read `<filename>.levels.json` and use
`content[<level>]` for the configured zoom level.
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

_WORD_RE = re.compile(r"[a-z0-9][a-z0-9_-]{1,}")
DEFAULT_TOKEN_BUDGET = 200000
LEVELS_SUFFIX = ".levels.json"
MAX_LEVEL = 50


def load_config() -> dict:
    try:
        if CONFIG_PATH.exists():
            return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except Exception:
        pass
    return {}


def sanitize_filename(filename: str) -> str:
    return "".join(c for c in filename if c.isalnum() or c in "-_.").strip()


def core_seed_paths() -> list[str]:
    if not SEEDS_DIR.is_dir():
        return []
    paths = sorted(
        str(p) for p in SEEDS_DIR.glob("*.md")
        if p.is_file() and not p.name.startswith(".") and ".sync-conflict" not in p.name
    )
    return paths


def parse_context_depth(value, fallback: int = 1) -> int:
    try:
        depth = int(value)
    except (TypeError, ValueError):
        return fallback
    if depth == -1:
        return -1
    if 1 <= depth <= MAX_LEVEL:
        return depth
    return fallback


def parse_token_budget(config: dict, fallback: int = DEFAULT_TOKEN_BUDGET) -> int:
    raw = config.get("token_budget", fallback)
    try:
        parsed = int(raw)
    except (TypeError, ValueError):
        return fallback
    return max(1, parsed)


def estimate_tokens(text: str) -> int:
    return max(1, len(text) // 4) if text else 0


def estimate_file_tokens(path: Path) -> int:
    try:
        return estimate_tokens(path.read_text(encoding="utf-8"))
    except Exception:
        return 0


def keyword_tokens(text: str) -> set[str]:
    return {token for token in _WORD_RE.findall(text.lower()) if len(token) >= 3}


def collect_relevance_tokens(limit: int = 40) -> set[str]:
    notes_dir = DATA_DIR / "notes"
    if not notes_dir.is_dir():
        return set()
    entries = load_all_notes(notes_dir)
    if not entries:
        return set()

    recent = sorted(entries, key=lambda entry: str(entry.get("ts", "")), reverse=True)[:max(1, limit)]
    cues = []
    for entry in recent:
        tags = entry.get("topic_tags", [])
        if isinstance(tags, list):
            cues.extend(str(tag) for tag in tags)
        note = str(entry.get("note", "")).strip()
        if note:
            cues.append(note[:300])
    return keyword_tokens(" ".join(cues))


def read_levels_document(filename: str) -> dict | None:
    path = FILES_DIR / f"{filename}{LEVELS_SUFFIX}"
    if not path.is_file():
        return None
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    return loaded if isinstance(loaded, dict) else None


def level_count(levels_doc: dict | None) -> int:
    if not isinstance(levels_doc, dict):
        return 0
    raw = levels_doc.get("levels", 0)
    try:
        parsed = int(raw)
    except (TypeError, ValueError):
        return 0
    return max(0, min(MAX_LEVEL, parsed))


def content_for_level(levels_doc: dict | None, level: int) -> str | None:
    if not isinstance(levels_doc, dict) or level < 1:
        return None
    content = levels_doc.get("content", {})
    if not isinstance(content, dict):
        return None
    value = content.get(str(level))
    if isinstance(value, str) and value.strip():
        return value
    return None


def available_tokens_by_level(filename: str) -> tuple[dict[int, int], int, dict | None]:
    raw_path = FILES_DIR / filename
    levels_doc = read_levels_document(filename)

    tokens = {-1: estimate_file_tokens(raw_path)}
    max_level = level_count(levels_doc)
    if max_level <= 0:
        return tokens, 0, levels_doc

    tokens_map = levels_doc.get("tokens", {}) if isinstance(levels_doc, dict) else {}
    for level in range(1, max_level + 1):
        from_manifest = None
        if isinstance(tokens_map, dict):
            value = tokens_map.get(str(level))
            if isinstance(value, int) and value >= 0:
                from_manifest = value
        if from_manifest is not None:
            tokens[level] = from_manifest
            continue
        level_text = content_for_level(levels_doc, level)
        tokens[level] = estimate_tokens(level_text or "")

    return tokens, max_level, levels_doc


def context_entry_relevance(filename: str, relevance_tokens: set[str], levels_doc: dict | None) -> int:
    score = len(keyword_tokens(filename.replace(".", " ")) & relevance_tokens) * 3
    if not isinstance(levels_doc, dict):
        return score

    content = levels_doc.get("content", {})
    if isinstance(content, dict):
        for level in ("1", "2"):
            text = content.get(level)
            if isinstance(text, str):
                score += len(keyword_tokens(text[:400]) & relevance_tokens)
    return score


def next_shallower_level(current_level: int, max_level_value: int) -> int | None:
    if current_level == -1 and max_level_value >= 1:
        return max_level_value
    if current_level > 1:
        return current_level - 1
    if current_level == 1:
        return None
    return None


def next_deeper_level(current_level: int, max_level_value: int) -> int | None:
    if current_level < 1:
        return None
    if current_level < max_level_value:
        return current_level + 1
    return None


def choose_initial_level(configured_level: int, max_level_value: int) -> int:
    if max_level_value <= 0:
        return -1
    if configured_level == -1:
        return -1
    if configured_level < 1:
        return 1
    return min(configured_level, max_level_value)


def semantic_read_path(filename: str, selected_level: int, levels_doc: dict | None) -> str | None:
    raw_path = FILES_DIR / filename
    levels_path = FILES_DIR / f"{filename}{LEVELS_SUFFIX}"

    if selected_level >= 1 and isinstance(levels_doc, dict) and levels_path.is_file():
        return str(levels_path)
    if raw_path.is_file():
        return str(raw_path)
    return None


def build_context_plan(config: dict) -> list[dict]:
    plan = []
    for path_str in core_seed_paths():
        seed_path = Path(path_str)
        plan.append(
            {
                "type": "seed",
                "path": path_str,
                "depth": None,
                "tokens": estimate_file_tokens(seed_path),
                "reason": "core_seed",
            }
        )

    token_budget = parse_token_budget(config)
    budget_remaining = token_budget - sum(int(item.get("tokens", 0)) for item in plan)
    if budget_remaining < 0:
        budget_remaining = 0

    relevance_tokens = collect_relevance_tokens()
    candidates = []
    entries = config.get("context_files", [])
    if not isinstance(entries, list):
        return plan

    for entry in entries:
        if not isinstance(entry, dict):
            continue
        if not entry.get("enabled", True):
            continue
        filename = sanitize_filename(entry.get("filename", ""))
        if not filename:
            continue
        raw_path = FILES_DIR / filename
        if not raw_path.is_file():
            continue

        configured = parse_context_depth(entry.get("depth", 1), 1)
        tokens_by_level, max_level_value, levels_doc = available_tokens_by_level(filename)
        selected_level = choose_initial_level(configured, max_level_value)
        relevance = context_entry_relevance(filename, relevance_tokens, levels_doc)
        candidates.append(
            {
                "filename": filename,
                "levels_doc": levels_doc,
                "max_level": max_level_value,
                "tokens_by_level": tokens_by_level,
                "depth": selected_level,
                "relevance": relevance,
                "reason": "default_level",
            }
        )

    total_tokens = sum(candidate["tokens_by_level"].get(candidate["depth"], 0) for candidate in candidates)

    # De-escalate lower relevance first until budget fits.
    for candidate in sorted(candidates, key=lambda item: (item["relevance"], item["filename"])):
        while total_tokens > budget_remaining:
            next_level = next_shallower_level(candidate["depth"], candidate["max_level"])
            if next_level is not None and next_level in candidate["tokens_by_level"]:
                current = candidate["tokens_by_level"].get(candidate["depth"], 0)
                downgraded = candidate["tokens_by_level"].get(next_level, current)
                candidate["depth"] = next_level
                candidate["reason"] = "deescalated_for_budget"
                total_tokens -= max(0, current - downgraded)
                continue
            if candidate["depth"] is not None:
                current = candidate["tokens_by_level"].get(candidate["depth"], 0)
                candidate["depth"] = None
                candidate["reason"] = "skipped_for_budget"
                total_tokens -= current
            break

    # Do not auto-escalate above configured depth.
    # User-selected depth acts as a hard cap; we only de-escalate for budget pressure.

    for candidate in candidates:
        selected_level = candidate.get("depth")
        if selected_level is None:
            continue
        read_path = semantic_read_path(candidate["filename"], selected_level, candidate["levels_doc"])
        if not read_path:
            continue
        plan.append(
            {
                "type": "semantic",
                "path": read_path,
                "filename": candidate["filename"],
                "depth": selected_level,
                "tokens": candidate["tokens_by_level"].get(selected_level, 0),
                "relevance": candidate["relevance"],
                "reason": candidate["reason"],
                "levels_count": candidate["max_level"],
                "is_levels_file": read_path.endswith(LEVELS_SUFFIX),
            }
        )
    return plan


def collect_files(config: dict) -> list[str]:
    paths = []
    for item in build_context_plan(config):
        path = item.get("path")
        if isinstance(path, str) and path:
            paths.append(path)
    return paths


def consume_hook_input():
    try:
        json.loads(sys.stdin.read())
    except (json.JSONDecodeError, EOFError):
        return


def format_depth_label(depth: int | None) -> str:
    if depth is None:
        return "n/a"
    if depth < 0:
        return "raw"
    return str(depth)


def print_context_instructions(plan: list[dict], is_compact: bool):
    header = "[Memorable] Context recovery after compaction. Read these files:\n"
    if not is_compact:
        header = "[Memorable] BEFORE RESPONDING, read these files in order:\n"
    print(header)
    for i, item in enumerate(plan, 1):
        path = item.get("path", "")
        suffix = ""
        if item.get("type") == "semantic":
            depth_label = format_depth_label(item.get("depth"))
            tokens = int(item.get("tokens", 0))
            reason = str(item.get("reason", "default_level"))
            levels_count = int(item.get("levels_count", 0) or 0)
            if item.get("is_levels_file") and int(item.get("depth", -1)) >= 1:
                suffix = (
                    f" (zoom level {depth_label}/{levels_count}, ~{tokens} tokens, {reason}; "
                    f"prefer MCP tool memorable_get_document_level(filename=\"{item.get('filename','')}\", level={depth_label}); "
                    f"fallback: use content[\"{depth_label}\"] from this JSON)"
                )
            else:
                suffix = f" (raw fallback, ~{tokens} tokens, {reason})"
        elif item.get("type") == "seed":
            suffix = " (core seed)"
        print(f"{i}. Read {path}{suffix}")
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


def print_observation_stream():
    """Load recent observations from live extraction stream."""
    obs_file = DATA_DIR / "stream" / "observations.jsonl"
    if not obs_file.exists():
        return

    # Prune entries older than 5 days
    from datetime import datetime, timezone, timedelta
    cutoff = (datetime.now(timezone.utc) - timedelta(days=5)).isoformat()

    observations = []
    kept_lines = []
    try:
        with open(obs_file) as f:
            for line in f:
                try:
                    entry = json.loads(line)
                    if entry.get("ts", "") >= cutoff:
                        kept_lines.append(line)
                        observations.append(entry)
                except (json.JSONDecodeError, ValueError):
                    continue
        # Write back pruned file
        obs_file.write_text("".join(kept_lines))
    except Exception:
        return

    if not observations:
        return

    # Group by type and show
    by_type = {}
    for obs in observations:
        t = obs.get("type", "fact")
        by_type.setdefault(t, []).append(obs)

    type_labels = {
        "fact": "Facts", "decision": "Decisions", "rejection": "Rejections",
        "preference": "Preferences", "open_thread": "Open Threads",
        "person": "People", "mood": "Mood",
    }

    lines = [f"\n[Memorable] Live observations (last 5 days, {len(observations)} total):"]
    for t in ["decision", "fact", "open_thread", "preference", "person", "rejection", "mood"]:
        items = by_type.get(t, [])
        if items:
            # Show most recent, highest importance first
            items.sort(key=lambda x: (-x.get("importance", 3), x.get("ts", "")))
            lines.append(f"  {type_labels.get(t, t)}:")
            for item in items[:5]:
                ts_short = item.get("ts", "")[:10]
                lines.append(f"    - [{ts_short}] {item['content']}")

    print("\n".join(lines))


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
        plan = build_context_plan(config)
        if not plan:
            return
        print_context_instructions(plan, is_compact)
        print_selected_notes_section()
        print_observation_stream()
        print_memorable_search_hint()
    except Exception as error:
        log_session_start_error(error)


if __name__ == "__main__":
    main()
