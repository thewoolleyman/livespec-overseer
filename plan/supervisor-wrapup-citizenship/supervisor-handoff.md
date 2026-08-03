# Supervisor Handoff - supervisor-wrapup-citizenship

## Shared Protocol

Read `.ai/supervisor-protocol.md` before driving. Validate this binder together
with that shared layer; this binder is intentionally thin and is not complete by
itself.

Regenerating this file MUST preserve two Corrections sections byte-for-byte:

- `.ai/supervisor-protocol.md` `## Corrections` for role-level corrections.
- This file's `## Corrections` for thread-specific corrections.

Preserve spelling, punctuation, code formatting, blank lines, and ordering
exactly; do not normalize markdown or code spans. A presence check is not enough
— a prior live regeneration silently reformatted a correction by turning a bare
identifier into a code span, and that would have passed a substring check.

Live thread status is NOT in this file. It lives in the ledger, in `handoff.md`,
and in `$supervisor_marker`. Read those first on a cold open — **all three**. On
2026-07-30 a supervisor on a sibling thread read two of the three, skipped
`handoff.md`, and the skipped file held the exact hazard that made it publish a
false accusation against the worker's own work. That is role-level correction
**C19**. On THIS thread the ordering matters in the other direction as well:
`handoff.md` is the record most likely to be BEHIND the ledger, because this
thread's spec phase completed inside a single night. Read it, then re-measure
every status claim it makes before acting on one.

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
stale tomorrow — a sibling thread's marker went 528 lines, then 697 within hours,
so no constant survives an append-only file. And truncation SEVERS RETRACTIONS
FROM CLAIMS: that marker carried an `OPEN OBLIGATIONS` block assigning
`holder: worker` inside the visible window while its retraction sat below the
cut, so a cold-open reader was handed a discharged obligation as live work.
Silently showing less is not the harm; manufacturing a false assignment is.
Corrections land at the END of an append-only file, which makes a head-only read
the worst possible cut.

**As of 2026-08-03T00:15Z there is no marker at that path and no `runtime_dir`
on disk.** The block above reports that as a NOTE and continues, which is
correct: absence at first boot is not a failure. Create the marker as soon as you
hold your first obligation — the shared layer's `## Obligation record` section
owns its schema. On this thread the first obligation is already live at
generation time and it has NO automatic wake: a factory run in another process,
watched from here.

## Bindings

Resolve and REPORT these before driving anything. Startup bindings only — no
live status, no next actions, and no date-gated behavior.

| Binding | Value |
|---|---|
| `repo_primary` | `/data/projects/livespec-overseer` |
| `thread_dir` | `plan/supervisor-wrapup-citizenship/` |
| `topic` | `supervisor-wrapup-citizenship` |
| `worker_session` | `supervisor-wrapup-citizenship` |
| `supervisor_session` | `supervisor-wrapup-citizenship-supervisor` |
| `WORKER_TARGET` | `'=supervisor-wrapup-citizenship:'` |
| `SUPERVISOR_TARGET` | `'=supervisor-wrapup-citizenship-supervisor:'` |
| `runtime_dir` | `<repo_primary>/tmp/overseer/supervisor-wrapup-citizenship/` |
| `supervisor_marker` | `<runtime_dir>/.supervisor-state` |
| `wait_channel` | `<runtime_dir>/worker-status.log` |
| `ledger_anchor` | `overseer-blccme` |

Placeholder classes declared by this binder:

- Concretely bound: `repo_primary`, `thread_dir`, `topic`, `worker_session`,
  `supervisor_session`, `WORKER_TARGET`, `SUPERVISOR_TARGET`, `ledger_anchor`.
- Composed bindings resolved to a fixed point: `runtime_dir`,
  `supervisor_marker`, `wait_channel`.
- Runtime slots intentionally left for later commands: `<condition-command>`,
  `<short-slug>`, `<branch>`.
- Illustrative placeholders appear only in prose that discusses a form, not in
  fenced commands.

The session names are the BARE topic and the topic plus `-supervisor`, per the
ratified `SPECIFICATION/spec.md` "Session-name derivation" rule: repo-qualified
names are for a genuine cross-repository topic collision, and this topic has
none.

