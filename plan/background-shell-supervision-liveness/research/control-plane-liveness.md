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

Status: **investigation complete, ready for adversarial review.** Nothing here
is implemented and nothing may be implemented from this note. It changes
governed clauses (§"Governed clauses this changes"), so it goes through the
widened `livespec:propose-change` first; the narrow instance then implements
through `impl:overseer-vyjkzw` and the widened lanes through sibling
work-items under epic `overseer-4xfmez`.

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
  round — and `void_stale_blocked` (called from exactly one site, `:206`)
  voided the now-stale declaration, **31 times** between 2026-07-25T21:28:38Z
  and 2026-07-28T03:15:26Z, at declaration ages from 121 s to 80 728 s
  (~22.4 h); the session then re-declared and the cycle repeated.

The track was never in any third state, so no round could open in either
phase. It burned to 22% with no wrap-up ever sent. Note what this incident is
NOT: it is not the "idle blocked is never voided" permanence the first brief
described. The declaration WAS voided, repeatedly. The trap is the precedence
of TWO branches over the threshold branch, and it needs no permanence at all.
A fix aimed only at voiding behavior misses it entirely.

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
| Every declaration's age | `TrackState.mtime` (`signals.py:357`), returned by every `read_state` call; used today for exactly two purposes (the 900 s ACK staleness, the 120 s void grace) |
| A continuous in-memory episode | `InjectState.idle_since` (`_supervisor_records.py:43`), advanced in `observe` (`_supervisor_observe.py:222–226`); the ONLY `_since` in the package |
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
   moment it fires.

The ratified shell-episode clock (`shell_since` / `shell_last_seen`,
`policy-options.md` §2) is the first instance of mechanism 2. `idle_since` is
retroactively the zeroth. Lanes B–D name their instances below; no lane may
mint a clock outside this rule.

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
  the wrap-up branch.
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
clause fires, its alert names the CURRENTLY preempting evidence (the
`blocked:` declaration and its void history, the gate, the shell) plus the
live remaining %, the starvation age, and the standing truth that the daemon
has taken no action and will not restart without a fresh `ready`.

Recommended row status for the general firing: **`winddown-starved`**
(yellow; `ATTENTION_STATUSES`; alert condition key `winddown-starved`).
Rejected names: `stuck` (asserts a stall the daemon has not proven),
`shielded` (names the mechanism, not the operator-relevant fact),
`no-round` (internal bookkeeping vocabulary). Token choice is flagged as a
maintainer decision, as `shell-prolonged`'s was.

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

Lane B decomposes into three independent behaviors. None of them voids an
idle declaration on a timer — see the first disagreement in
§"Disagreements" for why that route is rejected outright.

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

### B3 — dead-predecessor voiding (event-proof, not timer)

The one honest gap in `void_stale_blocked`: a pane replaced out-of-band (a
hand-restart, a `/clear`) inherits its predecessor's `blocked:`; if the
successor never generates — comes up and sits idle — the false
`blocked:human` stands forever, keeping a track in `NEEDS YOU` for a
question nobody is asking. Voiding on generation cannot catch it; voiding on
age must not (the long idle human-wait is the normal case).

There IS an exact, timer-free proof available: **the declaration predates
the live session's own birth.** A session that started after the file was
written cannot have written it. The daemon already holds the session's
start time — `procStart`, used for PID-reuse defence
(`claude_sessions.py:232`) — but in `/proc` clock ticks since boot, compared
today only as an opaque string. Converting to epoch (boot time from
`/proc/stat` `btime` plus `ticks / CLK_TCK`) is deterministic and cheap,
but it IS new mechanism — the handoff's §7 overstates this as "exact,
durable, and needs no timer" without the unit conversion; recorded in
§"Disagreements". The comparison must carry a safety margin (clock steps,
suspend/resume skew) and fail toward KEEPING the declaration: a kept stale
declaration only keeps alerting, while a wrongly voided one lets the track
fall through to the idle cascade — where a nudge or wrap-up could be pasted
into a session that is genuinely waiting on a human. Codex parity: the same
`/proc` stat read serves a live codex pid; same margin, same fail-closed
direction.

B3 is the lowest-urgency behavior in this note (its trap produces a
too-loud surface, not a silent one) and may be sliced last or deferred by
the maintainer without weakening A–D.

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

### The candidate — the track as a PAIR, monitor-and-surface only — SELECTED

A track optionally carries a supervisor MEMBER: the `<derived-session>
-supervisor` tmux session, discovered by the SAME name derivation and the
same containment check the daemon already applies (`supervisor_session_of`
composes the collision-aware `session_of`; `supervisor_running` already
proves pane process + repo containment). For a pair member that exists and
is live, the daemon additionally reads what it reads for any pane — the
capture, hence `Context N% left` via the existing runtime-agnostic parser,
and the coarse busy/idle/gate classification — and:

