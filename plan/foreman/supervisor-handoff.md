# Supervisor Handoff - foreman

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
**C19**.

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

**As of 2026-08-02T23:42Z there is no marker at that path and no `runtime_dir`
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
| `thread_dir` | `plan/foreman/` |
| `topic` | `foreman` |
| `worker_session` | `foreman` |
| `supervisor_session` | `foreman-supervisor` |
| `WORKER_TARGET` | `'=foreman:'` |
| `SUPERVISOR_TARGET` | `'=foreman-supervisor:'` |
| `runtime_dir` | `<repo_primary>/tmp/overseer/foreman/` |
| `supervisor_marker` | `<runtime_dir>/.supervisor-state` |
| `wait_channel` | `<runtime_dir>/worker-status.log` |
| `ledger_anchor` | `overseer-z5fo4y` |

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
none. Measured 2026-08-02T23:42Z across all twelve repos in
`~/.livespec-overseer-repos.json`: `plan/foreman/` exists in
`livespec-overseer` alone.

`runtime_dir` sits under the repo's gitignore-gated `tmp/` scratch, which is
also where this thread's own future feature writes its state
(`<repo>/tmp/overseer/foreman/`, review finding O18). Those are the same
directory by construction — the supervisor's marker and the eventual foreman
runtime share a home, so do not "clean up" one and take the other with it.

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
generator_ref='c530c70860d8'
generator_version='0.16.0'
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
2026-08-02T23:42Z.** The `0.16.0` release has landed, so the cached generator
prose at ref `c530c70860d8` is byte-identical to
`.claude-plugin/prose/supervise-plan.md` in this repo
(`eaebe06065b3efa0053d6ea5932d52c0` both ways). The hardened exemplar carries a
valve saying its provenance check WILL HALT because the repo was ahead of the
released plugin; **that condition has cleared and does not cover this file**, so
a HALT here is a real signal rather than the known-benign one.

A MISSING CACHE ROOT AND A MISSING REF ARE DIFFERENT CONDITIONS. No cache root
at all means this is not a charter-generating host — a CI runner, or another
checkout — so provenance is UNVERIFIED and the check continues; HALTing there
would make this file unreadable anywhere but the machine that produced it. A
cache root that no longer holds the recorded ref means the generator has been
REPLACED, which is exactly how a refresh shows up, and that HALTs.

## Thread-specific Valves

Every claim below is a measurement with a timestamp. Re-measure before carrying
any of it forward; the Verification Discipline block is the command.

- **THE WORKER ON THIS THREAD RUNS CODEX, NOT CLAUDE.** Measured
  2026-08-02T23:42Z: worker pane pid 270839 holds
  `bun /home/ubuntu/.bun/bin/codex --dangerously-bypass-approvals-and-sandbox`;
  the supervisor pane holds `claude`. Both drivers are legitimate and the
  preconditions accept either, but they are NOT interchangeable when you drive:
  Codex has no `/livespec:*` slash-command surface, so any instruction that
  assumes a Claude skill invocation will sit in that pane unexecuted. Report
  which driver was found every time you re-run the preconditions — it can change
  under you when a session is restarted.

- **THE READ-FIRST CHAIN IS THREE FILES AND THEY ARE ORDERED.** `handoff.md`
  names them: `research/seed-prompt.md` (the maintainer's verbatim requirements
  including addendum item 8), then `research/brainstorm.md` (§3 records four
  maintainer decisions that are FIXED inputs; §4 is the CURRENT v2 phasing and
  its correction banners are live corrections, not history), then
  `research/review-findings.md` (33 external adversarial findings; the per-phase
  dispositions are BINDING and are not to be re-litigated without new evidence).
  Cite finding ids when you reason about design here — the thread's whole
  vocabulary is those ids.

