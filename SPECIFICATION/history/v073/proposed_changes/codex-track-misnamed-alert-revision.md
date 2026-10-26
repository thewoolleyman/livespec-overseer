---
proposal: codex-track-misnamed-alert.md
decision: modify
revised_at: 2026-10-26T13:39:24Z
author_human: Chad Woolley <thewoolleyman@gmail.com>
author_llm: claude-opus-5-5
---

## Decision and Rationale

Accepted in substance; modified after three rounds of independent opus review, the final one NO BLOCKERS. As filed, the clause matched the bare topic (which flags a correctly collision-qualified session and prescribes a wrong rename), let a -supervisor pair member or another track's session be a candidate, left case, multiplicity and evidence source undefined, deduplicated per thread in a way that conflicted with the re-arm rule of Notify, never block, keyed on a recorded runtime the mapping store does not reliably hold, said nothing about done tracks, and added an attention row without a contracts.md membership entry.

## Modifications

(1) Match on the track's DERIVED session name (including any cross-repository qualifier), case-sensitively; the repair is /rename <derived-name>; a thread named exactly the derived name is never misnamed. (2) Identity from live process evidence (a live Codex process whose working directory resolves inside the repository); only the name is read from the session index. (3) Exclusions: reserved-suffix names (case-insensitive), another discovered track's derived name, threads adopted by or bound to another track. (4) Exactly one row per track listing every candidate's pane, thread id and actual name. (5) Dedup identity is the condition plus the candidate thread-id set; a name change alone does not re-emit; re-arms on clear. (6) Applies to any mapped track whose session is gone; the candidate's live runtime makes it Codex, so a stale recorded harness does not suppress the row; unassigned plans and done tracks never raise it. (7) contracts.md Attention surface gains a report-only membership paragraph that replaces session-gone for that track. (8) A third scenario pins the exclusions. The sacrificial-seat bullet in non-functional-requirements.md is accepted unchanged. Coverage debt for the three scenarios (owner overseer-uzvcbn.6) and the repointing of the five v072 entries from the regroomed overseer-hc7j to its slices land in the same commit, outside the spec target.

## Resulting Changes

- contracts.md
- non-functional-requirements.md
- scenarios.md
- spec.md

## Ratification Review

ratification_review: auto-spawn
reviewer_model: opus
reviewer_identity: opus
separate_reviewer: True
read_only: True
reviewed_at: 2026-10-26T13:38:46Z
verdict: NO BLOCKERS
proposal_stem: codex-track-misnamed-alert
content_digest: 41d19b92fd55235f70dc69ca5aa57e6e27c2ac87e76c3787f9463bb51e090087
