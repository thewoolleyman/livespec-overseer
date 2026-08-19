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

**AMENDED 2026-08-19 after independent review.** A fresh reviewer with no role in
drafting verified this proposal read-only against master and the ledger; the
record is `tmp/overseer/foreman/um53-review-2026-08-19.md`. Verdict:
ACCEPT-WITH-EDITS. The core divergence was confirmed real, but three drafted
clauses did not match the tree and two of them broke this proposal's own
"accepting needs no behavior change" premise. Every edit below was independently
re-verified against the tree before being written in. The summary and motivation
above are the ORIGINAL text and are preserved unchanged for the record; where the
summary says "for reserved supervisor topics only", read edit E1.


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
prescribes for the foreman.

**Accepting this proposal ratifies a keystroke-bearing act into gated,
human-waiting panes. That is a maintainer-grade safety decision.** It was
deliberately not self-authorized by the session that found it or by the session
that filed this proposal. Rejecting selects disposition (ii), and the follow-up
is then the removal of `nudge_charter_authorized_picker_stall`, its call site in
`apply_picker_stall`, and its test.

**The original draft claimed accepting (i) requires no behavior change. After
review that claim is CONDITIONAL, not free-standing:** it holds only if the
maintainer answers Q1 and Q2 below toward the shipped behavior. Answering either
toward the drafted text makes this a spec change AND a code change.

### Two questions this proposal does NOT decide

Both were raised by the independent review because the drafted clause was
narrower or stricter than the shipped code. Each is a genuine choice about what
the daemon should DO, not a wording preference, so each is put as a question
rather than resolved here.

**Q1 — Which topic classes may receive this paste?**

The original draft said "a RESERVED SUPERVISOR topic only, never a worker".
That is narrower than the code. The gate is
`signals.topic_reserved_for_supervisor`, and
`overseer/_signals_topics.py:13-21` defines it over
`_RESERVED_WORKER_SUFFIXES = ("-supervisor", "-foreman")` — it returns True for
a `-foreman` topic as well. The shipped daemon will paste this reminder into a
stalled FOREMAN picker.

- **Q1(a)** Ratify the shipped predicate: both reserved entity suffixes,
  `-supervisor` and `-foreman`. No code change.
- **Q1(b)** Narrow the code to `-supervisor` only, and specify that. A code
  change plus a test.

Q1(a) is the no-behavior-change answer. Q1(b) deserves real weight anyway: the
foreman is an operator role that acts on the fleet, and pasting a
SUPERVISOR-worded charter reminder into a foreman's picker may simply be the
wrong message rather than a sanctioned act. Whichever is chosen, the spec text
must name the predicate that the code actually holds.

**Q2 — What bounds the repeat?**

The original draft said the paste fires "at most ONCE per stall episode", with a
daemon restart re-arming it. That is STRICTER than the code, and the difference
is not cosmetic.

`overseer/_supervisor_progress.py:35-50` (`blocked_human_stall_seconds`) resets
`istate.picker_stall_nudged = False` whenever
`obs.istate.blocked_human_stall_capture != obs.capture` — that is, on ANY change
to the pane capture. A successful paste lands the reminder text in the picker's
composer, which CHANGES the capture. So the shipped sequence is: paste → flag
and stall clock both reset → thirty minutes of renewed stillness → paste again,
repeating indefinitely while a human stays away, accumulating reminder text in
the composer.

**The existing test cannot see this.** `FakeTmux` does not echo a paste back
into its capture, so the once-per-episode assertion in
`overseer/test_supervisor_liveness_starvation.py` passes against a fixture whose
capture never changes. The bound is real in the test and absent in production.

- **Q2(a)** Ratify the shipped behavior by defining the episode as
  CAPTURE-STABILITY-KEYED: one paste per interval of unchanged capture, which
  under a persistent human absence means a reminder roughly every
  `PICKER_STALL_AFTER`. No code change; the spec must then say plainly that the
  reminder repeats, so no reader mistakes "once per episode" for "once".
