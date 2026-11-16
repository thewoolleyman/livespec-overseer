---
proposal: sweep-greyed-suggestion-is-not-input.md
decision: modify
revised_at: 2026-11-16T19:45:29Z
author_human: Chad Woolley <thewoolleyman@gmail.com>
author_llm: claude-sonnet-5-5
---

## Decision and Rationale

DoD 4 of plan central-credential-service (epic overseer-iyfjbo), carrier overseer-klzawj. Measured 2026-11-16 on hetzner-xubuntu: two idle seats showing only Claude Code's greyed prompt suggestion were never re-issued onto Remote Control for 40+ minutes, because both overseer/remote_control_sweep.py and overseer/remote_control_reissue.py treat any text after the prompt mark as typed. The proposal makes the shared input-box judgement read the pane with colour attributes, so a suggestion is an empty box and typed text still blocks. Decided under spec_governance.revise_decision_mode delegated; two independent sonnet reviewers (the first returned BLOCKERS on the earlier bytes, both fixed below; the second returned NO BLOCKERS on the final bytes).

## Modifications

The proposal text is tightened. (1) 'Dim' was undefined and the proposal's own evidence (foreground 38;2;136;136;136, an RGB grey, not SGR 2) contradicted the obvious reading: dim text is now text carrying SGR 2 (faint) or a foreground colour attribute that differs from the input box's default foreground, such as 38;2;136;136;136, in both the contracts paragraph and the scenario Givens; text carrying neither is typed. (2) The fail-safe now states explicitly that a pane read WITHOUT colour attributes, a tmux pane included, and any read that cannot tell dim text from typed text, is treated as holding unsubmitted text, in the contracts paragraph and the scenario's last Then, so the tmux re-issue path is unambiguous. (3) One clause states that the matching of the account-changed notice and every other visible text stays plain-text and only the input-box judgement uses the colour-attribute read. Co-edit: TODO heading-coverage row and debt entry for the new scenario, owned by overseer-klzawj, in the same pull request.

## Resulting Changes

- contracts.md
- scenarios.md

## Ratification Review

ratification_review: auto-spawn
reviewer_model: sonnet
reviewer_identity: sonnet
separate_reviewer: True
read_only: True
reviewed_at: 2026-11-16T19:44:41Z
verdict: NO BLOCKERS
proposal_stem: sweep-greyed-suggestion-is-not-input
content_digest: 657bc9a7314d9e36e89f330d702c96f56f1c6764b736d61368291406a05ff60e
