# Opening research — overseerd release currency

ledger anchor `overseer-6s3pk6`

## The problem, measured 2026-08-21

`overseerd` supervises every tracked session in the fleet. It runs from an
**editable install**: `.venv/lib/python3*/site-packages/__editable__.livespec_overseer-1.19.0.pth`
points at the primary checkout, so `overseerd` imports
`/data/projects/livespec-overseer/overseer/` directly.

**That is worse than staleness.** It is not only that the daemon can be running
old commits — an **uncommitted edit** in the primary working tree is what
supervises the fleet. Anyone mid-experiment in that checkout is editing the live
supervisor.

Measured instance the same day: the running daemon (pid 1169541) started
2026-08-21T02:08:42Z. The consensus-evaluator fix `bd07aff` merged at
2026-08-21T14:04:10Z. The daemon had been running ~12 hours of superseded code,
and nothing surfaced it. It was found only because a supervision seat read the
source from the primary checkout, did not check it against `origin/master`, and
filed a P1 duplicate against code that no longer existed. **The stale daemon and
the stale reader are the same defect wearing two hats.**

`AGENTS.md` already records the mechanism: the daemon "imports `overseer.*` once
at startup and never hot-reloads; whatever the checkout holds at the moment of
import is what runs until the next bounce." The gap is that nothing makes the
next bounce happen.

## The anchor already exists

`.github/workflows/fast-forward-release-branch.yml` fires on `release: published`
and fast-forwards `refs/heads/release` to the released commit. Measured
2026-08-21: `refs/heads/release` = `2f47f01` = `refs/tags/v1.21.0`.

So "the latest released version" is already a single CI-maintained ref. This plan
does not need to invent a resolution rule; it needs to consume one.

## "Released" does NOT imply "green", and this repo proves it

The release-tag lane on this repo failed **93 of its most recent 100 runs** and
went green only at 2026-08-20T08:19:21Z, after a streak of 123 consecutive
failures over sixteen days that nobody noticed. A design that adopts "latest
release" without checking the commit's own required-check rollup would have
propagated a broken supervisor to the whole fleet, automatically, for sixteen
days.

**Currency and correctness are separate gates and both are required.**

## Design constraints this plan must respect

**Fail-open on currency; never fail-closed on supervision.** If the forge is
unreachable, rate-limited, or no green release resolves, the daemon MUST keep
running what it has. A supervisor that stops supervising because it could not
check for an update has traded a small problem for a large one.

**Never re-exec mid-interlock.** `overseer/marker-protocol.md` carries the
cardinal rule: a supervised session is restarted only once it has declared
itself `ready`. The daemon replacing ITSELF is a different act, but doing it
while a session restart is in flight could strand that session between
declaration and respawn. The safe point is a tick boundary with no restart
pending.

**The top pane is part of the contract.** Ratified 2026-08-20: whatever restarts
the daemon must ensure it lands and stays in the TOP pane of the two-pane
overseer session. Measured 2026-08-21 during a manual bounce: `Ctrl-C` does not
merely stop the daemon, it CLOSES ITS PANE, collapsing the layout to one pane and
renumbering the remaining panes so `:1.1` silently retargets the operator pane.
Any automation that assumes the pane survives its own restart will start the
daemon in the wrong pane, or into a pane that no longer exists.

**Rollback must exist.** A release that crashes on start must not crashloop the
fleet's supervisor. The previous runtime must remain on disk and be revertible.

## Why in the daemon rather than the pane

Maintainer preference, and it is also the more robust seat: a pane-side check
only runs when the operator surface is alive and attending, which is precisely
what the daemon exists to stop depending on. The daemon already ticks on a timer
and already writes a status snapshot every tick; the currency check is one more
thing it does at a boundary it already has.

The bootstrapping objection — code cannot replace itself while running — is
answered by `os.execv`: resolve and install the new runtime, then exec it,
replacing the process image in place while keeping the pane, the pid's terminal,
and the file descriptors.

## Open question the plan must decide, not assume

Whether the daemon runs from a **daemon-owned runtime prefix** (a non-editable
install of the release, isolated from the working tree) or from the primary
checkout pinned to `origin/release`. Only the first actually satisfies "local
primary changes cannot break it" — the second still exposes the daemon to
uncommitted edits in the tree it imports from. The research recommendation is the
isolated prefix; the plan owns ratifying it.
