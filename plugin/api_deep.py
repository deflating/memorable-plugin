#!/usr/bin/env python3
"""Deep memory API internals (upload, indexing, search)."""

import hashlib
import json
import re
import sqlite3
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

DEEP_CHUNK_TARGET_CHARS = 900
DEEP_CHUNK_MAX_CHARS = 1400
DEEP_SEARCH_DEFAULT_LIMIT = 20
DEEP_SEARCH_MAX_LIMIT = 50
DEEP_MAX_UPLOAD_SIZE = 200 * 1024 * 1024


def _ensure_deep_dirs(deep_files_dir: Path, deep_index_path: Path):
    deep_files_dir.mkdir(parents=True, exist_ok=True)
    deep_index_path.parent.mkdir(parents=True, exist_ok=True)


def _sanitize_filename(filename: str) -> str:
    return "".join(c for c in str(filename or "") if c.isalnum() or c in "-_.").strip()


def _deep_db_connect(deep_index_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(deep_index_path)
    conn.row_factory = sqlite3.Row
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS deep_files (
            filename TEXT PRIMARY KEY,
            size_bytes INTEGER NOT NULL,
            uploaded_at TEXT NOT NULL,
            modified_at TEXT NOT NULL,
            processed_at TEXT,
            chunk_count INTEGER NOT NULL DEFAULT 0,
            token_count INTEGER NOT NULL DEFAULT 0,
            source_sha256 TEXT
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS deep_chunks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filename TEXT NOT NULL,
            chunk_index INTEGER NOT NULL,
            content TEXT NOT NULL,
            token_estimate INTEGER NOT NULL,
            created_at TEXT NOT NULL,
            UNIQUE(filename, chunk_index)
        )
        """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_deep_chunks_filename ON deep_chunks(filename)")
    return conn


def _deep_ensure_fts_schema(conn: sqlite3.Connection) -> bool:
    """Create/sync FTS5 table for deep chunk retrieval. Returns True if usable."""
    try:
        conn.execute(
            """
            CREATE VIRTUAL TABLE IF NOT EXISTS deep_chunks_fts USING fts5(
                content,
                filename UNINDEXED,
                chunk_index UNINDEXED
            )
            """
        )
    except sqlite3.OperationalError:
        return False

    try:
        total_chunks = int(conn.execute("SELECT COUNT(*) FROM deep_chunks").fetchone()[0] or 0)
        total_fts = int(conn.execute("SELECT COUNT(*) FROM deep_chunks_fts").fetchone()[0] or 0)
        if total_fts != total_chunks:
            conn.execute("DELETE FROM deep_chunks_fts")
            conn.execute(
                """
                INSERT INTO deep_chunks_fts (rowid, content, filename, chunk_index)
                SELECT id, content, filename, chunk_index
                FROM deep_chunks
                """
            )
    except sqlite3.DatabaseError:
        return False
    return True


def _deep_build_fts_query(terms: list[str], fallback: str) -> str:
    cleaned = []
    for term in terms[:8]:
        safe = re.sub(r"[^a-zA-Z0-9_]", "", term or "")
        if len(safe) >= 2:
            cleaned.append(f"{safe}*")
    if cleaned:
        return " AND ".join(cleaned)

    literal = str(fallback or "").strip().replace('"', " ")
    if not literal:
        return ""
    return f'"{literal}"'


def _deep_file_metadata_map(deep_index_path: Path) -> dict[str, dict]:
    try:
        with _deep_db_connect(deep_index_path) as conn:
            rows = conn.execute(
                """
                SELECT filename, processed_at, chunk_count, token_count, source_sha256
                FROM deep_files
                """
            ).fetchall()
    except Exception:
        return {}

    out = {}
    for row in rows:
        out[str(row["filename"])] = {
            "processed_at": row["processed_at"],
            "chunk_count": int(row["chunk_count"] or 0),
            "token_count": int(row["token_count"] or 0),
            "source_sha256": row["source_sha256"],
        }
    return out


def _deep_split_long_block(block: str, max_chars: int) -> list[str]:
    block = block.strip()
    if not block:
        return []
    if len(block) <= max_chars:
        return [block]

    chunks: list[str] = []
    sentences = re.split(r"(?<=[.!?])\s+", block)
    buf = ""
    for sentence in sentences:
        s = sentence.strip()
        if not s:
            continue
        candidate = f"{buf} {s}".strip()
        if buf and len(candidate) > max_chars:
            chunks.append(buf)
            buf = s
        else:
            buf = candidate
    if buf:
        chunks.append(buf)

    out: list[str] = []
    for chunk in chunks:
        if len(chunk) <= max_chars:
            out.append(chunk)
            continue
        for idx in range(0, len(chunk), max_chars):
            out.append(chunk[idx : idx + max_chars].strip())
    return [item for item in out if item]


def _deep_chunk_text(text: str) -> list[str]:
    cleaned = str(text or "").strip()
    if not cleaned:
        return []

    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", cleaned) if p.strip()]
    if not paragraphs:
        return _deep_split_long_block(cleaned, DEEP_CHUNK_MAX_CHARS)

    chunks: list[str] = []
    buf = ""
    for para in paragraphs:
        expanded = _deep_split_long_block(para, DEEP_CHUNK_MAX_CHARS)
        for piece in expanded:
            candidate = f"{buf}\n\n{piece}".strip() if buf else piece
            if buf and len(candidate) > DEEP_CHUNK_TARGET_CHARS:
                chunks.append(buf)
                buf = piece
            else:
                buf = candidate
    if buf:
        chunks.append(buf)
    return [chunk for chunk in chunks if chunk]


def _deep_process_file(safe_filename: str, deep_files_dir: Path, deep_index_path: Path) -> dict:
    source_path = deep_files_dir / safe_filename
    if not source_path.is_file():
        return {
            "status": "error",
            "error": "file_not_found",
            "message": "File not found",
        }

    try:
        raw_bytes = source_path.read_bytes()
    except OSError:
        return {
            "status": "error",
            "error": "read_failed",
            "message": "Failed to read file",
        }

    text = raw_bytes.decode("utf-8", errors="replace")
    chunks = _deep_chunk_text(text)
    tokens = estimate_tokens(text)
    now_iso = datetime.now(timezone.utc).isoformat()
    source_hash = hashlib.sha256(raw_bytes).hexdigest()

    try:
        stat = source_path.stat()
        modified_iso = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat()
        size_bytes = int(stat.st_size)
    except OSError:
        modified_iso = now_iso
        size_bytes = len(raw_bytes)

    with _deep_db_connect(deep_index_path) as conn:
        fts_enabled = _deep_ensure_fts_schema(conn)
        conn.execute(
            """
            INSERT INTO deep_files (
                filename, size_bytes, uploaded_at, modified_at, processed_at,
                chunk_count, token_count, source_sha256
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(filename) DO UPDATE SET
                size_bytes=excluded.size_bytes,
                modified_at=excluded.modified_at,
                processed_at=excluded.processed_at,
                chunk_count=excluded.chunk_count,
                token_count=excluded.token_count,
                source_sha256=excluded.source_sha256
            """,
            (
                safe_filename,
                size_bytes,
                now_iso,
                modified_iso,
                now_iso,
                len(chunks),
                tokens,
                source_hash,
            ),
        )
        if fts_enabled:
            conn.execute("DELETE FROM deep_chunks_fts WHERE filename = ?", (safe_filename,))
        conn.execute("DELETE FROM deep_chunks WHERE filename = ?", (safe_filename,))
        conn.executemany(
            """
            INSERT INTO deep_chunks (filename, chunk_index, content, token_estimate, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            [
                (
                    safe_filename,
                    idx + 1,
                    chunk,
                    estimate_tokens(chunk),
                    now_iso,
                )
                for idx, chunk in enumerate(chunks)
            ],
        )
        if fts_enabled:
            rows = conn.execute(
                """
                SELECT id, content, filename, chunk_index
                FROM deep_chunks
                WHERE filename = ?
                ORDER BY chunk_index ASC
                """,
                (safe_filename,),
            ).fetchall()
            conn.executemany(
                """
                INSERT INTO deep_chunks_fts (rowid, content, filename, chunk_index)
                VALUES (?, ?, ?, ?)
                """,
                [
                    (
                        int(row["id"]),
                        str(row["content"]),
                        str(row["filename"]),
                        int(row["chunk_index"]),
                    )
                    for row in rows
                ],
            )

    return {
        "status": "ok",
        "filename": safe_filename,
        "chunks": len(chunks),
        "tokens": tokens,
        "source_sha256": source_hash,
        "processed_at": now_iso,
    }


def _deep_extract_snippet(content: str, query: str, max_len: int = 220) -> str:
    text = str(content or "").replace("\n", " ").strip()
    if len(text) <= max_len:
        return text
    q = str(query or "").strip().lower()
    if not q:
        return text[:max_len].strip() + "..."
    pos = text.lower().find(q)
    if pos < 0:
        terms = [t for t in re.findall(r"[a-zA-Z0-9]{2,}", q) if t]
        for term in terms:
            pos = text.lower().find(term)
            if pos >= 0:
                break
    if pos < 0:
        return text[:max_len].strip() + "..."
    start = max(0, pos - (max_len // 3))
    end = min(len(text), start + max_len)
    snippet = text[start:end].strip()
    if start > 0:
        snippet = "..." + snippet
    if end < len(text):
        snippet = snippet + "..."
    return snippet


def handle_get_deep_files(*, deep_files_dir: Path, deep_index_path: Path):
    """GET /api/deep/files — list files uploaded to Deep memory."""
    _ensure_deep_dirs(deep_files_dir, deep_index_path)
    files = []
    meta = _deep_file_metadata_map(deep_index_path)

    if not deep_files_dir.is_dir():
        return 200, {"files": files}

    for f in sorted(deep_files_dir.iterdir()):
        if not f.is_file() or f.name.startswith("."):
            continue
        safe = f.name
        try:
            stat = f.stat()
            m = meta.get(safe, {})
            processed_at = m.get("processed_at")
            chunk_count = int(m.get("chunk_count") or 0)
            token_count = int(m.get("token_count") or 0)
            files.append(
                {
                    "name": safe,
                    "size": stat.st_size,
                    "modified": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(),
                    "processed": bool(processed_at),
                    "processed_at": processed_at,
                    "chunks": chunk_count,
                    "tokens": token_count,
                }
            )
        except Exception:
            continue

    return 200, {"files": files}


def handle_post_deep_upload(handler, *, deep_files_dir: Path, deep_index_path: Path):
    """POST /api/deep/files/upload — upload a source file for Deep memory."""
    _ensure_deep_dirs(deep_files_dir, deep_index_path)
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
    if length == 0:
        return 400, error_response(
            "EMPTY_BODY",
            "Empty body",
            "Provide file content in the request body.",
        )
    if length > DEEP_MAX_UPLOAD_SIZE:
        return 413, error_response(
            "UPLOAD_TOO_LARGE",
            "Upload too large",
            f"Reduce payload to <= {DEEP_MAX_UPLOAD_SIZE} bytes.",
        )

    if "application/json" in content_type:
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

        safe = _sanitize_filename(filename)
        if not safe:
            safe = f"deep-{uuid.uuid4().hex[:8]}.txt"

        path = deep_files_dir / safe
        atomic_write(path, content)
        now_iso = datetime.now(timezone.utc).isoformat()
        with _deep_db_connect(deep_index_path) as conn:
            conn.execute(
                """
                INSERT INTO deep_files (filename, size_bytes, uploaded_at, modified_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(filename) DO UPDATE SET
                    size_bytes=excluded.size_bytes,
                    modified_at=excluded.modified_at
                """,
                (safe, len(content.encode("utf-8")), now_iso, now_iso),
            )

        append_audit("deep.upload", {"filename": safe, "size_bytes": len(content), "mode": "json"})
        return 200, {"ok": True, "filename": safe, "size": len(content), "tokens": estimate_tokens(content)}

    # Raw upload fallback
    filename = handler.headers.get("X-Filename", "")
    raw = handler.rfile.read(length)
    safe = _sanitize_filename(filename)
    if not safe:
        safe = f"deep-{uuid.uuid4().hex[:8]}.bin"

    path = deep_files_dir / safe
    atomic_write_bytes(path, raw)
    now_iso = datetime.now(timezone.utc).isoformat()
    with _deep_db_connect(deep_index_path) as conn:
        conn.execute(
            """
            INSERT INTO deep_files (filename, size_bytes, uploaded_at, modified_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(filename) DO UPDATE SET
                size_bytes=excluded.size_bytes,
                modified_at=excluded.modified_at
            """,
            (safe, len(raw), now_iso, now_iso),
        )

    tokens = 0
    try:
        tokens = estimate_tokens(raw.decode("utf-8"))
    except (UnicodeDecodeError, Exception):
        pass

    append_audit("deep.upload", {"filename": safe, "size_bytes": len(raw), "mode": "raw"})
    return 200, {"ok": True, "filename": safe, "size": len(raw), "tokens": tokens}


def handle_process_deep_file(filename: str, *, deep_files_dir: Path, deep_index_path: Path):
    """POST /api/deep/files/<filename>/process — process file into retrievable chunks."""
    safe = _sanitize_filename(filename)
    if not safe:
        return 400, error_response(
            "INVALID_FILENAME",
            "Invalid filename",
            "Use only alphanumeric characters, dash, underscore, and dot.",
        )

    result = _deep_process_file(safe, deep_files_dir, deep_index_path)
    append_audit(
        "deep.process",
        {"filename": safe, "status": result.get("status")},
    )
    if result.get("status") != "ok":
        return 404, error_response(
            "FILE_NOT_FOUND",
            "File not found",
            "Check the filename and upload the file if needed.",
        )
    return 200, result


def handle_delete_deep_file(filename: str, *, deep_files_dir: Path, deep_index_path: Path):
    """DELETE /api/deep/files/<filename> — delete source file and indexed chunks."""
    safe = _sanitize_filename(filename)
    if not safe:
        return 400, error_response(
            "INVALID_FILENAME",
            "Invalid filename",
            "Use only alphanumeric characters, dash, underscore, and dot.",
        )

    source_path = deep_files_dir / safe
    deleted = False
    if source_path.is_file():
        source_path.unlink()
        deleted = True

    with _deep_db_connect(deep_index_path) as conn:
        fts_enabled = _deep_ensure_fts_schema(conn)
        if fts_enabled:
            conn.execute("DELETE FROM deep_chunks_fts WHERE filename = ?", (safe,))
        conn.execute("DELETE FROM deep_chunks WHERE filename = ?", (safe,))
        conn.execute("DELETE FROM deep_files WHERE filename = ?", (safe,))

    if not deleted:
        return 404, error_response(
            "FILE_NOT_FOUND",
            "File not found",
            "Check the filename and try again.",
        )

    append_audit("deep.delete", {"filename": safe})
    return 200, {"ok": True, "deleted": safe}


def handle_get_deep_search(query_params: dict, *, deep_index_path: Path):
    """GET /api/deep/search?q=... — keyword retrieval over indexed Deep chunks."""
    raw_q = (query_params.get("q", [""])[0] or "").strip()
    if not raw_q:
        return 400, error_response(
            "MISSING_QUERY",
            "Missing query",
            "Provide a `q` query parameter.",
        )

    try:
        limit = int(query_params.get("limit", [str(DEEP_SEARCH_DEFAULT_LIMIT)])[0])
    except (TypeError, ValueError):
        limit = DEEP_SEARCH_DEFAULT_LIMIT
    limit = max(1, min(DEEP_SEARCH_MAX_LIMIT, limit))

    terms = [t.lower() for t in re.findall(r"[a-zA-Z0-9]{2,}", raw_q)]
    if not terms:
        terms = [raw_q.lower()]

    search_mode = "like_fallback"
    with _deep_db_connect(deep_index_path) as conn:
        fts_enabled = _deep_ensure_fts_schema(conn)
        if fts_enabled:
            fts_query = _deep_build_fts_query(terms, raw_q)
            if fts_query:
                rows = conn.execute(
                    """
                    SELECT
                        deep_chunks.filename AS filename,
                        deep_chunks.chunk_index AS chunk_index,
                        deep_chunks.content AS content,
                        deep_chunks.token_estimate AS token_estimate,
                        bm25(deep_chunks_fts) AS rank
                    FROM deep_chunks_fts
                    JOIN deep_chunks ON deep_chunks.id = deep_chunks_fts.rowid
                    WHERE deep_chunks_fts MATCH ?
                    ORDER BY rank ASC, deep_chunks.filename ASC, deep_chunks.chunk_index ASC
                    LIMIT ?
                    """,
                    (fts_query, limit),
                ).fetchall()
                search_mode = "fts5"
            else:
                rows = []
        else:
            where = " AND ".join(["LOWER(content) LIKE ?" for _ in terms])
            params = [f"%{term}%" for term in terms]
            params.append(limit)
            rows = conn.execute(
                f"""
                SELECT filename, chunk_index, content, token_estimate
                FROM deep_chunks
                WHERE {where}
                ORDER BY token_estimate ASC, filename ASC, chunk_index ASC
                LIMIT ?
                """,
                params,
            ).fetchall()

    results = []
    for row in rows:
        content = str(row["content"])
        results.append(
            {
                "filename": row["filename"],
                "chunk_index": int(row["chunk_index"]),
                "tokens": int(row["token_estimate"]),
                "snippet": _deep_extract_snippet(content, raw_q),
            }
        )

    return 200, {
        "query": raw_q,
        "terms": terms,
        "results": results,
        "count": len(results),
        "search_mode": search_mode,
    }
