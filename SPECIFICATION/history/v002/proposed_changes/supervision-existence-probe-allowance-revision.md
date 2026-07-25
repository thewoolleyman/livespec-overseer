---
proposal: supervision-existence-probe-allowance.md
decision: accept
revised_at: 2026-07-25T06:08:20Z
author_human: thewoolleyman <chad@thewoolleyman.com>
author_llm: claude-opus-5[1m]
---

## Decision and Rationale

Accepted as filed. The allowance is genuinely bounded on three axes — liveness-gated (no probe at all without a currently matching live session), existence-only (no open, no read, no hash, no content or mtime dependence), and single-path (exactly one reserved artifact, plan/<topic>/supervisor-handoff.md) — and it is consistent with §"Non-interference"'s own enumeration, since an existence test is not an open, write, or hash. It tracks the cited design record (design.md section 11.4 stat-allowance bound, surfacing DECIDED 2026-07-23 and the fourth truth-table cell DECIDED 2026-07-24) without departure. EDIT 2 is what keeps the cross-reference honest: the discovery clause cites §"Non-interference" as its authority, so the exception is stated in both places rather than leaving one section contradicting the other — the repair that merged as PR #70 and cleared independent re-review with no blockers. The paired scenario satisfies the behavior-implies-Gherkin authoring split, and its new `## ` heading is co-edited atomically into tests/heading-coverage.json in this same decision. Ratifying ahead of the implementing slice (overseer-6uobos) is the design's section 11.6 sequencing, not drift. Anchors re-verified verbatim; this proposal's spans are disjoint from the carve-out's, so the two ratify order-independently, and this decision's spec.md carries both proposals' edits cumulatively because resulting_files writes apply in payload order.

## Resulting Changes

- spec.md
- scenarios.md
- ../tests/heading-coverage.json
