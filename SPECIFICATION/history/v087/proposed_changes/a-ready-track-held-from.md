---
topic: a-ready-track-held-from
author: claude-opus-5-5
created_at: 2026-11-05T13:33:49Z
---

## Proposal: Bounded ready-hold event

### Target specification files

- SPECIFICATION/spec.md
- SPECIFICATION/contracts.md
- SPECIFICATION/scenarios.md

### Summary

A READY HOLD is defined by observable state: a track whose state-file token is exactly `ready`, whose declaration is certifiable under preconditions 1–5 of the restart interlock, and for which the supervising loop's evaluation withholds replacement because at least one of four live-pane conditions holds (busy with its source, not-idle, unsettled, or a failed immediate pre-act identity re-check). When a ready hold persists past the ready-hold window, the daemon MUST write one `overseer:` diagnostic event to its stderr event history naming the track and every holding condition the evaluation actually observed, repeated at most once per further window (a 600-second window gives events at 600 s, 1200 s, 1800 s, ...). The window is set by a new `overseerd` launch option, `--ready-hold-window-seconds N` (a strictly positive integer, default 600; an invalid value refuses startup), and contracts.md §"Daemon invocation" is corrected to list the daemon's true option set. A `ready` that fails any interlock precondition is never a hold, and neither is a session-gone, live-outside-tmux or unidentified-session track. The change is observability-only: no restart gate, interlock precondition, cascade order, or authorization changes, and restart suppression stays unbounded.

### Motivation

Work item overseer-qz7ez7. On 2026-11-05 the fleet daemon v5.52.1 held a `ready`, idle track (livespec-orchestrator-beads-fabro::kubernetes-sandbox-backend) from replacement for more than 15 minutes and logged no event at all, because the busy, not-idle, unsettled and identity holds are silent. Those gates sit UPSTREAM of the `request.ready` leg in the evaluation cascade (`_supervisor_evaluate.py`, `_supervisor_evaluate_active.py`, `_supervisor_evaluate_idle.py`), while certification is computed earlier in the same evaluation, so the hold is defined here by observable state rather than by cascade position. The identity condition is restricted to the immediate pre-act re-check (`pane_is_managed` in `_supervisor_evaluate_idle.py`, which yields `settling`), because an identity that cannot be established fails precondition 4 closed and is never certifiable. The spec already bounds ATTENTION for withheld rounds (spec.md §"Fail-soft posture") and immediately surfaces a determined precondition-4 identity mismatch (contracts.md §"The restart interlock"), but nothing reports a certifiable `ready` held by the live-pane conditions. contracts.md §"Daemon invocation" says `overseerd` takes "exactly ONE option" while the shipped `overseer/daemon.py` already accepts `--idle-nudge` as well, so adding a third option requires correcting that count. Amended twice after independent ratification reviews. In-flight survey: no open spec-touching PR; five `spec/*` branches (caam-capacity-aware-rotation, daemon-message-channel-delivery, ratify-launch-profile-launch-model, revise-three-proposals-v033, sanctioned-out-of-band-seat), none of which edits the restart branch's acting gates; this proposal aligns with all of them.

### Proposed Changes

Observability-only. Every existing restart and interlock gate, and the order of the evaluation cascade, stays exactly as it is; nothing below authorizes, suppresses, accelerates or delays a replacement. RESTART suppression for busy, changing and ambiguous evidence remains UNBOUNDED under spec.md §"Fail-soft posture"; this proposal bounds only how long such a hold may go UNREPORTED.

**1. contracts.md §"The restart interlock".** Insert the following paragraphs immediately after the paragraph ending "...a positive identity check that the pane really is this track's supervised session in this track's repository." (and before the paragraph beginning "A standing `ready` held by precondition 4..."):

