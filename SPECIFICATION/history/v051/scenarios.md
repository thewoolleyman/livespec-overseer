# livespec-overseer — scenarios

The canonical operator-observable behaviors of the supervision,
account-rotation and LLM credential-provider contracts, as plain Gherkin.
Each scenario is grouped under one named behavioral outcome; its clauses may
state the conditions and effects that jointly establish that outcome. Together
the scenarios cover the supervision round plus the refusal, fail-soft,
publication and credential-consumer paths.

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

## Scenario: A successor session's ready is surfaced immediately as a certification failure

Given a supervision round opened against one session identity

And a live successor session now occupying that pane under a different identity

And a standing ready declaration written by that successor

When the daemon completes the evaluation that observes the identity mismatch

Then the track is surfaced in that same completed evaluation with coordinates,
without waiting for the generic uncertifiable-ready continuity floor

And the row and its edge-triggered alert between them name the certification
failure, the round-open identity, and the live identity

And they name the remediation: the standing declaration cannot authorize a
restart, and the successor must complete a newly delivered current-session
round before declaring a fresh ready

And no respawn, declaration write, keystroke, or voiding of the declaration
occurs

And a low remaining-context reading does not relabel the row as ordinary danger

When the successor later completes a newly delivered current-session round and
declares a fresh ready

Then that fresh declaration is the only path by which a restart becomes
authorized

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

## Scenario: A failed un-open leaves a standing round that is surfaced

Given a track at a wind-down band with no round open

And the daemon writes the injection stamp and then fails to paste the opening
wrap-up

And the deletion of that just-written stamp also fails in the same observation

When the daemon renders the mechanical attention surface

Then the track is surfaced as carrying a standing round whose wrap-up was never
delivered

And the rendered note states that no wrap-up was delivered for that round

And no restart is authorized, no pane is keystroked, and the round's durable
record is neither deleted nor rewritten by the surfacing

## Scenario: A successful un-open after a failed wrap-up paste surfaces nothing

Given a track at a wind-down band with no round open

And the daemon writes the injection stamp and then fails to paste the opening
wrap-up

And the deletion of that just-written stamp SUCCEEDS

When the daemon renders the mechanical attention surface

Then the track is NOT surfaced as carrying a standing round whose wrap-up was
never delivered

And the track is left un-rounded so a later threshold crossing opens a fresh
round

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

And the fresh session carries no busy evidence

And no `resume_pending` flag was recorded

When the daemon acts on any tick while all of that evidence holds, including
before the 60-second floor is reached

Then it records `resume_pending` and re-sends the submission only

And it does not re-paste the resume text, respawn, terminate the session, or
write a declaration

And any composer text that is not an exact match confers no retry authority

And a fresh session that reads busy, or that shows a structured gate, is not
keystroked on this authority

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

## Scenario: The launch profile captures a mid-session model change from the transcript

Given a live Claude track launched with model `claude-opus-4-8` recorded in its
argv

And its conversation transcript's latest top-level assistant message names model
`claude-fable-5-1`

When the daemon captures the track's launch profile

Then the profile's model is `claude-fable-5-1`, the model the track is actually
running rather than its launched model

## Scenario: A same-base transcript model retains the launch token's context-window variant

Given a live Claude track launched with model `claude-opus-4-8[1m]` recorded in
its argv

And its conversation transcript's latest top-level assistant message names model
`claude-opus-4-8`

When the daemon captures the track's launch profile

Then the profile's model remains `claude-opus-4-8[1m]`, so the `[1m]`
context-window variant is not silently dropped by a source that does not carry it

## Scenario: The Codex launch profile captures a mid-session model change from its state database

Given a live Codex track launched with model `gpt-5.6-terra` recorded in its
argv

And the active Codex state database's exact thread row names model
`gpt-5.6-luna` and the supervised repository as its cwd

When the daemon captures the track's launch profile at adoption

Then the profile's model is `gpt-5.6-luna`

Given that exact row changes to `gpt-5.6-sol` before the wrap-up round

When the daemon re-checks the profile at wrap-up

Then the profile's model is `gpt-5.6-sol`

And a later restart re-asserts `gpt-5.6-sol`

## Scenario: A same-base Codex database model preserves the launch-token variant

Given a live Codex track launched with model `gpt-5.6-sol[1m]` recorded in its
argv

And the active Codex state database's exact matching thread row names model
`gpt-5.6-sol`

When the daemon captures the track's launch profile

Then the profile's model remains `gpt-5.6-sol[1m]`

## Scenario: An unavailable or mismatched Codex state row fails soft

Given one live Codex track whose active state database is unavailable while a
lower-numbered database retains an exact thread row

And another live Codex track whose active database's exact-id row records a cwd
for a different repository

When the daemon captures each track's launch profile independently

Then each profile falls back to its argv-or-environ launch model

And neither capture blocks supervision or uses the lower-numbered or
wrong-repository token

## Scenario: Codex runtime-model capture never reads a rollout body

Given a live Codex session identifier is present in the filename of a rollout
path held open by its supervised process

And the exact matching state-database row carries a usable model token and the
supervised repository cwd

And opening the rollout body would fail the capture

When the daemon captures the Codex launch profile

Then it obtains the model token from the state-database row

And it does not open, read, parse, or hash the rollout body

## Scenario: An ambiguous rollout set cannot lend another Codex session's model

Given a Codex carrier exposes more than one rollout candidate for the same
repository

And an indexed exact live identity selects one candidate for the tracked
session

And an ancestor or nested carrier exposes another session whose state row has
the same repository cwd

When the daemon captures the tracked session's launch profile

Then it queries only the row selected by the track's already-established exact
live identity

And it neither walks into the other carrier nor uses the other session's model

Given instead that no indexed identity or other exact process evidence selects
one of the tracked carrier's rollout candidates

When the daemon captures the launch profile

Then the state-database source is unusable and the profile falls back to its
argv-or-environ launch model

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

## Scenario: An unread verification signal is surfaced as unread, never as agreement

Given a track whose `model_profile` carries a recorded verification baseline,
and whose pane's rendered model cannot be read at restart time

When a fresh `ready` declaration passes the restart interlock

Then the daemon restarts the track, because an unreadable rendered model is
not a mismatch and never skips a restart

And it surfaces that the verification signal was not read

And a track whose rendered model IS read and agrees with the same baseline
restarts with no such surfacing, so silence is never reported as agreement

## Scenario: A track with no recorded launch profile restarts unaffected

Given a track whose mapping row carries no `model_profile`

When the daemon restarts the track

Then the relaunch uses exactly the COMMAND it used before this behavior existed

And the controlled environment variables are explicitly set or unset rather
than passively inherited, on every harness, because fail-soft governs the
command and never the environment

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

## Scenario: A collision-derived worker name ending in supervisor is refused

Given the topic supervisor is discovered in two watched repositories

When the collision qualifier derives session names

Then the derivation is refused and surfaced by name

And no session name is produced

## Scenario: A reserved-name live session is not adopted as a worker

Given a live session registry-named repo-slug-supervisor

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

## Scenario: A structurally impossible act is never rendered as in progress

Given a track carrying a standing `ready` declaration with no open supervision round for it to answer

When the daemon renders the track table

Then no restart-in-progress status and no status implying the act will occur is rendered for that track

And the rendered state names the reason the act is structurally impossible

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

## Scenario: A stalled reserved-entity picker gets exactly one charter reminder and is never answered

Given a tracked reserved-entity session whose derived row status is blocked:human

And whose live gate evidence shows an open structured picker

And whose pane capture has been unchanged past the bounded floor

When the daemon acts on that track

Then exactly one charter-reminder payload is pasted into that pane

And no Enter, digit, or other selection keystroke is sent to it

And no restart is authorized by that paste

## Scenario: An ordinary worker topic in the identical stalled-picker state is never pasted into

Given a tracked ORDINARY WORKER session whose derived row status is blocked:human

And whose live gate evidence shows an open structured picker

And whose pane capture has been unchanged past the bounded floor

When the daemon acts on that track

Then nothing is pasted into that pane

## Scenario: The charter reminder's own echo does not re-arm the once-per-episode bound

Given the stalled-picker preconditions are met and a reminder has been pasted

And the pasted text is visible in the subsequent pane capture

When the daemon observes that track again past the bounded floor

Then no second charter-reminder payload is pasted into that pane

And a later capture change not attributable to that paste re-arms the act

## Scenario: A human-waiting track on a stalled picker is published under a promoted status

Given a tracked session that is waiting on a human

And whose pane shows an open structured picker

When its pane capture has been unchanged past the bounded stall floor

Then its row publishes a picker-stall status rather than `blocked:human`

And the daemon continues to evaluate the track as `blocked:human`

And a consumer keyed on `blocked:human` alone does not observe the track as waiting on a human

And a consumer keyed on `picker_open` does observe it

And a consumer that must act on a human-waiting track handles the promoted row exactly as it handles a `blocked:human` row

## Scenario: A malformed mapping-store row is refused at write with its offending key named

Given a surface about to write a mapping-store row that does not satisfy the
durable-key contract

When the surface performs the write

Then the write is refused and the offending key is named

And the mapping store is left byte-unchanged

And no partially-corrected row is written in its place

## Scenario: A pre-existing non-conforming row does not block an unrelated store rewrite

Given a mapping store already holding one row that does not satisfy the
durable-key contract

And a maintenance path that rewrites the store without introducing or
changing that row

When the rewrite runs

Then the rewrite completes and the unrelated rows are written

And the non-conforming row is surfaced rather than silently rewritten or
silently dropped

And the rewrite is not refused on account of that row

## Scenario: A write that strips a recorded epic is refused though the resulting row would conform

Given a mapping-store row carrying a recorded ledger epic id

When a write would rewrite that row with its `epic` removed

Then the write is refused and `epic` is named as the offending key

And the mapping store is left byte-unchanged

And the refusal holds even though the resulting row, taken by itself,
satisfies the durable-key contract exactly as a never-assigned row does

## Scenario: A write that replaces a recorded epic with a different id is refused

Given a mapping-store row carrying a recorded ledger epic id

When a write would rewrite that row with a different value in `epic`

Then the write is refused and `epic` is named as the offending key

And the mapping store is left byte-unchanged

And the refusal does not depend on the replacement value being malformed

## Scenario: A read-time placeholder for an absent epic is never written back into the store

Given a mapping-store row with no recorded epic

And a reader that substitutes an in-memory placeholder so downstream code
has a value to carry

When a later write rewrites that row

Then the row is written with its epic still absent

And the placeholder does not appear in the stored row

And a row already carrying a persisted placeholder is treated exactly as a
row with no recorded epic

## Scenario: A killed session start leaves an attempted-and-failed record naming its invoker

Given an authorized unattended operator surface about to start a tracked
session

When the surface is killed after the spawn is issued and before it returns

Then a start-intent record written before the spawn is on file

And that record names the action, the target track, and the invoker

And the track is not left reading as live work on the strength of that record

And the absence of a session is distinguishable from a start that was never
attempted

## Scenario: A spawn that fails and returns has its start-intent record amended with the error

Given an authorized unattended operator surface that recorded a start-intent
before spawning a tracked session

When the spawn fails and the surface returns

Then the surface amends that intent record with the failure and its error

And the record is not left standing as though the attempt were still live

## Scenario: The stable account identifier is resolved even when the account manager names the profile

Given the account manager's own report names the active profile

And the operation therefore does not need its identity fallback

When a pass determines the active account

Then the operation also resolves that account's stable account identifier

## Scenario: A pass that switches publishes the newly selected account's identity

Given the operation is tracking several accounts

And the active account has crossed its rotation threshold

And a candidate account is eligible and live-verified

When a scheduled pass runs and switches onto that candidate

Then the published selection record names the candidate account by profile
name and stable account identifier

And the record carries the time at which it was written

And the record carries no credential material for any account

## Scenario: A pass that holds after a hand-run activation publishes the account it found active

Given the operation published account A on an earlier pass

And an operator has since activated account B by hand, outside the operation

When the next pass runs, finds account B active, and holds

Then the published selection record names account B

And the pass does not report the change as a rotation it performed

## Scenario: Republishing an unchanged identity is not reported as a change

Given the published selection record names account A

And no account has been activated since it was written

When a pass runs, finds account A still active, and holds

Then the published selection record still names account A

And the pass reports no change of selected account

## Scenario: The published record never influences a later pass's selection

Given the published selection record names account A

And account A is no longer the account the host is using

When a pass runs and evaluates rotation

Then the pass determines the active account without consulting the published
record

And the record affects neither eligibility, ranking, nor the decision to hold

## Scenario: An undetermined active account leaves the published record intact

Given the operation published account A on an earlier pass

And neither the account manager's report nor the stable-identifier fallback
can determine the active account

When a pass runs

Then the published selection record still names account A

And the pass reports that the active account could not be determined

## Scenario: An unresolvable stable identifier suppresses publication

Given the operation published account A on an earlier pass

And a pass determines that account B is active by profile name

And that pass cannot resolve account B's stable account identifier

When the pass runs

Then the published selection record still names account A

And the pass reports in its account table that the active account's identity
could not be fully resolved

And the pass does not exit non-zero on account of that condition

## Scenario: A pass that could not take the decision lock does not publish

Given the operation published account A on an earlier pass

And another caller holds the decision lock and is switching onto account B

When a pass runs and cannot take the lock

Then that pass holds without publishing

And the published selection record is left for the lock-holding caller to
write

## Scenario: An unreadable usage response does not suppress publication

Given a pass determined which account is active

And resolved that account's profile name and stable account identifier

And that account's usage response cannot be read

When the pass runs

Then the published selection record names the determined account

## Scenario: A failed publication fails the pass without undoing it

Given a pass has switched onto an eligible candidate

And the published selection record cannot be written

When the pass runs

Then the switch stands and the account table is reported

And the pass emits a clearly-marked failure line

And the pass exits non-zero

And selection publication retains the caam loop's last-writer-wins behavior outside its decision lock rather than inheriting the daemon state file's advisory-lock or warning-only fallback

## Scenario: Every supported harness exposes one lockstep caam operation

Given the repository ships the closed supported-harness set of Claude, Codex and namespaced Pi bindings while its livespec harness declaration covers only Claude and Codex plugin-resolution checks

When the caam-anthropic-loop manifests and operation bindings are inspected

Then every supported harness exposes exactly one visible caam-anthropic-loop operation

And the manifests declaring it are exactly the outer and nested Codex plugin manifests, whose name, version and description remain equal

And repository-root package.json advertises the namespaced Pi binding while its package version is excluded from operation-version lockstep

## Scenario: Provisioning writes a credential directly with no manager in the inference path

Given a factory run requests an eligible provider credential for its isolated target

When `llm-provider-manager` provisions the request successfully

Then the target contains one real selected credential

And no manager process proxies, relays or rewrites the inference request

## Scenario: The spread strategy assigns distinct accounts to simultaneous runs

Given two valid accounts satisfy the same provider, kind and purpose

And two consumer runs request credentials concurrently with the explicit spread strategy

When the manager provisions both requests

Then each run receives a valid credential for a different account

## Scenario: A reported authentication, rate-limit or provider-outage failure prevents reselection

Given a valid Anthropic credential was provisioned to a consumer run for purpose factory after rollout_started_at

And its record remains valid with the assignment value_generation equal to the current credential value_generation

And the proof record contains successful_consumer_dates

And any authentication report's occurred_at is not earlier than soak_started_at

When that consumer reports an authentication failure, rate limit or provider outage for the credential

