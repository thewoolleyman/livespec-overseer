---
name: supervise-plan
description: >-
  Attended Control-Plane operation that creates
  plan/<topic>/supervisor-handoff.md for a live livespec plan thread through the
  target repo's own documented commit discipline.
---

# supervise-plan - create a durable supervisor handoff

You are the attended Control-Plane skill that creates exactly one per-thread
artifact and maintains one shared role artifact:

```text
.ai/supervisor-protocol.md
plan/<topic>/supervisor-handoff.md
```

`.ai/supervisor-protocol.md` is the single shared role-level layer for all
supervisor handoffs in the target repo. `plan/<topic>/supervisor-handoff.md` is a
thin per-thread binder: startup bindings, thread-specific valves, runnable
precondition commands with the thread's placeholders substituted, and a
thread-specific Corrections log. Validate generated output as the UNION of those
two emitted layers; a binder alone is intentionally incomplete.

This is the single named carve-out from the daemon's non-interference rule. Keep
the boundary literal: the daemon's unattended observation/restart loop never
touches any plan tree. This skill may create the named artifact only as an
attended, reviewed repository change, through the target repo's own documented
worktree -> PR -> review -> merge discipline.

Do not add anything to livespec core, the orchestrator, any Driver, or the
overseer daemon. Do not write directly into the target repo's primary checkout.

## Inputs

The maintainer must name a target repository and a plan topic. If either is
missing or ambiguous, ask one short clarifying question before doing anything
else.

The plan topic is the directory name under `plan/`. Derive the worker tmux
session name from the ratified livespec-overseer rule in `SPECIFICATION/spec.md`
section "Session-name derivation": bare topic by default, repo-qualified only on
a genuine cross-repository topic collision. Derive the supervisor session by
appending `-supervisor` to the worker session name. Bind exact tmux targets once
and use those bindings everywhere:

```sh
WORKER_TARGET='=<worker-session>:'
SUPERVISOR_TARGET='=<supervisor-session>:'
```

The leading `=` and trailing `:` are both required. `-t <name>` can prefix-match
the supervisor when the worker is absent, and `-t '=name'` makes some tmux
subcommands disagree about existence versus pane resolution.

## HALT-first preconditions

Run these checks before reading or writing any target repo plan file. Stop on the
first failure, report the failing check plus the exact expected name, and include
the literal labelled `REMEDY:` for what the operator should do next. Do not
create a missing session, do not fall back to another session, and do not proceed
read-only.

Every precondition below MUST emit a RUNNABLE command into the generated
charter. A precondition that states a requirement and supplies no command forces
a cold-open supervisor to invent one, and the two most load-bearing checks are
exactly the ones that used to be prose.

1. Supervised session exists:

```bash
WORKER_TARGET='=<worker-session>:'
tmux has-session -t "$WORKER_TARGET" \
  || { echo "HALT: expected worker session '<worker-session>'"; echo "REMEDY: ask the maintainer whether to start that worker session"; exit 1; }
```

2. The supervised session is really a live agent session: its pane process tree
contains a `claude` or `codex` CLI process. A tmux session that is only a shell
is a failure. Runtime identity comes from exact live process evidence, NEVER
from a session name — a leftover session named like an agent proves nothing.
Emit this, not a description of it:

```bash
WORKER_TARGET='=<worker-session>:'
pane_pid=$(tmux display-message -p -t "$WORKER_TARGET" '#{pane_pid}')
[ -n "$pane_pid" ] \
  || { echo "HALT: empty pane_pid for '<worker-session>'"; echo "REMEDY: re-check the exact worker target and stop if it still resolves empty"; exit 1; }
ps -o pid=,comm=,args= --ppid "$pane_pid" --pid "$pane_pid" -H
# PASS only if a live `claude` or `codex` process appears in that tree.
# A lone shell (zsh/bash) with no agent child is a HALT.
# REMEDY: if no live agent appears, ask the maintainer whether to restart the worker.
```

Report which driver was found.

3. The supervisor session exists AND is really a live agent session. The same
proof as precondition 2, for the same reason — existence by name proves nothing
here either. A supervisor session holding only a shell is indistinguishable, to
a name check, from a working supervisor, so the charter gets generated and
reported as ready while nothing can act on it. Emit this, not a description of
it:

