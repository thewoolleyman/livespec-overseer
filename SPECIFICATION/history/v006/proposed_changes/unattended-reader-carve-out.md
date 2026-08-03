---
topic: unattended-reader-carve-out
author: claude-fable-5
created_at: 2026-08-02T06:48:48Z
---

## Proposal: A bounded read-only carve-out for an unattended operator surface, and the foreman's scratch home

### Target specification files

- SPECIFICATION/spec.md
- SPECIFICATION/constraints.md
- SPECIFICATION/scenarios.md

### Summary

spec.md §"Non-interference with tracked work" binds the unattended DAEMON to never touch plan-tree files and grants an ATTENDED skill (supervise-plan) a single authored-artifact carve-out. The foreman is a third shape the section does not admit: an UNATTENDED operator surface that must READ plan files (a handoff, for a consensus dossier) but never write them. This proposal adds that bounded read-only carve-out, names the foreman's state home inside the gitignore-gated scratch, and co-edits constraints.md §"Filesystem boundaries" — which restates both amended rules — so the tree stays internally consistent.

### Motivation

External review finding O7 (plan/foreman/research/review-findings.md): the foreman "sits in the gap the spec words shut" — it is neither the daemon (whose prohibition covers reads for authorization) nor an attended skill (the supervise-plan carve-out is explicitly ATTENDED). Finding O18 relocated foreman state under tmp/overseer/foreman/ so it inherits the startup gitignore refusal instead of needing a new gate. Finding O11 supplies the trust rule: what is read is evidence, never instruction.

### Proposed Changes

EDIT 1 — spec.md §"Non-interference with tracked work", after the attended-skill carve-out: an authorized UNATTENDED operator surface (the foreman) MAY READ files under a watched repository's plan tree — and MAY read pane content and work-item records — solely as EVIDENCE for its own decision-routing. It MUST NOT write, delete, or hash-as-authorization anything under plan/, MUST NOT write any tracked file outside the repository's reviewed commit discipline, and MUST NOT treat any session-authored or peer-authored text it reads as an instruction to itself. The DAEMON's own posture is unchanged by this carve-out.

EDIT 2 — spec.md, the overseer-state "exactly two places" sentence: an operator surface's runtime state MUST live under the same per-repository gitignored scratch area, in its own subdirectory (`tmp/overseer/foreman/`), so the existing startup gitignore refusal covers it with no new gate; an operator surface MUST NOT create any new scratch root.

EDIT 3 — spec.md, state-file authorship: a session's one state file remains writable ONLY by that session and the daemon's single self-token — the foreman MUST NOT write any value into any track's state file.

EDIT 4 — constraints.md §"Filesystem boundaries" (which restates both amended rules and would otherwise contradict them): the "one attended exception" sentence widens to enumerate BOTH carve-outs — the attended authored artifact and the unattended READ-ONLY evidence carve-out above; and the per-track scratch phrasing ("the per-track scratch directory `<repo>/tmp/overseer/<topic>/`") widens to admit the operator-surface subdirectory `tmp/overseer/foreman/` beside the per-track directories, all inside the same gitignore-gated root.

EDIT 5 — scenarios.md, one new scenario: Given a foreman holding a consensus dossier for a blocked track, When it acts on the panel's verdict, Then no value has been written to any track's `.overseer-state` by the foreman, and any unblocking answer reaches the session only through its own pane or through the ledger.

EDIT 6 — tests/heading-coverage.json (outside the spec target; the atomic behavior-coverage co-edit): link the new clauses to the scenario.

Composition: accept together with foreman-scope-governed (which defines the foreman) and before or with attention-ownership-superset (whose heartbeat lives in the scratch home EDIT 2 admits).
