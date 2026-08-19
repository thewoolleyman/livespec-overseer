---
topic: acting-safety-third-keystroke-act
author: claude-opus-5-supervision-safety-thread
created_at: 2026-08-19T05:36:24Z
---

## Proposal: Enumerate the stalled-picker charter reminder as a third sanctioned keystroke-bearing act

### Target specification files

- SPECIFICATION/constraints.md
- SPECIFICATION/spec.md
- SPECIFICATION/scenarios.md

### Summary

SPECIFICATION/constraints.md §"Acting safety" states that gated and human-waiting panes MUST never be pasted into, and enumerates exactly two keystroke-bearing acts that may coexist with that suppression rule. A THIRD such act ships in the daemon and fires precisely on those two forbidden pane classes: _supervisor_picker_stall.apply_picker_stall promotes a track to picker-stalled only when its declared status is blocked:human (a human wait) AND obs.gate is true (a structured gate) AND the stall exceeds PICKER_STALL_AFTER, and then — for reserved supervisor topics only — calls _supervisor_nudge.nudge_charter_authorized_picker_stall, which bracketed-pastes a charter reminder into that pane. This proposal amends the ratified letter to enumerate that act as a third sanctioned keystroke-bearing act under its own complete independent predicate, and to reconcile the "exactly two" count and the blanket "gated, human-waiting ... MUST never be pasted into" wording with it.

### Motivation

Work-item overseer-um53 (P1, blocked, reason needs-human), the requirement carrier this plan thread's opening handoff names as its single next action. The divergence was found while working overseer-g6sy item (c) ("govern the picker-stall surface"), which is itself blocked behind this letter decision because (c) cannot be drafted honestly until the letter says whether a third keystroke-bearing act exists.

The finding was proved with the three-way control this repo requires before believing any detector, and re-verified independently against the tree on 2026-08-19:

1. SUSPECT — overseer/_supervisor_picker_stall.py:54-70 returns early unless status == "blocked:human", picker_open (which is literally obs.gate) is true, and stall_seconds >= _supervisor_config.PICKER_STALL_AFTER (30 * 60.0). Past that gate, when act is true and signals.topic_reserved_for_supervisor(topic=...) holds, it calls _supervisor_nudge.nudge_charter_authorized_picker_stall, whose body (overseer/_supervisor_nudge.py:136-153) calls sup.tmux.bracketed_paste on that pane and sets istate.picker_stall_nudged so it fires at most once per stall episode.
2. KNOWN-SANCTIONED COMPARATOR — the pair-stall nudge named in the constraint, whose ratified predicate in spec.md §"The keep-going nudge" requires that NEITHER session presents a human wait. That is the exact inverse precondition, so the picker-stall paste is definitively not that act; and it is not the wrap-up either, whose trigger is below-threshold context.
3. THE CONSTRAINT TEXT itself, which both says "exactly two" and lists gated and human-waiting panes among those that MUST never be pasted into.

All three agree, so this is not a misreading of one sentence. The act is deliberate and tested — overseer/test_supervisor_liveness_starvation.py::test_charter_authorized_picker_stall_gets_clause_nudge_without_answering_picker asserts exactly one paste into a picker-showing supervisor pane, asserts the charter clause text, and asserts NO "Enter", "1" or "2" keystrokes — so this is a SPEC GAP, not a code bug.

It matters beyond tidiness. "Acting safety" is among the most safety-relevant statements in the tree, and pasting into a structured gate is the specific hazard the tree already reasons about: signals.is_structured_gate exists to SUPPRESS injection so a paste is never typed into a numbered chooser, and overseer/_supervisor_restart.py:289 refuses to keystroke a freshly-restarted pane that is on a gate. An act that deliberately pastes into a gate is exactly the case that sentence was written to forbid, so the divergence sits on the safety-critical side.

### Proposed Changes

### The decision this proposal puts to the maintainer

Two dispositions close the divergence, and they are mutually exclusive:

- **(i) Ratify the act.** Amend `constraints.md` to enumerate a THIRD
  keystroke-bearing act under its own complete independent predicate, and
  reconcile both the "exactly two" count and the blanket
  "gated, human-waiting ... MUST never be pasted into" clause with it. Specify
  the act itself in `spec.md` and pin it with a scenario in `scenarios.md`.
- **(ii) Judge the act unsanctioned and remove it.** `constraints.md` is
  already correct as written; the implementation and its test retreat.

**This proposal drafts (i)**, because the act's deliberateness and its
dedicated negative assertions (no `Enter`, no selection keystroke) point that
way, and because the mechanism it implements — paste into a picker without
answering it — is precisely the pattern v020's delivery-routing floor already
prescribes for the foreman, so the fleet has the mechanism and it is simply
ungoverned.

**Accepting this proposal ratifies a third keystroke-bearing act into gated,
human-waiting panes. That is a maintainer-grade safety decision.** It was
deliberately not self-authorized by the session that found it or by the session
that filed this proposal, even though both hold delegated spec-revision
authority. Rejecting this proposal at `/livespec:revise` selects disposition
(ii), and the follow-up is then the removal of
`nudge_charter_authorized_picker_stall`, its call site in
`apply_picker_stall`, and its test.

