---
proposal: shell-script-pipeline-verdicts.md
decision: modify
revised_at: 2026-11-09T19:40:21Z
author_human: Chad Woolley <thewoolleyman@gmail.com>
author_llm: claude:fleet-flaky-tests
---

## Decision and Rationale

Modified under delegated mode (placement only). No heading of this spec governed pipe correctness in repository shell scripts, so overseer-ng3b3w, the overseer share of the fleet pipefail sweep (plan fleet-flaky-tests), was refused at the R316 launch-time preflight at 2026-11-09T18:31:31Z. The section mirrors livespec-dev-tooling's ratified rule of the same name, which binds only that repository. legacy-coordinator-agent accepted this repository-local mirror; a core livespec proposal (livespec#3150) carries the fleet-wide end state. The independent read-only reviewer (sonnet) found no blockers on the exact bytes, and confirmed that all four sites the sweep found (scripts/check-pre-commit-doc-only.sh, scripts/overseer-live-exercise-codex-herdr.sh and two in scripts/overseer-live-exercise.sh) run under pipefail with their pipeline status used, so the rule governs each.

## Modifications

The proposed `## Shell script pipeline verdicts` H2 is dropped. Its paragraph, verbatim, becomes the last bullet of non-functional-requirements.md `## Constraints`. This repository requires every NFR H2 to mirror a spec-tree file (Boundary, Spec, Contracts, Constraints, Scenarios). overseer/test_enforcement_wiring.py::test_every_contributor_requirement_sits_in_the_section_mirroring_its_spec_file failed the first v092 push gate with "NFR sections that mirror no spec-tree file: ['Shell script pipeline verdicts']". `## Constraints` already holds contributor-facing rules for the repository's own scripts and tests. The scenario is unchanged. overseer-ng3b3w's References line therefore names `## Constraints` and the scenario heading.

## Resulting Changes

- non-functional-requirements.md
- scenarios.md

## Ratification Review

ratification_review: auto-spawn
reviewer_model: sonnet
reviewer_identity: sonnet
separate_reviewer: True
read_only: True
reviewed_at: 2026-11-09T19:39:49Z
verdict: NO BLOCKERS
proposal_stem: shell-script-pipeline-verdicts
content_digest: dbc4cbe2ff65b598fbadbd2fc90d0f45322640905952ddb39f92ed7eca28933d
