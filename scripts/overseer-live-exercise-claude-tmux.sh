#!/usr/bin/env bash
# Claude lifecycle controller for the isolated exercise's private terminal.
#
# This foreground program records observations of released overseer mechanics.  It
# deliberately asks the shipped modules whether a pane is idle and whether a
# registered Claude process is live; it does not imitate either judgement.

set -uo pipefail

# A host-level PYTHONHOME can make the fixture's interpreter fail before it can
# register its idle Claude session. The exercise owns its launcher and every
# Python helper it invokes, so preserve the normal interpreter discovery instead.
unset PYTHONHOME

backend="${OVERSEER_EXERCISE_BACKEND:?missing exercise backend}"
instance="${OVERSEER_EXERCISE_INSTANCE:?missing exercise instance}"
endpoint="${OVERSEER_EXERCISE_ENDPOINT:?missing exercise endpoint}"
topic="${OVERSEER_EXERCISE_TOPIC:?missing exercise topic}"
evidence="${OVERSEER_EXERCISE_EVIDENCE:?missing exercise evidence directory}"

checkout="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
package="$checkout/overseer"
repo="${OVERSEER_EXERCISE_REPO:-/tmp/livespec-overseer-exercise-repo}"
claude_home="${CLAUDE_HOME:-$HOME/.claude}"
lifecycle="$evidence/lifecycle.jsonl"
snapshot="$HOME/.livespec-overseer-status.json"
state_file="$repo/tmp/overseer/$topic/.overseer-state"
# This is populated by ``new-window -P``.  `overseer-start` renames the window
# which holds the agent, whereas pane ids remain stable through both that
# rename and the daemon's later atomic `respawn-pane -k`.
agent_target=""

readonly POLL_SECONDS=2
readonly CLAUDE_READY_TIMEOUT=60
readonly DAEMON_TIMEOUT=600
readonly ADOPTION_TIMEOUT=120
readonly WRAPUP_TIMEOUT=180
readonly REPLACEMENT_TIMEOUT=300
readonly CONTINUATION_TIMEOUT=180

[[ "$backend" == tmu[x] ]] || {
  echo "overseer Claude exercise: --backend must be tmux, got '$backend'" >&2
  exit 2
}
[[ -S "$endpoint" ]] || {
  echo "overseer Claude exercise: private socket is missing: $endpoint" >&2
  exit 2
}
[[ ! -e "$lifecycle" ]] || {
  echo "overseer Claude exercise: refusing to append to existing $lifecycle" >&2
  exit 2
}

json_record() {
  python3 -c '
import json
import sys
print(json.dumps({"stage": sys.argv[1], "status": sys.argv[2], "detail": sys.argv[3]}))
' "$1" "$2" "$3"
}

record() {
  mkdir -p -- "$evidence"
  json_record "$1" "$2" "$3" >>"$lifecycle"
}

pass_stage() {
  record "$1" passed "$2"
  echo "overseer Claude exercise: $1 passed — $2"
}

fail_stage() {
  record "$1" failed "$2"
  echo "overseer Claude exercise: $1 FAILED — $2" >&2
  exit 1
}

# This is intentionally the sole invocation point for the terminal client.  All
# controller calls consequently address the endpoint supplied by the exercise.
tx() {
  tmux -S "$endpoint" "$@"
}

pane_capture() {
  tx capture-pane -p -e -t "$agent_target" 2>/dev/null
}

pane_submit() {
  tx send-keys -l -t "$agent_target" "$1" >/dev/null 2>&1 &&
    tx send-keys -t "$agent_target" Enter >/dev/null 2>&1
}

shipped() {
  PYTHONPATH="$package" python3 "$@"
}

claude_pane_is_idle() {
  pane_capture | shipped -c '
import signals
import sys
sys.exit(0 if signals.is_idle_input(capture_text=sys.stdin.read()) else 1)
'
}

pane_ctx_remaining() {
  pane_capture | shipped -c '
import signals
import sys
value = signals.parse_ctx_remaining(capture_text=sys.stdin.read())
print("" if value is None else value)
'
}

live_identity() {
  shipped -c '
import claude_sessions
import sys

sessions_dir, topic = sys.argv[1:]
for session in claude_sessions.read_live_sessions(sessions_dir=sessions_dir):
    if session.name == topic:
        print(f"claude:{session.pid}:{session.proc_start}:{session.name}")
        break
' "$claude_home/sessions" "$topic"
}

