#!/usr/bin/env python3
"""UserPromptSubmit hook for Memorable.

Lightweight hint — reminds Claude where deployed context lives
so it can recover after compaction or context loss.
"""

import sys
from pathlib import Path

DATA_DIR = Path.home() / ".memorable" / "data"
DEPLOYED_DIR = DATA_DIR / "seeds"


def main():
    try:
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
