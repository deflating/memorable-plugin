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
_WORD_RE = re.compile(r"[a-z0-9][a-z0-9_-]{1,}")
DEFAULT_TOKEN_BUDGET = 200000
DETAIL_ORDER = (0, 1, 2, 3, -1)


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
    for name in ("user.md", "agent.md", "now.md", "knowledge.md"):
        path = SEEDS_DIR / name
        if path.is_file():
            paths.append(str(path))
    return paths


def parse_context_depth(value, fallback: int = -1) -> int:
    try:
        depth = int(value)
    except (TypeError, ValueError):
        return fallback
    if depth in (-1, 0, 1, 2, 3):
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


def read_manifest(filename: str) -> dict | None:
    path = FILES_DIR / f"{filename}.anchored.meta.json"
    if not path.is_file():
        return None
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    return loaded if isinstance(loaded, dict) else None


def manifest_level_tokens(manifest: dict | None, depth: int) -> int | None:
    if not isinstance(manifest, dict):
        return None
    levels = manifest.get("levels", {})
    if not isinstance(levels, dict):
        return None
    key = "full" if depth < 0 else str(depth)
    info = levels.get(key, {})
    if not isinstance(info, dict):
        return None
    tokens = info.get("tokens")
    if isinstance(tokens, int) and tokens >= 0:
        return tokens
    return None


def available_tokens_by_depth(filename: str) -> tuple[dict[int, int], bool, dict | None]:
    raw_path = FILES_DIR / filename
    anchored_path = FILES_DIR / f"{filename}.anchored"
    manifest = read_manifest(filename)
    anchored = anchored_path.is_file()

    tokens_map = {-1: estimate_file_tokens(raw_path)}
    if not anchored:
        return tokens_map, False, manifest

    anchored_text = None
    for depth in (0, 1, 2, 3):
        from_manifest = manifest_level_tokens(manifest, depth)
        if from_manifest is not None:
            tokens_map[depth] = from_manifest
            continue
        if anchored_text is None:
            try:
                anchored_text = anchored_path.read_text(encoding="utf-8")
            except Exception:
                anchored_text = ""
        tokens_map[depth] = estimate_tokens(extract_at_depth(anchored_text, depth))
    full_from_manifest = manifest_level_tokens(manifest, -1)
    if full_from_manifest is not None:
        tokens_map[-1] = full_from_manifest
    return tokens_map, True, manifest


def context_entry_relevance(filename: str, relevance_tokens: set[str], manifest: dict | None) -> int:
    score = len(keyword_tokens(filename.replace(".", " ")) & relevance_tokens) * 3

    if isinstance(manifest, dict):
        provenance = manifest.get("provenance", {})
        if isinstance(provenance, dict):
            sections = provenance.get("sections", [])
            if isinstance(sections, list):
                for section in sections:
                    if not isinstance(section, dict):
                        continue
                    title_tokens = keyword_tokens(str(section.get("title", "")))
                    score += len(title_tokens & relevance_tokens)
    return score


def next_shallower_depth(current_depth: int, anchored: bool) -> int | None:
    if not anchored:
        return None
    idx = DETAIL_ORDER.index(current_depth)
    if idx == 0:
        return None
    return DETAIL_ORDER[idx - 1]


def next_deeper_depth(current_depth: int, anchored: bool) -> int | None:
    if not anchored:
        return None
    idx = DETAIL_ORDER.index(current_depth)
    if idx >= len(DETAIL_ORDER) - 1:
        return None
    return DETAIL_ORDER[idx + 1]


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

        default_depth = parse_context_depth(entry.get("depth", -1), -1)
        tokens_by_depth, anchored, manifest = available_tokens_by_depth(filename)
        if default_depth not in tokens_by_depth:
            default_depth = -1
        relevance = context_entry_relevance(filename, relevance_tokens, manifest)
        candidates.append(
            {
                "filename": filename,
                "anchored": anchored,
                "tokens_by_depth": tokens_by_depth,
                "depth": default_depth,
                "relevance": relevance,
                "reason": "default_depth",
            }
        )

    total_tokens = sum(candidate["tokens_by_depth"].get(candidate["depth"], 0) for candidate in candidates)
    if budget_remaining < 0:
        budget_remaining = 0

    for candidate in sorted(candidates, key=lambda item: (item["relevance"], item["filename"])):
        while total_tokens > budget_remaining:
            next_depth = next_shallower_depth(candidate["depth"], candidate["anchored"])
            if next_depth is not None and next_depth in candidate["tokens_by_depth"]:
                current = candidate["tokens_by_depth"].get(candidate["depth"], 0)
                downgraded = candidate["tokens_by_depth"].get(next_depth, current)
                candidate["depth"] = next_depth
                candidate["reason"] = "deescalated_for_budget"
                total_tokens -= max(0, current - downgraded)
                continue
            if candidate["depth"] is not None:
                current = candidate["tokens_by_depth"].get(candidate["depth"], 0)
                candidate["depth"] = None
                candidate["reason"] = "skipped_for_budget"
                total_tokens -= current
            break

    for candidate in sorted(candidates, key=lambda item: (-item["relevance"], item["filename"])):
        while candidate["depth"] is not None and total_tokens < budget_remaining:
            next_depth = next_deeper_depth(candidate["depth"], candidate["anchored"])
            if next_depth is None or next_depth not in candidate["tokens_by_depth"]:
                break
            current = candidate["tokens_by_depth"].get(candidate["depth"], 0)
            deepened = candidate["tokens_by_depth"].get(next_depth, current)
            delta = max(0, deepened - current)
            if total_tokens + delta > budget_remaining:
                break
            candidate["depth"] = next_depth
            candidate["reason"] = "escalated_for_relevance"
            total_tokens += delta

    for candidate in candidates:
        depth = candidate.get("depth")
        if depth is None:
            continue
        prepared = prepare_context_file(candidate["filename"], depth)
        if not prepared:
            continue
        plan.append(
            {
                "type": "semantic",
                "path": prepared,
                "filename": candidate["filename"],
                "depth": depth,
                "tokens": candidate["tokens_by_depth"].get(depth, 0),
                "relevance": candidate["relevance"],
                "reason": candidate["reason"],
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
        return "full"
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
            reason = str(item.get("reason", "default_depth"))
            suffix = f" (depth {depth_label}, ~{tokens} tokens, {reason})"
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
        print_memorable_search_hint()
    except Exception as error:
        log_session_start_error(error)


if __name__ == "__main__":
    main()
