---
topic: a-daemon-wrap-up-whose
author: claude-opus-5-5:herdr-overseer
created_at: 2026-11-13T02:51:30Z
---

## Proposal: Submit the daemon's own pending wrap-up with Enter only

### Target specification files

- SPECIFICATION/spec.md
- SPECIFICATION/scenarios.md

### Summary

A daemon wrap-up whose submission was unconfirmed and which sits exactly in an otherwise idle, gate-free composer is completed Enter-only on a later observation instead of holding the track at settling; non-daemon composer text is never submitted; a payload pending past a bounded window is logged.

### Motivation

overseer-llrj5k: on fleet daemon 5.54.1 the fleet-flaky-tests wrap-up (pasted 19:30:51Z, submit failed 19:30:55Z while the seat was mid-turn) sat unsubmitted for nearly three hours with no further event, because an idle reading requires an EMPTY composer and the daemon's own payload made the pane never idle; the latched track could not be wrapped up or restarted. The dispatch-stage tier judge held the fix as spec-change: the Enter-only self-heal is stated for the restart's resume prompt only.

### Proposed Changes

In spec.md, at the end of "## The escalating wrap-up", after the paragraph on the expiry-notice, add this paragraph:

In addition to, and without narrowing, the completion retry for an unconfirmed delivery above, a wrap-up paste whose submission the daemon could not confirm can leave the daemon's own payload sitting in the composer, and that payload MUST NOT itself hold the track out of acting. When a later observation, while the round the payload was pasted for is still open, shows the composer holding EXACTLY the daemon's retained wrap-up payload (its full text, or the runtime's collapsed placeholder for a single paste of exactly that payload), and every other leg of the guarded-paste predicate of constraints.md §"Acting safety" holds (no busy evidence, no structured gate, a settled input region and positive pane identity), the daemon MUST re-send the SUBMISSION only. The retained payload stands in for the empty-input leg and for nothing else. The daemon MUST NOT paste again, MUST NOT open a new round or notify a new band, MUST NOT submit a payload whose round has closed, and MUST NOT treat any composer text other than its retained payload as authority to submit: composer text the daemon did not author stays governed by the rule that the daemon never injects over or submits typed input, and a daemon that no longer holds the retained payload, for example after its own restart, MUST NOT submit anything on this authority. While its own payload stays unsubmitted for longer than 10 minutes, the daemon MUST log an event naming the track and stating that its own wrap-up is pending in the composer; per §"Notify, never block" the event is emitted on entry and re-arms once the payload leaves the composer.

In scenarios.md, add:

## Scenario: A daemon wrap-up left unsubmitted in an idle composer is submitted with Enter only

Given a tracked session whose wrap-up paste was written to the pane and whose submission was not confirmed

And while that round is still open the composer holds exactly that wrap-up payload on a pane with no busy evidence, no structured gate, a settled input region and positive pane identity

When the daemon next observes the track

Then it re-sends the submission only and does not paste again

And the track is not held at settling by its own pending payload

And composer text the daemon did not author, or a payload whose round has closed, is never submitted

## Scenario: A daemon wrap-up pending in the composer past its window is surfaced

Given a daemon wrap-up payload has stayed unsubmitted in a track's composer for longer than 10 minutes

When the daemon observes the track

Then it logs one event naming the track and stating that its own wrap-up is pending in the composer

And the event re-arms once the payload leaves the composer

tests/heading-coverage.json gains a TODO entry for each new scenario heading, owed by the linked implementation item.
