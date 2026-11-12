---
proposal: enrolled-host-ssh-push.md
decision: modify
revised_at: 2026-11-12T19:07:45Z
author_human: Chad Woolley <thewoolleyman@gmail.com>
author_llm: claude-opus-5-5
---

## Decision and Rationale

Implements the maintainer's 2026-11-12 ruling on plan central-credential-service (overseer-iyfjbo): topology B with ssh push, no enrolment/HTTPS/host client, Remote Control re-issue after an account switch including the role holder's own panes, minimal status command showing live versus selected account, live login delivered, F-J rows deferred to the follow-up plan. Graded PASS-WITH-FIXES by legacy-coordinator-agent (session 7c4d3e4c); all 10 fixes applied at 8a6b78a7 and accepted without re-grade; revise decision taken under coordinator R301 delegation.

## Modifications

Beyond the proposal text, per the independent ratification review and the coordinator grade of #2961: (1) spec.md Push alerts and Factory credential probes bind only the report, not the central status view, which no longer carries those rows; (2) two scenarios added, An account switch re-issues Remote Control on the role holder's own sessions, and A macOS host applies a delivery from its inbox and its result is recorded, with owned coverage rows (overseer-fdwat6, overseer-7m6wu6); (3) contracts.md Remote Control re-issue pins Claude Code 2.1.322's real on-screen notice (Remote Control stopped — the app running this session is now signed in to a different Claude account) and narrows the pane filter to Claude Code panes not in a tmux mode, whole-line match, no re-issue when a submitted /remote-control already follows.

## Resulting Changes

- spec.md
- contracts.md
- scenarios.md
- constraints.md

## Ratification Review

ratification_review: auto-spawn
reviewer_model: sonnet
reviewer_identity: sonnet
separate_reviewer: True
read_only: True
reviewed_at: 2026-11-12T19:06:01Z
verdict: NO BLOCKERS
proposal_stem: enrolled-host-ssh-push
content_digest: e9649204a4e0260ef3039a11c9c7e0758f3f5612d30dc0f5cdabee484cee9368
