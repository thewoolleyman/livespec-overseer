---
proposal: caam-anthropic-loop-every-pass.md
decision: modify
revised_at: 2026-11-14T08:49:41Z
author_human: Chad Woolley <thewoolleyman@gmail.com>
author_llm: claude-opus-5-5
---

## Decision and Rationale

Both proposals close the gap measured 2026-11-13 (overseer-gzjv4s): a weekly-reserve override (2 against a default of 10) ran every pass for thirteen hours, visible only inside the hold line, and outlived the event it was tied to. The first proposal is accepted as written: every pass names each rotation-decision threshold set away from its default on a line of its own, before the account table. The second is modified only to close a gap in who it binds. As proposed, it bound 'the caller', but contracts.md 'A host-started schedule' says a host-started pass on the role holder has no agent caller, so on the deployment that clause requires, the lapse rule would bind nobody. Delegated decision; independent read-only sonnet ratification review NO BLOCKERS on the exact final bytes.

## Modifications

Section 1 lands verbatim. Its two scenarios are formatted with a blank line between steps, matching neighbouring scenarios. Section 2: 'From the first pass after the event, the caller MUST run passes with that threshold at its default' becomes 'From the first pass after the event, every pass MUST run with that threshold at its default'. A new sentence places the duty to restore the default on the party that set the override: the caller, where the caller supplies the threshold to the passes it runs, or, under A host-started schedule, the operator session that wrote the override into that schedule's configuration. 'The caller MUST NOT carry' becomes 'That party MUST NOT carry'. The scenario's When-step 'When the caller runs the next scheduled pass' becomes 'When the next scheduled pass runs'. Both scenarios are inserted after 'The account table's columns align on every kind of row'.

## Resulting Changes

- contracts.md
- scenarios.md

## Ratification Review

ratification_review: auto-spawn
reviewer_model: sonnet
reviewer_identity: sonnet
separate_reviewer: True
read_only: True
reviewed_at: 2026-11-14T08:48:45Z
verdict: NO BLOCKERS
proposal_stem: caam-anthropic-loop-every-pass
content_digest: 563d33a535bcf6f48e7c8a3e51d45a71f558c63e3ddd76980ca588dd57f19cf1
