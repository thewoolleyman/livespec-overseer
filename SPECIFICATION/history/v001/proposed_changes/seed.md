---
topic: seed
author: livespec-seed
---

## Proposal: seed

### Target specification files

- SPECIFICATION/spec.md
- SPECIFICATION/contracts.md
- SPECIFICATION/constraints.md
- SPECIFICATION/non-functional-requirements.md
- SPECIFICATION/scenarios.md
- SPECIFICATION/README.md

### Summary

Initial seed of the specification from user-provided intent.

### Motivation

livespec-overseer is the Control-Plane operator tool that keeps long-running agent sessions productive across context exhaustion. It watches every tracked session's remaining context headroom, injects an escalating wrap-up prompt as a session approaches its limit, and atomically restarts that session ONLY once the session has declared itself ready on the filesystem — so no work is lost to a mid-flight restart.

It is a two-part system: a headless `overseerd` daemon that polls session state and drives the marker-file handshake, and a thin interactive tmux pane that renders every tracked track for an operator.

The specification governs the SUPERVISION CONTRACT — the marker protocol between overseer and supervised session, the watch-set declaration, session-name derivation, and the atomicity and fail-soft rules — not the internal composition of the Python package.

### Proposed Changes

livespec-overseer is the Control-Plane operator tool that keeps long-running agent sessions productive across context exhaustion. It watches every tracked session's remaining context headroom, injects an escalating wrap-up prompt as a session approaches its limit, and atomically restarts that session ONLY once the session has declared itself ready on the filesystem — so no work is lost to a mid-flight restart.

It is a two-part system: a headless `overseerd` daemon that polls session state and drives the marker-file handshake, and a thin interactive tmux pane that renders every tracked track for an operator.

The specification governs the SUPERVISION CONTRACT — the marker protocol between overseer and supervised session, the watch-set declaration, session-name derivation, and the atomicity and fail-soft rules — not the internal composition of the Python package.
