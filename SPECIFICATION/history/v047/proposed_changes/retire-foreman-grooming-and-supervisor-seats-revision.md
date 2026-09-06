---
proposal: retire-foreman-grooming-and-supervisor-seats.md
decision: modify
revised_at: 2026-09-06T17:02:35Z
author_human: thewoolleyman <chad@thewoolleyman.com>
author_llm: claude-opus-4-8[1m]
---

## Decision and Rationale

Accepted the maintainer-ruled removal (2026-09-06, recorded as scope event D5 on console plan epic livespec-console-beads-fabro-pzbdbo) of the foreman, grooming, and supervise-plan seats across all four governed spec files, reducing the supervision contract to overseerd plus the caam account-rotation loop. Every seat-only clause and scenario was deleted; every daemon clause that merely mentioned a seat was reworded to drop the mention; the deliberately-preserved bucket-1 residue (the caam 'Account rotation and quota supervision' section's foreman-pin/suffix clauses, the account-rotation contract's 'peer to the foreman and grooming operations' phrase, and the daemon supervisor pair-member protocol) was kept verbatim exactly as the proposal directs. doctor-static (exit 0, all findings pass/skipped) and check-heading-coverage (exit 0) pass on the result, and no dangling section references to any deleted section remain.

## Modifications

Two internal-consistency repairs beyond the proposal's literal enumeration, both required to keep the revision self-consistent and green. (M1) The reworded scenario 'A collision-derived worker name ending in foreman is refused' -> '...in supervisor is refused' also had its tests/heading-coverage.json entry heading updated to the new title; the proposal reworded the heading but did not update its coverage entry, and an entry citing a renamed heading fails check-heading-coverage's orphan-entry direction. (M2) The two scenarios 'An absent or non-true full_autonomy key changes nothing' and 'A contradictory configuration is surfaced while full autonomy governs' (and their heading-coverage entries) were also deleted: they exclusively exercise the deleted '## The foreman valve disposition' / full-autonomy contract and would otherwise be orphaned scenarios describing removed behavior. The proposal's enumerated heading-coverage entries plus these two (64 total: 61 scenarios, 3 contracts sections) were removed by mechanically dropping every entry whose (spec_file, heading) no longer resolves to a current heading -- exactly check-heading-coverage's orphan direction. tests/heading-coverage.json is not a spec-target file, so it is edited directly in the same revision PR rather than through resulting_files, per the proposal's 'in the SAME revision pull request' directive.

## Resulting Changes

- constraints.md
- contracts.md
- scenarios.md
- spec.md

## Ratification Review

ratification_review: auto-spawn
reviewer_model: opus
reviewer_identity: opus
separate_reviewer: True
read_only: True
reviewed_at: 2026-09-06T17:01:29Z
verdict: NO BLOCKERS
proposal_stem: retire-foreman-grooming-and-supervisor-seats
content_digest: 289e31b717b7e02b1ecb5d42c939b9d99c148df7e67fbc66952db3cf820983ba
