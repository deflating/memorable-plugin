"""Hierarchical levels processor for semantic document zoom.

Generates `<filename>.levels.json` alongside uploaded source files.
Level `1` is always the tightest summary, and level `N` is full/near-full.
"""

from __future__ import annotations

import json
import os
import subprocess
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

DATA_DIR = Path.home() / ".memorable" / "data"
FILES_DIR = DATA_DIR / "files"
LLM_CONFIG_PATH = DATA_DIR / "config.json"
ERROR_LOG = Path.home() / ".memorable" / "hook-errors.log"

CHARS_PER_TOKEN = 4
DEFAULT_CLAUDE_CLI_COMMAND = "claude"
DEFAULT_CLAUDE_CLI_PROMPT_FLAG = "-p"
LEVELS_SUFFIX = ".levels.json"
LEVELS_VERSION = 1
MIN_LEVELS = 2
MAX_LEVELS = 8

LEVELS_PROMPT = """You are building a hierarchical semantic zoom representation for a document.

Return ONLY valid JSON (no markdown, no prose, no code fences) with this exact schema:
{
  "levels": <integer>,
  "content": {
    "1": "...",
    "2": "..."
  }
}

Rules:
- Choose number of levels based on document length and complexity.
- Allowed levels range: 2 to 8.
- Level 1 MUST be the most compressed possible summary (usually one short paragraph).
- Each next level adds meaningful detail.
- Highest level N MUST be near-full or full document fidelity.
- Keep facts and terminology accurate; do not invent details.
- Preserve structure where useful (headings/lists) at deeper levels.
- Ensure every key from "1" through "N" exists exactly once.
- Do not include any keys outside `levels` and `content`.

Filename: {filename}

Document:
{document_text}
"""


def _atomic_write(path: Path, content: str, encoding: str = "utf-8"):
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    tmp_path.write_text(content, encoding=encoding)
    tmp_path.rename(path)


def log_error(msg: str):
    try:
        with open(ERROR_LOG, "a") as f:
            f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] levels: {msg}\n")
    except Exception:
        pass


def estimate_tokens(text: str) -> int:
    return len(text) // CHARS_PER_TOKEN


def levels_path_for(filename: str) -> Path:
    return FILES_DIR / f"{filename}{LEVELS_SUFFIX}"


def read_levels_file(filename: str) -> dict | None:
    path = levels_path_for(filename)
    if not path.is_file():
        return None
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    return loaded if isinstance(loaded, dict) else None


def _load_llm_config() -> dict:
    try:
        if LLM_CONFIG_PATH.exists():
            return json.loads(LLM_CONFIG_PATH.read_text(encoding="utf-8"))
    except Exception:
        pass
    return {}


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
        "temperature": 0.2,
        "max_tokens": max_tokens,
    }).encode()
    req = urllib.request.Request(url, data=body, headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=180) as resp:
        data = json.loads(resp.read().decode())
    return data["choices"][0]["message"]["content"]


def _call_gemini(prompt: str, api_key: str, model: str = "gemini-2.5-flash",
                 max_tokens: int = 4096) -> str:
    url = (f"https://generativelanguage.googleapis.com/v1beta/models/"
           f"{model}:generateContent?key={api_key}")
    headers = {"Content-Type": "application/json"}
    body = json.dumps({
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.2, "maxOutputTokens": max_tokens},
    }).encode()
    req = urllib.request.Request(url, data=body, headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=180) as resp:
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
    with urllib.request.urlopen(req, timeout=180) as resp:
        data = json.loads(resp.read().decode())
    return data["content"][0]["text"]


def _call_claude_cli(prompt: str, cfg: dict) -> str:
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
            timeout=300,
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


def _normalize_provider_name(provider: str) -> str:
    value = (provider or "").strip().lower().replace(" ", "_")
    if value in {"claude", "claude-api", "claude_api"}:
        return "claude_api"
    if value in {"claude-cli", "claude_cli"}:
        return "claude_cli"
    return value


def _resolve_provider(llm_cfg: dict) -> str:
    explicit = _normalize_provider_name(llm_cfg.get("provider") or "")
    if explicit in {"deepseek", "gemini", "claude_api", "claude_cli"}:
        return explicit

    endpoint = (llm_cfg.get("endpoint") or "").lower()
    model = (llm_cfg.get("model") or "").lower()

    if "anthropic" in endpoint or model.startswith("claude"):
        return "claude_api"
    if "generativelanguage.googleapis.com" in endpoint or "gemini" in model:
        return "gemini"
    return "deepseek"


def _normalize_route_name(route: str) -> str:
    value = (route or "").strip().lower().replace(" ", "_")
    if value in {"claude", "claude-cli", "claude_cli"}:
        return "claude_cli"
    if value in {"claude-api", "claude_api"}:
        return "claude_api"
    return value


def _resolve_levels_route(cfg: dict, provider_fallback: str) -> str:
    routing = cfg.get("llm_routing", {})
    if isinstance(routing, dict):
        route_raw = routing.get("document_levels") or routing.get("anchors")
        if isinstance(route_raw, str):
            route = _normalize_route_name(route_raw)
            if route in {"deepseek", "gemini", "claude_api", "claude_cli"}:
                return route

    if provider_fallback in {"claude", "claude_api"}:
        return "claude_api"
    if provider_fallback == "claude_cli":
        return "claude_cli"
    return provider_fallback


def _read_llm_provider_config(cfg: dict) -> dict:
    llm_cfg = cfg.get("llm_provider")
    if llm_cfg is None:
        raise ValueError(
            "Invalid config schema: missing 'llm_provider' in ~/.memorable/data/config.json."
        )
    if not isinstance(llm_cfg, dict):
        raise ValueError(
            "Invalid config schema: 'llm_provider' must be an object in ~/.memorable/data/config.json."
        )
    return llm_cfg


