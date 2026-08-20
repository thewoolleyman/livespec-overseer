---
topic: undelivered-wrap-up-standing-round
author: claude-opus-5
created_at: 2026-08-20T07:45:07Z
---

## Proposal: Surface a standing round whose wrap-up was never delivered

### Target specification files

- SPECIFICATION/spec.md
- SPECIFICATION/contracts.md
- SPECIFICATION/scenarios.md

### Summary

spec.md requires the daemon to un-open a round whose opening wrap-up paste failed, by deleting the injection stamp it had just written. That deletion is itself a fail-soft storage operation and may fail, and when it does the track is left carrying a standing round with no wrap-up behind it — the exact state the un-open rule exists to forbid — with nothing in the ratified attention surface naming the condition. This proposal adds one REPORT-ONLY mechanical-attention member for that double failure, adds the matching surfacing requirement to the un-open rule itself, and pins both with scenarios. It changes nothing the daemon DOES to a pane: no new paste, no new restart, and no change to any authorization.

### Motivation

Recorded as a spec-side residual of the v010 ratification (`SPECIFICATION/history/v010/proposed_changes/post-void-ready-certification.md`) and carried since on work-item `overseer-y8n6`, whose analysis was completed against the shipped tree before this proposal was drafted.

THE ASYMMETRY IS THE ARGUMENT. contracts.md §"Attention surface" already carries a named member for the comparable EXPIRY-path double failure — the case where the state-file delete AND the floor record both failed in the same observation — precisely because surfacing is the only remaining guard once both writes are gone. The identical argument applies to a failed un-open with equal force, and it got no member. Searching the whole attention-surface section for the un-open case returns nothing.

THE CONDITION IS REACHABLE, VERIFIED AGAINST THE CODE RATHER THAN INFERRED. On the opening branch of the wrap-up injection the daemon writes the stamp BEFORE the paste by design, so that a marker the session later writes has a modification time greater than the round's opening instant. When the paste fails, the rollback calls the stamp-clearing operation, which returns nothing and writes through the fail-soft atomic-write path whose default is to warn rather than raise. The caller therefore cannot tell the rollback failed. On the next observation the round's opening instant is no longer absent, so the open block is skipped and the paste is re-attempted — the retry is real and the existing log line is accurate about it — but the round now STANDS with no wrap-up ever delivered.

THE HARM IS A CERTIFICATION HAZARD, NOT A RETRY FAILURE. Tracing the restart interlock's rejection predicate in that state, every branch falls through: the opening instant is set, the stamp is well-formed, the round-open identity matches the live one because it was written moments earlier, and any `ready` written afterwards is newer than the certification floor. The declaration is therefore CERTIFIABLE, and a restart would be authorized against a round whose wrap-up never landed. What makes that worse than it sounds is that THE PASTE FAILING IS ITSELF EVIDENCE THE SESSION COULD NOT BE REACHED — that is the whole reason the un-open exists — so the hazardous state is a standing round plus a session the daemon just failed to reach. A `ready` appearing against that round certifies a restart of a session that was never asked to wind down, never received the prompt, and never wrote a handoff. That is the cardinal rule's protection defeated by a storage failure rather than by a decision.

THE EXPOSURE WINDOW IS UNBOUNDED EXACTLY WHEN IT MATTERS. If the retry succeeds the round becomes legitimate and the window closes. But the condition that caused the paste to fail is a pane the daemon cannot reach, which is precisely the condition that also makes the retry fail, so the hazard concentrates in the case least likely to self-heal.

STATED HONESTLY, WHAT WAS NOT MEASURED: no end-to-end exercise producing a spurious restart was constructed, and no such incident is claimed to have occurred. The wrap-up prompt is what normally elicits a declaration and it is precisely what did not arrive, so the `ready` would have to come from elsewhere — a stale resume convention, a state file inherited from a predecessor, or an unprompted write. The interlock predicate's branch order, and that each branch falls through in this state, ARE measured.

OUT-OF-TARGET CO-EDIT, named here rather than in `target_spec_files` because it lies outside the spec target: the two scenarios below require the governed `tests/heading-coverage.json` co-edit in the same revision. No integration-tier test exists for either yet, so each entry MUST carry `test: "TODO"` together with a `work_item` naming an OPEN item — `overseer-dhkjxf`, this repo's standing carrier for TODO scenario coverage, which is open at the time of drafting. A TODO entry owned by a CLOSED item silently orphans the residual, which is the defect that convention exists to prevent.

### Proposed Changes

This proposal makes three coordinated edits. Together they name one condition, require it to be surfaced, and pin both the positive case and its discriminating control.

### 1. `spec.md` §"The supervision round" — complete the un-open rule

The ratified paragraph requires the un-open but is silent on that deletion failing. Immediately after the sentence ending "a merely attempted one is un-opened at once and was never a round at all", the following SHOULD be added:

That deletion is itself a fail-soft storage operation and MAY fail. When it does, the track carries a STANDING ROUND WITH NO WRAP-UP BEHIND IT — precisely the state this rule forbids — and no later observation can distinguish that round from a delivered one, because the evidence that would have distinguished them is the write that was lost. The daemon MUST surface that condition through the mechanical attention surface of contracts.md §"Attention surface". The surfacing is REPORT-ONLY: it MUST NOT gate, block, or authorize any act, MUST NOT suppress or alter the retry of the undelivered wrap-up, and MUST NOT itself delete, rewrite, or re-open the round's durable record.

