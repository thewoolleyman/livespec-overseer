---
proposal: undelivered-wrap-up-standing-round.md
decision: accept
revised_at: 2026-08-20T10:43:01Z
author_human: thewoolleyman <chad@thewoolleyman.com>
author_llm: claude-opus-5
---

## Decision and Rationale

ACCEPTED. The proposal adds one report-only mechanical-attention member for a track left carrying a standing round whose wrap-up was never delivered, completes the un-open rule in spec.md with the matching surfacing requirement, and pins both with a scenario pair. The asymmetry argument is sound and was verified against the shipped tree rather than inferred: contracts.md already carries a named member for the comparable expiry-path double failure (condition ready-expiry-both-writes-failed), and the un-open path carries a named condition for its OTHER failure mode (round-identity-undetermined) while the rollback failure has none. The condition is reachable -- clear_injection_stamp returns None and writes through the fail-soft atomic-write path, so the caller cannot observe the failure -- and it is unsurfaced, because the existing alert on that branch is emitted unconditionally and carries no condition string. The hazard is a certification one: every rejection branch of _ready_uncertifiable_reason falls through in that state, so a later ready is certifiable against a round whose wrap-up never landed, and a failed paste is itself evidence the session could not be reached. Accepted unmodified because the drafted text already carries the two properties an implementer could otherwise get wrong: membership requires BOTH failures in the SAME observation and excludes the paste-failure-alone case in terms, and the member is named by the state it leaves rather than by the operation that failed. The scope paragraph states the acting-behavior guarantee in full while naming the reporting-path change implementation requires, which is accurate rather than overstated. Independent read-only ratification review by the configured reviewer returned NO BLOCKERS on these exact bytes. The two new scenario headings are co-edited into tests/heading-coverage.json with test TODO and work_item overseer-dhkjxf, re-verified OPEN at the moment of writing.

## Resulting Changes

- spec.md
- contracts.md
- scenarios.md

## Ratification Review

ratification_review: auto-spawn
reviewer_model: fable
reviewer_identity: fable
separate_reviewer: True
read_only: True
reviewed_at: 2026-08-20T10:42:52Z
verdict: NO BLOCKERS
proposal_stem: undelivered-wrap-up-standing-round
content_digest: cec42e9643704926c1dde8ad048e02a7aa24f1cf4381c195079c7a632623280d
