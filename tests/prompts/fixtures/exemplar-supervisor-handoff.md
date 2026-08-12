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
| `ledger_anchor` | `overseer-yho` |

Placeholder classes declared by this binder:

- Concretely bound: `repo_primary`, `thread_dir`, `topic`, `worker_session`,
  `supervisor_session`, `WORKER_TARGET`, `SUPERVISOR_TARGET`, `ledger_anchor`.
- Composed bindings resolved to a fixed point: `runtime_dir`,
  `supervisor_marker`, `wait_channel`.
- Runtime slots intentionally left for later commands: `<condition-command>`,
  `<short-slug>`, `<branch>`.
- Illustrative placeholders appear only in prose that discusses a form, not in
  fenced commands.

## Generator provenance

This charter was produced from the generator prose whose digest is recorded
below. Run this before driving: a charter emitted from a stale plugin cache
carries defects the current generator no longer emits, and until this record
existed nothing about a charter said which generation produced it.

The DIGEST is the identity. The plugin, ref and version are companions for a
human reader — six releases (0.12.2 through 0.13.3) shipped byte-identical
prose, so a version would report six generators where there is one, and the ref
directory name is sometimes a commit sha and sometimes a version string.

```sh
generator_plugin='livespec-overseer'
generator_ref='013d35d48cde'
generator_version='0.15.0'
generator_prose_md5='1078f373eee39f88a5dcef2a351924dc'
cache_root="$HOME/.claude/plugins/cache/$generator_plugin/$generator_plugin"
generator_prose="$cache_root/$generator_ref/prose/supervise-plan.md"
if [ ! -d "$cache_root" ]; then
  printf '%s\n' "UNVERIFIED: no plugin cache at $cache_root, so this is not a host that generates charters and provenance cannot be checked here. Recorded generator: $generator_prose_md5"
elif [ ! -f "$generator_prose" ]; then
  echo "HALT: the cache at $cache_root no longer holds ref $generator_ref, so the generator that emitted this charter has been replaced"
  echo "REMEDY: regenerate this charter with supervise-plan, or re-point generator_ref at the installed ref and re-stamp generator_prose_md5 from it"
  exit 1
else
  installed=$(md5sum "$generator_prose")
  digest_rc=$?
  [ "$digest_rc" -eq 0 ] \
    || { echo "HALT: cannot digest the installed generator prose at $generator_prose"; echo "REMEDY: fix read access before trusting anything this charter says about its own currency"; exit 1; }
  installed_md5=${installed%% *}
  [ "$installed_md5" = "$generator_prose_md5" ] \
    || { echo "HALT: this charter was emitted by generator $generator_prose_md5 but the installed generator is $installed_md5"; echo "REMEDY: regenerate this charter before driving, or re-stamp generator_prose_md5 deliberately after reading what changed between the two"; exit 1; }
  printf '%s\n' "PASS: charter provenance matches the installed generator ($installed_md5)"
fi
```

THIS CHARTER IS AHEAD OF THE RELEASED PLUGIN, ON PURPOSE. It records the digest
of the generator prose IN THIS REPO, which is what it was written against. Between
a prose change and the release that ships it, that digest differs from the one the
cache holds, so the check HALTs here with both values named — the charter is ahead
of the deployed generator, which is true and is exactly the drift this record
exists to surface. It goes quiet once the release lands and the cache refreshes.
An adopter, whose charter is generated FROM a released cache ref, sees PASS.

A MISSING CACHE ROOT AND A MISSING REF ARE DIFFERENT CONDITIONS. No cache root
at all means this is not a charter-generating host — a CI runner, or another
checkout — so provenance is UNVERIFIED and the check continues; HALTing there
would make this file unreadable anywhere but the machine that produced it. A
cache root that no longer holds the recorded ref means the generator has been
REPLACED, which is exactly how a refresh shows up, and that HALTs.

## Thread-specific Valves

- This thread's subject is generated-prompt drift. Every generated-output claim
  must be checked against the union of `.ai/supervisor-protocol.md` and this
  binder, not against either layer alone.
- Byte-compare both Corrections layers across regeneration. Do not normalize
  markdown or code spans; changed bytes are drift.
- The current binder is a positive control for iteration stability: shared layer
  plus binder validates cleanly, while the binder alone deliberately does not.
- Factory branches never create or update `.github/workflows/`.
- **THE BINDER WILL HALT ON ITS OWN PROVENANCE PRECONDITION HERE. THAT IS
  CORRECT.** Measured 2026-08-02, true exit status 1 (read WITHOUT a pipe; through
  one it reads 0 — C14/C19). This repo's charter records the digest of the prose
  in THIS REPO, while the plugin cache holds the last RELEASED prose, so between a
  prose change and its release the two differ and the check fires. That IS the
  drift the record exists to surface; an adopter on a released ref sees PASS. It
  self-resolves when release PR **#360 (0.16.0)** ships, which is the maintainer's.
  **Do NOT re-stamp `generator_prose_md5` to silence it** — that forges currency
  the charter does not have.
