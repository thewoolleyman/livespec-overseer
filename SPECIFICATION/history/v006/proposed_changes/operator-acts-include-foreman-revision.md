---
proposal: operator-acts-include-foreman.md
decision: modify
revised_at: 2026-08-03T04:22:39Z
author_human: thewoolleyman <chad@thewoolleyman.com>
author_llm: claude-opus-5
---

## Decision and Rationale

Both deliberate-operator startup sentences must admit an authorized operator surface while leaving the daemon's auto-start prohibitions intact. The filed classifier matches the required never-started, crashed, and ambiguous split, but persisted-index evidence alone is insufficient for exact dead-runtime resumption.

## Modifications

Applied the filed operator-surface widening and launch classifier, but replaced EDIT 3 with the assessment's resumable-transcript guard: a dead runtime's exact persisted-index mapping is usable only when that runtime also retains the identifier's resumable transcript and cross-runtime candidates are unambiguous; missing, stale, conflicting, or mismatched evidence is reported as AMBIGUOUS and no launch occurs.

## Resulting Changes

- spec.md
- scenarios.md
- ../tests/heading-coverage.json
