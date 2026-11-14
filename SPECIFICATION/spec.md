# livespec-overseer

livespec-overseer is the Control-Plane operator tool for long-running agent
supervision, account rotation and LLM credential provisioning. Its supervision
system is a headless `overseerd` daemon plus a thin interactive overseer pane.
It watches every tracked session's remaining context headroom, injects an
escalating wrap-up prompt as a session approaches its limit, and safely
restarts that session ONLY once the session has declared itself ready on the
filesystem — so no work is lost to a mid-flight restart.

This specification governs the observable contracts of that supervision
system, `caam-anthropic-loop`, and `llm-provider-manager`; the exact internal
security and crash-safety mechanisms expressly required by `contracts.md`;
and the contributor-facing internal-composition constraints stated explicitly
in `non-functional-requirements.md`. It does NOT otherwise govern the internal
composition of the Python package or the overseer pane's operator-cockpit
presentation. Where non-functional requirements restate one of those exact
security mechanisms, they define its contributor-facing enforcement rather
than a second contract. The pane's track table, its columns, and its command vocabulary
may evolve freely so long as every guarantee in this tree holds.

This specification also governs only the incident-routing behavior of the existing
drain-backlog operator surface defined in contracts.md §"Expedited incident
operator routing". This adds no operator skill, resident seat, daemon, independent
incident lifecycle or store.

The existing daemon MUST also observe authorized result obligations independently
of an owning coordinator or explicit waiter and execute safe bounded recovery
through the orchestrator's public interface, as defined in contracts.md
§"Independent recovery of authorized session obligations". This adds no operator
skill or daemon and MUST NOT relax the cardinal ready-only restart rule.

## The cardinal rule

A supervised session is restarted ONLY when it has declared `ready` in its
state file during the current supervision round. That declaration is the SOLE
restart authorization. The daemon MUST NOT infer readiness — not from
idleness, not from a timer, and not from how low the session's remaining
context has fallen.

This is a correctness rule, not a courtesy. A timer cannot know whether a
session is safe to kill: an idle, settled pane is NOT evidence of a safe
stopping point, because a session can be idle while a background build runs,
while a sub-agent works, or while it waits on a human elsewhere. Only the
session knows, so only the session may say so.

A session that declares nothing is reported to the operator as not responding
and is otherwise left alone. Failing to declare is a defect in the supervised
session — which was told, escalatingly, exactly what to write — never a
licence for the daemon to guess on its behalf. There is exactly one restart
path in the system, and the only way to reach it is a fresh session-written
`ready` declaration.

The certification floor of §"The supervision round" governs WHICH declaration
may authorize a restart; it never governs whether the daemon may infer one. The
daemon MUST NOT restart on a timer, on idleness, on the age of a declaration,
or on how low remaining context has fallen, whatever floor a track carries.

## Out-of-band state declaration

A pane's text stream cannot carry a trustworthy "the session asserts X now"
signal: injected instructions are echoed back into the transcript, the model
quotes tokens while narrating, output scrolls beyond the captured region, and
long lines wrap — each of which can turn a printed sentinel into a false
match. The session's self-declared state therefore travels OUT-OF-BAND on the
filesystem, in one state file per track. A file write cannot be forged by
prompt echo, cannot scroll off, and cannot line-wrap.

The protocol uses ONE file holding ONE value — never a set of presence
markers. Two presence-marker files carried a built-in ambiguity (nothing
stopped both existing at once); a single file holding a single first line
makes that state unrepresentable. There are exactly four values a session
writes — `ready`, `blocked: <one-line reason>`, `winding-down`, and `done`
(optionally `done: <one-line summary>`, per §"The terminal declaration") — plus one
value the daemon writes to itself (`idle-with-context-left`, per §"The
keep-going nudge"). A malformed value is surfaced to the operator and treated
as NO declaration at all — fail-closed, so a typo can never restart anything.
A session's one state file remains writable ONLY by that session and the
daemon's single self-token.

Declaring is mandatory once a wrap-up has been received: a session chooses
WHICH value fits, but declining all four does not buy a reprieve — the track
is reported as not responding and sits untouched until a person intervenes.

Pane text remains trusted ONLY for the busy / idle / gate signals and for the
exact-match classification of §"First-run onboarding screens", including the
workspace-trust prompt's folder. Ambiguous,
unrecognized, or conflicting evidence suppresses action — the safe direction.
Recognized background-shell evidence is not itself ambiguous: it may coexist
with one of the narrowly qualified informational pastes below, but it never
authorizes a restart or relaxes that paste's independent guards.

Whether a supervised session can raise a STRUCTURED QUESTION MUST be derived
from live gate evidence, and MUST NOT be inferred from a runtime name, a launch
mode, or an approval or sandbox policy. A runtime that renders a structured gate
in one context does not thereby render one in every context, and a runtime
believed unable to render one may do so once a feature is enabled.

A supervised session MAY declare `blocked: <one-line reason>` whenever it is
genuinely waiting on a human and cannot obtain the needed decision through an
available structured gate. That escape hatch MUST remain available even to a
runtime that CAN render structured questions in some interactive contexts: a
headless invocation may offer no such surface, and not every human decision is
expressible as a multiple-choice question. The existence of a structured-question
feature MUST NOT make the blocked declaration conditional on that feature being
enabled, being suitable for the decision at hand, or being available in the
current harness.

## The supervision round

Supervision proceeds in per-track ROUNDS. A round opens when a session at or
below its wind-down threshold, or carrying a context-compaction latch, presents
a POSITIVELY EMPTY input. Claude MUST show a positively empty input box. Codex
cannot distinguish its empty placeholder from typed text in a plain capture, so
it MUST present positive evidence that its composer is empty: for an IDLE Codex
session its structural idle-input evidence — a live prompt and statusline with
no generating marker or picker — is that evidence; a BUSY Codex session needs
evidence that distinguishes the placeholder from typed text, and when that
evidence is unavailable the round MUST NOT open and the track MUST be surfaced
naming that reason. The input region MUST be identical across the two settle
captures. The pane MUST NOT show a structured gate or picker, MUST NOT be
runtime-reported as waiting on a human, and MUST NOT carry `blocked:`, `ready`,
`done`, or a fresh `winding-down`; a stale acknowledgement MAY resume
escalation. Busy evidence MUST NOT prevent the round: a generating turn,
sub-agents, monitors, background shells, and a capture that changes OUTSIDE the
input region all leave the round eligible. Winding down, including stopping its
own background processes, monitors and sub-agents before declaring `ready`, is
the SESSION's responsibility, and a session that never idles could otherwise
never be restarted. The daemon re-checks every authorization input immediately before acting,
records an injection stamp durably, then pastes the wrap-up, leaving all running work untouched. The stamp is written BEFORE the paste, so a declaration that
responds to the wrap-up is always newer than the stamp. The round closes when
the daemon restarts the session — which deletes the state file and the round's
stamp together — so a declaration can never re-trigger, and a stamp can never
outlive its round. A paste into a busy session is a queued submission. Its
submission MUST still be confirmed by runtime-appropriate evidence that the
payload left the input; a submission that cannot be confirmed is classified
under the delivery outcomes defined below and is un-opened only when it is
provably FAILED. This rule governs DELIVERY only. The restart interlock is
unchanged: a `ready` declaration restarts a session only under contracts.md
§"The restart interlock", including its no-busy gates, so a busy session that
declared `ready` is never killed mid-work. The recovered-round closure defined
below is the one other closure, and it deletes the round's durable record only when the state
file is already absent. A subsequent round starts fresh: every escalation
band may fire again.

A DELIVERED round is closed by exactly TWO events and no other: the restart,
and the recovered-round closure defined below. No other daemon behavior —
expiring a declaration included — MAY delete such a round's durable record or
reset its notified escalation bands.

A round whose wrap-up never landed is a different case, and un-opening it is
required rather than permitted. The round is opened speculatively: the stamp
is recorded before the message is pasted, precisely so a declaration
answering the wrap-up is newer than it. When that opening paste FAILS, no
wrap-up was delivered and there is no round for any declaration to answer,
so the daemon MUST delete the stamp it just wrote and leave the track
un-rounded. It MUST NOT leave a standing round behind an undelivered
message: any `ready` written afterwards — a stale resume convention, a state
file inherited from a predecessor, an unprompted write by a session that was
never told to declare — would otherwise certify against it and authorize a
kill. Only a DELIVERED round is closed by the restart or by the recovered-round
closure; a merely attempted one is un-opened at once and was never a round at
all.

That deletion is itself a fail-soft storage operation and MAY fail. When it
does, the track carries a STANDING ROUND WITH NO WRAP-UP BEHIND IT — precisely
the state this rule forbids — and no later observation can distinguish that
round from a delivered one, because the evidence that would have distinguished
them is the write that was lost. The daemon MUST surface that condition through
the mechanical attention surface of contracts.md §"Attention surface". The
surfacing is REPORT-ONLY: it MUST NOT gate, block, or authorize any act, MUST
NOT suppress or alter the retry of the undelivered wrap-up, and MUST NOT itself
delete, rewrite, or re-open the round's durable record.

Every opening paste resolves to exactly one of three outcomes. It is
DELIVERED when, on a pane that was not already busy, the runtime is observed
beginning the turn after Enter, or when the payload was observed in the input
and the input is next observed empty. It is FAILED when the daemon can show
that the payload never reached the input: the write itself was refused, or an
observation taken after the paste and before any Enter shows the input empty.
Every other outcome is UNCONFIRMED, including a payload still standing in the
input after the bounded submit retries, a write whose effect the daemon could
not observe, and an observation that could not be taken; an unavailable
observation never makes a paste FAILED. Only a FAILED paste un-opens the
round, as above. An UNCONFIRMED paste MUST NOT un-open it: the daemon MUST keep
the stamped round open, MUST surface the unconfirmed delivery, and MUST retry
completing the delivery on later observations, so a declaration answering a
wrap-up that did land certifies against that round. Completing an UNCONFIRMED
delivery MUST NOT rewrite the round's stamp or raise its certification floor,
and MUST NOT paste the payload again while it may already be queued: a payload
standing in the input is submitted, never re-pasted, and a runtime whose empty
input cannot be proven confirms delivery only by an observed turn start and
never has that payload pasted into it again while that payload's delivery is
unconfirmed. While an UNCONFIRMED wrap-up or expiry-notice paste is held for a
pane, no other daemon payload is pasted into that pane, with the two exceptions
below, and the held attempt stays surfaced; an UNCONFIRMED channel delivery is
held as contracts.md §"Daemon message delivery channel" defines. A
daemon-authored payload that asks the runtime for no turn, such as the `/rename`
command that names a fresh Codex successor after its topic, MUST NOT be held as
an UNCONFIRMED delivery and MUST NOT suppress a later paste: the daemon MUST
prove its outcome by that payload's own evidence (for a Codex rename, the
durable session-index record of §"The fresh Codex successor's proof and
backend report"), never by an observed turn start. When that evidence does not appear within the
replacement's bounded wait, the replacement MUST keep the ready declaration,
MUST surface the unnamed successor, and MUST NOT deliver the resume line. A held
attempt MUST NOT suppress the resume line a replacement delivers to its proven
successor; that resume line is pasted afresh, and its delivery is confirmed by
the successor's observed turn start. A held attempt MUST be released when a
later observation resolves it DELIVERED or FAILED, and MUST be released when its
round closes, so a later paste to that pane — including the resume line after a
restart — is pasted afresh rather than suppressed by the earlier attempt.
Keeping an UNCONFIRMED round open carries one accepted residual exposure: a
`ready` written after the stamp by a session whose paste did not in fact land.
That exposure is bounded by the stamp-before-paste ordering, which keeps any
older or inherited declaration from certifying, and by contracts.md §"The
restart interlock", whose no-busy gates still apply.

A wrap-up MAY instead be delivered through a supported direct channel under
contracts.md §"Daemon message delivery channel". Every rule of this section
applies to it, with its three delivery outcomes as that section defines them
for a channel.

A round carries a CERTIFICATION FLOOR, and that floor MAY rise within the round
— when a declaration expires, per contracts.md §"The restart interlock". A
rising floor never re-opens an escalation band, never authorizes a paste, and
never resets the notified bands.

A delivered round presumes remaining context only falls while the round stays
open; runtime compaction breaks that premise. When the daemon's supervising
loop — never a read-only listing surface — observes a DELIVERED round whose
track's effective remaining context is KNOWN, not stale under the bounded
staleness window, and strictly ABOVE the track's wind-down threshold, it MUST
close that round as RECOVERED: it MUST delete the round's durable record —
the stamp, the notified bands, any recorded expiry floor, and the round-open
identity — together, and MUST NOT touch any state file, MUST NOT keystroke
the pane, and MUST NOT restart anything. The closure is guarded fail-closed
against the round's own in-flight answer: it MUST NOT occur unless the
track's state file is ABSENT — any session-written token (`ready`,
`blocked`, `winding-down`, `done`), however stale, holds the round open, an
unreadable or malformed state file holds the round open exactly as a
declaration would, and only the daemon's own idle marker is treated as
absence. It MUST NOT occur while the track carries a context-compaction latch (per
§"The context-compaction latch"), nor while the round's resume submission is
pending,
and an unknown or stale context reading MUST NOT count as above-threshold.
The daemon MUST re-read every one of these closure inputs immediately before
deleting the record, exactly as it re-checks every authorization input
immediately before a paste; a declaration that appears between observation
and deletion holds the round open. After a recovered-round closure the track
is un-rounded: a later threshold crossing opens a fresh round and every
escalation band MAY fire again, and a declaration written after the closure
certifies nothing, exactly as for a declaration on a track that was never in
a round. One residual is accepted and surfaced rather than closed: a
standing declaration that can neither certify nor expire holds its round
open indefinitely (a `ready` that stands with no delivered round is not this
residual; it is retired under §"Fail-soft posture"), and such a track remains visible through the existing
standing-declaration attention members — except a standing `done`, which
holds its round open by design and renders the quiet `done` status rather
than an attention member, per §"The terminal declaration".

## The escalating wrap-up

The wrap-up is the daemon's only context-exhaustion lever — nothing is ever force-killed — so it
MUST actually escalate rather than repeat. It fires once when a track first
reaches its wind-down threshold (daemon-wide default 50% remaining,
overridable per daemon invocation and per track), then once more as remaining
context crosses each lower ten-percent band (40, 30, 20, 10). Each band fires
at most once per round; the set of already-notified bands is durable, so a
daemon restart never re-sends a band already sent, and several bands crossed
in one observation coalesce into a single message.

Above 30% remaining the message is a suggestion to start wrapping up; at 30%
and below it is an insistent demand to stop and wind down now. Every wrap-up
MUST tell the session, concretely: its current remaining-context percentage;
the exact state-file path and the four values it may write, naming `done` as
the declaration to write when its work is finished and it wants nothing
further; that the plan's
ledger-held state is the successor session's durable read-first source, so
drifted resume state belongs in an appended ledger entry, never withheld;
and the truth that it will be restarted ONLY when it declares `ready`.

A fresh `winding-down` acknowledgement suppresses further wrap-ups — the
daemon never keystrokes into a session that is actively wrapping up. A stale
acknowledgement (older than fifteen minutes) resumes the escalation and
re-reports the track, but it still authorizes nothing: the acknowledgement
buys patience, not an indefinite stall. At 20% remaining and below with
nothing declared, the track is reported loudly as not responding — and still
never acted on.

A `ready` declaration is never voided by intervening session activity; the
restart branch's own settle, busy, and identity gates already prevent killing
a session mid-work. A declaration remains armed until either a verified
settled-idle observation authorizes the restart, or it EXPIRES by exceeding a
bounded maximum age (thirty minutes by default), whichever comes first. Unlike
the restart, expiry does NOT close the round: it raises the certification
floor and deletes the state file (per contracts.md §"The state file", its
"Stale-declaration voiding" rule, and §"The restart interlock") while leaving
the round's durable record, notified bands, and open status untouched — an
expired declaration can neither certify a restart nor persist to be mistaken
for a live one.

When a `ready` declaration expires inside a DELIVERED round, the daemon MUST
send the session one EXPIRY-NOTICE: a message stating that its ready
declaration expired without a verified settled-idle observation, restating the
exact state-file path and the four values it may write, and restating that a
restart requires a fresh ready. The expiry-notice is subject to the complete
guarded-paste predicate that governs a wrap-up, with one difference: its
trigger is the expiry itself, not the below-threshold context trigger, so it
MAY fire at any known context while its round remains open — though a round
closed as recovered before the notice lands sends no notice, the fresh round's
own wrap-up re-teaching the protocol instead. The notice is sent at most ONCE
per round however many expiries the round accumulates, and that bound is
DURABLE alongside the round's notified bands, so a daemon restart never
re-sends a notice already sent. The expiry-notice is a bounded companion to
the escalation, not a band, and it MUST NOT re-open, re-fire, or reset any
notified band. A failed expiry-notice paste MUST NOT un-open the round and MAY
be retried on a later observation within the same round's single-notice bound.
The expiry-notice authorizes nothing. This mechanism is scoped to a DELIVERED
round only, mirroring the void-notice it supersedes; a round-less `ready`
(per §"Fail-soft posture", a `ready` standing on a track with no delivered
round) has no round to expire within and is governed
entirely by the retirement rule of §"Fail-soft posture" — it is neither
expired nor notice-eligible under this paragraph.

In addition to, and without narrowing, the completion retry for an unconfirmed
delivery above, a wrap-up paste whose submission the daemon could not confirm
can leave the daemon's own payload sitting in the composer, and that payload
MUST NOT itself hold the track out of acting. When a later observation, while
the round the payload was pasted for is still open, shows the composer holding
EXACTLY the daemon's retained wrap-up payload (its full text, or the runtime's
collapsed placeholder for a single paste of exactly that payload), and every
other leg of the guarded-paste predicate of constraints.md §"Acting safety"
holds (no busy evidence, no structured gate, a settled input region and
positive pane identity), the daemon MUST re-send the SUBMISSION only. The
retained payload stands in for the empty-input leg and for nothing else. The
daemon MUST NOT paste again, MUST NOT open a new round or notify a new band,
MUST NOT submit a payload whose round has closed, and MUST NOT treat any
composer text other than its retained payload as authority to submit: composer
text the daemon did not author stays governed by the rule that the daemon
never injects over or submits typed input, and a daemon that no longer holds
the retained payload, for example after its own restart, MUST NOT submit
anything on this authority. While its own payload stays unsubmitted for longer
than 10 minutes, the daemon MUST log an event naming the track and stating
that its own wrap-up is pending in the composer; per §"Notify, never block"
the event is emitted on entry and re-arms once the payload leaves the
composer.

## The restart

Once — and only once — a fresh `ready` declaration passes the restart
interlock (per contracts.md §"The restart interlock"), the daemon replaces
the supervised session's pane process through the backend replacement contract
in contracts.md §"The restart interlock" and hands the fresh session exactly one prompt: read the plan state held on this
track's ledger epic and follow it — a prompt that MUST name the track's
repository path and its recorded epic id literally, so a session opening
with no prior context can resolve what to read without opening any plan-tree
file. The abrupt kill is safe precisely BECAUSE of the declaration: the
session asserted it is at a clean stopping point, and only the process is
replaced — every file, worktree, branch, and commit on disk survives.

Every step of the restart is a hard gate. A failed tmux native replacement
proven not to have replaced the process MUST preserve the `ready` declaration
and surface the failure so the next observation may retry, unchanged from the
tmux-only contract. A herdr failure proven to precede any
termination attempt is surfaced and the `ready` declaration is PRESERVED so the
next observation may retry; a declaration is never silently destroyed. After a
herdr termination attempt, a failed or uncertain replacement instead retains
its durable guarded-replacement record and declaration as diagnostic evidence;
the declaration MUST NOT authorize another termination. Recovery is limited to
the verified launch-only continuation defined in the restart contract. A respawn that SUCCEEDED
but whose fresh session is never recognized has already destroyed the
predecessor, so it consumes the kill authorization: the round is held open
for submission retry only, and any further kill requires a genuinely fresh
`ready` (per contracts.md §"The restart interlock"). When the fresh session comes up but the resume
prompt fails to submit, the daemon retries the SUBMISSION ONLY, never a
second kill: re-killing stays gated on a fresh `ready` alone, so the retry
can never escalate. A fresh session that comes up showing a structured gate
is never keystroked; it is surfaced as waiting on a human, with the round
held open.

