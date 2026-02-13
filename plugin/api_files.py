#!/usr/bin/env python3
"""Semantic/files API handlers extracted from server_api."""

import hashlib
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

from server_storage import (
    append_audit,
    atomic_write,
    atomic_write_bytes,
    error_response,
    estimate_tokens,
)


def _sanitize_filename(filename: str) -> str:
    return "".join(c for c in str(filename or "") if c.isalnum() or c in "-_.").strip()


def handle_get_files(*, files_dir: Path, load_config, semantic_default_depth, normalize_semantic_depth, semantic_artifact_metadata, is_internal_context_artifact):
    """GET /api/files — list uploaded context files with levels metadata."""
    files = []
    if not files_dir.is_dir():
        return 200, {"files": files}

    config = load_config()
    default_depth = semantic_default_depth(config)
    context_files = {}
    for entry in config.get("context_files", []):
        if not isinstance(entry, dict):
            continue
        name = entry.get("filename")
        if isinstance(name, str) and name:
            context_files[name] = entry

    for f in sorted(files_dir.iterdir()):
        if not f.is_file():
            continue
        if is_internal_context_artifact(f.name):
            continue
        try:
            stat = f.stat()
            tokens = 0
            try:
                content = f.read_text(encoding="utf-8")
                tokens = estimate_tokens(content)
            except (UnicodeDecodeError, Exception):
                pass

            level_count, tokens_by_level, processed = semantic_artifact_metadata(f.name)

            cf = context_files.get(f.name, {})
            configured_depth = normalize_semantic_depth(
                cf.get("depth", default_depth),
                default_depth,
            )
            if level_count > 0 and configured_depth > level_count:
                configured_depth = level_count

            files.append(
                {
                    "name": f.name,
                    "size": stat.st_size,
                    "tokens": tokens,
                    "modified": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(),
                    "processed": bool(processed),
                    "levels": level_count,
                    "tokens_by_level": tokens_by_level or None,
                    "depth": configured_depth,
                    "enabled": bool(cf.get("enabled", False)),
                }
            )
        except Exception:
            continue

    return 200, {"files": files}


def handle_post_file_upload(handler, *, max_upload_size: int, files_dir: Path):
    """POST /api/files/upload — handle file upload via JSON or raw body."""
    content_type = handler.headers.get("Content-Type", "")

    raw_length = handler.headers.get("Content-Length", "0")
    try:
        length = int(raw_length)
    except (TypeError, ValueError):
        return 400, error_response(
            "INVALID_CONTENT_LENGTH",
            "Invalid Content-Length header",
            "Send a valid numeric Content-Length header.",
        )
    if length < 0:
        return 400, error_response(
            "INVALID_CONTENT_LENGTH",
            "Invalid Content-Length header",
            "Send a non-negative Content-Length header.",
        )

    if "application/json" in content_type:
        if length == 0:
            return 400, error_response(
                "EMPTY_BODY",
                "Empty body",
                "Provide a JSON body with filename and content.",
            )
        if length > max_upload_size:
            return 413, error_response(
                "UPLOAD_TOO_LARGE",
                "Upload too large",
                f"Reduce payload to <= {max_upload_size} bytes.",
            )
        raw = handler.rfile.read(length)
        try:
            body = json.loads(raw)
        except json.JSONDecodeError:
            return 400, error_response(
                "INVALID_JSON",
                "Invalid JSON",
                "Send a valid JSON object.",
            )
        if not isinstance(body, dict):
            return 400, error_response(
                "INVALID_JSON_OBJECT",
                "JSON body must be an object",
                "Send a JSON object payload.",
            )

        filename = body.get("filename", "")
        content = body.get("content", "")

        if not isinstance(filename, str) or not isinstance(content, str):
            return 400, error_response(
                "INVALID_UPLOAD_FIELDS_TYPE",
                "'filename' and 'content' must be strings",
                "Send JSON with string values for both filename and content.",
            )

        if not filename or not content:
            return 400, error_response(
                "MISSING_UPLOAD_FIELDS",
                "Missing 'filename' or 'content'",
                "Include both filename and content in the JSON body.",
            )

        safe = _sanitize_filename(filename)
        if not safe:
            safe = f"upload-{uuid.uuid4().hex[:8]}.txt"

        path = files_dir / safe
        atomic_write(path, content)
        append_audit("files.upload", {"filename": safe, "size_bytes": len(content), "mode": "json"})

        return 200, {
            "ok": True,
            "filename": safe,
            "size": len(content),
            "tokens": estimate_tokens(content),
        }

    filename = handler.headers.get("X-Filename", "")
    if length == 0:
        return 400, error_response(
            "EMPTY_BODY",
            "Empty body",
            "Provide request body bytes and optional X-Filename header.",
        )
    if length > max_upload_size:
        return 413, error_response(
            "UPLOAD_TOO_LARGE",
            "Upload too large",
            f"Reduce payload to <= {max_upload_size} bytes.",
        )

    raw = handler.rfile.read(length)

    safe = _sanitize_filename(filename) if filename else ""
    if not safe:
        safe = f"upload-{uuid.uuid4().hex[:8]}.bin"

    path = files_dir / safe
    atomic_write_bytes(path, raw)
    append_audit("files.upload", {"filename": safe, "size_bytes": len(raw), "mode": "raw"})

    tokens = 0
    try:
        tokens = estimate_tokens(raw.decode("utf-8"))
    except (UnicodeDecodeError, Exception):
        pass

    return 200, {
        "ok": True,
        "filename": safe,
        "size": len(raw),
        "tokens": tokens,
    }


