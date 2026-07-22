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
- A fresh `winding-down` acknowledgement is honored for fifteen minutes;
  past that it is stale, escalation resumes, and the track is re-reported —
  but staleness never authorizes an act.

## The restart interlock

A restart fires ONLY when every one of these deterministic checks passes:

1. An injection stamp exists for this round — without a recorded wrap-up
   there is no round to declare against.
2. The state file's token is exactly `ready`.
3. The state file's modification time is STRICTLY newer than the round's
   injection stamp — proving the declaration answers this round, not a
   prior one.

Any absent, unreadable, or other-valued file fails the check. Acting on a
passed check is additionally gated on live pane evidence: a verified empty
idle input state, a settled pane (two captures compared across a short
delay), no busy signals, and a positive identity check that the pane really
is this track's supervised session in this track's repository.

The restart itself guarantees:

- The pane's PROCESS is replaced in one atomic operation — never an exit
  followed by a scrape for a shell prompt. Files, worktrees, branches, and
  commits on disk all survive.
- The fresh session is launched autonomously (it does not stall on its first
  permission prompt), named after its plan topic, and handed exactly one
  prompt: read `<repo>/plan/<topic>/handoff.md` and follow it.
- Every step is a hard gate. A failed respawn or a pane that never becomes a
  live supervised session surfaces the failure and PRESERVES the `ready`
  declaration so the next cycle retries.
- A submitted-but-dropped resume is retried by re-sending the SUBMISSION
  only — recorded round-scoped so it cannot outlive its round, branched on
  the observed input-box state rather than on busy-ness, and never escalated
  to a second kill. A fresh session showing a structured gate is reported as
  waiting on a human and never keystroked, with the round held open.
- The restart never changes the track's runtime (per spec.md §"Supervised
  runtimes").

## The wrap-up injection

- Trigger: effective remaining context at or below the track's threshold
  AND a verified idle-input pane. The threshold is the per-track override
  when set, else the daemon-wide default (50% remaining unless overridden at
  daemon launch).
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

## Durable stores

Three operator-home files, plus the per-track state file above. All writes
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
  `resume_pending` flag. Opening a round resets its bands; closing a round
  deletes the key entirely, so no round datum outlives its round. A legacy
  bare-number value is still read as a round timestamp.
- **The watch-set declaration** (`~/.livespec-overseer-repos.json`) — a
  document of the shape `{"repos": ["<checkout-path>", …]}`. It is a
  hand-edited operator file, so it is parsed leniently: comments and
  trailing commas are tolerated. Admission per spec.md §"The watch-set
  declaration". An absent or unparsable declaration degrades to an empty
  watch-set with a warning, never a crash.

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

The daemon owns "what needs attention now". Membership: a blocked track, a
non-responding track at the danger line, a track whose mapped session is
gone, a malformed state value, and a restart whose resume has not yet
submitted. Discovered-but-unassigned plans are deliberately NOT attention —
startable is not stuck. The attention count is also badged onto the daemon's
window name, and the badge MUST clear when the count returns to zero — an
indicator that can only be set is one more stale surface.
