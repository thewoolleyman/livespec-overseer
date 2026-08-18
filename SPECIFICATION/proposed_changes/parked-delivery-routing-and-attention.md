---
topic: parked-delivery-routing-and-attention
author: foreman-fixes-to-blocking-pickers
created_at: 2026-08-19T01:40:00Z
---

## Proposal: Delivery routing to a picker-parked session, and a parked-delivery attention condition

### Target specification files

- SPECIFICATION/spec.md
- SPECIFICATION/contracts.md
- SPECIFICATION/scenarios.md

### Summary

A session parked on a blocking picker consumes no asynchronous input until a
human resolves that picker. Cross-session context sent to it renders in the
pane but is never processed, and the sender receives no signal that its
delivery has parked. Three floors are proposed: a sender-side routing rule
governing delivery to a picker-parked session, a picker-authoring rule
requiring long-lived questions to state where late-arriving context should
go, and a new report-only attention membership for a delivery observed parked
behind a picker.

### Motivation

Observed live on 2026-08-19. A session was parked on a picker choosing
between dispatching three children and leaving the thread parked. Its foreman
then delivered context bearing directly on that choice: a fleet capacity
resize had already discharged the escalation leg that motivated one of the
picker's options, and the delivery said so explicitly. The delivery rendered
below the picker overlay and was never consumed. The human answering the
picker could not see that better information had arrived unless they happened
to scroll the pane; the sender had no indication the delivery had parked.

The outcome is a silent mutual stall: the decision waits on a human, and the
context that would change that decision waits on the decision. Both ends
believe they are progressing. The delivery genuinely succeeded — it reached
the pane — so there is no error anywhere for either party to observe.

The condition was subsequently reproduced mechanically against the live pane
and a negative control. Every existing pane predicate returns identical
values for a picker with a parked delivery behind it and for an ordinary
picker, so nothing in the governed surface can presently distinguish them.

This is the delivery-side sibling of the operator-side escalation freeze
already governed by §"Relay and escalation discipline". That section governs
how the foreman surfaces a decision it cannot make. This proposal governs the
converse direction: how input reaches a session that is already parked on
one, and who is told when it cannot.

### Proposed Changes

In spec.md §"Relay and escalation discipline", add the delivery-routing floor.
Before a foreman delivers decision-relevant context to a supervised session,
it MUST determine from the daemon's own row for that session whether the
session is parked on a picker. Where the row reports a picker open, the
foreman MUST NOT deliver that context as an ordinary asynchronous message,
because such a delivery is not consumed while the picker stands and reports no
failure to the sender. It MUST instead either deliver through the picker's own
free-text response channel, where the picker offers one, or hold the context
and re-check on a bounded schedule. A hold MUST be bounded and MUST name the
condition that releases it; an unbounded hold merely relocates the stall to
the sender. This floor governs delivery routing only; it MUST NOT be read to
alter what may authorize a restart of a tracked session — the cardinal rule,
that a session is restarted only when it declares itself ready on the
filesystem, is unaffected by this proposal in every part.

Also in spec.md §"Relay and escalation discipline", add the picker-authoring
floor. Where the foreman raises a question that may stand open long enough to
accumulate later context, the question's own text MUST state where
late-arriving context is to be routed. This floor exists because the routing
rule above is available only to a sender that can read a daemon row; a human
sender cannot, and the question text is the only channel that reaches them.

In contracts.md §"NEEDS YOU membership", add the parked-delivery membership.
Membership also includes a tracked session whose row reports an open picker
and whose pane shows an undelivered inbound message queued behind that
picker. This is a distinct report-only member with normal coordinates; it
participates in the NEEDS YOU count and window badge, is edge-triggered,
clears when the picker resolves or the queued message is consumed, and
authorizes no act. Its rendered note MUST name the sender where the pane
makes it available, so the parked delivery can be attributed without reading
the pane. This membership is keyed on the picker being open, NOT on any
particular row status: the observed incident session reported a
picker-stalled status rather than a human-blocked one, so a status-keyed
condition would have missed the very case that motivates it. It is a distinct
condition from the picker-stall membership, which is keyed on the age of a
picker alone and reports nothing about what is queued behind it.

In scenarios.md, add a Given/When/Then scenario pinning the case: given a
tracked session parked on an open picker, when an inbound cross-session
message is queued behind that picker and remains unconsumed, then the session
appears as a report-only NEEDS YOU member naming the sender, no act is
authorized, and the member clears when the picker resolves or the message is
consumed. Add the negative leg in the same scenario or beside it: a session
parked on an open picker with no queued inbound message does NOT become a
member on this condition.
