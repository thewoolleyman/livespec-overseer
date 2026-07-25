---
proposal: non-interference-attended-skill-carveout.md
decision: accept
revised_at: 2026-07-25T06:08:20Z
author_human: thewoolleyman <chad@thewoolleyman.com>
author_llm: claude-opus-5[1m]
---

## Decision and Rationale

Accepted as filed. The proposal scopes the non-interference prohibition to the daemon's unattended observation/restart loop rather than punching a hole in it, which preserves the clause's protected property verbatim — supervision can never dirty a tracked working tree — because the attended supervise-plan write goes through the target repository's own worktree/PR/review/merge discipline. This is exactly the resolution the cited design record (livespec core plan/plan-skill-supervisor-handoff/design.md section 11.2, maintainer-adopted 2026-07-23) prescribes, so no design-record departure is involved and no acknowledgment is owed under §"Intent preservation and design-record authority". The skill has already SHIPPED (PR #49, overseer-myjovi accepted with live-exercise evidence) and the upstream admissions are ratified (livespec core v175, livespec-orchestrator-beads-fabro v048), leaving this repo's spec as the last surface forbidding what the fleet's ratified contracts admit. The constraints.md co-edit is load-bearing, not optional: §"Filesystem boundaries" independently restates the absolute rule and would otherwise be left contradicting the carve-out. All four anchors were re-verified verbatim against the working tree before assembly. No `## ` heading is added, removed, or renamed, so no heading-coverage co-edit is owed by this decision.

## Resulting Changes

- spec.md
- constraints.md
