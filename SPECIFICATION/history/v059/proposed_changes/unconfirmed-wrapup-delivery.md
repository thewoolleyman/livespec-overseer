---
topic: unconfirmed-wrapup-delivery
author: claude-opus-5-5:herdr-overseer
created_at: 2026-10-15T09:20:45Z
---

## Proposal: An unconfirmed wrap-up delivery keeps its round open

### Target specification files

- SPECIFICATION/spec.md
- SPECIFICATION/contracts.md
- SPECIFICATION/scenarios.md

### Summary

Distinguish a wrap-up paste that provably FAILED (no write landed) from one whose delivery the daemon cannot CONFIRM (the write may have landed). Only a provable failure un-opens the round. An unconfirmed delivery keeps the stamped round open, so a declaration that answers a wrap-up which did land certifies. Delivery confirmation must not report failure for a payload that has left the input after it was observed there.

### Motivation

MAINTAINER DIRECTIVE 2026-10-15 (highest priority, relayed from the overseerd bottom pane). Measured on daemon 5.28.3: petri-factory-on-gmktec (livespec-orchestrator-beads-fabro, herdr w6:pH) received the 08:09:30Z wrap-up. It appears exactly once in the pane scrollback, and the session wound down and wrote ready at 08:22:20Z. The daemon nevertheless logged wrapup-injection-submit-failed and un-opened the round (stamp at=null, session_identity=null), so the restart was refused at 08:23:21Z ('round closed before durable binding'). gitops-fleet-capacity-monitoring followed the same sequence on 2026-10-14 (11:12:50Z submit-failed, 11:16:29Z refused, 11:20:59Z ready) and was held for about 15h. Cause: the herdr submit confirmed delivery only by seeing the pane go busy within about one second after Enter, so a delivered wrap-up whose turn showed no busy frame in that window was reported failed. Its in-memory submit state then stayed stuck, so no later wrap-up was ever pasted to that pane. The current text requires un-opening on a FAILED opening paste, which made a cooperating session's ready permanently uncertifiable. The maintainer ruled that when the daemon cannot prove delivery it must keep the round open (or re-deliver with a stamp) so a ready can still certify, and must not strand the session.

### Proposed Changes

spec.md §"The supervision round": after the paragraph beginning "A round whose wrap-up never landed is a different case" add:

> A paste is FAILED only when the daemon can show that the payload never reached the input: the write itself was refused, or the input never showed the payload and is unchanged. A paste whose effect the daemon cannot determine is UNCONFIRMED, not failed: the write may have landed, the payload may have been observed in the input and then left it, or the runtime may have begun a turn the daemon did not observe. An unconfirmed opening paste MUST NOT un-open the round. The daemon MUST keep the stamped round open, MUST surface the unconfirmed delivery, and MUST retry delivery on a later observation, so a declaration answering a wrap-up that did land certifies against that round. Delivery confirmation MUST treat a payload that was observed in the input and then left it, leaving the input empty, as delivered, and MUST NOT report failure for it. A per-pane delivery attempt whose payload has left the input MUST be resolved rather than held, so a later wrap-up to that pane is pasted afresh. Only a provably failed paste un-opens the round, exactly as above.

contracts.md §"The wrap-up injection": in the message-delivery bullet, after "never by the pane going busy alone." add: "Submission is confirmed when the runtime begins the turn OR when the payload, once observed in the input, has left it and the input is empty; a payload whose delivery cannot be determined is UNCONFIRMED and keeps the stamped round open (spec.md §\"The supervision round\"), while only a provably failed paste un-opens it."

scenarios.md: add

```
## Scenario: An unconfirmed wrap-up delivery keeps its round open

Given a tracked session whose wrap-up paste was written to the pane

And the daemon could not confirm the submission

When the daemon records the outcome

Then the stamped round stays open and the unconfirmed delivery is surfaced

And a ready the session writes after the stamp certifies against that round

## Scenario: A payload that left the input after it was observed there counts as delivered

Given a wrap-up paste observed in the session's input

And the daemon pressed Enter

When the input is next observed empty without a busy frame having been seen

Then the delivery is confirmed and no failure is reported

And a later wrap-up to that pane is pasted afresh rather than answered from the earlier attempt
```

The revise MUST co-edit `tests/heading-coverage.json`, mapping each new scenario heading to an integration-tier test.
