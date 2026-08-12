# livespec-overseer — contracts

The wire-level surfaces of the supervision contract: the state file and its
grammar, the restart interlock, the injection and nudge obligations, the
durable stores, and the daemon's invocation surface. The interactive pane's
operator command vocabulary is deliberately NOT a governed surface, per the
scope statement at the top of spec.md.

## The state file

One file per track: `<repo>/tmp/overseer/<topic>/.overseer-state`, inside the
watched repository's gitignored scratch area. Its FIRST non-empty line is the
declaration, in the grammar `<token>` or `<token>: <detail>`.

| Value | Writer | Meaning |
|---|---|---|
| `winding-down` | session | "I received the wrap-up and am wrapping up now." Written IMMEDIATELY on receipt, before anything else. |
| `ready` | session | "I am at a clean stopping point — restart me." The SOLE restart authorization. |
| `blocked: <one-line reason>` | session | "I need a human decision I cannot make myself." Surfaced with coordinates; never restarted, never keystroked. |
| `idle-with-context-left` | daemon | The daemon's own once-per-episode nudge marker. Authorizes nothing. |
| (per entity) | — | A supervisor pair member keeps its OWN state file at `<repo>/tmp/overseer/<topic>-supervisor/.overseer-state`, with the same grammar, the same writers, and the same rules as a worker's. |

The normal sequence is two writes: `winding-down` the moment the wrap-up
lands, then `ready` (or `blocked: …`) when the session actually stops.

Contract rules:

- Any value outside the table is malformed: surfaced to the operator and
  treated as NO declaration (fail-closed). It is never coerced or
  fuzzy-matched, though it does suppress the keep-going nudge — the safe
  direction for an ambiguous file.
- Beyond the token, the file's contents are never inspected — no handoff
  hash, no payload. What a session hands its successor is its own business.
- The daemon DELETES the file as it restarts the session, together with the
  round's stamp, so a declaration can never re-trigger.
- The daemon's removal of its own nudge marker fires only while the file
  still holds `idle-with-context-left` — it can never clobber a value the
  session wrote in the meantime.
- Stale-declaration voiding: on observing a track busy or gated, a `ready`
  older than a two-minute grace is voided as no longer true. A younger one
  survives, because the declaring turn's own tail legitimately keeps the
  pane busy right after the write. A `blocked:` is voided only when the
  session is observed actively GENERATING (incompatible with waiting for an
  answer) past the same grace — a session merely running a background
  command at its prompt keeps its declaration, however old, and an idle
  blocked session is never touched.
- Voiding clears the DECLARATION ONLY. The daemon MUST delete the state file
  and MUST NOT delete the round's sidecar key, MUST NOT reset its notified
  bands, and MUST NOT otherwise close the round. This binds BOTH voiding
  rules — the `ready` void past the grace and the `blocked:` void on observed
  generating evidence — because both otherwise take the same round-closing
  path.
- The two steps of a `ready` void are ORDERED, because the two orderings fail
  in opposite directions across a crash: the daemon MUST record the void
  instant (per §"The restart interlock") BEFORE deleting the state file. A
  crash between them then leaves a raised floor and a surviving declaration,
  which fails closed; the reverse order leaves a deleted declaration and no
  floor, which is harmless only until the delete itself fails. A failed floor
  record MUST be surfaced to the operator and MUST NOT abort the delete
  attempt.
- Only the `ready` void raises the certification floor. A `blocked:` void MUST
  NOT raise it: a `blocked:` token can never certify a restart under any
  circumstances, so a floor raised on its account would be a durable write
  with no authorization consequence.
- A fresh `winding-down` acknowledgement is honored for fifteen minutes;
  past that it is stale, escalation resumes, and the track is re-reported —
  but staleness never authorizes an act.
- A declaration MUST NOT be honored for an ACT unless its file's
  canonicalized path equals that entity's canonical state path — no symlinked
  parent directories, no symlinked file — compared against an identically
  canonicalized repository root, so a legitimately symlinked checkout still
  passes. An aliased path MUST be surfaced by name and treated as NO
  declaration, so one entity's write can never satisfy another entity's
  authorization.

## The restart interlock

A restart fires ONLY when every one of these deterministic checks passes:

1. A CERTIFICATION FLOOR exists for the track, anchored on a USABLE round
   timestamp. The floor is the round's injection stamp; where a `ready`
   declaration has since been voided, the floor is the LATER of that stamp
   and the instant of the most recent such void. A track with no injection
   stamp MUST fail this check whatever else its record holds — a recorded
   void instant WITHOUT a usable round timestamp, or a stamp or void instant
   present but unreadable or non-numeric, is MALFORMED: it MUST be surfaced
   by name and MUST fail the check, never resolved by falling back to
   whichever value remains usable.
