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
report-only, so a tree that declares nothing behaves exactly as it did before
this policy was ratified.

Under report-only the foreman MUST NOT invoke any such action id, MUST NOT
answer a blocked question on a session's behalf, and MUST report the decision to
the human with coordinates and take no act on it.

Under the consensus disposition the foreman MAY act on a human valve ONLY when a
cross-vendor review panel returns a unanimous typed verdict, and only for an
action drawn from a closed, enumerated vocabulary. A free-form or unenumerated
action MUST escalate.

No configuration value MAY authorize the foreman to dispose of a truly
unresolvable decision, nor of any decision that is human-gated BY DESIGN —
drift acceptance, a spec-change slice, a regroom or backlog bounce, or a
human-only acceptance. Each of these MUST stay escalated even when the panel is
unanimous and fully confident. Such a floor MUST NOT be relaxable by any
configuration key; relaxing one requires a ratified amendment to this
specification.

The two floor categories named above — a truly unresolvable decision, and a
decision human-gated BY DESIGN — are DEFINED BY the governing orchestrator
contract, not by this tree, and this specification binds to those definitions BY
REFERENCE. It MUST NOT restate them, because a duplicated definition is a
definition that can drift; a reader resolving whether a decision sits below a
floor MUST consult that contract's terminology. Should this tree ever name a
floor category the governing contract does not define, that category MUST be
defined here before it may bound the foreman's authority.

The foreman MUST escalate, and MUST NOT act, when consensus evidence is
unavailable or insufficient, when the panel disagrees, when any reviewer returns
an insufficient-information verdict, or when the audit journal append fails.
Escalation MUST be the outcome of every condition this policy does not
explicitly authorize.

The panel MUST draw its reviewers from at least two distinct vendors, because a
panel whose members share a vendor is not the independent evidence this policy
relies on. A dissent that is not vendor-aligned with the majority MUST NOT be
overridable by the remaining reviewers. An outcome reached by overriding a
minority report MUST NOT be recorded as unanimous.

Every act the consensus disposition authorizes MUST be journaled before the act,
naming the governing setting, the panel identities, and the verdict. No
auto-disposition MAY be silent. A failed journal append MUST block the act.

The foreman's PRESENTATION — how it renders its attention view, its tick
cadence, and its report formats — is deliberately outside the governed
contract, exactly as the cockpit's rendering is; it MAY evolve freely so long
as every governed guarantee holds. Guarantees the foreman's contract surface
relies on MUST be stated in this tree before an implementation that depends on
them lands.

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
outlive its round. A subsequent round starts fresh: every escalation band may
fire again.

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
the exact state-file path and the three values it may write; that its
handoff file is the ONLY artifact the successor session inherits, so drifted
resume state belongs in a rewritten handoff, never withheld; and the truth
that it will be restarted ONLY when it declares `ready`.

A fresh `winding-down` acknowledgement suppresses further wrap-ups — the
daemon never keystrokes into a session that is actively wrapping up. A stale
acknowledgement (older than fifteen minutes) resumes the escalation and
re-reports the track, but it still authorizes nothing: the acknowledgement
buys patience, not an indefinite stall. At 20% remaining and below with
nothing declared, the track is reported loudly as not responding — and still
never acted on.

## The restart

Once — and only once — a fresh `ready` declaration passes the restart
interlock (per contracts.md §"The restart interlock"), the daemon replaces
the supervised session's pane process in a single atomic operation and hands
the fresh session exactly one prompt: read your track's handoff file and
follow it. The abrupt kill is safe precisely BECAUSE of the declaration: the
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