identity_pid() {
  local _kind pid _start _topic
  IFS=: read -r _kind pid _start _topic <<<"$1"
  printf '%s\n' "$pid"
}

identity_starttime() {
  local _kind _pid start _topic
  IFS=: read -r _kind _pid start _topic <<<"$1"
  printf '%s\n' "$start"
}

snapshot_row() {
  shipped -c '
import json
import sys
from pathlib import Path

path, topic, field = Path(sys.argv[1]), sys.argv[2], sys.argv[3]
try:
    rows = json.loads(path.read_text(encoding="utf-8")).get("rows", [])
except (OSError, json.JSONDecodeError):
    rows = []
for row in rows:
    if row.get("topic") == topic:
        value = row.get(field)
        print("" if value is None else value)
        break
' "$snapshot" "$topic" "$1"
}

overseer_cli() {
  shipped "$package/supervisor.py" "$@"
}

wait_until() {
  local seconds="$1"
  shift
  local deadline=$((SECONDS + seconds))
  while ((SECONDS < deadline)); do
    if "$@"; then
      return 0
    fi
    sleep "$POLL_SECONDS"
  done
  return 1
}

ensure_scratch_plan() {
  mkdir -p -- "$repo/plan/$topic" "$repo/tmp"
  [[ -f "$repo/.gitignore" ]] || printf 'tmp/\n' >"$repo/.gitignore"
  if [[ ! -d "$repo/.git" ]]; then
    git -C "$repo" init -q
    git -C "$repo" add -A
    git -C "$repo" -c user.email=exercise@invalid -c user.name=exercise \
      commit -qm "isolated overseer exercise scratch plan"
  fi
  local watch="$HOME/.livespec-overseer-repos.json"
  [[ -f "$watch" ]] || python3 -c '
import json
import sys
print(json.dumps({"repos": [sys.argv[1]]}))
' "$repo" >"$watch"
  : >>"$HOME/.livespec-overseer.jsonl"
}

clear_claude_trust_gate() {
  # The exercise owns this scratch home.  Declare the repo trusted before the
  # client starts so a directory-trust picker cannot consume its first input.
  mkdir -p -- "$claude_home"
  python3 -c '
import json
import sys
from pathlib import Path

path = Path(sys.argv[1])
repo = sys.argv[2]
try:
    value = json.loads(path.read_text(encoding="utf-8"))
except (OSError, json.JSONDecodeError):
    value = {}
projects = value.setdefault("projects", {})
projects[repo] = {"trustLevel": "trusted"}
path.write_text(json.dumps(value), encoding="utf-8")
' "$claude_home/settings.json" "$repo"
}

daemon_is_up() {
  [[ -f "$snapshot" ]]
}

stage_bootstrap() {
  local start_log
  ensure_scratch_plan
  clear_claude_trust_gate
  mkdir -p -- "$evidence"
  # The daemon's released launch plan deliberately invokes bare `claude`.  A
  # direct stub exercise may put its stub on this controller's PATH after the
  # private terminal server was started, so copy that PATH into THIS private
  # server before starting the pane.  No default terminal server is addressed.
  tx set-environment -g PATH "$PATH" ||
    fail_stage bootstrap "could not set PATH on the private exercise server"
  tx set-option -g default-shell /bin/sh ||
    fail_stage bootstrap "could not set the private exercise server's non-login shell"
  agent_target="$(tx new-window -d -P -F '#{pane_id}' -t "$instance:" -n "$topic" -c "$repo" \
    "exec env PATH=$(printf %q "$PATH") CLAUDECODE=1 claude --dangerously-skip-permissions -n $(printf %q "$topic")")" ||
    fail_stage bootstrap "could not open the Claude window on the private server"
  [[ "$agent_target" == %* ]] || fail_stage bootstrap \
    "private exercise server returned no pane id for the Claude window"
  wait_until "$CLAUDE_READY_TIMEOUT" claude_pane_is_idle || fail_stage bootstrap \
    "no idle Claude input in retained pane $agent_target within ${CLAUDE_READY_TIMEOUT}s (shipped is_idle_input never held)"
  predecessor="$(live_identity)"
  [[ -n "$predecessor" ]] || fail_stage bootstrap \
    "no live named Claude registry identity for '$topic' after its input became idle"
  start_log="$evidence/overseer-start.log"
  : >"$start_log"
  pane_submit "!$package/overseer-start > $(printf %q "$start_log") 2>&1" || fail_stage bootstrap \
    "could not submit overseer-start to Claude pane $agent_target"
  wait_until "$DAEMON_TIMEOUT" daemon_is_up || fail_stage bootstrap \
    "overseer-start did not create status snapshot $snapshot within ${DAEMON_TIMEOUT}s"
  pass_stage bootstrap \
    "Claude pane $agent_target named '$topic' with predecessor $predecessor; overseer-start brought up the daemon above it"
}

