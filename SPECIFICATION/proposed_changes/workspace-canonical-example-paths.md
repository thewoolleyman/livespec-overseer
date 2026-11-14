---
topic: workspace-canonical-example-paths
author: claude-opus-5-5
created_at: 2026-11-14T00:34:17Z
---

## Proposal: Name example repositories under ~/workspace in the onboarding-trust scenarios

### Target specification files

- SPECIFICATION/scenarios.md

### Summary

The workspace-trust and onboarding scenarios use `/data/projects/example` and `/data/projects/other` as the tracked pane's recorded repository. Use `~/workspace/example` and `~/workspace/other`, the canonical clone root, so the scenarios do not embed one host's data-disk path.

### Motivation

Maintainer ruling, 2026-11-14 (verbatim): "Fix this on all repos, everything should refer to $HOME/workspace as the place canonical project clones live, never in /data/projects, even if that's the rreal one workspace should always be syumlinked. Fix this across all livespec tenants." The scenarios' behaviour (accepting the trust prompt only for the recorded repository, reporting blocked-onboarding for any other path, preserving recorded trust) is unchanged; only the example paths change.

### Proposed Changes

In `SPECIFICATION/scenarios.md`, in the Claude Code workspace-trust and onboarding scenarios, replace every `/data/projects/example` with `~/workspace/example` and every `/data/projects/other` with `~/workspace/other` (seven occurrences). No step, assertion or scenario name changes otherwise.