def handle_process_file(filename: str, *, process_file_fn, load_config, save_config, semantic_default_depth, ensure_context_file_entry):
    """POST /api/files/<filename>/process — generate hierarchical semantic levels."""
    safe = _sanitize_filename(filename)
    if not safe:
        return 400, error_response(
            "INVALID_FILENAME",
            "Invalid filename",
            "Use only alphanumeric characters, dash, underscore, and dot.",
        )

    result = process_file_fn(safe, force=True)
    auto_load_configured = False
    depth = enabled = None
    if result.get("status") == "ok":
        config = load_config()
        default_depth = semantic_default_depth(config)
        auto_load_configured, depth, enabled = ensure_context_file_entry(
            config,
            safe,
            default_depth,
            True,
        )
        if auto_load_configured:
            save_config(config)
            append_audit(
                "files.depth.update",
                {
                    "filename": safe,
                    "depth": depth,
                    "enabled": enabled,
                    "source": "process_default",
                },
            )
        result["default_depth"] = depth
        result["enabled"] = enabled
        result["auto_load_configured"] = auto_load_configured

    append_audit(
        "files.process",
        {
            "filename": safe,
            "status": result.get("status"),
            "method": result.get("method"),
        },
    )
    return 200, result


def handle_get_file_levels(filename: str, *, files_dir: Path, read_file_levels, semantic_artifact_metadata, load_config, semantic_default_depth, normalize_semantic_depth):
    """GET /api/files/<filename>/levels — semantic zoom metadata + recoverability."""
    safe = _sanitize_filename(filename)
    if not safe:
        return 400, error_response(
            "INVALID_FILENAME",
            "Invalid filename",
            "Use only alphanumeric characters, dash, underscore, and dot.",
        )

    raw_path = files_dir / safe
    if not raw_path.is_file():
        return 404, error_response(
            "FILE_NOT_FOUND",
            "File not found",
            "Check the filename and upload the file if needed.",
        )

    try:
        raw_bytes = raw_path.read_bytes()
    except OSError:
        return 500, error_response(
            "READ_FAILED",
            "Failed to read source file",
            "Check file permissions and retry.",
        )

    raw_text = raw_bytes.decode("utf-8", errors="replace")
    full_tokens = estimate_tokens(raw_text)
    source_hash = hashlib.sha256(raw_bytes).hexdigest()
    levels_doc = read_file_levels(safe)
    levels = {}
    level_count, tokens_by_level, processed = semantic_artifact_metadata(safe)
    model = None
    generated_at = None
    if isinstance(levels_doc, dict):
        model = levels_doc.get("model")
        generated_at = levels_doc.get("generated_at")
    for key, value in tokens_by_level.items():
        if key == "raw":
            continue
        if not isinstance(value, int):
            continue
        denom = max(1, full_tokens)
        levels[key] = {
            "tokens": value,
            "compression_ratio": round(value / float(denom), 4),
        }
    levels["full"] = {"tokens": full_tokens, "compression_ratio": 1.0}

    config = load_config()
    configured_depth = semantic_default_depth(config)
    configured_enabled = False
    for entry in config.get("context_files", []):
        if not isinstance(entry, dict):
            continue
        if entry.get("filename") != safe:
            continue
        configured_depth = normalize_semantic_depth(entry.get("depth", configured_depth), configured_depth)
        if level_count > 0 and configured_depth > level_count:
            configured_depth = level_count
        configured_enabled = bool(entry.get("enabled", False))
        break

    return 200, {
        "filename": safe,
        "processed": bool(processed),
        "levels_count": level_count,
        "levels": levels,
        "default_depth": configured_depth,
        "enabled": configured_enabled,
        "recoverability": {
            "raw_exists": True,
            "full_recoverable": True,
            "source_sha256": source_hash,
            "levels_file_present": bool(levels_doc),
        },
        "generated_at": generated_at,
        "model": model,
        "levels_doc": levels_doc,
    }


