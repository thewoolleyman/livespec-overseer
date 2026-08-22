# livespec-overseer

livespec-overseer is the Control-Plane operator tool that keeps long-running
agent sessions productive across context exhaustion. It watches every tracked
session's remaining context headroom, injects an escalating wrap-up prompt as
a session approaches its limit, and atomically restarts that session ONLY once
the session has declared itself ready on the filesystem — so no work is lost
to a mid-flight restart.

It is a two-part system: a headless `overseerd` daemon that polls session
state and drives the marker-file handshake, and a thin interactive tmux pane
that renders every tracked track for an operator.

This specification governs the SUPERVISION CONTRACT — the marker protocol
between the overseer and each supervised session, the watch-set declaration,
session-name derivation, and the atomicity and fail-soft rules — NOT the
internal composition of the Python package, and NOT the interactive pane's
operator-cockpit surface. The pane's track table, its columns, and its
command vocabulary are deliberately outside the governed contract: they may
evolve freely so long as every guarantee in this tree holds.

The FOREMAN — the per-repository autonomous operator surface — is governed by
this specification in its CONTRACT surface: its reserved session-name
contract and reserved-suffix refusals, its observation-only consumption of the
status snapshot and fail-closed behavior on an unknown schema, its composing
attention view and heartbeat, its deliberate-operator launch classification,
its read-only plan-tree carve-out and prohibition on writing any track's state
file, and its state home under the gitignored scratch. Each foreman instance
MUST use `<repo-slug>-foreman` as both its tmux session name and its
runtime-registry name, with `<repo-slug>` derived from the canonical
watched-repository identity; a differently named instance is not an authorized
foreman.

The foreman's disposition of an action the governing orchestrator contract
classifies as a human valve MUST be selected by configuration. The safe default
MUST be report-only, and an absent or unreadable setting MUST resolve to
report-only whenever full_autonomy resolves to false, so a tree that declares
nothing behaves exactly as it did before this policy was ratified.

Under report-only the foreman MUST NOT invoke any such action id, MUST NOT
answer a blocked question on a session's behalf, and MUST report the decision to
the human with coordinates and take no act on it.

Under the consensus disposition the foreman MAY act on a human valve ONLY when a
cross-vendor review panel returns a typed verdict that SATISFIES THE EFFECTIVE
DECISION RULE (§"Full autonomy and the decision rule" below), and only for a
member of a closed, enumerated vocabulary. A free-form or unenumerated member
MUST escalate.

That vocabulary MUST admit two member kinds and no others. The first is an
ACTION, an act the foreman itself performs, identified by the governing
orchestrator contract's action id. The second is a TYPED RULING: a decision the
panel settles and a supervised session then executes, carried as a structured
payload whose kind is itself drawn from a closed enumeration.

A typed ruling MUST carry, in structured fields rather than in prose, the ruling
kind and every value the executing session needs in order to act without
re-deciding anything. A ruling the session must interpret before it can act is a
free-form member and MUST escalate.

THE SET OF RULING KINDS IS ITSELF GOVERNED, and it is governed the way this
specification governs the action ids and the floor categories: BY REFERENCE. The
ruling kinds MUST be those the governing orchestrator contract defines, and this
specification MUST NOT restate them, because a duplicated enumeration is an
enumeration that can drift. A ruling whose kind that contract does not define is
an unenumerated member and MUST escalate.

That binding is what makes "closed" do normative work, so it MUST NOT be
satisfied by an implementation-level enumeration. A kind that exists only in
code, and can therefore be widened by any change that adds a value to it, is not
a defined kind for this purpose however faithfully it is enforced. Widening the
set requires a ratified change to the governing contract, and no configuration
value MAY widen it. Should this tree ever need a ruling kind that contract does
not define, that kind MUST be defined here before it may be authorized — the
same obligation this specification already carries for a floor category the
governing contract does not define.

Admitting typed rulings MUST NOT MOVE THE FLOOR BOUNDARY: it widens what a panel
may SAY, never which decisions it may REACH. Every floor stated below applies
unchanged to a typed ruling, and a ruling that would dispose of a truly
unresolvable decision, or of one human-gated BY DESIGN, MUST escalate however
unanimous and confident the panel is. Nor may a typed ruling launder authority
by changing the actor: the foreman MUST NOT be authorized, through a ruling a
supervised session executes, to reach any decision a direct action id could not
have authorized it to reach — and the human valve id remains non-authorizable by
either member kind.

A typed ruling MUST be journaled before it is relayed, on the same terms as any
other authorized act: the governing setting, the panel identities, the verdict,
and the ruling payload as executed. A failed journal append MUST block the
relay.

No configuration value MAY authorize the foreman to dispose of a truly
unresolvable decision, nor of any decision that is human-gated BY DESIGN —
drift acceptance, a spec-change slice, a regroom or backlog bounce, or a
human-only acceptance. Each of these MUST stay escalated even when the panel is
unanimous and fully confident. No configuration key other than full_autonomy
MAY relax any floor; full_autonomy MAY relax only a floor category this
specification itself defines, as §"Full autonomy and the decision rule" states
— and at this revision it defines none, so every category named above remains
escalated under full_autonomy — and every other relaxation requires a ratified
amendment to this specification.

The two floor categories named above — a truly unresolvable decision, and a
decision human-gated BY DESIGN — are DEFINED BY the governing orchestrator
contract, not by this tree, and this specification binds to those definitions BY
REFERENCE. It MUST NOT restate them, because a duplicated definition is a
definition that can drift; a reader resolving whether a decision sits below a
floor MUST consult that contract's terminology. Should this tree ever name a
floor category the governing contract does not define, that category MUST be
defined here before it may bound the foreman's authority.