def call_llm(prompt: str, max_tokens: int = 4096) -> tuple[str, str]:
    cfg = _load_llm_config()
    llm_cfg = _read_llm_provider_config(cfg)

    route = _resolve_levels_route(cfg, _resolve_provider(llm_cfg))
    provider = "claude" if route == "claude_api" else route
    model = llm_cfg.get("model")
    api_key = llm_cfg.get("api_key", "")
    endpoint = llm_cfg.get("endpoint")

    if route == "claude_cli":
        output = _call_claude_cli(prompt, cfg)
        return output, "claude_cli"

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
        ), (model or "deepseek-chat")
    if provider == "gemini":
        return _call_gemini(prompt, api_key, model or "gemini-2.5-flash", max_tokens), (
            model or "gemini-2.5-flash"
        )
    if provider == "claude":
        return _call_claude(prompt, api_key, model or "claude-haiku-4-5-20251001", max_tokens), (
            model or "claude-haiku-4-5-20251001"
        )
    raise ValueError(f"Unknown provider: {provider}")


def _extract_json_payload(text: str) -> dict:
    raw = (text or "").strip()
    if not raw:
        raise ValueError("LLM returned empty output.")

    try:
        loaded = json.loads(raw)
        if isinstance(loaded, dict):
            return loaded
    except Exception:
        pass

    start = raw.find("{")
    end = raw.rfind("}")
    if start < 0 or end <= start:
        raise ValueError("LLM output was not valid JSON.")
    candidate = raw[start:end + 1]
    loaded = json.loads(candidate)
    if not isinstance(loaded, dict):
        raise ValueError("LLM JSON payload root must be an object.")
    return loaded


def _clamp_level_count(value) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return MIN_LEVELS
    return max(MIN_LEVELS, min(MAX_LEVELS, parsed))


def _normalize_levels_payload(payload: dict, raw_text: str) -> tuple[int, dict[str, str]]:
    levels = _clamp_level_count(payload.get("levels", MIN_LEVELS))
    content = payload.get("content", {})
    if not isinstance(content, dict):
        raise ValueError("LLM payload missing valid `content` object.")

    normalized = {}
    for level in range(1, levels + 1):
        key = str(level)
        value = content.get(key)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"LLM payload missing non-empty content for level {key}.")
        normalized[key] = value.strip()

    normalized[str(levels)] = raw_text
    return levels, normalized


def build_levels_manifest(
    filename: str,
    raw_text: str,
    level_count: int,
    level_content: dict[str, str],
    model: str,
) -> dict:
    tokens_by_level = {
        level: estimate_tokens(text)
        for level, text in level_content.items()
    }
    return {
        "version": LEVELS_VERSION,
        "filename": filename,
        "levels": level_count,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "model": model,
        "tokens": tokens_by_level,
        "source_tokens": estimate_tokens(raw_text),
        "content": level_content,
    }


def process_document_llm(text: str, filename: str) -> tuple[dict, str]:
    prompt = LEVELS_PROMPT.replace("{filename}", filename).replace("{document_text}", text)

    if len(prompt) > 160_000:
        head = text[:70_000]
        tail = text[-70_000:]
        clipped = head + "\n\n[...middle truncated for processing...]\n\n" + tail
        prompt = LEVELS_PROMPT.replace("{filename}", filename).replace("{document_text}", clipped)

    input_tokens = max(1, estimate_tokens(text))
    max_tokens = min(24_000, max(4_096, int(input_tokens * 1.35)))

    llm_output, model = call_llm(prompt, max_tokens=max_tokens)
    payload = _extract_json_payload(llm_output)
    level_count, level_content = _normalize_levels_payload(payload, text)
    return build_levels_manifest(filename, text, level_count, level_content, model), model


def process_file(filename: str, force: bool = False) -> dict:
    raw_path = FILES_DIR / filename
    levels_path = levels_path_for(filename)

    if not raw_path.is_file():
        return {
            "status": "error",
            "levels_path": None,
            "levels": None,
            "tokens_by_level": None,
            "error": "File not found",
        }

    if levels_path.exists() and not force:
        loaded = read_levels_file(filename)
        return {
            "status": "skipped",
            "levels_path": str(levels_path),
            "levels": loaded.get("levels") if isinstance(loaded, dict) else None,
            "tokens_by_level": loaded.get("tokens") if isinstance(loaded, dict) else None,
            "error": None,
        }

    try:
        text = raw_path.read_text(encoding="utf-8")
    except Exception as e:
        return {
            "status": "error",
            "levels_path": None,
            "levels": None,
            "tokens_by_level": None,
            "error": f"Read error: {e}",
        }

    try:
        manifest, _model = process_document_llm(text, filename)
    except Exception as e:
        log_error(f"LLM levels generation failed for {filename}: {e}")
        return {
            "status": "error",
            "levels_path": None,
            "levels": None,
            "tokens_by_level": None,
            "error": str(e),
        }

    _atomic_write(levels_path, json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
    return {
        "status": "ok",
        "levels_path": str(levels_path),
        "levels": manifest.get("levels"),
        "tokens_by_level": manifest.get("tokens"),
        "model": manifest.get("model"),
        "error": None,
    }


def read_file_at_level(filename: str, level: int) -> str | None:
    raw_path = FILES_DIR / filename
    levels = read_levels_file(filename)

    if isinstance(levels, dict):
        content = levels.get("content", {})
        if isinstance(content, dict) and level >= 1:
            value = content.get(str(level))
            if isinstance(value, str) and value:
                return value

    if raw_path.is_file():
        try:
            return raw_path.read_text(encoding="utf-8")
        except Exception:
            return None
    return None
