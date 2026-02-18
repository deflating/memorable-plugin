#!/usr/bin/env python3
"""Hourly now.md generator using Claude Haiku via claude CLI.

Reads session notes from the last 5 days and generates a comprehensive
now.md. Runs every hour via launchd.
"""

import json
import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

DATA_DIR = Path.home() / ".memorable" / "data"
NOTES_DIR = DATA_DIR / "notes"
NOW_PATH = DATA_DIR / "seeds" / "now.md"
LOG_FILE = DATA_DIR.parent / "logs" / "nowmd-hourly.log"

# Must unset CLAUDECODE to allow CLI subprocess
os.environ.pop("CLAUDECODE", None)


def log(msg):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"{timestamp} - {msg}"
    print(line)
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(LOG_FILE, "a") as f:
        f.write(line + "\n")


def get_recent_notes(days=5):
    """Read session notes from the last N days, deduplicated by session."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    entries = []

    for jsonl_file in NOTES_DIR.glob("*.jsonl"):
        if "sync-conflict" in jsonl_file.name:
            continue
        try:
            with open(jsonl_file) as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        entry = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    ts = entry.get("ts", "")
                    if not ts:
                        continue
                    try:
                        ts_clean = str(ts).replace("Z", "+00:00")
                        dt = datetime.fromisoformat(ts_clean)
                        if dt.tzinfo is None:
                            dt = dt.replace(tzinfo=timezone.utc)
                        if dt < cutoff:
                            continue
                    except (ValueError, TypeError):
                        continue
                    entries.append(entry)
        except OSError:
            continue

    # Sort newest first, dedup by session
    entries.sort(key=lambda e: e.get("ts", ""), reverse=True)
    seen = set()
    deduped = []
    for entry in entries:
        sid = entry.get("session", "")
        if sid and sid in seen:
            continue
        if sid:
            seen.add(sid)
        deduped.append(entry)

    return deduped


PROMPT_TEMPLATE = """You are writing a "now" document for an AI assistant (Claude Code). This document is read at the start of every new session so Claude can quickly orient: what's happening right now, and how things got here.

This document should capture the FULL context of recent sessions — not just technical work. If the user discussed personal matters (job changes, stress, major life decisions, health, relationships), those are equally important to any code or project work. Reflect whatever actually matters in the conversations.

You will receive session notes from the last 5 days. Synthesise them into a comprehensive document.

Output this exact markdown structure:

# Now

*Last updated: {date}*

## Active Focus
What the user is primarily working on or dealing with RIGHT NOW. 1-2 sentences.

## Current State
What's the user's current situation? Cover both personal context (if discussed) and technical/project context. Be specific — names, statuses, details. Bullet list, no max.

## Last 5 Days
A day-by-day summary (most recent first). For each day, cover whatever was discussed — personal, technical, or both. Include emotional context where it appeared in the sessions. 2-3 lines per day.

## Recent Decisions
Important choices made — personal AND technical. Format: "Chose X over Y — reason." Include ALL decisions from the session notes, not just the ones that seem most important. If someone decided something, it goes here. No maximum.

## Rejections
Things that were tried, considered, or proposed and then abandoned or rejected. Format: "Tried/Considered X — rejected because Y." These are as important as decisions — they prevent future sessions from re-exploring dead ends. No maximum.

## Open Threads
Things left unresolved or explicitly marked for later — life decisions, project work, anything pending. Be EXHAUSTIVE. If a session note mentions something unfinished, blocked, or "we'll come back to this," it MUST appear here. This is the most important section — nothing gets dropped. No maximum.

## People Mentioned Recently
Anyone mentioned and their context (one line each). Include enough detail to be useful (role, relationship, what's happening with them).

## Mood
How the user has been feeling across recent sessions. Quote their actual words where possible. Be honest and specific, not sanitised. If they're struggling, say so clearly.

Rules:
- Keep the whole document under 4000 words. Err on the side of including too much rather than too little.
- Personal context (mood, life events, decisions, relationships, health) is EQUALLY important to technical context.
- Be concrete and specific, not vague.
- COMPLETENESS IS CRITICAL: Every open thread, every decision, every rejection from the session notes MUST be represented. If you're unsure whether to include something, INCLUDE IT. The cost of forgetting something far exceeds the cost of being slightly too long.
- Prioritise the most recent session heavily — that's the freshest context.
- Use the user's actual words where possible, especially about how they're feeling.
- Don't include session timestamps or machine names.
- Include technical details: file paths, tool names, version numbers, config values. These matter for future sessions.

Here are the session notes:

{notes}"""


def generate():
    entries = get_recent_notes()
    if not entries:
        log("No recent notes found, skipping")
        return

    # Build notes text, cap at 60K chars
    parts = []
    total = 0
    for entry in entries:
        note = entry.get("note", "")
        if not note:
            continue
        if total + len(note) > 60_000:
            break
        parts.append(note)
        total += len(note)

    notes_text = "\n\n---\n\n".join(parts)
    today = datetime.now().strftime("%Y-%m-%d")
    prompt = PROMPT_TEMPLATE.replace("{date}", today).replace("{notes}", notes_text)

    log(f"Generating now.md from {len(entries)} notes ({total} chars)")

    try:
        result = subprocess.run(
            ["claude", "-p", prompt, "--model", "claude-haiku-4-5-20251001", "--max-turns", "1"],
            capture_output=True, text=True, timeout=120,
            cwd=str(Path.home()),
        )
        if result.returncode != 0:
            log(f"ERROR: claude CLI failed: {result.stderr[:500]}")
            return

        summary = result.stdout.strip()
        if not summary or len(summary) < 100:
            log(f"ERROR: Output too short ({len(summary)} chars), skipping write")
            return

        NOW_PATH.parent.mkdir(parents=True, exist_ok=True)
        NOW_PATH.write_text(summary + "\n")
        log(f"SUCCESS: now.md written ({len(summary)} chars from {len(entries)} notes)")

    except subprocess.TimeoutExpired:
        log("ERROR: claude CLI timed out after 120s")
    except Exception as e:
        log(f"ERROR: {e}")


if __name__ == "__main__":
    generate()
