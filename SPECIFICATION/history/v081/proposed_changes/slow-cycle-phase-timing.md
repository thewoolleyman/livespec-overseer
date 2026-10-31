---
topic: slow-cycle-phase-timing
author: claude-opus-5-5
created_at: 2026-10-31T20:27:28Z
---

## Proposal: Every cycle records its own wall time and phase timing

### Target specification files

- SPECIFICATION/contracts.md
- SPECIFICATION/scenarios.md

### Summary

States that the daemon writes one diagnostic line per cycle to its event history, carrying the cycle's wall time, the seconds spent in discovery, per-track observation and acts, and the count and total seconds of Herdr requests by kind. Adds one scenario.

### Motivation

Routed by the groom regroom of overseer-uzvcbn.9 (overseerd cycle regressed from ~15 s to ~390 s per tick), whose classifier judged per-cycle timing a behaviour the specification does not state. Measured 2026-10-31 from the daemon's event history: instance 7e30956e (v5.41.2) averaged 388 s per cycle against the roughly-ten-second cadence contracts.md section "Daemon invocation" states, and the drift had climbed from 13-25 s (2026-10-04) through 106-126 s (2026-10-20) without the daemon's own output ever saying which phase dominated. The cause had to be reconstructed by hand from per-request latencies (`herdr pane list` ~0.5 s, `pane read` ~0.03 s, `process-info` ~0.05 s) and call-site counting. The factory slices overseer-6ic2om (one Herdr listing per server per cycle) and overseer-vl2pqz (slow acts off the cycle) fix the measured causes; this record is what lets an operator see the next regression as it happens instead of three weeks later.

### Proposed Changes

In contracts.md section "Daemon invocation", in the bullet that begins "Standard error is the timestamped event history.", append:

The daemon MUST write exactly one `overseer:` diagnostic line per cycle, after that cycle's acts complete, carrying: the cycle's wall time in seconds; the seconds spent in discovery, in per-track observation, and in acts; and, for each kind of request the daemon issued to a Herdr server in that cycle (a request kind is the Herdr operation invoked, such as a pane listing, a pane read or a foreground-process query), the request count and total seconds. A cycle that issued no Herdr request MUST still write the line, with no Herdr request kinds listed. The line is a diagnostic, not an alert: it MUST NOT be prefixed `overseer[SURFACE]:` and MUST NOT carry track coordinates.

In scenarios.md, add:

## Scenario: Every cycle records its own timing

Given a running daemon supervising tracks on a Herdr server

When a cycle completes

Then the event history carries one diagnostic line for that cycle naming its wall time and the seconds spent in discovery, per-track observation and acts

And that line names the count and total seconds of each kind of Herdr request the cycle issued

And the line is not an operator alert

In tests/heading-coverage.json, the revise that accepts this proposal MUST add a row for the new scenario heading with `"test": "TODO"` and `work_item` naming the factory slice filed to implement it, per the repository's convention for a scenario ratified ahead of its implementation.

## Proposal: A cycle over 30 seconds is surfaced once, naming its dominant phase

### Target specification files

- SPECIFICATION/contracts.md
- SPECIFICATION/scenarios.md

### Summary

States that a cycle whose wall time exceeds 30 seconds raises one daemon-level `slow-cycle` surface notice naming the cycle's dominant phase and its share of the wall time, edge-triggered per spec.md "Notify, never block" so a run of slow cycles is reported once and re-arms only after a cycle completes within 30 seconds. Adds two scenarios.

### Motivation

Same origin as the per-cycle timing record: overseer-uzvcbn.9's regroom, 2026-10-31. A diagnostic line per cycle is history; nobody reads it until something is already wrong. On 2026-10-31 the harm was found only because a session that declared `ready` at 14:36:43Z was not replaced until 14:57:19Z, 21 minutes later, and every wrap-up, restart, stall alert and relayed gate on the fleet was delayed by the same factor for weeks with no alert. Thirty seconds is three times the stated ten-second cadence: well above ordinary jitter, and well below the 388 s the daemon actually reached. Edge-triggering follows the existing rule for every alert, so a fleet stuck slow does not flood the event history with one notice per cycle.

### Proposed Changes

In contracts.md section "Daemon invocation", in the bullet that begins "Standard error is the timestamped event history.", append after the per-cycle diagnostic line clause:

When a cycle's wall time exceeds 30 seconds, the daemon MUST emit one daemon-level `overseer[SURFACE]:` notice of kind `slow-cycle` naming that cycle's wall time, its dominant phase (the phase among discovery, per-track observation and acts that took the most seconds), and that phase's share of the wall time as a whole-number percentage. The notice MUST be edge-triggered per spec.md section "Notify, never block": while consecutive cycles each exceed 30 seconds the daemon MUST NOT emit a further `slow-cycle` notice, and the condition MUST re-arm only when a cycle completes within 30 seconds. Like every other daemon-level notice, it MUST carry no track coordinates. The notice MUST NOT pause, skip or alter any act; it only reports.

In scenarios.md, add:

## Scenario: A slow cycle is surfaced once with its dominant phase

Given a running daemon whose previous cycle completed within 30 seconds

When a cycle takes longer than 30 seconds

Then the daemon emits one slow-cycle surface notice naming that cycle's wall time, its dominant phase and that phase's share of the wall time

And the notice carries no track coordinates

And no act is paused or skipped because of it

## Scenario: A run of slow cycles is surfaced once until a cycle completes in time

Given a daemon that has emitted a slow-cycle surface notice

When the following cycles also take longer than 30 seconds

Then the daemon emits no further slow-cycle notice

When a cycle then completes within 30 seconds and a later cycle takes longer than 30 seconds

Then the daemon emits one new slow-cycle notice for that later cycle

In tests/heading-coverage.json, the revise that accepts this proposal MUST add a row for each new scenario heading with `"test": "TODO"` and `work_item` naming the factory slice filed to implement it.
