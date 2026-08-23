# Derived row status is not declared status

Measured 2026-08-19 against the tree, while ratifying
`acting-safety-third-keystroke-act`. Recorded here at the foreman's request
because the confusion it documents was made TWICE in one day by two different
sessions writing spec prose, and the second time it very nearly landed in
`SPECIFICATION/spec.md` as ratified text.

**If you are about to write a spec clause, a scenario Given, or a work-item
acceptance leg that says a session's status "is" some value — read this first.**

## The two vocabularies

They look alike, they overlap in spelling, and only one of them is something a
session can cause directly.

**DECLARED STATUS** is what a session writes to its own state file. `spec.md`
§"Out-of-band state declaration" fixes the vocabulary exactly: there are
**three** values a session may write —

    ready
    blocked: <one-line reason>
    winding-down

— plus exactly one value the daemon writes to itself, `idle-with-context-left`.
A malformed value is treated as NO declaration at all, fail-closed. That is the
complete set. Nothing else is declarable.

**DERIVED ROW STATUS** is the daemon's own classification of a track, computed
each tick and published on the snapshot row. Its vocabulary is DIFFERENT and
larger — `working`, `blocked:human`, `picker-stalled`, `session-gone`,
`ready-uncertifiable`, and others. A session cannot write any of them.

## The trap, stated concretely

**`blocked:human` is a DERIVED value. No session can declare it.** It is not in
the three-value set, and the string a session would actually write for a human
wait is `blocked: <reason>` — different token, different meaning, different
producer.

`overseer/_supervisor_evaluate.py` assigns it from **three** distinct sources,
and only one of them involves a declaration at all:

| line | source | needs a declaration? |
|---|---|---|
| 214 | an active **foreman pane claim** (`foreman_pane_claim.active_pane_claim`) | no |
| 250 | `elif gate or blocked is not None` — **live gate evidence ALONE** satisfies this | no |
| 250 | the same branch, reached via a standing `blocked:` declaration | yes |

So an open structured picker is sufficient on its own. A track can sit at
`blocked:human` for its entire life having declared nothing.

## Why it matters, and how it fails

A clause written as "the session's DECLARED status is `blocked:human`" is not a
harmless paraphrase. It is wrong in two compounding ways:

1. **It is inexpressible.** It names a value in a vocabulary that does not
   contain it, so a reader checking the letter against §"Out-of-band state
   declaration" finds no such declarable value and cannot tell what was meant.
2. **It narrows the behavior.** Read plainly — especially inside a list
   introduced by "fires only under ALL of the following" — it adds a
   precondition the daemon does not enforce. The letter then describes a
   stricter daemon than the one that ships, and **the act's COMMON case falls
   outside its own specification**: a session parked on its own picker has
   typically declared nothing.

Direction matters here. This is an UNDERSTATEMENT of what the daemon does, not
an overstatement, which makes it hard to catch by testing — every test of the
shipped behavior still passes. It is caught only by reading the clause against
the vocabulary.

Shipped proof that no declaration is required:
`tests/test_picker_stall_nudge_echo.py::test_foreman_picker_stall_gets_same_reserved_entity_nudge`
drives the stalled-picker charter reminder to fire with no state-file write
anywhere in the test.

## The rule to follow

- Say **"the daemon's derived row status is X"** when X is a snapshot-row value.
- Say **"the session has declared `blocked: <reason>`"** — with the space and the
  free-text reason — when you mean an actual declaration.
- Never write "declared status is `blocked:human`". There is no such thing.
- When a clause turns on a status, ask **who produces it**. If the answer is "the
  daemon, from evidence", it is derived, and a session's declaration is neither
  necessary nor sufficient for it.

## Provenance

Found by the independent read-only ratification reviewer required by
`spec_governance.ratification_review` during the `/livespec:revise` pass for
`acting-safety-third-keystroke-act`, as a BLOCKER, in text drafted by the session
running that pass. The clause was corrected before ratification; the ratified
§"The stalled-picker charter reminder" now states the derived-status form and
says explicitly that the act requires no declaration from the session.

The reviewer had also flagged the same wording in two `scenarios.md` Givens, which
is worth noting on its own: **the error propagates**, because a scenario Given is
usually written by copying the clause it pins.

Note also that the ORIGINAL proposal text still carries the incorrect wording, at
`SPECIFICATION/proposed_changes/acting-safety-third-keystroke-act.md` and therefore
in its archived copy under `history/`. That was left deliberately: the proposal is
the record of what was PROPOSED, and correcting it after the fact would falsify
that record. The divergence between proposed and ratified wording is recorded in
the revision's own rationale. Do not "fix" the archived proposal.
