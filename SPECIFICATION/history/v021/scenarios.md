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

And the message names the state-file path, the three writable values, and the ledger-held plan state

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

And hands the fresh session exactly one prompt naming the track's repository and its plan epic id

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

## Scenario: A ready declaration remains armed when its session resumes work

Given a session that declared ready and then went busy again

When the daemon next observes the track

Then the declaration remains armed and no restart occurs while the pane is
not verified settled-idle

And the declaration is not cleared, expired, or otherwise altered by the
activity

And the round's durable record and already-notified escalation bands are
unaffected

## Scenario: Repeated expiries never re-send an already-notified band

Given a session that repeatedly declares ready and each declaration ages past
the maximum without a settled-idle observation

When each declaration expires in turn within the same open round

Then no escalation band already notified in the open round is sent again

And the round's durable record and notified bands survive every expiry

And at most one expiry-notice is sent within the round however many
declarations expire

## Scenario: A round whose opening wrap-up never landed is un-opened

Given a track at its wind-down threshold whose injection stamp was just recorded

When the opening wrap-up paste fails to land

Then the daemon deletes the stamp it just wrote and leaves the track un-rounded

And a ready declaration written afterwards certifies nothing

## Scenario: A compacted session that re-crosses its threshold is re-warned in a fresh round

Given a delivered round whose every escalation band has been notified

When the session's effective remaining context is known, not stale, and
strictly above the track's wind-down threshold, its state file is absent,
and no resume submission is pending

Then the daemon closes the round as recovered by deleting its durable record
without touching any state file or pane

And when the session later crosses the threshold again a fresh round opens
and the wrap-up fires again

And a declaration written after the closure certifies nothing

## Scenario: A recovered-round closure defers to any standing state-file content

Given a delivered round whose session's effective remaining context has
recovered above the track's wind-down threshold

When the state file holds any session-written token however stale, or is
unreadable or malformed

Then the round's durable record survives and no closure occurs

And the daemon re-reads the state file immediately before any deletion so a
declaration appearing between observation and deletion also holds the round
open

## Scenario: A session clears a stale winding-down acknowledgement and resumes after its own context recovers

Given a session that wrote `winding-down` to its own state file before its context fell, and its context was then restored — by auto-compaction or any other means — to strictly above its wind-down threshold

When the session next takes a turn and observes its own recovered context together with its own standing `winding-down` declaration

Then the session treats that declaration as expired

And it clears the declaration from its own state file before doing anything else

And only then does it resume its own pending work from its own most recently appended ledger-held plan-state entry, without waiting for a restart

And the daemon's restart trigger is unchanged: only a fresh ready declaration passing the restart interlock authorizes a restart

## Scenario: A session clears a stale ready declaration and resumes instead of waiting to be killed

Given a session that wrote `ready` to its own state file before its context fell, and its context was then restored — by auto-compaction or any other means — to strictly above its wind-down threshold, with no restart having occurred in between

When the session next takes a turn and observes its own recovered context together with its own standing `ready` declaration

Then the session treats that declaration as expired

And it clears the declaration from its own state file before doing anything else, raising no certification floor by doing so

And only then does it resume its own pending work from its own most recently appended ledger-held plan-state entry, without waiting to be restarted

And the daemon's restart trigger is unchanged: only a fresh ready declaration passing the restart interlock authorizes a restart

## Scenario: An expired ready declaration is answered with one durable bounded expiry-notice

Given a delivered round in which a session's ready declaration expired

When the daemon next completes an observation whose guarded-paste predicate
passes

Then the session receives one expiry-notice naming the state-file path and the
fresh-ready requirement

And a second expiry within the same round sends no second notice, even across
a daemon restart

And no notified escalation band is re-sent and no restart is authorized

## Scenario: A standing uncertifiable declaration does not suppress the below-threshold branch

Given a track below its wind-down threshold carrying a ready declaration that cannot certify

And the declaration has stood past the attention floor

When the daemon evaluates the track

Then the track is surfaced as carrying a declaration that cannot certify

