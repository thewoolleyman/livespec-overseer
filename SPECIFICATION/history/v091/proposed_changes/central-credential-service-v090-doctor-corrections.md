---
topic: central-credential-service-v090-doctor-corrections
author: claude-opus-5-5-central-credential-service
created_at: 2026-11-08T23:17:43Z
---

## Proposal: An enforcement instruction the service has stopped serving is never served again

### Target specification files

- SPECIFICATION/contracts.md
- SPECIFICATION/scenarios.md

### Summary

v090 derived 'stop serving an instruction' from two records that can be deleted: the report store's copy of its outcome, kept for only seven days, and a newer instruction that supersedes it, which a pass may delete once its own outcome is held. When either is gone the service serves the old instruction again, and a client that has discarded its identifier acts on it a second time, breaking at-most-once. This keeps both records for as long as the instruction's record remains, and makes the service never serve a stopped instruction again.

### Motivation

Found by the independent post-step LLM doctor run on v090 (2026-11-08). The coordinator, legacy-coordinator-agent, ruled under R301 that all six findings of that run land together in one follow-up revised as v091, with one scoped post-step review over those six only, and that spec iteration for this plan then stops (scope events on overseer-iyfjbo). No implementation of enrolled-host delivery exists yet; overseer-3vnxkd owns it, and any slice of it that implements enforcement-instruction serving waits for v091. This was the run's one defect, confined to the enforcement-instruction path.

### Proposed Changes

In SPECIFICATION/contracts.md §"Enrolled-host delivery", in **Service stores**, replace the sentence:

"The service MUST keep each of those records for at least seven days, the longest window a refusal can name, so that a pass on the normal schedule reads each before it is discarded."

with:

The service MUST keep each of those records for at least seven days, the longest window a refusal can name, so that a pass on the normal schedule reads each before it is discarded. It MUST keep an enforcement-instruction outcome for longer where **Enforcement instructions** requires it.

In the same section, in **Enforcement instructions**, replace the two bullets:

"- The service MUST stop serving an instruction once the report store holds its outcome or a newer instruction supersedes it.
- A rotation pass MAY delete an instruction record once the report store holds its outcome or it is superseded."

with:

- The service MUST stop serving an instruction once the report store holds its outcome or a newer instruction supersedes it, and once it has stopped it MUST NOT serve that instruction again. The client MAY discard an identifier the service no longer serves, so serving that instruction again would let the client act on it a second time. The two rules below keep both conditions true for as long as the instruction's record remains.
- A rotation pass MAY delete an instruction record once the report store holds its outcome or it is superseded. It MUST NOT delete an instruction record while an older instruction record for the same session remains, so deleting a newer record never makes an older one the newest.
- The service MUST NOT discard an instruction's outcome from the report store while that instruction's record remains.

In SPECIFICATION/scenarios.md, immediately after the scenario "## Scenario: A client restarted after recording an instruction does not act on it again", add:

## Scenario: An instruction whose outcome was reported is never served again

Given the client applied an enforcement instruction to a remote session and reported its outcome

And the client has discarded that instruction's identifier

And more than seven days have passed since the report store recorded that outcome

And no rotation pass has deleted that instruction's record

When the client requests a delivery

Then the service does not serve that instruction

And the client does not act on it again


## Proposal: A return from silence is judged by when reports arrived, not when they were sent

### Target specification files

- SPECIFICATION/contracts.md

### Summary

The v090 return-from-silence rule defined the return as the first report the host SENT after a gap, which is a time on the enrolled host's clock. It is compared with an instruction's decision time, which a pass records on the role holder's clock, and staleness everywhere else is judged by when a report ARRIVED. This judges the return by when the host's first request after the silence arrived, on the role holder's clock, before that request is answered, and has the report store keep the times it needs.

### Motivation

Found by the independent post-step LLM doctor run on v090 (2026-11-08). The coordinator, legacy-coordinator-agent, ruled under R301 that all six findings of that run land together in one follow-up revised as v091, with one scoped post-step review over those six only, and that spec iteration for this plan then stops (scope events on overseer-iyfjbo). No implementation of enrolled-host delivery exists yet; overseer-3vnxkd owns it, and any slice of it that implements enforcement-instruction serving waits for v091. This was an advisory: contracts.md accepts any offset between the two clocks as unfixed, so a rule that mixes them can serve or withhold an instruction by the size of that offset.