2. The state file's token is exactly `ready`.
3. The state file's modification time is STRICTLY newer than the
   certification floor — proving the declaration answers this round, and
   post-dates any voiding within it, rather than answering a prior round.
4. The session identity live at the pane matches the ROUND-OPEN identity
   recorded for that round. A differing identity MUST hold the restart and
   surface the track rather than failing silently; an identity that cannot be
   determined, and a record carrying no identity at all, MUST both be treated
   as differing — fail-closed, per spec.md §"Fail-soft posture".

Any absent, unreadable, or other-valued file fails the check.

Where both a stamp and a void instant exist, the LATER of the two governs, so
the comparison always fails closed. A recorded void instant MUST be no earlier
than the voided declaration's own modification time plus the voiding grace. The
exclusion of a voided declaration is a property of the RECORDED floor rather
than of wall-clock time, because the naive form is falsifiable: the daemon
computes a declaration's age and records the void instant from separate
readings of a clock that is not guaranteed monotonic, and a backward step
between them could otherwise record a void instant EARLIER than the
modification time of the declaration it voids, which would then satisfy its own
floor.

The guarantee that one declaration MUST NEVER authorize two kills is unchanged,
and two different mechanisms carry it on two different paths. On the VOID path
it rests on a disjunction: a voided declaration is excluded whenever EITHER the
state-file delete or the floor record succeeded. Both are fail-soft storage
operations under spec.md §"Fail-soft posture", so where BOTH fail in the same
observation the declaration survives with an unraised floor; that outcome MUST
be surfaced as an attention condition rather than described as impossible. On
the RESTART path the guarantee is carried by the deletion of the round record,
exactly as before — the floor is CLEARED at restart, not raised, and plays no
part.

A declaration is bound to the SESSION that wrote it, and the anchor for that
binding is the ROUND-OPEN identity. The daemon MUST record the identity of the
session live at the pane WHEN A ROUND IS OPENED, and at no other instant; a
void MUST NOT overwrite, clear, or otherwise rewrite it. That round-open
identity is the identity every certification against that round is tested
against, per precondition 4. Where a void is observed with a live identity
DIFFERING from the round-open identity, the daemon MUST surface the track and
MUST NOT establish a certifiable floor from that void: the session that would
answer it is not the session that was asked. This extends the rule below — "a
declaration authorizes the restart of the session that wrote it, never of
whatever session later occupies that pane" — whose existing test is anchored at
first observation, and which a successor's own first-seen declaration would
otherwise pass trivially. Acting on a
passed check is additionally gated on live pane evidence: a verified empty
idle input state, a settled pane (two captures compared across a short
delay), no busy signals — including no background-shell evidence — and a
positive identity check that the pane really is this track's supervised
session in this track's repository.

The restart itself guarantees:

- The pane's PROCESS is replaced in one atomic operation — never an exit
  followed by a scrape for a shell prompt. Files, worktrees, branches, and
  commits on disk all survive.
- The fresh session is launched autonomously (it does not stall on its first
  permission prompt), named after the ENTITY's derived session name, and
  handed exactly one prompt: read that entity's resume artifact —
  `<repo>/plan/<topic>/handoff.md` for a worker,
  `<repo>/plan/<topic>/supervisor-handoff.md` for a supervisor pair member —
  and follow it.
- Every step is a hard gate, and the two failures are NOT the same. A
  respawn that FAILED — the pane's process was never replaced — surfaces the
  failure and PRESERVES the `ready` declaration so the next cycle retries. A
  respawn that SUCCEEDED but whose fresh session is not recognized in time
  has already destroyed the predecessor, so it CONSUMES the kill
  authorization: the round is held open for submission retry only, and any
  further kill requires a genuinely fresh `ready`. One declaration MUST
  NEVER authorize two kills.
- A restart is additionally held, and the track surfaced instead, when the
  session identity observed at the pane has changed since the `ready` was
  first seen — a declaration authorizes the restart of the session that
  wrote it, never of whatever session later occupies that pane.
- A submitted-but-dropped resume is retried by re-sending the SUBMISSION
  only — recorded round-scoped so it cannot outlive its round, branched on
  the observed input-box state rather than on busy-ness, and never escalated
  to a second kill. A fresh session showing a structured gate is reported as
  waiting on a human and never keystroked, with the round held open.
- The restart never changes the track's runtime (per spec.md §"Supervised
  runtimes").

