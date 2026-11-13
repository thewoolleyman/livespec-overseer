---
topic: caam-reset-best-value
author: claude-sonnet-5-5
created_at: 2026-11-12T20:00:17Z
spec_commitments:
  impl_followups:
    - id_hint: caam-reset-best-value-code
      description: |
        Implement the best-value reset-claim clause and the protected-account reset reserve in overseer/caam_*.py on top of the v057 reset code (overseer-33kyxp), with fake-transport tests for the five new scenarios; the live claim is a separate host-side obligation after merge.
---

## Proposal: claim-a-reset-at-the-best-value-moment

### Target specification files

- SPECIFICATION/spec.md
- SPECIFICATION/scenarios.md

### Summary

Add a best-value reset-claim clause to spec.md section "Account rotation and quota supervision": burn one account, and claim its reset at the weekly reserve while at least a configurable CLAIM HORIZON of days remains before its weekly window resets, staying on that account. Add a protected-account reset reserve. This REVERSES, for the burn-then-claim case only, the ratified rule that rotation is preferred while any candidate survives.

### Motivation

The ratified reset rules (v057) claim a reset only at an exhausted window with no candidate, or when a reset is about to lapse. Both fire late: while any candidate survives the operation rotates and never claims, so a reset is typically still unspent when it lapses, and it is then spent only when it refills little. The maintainer (2026-11-12) requires that resets neither be wasted nor sit unused, that one account be burned through and its reset claimed while several days remain in its weekly window, because a claim made on a nearly exhausted account with days to go refills the most allowance that would otherwise sit idle, that resets be spent before they expire, and that the protected account keep one reset in reserve unless it is about to lapse, as its quota rule already reserves quota. Measurement 002 of plan caam-quota-resets shows one cedar_ember grant refills the five-hour, weekly and Fable-scoped windows together and that use_requires_limit is false, so a claim before the wall is permitted by the provider; the timing is policy.

### Proposed Changes

In SPECIFICATION/spec.md, section "Account rotation and quota supervision", insert after the paragraph **A reset MUST be claimed rather than held at an exhausted window.** the following new paragraph, and amend that paragraph's sentence "Rotation MUST remain preferred: while any candidate survives, the operation MUST rotate and MUST NOT claim under this clause." to read "Rotation MUST remain preferred under this clause: while any candidate survives, the operation MUST rotate and MUST NOT claim under this clause, except in the case governed by the best-value clause below."

New paragraph:

**A reset MUST be claimed at the best-value moment, so that one account is burned through before the next is started.** A claim refills the allowance spent so far and gains the most when the account is nearly exhausted and many days remain before its weekly window would have reset on its own, because the refilled allowance would otherwise sit idle for those days. Where an invocation carrying the scheduled marker finds that the weekly-reserve trigger has fired on the active account, and the account holds a reset that is usable now and clears the weekly window, and at least a configurable CLAIM HORIZON, whose default MUST be three days, remains before the account's weekly window resets on its own, the operation MUST claim that reset and MUST then stay on that account, even where a candidate survives. This clause is the one exception to the rule that rotation is preferred while any candidate survives. It applies only to the weekly-reserve trigger on the active account; it MUST NOT apply where the account is refusal-held, where a short-window trigger or the fast-drain trigger fired, or where the account's weekly window is reported to reset on its own within the claim horizon, and in each of those cases the exhausted-window and rotation rules above govern unchanged. The operation MUST NOT claim under this clause on an account whose credential is not live-verified on that pass, on an account that cannot serve for a reason no reset clears such as a reached monthly spend cap, or for a reset the provider permits only at a limit the account has not reached. Where several resets qualify, the operation MUST apply the narrowest-qualifying and soonest-lapse preferences of the exhausted-window clause. After a claim the operation MUST re-read the active account, MUST re-evaluate the rotation triggers against the fresh reading and MUST stay on the account if no trigger still fires. The claim horizon is an input to this decision only and MUST NOT change ranking, eligibility or any reserve.

**The protected account MUST keep one reset in reserve.** The operation MUST NOT claim under the best-value clause a reset on a protected account if the claim would leave that account holding no usable reset. This reserve yields only to a reset that lapses within the expiry horizon, which the lapse clause already requires to be claimed, so that a reserved reset is never allowed to be forfeited. The exhausted-window clause is unchanged: where holding would leave the operation with no usable account, it MAY spend a protected account's last reset, because a reserve that cannot be spent is worth less than the capacity it would restore. The reserve counts usable uses remaining across the account's resets, not the number of grants.

In the paragraph **A claim MUST be serialized, idempotent and reported.**, change "the clause that required it (an exhausted window with no candidate, or an imminent lapse)" to "the clause that required it (an exhausted window with no candidate, an imminent lapse, or the best-value moment, in which case the line also names the days remaining before the account's weekly window resets)".

In SPECIFICATION/spec.md, section "Account rotation and quota supervision", the paragraph beginning "The operator-facing account table MUST show each account's resets" keeps its text; its sentence "Reset observation MUST NOT influence selection or ranking except through the reset-claim clauses below" stays true because the best-value clause is one of those clauses.

In SPECIFICATION/scenarios.md, amend the scenario "A reset is not claimed while a candidate can be rotated to" by adding the given "And the active account's weekly reserve is not the trigger that fired" so the scenario keeps its meaning for the short-window case, and add these scenarios after it, each in the file's existing Given/When/Then style:

## Scenario: A reset is claimed at the weekly reserve while days remain, instead of rotating

Given the active account's weekly allowance is at the weekly reserve

And the active account holds a usable reset that clears its weekly window

And at least the claim horizon remains before its weekly window resets on its own

And an eligible candidate exists

When a scheduled pass runs

Then the operation claims that reset

And it stays on the active account

And it reports the claim on its own line naming the days remaining before the weekly window resets

## Scenario: A reset is not claimed at the weekly reserve when the window resets within the claim horizon

Given the active account's weekly allowance is at the weekly reserve

And the active account holds a usable reset that clears its weekly window

And its weekly window resets on its own within the claim horizon

And an eligible candidate exists

When a scheduled pass runs

Then the operation rotates to the candidate

And it claims no reset under the best-value clause

## Scenario: The protected account keeps its last reset in reserve

Given the protected account is the active account

And its weekly allowance is at its own protection floor

And it holds exactly one usable reset that clears its weekly window and lapses beyond the expiry horizon

And at least the claim horizon remains before its weekly window resets

When a scheduled pass runs

Then the operation does not claim that reset under the best-value clause

## Scenario: The protected account's last reset is claimed when it is about to lapse

Given the protected account holds exactly one usable reset lapsing within the expiry horizon

And a window the reset clears is spent by more than the eligibility margin

When a scheduled pass runs

Then the operation claims that reset under the lapse clause

## Scenario: A reset is not claimed at the best-value moment on a spend-capped account

Given the active account's weekly allowance is at the weekly reserve

And the active account holds a usable reset and at least the claim horizon remains before its weekly window resets

And the account has reached its monthly spend cap

When a scheduled pass runs

Then the operation claims no reset

And it rotates or holds under the existing rules

In SPECIFICATION/scenarios.md the new scenarios are registered in tests/heading-coverage.json as TODO rows owned by the code-half work item, as for the v057 scenarios.
