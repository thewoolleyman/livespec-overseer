# Completeness-review brief — epic `overseer-hgq4wi`

**For the reviewer commissioned under archive gate leg 2.** This file exists
because the epic's ledger record is roughly **320 KB across 74 append-only
comments**, of which **54 are handoff entries that mostly supersede one
another** — a linear read is the enemy of a careful review, and most of what a
linear read costs you is retired state. This is a starting point, not a summary
you should trust: everything below was written by the OWNING thread and is
input to your review, never evidence within it.

Written 2026-08-22 by the owning plan session. Tally at writing: **67 of 79
children closed.** The thread is NOT ready for archive — see "what is not done".

## What you are certifying

The epic's acceptance names four legs, and they govern; nothing here supersedes
them. Leg 2 is the one you are performing. The thread's SUBJECT, against which
completeness is judged, is stated in its title: make this repo's test rig
**hermetic**, and its enforcement gates **non-vacuous, non-flaky, and armable**.

The scope event of 2026-08-19 cut that into three strands, and they are the
right axes for a completeness question:

1. **Hermeticity** — the test rig damaging production state (the suite writing
   the real `~/.livespec-overseer-status.json`; a test lacking `TMUX_PANE`
   isolation; the real-tmux rig leaking a socket per test and never reaping).
2. **Gates that cannot fail** — a required gate passing vacuously when its path
   moves; a warn-instead-of-fail alignment check; a blocking review that was
   decoration; a coverage gate adopting foreign data.
3. **The Result railway and coverage debt** — including whether the ROP check
   can be armed here at all.

## Where the substance lives, so you need not read the timeline

- **The two `plan-scope-event` comments** carry the strand cut and, importantly,
  the **explicit deferrals** — daemon-behaviour changes to `overseer-6tfncs`,
  fleet plumbing to `overseer-cajdwp`, and the arming of the heading-coverage
  lever until two named children land. Deferrals are where a completeness review
  most often finds a gap, and these are stated rather than implied.
- **The seven `plan-child-disposition` comments** are the closes that carry
  reasoning rather than a merge sha. Two are worth reading in full: the
  `overseer-hgq4wi.40` disposition (a duplicate the thread filed and then closed
  on itself, with the irony recorded as evidence of a structural dedup gap), and
  the `overseer-hgq4wi.39` disposition (an owner-tier close, plus a correction
  where this thread propagated a stale claim through two of its own handoffs).
- **The latest handoff entry only.** Each supersedes the one before and says so
  in its first line. Reading older ones tells you what was believed at the time,
  which is occasionally interesting and never authoritative.

## What the owning thread already did — and why it is not your evidence

This thread verified its own dispatched work rather than accepting green
verdicts, and the verification method is the part most worth auditing, because
if the method is weak then so is everything it certified:

- For split work it diffed the **sorted set of test names** before and after
  (`.43`: 19 and 19, character-identical) and, for a facade split, imported the
  module to confirm every `__all__` name resolves (`.44`).
- For a new guard it re-ran the **discrimination** itself rather than trusting
  the commit message that claimed a mutation check (`.45`, five mutations;
  `8nxb`, one). In `8nxb` the mutation made the guard fall back to the exact
  false message the item was filed about.
- For `.39` it measured both named instances rather than inheriting them.

**None of that is evidence in your review.** It is the thread grading its own
homework, and it is offered so you can attack the method, not so you can skip it.

## Known limits, stated so you do not have to find them

- **The census figures in `overseer-awec` disagree between instruments** — 15
  originally, 59 on a re-census, 68 on a third. The clause COUNTS agree where the
  instruments overlap; the POPULATION does not. No figure here should be treated
  as settled.
- **`overseer-jdo`'s entire statistical baseline predates a fix to one of its own
  named mechanisms.** Recorded on that item. Its sighting ledger is a repo file,
  and its runs explicitly do not count toward its acceptance.
- **The thread measured merge-race EXPOSURE, not incidence** (`.33`): tight merge
  gaps are necessary but not sufficient for the race, so those figures bound the
  opportunity only.
- **One probe technique in `awec` was found unsound** (a single-file mutation is
  always red on the carrier mirror) — which means any earlier reasoning that
  assumed the documented technique worked should be re-read with that in mind.

## What is NOT done, so completeness is judged against the right set

Twelve children remain open: four blocked on a cross-repo resolver
(`livespec-dev-tooling-x7ml`) or on a ratification, four in backlog needing a cut
or a design call (`zc53`, `awec`, `bjrm`, `jdo`), one maintainer-tier decision
(`.33`), one pending-approval, one ready, one active. **A completeness review
should not certify the thread as finished; it should certify whether the strands
are the right set and whether anything in scope is unaccounted for.**

## The question worth asking that the thread cannot ask itself

**Are the three strands the right cut, and is "gates that cannot fail" pinned at
the right level?** The thread has closed a large number of individual vacuous
gates, and it has repeatedly rediscovered the same shape in new places — in a
test's own Red leg, in a probe technique, in a conformance surface shipped this
week, and in the plan-records gate that turns out to check **zero live plans**.
A reviewer should ask whether closing instances one at a time is completeness, or
whether the thread's real finding is that this repo manufactures this shape
faster than it retires it — and if so, whether anything in the thread's scope
addresses the manufacturing rather than the instances.

A second question, narrower and concrete: **this epic's own leg 3 may be
unsatisfiable as written.** It requires the thread's handoff to declare the epic
as its ledger anchor "in the literal form the anchor gate's regex requires", but
that regex is applied to a `handoff.md` file, and this thread is ledger-held —
`plan/test-and-gate-integrity/` contains only `research/`. Measured 2026-08-22:
19 live plan directories, zero with `handoff.md`, zero with
`supervisor-handoff.md`. That is recorded on `overseer-vsavoe`, and it needs an
owner ruling before archive rather than a discovery at the gate.
