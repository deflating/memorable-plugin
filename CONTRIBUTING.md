# Contributing to Memorable

Memorable is intentionally local-first and lightweight. Contributions should preserve that.

## Ground Rules

- Keep data local by default.
- Python stays stdlib-only unless explicitly approved.
- Frontend stays vanilla JS/CSS/HTML (no framework migration).
- Keep changes scoped: one concern per PR.
- Add or update tests for behavior changes.

## Prerequisites

- `python3` (3.10+ recommended)
- Claude Code installed locally
- macOS/Linux shell environment

## Local Setup

```bash
git clone https://github.com/deflating/memorable-plugin.git
cd memorable-plugin
bash plugin/install.sh
python3 plugin/server.py
```

Open `http://localhost:7777`.

If you pull new changes that touch hooks or install behavior, run:

```bash
bash plugin/install.sh
```

## Development Workflow

1. Create a focused branch.
2. Make the smallest useful change that solves one issue.
3. Run tests.
4. Update docs/changelog if user-facing behavior changed.
5. Open PR with a clear scope and validation notes.

## Testing

Run the full suite:

```bash
python3 -m unittest discover -s tests -v
```

Run one test file:

```bash
python3 -m unittest discover -s tests -p 'test_server_api.py' -v
```

## Code Conventions

Project-specific style rules live in `AGENTS.md`.

Highlights:
- Python functions should stay small and focused.
- Validate inputs at boundaries (API handlers, file reads, user input).
- Avoid unnecessary defensive branching in internal code paths.
- Keep comments minimal and purposeful.
- Reuse existing CSS variables; avoid hardcoded colors outside `:root`.

## PR Conventions

- Title format: concise, imperative (`Fix config key mismatch in anchor processor`).
- Include:
  - what changed
  - why
  - how you validated (`python3 -m unittest ...`)
  - any follow-up risks or TODOs
- Do not bundle unrelated refactors with feature/bug work.

## Troubleshooting

### Port 7777 already in use

Start server on another port via config:

```bash
cat ~/.memorable/data/config.json
```

Set `server_port`, then restart `python3 plugin/server.py`.

### Hooks not firing after install

- Re-run `bash plugin/install.sh`.
- Verify `~/.claude/hooks/hooks.json` contains Memorable hook entries.
- Confirm `~/.memorable/plugin` points to your current repo path.

### Semantic anchoring not using LLM

- Confirm `~/.memorable/data/config.json` has `llm_provider`.
- Ensure `endpoint`, `model`, and `api_key` are set.
- Confirm `llm_routing.anchors` is set to the provider you want (`deepseek`, `claude`/`claude_cli`, `claude_api`, or `gemini`).
- Restart server/hooks after config updates.

### Import/reset requests fail

Expected confirmation tokens:
- Import: `X-Confirmation-Token: IMPORT`
- Reset: JSON body with `"confirmation_token":"RESET"`

### Tests fail with import/module errors

Run tests from repository root:

```bash
cd memorable-plugin
python3 -m unittest discover -s tests -v
```
