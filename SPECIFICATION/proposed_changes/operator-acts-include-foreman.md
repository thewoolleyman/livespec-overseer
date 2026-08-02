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

spec.md §"Surface-only startup" makes both the FIRST launch of a plan and the re-launch of a mapped-but-dead track "a deliberate operator act". The foreman is designed to be exactly such an operator, so this proposal widens "operator" in BOTH sentences to "the human, or an authorized operator surface acting under its own ratified contract" — while leaving the daemon's own prohibition fully intact and binding launches to a deterministic classification rule.

### Motivation

The foreman's Phase B (plan/foreman/, epic overseer-z5fo4y; brainstorm §4 v2) creates missing sessions for discovered plans, supervisor pairs, and qualifying work items. External review finding O7 found the plan amended only the first-launch wording while the SECOND sentence (no automatic recovery of dead sessions) is violated just as directly by an unattended re-creator; findings O15 and C3 pinned the classification discipline (never-started vs crashed vs ambiguous) that separates a safe unattended launch from the three dated failure modes recorded in the session-restart learnings.

### Proposed Changes

In spec.md §"Surface-only startup": (1) both occurrences of "a deliberate operator act" are widened to name the human OR an authorized operator surface (the foreman) acting under its own ratified contract; the DAEMON still MUST NOT auto-spawn a session for an unassigned plan and MUST NOT auto-recover dead sessions at startup — this amendment moves no authority into the daemon. (2) Add: an operator surface exercising this authority MUST route launches through the same deliberate-start semantics the operator CLI uses (absolute repository paths; exact-membership session-existence checks), and MUST first classify the target deterministically: a mapped-but-never-launched track MAY be started fresh; a crashed track whose runtime identity is established from exact live or indexed process evidence MUST be resumed as that runtime, never recreated as another; a target that is intentionally unassigned, ambiguous, or resolvable only by topic-name guessing MUST be reported to the human instead of launched — runtime identity is never inferred from a topic name. In scenarios.md, add one scenario: Given a mapped track whose session died and whose topic also names a stale same-topic entry in another runtime's index, When the operator surface classifies it, Then it refuses to launch, reports the ambiguity with both candidates' evidence, and no session is created. Co-edit tests/heading-coverage.json to link the new clauses.
