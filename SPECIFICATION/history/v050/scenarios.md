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
