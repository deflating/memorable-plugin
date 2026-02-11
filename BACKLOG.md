# Memorable — Backlog

*Generated 2026-02-11 from reviews by: Claude Agent Team (backend, frontend, UX, memory researcher) + ChatGPT Codex*

> Note: This file is a historical review artifact. Linear is the source of truth for active status.

---

## P0: Fix Now

Bugs and security issues that need fixing before any release.

---

### #1 — `extract_at_depth` import alias mismatch

**Type:** Bug
**File:** `plugin/server.py:883`
**Found by:** Agent Team (Backend)

The function is imported as `_extract_at_depth` (with underscore) but called as `extract_at_depth` (without) in the budget endpoint. This will crash with a `NameError` whenever `/api/budget` is called and an anchored context file exists.

**Fix:** Change the call site to use `_extract_at_depth`.

---

### #2 — Backup failure doesn't stop file overwrite

**Type:** Bug
**File:** `plugin/server.py:335-340`
**Found by:** Agent Team (Backend)

When saving seed files, a backup is created with `shutil.copy2()` inside a `try/except` that silently passes on failure. The code then proceeds to overwrite the original file. If the backup fails (disk full, permissions), the user's data is silently lost.

**Fix:** If backup creation fails, return 500 to the client and do not overwrite the original file.

---

### #3 — No max upload size

**Type:** Security
**File:** `plugin/server.py:542, 576, 963`
**Found by:** Agent Team (Backend)

`Content-Length` is read as `int(handler.headers.get("Content-Length", 0))` and the full body is allocated into memory with no upper bound. A client can send `Content-Length: 999999999` and exhaust memory.

**Fix:** Add `MAX_UPLOAD_SIZE = 10 * 1024 * 1024` constant. Check length before `rfile.read()`. Return 413 if exceeded.

---

### #4 — Markdown section parsing is case-sensitive

**Type:** Bug
**File:** `ui/app.js` — `parseUserMarkdown()`, `parseAgentMarkdown()`
**Found by:** Agent Team (Frontend)

Section lookups like `sections['About']` use exact case. If a user writes `## about` or `## ABOUT`, it falls through to a custom section instead of populating the structured form field. Data survives but loses its structured representation on round-trip.

**Fix:** Normalize section key lookups to be case-insensitive. Simplest approach: lowercase both the stored key and the lookup key.

---

### #5 — localStorage quota failure is silent

**Type:** Bug
**File:** `ui/app.js` — `saveToLocalStorage()`
**Found by:** Agent Team (Frontend)

The `catch` block is empty. If localStorage is full, the user gets no feedback and believes their data is saved. On next page load, changes are lost.

**Fix:** Show a toast notification on quota error using the existing `showToast()` pattern.

---

### #6 — Server binds to 0.0.0.0

**Type:** Security (Critical)
**File:** `plugin/server.py:1161`
**Found by:** Codex