The interlock and every guarantee above apply per supervised entity, under
that entity's own key.

## The wrap-up injection

- Trigger: effective remaining context at or below the track's threshold AND
  the complete guarded-paste predicate. The threshold is the per-track override
  when set, else the daemon-wide default (50% remaining unless overridden at
  daemon launch). Claude MUST show a positively empty input box; Codex MUST show
  its structural idle-input evidence — a live prompt and statusline with no
  generating marker or picker — because Codex cannot distinguish its empty
  placeholder from typed text. This Codex divergence applies only to the
  low-context wrap-up and MUST NOT weaken the pair nudge's positively-empty
  guard. Both settle captures MUST retain the runtime-appropriate eligible input
  shape and be identical. The pane MUST NOT be generating, changing,
  sub-agent-busy, gated, runtime-reported as waiting on a human, carrying
  `blocked:` or `ready`, or carrying a fresh `winding-down`; a stale
  acknowledgement MAY resume escalation. Shell-only eligibility MUST be
  affirmative — recognized Claude registry `status=shell`, or the Codex
  descendant-shell fallback — and any unknown, conflicting, malformed, or
  unavailable authoritative status suppresses the paste. Immediately before
  paste, the daemon MUST re-read managed-pane identity, authoritative runtime
  busy evidence, declaration, gate, and eligible-input state; any change or
  unreadable input cancels the act for that tick. No-busy and affirmatively
  shell-only-busy panes can satisfy this predicate; any other busy evidence
  cannot. A certifiable `ready` takes only the restart path after its stricter
  no-busy interlock passes; an uncertifiable `ready` remains report-only and is
  not pasted into; a malformed state value remains fail-closed as no declaration.
  The `ready` exclusion applies UNIFORMLY to ANY `ready` token on disk —
  certifiable or not, background-shell evidence present or absent, whichever
  runtime — because the daemon MUST NOT keystroke over a standing declaration.
  That uniform exclusion DEPENDS on the certification floor of §"The restart
  interlock" existing: an implementation MUST NOT tighten this predicate before
  that floor is in place, because doing so removes the only route by which a
  track carrying an uncertifiable declaration currently recovers without a
  person. It leaves a residual that is a REGRESSION against shipped behavior
  for one class of track and MUST be stated rather than discovered — a
  declaration standing on a track that was never in a round, which the floor
  deliberately does not reach, is surfaced rather than healed (per spec.md
  §"Fail-soft posture").
- The injection stamp is written durably BEFORE the message is pasted, so a
  responding declaration always post-dates it.
- Escalation bands: the threshold itself, then each lower ten-percent band
  (40, 30, 20, 10). Each band fires at most once per round; notified bands
  are durable across daemon restarts; several bands crossed at once coalesce
  into one message. At 30% remaining and below the message switches from
  suggestion to insistent demand.
- Message obligations: every wrap-up names the session's live
  remaining-context percentage, the state-file path with the three writable
  values, the handoff path as the sole artifact the successor inherits (with
  the instruction to REWRITE it on drift, never withhold the declaration),
  and states truthfully that only a `ready` declaration restarts the
  session.
- Re-warns stop while a fresh `winding-down` acknowledgement stands.
- The message is delivered as ONE atomic paste followed by a verified
  submission — a payload is never typed key-by-key, and submission is
  confirmed by runtime-appropriate evidence, with a bounded number of
  retries.

## The keep-going nudge

Preconditions, ALL required: the session is cleanly idle; has been
continuously idle for at least one hour; its remaining context is above its
threshold; it is not waiting on a human; and it has made no declaration of
its own. The daemon then pastes one keep-going message and writes its own
`idle-with-context-left` marker so the episode is never re-nudged. The
message points the session back at its handoff, tells it not to stop above
its threshold, and offers the `blocked: <reason>` escape for a session that
is actually waiting on a human. The marker clears when the session works
again; the continuous-idle clock is in-memory, so a daemon restart only ever
delays a nudge.

The nudge MUST describe the blocked declaration generically and truthfully. It
MUST NOT name a runtime, a launch mode, or an approval or sandbox policy as
inherently unable to render a structured question unless that inability is
established by CURRENT runtime evidence. A live structured gate MUST continue to
classify the pane as waiting on a human, suppressing both the nudge and the
wrap-up paste; and the ABSENCE of a gate MUST NOT be read as proof that the
session can obtain human input by some other means. The `blocked:` token, its
surfacing behavior, and its restart prohibition are unchanged by this rule.

## Durable stores

