---
proposal: vendored-exemption-intra-package-imports.md
decision: accept
revised_at: 2026-10-30T20:59:43Z
author_human: Chad Woolley <thewoolleyman@gmail.com>
author_llm: claude-opus-5-5
---

## Decision and Rationale

Accept. A wording repair that makes condition (b)'s allowed module-load import set explicitly include the vendored library's own modules, matching the clause's second sentence, its worked example and overseer-vqmq; nothing else in (b) loosens. Non-drift (origin: v027 ratification-review findings tracked as overseer-ntz1), so the delegated mode applies. The proposal's SHOULD-scenario is added proving both directions, with spec-first TODO coverage owned by new work-item overseer-a3m6. Independent read-only Sonnet reviewer (agent a40197a83b8280ad7) returned NO BLOCKERS on these exact bytes.

## Resulting Changes

- constraints.md
- scenarios.md
- ../tests/heading-coverage.json
- ../tests/heading-coverage-debt.json

## Ratification Review

ratification_review: auto-spawn
reviewer_model: sonnet
reviewer_identity: sonnet
separate_reviewer: True
read_only: True
reviewed_at: 2026-10-30T20:59:03Z
verdict: NO BLOCKERS
proposal_stem: vendored-exemption-intra-package-imports
content_digest: 9065b15e1454bff9de16ed060df4d2d4011db21518353ac35ef190535fea399c
