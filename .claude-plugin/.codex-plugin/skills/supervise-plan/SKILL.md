---
name: supervise-plan
description: Create a reviewed supervisor handoff for a live livespec plan thread. Invoked as livespec-overseer:supervise-plan.
---

# supervise-plan - Codex binding

Thin Codex binding for the `supervise-plan` operation of the
**livespec-overseer** plugin. The behavior lives in the plugin-owned prose
artifact at `prose/supervise-plan.md`; this binding only resolves the plugin
root and reads that contract.

## Resolving the plugin root (`$PLUGIN_ROOT`)

Codex does NOT textually substitute a plugin-root token into SKILL prose, so
resolve it explicitly, once, in this order:

1. If `LIVESPEC_OVERSEER_PLUGIN_ROOT` is set and non-empty, use it (explicit
   override for nonstandard dev setups).
2. Else if `./.claude-plugin/prose` exists under the cwd AND `./.claude-plugin`
   validates as this overseer plugin checkout (matching plugin manifest name),
   use `$(pwd)/.claude-plugin`.
3. Else use the newest valid installed cache root under
   `$HOME/.codex/plugins/cache/livespec-overseer/livespec-overseer/<version>`.
4. Else resolve the installed plugin's `source.path` from
   `codex plugin list --json -m livespec-overseer` using a robust executable
   lookup (`command -v codex`, `$HOME/.local/bin/codex`, then
   `$HOME/.bun/bin/codex`).

```bash
PLUGIN_ROOT="${LIVESPEC_OVERSEER_PLUGIN_ROOT:-}"
PLUGIN_ROOT_DIAGNOSTICS=""
if [ -z "$PLUGIN_ROOT" ] && [ -d "./.claude-plugin/prose" ]; then
  CANDIDATE_PLUGIN_ROOT="$(pwd)/.claude-plugin"
  if [ -f "$CANDIDATE_PLUGIN_ROOT/plugin.json" ] && python3 - "$CANDIDATE_PLUGIN_ROOT/plugin.json" <<'PY'
import json
import sys

try:
    with open(sys.argv[1], encoding="utf-8") as f:
        data = json.load(f)
except Exception:
    sys.exit(1)
sys.exit(0 if data.get("name") == "livespec-overseer" else 1)
PY
  then
    PLUGIN_ROOT="$CANDIDATE_PLUGIN_ROOT"
  fi
fi
if [ -z "$PLUGIN_ROOT" ]; then
  CODEX_CACHE_PARENT="$HOME/.codex/plugins/cache/livespec-overseer/livespec-overseer"
  if [ -d "$CODEX_CACHE_PARENT" ]; then
    CANDIDATE_PLUGIN_ROOT="$(find "$CODEX_CACHE_PARENT" -mindepth 1 -maxdepth 1 -type d | sort -V | tail -n 1)"
    if [ -n "$CANDIDATE_PLUGIN_ROOT" ] && [ -f "$CANDIDATE_PLUGIN_ROOT/prose/supervise-plan.md" ]; then
      PLUGIN_ROOT="$CANDIDATE_PLUGIN_ROOT"
    else
      PLUGIN_ROOT_DIAGNOSTICS="$PLUGIN_ROOT_DIAGNOSTICS
cache root not found: no valid version under $CODEX_CACHE_PARENT"
    fi
  else
    PLUGIN_ROOT_DIAGNOSTICS="$PLUGIN_ROOT_DIAGNOSTICS
cache root not found: $CODEX_CACHE_PARENT"
  fi
fi
if [ -z "$PLUGIN_ROOT" ]; then
  CODEX_BIN=""
  CODEX_TRIED="command -v codex, $HOME/.local/bin/codex, $HOME/.bun/bin/codex"
  if command -v codex >/dev/null 2>&1; then
    CODEX_BIN="$(command -v codex)"
  elif [ -x "$HOME/.local/bin/codex" ]; then
    CODEX_BIN="$HOME/.local/bin/codex"
  elif [ -x "$HOME/.bun/bin/codex" ]; then
    CODEX_BIN="$HOME/.bun/bin/codex"
  else
    PLUGIN_ROOT_DIAGNOSTICS="$PLUGIN_ROOT_DIAGNOSTICS
codex executable not found; tried: $CODEX_TRIED"
  fi
  if [ -n "$CODEX_BIN" ]; then
    PLUGIN_ROOT="$("$CODEX_BIN" plugin list --json -m livespec-overseer 2>/tmp/livespec-overseer-codex-plugin-list.err | python3 -c 'import json, sys
try:
    data = json.load(sys.stdin)
except Exception:
    sys.exit(0)
for plugin in data.get("installed", []):
    if plugin.get("pluginId") == "livespec-overseer@livespec-overseer":
        sys.stdout.write(plugin.get("source", {}).get("path", ""))
        break' 2>/dev/null || true)"
    if [ -z "$PLUGIN_ROOT" ]; then
      PLUGIN_ROOT_DIAGNOSTICS="$PLUGIN_ROOT_DIAGNOSTICS
plugin not installed according to: $CODEX_BIN plugin list --json -m livespec-overseer"
      if [ -s /tmp/livespec-overseer-codex-plugin-list.err ]; then
        PLUGIN_ROOT_DIAGNOSTICS="$PLUGIN_ROOT_DIAGNOSTICS
codex plugin list stderr: $(cat /tmp/livespec-overseer-codex-plugin-list.err)"
      fi
    fi
  fi
fi
if [ -z "$PLUGIN_ROOT" ] || [ ! -f "$PLUGIN_ROOT/prose/supervise-plan.md" ]; then
  echo "livespec-overseer plugin root not found." >&2
  if [ -n "$PLUGIN_ROOT_DIAGNOSTICS" ]; then
    printf "%b\n" "$PLUGIN_ROOT_DIAGNOSTICS" >&2
  fi
  echo "Install it first:" >&2
  echo "  codex plugin marketplace add thewoolleyman/livespec-overseer" >&2
  echo "  codex plugin add livespec-overseer@livespec-overseer" >&2
  exit 1
fi
```

If resolution fails, STOP and surface those install instructions rather than
improvising paths.

## Invocation

Read `$PLUGIN_ROOT/prose/supervise-plan.md` in full, then execute it
end-to-end.

```bash
cat "$PLUGIN_ROOT/prose/supervise-plan.md"
```

This binding adds NO operation behavior of its own; the operator contract lives
in the prose.
