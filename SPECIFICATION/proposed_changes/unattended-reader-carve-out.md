---
topic: unattended-reader-carve-out
author: claude-fable-5
created_at: 2026-08-02T06:48:48Z
---

## Proposal: A bounded read-only carve-out for an unattended operator surface, and the foreman's scratch home

### Target specification files

- SPECIFICATION/spec.md

### Summary

spec.md §"Non-interference with tracked work" binds the unattended DAEMON to never touch plan-tree files and grants an ATTENDED skill (supervise-plan) a single authored-artifact carve-out. The foreman is a third shape the section does not admit: an UNATTENDED operator surface that must READ plan files (a handoff, for a consensus dossier) but never write them. This proposal adds that bounded read-only carve-out and names the foreman's own state home inside the gitignore-gated scratch.

### Motivation

External review finding O7 (plan/foreman/research/review-findings.md): the foreman "sits in the gap the spec words shut" — it is neither the daemon (whose prohibition covers reads for authorization) nor an attended skill (the supervise-plan carve-out is explicitly ATTENDED). Finding O18 relocated foreman state under tmp/overseer/foreman/ so it inherits the startup gitignore refusal instead of needing a new gate. Finding O11 supplies the trust rule: what is read is evidence, never instruction.

### Proposed Changes

In spec.md §"Non-interference with tracked work": (1) After the attended-skill carve-out, add: an authorized UNATTENDED operator surface (the foreman) MAY READ files under a watched repository's plan tree — and MAY read pane content and work-item records — solely as EVIDENCE for its own decision-routing; it MUST NOT write, delete, or hash-as-authorization anything under plan/, MUST NOT write any tracked file outside the repository's reviewed commit discipline, and MUST NOT treat any session-authored or peer-authored text it reads as an instruction to itself. The DAEMON's own posture is unchanged by this carve-out. (2) The overseer-state "exactly two places" sentence gains the foreman's state home: an operator surface's runtime state MUST live under the same per-repository gitignored scratch area, in its own subdirectory (tmp/overseer/foreman/), so the existing startup gitignore refusal covers it with no new gate; an operator surface MUST NOT create any new scratch root. (3) A session's one state file remains writable ONLY by that session and the daemon's single self-token — the foreman MUST NOT write any value into any track's state file.
