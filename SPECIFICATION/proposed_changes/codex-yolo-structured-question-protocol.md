---
topic: codex-yolo-structured-question-protocol
author: openai-gpt-5.6-sol
created_at: 2026-08-04T14:16:30Z
---

## Proposal: Make structured-question capability evidence-based without weakening blocked declarations

### Target specification files

- SPECIFICATION/spec.md
- SPECIFICATION/contracts.md
- SPECIFICATION/scenarios.md

### Summary

Correct the supervision contract's assumption that a Codex session launched in YOLO mode cannot render a structured question, while preserving the out-of-band blocked declaration as a runtime- and harness-independent safety mechanism.

### Motivation

A live interactive Codex session running --dangerously-bypass-approvals-and-sandbox with default_mode_request_user_input enabled rendered and completed a native structured picker on 2026-08-04. External pane capture distinguished tool availability and invocation from model self-report. The current marker-protocol text names that mode as inherently unable to raise a structured question, but headless codex exec and other contexts still require the prose fallback, and some human decisions are not representable as a structured picker. The correction must therefore remove the false runtime example without deleting or narrowing the blocked: escape hatch.

### Proposed Changes

In `spec.md` under the out-of-band state declaration, state that structured-question capability MUST be derived from live gate evidence rather than inferred from a runtime name, launch mode, or approval/sandbox policy. A supervised session MAY use `blocked: <one-line reason>` whenever it is genuinely waiting on a human and cannot obtain the needed decision through an available structured gate; the escape hatch MUST remain available even for a runtime that can render structured questions in some interactive contexts. The existence of a structured-question feature MUST NOT make the blocked declaration conditional on that feature being enabled, suitable for the decision, or available in the current harness.

In `contracts.md` under the keep-going nudge, require the nudge to describe the blocked declaration generically and truthfully. The message MUST NOT name a runtime or launch mode as inherently unable to render structured questions unless that inability is established by current runtime evidence. A live structured gate MUST continue to classify the pane as waiting on a human and suppress nudge and wrap-up pastes; absence of a gate MUST NOT be treated as proof that the session can obtain human input another way. The `blocked:` token, its surfacing behavior, and its restart prohibition MUST remain unchanged by this correction.

In `scenarios.md`, add a scenario in which an interactive Codex session launched with approval and sandbox bypass renders a native structured picker: the pane is classified as a structured gate from its live rendering, the daemon pastes neither a nudge nor a wrap-up, and no state declaration is inferred. Add a second scenario in which the same runtime is running in a headless or otherwise picker-unavailable context, or needs a decision that the structured surface cannot express: the session MAY declare `blocked: <one-line reason>`, the operator surface names it with coordinates, and the daemon MUST neither restart nor keystroke into it. These scenarios MUST establish that the live pane evidence, not the YOLO label, selects the path.
