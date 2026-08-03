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

## Restart checkpoint — 2026-08-03, nine-proposal revise payload READY

Tasks 03 and 04 completed the PREPARATION for the ratification pass. They did
not run revise, commit the spec changes, push, or open a PR.

The owned worktree is:

```text
/home/ubuntu/.worktrees/livespec-overseer/spec-revise-v005
branch: spec-revise-v005
```

Its intentional working state is five modified tracked files plus the
untracked payload:

```text
SPECIFICATION/spec.md
SPECIFICATION/contracts.md
SPECIFICATION/constraints.md
SPECIFICATION/scenarios.md
tests/heading-coverage.json
tmp-revise-input.json
```

The ratification payload is
`/home/ubuntu/.worktrees/livespec-overseer/spec-revise-v005/tmp-revise-input.json`
(SHA-256
`b8e87e29081506307e5ab2b1694a24e18474da3ef92f8a9ec3ff6b70d422bf8c`).
It contains all nine decisions in the required cumulative order: six
`modify`, three `accept`, zero reject. Every `resulting_files` entry carries
complete post-edit file content, not a diff. Paths are relative to the
configured `SPECIFICATION/` target (`spec.md`, not
`SPECIFICATION/spec.md`); the installed v0.21.4 validator rejects the latter.

Two defects in the assessment were caught and repaired under an explicit
foreman ruling: its new MUST clauses lacked their required scenario halves.
The payload therefore includes, and calls out in the affected
`modifications` fields:

- `## Scenario: A missing supervisor role layer halts the binder with a
  remedy` — absent `.ai/supervisor-protocol.md` makes the binder guard halt
  and emit a labelled remedy.
- `## Scenario: A foreman uses the canonical name on both identity surfaces`
  — both tmux and runtime-registry names are `<repo-slug>-foreman`; a
  different name on either surface is unauthorized.

Neither scenario required choosing anything the clauses did not settle: no
new threshold, ordering, actor, fallback, or error path. Their
heading-coverage entries deliberately use `test: "TODO"` because no
integration-tier test exists yet; no test id was fabricated.

Verification is already GREEN: Draft-07 schema validation against the
installed `revise_input.schema.json`; proposal/path existence; exact
order/counts; in-memory sequential replay from HEAD to byte-identical final
working files; scenario introduction at decisions 3, 8, and 9; `git diff
--check`; JSON parsing; and `just check-heading-coverage`. The full aggregate
was deliberately not run per the loaded-host rule below.

Forge was last fetched at `origin/master` `20f04e8`. The worktree branch was
four commits behind, but `git diff HEAD..origin/master -- SPECIFICATION
tests/heading-coverage.json` was empty: none of those upstream commits touched
the payload's targets. Re-fetch before acting. Preserve the dirty worktree and
payload while satisfying the revise lifecycle's stale-branch gate; do not
reconstruct or reword the payload.

**Immediate next action after restart:** resume the `/livespec:revise`
lifecycle in that worktree using exactly `tmp-revise-input.json`, inspect the
resulting v006 history/revision artifacts, run the lifecycle-required focused
verification, and land the ratification through the normal worktree → PR →
rebase-merge path. Only after v006 lands, re-measure the ledger and proceed to
the approval/dispatch valves for `.1`–`.5` described below.

## Where the thread stands — derive live status from the ledger, not this file

Filed status is a claim with a timestamp; re-measure before acting:

```sh
/usr/local/bin/with-livespec-env.sh -- bd show overseer-z5fo4y --json
ls SPECIFICATION/proposed_changes/
```

(a bare `bd` in this repo returns Access denied — the wrapper is required).

**As re-measured 2026-08-03**, superseding the 2026-08-02 filing below:

- The epic is `backlog`; children `.1`–`.5` and the coverage task
  `overseer-n7xx67` remain `pending-approval`.
