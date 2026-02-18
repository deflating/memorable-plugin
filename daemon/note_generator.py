"""Shared note generation logic for Memorable.

Extracts session transcripts, calls an LLM for structured notes,
writes them to ~/.memorable/data/notes/, and maintains salience +
rolling summaries. Used by both the daemon (idle detection) and
the session_end hook (fallback).
"""

import json
import logging
import math
import os
import re
import socket
import subprocess
import time
import urllib.request
import urllib.error
from datetime import datetime, timedelta, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

DATA_DIR = Path.home() / ".memorable" / "data"
CONFIG_PATH = DATA_DIR / "config.json"
LEGACY_CONFIG_PATH = Path.home() / ".memorable" / "config.json"
ERROR_LOG = Path.home() / ".memorable" / "hook-errors.log"

# Default LLM config
DEFAULT_PROVIDER = "deepseek"
DEFAULT_MODEL = "deepseek-chat"
DEFAULT_DEEPSEEK_ENDPOINT = "https://api.deepseek.com/v1"
DEFAULT_CLAUDE_CLI_COMMAND = "claude"
DEFAULT_CLAUDE_CLI_PROMPT_FLAG = "-p"

# Max chars of transcript to send to the LLM
MAX_TRANSCRIPT_CHARS = 80_000


def log_error(msg: str):
    try:
        with open(ERROR_LOG, "a") as f:
            f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] note_generator: {msg}\n")
    except Exception:
        pass


def get_config() -> dict:
    cfg = {}
    try:
        if CONFIG_PATH.exists():
            loaded = json.loads(CONFIG_PATH.read_text())
            if isinstance(loaded, dict):
                cfg = loaded
    except Exception:
        cfg = {}

    # Backward compatibility: keep reading legacy root config if present.
    try:
        if LEGACY_CONFIG_PATH.exists():
            legacy = json.loads(LEGACY_CONFIG_PATH.read_text())
            if isinstance(legacy, dict):
                # Preserve canonical values, but keep legacy summarizer block
                # available for fallback during migration.
                if "summarizer" in legacy and "summarizer" not in cfg:
                    cfg["summarizer"] = legacy["summarizer"]
                if not cfg:
                    cfg = legacy
    except Exception:
        pass

    return cfg


def get_machine_id(cfg: dict) -> str:
    mid = cfg.get("machine_id")
    if mid:
        return mid
    return socket.gethostname()


def parse_transcript(transcript_path: str) -> dict:
    """Parse a Claude Code JSONL transcript into structured content.

    Returns dict with:
      - messages: list of {"role": "user"|"assistant", "text": str} in order
      - tool_calls: list of {tool, target} dicts
      - message_count: int (user messages only)
      - first_ts / last_ts: timestamps
    """
    messages = []
    tool_calls = []
    first_ts = None
    last_ts = None

    try:
        with open(transcript_path, "r") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue

                ts = entry.get("timestamp")
                if ts:
                    if first_ts is None:
                        first_ts = ts
                    last_ts = ts

                msg_type = entry.get("type")
                if entry.get("isSidechain"):
                    continue

                if msg_type == "user":
                    message = entry.get("message", {})
                    content = message.get("content")
                    texts = []
                    if isinstance(content, str):
                        texts.append(content)
                    elif isinstance(content, list):
                        for block in content:
                            if isinstance(block, dict) and block.get("type") == "text":
                                texts.append(block.get("text", ""))
                    for text in texts:
                        clean = re.sub(
                            r'<system-reminder>.*?</system-reminder>',
                            '', text, flags=re.DOTALL
                        ).strip()
                        if clean and len(clean) > 3:
                            messages.append({"role": "user", "text": clean[:2000]})

                elif msg_type == "assistant":
                    message = entry.get("message", {})
                    content = message.get("content")
                    if isinstance(content, list):
                        for block in content:
                            if not isinstance(block, dict):
                                continue
                            if block.get("type") == "text":
                                text = block.get("text", "")
                                if text and len(text) > 10:
                                    messages.append({"role": "assistant", "text": text[:3000]})
                            elif block.get("type") == "tool_use":
                                tool_name = block.get("name", "")
                                tool_input = block.get("input", {})
                                target = (
                                    tool_input.get("file_path", "") or
                                    tool_input.get("path", "") or
                                    tool_input.get("pattern", "") or
                                    tool_input.get("command", "")
                                )
                                tool_calls.append({
                                    "tool": tool_name,
                                    "target": str(target)[:200],
                                })

    except Exception as e:
        log_error(f"parse_transcript error: {e}")

    user_count = sum(1 for m in messages if m["role"] == "user")
    return {
        "messages": messages,
        "tool_calls": tool_calls,
        "message_count": user_count,
        "first_ts": first_ts,
        "last_ts": last_ts,
    }