### Proposed Changes

In SPECIFICATION/contracts.md §"Enrolled-host delivery", in **Enforcement instructions**, replace the bullet:

"- The service MUST NOT serve an instruction decided before the host's latest return from silence, that is, before the first report the host sent after a gap longer than `delivery.stale_after`."

with:

- The service MUST NOT serve an instruction decided before the host's latest return from silence. A host RETURNS FROM SILENCE when an authenticated request from it, of any operation, arrives and no authenticated request from it arrived within the preceding `delivery.stale_after`; the time of the return is that request's arrival time. The service MUST make this judgement before it answers that request, so that the first `delivery` request after a silence is already filtered. It MUST judge by arrival times on the role holder's clock, which is the clock a pass records an instruction's decision time on, and MUST NOT judge by any time a report states. The report store MUST record, for each host, the arrival time of its latest authenticated request and of its latest return from silence, and MUST keep both while any instruction record for that host's sessions remains.


## Proposal: Scenarios for supersession, the return-from-silence filter and refused label reuse

### Target specification files

- SPECIFICATION/scenarios.md

### Summary

v090 added three behaviours with no scenario: a newer enforcement instruction supersedes an older one, an instruction decided before a host's return from silence is not served, and issuance refuses a label that a revoked entry holds for a different network identity. This adds one scenario for each.

### Motivation

Found by the independent post-step LLM doctor run on v090 (2026-11-08). The coordinator, legacy-coordinator-agent, ruled under R301 that all six findings of that run land together in one follow-up revised as v091, with one scoped post-step review over those six only, and that spec iteration for this plan then stops (scope events on overseer-iyfjbo). No implementation of enrolled-host delivery exists yet; overseer-3vnxkd owns it, and any slice of it that implements enforcement-instruction serving waits for v091. This was an advisory: each of these is load-bearing behaviour stated as a MUST clause, and a clause with no scenario has nothing for its implementation's tests to exercise.

### Proposed Changes

Each scenario below MUST be added at the position named, so that each of the three clauses has a scenario.

In SPECIFICATION/scenarios.md, immediately after the scenario "## Scenario: A client restarted after recording an instruction does not act on it again" and after any scenario the preceding proposal adds there, add:

## Scenario: A superseded enforcement instruction is never served

Given a rotation pass wrote an enforcement instruction for a remote session and the host has reported no outcome for it

And a later pass wrote a newer instruction for the same session

And the host has reported within `delivery.stale_after` throughout

When the client requests a delivery

Then the service serves only the newer instruction

And after the host reports the newer instruction's outcome and a pass deletes every instruction record it may delete, the service serves neither instruction

## Scenario: An instruction decided before a host returns from silence is not served

Given a rotation pass wrote an enforcement instruction for a session on a following host and the host has reported no outcome for it

And no authenticated request from that host then arrived for longer than `delivery.stale_after`

When the client next requests a delivery, before any report from it arrives

Then the service does not serve that instruction

And the client does not act on it

In SPECIFICATION/scenarios.md, immediately after the scenario "## Scenario: A revoked device can be enrolled again", add:

## Scenario: A revoked host's label cannot be reused for another device

Given host A's enrolment under the label `laptop` has been revoked

When the operator issues an enrolment for a different device under the label `laptop`

Then the command refuses and the registry is unchanged

And no enrolment credential is shown


## Proposal: The stopped-service scenario excludes a stored forwarded refusal that is still eligible

### Target specification files

- SPECIFICATION/scenarios.md

### Summary

v090 made a forwarded refusal eligible by the conditions as they stood when its report arrived, so a refusal forwarded before every host fell silent can still be attributed. The scenario "A stopped delivery service does not affect a rotation pass" says the pass behaves exactly as with no enrolled host, but its Givens do not exclude such a refusal, so a pass that correctly attributes one contradicts the scenario. This adds the missing Given.

### Motivation

