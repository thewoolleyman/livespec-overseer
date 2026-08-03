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

Ledger anchor: `overseer-z5fo4y` (epic). Its Phase A children are
`overseer-z5fo4y.1` – `.5`; its Phase B children are the six random-id slices
listed in the checkpoint below. Every epic edge is prose-only — this tenant's
bridge does not create parent edges — while inter-slice blockers are real
`blocks` edges.

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

## Restart checkpoint — 2026-08-03T19:27Z, PHASE B FOUNDATIONS LANDED; ACTING CHAIN STARTED

**ALL FIVE PHASE A SLICES ARE CLOSED.** `.1` (snapshot export), `.2`
(`list --json`), `.3` (foreman-gather), `.4` (heartbeat surfacing), `.5`
(`-foreman` reserved suffix). Landed as PRs #582/#585 + #601 (dedupe), #607,
#621, #619, #580. Re-measured from the ledger at 18:32Z.

**DO NOT ARCHIVE THIS THREAD YET — and the previous version of this file told
you to, which is the error this checkpoint exists to correct.** It said the
remaining scope after Phase A was "archive this thread, then fleet rollout".
That is wrong. The epic `overseer-z5fo4y`'s own record carries the maintainer
decision of 2026-08-02: **`v1 = phases A+B` (observe, then mechanical acts)**,
with consensus / gate-driving / federation following. Phase A is only the
OBSERVE half. Archiving here would ship half of v1 and strand the other half
with no carrier.

**PHASE B NOW HAS SIX INTAKE-TRIAGED FACTORY SLICES.** They were transcribed
from the already-reviewed Phase B design through the `capture-work-item`
store + six-gate intake seam at 18:45–18:47Z, not filed with raw `bd create`.
The two independent foundations are closed; the first integration slice is
active; every later slice remains `pending-approval` with real `blocks` edges.
The epic stays `backlog` until all six close.

The deterministic wrapper/runtime (`overseer-by6hrx`) merged as PR #625 at
`ee2a1a1`; the fail-closed classifier (`overseer-eqbk4h`) merged as PR #627 at
`07bf2ae`. Both passed their post-merge janitors and closed in the ledger.
`overseer-4opppx` is now genuinely running as Fabro
`01KZ4HD12TAH3Z0CR4ETWPR3HN`.

**A CONCURRENT RAW-FILED DUPLICATE EXISTS:** `overseer-z5fo4y.6` was created
without `intake:triaged` after the six-slice cut and duplicates the wrapper
scope already merged in #625. Its run `01KZ4GWPDG0ARJ5Z9F2YVECJ0N` was
interrupted/steered at 19:26Z with the merge evidence and an explicit command
not to publish. Confirm it terminates without a PR, then close it as
duplicate/no-longer-applicable. Do not touch its worktree or branch directly.

Phase B was already SPECIFIED and its design is BINDING — see
`research/brainstorm.md` §4, which post-dates the external review:
the LLM foreman acting narrowly, behind an entry gate + tmux-name mutex + a
deterministic wrapper (lock, tick scheduling, LLM rotation from a durable
handoff), acting ONLY through a whitelisted `foreman-act` executable (session
lifecycle behind the deterministic never-started / crashed-resume /
ambiguous-report classifier, absolute repo paths, work-item sessions as
bounded one-shots with journaled claims; plus filing and journal triage), with
human valves REPORT-ONLY (C1) and act-time re-verification against a fresh
snapshot read. The ledger cut preserves that design; do not re-cut or groom it
unless a factory run returns concrete non-convergence evidence.