def build_llm_prompt(parsed: dict, session_id: str) -> str:
    """Build a prompt for the LLM to generate session notes."""

    # Build interleaved transcript
    parts = []
    parts.append("# Session Transcript\n")

    for msg in parsed["messages"]:
        role = "Matt" if msg["role"] == "user" else "Claude"
        text = msg["text"]
        if msg["role"] == "assistant" and len(text) > 500:
            text = text[:500] + "..."
        parts.append(f"**{role}:** {text}\n")

    # Notable tool calls
    notable_tools = [t for t in parsed["tool_calls"]
                     if t["tool"] in ("Edit", "Write", "Bash", "NotebookEdit",
                                      "mcp__deepseek__chat_completion",
                                      "mcp__deepseek__multi_turn_chat")]
    if notable_tools:
        parts.append("\n## Notable Tool Calls")
        for t in notable_tools[:30]:
            parts.append(f"- {t['tool']}: {t['target']}")

    transcript_text = "\n".join(parts)

    if len(transcript_text) > MAX_TRANSCRIPT_CHARS:
        transcript_text = transcript_text[:MAX_TRANSCRIPT_CHARS] + "\n\n[...truncated]"

    prompt = f"""You are a session note-taker for an AI coding assistant (Claude Code). You will receive a raw session transcript. Write structured session notes that capture both technical work and human context.

{transcript_text}

---

Output format (use only the sections that apply — skip empty ones):

## Summary
One paragraph. What happened in this session, in plain language.

## Decisions
Choices that were made and why. Format: "Chose X over Y — reason." These are high-value because they prevent the AI from re-suggesting rejected approaches.

## Rejections
Things that were explicitly tried or considered and didn't work or were abandoned. Include why if stated.

## Technical Context
- Project conventions discovered (test framework, file structure, naming patterns)
- Dependencies added or removed
- Bugs fixed (what was wrong, what fixed it)
- Files significantly modified
- Commands or workflows established

## User Preferences
Anything the user expressed a preference about — coding style, tools, approaches, communication style. Only include if explicitly stated or clearly demonstrated, not inferred.

## People & Life
Anyone mentioned by name and in what context. Life events, plans, situations discussed. This section exists because the AI is sometimes used as a companion, not just a coding tool — personal context matters for continuity.

## Mood
One or two words for the emotional register of the session (e.g. focused, frustrated, playful, low, excited). Then one sentence of context if relevant.

## Open Threads
Things left unfinished, unresolved, or explicitly marked for later. Questions that were raised but not answered. Plans stated but not executed.

---

Rules:
- Write in third person ("Matt did X", "Claude suggested Y"). Never use first person ("I").
- Be concise. Each bullet should be one line.
- Use the user's actual words where possible, especially for decisions and rejections.
- Don't editorialize or add interpretation. Just capture what happened.
- Don't summarize tool calls or file reads unless they led to something significant.
- If the session is purely technical with no personal content, skip People & Life and keep Mood brief.
- If the session is purely conversational with no code, skip Technical Context.
- The notes will be read by an AI at the start of a future session to establish context, so optimise for that use case.

After the markdown note, output exactly this metadata line (no extra text around it):
<!-- META: {{"topic_tags": ["tag1", "tag2", ...], "emotional_weight": 0.5}} -->

topic_tags: 3-5 short lowercase tags capturing the main topics (e.g. "memorable", "daemon", "mac-mini", "memory-system", "job-resignation"). Use consistent naming across sessions.
emotional_weight: float 0.0-1.0. Use 0.1-0.3 for routine technical sessions, 0.4-0.6 for sessions with meaningful decisions or progress, 0.7-1.0 for sessions with strong emotion, major life events, breakthroughs, or significant frustration."""

    return prompt