Then the credential becomes suspect before another selection

And an authentication report makes it suspect immediately

And no such report permits reselection until successful revalidation returns it to valid

And the reporting run's lease is released before acknowledgement

And last_auth_failure_at is set and successful_consumer_dates is cleared for that authentication report

## Scenario: An exhausted credential pool fails closed without changing the target

Given no valid credential satisfies a provisioning request

And the isolated target already contains known bytes

When the manager evaluates the request

Then it returns a typed retryable-exhaustion result

And the target remains byte-identical

## Scenario: Browser acquisition keeps research and secret execution capabilities separate

Given a provider credential must be acquired through a browser

When the acquisition roles run

Then the research role can search the web and cannot access secrets

And the execution role controls headed installed Google Chrome through worker-private CDP pipe descriptors with an owner-only account-specific persistent profile beneath manager state and cannot search the web

And both roles run through the installed Claude CLI using only the effective user's protected interactive credential, which the manager never reads, stores, substitutes or passes in role context

And no provider account shares its persistent profile with another account

And local tools type and persist password and token values without placing them in either role's context

## Scenario: An incomplete proof record keeps the caam loop available

Given `llm-provider-manager` has recorded a non-null rollout_started_at from an Anthropic factory-purpose target commit

And injected proof evidence leaves any seven-day, simultaneous-spread, production-success or legacy-pool-absence condition incomplete

When a maintainer invokes llm-provider-manager proof-status

Then deprecation_ready is false and `caam-anthropic-loop` remains installed, runnable and responsible for interactive Anthropic rotation

And a missing real-consumer date breaks the earlier consecutive suffix

And an authentication failure at or after the soak start clears the dated soak without clearing the one-time proof fields

## Scenario: Proof status before rollout is uniformly false

Given `coexistence-proof.json` is absent or contains the exact initial object with null rollout_started_at

When a maintainer invokes llm-provider-manager proof-status

Then seven_day_complete, simultaneous_spread_complete, production_success_complete, legacy_pool_absence_complete and deprecation_ready are all false

And the command exits zero while `caam-anthropic-loop` remains installed, runnable and responsible for interactive Anthropic rotation

## Scenario: A same-day success starts a new soak after authentication failure

Given a qualifying production completion and a later authentication failure occur on one UTC date

When another qualifying production completion occurs later on that same UTC date

Then successful_consumer_dates contains that date as the first date of a new soak

And soak_started_at is the later completion time and is later than last_auth_failure_at

## Scenario: Successful provisioning returns a secret-free receipt

Given a valid credential satisfies a well-formed provisioning request

When the manager provisions it to the isolated target

Then the write to that target is atomic

And the receipt names the credential record, account, purpose and validation time equal to the authoritative pre-assignment reread's last_validated

And the receipt contains no secret bytes

## Scenario: Failed provisioning leaves an existing target byte-identical

Given an isolated target contains known bytes

And the target adapter write definitively fails before commit, reports uncommitted before its deadline and prepared-state cleanup persists

When the manager returns the failure

Then it returns a typed provisioning-failed result

And the target remains byte-identical

And it discards the preparation, releases the lease and performs no new selection or write in that invocation

## Scenario: An invalid provisioning request takes no lease and leaves the target unchanged

Given a provisioning request is missing a required field or its target adapter reports a reference that is mismatched, host-wide, or shared with another run

And the target contains known bytes

When the manager validates the request

Then it returns a typed invalid-request result

And it selects no credential and acquires no account lease

And the target remains byte-identical

## Scenario: The selection brain reads metadata but no secret value

Given the acquisition-secrets store contains the initial provider login and Gmail verification-mailbox authorization

And the provisionable-token store contains records

When the selection brain reads through its store capability

Then it can read provisionable metadata and choose a value_ref but cannot resolve its raw bytes

And it cannot read provider passwords or verification-mailbox authorization while only the provider observer and final provisioning adapter read token values at runtime

And the acquisition-reader grant can read only login and mailbox material while the separate acquisition-writer grant creates generations without reading an existing generation's fields or value, lists values-vault titles only to enumerate the namespace item and otherwise reads only that namespace item for validation

And the parent passes only a secret-free value_ref request to the final provisioning child, which resolves and writes raw bytes without returning them to the parent or selection brain

## Scenario: Lifecycle metadata writes use a field-limited capability

Given acquisition has atomically created or replaced a complete provisionable record with identity, value-reference, initial-status and last-validation fields

And lifecycle and selection have their declared store capabilities

When reacquisition launch, any acquisition terminal failure, revalidation or another status-only lifecycle event changes status or last-validation metadata

Then the selection brain cannot write the change

And the lifecycle writer can write only status and last_validated

And it cannot read acquisition secrets or raw tokens or change identity or value-reference fields

And the metadata write appends a secret-free audit entry

And only initial creation or terminal acquisition or reacquisition success uses the acquisition-token complete-record entry point that can publish generation fields

## Scenario: A malformed consumer failure report changes no credential state

Given a consumer failure report is missing a required field or names an unsupported classification

When the manager validates the report

Then it returns a typed invalid-report result

And no credential record changes

And the reporting run's lease remains held

## Scenario: An age-stale valid credential is revalidated before exhaustion

Given a credential's recorded status is valid

And its last validation is older than the configured maximum validation age

And no fresh eligible record matches the request

When the manager selects for a provisioning request

Then the manager transitions it to revalidating and runs provider-specific validation before returning exhaustion

And successful validation refreshes last_validated and permits the same request to provision it

And definitive credential rejection transitions it to dead and does not provision it

## Scenario: A token-store write invalidates cache and appends a secret-free audit entry

Given provisionable credential metadata is present in the bounded backend cache

And the append-only audit log already contains entries

When acquisition writes a replacement token record

Then the affected metadata cache entry is invalidated

And while holding the audit-log lock the manager validates the complete prior log and atomically replaces it with the exact prior bytes plus one canonical complete line

And that line uses its deterministic effect_id, one closed writer actor and operation secret-value-set or credential-conditional-set

And its record_id is a lowercase RFC 4122 UUID version 4

And the event-to-actor table makes the actor byte-identical whether the original worker or recovery resumes the effect

And a later reacquisition or revalidation of the same record generates a fresh operation_id and distinct audit effect_ids, while a crash retry of one operation retains its operation_id and recognizes only its own lines

And a crash exposes either the byte-identical prior log or that whole new entry, never a torn suffix

And neither artifact contains secret bytes

## Scenario: Account rotation publishes identity while credential management provisions separately

Given `caam-anthropic-loop` has published its selected account record

And `llm-provider-manager` has independently validated provisionable material

When a consumer requests a credential

Then the published account record remains limited to profile name, stable account identifier and write time

And the manager provisions from its provisionable-token store without treating that record as credential material

## Scenario: Consume-first selection preserves capacity reserved for another purpose

Given multiple valid accounts satisfy a factory-purpose request

And `account_reservations` reserves one account for the `interactive` purpose but not the factory purpose

When two non-overlapping factory runs use the default selection strategy

Then the manager provisions both runs from one eligible unreserved account before moving to another

And it does not consume the capacity reserved for the other purpose

## Scenario: The default empty reservation map reserves no account

Given no `account_reservations` value is configured

When a request is evaluated for any declared purpose

Then the manager uses an empty reservation map

And no otherwise eligible account is excluded by purpose reservation

## Scenario: Expired credential material becomes dead without revalidation

Given a valid, suspect or revalidating record has passed its expires_at time

When any command that passed pre-recovery validation performs the mandatory credential-expiry recovery step

Then the record becomes dead

And a live revalidation worker is first revoked, terminated and reconciled before the authoritative expiry reread, while the expired value is neither revalidated nor provisioned

And recovery does not apply expiry to acquiring, reacquiring or already dead records even when they retain an elapsed prior expires_at

## Scenario: A record invariant violation is refused or excluded

Given a canonical metadata envelope parses as a credential record whose exact version-1 member set, field types, immutable identity, lifecycle fields or generation-reference relation is invalid

When the store or manager validates that record

Then the invalid write is refused or the stored record is ineligible with a secret-free diagnostic

And another valid record can still satisfy the request

And an invalid item envelope, noncanonical or unparseable record value, or duplicate JSON member instead returns store-unavailable without resetting the item

## Scenario: Out-of-range validation worker and cache configuration fails before access

Given maximum validation age, provider probe timeout or backend-cache interval is non-positive or greater than five minutes, acquisition worker timeout is outside one minute through 24 hours, or acquisition step limit is outside one through 200

When a manager command loads configuration

Then it returns invalid-request with exit 2

And it does not access the acquisition-secrets store, provisionable-token store or provisioning target

## Scenario: Lease expiry restores account eligibility

Given a consumer crashes while holding a run-scoped account lease

When lease_seconds expires and another request selects

Then the manager treats the expired lease as absent

And the account is eligible for the new request

## Scenario: An out-of-range lease bound acquires no lease

Given a provisioning request sets lease_seconds below 60 or above 86400

When the manager validates the request

Then it returns invalid-request

And numeric range validation occurs with exact object-shape validation before mandatory recovery, so it does not recover an unrelated worker, validate a target, select a credential or acquire a lease

## Scenario: Conflicting completion evidence preserves proof and lease state

Given completion evidence was accepted for one consumer run and record

When the same identity is completed again with different fields

Then the manager returns invalid-request

And it changes neither the proof record nor any lease

## Scenario: Concurrent acquisition for one provider account is serialized

Given two acquisition actors attempt to replace the same provider account credential concurrently

When the second attempt contends on the per-provider-account lock

Then contenders may perform the read-only metadata identity lookup but only the lock holder writes the provisionable-token store or creates its complete record

And a direct contender returns its defined invalid-request or original active success while provision-triggered contention returns retryable-exhaustion without a worker

And no interleaved partial credential record is observable

## Scenario: A browser verification wall raises bounded operator attention

Given browser acquisition reaches a CAPTCHA or two-factor verification wall

And no operator-attention wait is configured

When the execution role cannot complete the wall autonomously

Then the shared acquisition worker writes the owner-only manager attention artifact with its operation_id and exact worker identity and waits only through its deadline

And creation, operator status update, worker removal and recovery removal each re-read and match the artifact operation_id against its owning write-ahead operation and the artifact worker_pid and worker_start_ticks against its worker record under the same attention-artifact lock, while recovery releases every lower-ranked lock it acquired itself before taking that lock, may retain an enclosing acquire command's already-held provider-account lock in declared order, and a worker releases the artifact lock before any give-up lifecycle transition

And the artifact's non-empty provider and account_id equal the owning credential record's immutable identity fields

And llm-provider-manager attention copies those identity fields unchanged while listing the artifact's path, record_id, reason and deadline even for asynchronous acquisition

And it waits until the earlier of the default ten-minute bounded interval and its worker deadline

And only an explicit local-operator --resolve changes pending status to resolved, browser observation alone never resolves it, and the worker then removes the resolved artifact and starts another execution invocation with the retained profile and remaining cumulative step budget

And a resolved artifact that reaches its deadline before that removal is removed without a lifecycle transition while its worker remains authorized

And a pending artifact's deadline expiry or a give-up removes the artifact, stores no new credential value and leaves the attempt dead

And when an unresolved artifact deadline passes strictly before the worker deadline, the still-authorized worker itself locks and identity-matches the artifact, removes it, destroys every capture, persists failed flow-unavailable, transitions the credential to dead and only then releases its provider-account lock

And it does not substitute bundled Chromium or a cloud-account browser extension

## Scenario: A live lease makes its account ineligible

Given an eligible account lease is already held for another consumer run

When a new provisioning request evaluates eligible accounts

Then the manager treats that account as ineligible and does not share the held assignment

And it retries selection against the remaining eligible accounts

And the held lease remains until its matching report, completion, explicit release or lease_seconds expiry

## Scenario: Lease-record transaction contention retries selection without blocking

Given an otherwise eligible account has no live lease

And another transaction transiently holds that account's lease-record lock

When a new provisioning request attempts lease-create

Then it uses LOCK_NB and does not wait or create a shared lease

And it retries selection against the remaining eligible accounts

And it excludes the contended account from normal selection, recovery-candidate revalidation and dead-record replacement for that invocation

And it tries each otherwise eligible account at most once and, after recovery-candidate handling and any required replacement launch, returns retryable-exhaustion with exit 3 while removing its still-empty pre-lease provision operation directly without entering cleanup when none remains

## Scenario: A changed authoritative record is abandoned before provisioning

Given selection chose a valid credential and holds its account lease

And the authoritative record changes or becomes ineligible before provisioning

When the manager performs its cache-bypassing pre-provisioning read

Then it does not invoke the target adapter with the stale value

And it abandons that record and retries selection

## Scenario: An unavailable provisionable-token store returns a typed failure without changing the target

Given a provisioning request names an isolated target containing known bytes

And the provisionable-token store backend is unavailable

When the manager evaluates the request

Then it returns a typed store-unavailable result

And the target remains byte-identical

## Scenario: Repeating one consumer failure report is idempotent

Given a consumer failure report has already changed its credential record

When the same run, credential, occurrence time and classification are reported again

Then the stored report marker makes the duplicate report return duplicate true without creating an operation

And it repeats no audit, credential, proof, marker, lease or tombstone effect

And every newly inserted marker is kept in canonical occurred_at order with classification-byte order as its tie-break

And it exposes no credential material

And that exact stored-marker check precedes interval validation, so a previously accepted report remains duplicate after its assignment closes

## Scenario: An authentication report invalidates its generation-safe process cache

Given one manager process cached a credential generation that a consumer run used

When a consumer reports an authentication failure for that credential

Then its value-generation compare-and-set makes the credential suspect

And that process evicts the matching entry before acknowledgement, while every other process must uncached-list the current logical revision title before an eligibility cache hit and therefore cannot reuse its older valid revision even though the value generation is unchanged

## Scenario: A cache failure falls back to the store without admitting an unvalidated credential

Given the bounded backend cache fails while a provisioning request is selecting a credential

And the authoritative provisionable-token store contains only a stale or otherwise unvalidated matching credential

When the manager retries the read through the provisionable-token store

Then it returns the store result instead of failing on the cache error

And it does not make the unvalidated credential eligible

## Scenario: The lifecycle table determines every credential state transition

Given a credential record is in one lifecycle state

When acquisition, validation, expiry, a classified report, revalidation, replacement or operator give-up occurs

Then its next state is exactly the state named for that event in the lifecycle table

And no unlisted event changes its lifecycle state

And a report whose assignment generation differs from the current credential generation does not satisfy either generation-qualified report event and leaves the replacement state unchanged

## Scenario: An inconclusive validation probe does not kill a credential

Given an acquiring or reacquiring credential is on its first or second consecutive validation attempt, or a revalidating credential is probed

When rate limiting, provider outage, transport failure or timeout makes validation inconclusive

Then acquiring remains acquiring and reacquiring remains reacquiring

And revalidating becomes suspect rather than dead

## Scenario: An unknown consumer report releases the lease without changing lifecycle state

Given a consumer run holds a lease for a valid credential

When it reports a failure classified as unknown

Then the credential remains valid

And the matching run lease is released

And the report does not synthesize or modify a provider health observation

## Scenario: The consumer wire protocol emits one typed secret-free result

Given a consumer invokes target, provision, report, complete or release with one version-1 JSON object, or a maintainer invokes argument-free proof-status

When the manager accepts or rejects the invocation

Then standard output contains exactly one single-line version-1 JSON result with the operation's defined fields

