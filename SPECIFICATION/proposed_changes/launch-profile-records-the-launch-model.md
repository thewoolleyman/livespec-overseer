---
topic: launch-profile-records-the-launch-model
author: claude-opus-5-1m
created_at: 2026-08-21T23:40:00Z
---

## Proposal: Narrow the launch profile's mid-session-switch guarantee to the model the track was LAUNCHED with

### Target specification files

- SPECIFICATION/spec.md

### Summary

Ratified v018 requires the daemon to honor a mid-session `/model` switch, and separately forbids the
statusline as anything but a verification signal. For a hand-launched Claude session those two
clauses cannot both be satisfied, because a `/model` switch rewrites neither argv nor environ and
the only surface that reflects it is the statusline. This proposal resolves that by narrowing the
guarantee rather than by reopening the restriction: a launch profile records the model the track
was LAUNCHED with, re-check at wrap-up continues to honor any switch a permitted source does
express, and a switch visible only in the statusline is SURFACED rather than silently honored or
silently lost.

### Motivation

Filed against ledger item `overseer-bc55wx.11`, whose full measurement record is on that item and
on plan epic `overseer-bc55wx`. The tension was found by auditing the SHIPPED feature against the
LIVE fleet.

THE TENSION, in the ratified text. Clause (i) requires capture at adoption and re-check at wrap-up
"so a mid-session `/model` switch is honored by the next restart's re-assertion". Clause (ii)
requires environ and argv/parent-chain as the primary source and permits the statusline's rendered
model name "only as a mismatch-detection verification signal, never as the primary source and never
through a display-name-to-launch-token lookup table". A `/model` switch writes to neither argv nor
environ, so for a session that carries no model token clause (i) is unsatisfiable under clause (ii).

THE TRANSCRIPT CANDIDATE WAS CHECKED FIRST, because it is the only route that could have satisfied
both clauses as written, and a negative result is what justifies touching the spec at all. Measured
across 60 recent transcripts. It is a genuine non-statusline source carrying model IDs rather than
display names, it resolves for every tracked session, and it does catch a mid-session switch — 15 of
the 60 recorded one. But it collapses the context variant: `claude-opus-5` is recorded for sessions
rendering "Opus 5 (1M context)" and for sessions rendering plain "Opus 5" alike, and no
variant-bearing value appears anywhere in any transcript. Adopting it would close the SPEC tension
while leaving this epic's headline harm — a silent loss of the 1M variant on restart — fully live.

WHAT MAKES THE NARROWING CHEAP NOW, AND IT IS A MEASUREMENT RATHER THAN AN ARGUMENT. Since
`overseer-dnchj6` landed, the overseer starts every track with an explicit model in argv, and argv
is the one permitted source in which the context variant survives. Measured 2026-08-21 23:26Z on
the live fleet: 15 of 59 live harness processes carry a model token in argv and ALL FIFTEEN carry
the context variant; 10 of 34 mapping rows now carry a launch profile, all reading model `opus[1m]`,
against zero at every earlier take. The settings default at that moment was the bare string `opus`,
which renders "Opus 5" — so those tracks would each LOSE the variant on a bare relaunch, and do not.

The residual case this proposal concedes is therefore narrow and shrinking: a HAND-LAUNCHED session
whose model is switched mid-session, where no permitted source expresses the new model at all. It is
not the case the epic was opened about, and it cannot be closed without consulting the statusline.

### Proposed Changes

THE GUARANTEE SHOULD BE NARROWED, in "The launch profile". The clause requiring capture at adoption
and re-check at wrap-up SHOULD be retained unchanged as an obligation — it is what lets a row whose
pane acquired a token after adoption self-heal on the wrap-up round that necessarily precedes any
restart of it — but the guarantee attached to it SHOULD be restated: a launch profile records the
model the track was LAUNCHED with, and re-check at wrap-up honors a mid-session change ONLY where a
permitted source expresses it.

THE CONCEDED CASE SHOULD BE STATED EXPLICITLY RATHER THAN LEFT AS A SILENT OUTCOME. Where a session's
current model is expressed in no permitted source, the specification SHOULD say that the daemon
re-asserts the recorded launch model, that this is deliberate, and that the divergence MUST be
SURFACED. It MUST NOT be silently honored and MUST NOT be silently lost. The existing
mismatch-detection signal is the surfacing mechanism and needs no new machinery: clause (ii) already
permits the statusline for exactly that purpose, and the shipped mismatch veto already skips a
restart whose rendered model disagrees with the recorded profile.

CLAUSE (ii) SHOULD BE LEFT INTACT. This proposal deliberately does not reopen it.

### Alternatives considered and NOT recommended

Recorded here with their costs so a revise pass has the full option set without re-deriving it, and
can ratify a different branch than the one recommended.

ALTERNATIVE A — AMEND CLAUSE (ii) TO PERMIT THE STATUSLINE SOLELY TO RECOVER A CONTEXT VARIANT that
no other source exposes. This is the only direction that closes the hand-launched case completely.
Its cost is that it reopens a ratified restriction which a prior adversarial review already rejected
one attempt to weaken, and that recovering `opus[1m]` from the rendered string "Opus 5 (1M context)"
is precisely the display-name-to-launch-token lookup clause (ii) names and forbids. If a later pass
wants this, it is a spec act and belongs at ratification, not in an implementing seat's judgement.

ALTERNATIVE B — PERMIT THE TRANSCRIPT `message.model` AS A SOURCE. Real model IDs rather than display
names, and it catches mid-session switches. Its cost is stated under Motivation: it collapses the
context variant onto the base model ID, so an implementation that adopted it would look conformant
and still silently downgrade every 1M-context session on restart. It is a real source and a partial
answer, and adopting it alone would close the spec question while leaving the harm.

ALTERNATIVE C — CONCEDE THE CASE WITH NO SURFACING, stating simply that a session whose model is not
expressed in argv or environ takes the settings default by design. This is the current silent
outcome written down. It is rejected because the exposed population is redefined every time the
settings default is edited — measured directly on this thread, whose own predecessor was conformant
at adoption, drifted into divergence purely because the default moved, and then lost the 1M variant
on restart without anything about the session having changed. A concession with no surfacing accepts
that reclassification silently and with no event anywhere in the system.

### Evidence and provenance

A cross-vendor consensus panel was convened on this question 2026-08-21T00:45Z; its readable record
is `tmp/overseer/foreman/panel/1d33d3ec6ad3c93defab26290f6d13aeffe93feda5ae4adea6b007986f0f7c85/`.
Both reviewers that returned a parseable judgement — `claude-opus-5` and `gpt-5.6-sol`, one from
each vendor — independently selected this direction; the third reviewer's response did not parse.
Neither defended any alternative above. The panel's aggregate outcome was `escalate`, and two of the
three legs producing it were tooling failures rather than reasoned disagreement: a malformed
reviewer response and a failed audit-journal append.

Filing this proposal does not amend the specification; the revise pass ratifies.