And the below-threshold branch is still evaluated on its own terms

And any suppression of the wrap-up comes from the paste predicate, never from the attention membership

## Scenario: A pane carrying a standing declaration is never pasted into

Given a track below its wind-down threshold whose state file declares ready

When the wrap-up paste predicate is evaluated

Then no wrap-up is pasted into that pane

And the outcome is the same whether or not background-shell evidence is present

## Scenario: A declaration on a track that was never in a round is surfaced, not healed

Given a track whose state file declares ready

And the track has neither an injection stamp nor a recorded expiry

When the daemon observes the track below its wind-down threshold

Then no wrap-up is pasted, because the pane carries a standing declaration

And the declaration certifies nothing, because the track has no certification floor

And the track is surfaced to the operator for as long as the declaration stands

## Scenario: A ready declaration written after an expiry certifies without a new round

Given a session whose earlier ready declaration expired

And the session later writes ready again, after the instant of that expiry

And the pane is idle, settled, and positively identified as this track's session

When the daemon evaluates the restart interlock

Then the interlock passes and the session is restarted

And no new wrap-up was required to authorize it

## Scenario: An expired declaration never certifies against its own expiry

Given a ready declaration that expired past the maximum age

And the state file still carried that same declaration unchanged before expiry
deleted it

When the daemon evaluates the restart interlock immediately before expiry
deletes the file

Then the interlock fails, because the declaration predates the instant of its own expiry

## Scenario: An aged declaration never certifies before its expiry is recorded

Given a ready declaration older than the maximum age

And no expiry yet recorded in the round's sidecar for that declaration

When the daemon evaluates the restart interlock in that same observation,
before recording or deleting the expiry

Then the interlock fails on the declaration's own age

And no restart is authorized

## Scenario: A ready declaration on a track that was never in a round certifies nothing

Given a track with no injection stamp and no recorded expiry

And a state file declaring ready

When the daemon evaluates the restart interlock

Then the interlock fails and the track is surfaced as carrying a declaration that cannot certify

## Scenario: A successor session never certifies against its predecessor's floor

Given a track whose declaration expired, leaving a certification floor

And the supervised session at that pane was replaced out of band after that
expiry

When the successor session writes ready after that floor

Then the interlock holds, because the identity at the pane differs from the round-open identity

And the track is surfaced to the operator rather than restarted

## Scenario: A session replaced before the expiry never inherits a certifiable floor

Given a round opened for a session that received the wrap-up

And that session was replaced out of band before its declaration expired

When the daemon expires the inherited declaration and the successor later writes ready

Then no certifiable floor was established by that expiry

And the interlock holds, because the identity at the pane differs from the round-open identity

And the successor is surfaced rather than restarted, having received no wrap-up

## Scenario: An undeterminable session identity fails the interlock closed

Given a track carrying a ready declaration newer than its certification floor

And the session identity live at the pane cannot be determined

When the daemon evaluates the restart interlock

Then the interlock fails and no restart occurs

And the track is surfaced rather than silently skipped

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

## Scenario: Discovery performs no file-level probe inside a plan directory

Given a watched repository containing a plan directory, with or without a currently matching live session

When the daemon's discovery pass runs

Then it performs no file-level probe inside the plan directory And it never
opens, reads, or hashes plan-tree handoff files as authorization And it
points the session at ledger-held plan state instead


## Scenario: A respawn prompt names the plan epic and repository so a cold-open session can resolve it

Given a track whose mapping row records the plan's ledger epic id

When the daemon respawns the session after a fresh `ready` declaration passes the interlock

Then the single pasted prompt names that repository path and that epic id literally

And a track with no recorded epic id is not respawned, its `ready` declaration is preserved, and the track is surfaced

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

## Scenario: A restarted session that never begins work is surfaced without a second kill

Given a successful respawn

And the exact expected resume text remains in the fresh composer's input

And the fresh session has consumed no context

And no `resume_pending` flag was recorded

When the evidence remains continuous beyond the 60-second floor

