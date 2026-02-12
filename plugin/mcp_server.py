#!/usr/bin/env python3
"""Memorable MCP server (stdio JSON-RPC).

Primary tool added for semantic zoom retrieval:
- memorable_get_document_level
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

DATA_DIR = Path.home() / ".memorable" / "data"
FILES_DIR = DATA_DIR / "files"
LEVELS_SUFFIX = ".levels.json"


def _sanitize_filename(filename: str) -> str:
    return "".join(c for c in str(filename or "") if c.isalnum() or c in "-_.").strip()


def _estimate_tokens(text: str) -> int:
    return max(1, len(text) // 4) if text else 0


def _read_levels_doc(filename: str) -> dict | None:
    levels_path = FILES_DIR / f"{filename}{LEVELS_SUFFIX}"
    if not levels_path.is_file():
        return None
    try:
        loaded = json.loads(levels_path.read_text(encoding="utf-8"))
    except Exception:
        return None
    return loaded if isinstance(loaded, dict) else None


class MemorableMCP:
    def run(self):
        for line in sys.stdin:
            line = line.strip()
            if not line:
                continue
            try:
                request = json.loads(line)
            except json.JSONDecodeError:
                self._write_error(None, -32700, "Parse error")
                continue

            req_id = request.get("id")
            method = request.get("method", "")
            params = request.get("params", {}) or {}

            try:
                result = self._dispatch(method, params)
                self._write_result(req_id, result)
            except Exception as exc:
                self._write_error(req_id, -32603, str(exc))

    def _dispatch(self, method: str, params: dict):
        handlers = {
            "initialize": self._handle_initialize,
            "tools/list": self._handle_list_tools,
            "tools/call": self._handle_call_tool,
            "notifications/initialized": lambda _p: None,
        }
        handler = handlers.get(method)
        if handler is None:
            raise ValueError(f"Unknown method: {method}")
        return handler(params)

    def _handle_initialize(self, _params: dict) -> dict:
        return {
            "protocolVersion": "2024-11-05",
            "capabilities": {"tools": {}},
            "serverInfo": {
                "name": "memorable",
                "version": "5.0.0",
            },
        }

    def _handle_list_tools(self, _params: dict) -> dict:
        return {"tools": TOOLS}

    def _handle_call_tool(self, params: dict) -> dict:
        name = params.get("name", "")
        args = params.get("arguments", {}) or {}
        handlers = {
            "memorable_get_document_level": self._tool_get_document_level,
            "memorable_list_documents": self._tool_list_documents,
        }
        handler = handlers.get(name)
        if handler is None:
            return {
                "content": [{"type": "text", "text": f"Unknown tool: {name}"}],
                "isError": True,
            }
        try:
            output = handler(args)
            return {"content": [{"type": "text", "text": output}]}
        except Exception as exc:
            return {
                "content": [{"type": "text", "text": f"Error: {exc}"}],
                "isError": True,
            }

    def _tool_list_documents(self, _args: dict) -> str:
        if not FILES_DIR.is_dir():
            return "No files directory found."

        lines = []
        for path in sorted(FILES_DIR.iterdir()):
            if not path.is_file():
                continue
            name = path.name
            if name.endswith(LEVELS_SUFFIX) or name.startswith("."):
                continue
            levels_doc = _read_levels_doc(name)
            if isinstance(levels_doc, dict):
                try:
                    level_count = int(levels_doc.get("levels", 0) or 0)
                except (TypeError, ValueError):
                    level_count = 0
                lines.append(f"- {name} (levels: {level_count})")
            else:
                lines.append(f"- {name} (raw only)")
        if not lines:
            return "No semantic documents found."
        return "Semantic documents:\n" + "\n".join(lines)

    def _tool_get_document_level(self, args: dict) -> str:
        filename = _sanitize_filename(args.get("filename", ""))
        if not filename:
            return "Error: filename is required."

        raw_path = FILES_DIR / filename
        if not raw_path.is_file():
            return f"Error: file not found: {filename}"

        raw_text = raw_path.read_text(encoding="utf-8", errors="replace")
        requested = args.get("level", 1)
        try:
            requested_level = int(requested)
        except (TypeError, ValueError):
            requested_level = 1

        levels_doc = _read_levels_doc(filename)
        resolved_level = -1
        resolved_text = raw_text
        source = "raw"

        if requested_level >= 1 and isinstance(levels_doc, dict):
            content = levels_doc.get("content", {})
            if isinstance(content, dict):
                selected = content.get(str(requested_level))
                if isinstance(selected, str) and selected.strip():
                    resolved_level = requested_level
                    resolved_text = selected
                    source = "levels"

        payload = {
            "filename": filename,
            "requested_level": requested_level,
            "resolved_level": resolved_level,
            "source": source,
            "tokens": _estimate_tokens(resolved_text),
            "content": resolved_text,
        }
        return json.dumps(payload, ensure_ascii=False)

    def _write_result(self, req_id, result):
        if result is None:
            return
        self._write({"jsonrpc": "2.0", "id": req_id, "result": result})

    def _write_error(self, req_id, code: int, message: str):
        self._write(
            {
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {"code": code, "message": message},
            }
        )

    def _write(self, obj: dict):
        sys.stdout.write(json.dumps(obj, ensure_ascii=False) + "\n")
        sys.stdout.flush()


TOOLS = [
    {
        "name": "memorable_get_document_level",
        "description": "Return a single semantic zoom level for a document without reading the full levels JSON into context.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "filename": {"type": "string", "description": "Document filename under ~/.memorable/data/files"},
                "level": {"type": "integer", "description": "Requested zoom level (1..N). Use -1 for raw file.", "default": 1},
            },
            "required": ["filename"],
        },
    },
    {
        "name": "memorable_list_documents",
        "description": "List semantic documents and whether levels are available.",
        "inputSchema": {
            "type": "object",
            "properties": {},
        },
    },
]


if __name__ == "__main__":
    MemorableMCP().run()