And its exit code matches the result type

And standard output and standard error contain no credential material

## Scenario: Manager state and provisioned targets enforce private permissions

Given the manager creates local stores, an audit log and an isolated provisioning target

When their filesystem permissions are inspected after a successful provision

Then manager files are mode 0600 beneath a mode-0700 state directory

And the target is owned by the manager's effective operating-system user with mode no broader than 0600

And every existing directory from the registered isolated_root through the target parent is non-symlinked, owned by that user and mode no broader than 0700

And every registered parent directory is no broader than 0700

And a pre-existing manager path with broader permissions is refused

## Scenario: Repeating one live provisioning request is idempotent

Given a consumer run has been provisioned and its account lease remains live

When the same logical request is submitted again with the same consumer-run identity

Then the manager returns the original secret-free receipt without another assignment

And reusing that identity with different request fields returns invalid-request

And that refusal precedes target validation, selection and lease acquisition and leaves the live assignment, receipt and lease unchanged

## Scenario: Unreadable or below-floor shared usage excludes an account

Given health_strategy is remaining-percent

And the matching provider-and-kind registry row declares a shared-usage observer

And a provider health adapter reports one account's shared usage as unreadable or below its configured floor

And another account is eligible for the same provider, kind and purpose

When the manager selects a credential

Then it does not select the unreadable or below-floor account

And it selects the other eligible account or returns retryable-exhaustion when none remains

## Scenario: The default health strategy performs no usage observation

Given manager configuration omits health_strategy

When the manager selects among lifecycle-eligible credentials

Then it uses health_strategy none

And it does not invoke a provider health adapter or exclude an account for health

## Scenario: Consume-first selects and replaces its incumbent deterministically

Given consume-first has no eligible unleased incumbent and multiple records are otherwise eligible

When consume-first selects a new incumbent

Then it selects the record with the lexically smallest record_id

And it moves from that incumbent when the incumbent becomes ineligible or leased

## Scenario: Spread selects the least recently assigned record deterministically

Given spread has multiple eligible unleased records

When spread selects a record

Then it selects the least recently assigned record and breaks equal assignment times by lexical record_id

## Scenario: Failed provisioning releases its account lease immediately

Given provisioning acquired a run-scoped account lease

And prepared-state cleanup persistence is available

When the target adapter returns provisioning-failed

Then the target remains byte-identical

And the lease is released before the failure returns

And the account is eligible for a following request

And while its issuance remains unexpired, the consumer_run_id remains reusable for an identical or corrected request

## Scenario: A domain provisioning failure leaves its run identity reusable

Given a valid target and credential reach provisioning before the target adapter commits

And prepared-state cleanup persists

When the manager returns retryable-exhaustion, store-unavailable or provisioning-failed

Then it creates no assignment tombstone and leaves the consumer_run_id unconsumed

And an identical or corrected request may use that identity again while its issuance remains unexpired

But expiry of the later-unbound issuance permanently retires that run identity and every later request returns invalid-request

## Scenario: Explicit lease release is idempotent

Given a consumer run holds an account lease

When the consumer releases that lease twice

Then the first release returns released true and makes the account eligible

And the second release returns released false without changing another lease

And if the first release crashes after lease-release, resuming its own apply operation still returns released true before a later tombstone-only release returns false

## Scenario: Secret-free completion evidence updates the coexistence proof

Given a production consumer holds a manager-provisioned Anthropic factory-purpose credential lease whose target_committed_at is at or after non-null rollout_started_at

And the one-time production and legacy-pool proof fields are null with no dated soak or authentication failure

When it completes with successful provider authentication, no alternate credential and legacy-pool absence

Then the manager records the completion's durable run-and-record marker, UTC date, production success and legacy-pool-absence success without a secret

And it releases the matching lease

And repeating identical completion evidence checks its exact stored completion before interval validation and is idempotent, while a retry after a later authentication report cleared the dated soak sees the retained marker and cannot recreate the cleared evidence

## Scenario: A classified report against a non-valid record has a defined effect

Given a provisioned credential is revalidating, suspect, dead or reacquiring

When its consumer reports authentication, rate-limit or provider-outage

Then a revalidating record becomes suspect and every other named state remains unchanged

And an unchanged suspect, dead or reacquiring state performs no credential-store adapter call, appends no paired audit line and evicts no cache entry

And the matching run lease is released before acknowledgement

And after mandatory recovery but before report-operation creation, a report against an acquiring record returns invalid-report without applying the value-generation mismatch rule or releasing a lease

## Scenario: An internal bug before a known target commit follows commit fencing

Given a provisioning request encounters an unexpected internal bug

And cleanup persistence remains available

When the target write has not begun or the manager queries its commit status under the target-reference lock

Then no-write or uncommitted status discards the preparation, releases the lease and returns internal-bug

And committed status follows post-commit recovery while in-progress or unavailable status preserves both preparation and lease for an identical retry

And the manager never releases a lease while leaving its prepared assignment behind

## Scenario: An internal bug after provisioning commit preserves retry recovery

Given a provisioning request encounters an unexpected internal bug

And the target adapter has already committed success

And the manager persisted its prepared assignment, receipt and lease before invoking the adapter

When the consumer retries the identical logical request

Then the assignment, secret-free receipt and lease remain recoverable

And the manager returns that receipt without another write or assignment

## Scenario: Overlapping spread receipts record the simultaneous proof

Given two committed Anthropic factory-purpose spread assignments have the same kind, distinct run and account identities, target commits at or after rollout_started_at, and lease intervals containing the later target_committed_at

And the coexistence proof record's simultaneous_spread is null

When the second provision succeeds

Then proof-update records both run identities, both account identities and the deterministic bounded interval

And the proof does not depend on either consumer being test or production class

## Scenario: A dash JSON path reads exactly one object from standard input

Given a manager command receives `-` as its JSON path

When exactly one valid UTF-8 JSON object arrives on standard input

Then the command processes that object

## Scenario: Malformed consumer JSON maps to its command-specific error

Given a manager command receives input with trailing non-whitespace, unknown fields or malformed JSON

When the manager parses that input

Then target, provision, complete and release return invalid-request

And report returns invalid-report

## Scenario: Omitted manager bounds use their contract defaults

Given a provisioning request omits lease_seconds

And manager configuration omits maximum validation age, backend-cache interval, provider probe timeout, external-call timeout, acquisition worker timeout, acquisition step limit, health strategy, health floor, browser attention wait, target adapters and secret-store backend

When the manager validates the request and configuration

Then lease_seconds is 21600

And maximum validation age is five minutes

And backend-cache interval is five minutes

And provider probe timeout is 30 seconds

And external-call timeout is 30 seconds

And acquisition worker timeout is two hours

And any configured acquisition worker timeout below three provider-probe intervals plus six external-call intervals plus three seconds is invalid-request before external access

And acquisition step limit is 50

And health strategy is none with floor 10, browser attention wait is ten minutes, enabled target adapters is isolated-run and secret-store backend is onepassword

## Scenario: Manager configuration and state use one invoker-independent home

Given operator and consumer invocations for the same effective user carry different HOME, XDG_CONFIG_HOME and XDG_STATE_HOME values

When a manager command resolves configuration and local state

Then it reads only the effective user's operating-system account-database home at .config/livespec-overseer/llm-provider-manager.json

And it uses only that account-database home at .local/state/livespec-overseer/llm-provider-manager as its mode-0700 state directory

And both invocations therefore share one operation, worker, lock, lease, assignment, attention, selection and proof namespace independently of those environment variables

## Scenario: Every supported harness exposes one lockstep manager operation

Given the repository ships the closed supported-harness set of Claude, Codex and namespaced Pi bindings while its livespec harness declaration covers only Claude and Codex plugin-resolution checks

When their plugin manifests and operation bindings are inspected

Then every supported harness exposes llm-provider-manager

And the declaring manifests are exactly the outer and nested Codex plugin manifests, whose name, version and description match, while repository-root package.json advertises the namespaced Pi path but its package version is excluded from operation-version lockstep

And package metadata declares the llm-provider-manager console entry point while consumer-host installation and PATH wiring remain that consumer's integration prerequisite

And a no-argument invocation requests no attention-status mutation while still allowing mandatory recovery, whereas the four unique non-empty flags --provider, --account-id, --kind and --purpose in any order run exactly the root's manager executable with `acquire --acquisition-json -` and stream the canonical five-member version-1 object to standard input without a temporary file or another argument

And a missing, empty, repeated, unknown or positional argument returns the exact common invalid-request JSON with exit 2 and named missing or offending fields, while executable JSON is otherwise presented verbatim with only secret-free explanation and its exit status is propagated unchanged

And each of the Claude, Codex and namespaced Pi bindings supplies a canonical absolute plugin root whose outer and nested manifest name, version and description match and whose three manager bindings and shared prose exist

And the operator invocation layer invokes only that root's absolute bin/llm-provider-manager, while an invalid manifest or unlaunchable plugin executable returns the common internal-bug object with exit 70 without searching consumer PATH

And each binding constructs only the attention list vector for zero arguments or the acquire --acquisition-json - vector for four valid pairs and cannot construct, forward or execute attention --resolve or attention --give-up

## Scenario: Backend and credential secrets remain outside every agent artifact

Given acquisition, validation and provisioning use the acquisition-secrets and provisionable-token stores with raw credential values

When agent contexts, operation output, logs, traces, browser screenshots and handoffs are inspected

Then no manager-store backend credential appears in any agent context

And no raw provider login or credential value appears in any inspected artifact

## Scenario: Manager backends and browser control run in the isolated interpreter

Given no third-party package is installed in the manager's interpreter

When llm-provider-manager exercises its acquisition-secrets store, provisionable-token store and CDP browser-control path

Then the installed wrapper imports only the necessarily executed overseer package initializer and its bootstrap before re-executing the manager companion with -I -S and its original arguments and standard streams

And the package console entry point loads the distribution built from the repository-root overseer implementation while the plugin bin entry point loads only the tracked .claude-plugin/overseer mirror and cannot import a separately installed overseer package

And every substantive path succeeds using only the standard library or its in-tree vendored exemption

And it does not import a third-party library from the installed environment

And failure to establish the isolated companion emits internal-bug with exit 70 before substantive mutation

## Scenario: An issued target reference cannot be reassigned

Given a target_ref is immutably bound to one consumer-run identity

When an adapter attempts to bind or use it for another run

Then the manager returns invalid-request before selection or lease acquisition

And the original binding and target bytes remain unchanged

## Scenario: A consumer obtains a run-bound target reference before provisioning

Given isolated-run is an enabled ProvisioningTarget adapter

And trusted local registration binds the consumer-run identity to a credential path beneath its isolated-run root

When a consumer submits a target request for its globally unique consumer_run_id

Then the manager returns an opaque target_ref and its expiry without credential material

And its issuance record binds that reference immutably to the requesting run for provisioning

And no destination path came from the target request

And the issuance record commits before the consumed registration is removed as resumable write-ahead effects

## Scenario: Concurrent target issuance refuses one shared destination

Given two consumer runs have valid isolated-run registrations whose canonical target_path identities are equal

When their target commands concurrently try to issue references

Then the destination-keyed lock serializes the cross-run scan through issuance-create commit

And exactly one run receives an issuance while the other returns invalid-request without an issuance or registration removal

And the losing run's unconsumed registration did not prevent the lock winner from creating that sole issuance

## Scenario: Concurrent writes to one target reference serialize

Given two provisioning attempts reach the same valid target_ref concurrently

When the ProvisioningTarget adapter writes them

Then their writes serialize for that reference

And the target contains one complete durable value rather than interleaved bytes

## Scenario: Process interruption preserves prior target bytes

Given an isolated target contains known bytes

And provisioning is interrupted during the adapter write

When the interrupted process terminates

Then the target remains byte-identical to its prior complete value

## Scenario: A provisioning request drives suspect and dead credential recovery

Given no eligible record exists and otherwise matching records are suspect or dead

When the manager evaluates a provisioning request before returning exhaustion

Then it revalidates suspect and age-stale valid records in the request strategy's candidate order until the first success or all have failed

And after no success it starts asynchronous serialized replacement for only the matching dead record with the lexically smallest record_id among those permitted by reservation and lease filters, without applying provider health to recovery candidates

And it returns retryable exhaustion immediately instead of waiting on browser acquisition

## Scenario: Non-qualifying completion evidence cannot advance coexistence proof

Given a completion is test-class, reports unsuccessful provider authentication, reports alternate credential use, belongs to a non-Anthropic or non-factory assignment, or has no recorded rollout start

When the manager accepts that completion and releases its lease

Then successful_consumer_dates remains unchanged

And production_success and legacy_pool_absence_success remain unchanged

## Scenario: Invalid purpose reservations fail before external access

Given account_reservations contains an empty purpose set, malformed entry, a multi-purpose account while health_strategy is none, or a multi-purpose provider whose registered credential kind declares shared-usage observation unsupported

When a manager command loads configuration

Then it returns invalid-request with exit 2

And it does not access the acquisition-secrets store, provisionable-token store or provisioning target

## Scenario: Unassigned consumer messages cannot mutate another assignment

Given a credential record is assigned to one consumer run

When another run or an unknown record identity reports, completes or releases that assignment

Then report returns invalid-report and completion or release returns invalid-request

And after completing mandatory run-scoped and global recovery, the refused message itself leaves credential, proof and lease state unchanged

## Scenario: A closed consumer run identity cannot be reused

Given a consumer run's assignment lease was released or expired

When a provisioning request reuses that consumer_run_id at any later time

Then the manager returns invalid-request

And it does not validate a target, select a credential or acquire a lease

And the initial manager retains the assignment tombstone and target binding indefinitely and performs no retention cleanup

## Scenario: Invalid manager configuration fails before every external access

Given an existing manager configuration is unreadable or non-UTF-8, is malformed JSON, repeats a member name, has an unknown key or version, has a wrong JSON type or malformed reservation shape, names an unsupported health strategy or SecretStore backend, has a health floor outside zero through one hundred, has a provider probe or external-call timeout outside one through 300 seconds, has an acquisition worker timeout outside 60 through 86400 seconds, has an acquisition step limit outside one through 200, has a browser attention wait outside one through 3600 seconds, or has an empty, duplicate or unknown target-adapter list

When any manager command loads that configuration

Then it returns invalid-request with exit 2

And it does not access a store, health adapter, acquisition browser or provisioning target

## Scenario: A health remainder equal to the configured floor stays eligible

Given health_strategy is remaining-percent with health_floor_percent 10

And the matching provider-and-kind registry row declares a shared-usage observer

And an otherwise eligible account's provider health adapter returns 10

When the manager selects a credential

Then the account remains eligible at the inclusive floor

## Scenario: Provider-observer access failure excludes only its candidate

Given remaining-percent selection evaluates one candidate whose registered row declares a shared-usage observer

When its key is absent, launch or values-vault access is refused, its result is malformed, or its deadline passes

Then the manager treats that observation as unavailable and makes only that candidate ineligible

And it exposes no secret or backend detail and continues evaluating other candidates rather than returning store-unavailable

## Scenario: A disabled target adapter cannot issue a reference

Given a ProvisioningTarget adapter is registered but omitted from enabled_target_adapters

And an unrelated stopped worker would require mandatory recovery if recovery were entered

When a target request names that adapter

Then the manager returns invalid-request before invoking the adapter

And it creates no issuance record

And it does not enter recovery or mutate the unrelated worker

## Scenario: Disabling a target adapter refuses fresh provision but preserves recovery