Then the track is in NEEDS YOU

And the attention count badges the overseer window

And the daemon reports coordinates without respawning, submitting, writing state, or terminating the session

When the session begins work or the composer changes

Then the membership and badge clear

And a later qualifying episode can edge-trigger again

And an unassigned track never enters this membership

## Scenario: A restart re-asserts an explicitly recorded model

Given a track whose mapping row carries a `model_profile` with an explicit
non-default model, captured from the live session's environ and argv at
adoption

When a fresh `ready` declaration passes the restart interlock and the
daemon restarts the track

Then the relaunch command carries the recorded explicit model

And the fresh session does not take the runtime's own default model

## Scenario: A restart re-asserts a local-llm track's wrapper and env

Given a track whose mapping row carries a `model_profile` naming a wrapper
path and a non-default model

When the daemon restarts the track

Then the relaunch invokes the recorded wrapper with the required autonomy
flags, prefixed with the recorded model so the wrapper's own deference
honors it

And the daemon does not leak its own cloud credentials into the relaunch

## Scenario: A stale launch profile is surfaced and the restart is skipped

Given a track whose mapping row carries a `model_profile` naming a wrapper
path that no longer exists on disk

When a fresh `ready` declaration passes the restart interlock

Then the daemon surfaces the stale profile

And it skips the restart for that tick rather than relaunching with a
default model or wrapper

## Scenario: A track with no recorded launch profile restarts unaffected

Given a track whose mapping row carries no `model_profile`

When the daemon restarts the track

Then the relaunch proceeds exactly as it did before this behavior existed

## Scenario: An exhausted escalation below threshold is surfaced, never acted on

Given a delivered round at or below its wind-down threshold whose every band
at or above the known current effective context is already notified

When the session stays idle under its runtime's idle predicate past the
ten-minute floor with no declaration on file, no pending resume submission,
and no recognized busy or background-shell evidence

Then the track enters the mechanical attention surface as
escalation-exhausted with its coordinates and is counted in the window badge

And the rendered note names the state-file path and states that the
runtime's idle indicator is not the protocol ready

And the daemon sends no keystroke and performs no restart on this member's
account

And the member clears edge-triggered when the session works, declares, or
the round closes

And an unknown or stale context reading establishes no membership

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

Given supervise-plan-authored binder entries on a plan's ledger epic whose required shared role layer `.ai/supervisor-protocol.md` is absent

When a supervisor reads the binder

Then the binder's guard halts

And it emits a labelled remedy for the missing shared role layer

## Scenario: An open supervisor obligation or malformed marker refuses completion

Given an active supervisor marker with an open obligation

Or a marker that is missing, malformed, stale, or unreadable

When the Driver completion gate evaluates an attempt to end the turn

Then it refuses completion

And it does not treat final-response or pane text as evidence of completion

## Scenario: A stale producer or prose-only wake claim refuses completion

Given an active supervisor marker with a terminal disposition

And its wake producer has a stale PID, wrong command or identity, unknown registered identity, or only a prose claim

When the Driver completion gate evaluates an attempt to end the turn

Then it refuses completion

And it records no successful completion from that evidence

## Scenario: An explicit plan-complete disposition may end an active supervisor turn

Given an active supervisor marker with no open obligations

And an explicit `plan-complete` disposition

And a verified independently running wake producer

When the Driver completion gate evaluates an attempt to end the turn

Then it permits completion

## Scenario: Exactly one genuine maintainer block may end an active supervisor turn

Given an active supervisor marker with no open obligations other than one genuine maintainer-blocking question

And a verified independently running wake producer

When the Driver completion gate evaluates an attempt to end the turn

Then it permits completion for that one question

And it refuses a second or non-maintainer blocking question

## Scenario: A verified wake producer cold-opens from fresh state

Given an active supervisor marker whose verified producer wakes

When that producer re-enters the supervisor

Then it cold-opens from the marker

And it re-queries fresh ledger and forge state

And the ended turn is not treated as the wake mechanism

## Scenario: User messages are additive during active supervision

