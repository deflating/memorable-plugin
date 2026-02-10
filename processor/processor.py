"""
CLI wrapper for the weighted anchor processor.

Usage:
  python3 -m processor.processor --file doc.md --level 1   # level 1 only
  python3 -m processor.processor --file doc.md --level 2   # levels 1+2
  python3 -m processor.processor --file doc.md --annotate  # full with annotations
  python3 -m processor.processor --file doc.md             # full JSON output
"""

import argparse
import json
import sys
from pathlib import Path

from .anchor import process_full, extract_level, annotate_document


def main():
    parser = argparse.ArgumentParser(description="Weighted anchor document processor")
    parser.add_argument("--file", "-f", required=True, help="Path to document file")
    parser.add_argument("--level", "-l", type=int, choices=[1, 2, 3],
                        help="Output only content up to this level")
    parser.add_argument("--annotate", "-a", action="store_true",
                        help="Output full document with anchor annotations")
    parser.add_argument("--json", "-j", action="store_true",
                        help="Force JSON output (default when no --level or --annotate)")

    args = parser.parse_args()

    filepath = Path(args.file)
    if not filepath.exists():
        print(f"Error: File not found: {filepath}", file=sys.stderr)
        sys.exit(1)

    text = filepath.read_text(encoding="utf-8")

    if args.level:
        content = extract_level(text, args.level)
        if args.json:
            print(json.dumps({"content": content}, indent=2))
        else:
            print(content)
    elif args.annotate:
        content = annotate_document(text)
        if args.json:
            print(json.dumps({"content": content}, indent=2))
        else:
            print(content)
    else:
        # Default: full JSON output
        result = process_full(text)
        print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
