#!/usr/bin/env python3
"""Background worker: extract observations from a conversation chunk via Haiku.

Called by live_extraction.py as a detached subprocess.
Usage: python3 live_extractor_worker.py <chunk_file> <session_id>
"""

import asyncio
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from claude_code_sdk import query, ClaudeCodeOptions

STREAM_DIR = Path.home() / ".memorable" / "data" / "stream"
OBSERVATIONS_FILE = STREAM_DIR / "observations.jsonl"

EXTRACTION_PROMPT = """Extract observations from this conversation chunk. Be precise and concise.

Output a JSON array of observations. Each observation has:
- "type": one of "fact", "decision", "rejection", "preference", "open_thread", "person", "mood"
- "content": one sentence, standalone (makes sense without the conversation)
- "importance": 1-5 (5 = critical context for future sessions)

Types:
- fact: concrete factual statement (technical detail, project status, life event)
- decision: choice made and why ("Chose X over Y because Z")
- rejection: something tried/considered and abandoned ("Tried X, didn't work because Y")
- preference: user preference expressed (coding style, tools, communication)
- open_thread: unresolved question or pending item
- person: someone mentioned by name and context
- mood: emotional state or energy level

Rules:
- Only include observations directly supported by the text
- Each must be standalone — a future AI reading just that line should understand it
- Be specific: include names, dates, amounts, file paths when available
- Skip routine tool use, file reads, and mechanical exchanges
- 5-15 observations per chunk is typical
- If there's nothing worth extracting, return an empty array []

CONVERSATION CHUNK:
"""

HAIKU_MODEL = "claude-haiku-4-5-20251001"


async def extract(chunk_text, session_id):
    prompt = EXTRACTION_PROMPT + chunk_text

    result_text = ""
    try:
        async for message in query(
            prompt=prompt,
            options=ClaudeCodeOptions(
                model=HAIKU_MODEL,
                permission_mode="bypassPermissions",
                max_turns=1,
                system_prompt="You are a precise observation extraction system. Output only valid JSON arrays. No preamble, no explanation.",
            ),
        ):
            if hasattr(message, "content"):
                for block in message.content:
                    if hasattr(block, "text"):
                        result_text += block.text
    except Exception as e:
        log(f"SDK error: {e}")
        return

    # Parse the JSON array from Haiku's response
    result_text = result_text.strip()
    # Handle markdown code blocks
    if result_text.startswith("```"):
        lines = result_text.split("\n")
        result_text = "\n".join(lines[1:-1] if lines[-1].startswith("```") else lines[1:])

    try:
        observations = json.loads(result_text)
    except json.JSONDecodeError:
        # Try to find JSON array in the response
        import re
        match = re.search(r'\[.*\]', result_text, re.DOTALL)
        if match:
            try:
                observations = json.loads(match.group())
            except json.JSONDecodeError:
                log(f"Failed to parse Haiku output: {result_text[:200]}")
                return
        else:
            log(f"No JSON array found: {result_text[:200]}")
            return

    if not isinstance(observations, list):
        return

    # Append to observations file
    ts = datetime.now(timezone.utc).isoformat()
    STREAM_DIR.mkdir(parents=True, exist_ok=True)

    with open(OBSERVATIONS_FILE, "a") as f:
        for obs in observations:
            if not isinstance(obs, dict) or "content" not in obs:
                continue
            entry = {
                "ts": ts,
                "session": session_id,
                "type": obs.get("type", "fact"),
                "content": obs["content"],
                "importance": obs.get("importance", 3),
            }
            f.write(json.dumps(entry) + "\n")

    log(f"Extracted {len(observations)} observations from session {session_id[:8]}")


def log(msg):
    try:
        log_file = STREAM_DIR / "extractor.log"
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(log_file, "a") as f:
            f.write(f"{ts} - {msg}\n")
    except Exception:
        pass


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: live_extractor_worker.py <chunk_file> <session_id>")
        sys.exit(1)

    chunk_file = Path(sys.argv[1])
    session_id = sys.argv[2]

    if not chunk_file.exists():
        sys.exit(1)

    chunk = chunk_file.read_text()
    asyncio.run(extract(chunk, session_id))