A session that declares `ready` and then resumes work — narrates further, emits
more turns, streams stop-hook output — keeps its declaration armed; the restart
branch's settle and busy gates prevent a kill mid-work without requiring any
activity-based clearing. The declaration is cleared only by a successful
restart or by exceeding its bounded maximum age (per contracts.md §"The state
file", its "Stale-declaration voiding" rule). Withholding the restart of such a
ready hold remains unbounded under §"Fail-soft posture", but the daemon MUST
NOT leave such a hold unreported past the ready-hold window: a certifiable
`ready` withheld by the busy, not-idle, unsettled or pane-identity condition
(the immediate pre-act identity re-check) for longer than that window MUST
produce a report-only diagnostic event naming the track and every holding
condition observed, repeated at most once per window while the hold persists
(per contracts.md §"The restart interlock", its "ready-hold event" rule); the
event changes no gate and authorizes nothing.

**The host memory floor.** A seat replacement adds a whole new session to a host before its predecessor's memory is released, so the daemon MUST NOT start one while the host is short of memory. Immediately before every seat replacement the daemon starts — the herdr guarded replacement transaction and the tmux native replacement alike, and any replacement path added later — it MUST take one fresh reading of the host's available memory (`MemAvailable` in `/proc/meminfo`) and memory pressure (the `some avg10` value in `/proc/pressure/memory`) and compare it with the host's memory floor. The floor is a minimum available memory and a maximum pressure, and the replacement proceeds only when the available memory is at or above the minimum AND the pressure is below the maximum. The floor values MUST be read from the host load-floor file, `/etc/livespec/host-load-floor.json`, and MUST NOT be literals in the daemon: each host's file is rendered from THAT HOST's own committed load-floor entry in the fleet gitops inventory (the same inventory that renders `/etc/livespec/fabro-factories.json`), because hosts differ in memory and swap and need different floors; on each host that one rendered file is the single floor source that the daemon, the dispatcher's ticket helper and the operator load guard all read, so none of them can drift from the others. Below the floor the replacement is HELD, not failed: the daemon MUST NOT terminate, respawn, keystroke or re-brief the session, MUST preserve the `ready` declaration and the open round, and MUST re-take the reading on a later tick, proceeding once a reading clears the floor. Holding never weakens the restart interlock: a held seat is still replaced only on a certifiable `ready`, and a cleared floor authorizes nothing the interlock does not. A hold MUST be visible: the track's row names the memory-floor hold and the reading that caused it, and the daemon MUST journal one `restart-held-by-memory-floor` event naming the track, the reading (available memory and pressure) and the floor it failed, on entry to the hold, and one on release, never one per tick (per §"Notify, never block"). The floor gates seat replacement only; it does not gate observation, wrap-up injection, submission retries into an already-running session, or alerts. When the host load-floor file is absent, the daemon applies no floor and MUST surface that once, edge-triggered, as an unconfigured-floor notice, so a host without a floor is visible rather than silently unguarded. When the file exists but cannot be read or parsed, or a memory reading cannot be taken, the daemon MUST treat the reading as below the floor (hold) and surface the failure once, edge-triggered: an unknown reading never authorizes a replacement. Taking the reading MUST be bounded and MUST NOT delay other tracks' observation.

After a respawn succeeds, the daemon retains enough live observation to
recognize a fresh session that has consumed no context and whose composer
holds exactly the track's expected resume text. If those facts remain
continuously observed for a bounded 60-second post-respawn floor, the daemon
MUST surface the track as report-only NEEDS YOU attention, even when the
ordinary `resume_pending` retry state is absent. The daemon MUST re-evaluate
this condition on every supervision tick, MUST emit the attention edge only
on entry, and MUST clear and re-arm it when the session begins work or the
composer no longer exactly matches the expected resume text. An unknown or
unreadable context signal MUST NOT satisfy the no-consumption predicate.

That SAME evidence independently authorizes a submission-only self-heal, and
the 60-second floor does not gate it. On ANY acting tick where the daemon
observes that evidence — a fresh post-respawn session that has consumed no
context, that carries no busy evidence, and whose composer holds EXACTLY the
track's expected resume text — the daemon MUST record the round-scoped
`resume_pending` retry state and re-send the SUBMISSION only. All three legs
are required: a session reading busy has not been shown to be stranded, and
MUST NOT be keystroked on this authority. A fresh session showing a structured
gate is never keystroked either; it is reported as waiting on a human with the
round held open, exactly as above. The daemon MUST NOT re-paste the resume
text, which is already in the composer; MUST NOT respawn the session; MUST NOT
terminate the session; MUST NOT write a declaration; and MUST NOT treat any
composer text that is not an exact match as retry authority. The retry is
round-scoped so it cannot outlive its round, and it can never escalate to a
second kill: the fresh session-written `ready` declaration remains the sole
restart authorization. The 60-second-floor NEEDS YOU surfacing above is
unchanged and applies independently of whether this self-heal has fired;
neither condition authorizes or suppresses the other.

### The fresh Codex successor's proof and backend report

This subsection governs the daemon's own replacement of a Codex track through
the guarded replacement of contracts.md §"The restart interlock", once it has
launched a fresh Codex successor into the retained shell. After the launch,
the daemon submits `/rename <name>` to the successor, where `<name>` is the
track's derived session name under §"Session-name derivation". The daemon MUST
treat the rename as confirmed only when, within the replacement's bounded
wait, the Codex session index records a thread created by this launch (one
absent from the index when the launch attempt was recorded) whose name equals
EXACTLY `<name>` and whose identifier differs from the predecessor's session
identity.

Once the rename is confirmed, the daemon MUST report that thread's identifier
to the terminal backend as the agent session of the replacement record's pane
on its recorded backend instance, and of no other pane, for a backend that
accepts such a report. The daemon MUST report a Codex agent session only for a
pane in which it launched that carrier itself, as named by its own durable
replacement record. It MUST NOT report one for a pane read from any process's
environment: a Codex session thread hosted by a shared runtime server runs in
a process whose environment can name an unrelated pane. A report the backend
rejects MUST be surfaced, and MUST NOT by itself void a proof that otherwise
holds.

The daemon MUST accept the successor as proven when all of the following
hold: the predecessor process is gone; the successor is a process started by
this launch in the same retained shell, pane and backend instance; the rename
is confirmed as above; and the session identity the daemon binds to the
successor (and reports to the backend, where the backend accepts such a
report) is exactly the thread the index named for `<name>`. It MUST accept that proof even when the successor holds no
rollout file open, because a successor whose thread is hosted by a shared
runtime server holds none. The proof MUST NOT rest on a rollout file's write
time or recency, and MUST NOT open, read, parse or hash any rollout body.
Every other condition of contracts.md §"The restart interlock" still applies:
the ready declaration is consumed only after the proven successor's verified
continuation, and no recovery path applies the predecessor's authorization to
the successor.

When the rename is not confirmed within the bound, the daemon MUST report no
agent session to the backend for any pane, and the successor MUST stay
unproven. The replacement then keeps the ready declaration, surfaces the
unnamed successor and delivers no resume line, exactly as §"The supervision
round" requires, and that declaration authorizes no further termination or
launch.

### The launch profile

A restart replaces the pane's process; nothing else about the change is
free unless the daemon makes it so. The daemon MUST record a per-track
launch profile — `{harness, model, wrapper|null}` — read from the live
supervised session, and MUST re-assert that profile on every restart of
that track, so a restart never silently changes the runtime, model, or
wrapper a track runs under. Without this, a bare relaunch takes whatever
default the runtime's own configuration currently holds, which silently
downgrades a hand-picked model and, for a track launched through an
env-wrapper, silently converts it from a local runtime back onto the
cloud API.

The daemon MUST read the profile from `/proc/<pid>/environ` and
argv/parent-chain as the primary source, and MAY use the statusline's
rendered model name only as a mismatch-detection verification signal,
never as the primary source and never through a display-name-to-launch-token
lookup table. The daemon MUST capture the profile at adoption (first join)
and MUST re-check it at wrap-up time. That obligation is retained in full: it
is what lets a row whose pane acquired a model token after adoption self-heal
on the wrap-up round that necessarily precedes any restart of it. The
guarantee it carries is narrower than the obligation, and is stated here
rather than left to be inferred: a launch profile records the model the track
was LAUNCHED with, and re-check at wrap-up honors a mid-session change ONLY
where a permitted source expresses it.

For a Claude-harness track the session's own conversation transcript is an
ADDITIONAL permitted source for the profile's model: the model TOKEN carried on
the latest TOP-LEVEL assistant message, where a top-level message is one that is
NOT a sidechain or sub-agent message. This token is a real launch token, not a
rendered display name, so admitting it does NOT weaken the prohibition above: the
statusline stays verification-only, and no display-name-to-launch-token lookup
table is introduced. Sidechain and sub-agent assistant messages MUST be excluded
when selecting the latest top-level model, because a session mixes models across
its main thread and its sub-agents.

The transcript token expresses a mid-session model change — and the daemon MUST
prefer it over argv and environ — ONLY where its BASE model token differs from
the base model token named by the launch source. The base model token is the
model token with any trailing bracketed context-window or variant suffix (for
example `[1m]`) removed. Where the transcript names the SAME base model as the
launch source, the daemon MUST retain the launch source's token, so a
context-window or other launch-token variant recorded at launch is never
silently dropped by a source that does not carry it. Where the transcript
expresses a differing base model, the daemon MUST record that transcript token as
the profile's model, so a restart preserves the model the track is actually
running rather than the model it was launched with.

The transcript source MUST be fail-soft. An absent, unreadable, or unparseable
transcript, or one exposing no usable top-level assistant model token — a
synthetic or otherwise non-token model value is not usable — MUST NOT be treated
as a mismatch and MUST fall back to the launch source (argv, else environ)
exactly as today. This transcript source applies to the CLAUDE harness ONLY.

For a Codex-harness track, the live session's Codex state database is an
ADDITIONAL permitted source for the profile's model. The ACTIVE DATABASE for
this purpose is the numerically greatest regular file named
`state_<positive-integer>.sqlite` under the live carrier's non-empty
`CODEX_HOME`, or under the daemon account's standard `~/.codex` when that
variable is absent. A lower-numbered candidate MUST NOT be consulted when the
active database is unusable, because an older database can retain a stale row.
The daemon MUST query the database read-only and MUST accept `threads.model`
only from the row whose thread identifier exactly equals the track's already-
established live Codex session identifier and whose `cwd`, after path
resolution, equals the supervised repository.

The state-database source MUST consume the exact live session identity already
established from process evidence under §"Supervised runtimes"; it MUST NOT
independently choose among open rollout paths, walk upward into an ancestor
carrier, or descend through a nested carrier to obtain an identity. Where no
single session identity has been tied to this track — including an ambiguous
set of rollout candidates with no indexed identity that selects one — the
source is unusable. Establishing the identity MAY inspect rollout-path filename
metadata but MUST NOT open, read, parse, or hash any rollout body. A state-
database token is a launch token rather than a rendered display name: admitting
it MUST NOT make the statusline a primary source and MUST NOT introduce a
display-name-to-launch-token mapping.

Independently of how its live identity was established, the daemon MUST NOT
read a Codex session's rollout body to derive a runtime model.

Where the state-database token's BASE model differs from the base model named by
the argv-or-environ launch source, the daemon MUST prefer the database token at
adoption and at the wrap-up re-check, so a mid-session Codex model change
survives restart. Where both sources name the SAME base model, the daemon MUST
retain the launch-source token, so a context-window or other launch-token
variant is not silently discarded.

The Codex state-database source MUST be fail-soft. An unresolved Codex home; an
absent, non-regular, unreadable, or locked active database; a schema without the
required table or fields; an undetermined or ambiguous live session identity; a
missing exact session row; a row whose `cwd` does not resolve to the supervised
repository; or a null, empty, synthetic, or otherwise unusable model token MUST
NOT be treated as a mismatch and MUST fall back to the launch source (argv,
else environ) exactly as today.
This source applies to the CODEX harness ONLY and MUST NOT change the Claude
transcript source.

Where a session's current model is expressed in no permitted source, the
daemon MUST re-assert the recorded launch model. This is deliberate, not an
oversight, and the divergence MUST be SURFACED: it MUST NOT be silently
honored and MUST NOT be silently lost. The mismatch-detection signal
permitted above is the intended surfacing mechanism. Because that signal is
fail-soft — an unreadable rendered model is not a mismatch and MUST NOT skip
a restart — surfacing MUST, for a track whose profile carries a recorded
verification baseline, distinguish having read the verification signal and
found agreement from not having read it at all; a daemon that cannot tell
those apart reports silence as agreement at exactly the moment the surfacing
is owed.

That obligation is scoped to baselined tracks because a track carrying no
recorded baseline has nothing to compare a rendered model against, so no
agreement can be claimed for it either way. The scoping records what the
daemon can honor and MUST NOT be read as ratifying the unbaselined
population as acceptable: for such a track the daemon MUST NOT be reported,
or relied upon, as having verified the re-asserted model.

The `harness` value MUST be treated as an open string in storage, so an
unrecognized future harness can be recorded with no schema change; DISPATCH
MUST enumerate known harnesses, and the daemon MUST relaunch a track only
for a harness it recognizes. An unrecognized or unadoptable harness's
profile MUST be surfaced report-only and MUST NOT be used to construct or
guess a relaunch command — aiming one runtime's relaunch command at
another runtime's pane destroys the session.

A track's mapping row that carries no launch profile MUST continue to
relaunch with exactly the COMMAND it uses today; this is fail-soft by
construction and requires no migration of existing rows. Fail-soft governs the
launch COMMAND, not the launch ENVIRONMENT: the set-or-scrub rule below applies
to such a relaunch too, and the two do not conflict, because the environment
delta never alters the command. A launch profile MUST NOT record
any secret or token value; it records only the harness, the model token,
and the wrapper's path, since the wrapper itself owns its own secrets.

Every Codex launch command that the daemon or the sanctioned out-of-band
relaunch composes MUST run Codex with its startup update check disabled, by
passing the Codex configuration `check_for_update_on_startup=false` on that
invocation. This covers a fresh successor, a resume, and a relaunch of a Codex
row that carries no recorded launch profile. Codex caches a newer upstream
release on one launch and opens the NEXT launch at an update picker. A
launched successor waiting there shows a structured gate, which §"The restart"
forbids keystroking, so the replacement or relaunch would wait forever. The
override is a fixed part of the Codex launch command, not a launch-profile
field. It MUST NOT be recorded in a captured launch profile, and re-capturing
a profile from a running successor that carries it MUST NOT make the next
launch carry it twice. For a Codex row that carries no launch profile, this is
the one sanctioned difference from the rule above that such a row relaunches
with exactly the command it uses today.

On every relaunch — of EVERY harness, and INCLUDING a relaunch of a row that
carries no recorded launch profile — the daemon MUST explicitly set or unset
`ANTHROPIC_MODEL`, `ANTHROPIC_SMALL_FAST_MODEL`, and the `CLAUDE_CODE_*`
context-limit override environment variables rather than passively
inheriting them — set to the recorded profile's values for a wrapper/local
track, and unset otherwise — which covers both a cloud track with no wrapper
recorded and a track carrying no profile at all. A wrapper's
own deference to an inherited value (e.g. `ANTHROPIC_MODEL="${ANTHROPIC_MODEL:-default}"`)
means a leaked inherited value would silently win over the wrapper's own
intended default, so passive inheritance is the failure mode in both
directions. No harness is exempt. The controlled variables are named for one
runtime, but a relaunch of any harness inherits whatever the daemon's own
environment holds, and it is that inheritance the rule exists to prevent.

A stale or corrupt profile — a recorded wrapper path that is missing or
not executable, a recorded model token the runtime rejects, or a
harness/wrapper mismatch — MUST be surfaced and MUST cause the daemon to
skip that restart rather than silently falling back to a default-model or
default-wrapper launch, which would reproduce the exact silent-downgrade
defect this section exists to close.

### The sanctioned out-of-band relaunch

A seat is sometimes relaunched outside the daemon's ready-gated restart: by a
coordinator, by the maintainer, or from the bottom pane. The overseer MUST
ship exactly ONE sanctioned entrypoint for that relaunch, and the operator
skill MUST name it as the procedure for relaunching a seat outside the daemon.
The entrypoint is an OPERATOR surface invoked on purpose for one named track.
It is not a daemon act and MUST NOT widen any daemon acting rule of
constraints.md §"Acting safety". It starts a tracked session, so it MUST
record the start-intent of §"Non-interference with tracked work" before its
launch, and MUST amend it with the outcome.

The entrypoint takes a tracked plan topic and a target pane, and optionally a
runtime, model and wrapper to launch in place of the track's recorded launch
profile. The optional values are how a seat whose recorded profile names a
runtime it no longer runs is repaired. It MUST refuse before writing any
record or sending any input when any of the following holds:

- the topic names no mapped track, or the track records no epic id;
- the target pane does not exist on the track's recorded backend instance;
- the target pane's foreground process is anything other than an idle
  interactive shell at its prompt, so a pane holding a live agent (including
  the track's own live session) or any other running program is never typed
  into and never replaced;
- the profile to launch, recorded or named, names an unrecognized harness or
  is stale under §"The launch profile" (a missing or non-executable wrapper, a
  model token the runtime rejects, or a harness/wrapper mismatch).

Otherwise it MUST launch that profile's runtime by submitting its launch
command at the target pane's shell prompt, setting or scrubbing the launch
environment exactly as §"The launch profile" requires of a daemon relaunch. It
MUST NOT terminate any process, and MUST NOT write, consume or clear a
state-file declaration.

When the launched runtime is Codex, the entrypoint MUST then submit
`/rename <name>` in the launched session, where `<name>` is the track's derived session
name under §"Session-name derivation". It MUST treat the relaunch as
successful only once the Codex session index shows a thread created by this
launch named EXACTLY that name, within a bounded wait the entrypoint states in
its output. Once that is confirmed, it MUST report that thread's identifier to
the terminal backend as the agent session of the target pane only, for a
backend that accepts such a report. When the rename is not confirmed within
the bound, the entrypoint MUST report a failure naming the pane and the thread
it observed, if any, MUST report no session to the backend, and MUST leave the
track's mapping row unchanged. A launched runtime other than Codex submits no
rename.

After a successful launch, the entrypoint MUST deliver the resume prompt of
this section, naming the track's repository path and recorded epic id. It MUST
then re-bind the track's mapping row to the target pane, the launched
session's identity, and the launched launch profile (harness, model and
wrapper, or null when none was launched), so no binding to another pane or
another runtime remains. The daemon's own identification of the session may
land before or after this re-binding. Both rest on the same exact evidence, so
neither can bind the track to a different session.

On a terminal backend that pastes input, the entrypoint MUST paste the resume
text at most ONCE per relaunch, and only after the launched session's composer
is observed at its input prompt with no structured gate and no busy evidence.
Every later attempt within the same relaunch, after a paste that may have
landed, MUST be an Enter-only submission: a just-launched session can show an
empty composer for a while and then draw buffered input all at once, so an
empty reading after a paste does not prove the paste failed and MUST NOT
authorize a second paste. The entrypoint MUST bound its submission attempts
and state that bound in its output. When the resume's submission or the
mapping row's re-binding is not confirmed within the bound, it MUST end with
the failure outcome `resume_or_rebind_failed` amended onto its start-intent,
MUST leave the track's mapping row unchanged, and MUST leave at most one copy
of the resume text in the composer.

## The keep-going nudge

The wrap-up addresses a session running LOW on context. The inverse failure
is a session that stops EARLY — idle while still comfortably above its
threshold, wasting headroom it still has. The daemon closes that gap with a
single keep-going nudge per idle episode: when a tracked session has been
CONTINUOUSLY idle for at least one hour, is above its threshold, is not
waiting on a human, and has made no declaration of its own, the daemon pastes
one message telling it to continue, and writes `idle-with-context-left` to
the state file as a note to itself so the same episode is never re-nudged.

The nudge MAY instead be delivered through a supported direct channel under
contracts.md §"Daemon message delivery channel", which keeps every obligation
in this section.

The rejected-state notice of contracts.md §"The state file" MUST be delivered
under the informational-paste safety floor below, with all three busy legs. It
does NOT wait for this nudge's one-hour continuous-idle floor or its
above-threshold condition: a settled idle input on any tick suffices. It MAY
likewise be delivered through a supported direct channel.

That daemon-written value authorizes NOTHING — it gates only the
once-per-episode nudge, never a restart. It is edge-triggered and
self-clearing: the daemon removes it the moment the session works again,
re-arming a future episode, and the removal only happens while the file still
holds the daemon's own value — it can never clobber a declaration the session
wrote in the meantime. The one-hour floor is load-bearing: the nudge pastes
and submits text, so firing it on a session merely between turns would
interrupt active work. The continuous-idle clock is in-memory and resets on
any activity; a daemon restart resets it too, which only ever DELAYS a nudge
— the safe direction. The nudge's escape hatch is the existing `blocked:`
value, for a session that is genuinely waiting on a human but can only say so
in prose.

One further nudge exists, and it is aimed at the PAIR. When a worker and its
supervisor have BOTH shown no observable progress continuously past a
bounded floor, and NEITHER presents a human wait — no structured gate, no
runtime report of waiting on a human, no standing `blocked:`, and neither is a
done track per §"The terminal declaration" — and the
supervisor has no open round and no fresh wind-down acknowledgement, the
daemon MUST paste ONE nudge into the SUPERVISOR, because the supervisor owns
direction for the pair. The message MUST name the stall and its duration,
MUST name the worker's coordinates, and MUST offer exactly two honest outs:
resume driving, or surface and declare the human question actually being
waited on.
Progress, for this purpose, is the runtime's own authoritative report that
it is working, or the remaining-context reading moving between two KNOWN
readings. A pane's displayed TEXT MUST never count as progress evidence for
a session whose runtime reports authoritatively: displayed content routinely
contains busy-looking text, and evidence that deliberately over-fires is safe
only where it SUPPRESSES an act, never where it AFFIRMS progress and thereby
suppresses detection.

Keystroke-bearing informational pastes share one safety floor: a paste MUST
remain suppressed while its target is generating, changing, gated,
runtime-reported as waiting on a human, sub-agent-busy, blocked or done by
declaration,
or missing the input evidence that act requires — except that the
generating, changing, and sub-agent-busy legs do NOT apply to the low-context
wrap-up or its expiry-notice tail, which are delivered into a busy pane whose
input region is positively empty and settled, per §"The supervision round".
The keep-going nudge, the rejected-state notice, the pair-stall nudge, and the
charter reminder keep all three legs. Background-shell evidence
alone does not suppress an otherwise qualified informational paste. Exactly
six acts apply that rule: the low-context wrap-up for any supervised
entity, using the runtime-specific predicate in §"The supervision round";
the once-per-round expiry-notice of §"The escalating wrap-up", which is that
wrap-up's round-scoped tail and fires under the wrap-up's own complete
guarded-paste predicate rather than an independent one; the
idle-with-context-left keep-going nudge specified above; the
once-per-rejected-value rejected-state notice of contracts.md §"The state
file"; this bounded
pair-stall nudge into the supervisor; and the bounded charter-reminder paste
into a stalled reserved-entity picker in §"The stalled-picker charter
reminder". The sixth member is the sanctioned exception of constraints.md
§"Acting safety" and is the ONE act that INVERTS this floor's gated and
human-waiting legs: it fires ONLY while its target is gated and waiting on a
human, and it may fire with a standing `blocked:` declaration. It remains
subject to every leg of this floor not named in this sentence, and the
inversion MUST NOT be read as relaxing the floor for any other act. That enumeration is the same
membership and the same count as constraints.md §"Acting safety"; the two
MUST be amended together.

The pair nudge retains its stronger guard: the paste MAY land while the
supervisor's only busy evidence is a background command at its prompt, and
only then — at a positively verified empty and settled input prompt. It MUST
NOT land while a round is open or a fresh acknowledgement stands, and it MUST
land only for a runtime whose empty input state is positively verifiable. A
runtime whose input box cannot be verified empty MUST never be pair-nudged;
the Codex structural predicate admitted for low-context wrap-ups MUST NOT
weaken this guard. The nudge MUST fire at most once per stall episode. An
episode that ends only in the nudge's own answering turn does NOT reset the
escalation: on the second consecutive episode ending in a nudge, the daemon
MUST skip the paste and MUST surface the pair to the operator, naming both
panes, the supervisor first, and the fact that the autonomous remedy has
already failed.

Two residuals are accepted and stated rather than hidden. A human question
posed only in scrolled-off prose is invisible to this guard set, which is
why the nudge's own text instructs the supervisor to convert such a wait
into a declared block. And a structured gate whose rendering escapes the
gate detector is not suppressed by it.

## The stalled-picker charter reminder

One daemon informational act pastes into a pane that is BOTH gated and
waiting on a human, and it is the sanctioned daemon exception named in
constraints.md §"Acting safety". It exists because a reserved-entity session
parked on its own structured picker is not waiting on the overseer for an
answer — it is waiting on itself to apply its own charter — and the remedy is
to say so, not to answer for it. The exception MUST NOT be widened to any
other daemon act, pane class, or topic class.

The act fires only under ALL of the following, and every clause is part of
one complete independent predicate:

- The topic is in the reserved entity namespace — the `-supervisor` suffix.
  It NEVER applies to an ordinary worker topic.
- The target pane is positively identified as that track's supervised
  session. That identity gate holds upstream in the evaluation precedence
  rather than inside this act.
- The daemon's DERIVED row status for the track is `blocked:human`. That is the
  daemon's own classification, NOT one of the four values a session may write,
  per §"Out-of-band state declaration"; the daemon reaches it from several
  distinct kinds of evidence and this section does not enumerate them. In every
  state where THIS act can fire, the classification is reached from live gate
  evidence, optionally alongside a standing `blocked:` declaration — which
  follows from the open-picker clause below rather than from any property of
  the status itself. The act therefore requires no declaration
  from the session, and in its common case the session has made none.
- Live gate evidence shows an OPEN structured picker. Whether a runtime can
  raise a structured question MUST continue to be derived from live gate
  evidence, never inferred from a runtime name, launch mode, or policy, per
  §"Out-of-band state declaration".
- The pane capture has been UNCHANGED for longer than a bounded floor, thirty
  minutes. The clock is capture-stability-keyed, not wall-clock from any
  declaration.
- The paste fires at most ONCE per stall episode. An episode ends when the
  pane capture changes for a reason OTHER than the daemon's own paste, or when
  the status the daemon EVALUATES for the track on a later tick is no longer
  `blocked:human`. That evaluated status is the input to this act, and is not
  necessarily the status finally published on the track's row. The daemon MUST
  therefore recognize the echo of its own paste and MUST NOT treat it as the
  human activity that re-arms the act.

The payload is delivered as ONE atomic paste and is NEVER SUBMITTED: no
`Enter`, no selection keystroke, no digit. The daemon does not choose from a
picker and MUST NOT answer one. That is the property separating this act from
every other daemon keystroke-bearing act, each of which pastes AND submits.

The message states only that the supervisor should re-read its own pending
picker, perform charter-authorized mechanical unblocks itself, and declare
`blocked: <reason>` only when the unblock genuinely requires a human
decision.

The act AUTHORIZES NOTHING. It writes no state file, calls no restart path,
never closes or re-opens a round, never raises or lowers a certification
floor, and never answers the picker. A failed paste is surfaced to the
operator and does NOT mark the episode handled, matching the failed-paste
posture of the wrap-up and the keep-going nudge. Ambiguous evidence — an
unreadable gate reading, an unresolved pane, an unsettled capture — resolves
to inaction.

## Wind-down expiry on context recovery

A supervised session's own wind-down intent is scoped to the CONDITION that
produced it — remaining context at or below the wind-down threshold — and
MUST be treated by that session as EXPIRED once that condition no longer
holds — except when the latest wrap-up the session received stated that a
context compaction requires a restart (per §"The context-compaction latch"):
that intent is scoped to the compaction, not to the remaining-context reading,
and MUST NOT be treated as expired on context recovery. The runtime's own auto-compaction is the recognized case: it can
restore a session's remaining context to strictly above its wind-down
threshold at any point after the session formed a wind-down intent, and it
does so by an event that can also erase the session's own memory of having
formed that intent. A session MUST NOT decide this from recollection; it
MUST decide it from durable, on-disk evidence — its own state file —
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
declaration — by deleting or overwriting its own state file — and only
THEN resume its own pending work from its own most recently appended
ledger-held plan-state entry, without waiting for a restart and without
re-declaring wind-down on account of that stale declaration alone. This
ordering is normative, not incidental: clearing first ensures no window
exists in which the session is both actively working and still carrying an
apparent restart authorization. A session evaluates this condition
whenever it next takes a turn — there is no separate poll — so a session
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

## The context-compaction latch

Remaining context falls monotonically within one context generation, so a
RISE in a track's remaining context has exactly two causes: the session was
replaced, or the runtime compacted its context in place. A compacted
generation is a summary of the one the daemon was winding down, and it MUST be
treated as EXHAUSTED: the obligation to wind it down and restart it stands at
any later percentage.

The daemon's supervising loop (never a read-only listing surface) MUST latch a
track as RESTART-REQUIRED when it observes a KNOWN remaining-context reading
that exceeds the LOWEST known reading observed under the same live session
identity by more than a bounded tolerance (five percentage points), while the
live session identity at the pane is PROVABLY that same identity. Rises within
the tolerance are noise and do not move the lowest reading back up. A
changed live session identity is the successor of a completed restart and
MUST clear the latch. An unprovable identity, an unknown or unreadable
reading, or a rise within the tolerance MUST change nothing, in either
direction. No elapsed time and no context reading clears the latch. The latch
MUST be durable across daemon restarts, held with the track's own durable
record rather than in memory.

The latch is an OBLIGATION, never an authorization. While it stands:

- the track owes the wind-down at ANY remaining context: the wrap-up trigger
  of contracts.md §"The wrap-up injection" fires for it, and band selection
  treats it as at its threshold unless it is genuinely lower;
- once per latch, the delivered round's already-notified bands are re-armed,
  so a wrap-up is delivered even when every band was already spent; the
  round's open time and certification floor MUST NOT move;
- a latched track's round MUST NOT be closed as recovered under §"The
  supervision round", whatever its reading;
- every wrap-up delivered under the latch MUST state that a context compaction
  was detected and that a restart is required regardless of the remaining
  context the session sees, and MUST name the latch in its context figure — the
  track's wind-down threshold and the daemon's effective live reading together,
  per contracts.md §"The wrap-up injection" — never a single bare ctx
  percentage.

The cardinal rule is unchanged: only the session's own fresh certifiable
`ready` restarts it, under the unchanged restart interlock. Each latch is
reported once, as an edge-triggered alert naming the track, both session
identities compared, and the readings.

## The terminal declaration

A session whose work is COMPLETE — its plan finished, archived, or otherwise
ended, and nothing further wanted from it — MUST be able to say so honestly.
It does so by writing `done` (optionally `done: <one-line summary>`) to its own
state file. `done` means: my work is complete, I want nothing further, do not
restart me. It is the terminal declaration, and the daemon MUST honour it as a
valid session declaration, never as a malformed one. It exists because none of
the other three values says this truthfully: `ready` authorizes a restart
nobody wants, `blocked:` asks a human for something, and `winding-down` is an
acknowledgement that goes stale.

A standing `done` declaration MUST NOT authorize a restart under any
circumstances: it is not `ready`, it can never certify against a round, and it
never raises or lowers a certification floor. The daemon MUST NOT restart a
track holding `done`, however low its remaining context falls and however long
it stays idle.

While `done` stands, the daemon MUST NOT paste a wrap-up to that track at any
escalation band, whatever made that band due — MUST NOT
send it the keep-going nudge, and MUST NOT report it as not responding. Unlike
`winding-down`, `done` has no freshness window: it does not go stale with age,
and no amount of time alone resumes the escalation.

A DONE TRACK is a track holding a standing `done` declaration, or a plan track
whose plan directory is archived (or gone) while its recorded session still
exists (running or exited), per §"Track discovery and the mapping store". The
daemon MUST perform NO
act on a done track: it MUST NOT paste, type, or deliver any daemon message to
it by any transport (a wrap-up at any band, a keep-going or pair-stall nudge, a
notice, a resume or a resume retry, a compaction-latch wrap-up, or the release
of a held delivery), MUST NOT send it any keystroke, and MUST NOT restart,
respawn, or replace its session. The daemon MUST NOT close, kill, or archive a
done track's session or pane: it stays open so the maintainer can read its
wrap-up. Every observation of a done track is read-only, exactly as the `list`
path is: the daemon MUST NOT write, delete, void, or expire that track's state
file, and MUST NOT close, delete, or advance its round record; its own event
log and the edge-triggered bookkeeping of its alerts remain permitted. A done
track is therefore spent zero model turns by the daemon for as long as it
stays done. This prohibition takes precedence over every clause of this
specification and of contracts.md that would otherwise authorize or require
an act on a done track, or a write to its state file or round record.

A done track MUST NOT be an attention member through any REPORT-ONLY
member of §"Fail-soft posture" — the low-context shield, the busy-shield
no-progress member, the stale-context-knowledge member, the standing
declaration that cannot certify, and the declaration standing on a track never
in a round — nor through the non-responding, escalation-exhausted, or gone
session members: its inability to certify, and its silence, are its meaning,
not a dead end. For a track that is done by its own declaration, every OTHER
member still applies: a malformed or path-aliased state value, a restart whose
resume has not yet submitted, a wait-inventory mismatch, and live gate
evidence. A path-aliased `done` is not a `done` declaration at all; it is
treated as no declaration and surfaced, exactly as any other aliased value. A
track that is done because its plan is archived is an attention member ONLY
through live gate evidence: whatever its state file holds — nothing, a stale
declaration, or a malformed or path-aliased value — it renders the quiet
`done` row.

The daemon MUST NOT void, delete, overwrite, or expire a `done` declaration on
any evidence — not on observed generation, not on background activity, not on
idleness, and not on age. A session that resumes generating while holding
`done` keeps its declaration and its track stays done.

A done track is RE-OPENED only explicitly, and only once it holds no standing
`done` declaration AND its plan directory is not archived. Its session (or the
maintainer) clears a `done` by deleting the session's own state file or
overwriting it with a value other than `done`. A
plan directory moved back out of `plan/archive/` therefore re-opens its track
only if the track holds no `done`, per §"Track discovery and the mapping
store". A session that is handed new work
after declaring `done` MUST clear its own `done` declaration BEFORE resuming
that work, so no window exists in which it is working while still asserting it
wants nothing. Once re-opened, the track is supervised exactly as an
undeclared track is, from its round's existing state: the re-open MUST NOT
raise a certification floor, delete the round's durable record, or reset its
notified bands.

Live gate evidence still outranks `done` for REPORTING: a done track whose pane
shows an open structured picker is waiting on a human whatever it declared, and
MUST be surfaced as a blocked attention member rather than the quiet row.
Surfacing it is report-only: the daemon MUST NOT act on that track while it
remains done.

The operator surface MUST render a done track as a QUIET row — a
distinct `done` status that is NOT an attention member, does not count toward
the attention badge, and is never rendered as broken — both while its session
is still running and after its session has exited. An exited session holding
`done` MUST NOT be reported as a gone session; its row MUST say the session
has exited. A `done` declaration standing on a track whose session has exited
is an orderly ending.

## The watch-set declaration

Which repositories the overseer supervises is DECLARED by the operator in a
single home-directory file — never derived. An entry is admitted to the
watch-set only when its checkout exists on disk and contains a plan
directory; an entry that fails admission is silently inert rather than an
error, so declaring a repository before it is cloned is safe.

The watch-set is deliberately NOT derived from the mapping store's existing
rows: discovery has to scan repositories with zero assigned tracks in order
to surface their unassigned plans at all. Declaring a repository that has no
session assigned yet is the normal case — that is exactly how a brand-new
plan becomes visible as startable.

A repository the operator wishes to keep unsupervised MUST be declared as
HELD — a recorded entry in the same declaration carrying at minimum the
repository path, a non-empty reason, and the timestamp at which the hold was
declared — rather than by removing the repository's active watch-set entry.
Representing a deliberate non-supervision by deletion alone MUST NOT be the
mechanism, because deletion is indistinguishable from a repository that was
never watched or one removed by accident.

A held repository MUST NOT be admitted to the watch-set: its supervision
behavior is unchanged — it is not watched, no track is discovered for it, and
no session of it is restarted. Only its REPRESENTATION changes.

A repository MUST NOT be simultaneously an active watch-set entry and a held
entry. The DECLARED held-set and the EFFECTIVE watch-set MUST NOT silently
disagree: a repository declared in both MUST be surfaced as a conflict rather
than silently resolved. While the conflict stands the repository is not
admitted, per contracts.md §"Durable stores", and the surfaced conflict is what
keeps that outcome from being silent.

The operation MUST surface each held repository on the same observability
surface that already reports supervised state, as a HELD condition
distinguishable from a repository that is absent from the declaration —
whether it was never watched or was removed. "This repository is deliberately
unsupervised" MUST be a fact the machine can state, not one that lives only in
a configuration comment.

A held entry MAY carry an optional review-by date. Independently of whether one
is set, the operation MUST surface the hold's AGE (declared-at to now) wherever
it surfaces the held repository, so a hold that is never reviewed becomes more
visible over time rather than persisting silently. Where a review-by date is
set and has passed, that MUST be surfaced as well.

## Track discovery and the mapping store

The track list is re-discovered every observation cycle: for each watched
repository, one track per unarchived plan-topic directory. Archived plans
are excluded. Discovery keys on the DIRECTORY existing — it never reads,
stats, or hashes any file inside a plan directory (per §"Non-interference
with tracked work"). The read-first target it hands to sessions is the
plan's LEDGER-HELD PLAN STATE: the append-only, individually attributed and
timestamped handoff entries carried on the governed plan's ledger epic,
whose id the mapping store persists as that track's `epic` value. A track's
worker and its supervisor pair member share that ONE epic and that ONE
stream; there is no second store and no separate supervisor stream.
ATTRIBUTION is what separates them: a SUPERVISOR HANDOFF ENTRY is an entry
attributed to the track's supervisor entity, and a worker's entries are
those attributed to the worker entity. Every entry carries an attribution by
construction, so the filter is always available to a reader. The daemon holds the epic id as an OPAQUE LOCATOR for the plan's handoff entries — it hands the id and the entity name to sessions, and it never reads those entries, never hashes them, and never inspects them as restart authorization. The daemon also reads and writes the topic's live-seat record of §"Supervision across machines", which is held under a key naming that epic id rather than on the epic itself, is not a handoff entry, and authorizes no restart on its own. Because the daemon never reads
inside a plan directory on the discovery or consumption path — the sole
exception being the supervisor resume-artifact certification per
contracts.md §"The restart interlock" — it can never re-derive that id
for itself on any other path: the id
is recorded into the row AT TRACK ASSIGNMENT — the moment the row itself
comes into being, since the store holds one row per ASSIGNED track — by
whichever surface performs that assignment, read from the plan's write-once
metadata anchor. This specification does not make any one surface the
assigner; the obligation attaches to whichever surface performs the
assignment. A track assigned when the anchor cannot
be read simply carries no recorded `epic`, which the restart interlock
already handles by refusing the respawn and preserving the declaration. The
daemon consumes the recorded value and never reads the anchor itself to
re-derive it — the sole exception is the supervisor resume-artifact
certification per contracts.md §"The restart interlock", which MAY read
the SAME anchor file for that narrower, unrelated purpose. The
discovery path performs no file-level probe inside a plan directory.

The displayed list is discovery LEFT-JOINED with the mapping store. The
store persists ONLY facts the DAEMON cannot re-derive for itself: the
topic-to-session mapping, the plan's ledger epic id, a custom resume line, a
per-track threshold override, and a pinned session identity. The epic id
qualifies because its source is the plan's write-once metadata anchor, a
file inside a plan directory, and the daemon never reads one for THIS
purpose (id re-derivation) — the supervisor resume-artifact certification
per contracts.md §"The restart interlock" MAY read the SAME anchor file
(plan/<topic>/epic.md, in the migrated shape -- since overseer/_registry_epic.py
commit e0f1100, epic.md is the FIRST-read write-once anchor, not a
distinct file) for a DIFFERENT, narrower purpose:
certifying a supervisor's resume artifact, never re-deriving an id — which
is why the id is recorded at track assignment by a surface that MAY read
plan-tree text as evidence, and merely consumed by the daemon thereafter. Everything
else is recomputed from live state, so the list can never go stale. Rows
whose plan has been archived or deleted are garbage-collected once their
recorded session no longer exists — with two protections: an ACTIVE plan
always wins over a same-named archived copy, and a repository whose root is
transiently unreachable is never mistaken for a deleted plan. While a
previously-mapped PLAN row's directory is archived or gone but its recorded
session still exists (running or exited), the row and its mapping are RETAINED, and the track
stays in the displayed list, so the maintainer can read the session's
wrap-up. Retention is for visibility only: such a track is a done track per
§"The terminal declaration", receives no act of any kind, and renders as the
quiet `done` row whatever its state file holds, per §"The terminal
declaration". Moving the plan's directory back out of `plan/archive/`
re-opens the track unless it holds `done`, and it is supervised again from
the next observation; the daemon keys on the directory alone, and whoever
moves it back MUST reopen its epic, per the archival rules below.

Whoever archives a plan MUST leave NOTHING at its live path `plan/<topic>/`.
A stub, a terminal marker, a forwarding note, or any other residue there is
FORBIDDEN, and the directory itself MUST NOT remain, even empty. Archival
MUST relocate the directory whole, leaving nothing behind.

Stated as a state invariant rather than only as a rule about the archival
event: in no committed tree, from this clause's ratification forward, may
the same topic exist at BOTH `plan/<topic>/` and `plan/archive/<topic>/`. A
retired topic's slug is therefore NOT reused for a new thread while its
archive remains — choose a new slug; or, if the new work genuinely continues
the old thread, REOPEN ITS EPIC, which unarchives the thread by moving it
back. Moving an archived thread back WITHOUT reopening its epic is
forbidden: it produces a live directory whose epic is closed, which is the
tombstone condition wearing a different name.

This prohibition is load-bearing because of how discovery works. The
archived-or-deleted test keys on the DIRECTORY alone, and discovery
enumerates directories, performing no file-level probe inside any plan
directory. The live directory's continued existence — including via a
symlink to a directory — makes an archived thread read as ACTIVE, so its
mapping row is never garbage-collected and the finished thread remains
eligible for nudges, for wrap-up injection, and for RESTART.

The daemon reads each watched checkout's WORKING TREE, not a commit, so
untracked residue under `plan/<topic>/` keeps the directory alive even after
a clean archive has merged. Removing the tracked files is not sufficient;
the directory must be gone from the tree the daemon actually reads.

When a plan would close with anything unresolved, exactly ONE of two
dispositions is sanctioned. Either the thread is LEFT UN-ARCHIVED — its epic
staying OPEN — until its blockers are resolved; or ALL of its blockers are
TRANSFERRED to a different or new NON-ARCHIVED plan and/or work-item, after
which the thread is archived whole. Archiving it and leaving a note saying
what is left is not a third option.

The precedence by which an ACTIVE plan wins over a same-named archived copy
is daemon ROBUSTNESS — it keeps a live thread from being garbage-collected
in a working tree that transiently holds both, such as a lagging checkout or
a mid-operation tree — and NOT a sanction of the both-present pair as a
durable state. The protection against mistaking a transiently-unreachable
repository root for a deleted plan is likewise unaffected.

## Supervision across machines

Supervised seats MAY run on more than one machine. Each machine that hosts supervised seats and meets the runtime requirements (constraints.md §"Runtime requirements": Linux, with tmux or herdr) runs its OWN daemon, and a daemon supervises only the panes of the machine it runs on. A SUPERVISED MACHINE is any machine running a daemon. That set is independent of the credential-rotation role holder and its listed hosts under §"Account rotation and quota supervision": listing a host there neither makes it a supervised machine nor is required to make it one. Every input a daemon's decision depends on is read on the machine that runs the seat, never fetched from another machine: process identity and start time, the agent's session and rollout files, the track's state file, and the host memory floor of §"The restart". Each machine keeps its own mapping store. Because the same repositories are checked out on several machines, daemons on different machines discover the same tracks. Discovery is unchanged, and a track with no live seat on a daemon's own machine receives no act from that daemon.

**One live seat per plan topic.** At most one live supervised seat may exist for a plan topic across all supervised machines. The record that enforces this is the topic's LIVE-SEAT RECORD. It is held in the plan's ledger, under a key naming the plan's epic id (the epic id the mapping store already records for the track), because the ledger is the one store every machine's daemon can reach. It is held apart from the epic's own fields, so no write to the epic can alter or erase it. A live-seat record names: the holding machine by its `/etc/machine-id`, which is what every comparison uses; that machine's hostname, which is display only; the holding seat's session identity; and the time it was last written. It is NOT plan state. It is never a handoff entry, the daemon still never reads the epic's handoff entries, and the record on its own authorizes no restart. A live-seat record is written ONLY by an atomic conditional write that succeeds only when the record is absent or already names the writer's own machine, so two machines can never both hold it. It is written at exactly three moments: when a seat is bound to the topic (taken, naming that seat's session identity); after a successful replacement (rewritten to name the successor's session identity, on the same machine); and when the holder releases it. It is read by a daemon before binding and before replacing, by every session-starting surface before it launches, and by the duplicate-seat condition below, to name the holder. It is never renewed and never expires with time.

The DAEMON MUST hold the topic's live-seat record, read fresh for that act, before it binds a discovered session to the track and before it starts a seat replacement. The replacement passes through the restart interlock unchanged; the record is an additional precondition, never a substitute for it. The sanctioned out-of-band relaunch is not a daemon act (§"The sanctioned out-of-band relaunch"). Its operator entrypoint, and every other surface that starts a session for a supervised plan topic, MUST take or verify the topic's live-seat record for its own machine before it launches, MUST NOT launch when the record names another machine, and re-binds the track's mapping row only while holding it. When a daemon finds a live local session for a topic whose record names ANOTHER machine, it MUST NOT bind, replace, keystroke or terminate that session, and MUST journal one `live-seat-held-elsewhere` event, edge-triggered (§"Notify, never block"), naming the topic, the record's holding machine and its own. A daemon releases a record it holds only when it observes that its own seat for the topic is gone: the session has exited and is not being replaced.

**An unverifiable record fails toward one seat.** A record is NEVER taken over because time passed. A record held by a machine that has stopped, or that no other machine can reach, stays held until that machine's daemon releases it, or until an operator releases it with an explicit, attributed release naming the topic and the machine. A daemon does not probe other machines and makes no claim about their reachability. While the ledger cannot be read or written, and for any track that carries no recorded epic id (and so has no record to verify), a daemon MUST treat the record as NOT held by itself. It MUST hold each act that requires the record the way it holds a replacement below the memory floor: the ready declaration and the round are preserved, the act is retried on a later tick, and one `live-seat-unverifiable` event naming the topic and the reason is journaled, edge-triggered. The one exception is a track with no recorded epic id while the daemon's own configuration declares no supervised machine other than its own: such a track MAY still be bound on that machine, as it is today, so it keeps receiving wrap-up; its replacement stays held by the recorded-epic gate of contracts.md §"The restart interlock", and the exception ends for every such track once a second supervised machine is declared, which MUST happen before a second machine's daemon starts. Observation, context reading, wrap-up injection, submission retries into an already-running session, and alerts are not gated by the record, so a seat that is already live keeps being supervised on its own machine.

**Where the guarantee does not reach.** The guarantee holds only among daemons, and session-starting surfaces, that run a build implementing this section. During a rollout, a machine still running an earlier daemon neither reads nor writes the record, so the guarantee holds only once every supervised machine runs a build that does. A seat on a machine that cannot run a daemon, such as a macOS host (outside constraints.md §"Runtime requirements"), is unsupervised and holds no live-seat record, so no daemon can see it. The operator MUST NOT run a seat for a supervised plan topic on such a machine while that topic is live on a supervised machine, and MUST NOT start one on a supervised machine while it runs on such a machine.

## Session-name derivation

A supervised session is named after its BARE plan topic — the name the
operator reads and navigates by. A repository qualifier is added ONLY on a
genuine cross-repository collision, when the same topic exists in two or more
watched repositories, and then as `<repo-slug>-<topic>` with a single dash.
The collision set is recomputed from discovery on every cycle and the SAME
derivation is used at every site that names a session, so a session is named
identically wherever it is derived.

A live session is linked to a discovered plan only when the derived session
exists AND that session's working directory resolves inside the plan's
repository — the containment check, not the name, is what prevents two
repositories sharing a topic from cross-linking. Adoption of already-running
sessions matches each session's registered display name against active plan
topics, exactly — never a screen-scrape, and never a most-recent-by-time
guess.

A mapped track whose session is gone MUST be surfaced as MISNAMED, rather than
as gone, whenever a Codex near-miss candidate exists. It is the candidate's own
live runtime that makes the case a Codex one, not the track's recorded launch
profile, so a stale recorded harness does not suppress the row. A candidate is a Codex thread whose identity is established from live
process evidence — a live Codex process whose working directory resolves
inside the track's repository — and whose name, read from the Codex session
index, CONTAINS the track's derived session name (as derived in this section,
including any cross-repository qualifier), compared case-sensitively, but is
not equal to it. A thread named exactly the derived session name is never
misnamed. A thread is never a candidate when its name ends in a reserved
suffix (compared case-insensitively), when its name equals the derived
session name of any other discovered track, or when it is already adopted by
or bound to another track. When one or more candidates exist, the daemon MUST
raise exactly one `codex-track-misnamed` attention row for the track, in place
of its session-gone row, naming every candidate's live pane, thread
identifier and actual name, together with the exact one-line repair
`/rename <derived-name>` to be typed in the intended candidate's pane. While a
track reads misnamed, the daemon MUST NOT adopt, wrap up, nudge, restart, or
consume a ready declaration for any candidate: containment is evidence for
the operator, never an identity, and exact-name adoption remains the only way
a session becomes a track. The row's notification follows §"Notify, never
block": its dedup identity is the misnamed condition together with the set of
candidate thread identifiers, a change in a candidate's actual name alone
MUST NOT re-emit it, and it re-arms when that condition clears. On the first
round after a candidate's indexed name becomes exactly the derived session
name, ordinary exact-name adoption applies: the session is adopted, the track
binds that session's live pane, and the misnamed row clears. A
discovered-but-unassigned plan never raises a misnamed row, and neither does a
done track (§"The terminal declaration"), which keeps its quiet `done` status.

The `-supervisor` suffix is RESERVED for pair members (per §"Supervised
runtimes"). It is compared case-insensitively. A worker entity MUST
NOT be derived, registered, or accepted under a session name ending in a
reserved suffix; the check MUST be applied to the final derived name —
including the repo-slug-qualified form the cross-repository collision
qualifier produces — and the offending derivation MUST be refused and
surfaced by name, never reduced to a warning and never silently skipped. The
daemon MUST refuse to adopt a live session whose registry name ends in a
reserved suffix, so a supervisor session can never be captured as
a plan worker, wrapped up, nudged, or respawned into ledger-held plan state.
A pair member's session name is derived from its worker's PLAN TOPIC, using
the same derivation and the same collision qualification with the suffix
appended, never from whatever tmux session currently happens to host the
worker.

## Surface-only startup

The daemon NEVER auto-spawns a session for a plan that has none. A discovered
plan with no session is surfaced as unassigned — startable, never started.
The first launch of a plan is a deliberate act by the human, or by an
authorized operator surface acting under its own ratified contract. The daemon
likewise performs no automatic recovery of dead sessions at startup:
re-launching a mapped-but-dead track is a deliberate act by the human, or by an
authorized operator surface acting under its own ratified contract. This rule
governs FIRST launches only; whether an already-tracked session may be
restarted is governed exclusively by §"The cardinal rule", and neither rule
licenses an exception to the other.

An operator surface exercising this authority MUST use absolute repository
paths and exact-membership session-existence checks, never prefix-matching,
and MUST first classify the target deterministically. A mapped-but-never-
launched track MAY be started fresh. A crashed track whose runtime identity is
established from runtime-identity evidence in §"Supervised runtimes" MUST be
resumed as that runtime, never recreated as another. A target that is
intentionally unassigned, ambiguous between candidate runtimes, or resolvable
only by topic-name guessing MUST be reported to the human instead of launched;
runtime identity is never inferred from a topic name.

An independent recovery command invoked under contracts.md
§"Independent recovery of authorized session obligations" is not a first launch
or recovery of a supervised plan session. For recovery execution the daemon MUST invoke only the
orchestrator's typed public recovery command; that authorized surface launches
any bounded diagnostic worker as a subprocess or runtime-API process, without
pane input. Such a worker MUST NOT become a mapping or track, receive adoption,
wrap-up or nudge, recreate or resume the coordinator, or replace or restart it.
The existing first-launch and restart rules remain unchanged.

## Supervised runtimes

More than one agent runtime can be supervised, and every tracked session is a
full citizen regardless of runtime: it is discovered, adopted, nudged, warned,
and restarted through the same protocol. Every acting mechanic dispatches on
the track's detected runtime, and a restart MUST resume the session under the
SAME runtime it supervises — replacing a session with a different runtime's
launcher is the one destructive cross-runtime failure, and it is designed out
at the dispatch layer. For a DEAD process only, runtime identity MAY be
established from the runtime's own persisted session index only when the index
maps the exact session identifier to the expected session name, that same
runtime retains a resumable transcript for the identifier, and cross-runtime
same-topic candidates leave the result unambiguous. A missing transcript,
stale namesake, conflicting candidate, or identifier mismatch MUST be
classified as AMBIGUOUS and reported to the human, and no launch occurs. A
live process's identity MUST still be established from exact live process
evidence; an index MUST NOT override live evidence.

Live process evidence MUST include every process the carrier spawned,
whichever of the carrier's threads spawned it. When the daemon reads a
process's children to find a carrier's session, it MUST read the children of
EVERY thread of that process, MUST return each child process identifier once
even when it is listed under more than one thread, and MUST fail soft: a
process or thread that has gone contributes no children, and its absence MUST
NOT raise an error or discard the children of the remaining threads. A session
held by a helper that a non-main thread of the carrier spawned is therefore
that carrier's live session for discovery and adoption, exactly as one spawned
by the main thread would be.

A LIVE carrier of a supported runtime running in a mapped track's recorded
pane — the pane resolved under contracts.md §"Durable stores"'s backend,
instance and pane coordinate rules, so no alias on another server or
generation matches — whose session identity cannot be established from exact
per-carrier evidence MUST be reported with a distinct `unidentified-session`
status and MUST NOT be reported as session-gone: a live carrier is not a gone
session, and §"Session-name derivation"'s misnamed surfacing applies only to a
track whose session is gone. The daemon MUST log one event when the track
enters that status, naming the pane, the carrier's process identifier and the
refusing condition (ambiguous repository sessions, or no live candidate); per
§"Notify, never block" its dedup identity is the unidentified condition for
the track, so a change of refusing condition or carrier process alone does not
re-emit it, and it re-arms when the condition clears. An unidentified track is
ambiguous evidence: it receives no adoption, wrap-up, nudge or restart.

A carrier in the recorded pane is identified only by exact per-carrier
evidence that also ties the session to THIS track: a session identifier the
terminal backend reports for that pane's agent, accepted only when the
runtime's own state database binds it to the track's repository, AND either
its thread name equals the track's derived session name or the identifier
equals the session identity the row already records, AND it is not adopted by
or bound to another track. This is exact-name adoption with per-carrier
evidence, not an exception to it: a carrier whose name merely contains the
derived session name stays unidentified-session. Once a carrier is
identified, the daemon adopts its session, re-records the row's session
identity, and re-captures the WHOLE launch profile from the live process per
§"The launch profile"; a profile field it cannot read from permitted sources
leaves the profile stale under contracts.md §"Durable stores", so it is
surfaced and the restart is skipped. This applies whether the recorded
identity belonged to another runtime or to an earlier session of the same
runtime, provided that recorded session's process is gone from the pane. A
recorded session whose process is still alive in the pane keeps its identity
and launch profile, and no other carrier in that pane is adopted. Re-recording
never rewrites an open round's round-open identity.

A row whose stored pane no longer exists on its recorded backend instance
MUST be rebound when exactly one pane on that instance runs an identified
carrier whose thread name equals the row's derived session name, whose session
the state database binds to the row's repository, and which is not bound to
another track; this is the coordinate update exact-name adoption performs,
with the state-database binding as an added condition, and every rebind MUST
log the old and new pane identifiers. When no such pane exists, the stored
coordinate is unchanged and ordinary classification applies — session-gone,
or misnamed per §"Session-name derivation". When more than one exists, the
stored coordinate is unchanged and the track reads unidentified-session with
the refusing condition ambiguous panes, naming every candidate pane. A done
track and a discovered-but-unassigned plan never read unidentified-session.
The rebind, and the session-identity re-record it performs, is an act of the
supervising loop: the read-only list path MUST report the classification the
loop would report for such a row, and MUST leave the row's stored coordinate
and recorded session identity unchanged.

A tracked session MAY have an attended SUPERVISOR session beside it (the
authoring permissions are in §"Non-interference with tracked work"). That
pair member is itself a SUPERVISED ENTITY under this whole specification:
the same marker protocol, the same wind-down threshold and escalation bands,
the same restart interlock, and the cardinal rule verbatim per entity — only
the supervisor's OWN fresh `ready`, declared in its OWN state file, may
restart the supervisor, and no worker declaration may ever restart its
supervisor or the reverse.

Its distinct identities are exactly these, and every topic-parameterized
surface MUST draw from them: its state file and its round records key on the
suffixed entity name; its wrap-up and keep-going messages are entity
VARIANTS whose session name and append ritual refer to the supervisor's own
layer — the entries on the governed plan's ledger epic ATTRIBUTED to the
supervisor entity, appended through the orchestrator's sanctioned plan
surface — and never to the worker's own entries. The pair shares one epic
and one stream; attribution, not a separate store, is what keeps the two
layers distinct, and neither member may append under the other's
attribution. Its restart preserves the suffixed session name and hands the
fresh session exactly one prompt: read the entries on this track's ledger
epic attributed to the supervisor entity and follow them, with the
repository path, the epic id, and that entity name all stated literally. The
respawn is additionally gated on that epic id being RECORDED for the track,
re-checked immediately before the act, so a `ready` with no recorded epic
preserves the declaration and surfaces the existing capture offer instead of
resuming onto a pointer the fresh session cannot resolve; the daemon takes
no content or modification-time dependence on those entries, so brief
freshness remains the supervisor's own protocol obligation, discharged by
appending the brief through that sanctioned plan surface before declaring
`ready`.

A supervisor has no supervisor of its own, by design: the supervision-offer
surface is NOT applied to a pair member. Whether a track's supervision needs
attention is evaluated independently of the worker's own classification on
every cycle, rather than only when the worker happens to be idle. A pair
member that disappears while its wind-down round is open MUST be surfaced as
attention — supervision died mid-brief and the ledger entry is at risk; one
that disappears with no round open is surfaced only through the ordinary
supervision offer.

## First-run onboarding screens

A tracked Claude Code session can come up on a first-run onboarding screen
instead of its input prompt: the THEME PICKER, the SECURITY-NOTES screen
("Press Enter to continue"), or the WORKSPACE-TRUST prompt, whose default
selection is its exit option. These screens are harness setup, not a human
decision about the tracked work, and a session parked on one makes no progress
and declares nothing.

The daemon MUST classify a tracked pane showing any of these screens as
`blocked-onboarding`: a distinct kind of waiting on a human, reported under
its own status rather than the generic blocked-on-human one, and never as
session-gone, idle, or busy. Like any structured gate it suppresses the
keep-going nudge and the wrap-up paste. Classification MUST rest on an exact match of the screen's
pane text; unrecognized, partial, or conflicting text MUST NOT be classified
`blocked-onboarding` and suppresses action as ambiguous evidence does. On the
first observation of each onboarding episode the daemon MUST log one event
naming the pane, the screen, and, for the workspace-trust prompt, the prompted
folder.

These three screens are the ONE bounded exception to the rule that a fresh
session showing a structured gate is never keystroked, carved out of
constraints.md §"Acting safety" as its first-run onboarding exception. On the acting path only,
the daemon MAY resolve them:

- the theme picker, by selecting Dark mode and submitting it;
- the security-notes screen, by submitting it;
- the workspace-trust prompt, by moving the selection to its accept option and
  submitting it, ONLY when the prompted folder equals the track's recorded
  repository path.

Before every keystroke the daemon MUST re-read the pane and confirm that the
same screen is still shown, and it MUST log each keystroke it sends. The daemon
MUST NOT send a bare Enter while the workspace-trust prompt's selection is on its
exit option. When the trust prompt names a folder other than the track's
recorded repository, or a screen cannot be matched exactly, the daemon MUST send
nothing and MUST surface the track as an attention row naming the pane and the
screen. The read-only list path MUST report `blocked-onboarding` without sending
any keystroke. A pane that is not a tracked session MUST NOT be keystroked by
this rule.

## Non-interference with tracked work

The overseer's DAEMON — the unattended observation and restart loop — NEVER
touches files under any repository's plan tree, with exactly ONE bounded
READ exception (per contracts.md §"The restart interlock", resume-artifact
certification; existence-only STAT probes elsewhere, e.g. the supervision-offer
surface's check of the same two artifact names, are unchanged by this
exception and were never covered by the "opens, writes, or hashes" verb
list the next sentence uses). The plan state and everything beside it are the
supervised session's own workflow: the overseer enumerates plan DIRECTORIES
to discover tracks and points sessions at ledger-held plan state, and for
every topic other than a SUPERVISOR topic the daemon never opens, writes, or
hashes plan-tree files and never reads plan-state text as restart
authorization — the restart interlock inspects nothing beyond the
state-file token for those tracks. For a SUPERVISOR topic only, the restart
interlock ADDITIONALLY certifies that either the legacy
plan/<topic>/supervisor-handoff.md exists, or the migrated
plan/<topic>/epic.md names the track's recorded ledger epic and references
the ledger-comment binder medium, before restarting — a bounded, read-only,
restart-gating-only check that can never trigger a restart, authorize a
kill, or substitute for the entity's own fresh `ready` declaration. The
discovery path still performs no file-level probe inside a plan
directory — the one named read exception sits on the restart interlock,
never on discovery.

When any operator surface STARTS a tracked session, it MUST durably record a
start-intent BEFORE the spawn, naming the action, the target track, and the
INVOKER on whose behalf it acts. The two failure cases are NOT the same and
carry different obligations. A spawn that fails and RESOLVES: the surface
MUST amend that intent record with the failure and its error. A spawn that
does NOT return at all: the intent record stands with no outcome, and an
intent record carrying no outcome MUST be read as ATTEMPTED-AND-FAILED —
never as work still live, and never as evidence that no attempt was made. No
obligation is placed on a surface that no longer exists to write anything
after its own death; the pre-spawn record is what carries the attempt, which
is why it MUST precede the spawn. This obligation attaches to EVERY start the
surface performs, not only to those whose path happens already to write a
pre-spawn record.

The overseer's daemon writes its runtime state to exactly three places: its
home-directory stores, a per-track temporary directory inside each watched
repository's gitignored scratch area, and, for the live-seat record of
§"Supervision across machines" only, the plan's ledger. At startup the daemon verifies that
every watched repository ignores that scratch path and REFUSES to run if any
does not — so supervision can never dirty a tracked working tree.

## The isolated live exercise

The released live-exercise runner (`scripts/overseer-live-exercise.sh`) runs one
supported terminal backend and one authenticated agent client (Claude Code or
Codex) inside a private namespace. It is the sanctioned surface for the
host-captured lifecycle proof of a release. It MUST NOT touch the operator's real
tracked sessions, real terminal-backend servers, or home-directory overseer
stores.

The namespace MUST mount a scratch home at the operator's home path. Inside the
namespace, the only writable host paths MUST be the runner's own scratch root and
the operator-supplied evidence directory; every other operator-home path MUST be
either hidden by the scratch home or bound read-only. The runner copies the
released checkout into its scratch root, and apart from that copy the agent
client's credential is the only operator content copied into the scratch home.

An agent client installed under the operator home MUST be made runnable inside the
namespace by binding, read-only, what that client actually executes — the
executable itself, or the install tree a script launcher runs from. Binding only
the launcher file is insufficient when that launcher executes content elsewhere
under the operator home, because the scratch home hides that content.

On the agent client's behalf the runner MUST bind, read-only, at most two
operator-home paths and no others: (1) the launcher on PATH, bound at its own path
from its real path so the client stays callable by name; and (2) when that
launcher is a script that runs content elsewhere under the operator home, that
content's install root. The install root is the first directory below the
operator home on the real path of the program the launcher's exec line runs, or,
when that program lies outside the operator home, on the real path of the script
file the launcher passes to it; when that program sits directly in the operator
home, the install root is the operator home itself. A launcher whose real path is
a self-contained executable rather than a script needs only bind (1). When the
program and the script file it is passed both lie under the operator home but in
different first-level directories, the runner cannot make the client runnable and
MUST refuse as described below. The runner MUST NOT bind a parent of the install
root in its place, and MUST NOT bind any other operator-home path for the agent
client, whatever other home paths the launcher names (configuration, cache or
state directories, other installs); those paths stay hidden by the scratch home.
This rule governs only the binds the runner makes for the agent client. Read-only
binds the runner makes for the terminal backend or its own tooling remain
governed by the writable-path rule above.

When the runner cannot make the selected agent client runnable inside the
namespace — including when the client is absent from PATH, or when the runner
cannot determine what a launcher executes — it MUST refuse BEFORE it starts any
terminal backend. The refusal MUST name the client name or path it could not
resolve. The runner MUST likewise refuse BEFORE it starts any terminal backend
when the resolved install root is the operator home directory itself, or is one
of the home directories the exercise writes inside the namespace (`~/.claude`,
`~/.codex` or `~/.config`), because binding that root read-only would defeat the
scratch home or make read-only a directory the exercise must write. That refusal
MUST name the offending root. This refusal set is the runner's fixed list of the
roots it writes; it MUST NOT grow with the home paths a launcher names. The
runner MUST NOT report either refusal condition later as a failed `bootstrap`
lifecycle stage.

## Notify, never block

A question may only be asked by the actor that OWNS the decision. A
supervised session's decision is already displayed in its own pane, so the
overseer never re-asks it and never blocks on it: every track that needs a
human — a blocked declaration, a structured gate, a non-responder in danger,
a malformed state value — is relayed as NON-BLOCKING text. Because that
relay is the daemon's only handover, every track-scoped alert MUST be
self-sufficient: it names the plan topic, the repository, the session and
pane holding it, and a copy-pasteable jump command.

Alerts MUST be edge-triggered — one line when a track enters a condition,
not one per cycle. A standing human-wait — a declared block that persists —
MUST be re-reported at most once per crossed rising age boundary, on a small
set of such bands, and a re-declaration MUST start those bands afresh. The
condition MUST be re-derived from live state on every cycle, so an alert
stops on its own once the human acts. Current state is rendered
only by the daemon, rebuilt from live captures on every cycle; it can never
freeze on a stale snapshot. An alert's dedup identity is its CONDITION, and
any live value embedded in an alert line is quantized to the value at entry
or to the boundary just crossed, so a standing condition never re-emits
merely because a number drifted. Each condition re-arms when THAT condition
clears, independently of any other condition the same track carries. Wait-inventory conditions defined in contracts.md MUST follow the same standing-condition age-band rule, with dedup identity equal to condition plus immutable wait identity (or registered session identity for unavailable inventory), and live values quantized to the band crossed; no per-cycle re-report is permitted.

## Fail-soft posture

The daemon supervises many tracks at once, so no single track's bad state may
take down the loop, and no ambiguous reading may trigger an action:

- A malformed store row or state value is skipped or surfaced BY NAME; the
  remaining tracks are unaffected.
- An unknown context reading keeps the last known value and NEVER counts as
  a threshold crossing.
- A storage error on the overseer's own files is reported and survived,
  never raised out of the supervision loop.
- Generating and sub-agent-busy detection deliberately over-fire for the
  RESTART: a false positive withholds a restart, while a miss could kill a
  working session. Busy evidence MUST NOT suppress a wrap-up, wind-down, or
  expiry-notice paste into a positively empty input.
  Ambiguous, conflicting, malformed, unavailable, or unknown authoritative
  runtime evidence therefore resolves toward withholding a restart, and
  ambiguous evidence about the input, the pane's identity, a gate, or a human
  wait resolves toward withholding a paste. Shell-only
  eligibility is affirmative: Claude requires recognized registry
  `status=shell`; Codex requires its descendant-shell fallback. Recognized
  shell-only evidence neither authorizes an act nor suppresses a separately
  qualified informational paste. RESTART suppression remains unbounded for
  generating, changing, sub-agent-busy, and ambiguous evidence. PASTE
  suppression remains unbounded only for typed, unreadable, or unproven-empty
  input, gates, human waits, standing declarations, and ambiguous identity
  evidence. Both are bounded for ATTENTION (see below).
- Every authorization check is fail-closed: absent, unreadable, or
  unexpected inputs answer "no".

Suppressing a RESTART without limit for generating, changing, sub-agent-busy,
or ambiguous evidence is correct; shell-only evidence does not by itself impose
that suppression. Suppressing ATTENTION without limit is not. A track can sit in a state in which no supervision round can
open — a busy classification that never ends, a standing `blocked:`
declaration, an alternation between the two — while its remaining context
runs down, and while it does, the track is never warned and never reported.
A low-context track shielded silently is therefore its own failure, distinct
from the restart the cardinal rule correctly withholds. When a track's
remaining context is KNOWN and has been continuously at or below its
wind-down threshold past a bounded floor, no round has opened in that time,
and the session is not observed actively generating, the daemon MUST surface
the track to the operator, naming EVERY piece of evidence currently
preventing the round — a background command and its age, a standing
declaration and its age, a visible gate — never a single presumed cause.
Where the preventing evidence is a background command observed continuously
past its own bounded floor, the report names that instance specifically.
Separately, a track whose busy classification rests SOLELY on a background
command and that has shown no observable progress past a LONGER bounded
floor MUST be surfaced regardless of its remaining context. Those attention memberships are report-only: they MUST NOT authorize an
injection, keystroke, command termination, declaration write, or restart. They
do not suppress an independently qualified escalation-band wrap-up under
§"The supervision round"; that wrap-up is authorized by its own complete
predicate, never by the attention condition. That requirement binds EVALUATION
ORDER as well as authorization: a report-only membership MUST NOT be evaluated
in a position that prevents the below-threshold branch from being reached, and
the ONLY thing that may suppress a wrap-up is the wrap-up's own complete paste
predicate under §"The supervision round". The
standing-uncertifiable-declaration member is bound by this rule by name, since
it is the member for which the ordering property is load-bearing. A track's
rendered status MAY reflect a report-only membership while the below-threshold
branch still runs its own reporting and its own predicate evaluation:
surfacing a dead end and evaluating the wrap-up are independent obligations,
and satisfying the first MUST NOT discharge the second.

A `ready` declaration standing on a track with NO DELIVERED ROUND — no
round-open timestamp and no recorded expiry, as after a failed opening paste
whose round was un-opened, an out-of-band session replacement, a lost sidecar,
or an unprompted write — carries no certification floor and cannot certify. It
MUST NOT be left to block the wind-down. When the daemon's supervising loop
(never a read-only listing surface) observes such a `ready` on a track whose
remaining context is KNOWN and at or below its wind-down threshold, or which
carries a context-compaction latch, and the declaration has stood unchanged
past the same two-minute grace, measured from the declaration's own
modification time, that governs voiding a `blocked:` declaration, the daemon
MUST retire it. It MUST re-read the state file immediately before acting, MUST
delete the state file only if it still holds that same `ready` token with the
same modification time, and MUST NOT restart, keystroke, or open a round in the
same act. The retirement is recorded as an edge-triggered alert naming the
track and the retired declaration's age; it writes no new state-file value. The ordinary
wrap-up predicate of §"The supervision round" then opens a fresh round on that
or a later observation, and a `ready` the session writes in answer certifies
against that round normally. The retirement authorizes NOTHING. A failed
retirement delete MUST be surfaced through the attention surface and MUST NOT
be retried as anything but the same guarded delete. A `ready` on an un-rounded track that
owes no wind-down (above threshold, no latch) is left standing and surfaced
exactly as before, and that state MUST NOT be described as self-healing. A fresh session-written `ready`
remains the SOLE restart authorization. Each floor MUST be long enough that
ordinary long-running background work completes inside it, so a genuine
build is not ordinarily reported; a genuine command that outlives its floor
produces exactly one report-only line whose text is literally true, and that
residual is accepted rather than designed away. Every condition here MUST be
re-derived from live state each cycle, MUST clear on its own when its
evidence clears, MUST re-arm for a later episode, and MUST key its
continuity on continuously OBSERVED evidence — an observation gap restarts
the floor rather than shortening it. An unknown remaining-context reading is
NEVER a crossing and NEVER starts any of these floors; the requirement that
the reading be KNOWN is explicit in every restatement, so a track whose
context has never been read cannot fire them. A duration the daemon asserts
is carried either by a declaration file's own modification time or by an
in-memory clock over continuously observed evidence; a daemon restart resets
every in-memory clock, which DELAYS every report and fabricates none.
Remaining-context knowledge itself ages: a last-known value unseen past a
bounded staleness window no longer satisfies any context gate, and a track
whose last-known value was at or below its threshold when knowledge went
stale MUST be surfaced with full coordinates — losing sight of a low track
is itself attention. A standing declaration that cannot certify — a `ready`
with no round open for it to answer, or any declaration whose certification
precondition is structurally absent — MUST be surfaced to the operator past
a bounded floor, regardless of remaining context, naming the declaration,
its age (carried by the declaration file's own modification time, per the
duration rule above), and the specific reason it cannot certify. The daemon
MUST NOT render an acting status — a restart-in-progress or any status
implying the act will occur — for a track whose act is structurally
impossible; the rendered state names the dead end instead. Surfacing is the
ENTIRE response here as everywhere above: the interlock's refusal is
unchanged, and no age or floor ever authorizes the restart itself.

## Account rotation and quota supervision

**Scope.** `caam-anthropic-loop` is the account-rotation operation governed by this section. It is identity-only, except for the delivery defined in §"Enrolled-host credential delivery".
- The ROLE HOLDER is the machine that holds the CREDENTIAL-ROTATION ROLE: the one machine currently assigned that role, which holds the managed accounts' logins, runs the rotation operation and pushes deliveries. Where no host list is configured on it, there are no listed hosts, which is the single-host behaviour this section had before delivery.
- The operation MUST observe every account that the coding-agent account manager tracks on the role holder, and MUST report those accounts' remaining quota.
- When the active account's allowance is nearly spent, the operation MUST rotate the role holder's host-wide active credential.
- Every FOLLOWING HOST, as defined in §"Enrolled-host credential delivery", receives that rotation through the delivery defined there.

It MUST NOT implement, install, or version the account-manager binary itself; that remains a host concern. Elsewhere in this section, "the host" means the role holder.

**One decision, on the role holder.** Only an instance of the operation running on the role holder MAY make a rotation decision that a listed host follows, and the decision lock defined under **Switching** serializes those decisions. A listed host MUST NOT make a rotation decision of its own. Every delivery MUST name the account that is active on the role holder, so every following host uses that account. Delivering different accounts to different hosts would change the selection rules, and this section does NOT authorize it.

**The role, never a hostname.** Every provisioning artifact MUST name the credential-rotation role, never a machine's hostname, as the place the rotation runs.
- A listed host's configuration MUST NOT name the role holder at all, because the role holder pushes to the host and the host never reaches the role holder.
- Moving the role to another machine MUST NOT require any change on a listed host.

**Listing a host does not change the selection rules.** Adding or removing a listed host MUST NOT change any rule by which the operation ranks, selects, holds or rotates accounts, and MUST NOT be treated as a reason to alter any threshold, reserve or margin: the usage figures the operation reads are account-wide and already count every host's use. In this revision, listing a host does not widen the set of sessions whose refusals and models those rules observe; **Forwarded refusals** and **Remote sessions** state that deferral.

**Observation.** The operation MUST derive every quota figure from utilization percentages and MUST NOT depend on the monetary fields of the usage response, which are absent on the subscription plans in use. It MUST poll the active account with the live credential and every other account with that account's stored snapshot. It MUST treat an absent scoped-model allowance as a normal condition and not as an error.

**An account's usage reading MUST be a set of limits, and an absent short window MUST be a reading, not a failure.** A provider reports, for each account on each reading, a SET of limit windows, and which windows it reports is a property of that READING: a plan tier MAY carry no short-window limit at all, and an account on such a tier MAY carry a temporary short-window limit on some readings and none on others. The operation MUST parse each reading into a provider-agnostic set in which every limit carries its kind, its remaining figure, and its reset time where the provider reports one, and MUST decide on every reading, never once per account, whether a short-window limit is present. A reading that carries a usable weekly limit and no short-window limit MUST be treated as readable. For that reading the short-window threshold in **Rotation triggers**, the fast-drain trigger, and every short-window burn-rate or baseline computation MUST NOT be evaluated, and the burn rate MUST be taken as unknown; the weekly reserve, the expiring-quota drain, the refusal trigger, every protection floor and the scoped-model reserve MUST still apply. Such an account MUST remain a rotation destination on the dimensions it reports. Where a rotation is compared on the short-window dimension, a candidate whose current reading carries no short-window limit MUST be treated as holding the full short-window headroom, because no short-window limit constrains it; it MUST count as clear of the short-window threshold for the expiring-quota drain; and the capacity test MUST NOT exclude it on the short-window dimension. The operator-facing account table MUST show such an account's weekly figures and MUST state that its current reading has no short-window limit, and MUST NOT report it as unreadable. A short-window limit that appears on a later reading MUST be evaluated against every short-window rule on that reading, and its absence on a still later reading MUST return the account to evaluation without a short-window trigger. The operation MUST NOT carry a short-window figure, baseline or burn rate across a reading that reported no short-window limit.

**A limit the operation does not recognise MUST be shown and MUST NOT make an account unreadable.** A provider MAY report additional limits that throttle or govern an account, and the operation MUST accept them from any provider without becoming unable to read the account. A limit whose kind the operation does not recognise MUST be recorded in the reading's limit set with its provider-reported name, remaining figure and reset time where reported, and the operator-facing account table MUST show it beside the account's other windows. An unrecognised limit MUST NOT on its own fire a rotation trigger, define a comparison dimension, or disqualify a candidate, because no rule in this section states its meaning; a limit kind gains a trigger only when this section names it. The operation MUST report a reading as unreadable only when it carries no usable limit at all or is malformed; a reading that lacks a particular window, or carries a window the operation does not recognise, MUST NOT be reported as unreadable and MUST NOT be a failure path under **Fail loudly**.

**Quota resets MUST be observed and reported.** A provider MAY grant an account QUOTA RESETS: a use of one refills one or more of that account's allowance windows before they would replenish on their own. The operation MUST observe, on every pass and for every managed account, the resets that account holds, and MUST parse each provider's response into a provider-agnostic RESET carrying: the provider's program and reset identifier; the windows one use CLEARS (short-window, weekly, scoped, or several of these at once); the number of uses remaining and in total; the moment the reset itself LAPSES, if the provider reports one; whether it is usable now; and whether the provider permits its use only while the account is at a limit. A recurring reset that the provider reports only while the account is at a limit MUST be represented as such and MUST NOT be reported as absent when the account is not at one. The read MUST be read-only, MUST be made with the same credential the quota poll for that account uses, and MUST present the client identity of the agent whose credential it is. A reading in which the provider declines to state the account's resets for a reason that concerns the requesting client rather than the account MUST be treated as UNREADABLE and MUST NOT be reported as the account holding no resets.

The operator-facing account table MUST show each account's resets in one column headed QUOTA RESETS, placed immediately to the left of the EXTRA column. For an account whose resets were read, the cell MUST state the number of reset uses the account holds, the uses remaining summed over all its resets, and, where at least one reset with a use remaining reports when it lapses, MUST follow that number with `, next expires in <d>d <h>h`, the whole days and remaining whole hours until the soonest such reset lapses; for example `3, next expires in 5d 4h`. An account holding no reset uses MUST show `0`. An account whose resets could not be read MUST show `unreadable`, and MUST NOT be shown as holding none. Reset observation MUST NOT influence selection or ranking except through the reset-claim clauses below, and a failure to read resets MUST NOT disturb the quota report or the rotation.

Every cell of the account table MUST be aligned under its column's header on every kind of row, whether readable, unreadable, stale, without a short-window limit, or with the unrecognised-limits column shown: a right-aligned column's cells MUST end where its header ends, and a left-aligned column's cells MUST start where its header starts, measured in the width the cell occupies on a terminal (a wide character such as the CURRENT column's ✅ occupies two). So that this can always be met, each column's width MUST be the larger of its header's width and the widest cell that column holds in that rendering: no cell is truncated, and a cell wider than its header widens its whole column rather than overflowing into the next one.

**Each account's capacity class MUST be observed live and reported.** Two accounts at the same percentage can hold very different absolute headroom, so the operator-facing report MUST show, for every account, its CAPACITY CLASS — one of `small`, `medium` or `large` — with the provider's own plan name as detail, or `unknown` when the class cannot be determined. The operation MUST determine the class on every pass from a read-only provider request that reflects the account's CURRENT plan, made with the same credential the pass uses for that account's usage, and subject to the same **Never refresh** rule. It MUST NOT derive the class from plan fields stored in a credential at login, which do not change when the plan does. A failed or unparseable read, or a provider plan name with no mapping, MUST yield `unknown`; the operation MUST NOT fall back to a stored or guessed class, and an unknown class MUST NOT on its own fail the pass.

**Never refresh.** The operation MUST perform read-only requests only, with the single exception of the reset claim governed by the reset-claim clauses of this section, and MUST NOT itself invoke the OAuth token endpoint under any circumstance, because rotating a refresh token outside the agent's own control can revoke the whole token family. It MUST detect a locally-expired token and skip the request rather than send it, because the usage endpoint backs off a specific repeatedly-rejected token and a loop that retries a dead token manufactures the error it then reports.

**Identity.** The operation MUST NOT depend solely on the account manager's own report of which profile is active. That report is derived by byte-matching the live credential against each snapshot and therefore becomes unavailable whenever the agent refreshes its own token as normal operation. The operation MUST fall back to matching a stable account identifier that survives token rotation, and MUST fail loudly when it cannot determine the active account by either path.

**A determined account's stable identifier MUST be resolved whichever path determined it.** On every pass that determines an active account, the operation MUST resolve that account's stable account identifier in addition to the account manager's profile name, reading it from whichever of the live account file or the account's stored snapshot the pass has available. A profile name alone MUST NOT be treated as a durable name for the account, since renaming a profile would silently redirect every consumer keyed on it. Resolving the identifier only where the account manager's report is unavailable would make its presence depend on which path happened to answer — an accident of implementation rather than a property of the account, and one that everything downstream of the decision would inherit.

**An unresolved identifier is a reported condition, not a failure path.** Where the operation determined the active account but could not resolve that account's stable identifier — a profile the account manager names but has never snapshotted, for instance — it MUST report the condition in the operator-facing report and MUST continue the pass. Its observation, reporting and rotation obligations are unaffected by the gap, and abandoning a valid rotation over an identifier that only downstream consumers require would cost more than the condition it signals. This condition MUST NOT on its own cause a non-zero exit and MUST NOT be treated as a failure path under **Fail loudly**; what it MUST do is suppress publication, per the publication clauses below.

**Rotation triggers.** The operation MUST rotate when the active account's current reading carries a short-window limit and that allowance is at or above a configurable threshold, or when its weekly remaining falls below a configurable reserve. The threshold SHOULD be set high enough that the window is nearly drained before moving, but low enough that heavy fleet use cannot cross the remaining margin between two polls. Candidates MUST be compared on whichever dimension triggered the rotation; comparing on a dimension that is not the reason for leaving MAY select an account that is no better off in the way that matters. The operation MUST additionally rotate when an operator pin names the scoped model and the active account is at or below a configurable scoped-model reserve on that allowance; because no comparison relation is defined over a scoped allowance, where that is the sole reason for leaving candidates MUST be compared on the short-window dimension, per the scoped-model clause below.

**Short-window floor.** Throughout this section the SHORT-WINDOW FLOOR is the short-window remaining at which the short-window threshold in **Rotation triggers** fires, expressed in remaining terms (100 minus that threshold where the threshold is stated as spent). Every clause below that compares a remaining figure with the short-window threshold MUST compare it with this floor.

**An account that is refusing requests MUST be left, and MUST NOT be returned to until its refusal has lapsed.** A refusal for a usage limit is ground truth about an account's allowance; a usage percentage is a report about it, and on 2026-10-13 the report read 45% remaining nine minutes before the account refused. The operation MUST therefore observe, on every pass, the refusal records that tracked sessions' transcripts carry, and MUST treat a USAGE-LIMIT REFUSAL of the active account as a rotation trigger on its own, alongside every trigger in **Rotation triggers**, whatever the usage figures report. A usage-limit refusal is a refusal the provider attributes to a short-window, weekly or rate limit; a rate limit counts as short-window, and where it carries a retry-after interval, the time it was recorded plus that interval MUST be taken as its reported reset time. The operation MUST parse each provider's refusal records into a provider-agnostic refusal carrying the time it was recorded, the window it names and the reset time the provider reported, if any; a provider whose records cannot be parsed MUST contribute no refusals rather than a guessed one. Detecting refusals MUST NOT send any request of its own.

The operation MUST attribute a refusal to the active account only when ALL of these hold: it was recorded by a tracked session of the same provider as the active account; that session authenticates with the role holder's live credential, as **Which credential a refusing session used** below establishes; where the record names an account identity, that identity is the active account's stable identifier; it was recorded after the moment the operation last observed that account become active, which the operation MUST keep in its durable store; and its reported reset time does not match, within the one-minute tolerance, the reset time of the same window as last read on any DEPARTED ACCOUNT, since concurrent sessions MAY still be spending a departed account's credential for a while after a switch, and their refusals belong to it. Whenever the operation records an activation time, whatever trigger the departure was made on and whether or not the operation made the switch itself, it MUST store in its durable store a DEPARTED ENTRY holding the short-window and weekly reset times last read on the account the previous activation time named, MUST keep that entry until the later of its stored reset times has passed, and MUST drop an account's entry when that account becomes active again. A DEPARTED ACCOUNT is any account with a kept departed entry other than the active account, so an account returned to is never compared with its own reset times. A refusal that reported no reset time never matches. Two residuals are accepted and not corrected: a lagging session's rate-limit refusal, whose reset is derived from its own retry-after interval, cannot match and MAY be attributed to the new account, bounded by its own short hold; and a genuine refusal of the new account whose reset coincides within a minute with a departed account's is not attributed, which fails safe because every other trigger still applies. Where no activation time is stored, or the stored one names a different account from the active account, the operation MUST record the current pass's time as the active account's activation time and MUST attribute no refusal on that pass rather than guess. A refusal recorded by a credential consumer outside the tracked sessions is outside what the operation can observe and MUST NOT be inferred.

**Which credential a refusing session used.** The operation MUST establish the credential conjunct above as follows, so that neither a separately provisioned credential nor the operation's own refresh-maintenance sandbox, whose sessions exercise other accounts' stored credentials and MUST NOT be read for refusals, can contribute:
- For a session on the role holder, the session's agent configuration directory MUST be the role holder's default directory, the one holding the live credential.
- A session on a listed host is not a tracked session in this revision, so no refusal it records is attributed.

**Forwarded refusals.** Deferred to a later revision, reopened by the follow-up plan opened once push runs on every reachable Linux host. In this revision no refusal is forwarded from a listed host, and the operation observes refusals only from tracked sessions on the role holder. Until then, a refusal on a listed host reaches the operation only through the account-wide usage readings.

The operation MUST remember each attributed refusal against its account in its durable store, with its window, its reported reset time, and the reset time that window's reading carried when the refusal was attributed. An account is REFUSAL-HELD from the moment a refusal is attributed to it until the reset time that refusal reported has passed, or, where none was reported, until a later reading of the named window shows it fully replenished or shows a reset time more than one minute later than the reset time that window's reading carried when the refusal was attributed, or until a reset claim settles it. A reset claim made on an account SETTLES every refusal remembered against that account whose named window the claim cleared, only where the provider's answer to that claim reports the reset as used by it and the claim's re-read then shows that window fully replenished; a claim answered as already used, not needed, cooling down, ineligible or unavailable settles nothing, because the re-read after such a claim is the same reading the hold already distrusts. A rate-limit refusal names no quota window a reset clears, so no claim settles it. The operation MUST record in its durable store, against that account, the time of the settling claim's re-read, and MUST NOT attribute to that account again any refusal recorded at or before that time that names a window the settling claim cleared, so that a settled refusal neither holds its account nor returns on a later pass. A refusal-held account MUST NOT be selected as a candidate, whether or not it is still the active account, and whatever its readings report. This is what keeps the refusal trigger from oscillating: a lagging reading on an account that has refused cannot attract a return to it until its window has actually reset.

The refusal trigger fires only while the active account is refusal-held. A move made under it on a short-window or rate-limit refusal counts as a short-window move for condition (f) of the expiring-quota drain. When this trigger fires, candidates MUST be compared on the dimension the refusal names, and the active account's headroom on that dimension MUST be taken as zero, since an account that is refusing has none to offer whatever its reading says. For the weekly reserve's release, a refusal-held active account MUST NOT count as a usable account above the reserve. The trigger MUST NOT relax any per-account protection floor, the zero-weekly disqualifier, the cannot-serve-immediately disqualifier or the live-verification rule. Where no candidate survives those rules, the operation MUST hold and MUST report that the active account is refusing requests and that no account could be selected. A switch made under this trigger MUST be reported as such: the switch line MUST name the refusal as the reason and MUST state when the refusal was recorded.

**A dark active login MUST be left at once.** An account's login is DARK when the provider will no longer accept it and no refresh can restore it. The operation MUST judge the active account's login dark when either of these holds on a pass: (a) a tracked session's transcript records the provider refusing that account's login as unrenewable or revoked, such as the refusal stating that the login reached its time limit and cannot be renewed, where that record is attributed to the account by every condition the usage-limit refusal clause above requires of an attributed refusal, AND, where the account's current login's mint time under **Login records** is `recorded`, was recorded after that mint time; or (b) the operation's own read-only reading of the active account is refused as unauthenticated while the live credential's access token has not reached its expiry, the operation then re-reads the live credential and finds it byte-identical to the one that was refused, and the reading on the next pass is refused the same way with that same credential still unchanged. A single refused reading MUST NOT judge a login dark under (b), because a refresh on the role holder revokes the previous access token at once and can race the reading. An access token that has merely reached its expiry is NOT a dark login, because the agent's own refresh may restore it. Detecting a dark login under (a) MUST NOT send any request of its own, and under (b) MUST use only the reading **Observation** already makes. A dark login MUST be treated as a rotation trigger on its own, alongside every trigger in **Rotation triggers**, whatever the account's usage figures report: on the next pass that judges it, the operation MUST rotate to a candidate that survives every rule of **Eligibility**, chosen by **Ranking**. Candidates MUST be compared on the weekly dimension, and the dark account's headroom MUST be taken as zero on every dimension. For the weekly reserve's release, a login-held active account MUST NOT count as a usable account above the reserve, and a login-held account MUST NOT count as able to serve now. The capacity test's release, which applies only where the active account is refusal-held, is NOT extended to a dark login: where every candidate fails the capacity test, the operation MUST hold, and the hold report MUST say so. A dark login MUST NOT be a ground for claiming a reset, because no reset restores a login. The trigger MUST NOT relax any per-account protection floor, the zero-weekly disqualifier, the cannot-serve-immediately disqualifier or the live-verification rule. Where no candidate survives, the operation MUST hold and MUST report that the active account's login is dark and that no account could be selected. A switch made under this trigger MUST be reported as such: the switch line MUST name the dark login as the reason, MUST state which of (a) or (b) judged it, and MUST state when.

An account whose login has been judged dark is LOGIN-HELD: it MUST NOT be selected as a candidate, on any pass, until a new login is recorded for it under **Login records**, and MUST NOT count as live-verified meanwhile. A reading or a reset claim MUST NOT release a login hold. The operation MUST remember the hold in its durable store, so that a restart does not return the fleet to a dark login.

**Trigger precedence.** Where several triggers fire on one pass, the dark-login trigger MUST govern; otherwise the refusal trigger and its dimension MUST govern; otherwise every other trigger in this section except the drain, including the protected-account floor trigger, governs as already stated; the fast-drain trigger governs only where none of those fires; and the expiring-quota drain remains the lowest. The protection ordering and, where an operator pin names the scoped model, the scoped ordering in **Ranking** MUST apply under every trigger.

**An account that will reach the floor before the next pass MUST be left now.** The short-window floor protects an account only if the account cannot spend its remaining margin between two passes, and on a small plan under fleet load it can. The operation MUST define a configurable PROJECTION HORIZON, a duration whose default MUST equal the documented interval of the operation's own schedule, because the operation's executable cannot read the schedule it was installed under, duplicate schedules can run closer together, and an unscheduled invocation has no interval at all. The operation MUST keep, in its durable store, a BASELINE READING of the active account's short window: its remaining figure, its provider-reported reset time and the time it was taken. Every pass that reads the active account MUST compute the SHORT-WINDOW BURN RATE as the fall in remaining from the baseline to the current reading divided by the time between them, but only where the two readings are of the same short window (reset times agreeing within the one-minute tolerance defined under **Expiring weekly quota MUST be drained**), the account was continuously the active account between them, and they are at least half the projection horizon apart; otherwise the burn rate is UNKNOWN. A pass MUST replace the baseline with its current reading only when no valid baseline exists — a valid baseline is one taken of the current active account and of the same short window — or the current reading is at least half the projection horizon after it, so that closely spaced passes measure across the older baseline rather than amplifying one percentage step into a large rate. A scheduled pass MUST rotate when the burn rate is known and positive and the active account's short-window remaining, less the burn rate multiplied by the projection horizon, is at or below the short-window floor. Candidates MUST be compared on the short-window dimension under this trigger, whose precedence is stated under **Trigger precedence**. The trigger MUST NOT fire on an invocation without the scheduled marker, which already rotates under **Mode resolution**. It MUST NOT relax the weekly reserve, any per-account protection floor, the zero-weekly disqualifier or the live-verification rule. A move made under it counts as a short-window move for condition (f) of the expiring-quota drain.

Where no candidate survives the other rules, the operation MUST hold and MUST report that the active account is projected to reach the short-window floor and that no account could be selected. The operation MUST NOT shorten or otherwise change its schedule in response to a burn rate. Projecting across a whole horizon already moves the fleet one pass early, and the refusal trigger covers an account whose usage figures lag what it actually spent. A switch made under this trigger MUST be reported as such: the switch line MUST name the projected short-window drain as the reason and MUST state the burn rate and the projected remaining at the end of the horizon.

**Expiring weekly quota MUST be drained.** Leaving weekly allowance unspent forfeits it permanently at that window's reset, and the soonest-weekly-reset ranking below can spend the most perishable balance first only once some trigger fires. An invocation carrying the scheduled marker MUST therefore also rotate when NO other trigger in this section has fired and at least one DRAIN CANDIDATE exists. A DRAIN CANDIDATE is a candidate that (a) is live-verified per the clause below; (b) survives the zero-weekly disqualifier, the cannot-serve-immediately disqualifier and the weekly-reserve exclusion, and the capacity test defined under **A candidate MUST be able to carry the current load until the next pass**, exactly as for any other trigger; (c) has a readable weekly reset at least one minute sooner than the active account's weekly reset — readings that differ by less than a minute are treated as the same reset, because the provider reports a nominal reset with sub-second jitter that can straddle a minute boundary, and a fixed tolerance of one minute is a property of that reading noise rather than a setting; (d) holds weekly remaining at least the eligibility margin above the weekly reserve and, where it is protected, weekly remaining at least the eligibility margin above its own protection floor; (e) holds a short-window allowance at least the eligibility margin clear of the short-window rotation threshold; (f) where the operation last moved off that account on a short-window trigger, has passed the short-window reset time the provider reported for that account at the moment of the move or, where the provider reported none, has a fully replenished short window — a reported reset time is taken to be the moment that window is fully replenished. A move counts as made on a short-window trigger whenever the short-window threshold was among the triggers that fired on that pass. The operation MUST remember in its durable store each account it moved off on a short-window trigger together with the short-window reset time reported at that moment. Conditions (d) and (e) reuse the configurable margin of **Eligibility** as a buffer from each threshold, and the drain trigger MUST NOT introduce any configuration of its own: no horizon on how soon the candidate's reset must fall, no minimum weekly quota other than the buffer in (d), no required gap between the candidate's balance and the active account's, and no cooldown measured in time. Where the active account's weekly reset cannot be read, the drain trigger MUST NOT fire, because no candidate can be shown to reset sooner. Where an operator pin names the scoped model and the active account is above the scoped-model reserve, a drain candidate MUST additionally hold the scoped allowance at least the eligibility margin above that reserve, so that draining never makes a satisfiable pin unsatisfiable and never lands on an account the scoped-model trigger would move it off at the next pass.

The drain trigger MUST preserve the protection ordering. Because a drain is a voluntary move from an account that need not be left, it MUST NOT move from an unprotected active account onto a protected candidate, and where the active account is protected it MUST NOT select a protected drain candidate while any unprotected drain candidate exists. Within the drain trigger, "eligible" in the protected-account clause means a drain candidate.

The drain trigger MUST be the lowest-precedence trigger: where any other trigger in this section fires on the same pass, that trigger and its comparison dimension MUST govern and the drain rule MUST NOT apply. Under the drain trigger the comparison dimension is weekly reset time rather than headroom, so the relative-headroom comparison against the active account in **Eligibility** MUST NOT apply to a drain candidate; conditions (d) and (e) apply the same margin against thresholds instead. The drain trigger MUST NOT relax the weekly reserve, any per-account protection floor, the zero-weekly disqualifier or the live-verification rule. Among drain candidates the **Ranking** clause MUST govern unchanged, subject to the protection ordering above. The drain trigger MUST NOT fire on an invocation without the scheduled marker; such an invocation already rotates under **Mode resolution**.

The drain trigger MUST NOT flap. It moves only to an account whose weekly reset is at least one minute sooner than the active account's, so jitter in readings of one nominal reset cannot order two accounts, and a move in the reverse direction would require the departed account to reset at least one minute sooner than the destination — which cannot happen until one of their weekly windows actually resets and the order itself changes. No memory of past drains is needed for this. Conditions (d) and (e), and the scoped condition above, keep a drain off any account that the weekly reserve, its own protection floor, the short-window threshold or the scoped-model reserve would move it off at the next pass. Condition (f) bounds the loop in which a short-window trigger moves the operation off a drained account and the drain later returns: the drain MUST NOT return before that account's short window has reset, by the reset time the provider reported or, failing that, by full replenishment, so it causes at most one return to a given account per short-window cycle whether the provider's window resets at a fixed time or replenishes gradually, without the operation assuming the length of that cycle. The return loop ends once the account's weekly remaining falls below the buffer in (d) or its weekly reset passes.

A switch made under the drain trigger MUST be reported as such: the switch line MUST name expiring weekly quota as the reason and MUST state the destination's remaining weekly percentage and the time until its weekly reset.

**Eligibility.** A candidate MUST hold at least a configurable margin more headroom than the active account on the triggering dimension. This test MUST be relative rather than absolute: an absolute test strands the fleet once every account sits just above the bar, holding while the active account runs to exhaustion. The margin also makes oscillation impossible, since a switch requires a strict improvement that the reverse move cannot match; under the refusal trigger, where the departing account's headroom is taken as zero, the refusal hold carries that guarantee instead, because a refusal-held account cannot be selected until its window has reset. Two clauses carve out exceptions to this margin: the expiring-quota drain above, whose comparison dimension is weekly reset time and which applies the same margin against thresholds instead, and the scoped-model clause below. The scoped-model exception is available only while an operator pin names the scoped model AND the active account is at or below the scoped-model reserve on that allowance; oscillation remains impossible under it, because the account being left is at or below the reserve while the selected candidate holds the scoped allowance strictly above it, so the reverse move cannot invoke the same exception. A candidate MUST be disqualified when it has no weekly allowance remaining or cannot serve a request immediately.

**A candidate MUST be able to carry the current load until the next pass.** Every account has a CAPACITY CLASS, defined under the capacity-reporting clause, and each class MUST carry a configurable relative CAPACITY WEIGHT, set per provider. The operation MUST NOT hardcode a provider's nominal plan multiplier as a weight, because the nominal and observed ratios differ (2026-10-13: about seven to one between Anthropic's large and small plans on the short window, against a nominal twenty). The FLEET LOAD is the active account's short-window burn rate, as defined under the fast-drain clause, multiplied by the active account's capacity weight. Whenever the burn rate is known, the active account's capacity class is known, and the active account is not refusal-held (an account that is refusing spends nothing, so its burn rate understates the load), the operation MUST record the fleet load and the time it was measured in its durable store, and when the burn rate is unknown it MUST use the last recorded fleet load for as long as it is no older than twice the projection horizon, so that the test still applies on the pass after a switch. A candidate's PROJECTED BURN is the fleet load divided by the candidate's capacity weight. A candidate MUST NOT be selected when its short-window remaining, less its projected burn multiplied by the projection horizon, is at or below the short-window floor. This CAPACITY TEST MUST apply to every selection the operation makes, under every trigger including the expiring-quota drain, and to an invocation without the scheduled marker, which MUST use the burn rate or fleet load available to it on that pass. When no fleet load is available, the capacity test MUST NOT exclude any candidate.

