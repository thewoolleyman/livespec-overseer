---
proposal: enrolled-host-refresh-push.md
decision: accept
revised_at: 2026-11-13T20:03:59Z
author_human: Chad Woolley <thewoolleyman@gmail.com>
author_llm: claude-opus-5-5
---

## Decision and Rationale

Plan central-credential-service (epic overseer-iyfjbo), work item overseer-r7pymu. Measured 2026-11-13: the push service never re-pushed an unchanged delivery, so gmktec, poweredge and hp read `stale` at 13:47Z while holding the current sequence 7 applied at 13:03Z, which made `stale` useless as the silent-host signal. The proposal adds one obligation to the Retry and timeouts paragraph of contracts.md: re-send the current delivery to a host that already holds it once its last successful push is older than half of `delivery.stale_after`, with the host's already-holds answer counted as a successful push that changes nothing on the host. It also adds one scenario after the silent-host scenario. The meaning of `stale` is unchanged, the newer-sequence-only apply rule and the no-refresh-token and in-memory rules are untouched, and no design record is contradicted. The independent reviewer's non-blocking notes (the clause is the first normative statement that a same-sequence answer counts as success; the scenario omits an unexpired-token precondition; restart behaviour of the in-memory delivery is an implementation concern) were weighed and need no change. Revise decision taken under coordinator R301 delegation (legacy-coordinator-agent), revise_decision_mode delegated: ACCEPT verbatim.

## Resulting Changes

- contracts.md
- scenarios.md

## Ratification Review

ratification_review: auto-spawn
reviewer_model: sonnet
reviewer_identity: sonnet
separate_reviewer: True
read_only: True
reviewed_at: 2026-11-13T20:03:30Z
verdict: NO BLOCKERS
proposal_stem: enrolled-host-refresh-push
content_digest: 1cc91784dd4af1128fbc389b2e5d179d575a16c8e9f2dd53e5a7baf19ede0430