> **The ready-hold event.** A READY HOLD is a track whose state-file token is exactly `ready`, whose declaration satisfies preconditions 1–5 of this interlock (certifiable), and for which the daemon withholds replacement in the supervising loop's evaluation because at least one of the four live-pane conditions below holds. A hold is defined by that observable state, never by the position in the evaluation cascade at which the withholding occurs. The four HOLDING CONDITIONS are exactly:
>
> - `busy`, carrying each SOURCE observed: `spinner` (a generating or sub-agent-busy marker in the pane), `background-wait` (a background-shell or background-wait line in the pane, or the runtime's descendant-shell evidence), or `session-status` (the harness-reported session status, carrying its value, e.g. `busy` or `shell`);
> - `not-idle` (no verified empty idle input state);
> - `unsettled` (the two settle captures differ);
> - `pane-identity`, which is ONLY the immediate pre-act identity re-check: in an evaluation that has already certified preconditions 1–5, the re-verification taken after the settle captures that the pane is still this track's supervised session in this track's repository fails, and the evaluation waits for the next observation instead of acting.
>
> A `ready` that fails ANY of preconditions 1–5 is NEVER a ready hold, even when the pane also shows one or more of the four conditions. In particular an identity that cannot be determined fails precondition 4 closed and is therefore never a hold. Such a `ready` remains governed by its own attention memberships, including the immediate surfacing of a determined precondition-4 mismatch below, and MUST NOT emit this event. A track whose evaluation resolves to `session-gone`, `live-outside-tmux` or `unidentified-session` (spec.md §"Session-name derivation") has no managed pane to replace and is NEVER a ready hold.
>
> The READY-HOLD WINDOW is the configured value of the `overseerd` launch option `--ready-hold-window-seconds` (contracts.md §"Daemon invocation"), default 600 seconds. The daemon's supervising loop (never a read-only listing surface) MUST measure a ready hold from the first acting evaluation that observes it, continuously while every acting evaluation of the track observes it. A cycle evaluated with acting disabled (the read-only `act=False` path) neither starts nor ends a hold measurement. The hold ends when replacement proceeds, when the track is no longer a ready hold (the token is no longer `ready`, the declaration stops certifying, or no holding condition is observed), or when the declaration's modification time changes. A change in WHICH holding conditions are observed does not end the hold. The measurement MAY be held in memory: a daemon restart restarts the measurement, which can delay the event but MUST NOT suppress it.
>
> When a ready hold has persisted for longer than the ready-hold window, the daemon MUST write ONE event for the track to its event history: an `overseer:`-prefixed diagnostic line on standard error, per §"Daemon invocation", and NOT an `overseer[SURFACE]:` alert line or an attention membership. A certifiable `ready` held by live-pane evidence is the cardinal rule working as designed rather than a condition waiting on a human, so raising it as an alert would report ordinary long-running work as needing a person; the event exists so that an operator investigating a long hold can find its cause in the history. The event MUST nonetheless carry the coordinates spec.md §"Notify, never block" requires of a track-scoped alert: the plan topic, the repository, the session and pane, and a copy-pasteable jump command. It also carries the declaration's age, the hold's age quantized to the window boundary just crossed, and EVERY holding condition the emitting evaluation ACTUALLY observed — never a single presumed cause — each `busy` condition with every source observed and, for `session-status`, its value. Observing a holding condition MUST NOT require any capture, delay, or keystroke beyond what the unchanged gates already perform; a condition the evaluation did not reach is not named.
>
> While the same hold persists, the event MUST be re-emitted at most once per further ready-hold window, on crossing each multiple of the window, and MUST NOT be emitted once per cycle. With the default 600-second window, a hold that persists for 25 minutes produces events at 600 s, 1200 s and nothing more until 1800 s. Its dedup identity is the ready HOLD for the track, not the individual holding condition: a change of holding condition alone MUST NOT re-emit it ahead of the next window boundary, and the next emission names the conditions then observed. This intentionally departs from §"Notify, never block"'s per-condition re-arm ("each condition re-arms when THAT condition clears"): busy evidence on a working session routinely alternates between sources, and between busy and unsettled, from one cycle to the next, and per-condition re-arming would turn one hold into a stream of entries. The measurement and the per-window allowance re-arm only when the hold ends.
>
> Other silent withholdings of a certifiable `ready` are OUT OF SCOPE of the ready-hold event: the statusline-model veto, a track with no recorded epic id, a round held for `resume_pending` submission retry, and a backend restart refusal. Each stays governed by its own existing surfacing.
>
> The ready-hold event is REPORT-ONLY. It MUST NOT authorize or suppress an injection, keystroke, command termination, declaration write, declaration voiding, or restart, and MUST NOT alter any interlock precondition or live-pane gate. It MUST NOT be evaluated in a position that prevents any branch of the evaluation cascade from being reached or alters which branch is selected. A failure to write the event is a storage error on the overseer's own files under spec.md §"Fail-soft posture": it is reported and survived, and it MUST NOT change the track's restart decision.

**2. contracts.md §"Daemon invocation".** Replace the opening paragraph (beginning "`overseerd` runs with NO subcommands and exactly ONE option") with:

> `overseerd` runs with NO subcommands. Its options are exactly these three, each a daemon-wide setting:
>
> - `--warn-percent N`, an integer from 1 to 99: the daemon-wide default remaining-context threshold at which the first wrap-up fires (default 50). A per-track threshold override in the mapping store wins over it.
> - `--idle-nudge {on,off}` (default `on`): the daemon-wide switch for the keep-going nudge to a session idle with context left. A per-repository or per-track override wins over it. It governs that nudge alone; the low-context wrap-up and the restart on `ready` cannot be switched off.
> - `--ready-hold-window-seconds N`, a strictly positive integer (default 600): the ready-hold window of §"The restart interlock", its "ready-hold event" rule. It governs only when that report-only event is written and changes no gate.
>
> An option value outside its stated domain — for `--ready-hold-window-seconds`, any value that is not a strictly positive integer, including zero, a negative number or a non-integer — MUST make the daemon refuse to start: it exits non-zero with a message naming the option and the rejected value, before any startup gate runs and before any track is observed. There are deliberately NO flags for the store, sidecar, or watch-set paths, and no recovery or interval options: the paths are fixed by construction, and the daemon is surface-only (per spec.md §"Surface-only startup").

**3. spec.md §"The restart".** Replace the paragraph beginning "A session that declares `ready` and then resumes work" with the same paragraph followed by one added sentence, so it reads:

> A session that declares `ready` and then resumes work — narrates further, emits more turns, streams stop-hook output — keeps its declaration armed; the restart branch's settle and busy gates prevent a kill mid-work without requiring any activity-based clearing. The declaration is cleared only by a successful restart or by exceeding its bounded maximum age (per contracts.md §"The state file", its "Stale-declaration voiding" rule). Withholding the restart of such a ready hold remains unbounded under §"Fail-soft posture", but the daemon MUST NOT leave such a hold unreported past the ready-hold window: a certifiable `ready` withheld by the busy, not-idle, unsettled or pre-act identity re-check condition for longer than that window MUST produce a report-only diagnostic event naming the track and every holding condition observed, repeated at most once per window while the hold persists (per contracts.md §"The restart interlock", its "ready-hold event" rule); the event changes no gate and authorizes nothing.

**4. scenarios.md.** Insert immediately after `## Scenario: A ready declaration remains armed when its session resumes work`:

```
## Scenario: A ready track held from replacement past the hold window logs a hold event

Given a track whose state file reads ready with a declaration that satisfies every restart-interlock precondition

And the supervising loop's evaluation withholds replacement because the pane is unsettled

When the hold has persisted for longer than the ready-hold window

Then the daemon writes one overseer: diagnostic event to its event history naming the track's plan topic, repository, session, pane and jump command

And the event names the holding condition unsettled, the declaration's age, and the hold's age at the window boundary crossed

And no overseer[SURFACE]: alert or attention membership is raised for the hold

And no restart, keystroke, paste, declaration write or declaration voiding occurs on account of the event

And the evaluation selects exactly the branch it would select without the event

## Scenario: A ready hold is not re-reported within the same hold window

Given a ready hold that has already written its hold event at the 600-second boundary of a 600-second window

When the hold persists through further supervision cycles before the 1200-second boundary, its holding condition changing from busy to unsettled

Then no further hold event is written for the track

## Scenario: A persisting ready hold is re-reported at the next window boundary

Given a ready hold that has already written its hold event at the 600-second boundary of a 600-second window

When the hold persists past the 1200-second boundary

Then exactly one further hold event is written, naming the holding conditions observed in that evaluation

## Scenario: A ready hold that ends measures a later hold afresh

Given a ready hold that has already written its hold event

When the state file no longer reads ready and a later ready declaration is held again

Then the later hold's window is measured from its own first acting evaluation

## Scenario: A busy hold names the source of its busy evidence

Given a track whose state file reads ready with a declaration that satisfies every restart-interlock precondition

And the supervising loop's evaluation withholds replacement because a background-wait line is visible in the pane

When the hold has persisted for longer than the ready-hold window

Then the hold event names the holding condition busy with source background-wait

## Scenario: A failed pre-act identity re-check is a pane-identity hold

Given a track whose state file reads ready with a declaration that satisfies every restart-interlock precondition

And every acting evaluation's immediate pre-act identity re-check fails after the settle captures, so the evaluation waits instead of acting

When the hold has persisted for longer than the ready-hold window

Then the hold event names the holding condition pane-identity

And no restart occurs

## Scenario: An uncertifiable ready on a busy pane is never a ready hold

Given a track whose standing ready declaration fails a restart-interlock precondition

And the pane shows a spinner

When the declaration stands past the ready-hold window

Then the daemon writes no ready-hold event for the track

And the declaration is surfaced only through the certification failure's own attention membership

## Scenario: A read-only listing neither starts nor ends a ready-hold measurement

Given a track in a ready hold whose measurement began at an acting evaluation

When the track is evaluated by the read-only listing path

Then the hold measurement is neither restarted nor ended by that evaluation

## Scenario: The ready-hold window is configured at daemon launch

Given the daemon launched with --ready-hold-window-seconds 120

And a track in a ready hold

When the hold has persisted for longer than 120 seconds

Then the daemon writes the hold event

## Scenario: The ready-hold window defaults to 600 seconds

Given the daemon launched without --ready-hold-window-seconds

When a track's ready hold has persisted for 599 seconds

Then no hold event has been written for the track

## Scenario: The daemon refuses to start with an invalid ready-hold window

Given an overseerd launch with --ready-hold-window-seconds 0

When the daemon starts

Then it exits non-zero with a message naming --ready-hold-window-seconds and the rejected value

And no startup gate runs and no track is observed
```

**5.** **tests/heading-coverage.json** (outside the spec target; co-edited atomically by the revise that ratifies this proposal). Each new scenario heading above MUST receive a registry entry (`"test": "TODO"` until an integration-tier pinning test lands), per non-functional-requirements.md §"Scenarios".

## Proposal: Stuck harness session-status diagnosis in the ready-hold event

### Target specification files

- SPECIFICATION/contracts.md
- SPECIFICATION/scenarios.md

### Summary

When a ready hold's busy evidence rests solely on a harness session-status value of busy or shell while the same evaluation's pane capture shows an idle composer with no spinner and no background-wait line, the ready-hold event MUST say so explicitly, so an operator can tell a stuck harness status from real work. The diagnosis uses only what the evaluation already observed and is report-only: the session-status evidence continues to withhold the restart exactly as today.

### Motivation

Work item overseer-qz7ez7. A held `ready` track whose only busy evidence is the harness session-status reads, in a bare hold event, the same as a session that is genuinely working. The 2026-11-05 incident (fleet daemon v5.52.1, livespec-orchestrator-beads-fabro::kubernetes-sandbox-backend held 15+ minutes while visibly idle) is exactly the case where the pane and the harness status disagree, and the operator needs that disagreement stated rather than inferred. Amended after independent ratification reviews. Builds on the 'Bounded ready-hold event' proposal in this file.

### Proposed Changes

Observability-only; the restart gates and the evaluation cascade are unchanged. In particular, spec.md §"Fail-soft posture" still resolves the disagreement toward withholding the restart, and recognized shell-only evidence still neither authorizes an act nor is overridden.

**1. contracts.md §"The restart interlock".** Append the following paragraph immediately after the "ready-hold event" paragraphs added by the 'Bounded ready-hold event' proposal:

> **Stuck-status diagnosis.** When a ready-hold event is emitted and, in the evaluation that emits it, (a) the `busy` holding condition rests SOLELY on the `session-status` source with a value of `busy` or `shell`, (b) the pane capture that evaluation already took shows an idle composer — the runtime's verified empty idle input state — and (c) that capture shows no spinner and no background-wait line, the event MUST state explicitly that the harness session-status disagrees with an idle pane, naming the status value and stating that no spinner and no background wait is visible, so an operator can distinguish a possibly stuck harness status from real work. Where any of (a)–(c) does not hold, or was not observed by that evaluation, the event MUST NOT carry that statement; establishing (a)–(c) MUST NOT require any capture, delay, or keystroke beyond what the unchanged gates already perform. The diagnosis MUST NOT be treated as idle evidence, MUST NOT clear or downgrade the `busy` holding condition, and MUST NOT authorize or hasten a restart; the session-status evidence continues to withhold replacement exactly as before.

**2. scenarios.md.** Insert immediately after the scenarios added by the 'Bounded ready-hold event' proposal:

```
## Scenario: A ready hold resting only on a harness session-status is diagnosed as a possible stuck status

Given a track whose state file reads ready with a declaration that satisfies every restart-interlock precondition

And the harness reports the session's status as shell

And the pane shows an idle empty composer with no spinner and no background-wait line

When the hold has persisted for longer than the ready-hold window

Then the hold event names the holding condition busy with source session-status and value shell

And the event states explicitly that the harness session-status disagrees with an idle pane showing no spinner and no background wait

And the restart remains withheld exactly as it would be without the diagnosis

## Scenario: A ready hold with visible busy evidence is not diagnosed as a stuck status

Given a track whose state file reads ready with a declaration that satisfies every restart-interlock precondition

And the harness reports the session's status as busy

And the pane shows a spinner

When the hold has persisted for longer than the ready-hold window

Then the hold event names busy with both its spinner and session-status sources

And the event does not state that the harness session-status disagrees with the pane
```

**3.** **tests/heading-coverage.json** (outside the spec target; co-edited atomically by the revise that ratifies this proposal). Each new scenario heading above MUST receive a registry entry (`"test": "TODO"` until an integration-tier pinning test lands), per non-functional-requirements.md §"Scenarios".

## Proposal: Latched wrap-up names the latch and the live context reading

### Target specification files

- SPECIFICATION/spec.md
- SPECIFICATION/contracts.md
- SPECIFICATION/scenarios.md

### Summary

A wrap-up injection delivered to a context-compaction-latched track MUST name the latch in its context figure, in the form `ctx latched to <latched>%; live <live>%`. `<latched>` is the track's wind-down threshold, the band ceiling the latch applies. `<live>` is the daemon's current effective remaining-context reading, which for an unreadable statusline is the kept last-known value per spec.md §"Fail-soft posture". The word `unknown` appears only when the daemon holds no effective reading at all. Band selection is unchanged: it still uses min(effective reading, threshold), so a genuinely lower live figure still selects the sharper band. Only the message wording changes.

### Motivation

Work item overseer-qz7ez7. A compaction-latched track's wrap-up currently reads "ctx 50%" while the pane shows 86%, because the latch floors the band-selection figure to the track's threshold (spec.md §"The context-compaction latch"; `injection_ctx` returns min(eff_ctx, threshold) in `overseer/_supervisor_compaction.py`). That floor is correct, but presenting it as the session's live reading contradicts what the session sees and makes the wrap-up read as wrong. contracts.md §"The wrap-up injection" already obliges every wrap-up to name the live remaining-context percentage; a latched wrap-up does not truthfully meet that obligation today. The `unknown` case is reachable, which was checked in the code: `effective_ctx` in `overseer/_supervisor_observe.py` returns None when no reading has been observed since the daemon started (the latch is durable across daemon restarts, while the last-known value is in memory) or when the last-known value is older than the staleness window (spec.md §"Fail-soft posture", "Remaining-context knowledge itself ages"); `_supervisor_threshold.threshold` then substitutes the threshold before `maybe_inject`, and a latched track owes the wrap-up at any reading. Amended twice after independent ratification reviews.

### Proposed Changes

Wording-only. The latch's trigger, band selection (which uses the lower of the effective reading and the threshold, treating the track as at its threshold unless genuinely lower), band re-arming, the last-known-value rule of spec.md §"Fail-soft posture", and every paste and restart gate are unchanged.

**1. contracts.md §"The wrap-up injection", "Message obligations" bullet.** After the sentence ending "...and states truthfully that only a `ready` declaration restarts the session.", insert:

> For a track carrying a context-compaction latch (spec.md §"The context-compaction latch"), the wrap-up MUST NOT present a single bare remaining-context percentage. It MUST name the latch together with two figures in the form `ctx latched to <latched>%; live <live>%` (for example `ctx latched to 50%; live 86%`):
>
> - `<latched>` is the track's wind-down THRESHOLD — the per-track override when set, else the daemon-wide default — which is the band ceiling the latch applies. It MUST be the threshold whether the live reading is above or below it. It is NOT the band-selection figure, which remains the lower of the effective reading and the threshold and is unaffected by this wording.
> - `<live>` is the daemon's current EFFECTIVE remaining-context reading for the session: the reading parsed from the current capture, else the last known value kept under spec.md §"Fail-soft posture" while it has not aged past the staleness window. An unreadable statusline therefore shows the kept last-known value, not `unknown`.
>
> Only when the daemon holds NO effective reading — none observed for the session since the daemon started, or the last known value aged past the staleness window — MUST the wrap-up read `ctx latched to <latched>%; live unknown`, and it MUST NOT substitute the threshold or any other figure for the live reading. A wrap-up for a track carrying no latch keeps its existing ctx wording unchanged.

**2. spec.md §"The context-compaction latch".** Replace the bullet beginning "every wrap-up delivered under the latch MUST state that a context compaction was detected" with:

> - every wrap-up delivered under the latch MUST state that a context compaction was detected and that a restart is required regardless of the remaining context the session sees, and MUST name the latch in its context figure — the track's wind-down threshold and the daemon's effective live reading together, per contracts.md §"The wrap-up injection" — never a single bare ctx percentage;

**3. scenarios.md.** Insert immediately after `## Scenario: A latched round is never closed as recovered`:

```
## Scenario: A latched track's wrap-up names the latch and the live context reading

Given a track carrying a context-compaction latch whose wind-down threshold is 50%

And the pane's live remaining context reads 86%

When the daemon delivers a wrap-up to the track under the latch

Then the wrap-up's context figure reads ctx latched to 50%; live 86%

And the wrap-up does not present 50% as a bare remaining-context percentage

And the wrap-up still states that a context compaction was detected and a restart is required

## Scenario: A latched track below its threshold names the threshold and keeps its sharper band

Given a track carrying a context-compaction latch whose wind-down threshold is 50%

And the pane's live remaining context reads 30%

When the daemon delivers a wrap-up to the track under the latch

Then the wrap-up's context figure reads ctx latched to 50%; live 30%

And the escalation band is selected by the 30% figure exactly as without this wording, so the insistent 30% band applies

## Scenario: A latched track with an unreadable statusline names its kept last-known reading

Given a track carrying a context-compaction latch whose wind-down threshold is 50%

And the daemon last read 72% remaining for the session within the staleness window

And the current capture's statusline is unreadable

When the daemon delivers a wrap-up to the track under the latch

Then the wrap-up's context figure reads ctx latched to 50%; live 72%

## Scenario: A latched track with no effective reading says live unknown

Given a track carrying a durable context-compaction latch whose wind-down threshold is 50%

And the daemon has observed no remaining-context reading for the session since it started

When the daemon delivers a wrap-up to the track under the latch

Then the wrap-up's context figure reads ctx latched to 50%; live unknown

And the threshold is not presented as the live reading

## Scenario: An unlatched track's wrap-up keeps its bare live context figure

Given a track carrying no context-compaction latch at 40% remaining context

When the daemon delivers a wrap-up to the track

Then the wrap-up names the live remaining context as 40% without any latch wording
```

**4.** **tests/heading-coverage.json** (outside the spec target; co-edited atomically by the revise that ratifies this proposal). Each new scenario heading above MUST receive a registry entry (`"test": "TODO"` until an integration-tier pinning test lands), per non-functional-requirements.md §"Scenarios".
