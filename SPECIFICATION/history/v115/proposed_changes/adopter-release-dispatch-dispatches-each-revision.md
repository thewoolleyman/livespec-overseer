---
proposal: adopter-release-dispatch-dispatches-each.md
decision: accept
revised_at: 2026-11-15T03:12:49Z
author_human: Chad Woolley <thewoolleyman@gmail.com>
author_llm: claude-opus-5-5
---

## Decision and Rationale

Delegated decision (revise_decision_mode: delegated), accepted as written. Decider: legacy-coordinator-agent under R301, this fleet's delegated decision mode, as relayed through the stale-base-merge-options seat (plan epic livespec-dev-tooling-xowhol): ACCEPT as written. The clause binds adopter-release-dispatch.yml to livespec v247's fleet-wide adopter resolution rule (livespec#3242), mints one App token per resolved owner from the App already installed there (the route endorsed by legacy-coordinator-agent on overseer-j4ejek after the 2026-11-15 measurement), and keeps an unauthorized owner loud and counted rather than silent. Independent read-only ratification review (auto-spawn, sonnet) returned NO BLOCKERS for these exact bytes; its non-blocking observation that the MUST NOT wording reads loosely when an adopter's resolved owner equals the repository's own owner is left for a later proposal.

## Resulting Changes

- non-functional-requirements.md

## Ratification Review

ratification_review: auto-spawn
reviewer_model: sonnet
reviewer_identity: sonnet
separate_reviewer: True
read_only: True
reviewed_at: 2026-11-15T03:12:47Z
verdict: NO BLOCKERS
proposal_stem: adopter-release-dispatch-dispatches-each
content_digest: b447e40f07b02e5a9e6caff6dd2db5b39f87771f02cf7cfbf1c0cbe25925f77b
