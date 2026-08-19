---
topic: tighten-parked-delivery-floors
author: foreman-fixes-to-blocking-pickers
created_at: 2026-08-19T03:50:00Z
---

## Proposal: Pin the status-agnostic keying, and state the degraded-snapshot leg

### Target specification files

- SPECIFICATION/spec.md
- SPECIFICATION/scenarios.md

### Summary

Two gaps in the v020 parked-delivery floors, both raised as non-blocking
findings by that version's own independent ratification review and deferred
rather than folded in. The first is that v020's load-bearing
MUST-NOT-key-on-status clause is not actually pinned by any scenario. The
second is that the delivery-routing floor is silent on what the foreman does
when the daemon snapshot is degraded.

### Motivation

v020's attention membership carries an explicit floor: it MUST be keyed on the
picker being open and MUST NOT be keyed on any particular row status. That
clause exists because of a measurement — the session in the originating
incident reported a picker-stall status, while the negative control reported
the human-blocked status, and both had the picker open. A condition keyed on
the human-blocked status literal, which is the natural reading of the incident
report, would have missed the very case the membership exists to catch.

But the scenario pinning that membership opens only with "Given a tracked
session whose row reports an open picker". An implementation that keyed on a
status literal could satisfy that scenario with a fixture that happens to use
the human-blocked status, and pass. The normative clause is therefore
unenforced by the scenario set: what is missing is not a fix but the thing
that would CATCH a regression. This matters beyond the one membership, because
a consumer treating the status vocabulary as a stable contract is a defect
this project has already had — the daemon emitted a picker-stall status while
an actuator accepted only the human-blocked literal, which made a human-gated
valve undeliverable in exactly the state it exists for.

Separately, v020's delivery-routing floor requires the foreman to determine
picker state "from the daemon's own row" but never says what happens when
there is no usable row. The snapshot contract already tells a consumer how to
READ a degraded snapshot — treat an absent, unreadable, or unknown-schema
snapshot as absent, do not best-effort-parse it, and surface that it could not
be read — but it does not say whether the foreman then holds the context or
delivers it anyway. That silence sits under a floor whose entire purpose is to
prevent a failure that is silent at both ends, so leaving the degraded case to
inference is the wrong default. The corresponding actuator-side decision has
already been made in this project's implementation: a row lacking the
picker-open field fails closed and refuses rather than proceeding.

### Proposed Changes

In scenarios.md, strengthen the Given of the scenario "A message queued behind
an open picker is surfaced as attention" so it pins the keying clause rather
than merely being consistent with it. Add a clause establishing that the row's
status is NOT the human-blocked status, so that an implementation keyed on the
human-blocked status literal FAILS this scenario. The rest of the scenario is
unchanged.

The clause is deliberately phrased as the governed NEGATIVE ("not the
human-blocked status") rather than by naming the picker-stall status. The
picker-stall surface is referenced in v020's prose but is defined nowhere in
the ratified tree, and a normative scenario should not take a load-bearing
dependency on an ungoverned term. The negative form is also the stronger
assertion: it excludes every status keyed on by a naive implementation, not
just the one the originating incident happened to show.

In spec.md §"Relay and escalation discipline", extend the delivery-routing
floor with its degraded-snapshot leg: where no usable row is available for the
session — because the snapshot is absent, unreadable, of an unknown schema, or
stale — the foreman MUST treat the picker state as UNDETERMINED and MUST NOT
deliver decision-relevant context as an ordinary asynchronous message on the
assumption that no picker is open. It holds the context under the same bounded
re-check the floor already requires, and surfaces that the row could not be
read. An undetermined picker state MUST fail closed toward holding, because
the failure this floor prevents is silent at both ends: an unwarranted hold is
visible to the holder and bounded, while an unwarranted delivery is observed
by no one.

Add a scenario in scenarios.md pinning that degraded leg: given the foreman
holds decision-relevant context and no usable row is available, it treats the
picker state as undetermined, does not deliver as an ordinary asynchronous
message, holds under a bounded re-check naming its release condition, and
surfaces that the row could not be read. This scenario accompanies the new
MUST rather than leaving it prose-only, matching the one-scenario-per-floor
pattern the rest of "Relay and escalation discipline" follows — the omission
of exactly such a scenario was a blocking finding against v020 and is not
repeated here.
