---
proposal: codex-helper-spawned-from-a.md
decision: accept
revised_at: 2026-11-13T02:53:05Z
author_human: Chad Woolley <thewoolleyman@gmail.com>
author_llm: claude-opus-5-5:herdr-overseer
---

## Decision and Rationale

Accepted as refiled after one independent review round. Live process evidence now covers children spawned by every thread of a carrier, each once, failing soft per thread, so a Codex session held by a helper that a worker thread spawned is discovered and adopted like any other. This is the spec half of overseer-uzvcbn.21, whose dispatch the tier judge held for it (spec v095); the implementation and its test are owed by that item.

## Resulting Changes

- spec.md
- scenarios.md

## Ratification Review

ratification_review: auto-spawn
reviewer_model: sonnet
reviewer_identity: sonnet
separate_reviewer: True
read_only: True
reviewed_at: 2026-11-13T02:51:54Z
verdict: NO BLOCKERS
proposal_stem: codex-helper-spawned-from-a
content_digest: 04fa7eccc2c6d629f527c685504183c9c5a08779845dd8b3286a6c3b42fdfbdf
