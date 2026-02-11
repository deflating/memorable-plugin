#!/usr/bin/env python3
"""now.md generation helpers for Memorable hooks."""

import re
from datetime import datetime, timezone
from pathlib import Path

BASE_DIR = Path.home() / ".memorable"
DATA_DIR = BASE_DIR / "data"
SEEDS_DIR = DATA_DIR / "seeds"

AUTO_NOW_MARKER = "<!-- memorable:auto-now -->"
_ACTION_CUE_RE = re.compile(
    r"\b(todo|next step|next steps|action(?:s| items?)?|follow[- ]?up|"
    r"decide|decision|blocked|blocker|unblock|deadline|ship|fix|implement|resolve)\b",
    re.IGNORECASE,
)


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def note_text(entry: dict) -> str:
    text = entry.get("note", "")
    return text if isinstance(text, str) else str(text)


def note_timestamp(entry: dict) -> str:
    return entry.get("first_ts", entry.get("ts", ""))


def clean_note_tags(value) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(tag).strip() for tag in value if str(tag).strip()]


def note_summary(entry: dict) -> str:
    text = note_text(entry)
    for line in text.splitlines():
        stripped = line.strip().lstrip("#").strip()
        if stripped and stripped.lower() != "summary":
            return stripped
    return "No summary"


def extract_open_threads(entries: list[dict]) -> list[str]:
    threads = []
    seen = set()
    for entry in entries:
        text = note_text(entry)
        for line in text.splitlines():
            cleaned = line.strip().lstrip("-*").strip()
            if not cleaned:
                continue
            if not _ACTION_CUE_RE.search(cleaned):
                continue
            key = cleaned.lower()
            if key in seen:
                continue
            seen.add(key)
            threads.append(cleaned)
            if len(threads) >= 6:
                return threads
    return threads


def theme_counts(entries: list[dict]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for entry in entries:
        for tag in clean_note_tags(entry.get("topic_tags", [])):
            counts[tag] = counts.get(tag, 0) + 1
    return counts


def theme_section_lines(top_tags: list[tuple[str, int]]) -> list[str]:
    if not top_tags:
        return ["- No clear themes yet"]
    return [f"- {tag} ({count})" for tag, count in top_tags]


def recent_highlight_lines(highlights: list[dict]) -> list[str]:
    if not highlights:
        return ["- No recent highlights yet"]
    lines: list[str] = []
    for entry in highlights:
        ts = note_timestamp(entry)[:10]
        summary = note_summary(entry)
        sid = str(entry.get("session", "")).strip()[:8]
        sid_suffix = f" [{sid}]" if sid else ""
        lines.append(f"- {ts}{sid_suffix}: {summary}")
    return lines


def open_thread_lines(open_threads: list[str]) -> list[str]:
    if not open_threads:
        return ["- No explicit open threads detected"]
    return [f"- {item}" for item in open_threads]


def generate_now_markdown(entries: list[dict]) -> str:
    now_iso = utc_now_iso()
    by_recency = sorted(entries, key=note_timestamp, reverse=True)
    highlights = by_recency[:6]
    tag_counts = theme_counts(entries)
    top_tags = sorted(tag_counts.items(), key=lambda kv: kv[1], reverse=True)[:6]
    open_threads = extract_open_threads(entries)
    lines = [
        "# Working Memory",
        "",
        AUTO_NOW_MARKER,
        "",
        f"_Auto-updated from session notes on {now_iso}_",
        "",
        "## Active Themes",
        "",
    ]
    lines.extend(theme_section_lines(top_tags))
    lines.extend(["", "## Recent Session Highlights", ""])
    lines.extend(recent_highlight_lines(highlights))
    lines.extend(["", "## Open Threads", ""])
    lines.extend(open_thread_lines(open_threads))
    return "\n".join(lines).strip() + "\n"


def maybe_update_now_md(selected_entries: list[dict]):
    try:
        SEEDS_DIR.mkdir(parents=True, exist_ok=True)
        now_path = SEEDS_DIR / "now.md"
        if now_path.exists():
            existing = now_path.read_text(encoding="utf-8")
            if AUTO_NOW_MARKER not in existing:
                return

        content = generate_now_markdown(selected_entries)
        now_path.write_text(content, encoding="utf-8")
    except Exception:
        pass
