---
proposal: plan-thread-tombstone-ban.md
decision: accept
revised_at: 2026-08-04T16:05:31Z
author_human: thewoolleyman <chad@thewoolleyman.com>
author_llm: claude-opus-5
---

## Decision and Rationale

Accepted after two rounds of independent adversarial review. Round 1 returned DO-NOT-RATIFY with four blockers, all discharged: the draft sanctioned retired-slug reuse in MUST language while the shipped plan_thread_no_tombstone check hard-fails any both-present pair, so a repo doing what the spec protected would have gone permanently CI-red with no sanctioned green path; a categorical 'never on the files inside it' contradicted the bounded supervisor-handoff existence probe granted in the same section; the mechanism claim overstated what triggers it (the DIRECTORY, including via a symlink); and normative text was not delimited from proposal commentary. Round 2 confirmed all four discharged with no new blockers, and a sibling review caught a further defect in the rewrite — an unqualified move-back arm licensing a live directory whose epic is closed — now explicitly forbidden. DELIBERATELY SCOPED partial revise pass: the payload names only this topic, so the other in-flight proposals in this tree are neither read nor disposed of.

## Resulting Changes

- spec.md

## Ratification Review

ratification_review: manual-spawn
reviewer_model: fable
reviewer_identity: fable
separate_reviewer: True
read_only: True
reviewed_at: 2026-08-04T15:20:20Z
verdict: NO BLOCKERS
proposal_stem: plan-thread-tombstone-ban
content_digest: 26d43bca0fff828964a53858947b56426885facbe47d78e3b2316463c1536a43
