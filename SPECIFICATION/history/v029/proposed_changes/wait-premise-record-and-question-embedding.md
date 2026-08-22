---
topic: wait-premise-record-and-question-embedding
author: claude-fable-5
created_at: 2026-08-22T00:04:24Z
---

## Proposal: The wait-premise record as a governed durable store

### Target specification files

- SPECIFICATION/contracts.md

### Summary

Define the wait-premise record as a durable store this tree governs: its purpose, its schema version, its required fields, the CLOSED SET OF FOUR KINDS enumerated here, its exact path and filename derivation, its atomic write, its fail-soft individually-scoped read, its expiry and evidence rules, and its lifecycle. The record exists in the implementation today and is governed nowhere, so any obligation referring to it would rest on undefined vocabulary.

### Motivation

Measured incidents, 2026-08-18 and 2026-08-19: sessions and pickers parked on waits whose premises were false — an option asking an operator to wait on a run that did not exist, and workers waiting on runs absent from the records they were checked against. The durable lesson was that the hazard is an UNVERIFIABLE claim rather than a missing target: a wait recorded only as prose supplies nothing a later reader can re-query, so it is trusted indefinitely. Independent review established two things about placement that this proposal follows. First, a durable store's shape is a wire-level surface, which README.md assigns to this file rather than to spec.md. Second — correcting an over-application in an earlier draft — the by-reference rule that forbids restating the governing orchestrator contract's enumerations does NOT apply here: the wait-premise record is THIS tree's own store, no other document owns its kinds, and so enumerating them here IS the definition rather than a duplication. An earlier draft declared a closed vocabulary and enumerated nothing, leaving a closed set with no members and no owner, which made the companion obligation's central predicate undecidable. A later review round approved this definition and asked for one addition now folded in: every sibling store in this file governs its own lifecycle, and this one did not say whether a record is ever removed, so records would accumulate under a per-track scratch directory indefinitely.

### Proposed Changes

Add to contracts.md, beside the other per-track durable stores and immediately before "## Daemon invocation", a new section:

## The wait-premise record

A wait-premise record states, in re-queryable form, that an actor is waiting
on a named external target, so a later reader can test the wait rather than
trust the writer.

Each record MUST carry an integer `schema_version`; the target's KIND; the
target's IDENTIFIER; the EVIDENCE SOURCE that can be re-queried to test
whether the premise still holds; the instant it was RECORDED; and the instant
by which it MUST be RE-CHECKED. A record missing any of these MUST NOT be
treated as a valid premise.

The kind MUST be one of exactly four members: `fabro-run`, `pr`, `ci-run`, and
`work-item-close`. That set is CLOSED. Widening it requires a ratified change
to this specification, no configuration value MAY widen it, and an
implementation-level enumeration MUST NOT satisfy it — a kind that exists only
in code can be widened by any change that adds a value to it, and is therefore
not a defined kind for this purpose however faithfully it is enforced. A
target whose kind this set cannot express MUST NOT be recorded under a
neighbouring kind, because a record whose kind is wrong is worse evidence than
no record at all.

Records live in a `wait-premises/` subdirectory of whichever runtime-state
directory this tree already assigns the writing actor, so no actor is required
to write outside the home spec.md gives it: for a track-scoped session that is
`<repo>/tmp/overseer/<topic>/wait-premises/`, and for an authorized operator
surface it is `<repo>/tmp/overseer/foreman/wait-premises/`. No actor MAY
create a new scratch root for these records. There is one file per record,
each named from the record's kind and target identifier. Because an identifier
may contain characters a filename cannot carry, the derivation MUST be
collision-free across distinct targets: two records naming DIFFERENT targets
MUST NOT derive the same filename, and a derivation that would collide MUST be
disambiguated rather than allowed to overwrite. Because the disambiguation
scheme is deliberately unspecified, a reader given a record's kind and target
identifier locates it by MATCHING THOSE FIELDS within the writing actor's own
wait-premise directory rather than by recomputing its filename.

A record MUST be written atomically, so a reader observes either the previous
content or the complete new content, never a partial write. Reads are
FAIL-SOFT and INDIVIDUALLY SCOPED: an unreadable, malformed, or
unknown-or-newer `schema_version` record MUST be skipped and surfaced rather
than failing the surrounding read of its sibling records. A failed WRITE MUST
be surfaced and survived under spec.md §"Fail-soft posture", and MUST NOT
abort the act its writer was performing.

A premise is EXPIRED once its re-check instant has passed with no
re-verification against its recorded evidence source. An expired premise MUST
NOT be presented as current evidence that a wait still holds. Evidence that a
premise no longer holds MUST come from that premise's own recorded evidence
source; a different or narrower source MUST NOT be substituted for it.

A record's lifecycle ends when its wait does: once the wait it states is
resolved or ABANDONED — abandoned meaning the actor is no longer waiting on
that target — the record MUST be removed, so the directory holds the waits
that are live rather than every wait ever held. Removal MUST NOT be inferred
from expiry alone — an expired premise is one nobody has re-checked, which is
a condition to surface rather than evidence the wait ended.

Add to scenarios.md three scenarios:

## Scenario: A malformed wait-premise record is skipped rather than failing its siblings

Given a wait-premise directory holding one valid record and one malformed record

When the records are read

Then the valid record is returned

And the malformed record is skipped and surfaced## Scenario: An expired wait premise is not presented as current evidence

Given a wait-premise record whose re-check instant has passed

And no re-verification has been performed against its recorded evidence source

When the premise is consulted

Then it is not presented as current evidence that the wait still holds

