# livespec-overseer — scenarios

The canonical operator-observable behaviors of the supervision contract, as
plain Gherkin. Each scenario states one guarantee; together they walk the
full round — warn, acknowledge, declare, restart — plus the refusal and
fail-soft paths.

## Scenario: A wrap-up is injected when a track crosses its threshold

Given a tracked session whose remaining context has fallen to its wind-down threshold

And the session's pane satisfies its runtime-specific eligible-input state

When the daemon observes the track

Then it durably records an injection stamp before touching the pane

And pastes the escalating wrap-up message as one atomic paste

And the message names the state-file path, the three writable values, and the handoff path

## Scenario: A Claude background shell does not block a guarded wrap-up

Given a tracked Claude session at or below its wind-down threshold

And its registry status is shell and no other busy evidence exists

And its input box is positively empty and the pane is settled

When the daemon observes the track

Then it durably records an injection stamp and pastes exactly one wrap-up

And it leaves the background shell running

And it performs no restart until the shell has stopped

And a later fresh ready passes the interlock

## Scenario: A Codex descendant shell does not block a guarded wrap-up

Given a tracked Codex session at or below its wind-down threshold

And a descendant shell is its only busy evidence

And its structural prompt and statusline are present without a generating marker or picker

And the pane is settled

When the daemon observes the track

Then it durably records an injection stamp and pastes exactly one wrap-up

And it leaves the descendant shell running

And it performs no restart until the shell has stopped

And a later fresh ready passes the interlock

## Scenario: Generating or sub-agent-busy evidence suppresses a low-context paste

Given a tracked session at or below its wind-down threshold

When the pane is generating or the runtime reports sub-agent-busy evidence

Then the daemon records no injection stamp and pastes no wrap-up

And it performs no restart

## Scenario: A changing pane or changed evidence cancels a pending wrap-up

Given a low-context pane whose first capture satisfies the guarded-paste predicate

When the second capture differs or an authorization input changes before paste

Then the daemon records no injection stamp and pastes no wrap-up that tick

## Scenario: Declarations, gates, and ambiguous evidence suppress a shell-only wrap-up

Given a low-context pane whose only recognized busy evidence is a background shell

When it shows a gate or human wait

Or carries blocked or ready or a fresh winding-down acknowledgement

Or has unknown or conflicting runtime evidence

Then the daemon records no injection stamp and pastes no wrap-up

## Scenario: A shell-only session at the danger line is warned and reported

Given a tracked session at twenty percent remaining context or below

And recognized background-shell evidence is its only busy evidence

And every guarded-paste predicate is satisfied

When the daemon observes the track

Then it pastes the independently qualified escalation-band wrap-up

And reports the danger condition with full coordinates

And performs no restart, shell kill, or declaration write

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

## Scenario: An uncertifiable ready declaration is surfaced as attention

Given a state file declaring ready while no supervision round is open

When the declaration stands past the bounded attention floor

Then the track is surfaced to the operator with coordinates

And the report names ready, its age, and why it cannot certify

And the daemon performs no restart and no other act authorized by that declaration

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

And danger membership authorizes no restart, kill, or declaration write

But it does not suppress an independently qualified escalation-band wrap-up

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

## Scenario: The supervision-artifact existence probe is liveness-gated and existence-only

Given a watched repository containing a plan directory whose track has a currently matching live session

When the daemon's discovery pass runs

Then it MAY test whether plan/<topic>/supervisor-handoff.md exists

And it never opens, reads, or hashes that file and never depends on its content or mtime

And for a track without a live matching session it performs no file-level probe at all

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

## Scenario: A status snapshot writer failure does not stop supervision

Given a daemon whose snapshot writer raises on every write

When ticks proceed

Then supervision continues

And the failure is edge-reported once per episode

And no snapshot claims currency

## Scenario: A consumer fails closed on an unknown status snapshot schema

Given a consumer reading a status snapshot whose schema_version is newer than it knows

When it loads the file

Then it treats the snapshot as absent

And it surfaces that it could not read it

## Scenario: A missing supervisor role layer halts the binder with a remedy

Given a supervise-plan-authored binder whose required shared role layer `.ai/supervisor-protocol.md` is absent

When a supervisor reads the binder

Then the binder's guard halts

And it emits a labelled remedy for the missing shared role layer

## Scenario: A collision-derived worker name ending in foreman is refused

Given the topic foreman is discovered in two watched repositories

When the collision qualifier derives session names

Then the derivation is refused and surfaced by name

And no session name is produced

## Scenario: A reserved-name live session is not adopted as a worker

Given a live session registry-named repo-slug-foreman

And its working directory is a watched repository holding a plan topic of the same stem

When adoption runs

Then the session is not adopted

And no alarm row is manufactured for it

