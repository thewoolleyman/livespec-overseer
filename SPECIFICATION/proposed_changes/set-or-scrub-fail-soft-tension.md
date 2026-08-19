---
topic: set-or-scrub-fail-soft-tension
author: claude-opus-5-1m
created_at: 2026-08-19T14:48:49Z
---

## Proposal: Resolve the set-or-scrub versus fail-soft tension for a relaunch with no recorded launch profile

### Target specification files

- SPECIFICATION/spec.md

### Summary

The set-or-scrub environment rule and the fail-soft no-profile rule both govern a relaunch of a track whose mapping row carries no launch profile, and they prescribe different behavior for it. The specification does not say which wins, and the implementation has already resolved the conflict one way for Claude and the other way for Codex. This proposal records the tension and carries both candidate resolutions without recommending either, so ratification rather than authorship decides.

### Motivation

Discovered 2026-08-19 while auditing the launch-profile chain for harness symmetry,
the same review that produced work-item `overseer-gaouiv`. Evidence and the full measurement are
recorded on ledger epic `overseer-bc55wx`.

The ambiguity is not academic: it has already produced divergent implementations of the same rule
inside one module. The two planners yield six environment outcomes and exactly one of them
passively inherits. A reader auditing the daemon for conformance today reaches opposite verdicts
depending on which clause they consult first, and both verdicts are defensible.

PRACTICAL IMPACT TODAY APPEARS TO BE NIL, and that is stated deliberately so this is not treated as
urgent. The scrubbed variables are Claude-controlled and a bare Codex resume command does not read
them. A concrete harm was sought and none was constructed.

The reason to resolve it anyway is that the set-or-scrub rule exists precisely because passive
inheritance is the documented failure mode in both directions, and because the wrapper idiom of
substituting a default for an unset variable means a leaked value silently wins over a wrapper's
own default. That reasoning is not obviously harness-specific. The next person to add a Codex
wrapper shape, or to make any Codex launch consult an inherited variable, will be standing on the
one branch that does not scrub, with nothing in the specification telling them which side of the
tension they are on.

Resolving it costs one clause either way, and leaving it unresolved means the answer keeps
depending on which clause a reader happens to open first.

### Proposed Changes

Two ratified clauses in `spec.md` "The launch profile" both govern a relaunch of a
track whose mapping row carries NO launch profile, and they cannot both be satisfied for that case.

THE SET-OR-SCRUB CLAUSE says the daemon MUST, on every relaunch, explicitly set or unset
`ANTHROPIC_MODEL`, `ANTHROPIC_SMALL_FAST_MODEL` and the `CLAUDE_CODE_*` context-limit overrides
rather than passively inheriting them. It carries no harness qualifier and no profile qualifier.

THE FAIL-SOFT CLAUSE says a track's mapping row that carries no launch profile MUST continue to
relaunch exactly as it does today.

For a no-profile row, "explicitly set or unset the controlled variables" and "relaunch exactly as
it does today" are different behaviors. The specification does not say which governs, and the
implementation has resolved the conflict differently on each harness: the Claude planner scrubs on
its no-profile branch, while the Codex planner passes no environment delta at all. The
inconsistency is also internal to the Codex path, whose cloud-profile branch scrubs while its
no-profile branch does not, though both launch the same bare resume command.

THIS PROPOSAL DELIBERATELY RECOMMENDS NEITHER ARM. Both are recorded so the revise pass makes the
choice; a proposal that picked one would settle by authorship a question that belongs to
ratification.

ARM A — THE SET-OR-SCRUB RULE WINS, AND FAIL-SOFT IS NARROWED TO MEAN THE COMMAND.
The set-or-scrub clause SHOULD be stated to apply to every relaunch including one for a row with no
recorded profile, and the fail-soft clause SHOULD be narrowed to say that such a row MUST continue
to relaunch with exactly the command it uses today, rather than with exactly the behavior it has
today. Under this arm the daemon MUST scrub the controlled variables on the Codex no-profile branch
as it already does for Claude. This arm treats passive inheritance as the hazard the rule names,
and reads fail-soft as being about the launch command rather than about the environment.

ARM B — SET-OR-SCRUB IS SCOPED TO CLAUDE.
The set-or-scrub clause SHOULD be stated to govern relaunches of Claude tracks and of any track
launched through a recorded wrapper, and the daemon MAY pass no environment delta when relaunching
a Codex track that has no recorded profile. Under this arm the current implementation is already
conformant and no code changes. This arm reads the controlled variables as Claude-specific, which
is what their names denote, and preserves fail-soft literally.

WHICHEVER ARM IS RATIFIED, the resulting text MUST be unambiguous about the no-profile case for
both harnesses, so that a reader cannot reach opposite conclusions by consulting different clauses.

