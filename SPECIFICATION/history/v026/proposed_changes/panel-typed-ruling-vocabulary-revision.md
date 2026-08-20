---
proposal: panel-typed-ruling-vocabulary.md
decision: modify
revised_at: 2026-08-20T13:19:09Z
author_human: thewoolleyman <chad@thewoolleyman.com>
author_llm: claude-opus-5
---

## Decision and Rationale

Accepted in intent, modified in text. The proposal's own Proposed Changes section introduced the phrase 'whose kind is itself drawn from a closed enumeration' while anchoring that enumeration to nothing: no owner, no anti-drift rule, and no gate on widening it, unlike the action ids and the floor categories which are both bound by reference in the same section. An independent ratification review BLOCKED that draft on exactly this point, observing that the natural implementation is a code-level enum any PR can extend, which would leave 'closed' doing no normative work on precisely the axis this disposition exists to control. The ratified text therefore adds two governance paragraphs beyond the proposal: the ruling kinds are those the governing orchestrator contract defines and MUST NOT be restated here, an implementation-level enumeration explicitly does not satisfy the requirement, widening requires a ratified change to that contract, no configuration value may widen it, and a kind that contract does not define escalates as unenumerated. It also retires the proposal's relative human-valve phrasing for an absolute one, and reties 'MUST NOT widen which decisions the panel may reach' explicitly to the floor boundary, which a reviewer flagged as ambiguous under a plainer reading. A second independent reviewer returned NO BLOCKERS on these exact bytes and judged the divergence a correction within the proposal's declared intent rather than a separate change: the added paragraphs constrain how the enumeration may be defined and do not widen what the panel may do. The independent reviewers were separate read-only agents on model fable: the blocking first pass and the confirming second pass ratification-reviewer-panel-typed-ruling-2, which reviewed the corrected bytes without having authored them. The evidence block records reviewer_identity as 'fable' because the validator requires identity and model to be equal; the agent names are recorded here so the distinct passes remain traceable.

## Modifications

Beyond the proposal text: (1) added a paragraph binding the set of ruling kinds BY REFERENCE to the governing orchestrator contract, forbidding this tree from restating them, and escalating a ruling whose kind that contract does not define; (2) added a paragraph refusing an implementation-level enumeration as satisfying 'closed', gating widening behind a ratified change to the governing contract, forbidding any configuration value from widening it, and carrying the existing define-it-here obligation across from the floor categories; (3) replaced the proposal's relative human-valve sentence with an absolute one, and restated the no-laundering rule in terms of the actor shift so a supervised session executing a ruling cannot reach a decision a direct action id could not; (4) retitled the widening sentence to say the amendment MUST NOT MOVE THE FLOOR BOUNDARY, tying it to the floors rather than leaving it open to a plainer reading under which admitting typed rulings is precisely what makes previously-undisposable decisions disposable.

## Resulting Changes

- spec.md

## Ratification Review

ratification_review: auto-spawn
reviewer_model: fable
reviewer_identity: fable
separate_reviewer: True
read_only: True
reviewed_at: 2026-08-20T11:49:00Z
verdict: NO BLOCKERS
proposal_stem: panel-typed-ruling-vocabulary
content_digest: e8514db5b31fb1cd4f7ae3a9fac3f2ca919a01570a33d26fa9f4e17aa33fb182
