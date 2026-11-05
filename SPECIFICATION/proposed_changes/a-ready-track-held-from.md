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

A READY HOLD is defined by observable state: a track whose state-file token is exactly `ready`, whose declaration is certifiable under preconditions 1–5 of the restart interlock, and for which the supervising loop's evaluation withholds replacement because at least one of four live-pane conditions holds (busy with its source, not-idle, unsettled, pane-identity). When a ready hold persists past the named ready-hold window (`--ready-hold-window-seconds`, default 600), the daemon MUST log one daemon-log event naming the track and every holding condition the evaluation actually observed, repeated at most once per further window. A `ready` failing any interlock precondition is never a hold. The change is observability-only: no restart gate, interlock precondition, cascade order, or authorization changes, and restart suppression stays unbounded.

### Motivation

Work item overseer-qz7ez7. On 2026-11-05 the fleet daemon v5.52.1 held a `ready`, idle track (livespec-orchestrator-beads-fabro::kubernetes-sandbox-backend) from replacement for more than 15 minutes and logged no event at all, because the busy, not-idle, unsettled and pane-identity holds are silent. Those gates sit UPSTREAM of the `request.ready` leg in the evaluation cascade (`_supervisor_evaluate.py`, `_supervisor_evaluate_active.py`, `_supervisor_evaluate_idle.py`), so the hold is defined here by observable state rather than by cascade position. The spec already bounds ATTENTION for withheld rounds (spec.md §"Fail-soft posture") and immediately surfaces a determined precondition-4 identity mismatch (contracts.md §"The restart interlock"), but nothing reports a certifiable `ready` held by the live-pane conditions. Amended after an independent ratification review (blockers: hold definition by observable state; nits: channel, window name, unbounded-suppression wording). In-flight survey: no open spec-touching PR; five `spec/*` branches (caam-capacity-aware-rotation, daemon-message-channel-delivery, ratify-launch-profile-launch-model, revise-three-proposals-v033, sanctioned-out-of-band-seat), none of which edits the restart branch's acting gates; this proposal aligns with all of them.

### Proposed Changes

Observability-only. Every existing restart and interlock gate, and the order of the evaluation cascade, stays exactly as it is; nothing below authorizes, suppresses, accelerates or delays a replacement. RESTART suppression for busy, changing and ambiguous evidence remains UNBOUNDED under spec.md §"Fail-soft posture"; this proposal bounds only how long such a hold may go UNREPORTED.

**1. contracts.md §"The restart interlock".** Insert the following paragraphs immediately after the paragraph ending "...a positive identity check that the pane really is this track's supervised session in this track's repository." (and before the paragraph beginning "A standing `ready` held by precondition 4..."):

