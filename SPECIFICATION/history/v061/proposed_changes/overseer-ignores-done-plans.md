---
topic: overseer-ignores-done-plans
author: overseer-ignore-done-plans
created_at: 2026-10-19T01:27:39Z
---

## Proposal: A done track receives no act of any kind

### Target specification files

- SPECIFICATION/spec.md
- SPECIFICATION/scenarios.md

### Summary

Define a DONE track — a track holding a standing `done` declaration, or a plan track whose plan directory is archived while its session is still live — and require that the daemon perform NO act on it: no paste or daemon message by any transport, no keystroke, no restart or replacement, no resume retry, no compaction-latch wrap-up, no release of a held delivery. Its session and pane are never closed by the daemon, and its row is quiet.

### Motivation

Maintainer direction, verbatim: "This is clearly a bug in the overseer. It should be doing absolutely nothing with done plans, much less burning any tokens on them. It should be completely ignoring them. The only reason they should not be closed is because I need to be able to read the wrap-up and ensure that they are completed. Open a new session with a plan to change the overseer to make it behave this way and drive it to completion." (maintainer, 2026-10-19 ~01:15Z) Measured on the live daemon (release 5.31.1, log window 2026-10-15T10:35Z..2026-10-19T01:16Z, recorded on plan epic overseer-jfp23f research 001): three plans archived while their sessions were live kept being supervised. `livespec::factory-worker-nodes-gitops` had its `done` voided twice by the daemon ("session resumed generating", age 3288s) and then received a 50% wrap-up paste; `livespec::k3s-on-gmktec-for-vps-usage` had `done` voided at age 3258s, its compaction latch fired, and a 50% wrap-up was pasted; `livespec-overseer::caam-mixed-plan-capacity` sat as a `warned` attention member. Two independent gaps: (1) the code-only archived-live retention (maintainer ruling 2026-09-12) re-admits an archived plan with a live session to the FULL supervision cascade, while this spec still says such rows are garbage-collected; (2) the generation-based `done` void fires on a finished session's own self-paced wakeup (~55 min after declaring), after which the next due band pastes a wrap-up into a finished plan. The existing clauses forbid individual acts (wrap-up bands, the keep-going nudge, restart) one by one; the maintainer's direction is categorical, so the rule must be stated as one prohibition over every act path, not a list that a new act path can slip past.

### Proposed Changes

In spec.md §"The terminal declaration", insert after the paragraph beginning "While `done` stands, the daemon MUST NOT paste a wrap-up" a new paragraph:

> A DONE TRACK is a track holding a standing `done` declaration, or a plan track whose plan directory is archived (or gone) while its recorded session is still live, per §"Track discovery and the mapping store". The daemon MUST perform NO act on a done track: it MUST NOT paste, type, or deliver any daemon message to it by any transport (a wrap-up at any band, a keep-going or pair-stall nudge, a notice, a resume or a resume retry, a compaction-latch wrap-up, or the release of a held delivery), MUST NOT send it any keystroke, and MUST NOT restart, respawn, or replace its session. The daemon MUST NOT close, kill, or archive a done track's session or pane: it stays open so the maintainer can read its wrap-up. Every observation of a done track is read-only, exactly as the `list` path is. A done track is therefore spent zero model turns by the daemon for as long as it stays done.

Replace the paragraph beginning "Live gate evidence still outranks `done`" with:

> Live gate evidence still outranks `done` for REPORTING: a done track whose pane shows an open structured picker is waiting on a human whatever it declared, and MUST be surfaced as a blocked attention member rather than the quiet row. Surfacing it is report-only: the daemon MUST NOT act on that track while it remains done.

In the paragraph beginning "The operator surface MUST render a track holding `done` as a QUIET row", change "a track holding `done`" to "a done track" in its first sentence, so an archived plan with a live session renders the quiet `done` row too.

scenarios.md — add after "## Scenario: A done declaration suppresses the keep-going nudge":

## Scenario: A done track receives no act on any path

Given a track holding `done` whose round has a band due, whose compaction latch would fire, whose pending resume would be retried, and which has a held channel delivery

When the daemon observes the track over a full supervision cycle

Then no paste, message, keystroke, restart, or replacement is delivered to it

And its session and pane remain open

## Proposal: The daemon never voids a done declaration

### Target specification files

- SPECIFICATION/spec.md
- SPECIFICATION/contracts.md
- SPECIFICATION/scenarios.md

### Summary

Remove the daemon-side generation-based void of `done`. Only an explicit re-open ends a done track: the session (or the maintainer) clearing its own `done` declaration, or the plan directory being moved back out of `plan/archive/` with its epic reopened.

### Motivation

Maintainer direction: "This is clearly a bug in the overseer. It should be doing absolutely nothing with done plans, much less burning any tokens on them. It should be completely ignoring them. The only reason they should not be closed is because I need to be able to read the wrap-up and ensure that they are completed. Open a new session with a plan to change the overseer to make it behave this way and drive it to completion." (maintainer, 2026-10-19 ~01:15Z) The direction is that only the maintainer's own action changes a done plan. Generation cannot distinguish a finished session's self-paced wakeup from new work; both measured voids (ages 3258s and 3288s) were self-wakeups, and each void re-armed the wrap-up cascade against a finished plan. The protocol already requires a session handed new work to clear its own `done` before resuming, so re-open stays possible and explicit; the daemon-side void was only a backstop for a session that does not, and that backstop is exactly the measured defect. Session decision (recorded on overseer-jfp23f, reported for objection): REMOVE the void rather than narrow it.

