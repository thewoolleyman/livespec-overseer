# Supervisor Handoff - ready-certification-deadlock

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
**C19**. On this thread there is a fourth file that is not optional:
`plan/ready-certification-deadlock/deadlock-mechanism.md` carries the observed
timeline, the deadlock triangle, and the three candidate contract cuts, and
every valve below assumes you have read it.

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

**As of 2026-08-04T14:05Z there is no marker at that path and no `runtime_dir`
on disk.** The block above reports that as a NOTE and continues, which is
correct: absence at first boot is not a failure. Create the marker as soon as
you hold your first obligation — the shared layer's `## Obligation record`
section owns its schema.

## Bindings

Resolve and REPORT these before driving anything. Startup bindings only — no
live status, no next actions, and no date-gated behavior.

| Binding | Value |
|---|---|
| `repo_primary` | `/data/projects/livespec-overseer` |
| `thread_dir` | `plan/ready-certification-deadlock/` |
| `topic` | `ready-certification-deadlock` |
| `worker_session` | `ready-certification-deadlock` |
| `supervisor_session` | `ready-certification-deadlock-supervisor` |
| `WORKER_TARGET` | `'=ready-certification-deadlock:'` |
| `SUPERVISOR_TARGET` | `'=ready-certification-deadlock-supervisor:'` |
| `runtime_dir` | `<repo_primary>/tmp/overseer/ready-certification-deadlock/` |
| `supervisor_marker` | `<runtime_dir>/.supervisor-state` |
| `wait_channel` | `<runtime_dir>/worker-status.log` |
| `ledger_anchor` | `overseer-er6ikw` |

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
none. Measured 2026-08-04T13:59:57Z across all 13 repos in
`~/.livespec-overseer-repos.json`: `plan/ready-certification-deadlock/` exists in
`livespec-overseer` alone. That scan was run with a POSITIVE CONTROL — the same
loop over the same watch-set for a topic known to exist (`plan/foreman/`)
returned exactly one repo. The control was not decoration: the first attempt
parsed the watch-set with a plain JSON reader, which threw on the file's `//`
comments and printed NOTHING for every repo including this one, and without the
control that silence would have read as "no collision" for the right answer by
the wrong route.

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
generator_ref='ca08aa85bd1f'
generator_version='0.30.1'
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

**THIS CHARTER PASSES ITS OWN PROVENANCE CHECK ON THIS HOST — measured
2026-08-04T14:05Z.** The recorded ref is the build this session actually read the
generator prose from, and this repo's own `.claude-plugin/prose/supervise-plan.md`
digests to the same `eaebe06065b3efa0053d6ea5932d52c0`, so the repo is NOT ahead
of the released plugin and no known-benign HALT is outstanding against this file.
A HALT here is a real signal.

The ref was NOT taken from the path the skill binding named. That binding
resolved `cf67bb9c6947`, while the session's own startup hook had already updated
the plugin to `ca08aa85bd1f` — the documented "a running session keeps its
originally-resolved plugin path" trap. Both refs were digested and found
byte-identical, so nothing about this charter's content turns on the difference;
the ref recorded is the CURRENT installed one, because a provenance record that
names a superseded ref HALTs the moment that ref is evicted from the cache.

A MISSING CACHE ROOT AND A MISSING REF ARE DIFFERENT CONDITIONS. No cache root
at all means this is not a charter-generating host — a CI runner, or another
checkout — so provenance is UNVERIFIED and the check continues; HALTing there
would make this file unreadable anywhere but the machine that produced it. A
cache root that no longer holds the recorded ref means the generator has been
REPLACED, which is exactly how a refresh shows up, and that HALTs.

## Thread-specific Valves