> **The ready-hold event.** A READY HOLD is a track whose state-file token is exactly `ready`, whose declaration satisfies preconditions 1–5 of this interlock (certifiable), and for which the daemon withholds replacement in the supervising loop's evaluation because at least one of the four live-pane conditions below holds. A hold is defined by that observable state, never by the position in the evaluation cascade at which the withholding occurs. The four HOLDING CONDITIONS are exactly:
>
> - `busy`, carrying each SOURCE observed: `spinner` (a generating or sub-agent-busy marker in the pane), `background-wait` (a background-shell or background-wait line in the pane, or the runtime's descendant-shell evidence), or `session-status` (the harness-reported session status, carrying its value, e.g. `busy` or `shell`);
> - `not-idle` (no verified empty idle input state);
> - `unsettled` (the two settle captures differ);
> - `pane-identity` (the positive identity check that the pane is this track's supervised session in this track's repository fails or cannot be established).
>
> A `ready` that fails ANY of preconditions 1–5 is NEVER a ready hold, even when the pane also shows one or more of the four conditions. It remains governed by its own attention memberships, including the immediate surfacing of a determined precondition-4 mismatch below, and MUST NOT emit this event.
>
> The READY-HOLD WINDOW is a named bound, `ready_hold_window`, configured by the `overseerd` launch option `--ready-hold-window-seconds <N>`, where N MUST be a strictly positive integer and the default is 600 (10 minutes). The daemon's supervising loop (never a read-only listing surface) MUST measure a ready hold from the first evaluation that observes it, continuously while every evaluation of the track observes it; the hold ends when replacement proceeds, when the track is no longer a ready hold (the token is no longer `ready`, the declaration stops certifying, or no holding condition is observed), or when the declaration's modification time changes. A change in WHICH holding conditions are observed does not end the hold. The measurement MAY be held in memory: a daemon restart restarts the measurement, which can delay the event but MUST NOT suppress it.
>
> When a ready hold has persisted for longer than the ready-hold window, the daemon MUST log ONE event for the track to the daemon's event log — the same channel spec.md §"Notify, never block" and §"Session-name derivation" use for the `unidentified-session` event — and NOT as an attention or alert line. A certifiable `ready` held by live-pane evidence is the cardinal rule working as designed rather than a condition waiting on a human, so raising it as an attention alert would report ordinary long-running work as needing a person; the event exists so that an operator investigating a long hold can find its cause in the log. The event MUST nonetheless be self-sufficient as §"Notify, never block" requires of track-scoped alerts: it names the plan topic, the repository, the session and pane, and a copy-pasteable jump command, together with the declaration's age, the hold's age quantized to the window boundary just crossed, and EVERY holding condition the evaluation that emits it ACTUALLY observed — never a single presumed cause — each `busy` condition with every source observed and, for `session-status`, its value. Observing a holding condition MUST NOT require any capture, delay, or keystroke beyond what the unchanged gates already perform; a condition the evaluation did not reach is not named.
>
> While the same hold persists, the event MUST be re-emitted at most once per further ready-hold window (at most once on crossing each multiple of the window), and MUST NOT be emitted once per cycle. Its dedup identity is the ready HOLD for the track, not the individual holding condition: a change of holding condition alone MUST NOT re-emit it ahead of the next window boundary, and the next emission names the conditions then observed. This intentionally departs from §"Notify, never block"'s per-condition re-arm ("each condition re-arms when THAT condition clears"): busy evidence on a working session routinely alternates between sources and between busy and unsettled from one cycle to the next, and per-condition re-arming would turn one hold into a stream of entries. The measurement and the per-window allowance re-arm only when the hold ends.
>
> The ready-hold event is REPORT-ONLY. It MUST NOT authorize or suppress an injection, keystroke, command termination, declaration write, declaration voiding, or restart, and MUST NOT alter any interlock precondition or live-pane gate. It MUST NOT be evaluated in a position that prevents any branch of the evaluation cascade from being reached or alters which branch is selected. A failure to write the event is a storage error on the overseer's own files under spec.md §"Fail-soft posture": it is reported and survived, and it MUST NOT change the track's restart decision.

**2. spec.md §"The restart".** Replace the paragraph beginning "A session that declares `ready` and then resumes work" with the same paragraph followed by one added sentence, so it reads:

> A session that declares `ready` and then resumes work — narrates further, emits more turns, streams stop-hook output — keeps its declaration armed; the restart branch's settle and busy gates prevent a kill mid-work without requiring any activity-based clearing. The declaration is cleared only by a successful restart or by exceeding its bounded maximum age (per contracts.md §"The state file", its "Stale-declaration voiding" rule). Withholding the restart of such a ready hold remains unbounded under §"Fail-soft posture", but the daemon MUST NOT leave such a hold unreported past the ready-hold window: a certifiable `ready` withheld by the busy, not-idle, unsettled or pane-identity condition for longer than that window MUST produce a report-only daemon-log event naming the track and every holding condition observed, repeated at most once per window while the hold persists (per contracts.md §"The restart interlock", its "ready-hold event" rule); the event changes no gate and authorizes nothing.

**3. scenarios.md.** Insert immediately after `## Scenario: A ready declaration remains armed when its session resumes work`:

```
## Scenario: A ready track held from replacement past the hold window logs a hold event

Given a track whose state file reads ready with a declaration that satisfies every restart-interlock precondition

And the supervising loop's evaluation withholds replacement because the pane is unsettled

When the hold has persisted for longer than the ready-hold window

Then the daemon logs one event to its event log naming the track's plan topic, repository, session, pane and jump command

And the event names the holding condition unsettled, the declaration's age, and the hold's age at the window boundary crossed

And no attention or alert line is raised for the hold

And no restart, keystroke, paste, declaration write or declaration voiding occurs on account of the event

And the evaluation selects exactly the branch it would select without the event

## Scenario: A persisting ready hold is re-reported at most once per hold window

Given a ready hold that has already logged its hold event

When the hold persists through further supervision cycles within the same ready-hold window, its holding condition changing from busy to unsettled

Then no further hold event is logged for the track

When the hold persists past the next multiple of the ready-hold window

Then exactly one further hold event is logged, naming the holding conditions observed in that evaluation

When the state file no longer reads ready

Then the hold ends and a later ready hold measures its window afresh

## Scenario: A busy hold names the source of its busy evidence

Given a track whose state file reads ready with a declaration that satisfies every restart-interlock precondition

And the supervising loop's evaluation withholds replacement because a background-wait line is visible in the pane

When the hold has persisted for longer than the ready-hold window

Then the hold event names the holding condition busy with source background-wait

## Scenario: An uncertifiable ready on a busy pane is never a ready hold

Given a track whose standing ready declaration fails a restart-interlock precondition

And the pane shows a spinner

When the declaration stands past the ready-hold window

Then the daemon logs no ready-hold event for the track

And the declaration is surfaced only through the certification failure's own attention membership

## Scenario: The ready-hold window is configured at daemon launch

Given the daemon launched with --ready-hold-window-seconds 120

And a track in a ready hold

When the hold has persisted for longer than 120 seconds

Then the daemon logs the hold event

And a daemon launched without the option uses a ready-hold window of 600 seconds
```

**4.** **tests/heading-coverage.json** (outside the spec target; co-edited atomically by the revise that ratifies this proposal). Each new scenario heading above MUST receive a registry entry (`"test": "TODO"` until an integration-tier pinning test lands), per non-functional-requirements.md §"Scenarios".

## Proposal: Stuck harness session-status diagnosis in the ready-hold event

### Target specification files

- SPECIFICATION/contracts.md
- SPECIFICATION/scenarios.md

### Summary

When a ready hold's busy evidence rests solely on a harness session-status value of busy or shell while the same evaluation's pane capture shows an idle composer with no spinner and no background-wait line, the ready-hold event MUST say so explicitly, so an operator can tell a stuck harness status from real work. The diagnosis uses only what the evaluation already observed and is report-only: the session-status evidence continues to withhold the restart exactly as today.

### Motivation

Work item overseer-qz7ez7. A held `ready` track whose only busy evidence is the harness session-status reads, in a bare hold event, the same as a session that is genuinely working. The 2026-11-05 incident (fleet daemon v5.52.1, livespec-orchestrator-beads-fabro::kubernetes-sandbox-backend held 15+ minutes while visibly idle) is exactly the case where the pane and the harness status disagree, and the operator needs that disagreement stated rather than inferred. Builds on the 'Bounded ready-hold event' proposal in this file.

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

A wrap-up injection delivered to a context-compaction-latched track MUST name the latch in its context figure, in the form `ctx latched to <latched>%; live <live>%`, where `<latched>` is the track's wind-down threshold (the band ceiling the latch applies) and `<live>` is the live remaining-context reading or the word `unknown`. Band selection is unchanged: it still uses min(live, threshold), so a genuinely lower live figure still selects the sharper band. Only the message wording changes.

### Motivation

Work item overseer-qz7ez7. A compaction-latched track's wrap-up currently reads "ctx 50%" while the pane shows 86%, because the latch floors the band-selection figure to the track's threshold (spec.md §"The context-compaction latch"; `injection_ctx` returns min(live, threshold) in `overseer/_supervisor_compaction.py`). That floor is correct, but presenting it as the session's live reading contradicts what the session sees and makes the wrap-up read as wrong. contracts.md §"The wrap-up injection" already obliges every wrap-up to name the live remaining-context percentage; a latched wrap-up does not truthfully meet that obligation today. Amended after an independent ratification review (blocker: define the latched figure as the threshold, not as the band-selection value; nit: cover the unknown live reading).

### Proposed Changes

Wording-only. The latch's trigger, band selection (which uses min(live, threshold), treating the track as at its threshold unless genuinely lower), band re-arming, and every paste and restart gate are unchanged.

**1. contracts.md §"The wrap-up injection", "Message obligations" bullet.** After the sentence ending "...and states truthfully that only a `ready` declaration restarts the session.", insert:

> For a track carrying a context-compaction latch (spec.md §"The context-compaction latch"), the wrap-up MUST NOT present a single bare remaining-context percentage. It MUST name the latch together with two figures in the form `ctx latched to <latched>%; live <live>%`, where `<latched>` is the track's wind-down THRESHOLD — the band ceiling the latch applies, per-track override when set, else the daemon-wide default — and `<live>` is the live remaining-context reading (for example `ctx latched to 50%; live 86%`). `<latched>` MUST be the threshold whether the live reading is above or below it; it is NOT the band-selection figure, which remains the lower of the live reading and the threshold and is unaffected by this wording. Where the live reading is unknown, the wrap-up MUST read `ctx latched to <latched>%; live unknown` and MUST NOT substitute any other figure for the live reading. A wrap-up for a track carrying no latch keeps its existing ctx wording unchanged.

**2. spec.md §"The context-compaction latch".** Replace the bullet beginning "every wrap-up delivered under the latch MUST state that a context compaction was detected" with:

> - every wrap-up delivered under the latch MUST state that a context compaction was detected and that a restart is required regardless of the remaining context the session sees, and MUST name the latch in its context figure — the track's wind-down threshold and the live reading together, per contracts.md §"The wrap-up injection" — never a single bare ctx percentage;

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

## Scenario: A latched track with an unknown live reading says so

Given a track carrying a context-compaction latch whose wind-down threshold is 50%

And the pane's live remaining-context reading is unknown

When the daemon delivers a wrap-up to the track under the latch

Then the wrap-up's context figure reads ctx latched to 50%; live unknown

And no other figure is presented as the live reading

## Scenario: An unlatched track's wrap-up keeps its bare live context figure

Given a track carrying no context-compaction latch at 40% remaining context

When the daemon delivers a wrap-up to the track

Then the wrap-up names the live remaining context as 40% without any latch wording
```

**4.** **tests/heading-coverage.json** (outside the spec target; co-edited atomically by the revise that ratifies this proposal). Each new scenario heading above MUST receive a registry entry (`"test": "TODO"` until an integration-tier pinning test lands), per non-functional-requirements.md §"Scenarios".
