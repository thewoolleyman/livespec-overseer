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

## THIRD CHILD, ADOPTED 2026-08-02: `overseer-oydugu` — rung 3

`supervisor-prompt-quality` ARCHIVED on 2026-08-02 and this slice moved here at
maintainer direction. It is `blocked` / `blocked-reason:needs-human`, and that
verdict is correct rather than an oversight — it needs a human design call before
it can be dispatched.

**What it is.** Nothing anywhere observes a supervisor READING a charter clause
and doing otherwise. The supervision ladder is *static prose → generated output →
observed conduct*; rungs 1 and 2 have executable gates for eleven defect classes,
and **rung 3 has nothing**. This is the first gate for it.

**Why it belongs beside `j1r` and `mkx`, stated honestly.** All three are the
system's MODEL of what is happening diverging from what IS happening — a live
track modelled as gone, a dead track modelled as hung, and supervisor conduct not
modelled at all. **But the mechanism differs and that matters for whoever picks it
up:** `j1r` and `mkx` are the daemon's runtime loop; this one is harness/hook
shaped, observing a session's TOOL-CALL STREAM rather than a state file. Do not
assume a fix for one informs the other.

**The evidence, and it is unusually sharp.** The rule chosen as the first target
is the picker rule — every maintainer-facing decision must be an
`AskUserQuestion` call. It is policed by **six of the charter contract's
thirty-one requirements** (`picker-rule`, `picker-recommended-first`,
`picker-option-costs`, `picker-full-repository-names`, `picker-final-line-fence`,
`picker-batch-ripe-valves`); the gate asserting all six is **GREEN**;
`.ai/supervisor-protocol.md` states it in plain words — and on 2026-08-02 a
supervisor raised four ripe valves as prose anyway, after applying the rule
correctly three times in the same session. That is charter correction **C20**.
**A rule's text-enforcement strength says nothing about whether it binds
conduct**, and this is the instance that demonstrates it rather than conceding it.

**THE DESIGN PROBLEM IS THE WHOLE DIFFICULTY — read this before writing any
rule.** A detector keying on "prose + question mark + no picker" flags the
LEGITIMATE ANSWERING turn too: the turn that produced C20 answered a direct
maintainer question in prose, which is correct. **Answering the maintainer is
prose; asking them is a picker; both appear in one turn.** Intent is not reliably
in the text. This is the family that killed four gates on the originating thread —
*the false positive was always data or prose that legitimately RESEMBLES the
defect.* Measure the corpus before writing the rule.

**Acceptance must begin RED, with a control proving it did not flag
everything:** RED against the recorded 2026-08-02 four-valves-as-prose turn;
**GREEN against the recorded answering turn in that same session** (prose,
question marks, no picker, and correct) — that control is load-bearing and a gate
without it must not land; GREEN against the three turns that used the picker
correctly. A sabotage producing no RED is UNVERIFIED, not passed.

**A negative result is an acceptable outcome.** If no discriminator separates
answering from asking, record that and state the advisory ceiling plainly. **Do
NOT weaken the picker rule to make a gate pass.**

**Its epic edge is PROSE-ONLY and that is not an oversight.** `bd dep add
overseer-oydugu overseer-x29 --type blocks` is refused — *"tasks can only block
other tasks, not epics"* — the same constraint this repo already records for the
prompt-quality epic's children. Cite the link; do not go looking for the edge.

## Operational facts inherited from the archived thread — do not re-derive

- **`just worktree-create` is effectively BROKEN in this repo at scale.**
  `worktree-lib.sh:89` pipes `git worktree list --porcelain` into an `awk` that
  `exit`s on the first match, closing the pipe while git is still writing → git
  takes SIGPIPE → `pipefail` propagates 141 → `set -e` aborts before any output,
  so a redirected run leaves an EMPTY log. It worsens as the worktree count grows:
  4-of-8 failures at 56 worktrees, 14 attempts at 63, and on 2026-08-02 at **77
  worktrees it failed 65 CONSECUTIVE times** and never succeeded. Recorded fix is
  one line in `livespec-dev-tooling`'s package source (`livespec-dev-tooling-zi4q`);
  never hand-edit the gitignored `dev-tooling/` copy.
  **THE RESCUE PATH, used successfully:** `git worktree add <path> -b <branch>`
  then `just install-worktree-pack` inside it. That writes a `worktree_discipline`
  key into the TRACKED `.livespec.jsonc`; it only makes the existing default
  explicit, so `git checkout --` it unless you mean to land it.
- **A literal double-brace `just`-interpolation token in a work-item's text makes
  the item UNDISPATCHABLE.** `drive.py` interpolates item text into fabro's
  templated `goal`, so the token is parsed as a fabro template variable, finds no
  binding, and the graph is rejected before any agent runs — leaving a PHANTOM
  `active`/`fabro` claim with no run behind it. `fabro ps` is the evidence, never
  `ACTIVE`. Describe such a construct in words; never write it literally.
- **Confirming a paste by grepping the pane for its text CANNOT WORK** (charter
  C21). Claude Code renders a multi-line paste as `[Pasted text #N +M lines]` and
  a single-line paste inline, so a content grep returns zero on a paste that
  landed. Confirm by the placeholder OR a non-empty prompt line, accept either
  shape, and **re-capture rather than re-sending** — the render lags after both
  `paste-buffer` and `Enter`.
- **zsh does not word-split unquoted expansions** (charter C22), so `set -- $row`
  yields ONE argument. A watcher built that way slept through a green CI run for
  14 minutes and then reported "still not terminal". C14's family: a bash idiom
  that silently does nothing here, failing in the direction that reads as a pass.
- The shared protocol now carries **C1–C22**; `handoff.md`-style count claims in
  any thread are gated by `tests/test_charter_correction_counts_are_current.py`,
  so appending a correction reddens that gate until the stated count is updated.

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
