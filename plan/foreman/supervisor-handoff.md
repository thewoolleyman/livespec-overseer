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

  **THE RESTART-LIVELOCK CLAIM BELOW IS REFUTED FOR THIS SESSION — RE-MEASURED
  2026-08-04T13:21Z. Read this before planning around a worker you believe cannot
  be restarted.** The worker declared `ready` at 13:21:34Z and the daemon
  respawned it at **13:21:53Z — nineteen seconds** — as
  `codex resume … 019fcb7d-… read plan/foreman/handoff.md and follow it`, coming
  back at 75% context from 28%. A wrap-up injection had also arrived at 13:10:49Z,
  which independently refutes the neighbouring claim that this track is
  `session-gone` and gets no wrap-up. **Both standing worker-health warnings in
  this binder were stale, and inheriting them would have had this session plan
  around a worker it wrongly believed was terminal.** The MECHANISM below is
  preserved verbatim because it is real and may recur — it is the imperative that
  expired, not the description. `overseer-t6m`/`overseer-vyzkzw` and
  `overseer-6eo` remain OPEN and their acceptance is unmet; only their stated
  impact on this track has lapsed. Re-measure before trusting either direction.

  **THE ORIGINAL CLAIM, PRESERVED — measured
  2026-08-03T08:26–08:29Z and still true at 20:44Z, when it was at 17% context.**
  It obeys the marker protocol correctly: at each wrap-up it writes
  `winding-down` then `ready` and stops. It is never restarted, because the
  daemon renders it `working (background shell)`. The busy guard in
  `_supervisor_evaluate.evaluate` reads
  `busy and (ready or not (shell_only and eff_ctx <= threshold)) and ...`, so
  `ready` is the FIRST disjunct — declaring `ready` does not bypass the busy
  branch, it GUARANTEES it; `_void_if_stale` then clears the declaration and the
  wrap-up re-fires. The busy evidence is not work: `has_active_subshell` sees an
  MCP server chain (`with-homelab-env.sh` -> `op run` -> `mcp-remote`) alive for
  the session's whole life, which can never exit on its own.
  **DO NOT "FIX" THIS BY RESTARTING THE DAEMON — that remedy is REFUTED.**
  PR #597 rewrote exactly the deciding module and merged 07:28:08Z, so a stale
  daemon is the obvious suspect; both the current and pre-fix versions were run
  against the live tree and BOTH return `True`. Loading the fix changes nothing
  here. Recorded on `overseer-t6m`; `overseer-vyjkzw` should own the fix.
  PRACTICAL CONSEQUENCE: the worker cannot be rotated for fresh context, so it
  will run out. Plan for it to stop permanently, and do not hand it work that
  needs more context than it has left.

- **THE READ-FIRST CHAIN IS THREE FILES AND THEY ARE ORDERED.** `handoff.md`
  names them: `research/seed-prompt.md` (the maintainer's verbatim requirements
  including addendum item 8), then `research/brainstorm.md` (§3 records four
  maintainer decisions that are FIXED inputs; §4 is the CURRENT v2 phasing and
  its correction banners are live corrections, not history), then
  `research/review-findings.md` (33 external adversarial findings; the per-phase
  dispositions are BINDING and are not to be re-litigated without new evidence).
  Cite finding ids when you reason about design here — the thread's whole
  vocabulary is those ids.

