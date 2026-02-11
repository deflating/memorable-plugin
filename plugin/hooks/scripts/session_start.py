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
from datetime import datetime, timezone
from pathlib import Path

BASE_DIR = Path.home() / ".memorable"
SEEDS_DIR = BASE_DIR / "data" / "seeds"
FILES_DIR = BASE_DIR / "data" / "files"
CONFIG_PATH = BASE_DIR / "data" / "config.json"

ANCHOR = "\u2693"
_ANCHOR_RE = re.compile(ANCHOR + r"([0-3]\ufe0f\u20e3)?")
_WORD_RE = re.compile(r"[A-Za-z0-9_']+")
_BULLET_RE = re.compile(r"^\s*[-*]\s+", re.MULTILINE)
_ACTION_CUE_RE = re.compile(
    r"\b(todo|next step|next steps|action(?:s| items?)?|follow[- ]?up|"
    r"decide|decision|blocked|blocker|unblock|deadline|ship|fix|implement|resolve)\b",
    re.IGNORECASE,
)

# Note loading constants
DECAY_FACTOR = 0.97
MIN_SALIENCE = 0.05
MAX_SALIENT_NOTES = 8
RECENCY_CEILING = 3  # Always include this many most-recent notes


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


def _effective_salience(entry: dict) -> float:
    """Calculate effective salience with decay + density + actionability."""
    try:
        salience = float(entry.get("salience", 1.0))
    except (TypeError, ValueError):
        salience = 1.0

    try:
        emotional_weight = float(entry.get("emotional_weight", 0.3))
    except (TypeError, ValueError):
        emotional_weight = 0.3
    emotional_weight = max(0.0, min(1.0, emotional_weight))

    last_ref = entry.get("last_referenced", entry.get("ts", ""))
    try:
        ts_clean = str(last_ref).replace("Z", "+00:00")
        dt = datetime.fromisoformat(ts_clean)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        days = (datetime.now(timezone.utc) - dt).total_seconds() / 86400
    except (ValueError, TypeError):
        days = 30

    adjusted_days = days * (1.0 - emotional_weight * 0.5)
    decayed = salience * (DECAY_FACTOR ** adjusted_days)
    base = max(MIN_SALIENCE, decayed)
    density_mult = _information_density_multiplier(entry)
    actionability_mult = _actionability_multiplier(entry)
    return max(MIN_SALIENCE, base * density_mult * actionability_mult)


def _note_text(entry: dict) -> str:
    text = entry.get("note", "")
    return text if isinstance(text, str) else str(text)


def _information_density_multiplier(entry: dict) -> float:
    """Score notes by signal per token (short dense > long rambling)."""
    text = _note_text(entry).strip()
    if not text:
        return 1.0

    words = _WORD_RE.findall(text.lower())
    if not words:
        return 1.0

    word_count = len(words)
    unique_ratio = len(set(words)) / word_count
    est_tokens = max(1, len(text) // 4)
    words_per_token = word_count / est_tokens

    lexical_score = max(0.0, min(1.0, (unique_ratio - 0.25) / 0.55))
    density_score = max(0.0, min(1.0, words_per_token / 0.85))

    # Softly penalize extremely long notes unless they are exceptionally dense.
    token_penalty = 0.0
    if est_tokens > 450:
        token_penalty = min(0.25, (est_tokens - 450) / 2200)

    score = (0.55 * lexical_score) + (0.45 * density_score) - token_penalty
    score = max(0.0, min(1.0, score))

    # 0.80x .. 1.30x
    return 0.8 + (0.5 * score)


def _actionability_multiplier(entry: dict) -> float:
    """Boost notes with clear next actions, blockers, or explicit action items."""
    text = _note_text(entry)
    score = 0.0

    if _ACTION_CUE_RE.search(text):
        score += 0.4

    bullet_count = len(_BULLET_RE.findall(text))
    if bullet_count >= 2:
        score += 0.25
    elif bullet_count == 1:
        score += 0.15

    action_items = entry.get("action_items", [])
    if isinstance(action_items, list):
        valid_items = [str(x).strip() for x in action_items if str(x).strip()]
        if valid_items:
            score += min(0.45, 0.15 + (0.1 * len(valid_items)))

    score = max(0.0, min(1.0, score))
    # 1.00x .. 1.35x
    return 1.0 + (0.35 * score)


def _note_timestamp(entry: dict) -> str:
    """Get the best timestamp for recency sorting."""
    return entry.get("first_ts", entry.get("ts", ""))


def _load_all_notes(notes_dir: Path) -> list[dict]:
    """Load all note entries from JSONL files in the notes directory."""
    entries = []
    for jsonl_file in notes_dir.glob("*.jsonl"):
        try:
            with open(jsonl_file) as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        entries.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
        except OSError:
            continue
    return entries


def _select_notes(entries: list[dict]) -> list[tuple[float, dict]]:
    """Select notes with recency ceiling: always include the N most recent,
    then fill remaining slots by salience score."""
    if not entries:
        return []

    # Sort by timestamp descending to find most recent
    by_recency = sorted(entries, key=lambda e: _note_timestamp(e), reverse=True)

    # Always include the RECENCY_CEILING most recent notes
    recent = by_recency[:RECENCY_CEILING]
    recent_sessions = {e.get("session", "") for e in recent}

    # Score all remaining notes by salience
    remaining = [e for e in entries if e.get("session", "") not in recent_sessions]
    scored_remaining = [(_effective_salience(e), e) for e in remaining]
    scored_remaining.sort(key=lambda x: x[0], reverse=True)

    # Fill remaining budget with highest-salience notes
    budget = MAX_SALIENT_NOTES - len(recent)
    top_by_salience = scored_remaining[:budget]

    # Combine: recent notes (scored) + salience notes
    result = [(_effective_salience(e), e) for e in recent]
    result.extend(top_by_salience)

    # Sort final list by salience descending for display
    result.sort(key=lambda x: x[0], reverse=True)
    return result


def _format_notes(scored: list[tuple[float, dict]]) -> str:
    """Format selected notes as compact references."""
    parts = []
    for score, entry in scored:
        tags = entry.get("topic_tags", [])
        tag_str = ", ".join(tags) if tags else "untagged"
        raw_anti = entry.get("should_not_try", [])
        anti = []
        if isinstance(raw_anti, list):
            anti = [str(x).strip() for x in raw_anti if str(x).strip()]
        anti_str = f" avoid:{'; '.join(anti[:3])}" if anti else ""
        ts = entry.get("first_ts", entry.get("ts", ""))[:10]
        sid = entry.get("session", "")[:8]
        parts.append(f"  {ts} [{tag_str}] salience:{score:.2f} session:{sid}{anti_str}")
    return "\n".join(parts)


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

        # Add session notes with recency ceiling
        notes_dir = BASE_DIR / "data" / "notes"
        if notes_dir.exists():
            entries = _load_all_notes(notes_dir)
            if entries:
                selected = _select_notes(entries)
                if selected:
                    formatted = _format_notes(selected)
                    print(f"\n[Memorable] Most salient session notes ({len(entries)} total in {notes_dir}/):")
                    print(formatted)
                    print(f"To read a note: grep {notes_dir}/ for its session ID. To search by topic: grep by keyword.")

        # Surface memorable_search tool
        print("\n[Memorable] To search past sessions and observations, use the `memorable_search` MCP tool or the /memorable-search skill.")
        print("Use this when the user references past conversations, asks \"do you remember...\", or when you need historical context.")

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