- **THE NINE-SLICE CUT AND ITS PHASE-2 FOLLOW-ON ARE BOTH ESSENTIALLY DONE.
  Re-measure before believing this.** Epic `overseer-byvxlp` closed; phase-2 epic
  `overseer-yho` is 3 of 4 closed:
  - `overseer-yho.1` CLOSED — detector `(k) local-time-labelled-utc`. The charter
    gate now carries **eleven** classes, a..k.
  - `overseer-yho.2` CLOSED — a generated charter now RECORDS and CHECKS its
    generator by **prose digest** (not version: six releases shipped byte-identical
    prose, and a prose fix without a release bump reports an unchanged version for
    changed prose). The comparison is a HALT-first precondition on the ADOPTER'S
    host, never equality in CI, which would redden every charter on every release.
  - `overseer-gjb` CLOSED — the module docs no longer deny a directory that exists,
    and the claim is now gated so the premise cannot rot silently again.
  - `overseer-d4t` **CLOSED** — this thread's top open item all day. All three of
    its asks delivered and its own acceptance clause discharged: RED against a
    real stale-cache generation, not against repo prose.
- **THE ONE REMAINING SLICE IS `overseer-yho.3`, AND ITS SCOPE IS ALREADY
  DECIDED.** The maintainer chose **PHASED — `livespec-orchestrator-beads-fabro`
  FIRST**, because that repo holds **56 of the 117** fleet defects with five of
  its six charters dirty, so one scoped slice clears about half the exposure. Two
  constraints ride with it: it touches ANOTHER TRACK'S REPO, so tell that track
  before changing anything (a charter whose sessions are both live is ARMED — the
  defect is dormant and fires when a worker exits); and it leaves **61 defects
  across 4 repos** unaddressed, which MUST be stated on completion rather than
  read as "the fleet is clean". Carry all ELEVEN detectors, not the seven that
  existed when `GAP-no-remediation-slice.md` was costed. That file's 130/18/6
  figure is SUPERSEDED by the 117/12/5 re-measure recorded beside it.
- **THE DAEMON-LIVENESS PAIR WAS SPLIT OUT AND IS NOT YOURS.** Epic
  `overseer-x29`, plan thread `plan/daemon-liveness-truth/`: a LIVE track
  reporting session-gone (`overseer-j1r`) and a TORN-DOWN one reporting hung
  mid-wrap-up (`overseer-mkx`). Same defect mirrored, but about the daemon's
  runtime liveness model rather than what the generator emits. **The worker was
  reassigned to that track on 2026-08-02 by maintainer ruling**, so it is live on
  a DIFFERENT thread — do not assume it is available here.
- Items routed OUT of this tenant by owning component, do NOT re-file them:
  `overseer-btt` → `livespec-dev-tooling-xezh`; `overseer-1sv` →
  `livespec-dev-tooling-1syc` (its P1 premise was REFUTED — the wrapper propagates
  127; the real defect is that it does not propagate the caller's PATH);
  `overseer-8jg` → `bd-ib-0kif`; the `just worktree-create` SIGPIPE →
  `livespec-dev-tooling-zi4q`. Still open HERE and unrelated to this thread:
  `overseer-jdo` (flaky aggregate; 24 clean runs recorded, acceptance revised to
  20 at `-n auto` since local runs 4 workers and CI runs 18) and `overseer-n04`
  (every `bd` write fails its auto-backup).
- **BEFORE FILING ANYTHING FROM AN INHERITED "UNFILED" LIST, SEARCH THE LEDGER
  FIRST.** All three drifts this binder used to list are discharged, and one of
  them — the nested Codex manifest — was filed by ANOTHER TRACK fourteen minutes
  before I duplicated it. "This is unfiled" is a claim with a timestamp exactly
  like an item's status. That is charter correction **C18**.
- One open PR of this track's remains: **#440**, needing a rebase against master's
  `handoff.md`. Six siblings (#441, #445, #446, #452, #456, #465) were merged
  2026-08-02 on green checks; they were opened while unsupervised and were NOT
  reviewed line by line — that is stated rather than implied.
- Full narrative state, including corrections to this supervisor's own conduct
  that are not yet role-level, lives in the supervisor marker at
  `tmp/overseer/supervisor-prompt-quality/.supervisor-state`. Read it at boot;
  treat every status line in it as a claim with a timestamp and re-measure.

## Verification Discipline

Re-measure the filed work item from the ledger before carrying forward any status
or acceptance claim from this file, the plan thread, or a marker:

```sh
ledger_anchor='overseer-yho'
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

- **T1 — `ledger_anchor` pointed at a CLOSED BUG, inside the block whose job is to
  stop exactly that.** Measured 2026-07-31: both spellings of this binder's anchor
  — the Bindings table and the executable `ledger_anchor='…'` in Verification
  Discipline — read `overseer-d4t`, a **bug** closed 2026-07-30T19:34:35Z and an id
  this thread's `handoff.md` declares nowhere. The handoff declares the epics
  `overseer-byvxlp` and, for phase 2, `overseer-yho`. So a supervisor obeying the
  instruction directly above it — "re-measure the filed work item from the ledger
  before carrying forward any status or acceptance claim" — would have re-measured
  a closed bug belonging to no phase of this thread and reported on it with
  confidence. Corrected to `overseer-yho` in both places, matching the handoff.
  **This is `overseer-bak` instantiated in the repo's own hardened exemplar**, and
  nothing could see it: the eleven-class charter gate reads shell and tmux forms,
  the two fleet plan-thread checks read `handoff.md` only, and **no check anywhere
  in the fleet reads this file at all** (measured, against a passing control).
  `tests/test_plan_thread_records_agree.py` now compares the two records
  statically. **When the phase changes, this binding changes with it** — an anchor
  is a claim with a timestamp, like every other status in this file.