`HTTPServer(("0.0.0.0", port), ...)` exposes the API to the entire local network. Combined with the CORS wildcard (#7), this means any device on your LAN can read your notes, seeds, and config.

**Fix:** Change to `"127.0.0.1"`. If LAN access is ever needed, it should be opt-in via config.

---

### #7 — CORS wildcard on all responses

**Type:** Security (Critical)
**File:** `plugin/server.py:951-952, 1151-1152`
**Found by:** Codex

Every response includes `Access-Control-Allow-Origin: *`. This means any website you visit can make fetch requests to `http://127.0.0.1:7777/api/notes` and read the response. Your notes, seeds, and files are readable by any web page.

**Fix:** Remove all `Access-Control-Allow-Origin: *` headers entirely. The UI is served from the same origin, so no CORS headers are needed.

---

### #8 — /api/config endpoint is a remote config overwrite vector

**Type:** Security (Critical)
**File:** `plugin/server.py:696-758`
**Found by:** Codex

`GET /api/config` exposes full config (including API keys). `POST /api/config` allows arbitrary config overwrites with no authentication. Combined with #6 and #7, any website or LAN device can rewrite your config, change API endpoints, and corrupt state.

**Fix:** Remove both `handle_get_config()` and `handle_post_config()` handlers and their routing entries. Settings should only be changed via `/api/settings` which has a defined schema.

---

### #9 — Google Fonts external request (Done 2026-02-11)

**Type:** Privacy
**File:** `ui/index.html:7-10`
**Found by:** Codex

The README says "nothing leaves your machine" but the UI loads Google Fonts via external `<link>` tags, sending requests to Google on every page load.

**Fix:** Remove the Google Fonts `<link>` tags. Use system font stack: `-apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif`. Update `styles.css` font-family declarations if they reference the Google font name.

---

### #10 — Settings UI wired to wrong schema (Done 2026-02-11)

**Type:** Bug
**File:** `ui/app.js` — settings load/save functions
**Found by:** Codex

The server returns `{ "settings": { "llm_provider": { "endpoint": ..., "api_key": ..., "model": ... }, "server_port": ..., "token_budget": ..., "daemon": { "enabled": ..., "idle_threshold": ... } } }`. The UI reads different keys (`data.llm`, `s.port`, etc.) and POSTs a different shape. Net effect: Settings page appears empty and Save doesn't persist correctly.

**Fix:** Align the UI's key names to match the server's actual response/request schema. Read `handle_get_settings()` and `handle_post_settings()` in server.py to confirm the exact shapes.

---

### #11 — Dashboard onboarding field name mismatch

**Type:** Bug
**File:** `ui/app.js` — dashboard rendering
**Found by:** Codex

The dashboard checks `status.seeds_exist` to decide whether to show the onboarding card, but the server sends the field as `seeds_present`. Onboarding card may show/hide incorrectly.

**Fix:** Change `seeds_exist` to `seeds_present` in the UI lookup.

---

## P1: Build Next

High-impact improvements that should happen soon after P0.

---

### #12 — Recency ceiling on note loading

**Type:** Memory Architecture
**Found by:** Memory Researcher

Session notes are loaded at startup sorted purely by salience score. A note from 1 hour ago with low emotional weight can be buried by a 2-day-old emotional note. Recent context should always be available.

**Fix:** At session start, always load the 3-5 most recent notes regardless of salience. Fill remaining slots by salience score. Modify the note selection logic in `session_start.py` or the note loading hook.

---

### #13 — Tooltips for jargon terms

**Type:** UX
**Found by:** UX Review

Terms like "seed files," "anchor depth," "salience," and "daemon" are used throughout the UI without explanation. New users won't understand what they mean.

**Fix:** Add `title` attributes or small `(?)` hover icons next to jargon terms. Key terms to cover:
- "Seed files" → "Files that define who you are (user.md) and how the agent should behave (agent.md)"
- "Anchor Depth" → "How much detail to include when loading this document. Higher depth = more tokens"
- "Salience" → "How relevant/important this note is. Higher = more likely to be loaded"
- "Daemon" → "Background process that watches your sessions and auto-generates notes"

---

### #14 — Save indicator state transitions

**Type:** UX
**Found by:** UX Review

The "Auto-saved" indicator is static text. Users get no feedback during saves, no confirmation after saves, and no error state if saving fails.

**Fix:** Change the indicator to cycle through states: idle → "Saving..." (with subtle animation) → "Saved" (brief green checkmark) → idle. On error: "Save failed" in red with retry option.

---

### #15 — Null checks on API responses

**Type:** Bug Prevention
**File:** `ui/app.js`
**Found by:** Agent Team (Frontend)

Several rendering functions access nested properties without null guards (e.g., `filesData.files`, `data.breakdown`). If the API returns unexpected shapes, the UI crashes silently.

**Fix:** Add defensive checks before iterating API response data. Use `(data.files || [])`, `(data.breakdown || [])`, etc.

---

### #16 — Config validation with defaults

**Type:** Robustness
**File:** `plugin/server.py` — `load_config()`
**Found by:** Agent Team (Backend)

`load_config()` returns the raw JSON without validating required keys. A corrupted or minimal config.json causes cryptic errors in downstream code that assumes keys exist.

**Fix:** After loading, merge with a `DEFAULT_CONFIG` dict that provides all required keys with sensible defaults. Return the merged result.

---

### #17 — Unify config schemas (Done 2026-02-11)

**Type:** Architecture
**Files:** `plugin/install.sh`, `plugin/server.py`, `processor/anchor.py`
**Found by:** Codex

Three different config schemas exist:
- Installer writes `{ "port": ..., "llm": {...} }`
- Server expects `{ "server_port": ..., "llm_provider": {...} }`
- Anchor processor expects `{ "summarizer": {...} }` from a different config path

This guarantees broken behavior on fresh installs.

**Fix:** Pick one canonical schema (the server's `~/.memorable/data/config.json` with `llm_provider`/`server_port`/`token_budget`/`daemon`). Update installer to write that schema. Update `processor/anchor.py` to read from the same file and key names.

---

### #18 — Use ThreadingHTTPServer

**Type:** Robustness
**File:** `plugin/server.py:1161`
**Found by:** Codex

The server uses `HTTPServer` (single-threaded). When `/api/files/<name>/process` calls the LLM (up to 120s timeout), all other requests — including the UI — block completely.

**Fix:** Change `HTTPServer` to `ThreadingHTTPServer` (from `http.server`). One-line change, no other modifications needed.

---

### #19 — Atomic file writes everywhere

**Type:** Robustness
**Files:** `plugin/server.py:342-343, 565-566, 590-592`, `processor/anchor.py:506-508`
**Found by:** Codex

Seeds, uploads, and anchored output are overwritten directly with `path.write_text()`. If the process crashes mid-write, the file is corrupted. The config save already uses a correct atomic pattern (write to `.tmp` then rename).

**Fix:** Extract the atomic write pattern into a utility function. Use it for all file writes: seeds, uploaded files, anchored output.

---

### #20 — Allow "Load (full)" for raw (unanchored) files

**Type:** UX
**File:** `ui/app.js`
**Found by:** Codex

The Semantic Memory UI only shows the depth selector when `f.anchored` is true. But the backend and hook can load raw files at depth -1 (full). Users should be able to enable loading for unanchored files too.

**Fix:** Show an enable/disable toggle for all files, not just anchored ones. For unanchored files, hide the depth selector but still allow toggling the file on/off for session loading.

---

## P2: Build Soon

High-impact features that require more design or effort.

---

### #21 — Session-time note retrieval

**Type:** Memory Architecture (Major)
**Found by:** Memory Researcher

The `memorable_search` MCP tool exists but isn't surfaced anywhere in Claude's session context. Claude has no prompt or instruction telling it the tool exists. Memory is currently passive (loaded at startup only) — it should be active (searchable during conversation).

**Fix:** Add a line to the session start output or context-index telling Claude: "To search past sessions, use `memorable_search(query)`. Use this when the user references past conversations or when you need historical context." This is the difference between "Claude remembers what was loaded" and "Claude can look things up."

---

### #22 — Hierarchical note consolidation

**Type:** Memory Architecture
**Found by:** Memory Researcher

Session notes accumulate linearly forever. After 500+ sessions, the note collection becomes unwieldy with no synthesis or compression. Old notes with low salience should be consolidated, not just decayed.

**Fix:** Implement a consolidation pipeline:
- **Weekly:** Summarize top-salience notes by topic tag into a weekly synthesis note
- **Monthly:** Synthesize weekly summaries into monthly summaries
- **Archive:** Auto-archive notes below salience 0.1 after 90 days (move to archive dir, not delete)

This can be a daemon task that runs periodically.

---

### #23 — Guided onboarding wizard

**Type:** UX
**Found by:** UX Review

First-time users face 8+ form sections dumped on a single page with no guidance. The current onboarding is just two buttons on a welcome card.

**Fix:** Replace the welcome card with a multi-step wizard:
1. Name + Pronouns
2. About You (free-form)
3. Core Values (pick from defaults or create)
4. Agent Personality (key trait sliders)
5. Review + Save

Each step is one focused screen with "Next" and "Skip for now." Wizard collapses to the full form editor afterward.

---

### #24 — Conflict detection in notes

**Type:** Memory Architecture
**Found by:** Memory Researcher

When two notes disagree on a fact (e.g., "we use Jest" vs. "switched to Vitest"), both get loaded and Claude has to figure it out. There's no flagging or resolution mechanism.

**Fix:** When generating a new note, check if it contradicts an existing high-salience note on overlapping topic tags. If so, add a `conflicts_with` field to the new note's JSONL entry. Surface conflicts in the UI and optionally in the session start context.

---

### #25 — Wire now.md auto-updates from daemon

**Type:** Feature
**Found by:** Memory Researcher

The daemon has a `generate_rolling_summary()` function and a `ROLLING_SUMMARY_PROMPT`, but they aren't wired to `now.md`. The Working Memory tab in the UI says "now.md will be created automatically by the daemon" but no daemon exists in this repo.

**Fix:** When the daemon processes a session, generate a rolling summary and either update `now.md` directly or write a proposed update that the user can review/approve in the UI.

---

### #26 — Hook cache file path manipulation (Done 2026-02-11)

**Type:** Security
**File:** `plugin/hooks/scripts/session_start.py:90-93`
**Found by:** Codex

The hook writes `.cache-{filename}-depth{depth}.md` using `filename` from config without sanitization. If an attacker can write config (which was possible via #8 before removal), this becomes a path traversal vector.

**Fix:** Sanitize `filename` in the hook before using it in file paths. Strip path separators and ensure it only contains alphanumeric characters, hyphens, underscores, and dots.

---

### #27 — Anchor processor config mismatch (Done 2026-02-11)

**Type:** Bug
**File:** `processor/anchor.py:28-30, 166-196`
**Found by:** Codex

The anchor processor reads `~/.memorable/config.json` (not `~/.memorable/data/config.json`) and expects a `summarizer` key (not `llm_provider`). On a fresh install with the standard config, LLM-powered anchoring will silently fail and fall back to mechanical every time.

**Fix:** Part of #17 (unify config schemas). Make the processor read from `~/.memorable/data/config.json` and use the `llm_provider` key.

---

### #28 — Export/reset endpoints are 404

**Type:** Bug
**Files:** `ui/app.js`, `plugin/server.py`
**Found by:** Codex

The UI calls `/api/export` and `/api/reset` but these endpoints don't exist in server.py. The Export and Reset buttons in Settings silently fail.

**Fix:** Either implement the endpoints or disable the buttons with "Coming soon" labels. For export: zip up `~/.memorable/data/` and return it. For reset: require confirmation token, then wipe data dir contents.

---

## P3: Build Later

Nice-to-haves and long-term improvements.

---

### #29 — Undo/redo in Configure page
**Type:** UX | **Source:** Frontend Review
All edits are immediately persisted. No way to undo accidental deletions. Implement a state history stack.

### #30 — Dark mode
**Type:** UX | **Source:** Frontend Review
CSS custom properties are already in place. Add a `prefers-color-scheme: dark` media query variant for all color variables.

### #31 — Import preview/diff
**Type:** UX | **Source:** Frontend Review
Show a summary of what will change before confirming a markdown import. "This will replace 3 sections and add 2 new custom ones."

### #32 — Drag-and-drop reordering
**Type:** UX | **Source:** UX Review
Allow reordering people, projects, and custom sections by dragging.

### #33 — Keyboard shortcuts
**Type:** UX | **Source:** UX Review
Ctrl+S to force save, Ctrl+Z to undo, etc.

### #34 — Section collapse persistence
**Type:** UX | **Source:** UX Review
Save expanded/collapsed state of form sections to localStorage.

### #35 — File upload progress indicator
**Type:** UX | **Source:** Frontend Review
Show a progress bar for large semantic memory file uploads.

### #36 — Structured error responses from API
**Type:** DX | **Source:** Agent Team (Backend)
Return error codes + human-readable suggestions instead of generic messages. E.g., `{ "error": { "code": "INVALID_SEED_NAME", "message": "...", "suggestion": "..." } }`.

### #37 — Audit log
**Type:** Robustness | **Source:** Agent Team (Backend)
Append-only log of all mutations at `~/.memorable/data/audit.log`. Track who/what changed seed files, config, etc.

### #38 — Health check endpoint
**Type:** DX | **Source:** Agent Team (Backend)
`GET /api/health` returning seed status, disk space, config validity, daemon status.

### #39 — Antiforcing register
**Type:** Memory Architecture | **Source:** Memory Researcher
A "don't try again" list. When an approach fails, record it so Claude doesn't re-suggest it. New field in notes: `should_not_try: [list]`.

### #40 — Reference effectiveness tracking
**Type:** Memory Architecture | **Source:** Memory Researcher
Track whether loaded notes were actually referenced during the session. Only boost salience for notes that were genuinely used, not just loaded.

### #41 — Information density scoring
**Type:** Memory Architecture | **Source:** Memory Researcher
Weight notes by actionability and information-per-token, not just token count. Dense 50-token notes should rank higher than rambling 1000-token ones.

### #42 — Time-of-day context prediction
**Type:** Memory Architecture | **Source:** Memory Researcher
Learn session patterns (e.g., Project X at 6am, Project Y at 2pm) and pre-load relevant notes based on time/machine.

### #43 — Multi-tab sync
**Type:** UX | **Source:** Frontend Review
Detect concurrent edits via `storage` event listener. Warn or sync when the same app is open in multiple tabs.

### #44 — Split server.py into modules (Done 2026-02-11)
**Type:** Architecture | **Source:** Codex
Extract config, storage, API handlers, and HTTP wiring into separate files. Keep server.py as ~100 lines of wiring.

### #45 — Streaming JSONL iteration
**Type:** Performance | **Source:** Codex
Notes loading reads entire JSONL files into memory. For large note collections (500+ sessions), switch to streaming iteration.

### #46 — Fix mechanical anchor nesting
**Type:** Bug | **Source:** Codex
Mechanical fallback in `processor/anchor.py` doesn't produce well-nested anchor structures. Heading handling opens `⚓1️⃣` without predictable closes. If nesting semantics matter, the mechanical output should be valid.

### #47 — Split `ui/app.js` into page modules
**Type:** Architecture | **Source:** External Review
`ui/app.js` is >5k lines and mixes page renderers, event binding, API calls, markdown parsing, and state transitions in one file. Keep the current no-framework approach, but split into focused modules (`settings`, `memories`, `configure`, shared `ui/actions` helpers) loaded in `index.html`.

### #48 — Break up `session_start.py` by concern (Done 2026-02-12)
**Type:** Architecture | **Source:** External Review
`plugin/hooks/scripts/session_start.py` handles selection, salience scoring, archiving, synthesis, and now.md generation in one script (>1k lines). Extract pure modules (`note_selection.py`, `note_maintenance.py`, `now_builder.py`) and keep `session_start.py` as orchestration.

### #49 — Strict `/api/settings` payload validation (Done 2026-02-11)
**Type:** Robustness | **Source:** External Review
`POST /api/settings` currently accepts loosely-typed values and unknown keys, which can persist malformed config (wrong types/ranges) and break downstream behavior.

**Fix:** Validate and normalize all boundary fields in `handle_post_settings`:
- top-level keys: `llm_provider`, `token_budget`, `daemon`, `server_port`, `data_dir`
- enforce type/range for numeric fields (`token_budget`, `server_port`, `daemon.idle_threshold`)
- enforce booleans for flags (`daemon.enabled`)
- enforce string fields for `llm_provider` and `data_dir`
- reject unknown keys with structured API errors.

---

## Explicitly Ignored

These were raised in reviews but are not worth the cost for this project:

| Issue | Why ignore |
|---|---|
| File locking / fcntl | Single-user local app. Race conditions are theoretically possible but practically negligible. |
| Rate limiting on API | Localhost only. Nobody is DDoS'ing your own machine. |
| Unicode normalization attacks | You're the only user. Your filenames are fine. |
| XML seed markers | Claude reads seeds as separate files in sequence. Wrappers add no value. |
| Framework migration / TypeScript | Correct observation, wrong time. Rewrite cost exceeds benefit for a working v1. |
| Multi-machine note merge | Syncthing handles file sync. Custom merge logic is premature. |
| Event listener cleanup | App refreshes each session start. Leaks don't accumulate in practice. |
| Installer shell injection | Not remote-exploitable. Fix when install.sh is next touched. |
