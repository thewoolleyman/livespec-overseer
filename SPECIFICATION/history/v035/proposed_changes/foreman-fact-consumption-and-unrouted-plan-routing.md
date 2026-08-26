---
topic: foreman-fact-consumption-and-unrouted-plan-routing
author: claude-opus-5
created_at: 2026-08-26T02:33:30Z
---

## Proposal: The unrouted-plan condition is computed from the composed attention snapshot and carries a typed remedy

### Target specification files

- SPECIFICATION/spec.md
- SPECIFICATION/scenarios.md

### Summary

Names and specifies a condition the foreman MUST compute deterministically on each tick from the composed attention snapshot — a plan unactioned past its bound whose ready children are aging with no live session — and requires the tick to carry the typed session-lifecycle remedy for that condition rather than leaving the seat to compose a response. The condition is named the UNROUTED-PLAN condition, deliberately not any form of the word starvation.

### Motivation

The foreman already consumes a composed attention snapshot, and it already carries a per-plan consecutive-unactioned counter with a bound. What is missing is the join: nothing says that those inputs compose into a single named condition, that the composition is deterministic, or that the tick must offer the remedy that condition implies. Left unstated, the seat is the thing that decides what an unactioned plan means, and a seat deciding that in prose is how a remedy that does not exist gets proposed while a remedy inside the whitelist goes untaken.

The NAME is a normative choice here rather than a drafting preference, and this is the reason it is written into the proposal rather than left to the implementer. This tree already uses the word starvation, and it uses it for something else entirely: a daemon-side liveness condition about a supervised session failing to complete its wind-down, with its own floor, its own episode record, its own alert surface and its own condition string. That subsystem is about a SESSION not finishing. This condition is about a PLAN not being worked. They share no input, no consequence, and no owner. Naming this one starvation would put two unrelated conditions under one word in a tree whose vocabulary is otherwise closed and testable, and would send any implementer told to "compute starvation" into the wrong subsystem first.

Deterministic is likewise load-bearing. A condition an operator surface computes by judgement is not re-checkable, and this tree already requires elsewhere that a wait rest on a re-checkable premise rather than on prose alone.

### Proposed Changes

In `SPECIFICATION/spec.md`, in §"Relay and escalation discipline", add a paragraph:

> On each tick the foreman MUST compute, deterministically and from the composed attention snapshot it already consumes, whether each tracked plan is in the UNROUTED-PLAN condition: the plan is unactioned past its bound, its ready work is aging, and no live session is working it. The computation MUST be a total function of the snapshot and the foreman's own recorded per-plan counter; it MUST NOT depend on the seat's judgement, and it MUST be re-checkable against those same inputs by a reader who did not perform it. Where the snapshot does not carry a fact the computation needs, the condition MUST resolve to NOT-DETERMINED and the absence MUST be surfaced — it MUST NOT resolve to absent-condition, because an unavailable input is not evidence that a plan is being worked.
>
> When the condition holds for a plan, the tick MUST carry the typed session-lifecycle remedy for that plan — the whitelisted action that starts or resumes work on it — as a proposal in the tick's own input. The foreman MUST NOT leave the remedy to be composed by the seat.
>
> This condition MUST NOT be named as any form of "starvation". That term is already bound in this tree to the daemon-side wind-down liveness condition, which shares neither its inputs nor its consequences.

In `SPECIFICATION/scenarios.md`, add two scenarios:

```
## Scenario: An unrouted plan yields a typed remedy in the tick input

Given a tracked plan unactioned past its bound

And its ready work is aging with no live session working it

When the foreman ticks

Then the unrouted-plan condition is computed from the composed attention snapshot

And the tick input carries the typed session-lifecycle remedy for that plan

And the seat is not left to compose the remedy itself

## Scenario: A missing snapshot input yields not-determined, never absent-condition

Given a composed attention snapshot that does not carry a fact the condition needs

When the foreman ticks

Then the unrouted-plan condition resolves to not-determined for that plan

And the missing input is surfaced

And the plan is not reported as being worked on the strength of the absent fact
```

Each added scenario heading requires one corresponding `tests/heading-coverage.json` entry with `spec_root` `SPECIFICATION` and `spec_file` `scenarios.md`; those entries MAY carry `test: "TODO"` until the implementing work lands.