Where a capacity class cannot be determined, the operation MUST be conservative toward the candidate and neutral toward the active account. A candidate of unknown class MUST be weighted as the smallest class configured for its provider. An active account of unknown class MUST contribute the weight of the candidate under test, so that candidate's projected burn equals the active account's own burn rate; such a pass MUST NOT record a fleet load. The capacity test MUST NOT relax any other rule.

The capacity test MUST be released only where the active account is refusal-held, on a scheduled pass or an invocation without the scheduled marker alike, and no candidate that survives every other rule passes it. In that case the operation MUST select from the candidates that fail it, ranked by **Ranking** unchanged, because an account that is refusing requests serves nothing, while an account that drains before the next pass still serves until then. Outside that case, where a trigger other than the drain has fired and the capacity test excludes every candidate that survives the other rules, the operation MUST hold and MUST report that no candidate can carry the current load until the next pass; where the drain finds no candidate because of the capacity test, the operation simply holds as for any absent drain candidate. One report line MAY name both the trigger that fired and the capacity test.

**The weekly reserve MUST NOT be forfeited.** An account CAN SERVE NOW when it is live-verified; it is not refusal-held, whether or not it is the active account; it is not SPEND-BLOCKED, meaning its monthly extra-usage spend cap is reached while its short window or its weekly window has nothing left; and its short-window remaining is above the short-window floor. Only an UNPROTECTED account above the reserve keeps the reserve in force, and only while it is USABLE. The active account is usable while it can serve now and the trigger under **An account that will reach the floor before the next pass MUST be left now** has not fired on it. Any other account is usable only while it can serve now and also survives, as a candidate on that pass, every other selection rule, namely: the zero-weekly and cannot-serve-immediately disqualifiers; the **Eligibility** margin on each dimension the governing trigger compares, applied without the scoped-model clause's exception to that margin, and with no margin where no trigger governs or the expiring-quota drain governs; and the capacity test defined under **A candidate MUST be able to carry the current load until the next pass**, applied WITHOUT that clause's release for a refusal-held active account. So no account that the fast-drain trigger or the capacity test projects to reach the short-window floor before the next pass keeps the reserve in force, whether it is the active account or not. Candidates below the reserve MUST be excluded while at least one unprotected account above the reserve is usable, and the reserve MUST be released once none is — whether because every unprotected account is below the reserve or because no unprotected account above it is usable — since at that point it protects nothing: it would keep allowance on accounts that cannot spend it while withholding the only unprotected accounts that can. A protected account MUST NOT keep the reserve in force, whatever its weekly remaining and whether or not it is the active account, because counting it would exclude the unprotected accounts below the reserve and so select or keep the protected account ahead of them, inverting the protection ordering. The reserve decision MUST be made first, and the capacity test's release for a refusal-held active account MUST then be evaluated over the candidate set that decision leaves, including every candidate the reserve's release admits. This release is the weekly reserve's own rule rather than a relaxation of it by any trigger, so the clauses stating that a trigger MUST NOT relax the weekly reserve are unaffected. The release governs the fleet-wide reserve only and MUST NOT be read as releasing any per-account protection floor: it MUST NOT relax any per-account protection floor or the protection ordering. Every candidate the release admits MUST still survive the zero-weekly disqualifier, the cannot-serve-immediately disqualifier, the live-verification rule and the capacity test, subject to that test's own release, exactly as any other candidate. The release does not reach the expiring-quota drain, whose condition (d) still keeps a drain off any candidate below the reserve. A switch or hold made under a rotation trigger other than the expiring-quota drain on a pass that released the reserve MUST report that the weekly reserve was released and why: either that no unprotected account is above it, or that no unprotected account above it was usable, in which case the report MUST name those accounts.

