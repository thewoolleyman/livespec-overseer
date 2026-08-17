---
proposal: ready-activity-downgrade-contract.md
decision: accept
revised_at: 2026-08-17T03:09:48Z
author_human: thewoolleyman
author_llm: claude-fable-5
---

## Decision and Rationale

Accepted. Work-item `overseer-27ug3t` explicitly changes the supervision
contract from deleting or preserving a post-ready declaration to visibly
downgrading it on disk. The specification must match the shipped daemon
behavior so the state file remains a readable diagnostic surface and the round
can re-arm through the ordinary stale-acknowledgement path.

## Resulting Changes

- contracts.md
- spec.md
- scenarios.md
