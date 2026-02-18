#!/usr/bin/env python3
"""Live observation extraction during active sessions.

Triggered by UserPromptSubmit hook every N messages. Reads the latest
chunk of the transcript, spawns a background Haiku agent to extract
observations, and appends them to a rolling file.

The rolling file (~/.memorable/data/stream/observations.jsonl) gets
pruned of entries older than 5 days at session start.
"""

import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path

DATA_DIR = Path.home() / ".memorable" / "data"
STREAM_DIR = DATA_DIR / "stream"
OBSERVATIONS_FILE = STREAM_DIR / "observations.jsonl"
STATE_FILE = STREAM_DIR / ".extraction-state.json"
CLAUDE_PROJECTS = Path.home() / ".claude" / "projects"

# Trigger extraction every N user messages
EXTRACT_EVERY_N = 15

# How many recent lines of transcript to send to Haiku
CHUNK_LINES = 200


def load_state():
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text())
        except (json.JSONDecodeError, OSError):
            pass
    return {"message_count": 0, "last_extraction_at": None, "session_id": None}


def save_state(state):
    STREAM_DIR.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state))


def get_current_session_id():
    """Find the most recently modified transcript."""
    newest = None
    newest_mtime = 0
    for project_dir in CLAUDE_PROJECTS.glob("*"):
        if not project_dir.is_dir():
            continue
        for jsonl_file in project_dir.glob("*.jsonl"):
            mtime = jsonl_file.stat().st_mtime
            if mtime > newest_mtime:
                newest_mtime = mtime
                newest = jsonl_file
    return newest


def read_recent_chunk(jsonl_path):
    """Read recent conversation from the transcript, formatted for extraction."""
    messages = []
    try:
        with open(jsonl_path, 'r') as f:
            lines = f.readlines()

        # Read from the end, collect recent messages
        for line in reversed(lines):
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue

            if entry.get("type") not in ("user", "assistant"):
                continue

            msg = entry.get("message", {})
            role = msg.get("role", "")
            content = msg.get("content")
            if not content:
                continue

            text = ""
            if isinstance(content, str):
                if content.startswith("You are"):
                    continue
                # Strip system reminders
                import re
                text = re.sub(r'<system-reminder>.*?</system-reminder>', '', content, flags=re.DOTALL).strip()
            elif isinstance(content, list):
                parts = []
                for block in content:
                    if block.get("type") == "text" and len(block.get("text", "")) > 5:
                        parts.append(block["text"])
                text = "\n".join(parts)

            if text and len(text) > 10:
                speaker = "Matt" if role == "user" else "Claude"
                messages.append(f"**{speaker}:** {text[:1000]}")

            if len(messages) >= CHUNK_LINES:
                break

    except Exception:
        return ""

    messages.reverse()
    return "\n\n".join(messages)


def spawn_extraction(chunk, session_id):
    """Spawn background Haiku extraction via SDK."""
    STREAM_DIR.mkdir(parents=True, exist_ok=True)

    # Write chunk to temp file for the extractor to read
    chunk_file = STREAM_DIR / ".current-chunk.txt"
    chunk_file.write_text(chunk)

    # Spawn the actual extraction as a detached background process
    extractor = Path(__file__).parent / "live_extractor_worker.py"
    env = os.environ.copy()
    env.pop("CLAUDECODE", None)

    subprocess.Popen(
        ["/opt/homebrew/bin/python3", str(extractor), str(chunk_file), session_id],
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=open(str(STREAM_DIR / "extractor.log"), "a"),
        start_new_session=True,
    )


def prune_old_observations(max_age_days=5):
    """Remove observations older than max_age_days."""
    if not OBSERVATIONS_FILE.exists():
        return

    cutoff = datetime.now(timezone.utc) - timedelta(days=max_age_days)
    cutoff_str = cutoff.isoformat()

    kept = []
    try:
        with open(OBSERVATIONS_FILE) as f:
            for line in f:
                try:
                    entry = json.loads(line)
                    if entry.get("ts", "") >= cutoff_str:
                        kept.append(line)
                except json.JSONDecodeError:
                    continue

        OBSERVATIONS_FILE.write_text("".join(kept))
    except Exception:
        pass


def main():
    try:
        hook_input = {}
        try:
            hook_input = json.loads(sys.stdin.read())
        except (json.JSONDecodeError, EOFError):
            pass

        state = load_state()

        # Find current session
        transcript = get_current_session_id()
        if not transcript:
            return

        session_id = transcript.stem

        # Reset counter if session changed
        if state.get("session_id") != session_id:
            state = {"message_count": 0, "last_extraction_at": None, "session_id": session_id}
            # Prune old observations on new session
            prune_old_observations()

        state["message_count"] = state.get("message_count", 0) + 1
        save_state(state)

        # Check if it's time to extract
        if state["message_count"] % EXTRACT_EVERY_N != 0:
            return

        # Read recent chunk
        chunk = read_recent_chunk(transcript)
        if not chunk or len(chunk) < 200:
            return

        # Spawn background extraction
        spawn_extraction(chunk, session_id)
        state["last_extraction_at"] = datetime.now(timezone.utc).isoformat()
        save_state(state)

    except Exception:
        # Never crash the hook
        pass


if __name__ == "__main__":
    main()
