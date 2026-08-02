# release-automation-gap — handoff

Epic anchor: **`overseer-oijk3d`**. Read status from the ledger, never from
this file — nothing here stores a status or a checkbox queue.

## Read-first chain

1. This file.
2. `plan/release-automation-gap/research/how-the-gap-was-found.md` — why the
   defect was invisible for days, and the reasoning that is expensive to redo.

That is the whole chain. Everything else is in the ledger.

## Scope: BOTH defects, despite the slug

The slug reads narrower than half this thread's content. That is deliberate —
the maintainer chose it — so the scope is stated here instead:

| item | what | route |
|---|---|---|
| `overseer-sf0` | P1 — this repo is the ONLY fleet repo missing `.github/workflows/auto-enable-merge.yml`, so release PRs are never armed for auto-merge and park forever | **factory-INELIGIBLE**, see below |
| `overseer-dtl` | P1 — the `Release tag` gate has failed on EVERY release since 2026-07-30 and three shipped over it; the daily canary flagged it unheeded | factory dispatch |
| `overseer-zxy` | P2 — re-verify the archived Codex-parity evidence at `--ref release`, now that `origin/release` carries the launcher at 0.16.0 | factory dispatch |

`overseer-dtl` is not an "automation gap" at all — it is seven files over an
LLOC soft ceiling. Do not treat it as off-topic; it is the same condition seen
from the other side.

**The common condition:** this repo's release train runs unattended and nothing
notices when it breaks. One half has no actor to press merge; the other half has
an actor shouting daily into a void.

## Next action

Compose current status first:

```bash
/livespec-orchestrator-beads-fabro:next --json
```

Then work the ripe item. Both `sf0` and `dtl` are P1 and independent — either
order is defensible; `sf0` is recommended first because it is the one that
stops a human having to press merge by hand.

### `overseer-sf0` — FACTORY-INELIGIBLE, implement in-session

This item is **explicitly recorded as factory-ineligible** and is the enumerated
exception to this thread's dispatch routing. Its fix creates
`.github/workflows/auto-enable-merge.yml`, and the factory branch boundary is
absolute: *"Factory branches never create/update files under
`.github/workflows/`."* **A dispatched run will silently DROP the only file that
matters and report success.** Implement it locally through the normal
worktree → PR → rebase-merge path.

Port the workflow from `thewoolleyman/livespec` (or `livespec-dev-tooling`).
Both required secrets — `APP_ID` and `APP_PRIVATE_KEY` — **already exist in this
repo**, set 2026-07-21, so this is not a credentials project.

**Acceptance is LIVE, not file presence.** A workflow that exists but never
fires is the vacuous-green shape this repo keeps rediscovering. The bar is: the
NEXT release-please PR reaches `MERGED` with `mergedBy == app/livespec-pr-bot`,
with no human or agent pressing merge.

### `overseer-dtl` and `overseer-zxy` — factory dispatch

```bash
/livespec-orchestrator-beads-fabro:drive --action impl:<id>
```

or let the Dispatcher drain `ready`. Do **not** use the in-session Red→Green
driver for these.

On `dtl`, the constraint is on the item and is not negotiable: **do not raise
the ceiling, unset the lever, or exclude the files.** That converts a working
detector into one that cannot fail and ratifies three releases' worth of drift.
`overseer/_supervisor_evaluate.py` sits at exactly 250 — the HARD ceiling — and
is the most urgent.

## Standing constraints

- Never pass `--no-verify`; halt and report on hook failure.
- Every tracked-file change goes worktree → PR → rebase-merge; never commit on
  the primary checkout. `just worktree-create` was 9/9 broken under load on
  2026-08-02 — use `git worktree add` + `just install-worktree-pack`, then
  discard the `worktree_discipline` key it writes into `.livespec.jsonc`.
- Verify against the FORGE after a fetch, never a possibly-stale working tree.
- Never kill, stop or restart the acting overseer daemon (tmux
  `livespec-overseer:1.1`).