Found by the independent post-step LLM doctor run on v090 (2026-11-08). The coordinator, legacy-coordinator-agent, ruled under R301 that all six findings of that run land together in one follow-up revised as v091, with one scoped post-step review over those six only, and that spec iteration for this plan then stops (scope events on overseer-iyfjbo). No implementation of enrolled-host delivery exists yet; overseer-3vnxkd owns it, and any slice of it that implements enforcement-instruction serving waits for v091. This was an advisory: the scenario's Then is only true when the report store holds no refusal that is still eligible.

### Proposed Changes

The scenario's Givens MUST exclude every input through which an enrolled host can still affect the pass. In SPECIFICATION/scenarios.md, in "## Scenario: A stopped delivery service does not affect a rotation pass", replace:

"And no enrolled host has reported within `delivery.stale_after`"

with:

And no enrolled host has reported within `delivery.stale_after`

And the report store holds no forwarded refusal that is still eligible for attribution


## Proposal: The client rollback covers only the two delivery files

### Target specification files

- SPECIFICATION/constraints.md

### Summary

constraints.md lists three client writes, the credential file, the global state file and the record of acted enforcement-instruction identifiers, and then says that a failed client write restores the previous bytes of 'both files'. That reads as covering the identifier record too, and restoring an earlier copy of that record could drop a recorded identifier and let the client act on an instruction twice. This scopes the restore to the two delivery files.

### Motivation

Found by the independent post-step LLM doctor run on v090 (2026-11-08). The coordinator, legacy-coordinator-agent, ruled under R301 that all six findings of that run land together in one follow-up revised as v091, with one scoped post-step review over those six only, and that spec iteration for this plan then stops (scope events on overseer-iyfjbo). No implementation of enrolled-host delivery exists yet; overseer-3vnxkd owns it, and any slice of it that implements enforcement-instruction serving waits for v091. This was an advisory against the rollback sentence in constraints.md, which v090 did not change when it added the identifier record to the list above it.

### Proposed Changes

In SPECIFICATION/constraints.md, replace the sentence:

"A failed client write restores the previous bytes of both files and is reported, as contracts.md §"Enrolled-host delivery" defines."

with:

A failed client write of the interactive credential file or the global state file restores the previous bytes of those two files and is reported, as contracts.md §"Enrolled-host delivery" defines. That restore MUST NOT rewrite the record of acted enforcement-instruction identifiers, because restoring an earlier copy of it could drop a recorded identifier and let the client act on that instruction again. A failed write of that record leaves the client not acting on the instruction, because the same section requires the client to record an identifier before it acts on it.


## Proposal: Issuance refers to the registry's uniqueness rules instead of restating them

### Target specification files

- SPECIFICATION/contracts.md

### Summary

**Issuance** restates, as refusal conditions, the uniqueness rules that **Enrolment registry** already states. Two copies of one rule can drift apart. This makes Issuance refuse whatever the registry's rules forbid, with no change in behaviour.

### Motivation

Found by the independent post-step LLM doctor run on v090 (2026-11-08). The coordinator, legacy-coordinator-agent, ruled under R301 that all six findings of that run land together in one follow-up revised as v091, with one scoped post-step review over those six only, and that spec iteration for this plan then stops (scope events on overseer-iyfjbo). No implementation of enrolled-host delivery exists yet; overseer-3vnxkd owns it, and any slice of it that implements enforcement-instruction serving waits for v091. This was an advisory. The two statements are equivalent today: a label or network identity held by an unrevoked entry, or a label a revoked entry holds for a different network identity.

### Proposed Changes

In SPECIFICATION/contracts.md §"Enrolled-host delivery", in **Issuance**, replace the sentence:

"Under the REGISTRY LOCK, which **Revocation** also holds for its write, the command MUST refuse a label or a network identity that an unrevoked entry already holds, or a label that a revoked entry holds for a different network identity, and MUST then write the new entry."

with:

Under the REGISTRY LOCK, which **Revocation** also holds for its write, the command MUST refuse an entry that the label and network-identity rules of **Enrolment registry** forbid, including a label that a revoked entry holds for a different network identity, and MUST otherwise write the new entry.

