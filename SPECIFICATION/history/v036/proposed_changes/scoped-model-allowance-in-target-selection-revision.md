---
proposal: scoped-model-allowance-in-target-selection.md
decision: modify
revised_at: 2026-08-26T10:50:25Z
author_human: thewoolleyman <chad@thewoolleyman.com>
author_llm: caam-anthropic-loop-planner
---

## Decision and Rationale

ACCEPTED WITH MODIFICATIONS, after THREE rounds of independent adversarial review that found real defects in the first two drafts. The proposal's INTENT is adopted in full: a scoped-model allowance may influence rotation target selection, narrowly, because only the ACTIVE account's scoped allowance can satisfy an operator pin naming that model. The ratified TEXT differs substantially from the proposal's literal rendering, which is why this is modify rather than accept. ROUND 1 BLOCKERS, all three sustained and fixed. (a) The trigger was unconditioned on a pin existing, so it contradicted the prohibition the same clause retains -- with no pin set, rotating on scoped exhaustion is rotating to consume a scoped allowance. (b) The text said candidates MUST be compared on the scoped dimension; the reviewer read dimension_spent and found it returns inf for any dimension outside five_hour/seven_day, so that sentence would have specified a DEADLOCK -- every candidate ineligible, rotation frozen -- the exact opposite of the fix. (c) 'exactly three places' forbade the enforcement observation that the Model enforcement clause mandates. ROUND 2 BLOCKER, sustained and fixed. The eligibility waiver was available whenever a pin EXISTED, while its own oscillation justification assumed the stronger condition that the ACTIVE account cannot serve the pin. The reviewer walked a concrete two-account ping-pong against the shipped constants and showed the margin's anti-oscillation guarantee was defeated in the ordinary steady state this amendment is written for. It also found a second consequence: under a weekly-reserve trigger the waived margin is the weekly one while the proviso bounded only short-window. Both are cured by bounding the waiver to the capability case, with the converse stated explicitly rather than left to inference. ROUND 3: NO BLOCKERS on these exact bytes. ONE CAVEAT THE RECORD MUST CARRY, because it corrects a claim the AUTHOR made and the reviewer refused to let stand: the weekly-dimension path is NOT unreachable. Where scoped unsatisfiability coincides with a weekly-reserve or protection-floor trigger, binding() selects seven_day while the proviso still bounds only short-window. The outcome is safe, but it is safe because candidate_allowed independently excludes candidates below the reserve, and because is_eligible excludes a candidate at its own protection floor -- NOT because the proviso covers that path. Do not read the proviso as self-sufficient.

## Modifications

1. The whole exception is gated on an operator pin naming the scoped model, on every normative sentence including the Rotation triggers paragraph an implementer reads first. 2. The eligibility waiver is further bounded to the case where the ACTIVE account cannot serve the pinned model, with the converse ('where the active account CAN already serve it, the margin MUST apply unwaived') stated explicitly. 3. 'Candidates MUST be compared on the scoped dimension' is REMOVED entirely and replaced by a paragraph forbidding a scoped allowance as a comparison dimension and routing the sole-trigger case to the short-window dimension, with scoped availability governing only ranking. 4. The three-place bound is scoped to SELECTION, followed by an explicit sentence preserving the enforcement and operator-report observations other clauses require. 5. The serve-capability predicate is defined once, balance-only ('present and not fully spent'), matching the shipped predicate, and says a model that is available but not answering is the pin's concern rather than selection's. 6. The trigger covers a scoped allowance that is fully spent OR absent altogether, since under a pin both are equally unsatisfiable. 7. The Eligibility paragraph gains a cross-reference carrying the same bound and stating why oscillation remains impossible; the Ranking cross-reference direction is corrected to 'above'; the operator-pin sentence reads 'a pinned SCOPED model' so its delegation lands, and 'in addition to warning' so it extends rather than replaces the warn-and-honor pair. 8. Presentationally, the proposal's bullet list is rendered as an inline run with bolded Trigger / Eligibility / Ranking leads, because the section contains no bullet lists.

## Resulting Changes

- spec.md

## Ratification Review

ratification_review: auto-spawn
reviewer_model: opus
reviewer_identity: opus
separate_reviewer: True
read_only: True
reviewed_at: 2026-08-26T10:42:00Z
verdict: NO BLOCKERS
proposal_stem: scoped-model-allowance-in-target-selection
content_digest: 31c605fbe34e788c0cee13ef93d24653c8bec1b5fa86afde4fee1464a6dbac3d
