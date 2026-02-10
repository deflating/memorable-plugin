# Memorable — Product Plan

*Written Feb 11, 2026 at 4am because Matt couldn't sleep and had ideas.*

## What Is Memorable?

A Claude Code plugin that gives Claude persistent memory and personal context across sessions. Seed files define who the user is, who Claude is, and what's happening now. A daemon watches sessions and builds a growing library of notes. A web UI lets you manage everything.

**The differentiator:** Memorable isn't just memory storage. It's the system that makes Claude feel like someone who knows you. Other tools (claude-mem, OpenMemory) solve retrieval. Memorable solves presence.

## What Ships

### The Plugin
- **Hooks**: SessionStart (load context), PreCompact (re-inject after compaction), UserPromptSubmit (lightweight hint)
- **Daemon**: Watches Claude Code transcripts, detects session idle, generates notes via configurable LLM (DeepSeek by default, user can configure any endpoint)
- **Session notes**: Stored as JSON, scored with salience + emotional weight, decay over time, reinforced when topics recur
- **Seed files**: `user.md`, `agent.md`, `now.md` — loaded in order at session start

### The Web UI
Served by the plugin on localhost (default port 7777). Five sections:

**Dashboard (home)**
- Token budget bar (persistent across all views)
- Last session summary card
- Recent 5 session notes as cards with salience indicators
- Quick actions: edit seeds, upload file, search sessions
- If no seed files exist: shows onboarding flow instead

**Seeds**
- The current Context Configurator, rebranded
- User profile editor (identity, cognitive style, values, communication prefs, people, projects, custom sections)
- Agent profile editor (traits, behaviors, avoid list, when-user-is-low, technical style, custom sections)
- Use case presets (Technical, Research, Personal, Custom)
- Toggle sections on/off, add custom options everywhere
- Form editor / plain text / rich text toggle with bidirectional sync
- Import existing .md files
- Export / download / copy to clipboard

**Session Notes**
- Browse all session notes chronologically
- Search by keyword / topic tag
- Sort by date or salience
- Each note shows: date, one-line summary, tags, salience score (visual indicator), word count
- Click to expand full note content
- Salience decay visualized (color fade from warm to cool)

**Files**
- Context file manager
- Upload / paste documents
- Each file shows: name, size, token estimate, anchor depth, project tag
- Anchor depth selector per file: Full / Detailed (L1+L2) / Summary (L1) / None
- Anchor processing via configured LLM (or mechanical fallback)
- Project tagging — link files to projects defined in Seeds
- Files are included in session context based on depth setting

**Settings**
- LLM provider: endpoint URL, API key, model name (default: DeepSeek)
- Token budget limit (default: 200K, but relevant portion is startup context)
- Data directory path
- Daemon: on/off, idle detection threshold
- Server port
- Reset / export all data

### Install & Onboarding

**Install:**
```bash
# Option 1: Clone + install
git clone https://github.com/mattkennelly/memorable.git
cd memorable && ./install.sh

# Option 2: If we package it
pip install memorable  # or npm, TBD
```

`install.sh` does:
- Creates `~/.memorable/` directory structure
- Writes default config
- Installs hooks into `~/.claude/hooks/` (merges with existing hooks.json if present)
- Starts the web server
- Opens localhost:7777 in browser

**Onboarding (first run):**
1. SessionStart hook detects no seed files → injects onboarding prompt instead of context
2. Claude interviews the user conversationally: who are you, what do you do, how should I talk to you, what are you working on
3. User can also drop in documents: "here's my project README", "here's my team wiki"
4. Claude processes documents with weighted anchors (using configured LLM)
5. Claude offers to open the web UI for fine-tuning: "Want to customize further? I'll open the configurator."
6. Web UI shows everything Claude captured, pre-populated in the forms
7. User tweaks as desired, uploads more files if they want
8. User hits "Publish" → seed files written to `~/.memorable/seeds/`, hooks activated
9. Next session starts with full context loaded

## File Structure

```
memorable/
├── README.md
├── install.sh
├── plugin/
│   ├── hooks/
│   │   ├── hooks.json
│   │   └── scripts/
│   │       ├── session_start.py
│   │       ├── pre_compact.py
│   │       └── user_prompt.py
│   ├── daemon/
│   │   ├── memorable_daemon.py
│   │   ├── transcript_watcher.py
│   │   ├── note_generator.py
│   │   └── inference.py
│   └── server/
│       └── server.py          # HTTP server + API
├── processor/
│   ├── __init__.py
│   ├── anchor.py              # Weighted anchor extraction
│   └── processor.py           # CLI wrapper
├── ui/
│   ├── index.html
│   ├── styles.css
│   └── app.js
└── data/                      # Created at ~/.memorable/ on install
    ├── seeds/
    │   ├── user.md
    │   ├── agent.md
    │   └── now.md
    ├── notes/
    ├── sessions/
    ├── files/                  # Uploaded context documents
    ├── transcripts/
    └── config.json
```

## Build Stages

### Stage 1: Clean repo structure
- Create a fresh git repo
- Copy and clean existing plugin code (strip Matt-specific references)
- Copy the Context Configurator UI as starting point
- Copy the anchor processor
- Write install.sh that actually works for other people
- Write a basic README

### Stage 2: Web UI — Dashboard + navigation
- Restructure UI from 3 tabs to full app with sidebar nav
- Build dashboard page (status, recent notes, quick actions)
- Token budget bar as persistent header element
- Earthy design language carried through

### Stage 3: Web UI — Session Notes page
- Build session notes browser
- Wire it to read from ~/.memorable/notes/
- Search, sort, salience visualization
- Expandable note cards

### Stage 4: Web UI — Files page
- Build file manager
- Upload / paste / drag-drop
- Anchor processing integration (call configured LLM or mechanical fallback)
- Depth selector, token estimates, project tags

### Stage 5: Web UI — Settings page
- LLM provider configuration
- Token budget
- Daemon controls
- Data management

### Stage 6: Server API
- Wire all UI pages to server.py endpoints
- Config read/write, file upload, deploy/publish, budget calculation
- Serve UI from the server

### Stage 7: Onboarding flow
- First-run detection in SessionStart hook
- Onboarding prompt that Claude uses to interview the user
- Document processing during onboarding
- Handoff to web UI
- Publish action that finalizes setup

### Stage 8: Polish + ship
- Test install on clean machine
- Write proper README with screenshots
- Record a short demo if energy allows
- Push to GitHub
- Post on Reddit / share

## What's NOT in v1
- Multi-profile management (work Claude vs personal Claude)
- Community template sharing
- Hook configurator UI
- Native session memory integration (waiting for official rollout)
- Mobile-responsive UI (nice to have but not essential)
- Anything requiring a database server

## Open Questions
- Python package (pip) or just git clone? pip is cleaner but adds packaging complexity
- Do we need the daemon for v1, or can session notes be generated by a hook instead? The daemon is more reliable but harder to install.
- Should the anchor processor use the configured LLM by default, or default to mechanical with LLM as opt-in?
- Naming: is `memorable` available on PyPI/npm?