# -- LLM callers ----------------------------------------------------------


def _build_deepseek_chat_url(endpoint: str) -> str:
    endpoint = (endpoint or DEFAULT_DEEPSEEK_ENDPOINT).strip().rstrip("/")
    if endpoint.endswith("/chat/completions"):
        return endpoint
    if endpoint.endswith("/v1"):
        return endpoint + "/chat/completions"
    return endpoint + "/chat/completions"


def call_deepseek(
    prompt: str,
    api_key: str,
    model: str = DEFAULT_MODEL,
    endpoint: str = DEFAULT_DEEPSEEK_ENDPOINT,
) -> str:
    """Call DeepSeek API directly via HTTP."""
    url = _build_deepseek_chat_url(endpoint)
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }
    body = json.dumps({
        "model": model,
        "messages": [
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.3,
        "max_tokens": 2000,
    }).encode()

    req = urllib.request.Request(url, data=body, headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=60) as resp:
        data = json.loads(resp.read().decode())
    return data["choices"][0]["message"]["content"]


def call_gemini(prompt: str, api_key: str, model: str = "gemini-2.5-flash") -> str:
    """Call Gemini API directly via HTTP."""
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
    headers = {"Content-Type": "application/json"}
    body = json.dumps({
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.3, "maxOutputTokens": 2000},
    }).encode()

    req = urllib.request.Request(url, data=body, headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=60) as resp:
        data = json.loads(resp.read().decode())
    return data["candidates"][0]["content"]["parts"][0]["text"]


def call_claude(prompt: str, api_key: str, model: str = "claude-haiku-4-5-20251001") -> str:
    """Call Claude API directly via HTTP."""
    url = "https://api.anthropic.com/v1/messages"
    headers = {
        "Content-Type": "application/json",
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
    }
    body = json.dumps({
        "model": model,
        "max_tokens": 2000,
        "messages": [{"role": "user", "content": prompt}],
    }).encode()

    req = urllib.request.Request(url, data=body, headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=60) as resp:
        data = json.loads(resp.read().decode())
    return data["content"][0]["text"]


def call_claude_cli(prompt: str, cfg: dict) -> str:
    """Call Claude CLI via `claude -p <prompt>`."""
    command = DEFAULT_CLAUDE_CLI_COMMAND
    prompt_flag = DEFAULT_CLAUDE_CLI_PROMPT_FLAG

    cli_cfg = cfg.get("claude_cli", {})
    if isinstance(cli_cfg, dict):
        command = (cli_cfg.get("command") or command).strip() or command
        prompt_flag = (cli_cfg.get("prompt_flag") or prompt_flag).strip() or prompt_flag

    cmd = [command, prompt_flag, prompt]
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=240,
            check=False,
        )
    except FileNotFoundError as exc:
        raise ValueError(
            f"Claude CLI not found: '{command}'. Install Claude CLI or set claude_cli.command."
        ) from exc
    except subprocess.TimeoutExpired as exc:
        raise TimeoutError("Claude CLI timed out while generating output.") from exc

    if proc.returncode != 0:
        err = (proc.stderr or "").strip()
        raise RuntimeError(
            f"Claude CLI failed (exit {proc.returncode}). "
            f"{err if err else 'No stderr output from claude CLI.'}"
        )

    output = (proc.stdout or "").strip()
    if not output:
        raise RuntimeError("Claude CLI returned empty output.")
    return output


def _infer_provider(provider_hint: str, endpoint: str, model: str) -> str:
    hint = _normalize_provider_name(provider_hint)
    if hint in {"deepseek", "gemini", "claude_api", "claude_cli"}:
        return hint

    endpoint_hint = (endpoint or "").strip().lower()
    model_hint = (model or "").strip().lower()
    combined = f"{endpoint_hint} {model_hint}"

    if "anthropic" in combined or "claude" in combined:
        return "claude_api"
    if "googleapis" in combined or "generativelanguage" in combined or "gemini" in combined:
        return "gemini"
    if "deepseek" in combined:
        return "deepseek"
    return DEFAULT_PROVIDER