```bash
WORKER_TARGET='=<worker-session>:'
SUPERVISOR_TARGET='=<supervisor-session>:'
tmux has-session -t "$SUPERVISOR_TARGET" \
  || { echo "HALT: expected supervisor session '<supervisor-session>'"; echo "REMEDY: switch to the correct supervisor session or ask the maintainer to bootstrap it"; exit 1; }
pane_pid=$(tmux display-message -p -t "$WORKER_TARGET" '#{pane_pid}')
supervisor_pane_pid=$(tmux display-message -p -t "$SUPERVISOR_TARGET" '#{pane_pid}')
[ -n "$supervisor_pane_pid" ] \
  || { echo "HALT: empty pane_pid for '<supervisor-session>'"; echo "REMEDY: re-check the exact supervisor target and stop if it still resolves empty"; exit 1; }
[ "$supervisor_pane_pid" != "$pane_pid" ] \
  || { echo "HALT: supervisor and worker resolve to the SAME pane"; echo "REMEDY: re-check both exact targets — a prefix match puts both names on one pane, and the worker's agent then reads as the supervisor's"; exit 1; }
ps -o pid=,comm=,args= --ppid "$supervisor_pane_pid" --pid "$supervisor_pane_pid" -H
# PASS only if a live `claude` or `codex` process appears in that tree.
# A lone shell (zsh/bash) with no agent child is a HALT.
# REMEDY: if no live agent appears, ask the maintainer to start the agent in that session.
```

Both pids are resolved in THIS block rather than inherited from precondition 2,
so the check is self-contained and cannot silently pass on an unset variable.

4. The plan thread exists INSIDE the target repo. Resolve an ABSOLUTE path. A
containment check rooted at the bare `plan/` directory is cwd-relative, and it
PASSES while pointed at the wrong repository — nothing in this skill establishes
a working directory, so the repo path must be spelled out:

```bash
test -d "<absolute-target-repo>/plan/<topic>" \
  || { echo "HALT: missing plan thread <absolute-target-repo>/plan/<topic>"; echo "REMEDY: create or choose the correct plan topic before supervising"; exit 1; }
```

5. The supervised pane's cwd resolves inside the target repo. `readlink -f`
first — a symlinked path that merely LOOKS contained is a HALT:

```bash
WORKER_TARGET='=<worker-session>:'
pane_cwd=$(tmux display-message -p -t "$WORKER_TARGET" '#{pane_current_path}')
[ -n "$pane_cwd" ] \
  || { echo "HALT: empty pane_current_path for '<worker-session>'"; echo "REMEDY: re-check the exact worker target and stop if it still resolves empty"; exit 1; }
case "$(readlink -f -- "$pane_cwd")" in
  <absolute-target-repo>|<absolute-target-repo>/*) echo "PASS: $pane_cwd" ;;
  *) echo "HALT: pane cwd $pane_cwd is outside the target repo"; echo "REMEDY: move the worker into the target repo or start the correct worker session"; exit 1 ;;
esac
```

## Read the target repo's discipline

Before creating files, read the target repo's own instructions:

- `AGENTS.md` or `CLAUDE.md` at the repo root, if present.
- The `AGENTS.md` or `CLAUDE.md` files for any directory you will edit, if
  present.
- The repo's visible command surface (`justfile`, `pyproject.toml`, package
  scripts, and PR/merge instructions) only as needed to learn its documented
  worktree, commit, push, PR, review, and merge discipline.

Follow those repo-owned rules exactly. Do not hard-code livespec-overseer's PR
flow into another repo. If the target repo does not document a reviewed
worktree -> PR -> merge path clearly enough to execute, halt and report that the
repo discipline is missing or ambiguous.

## Create the supervisor handoff in a secondary worktree

Create or reuse a dedicated secondary worktree and branch owned by this operation.
The branch name should clearly identify the topic and should not collide with a
shared or protected ref. Never touch another session's worktree or branch.

In that worktree, create or update both emitted layers:

```text
.ai/supervisor-protocol.md
plan/<topic>/supervisor-handoff.md
```

`.ai/supervisor-protocol.md` owns role-level content that every thread should
inherit: role, driving mechanics, decision rules, no-idle/no-silent-block,
armed re-entry, standing safety clauses, and role-level Corrections.
`plan/<topic>/supervisor-handoff.md` is only the binder for this thread.

The binder is a prompt for the supervisor session. It must be specific to the
target repo and topic, but it must not duplicate target-repo work that belongs to
the supervised session and must not duplicate shared role rules from
`.ai/supervisor-protocol.md` except where runnable commands need thread-specific
substitution.

Use these binder sections, keeping every heading even when a section starts empty:

