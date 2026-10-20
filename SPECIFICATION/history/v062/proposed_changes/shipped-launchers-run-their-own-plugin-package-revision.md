---
proposal: shipped-launchers-run-their-own-plugin-package.md
decision: accept
revised_at: 2026-10-20T11:37:31Z
author_human: Chad Woolley <thewoolleyman@gmail.com>
author_llm: claude-opus-5-5
---

## Decision and Rationale

Accepted verbatim. The clause generalizes contracts.md §'Daemon invocation' to every shipped launcher and adds the governing scenario, so overseer-uzvcbn.2 (the measured cwd-shadowing defect, where a launcher run from inside this checkout imported the checkout's overseer package and launched a stale runtime) has a heading to be graded against. It adds no overseerd option and no feature scope, and it agrees with contracts.md §'Bootstrap preconditions' and the llm-provider-manager plugin-root resolution clause. Decided under spec_governance.revise_decision_mode=delegated with independent auto-spawned ratification review (NO BLOCKERS on the exact bytes). The reviewer's non-blocking notes are left for a later revision: whether the launcher-level plugin-root refusal orders against constraints.md 'BEFORE every other startup gate', which channel llm-provider-manager uses to name the missing root, and the shared word 'launcher' versus 'not a standalone launcher' in Bootstrap preconditions.

## Resulting Changes

- contracts.md
- scenarios.md

## Ratification Review

ratification_review: auto-spawn
reviewer_model: opus
reviewer_identity: opus
separate_reviewer: True
read_only: True
reviewed_at: 2026-10-20T11:36:52Z
verdict: NO BLOCKERS
proposal_stem: shipped-launchers-run-their-own-plugin-package
content_digest: 70b710c11fb4492f674dbcdb5aec77f00cc09acc5ba61f3962fa08f6fda801cf
