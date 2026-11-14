---
topic: live-seat-record-survives-epic-writes
author: claude-opus-5-5:herdr-overseer
created_at: 2026-11-14T09:17:12Z
---

## Proposal: The live-seat record survives writes to the plan epic, stated as a MUST and pinned by a scenario

### Target specification files

- SPECIFICATION/spec.md
- SPECIFICATION/scenarios.md

### Summary

SPECIFICATION v108 states, in spec.md §"Supervision across machines", paragraph "**One live seat per plan topic.**", that the live-seat record "is held apart from the epic's own fields, so no write to the epic can alter or erase it." That is a load-bearing invariant, but it is stated declaratively, with no BCP14 keyword and no scenario. This proposal restates the sentence as a MUST and adds one scenario that pins it. The record's location, contents, writes, readers and every other rule of the section are unchanged.

### Motivation

The v107/v108 revise's post-step LLM doctor phase (PR #3042) found doctor-llm-subjective-behavior-coverage on this sentence: behaviour the implementation must honour, with no MUST clause and no scenario. It is the reason v108 exists. The beads CLI's --set-metadata is a client-side read-modify-write of the epic's whole metadata column, so a record kept in epic fields is silently erased by any handoff or next-action write, which admits a second seat. legacy-coordinator-agent's grade of #3042 asked that the spec carry this as a scenario, not only as a test. The implementation item overseer-fnu5gl already carries the matching Definition-of-Done bullet.

### Proposed Changes

In SPECIFICATION/spec.md §"Supervision across machines", paragraph "**One live seat per plan topic.**", replace the sentence

> It is held apart from the epic's own fields, so no write to the epic can alter or erase it.

with:

> It MUST be held apart from the epic's own fields, so that no write to the epic, such as a handoff entry or a next-action write, alters or erases it.

In SPECIFICATION/scenarios.md, add immediately after "## Scenario: A session-starting surface does not launch while another machine holds the topic's live seat":

> ## Scenario: A write to the plan epic leaves the topic's live-seat record intact
>
> Given plan topic T's live-seat record names machine M1 and a seat there
>
> When a session writes a handoff entry and a new next action onto T's plan epic, rewriting the epic's metadata
>
> Then T's live-seat record still names M1 and that seat
>
> And a take of T's record from machine M2 still fails

No heading other than the new scenario's is added, removed or renamed. The new scenario heading needs a row in tests/heading-coverage.json and in its debt register, owned by overseer-fnu5gl, the implementation item for the live-seat record store.
