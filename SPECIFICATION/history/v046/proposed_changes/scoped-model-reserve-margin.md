---
topic: scoped-model-reserve-margin
author: claude-opus-4-8
created_at: 2026-09-06T00:00:00Z
---

## Proposal: give the scoped-model rotation trigger a configurable remaining-margin, so a Fable-dependent session is moved before the active account's Fable reaches zero

### Target specification files

- SPECIFICATION/spec.md

### Summary

The ratified v045 scoped-model clause triggers rotation, and waives the relative-headroom
margin, only when the ACTIVE account CANNOT SERVE the pinned model — defined as its scoped
allowance being fully spent or absent, i.e. remaining == 0. There is no remaining-margin,
unlike the five-hour window's configurable threshold, whose whole purpose is stated in the
same section: "low enough that heavy fleet use cannot cross the remaining margin between two
polls." So a Fable-dependent active account drains Fable all the way to 0 — starving its
Fable-pinned sessions of their final requests — before rotation even considers firing, and
30-minute polling lets a human beat the loop to it. This proposal adds a configurable
SCOPED-MODEL RESERVE (percent remaining) so the scoped trigger and its eligibility waiver
fire once the active account is at or below the reserve, not only at full exhaustion. To keep
a reserve-triggered move non-oscillating, ranking prefers a candidate that HOLDS the scoped
allowance above the reserve, and where the reserve is the sole reason for leaving and no
candidate holds above it the operation HOLDS rather than move onto an account that would
immediately re-trigger. A reserve of zero reduces every rule to the exact ratified
cannot-serve boundary, so the change is a strict, opt-out-able extension.

### Motivation

Incident 2026-09-06 (bug overseer-dyt6). Active account anthropic-1 held Fable at 1% while
three idle accounts held 57–69% Fable; a Fable-dependent foreman session (observed on Fable,
so scoped_pin was armed) was left with no Fable and the operator switched accounts by hand,
twice. Verified by running the shipped v045 decision core against the incident's recorded
state (`~/.local/state/caam-usage-rotate/state.json`): with active Fable = 1% the trigger did
NOT fire and the pass HELD, even though the machinery would have correctly selected anthropic-3
(57% Fable, 85% five-hour) had it fired; with active Fable forced to 0 it fired and switched.
So the machinery, the ranking, the floor precedence and the observed-session arming are all
correct — the sole gap is that "cannot serve" is a zero-remaining boundary with no margin.

Maintainer requirement 2026-09-06, verbatim intent: "When Fable-dependent sessions are active
and the active account's Fable is spent, rotate to any account that still holds Fable and is
not otherwise expired, respecting protected-account weekly floors; do not strand perishable
weekly for accounts that have no Fable sessions." The reserve is gated on the existing
scoped-pin condition, so it never fires absent a Fable-dependent session and therefore never
strands weekly for non-Fable accounts. The protection-floor precedence ratified in v040 ("a
candidate at or below its protection floor MUST remain disqualified even to serve the pinned
model") is unchanged; a protected account below its floor is still never selected.

### Reconciliation with the existing prohibitions

This adds no FOURTH way for the scoped allowance to influence selection: it parameterises the
existing three (Trigger, Eligibility, Ranking) with a reserve, exactly as the five-hour and
weekly triggers are parameterised by their configurable thresholds. It does not violate "MUST
NOT rotate in order to consume a scoped allowance": that prohibition governs CAPACITY (spending
Fable draws down weekly), whereas the reserve is a CAPABILITY guarantee for a pinned session —
the same capacity/capability distinction the clause already draws — and it fires only "WHILE
SUCH A PIN IS IN EFFECT, AND ONLY THEN." The MODEL ENFORCEMENT clauses remain keyed on
can-serve / cannot-serve (the exhaustion boundary), deliberately NOT on the reserve: rotation
moves the active account onto a Fable-rich one so the session GETS Fable, while enforcement
keeps a session on Fable as long as any selectable account can serve it — complementary, not
contradictory.

### Anti-oscillation

An independent ratification review of the first draft found, correctly, that bounding the
Eligibility waiver alone was insufficient: a candidate at or below the reserve but with
remaining > 0 could still enter selection via the ORDINARY relative-headroom margin and, under
the unchanged "can serve" ranking, out-rank a genuine above-reserve holder on soonest weekly
reset — landing a reserve-triggered move on an account that immediately re-triggers. This
proposal therefore also re-expresses RANKING against the reserve (a holder above the reserve
sorts ahead of one that is not) and the scoped-unsatisfiability HOLD against the reserve (hold
when the reserve is the sole reason for leaving and no candidate holds above it). Both reduce
exactly to their can-serve forms at a reserve of zero, so anti-oscillation is guaranteed: a
reserve-triggered move always lands on an account holding the scoped allowance strictly above
the reserve, whose own reserve trigger is quiet, or the operation holds.

