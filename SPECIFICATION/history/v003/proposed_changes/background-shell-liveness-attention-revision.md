---
proposal: background-shell-liveness-attention.md
decision: modify
revised_at: 2026-07-28T16:17:47Z
author_human: thewoolleyman <chad@thewoolleyman.com>
author_llm: claude-opus-5[1m]
---

## Decision and Rationale

The proposal ratifies the control-plane liveness contract that survived an eight-review adversarial gate (two waves, Fable and GPT-Codex, every finding verified and folded) and carries the maintainer's explicit rulings of 2026-07-28: full supervisor-pair citizenship under the identical marker protocol and restart interlock, the guarded both-stalled pair nudge with its one bounded busy-suppression exception, bounded attention-suppression with the background-command instance, and the accepted value defaults. Two independent ratification-counsel reviews (Fable and GPT-Codex) each verified all nine edits apply exactly as specified and each independently found the same single coherence defect: EDIT 8(b) corrects the restart preservation guarantee in contracts.md while the parallel sentence in spec.md §"The restart" still states the uncorrected disjunction, which would snapshot a direct cross-file contradiction on exactly the guarantee being sharpened. The decision is therefore modify rather than accept: land the nine edits verbatim plus one counsel-drafted co-edit aligning that parallel sentence. The co-edit introduces no new design decision; it realizes the already-ruled EDIT 8(b) substance (one declaration must never authorize two kills) in the second location, and it aligns with the already-ratified scenario "A dropped resume submission is retried without a second kill". The intent-preservation gate was checked and is clear: the replaced clause cites no design record.

## Modifications

One co-edit beyond the proposal's nine: spec.md §"The restart", the paragraph opening "Every step of the restart is a hard gate." is replaced so its failure taxonomy matches EDIT 8(b): a FAILED respawn (process never replaced) preserves the ready declaration for retry, while a respawn that SUCCEEDED but whose fresh session is never recognized has already destroyed the predecessor and consumes the kill authorization — the round is held open for submission retry only and any further kill requires a genuinely fresh ready (cross-referencing contracts.md §"The restart interlock"). The section's following sentences (submission-only retry; structured-gate handling) already agree and are unchanged. All nine proposal edits are otherwise applied verbatim, re-wrapped to the files' 76-column prose style.

## Resulting Changes

- spec.md
- contracts.md