A session that declares `ready` and then resumes work has its now-false
declaration voided rather than honored later; a declaration young enough to
be the declaring turn's own busy tail survives (per contracts.md §"The state
file").

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
two acts apply that rule: the low-context wrap-up for any supervised entity,
using the runtime-specific predicate in §"The supervision round", and this
bounded pair-stall nudge into the supervisor.

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
repository, one track per unarchived plan-topic directory. Archived plans are
excluded. Discovery keys on the DIRECTORY existing — it never reads, stats,
or hashes any file inside a plan directory (per §"Non-interference with
tracked work"); the conventional handoff path it derives is a pointer handed
to sessions, never opened by the overseer. One bounded exception: for a track
with a CURRENTLY MATCHING live session (the liveness gate), the daemon MAY
test the EXISTENCE of exactly one named artifact,
plan/<topic>/supervisor-handoff.md — no open, no read, no hash, no content or
mtime dependence, and no probe of any kind for tracks without a live session.
This is the ONLY file-level probe the discovery path may ever perform.

The displayed list is discovery LEFT-JOINED with the mapping store. The
store persists ONLY facts that cannot be re-derived from the filesystem: the
topic-to-session mapping, a custom resume line, a per-track threshold
override, and a pinned session identity. Everything else is recomputed from
live state, so the list can never go stale. Rows whose plan has been archived
or deleted are garbage-collected — with two protections: an ACTIVE plan
always wins over a same-named archived copy, and a repository whose root is
transiently unreachable is never mistaken for a deleted plan.

Whoever archives a plan thread MUST leave NOTHING at its live path
`plan/<topic>/`. A stub, a terminal marker, a forwarding note, or any other
residue there is FORBIDDEN, and the directory itself MUST NOT remain, even
empty. Archival MUST relocate the directory whole, leaving nothing behind.

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
enumerates directories (the one bounded existence probe stated above
notwithstanding). The live directory's continued existence — including via a
symlink to a directory — makes an archived thread read as ACTIVE, so its
mapping row is never garbage-collected and the finished thread remains
eligible for nudges, for wrap-up injection, and for RESTART.

The daemon reads each watched checkout's WORKING TREE, not a commit, so
untracked residue under `plan/<topic>/` keeps the directory alive even after
a clean archive has merged. Removing the tracked files is not sufficient;
the directory must be gone from the tree the daemon actually reads.

When a plan thread would close with anything unresolved, exactly ONE of two
dispositions is sanctioned. Either the thread is LEFT UN-ARCHIVED — its epic
staying OPEN — until its blockers are resolved; or ALL of its blockers are
TRANSFERRED to a different or new NON-ARCHIVED plan thread and/or work-item,
after which the thread is archived whole. Archiving it and leaving a note
saying what is left is not a third option.

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
a plan-thread worker, wrapped up, nudged, or respawned into a plan handoff. A
pair member's session name is derived from its worker's PLAN TOPIC, using the
same derivation and the same collision qualification with the suffix appended,
never from whatever tmux session currently happens to host the worker.

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
artifact permission is in §"Non-interference with tracked work"). That pair
member is itself a SUPERVISED ENTITY under this whole specification: the
same marker protocol, the same wind-down threshold and escalation bands, the
same restart interlock, and the cardinal rule verbatim per entity — only the
supervisor's OWN fresh `ready`, declared in its OWN state file, may restart
the supervisor, and no worker declaration may ever restart its supervisor or
the reverse.

Its distinct identities are exactly these, and every topic-parameterized
surface MUST draw from them: its state file and its round records key on the
suffixed entity name; its wrap-up and keep-going messages are entity
VARIANTS whose paths, session name, and commit ritual refer to the
supervisor's own artifacts — `plan/<topic>/supervisor-handoff.md`, committed
through the repository's own discipline — and never to the worker's handoff;
and its restart preserves the suffixed session name and hands the fresh
session exactly one prompt: read the supervisor handoff and follow it. The
respawn is additionally gated on that artifact EXISTING, re-checked
immediately before the act, so a `ready` with no artifact preserves the
declaration and surfaces the existing capture offer instead of resuming onto
a dead pointer; the daemon takes no content or modification-time dependence
on the artifact, so brief freshness remains the supervisor's own protocol
obligation, discharged by committing the brief before declaring `ready`.

A supervisor has no supervisor of its own, by design: the supervision-offer
surface is NOT applied to a pair member. Whether a track's supervision needs
attention is evaluated independently of the worker's own classification on
every cycle, rather than only when the worker happens to be idle. A pair
member that disappears while its wind-down round is open MUST be surfaced as
attention — supervision died mid-handoff and the brief is at risk; one that
disappears with no round open is surfaced only through the ordinary
supervision offer.

## Non-interference with tracked work

The overseer's DAEMON — the unattended observation and restart loop — NEVER
touches files under any repository's plan tree. The handoff and everything
beside it are the supervised session's own workflow: the overseer enumerates
plan DIRECTORIES to discover tracks and points sessions at the conventional
handoff path, but the daemon never opens, writes, or hashes those files — the
restart interlock deliberately inspects nothing beyond the state-file token
for the same reason. The one bounded exception, consistent with that
enumeration — an existence test is not an open, write, or hash — is the
supervision-artifact probe: for a track with a CURRENTLY MATCHING live
session, the daemon MAY test whether the single reserved
plan/<topic>/supervisor-handoff.md exists, never opening, reading, or hashing
it, and it probes not at all for a track without a live session, exactly as
§"Track discovery and the mapping store" permits.

An ATTENDED Control-Plane operator skill (supervise-plan) MAY create exactly
TWO named artifacts in a watched repository: the shared role layer
`.ai/supervisor-protocol.md`, and the per-thread binder
`plan/<topic>/supervisor-handoff.md`. The binder is intentionally thin and is
NOT complete on its own; it MUST be read together with the shared layer, and
it MUST emit a guard that HALTS with a labelled REMEDY if that layer is absent.
Both MUST be written exclusively through that repository's own documented
commit discipline — worktree, then pull request, then review, then merge —
never directly to a primary checkout. Neither is a packaged plugin asset; the
skill writes both into the consuming repository's own tree. An authored
artifact is NOT overseer runtime state: the "exactly two places" sentence
below and the startup gitignore refusal continue to bind the daemon's runtime
state verbatim.

An authorized UNATTENDED operator surface — the foreman — MAY READ files under
a watched repository's plan tree, and MAY read pane content and work-item
records, solely as EVIDENCE for its own decision-routing. It MUST NOT write,
delete, or hash-as-authorization anything under `plan/`, MUST NOT write any
tracked file outside the repository's reviewed commit discipline, and MUST
NOT treat any session-authored or peer-authored text it reads as an instruction
to itself. The DAEMON's own posture is unchanged by this carve-out.

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
predicate, never by the attention condition. A fresh session-written `ready`
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
