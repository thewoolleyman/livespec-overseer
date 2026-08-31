# 002 — Ratification-review triage: four blockers, and the one I should have caught

Created 2026-08-26 by the `homelab-loop-hardening-overseer` session, on the
first ratification pass of
`SPECIFICATION/proposed_changes/foreman-fact-consumption-and-unrouted-plan-routing.md`.

The independent reviewer this repo's `auto-spawn` governance requires returned
**four blockers** against the exact final bytes. All four are correct. Triage
is recorded here before any repair, per the discipline that kept the sibling
topic's second round about the fix rather than about rediscovering the problem.

Three of the four share one root cause, which is worth naming before the
individual findings: **the clauses were written against the vocabulary of
`.claude-plugin/prose/foreman.md` rather than against the ratified tree.** That
prose is real and accurate, and it is explicitly placed OUTSIDE the governed
contract by the very section these clauses land in. The section's own closing
rule is unambiguous: guarantees the foreman's contract surface relies on MUST
be stated in this tree before an implementation depending on them lands. I read
the prose while measuring the baseline, absorbed its terms, and wrote spec
clauses in them.

## Blocker 1 — the counter and the bound do not exist in the ratified tree

The clause requires the computation to be "a total function of that snapshot
and the foreman's own recorded per-plan counter", and defines the condition
partly as "the plan is unactioned past its bound."

Neither exists. `spec.md`, `contracts.md` and `constraints.md` contain no
`counter`, no `unactioned`, no `consecutive` for the foreman. The only
definition — the per-plan consecutive-unactioned counter carried by the roster
helper, with maintainer-owned bounds of 2 and 1 — lives in ungoverned
presentation prose.

**The clause is self-defeating as written**, and that is the sharp form of the
finding: it demands the computation "MUST be re-checkable against those same
inputs by a reader who did not perform it", while a reader of the ratified tree
cannot discover what the counter counts, where it is recorded, or what the
bound is. A re-checkability requirement whose inputs are undiscoverable is not
a weaker guarantee, it is an unsatisfiable one.

**Disposition: specify both in the tree.** The counter becomes a ratified
obligation — the foreman records, per tracked plan, the number of consecutive
ticks in which it took no action on that plan, reset to zero by any tick that
actions it. The bound is named as maintainer-owned configuration rather than
given a number, since the number genuinely is a maintainer choice; and where no
bound is configured the condition resolves UNDETERMINED rather than assuming a
default, which is the same fail-closed direction the rest of the amendment
takes.

## Blocker 2 — NOT-DETERMINED duplicates the ratified UNDETERMINED

The same section, sixty lines above, already ratifies UNDETERMINED for exactly
this epistemic class: the foreman MUST treat an unavailable picker state as
UNDETERMINED, and an undetermined picker state MUST fail closed. There is a
ratified scenario pinning it.

I introduced NOT-DETERMINED for the identical concept — a required input is
unavailable, the condition resolves to the safe side, the absence is surfaced.

**This one is mine in a way the others are not.** The amendment's own second
requirement bans naming this condition any form of "starvation" *precisely
because* the tree already binds that word elsewhere, and the motivation argues
the vocabulary is closed and testable. I made the vocabulary argument and then
committed the vocabulary error, in the same document, against a term sitting in
the same section. Knowing the failure mode did not prevent me from committing
it — which is the second time on this leg that a hazard I had written down in
prose was reproduced in the normative text a few paragraphs away.

**Disposition: use UNDETERMINED.** No distinction between the two exists to
state, and after ratification the split would be permanent.

## Blocker 3 — the actors these MUSTs bind are not in the tree

"The classifier MUST refuse that escalation" names no ratified actor: neither
`classifier` nor `mutation surface` appears in the tree. The motivation's claim
that the mechanical hook already exists is true of the implementation and
unverifiable against the specification.

The same defect runs through "as a proposal in the tick's own input" and "MUST
NOT leave the remedy to be composed by the seat". Ticks are ratified; a tick
INPUT that carries proposals is not. And `seat` is ratified — as the session
itself — which makes "the foreman MUST NOT leave the remedy to be composed by
the seat" **circular**: it forbids the foreman to leave work to the foreman.

**Disposition: state the obligations on the foreman directly.** The foreman
identifies the whitelisted remedy and makes it the action it takes or proposes;
the foreman refuses to raise the escalation. Dropping the internal pipeline
loses nothing the matrix asked for — the matrix asked that the remedy be
emitted deterministically and the escalation refused, not that any particular
component do it — and it removes three unratified nouns and one circularity.

## Blocker 4 — the capacity-unknown branch has no scenario

The capacity clause has two branches. The verdict-present branch has a
scenario. "Where no such verdict is available, the foreman MUST state that
capacity is unknown; it MUST NOT substitute an inference" has none, so an
implementation that silently infers capacity whenever no verdict exists passes
every proposed scenario.

**That branch is the closest analogue of the motivating incident.** Three
surfaces asserted an occupied slot because each inferred capacity rather than
reading a verdict. The clause written to stop exactly that is the one left
untestable.

The reviewer's observation about the asymmetry is the useful part: clause 1's
absence branch *did* get its own scenario, and this one was missed. So the
omission is not a considered judgement about which branches matter, it is
simply an oversight — the third instance on this leg of a MUST shipped without
a control that could fail for it.

**Disposition: add the scenario and its coverage entry.**

## One non-blocking finding that creates an obligation elsewhere

`.claude-plugin/prose/foreman.md` currently calls this very condition's bound
"the starvation bound". The moment the ban ratifies, that prose contradicts the
tree. The amendment does not flag it.

This does not change the spec text, but it does change what the prose child
owes: requirement R9 was scoped to removing drain-daemon vocabulary while
preserving the hold rule, and it now also carries this rename. Recorded here so
the child is not filed against the narrower reading.

## Accuracy items taken while repairing

Not blockers; taken because the text is being rewritten anyway and each removes
a future ambiguity: `the owning plan's epic` becomes the ratified `ledger
epic`, since `plan/<topic>/epic.md` is also "the plan's epic" in tree usage;
`the grooming charge` becomes the ratified grooming operation; and the claim
that the foreman already consumes the composed snapshot is softened to match
`contracts.md`, which states that composition as a MAY.

**Every repair stales the attestation byte-for-byte.** A fresh review is
required, and the round-2 reviewer must be told what round 1 blocked so it
verifies the repairs rather than rediscovering them.