### Proposed Changes

Seven coordinated edits in SPECIFICATION/spec.md, all within the account-rotation /
scoped-model section. The reserve is defined once and Trigger, Eligibility, Ranking and the
scoped-unsatisfiability hold are re-expressed against it; the CAN SERVE definition, the
protection-floor rules, and the Model-enforcement clauses are left verbatim.

A. **Rotation triggers paragraph** — re-express the scoped trigger against the reserve:
"…and the active account **is at or below a configurable scoped-model reserve on that
allowance**;…" (was "…cannot serve it;…").

B. **Eligibility paragraph** — re-express the carve-out's condition and its oscillation
argument: available only while the active account "**is at or below the scoped-model reserve
on that allowance**; …the account being left is at or below the reserve while the selected
candidate holds the scoped allowance strictly above it,…".

C. **Scoped-model clause, definitions** — after the CAN SERVE definition, add: a configurable
SCOPED-MODEL RESERVE (percent remaining, nonzero default, zero restores cannot-serve-only);
an ACTIVE account is AT OR BELOW THE SCOPED-MODEL RESERVE when its scoped allowance is absent
or its remaining is at or below the reserve; a CANDIDATE HOLDS THE SCOPED ALLOWANCE ABOVE THE
RESERVE when its scoped remaining is present and strictly greater than the reserve; at reserve
zero these reduce to cannot-serve and can-serve, so the reserve parameterises the three
selection rules without adding a fourth.

D. **Scoped-model clause, Trigger + Eligibility leads** — Trigger fires when the active account
"**is at or below the scoped-model reserve on the pinned model**" (spent, absent, or merely at
or below the reserve), with the anti-starvation rationale and the reserve-zero reduction;
Eligibility waives the margin for a candidate that "**HOLDS THE SCOPED ALLOWANCE ABOVE THE
RESERVE**", excludes an at-or-below-reserve candidate from the waiver, and states the
non-oscillation guarantee (a candidate that would itself immediately re-trigger MUST NOT be
chosen, whether via the waiver or the ordinary margin) cross-referencing Ranking (F) and the
hold (E); the unwaived case is "**where the active account is ABOVE the scoped-model reserve**".

E. **Scoped-unsatisfiability hold** — "Where rotation is triggered by **the scoped-model
reserve alone and no candidate holds the scoped allowance above the reserve**, the operation
MUST hold and MUST report that the pin cannot currently be satisfied above the reserve,…" (was
"…scoped unsatisfiability alone and no candidate can serve the pinned model…"), with the
reserve-zero reduction stated.

F. **Ranking** — both the scoped-clause Ranking lead and the standalone Ranking paragraph:
"**one that holds the scoped allowance above the reserve MUST sort ahead of one that does
not**" (was "one that can serve … ahead of one that cannot"); an unreadable scoped allowance
is treated as not holding above the reserve; reserve-zero reduces exactly to the can-serve
ordering.

G. **Per-session-pin paragraph consistency** — the arming rationale reads "the active account
being **at or below the scoped-model reserve** on the scoped model is a rotation trigger…", and
the anti-oscillation clause reads "where the ACTIVE account **is ABOVE the scoped-model
reserve** on the pinned model the margin MUST apply unwaived" (both were phrased against
"serve"), so the per-session pin case matches the reserve-based trigger/waiver exactly.

### Notes for ratification review

- Boundary equivalence at reserve = 0 (confirmed by first-round review): "at or below the
  reserve" ⇒ fully-spent-or-absent (remaining cannot be negative); "holds above the reserve"
  ⇒ present-and-not-fully-spent; so reserve 0 is byte-equivalent to ratified v045.
- Anti-oscillation now rests on Ranking (F) preferring above-reserve holders AND the hold (E)
  when none holds above the reserve, closing the first-round blocker where a below-reserve
  candidate reachable via the ordinary margin could be selected and immediately re-trigger.
- Enforcement clauses (foreman → general model only when NO selectable account can serve) are
  deliberately left on the can-serve boundary; confirm the change created no contradiction
  between them and the reserve-based rotation.
