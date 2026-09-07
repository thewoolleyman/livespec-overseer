# foreman-actuator-gather-and-roster — opening research

Thread opened 2026-08-23 at the maintainer's direction, by promoting the existing
carrier epic `overseer-tdfe` into a full plan thread. The epic is not new; what is new
is that it now has a plan directory, a scope event, a handoff timeline and an archive
gate.

## Why this thread exists

`overseer-tdfe` was created 2026-08-23 as a **carrier epic** — deliberately not a plan
thread — to hold measured defects in the foreman's own executable surfaces as
`plan/foreman-improvements` archived. Its own text said so: "CARRIER EPIC, NOT A PLAN
THREAD. No plan directory, no scope event, no archive gate."

That was a reasonable holding pattern and it has been outgrown. Measured 2026-08-23:

| | count |
|---|---|
| children | **87** |
| open | **67** |
| closed | 20 |

Open children break down as 20 `ready`, 18 `pending-approval`, 14 `blocked`, 14
`backlog`, 1 `active`.

**The carrier has become the thing it replaced.** `plan/foreman-improvements` was cut up
on 2026-08-22 precisely because it "held 38 open children with exactly three real blocks
edges among them: a junk drawer of decoupled work". Its successor now holds 67. The
failure repeated in under two days, at nearly twice the size, which is the strongest
available evidence that a carrier without an archive gate does not stay small on its own.

This was already noticed from inside: `overseer-tdfe.10` (P1, ready) reads "Work on the
tdfe carrier epic has no mechanical advocate: 60 open children..." — filed while the
count was still 60. That item's premise is this thread's premise.

## What promoting it to a plan actually changes

A carrier epic and a plan anchor differ in exactly the properties that let a junk drawer
form:

- **Archive gate.** A plan refuses to archive while any child is undisposed, and requires
  independent completeness-review evidence. A carrier has neither, so nothing ever forces
  a reckoning with its backlog.
- **Scope event.** A plan records requirement carriers and explicit deferrals before
  implementation children are admitted. A carrier admits anything that fits its prose
  description, which is how 87 children accumulate.
- **Handoff timeline.** A plan's state is a ledger-held timeline on the epic, readable by
  a fresh session with no chat history. A carrier's state is whatever its child list
  happens to look like.
- **A worker seat.** A plan thread is driven by a session named for its slug and tracked
  by the daemon. A carrier is driven by whoever happens to notice it.

## The tension this thread must resolve first

The epic's own description forbids what is now being done to it: "no new plan", "Do not
add scope". Those sentences were written for a carrier and are now false of the record
they sit on.

**Leaving them would reproduce the exact defect this session spent its day chasing** — a
record whose text contradicts its own state, which a reader trusts. Two instances were
measured this week: `overseer-lixhd3` deferral D3 and `overseer-6tfncs.5` criterion 8
each disclaimed foreman self-restart while citing the other, so a reader of either
concluded it was covered and nobody owned it (`overseer-5e5a`); and
`.claude-plugin/prose/foreman.md` forbade a blocking-picker escape that
`SPECIFICATION/spec.md` still ratified, which deadlocked a four-hour factory run.

So the promotion is not complete until the epic's own description and acceptance are
rewritten to describe a plan thread. That is a requirement carrier below, not a tidy-up.

## What this thread does NOT take on

It does not re-cut the 67 open children. Promoting the anchor is a governance change;
deciding which children belong together is a grooming pass, and doing both at once would
make neither reviewable. The cut is named as an explicit deferral with the item that
should drive it.

## Read first

- `overseer-tdfe` — the epic being promoted, and its carrier-era description.
- `overseer-tdfe.10` — the mechanical-advocate gap, filed from inside the carrier.
- `plan/archive/foreman-improvements` — the predecessor junk drawer and the commit that
  cut it up (`b24b8d1`, "cut three cohesive threads out of the foreman junk drawer").
- `overseer-5e5a` — the circular-disclaimer failure this thread must not reproduce.
