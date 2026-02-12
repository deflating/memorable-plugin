# Memorable

Persistent memory and personal context for Claude Code.

## Overview

Memorable gives Claude durable context across sessions using local files and hooks.

- Seed files (`user.md`, `agent.md`, `now.md`) define identity and current context.
- Session notes are generated from transcripts and ranked by salience.
- A local web UI (`http://localhost:7777`) lets you manage seeds, notes, knowledge docs, and settings.
- Semantic docs can be processed into multiple zoom levels to control token cost.
- MCP tools can retrieve specific zoom levels on demand.

All local state is stored on your machine under `~/.memorable/data/`.
If you enable semantic processing with an external LLM provider, document content sent for processing leaves your machine to that provider.

Release history: see `CHANGELOG.md`.
Contribution guide: see `CONTRIBUTING.md`.

## Quick Start

Prerequisites:
- `python3` (3.10+ recommended)
- Claude Code installed locally

Install and run:

```bash
git clone https://github.com/deflating/memorable-plugin.git
cd memorable-plugin
bash plugin/install.sh
python3 plugin/server.py
```

Then open `http://localhost:7777`.

The installer:
- creates `~/.memorable/data/*` directories,
- writes default `config.json` if missing,
- installs/merges Claude hooks in `~/.claude/hooks/hooks.json`,
- links `~/.memorable/plugin` to your installed plugin path.

## Core Features

- Seed editor for `user.md` and `agent.md` with draft/deploy flow
- Memories area with:
  - Episodic: session notes + search/filter
  - Working: `now.md` current context
  - Semantic: knowledge docs with zoom-level controls
- Memory effectiveness insights (load vs reference yield)
- Daemon reliability health indicators (API + UI)
- Import/export/reset operations for local data
- Token budget breakdown endpoint and UI

## Upgrade Existing Installs

After pulling latest changes, re-run installer:

```bash
cd memorable-plugin
bash plugin/install.sh
```

This is idempotent and will:
- preserve non-Memorable hook entries,
- replace stale Memorable hook paths from old install locations,
- avoid duplicate Memorable hook blocks.

## Operations

### MCP Tools (Selective Level Retrieval)

Memorable includes an MCP server at `plugin/mcp_server.py` with:
- `memorable_get_document_level(filename, level)` — returns only the requested level content
- `memorable_list_documents()` — lists available semantic docs and level availability

Register it in Claude (example):

```bash
claude mcp add memorable python3 /Users/mattkennelly/memorable-plugin/plugin/mcp_server.py
```

### Backup (Export)

Use Settings -> Backups -> Export, or:

```bash
curl -sS -o memorable-export.zip http://127.0.0.1:7777/api/export
```

### Restore (Import)

Use Settings -> Backups -> Import ZIP, or:

```bash
curl -sS -X POST \
  -H "X-Confirmation-Token: IMPORT" \
  --data-binary @memorable-export.zip \
  http://127.0.0.1:7777/api/import
```

### Reset All Data

Use Settings -> Danger Zone -> Reset Everything, or:

```bash
curl -sS -X POST \
  -H "Content-Type: application/json" \
  -d '{"confirmation_token":"RESET"}' \
  http://127.0.0.1:7777/api/reset
```

## Configuration

Config path: `~/.memorable/data/config.json`

Important keys:
- `llm_provider` (`endpoint`, `api_key`, `model`)
- `llm_routing` (`session_notes`, `now_md`, `document_levels`) with values:
  - `deepseek`
  - `claude_cli` (or `claude`) to use `claude -p`
  - `claude_api`
  - `gemini`
- `claude_cli` (`command`, `prompt_flag`) defaults to `claude` + `-p`
- `token_budget`
- `daemon` (`enabled`, `idle_threshold`)
- `server_port`
- `context_files`

## Testing

Run all tests:

```bash
python3 -m unittest discover -s tests -v
```

Current suite includes:
- API/unit regression tests
- hook behavior tests
- end-to-end smoke test booting the HTTP server
- installer integration tests (isolated `HOME`)
- import/export/reset data integrity tests

## Known Limitations

- No authentication layer is provided. The server is intended for local loopback use only.
- Daemon process orchestration (start/stop lifecycle) is still external to the web UI.
- Semantic processing quality depends on external LLM quality/configuration.
- Frontend remains vanilla JS/CSS (no component framework), so large UI refactors are manual.

## Project Layout

```
memorable-plugin/
├── plugin/
│   ├── server.py
│   ├── server_http.py
│   ├── server_api.py
│   ├── server_storage.py
│   ├── install.sh
│   └── hooks/scripts/
├── processor/
├── ui/
└── tests/
```

## License

MIT
