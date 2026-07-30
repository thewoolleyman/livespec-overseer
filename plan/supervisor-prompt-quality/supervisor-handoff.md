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

```sh
test -f ".ai/supervisor-protocol.md" \
  || { echo "HALT: missing shared supervisor protocol .ai/supervisor-protocol.md"; echo "REMEDY: regenerate the two-layer supervisor handoff before driving"; exit 1; }
printf '%s\n' "BOOT: read .ai/supervisor-protocol.md, this binder, and the supervisor marker if it exists"
[ -n "${supervisor_marker:-}" ] \
  || { echo "HALT: supervisor_marker is unset or empty"; echo "REMEDY: resolve it from the Bindings table below before running this block — an unset marker makes the read display NOTHING and still exit 0"; exit 1; }
if [ ! -f "$supervisor_marker" ]; then
  printf '%s\n' "NOTE: no supervisor marker at $supervisor_marker yet — nothing to read."
else
  marker_lines=$(wc -l < "$supervisor_marker")
  if [ "$marker_lines" -le 400 ]; then
    cat "$supervisor_marker"
  else
    sed -n '1,160p' "$supervisor_marker"
    printf '\n*** TRUNCATED: lines 161-%d of %d NOT SHOWN (%d hidden). A claim above may be RETRACTED in the hidden range. Read %s in full before acting on anything above. ***\n\n' \
      "$((marker_lines - 160))" "$marker_lines" "$((marker_lines - 320))" "$supervisor_marker"
    sed -n "$((marker_lines - 159)),${marker_lines}p" "$supervisor_marker"
  fi
fi
```

The read is WHOLE-FILE up to 400 lines and head-and-tail beyond, and the
truncation notice is MANDATORY whenever anything is hidden. A constant cap is
stale tomorrow — this thread's own marker went 528 lines, then 697, then past
1000 within hours. And truncation SEVERS RETRACTIONS FROM CLAIMS: that marker
carried an `OPEN OBLIGATIONS` block assigning `holder: worker` inside the
visible window while its retraction sat below the cut, so a cold-open reader was
handed a discharged obligation as live work. Silently showing less is not the
harm; manufacturing a false assignment is.

## Bindings

Resolve and REPORT these before driving anything. Startup bindings only - no
live status, no next actions, and no date-gated behavior.

| Binding | Value |
|---|---|
| `repo_primary` | `/data/projects/livespec-overseer` |
| `thread_dir` | `plan/supervisor-prompt-quality/` |
| `topic` | `supervisor-prompt-quality` |
| `worker_session` | `supervisor-prompt-quality` |
| `supervisor_session` | `supervisor-prompt-quality-supervisor` |
| `WORKER_TARGET` | `'=supervisor-prompt-quality:'` |
| `SUPERVISOR_TARGET` | `'=supervisor-prompt-quality-supervisor:'` |
| `runtime_dir` | `<repo_primary>/tmp/overseer/supervisor-prompt-quality/` |
| `supervisor_marker` | `<runtime_dir>/.supervisor-state` |
| `wait_channel` | `<runtime_dir>/worker-status.log` |
| `ledger_anchor` | `overseer-d4t` |

Placeholder classes declared by this binder:

- Concretely bound: `repo_primary`, `thread_dir`, `topic`, `worker_session`,
  `supervisor_session`, `WORKER_TARGET`, `SUPERVISOR_TARGET`, `ledger_anchor`.
- Composed bindings resolved to a fixed point: `runtime_dir`,
  `supervisor_marker`, `wait_channel`.
- Runtime slots intentionally left for later commands: `<condition-command>`,
  `<short-slug>`, `<branch>`.
- Illustrative placeholders appear only in prose that discusses a form, not in
  fenced commands.

## Thread-specific Valves

- This thread's subject is generated-prompt drift. Every generated-output claim
  must be checked against the union of `.ai/supervisor-protocol.md` and this
  binder, not against either layer alone.
- Byte-compare both Corrections layers across regeneration. Do not normalize
  markdown or code spans; changed bytes are drift.
- The current binder is a positive control for iteration stability: shared layer
  plus binder validates cleanly, while the binder alone deliberately does not.