- **STATE AS OF 2026-08-05T04:38Z — BOTH RATIFICATIONS HAVE LANDED AND TWO
  PHASE-D SLICES ARE RUNNING IN THE FACTORY RIGHT NOW. THIS IS THE ONLY STATUS
  BLOCK; EVERYTHING ELSE IN THIS FILE IS STANDING GUIDANCE.** Re-measure before
  acting; the Verification Discipline block below is the command. **Two standing
  worker-health warnings in this file were REFUTED on 2026-08-04 (see the
  retirement notice above) — a health claim ages exactly like an item status.**

  **THE FIRST THING TO DO ON A COLD OPEN IS NOT TO DISPATCH ANYTHING.** Two runs
  were in flight at wind-down and BOTH claims are REAL:

      overseer-ym6   fabro 01KZ817KD05M   running   37m35s at 04:38:23Z
      overseer-afn   fabro 01KZ83CQ38A6   starting  32s     at 04:38:23Z

  Both read `active`/`fabro` in the ledger, and both are corroborated by
  `fabro ps` — that is what makes them real rather than phantom. **DO NOT
  RE-DISPATCH EITHER.** Reconcile per the discipline below: check
  `gh pr list --state merged` FIRST (`overseer-6pn`: a dispatcher that reports
  `failed` while its PR MERGED is that bug, not a real failure), then
  three-way discriminate — failed-with-merged-PR = reconcile not re-dispatch;
  blocked = `fabro dump` FIRST; absent from `fabro ps -a` = eviction, release the
  claim by hand and record WHY on the item.

  Watchers were armed on both dispatch logs and were stopped at wind-down, so
  **NOTHING IS WATCHING THEM NOW — re-arm before doing anything else.** The
  scripts are `tmp/overseer/foreman/watch-ym6-dispatch.sh` and
  `watch-afn-dispatch.sh`; each hardcodes its own id, reads the dispatch log,
  and distinguishes queued-or-running from evicted.

  **COLD-OPEN, DO THESE SIX THINGS FIRST, IN THIS ORDER:**

  0. **`git fetch` AND CHECK THIS FILE IS CURRENT** before reading it for
     content — role-level correction **C24** carries the runnable check. A
     charter is a claim with a timestamp.
  1. **READ `plan/foreman/research/seed-prompt.md` IN FULL.** It is the
     maintainer's VERBATIM intent — requirements 1–7 plus addenda 8 and 2.
     **The previous supervisor never read it across an entire session while
     driving this thread to a false "done".** Then `research/brainstorm.md` §3–§4
     and `research/review-findings.md` for the binding dispositions.
  2. **Read the supervisor marker** at `tmp/overseer/foreman/.supervisor-state`
     — full narrative behind every summary here.
  3. **`ls tmp/overseer/foreman/INBOX*` AND READ EVERY ONE.** Peer tracks
     deliver cross-track notifications as `INBOX-from-<repo>-<topic>.md` files
     in THIS thread's runtime directory. **This step exists because it was
     missing**, and on 2026-08-04 a `livespec` notification sat unread there for
     over two hours while this supervisor filed a six-slice cut it was directly
     about — see **T10**. An inbox is a source like any other; a boot chain that
     does not name it cannot be obeyed into reading it.
  4. **`tmux capture-pane -p -t '=foreman:'` — READ THE WORKER'S PANE.** Read the
     **HEAD**, not the tail: the pane is ~107 lines and a fresh prompt sits at
     the TOP, so `| tail` renders a healthy session as blank (T7).
  5. **Re-measure the ledger with `bd list --all`** (bare `bd list` hides ~4/5).

  **WHY THIS THREAD WAS REOPENED — v1 WAS NEVER PROVEN TO RUN.** It was archived
  on unit-green. The maintainer then invoked `/livespec-overseer:foreman` for the
  first time and **both shipped executables are dead on arrival**:

  ```
  $PLUGIN_ROOT/bin/foreman-runtime -> ModuleNotFoundError: '_claude_sessions_proc'
  $PLUGIN_ROOT/bin/foreman-act     -> ModuleNotFoundError: 'jsonio'
  ```

  Reproduced on cache build `0.27.2`, on `ff2644d0fc8e`, and on the repo-side
  `.claude-plugin/bin/` copy. Both pin only the plugin ROOT onto `sys.path` then
  `from overseer import …`, while every module flat-imports its private siblings.
  The working siblings go through `python3 -m overseer.daemon`; `bin/overseerd
  --help` prints usage, which is the clean control.

  **Eleven closed slices, 983 tests, 100% coverage, two releases, a post-merge
  janitor and a live daemon restart ALL passed over a product that cannot
  start**, because every acceptance leg was satisfied by beside-tests that
  `sys.path.insert` the package dir and import modules directly. **NOTHING EVER
  EXECUTED A SHIPPED ENTRYPOINT.**

  **EXIT CONDITION FOR THIS REOPENING — e2e tests that EXECUTE the shipped
  artifacts and demonstrate the seed-prompt requirements working.** Unit tests
  with injected fakes do not count; they are what produced the false "done".
  **DO NOT ARCHIVE THIS THREAD AGAIN ON UNIT-GREEN.**

  **REQUIREMENT 5 WAS THE BIGGEST GAP AND IT IS NOW LARGELY BUILT — this
  paragraph used to say "IT IS NOT BUILT" and that is retired.** The maintainer
  ruled at 07:12Z to build Phase C+D; the panel core (`overseer-a7c`) and the pin
  correction (`overseer-xbn`) are CLOSED and RELEASED, and the minority-report
  round (`overseer-ncx`) was in flight at wind-down. What remains is the
  RATIFICATION plus the wiring — see the state table.

  **STATE, re-measured 2026-08-05T04:38Z. This supersedes every earlier reading
  in this file, including the 14:12Z table it replaces.**

  | Thing | State |
  |---|---|
  | `plan/foreman/` | **un-archived**, live |
  | epic `overseer-z5fo4y` | `backlog` (open) |
  | `origin/master` | `84cf51b`; CI **green** |
  | ratified spec | **`v009`** is latest (`v007` = the consensus policy, `v009` = evidence-based Codex questions) |
  | `SPECIFICATION/proposed_changes/` | holds `post-void-ready-certification.md` — **ANOTHER THREAD'S, do not process it** (see below) |
  | `overseer-6fm` entrypoint gate | **closed**, released |
  | `overseer-gxzv5v` actuator filing defect | **closed**, PR #665 |
  | `overseer-5f2pfj` occupied-session classifier | **closed**, PR #670, released v0.28.1 |
  | `overseer-mqpgs7` E2E for seed reqs 3/4/6/7 | **closed**, PR #672, released v0.29.0 |
  | `overseer-a7c` Phase C core (the panel) | **closed**, PR #668, released |
  | `overseer-xbn` panel pin correction | **closed**, PR #675 |
  | `overseer-ncx` minority-report round | **CLOSED** — its ORIGINAL run finished green (PR #681, merge `ec778b2`, released `0.30.0`). Correctly never re-dispatched. **PHASE C IS COMPLETE.** |
  | `overseer-ym6` Phase D foundation | **`active`/`fabro`, run `01KZ817KD05M` RUNNING — real claim. DO NOT RE-DISPATCH.** Spec half discharged by `v007`; the WIRING is what is running |
  | `overseer-afn` Codex question surface | **`active`/`fabro`, run `01KZ83CQ38A6` starting — real claim. DO NOT RE-DISPATCH.** Legs 1-2 MEASURED and discharged, marker-protocol claim AMENDED by `v009`; only leg 3 remains |
  | `overseer-0fy` gate driving | `backlog`, gated on **`ym6` alone** (`ncx` closed) |
  | `overseer-ctc` E2E for requirement 5 | `backlog`; needs **`0fy` AND `afn`** — verified from `ctc`'s OWN dep tree, not its blockers' (T2). **The exit condition** |
  | `overseer-6eo` (P1) | OPEN and unmet, but **its stated impact on this track has LAPSED** — a wrap-up reached this worker at 13:10:49Z |
  | worker session `foreman` | alive, codex, **restarted TWICE** (13:21:53Z and again overnight); at **88% context** at 04:38Z, lane complete, needs nothing |

  **THAT RATIFICATION IS DONE — `v007` IS MERGED. 2026-08-04T14:10:54Z, PR #688,
  merge `c57d928`.** This paragraph used to name PR #679's pending
  `/livespec:revise` pass as the single most important open thing; it is
  discharged. Verified against the FORGE after a fetch, not the working tree:
  `SPECIFICATION/history/v007/` is in `git ls-tree origin/master`,
  `proposed_changes/` holds only its `README.md`, the self-retiring sentence has
  **zero** occurrences in master's `spec.md`, and the ratified policy is present.
  **PHASE D IS UNGATED.** Do not re-run revise and do not re-file the proposal.

  Three things about that pass are worth inheriting rather than re-deriving:

  - **The blocker was a PRECONDITION, not the decision.**
    `no_stale_revise_branches` failed on three `spec/*` branches that were
    rebase-merge leftovers (C13's shape — a landed branch is not an ancestor of
    `origin/master`). `--skip-stale-branch-check` was available and was REFUSED,
    because skipping a check is this contract's one stop-boundary. The branches
    were deleted behind backup refs at `refs/backup/2026-08-04/`, and the check
    then passed on its own merits.
  - **RATIFYING AHEAD OF IMPLEMENTATION IS SUPPORTED — use `test: "TODO"`.**
    `check-heading-coverage` demands a registry entry for every `##` heading and
    an INTEGRATION-tier test for every `## Scenario:`. No integration test exists
    for the consensus panel, so the eight new headings were unlandable until they
    were registered as `"test": "TODO"` with a non-empty `reason` (and, for
    scenarios, a reason that explicitly acknowledges the tier requirement). Ten
    such entries already existed. **Never point a new heading at an unrelated
    existing test to make that gate green.**
  - **THE INDEPENDENT REVIEW CAUGHT A REAL DEFECT, so do not treat it as
    ceremony.** The first pass returned BLOCKERS: `contracts.md` cited
    `spec.md §"The foreman"`, a heading that does not exist — an invented anchor
    that read plausibly. Corrected, digest recomputed, re-reviewed to NO
    BLOCKERS. `just check`'s `doctor-anchor-reference-resolution` would also have
    caught it; the review caught it first and cheaper.

  **THE DEPLOYMENT PROOF IS DISCHARGED — 2026-08-04T06:56:40Z, AGAINST THE
  RELEASED CACHE BUILD, AND CONTROLLED BOTH WAYS.** The previous version of this
  paragraph told the reader to wait for the release and then re-prove; the
  release cut as PR #664 at 06:51:54Z (tag `v0.27.5` = `c35dea6`, and
  `git merge-base --is-ancestor c6ace4b c35dea6` confirms the entrypoint fix is
  IN it), `just ensure-plugins` reports the cache at `c35dea62368f`, and every
  file in that build's `bin/` — enumerated from the TREE with `find`, not from a
  list, so a future executable is covered the day it lands — was EXECUTED under
  `env -u PYTHONPATH`:

      foreman-act      rc=0    usage: foreman-act [-h] --proposal PROPOSAL ...
      foreman-runtime  rc=0    usage: foreman-runtime [-h] [--repo REPO] ...
      overseer-start   rc=0    usage: overseer-start [-h] [--warn-percent N]
      overseerd        rc=0    usage: overseerd [-h] [--warn-percent N]

  **THE NEGATIVE CONTROL IS WHAT MAKES THAT MEAN ANYTHING** (T6: a successful
  result is not a finding unless you know what the check examined). The prior
  build `af2e3af9aa61` (v0.27.4) is still on disk, so the identical command shape
  was run against it: `foreman-act` exits 1 on `ModuleNotFoundError: No module
  named 'jsonio'` and `foreman-runtime` exits 1 on `No module named
  '_claude_sessions_proc'`. The check CAN fail. It did not.

  **DO NOT RE-RUN THIS AS IF IT WERE OPEN, and do not read it as more than it
  is.** It closes the ENTRYPOINT question only. The reopening's exit condition is
  e2e proof of the SEED REQUIREMENTS, and that is untouched by this.

  **THE MAINTAINER RULED ON REQUIREMENT 5 AT 07:12Z: BUILD PHASE C+D NOW.** The
  worker drafted the cut and raised it as a picker in its OWN pane; per C23 the
  supervisor PROXIED it rather than pointing the maintainer at that pane, and
  relayed the answer back down by selecting the matching option there. So
  requirement 5 is now IN the reopened thread's exit condition: the pinned
  Fable/Opus/GPT-sol panel, the minority-report override, typed auto-actions, the
  blocked-pane interlock, the Codex native-picker fallback, and the cross-repo
  spec amendments needed to reverse the report-only disposition (review finding
  C1) across `livespec-overseer`, `livespec-orchestrator-beads-fabro` and
  `livespec`. **The standing "do not add Phase C consensus" prose and the
  `human_action_report_only` refusal are now SUPERSEDED by this ruling** — that
  is a deferral the maintainer has explicitly reversed, so do not re-apply it as
  if it still bound.

  **WHY THE ORIGINAL PLAN MISSED REQUIREMENT 5, since the mechanism matters more
  than the blame and it will recur.** It was never overlooked: `brainstorm.md`
  specifies the panel completely, and maintainer decision 4 deliberately scoped
  it out with `v1 = phases A+B`. The defect is that **Phases C, D and E existed
  ONLY as prose bullets in a research document and were never cut into ledger
  items**, while completion was computed entirely from ledger state. So a
  deferral written in prose and a completion measured in the ledger could never
  meet, and the unbuilt majority was invisible to every instrument that decided
  the thread was done. Each check was internally consistent and every one
  answered *did we do what the epic said* — none answered *does the epic say what
  the seed asked*. **A phase with no ledger representation does not exist to any
  process that measures the ledger. Give every deferred phase a carrier, or the
  deferral becomes a silent cancellation.**

  **THE WORKER OWNS THESE FOUR — do NOT file them yourself (T5):**

  1. **FILED as `overseer-gxzv5v` and IN FLIGHT** (run `01KZ5RWXGN67`, confirmed
     `running` 06:58Z). `work_item_file` cannot complete through the actuator: the
     filing subprocess raises `ModuleNotFoundError:
     livespec_orchestrator_beads_fabro`. Also `append_journal` sits AFTER the
     raising call in `act()`, so **a failed filing leaves no audit trace at all**.
  2. **FILED as `overseer-5f2pfj`**, `pending-approval`, held by the worker until
     `gxzv5v` lands. `classify_session_lifecycle` would **START INTO AN OCCUPIED
     tmux session** — it special-cases only `unassigned` and `_matching_live` keys
     purely on the registry name. Measured: `charter-gate-ratchet` returns
     `action=start` while its tmux holds a live Claude (pid 1741876). Destructive;
     only the prose boundary kept it from firing.
  3. **FILED as `overseer-mqpgs7`** — "E2E: shipped foreman fulfills seed
     requirements 3, 4, 6, and 7" — created 07:01:04Z, `pending-approval`, blocked
     by BOTH `overseer-5f2pfj` and `overseer-gxzv5v` (verified by querying
     `mqpgs7`'s OWN dep tree, not its blockers' — T2). Covers per-work-item
     sessions named exactly after the item; auto-created sessions; the `NEEDS YOU`
     summary; and the hourly loop — whose 2-consecutive-identical-states exit
     ALREADY exists as `converged_ticks=2` returning `exit_reason`, so that leg is
     a PROOF, not a build.

     **A T5 NEAR-MISS WORTH THE THREE LINES, because it happened to the
     supervisor writing this file.** An unfiltered `--all` subject search at
     06:58Z returned nothing for this subject, and that reading was TRUE. The
     worker filed `mqpgs7` at 07:01:04Z — three minutes later. The sentence
     "still unfiled" was written into this binder at 07:15Z and was already false;
     it was caught only by re-measuring before the commit landed. **Minutes are
     enough. Re-measure a "this is unfiled" claim at the moment you WRITE it, not
     only at the moment you file.**
  4. **RULED 07:12Z — BUILD PHASE C+D NOW. THE CUT IS FILED; ITEMS 1–3 ABOVE ARE
     ALL CLOSED.** Six slices were transcribed from the binding design (NOT
     invented): `a7c` core panel, `ncx` minority-report, `ym6` Phase D
     foundation, `0fy` gate driving, `afn` Codex picker, `ctc` requirement-5 E2E.
     Edges were wired AFTER creation — `bd create --deps blocks:X` reads INVERTED
     and produced a fully reversed chain the last time Phase B was cut — using
     `bd dep <blocker> --blocks <blocked>`, then verified by querying EACH item's
     OWN tree (T2). `bd dep cycles` reports none.

  **NEXT ACTIONS, IN ORDER, FOR THE SESSION THAT INHERITS THIS:**

  1. ~~Check whether PR #679's proposal has been REVISED.~~ **DONE — `v007`
     merged 2026-08-04T14:10:54Z (PR #688).** Phase D is ungated.
  2. ~~Reconcile `overseer-ncx`.~~ **DONE — it completed on its ORIGINAL run.**
     Run `01KZ679ZJM93EH05HF184EP1QZ` reported green, PR #681, merge `ec778b2`,
     janitor green, released as `0.30.0`. It was never a phantom claim and was
     correctly NOT re-dispatched. **Phase C is COMPLETE**: `a7c`, `xbn`, `ncx`
     all closed.
  2b. **A SECOND RATIFICATION LANDED TOO — `v009`, PR #717, merge `332aa3a`,
     2026-08-05T03:53:45Z.** It corrects the refuted "Codex in YOLO mode cannot
     raise a structured question" claim: capability MUST now be derived from LIVE
     GATE EVIDENCE, never inferred from a runtime name, launch mode, or
     approval/sandbox policy. **The `blocked:` escape hatch was deliberately NOT
     deleted or narrowed** — only its justification was retired — because
     `codex exec` is headless with no picker, not every human decision is
     multiple-choice, and the feature can be withdrawn. The same commit corrected
     `overseer/marker-protocol.md`, the CARDINAL doc, which sits OUTSIDE
     `SPECIFICATION/` so no revise pass can ever reach it.

  3. **`ym6`'s SPEC HALF IS DISCHARGED BY `v007`** — its acceptance leg 1 reads
     "the spec amendment filed through the `/livespec:` lifecycle in the OWNING
     repo", the owning repo is THIS one, and both the filing (#679) and the
     ratification (#688) have happened. **Leg 1's wording is now misleading
     rather than outstanding; the item is annotated.** What remains is the
     WIRING — reading the ratified key with report-only as the fail-closed
     effective value, surfacing an unrecognized value, making the effective value
     observable without invoking the foreman, refusing self-setting, plus leg 2's
     journal-before-act RED test and leg 3's opt-in control. That is ordinary
     code in this repo, so it IS factory-dispatchable; the old "not a factory
     dispatch" framing died with the three-repo re-scoping.
  4. **`afn` leg 1 is DONE and positive**; legs 2–3 and the marker-protocol
     amendment remain.
  5. Then `0fy` — now gated on `ym6` ALONE, since `ncx` is closed — then `ctc`.
     `ctc` is the exit condition, and it is where the foreman finally gets RUN.
     **Do not run the product before then**; that is a deliberate ordering, not
     an oversight.
  6. **Post-step `capture-impl-gaps` (revise prose Step 13) has NOT been run**,
     deliberately: gaps belong against ratified bytes, and `overseer-ym6` already
     carries this exact implementation, so running it blind risks the duplicate
     this thread has already filed twice (T5, C18). Run it, but search the
     subject `--all`-unfiltered first and expect `ym6` to be the answer.

  7. **DO NOT PROCESS `SPECIFICATION/proposed_changes/post-void-ready-certification.md`.**
     It is 38 KB, it belongs to the SEPARATE live thread
     `plan/ready-certification-deadlock/` (epic `overseer-er6ikw`, both tmux
     sessions alive), and it carries an explicit binding sequencing constraint —
     one of its findings says in terms "MUST NOT be implemented on its own".
     `/livespec:revise` is DIRECTORY-scoped, so a pass run for one of YOUR
     proposals will walk it too unless the payload names only your decision.
     **That is safe and proven**: the CLI requires `proposed_changes/` to be
     NON-EMPTY, not fully processed, and `v009` left this exact file pending and
     byte-identical (blob `edf6c483` before and after). Name only your own
     decision, then VERIFY afterwards that the other file is untouched.

  **`overseer-ym6` WAS RE-SCOPED AT 11:2xZ AND ITS OLD TITLE WAS WRONG.** It used
  to read "a THREE-REPO reversal of the needs-human guarantee". **There is no
  reversal and no contradiction.** I had quoted the orchestrator contract from a
  work item's DESCRIPTION instead of reading `contracts.md`; the actual clause
  (1932-1944) states a FLOOR OVER POLICY SETTINGS — "no policy setting MAY
  auto-dispose a truly-unresolvable decision" — not a ban on config-selected
  autonomy, and it constrains THE DISPATCHER specifically. `livespec` already
  ratified the same shape as **v193**: `revise_decision_mode`
  (`manual|delegated|consensus`, safe default `manual`) with
  `requires_revise_decision_input` owning the hard floors, and "consensus is
  valid configuration but unavailable evidence escalates; NO PANEL WAS BUILT OR
  STUBBED". **The panel was always the missing piece, and `a7c` built it.** The
  maintainer identified this; I had it wrong. Do not restore the old framing.

  **BUT THAT RETRACTION IS ITSELF TOO BROAD IN EXACTLY ONE PLACE, AND THE PEER
  TRACK CAUGHT IT — 2026-08-04T11:31Z, absorbed here 13:25Z.** The floor clause's
  own enumeration reads: *"A decision that is human-gated BY DESIGN — **drift
  acceptance**, a spec-change slice, a regroom / backlog bounce, or a
  `human-only` acceptance — MUST stay escalated even when the Dispatcher is fully
  confident."* **Drift acceptance is named INSIDE the floor, not below it.** So
  `drift_acceptance_mode: consensus` genuinely does contradict that clause until
  the clause itself is amended. The general retraction stands; drift is the
  exception. Note how each side reached a wrong answer one artifact apart: I
  quoted the contract from a work item's DESCRIPTION, and they accepted my
  retraction's framing until they opened `contracts.md` themselves.
  **NEITHER HALF IS OURS TO CARRY.** `bd-ib-qek6`
  (`livespec-orchestrator-beads-fabro`, `backlog`) amends the floor for drift
  acceptance ONLY, preserving every other floor verbatim; `livespec-jvdvx4.5`
  (`livespec`) carries core's drift-doctrine sentence and the
  `spec_governance.drift_acceptance_mode` key. Both were filed by the peer track
  into their OWNING tenants. They must agree, and **neither may ratify claiming
  the other already did.** `v007` deliberately did not touch drift: it keeps
  drift acceptance inside the hard floors and binds the floor CATEGORIES by
  reference rather than restating them, so it pre-empts nothing.
  **THE O12 FOUR-PLACE LIST ON `overseer-ym6` IS NOT COMPLETE** — `livespec` is a
  fifth place, carried by `livespec-jvdvx4.5`. Do not read that enumeration as
  exhaustive.

  **A REPO-WIDE DISPATCH BLOCKER I CLEARED — expect its shape again.** The first
  dispatch was refused by a **pre-dispatch LEDGER check**, not by anything about
  the item: `depends-on-ref-wellformedness` found `overseer-e723tt` carrying
  `{"kind":"cross-repo","ref":"…#…"}`. Accepted kinds are `local`,
  `sibling_work_item`, `pull_request`, `branch`. **ONE malformed entry on ONE
  unrelated item blocks EVERY dispatch in the tenant.** Fixed by rewriting the
  whole metadata object via `--metadata @file.json` (never `--set-metadata`, C11)
  after validating the replacement THROUGH THE REAL PARSER. Read dispatcher
  stderr before blaming your own item.

  **MY PRs, ALL MERGED — do not re-do them:** #605, #623, #634, #635, #637
  (role-level C24 — this one reddened master for ten minutes, see T6), #639,
  #642, #648, #654, #660 (the reopening). Prior sessions' history is in the
  superseded blocks below and in the marker.

- **THE DAEMON CANNOT SEE THIS THREAD'S OWN LIVE WORKER, SO NOTHING IS
  SUPERVISING IT — filed 07:05Z as `overseer-6eo` (P1).** Measured against a
  FRESH snapshot (written_at 07:04:04Z, tick 721, 57 rows): `topic=foreman` reads
  `status=session-gone, tmux=null, runtime=null, ctx=null,
  session_identity="none:/data/projects/livespec-overseer:foreman"` while the
  tmux session is alive and working. **`session-gone` means NO wrap-up injection
  and NO restart**, so the worker runs to zero context with no wind-down and the
  supervision layer never notices.

  MECHANISM, measured to the file: the codex process holds EXACTLY ONE rollout
  fd, `019fcb7d-8b6b-7461-b86f-e6fc67876603`, created 06:37:24Z, while
  `~/.codex/session_index.jsonl` holds 183 rows and was last written 05:22:23Z —
  75 minutes EARLIER. `map_codex_sessions` resolves no `thread_name` and drops
  the process. The mapping store DOES carry the row and it names `tmux: foreman`,
  so the daemon holds a correct topic-to-tmux binding and still reports GONE.

  **NOT the three closed neighbours, and check this before re-deriving:**
  `overseer-159` was TWO rollouts with the wrong one picked (this holds ONE, the
  right one); `overseer-mir` was ZERO rollout fds and its impact claim was
  explicitly RETRACTED (this DEMONSTRATES that retracted impact on a live track);
  `overseer-j1r` was the CLAUDE path and `nameSource: derived`. j1r is the
  instructive one — it fixed this exact operator-facing harm for Claude with a
  softener, on the stated principle that the operator should not be told
  finished-looking work was lost when it is merely out of reach. **The codex path
  has no equivalent softener**, so an unresolvable rollout degrades straight past
  every informational status to the daemon's ONLY red one.

  **NOT a fleet-wide outage, and the control is why that is known:** the same
  snapshot resolves `runtime=codex` for 10 rows. A first pass looked for the
  index under `~/.codex/sessions/`, found nothing, and was forming a fleet-wide
  claim; the runtime-distribution control refuted it before it reached anything
  durable. **An absence is not a finding until the query is proven able to find
  something** — and the index is at `~/.codex/session_index.jsonl`.

  PRACTICAL CONSEQUENCE FOR DRIVING: while this is open, the supervisor is the
  ONLY thing watching this worker. Arm a pane watcher and tell the worker
  explicitly that no wrap-up is coming, because it will otherwise wait for one.

- **THIS THREAD HAS A LIVE PEER TRACK AND AN AGREED BOUNDARY — do not duplicate
  it and do not file into its tenant.** `livespec` repo, plan thread
  `plan/spec-side-autonomy/`, tmux sessions `spec-side-autonomy` (codex) and
  `spec-side-autonomy-supervisor` (claude), epic `livespec-jvdvx4`.

      plan/foreman/            OWNS the foreman and the consensus panel implementation
      plan/spec-side-autonomy/ OWNS the core-owned spec_governance lever design

  Neither closes into the other. **`livespec`'s half of the work — its
  drift-doctrine sentence and the `spec_governance.drift_acceptance_mode` key
  (`human | consensus`, default `human`, and it NEVER accepts `delegated`) — is
  THEIRS.** `overseer-ym6` cross-links `livespec-jvdvx4` in prose and must not
  carry it. **Do not add a metadata dep edge for that cross-link**: this tenant's
  `depends-on-ref-wellformedness` accepts only `local`, `sibling_work_item`,
  `pull_request` and `branch`, and one malformed `cross-repo` entry blocks EVERY
  dispatch in the tenant.

  Their standing valve was "the key must not ship armed-able before the consensus
  panel exists". **It exists now**, and the ratification it was waiting on has
  LANDED as `v007`.

  **THE NOTIFY-ON-RATIFICATION PROMISE IS DISCHARGED — 2026-08-04T14:12Z.** It
  had been inherited across three supervisor sessions. Delivered on BOTH channels
  they named: appended to
  `/data/projects/livespec/tmp/overseer/spec-side-autonomy/INBOX-from-livespec-overseer-foreman.md`
  and one line to their `worker-status.log`, naming the version (`v007`), the
  merge commit (`c57d928`), that drift stays inside the floors so `bd-ib-qek6` is
  not pre-empted, and the caveat that this is ratified AHEAD of implementation —
  so if they need the foreman to actually ACT, that is gated on `overseer-ym6`,
  not on `v007`. **Do not re-send it; do not re-promise it.**

  **THEIR REPLY 2 (11:31Z) SAT UNACKNOWLEDGED THROUGH A WIND-DOWN** and is ACKed
  as of 13:25Z. Its substance is a correction to this binder and is folded in
  above — drift acceptance is named INSIDE the floor. **Check the INBOX at every
  cold open (step 3); a reply can arrive between a predecessor's last read and
  their wind-down, which is exactly what happened here.**

- **THERE IS A SECOND PEER TRACK, IN THIS REPO, AND THIS THREAD'S WORKER IS ITS
  LIVE REPRODUCTION.** `plan/ready-certification-deadlock/` (epic
  `overseer-er6ikw`, both tmux sessions alive) owns the uncertifiable-`ready`
  deadlock. Its handoff already cites THIS track's 2026-08-03 instance.
  **A SECOND OCCURRENCE HAPPENED HERE ON 2026-08-05 AND IT CARRIES A
  DISCRIMINATOR THEY DID NOT HAVE.** At 03:55:47Z the worker held a sincere
  `ready`, idle, on pane pid 2484970 — and was NOT respawned. But a `ready` on
  that SAME session had been honoured in NINETEEN SECONDS at 13:21:53Z the day
  before, returning it to 75% context. **So the condition is INTERMITTENT, not
  permanent.** That refutes both over-strong models: "this session can never be
  restarted", and "the daemon never sees the declaration" — it demonstrably saw
  and cleared one, and the snapshot then read `declaration=null`.
  **I REPORTED, I DID NOT FILE.** They own the subject and have a PENDING
  proposal about it; filing would have been C18/T5 exactly. Delivered to
  `tmp/overseer/ready-certification-deadlock/INBOX-from-livespec-overseer-foreman.md`
  and one line in their `worker-status.log`, asserting NO mechanism claim because
  I did not read `_void_if_stale` and that analysis is theirs.
  **AN OFFER IS OUTSTANDING AND UNANSWERED:** I offered to HOLD the worker in the
  reproducing state for them to observe rather than letting it wind down. If they
  reply asking for that, honour it. Otherwise the worker takes the normal path —
  and it already has, twice.

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

- **`just worktree-create` FAILS AT SCALE IN THIS REPO — AND SO DOES
  `just worktree-reap`, WHICH MAKES IT SELF-REINFORCING. Re-measured
  2026-08-04T13:18–13:23Z at 121 WORKTREES:** both recipes exit **141**
  (128+13 = SIGPIPE), `worktree-create` at recipe line 25 and `worktree-reap` at
  line 39. **The sanctioned remedy for having too many worktrees is the recipe
  that the number of worktrees breaks**, so the condition can only worsen
  unattended. The root-cause item `livespec-dev-tooling-2oip`
  ("`worktree_primary_path` dies of SIGPIPE past ~4KB of `git worktree list`
  output") was **CLOSED 2026-08-03T18:35Z on this exact signature**, so this is a
  regression or an incomplete fix — reported there as a comment (not reopened;
  their queue's next action is theirs). Compounding it,
  `livespec-dev-tooling-xezh` records that reap's merged-ness test is ANCESTRY,
  which under this fleet's mandatory rebase-merge can never recognise a correctly
  landed worktree — so nothing is ever reaped and the list only grows.
  **The binder previously cited only `livespec-dev-tooling-zi4q` and only
  `worktree-create`, at 81 worktrees.** The proven rescue,
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

- **T6 (2026-08-03) — I REDDENED MASTER WITH A CORRECTION ABOUT FALSE ASSURANCE,
  AND EVERY LAYER I USED TO CHECK MY WORK REPORTED SUCCESS WITHOUT LOOKING.**
  PR #637 landed role-level **C24** and broke `check-coverage` and
  `check-per-file-coverage` on master at 21:12:32Z. A red master refuses EVERY
  factory dispatch fleet-wide at the dispatcher's green-master pre-flight — the
  C14 precedent, where a charter edit held the fleet across seven commits — and
  it simultaneously blocked PR #638, the `wykyth` work I was supervising. So a
  correction written to protect the next supervisor blocked the thread it was
  written on. Red for about ten minutes; fixed forward by PR #639 with neither
  gate weakened. Both breaks were gates working exactly as designed: appending a
  correction reddens `test_charter_correction_counts_are_current` until the ONE
  prose sentence stating the count is updated, and
  `tests/prompts/test_cold_open_generation_gate.py` **executes** every fenced
  `sh` block in `.ai/supervisor-protocol.md` under stubs where the forge is
  unreachable, so a block ending `|| exit 1` exits 1.
  **THE FIRST FALSE ASSURANCE — WHY IT REACHED MASTER.** I wrote "verified, both
  charter gates green (107 tests)" and believed it. Both hooks printed
  `doc-only mode detected (zero .py files staged): running
  just check-pre-commit-doc-only` and **skipped the aggregate**. The prose gates
  that caught this live in `just check-coverage`, which never ran locally.
  **A DOCS-ONLY CHANGE DOES NOT RUN THE TESTS THAT GATE DOCS.** This is distinct
  from the repo-root CLAUDE.md note that a doc-only branch is still REFUSED at
  push without the worktree pack: that is about permission to push, this is
  about what gets checked once you may.
  **THE SECOND — AND IT NEARLY PUT A FALSE "VERIFIED" IN THE FIX ITSELF.**
  Re-running `just check-coverage` after editing returned `rc=0`, and I was one
  step from citing it. Its first line: `reading existing .coverage (produced by
  check-per-file-coverage); no duplicate suite run`. It re-read stale coverage
  data and ran no tests. `rc=0` there is a statement about a PREVIOUS run.
  Caught only because a `grep` for "passed" came back EMPTY and I treated the
  empty result as a question rather than a pass. **To verify a tree, run the
  SUITE (`uv run pytest`), not a recipe that may legitimately decide it has
  nothing to do.**
  **THE THIRD, ON A PROBE — AND IT IS THE MOST TRANSFERABLE.** My first watcher
  tested dispatcher liveness with `ps -eww -o args= | grep -F '<pattern>'`, and
  its POSITIVE control failed against a process I had just seen alive. Cause:
  `ps` captures the harness's OWN invocation, whose argv holds the entire script
  — including every pattern the script searches for — so a deliberately
  IMPOSSIBLE pattern "matched" too. `/usr/bin/grep` gave the same answer, ruling
  out this host's `grep`→ugrep shim. That is the global `pgrep -f` self-match
  trap wearing new clothes: not the matcher finding itself, but the command line
  containing the needle. **THE FIX IS STRUCTURAL: run watchers FROM A FILE, and
  HARDCODE their patterns inside it** — a pattern passed as an argument lands
  right back in argv and restores the bug. Then the corrected probe failed its
  positive control AGAIN, and that time it was true: the dispatcher had exited.
  **A broken probe and a true negative are indistinguishable until the probe is
  controlled.**
  A FOURTH, CAUGHT BEFORE IT COST ANYTHING, recorded because it is the same
  family and the cheapest to hit: `fabro ps` **truncates the 26-character ULID**
  to 12. An equality probe built from the displayed id matches nothing forever
  and reads as ABSENT — the queue-eviction shape — which would release a REAL
  claim on a RUNNING job and dispatch it again (T3). `status` is an OBJECT
  (`.status.kind`), so a string compare silently never matches either. Both were
  found by running positive AND negative controls before arming, plus a
  truncation control that DEMONSTRATES the displayed id failing to match.
  **THE SHAPE, since it is now four deep:** C24 says a charter's `PASS` can be
  uninformative; the hooks' PASS was uninformative; the recipe's `rc=0` was
  uninformative; the probe's match was uninformative. The shared layer already
  says *an empty result is not a finding*. **This generalises it: a SUCCESSFUL
  result is not a finding either, unless you know what the check actually
  examined.** Ask what a green thing looked at before you spend it as evidence.

- **T7 (2026-08-04) — I DROVE THIS THREAD TO A FALSE "DONE" WITHOUT EVER READING
  THE REQUIREMENTS OR EVER RUNNING THE PRODUCT.** The maintainer found both, in
  one sentence, by invoking the skill.
  **FAILURE ONE: I never read the seed prompt.** This binder's own read-first
  chain names three files — `research/seed-prompt.md`, `brainstorm.md`,
  `review-findings.md`. Across an entire session I read NONE of them, while
  dispatching eleven slices, closing an epic, archiving the thread and reporting
  v1 complete. That is role-level **C19** verbatim ("when a boot instruction
  enumerates N sources, read all N"), and C19 is in the shared layer I read at
  boot. Having finally read it: **requirement 5, the Fable/Opus/GPT-sol consensus
  panel, is the ENGINE for goals 2 and 3 and was never built** — so the thing the
  maintainer actually asked for did not exist while I called it done. **A plan's
  acceptance is the SEED's requirements, not the ledger's slice titles.** I was
  auditing the slices against each other and never against the ask.
  **FAILURE TWO: no test ever executed a shipped artifact.** Both `bin/`
  executables raise `ModuleNotFoundError` before any logic runs. Every acceptance
  leg read "beside tests prove X", and every one of those tests
  `sys.path.insert`s the package dir and imports modules directly. 983 tests,
  100% coverage, two releases, a post-merge janitor and a live daemon restart all
  passed over a product that cannot start. **I even verified the DAEMON's new
  code behaviourally, with three controls, and never once ran the foreman's own
  binary** — so I demonstrated I knew the difference between shipped and running,
  and applied it to the component I happened to be thinking about.
  **THIS IS T6 ONE LAYER OUT, AND T6 SHOULD HAVE CAUGHT IT.** T6 says a
  successful result is not a finding unless you know what the check examined. I
  wrote that sentence and then accepted "beside tests prove X" eleven times
  without once asking what those tests import. **When an acceptance criterion
  says a test proves something, read the test's IMPORTS, not its name.**
  **THE STRUCTURAL FIX, not a resolution to try harder:** `overseer-6fm` adds a
  gate that EXECUTES every file in `bin/` as a subprocess under a scrubbed
  environment, enumerated from the tree so a future executable is covered the day
  it lands, with a sabotage control so it cannot pass vacuously.
  **THREE TMUX MECHANICS I ALSO GOT WRONG while restarting the worker**, each of
  which cost real time: (a) `tmux respawn-pane -k` WITHOUT a command re-runs the
  pane's ORIGINAL command — it does NOT give you a shell, so every following
  `send-keys` lands in the agent's composer as a PROMPT; I twice made the worker
  launch a NESTED codex that way. (b) `capture-pane | tail` on a ~107-line pane
  shows only trailing blanks, because a fresh prompt sits at the TOP — I
  diagnosed a healthy session as dead. **Read the HEAD.** (c) a large paste
  arrives in CHUNKS and can settle INCOMPLETE (4088 of 5075 chars, stable across
  four polls). **Put a long brief in a FILE and send a one-line pointer** — the
  same idiom the daemon's own resume line uses.

- **T8 (2026-08-04) — I READ A RENDERING AS A MEASUREMENT, AND THE "FIX" I
  REACHED FOR MADE IT WORSE. THIS PARTLY CORRECTS T7(c) ABOVE.** Pasting a
  2765-char note into the Codex worker, the composer rendered
  `[Pasted Content 1018 chars]`. I polled four times, saw it stable, and
  concluded the paste had TRUNCATED — which is exactly what T7(c) taught me to
  expect. I then sent `tmux send-keys C-u` to clear it. **`C-u` did not clear the
  composer**, and a second chip appeared beside the first, so the pane then read
  `[Pasted Content 1018 chars][Pasted Content 1020 chars]` and I had made the
  state worse while believing I was repairing it.
  **THE CHIPS ARE A COLLAPSED RENDERING, NOT A LENGTH REPORT.** Once I typed an
  ordinary trailing line, the composer EXPANDED and ended on the note's true last
  line — the content had been complete the whole time, and 1018+1020 is not the
  content's length in any sense. The subsequent submission confirmed it: the full
  note, every section, is in the worker's transcript.
  **SO T7(c) IS RIGHT ABOUT THE REMEDY AND WRONG ABOUT THE DIAGNOSTIC.** Putting
  a long brief in a FILE and sending a one-line pointer remains correct and is
  what I did. But "stable across four polls" is NOT evidence of truncation,
  because the number being polled is not a measurement of anything. **Do not
  derive a byte count from a UI chip, and do not send control keys to a composer
  on the strength of one.** If you doubt a paste, add a trailing line and read
  what the composer expands to, or verify from the receiving side after
  submission — never from the chip.
  THE FAMILY THIS BELONGS TO IS T6's: a successful-looking readout is not a
  finding unless you know what produced it. T6 was about a green result that had
  examined nothing; this is about a NUMBER that measured nothing. Both invite
  action, and here the action was destructive-adjacent — a control key sent into
  a live peer session on a false premise, which is one keystroke away from C21's
  near-miss of re-pasting into another track's pane.

- **T9 (2026-08-04) — I EXECUTED ARBITRARY COMMANDS OUT OF MY OWN PROSE, THEN
  KILLED MY OWN SHELL TRYING TO CLEAN IT UP. Two textbook shell traps, back to
  back, one of which is written down in the instructions I had already read.**
  **(a) BACKTICKS IN A DOUBLE-QUOTED SHELL STRING ARE COMMAND SUBSTITUTION.** I
  wrote a ledger note that quoted two identifiers in backticks — a `codex exec`
  invocation and the `blocked:` token — inside a double-quoted
  `bd update --append-notes "…"` argument. The shell did exactly what it is
  specified to do: it RAN them. A real `codex exec` process started and hung
  reading a prompt from stdin, the `bd` write never happened, and the whole call
  sat until the 600s tool timeout. **The failure announced itself in the one line
  of output — `Reading prompt from stdin...` — which is not a `bd` message at
  all.** Read the output you got, not the output you expected.
  Every earlier `--append-notes` call in this session succeeded only because it
  happened to contain no backticks. That is luck, not technique, and prose about
  shell tooling is exactly the text most likely to contain them.
  **THE FIX IS STRUCTURAL, not "escape more carefully":** build note text with a
  QUOTED heredoc (`<<'EOF'`) into a file, then pass `"$(cat file)"`.
  Command-substitution OUTPUT is not re-scanned, so backticks inside it are
  inert. Verified working immediately afterwards, with a read-back.
  **(b) `pkill -f '<pattern>'` MATCHED ITS OWN SHELL AND KILLED IT.** Cleaning up
  the hung process, I ran `pkill -f 'codex exec'`. The harness's own invocation
  carries that pattern in its argv, so `pkill` matched itself; the call died with
  exit 144. **This is the self-match trap stated verbatim in the global operating
  instructions, which I had read at boot.** Knowing a rule and having read it
  recently does not arm it — the same shape as T5, C20 and C23, all of which
  record breaking a rule shortly after applying or reading it.
  **WHAT MADE IT SURVIVABLE WAS THE MEASUREMENT, NOT THE CARE.** I verified the
  blast radius immediately rather than assuming it was contained: the worker was
  alive on the SAME pids (3096957/3096987) and the acting daemon was alive at pid
  1842709 with a snapshot 20 seconds fresh at tick 1342 — so it was still
  TICKING, not merely present. Neither of those processes carries `codex exec` in
  its argv, which is why they survived; had the pattern been `codex` I would have
  killed this repo's own worker, and a broader one could have reached the daemon,
  whose blast radius is the whole fleet.
  **THE RULE: never `pkill`/`pgrep -f` a pattern that can appear in your own
  command line.** Resolve an exact pid first and kill that, or match on something
  structurally absent from the invocation. And after ANY kill by pattern, prove
  what survived by pid — a kill is the one operation where an unexamined success
  and a catastrophe look identical.
  **A THIRD, SMALLER MECHANIC FROM THE SAME SESSION, recorded because it wasted
  two round trips:** a `tmux send-keys` of roughly a thousand characters or more
  renders in the Codex composer as a `[Pasted Content N chars]` chip, and the
  FIRST `Enter` does NOT submit it — a second `Enter` does. The pane shows no
  `Working` indicator in between, which is the reliable discriminator between
  "not submitted yet" and "submitted and still rendering". Check for that
  indicator before concluding either way; and note this does NOT contradict C21's
  warning against re-sending, because there the composer was empty and here it
  demonstrably still held the text.

- **T10 (2026-08-04) — I ASSERTED A CROSS-REPO CONTRADICTION FROM A WORK ITEM'S
  PARAPHRASE, ALMOST FILED A SPEC REVERSAL ON IT, AND MISSED A PEER'S MESSAGE
  SITTING IN MY OWN DIRECTORY. The maintainer caught all of it in one question.**
  **THE SUBSTANTIVE ERROR.** I read `bd-ib-vntx65`'s DESCRIPTION, which quotes the
  orchestrator's `contracts.md`, and concluded that `overseer-ym6` proposed
  reversing a ratified guarantee. I titled the item that way, wrote it into the
  item's notes, and raised a maintainer picker asking how to scope the reversal.
  **Reading `contracts.md:1932-1944` directly shows something narrower and
  differently shaped**: "No policy setting MAY auto-dispose a truly-unresolvable
  decision… The Dispatcher MUST NOT auto-resolve a `blocked_reason: needs-human`
  item." That is a FLOOR OVER POLICY SETTINGS — it presupposes config-selected
  autonomy and bounds it — and it names THE DISPATCHER, not every actor. Below
  the floor it is exactly config, which is what the maintainer said and I had not
  verified. `livespec` had already ratified that very pattern as **v193**, with
  `consensus` valid as configuration and the PANEL deliberately left unbuilt —
  the piece this thread had just built. **There was no contradiction to resolve.**
  **THE RULE I BROKE IS ONE THIS FILE ALREADY STATES.** T4 says a check, a footer
  and a status line all NAME a thing and none explains itself; C18 says verifying
  the thing in front of you is not verifying the claim that made you act on it.
  A work item quoting a spec is a PARAPHRASE OF AN AUTHORITY, not the authority.
  **Read the spec, not the ticket about the spec** — especially before proposing
  to change it, because a proposal filed on a misread is a misread with a PR
  number and someone else's revise pass behind it.
  **WHAT STOPPED IT WAS NOT ME.** I had already searched the peer tenant and
  written the finding down; I was one tool call from filing. The maintainer asked
  whether config fields dissolved the conflict. **A picker raised on a premise I
  had not verified would have converted my error into their decision** — T5's
  exact shape, one repo further out.
  **THE SECOND FAILURE, AND IT IS STRUCTURAL RATHER THAN CARELESS.** The peer
  track had written me a cross-track notification at 09:05Z, into
  `tmp/overseer/foreman/INBOX-from-livespec-spec-side-autonomy.md` — MY OWN
  runtime directory, the same directory as the marker I read at boot. It sat
  unread for over two hours while I filed a six-slice cut it was directly about,
  and their supervisor's handoff correctly recorded it as UNACKNOWLEDGED. **My
  boot chain enumerates the ledger, `handoff.md` and the marker; it does not
  enumerate an inbox.** C19 says read all N sources a boot instruction names —
  this is one layer earlier: **the enumeration itself was incomplete, so
  obedience could not have saved me.** Cold-open step 3 now names it. When you
  add a channel by which other tracks can reach you, add it to the boot chain in
  the same change, or you have built a mailbox nobody opens.

- **T11 (2026-08-04) — THE WORKER WAS DEAD ON A REVOKED TOKEN, THE BANNER'S OWN
  REMEDY WOULD HAVE MADE IT WORSE FOR EVERY OTHER SESSION ON THE HOST, AND THE
  FIX WAS A PLAIN RETRY.** Cold-opening, I found the worker pane showing, twice:
  *"Your access token could not be refreshed because your refresh token was
  revoked. Please log out and sign in again."* Its 13:10:50Z turn — the daemon's
  wrap-up injection — hit `task_complete` **0.9 seconds** later, i.e. aborted
  before doing anything, and it had written no `.overseer-state` at all. That is
  the wrap-up text's own "you are reported to the human as not responding" case.
  **THE BANNER NAMES A REMEDY THAT POINTS AWAY FROM THE FIX, and following it
  would have caused a second, larger outage.** `~/.codex/auth.json` is SHARED by
  every Codex session on this host — there were a dozen live. Its `last_refresh`
  read **13:13:00Z**, i.e. a SIBLING session had rotated the refresh token
  successfully *after* this worker's attempt failed. The credential ON DISK was
  fresh the whole time. This is a refresh-token **ROTATION RACE**: the worker held
  a stale token in memory, a sibling rotated it, and the server correctly rejected
  the old one. Logging out and signing in again would have rotated it AGAIN and
  broken every other live Codex session — including two other tracks' workers.
  **THE FIX WAS ONE SHORT MESSAGE.** I sent a retry instruction; the worker
  re-read the on-disk credential, acknowledged, wrote `winding-down`, updated and
  committed its handoff (PR #684), and declared `ready`. No re-auth, no restart,
  no maintainer.
  **HOW TO TELL, BEFORE ACTING:** read `last_refresh` in `~/.codex/auth.json` and
  compare it against when the failure occurred (the rollout file's tail gives the
  exact turn timing). A `last_refresh` NEWER than the failure means a sibling
  already repaired the credential and a retry will work. Only a `last_refresh`
  that is stale, or a genuinely absent/short-lived token, argues for re-auth.
  Never print token material — presence, prefix and length are enough.
  THE FAMILY: this is the repo-root CLAUDE.md's *"a remedy that appears to do
  nothing"* trap wearing new clothes, and its cousin C13 — an error message names
  a cause, and a cause is not an explanation. It is also T4 exactly: **a banner,
  like a check name and a status line, names a thing and does not explain
  itself.** The cheap discriminating read took one command.

- **T12 (2026-08-04) — THE DAEMON'S OWN WRAP-UP INSTRUCTION DIRTIES THE PRIMARY
  CHECKOUT BY DESIGN, AND THAT IS THE CONDITION `overseer-6pn` SAYS FAILS EVERY
  DISPATCH FLEET-WIDE.** The maintainer caught this as "wrote a handoff doc to
  the primary checkout".
  **WHAT WAS ACTUALLY THERE, because the alarming reading was the wrong one.**
  `git status` showed one modified file, `plan/foreman/handoff.md`, **unstaged and
  uncommitted**, and `git log origin/master..HEAD` was EMPTY — nothing had been
  committed to the primary and the commit-refuse hook was never bypassed. The
  file was **byte-identical to `origin/master`** (SHA-256 both ways, with a
  positive control proving the diff could report a difference). The worker had
  written it, then committed it correctly through a worktree as PR #684, which
  merged. The primary was simply two commits BEHIND, so already-landed content
  rendered as a local modification. The repair was a fast-forward; nothing was
  discarded and nothing was lost.
  **THE MECHANISM IS THE WRAP-UP TEXT ITSELF, so it recurs every wind-down.** The
  daemon's injected instruction says, in order: (1) *"UPDATE
  `plan/<topic>/handoff.md` to match"* — which is the PRIMARY checkout, because
  that is where the session is — and only then (2) create a worktree, `cp` the
  file across, and commit THERE. Step 1 necessarily dirties the primary, and
  nothing in the ritual cleans it up afterwards.
  **WHY THAT IS NOT COSMETIC.** `overseer-6pn` records that the post-merge
  janitor pulls the PRIMARY checkout and that **one dirty file there aborts its
  `git pull` and fails every dispatch fleet-wide**. So the sanctioned wind-down
  ritual manufactures, once per wind-down, exactly the state that halts the
  factory for every repo. It also sets up C24's trap: the successor cold-opens on
  a primary that is behind, and reads a stale charter.
  **WHAT TO DO:** after any wind-down, `git status` the primary and fast-forward
  it. **Check `git status`, not `git log`** — the repo-root CLAUDE.md already says
  this for hook-gated commits, and it applies here for the opposite reason: `git
  log` looked perfectly healthy while the tree was dirty. And before discarding
  anything, prove WHOSE the edit is: compare the working file against
  `origin/master` by hash, not by `git diff` against a stale HEAD, which reports a
  landed change as a local one.

- **T13 (2026-08-05) — TWO ITEMS WERE ONE COMMAND AWAY FROM BEING DISPATCHED
  WITH BODIES THAT ORDERED WORK THAT WAS ALREADY DONE, AND ONE OF THEM ORDERED A
  MEASUREMENT ITS SANDBOX STRUCTURALLY CANNOT INTERPRET.** An item's ACCEPTANCE
  TEXT ages exactly like its status, and nothing re-measures it — the ledger
  updates `status`, never the prose.
  **`overseer-ym6`** still read "the spec amendment filed through the
  `/livespec:` lifecycle in the OWNING repo" as acceptance leg 1. That was
  discharged by `v007`: the owning repo is this one, the filing was PR #679 and
  the ratification PR #688. A sandbox agent reading it would have re-filed a
  proposed change that was already ratified.
  **`overseer-afn` was worse, and this is the transferable half.** Its body said
  the marker-protocol claim "STANDS until a live measurement says otherwise" and
  made that measurement the slice's FIRST deliverable. The claim was refuted on
  2026-08-04 and amended by `v009`. But the deeper hazard is that **the fabro
  sandbox is HEADLESS and the feature is scoped to the INTERACTIVE CLI**, so a
  re-run there would have produced a NEGATIVE that measured THE HARNESS, not the
  feature — a false negative indistinguishable from a real finding. That is
  precisely the confusion the item's own leg 2 exists to prevent, and the item
  would have walked its agent into it.
  **THE FIX THAT GENERALISES: before dispatching, read the item's ACCEPTANCE as
  if you were the sandbox agent, and ask two questions — is any leg already
  discharged, and can this environment even produce an interpretable result for
  each leg?** Where the answer is no, annotate the item BEFORE dispatch with an
  explicit stop-and-escalate instruction, and correct a title that names retired
  work. Both were annotated and `afn` was retitled; the annotation tells the
  agent to REPORT a dispute rather than measure, because "produce a fresh
  negative from the wrong environment and record it as a finding" is the failure
  mode.
  This is C9's family — "the PR merged and CI is green" answers a different
  question from "the acceptance criteria were met" — arriving from the opposite
  direction: here the acceptance criteria were met and the TEXT never noticed.

- **T14 (2026-08-05) — TWO TOOLING HAZARDS THAT BOTH FAIL AS A PASS, caught by
  controls rather than by care.**
  **(a) `status` IS A READ-ONLY VARIABLE IN zsh.** Building a CI watcher I wrote
  `status=${row%%|*}`, and the control died with `read-only variable: status`.
  Under this fleet's zsh, `$status` is a reserved alias for `$?`. A watcher whose
  first assignment aborts emits NO `WAKE:` line at all — the exact silent death
  C16 is about, where a killed watcher is indistinguishable from one that never
  fired. The script's shebang is bash, where the name is legal, so it would
  probably have survived; **"probably" is not a control**. Renamed to
  `run_status` and verified with `bash -n`. THE RULE: never name a shell variable
  `status` here, and run a watcher's parser once by hand before arming it — this
  is C14 and C22's family, bash idioms that silently do nothing under zsh.
  **(b) THE FIRST `just check` IN A FRESH WORKTREE FAILS ON `check-coverage`,
  AND RE-RUNNING THE RECIPE ALONE "PASSES" WITHOUT TESTING ANYTHING.** Measured
  while landing `v009`: `just check` reported `Failed targets (1): check-coverage`.
  Re-running `just check-coverage` returned **rc=0**, and its FIRST LINE was
  `:: check-coverage: reading existing .coverage (produced by
  check-per-file-coverage); no duplicate suite run`. **That rc=0 is a statement
  about a PREVIOUS run — it executed no tests.** This is T6 verbatim, met in the
  wild rather than recalled, and it is the shape that would let a false
  "verified" reach a commit message.
  The cause is ORDERING: in a brand-new worktree `check-coverage` runs before
  `check-per-file-coverage` has produced a `.coverage` to read. **The remedy is
  not to re-run the recipe until it passes.** Run the SUITE (`uv run pytest` —
  green, exit 0), then the aggregate again (All 68 targets passed, green token
  written), and confirm with a control that the failure grep CAN match — it
  matched on the failing run and found nothing on the green one.
