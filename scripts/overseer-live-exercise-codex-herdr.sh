#!/usr/bin/env bash
# Codex-on-Herdr lifecycle controller for the isolated live exercise.
#
# Read `overseer/live-exercise.md` first. This is the foreground controller that
# `scripts/overseer-live-exercise.sh` runs inside its namespace, and it is also
# runnable directly against a herdr instance started for the run. It appends one
# record per required lifecycle stage to `$OVERSEER_EXERCISE_EVIDENCE/lifecycle.jsonl`
# and the checked-in verifier grades the result.
#
# IT DRIVES THE SHIPPED MECHANICS AND RE-IMPLEMENTS NONE OF THEM. Every judgement
# about a pane -- is this an idle Codex TUI, which rollout is live for this topic --
# is delegated to the released `overseer/` modules, so the exercise cannot pass
# against a daemon whose own predicates would read the pane differently. The six
# stages are observations of the daemon's work, never substitutes for it:
#
#   bootstrap    a Codex pane exists, is named for the topic, and the shipped
#                `overseer-start` brought the daemon up beside it
#   adoption     the daemon's own snapshot binds that Codex session to the track
#   wrap-up      the daemon injected its escalating wind-down, after the round was
#                opened with a per-track threshold just above live remaining context
#   declaration  the session declared through the shipped `overseer-declare ready`
#   replacement  the daemon bound a DIFFERENT canonical rollout in the same pane
#   continuation the resume line reached that successor
#
# Per `overseer/live-exercise.md` the scratch plan is deliberately not a real ledger
# thread, so the continuation record says so and claims no end-to-end continuation.

set -uo pipefail

backend="${OVERSEER_EXERCISE_BACKEND:?missing exercise backend}"
instance="${OVERSEER_EXERCISE_INSTANCE:?missing exercise instance}"
topic="${OVERSEER_EXERCISE_TOPIC:?missing exercise topic}"
evidence="${OVERSEER_EXERCISE_EVIDENCE:?missing exercise evidence directory}"

checkout="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
package="$checkout/overseer"
repo="${OVERSEER_EXERCISE_REPO:-/tmp/livespec-overseer-exercise-repo}"
lifecycle="$evidence/lifecycle.jsonl"
codex_home="${CODEX_HOME:-$HOME/.codex}"
snapshot="$HOME/.livespec-overseer-status.json"
state_file="$repo/tmp/overseer/$topic/.overseer-state"

# Bounds. Every wait is bounded and every expiry is a FAILED record for the stage
# that was waiting, never a silent downgrade to a later stage.
readonly POLL_SECONDS=2
readonly CODEX_READY_TIMEOUT=60
# A warmed exercise normally reaches its first status snapshot in seconds. The
# release host, however, runs this alongside fleet work and the daemon itself, so
# bootstrap is allowed one loaded-host ten-minute window before it is diagnosed.
readonly DAEMON_TIMEOUT=600
readonly ADOPTION_TIMEOUT=120
readonly WRAPUP_TIMEOUT=180
readonly REPLACEMENT_TIMEOUT=300
readonly CONTINUATION_TIMEOUT=180
readonly AGENT_PANE=w1:p1

[[ "$backend" == herdr ]] || {
  echo "overseer codex herdr exercise: --backend must be herdr, got '$backend'" >&2
  exit 2
}

# `overseer/live-exercise.md`: a reused evidence directory is refused BEFORE
# anything is written, so an incomplete run can never inherit passed lifecycle
# records from an earlier attempt. The coordinator enforces this for a harness run;
# repeating it here covers a direct run, and it is not hypothetical -- two
# controllers sharing one evidence directory interleave their records, and the
# result reads as one run that recorded a stage twice.
[[ -e "$lifecycle" ]] && {
  echo "overseer codex herdr exercise: refusing to append to an existing $lifecycle" >&2
  exit 2
}

# --------------------------------------------------------------------------- #
# Evidence
# --------------------------------------------------------------------------- #

json_record() {
  # Build one lifecycle record with python so a detail carrying quotes, newlines
  # or a backslash cannot forge or truncate a record the verifier then reads.
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
  echo "overseer codex herdr exercise: $1 passed — $2"
}

