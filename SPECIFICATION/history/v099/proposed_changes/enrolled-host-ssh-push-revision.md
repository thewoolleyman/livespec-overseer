---
proposal: enrolled-host-ssh-push.md
decision: modify
revised_at: 2026-11-13T09:42:19Z
author_human: Chad Woolley <thewoolleyman@gmail.com>
author_llm: claude-opus-5-5
---

## Decision and Rationale

Re-cut of the enrolled-host-ssh-push design that #2960 ratified as v096 on its own branch, where it collided with master's own v096 (f2e83487); re-filed against master v098 per the maintainer's 2026-11-12 rulings on plan central-credential-service (epic overseer-iyfjbo): topology B, ssh push, no enrolment, HTTPS transport or host client, Remote Control re-issue after an account switch, a minimal status command, forwarded refusals, remote sessions and the login-age, probe and alert rows deferred. The proposal states exactly the text the #2960 revise and its two coordinator-graded amendments produced, and corrects the Remote Control clause to the real Claude Code 2.1.323 account-switch capture of 2026-11-13. Implementations already merged against this design: #2962 (push over ssh and the status command, overseer-aj577z, overseer-ky6u2l) and #2979 (live-account confirmation fixes, overseer-4ji2n4). Revise decision taken under coordinator R301 delegation.

## Modifications

Per the independent ratification review: (1) contracts.md §"The account-rotation operation", paragraph "A host-started schedule": "where the operator-facing report and the central status view read them" becomes "where the operator-facing report reads them", since the central status view is replaced by the status command (a dangling reference #2960's v096 also missed); (2) contracts.md §"Enrolled-host delivery", Remote Control re-issue: adds the identification rule, a pane's foreground process is Claude Code when its command line's executable has the basename `claude` or lies under `~/.local/share/claude/versions/<version>` of the host's user; (3) scenarios.md "An account switch re-issues Remote Control only where it stopped": the Given adds that tmux reports each pane's current command as `2.1.323`, not `claude`, and a third pane where a pager displays the notice text, and the Then sends nothing to the second pane or to the pager pane.

## Resulting Changes

- constraints.md
- contracts.md
- scenarios.md
- spec.md

## Ratification Review

ratification_review: auto-spawn
reviewer_model: sonnet
reviewer_identity: sonnet
separate_reviewer: True
read_only: True
reviewed_at: 2026-11-13T09:41:39Z
verdict: NO BLOCKERS
proposal_stem: enrolled-host-ssh-push
content_digest: 6c448bcb499f29f6898515a7d30439df58ac0cd1a4208a7551b6b32113eb1796
