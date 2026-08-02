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
```

(a bare `bd` in this repo returns Access denied — the wrapper is required).
As filed on 2026-08-02: the epic is `backlog`; children `.1`–`.5` and the
independent defect `overseer-jgqw7d` (`tmux_id` refusal gap — `.5` depends
on it) are all `pending-approval`, awaiting the maintainer's `approve`
valve. Valve driving is a ratified HUMAN act (review finding C1): surface
ripe valves to the maintainer; never drive them from this thread.

## NEXT ACTION

File the spec-side proposed changes enumerated in `research/brainstorm.md`
§4 ("Spec-side, enumerated") against THIS repo's `SPECIFICATION/` via the
`/livespec:propose-change` operation — one proposed change per amendment
topic (the snapshot store joining the closed three-file enumeration; the
attention-ownership sentence; both §Surface-only startup sentences; the
§Non-interference unattended-reader fork; the scope-statement fork; the
session-name derivation refusal). File all six in ONE PR — each is its own
`SPECIFICATION/proposed_changes/<topic>.md` file, and acceptance is
per-file at the next `/livespec:revise` pass, so a single landing loses no
granularity. Slices `.1` and `.4` state this ratification as their
precondition, so it is the critical path.

After that: slices approved by the maintainer are implemented FACTORY-SIDE —
the dispatch route (`drive.py --action impl:<id>`, or the Dispatcher drain)
is THE implementation path for every ledger-backed slice in this thread;
none of them is factory-ineligible, so none is implemented inline. The two
dispatch traps recorded in the repo-root `.claude/CLAUDE.md` §"Two dispatch
traps" apply verbatim.

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