## Proposal: An escalation naming a component the deployment does not have is refused, not relayed

### Target specification files

- SPECIFICATION/spec.md
- SPECIFICATION/scenarios.md

### Summary

Requires the foreman's classifier to REFUSE an escalation whose proposed remedy names a component that does not exist in the deployment, when a whitelisted remedy addresses the same condition — the same way it already refuses a proposal whose classification does not match. The refusal names the absent component and the whitelisted remedy that was available.

### Motivation

A foreman seat, seeing a plan unactioned while its ready children aged, escalated a request to start or repair a resident drain process. No such process exists anywhere in this deployment; the drain is a bounded invocation, not a daemon. The remedy that would have worked was already inside the foreman's own whitelist and was not taken. The escalation cost a human's attention and moved nothing.

The mechanical hook for this already exists and is already used: the mutation surface classifies proposals and refuses one whose classification does not match. This proposal extends that refusal to a second, adjacent malformation — a proposal that is internally coherent but names a thing the deployment does not have — rather than inventing a new mechanism.

The prose half of this defect is worth stating explicitly because it is NOT what fixes it. A sweep of this repository's prose, package and specification for the vocabulary that escalation used returns no occurrence of it anywhere: the seat composed the phrase at run time, from its own model of the system, not by reading it. Wording repairs therefore reduce the chance of recurrence without preventing it, and a mechanical refusal is the only leg that closes it. That is why this proposal is a clause about the classifier rather than a note about vocabulary.

The condition is scoped deliberately. Refusing every escalation that names something the foreman cannot find would make the foreman the arbiter of what exists, and would suppress genuine reports of missing infrastructure. The refusal arms only where a whitelisted remedy for the SAME condition was available and untaken, which is exactly the case where escalating is a mistake rather than a judgement call.

### Proposed Changes

In `SPECIFICATION/spec.md`, in §"Relay and escalation discipline", add a paragraph:

> Where a proposed escalation's remedy names a component that is not part of this deployment, AND a whitelisted remedy addressing the SAME condition is available to the foreman, the classifier MUST refuse that escalation rather than raising it. The refusal MUST name both the absent component and the whitelisted remedy that was available, so the refusal is actionable rather than merely obstructive. Where NO whitelisted remedy addresses the condition, the escalation MUST still be raised: this clause governs a remedy the foreman could have taken and did not, and it MUST NOT be read as licence to suppress a genuine report that required infrastructure is missing.

In `SPECIFICATION/scenarios.md`, add two scenarios:

```
## Scenario: An escalation proposing repair of an absent component is refused with the available remedy named

Given the unrouted-plan condition holds for a tracked plan

And a proposed escalation whose remedy names a component this deployment does not have

And a whitelisted remedy for that same condition is available to the foreman

When the classifier evaluates the proposal

Then the escalation is refused rather than raised

And the refusal names the absent component and the available whitelisted remedy

## Scenario: A genuine report of missing infrastructure is still raised

Given a proposed escalation whose remedy names a component this deployment does not have

And no whitelisted remedy addresses that condition

When the classifier evaluates the proposal

Then the escalation is raised

And it is not refused on account of the named component being absent
```

Each added scenario heading requires one corresponding `tests/heading-coverage.json` entry, which MAY carry `test: "TODO"` until the implementing work lands.

## Proposal: Capacity and wait statements are read from composed facts, never re-derived from raw records

### Target specification files

- SPECIFICATION/spec.md
- SPECIFICATION/scenarios.md

### Summary

Requires the foreman to source any statement it makes about dispatch capacity from the composed attention snapshot's own capacity verdict rather than deriving it from raw work-item statuses, in every surface it authors; and requires the foreman's own wait states to be published as ledger state on the owning plan epic so they are readable without opening a pane.

### Motivation

During the incident this thread was commissioned from, three independent surfaces — a parked session's picker, the foreman's escalation, and a review panel's dossier — all asserted that the dispatch capacity slot was occupied, and all three were wrong in the same way. None had asked the machinery; each had re-derived capacity from raw statuses, and the raw statuses did not mean what all three assumed. A verdict that exists and is not read is worse than one that does not exist, because it produces confident agreement between observers who share a mistake.

