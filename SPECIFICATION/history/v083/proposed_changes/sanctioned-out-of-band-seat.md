---
topic: sanctioned-out-of-band-seat
author: claude-opus-5-5
created_at: 2026-11-02T07:41:13Z
---

## Proposal: A sanctioned out-of-band relaunch entrypoint binds the seat it launches

### Target specification files

- SPECIFICATION/spec.md

### Summary

Add a subsection to spec.md §"The restart" for the one sanctioned operator entrypoint that relaunches a tracked seat outside the daemon's ready-gated restart. Given a tracked plan topic and a target pane, it launches the track's recorded runtime under its recorded launch profile. For a Codex track it binds and confirms `/rename <topic>` and reports the confirmed session to the terminal backend for that pane. It then delivers the restart's resume prompt and re-binds the track's mapping row to that pane, session and launch profile. It refuses before launching anything when its inputs do not name a tracked topic and an existing pane.

### Motivation

Only the daemon's own fresh-Codex restart binds `/rename <topic>` and refreshes the mapping row. Every other relaunch skips both: a coordinator relaunch, a maintainer's hand restart, or a bottom-pane manual restart. Measured 2026-10-26: dispatch-control-plane was relaunched by a coordinator, auto-titled 'Resume dispatch-control-plane', and its row kept a dead pane and a stale Claude launch profile. Measured again 2026-11-02: the same seat had sat idle at 10% context for about 28 hours, never wrapped up, because its row still bound a dead pane with harness=claude, and its relaunch had lost its model. On the same day herdr was measured reporting no `agent_session` for any Codex pane attached to the shared managed app-server. The launcher, which knows the pane, must therefore report the session itself, or the identification rule of §"Supervised runtimes" has no input for a relaunched seat. Factory item overseer-uzvcbn.7 carries the implementation and was refused before dispatch as spec-change tier, because this behaviour is unstated in the spec.

### Proposed Changes

In SPECIFICATION/spec.md, at the end of §"The restart" and after its "### The launch profile" subsection, add:

### The sanctioned out-of-band relaunch

A seat is sometimes relaunched outside the daemon's ready-gated restart: by a coordinator, by the maintainer, or from the bottom pane. The overseer MUST ship exactly ONE sanctioned entrypoint for that relaunch, and the operator skill MUST name it as the procedure for relaunching a seat outside the daemon. The entrypoint is an OPERATOR act, invoked on purpose for one named track. It is not a daemon act and MUST NOT widen any daemon acting rule of constraints.md §"Acting safety".

Given a tracked plan topic and a target pane, the entrypoint MUST refuse before launching anything, and without changing any record, when the topic names no mapped track, or when the target pane does not exist on the track's recorded backend instance. Otherwise it MUST launch the track's recorded runtime in that pane under the track's recorded launch profile, applying §"The launch profile" exactly as a daemon relaunch does: an unrecognized harness or a stale profile refuses the launch, and the launch environment is set or scrubbed.

For a Codex track the entrypoint MUST submit `/rename <topic>` in the launched session. It MUST treat the relaunch as successful only after the Codex session index shows a thread named EXACTLY the topic that was created by this launch. Once that is confirmed it MUST report that thread's identifier to the terminal backend as the agent session of the target pane, for a backend that accepts such a report, and only for that pane. When the rename cannot be confirmed within its bound, the entrypoint MUST report a failure naming the pane and the thread it observed, if any, and MUST leave the track's mapping row unchanged.

After the launch, and for a Codex track after the rename is confirmed, the entrypoint MUST deliver the resume prompt of this section, naming the track's repository path and recorded epic id. It MUST then re-bind the track's mapping row to the target pane, the launched session's identity and a launch profile naming the launched runtime and model. That way no binding to another pane or another runtime remains. The entrypoint MUST NOT write, consume or clear a state-file declaration, and MUST NOT terminate any process.

## Proposal: Scenarios for the sanctioned out-of-band relaunch

### Target specification files

- SPECIFICATION/scenarios.md

### Summary

Add three scenarios after the misnamed-Codex scenarios: a successful Codex relaunch binds the row and reports the session to the backend; an unconfirmed rename leaves the row unchanged and names the pane; and the entrypoint refuses an untracked topic or a missing pane before launching anything.

### Motivation

Every MUST of the new subsection is load-bearing behaviour and needs a Given/When/Then scenario. The scenarios sit beside the misnamed-Codex scenarios because the sanctioned relaunch is the repair route for the seats those scenarios surface.

### Proposed Changes

In SPECIFICATION/scenarios.md, after §"Scenario: Supervisor, other-track and out-of-repository threads are never misnamed candidates", add:

## Scenario: A sanctioned relaunch of a Codex seat binds its topic, pane and profile

Given a mapped Codex track whose row binds a pane that is gone, and an existing target pane on the same backend instance

When the operator runs the sanctioned relaunch entrypoint for that topic and target pane

Then the track's recorded runtime is launched in the target pane under its recorded launch profile

And /rename <topic> is submitted, and the Codex session index shows a thread created by this launch named exactly the topic

And the terminal backend reports that thread as the target pane's agent session

And the resume prompt naming the track's repository and epic is delivered to the launched session

And the track's mapping row binds the target pane, the launched session's identity and a launch profile naming the launched runtime and model

## Scenario: An unconfirmed rename leaves the relaunched seat's row unchanged

Given the sanctioned relaunch entrypoint has launched a Codex track's runtime in a target pane

When the Codex session index shows no thread named exactly the topic within the rename bound

Then the entrypoint reports a failure naming the pane and the thread it observed

And the track's mapping row is unchanged

And no agent session is reported to the terminal backend for the pane

## Scenario: The sanctioned relaunch refuses an untracked topic or a missing pane

Given a topic that names no mapped track, or a target pane that does not exist on the track's recorded backend instance

When the operator runs the sanctioned relaunch entrypoint

Then it refuses before launching anything

And no mapping row, state file or backend record is changed

Each of these scenarios MUST be reached by a test, or carried by a heading-coverage row naming its owning work item.
