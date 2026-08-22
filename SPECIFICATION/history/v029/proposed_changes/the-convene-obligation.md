---
topic: the-convene-obligation
author: claude-fable-5
created_at: 2026-08-22T00:04:24Z
---

## Proposal: The convene obligation: seeking a panel verdict under consensus disposition

### Target specification files

- SPECIFICATION/spec.md
- SPECIFICATION/scenarios.md

### Summary

The consensus disposition states when the foreman MAY act on a panel verdict and when it MUST escalate, but never when it MUST SEEK a verdict, so a foreman that never convenes violates nothing while a decision the panel could resolve sits blocked indefinitely. This adds that obligation, named so it can be cited, bounded by one wall-clock deadline shared by every leg, scoped by explicit exclusion of the floors, and discharged — with a recorded artifact — when a panel cannot be constituted. It widens no authority, moves no floor, changes no outcome rule, and adds no heading to existing text.

### Motivation

Measured failure, 2026-08-19: a decision sat blocked for hours across multiple foreman ticks under an effective valve disposition of consensus while the foreman repeatedly surfaced it to the maintainer instead of seeking a panel verdict. The maintainer ordered the panel explicitly; it returned a unanimous verdict in minutes (panel record 4e066523c6948156e4a2b8497ddcecc61b66ea17b39364188ec3d394f06ad2d4). The gap is asymmetric permission: this tree says when the foreman MAY act and when it MUST escalate, never when it MUST ask, so indefinite inaction is compliant and reads as prudence. Four rounds of independent adversarial review shaped this text, and the last three found defects that would have misfired in production rather than merely read poorly. A trigger that fired outside the panel's authority; a narrowing that still over-fired past the floors, since a human-only acceptance is both a human valve and floor-barred; a precondition that swallowed the residual-escalation catch-all and could never be satisfied; a cross-reference to a section heading that did not exist; a requirement aimed at a foreman-owned attention surface this tree forbids as a parallel foreman-private status; an unauditable reconstructed clock that punished a missing record more than a refusal; and a trigger conjunct that was circular, since panel constitutability is discoverable only by attempting it. The final round found two more: creating a heading to make a reference resolve would have annexed the cross-vendor independence and pre-act journal paragraphs under a heading about escalation, so this proposal now cites the paragraph by its opening words and adds no heading at all; and the escape wording, written against an earlier narrower trigger, would have marked a foreman that correctly escalates on a condition present from the start as delinquent. Both are corrected below, and discharge now requires a recorded artifact so the softest path is no longer the least evidenced.

### Proposed Changes

Add to spec.md, immediately BEFORE the heading "### Relay and escalation discipline", the following. Placing it there keeps every existing paragraph of the consensus policy in the un-headed region it occupies today: no heading is added to existing text, no existing paragraph is moved, and none is brought inside a new section.

### The convene obligation

Under the consensus disposition the foreman MUST also SEEK the verdict it is
permitted to act on. That duty is the CONVENE OBLIGATION, and it is referred to
by that name elsewhere in this tree. The escalation conditions referred to below
are those stated in the paragraph beginning "The foreman MUST escalate, and MUST
NOT act, when consensus evidence is unavailable or insufficient".

The convene obligation applies to a decision when ALL of the following hold: the
effective valve disposition is consensus; the governing orchestrator contract
classifies the decision as a human valve within the closed, enumerated
vocabulary this specification binds to by reference; the decision is NOT one the
floors require to stay escalated, being neither a truly unresolvable decision
nor one human-gated BY DESIGN; and the decision is not the human valve id that
remains non-authorizable. Whether consensus evidence can in fact be obtained is
NOT part of this test, because that is discoverable only by attempting to obtain
it.