**A protected account MUST retain its own weekly floor.** An operator MAY mark any account as protected and MUST be able to give each protected account its own floor, expressed as a share of its weekly allowance; the floor MUST have a configurable default so that marking an account protected is sufficient on its own. A protected account's usable headroom MUST be measured net of its floor, so that the account is disqualified as a candidate once spending it further would breach that floor. A protected account MUST NOT be selected while any unprotected account is eligible: protection is an ordering over which accounts are spent, not merely a limit on how far. Where the active account is itself protected and has reached its floor, that MUST trigger rotation on its own, since selection rules alone cannot stop an account being spent while it is the one in use.

**A protection floor MUST NOT be released by the weekly reserve's release.** The two floors answer different questions: the weekly reserve protects the fleet's ability to keep working and correctly stops protecting anything once no unprotected account above it is usable, whereas a protection floor is a commitment about one account that the operator relies on elsewhere. Releasing the second because the first ran out would breach that commitment at exactly the moment it was made for. Where every remaining candidate is protected and at or below its floor, the operation MUST hold and MUST report which accounts are protected and at what floor, rather than breaching a floor silently or stalling without a reason.

**A scoped-model allowance MUST NOT be treated as spendable capacity, and MUST influence selection only while an operator pin depends on it.** Such an allowance caps how much of the weekly allowance a single model may spend and draws down the general weekly allowance as it is used, so leaving it unspent forfeits no capacity while leaving weekly unspent forfeits it permanently. The operation MUST NOT rotate in order to consume a scoped allowance, MUST NOT disqualify a candidate for holding one, and MUST NOT prefer a candidate on scoped grounds for any capacity reason. Outside the single exception below, the allowance MUST inform only which model a session runs.

