---
proposal: runtime-model-permitted-source.md
decision: accept
revised_at: 2026-09-02T17:38:15Z
author_human: thewoolleyman <chad@thewoolleyman.com>
author_llm: claude-opus-4-8
---

## Decision and Rationale

Admit the Claude conversation transcript's latest top-level assistant-message model token as a new permitted source for the launch profile's model, preferred over argv/environ only on a base-model difference so a mid-session /model switch survives a restart while a launch-token variant such as [1m] is never dropped. Uses the spec's own escape hatch; fail-soft and Claude-only. Independently ratified with NO BLOCKERS over the exact resulting-file bytes.

## Resulting Changes

- spec.md
- scenarios.md

## Ratification Review

ratification_review: auto-spawn
reviewer_model: opus
reviewer_identity: opus
separate_reviewer: True
read_only: True
reviewed_at: 2026-09-02T17:36:44Z
verdict: NO BLOCKERS
proposal_stem: runtime-model-permitted-source
content_digest: b9295f3abad8af1b1ad20fd669f32f9a29b14b19e5298c87747f41a55806009f