Given an active supervisor marker with an objective and open obligations

When a user sends an ordinary message

Then the message is added without clearing the objective or obligations

When the user literally says `stop supervising <topic>`

Then supervision is cleared

When the user literally says `replace supervision objective`

Then only the recorded objective is replaced

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

## Scenario: A foreman relay embeds the full panel record on first delivery

Given a foreman about to relay a panel or evaluator outcome to a supervised session

When it composes the relay

Then the relay embeds every reviewer verdict with its rationale verbatim, the evaluator's outcome and reason, and an on-disk path the session can independently read

And an attributed summary with no such record is not sent as the relay

## Scenario: An escalation quotes the session's exact words rather than paraphrasing them

Given a supervised session's response the foreman is about to classify or escalate

When the foreman composes the escalation

Then the escalation quotes the session's exact words

And no paraphrase of that response is the basis for the escalation

## Scenario: A worker's corroboration request is not escalated as an authority challenge

Given a supervised session's response asks the foreman for data or evidence the foreman already possesses or can produce

When the foreman classifies that response

Then it is not escalated as an authority challenge

And the foreman satisfies the request with the data instead

## Scenario: Two consecutive STILL alerts force a fresh pane re-read

Given a tracked session has raised the daemon's report-only pane-still condition twice in a row

When the foreman observes the second STILL alert

Then it takes a fresh pane capture and re-classifies the session's state

And it does not rely on any standing explanation it had already formed for the idleness

## Scenario: A daemon-bounce-invalidated watch is not treated as armed

Given a foreman-established watch keyed only on a bare pane or process identifier

And the daemon has bounced since the watch was established

When the foreman consults the watch

Then the watch is not treated as a valid mechanism

And a watch keyed on re-resolvable identity plus a bounce-detection signal remains valid across the bounce

## Scenario: A foreman's own blocking question does not freeze supervision of other tracks

Given the foreman needs a human decision it cannot make itself for one tracked session

When it has no answer yet

Then the affected track is surfaced as a non-blocking attention condition on the existing mechanical attention surface

And the foreman continues ticking and supervising every other tracked session

And no restart authorization is altered by this escalation

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

## Scenario: A message queued behind an open picker is surfaced as attention

Given a tracked session whose row reports an open picker

And whose row status is NOT a human-blocked status

When an inbound cross-session message is queued behind that picker and remains unconsumed

Then that session becomes a report-only member of the attention surface with normal coordinates

And its note names the sender where the pane makes that available

And the membership is edge-triggered and participates in the NEEDS YOU count and window badge

And no act is authorized by the membership

And the member clears when the picker resolves or the queued message is consumed

## Scenario: An open picker with nothing queued behind it is not attention

Given a tracked session whose row reports an open picker

And no inbound cross-session message is queued behind that picker

When the daemon observes the pane

Then the session does NOT become a member on the queued-message condition

## Scenario: An unreadable snapshot holds decision-relevant context rather than delivering it

Given the foreman holds decision-relevant context for a supervised session

And the daemon snapshot is absent, unreadable, of an unknown schema, or stale, so no usable row is available for that session

When the foreman prepares to deliver that context

Then it treats the session's picker state as undetermined

And it does not deliver the context as an ordinary asynchronous message

And it holds the context under a bounded re-check that names the condition releasing it

And it surfaces that the row could not be read

## Scenario: A long-lived question states where late-arriving context is routed

Given the foreman raises a question that may stand open long enough to accumulate later context

When it composes that question's text

Then the text states where late-arriving context is to be routed

And a sender who cannot read a daemon row can act on that statement alone

## Scenario: Decision-relevant context is not delivered to a picker-parked session

Given a supervised session whose daemon row reports an open picker

And the foreman holds context relevant to the decision that picker is making

When the foreman prepares to deliver that context

Then it does not deliver it as an ordinary asynchronous message

And it either delivers through the picker's own free-text response channel or holds the context on a bounded schedule that names the condition releasing it

And no restart authorization is altered by the routing choice
