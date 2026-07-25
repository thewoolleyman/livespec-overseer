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

The discovery clause ('Discovery keys on the DIRECTORY existing — it never reads, stats, or hashes any file inside a plan directory') gains one bounded allowance: for a track with a CURRENTLY MATCHING live session (the liveness gate), the daemon MAY perform an existence-only check of exactly one named artifact, plan/<topic>/supervisor-handoff.md. It MUST NOT open, read, or hash the file and MUST NOT depend on its content or mtime, and it MUST perform no probe at all for tracks without a live session. Because §"Non-interference with tracked work" is the clause the discovery paragraph cites as its authority, the same bounded existence-only exception is appended there too, so the cross-reference stays true and the section's umbrella 'NEVER touches files' first sentence is reconciled against its own enumerated prohibition ('opens, writes, or hashes', which does not bar an existence test); the append is anchored to that paragraph's FINAL sentence, which the non-interference-attended-skill-carveout proposal does not touch, so the two proposals stay independently ratifiable with no ordering dependency. A paired discovery scenario pins the behavior, per this repo's discipline of backing discovery behavior with scenarios (the omission the 2026-07-25 independent review flagged as a blocker). Split out of the non-interference-attended-skill-carveout proposal per that review's granularity advisory, so the already-shipped-skill carve-out and this not-yet-built-surface allowance ratify independently.

### Motivation

Adopted design: livespec core plan/plan-skill-supervisor-handoff/design.md section 11.4 (surfacing DECIDED by the maintainer 2026-07-23: liveness-gated nudge + attended write; the fourth truth-table cell DECIDED 2026-07-24: Surface A as capture offer, recorded on epic overseer-3wt) and the section 11.4 stat-allowance bound ('for a track with live-session evidence, the daemon MAY test existence of the single reserved supervision-artifact path, and MUST NOT open, read, or hash it'). The Surface A / Surface B implementation is ledger item overseer-6uobos, blocked on this ratification — spec text deliberately ratifies ahead of the implementing slice per design section 11.6 sequencing.

### Proposed Changes

THREE edits, anchors verified against origin/master at filing/repair time.

EDIT 1 (spec.md §"Track discovery and the mapping store"). The discovery paragraph currently reads: "Discovery keys on the DIRECTORY existing — it never reads, stats, or hashes any file inside a plan directory (per §\"Non-interference with tracked work\"); the conventional handoff path it derives is a pointer handed to sessions, never opened by the overseer." Append to that paragraph: "One bounded exception: for a track with a CURRENTLY MATCHING live session (the liveness gate), the daemon MAY test the EXISTENCE of exactly one named artifact, plan/<topic>/supervisor-handoff.md — no open, no read, no hash, no content or mtime dependence, and no probe of any kind for tracks without a live session. This is the ONLY file-level probe the discovery path may ever perform."

EDIT 2 (spec.md §"Non-interference with tracked work"). This reconciles the section that EDIT 1's discovery clause cites as its authority, so the cross-reference does not dangle. The daemon paragraph's FINAL sentence currently reads: "the restart interlock deliberately inspects nothing beyond the state-file token for the same reason." Replace that sentence with: "the restart interlock deliberately inspects nothing beyond the state-file token for the same reason. The one bounded exception, consistent with that enumeration — an existence test is not an open, write, or hash — is the supervision-artifact probe: for a track with a CURRENTLY MATCHING live session, the daemon MAY test whether the single reserved plan/<topic>/supervisor-handoff.md exists, never opening, reading, or hashing it, and it probes not at all for a track without a live session, exactly as §\"Track discovery and the mapping store\" permits." (Anchored to the paragraph's final sentence — a span the non-interference-attended-skill-carveout proposal's edits, EDIT 1 on the first sentence and EDIT 2 on the mid-paragraph "opens, writes, or hashes" clause, do not touch — so this edit is collision-free and order-independent with that proposal.)

EDIT 3 (scenarios.md). Add one scenario in the discovery group, after §"Scenario: An unassigned plan is discovered but never auto-started":

## Scenario: The supervision-artifact existence probe is liveness-gated and existence-only

Given a watched repository containing a plan directory whose track has a currently matching live session

When the daemon's discovery pass runs

Then it MAY test whether plan/<topic>/supervisor-handoff.md exists

And it never opens, reads, or hashes that file and never depends on its content or mtime

And for a track without a live matching session it performs no file-level probe at all

RATIFICATION CO-EDIT (required): EDIT 3 adds one `## ` heading to scenarios.md, so the revise resulting_files[] MUST co-edit tests/heading-coverage.json with the matching entry for the new scenario heading (spec_root SPECIFICATION, spec_file scenarios.md, TODO test pointer + reason), per this repo's heading-coverage discipline. EDITs 1 and 2 add, remove, or rename NO `## ` heading (both append or replace a sentence inside an existing paragraph), so they require no further heading-coverage co-edit.
