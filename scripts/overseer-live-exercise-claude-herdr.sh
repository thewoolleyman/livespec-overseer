#!/usr/bin/env bash
# Claude Code-on-Herdr lifecycle controller for the isolated live exercise.
#
# This foreground controller drives the shipped daemon only: Claude input and
# process identity are read through the released `overseer/` predicates, while
# lifecycle evidence records observations made after each daemon action.

set -uo pipefail

backend="${OVERSEER_EXERCISE_BACKEND:?missing exercise backend}"
instance="${OVERSEER_EXERCISE_INSTANCE:?missing exercise instance}"
topic="${OVERSEER_EXERCISE_TOPIC:?missing exercise topic}"
evidence="${OVERSEER_EXERCISE_EVIDENCE:?missing exercise evidence directory}"

checkout="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
package="$checkout/overseer"
repo="${OVERSEER_EXERCISE_REPO:-/tmp/livespec-overseer-exercise-repo}"
lifecycle="$evidence/lifecycle.jsonl"
claude_home="${CLAUDE_HOME:-$HOME/.claude}"
snapshot="$HOME/.livespec-overseer-status.json"
state_file="$repo/tmp/overseer/$topic/.overseer-state"

readonly POLL_SECONDS=2
readonly CLAUDE_READY_TIMEOUT=60
readonly DAEMON_TIMEOUT=600
readonly ADOPTION_TIMEOUT=120
readonly WRAPUP_TIMEOUT=180
readonly REPLACEMENT_TIMEOUT=300
readonly CONTINUATION_TIMEOUT=180
readonly AGENT_PANE=w1:p1

[[ "$backend" == herdr ]] || {
  echo "overseer claude herdr exercise: --backend must be herdr, got '$backend'" >&2
  exit 2
}
[[ ! -e "$lifecycle" ]] || {
  echo "overseer claude herdr exercise: refusing to append to an existing $lifecycle" >&2
  exit 2
}

json_record() {
  python3 -c '
import json
import sys

stage, status, detail = sys.argv[1], sys.argv[2], sys.argv[3]
print(json.dumps({"stage": stage, "status": status, "detail": detail}))
' "$1" "$2" "$3"
}

record() {
  mkdir -p -- "$evidence"
  json_record "$1" "$2" "$3" >>"$lifecycle"
}

pass_stage() {
  record "$1" passed "$2"
  echo "overseer claude herdr exercise: $1 passed — $2"
}

fail_stage() {
  record "$1" failed "$2"
  echo "overseer claude herdr exercise: $1 FAILED — $2" >&2
  exit 1
}

# Every Herdr operation is constructed here so the exercise can never address
# the operator's default instance.
hd() {
  herdr --session "$instance" "$@"
}

pane_capture() {
  hd pane read "$1" --source visible --format text 2>/dev/null
}

pane_submit() {
  hd pane run "$1" "$2" >/dev/null 2>&1
}

shipped() {
  PYTHONPATH="$package" python3 "$@"
}

claude_pane_is_idle() {
  pane_capture "$1" | shipped -c '
import sys
import signals

sys.exit(0 if signals.is_idle_input(capture_text=sys.stdin.read()) else 1)
'
}

claude_trust_gate_is_open() {
  pane_capture "$1" | shipped -c '
import sys
import signals

sys.exit(0 if signals.is_structured_gate(capture_text=sys.stdin.read()) else 1)
'
}

pane_ctx_remaining() {
  pane_capture "$1" | shipped -c '
import sys
import signals

remaining = signals.parse_ctx_remaining(capture_text=sys.stdin.read())
print("" if remaining is None else remaining)
'
}

# The live process identity comes from the shipped Claude registry reader. It
# validates the pid/starttime pair against /proc, so a stale registry file can
# never satisfy bootstrap or replacement.
live_claude_identity() {
  shipped -c '
import sys
import claude_sessions

home, topic = sys.argv[1], sys.argv[2]
for session in claude_sessions.read_live_sessions(sessions_dir=f"{home}/sessions"):
    if session.name == topic:
        print(f"{session.pid}:{session.proc_start}")
        break
' "$claude_home" "$topic"
}

