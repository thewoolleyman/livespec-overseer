---
proposal: daemon-message-channel-delivery.md
decision: modify
revised_at: 2026-10-15T17:02:56Z
author_human: Chad Woolley <thewoolleyman@gmail.com>
author_llm: claude-herdr-overseer
---

## Decision and Rationale

Delegated decision under the maintainer's in-session rulings recorded on livespec-dev-tooling-dfixhe at 2026-10-15T00:08Z ('I authorize you to run the revise on my behalf and approve them ... after a quick Fable subagent review') and 00:09Z/00:22Z, executed by the stability-freeze driver (gitops-fleet-capacity-monitoring). The driver's Fable review of the 2f8184d7 bytes returned BLOCK with two fixes (contracts.md heading coverage for the new H2; a channel hook in both keep-going nudge sections); both were applied verbatim and the driver accepted the delta without further review by message at about 17:0xZ 2026-10-15. Independent Opus ratification review: NO BLOCKERS on the final digest 8f6f825e0e9b867b1620d08c2ade5b2854ccac5cab58870af7eb7fc0e5a9c78c. Serves overseer-uepcr6 (plan herdr-overseer): deliver daemon messages through a session-bound channel where one is supported.

## Modifications

Accepted with modification. (1) The post-restart RESUME PROMPT is NOT a daemon message under the new contracts.md section: the proposal admitted it, but the ratified restart rules retry a dropped resume against the composer and key self-heal and attention on the composer holding the exact resume text, which a channel delivery cannot satisfy; its channel delivery is deferred to its own proposal (recorded on overseer-uepcr6). The pair nudge and the picker-stall relay likewise keep their paste forms. (2) spec.md is edited as well as contracts.md and scenarios.md: one hook paragraph each in the supervision-round wrap-up text and in 'The keep-going nudge'. (3) Scenarios grew from the proposal's three to eleven, covering binding, fallback, the unconfirmed hold and its release, the paste-path record, and the no-fallback un-open. (4) The new contracts.md H2 and the eleven scenarios carry heading-coverage TODO rows and debt-register entries owned by overseer-uepcr6 under the spec-first admission.

## Resulting Changes

- contracts.md
- scenarios.md
- spec.md

## Ratification Review

ratification_review: auto-spawn
reviewer_model: opus
reviewer_identity: opus
separate_reviewer: True
read_only: True
reviewed_at: 2026-10-15T17:02:23Z
verdict: NO BLOCKERS
proposal_stem: daemon-message-channel-delivery
content_digest: 8f6f825e0e9b867b1620d08c2ade5b2854ccac5cab58870af7eb7fc0e5a9c78c