### 2. `contracts.md` §"Attention surface" — add the membership

A new membership paragraph SHOULD be added alongside the existing members, in the same shape as the three conditions arising from the certification floor:

Membership also includes a track carrying a STANDING ROUND WHOSE WRAP-UP WAS NEVER DELIVERED: a round whose opening wrap-up paste FAILED and whose required un-open — the deletion of the injection stamp the daemon had just written, per spec.md §"The supervision round" — ALSO failed in the same observation, so the round's durable record remains with no wrap-up behind it. Surfacing is the remaining guard here, exactly as it is for the expiry-path double failure: once the rollback write is lost, nothing left in the data distinguishes this round from a legitimate one, and a declaration written afterwards would certify against it. Membership MUST require BOTH failures in the SAME observation. A failed opening paste whose un-open SUCCEEDED leaves the track un-rounded and MUST NOT establish membership, and the paste failure alone MUST NOT establish it either — that failure is already answered by the un-open and by the daemon's own retry, and a member keyed on it would fire on the ordinary, harmless case and report nothing about the hazardous one. This member is REPORT-ONLY with normal coordinates; it participates in the NEEDS YOU count and window badge, is edge-triggered like every other member, clears when the round's wrap-up is subsequently delivered or when the round's durable record is removed, and MUST NOT authorize any act — a fresh session-written `ready` remains the sole restart authorization. Its rendered note MUST state that no wrap-up was delivered for the standing round, so an operator can distinguish it from a delivered round legitimately awaiting a declaration.

THE MEMBER IS NAMED BY THE STATE IT LEAVES, NOT BY THE OPERATION THAT FAILED. "A standing round whose wrap-up was never delivered" is the reportable condition; "a stamp delete failed" is one way of arriving at it. Naming the state keeps the member meaningful if the rollback is ever implemented by a different mechanism, and keeps it aimed at the hazard rather than at an implementation detail.

### 3. `scenarios.md` — pin the member and its control

Two scenarios SHOULD be added. The second is not optional colour: it is the discriminating control that proves the member is keyed on the double failure rather than on the paste failure, and without it a member that fired on every failed paste would satisfy the first scenario alone.

## Scenario: A failed un-open leaves a standing round that is surfaced

Given a track at a wind-down band with no round open

And the daemon writes the injection stamp and then fails to paste the opening wrap-up

And the deletion of that just-written stamp also fails in the same observation

When the daemon renders the mechanical attention surface

Then the track is surfaced as carrying a standing round whose wrap-up was never delivered

And the rendered note states that no wrap-up was delivered for that round

And no restart is authorized, no pane is keystroked, and the round's durable record is neither deleted nor rewritten by the surfacing

## Scenario: A successful un-open after a failed wrap-up paste surfaces nothing

Given a track at a wind-down band with no round open

And the daemon writes the injection stamp and then fails to paste the opening wrap-up

And the deletion of that just-written stamp SUCCEEDS

When the daemon renders the mechanical attention surface

Then the track is NOT surfaced as carrying a standing round whose wrap-up was never delivered

And the track is left un-rounded so a later threshold crossing opens a fresh round

### Scope of what this proposal does and does not authorize

NO CHANGE TO THE DAEMON'S ACTING BEHAVIOR IS PROPOSED OR AUTHORIZED. Nothing here adds, removes, or re-times a paste, a keystroke, a respawn, a restart, a state-file write, or any authorization. The retry of the undelivered wrap-up MUST continue to behave exactly as it does today, and the existing unconditional log line reporting the failed paste SHOULD be left as it stands, since it is accurate about the paste; the new member is ADDITIVE.

ONE PRECISION IS OWED, AND IT IS STATED RATHER THAN GLOSSED. The hazardous STATE is already reachable in shipped behavior — this proposal invents no new state and widens no hazard. But the condition is not currently distinguishable by the code at the point where it would be reported, because the stamp-clearing operation returns nothing and its fail-soft write reports failure only as a warning. Implementing this member will therefore require that operation to report its outcome to its caller, and the caller to surface the condition when both failures occurred. That is a REPORTING-PATH change, not a change to any act, and it is the minimum required for the member to be truthful rather than presumed. A member that could not tell the two cases apart would report the harmless case as the hazardous one, which is the cry-wolf direction and worse than no member.

The governed `tests/heading-coverage.json` co-edit MUST land atomically with the scenarios in the same revision, per this project's self-application discipline, with `test: "TODO"` and a `work_item` naming an open item as described in the motivation.

CLOSING AS WONTFIX REMAINS A LEGITIMATE DISPOSITION. The behavior fails closed today in the sense that the retry continues and no act is taken on the strength of this condition, and the hazard requires a second, independent storage failure. If the ratifying decision is that an unnamed condition is acceptable here while the comparable expiry-path condition keeps its member, that asymmetry SHOULD be recorded explicitly in the revision's rationale, so the next reader who finds it does not re-file it as an oversight.