- **Q2(b)** Fix the code to hold the bound across the paste's own echo — for
  example by keying the reset on a capture change that is not attributable to
  the daemon's own paste — and specify a true once-per-episode bound. A code
  change plus a test that can actually observe the echo.

Related, and worth deciding alongside: this act has NO second-episode
escalation, unlike the pair-stall nudge's ratified skip-and-surface rule. If
Q2(a) is chosen, an unbounded repeat with no escalation is what gets ratified.

### Change 1 — `SPECIFICATION/constraints.md`, section "Acting safety"

Replace the two sentences that enumerate the sanctioned acts and forbid the
pane classes. Current text:

    It may coexist with exactly two acts under their independent complete
    predicates: the low-context wrap-up in contracts.md §"The wrap-up
    injection", and the bounded pair-stall nudge in spec.md §"The keep-going
    nudge". The shell is left running and neither paste authorizes a restart.
    Generating, changing, sub-agent-busy, gated, human-waiting, foreign,
    bare-shell, and ambiguous panes MUST never be pasted into.

Proposed text, with the enumeration composed per the companion finding and the
count settled by the maintainer's answer to its Q3:

    It may coexist with the acts enumerated in spec.md §"The keep-going nudge",
    §"The escalating wrap-up", contracts.md §"The wrap-up injection", and
    spec.md §"The stalled-picker charter reminder", each under its own
    independent complete predicate. The shell is left running and NO such paste
    authorizes a restart. Generating, changing, sub-agent-busy, foreign,
    bare-shell, and ambiguous panes MUST never be pasted into. Gated and
    human-waiting panes MUST never be pasted into by any DAEMON informational
    act EXCEPT the stalled-picker charter reminder under its own complete
    predicate, which MUST NOT be widened to any other daemon act, pane class, or
    topic class.

**E3, and this is a correction to the original draft.** The original wrote "which
is the ONLY sanctioned exception". The independent review falsified that against
the ratified tree itself, and the falsification is not marginal:

- `spec.md`'s v020 delivery-routing floor already sanctions the FOREMAN
  delivering decision-relevant context through a picker's own free-text response
  channel — a paste into an open picker, by design.
- `overseer/foreman_blocked_answer.py:205-207` pastes an answer AND sends
  `Enter` into a blocked, gated pane under the consensus valve. That is stronger
  than this act, which never submits.
- `overseer/foreman_gate_state.py:61-63` sends key sequences and re-pastes
  question text.

Those are foreman acts, governed by the foreman sections and the v020 floor, and
they are correctly outside this DAEMON enumeration — but a sentence claiming a
sole exception across the whole document would have contradicted a ratified
floor and shipped behavior on the day it was written. The scoping words "by any
DAEMON informational act" and "any other daemon act" carry that correction. The
`constraints.md` sentence "The foreman MUST NOT widen its own authority on the
basis of any evidence it produced itself" already sits in this section and is
unchanged.

### Change 2 — `SPECIFICATION/spec.md`, new section "The stalled-picker charter reminder"

Add one section stating the act's complete independent predicate. Every clause
below has been verified against the shipped code; the two clauses that carry a
maintainer choice are marked and resolve per Q1 and Q2 above.

- **[Q1]** The act applies to a topic in the reserved entity namespace. As
  shipped that is BOTH `-supervisor` and `-foreman`
  (`signals.topic_reserved_for_supervisor`); it never applies to an ordinary
  worker topic. The final wording follows the answer to Q1.
- The target pane is positively identified as that track's supervised session.
  The identity gate holds upstream in the evaluation precedence rather than
  inside this act.
- The session's declared status is `blocked:human`.
- Live gate evidence shows an OPEN structured picker (`obs.gate`). Whether a
  runtime can raise a structured question MUST continue to be derived from live
  gate evidence, never inferred from a runtime name, launch mode, or policy, per
  the existing rule in §"The state file".
- The pane capture has been UNCHANGED for longer than a bounded floor, thirty
  minutes by default. The clock is capture-stability-keyed, not wall-clock from
  the declaration.
