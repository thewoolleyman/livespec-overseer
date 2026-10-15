---
topic: daemon-message-channel-delivery
author: claude-opus-5-5:herdr-overseer
created_at: 2026-10-15T12:43:37Z
---

## Proposal: Daemon messages may be delivered through a session-bound direct channel

### Target specification files

- SPECIFICATION/contracts.md
- SPECIFICATION/scenarios.md

### Summary

Allow the daemon to deliver its wrap-up, its keep-going nudge and its post-restart resume prompt through a direct message channel bound to the exact supervised session, as an ALTERNATIVE to the ONE atomic paste. Every guard, the stamp-before-delivery ordering and the DELIVERED / FAILED / UNCONFIRMED outcome rules apply unchanged. The daemon falls back to the guarded paste only after a provably FAILED channel delivery, never after an UNCONFIRMED one. The track's row and the daemon log record which path delivered each message. The picker-stall relay act is excluded and keeps its paste-without-submit form.

### Motivation

MAINTAINER RULING 2026-10-15, follow-on (3) of the busy-session wrap-up ruling (plan epic overseer-uzvcbn), filed as work item overseer-uepcr6: prefer delivering daemon messages as direct agent messages through harness or API messaging instead of typing into the TUI where possible. Typing into the TUI is the daemon's most fragile act. On daemon 5.28.3 a herdr wrap-up paste was mis-confirmed as failed and wedged two sessions for about fifteen hours (fixed by v059, released 5.29.0). Every paste also competes with the operator for the input box. The harnesses now expose per-session message channels: Claude Code sessions accept cross-session messages through a per-session socket and deliver them into the session's turn queue. overseer-uepcr6 cannot be dispatched as filed, because contracts.md section 'The wrap-up injection' mandates ONE atomic paste followed by a verified submission, and a factory run cannot change SPECIFICATION/. This proposal makes channel delivery a ratified alternative so the code half becomes dispatch-safe. Scope is deliberately conservative: the delivery mechanism changes, the decision to deliver does not. The guarded predicate is kept whole, including the input-box guards a channel would not strictly need; relaxing them is a separate question for a later change.

### Proposed Changes

contracts.md: add a new H2 section immediately before '## The keep-going nudge' (that is, directly after the bullets of '## The wrap-up injection'):

```
## Daemon message delivery channel

The wrap-up, the keep-going nudge and the resume prompt a restart delivers to
its successor are DAEMON MESSAGES. A daemon message MAY be delivered through a
direct message channel instead of the ONE atomic paste, when the session's
runtime offers a supported channel that is bound to the exact session the act
targets: the channel addresses that session's live process identity, the same
identity the round records or, for a resume prompt, the proven successor's.
A channel addressed only by topic name, pane or repository is not bound and
MUST NOT be used.

- Choosing the channel changes HOW a message is delivered, never WHETHER it
  is. Every guard that governs the act's paste governs its channel delivery,
  unchanged: the guarded predicate, the immediate pre-delivery re-read, the
  stamp written durably before delivery, the escalation bands, the message
  obligations, and every suppression.
- A channel delivery resolves to the same three outcomes as a paste (spec.md
  section "The supervision round"). It is DELIVERED only when the channel
  confirms that the addressed session accepted the message. It is FAILED only
  when the channel provably refused it or was unavailable before anything was
  sent. Every other outcome is UNCONFIRMED, and an UNCONFIRMED channel
  delivery keeps the round open exactly as an UNCONFIRMED paste does.
- After a FAILED channel delivery the daemon MAY fall back to the guarded paste
  in the same act. After an UNCONFIRMED channel delivery it MUST NOT paste the
  same message, because the message may already be queued in the session.
- The track's row and the daemon log MUST name the delivery path (channel or
  paste) of every daemon message, together with its outcome.
- The picker-stall relay act is NOT a daemon message under this section. It
  is pasted and never submitted, which a channel cannot express, so it keeps
  its paste form.
```

contracts.md '## The wrap-up injection', in the delivery bullet that begins '- The message is delivered as ONE atomic paste followed by a verified submission', append one sentence at its end: 'The message MAY instead be delivered through a direct channel under §"Daemon message delivery channel", which keeps every obligation in this section.'

scenarios.md: append three scenarios:

```
## Scenario: A daemon message is delivered through a session-bound channel when one is available

Given a supervised session whose runtime offers a channel bound to its live process identity

And the daemon owes it a wrap-up whose guarded predicate holds

When the daemon delivers the wrap-up

Then the message is sent through the channel and no keystroke is typed into the pane

And the round's stamp was written before the delivery

And the track's row and the daemon log name the channel as the delivery path

## Scenario: A failed channel delivery falls back to the guarded paste

Given a supervised session whose bound channel provably refuses a wrap-up

When the daemon records the outcome

Then it delivers the same wrap-up by the guarded paste in that act

And the daemon log names both the failed channel delivery and the paste

## Scenario: An unconfirmed channel delivery is never followed by a paste

Given a wrap-up sent through a bound channel whose acceptance could not be confirmed

When the daemon records the outcome

Then the round stays open and the unconfirmed delivery is surfaced

And the same wrap-up is not pasted into the pane
```

The revise MUST co-edit tests/heading-coverage.json with one TODO row per new scenario, owned by overseer-uepcr6 and registered in tests/heading-coverage-debt.json under the v067 spec-first admission (each scenario's H2 is introduced by this change), so the factory implementation of overseer-uepcr6 lands the tests.
