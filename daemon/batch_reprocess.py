#!/usr/bin/env python3
"""Batch reprocess all session transcripts through Haiku.

Deletes all existing session notes, then reprocesses every transcript
that has >= 3 user messages. Uses claude CLI for speed (no SDK overhead).

Usage:
    python3 batch_reprocess.py [--dry-run] [--min-messages N] [--route claude_cli]
"""

import json
import logging
import os
import sys
import time
from pathlib import Path

# Add parent so we can import note_generator
sys.path.insert(0, str(Path(__file__).parent))

from note_generator import (
    parse_transcript,
    build_llm_prompt,
    parse_meta,
    compute_novelty_score,
    update_salience_on_new_note,
    _ingest_to_wax,
    get_config,
    get_machine_id,
    call_claude_cli,
    call_deepseek,
    DATA_DIR,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

PROJECTS_DIR = Path.home() / ".claude" / "projects"
NOTES_DIR = DATA_DIR / "notes"


def find_all_transcripts() -> list[tuple[str, Path]]:
    """Find all session transcript JSONL files, excluding subagents."""
    transcripts = []
    for jsonl_file in PROJECTS_DIR.rglob("*.jsonl"):
        if "subagents" in str(jsonl_file):
            continue
        if jsonl_file.parent.name.startswith("agent-"):
            continue
        session_id = jsonl_file.stem
        transcripts.append((session_id, jsonl_file))
    return transcripts


def clear_existing_notes():
    """Delete all existing session note JSONL files (preserving archive dir)."""
    if not NOTES_DIR.exists():
        return
    for f in NOTES_DIR.glob("*.jsonl"):
        logger.info("Deleting: %s", f.name)
        f.unlink()


def process_one(session_id: str, transcript_path: str, machine_id: str, cfg: dict) -> bool:
    """Process a single transcript using claude CLI (fast, no SDK overhead)."""
    from datetime import datetime, timezone

    parsed = parse_transcript(transcript_path)
    if parsed["message_count"] < 3:
        return False

    prompt = build_llm_prompt(parsed, session_id)

    # Use claude CLI with Haiku — fast, uses session token
    raw_response = call_claude_cli(prompt, cfg)

    note_text, topic_tags, emotional_weight = parse_meta(raw_response)

    now_iso = datetime.now(timezone.utc).isoformat()
    session_ts = parsed.get("first_ts") or now_iso

    notes_dir = NOTES_DIR
    notes_dir.mkdir(parents=True, exist_ok=True)

    novelty_score = 0.5
    try:
        novelty_score = compute_novelty_score(notes_dir, topic_tags, note_text)
    except Exception:
        pass

    entry = {
        "ts": session_ts,
        "session": session_id,
        "machine": machine_id,
        "message_count": parsed["message_count"],
        "first_ts": parsed["first_ts"],
        "last_ts": parsed["last_ts"],
        "note": note_text,
        "salience": 1.0,
        "emotional_weight": emotional_weight,
        "novelty_score": novelty_score,
        "topic_tags": topic_tags,
        "last_referenced": now_iso,
        "reference_count": 0,
    }

    notes_file = notes_dir / f"{machine_id}.jsonl"
    with open(notes_file, "a") as f:
        f.write(json.dumps(entry) + "\n")

    logger.info("Note: tags=%s, ew=%.1f", topic_tags, emotional_weight)

    return True


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--min-messages", type=int, default=3)
    parser.add_argument("--skip-delete", action="store_true")
    args = parser.parse_args()

    cfg = get_config()
    # Ensure CLI config uses Haiku, but respect existing command path from config
    existing_cli = cfg.get("claude_cli", {})
    cfg["claude_cli"] = {
        "command": existing_cli.get("command", "claude"),
        "prompt_flag": "-p",
        "model_flag": "--model",
        "model": "claude-haiku-4-5-20251001",
    }
    cfg["llm_routing"] = cfg.get("llm_routing", {})
    cfg["llm_routing"]["session_notes"] = "claude_cli"
    machine_id = get_machine_id(cfg)

    all_transcripts = find_all_transcripts()
    logger.info("Found %d total transcript files", len(all_transcripts))

    worthy = []
    for session_id, path in all_transcripts:
        parsed = parse_transcript(str(path))
        if parsed["message_count"] >= args.min_messages:
            worthy.append((session_id, path, parsed["message_count"]))

    worthy.sort(key=lambda x: x[2])
    logger.info("%d transcripts have >= %d user messages", len(worthy), args.min_messages)

    if args.dry_run:
        for sid, path, count in worthy:
            logger.info("  [DRY RUN] %s (%d msgs) %s", sid[:12], count, path)
        return

    if not args.skip_delete:
        logger.info("Clearing existing session notes...")
        clear_existing_notes()

    success = 0
    failed = 0
    skipped = 0
    total = len(worthy)

    for i, (session_id, path, msg_count) in enumerate(worthy, 1):
        logger.info("[%d/%d] Processing %s (%d msgs)...", i, total, session_id[:12], msg_count)
        try:
            result = process_one(session_id, str(path), machine_id, cfg)
            if result:
                success += 1
                logger.info("[%d/%d] OK", i, total)
            else:
                skipped += 1
        except Exception as e:
            failed += 1
            logger.error("[%d/%d] FAILED: %s", i, total, e)
        if i < total:
            time.sleep(0.5)

    logger.info("=" * 60)
    logger.info("DONE: %d success, %d skipped, %d failed out of %d", success, skipped, failed, total)

    # Regenerate now.md from fresh notes
    if success > 0:
        logger.info("Regenerating now.md from fresh notes...")
        try:
            from note_generator import generate_rolling_summary
            generate_rolling_summary(cfg, NOTES_DIR)
            logger.info("now.md regenerated!")
        except Exception as e:
            logger.error("now.md regen failed: %s", e)


if __name__ == "__main__":
    main()
