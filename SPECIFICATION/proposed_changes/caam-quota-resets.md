---
topic: caam-quota-resets
author: claude-opus-5-5
created_at: 2026-10-14T01:48:01Z
---

## Proposal: Report each account's available quota resets

### Target specification files

- SPECIFICATION/spec.md
- SPECIFICATION/scenarios.md

### Summary

The operation observes the quota resets each managed account holds, and the account table shows them in provider-agnostic terms: what one use clears, how many remain, and when it lapses. A reading the operation could not make is shown as unreadable, never as no resets.

### Motivation

Plan caam-quota-resets (epic overseer-pv53ri, item overseer-33kyxp). The maintainer asked that the loop detect provider quota resets, show them in new column(s), and use them wisely. Research note plan/caam-quota-resets/research/002-reset-mechanisms-measured.md measured on 2026-10-14 that every live Anthropic account held one unused reset (grant opus55-launch-promax-20260921) clearing the five-hour, weekly and scoped windows together and lapsing 2026-10-22T16:00Z, and that the loop ignored it. It also measured two traps. The reset blocks fill in only on a reset-aware read of the same usage endpoint. And the provider answers ineligible_reason=surface for every account unless the request carries the agent client's own identity, an HTTP 200 that silently reads as 'no resets exist'.

### Proposed Changes

In spec.md §"Account rotation and quota supervision", insert the following paragraph immediately after the **Observation** paragraph:

**Quota resets MUST be observed and reported.** A provider MAY grant an account QUOTA RESETS: a use of one refills one or more of that account's allowance windows before they would replenish on their own. The operation MUST observe, on every pass and for every managed account, the resets that account holds, and MUST parse each provider's response into a provider-agnostic RESET carrying: the provider's program and reset identifier; the windows one use CLEARS (short-window, weekly, scoped, or several of these at once); the number of uses remaining and in total; the moment the reset itself LAPSES, if the provider reports one; whether it is usable now; and whether the provider permits its use only while the account is at a limit. A recurring reset that the provider reports only while the account is at a limit MUST be represented as such and MUST NOT be reported as absent when the account is not at one. The read MUST be read-only, MUST be made with the same credential the quota poll for that account uses, and MUST present the client identity of the agent whose credential it is. A reading in which the provider declines to state the account's resets for a reason that concerns the requesting client rather than the account MUST be treated as UNREADABLE and MUST NOT be reported as the account holding no resets.

The operator-facing account table MUST show each account's resets in provider-agnostic terms beside its windows: for each reset, the windows it clears, the uses remaining, and the time until it lapses. It MUST show an account with no resets as holding none, and an account whose resets could not be read as unreadable. Reset observation MUST NOT influence selection or ranking except through the reset-claim clauses below, and a failure to read resets MUST NOT disturb the quota report or the rotation.

In scenarios.md, add these scenarios after "## Scenario: An invocation without the scheduled marker does not drain":

```gherkin
## Scenario: The account table shows each account's resets

Given an account holds one reset that clears its short-window and weekly windows, with one use remaining, lapsing in eight days

When a pass renders the account table

Then that account's row shows one reset clearing the short-window and weekly windows, with one use left, lapsing in eight days

## Scenario: A reset reading declined for the requesting client is unreadable, not empty

Given the provider answers an account's reset read as ineligible for a reason concerning the requesting client

When a pass renders the account table

Then that account's resets are shown as unreadable

And the account is not shown as holding no resets
```


## Proposal: Claim a reset rather than hold at an exhausted window

### Target specification files

- SPECIFICATION/spec.md
- SPECIFICATION/scenarios.md

### Summary

When a rotation trigger fires on the active account and no candidate survives, so the operation would otherwise hold while the account stays exhausted, a scheduled pass claims a reset that clears the triggering window. It does not claim when that window replenishes on its own within the configurable self-reset horizon. Rotation stays preferred over spending a reset. The never-refresh clause is narrowed to permit exactly this one write.

### Motivation