def _normalize_provider_name(provider: str) -> str:
    value = (provider or "").strip().lower().replace(" ", "_")
    if value in {"claude", "claude-api", "claude_api"}:
        return "claude_api"
    if value in {"claude-cli", "claude_cli"}:
        return "claude_cli"
    return value


def _normalize_route_name(route: str) -> str:
    value = (route or "").strip().lower().replace(" ", "_")
    if value in {"claude", "claude-cli", "claude_cli"}:
        return "claude_cli"
    if value in {"claude-api", "claude_api"}:
        return "claude_api"
    return value


def _resolve_task_route(cfg: dict, task: str, provider_fallback: str) -> str:
    routing = cfg.get("llm_routing", {})
    if isinstance(routing, dict):
        route_raw = routing.get(task)
        if isinstance(route_raw, str):
            route = _normalize_route_name(route_raw)
            if route in {"deepseek", "gemini", "claude_api", "claude_cli"}:
                return route

    if provider_fallback in {"claude", "claude_api"}:
        return "claude_api"
    if provider_fallback == "claude_cli":
        return "claude_cli"
    return provider_fallback


def _resolve_llm_settings(cfg: dict) -> dict:
    llm_provider = cfg.get("llm_provider", {})
    if not isinstance(llm_provider, dict):
        llm_provider = {}

    # Legacy migration fallback.
    summarizer = cfg.get("summarizer", {})
    if not isinstance(summarizer, dict):
        summarizer = {}

    endpoint = (llm_provider.get("endpoint") or summarizer.get("endpoint") or "").strip()
    model = (llm_provider.get("model") or summarizer.get("model") or "").strip()
    api_key = (llm_provider.get("api_key") or summarizer.get("api_key") or "").strip()
    provider_hint = llm_provider.get("provider") or summarizer.get("provider") or ""
    provider = _infer_provider(provider_hint, endpoint, model)

    enabled = True
    if "enabled" in summarizer:
        enabled = bool(summarizer.get("enabled", True))

    return {
        "provider": provider,
        "endpoint": endpoint,
        "model": model,
        "api_key": api_key,
        "enabled": enabled,
    }


def call_llm(prompt: str, cfg: dict, task: str = "session_notes") -> str:
    """Call the configured LLM provider for a specific task."""
    settings = _resolve_llm_settings(cfg)
    route = _resolve_task_route(cfg, task, settings["provider"])
    provider = "claude" if route == "claude_api" else route
    model = settings["model"]
    endpoint = settings["endpoint"]
    api_key = settings["api_key"]

    if route == "claude_cli":
        return call_claude_cli(prompt, cfg)

    # Fall back to env vars if no key in config
    if not api_key:
        if provider == "deepseek":
            api_key = os.environ.get("DEEPSEEK_API_KEY", "")
        elif provider == "gemini":
            api_key = os.environ.get("GOOGLE_AI_API_KEY", "") or os.environ.get("GEMINI_API_KEY", "")
        elif provider == "claude":
            api_key = os.environ.get("ANTHROPIC_API_KEY", "")

    if not api_key:
        raise ValueError(
            f"No API key found for provider '{provider}'. "
            f"Set ~/.memorable/data/config.json (llm_provider.api_key) "
            f"or use an environment variable."
        )

    if provider == "deepseek":
        return call_deepseek(
            prompt,
            api_key,
            model or DEFAULT_MODEL,
            endpoint or DEFAULT_DEEPSEEK_ENDPOINT,
        )
    elif provider == "gemini":
        return call_gemini(prompt, api_key, model or "gemini-2.5-flash")
    elif provider == "claude":
        return call_claude(prompt, api_key, model or "claude-haiku-4-5-20251001")
    else:
        raise ValueError(f"Unknown LLM provider: {provider}")


# -- Metadata parsing ------------------------------------------------------


