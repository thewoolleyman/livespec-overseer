---
proposal: rebind-a-row-whose-stored.md
decision: accept
revised_at: 2026-11-04T10:31:22Z
author_human: Chad Woolley <thewoolleyman@gmail.com>
author_llm: claude-opus-5-5:herdr-overseer
---

## Decision and Rationale

Accepted unmodified. The spec already treats the list path as read-only for done tracks and blocked onboarding, but the vanished-pane rebind clause was silent on which surface may rewrite the mapping store's coordinate and session identity. This makes the rebind and its identity re-record an act of the supervising loop only, requires the read-only list path to report the same classification without writing, and pins it as a final step of the existing rebind scenario, whose heading (and so its heading-coverage link) is unchanged. It restores the requirement removed from overseer-m2hwyd by the dispatch-stage tier judge on 2026-11-04; the list-path test that carries it is owed as a follow-up child of plan epic overseer-uzvcbn.

## Resulting Changes

- spec.md
- scenarios.md

## Ratification Review

ratification_review: auto-spawn
reviewer_model: sonnet
reviewer_identity: sonnet
separate_reviewer: True
read_only: True
reviewed_at: 2026-11-04T10:30:20Z
verdict: NO BLOCKERS
proposal_stem: rebind-a-row-whose-stored
content_digest: 49eb3fc56ddbeb7cb4727c28e1b12fe9b45f649036fcfead2b64f6e137d51829