# A stage that cannot complete ENDS the run. The verifier would reject a later
# `passed` anyway, but stopping here is what makes the evidence honest: nothing
# after the first failure was ever observed, so nothing after it is recorded.
fail_stage() {
  record "$1" failed "$2"
  echo "overseer codex herdr exercise: $1 FAILED — $2" >&2
  exit 1
}

# --------------------------------------------------------------------------- #
# Herdr — the ONE place the CLI is invoked
# --------------------------------------------------------------------------- #

# Every herdr command this controller issues goes through here, so `--session
# "$OVERSEER_EXERCISE_INSTANCE"` is carried by CONSTRUCTION rather than by each
# call site remembering it. Addressing the operator's default server is the
# failure this forecloses: it is the one mistake that would reach outside the
# exercise instance.
hd() {
  herdr --session "$instance" "$@"
}

pane_capture() {
  hd pane read "$1" --source visible --format text 2>/dev/null
}

pane_submit() {
  # `pane run` is herdr's send-text-and-Enter: the controller's own keystrokes into
  # a pane it owns. The DAEMON's injections use the bracketed `pane.send_input`
  # path, and proving THAT is the wrap-up stage's job, not this helper's.
  hd pane run "$1" "$2" >/dev/null 2>&1
}

# --------------------------------------------------------------------------- #
# Shipped predicates — imported, never reimplemented
# --------------------------------------------------------------------------- #

shipped() {
  PYTHONPATH="$package" python3 "$@"
}

