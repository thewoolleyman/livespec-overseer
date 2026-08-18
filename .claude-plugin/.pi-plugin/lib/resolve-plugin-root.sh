#!/usr/bin/env bash
#
# resolve-plugin-root.sh - the single realization of the pi bindings'
# plugin-root resolution.
#
# Ordered algorithm - first hit wins:
#
#   1. $LIVESPEC_OVERSEER_PLUGIN_ROOT when set and non-empty. The explicit
#      operator override; covers nonstandard dev setups such as driving a
#      sibling checkout's plugin.
#   2. <project-root>/.claude-plugin when that checkout IS this plugin
#      (dogfooding) - identity confirmed from its plugin manifest name, never
#      from the path alone.
#   3. <project-root>/.pi/git/github.com/thewoolleyman/livespec-overseer/.claude-plugin
#      - the PROJECT-scope pi package clone (`pi install ... -l`).
#   4. ~/.pi/agent/git/github.com/thewoolleyman/livespec-overseer/.claude-plugin
#      - the USER-scope pi package clone.
#
# A candidate counts as resolved ONLY when it carries the shared prose directory
# and its plugin.json names this plugin. On success, writes the resolved
# absolute path to stdout. On failure, writes an install diagnostic to stderr.

set -euo pipefail

plugin_name="livespec-overseer"
project_root="${1:-.}"

if ! project_root="$(cd "$project_root" 2>/dev/null && pwd)"; then
    printf 'plugin root resolution failed: project root %s does not exist\n' \
        "${1:-.}" >&2
    exit 1
fi

clone_suffix="git/github.com/thewoolleyman/$plugin_name/.claude-plugin"

candidates=()
if [ -n "${LIVESPEC_OVERSEER_PLUGIN_ROOT:-}" ]; then
    candidates+=("$LIVESPEC_OVERSEER_PLUGIN_ROOT")
fi
candidates+=("$project_root/.claude-plugin")
candidates+=("$project_root/.pi/$clone_suffix")
candidates+=("${HOME:-}/.pi/agent/$clone_suffix")

is_this_plugin() {
    manifest="$1/plugin.json"
    [ -f "$manifest" ] || return 1
    python3 - "$manifest" "$plugin_name" <<'PY'
import json
import sys

try:
    with open(sys.argv[1], encoding="utf-8") as handle:
        manifest = json.load(handle)
except (OSError, ValueError):
    sys.exit(1)
sys.exit(0 if manifest.get("name") == sys.argv[2] else 1)
PY
}

for candidate in "${candidates[@]}"; do
    if [ -d "$candidate/prose" ] && is_this_plugin "$candidate"; then
        printf '%s\n' "$candidate"
        exit 0
    fi
done

{
    printf '%s plugin root could not be resolved.\n' "$plugin_name"
    printf 'A candidate resolves only when it carries prose/ AND its\n'
    printf 'plugin.json names this plugin. Searched, in order:\n'
    for candidate in "${candidates[@]}"; do
        printf '    %s\n' "$candidate"
    done
    printf '\n'
    if [ -n "${LIVESPEC_OVERSEER_PLUGIN_ROOT:-}" ]; then
        printf 'LIVESPEC_OVERSEER_PLUGIN_ROOT is set to %s but does not resolve.\n' \
            "$LIVESPEC_OVERSEER_PLUGIN_ROOT"
        printf 'An override that does not resolve is a configuration error, not\n'
        printf 'a missing install - fix or unset it before installing anything.\n\n'
    fi
    printf 'Install this plugin as a project-scope pi package from the repo root:\n'
    printf '    pi install git:github.com/thewoolleyman/%s@release -l\n\n' "$plugin_name"
    printf 'pi resolves project packages only after the project is TRUSTED, so a\n'
    printf 'non-interactive run (-p, --mode json, --mode rpc) in an untrusted\n'
    printf 'project silently loads nothing. Establish trust before driving\n'
    printf 'unattended.\n'
} >&2
exit 1