Given an issuance names a registered adapter that configuration later omits from enabled_target_adapters

When a fresh provision with no pending or retained run state uses that reference

Then the manager returns invalid-request before selection

But matching pending, prepared, committed or retained state keeps using the issuance-record adapter for recovery or replay

And an unavailable registered implementation returns store-unavailable without discarding, reissuing or reinterpreting that state

## Scenario: An absent or expired target reference is refused before selection

Given a provisioning request names a target_ref that was never issued or whose unassigned issuance reached or passed expires_at

When the manager validates the target reference

Then it returns invalid-request before selecting a credential or acquiring a lease

And no target bytes change

## Scenario: An out-of-order completion cannot rewrite the current soak

Given the proof record has a current consecutive soak and its soak_started_at

When a qualifying production completion arrives for an earlier UTC date

Then successful_consumer_dates and soak_started_at remain unchanged

## Scenario: A late authentication report before the soak does not clear it

Given a current soak began after the stored last_auth_failure_at

When an authentication report arrives whose occurred_at is later than the stored failure but earlier than soak_started_at

Then last_auth_failure_at advances to occurred_at and the current soak remains unchanged

And a still-earlier report cannot move last_auth_failure_at backward

## Scenario: Seven consecutive dates complete a soak with no authentication failure

Given rollout_started_at is non-null and last_auth_failure_at is null

And the proof record has seven consecutive successful_consumer_dates with a non-null soak_started_at

When a maintainer invokes llm-provider-manager proof-status

Then seven_day_complete is true and deprecation_ready reflects the other three proof Booleans

## Scenario: A well-formed purpose reservation filters only its account

Given account_reservations is {"anthropic":{"account-1":["factory"]}}

And health_strategy is none

And a matching provisionable record has provider anthropic and account_id account-1

When selection evaluates a factory request and an unrelated unreserved account

Then account-1 is eligible for the listed factory purpose

And the unrelated account remains unreserved

## Scenario: Purpose names do not restrict a registered credential kind

Given the initial anthropic claude-code-oauth row is registered

When otherwise valid acquire or provision inputs name factory, interactive or another non-empty purpose

Then provider-and-kind validation accepts each purpose identically

And interactive is only the exact reserved spelling for caam coexistence while matching and reservation policy still compare every purpose byte-for-byte

## Scenario: A completion before the latest authentication failure cannot start a soak

Given last_auth_failure_at is non-null and no dated soak exists

And the one-time production and legacy-pool proof fields are null

When a qualifying production completion arrives whose completed_at is not later than last_auth_failure_at

Then it sets production_success and sets legacy_pool_absence_success exactly when legacy_pool_absent is true

And it does not set successful_consumer_dates or soak_started_at

## Scenario: A completion on the next UTC date extends the soak

Given the current soak ends on one successful consumer date

When a qualifying production completion occurs on the next UTC date and after last_auth_failure_at

Then the manager appends that date and preserves soak_started_at

## Scenario: Another completion on the latest soak date is a dated no-op

Given the current soak already contains a successful consumer date

When another qualifying production completion occurs on that latest date and after last_auth_failure_at

Then successful_consumer_dates and soak_started_at remain unchanged

## Scenario: A nonconsecutive completion starts a new dated soak

Given the current soak's latest successful consumer date is more than one UTC day before a qualifying completion

And the completion occurs after last_auth_failure_at

When the manager records that completion

Then successful_consumer_dates contains only the completion's UTC date

And soak_started_at equals its completed_at

## Scenario: A required persistence failure is not acknowledged as success

Given a manager command requires an audit append, provisionable-token store mutation or atomic manager-local state transaction

When that required persistence fails before a provisioning target commits

Then the manager returns store-unavailable with exit 4 and does not acknowledge report, complete or release

And effects already committed retain their new values, every not-yet-committed effect retains its prior value for later resume, and target bytes remain unchanged before target commit

## Scenario: An ambiguous conditional metadata write is authoritatively reconciled

Given a credential-conditional-set adapter reaches its deadline after receiving the expected logical predecessor, desired replacement and effect_id for one append-only metadata revision

When the manager terminates and reaps that adapter process and rereads the complete revision chain without cache while holding the credential lock

Then the exact desired next revision carrying that effect_id completes the effect without another adapter call, while a different current logical record after an unknown outcome retains the fence and fails closed as store-unavailable

And before the physical create the manager persisted the exact pending metadata-effect fence, including the writer role matching that effect's semantic audit actor, so the exact predecessor proves only that the desired revision was not visible by that reread and every later writer returns store-unavailable or launches that recorded role to retry only the identical title and fields until the original or retry makes it authoritative

And a live worker with an unknown terminal-success metadata outcome retains its terminal phase and fence, retries only that byte-identical create until its deadline and then exits for special terminal-success pending-fence recovery without rewriting the phase while the fence remains

And a live worker with an unknown terminal-failure metadata outcome instead retains its original failure result, effects, actor and fence until its deadline, after which global recovery uses the fence's recorded writer role to reconcile only that byte-identical failure revision, removes the fence when it is authoritative and resumes worker removal without rewriting the terminal phase

And byte-identical physical duplicates collapse to one logical revision, so a late create cannot overwrite or outrank a later revision

And while the fence or owning worker operation exists the credential is ineligible, and a concurrent provision's locked authoritative reread abandons even an intermediate valid revision before value read or target action

And an unreconcilable fence quarantines only its record while global recovery continues in lexical record order, so an unrelated valid record can satisfy a command; a command bound to the quarantined record or a provision left only with matching quarantined candidates returns store-unavailable

## Scenario: A committed effect survives a missing completion marker without duplication

Given an ordered effect commits and the process stops before advancing completed_step

When an identical retry resumes that effect position under its required locks

Then the exact authoritative postcondition advances the marker without repeating the effect

And audit append finds its one matching effect identity and immutable semantic fields without adding a line despite the stored first-attempt time

And worker, lease, prepared-assignment and issuance creates recover their exact authoritative record and original derived fields rather than minting another

## Scenario: An unsafe isolated-run registration cannot issue a target

Given an isolated-run registration is missing, malformed, at or past expires_at, owned by another user, broadly accessible, symlinked, has a filename digest mismatching its consumer_run_id, names a path escaping its isolated root, has a missing, symlinked, wrongly owned or broadly accessible directory from isolated_root through the target parent, resolves through a symlink to the effective user's protected .claude/.credentials.json path, or conflicts with another run

When that consumer_run_id requests a target reference

Then the manager returns invalid-request with exit 2 and creates no issuance record

And no target bytes change

And issuance and target write compare the destination against the union of every registered credential-kind protected-path list, which initially contains exactly the effective user's protected .claude/.credentials.json

And an expired registration is removed without issuing a reference

And a well-formed registration written by any process with the manager effective user id is inside the declared local trust boundary

## Scenario: Retry discards an uncommitted prepared assignment

Given a process stops after persisting a prepared assignment and before the target adapter commits

When the identical logical request is retried

Then the manager queries adapter commit status, discards the uncommitted preparation and releases its lease

And it removes the completed cleanup operation, starts a new provision operation with newly captured accepted_at, returns no stored receipt, creates no tombstone and continues as a fresh request

## Scenario: Target commit evidence closes the atomic-replace crash window

Given the isolated-run adapter durably stored matching target-commit evidence before its atomic target replacement

When process loss leaves that evidence prepared or armed and an identical retry queries status under the target-reference lock

Then prepared evidence with null committed_at is removed as uncommitted because its final lease fence never committed

And armed evidence with an exact target hash and safe ownership is promoted to committed and returns its final lease-fence time, including when identical bytes pre-existed

And armed evidence with a mismatching target is removed and returns uncommitted without changing target bytes

And matching committed evidence returns committed while malformed or identity-mismatched evidence returns store-unavailable without mutation

## Scenario: An interrupted report resumes before duplicate acknowledgement

Given an authentication report's write-ahead record shows the credential became suspect but its lease, proof and duplicate-marker transaction did not commit

When the identical report is retried

Then the manager resumes the pending manager-local effects without repeating the lifecycle transition

And it does not return duplicate true until every required effect commits

## Scenario: Failed provisioning cleanup can hold only through recovery or expiry

Given a target adapter returns a pre-commit domain failure and prepared-state cleanup cannot persist

When the manager handles that cleanup failure

Then it returns store-unavailable and leaves the target byte-identical and the run identity unconsumed

And the lease remains held only until a later retry completes cleanup or lease_seconds expires

And cleanup after any committed start effect always includes lease-release, which completes as a no-op if another run already replaced the lease

## Scenario: A failed store mutation leaves its attempted audit evidence

Given the audit append for a provisionable-token store mutation succeeded and the following adapter call returned the definitive uncommitted result

When the manager applies that definitive result

Then the manager returns the effect's declared uncommitted outcome and credential state remains unchanged

And all prior audit entries and the new attempted-operation entry remain append-only and secret-free

## Scenario: Post-commit retry completes simultaneous-spread proof

Given a second overlapping spread target committed but its proof-update did not persist

And the manager returned internal-bug with exit 70 while preserving the prepared assignment, receipt and lease

And the coexistence proof record's simultaneous_spread is null

And rollout_started_at already satisfies its own minimum

When the consumer retries the identical provisioning request

Then the manager writes no target and performs no selection

And it idempotently commits simultaneous_spread before returning the stored receipt

And neither proof contribution alone contains the effect because rollout and simultaneous-spread proof are conjunctive

## Scenario: A late report for a replaced value does not suspect the replacement

Given an Anthropic factory-purpose committed assignment after rollout start used an earlier value_generation and value_ref and the record now has a different valid value_generation and value_ref

When that run reports authentication, rate-limit or provider-outage

Then the manager accepts the report and releases the lease without changing or invalidating the replacement credential

And an authentication report still applies its event-time proof effect

## Scenario: A concurrent retry cannot discard an in-flight target write

Given an identical provisioning retry arrives while the target adapter holds its per-reference write lock

When the retry queries commit status

Then the adapter reports in-progress and the manager returns retryable-exhaustion

And it preserves the prepared assignment and lease until the original write reaches a terminal status

And the same preservation and identical-retry requirement applies if the final-provisioning write call itself returns the conforming in-progress shape

## Scenario: An uncommitted or nonoverlapping peer cannot satisfy spread proof

Given proof-update can observe a peer that is uncommitted or whose retained lease interval excludes the later target_committed_at

When the manager derives eligible simultaneous-spread peers during success or retry

Then it does not set simultaneous_spread from that peer

And after any required Anthropic factory rollout-start update, the pair portion of proof-update completes as a no-op for this case, for consume-first, or after simultaneous_spread is already set

## Scenario: Report retry compares against a replaced value again

Given a report write-ahead record exists and its assignment value_generation initially matched

And acquisition replaces that value generation before the lifecycle transition commits

When the identical report resumes

Then its conditional lifecycle effect becomes a completed no-op and the replacement remains valid

And the lease and any authentication proof effect still commit

## Scenario: A crashed revalidation returns the record to suspect

Given a record is revalidating and its worker record identifies a worker that is no longer live

When an ordinary provision command begins

Then it returns the record to suspect before selection and can revalidate it again

And an explicit operator acquire may retain that suspect record_id and start its internal reacquisition, while automatic provision-triggered replacement remains limited to dead records

## Scenario: A crashed acquisition becomes dead and clears stale attention

Given an acquiring or reacquiring record has a stopped worker, a past worker deadline, or a still-pending attention artifact past its own deadline

When an ordinary provision command begins

Then it makes the record dead and removes its pending attention artifact before selection

## Scenario: Revalidation skips leased or reserved-away accounts

Given suspect records are leased or reserved away from the requested purpose

When no fresh eligible record satisfies a provisioning request

Then the manager does not revalidate those excluded records while health remains irrelevant until final selection

## Scenario: Concurrent requests serialize revalidation of one record

Given two provisioning requests reach the same eligible suspect record concurrently

When both attempt request-time recovery

Then only one provider validation for that record runs at a time

## Scenario: A concurrent report defeats a revalidation success

Given request-time revalidation receives a successful provider response

And a consumer report has moved the record from revalidating to suspect

And a later filtered candidate can validate successfully

When the manager performs its authoritative post-validation reread

Then the defeated success does not make the first record eligible

And the manager continues to the later candidate and provisions it after its authoritative reread passes

## Scenario: Initial acquisition creates an audited immutable identity

Given no record has the requested provider, account_id, kind and purpose

When an operator invokes acquire with those four identity fields

Then after mandatory recovery and every pre-creation prerequisite it captures accepted_at immediately before operation persistence

And the manager generates a unique lowercase UUIDv4 record_id, spawns its worker held and persists the complete worker record

And it appends the attempted-operation audit entry, atomically creates the acquiring record with acquired_at equal to accepted_at and null expiry and value references, releases the worker and returns a secret-free acquiring result

## Scenario: Spread orders a never-assigned record before assigned records

Given eligible spread candidates include a record with no retained assignment time and records with assignment times

When spread selects a record

Then it selects the never-assigned record and breaks ties between never-assigned records by lexical record_id

## Scenario: Target commit persists selection ordering state

Given a provisioning target commits successfully

When the manager updates selection-state

Then it atomically advances the assignment time and applicable consume-first incumbent only when that commit's deterministic timestamp tuple is later

And delayed post-commit recovery cannot regress either value

## Scenario: A corrected request cannot overwrite pending provisioning state

Given a consumer_run_id has a pending provisioning operation or prepared assignment

When a non-identical corrected request reuses that identity before identical-request cleanup

Then the manager returns invalid-request before target validation, selection or lease acquisition

And it leaves the pending operation, preparation and lease unchanged even after lease expiry

## Scenario: Expired post-commit recovery preserves effects without returning a receipt

Given a target committed and post-commit effects remain pending after its assignment lease expired

When the identical provisioning request retries

Then the manager applies every pending effect, closes the assignment and creates its tombstone

And it returns invalid-request saying the committed target credential must not be used, without a success receipt

## Scenario: A target write cannot commit after its account lease expires

Given a target adapter has staged its replacement while the account lease remains live

When its mandatory manager-time sample immediately before atomic target replacement is at or after lease_expires_at

Then it leaves prior target bytes unchanged and reports uncommitted

And other selection reads treat the expired lease as absent

And a timed-out final-provisioning child may commit only if it entered the evidence-and-target critical sequence by the original composite call deadline

And after timely entry it must finish and release the target-reference lock no later than that deadline plus one external-call interval

And a timed-out or parent-orphaned final provisioning child retains the target-reference lock only until terminal exit no later than its two-interval composite deadline plus one external_call_timeout_seconds, so an earlier retry observes in-progress without overtaking it and a later retry cannot remain pinned indefinitely

## Scenario: Syntactically rejected input does not trigger unrelated worker recovery

Given an unrelated credential has a worker that is no longer live

When an invocation fails configuration, flag, JSON shape, field-type, an object-validation numeric range such as lease_seconds, consumer-message record_id lowercase UUIDv4 spelling, canonical timestamp spelling or other pre-recovery validation

Then the invocation returns its defined invalid result before worker recovery

And the rejected invocation changes no credential, proof or lease state

And an assignment-mismatched invocation, reused provision state or tombstone, invalid target reference or duplicate acquire identity other than the explicit matching-authorized-worker retry first completes every mandatory recovery, then returns its defined invalid result with no further request-attributable mutation

## Scenario: Process identifier reuse cannot impersonate a stopped worker