- **`overseer-jgqw7d` is CLOSED**, factory-implemented and merged as
  `7eb7484` (PR #531). `.5`'s only dep edge is therefore satisfied.
- **The slices carry REAL dep edges**, not merely practical ordering: `.2`
  is blocked by `.1`, and `.3` by `.2` by `.1`. A dep tree is directional —
  querying `.1` reports what blocks `.1`, never what `.1` blocks.
- **NINE proposed changes pend, not six.** The six foreman proposals
  (PR #495) plus two that predate this thread
  (`gap-invisible-clauses-to-must-form`,
  `supervise-plan-authors-two-layers`, both 2026-07-30) plus
  `fail-soft-render-prohibition-scenario` (PR #538, `fdc4018`), which is
  `overseer-n7xx67`'s landing path. `/livespec:revise` is
  DIRECTORY-scoped, not thread-scoped, so a pass walks all nine.
- **`SPECIFICATION/history/v005/` already exists** and is NOT this thread's:
  the `supervisor-wrapup-citizenship` track ratified its own proposal at
  `cc90899` on 2026-08-03. This thread's pass therefore produces **v006**,
  and that ratification EDITED `spec.md`, `contracts.md`, `constraints.md`
  and `scenarios.md` in regions several of the nine target. Re-verify every
  anchor against current master before applying any proposal's wording.

As filed on 2026-08-02 (retained for provenance): all seven ledger items
were `pending-approval` and the six spec-side proposed changes were filed
in PR #495. Valve driving is a ratified HUMAN act (review finding C1) — but
SURFACING every ripe valve is THIS THREAD'S FIRST TASK, not a thing the
maintainer must remember: a decision the maintainer has not been shown is a
stall of this thread's own making.

## NEXT ACTION — execute the prepared revise payload; the picker is DISCHARGED

FIRST, in the resuming session's opening turns: re-fetch, verify the prepared
worktree and payload against the checkpoint above, then re-measure the ledger
and `SPECIFICATION/proposed_changes/` (the commands above). Do not repeat the
assessment or rebuild the payload unless live target bytes actually changed.

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

The valves, with what became of each:

1. ~~**Approve + dispatch `overseer-jgqw7d` now**~~ — **DONE 2026-08-03.**
   Approved, factory-dispatched, merged as `7eb7484` (PR #531), item
   CLOSED. The merged refusal has no live fleet effect: zero plan topics
   across all twelve watched repos end in a reserved suffix, live or
   archived. It is a latent guard.
2. **Run the `/livespec:revise` walk-through** — now over **nine**
   proposals, not six, and producing **v006**. Decision prep exists: read
   `tmp/overseer/foreman/assessment-proposals.md` (gitignored scratch, so
   re-derive it if absent) before opening the pass. It verified every
   proposal's anchors against the real spec text and the 33 binding review
   dispositions and returned **3 ACCEPT / 6 ACCEPT-WITH-MODIFICATION / 0
   REJECT**, with exact replacement wording and a required application
   order whose two hard textual constraints are:
   `gap-invisible-clauses-to-must-form` must precede
   `reserved-suffix-refusal`, and `supervise-plan-authors-two-layers` must
   precede `unattended-reader-carve-out`.

   Four of the six modifications are substantive rather than editorial, and
   two of those are safety-relevant: `attention-ownership-superset`
   specifies a heartbeat schema missing the `tick_generation` field slice
   `.4` requires (ratifying as-written makes `.4` unimplementable against
   its own spec), and `foreman-scope-governed` forbids the foreman only
   four named human-valve verbs where binding finding C1 covers the entire
   class — leaving policy edits, caps and move apparently permitted to an
   unattended component. `unattended-reader-carve-out` proposes a scenario
   permitting a pane answer to a BLOCKED track, contradicting ratified
   "never restarted, never keystroked".

3. **Approve slices `.1`–`.5`** (post-ratification) and optionally
   `overseer-n7xx67`. Respect the ledger dep chain: `.1` → `.2` → `.3`.
   `.1` needs BOTH `status-snapshot-store` and the `spec.md` scope half of
   `foreman-scope-governed`; `.4` needs `attention-ownership-superset` plus
   `unattended-reader-carve-out` for its heartbeat home; `.5` needs only
   `reserved-suffix-refusal` now that `overseer-jgqw7d` is closed.

On each approval answer, EXECUTE it in the same session: the corresponding
`drive.py --action approve:<id>` then the dispatch
(`drive.py --action impl:<id>`, or the Dispatcher drain) — approval
expressed by the maintainer in the picker IS the human act; running the
command is mechanics. A declined valve is recorded here and NOT re-raised
until its inputs change. Implementation of every ledger-backed slice is
FACTORY-SIDE — the dispatch route is THE implementation path; none of them
is factory-ineligible, so none is implemented inline. The two dispatch
traps recorded in the repo-root `.claude/CLAUDE.md` §"Two dispatch traps"
apply verbatim.

(The previous next action — filing the six proposed changes — is DONE, PR
#495. Do not re-file; a same-topic re-run mints `<topic>-2.md` collisions.)

## Standing hazard — live until `.5` lands, and NARROWER than it first read

`plan/foreman/` is a discovered plan topic in a watched repo. Adoption
matches live sessions' REGISTRY names against discovered topics, so a
session registry-named `foreman` in this repo WILL be adopted as this
thread's worker — wrapped up at threshold, nudged when idle, and
respawn-able into this handoff.

**That is about a foreman PROTOTYPE, not about this thread's own worker.**
Adoption keys on EXACT equality (`overseer/_supervisor_discovery.py` sets
`topic = name` and requires membership in the active-topic set), so a
worker session named `foreman` working THIS plan thread is adopted exactly
as intended — that is the daemon managing its own track, not a hazard. One
has run under this handoff since 2026-08-03. A foreman PROTOTYPE is the
thing to avoid: it must be registry-named `<repo-slug>-foreman`, and even
that is only safe after `.5`'s adoption refusal lands.

**A trap `.5`'s implementation must not walk into.** The shipped mechanism
is `signals.topic_reserved_for_supervisor`, i.e.
`topic.lower().endswith("-supervisor")`. The bare topic `foreman` does NOT
end in `-foreman`, so this thread's worker is safe under a HYPHENATED test
— but a hyphen-less `endswith("foreman")` would orphan the very worker
supervising this plan. Separately, `tmux_id`'s collision branch derives the
repo-qualified `livespec-overseer-foreman`, which DOES end in `-foreman`
and which `.5` refuses by design; that is latent today (measured
2026-08-03: no watched repo but this one holds a `plan/foreman/`) and goes
live the moment a second one does. Both belong in `.5`'s beside-tests.

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