**HOW THE WRONG ARCHIVE CLAIM GOT HERE, because the mechanism matters more
than the correction.** It came from the supervisor binder's status block
("REMAINING ON THIS THREAD: `.2` and `.4` land, then `.3`, then archive the
thread, then fleet rollout") and was copied into this file without being
checked against the epic. It is the same defect class this thread has now
recorded three times — T2 (a ledger fact asserted, not measured), C18 (a
defect re-measured while the claim ABOUT it was not), and T4 (a cause inferred
from a label). **A scope claim is a claim with a timestamp exactly like an item
status.** The epic was one `bd show` away.

The previous prepared-revise checkpoint is fully discharged. The nine-proposal
ratification landed as v006 in `47ad0e0` (PR #575), and
`SPECIFICATION/proposed_changes/` is empty. The
`spec-revise-v005` worktree and its payload are completed artifacts, not a
resume target. **Do not run revise again.**

**THE `.1` DUPLICATION CLEANUP IS DONE — the section below that calls it "the
urgent unfinished state" is superseded and kept only as provenance.**
`overseer-41p` merged as PR #601 at 07:54:27Z and closed; master `ee0fc7f`
deletes `overseer/_supervisor_status_snapshot.py`, its `.claude-plugin` mirror
and `tests/test_status_snapshot_export.py`, leaving `_supervisor_snapshot.py`
as the single once-per-tick writer. `overseer-z5fo4y.1` is `closed`.
`overseer-n7xx67` also closed (PR #600). Re-measured from the ledger and the
forge at 08:11–08:18Z. **Do not go looking for two snapshot modules; there is
one.**

Slice `.5` also landed as `335a578` (PR #580). Task 05 investigated its only
red forge job before touching the branch. The job's actual first-attempt
complaint was an environment-setup timeout downloading `ruff==0.8.6`; it never
executed the named commit-pair check. An unchanged failed-job rerun executed
`check-commit-pairs-source-and-test`, which passed, followed by `ci-green`.
Auto-merge then landed the PR. No commit reshape, code edit, rebase, push, or
work-item re-dispatch occurred. The ledger's `.5` note claiming a REAL pairing
defect is therefore stale and contradicted by the forge log.

**RETIRED 2026-08-03T08:11–08:18Z — kept because the mechanism is the durable
part, re-tensed because the imperative expired.** For several hours the urgent
unfinished state WAS slice `.1`: two independent implementations had merged, in
`f54ff05` (PR #582) and `1065ad7` (PR #585), and `overseer-41p` (P1) recorded
the duplication and the required cleanup. That cleanup merged as PR #601;
`overseer-41p` and `.1` are both `closed`, and one writer remains.

The mechanism that caused it still binds: **`.1` was re-dispatched after its
work had already merged**, because a dispatcher that reports failure while its
PR merges (`overseer-6pn`) makes "failed" useless as a signal. Three
dispatches, two survivors. That is why the standing rule is to check
`gh pr list --state merged` BEFORE any re-dispatch, and never to re-run
`drive.py` in the foreground to capture stderr.

No task-05 worktree or local branch was created, and no task-05 subprocess is
still running.

## Where the thread stands — derive live status from the ledger, not this file

Filed status is a claim with a timestamp; re-measure before acting:

```sh
/usr/local/bin/with-livespec-env.sh -- bd show overseer-z5fo4y --json
ls SPECIFICATION/proposed_changes/
```

(a bare `bd` in this repo returns Access denied — the wrapper is required).

**As re-measured 2026-08-03T19:27Z (ledger/Fabro/forge):**

| Item | State |
|---|---|
| `overseer-z5fo4y` (epic) | `backlog` — **stays open: it spans v1 = A+B** |
| `overseer-z5fo4y.1` snapshot export | **closed** — dedupe landed, PR #601 |
| `overseer-z5fo4y.2` `list --json` | **closed**, PR #607 (sha `706f23b`) |
| `overseer-z5fo4y.3` foreman-gather | **closed**, PR #621 (sha `f699678`) |
| `overseer-z5fo4y.4` heartbeat surfacing | **closed**, PR #619 (sha `a01d3e2`) |
| `overseer-z5fo4y.5` `-foreman` suffix | **closed**, PR #580 |
| `overseer-41p` | **closed**, PR #601 |
| `overseer-n7xx67` | **closed**, PR #600 |
| `overseer-by6hrx` deterministic wrapper/runtime | **closed**, PR #625, `ee2a1a1`, post-merge janitor green |
| `overseer-eqbk4h` fail-closed session classifier | **closed**, PR #627, `07bf2ae`, post-merge janitor green |
| `overseer-4opppx` session-lifecycle `foreman-act` + fresh revalidation | **active; Fabro `01KZ4HD12TAH3Z0CR4ETWPR3HN` running** |
| `overseer-wykyth` typed filing + journal-triage actions | `pending-approval`, blocked by `overseer-4opppx` |
| `overseer-vts4lo` bounded one-shot work-item sessions | `pending-approval`, blocked by `overseer-4opppx` + `overseer-wykyth` |
| `overseer-qp3vpb` Claude/Codex skill + end-to-end v1 binding | `pending-approval`, blocked by the wrapper and all acting/lifecycle slices |
| `overseer-z5fo4y.6` raw-filed wrapper duplicate | **active duplicate; run steered to stop without publishing** |

- v006 is ratified and all nine proposal files are archived. The ratification
  prerequisite for the Phase A work is satisfied — including `.4`'s stated
  precondition (attention-surface membership ratified in `contracts.md`).
- The earlier reconciliation work is all discharged: `.5`, `.1`, `overseer-41p`
  and `overseer-n7xx67` are closed. Nothing here needs re-dispatching.
- The Phase A slices carried real dependency edges (`.2` blocked by `.1`; `.3`
  by `.2` and `.1`), and all of them are now satisfied and closed. The durable
  lesson, since Phase B will have edges of its own: **a dep tree is
  directional** — querying `.1` reports what blocks `.1`, never what `.1`
  blocks, so query the item you actually care about (that is correction T2).
  `.3` also moved `pending-approval` -> `ready` BY ITSELF once `.2` closed; no
  approve valve was run, because per C10 the set-admission + approve two-step is
  unnecessary and permanently rewrites the item's recorded admission policy.

## NEXT ACTION — land `foreman-act`, contain the duplicate, then drain the chain

FIRST, re-fetch and re-measure the six Phase B items, `fabro ps`, current
master, and `gh pr list --state all`; never infer run state from the ledger.
Then:

1. **Watch `overseer-4opppx` to a terminal outcome.** Reconcile forge state
   before any retry. It was dispatched directly from effective
   `admission:auto`; `approve` correctly refused with `invalid-source-state`,
   so do not repeat that human valve.
2. **Contain `overseer-z5fo4y.6`.** Confirm the steered duplicate run opens no
   PR, preserve #625/`ee2a1a1` as its replacement evidence, and close the raw
   record as duplicate/no-longer-applicable. Never implement or merge it.
3. **Then drain `overseer-wykyth`, `overseer-vts4lo`, and finally
   `overseer-qp3vpb` in dependency order.** The item-level `admission:auto`
   labels are intentional; linked items remain `pending-approval` until their
   real edges clear and the lifecycle admits them.
4. **Only after all six close, close/archive the epic and thread, then verify
   the released plugin is deployed fleet-wide.** v1 is A+B; Phase C–E remain
   separate future scope.

Do not resume `tmp-revise-input.json`, do not re-file any of the nine spec
proposals, do not re-dispatch any of `.1`–`.5`, `overseer-41p` or
`overseer-n7xx67` (all closed), do not close the epic on Phase A's completion
(it spans A+B), and do not hand-code a factory-eligible ledger item inline.

**DISPATCH LESSONS FROM PHASE A THAT WILL RECUR IN PHASE B**, each measured
2026-08-03 rather than inherited:

- **A dispatcher `failed` is not evidence the work failed.** `.2` reported
  `failed` at stage `merge-poll` ("PR did not reach MERGED within the poll
  budget") while PR #607 merged fine — the budget expired because CI was red on
  a transient forge outage. That is `overseer-6pn`. Check
  `gh pr list --state merged`, verify the merge sha is an ancestor of
  `origin/master`, then reconcile (`--status acceptance`, then the accept
  valve) rather than re-running.
- **A run can be `blocked` on human input while `drive.py` has already said
  `failed`.** `.4`'s first attempt sat at an unwatched 3-option prompt, then
  died on a hard 240m timeout, destroying its sandbox. `fabro inspect <run>`
  distinguishes `blocked` / `human_input_required` from a real failure.
  **`fabro dump <run> --output <dir>` BEFORE deciding anything** — that dump
  was the only surviving copy of the review finding, and writing that finding
  into the item is what made the re-dispatch pass first time.
  Root cause filed as `bd-ib-hote` (P1, orchestrator tenant): review findings
  are never propagated into the disposition stage's prompt.
- **Always dispatch with `--json`.** Three plain runs reported nothing but
  `status: failed`; only the `--json` run surfaced the stale-build stderr that
  explained four consecutive refusals.
- **`ACTIVE` is never evidence of a run, and neither is a `runnable` one.**
  Confirm a run reaches `running`; a queued run can be evicted without ever
  executing and leaves an identical-looking claim.

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

- **MTIME IS NOT RELEASE ORDER — the dispatch wrapper resolved a STALE build
  and refused four dispatches before anyone read its stderr.** Measured
  2026-08-03T08:12Z. `tmp/overseer/foreman/dispatch.sh` picked "the current
  build" as the newest cache directory by mtime. That premise is false: a
  cache directory's mtime moves whenever anything touches it, so the cache
  sorted

  ```
  1785744577  0.50.0        <- newest mtime, not a dispatcher build at all
  1785742178  18e482f85b9f  <- newer mtime, OLDER release  (what it picked)
  1785732282  525886a4f799  <- older mtime, CURRENT release (what was needed)
  ```

  Every `impl:overseer-z5fo4y.2` and `.4` dispatch was refused with exit 3 and
  the message `dispatcher plugin build is stale; executing build 18e482f85b9f
  predates latest release 525886a4f799`. **Only the `--json` run captured that
  stderr** — the three plain runs reported nothing but `status: failed`, which
  is why the cause went unread. Always dispatch with `--json`.

  The wrapper now asks the AUTHORITY instead: it parses the build id out of
  `just ensure-plugins` output — the same release the dispatcher's staleness
  gate compares against — and HALTs rather than falling back to mtime.
  Positive and negative controls were run before use. The old idiom also used
  `ls`, which is aliased to `lsd` on this host, a second reason it could not
  be trusted.

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