The foreman MUST escalate, and MUST NOT act, when consensus evidence is
unavailable or insufficient, when the panel's verdicts do not satisfy the
effective decision rule, when a reviewer verdict the effective decision rule
treats as a veto is present, when any reviewer response is structurally
unusable (a missing or unpinned identity, a malformed response, a reviewer tool
failure or timeout), or when the audit journal append fails.
Escalation MUST be the outcome of every condition this policy does not
explicitly authorize.

The panel MUST draw its reviewers from at least two distinct vendors, because a
panel whose members share a vendor is not the independent evidence this policy
relies on. Under the unanimous decision rule a dissent that is not vendor-aligned with the
majority MUST NOT be overridable by the remaining reviewers. Under the majority
decision rule the only non-overridable dissent is a SECURITY DISSENT as defined
in §"Full autonomy and the decision rule". An outcome reached by overriding a
minority report MUST NOT be recorded as unanimous.

Every act the consensus disposition authorizes MUST be journaled before the act,
naming the governing setting, the panel identities, and the verdict. No
auto-disposition MAY be silent. A failed journal append MUST block the act.

### Full autonomy and the decision rule

A governed repository MAY declare FULL AUTONOMY in its livespec configuration,
as the `full_autonomy` key of this tree's configuration section. The
declaration is a delegation by the maintainer of their own decision authority
for that repository to the repository's foreman seat — the session named by the
reserved `<repo-slug>-foreman` contract — for as long as the key reads true. It
is boolean, and it MUST be read fail-closed: an absent, empty, wrong-typed, or
non-true value MUST resolve to false, so a tree that declares nothing behaves
exactly as it did before this section was ratified.

When full_autonomy resolves to true, the effective valve disposition MUST be
consensus and the effective decision rule MUST be majority, REGARDLESS of the
value of the valve-disposition key. A configuration that declares full_autonomy
true together with an explicit report-only disposition, or with an unrecognized
disposition value, is CONTRADICTORY: full
autonomy MUST still win at runtime, because it is the key the maintainer set in
order to override the others, AND the contradiction MUST be surfaced to the
operator through the same observability the valve disposition already has. A
contradiction MUST NOT be resolved silently to the cautious reading.

The DECISION RULE is the lever that states what a panel's verdicts must satisfy
before the foreman may act. It is one of exactly two values. `unanimous` is the
default and the effective value whenever full_autonomy is false: every reviewer
returns the same typed action, and every condition this policy stated before
this section was ratified applies unchanged, including the minority-report path
and every single-reviewer veto. `majority` is the effective value whenever
full_autonomy is true, and under it:

- a typed action held by a strict majority of the constituted reviewers
  AUTHORIZES that action, for every member of the closed vocabulary this policy
  admits, whether an action the foreman performs or a typed ruling a session
  executes;
- an insufficient-information verdict is an ABSTENTION: it neither vetoes nor
  counts toward any action, and the remaining reviewers decide if a strict
  majority of the constituted panel still agrees;
- a needs-human verdict, from any vendor, is one vote for escalation and MUST
  NOT veto on its own;
- a hard-risk dissent is one vote unless it is a SECURITY DISSENT: a needs-human
  verdict carrying a hard-risk marker whose declared risk kind is security, from
  ANY reviewer, MUST escalate and MUST NOT be overridable by any majority. Every
  hard-risk verdict MUST declare its risk kind as one of `security` or `other`;
  a hard-risk verdict that declares neither is structurally unusable and MUST
  escalate as a tooling failure, never as a dissent;
- a panel with no strict majority for any single typed action MUST escalate;
- a structurally unusable reviewer response, a reviewer set that does not
  match the constituted panel, and a failed journal append MUST escalate
  exactly as under the unanimous rule, because none of them is an opinion.

A verdict MUST record the decision rule it was evaluated under, and an act
authorized under the majority rule MUST be journaled and recorded as a majority
outcome; it MUST NOT be recorded as unanimous. The pre-act journal entry this
policy already requires MUST additionally name the full_autonomy value and the
decision rule in force.

Full autonomy relaxes the floors ONLY as follows, and this enumeration is
closed. This specification defines no floor category of its own at this
revision: both the truly-unresolvable and the human-gated-by-design categories
are bound BY REFERENCE — a disposition of an item the governing orchestrator
contract holds for a human, and the acceptance of drift that livespec core's
governance holds for a human or for unanimous consensus — and a category so
bound MUST stay escalated under full_autonomy until the owning contract
ratifies a relaxation; this specification MUST NOT be read to relax it. Should
this specification later define a floor category of its own, that category is
panel-decidable under the majority rule unless the clause defining it says
otherwise. Four floors hold under full_autonomy and no configuration value MAY
relax them: the cardinal rule stated in §"The cardinal rule"; the rule, stated
here, that every mutation the foreman performs goes through its own actuator
and never by keystroking into a structured gate; the security dissent; and
journal-before-act.

Full autonomy MUST be observable without running the foreman, on the same
surface as the valve disposition, together with the effective decision rule and
whether a contradiction was found. The foreman MUST NOT set, clear, or alter
full_autonomy or the decision rule: nothing the foreman writes MAY change its
own authority. The condition that ends a delegation — the maintainer's own
terminating condition for the orders it records — is the maintainer's to apply
by changing the key; the foreman MAY report that the condition appears reached
and MUST NOT act on that report.

Full autonomy does not change what the daemon does. The daemon's
observation-only posture toward the foreman, the cardinal rule, and the
surface-only rules of this tree are unaffected by the key.

