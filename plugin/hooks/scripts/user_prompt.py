#!/usr/bin/env python3
"""UserPromptSubmit hook for Memorable.

Lightweight hint — reminds Claude where deployed context lives
so it can recover after compaction or context loss.
"""

import json
import sys
from pathlib import Path

DEPLOYED_DIR = Path.home() / ".memorable" / "data" / "seeds"


def main():
    try:
        try:
            json.loads(sys.stdin.read())
        except (json.JSONDecodeError, EOFError):
            pass

        if not DEPLOYED_DIR.is_dir():
            return

        files = sorted(DEPLOYED_DIR.glob("*.md"))
        if not files:
            return

        names = ", ".join(f.name for f in files)
        print(f"[Memorable] Deployed context: {names} in {DEPLOYED_DIR}/")

    except Exception:
        pass


if __name__ == "__main__":
    main()