The second half addresses the same failure from the other side. The foreman's own wait states — an open picker, a raised escalation, a panel in progress — lived only in a pane and in the surface's private scratch area. Nobody could see what the loop was waiting on without opening the pane it was waiting in, which is precisely the state in which a stall goes unnoticed.

Publishing those waits as LEDGER STATE on the owning plan epic is the placement, and it is chosen rather than assumed. Plan threads and their blocked states are already an established composition class on both sides of this boundary, so the operator is reached through machinery that exists. It also keeps the direction of knowledge right: nothing upstream of this repository needs to learn that this repository exists in order for its waits to be visible.

### Proposed Changes

In `SPECIFICATION/spec.md`, in §"Relay and escalation discipline", add a paragraph:

> Any statement the foreman makes about dispatch CAPACITY — in a tick report, an escalation, a panel dossier, or any other surface it authors — MUST be sourced from the composed attention snapshot's own capacity verdict, or from the equivalent verdict the dispatch machinery itself reports. The foreman MUST NOT derive capacity from raw work-item statuses, and MUST NOT assert that a slot is occupied or free on any basis other than that verdict. Where no such verdict is available, the foreman MUST state that capacity is unknown; it MUST NOT substitute an inference.
>
> The foreman's OWN wait states — an open picker it raised, an escalation awaiting an answer, a panel in progress — MUST be published as ledger state on the owning plan's epic, so that what the loop is waiting on is readable without opening the pane it is waiting in. Publishing them elsewhere in addition is permitted; publishing them ONLY to the surface's private runtime state is not.

In `SPECIFICATION/scenarios.md`, add two scenarios:

```
## Scenario: Capacity is stated from the composed verdict, not from raw statuses

Given a composed attention snapshot carrying a capacity verdict

And raw work-item statuses that would suggest a different answer

When the foreman authors a tick report, an escalation, or a panel dossier

Then the capacity statement matches the composed verdict

And no capacity claim is derived from the raw statuses

## Scenario: A foreman wait is readable without opening its pane

Given the foreman is waiting on an open picker, an escalation, or a panel in progress

When a reader consults the owning plan's epic

Then the wait is published there as ledger state

And the reader can tell what the loop is waiting on without opening the pane
```

Each added scenario heading requires one corresponding `tests/heading-coverage.json` entry, which MAY carry `test: "TODO"` until the implementing work lands.

## Proposal: A surfaced detection-staleness item is routed, never run by the foreman itself

### Target specification files

- SPECIFICATION/spec.md
- SPECIFICATION/scenarios.md

### Summary

Requires the foreman to treat a surfaced detection-staleness item as a ROUTING target — an attended session for the owning plan, or the grooming charge — and forbids it from running the detection itself, because those detections are consent-gated attended dialogues.

### Motivation

The detection skills that keep specification and implementation converging are consent-gated attended dialogues by design: each finding is offered to a human, one at a time. An unattended surface that ran them would either bypass that consent or stall holding a dialogue nobody is present for. Both outcomes are worse than not running them.

At the same time, an item saying detection is overdue is exactly the kind of fact this loop exists to act on, and an unattended surface that receives such an item and does nothing with it reproduces the ownership hole the item was composed to close. Routing is the only correct response, and stating it as a clause is what keeps a future implementer from reading "the foreman acts on attention items" as licence to run these particular ones.

### Proposed Changes

In `SPECIFICATION/spec.md`, in §"Relay and escalation discipline", add a paragraph:

> Where the composed attention snapshot surfaces a DETECTION-STALENESS item — a report that a convergence detection is overdue — the foreman MUST treat it as a ROUTING target: it MUST route the item to an attended session for the owning plan, or to the grooming charge. The foreman MUST NOT run the detection itself, and MUST NOT treat the item as satisfied by any act other than that routing, because those detections are consent-gated attended dialogues and an unattended surface can neither give that consent nor hold that dialogue.

In `SPECIFICATION/scenarios.md`, add one scenario:

```
## Scenario: A detection-staleness item is routed to an attended surface, never run

Given the composed attention snapshot surfaces a detection-staleness item

When the foreman ticks

Then the item is routed to an attended session for the owning plan or to the grooming charge

And the foreman does not run the detection itself

And the item is not treated as satisfied by any act other than that routing
```

The added scenario heading requires one corresponding `tests/heading-coverage.json` entry, which MAY carry `test: "TODO"` until the implementing work lands.