Given an acquisition or revalidation worker record names a worker_pid whose stored worker_start_ticks differ from proc field 22

When an ordinary provision command performs pre-operation recovery

Then it treats that worker as stopped and applies the lifecycle interruption transition

## Scenario: Concurrent recovery cannot kill a starting acquisition

Given acquire has spawned a held worker and persisted its complete worker record

And its launcher has held the provider-account launch serialization continuously since before persisting the launch operation

When another valid manager command performs recovery as the acquiring record becomes visible

Then recovery cannot acquire that launch serialization, leaves the operation and worker record unchanged and does not transition the new record to dead

And the acquire command releases the worker only after both records commit

And a revalidation launcher provides the same interlock with its credential-record serialization from before operation persistence through lifecycle commit and worker release

## Scenario: Acquire refuses an existing credential identity

Given a credential record already has one provider, account_id, kind and purpose tuple with no matching pending acquire operation

When acquire requests the same four identity fields

Then it returns invalid-request with exit 2 and creates no record or worker

And the existing record remains unchanged and replacement stays on the lifecycle path

## Scenario: Malformed acquisition input starts no worker

Given acquisition JSON is malformed, has trailing input, omits an identity field or supplies an extra record_id

When the acquire command validates it

Then it returns invalid-request with exit 2 before store or worker access

## Scenario: A late acquisition worker cannot revive a recovered record

Given an acquiring worker resolves a provider flow as its attention deadline passes

When recovery revokes the matching worker record and moves the credential to dead

Then the late worker's authorization precheck or terminal metadata compare-and-set fails

And it cannot move the dead credential to valid; a revocation racing after a successful precheck may leave only an unreferenced immutable generation item that no metadata record publishes

## Scenario: A launcher death before release leaves no provider action

Given acquire has persisted a held worker record and an acquiring lifecycle record

When the launcher dies before releasing the worker

Then the held worker exits without provider or store action

And a later valid command removes the stopped worker record and moves the acquiring credential to dead

## Scenario: Failed operation startup retains the required worker fence

Given an operation has spawned its worker held

When worker-record persistence or lifecycle audit append prevents the conditional lifecycle mutation, or lifecycle persistence is definitively uncommitted

Then the command returns store-unavailable with exit 4

And it terminates the held worker, removes any orphan worker record and exposes no new active lifecycle state

But when lifecycle persistence instead has an unknown outcome

Then the manager keeps the worker held, revokes its worker record, terminates and reaps its process group, retains that safety record and the owning launch operation, and returns store-unavailable

And a retry or recovery that finds the existing fence reconciles or repeats only the byte-identical conditional-set, removes the fence only after its desired revision is authoritative, and otherwise retains the fence on uncommitted, condition-failed or a different revision

And a direct definitive launch condition-failed revokes and reaps the held worker, removes its worker and launch-operation records, leaves the credential unchanged, and returns direct acquire invalid-request, counts revalidation as a non-success, or leaves provision-triggered replacement at retryable exhaustion

And a different authoritative revision after an unknown launch outcome instead retains the revoked worker, operation and pending-effect fence and returns store-unavailable

## Scenario: Recovery cleans a worker record left after lifecycle completion

Given a worker committed its value and non-active lifecycle transition but crashed before removing its owning operation and worker records

And its terminal credential-conditional-set was marked complete or no pending metadata-effect fence remains

When a valid manager command performs pre-operation recovery

Then it advances the authoritative terminal effect without another adapter call, removes the worker record and removes that operation

And it preserves the committed credential lifecycle and value so a fresh operation for that record may start

## Scenario: An orphan record for a held worker cannot block a later launch

Given a launcher died after persisting a worker record but before creating or transitioning its credential

When a later operation proves the recorded worker is not live

Then recovery removes the record without a lifecycle transition

And a new held worker may atomically install its complete record at that path

## Scenario: Concurrent duplicate acquisition is refused atomically

Given two acquire commands request one provider, account_id, kind and purpose tuple concurrently

When the second contends after the matching worker's initial active lifecycle transition is authoritative, whether the worker is still held or has been released

Then exactly one compare-and-creates an acquiring record and worker

And matching-authorized-worker contention returns the original acquiring success before host preflight, prerequisite checking or a Chrome probe and without recovery or mutation, while every other initial contention first runs global worker recovery and retries the lock once before any invalid-request refusal, without creating either record or worker

And contention before the active lifecycle transition uses that ordinary recovery-and-retry branch rather than returning an active success that does not yet exist

## Scenario: Inconclusive acquisition validation has a fixed bound

Given an acquisition or reacquisition worker receives only inconclusive provider validation outcomes

When the browser-control service's acquisition-validator performs its validation loop while retaining the capture

Then it makes exactly three attempts separated by one-second and two-second waits

And it returns no intermediate result, returns inconclusive only after the third attempt, destroys the capture and moves the credential to dead

## Scenario: Corrected target input proceeds after validation refusal

Given a provisioning request has an absent, expired or mismatched target_ref

When the manager refuses it and the consumer retries with a valid corrected target_ref

Then the refusal left no provisioning operation record, prepared assignment or lease

And the corrected request may proceed through selection and provisioning

## Scenario: Missing manager-local records have exact initial state

Given selection-state.json and coexistence-proof.json are absent on first use

When a valid manager command reads them

Then selection state is version 1 with empty incumbents and last_assignments

And populated incumbent and last-assignment arrays accept only their exact entry members and persist in their declared lexical key order

And coexistence proof is version 1 with rollout_started_at and every evidence field null plus empty date and completion-marker lists

And absent issuance, target-commit evidence, lease, assignment, tombstone, operation and pending metadata-effect fence files mean those entities do not exist while an absent audit file means empty history

And a prepared assignment has null target_committed_at, actual_lease_ended_at and completion fields with empty report markers, while a committed assignment has non-null target_committed_at and preserves the schema's declared completion relationships

And any assignment violating those status-dependent relationships is malformed and causes store-unavailable

## Scenario: Unsafe manager-local records fail closed without reset

Given any manager-local record other than a run registration or worker record is malformed, non-regular, symlinked, incorrectly owned or more broadly accessible

When a manager command needs that record

Then it returns store-unavailable with exit 4

And it neither resets nor mutates the unsafe path

And an unsafe run registration instead follows its typed invalid-request refusal while an unsafe worker record is treated as not live and follows fenced recovery

## Scenario: Attention output is exact and path-sorted

Given multiple pending browser-verification artifacts exist under the manager state directory

When llm-provider-manager attention reads them

Then each item contains exactly path, record_id, provider, account_id, reason and deadline

And the items are sorted by path

## Scenario: Unreadable attention state returns a typed failure

Given the manager cannot read its attention state

When llm-provider-manager attention runs

Then it emits the common store-unavailable object and exits 4

## Scenario: Invalid attention update cannot revive or mutate an attempt

Given an attention artifact is no longer pending while its worker remains authorized and current time is before both deadlines

When a local operator invokes attention --resolve or attention --give-up for that record_id

Then the manager returns the common invalid-request object with exit 2

And it leaves the artifact and credential byte-identical without reviving the acquisition attempt

And if instead the worker is unauthorized, current time is at the worker deadline, or the artifact remains pending at its own deadline, mandatory recovery first fences the worker, moves the credential to dead and removes the artifact, after which the requested update returns invalid-request with no further mutation

And a resolved artifact at its own deadline with an authorized worker is removed without a lifecycle transition before the requested update returns invalid-request

And a resolve or give-up argument that is not a lowercase UUIDv4 returns invalid-request before recovery and changes no state

## Scenario: Manager invocation failures use the closed error mapping

Given a manager invocation has no subcommand, an unknown subcommand, invalid flag cardinality, unexpected argument or unreadable or non-UTF-8 input

When the executable classifies the failure

Then a recognized report emits invalid-report with exit 2 and every other invocation emits invalid-request with exit 2

And no command emits an error_type or exit outside its declared closed set

And invalid configuration, flags or input return that typed result before the manager resolves the configured SecretStore executable

And after report is recognized, flag cardinality precedes configuration and configuration precedes input decoding, so bad report flags plus bad configuration returns invalid-report while valid flags plus bad configuration and malformed input returns invalid-request

## Scenario: The coexistence proof schema retains its first qualifying evidence

Given coexistence-proof.json is owner-only and has the exact version 1 initial shape

When qualifying Anthropic factory-purpose spread and production events after the first committed target populate its nullable fields

Then rollout_started_at is the earliest qualifying target_committed_at and every successful_consumer_dates entry is an RFC 3339 UTC full date in YYYY-MM-DD form compared with the UTC calendar date of rollout_started_at

And a first qualifying completion later on the same UTC calendar date as rollout_started_at produces a valid first soak date even though that date's midnight precedes the rollout timestamp

And every qualifying completion contributes one retained marker containing exactly consumer_run_id, record_id and completed_at in canonical order

And simultaneous_spread records the two distinct run and account identities and the exact bounded overlap interval

And production_success and legacy_pool_absence_success each record exactly consumer_run_id and completed_at

And later qualifying events do not replace any one-time proof field

And a later backward wall-clock step does not make the already accepted proof record malformed

## Scenario: A worker spawn failure is an internal bug

Given acquire has passed input, duplicate and lock validation

When spawning its held worker fails

Then it returns internal-bug with exit 70

And it creates no worker record or acquiring credential

## Scenario: Account acquisition serialization lasts through worker completion

Given one acquisition worker holds the per-provider-account lock

When acquire requests a different kind or purpose on that account and provision requests replacement on that account

Then acquire returns invalid-request with exit 2 and creates no record or worker

And provision returns retryable-exhaustion and starts no replacement worker

And the lock remains held until the original worker's terminal lifecycle commit and worker-record removal

## Scenario: Account-lock acquisition rescans a worker lost after global recovery

Given provision completed global recovery and an acquisition worker for the selected provider account dies before provision acquires that account's lock for replacement

When provision acquires the now-released provider-account lock

Then it rescans and terminally reconciles every fenced or lost acquisition or reacquisition worker record for that account under the same hold before spawning or transferring the lock to a replacement worker

And a live conflicting worker or failed reconciliation starts no replacement and returns the applicable typed contention or recovery failure, so the stale record cannot wedge unrelated later commands behind the new worker

## Scenario: Stale attention for a non-active credential is only removed

Given a browser-verification attention artifact remains after its credential reached valid or dead

When a valid manager command performs recovery

Then it removes only the stale attention artifact

And it does not change the credential lifecycle or value

## Scenario: Unconfirmed worker termination stops command recovery

Given recovery revoked a live worker record but cannot confirm that worker terminated

When the command reaches its recovery boundary

Then it returns store-unavailable with exit 4 before its substantive operation

And it leaves the credential active while the revoked fence prevents the worker from committing

## Scenario: Explicit provisioning defaults are identical on retry

Given a provisioning operation was created from a request omitting strategy and lease_seconds

When the same consumer retries with strategy consume-first and lease_seconds 21600 explicitly present

Then the normalized requests are identical

And the retry resumes the pending operation rather than returning invalid-request

## Scenario: Manager-local transaction records use exact versioned shapes

Given the manager persists issuance, lease, assignment, tombstone, write-ahead and audit state

When each record is read back through its deterministic identity-derived path

Then it contains exactly its declared version 1 fields and value types

And every operation key matches its command-specific length-prefixed digest

And repeated effect names are tracked by positional completed_step while an atomic phase change installs the next complete effect plan

And an unexpected field or invalid value makes the record fail closed as store-unavailable

## Scenario: A report after lease expiry uses retained assignment evidence

Given an expired committed assignment has been closed into a tombstone retaining its value_ref

And a consumer failure occurred between target_committed_at and actual_lease_ended_at

When the matching report arrives during tombstone retention

Then the manager compares the retained value_generation, applies the lifecycle and proof effects and records the report marker

And it performs no lease-release effect and an identical report is duplicate

## Scenario: Lease release deletes the live lease record

Given a committed assignment has a live lease record

When completion, report, explicit release or expiry ends the lease

Then the manager atomically deletes the lease record

And the assignment or tombstone retains the actual lease-end time while selection treats the account as unleased

And a late close for that assignment cannot delete a newer live lease naming another run or record

## Scenario: A conflicting completion cannot pass pending completion state

Given a completion operation for one run and record committed proof effects but not its completion marker

When a completion with different evidence fields arrives concurrently

Then per-run serialization finds the same run-and-record operation key

And it resumes the first completion through completion, lease and tombstone effects

And it then returns invalid-request for the conflicting evidence without any further mutation

## Scenario: A live mismatched revalidation worker does not block later candidates

Given a report moved a revalidating record to suspect while its prior worker is still live

And a later lexical candidate can validate successfully

When provision performs synchronous candidate recovery

Then it counts the blocked launch as a non-success without waiting or starting another worker

And it continues to and provisions the later candidate

And after the mismatched worker ends, recovery treats its terminal metadata and paired audit positions as completed no-ops, removes its worker and operation, and does not change the suspect credential or wedge later commands

## Scenario: Provider probe timeout bounds synchronous revalidation

Given a provider validation probe remains unresponsive beyond provider_probe_timeout_seconds

When provision synchronously revalidates the record

Then the probe stops at the configured deadline and produces an inconclusive timeout

And the revalidation role input carries both timeout values and its worker deadline, so the provider-observer value read has its own external-call interval before the separate provider-probe interval and the composite deadline preserves the final three worker intervals

And the parent role deadline equals the earlier of role-launch time plus external_call_timeout_seconds plus provider_probe_timeout_seconds and worker_deadline minus three external-call intervals

And its recorded worker deadline reserves six external-call intervals around the independent probe budget, while the probe itself leaves three final intervals for the terminal credential-lock wait, audit-lock wait and conditional metadata publication

And the worker cannot commit at or after its later recorded worker deadline

And recovery fences a still-running revalidation worker, moves the credential to suspect and does not block indefinitely

## Scenario: Acquire retry recognizes its own live worker by credential identity

Given acquire made the initial acquiring lifecycle transition visible for one provider, account_id, kind and purpose, released its worker and its response was not observed

When the identical acquisition input retries while that authorized worker holds the provider-account lock

Then it resolves the same length-prefixed identity key and recognizes that its matching worker owns the lock

And it returns the original acquiring success without recovery, mutation or a duplicate record

## Scenario: Target retry returns its existing issuance

Given target created an unexpired issuance and removed its consumed registration before the response was observed

When the same run and adapter retry the target request

Then the manager returns the original target_ref and expiry without requiring the registration

And a different adapter for that run returns invalid-request without mutation

And after mandatory recovery a run with a nonterminal provision operation, prepared assignment, committed assignment or retained tombstone returns invalid-request without an adapter call or returning its old target_ref, even when its issuance has not expired

## Scenario: An expired unbound target issuance is retained and never reissued

Given target created an issuance with no matching nonterminal provision operation, prepared assignment, committed assignment or retained tombstone when its expires_at arrived

When the same run requests a target again with the same or a different adapter and may have a later registration

Then the manager returns invalid-request without invoking an adapter or mutating state

And it retains the expired issuance as the run's non-reissuable identity record and never returns a replacement reference

## Scenario: Fenced acquisition cleanup survives account-lock contention

Given recovery revoked an acquisition worker and confirmed that its process ended

And another acquisition already holds that provider account's lock

When recovery tries that lock non-blockingly

Then it returns store-unavailable while leaving the credential active and worker record revoked

And the command holding the lock completes the terminal transition and worker-record cleanup before evaluating its new acquisition

