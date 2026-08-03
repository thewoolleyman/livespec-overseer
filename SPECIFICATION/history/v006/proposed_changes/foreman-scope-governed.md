---
topic: foreman-scope-governed
author: claude-fable-5
created_at: 2026-08-02T06:48:49Z
---

## Proposal: The foreman is inside the governed contract — resolving the scope-statement fork

### Target specification files

- SPECIFICATION/spec.md

### Summary

spec.md's scope statement governs the supervision contract and deliberately excludes the interactive pane's operator-cockpit surface. The foreman forks that line: it is an operator surface, but unlike the cockpit it ACTS autonomously — it launches sessions, drives an acting executable, and will later answer blocked questions. This proposal resolves the fork by declaring the foreman's CONTRACT surface governed (its naming contract, its snapshot consumption rules, its act bounds, its state home) while leaving its presentation — like the cockpit's — free to evolve.

### Motivation

External review finding O7 (plan/foreman/research/review-findings.md) exposed the fork: "Either the foreman is out of scope (and an ACTING autonomous agent then has no ratified bounds at all), or the scope statement itself must be amended. The plan does not notice the fork." An autonomous actor with no ratified bounds would also contradict the repo's own lesson that prose-only bounds do not bind conduct (supervisor-protocol C20) — bounds must be ratified so their mechanical gates have a contract to enforce.

### Proposed Changes

EDIT 1 — spec.md, the scope paragraph, after the sentence excluding the pane's track table, columns, and command vocabulary: the FOREMAN — the per-repository autonomous operator surface — is governed by this specification in its CONTRACT surface: its reserved session-name contract (the repo-slug-foreman tmux and runtime-registry names and the reserved-suffix refusals), its consumption of the status snapshot (observation-only, fail-closed on unknown schema), its authority boundaries (the deliberate-operator launch classification, the read-only plan-tree carve-out, and the prohibition on writing any track's state file), and its state home under the gitignored scratch.

EDIT 2 — spec.md, same addition, the standing autonomous-action bound (self-contained, so it depends on no unratified artifact): until a consensus-decision policy is ratified in this tree, the foreman MUST NOT resolve, approve, accept, or reject any work-item valve and MUST NOT answer a blocked question on a session's behalf — it reports such decisions to the human with coordinates and takes no act on them.

EDIT 3 — spec.md, same addition, the presentation exclusion: the foreman's PRESENTATION — how it renders its attention view, its tick cadence, its report formats — is deliberately outside the governed contract, exactly as the cockpit's rendering is; it MAY evolve freely so long as every governed guarantee holds. Guarantees the foreman's contract surface relies on MUST be stated in this tree before an implementation that depends on them lands.

Composition: the other five foreman proposals (status-snapshot-store, attention-ownership-superset, operator-acts-include-foreman, unattended-reader-carve-out, reserved-suffix-refusal) supply the clauses this scope entry points at — accept this one together with whichever of them are accepted, and reconcile the enumeration in EDIT 1 to name only the accepted ones.