**V1 — This thread is CONTRACT-BEARING, and the order of operations is the
work.** The deliverable is a ratified spec change first, and only then a daemon
change. The sequence is `/livespec:propose-change` against THIS repo's
`SPECIFICATION/`, then an independent adversarial review by a separately-spawned
Fable-model agent, then `/livespec:revise` with the maintainer. The daemon
implementation is filed AFTER ratification as a CHILD of the epic and executed
through the FACTORY path — the `drive` operation (`impl:<id>`) or the Dispatcher
drain — never the in-session `implement` operation. A worker that starts editing
`overseer/*.py` before ratification is doing the wrong work in the right repo;
that is the single most likely way this thread goes wrong, because the code fix
looks small and the contract question is the hard part.

**V2 — A code-derived answer is a PRECONDITION of the spec draft, not a
follow-up.** Before any proposed change is drafted, the worker must re-derive
from source which step actually cleared the round's injection stamp after the
void. The discrepancy is stated and unresolved: `overseer/_supervisor_restart.py`
documents round-close as happening "ONLY when the resume line actually SUBMITS",
`SPECIFICATION/spec.md` §"The supervision round" says the round closes on
restart, and yet the observed foreman stamp was cleared with NO restart ever
logged. A third path is clearing it, with the void handling as the lead
candidate. Do not accept a draft that picks among the three candidate cuts
without naming that path — candidate (c) ("voiding a declaration does not close
the round") is either the minimal fix or a no-op depending entirely on this
answer, and a draft that guesses cannot tell which it wrote.

**V3 — The regression boundary is four invariants, and "the fix preserves
them" is a claim to verify, not to accept.** The fix must not create: a restart
from a stale or replayed declaration (one declaration, one kill); a timer-based
or idleness-inferred restart (THE CARDINAL RULE — only a session-written `ready`
ever authorizes a restart); band re-spam (any re-armed band bounded to at most
once per cool-down); or a benefit-of-the-doubt certification (ambiguity still
fails closed). A session oscillating declare → work → declare must still never be
killed mid-work, which means whatever re-opens certification has to require a
verified settled idle prompt at restart time. Hand each of these to the worker as
INPUT TO VERIFY against its own draft; the deadlock exists precisely because four
individually-correct rules interacted, so a fix that reads as obviously safe is
the expected shape of a fix that breaks one of them.

**V4 — The epic anchor reports the CUT, not the work, and it currently has no
children.** Measured 2026-08-04T13:59:38Z: `overseer-er6ikw` is
`issue_type: epic`, `status: backlog`, with `dependent_count: 0` and
`dependency_count: 0`. Do not read that zero as "nothing blocks this thread" —
no child items have been filed yet, so the epic's own counters are silent about
work that does not exist rather than evidence about work that does. Once the
daemon-implementation child is filed under V1, re-measure it BY ID; this tenant
refuses task-to-epic dependency edges on sibling threads, so an epic's counters
are not a reliable index of its children. The two related ids are read-live, not
stored: `overseer-mgg` (sibling restart-leg confirm race) and `overseer-blccme`
(the closed narrowing epic that raises this deadlock's frequency by design).

**V5 — THIS REPO'S WORKTREE LIFECYCLE IS DOWN, and every publication on this
thread hits it.** Measured 2026-08-04T14:03Z: `just worktree-create`,
`just worktree-land` and `just worktree-reap` all fail with exit **141**
(SIGPIPE) before doing anything. The cause is `worktree_primary_path()` in
`dev-tooling/worktree-lib.sh`, which pipes `git worktree list --porcelain` into
an `awk` that exits on the first record; under the script's `set -o pipefail`,
`git` is killed by SIGPIPE while still writing and the whole recipe inherits 141.
The defective line, quoted here as evidence and deliberately not fenced:

    git worktree list --porcelain | awk '/^worktree /{print $2; exit}'

It is COUNT-DEPENDENT, not random: `git` only loses the race once the list is
long enough. Measured the same minute — `livespec` at 12 worktrees,
`livespec-dev-tooling` at 17 and `homelab` at 39 all succeed; this repo at **120**
fails **20 times out of 20**. So retrying is not a remedy, and neither is
`git worktree prune`: all 120 records point at live directories, so there is
nothing stale to clear. `dev-tooling/*` is gitignored and byte-verified against
the package source, so the fix belongs upstream in `livespec-dev-tooling` behind
a pin bump — do NOT hand-edit the installed copy, which would fail the
byte-verification gate it is checked by. Until that lands, create worktrees by
calling the pack's own function with only the crashing resolver replaced, which
runs the real provisioning and hydrate steps rather than a raw
`git worktree add` (a worktree without the pack can neither commit nor push):

**IT MUST RUN UNDER BASH.** This fleet's interactive shell is zsh, and running
the block there yields a WORSE outcome than the failure it works around: zsh does
not word-split an unquoted `$pack_files`, so
`worktree_provision_pack_from_primary` receives one four-name string, reports
`BLOCKED`, and leaves a PACK-LESS worktree behind. That worktree looks fine and
then refuses to commit or push much later, with an error naming the missing hook
rather than the shell. Run it as a bash script, not by pasting the body into your
shell:

```sh
cat > /tmp/overseer-mkwt.sh <<'SH'
#!/usr/bin/env bash
set -euo pipefail
cd /data/projects/livespec-overseer
# shellcheck source=/dev/null
. ./dev-tooling/worktree-lib.sh
# Ground truth, measured from `git worktree list --porcelain | head -1`.
worktree_primary_path() { printf '%s\n' '/data/projects/livespec-overseer'; }
worktree_create "$1" origin/master
SH
bash /tmp/overseer-mkwt.sh '<branch>'
```

Then CONFIRM the pack actually arrived, because its absence is silent:

```sh
ls /home/ubuntu/.worktrees/livespec-overseer/'<branch>'/dev-tooling/ \
  || { echo "HALT: pack-less worktree — the provision step was skipped"; echo "REMEDY: re-run the block under bash; a zsh run reports BLOCKED and leaves this state"; exit 1; }
```

This substitutes a correct constant for a crashing resolver; it weakens no check,
and `just check` plus every hook still runs unchanged on the resulting commit.

**V6 — A `{{...}}` token anywhere in a work item's text makes that item
UNDISPATCHABLE.** This matters on this thread specifically because the
daemon-implementation child filed under V1 will quote daemon source and very
likely a `just` recipe, and every recipe variable has exactly that shape.
`drive.py --action impl:<id>` interpolates item text into the fabro workflow's
templated `goal` attribute, so a literal `{{name}}` is parsed as a fabro template
variable, resolves to nothing, and the graph is rejected before any agent runs.
Do NOT repair this by editing the work item: that corrupts the item's own
evidence and hides a defect tracked as `bd-ib-vv9y`. It also leaves a PHANTOM
CLAIM — the item reads `status=active, assignee=fabro` with no run behind it.
`ACTIVE` is never evidence of a run; `fabro ps` is, and a `drive.py` exit of 0
means only that the request was accepted, not that work began.

**V7 — The worker on this thread can be captured by the very deadlock it is
fixing, and that is a supervision hazard rather than a curiosity.** The failure
under study is a session sitting in `NEEDS YOU` as `ready-uncertifiable` for
hours at low context. This thread's own worker is an ordinary supervised session
subject to the same machinery, so if it declares `ready`, resumes work inside the
120s grace, and later re-declares with its bands spent, it will deadlock exactly
as foreman did and this thread will stall on its own subject matter. Recognise
that state by its status string rather than inferring it from a quiet pane, and
do not attempt to clear it by instructing the worker to re-declare — the shared
layer's rule applies with full force here: a bare `ready` outside an open round
cannot restart anything and only manufactures report-only attention for a human
to reconcile.

## Verification Discipline

Re-measure the filed work item from the ledger before carrying forward any status
or acceptance claim from this file, the plan thread, or a marker:

```sh
ledger_anchor='overseer-er6ikw'
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

The spec-side half of this thread's state is NOT in the ledger at all, and it is
the half this thread is judged on. Measure it from the filesystem in the same
pass:

```sh
ls /data/projects/livespec-overseer/SPECIFICATION/proposed_changes/
ls /data/projects/livespec-overseer/SPECIFICATION/history/
date -u '+MEASURED_AT: %Y-%m-%dT%H:%M:%SZ'
```

`/livespec:revise` is DIRECTORY-scoped, not thread-scoped: it walks every
proposal sitting in `proposed_changes/`, including ones this thread did not
write. Re-measure that directory as a SET before quoting its SIZE in any picker
option, because the cost stated in an option is what the maintainer actually
consents to.

When a command's own success is the verdict, capture that status before any pipe
used only to filter or display its output:

```sh
WORKER_TARGET='=ready-certification-deadlock:'
pane_pid=$(tmux display-message -p -t "$WORKER_TARGET" '#{pane_pid}')
tmux_rc=$?
[ "$tmux_rc" -eq 0 ] \
  || { echo "HALT: tmux pane lookup failed for 'ready-certification-deadlock'"; echo "REMEDY: re-check the exact target before filtering its output"; exit 1; }
printf '%s\n' "$pane_pid" | head -1
```

Inspect read-only before driving anything — a bounded scrollback sample plus the
whole visible worker pane:

```sh
WORKER_TARGET='=ready-certification-deadlock:'
tmux capture-pane -p -t "$WORKER_TARGET" -S -40
```

`-S -40` starts 40 lines back in history and then includes the entire visible
pane. It is NOT "the last 40 lines", and its history must never feed the picker
test or the pane diff — a picker that closed minutes ago is still in the buffer.

## HALT-first preconditions

Worker session `ready-certification-deadlock`; supervisor session
`ready-certification-deadlock-supervisor`; target repo
`/data/projects/livespec-overseer`. Verify both sessions AND the live agent
driver in each before doing anything else. Stop on the FIRST failure and act on
the labelled `REMEDY:`. Runtime identity comes from exact live process evidence,
NEVER from a session name — a leftover session named like an agent proves
nothing, and which driver you find changes how you may drive it.

```sh
WORKER_TARGET='=ready-certification-deadlock:'
tmux has-session -t "$WORKER_TARGET" \
  || { echo "HALT: expected worker session 'ready-certification-deadlock'"; echo "REMEDY: ask the maintainer whether to start that worker session"; exit 1; }
pane_pid=$(tmux display-message -p -t "$WORKER_TARGET" '#{pane_pid}')
[ -n "$pane_pid" ] \
  || { echo "HALT: empty pane_pid for 'ready-certification-deadlock'"; echo "REMEDY: re-check the exact worker target and stop if it still resolves empty"; exit 1; }
ps -o pid=,comm=,args= --ppid "$pane_pid" --pid "$pane_pid" -H
# PASS only if a live `claude` or `codex` process appears in that tree.
# A lone shell (zsh/bash) with no agent child is a HALT.
# REMEDY: if no live agent appears, ask the maintainer whether to restart the worker.

SUPERVISOR_TARGET='=ready-certification-deadlock-supervisor:'
tmux has-session -t "$SUPERVISOR_TARGET" \
  || { echo "HALT: expected supervisor session 'ready-certification-deadlock-supervisor'"; echo "REMEDY: switch to the correct supervisor session or ask the maintainer to bootstrap it"; exit 1; }
supervisor_pane_pid=$(tmux display-message -p -t "$SUPERVISOR_TARGET" '#{pane_pid}')
[ -n "$supervisor_pane_pid" ] \
  || { echo "HALT: empty pane_pid for 'ready-certification-deadlock-supervisor'"; echo "REMEDY: re-check the exact supervisor target and stop if it still resolves empty"; exit 1; }
[ "$supervisor_pane_pid" != "$pane_pid" ] \
  || { echo "HALT: supervisor and worker resolve to the SAME pane"; echo "REMEDY: re-check both exact targets — a prefix match puts both names on one pane, and the worker's agent then reads as the supervisor's"; exit 1; }
ps -o pid=,comm=,args= --ppid "$supervisor_pane_pid" --pid "$supervisor_pane_pid" -H
# PASS only if a live `claude` or `codex` process appears in that tree.
# A lone shell (zsh/bash) with no agent child is a HALT.
# REMEDY: if no live agent appears, ask the maintainer to start the agent in that session.

test -d "/data/projects/livespec-overseer/plan/ready-certification-deadlock" \
  || { echo "HALT: missing plan thread /data/projects/livespec-overseer/plan/ready-certification-deadlock"; echo "REMEDY: create or choose the correct plan topic before supervising"; exit 1; }
pane_cwd=$(tmux display-message -p -t "$WORKER_TARGET" '#{pane_current_path}')
[ -n "$pane_cwd" ] \
  || { echo "HALT: empty pane_current_path for 'ready-certification-deadlock'"; echo "REMEDY: re-check the exact worker target and stop if it still resolves empty"; exit 1; }
case "$(readlink -f -- "$pane_cwd")" in
  /data/projects/livespec-overseer|/data/projects/livespec-overseer/*) echo "PASS: $pane_cwd" ;;
  *) echo "HALT: pane cwd $pane_cwd is outside the target repo"; echo "REMEDY: move the worker into the target repo or start the correct worker session"; exit 1 ;;
esac
```

Report which driver was found. The containment check resolves an ABSOLUTE repo
path on purpose: a check rooted at the bare `plan/` directory is cwd-relative
and PASSES while pointed at the wrong repository. The non-empty guard runs
BEFORE the resolution because `readlink -f ""` returns the CWD at exit 0 on this
host's uutils coreutils, which renders as a `PASS:` against the repo root — that
is role-level correction **C2**.

All five preconditions were measured PASS at 2026-08-04T13:58Z when this charter
was generated: worker pane pid 2637025 running claude, supervisor pane pid
2801061 running claude, distinct panes, plan thread present, worker cwd
`/data/projects/livespec-overseer`. Both sides of this pair are Claude, so the
Codex-specific driving caveats carried by sibling threads do not apply here.
That is a claim with a timestamp like every other — re-run the block rather than
trusting this sentence.

## Corrections

Thread-specific corrections live here. Regenerating this binder MUST preserve
this section byte-for-byte, from the `## Corrections` heading through the end of
the section. Preserve spelling, punctuation, code formatting, blank lines, and
ordering exactly.

Record corrections to THIS supervisor's own conduct here, not the worker's
mistakes; role-level corrections belong in `.ai/supervisor-protocol.md` so every
binder inherits them.

- **T1 (2026-08-04) — I published a runnable block I had never run in the form I
  published it, and it fails WORSE than the defect it works around.** V5's
  worktree workaround shipped as a bare ``sh`` block with no shell named. I had
  executed the same lines from a `#!/usr/bin/env bash` script, so it worked for
  me; pasted into this fleet's actual interactive shell, zsh, it does not.
  zsh does not word-split an unquoted `$pack_files`, so
  `worktree_provision_pack_from_primary` receives ONE four-name string, reports
  `BLOCKED`, and leaves a PACK-LESS worktree. That is worse than the exit-141
  failure V5 exists to route around: 141 is loud and immediate, while this is
  silent and surfaces much later at commit or push time with an error naming a
  missing hook rather than the shell. The worker found it by running the
  published form; I had verified the *effect* on my own machine and mistaken
  that for verifying the *artifact*.
  **THE GENERALISATION, and it is why this is worth its length: THE THING THAT
  SHIPS IS THE TEXT, NOT THE OUTCOME I GOT.** A command verified in a different
  shell, a different cwd, or a wrapper script is an untested command in the form
  a reader will use. This is the same defect class this charter polices in
  others — a check that cannot fail, a precondition without a command — arriving
  as a command that cannot succeed. Where a block's shell is load-bearing, name
  it in the block and add an assertion the reader can run, because a silent
  wrong result is the failure mode a fenced block is least able to report. V5
  now carries both.