## Scenario: Tombstone-first close survives an assignment-removal crash

Given report, completion or release created a tombstone and crashed before removing the assignment

When provision checks that consumer_run_id or the original command retries

Then the tombstone is authoritative and provision refuses reuse

And the retry removes the redundant assignment without losing report, completion or target-binding evidence

## Scenario: Out-of-interval consumer evidence is refused without proof mutation

Given a canonical report or completion time is before target_committed_at, later than the manager clock, later than a live assignment's lease_expires_at or later than a retained actual_lease_ended_at

And the run has no pending lifecycle operation or expired committed assignment requiring prior recovery and no global worker, credential-expiry or stale-attention recovery effect is required

When the manager validates that evidence

Then report returns invalid-report and completion returns invalid-request

And credential, proof, assignment, tombstone and lease state remain unchanged

And if any run-scoped or global mandatory recovery is required, the manager finishes all of it first, checks the evidence against the resulting authoritative state and makes no mutation attributable to the refused evidence

## Scenario: A matching live revalidation worker is awaited only to its deadline

Given a filtered candidate already has a live matching revalidation worker

When another provisioning request reaches that candidate

Then the matching record remains a recovery candidate despite its one nonterminal revalidate operation, while a pending metadata-effect fence or acquire, reacquire or mismatched revalidate operation excludes a record

And it releases every lock needed by the worker and waits no later than the worker's recorded deadline

And it reacquires locks in contract order and performs the authoritative reread

And it uses only a valid result with the worker-written last_validated and unchanged value_generation or otherwise continues to the next candidate

## Scenario: Completion after lease end uses the retained tombstone

Given a retained tombstone has null completion and a qualifying completion occurred within its target-commit and actual-lease-end interval

When that completion arrives after expiry or explicit release

Then the manager updates completion and proof state without a lease effect

And an identical repeat returns duplicate true while conflicting evidence returns invalid-request without mutation

## Scenario: A pending close is resumed before another run command

Given report, completion, release or expiration left one nonterminal run-lifecycle operation for a consumer_run_id

When another report, complete, release or provision command for that run passes syntax validation

Then it resumes the stored operation to its tombstone before evaluating the new command

And more than one pending run-lifecycle operation returns store-unavailable without choosing between them

And any command resumes a pending target issue or provision cleanup or postcommit before expiration, while provision start remains untouched through global metadata-fence, worker, credential-expiry and attention recovery; only the identical provision request then resumes that start and another command returns its invalid input result without creating an expire operation

## Scenario: Retried close keeps its original acceptance time

Given report, completion or release persisted accepted_at and was interrupted during its run-lifecycle operation

When the same or another run command resumes it at a later manager time

Then the tombstone uses the latest of lease_started_at, target_committed_at and the earlier of original accepted_at and lease_expires_at for actual_lease_ended_at, and uses original accepted_at for closed_at

And it does not extend the assignment interval to the retry time

And a backward wall-clock step may make closed_at precede actual_lease_ended_at but cannot make the retained lease interval begin after it ends or end before target commit

## Scenario: Selection history and tombstones remain retained

Given an assignment closes while its credential record and selection history remain

When any later manager command evaluates retained state

Then the tombstone and target binding remain present and the credential's last assignment time remains in selection-state

And spread continues to order it by that retained time

## Scenario: Dead credential records and values remain retained

Given a dead credential has no assignment, tombstone, worker or operation reference

When any later manager command evaluates manager state

Then it does not delete the credential metadata or any values-vault generation

And its immutable identity remains available for operator reacquisition

## Scenario: Shared selection and proof updates cannot lose concurrent evidence

Given two runs concurrently update selection-state or coexistence-proof

When each performs its read-modify-write

Then the named exclusive global lock serializes their atomic replacements

And both incumbents, assignment times, completion markers, soak dates and first-writer proof evidence are preserved

## Scenario: Expired assignment closure is resumable and identity-safe

Given a committed assignment has expired and its account lease path may now name a newer run

When a valid run command creates or resumes the internal expiration operation

Then it conditionally releases only the stale matching lease, creates the tombstone and removes the assignment in order

And the requested command reevaluates the tombstone while any newer run's lease remains live

## Scenario: A pre-lifecycle launcher crash discards its launch plan

Given acquire, reacquire or revalidate persisted its launch operation either before worker-record-create or with a worker record but not its initial lifecycle transition

When the launcher dies, its held worker exits if one exists, and a later valid command performs global recovery

Then recovery enumerates the launch operation even without a worker record, acquires its provider-account or credential-record launch serialization and removes it plus any orphan worker record without changing credential state

And a concurrent recovery that cannot acquire that serialization leaves the pre-worker-record window untouched and continues with other records

And a later invocation creates a fresh launch plan instead of resuming after worker-record-create

And that plan has a new operation_id whose audit effect_ids cannot collide with the abandoned plan's retained audit lines

And a synchronous-revalidation spawn failure removes the empty launch operation, counts that candidate as a non-success and continues, while a provision-triggered reacquire spawn failure removes it and returns retryable-exhaustion

## Scenario: Acquisition worker deadline releases a stuck provider account

Given an acquisition or reacquisition worker remains live without raising browser attention

When current time reaches its started_at plus acquisition_worker_timeout_seconds

Then recovery fences it, moves the credential to dead and removes its worker and operation records

And the provider-account lock becomes available for later replacement

## Scenario: Prepared-only assignments reject consumer lifecycle commands

Given a target has not committed and its assignment remains prepared with a live lease

When report, completion and release each name that run and record

Then report returns invalid-report and completion and release return invalid-request

And the prepared assignment, lease and credential state remain byte-identical

## Scenario: Authoritative reread abandonment restarts provision durably

Given provision acquired a lease and prepared an assignment before the authoritative record changed

When its cache-bypassing reread detects the change

Then it first replaces the in-process metadata cache entry with the authoritative record or evicts it even when the generation is unchanged

And it enters cleanup, discards the preparation and conditionally releases the lease

And after removing that operation it creates a fresh provision operation and retries selection without changing the target

## Scenario: A crashed provision with a lost pre-assignment lease restarts selection

Given provision committed lease-create and crashed before prepared-assignment-create

And on its identical retry that lease is expired, absent or belongs to another run

And the issuance remains matching and unexpired and its adapter remains enabled

When the retry resumes provision start after global recovery

Then it enters cleanup with a conditional no-op lease-release, removes the completed operation, passes the restart-admission check and creates a fresh operation with a new accepted_at

And the fresh lease-create postcondition treats the same-run expired lease as absent, retries deterministic selection and atomically replaces an expired lease at the selected account path with a new live lease without creating from a lost or foreign lease or changing target bytes

And a later crash replay recognizes only that new live lease as committed and preserves its new lease timestamps rather than adopting the expired lease again

## Scenario: Target-committed prepared expiry completes both recovery phases

Given a target committed but assignment-commit did not persist before lease expiry

When the identical provision request performs prepared-state recovery

Then it uses the adapter committed_at to finish provision postcommit and removes that operation

And it runs expiration through lease release, tombstone creation and assignment removal before returning the typed no-receipt refusal

## Scenario: Lease timestamps derive once from lease creation

Given provision normalizes lease_seconds and commits lease-create at a known manager time

When an identical retry reclaims that run's lease and later returns its receipt

Then lease_started_at equals the original lease-create time and lease_expires_at equals that time plus lease_seconds

And the retry preserves both timestamps while selection assigned_at is the later of its prior value and target_committed_at

## Scenario: Consume-first revalidates its stale incumbent first

Given the retained consume-first incumbent and a lexically earlier matching record are both eligible except that validation age is stale

When provision performs request-time recovery

Then it revalidates the incumbent before every other candidate

And it provisions that incumbent when revalidation succeeds

## Scenario: Spread revalidation preserves least-recently-assigned order

Given multiple matching spread candidates are eligible except that validation age is stale

When provision performs request-time recovery

Then it tries never-assigned and least-recently-assigned records first with lexical record_id ties

And no revalidation outside command execution and pre-operation recovery occurs to change that order

## Scenario: A post-lifecycle held-worker crash becomes a defined failed acquisition

Given acquire made its initial acquiring lifecycle transition visible but the launcher died before releasing the held worker

When the identical acquisition input retries after the held worker exits

Then recovery moves the credential to dead and removes its worker and operation records

And acquire returns invalid-request for the failed attempt without launching replacement

## Scenario: Browser attention clamps to the acquisition worker deadline

Given an acquisition worker raises a browser wall less than browser_attention_wait_seconds before its own deadline

When it writes the attention artifact

Then the artifact deadline equals the earlier worker deadline rather than raised_at plus the configured wait

And at that shared instant the worker destroys in-memory captures and exits without artifact, terminal or lifecycle mutation, after which mandatory recovery identity-matches and removes the artifact, marks the worker revoked, confirms its process group ended and applies failed flow-unavailable recovery to dead

## Scenario: Bound target retry survives issuance expiry

Given a target reference's issuance expires after an identical provision created prepared or committed assignment state

When the identical provision request retries

Then the manager recognizes the bound run state before applying issuance expiry

And committed state or prepared state whose status remains in-progress resumes or returns its stored result without selecting or writing again

And prepared state whose status is uncommitted is cleaned up, after which the now-unbound expired issuance makes the identical retry return invalid-request without selecting or writing

## Scenario: Simultaneous-spread peer choice is deterministic

Given several committed Anthropic factory-purpose spread peers at or after rollout_started_at use the same kind and distinct live runs and accounts

When one committed assignment performs proof-update while simultaneous_spread proof is null

Then it chooses the qualifying peer with earliest target_committed_at and lexical consumer_run_id as the tie-break

And it canonically orders the pair and records the later target_committed_at as overlap_ended_at

## Scenario: Credential freshness boundaries are exclusive

Given one valid credential's current time equals last_validated plus maximum_validation_age_seconds and another equals expires_at

When provision evaluates eligibility

Then the first credential is age-stale and the second is expired

And neither is selected at the equality instant

## Scenario: Pre-lease exhaustion removes its empty provision plan

Given provision persisted its operation but no start effect committed because selection found no eligible credential

When it returns retryable-exhaustion

Then it removes the operation directly without entering cleanup

And it writes no empty ordered_effects array, lease, assignment or target bytes

## Scenario: Concurrent prepared spread runs still prove overlap

Given two Anthropic factory-purpose spread runs both prepared assignments before either target committed

When both targets commit with overlapping retained lease intervals and their proof-updates serialize

Then the first update that can observe both committed assignments records the canonical pair

And simultaneous_spread is not lost merely because both runs prepared concurrently

And its later lease-start time may precede rollout_started_at while its later target-commit time does not, without making the proof record malformed

And later standalone proof validation checks the distinct identities, internal timestamp order and rollout relation from the proof record itself without requiring a retained assignment or tombstone to reconstruct either copied source instant

## Scenario: Isolated-run provisioning preserves exact credential bytes

Given a selected value_ref resolves raw bytes that do not end in a newline

When the isolated-run target adapter commits them

Then the target contains exactly those bytes with no encoding, framing or trailing newline

And the committed target bytes equal the bytes resolved from value_ref byte-for-byte

## Scenario: Spread assignment cannot replace a consume-first incumbent

Given consume-first retains record A as incumbent and a spread request commits record B for the same provider, kind and purpose

When a later consume-first request evaluates both as eligible and unleased

Then spread updated B's assignment time but left A as incumbent

And consume-first selects A

## Scenario: Anthropic setup-token refuses unsupported remaining-percent selection

Given health_strategy is remaining-percent

When provision names the initial anthropic claude-code-oauth setup-token kind

Then the manager returns invalid-request with exit 2 before recovery or store, health-adapter or target access

And it does not send the setup token to the Anthropic usage endpoint or claim a shared-usage remainder

And with otherwise valid configuration, such as no multi-purpose reservation, a direct acquire for that identity remains permitted because the provision-only health check does not perform acquisition selection

## Scenario: Acquisition refuses a mismatched provider account identity

Given the requested account_id has one unique concealed login_identifier and execution captured a provider token through that account's worker-bound browser session

When the trusted local identity inspector compares the provider's authenticated first-party account identifier with that stored login_identifier

Then an exact match is required before credential validation or any value-store effect

And a mismatch destroys the capture and becomes failed provider-rejected while an unavailable identity result destroys it and becomes failed flow-unavailable, with neither identity returned to the execution role

And the prerequisite checker treats two account ids for that provider with one concealed login_identifier as malformed before worker launch

## Scenario: Anthropic validation maps every probe response

Given the exact bounded Anthropic Messages request returns a successful expected HTTP-200 message body, a 401 or 403, a 429 or 5xx, a transport timeout, or an unmapped response

When the validation adapter classifies it

Then those cases map respectively to definitive success, definitive rejection, inconclusive, inconclusive and inconclusive

And no response is left to an implementer-defined lifecycle outcome

And a duplicate body member makes a body-dependent row inconclusive while status-only 401 or 403 rejection ignores the body and remains definitive

And provider-observer receives the exact mode-specific object: both modes carry version, mode, provider, kind, record_id, value_generation, value_ref, external_call_timeout_seconds and op_executable matching one registered immutable record identity, while revalidation also carries provider_probe_timeout_seconds and worker_deadline; health returns only an integer remaining_percent or unavailable, revalidation makes exactly one probe and returns only success with immediately captured validated_at, rejected or terminal inconclusive, and an unregistered or mismatched identity, key, launch, values-vault, permission, malformed-result or deadline failure maps to inconclusive and transitions revalidating to suspect rather than returning store-unavailable

## Scenario: OnePassword stores separate acquisition and provisionable secrets

Given the operator seeded exact login and primary-Gmail items in llm-provider-manager-acquisition and one matching namespace-binding item in each of the acquisition, token-metadata and token-values vaults for the current machine-id digest, effective uid and canonical manager-state path

And token metadata uses canonical references to immutable per-generation items across llm-provider-manager-token-metadata and llm-provider-manager-token-values

When the closed acquisition-prerequisite checker, trusted account-identity inspector and the acquisition, lifecycle, selection, provider-observer and final-provisioning adapters start through the credential-role launch boundary using their user-keyring descriptions

Then the acquisition-reader grant lets the prerequisite checker, identity inspector, browser-control startup login-identifier resolution and local login and mailbox tools read only login and mailbox material, while the separate acquisition-writer grant can write both token vaults but creates one generation without reading an existing generation's fields or value, lists values-vault titles only to enumerate the namespace item and otherwise reads only that namespace item for validation; lifecycle can write only lifecycle metadata; selection can read only metadata; and only the provider observer and final provisioning read values at runtime

And a short-lived launcher child retrieves the one named token only after fork and replaces itself with the manager-owned role vector selected by a closed role name, so the parent manager and selection brain receive no token bytes; the adapter receives only that service-account token and does not invoke keyctl, while same-user code remains in the declared trust boundary and no token or secret bytes enter configuration or agent context

And the operator seeds each user-keyring token through standard input, captures its serial and sets permission mask 0x3f0b0000, after which the launcher directly searches @u, reads exactly the five semicolon-separated raw fields from keyctl rdescribe, requires type user, decimal uid equal to the effective uid, exact key description and lowercase permission field 3f0b0000 after removing an optional 0x prefix, and pipes it without relying on a session-keyring link, while any mismatched field or broader permission word fails before payload read through that role's exact pre-exec failure mapping and the launcher reapplies the complete closed inherited credential-override scrub before key lookup