- **[Q2]** The repeat bound. As shipped, one paste per interval of unchanged
  capture; because a successful paste changes the capture, the reminder recurs
  about every floor-length interval while the human stays away. The final
  wording follows the answer to Q2, and MUST describe whichever behavior ships
  — a spec that says "once" over a daemon that repeats is the defect this
  proposal exists to close, reproduced.
- The payload is delivered as ONE atomic paste and is NEVER SUBMITTED: no
  `Enter`, no selection keystroke, no digit. The daemon does not choose from a
  picker and MUST NOT answer one. This is the property that separates this act
  from every other DAEMON keystroke-bearing act, each of which pastes AND
  submits. (It does not separate it from the foreman's blocked-answer valve,
  which does submit — see E3.)
- The message states only that the supervisor should re-read its own pending
  picker, perform charter-authorized mechanical unblocks itself, and declare
  `blocked: <reason>` only when the unblock genuinely requires a human decision.
- The act AUTHORIZES NOTHING. It writes no state file, calls no restart path,
  never closes or re-opens a round, never raises or lowers a certification
  floor, and never answers the picker.
- A failed paste is surfaced to the operator and does NOT mark the episode
  handled, matching the failed-paste posture of the wrap-up and the keep-going
  nudge.
- Ambiguous evidence — an unreadable gate reading, an unresolved pane, an
  unsettled capture — resolves to inaction.

The section MUST also state, explicitly, that this act is the sanctioned daemon
exception named in constraints.md §"Acting safety", so a reader arriving from
either document finds the other.

### Change 3 — `SPECIFICATION/scenarios.md`, pinning scenarios

Add a scenario pinning the properties a regression would break, written
status-adversarially so a status-keyed implementation cannot satisfy it by
accident:

    Given a tracked reserved-entity session whose declared status is
      blocked:human
    And whose live gate evidence shows an open structured picker
    And whose pane capture has been unchanged past the bounded floor
    When the daemon acts on that track
    Then exactly one charter-reminder payload is pasted into that pane
    And no Enter, digit, or other selection keystroke is sent to it
    And no restart is authorized by that paste

A negative scenario pins the topic bound (its exact subject follows Q1):

    Given a tracked ORDINARY WORKER session in the identical stalled-picker
      state
    When the daemon acts on that track
    Then nothing is pasted into that pane

**A third scenario is now REQUIRED, and the original draft omitted it** — it is
the leg that would have caught the Q2 mismatch. It must exercise the paste's own
echo, which means a tmux double that reflects a pasted payload back into the
capture:

    Given the stalled-picker preconditions are met and a reminder has been
      pasted
    And the pasted text is visible in the subsequent pane capture
    When the daemon observes that track again past the bounded floor
    Then the behavior matches the ratified repeat bound exactly

Written against today's `FakeTmux`, which does not echo pastes, that scenario is
unfalsifiable — which is precisely why the existing test asserts a bound the
daemon does not hold. Whichever way Q2 is answered, the double must gain
paste-echo before this scenario means anything.

### What this proposal does NOT change

- The cardinal rule in `overseer/marker-protocol.md` is untouched, and the
  independent review checked this specifically: the act writes no state, calls
  no restart path, and every drafted version of the constraint text says no
  sanctioned paste authorizes a restart.
- The restart-path keystrokes (`_supervisor_restart.py:289`,
  `_supervisor_recovery.py:205`, `_supervisor_launch.py:195/235/246`) are
  governed separately by §"The restart" and the restart interlock.
- The foreman's own keystroke-bearing acts are governed by the foreman sections
  and the v020 delivery-routing floor; this enumeration is the DAEMON's.
- Governing the "picker-stall surface" and "picker-stall status" vocabulary that
  v020 references but never defines stays with its existing carrier,
  `overseer-g6sy` item (c), which unblocks once this letter question is settled
  in either direction.

## Proposal: Make the acting-safety act enumeration name each act instead of citing a two-act section

### Target specification files

- SPECIFICATION/constraints.md
- SPECIFICATION/spec.md

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

