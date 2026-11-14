---
proposal: remote-control-keep-alive-sweep.md
decision: modify
revised_at: 2026-11-14T23:14:20Z
author_human: Chad Woolley <thewoolleyman@gmail.com>
author_llm: claude-opus-5-5:distributed-send-message
---

## Decision and Rationale

Accepted. Maintainer direction 2026-11-15: every interactive dev seat on vps, hetzner-xubuntu and gamingpc-xubuntu stays on Remote Control and never stalls on a Remote Control dialog, inside the existing caam-delivery-push service.

## Modifications

Accepted with modifications from four rounds of independent read-only sonnet ratification review: the re-issue command is capped at once per pane per ten minutes, counting the post-push re-issue's sends; the folder-trust check compares the real path of the prompt's directory with herdr's pane cwd, strictly below the two roots, with Down pressed only while Yes is not selected; the session record is matched by pid; a pane with no record is unknown and gets no /remote-control or Escape but still has its enable dialog and trust prompt answered; Escape on the status panel waits while the record is busy; the sweep skips a host during a re-issue run; the alert clock, pane-id reuse, journal secrecy and in-memory state are defined; tmux stays with the re-issue; the evidence includes real captures of each dialog and a connected/disconnected record pair with status values.

## Resulting Changes

- contracts.md

## Ratification Review

ratification_review: auto-spawn
reviewer_model: sonnet
reviewer_identity: sonnet
separate_reviewer: True
read_only: True
reviewed_at: 2026-11-14T23:14:01Z
verdict: NO BLOCKERS
proposal_stem: remote-control-keep-alive-sweep
content_digest: a33911861e0817313ba73091199b4d87bd3b2d27b3b49d8402335722d9c366c8
