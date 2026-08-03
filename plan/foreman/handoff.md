# Plan — foreman

## What this thread is

A new `livespec-overseer:foreman` surface: a singleton per-repo LLM operator
session (required tmux AND runtime-registry name `<repo-slug>-foreman`) on an
hourly loop that keeps its OWN repo's plans and work-items moving, escalates
only what a cross-vendor model-consensus panel confirms genuinely needs the
maintainer, keeps everything else progressing, and coordinates with peer
foremen in other repos by filing — never by driving their queues. It is a
PEER of the overseer daemon: the daemon stays the deterministic mechanical
layer (unchanged, including its `NEEDS YOU`), and the foreman builds the
semantic decision-routing layer on top of a new read-only daemon snapshot.

Ledger anchor: `overseer-z5fo4y` (epic). Its children are the Phase A
slices `overseer-z5fo4y.1` – `.5` (dotted ids; the epic edge is prose-only —
this tenant refuses task-to-epic dep edges).

## Read-first chain (in this order, all beside this file)

1. `research/seed-prompt.md` — the maintainer's verbatim requirements,
   including addendum item 8 (the mandatory `<repo-slug>-foreman` name).
2. `research/brainstorm.md` — the grounded architecture. Its §3 records four
   maintainer decisions that are FIXED inputs (snapshot transport; a
   consensus policy tier via spec amendment; daemon attention unchanged and
   subsumed; v1 = phases A+B). Its §4 is the CURRENT (v2, post-review)
   phasing; its correction banners are live corrections, not history.
3. `research/review-findings.md` — the external adversarial review record
   (Opus + GPT/Codex, 33 findings, every load-bearing claim independently
   re-verified). The per-phase dispositions in it are BINDING design
   constraints; do not re-litigate a finding without new evidence.

## Restart checkpoint — 2026-08-03, v006 and `.5` landed; `.1` cleanup is next