**AMENDED 2026-08-19 after independent review.** The same review found this
finding UNDERSTATED rather than wrong: a SECOND closed count exists in the
ratified tree that the original draft never mentions, and the original's
clarifying sentence directly contradicts it. See edit E4.


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
an undecidable count is a real defect: an implementer adding a further act
cannot tell whether they are violating a closed list, and a reviewer auditing
the daemon against the letter cannot tell whether the idle nudge is sanctioned
or is itself a drift.

### E4 — there is a SECOND closed count, and the original draft contradicted it

The independent review found this and it is the more consequential half of the
finding. `SPECIFICATION/spec.md:531-539` states:

    Keystroke-bearing informational pastes share one safety floor: a paste MUST
    remain suppressed while its target is generating, changing, gated,
    runtime-reported as waiting on a human, sub-agent-busy, blocked by
    declaration, or missing the input evidence that act requires. ... Exactly
    three acts apply that rule: the low-context wrap-up for any supervised
    entity, using the runtime-specific predicate in §"The supervision round",
    the once-per-round expiry-notice of §"The escalating wrap-up", and this
    bounded pair-stall nudge into the supervisor.

That sentence does two things the original draft missed. It COUNTS the
expiry-notice as one of three distinct acts — where the original draft proposed
writing "the ready-expiry notice is NOT a further act" into `constraints.md`, a
direct contradiction of ratified text. And it OMITS the idle keep-going nudge
entirely, which independently corroborates this finding's core claim from a
second location: two ratified closed counts, in two documents, disagree with
each other AND with the tree.

Accepting the original draft as written would have produced `constraints.md`
saying "exactly four, expiry excluded" beside `spec.md` saying "exactly three,
expiry included" — trading one undecidable count for two conflicting ones. That
is worse than the defect being fixed.

**Q3 — is the ready-expiry notice a distinct act, or part of the wrap-up?**

Both readings are defensible from ratified text, which is the whole problem:

- **Q3(a) A distinct act**, as `spec.md:535-539` currently counts it.
- **Q3(b) Part of the wrap-up**, as `spec.md:369-371` supports: the
  expiry-notice "is subject to the complete guarded-paste predicate that governs
  a wrap-up" and is "a bounded companion to the escalation, not a band".

This proposal takes no position. The REQUIREMENT is that both documents say the
same thing, in the same pass, whichever way it is ruled.

### Proposed change — both documents, in one pass

Name each act individually rather than by section, so the count is checkable
against the code without interpretation, and make the two closed counts agree.

In `SPECIFICATION/constraints.md` §"Acting safety", the enumeration becomes —
composed with the companion finding's third act, and with membership per Q3:

    It may coexist with exactly N acts under their independent complete
    predicates: the low-context wrap-up in contracts.md §"The wrap-up
    injection", the idle-with-context-left keep-going nudge and the bounded
    pair-stall nudge, both in spec.md §"The keep-going nudge", and the bounded
    charter-reminder paste into a stalled supervisor picker in spec.md §"The
    stalled-picker charter reminder".

with N and the expiry-notice's membership fixed by Q3. Under Q3(a) the
expiry-notice is named as its own member; under Q3(b) one sentence follows the
enumeration:

    The ready-expiry notice in spec.md §"The escalating wrap-up" is NOT a
    further act: it fires under the wrap-up's own complete guarded-paste
    predicate and is enumerated here as part of it.

**And in the SAME pass**, `SPECIFICATION/spec.md:535-539`'s "Exactly three acts
apply that rule" sentence MUST be amended to agree with that enumeration in both
membership and count. As it stands it omits the idle keep-going nudge regardless
of how Q3 is answered, so it needs correction under either ruling. Leaving it
untouched is the one outcome this finding exists to prevent.

If the companion finding is REJECTED (disposition (ii), the picker-stall act
removed), this finding still stands on its own: the two nudges still need naming
separately, and the two closed counts still need to agree.

### Why this is filed as a separate finding

It is independently acceptable. The companion finding settles a safety question
about an act that ships today; this one settles a readability and auditability
question about the sentences that govern all of them. A maintainer may
reasonably accept this and reject that, and the resulting text is coherent
either way.