- **STATE AS OF 2026-08-03T20:38Z — THIS IS THE ONLY STATUS BLOCK; EVERYTHING
  ELSE IN THIS FILE IS STANDING GUIDANCE.** Re-measure before acting; the
  Verification Discipline block below is the command.

  **v006 IS RATIFIED AND MERGED** (PR #575). All nine pending proposals were
  processed in one pass: six `modify`, three `accept`, none rejected.
  `SPECIFICATION/proposed_changes/` is EMPTY. Do not re-file any of them; a
  same-topic re-run mints a `<topic>-2.md` collision.

  **PHASE A IS COMPLETE — all five slices closed:**

  | Item | State |
  |---|---|
  | `overseer-z5fo4y.1` snapshot export | **closed** (dedupe landed, PR #601) |
  | `overseer-z5fo4y.2` `list --json` | **closed**, PR #607 (`706f23b`) |
  | `overseer-z5fo4y.3` foreman-gather | **closed**, PR #621 (`f699678`) |
  | `overseer-z5fo4y.4` heartbeat surfacing | **closed**, PR #619 (`a01d3e2`) |
  | `overseer-z5fo4y.5` `-foreman` suffix | **closed**, merged `335a578` |
  | `overseer-n7xx67`, `overseer-jgqw7d`, `overseer-3hq`, `overseer-63y`, `overseer-41p` | **closed** |

  **PHASE B IS ANOTHER TRACK'S WORK, AND IT IS ALREADY UNDER WAY.** Do not file
  slices for it, do not dispatch it, do not re-rank it. Its items, none of them
  ours:

  | Item | State |
  |---|---|
  | `overseer-by6hrx` foreman runtime wrapper | **closed**, PR #625 |
  | `overseer-4opppx` foreman-act session-lifecycle | **closed**, PR #630 |
  | `overseer-wykyth` typed filing + journal triage | `pending-approval` |
  | `overseer-vts4lo` work-item bounded one-shots | `pending-approval` |
  | `overseer-qp3vpb` the foreman skill / v1 binding | `pending-approval` |

  **THE EPIC STAYS OPEN. v1 = PHASES A+B** — a maintainer decision of
  2026-08-02 recorded in `overseer-z5fo4y`'s own description. Phase A is only
  the OBSERVE half. Archiving on Phase A's completion would ship half of v1,
  and the previous version of this block said to do exactly that ("REMAINING ON
  THIS THREAD: … then archive the thread, then fleet rollout"). That sentence
  was wrong, it was inherited into `handoff.md` without being checked against
  the epic, and correcting it cost a PR (#623). **A SCOPE CLAIM IS A CLAIM WITH
  A TIMESTAMP, exactly like an item status.**

  REMAINING: Phase B drains under its own track; only then close/archive the
  epic and thread and verify fleet deployment. Phases C–E are separate future
  scope.

- **BEFORE YOU DIAGNOSE ANY DISPATCH FAILURE, READ `overseer-6pn`.** A
  dispatcher that reports `failed` while its PR MERGED is that bug, not a real
  failure. FIVE occurrences on this thread alone (`jgqw7d`, `63y` twice, `3hq`,
  `n7xx67`). **Check `gh pr list --state merged` BEFORE re-dispatching**, then
  reconcile the phantom claim (`--status acceptance`, then the `accept` valve)
  instead of re-running the work. The root cause is the post-merge janitor
  pulling the PRIMARY checkout: one dirty file there aborts its `git pull` and
  fails every dispatch fleet-wide. That condition was cleared 2026-08-03; if it
  returns, `git status` the primary before believing any dispatch failure.

- **NEVER RE-RUN `drive.py` IN THE FOREGROUND TO CAPTURE STDERR.** A foreground
  re-run IS a dispatch. Killing it on a timeout leaves a phantom claim, and
  treating that claim as spurious leads to dispatching a third time. That is
  exactly how TWO implementations of slice `.1` both merged (`overseer-41p`,
  since resolved). To capture diagnostics, dispatch DETACHED with `--json`:
  `setsid nohup ./tmp/overseer/foreman/dispatch.sh impl:<id> --json > log 2>&1 &`.
  That wrapper also re-resolves the plugin build at call time, which matters
  because the release train invalidated this session's build FOUR times in one
  day.

- **A CHECK'S NAME IS NOT ITS CAUSE.** `check-commit-pairs-source-and-test`
  failed on PR #580 and the supervisor briefed a commit reshape. The job had
  died on a **ruff download timeout before the pairing gate ever ran**. The
  worker read the failed job's LOG, requested a rerun on the UNCHANGED branch,
  and it went green — no defect existed. Read the job output, not the job name.

- **`-foreman` AS A RESERVED SUFFIX HAS A COLLISION TRAP `.5` MUST NOT WALK
  INTO.** The shipped mechanism is `signals.topic_reserved_for_supervisor`,
  which is `topic.lower().endswith("-supervisor")` (`overseer/signals.py:341`,
  `:344`). The bare topic `foreman` does NOT end in `-foreman`, so this thread's
  own worker session is safe under a HYPHENATED suffix test — but an
  implementation that tests `endswith("foreman")` without the hyphen would
  orphan the very worker supervising this plan. Separately, `tmux_id`'s
  collision branch returns the repo-qualified `livespec-overseer-foreman`, which
  DOES end in `-foreman` and which `.5` refuses by design; that is latent today
  (no collision exists) and becomes live the moment a second watched repo grows
  a `plan/foreman/`. Both belong in `.5`'s beside-tests.

- **THE STANDING ADOPTION HAZARD IN `handoff.md` IS NARROWER THAN IT READS.**
  It says a session registry-named `foreman` WILL be adopted as this thread's
  worker and "do not run one". Adoption keys on EXACT equality —
  `overseer/_supervisor_discovery.py:180` sets `topic = name` and requires
  membership in the active-topic set — so it is about a foreman PROTOTYPE
  session, not about this thread's legitimate worker, which is named `foreman`
  precisely so the daemon manages it. A prototype must be named
  `<repo-slug>-foreman` and is only safe once `.5` lands. This supervisor
  session, `foreman-supervisor`, is not adoptable as a worker for any topic
  (no `plan/foreman-supervisor/` exists).

- **BOTH DISPATCH TRAPS IN THE REPO-ROOT `.claude/CLAUDE.md` APPLY VERBATIM.**
  A literal double-brace template token anywhere in a work item's text makes it
  undispatchable and leaves a PHANTOM CLAIM (`status=active, assignee=fabro`
  while `fabro ps` shows nothing) — release it by hand, do NOT edit the item to
  silence it. And a "dispatcher plugin build is stale" error names a remedy that
  appears to do nothing, because a running session keeps its originally-resolved
  plugin path; invoke the new build by ABSOLUTE PATH. All seven items above were
  scanned for the token on 2026-08-02T23:42Z and are clean.

- **`just worktree-create` FAILS AT SCALE IN THIS REPO.** Measured
  2026-08-02T23:42Z: 81 worktrees, past the 77 at which 65 consecutive failures
  were recorded (fix tracked as `livespec-dev-tooling-zi4q`). The proven rescue,
  used to create this charter's own branch: `git worktree add <path> -b <branch>
  <base>`, then `just install-worktree-pack` inside it, then discard the
  `worktree_discipline` key it writes into the tracked `.livespec.jsonc` unless
  you mean to land it. A worktree without that pack can neither commit a `.py`
  change nor push at all.

- **IMPLEMENTATION IS FACTORY-SIDE.** Every ledger-backed slice here is
  dispatch-eligible; the dispatch route IS the implementation path. Do not
  hand-code a slice inline in this pane. This thread FILES ripe work and routes
  spec matter to the spec lifecycle.

- **THE DAEMON IS OUT OF BOUNDS FOR THIS THREAD'S CHANGES** (maintainer
  decision 3): additive snapshot plus heartbeat surfacing only. Its `evaluate()`
  cascade, the cardinal rule, and its attention semantics do not change. Phase A
  ships NO LLM loop (findings O16/C5).

- Full narrative state, including corrections to this supervisor's own conduct
  that are not yet role-level, lives in the supervisor marker at
  `tmp/overseer/foreman/.supervisor-state`. Read it at boot; treat every status
  line in it as a claim with a timestamp and re-measure.

## Verification Discipline

Re-measure the filed work item from the ledger before carrying forward any status
or acceptance claim from this file, the plan thread, or a marker:

```sh
ledger_anchor='overseer-z5fo4y'
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

`overseer-z5fo4y` is an EPIC, so that reading reports the cut and not the work.
Its children are the dotted ids `overseer-z5fo4y.1` through `.5` — the epic edge
is PROSE-ONLY because this tenant refuses task-to-epic dep edges, so the epic's
own `dependent_count` is `0` and proves nothing about its children. Re-measure
each child by id, plus the two items that hang off this thread without dotted
ids: `overseer-jgqw7d` and `overseer-n7xx67`.

The spec-side half of this thread's state is NOT in the ledger at all. Measure it
from the filesystem in the same pass:

```sh
ls /data/projects/livespec-overseer/SPECIFICATION/proposed_changes/
ls /data/projects/livespec-overseer/SPECIFICATION/history/
date -u '+MEASURED_AT: %Y-%m-%dT%H:%M:%SZ'
```

When a command's own success is the verdict, capture that status before any pipe
used only to filter or display its output:

```sh
WORKER_TARGET='=foreman:'
pane_pid=$(tmux display-message -p -t "$WORKER_TARGET" '#{pane_pid}')
tmux_rc=$?
[ "$tmux_rc" -eq 0 ] \
  || { echo "HALT: tmux pane lookup failed for 'foreman'"; echo "REMEDY: re-check the exact target before filtering its output"; exit 1; }
printf '%s\n' "$pane_pid" | head -1
```

Inspect read-only before driving anything — a bounded scrollback sample plus the
whole visible worker pane:

```sh
WORKER_TARGET='=foreman:'
tmux capture-pane -p -t "$WORKER_TARGET" -S -40
```

`-S -40` starts 40 lines back in history and then includes the entire visible
pane. It is NOT "the last 40 lines", and its history must never feed the picker
test or the pane diff — a picker that closed minutes ago is still in the buffer.

## HALT-first preconditions

Worker session `foreman`; supervisor session `foreman-supervisor`; target repo
`/data/projects/livespec-overseer`. Verify both sessions AND the live agent
driver in each before doing anything else. Stop on the FIRST failure and act on
the labelled `REMEDY:`. Runtime identity comes from exact live process evidence,
NEVER from a session name — a leftover session named like an agent proves
nothing, and on this thread the worker's driver is Codex rather than Claude, so
the driver you find changes how you may drive it.

```sh
WORKER_TARGET='=foreman:'
tmux has-session -t "$WORKER_TARGET" \
  || { echo "HALT: expected worker session 'foreman'"; echo "REMEDY: ask the maintainer whether to start that worker session"; exit 1; }
pane_pid=$(tmux display-message -p -t "$WORKER_TARGET" '#{pane_pid}')
[ -n "$pane_pid" ] \
  || { echo "HALT: empty pane_pid for 'foreman'"; echo "REMEDY: re-check the exact worker target and stop if it still resolves empty"; exit 1; }
ps -o pid=,comm=,args= --ppid "$pane_pid" --pid "$pane_pid" -H
# PASS only if a live `claude` or `codex` process appears in that tree.
# A lone shell (zsh/bash) with no agent child is a HALT.
# REMEDY: if no live agent appears, ask the maintainer whether to restart the worker.

SUPERVISOR_TARGET='=foreman-supervisor:'
tmux has-session -t "$SUPERVISOR_TARGET" \
  || { echo "HALT: expected supervisor session 'foreman-supervisor'"; echo "REMEDY: switch to the correct supervisor session or ask the maintainer to bootstrap it"; exit 1; }
supervisor_pane_pid=$(tmux display-message -p -t "$SUPERVISOR_TARGET" '#{pane_pid}')
[ -n "$supervisor_pane_pid" ] \
  || { echo "HALT: empty pane_pid for 'foreman-supervisor'"; echo "REMEDY: re-check the exact supervisor target and stop if it still resolves empty"; exit 1; }
[ "$supervisor_pane_pid" != "$pane_pid" ] \
  || { echo "HALT: supervisor and worker resolve to the SAME pane"; echo "REMEDY: re-check both exact targets — a prefix match puts both names on one pane, and the worker's agent then reads as the supervisor's"; exit 1; }
ps -o pid=,comm=,args= --ppid "$supervisor_pane_pid" --pid "$supervisor_pane_pid" -H
# PASS only if a live `claude` or `codex` process appears in that tree.
# A lone shell (zsh/bash) with no agent child is a HALT.
# REMEDY: if no live agent appears, ask the maintainer to start the agent in that session.

test -d "/data/projects/livespec-overseer/plan/foreman" \
  || { echo "HALT: missing plan thread /data/projects/livespec-overseer/plan/foreman"; echo "REMEDY: create or choose the correct plan topic before supervising"; exit 1; }
pane_cwd=$(tmux display-message -p -t "$WORKER_TARGET" '#{pane_current_path}')
[ -n "$pane_cwd" ] \
  || { echo "HALT: empty pane_current_path for 'foreman'"; echo "REMEDY: re-check the exact worker target and stop if it still resolves empty"; exit 1; }
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

All five preconditions were measured PASS at 2026-08-02T23:42Z when this charter
was generated: worker pane pid 270839 running codex, supervisor pane pid 2257990
running claude, distinct panes, plan thread present, worker cwd
`/data/projects/livespec-overseer`. That is a claim with a timestamp like every
other — re-run the block rather than trusting this sentence.

## Corrections

Thread-specific corrections live here. Regenerating this binder MUST preserve
this section byte-for-byte, from the `## Corrections` heading through the end of
the section. Preserve spelling, punctuation, code formatting, blank lines, and
ordering exactly.

- **T1 (2026-08-02) — I was about to raise the maintainer's revise valve costed
  at SIX proposals when eight were pending.** `handoff.md` says "The six
  spec-side proposed changes are FILED (PR #495, 2026-08-02)", which is true
  about what this thread filed and false about what a `/livespec:revise` pass
  will walk. Two older proposals —
  `gap-invisible-clauses-to-must-form.md` and
  `supervise-plan-authors-two-layers.md`, both 2026-07-30, both after the `v004`
  snapshot — sit in the same directory and are not this thread's. `revise` is
  directory-scoped, not thread-scoped, so the maintainer would have been asked to
  authorise a walk-through two proposals larger than the one described to them.
  The general fault is mine and not the handoff's: **a count inherited from a
  prose record is a claim with a timestamp, exactly like an item status, and the
  directory was one `ls` away.** Re-measure a SET before quoting its SIZE in a
  picker option, because the cost stated in an option is the thing the maintainer
  actually consents to.

- **T2 (2026-08-03) — I asserted a ledger fact I had not measured, in the very
  binder whose job is to stop that.** This file shipped saying slice `.2`
  "carries no dep edge and no stated precondition", and told the reader to treat
  its ordering after `.1` as an inference from acceptance text. The ledger says
  otherwise and always did: `.2` is blocked by `.1`, and `.3` by `.2` by `.1`,
  as real `blocks` edges. What I actually ran was `bd dep tree` on `.1`, `.5` and
  `overseer-n7xx67` — never on `.2` or `.3` — and a dep tree for `.1` shows what
  blocks `.1`, not what `.1` blocks. I read three absences of an inbound edge as
  evidence about a different item's outbound edges. **A dep tree is directional,
  and "I saw no edge" is evidence only about the node actually queried.** Worse,
  I labelled the guess as an inference and thereby made it look considered — a
  flagged guess still reads as a measurement to the next supervisor. The error
  was caught by the worker in task-02, which measured every slice by id as
  instructed instead of inheriting my summary. That is the second time on this
  thread the worker's measurement beat the supervisor's prose, and both times the
  rule I broke was the one this binder itself states: re-measure, do not carry
  forward.

- **T3 (2026-08-03) — I re-dispatched work that had already merged, and two
  implementations of slice `.1` landed on master.** The chain: the dispatcher
  reported failure, I re-ran `drive.py` in the FOREGROUND under a 240s timeout
  to capture stderr, that started a second real dispatch and the timeout killed
  the caller, I read the leftover claim as spurious and dispatched a third time.
  Two runs completed and both auto-merged, leaving
  `_supervisor_status_snapshot.py` and `_supervisor_snapshot.py` implementing
  the same ratified behaviour side by side. Filed as `overseer-41p` and since
  resolved to one module. **Every link in that chain was something I had already
  filed** — `overseer-6pn` (a failing dispatcher whose PR merged), `overseer-1hv`
  (no reconciliation path), and the foreground-rerun trap I wrote into the marker
  *after* committing it. Filing a hazard is not the same as being protected from
  it; the rule has to be checked at the moment of acting, not at the moment of
  writing. **Check `gh pr list --state merged` before every re-dispatch.**

- **T4 (2026-08-03) — three times I inferred a cause from a label instead of
  reading one layer down, and each time a measurement refuted me.** (a) I called
  master "red" and "fleet-blocking" from two local failures; load average was 109
  on 18 cores against a fixed 5s tmux settle, and the same commits were green in
  CI. (b) I filed a P1 saying the daemon never wrapped a Codex track because a
  Codex context footer was unparseable; `signals.py` handles both renderings by
  design and the parser returned `17` on the real pane — the true defect was an
  unbounded suppression guard, and a Claude track in another repo was starved
  identically. (c) I read `check-commit-pairs-source-and-test: fail` as a pairing
  defect and briefed a commit reshape; the job had died on a ruff download
  timeout before that gate ran. **A check, a footer, and a status line all name a
  thing; none of them explains itself.** Run the positive control, read the job
  log, check the host — before writing the cause down anywhere a reader will
  inherit it.

- **T5 (2026-08-03) — I filed FIVE duplicate work items and burned factory spend
  on one, by breaking role-level correction C18 twenty minutes after applying
  C18 correctly.** I measured "Phase B has no work items" at 18:32Z. That was
  TRUE when measured. Another track filed the entire Phase B cut at
  18:43:02–18:44:01Z. I filed mine at 19:04Z — twenty-one minutes later —
  **without re-measuring** — then dispatched one at 19:12Z.
  C18 is this failure verbatim, and I had read it at boot: *"Search the ledger
  for the SUBJECT before filing anything from an inherited list"*; *"re-measuring
  the fact while trusting the metadata about the fact is only half the
  discipline"*. C18's own incident was a **fourteen**-minute gap; mine was
  twenty-one. Concurrent tracks measure this repo constantly, so a
  minutes-old "this is unfiled" is entirely normal and entirely wrong.
  **WORSE: I APPLIED THE RULE CORRECTLY EARLIER IN THE SAME SESSION.** Finding
  the worker livelock, I searched first, found `overseer-t6m` and
  `overseer-vyjkzw` already covered it, and deliberately did NOT file. Then I
  filed five duplicates on the very next filing action — the same shape as C20
  and C23, both of which record breaking a rule in the turn right after
  applying it. Knowing a rule and having just used it does not arm it.
  **A SECOND, INDEPENDENT DEFECT MADE IT UNDETECTABLE: my subject search
  filtered to non-closed items**, so it could not have found a sibling that was
  already DONE — which is precisely the answer that should have stopped me.
  Never status-filter a subject search; "already built" is the finding.
  **THE MAINTAINER'S RULING WAS MADE ON MY STALE REPRESENTATION.** They chose
  "file and dispatch all five" because I told them Phase B was unfiled. The
  decision was sound given what I presented; the presentation was the defect.
  Escalating with a stale premise converts my measurement error into their
  decision, which is worse than making it alone.
  What limited the damage was not me: the implementation agent detected the
  duplicate itself, refused to push, and recorded a precise reason
  (*"duplicate/no-longer-applicable: … already merged green in PR #625"*). No
  duplicate code merged. **That is the third time on this thread a worker's
  measurement beat the supervisor's prose** (see T2, T3).
  THE RULE: **re-run the subject search AT THE MOMENT OF FILING, unfiltered by
  status** — not at plan time, not before the picker, not "recently". Minutes
  are enough to make it wrong.

  **ADDENDUM (2026-08-03T20:50Z) — I STATED THAT RULE CORRECTLY AND THEN RAN IT
  THROUGH A TOOL THAT FILTERS BY DEFAULT.** My searches used plain
  `bd list --limit N --json`, and I wrote "unfiltered by status" in the code
  comment beside them. Measured with a control: `bd list --all --limit 1000`
  returns **191** items where the same call without `--all` returns **39**. The
  default hides roughly four-fifths of the ledger, including everything closed
  — and "already built, already closed" is exactly the answer a
  did-someone-already-do-this search exists to find.
  Worse than a static filter: **the hidden set GROWS OVER TIME**, so the same
  search silently narrows. My duplicate-hunt an hour earlier did surface a
  freshly-closed sibling; the identical command later did not. A query that
  worked once is not a query that works.
  So: pass `--all` explicitly, and prove the widening with a control
  (`--all` count strictly greater than the default) rather than trusting the
  flag name. This is the C1/C12 rule — *when a check passes, confirm it can also
  FAIL* — applied to a search: **a search that cannot return the closed item
  cannot tell you the work is already done.**