The maintainer's first use case: spend a reset when the window it resets is almost completely exhausted and a reset is available. Rotation already handles exhaustion while an eligible candidate exists, and that spends no scarce reset. The case rotation cannot handle is the hold, where every session on the host waits for the window to replenish. Research note 002 measured anthropic-3 at a 100% short window with both a session reset and a granted reset available. The maintainer also asked that a reset not be spent on a window that is about to reset on its own anyway. And the existing never-refresh clause permits read-only requests only, so claiming needs a deliberate, bounded exception rather than a silent breach. This proposal is revised after caam-capacity-aware-rotation, whose refusal trigger, fast-drain trigger, refusal hold and capacity-test release it names; the refusal sentence keeps a reset from ever being spent while a refusing account can still be left.

### Proposed Changes

In spec.md §"Account rotation and quota supervision", replace the first sentence of the **Never refresh** paragraph with:

The operation MUST perform read-only requests only, with the single exception of the reset claim governed by the reset-claim clauses of this section, and MUST NOT itself invoke the OAuth token endpoint under any circumstance, because rotating a refresh token outside the agent's own control can revoke the whole token family.

Then insert the following paragraph immediately after the **Ranking** paragraph:

**A reset MUST be claimed rather than held at an exhausted window.** Where an invocation carrying the scheduled marker finds that a rotation trigger has fired on the active account — the short-window threshold, the weekly reserve, its own protection floor, the scoped-model reserve, the usage-limit refusal trigger, or the fast-drain trigger — and no candidate survives the rules of this section, so that the operation would hold, the operation MUST claim one of the active account's resets that is usable now and clears every window whose trigger fired, before it holds. Rotation MUST remain preferred: while any candidate survives, the operation MUST rotate and MUST NOT claim under this clause. Where the active account is refusal-held, the refusal trigger governs: the operation MUST rotate while any candidate survives, including under the capacity-test release, MAY claim a reset that clears the refused window only where none survives, and a claim whose re-read shows that window replenished ends the refusal hold. The operation MUST NOT claim under this clause where every window whose trigger fired is reported to replenish on its own within a configurable SELF-RESET HORIZON, whose default MUST be sixty minutes, because such a claim buys at most that horizon's worth of use at the price of a reset. Where several resets qualify, the operation MUST prefer a reset that clears ONLY the windows whose trigger fired over one that clears more, and among those equal on that test MUST prefer the one that lapses soonest, treating a reset with no reported lapse as lapsing last. After a claim, the operation MUST re-read the active account and MUST re-evaluate the rotation triggers against the fresh reading, holding if no trigger still fires.

In scenarios.md, add these scenarios after "## Scenario: A reset reading declined for the requesting client is unreadable, not empty":

```gherkin
## Scenario: An exhausted active account with no candidate claims a reset instead of holding

Given the active account's short window is at the rotation threshold and does not replenish within the self-reset horizon

And no candidate survives the rotation rules

And the active account holds a reset that is usable now and clears its short window

When a scheduled pass runs

Then the operation claims that reset

And it re-reads the active account and holds without rotating

## Scenario: A reset is not claimed while a candidate can be rotated to

Given the active account's short window is at the rotation threshold

And an eligible candidate exists

And the active account holds a usable reset that clears its short window

When a scheduled pass runs

Then the operation rotates to the candidate

And it claims no reset

## Scenario: A reset is not spent on a window about to replenish on its own

Given the active account's short window is at the rotation threshold and replenishes within the self-reset horizon

And no candidate survives the rotation rules

And the active account holds a usable reset that clears its short window

When a scheduled pass runs

Then the operation claims no reset and holds

## Scenario: The narrowest qualifying reset is claimed

Given only the active account's short-window trigger fired and no candidate survives

And the account holds a usable reset clearing only its short window and another clearing its short-window and weekly windows

When a scheduled pass runs

Then the operation claims the reset that clears only the short window

## Scenario: A refusal-held active account rotates under the capacity-test release rather than claiming a reset

Given the active account is refusal-held on a short-window refusal

And every candidate that survives the other rotation rules fails the capacity test

And the active account holds a usable reset that clears its short window

When a scheduled pass runs

Then the operation rotates to the best-ranked of those candidates

And it claims no reset

## Scenario: A claim that replenishes the refused window ends the refusal hold

Given the active account is refusal-held on a short-window refusal and no candidate survives

And the active account holds a usable reset that clears its short window

When a scheduled pass claims that reset and the re-read shows the short window replenished

Then the active account is no longer refusal-held

And the operation holds on it without rotating
```