### Change 1 — `SPECIFICATION/constraints.md`, section "Acting safety"

Replace the two sentences that enumerate the sanctioned acts and forbid the
pane classes. Current text:

    It may coexist with exactly two acts under their independent complete
    predicates: the low-context wrap-up in contracts.md §"The wrap-up
    injection", and the bounded pair-stall nudge in spec.md §"The keep-going
    nudge". The shell is left running and neither paste authorizes a restart.
    Generating, changing, sub-agent-busy, gated, human-waiting, foreign,
    bare-shell, and ambiguous panes MUST never be pasted into.

Proposed text:

    It may coexist with exactly three acts under their independent complete
    predicates: the low-context wrap-up in contracts.md §"The wrap-up
    injection", the bounded pair-stall nudge in spec.md §"The keep-going
    nudge", and the bounded charter-reminder paste into a stalled supervisor
    picker in spec.md §"The stalled-picker charter reminder". The shell is left
    running and NO such paste authorizes a restart. Generating, changing,
    sub-agent-busy, foreign, bare-shell, and ambiguous panes MUST never be
    pasted into. Gated and human-waiting panes MUST never be pasted into
    EXCEPT by the stalled-picker charter reminder under its own complete
    predicate, which is the ONLY sanctioned exception and MUST NOT be widened
    to any other act, pane class, or topic class.

The clause "The foreman MUST NOT widen its own authority on the basis of any
evidence it produced itself" already sits in this section and is unchanged; the
new "MUST NOT be widened" clause is its analogue for this exception.

### Change 2 — `SPECIFICATION/spec.md`, new section "The stalled-picker charter reminder"

Add one section stating the act's complete independent predicate. Every clause
below is a boundary the shipped implementation already holds, so ratifying (i)
requires no behavior change:

- The act applies to a RESERVED SUPERVISOR topic only, never to a worker track.
- The target pane is positively identified as that track's supervised session.
- The session's declared status is `blocked:human`.
- Live gate evidence shows an OPEN structured picker. Whether a runtime can
  raise a structured question MUST continue to be derived from live gate
  evidence, never inferred from a runtime name, launch mode, or policy, per the
  existing rule in §"The state file".
- The stall has continuously exceeded a bounded floor, thirty minutes by
  default, measured on the human-blocked stall clock.
- The paste fires at most ONCE per stall episode. The once-per-episode bound is
  held in the track's in-memory inject state; a daemon restart re-arms it, which
  only ever DELAYS a reminder — the safe direction, matching the keep-going
  nudge's continuous-idle clock.
- The payload is delivered as ONE atomic paste and is NEVER SUBMITTED: the
  daemon sends no `Enter`, no selection keystroke, and no digit. The daemon
  does not choose from a picker and MUST NOT answer one. This is the single
  property that separates this act from every other keystroke-bearing act,
  each of which pastes AND submits.
- The message states only that the supervisor should re-read its own pending
  picker, perform charter-authorized mechanical unblocks itself, and declare
  `blocked: <reason>` only when the unblock genuinely requires a human decision.
- The act AUTHORIZES NOTHING. It never restarts, never closes or re-opens a
  round, never raises or lowers a certification floor, and never answers the
  picker on the session's behalf.
- A failed paste is surfaced to the operator and does not mark the episode
  handled, matching the existing failed-paste posture of the wrap-up and the
  keep-going nudge.
- Ambiguous evidence — an unreadable gate reading, an unresolved pane, an
  unsettled capture — resolves to inaction, per the general rule.

The section MUST also state, explicitly, that this act is the sanctioned
exception named in constraints.md §"Acting safety", so a reader arriving from
either document finds the other.

### Change 3 — `SPECIFICATION/scenarios.md`, one pinning scenario

Add a scenario that pins the two properties a regression would break, written
status-adversarially so a status-keyed implementation cannot satisfy it by
accident:

    Given a tracked SUPERVISOR-topic session whose declared status is
      blocked:human
    And whose live gate evidence shows an open structured picker
    And whose human-blocked stall has continuously exceeded the bounded floor
    When the daemon acts on that track
    Then exactly one charter-reminder payload is pasted into that pane
    And no Enter, digit, or other selection keystroke is sent to it
    And no restart is authorized by that paste
    And a second observation within the same stall episode pastes nothing further

A companion negative scenario pins the topic bound:

    Given a tracked WORKER-topic session in the identical stalled-picker state
    When the daemon acts on that track
    Then nothing is pasted into that pane

### What this proposal does NOT change

- The cardinal rule in `overseer/marker-protocol.md` is untouched. This concerns
  an informational paste only; the amended constraint text continues to state
  that no sanctioned paste authorizes a restart.
- The restart-path keystrokes (the resume line submitted into a
  freshly-respawned pane) are not in scope and are governed separately by
  §"The restart" and the restart interlock.
- Governing the "picker-stall surface" and "picker-stall status" vocabulary
  that v020 references but never defines is deliberately left to its existing
  carrier, work-item `overseer-g6sy` item (c), which unblocks once this letter
  question is settled in either direction.