def parse_meta(raw_response: str) -> tuple[str, list[str], float]:
    """Extract metadata from LLM response. Returns (note_text, topic_tags, emotional_weight)."""
    meta_match = re.search(r'<!-- META:\s*(\{.*?\})\s*-->', raw_response)
    if meta_match:
        note_text = raw_response[:meta_match.start()].strip()
        try:
            meta = json.loads(meta_match.group(1))
            tags = meta.get("topic_tags", [])
            weight = float(meta.get("emotional_weight", 0.3))
            weight = max(0.0, min(1.0, weight))
            return note_text, tags, weight
        except (json.JSONDecodeError, ValueError, TypeError):
            pass
    return raw_response.strip(), [], 0.3


# -- Salience --------------------------------------------------------------

DECAY_FACTOR = 0.97  # per-day decay (~0.4 after 30 days, ~0.16 after 60)
MIN_SALIENCE = 0.05
REINFORCEMENT_BOOST = 0.3  # added to salience when a topic recurs
SPACING_EFFECT_FACTOR = 0.004  # each access slows decay by this much (capped)
SPACING_EFFECT_CAP = 0.03  # max decay slowdown from repeated access


def effective_salience(entry: dict) -> float:
    """Calculate effective salience for a note entry.

    Uses an enhanced forgetting curve with:
    - Emotional weight as decay resistance
    - Spacing effect: frequently accessed notes decay slower
    - Novelty score bonus (if present)
    """
    salience = entry.get("salience", 1.0)
    emotional_weight = entry.get("emotional_weight", 0.3)
    reference_count = entry.get("reference_count", 0)
    novelty_score = entry.get("novelty_score", 0.0)

    last_ref = entry.get("last_referenced", entry.get("ts", ""))
    try:
        ts_clean = str(last_ref).replace("Z", "+00:00")
        dt = datetime.fromisoformat(ts_clean)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        days = (datetime.now(timezone.utc) - dt).total_seconds() / 86400
    except (ValueError, TypeError):
        days = 30  # assume old if unparseable

    # Emotional weight acts as decay resistance: higher weight = slower decay
    adjusted_days = days * (1.0 - emotional_weight * 0.5)

    # Spacing effect: frequently accessed memories decay slower
    spacing_bonus = min(SPACING_EFFECT_CAP, reference_count * SPACING_EFFECT_FACTOR)
    decay_rate = DECAY_FACTOR + spacing_bonus  # e.g. 0.97 -> 0.99 max

    decayed = salience * (decay_rate ** adjusted_days)

    # Novelty bonus: novel information gets a small persistent boost
    if novelty_score > 0:
        decayed += novelty_score * 0.15

    return max(MIN_SALIENCE, decayed)


def compute_novelty_score(notes_dir: Path, new_tags: list[str], note_text: str) -> float:
    """Score how novel a new note is compared to the existing corpus.

    Returns 0.0 (completely redundant) to 1.0 (entirely new information).
    Based on:
    - Tag overlap with existing recent notes (fewer shared tags = more novel)
    - Simple content similarity check via word overlap
    """
    if not new_tags and not note_text:
        return 0.5  # neutral if we can't assess

    existing_tags: dict[str, int] = {}
    existing_words: set[str] = set()
    note_count = 0
    cutoff = datetime.now(timezone.utc) - timedelta(days=30)

    for jsonl_file in notes_dir.glob("*.jsonl"):
        if "sync-conflict" in jsonl_file.name:
            continue
        try:
            with open(jsonl_file) as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        entry = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    # Only compare against recent notes
                    ts = entry.get("ts", "")
                    try:
                        ts_clean = str(ts).replace("Z", "+00:00")
                        dt = datetime.fromisoformat(ts_clean)
                        if dt.tzinfo is None:
                            dt = dt.replace(tzinfo=timezone.utc)
                        if dt < cutoff:
                            continue
                    except (ValueError, TypeError):
                        continue
                    note_count += 1
                    for tag in entry.get("topic_tags", []):
                        existing_tags[tag] = existing_tags.get(tag, 0) + 1
                    # Sample words from existing notes for content overlap
                    existing_note = entry.get("note", "")
                    if existing_note:
                        words = set(re.findall(r'[a-z]{3,}', existing_note.lower()))
                        existing_words.update(words)
        except OSError:
            continue

    if note_count == 0:
        return 1.0  # first note is maximally novel

    # Tag novelty: what fraction of new tags are unseen or rare?
    tag_novelty = 0.0
    if new_tags:
        novel_tags = sum(1 for t in new_tags if existing_tags.get(t, 0) <= 1)
        tag_novelty = novel_tags / len(new_tags)

    # Content novelty: what fraction of significant words are new?
    content_novelty = 0.5  # default
    if note_text and existing_words:
        new_words = set(re.findall(r'[a-z]{3,}', note_text.lower()))
        if new_words:
            novel_words = new_words - existing_words
            content_novelty = len(novel_words) / len(new_words)

    # Weighted combination: tags matter more for topic-level novelty
    return min(1.0, (tag_novelty * 0.6) + (content_novelty * 0.4))


