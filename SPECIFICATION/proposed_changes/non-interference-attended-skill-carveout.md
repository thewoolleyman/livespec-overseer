---
topic: non-interference-attended-skill-carveout
author: claude-fable-5 (cutover-and-shipping planning session)
created_at: 2026-07-24T00:02:05Z
---

## Proposal: Scope non-interference to the daemon's unattended loop; permit one attended, reviewed artifact

### Target specification files

- spec.md

### Summary

The 'Non-interference with tracked work' section currently binds THE OVERSEER as a whole ('The overseer NEVER touches files under any repository's plan tree'). Scope the prohibition to the DAEMON's unattended observation/restart loop, and permit an ATTENDED operator skill (supervise-plan) to create exactly one named artifact, plan/<topic>/supervisor-handoff.md, writing only through the target repository's own documented commit discipline (worktree, PR, review, merge). Authored artifacts are distinct from runtime state: the two-places sentence for the overseer's own runtime state survives unchanged, as does the startup gitignore refusal.

### Motivation

Adopted design: livespec core plan/plan-skill-supervisor-handoff design.md section 11 (maintainer-adopted 2026-07-23, livespec PR #1695). The clause's protected property is 'supervision can never dirty a tracked working tree'. An attended, reviewed PR write preserves that property literally; the unattended tick loop remains fully prohibited. Without this scoping, the repo's own spec forbids the supervise-plan slice the maintainer has cut (ledger: overseer-myjovi under epic overseer-3wt).

### Proposed Changes

In spec.md section 'Non-interference with tracked work': (1) reword the opening sentence to bind the DAEMON's unattended observation/restart loop (never opens, writes, or hashes plan-tree files — unchanged in force); (2) add one paragraph: an attended Control-Plane operator skill (supervise-plan) MAY create exactly ONE named artifact, plan/<topic>/supervisor-handoff.md, in a watched repository, and MUST write it exclusively through that repository's own documented commit discipline (worktree -> PR -> review -> merge), never directly to a primary checkout; (3) state explicitly that authored artifacts are distinct from the overseer's runtime state, so the existing 'exactly two places' sentence and the startup gitignore refusal continue to hold verbatim.

## Proposal: Narrow existence-only discovery allowance for the supervision surfaces

### Target specification files

- spec.md

### Summary

The discovery clause ('keys on the DIRECTORY existing - it never reads, stats, or hashes any file inside a plan directory') gains one bounded allowance: for a track that has a CURRENTLY MATCHING live session (the liveness gate), the daemon MAY perform an existence-only check of exactly one named artifact, plan/<topic>/supervisor-handoff.md. It never opens, reads, hashes, or depends on the content or mtime of that file, and performs no check at all for tracks without a live session.

### Motivation

The adopted supervision surfaces (design.md section 11.4: Surface A 'no supervision prompt' / Surface B 'nobody supervising', liveness-gated, edge-triggered, precedence below NEEDS-YOU) require knowing whether the artifact exists. An existence probe writes nothing and couples to no content, so the non-interference property is preserved; bounding it to liveness-gated tracks and one named filename prevents scope creep. Implementation is ledger item overseer-6uobos, blocked on this ratification.

### Proposed Changes

In spec.md, amend the discovery clause (the 'never reads, stats, or hashes any file inside a plan directory' sentence) with the single bounded exception: for tracks passing the liveness gate the daemon MAY test the EXISTENCE of plan/<topic>/supervisor-handoff.md only - no open, no read, no hash, no content or mtime dependence, no probe for sessionless tracks. State that this is the ONLY file-level probe the discovery path may ever perform.
