---
proposal: central-factory-selection.md
decision: modify
revised_at: 2026-11-16T08:05:58Z
author_human: Chad Woolley <thewoolleyman@gmail.com>
author_llm: claude-opus-5-5
---

## Decision and Rationale

DoD of plan central-credential-service (epic overseer-iyfjbo, carrier overseer-shojan). Nothing central decides the factory account today: each dispatcher ranks its own injected slots by short-window headroom and ignores the protection floors, which drove anthropic-0 to 99% weekly utilization past its 10% floor between 2026-10-31 and 2026-11-14 (overseer-kzmmn7), and the seat-side workaround since pins every factory to anthropic-4. The proposal makes the role holder's rotation decide a separate factory account under the same eligibility, protection floors, weekly reserve and ranking, never the interactive account, decided after and unable to change the interactive decision, incumbent kept while it qualifies, a no-account record with a reason instead of a stale name, delivered identity-only to every listed host. Decided under spec_governance.revise_decision_mode delegated, with six post-step doctor findings in the new text fixed inside this revision at the coordinator's direction (see Modifications). The independent sonnet reviewer (claude-sonnet-5-5) found no blockers on the final bytes and confirmed every fix and cross-reference; its remaining non-blocking nits, left for a follow-up proposal, are that two behaviours have no dedicated scenario: a protected factory account replaced while an unprotected account qualifies, and the strictly-later written_at guard on a listed host. The consumer change (a dispatcher reading this record at run start) belongs to livespec-orchestrator-beads-fabro's specification.

## Modifications

The three changes are applied with headings verbatim, modified as follows. (a) Placement, contracts.md: the Factory selection record paragraph sits after the whole Published selection record entry, immediately before Concurrency, because that entry's two continuation paragraphs refer to it as 'The record' and one carries the no-expiry stale-identity rule the factory record deliberately reverses. (b) Whitespace, scenarios.md: one blank line precedes the first new scenario. Six doctor findings in the new text, fixed: (1) Not a delivery: the identity-only paragraph states that writing the factory selection record is NOT a delivery under Enrolled-host credential delivery, takes no delivery sequence, and is not subject to One decision, on the role holder or its rule that every delivery names the role holder's active account; this replaces 'Writing an identity-only record is not a sending of credential material, and'. (2) Ordering: the contracts.md Factory selection record entry adds that the delivery service MUST NOT replace a listed host's copy with a record whose written_at is not strictly later than the copy already there, and Concurrency accepts the factory record on the same last-writer-wins, next-pass-converges terms as the published selection record. (3) Failure: a failure to write the factory selection record fails the pass exactly as A publication failure MUST fail the pass without undoing it requires, and does not undo the interactive publication or any switch. (4) Protection ordering: a protected account MUST NOT be the factory account while any unprotected account qualifies, the same ordering A protected account MUST retain its own weekly floor applies to the interactive decision, and the keep/replace paragraph names it as a replacement trigger. (5) Scenarios: new scenario 'An unresolved interactive identity suppresses both selection records'; the no-qualifying scenario's Then lines now require profile and account_uuid both null and a non-empty reason. (6) Terminology: 'factory consumer(s)' becomes 'factory credential consumer(s)' throughout. Co-edit: TODO heading-coverage rows and debt entries for the seven new scenarios, owned by overseer-shojan, in the same pull request.

## Resulting Changes

- spec.md
- contracts.md
- scenarios.md

## Ratification Review

ratification_review: auto-spawn
reviewer_model: sonnet
reviewer_identity: sonnet
separate_reviewer: True
read_only: True
reviewed_at: 2026-11-16T08:05:56Z
verdict: NO BLOCKERS
proposal_stem: central-factory-selection
content_digest: 776ea1ff3cd4c3ec1ec8aa9e0fb7c1d505d06c75c0385f08035e0757e947e837
