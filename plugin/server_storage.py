#!/usr/bin/env python3
"""Shared storage/config helpers and constants for Memorable server."""

import json
from datetime import datetime, timezone
from pathlib import Path

DATA_DIR = Path.home() / ".memorable" / "data"
SEEDS_DIR = DATA_DIR / "seeds"
NOTES_DIR = DATA_DIR / "notes"
SESSIONS_DIR = DATA_DIR / "sessions"
FILES_DIR = DATA_DIR / "files"
CONFIG_PATH = DATA_DIR / "config.json"
AUDIT_LOG_PATH = DATA_DIR / "audit.log"

UI_DIR = Path(__file__).resolve().parent.parent / "ui"

CHARS_PER_TOKEN = 4
DEFAULT_PORT = 7777
MAX_UPLOAD_SIZE = 10 * 1024 * 1024

DEFAULT_CONFIG = {
    "llm_provider": {
        "endpoint": "https://api.deepseek.com/v1",
        "api_key": "",
        "model": "deepseek-chat",
    },
    "llm_routing": {
        "session_notes": "deepseek",
        "now_md": "deepseek",
        "document_levels": "deepseek",
    },
    "claude_cli": {
        "command": "claude",
        "prompt_flag": "-p",
    },
    "token_budget": 200000,
    "daemon": {
        "enabled": False,
        "idle_threshold": 300,
    },
    "semantic_default_depth": 1,
    "server_port": DEFAULT_PORT,
    "context_files": [],
}


def ensure_dirs():
    """Create all required directories if they don't exist."""
    for d in [DATA_DIR, SEEDS_DIR, NOTES_DIR, SESSIONS_DIR, FILES_DIR]:
        d.mkdir(parents=True, exist_ok=True)


def atomic_write(path: Path, content: str, encoding: str = "utf-8"):
    """Write content atomically by writing to a temp file then renaming."""
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    tmp_path.write_text(content, encoding=encoding)
    tmp_path.rename(path)


def atomic_write_bytes(path: Path, data: bytes):
    """Write bytes atomically by writing to a temp file then renaming."""
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    tmp_path.write_bytes(data)
    tmp_path.rename(path)


def _deep_merge(defaults: dict, overrides: dict) -> dict:
    """Recursively merge *overrides* into *defaults*."""
    merged = dict(defaults)
    for key, value in overrides.items():
        if (
            key in merged
            and isinstance(merged[key], dict)
            and isinstance(value, dict)
        ):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def _normalize_legacy_config(config: dict) -> dict:
    """Apply minimal schema migrations for older config versions."""
    normalized = dict(config)
    routing = normalized.get("llm_routing")
    if isinstance(routing, dict):
        migrated = dict(routing)
        legacy_document_route = migrated.get("anchors")
        if "document_levels" not in migrated and isinstance(legacy_document_route, str):
            migrated["document_levels"] = legacy_document_route
        migrated.pop("anchors", None)
        normalized["llm_routing"] = migrated
    return normalized


def load_config() -> dict:
    """Load config.json, returning defaults on any error."""
    try:
        if CONFIG_PATH.exists():
            data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return _deep_merge(DEFAULT_CONFIG, _normalize_legacy_config(data))
    except Exception:
        pass
    return dict(DEFAULT_CONFIG)


def save_config(config: dict):
    """Write config.json atomically."""
    ensure_dirs()
    atomic_write(CONFIG_PATH, json.dumps(config, indent=2, ensure_ascii=False))


def estimate_tokens(text: str) -> int:
    return len(text) // CHARS_PER_TOKEN


def append_audit(event: str, details: dict | None = None):
    """Append a JSONL audit event. Best-effort only."""
    try:
        ensure_dirs()
        entry = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "event": event,
            "details": details or {},
        }
        with AUDIT_LOG_PATH.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry, ensure_ascii=False, default=str) + "\n")
    except Exception:
        pass


def error_response(code: str, message: str, suggestion: str | None = None):
    """Build a structured API error payload."""
    payload = {"error": {"code": code, "message": message}}
    if suggestion:
        payload["error"]["suggestion"] = suggestion
    return payload