The previous prepared-revise checkpoint is fully discharged. The nine-proposal
ratification landed as v006 in `47ad0e0` (PR #575), and
`SPECIFICATION/proposed_changes/` is empty. The
`spec-revise-v005` worktree and its payload are completed artifacts, not a
resume target. **Do not run revise again.**

Slice `.5` also landed as `335a578` (PR #580). Task 05 investigated its only
red forge job before touching the branch. The job's actual first-attempt
complaint was an environment-setup timeout downloading `ruff==0.8.6`; it never
executed the named commit-pair check. An unchanged failed-job rerun executed
`check-commit-pairs-source-and-test`, which passed, followed by `ci-green`.
Auto-merge then landed the PR. No commit reshape, code edit, rebase, push, or
work-item re-dispatch occurred. The ledger's `.5` note claiming a REAL pairing
defect is therefore stale and contradicted by the forge log.

The urgent unfinished state is slice `.1`: two independent implementations
merged in `f54ff05` (PR #582) and `1065ad7` (PR #585). `overseer-41p` (P1,
`backlog`) records the duplication and the required cleanup. Until one
canonical snapshot writer and its matching test surface remain, `.1` is not
complete even though its ledger record is `active`, and dependent slices must
not advance. Do not re-dispatch `.1`; that is the mechanism that created the
duplicate.

No task-05 worktree or local branch was created, and no task-05 subprocess is
still running. Forge master was last fetched at `335a578`.

## Where the thread stands — derive live status from the ledger, not this file

Filed status is a claim with a timestamp; re-measure before acting:

```sh
/usr/local/bin/with-livespec-env.sh -- bd show overseer-z5fo4y --json
ls SPECIFICATION/proposed_changes/
```

(a bare `bd` in this repo returns Access denied — the wrapper is required).

**As re-measured 2026-08-03 after PR #580 merged:**

- The epic is `backlog`; `.1` and `.5` still read `active`/`fabro` even
  though their forge state has moved beyond those claims. `.2`, `.3`, `.4`,
  and `overseer-n7xx67` remain `pending-approval`.
- v006 is ratified and all nine proposal files are archived. The ratification
  prerequisite for the Phase A work is satisfied.
- `.5` has one implementation, green CI, and a merged PR. Reconcile its stale
  ledger record to `closed`; do not re-dispatch it and do not try to rewrite
  its already-merged history.
- `.1` has the opposite problem: two merged implementations. Read
  `overseer-41p` in full, compare both implementations against the v006
  snapshot contract, retain one canonical writer/test surface, and remove
  the other without unpicking the survivor. Exactly one writer must be called
  once per daemon tick. Do not close `.1` until that cleanup is forge-green.
- The slices carry real dependency edges: `.2` is blocked by `.1`, and `.3`
  by `.2` and `.1`. A dep tree is directional — querying `.1` reports what
  blocks `.1`, never what `.1` blocks.
- `overseer-n7xx67`'s spec-side acceptance landed in v006; re-check its exact
  ledger acceptance against the archived scenario and heading-coverage row,
  then reconcile it rather than filing or ratifying a duplicate proposal.

## NEXT ACTION — clean up duplicated `.1`; the picker is DISCHARGED

FIRST, re-fetch and re-measure `overseer-41p`, `.1`–`.5`,
`overseer-n7xx67`, PRs #575/#580/#582/#585, and current master. Then:

1. Reconcile `.5` to `closed` from PR #580's green merged evidence. The stale
   pairing-defect note is provenance, not a reason to act on the branch.
2. Route `overseer-41p` through the normal work-item/factory lifecycle. Its
   implementation must choose the canonical `.1` snapshot module by the v006
   contract, remove the loser plus its tests and mirror, and leave exactly one
   once-per-tick writer. This is cleanup of merged duplication, not a third
   implementation of `.1`.
3. Keep `.1` open and `.2`/`.3` blocked until that cleanup merges green. Then
   reconcile `.1` and advance `.2`, `.3`, and `.4` in dependency order under
   the standing autonomous-driving grant.
4. Verify `overseer-n7xx67` against the v006 archived scenario and coverage
   row and reconcile it if its acceptance is already satisfied.

Do not resume `tmp-revise-input.json`, do not re-file any of the nine spec
proposals, do not re-dispatch `.1` or `.5`, and do not hand-code a
factory-eligible ledger item inline.

**The batched valve picker this section used to demand is DISCHARGED.** On
2026-08-03 the maintainer replaced it with a standing instruction to drive
every phase autonomously — plan through implementation, archive and fleet
deployment — and to route any genuinely blocking question to a Codex
subsession first to test whether it truly needs them. That is a broader
grant than any single picker answer, and it is why valve 1 was executed
without one. **A resuming session should not re-raise the picker as if the
decision were still open**; it should either act under that grant or, if
the grant has lapsed, raise the valves that are still ripe. The picker
rules themselves still bind whenever a valve IS raised (recommended option
first, every option stating its cost, full repository names, one batched
call, `---` as the final line before the picker — `.ai/supervisor-protocol.md`
owns them; restated here so this file stays self-sufficient).

Completed valves: `overseer-jgqw7d` landed in `7eb7484` (PR #531); the
nine-proposal v006 revise landed in `47ad0e0` (PR #575); `.5` landed in
`335a578` (PR #580). The remaining implementation route is factory-side.
The two dispatch traps recorded in the repo-root AGENTS instructions apply
verbatim, especially that a foreground diagnostic re-run is itself a real
dispatch and `ACTIVE` is not evidence of a live run.

## Reserved-name hazard — resolved by `.5`

`plan/foreman/` is a discovered plan topic in a watched repo. Adoption
matches live sessions' REGISTRY names against discovered topics, so a
session registry-named `foreman` in this repo WILL be adopted as this
thread's worker — wrapped up at threshold, nudged when idle, and
respawn-able into this handoff.

PR #580 now refuses `-foreman` case-insensitively at topic-level and after
collision-qualified derivation, and `adopt_sessions` leaves live registry
names ending in `-foreman` unadopted. A correctly named foreman prototype is
therefore no longer capturable as a plan worker.

The distinction still matters: the bare topic/session name `foreman` does
not end in the hyphenated reserved suffix, so this thread's ordinary worker
remains adoptable and supervised as intended. Do not broaden the check to a
hyphen-less `endswith("foreman")` in a future cleanup.

## Constraints that bind this thread — do not re-derive

- The daemon is UNCHANGED in behavior and ownership: additive snapshot +
  heartbeat surfacing only. Its evaluate() cascade, cardinal rule, and
  attention semantics are out of bounds (maintainer decision 3).
- Phase A ships NO LLM loop (review O16/C5). Phase B's acting surface is a
  whitelisted executable; human valves stay report-only (C1).
- Foreman state lives under `<repo>/tmp/overseer/foreman/` — inside the
  gitignore-gated scratch, never a new `tmp/` root (O18).
- Never write a literal double-brace template token into any work-item's
  text — it makes the item undispatchable and leaves a phantom claim
  (repo-root `.claude/CLAUDE.md`); describe such constructs in words.
- `just worktree-create` fails at scale in this repo (recorded: 65
  consecutive failures at 77 worktrees; fix tracked in livespec-dev-tooling
  as `livespec-dev-tooling-zi4q`). The proven rescue: `git worktree add
  <path> -b <branch>`, then `just install-worktree-pack` inside it, then
  discard the `worktree_discipline` key it writes into the tracked
  `.livespec.jsonc` unless you mean to land it. Still true at 81+
  worktrees on 2026-08-03; the rescue was used for every branch this
  session.

- **REBASE BEFORE PUSHING, or a docs-only branch inherits everyone else's
  risk.** The pre-push hook picks its subset from the diff against
  `origin/master`. With a STALE BASE that diff sweeps in other tracks'
  `.py` commits, so the hook runs the FULL aggregate instead of the
  doc-only subset — measured 2026-08-03: 407 seconds and a red push for a
  branch touching one markdown file, then 0.96 seconds and a clean push
  after rebasing onto current master. Nothing about the failure names the
  stale base as the cause.

- **DO NOT TRUST A LOCAL FULL `just check` ON A LOADED HOST, and do not
  add to the load.** Measured 2026-08-03T04:11Z: load average 109 on an
  18-core host with 51 sessions. `tests/prompts/` drives real tmux panes
  against a fixed 5-second settle budget, which cannot hold at that load,
  so the aggregate reddens for host reasons and it does NOT look like a
  host problem — one form is a plain test failure, the other is a COVERAGE
  failure with no test reported failed, on a branch containing no Python.
  A local red is not evidence about the tree; CI is the arbiter. Tracked
  as `overseer-63y`, whose acceptance is now the timing DEPENDENCE, not
  the reporting of its expiry (PR #547 made the expiry loud, which helps
  diagnosis and does not remove the dependence).

## Discipline

Fleet-standard: worktree → PR → rebase-merge; never commit on the primary
checkout; never `--no-verify`; `mise exec -- git …` so hooks fire. Check
`git status`, not `git log`, after a hook-gated commit. Never kill the
acting overseer daemon (tmux `livespec-overseer:1.1`) — its blast radius is
the whole fleet. Beads only via the fleet credential wrapper. This thread
FILES ripe work and routes spec matter to the spec lifecycle; it does not
hand-code implementation inline.