That reasoning governs capacity and does not reach capability. Enforcement can spend only the ACTIVE account's scoped allowance, so an operator pin naming the scoped model becomes unsatisfiable the moment the active account cannot serve that model, and no rule keyed on capacity can observe the condition. WHILE SUCH A PIN IS IN EFFECT, AND ONLY THEN, the operation MUST let the scoped allowance influence SELECTION in exactly the three ways below and in the drain condition stated under **Expiring weekly quota MUST be drained**, and MUST NOT let it influence selection in any other way. This bounds selection only; the operation MUST still observe the allowance wherever other clauses require it, in particular to enforce session models and to render the operator-facing report. Throughout this clause an account CAN SERVE the pinned model when its own scoped allowance is present and not fully spent, and the operation MUST determine that from the scoped balance alone; a model that is available but not answering for non-quota reasons is outside what selection can observe, and is the operator pin's concern rather than selection's. The operation MUST also define a configurable SCOPED-MODEL RESERVE, a percentage of the scoped allowance measured in what REMAINS; its default MUST be a nonzero margin so a Fable-dependent session is moved before its allowance is fully drained, and a configured value of zero MUST reduce every rule in this clause to the fully-spent boundary, restoring the cannot-serve-only behaviour exactly. An ACTIVE account is AT OR BELOW THE SCOPED-MODEL RESERVE when its scoped allowance is absent, or its remaining is at or below the reserve; a CANDIDATE HOLDS THE SCOPED ALLOWANCE ABOVE THE RESERVE when its scoped remaining is present and strictly greater than the reserve. At a reserve of zero these reduce respectively to cannot-serve (fully spent or absent) and to can-serve (present and not fully spent), so the reserve parameterises the three selection rules below without adding a fourth. **Trigger:** an ACTIVE account that is at or below the scoped-model reserve on the pinned model -- whether its scoped allowance is fully spent, absent altogether, or merely at or below the reserve -- MUST trigger rotation on its own, alongside the short-window threshold, the weekly reserve and any per-account protection floor. Moving before the allowance is fully spent is what keeps a Fable-dependent session from being starved between two polls, exactly as the short-window threshold's margin does for the five-hour window; a reserve of zero reverts this to firing only at full exhaustion. **Eligibility:** WHERE THE ACTIVE ACCOUNT IS AT OR BELOW THE SCOPED-MODEL RESERVE ON THE PINNED MODEL, a candidate that HOLDS THE SCOPED ALLOWANCE ABOVE THE RESERVE MAY be selected even though it does not clear the relative-headroom margin, PROVIDED its own short-window allowance is still below the rotation threshold, so that the operation never moves onto an account it would immediately have to leave. A candidate whose own scoped allowance is itself at or below the reserve MUST NOT be selected under this waiver. A candidate that would itself immediately re-trigger the reserve MUST NOT be chosen to satisfy it, whether it reached eligibility by this waiver or by the ordinary relative-headroom margin: the ranking below sorts a holder above the reserve ahead of one that is not, and where the reserve is the sole reason for leaving and no candidate holds the scoped allowance above the reserve the operation MUST hold rather than move onto an account below it, per the scoped-unsatisfiability hold below. Where the active account is ABOVE the scoped-model reserve on the pinned model, the margin MUST apply unwaived, because the pin is comfortably satisfiable where it is and no capability justifies relaxing it. **Ranking:** among eligible candidates, one that holds the scoped allowance above the reserve MUST sort ahead of one that does not, and soonest weekly reset MUST remain the ordering among candidates equal on that test; a candidate whose scoped allowance cannot be read MUST be treated as not holding the scoped allowance above the reserve. At a reserve of zero this ordering reduces exactly to sorting a candidate that can serve the pinned model ahead of one that cannot.

