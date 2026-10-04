---
topic: herdr-pane-backend
author: gpt-6
created_at: 2026-10-04T00:02:24Z
---

## Proposal: Support verified herdr and tmux ownership with guarded restart parity

### Target specification files

- SPECIFICATION/README.md
- SPECIFICATION/constraints.md
- SPECIFICATION/contracts.md
- SPECIFICATION/spec.md
- SPECIFICATION/scenarios.md

### Summary

Add herdr as a Linux terminal backend selected by verified process ownership, preserving the two-pane operator session and all supervision safeguards.

### Motivation

The maintainer requests herdr tabs and panes alongside tmux, selected by parent processes, with live-tested parity. Measured herdr 0.9.3 supports layout, capture, input and process inspection but has no native atomic respawn, requiring an explicitly guarded replacement contract.

### Proposed Changes

The daemon MUST support tmux and herdr selected by the nearest positively verified owning ancestor and exact pane; environment alone MUST NOT establish ownership. Unknown ownership MUST fail closed. Backend-qualified coordinates MUST distinguish server and pane while preserving legacy tmux mappings. The daemon MUST remain above the same interactive LLM session and bootstrap MUST be idempotent. Every supervision, paste, declaration, model-profile and ready-only restart guard MUST apply equally. tmux MUST retain native atomic replacement. herdr MAY replace through a serialized operation with durable predecessor and launch-attempt evidence, verified idle retained shell, no second kill under one declaration, no duplicate uncertain launch, and no successful completion without a verified successor. The change explicitly supersedes the prior tmux-only/no-abstraction requirement and narrows native atomic replacement to tmux; it preserves Linux and standard-library-only dependencies. Add Given/When/Then scenarios for selection, stale environment refusal, identity separation, parity, partial replacement recovery and prerequisite failures.
