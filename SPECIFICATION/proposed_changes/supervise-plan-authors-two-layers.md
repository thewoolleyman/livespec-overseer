---
topic: supervise-plan-authors-two-layers
author: claude-opus-5
created_at: 2026-07-30T14:10:00Z
---

## Proposal: supervise-plan authors TWO layers, not one — correct the count in spec.md

### Target specification files

- spec.md

### Summary

`spec.md` says the `supervise-plan` operator skill "MAY create exactly ONE named
artifact, `plan/<topic>/supervisor-handoff.md`". Since commit `57426df` it creates
**two**: a shared role layer at `.ai/supervisor-protocol.md` plus the per-thread
binder at `plan/<topic>/supervisor-handoff.md`. The specification governs, the code
is the final word on behavior, and here they disagree — so the specification is
wrong and should be corrected to match shipped behavior.

### Motivation

The two-layer split is not an accident to be reverted; it is the shipped design and
it is load-bearing. The binder is deliberately thin and explicitly "not complete by
itself"; the shared layer carries the role contract — HALT-first preconditions, the
ledger re-measure, the watcher shapes, and the role-level `## Corrections` log. Both
are written into the CONSUMER's tree by the skill, and neither is a packaged plugin
asset (measured: `.claude-plugin/` contains zero `.ai/` paths).

The drift is not cosmetic. The emitted binder carries a `test -f` guard that HALTs
with a labelled REMEDY when the shared layer is missing, so a reader following the
specification's "exactly ONE" would be surprised by a second file the tooling
already treats as mandatory.

Measured 2026-07-30 against `origin/master`: `.ai/` exists and holds
`supervisor-protocol.md`; the generator prose instructs the skill to create both
layers; and this repository's own charter gate now scans both, because the shared
layer is half of what any supervisor actually reads.

### What this proposal deliberately does NOT touch

**`spec.md` line 221 and the `§"Non-interference with tracked work"` passage around
line 326 must stay exactly as they are.** Those describe the DAEMON's bounded
existence probe — "the daemon MAY test the EXISTENCE of exactly one named artifact,
`plan/<topic>/supervisor-handoff.md`" — and that sentence is still **true and still
correctly scoped**. The daemon never opens, reads, hashes, or probes `.ai/` at all;
two independent merge-safety reviews of release PR #244 verified that
`overseer/_supervisor_restart.py` and `_supervisor_prompts.py` check only that the
binder EXISTS.

That constraint is a non-interference guarantee, and widening its "exactly one" to
"two" while correcting the authoring clause would WEAKEN a check that is currently
accurate — permitting a file-level probe the daemon does not perform and must not
start performing. The two clauses use similar words for entirely different actors.
Any revision accepting this proposal should change the AUTHORING clause only.

### Proposed Changes

In `spec.md`, in the paragraph beginning "An ATTENDED Control-Plane operator skill
(supervise-plan) MAY create exactly", replace:

> An ATTENDED Control-Plane operator skill (supervise-plan) MAY create exactly
> ONE named artifact, plan/<topic>/supervisor-handoff.md, in a watched
> repository, and MUST write it exclusively through that repository's own
> documented commit discipline — worktree, then pull request, then review, then
> merge — never directly to a primary checkout.

with:

> An ATTENDED Control-Plane operator skill (supervise-plan) MAY create exactly
> TWO named artifacts in a watched repository: the shared role layer
> `.ai/supervisor-protocol.md`, and the per-thread binder
> `plan/<topic>/supervisor-handoff.md`. The binder is intentionally thin and is
> NOT complete on its own; it MUST be read together with the shared layer, and it
> MUST emit a guard that HALTs with a labelled REMEDY if that layer is absent.
> Both MUST be written exclusively through that repository's own documented commit
> discipline — worktree, then pull request, then review, then merge — never
> directly to a primary checkout. Neither is a packaged plugin asset; the skill
> writes both into the consuming repository's own tree.

The following sentence — "An authored artifact is NOT overseer runtime state: the
'exactly two places' sentence below and the startup gitignore refusal continue to
bind the daemon's runtime state verbatim." — stands unchanged and now covers both
authored artifacts.