### Proposed Changes

spec.md §"The terminal declaration": replace the paragraph beginning "`done` is voided by exactly the evidence that voids a `blocked:` declaration" with:

> The daemon MUST NOT void, delete, overwrite, or expire a `done` declaration on any evidence — not on observed generation, not on background activity, not on idleness, and not on age. A session that resumes generating while holding `done` keeps its declaration and its track stays done.

Replace the paragraph beginning "A session that is handed new work after declaring `done` MUST clear its own" with:

> A done track is RE-OPENED only explicitly: by its session (or the maintainer) deleting or overwriting the session's own state file, or by the plan's directory being moved back out of `plan/archive/` with its epic reopened, per §"Track discovery and the mapping store". A session that is handed new work after declaring `done` MUST clear its own `done` declaration BEFORE resuming that work, so no window exists in which it is working while still asserting it wants nothing. Once re-opened, the track is supervised exactly as an undeclared track is, from its round's existing state: the re-open MUST NOT raise a certification floor, delete the round's durable record, or reset its notified bands.

contracts.md: replace the bullet beginning "`DONE` VOIDING, independent of the ready-side expiry" with:

- NO `DONE` VOIDING. The daemon MUST NOT void, delete, or overwrite a `done` declaration on any observation — generating, background command, idle, or age. Only the session's own write (or the maintainer's) clears it, per spec.md §"The terminal declaration".

scenarios.md: replace "## Scenario: A done session that resumes generating has its declaration voided" and its body with:

## Scenario: A done session that resumes generating keeps its declaration

Given a track holding a `done` declaration older than the two-minute grace

When the daemon observes the session actively generating on input that was not peer-injected

Then the declaration stands and its state file is untouched

And the track stays done and receives no act

Add after "## Scenario: A done session handed new work clears its own declaration first":

## Scenario: A done track whose session clears its own declaration is supervised again

Given a track holding `done` whose round has a band due

When its session deletes its own state file

Then the track is supervised as an undeclared track on the next observation

And its round's certification floor and notified bands are unchanged

## Proposal: An archived plan with a live session is retained for visibility only

### Target specification files

- SPECIFICATION/spec.md
- SPECIFICATION/scenarios.md

### Summary

State the archived-live retention the code already performs (maintainer ruling 2026-09-12) — a mapped plan row whose directory is archived is kept, with its row and mapping, while its recorded session still exists — and bound it to VISIBILITY: such a track is a done track, receives no act, and renders quiet. Archive-GC drops the row once the session is gone. Moving the directory back out of plan/archive/ re-opens it.

### Motivation

Maintainer direction: "This is clearly a bug in the overseer. It should be doing absolutely nothing with done plans, much less burning any tokens on them. It should be completely ignoring them. The only reason they should not be closed is because I need to be able to read the wrap-up and ensure that they are completed. Open a new session with a plan to change the overseer to make it behave this way and drive it to completion." (maintainer, 2026-10-19 ~01:15Z) The spec still says rows whose plan has been archived are garbage-collected, while the daemon since 2026-09-12 retains them AND supervises them fully; that undocumented supervision half is gap (1) in the measurement above. The visibility half is kept because the maintainer needs to read the wrap-up in the still-open session. This supersedes the supervision half of the 2026-09-12 ruling only.

### Proposed Changes

spec.md §"Track discovery and the mapping store": replace the sentence beginning "Rows whose plan has been archived or deleted are garbage-collected — with two protections:" through "never mistaken for a deleted plan." with:

> Rows whose plan has been archived or deleted are garbage-collected once their recorded session no longer exists — with two protections: an ACTIVE plan always wins over a same-named archived copy, and a repository whose root is transiently unreachable is never mistaken for a deleted plan. While a previously-mapped PLAN row's directory is archived or gone but its recorded session still exists, the row and its mapping are RETAINED, and the track stays in the displayed list, so the maintainer can read the session's wrap-up. Retention is for visibility only: such a track is a done track per §"The terminal declaration", receives no act of any kind, and renders as the quiet `done` row whatever its state file holds, including no declaration or a malformed one. Moving the plan's directory back out of `plan/archive/` (with its epic reopened) re-opens the track, and it is supervised again from the next observation.

scenarios.md — add after "## Scenario: A done track renders as a quiet row whether running or exited":

## Scenario: An archived plan whose session is still live receives nothing

Given a mapped plan track whose directory has been moved to `plan/archive/` while its recorded session is still live, with nothing declared and its remaining context below its threshold

When the daemon observes the track over a full supervision cycle

Then its row and mapping are retained and it renders the quiet `done` status outside NEEDS YOU

And no paste, message, keystroke, restart, or replacement is delivered to it

And its session and pane remain open

## Scenario: An archived plan moved back out of the archive is supervised again

Given an archived plan track whose recorded session is still live

When its plan directory is moved back to `plan/<topic>/`

Then the track is discovered as an active plan on the next observation and supervised as an undeclared track

## Scenario: An archived plan's row is collected once its session is gone

Given an archived plan track whose recorded session no longer exists

When the daemon runs its archive cleanup

Then the row and its mapping are garbage-collected
