---
topic: mapping-store-write-validation-and-start-intent
author: claude-opus-5
created_at: 2026-08-26T02:31:37Z
---

## Proposal: Mapping-store rows are validated when they are written, not only tolerated when they are read

### Target specification files

- SPECIFICATION/contracts.md
- SPECIFICATION/scenarios.md

### Summary

Adds a write-side obligation to contracts.md §"Durable stores": a surface writing a mapping-store row MUST validate it against the row's own durable-key contract before the write, and MUST refuse a row that fails, naming the offending key and leaving the store unchanged. The refusal is scoped to the row being introduced or changed, so a rewrite that merely carries a pre-existing non-conforming row along is not refused. Adds the two scenarios that exercise the refusal and that scoping.

### Motivation

The mapping-store bullet in §"Durable stores" governs the READ side thoroughly — malformed lines are skipped and named, unknown keys survive rewrites, a stale `model_profile` is surfaced and the restart skipped — and says nothing at all about the WRITE side. A writer may therefore introduce a row that no reader can act on, and nothing detects it at the moment of the write. The loss surfaces only later, when a restart that should have happened does not, which is the worst possible time to learn it: the declaration has already been made, and the evidence of who wrote the bad row is gone.

This is not a hypothetical gap. It was reported twice against this deployment that a track's row lost its ledger epic id, once after the row had already been repaired by hand. A hand repair does not hold, because nothing refuses the write that undoes it. Read-side tolerance is correct for its own purpose and cannot substitute: tolerance is what lets a single bad line coexist with a healthy store, and it is precisely why a bad row can persist unnoticed.

The scoping half is load-bearing and is stated here rather than left to implementation. The store is rewritten wholesale by several maintenance paths that are not introducing or changing the row in question. A validation gate that refused any write carrying a non-conforming row would let one bad row block unrelated maintenance across the whole store, converting a narrow defect into a broad outage. Scoping the refusal to the row being introduced or changed is what makes the write gate safe to arm, and it is also what makes the surfacing obligation in the sibling proposal necessary rather than decorative: the two are complements, because a row that survives the gate must still be visible.

### Proposed Changes

In `SPECIFICATION/contracts.md`, in the **mapping store** bullet of §"Durable stores", after the sentence "Malformed lines are skipped and named, never fatal.", add:

> A surface that writes a mapping-store row MUST validate that row against the durable-key contract above BEFORE the write. A row that fails validation MUST be refused with the offending key named, and the store MUST be left byte-unchanged by the refused write; the surface MUST NOT write a partially-corrected row. Validation applies to the row being INTRODUCED OR CHANGED by that write, and MUST NOT be applied to a row the write merely carries along unchanged — so a pre-existing non-conforming row can never block unrelated maintenance of the store. A row that is carried along unchanged and does not conform MUST be surfaced per §"Attention surface" rather than silently rewritten or silently dropped.

The read-side sentence it follows is unchanged: malformed LINES remain skipped and named. The two rules govern different failures — a line that is not parseable JSON, and a parseable object whose keys do not satisfy the contract — and neither subsumes the other.

In `SPECIFICATION/scenarios.md`, add two scenarios:

```
## Scenario: A malformed mapping-store row is refused at write with its offending key named

Given a surface about to write a mapping-store row that does not satisfy the durable-key contract

When the surface performs the write

Then the write is refused and the offending key is named

And the mapping store is left byte-unchanged

And no partially-corrected row is written in its place

## Scenario: A pre-existing non-conforming row does not block an unrelated store rewrite

Given a mapping store already holding one row that does not satisfy the durable-key contract

And a maintenance path that rewrites the store without introducing or changing that row

When the rewrite runs

Then the rewrite completes and the unrelated rows are written

And the non-conforming row is surfaced rather than silently rewritten or silently dropped

And the rewrite is not refused on account of that row
```

Each added scenario heading requires one corresponding `tests/heading-coverage.json` entry with `spec_root` `SPECIFICATION` and `spec_file` `scenarios.md`. Those entries MAY carry `test: "TODO"` until the implementing work lands, which the existing heading-coverage check reports as a warning rather than a failure.

## Proposal: The unresolved-epic projection is a read-time value and MUST NOT be persisted into the mapping store

### Target specification files

- SPECIFICATION/contracts.md
- SPECIFICATION/scenarios.md

### Summary

States that a mapping-store row's recorded `epic`, when present, MUST be the plan's ledger epic id, and that the in-memory placeholder a reader substitutes for an ABSENT epic MUST NOT be written back into the store. Adds the scenario that exercises the round-trip, and requires that a row carrying such a persisted placeholder be treated exactly as a row with no recorded epic.

### Motivation

The specification already rules on the absent-epic case, in two places and consistently: spec.md §"Track discovery and the mapping store" says a track assigned when the anchor cannot be read "simply carries no recorded `epic`", and contracts.md §"The restart interlock" says a track with no recorded epic id "is not respawned at all: the `ready` declaration is PRESERVED and the track surfaced". Absent is therefore a sanctioned, handled state with a specified consequence.

What is not ruled on is a THIRD state that the implementation can currently produce: a reader substitutes an in-memory placeholder for an absent epic so that downstream code has a value to carry, and a subsequent write can persist that placeholder as though it were data. The row then reads as having a recorded epic that is not a ledger epic id and never was.

This was measured in the live store of this deployment: one row carries such a persisted placeholder. The resolution predicate correctly reports it unresolved, so the type layer is behaving. The damage is elsewhere and is the reason this needs a clause rather than a bug fix. An audit exists specifically to surface rows whose epic is absent, and it keys on absence — so the moment the placeholder is persisted, the row is no longer absent, and the audit reports the store clean while an unresolvable row sits in it. Measured against the same store: the audit returns zero rows, and the placeholder row is not among them.

