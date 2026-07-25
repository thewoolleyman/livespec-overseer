---
topic: supervision-existence-probe-allowance
author: claude-fable-5
created_at: 2026-07-25T01:05:18Z
---

## Proposal: Narrow existence-only discovery allowance for the supervision surfaces

### Target specification files

- SPECIFICATION/spec.md
- SPECIFICATION/scenarios.md

### Summary

The discovery clause ('Discovery keys on the DIRECTORY existing — it never reads, stats, or hashes any file inside a plan directory') gains one bounded allowance: for a track with a CURRENTLY MATCHING live session (the liveness gate), the daemon MAY perform an existence-only check of exactly one named artifact, plan/<topic>/supervisor-handoff.md. It MUST NOT open, read, or hash the file and MUST NOT depend on its content or mtime, and it MUST perform no probe at all for tracks without a live session. A paired discovery scenario pins the behavior, per this repo's discipline of backing discovery behavior with scenarios (the omission the 2026-07-25 independent review flagged as a blocker). Split out of the non-interference-attended-skill-carveout proposal per that review's granularity advisory, so the already-shipped-skill carve-out and this not-yet-built-surface allowance ratify independently.

### Motivation

Adopted design: livespec core plan/plan-skill-supervisor-handoff/design.md section 11.4 (surfacing DECIDED by the maintainer 2026-07-23: liveness-gated nudge + attended write; the fourth truth-table cell DECIDED 2026-07-24: Surface A as capture offer, recorded on epic overseer-3wt) and the section 11.4 stat-allowance bound ('for a track with live-session evidence, the daemon MAY test existence of the single reserved supervision-artifact path, and MUST NOT open, read, or hash it'). The Surface A / Surface B implementation is ledger item overseer-6uobos, blocked on this ratification — spec text deliberately ratifies ahead of the implementing slice per design section 11.6 sequencing.

### Proposed Changes

TWO edits, anchors verified against origin/master at filing time.

EDIT 1 (spec.md §"Track discovery and the mapping store"). The discovery paragraph currently reads: "Discovery keys on the DIRECTORY existing — it never reads, stats, or hashes any file inside a plan directory (per §\"Non-interference with tracked work\"); the conventional handoff path it derives is a pointer handed to sessions, never opened by the overseer." Append to that paragraph: "One bounded exception: for a track with a CURRENTLY MATCHING live session (the liveness gate), the daemon MAY test the EXISTENCE of exactly one named artifact, plan/<topic>/supervisor-handoff.md — no open, no read, no hash, no content or mtime dependence, and no probe of any kind for tracks without a live session. This is the ONLY file-level probe the discovery path may ever perform."

EDIT 2 (scenarios.md). Add one scenario in the discovery group, after §"Scenario: An unassigned plan is discovered but never auto-started":

## Scenario: The supervision-artifact existence probe is liveness-gated and existence-only

Given a watched repository containing a plan directory whose track has a currently matching live session

When the daemon's discovery pass runs

Then it MAY test whether plan/<topic>/supervisor-handoff.md exists

And it never opens, reads, or hashes that file and never depends on its content or mtime

And for a track without a live matching session it performs no file-level probe at all

RATIFICATION CO-EDIT (required): EDIT 2 adds one `## ` heading to scenarios.md, so the revise resulting_files[] MUST co-edit tests/heading-coverage.json with the matching entry for the new scenario heading (spec_root SPECIFICATION, spec_file scenarios.md, TODO test pointer + reason), per this repo's heading-coverage discipline.