### The convene obligation

Under the consensus disposition the foreman MUST also SEEK the verdict it is
permitted to act on. That duty is the CONVENE OBLIGATION, and it is referred to
by that name elsewhere in this tree. The escalation conditions referred to below
are those stated in the paragraph beginning "The foreman MUST escalate, and MUST
NOT act, when consensus evidence is unavailable or insufficient".

The convene obligation applies to a decision when ALL of the following hold: the
effective valve disposition is consensus; the governing orchestrator contract
classifies the decision as a human valve within the closed, enumerated
vocabulary this specification binds to by reference; the decision is NOT one the
floors require to stay escalated, being neither a truly unresolvable decision
nor one human-gated BY DESIGN; and the decision is not the human valve id that
remains non-authorizable. Whether consensus evidence can in fact be obtained is
NOT part of this test, because that is discoverable only by attempting to obtain
it.

Where the convene obligation applies, the foreman MUST, within THIRTY MINUTES of
first observing that decision, do AT LEAST ONE of three things: successfully
constitute a cross-vendor review panel for it; record which escalation condition
applies to it, whether that condition applied when the decision was first
observed or has since come to apply; or record a DISCHARGE under the paragraph
below. Every leg shares that single wall-clock bound: the foreman that declines
MUST NOT have longer than the foreman that acts. Where none of the three is done
within the bound, the obligation is UNMET; doing more than one of them is not a
violation, because the obligation is satisfied by an artifact existing rather
than by exactly one existing; a decision MUST NOT be left unaccounted for on the
ground that no escalation condition existed.

So the bound is auditable rather than merely asserted, the foreman MUST record
the instant at which it first observes a decision the convene obligation applies
to. Where no such instant was recorded, the obligation for that decision is
UNMET; this specification does NOT reconstruct a retroactive observation
instant, because a reconstructed clock cannot be audited. The records this
obligation requires — the first-observation instant, the recorded escalation
condition, and the recorded discharge — live under the operator surface's own
`tmp/overseer/foreman/` subdirectory, so an auditor knows where to look and a
conformance check has something to read.

The obligation is DISCHARGED, not violated, when an attempt to constitute a
cross-vendor review panel within the bound cannot produce one — including where
a second vendor is unreachable. That is consensus evidence being unavailable,
and the foreman MUST then escalate under the escalation conditions rather than
act. A discharge MUST be RECORDED within the bound, naming the attempt made and
the reason a panel could not be constituted; an unrecorded discharge is an UNMET
obligation, not a discharge. No leg of this obligation may be satisfied without
leaving an artifact.

An unmet convene obligation MUST be surfaced, with the decision's coordinates,
so the omission is observable rather than silent. Elapsed inaction alone MUST
NOT be treated as compliance with this obligation.

This obligation is a duty to SEEK a verdict and never a widening of what a
verdict may authorize. It MUST NOT be read to extend the panel's authority
beyond the closed, enumerated vocabulary; to move any floor boundary; to relax
the requirement that a verdict satisfy the effective decision rule and be
typed; to relax the requirement
that reviewers be drawn from at least two distinct vendors; or to permit acting
where escalation is required. The cardinal rule, stated in §"The cardinal rule",
is unaffected.

### Relay and escalation discipline

When the foreman relays a panel or evaluator outcome to a supervised session,
or classifies and escalates that session's response, the following floors
apply. They govern the foreman's OWN behavior as a relaying and escalating
actor; they do not relax or extend any disposition floor stated above.

A relay that asserts a panel or evaluator outcome MUST embed the full record
in its first delivery to the session: every reviewer verdict with its
rationale verbatim, the evaluator's outcome, reason, and cache key where one
exists, and an on-disk path the session can independently read. An
attributed summary alone MUST NOT stand in for that record.

When the foreman classifies or escalates a supervised session's response, it
MUST quote the session's exact words rather than paraphrasing them; a
paraphrase MUST NOT be the basis for an escalation.

Before the foreman treats a supervised session's pushback as a challenge to
its own authority, it MUST first determine whether the pushback can be
satisfied with data the foreman already possesses or can produce. A request
for corroborating evidence or data is NEVER, by itself, an authority
challenge, and MUST NOT be escalated as one.

A "STILL alert" is the daemon's report-only `pane-still` attention condition:
a tracked session's pane content observed unchanged past the daemon's
stillness bound while its row does not read idle. Two consecutive STILL
alerts on the same tracked session MUST force the foreman to take a fresh
pane capture and re-classify that session's state, rather than relying on
any standing explanation it has already formed for the idleness.
Independently of alert count, no standing explanation the foreman holds for
an idle or still-alerted session remains valid unexamined past 30 minutes; the
foreman MUST re-verify it by that point regardless.

A monitor or watch the foreman relies on is a valid mechanism only while its
target is confirmed alive. Because a daemon bounce can invalidate a pane- or
process-scoped watch silently, any watch the foreman establishes MUST key on
re-resolvable identity (for example, a pane title) plus an explicit signal
that detects a bounce (for example, a daemon instance identifier), never on a
bare pane or process identifier alone.

When the foreman itself needs a human decision it cannot make — as distinct
from relaying a supervised session's own blocked declaration under "Notify,
never block" — it MUST default to a non-blocking escalation: the affected
track becomes a new membership condition on the daemon's existing mechanical
attention surface, never a parallel foreman-private status, and the foreman
schedules a bounded re-check rather than blocking its own operator loop on an
open-ended question. The channel used to alert a human of that condition is
an implementation choice outside this governed contract. A blocking question
MAY be used only as a last resort and only for a bounded wait with a defined
timeout, after which the escalation reverts to the non-blocking form. This
requirement governs only how the foreman surfaces a decision it cannot make
itself; it MUST NOT be read to alter, in any way, what may authorize a
restart of a tracked session — the cardinal rule, stated in "The cardinal
rule" section below, that a session
is restarted only when it declares itself ready on the filesystem, is
unaffected by this section.

