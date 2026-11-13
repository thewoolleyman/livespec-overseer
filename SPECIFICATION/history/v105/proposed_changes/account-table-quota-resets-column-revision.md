---
proposal: account-table-quota-resets-column.md
decision: accept
revised_at: 2026-11-13T21:26:49Z
author_human: Chad Woolley <thewoolleyman@gmail.com>
author_llm: claude-opus-5-5:herdr-overseer
---

## Decision and Rationale

Accepted unmodified after an independent read-only sonnet ratification review reporting NO BLOCKERS, and a coordinator grade of PASS (re-graded at 9f9af908 after fixes a-e). Ratifies the maintainer's 2026-11-13 direction for the reset-handling track: one QUOTA RESETS column immediately left of EXTRA reading `<uses>, next expires in <d>d <h>h` (`0` for none, `unreadable` when unreadable), replacing v057's per-reset table detail; every account-table cell aligned under its header on every kind of row in displayed width, with columns sized from content; and the 120-column no-wrap capacity scenario reconciled to a terminal at least as wide as the table. Reviewer non-blocking notes carried to the implementation item overseer-fr3hnj: hours are whole hours rounded down (a sub-hour remainder shows `0h`); 'at least as wide as the table's header' means that rendering's header; the 'no short-window limit' text spans the 5H LEFT and 5H RESET columns and must end where the 5H RESET header ends; 'no usage reading' is the row the renderer prints with dashes.

## Resulting Changes

- spec.md
- scenarios.md

## Ratification Review

ratification_review: auto-spawn
reviewer_model: sonnet
reviewer_identity: sonnet
separate_reviewer: True
read_only: True
reviewed_at: 2026-11-13T21:21:30Z
verdict: NO BLOCKERS
proposal_stem: account-table-quota-resets-column
content_digest: 23648fe0556505317616e7fdafc54552fa1355e7d04b08c717287293b7004a80
