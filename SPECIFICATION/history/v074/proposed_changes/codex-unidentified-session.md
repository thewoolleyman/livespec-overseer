---
topic: codex-unidentified-session
author: claude-opus-5-5
created_at: 2026-10-26T15:34:07Z
---

## Proposal: A live carrier whose session cannot be identified is reported unidentified, never session-gone

### Target specification files

- SPECIFICATION/spec.md
- SPECIFICATION/contracts.md
- SPECIFICATION/scenarios.md

### Summary

Add to spec.md §"Supervised runtimes": a live agent carrier in a mapped track's pane whose session identity cannot be established from exact per-carrier evidence is reported with a distinct `unidentified-session` status, logged once per onset with the pane, carrier pid and refusing condition, and never acted on. Once exact evidence binds the carrier (a backend-reported per-carrier session id that the runtime's state database binds to the track's repository), the daemon adopts it and re-records the row's session identity and launch-profile harness from that live evidence, superseding a recorded identity of another runtime whose process is gone in that pane but never one whose process is still alive there. A row whose stored pane no longer exists on the live server generation is rebound only to the single pane whose identified carrier's thread name equals the derived session name and whose session the state database binds to the row's repository; zero or several leave the coordinate unchanged and the track unidentified. contracts.md §"Attention surface" gains the report-only membership; three scenarios pin it.

### Motivation

Measured 2026-10-25 and again 2026-10-26 on dispatch-control-plane (overseer-5eqavc, the rework of overseer-iffpgw): a hand-started Codex TUI that holds no rollout file open, beside a sibling Codex in the same repository behind one shared app-server, has no exact per-carrier evidence; and its mapping row still recorded a dead pane and a Claude identity from before the seat switched runtimes. The daemon reported session-gone, which is indistinguishable from a dead seat, and the track lost wrap-up coverage down to 15% context. §"Supervised runtimes" already forbids guessing identity and classifies dead-process ambiguity, but says nothing about a LIVE carrier that cannot be identified, nor how a row re-records identity across a runtime switch or rebinds a pane that no longer exists.

### Proposed Changes

Add to SPECIFICATION/spec.md §"Supervised runtimes", after the paragraph ending "an index MUST NOT override live evidence.", a paragraph stating: a live carrier of a supported runtime running in a mapped track's recorded pane, whose session identity cannot be established from exact per-carrier evidence, MUST be reported with a distinct `unidentified-session` status and MUST NOT be reported as session-gone; the daemon MUST log one event per onset naming the pane, the carrier process id and the refusing condition (ambiguous repository sessions, or no live candidate); an unidentified track is ambiguous evidence and receives no adoption, wrap-up, nudge or restart. Exact per-carrier evidence includes a session identifier the terminal backend reports for that pane's agent when the runtime's own state database binds that identifier to the track's repository. Once identified, the daemon adopts the session and re-records the mapping row's session identity and launch-profile harness from that live evidence; a recorded identity of another runtime whose process is gone in that pane yields to it, but a recorded session whose process is still alive in the pane keeps its identity. A row whose stored pane no longer exists on the live server generation MAY be rebound only to the single pane on that server whose identified carrier's thread name equals the row's derived session name and whose session the state database binds to the row's repository; zero or more than one such pane leaves the stored coordinate unchanged and the track unidentified-session, and every rebind logs the old and new pane identifiers. A done track or an unassigned plan never reads unidentified-session. In contracts.md §"Attention surface", add a report-only membership paragraph for an unidentified-session track (normal coordinates, NEEDS YOU and window badge, edge-triggered, authorizes no act, rendered note names pane, carrier pid and refusing condition; it is distinct from and never concurrent with session-gone or misnamed for the same track). Add three scenarios to scenarios.md, registered as spec-first coverage debt owned by overseer-5eqavc.