codex_pane_is_idle() {
  pane_capture "$1" | shipped -c '
import sys

import signals

capture = sys.stdin.read()
sys.exit(0 if signals.is_codex_idle_input(capture_text=capture) else 1)
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

# The canonical rollout id the SHIPPED discovery join reports for this topic, or
# empty when no live Codex session carries it. This is the same join the daemon
# adopts and proves a successor through.
live_rollout_id() {
  shipped -c '
import sys

import codex_sessions

home, topic = sys.argv[1], sys.argv[2]
for session in codex_sessions.read_live_codex_sessions(codex_home=home):
    if session.name == topic:
        print(session.session_id)
        break
' "$codex_home" "$topic"
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
  # The released checkout's own one-shot track CLI. `overseer-start` provisions the
  # DAEMON's runtime from the matching release tag, so in the exercise's released
  # checkout this CLI and the running daemon are the same build -- which is what
  # lets the CLI's store write be read back by the daemon on its next tick.
  shipped "$package/supervisor.py" "$@"
}

# --------------------------------------------------------------------------- #
# Waiting
# --------------------------------------------------------------------------- #

# Poll `predicate` until it succeeds or `seconds` elapse. Returns non-zero on
# expiry so the CALLING STAGE decides what the expiry means and records it.
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

# --------------------------------------------------------------------------- #
# Scratch plan tree
# --------------------------------------------------------------------------- #

# Idempotent: `scripts/overseer-live-exercise.sh` already builds this inside its
# namespace, and a direct run needs it built here. The daemon REFUSES to run
# unless each watched repo's `tmp/overseer/` is gitignored, so the ignore rule and
# the `git init` are preconditions rather than tidiness.
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

# --------------------------------------------------------------------------- #
# Stage 1 — bootstrap
# --------------------------------------------------------------------------- #

stage_bootstrap() {
  local overseer_start_output bootstrap_started_at elapsed launcher_output
  ensure_scratch_plan
  mkdir -p -- "$codex_home"
  cat >"$codex_home/config.toml" <<EOF
[tui]
status_line = ["model-with-reasoning", "current-dir", "context-remaining"]

[projects."$repo"]
trust_level = "trusted"
EOF
  hd workspace create --cwd "$repo" --label "$topic" >/dev/null 2>&1

  # Export into the RETAINED SHELL rather than onto one command line. The daemon's
  # replacement relaunches `codex` in this same shell, so a per-command
  # environment would leave the successor launch with no `codex` to find -- a
  # replacement failure whose message names the shell, not the environment.
  pane_submit "$AGENT_PANE" \
    "export HOME=$HOME CODEX_HOME=$codex_home HERDR_SOCKET_PATH=$HERDR_SOCKET_PATH PATH=$PATH"
  pane_submit "$AGENT_PANE" "cd $(printf '%q' "$repo")"
  pane_submit "$AGENT_PANE" "codex --dangerously-bypass-approvals-and-sandbox"

  wait_until "$CODEX_READY_TIMEOUT" codex_pane_is_idle "$AGENT_PANE" || fail_stage bootstrap \
    "no idle Codex TUI in pane $AGENT_PANE within ${CODEX_READY_TIMEOUT}s (shipped is_codex_idle_input never held)"

  pane_submit "$AGENT_PANE" "/rename $topic"
  wait_until "$CODEX_READY_TIMEOUT" rollout_is_named || fail_stage bootstrap \
    "Codex never indexed a rollout under thread_name '$topic' within ${CODEX_READY_TIMEOUT}s"
  predecessor="$(live_rollout_id)"

  # The checkout's own shipped bootstrap executable, run from INSIDE the Codex
  # pane: it detects its owning pane through process ancestry and refuses unless a
  # supported agent runtime is in that ancestry, so it cannot be run for the
  # session from out here.
  overseer_start_output="$evidence/overseer-start.log"
  : >"$overseer_start_output"
  bootstrap_started_at=$SECONDS
  pane_submit "$AGENT_PANE" "!$package/overseer-start > $(printf '%q' "$overseer_start_output") 2>&1"
  if ! wait_until "$DAEMON_TIMEOUT" daemon_is_up; then
    elapsed=$((SECONDS - bootstrap_started_at))
    launcher_output="$(tail -n 3 -- "$overseer_start_output" 2>/dev/null || true)"
    [[ -n "$launcher_output" ]] || launcher_output="<no launcher output captured>"
    fail_stage bootstrap \
      "overseer-start did not bring a daemon up after ${elapsed}s (no status snapshot at $snapshot; overseer-start last output: ${launcher_output//$'\n'/ | })"
  fi

  pass_stage bootstrap \
    "codex pane $AGENT_PANE named '$topic' on rollout $predecessor; overseer-start brought up the daemon beside it"
}

rollout_is_named() {
  [[ -n "$(live_rollout_id)" ]]
}

daemon_is_up() {
  [[ -f "$snapshot" ]]
}

# --------------------------------------------------------------------------- #
# Stage 2 — adoption
# --------------------------------------------------------------------------- #

track_is_adopted() {
  [[ "$(snapshot_row session_identity)" == "codex:$predecessor" ]]
}

stage_adoption() {
  wait_until "$ADOPTION_TIMEOUT" track_is_adopted || fail_stage adoption \
    "the daemon's own snapshot never bound '$topic' to codex:$predecessor within ${ADOPTION_TIMEOUT}s (snapshot said '$(snapshot_row session_identity)')"
  pass_stage adoption \
    "the daemon's snapshot binds $topic to codex:$predecessor at $(snapshot_row tmux)"
}

# --------------------------------------------------------------------------- #
# Stage 3 — wrap-up
# --------------------------------------------------------------------------- #

wrapup_round_is_open() {
  [[ "$(snapshot_row round_open)" == "True" ]]
}

stage_wrapup() {
  local remaining threshold
  # A fresh Codex session can report 100% remaining, where a threshold capped at
  # 99% cannot open a round. Submit a bounded context-burning turn and wait for
  # its idle prompt before reading the value used to set the threshold.
  pane_submit "$AGENT_PANE" "seq 1 60000"
  wait_until "$CODEX_READY_TIMEOUT" codex_pane_is_idle "$AGENT_PANE" || fail_stage wrap-up \
    "Codex did not return to an idle prompt after the context-burning turn within ${CODEX_READY_TIMEOUT}s"
  remaining="$(pane_ctx_remaining "$AGENT_PANE")"
  [[ -n "$remaining" ]] || fail_stage wrap-up \
    "no remaining-context reading in pane $AGENT_PANE; the daemon cannot cross a threshold it cannot read"
  # Just ABOVE live remaining context, per `overseer/AGENTS.md` "How to exercise it
  # live" item 4: that is what opens a round on demand instead of waiting for a
  # real session to burn its window down.
  threshold=$((remaining + 5))
  ((threshold <= 99)) || threshold=99

  # The epic is recorded FIRST. A track with no epic is deliberately never
  # respawned -- the declaration is preserved and the track surfaced -- so opening
  # the round before recording one would stall the replacement stage behind a
  # refusal that is correct behaviour.
  overseer_cli add --repo "$repo" --topic "$topic" \
    --epic "$OVERSEER_EXERCISE_EPIC" --ctx-threshold "$threshold" >/dev/null 2>&1

  wait_until "$WRAPUP_TIMEOUT" wrapup_round_is_open || fail_stage wrap-up \
    "the daemon opened no wrap-up round within ${WRAPUP_TIMEOUT}s against threshold ${threshold}% with ${remaining}% remaining"
  pass_stage wrap-up \
    "the daemon injected its wind-down and opened a round at threshold ${threshold}% against ${remaining}% remaining"
}

# --------------------------------------------------------------------------- #
# Stage 4 — declaration
# --------------------------------------------------------------------------- #

session_declared_ready() {
  [[ -f "$state_file" ]] && [[ "$(head -n 1 -- "$state_file")" == ready ]]
}

stage_declaration() {
  # Through the SHIPPED declare surface, from the session's own pane. Writing the
  # state file on the session's behalf would prove the daemon reads a file the
  # exercise wrote, which is not the cardinal rule's claim.
  pane_submit "$AGENT_PANE" \
    "!cd $repo && PYTHONPATH=$package python3 $package/declare.py ready 2>&1 | tail -2"
  wait_until "$CODEX_READY_TIMEOUT" session_declared_ready || fail_stage declaration \
    "the session never declared 'ready' through overseer-declare within ${CODEX_READY_TIMEOUT}s"
  pass_stage declaration \
    "the session declared ready through the shipped overseer-declare, at $state_file"
}

# --------------------------------------------------------------------------- #
# Stage 5 — replacement
# --------------------------------------------------------------------------- #

successor_is_bound() {
  successor="$(live_rollout_id)"
  [[ -n "$successor" ]] && [[ "$successor" != "$predecessor" ]]
}

stage_replacement() {
  wait_until "$REPLACEMENT_TIMEOUT" successor_is_bound || fail_stage replacement \
    "no different canonical rollout was bound for '$topic' within ${REPLACEMENT_TIMEOUT}s; predecessor $predecessor was still the live rollout"
  pass_stage replacement \
    "the daemon replaced predecessor rollout $predecessor with successor rollout $successor in pane $AGENT_PANE"
}

# --------------------------------------------------------------------------- #
# Stage 6 — continuation
# --------------------------------------------------------------------------- #

resume_line_delivered() {
  pane_capture "$AGENT_PANE" | grep -qF "resume plan epic $OVERSEER_EXERCISE_EPIC in repository $repo"
}

stage_continuation() {
  wait_until "$CONTINUATION_TIMEOUT" resume_line_delivered || fail_stage continuation \
    "the resume line naming epic $OVERSEER_EXERCISE_EPIC never reached successor rollout $successor within ${CONTINUATION_TIMEOUT}s"
  # The limitation is part of the record, not a footnote: `overseer/live-exercise.md`
  # makes the scratch plan deliberately NOT a real ledger thread, so what was proven
  # is delivery of the resume line to the successor -- never that a ledger thread
  # continued end to end.
  pass_stage continuation \
    "the resume line naming epic $OVERSEER_EXERCISE_EPIC reached successor rollout $successor; the scratch plan is NOT a real ledger thread, so this proves resume-line delivery only and claims no end-to-end ledger continuation"
}

# --------------------------------------------------------------------------- #

predecessor=""
successor=""
: "${OVERSEER_EXERCISE_EPIC:=overseer-exercise-epic}"
: "${HERDR_SOCKET_PATH:=$HOME/.config/herdr/sessions/$instance/herdr.sock}"

stage_bootstrap
stage_adoption
stage_wrapup
stage_declaration
stage_replacement
stage_continuation

echo "overseer codex herdr exercise: every required lifecycle stage passed"