Four operator-home files, plus the per-track state file above. All writes
to the overseer's own stores are atomic (a complete temp file replaces the
old file, so a reader sees the old or the new content, never a partial), and
read-modify-write sequences hold an advisory lock; on a lock or storage
failure the daemon degrades and warns rather than crashing.

- **The mapping store** (`~/.livespec-overseer.jsonl`) — one JSON object per
  line, one row per assigned track. Durable keys: `topic`, `repo`, `tmux`,
  `handoff`, `resume`, `epic`, `pinned_session_id`, plus `ctx_threshold`
  ONLY when a per-track override is set — a row without the key means
  "inherit the daemon default", and readers MUST NOT materialize the default
  at read time. Unknown keys survive rewrites. Malformed lines are skipped
  and named, never fatal. Steady-state cycles that change nothing do not
  rewrite the store.
- **The round sidecar** (`~/.livespec-overseer-stamps.json`) — a JSON object
  keyed per track, each value carrying the round-open timestamp `at` (epoch
  seconds), the notified escalation `bands`, and the round-scoped
  `resume_pending` flag, plus the VOID INSTANT and the ROUND-OPEN SESSION
  IDENTITY backing the certification floor of §"The restart interlock". The
  write discipline for each is part of this contract, because that is where an
  ambiguity would otherwise live: the round-open identity is written ONCE, when
  the round opens, and is never rewritten for the life of that round; the void
  instant MAY be raised repeatedly within the round. Opening a round resets its
  bands; the RESTART deletes the key entirely, so no round datum — floor and
  identity included — outlives its round. Key deletion is tied to the restart
  specifically rather than to any round-ending event: a voided declaration
  leaves the key in place. A legacy
  bare-number value is still read as a round timestamp. A record carrying a
  round timestamp but NO identity — the legacy bare-number value included —
  MUST NOT certify anything: it fails closed rather than being read as matching
  whatever session is live.
- **The watch-set declaration** (`~/.livespec-overseer-repos.json`) — a
  document of the shape `{"repos": ["<checkout-path>", …]}`. It is a
  hand-edited operator file, so it is parsed leniently: comments and
  trailing commas are tolerated. Admission per spec.md §"The watch-set
  declaration". An absent or unparsable declaration degrades to an empty
  watch-set with a warning, never a crash.
- **The status snapshot** (`~/.livespec-overseer-status.json`) — the daemon
  MUST rewrite it atomically on each completed tick. Its governed top-level
  fields are integer `schema_version`, `daemon_instance_id`, monotonically
  increasing per-completed-tick `tick_generation`, and `written_at`; for each
  evaluated track, one row carries `topic`, `repo`, `tmux`, `runtime`,
  `status`, `note`, `ctx`, `progress_now`, `human_wait`, `round_open`, `acked`,
  and `session_identity`, a token derived from the live session join and
  sufficient for a consumer to detect that the session behind a row changed.
  Session-authored free text in `note`, including a blocked reason, MUST be
  elided and length-bounded at serialization; the snapshot MUST NOT become an
  unelided surface for session-authored text. A snapshot write failure MUST
  be contained and edge-reported and MUST NOT terminate or degrade the
  supervision loop. The snapshot is OBSERVATION-ONLY: nothing in it
  authorizes any act, and no daemon behavior may read it back as an input.
  Consumers MUST treat an absent, unreadable, or unknown-or-newer
  `schema_version` snapshot as absent, MUST NOT best-effort-parse it, and MUST
  surface that it could not be read. Staleness is detectable from
  `tick_generation` plus file mtime; a stale snapshot proves only that no
  fresh snapshot exists — it does NOT prove the daemon is down.

## Daemon invocation

`overseerd` runs with NO subcommands and exactly ONE option:
`--warn-percent N`, an integer from 1 to 99 — the daemon-wide default
remaining-context threshold at which the first wrap-up fires (default 50). A
per-track threshold override in the mapping store wins over it. There are
deliberately NO flags for the store, sidecar, or watch-set paths, and no
recovery or interval options: the paths are fixed by construction, and the
daemon is surface-only (per spec.md §"Surface-only startup").

- Standard output is the live state surface, re-rendered from live captures
  on every cycle (roughly every ten seconds).
- Standard error is the timestamped event history. Diagnostic lines are
  prefixed `overseer:`; operator-relevant alerts are prefixed
  `overseer[SURFACE]:`. Track-scoped alerts carry the full coordinates per
  spec.md §"Notify, never block"; daemon-level notices (a failed paste, a
  refused startup) carry none.
- Startup gates, in order: an unsupported host is refused FIRST with the
  failed precondition named (per constraints.md §"Runtime requirements");
  then the daemon refuses if any watched repository fails the gitignore
  precondition (per spec.md §"Non-interference with tracked work"); then it
  refuses if another daemon instance already holds the singleton lock for
  the same mapping store.

