---
proposal: llm-provider-manager-credential-provider.md
decision: modify
revised_at: 2026-09-12T00:07:26Z
author_human: Chad Woolley <thewoolleyman@gmail.com>
author_llm: gpt-5.6-sol
---

## Decision and Rationale

Ratify a fourth operator operation, `llm-provider-manager`, as the provider-agnostic credential authority while preserving the existing three operations during rollout. The manager provisions credentials directly into consumer-owned targets rather than proxying provider requests, and `caam-anthropic-loop` remains installed, runnable and responsible for interactive Anthropic rotation until the manager's recorded coexistence proof reports deprecation readiness. This realizes the proposal's boundary while making its lifecycle, persistence, privilege separation, recovery and observable consumer behavior precise enough for implementation and conformance testing.

## Modifications

Defined a closed provider/kind/purpose registry, purpose reservations and health strategies; exact configuration keys, defaults and cross-field bounds; immutable credential identity; append-only audit preservation; fail-closed malformed-record behavior; deterministic consume-first and spread selection; bounded validation and cache behavior; account leases; and authoritative recovery. Authentication failures move credentials to `suspect`; explicit `acquire` may reacquire a persistently suspect identity under the same record id, while successful revalidation is the only ordinary return to `valid`. Acquisition, reacquisition and revalidation use durable operation and worker records, bounded deadlines, fenced recovery and manager-owned browser-verification attention.

Defined privilege-separated research, execution, acquisition-store and provisionable-store roles; system-keyring and 1Password backends bound to the local machine namespace; and secret-free metadata descriptors, diagnostics, outputs, target references and proof evidence. Defined exact Claude, Codex and namespaced Pi bindings plus Pi package discovery, with one harness-neutral implementation and lockstep operation availability. Defined operator `acquire` and `attention` behavior and the versioned consumer protocol (`target`, `provision`, `report`, `complete`, `release`, `proof-status`), including exact JSON shapes, outputs, exit codes, built-in `isolated-run` provisioning and owner-only run registration.

Defined atomic durable writes, authoritative cache-bypassing rereads, write-ahead operations, tri-state target commit, prepared-assignment recovery, durable consumer commit evidence, retry and idempotency rules, late-report generation matching, and assignment, lease and tombstone handling. Closed assignment tombstones and their target bindings are retained indefinitely so late reports and completions remain decidable. Store and audit failures are typed and fail closed without exposing credential material.

Departed from the proposal's permission for non-authentication reports to feed a generic signal strategy: reports do not synthesize or modify the provider health adapter's independently read remainder, and `unknown` releases its matching lease without changing lifecycle state. Relocated the contributor-facing thin-binding mechanics for both `caam-anthropic-loop` and `llm-provider-manager` from the operator contract into normative non-functional requirements, while retaining the observable one-binding-per-supported-harness and manifest-lockstep obligations in contracts.md.

Defined the timestamped coexistence proof record, including simultaneous spread, production success, legacy-pool absence, consecutive REAL CONSUMER DAY soak evidence, out-of-order completion handling, monotonic authentication-failure evidence and same-day soak restart. Added the complete operator scenarios and heading-coverage ownership needed to exercise these behaviors, clarified the shipped-operation and harness boundaries, and updated the overview, constraints and non-functional requirements accordingly.

Ratification intentionally precedes implementation: the current three-operation code and tests are expected to differ until the already-filed plan children realize the new operation and update the pinned shipped surface. That expected spec-to-implementation gap is not a contradictory implementation constraint and does not enlarge this revision's scope.

## Resulting Changes

- spec.md
- contracts.md
- scenarios.md
- README.md
- constraints.md
- non-functional-requirements.md

## Ratification Review

ratification_review: auto-spawn
reviewer_model: opus
reviewer_identity: opus
separate_reviewer: True
read_only: True
reviewed_at: 2026-09-12T00:07:19Z
verdict: NO BLOCKERS
proposal_stem: llm-provider-manager-credential-provider
content_digest: f853156619ed3c6177b65ca62327a023f3793a2270f0fb3ecf2657f7d9a10257
