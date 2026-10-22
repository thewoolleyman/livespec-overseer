---
proposal: live-exercise-agent-client-isolation.md
decision: modify
revised_at: 2026-10-22T05:00:11Z
author_human: Chad Woolley <thewoolleyman@gmail.com>
author_llm: claude-opus-5-5
---

## Decision and Rationale

Accepted with modifications. The specification governed nothing about the live-exercise runner, which is the only sanctioned surface for authenticated host-captured release proof. A measured failure on the release host (a script-launcher Codex hidden by the scratch home, surfacing late as a bootstrap failure) shows that the agent-client binding and pre-start refusal must be contract, so that overseer-fr8f has a governing scenario. The section sits beside Non-interference with tracked work because the runner's first obligation is to touch neither the operator home nor the operator's real tracked sessions, terminal-backend servers or overseer stores. No design record is contradicted: the runner was previously unspecified.

## Modifications

Modified on independent ratification review (three blockers). (1) The credential sentence now acknowledges that the released checkout is copied into the scratch root. (2) The writable-path rule is stated by what is writable inside the namespace: only the runner scratch root and the operator-supplied evidence directory, with every other operator-home path hidden or read-only. (3) The undefined fleet term is replaced by the concrete set the runner must not touch: real tracked sessions, real terminal-backend servers, and home-directory overseer stores. Also folded in: refusal covers a client absent from PATH or a launcher whose target cannot be determined, the refusal names the client name or path, and the idle prompt is tied to the bootstrap lifecycle stage.

## Resulting Changes

- spec.md
- scenarios.md

## Ratification Review

ratification_review: auto-spawn
reviewer_model: opus
reviewer_identity: opus
separate_reviewer: True
read_only: True
reviewed_at: 2026-10-22T04:59:54Z
verdict: NO BLOCKERS
proposal_stem: live-exercise-agent-client-isolation
content_digest: 12c92166fd82019d30fd8cf47e7b3d95f4a588075dc6fd88463e44a0b4590927
