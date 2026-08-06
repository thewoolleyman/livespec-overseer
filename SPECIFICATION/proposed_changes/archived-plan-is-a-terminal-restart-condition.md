---
topic: archived-plan-is-a-terminal-restart-condition
author: claude-opus-5
created_at: 2026-08-06T09:57:46Z
---

## Proposal: An archived plan is a terminal restart condition, distinct from a missing supervision artifact

### Target specification files

- SPECIFICATION/spec.md
- SPECIFICATION/scenarios.md

### Summary

The daemon's supervisor restart path gates on the EXISTENCE of plan/<topic>/supervisor-handoff.md and treats every absence identically, surfacing a missing-artifact condition. That conflates two states with opposite meanings: a thread that was correctly archived (the artifact moved with its directory, and the track should retire) and a live thread whose binder is genuinely absent (an anomaly worth surfacing). This proposal requires the daemon to distinguish them using the DIRECTORY-level archived-or-deleted test it already performs, retiring the track terminally and without a missing-artifact alert when the plan is archived or gone, and preserving today's alert only for a live plan directory whose binder is absent. It adds no new file-level probe and widens no existing allowance.

### Motivation

Measured 2026-08-06 in livespec-overseer against work-item overseer-y26 and epic overseer-4w2m. The tombstone prohibition in spec.md is load-bearing precisely because a residual live directory leaves a finished thread eligible for nudges, wrap-up injection, and restart. The prohibition is ratified and mechanically enforced, yet thirteen hours after its fleet-wide ratification a supervisor in a sibling repository deliberately recreated a stub at the live path and explained why: the respawn prompt named a path the archive had removed, and the alert it produced named a MISSING FILE. The ban removed the stub; it never corrected the message that asks for one. So the enforcement holds while its cause stays open, and competent sessions keep re-deriving the banned workaround from the same pressure.

The originally-scoped remedy — resolving the binder at either plan/<topic>/ or plan/archive/<topic>/ so an archived thread boots from its archive — was rejected on re-measurement because it contradicts this specification. Discovery excludes archived plans, so an archived thread is not a track at all; making its binder resolvable would make archived threads bootable by design, reintroducing in the daemon exactly the hazard the tombstone prohibition exists to prevent. Re-measurement also showed the mapping store holding nineteen rows with zero dangling targets, confirming that archive garbage-collection already works and that the residue is narrower than the original scope assumed: the window between an archive merging and the next collection tick, and the daemon's inability to name the archived case as archived.

The existing directory-level archived-or-deleted test already separates the two states, and directory enumeration is already permitted, so the correct fix reinforces the invariant rather than undercutting it.

### Proposed Changes

In `spec.md`, in the passage governing the supervisor pair member's restart (the clause stating that the respawn is gated on the supervision artifact existing, re-checked immediately before the act), the specification MUST distinguish the two absences rather than treating the artifact's absence as a single condition.

The daemon MUST, when that artifact is absent, evaluate the same DIRECTORY-level archived-or-deleted test that governs mapping-row garbage collection — the test in which an ACTIVE `plan/<topic>/` wins over any same-named archived copy — and branch on its result:

- When the plan directory is archived or deleted, the outcome MUST be a distinct TERMINAL condition. The daemon MUST NOT restart, MUST NOT surface a missing-artifact condition, and MUST retire the track rather than hold it as anomalous. The condition surfaced MUST name the thread as ARCHIVED, so that no reader can reasonably infer that restoring a file at the live path is the remedy. This clause is a direct consequence of the tombstone prohibition already stated in this document: a correctly archived thread MUST NOT produce a signal whose plain reading asks for a stub at the live path.

- When the plan directory is present and the supervision artifact is nonetheless absent, the existing behavior MUST be preserved unchanged: the `ready` declaration is preserved, no restart occurs, and the missing-artifact condition is surfaced. That state is genuinely anomalous and MUST remain visible.

The specification MUST state explicitly that this branch introduces NO new file-level probe and does NOT widen the single bounded existence probe permitted in §"Non-interference with tracked work" and §"Track discovery and the mapping store". The archived-or-deleted evaluation is a DIRECTORY test, already permitted by the enumeration allowance; the daemon MUST NOT open, read, hash, or take content or modification-time dependence on anything under a plan tree in order to make this distinction. The resume artifact for a supervisor pair member MUST remain `plan/<topic>/supervisor-handoff.md` and MUST NOT be resolved from `plan/archive/<topic>/`; an archived thread is not a track and MUST NOT be made bootable.

In `scenarios.md`, a new `## Scenario` MUST be added covering the archived case, and it MUST be paired with a scenario or scenario clause covering the live-directory control so the distinction is exercised in both directions:

```
## Scenario: An archived plan retires its supervisor track instead of reporting a missing artifact

Given a watched repository whose plan topic has been archived, so that plan/<topic>/ is absent and plan/archive/<topic>/ is present

And a supervisor pair member for that topic whose mapping row has not yet been garbage-collected

When that supervisor declares ready

Then the daemon does not restart it

And the condition surfaced names the thread as archived

And no missing-supervision-artifact condition is surfaced

And the daemon performs no file-level probe under the archived plan directory

## Scenario: A live plan directory with an absent supervision artifact still reports the missing artifact

Given a watched repository whose plan topic directory plan/<topic>/ is present

And that topic's plan/<topic>/supervisor-handoff.md does not exist

When the supervisor pair member for that topic declares ready

Then the daemon does not restart it

And the missing-supervision-artifact condition is surfaced

And the ready declaration is preserved
```

The project links clauses to scenarios, so the accepting revision MUST co-edit `tests/heading-coverage.json` atomically with these additions.
