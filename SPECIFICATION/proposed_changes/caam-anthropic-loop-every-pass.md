---
topic: caam-anthropic-loop-every-pass
author: claude-opus-5-5
created_at: 2026-11-14T04:31:24Z
---

## Proposal: Every pass names its non-default rotation thresholds

### Target specification files

- SPECIFICATION/contracts.md
- SPECIFICATION/scenarios.md

### Summary

Add a clause to contracts.md §"The account-rotation operation" requiring every pass to print one line naming each rotation-decision threshold (the short-window threshold, the weekly reserve, the scoped-model reserve and the eligibility margin) that is set to a value other than its default, with that value and the default, and to print no such line when every threshold is at its default. Add a scenario covering both cases.

### Motivation

Measured 2026-11-13 (overseer-gzjv4s). The maintainer said "Just stay on the 6 account. I will reset it when it gets close to 98%", and the loop then ran every pass from 07:42Z to 20:49Z with the weekly reserve overridden to 2 (CAAM_ROTATE_WEEKLY_RESERVE=2; default 10). The override showed only inside the hold line ("reserve 2%"), so nothing on screen said a default had been overridden. At the default 10% the 20:19Z pass would have rotated; instead anthropic-6 ran to 2-3% weekly left and every listed host stayed on it until the maintainer typed "rotate" at 20:51Z. The maintainer ruled "go back to 10%" and "make sure that the override rule is deleted". This clause is the guard that makes any future override visible on every pass.

### Proposed Changes

In SPECIFICATION/contracts.md §"The account-rotation operation", add this paragraph after **Reporting.**:

**Non-default thresholds are named.** The ROTATION-DECISION THRESHOLDS are the configurable values the selection rules of spec.md §"Account rotation and quota supervision" read: the short-window threshold and the weekly reserve of its **Rotation triggers** clause, the scoped-model reserve, and the margin of its **Eligibility** clause. An operator MAY set any of them away from its default for a pass. Every pass in which one or more of those thresholds is set to a value other than its default MUST print, before its account table, exactly one line naming each such threshold, its effective value and its default. A pass in which every rotation-decision threshold is at its default MUST NOT print that line. The line MUST NOT be folded into a hold, rotate or skip line, because a reader scanning for the decision MUST be able to tell that a default was overridden without parsing the decision's own wording.

In SPECIFICATION/scenarios.md, add:

## Scenario: A pass names each rotation threshold set away from its default

Given the weekly reserve is set to 2 for a scheduled pass, and its default is 10
And every other rotation-decision threshold is at its default
When the pass runs
Then the pass MUST print, before its account table, one line naming the weekly reserve, the value 2 and the default 10
And that line MUST NOT name any threshold that is at its default

Given every rotation-decision threshold is at its default
When a scheduled pass runs
Then the pass MUST NOT print a non-default-threshold line

At revise, add a tests/heading-coverage.json row for this scenario whose test is TODO, owned by overseer-gzjv4s.

## Proposal: An event-tied threshold override lapses once its event has happened

### Target specification files

- SPECIFICATION/contracts.md
- SPECIFICATION/scenarios.md

### Summary

Add a caller clause to contracts.md §"The account-rotation operation": a rotation-threshold override the maintainer ties to an event (for example, until an account's quota reset is used) lapses once that event has happened, and the caller MUST then run later passes at the default unless the maintainer renews it. Add a scenario.

### Motivation

The same 2026-11-13 incident (overseer-gzjv4s): the weekly-reserve override existed to hold anthropic-6 until the maintainer used its reset. The maintainer used the reset, but the override stayed in force for every later pass, because nothing said an event-tied override ends when its event happens. The caller (the operator surface that runs the loop) is the party that sets and carries an override, so the rule binds the caller, alongside the existing **Reporting.** obligations on it.

### Proposed Changes

In SPECIFICATION/contracts.md §"The account-rotation operation", add this paragraph after the **Non-default thresholds are named.** paragraph:

**An event-tied override lapses.** When the maintainer sets a rotation-decision threshold away from its default and ties that setting to an event, such as using an account's quota reset, the override lapses once that event has happened. From the first pass after the event, the caller MUST run passes with that threshold at its default, unless the maintainer renews the override. The caller MUST NOT carry an event-tied override past its event because no one withdrew it. This clause governs overrides the maintainer sets; it adds nothing to, and MUST NOT be read as changing, how a pass itself claims or spends a quota reset under spec.md §"Account rotation and quota supervision", which needs no threshold override.

In SPECIFICATION/scenarios.md, add:

## Scenario: A threshold override tied to an account's reset lapses once the reset is used

Given the maintainer set the weekly reserve to 2 until account A's quota reset is used, and its default is 10
And account A's quota reset has now been used
When the caller runs the next scheduled pass
Then that pass MUST run with the weekly reserve at its default of 10
And the pass MUST NOT print a non-default-threshold line for the weekly reserve

At revise, add a tests/heading-coverage.json row for this scenario whose test is TODO, owned by overseer-gzjv4s.
