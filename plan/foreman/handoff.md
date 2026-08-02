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

## Where the thread stands — derive live status from the ledger, not this file

Filed status is a claim with a timestamp; re-measure before acting:

```sh
/usr/local/bin/with-livespec-env.sh -- bd show overseer-z5fo4y --json
ls SPECIFICATION/proposed_changes/
```

(a bare `bd` in this repo returns Access denied — the wrapper is required).
As filed on 2026-08-02: the epic is `backlog`; children `.1`–`.5`, the
independent defect `overseer-jgqw7d` (`tmux_id` refusal gap — `.5` depends
on it), and the coverage task `overseer-n7xx67` are all `pending-approval`,
awaiting the maintainer's `approve` valve. The six spec-side proposed
changes are FILED (PR #495, 2026-08-02) and pend in
`SPECIFICATION/proposed_changes/` awaiting `/livespec:revise`. Valve
driving is a ratified HUMAN act (review finding C1) — but SURFACING every
ripe valve is THIS THREAD'S FIRST TASK, not a thing the maintainer must
remember: a decision the maintainer has not been shown is a stall of this
thread's own making.

## NEXT ACTION — open with the batched valve picker, then execute the answers

FIRST, in the resuming session's opening turns: re-measure the ledger and
`SPECIFICATION/proposed_changes/` (the commands above), then raise ONE
batched `AskUserQuestion` to the maintainer carrying EVERY ripe valve, each
option stating its cost, recommended option first, full repository names,
one call batching every ripe valve rather than a trickle, and a `---` final
line before the picker (these are `.ai/supervisor-protocol.md`'s picker
rules, restated here so this file stays self-sufficient):

1. **Approve + dispatch `overseer-jgqw7d` now** — it needs NO spec
   ratification (it fixes an existing spec-vs-impl gap) and unblocks `.5`.
   Recommended yes.
2. **Run the `/livespec:revise` walk-through** on the six foreman proposals
   (each carries a composition note; `.1`/`.4`/`.5` wait on ratification of
   `status-snapshot-store`, the attention amendments, and
   `reserved-suffix-refusal`). This operation is itself interactive —
   per-proposal accept/modify/reject stays with the maintainer.
3. **Approve slices `.1`–`.5`** (post-ratification) and optionally
   `overseer-n7xx67`.

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

## Standing hazard — live until `.5` lands

`plan/foreman/` is a discovered plan topic in a watched repo. Adoption
matches live sessions' REGISTRY names against discovered topics, so a
session registry-named `foreman` in this repo WILL be adopted as this
thread's worker — wrapped up at threshold, nudged when idle, and
respawn-able into this handoff. Do not run one. A foreman prototype session
must be registry-named `<repo-slug>-foreman`, and even that is only safe
after `.5`'s adoption refusal lands.

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
  `.livespec.jsonc` unless you mean to land it.

## Discipline

Fleet-standard: worktree → PR → rebase-merge; never commit on the primary
checkout; never `--no-verify`; `mise exec -- git …` so hooks fire. Check
`git status`, not `git log`, after a hook-gated commit. Never kill the
acting overseer daemon (tmux `livespec-overseer:1.1`) — its blast radius is
the whole fleet. Beads only via the fleet credential wrapper. This thread
FILES ripe work and routes spec matter to the spec lifecycle; it does not
hand-code implementation inline.
