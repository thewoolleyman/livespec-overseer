---
proposal: declaration-command.md
decision: modify
revised_at: 2026-10-31T15:01:06Z
author_human: Chad Woolley <thewoolleyman@gmail.com>
author_llm: claude-opus-5-5
---

## Decision and Rationale

Accepts the proposal's intent under maintainer direction 2026-10-31: overseer-declare becomes the session's single validated declaration channel, and no daemon text instructs a hand write. Modified after an independent review (no blockers, five should-fix items).

## Modifications

(1) The message list adds the pair-stall nudge and the instruction to clear a done before new work. (2) clear also removes the daemon's idle-with-context-left marker, which the keep-going nudge offers to clear, and leaves any other daemon-written value in place, reporting it with exit zero. It re-reads before deleting under a same-first-line, same-modification-time guard, and clear followed by a declaration satisfies spec.md's clear-before-resume obligations. (3) The invocation is an ABSOLUTE path to the composing daemon's runtime overseer-declare, which exists at composition, so it works for Codex sessions without PATH. (4) A pair member's ready reports arming against its own entity. (5) The maintainer may still hand-write or remove the file. (6) A fixed sentence 'Declare only through overseer-declare; never write or delete the state file by hand.' and a defined negative (no echo, redirection, rm or mkdir aimed at the state file) make the instruction scenario testable. (7) A third scenario covers clear.

## Resulting Changes

- contracts.md
- scenarios.md

## Ratification Review

ratification_review: auto-spawn
reviewer_model: sonnet
reviewer_identity: sonnet
separate_reviewer: True
read_only: True
reviewed_at: 2026-10-31T14:59:26Z
verdict: NO BLOCKERS
proposal_stem: declaration-command
content_digest: 85914e9d44188cbe875134a74ec930b752ef76a16a39069b9c767caf0d557b34
