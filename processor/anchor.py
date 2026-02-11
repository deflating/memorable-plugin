"""
Anchor processor for Semantic Memory.

Processes documents through an LLM to create tiered anchors using ⚓ emoji format.
Falls back to mechanical (heuristic) processing if no LLM is available.

Anchor levels (cumulative):
  0: Fingerprint — tags + one-line summary. Always loaded.
  1: Core ideas — the abstract.
  2: Supporting detail — arguments, examples, mechanisms.
  3: Everything worth keeping — near-complete minus filler.
  full: Raw unprocessed document.
"""

import json
import os
import re
import time
import urllib.request
import urllib.error
from dataclasses import dataclass
from pathlib import Path

# -- Paths -----------------------------------------------------------------

DATA_DIR = Path.home() / ".memorable" / "data"
FILES_DIR = DATA_DIR / "files"
LLM_CONFIG_PATH = DATA_DIR / "config.json"
LEGACY_LLM_CONFIG_PATH = Path.home() / ".memorable" / "config.json"
ERROR_LOG = Path.home() / ".memorable" / "hook-errors.log"

CHARS_PER_TOKEN = 4

# -- Anchor format constants -----------------------------------------------

ANCHOR = "⚓"
LEVEL_TAGS = {
    0: "0️⃣",
    1: "1️⃣",
    2: "2️⃣",
    3: "3️⃣",
}

# Regex: match ⚓ optionally followed by a level indicator (digit + variation selector + keycap)
_ANCHOR_RE = re.compile(ANCHOR + r"([0-3]\ufe0f\u20e3)?")


# -- LLM Prompt ------------------------------------------------------------

ANCHOR_PROMPT = """You are processing a document into a tiered anchor format for a memory system.

Use ⚓ emoji delimiters to mark content at different importance levels:
- ⚓0️⃣ ... ⚓ = Fingerprint. Two lines: first line is comma-separated topic tags, second line is a one-sentence summary describing what this document is about. Always loaded, minimal tokens.
- ⚓1️⃣ ... ⚓ = Core ideas. The abstract — what you'd tell someone in 30 seconds.
- ⚓2️⃣ ... ⚓ = Supporting detail. Key arguments, examples, mechanisms.
- ⚓3️⃣ ... ⚓ = Deep detail. Everything worth preserving minus filler.

⚓ alone (no number) is the CLOSING tag.

CRITICAL: Every opening ⚓N️⃣ MUST have a matching ⚓ close. Count your opens and closes — they must be equal. If you open ⚓1️⃣ then ⚓2️⃣ then ⚓3️⃣, you need THREE closing ⚓ tags: ⚓ ⚓ ⚓ (one for each level). Innermost closes first.

Rules:
1. First line of output must be ⚓0️⃣ fingerprint with tags on one line, then summary on the next
2. Levels nest: ⚓1️⃣ may contain ⚓2️⃣ which may contain ⚓3️⃣. Each MUST close with its own ⚓
3. Preserve the author's words — compress, don't paraphrase
4. Strip boilerplate and filler
5. Level 1 should be readable as a standalone summary

Example (note closing tag counts):
⚓0️⃣ memory-systems, extended-mind, cognitive-extension
External memory systems serve as genuine cognitive extensions through environmental coupling, offloading, and distributed processing. ⚓
⚓1️⃣ External memory systems function as genuine cognitive extensions, not just storage. ⚓2️⃣ Three mechanisms: environmental coupling, cognitive offloading, distributed processing. ⚓3️⃣ Environmental coupling: spatial arrangements serve as retrieval cues — 40% recall improvement when spatially organized vs listed. ⚓ ⚓ ⚓
                                                                                                                                                                                                         ↑ closes 3️⃣  ↑ closes 2️⃣  ↑ closes 1️⃣
⚓1️⃣ Design implication: systems should support relational organization, not just search. ⚓2️⃣ Three principles: proximity, salience, decay. ⚓ ⚓
                                                                                                                                               ↑ closes 2️⃣  ↑ closes 1️⃣

Filename: {filename}

{document_text}

Output the anchored version. Start with ⚓0️⃣. No preamble."""