And the initial Anthropic identity inspector opens the authenticated claude.ai Settings > Account panel and reads exactly one visible syntactically valid account-email field from the CDP accessibility tree, while an unauthenticated page, failed query, zero fields or multiple fields yields only unavailable

And the role maps its sole manager-named token to the op child's sole OP_SERVICE_ACCOUNT_TOKEN, the first backend-needing action after configuration, invocation and exact input-shape validation resolves one canonical regular op executable, carries it in every token-bearing role's closed op_executable input and into any detached worker it launches, and every role uses only that path with its closed item-get, item-list or item-create prefixes and vault constraints while no role searches PATH, accepts a request-supplied executable or includes keyctl in its adapter allowlist

And the acquisition writer streams a credential-bearing item JSON template to op item create over an anonymous standard-input pipe, so no raw credential, login or mailbox bytes enter process arguments, environment or a template file

And after validation the worker passes exactly one writable captured-credential anonymous-pipe FIFO descriptor to browser-control by SCM_RIGHTS over its private SOCK_SEQPACKET control channel, passes only the read descriptor through the acquisition-writer launcher, closes its copies, and browser-control closes the received descriptor after its one write

And only the final provisioning child receives the value-reader token at launch, validates the target binding before reading that variable or the values vault, then resolves value_ref and passes raw bytes directly to its target write, while a status-only query runs through the tokenless target-status launcher role with exactly version, target_ref, consumer_run_id and value_generation plus only the target-reference lock descriptor, accepts evidence only when all three identity fields match, makes no keyring call, and returns store-unavailable for malformed or mismatched evidence while an ordinary retry preserves prepared state on that result or malformed role output

And before role exec a missing key, bad permission or exec failure produces that role's exact secret-free failure object without backend or target action, so final-provisioning cleans up with store-unavailable rather than treating launcher failure as an ambiguous write

And provider-observer and final-provisioning validate the values-vault namespace item before their exact referenced value read, bypass the metadata cache, hold raw bytes only for that role call and destroy them when it ends

And the prerequisite checker returns only present, absent, malformed or unavailable without returning an item field, reference or diagnostic, while both acquire identity lookups use only the metadata-reader role and neither a preliminary duplicate or unavailable lookup nor a metadata-reader unavailable result can be interpreted as absence or return before the authoritative under-lock lookup and global recovery

And metadata get, list and chain reconciliation exclude exactly the independently validated llm-provider-manager-namespace item before revision-envelope validation, then collapse byte-identical physical duplicates, validate each append-only predecessor chain and wrap each valid current logical record with the revision title as backend item_id, so the reserved namespace item coexists with valid rows while another non-revision title remains store-unavailable

And get represents an invalid chain only as status invalid plus its record_id and closed reason, while list returns valid items and a separately sorted invalid descriptor array, so no earlier valid-looking revision of that chain reaches selection and another valid chain can still satisfy the request

And direct acquire treats any invalid descriptor in its authoritative under-lock metadata list as store-unavailable rather than proving a new identity absent or minting a record_id, without preventing another command from selecting an unrelated valid record

And conditional-set appends only the next effect_id-bearing revision through op item create under the per-record lock; unconditional set returns committed, uncommitted or unavailable, conditional-set may additionally return condition-failed, and every other result shape is unavailable or requires revision-chain reconciliation

And each acquisition, metadata or values vault contains exactly one matching namespace item, and before every read or create the role validates the item in every vault it will access, while absence, duplicates, mismatch or an unsafe machine-id source returns store-unavailable before credential data access or mutation so another host, uid or state namespace cannot use the vaults

And the concealed Gmail authorization is canonical client-id, client-secret and refresh-token JSON whose local mailbox tool refreshes at the fixed HTTPS endpoint and keeps each access token only for that call

## Scenario: Acquisition roles communicate only through closed secret-free interfaces

Given an acquisition worker starts with a matching login item, remaining step budget and account-specific Chrome profile

When research discovers the current flow and execution drives it with the restricted tools

Then their inputs, outputs and capabilities match the closed research-and-execution role protocol

And research and execution use their exact complete claude --print --verbose --output-format stream-json argument vectors with empty ordinary and managed setting sources, literal manager-owned system prompts, and separate empty owner-only manager-owned working directories

And only the canonical version-1 role object plus one LF enters standard input, no input enters an argument or prompt, and only a zero-exit stream ending in one successful result whose result string is the closed role JSON object is accepted

And before a tool call the first stream object must be system init with the exact working directory, default output style, empty slash-command, skill and plugin inventories, the role's exact tool inventory, only its permitted connected MCP server and absent or empty owner-only reported memory paths

And execution's sole MCP server is named lpm_acquisition with the exact canonical one-server config, and its allowed-tools are exactly the 17 mcp__lpm_acquisition__ prefixed declared tool names

And after preflight a race in which the runtime rejects a required flag, a runtime-reported startup inventory other than exactly WebSearch for research and exactly the 17 private MCP tools with no built-ins for execution, or an admin-managed source that can extend either invocation fails before agent work as flow-unavailable

And research has only web search and cannot read or write the filesystem, run a shell or process, fetch outside search, use MCP, or access the protected interactive credential file

And execution receives exactly the seven browser, six terminal and four secret-aware tools through one manager-owned private-stdio MCP proxy and strict allowed-tools configuration, with filesystem, shell, generic process or URL access, web search, every other MCP server, manager state and the protected interactive credential disabled

And the worker alone spawns Chrome, creates both CDP pipe pairs, passes only the browser-side ends to Chrome and the service-side ends through the browser-control launcher, then closes every own copy; browser-control alone retains the service-side ends and spawns the acquisition terminal, and execution claude alone spawns its configured MCP proxy, with the actual spawner applying the complete ASCII-uppercased credential-override scrub, including OP_* and all six manager variables, at each boundary

And foreground preflight passes immutable canonical path plus device-and-inode references for Claude, the registered acquisition terminal and Chrome to the held worker, which never re-searches PATH, revalidates each identity immediately before its permitted spawn and passes only the terminal reference into browser-control; SecretStore calls separately use only the retained canonical op path

And the initial Anthropic terminal reference is exactly the already-resolved Claude executable reference with sole fixed argument setup-token, so preflight performs no second PATH search for it

And setup-token receives no display, Wayland, X authority or session-bus variable, receives only the non-secret LPM_BROWSER_CREDENTIAL_KIND binding for helper policy, invokes only the manager-packaged BROWSER helper, and that helper refuses an absent or unregistered kind and otherwise validates the URL against that row's allowlist before writing its single allowed authorization URL only through inherited writable FIFO descriptor 4 for browser-control to navigate in the worker profile without opening the host browser

And the initial Anthropic browser allowlist is exactly claude.ai for identity inspection, claude.com for the setup-token authorization page, platform.claude.com for its callback and success pages, and accounts.google.com for login; any other origin is refused

And as its first manager-owned instruction the proxy removes that complete set from its own runtime-supplied environment before reading any other value or request, refusing startup if a manager service-account or OP_* value was present

And the launcher-created browser-control service alone owns CDP, terminal state, the acquisition-reader token, captures and taint state; the proxy forwards only canonical tool requests and closed secret-free results, while identity inspection and acquisition validation use a separate worker-control channel

And before Chrome launch or any observation the service resolves only the matching concealed login_identifier, taints its exact bytes and exposes neither value nor presence, while login_secret remains unresolved until an allowed-origin type-login-material call

And browser-control sends exactly one ready or unavailable startup object on the worker-control channel after that taint step, and the worker waits one external-call interval for ready before profile setup, Chrome launch or agent launch

And the worker exposes the proxy endpoint only as inheritable descriptor 3 through execution claude to its sole MCP child, the proxy validates that descriptor as its connected AF_UNIX SOCK_STREAM channel, and the pair carries one outstanding four-byte-length-prefixed canonical version-1 tool-and-arguments request and closed result

And malformed framing, JSON, structural member set, JSON type or tool identity closes the channel without action or step consumption and fails execution flow-unavailable

And a structurally valid request whose values violate a bound, origin, taint, handle, authorization or other semantic predicate instead returns refused without action and consumes one step

And every launcher role receives only its exact version-1 input object and registered descriptor set, while metadata-reader has only get and list forms, each writer has only its field-authorized conditional-set form, acquisition-writer alone also has descriptor-backed secret-value-set, and malformed or relation-invalid input fails before external action

And a browser-control pre-exec failure emits exactly version 1 and unavailable on its launcher-result pipe and maps to failed flow-unavailable without browser or store action

And the worker-control channel accepts only exact inspect-account-identity, validate-capture and one-descriptor transfer-capture requests, returning only their closed result shapes and performing no action for a malformed identity, handle or descriptor relation

And after identity match the service validates the captured bytes and extracts expiry internally, returns only the closed validation result and timestamps, then transfers those bytes directly to the acquisition writer through an anonymous descriptor whose parent copies are closed, so neither agent, proxy nor worker receives them

And login, mailbox, verification-code and captured-token bytes never enter either role's messages or artifacts

And before either agent or any terminal, Chrome, proxy or browser-control child starts, including during provision-triggered reacquisition, the actual spawning process removes every inherited CLAUDECODE, ANTHROPIC_*, CLAUDE_*, OP_* and manager service-account variable after installing any token of its own

And when the invoking consumer environment carries a legacy CLAUDE_CODE_OAUTH_TOKEN or another closed credential override, the bootstrap's first action after its two permitted imports removes that name without reading its value before the isolated companion starts, and every credential-role launcher reapplies the same complete name-based scrub before key lookup

And agent, Chrome and browser-control HOME is the effective user's account-database home, while setup-token gets a fresh empty worker-private HOME, cannot read the protected interactive credential and removes that directory after exit

And actionable accessibility nodes expose only opaque worker/document/frame/revision-bound element handles that become stale after navigation or a DOM-changing action

And every invocation of any one of those 17 tools consumes one cumulative step across attention resume whether it succeeds, is refused or is unavailable, while a request arriving with zero remaining budget is not an invocation, performs no action, returns refused without consuming a step and imposes terminal step-limit

And action identity is the exact tool name and canonical validated arguments, observed state is the browser fingerprint plus cumulative terminal-state digest, and the first three consecutive matching mutation calls may run while a fourth consumes its step, returns refused before execution and imposes terminal step-limit

And browser-control sends the exact execution-stop object for an imposed step-limit or flow-unavailable condition, after which the worker terminates and reaps execution, destroys every capture and ignores any conflicting concurrent or later role result

And observation and wait calls do not enter or reset that repetition count unless observed state changes, while wait-browser accepts only whole seconds from one through 30 and refuses another value without browser action

And every local capability returns its exact secret-free ok, captured, applied, not-found, refused or unavailable shape, while apply-mailbox-verification accepts no query or candidate value and uses only the trusted registered selector

## Scenario: Invalid browser-control requests are refused without browser action

Given an execution role has its registered credential-kind browser-origin allowlist and remaining step budget

When it requests navigation to a non-HTTPS or off-allowlist origin, empty, oversized or tainted browser text or selection, or a scroll with direction other than up or down or pixels outside one through 10000

Then the tool returns exactly the version-1 refused result without browser action

And the refusal consumes one step but is not a performed action and does not enter or reset the repetition guard

## Scenario: Browser profile first use and unsafe state are deterministic

Given an authorized acquisition worker reaches its account-specific persistent browser profile

When the final profile directory is absent

Then it atomically creates that directory mode 0700 beneath the validated owner-only non-symlink browser-profiles parent and launches Chrome only after validating the result

And each launch sets password-manager, profile-autofill and payment-autofill preferences false, disables sync and permits no basic plaintext password store

But when the parent or profile tree is malformed, symlinked, wrongly owned or broadly accessible, or directory creation fails

Then it launches no Chrome, does not chmod, replace or reset the path, destroys every capture and terminally fails flow-unavailable so the credential follows its lifecycle transition to dead

And before a normal close while Chrome runs, browser-control clears secret-populated fields and navigates blank, then closes Chrome and scans the exited profile for exact tainted login-secret, mailbox-code, provider-token-match and captured-token bytes while allowing only the non-secret login_identifier to remain as inaccessible signed-in account state

And an already exited or crashed Chrome skips those impossible live actions but still receives the post-exit scan, while a live-sanitization failure, match or unscanned state removes the profile and fails flow-unavailable

And the retained non-secret login_identifier is nevertheless redacted from every URL, title, DOM, accessibility, screenshot, agent message and trace by the startup taint registration

## Scenario: Anthropic mailbox verification rejects unauthenticated or ambiguous codes

Given the local Gmail selector inspects messages at or after worker started_at without receiving a query or candidate from the execution role

When the newest message by numeric internalDate and lexical message id has exactly one From mailbox in the anthropic.com domain, topmost mx.google.com Authentication-Results with matching dmarc pass header.from, a topmost Delivered-To mailbox matching the acquisition login_identifier without ASCII case sensitivity, and exactly one distinct standalone six-digit string across its plain body and rendered HTML text

Then apply-mailbox-verification types that value into the bound element and returns applied without exposing it

And equal internalDate messages choose the lexically greatest Gmail message id before applying the same one-value rule

And repeated occurrences of the same code count once, while HTML markup, attributes, comments and script or style content do not count

And a pre-start message, multiple From mailboxes, a non-Anthropic or mismatched or DMARC-failing sender, a missing, malformed or account-mismatched topmost Delivered-To field, or a selected newest message with zero or multiple distinct standalone six-digit values returns not-found without typing, while lower Authentication-Results and Delivered-To fields are ignored as untrusted

## Scenario: Operator give-up terminates browser acquisition safely

Given a pending browser-verification artifact names an authorized worker before both deadlines

When the local operator runs attention --give-up for its record_id

Then the manager atomically records give-up and returns the exact attention-update success

And the worker removes the artifact, destroys captured bytes, persists terminal failure_reason flow-unavailable and transitions the credential to dead

## Scenario: Acquire expires or restarts a matching identity through reacquisition

Given one record matches the requested provider, account_id, kind and purpose and is either dead with no pending operation or valid, suspect or revalidating with expires_at no later than the manager's captured time

When the operator invokes acquire for that identity

Then a valid, suspect or revalidating expired record first runs the mandatory expiry sequence under the held provider-account lock, including fencing and reconciling any live revalidation worker before the authoritative reread and dead transition

Then the manager retains its record_id, generates a fresh next_value_generation and launches an internal reacquire operation

And it returns the secret-free acquire success with credential_status reacquiring after the held-worker lifecycle transition commits

## Scenario: Acquire retry reports a recovered terminal outcome exactly

Given an identical acquire retry finds its direct acquire operation or locates a matching record_id and reacquire operation through the canonical metadata identity lookup, and that worker is no longer live

When recovery completes the operation under the provider-account lock

Then an exact committed terminal metadata record derived from stored validated_at, published_at and expires_at advances any unmarked effect and finishes cleanup without another worker

And acquire completes global mandatory recovery while retaining the provider-account lock before returning that recovered success or any recovered failure

And a persisted terminal failure retains its terminal result, effect identifiers and lifecycle-writer actor even if another process resumes it after worker loss, then finishes cleanup and returns invalid-request without another worker

And a lost active worker with no persisted terminal phase, or one whose desired terminal-success record is absent, enters a recovery phase whose effect identifiers and recovery-writer audit differ from any prior terminal-success audit

## Scenario: Missing acquisition prerequisites start no worker

Given the protected Claude credential, matching acquisition-vault login item or required Gmail mailbox item is absent, duplicated by title or violates its exact ownership, mode or schema rule

When the operator invokes acquire