- Factory branches never create or update `.github/workflows/`.
- The nine-slice generated-prompt-quality cut is DONE and its ledger items are
  closed; do not re-open or re-drive them. Re-measure before believing that.
- The live work is the FOLLOW-ON set, all P1 and all unanchored in `backlog`:
  `overseer-d4t` (a generator fix is inert until each adopter refreshes its
  pinned plugin cache — shipping 0.14.0 was necessary and NOT sufficient),
  `overseer-jdo` (the check aggregate is flaky under concurrency; now able to
  block every contributor because `check-prose-release-hygiene` is a required
  branch-protection context), `overseer-1sv` (`with-livespec-env.sh` exits 0 when
  the wrapped binary is MISSING, so "no runs" and "cannot look" are
  indistinguishable), `overseer-btt` (`just worktree-reap` can never reap a
  correctly-landed worktree because its test is ancestry and this fleet
  rebase-merges), `overseer-8jg` (an unresolvable cross-repo sibling reports a
  bare "not in the ready set" without naming it).
- Those five have NO plan-thread anchor and NO `intake:triaged` label, so no
  dispatch surface admits them and nothing else reports them. Deciding where they
  belong is a maintainer cut, not a supervisor call — surface it, do not
  self-assign it.
- Unfiled drifts, evidence-backed, still needing routing: the nested
  `.claude-plugin/.codex-plugin/plugin.json` stayed 0.13.3 while its sibling went
  0.14.0 (release-please `extra-files` omits it); `SPECIFICATION/spec.md:334-336`
  still says supervise-plan creates exactly ONE artifact when it now creates two;
  `overseer/marker-protocol.md:397` and `overseer/AGENTS.md:1428` both assert
  there is no `.ai/` directory, false since `57426df`.
- The FLEET-WIDE remediation half remains the maintainer's: 130 bare targets, 18
  files, 6 repos. Costed options are in the thread's
  `GAP-no-remediation-slice.md`. The local half is done and gated.
- Full narrative state, including corrections to this supervisor's own conduct
  that are not yet role-level, lives in the supervisor marker at
  `tmp/overseer/supervisor-prompt-quality/.supervisor-state`. Read it at boot;
  treat every status line in it as a claim with a timestamp and re-measure.

## Verification Discipline

Re-measure the filed work item from the ledger before carrying forward any status
or acceptance claim from this file, the plan thread, or a marker:

```sh
ledger_anchor='overseer-d4t'
# `bd` reaches a per-repo TENANT database and needs the fleet credential wrapper
# here; a bare `bd` returns "Access denied". DETECTED, not hard-coded, so an
# adopter without a wrapper can still re-measure.
ledger_show() {
  if command -v with-livespec-env.sh >/dev/null 2>&1; then
    with-livespec-env.sh -- bd show "$1" --json
  else
    bd show "$1" --json
  fi
}
if ! ledger_show "$ledger_anchor"; then
  echo "HALT: cannot re-measure ledger item '$ledger_anchor'"
  if command -v with-livespec-env.sh >/dev/null 2>&1; then
    echo "REMEDY: the credential wrapper WAS used, so ledger access is not the suspect — check the anchor id is real and that this repo's tenant is reachable"
  else
    echo "REMEDY: no credential wrapper on PATH, so a BARE 'bd' ran — install/expose the fleet credential wrapper, or check the anchor id"
  fi
  exit 1
fi
date -u '+MEASURED_AT: %Y-%m-%dT%H:%M:%SZ'
```

When a command's own success is the verdict, capture that status before any pipe
used only to filter or display its output:

```sh
WORKER_TARGET='=supervisor-prompt-quality:'
pane_pid=$(tmux display-message -p -t "$WORKER_TARGET" '#{pane_pid}')
tmux_rc=$?
[ "$tmux_rc" -eq 0 ] \
  || { echo "HALT: tmux pane lookup failed for 'supervisor-prompt-quality'"; echo "REMEDY: re-check the exact target before filtering its output"; exit 1; }
printf '%s\n' "$pane_pid" | head -1
```

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
