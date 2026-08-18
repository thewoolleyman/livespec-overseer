---
topic: winddown-rationale-expiry
author: claude-sonnet-5
created_at: 2026-08-18T21:56:54Z
---

## Proposal: winddown-declaration-expiry-on-recovery

### Target specification files

- SPECIFICATION/spec.md
- SPECIFICATION/scenarios.md
- SPECIFICATION/contracts.md

### Summary

Add a session-side rule: a supervised session's wind-down intent MUST be treated as expired once its own remaining context is restored strictly above its wind-down threshold (most commonly by the runtime's auto-compaction), and the session MUST clear its own standing declaration (`winding-down` or `ready` in its own state file) BEFORE resuming pending work from its own ledger-held plan state, deciding this from durable on-disk evidence rather than its own recollection, without waiting for a daemon-triggered restart. `SPECIFICATION/contracts.md` gains one companion bullet naming the session as a third, narrowly-scoped deleter of its own state file, alongside the daemon's two existing deleters, with no certification-floor effect.

### Motivation

Observed 2026-08-06 on a supervised session (repo livespec-overseer): low on context, the session refreshed its ledger-held resume state with a restart checkpoint and announced readiness for restart as PANE TEXT (no out-of-band declaration was ever written, so the daemon never opened a round around it). The runtime then auto-compacted the session to roughly 94% remaining context, which invalidated the restart rationale entirely, yet the session sat idle waiting for a restart that could never come, un-sticking only when the maintainer intervened -- at which point the session itself articulated the missing rule: compaction makes the old reading irrelevant, waiting is wrong, resume from the checkpoint. The ratified spec already handles the symmetric DAEMON-side half of this (spec.md's supervision-round recovered-closure, which closes an open round when a track's context recovers above threshold with an ABSENT state file) but that closure is explicitly and deliberately guarded to hold the round open whenever ANY session-written token stands, however stale -- so a session that wrote a wind-down declaration before recovering has no obligation telling it to clear that declaration and resume; it is exactly this asymmetry that would strand a session in the observed shape.

This proposal deliberately narrows to the case where the session's own state-file declaration is what is standing stale -- the same file and grammar the recovered-round closure already reasons about -- rather than to the observed incident's own PANE-TEXT-ONLY case, where no declaration was ever written at all. The pane-text root cause is a distinct, already-diagnosed defect (a generated charter/wrap-up MUST state that a declaration IS the state file, never pane text) tracked as a companion item on this same epic and deliberately OUT of this proposal's scope; this rule does not depend on it and does not claim to be the complete incident fix by itself.

### Proposed Changes

In `SPECIFICATION/spec.md`, add a new section titled `## Wind-down expiry on context recovery`, placed after `## The keep-going nudge` and before `## The watch-set declaration`, containing normative text along these lines (BCP14 keywords required):

```markdown
## Wind-down expiry on context recovery

A supervised session's own wind-down intent is scoped to the CONDITION that
produced it -- remaining context at or below the wind-down threshold -- and
MUST be treated by that session as EXPIRED once that condition no longer
holds. The runtime's own auto-compaction is the recognized case: it can
restore a session's remaining context to strictly above its wind-down
threshold at any point after the session formed a wind-down intent, and it
does so by an event that can also erase the session's own memory of having
formed that intent. A session MUST NOT decide this from recollection; it
MUST decide it from durable, on-disk evidence -- its own state file --
exactly as its declaration itself is decided. A session's own read of its
remaining-context percentage is not authoritative in the way the daemon's
is: if a session misjudges its own recovery and clears a declaration that
was in fact still warranted, the daemon's own escalating wrap-up remains
the backstop, re-teaching the protocol and re-soliciting a fresh
declaration exactly as it would for any other undeclared low-context
track.

A session whose own remaining context is, on its own observation, strictly
ABOVE its wind-down threshold, and which finds a declaration it wrote
(`winding-down` or `ready`) standing in its own state file, MUST treat that
declaration as expired. It MUST, in this order, first clear the
declaration -- by deleting or overwriting its own state file -- and only
THEN resume its own pending work from its own most recently appended
ledger-held plan-state entry, without waiting for a restart and without
re-declaring wind-down on account of that stale declaration alone. This
ordering is normative, not incidental: clearing first ensures no window
exists in which the session is both actively working and still carrying an
apparent restart authorization. A session evaluates this condition
whenever it next takes a turn -- there is no separate poll -- so a session
sitting fully idle post-recovery is exactly the case the daemon's own
keep-going nudge and escalation machinery exist to eventually reach; this
rule governs what the session does once it IS running, not how it is woken
from a standing declaration on its own. The ledger-held plan-state entry
the session appended while winding down is not wasted by this rule; it
stands as an ordinary, current checkpoint for the resumed work.

This rule authorizes no new restart path and creates none: it governs only
the session's own choice to keep working, never a daemon-triggered restart,
and the daemon's sole restart trigger (a fresh `ready` passing the restart
interlock, per contracts.md §"The restart interlock") is unchanged. A
session-cleared declaration raises no certification floor and is not an
expiry under contracts.md §"The state file"'s ready-side expiry rule, which
remains exclusively daemon-triggered. A session that has already fully
stopped, such that only the daemon's own restart mechanism could resume
it, remains outside this rule's reach; the daemon's own recovered-round
closure (§"The supervision round") governs that case once the state file
this rule clears has actually gone absent, and the two rules are
neighbors, not the same rule: the recovered-round closure is what the
daemon does once no declaration stands in the way, and this rule is what
the SESSION itself must do while one still does.
```

In `SPECIFICATION/scenarios.md`, add two new Given/When/Then scenarios immediately after `## Scenario: A recovered-round closure defers to any standing state-file content`:

```markdown
## Scenario: A session clears a stale winding-down acknowledgement and resumes after its own context recovers

Given a session that wrote `winding-down` to its own state file before its context fell, and its context was then restored -- by auto-compaction or any other means -- to strictly above its wind-down threshold

When the session next takes a turn and observes its own recovered context together with its own standing `winding-down` declaration

Then the session treats that declaration as expired

And it clears the declaration from its own state file before doing anything else

And only then does it resume its own pending work from its own most recently appended ledger-held plan-state entry, without waiting for a restart

And the daemon's restart trigger is unchanged: only a fresh ready declaration passing the restart interlock authorizes a restart

## Scenario: A session clears a stale ready declaration and resumes instead of waiting to be killed

Given a session that wrote `ready` to its own state file before its context fell, and its context was then restored -- by auto-compaction or any other means -- to strictly above its wind-down threshold, with no restart having occurred in between

When the session next takes a turn and observes its own recovered context together with its own standing `ready` declaration

Then the session treats that declaration as expired

And it clears the declaration from its own state file before doing anything else, raising no certification floor by doing so

And only then does it resume its own pending work from its own most recently appended ledger-held plan-state entry, without waiting to be restarted

And the daemon's restart trigger is unchanged: only a fresh ready declaration passing the restart interlock authorizes a restart
```

In `SPECIFICATION/contracts.md` §"The state file", add one bullet to the contract-rules list, alongside the existing daemon-deleter rules:

```markdown
- A session MAY delete its own state file when spec.md §"Wind-down expiry
  on context recovery" applies -- its own remaining context has recovered
  strictly above its wind-down threshold while its own prior `winding-down`
  or `ready` declaration still stands. This is the ONE case a session
  deletes its own declaration rather than the daemon deleting it. A
  session-cleared declaration raises NO certification floor and is
  distinct from the daemon-triggered ready-side expiry above: it has no
  recorded expiry instant, and it MUST NOT be treated as a floor-raising
  event by the restart interlock.
```
