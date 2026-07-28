# Control-plane supervision liveness — the general contract

## Purpose and status

This note generalizes the ratified narrow predicate (`shell-prolonged`,
`policy-options.md`) into a control-plane liveness contract covering the four
lanes the widened thread owns: duration as a primitive (A), `blocked:` liveness
(B), the supervisor as a tracked entity (C), and track-level progress (D). It
uses the same discipline as `policy-options.md`: every candidate carries its
rejected alternatives and their failure modes, every time-based mechanism
states its clearing, re-arm, and daemon-restart behavior, and every proposed
operator line is judged against the primary goal in BOTH directions — no
silent stall, and no line a human cannot act on.

Status: **investigation complete; wave-1 adversarial findings verified and
incorporated.** Nothing here is implemented and nothing may be implemented
from this note. It changes governed clauses (§"Governed clauses this
changes"), so it goes through the widened `livespec:propose-change` first;
the narrow instance then implements through `impl:overseer-vyjkzw` and the
widened lanes through sibling work-items under epic `overseer-4xfmez`.

Wave 1 of the §9 gate (five reviews so far — Fable autonomy, Fable
safety, GPT-Codex autonomy, and TWO independent code-truth claim tables,
Fable and GPT-Codex — run from the supervisor seat over the PRE-note
artifacts) produced 40 adversarial findings plus two 13-claim
verification tables that CONVERGED independently on the consequential
items (the mtime inventory hiding the `ready_valid` interlock consumer;
the 32-void recount); their deltas are folded in below. Every finding was verified
against source by this note's author; the per-finding log, including the
findings REFUTED by verification, is at
`tmp/overseer/background-shell-supervision-liveness/reviews/wave1-verification.md`.
The material consequences are folded in below and marked "(wave 1)" or by
finding id where load-bearing: the dead-predecessor voiding candidate is
WITHDRAWN; an above-threshold instance, a cascade amendment for
shell-masked blocked/gate evidence, a ctx-staleness bound, and a
note-priority fix are ADDED; and the mechanism rules (alert identity,
per-condition re-arm, continuity-gap sizing, the codex-arm identity
requirement, the two-known-reads ctx rule, the `-supervisor` namespace
reservation) are new.

Separately, a **maintainer ruling (2026-07-28, binding)** reshaped lanes C
and D after the first revision: supervisor sessions are FULL CITIZENS
(wrap-up, ready-gated restart, same thresholds and naming as workers), and
a both-stalled pair triggers a guarded supervisor NUDGE rather than a
report alone. The lane C and lane D sections are rewritten under that
ruling; the overruled monitor-only stance is preserved in their
rejected-alternatives records, and the ruling's one posture exception is
flagged explicitly in lane D and in the governed-clauses list.

Where this note contradicts the supervisor's first brief or the handoff's §7
design direction, the contradiction is deliberate and collected in
§"Disagreements with prior briefs", each with the measurement that forced it.

## The problem, generalized from two measured incidents

Two incidents, different signals, one shape.

**Incident 1 — the immortal shell** (`root-cause.md`). A dead
`gh pr checks --json` poller kept Claude's registry `status` at `shell` for
~39 hours. `shell` is busy, the busy branch (`_supervisor_evaluate.py:198`)
precedes the threshold branch (`:296`), so no round could open: no stamp, no
wrap-up, no attention, a green `working (background shell)` row through every
escalation band down to 29%.

**Incident 2 — the blocked/generating oscillation** (handoff §6, corrections;
re-verified this session against the acting daemon's log).
`console-happy-path-mvp` cycled between two states for ~54 hours:

- while a `blocked:` declaration stood and the pane was idle, the blocked
  branch (`:241`) preempted the threshold branch — no round;
- while the session generated, the busy branch (`:198`) preempted it — no
  round — and `void_stale_blocked` (one LIVE call site, `:206`; a facade
  wrapper with test-only callers also exists — both claim tables) voided
  the now-stale declaration, **32 times and counting** (first
  2026-07-25T21:28:38Z; the 32nd landed 2026-07-28T03:39:32Z, AFTER the
  handoff was committed — the trap is live, and the handoff's Correction 2
  "voided and not re-declared" is already stale), at declaration ages from
  121 s to 80 728 s (~22.4 h); the session then re-declared and the cycle
  repeated.

Across 32 observed cycles over ~54 hours the track was never in a third
state, so no round could open in either phase; it burned to 22% with no
wrap-up ever sent. Two framing points matter (the second from the
code-truth pass). First, this is NOT the "idle blocked is never voided"
permanence the first brief described — the declaration WAS voided,
repeatedly; the trap is the precedence of TWO branches over the threshold
branch, and it needs no permanence at all, so a fix aimed only at voiding
behavior misses it entirely. Second, "no round can ever open" is
EMPIRICAL about this track's observed pattern, not structural: a
void-then-idle-WITHOUT-redeclare tick would fall through to the threshold
branch (`:296`) and open a round — this session simply always re-declared
before idling, 32 times running. That empirical character is an argument
FOR outcome-keyed detection rather than against it: round-starvation
times the outcome and self-clears the moment a round does open, so it is
correct whether or not any particular cycle happens to break.

**The unifying measurement.** Exactly one signal in the daemon carries a
duration — `InjectState.idle_since` (`_supervisor_records.py:43`), the
keep-going nudge's continuous-idle clock — and no signal carries progress. A
shell 3 seconds old and one 39 hours old are indistinguishable; so are a
`blocked:` 5 minutes old and one 22 hours old; so are a supervisor at 80%
context and one at 2% (the read-only render shows 33 tracks and zero
supervisors, while tmux holds 9–11 `-supervisor` sessions and the Claude
registry holds ~10 live supervisors at 57–80%); and a worker/supervisor pair
waiting on each other looks healthy from both single-session vantages.

**The generalized defect.** The evaluate cascade has absorbing regions —
combinations of states in which no round can ever open — and nothing bounds
how long a track may sit in one while its context runs down. The narrow
predicate closes one such region (the shell). The general contract must close
the CLASS, without adding a bespoke clock and a bespoke alert per signal, and
without adding a single operator line no human can act on.

## What the daemon can already see

Everything below exists today. The lanes add **no new evidence source**; two
of them add a small amount of new MECHANISM over existing evidence, called
out explicitly where it appears.

| Fact | Where it already lives |
|---|---|
| Every declaration's age | `TrackState.mtime` (`signals.py:357`), returned by every `read_state` call; FOUR consumers today (code-truth claim 7 corrected an earlier "exactly two"): the 900 s ACK staleness (`_supervisor_observe.py:243`), the 120 s void grace (`_supervisor_state.py:62,112`), **the restart interlock itself** — `ready_valid` requires `state.mtime > injection_stamp` (`signals.py:423`) — and the stale-ACK age `alert_non_responder` quotes (`_supervisor_nudge.py:146`) |
| A continuous in-memory episode | `InjectState.idle_since` (`_supervisor_records.py:43`), advanced in `observe` (`_supervisor_observe.py:222–226`); the only `_since` FIELD in the code — the claim is field-level deliberately, since doc prose still names the deleted `danger_idle_since` (codex-codetruth E1) |
| Remaining context, sticky across unknown reads | `effective_ctx` (`_supervisor_observe.py:36`), storing `InjectState.last_ctx` |
| Whether a round is open | the injection stamp (`registry.read_injection_stamp`); stamp present ⇔ round open, deleted at round close |
| "generating" as distinct from "busy" | `signals.is_busy(capture) or claude_status == "busy"` — the exact definition `evaluate` already passes to `void_stale_blocked` (`_supervisor_evaluate.py:210`) |
| The supervisor session's existence and liveness | `supervisor_session_of` / `supervisor_running` (`_supervisor_offer.py:35,40`) — derived by the SAME name derivation + containment discipline as the track itself, then reduced to two booleans |
| A live session's process start time | `procStart` in the Claude registry, verified against `/proc/<pid>/stat` (`claude_sessions.py:116,232`) — **in clock ticks since boot, not epoch seconds**; see lane B for what that costs |

## Lane A — duration as a first-class primitive

### The candidate — two mechanisms, honestly split — SELECTED

Duration does not want one clock; it wants one RULE with two carriers,
because the evidence already splits that way:

1. **Declarations: on-disk mtime age.** Any state the session (or daemon)
   declared has an age for free: `now - TrackState.mtime`. Durable across
   daemon restarts, zero new state, already read on every tick. Everything
   lane B needs rides on this.

   **Interlock adjacency, stated because the mtime inventory sits beside
   the restart authorization (claim 7 of BOTH code-truth tables,
   independently converged).** The most consequential existing mtime
   consumer is `ready_valid` itself: `state.mtime > injection_stamp`
   (`signals.py:423`) is the this-round freshness half of the restart
   interlock — and it is not merely code: contracts.md §"The restart
   interlock" states the ordering in governed prose (its item 3). Lane A's age reinterpretation cannot perturb it,
   and the reason is structural, not incidental: every age use in this
   note is READ-ONLY — nothing in lanes A or B writes, refreshes, or
   deletes a declaration on the basis of its age (the one candidate that
   would have, B3, is withdrawn; the only voids remain
   generation-authorized, unchanged) — so the mtime ordering `ready_valid`
   compares is never touched by anything this note adds. Any future lane
   that mutates a declaration file must re-derive this argument before it
   ships. Under the full-citizenship ruling the same statement covers the
   SUPERVISOR's state file verbatim: its `ready` certifies through the
   identical `mtime > stamp` rule under its own key (lane C).
2. **Observed conditions: one in-memory episode clock per condition class.**
   For conditions with no disk footprint (a shell episode, a
   below-threshold spell, an idle spell), `InjectState` carries a
   `(since, last_seen)` pair per condition class, advanced in `observe` under
   one uniform rule:

   ```text
   if condition_now:
       if since is None or (now - last_seen) > CONTINUITY_GAP:
           since = now              # start, or restart after a gap
       last_seen = now
   else:
       since = None; last_seen = None
   ```

   Start on the first true tick; reset on any false tick OR any observation
   gap beyond the continuity window (the early-return paths — `unassigned`,
   `session-gone`, `live-outside-tmux`, the identity-gate rejection — never
   advance a clock, so continuity is measured, not assumed, and no cascade
   edit is needed); daemon restart resets everything in-memory, which only
   ever DELAYS — the same model, and the same justification, spec.md already
   ratifies for the keep-going nudge's idle clock.

   The clock is keyed to the condition CLASS (the evidence), never to the
   rendered status: the status changes at the floor (`working` →
   `shell-prolonged`), so a status-keyed clock would reset itself at the
   moment it fires. "Condition class" means a NAMED boolean predicate each
   instance defines (`shell_episode_now`, `starving_now`, …) — there is no
   generic field-tuple signature machine to drift or to over-reset
   (wave 1).

   **The continuity gap is sized to the worst-case TICK, not the loop
   interval (wave 1).** An `act=True` tick is serial across ~33 tracks and
   its legs block (a restart poll alone is ~15 s; submit and settle delays
   add more), so a 60-second gap can be exceeded by ordinary churn — which
   would reset every episode clock every tick and silently starve every
   floor. The gap for ALL lane-A clocks must exceed the worst-case tick
   duration with margin; recommended **300 s** (flagged as a maintainer
   decision), replacing the narrow predicate's proposed 60 s constant at
   implementation time. A too-large gap only bridges genuinely separate
   episodes into one earlier alarm on a still-true condition — the bounded
   direction — while a too-small gap suppresses detection entirely.

   **mtime residuals, stated (wave 1).** Ages clamp to ≥ 0 (clock skew).
   A session that re-writes its declaration each turn refreshes the mtime;
   that is treated as a FRESH assertion — deliberate, matching the ACK
   staleness semantics — so age-based escalation resets with it. A scratch
   tree restored with preserved ancient mtimes (`cp -p`) produces at most
   one spurious top-band line; accepted and documented.

The ratified shell-episode clock (`shell_since` / `shell_last_seen`,
`policy-options.md` §2) is the first instance of mechanism 2. `idle_since` is
retroactively the zeroth. Lanes B–D name their instances below; no lane may
mint a clock outside this rule.

### Alert identity, quantization, and per-condition re-arm (wave 1)

Two verified mechanism facts constrain every alert this note adds:

- `Supervisor.alert` keys its dedup on `(repo, topic, condition)` but
  compares the FULL LINE TEXT (`_supervisor_core.py:281-284`): an alert
  whose message embeds a free-running value (an age, a live %) re-emits on
  every change of that value — per-hour lines at hour granularity, per-tick
  at finer — reproducing the ~3,000-line log burial invariant 10 exists to
  prevent.
- The re-arm block (`_supervisor_evaluate.py:385-391`) drops a track's
  alert keys only when the WHOLE row is healthy (`not needs_attention`), so
  a track pinned in `NEEDS YOU` by one standing condition silently swallows
  every later episode of any OTHER condition.

The rule, binding on every lane: **an alert's identity is its condition
key; its message quantizes embedded values to deliberate escalation
boundaries** (the value at entry, the crossed band) — free-running values
belong on the re-rendered ROW, which is state, never in the log, which is
history. Deliberate escalations are DISTINCT condition keys (band-suffixed,
e.g. `blocked-age-24h`), so each fires once. And **each condition key
re-arms when ITS condition clears**, not when the whole row goes healthy —
pinned by a test in the owed list.

A corollary, same invariant: **every firing condition carries a ROW
projection** (a status or a `needs_attention`-matched note). A log-only
condition would re-create the frozen-report failure the state/history
split exists to prevent.

### Projection: age on the row is free and ungoverned

Once ages exist, the row note and every alert line should carry them —
`blocked:human (22h)`, `background shell (39h)`. This is pure projection: the
pane table and status vocabulary are deliberately outside the governed
contract (spec.md scope statement), so this costs no spec change, and it is
the cheapest possible §1 win: the operator can finally distinguish a
5-minute wait from a 22-hour one at a glance.

### Rejected alternatives

- **One bespoke clock per signal** (the shape the widened thread exists to
  prevent): each new signal re-litigates start/reset/restart semantics;
  drift between them is guaranteed. Rejected for the single rule above.
- **A clock keyed on the rendered status**: self-resetting at the floor, as
  above. Rejected.
- **Durable episode state** (persisting `since` in the sidecar): the round
  sidecar is round-scoped by construction and these conditions exist
  precisely when no round is open; and durable age can fire IMMEDIATELY
  after a daemon restart on an episode whose continuity the daemon did not
  actually observe — a false alarm in exactly the direction the fail-soft
  posture forbids. Rejected (same grounds as `policy-options.md` §3).
- **Kernel-durable process age** (`/proc` start time of the descendant
  shell): fires on evidence the daemon deliberately demoted for Claude
  (registry `status` superseded the shell walk), and PID-keyed age resets
  every iteration for a respawn-per-poll loop — the exact incident shape.
  Rejected (measured in `policy-options.md`).

## The general attention clause — bounded round-starvation

### What §7 proposed, and where testing it led

The handoff's §7 frames the general attention clause per-signal: "a track
whose observable condition has persisted past a bounded floor without
progress while its remaining context is at or below its wind-down
threshold". Testing that formulation against incident 2 breaks it: the
oscillating track has NO single persistent condition. Each `blocked:` phase
carries a young declaration (re-declared after every void, so
declaration-age escalation never fires), each generating phase is genuine
progress, and no per-signal clock survives the alternation. A per-signal
clause closes incident 1's region and leaves incident 2's open — the exact
"ratify the instance, strand the class" failure the handoff warns about.

What both incidents actually share is not a signal. It is the OUTCOME: the
track sat at or below its wind-down threshold for a long time, and no round
ever opened. That outcome is directly observable from evidence the daemon
already holds — `eff_ctx`, the threshold, and the injection stamp — and it is
evidence-AGNOSTIC: it covers the shell region, the blocked region, the
oscillation between them, and any absorbing region a future signal adds.

### The predicate

One new condition-class clock (lane A mechanism 2): `starved_since`, timing
the condition `eff_ctx is not None and eff_ctx <= threshold and no injection
stamp exists for this track`. Then, per tick:

```text
starving_now = eff_ctx is not None and eff_ctx <= threshold
               and injection_stamp is None

attention    = starving_now
               and (now - starved_since) >= STARVATION_ATTENTION_AFTER
               and not generating          # is_busy(capture) or claude_status == "busy"
```

- **The clock runs through every phase** — generating, blocked, shell,
  gate — because the starvation is true throughout. Only the FIRING is
  gated on a non-generating tick, so a track that is actively producing
  tokens is never alarmed mid-generation (the operator can do nothing with
  a working session — §1's noise direction), while the oscillator alarms in
  its very next blocked or shell phase.
- **An idle non-generating tick below threshold cannot false-fire**: on that
  tick the threshold branch itself opens the round (writes the stamp), which
  makes `starving_now` false. The clause can only fire where a round
  genuinely cannot open — which is precisely the defect.
- `eff_ctx is None` never counts (the existing fail-soft rule verbatim);
  the sticky last-known value participates exactly as it already does in
  the wrap-up branch, bounded by the staleness window below. The `is not
  None` conjunct stays EXPLICIT in every governed restatement — the
  handoff's abbreviation of the ratified predicate dropped it (code-truth
  claim 5), and an implementer following the abbreviation would let a
  never-known track fire.
- Floor: **the same 2-hour floor as the ratified instance**
  (`STARVATION_ATTENTION_AFTER = 7200.0`), for the same reason — long
  genuine work finishes inside it, both incidents ran an order of magnitude
  past it. One value to ratify, not two.

### Relation to the ratified `shell-prolonged` — instance, not sibling

`shell-prolonged` stands exactly as ratified (2 h episode floor, yellow,
`ATTENTION_STATUSES` membership, alert key `prolonged-background-shell`):
it is the instance of this clause where the starving evidence is a
background shell, and its evidence-specific clock lets it name the shell and
its age in the alert — strictly better operator information than the generic
line. The general clause is the safety net UNDER it: when a track qualifies
for both (a long shell straddling the threshold crossing), the specific
instance wins the row status and the alert; the general clause fires only
for starvation the specific instances do not explain. When the general
clause fires, its alert ENUMERATES every piece of currently observed
evidence — the `blocked:` declaration and its void history, a visible
structured gate, the shell — rather than naming a single cause (wave 1: for
the Codex arm, `busy` at `:198` preempts the gate check at `:241`, so a
lingering shell can mask a `› 1.` approval picker; a single-cause alert
would misdiagnose a human wait as a shell problem, and policy-options'
Codex matrix row 6 is wrong in exactly that combination). It also carries
the remaining % and starvation age (quantized per the alert-identity rule)
and the standing truth that the daemon has taken no action and will not
restart without a fresh `ready`.

**A cascade amendment, upgraded from candidate to selected by
codex-autonomy #4 (verified, with the repo's own pinning test).** The busy
branch does not merely delay the blocked/gate surface — it REPLACES it:
`test_blocked_with_only_a_background_shell_is_never_voided` pins that a
standing `blocked:` plus shell-only busy renders plain `working`, and the
shell arm then overwrites the note to `background shell` — so a worker
that declares `blocked:`, leaves a validation build running, and waits,
shows GREEN with no blocked alert at all, for as long as the shell lives.
The amendment: **on a NON-GENERATING tick, a visible structured gate or a
standing `blocked:` declaration takes the blocked branch even when shell
evidence is present** — status `blocked:human`, the reason and the shell
both named in the note, the alert fired. This is exactly as trustworthy as
today's gate branch, which already trusts the same evidence on a not-busy
tick; the risk that had deferred this reordering — gate-like page content
in a GENERATING pane — cannot arise, because generating ticks keep today's
precedence unchanged. The pinned test keeps its load-bearing assertion
(the declaration is NEVER voided by shell-only busy) and updates its
incidental one (the rendered status). Voiding semantics change in neither
direction. And the amendment slots BELOW the cascade's true first leg:
the R1 resume-retry intercept returns before everything else
(`_supervisor_evaluate.py:165-167` — both claim tables flag it as the
branch worth remembering) and is untouched.

**A note-priority defect, existing today (codex-autonomy #5, verified).**
`evaluate` sets the fail-closed `BAD state file` note before the cascade
and the busy branch's shell arm then overwrites it unconditionally
(`_supervisor_evaluate.py:177,215-217`) — so a malformed declaration plus
a background shell alerts once, loses its note to `background shell`, and
drops silently out of `NEEDS YOU`. The malformed-state note must never be
displaced (compose the notes, or rank fail-closed notes above cosmetic
ones); owed test listed.

**Dedupe against instant members (codex-autonomy #12 — half refuted, half
adopted).** Refuted half: a `resume_pending` track cannot round-starve —
its round is OPEN (the stamp exists), so `starving_now` is false by
construction and no duplicate line arises. Adopted half: a track ALREADY
carrying an instant attention status (a surfaced `blocked:human`) that
then crosses the starvation floor gets ONE escalation line naming both
facts ("blocked 26 h AND below its wind-down line — no round possible"),
not a second free-standing line, and the ROW keeps the more specific
status.

**Last-known context must age (codex-autonomy #11, verified).**
`effective_ctx` returns the stale last-known value indefinitely on parse
failure, so a statusline format change would PIN every ctx gate at the
last parsed number — above threshold, every ctx-gated mechanism in this
note silently disarms while the table confidently displays a stale
percentage. Bound it: a last-known value UNSEEN for longer than a bounded
staleness window (recommended 1 h; one lane-A clock) demotes to unknown —
failing toward silence exactly as the ratified rule requires — AND raises
one DAEMON-level notice (`surface`, no track coordinates): "ctx unreadable
for N tracks for over an hour" is a parser/format break, fleet-wide and
operator-actionable, not a per-track condition.

**The general clause is also the backstop for the ratified instance's own
residuals (wave 1, safety #3/#4 — both verified TRUE).** The shell-episode
clock resets on ANY generating tick, so a supervisor that pokes its worker
on a cadence under two hours makes the narrow predicate unreachable forever
— and root-cause.md records the supervisor doing exactly that mid-incident.
Separately, `signals.is_busy` searches the WHOLE ANSI-stripped capture
(`signals.py:152-155`), so page content containing busy markers (this
repo's own source on screen) false-busies a frame and resets the episode.
The starvation clock survives both by construction: it keys on
ctx-below-threshold + no stamp, which persists THROUGH generation and
false-busy frames; those only defer the FIRING to the next clean
non-generating tick. Narrowing `is_busy` itself is REJECTED: over-firing
busy is the ratified safe direction for ACTION suppression, and trading a
missed-busy risk (dangerous) for an attention delay (safe, now bounded by
this clause) is the wrong exchange.

**One implementation obligation on the shell-episode predicate, both arms
(wave 1, safety #5 — verified TRUE as constructed).** To be unambiguous
about tense: today's code does NOT conjoin this — the fallback applies on
any registry miss (`_supervisor_observe.py:185`) — so this is a CHANGE the
implementing slice owes, not a description of current behavior
(codex-codetruth claim 6 concurs). The fallback disjunct must become
`codex_fallback and is_codex`, not bare `codex_fallback`: a Claude
session whose registry entry momentarily vanishes reads `claude_status is
None`, and a streaming Claude renders no busy marker in the captured
region, so any innocent descendant shell (a dev server) would otherwise
accrue a false shell episode on a genuinely WORKING track. `is_codex` is
the live rollout-fd join — a registry-missed Claude fails it, genuine Codex
passes it. The registry-miss fixture joins the owed-tests list.

Recommended row status for the general firing: **`winddown-starved`**
(yellow; `ATTENTION_STATUSES`; alert condition key `winddown-starved`).
Rejected names: `stuck` (asserts a stall the daemon has not proven),
`shielded` (names the mechanism, not the operator-relevant fact),
`no-round` (internal bookkeeping vocabulary). Token choice is flagged as a
maintainer decision, as `shell-prolonged`'s was.

### The above-threshold arm — busy-shielded no-progress (wave 1)

Round-starvation is definitionally below-threshold: above the threshold no
round is owed, so its clock never starts — and a SHIELDED session spends no
tokens, so it never drifts down to the threshold on its own. Both wave-1
lenses found the same hole (autonomy #2, safety #6, verified TRUE): a dead
poller shielding a track at 55% is a full §1 silent stall — busy suppresses
the keep-going nudge as well as the round machinery, so NOTHING ever
surfaces it, indefinitely. The incident was caught only because it happened
to occur at 29%.

The added instance: **a track whose busy classification rests SOLELY on
shell evidence (`claude_status == "shell"`, or `codex_fallback and
is_codex`) and that has shown no `progress_now` (lane D's definition)
continuously past a LONGER floor is surfaced report-only, regardless of
context.** Recommended floor: **8 hours** (flagged as a maintainer
decision). The longer floor is the noise control that replaces the missing
low-context anchor: below threshold the 2-hour line is justified by an OWED
wind-down; above threshold nothing is owed yet, the only claim is "no
observed progress for a working-classified track", and a genuine
uninterrupted 8-hour background build with zero session interaction is rare
enough that one report-only line clears the §1 noise bar. The instance is
deliberately scoped to shell-classified busy: an idle track above threshold
already has the nudge machinery (which forces a turn or a `blocked:`), and
a generating or sub-agent-running track is progressing by definition.

Clearing and re-arm follow the standard rules (any progress tick or the
shell ending clears; key-drop re-arms; restart delays). Recommended row
status: **`shell-prolonged`** with the age in the note — it is the same
operator situation as the ratified instance, just above the line — so no
third token is minted; whether to reuse the token or mint one is left with
the maintainer alongside the floor.

Rejected for this arm: extending the keep-going NUDGE to shell-status
sessions in general (a paste+submit into a session whose busy
classification the daemon trusts for suppression — an act on ambiguous
evidence, the exact direction the fail-soft posture forbids; note the ONE
ruled exception to this rejection: the supervisor pair nudge, lane D,
which the maintainer has mandated under strictly narrower guards — that
exception is scoped to the pair member and does not reopen this arm); and
dropping the ctx conjunct from round-starvation instead (incoherent — no
stamp above threshold is the normal state of every healthy track, so the
predicate would be vacuously true fleet-wide).

### The five forbidden acts

Identical to the ratified instance, and load-bearing for every lane in this
note: no paste, no Enter, no respawn, no kill, no declaration write. The
clause sets a row status, a row note, and calls `sup.alert`. A starved track
whose preempting evidence is a `blocked:` declaration keeps that declaration
untouched — surfacing does not void (see lane B).

### Rejected alternatives

- **Per-signal persistence clauses only** (§7's formulation): leaves the
  oscillation region open, as measured above. Rejected as the GENERAL
  clause; retained as instances where signal-specific evidence improves the
  alert.
- **A void-cycle counter** (alert after N `void_stale_blocked` firings):
  considered for incident 2 specifically; dropped because round-starvation
  surfaces the same trap on stable evidence with no new counter, and the
  void history already exists in the daemon log for the alert to cite.
- **Opening a round despite the preempting branch** (inject the wrap-up into
  a blocked or shell-busy track at threshold): a keystroke into a session
  that may be waiting on a human or running real work. Forbidden by the
  same rule that created the precedence. Rejected without qualification.

## Lane B — `blocked:` liveness

Lane B decomposes into two shipped behaviors and one withdrawn candidate.
Nothing in this lane voids an idle declaration on a timer — see the first
disagreement in §"Disagreements" for why that route is rejected outright.
Note also what lane B does NOT need to solve: a legitimately blocked track
that sinks below its threshold (never warned, because the blocked branch
preempts the threshold branch) is exactly a round-starved track — the
general clause surfaces it at the floor, naming the blocked declaration and
its age, so the human it is waiting on learns the wait has become
context-critical (wave-1 autonomy #6b, closed by convergence).

### B1 — age on every blocked surface (projection only)

`blocked:human` rows and alerts carry the declaration age from
`TrackState.mtime`: `blocked on human (26h): <reason>`. No clock, no policy
change, no governed-clause change. This is the minimum §1 repair for the
pure long-wait case: the row already sits in `NEEDS YOU`; what the operator
cannot currently see is for HOW LONG.

### B2 — escalation by age band (re-arm, not re-void)

The current alert is edge-triggered per episode: a track blocked for 22
hours emits ONE line at hour zero and the history is silent thereafter
(the live table keeps showing the row — state — but the log — history —
never speaks again, and the operator was told once). Escalate the way the
wrap-up already escalates: on the declaration age crossing each member of a
small band set — recommended **{4 h, 24 h}, then every 24 h** — the alert
re-arms and fires once more, carrying the age. Band bookkeeping is keyed to
the declaration identity (its mtime), so a RE-declaration — a new answer, a
new reason — resets the bands naturally, and the oscillation's young
declarations correctly never escalate (round-starvation owns that trap).

Bookkeeping is in-memory. A daemon restart therefore re-fires at most the
highest crossed band once — a TRUE statement re-stated once after a restart,
not a false alarm; accepted, and documented, rather than persisting
per-declaration alert state into a sidecar that is round-scoped by
construction.

This amends the edge-trigger clause (spec.md §"Notify, never block":
"one line when a track enters a condition") into "one line on entry, plus at
most one per crossed age band for a standing human-wait" — a governed
change, named in §"Governed clauses this changes".

### B3 — dead-predecessor voiding: WITHDRAWN (wave 1)

An earlier draft of this note carried §7's route (ii) — void an idle
`blocked:` on proof its mtime predates the live session's process start —
hardened with a unit conversion, a margin, and a fail-toward-keeping rule.
It is withdrawn entirely, because verification showed the PREMISE is
unsound in both directions, and no margin repairs a wrong premise:

- **False void (safety #1, BLOCKER, verified).** The documented tmux-crash
  recovery (`overseer/AGENTS.md` runbook) restores a blocked session via
  `claude --resume`: a NEW process — fresh `procStart` — continuing the
  SAME conversation, whose pre-crash `blocked: waiting on maintainer` is
  still semantically true (the runbook itself orders such panes left
  alone). mtime < start would void a LIVE declaration. That declaration is
  the only suppressor of real act paths: the threshold branch
  (`_supervisor_evaluate.py:296`) carries NO waiting-on-human check (that
  guard exists only in the idle branch, `:340`), so a voided track at/below
  threshold gets the wrap-up pasted and submitted into a session waiting on
  a human; above threshold, a Codex YOLO session (no registry `waiting` to
  suppress it) becomes nudge-eligible. A pure time comparison would
  authorize a paste and an Enter — the plan's own §12 red line.
- **Missed catch (this verification's own finding).** The `/clear` case
  that MOTIVATED the candidate keeps the same process: `/clear` starts a
  new conversation in the same pid, so `procStart` is unchanged and the
  proof never fires on it. Wrong on the false-void side AND blind to its
  own motivating case.

What remains for the inherited-false-`blocked:` gap: the existing
generation-triggered void (ratified, unchanged — observed token production
is the authorizer, the age grace only bounds it in the keep direction), and
lanes B1/B2 — a falsely-blocked row now carries a visible, escalating age,
so the operator can retire it by hand with one glance instead of
discovering it by archaeology. A too-loud surface, made legible, is the
correct steady state here; a timer that can silence a true human wait is
not.

### Rejected alternatives

- **Void an idle `blocked:` on declaration age** (the first brief's
  prescription): the daemon overruling a session's own semantic assertion
  on a timer — the exact reasoning the cardinal rule forbids on the restart
  path, and operationally unsafe: the voided track falls through to the
  idle branches, where the keep-going nudge or the wrap-up would keystroke
  into a session that told us it is waiting for a human. Rejected without a
  fallback.
- **Void on IDLE ticks** (same brief, narrower): identical failure — idle is
  the NORMAL state of a blocked session.
- **Escalate by re-alerting every tick past a floor**: re-introduces the
  buried-history failure (invariant 10's ~3 000 identical lines). Rejected;
  bands are the already-ratified escalation shape.
- **Persist band bookkeeping durably**: the sidecar is round-scoped by
  construction; a new durable store for alert cosmetics fails the
  cost/benefit test its one-duplicate-line-per-restart residual sets.
  Rejected, residual accepted and documented.

## Lane C — the supervisor as a tracked entity

### The measured hole

`supervisor.py list` renders 33 tracks and zero supervisors while tmux holds
9–11 `<topic>-supervisor` sessions and the registry holds ~10 live
supervisors at 57–80% context, one of them `status: shell`.
`surface_supervision_offer` (`_supervisor_offer.py:77`) reduces a supervisor
to two booleans — handoff exists, session running — and returns. No context
monitoring, no duration, no attention, no state file, for any supervisor in
the fleet. A supervisor that burns to 0% dies mid-thought, silently, taking
its live brief with it; the offer surface reports nothing because the
session is still "running" right up until it is not.

Discovery cannot see supervisors because discovery keys on plan
directories, and a supervisor has no `plan/<topic>/` of its own — by design,
and that design is correct (see rejected alternatives).

### The design — the pair member is a FULL CITIZEN (maintainer ruling, 2026-07-28)

An earlier revision of this note selected monitor-and-surface only,
recording full citizenship as a growth path deliberately not taken. **The
maintainer has OVERRULED that deferral — full citizenship ships in this
contract**, with three binding decisions: (1) restart of low-context
supervisor sessions is IN scope; (2) thresholds, escalation bands, session
naming, and restart machinery are EXACTLY the worker's — the ready
interlock included, so the cardinal rule is unchanged and applies per
entity; (3) a supervisor NUDGE exists for the both-stalled case (lane D).
This section is the design worked out under that ruling; its feasibility
was verified against the code, and its one genuine posture conflict is
flagged in lane D rather than silently absorbed.

**The shape: the pair member is a track-shaped supervised entity keyed
`<topic>-supervisor`.** Derived, never discovered from a plan directory:
the `<derived-session>-supervisor` tmux session (`supervisor_session_of`
composes the collision-aware derivation; `supervisor_running` proves pane
process + repo containment). From there, every mechanism in the existing
contract and in this note applies to it IDENTICALLY, by construction
rather than by parallel implementation:

- **State file**: `<repo>/tmp/overseer/<topic>-supervisor/.overseer-state`
  — its own directory under the same gitignored scratch root, so the
  one-file-one-value rule (invariant 9) holds per entity with no collision
  against the worker's file. The round sidecar keys on
  `(repo, <topic>-supervisor)` identically. The namespace reservation
  below is what makes this key sound: no real plan topic may ever claim
  it.
- **Wrap-up**: same trigger (threshold), same bands, same
  idle-verified/settled/identity gates, same escalating message — with
  `{state_file}` substituted to the supervisor's own file and `{handoff}`
  to `plan/<topic>/supervisor-handoff.md`, the one artifact spec already
  reserves for supervision and the daemon already existence-probes. The
  wrap-up body already teaches committing the handoff through the repo's
  PR discipline, which is exactly how spec requires that artifact to land
  — one substitution, no new prose obligations.
- **Restart**: the identical interlock — a supervisor-round stamp, the
  supervisor's own fresh `ready`, strict mtime ordering (LITERALLY the
  same `ready_valid` — `state.mtime > injection_stamp`, `signals.py:423` —
  evaluated under the `(repo, <topic>-supervisor)` key, per lane A's
  interlock-adjacency statement), idle/settled/identity gates — then the
  same atomic respawn PRESERVING the session name:
  `claude --dangerously-skip-permissions -n <topic>-supervisor`,
  resume line `read <repo>/plan/<topic>/supervisor-handoff.md and follow
  it`. Runtime dispatch applies unchanged should a Codex supervisor exist.
  One admission guard: the RESPAWN (not the wrap-up) additionally requires
  the existence probe to pass — respawning onto a missing handoff artifact
  would hand the fresh session a dead pointer, so a `ready` with no
  artifact surfaces the existing capture-offer and holds the round open,
  exactly as a failed respawn preserves a worker's declaration.
- **Threshold resolution**: the daemon-wide default (the ruling's "wrap-up
  starting at 50%"); a supervisor has no mapping-store row to carry an
  override. Whether the WORKER's per-track override should propagate to
  its supervisor is a small open decision; the recommended answer is no
  (an override is track-scoped tuning).
- **The general clauses of this note apply to it automatically.** A
  supervisor on a dead Monitor shell below threshold round-starves and
  surfaces; above threshold the busy-shielded no-progress arm covers it;
  its `blocked:` carries an age and bands. Full citizenship means no
  bespoke supervisor machinery anywhere — which is also the strongest
  available safety argument: every act path onto a supervisor is an
  already-tested worker path under a different key, not new code.

**What this dissolves, and what stands, from the wave-1 lane C findings —
re-checked individually, not dropped wholesale.** Autonomy #5 dissolves:
the supervisor now has the declaration grammar, the wind-down lever, and
the recovery transition it lacked, and the chronic-noise concern dissolves
because supervisor rows use the SAME status vocabulary and attention
membership as workers (`warned` is a working state with a round open, not
an operator page; the measured 57–80% fleet produces zero attention rows).
Codex-autonomy #9 ("supervisor at 2% holding the only live brief; human
cannot safely act") dissolves with it. The former open decision on a 20%
attention floor DISSOLVES — same-as-worker replaces it. What STANDS:
the `-supervisor` namespace reservation (safety #8 — now doubly
load-bearing, because the scratch directory and sidecar key depend on it
too) and the outside-the-cascade pair pass (autonomy #11 — the supervisor
entity's own evaluation runs per tick regardless of the WORKER's branch,
and the legacy `SUPERVISION_CONDITIONS` offers fold into that pass).

**Position in the tick, and reconciliation with the existing offers
(wave 1, autonomy #11 — verified).** Today's only supervisor surface,
`surface_supervision_offer`, is called from the idle-above-threshold
else-leaf of the cascade (`_supervisor_evaluate.py:326`) — so a track that
is busy, blocked, warned, or in danger NEVER surfaces its supervision
state: a fifth uninventoried instance of "condition suppressed by cascade
position", found by review of this very plan. Lane C's pair monitoring must
therefore run OUTSIDE the worker's decision cascade — per tick, for every
track with a live pair member, regardless of the worker's state — and the
existing `SUPERVISION_CONDITIONS` offers must be folded into (or explicitly
sequenced with) that per-tick pass, so the two surfaces cannot disagree
about the same supervisor.

**The `-supervisor` namespace is RESERVED (wave 1, safety #8 — verified as
a latent act path in the CURRENT code).** Nothing today forbids a plan
directory named `plan/<x>-supervisor/`; discovery would mint it as a track
whose derived session name collides with track `<x>`'s supervisor session,
and adoption (registry name match + cwd containment) would then bind the
SUPERVISOR as that track's worker — handing it the full cascade, wrap-up
paste through `ready`-triggered `respawn-pane -k`, today, before lane C
adds anything. Discovery MUST refuse a plan directory whose name ends in
`-supervisor` (skipped and surfaced by name, fail-soft, like every other
malformed input), which closes the collision for the existing machinery
and makes the pair derivation sound in both directions. This is a
discovery-admission rule, so it joins the governed-clauses list.

**Charter obligation (sequencing note, not a gate).** The generated
supervisor charter must now TEACH the state-file protocol — a supervisor
that receives a wrap-up must know what `winding-down` / `ready` /
`blocked:` mean and where its own state file lives. That edit touches the
same generated-charter file `plan/supervisor-scratch-discipline/`
(`overseer-5jttov`) is editing; sequence the edits, exactly as the
handoff's §8 resolves the adjacency.

### Rejected alternatives

- **Monitor-and-surface only** (this note's own earlier selection):
  OVERRULED by the maintainer, and the wave-1 record shows why the
  overruling is right — monitor-only made supervisor failure
  spectate-able rather than fixed (autonomy #5), left a 2%-context
  supervisor with no safe recovery transition (codex-autonomy #9), and
  bought its safety by withholding the exact machinery that is already
  tested on workers. Rejected, superseded by full citizenship.
- **Give supervisors plan directories** so discovery sees them: pollutes the
  plan namespace with non-plans, doubles the track list, invites
  supervisor-of-supervisor regress, and breaks the archived/unarchived
  lifecycle semantics for a thing that is not a plan thread. Rejected.
- **Register supervisors as mapping-store rows**: the store persists ONLY
  facts not re-derivable from the filesystem (invariant 4), and the pair
  member is fully derivable (derivation + containment). A stored row is a
  hand-maintained list waiting to go stale. Rejected.
- **A second daemon (supervisor-of-supervisors)**: the daemon is already
  the terminal watcher; supervising the pair member from the existing loop
  costs one more evaluated entity per track per tick. Rejected as structure
  for structure's sake.
- **Status quo** (the two booleans): measured above; fails §1's stall
  direction for every supervisor in the fleet. Rejected.

**Accepted residual (wave 1, autonomy #12).** Pair discovery keys on the
WORKER's plan directory, so a supervisor whose plan is archived — or whose
worker was never assigned — stays undiscoverable; the census drift lives at
exactly those orphan edges (11 tmux `-supervisor` sessions vs 10 registry
entries at handoff time; 9 tmux at this note's first draft; 8 registry
supervisors of 26 live sessions, two at `status: shell`, at the code-truth
pass — the numbers churn, the structural point never moves). Orphan
supervisors are operator hygiene, not supervision of an active track;
recorded rather than engineered around.

## Lane D — track-level progress

### Testing §7's candidate broke it

§7 proposes: a session classified busy whose `eff_ctx` has not moved across
a bounded window is "not spending tokens, therefore not working". Two
measured facts refute the inference for Claude:

- A parent session running an in-process sub-agent reports registry `busy`
  while its OWN context is frozen — for hours, legitimately (the
  supervisors in this very fleet do it daily). Frozen ctx + busy ⇒ working,
  not stalled.
- A long foreground tool call (a build under a plain `Bash` call) holds
  `busy` with zero token spend until it returns.

And the quantization is coarse: `eff_ctx` is an integer percent of a large
window, so a genuinely thinking session can legitimately hold one value for
many minutes. A per-session "frozen ctx = stalled" detector therefore
false-fires on exactly the sessions doing the heaviest legitimate work —
§1's noise failure — and is **rejected as a detector**.

What survives is the inverse use: **ctx MOVEMENT is reliable evidence OF
progress** (tokens were spent; nobody spends tokens by accident), and it is
runtime-agnostic. So progress is defined as a disjunction that fails toward
"working":

```text
progress_now = signals.is_busy(capture)        # generation spinner, either runtime
               or claude_status == "busy"      # generating or sub-agent
               or eff_ctx changed since the previous known reading
```

`claude_status == "shell"` is deliberately NOT progress — a shell is
precisely the signal incident 1 proved can be dead — and idle / waiting /
gate are not progress. **The state this needs, named exactly (codex-
codetruth E3 refutes §7's "`last_ctx` is already the storage"):**
`last_ctx` holds one integer overwritten on every known read — a
comparison BASELINE and nothing more; the window additionally needs a
`last_ctx_changed_at` stamp (one lane-A field) recording when a known
read last DIFFERED from the baseline. And the claim the window supports
is deliberately one-directional: ctx MOVEMENT proves spend; an UNCHANGED
integer percentage never proves zero spend (quantization) — which is
exactly why movement appears only as positive progress evidence in
`progress_now` and no detector in this note fires on "ctx unchanged"
alone.

Two wave-1 refinements to the ctx-movement disjunct:

- **Movement counts only between two KNOWN reads.** `effective_ctx` keeps
  the last known value across unknown parses, so a naive comparison would
  read "unchanged" during any stretch where the statusline is unparseable —
  measuring parse availability, not progress. An unknown-parse tick yields
  no movement evidence in either direction.
- **Compaction counts as progress and that is accepted.** Autocompaction
  RAISES remaining % without work; it reads as movement and resets the
  no-progress clocks — a delay in the safe direction, at most once per
  compaction, not a false alarm.

One wave-1 claim against this lane is REFUTED and recorded (safety #7,
last sentence): "the M3 pair itself would have false-alarmed as a mutual
wait at the measured instant". False against this note's definition — M3's
worker was mid-dry-run, i.e. registry `busy`, which `progress_now` counts
as progress, so pair-stalled cannot fire there. The claim is true only of
§7's frozen-ctx formulation, which this note had already rejected on
exactly those grounds.

### The design — pair-stalled feeds the supervisor NUDGE (maintainer ruling 3)

With lane C in place, the mutual wait becomes expressible from outside both
sessions: **a pair is stalled when BOTH members have shown no
`progress_now` and NEITHER is in a human-waiting state (a structured gate,
registry `waiting`, or a standing `blocked:` — those have their own
surfaces) for a continuous 2-hour floor** (one lane-A clock on the pair
condition).

An earlier revision made this detector report-only and gated its arming on
a post-lane-C measurement period. **The maintainer's ruling 3 replaces
both**: when the pair is stalled and the supervisor is NOT presenting a
human-blocked question — its own or proxied from the worker — the
supervisor SHOULD be NUDGED to un-stall itself and its worker. A presented
question is a legitimate human gate: no nudge, surface it instead. So the
detector ships WITH lane C, and its firing is an escalation ladder, act
first, operator second:

1. **Human gate present** (either member shows a gate; the supervisor is
   `waiting` or has a standing `blocked:`): NO nudge. The existing
   `blocked:human` surface carries it, and the pair context rides that
   alert's note ("worker also stalled 3h") so the operator sees the wait
   is mutual.
2. **No human gate**: paste ONE nudge into the SUPERVISOR (it owns
   direction), once per stall episode, under the full act discipline the
   existing keep-going nudge already uses — verified empty idle input,
   settled pane, identity gate, never at a gate. The message names the
   worker's coordinates, the no-progress duration, and the two honest
   outs: resume driving, or surface/declare the human question you are
   actually waiting on (`blocked: <reason>` — which converts the pair into
   case 1 on the next tick).
3. **Still stalled one floor after the nudge** (no progress from either
   member): the report-only pair-stalled operator line, naming both panes
   and the fact that an autonomous nudge already failed — which is
   precisely what makes the line actionable rather than noise: the
   autonomous remedy is exhausted, a human is genuinely owed.

**The one posture conflict, flagged loudly rather than silently absorbed.**
The M3 stall shape has the supervisor at registry `shell` (an armed
Monitor is a background shell). A nudge into that pane is an act on a
session the daemon CLASSIFIES busy — the exact thing busy-suppression
exists to prevent, and this note's above-threshold arm rejected for the
general keep-going nudge. The resolution is that this is a RULED,
narrowly-guarded exception, and the guards make it mechanically safe: the
paste happens only at a VERIFIED EMPTY, SETTLED input prompt (a
shell-status session sits at its prompt — that is what `shell` means; the
pane accepts input while the background command runs), only when the
session is provably not generating (generation is progress, so a
generating pair is never stalled), only after 2 h of measured pair-wide
no-progress, and never over a gate / `waiting` / `blocked:`. What the
guard set cannot rule out is nudging a supervisor whose Monitor was a
DELIBERATE, correct wait — the cost there is one wasted supervisor turn
per episode (the supervisor re-evaluates and re-arms), which is also the
answer to wave-1 codex-autonomy #7: the false-positive cost of this
detector lands on an agent turn, not on the operator. The widened
proposal MUST state this exception explicitly in governed prose — it
bounds the fail-soft busy-suppression clause in the act direction for
exactly this one path, and hiding it in implementation would be a silent
contract lapse.

Interactions that keep it quiet on healthy tracks, walked explicitly:

- A worker idling above threshold gets the keep-going nudge at 1 h; its
  answering turn is progress and resets the pair clock. A pair that
  RE-stalls after the nudge — the worker replied "waiting on my
  supervisor" and idled again, the supervisor's armed monitor never fires —
  is exactly the M3 shape, and it reaches the 2-hour floor with no further
  interruption because the nudge is once-per-episode. The detector fires
  there, and there is genuinely nothing else that would.
- A worker below threshold is inside the wrap-up escalation; its responses
  are progress ticks. The pair detector stays quiet where the round
  machinery is already driving.
- A supervisor running its reviewers is registry `busy` ⇒ progress ⇒ no
  fire, however long the review runs.

**Edge-triggering the nudge.** Once per stall episode. The recommended
carrier is the supervisor's own state file with a daemon-written marker —
the mechanism the keep-going nudge already ratifies — but the existing
token's name (`idle-with-context-left`) states the wrong fact for a pair
nudge, so the state-file grammar gains ONE new daemon-written value
(recommended `pair-stall-nudged`; authorizes nothing; cleared by the
daemon the moment either member progresses, with the same
never-clobber-a-session-value rule). A governed grammar extension —
listed under governed clauses. The in-memory alternative (no new token)
re-nudges once after a daemon restart; flagged as the fallback if the
maintainer prefers no grammar growth.

Also refuted for the record (codex-autonomy #6): "lane D's busy-based
predicate misses the mutual IDLE wait — both idle, neither blocked."
That is true of §7's formulation and FALSE here: `progress_now` does not
require busy classification, so two idle members are exactly the
detector's core positive case — and under ruling 3 that case now gets the
nudge, not just a line.

### Rejected alternatives

- **Reading `plan/` or git history for progress**: violates
  non-interference outright (invariant 1). Rejected.
- **Reading the ledger**: couples the daemon to one orchestrator; the
  daemon must stay orchestrator-agnostic. Rejected.
- **Pane-text diffing over long windows**: exists at 0.6 s as
  `pane_settled` for a different purpose; over minutes-to-hours pane text
  churns for cosmetic reasons (clocks, spinners, statusline), so it
  over-reports progress in exactly the case under test. Rejected.
- **Per-session frozen-ctx detector** (§7's formulation): refuted above.
  Rejected.

## Clearing, re-arm, and daemon-restart — every time-based mechanism

| Mechanism | Carrier | Starts | Resets/clears | Re-arms | Daemon restart |
|---|---|---|---|---|---|
| Shell episode (ratified) | in-memory clock | first `shell_episode_now` tick | evidence-false tick, or observation gap > the continuity gap (recommended 300 s, sized to worst-case tick — wave 1) | per-condition key drop when ITS condition clears | clock resets; delay-only |
| Round-starvation | in-memory clock | first tick below threshold with no stamp | ctx recovers above threshold; a round opens (stamp written); observation gap | same per-condition rule | clock resets; delay-only |
| Above-threshold no-progress (wave 1) | in-memory clock | first shell-classified no-progress tick | any progress tick; shell evidence ends; gap | same per-condition rule | clock resets; delay-only |
| Blocked age + bands | on-disk mtime (no clock) | declaration write | new declaration (new mtime) resets bands; declaration cleared/voided ends episode | next declaration is a fresh episode; band keys are distinct conditions | age survives (mtime); band memory in-memory → at most one true re-statement |
| Supervisor entity rounds (lane C, ruled) | the EXISTING durable round machinery, keyed `(repo, <topic>-supervisor)` | threshold crossing opens a round | round close on restart, exactly as a worker's | per the existing round contract | stamp + bands durable, exactly as a worker's |
| Pair-stalled → nudge → line (ruled) | in-memory clock + a daemon-written once-per-episode marker in the supervisor's state file | first no-progress-both tick | any member progresses; any human-waiting state (→ surface instead); gap | marker cleared on progress re-arms the next episode; the operator line re-arms per condition key | clock resets; at most one repeat nudge per restart if the in-memory fallback is chosen; delay-only otherwise |
| Ctx staleness bound (codex-autonomy #11) | in-memory clock per track | first unknown-parse tick after a known value | any successful parse | daemon-level notice, not a track alert | clock resets; delay-only |

Every alert above is coordinate-rich (via `sup.alert` — topic, repo,
session, pane, jump command) and edge-triggered under the alert-identity
rule (lane A): identity = condition key, embedded values quantized to
escalation boundaries, per-condition re-arm rather than whole-row re-arm.
None of the new condition keys joins `SUPERVISION_CONDITIONS` (the re-arm
exemption set). Every in-memory clock fails in the delay direction on
restart, never the false-alarm direction. (The dead-predecessor void row
that stood here is withdrawn — lane B3.)

## Two cross-cutting boundaries, stated so they stop being ambient (wave 1)

**The daemon's own liveness is a NAMED residual, not a covered lane —
and wave 1 added CODE evidence that sharpens it (codex-autonomy #1,
verified).** `run_loop` deliberately does NOT catch a raising tick: its
docstring says the exception propagates "and the process supervisor
restarts it" (`_supervisor_lifecycle.py:120-127`) — but no process
supervisor exists: `overseerd` is launched bare into a tmux pane
(`start.py`, `daemon_command`), with no service unit and no restart
wrapper, so the code's own stated assumption is false in the shipped
deployment and one unhandled tick bug ends all supervision at once. The
design intent is sound (a bug must not be swallowed into a loop that
re-enters it) and the boundarying of expected per-track failures is real —
but the recovery half of that design is an assumption, not a mechanism.
Every clock in this note is additionally in-memory, so a daemon restarted
more often than a floor never fires that floor — and sub-2-hour daemon
restarts are NORMAL during active development (`AGENTS.md` prescribes
restarting the daemon after every landed overseer change). The mitigations
that exist are real but passive: a crashed daemon leaves its traceback in
the top pane, the table render is timestamped every tick (a dead or
frozen daemon is visible as a stale stamp in the top pane), and every
restart failure is in the delay direction, never a false alarm. What does
NOT exist is any observer of daemon restart CADENCE — policy-options'
accepted residual ("a daemon restarting every two hours is itself an
operator-visible anomaly") names an anomaly nothing is watching for.
Closing that — daemon self-liveness, and likewise the interactive bottom
pane's own context exhaustion — is a different supervisor (of a different
thing) and is explicitly OUT of this thread's four lanes; it is flagged as
an open maintainer decision whether to file it as its own thread, so the
residual is a recorded choice rather than an oversight.

**Who may ever raise `AskUserQuestion`.** §1 requires a legitimate blocking
human decision to be presented as an `AskUserQuestion`, and invariant 8
forbids the overseer to block on a question it does not own. These
reconcile cleanly and this note depends on the reconciliation: the DAEMON
owns no decisions, so every condition in this note is non-blocking
coordinate-rich text, exactly as invariant 8 requires; a blocking question
is raised only by the ATTENDED seat that owns the decision — the supervisor
seat for supervisor-owned calls, the interactive bottom pane for
overseer-owned ones (add/remove/start/threshold), and the tracked session
itself for its own work. Nothing in lanes A–D creates a decision the daemon
owns, so nothing in this note ever converts an alert into a prompt.

## Disagreements with prior briefs — deliberate, with the forcing measurement

1. **Brief 1's "void a stale `blocked:` on idle ticks" is rejected**
   (agreeing with handoff §7): an idle blocked session is the normal case
   of waiting on a human; a timer that discards the declaration both
   overrules a session-owned semantic assertion and drops the track into
   the idle cascade where the nudge/wrap-up machinery could keystroke into
   it. Escalate-by-age (B2) and the dead-predecessor proof (B3) replace it.
2. **Brief 1's "permanent by construction" mechanism for incident 2 is
   wrong in the direction that matters**: the log shows 32 voids — the
   declaration is repeatedly retired and re-made, and the trap is branch
   precedence, not permanence. This is why lane B alone cannot close
   incident 2 and the round-starvation clause exists.
3. **Handoff §7's per-signal general clause is replaced** by the
   evidence-agnostic round-starvation clause: the oscillation has no
   persistent per-signal condition to time (measurement in §"The general
   attention clause"). §7's instinct that the attention surface changes
   SHAPE — a general clause, not a sixth enumerated member — is confirmed.
4. **Handoff §7's lane D detector ("busy + frozen ctx ⇒ not working") is
   refuted** for Claude sub-agent turns and long foreground tool calls;
   ctx movement is kept as positive evidence of progress only, and the
   pair-level detector replaces the per-session one. §7's
   "`InjectState.last_ctx` is already the storage" holds for the value but
   not the change-time, which must be added.
5. **Handoff §7's lane B route (ii) understates its own mechanism, and is
   now withdrawn outright**: `procStart` is clock ticks since boot compared
   as a string (`claude_sessions.py:232`), not an epoch time comparable to
   a file mtime — and wave-1 verification then showed the premise itself
   unsound in both directions (`--resume` recovery false-voids a live
   declaration; `/clear` keeps the pid and is never caught). See lane B3.

## Governed clauses this changes

Route through the WIDENED `livespec:propose-change` before any product code
— one ratification cycle for the whole contract:

- **spec.md §"Fail-soft posture"** — as already filed (bounded suppression
  of attention), WIDENED from "a background command" to the general
  round-starvation obligation: a track at or below its wind-down threshold
  that has been observably unable to open a round past a bounded floor MUST
  be surfaced, report-only, with the preempting evidence named; the
  shell-specific wording becomes the named instance.
- **spec.md §"Notify, never block"** — the edge-trigger sentence gains the
  age-band escalation for standing human-waits (B2): one line on entry plus
  at most one per crossed age band.
- **The supervisor pair member as a full supervised entity (maintainer
  ruling)** — the derived `-supervisor` session is supervised under the
  SAME contract as its worker, per entity: its own state file
  (`tmp/overseer/<topic>-supervisor/`), the same wrap-up trigger and
  bands, the identical ready interlock (the cardinal rule restated
  per-entity: only the supervisor's own fresh `ready` restarts the
  supervisor), the same-name atomic respawn, resume pointer
  `plan/<topic>/supervisor-handoff.md` (still pointed at, never opened),
  and the respawn additionally gated on the already-permitted existence
  probe. Touches spec.md's supervision-round/wrap-up/restart language
  ("every tracked session" grows to "every supervised entity") and
  contracts.md §"The state file" (the supervisor's path joins the table).
  Amend EXISTING sections — the heading-coverage fixture mechanically pins
  every `## ` heading in spec.md to a real test
  (`tests/heading-coverage.json`), so the proposal may not add a heading
  ahead of the implementing slice's tests.
- **The pair nudge and its posture exception (maintainer ruling 3)** —
  spec.md gains the both-stalled supervisor nudge obligation with its
  guard set, INCLUDING the explicit statement that this is the one bounded
  exception to shell-classified busy suppressing acts (fired only at a
  verified empty settled prompt, never generating, never over a gate /
  `waiting` / `blocked:`, once per episode). contracts.md §"The state
  file" gains the one new daemon-written marker value for the nudge's
  edge-trigger (authorizes nothing; never clobbers a session value).
- **spec.md §"Track discovery and the mapping store"** — the `-supervisor`
  namespace reservation (wave 1): discovery MUST refuse a plan directory
  whose name ends in `-supervisor`, surfaced by name, so a supervisor
  session can never be adopted as a worker track.
- **contracts.md §"Attention surface"** — membership restated as the five
  instant members PLUS the report-only bounded members this note defines
  (round-starvation with its shell instances, below and above threshold;
  the post-nudge pair-stalled line), each carrying the same coordinates,
  edge-triggering, clear-and-re-arm, and worker-no-act guarantees.
  Supervisor entities need no new membership entry: as full citizens their
  rows enter attention through the SAME statuses as workers.
- **Wording obligations carried into the widened proposal.** (i) Wave-1
  safety #15: the filed EDIT 2's "a genuine build is never reported as a
  problem" is a falsifiable MUST — no finite floor satisfies "never". The
  widened wording says the floor is long enough that ordinary long-running
  background work COMPLETES inside it, and accepts the >floor genuine-build
  residual explicitly (one report-only line whose text is literally true).
  (ii) Code-truth extra finding: the filed Motivation ¶4 misquotes the
  spec's scope sentence as placing the "status vocabulary" outside the
  governed contract — spec.md says "COMMAND vocabulary". The substantive
  justification survives via "the pane's track table, its columns", but
  the widened proposal must correct the load-bearing quote.
  (iii) Codex-codetruth E2: the filed proposal says "Two edits" while
  labeling EDIT 1/2/3 — the count is corrected in the widened text.

Explicitly unchanged: the cardinal rule, the supervision round, the
escalating wrap-up, the restart interlock, the state-file grammar, and
surface-only startup. Out-of-governed-scope coherence edits at
implementation time: `overseer/AGENTS.md` (state diagram, precedence,
colors, attention), `overseer/marker-protocol.md` (these conditions never
inject), `.claude-plugin/prose/overseer.md` (status table), and
`SPECIFICATION/scenarios.md` — each scenario landing atomically with its
integration test and heading-coverage row, per the standing outcome
constraint.

## The §1 test, applied to every line this note adds

| New line | Stall direction (does silence end?) | Noise direction (can the operator act?) |
|---|---|---|
| `shell-prolonged` (ratified) | closes incident 1's region | names the shell, its age, the % — operator kills/fixes the dead command in the named pane |
| `winddown-starved` | closes incident 2's region and the BELOW-THRESHOLD class, including future absorbing states (and backstops the ratified instance's poke/false-busy residuals) | enumerates the preempting evidence + starvation age — operator goes to the named pane and unwedges the specific obstruction |
| above-threshold no-progress (wave 1) | closes the above-threshold shielding hole both wave-1 lenses found — the stall that never drifts down to any threshold | same evidence enumeration; 8 h floor is the noise control replacing the low-context anchor |
| blocked age + bands | ends the 22-hour silent-history wait | the operator IS the awaited party; a dated reminder of an owed answer is maximally actionable |
| supervisor full citizenship (ruled) | ends silent supervisor death AUTONOMOUSLY — wrap-up, wind-down, ready-gated restart; the operator is paged only where a worker would page | supervisor rows use the worker vocabulary; no new operator surface at all in the healthy path |
| supervisor nudge (ruled) | breaks the M3 mutual wait without a human — the autonomous remedy fires first | costs one supervisor turn on a false positive, not an operator interrupt; never fires over a presented question (that surfaces instead) |
| pair-stalled operator line | the escalation floor when the nudge already failed — no stall outlives it silently | the line SAYS the autonomous remedy failed, which is what makes it actionable: a human is genuinely owed, both panes named, supervisor first |

Every DETECTION in this note is report-only against the WORKER — nothing
here adds any act path onto a worker session, and no shell age, timer, or
context percentage authorizes a paste, Enter, respawn, kill, or
declaration write against one. The acts this contract does add are the
maintainer-ruled supervisor paths, and each reuses an already-ratified
act shape under its full guard set: the supervisor wrap-up and restart
are the worker's own machinery (the ready interlock included, per
entity), and the pair nudge is the keep-going nudge's act discipline
under strictly narrower conditions, with its one posture exception
stated in governed prose rather than hidden. Ambiguity in any input
still resolves toward silence (unknown ctx, unproven identity,
unobserved gaps all delay rather than fire).

## Tests the implementation owes (sketch, per lane)

Beyond `policy-options.md` §6's nine for the ratified instance:

1. Round-starvation: below threshold + no stamp + alternating
   blocked/generating phases across the floor ⇒ `winddown-starved`, one
   alert, in `NEEDS YOU`; and the same fixture asserts no paste, no Enter,
   no respawn, no kill, and the `blocked:` declaration NOT voided by the
   surfacing path.
2. Round-starvation negative: the round opening on an idle tick clears it;
   ctx recovery clears it; a generating tick never fires it; unknown ctx
   never starts it; daemon restart delays it.
3. Blocked age bands: one alert per band per declaration; re-declaration
   resets; per-tick re-alerting impossible; restart re-states at most the
   highest band once.
4. Registry-miss guard (wave 1): a Claude session with `claude_status`
   None and a live descendant shell accrues NO shell episode (`is_codex`
   false); the genuine Codex twin still does.
5. Supervisor full citizenship (ruled — note the sabotage tests INVERT
   from the monitor-only draft: the owed proof is no longer "no act path
   exists" but "every act path fires ONLY under its guards, never
   otherwise"): derived-name + containment discovery; the pair pass runs
   while the WORKER is busy/blocked (not only in the idle leaf); a
   `plan/<x>-supervisor/` directory is refused by discovery and surfaced
   by name; the supervisor wrap-up fires at threshold into a verified-idle
   supervisor pane and NEVER into a gate; the supervisor restart fires
   ONLY on the supervisor's own fresh `ready` against its own stamp
   (a worker's `ready` can never restart its supervisor and vice versa —
   the crossed-file sabotage goes red); a `ready` with no
   `supervisor-handoff.md` holds the round open and surfaces the
   capture-offer; the respawn preserves the `-supervisor` session name.
6. Pair nudge (ruled): both-stalled past the floor with no human gate
   nudges the SUPERVISOR once per episode; a structured gate, registry
   `waiting`, or standing `blocked:` on EITHER member suppresses the nudge
   and surfaces instead; a generating member (registry `busy` or spinner)
   means no stall; the nudge marker never clobbers a session-written
   value; still-stalled one floor later emits the operator line naming
   the failed nudge.
7. Alert identity (wave 1): a standing condition with a changing embedded
   age emits no new line between escalation boundaries; each band key
   fires exactly once; a condition key re-arms when ITS condition clears
   even while the row stays in `NEEDS YOU` via an unrelated condition.
8. Above-threshold instance (wave 1): shell-classified no-progress past
   the long floor fires report-only at ANY context; a single progress tick
   resets; an idle (non-shell) track above threshold never reaches it.
9. Cascade amendment (codex-autonomy #4): standing `blocked:` + shell-only
   busy on a non-generating tick renders `blocked:human` with both facts
   in the note and fires the alert — while the declaration remains never
   voided (the pinned bound keeps its load-bearing assertion); a
   GENERATING tick keeps today's precedence.
10. Note priority (codex-autonomy #5): a malformed state file plus a
    background shell keeps its `BAD state file` note and its `NEEDS YOU`
    membership on every tick.
11. Ctx staleness (codex-autonomy #11): a last-known value unseen past the
    staleness window demotes to unknown (no ctx-gated mechanism fires on
    it) and raises one daemon-level notice; a successful parse restores.
12. The two standing heading-coverage tests named by the handoff's outcome
    constraints
    (`test_needs_attention_predicate_covers_every_attention_status`,
    `test_ctx_unknown_never_injects`) grown, not weakened, by the
    implementing slice. Naming nuance (claim 13 of both tables): the
    fixture's ids read `overseer.test_supervisor.*`, but the functions
    live in `test_supervisor_tmux_column_annotates.py` and
    `test_supervisor_warned_stamp_written.py` respectively — stale
    qualified names left over from the test-module split. The JSON id fix
    belongs to the IMPLEMENTING slice, which already must grow those very
    rows — not to the widening step, which deliberately touches no
    heading-coverage rows.

Gate: `uv run pytest overseer -q`, then `just check`. No existing check may
be weakened, removed, skipped, or exempted.

## Open maintainer decisions

Defaults are recommended rather than derived; each is safe to change
without reopening the design:

1. **The starvation floor** — recommended 7200 s, equal to the ratified
   shell floor (one value in the contract, not two).
2. **The general-clause status token** — recommended `winddown-starved`;
   rejected alternatives recorded above.
3. **Blocked escalation bands** — recommended {4 h, 24 h, then every 24 h}.
4. **Worker-override propagation** — whether a track's `ctx_threshold`
   override also governs its supervisor entity; recommended no (the ruled
   default is the daemon-wide 50). The former decision here — a 20%
   report-only attention floor — DISSOLVED under the full-citizenship
   ruling.
5. **The above-threshold floor and token** (wave 1) — recommended 8 h,
   reusing `shell-prolonged`; reasoning in the above-threshold arm.
6. **The continuity-gap value** (wave 1) — recommended 300 s for every
   lane-A clock, sized to the worst-case tick; replaces the narrow
   predicate's proposed 60 s at implementation time.
7. **Pair-nudge parameters** — the marker token name (recommended
   `pair-stall-nudged`; the in-memory fallback avoids grammar growth at
   the cost of one repeat nudge per daemon restart), and the
   post-nudge escalation floor before the operator line (recommended one
   further 2 h floor). The former decision here — a post-C measurement
   period gating the detector's arming — DISSOLVED under ruling 3's
   mandate.
8. **Whether daemon self-liveness becomes its own thread** (wave 1) — the
   in-memory-clock residual and the unobserved restart cadence, recorded
   in §"Two cross-cutting boundaries"; out of these four lanes either way.
