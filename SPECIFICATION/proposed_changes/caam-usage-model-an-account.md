---
topic: caam-usage-model-an-account
author: claude-opus-5-5
created_at: 2026-10-31T16:59:22Z
---

## Proposal: An account's usage reading is a set of limits, and an absent short window is a reading

### Target specification files

- SPECIFICATION/spec.md
- SPECIFICATION/scenarios.md

### Summary

States that each usage reading is a per-reading set of limits, so an account whose reading carries no short-window limit stays readable, is evaluated on the limits it does report with no short-window trigger and no short-window projection, and remains a rotation destination; a temporary short-window limit is honoured on exactly the readings that report it. Adds four scenarios.

### Motivation

Work item overseer-jqmojb, plan caam-generic-limit-windows (epic overseer-rumvpf); research in plan/caam-generic-limit-windows/research/2026-10-31-generic-limit-windows.md. Measured 2026-10-31: anthropic-1, anthropic-5 and anthropic-6 return no short-window figure (five_hour: null) and list only weekly limits, while their weekly utilization reads normally. Because the reader requires a short-window figure, those accounts are reported unreadable, and since anthropic-5 is the active account every scheduled pass since 2026-10-31T09:21:57Z has failed with exit 2. The provider documents this as a plan tier: "Ultra plans have a weekly limit, and verified Ultra accounts don't have a five-hour session limit", and such an account MAY carry a TEMPORARY limit, so presence is a property of a reading, not of an account. The section is already worded provider-agnostically, but nothing states what the operation does when an account has no short window, and **Rotation triggers** reads as if one always exists. Maintainer direction 2026-10-31, verbatim: "This should also incorporate forward-looking support for other non-Anthropic accounts. Make the 5-hour thing generic but able to handle other types of additional limits that may be throttling or governing it, regardless of where they come from." Coordinator confirmation of the plan's Definition of Done under ruling R301. Filed under topic caam-usage-model-an-account because the Dispatcher's spec-change-tier hold on overseer-e6bvmt names that topic: the hold releases only once that topic carries an accepted or modified revision (refusal recorded 2026-10-31T16:53Z, reason unratified-topic, generalization target contracts.md ## The account-rotation operation). This supersedes the earlier filing of the same content under caam-accounts-without-short-window-and-generic-limits (PR #2706), which this change removes.

### Proposed Changes

In spec.md section "Account rotation and quota supervision", insert the following paragraph immediately after **Observation**.

**An account's usage reading MUST be a set of limits, and an absent short window MUST be a reading, not a failure.** A provider reports, for each account on each reading, a SET of limit windows, and which windows it reports is a property of that READING: a plan tier MAY carry no short-window limit at all, and an account on such a tier MAY carry a temporary short-window limit on some readings and none on others. The operation MUST parse each reading into a provider-agnostic set in which every limit carries its kind, its remaining figure, and its reset time where the provider reports one, and MUST decide on every reading, never once per account, whether a short-window limit is present. A reading that carries a usable weekly limit and no short-window limit MUST be treated as readable. For that reading the short-window threshold in **Rotation triggers**, the fast-drain trigger, and every short-window burn-rate or baseline computation MUST NOT be evaluated, and the burn rate MUST be taken as unknown; the weekly reserve, the expiring-quota drain, the refusal trigger, every protection floor and the scoped-model reserve MUST still apply. Such an account MUST remain a rotation destination on the dimensions it reports. Where a rotation is compared on the short-window dimension, a candidate whose current reading carries no short-window limit MUST be treated as holding the full short-window headroom, because no short-window limit constrains it; it MUST count as clear of the short-window threshold for the expiring-quota drain; and the capacity test MUST NOT exclude it on the short-window dimension. The operator-facing account table MUST show such an account's weekly figures and MUST state that its current reading has no short-window limit, and MUST NOT report it as unreadable. A short-window limit that appears on a later reading MUST be evaluated against every short-window rule on that reading, and its absence on a still later reading MUST return the account to evaluation without a short-window trigger. The operation MUST NOT carry a short-window figure, baseline or burn rate across a reading that reported no short-window limit.

In the same section, in **Rotation triggers**, replace "The operation MUST rotate when the active account's short-window allowance is at or above a configurable threshold," with "The operation MUST rotate when the active account's current reading carries a short-window limit and that allowance is at or above a configurable threshold,".

In scenarios.md, add:

## Scenario: A scheduled pass evaluates an active account that has no short-window limit

Given the active account's usage reading carries a weekly limit and no short-window limit

When a scheduled pass runs

Then the pass reads the active account successfully and evaluates the weekly reserve against it

And the pass does not fail on the missing short-window limit

And the account table shows the active account's weekly figures and states that it has no short-window limit

## Scenario: An account with no short-window limit is not reported unreadable

Given a managed account's usage reading carries a weekly limit and no short-window limit

When a pass reports the account table

Then the account's row shows its weekly figures and states that it has no short-window limit

And the row does not report the account as unreadable

## Scenario: An account with no short-window limit is selected on a short-window rotation

Given the active account has crossed its short-window rotation threshold

And a live-verified candidate's usage reading carries a weekly limit above the weekly reserve and no short-window limit

When a scheduled pass runs

Then that candidate is eligible as a rotation destination

## Scenario: A temporary short-window limit is honoured only on the readings that report it

Given the active account's previous reading carried no short-window limit

And its current reading carries a short-window limit at or above the short-window threshold

When a scheduled pass runs

Then the short-window trigger is evaluated and fires on that reading

And on a later reading that carries no short-window limit, the account is evaluated without a short-window trigger

## Proposal: Unrecognised limits from any provider leave an account readable and shown

### Target specification files

- SPECIFICATION/spec.md
- SPECIFICATION/scenarios.md

### Summary

States that a limit kind the operation does not recognise, from any provider, is recorded and shown in the account table and never makes the account unreadable, and reserves unreadable for a reading with no usable limit or a malformed one. Adds one scenario.

### Motivation

Work item overseer-jqmojb, plan caam-generic-limit-windows (epic overseer-rumvpf); research in plan/caam-generic-limit-windows/research/2026-10-31-generic-limit-windows.md. Measured 2026-10-31: anthropic-1, anthropic-5 and anthropic-6 return no short-window figure (five_hour: null) and list only weekly limits, while their weekly utilization reads normally. Because the reader requires a short-window figure, those accounts are reported unreadable, and since anthropic-5 is the active account every scheduled pass since 2026-10-31T09:21:57Z has failed with exit 2. The provider documents this as a plan tier: "Ultra plans have a weekly limit, and verified Ultra accounts don't have a five-hour session limit", and such an account MAY carry a TEMPORARY limit, so presence is a property of a reading, not of an account. The section is already worded provider-agnostically, but nothing states what the operation does when an account has no short window, and **Rotation triggers** reads as if one always exists. Maintainer direction 2026-10-31, verbatim: "This should also incorporate forward-looking support for other non-Anthropic accounts. Make the 5-hour thing generic but able to handle other types of additional limits that may be throttling or governing it, regardless of where they come from." Coordinator confirmation of the plan's Definition of Done under ruling R301. Filed under topic caam-usage-model-an-account because the Dispatcher's spec-change-tier hold on overseer-e6bvmt names that topic: the hold releases only once that topic carries an accepted or modified revision (refusal recorded 2026-10-31T16:53Z, reason unratified-topic, generalization target contracts.md ## The account-rotation operation). This supersedes the earlier filing of the same content under caam-accounts-without-short-window-and-generic-limits (PR #2706), which this change removes.

### Proposed Changes

In spec.md section "Account rotation and quota supervision", insert the following paragraph immediately after the paragraph added by the limit-set proposal above.

**A limit the operation does not recognise MUST be shown and MUST NOT make an account unreadable.** A provider MAY report additional limits that throttle or govern an account, and the operation MUST accept them from any provider without becoming unable to read the account. A limit whose kind the operation does not recognise MUST be recorded in the reading's limit set with its provider-reported name, remaining figure and reset time where reported, and the operator-facing account table MUST show it beside the account's other windows. An unrecognised limit MUST NOT on its own fire a rotation trigger, define a comparison dimension, or disqualify a candidate, because no rule in this section states its meaning; a limit kind gains a trigger only when this section names it. The operation MUST report a reading as unreadable only when it carries no usable limit at all or is malformed; a reading that lacks a particular window, or carries a window the operation does not recognise, MUST NOT be reported as unreadable and MUST NOT be a failure path under **Fail loudly**.

In scenarios.md, add:

## Scenario: An unrecognised limit leaves the account readable and is shown

Given a managed account's usage reading carries a weekly limit and a limit of a kind the operation does not recognise

When a pass reports the account table

Then the account is read successfully and its weekly figures are shown

And its row shows the unrecognised limit by its provider-reported name

And the unrecognised limit does not fire a rotation trigger

## Proposal: The Anthropic usage response maps to a limit set, and a pass over such readings is a completed pass

### Target specification files

- SPECIFICATION/contracts.md

### Summary

Adds the provider wire contract under ## The account-rotation operation that the two spec.md proposals above need: how the Anthropic usage response maps to the per-reading limit set, that a null or absent five_hour object is a reading with no short-window limit rather than a failure, that unmapped limits are carried as unrecognised limits, and that a pass over such readings exits zero under the exit contract.

### Motivation

Work item overseer-jqmojb, plan caam-generic-limit-windows (epic overseer-rumvpf); research in plan/caam-generic-limit-windows/research/2026-10-31-generic-limit-windows.md. Measured 2026-10-31: anthropic-1, anthropic-5 and anthropic-6 return no short-window figure (five_hour: null) and list only weekly limits, while their weekly utilization reads normally. Because the reader requires a short-window figure, those accounts are reported unreadable, and since anthropic-5 is the active account every scheduled pass since 2026-10-31T09:21:57Z has failed with exit 2. The provider documents this as a plan tier: "Ultra plans have a weekly limit, and verified Ultra accounts don't have a five-hour session limit", and such an account MAY carry a TEMPORARY limit, so presence is a property of a reading, not of an account. The section is already worded provider-agnostically, but nothing states what the operation does when an account has no short window, and **Rotation triggers** reads as if one always exists. Maintainer direction 2026-10-31, verbatim: "This should also incorporate forward-looking support for other non-Anthropic accounts. Make the 5-hour thing generic but able to handle other types of additional limits that may be throttling or governing it, regardless of where they come from." Coordinator confirmation of the plan's Definition of Done under ruling R301. Filed under topic caam-usage-model-an-account because the Dispatcher's spec-change-tier hold on overseer-e6bvmt names that topic: the hold releases only once that topic carries an accepted or modified revision (refusal recorded 2026-10-31T16:53Z, reason unratified-topic, generalization target contracts.md ## The account-rotation operation). This supersedes the earlier filing of the same content under caam-accounts-without-short-window-and-generic-limits (PR #2706), which this change removes.

### Proposed Changes

In contracts.md section "The account-rotation operation", insert the following paragraph immediately before **Capacity class source**.

**Usage reading source.** For the Anthropic provider, each account's usage reading MUST be read from `GET https://api.anthropic.com/api/oauth/usage`, and the response MUST be mapped onto the limit set defined in spec.md §"Account rotation and quota supervision" as follows. The `five_hour` object MUST map to the short-window limit and the `seven_day` object to the weekly limit, each taking its remaining figure from `utilization` and its reset time from `resets_at` where present. A `five_hour` that is `null` or absent MUST map to a reading with no short-window limit and MUST NOT be treated as a malformed response; the same MUST hold of any other window the provider omits. Each entry of the response's `limits` list that the operation does not map onto a window it recognises MUST be carried into the limit set as an unrecognised limit under its provider-reported kind, with its figure and reset time where reported, and MUST NOT make the reading fail. A response that is not a JSON object, or that carries neither a usable weekly limit nor a usable short-window limit, MUST be reported as unreadable. A provider added later MUST supply its own mapping onto the same limit set and MUST NOT require any rule in spec.md to name that provider.

In the same section, in **Exit contract**, append: "A pass whose readings carry no short-window limit, or carry an unrecognised limit, is a completed pass and MUST exit zero when it otherwise held, reported, or switched successfully."
