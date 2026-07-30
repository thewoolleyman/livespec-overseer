# Supervisor Handoff - supervisor-prompt-quality

## Shared Protocol

Read `.ai/supervisor-protocol.md` before driving. Validate this binder together
with that shared layer; this binder is intentionally thin and is not complete by
itself.

Regenerating this file MUST preserve two Corrections sections byte-for-byte:

- `.ai/supervisor-protocol.md` `## Corrections` for role-level corrections.
- This file's `## Corrections` for thread-specific corrections.

Live thread status is NOT in this file. It lives in the ledger, in `handoff.md`,
and in `$supervisor_marker`. Read those first on a cold open.

## Bindings

Resolve and REPORT these before driving anything. Startup bindings only - no
live status, no next actions, and no date-gated behavior.

| Binding | Value |
|---|---|
| `repo_primary` | `/data/projects/livespec-overseer` |
| `thread_dir` | `plan/supervisor-prompt-quality/` |
| `worker_session` | `supervisor-prompt-quality` |
| `supervisor_session` | `supervisor-prompt-quality-supervisor` |
| `WORKER_TARGET` | `'=supervisor-prompt-quality:'` |
| `SUPERVISOR_TARGET` | `'=supervisor-prompt-quality-supervisor:'` |
| `runtime_dir` | `<repo_primary>/tmp/overseer/supervisor-prompt-quality/` |
| `supervisor_marker` | `<runtime_dir>/.supervisor-state` |
| `wait_channel` | `<runtime_dir>/worker-status.log` |
| `ledger_anchor` | `overseer-t7qqik` |

## Thread-specific Valves

- This thread's subject is generated-prompt drift. Every generated-output claim
  must be checked against the union of `.ai/supervisor-protocol.md` and this
  binder, not against either layer alone.
- Byte-compare both Corrections layers across regeneration. Do not normalize
  markdown or code spans; changed bytes are drift.
- The current binder is a positive control for iteration stability: shared layer
  plus binder validates cleanly, while the binder alone deliberately does not.
- Factory branches never create or update `.github/workflows/`.

## HALT-first preconditions

```sh
WORKER_TARGET='=supervisor-prompt-quality:'
tmux has-session -t "$WORKER_TARGET" \
  || { echo "HALT: expected worker session 'supervisor-prompt-quality'"; echo "REMEDY: ask the maintainer whether to start that worker session"; exit 1; }
pane_pid=$(tmux display-message -p -t "$WORKER_TARGET" '#{pane_pid}')
[ -n "$pane_pid" ] \
  || { echo "HALT: empty pane_pid for 'supervisor-prompt-quality'"; echo "REMEDY: re-check the exact worker target and stop if it still resolves empty"; exit 1; }
ps -o pid=,comm=,args= --ppid "$pane_pid" --pid "$pane_pid" -H

SUPERVISOR_TARGET='=supervisor-prompt-quality-supervisor:'
tmux has-session -t "$SUPERVISOR_TARGET" \
  || { echo "HALT: expected supervisor session 'supervisor-prompt-quality-supervisor'"; echo "REMEDY: switch to the correct supervisor session or ask the maintainer to bootstrap it"; exit 1; }
supervisor_pane_pid=$(tmux display-message -p -t "$SUPERVISOR_TARGET" '#{pane_pid}')
[ -n "$supervisor_pane_pid" ] \
  || { echo "HALT: empty pane_pid for 'supervisor-prompt-quality-supervisor'"; echo "REMEDY: re-check the exact supervisor target and stop if it still resolves empty"; exit 1; }
[ "$supervisor_pane_pid" != "$pane_pid" ] \
  || { echo "HALT: supervisor and worker resolve to the SAME pane"; echo "REMEDY: re-check both exact targets"; exit 1; }
ps -o pid=,comm=,args= --ppid "$supervisor_pane_pid" --pid "$supervisor_pane_pid" -H

test -d "/data/projects/livespec-overseer/plan/supervisor-prompt-quality" \
  || { echo "HALT: missing plan thread /data/projects/livespec-overseer/plan/supervisor-prompt-quality"; echo "REMEDY: create or choose the correct plan topic before supervising"; exit 1; }
pane_cwd=$(tmux display-message -p -t "$WORKER_TARGET" '#{pane_current_path}')
[ -n "$pane_cwd" ] \
  || { echo "HALT: empty pane_current_path for 'supervisor-prompt-quality'"; echo "REMEDY: re-check the exact worker target and stop if it still resolves empty"; exit 1; }
case "$(readlink -f -- "$pane_cwd")" in
  /data/projects/livespec-overseer|/data/projects/livespec-overseer/*) echo "PASS: $pane_cwd" ;;
  *) echo "HALT: pane cwd $pane_cwd is outside the target repo"; echo "REMEDY: move the worker into the target repo or start the correct worker session"; exit 1 ;;
esac
```

## Corrections

Thread-specific corrections live here. Regenerating this binder MUST preserve
this section byte-for-byte, from the `## Corrections` heading through the end of
the section. Preserve spelling, punctuation, code formatting, blank lines, and
ordering exactly.
