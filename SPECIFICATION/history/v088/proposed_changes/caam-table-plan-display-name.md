---
topic: caam-table-plan-display-name
author: claude-sonnet-5-5
created_at: 2026-11-05T20:04:54Z
---

## Proposal: Show the provider's plan display name in a narrow capacity cell

### Target specification files

- SPECIFICATION/contracts.md
- SPECIFICATION/scenarios.md

### Summary

The account table's capacity cell currently shows the raw provider tier string (for example `large (default_claude_max_20x)`). Change `contracts.md` "Capacity class source" so the plan-name detail is the provider's plan display name (for Anthropic, `plan_display_name` from the same profile response, for example `Ultra`), falling back to the tier string when the display name is absent, and require the cell to be narrow enough that a seven-row table does not wrap in a 120-column terminal. The class mapping and the single read-only request are unchanged. Add one scenario pinning the behavior.

### Motivation

The provider now names these plans `Ultra`, so the tier string `default_claude_max_20x` reads as a stale plan name, and the 30-character cell makes the table wrap in narrow terminals. The profile response the capacity source already reads carries `plan_display_name`, so no new request is needed. The class used by the capacity test and destination ranking does not change, so the change has no effect on rotation or cost. Maintainer ruling recorded on epic livespec-dev-tooling-6tgd2z at 12:46:55Z item 3(a) ("a: yes"), relayed by legacy-coordinator-agent under R301 on 2026-11-05. Ledger item: overseer-zmkkef. `spec.md` already says the class is shown "with the provider's own plan name as detail", which the display name satisfies, so `spec.md` needs no edit.

### Proposed Changes

In `SPECIFICATION/contracts.md`, "Capacity class source", replace the sentence "Any other value MUST map to `unknown`, and the provider value MUST be shown as the plan-name detail." with: "Any other value MUST map to `unknown`. The plan-name detail MUST be the provider's plan display name taken from the same response (for the Anthropic provider, `plan_display_name`, for example `Ultra`), and MUST fall back to the `organization.rate_limit_tier` value when the response carries no display name. The class MUST still be derived only from `organization.rate_limit_tier`, never from the display name. The capacity cell MUST be narrow enough that an account table of seven rows does not wrap in a 120-column terminal." Add to `SPECIFICATION/scenarios.md`, after "The account table shows each account's capacity class", a new scenario titled "The capacity cell shows the plan display name without wrapping": Given the provider reports the display name `Ultra` and the tier `default_claude_max_20x` for an account; When the operation renders the account table for seven accounts in a 120-column terminal; Then the account's capacity cell shows the class with `Ultra` as detail, And the class is still `large`, And no row wraps. The `tests/heading-coverage.json` link for the new scenario MUST be added in the revise cut that accepts this proposal.
