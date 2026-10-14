---
topic: caam-capacity-aware-rotation
author: claude-opus-5-5
created_at: 2026-10-14T00:05:40Z
---

## Proposal: Rotate off an account that is refusing requests

### Target specification files

- SPECIFICATION/spec.md
- SPECIFICATION/scenarios.md

### Summary

Adds a refusal trigger: when the active account is observed refusing requests for a usage limit, a scheduled pass rotates off it whatever the usage figures report, and the switch line names the refusal.

### Motivation

On 2026-10-13 on host hp the loop held on anthropic-3, a small ($20) plan, while the usage API read 45% short-window remaining at 22:37Z; the account was refusing requests for its session limit at 22:46Z and read 0% at 22:49Z, and the operator had to switch by hand. The same day anthropic-2, downgraded to a small plan, fell about 70 short-window points per 30-minute pass where it had fallen about 10 on a large plan. Every rotation trigger is a percentage of an account's own window checked once per scheduled pass, so a small plan can drain inside one pass, and the operation has no signal for an account that is already refusing. Plan caam-mixed-plan-capacity (epic overseer-4nhrne, spec item overseer-prdmie); evidence in plan/caam-mixed-plan-capacity/research/001-mixed-plan-capacity.md, design and the maintainer's 2026-10-14 ruling (keep v055's capacity-blind ranking, make eligibility capacity-aware) in 002-scope-and-capacity-ruling.md.

### Proposed Changes

In spec.md §"Account rotation and quota supervision", insert the following paragraph immediately after the **Rotation triggers** paragraph:

**An account that is refusing requests MUST be left.** A refusal for a usage limit is ground truth about an account's allowance; a usage percentage is a report about it, and on 2026-10-13 the report read 45% remaining nine minutes before the account refused. The operation MUST therefore observe, on every pass, the refusal records that tracked sessions' transcripts carry, and MUST treat a USAGE-LIMIT REFUSAL as a rotation trigger on its own, alongside every trigger in **Rotation triggers**, whatever the usage figures report. A usage-limit refusal is a refusal the provider attributes to a short-window, weekly or rate limit of the account in use. The operation MUST attribute a refusal to the active account only when the refusal was recorded after the moment the operation last observed that account become active, and MUST disregard a refusal whose provider-reported reset time has passed. The operation MUST parse each provider's refusal records into a provider-agnostic refusal carrying the time it was recorded, the window it names (short-window or weekly; a rate limit counts as short-window) and the reset time the provider reported, if any; a provider whose records cannot be parsed MUST contribute no refusals rather than a guessed one. Detecting refusals MUST NOT send any request of its own.

When this trigger fires, candidates MUST be compared on the dimension the refusal names, and the active account's headroom on that dimension MUST be taken as zero, since an account that is refusing has none to offer whatever its reading says. Where this trigger and another fire on the same pass, the refusal's dimension MUST govern. The trigger MUST NOT relax the weekly reserve, any per-account protection floor, the zero-weekly disqualifier or the live-verification rule. Where no candidate survives those rules, the operation MUST hold and MUST report that the active account is refusing requests and that no account could be selected. A switch made under this trigger MUST be reported as such: the switch line MUST name the refusal as the reason and MUST state when the refusal was recorded.

In scenarios.md, add these scenarios after "## Scenario: An invocation without the scheduled marker does not drain":

```gherkin
## Scenario: A refusing active account is left whatever its usage reads

Given the active account's sessions recorded a short-window usage-limit refusal after the account became active

And the usage API reports the active account's short-window remaining above the rotation threshold

And an eligible candidate exists

When a scheduled pass runs

Then the operation rotates off the active account

And the switch line names the refusal as the reason and states when it was recorded

## Scenario: A refusal recorded before the account became active is not attributed to it

Given a usage-limit refusal was recorded before the active account became active

And the active account is clear of every rotation threshold

When a scheduled pass runs

Then the refusal does not trigger rotation

## Scenario: A refusal whose reset has passed does not trigger rotation

Given the active account recorded a usage-limit refusal whose provider-reported reset time has passed

And the active account is clear of every rotation threshold

When a scheduled pass runs

Then the refusal does not trigger rotation

## Scenario: A refusing account with no selectable candidate holds and says so

Given the active account is refusing requests for a usage limit

And no candidate survives the weekly reserve, the protection floors, the zero-weekly disqualifier and live verification

When a scheduled pass runs

Then the operation holds

And it reports that the active account is refusing requests and no account could be selected
```


## Proposal: Rotate off an account that will drain before the next pass

### Target specification files

- SPECIFICATION/spec.md
- SPECIFICATION/scenarios.md

### Summary

Adds a fast-drain trigger: a scheduled pass rotates when the active account's short-window remaining, projected at its observed burn rate across one schedule interval, would reach the rotation threshold before the next pass. The schedule interval itself is unchanged.

### Motivation

On 2026-10-13 on host hp the loop held on anthropic-3, a small ($20) plan, while the usage API read 45% short-window remaining at 22:37Z; the account was refusing requests for its session limit at 22:46Z and read 0% at 22:49Z, and the operator had to switch by hand. The same day anthropic-2, downgraded to a small plan, fell about 70 short-window points per 30-minute pass where it had fallen about 10 on a large plan. Every rotation trigger is a percentage of an account's own window checked once per scheduled pass, so a small plan can drain inside one pass, and the operation has no signal for an account that is already refusing. Plan caam-mixed-plan-capacity (epic overseer-4nhrne, spec item overseer-prdmie); evidence in plan/caam-mixed-plan-capacity/research/001-mixed-plan-capacity.md, design and the maintainer's 2026-10-14 ruling (keep v055's capacity-blind ranking, make eligibility capacity-aware) in 002-scope-and-capacity-ruling.md.

### Proposed Changes

In spec.md §"Account rotation and quota supervision", insert the following paragraph immediately after the paragraph added by the refusal-trigger proposal (or after **Rotation triggers** if that proposal is rejected):

**An account that will cross the threshold before the next pass MUST be left now.** The short-window threshold protects an account only if the account cannot spend its remaining margin between two passes, and on a small plan under fleet load it can. The operation MUST therefore keep, in its durable store, the active account's previous short-window reading and the time it was taken, and on each scheduled pass MUST compute the active account's SHORT-WINDOW BURN RATE as the fall in short-window remaining between that reading and the current one divided by the time between them. A burn rate MUST be computed only from two readings of the same short window — readings whose provider-reported short-window reset times agree within the one-minute tolerance defined under **Expiring weekly quota MUST be drained** — taken while the account was continuously the active account; otherwise the burn rate is UNKNOWN. A scheduled pass MUST rotate when the burn rate is known and the active account's short-window remaining, less the burn rate multiplied by the operation's schedule interval, is at or below the short-window rotation threshold. Candidates MUST be compared on the short-window dimension under this trigger. The trigger MUST NOT fire when the burn rate is unknown, is zero or is negative, and MUST NOT fire on an invocation without the scheduled marker, which already rotates under **Mode resolution**. It MUST NOT relax the weekly reserve, any per-account protection floor, the zero-weekly disqualifier or the live-verification rule. It MUST take precedence over the expiring-quota drain, and a move made under it counts as a short-window move for condition (f) of that clause.

The operation MUST NOT shorten or otherwise change its schedule interval in response to a burn rate. Projecting across the whole interval already moves the fleet one pass early, and the refusal trigger covers an account whose usage figures lag what it actually spent. A switch made under this trigger MUST be reported as such: the switch line MUST name the projected short-window drain as the reason and MUST state the burn rate and the projected remaining at the next pass.

In scenarios.md, add these scenarios:

```gherkin
## Scenario: An account projected to cross the threshold before the next pass is left

Given the active account's short-window remaining fell from 75% to 36% between two readings of the same window one schedule interval apart

And the short-window rotation threshold is 15% remaining

And an eligible candidate exists

When a scheduled pass runs

Then the operation rotates off the active account

And the switch line names the projected short-window drain and states the burn rate

## Scenario: A slowly draining account holds

Given the active account's short-window remaining fell from 75% to 65% between two readings of the same window one schedule interval apart

And the short-window rotation threshold is 15% remaining

When a scheduled pass runs

Then the fast-drain trigger does not fire

## Scenario: No burn rate is computed across a short-window reset

Given the active account's two most recent readings report short-window reset times more than one minute apart

When a scheduled pass runs

Then the burn rate is unknown

And the fast-drain trigger does not fire

## Scenario: No burn rate is computed across a switch

Given the active account became active after its previous reading was taken

When a scheduled pass runs

Then the burn rate is unknown

And the fast-drain trigger does not fire
```


## Proposal: Do not switch onto an account too small for the current load

### Target specification files

- SPECIFICATION/spec.md
- SPECIFICATION/contracts.md
- SPECIFICATION/scenarios.md

### Summary

Makes eligibility capacity-aware: a candidate that the fleet's current consumption, scaled to that candidate's capacity, would drain past the short-window threshold before the next pass is not eligible. Ranking is unchanged. The test is released only when the active account is refusing and no candidate passes it.

### Motivation

On 2026-10-13 on host hp the loop held on anthropic-3, a small ($20) plan, while the usage API read 45% short-window remaining at 22:37Z; the account was refusing requests for its session limit at 22:46Z and read 0% at 22:49Z, and the operator had to switch by hand. The same day anthropic-2, downgraded to a small plan, fell about 70 short-window points per 30-minute pass where it had fallen about 10 on a large plan. Every rotation trigger is a percentage of an account's own window checked once per scheduled pass, so a small plan can drain inside one pass, and the operation has no signal for an account that is already refusing. Plan caam-mixed-plan-capacity (epic overseer-4nhrne, spec item overseer-prdmie); evidence in plan/caam-mixed-plan-capacity/research/001-mixed-plan-capacity.md, design and the maintainer's 2026-10-14 ruling (keep v055's capacity-blind ranking, make eligibility capacity-aware) in 002-scope-and-capacity-ruling.md. Observed ratio between Anthropic's large and small plans on the short window: about 7x, not the nominal 20x, so the weights are configurable rather than hardcoded.

### Proposed Changes

In spec.md §"Account rotation and quota supervision", insert the following paragraphs immediately after the **Eligibility** paragraph:

**A candidate MUST be able to carry the current load until the next pass.** Every account has a CAPACITY CLASS, defined under the capacity-reporting clause below, and each class MUST carry a configurable relative CAPACITY WEIGHT. The operation MUST NOT hardcode a provider's nominal plan multiplier as a weight, because the nominal multiplier and the observed one differ (2026-10-13: about seven to one between Anthropic's large and small plans on the short window, against a nominal twenty). When the active account's short-window burn rate, as defined under the fast-drain clause, is known, a candidate's PROJECTED BURN is that burn rate multiplied by the active account's capacity weight divided by the candidate's capacity weight. A candidate MUST NOT be selected when its short-window remaining, less its projected burn multiplied by the operation's schedule interval, is at or below the short-window rotation threshold. This CAPACITY TEST MUST apply to every selection the operation makes, under every trigger including the expiring-quota drain, and to an invocation without the scheduled marker. When the burn rate is unknown the capacity test MUST NOT exclude any candidate.

Where a capacity class cannot be determined, the operation MUST be conservative toward the candidate and neutral toward the active account: a candidate of unknown class MUST be weighted as the smallest class configured for its provider, and an active account of unknown class MUST be given the candidate's own weight, so the candidate's projected burn equals the active account's burn rate. The capacity test MUST NOT relax any other rule.

The capacity test MUST be released only where the active account is refusing requests under the refusal trigger and no candidate that survives every other rule passes it. In that case the operation MUST select from the candidates that fail it, ranked by **Ranking** unchanged, because an account refusing requests serves nothing, and an account that drains before the next pass still serves until then. Outside that case, where the capacity test excludes every candidate, the operation MUST hold and MUST report that no candidate can carry the current load until the next pass.

In contracts.md §"The account-rotation operation", add after **Durable store**:

**Capacity weights.** Capacity weights MUST be configurable per provider and capacity class. The defaults MUST be: `small` 1, `medium` 2 and `large` 7. Only the ratio between two weights affects a decision. The medium default is deliberately low, which makes the capacity test stricter for medium accounts, because no medium-class ratio has been measured.

In scenarios.md, add these scenarios:

```gherkin
## Scenario: A small candidate that the current load would drain is not selected

Given the active account is in the large capacity class with a short-window burn rate of 10 points per schedule interval

And a candidate in the small capacity class holds 50% short-window remaining

And the capacity weights are large 7 and small 1

When the operation selects a destination

Then the small candidate is not selected

## Scenario: A small candidate is selectable under light load

Given the active account is in the large capacity class with a short-window burn rate of 1 point per schedule interval

And a candidate in the small capacity class holds 50% short-window remaining

And the capacity weights are large 7 and small 1

When the operation selects a destination

Then the capacity test does not exclude the small candidate

## Scenario: A candidate of unknown capacity is weighted as the smallest class

Given a candidate whose capacity class cannot be determined

And the active account's short-window burn rate is known

When the operation applies the capacity test

Then the candidate is weighted as the smallest capacity class configured for its provider

## Scenario: The capacity test is released for a refusing account when no candidate passes it

Given the active account is refusing requests for a usage limit

And every candidate that survives the other rules fails the capacity test

When a scheduled pass runs

Then the operation selects among those candidates by soonest weekly reset

## Scenario: The capacity test holds when it excludes every candidate and the active account is not refusing

Given the active account has triggered rotation on its short-window threshold

And the capacity test excludes every candidate

When a scheduled pass runs

Then the operation holds

And it reports that no candidate can carry the current load until the next pass
```


## Proposal: Report each account's capacity class from a live read

### Target specification files

- SPECIFICATION/spec.md
- SPECIFICATION/contracts.md
- SPECIFICATION/scenarios.md

### Summary

The account table shows each account's capacity class in provider-agnostic terms with the provider's plan name as detail, read live from the provider rather than from login-time credential fields, and shows unknown when it cannot be read.

### Motivation

On 2026-10-13 on host hp the loop held on anthropic-3, a small ($20) plan, while the usage API read 45% short-window remaining at 22:37Z; the account was refusing requests for its session limit at 22:46Z and read 0% at 22:49Z, and the operator had to switch by hand. The same day anthropic-2, downgraded to a small plan, fell about 70 short-window points per 30-minute pass where it had fallen about 10 on a large plan. Every rotation trigger is a percentage of an account's own window checked once per scheduled pass, so a small plan can drain inside one pass, and the operation has no signal for an account that is already refusing. Plan caam-mixed-plan-capacity (epic overseer-4nhrne, spec item overseer-prdmie); evidence in plan/caam-mixed-plan-capacity/research/001-mixed-plan-capacity.md, design and the maintainer's 2026-10-14 ruling (keep v055's capacity-blind ranking, make eligibility capacity-aware) in 002-scope-and-capacity-ruling.md. The vault's login-time plan fields still read the large plan for anthropic-2 after its downgrade; Anthropic's GET /api/oauth/profile returns the organization's current rate_limit_tier read-only (measured 2026-10-14, recorded in research note 002).

### Proposed Changes

In spec.md §"Account rotation and quota supervision", insert the following paragraph immediately after the **Observation** paragraph:

**Each account's capacity class MUST be observed live and reported.** Two accounts at the same percentage can hold very different absolute headroom, so the operator-facing report MUST show, for every account, its CAPACITY CLASS — one of `small`, `medium` or `large` — with the provider's own plan name as detail, or `unknown` when the class cannot be determined. The operation MUST determine the class on every pass from a read-only provider request that reflects the account's CURRENT plan, made with the same credential the pass uses for that account's usage, and subject to the same **Never refresh** rule. It MUST NOT derive the class from plan fields stored in a credential at login, which do not change when the plan does. A failed or unparseable read, or a provider plan name with no mapping, MUST yield `unknown`; the operation MUST NOT fall back to a stored or guessed class, and an unknown class MUST NOT on its own fail the pass.

In contracts.md §"The account-rotation operation", add after the capacity-weights paragraph:

**Capacity class source.** For the Anthropic provider, the current plan MUST be read from `GET https://api.anthropic.com/api/oauth/profile` with the account's OAuth access token and the `anthropic-beta: oauth-2025-04-20` header, taking `organization.rate_limit_tier`. The mapping MUST be: `default_claude_ai` to `small`, `default_claude_max_5x` to `medium`, and `default_claude_max_20x` to `large`. Any other value MUST map to `unknown`, and the provider value MUST be shown as the plan-name detail. A provider added to rotation later MUST supply its own source and mapping onto the same three classes.

In scenarios.md, add these scenarios:

```gherkin
## Scenario: The account table shows each account's capacity class

Given the provider reports a large plan for one account and a small plan for another

When the operation renders the account table

Then each row shows its capacity class with the provider's plan name as detail

## Scenario: A plan change shows without a fresh login

Given an account's stored login-time credential names a large plan

And the provider's live read reports a small plan for that account

When the operation renders the account table

Then that account's row shows the small capacity class

## Scenario: An unreadable plan shows unknown

Given the live plan read for an account fails

When the operation renders the account table

Then that account's row shows an unknown capacity class

And the pass does not fail on that account
```


## Proposal: Rest the capacity-blind ranking on the rules that bound a small account

### Target specification files

- SPECIFICATION/spec.md

### Summary

Keeps v055's ranking rule (soonest weekly reset, no capacity weight) and rewords only its rationale, whose claim that every trigger already bounds a small account's spend was false until the refusal, fast-drain and capacity-test rules exist.

### Motivation

On 2026-10-13 on host hp the loop held on anthropic-3, a small ($20) plan, while the usage API read 45% short-window remaining at 22:37Z; the account was refusing requests for its session limit at 22:46Z and read 0% at 22:49Z, and the operator had to switch by hand. The same day anthropic-2, downgraded to a small plan, fell about 70 short-window points per 30-minute pass where it had fallen about 10 on a large plan. Every rotation trigger is a percentage of an account's own window checked once per scheduled pass, so a small plan can drain inside one pass, and the operation has no signal for an account that is already refusing. Plan caam-mixed-plan-capacity (epic overseer-4nhrne, spec item overseer-prdmie); evidence in plan/caam-mixed-plan-capacity/research/001-mixed-plan-capacity.md, design and the maintainer's 2026-10-14 ruling (keep v055's capacity-blind ranking, make eligibility capacity-aware) in 002-scope-and-capacity-ruling.md.

### Proposed Changes

In spec.md §"Account rotation and quota supervision", in the **Ranking** paragraph, replace the sentence

"Soonest weekly reset is the only perishability order the operation can defend, and every trigger already bounds how far a small account is spent before the operation moves on; a capacity weight would systematically leave a smaller account's perishable balance to lapse."

with

"Soonest weekly reset is the only perishability order the operation can defend. Capacity governs whether an account can serve the current load, which the capacity test under **Eligibility** decides. How far a small account is spent is bounded by the refusal trigger and the fast-drain trigger, not by ranking. A capacity weight in ranking would systematically leave a smaller account's perishable balance to lapse, and it MUST NOT be reintroduced to compensate for a gap in those rules."

The rule sentence "Ranking MUST NOT weight a candidate by its plan capacity or rate-limit tier." and the scenario "## Scenario: Ranking ignores plan capacity" MUST remain unchanged.
