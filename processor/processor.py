"""CLI wrapper for hierarchical semantic levels processor.

Usage:
  python3 -m processor.processor --file doc.md --process
  python3 -m processor.processor --file doc.md --level 1
  python3 -m processor.processor --file doc.md --json
"""

import argparse
import json
import sys
from pathlib import Path

from .levels import estimate_tokens, process_file, read_file_at_level, read_levels_file


def main():
    parser = argparse.ArgumentParser(description="Hierarchical levels document processor")
    parser.add_argument("--file", "-f", required=True, help="Filename under ~/.memorable/data/files")
    parser.add_argument("--level", "-l", type=int, help="Read at this semantic level")
    parser.add_argument("--process", action="store_true", help="Generate/update <file>.levels.json")
    parser.add_argument("--json", "-j", action="store_true", help="Force JSON output")

    args = parser.parse_args()

    if args.process:
        result = process_file(args.file, force=True)
        print(json.dumps(result, indent=2, ensure_ascii=False))
        if result.get("status") != "ok":
            sys.exit(1)
        return

    if args.level is not None:
        content = read_file_at_level(args.file, args.level)
        if content is None:
            print(f"Error: file not found: {args.file}", file=sys.stderr)
            sys.exit(1)
        if args.json:
            print(json.dumps({"level": args.level, "tokens": estimate_tokens(content), "content": content}, indent=2))
        else:
            print(content)
        return

    levels_doc = read_levels_file(args.file)
    if levels_doc is None:
        print(json.dumps({"status": "missing", "file": args.file, "message": "No levels file found"}, indent=2))
        return
    print(json.dumps(levels_doc, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
