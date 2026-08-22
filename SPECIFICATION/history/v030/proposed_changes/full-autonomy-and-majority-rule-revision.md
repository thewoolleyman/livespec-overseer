---
proposal: full-autonomy-and-majority-rule.md
decision: modify
revised_at: 2026-08-22T00:42:31Z
author_human: thewoolleyman <chad@thewoolleyman.com>
author_llm: claude-fable-5
---

## Decision and Rationale

Accepted with the modifications listed below. The proposal turns the maintainer's standing orders for this repository (seat anchor overseer-z5fo4y, 2026-08-20T22:38:36Z and 2026-08-21T22:38:29Z) into a configured delegation: a fail-closed full_autonomy key and a decision_rule lever whose default, unanimous, is byte-for-byte the behaviour this tree ratified through v028, and whose majority value is the rule the orders demand. It also ratifies the majority outcome that overseer-5stpf2 / PR #1476 shipped unconditionally on 2026-08-21T23:25:11Z, closing a drift that otherwise exists on master today. The four floors that survive (the cardinal rule, actuator-only mutation, the security dissent, journal-before-act) are named verbatim; the floor categories this tree binds to by reference from the orchestrator and livespec-core contracts are kept escalated by text, so binding-by-reference stays honest; every new MUST has a scenario and every scenario a MUST. Decision ownership: delegated per spec_governance.revise_decision_mode, decider this plan session (foreman-full-autonomy-option, claude-fable-5), with the independent read-only fable reviewer returning NO BLOCKERS on the exact resulting bytes. Plan anchor overseer-3h4s5w, child overseer-3h4s5w.1.

## Modifications

Three blockers from the independent round-one review, each accepted. (1) The unqualified report-only default contradicted the full_autonomy implication: spec.md's preamble, contracts.md's valve-disposition section, and the two default-resolution scenarios now condition the report-only default on full_autonomy resolving to false. (2) The proposal relaxed 'locally-owned' floor categories that this tree never defines; the ratified text now states that this specification defines no floor category of its own at this revision, that both categories are bound by reference and stay escalated under full_autonomy, and that a category this tree later defines is panel-decidable under majority unless its defining clause says otherwise; the majority scenario's Given is 'a human valve whose category sits below no floor'. (3) The authority-widening leg had no scenario: added 'A needs-human dissent without a security risk kind is outvoted under the majority rule'. Two review notes also taken: the risk kind is enumerated as security or other, and 'a panel of the wrong size' became 'a reviewer set that does not match the constituted panel'. Round two found one residual of blocker one, the unrecognized-value scenario and its contracts.md sentence, now qualified the same way, and spec.md's contradiction sentence now names the unrecognized-value case too. Re-based onto v029 (the convene obligation and the wait-premise record, ratified by another thread first): the convene obligation's sentence about relaxing the unanimity requirement now reads 'the requirement that a verdict satisfy the effective decision rule and be typed', the alignment the proposal pre-announced. Heading-coverage TODO rows for the eight new scenarios are owned by the implementing children.

## Resulting Changes

- spec.md
- contracts.md
- constraints.md
- scenarios.md

## Ratification Review

ratification_review: auto-spawn
reviewer_model: fable
reviewer_identity: fable
separate_reviewer: True
read_only: True
reviewed_at: 2026-08-22T00:41:57Z
verdict: NO BLOCKERS
proposal_stem: full-autonomy-and-majority-rule
content_digest: 8134137b60ad1b5afae3fb79d56df2684a0a43508928b7ca913c39b0acfede70
