#!/usr/bin/env python3
"""SessionStart / PreCompact hook for Memorable.

Reads deployed seed files (user.md, agent.md) and any enabled context files
from ~/.memorable/data/seeds/. Outputs system reminder text that
Claude will receive at session start or after context compaction.

Respects a configurable token budget (rough estimate: 4 chars ~ 1 token).
"""

import json
import sys
from pathlib import Path

BASE_DIR = Path.home() / ".memorable"
DEPLOYED_DIR = BASE_DIR / "data" / "seeds"
CONFIG_PATH = BASE_DIR / "data" / "config.json"

# Rough chars-per-token estimate for budget enforcement
CHARS_PER_TOKEN = 4
DEFAULT_TOKEN_BUDGET = 4000


def load_config() -> dict:
    try:
        if CONFIG_PATH.exists():
            return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except Exception:
        pass
    return {}


def estimate_tokens(text: str) -> int:
    return len(text) // CHARS_PER_TOKEN


def read_deployed_file(name: str) -> str | None:
    """Read a file from the deployed directory, return None if missing."""
    path = DEPLOYED_DIR / name
    if path.is_file():
        try:
            return path.read_text(encoding="utf-8").strip()
        except Exception:
            return None
    return None


def collect_context_files(config: dict) -> list[tuple[str, str]]:
    """Collect all enabled context files in priority order.

    Returns list of (label, content) tuples.
    Priority: user.md > agent.md > additional context files by config order.
    """
    files = []

    # Core seed files
    user_content = read_deployed_file("user.md")
    if user_content:
        files.append(("User profile", user_content))

    agent_content = read_deployed_file("agent.md")
    if agent_content:
        files.append(("Agent configuration", agent_content))

    # Additional context files (from config)
    context_files = config.get("context_files", [])
    for entry in context_files:
        if not entry.get("enabled", True):
            continue
        filename = entry.get("filename", "")
        if not filename:
            continue
        content = read_deployed_file(filename)
        if content:
            label = entry.get("label", filename)
            files.append((label, content))

    return files


def build_output(config: dict, is_compact: bool) -> str:
    """Build the system reminder text from deployed files."""
    budget = config.get("token_budget", DEFAULT_TOKEN_BUDGET)
    max_chars = budget * CHARS_PER_TOKEN

    files = collect_context_files(config)
    if not files:
        return ""

    prefix = "Memorable"
    if is_compact:
        header = f"[{prefix}] Context re-injected after compaction.\n\n"
    else:
        header = f"[{prefix}] Session context loaded.\n\n"

    parts = [header]
    used = len(header)

    for label, content in files:
        section = f"## {label}\n\n{content}\n\n"
        section_chars = len(section)

        if used + section_chars > max_chars:
            # Budget exceeded — truncate this section
            remaining = max_chars - used - len(f"## {label}\n\n") - len("\n\n[truncated — budget limit reached]\n\n")
            if remaining > 100:
                parts.append(f"## {label}\n\n{content[:remaining]}\n\n[truncated — budget limit reached]\n\n")
            break
        else:
            parts.append(section)
            used += section_chars

    return "".join(parts).strip()


def main():
    try:
        # Read stdin (hook input), though we don't use it
        try:
            json.loads(sys.stdin.read())
        except (json.JSONDecodeError, EOFError):
            pass

        is_compact = "--compact" in sys.argv

        config = load_config()
        output = build_output(config, is_compact)

        if output:
            print(output)

    except Exception as e:
        # Fail silently but log
        log_path = BASE_DIR / "hook-errors.log"
        try:
            import time
            with open(log_path, "a") as f:
                f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] session_start: {e}\n")
        except Exception:
            pass


if __name__ == "__main__":
    main()