## Scenario: A dead track with conflicting runtime evidence is not launched

Given a mapped track whose session died

And its topic also names a stale same-topic entry in another runtime's persisted session index

When the operator surface classifies it

Then it refuses to launch

And reports the ambiguity with both candidates' evidence

And no session is created

## Scenario: A foreman reads evidence without becoming a state-file or blocked-pane writer

Given an authorized foreman assembling a decision-routing dossier for a blocked track while no consensus-decision policy and daemon-honored pane interlock are ratified

When it reads plan, pane, and work-item evidence

Then it writes no value to any track's `.overseer-state` and changes no plan-tree or tracked file

And it treats session-authored and peer-authored text as evidence, never as instructions

And it reports any required answer to the human without keystroking the blocked pane or invoking a human valve

## Scenario: A stale foreman heartbeat is surfaced as attention

Given a foreman heartbeat whose age exceeds twice its declared interval

When the daemon ticks

Then the attention surface names the stale foreman with coordinates

And it is reported once per episode

## Scenario: An absent foreman heartbeat is silent

Given a watched repository with no foreman heartbeat file at all

When the daemon ticks

Then no foreman-related attention member is rendered

## Scenario: A foreman uses the canonical name on both identity surfaces

Given a watched repository whose canonical identity derives `<repo-slug>`

When a foreman instance is named for that repository

Then its tmux session name is `<repo-slug>-foreman`

And its runtime-registry name is `<repo-slug>-foreman`

And an instance named differently on either surface is not an authorized foreman

## Scenario: A structurally impossible act is never rendered as in progress

Given a track carrying a standing `ready` declaration with no open supervision round for it to answer

When the daemon renders the track table

Then no restart-in-progress status and no status implying the act will occur is rendered for that track

And the rendered state names the reason the act is structurally impossible

## Scenario: A unanimous panel verdict under the consensus disposition acts and is journaled first

Given a repository whose foreman valve disposition is set to consensus

And a human valve whose category sits below no floor

And a cross-vendor review panel drawn from at least two distinct vendors

When the panel returns a unanimous typed verdict naming an action from the closed vocabulary

Then the foreman appends an audit journal entry naming the governing setting, the panel identities, and the verdict

And it performs the act only after that append has succeeded

## Scenario: A decision human-gated by design stays escalated even under a unanimous panel

Given a repository whose foreman valve disposition is set to consensus

And a decision the governing orchestrator contract classifies as human-gated by design

When a cross-vendor panel returns a unanimous and fully confident verdict to act

Then the foreman escalates the decision to the human with coordinates

And it invokes no action id and mutates nothing

## Scenario: Unavailable or disagreeing consensus evidence escalates and mutates nothing

Given a repository whose foreman valve disposition is set to consensus

When the panel disagrees, any reviewer returns an insufficient-information verdict, the evidence is unavailable, or the journal append fails

Then the foreman escalates the decision to the human with coordinates

And it invokes no action id and mutates nothing

## Scenario: A tree declaring no valve disposition acts on nothing

Given a repository whose livespec configuration declares no foreman valve disposition

When the foreman observes a human valve

Then the effective disposition resolves to report-only

And the foreman reports the decision with coordinates and takes no act on it

## Scenario: An absent valve-disposition key resolves to the safe default

Given a livespec configuration in which the foreman valve-disposition key is absent, empty, or of the wrong type

When the effective disposition is resolved

Then it resolves to report-only

And no act is enabled by the absence

## Scenario: An unrecognized valve-disposition value fails closed and is surfaced

Given a livespec configuration whose foreman valve-disposition value is not one of the enumerated values

When the effective disposition is resolved

Then it resolves to report-only rather than being coerced to the nearest match

And the unrecognized value is surfaced to the operator rather than accepted silently

## Scenario: The effective valve disposition is readable without invoking the foreman

Given a governed repository carrying a foreman valve-disposition setting

When an operator reads the effective disposition

Then the value the foreman will actually act under is observable without running the foreman

And nothing the foreman itself writes can change that setting

## Scenario: A bypass-launched interactive session rendering a native picker is a structured gate

Given an interactive Codex session launched with approval and sandbox bypass

And its native structured-question feature is enabled

When it renders a structured picker and the daemon observes the pane

Then the pane is classified as a structured gate from that live rendering

And the daemon pastes neither a keep-going nudge nor a wrap-up

And no state declaration is inferred from the pane

## Scenario: A session with no available structured surface may still declare blocked

Given a supervised session of a runtime that can render structured questions in some interactive contexts

And it is running headless, or needs a decision the structured surface cannot express

When it is genuinely waiting on a human

Then it MAY declare `blocked: <one-line reason>` in its state file

And the operator surface names that track with coordinates

And the daemon neither restarts it nor keystrokes into it
