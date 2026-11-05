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

When a track's state file reads `ready` and the restart branch withholds replacement on one of its live-pane gates (busy, not-idle, unsettled, or pane-identity mismatch) for longer than a named, configurable ready-hold window (default 10 minutes), the daemon MUST log one self-sufficient event naming the track and every holding condition, busy with its source, and MUST repeat it at most once per further window while the hold persists. The change is observability-only: no restart gate, interlock precondition, or authorization changes.

### Motivation

Work item overseer-qz7ez7. On 2026-11-05 the fleet daemon v5.52.1 held a `ready`, idle track (livespec-orchestrator-beads-fabro::kubernetes-sandbox-backend) from replacement for more than 15 minutes and logged no event at all, because the restart branch's busy, not-idle, unsettled and pane-identity holds are silent. An operator watching the daemon cannot distinguish a correctly withheld restart from a wedged one. The spec already bounds ATTENTION for withheld rounds (spec.md §"Fail-soft posture") and immediately surfaces a precondition-4 identity mismatch (contracts.md §"The restart interlock"), but nothing bounds the silence of a certifiable `ready` held by the acting gates. In-flight survey: no open spec-touching PR; five `spec/*` branches (caam-capacity-aware-rotation, daemon-message-channel-delivery, ratify-launch-profile-launch-model, revise-three-proposals-v033, sanctioned-out-of-band-seat), none of which edits the restart branch's acting gates; this proposal aligns with all of them.

### Proposed Changes

Observability-only. Every existing restart and interlock gate stays exactly as it is; nothing below authorizes, suppresses, accelerates or delays a replacement.

**1. contracts.md §"The restart interlock".** Insert the following paragraphs immediately after the paragraph ending "...a positive identity check that the pane really is this track's supervised session in this track's repository." (and before the paragraph beginning "A standing `ready` held by precondition 4..."):

