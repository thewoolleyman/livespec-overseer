---
proposal: malformed-state-rejection.md
decision: modify
revised_at: 2026-10-30T19:51:02Z
author_human: Chad Woolley <thewoolleyman@gmail.com>
author_llm: claude-opus-5-5
---

## Decision and Rationale

Accepts the proposal's intent: a malformed state value must not suppress the wrap-up, and the daemon moves the bad file aside and names it in the next wrap-up. Modified after independent review found one blocker: as filed, the rename and attention membership did not carve out a track done because its plan is archived, which spec.md §'The terminal declaration' excludes from every act and every non-gate attention member.

## Modifications

(1) The rename MUST NOT fire on a track done because its plan is archived, and such a track remains an attention member only through live gate evidence. (2) The rename happens BEFORE that tick composes any wrap-up, so the observation-tick wrap-up carries the rejected-value line. (3) The guard is cited as the existing same-token, same-modification-time guard of §'The wrap-up injection'. (4) The echoed rejected value has control characters removed and is truncated to at most 120 characters.

## Resulting Changes

- contracts.md
- scenarios.md

## Ratification Review

ratification_review: auto-spawn
reviewer_model: sonnet
reviewer_identity: sonnet
separate_reviewer: True
read_only: True
reviewed_at: 2026-10-30T19:49:38Z
verdict: NO BLOCKERS
proposal_stem: malformed-state-rejection
content_digest: 3b981c1254c4f4beb3ef118f1b81a086871fd3788cc708c33de2c56bf77841ce