# -- Utility ---------------------------------------------------------------


def log_error(msg: str):
    try:
        with open(ERROR_LOG, "a") as f:
            f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] anchor: {msg}\n")
    except Exception:
        pass


def estimate_tokens(text: str) -> int:
    """Rough token estimate: chars / 4."""
    return len(text) // CHARS_PER_TOKEN


def _load_llm_config() -> dict:
    """Load LLM config from ~/.memorable/data/config.json."""
    try:
        if LLM_CONFIG_PATH.exists():
            return json.loads(LLM_CONFIG_PATH.read_text(encoding="utf-8"))
    except Exception:
        pass
    # Backward compatibility for older installs
    try:
        if LEGACY_LLM_CONFIG_PATH.exists():
            return json.loads(LEGACY_LLM_CONFIG_PATH.read_text(encoding="utf-8"))
    except Exception:
        pass
    return {}


# -- LLM callers (copied from note_generator.py) --------------------------


def _call_deepseek(prompt: str, api_key: str, model: str = "deepseek-chat",
                   max_tokens: int = 4096, endpoint: str | None = None) -> str:
    base = (endpoint or "https://api.deepseek.com/v1").rstrip("/")
    url = base if base.endswith("/chat/completions") else f"{base}/chat/completions"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }
    body = json.dumps({
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.3,
        "max_tokens": max_tokens,
    }).encode()
    req = urllib.request.Request(url, data=body, headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=120) as resp:
        data = json.loads(resp.read().decode())
    return data["choices"][0]["message"]["content"]


def _call_gemini(prompt: str, api_key: str, model: str = "gemini-2.5-flash",
                 max_tokens: int = 4096) -> str:
    url = (f"https://generativelanguage.googleapis.com/v1beta/models/"
           f"{model}:generateContent?key={api_key}")
    headers = {"Content-Type": "application/json"}
    body = json.dumps({
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.3, "maxOutputTokens": max_tokens},
    }).encode()
    req = urllib.request.Request(url, data=body, headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=120) as resp:
        data = json.loads(resp.read().decode())
    return data["candidates"][0]["content"]["parts"][0]["text"]


def _call_claude(prompt: str, api_key: str, model: str = "claude-haiku-4-5-20251001",
                 max_tokens: int = 4096) -> str:
    url = "https://api.anthropic.com/v1/messages"
    headers = {
        "Content-Type": "application/json",
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
    }
    body = json.dumps({
        "model": model,
        "max_tokens": max_tokens,
        "messages": [{"role": "user", "content": prompt}],
    }).encode()
    req = urllib.request.Request(url, data=body, headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=120) as resp:
        data = json.loads(resp.read().decode())
    return data["content"][0]["text"]


def _resolve_provider(llm_cfg: dict) -> str:
    explicit = (llm_cfg.get("provider") or "").strip().lower()
    if explicit in ("deepseek", "gemini", "claude"):
        return explicit

    endpoint = (llm_cfg.get("endpoint") or "").lower()
    model = (llm_cfg.get("model") or "").lower()

    if "anthropic" in endpoint or model.startswith("claude"):
        return "claude"
    if "generativelanguage.googleapis.com" in endpoint or "gemini" in model:
        return "gemini"
    return "deepseek"


