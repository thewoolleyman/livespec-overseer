---
topic: session-start-respects-live-seat-record
author: claude-opus-5-5:herdr-overseer
created_at: 2026-11-14T00:51:29Z
---

## Proposal: A session-starting surface respects the live-seat record, pinned by a scenario

### Target specification files

- SPECIFICATION/scenarios.md
- SPECIFICATION/spec.md

### Summary

SPECIFICATION v106 §"Supervision across machines" requires the sanctioned relaunch entrypoint and every other session-starting surface to take or verify a plan topic's live-seat record for its own machine before launching, and not to launch when the record names another machine. No scenario pins that MUST. This proposal adds one, and it also rewords spec.md's "OPAQUE LOCATOR" sentence, which still reads as if the daemon touches nothing on the plan epic beside the v106 live-seat record held there.

### Motivation

The v106 revise's post-step doctor phase found that this load-bearing MUST had no scenario (check doctor-llm-subjective-behavior-coverage). The finding was deferred and journaled on overseer-5y7ebe, so the implementation item for the session-start gate, overseer-bluagz, waits on this proposal. The coordinator's grade of #3022 asked for the OPAQUE LOCATOR clarification to be folded into the same proposal.

### Proposed Changes

In SPECIFICATION/scenarios.md, add immediately after "## Scenario: A seat moved between machines is bound only after the old seat releases":

> ## Scenario: A session-starting surface does not launch while another machine holds the topic's live seat
>
> Given plan topic T's live-seat record names machine M1 and a seat there
>
> When the sanctioned out-of-band relaunch entrypoint on machine M2 is asked to launch a session for topic T
>
> Then it does not launch a session
>
> And its refusal names T and M1
>
> And T's live-seat record still names M1
>
> And no mapping row for T on M2 is re-bound

In SPECIFICATION/spec.md, in the paragraph on the plan epic shared by a worker and its supervisor pair member, replace the sentence that begins "The daemon holds the epic id as an OPAQUE LOCATOR" up to and including "never inspects them as restart authorization." with:

> The daemon holds the epic id as an OPAQUE LOCATOR for the plan's handoff entries — it hands the id and the entity name to sessions, and it never reads those entries, never hashes them, and never inspects them as restart authorization. The one thing the daemon itself reads and writes on that epic is the topic's live-seat record of §"Supervision across machines", which is not a handoff entry and authorizes no restart on its own.

Both edits are wording within existing sections; no section heading changes. The new scenario's heading needs a row in tests/heading-coverage.json and its debt register, owned by overseer-bluagz, the implementation item for the session-start gate.
