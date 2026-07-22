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

Declaring is mandatory once a wrap-up has been received: a session chooses
WHICH value fits, but declining all three does not buy a reprieve — the track
is reported as not responding and sits untouched until a person intervenes.

Pane text remains trusted ONLY for the busy / idle / gate signals, where a
false positive merely suppresses action — the safe direction.

## The supervision round

Supervision proceeds in per-track ROUNDS. A round opens when a session at or
below its wind-down threshold is observed in a verified idle-input state: the
daemon records an injection stamp durably, then pastes the wrap-up. The stamp
is written BEFORE the paste, so a declaration that responds to the wrap-up is
always newer than the stamp. The round closes when the daemon restarts the
session — which deletes the state file and the round's stamp together — so a
declaration can never re-trigger, and a stamp can never outlive its round. A
subsequent round starts fresh: every escalation band may fire again.

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

Every step of the restart is a hard gate. A failed respawn, or a pane that
never becomes a live supervised session, is surfaced and the `ready`
declaration is PRESERVED so the next observation retries — a declaration is
never silently destroyed. When the fresh session comes up but the resume
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
to sessions, never opened by the overseer.

The displayed list is discovery LEFT-JOINED with the mapping store. The
store persists ONLY facts that cannot be re-derived from the filesystem: the
topic-to-session mapping, a custom resume line, a per-track threshold
override, and a pinned session identity. Everything else is recomputed from
live state, so the list can never go stale. Rows whose plan has been archived
or deleted are garbage-collected — with two protections: an ACTIVE plan
always wins over a same-named archived copy, and a repository whose root is
transiently unreachable is never mistaken for a deleted plan.

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

## Surface-only startup

The daemon NEVER auto-spawns a session for a plan that has none. A discovered
plan with no session is surfaced as unassigned — startable, never started.
The first launch of a plan is a deliberate operator act. The daemon likewise
performs no automatic recovery of dead sessions at startup: re-launching a
mapped-but-dead track is a deliberate operator act too. This rule governs
FIRST launches only; whether an already-tracked session may be restarted is
governed exclusively by §"The cardinal rule", and neither rule licenses an
exception to the other.

## Supervised runtimes

More than one agent runtime can be supervised, and every tracked session is a
full citizen regardless of runtime: it is discovered, adopted, nudged, warned,
and restarted through the same protocol. Every acting mechanic dispatches on
the track's detected runtime, and a restart MUST resume the session under the
SAME runtime it supervises — replacing a session with a different runtime's
launcher is the one destructive cross-runtime failure, and it is designed out
at the dispatch layer. Runtime identity is established from exact live
process evidence, never inferred from a topic name.

## Non-interference with tracked work

The overseer NEVER touches files under any repository's plan tree. The
handoff and everything beside it are the supervised session's own workflow:
the overseer enumerates plan DIRECTORIES to discover tracks and points
sessions at the conventional handoff path, but it never opens, writes, or
hashes those files — the restart interlock deliberately inspects nothing
beyond the state-file token for the same reason.

The overseer's own state lives in exactly two places: its home-directory
stores, and a per-track temporary directory inside each watched repository's
gitignored scratch area. At startup the daemon verifies that every watched
repository ignores that scratch path and REFUSES to run if any does not — so
supervision can never dirty a tracked working tree.

## Notify, never block

A question may only be asked by the actor that OWNS the decision. A
supervised session's decision is already displayed in its own pane, so the
overseer never re-asks it and never blocks on it: every track that needs a
human — a blocked declaration, a structured gate, a non-responder in danger,
a malformed state value — is relayed as NON-BLOCKING text. Because that
relay is the operator's only handover, every track-scoped alert MUST be
self-sufficient: it names the plan topic, the repository, the session and
pane holding it, and a copy-pasteable jump command.

Alerts are edge-triggered — one line when a track enters a condition, not one
per cycle — and the condition is re-derived from live state on every cycle,
so an alert stops on its own once the human acts. Current state is rendered
only by the daemon, rebuilt from live captures on every cycle; it can never
freeze on a stale snapshot.

## Fail-soft posture

The daemon supervises many tracks at once, so no single track's bad state may
take down the loop, and no ambiguous reading may trigger an action:

- A malformed store row or state value is skipped or surfaced BY NAME; the
  remaining tracks are unaffected.
- An unknown context reading keeps the last known value and NEVER counts as
  a threshold crossing.
- A storage error on the overseer's own files is reported and survived,
  never raised out of the supervision loop.
- Busy detection deliberately over-fires: a false "busy" merely suppresses
  action, while a missed "busy" could inject into a working session — so
  ambiguity always resolves toward doing nothing.
- Every authorization check is fail-closed: absent, unreadable, or
  unexpected inputs answer "no".
