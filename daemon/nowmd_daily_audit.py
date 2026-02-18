#!/usr/bin/env python3
"""Daily now.md audit — reads raw transcripts to catch what session notes missed.

Reads actual Claude Code transcripts from the last 5 days, compares against
current now.md, and patches anything that was lost in the summarization pipeline.
Runs once daily via launchd.

Also used by the UI "Regenerate" button for deep passes.
"""

import json
import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

DATA_DIR = Path.home() / ".memorable" / "data"
NOW_PATH = DATA_DIR / "seeds" / "now.md"
CLAUDE_PROJECTS = Path.home() / ".claude" / "projects"
LOG_FILE = DATA_DIR.parent / "logs" / "nowmd-daily-audit.log"

# Must unset CLAUDECODE to allow CLI subprocess
os.environ.pop("CLAUDECODE", None)


def log(msg):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"{timestamp} - {msg}"
    print(line)
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(LOG_FILE, "a") as f:
        f.write(line + "\n")


def get_recent_transcripts(days=5):
    """Find and parse transcript JSONL files from the last N days.

    Returns list of dicts with session_id, messages (user/assistant text), timestamps.
    """
    cutoff = datetime.now() - timedelta(days=days)
    transcripts = []

    if not CLAUDE_PROJECTS.exists():
        return transcripts

    # Find all JSONL session files across all project dirs
    for jsonl_file in CLAUDE_PROJECTS.rglob("*.jsonl"):
        if "sync-conflict" in jsonl_file.name:
            continue
        # Check file modification time
        try:
            mtime = datetime.fromtimestamp(jsonl_file.stat().st_mtime)
            if mtime < cutoff:
                continue
        except OSError:
            continue

        session_id = jsonl_file.stem
        messages = []
        first_ts = None
        last_ts = None

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

                    ts = entry.get("timestamp")
                    if ts:
                        if first_ts is None:
                            first_ts = ts
                        last_ts = ts

                    if entry.get("isSidechain"):
                        continue

                    msg_type = entry.get("type")

                    if msg_type == "user":
                        content = entry.get("message", {}).get("content")
                        if isinstance(content, str) and content.strip():
                            messages.append(f"USER: {content.strip()}")
                        elif isinstance(content, list):
                            for block in content:
                                if isinstance(block, dict) and block.get("type") == "text":
                                    text = block.get("text", "").strip()
                                    if text:
                                        messages.append(f"USER: {text}")

                    elif msg_type == "assistant":
                        content = entry.get("message", {}).get("content")
                        if isinstance(content, str) and content.strip():
                            messages.append(f"ASSISTANT: {content.strip()}")
                        elif isinstance(content, list):
                            for block in content:
                                if isinstance(block, dict) and block.get("type") == "text":
                                    text = block.get("text", "").strip()
                                    if text:
                                        messages.append(f"ASSISTANT: {text}")
        except OSError:
            continue

        # Only include sessions with real conversation
        user_msgs = [m for m in messages if m.startswith("USER:")]
        if len(user_msgs) >= 2:
            transcripts.append({
                "session_id": session_id,
                "messages": messages,
                "first_ts": first_ts,
                "last_ts": last_ts,
                "file": str(jsonl_file),
            })

    # Sort by timestamp, newest first
    transcripts.sort(key=lambda t: t.get("last_ts") or "", reverse=True)
    return transcripts


