---
topic: non-interference-attended-skill-carveout
author: claude-fable-5 (cutover-and-shipping planning session; repaired and split 2026-07-25 per independent review by the plan-skill-supervisor-handoff session)
created_at: 2026-07-24T00:02:05Z
---

## Proposal: Scope non-interference to the daemon's unattended loop; permit one attended, reviewed artifact

### Target specification files

- spec.md
- constraints.md

### Summary

The 'Non-interference with tracked work' section currently binds THE OVERSEER as a whole ('The overseer NEVER touches files under any repository's plan tree'). Scope the prohibition to the DAEMON's unattended observation/restart loop, and permit an ATTENDED operator skill (supervise-plan) to create exactly one named artifact, plan/<topic>/supervisor-handoff.md, writing only through the target repository's own documented commit discipline (worktree, PR, review, merge). Authored artifacts are distinct from runtime state: the two-places sentence for the overseer's own runtime state survives unchanged, as does the startup gitignore refusal. The same scoping is applied to constraints.md §"Filesystem boundaries", which independently restates the absolute rule ('It NEVER reads, writes, or hashes files under any repository's plan tree'; 'writes to exactly two places') and would otherwise be left contradicting the carve-out — the drift target the 2026-07-25 independent review caught.

### Motivation

Adopted design: livespec core plan/plan-skill-supervisor-handoff design.md section 11 (maintainer-adopted 2026-07-23, livespec PR #1695), specifically section 11.2: the clause's protected property is 'supervision can never dirty a tracked working tree', an attended reviewed PR write preserves that property literally, and the correct amendment SCOPES the prohibition to the unattended loop rather than punching a hole in it. The supervise-plan skill has since SHIPPED (this repo's PR #49, work-item overseer-myjovi accepted done with live-exercise evidence: livespec PR #1706) and the upstream admissions are RATIFIED (livespec core v175; livespec-orchestrator-beads-fabro v048), so this repo's own spec is now the only surface still forbidding what the fleet's ratified contracts admit. This file originally bundled the slice-3a existence-probe allowance as a second proposal section; per the 2026-07-25 independent review's granularity advisory it now carries slice 2 alone, and the allowance lives in its own proposal file (supervision-existence-probe-allowance).

### Proposed Changes

Three edits to spec.md §"Non-interference with tracked work" and one to constraints.md §"Filesystem boundaries". Anchors verified verbatim against origin/master at repair time.

EDIT 1 (spec.md, first sentence). Replace: "The overseer NEVER touches files under any repository's plan tree." with: "The overseer's DAEMON — the unattended observation and restart loop — NEVER touches files under any repository's plan tree." (Unchanged in force for the daemon.)

EDIT 2 (spec.md, second sentence — the review's precision note: this sentence also binds the whole overseer). In the same paragraph, replace: "but it never opens, writes, or hashes those files" with: "but the daemon never opens, writes, or hashes those files".

EDIT 3 (spec.md, new paragraph after that paragraph): "An ATTENDED Control-Plane operator skill (supervise-plan) MAY create exactly ONE named artifact, plan/<topic>/supervisor-handoff.md, in a watched repository, and MUST write it exclusively through that repository's own documented commit discipline — worktree, then pull request, then review, then merge — never directly to a primary checkout. An authored artifact is NOT overseer runtime state: the 'exactly two places' sentence below and the startup gitignore refusal continue to bind the daemon's runtime state verbatim."

EDIT 4 (constraints.md §"Filesystem boundaries"). Replace: "The overseer writes to exactly two places: its operator-home stores and the per-track scratch directory `<repo>/tmp/overseer/<topic>/` inside each watched repository. It NEVER reads, writes, or hashes files under any repository's plan tree," with: "The overseer's daemon writes its runtime state to exactly two places: its operator-home stores and the per-track scratch directory `<repo>/tmp/overseer/<topic>/` inside each watched repository. The daemon NEVER reads, writes, or hashes files under any repository's plan tree," and append, after the sentence ending "fails to gitignore the scratch path.": "The one attended exception is Control-Plane authored, not daemon-written: the supervise-plan operator skill MAY create plan/<topic>/supervisor-handoff.md in a watched repository, writing only through that repository's own reviewed commit discipline (worktree, pull request, review, merge), never directly to a primary checkout — an authored artifact, not overseer runtime state."

No `## ` heading is added, removed, or renamed in either file, so no tests/heading-coverage.json co-edit is required. No new daemon behavior is introduced (the attended skill's behavior is specified by its own shipped prose); the existence-probe allowance and its discovery scenario are the separate supervision-existence-probe-allowance proposal.