Before the foreman delivers decision-relevant context to a supervised
session, it MUST determine from the daemon's own row for that session whether
that session is parked on a picker. Where the row reports a picker open, the
foreman MUST NOT deliver that context as an ordinary asynchronous message: a
session parked on a picker does not consume asynchronous input until the
picker resolves, so such a delivery is neither processed by the session nor
reported as failed to the sender. It MUST instead either deliver through the
picker's own free-text response channel, where the picker offers one, or hold
the context and re-check on a bounded schedule. A hold MUST be bounded and
MUST name the condition that releases it; an unbounded hold merely relocates
the stall from the recipient to the sender.

Where no usable row is available for that session — because the snapshot is
absent, unreadable, of an unknown schema, or stale — the foreman MUST treat
the session's picker state as UNDETERMINED, and MUST NOT deliver the context
as an ordinary asynchronous message on the assumption that no picker is open.
It MUST hold the context under the same bounded re-check required above and
surface that the row could not be read. An undetermined picker state MUST
fail closed toward holding: an unwarranted hold is visible to the holder and
bounded, whereas an unwarranted delivery is observed by no one.

This floor governs delivery routing only; like the escalation floor above, it
MUST NOT be read to alter, in any way, what may authorize a restart of a
tracked session — the cardinal rule, that a session is restarted only when it
declares itself ready on the filesystem, is unaffected by it.

Where the foreman raises a question that may stand open long enough to
accumulate later context, that question's own text MUST state where
late-arriving context is to be routed. The routing floor above is available
only to a sender that can read a daemon row; a human sender cannot, and the
question's text is the only channel that reaches them.

The foreman's PRESENTATION — how it renders its attention view, its tick
cadence, and its report formats — is deliberately outside the governed
contract, exactly as the cockpit's rendering is; it MAY evolve freely so long
as every governed guarantee holds. Guarantees the foreman's contract surface
relies on MUST be stated in this tree before an implementation that depends on
them lands.

Where the foreman raises a question whose option asks a session or an operator
to WAIT on an external target, and that target's kind is one the wait-premise
vocabulary in contracts.md §"The wait-premise record" expresses, the foreman
MUST record the wait-premise before raising the question, and MUST identify
that record in the option by its kind and target identifier, so a reader can
locate and re-query it without trusting the raiser.

Recording a premise is not sufficient: a premise nobody re-checks is prose
with a timestamp. The foreman that raised the question MUST re-verify that
premise against its recorded evidence source by the record's re-check instant,
and a foreman that assumes responsibility for a raised question INHERITS that
obligation. The outcome MUST be surfaced where the premise fails, has expired,
or cannot be tested; a re-verification that passes needs no announcement, so
this obligation does not emit a line per healthy wait per cycle. Where the
foreman determines that an option's premise has expired, or that its target
cannot be confirmed by that premise's recorded evidence source, it MUST
SURFACE the option as resting on a failed premise.

The purpose is re-checkability, not enforcement against a rendered surface.
Such an option MUST be capable of being tested against its named record's own
evidence source, without re-reading the option's prose and without trusting
the raiser. Nothing in this paragraph authorizes any actor to alter, withdraw,
answer, or select an option once raised; a question already showing a
structured gate remains subject to the acting suppression that constraints.md
§"Acting safety" governs, without exception.

The recording obligation is FAIL-SOFT and MUST NOT suppress the question.
Where the target's kind is not expressible in that closed vocabulary, or the
record cannot be written, the question MAY still be raised, and the foreman
MUST surface that the option carries no re-checkable premise, so a reader
knows the wait rests on prose alone. This paragraph governs the foreman's own
behavior as a question-raising actor, consistent with the scope of the section
it sits in; an open picker raised by a supervised session's own harness
remains something this tree OBSERVES rather than something it forbids. The
cardinal rule is unaffected.

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
makes that state unrepresentable. There are exactly three values a session
writes — `ready`, `blocked: <one-line reason>`, and `winding-down` — plus one
value the daemon writes to itself (`idle-with-context-left`, per §"The
keep-going nudge"). A malformed value is surfaced to the operator and treated
as NO declaration at all — fail-closed, so a typo can never restart anything.
A session's one state file remains writable ONLY by that session and the
daemon's single self-token. The foreman MUST NOT write any value into any
track's state file.

Declaring is mandatory once a wrap-up has been received: a session chooses
WHICH value fits, but declining all three does not buy a reprieve — the track
is reported as not responding and sits untouched until a person intervenes.

Pane text remains trusted ONLY for the busy / idle / gate signals. Ambiguous,
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
below its wind-down threshold satisfies the runtime-specific eligible-input
predicate and is settled: Claude requires a positively empty input box; Codex,
whose empty placeholder cannot be distinguished from typed text, requires its
structural idle-input evidence — a live prompt and statusline with no generating
marker or picker. The pane MUST NOT be generating, changing, sub-agent-busy,
gated, runtime-reported as waiting on a human, or carrying `blocked:`, `ready`,
or a fresh `winding-down`; a stale acknowledgement MAY resume escalation.
Affirmatively recognized background-shell evidence alone does not prevent the
round. The daemon re-checks every authorization input immediately before acting,
records an injection stamp durably, then pastes the wrap-up while leaving the
shell running. The stamp is written BEFORE the paste, so a declaration that
responds to the wrap-up is always newer than the stamp. The round closes when
the daemon restarts the session — which deletes the state file and the round's
stamp together — so a declaration can never re-trigger, and a stamp can never
outlive its round. The recovered-round closure defined below is the one
other closure, and it deletes the round's durable record only when the state
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
`blocked`, `winding-down`), however stale, holds the round open, an
unreadable or malformed state file holds the round open exactly as a
declaration would, and only the daemon's own idle marker is treated as
absence. It MUST NOT occur while the round's resume submission is pending,
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
open indefinitely, and such a track remains visible through the existing
standing-declaration attention members.