AUDIT_PROMPT = """You are auditing a "now" document for an AI assistant. Your job is to read the RAW conversation transcripts and compare them against the current now.md to find ANYTHING that's missing, stale, or wrong.

Here is the current now.md:

---BEGIN NOW.MD---
{now_md}
---END NOW.MD---

Here are the raw conversation transcripts from the last 5 days (most recent first):

---BEGIN TRANSCRIPTS---
{transcripts}
---END TRANSCRIPTS---

Your task: Generate a COMPLETE, UPDATED now.md that incorporates everything from the transcripts. Don't just patch — write the full document from scratch, using the current now.md as a starting point but correcting and completing it based on the raw transcripts.

Pay special attention to:
- Open threads mentioned in conversations that aren't in now.md
- Decisions made that aren't recorded
- Things tried and abandoned (rejections) that aren't captured
- People mentioned who are missing
- Mood/emotional context that was sanitised or lost
- Technical details (file paths, commands, config values) that were dropped
- Anything in now.md that's now STALE or RESOLVED based on later transcripts

Output the full now.md document using this exact structure:

# Now

*Last updated: {date}*

## Active Focus
What the user is primarily working on or dealing with RIGHT NOW. 1-2 sentences.

## Current State
Bullet list of current situation — personal and technical. Be specific. No max.

## Last 5 Days
Day-by-day summary, most recent first. 2-3 lines per day.

## Recent Decisions
ALL decisions. Format: "Chose X over Y — reason." No maximum.

## Rejections
ALL things tried and abandoned. Format: "Tried/Considered X — rejected because Y." No maximum.

## Open Threads
EXHAUSTIVE list of unresolved items. This is the MOST IMPORTANT section. No maximum.

## People Mentioned Recently
One line each with context.

## Mood
Honest, specific, quote actual words.

Rules:
- Under 4000 words but err on the side of completeness
- COMPLETENESS IS CRITICAL — the cost of forgetting exceeds the cost of including too much
- Include technical details: file paths, tool names, config values
- Personal context is EQUALLY important to technical context
- Prioritise the most recent transcripts heavily"""


def audit(max_transcript_chars=120_000):
    """Run the daily audit. Also called by the server for deep regeneration."""
    transcripts = get_recent_transcripts()
    if not transcripts:
        log("No recent transcripts found")
        return False

    # Read current now.md
    current_now = ""
    if NOW_PATH.exists():
        current_now = NOW_PATH.read_text()

    # Build transcript text, cap at max_transcript_chars
    parts = []
    total = 0
    for t in transcripts:
        # Condense transcript: take user messages + short assistant responses
        condensed = []
        for msg in t["messages"]:
            if msg.startswith("USER:"):
                condensed.append(msg)
            elif msg.startswith("ASSISTANT:"):
                # Keep assistant messages but truncate long ones
                text = msg[11:]
                if len(text) > 500:
                    text = text[:500] + "..."
                condensed.append(f"ASSISTANT: {text}")

        session_text = f"\n### Session {t['session_id'][:8]}\n" + "\n".join(condensed)

        if total + len(session_text) > max_transcript_chars:
            break
        parts.append(session_text)
        total += len(session_text)

    transcripts_text = "\n\n".join(parts)
    today = datetime.now().strftime("%Y-%m-%d")

    prompt = (AUDIT_PROMPT
              .replace("{now_md}", current_now)
              .replace("{transcripts}", transcripts_text)
              .replace("{date}", today))

    log(f"Auditing now.md against {len(parts)} transcripts ({total} chars)")

    try:
        result = subprocess.run(
            ["claude", "-p", prompt, "--model", "claude-haiku-4-5-20251001", "--max-turns", "1"],
            capture_output=True, text=True, timeout=180,
            cwd=str(Path.home()),
        )
        if result.returncode != 0:
            log(f"ERROR: claude CLI failed: {result.stderr[:500]}")
            return False

        summary = result.stdout.strip()
        if not summary or len(summary) < 100:
            log(f"ERROR: Output too short ({len(summary)} chars), skipping write")
            return False

        NOW_PATH.parent.mkdir(parents=True, exist_ok=True)
        NOW_PATH.write_text(summary + "\n")
        log(f"SUCCESS: now.md audited and updated ({len(summary)} chars from {len(parts)} transcripts)")
        return True

    except subprocess.TimeoutExpired:
        log("ERROR: claude CLI timed out after 180s")
        return False
    except Exception as e:
        log(f"ERROR: {e}")
        return False


if __name__ == "__main__":
    audit()
