---
topic: codex-track-misnamed-alert
author: claude-opus-5-5
created_at: 2026-10-26T13:32:51Z
---

## Proposal: A Codex track whose live thread contains but does not equal its topic is surfaced as misnamed

### Target specification files

- SPECIFICATION/spec.md
- SPECIFICATION/scenarios.md

### Summary

Add a clause to §"Session-name derivation": when a tracked Codex topic has no exactly-named thread but a live Codex process in the track's repository holds or indexes a thread whose name contains the topic and differs from it, the daemon MUST surface a distinct `codex-track-misnamed` attention row naming the pane, thread id, actual name and the `/rename <topic>` repair; MUST NOT act on that session while it is misnamed; MUST notify once per distinct misnamed thread; and adopts it on the first round after its indexed name becomes exactly the topic. Two scenarios pin the behaviour.

### Motivation

Adoption matches a session's registered name against the plan topic exactly, and only the daemon's own fresh-Codex launch binds `/rename <topic>`. Any other relaunch (a coordinator relaunch, a maintainer hand restart, a bottom-pane manual restart) leaves Codex to auto-title the thread from its first prompt, and the auto-title routinely contains the topic (measured 2026-10-26: dispatch-control-plane was indexed as `Resume dispatch-control-plane`). The daemon then reports bare session-gone, which is indistinguishable from a dead seat, and the track silently loses wrap-up and restart coverage. Exact matching stays correct: it is the identity guard. What is missing is SURFACING the near miss with its one-line repair. Work item: overseer-uzvcbn.6.

### Proposed Changes

In SPECIFICATION/spec.md §"Session-name derivation", insert after the paragraph ending "never a screen-scrape, and never a most-recent-by-time guess." this new paragraph:

> A Codex track whose live session is not named exactly after its topic MUST be surfaced rather than reported as gone. When a tracked Codex topic has no session whose indexed thread name equals the topic, and a live Codex process whose working directory resolves inside the track's repository holds or indexes a thread whose name CONTAINS the topic but is not equal to it, the daemon MUST raise a distinct `codex-track-misnamed` attention row in place of a bare session-gone row. That row MUST name the live pane, the thread identifier, the thread's actual name, and the exact one-line repair `/rename <topic>` to be typed in that pane. While a track reads misnamed, the daemon MUST NOT adopt, wrap up, nudge, restart, or consume a ready declaration for that session: containment of the topic is evidence for the operator, never an identity, and exact-name adoption remains the only way a session becomes a track. The daemon MUST notify the operator of a misnamed track once per distinct misnamed thread, not once per supervision round. On the first round after that thread's indexed name becomes exactly the topic, ordinary exact-name adoption applies: the session is adopted, the track binds the session's live pane, and the misnamed row clears.

In SPECIFICATION/scenarios.md, append:

## Scenario: A live Codex thread named around its topic is surfaced as misnamed, not adopted

Given a tracked Codex topic with no thread named exactly that topic

And a live Codex process in the track's repository whose indexed thread name is `Resume <topic>`

When a supervision round runs

Then the attention surface shows a `codex-track-misnamed` row naming the pane, the thread identifier, the name `Resume <topic>` and the repair `/rename <topic>`

And no bare session-gone row is shown for the track

And the session is not adopted, wrapped up, nudged or restarted

And a second round with nothing changed sends the operator no second notification

## Scenario: A misnamed Codex track is adopted on the round after it is renamed to its topic

Given a track reading `codex-track-misnamed` for a live Codex thread in pane P

When that thread's indexed name becomes exactly the topic

And the next supervision round runs

Then the session is adopted for the track

And the track is bound to pane P

And the misnamed row is cleared

Register both scenario headings in tests/heading-coverage.json as spec-first coverage debt (test "TODO") owned by work item overseer-uzvcbn.6.

## Proposal: Live proofs of session naming and restart use a sacrificial seat, never an active session

### Target specification files

- SPECIFICATION/non-functional-requirements.md

### Summary

Add a bullet to non-functional-requirements.md §"Scenarios": any live proof that renames, misnames, restarts, sends keys to, closes or re-briefs a supervised session MUST run against a sacrificial seat started for a small, inactive, unrelated throwaway plan and torn down afterwards, never against an operator's active session.

### Motivation

Maintainer direction 2026-10-26, after an item's host-captured proof named the live dispatch-control-plane seat as its reproduction subject: 'This is an important session. Don't touch it. If you need to do this as part of your definition of done, spin up some other inactive, small, unrelated plan to prove it. Don't touch any of my active ones.' This is a contributor-facing verification rule about how this repository's live evidence is gathered, so it belongs in non-functional requirements rather than in the supervision contract.

### Proposed Changes

In SPECIFICATION/non-functional-requirements.md §"Scenarios", append this bullet:

- A live proof that renames, misnames, restarts, sends keys to, closes or re-briefs a supervised session MUST run against a SACRIFICIAL seat: a fresh session started for a small, inactive plan unrelated to any active work, torn down once the proof is captured. It MUST NEVER use one of the operator's active sessions as its subject or reproduction, even when that session currently exhibits the defect being proved.