Then the manager returns invalid-request before creating an operation, worker or credential record

And no browser, terminal or provider validation action occurs

And the checker and later local tools never choose between duplicate login or mailbox items

## Scenario: Failed research and bounded execution fail acquisition safely

Given the research role fails or returns malformed output, execution receives an unavailable or malformed local-tool result, exhausts its cumulative step limit, requests a fourth identical mutation action against its exact unchanged state fingerprint, or returns attention with zero remaining steps

When the acquisition worker applies the closed research-and-execution role protocol

Then failed or malformed research persists terminal failure_reason flow-unavailable and launches no execution role

And unavailable or malformed local tooling returns flow-unavailable, while bounded execution returns the declared step-limit failure, destroys every capture and follows the terminal dead transition

And zero-budget attention creates no artifact

## Scenario: Terminal token output is captured without disclosure

Given the allowlisted claude setup-token process emits an authorization URL and an sk-ant-oat01 token

When the execution role observes terminal output and captures the token

Then the authorization URL remains visible while the token is replaced with the exact [[redacted-token:terminal:<uuid>]] marker carrying its otherwise opaque source handle

And capture-token accepts only that opaque handle and returns only a single-use capture handle

## Scenario: Invalid terminal-control requests have no side effect

Given the acquisition terminal may already be started and the execution role requests a second start, supplies launch inputs, sends an empty, oversized or tainted line, requests a wait outside one through 30 whole seconds, or supplies an unknown, stale or mismatched source handle

When the terminal controller validates that request

Then it refuses without starting another process, writing terminal input, waiting or taking another process action

And a valid send-terminal-handle writes only its locally resolved bytes to terminal standard input and returns none of them

And any non-empty line within the byte limit that matches neither taint nor the provider-token matcher is accepted without an observation-provenance requirement

## Scenario: Unregistered provider identities fail before external access

Given acquire or provision names a provider or credential kind absent from the initial registry

When the manager validates the request

Then it returns invalid-request with exit 2 before any store, worker, health adapter or provisioning target access

And the registered anthropic claude-code-oauth factory identity remains accepted

## Scenario: External adapter deadlines have typed fail-closed outcomes

Given a SecretStore, provider-health, target-issuance, target-write or commit-status call remains unresponsive beyond external_call_timeout_seconds

When the manager reaches that call

Then a foreground-command SecretStore deadline outside the provider-observer and detached-worker paths, or a target-issuance deadline, returns store-unavailable and a health deadline excludes that account

And a revalidation provider-observer value-read deadline is inconclusive and transitions revalidating to suspect, while a detached writer's SecretStore deadline retains its owning operation for the defined recovery path

And a target-write or commit-status deadline returns retryable-exhaustion, preserves the prepared assignment and lease, and makes an identical retry query commit status before another write

And final provisioning budgets one external-call interval for its values read and one for target validation and write, while a value-reader launcher failure produces the exact pre-exec store-unavailable shape and a values-vault failure after target validation produces the same pre-write result, after which the manager discards prepared state, releases the lease and returns store-unavailable with exit 4

And final-provisioning abnormal exit or malformed output after successful role exec preserves prepared state and returns retryable-exhaustion for an identical status-query retry, while an ordinary tokenless target-status abnormal exit or malformed result strictly before its parent deadline preserves that state and returns store-unavailable; a parent-enforced target-status deadline and its resulting termination instead return retryable-exhaustion

## Scenario: Credential generations publish without stale-reference ambiguity

Given acquisition or reacquisition generated next_value_generation and an older value generation may still exist

When its terminal operation succeeds

Then secret-value-set creates the new immutable concealed generation item before metadata conditional-set publishes the matching value_generation and value_ref

And the worker checks its active lifecycle and worker authorization immediately before that unconditional create, while the later metadata conditional-set repeats those predicates so a raced revocation can leave only an unreferenced item

And the old generation remains addressable only by its old reference while a late report compares its stored generation and cannot suspect the replacement

And an explicitly uncommitted, unavailable, malformed, timed-out or interrupted creation is never postcondition-read or retried for that generation; the live worker or later recovery enters the recovery phase, abandons any item unreferenced, records failure and makes a later attempt generate a new value_generation

## Scenario: Worker operation phases retain every terminal effect

Given an acquire, reacquire or revalidate launch phase committed its active lifecycle transition

When the worker succeeds, fails or is recovered

Then the completed launch remains durable until a worker atomically enters its exact terminal phase or pre-terminal recovery atomically enters its exact recovery phase with a secret-free result, and the operation cannot be removed from a nonfinal phase

And acquisition terminal success or failure completes value audit, secret-value, metadata audit, conditional metadata and worker-removal positions while revalidation uses its exact metadata-only terminal array

And persisted acquisition failure stores exactly one of provider-rejected, flow-unavailable or step-limit in failure_reason with null timestamps, persisted acquisition success stores null failure_reason, persisted revalidation success publishes valid with stored validated_at, persisted rejected failure publishes dead even if the worker is later lost unless another actor already moved the record out of revalidating or replaced its value generation, persisted inconclusive publishes suspect, and pre-terminal fencing durably enters recovery with inconclusive and publishes suspect

And after worker loss a persisted terminal success completes only when its metadata conditional-set was marked or its exact desired replacement is authoritative; otherwise recovery atomically replaces it with the failure recovery phase and new recovery-writer effect identifiers

And when that unmarked terminal-success conditional-set still has a pending-effect fence after worker loss, mandatory recovery instead retains the original terminal phase while it reconciles only the byte-identical revision, then durably enters failure recovery before removing the fence, so a crash cannot strand a revision fork or preserve the intermediate success

And whenever a paired SecretStore effect is a completed no-op, its preceding audit-append is also a no-line completed no-op

## Scenario: Credential expiry is audited and retained without a journal

Given a valid, suspect or revalidating credential reaches expires_at, with a live worker still present for the revalidating case

When any command that passed pre-recovery validation performs its mandatory credential-expiry recovery step

Then it first revokes, terminates and reconciles the live worker when present, rereads authoritatively, and appends attempted-operation audit evidence before one conditional metadata transition to dead

And that single-store transition needs no write-ahead record and deletes neither credential metadata nor value generations

## Scenario: An unknown operation-less expiry write remains recoverable

Given lifecycle expiry appended its audit entry and its recovery-writer conditional-set reached an unknown outcome

And the canonical pending metadata-effect fence has null owner_operation_id because expiry has no write-ahead operation

And its expire-lifecycle digest is simultaneously the audit deduplication identity, conditional-set effect_id, revision-title suffix and fence effect_id, recomputed from the authoritative expiring record

When immediate authoritative reconciliation cannot prove the desired revision committed

Then the command returns store-unavailable, retains the fence and leaves that credential ineligible

And a later command's global recovery discovers the fence without an operation record and retries only its byte-identical revision through recovery-writer

And the credential remains ineligible until reconciliation makes that revision authoritative and removes the fence

## Scenario: Deterministic local paths use length-prefixed identities

Given provider, account, target, run, command or idempotency values contain arbitrary non-empty UTF-8 bytes

When the manager derives an issuance, lease, assignment, tombstone or operation path

Then it hashes the contract's ordered LP values rather than delimiter-joined text

And distinct value tuples cannot collide through an embedded separator

And explicitly specified external-backend item titles and value references retain their literal wire syntax

## Scenario: Successful replacement refreshes acquisition time and declared expiry

Given acquisition or reacquisition has validated a new credential generation

When its metadata conditional-set publishes that generation

Then acquired_at becomes the stored terminal-result published_at, last_validated becomes the stored successful validation time, status becomes valid and the prior value_ref becomes previous_value_ref

And the initial anthropic claude-code-oauth adapter sets expires_at null while any future kind uses only its registered canonical expiry extractor

## Scenario: An extracted expiry that elapsed before publication fails acquisition

Given a future credential-kind expiry extractor returns a non-null expiry no later than the worker's later published_at

When the worker validates that extracted expiry before persisting terminal success

Then it destroys the capture, persists the failure terminal result with null timestamps and failure_reason flow-unavailable, and returns failed flow-unavailable

And it creates no value item, publishes no expiry and transitions the acquiring or reacquiring credential to dead

## Scenario: Backward time between validation and publication is clamped

Given acquisition validation stored validated_at and the manager wall clock then moves backward before the worker receives that result

When the worker captures its publication-time candidate

Then it stores published_at equal to validated_at, validates any extracted expiry against that normalized time and can persist a conforming terminal success without moving time backward

## Scenario: Report diagnostics do not change idempotent identity

Given a report operation or report marker exists for one run, record, occurrence time and classification

When a repeat supplies a different redacted diagnostic or omits it

Then the manager discards the diagnostic before normalized-input comparison

And it resumes or returns the same duplicate result without another lifecycle transition

And an overlong diagnostic, ASCII control character or provider-kind token match instead returns invalid-report before recovery or mutation

## Scenario: Manager runtime prerequisites fail without fallback

Given a manager action or released acquisition worker needs Linux procfs, the user keyring, OnePassword CLI, Claude CLI with its protected host credential and required role-flag capability, headed installed Google Chrome, or a graphical session and that prerequisite is unavailable

When the manager reaches the first action requiring it

Then a base or SecretStore prerequisite returns store-unavailable, direct-acquire browser prerequisites return invalid-request, provision replacement prerequisites return retryable-exhaustion, and released-worker loss becomes terminal failed flow-unavailable

And it does not use plaintext storage, another operating system, another agent credential source, bundled or cloud browser, or a network-exposed CDP listener

And preflight accepts the Claude CLI role-flag capability only after separate local non-network invocations with --managed-settings followed by safe-mode or restricted and --version both exit zero and emit the same non-empty single-line version, and accepts Chrome only after the fixed executable-name search, Google Chrome version check, non-empty display variable and private-pipe Browser.getVersion probe all succeed

And direct acquire runs that preflight only after acquiring the provider-account lock, matching-operation and global recovery, expiry and non-dead duplicate resolution, then runs the acquisition-prerequisite checker before creating a new operation

## Scenario: Recovery candidates bypass health until final selection

Given remaining-percent is configured and an authentication failure made a record suspect or left a dead record whose prior value cannot authenticate to usage

And that provider-and-kind registry row declares a shared-usage observer

When request-time recovery evaluates that account

Then health unavailability does not exclude the suspect record from revalidation or the dead record from replacement

And a recovered valid record must still pass a fresh health observation before final selection

## Scenario: Kernel lock files release when their holder ends

Given a manager run, account, credential, global record or target-reference holder owns its declared flock descriptor

When its last holding process or inherited descriptor ends unexpectedly

Then the kernel releases the lock while the owner-only non-authoritative lock file may remain

And a contender recognizes matching worker ownership only from the contended account lock plus exactly one authorized live worker record

## Scenario: A bounded blocking lock wait times out without mutation

Given a credential-record, attention, target-reference, audit-log, selection-state or proof-record lock remains held by another actor

When a command cannot acquire that otherwise blocking lock within external_call_timeout_seconds

Then it returns store-unavailable with exit 4

And it performs no substantive mutation

And a fenced acquisition kills the worker's whole process group while its worker inherited only the explicit account lock and no Chrome, terminal, browser-control or agent child inherited even that descriptor

And a revalidation worker inherits no manager lock descriptor

And it holds no manager lock during its provider probe, then takes credential-record and audit-log locks in contract order only for its bounded terminal commit

And a final provisioning child inherits only the target-reference lock descriptor and retains it through write or status completion even if its parent times out or exits

## Scenario: Secret-tainted browser observations fail closed

Given local acquisition tools typed login or mailbox values or captured a token

When the execution role requests an observation containing URL, title, DOM, accessibility or screenshot fields

Then the observer replaces every token match with its handle-bearing token marker and every remaining registered exact value with the fixed handle-free sensitive marker in URL, title, DOM and accessibility fields before computing the fingerprint, and masks every populated or matched screenshot node before returning the observation

And capture-token and send-terminal-handle accept only a token handle and never the fixed sensitive marker

And terminal redaction matches each cumulative stream, withholds an unresolved token-like suffix across incremental observations and releases only sanitized text

And a browser token matcher registers its hidden value before constructing output and masks every matching node in the screenshot

And when it cannot prove that every sensitive region is covered, the observation consumes one step, returns only unavailable, leaves the prior successful fingerprint unchanged and ends the invocation as failed/flow-unavailable

And a secret-aware tool refuses before lookup unless both frame and top-level origins are registered

And no browser capability exposes cookies, credential-manager data, storage, request bodies, downloads, clipboard, arbitrary JavaScript or raw Runtime.evaluate

## Scenario: Run closure records assignment end before tombstone creation

Given report, completion, release or expiration closes a live committed assignment

When its exact operation array is persisted and resumed

Then assignment-end-update records the latest of lease_started_at, target_committed_at and the earlier of accepted_at and lease_expires_at for report, completion or release, and records lease_expires_at for expiration before conditional lease release, tombstone creation and assignment close

And tombstone closed_at remains accepted_at for report, completion or release and may precede the normalized actual_lease_ended_at only after a backward clock step, while expiration uses lease_expires_at as its logical closed_at and actual_lease_ended_at never precedes lease_started_at or target_committed_at or exceeds lease_expires_at

And classification or generation no-ops remain completed positions rather than changing the persisted effect array

And report releases credential-record serialization after its conditional credential effect and cache eviction, before proof or lease effects

## Scenario: Run closure clamps a lease that expires during global recovery

Given report, completion or release begins while its lease is live and global recovery lasts past lease_expires_at

When the command captures accepted_at and closes the assignment

Then actual_lease_ended_at equals lease_expires_at, closed_at equals the later accepted_at, and the retained interval cannot overlap a peer after the lease actually expired

## Scenario: Lease mutations serialize on one account identity lock

Given concurrent create, release and expiration operations address one provider and account

When they contend on the deterministic lease-record lock

Then exactly one mutates the lease record while a contended create retries selection

And no caller observes or writes a partial shared lease decision

## Scenario: Target commands serialize every local effect for one run

Given concurrent target, provision and lifecycle commands address one consumer_run_id

When they attempt manager-local effects

Then the per-run lock admits exactly one command at a time

And every later command resumes the one nonterminal run operation before evaluating its own request

And a target write or commit-status query holds the target-reference lock for the complete adapter call

## Scenario: Manager time truncates toward the earlier UTC second

Given the UTC system clock has a fractional-second value at a manager decision or target commit boundary

When the manager captures current time or the target supplies target_committed_at

Then it truncates toward the earlier whole second in canonical Z form without rounding

And comparisons and duration additions for that decision reuse that captured second

## Scenario: Duplicate JSON member names are never silently collapsed

Given a repeated member name occurs in configuration, command input, manager-local state, SecretStore metadata, research, execution or prerequisite-checker output, or a provider validation response

When the responsible JSON parser reads it

Then configuration and command input use their defined invalid input result, stored state is store-unavailable, malformed acquisition output uses its typed failure, and the provider response is inconclusive

And no parser chooses either duplicate value or performs the rejected mutation

## Scenario: Canonical stored JSON has one byte representation

Given equivalent credential metadata, audit or pending metadata-effect fence objects differ only in input member order, insignificant whitespace or permitted JSON escaping

When the manager serializes them for the metadata record, audit line or fence file

Then all use the contract's sorted-member, minimal-whitespace, scalar-string and integer rules to produce identical UTF-8 bytes without a byte-order mark

And metadata and fence files have no trailing newline while each complete audit object has exactly one following LF