def call_llm(prompt: str, max_tokens: int = 4096) -> str:
    """Call the configured LLM provider using current config schema."""
    cfg = _load_llm_config()

    # Current schema: llm_provider {endpoint, api_key, model}
    llm_cfg = cfg.get("llm_provider", {})
    # Backward compatibility schemas
    if not isinstance(llm_cfg, dict) or not llm_cfg:
        llm_cfg = cfg.get("llm", {})
    if not isinstance(llm_cfg, dict) or not llm_cfg:
        llm_cfg = cfg.get("summarizer", {})

    if not isinstance(llm_cfg, dict):
        llm_cfg = {}

    provider = _resolve_provider(llm_cfg)
    model = llm_cfg.get("model")
    api_key = llm_cfg.get("api_key", "")
    endpoint = llm_cfg.get("endpoint")

    if not api_key:
        if provider == "deepseek":
            api_key = os.environ.get("DEEPSEEK_API_KEY", "")
        elif provider == "gemini":
            api_key = (os.environ.get("GOOGLE_AI_API_KEY", "")
                       or os.environ.get("GEMINI_API_KEY", ""))
        elif provider == "claude":
            api_key = os.environ.get("ANTHROPIC_API_KEY", "")

    if not api_key:
        raise ValueError(
            f"No API key for '{provider}'. Set llm_provider.api_key in "
            f"~/.memorable/data/config.json (llm_provider.api_key) or use an environment variable."
        )

    if provider == "deepseek":
        return _call_deepseek(
            prompt,
            api_key,
            model or "deepseek-chat",
            max_tokens,
            endpoint=endpoint,
        )
    elif provider == "gemini":
        return _call_gemini(prompt, api_key, model or "gemini-2.5-flash", max_tokens)
    elif provider == "claude":
        return _call_claude(prompt, api_key, model or "claude-haiku-4-5-20251001", max_tokens)
    else:
        raise ValueError(f"Unknown provider: {provider}")


# -- Extraction (reading anchored content) ---------------------------------


