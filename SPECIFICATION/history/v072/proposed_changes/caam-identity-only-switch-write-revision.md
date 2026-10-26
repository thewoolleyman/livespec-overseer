---
proposal: caam-identity-only-switch-write.md
decision: modify
revised_at: 2026-10-26T07:48:53Z
author_human: Chad Woolley <thewoolleyman@gmail.com>
author_llm: claude-opus-5-5
---

## Decision and Rationale

Accepted in substance; modified after three rounds of independent opus review, the final one NO BLOCKERS. As filed, the clause left the identity keys open-ended, could not capture an already-unreadable live file, gave the settings write-back and the restores no atomicity or order, contradicted contracts.md Durable store once the operation restores the credential itself, and left the session-write race unrecorded.

## Modifications

(1) Account-identity keys are a closed list: `oauthAccount` and `userID` (measured as the only account-scoped keys that differ across all 7 vault copies). (2) All reads, parses and identity-key checks, and capture of the pre-switch bytes of the global state, settings and credential, happen BEFORE the account manager is invoked; a failure there changes nothing and reports a distinct failure. (3) Both post-install writes are atomic under the switch lock. (4) On a write failure the restore is ordered (credential, global state, settings), atomic per file, and every restore is attempted; a failed restore is a further distinct failure naming each unrestored file. (5) The post-switch verification also checks the live `oauthAccount`. (6) contracts.md Durable store covers the operation's own credential restore, and Concurrency records the session-write race. (7) The constraints.md carve-out covers the two file writes and the credential restore. (8) Five scenarios; their coverage rows and spec-first debt entries (owner overseer-hc7j) land in the same commit, outside the spec target.

## Resulting Changes

- spec.md
- constraints.md
- contracts.md
- scenarios.md

## Ratification Review

ratification_review: auto-spawn
reviewer_model: opus
reviewer_identity: opus
separate_reviewer: True
read_only: True
reviewed_at: 2026-10-26T07:48:51Z
verdict: NO BLOCKERS
proposal_stem: caam-identity-only-switch-write
content_digest: 70c365b26c5816e1744a18ccc57bc0a9a37115ae35e3a178467347110afad898
