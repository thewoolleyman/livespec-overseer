---
proposal: supervise-plan-authors-two-layers.md
decision: modify
revised_at: 2026-08-03T04:22:39Z
author_human: thewoolleyman <chad@thewoolleyman.com>
author_llm: claude-opus-5
---

## Decision and Rationale

The live authoring clause incorrectly says supervise-plan creates one artifact although the shipped, load-bearing design creates the shared role layer and per-thread binder. Accepting the spec.md edit alone would leave constraints.md directly contradicting it, and the missing-role-layer HALT is observable behavior that requires its scenario half.

## Modifications

Applied the filed spec.md two-layer replacement; co-edited constraints.md with the assessment's exact two-artifact wording; and authored `## Scenario: A missing supervisor role layer halts the binder with a remedy` plus its TODO heading-coverage row as the co-edited scenario half of the assessed clause requiring the binder guard to HALT with a labelled REMEDY when `.ai/supervisor-protocol.md` is absent. The scenario introduces no intent beyond that clause, and no integration-tier test exists yet to cite.

## Resulting Changes

- spec.md
- constraints.md
- scenarios.md
- ../tests/heading-coverage.json