## Bootstrap preconditions

The two-pane bootstrap is invoked BY the operator surface from inside the
interactive pane's own session — it is not a standalone launcher and does not
start an agent session itself. It refuses, before mutating any window, when
it is not running inside the operator's agent session or when it is not
inside a tmux pane, naming the missing precondition. It splits ONLY the
invoking window — never targeting another session by name — and it is
idempotent: a daemon pane already present is left in place. It then adopts
already-running sessions whose registered names match active plan topics.

## Attention surface

The daemon owns and renders the MECHANICAL attention surface: the
session-liveness membership enumerated here. This surface MUST remain
authoritative, self-refreshing, and complete on its own terms. A consuming
operator surface MAY compose a superset attention view from the status
snapshot in §"Durable stores". Such a consumer MUST NOT suppress, filter,
re-rank, or replace the daemon's own rendering, and MUST NOT introduce any
surface that requires the daemon's rendering to be ignored. The daemon's
report-only members authorize no act regardless of who consumes them.

A foreman MUST write a heartbeat file at
`<repo>/tmp/overseer/foreman/heartbeat.json` on every completed foreman tick.
The heartbeat MUST carry `written_at`, `pid`, a monotonically increasing
`tick_generation`, and `tick_interval_seconds`, the interval the foreman has
declared for that loop. A present heartbeat is stale when its age exceeds
twice `tick_interval_seconds`, subject to a floor of thirty minutes.

Mechanical attention membership is: a blocked track, a non-responding track
at the danger line, a track whose mapped session is gone, a malformed or
path-aliased state value, a restart whose resume has not yet submitted, a
supervisor pair member that disappeared while its round was open, and the
REPORT-ONLY bounded members of spec.md §"Fail-soft
posture" — a known-low track that has been unable to open a round past its
floor (naming its background-command instance where that is the evidence), a
track busy-shielded past the longer no-progress floor, a low track whose
context knowledge has gone stale, a track carrying a standing declaration
that cannot certify past its bounded floor, and a pair whose autonomous
nudge has already failed. Membership also includes three conditions arising
from the certification floor of §"The restart interlock": a track whose
state-file delete AND floor record BOTH failed in the same observation, which
is the case where surfacing is the ONLY remaining guard against honoring a
voided declaration; a track whose round record is MALFORMED under the
certification-floor rules; and a track whose void was observed under a live
identity DIFFERING from its round-open identity. All three are report-only and
MUST NOT authorize any act, like every other member. A PRESENT-but-STALE foreman heartbeat MUST be
surfaced with coordinates, edge-triggered like every other member. An ABSENT
heartbeat MUST NOT be attention — no foreman adopted means nothing is wrong,
mirroring the unassigned-is-not-attention rule. This member is report-only and
MUST NOT authorize any act. Every member carries the same coordinates and the
same edge-triggering; the report-only members MUST NOT authorize any act. A
supervisor pair member needs no membership entry of its own — as a
supervised entity it enters attention through the same statuses as any
other. Discovered-but-unassigned plans are deliberately NOT attention —
startable is not stuck. The attention count is also badged onto the daemon's
window name, and the badge MUST clear when the count returns to zero — an
indicator that can only be set is one more stale surface.

Membership also includes a successfully restarted fresh session with no
observed context consumption and an exact expected resume payload still in
its composer continuously past the 60-second floor, including the case where
`resume_pending` was not recorded. This is a distinct report-only member with
normal coordinates; it participates in the NEEDS YOU count and window badge,
is edge-triggered, and authorizes no act. Discovered-but-unassigned tracks
remain outside this membership.

## The foreman valve disposition

The disposition selected by spec.md's consensus-decision policy MUST be
declared in the governed repository's livespec configuration, alongside the
other settings that tree already carries, and MUST be readable without invoking
the foreman.

Its value MUST be one of an enumerated set. `report-only` MUST be the safe
default and MUST be the effective value when the key is absent, empty, or of the
wrong type. `consensus` MUST select the consensus disposition ratified in
spec.md.

An unrecognized value MUST NOT be coerced to the nearest match and MUST NOT
silently enable any act; it MUST resolve to the safe default and MUST be
surfaced to the operator. Failing closed on an unknown value is required
precisely because this setting is the one that widens authority.

The effective value MUST be observable — an operator MUST be able to read what
the foreman will actually do without running it.

The setting MUST NOT be settable by the foreman itself. Nothing the foreman
writes MAY change its own disposition.