def handle_get_file_provenance(filename: str, query_params: dict):
    """Provenance endpoint retired with levels-based redesign."""
    return 410, error_response(
        "PROVENANCE_RETIRED",
        "Provenance endpoint retired",
        "Use /api/files/<filename>/levels and /api/files/<filename>/preview for levels-based retrieval.",
    )


def handle_preview_file(filename: str, query_params: dict, *, read_file_at_level):
    """GET /api/files/<filename>/preview — preview at selected semantic level."""
    safe = _sanitize_filename(filename)
    if not safe:
        return 400, error_response(
            "INVALID_FILENAME",
            "Invalid filename",
            "Use only alphanumeric characters, dash, underscore, and dot.",
        )

    depth_str = query_params.get("depth", ["1"])[0]
    try:
        depth = int(depth_str)
    except ValueError:
        depth = -1 if depth_str == "full" else 1

    content = read_file_at_level(safe, depth)
    if content is None:
        return 404, error_response(
            "FILE_NOT_FOUND",
            "File not found",
            "Check the filename and upload the file if needed.",
        )

    return 200, {
        "content": content,
        "tokens": estimate_tokens(content),
        "depth": depth,
    }


def handle_put_file_depth(filename: str, body: dict, *, default_semantic_depth: int, semantic_depth_values: tuple, load_config, save_config):
    """PUT /api/files/<filename>/depth — set loading depth + enabled."""
    safe = _sanitize_filename(filename)
    if not safe:
        return 400, error_response(
            "INVALID_FILENAME",
            "Invalid filename",
            "Use only alphanumeric characters, dash, underscore, and dot.",
        )

    raw_depth = body.get("depth", default_semantic_depth)
    try:
        depth = int(raw_depth)
    except (TypeError, ValueError):
        return 400, error_response(
            "INVALID_DEPTH",
            "Invalid depth value",
            "Send depth as -1 (raw) or an integer level >= 1.",
        )
    if depth not in semantic_depth_values:
        return 400, error_response(
            "INVALID_DEPTH",
            "Invalid depth value",
            "Send depth as -1 (raw) or an integer level between 1 and 50.",
        )

    enabled = body.get("enabled", True)
    if not isinstance(enabled, bool):
        return 400, error_response(
            "INVALID_ENABLED",
            "Invalid enabled value",
            "Send enabled as a boolean true/false.",
        )

    config = load_config()
    context_files = config.get("context_files", [])
    if not isinstance(context_files, list):
        context_files = []

    found = False
    for cf in context_files:
        if not isinstance(cf, dict):
            continue
        if cf.get("filename") == safe:
            cf["depth"] = depth
            cf["enabled"] = enabled
            found = True
            break
    if not found:
        context_files.append({"filename": safe, "depth": depth, "enabled": enabled})

    config["context_files"] = context_files
    save_config(config)
    append_audit("files.depth.update", {"filename": safe, "depth": depth, "enabled": enabled})

    return 200, {"ok": True, "filename": safe, "depth": depth, "enabled": enabled}
