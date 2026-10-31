---
topic: sacrificial-seat-scope-and-pane-unblock
author: claude-opus-5-5 (herdr-overseer)
created_at: 2026-10-31T14:23:12Z
---

## Proposal: Scope the sacrificial-seat rule to live proofs and mandate unblocking a session stuck at a picker

### Target specification files

- SPECIFICATION/non-functional-requirements.md

### Summary

State that the sacrificial-seat bullet in §"Scenarios" governs LIVE PROOFS only and is not a ban on a coordinator typing into a session's pane; add a MUST for a coordinator to unblock a session blocked at a decision picker it cannot otherwise answer, followed by the answer in words over a cross-session message; and add the courtesy that, outside unblocking, a session avoids typing into another session's input field.

### Motivation

Maintainer ruling 2026-10-31 (~13:1xZ, attended, in the gitops-fleet-capacity-monitoring coordinator chat; recorded on livespec-dev-tooling-dfixhe and quoted verbatim on work item overseer-wcsd): "However that rule got recorded, it is completely wrong. You, in the coordinator role, can absolutely do whatever you need to do to unblock a pane. The intent of the rule was to not always spam the actual input field on other panes, which interferes with me trying to type into them. But if they are actually blocked on a picker and there is no other way for you to unblock them, then there is, yes, absolutely, a mandate to unblock them and to type whatever you need to in the pane." The bullet's own text is scoped to "a live proof that ...", but it was carried into session handoffs as a blanket "never send keys to ANY active maintainer session". On 2026-10-31 that reading led a seat (herdr-overseer) to refuse coordinator-directed unblocking, sit frozen at its own picker for hours, and cause the coordinator to withdraw a ruling. The spec must say what the rule does NOT forbid as plainly as what it does, so the scope cannot be lost in paraphrase.

### Proposed Changes

In SPECIFICATION/non-functional-requirements.md, section ## Scenarios, keep the existing sacrificial-seat bullet unchanged and add the following three bullets immediately after it:

- The sacrificial-seat rule above governs LIVE PROOFS only: a session that renames, misnames, restarts, sends keys to, closes or re-briefs a supervised session IN ORDER TO PROVE a behaviour. It does not forbid any other interaction with a session's pane, and in particular it MUST NOT be read as forbidding a coordinator from typing into a session's pane.
- A coordinator MUST unblock a session that is blocked at a decision picker it cannot otherwise answer, by typing whatever that picker needs into the session's pane, and then MUST send the same answer to that session in words by cross-session message, so the session's conversation records what was chosen and by whom.
- Outside unblocking a session at a picker, a session SHOULD NOT type into another session's input field, because keystrokes there collide with the operator's own typing; it uses a cross-session message instead.
