---
topic: scoped-model-allowance-in-target-selection
author: caam-anthropic-loop-planner
created_at: 2026-08-26T09:55:08Z
---

## Proposal: A scoped-model allowance MUST influence selection where it decides whether operator model pins can be honoured

### Target specification files

- SPECIFICATION/spec.md

### Summary

Narrow the blanket prohibition on a scoped-model allowance influencing account selection so that it no longer forbids the one case where the allowance is not about capacity at all. Where an operator has pinned sessions to the scoped model, only the ACTIVE account's scoped allowance can satisfy those pins, so exhausting it disables a capability the operator explicitly configured. Adds three narrow normative rules -- exhaustion of the active account's scoped allowance MUST trigger rotation, a candidate's remaining scoped allowance MAY override the relative-headroom margin while that candidate's short-window allowance is still below the rotation threshold, and scoped availability MUST rank ahead of soonest weekly reset -- while leaving the capacity reasoning that motivated the original prohibition intact and explicitly restating that the allowance MUST NOT be treated as spendable capacity.

### Motivation

The ratified clause states that a scoped-model allowance MUST NOT influence account selection: it MUST NOT trigger a rotation, MUST NOT disqualify a candidate, and MUST NOT tier or rank candidates. Its stated rationale is purely capacity economics -- such an allowance draws down the general weekly allowance as it is used, so leaving it unspent forfeits no capacity while leaving weekly unspent forfeits it permanently. That reasoning remains correct and this proposal does not dispute it.

What the rationale never weighed is SESSION CAPABILITY. The same section obliges the operation to point sessions at the scoped model, and a later clause obliges it to honour an explicit operator pin and to persist that pin in durable state. Enforcement can only ever spend the ACTIVE account's scoped allowance. So when the active account's scoped allowance reaches zero, every operator pin naming that model becomes unsatisfiable, and the operation goes on holding because no rule in the trigger set can see the condition. The clause's own closing sentence -- that the allowance MUST inform only which model a session runs -- is the hinge: this proposal observes that WHICH ACCOUNT IS ACTIVE now determines whether that sentence can be honoured at all.

This is measured, not hypothetical. Over 2026-08-25 and 2026-08-26 the active account's scoped allowance drained from 14 percent to 0 across eight consecutive scheduled passes while the operation held every time, because the trigger set is short-window threshold OR weekly reserve and carries no scoped term. At exhaustion both persisted operator pins were reported BLOCKED by the operation's own warning lines and roughly 23 sessions were reset to the general model. A forced pass recovered it by rotating away. The scheduler then RE-CREATED the identical state unaided: the next account crossed the short-window threshold, and ranking -- whose sole key is soonest weekly reset -- selected the one account whose scoped allowance was zero, because the two candidates with scoped allowance remaining were disqualified on weekly quota. Both pins have been unsatisfiable since. The existing rules did not merely fail to prevent this; ranking actively steered into it.

The remedy is deliberately narrow. It does not make the allowance spendable capacity, does not disqualify any candidate on scoped grounds, and does not weaken the live-verified rule, the weekly reserve, the zero-weekly disqualifier, or any per-account protection floor. It adds one trigger, one bounded override of the margin test, and one ranking key.

### Proposed Changes

Replace the paragraph beginning "**A scoped-model allowance MUST NOT influence account selection.**" in SPECIFICATION/spec.md section "Account rotation and quota supervision" with the following:

> **A scoped-model allowance MUST NOT be treated as spendable capacity, and MUST influence selection only where it decides whether an operator's model pins can be honoured.** Such an allowance caps how much of the weekly allowance a single model may spend and draws down the general weekly allowance as it is used, so leaving it unspent forfeits no capacity while leaving weekly unspent forfeits it permanently. The operation MUST NOT rotate in order to consume a scoped allowance, MUST NOT disqualify a candidate for holding one, and MUST NOT prefer a candidate on scoped grounds for any capacity reason.
>
> That reasoning governs capacity and does not reach capability. Enforcement can spend only the ACTIVE account's scoped allowance, so where the operator has pinned any session to the scoped model, the active account's remaining scoped allowance decides whether that pin can be honoured at all. The operation MUST therefore observe the scoped allowance in exactly three places, and MUST NOT extend it to a fourth:
>
> - **Trigger.** Exhaustion of the ACTIVE account's scoped allowance MUST trigger rotation on its own, alongside the short-window threshold and the weekly reserve. Without this the condition is invisible to the trigger set and the operation holds while every pinned session runs unpinned.
> - **Eligibility.** A candidate that retains a scoped allowance MAY be selected even though it does not clear the relative-headroom margin on the triggering dimension, PROVIDED its own short-window allowance is still below the rotation threshold, so that the operation never moves onto an account it would immediately have to leave. Where the candidate's short-window allowance is at or above that threshold, the ordinary relative-headroom comparison MUST apply unchanged.
> - **Ranking.** Among eligible candidates, a candidate retaining a scoped allowance MUST sort ahead of one that has none, and soonest weekly reset MUST remain the ordering among candidates that are equal on that test. A candidate whose scoped allowance cannot be read MUST be treated as having none and MUST NOT be treated as retaining one.
>
> These three MUST NOT weaken any other rule. A candidate that is not live-verified MUST NOT be selected on scoped grounds; the weekly reserve, the zero-weekly disqualifier and any per-account protection floor MUST continue to exclude a candidate regardless of its scoped allowance; and the operation MUST still hold, rather than switch, when no candidate survives those rules. Where rotation is triggered by scoped exhaustion alone and no candidate retains a scoped allowance, the operation MUST hold and MUST report that the pins cannot currently be satisfied, rather than rotating to no purpose.

Amend the paragraph beginning "**Rotation triggers.**" by appending one sentence:

> The operation MUST additionally rotate when the active account's scoped-model allowance is exhausted, and where that is the sole reason for leaving, candidates MUST be compared on the scoped dimension.

Amend the paragraph beginning "**Ranking.**" by appending one sentence:

> Scoped-model availability MUST be applied as a higher-priority ordering than soonest weekly reset, per the scoped-model clause below.

Amend the paragraph beginning "**An operator override MUST be able to pin the enforced model, and it MUST persist.**" by appending one sentence:

> Where a pin selects a model whose allowance is exhausted on the active account, the operation MUST treat that as a rotation trigger per the scoped-model clause rather than merely warning, since a warning leaves the pin unsatisfiable indefinitely.