## Proposal: Claim a reset that would otherwise lapse unused

### Target specification files

- SPECIFICATION/spec.md
- SPECIFICATION/scenarios.md

### Summary

A scheduled pass claims a reset whose own lapse falls within a configurable expiry horizon, on any live-verified managed account, provided the claim would refill at least the eligibility margin of spent allowance on some window it clears. This is the same 'otherwise lost' principle as the expiring weekly drain.

### Motivation

The maintainer's second use case: use a reset that is expiring soon and would otherwise be lost. Research note 002 measured that every live Anthropic account's grant lapses 2026-10-22T16:00Z with one use left, and that Codex reset credits also carry an expiry. An unclaimed lapsing reset is forfeited exactly as unspent weekly allowance is, which is the principle the ratified expiring-weekly drain already acts on. A claim that refills almost nothing would waste the reset as surely as letting it lapse, so a minimum benefit is required. That minimum reuses the existing eligibility margin rather than adding a new setting.

### Proposed Changes

In spec.md §"Account rotation and quota supervision", insert the following paragraph immediately after the paragraph beginning **A reset MUST be claimed rather than held at an exhausted window.**:

**A reset that would otherwise lapse MUST be claimed.** A reset left unclaimed past the moment it lapses is forfeited permanently. An invocation carrying the scheduled marker MUST therefore claim, on any managed account whether active or not, a reset that is usable now and whose reported lapse falls within a configurable EXPIRY HORIZON, whose default MUST be twenty-four hours, provided that the claim would refill at least the eligibility margin of **Eligibility** of spent allowance on at least one window the reset clears. The operation MUST NOT claim a reset under this clause on an account whose credential is not live-verified on that pass. It MUST NOT claim a reset whose provider permits its use only while the account is at a limit unless the account is at a limit that the reset clears. And it MUST NOT claim under this clause a reset that reports no lapse. Where an account holds several resets within the horizon, the operation MUST claim at most one per account per pass, the one that lapses soonest. This clause MUST apply whether or not any rotation trigger fired, and a claim under it MUST NOT itself cause a rotation. Rotation on that pass MUST be decided on readings taken after the claim.

In scenarios.md, add these scenarios after "## Scenario: A claim that replenishes the refused window ends the refusal hold":

```gherkin
## Scenario: A reset about to lapse is claimed

Given a non-active, live-verified account holds a usable reset lapsing within the expiry horizon

And that account's weekly window is spent by more than the eligibility margin

When a scheduled pass runs

Then the operation claims that reset

And it does not switch to that account because of the claim

## Scenario: A lapsing reset that would refill almost nothing is not claimed

Given an account holds a usable reset lapsing within the expiry horizon

And every window the reset clears is spent by less than the eligibility margin

When a scheduled pass runs

Then the operation claims no reset

## Scenario: A reset lapsing beyond the expiry horizon is not claimed early

Given an account holds a usable reset whose lapse falls beyond the expiry horizon

And no rotation trigger fires on that account

When a scheduled pass runs

Then the operation claims no reset
```


## Proposal: Bound every reset claim by the existing rotation rules

### Target specification files

- SPECIFICATION/spec.md
- SPECIFICATION/scenarios.md
- SPECIFICATION/contracts.md

### Summary

A reset claim never relaxes the weekly reserve, any protection floor and the ordering it imposes, the scoped-model rules, the zero-weekly and cannot-serve-immediately disqualifiers (which cover a spend-capped account), or the live-verification rule. It runs only on a scheduled pass under the decision lock, is idempotent across retries, and is reported with its reason and outcome. A provider refusal is a reported outcome, and a transport failure fails the pass without undoing it.

### Motivation

The maintainer asked for switching rules 'in accordance with existing rules and principles', naming protected accounts, the weekly reserve, scoped-model pins and the spend cap. A claim is the operation's first write to the provider and spends something scarce, so it needs the same serialization and fail-loudly guarantees as a switch. Research note 002 measured that the provider's claim takes a caller-supplied request identifier that makes a retried claim idempotent. Without persisting it, a pass retried after a lost response could spend a second use.

### Proposed Changes

