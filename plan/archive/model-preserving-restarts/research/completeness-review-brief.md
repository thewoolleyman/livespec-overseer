# Completeness-review brief — epic `overseer-bc55wx`

**For the reviewer commissioned under archive gate leg 2.** This file exists
because the epic's ledger record is roughly 364 KB across 94 append-only
comments, and a linear read of it is the enemy of a careful review. This is a
starting point, not a summary you should trust: everything below was written by
the OWNING thread and is input to your review, never evidence within it.

Written 2026-08-22 by the owning plan session, after leg 1 closed.

## What you are certifying

The epic's own acceptance names FOUR PROPERTIES and TWO HARD CONSTRAINTS. They
are at the top of the ledger record and they govern — nothing in this file
supersedes them. In brief:

1. a restart re-asserts the recorded launch PROFILE, not a bare model string
2. the two regressions are EACH proven by a test that fails against pre-fix
   behaviour — a downgraded cloud session, and a local-LLM track converted to
   the cloud provider
3. the profile is READ from the live session, captured at adoption AND
   re-checked at wrap-up, so a mid-session switch is honoured
4. fail-soft is preserved — a row WITHOUT the field behaves exactly as today

Constraints: no token values ever reach the mapping store, and the cardinal
rule plus all authorization machinery are untouched (this epic changes WHAT is
launched, never WHEN).

## Where the substance lives, so you need not read the timeline

Ledger comments worth reading, by timestamp, all 2026-08-22: `12:38` (the last
child's verification), `12:44` (leg 1 lifted), `13:51` (the property dossier),
`13:57` (property 3), `15:02` (the operator exposure picture), `16:06` (the
unknown rows). A `READER'S INDEX` comment near the end of the record lists
these with the corrections that override earlier text.

In-repo, and more reliable than any comment:
`method-rules-this-plan-paid-for.md` beside this file, and the code and tests
themselves, which are the final word.

## What the owning thread already did — and why it is not your evidence

Each of the four properties was given a NEGATIVE CONTROL: the relevant
behaviour was deliberately removed in a throwaway worktree and the suite
re-run, to show which tests actually catch it. Summary of what reddened:
dropping the recorded model reddens 2 tests including an end-to-end scenario;
ignoring the recorded wrapper reddens 3; making the no-profile relaunch name a
model reddens 2; disabling the wrap-up re-check reddens 4.

**Treat that as a claim, not a result.** It was produced by the thread whose
work you are reviewing. If you re-run any of it, re-run the controls rather
than the assertions — a passing suite tells you much less than a sabotage that
fails to redden anything.

## Known limits, stated so you do not have to find them

- The exposure figures in the ledger are a JOIN between a mapping store and a
  live process list, through tmux session names, which are mutable handles.
  Every such figure is valid only at its timestamp. One earlier list in the
  record was inverted by a settings default that moved; the correction is the
  `15:02` comment.
- Roughly a quarter of profile-less rows are unreadable at any instant because
  an overlay covers the statusline, clustering on sessions waiting on a picker.
  Unknown is common here and is not the same as safe.
- Two findings were filed rather than fixed inside this epic and are carried
  forward standalone: the marker's invisibility to every operator surface, and
  — now closed — the unpinned no-credential-material constraint.

## The question worth asking that the thread cannot ask itself

The dossier shows each property has A test that fails when the behaviour is
removed. It does not establish that the properties are the RIGHT set, that the
tests pin them at the right level, or that a reader of the shipped code would
arrive at the same reading of the spec. That judgement is the reason leg 2
exists and is the part no amount of self-verification substitutes for.