Where the convene obligation applies, the foreman MUST, within THIRTY MINUTES of
first observing that decision, do AT LEAST ONE of three things: successfully
constitute a cross-vendor review panel for it; record which escalation condition
applies to it, whether that condition applied when the decision was first
observed or has since come to apply; or record a DISCHARGE under the paragraph
below. Every leg shares that single wall-clock bound: the foreman that declines
MUST NOT have longer than the foreman that acts. Where none of the three is done
within the bound, the obligation is UNMET; doing more than one of them is not a
violation, because the obligation is satisfied by an artifact existing rather
than by exactly one existing; a decision MUST NOT be left unaccounted for on the
ground that no escalation condition existed.

So the bound is auditable rather than merely asserted, the foreman MUST record
the instant at which it first observes a decision the convene obligation applies
to. Where no such instant was recorded, the obligation for that decision is
UNMET; this specification does NOT reconstruct a retroactive observation
instant, because a reconstructed clock cannot be audited. The records this
obligation requires — the first-observation instant, the recorded escalation
condition, and the recorded discharge — live under the operator surface's own
`tmp/overseer/foreman/` subdirectory, so an auditor knows where to look and a
conformance check has something to read.

The obligation is DISCHARGED, not violated, when an attempt to constitute a
cross-vendor review panel within the bound cannot produce one — including where
a second vendor is unreachable. That is consensus evidence being unavailable,
and the foreman MUST then escalate under the escalation conditions rather than
act. A discharge MUST be RECORDED within the bound, naming the attempt made and
the reason a panel could not be constituted; an unrecorded discharge is an UNMET
obligation, not a discharge. No leg of this obligation may be satisfied without
leaving an artifact.

An unmet convene obligation MUST be surfaced, with the decision's coordinates,
so the omission is observable rather than silent. Elapsed inaction alone MUST
NOT be treated as compliance with this obligation.

This obligation is a duty to SEEK a verdict and never a widening of what a
verdict may authorize. It MUST NOT be read to extend the panel's authority
beyond the closed, enumerated vocabulary; to move any floor boundary; to relax
the requirement that a verdict be unanimous and typed; to relax the requirement
that reviewers be drawn from at least two distinct vendors; or to permit acting
where escalation is required. The cardinal rule, stated in §"The cardinal rule",
is unaffected.

Add to scenarios.md five scenarios:

## Scenario: The foreman seeks a panel verdict for a decision the convene obligation applies to

Given an effective valve disposition of consensus

And a blocked decision the governing contract classifies as a human valve within the panel's enumerated vocabulary

And the decision is neither truly unresolvable nor human-gated by design

And no escalation condition applies to that decision

And a cross-vendor review panel can be constituted for it

When the foreman first observes that decision

Then the foreman records the instant of that first observation

And the foreman successfully constitutes a cross-vendor review panel for it within thirty minutes of that instant

## Scenario: A foreman that declines to convene records the escalation condition, however long it has applied

Given a decision the convene obligation applies to

And an escalation condition that applied when the decision was first observed

When thirty minutes pass from the recorded instant of first observation with no panel initiated

Then the foreman has recorded which escalation condition applies

And the obligation is not reported as unmet

## Scenario: A panel that cannot be constituted discharges the obligation and escalates

Given a decision the convene obligation applies to

And a second vendor that is unreachable throughout the bound

When the foreman attempts to constitute a cross-vendor review panel and cannot

Then the foreman records a discharge naming the attempt and the reason within the bound

And the decision is escalated rather than acted on

## Scenario: An unmet convene obligation is surfaced rather than passing silently

Given a decision the convene obligation applies to

When thirty minutes pass from the recorded instant of first observation with no panel initiated, no escalation condition recorded, and no discharge recorded

Then the decision is surfaced as an unmet convene obligation

And the surfaced entry carries the decision's coordinates

## Scenario: A floor-barred human valve does not trigger the convene obligation

Given an effective valve disposition of consensus

And a blocked decision that is human-gated by design

When the foreman observes that decision

Then the decision stays escalated

And no panel is initiated for it
