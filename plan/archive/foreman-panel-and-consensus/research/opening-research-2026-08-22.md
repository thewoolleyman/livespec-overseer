# Making the reviewer panel survive its own failure modes

Opening research note for `plan/foreman-panel-and-consensus`. Ledger anchor `overseer-6l7v`.

Written 2026-08-22 when this thread was cut out of `plan/foreman-improvements`
(anchor `overseer-au3pt3`) by the grooming drain pass, at the maintainer's
direction and on their selected cut.

## Why this thread exists separately

The panel children share a property none of the other clusters have: **every one
of them is a way the panel produces a wrong or missing verdict while reporting
success**. They are not edge-coupled — a dependency scan over all 38 children of
`overseer-au3pt3` found no `blocks` edge anywhere in this cluster — but they are
one subject, and that subject is failure-mode containment rather than feature
work.

Three of the six were `pending-approval` at the cut and two were P1, which is
what makes the cluster worth its own supervised session rather than a corner of a
larger thread.

## What this thread holds

| child | status at cut | scope |
|---|---|---|
| `overseer-cdwm` | acceptance | panel aborts the whole convening on an uncaught reviewer timeout, writing no result |
| `overseer-suihv6` | pending-approval | panel spends three reviewers on a structurally EMPTY dossier, then reports the outcome |
| `overseer-au3pt3.12` | pending-approval | `foreman-consensus` caches a `panel_size_mismatch` structural refusal under the request key |
| `overseer-kjjufq` | pending-approval | both anthropic reviewers fail at the tool layer; the record append reports `invalid_report` |
| `overseer-b6q2` | ready | implement the v026 typed-ruling vocabulary the spec mandates and the code does not provide |
| `overseer-5stpf2` | **closed 02:07:58Z** | majority opinion vs a decision matrix with no majority path |

`overseer-5stpf2` closed itself minutes after being moved here, by the session
that was working it. It is recorded above because the thread inherits its
conclusion: the standing orders and the decision matrix disagreed about minority
outcomes, and `b6q2`'s typed-ruling vocabulary is the surface where that
resolution has to land.

## The seam with the wait-premise thread

`plan/foreman-wait-premises` (`overseer-vszm`) owns **when a panel must be
convened** — the positive convene-criterion, the consensus-overdue condition, and
what a waiting premise means. This thread owns **what the panel does once
convened**. The convene call is the seam. A change that alters the convene
criterion belongs there; a change that alters reviewer handling, caching, or
ruling vocabulary belongs here.

Stated explicitly because `overseer-a3l6x2` ("panel-first discipline") sits on the
other side of that line and reads like it belongs here.

## Explicit deferrals

- **Convene criteria and consensus-overdue** — deferred to `overseer-vszm`.
- **The actuator that carries a panel result to the ledger** — deferred to
  `overseer-au3pt3`, retained as the actuator thread.
- **Which model a reviewer seat runs** — `overseer-vx4ky3.7` (seat-model
  measurement) went to `plan/foreman-seats-and-plan-records` (`overseer-ow7c`)
  because it is a seat-identity question, not a panel-behaviour one.

## Read first

- `overseer/foreman_consensus_decision.py` and its neighbours — note that
  `overseer-hgq4wi.35` is separately working the LLOC soft-band debt on that same
  module, under `plan/test-and-gate-integrity`. Coordinate before large edits.
- `SPECIFICATION/spec.md` v026, the typed-ruling vocabulary `b6q2` must implement.
- The ledger anchor `overseer-6l7v` and each child's own acceptance field.
