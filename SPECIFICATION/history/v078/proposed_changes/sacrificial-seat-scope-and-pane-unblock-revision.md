---
proposal: sacrificial-seat-scope-and-pane-unblock.md
decision: accept
revised_at: 2026-10-31T14:27:31Z
author_human: Chad Woolley <thewoolleyman@gmail.com>
author_llm: claude-opus-5-5 (herdr-overseer)
---

## Decision and Rationale

Accepted as filed on the maintainer's attended ruling of 2026-10-31 (~13:1xZ, in the gitops-fleet-capacity-monitoring coordinator chat; recorded on livespec-dev-tooling-dfixhe and quoted verbatim on overseer-wcsd and in the proposal's Motivation): the sacrificial-seat rule's intent was only to stop sessions spamming other panes' input fields, and a coordinator has a mandate to unblock a session stuck at a picker by typing into its pane. The three added bullets scope the existing live-proof rule (left byte-identical), state that mandate as a MUST with the follow-up message, and keep the input-field courtesy as a SHOULD NOT. Independent read-only Sonnet review returned NO BLOCKERS over the exact final bytes. The independent reviewer was a separate read-only Sonnet subagent spawned by herdr-overseer with no role in drafting; it re-attested NO BLOCKERS after the resulting-file path was made spec-relative (content unchanged).

## Resulting Changes

- non-functional-requirements.md

## Ratification Review

ratification_review: auto-spawn
reviewer_model: sonnet
reviewer_identity: sonnet
separate_reviewer: True
read_only: True
reviewed_at: 2026-10-31T14:26:40Z
verdict: NO BLOCKERS
proposal_stem: sacrificial-seat-scope-and-pane-unblock
content_digest: 308625c5e6c962ec42809e2b355c505ab89d02767768d1b83d33d5c0683d0e2a