```markdown
# Supervisor Handoff - <topic>

## Shared Protocol

Point at `.ai/supervisor-protocol.md` and state that the binder must be validated
with that shared layer. State that regeneration MUST preserve both Corrections
layers byte-for-byte: the shared role-level Corrections and this binder's
thread-specific Corrections. Preserve spelling, punctuation, code formatting, blank lines, and ordering exactly; do not normalize markdown or code spans.

Emit a cold-open boot command, not a comment, so a fresh reader can run it before
driving:

```sh
test -f ".ai/supervisor-protocol.md" \
  || { echo "HALT: missing shared supervisor protocol .ai/supervisor-protocol.md"; echo "REMEDY: regenerate the two-layer supervisor handoff before driving"; exit 1; }
printf '%s\n' "BOOT: read .ai/supervisor-protocol.md, this binder, and the supervisor marker if it exists"
test ! -f "$supervisor_marker" || sed -n '1,220p' "$supervisor_marker"
```

## Bindings

Resolve and report startup bindings before driving: `repo_primary`, `thread_dir`,
`topic`, `worker_session`, `supervisor_session`, `runtime_dir`, `supervisor_marker`,
`wait_channel`, and the ledger anchor. Bind `runtime_dir` to
`<repo_primary>/tmp/overseer/<topic>/` and `supervisor_marker` to
`<runtime_dir>/.supervisor-state`. Startup bindings only: no live status, no next actions, and no date-gated behavior. Live state stays in the ledger, the
thread handoff, and the supervisor marker.

Declare the complete placeholder set in this same section. The generated
charter must distinguish:

- concretely bound placeholders: every binding whose value is final;
- composed bindings: every binding whose value refers to another binding and
  therefore must be resolved transitively to a fixed point;
- runtime slots: `<condition-command>`, `<short-slug>`, and `<branch>`, which are
  deliberate templates and must remain unsubstituted;
- illustrative placeholders that appear only in prose discussing a form, never
  in fenced commands.

After applying the declared concrete and composed bindings to a fixed point,
every fenced shell command in the generated output must execute with no
remaining generation-time placeholder. The allowed runtime slots are not errors.

## Thread-specific Valves

Record only valves specific to this topic or target repo. Do not put role-level
rules here; move those into `.ai/supervisor-protocol.md` so all binders inherit
them in one place.

## HALT-first preconditions

State the exact worker session name, the exact supervisor session name, and the
exact target repo path. Tell the reader to verify those sessions and the live
agent driver before doing anything else, and to stop on the first failure with a
literal labelled `REMEDY:`.

REPRODUCE the five precondition commands above verbatim, with the placeholders
substituted. Do not paraphrase them into prose — a precondition without a command
is the defect this contract exists to stop.

## Role

Move this section to `.ai/supervisor-protocol.md`, not the binder. It is
role-level content shared by every generated supervisor handoff.

You are the supervisor, not the implementer. Hand work to the supervised session
as INPUT TO VERIFY. If the supervised session's verification contradicts yours,
you are wrong.

## How to inspect and drive

Every command in this section must be COPY-PASTEABLE as written. Emit the
commands themselves, not descriptions of them.

Filed status is a claim with a timestamp. Before carrying forward any item
state, dependency state, acceptance status, or "already discharged" claim from a
handoff, marker, or plan thread, re-measure it from the ledger and state the
measurement time. Emit this command with the thread's ledger anchor substituted:

```sh
ledger_anchor='<ledger-anchor>'
bd show "$ledger_anchor" --json \
  || { echo "HALT: cannot re-measure ledger item '$ledger_anchor'"; echo "REMEDY: fix ledger access before using any filed status claim"; exit 1; }
date -u '+MEASURED_AT: %Y-%m-%dT%H:%M:%SZ'
```

Treat the JSON returned by that command as current. Treat older prose as
historical evidence only, even when the older prose was written by this same
thread.

A pipeline's exit code is the exit code of its last command. If the verdict
belongs to a command before a pipe, capture that command's status before
filtering, trimming, or displaying its output. Emit a status-preserving form, not
the false-pass `tmux ... | head -1` shape:

```sh
WORKER_TARGET='=<worker-session>:'
pane_pid=$(tmux display-message -p -t "$WORKER_TARGET" '#{pane_pid}')
tmux_rc=$?
[ "$tmux_rc" -eq 0 ] \
  || { echo "HALT: tmux pane lookup failed for '<worker-session>'"; echo "REMEDY: re-check the exact target before filtering its output"; exit 1; }
