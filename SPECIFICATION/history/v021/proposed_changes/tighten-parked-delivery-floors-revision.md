---
proposal: tighten-parked-delivery-floors.md
decision: accept
revised_at: 2026-08-19T03:55:57Z
author_human: thewoolleyman <chad@thewoolleyman.com>
author_llm: claude-opus-5
---

## Decision and Rationale

Accepted after two rounds of independent ratification review of these exact bytes, both NO BLOCKERS. The change closes two non-blocking findings deferred from v020's own review. The first adds a Given pinning that the parked-delivery membership is not keyed on the human-blocked status literal -- the measured failure mode, since the originating incident's row reported a picker-stall status while the negative control reported the human-blocked one, both with the picker open. It is phrased as the governed negative rather than by naming the picker-stall status, which is referenced in v020's prose but defined nowhere in the ratified tree; a normative scenario must not depend on an ungoverned term. The proposal states precisely what that pin does and does not enforce: the clause it serves is a universally quantified negative that no finite Given/When/Then can close, so the scenario pins a representative discriminator and the normative clause governs every unenumerated case. The second states the routing floor's degraded-snapshot leg -- where no usable row exists the picker state is UNDETERMINED and the foreman fails closed toward holding, justified normatively by the asymmetry that an unwarranted hold is visible and bounded while an unwarranted delivery is observed by no one -- and it ships with its own scenario rather than as a prose-only MUST, which was the blocking finding against v020 round 1. Round 2 confirmed the paragraph restructuring did not re-scope the cardinal-rule disclaimer or any MUST. The cardinal rule is unaffected; nothing here authorizes any act.

## Resulting Changes

- spec.md
- scenarios.md

## Ratification Review

ratification_review: auto-spawn
reviewer_model: fable
reviewer_identity: fable
separate_reviewer: True
read_only: True
reviewed_at: 2026-08-19T03:55:00Z
verdict: NO BLOCKERS
proposal_stem: tighten-parked-delivery-floors
content_digest: d92cff6e882e18067d7a9cd344441bcec1d3f80c5bf0304795864533e4309d97