## The escalating wrap-up

The wrap-up is the daemon's ONLY lever — nothing is ever force-killed — so it
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
the exact state-file path and the three values it may write; that the plan's
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
exact state-file path and the three values it may write, and restating that a
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
round only, mirroring the void-notice it supersedes; a round-less standing
declaration (per §"Fail-soft posture", a declaration standing on a track that
has NEVER been in a round) has no round to expire within and remains governed
entirely by that existing, separate, continuously-surfaced rule — it is
neither expired nor notice-eligible under this paragraph.

## The restart

Once — and only once — a fresh `ready` declaration passes the restart
interlock (per contracts.md §"The restart interlock"), the daemon replaces
the supervised session's pane process in a single atomic operation and hands
the fresh session exactly one prompt: read the plan state held on this
track's ledger epic and follow it — a prompt that MUST name the track's
repository path and its recorded epic id literally, so a session opening
with no prior context can resolve what to read without opening any plan-tree
file. The abrupt kill is safe precisely BECAUSE of the declaration: the
session asserted it is at a clean stopping point, and only the process is
replaced — every file, worktree, branch, and commit on disk survives.

Every step of the restart is a hard gate, and its two failures are not the
same. A respawn that FAILED — the pane's process was never replaced — is
surfaced and the `ready` declaration is PRESERVED so the next observation
retries; a declaration is never silently destroyed. A respawn that SUCCEEDED
but whose fresh session is never recognized has already destroyed the
predecessor, so it consumes the kill authorization: the round is held open
for submission retry only, and any further kill requires a genuinely fresh
`ready` (per contracts.md §"The restart interlock"). When the fresh session comes up but the resume
prompt fails to submit, the daemon retries the SUBMISSION ONLY, never a
second kill: re-killing stays gated on a fresh `ready` alone, so the retry
can never escalate. A fresh session that comes up showing a structured gate
is never keystroked; it is surfaced as waiting on a human, with the round
held open.

A session that declares `ready` and then resumes work — narrates further,
emits more turns, streams stop-hook output — keeps its declaration armed; the
restart branch's settle and busy gates prevent a kill mid-work without
requiring any activity-based clearing. The declaration is cleared only by a
successful restart or by exceeding its bounded maximum age (per contracts.md
§"The state file", its "Stale-declaration voiding" rule).

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
and MUST re-check it at wrap-up time, so a mid-session `/model` switch is
honored by the next restart's re-assertion.

The `harness` value MUST be treated as an open string in storage, so an
unrecognized future harness can be recorded with no schema change; DISPATCH
MUST enumerate known harnesses, and the daemon MUST relaunch a track only
for a harness it recognizes. An unrecognized or unadoptable harness's
profile MUST be surfaced report-only and MUST NOT be used to construct or
guess a relaunch command — aiming one runtime's relaunch command at
another runtime's pane destroys the session.

A track's mapping row that carries no launch profile MUST continue to
relaunch exactly as it does today; this is fail-soft by construction and
requires no migration of existing rows. A launch profile MUST NOT record
any secret or token value; it records only the harness, the model token,
and the wrapper's path, since the wrapper itself owns its own secrets.

On every relaunch, the daemon MUST explicitly set or unset
`ANTHROPIC_MODEL`, `ANTHROPIC_SMALL_FAST_MODEL`, and the `CLAUDE_CODE_*`
context-limit override environment variables rather than passively
inheriting them — set to the recorded profile's values for a wrapper/local
track, and unset for a cloud track with no wrapper recorded. A wrapper's
own deference to an inherited value (e.g. `ANTHROPIC_MODEL="${ANTHROPIC_MODEL:-default}"`)
means a leaked inherited value would silently win over the wrapper's own
intended default, so passive inheritance is the failure mode in both
directions.

A stale or corrupt profile — a recorded wrapper path that is missing or
not executable, a recorded model token the runtime rejects, or a
harness/wrapper mismatch — MUST be surfaced and MUST cause the daemon to
skip that restart rather than silently falling back to a default-model or
default-wrapper launch, which would reproduce the exact silent-downgrade
defect this section exists to close.

## The keep-going nudge

The wrap-up addresses a session running LOW on context. The inverse failure
is a session that stops EARLY — idle while still comfortably above its
threshold, wasting headroom it still has. The daemon closes that gap with a
single keep-going nudge per idle episode: when a tracked session has been
CONTINUOUSLY idle for at least one hour, is above its threshold, is not
waiting on a human, and has made no declaration of its own, the daemon pastes
one message telling it to continue, and writes `idle-with-context-left` to
the state file as a note to itself so the same episode is never re-nudged.

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
runtime report of waiting on a human, no standing `blocked:` — and the
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
runtime-reported as waiting on a human, sub-agent-busy, blocked by declaration,
or missing the input evidence that act requires. Background-shell evidence
alone does not suppress an otherwise qualified informational paste. Exactly
five acts apply that rule: the low-context wrap-up for any supervised
entity, using the runtime-specific predicate in §"The supervision round";
the once-per-round expiry-notice of §"The escalating wrap-up", which is that
wrap-up's round-scoped tail and fires under the wrap-up's own complete
guarded-paste predicate rather than an independent one; the
idle-with-context-left keep-going nudge specified above; this bounded
pair-stall nudge into the supervisor; and the bounded charter-reminder paste
into a stalled reserved-entity picker in §"The stalled-picker charter
reminder". The fifth member is the sanctioned exception of constraints.md
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

