#!/usr/bin/env python3
"""UserPromptSubmit hook for Memorable.

Layered memory search: searches session notes and journals FIRST,
then falls back to the deep chat export only if nothing better was found.
Injects relevant context as a system reminder.
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
JOURNAL_DIR = Path.home() / "claude-memory" / "journal"
SIGNAL_CONV = Path.home() / "claude-memory" / "signal" / "conversation.md"

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
    "haha", "hmm", "uhh", "ahh", "oh", "ah", "um", "uh", "signal",
    "can", "don't", "i'm", "it's", "that's", "what's", "there's",
}

MIN_WORD_LEN = 3
MAX_RESULTS_PER_LAYER = 3
MAX_CHUNK_CHARS = 400
MAX_TOTAL_RESULTS = 5  # Total results across all layers


def extract_keywords(text):
    """Extract meaningful keywords from user prompt."""
    text = re.sub(r"https?://\S+", "", text)
    text = re.sub(r"^Signal:\s*", "", text, flags=re.IGNORECASE)
    words = re.findall(r"[a-zA-Z0-9][\w\'-]*[a-zA-Z0-9]|[a-zA-Z0-9]", text.lower())
    keywords = [w for w in words if w not in STOP_WORDS and len(w) >= MIN_WORD_LEN]
    seen = set()
    unique = []
    for kw in keywords:
        if kw not in seen:
            seen.add(kw)
            unique.append(kw)
    return unique[:8]


def search_notes(keywords):
    """Layer 1: Search session notes for keyword matches."""
    if not keywords:
        return []

    results = []
    seen_sessions = set()
    try:
        for notes_file in NOTES_DIR.glob("*.jsonl"):
            # Skip sync-conflict duplicates
            if "sync-conflict" in notes_file.name:
                continue
            # Skip backup files
            if notes_file.name.endswith(".bak"):
                continue
            with open(notes_file) as f:
                for line in f:
                    try:
                        entry = json.loads(line)
                    except (json.JSONDecodeError, ValueError):
                        continue

                    # Search in both note and summary fields
                    note_text = (entry.get("note", "") + " " + entry.get("summary", "")).lower()
                    tags = " ".join(entry.get("tags", [])).lower()
                    searchable = note_text + " " + tags

                    matches = sum(1 for kw in keywords if kw in searchable)

                    # Lower threshold: 1 match is enough
                    if matches >= 1:
                        session_id = entry.get("session", "")
                        # Deduplicate by session
                        if session_id in seen_sessions:
                            continue
                        seen_sessions.add(session_id)

                        ts = entry.get("ts", "")[:10]
                        # Use note field (richer), fall back to summary
                        content = entry.get("note", entry.get("summary", ""))
                        # Truncate to first ~300 chars for injection
                        if len(content) > 300:
                            content = content[:297] + "..."
                        results.append((matches, ts, content))

        results.sort(key=lambda x: -x[0])
        return [{"source": "session_notes", "ts": ts, "content": content}
                for _, ts, content in results[:MAX_RESULTS_PER_LAYER]]
    except Exception:
        return []


def search_journals(keywords):
    """Layer 2: Search journal entries for keyword matches."""
    if not keywords or not JOURNAL_DIR.exists():
        return []

    results = []
    try:
        for journal_file in sorted(JOURNAL_DIR.glob("*.md"), reverse=True):
            if journal_file.name in ("CLAUDE.md", "DIGEST.md", "README.md"):
                continue
            try:
                text = journal_file.read_text()[:3000]  # First 3k chars
            except Exception:
                continue

            text_lower = text.lower()
            matches = sum(1 for kw in keywords if kw in text_lower)

            if matches >= 1:
                # Extract first meaningful paragraph after the title
                lines = [l.strip() for l in text.split("\n") if l.strip() and not l.startswith("#") and not l.startswith("*") and not l.startswith("---")]
                snippet = " ".join(lines[:3])[:300]
                date = journal_file.name[:10]  # YYYY-MM-DD
                results.append((matches, date, snippet))

        results.sort(key=lambda x: -x[0])
        return [{"source": "journal", "ts": ts, "content": content}
                for _, ts, content in results[:MAX_RESULTS_PER_LAYER]]
    except Exception:
        return []


def search_deep(keywords):
    """Layer 3 (fallback): Search the FTS5 deep memory index (claude.ai chat export)."""
    if not DEEP_DB.exists() or not keywords:
        return []

    try:
        conn = sqlite3.connect(str(DEEP_DB))
        fts_query = " OR ".join(keywords)
        cursor = conn.execute(
            """SELECT rowid, rank, substr(content, 1, ?)
               FROM deep_chunks_fts
               WHERE deep_chunks_fts MATCH ?
               ORDER BY rank
               LIMIT ?""",
            (MAX_CHUNK_CHARS, fts_query, MAX_RESULTS_PER_LAYER),
        )
        results = []
        for rowid, rank, content in cursor:
            if rank > -5.0:
                continue
            clean = re.sub(r'[{}"\\]', " ", content)
            clean = re.sub(r"\s+", " ", clean).strip()
            if len(clean) > 50:
                results.append({"source": "chat_history", "ts": "", "content": clean[:MAX_CHUNK_CHARS]})
        conn.close()
        return results
    except Exception:
        return []


def main():
    try:
        try:
            hook_input = json.loads(sys.stdin.read())
        except (json.JSONDecodeError, EOFError):
            hook_input = {}

        prompt = hook_input.get("prompt", "")

        # Remind Claude to read seed files if not already done this session
        if SEEDS_DIR.is_dir():
            files = sorted(f for f in SEEDS_DIR.glob("*.md") if "sync-conflict" not in f.name)
            if files:
                names = ", ".join(f.name for f in files)
                print(f"[Memorable] Seed files available in {SEEDS_DIR}/: {names}. If you haven't read these this session, read them now before responding.")

        # Extract keywords and search
        keywords = extract_keywords(prompt)
        if not keywords:
            return

        # Layered search: session notes first, then journals, then deep fallback
        all_results = []

        # Layer 1: Session notes (highest priority — our shared history)
        note_results = search_notes(keywords)
        all_results.extend(note_results)

        # Layer 2: Journal entries (wakeup session writing)
        if len(all_results) < MAX_TOTAL_RESULTS:
            journal_results = search_journals(keywords)
            remaining = MAX_TOTAL_RESULTS - len(all_results)
            all_results.extend(journal_results[:remaining])

        # Layer 3: Deep chat export (fallback only if layers 1+2 found < 2 results)
        if len(all_results) < 2:
            deep_results = search_deep(keywords)
            remaining = MAX_TOTAL_RESULTS - len(all_results)
            all_results.extend(deep_results[:remaining])

        if not all_results:
            return

        # Build context injection grouped by source
        parts = []
        by_source = {}
        for r in all_results:
            by_source.setdefault(r["source"], []).append(r)

        source_labels = {
            "session_notes": "Memorable Session Notes",
            "journal": "Memorable Journal Entries",
            "chat_history": "Memorable Deep Memory (chat history)",
        }

        for source in ["session_notes", "journal", "chat_history"]:
            items = by_source.get(source, [])
            if items:
                parts.append(f"[{source_labels[source]}]")
                for item in items:
                    ts_prefix = f"[{item['ts']}] " if item['ts'] else ""
                    parts.append(f"  - {ts_prefix}{item['content'][:MAX_CHUNK_CHARS]}")

        print("\n".join(parts))

    except Exception:
        # Never crash the hook
        pass


if __name__ == "__main__":
    main()