## Proposal: Make the acting-safety act enumeration name each act instead of citing a two-act section

### Target specification files

- SPECIFICATION/constraints.md

### Summary

The same enumeration in constraints.md §"Acting safety" identifies its second sanctioned act as "the bounded pair-stall nudge in spec.md §'The keep-going nudge'", but that spec section specifies TWO distinct keystroke-bearing acts with different predicates — the idle-with-context-left keep-going nudge aimed at a single session, and the pair-stall nudge aimed at the supervisor of a stalled pair. A reader cannot tell from the constraint whether the reference names one act or covers the whole section, so the closed count "exactly two" is not decidable from the ratified text. This proposal makes the enumeration name each act unambiguously rather than leaning on a section reference.

### Motivation

Found while drafting the amendment in the companion proposal above, which necessarily rewrites this exact enumeration. Correcting the count from two to three without resolving this ambiguity would bake a new arithmetic error into a safety-critical sentence, so the two findings belong in the same proposed change even though they are independently acceptable.

Measured from the tree on 2026-08-19 rather than from any document's list, per this repo's standing rule that a LIST in an authoritative doc may not be assumed complete. The daemon's keystroke-bearing acts against a live supervised pane, enumerated from every _supervisor_launch.submit_prompt and tmux.bracketed_paste call site in overseer/:

- _supervisor_restart.maybe_inject — the low-context wrap-up. Named in the constraint.
- _supervisor_threshold.maybe_send_expiry_notice — the ready-expiry notice. NOT a separate act: spec.md §"The escalating wrap-up" states it "is subject to the complete guarded-paste predicate that governs a wrap-up" and calls it "a bounded companion to the escalation", so it correctly needs no enumeration entry of its own. Naming that explicitly is worthwhile because a reader auditing the count from the code will otherwise find it and mistake it for a fourth act.
- _supervisor_nudge.nudge_idle_with_context — the idle-with-context-left keep-going nudge, with its own complete predicate (continuously idle at least one hour, above threshold, not waiting on a human, no declaration of its own, once per idle episode). This is the act whose enumeration status is ambiguous.
- _supervisor_pair_stall._try_pair_nudge — the bounded pair-stall nudge. Named in the constraint.
- _supervisor_nudge.nudge_charter_authorized_picker_stall — the unenumerated third act, the subject of the companion proposal.

Restart-path keystrokes (_supervisor_restart._do_claude_restart, _supervisor_recovery.do_launch) submit a resume line into a freshly-respawned pane and are governed separately by §"The restart"; they are correctly outside this enumeration.

### Proposed Changes

### The ambiguity, precisely

`spec.md` §"The keep-going nudge" opens by specifying the
idle-with-context-left nudge, and then says "One further nudge exists, and it
is aimed at the PAIR", specifying the pair-stall nudge. Two acts, one section,
different predicates — the idle nudge requires the session to be above its
threshold and continuously idle for an hour; the pair-stall nudge requires
BOTH members of a pair to show no observable progress past a bounded floor.

`constraints.md` refers to that section as "the bounded pair-stall nudge in
spec.md §'The keep-going nudge'". Two readings survive the text:

- The phrase names ONE act (the pair-stall nudge) and cites the section that
  contains it. Then the idle keep-going nudge is a sanctioned act that the
  enumeration omits, and "exactly two" undercounts.
- The phrase is a loose section reference intended to cover both nudges in it.
  Then "exactly two" is correct but the wording says otherwise.

Nothing in the ratified tree selects between them. Because the sentence is a
CLOSED enumeration ("exactly N") in the tree's most safety-relevant paragraph,
an undecidable count is a real defect: an implementer adding a fourth act
cannot tell whether they are violating a closed list, and a reviewer auditing
the daemon against the letter cannot tell whether the idle nudge is sanctioned
or is itself a drift.

### Proposed change — `SPECIFICATION/constraints.md`, section "Acting safety"

Name each act individually rather than by section, so the count is checkable
against the code without interpretation. Composed with the companion proposal,
the enumeration becomes:

    It may coexist with exactly four acts under their independent complete
    predicates: the low-context wrap-up in contracts.md §"The wrap-up
    injection", the idle-with-context-left keep-going nudge and the bounded
    pair-stall nudge, both in spec.md §"The keep-going nudge", and the bounded
    charter-reminder paste into a stalled supervisor picker in spec.md §"The
    stalled-picker charter reminder".

Add one clarifying sentence immediately after it:

    The ready-expiry notice in spec.md §"The escalating wrap-up" is NOT a
    further act: it fires under the wrap-up's own complete guarded-paste
    predicate and is enumerated here as part of it.

If the companion proposal is REJECTED (disposition (ii), the picker-stall act
removed), this proposal still stands on its own and the enumeration becomes
"exactly three acts", naming the two nudges separately and adding the same
expiry-notice sentence.

### Why this is filed as a separate finding

It is independently acceptable. The companion proposal settles a safety
question about an act that ships today; this one settles a readability and
auditability question about the sentence that governs all of them. A maintainer
may reasonably accept this and reject that, and the resulting text is coherent
either way — which is exactly the property that makes them separable rather
than one change.
