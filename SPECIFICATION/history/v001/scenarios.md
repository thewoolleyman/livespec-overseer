# livespec-overseer — scenarios

The canonical operator-observable behaviors of the supervision contract, as
plain Gherkin. Each scenario states one guarantee; together they walk the
full round — warn, acknowledge, declare, restart — plus the refusal and
fail-soft paths.

## Scenario: A wrap-up is injected when a track crosses its threshold

Given a tracked session whose remaining context has fallen to its wind-down threshold

And the session's pane is in a verified idle-input state

When the daemon observes the track

Then it durably records an injection stamp before touching the pane

And pastes the escalating wrap-up message as one atomic paste

And the message names the state-file path, the three writable values, and the handoff path

## Scenario: The wrap-up sharpens as context keeps falling

Given a tracked session that was warned at its threshold

When its remaining context later crosses a lower ten-percent band

Then the daemon sends one further wrap-up for that band

And the message is a suggestion above thirty percent remaining

And an insistent demand to stop at thirty percent remaining and below

## Scenario: A band never fires twice in one round

Given a track that has already been warned for a band this round

When the daemon restarts and observes the same track below that band again

Then no second wrap-up is sent for that band

Because the notified bands are recorded durably, not in daemon memory

## Scenario: A winding-down acknowledgement pauses the escalation

Given a warned session that wrote winding-down to its state file

When the daemon next observes the track

Then no further wrap-up is pasted while the acknowledgement is fresh

Because the daemon never keystrokes into a session that is actively wrapping up

## Scenario: A stale acknowledgement resumes escalation but authorizes nothing

Given a session whose winding-down acknowledgement is older than fifteen minutes

When the daemon observes the track still below threshold

Then the escalation resumes and the track is re-reported to the operator

And the daemon still takes no action against the session

## Scenario: A fresh ready declaration triggers the atomic restart

Given a warned session that wrote ready to its state file after this round's injection stamp

And the pane is idle, settled, and positively identified as this track's session

When the daemon observes the track

Then it replaces the pane's process in one atomic operation

And hands the fresh session exactly one prompt pointing at the track's handoff

And deletes the state file and the round's stamp so the declaration cannot re-trigger

## Scenario: A ready declaration from a prior round never restarts

Given a state file declaring ready whose modification time predates this round's injection stamp

When the daemon evaluates the restart interlock

Then the interlock fails and no restart occurs

## Scenario: A ready declaration is voided when its session resumes work

Given a session that declared ready and then went busy again

When the declaration is older than the voiding grace

Then the daemon clears the now-false declaration instead of restarting later

And a declaration younger than the grace survives its own turn's busy tail

## Scenario: An undeclared session at the danger line is reported, never restarted

Given a warned session at twenty percent remaining context or below

And its state file holds no declaration

When the daemon observes the track

Then it reports the track loudly as not responding, with full coordinates

And performs no restart and no further act against the session

## Scenario: A malformed state value is surfaced and treated as no declaration

Given a state file whose first line is not one of the protocol's values

When the daemon reads the track's declaration

Then the malformed value is surfaced to the operator by name

And the track is treated as having declared nothing

And no act is ever authorized by the malformed value

## Scenario: A blocked declaration is relayed, not answered

Given a session that wrote blocked with a one-line reason

When the daemon observes the track

Then the track is relayed to the operator as non-blocking text

And the alert names the topic, repository, session, pane, and a jump command

And the session is never keystroked and never restarted while blocked

## Scenario: An idle session with context left is nudged once per episode

Given a tracked session that has been continuously idle for at least one hour

And its remaining context is above its threshold

And it is not waiting on a human and has declared nothing

When the daemon observes the track

Then it pastes one keep-going message and records its own marker in the state file

And it does not nudge the same idle episode again

And the marker clears when the session works again, re-arming a future episode

## Scenario: An unassigned plan is discovered but never auto-started

Given a watched repository containing a plan directory with no assigned session

When the daemon discovers tracks

Then the plan appears as unassigned

And the daemon never launches a session for it

## Scenario: Topics colliding across repositories get qualified session names

Given two watched repositories that both contain the same plan topic

When a session name is derived for either track

Then the name is qualified with the repository slug and a single dash

And a topic unique to one repository keeps its bare topic name

## Scenario: The daemon refuses an unsupported host

Given a host missing a declared runtime requirement

When the daemon starts

Then it refuses to run and names the failed precondition

And that refusal precedes every other startup gate

## Scenario: The daemon refuses a repository that does not ignore its scratch path

Given a watched repository that does not gitignore the overseer's scratch directory

When the daemon starts

Then it refuses to run and names the offending repository

## Scenario: A second daemon instance refuses to start

Given a daemon already holding the singleton lock for the mapping store

When a second daemon starts against the same store

Then the second instance refuses and names the contested lock

## Scenario: A dropped resume submission is retried without a second kill

Given a restart whose fresh session came up with the resume prompt unsubmitted

When the daemon observes the track on later cycles

Then it re-sends the submission only, until the prompt lands

And it never kills the fresh session again without a fresh ready declaration

And the track remains visible as needing attention until the resume submits

## Scenario: A restart never switches a track's runtime

Given a tracked session supervised under one agent runtime

When the daemon restarts it on a ready declaration

Then the fresh session is resumed under that same runtime

And the other runtime's launch command is never issued at that pane

## Scenario: An unknown context reading never triggers a wrap-up

Given a pane whose capture yields no readable remaining-context value

When the daemon evaluates the track's context

Then the last known value is kept and the unknown reading counts as no crossing

And the track's context renders as unknown rather than a guess
