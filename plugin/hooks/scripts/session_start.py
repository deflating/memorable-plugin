#!/usr/bin/env python3
"""SessionStart / PreCompact hook for Memorable.

Reads deployed seed files (user.md, agent.md) and any enabled context files
from ~/.memorable/data/seeds/. Also loads semantic memory files from
~/.memorable/data/files/ at the configured anchor depth.

Outputs system reminder text that Claude will receive at session start
or after context compaction.

Respects a configurable token budget (rough estimate: 4 chars ~ 1 token).
"""

import json
import re
import sys
from pathlib import Path

BASE_DIR = Path.home() / ".memorable"
DEPLOYED_DIR = BASE_DIR / "data" / "seeds"
FILES_DIR = BASE_DIR / "data" / "files"
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


def _extract_at_depth(anchored_text: str, max_depth: int) -> str:
    """Extract content from anchored text up to max_depth level.

    Self-contained — no imports from processor (hooks must be standalone).
    Parses ⚓N️⃣...⚓ format.
    """
    if max_depth < 0:
        return anchored_text

    anchor = "⚓"
    pattern = re.compile(anchor + r"([0-3]\ufe0f\u20e3)?")

    result = []
    pos = 0
    depth_stack = []

    for match in pattern.finditer(anchored_text):
        level_str = match.group(1)
        start = match.start()
        end = match.end()

        if level_str:
            level = int(level_str[0])
            if depth_stack and depth_stack[-1] <= max_depth:
                result.append(anchored_text[pos:start])
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

    text = "".join(result).strip()
    text = re.sub(r" {2,}", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text


def _format_context_block(filename: str, depth: int, content: str,
                          tokens_by_depth: dict | None = None) -> str:
    """Format a semantic file as a self-describing context block.

    Every document becomes its own instruction manual — Claude reads the block
    and immediately knows what the document is, how much more detail is available,
    and exactly how to load more.
    """
    max_depth = 3 if tokens_by_depth else depth

    depth_parts = []
    if tokens_by_depth:
        depth_labels = {0: "fingerprint", 1: "core", 2: "detail", 3: "complete"}
        for d in range(4):
            key = str(d)
            if key in tokens_by_depth and d > depth:
                label = depth_labels.get(d, f"depth {d}")
                depth_parts.append(f"{d} ({label}, ~{tokens_by_depth[key]} tokens)")
        if "full" in tokens_by_depth:
            depth_parts.append(f"full (~{tokens_by_depth['full']} tokens)")

    lines = [f"[Semantic: {filename} (depth {depth}/{max_depth})]"]
    lines.append(content)
    if depth_parts:
        lines.append(f"Available depths: {', '.join(depth_parts)}")
    lines.append(f"Full document: ~/.memorable/data/files/{filename}")

    return "\n".join(lines)


def collect_context_files(config: dict) -> list[tuple[str, str]]:
    """Collect all enabled context files in priority order.

    Returns list of (label, content) tuples.
    Priority: user.md > agent.md > seed context files > semantic files.
    """
    files = []

    # Core seed files
    user_content = read_deployed_file("user.md")
    if user_content:
        files.append(("User profile", user_content))

    agent_content = read_deployed_file("agent.md")
    if agent_content:
        files.append(("Agent configuration", agent_content))

    # Additional context files from config
    context_files = config.get("context_files", [])
    for entry in context_files:
        if not entry.get("enabled", True):
            continue
        filename = entry.get("filename", "")
        if not filename:
            continue

        depth = entry.get("depth")

        # Try semantic file (from files dir) first
        raw_path = FILES_DIR / filename
        anchored_path = FILES_DIR / (filename + ".anchored")

        if raw_path.is_file():
            # This is a semantic memory file — format as self-describing block
            if depth is not None and depth >= 0 and anchored_path.is_file():
                try:
                    anch_text = anchored_path.read_text(encoding="utf-8")
                    content = _extract_at_depth(anch_text, depth)

                    # Compute token counts at each depth for the metadata
                    tokens_by_depth = {}
                    for d in range(4):
                        extracted = _extract_at_depth(anch_text, d)
                        tokens_by_depth[str(d)] = estimate_tokens(extracted)
                    tokens_by_depth["full"] = estimate_tokens(
                        raw_path.read_text(encoding="utf-8")
                    )

                    # Format as self-describing context block
                    block = _format_context_block(
                        filename, depth, content, tokens_by_depth
                    )
                    files.append((None, block))  # None label = raw block, no ## header
                except Exception:
                    content = raw_path.read_text(encoding="utf-8").strip()
                    files.append((f"Semantic: {filename}", content))
            else:
                content = raw_path.read_text(encoding="utf-8").strip()
                files.append((f"Semantic: {filename}", content))
            continue

        # Fall back to seed file
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
        if label is None:
            # Raw block (self-describing semantic file) — no ## header
            section = f"{content}\n\n"
        else:
            section = f"## {label}\n\n{content}\n\n"
        section_chars = len(section)

        if used + section_chars > max_chars:
            # Budget exceeded — truncate this section
            hdr = f"## {label}\n\n" if label else ""
            remaining = max_chars - used - len(hdr) - len("\n\n[truncated — budget limit reached]\n\n")
            if remaining > 100:
                parts.append(f"{hdr}{content[:remaining]}\n\n[truncated — budget limit reached]\n\n")
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