def extract_at_depth(anchored_text: str, max_depth: int) -> str:
    """Extract content from an anchored document up to max_depth.

    Depth semantics (cumulative):
      -1 or "full" → return raw unprocessed text
       0 → only ⚓0️⃣ content (fingerprint)
       1 → 0 + 1 (core ideas)
       2 → 0 + 1 + 2 (supporting detail)
       3 → 0 + 1 + 2 + 3 (everything anchored)

    Returns extracted text with anchor markers stripped.
    """
    if max_depth < 0:
        return anchored_text

    result = []
    pos = 0
    depth_stack = []

    for match in _ANCHOR_RE.finditer(anchored_text):
        level_str = match.group(1)
        start = match.start()
        end = match.end()

        if level_str:
            # Opening tag — extract the digit
            level = int(level_str[0])
            # Capture text before this tag if we're at an included depth
            if depth_stack and depth_stack[-1] <= max_depth:
                result.append(anchored_text[pos:start])
            elif not depth_stack and pos == 0:
                # Text before any anchor — include it
                before = anchored_text[:start].strip()
                if before:
                    result.append(before + " ")
            depth_stack.append(level)
            pos = end
        else:
            # Closing tag (bare ⚓)
            if depth_stack:
                if depth_stack[-1] <= max_depth:
                    result.append(anchored_text[pos:start])
                depth_stack.pop()
            pos = end

    # Capture trailing text
    if depth_stack and depth_stack[-1] <= max_depth:
        result.append(anchored_text[pos:])
    elif not depth_stack:
        trailing = anchored_text[pos:].strip()
        if trailing:
            result.append(trailing)

    text = "".join(result).strip()
    # Clean up whitespace: collapse multiple spaces/newlines
    text = re.sub(r" {2,}", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text


def validate_anchored(text: str) -> bool:
    """Check that anchored text has at least one ⚓0️⃣ tag."""
    return ANCHOR + LEVEL_TAGS[0] in text


def _repair_anchored(text: str) -> str:
    """Fix unbalanced anchor tags in LLM output.

    Walks through the text tracking the depth stack. Removes orphan closing
    tags (closes with no matching open) and appends missing closes at the end.
    """
    # Strip the ↑ annotation lines the prompt example might cause LLMs to echo
    text = re.sub(r"^[ \t]*↑[^\n]*$", "", text, flags=re.MULTILINE)
    text = re.sub(r"\n{3,}", "\n\n", text)

    # First pass: find positions of orphan closing tags to remove
    depth_stack = []
    orphan_positions = []

    for match in _ANCHOR_RE.finditer(text):
        level_str = match.group(1)
        if level_str:
            depth_stack.append(int(level_str[0]))
        else:
            if depth_stack:
                depth_stack.pop()
            else:
                # This close has no matching open — mark for removal
                orphan_positions.append((match.start(), match.end()))

    # Remove orphan closes (process in reverse to preserve positions)
    if orphan_positions:
        parts = []
        prev_end = 0
        for start, end in orphan_positions:
            parts.append(text[prev_end:start])
            prev_end = end
        parts.append(text[prev_end:])
        text = "".join(parts)

    # Second pass: count remaining balance and append missing closes
    depth_stack = []
    for match in _ANCHOR_RE.finditer(text):
        level_str = match.group(1)
        if level_str:
            depth_stack.append(int(level_str[0]))
        else:
            if depth_stack:
                depth_stack.pop()

    if depth_stack:
        text = text.rstrip()
        text += " " + " ".join([ANCHOR] * len(depth_stack))

    return text


# -- LLM Processing --------------------------------------------------------


def process_document_llm(text: str, filename: str) -> str:
    """Process a document through the configured LLM to create anchors.

    Returns the anchored text in ⚓ format.
    """
    # Dynamic max_tokens: 1.5x input tokens, floor 4096, cap 16384
    input_tokens = estimate_tokens(text)
    max_tokens = min(16384, max(4096, int(input_tokens * 1.5)))

    # Build prompt — truncate very long documents to stay within context window
    prompt = ANCHOR_PROMPT.replace("{filename}", filename).replace("{document_text}", text)
    if len(prompt) > 120_000:
        # Truncate document, keeping first and last portions
        max_doc = 100_000
        half = max_doc // 2
        truncated = text[:half] + "\n\n[...middle truncated for processing...]\n\n" + text[-half:]
        prompt = ANCHOR_PROMPT.replace("{filename}", filename).replace("{document_text}", truncated)

    return call_llm(prompt, max_tokens)


# -- Mechanical Fallback ---------------------------------------------------


@dataclass
class AnnotatedLine:
    text: str
    level: int  # 1, 2, or 3


def _is_heading(line: str) -> int:
    stripped = line.strip()
    if not stripped.startswith("#"):
        return 0
    match = re.match(r"^(#{1,6})\s", stripped)
    return len(match.group(1)) if match else 0


def _is_list_item(line: str) -> bool:
    stripped = line.strip()
    return bool(re.match(r"^[-*+]\s", stripped) or re.match(r"^\d+[.)]\s", stripped))


def _has_bold(line: str) -> bool:
    return bool(re.search(r"\*\*[^*]+\*\*", line))


def _is_blank(line: str) -> bool:
    return line.strip() == ""


def _is_code_fence(line: str) -> bool:
    return line.strip().startswith("```")


def process_document_mechanical(text: str) -> str:
    """Fallback: mechanical anchor processing using document structure.

    Maps the old 3-level system (1=highest, 2=medium, 3=full) to ⚓ format:
      Old level 1 (title, H1, first para, bold) → ⚓1️⃣
      Old level 2 (H2+, lists, definitions)     → ⚓2️⃣
      Old level 3 (everything else)              → ⚓3️⃣
    Plus a generated ⚓0️⃣ fingerprint line.
    """
    lines = text.split("\n")

    # Generate fingerprint (⚓0️⃣)
    first_heading = ""
    tags = []
    for line in lines:
        h = _is_heading(line)
        if h > 0:
            heading_text = line.strip().lstrip("#").strip()
            if not first_heading:
                first_heading = heading_text
            tags.append(heading_text.lower().replace(" ", "-"))

    tags = tags[:5]
    tag_str = ", ".join(tags) if tags else "untagged"
    first_nonblank = next((ln.strip() for ln in lines if ln.strip()), "")
    summary = first_heading or first_nonblank[:80] or "No summary"

    # First pass: assign a heuristic level to each line
    annotated: list[AnnotatedLine] = []
    in_code_block = False
    after_heading = False
    first_content_line = True

    for raw_line in lines:
        line = raw_line.rstrip()

        if _is_code_fence(line):
            in_code_block = not in_code_block
            annotated.append(AnnotatedLine(line, 3))
            first_content_line = False
            after_heading = False
            continue

        if in_code_block:
            annotated.append(AnnotatedLine(line, 3))
            continue

        if _is_blank(line):
            annotated.append(AnnotatedLine("", 0))
            continue

        heading_level = _is_heading(line)
        stripped = line.strip()

        if heading_level == 1 or (first_content_line and heading_level == 0):
            annotated.append(AnnotatedLine(stripped, 1))
            after_heading = True
            first_content_line = False
            continue

        first_content_line = False

        if heading_level >= 2:
            annotated.append(AnnotatedLine(stripped, 2))
            after_heading = True
            continue

        if after_heading:
            annotated.append(AnnotatedLine(stripped, 1))
            after_heading = False
            continue

        if _has_bold(line) or _is_list_item(line):
            annotated.append(AnnotatedLine(stripped, 2))
            continue

        annotated.append(AnnotatedLine(stripped, 3))

    # Second pass: emit valid nested anchors using a level stack
    parts = [f"{ANCHOR}{LEVEL_TAGS[0]} {tag_str}\n{summary} {ANCHOR}\n"]
    open_levels: list[int] = []

    def close_until(level: int):
        while open_levels and open_levels[-1] > level:
            open_levels.pop()
            parts.append(f"{ANCHOR}\n")

    for ann in annotated:
        if ann.level == 0:
            parts.append("\n")
            continue

        close_until(ann.level)
        if not open_levels or open_levels[-1] < ann.level:
            parts.append(f"{ANCHOR}{LEVEL_TAGS[ann.level]} ")
            open_levels.append(ann.level)
        parts.append(f"{ann.text}\n")

    close_until(0)

    out = "".join(parts).strip() + "\n"
    out = re.sub(r"\n{3,}", "\n\n", out)
    return out


# -- High-level API --------------------------------------------------------


def process_file(filename: str, force: bool = False) -> dict:
    """Process a file in FILES_DIR, creating {filename}.anchored.

    Returns:
        {
            "status": "ok" | "error" | "skipped",
            "method": "llm" | "mechanical" | None,
            "tokens_by_depth": {0: N, 1: N, 2: N, 3: N, "full": N} | None,
            "error": str | None,
        }
    """
    raw_path = FILES_DIR / filename
    anchored_path = FILES_DIR / (filename + ".anchored")

    if not raw_path.is_file():
        return {"status": "error", "method": None,
                "tokens_by_depth": None, "error": "File not found"}

    if anchored_path.exists() and not force:
        return {"status": "skipped", "method": None,
                "tokens_by_depth": None, "error": None}

    try:
        text = raw_path.read_text(encoding="utf-8")
    except Exception as e:
        return {"status": "error", "method": None,
                "tokens_by_depth": None, "error": f"Read error: {e}"}

    method = "llm"
    try:
        anchored = process_document_llm(text, filename)
        if not validate_anchored(anchored):
            raise ValueError("LLM output missing ⚓0️⃣ fingerprint — falling back")
        anchored = _repair_anchored(anchored)
    except Exception as e:
        log_error(f"LLM failed for {filename}: {e}")
        method = "mechanical"
        try:
            anchored = process_document_mechanical(text)
        except Exception as e2:
            log_error(f"Mechanical also failed for {filename}: {e2}")
            return {"status": "error", "method": None,
                    "tokens_by_depth": None, "error": str(e)}

    # Save anchored output
    anchored_path.write_text(anchored, encoding="utf-8")

    # Calculate token counts at each depth
    tokens_by_depth = {}
    for depth in range(4):
        extracted = extract_at_depth(anchored, depth)
        tokens_by_depth[depth] = estimate_tokens(extracted)
    tokens_by_depth["full"] = estimate_tokens(text)

    return {
        "status": "ok",
        "method": method,
        "tokens_by_depth": tokens_by_depth,
        "error": None,
    }


def get_file_info(filename: str) -> dict | None:
    """Return metadata about a file including anchor status."""
    raw_path = FILES_DIR / filename
    if not raw_path.is_file():
        return None

    anchored_path = FILES_DIR / (filename + ".anchored")
    is_anchored = anchored_path.is_file()

    try:
        stat = raw_path.stat()
        content = raw_path.read_text(encoding="utf-8")
        tokens_full = estimate_tokens(content)
    except Exception:
        return None

    tokens_by_depth = None
    if is_anchored:
        try:
            anchored_text = anchored_path.read_text(encoding="utf-8")
            tokens_by_depth = {}
            for depth in range(4):
                extracted = extract_at_depth(anchored_text, depth)
                tokens_by_depth[depth] = estimate_tokens(extracted)
        except Exception:
            pass

    from datetime import datetime, timezone
    return {
        "name": filename,
        "size": stat.st_size,
        "tokens": tokens_full,
        "tokens_by_depth": tokens_by_depth,
        "anchored": is_anchored,
        "modified": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(),
    }


def read_file_at_depth(filename: str, depth: int) -> str | None:
    """Read a file at the specified depth.

    If depth == -1 or no .anchored file exists, returns the raw file.
    Otherwise extracts anchored content at the given depth.
    """
    raw_path = FILES_DIR / filename
    anchored_path = FILES_DIR / (filename + ".anchored")

    if depth < 0 or not anchored_path.is_file():
        if raw_path.is_file():
            return raw_path.read_text(encoding="utf-8")
        return None

    try:
        anchored_text = anchored_path.read_text(encoding="utf-8")
        return extract_at_depth(anchored_text, depth)
    except Exception:
        if raw_path.is_file():
            return raw_path.read_text(encoding="utf-8")
        return None


def format_context_block(filename: str, depth: int, content: str,
                         tokens_by_depth: dict | None = None) -> str:
    """Format a semantic file for injection into Claude's context.

    Wraps the extracted content with a self-describing header that tells
    Claude what the document is, what depth it's loaded at, what other
    depths are available, and how to load more.

    Each document becomes its own instruction manual.
    """
    max_depth = 3 if tokens_by_depth else depth

    # Build available depths line
    depth_parts = []
    if tokens_by_depth:
        depth_labels = {0: "fingerprint", 1: "core", 2: "detail", 3: "complete"}
        for d in range(4):
            key = str(d) if str(d) in tokens_by_depth else d
            if key in tokens_by_depth and d > depth:
                label = depth_labels.get(d, f"depth {d}")
                depth_parts.append(f"{d} ({label}, ~{tokens_by_depth[key]} tokens)")

    # Build the raw file token count
    raw_path = FILES_DIR / filename
    full_tokens = None
    if raw_path.is_file():
        try:
            full_tokens = estimate_tokens(raw_path.read_text(encoding="utf-8"))
        except Exception:
            pass
    if full_tokens and (not tokens_by_depth or "full" not in tokens_by_depth):
        depth_parts.append(f"full (~{full_tokens} tokens)")
    elif tokens_by_depth and "full" in tokens_by_depth:
        depth_parts.append(f"full (~{tokens_by_depth['full']} tokens)")

    # Format the block
    lines = [f"[Semantic: {filename} (depth {depth}/{max_depth})]"]
    lines.append(content)
    if depth_parts:
        lines.append(f"Available depths: {', '.join(depth_parts)}")
    lines.append(f"Full document: ~/.memorable/data/files/{filename}")

    return "\n".join(lines)