An operator pin names the scoped model, for every selection clause in this section, when EITHER any per-session operator pin -- a per-session enforced-model entry -- is set to the scoped model, OR any tracked session is currently observed running the scoped model, whether it arrived there by pin, by an operator's choice, or as the default; a session observed on the scoped model arms the trigger, the eligibility waiver and the ranking exactly as a per-session pin does, so that the active account being at or below the scoped-model reserve on the scoped model is a rotation trigger for every session that depends on it, not only for a pinned one. A per-session pin naming the scoped model and an observed scoped session each arm the trigger, the eligibility waiver and the ranking above identically, and every precedence stated in this section holds for both. In particular the eligibility waiver relaxes ONLY the relative-headroom margin: it MUST NOT relax any per-account protection floor, so a candidate at or below its protection floor MUST remain disqualified even to serve the pinned model, and a per-session scoped pin grants no license to select or retain a protected account past its floor. Anti-oscillation is preserved for every arming route: where the ACTIVE account is ABOVE the scoped-model reserve on the pinned model the margin MUST apply unwaived, regardless of whether the arming is a per-session pin or an observed scoped session.

A scoped allowance MUST NOT be used as a comparison dimension. The eligibility margin is defined for the short-window and weekly dimensions only, and no "more headroom" relation is defined over a scoped allowance, so where scoped unsatisfiability is the SOLE reason for leaving, candidates MUST be compared on the short-window dimension and the scoped allowance MUST govern only the ranking among those that qualify.

These three MUST NOT weaken any other rule. A candidate that is not live-verified MUST NOT be selected on scoped grounds; the weekly reserve, the zero-weekly disqualifier and any per-account protection floor MUST continue to exclude a candidate regardless of its scoped allowance; and the operation MUST still hold, rather than switch, when no candidate survives those rules. Where rotation is triggered by the scoped-model reserve alone and no candidate holds the scoped allowance above the reserve, the operation MUST hold and MUST report that the pin cannot currently be satisfied above the reserve, rather than rotating to no purpose. At a reserve of zero this reduces to holding when scoped unsatisfiability is the sole reason for leaving and no candidate can serve the pinned model.

**Ranking.** Eligible candidates MUST be ranked by soonest weekly reset, so that the most perishable balance is spent first. A candidate whose reset time cannot be read MUST sort last and MUST NOT be treated as imminently resetting. Where an operator pin names the scoped model, holding the scoped allowance above the scoped-model reserve MUST be applied as a higher-priority ordering than soonest weekly reset, per the scoped-model clause above. Ranking MUST NOT weight a candidate by its plan capacity or rate-limit tier. Soonest weekly reset is the only perishability order the operation can defend. Capacity governs whether an account can serve the current load, which the capacity test under **Eligibility** decides. How far a small account is spent is bounded by the refusal trigger and the fast-drain trigger, not by ranking. A capacity weight in ranking would systematically leave a smaller account's perishable balance to lapse, and it MUST NOT be reintroduced to compensate for a gap in those rules.

**A reset MUST be claimed rather than held at an exhausted window.** Where an invocation carrying the scheduled marker finds that a rotation trigger has fired on the active account — the short-window threshold, the weekly reserve, its own protection floor, the scoped-model reserve, the usage-limit refusal trigger, or the fast-drain trigger — and no candidate survives the rules of this section, so that the operation would hold, the operation MUST claim one of the active account's resets that is usable now and clears every window whose trigger fired, before it holds. Rotation MUST remain preferred under this clause: while any candidate survives, the operation MUST rotate and MUST NOT claim under this clause, except in the case governed by the best-value clause below. Where the active account is refusal-held, the refusal trigger governs: the operation MUST rotate while any candidate survives, including under the capacity-test release, MUST claim a reset that clears the refused window only where none survives, MUST NOT claim under this clause where the only refusal holding the account is a rate-limit refusal, which no claim settles, and a claim whose re-read shows that window replenished settles the refusal, ending its hold as the refusal-hold definition provides. The operation MUST NOT claim under this clause where every window whose trigger fired is reported to replenish on its own within a configurable SELF-RESET HORIZON, whose default MUST be sixty minutes, because such a claim buys at most that horizon's worth of use at the price of a reset. Where several resets qualify, the operation MUST prefer a reset that clears ONLY the windows whose trigger fired over one that clears more, and among those equal on that test MUST prefer the one that lapses soonest, treating a reset with no reported lapse as lapsing last. After a claim, the operation MUST re-read the active account and MUST re-evaluate the rotation triggers against the fresh reading, holding if no trigger still fires.

