---
proposal: remote-control-reissue-herdr-panes.md
decision: accept
revised_at: 2026-11-13T18:39:59Z
author_human: Chad Woolley <thewoolleyman@gmail.com>
author_llm: claude-opus-5-5
---

## Decision and Rationale

Plan central-credential-service (epic overseer-iyfjbo), work item overseer-fdwat6. Measured 2026-11-13: the role holder and every listed host run a herdr server and no tmux, so the clause as ratified through v102 reached no session anywhere. The proposal widens only the pane backend, to the host's terminal multiplexer, herdr (every running herdr session) or tmux. That covers enumeration, visible-text capture with wrapped lines joined, foreground-executable identification, a not-in-a-mode guard and sending /remote-control plus Enter through the pane's multiplexer. It restates the real-capture fixture requirement as a capture read the way the service reads that pane's multiplexer. Every other rule is kept verbatim, and spec.md is multiplexer-neutral and unchanged. No design record is contradicted. Revise decision taken under coordinator R301 delegation (legacy-coordinator-agent), revise_decision_mode delegated: ACCEPT verbatim.

## Resulting Changes

- contracts.md
- scenarios.md

## Ratification Review

ratification_review: auto-spawn
reviewer_model: sonnet
reviewer_identity: sonnet
separate_reviewer: True
read_only: True
reviewed_at: 2026-11-13T18:39:54Z
verdict: NO BLOCKERS
proposal_stem: remote-control-reissue-herdr-panes
content_digest: f46e68a53b918c9d96b1547b415eae8ae3ac7f79b735d2302456ba284359f5fd