In spec.md §"Account rotation and quota supervision", insert the following paragraph immediately after the paragraph beginning **A reset that would otherwise lapse MUST be claimed.**:

**Reset claims MUST NOT weaken any other rule.** A claim refills an account's windows. It is not a rotation and MUST NOT be treated as one. A claim MUST NOT relax the weekly reserve, any per-account protection floor, the protection ordering, the zero-weekly disqualifier, the cannot-serve-immediately disqualifier or the live-verification rule. In particular, a protected account whose windows a claim refilled MUST NOT be selected while any unprotected account is eligible. An account that cannot serve for a reason no reset clears, such as a reached monthly spend cap, MUST NOT have a reset claimed on that ground. A reset that clears a scoped window MAY satisfy the scoped-model reserve trigger under the exhausted-window claim clause, and MUST NOT otherwise make the scoped allowance influence selection beyond what the scoped-model clause permits. An invocation without the scheduled marker MUST NOT claim a reset.

**A claim MUST be serialized, idempotent and reported.** A claim MUST be made only while holding the lock that serializes the decision-and-switch sequence, and only after re-reading the account it is made on. Before sending a claim, the operation MUST record in its durable store a claim identifier for that account and reset. A retry of the same claim MUST reuse that identifier, so that a claim whose response was lost cannot spend a second use. At most one claim MAY be made per account per pass. Every claim MUST be reported on its own line, naming the account, the reset, the clause that required it (an exhausted window with no candidate, or an imminent lapse) and the windows it cleared. A provider answer that the reset was already used, was not needed, is cooling down, is ineligible or is unavailable MUST be reported as that outcome and MUST NOT be treated as a failure. A claim that could not be sent or whose answer could not be read is a failure path under **Fail loudly**: the operation MUST emit a clearly-marked failure line and exit non-zero, and MUST NOT roll back a switch, suppress the account table, prevent publication or prevent the persistence of operation state.

In contracts.md §"The account-rotation operation", append the following sentences to the end of the **Durable store** paragraph:

A claim identifier recorded under spec.md §"Account rotation and quota supervision" for an unsettled reset claim MUST NOT be stored where a concurrent writer can overwrite it. It MUST be written atomically, with owner-only permissions, to a record of its own in the same host state directory, separate from the cache, before the claim is sent, and MUST be removed only once the claim's outcome has been read. A concurrent overwrite of the cache MUST NOT be able to discard it, because the cost of losing it is a second use of a scarce reset, not a cached reading.

In the **Concurrency** paragraph of the same section, replace "Any number of concurrent callers MUST be able to report safely, since observation is read-only. At most one MAY switch." with:

Any number of concurrent callers MUST be able to report safely, since observation is read-only. At most one MAY switch or claim a reset, because both are made only while holding the decision lock.

In scenarios.md, add these scenarios after "## Scenario: A reset lapsing beyond the expiry horizon is not claimed early":

```gherkin
## Scenario: A refilled protected account is not preferred over an unprotected one

Given a protected account's lapsing reset was claimed on this pass

And the active account must be left and an unprotected candidate is eligible

When the operation selects a destination

Then it selects the unprotected candidate

## Scenario: A retried claim reuses its identifier

Given a claim was sent for an account's reset and its response was lost

When the next pass retries that claim

Then it sends the claim identifier recorded before the first attempt

## Scenario: A concurrent reporting pass cannot discard an unsettled claim identifier

Given a claim identifier was recorded for an unsettled claim

And a concurrent reporting pass rewrites the operation's cache

When the next pass retries the claim

Then it sends the recorded claim identifier

## Scenario: A spend-capped account is not given a reset

Given the active account cannot serve because its monthly spend cap is reached

And its windows are below every rotation threshold

And it holds a usable reset

When a scheduled pass runs

Then the operation claims no reset on the ground of the spend cap

## Scenario: A manual invocation claims no reset

Given the active account holds a usable reset lapsing within the expiry horizon

When an invocation without the scheduled marker runs

Then the operation claims no reset

## Scenario: A provider-refused claim is reported, not failed

Given the provider answers a claim that the reset was already used

When the pass completes

Then the claim line reports that outcome

And the pass exits zero if nothing else failed
```

