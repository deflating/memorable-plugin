#!/usr/bin/env bash
# Memorable — installer
#
# Creates the ~/.memorable/ data directory structure, installs hooks into
# ~/.claude/hooks/hooks.json, and symlinks the plugin directory.
#
# Idempotent: safe to run multiple times.
# Run from anywhere: bash /path/to/install.sh

set -euo pipefail

PLUGIN_DIR="$(cd "$(dirname "$0")" && pwd)"
BASE_DIR="$HOME/.memorable"
DATA_DIR="$BASE_DIR/data"
HOOKS_DIR="$HOME/.claude/hooks"
HOOKS_FILE="$HOOKS_DIR/hooks.json"

# ---------------------------------------------------------------------------
# 1. Create directory structure
# ---------------------------------------------------------------------------
mkdir -p "$DATA_DIR/seeds"
mkdir -p "$DATA_DIR/notes"
mkdir -p "$DATA_DIR/sessions"
mkdir -p "$DATA_DIR/files"

# ---------------------------------------------------------------------------
# 2. Create default config.json (only if it doesn't already exist)
# ---------------------------------------------------------------------------
if [ ! -f "$DATA_DIR/config.json" ]; then
    cat > "$DATA_DIR/config.json" << 'EOF'
{
  "token_budget": 200000,
  "server_port": 7777,
  "llm_provider": {
    "endpoint": "",
    "api_key": "",
    "model": "deepseek-chat"
  },
  "llm_routing": {
    "session_notes": "deepseek",
    "now_md": "deepseek",
    "anchors": "deepseek"
  },
  "claude_cli": {
    "command": "claude",
    "prompt_flag": "-p"
  },
  "daemon": {
    "enabled": false,
    "idle_threshold": 300
  },
  "semantic_default_depth": 1,
  "context_files": []
}
EOF
fi

# ---------------------------------------------------------------------------
# 3. Create symlink from ~/.memorable/plugin -> plugin directory
# ---------------------------------------------------------------------------
if [ -L "$BASE_DIR/plugin" ]; then
    rm "$BASE_DIR/plugin"
fi
ln -s "$PLUGIN_DIR" "$BASE_DIR/plugin"

# ---------------------------------------------------------------------------
# 4. Install hooks into ~/.claude/hooks/hooks.json
# ---------------------------------------------------------------------------
mkdir -p "$HOOKS_DIR"

# Build the Memorable hook entries using the resolved plugin path.
MEMORABLE_HOOKS=$(cat << ENDJSON
{
  "SessionStart": [
    {
      "matcher": "*",
      "hooks": [
        {
          "type": "command",
          "command": "python3 $PLUGIN_DIR/hooks/scripts/session_start.py",
          "timeout": 15
        }
      ]
    }
  ],
  "PreCompact": [
    {
      "matcher": "*",
      "hooks": [
        {
          "type": "command",
          "command": "python3 $PLUGIN_DIR/hooks/scripts/session_start.py --compact",
          "timeout": 15
        }
      ]
    }
  ],
  "UserPromptSubmit": [
    {
      "matcher": "*",
      "hooks": [
        {
          "type": "command",
          "command": "python3 $PLUGIN_DIR/hooks/scripts/user_prompt.py",
          "timeout": 5
        }
      ]
    }
  ]
}
ENDJSON
)

if [ -f "$HOOKS_FILE" ]; then
    # Merge Memorable hooks into existing hooks.json, preserving other events.
    # python3 is used for reliable JSON merging.
    python3 -c "
import json, sys

with open('$HOOKS_FILE', 'r') as f:
    existing = json.load(f)

memorable = json.loads('''$MEMORABLE_HOOKS''')

def is_memorable_entry(entry):
    hooks = entry.get('hooks', [])
    for h in hooks:
        cmd = h.get('command', '')
        if not isinstance(cmd, str):
            continue
        # Match Memorable hooks even if plugin location changed since last install.
        if (
            'hooks/scripts/session_start.py' in cmd
            or 'hooks/scripts/user_prompt.py' in cmd
            or 'hooks/scripts/session_end.py' in cmd
            or 'hooks/scripts/pre_compact.py' in cmd
        ):
            return True
    return False

# Merge each hook event: replace Memorable entries, keep everything else
for event, entries in memorable.items():
    if event not in existing:
        existing[event] = entries
    else:
        # Remove any previous Memorable hooks (including stale old install paths)
        cleaned = [
            e for e in existing[event]
            if not is_memorable_entry(e)
        ]
        existing[event] = cleaned + entries

# Also remove stale Memorable entries from events no longer managed
# (e.g. SessionEnd removed from installer defaults).
for event in list(existing.keys()):
    if event in memorable:
        continue
    entries = existing.get(event)
    if not isinstance(entries, list):
        continue
    cleaned = [e for e in entries if not is_memorable_entry(e)]
    if cleaned:
        existing[event] = cleaned
    else:
        del existing[event]

with open('$HOOKS_FILE', 'w') as f:
    json.dump(existing, f, indent=2)
    f.write('\n')
"
else
    # No existing hooks file — write fresh.
    echo "$MEMORABLE_HOOKS" | python3 -c "
import json, sys
data = json.load(sys.stdin)
with open('$HOOKS_FILE', 'w') as f:
    json.dump(data, f, indent=2)
    f.write('\n')
"
fi

# ---------------------------------------------------------------------------
# 5. Success message
# ---------------------------------------------------------------------------
cat << EOF

✦ Memorable — Setup Complete
==============================

Data directory: ~/.memorable/data/
Hooks installed: ~/.claude/hooks/hooks.json

To start the web UI:
  python3 $PLUGIN_DIR/server.py

Then open http://localhost:7777

To create your first seed files, start a Claude Code session —
Memorable will guide you through setup.

EOF
