#!/bin/bash
# usage: engine-on-green.sh <label> <parallel> <work-item-id>...
#
# The ONLY way a drain engine is launched. Gates, in order, ALL MEASURED:
#   1. the Claude credential PROBE returns `usable` (dispatcher claude-cred-status),
#      retried every 5 minutes. NEVER a claimed reset time from a 429 body or a handoff.
#      While usable, an unexpired dispatcher exhaustion record is retired through the
#      codified valve (clear-provider-exhaustion); "nothing to clear" is success.
#   2. the newest master CI run is green (a red master means "not launching", exit 2).
# Then the engine starts DETACHED (setsid nohup) so it outlives the shell and the LLM session.
#
# Environment (all optional):
#   DRAIN_REPO        target repo path        (default: git toplevel of cwd)
#   DRAIN_PLUGIN_ROOT orchestrator plugin cache dir holding scripts/bin/dispatcher.py
#                     (default: newest livespec-orchestrator-beads-fabro cache entry)
#   DRAIN_WRAPPER     credential wrapper      (default: /usr/local/bin/with-livespec-env.sh)
#   DRAIN_INVOKER     journal invoker string  (default: skill:drain-backlog)
#   DRAIN_STATE_DIR   state dir               (default: $DRAIN_REPO/tmp/drain-backlog)
set -u
label=${1:?label}; parallel=${2:?parallel}; shift 2
[ $# -ge 1 ] || { echo "usage: $0 <label> <parallel> <work-item-id>..." >&2; exit 64; }

REPO=${DRAIN_REPO:-$(git rev-parse --show-toplevel 2>/dev/null || pwd)}
W=${DRAIN_WRAPPER:-/usr/local/bin/with-livespec-env.sh}
INVOKER=${DRAIN_INVOKER:-skill:drain-backlog}
STATE=${DRAIN_STATE_DIR:-$REPO/tmp/drain-backlog}
mkdir -p "$STATE"
if [ -n "${DRAIN_PLUGIN_ROOT:-}" ]; then
  R=$DRAIN_PLUGIN_ROOT
else
  R=$(ls -td "$HOME"/.claude/plugins/cache/livespec-orchestrator-beads-fabro/livespec-orchestrator-beads-fabro/*/scripts/bin/dispatcher.py 2>/dev/null | head -1 | xargs -r dirname | xargs -r dirname | xargs -r dirname)
fi
[ -f "$R/scripts/bin/dispatcher.py" ] || { echo "dispatcher.py not found under plugin root '$R'" >&2; exit 66; }
gh_repo=$(git -C "$REPO" config --get remote.origin.url | sed -E 's#.*github.com[:/]##; s#\.git$##')
LOG=$STATE/engine-$label.log
items=(); for i in "$@"; do items+=(--item "$i"); done

ts() { date -u +%H:%M:%SZ; }
probe() {
  $W -- python3 "$R/scripts/bin/dispatcher.py" claude-cred-status --json 2>/dev/null | jq -r '.condition // "probe-failed"'
}

# Gate 1: the probe. A "wait before retrying" remedy carries no time; the probe's own next result is the signal.
while true; do
  c=$(probe); echo "$(ts) credential probe: $c"
  if [ "$c" = "usable" ]; then
    $W -- python3 "$R/scripts/bin/dispatcher.py" clear-provider-exhaustion --repo "$REPO" --provider claude \
      --reason "credential probe returned usable at $(ts) (drain launcher $label)" \
      --invoker "$INVOKER" 2>&1 | grep -v '^WARN' | grep -E 'CLEARED|nothing to clear' | tail -n 1 || true
    break
  fi
  sleep 300
done

# Gate 2: master green. Red master -> not launching (exit 2) so the caller can decide; queued/in_progress -> wait.
# The poll is a CONDITIONAL request: it sends the stored ETag as If-None-Match, so an unchanged master answers a
# 304 that costs no primary rate-limit budget. `gh api --cache` is NOT used: it is a TTL-only local cache that
# sends no If-None-Match, so a TTL equal to the sleep makes every iteration a counted 200. `gh api -i` prints the
# status line and headers on stdout and exits 1 on a 304, so the status line (not the exit code) decides.
etag=""
runs_url="repos/$gh_repo/actions/workflows/ci.yml/runs?branch=master&per_page=1"
while true; do
  if [ -n "$etag" ]; then
    resp=$(gh api -i -H "If-None-Match: $etag" "$runs_url" 2>/dev/null); rc=$?
  else
    resp=$(gh api -i "$runs_url" 2>/dev/null); rc=$?
  fi
  http=$(printf '%s\n' "$resp" | head -n 1 | awk '{print $2}')
  # Unchanged since the last evaluation, which did not end the gate: wait without spending a counted call.
  if [ "$http" = "304" ]; then sleep 60; continue; fi
  [ "$rc" -eq 0 ] || { sleep 60; continue; }
  etag=$(printf '%s\n' "$resp" | tr -d '\r' | sed -n 's/^[Ee][Tt][Aa][Gg]:[[:space:]]*//p' | head -n 1)
  j=$(printf '%s\n' "$resp" | tr -d '\r' | sed '1,/^$/d')
  id=$(jq -r '.workflow_runs[0].id' <<<"$j"); st=$(jq -r '.workflow_runs[0].status' <<<"$j"); cc=$(jq -r '.workflow_runs[0].conclusion' <<<"$j")
  echo "$(ts) newest master run $id status=$st conclusion=$cc"
  if [ "$st" = "completed" ]; then
    if [ "$cc" = "success" ]; then
      echo "MASTER GREEN at run $id -> launching detached engine '$label' for $# item(s), parallel $parallel, log $LOG"
      setsid nohup $W -- env PATH="$HOME/.fabro/bin:$PATH" \
        python3 "$R/scripts/bin/dispatcher.py" loop --repo "$REPO" --budget $# --parallel "$parallel" \
        "${items[@]}" --invoker "$INVOKER" --json > "$LOG" 2>&1 < /dev/null &
      echo "engine pid $!"
      sleep 60
      grep -E '"event": "(ledger-admit|capacity-deferred|loop-pick)"|refus|ERROR' "$LOG" | cut -c1-200 | tail -n 8 || true
      exit 0
    else
      echo "MASTER RED at run $id ($cc) -> not launching"; exit 2
    fi
  fi
  sleep 60
done