snapshot_row() {
  shipped -c '
import json
import sys
from pathlib import Path

path, topic, field = Path(sys.argv[1]), sys.argv[2], sys.argv[3]
if not path.is_file():
    sys.exit(0)
try:
    rows = json.loads(path.read_text(encoding="utf-8")).get("rows", [])
except json.JSONDecodeError:
    sys.exit(0)
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
  [[ -d "$repo/.git" ]] || {
    git -C "$repo" init -q
    git -C "$repo" add -A
    git -C "$repo" -c user.email=exercise@invalid -c user.name=exercise \
      commit -qm "isolated overseer exercise scratch plan"
  }
  local watch="$HOME/.livespec-overseer-repos.json"
  [[ -f "$watch" ]] || python3 -c '
import json
import sys

print(json.dumps({"repos": [sys.argv[1]]}))
' "$repo" >"$watch"
  : >>"$HOME/.livespec-overseer.jsonl"
}

initial_claude_surface_is_ready() {
  claude_pane_is_idle "$AGENT_PANE" || claude_trust_gate_is_open "$AGENT_PANE"
}

clear_claude_trust_gate() {
  # A fresh scratch folder can stop Claude at its folder-trust picker. Clearing
  # that shipped structured gate before adoption prevents a profile-less row.
  if claude_trust_gate_is_open "$AGENT_PANE"; then
    pane_submit "$AGENT_PANE" "1"
  fi
  wait_until "$CLAUDE_READY_TIMEOUT" claude_pane_is_idle "$AGENT_PANE"
}

stage_bootstrap() {
  local overseer_start_output bootstrap_started_at elapsed launcher_output
  ensure_scratch_plan
  mkdir -p -- "$evidence" "$claude_home/sessions"
  hd workspace create --cwd "$repo" --label "$topic" >/dev/null 2>&1
  pane_submit "$AGENT_PANE" \
    "export HOME=$HOME PATH=$PATH HERDR_SOCKET_PATH=$HERDR_SOCKET_PATH"
  pane_submit "$AGENT_PANE" \
    "cd $(printf %q "$repo") && claude --dangerously-skip-permissions -n $(printf %q "$topic")"
  wait_until "$CLAUDE_READY_TIMEOUT" initial_claude_surface_is_ready || fail_stage bootstrap \
    "no idle Claude TUI or trust-folder gate in pane $AGENT_PANE within ${CLAUDE_READY_TIMEOUT}s"
  clear_claude_trust_gate || fail_stage bootstrap \
    "Claude did not become idle after clearing its trust-folder gate in pane $AGENT_PANE"
  wait_until "$CLAUDE_READY_TIMEOUT" claude_identity_is_live || fail_stage bootstrap \
    "no live named Claude registry identity for '$topic' within ${CLAUDE_READY_TIMEOUT}s"
  predecessor="$(live_claude_identity)"

  overseer_start_output="$evidence/overseer-start.log"
  : >"$overseer_start_output"
  bootstrap_started_at=$SECONDS
  pane_submit "$AGENT_PANE" \
    "!$package/overseer-start > $(printf '%q' "$overseer_start_output") 2>&1"
  if ! wait_until "$DAEMON_TIMEOUT" daemon_is_up; then
    elapsed=$((SECONDS - bootstrap_started_at))
    launcher_output="$(tail -n 3 -- "$overseer_start_output" 2>/dev/null || true)"
    [[ -n "$launcher_output" ]] || launcher_output="<no launcher output captured>"
    fail_stage bootstrap \
      "overseer-start did not bring a daemon up after ${elapsed}s (no status snapshot at $snapshot; overseer-start last output: ${launcher_output//$'\n'/ | })"
  fi
  pass_stage bootstrap \
    "Claude pane $AGENT_PANE named '$topic' has predecessor pid/starttime $predecessor; overseer-start brought up the daemon beside it"
}

claude_identity_is_live() {
  [[ -n "$(live_claude_identity)" ]]
}

daemon_is_up() {
  [[ -f "$snapshot" ]]
}

track_is_adopted() {
  [[ "$(snapshot_row session_identity)" == "claude:$predecessor:$topic" ]]
}

