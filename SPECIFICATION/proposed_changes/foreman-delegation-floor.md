---
topic: foreman-delegation-floor
author: claude-opus-5
created_at: 2026-08-22T04:50:03Z
---

## Proposal: Full autonomy is authority over decisions, not over work

### Target specification files

- SPECIFICATION/spec.md
- SPECIFICATION/scenarios.md

### Summary

Add a delegation floor to the foreman operator contract: under full autonomy the foreman MUST NOT perform any track's deliverable, and the acts full autonomy authorizes are unsticking acts on the worker and the queue. The specification today constrains HOW the foreman mutates and forbids laundering authority through a typed ruling, but says nothing about WHOSE HANDS do a track's work, so a foreman that implements a stuck track's fix itself violates no ratified rule.

### Motivation

The standing orders that this repository's full_autonomy key was built to mechanize instruct the foreman to keep all work moving to done, and enumerate concrete acts, without ever bounding whose hands do the work. The maintainer identified on 2026-08-22 that this reads as permission for the foreman to do the work itself, which was never intended.

A foreman optimizing for momentum under an unbounded reading will, when a track is stuck and the fix looks small, simply make the fix. That HIDES the stall rather than curing it: the worker is left exactly as stuck, the reason it stalled is never surfaced, and the foreman's own loop is consumed by work it should have been routing. The failure is worst precisely when momentum pressure is highest.

The gap is real rather than theoretical. v030 already states that every mutation the foreman performs goes through its own actuator and never by keystroking into a structured gate, and that the foreman MUST NOT be authorized, through a ruling a supervised session executes, to reach any decision a direct action id could not have authorized it to reach. Both govern mechanism and authority. Neither governs execution: nothing in the ratified text distinguishes deciding that a change is correct from writing it.

### Proposed Changes

In `SPECIFICATION/spec.md`, in the section governing full autonomy and the decision rule, add a DELEGATION FLOOR alongside the four floors that already hold:

First, because the floor turns on a term the specification does not currently
use, `SPECIFICATION/spec.md` MUST define it where the foreman's vocabulary is
established:

- A track's DELIVERABLE is the work product that track exists to produce: any
  change to the repository's source, tests, or documentation that the track is
  assigned to make, together with the pull request carrying it. A deliverable is
  distinguished from the SUPERVISION ARTIFACTS the foreman itself produces --
  journal entries, typed rulings, panel verdicts, attention records, dispatch
  records, and findings -- which are the foreman's own output and are NOT a
  track's deliverable. Where a change could be read as either, it MUST be
  treated as the track's deliverable.

- A track's ASSIGNED WORKER is the non-supervisor pair member of that track, in
  the sense the specification already uses when it speaks of a worker and its
  supervisor sharing one epic. A track whose worker session does not exist, has
  exited, or is not attributable to the worker entity has NO assigned worker for
  the purpose of the floor below.


- The foreman MUST NOT perform any track's deliverable. It MUST NOT author or modify a track's source, tests, or documentation, and MUST NOT open a pull request carrying a track's own work, however small the change appears, however long the track has been stalled, and however confident or unanimous any panel is. No configuration value, `full_autonomy` included, MAY relax this, and it MUST NOT be panel-decidable.

- The acts full autonomy DOES authorize are UNSTICKING acts, on the worker and on the queue. The enumeration is closed: dispatching ready work; answering a parked question from the record or from a panel verdict; resolving a gate blocking a supervised pane; relaying a typed ruling, including a final relay; restarting a session that has declared itself ready, subject to the cardinal rule unchanged; verifying a claimed blocker and requiring the worker to proceed where that blocker does not hold; and filing findings.

- Where a track has no assigned worker, the authorized act is to get one assigned and started. The foreman MUST NOT absorb the work in the absence of a worker.

- The majority rule governs WHICH DECISION is reached; it MUST NOT be read to govern who executes the resulting work. A panel that unanimously concludes a change is correct authorizes the foreman to relay that conclusion, never to implement it.

- A foreman that has performed a track's deliverable is a REPORTABLE CONDITION and MUST be surfaced on the same observability surface that already reports the effective valve disposition, the effective decision rule, and whether a contradiction was found.

In `SPECIFICATION/scenarios.md`, add the covering scenarios:

- `## Scenario: A panel-authorized change is relayed to the worker rather than implemented by the foreman` — Given full autonomy resolves true and a constituted panel authorizes a typed action carrying a code change, When the foreman acts on that verdict, Then it relays the ruling to the assigned worker and no track deliverable is authored by the foreman seat.

- `## Scenario: A track with no assigned worker resolves to an assignment rather than to foreman-authored work` — Given full autonomy resolves true and a ready track carries no assigned worker, When the foreman acts, Then it assigns and starts a worker, and does not author the track's deliverable.

- `## Scenario: The delegation floor holds against a unanimous panel` — Given full autonomy resolves true and every reviewer agrees the foreman should make a one-line fix directly, When the verdict is evaluated, Then the act is refused as a floor violation rather than authorized.

Both new scenarios MUST be linked to their clauses through the project's heading-coverage registry in the same change, per the co-editing requirement in `spec.md` on self-application. Any row that names a test not yet written MUST carry the placeholder token in its `test` field rather than a prospective test identifier, since a mapped identifier reads as coverage regardless of what its reason says.
