#!/usr/bin/env python3
"""UserPromptSubmit hook for Memorable.

Extracts keywords from the user's prompt, searches the deep memory
FTS5 index and recent session notes, and injects relevant context
as a system reminder. Also reminds Claude where seed files live
for context recovery.
"""

import json
import re
import sqlite3
import sys
from pathlib import Path

DATA_DIR = Path.home() / ".memorable" / "data"
SEEDS_DIR = DATA_DIR / "seeds"
DEEP_DB = DATA_DIR / "deep_index.sqlite3"
NOTES_DIR = DATA_DIR / "notes"

# Words too common to be useful search terms
STOP_WORDS = {
    "i", "me", "my", "you", "your", "we", "our", "the", "a", "an", "is",
    "are", "was", "were", "be", "been", "being", "have", "has", "had", "do",
    "does", "did", "will", "would", "could", "should", "can", "may", "might",
    "shall", "to", "of", "in", "for", "on", "with", "at", "by", "from",
    "up", "about", "into", "through", "during", "before", "after", "above",
    "below", "between", "out", "off", "over", "under", "again", "further",
    "then", "once", "here", "there", "when", "where", "why", "how", "all",
    "each", "every", "both", "few", "more", "most", "other", "some", "such",
    "no", "nor", "not", "only", "own", "same", "so", "than", "too", "very",
    "just", "don", "now", "and", "but", "or", "if", "it", "its", "this",
    "that", "what", "which", "who", "whom", "these", "those", "am", "as",
    "he", "she", "they", "them", "his", "her", "him", "it", "let", "say",
    "said", "like", "also", "well", "back", "even", "still", "way", "take",
    "come", "go", "going", "went", "got", "get", "make", "made", "know",
    "think", "see", "look", "want", "give", "use", "find", "tell", "ask",
    "work", "seem", "feel", "try", "leave", "call", "need", "keep", "put",
    "mean", "become", "show", "hear", "play", "run", "move", "live", "right",
    "thing", "things", "much", "really", "yeah", "yes", "ok", "okay", "hey",
    "hi", "hello", "thanks", "thank", "please", "sure", "actually", "probably",
    "maybe", "something", "anything", "everything", "nothing", "someone",
    "anyone", "everyone", "lot", "bit", "kind", "sort", "stuff", "lol",
    "haha", "hmm", "uhh", "ahh", "oh", "ah", "um", "uh",
}

# Minimum keyword length
MIN_WORD_LEN = 3

# Max chunks to return from deep search
MAX_DEEP_RESULTS = 3

# Max characters per chunk to inject
MAX_CHUNK_CHARS = 400

# Minimum FTS rank to consider a result relevant (more negative = better match)
MAX_RANK = -5.0


def extract_keywords(text):
    """Extract meaningful keywords from user prompt."""
    # Remove URLs
    text = re.sub(r"https?://\S+", "", text)
    # Remove Signal: prefix
    text = re.sub(r"^Signal:\s*", "", text, flags=re.IGNORECASE)
    # Extract words, keep alphanumeric and hyphens
    words = re.findall(r"[a-zA-Z0-9][\w\'-]*[a-zA-Z0-9]|[a-zA-Z0-9]", text.lower())
    # Filter stop words and short words
    keywords = [w for w in words if w not in STOP_WORDS and len(w) >= MIN_WORD_LEN]
    # Deduplicate preserving order
    seen = set()
    unique = []
    for kw in keywords:
        if kw not in seen:
            seen.add(kw)
            unique.append(kw)
    return unique[:8]  # Cap at 8 keywords


def search_deep(keywords):
    """Search the FTS5 deep memory index."""
    if not DEEP_DB.exists() or not keywords:
        return []

    try:
        conn = sqlite3.connect(str(DEEP_DB))
        # Build FTS5 query — OR between keywords for broader matching
        fts_query = " OR ".join(keywords)
        cursor = conn.execute(
            """SELECT rowid, rank, substr(content, 1, ?)
               FROM deep_chunks_fts
               WHERE deep_chunks_fts MATCH ?
               ORDER BY rank
               LIMIT ?""",
            (MAX_CHUNK_CHARS, fts_query, MAX_DEEP_RESULTS),
        )
        results = []
        for rowid, rank, content in cursor:
            if rank > MAX_RANK:
                continue
            # Clean up the content — strip JSON artifacts
            clean = re.sub(r'[{}"\\]', " ", content)
            clean = re.sub(r"\s+", " ", clean).strip()
            if len(clean) > 50:  # Skip tiny fragments
                results.append(clean)
        conn.close()
        return results
    except Exception:
        return []


def search_notes(keywords):
    """Search recent session notes for keyword matches."""
    if not keywords:
        return []

    results = []
    try:
        for notes_file in NOTES_DIR.glob("*.jsonl"):
            with open(notes_file) as f:
                for line in f:
                    try:
                        entry = json.loads(line)
                    except (json.JSONDecodeError, ValueError):
                        continue
                    summary = entry.get("summary", "").lower()
                    # Check if any keyword appears in the summary
                    matches = sum(1 for kw in keywords if kw in summary)
                    if matches >= 2 or (matches >= 1 and len(keywords) <= 2):
                        ts = entry.get("ts", "")[:10]
                        results.append((matches, ts, entry.get("summary", "")))
        # Sort by match count descending, take top 2
        results.sort(key=lambda x: -x[0])
        return [f"[{ts}] {summary}" for _, ts, summary in results[:2]]
    except Exception:
        return []


def main():
    try:
        # Read hook input
        try:
            hook_input = json.loads(sys.stdin.read())
        except (json.JSONDecodeError, EOFError):
            hook_input = {}

        prompt = hook_input.get("prompt", "")

        # Always output context recovery hint
        if SEEDS_DIR.is_dir():
            files = sorted(SEEDS_DIR.glob("*.md"))
            if files:
                names = ", ".join(f.name for f in files)
                print(f"[Memorable] Deployed context: {names} in {SEEDS_DIR}/")

        # Extract keywords and search
        keywords = extract_keywords(prompt)
        if not keywords:
            return

        deep_results = search_deep(keywords)
        note_results = search_notes(keywords)

        if not deep_results and not note_results:
            return

        # Build context injection
        parts = []
        if deep_results:
            parts.append("[Memorable Deep Memory]")
            for i, chunk in enumerate(deep_results, 1):
                parts.append(f"  {i}. {chunk[:MAX_CHUNK_CHARS]}")
        if note_results:
            parts.append("[Memorable Session Notes]")
            for note in note_results:
                parts.append(f"  - {note[:300]}")

        print("\n".join(parts))

    except Exception:
        # Never crash the hook
        pass


if __name__ == "__main__":
    main()