> **The ready-hold event.** A READY HOLD is the condition in which the state file's token is exactly `ready`, the restart branch is reached, and replacement is withheld by one or more of the acting gates above. Its HOLDING CONDITIONS are exactly these four:
>
> - `busy`, carrying its SOURCE: `spinner` (a generating or sub-agent-busy marker in the pane), `background-wait` (a background-shell or background-wait line in the pane, or the runtime's descendant-shell evidence), or `session-status` (the harness-reported session status, carrying its value, e.g. `busy` or `shell`);
> - `not-idle` (no verified empty idle input state);
> - `unsettled` (the two settle captures differ);
> - `pane-identity` (the positive identity check that the pane is this track's supervised session in this track's repository fails or cannot be established).
>
> A certification failure under preconditions 1–5 is NOT a ready hold: it remains governed by its own attention memberships, including the immediate surfacing of a determined precondition-4 mismatch below, and MUST NOT additionally emit this event.
>
> The daemon MUST define a READY-HOLD WINDOW: a named bound, configurable at daemon launch, whose default MUST be 10 minutes and which MUST be strictly positive. The daemon's supervising loop (never a read-only listing surface) MUST measure a ready hold from the first observation in which it holds, continuously while every observation of the track finds it holding; the hold ends when replacement proceeds, when the state file no longer reads `ready` (restart, expiry, session clear, or any other change of token), or when the declaration's modification time changes. A change in WHICH holding conditions apply does not end the hold. The measurement MAY be held in memory: a daemon restart restarts the measurement, which can delay the event but MUST NOT suppress it.
>
> When a ready hold has persisted for longer than the ready-hold window, the daemon MUST log ONE event for the track. The event MUST name the track with the self-sufficient coordinates of spec.md §"Notify, never block" (plan topic, repository, session, pane, and jump command), the declaration's age, the hold's age quantized to the window boundary just crossed, and EVERY holding condition observed in the evaluation that emits it — never a single presumed cause — each `busy` condition with its source and, for `session-status`, its value. While the same hold persists, the event MUST be re-emitted at most once per further ready-hold window (at most once on crossing each multiple of the window); it MUST NOT be emitted once per cycle. Its dedup identity is the ready hold for the track, so a change of holding condition alone MUST NOT re-emit it ahead of the next window boundary; the next emission names the conditions then holding. The measurement and the per-window allowance re-arm when the hold ends.
>
> The ready-hold event is REPORT-ONLY. It MUST NOT authorize or suppress an injection, keystroke, command termination, declaration write, declaration voiding, or restart; MUST NOT alter any interlock precondition or acting gate; and MUST NOT be evaluated in a position that prevents the restart branch, or any other branch, from being reached. A failure to write the event is a storage error on the overseer's own files under spec.md §"Fail-soft posture": it is reported and survived, and it MUST NOT change the track's restart decision.

**2. spec.md §"The restart".** Replace the paragraph beginning "A session that declares `ready` and then resumes work" with the same paragraph followed by one added sentence, so it reads:

> A session that declares `ready` and then resumes work — narrates further, emits more turns, streams stop-hook output — keeps its declaration armed; the restart branch's settle and busy gates prevent a kill mid-work without requiring any activity-based clearing. The declaration is cleared only by a successful restart or by exceeding its bounded maximum age (per contracts.md §"The state file", its "Stale-declaration voiding" rule). Those gates MUST NOT hold a `ready` silently without bound: a `ready` withheld from replacement by the busy, not-idle, unsettled or pane-identity gate for longer than the bounded ready-hold window MUST produce a report-only event naming the track and every holding condition, repeated at most once per window while the hold persists (per contracts.md §"The restart interlock", its "ready-hold event" rule); the event changes no gate and authorizes nothing.

**3. scenarios.md.** Insert immediately after `## Scenario: A ready declaration remains armed when its session resumes work`:

```
## Scenario: A ready track held from replacement past the hold window logs a hold event

Given a track whose state file reads ready with a certifiable declaration

And the restart branch withholds replacement because the pane is unsettled

When the hold has persisted for longer than the ready-hold window

Then the daemon logs one event naming the track's plan topic, repository, session, pane and jump command

And the event names the holding condition unsettled, the declaration's age, and the hold's age at the window boundary crossed

And no restart, keystroke, paste, declaration write or declaration voiding occurs on account of the event

And every restart gate evaluates exactly as it would without the event

## Scenario: A persisting ready hold is re-reported at most once per hold window

Given a ready hold that has already logged its hold event

When the hold persists through further supervision cycles within the same ready-hold window

Then no further hold event is logged for the track

When the hold persists past the next multiple of the ready-hold window

Then exactly one further hold event is logged, naming the holding conditions observed in that evaluation

When the state file no longer reads ready

Then the hold ends and a later ready hold measures its window afresh

## Scenario: A busy hold names the source of its busy evidence

Given a track whose state file reads ready with a certifiable declaration

And the restart branch withholds replacement because a background-wait line is visible in the pane

When the hold has persisted for longer than the ready-hold window

Then the hold event names the holding condition busy with source background-wait

## Scenario: A certification failure does not emit a ready-hold event

Given a track whose standing ready declaration fails a restart-interlock precondition

When the declaration stands past the ready-hold window

Then the daemon logs no ready-hold event for the track

And the declaration is surfaced only through the certification failure's own attention membership
```

**4. tests/heading-coverage.json** (outside the spec target; co-edited atomically by the revise that ratifies this proposal). Each new scenario heading above MUST receive a registry entry (`"test": "TODO"` until an integration-tier pinning test lands), per non-functional-requirements.md §"Scenarios".

## Proposal: Stuck harness session-status diagnosis in the ready-hold event

### Target specification files

- SPECIFICATION/contracts.md
- SPECIFICATION/scenarios.md

### Summary

When a ready hold's busy evidence rests solely on a harness session-status value of busy or shell while the same evaluation's pane capture shows an idle composer with no spinner and no background-wait line, the ready-hold event MUST say so explicitly, so an operator can tell a stuck harness status from real work. The diagnosis is report-only: the session-status evidence continues to withhold the restart exactly as today.

### Motivation

Work item overseer-qz7ez7. A held `ready` track whose only busy evidence is the harness session-status reads, in a bare hold event, the same as a session that is genuinely working. The 2026-11-05 incident (fleet daemon v5.52.1, livespec-orchestrator-beads-fabro::kubernetes-sandbox-backend held 15+ minutes while visibly idle) is exactly the case where the pane and the harness status disagree, and the operator needs that disagreement stated rather than inferred. Builds on the 'Bounded ready-hold event' proposal in this file.

### Proposed Changes

Observability-only; the restart gates are unchanged. In particular, spec.md §"Fail-soft posture" still resolves the disagreement toward withholding the restart, and recognized shell-only evidence still neither authorizes an act nor is overridden.

**1. contracts.md §"The restart interlock".** Append the following paragraph immediately after the "ready-hold event" paragraphs added by the 'Bounded ready-hold event' proposal:

> **Stuck-status diagnosis.** When a ready-hold event is emitted and, in the evaluation that emits it, (a) the `busy` holding condition rests SOLELY on the `session-status` source with a value of `busy` or `shell`, (b) the pane capture shows an idle composer — the runtime's verified empty idle input state — and (c) the capture shows no spinner and no background-wait line, the event MUST state explicitly that the harness session-status disagrees with an idle pane, naming the status value and stating that no spinner and no background wait is visible, so an operator can distinguish a possibly stuck harness status from real work. Where any of (a)–(c) does not hold, the event MUST NOT carry that statement. The diagnosis MUST NOT be treated as idle evidence, MUST NOT clear or downgrade the `busy` holding condition, and MUST NOT authorize or hasten a restart; the session-status evidence continues to withhold replacement exactly as before.

**2. scenarios.md.** Insert immediately after the scenarios added by the 'Bounded ready-hold event' proposal:

```
## Scenario: A ready hold resting only on a harness session-status is diagnosed as a possible stuck status

Given a track whose state file reads ready with a certifiable declaration

And the harness reports the session's status as shell

And the pane shows an idle empty composer with no spinner and no background-wait line

When the hold has persisted for longer than the ready-hold window

Then the hold event names the holding condition busy with source session-status and value shell

And the event states explicitly that the harness session-status disagrees with an idle pane showing no spinner and no background wait

And the restart remains withheld exactly as it would be without the diagnosis

## Scenario: A ready hold with visible busy evidence is not diagnosed as a stuck status

Given a track whose state file reads ready with a certifiable declaration

And the harness reports the session's status as busy

And the pane shows a spinner

When the hold has persisted for longer than the ready-hold window

Then the hold event names busy with both its spinner and session-status sources

And the event does not state that the harness session-status disagrees with the pane
```

**3. tests/heading-coverage.json** (outside the spec target; co-edited atomically by the revise that ratifies this proposal). Each new scenario heading above MUST receive a registry entry (`"test": "TODO"` until an integration-tier pinning test lands).

## Proposal: Latched wrap-up names the latch and the live context reading

### Target specification files

- SPECIFICATION/spec.md
- SPECIFICATION/contracts.md
- SPECIFICATION/scenarios.md

### Summary

A wrap-up injection delivered to a context-compaction-latched track MUST name the latch in its context figure — for example "ctx latched to 50%; live 86%" — instead of presenting the substituted threshold value as a bare ctx percentage. Band selection, the trigger, and every gate are unchanged; only the message wording changes.

### Motivation

Work item overseer-qz7ez7. A compaction-latched track's wrap-up currently reads "ctx 50%" while the pane shows 86%, because the latch deliberately substitutes the threshold value for band selection (spec.md §"The context-compaction latch"). That substitution is correct, but presenting it as the session's live reading contradicts what the session sees and makes the wrap-up read as wrong. contracts.md §"The wrap-up injection" already obliges every wrap-up to name the live remaining-context percentage; a latched wrap-up does not truthfully meet that obligation today.

### Proposed Changes

Wording-only. The latch's trigger, band selection (treating the track as at its threshold unless genuinely lower), band re-arming, and every paste and restart gate are unchanged.

**1. contracts.md §"The wrap-up injection", "Message obligations" bullet.** After the sentence ending "...and states truthfully that only a `ready` declaration restarts the session.", insert:

> For a track carrying a context-compaction latch (spec.md §"The context-compaction latch"), the wrap-up MUST NOT present the latch's substituted band value as a bare remaining-context percentage. It MUST name the latch together with both figures — the latched value used for band selection and the live remaining-context reading — in the form `ctx latched to <latched>%; live <live>%` (for example `ctx latched to 50%; live 86%`). Where the live reading is unknown, the wrap-up MUST say `live unknown` in place of the live figure and MUST NOT substitute the latched value for it. A wrap-up for a track carrying no latch keeps its existing ctx wording unchanged.

**2. spec.md §"The context-compaction latch".** Replace the bullet beginning "every wrap-up delivered under the latch MUST state that a context compaction was detected" with:

> - every wrap-up delivered under the latch MUST state that a context compaction was detected and that a restart is required regardless of the remaining context the session sees, and MUST name the latch in its context figure — the latched band value and the live reading together, per contracts.md §"The wrap-up injection" — never the latched value presented as a bare ctx percentage;

**3. scenarios.md.** Insert immediately after `## Scenario: A latched round is never closed as recovered`:

```
## Scenario: A latched track's wrap-up names the latch and the live context reading

Given a track carrying a context-compaction latch whose threshold is 50%

And the pane's live remaining context reads 86%

When the daemon delivers a wrap-up to the track under the latch

Then the wrap-up's context figure reads ctx latched to 50%; live 86%

And the wrap-up does not present 50% as a bare remaining-context percentage

And the wrap-up still states that a context compaction was detected and a restart is required

## Scenario: An unlatched track's wrap-up keeps its bare live context figure

Given a track carrying no context-compaction latch at 40% remaining context

When the daemon delivers a wrap-up to the track

Then the wrap-up names the live remaining context as 40% without any latch wording
```

**4. tests/heading-coverage.json** (outside the spec target; co-edited atomically by the revise that ratifies this proposal). Each new scenario heading above MUST receive a registry entry (`"test": "TODO"` until an integration-tier pinning test lands).
