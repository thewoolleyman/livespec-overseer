---
proposal: sanctioned-out-of-band-seat.md
decision: modify
revised_at: 2026-11-02T07:45:33Z
author_human: Chad Woolley <thewoolleyman@gmail.com>
author_llm: claude-opus-5-5 (herdr-overseer)
---

## Decision and Rationale

Ratified under the delegated revise_decision_mode to unblock overseer-uzvcbn.7, which the dispatch tier gate refused on 2026-11-02 as unratified topic 'sanctioned-out-of-band-seat' (behaviour unstated; generalize '## The restart'). The change adds one operator entrypoint, as a subsection of §'The restart', plus four scenarios. The entrypoint is an operator surface, not a daemon act, so constraints.md §'Acting safety' and the daemon's same-runtime restart rule are untouched. It reuses §'The launch profile', §'Session-name derivation' and the start-intent of §'Non-interference with tracked work'. No design record is contradicted. The independent read-only Sonnet reviewer first returned five BLOCKERS: bare topic instead of derived session name; occupied target pane unspecified; Codex condition ambiguous under override; scenario gaps; override without stale-profile refusal. All were repaired as modifications, and the same reviewer returned NO BLOCKERS over the exact final bytes. One non-blocking note is left to the implementation: a rejected model token may only be detectable at launch, the same limit as the daemon's launch-profile rule. Heading-coverage and debt-register rows for the four new scenarios land in the same branch, owned by overseer-uzvcbn.7.

## Modifications

Made over the filed proposal after the independent review. (a) An operator-named runtime/model/wrapper override, needed to repair a seat whose recorded profile names a runtime it no longer runs (dispatch-control-plane records Claude but runs Codex). The named profile gets the same unrecognized/stale refusal. (b) `/rename` uses the track's derived session name under §'Session-name derivation', not the bare topic. (c) A refusal list checked before any record or input: untracked topic or no epic id, missing pane, a target pane whose foreground is not an idle shell at its prompt, unrecognized or stale profile. 'Launch' is defined as submitting the launch command at that shell prompt, with no termination. (d) The rename applies when the LAUNCHED runtime is Codex, with an explicit non-Codex path. (e) The start-intent is recorded before launch and amended with the outcome. (f) The re-bound profile names harness, model and wrapper (or null), and the daemon-identification race is stated benign. (g) Scenarios are expanded to four: Codex relaunch, non-Codex relaunch, unconfirmed rename, refusal.

## Resulting Changes

- scenarios.md
- spec.md

## Ratification Review

ratification_review: auto-spawn
reviewer_model: sonnet
reviewer_identity: sonnet
separate_reviewer: True
read_only: True
reviewed_at: 2026-11-02T07:45:32Z
verdict: NO BLOCKERS
proposal_stem: sanctioned-out-of-band-seat
content_digest: e2eda8d37b6d11616ebf694e4bd0f272aba0f568b183b7c1c39e661caa271764