- The topic is in the reserved entity namespace — BOTH the `-supervisor` and
  the `-foreman` suffix. It NEVER applies to an ordinary worker topic.
- The target pane is positively identified as that track's supervised
  session. That identity gate holds upstream in the evaluation precedence
  rather than inside this act.
- The daemon's DERIVED row status for the track is `blocked:human`. That is the
  daemon's own classification, NOT one of the three values a session may write,
  per §"Out-of-band state declaration"; the daemon reaches it from several
  distinct kinds of evidence and this section does not enumerate them. In every
  state where THIS act can fire, the classification is reached from live gate
  evidence, optionally alongside a standing `blocked:` declaration or a foreman
  pane claim — which follows from the open-picker clause below rather than from
  any property of the status itself. The act therefore requires no declaration
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
It does not separate it from the foreman's own valve acts, which do submit
and which are governed by the foreman sections and the v020 delivery-routing
floor rather than by this enumeration.

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
holds. The runtime's own auto-compaction is the recognized case: it can
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
construction, so the filter is always available to a reader. The daemon
holds the epic id as an OPAQUE LOCATOR — it hands the id and the entity name
to sessions, and it never reads those entries, never hashes them, and never
inspects them as restart authorization. Because the daemon never reads
inside a plan directory on the discovery or consumption path — the sole
exception being the supervisor resume-artifact certification per
contracts.md §"The restart interlock" — it can never re-derive that id
for itself on any other path: the id
is recorded into the row AT TRACK ASSIGNMENT — the moment the row itself
comes into being, since the store holds one row per ASSIGNED track — by
whichever surface performs that assignment, read from the plan's write-once
metadata anchor. This specification does not make any one surface the
assigner; the obligation attaches to whichever surface performs the
assignment. Where that surface is the authorized unattended foreman,
§"Non-interference with tracked work" grants it this purpose expressly,
alongside its own decision-routing. A track assigned when the anchor cannot
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
whose plan has been archived or deleted are garbage-collected — with two
protections: an ACTIVE plan always wins over a same-named archived copy, and
a repository whose root is transiently unreachable is never mistaken for a
deleted plan.

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

