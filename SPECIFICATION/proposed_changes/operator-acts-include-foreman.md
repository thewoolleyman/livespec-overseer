---
topic: operator-acts-include-foreman
author: claude-fable-5
created_at: 2026-08-02T06:48:47Z
---

## Proposal: Deliberate operator acts include an authorized operator surface — both surface-only sentences

### Target specification files

- SPECIFICATION/spec.md
- SPECIFICATION/scenarios.md

### Summary

spec.md §"Surface-only startup" makes both the FIRST launch of a plan and the re-launch of a mapped-but-dead track "a deliberate operator act". The foreman is designed to be exactly such an operator, so this proposal widens "operator" in BOTH sentences to "the human, or an authorized operator surface acting under its own ratified contract" — while leaving the daemon's own prohibition fully intact, binding launches to a deterministic classification rule, and explicitly widening §"Supervised runtimes"' evidence rule to cover a dead process whose runtime left a persisted session index.

### Motivation

The foreman's Phase B (plan/foreman/, epic overseer-z5fo4y; brainstorm §4 v2) creates missing sessions for discovered plans, supervisor pairs, and qualifying work items. External review finding O7 found the plan amended only the first-launch wording while the SECOND sentence (no automatic recovery of dead sessions) is violated just as directly by an unattended re-creator; findings O15 and C3 pinned the classification discipline (never-started vs crashed vs ambiguous) that separates a safe unattended launch from the three dated failure modes recorded in the session-restart learnings.

### Proposed Changes

EDIT 1 — spec.md §"Surface-only startup": both occurrences of "a deliberate operator act" are widened to name the human OR an authorized operator surface (the foreman) acting under its own ratified contract. The DAEMON still MUST NOT auto-spawn a session for an unassigned plan and MUST NOT auto-recover dead sessions at startup — this amendment moves no authority into the daemon.

EDIT 2 — spec.md, same section, the launch discipline: an operator surface exercising this authority MUST use absolute repository paths and exact-membership session-existence checks (never prefix-matching), and MUST first classify the target deterministically: a mapped-but-never-launched track MAY be started fresh; a crashed track whose runtime identity is established from runtime-identity evidence (EDIT 3) MUST be resumed as that runtime, never recreated as another; a target that is intentionally unassigned, ambiguous between candidate runtimes, or resolvable only by topic-name guessing MUST be reported to the human instead of launched — runtime identity is never inferred from a topic name.

EDIT 3 — spec.md §"Supervised runtimes", the evidence rule: "Runtime identity is established from exact live process evidence" widens to admit, for a DEAD process only, the runtime's own persisted session index — a record the runtime itself maintains that maps its session identifiers to their session names (the Codex session index is the existing instance) — read as recorded evidence and cross-checked for staleness against same-topic candidates in other runtimes' records. A live process's identity is still established from live process evidence alone; an index entry MUST NOT override live evidence, and an index whose entry is a stale namesake (an older same-name session than another runtime's candidate) is AMBIGUOUS, not authoritative.

EDIT 4 — scenarios.md, one new scenario: Given a mapped track whose session died and whose topic also names a stale same-topic entry in another runtime's persisted session index, When the operator surface classifies it, Then it refuses to launch, reports the ambiguity with both candidates' evidence, and no session is created.

EDIT 5 — tests/heading-coverage.json (outside the spec target; the atomic behavior-coverage co-edit): link the new clauses to the scenario.

Composition: accept together with foreman-scope-governed, which defines the foreman this proposal names as an authorized operator surface.