And the record is not removed on the strength of its expiry

## Scenario: Two distinct targets do not collide onto one wait-premise file

Given two wait-premise records naming different targets of the same kind

And the two identifiers derive the same filename before disambiguation

When both records are written

Then both records are readable

And neither has overwritten the other

## Proposal: A question that asks for a wait carries a re-checkable premise, and that premise is re-checked

### Target specification files

- SPECIFICATION/spec.md
- SPECIFICATION/scenarios.md

### Summary

Where an actor this tree governs raises a question whose option asks someone to wait on an external target, and that target's kind is one the governed wait-premise vocabulary expresses, the actor MUST record the premise before raising, MUST identify it in the option by kind and identifier, and MUST re-verify it against its recorded evidence source by the record's re-check instant, surfacing the outcome where the premise fails rather than on every healthy pass. Where the kind is inexpressible or the record cannot be written, the question MAY still be raised and the gap MUST be surfaced. CONDITIONAL: this proposal MUST NOT be ratified unless the companion proposal defining the wait-premise record in contracts.md is also ratified, since every term it uses normatively is defined there.

### Motivation

Same measured incidents as the companion proposal: waits whose premises were false, discovered by a human hours later, because a prose-only wait supplies nothing re-queryable. Several rounds of independent adversarial review shaped this text. An early draft forbade raising a prose-only question at all, which would have forced a raiser into silence or into fabricating a false kind whenever the closed vocabulary could not express the wait; that is now an explicit fail-soft branch. The same draft bound actors this tree does not govern, since an open picker raised by a supervised session's own harness is something this tree OBSERVES rather than forbids. A later draft HARDENED a requirement an earlier one had right, demanding a stale option be reported as invalid rather than presented as a live choice — which no governed actor can do, because altering a rendered option means acting on a pane showing a structured gate, which this tree suppresses absolutely; the capability form is restored, with surfacing rather than un-presenting. The review round that approved that text identified one remaining completeness gap, now closed here and load-bearing: the definition made a wait RE-CHECKABLE but nothing obliged anyone to RE-CHECK it, so a conformant implementation could record a premise, let its re-check instant pass, and never re-query — which is precisely the 2026-08-19 incident surviving ratification. The obligation to re-verify by the recorded instant is therefore stated explicitly, and the form in which a record is identified is pinned so a later reader can actually find it.

### Proposed Changes

Add to spec.md, at the end of the foreman relay-and-escalation discipline section (immediately before "## The cardinal rule"), a new paragraph group:

Where the foreman raises a question whose option asks a session or an operator
to WAIT on an external target, and that target's kind is one the wait-premise
vocabulary in contracts.md §"The wait-premise record" expresses, the foreman
MUST record the wait-premise before raising the question, and MUST identify
that record in the option by its kind and target identifier, so a reader can
locate and re-query it without trusting the raiser.

Recording a premise is not sufficient: a premise nobody re-checks is prose
with a timestamp. The foreman that raised the question MUST re-verify that
premise against its recorded evidence source by the record's re-check instant,
and a foreman that assumes responsibility for a raised question INHERITS that
obligation. The outcome MUST be surfaced where the premise fails, has expired,
or cannot be tested; a re-verification that passes needs no announcement, so
this obligation does not emit a line per healthy wait per cycle. Where the
foreman determines that an option's premise has expired, or that its target
cannot be confirmed by that premise's recorded evidence source, it MUST
SURFACE the option as resting on a failed premise.

The purpose is re-checkability, not enforcement against a rendered surface.
Such an option MUST be capable of being tested against its named record's own
evidence source, without re-reading the option's prose and without trusting
the raiser. Nothing in this paragraph authorizes any actor to alter, withdraw,
answer, or select an option once raised; a question already showing a
structured gate remains subject to the acting suppression that constraints.md
§"Acting safety" governs, without exception.

The recording obligation is FAIL-SOFT and MUST NOT suppress the question.
Where the target's kind is not expressible in that closed vocabulary, or the
record cannot be written, the question MAY still be raised, and the foreman
MUST surface that the option carries no re-checkable premise, so a reader
knows the wait rests on prose alone. This paragraph governs the foreman's own
behavior as a question-raising actor, consistent with the scope of the section
it sits in; an open picker raised by a supervised session's own harness
remains something this tree OBSERVES rather than something it forbids. The
cardinal rule is unaffected.

Add to scenarios.md four scenarios:

## Scenario: The foreman identifies a recorded premise in a wait option

Given a foreman that has recorded a wait-premise for an expressible target kind

When the foreman raises a question whose option asks a session to wait on that target

Then the option identifies that record by its kind and target identifier

And the option is testable against the premise's own recorded evidence source

## Scenario: A recorded premise is re-verified by its recheck instant

Given a raised question whose option identifies a recorded wait-premise

When the premise's re-check instant arrives

Then the foreman that raised the question re-verifies the premise against its recorded evidence source

And the outcome is surfaced where the premise fails, has expired, or cannot be tested

## Scenario: An inexpressible wait kind does not suppress the question

Given a foreman about to raise a question whose option asks a session to wait on a target

And that target's kind is not expressible in the wait-premise vocabulary

When the foreman raises the question

Then the question is still raised

And the foreman surfaces that the option carries no re-checkable premise

## Scenario: A failed premise is surfaced rather than the option being altered

Given a raised question whose option identifies a recorded wait-premise

And the premise's target cannot be confirmed by that premise's recorded evidence source

When the foreman determines the premise has failed

Then the foreman surfaces the option as resting on a failed premise

And the raised question itself is neither altered nor answered by the foreman