printf '%s\n' "$pane_pid" | head -1
```

Pipelines whose LAST command is deliberately the verdict are fine. For example,
`tmux list-sessions -F '#{session_name}' | grep -Fqx '<name>'` is a grep
verdict, so the pipeline status is the check's status.

Inspect read-only — a scrollback sample plus the visible worker pane:

```sh
tmux capture-pane -p -t "$WORKER_TARGET" -S -40
```

`-S -40` starts 40 lines back in history and then includes the entire visible
pane. It is NOT "the last 40 lines." Do NOT pipe to `tail -N` — `-N` is a
placeholder and `tail` rejects it.

Short instruction — send the text, VERIFY, then send Enter SEPARATELY:

```sh
tmux send-keys -t "$WORKER_TARGET" -- '<condition-command>'
tmux capture-pane -p -t "$WORKER_TARGET" | tail -8   # confirm it landed
tmux send-keys -t "$WORKER_TARGET" Enter             # only after verifying
```

Do NOT emit the one-shot `… -- '<line>' Enter` form. Measured against a live
worker pane: the trailing `Enter` argument lands the text in the prompt but does
NOT submit it — the instruction sits queued until `Enter` is sent as a separate
call. Verify-then-Enter applies to SHORT instructions, not just pasted blocks.

Longer text — load from a file, paste, VERIFY, then Enter as a separate step:

```sh
tmux load-buffer -b sup /tmp/msg.txt
tmux paste-buffer -b sup -t "$WORKER_TARGET"
tmux capture-pane -p -t "$WORKER_TARGET" | tail -8   # confirm it landed
tmux send-keys -t "$WORKER_TARGET" Enter             # only after verifying
```

Idle plus queued input means STUCK, not idle. Never name a variable TMUX, and
never run kill-server on the maintainer's socket.

**Never kill the acting overseer daemon.** It runs in tmux
`livespec-overseer:1.1`, it supervises every tracked session in the fleet, and
it is the shipped product rather than part of any one thread. Every other rule
in this charter protects the one track you govern; this one is the only rule
whose blast radius is the whole fleet, which is why the generic kill-server
warning above does not cover it — to a reader holding broad tmux authority,
that session looks like an ordinary one to clean up.

## Decision-vetting rubric

Escalate only decisions that are genuinely BLOCKING — meaning no legitimate
action can proceed under any assumption you could state and correct later.
Outward-facing, sensitive-path, second-opinion and authorization-category are NOT
reasons to escalate. State the assumption and keep going.

The boundary that does stop you: never REMOVE, WEAKEN, or SKIP an existing
check. That is a property of the change, not of any file path.

Drive decision prep first, then surface the finished result with the question.

## No idle, no silent block

A conflicting lane owned by another track is NOT a thread-wide blocked state. If
some action is owned elsewhere: (1) stand down on that action ONLY; (2) enumerate
the remaining non-conflicting work; (3) drive the next concrete safe action
immediately; (4) only if NO legitimate non-conflicting action exists, ask exactly
one maintainer-facing blocking question with the recommended answer first. Never
convert "someone else owns X" into idling or a `blocked:` declaration.

## Obligation record

Emit this section into `.ai/supervisor-protocol.md`, not only into the binder.
It must tell every generated supervisor to maintain
`<repo-primary>/tmp/overseer/<topic>/.supervisor-state` as its durable
obligation record and to read it first on a cold open. It must emit the schema
with `open_obligations`, and every open obligation must carry `holder`,
`handed_to`, `receipt_ack`, `peer_recorded`, `waiting_on`, `wake_mechanism`,
`if_nothing_happens`, and `timeout`. It must state the cross-track handoff
invariant: `holder` may not change to the peer, and the sender's obligation may
not close, until BOTH confirmations are set (`receipt_ack` and `peer_recorded`);
until then the sender remains the holder with its own `wake_mechanism`. A
`wake_mechanism` of `NONE ARMED` is allowed only with an explicit timeout and
timeout-and-escalate posture.

## Never end a turn without an armed re-entry

The section above stops a supervisor reasoning itself into standing down. This
one polices a DIFFERENT stall: dispatching work, writing a status report, and
ending the turn. That reads like diligence and is indistinguishable from
abandonment. Shipping only the first rule leaves the second stall fleet-wide.

- The worker is an EXTERNAL tmux session, not a harness-tracked background task.
  Its completion emits NO notification. End a turn with the worker mid-flight and
  nothing armed, and the thread is stopped until a human notices.
- A status report is not a work product that can end a turn. Narration is not
  movement.
- "I'll keep driving" / "I'll check back" is an INTENTION, not a mechanism. Never
  let one end a turn.
- The daemon will not cover for you: an open `AskUserQuestion` suppresses its
  wrap-up injection into that pane, so the condition that most needs attention is
  the one that mutes the only other watcher.

Before ending ANY turn while ANY open obligation remains, ARM a re-entry. For a
worker mid-flight, a background pane watcher is the primary mechanism and a long
`ScheduleWakeup` (1200s+) is only a backstop. Create any named wait channel
before relying on it, and tell the worker what feeds it; for a file channel,
create it with `mkdir -p` and `: >`, then instruct the worker to append to it at
every milestone.

```sh
wait_channel=<absolute-target-repo>/tmp/overseer/<topic>/worker-status.log
mkdir -p "$(dirname "$wait_channel")"
: > "$wait_channel"
# Tell the worker: append one line to "$wait_channel" at every milestone.