- **renders** the supervisor beside its track (an annotation or sub-row —
  ungoverned view detail, implementation's choice);
- **surfaces** exactly one new report-only attention member: a live
  supervisor at or below a context floor. Recommended floor: the DANGER
  line (20%), not the track threshold — a supervisor has no wrap-up lever
  aimed at it in this cycle, so the alert is a hand-off to the operator,
  and paging a human at 50% for a session only they can wind down is noise;
  paging at 20% is "the brief dies soon — go save it". The row (ungoverned)
  may show the supervisor's context from any level; only the ATTENTION
  floor is governed. Flagged as a maintainer decision.
- **acts on the supervisor in NO way.** No wrap-up, no nudge, no restart,
  no state file, no `supervisor-handoff.md` read (the existence probe
  already permitted by spec stays the only file-level touch). A supervisor
  holds the plan's live judgment; restarting it is strictly more dangerous
  than restarting a worker, and the daemon has no ratified protocol with
  it. The alert's action line is the existing attended path: wind it down
  in its own pane and recapture via `/livespec-overseer:supervise-plan`.

The alert must say explicitly which pane to visit (the supervisor's own),
what is at stake (the brief), and what the daemon will and will not do
(surface only; never restart a supervisor) — the §1 actionability test
applied to the one line this lane adds.

**The growth path is recorded, not taken**: making supervisors full citizens
(wrap-up + `ready`-gated restart against `supervisor-handoff.md`) would
require the supervisor charter to teach the state-file protocol and a
ratified extension of the restart contract, and it touches the same
generated-charter file `plan/supervisor-scratch-discipline/`
(`overseer-5jttov`) edits — a sequencing note, not a gate, exactly as the
handoff's §8 resolves it. Nothing in this cycle depends on it.

### Rejected alternatives

- **Give supervisors plan directories** so discovery sees them: pollutes the
  plan namespace with non-plans, doubles the track list, invites
  supervisor-of-supervisor regress, and breaks the archived/unarchived
  lifecycle semantics for a thing that is not a plan thread. Rejected.
- **Register supervisors as mapping-store rows**: the store persists ONLY
  facts not re-derivable from the filesystem (invariant 4), and the pair
  member is fully derivable (derivation + containment). A stored row is a
  hand-maintained list waiting to go stale. Rejected.
- **A second daemon (supervisor-of-supervisors)**: the daemon is already the
  terminal watcher; monitor-and-surface from the existing loop costs one
  capture per supervisor per tick. Rejected as structure for structure's
  sake.
- **Status quo** (the two booleans): measured above; fails §1's stall
  direction for every supervisor in the fleet. Rejected.

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
gate are not progress. Recording "when did `eff_ctx` last change" is one
small addition beside `last_ctx` (a `last_ctx_changed_at` stamp under lane
A's rule; §7's "`InjectState.last_ctx` is already the storage" is storage of
the VALUE only — noted in §"Disagreements").

### The candidate — pair-stalled, defined now, armed after lane C — SELECTED with a gate

With lane C in place, the mutual wait becomes expressible from outside both
sessions: **a pair is stalled when BOTH members have shown no
`progress_now` and NEITHER is in a human-waiting state (gate, registry
`waiting`, or a standing `blocked:` — those have their own surfaces) for a
continuous 2-hour floor** (one lane-A clock on the pair condition).
Report-only, edge-triggered, clears the moment either member progresses;
the alert names BOTH panes and sends the operator to the supervisor first
(it owns direction), with the same no-act statement as every other line in
this note.

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

**The armed/deferred split.** The definition above is settled NOW (it is
what the widened proposal ratifies); the FUSED detector ships only after
lane C lands and its per-member surfaces have been observed for a
measurement period, because lanes A+C may already make the mutual wait
operator-visible (two adjacent rows, both carrying durations, one of them a
supervisor at `shell (3h)`) — in which case the fused alert would be a
duplicate line, failing §1's noise direction. The post-C re-measure is the
admission test: if pairs still stall silently past the floor with A+C live,
arm D; if every observed mutual wait was already legible from the paired
rows, file the fused detector as not-needed with the measurement attached.

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
| Shell episode (ratified) | in-memory clock | first `shell_episode_now` tick | evidence-false tick, or observation gap > 60 s | row exits `NEEDS YOU` → alert keys drop | clock resets; delay-only |
| Round-starvation | in-memory clock | first tick below threshold with no stamp | ctx recovers above threshold; a round opens (stamp written); observation gap | same key-drop rule | clock resets; delay-only |
| Blocked age + bands | on-disk mtime (no clock) | declaration write | new declaration (new mtime) resets bands; declaration cleared/voided ends episode | next declaration is a fresh episode | age survives (mtime); band memory in-memory → at most one true re-statement |
| Dead-predecessor void | event proof (no timer) | n/a | n/a — one-shot on proof `mtime + margin < session-start epoch` | n/a | proof re-derivable; idempotent |
| Supervisor low-context | instant condition (no clock) | crossing the floor | ctx recovers, or supervisor exits | key-drop on recovery | stateless |
| Pair-stalled | in-memory clock (post-C gate) | first no-progress-both tick | any member progresses; any human-waiting state; gap | key-drop rule | clock resets; delay-only |

Every alert above is coordinate-rich (via `sup.alert` — topic, repo,
session, pane, jump command) and edge-triggered; none of the new condition
keys joins `SUPERVISION_CONDITIONS` (the re-arm exemption set). Every
in-memory clock fails in the delay direction on restart, never the
false-alarm direction.

## Disagreements with prior briefs — deliberate, with the forcing measurement

1. **Brief 1's "void a stale `blocked:` on idle ticks" is rejected**
   (agreeing with handoff §7): an idle blocked session is the normal case
   of waiting on a human; a timer that discards the declaration both
   overrules a session-owned semantic assertion and drops the track into
   the idle cascade where the nudge/wrap-up machinery could keystroke into
   it. Escalate-by-age (B2) and the dead-predecessor proof (B3) replace it.
2. **Brief 1's "permanent by construction" mechanism for incident 2 is
   wrong in the direction that matters**: the log shows 31 voids — the
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
5. **Handoff §7's lane B route (ii) understates its own mechanism**:
   `procStart` is clock ticks since boot compared as a string
   (`claude_sessions.py:232`), not an epoch time comparable to a file
   mtime; the boot-time conversion is real (small, deterministic) new
   mechanism and needs a safety margin that fails toward keeping the
   declaration.

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
- **spec.md §"Non-interference with tracked work"** (or the discovery
  section it cross-references) — the supervisor pair member: the daemon MAY
  observe the derived `-supervisor` session's pane exactly as it observes a
  track's (capture, context, coarse state), MUST surface its low-context
  condition report-only, and MUST NOT inject into, nudge, restart, or write
  any state for it. Amend EXISTING sections — the heading-coverage fixture
  mechanically pins every `## ` heading in spec.md to a real test
  (`tests/heading-coverage.json`), so the proposal may not add a heading
  ahead of the implementing slice's tests.
- **contracts.md §"Attention surface"** — membership restated as the five
  instant members PLUS the report-only bounded members this note defines
  (round-starvation with its shell instance; the supervisor floor;
  pair-stalled once armed), each carrying the same coordinates,
  edge-triggering, clear-and-re-arm, and no-act guarantees.

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
| `winddown-starved` | closes incident 2's region and the CLASS, including future absorbing states | names the preempting evidence + starvation age — operator goes to the named pane and unwedges the specific obstruction |
| blocked age + bands | ends the 22-hour silent-history wait | the operator IS the awaited party; a dated reminder of an owed answer is maximally actionable |
| supervisor low-context | ends silent supervisor death | names the supervisor pane and the recapture command; the operator is the only actor who can wind a supervisor down |
| pair-stalled (post-C gate) | closes the M3 mutual-wait region | names both panes and which to visit first; ARMED only if A+C measurement proves the paired rows alone did not already make this legible — the one line in this note whose noise risk is judged real enough to gate on measurement |

Every line is report-only; none authorizes any of the five forbidden acts;
ambiguity in any input resolves toward silence (unknown ctx, unproven
identity, unobserved gaps all delay rather than fire).

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
4. Dead-predecessor void: declaration older than session birth (with
   margin) voided once; younger kept; conversion failure keeps; codex twin
   through the injected `/proc` seams.
5. Supervisor pair: derived-name + containment discovery; low-context
   member fires report-only with the recapture command; sabotage: removing
   the no-act guard (routing a supervisor to `maybe_inject` or
   `do_restart`) goes red.
6. Pair-stalled (when armed): both-idle past floor fires; either member's
   progress (including registry `busy` and ctx movement) resets; any
   human-waiting state suppresses.
7. The two standing heading-coverage tests named by the handoff's outcome
   constraints
   (`test_needs_attention_predicate_covers_every_attention_status`,
   `test_ctx_unknown_never_injects`) grown, not weakened, by the
   implementing slice.

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
4. **The supervisor attention floor** — recommended the danger line (20%),
   not the wind-down threshold; reasoning in lane C.
5. **Whether B3 (dead-predecessor void) ships in this cycle** — it repairs
   a too-loud surface, not a silent one, and may be deferred.
6. **The pair-stalled admission measurement** — the post-C observation
   period length before lane D's fused detector is armed or filed
   not-needed.
