---
proposal: factory-routing-default-petri.md
decision: accept
revised_at: 2026-10-22T23:09:52Z
author_human: Chad Woolley <thewoolleyman@gmail.com>
author_llm: claude-opus-5-5
---

## Decision and Rationale

Maintainer direction R668 (2026-10-22) makes the Petri-era Fabro cutover on gmktec the priority and approves the blocking steps; cutover item bd-ib-iud52v. The registry already maps petri to gmktec-xubuntu :32276, and the orchestrator repository already moved its own default to petri. The clause pinning legacy is the only obstacle, and keeping legacy declared preserves recorded legacy pins. A separate read-only Opus reviewer (the configured ratification reviewer) and a read-only Codex gpt-6-astra review both returned NO BLOCKERS on the exact resulting text. Coordinator ruling R678 assigns this pass v066 ahead of the unpushed live-exercise-one-install-root branch.

## Resulting Changes

- constraints.md

## Ratification Review

ratification_review: auto-spawn
reviewer_model: opus
reviewer_identity: opus
separate_reviewer: True
read_only: True
reviewed_at: 2026-10-22T22:18:00Z
verdict: NO BLOCKERS
proposal_stem: factory-routing-default-petri
content_digest: 3f28f50e5f44d3b34f10f69a9b1143b9494068707407cdbacfdc36c981663533