`ledger_anchor` is the EPIC `overseer-blccme`. The implementation child
`overseer-6mbp2q` is where all remaining work lives, and it must be re-measured
BY ID — the Verification Discipline block below takes an id argument for exactly
that reason. Do not re-point this binding at the child to reach it: the anchor
gate requires this value to equal the anchor `handoff.md` declares.

## Generator provenance

This charter was produced from the generator prose whose digest is recorded
below. Run this before driving: a charter emitted from a stale plugin cache
carries defects the current generator no longer emits, and until this record
existed nothing about a charter said which generation produced it.

The DIGEST is the identity. The plugin, ref and version are companions for a
human reader — six releases shipped byte-identical prose, so a version would
report six generators where there is one, and the ref directory name is
sometimes a commit sha and sometimes a version string.

```sh
generator_plugin='livespec-overseer'
generator_ref='14d9fab90573'
generator_version='0.16.1'
generator_prose_md5='eaebe06065b3efa0053d6ea5932d52c0'
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

**Measured 2026-08-03T00:13Z: the cached generator prose at ref `14d9fab90573`
and this repo's own `.claude-plugin/prose/supervise-plan.md` are byte-identical
(`eaebe06065b3efa0053d6ea5932d52c0` both ways), so this charter PASSES its own
provenance check on this host.** A HALT here is therefore a real signal. Note the
digest is the SAME one a sibling charter recorded against ref `c530c70860d8` and
version `0.16.0` — that is the point of using the digest rather than the version
as the identity, not a copy error.

A MISSING CACHE ROOT AND A MISSING REF ARE DIFFERENT CONDITIONS. No cache root
at all means this is not a charter-generating host — a CI runner, or another
checkout — so provenance is UNVERIFIED and the check continues; HALTing there
would make this file unreadable anywhere but the machine that produced it. A
cache root that no longer holds the recorded ref means the generator has been
REPLACED, which is exactly how a refresh shows up, and that HALTs.

## Thread-specific Valves

Every claim below is a measurement with a timestamp. Re-measure before carrying
any of it forward — that is the shared layer's first rule and this section is not
exempt from it. On THIS thread that rule has unusual teeth: the thread's whole
subject is a contract about when a session may be spoken to, and the thread's own
records went stale inside a single night.

- **THE SPEC IS ALREADY RATIFIED. `handoff.md` §2 and §4 SAY IT IS NOT, AND THEY
  ARE WRONG.** Those sections were written 2026-08-02T08:53Z and name the
  proposed change, its review and its ratification as NOT done. Measured
  2026-08-03T00:09Z: the narrowing ratified as **v005**, merged by PR #522 at
  commit `cc90899`, with `SPECIFICATION/history/v005/` holding the revision and
  the accepted proposal. **Do not re-author the proposed change.** That is the
  single most expensive mistake available on this thread, because the stale
  instruction is phrased as an imperative next action and reads as current.
- **THE IMPLEMENTATION MERGED, AND THE LEDGER DOES NOT SAY SO.** Measured
  2026-08-03T01:00Z: `overseer-6mbp2q` produced PR **#536**, MERGED at
  00:39:03Z as `96eb0a2`, shipped by release **0.17.0** (`4b3a300`) — while its
  ledger row still reads `status=active, assignee=fabro` with an `updated_at`
  of 00:04:54Z. **`ACTIVE` is never evidence of a run and never evidence of an
  open one; `mise exec -- fabro ps` and the forge are.** Both children of this
  anchor read `active` today and one of them is long since merged.
- **THE OPEN ITEM IS `overseer-sfpurg`, AND ITS OWN PREMISE IS FALSE.** It asks
  to "supersede PR #536" and states that #536 "will be closed unmerged" and
  that the replacement branch must carry the entire implementation. It was
  filed at 00:44:51Z — six minutes AFTER #536 merged. `git branch -r --contains
  96eb0a2` returns `origin/master` and `origin/release`. **Treat it as a
  FORWARD FIX ON TOP OF MASTER**, and do not read a clean rebase as evidence
  that the implementation went missing. Recorded as a comment on the item
  rather than edited into it: the run was dispatched before this was noticed,
  so an edit cannot reach the interpolated goal, and rewriting an item to match
  reality destroys the evidence of how it came to be filed wrong.
- **ITS REQUIRED REPAIRS ARE REAL AND STILL ABSENT FROM MASTER**, verified
  against `origin/master:overseer/_supervisor_threshold.py`.
  `_fresh_threshold_observation` cancels on a changed `capture` and a changed
  `is_codex`, then re-derives `shell_only`, `blocked` and `ready` from the FRESH
  observation alone — it never compares `claude_status`, `codex_fallback` or
  `declared` against `request.obs`. Independently-safe is not unchanged. Its
  vocabulary guard is also skipped when the status is `None`, so an ABSENT
  Claude registry status is not distinguished from an affirmative idle one.
  **Do not let the stale framing above discredit these repairs** — the framing
  is wrong and the repairs are right.
- **A BLOCKING REVIEW WAS BYPASSED, AND THAT IS A GATE DEFECT, NOT THIS
  THREAD'S CODE DEFECT.** PR #536's `CHANGES_REQUESTED` review landed
  00:38:24Z; the merge happened 00:39:03Z, 39 seconds later; the release
  followed. Filed as `overseer-zfq` (P1) and routed to the orchestrator's
  publish step, which owns the merge path. **THE CARDINAL RULE IS UNTOUCHED BY
  ALL OF IT** — restart still requires a fresh session-written `ready`, and
  every busy kind still suppresses restart — so this is work to finish, not an
  incident to roll back. Say that plainly when reporting it; a P1 about a
  bypassed gate reads like an outage unless the blast radius is stated.
- **THIS THREAD'S OWN WORKER IS THE DEFECT'S VICTIM, AND THAT IS EVIDENCE, NOT
  IRONY.** Observed 2026-08-03T00:16Z: the worker pane sat at **9% context** with
  a live background terminal blocking on its own `drive.py` call. Shell-only busy
  evidence plus a below-threshold track is precisely the state v005 narrows, so
  under the pre-v005 daemon this session is UNINJECTABLE and no wrap-up can
  reach it. Cite it as case 6 if the safety case is ever questioned; the
  reasoning note's five cases were all other people's sessions.
- **THE ANCHOR TRAP WAS LIVE ON THIS THREAD AND THIS CHARTER'S PR IS WHAT
  DEFUSED IT.** `tests/test_plan_thread_records_agree.py` extracts a handoff's
  anchor with `_HANDOFF_DECLARES`, keyed on the words *ledger anchor*. This
  thread's `handoff.md` spelled it "The epic anchor is", so the extractor
  returned an EMPTY list — and a thread with a charter and an unreadable
  declaration is scored as an OFFENCE, not a skip. Generating this charter
  without amending `handoff.md` in the same commit would have turned master RED,
  with a message naming the CHARTER while the file needing the change was the
  HANDOFF. Measured live 2026-08-03T00:12Z by running the real extractor, with
  three declaring threads as the positive control. Filed as `overseer-jtc`.
- **THE SAME TRAP IS STILL ARMED ON THREE OTHER THREADS, AND THEY ARE NOT YOURS
  TO FIX.** Same measurement: `plan/release-automation-gap/`,
  `plan/shell-evidence-truth/` and `plan/supervisor-scratch-discipline/` all
  extract to an empty list. None has a charter yet, so master is green today;
  each reddens it the moment `supervise-plan` runs there. `overseer-jtc` owns the
  durable fix and records two non-exclusive remedies. Report the exposure, do not
  reach into another track's plan thread to clear it.
- **`overseer-vyjkzw` ACCEPTANCE CRITERION 3 IS INSIDE THE FACTORY RUN, NOT A
  SEPARATE EDIT.** It is REQUIRED BEHAVIOR item 7 of `overseer-6mbp2q`. Its
  letter ("the daemon continues suppressing injection/restart" on shell
  evidence) encodes the old contract; its intent — protect genuine background
  work — survives. **Verify it actually happened before closing anything**, and
  do not hand-edit it in parallel with a run that owns it.
- **`overseer-x6d` AND `overseer-3rk` ARE ADJACENT AND OUT OF SCOPE.**
  `overseer-x6d` is complementary report-only surfacing for GENERATING panes,
  which stay suppressed under v005. `overseer-3rk` and `plan/shell-evidence-truth/`
  own whether shell evidence is TRUTHFUL at all — the postscript in this thread's
  reasoning note records one such evidence trail as session-lifetime MCP
  launch-chain infrastructure rather than work. That finding STRENGTHENS this
  thread's case and is deliberately someone else's scope. Do not absorb it.
- **THE CARDINAL RULE IS THE ONE LINE THAT ENDS A TURN IN A QUESTION.** This
  thread changes when the daemon may SPEAK, never when it may act on a session's
  life. A restart remains authorized only by a fresh session-written `ready` for
  an open round; no force-kill, no auto-spawn, no inferred readiness, no daemon
  written declaration. If any diff on this thread touches restart authorization,
  that is not a judgment call to state an assumption about — it is the shared
  layer's one hard boundary, because it REMOVES an existing check.
- **`danger` STAYS REPORT-ONLY** and the one-paste-per-tick precedence stands.
  v005 adds exactly one eligible act beside the already-guarded pair-stall nudge;
  it does not weaken that nudge's stronger positively-empty-input guard, and the
  Codex path does not inherit pair-nudge eligibility from this change.
- **`just worktree-create` IS EFFECTIVELY BROKEN IN THIS REPO AND FAILS
  SILENTLY.** `dev-tooling/worktree-lib.sh:89` pipes `git worktree list
  --porcelain` into an `awk` that exits on first match, closing the pipe while
  git is still writing; git takes SIGPIPE, `pipefail` propagates 141, and
  `set -e` aborts before any output. **Re-measured for this charter
  2026-08-03T00:14Z at 86 worktrees: still exit 141.** The fix is one line in
  `livespec-dev-tooling`'s package source (`livespec-dev-tooling-zi4q`); never
  hand-edit the gitignored `dev-tooling/` copy. **THE RESCUE PATH, used to
  produce this charter:** `git worktree add <path> -b <branch>` then
  `just install-worktree-pack` inside it. That pack install writes a
  `worktree_discipline` key into the TRACKED `.livespec.jsonc`; it only makes the
  existing default explicit, so `git checkout --` it unless you mean to land it.
- **THIS BINDER IS ITSELF INSIDE THE CORPUS THE CHARTER GATE SCORES.** The gate's
  globs are `plan/**/supervisor-handoff.md` and `.ai/supervisor-protocol.md`, so
  every edit to this file is scored by eleven detectors in this repo's own CI at
  `just check`. This repo stands at ZERO defects and that zero is enforced, not
  merely maintained — a careless edit here fails the build.
- **A CHANGE TO ANY FILE UNDER `overseer/` REQUIRES A PAIRED CHANGE UNDER
  `tests/**`** (`commit_pairs_source_and_test`). The beside-tests in `overseer/`
  are themselves SOURCE to that check, so a beside-test alone does not satisfy
  it. `tests/conftest.py` puts `overseer/` on `sys.path`, so a module moves to
  `tests/` verbatim with no import changes. Product Python changes follow the
  red-green-replay commit ritual; never pass `--no-verify`.
- **`just check` HAS A FLAKY LEG RIGHT NOW, SO ONE RED RUN IS NOT A VERDICT.**
  `tests/prompts/test_watcher_wake_discriminates.py::test_c_a_footer_in_scrollback_does_not_wake_the_proposed_watcher`
  fails intermittently. Measured 2026-08-03T00:24Z on clean master as a CONTROL,
  before this branch existed: 1 failure in 3 isolated runs, same tree.
  Mechanism, replicated by hand: the leg's own command TEXT contains the footer
  under test, and when the pane does not settle within the rig's 5.0s deadline
  the settle fixture returns the LAST capture instead of a settled one — so the
  watcher reads the typed command and correctly reports PICKER for text that is
  not a footer. Filed as `overseer-63y` (P1). **Re-run before concluding
  anything from a red `just check`, and do not patch that file from this
  thread** — it is live work on the fleet-charter-remediation track.
- **`just check` PASSING LOCALLY IS NOT EVIDENCE ABOUT THE TREE YOU PUSHED.**
  The pre-push hook skips the aggregate on a green-token match keyed to the tree,
  so after MOVING or RENAMING a file the previous green describes a tree that no
  longer exists. Re-run `just check` after any move or rename, before pushing.
- **`date -u -r <file>` DOES NOT APPLY `-u` ON THIS HOST.** It runs uutils
  coreutils, not GNU: the command prints LOCAL time, and local is ahead of UTC,
  so a `Z` appended to it is a silent lie. Derive any mtime that will enter a
  published claim through `datetime.fromtimestamp(ts, timezone.utc)`. This is
  role-level correction **C19**.
- **`bd` NEEDS THE FLEET CREDENTIAL WRAPPER HERE** — a bare `bd` returns
  `Access denied` against this repo's tenant. The Verification Discipline block
  below DETECTS the wrapper rather than hard-coding a path, so an adopter without
  one can still re-measure.
- **CONFIRMING A PASTE BY GREPPING THE PANE FOR ITS TEXT CANNOT WORK**
  (role-level correction **C21**). Confirm by the render placeholder OR a
  non-empty prompt line, accept either shape, and **re-capture rather than
  re-sending**. On the Codex worker this thread drives there is a second step:
  a busy pane offers `tab to queue message`, and `Enter` alone leaves the text
  sitting in the composer unsent. Measured 2026-08-03T00:16Z — the notice landed,
  `Enter` did not submit it, and `Tab` queued it for delivery at turn end.
- **THE WORKER IS RUNNING UNDER A STANDING AUTONOMY INSTRUCTION — CHECK IT
  BEFORE YOU ESCALATE.** Observed 2026-08-03T00:13Z: the maintainer directed this
  track to proceed autonomously through all phases including final
  implementation, archive, and fleet-wide deployment; to avoid obvious questions;
  and to route genuine uncertainty to a Codex subsession first to test whether
  the answer is obvious enough to continue on. It does **not** lower the shared
  layer's escalation boundary — never REMOVE, WEAKEN or SKIP an existing check —
  which is a property of the change and is not delegable to a subsession.
- **NEVER KILL THE ACTING OVERSEER DAEMON.** It runs in tmux
  `livespec-overseer:1.1`, supervises every tracked session in the fleet, and is
  the shipped product rather than part of this thread. It is currently tracking
  this very track: measured 2026-08-03T00:13Z it auto-linked the worker at
  23:13:35Z and has been surfacing "supervision is running but has no durable
  prompt" ever since. That line is what this charter clears.
- The shared layer `.ai/supervisor-protocol.md` carried role-level corrections
  through **C22** when this charter was generated (2026-08-03T00:13Z). That is a
  count with a timestamp, not a standing fact: the section is append-only, so
  re-read it rather than trusting this number.
- Full narrative state, including corrections to this supervisor's own conduct
  that are not yet role-level, belongs in the supervisor marker at
  `tmp/overseer/supervisor-wrapup-citizenship/.supervisor-state`. Read it at
  boot; treat every status line in it as a claim with a timestamp and re-measure.

## Verification Discipline

Re-measure the filed work item from the ledger before carrying forward any status
or acceptance claim from this file, the plan thread, or a marker:

```sh
ledger_anchor='overseer-blccme'
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
if ! ledger_json="$(ledger_show "$ledger_anchor")"; then
  echo "HALT: cannot re-measure ledger item '$ledger_anchor'"
  if command -v with-livespec-env.sh >/dev/null 2>&1; then
    echo "REMEDY: the credential wrapper WAS used, so ledger access is not the suspect — check the anchor id is real and that this repo's tenant is reachable"
  else
    echo "REMEDY: no credential wrapper on PATH, so a BARE 'bd' ran — install/expose the fleet credential wrapper, or check the anchor id"
  fi
  exit 1
fi
# EXIT STATUS IS NOT EVIDENCE. A tool that exits 0 while printing nothing would
# let the stamp below certify a re-measurement that never happened.
[ -n "$ledger_json" ] \
  || { echo "HALT: ledger re-measure for '$ledger_anchor' exited 0 but returned NOTHING"; echo "REMEDY: do not record this as a measurement — an empty success is not a reading; confirm the anchor exists and that the ledger tool is actually reporting"; exit 1; }
printf '%s\n' "$ledger_json"
date -u '+MEASURED_AT: %Y-%m-%dT%H:%M:%SZ'
```

`ledger_show` takes the id as an argument on purpose: the anchor above is the
EPIC, and the work lives on its children — `overseer-6mbp2q`, merged, and
`overseer-sfpurg`, the open repair — each of which must be re-measured the same
way and BY ID. Re-measure the epic as well when
reporting — a parent's own status field lagged its children by two closes on a
sibling epic in this same tenant, so infer nothing about children from a parent's
field, and nothing about a parent from its children.

**A RUNNING FACTORY JOB IS RE-MEASURED WITH `fabro`, NOT WITH THE LEDGER.** The
ledger records the CLAIM; `mise exec -- fabro ps` records the RUN, and
`mise exec -- fabro events <run-id>` records what it is doing. A bare `fabro` is
not on PATH here — measured 2026-08-03T00:10Z, `with-livespec-env.sh -- fabro`
returns `No such file or directory` while `mise exec -- fabro` works. When those
two sources disagree, the process is the truth and the ledger row is the stale
claim.

When a command's own success is the verdict, capture that status before any pipe
used only to filter or display its output:

```sh
WORKER_TARGET='=supervisor-wrapup-citizenship:'
pane_pid=$(tmux display-message -p -t "$WORKER_TARGET" '#{pane_pid}')
tmux_rc=$?
[ "$tmux_rc" -eq 0 ] \
  || { echo "HALT: tmux pane lookup failed for 'supervisor-wrapup-citizenship'"; echo "REMEDY: re-check the exact target before filtering its output"; exit 1; }
printf '%s\n' "$pane_pid" | head -1
```

Inspect read-only before driving anything — a bounded scrollback sample plus the
whole visible worker pane:

```sh
WORKER_TARGET='=supervisor-wrapup-citizenship:'
tmux capture-pane -p -t "$WORKER_TARGET" -S -40
```

`-S -40` starts 40 lines back in history and then includes the entire visible
pane. It is NOT "the last 40 lines", and its history must never feed the picker
test or the pane diff — a picker that closed minutes ago is still in the buffer.

## HALT-first preconditions

Worker session `supervisor-wrapup-citizenship`; supervisor session
`supervisor-wrapup-citizenship-supervisor`; target repo
`/data/projects/livespec-overseer`. Verify both sessions AND the live agent
driver in each before doing anything else. Stop on the FIRST failure and act on
the labelled `REMEDY:`. Runtime identity comes from exact live process evidence,
NEVER from a session name — a leftover session named like an agent proves
nothing.

```sh
WORKER_TARGET='=supervisor-wrapup-citizenship:'
tmux has-session -t "$WORKER_TARGET" \
  || { echo "HALT: expected worker session 'supervisor-wrapup-citizenship'"; echo "REMEDY: ask the maintainer whether to start that worker session"; exit 1; }
pane_pid=$(tmux display-message -p -t "$WORKER_TARGET" '#{pane_pid}')
[ -n "$pane_pid" ] \
  || { echo "HALT: empty pane_pid for 'supervisor-wrapup-citizenship'"; echo "REMEDY: re-check the exact worker target and stop if it still resolves empty"; exit 1; }
ps -o pid=,comm=,args= --ppid "$pane_pid" --pid "$pane_pid" -H
# PASS only if a live `claude` or `codex` process appears in that tree.
# A lone shell (zsh/bash) with no agent child is a HALT.
# REMEDY: if no live agent appears, ask the maintainer whether to restart the worker.

SUPERVISOR_TARGET='=supervisor-wrapup-citizenship-supervisor:'
tmux has-session -t "$SUPERVISOR_TARGET" \
  || { echo "HALT: expected supervisor session 'supervisor-wrapup-citizenship-supervisor'"; echo "REMEDY: switch to the correct supervisor session or ask the maintainer to bootstrap it"; exit 1; }
supervisor_pane_pid=$(tmux display-message -p -t "$SUPERVISOR_TARGET" '#{pane_pid}')
[ -n "$supervisor_pane_pid" ] \
  || { echo "HALT: empty pane_pid for 'supervisor-wrapup-citizenship-supervisor'"; echo "REMEDY: re-check the exact supervisor target and stop if it still resolves empty"; exit 1; }
[ "$supervisor_pane_pid" != "$pane_pid" ] \
  || { echo "HALT: supervisor and worker resolve to the SAME pane"; echo "REMEDY: re-check both exact targets — a prefix match puts both names on one pane, and the worker's agent then reads as the supervisor's"; exit 1; }
ps -o pid=,comm=,args= --ppid "$supervisor_pane_pid" --pid "$supervisor_pane_pid" -H
# PASS only if a live `claude` or `codex` process appears in that tree.
# A lone shell (zsh/bash) with no agent child is a HALT.
# REMEDY: if no live agent appears, ask the maintainer to start the agent in that session.

test -d "/data/projects/livespec-overseer/plan/supervisor-wrapup-citizenship" \
  || { echo "HALT: missing plan thread /data/projects/livespec-overseer/plan/supervisor-wrapup-citizenship"; echo "REMEDY: create or choose the correct plan topic before supervising"; exit 1; }
pane_cwd=$(tmux display-message -p -t "$WORKER_TARGET" '#{pane_current_path}')
[ -n "$pane_cwd" ] \
  || { echo "HALT: empty pane_current_path for 'supervisor-wrapup-citizenship'"; echo "REMEDY: re-check the exact worker target and stop if it still resolves empty"; exit 1; }
case "$(readlink -f -- "$pane_cwd")" in
  /data/projects/livespec-overseer|/data/projects/livespec-overseer/*) echo "PASS: $pane_cwd" ;;
  *) echo "HALT: pane cwd $pane_cwd is outside the target repo"; echo "REMEDY: move the worker into the target repo or start the correct worker session"; exit 1 ;;
esac
```

Report which driver was found. **At generation the worker was `codex` and the
supervisor was `claude`** (measured 2026-08-03T00:07Z), and that asymmetry is
load-bearing rather than incidental: the paste-confirmation and queueing
behavior differs between the two runtimes, and this thread's own subject — the
Claude registry `status=shell` path versus the Codex descendant-shell fallback —
is exactly a place where treating the two as interchangeable produces a wrong
answer. The containment check resolves an ABSOLUTE repo path on purpose: a check
rooted at the bare `plan/` directory is cwd-relative and PASSES while pointed at
the wrong repository. The non-empty guard runs BEFORE the resolution because
`readlink -f ""` returns the CWD at exit 0 on this host's uutils coreutils, which
renders as a `PASS:` against the repo root — that is role-level correction **C2**.

## Corrections

Thread-specific corrections live here. Regenerating this binder MUST preserve
this section byte-for-byte, from the `## Corrections` heading through the end of
the section. Preserve spelling, punctuation, code formatting, blank lines, and
ordering exactly.

Role-level corrections C1 onward already apply and live in
`.ai/supervisor-protocol.md` — do not copy them down here. Record a `T<n>` entry
the first time THIS supervisor gets something wrong on THIS thread, and record it
about your own conduct; a section that logs only the worker's mistakes is a wrong
record.

- **T1 (2026-08-03) — I VERIFIED A GUARD IN ONE DIRECTION AND CALLED IT
  CORRECT.** On PR #548 I read the new `_adopted_claude_status_missing`
  predicate, asked whether it OVER-fires, satisfied myself that it did not, and
  published a supervisor verification comment saying it was "scoped to adopted
  panes" and correct. I never asked the opposite question. The maintainer's
  blocking review landed 29 seconds later and named exactly what I had not
  checked: the predicate required `request.session in
  request.sup.claude_names_by_session`, which covers a PARTIAL registry record
  (name present, status absent) but NOT an UNAVAILABLE registry. With both maps
  empty, `pane_is_managed_claude` stays fail-soft on identity via process/cwd
  proof, so the pane is still managed, the predicate returns false, and a stable
  empty Claude prompt could still be pasted into with `claude_status=None`. PR
  #548 was closed unmerged and replaced by #555, whose guard is unconditional —
  `not fresh.is_codex and fresh.claude_status is None` — with a control that
  empties BOTH maps.

  Three things to carry forward, none of which is "read more carefully":

  1. **A guard has two failure directions and they need separate questions.**
     Over-firing is visible — it breaks a passing test. Under-firing is silent,
     and on this thread silence is the whole subject: the contract being
     implemented is about an ABSENT signal being read as a safe one. I applied
     that thread's own lesson to the daemon's inputs and not to my own review.
  2. **My verification read the code but not the CONTROLS.** I confirmed the new
     test NAMES existed and matched the required repairs. I did not read what
     `test_missing_authoritative_claude_status_...` actually SET UP — it
     populated `claude_names_by_session`, encoding only the partial-record case.
     A test list is not test coverage, and I had already written a valve on this
     charter saying an empty result is not a finding without a positive control.
  3. **Publishing the verification made it worse, not better.** I posted it to
     counter the bypassed-review pattern in `overseer-zfq`, which was the right
     instinct aimed at the wrong artifact: a confident supervisor sign-off on an
     incomplete audit is a stronger false signal than no sign-off at all. If a
     verification is worth publishing, state which directions were checked and
     which were not, so its silence cannot be read as coverage.