stage_adoption() {
  wait_until "$ADOPTION_TIMEOUT" track_is_adopted || fail_stage adoption \
    "the daemon's own snapshot never bound '$topic' to claude:$predecessor:$topic within ${ADOPTION_TIMEOUT}s (snapshot said '$(snapshot_row session_identity)')"
  tracked_pane="$(snapshot_row tmux)"
  [[ -n "$tracked_pane" ]] || fail_stage adoption \
    "the daemon bound '$topic' to its Claude identity but reported no retained pane"
  pass_stage adoption \
    "the daemon's snapshot binds $topic to claude:$predecessor:$topic at $tracked_pane"
}

wrapup_round_is_open() {
  [[ "$(snapshot_row round_open)" == "True" ]]
}

stage_wrapup() {
  local remaining threshold
  remaining="$(pane_ctx_remaining "$AGENT_PANE")"
  [[ "$remaining" =~ ^[0-9]+$ ]] || fail_stage wrap-up \
    "no numeric remaining-context reading in pane $AGENT_PANE"
  threshold=$((remaining + 1))
  overseer_cli add --repo "$repo" --topic "$topic" \
    --epic "$OVERSEER_EXERCISE_EPIC" --ctx-threshold "$threshold" >/dev/null 2>&1
  wait_until "$WRAPUP_TIMEOUT" wrapup_round_is_open || fail_stage wrap-up \
    "the daemon opened no wrap-up round within ${WRAPUP_TIMEOUT}s against threshold ${threshold}% with ${remaining}% remaining"
  pass_stage wrap-up \
    "the daemon injected its wind-down and opened a round at threshold ${threshold}% just above the observed ${remaining}% remaining context"
}

session_declared_ready() {
  [[ -f "$state_file" ]] && [[ "$(head -n 1 -- "$state_file")" == ready ]]
}

stage_declaration() {
  pane_submit "$AGENT_PANE" \
    "!cd $repo && PYTHONPATH=$package python3 $package/declare.py ready 2>&1 | tail -2"
  wait_until "$CLAUDE_READY_TIMEOUT" session_declared_ready || fail_stage declaration \
    "the session never declared 'ready' through overseer-declare within ${CLAUDE_READY_TIMEOUT}s"
  pass_stage declaration \
    "the session declared ready through the shipped overseer-declare, at $state_file"
}

successor_is_bound() {
  successor="$(snapshot_row session_identity)"
  [[ "$successor" == claude:* ]] && [[ "$successor" != "claude:$predecessor:$topic" ]] && \
    [[ "$(snapshot_row tmux)" == "$tracked_pane" ]]
}

stage_replacement() {
  wait_until "$REPLACEMENT_TIMEOUT" successor_is_bound || fail_stage replacement \
    "no different Claude process identity was bound for '$topic' within ${REPLACEMENT_TIMEOUT}s; predecessor pid/starttime was $predecessor"
  pass_stage replacement \
    "the daemon replaced predecessor Claude pid/starttime $predecessor with successor $successor in retained pane $AGENT_PANE"
}

resume_line_delivered() {
  local captured
  captured="$(pane_capture "$AGENT_PANE")" || return 1
  grep -qF "resume plan epic $OVERSEER_EXERCISE_EPIC in repository $repo" <<<"$captured"
}

stage_continuation() {
  wait_until "$CONTINUATION_TIMEOUT" resume_line_delivered || fail_stage continuation \
    "the resume line naming epic $OVERSEER_EXERCISE_EPIC never reached successor $successor within ${CONTINUATION_TIMEOUT}s"
  pass_stage continuation \
    "the resume line naming epic $OVERSEER_EXERCISE_EPIC reached successor $successor; the scratch plan is NOT a real ledger thread, so this proves resume-line delivery only and claims no end-to-end ledger continuation"
}

predecessor=""
successor=""
tracked_pane=""
: "${OVERSEER_EXERCISE_EPIC:=overseer-exercise-epic}"
: "${HERDR_SOCKET_PATH:=$HOME/.config/herdr/sessions/$instance/herdr.sock}"

stage_bootstrap
stage_adoption
stage_wrapup
stage_declaration
stage_replacement
stage_continuation

echo "overseer claude herdr exercise: every required lifecycle stage passed"