def update_salience_on_new_note(notes_dir: Path, new_tags: list[str], new_session: str):
    """Scan existing notes and boost salience for those sharing topic tags with the new note."""
    if not new_tags:
        return

    new_tag_set = set(new_tags)
    now_iso = datetime.now(timezone.utc).isoformat()

    for jsonl_file in notes_dir.glob("*.jsonl"):
        if "sync-conflict" in jsonl_file.name:
            continue
        lines = []
        modified = False
        try:
            with open(jsonl_file) as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        lines.append("")
                        continue
                    try:
                        entry = json.loads(line)
                    except json.JSONDecodeError:
                        lines.append(line)
                        continue

                    # Don't boost the note we just wrote
                    if entry.get("session") == new_session:
                        lines.append(json.dumps(entry))
                        continue

                    entry_tags = set(entry.get("topic_tags", []))
                    overlap = entry_tags & new_tag_set
                    if overlap:
                        old_salience = entry.get("salience", 1.0)
                        boost = REINFORCEMENT_BOOST * (len(overlap) / max(len(entry_tags), 1))
                        entry["salience"] = min(2.0, old_salience + boost)
                        entry["last_referenced"] = now_iso
                        entry["reference_count"] = entry.get("reference_count", 0) + 1
                        modified = True

                    lines.append(json.dumps(entry))
        except OSError:
            continue

        if modified:
            try:
                with open(jsonl_file, "w") as f:
                    f.write("\n".join(lines) + "\n")
            except OSError as e:
                log_error(f"Failed to write salience updates to {jsonl_file}: {e}")


# -- Rolling summary -------------------------------------------------------

ROLLING_SUMMARY_PROMPT = """You are writing a "now" document for an AI assistant (Claude Code). This document is read at the start of every new session so Claude can quickly orient: what's happening right now, and how things got here.

This document should capture the FULL context of recent sessions — not just technical work. If the user discussed personal matters (job changes, stress, major life decisions, health, relationships), those are equally important to any code or project work. Reflect whatever actually matters in the conversations.

You will receive session notes from the last 5 days. Synthesise them into a comprehensive document.

Output this exact markdown structure:

# Now

*Last updated: {date}*

## Active Focus
What the user is primarily working on or dealing with RIGHT NOW. 1-2 sentences.

## Current State
What's the user's current situation? Cover both personal context (if discussed) and technical/project context. Be specific — names, statuses, details. Bullet list, no max.

## Last 5 Days
A day-by-day summary (most recent first). For each day, cover whatever was discussed — personal, technical, or both. Include emotional context where it appeared in the sessions. 2-3 lines per day.

## People Mentioned Recently
Anyone mentioned and their context (max 8, one line each). Include enough detail to be useful (role, relationship, what's happening with them).

## Recent Decisions
Important choices made — personal AND technical. Format: "Chose X over Y — reason." Include ALL decisions from the session notes, not just the ones that seem most important. If someone decided something, it goes here. No maximum.

## Rejections
Things that were tried, considered, or proposed and then abandoned or rejected. Format: "Tried/Considered X — rejected because Y." These are as important as decisions — they prevent future sessions from re-exploring dead ends. No maximum.

## Open Threads
Things left unresolved or explicitly marked for later — life decisions, project work, anything pending. Be EXHAUSTIVE. If a session note mentions something unfinished, blocked, or "we'll come back to this," it MUST appear here. This is the most important section — nothing gets dropped. No maximum.

## Mood
How the user has been feeling across recent sessions. Quote their actual words where possible. Be honest and specific, not sanitised. If they're struggling, say so clearly.

Rules:
- Keep the whole document under 4000 words. Err on the side of including too much rather than too little.
- Personal context (mood, life events, decisions, relationships, health) is EQUALLY important to technical context. If the user is going through something significant in their life, that should be prominent — not buried or omitted.
- Be concrete and specific, not vague.
- COMPLETENESS IS CRITICAL: Every open thread, every decision, every rejection from the session notes MUST be represented. If you're unsure whether to include something, INCLUDE IT. The cost of forgetting something far exceeds the cost of being slightly too long.
- Prioritise the most recent session heavily — that's the freshest context.
- Use the user's actual words where possible, especially about how they're feeling.
- Each session note below is prefixed with its DATE. Use ONLY those dates for the Last 5 Days section. Do NOT invent or guess dates. If no notes exist for a particular day, skip that day entirely.
- Include technical details: file paths, tool names, version numbers, config values. These matter for future sessions.
"""


