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

## MEASURED 2026-08-02: THEY DO **NOT** SHARE A ROOT — read this before the section below

**The "root they probably share" section is a HYPOTHESIS, and for `overseer-j1r` it
is wrong.** It was examined first, exactly as instructed, and the measurement went
the other way. Recorded here rather than by editing that section, because its
reasoning is still correct for `overseer-mkx` and the contrast is the finding.

| child | actual root | does the terminal token close it? |
|---|---|---|
| `overseer-mkx` | state-file **lifecycle** — teardown leaves the last declaration speaking for a dead session | **plausibly yes** — the section below stands |
| `overseer-j1r` | **registry-name provenance** — nothing to do with tokens, declarations or discovery | **no** |

**`overseer-j1r` is FIXED — PR #468.** A manually-started Claude AUTO-derives its
registry name from the repo directory (`livespec-overseer-01`,
`"nameSource":"derived"`); a daemon-spawned one receives `-n <topic>` explicitly.
The daemon matched on topic equality in **two** places — the identity gate
(`_supervisor_observe.py:195`, `topic in names`) and its `live-outside-tmux`
softener (`_supervisor_offer.py`, `live.name != topic`) — so a derived name failed
**both**, and the row degraded straight past the informational status to
`session-gone`, the only red status. The softener could only soften cases that had
already matched by name, which are exactly the cases that did not need softening.

**`nameSource` is the discriminator, and finding it was the whole difficulty.** By
NAME alone, our own auto-named track (`repo-01`) and a DIFFERENT topic's session
squatting in a reused window (R2/SF5's `beta`) are indistinguishable — both merely
differ from the topic. Softening both would tell the operator to rename a window
another live track is using. Only the first carries `nameSource: derived`, so the
deliberate-name case keeps reporting the truthful `session-gone` and
`test_claude_name_gate_is_wired_end_to_end_through_the_registry` is left **passing
unchanged**. That test failing was the signal that the first cut was wrong.

**The identity gate is UNTOUCHED** — the fix is a reporting softener, never an act
gate, so R2/SF5's protection against injecting into and then respawn-KILLING a
reused window is exactly as it was.

**Six controls ship with the RED**, per this thread's acceptance shape: a genuinely
absent session, an agent not in the mapped session, an explicitly-named foreign
session, a derived-name agent in a DIFFERENT repo, and a no-keystroke assertion.
Sabotage-verified **against the final artifact** — removing the branch reddens the
RED test alone and leaves every control green.

**A HAZARD THIS COST, worth carrying: `just check` passing locally is not evidence
about the tree you PUSHED.** The full aggregate was green while the test module
still lived in `overseer/`; moving it to `tests/` (required — see below) changed
coverage, and the pre-push hook then **skipped the aggregate on a green-token
match** (*"tree byte-identical to last green check"*), so the post-move tree was
never fully checked locally. CI was its first real run, and it found
`_supervisor_offer.py:177` uncovered. **After moving or renaming a file, re-run
`just check` before pushing — the green token is keyed to the tree, and a move
makes the previous green describe a tree that no longer exists.**

**And a structural rule that is not written down anywhere else:** a change to any
file under `overseer/` REQUIRES a paired change under `tests/**`
(`commit_pairs_source_and_test`). The beside-tests in `overseer/` are themselves
source to that check, so a beside-test alone does **not** satisfy it — the paired
test must live in `tests/`. `tests/conftest.py` puts `overseer/` on `sys.path`, so
a module moves there verbatim with no import changes.

**What remains on `overseer-mkx`** is the token-vocabulary decision, which is a
change to `marker-protocol.md` — the cardinal contract doc — and therefore the
maintainer's, not a worker's. Nothing about mkx was touched.

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
