---
topic: vendored-exemption-intra-package-imports
author: test-and-gate-integrity-resume-session
created_at: 2026-08-22T17:13:46Z
---

## Proposal: Condition (b) covers a vendored library's own intra-package imports

### Target specification files

- SPECIFICATION/constraints.md

### Summary

Amend the vendored-dependency exemption's condition (b) so that the set an
allowed module-load import may resolve into explicitly includes the vendored
library's OWN modules, not only some other library vendored beside it. The
change is one phrase and moves nothing normative: it makes the clause say what
its own second sentence, its worked example, and its binding implementation
commitment already require.

### Motivation

Condition (b) as ratified in v027 reads that every import the vendored code
evaluates at module load "MUST resolve either to the standard library or to
ANOTHER library vendored under the same `overseer/_vendor/` tree."

READ LITERALLY, THAT SET EXCLUDES THE LIBRARY'S OWN MODULES. A vendored package
importing its own submodules — `returns` importing `returns.primitives.hkt`, and
dozens like it at module load — is importing neither the standard library nor
ANOTHER library. So the literal reading makes (b) unsatisfiable by any
multi-module library, which would make the whole exemption vacuous: no library
that could plausibly need vendoring could ever satisfy it.

THE LITERAL READING IS ALREADY CONTRADICTED THREE WAYS INSIDE THE RATIFIED
MATERIAL, which is why this is a wording repair and not a change of rule. The
clause's own second sentence frames (b) around a library's RUNTIME DEPENDENCIES.
Its worked example treats the vendored library's internals as in-set. And the
binding implementation commitment `overseer-vqmq` encodes the intent verbatim —
"the vendored tree's own imports resolve within itself and the standard
library."

BOTH INDEPENDENT RATIFICATION REVIEWS FOUND THIS AND BOTH CLEARED IT AS
NON-BLOCKING. It was deliberately not ridden on the ratification: editing the
proposal file would have changed `proposal_bytes`, invalidated the ratification
digest, and forced a third review round against bytes nobody had reviewed. That
trade was judged correctly. Ratified text can only be changed by ratification,
so the polish needs its own proposal — this one. Tracked as `overseer-ntz1`.

### The v027 worked-example counts are OVERCOUNTS — recorded here because the history is frozen

`SPECIFICATION/history/v027/` is frozen and MUST NOT be edited. Its worked
example states 27 module-load `typing_extensions` sites and 19 contrib files.
The true figures are 24 and 18. This is recorded in the proposal stream so that
a future reader who notices the discrepancy does not re-derive it or mistake it
for version skew: it is neither. The same vendored copy, two counting methods.

PROVENANCE OF THE ERROR: a naive grep of string occurrences rather than an AST
walk of module-load imports. The three extra `typing_extensions` hits are two
docstring doctest lines (`context/requires_context.py:245` and `:267`) plus
`contrib/hypothesis/laws.py`, which the same clause prunes. The nineteenth
contrib file, `contrib/hypothesis/_entrypoint.py`, imports `hypothesis` inside
`_setup_hook()` — a function body, never evaluated at import.

MEASURED INDEPENDENTLY A THIRD TIME while authoring this proposal, on the live
tree at 8f2f5ba: an AST walk over `overseer/_vendor/returns/**/*.py` counting
only module-load (top-level) imports whose root package is `typing_extensions`
returns **24**, reproducing the corrected figure exactly. State the boundary
honestly: the **18** figure could NOT be re-measured here, because the vendored
copy carries **zero** contrib files — the pruning that condition (b) itself
mandates has already removed that tree. So 24 is confirmed three ways and 18
rests on the two reviewers' agreement.

NOTHING NORMATIVE MOVES. The counts appear only in motivational prose and an
implementation-followup description, never in ratified constraint text, and both
conclusions they support still hold at the corrected figures: `typing_extensions`
is a genuine module-load dependency, and all three contrib trees imported tooling
at module load.

### Proposed changes

In `SPECIFICATION/constraints.md`, section "Language and dependencies",
condition (b) **Standalone**, first sentence: replace

> "...MUST resolve either to the standard library or to another library vendored
> under the same `overseer/_vendor/` tree."

with wording whose allowed set explicitly admits the vendored library's own
modules — for example "...MUST resolve either to the standard library or WITHIN
the same `overseer/_vendor/` tree." The phrase "within the same tree" covers
both a library's own submodules and a sibling vendored library, which is the set
the clause's second sentence, its worked example, and `overseer-vqmq` all
already assume.

The rest of (b) is UNCHANGED and this proposal must not be read as loosening it.
The requirement that a library whose runtime dependencies cannot themselves all
be vendored under (a)-(c) MUST NOT be vendored, and the requirement that modules
importing anything outside that set be pruned or be provably unreachable, both
stand exactly as ratified. This proposal widens the allowed set by exactly one
member — the library's own modules — which the literal text excluded only by
accident of phrasing.

Where `SPECIFICATION/scenarios.md` carries constraint scenarios, a scenario
SHOULD prove the boundary in both directions: a multi-module vendored library
whose module-load imports resolve to its own submodules and the standard library
SATISFIES (b); a vendored module importing a third-party package that is not
vendored under the same tree still FAILS (b), whether that import is its own
submodule's or not.