def generate_rolling_summary(cfg: dict, notes_dir: Path):
    """Read last 5 days of notes and generate a rolling summary via LLM."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=5)
    entries = []

    for jsonl_file in notes_dir.glob("*.jsonl"):
        if "sync-conflict" in jsonl_file.name:
            continue
        try:
            with open(jsonl_file) as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        entry = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    ts = entry.get("ts", "")
                    if not ts:
                        continue
                    try:
                        ts_clean = str(ts).replace("Z", "+00:00")
                        dt = datetime.fromisoformat(ts_clean)
                        if dt.tzinfo is None:
                            dt = dt.replace(tzinfo=timezone.utc)
                        if dt < cutoff:
                            continue
                    except (ValueError, TypeError):
                        continue
                    entries.append(entry)
        except OSError:
            continue

    if not entries:
        log_error("Rolling summary: no recent notes found")
        return

    # Sort newest first
    entries.sort(key=lambda e: e.get("ts", ""), reverse=True)

    # Deduplicate: keep only the latest note per session.
    # Session notes are regenerated as transcripts grow, so a single long
    # session may produce many near-identical notes.  Only the final
    # (most recent) snapshot matters.
    seen_sessions: set[str] = set()
    deduped: list[dict] = []
    for entry in entries:
        sid = entry.get("session", "")
        if sid and sid in seen_sessions:
            continue
        if sid:
            seen_sessions.add(sid)
        deduped.append(entry)
    entries = deduped

    log_error(f"Rolling summary: {len(entries)} unique session notes after dedup")

    # Build input: concat notes with dates, cap at 60K chars
    parts = []
    total = 0
    for entry in entries:
        note = entry.get("note", "")
        if not note:
            continue
        ts = entry.get("ts", "")
        try:
            ts_clean = str(ts).replace("Z", "+00:00")
            dt = datetime.fromisoformat(ts_clean)
            date_str = dt.strftime("%Y-%m-%d")
        except (ValueError, TypeError):
            date_str = "unknown-date"
        dated_note = f"[DATE: {date_str}]\n{note}"
        if total + len(dated_note) > 60_000:
            break
        parts.append(dated_note)
        total += len(dated_note)

    notes_text = "\n\n---\n\n".join(parts)
    today = datetime.now().strftime("%Y-%m-%d")
    prompt_text = ROLLING_SUMMARY_PROMPT.replace("{date}", today)
    prompt_text += "\n\nHere are the session notes:\n\n" + notes_text

    summary = call_llm(prompt_text, cfg, task="now_md")

    # Write to seeds/now.md (replaces the old now.md entirely)
    now_path = DATA_DIR / "seeds" / "now.md"
    now_path.parent.mkdir(parents=True, exist_ok=True)
    now_path.write_text(summary.strip() + "\n")

    # Clean up old recent.md if it exists
    recent_path = DATA_DIR / "seeds" / "recent.md"
    if recent_path.exists():
        recent_path.unlink()

    log_error(f"SUCCESS: now.md written ({len(summary)} chars, {len(entries)} notes)")


# -- High-level entry point ------------------------------------------------


def generate_note(session_id: str, transcript_path: str, machine_id: str = None) -> bool:
    """Generate a session note from a transcript file.

    Returns True if a note was written, False otherwise.
    """
    cfg = get_config()
    if machine_id is None:
        machine_id = get_machine_id(cfg)

    llm_settings = _resolve_llm_settings(cfg)
    if not llm_settings.get("enabled", True):
        logger.info("Note generation disabled in config")
        return False

    # Parse the transcript
    parsed = parse_transcript(transcript_path)

    # Skip very short sessions (< 3 user messages)
    if parsed["message_count"] < 3:
        logger.info("Session too short (%d messages), skipping note", parsed["message_count"])
        return False

    # Build LLM prompt and call
    prompt = build_llm_prompt(parsed, session_id)
    raw_response = call_llm(prompt, cfg, task="session_notes")

    # Parse note text and metadata
    note_text, topic_tags, emotional_weight = parse_meta(raw_response)

    now_iso = datetime.now(timezone.utc).isoformat()

    # Use the session's own start time, not the processing time.
    # This ensures notes are dated when the conversation happened,
    # not when the daemon got around to summarising it.
    session_ts = parsed.get("first_ts") or now_iso

    # Compute novelty score against existing corpus
    novelty_score = 0.5  # default
    try:
        novelty_score = compute_novelty_score(notes_dir, topic_tags, note_text)
    except Exception as e:
        log_error(f"Novelty scoring failed (non-fatal): {e}")

    # Build the full entry with salience metadata
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

    # Write to notes JSONL — replace existing entry for this session if present
    notes_dir = DATA_DIR / "notes"
    notes_dir.mkdir(parents=True, exist_ok=True)
    notes_file = notes_dir / f"{machine_id}.jsonl"

    replaced = False
    if notes_file.exists():
        lines = []
        try:
            with open(notes_file) as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        existing = json.loads(line)
                    except json.JSONDecodeError:
                        lines.append(line)
                        continue
                    if existing.get("session") == session_id:
                        if not replaced:
                            # Replace first occurrence, preserve original salience boosts
                            entry["salience"] = max(entry["salience"], existing.get("salience", 1.0))
                            entry["reference_count"] = existing.get("reference_count", 0)
                            lines.append(json.dumps(entry))
                            replaced = True
                        # Skip any additional entries for the same session (dedup)
                    else:
                        lines.append(line)
            if replaced:
                with open(notes_file, "w") as f:
                    f.write("\n".join(lines) + "\n")
        except OSError as e:
            log_error(f"Failed to read/replace in {notes_file}: {e}")
            replaced = False

    if not replaced:
        # Check for duplicate note text before appending
        note_text = entry.get("note", "")
        dupe_text = False
        if notes_file.exists() and note_text:
            try:
                with open(notes_file) as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            existing = json.loads(line)
                            if existing.get("note", "") == note_text:
                                dupe_text = True
                                logger.info("Skipping duplicate note text for session %s", session_id)
                                break
                        except json.JSONDecodeError:
                            continue
            except OSError:
                pass
        if not dupe_text:
            with open(notes_file, "a") as f:
                f.write(json.dumps(entry) + "\n")

    logger.info("Note written for session %s (%d msgs, tags=%s, ew=%.1f)",
                session_id, parsed["message_count"], topic_tags, emotional_weight)
    log_error(f"SUCCESS: Note written for session {session_id} "
              f"({parsed['message_count']} msgs, tags={topic_tags}, ew={emotional_weight})")

    # Clean up any sync-conflict files in notes directory
    try:
        for conflict_file in notes_dir.glob("*.sync-conflict-*.jsonl"):
            conflict_file.unlink()
            logger.info("Removed sync-conflict file: %s", conflict_file.name)
    except Exception as e:
        logger.warning("Sync-conflict cleanup failed (non-fatal): %s", e)

    # Boost salience of related existing notes
    try:
        update_salience_on_new_note(notes_dir, topic_tags, session_id)
    except Exception as e:
        log_error(f"Salience update failed (non-fatal): {e}")

    # Regenerate rolling 5-day summary
    try:
        generate_rolling_summary(cfg, notes_dir)
    except Exception as e:
        log_error(f"Rolling summary failed (non-fatal): {e}")

    return True