**A reset MUST be claimed at the best-value moment, so that one account is burned through before the next is started.** A claim refills the allowance spent so far and gains the most when the account is nearly exhausted and many days remain before its weekly window would have reset on its own, because the refilled allowance would otherwise sit idle for those days. Where an invocation carrying the scheduled marker finds that the active account's weekly trigger has fired (the weekly reserve, or, for a protected account, its own protection floor, whichever fires first), and the account holds a reset that is usable now and clears the weekly window, and at least a configurable CLAIM HORIZON, whose default MUST be three days, remains before the account's weekly window resets on its own, the operation MUST claim that reset and MUST then stay on that account, even where a candidate survives. On a protected account this clause MUST NOT apply while any unprotected account is eligible, because the protection ordering applies under every trigger. This clause is the one exception to the rule that rotation is preferred while any candidate survives. It applies only to that weekly trigger on the active account; it MUST NOT apply where the account is refusal-held, where the active login is dark or the account is login-held, where a short-window trigger, the scoped-model reserve trigger or the fast-drain trigger fired, or where the account's weekly window is reported to reset on its own within the claim horizon, and in each of those cases the exhausted-window and rotation rules above govern unchanged. The operation MUST NOT claim under this clause on an account whose credential is not live-verified on that pass, on an account whose monthly extra-usage spend cap is reached, so that a claim never extends spending the cap was set to stop, on an account that cannot serve for a reason no reset clears, or for a reset the provider permits only at a limit the account has not reached. Where several resets qualify, the operation MUST apply the narrowest-qualifying and soonest-lapse preferences of the exhausted-window clause. Where a claim under the lapse clause has been made on the active account in the same pass, this clause MUST evaluate against that claim's re-read and MUST NOT claim on that account in that pass. After a claim the operation MUST re-read the active account, MUST re-evaluate the rotation triggers against the fresh reading and MUST stay on the account if no trigger still fires; where a trigger still fires after the re-read, the rotation and exhausted-window rules above apply unchanged. The claim horizon is an input to this decision only and MUST NOT change ranking, eligibility or any reserve.

**The protected account MUST keep one reset in reserve.** The operation MUST NOT claim under the best-value clause a reset on a protected account if the claim would leave that account holding no usable reset. This reserve yields only to a reset that lapses within the expiry horizon, which the lapse clause already requires to be claimed, so that a reserved reset is never allowed to be forfeited. The exhausted-window clause is unchanged: where holding would leave the operation with no usable account, it still requires the claim, including of a protected account's last reset, because a reserve that cannot be spent is worth less than the capacity it would restore. The reserve counts usable uses remaining across the account's resets, not the number of grants.

**A reset that would otherwise lapse MUST be claimed.** A reset left unclaimed past the moment it lapses is forfeited permanently. An invocation carrying the scheduled marker MUST therefore claim, on any managed account whether active or not, a reset that is usable now and whose reported lapse falls within a configurable EXPIRY HORIZON, whose default MUST be twenty-four hours, provided that the claim would refill at least the eligibility margin of **Eligibility** of spent allowance on at least one window the reset clears. The operation MUST NOT claim a reset under this clause on an account whose credential is not live-verified on that pass. It MUST NOT claim a reset whose provider permits its use only while the account is at a limit unless the account is at a limit that the reset clears. And it MUST NOT claim under this clause a reset that reports no lapse. Where an account holds several resets within the horizon, the operation MUST claim at most one per account per pass, the one that lapses soonest. This clause MUST apply whether or not any rotation trigger fired, and a claim under it MUST NOT itself cause a rotation. Rotation on that pass MUST be decided on readings taken after the claim. Where the active account is refusal-held and a candidate survives, the operation MUST decide and make that pass's rotation on the readings taken before any claim, and only then claim under this clause on the account it left, which is by then not the active account. A lapse claim whose transport fails leaves the pass's rotation decision unchanged; the failure is reported and the claim is retried with its recorded identifier on the next scheduled pass.

**Reset claims MUST NOT weaken any other rule.** A claim refills an account's windows. It is not a rotation and MUST NOT be treated as one. A claim MUST NOT relax the weekly reserve, any per-account protection floor, the protection ordering, the zero-weekly disqualifier, the cannot-serve-immediately disqualifier or the live-verification rule. In particular, a protected account whose windows a claim refilled MUST NOT be selected while any unprotected account is eligible. An account that cannot serve for a reason no reset clears, such as a reached monthly spend cap, MUST NOT have a reset claimed on that ground. A reset that clears a scoped window MAY satisfy the scoped-model reserve trigger under the exhausted-window claim clause, and MUST NOT otherwise make the scoped allowance influence selection beyond what the scoped-model clause permits. An invocation without the scheduled marker MUST NOT claim a reset.