track_is_adopted() {
  [[ "$(snapshot_row session_identity)" == "$predecessor" ]]
}

stage_adoption() {
  wait_until "$ADOPTION_TIMEOUT" track_is_adopted || fail_stage adoption \
    "the daemon snapshot never bound '$topic' to $predecessor within ${ADOPTION_TIMEOUT}s (snapshot said '$(snapshot_row session_identity)')"
  pass_stage adoption "the daemon snapshot binds $topic to $predecessor at $(snapshot_row tmux)"
}

wrapup_round_is_open() {
  [[ "$(snapshot_row round_open)" == True ]]
}

stage_wrapup() {
  local remaining threshold
  remaining="$(pane_ctx_remaining)"
  [[ "$remaining" =~ ^[0-9]+$ ]] || fail_stage wrap-up \
    "no numeric remaining-context reading in retained Claude pane $agent_target"
  threshold=$((remaining + 1))
  overseer_cli add --repo "$repo" --topic "$topic" \
    --epic "$OVERSEER_EXERCISE_EPIC" --ctx-threshold "$threshold" >/dev/null 2>&1 ||
    fail_stage wrap-up "could not open a per-track wrap-up round at ${threshold}%"
  wait_until "$WRAPUP_TIMEOUT" wrapup_round_is_open || fail_stage wrap-up \
    "the daemon opened no wrap-up round within ${WRAPUP_TIMEOUT}s at threshold ${threshold}% with ${remaining}% remaining"
  pass_stage wrap-up \
    "the daemon injected its wind-down after the controller opened a round at ${threshold}% just above live ${remaining}% remaining context"
}

session_declared_ready() {
  [[ -f "$state_file" ]] && [[ "$(head -n 1 -- "$state_file")" == ready ]]
}

stage_declaration() {
  pane_submit "!cd $(printf %q "$repo") && PYTHONPATH=$(printf %q "$package") python3 $(printf %q "$package/declare.py") ready" ||
    fail_stage declaration "could not submit the shipped ready declaration"
  wait_until "$CLAUDE_READY_TIMEOUT" session_declared_ready || fail_stage declaration \
    "the session never declared ready through overseer-declare within ${CLAUDE_READY_TIMEOUT}s"
  pass_stage declaration "the session declared ready through shipped overseer-declare at $state_file"
}

successor_is_bound() {
  successor="$(live_identity)"
  [[ -n "$successor" ]] && [[ "$successor" != "$predecessor" ]] &&
    [[ "$(snapshot_row session_identity)" == "$successor" ]]
}

stage_replacement() {
  wait_until "$REPLACEMENT_TIMEOUT" successor_is_bound || fail_stage replacement \
    "no different live Claude identity appeared within ${REPLACEMENT_TIMEOUT}s; predecessor was $predecessor"
  pass_stage replacement \
    "atomic respawn retained pane $agent_target and replaced predecessor pid=$(identity_pid "$predecessor") starttime=$(identity_starttime "$predecessor") with successor pid=$(identity_pid "$successor") starttime=$(identity_starttime "$successor")"
}

resume_line_delivered() {
  local captured
  captured="$(pane_capture)" || return 1
  grep -qF "resume plan epic $OVERSEER_EXERCISE_EPIC in repository $repo" <<<"$captured"
}

stage_continuation() {
  wait_until "$CONTINUATION_TIMEOUT" resume_line_delivered || fail_stage continuation \
    "the resume line naming epic $OVERSEER_EXERCISE_EPIC never reached successor $successor"
  pass_stage continuation \
    "the resume line reached successor $successor; the scratch plan is NOT a real ledger thread, so this proves resume-line delivery only and claims no end-to-end ledger continuation"
}

predecessor=""
successor=""
: "${OVERSEER_EXERCISE_EPIC:=overseer-exercise-epic}"

stage_bootstrap
stage_adoption
stage_wrapup
stage_declaration
stage_replacement
stage_continuation

echo "overseer Claude exercise: every required lifecycle stage passed"