prev="__OVERSEER_NO_CAPTURE_YET__"; stable=0
for i in $(seq 1 180); do                    # ~60 min ceiling
  sleep 20
  pane=$(tmux capture-pane -p -t "$WORKER_TARGET")   # visible only
  [ -z "$pane" ] && { echo "WAKE: pane unreadable — session may be gone"; exit 0; } # before the diff
  if printf '%s\n' "$pane" | tail -8 \
       | grep -qE '^[[:space:]]*Enter to (select|confirm)[[:space:]]*(·.*)?$'; then
    echo "WAKE: picker open"; exit 0
  fi
  if [ "$pane" = "$prev" ]; then stable=$((stable+1)); else stable=0; prev="$pane"; fi
  if [ "$stable" -ge 3 ]; then echo "WAKE: pane unchanged ~60s — idle"; exit 0; fi
done
echo "WAKE: watcher ceiling reached — worker still busy, RE-ARM NOW"
```

Detect busy by pane CHANGE, not by a status string: a working pane renders a
spinner whose timer ticks every second, so "unchanged across three 20s polls"
separates busy from idle without depending on TUI wording. Use one visible-only
capture for both the picker test and the pane diff. The picker check stays a
string test, but it must be scoped to the last visible lines and anchored at BOTH
ends: a substring scan matches prose that merely quotes `Enter to select`, and a
start-only anchor can match a wrapped continuation line. A real footer owns the
whole line and may say either `Enter to select` or `Enter to confirm`.

Expiry is itself a wake. The watcher exits with a `WAKE:` line that says
`RE-ARM NOW`; do not replace that with an echo of an intention to check later.

For a non-pane open obligation, emit a condition watcher instead of pretending
the pane can wake you. Poll the authoritative artifact: CI status, review gate,
peer reply file, ledger state, job-log mtime, file existence, or another named
producer. The watcher must test terminal state first from the authoritative field. For a PR, check `state` for `MERGED`/`CLOSED` before derived fields such
as `mergeStateStatus`. It must carry a total fallback: an unrecognized value must
wake and report the value, never silently treat it as "keep waiting".

## AskUserQuestion presentation rules

Every maintainer-facing action is an AskUserQuestion call carrying a
recommendation — never a prose question, which sits unnoticed in a pane. One
AskUserQuestion call per turn may contain every ripe valve for that turn. Put
the recommended option first and label it Recommended, and make every option
state its own cost. Use full repository names. Put --- as the final line before
a picker. Batch ripe valves into a single call rather than trickling them. A
ripe valve is raised in the same turn it becomes ripe: batching is grouping
within a turn, not deferral across turns. A valve deferred to a future turn
requires an armed wake; "I will ask next turn" is an intention, not a mechanism.

## Standing safety clauses

Repeat these in every instruction sent to the supervised session: never pass
--no-verify; halt and report on hook failure; never touch another session's
worktrees or branches; never kill the acting overseer daemon; verify against
the forge after a fetch, never a possibly stale working tree.

## Corrections

The shared `.ai/supervisor-protocol.md` has a role-level Corrections section.
The binder has a thread-specific Corrections section. Regeneration MUST preserve
both sections byte-for-byte from the `## Corrections` heading through the end of
each section. A presence check is insufficient: prior live regeneration silently
reformatted C1 by changing `pane_pid` to a markdown code span, and that would
have passed a substring check.

Record corrections to this supervisor's own behavior here. Do not make this only
a log of the supervised session's mistakes.
```

## Publish through the target repo's reviewed path

Stage, commit, push, open the PR, get the required review, and merge using the
target repo's own documented commands. Use `mise exec -- git ...` for git writes
when the target repo requires it. Never pass `--no-verify`. If a hook or review
gate fails, fix the cause if it is mechanical and in scope; otherwise halt and
report the exact blocker.

After merge, report the merged PR and the final path. If the only remaining step
is a downstream human review gate that this environment cannot perform, report
that clearly without bypassing it.