The `-supervisor` suffix is RESERVED for pair members (per §"Supervised
runtimes"), and the `-foreman` suffix is RESERVED for the per-repository
foreman surface. Both are compared case-insensitively. A worker entity MUST
NOT be derived, registered, or accepted under a session name ending in a
reserved suffix; the check MUST be applied to the final derived name —
including the repo-slug-qualified form the cross-repository collision
qualifier produces — and the offending derivation MUST be refused and
surfaced by name, never reduced to a warning and never silently skipped. The
daemon MUST refuse to adopt a live session whose registry name ends in a
reserved suffix, so a foreman or supervisor session can never be captured as
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

The attended supervisor's completion control is a separate structured marker
at `<repo>/tmp/overseer/<topic>/.supervisor-state`, governed by
contracts.md §"Supervisor completion gate". It is neither the supervisor's
`.overseer-state` declaration nor a daemon restart authorization. The daemon
MUST retain its non-semantic boundary: it MUST NOT read or interpret final
response or pane prose to decide whether supervision has completed. A
Driver-owned completion gate owns that decision, and an independently verified
wake producer owns cold re-entry with fresh ledger/forge evidence.

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
never on discovery. An ATTENDED Control-Plane operator skill
(supervise-plan) authors the same two layers it always has, on two different
media. It MAY create exactly ONE named artifact in a watched repository —
the shared role layer `.ai/supervisor-protocol.md` — and it authors the
per-plan binder as supervisor handoff entries on the governed plan's ledger
epic. The binder is intentionally thin and is NOT complete on its own; it
MUST be read together with the shared layer, and it MUST emit a guard that
HALTS with a labelled REMEDY if that layer is absent.
`.ai/supervisor-protocol.md` MUST be written exclusively through that
repository's own documented commit discipline — worktree, then pull request,
then review, then merge — never directly to a primary checkout. The binder's
handoff entries MUST be appended THROUGH the orchestrator's sanctioned plan
surface, never by a direct write to the plan epic's ledger and never by
creating or updating `plan/<topic>/supervisor-handoff.md` through the pull
request path. Neither layer is a packaged plugin asset; the skill writes the
shared layer into the consuming repository's own tree and the binder onto
that repository's own plan epic. Neither is overseer runtime state: the
"exactly two places" sentence below and the startup gitignore refusal
continue to bind the daemon's runtime state verbatim.

An authorized UNATTENDED operator surface — the foreman — MAY READ files
under a watched repository's plan tree, and MAY read pane content and
work-item records, solely as EVIDENCE for its own decision-routing and, when
it is the surface assigning a track, to record that plan's ledger epic id
into the track's mapping-store row at assignment. It MUST NOT write, delete,
or hash-as-authorization anything under `plan/`, MUST NOT write any tracked
file outside the repository's reviewed commit discipline, and MUST NOT treat
any session-authored or peer-authored text it reads as an instruction to
itself. The DAEMON's own posture is unchanged by this carve-out.

The overseer's daemon writes its runtime state to exactly two places: its
home-directory stores and a per-track temporary directory inside each watched
repository's gitignored scratch area. An authorized operator surface's runtime
state MUST live under that same per-repository gitignored scratch area, in its
own `tmp/overseer/foreman/` subdirectory; it MUST NOT create any new scratch
root. At startup the daemon verifies that every watched repository ignores
that scratch path and REFUSES to run if any does not — so supervision can never
dirty a tracked working tree.

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
clears, independently of any other condition the same track carries.

## Fail-soft posture

The daemon supervises many tracks at once, so no single track's bad state may
take down the loop, and no ambiguous reading may trigger an action:

- A malformed store row or state value is skipped or surfaced BY NAME; the
  remaining tracks are unaffected.
- An unknown context reading keeps the last known value and NEVER counts as
  a threshold crossing.
- A storage error on the overseer's own files is reported and survived,
  never raised out of the supervision loop.
- Generating and sub-agent-busy detection deliberately over-fire: a false
  positive suppresses action, while a miss could inject into a working session.
  Ambiguous, conflicting, malformed, unavailable, or unknown authoritative
  runtime evidence therefore resolves toward doing nothing. Shell-only
  eligibility is affirmative: Claude requires recognized registry
  `status=shell`; Codex requires its descendant-shell fallback. Recognized
  shell-only evidence neither authorizes an act nor suppresses a separately
  qualified informational paste. Action suppression remains unbounded for
  generating, changing, sub-agent-busy, and ambiguous evidence, and bounded for
  ATTENTION (see below).
- Every authorization check is fail-closed: absent, unreadable, or
  unexpected inputs answer "no".

Suppressing action without limit for generating, changing, sub-agent-busy,
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

A declaration standing on a track that has NEVER been in a round — no
injection stamp and no recorded expiry, as after an out-of-band session
replacement, a lost sidecar, or an unprompted write — carries no certification
floor and therefore cannot certify. The daemon MUST NOT paste into that pane
either, because a standing declaration is never keystroked over (per
contracts.md §"The wrap-up injection"). Such a track MUST be surfaced to the
operator for as long as the declaration stands, and the state MUST NOT be
described as self-healing: it is not, and the track receives no further
escalation-band warnings while its remaining context runs down. A fresh session-written `ready`
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

**Scope.** The operation MUST observe every account tracked by the host's coding-agent account manager, MUST report their remaining quota, and MUST rotate the host-wide active credential when the active account's allowance is nearly spent. It MUST NOT implement, install, or version the account-manager binary itself; that remains a host concern.

**Observation.** The operation MUST derive every quota figure from utilization percentages and MUST NOT depend on the monetary fields of the usage response, which are absent on the subscription plans in use. It MUST poll the active account with the live credential and every other account with that account's stored snapshot. It MUST treat an absent scoped-model allowance as a normal condition and not as an error.

**Never refresh.** The operation MUST perform read-only requests only and MUST NOT perform an OAuth refresh under any circumstance, because rotating a refresh token outside the agent's own control can revoke the whole token family. It MUST detect a locally-expired token and skip the request rather than send it, because the usage endpoint backs off a specific repeatedly-rejected token and a loop that retries a dead token manufactures the error it then reports.

**Identity.** The operation MUST NOT depend solely on the account manager's own report of which profile is active. That report is derived by byte-matching the live credential against each snapshot and therefore becomes unavailable whenever the agent refreshes its own token as normal operation. The operation MUST fall back to matching a stable account identifier that survives token rotation, and MUST fail loudly only when both paths fail.

**Rotation triggers.** The operation MUST rotate when the active account's short-window allowance is at or above a configurable threshold, or when its weekly remaining falls below a configurable reserve. The threshold SHOULD be set high enough that the window is nearly drained before moving, but low enough that heavy fleet use cannot cross the remaining margin between two polls. Candidates MUST be compared on whichever dimension triggered the rotation; comparing on a dimension that is not the reason for leaving MAY select an account that is no better off in the way that matters.

**Eligibility.** A candidate MUST hold at least a configurable margin more headroom than the active account on the triggering dimension. This test MUST be relative rather than absolute: an absolute test strands the fleet once every account sits just above the bar, holding while the active account runs to exhaustion. The margin also makes oscillation impossible, since a switch requires a strict improvement that the reverse move cannot match. A candidate MUST be disqualified when it has no weekly allowance remaining or cannot serve a request immediately.

**The weekly reserve MUST NOT be forfeited.** Candidates below the reserve MUST be excluded while any candidate is above it, and the reserve MUST be released once every account is below it, since at that point it protects nothing.

**A scoped-model allowance MUST NOT influence account selection.** It MUST NOT trigger a rotation, MUST NOT disqualify a candidate, and MUST NOT tier or rank candidates. Such an allowance caps how much of the weekly allowance a single model may spend and draws down the general weekly allowance as it is used, so leaving it unspent forfeits no capacity while leaving weekly unspent forfeits it permanently. The allowance MUST inform only which model a session runs.

**Ranking.** Eligible candidates MUST be ranked by soonest weekly reset, so that the most perishable balance is spent first. A candidate whose reset time cannot be read MUST sort last and MUST NOT be treated as imminently resetting.

**Only a live-verified account MAY be switched onto.** A candidate whose own stored credential could not be exercised during the current pass MUST NOT be selected, because that credential is precisely what a switch installs as the host-wide login, and post-switch verification cannot detect the failure: the switch succeeds onto a dead token. Where no candidate can be verified, the operation MUST hold, MUST report which accounts could not be verified, and SHOULD state how to revive them. A stalled rotation costs quota; a bad switch stops every running session on the host.

**The set of verifiable accounts MUST be actively maintained, not merely reported on.** The live-verified rule above is absolute, and on its own it deadlocks: an idle account's short-lived access token lapses after several hours, so the set of valid destinations drains to empty precisely when rotation becomes necessary, and the operation holds every tick while the active account runs to exhaustion. Reporting the condition is not a remedy — the operation MUST refresh an idle account's stored credential before it lapses, and MUST do so on a schedule and with a retry backoff such that a persistently unrefreshable account is neither abandoned silently nor retried without limit. An account that cannot be refreshed MUST be reported as such, because discovering an orphaned credential while merely maintaining the set is far cheaper than discovering it at the moment of rotation. That report MUST distinguish an unrecoverable credential from a transient or policy condition, and MUST carry the underlying diagnostic rather than a summarised verdict: the remedies differ, and prescribing re-authentication for an account that is merely capped wastes the operator's effort on a credential that is fine. An account whose credential is still valid MUST NOT be reported as a failure merely because no refresh was necessary. The operation MUST establish an account's refreshability by attempting it; a recorded expiry claiming future validity MUST NOT be treated as evidence, because a credential can be revoked or rotated while that field still reads far in the future.

**Refreshing MUST delegate to the agent, and MUST NOT touch the live credential.** This obligation does not weaken the prohibition on out-of-band refresh: the operation MUST perform the refresh by exercising the stored credential through the agent itself, in an isolated configuration sandbox, so that the agent performs its own refresh, and MUST NOT call the token endpoint directly. The operation MUST leave the host's live credential byte-identical across the whole maintenance pass, MUST verify that it did, and MUST report a failure loudly if it did not — silently swapping the account the host is using would be a worse fault than the deadlock being fixed. A maintenance failure MUST be survivable and MUST NOT disturb the quota report or the rotation.

**Switching.** The decision-and-switch sequence MUST be serialized by a non-blocking host-level lock, and a caller that cannot take the lock MUST hold rather than wait. Holding the lock, the operation MUST re-read the active account and abandon a decision whose premise changed, and MUST re-exercise the destination credential immediately before installing it. After switching it MUST verify the switch took effect and MUST report a failure rather than a success when it did not, since concurrent sessions share the credential file and MAY silently reinstate the previous account.

**Model enforcement.** Sessions whose name carries the foreman suffix MUST be pointed at the scoped model while the active account retains that allowance, and at the general model otherwise; when the allowance is spent, every other agent session MUST also be reset to the general model, and otherwise other sessions MUST be left alone. Suffix matching MUST be exact. Enforcement MUST be advisory and best-effort: a busy session MUST be skipped rather than driven, a failure affecting one session MUST NOT stop the sweep, and no enforcement failure MAY disturb the quota report or the rotation.

**An operator override MUST be able to pin the enforced model, and it MUST persist.** The precedence rules above are all derived from the scoped-model *balance*, so they cannot observe a model that is available but not answering — a model refusing requests for non-quota reasons reads as perfectly healthy, and enforcement goes on pinning sessions to it. The operation MUST therefore accept an explicit operator pin that overrides the foreman precedence rules, MUST leave the rules governing other sessions unaffected by it, and MUST persist the pin in its durable state. Persistence is not a convenience: the operation re-runs on a schedule, so a pin that lasted one run would be reverted by the next tick and would appear to work while doing nothing. The operation MUST provide a way to clear the pin and restore derived behavior, MUST ignore an unrecognized pin value without failing and without disturbing an existing pin, MUST ignore a stored pin value it does not recognize so that corrupt state degrades rather than breaking enforcement, and MUST report when a pin is in effect. Where a pin selects a model whose allowance is exhausted, the operation MUST warn and MUST still honor the pin; the operator is warned, not overruled.

**Operation state MUST be persisted after enforcement, not before it.** Enforcement writes durable state of its own — at minimum the operator pin and the per-session suppression memo. Persisting before enforcement runs discards those writes, which silently defeats both while leaving every observable symptom of a working implementation. The persistence step MUST run even when enforcement itself failed, and MUST NOT be able to fail the run.

**The operator-facing report MUST NOT assert figures it cannot know.** Where a remembered reading describes an allowance window that has since rolled over, the operation MUST withhold the figures and mark the row as stale rather than render them, because such figures describe a period that no longer exists and understate a balance that has in fact replenished. This is a reporting obligation with no effect on selection — an unverifiable account is already ineligible — and it matters precisely because it does not: the machine is protected from the stale reading by the live-verification rule, so the only consumer left to mislead is the human deciding whether to intervene, and a report that understates an account's balance steers that operator away from the best available account. A safety rule that keeps bad data out of the decision path MUST NOT be mistaken for one that keeps it off the display.

**Session identity.** A session's model MUST be determined programmatically and MUST NOT be read from the terminal status line, which truncates in a narrow pane and previously caused affected sessions to be classified as non-agent sessions and excluded from enforcement indefinitely. A session whose model cannot be determined MUST be treated as possibly needing to be set rather than skipped, and repeated attempts against such a session MUST be bounded by a time-based memo.

**Effort MUST be re-asserted as a floor.** Installing an account's snapshot restores a settings file that carries the reasoning-effort key, so a rotation silently overwrites it. The operation MUST restore the configured effort when the live value is lower, MUST leave a deliberately higher value untouched, and MUST rewrite only that key, preserving hook, environment, plugin and integration configuration in the same file.

**Fail loudly.** Every failure path MUST emit a clearly-marked failure line and exit non-zero, including unexpected failures, so that a missing binary or an unwritable state directory can never present as a quiet success.
