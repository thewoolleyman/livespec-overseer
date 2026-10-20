## The maintainer's statement of what done means

This is clearly a bug in the overseer. It should be doing absolutely nothing with done plans, much less burning any tokens on them. It should be completely ignoring them. The only reason they should not be closed is because I need to be able to read the wrap-up and ensure that they are completed. Open a new session with a plan to change the overseer to make it behave this way and drive it to completion.

## Definition of Done assertions derived from that statement

- The live fleet overseerd daemon delivers no paste, keystroke, restart, replacement or done-void to a plan track whose plan directory is archived while its session is still live, across a measured window of at least one full supervision cycle.
- The live fleet overseerd daemon delivers no wrap-up, nudge, notice, keystroke, restart or compaction-latch wrap-up to a track holding a standing done declaration, and never voids that declaration because the session generated on its own.
- A done plan's session and pane stay open on the host, and the operator surface renders its row as a quiet done row rather than an attention member.
- A plan the maintainer re-opens, by moving its directory back out of plan/archive/ or by its session clearing its own done declaration, is supervised again by the live daemon.
- The done-plan rule is stated in livespec-overseer SPECIFICATION/ and the running daemon reports a released version that implements it.

# overseer-ignore-done-plans — baseline measurement (2026-10-19)

## Maintainer direction (verbatim, 2026-10-19 ~01:15Z, relayed by coordinator
## `gitops-fleet-capacity-monitoring`)

"This is clearly a bug in the overseer. It should be doing absolutely nothing
with done plans, much less burning any tokens on them. It should be completely
ignoring them. The only reason they should not be closed is because I need to
be able to read the wrap-up and ensure that they are completed. Open a new
session with a plan to change the overseer to make it behave this way and
drive it to completion."

## What the live daemon did (measured, not inferred)

Source: the running daemon's own history,
`~/.claude/plugins/cache/livespec-overseer/livespec-overseer/fe6630ca9b2d/tmp/overseer/daemon.log`
(the daemon runs from its plugin-cache checkout; the repo's own
`tmp/overseer/daemon.log` stopped 2026-10-16 and is NOT the live log). Daemon
release 5.31.1, log window 2026-10-15T10:35Z .. 2026-10-19T01:16Z.

Three plans were archived while their sessions were live. For each, the daemon
logged `archived-live-retained` ("archived plan … kept under supervision — its
recorded session is still live") and then kept acting on it:

| topic | archived (retained) | acts after archive |
|---|---|---|
| `livespec::factory-worker-nodes-gitops` | 2026-10-17T16:01:28Z | `done` voided twice (16:58:13Z, 23:14:20Z, "session resumed generating", age 3288s); 50% wrap-up PASTED 16:59:15Z; 161 `winddown-starved` reports; 5 `danger-non-responder`; row now `warned` "context compaction 47%->100%; restart required" |
| `livespec::k3s-on-gmktec-for-vps-usage` | 2026-10-18T21:36:47Z | `done` voided 22:30:24Z (age 3258s); compaction latched 22:32:00Z; 50% wrap-up PASTED 22:32:05Z |
| `livespec-overseer::caam-mixed-plan-capacity` | 2026-10-16T12:45:22Z | no paste; row `warned` "BAD state file: 'working'" (an attention member) |

Shape of the defect, two independent gaps:

1. **Archival does not end supervision.** `_supervisor_archived_live`
   (maintainer ruling 2026-09-12, code-only — not in SPECIFICATION/, which
   still says archived rows are garbage-collected) re-admits an archived plan
   whose session is live to the FULL supervision cascade: wrap-ups, nudges,
   compaction latch, ready-gated restart.
2. **`done` is voided by the session's own generation.** Each void came ~55
   minutes after the declaration (3258–3288s), which matches a session's own
   self-paced wakeup, not a maintainer handing it new work. After the void the
   track is supervised as undeclared (spec.md §"The terminal declaration"), so
   the next band due — here the compaction latch — pastes a wrap-up. That is a
   model turn the overseer spent on a finished plan.

## Target rule (to ratify)

A DONE track — a plan track whose plan directory is archived, or any track
holding a standing `done` declaration — receives NO act: no paste of any kind,
no keystroke, no restart/replacement, no compaction-latch wrap-up, and no
daemon-side void of its `done`. Its session and pane are never closed by the
daemon; it renders as a quiet row. Only an explicit re-open ends it: the plan
directory moved back out of `plan/archive/`, or the session (or maintainer)
removing its own `done`.

Decision recorded (session-decided, report for objection): the
generation-based `done` void is REMOVED rather than narrowed. The maintainer's
direction is that only the maintainer's own action re-opens a done plan;
generation cannot distinguish a self-wakeup from new work, and the measured
voids were self-wakeups. Re-open stays possible and explicit — the protocol
already requires a session handed new work to clear its own `done` first.
This supersedes the supervision half of the 2026-09-12 archived-live ruling;
its visibility half (the row and mapping are kept while the session lives) is
retained, because the maintainer needs to read the wrap-up.
