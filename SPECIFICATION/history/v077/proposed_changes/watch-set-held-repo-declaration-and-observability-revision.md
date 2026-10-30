---
proposal: watch-set-held-repo-declaration-and-observability.md
decision: modify
revised_at: 2026-10-30T21:03:48Z
author_human: Chad Woolley <thewoolleyman@gmail.com>
author_llm: claude-opus-5-5
---

## Decision and Rationale

Modify. Gives the watch-set declaration a first-class HELD state (declared, unwatched, observable, age surfaced), matching every property design record overseer-zidpiu.5 states. Non-drift (a new capability, not impl-to-spec drift), so the delegated mode applies. Modified only to reconcile the proposal with the live spec: the contracts.md targets are bullets inside Durable stores; the spec conflict clause is reconciled with the proposal's own contracts rule that a doubly-declared repo is not admitted; the conflict gets a wire home on the snapshot; held is distinguished from absence. Independent read-only Sonnet reviewer (agent a6ecef2270d67a7d1) returned NO BLOCKERS on these exact bytes.

## Modifications

(a) The proposal's contracts.md targets §"The watch-set declaration" and §"The status snapshot" are bullets inside contracts.md §"Durable stores"; the amendments are made to those two bullets. (b) spec.md's conflict clause no longer says 'rather than silently resolved toward either reading', which contradicted the proposal's own contracts clause that a repository named in both is not admitted; it now says the conflict is surfaced rather than silently resolved, and while it stands the repository is not admitted, per contracts.md. (c) The snapshot bullet marks a held repository that is also named in repos as a declared/effective conflict, giving the spec's surfaced conflict a wire home. (d) Held must be distinguishable from a repository absent from the declaration, whether never watched or removed; the two absent cases need not be told apart. (e) Only a VALID holds element excludes a repository; an inert malformed element excludes nothing. (f) Scenario 3 adds that the repository is not admitted; scenario 4 adds the passed review-by case; scenario 2 names the status snapshot as the surface. Four spec-first TODO coverage rows and debt-register rows owned by overseer-zidpiu.5.

## Resulting Changes

- spec.md
- contracts.md
- scenarios.md
- ../tests/heading-coverage.json
- ../tests/heading-coverage-debt.json

## Ratification Review

ratification_review: auto-spawn
reviewer_model: sonnet
reviewer_identity: sonnet
separate_reviewer: True
read_only: True
reviewed_at: 2026-10-30T21:03:30Z
verdict: NO BLOCKERS
proposal_stem: watch-set-held-repo-declaration-and-observability
content_digest: 3d5fd3686268730dbabf4185674d7526f24093cabb7e37f1859bb04dc5d55681
