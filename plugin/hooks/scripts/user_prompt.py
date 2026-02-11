#!/usr/bin/env python3
"""UserPromptSubmit hook for Memorable.

Lightweight hint — reminds Claude where deployed context lives
so it can recover after compaction or context loss.
"""

import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

DATA_DIR = Path.home() / ".memorable" / "data"
DEPLOYED_DIR = DATA_DIR / "seeds"
NOTE_USAGE_PATH = DATA_DIR / "note_usage.json"
CURRENT_LOADED_NOTES_PATH = DATA_DIR / "current_loaded_notes.json"

_WORD_RE = re.compile(r"[A-Za-z0-9_']+")
_TEXT_KEYS = {"prompt", "input", "text", "message", "query", "content"}
_STOPWORDS = {
    "this", "that", "with", "from", "about", "have", "just", "into", "then",
    "than", "will", "would", "could", "should", "your", "their", "there",
    "where", "when", "what", "which", "also", "need", "make", "made", "using",
    "work", "project", "session", "notes", "context", "memory",
}


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_json(path: Path, fallback):
    try:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        pass
    return fallback


def _save_json(path: Path, payload):
    try:
        path.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
    except Exception:
        pass


def _collect_prompt_fragments(obj, fragments: list[str]):
    if isinstance(obj, dict):
        for k, v in obj.items():
            if isinstance(v, str) and k.lower() in _TEXT_KEYS and v.strip():
                fragments.append(v.strip())
            else:
                _collect_prompt_fragments(v, fragments)
    elif isinstance(obj, list):
        for item in obj:
            _collect_prompt_fragments(item, fragments)


def _extract_prompt_text(payload: dict) -> str:
    fragments: list[str] = []
    _collect_prompt_fragments(payload, fragments)
    return " ".join(fragments).strip()


def _tokenize(text: str) -> set[str]:
    return {w for w in _WORD_RE.findall(text.lower()) if len(w) >= 4}


def _note_matches_prompt(note: dict, prompt_lower: str, prompt_tokens: set[str]) -> bool:
    session = str(note.get("session", "")).strip().lower()
    short = str(note.get("session_short", "")).strip().lower()
    if session and session in prompt_lower:
        return True
    if short and len(short) >= 6 and short in prompt_lower:
        return True

    tags = note.get("tags", [])
    if not isinstance(tags, list):
        return False
    for tag in tags:
        tag_text = str(tag).strip().lower()
        if not tag_text:
            continue
        if tag_text in prompt_lower:
            return True
        tag_tokens = [t for t in _WORD_RE.findall(tag_text) if len(t) >= 4 and t not in _STOPWORDS]
        if tag_tokens and any(tok in prompt_tokens for tok in tag_tokens):
            return True
    return False


def _track_reference_effectiveness(payload: dict):
    current_loaded = _load_json(CURRENT_LOADED_NOTES_PATH, {"notes": []})
    notes = current_loaded.get("notes", []) if isinstance(current_loaded, dict) else []
    if not isinstance(notes, list) or not notes:
        return

    prompt_text = _extract_prompt_text(payload)
    if not prompt_text:
        return

    prompt_lower = prompt_text.lower()
    prompt_tokens = _tokenize(prompt_text)

    usage = _load_json(NOTE_USAGE_PATH, {"notes": {}})
    usage_notes = usage.get("notes", {}) if isinstance(usage, dict) else {}
    if not isinstance(usage_notes, dict):
        usage_notes = {}
        usage = {"notes": usage_notes}

    now_iso = _utc_now_iso()
    changed = False
    for note in notes:
        if not isinstance(note, dict):
            continue
        key = str(note.get("key", "")).strip()
        if not key:
            continue
        if not _note_matches_prompt(note, prompt_lower, prompt_tokens):
            continue

        rec = usage_notes.setdefault(
            key,
            {
                "loaded_count": 0,
                "referenced_count": 0,
                "first_loaded": now_iso,
            },
        )
        rec["referenced_count"] = int(rec.get("referenced_count", 0)) + 1
        rec["last_referenced"] = now_iso
        if "session" not in rec and note.get("session"):
            rec["session"] = note.get("session")
        if "session_short" not in rec and note.get("session_short"):
            rec["session_short"] = note.get("session_short")
        changed = True

    if changed:
        _save_json(NOTE_USAGE_PATH, usage)


def main():
    try:
        payload = {}
        try:
            payload = json.loads(sys.stdin.read())
        except (json.JSONDecodeError, EOFError):
            payload = {}

        _track_reference_effectiveness(payload)

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
