# Plan — daemon-liveness-truth

## What this thread is

The overseer daemon's view of whether a track is alive disagrees with reality, in
**both directions**. Two defects, observed independently, that are the same defect
in mirror image:

- a **live**, working, in-tmux track is reported as **session-gone**
  (`overseer-j1r`);
- a **deliberately torn-down** track is reported as **hung mid-wrap-up**
  (`overseer-mkx`).

One raises a false alarm about a session that is fine; the other raises a false
alarm about a session that no longer exists. Both erode the same thing — an
operator's ability to trust the display — and an operator who learns to discount
one will discount the other.

Ledger anchor: `overseer-x29` (epic). Both items are its children.

## Why this is NOT the supervisor-prompt-quality thread

That thread is about **the quality of what the generator emits** — whether a
defect in an emitted charter can be caught mechanically instead of by a supervisor
noticing. These two are about the **daemon's runtime model of session liveness and
state**. They surfaced during that thread only because it was the thread driving
sessions hard enough to hit both. The subject matter, the code
(`_supervisor_state.py`, `_supervisor_nudge.py`, discovery) and the fix shape are
all different. Filing them under the prompt-quality epic would have made that epic
mean "whatever the supervisor tripped over", which is how an epic stops being a
cut.

## The root they probably share — examine this first

Discovery keys on the **plan directory existing**, not on session liveness, so a
track stays discovered whether or not any session backs it — and its **last
written declaration keeps speaking for it indefinitely**.

There is no session token meaning *"complete, parked, nothing wanted"*. A
finishing session must choose among tokens that each decay wrongly:

| token | how it decays |
|---|---|
| `ready` | authorises an unwanted restart — the only token that does |
| `idle-with-context-left` | forges a marker the DAEMON owns, not a session |
| `blocked` | alerts forever on widening bands, loudest when all is well |
| `winding-down` | decays into a false hung-session alarm |

That vocabulary gap is the likely common cause. A fix that adds the missing
terminal token may close both children at once; a fix that patches each symptom
separately will not.

## What is already measured — do not re-derive

- `_supervisor_nudge.py:145` documents a stale `winding-down` as *"it DID
  acknowledge, then never finished"*. That is the mechanism behind `overseer-mkx`.
- `_supervisor_state.py` **already has** state-file cleanup —
  `signals.state_path(...).unlink(missing_ok=True)` at lines 42 and 116 — so the
  daemon knows how to void a declaration that no longer describes reality. Those
  paths simply do not fire for a teardown, because teardown is a supervisor action
  outside the daemon's loop.
- Observed cost, 2026-07-30: a torn-down track rendered as dead-and-not-working
  and the maintainer had to ask what had happened. The state file had been stale
  for **327 minutes**.

## Acceptance shape, for both children

Demonstrate the **RED**, with a control proving the fix did not simply silence
everything:

- tear a tracked session down deliberately → the display must NOT report it as
  hung mid-wrap-up, **and** a genuinely hung wrap-up must STILL be reported;
- run a live in-tmux track under a derived session name → it must NOT report
  session-gone, **and** a genuinely absent session must STILL be reported.

A fix that silences both halves is worse than the defect, because it removes the
alarm that the whole supervision contract rests on.

## Discipline

Fleet-standard: worktree → PR → rebase-merge, never commit on the primary
checkout. Create worktrees with `just worktree-create`, never raw
`git worktree add`. Never `--no-verify`; halt and report on hook failure. Never
kill the acting overseer daemon in tmux `livespec-overseer:1.1` — it supervises
every tracked session in the fleet, and this thread's subject makes it especially
tempting to restart it while testing. Do not.

**`bd` needs the fleet credential wrapper here** — a bare `bd` returns
`Access denied`. Use `with-livespec-env.sh -- bd …`, or detect it.

**`date -u -r <file>` does NOT apply `-u` on this host** (uutils coreutils, not
GNU): it prints LOCAL time and the `Z` you append is a lie, a silent two-hour
error. Read mtimes through `datetime.fromtimestamp(ts, timezone.utc)` when the
value enters a claim. This cost the sibling thread a false accusation against a
colleague's work; see charter correction C19.
