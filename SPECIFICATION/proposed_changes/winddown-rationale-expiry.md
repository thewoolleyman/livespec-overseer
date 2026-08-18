---
topic: winddown-rationale-expiry
author: claude-sonnet-5
created_at: 2026-08-18T21:56:54Z
---

## Proposal: winddown-declaration-expiry-on-recovery

### Target specification files

- SPECIFICATION/spec.md
- SPECIFICATION/scenarios.md

### Summary

Add a session-side rule: a supervised session's wind-down intent MUST be treated as expired once its own remaining context is restored strictly above its wind-down threshold (most commonly by the runtime's auto-compaction), and the session MUST clear any declaration it wrote and resume from its own ledger-held plan state, on disk evidence rather than its own recollection, without waiting for a daemon-triggered restart.

### Motivation

Observed 2026-08-06 on a supervised session (repo livespec-overseer): low on context, the session refreshed its ledger-held resume state with a restart checkpoint and announced readiness for restart as PANE TEXT (no out-of-band declaration was ever written, so the daemon never opened a round around it). The runtime then auto-compacted the session to roughly 94% remaining context, which invalidated the restart rationale entirely, yet the session sat idle waiting for a restart that could never come, un-sticking only when the maintainer intervened -- at which point the session itself articulated the missing rule: compaction makes the old reading irrelevant, waiting is wrong, resume from the checkpoint. The ratified spec already handles the symmetric DAEMON-side half of this (spec.md's supervision-round recovered-closure, which closes an open round when a track's context recovers above threshold with an ABSENT state file) but that closure is explicitly and deliberately guarded to hold the round open whenever ANY session-written token stands, however stale -- so a session that wrote (or believes it wrote) a wind-down declaration before recovering has no obligation telling it to clear that declaration and resume; it is exactly this asymmetry that stranded the observed session. This rule is the session's own complementary half, never a new daemon-triggered restart path.

### Proposed Changes

In `SPECIFICATION/spec.md`, add a new section titled `## Wind-down expiry on context recovery`, placed after `## The keep-going nudge` and before `## The watch-set declaration`, containing normative text along these lines (BCP14 keywords required):

```markdown
## Wind-down expiry on context recovery

A supervised session's own wind-down intent is scoped to the CONDITION that
produced it -- remaining context at or below the wind-down threshold -- and
MUST be treated by that session as EXPIRED once that condition no longer
holds. The runtime's own auto-compaction is the recognized case: it can
restore a session's remaining context to comfortably above its wind-down
threshold at any point after the session formed a wind-down intent, and it
does so by an event that can also erase the session's own memory of having
formed that intent. A session MUST NOT decide this from recollection; it
MUST decide it from durable, on-disk evidence, exactly as its declaration
itself is decided.

A session whose own remaining context is, on its own observation, strictly
ABOVE its wind-down threshold, and which finds under its own topic either a
wind-down declaration it wrote (`winding-down` or `ready` in its own state
file) or a just-appended ledger entry recording that it had begun winding
down, MUST treat that intent as expired. It MUST clear any such declaration
it wrote -- by deleting or overwriting its own state file -- and MUST resume
its own pending work from its own most recently appended ledger-held
plan-state entry, without waiting for a restart and without re-declaring
wind-down on account of that stale evidence alone. The ledger-held
plan-state entry the session appended while winding down is not wasted by
this rule; it stands as an ordinary, current checkpoint for the resumed
work.

This rule authorizes no new restart path and creates none: it governs only
the session's own choice to keep working, never a daemon-triggered restart,
and the daemon's sole restart trigger (a fresh `ready` passing the restart
interlock, per contracts.md §"The restart interlock") is unchanged. A
session that has already fully stopped, such that only the daemon's own
restart mechanism could resume it, remains outside this rule's reach; the
daemon's own recovered-round closure (§"The supervision round") governs
that case, and the two rules are neighbors, not the same rule: the
recovered-round closure is what the daemon does when NO declaration stands
in the way, and this rule is what the SESSION itself must do when one does.
```

In `SPECIFICATION/scenarios.md`, add a new Given/When/Then scenario immediately after `## Scenario: A recovered-round closure defers to any standing state-file content`:

```markdown
## Scenario: A session clears an expired wind-down intent and resumes after its own context recovers

Given a session that wrote a wind-down declaration before its context fell, and its context was then restored -- by auto-compaction or any other means -- to strictly above its wind-down threshold

When the session observes its own recovered context together with its own standing declaration or a just-appended wind-down ledger entry under its own topic

Then the session treats its wind-down intent as expired

And it clears the declaration it wrote from its own state file

And it resumes its own pending work from its own most recently appended ledger-held plan-state entry, without waiting for a restart

And the daemon's restart trigger is unchanged: only a fresh ready declaration passing the restart interlock authorizes a restart
```

No change to `SPECIFICATION/contracts.md` is proposed here: the daemon's wire-level restart interlock, round-recovery closure, and state-file grammar are already correctly specified and are explicitly unaffected -- this rule binds only the session's own behavior, never the daemon's.
