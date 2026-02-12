#!/usr/bin/env python3
"""Memorable background daemon.

Watches Claude Code session transcripts in real-time and generates
session notes when sessions go idle.

Usage:
    python3 memorable_daemon.py
    python3 memorable_daemon.py --no-notes   # watch only, no note generation
"""

import argparse
import logging
import os
from pathlib import Path

from transcript_watcher import watch_transcripts
from note_generator import generate_note

logger = logging.getLogger(__name__)

DATA_DIR = Path.home() / ".memorable" / "data"
PID_FILE = DATA_DIR / "daemon.pid"


class MemorableDaemon:
    """Main daemon that watches transcripts and generates session notes."""

    def __init__(self, enable_notes: bool = True):
        self.enable_notes = enable_notes

    def on_session_idle(self, session_id: str, transcript_path: str, human_count: int):
        """Called when a session goes idle. Generates a session note via LLM."""
        if not self.enable_notes:
            return

        # Skip subagent transcripts (session_id contains '/')
        if "/" in session_id:
            logger.debug("Skipping subagent session: %s", session_id)
            return

        if human_count < 3:
            logger.info("Session %s too short (%d msgs), skipping note", session_id, human_count)
            return

        logger.info("Generating note for idle session %s (%d human msgs)", session_id, human_count)

        try:
            success = generate_note(session_id, transcript_path)
            if success:
                logger.info("Note generated for session %s", session_id)
            else:
                logger.info("Note generation skipped for session %s", session_id)
        except Exception:
            logger.exception("Note generation failed for session %s", session_id)


def write_pid_file():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    PID_FILE.write_text(str(os.getpid()), encoding="utf-8")
    logger.info("PID file written: %s", PID_FILE)


def clear_pid_file():
    try:
        if not PID_FILE.exists():
            return
        current = PID_FILE.read_text(encoding="utf-8").strip()
        if current == str(os.getpid()):
            PID_FILE.unlink()
            logger.info("PID file cleared: %s", PID_FILE)
    except OSError:
        logger.exception("Failed to clear PID file")


def main():
    parser = argparse.ArgumentParser(description="Memorable background daemon")
    parser.add_argument("--no-notes", action="store_true", help="Disable session note generation")
    parser.add_argument("--idle-timeout", type=float, default=300.0, help="Seconds before flushing idle session")
    parser.add_argument("--log-level", type=str, default="INFO", choices=["DEBUG", "INFO", "WARNING", "ERROR"])
    args = parser.parse_args()

    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    daemon = MemorableDaemon(
        enable_notes=not args.no_notes,
    )

    logger.info("Memorable daemon starting")
    logger.info("  Notes: %s", "enabled" if not args.no_notes else "disabled")

    write_pid_file()
    try:
        watch_transcripts(
            on_chunk=None,
            on_human_message=None,
            on_session_idle=daemon.on_session_idle,
            chunk_every=10,
            idle_timeout=args.idle_timeout,
        )
    finally:
        clear_pid_file()


if __name__ == "__main__":
    main()