**A claim MUST be serialized, idempotent and reported.** A claim MUST be made only while holding the lock that serializes the decision-and-switch sequence, and only after re-reading the account it is made on. Before sending a claim, the operation MUST record in its durable store a claim identifier for that account and reset. A retry of the same claim MUST reuse that identifier, so that a claim whose response was lost cannot spend a second use. At most one claim MAY be made per account per pass; where a claim under the lapse clause has been made on the active account, the exhausted-window clause MUST evaluate against that claim's re-read and MUST NOT claim on that account in the same pass. A recorded claim identifier whose outcome has not been read MUST be retried, with that identifier, on the next scheduled pass that holds the lock, whatever that pass's triggers report, until its outcome is read. Every claim MUST be reported on its own line, naming the account, the reset, the clause that required it (an exhausted window with no candidate, an imminent lapse, or the best-value moment, in which case the line also names the days remaining before the account's weekly window resets) and the windows it cleared. A provider answer that the reset was already used, was not needed, is cooling down, is ineligible or is unavailable MUST be reported as that outcome and MUST NOT be treated as a failure. A claim that could not be sent or whose answer could not be read is a failure path under **Fail loudly**: the operation MUST emit a clearly-marked failure line and exit non-zero, and MUST NOT roll back a switch, suppress the account table, prevent publication or prevent the persistence of operation state.

**Only a live-verified account MAY be switched onto.** A candidate whose own stored credential could not be exercised during the current pass MUST NOT be selected, because that credential is precisely what a switch installs as the host-wide login, and post-switch verification cannot detect the failure: the switch succeeds onto a dead token. Where no candidate can be verified, the operation MUST hold, MUST report which accounts could not be verified, and SHOULD state how to revive them. A stalled rotation costs quota; a bad switch stops every running session on the host.

**The set of verifiable accounts MUST be actively maintained, not merely reported on.** The live-verified rule above is absolute, and on its own it deadlocks: an idle account's short-lived access token lapses after several hours, so the set of valid destinations drains to empty precisely when rotation becomes necessary, and the operation holds every tick while the active account runs to exhaustion. Reporting the condition is not a remedy — the operation MUST detect an expired or absent stored credential the instant it is knowable, independently of any staleness ceiling that governs when the cached quota figures may still be rendered, and MUST refresh it promptly and on a schedule so as to minimise the window in which the account is unselectable, with a retry backoff such that a persistently unrefreshable account is neither abandoned silently nor retried without limit on the *rate* at which attempts are made — a fixed minimum interval between attempts per account satisfies this, and no bound on the total number of attempts is required, since an account that becomes refreshable again must be picked up. A pre-expiry refresh is NOT required and MUST NOT be assumed available: where the refresh is delegated to the agent (per the clause below) and the agent will renew only a credential that has already expired, refreshing immediately upon expiry and reporting the condition satisfies this obligation. What the operation MUST NOT do is defer a refresh it could already perform — a credential known expired at poll time MUST NOT wait on an unrelated reporting-staleness timer before the refresh is attempted. An account that cannot be refreshed MUST be reported as such, because discovering an orphaned credential while merely maintaining the set is far cheaper than discovering it at the moment of rotation. That report MUST distinguish an unrecoverable credential from a transient or policy condition, and MUST carry the underlying diagnostic rather than a summarised verdict: the remedies differ, and prescribing re-authentication for an account that is merely capped wastes the operator's effort on a credential that is fine. An account whose credential is still valid MUST NOT be reported as a failure merely because no refresh was necessary. The operation MUST establish an account's refreshability by attempting it; a recorded expiry claiming future validity MUST NOT be treated as evidence, because a credential can be revoked or rotated while that field still reads far in the future.

**Refreshing MUST delegate to the agent, and MUST NOT touch the live credential.** This obligation does not weaken the prohibition on out-of-band refresh: the operation MUST perform the refresh by exercising the stored credential through the agent itself, in an isolated configuration sandbox, so that the agent performs its own refresh, and MUST NOT call the token endpoint directly. The operation MUST leave the host's live credential byte-identical across the whole maintenance pass, MUST verify that it did, and MUST report a failure loudly if it did not — silently swapping the account the host is using would be a worse fault than the deadlock being fixed. A maintenance failure MUST be survivable and MUST NOT disturb the quota report or the rotation.

**Login records.** A LOGIN is one provider sign-in for an account, from the moment the operator completes it until the provider stops accepting it or a later login for that account replaces it. The operation MUST keep in its durable store, for every managed account, a record of its current login and of each past login, each carrying: its MINT TIME and how that time is known (`recorded` when taken at the login, `first-seen` when an account that has NEVER had a login record is given one, with the mint time set to that pass's time, which is a lower bound only); and, once it ends, its END TIME and END CAUSE (`dark`, with the evidence that judged it under the dark-login trigger, or `replaced`). The operation MUST provide an operator command that takes the credential from the configuration directory in which the operator has just completed a login for a named account, stores it as that account's stored credential through the store the operation already uses for stored credentials, and records that login with mint time `recorded`, taken as that credential file's write time where readable and otherwise the time the command ran, stating which. The command MUST NOT write the live credential; where the named account is the active one, the live credential changes only by the operator's own login or by **Switching**. That command MUST end the account's previous login as `replaced` unless it already ended, and MUST release any login hold on the account. Only this command releases a login hold; an account whose login has ended MUST NOT be given a `first-seen` record. A refresh of an existing login MUST NOT be recorded as a new login. Past login records MUST be kept for at least 365 days.

**Login age and the lifetime cap.** The operator-facing report MUST show, for every managed account, its current login's age and mint time, marked as a lower bound when the mint time is `first-seen`. The lifetime cap is a configurable duration that MUST be unset by default, because no cap length has been measured. While it is unset the report MUST state that the lifetime cap is not yet measured and MUST NOT warn. Once it is set, the report MUST warn for every account whose current login's age has reached the cap minus a configurable warning lead, whose default MUST be 48 hours. An age that is only a lower bound MUST still warn, because the true age is at least that. The login records MUST NOT influence eligibility or ranking: only the dark-login hold acts on selection.

**Switching.** The decision-and-switch sequence MUST be serialized by a non-blocking host-level lock, and a caller that cannot take the lock MUST hold rather than wait. Holding the lock, the operation MUST re-read the active account and abandon a decision whose premise changed, and MUST re-exercise the destination credential immediately before installing it. After switching it MUST verify the switch took effect and MUST report a failure rather than a success when it did not, since concurrent sessions share the credential file and MAY silently reinstate the previous account.

**The selected account's identity MUST be published for credential consumers outside the host agent.** A CREDENTIAL CONSUMER is a party outside the host's interactive agent that bills against the same accounts under its own separately-provisioned credential — one this operation neither stores, installs, nor refreshes. Such a consumer cannot follow a rotation unless the operation states which account it selected, and MUST NOT be required to infer it. The operation MUST publish the identity of the selected account as a PUBLISHED SELECTION RECORD, whose shape and location are fixed by contracts.md §"The account-rotation operation".

**Publication MUST carry identity only.** The operation MUST NOT publish, copy, export, or otherwise expose credential material for the selected account or any other, and a credential consumer MUST NOT be expected to obtain a credential from this operation. The ONE exception is the delivery defined in §"Enrolled-host credential delivery", the only channel by which the operation sends credential material to another machine. That channel carries only the role holder's live interactive credential, with its refresh token removed, and only to an authenticated following host, never to a credential consumer. Moving the role, which contracts.md §"Enrolled-host delivery" defines, is an operator act and not a sending by the operation. Which credential a consumer presents for the published account is that consumer's own concern. `llm-provider-manager` is the separate credential-provider boundary: it MUST NOT read the published selection record as credential material or as authority to bypass its own validation and selection.

**Publication MUST occur on every pass that FULLY determined an active account — one that resolved both the profile name and the stable account identifier — not only on a switch.** The record MUST name the account active at the end of the pass whether the pass switched, held, or found the active account changed beneath it — a hand-run activation takes no lock, so a record written only when this operation itself switches is permanently wrong after any activation it did not perform, and a pass MUST NOT report an activation it did not perform as a rotation of its own. Republishing an unchanged identity MUST have no effect beyond the write and MUST NOT be reported as a change. A pass that could not take the lock that serializes the decision-and-switch sequence MUST NOT publish, because the caller holding that lock is deciding the very fact the record states; publication is that caller's to make.

**An identity the pass could not fully resolve MUST suppress publication rather than degrade it.** Where the operation cannot determine the active account by either path named in **Identity**, or determined it but could not resolve its stable account identifier, it MUST leave any previously published record intact, MUST NOT overwrite it with a candidate, a remembered value, or a partially-resolved identity, and MUST report the condition. A consumer acting on a fabricated identity would spend an account the operation never chose, and one acting on a name-only record would follow a renamed profile to the wrong account; a stale but complete record is the safer failure, because its write time lets a consumer see that it is stale. A pass that fully resolved the active account's identity but could not read its quota MUST still publish, since the identity is known and the missing figures bear only on the report.

**Publication MUST NOT influence selection.** The published record is an output of the pass. The operation MUST NOT read it back as evidence of the active account, MUST NOT let it arm or suppress any rotation trigger, and MUST NOT let a consumer's presence, absence, or state affect eligibility, ranking, or the decision to hold. The delivery service of §"Enrolled-host credential delivery" does not read the published record.

**A publication failure MUST fail the pass without undoing it.** Failing to write the record is a failure path under **Fail loudly**: the operation MUST emit a clearly-marked failure line and MUST exit non-zero. It MUST NOT roll back a switch that already succeeded, MUST NOT suppress or alter the account table, and MUST NOT prevent the persistence of operation state — the rotation and the report are complete work, and discarding them to signal a failed publication would cost more than the failure it reports. Where this obligation meets contracts.md §"The account-rotation operation" under **Exit contract**, whose first sentence exits zero for a pass that held, reported, or switched successfully, the failure rule MUST prevail: a pass that held, reported, or switched and then failed to publish exits non-zero. Completing that work is what makes the non-zero exit safe to act on rather than a reason to suppress it.

**Model enforcement.** The operation MUST NOT derive any session's enforced model from the session's name; it enforces only an operator-set per-session model, and MUST leave every session with no such pin alone except for the servability reset below. Enforcement records which session it set, to which model, and when; a session whose currently-observed model is KNOWN and differs from the model enforcement itself last set for that session is operator-set, and MUST be left alone rather than driven. The servability reset is keyed on servability, not on the global scoped-allowance-exhausted condition: where NO selectable account in the fleet -- one this section's rotation rules could actually choose, i.e. not excluded by a per-account protection floor, the zero-weekly disqualifier, the weekly-reserve rule or the live-verification rule -- can serve the model a session is currently on, enforcement MUST move that session to the general model rather than strand it on a model nothing selectable can serve, whether that model was operator-set or the session's own. A model that ANY selectable account can serve MUST be left alone, even while the ACTIVE account's scoped allowance is unavailable, since rotation rather than a model change is the remedy for an active account that cannot serve it; the active account's scoped allowance being exhausted MUST NOT, on its own, move a session whose own model remains serviceable on a selectable account. An observed model that cannot be read is NEVER evidence of an operator choice and MUST NOT be treated as one; the operator-set determination requires a known observed model. Enforcement MUST be advisory and best-effort: a busy session MUST be skipped rather than driven, a failure affecting one session MUST NOT stop the sweep, and no enforcement failure MAY disturb the quota report or the rotation. This clause bounds which sessions enforcement drives; it changes neither an operator-set per-session model nor the scoped-model selection clauses.

**Remote sessions.** Deferred to a later revision, reopened by the follow-up plan opened once push runs on every reachable Linux host. In this revision a session on a listed host is not a tracked session: it arms no trigger through its observed model, and enforcement drives only sessions on the role holder.

**Operation state MUST be persisted after enforcement, not before it.** Enforcement writes durable state of its own — at minimum the operator-set per-session model pins and the per-session suppression memo. Persisting before enforcement runs discards those writes, which silently defeats both while leaving every observable symptom of a working implementation. The persistence step MUST run even when enforcement itself failed, and MUST NOT be able to fail the run.

**The operator-facing report MUST NOT assert figures it cannot know.** Where a remembered reading describes an allowance window that has since rolled over, the operation MUST withhold the figures and mark the row as stale rather than render them, because such figures describe a period that no longer exists and understate a balance that has in fact replenished. This is a reporting obligation with no effect on selection — an unverifiable account is already ineligible — and it matters precisely because it does not: the machine is protected from the stale reading by the live-verification rule, so the only consumer left to mislead is the human deciding whether to intervene, and a report that understates an account's balance steers that operator away from the best available account. A safety rule that keeps bad data out of the decision path MUST NOT be mistaken for one that keeps it off the display.

**Session identity.** A session's model MUST be determined programmatically and MUST NOT be read from the terminal status line, which truncates in a narrow pane and previously caused affected sessions to be classified as non-agent sessions and excluded from enforcement indefinitely. A session whose model cannot be determined MUST be treated as possibly needing to be set rather than skipped, and repeated attempts against such a session MUST be bounded by a time-based memo.

**Effort MUST be re-asserted as a floor.** Installing an account's snapshot restores a settings file that carries the reasoning-effort key, so a rotation silently overwrites it. The operation MUST restore the configured effort when the live value is lower, MUST leave a deliberately higher value untouched, and MUST rewrite only that key, preserving hook, environment, plugin and integration configuration in the same file.

**Installing an account MUST swap identity only.** The account manager's restore replaces the host agent's whole global state file (`~/.claude.json`) and settings file with the copies the destination profile was backed up from. A profile backed up before onboarding, or before a repository was trusted, would therefore silently return every session started afterwards to first-run onboarding. The ACCOUNT-IDENTITY KEYS of the global state file are exactly `oauthAccount` and `userID`; every other key is host state.

While holding the switch lock and BEFORE invoking the account manager, the operation MUST read and parse the live global state file, the live settings file and the destination profile's stored global state file, MUST confirm that the stored copy carries both account-identity keys, and MUST capture the pre-switch bytes of the live global state file, settings file and credential. When any of those reads, parses or checks fails, the operation MUST NOT invoke the account manager, MUST change no file, and MUST report the switch as failed with a reason distinct from every other switch failure.

After the account manager installs the destination, the operation MUST write the live global state file as the captured pre-switch content with each account-identity key replaced by the destination profile's value, and MUST write the live settings file as the captured pre-switch bytes changed only where **Effort MUST be re-asserted as a floor** rewrites them. Each write MUST be atomic: a temporary file in the same directory, renamed into place, with owner-only permissions, made while the switch lock is held.

When either write fails, the operation MUST restore the captured pre-switch bytes, each restore atomic in the same way, in this order: the credential, then the global state file, then the settings file. Every restore MUST be attempted whatever the outcome of an earlier one. It MUST then report the switch as failed with a reason distinct from every other switch failure and leave the pre-switch account active. A restore that itself fails MUST be reported as a further distinct failure naming every file left unrestored, and the operation MUST NOT report a switch, a hold or a success on that pass.

The post-switch verification of **Switching** MUST also confirm that the live global state file's `oauthAccount` names the destination account, and MUST report the switch as not having taken effect when it does not.

**On the role holder, the scheduled pass MUST NOT depend on a provider login.** On the machine holding the credential-rotation role, scheduled passes MUST be started as contracts.md §"The account-rotation operation" **A host-started schedule** requires, by a host scheduler or supervised process that needs no provider login, so that a dark active login cannot stop the pass that would rotate away from it. Such a pass MUST NOT be started by, or wait to be started by, an agent session that authenticates with any managed account. The refresh-maintenance sandbox that **The set of verifiable accounts MUST be actively maintained, not merely reported on.** requires is not such a dependency, because it exercises a stored credential rather than the live one, and its failure MUST NOT stop the pass.

**Push alerts.** The operation MUST deliver an alert to the maintainer through an operator-configured PUSH CHANNEL, separate from its report and the status command, at the onset of each of these conditions: a login is judged dark; a lifetime-cap warning starts for a login under **Login age and the lifetime cap**; the operation holds because a dark login left no surviving candidate; and a probed factory credential becomes unusable under **Factory credential probes**. It MUST also deliver one recovery alert when such a condition ends. While a condition persists, it MUST repeat the alert once per configurable repeat interval, whose default MUST be six hours, and not more often. An alert MUST name the condition, the account label or the probed credential's label and owning tenant, and when the condition started, and MUST NOT contain any credential material. Delivering an alert MUST NOT depend on any provider login. A failed delivery MUST be reported as a failure in the report and retried on the next pass; it MUST NOT block, delay or undo a rotation. Where no push channel is configured, the report MUST state that alerts cannot be delivered.

**Factory credential probes.** The operation MUST probe every factory credential named in a configured PROBE LIST. Each entry names a label, its owning tenant, and a location the role holder can read it from; the list MUST NOT hold credential values. On the first scheduled pass after a configurable probe interval has elapsed since its last probe, whose default MUST be one hour, the operation MUST exercise each listed credential with one read-only authenticated reading of the kind **Observation** already makes. It MUST judge the credential UNUSABLE when that reading is refused as unauthenticated, when the reading itself shows its weekly or short-window remaining at zero, or when the credential cannot be read from its location. A rate-limited or failed request MUST be judged INCONCLUSIVE, reported, and not alerted, because the usage endpoint backs off a repeatedly read token and its refusal is not evidence that the credential is exhausted. A probe is observation only: it MUST NOT refresh, rewrite or rotate the probed credential, MUST NOT change any credential record's lifecycle state that §"LLM provider credential management" owns, and MUST NOT influence the selection of the interactive account. The report MUST show each probed credential's label, tenant, last probe time and verdict.

**Fail loudly.** Every failure path MUST emit a clearly-marked failure line and exit non-zero, including unexpected failures, so that a missing binary or an unwritable state directory can never present as a quiet success.

## Enrolled-host credential delivery

**Components.** Enrolled-host delivery is a component of the account-rotation operation. It is a DELIVERY SERVICE that runs on the role holder and PUSHES each delivery over ssh to every host in the role holder's HOST LIST. Nothing that reaches the role holder runs on a listed host.

Three kinds of host are defined:
- A LISTED HOST is a host other than the role holder that has an entry in the host list. "Enrolled host" elsewhere in this specification means a listed host.
- A CONVERTED host is a listed host whose interactive credential holds no refresh token.
- A FOLLOWING HOST is a converted listed host.

Delivery never makes a rotation decision. A failure of the delivery service MUST NOT fail a rotation pass.

**The service is a supervised long-running process.** It MUST run under the role holder's per-user service manager, which restarts it when it stops. **Schedule**, **Mode resolution** and **Exit contract** in contracts.md §"The account-rotation operation" govern rotation passes and do not apply to it. **Fail loudly** applies to it as follows:
- On every failure, the service MUST emit a clearly-marked failure line that contains no credential material, and continue.
- A failure that stops the service MUST exit non-zero.

**The one source.** The delivery service MUST read credential material from exactly one place: the role holder's LIVE credential, the host-wide credential that §"Account rotation and quota supervision" polls as the active account's.
- From that credential, it MUST read only the interactive OAuth object, and MUST remove the refresh token from that object before the object leaves the reading.
- It MUST read the account-identity keys from the role holder's global state file, as that section defines them under **Installing an account MUST swap identity only**, and resolve from them the stable account identifier of **Identity**.
- It MUST NOT transmit any refresh token.
- It MUST NOT read the account manager's stored snapshots or the refresh-maintenance sandbox.
- It MUST NOT write any file the rotation operation writes.
- It MUST deliver only the account of the login the role holder is itself using, as the live credential holds it, and MUST NOT take the account to deliver from the operation's published selection record. Where the published selection names a different account from the live credential, the service MUST still deliver the live credential's account, and the status command MUST show the divergence.

**A delivery names the account its token belongs to.** Before it issues a delivery, the service MUST confirm, with the ONE read-only request contracts.md §"Enrolled-host delivery" names, that the access token it read belongs to the account whose stable identifier the identity keys carry. Where the two differ, the service MUST NOT issue a delivery, and MUST read again on the next change to either the live credential or the global state file. This covers two cases:
- a switch in progress, in which the account manager has installed the new credential before the identity keys are rewritten;
- a session that reinstates or rewrites either file after a switch.

Where the token is locally expired, the service MUST NOT send the request, as **Never refresh** requires.

**Delivery follows the live credential.** The service MUST observe the live credential continuously. Whenever the access token or the account-identity keys change, the service MUST issue a new DELIVERY once the confirmation above succeeds, provided the access token differs from the one in the last delivery issued, whether the change came from an agent session on the role holder refreshing it or from the rotation operation switching accounts.
- The service MUST NOT cause a refresh. It MUST NOT invoke the OAuth token endpoint, and **Never refresh** applies to it unchanged. When to refresh remains a decision for the role holder's sessions.
- No lead time before expiry is promised. A refresh on the role holder revokes the previously delivered access token at once. The window between that revocation and each following host applying the replacement is an ACCEPTED exposure under this revision. The status command records when each host last received a delivery.

**Every delivery is pushed to every listed host.** The service MUST push each delivery it issues to every listed host, and MUST push to each host independently, so that a slow or unreachable host never delays another. A host the push cannot reach, or whose push fails, MUST be retried at the interval contracts.md §"Enrolled-host delivery" defines until it holds the current delivery or a later delivery supersedes the one being retried. Retrying MUST NOT re-confirm or re-read the live credential beyond what **Delivery follows the live credential** requires.

**An expired live credential is reported, never repaired.** Where the live credential's access token reaches its expiry and no change has replaced it, the service MUST report that condition through the status command. Every following host whose last-applied delivery carried that token is then shown as `expired`. The service MUST NOT refresh the credential to prevent this.

**A refresh token never reaches a listed host.** The service MUST NOT send a refresh token to any host. The apply step MUST NOT write a refresh token, and MUST NOT write over an interactive credential that already holds one, whether that token comes from the host's own login or from anywhere else. Where the credential holds one, the apply step MUST leave the host unchanged and report the host as NOT CONVERTED, and the service MUST NOT count it as following.

Converting a host is an explicit operator act that removes the host's own login. Neither the service nor the apply step performs it. A not-converted host's own login is a separate grant from the role holder's. That host holds none of the role holder's refresh tokens.

**Applying a delivery swaps the credential and identity only.** The push runs an APPLY STEP on the listed host. When the apply step applies a delivery:
- it MUST set the interactive OAuth object of the host's interactive credential to the delivered object;
- it MUST set the account-identity keys of the host's agent global state file to the delivered values;
- it MUST preserve every other key of both;
- it MUST verify afterwards that both hold what it wrote, and MUST report as not applied a delivery whose verification fails.

Atomicity, serialization and rollback are defined in contracts.md §"Enrolled-host delivery". Applying a delivery MUST NOT require restarting any session.

**Deliveries never move backwards.** Every delivery MUST carry a DELIVERY SEQUENCE number strictly greater than the number of every delivery the service issued before it. The sequence MUST continue across a move of the role. The apply step MUST apply a delivery only when its delivery sequence is greater than the one the host last applied, so a delayed or retried push cannot move a host back to an earlier account or an earlier token.

**Remote Control follows an account switch.** Claude Code stops a session's Remote Control when the signed-in account changes. After a following host applies a delivery that names a different account from the one it last applied, the service MUST re-issue Remote Control on that host in every agent session it can reach, as contracts.md §"Enrolled-host delivery" defines, whose terminal shows Claude Code's account-changed notice (in Claude Code 2.1.323, `signed-in claude.ai account or organization changed on this machine — run /remote-control` in the transcript, or `/rc failed` in the footer) and whose input box holds no unsubmitted text, as contracts.md §"Enrolled-host delivery" defines. The service MUST apply the same re-issue, once, to the role holder's own agent sessions that it can reach after the account the role holder's live credential holds changes to a different account, whether or not that change produces a delivery. It MUST NOT start Remote Control in any other session. The re-issue is advisory and best-effort: its failure MUST be reported and MUST NOT undo the delivery or fail a rotation pass.

**Delivery is not the request path.** The delivery service and the apply step MUST NOT carry, relay or observe inference traffic. Each following host's sessions MUST authenticate directly to the provider with the delivered access token.

**Not the credential-provider manager.** Enrolled-host delivery is not a provisioning path of `llm-provider-manager`. It MUST NOT read or write that manager's store, records, leases, assignments or tombstones. Apart from the read prohibition that §"LLM provider credential management" **Direct provisioning** states for deliveries, the manager's rules are unchanged.

**Coexistence on the role holder.** The role holder MUST keep its full live credential, and the rotation operation's handling of that credential MUST remain unchanged. Only a later revision of this section may remove the role holder's refresh tokens. An implementation MUST NOT do so on its own.

**The host list is held only on the role holder.** Adding a host to delivery MUST be one entry in the host list. A listed host MUST NOT hold the role holder's address, the role name, or any credential for the role holder: the role holder reaches the host, and the host never reaches the role holder. The push authenticates to each host with the ROLE KEY, which moves with the role, so moving the role MUST NOT require any change on a listed host.

**Least privilege.** A listed host MUST NOT be able to read anything on the role holder, including the account manager's stored snapshots, any refresh token, or the service stores. The host list and the service stores MUST contain no credential material. The role key MUST be readable only by the role holder's operating user.

**Status command.** The delivery service MUST provide one operator command on the role holder that shows delivery state and contains no credential material. It MUST show whether the live credential has expired without replacement; the account the live credential holds and the account the operation's published selection record names, flagging when they differ; and, for each listed host, the fields and STATE that contracts.md §"Enrolled-host delivery" defines. A host that has had no successful push within `delivery.stale_after` MUST NOT be shown as `current`. It MUST be shown as `stale` unless a state listed before `stale` applies.

**Deferred to a later revision.** This revision does not define rows in the status command for account limits, login age and lifetime-cap warnings, factory credential probes or undelivered push alerts; the rotation operation's clauses on these are unchanged. Refusals forwarded from listed hosts, and tracking and model enforcement of sessions on listed hosts, are deferred as §"Account rotation and quota supervision" **Forwarded refusals** and **Remote sessions** state, until the follow-up plan opened once push runs on every reachable Linux host.

## LLM provider credential management

**Operation boundary.** `llm-provider-manager` MUST be a distinct operator operation, not a mode or rename of `caam-anthropic-loop`. It MUST acquire, validate, store, select, provision, revalidate and replace LLM provider credentials for a requested provider, credential kind and purpose.

**Direct provisioning.** Provisioning MUST write one real selected credential directly into the requesting consumer's isolated credential file, as defined by contracts.md §"The LLM credential-provider operation", after which that consumer authenticates directly to the provider as the selected account. The manager MUST NOT proxy, relay or rewrite inference traffic, enter the inference request path, or pool subscription credentials behind a shared network endpoint. The manager MUST NOT read a delivery of §"Enrolled-host credential delivery" as credential material, or as authority to bypass its own validation and selection.

**Purpose and shared usage.** Purpose MUST be a policy partition over credentials and shared provider-account usage, not a claim that different credential kinds on one account have independent quota. Selection MUST make an account reserved for other purposes ineligible under the configuration defined by contracts.md §"The LLM credential-provider operation". Interactive caam use MUST be representable by the purpose `interactive`, so coexistence does not create an implicit reservation outside that configuration. When the configured health strategy requires a shared account-usage observation, the provider health adapter MUST supply it and an unreadable or below-floor observation MUST make that account ineligible rather than consume a reservation blindly. The default `none` strategy defined in contracts.md MUST require no health observation and MUST apply no health-based exclusion.

A provisioning request for a registered credential kind that cannot supply the configured shared-usage observation MUST be refused with the pre-access `invalid-request` behavior defined in contracts.md. A configuration containing a multi-purpose reservation for a provider with any such registered kind is itself invalid for every command. Direct acquisition does not perform selection and is not refused by the provision-only health-strategy check when configuration is otherwise valid. The initial Anthropic setup-token kind can be provisioned only under `health_strategy` `none` and single-purpose reservation policy.

A stored credential record matches a provisioning request exactly when its `provider`, `kind` and `purpose` fields equal the request's fields. Purpose reservation is an additional eligibility filter over matching records; it does not make a differently purposed record match. The `consume-first` strategy MUST be the factory default. It MUST retain one incumbent record for each provider, kind and purpose and reuse that record across non-overlapping runs while it remains eligible and unleased; it MUST move only when the incumbent becomes ineligible or leased. When no incumbent is eligible it MUST choose the eligible, unleased record with the lexically smallest `record_id`. The explicit `spread` strategy MUST instead choose the eligible, unleased record least recently assigned, breaking ties by lexical `record_id`. A record with no retained assignment time MUST sort before every assigned record, with lexical `record_id` breaking ties between such records. The durable selection state is defined in contracts.md. A run-scoped lease defined there MUST make active assignments ineligible under both strategies, so overlapping runs never share one account assignment.

**Credential lifecycle.** Each credential record MUST be in exactly one of `acquiring`, `valid`, `suspect`, `revalidating`, `dead` or `reacquiring`. Only the following events MAY change that state. In this feature, `run-lifecycle operation` is an exact alias for the closed `run-scoped operation` set defined in contracts.md, not a narrower subset. `Pending run-lifecycle resumption` means completing, at the mandatory recovery boundary, every eligible pending operation in that set; it excludes a pending provision `start` except when an identical provision resumes it at the later step expressly defined in contracts.md:

| From | Event | To |
|---|---|---|
| no record | acquisition starts | `acquiring` |
| `acquiring` | acquired value passes provider validation | `valid` |
| `acquiring` | acquisition fails, validation definitively rejects the credential, or the operator gives up | `dead` |
| `acquiring` | its acquisition worker is no longer live, its worker deadline passes or its pending attention artifact's deadline passes | `dead` |
| `acquiring` | first or second consecutive validation attempt is inconclusive | `acquiring` |
| `acquiring` | third consecutive validation attempt is inconclusive | `dead` |
| `valid` | authentication, rate-limit or provider-outage report whose assignment generation equals the current credential generation | `suspect` |
| `valid` | revalidation starts because validation is too old | `revalidating` |
| `valid` | credential expiry passes | `dead` |
| `valid` | terminal-success pending-fence recovery after an acquisition or reacquisition worker was revoked or ceased to be live | `dead` |
| `valid` | terminal-success pending-fence recovery after a revalidation worker was revoked or ceased to be live | `suspect` |
| `suspect` | revalidation starts | `revalidating` |
| `suspect` | operator starts explicit reacquisition through `acquire` | `reacquiring` |
| `suspect` | credential expiry passes | `dead` |
| `revalidating` | authentication, rate-limit or provider-outage report whose assignment generation equals the current credential generation | `suspect` |
| `revalidating` | credential expiry passes | `dead` |
| `revalidating` | provider validation succeeds | `valid` |
| `revalidating` | provider validation definitively rejects the credential | `dead` |
| `revalidating` | its revalidation worker is no longer live or its worker deadline passes | `suspect` |
| `revalidating` | validation is inconclusive | `suspect` |
| `dead` | replacement starts | `reacquiring` |
| `reacquiring` | replacement passes provider validation | `valid` |
| `reacquiring` | acquisition fails, validation definitively rejects the credential, or the operator gives up | `dead` |
| `reacquiring` | its reacquisition worker is no longer live, its worker deadline passes or its pending attention artifact's deadline passes | `dead` |
| `reacquiring` | first or second consecutive validation attempt is inconclusive | `reacquiring` |
| `reacquiring` | third consecutive validation attempt is inconclusive | `dead` |

The active lifecycle states are exactly `acquiring`, `reacquiring` and `revalidating`. An acquire operation's matching active state is `acquiring`, a reacquire operation's is `reacquiring` and a revalidate operation's is `revalidating`; `active state`, `active lifecycle state`, `matching active state` and `non-active` use only this mapping throughout the credential-provider contract.

A worker's terminal outcome and any later process-loss recovery MUST produce the operator-observable lifecycle state in the table above through the authoritative persistence rules defined in contracts.md §"The LLM credential-provider operation".

Every command that passes its pre-recovery boundary MUST apply the mandatory recovery contract before substantive action, so a `valid`, `suspect` or `revalidating` credential at or past `expires_at` becomes `dead` and cannot be revalidated or provisioned. `acquiring`, `reacquiring` and already `dead` records are not expired by recovery; the exact fencing, audit, reread and conditional-write sequence is defined in contracts.md §"The LLM credential-provider operation".

A provider-specific API probe MAY establish validity even though provider-scripted browser flows are forbidden. A validation outcome MUST be definitive success, definitive credential rejection or inconclusive; rate limiting, provider outage, transport failure and timeout MUST be inconclusive rather than credential rejection. Acquisition and replacement MUST use the bounded attempt, backoff and deadline policy defined once in contracts.md §"The LLM credential-provider operation", while revalidation uses that contract's single-attempt policy and reserved terminal-publication interval. Recovery of a revalidation worker that ceases to be live or reaches its deadline MUST return the record to `suspect` according to the lifecycle table. Acquisition and reacquisition for one provider account MUST be serialized, and every acquisition, reacquisition and revalidation worker record MUST identify its worker; `held` and `live` are states of that one record shape, not separate record kinds.

The initial Anthropic adapter's exact validation request and response-to-outcome mapping MUST be the wire contract in contracts.md §"The LLM credential-provider operation".

The authoritative `held`, `live` and authorized-worker definitions are in contracts.md §"The LLM credential-provider operation"; after the initial active lifecycle transition is authoritative, an identical acquire contender MUST receive the same active success while that matching worker remains authorized, whether the worker is still held or has been released. Contention before that lifecycle transition follows the contract's ordinary recovery-and-retry branch.

Health-strategy support validation for a provision request's registered provider-and-kind row MUST occur before recovery and belongs to the pre-recovery validation boundary.

For `report`, validation of `occurred_at` against the interval from `target_committed_at` through `lease_expires_at` for a live assignment or through `actual_lease_ended_at` for a tombstone, also capped by captured current time MUST occur after the complete mandatory pre-operation recovery sequence defined in contracts.md. For `complete`, the equivalent `completed_at` interval validation MUST occur at that same post-recovery point. When assignment-expiration recovery replaces the named assignment with a tombstone, the check MUST use that tombstone and its recovered `actual_lease_ended_at`. Apart from every required run-scoped and global recovery effect that completed first, either refusal MUST cause no further worker, lifecycle-expiry, attention, credential, proof, assignment, tombstone or lease mutation.

Acquire's non-dead duplicate check MUST first apply the matching-record expiry recovery defined in contracts.md when that record is at or past non-null `expires_at`; after the transition, the same invocation MUST take the dead-record reacquisition path.

Every command MUST use the exact validation boundary, typed refusals and mandatory recovery sequence defined in contracts.md §"The LLM credential-provider operation" before substantive action. A pre-recovery refusal MUST cause no recovery side effect; a later stateful refusal MAY reflect the required recovery that preceded it but MUST cause no additional mutation itself. The sole stateful early-return exception is an acquire retry that recognizes its matching authorized active worker and returns the original active success without recovery or mutation; other acquire contention runs the contract's recovery-and-retry branch first. Provision-triggered replacement MUST return retryable exhaustion rather than launch on provider-account contention. In the replacement behavior below, the lexically first matching `dead` record means the matching record with the lexically smallest `record_id`.

After mandatory recovery, normal selection MUST run before recovery-candidate handling. Only when it finds no fresh eligible record may provision inspect matching `suspect` records, matching `valid` records stale only because validation is too old, and matching `revalidating` records that have the exact authorized live worker and record-keyed operation required by the matching live revalidation worker and bounded matching-live-revalidation wait defined in contracts.md §"The LLM credential-provider operation", whose accounts are unleased and permitted by purpose reservations. Recovery-candidate discovery MUST NOT apply the configured health strategy; health filtering resumes only after a record becomes fresh and valid for final selection. `consume-first` MUST consider its retained incumbent first when present in that set and order the rest lexically by `record_id`; `spread` MUST use its normal least-recently-assigned order and lexical tie-break. Provision MUST synchronously consider one revalidation candidate at a time and stop only at the first result that remains authoritative, fresh, valid and eligible; a mismatched live worker, failed or defeated result, concurrent return to `suspect`, or expired record is a non-success and provision continues. If none succeeds, it MUST start asynchronous replacement of the lexically first matching `dead` record permitted by reservation and lease filters and return retryable exhaustion without waiting for browser acquisition. The manager MUST NOT proactively revalidate or replace credentials outside command execution and pre-operation recovery. Exact serialization, worker waiting, compare-and-set, reread and recovery mechanics are defined once in contracts.md §"The LLM credential-provider operation".

**Browser acquisition.** Browser acquisition MUST remain agent-discovered rather than provider-scripted and MUST use the closed research/execution role protocol in contracts.md §"The LLM credential-provider operation". A research role MAY use web search but MUST have no secret access. A separate execution role MAY control the acquisition browser but MUST have no web-search capability and MUST NOT receive password or minted-token values in its context. Local tools MUST type stored login material into the browser and persist newly minted tokens without echoing either value. Acquisition MUST use a headed, installed Google Chrome reached over CDP with an account-specific persistent profile; it MUST NOT use bundled Chromium or a cloud-account browser extension. CAPTCHA and 2FA walls MUST surface through the manager-owned browser-verification attention artifact defined in contracts.md §"The LLM credential-provider operation" for a configurable wait whose default is ten minutes. Only the explicit local-operator resolve action MUST resolve that artifact; the worker MUST then remove it and resume acquisition, and browser observation alone MUST NOT resolve it. A pending artifact's expiry strictly before the worker deadline or an operator give-up MUST remove it, return `failed/flow-unavailable`, persist acquisition `failure_reason` `flow-unavailable`, store no new credential value and transition the attempt to `dead` according to the lifecycle table; a pending artifact expiry equal to the worker deadline MUST instead use mandatory worker-deadline recovery to the same result and state. A resolved artifact reaching its own deadline before its still-authorized worker removes it MUST instead be removed without a terminal result, `failure_reason` or lifecycle transition, and the worker MUST continue.

**Coexistence proof.** `caam-anthropic-loop` MUST remain installed, runnable and responsible for interactive Anthropic account rotation throughout the initial factory-purpose rollout. That rollout begins at the earliest target-commit time the manager records for provider `anthropic` and purpose `factory` and ends only when `llm-provider-manager proof-status` first reports `deprecation_ready` true; before it begins and until it ends, the same caam availability and responsibility MUST remain in force. A REAL CONSUMER DAY is a UTC date on which at least one production consumer reports successful Anthropic provider authentication using the manager-provisioned factory-purpose credential with no alternate credential, together with the secret-free completion evidence defined in contracts.md. Seven-day proof MUST mean evidence on seven consecutive UTC dates at or after rollout start. The simultaneous-spread proof MUST use only Anthropic factory-purpose assignments and the exact committed-assignment peer eligibility, target-commit instant-containment and deterministic pair construction defined in contracts.md. The production proof MUST record at least one production-class completion reporting successful Anthropic authentication for that purpose. The legacy credential pool means the manually maintained `CLAUDE_CODE_OAUTH_TOKEN*` entries in the factory consumer's credential environment. The legacy-pool proof MUST record a successful production-class completion whose consumer attests that this pool was absent. How a consumer establishes production class, alternate-credential use and legacy-pool absence belongs to that consumer's own contract.

The qualifying-completion rule in contracts.md is the exact mechanization of a REAL CONSUMER DAY, and “evidence” in the seven-day rule above means at least one such day on each of those seven consecutive dates.

The manager MUST maintain the secret-free proof record and apply the event-time reset semantics defined in contracts.md §"The LLM credential-provider operation". A maintainer MAY deprecate `caam-anthropic-loop` only after invoking `llm-provider-manager proof-status` and receiving `deprecation_ready` true; until then it MUST remain installed and runnable. The one-time proofs MUST NOT substitute for a qualifying seven-day soak.