That is a check which cannot fire for the very condition it was built to catch, and it will stay that way for as long as a read-time projection is allowed to become stored data. Forbidding the write-back is the narrow fix; requiring that any such row already in the store be treated as having no recorded epic is what keeps the existing interlock behavior correct for rows written before the rule.

### Proposed Changes

In `SPECIFICATION/contracts.md`, in the **mapping store** bullet of §"Durable stores", after the sentence beginning "The `epic` value is the plan-state locator", add:

> A recorded `epic` MUST be the plan's ledger epic id as read from that plan's write-once metadata anchor. Where a reader substitutes an in-memory placeholder for an ABSENT `epic` so that downstream code has a value to carry, that placeholder is a READ-TIME projection and MUST NOT be written back into the store: absent and recorded are the only two persisted states, and the projection MUST NOT become a third. A row already carrying such a persisted placeholder MUST be treated exactly as a row with NO recorded `epic` — including by §"The restart interlock", which therefore does not respawn it, preserves its `ready` declaration, and surfaces the track.

In `SPECIFICATION/scenarios.md`, add one scenario:

```
## Scenario: A read-time placeholder for an absent epic is never written back into the store

Given a mapping-store row with no recorded epic

And a reader that substitutes an in-memory placeholder so downstream code has a value to carry

When a later write rewrites that row

Then the row is written with its epic still absent

And the placeholder does not appear in the stored row

And a row already carrying a persisted placeholder is treated exactly as a row with no recorded epic
```

This proposal introduces no new obligation on the absent-epic path itself; that path is already specified in both spec.md and contracts.md and is unchanged. The added scenario heading requires one corresponding `tests/heading-coverage.json` entry, which MAY carry `test: "TODO"` until the implementing work lands.

## Proposal: A surface that starts a tracked session records the attempt before spawning, and reconciles it with an outcome

### Target specification files

- SPECIFICATION/spec.md
- SPECIFICATION/contracts.md
- SPECIFICATION/scenarios.md

### Summary

Requires an authorized unattended operator surface to durably record a start-intent — naming the action, the target track, and the INVOKER — before it spawns a tracked session, and to reconcile that intent with an outcome afterwards, so that a spawn which fails or dies leaves an attempted-and-failed record carrying the error rather than no record at all. Adds the scenario that exercises the killed-spawn case.

### Motivation

Nothing in this specification currently says when a session-start attempt is recorded relative to the spawn it describes, and the ordering is the whole of the property. A record written after the act cannot describe an act that did not return. In this deployment the mutation surface journals exactly once, at the tail of its dispatch, so a start that does not survive its own spawn leaves nothing behind: no journal record, no error, and no evidence the attempt was ever made. The observable residue is a track that is simply gone, which is indistinguishable from a track that was never started.

The absence is not uniform, and that asymmetry is why this is stated as a general obligation rather than as a repair to one path. One start path already writes a durable claim before spawning and is therefore close to conforming; another writes nothing before the spawn at all, and its only pre-spawn step refuses on an occupied session name and records nothing when it passes. A rule scoped to the better-instrumented path would leave the reported one untouched.

The reconciliation half is required for the same reason and is easy to omit. Where a pre-spawn record does exist today, a failed spawn leaves it in place and unamended, so a dead attempt reads as live work — which is worse than no record, because it is a record that actively misleads. The invoker field is required because the operator question a start record must answer is not only whether an attempt happened but who made it; the surface's own record shape is the only place that can be discharged, since it is this repository's record and not an upstream one.

The scenario deliberately specifies the KILLED spawn rather than merely the failed one. A control that asserts the record's CONTENT cannot distinguish a record written before the spawn from one written after it; only interrupting the act between the spawn and the return can.

### Proposed Changes

In `SPECIFICATION/spec.md`, in §"Non-interference with tracked work", in the paragraph granting the authorized unattended operator surface its carve-out, after the clause "and, when it is the surface assigning a track, to record that plan's ledger epic id into the track's mapping-store row at assignment", add a following sentence:

> When such a surface STARTS a tracked session, it MUST durably record a start-intent BEFORE the spawn, naming the action, the target track, and the INVOKER on whose behalf it acts; and it MUST reconcile that intent with an outcome once the spawn resolves. A spawn that fails, or that does not return at all, MUST therefore leave an attempted-and-failed record carrying the error — never an absent record, and never a record left standing as though the attempt were still live. This obligation attaches to EVERY start the surface performs, not only to those whose path happens already to write a pre-spawn record.

In `SPECIFICATION/contracts.md`, in §"Durable stores", add to the introductory sentence's set a note that the start-intent record is written to the authorized operator surface's own runtime state under the per-repository gitignored scratch area named by spec.md §"Non-interference with tracked work", and that it MUST carry the action, the target track, the invoker, and — once the spawn resolves — its outcome. It MUST NOT be written under `plan/`, which that same section forbids the surface from writing.

In `SPECIFICATION/scenarios.md`, add one scenario:

```
## Scenario: A killed session start leaves an attempted-and-failed record naming its invoker

Given an authorized unattended operator surface about to start a tracked session

When the surface is killed after the spawn is issued and before it returns

Then a start-intent record written before the spawn is on file

And that record names the action, the target track, and the invoker

And the track is not left reading as live work on the strength of that record

And the absence of a session is distinguishable from a start that was never attempted
```

The added scenario heading requires one corresponding `tests/heading-coverage.json` entry, which MAY carry `test: "TODO"` until the implementing work lands. This proposal states WHEN the record is written and WHAT it carries; it does not prescribe the record's serialization format, which remains an implementation choice.
