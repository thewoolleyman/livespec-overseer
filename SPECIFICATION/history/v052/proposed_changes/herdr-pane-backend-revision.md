---
proposal: herdr-pane-backend.md
decision: modify
revised_at: 2026-10-04T00:21:57Z
author_human: Chad Woolley <thewoolleyman@gmail.com>
author_llm: gpt-6
---

## Decision and Rationale

The maintainer explicitly requests herdr alongside tmux and autonomous completion. This deliberately supersedes the tmux-only Runtime requirements decision and the single-native-operation restart requirement for herdr alone: measured herdr 0.9.3 has no atomic respawn. The replacement is therefore explicitly guarded, durable, and fail closed, never mislabeled atomic. Linux, standard-library-only Python, all supervision guards, and one declaration authorizing at most one predecessor termination remain mandatory. Existing tmux atomic replacement and persisted mappings remain compatible.

## Modifications

Independent review clarified unchanged tmux failure retry, the narrow retained-shell successor-launch exception, server-generation identity, refusal of exec-replaced root shells, and one termination signal per declaration. Add explicit herdr/socket hermetic doubles to non-functional-requirements.md alongside the proposed backend contract.

## Resulting Changes

- README.md
- constraints.md
- contracts.md
- spec.md
- scenarios.md
- non-functional-requirements.md

## Ratification Review

ratification_review: auto-spawn
reviewer_model: opus
reviewer_identity: opus
separate_reviewer: True
read_only: True
reviewed_at: 2026-10-04T00:19:57Z
verdict: NO BLOCKERS
proposal_stem: herdr-pane-backend
content_digest: cb356c2dc00b30a9c8f337d968bbbae3caacc738e21e5ceba19e7f039b7783f8
