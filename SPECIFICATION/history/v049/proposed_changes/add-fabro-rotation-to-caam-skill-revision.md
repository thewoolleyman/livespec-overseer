---
proposal: add-fabro-rotation-to-caam-skill.md
decision: modify
revised_at: 2026-09-09T02:37:18Z
author_human: thewoolleyman <chad@thewoolleyman.com>
author_llm: claude-opus-5
---

## Decision and Rationale

Accepts all three proposals with modifications. The plan (epic overseer-rqkwyh) needs the account-rotation operation to publish which account it selected, so the factory's separately provisioned Claude credential can follow the rotation instead of being hand-rotated whenever it runs out. The three proposals are mutually dependent and ratify together: the Identity amendment makes the stable account identifier available on every determining pass, which is what lets the published record require it unconditionally, which is what makes the record rename-proof. Publication carries identity only and never credential material, preserving the section's existing Never-refresh and byte-identical-live-credential guarantees unchanged.

## Modifications

Five departures from the proposal as filed, four of them raised by independent review and one by a gate the proposal would have tripped.

1. Coverage rows acknowledge the scenario tier. Each of the ten new tests/heading-coverage.json rows ends its reason by naming the integration-tier requirement. Without it check-heading-coverage direction 4 rejects a scenarios.md row whose test is TODO, so the ratification commit could not have landed; verified with the shipped checker plus a control that fails when the sentence is removed.

2. Exit-contract precedence is stated rather than left to inference. The publication-failure clause now says that where it meets contracts.md Exit contract's zero-exit sentence for a pass that held, reported, or switched successfully, the failure rule prevails. The proposal left the two in unreconciled tension.

3. Concurrency records the unlocked publication window. contracts.md Concurrency now carries, as accepted and unfixed alongside the races it already lists, that publication happens outside the decision lock, that the lock withholds it only from a pass that tried and failed to take it, that the identity-suppression rule withholds independently of the lock, and that a holding and a switching pass may both write with the last writer winning until the next pass converges. The proposal's lock carve-out did not cover a pass that never contends.

4. The publication-cadence clause is scoped to a FULLY determined account, defined inline as one whose profile name and stable identifier were both resolved, and now forbids reporting an activation the pass did not perform as a rotation of its own. Without the first, the clause's antecedent was wider than the identity-suppression carve-out; without the second, a scenario step asserted something no clause required.

5. Two scenarios were added and one renamed. Added: the published record never influences a later pass's selection (the selection-isolation clause was otherwise uncovered), and republishing an unchanged identity is not reported as a change (orphaned by the rename). Renamed: 'A pass that holds republishes the unchanged active identity' became 'A pass that holds after a hand-run activation publishes the account it found active', because the original heading contradicted its own body, which walks the account from A to B. Ten scenarios land rather than the proposal's eight. Filename citations were also de-backticked so they resolve file-scoped under the doctor citation gate rather than tree-wide.

## Resulting Changes

- spec.md
- contracts.md
- scenarios.md

## Ratification Review

ratification_review: auto-spawn
reviewer_model: opus
reviewer_identity: opus
separate_reviewer: True
read_only: True
reviewed_at: 2026-09-09T02:35:41Z
verdict: NO BLOCKERS
proposal_stem: add-fabro-rotation-to-caam-skill
content_digest: 6b4cdff34dc5c4f048297bdb90a32bab1db150ce9d6bbf362cf8caf8863e33fa
