# 003 — Ratification-review triage: two blockers, and what they change

Created 2026-08-26 by the `homelab-loop-hardening-overseer` session, on the
first ratification pass of
`SPECIFICATION/proposed_changes/mapping-store-write-validation-and-start-intent.md`.

This repository runs `revise` under `revise_decision_mode: "delegated"` with
`ratification_review: "auto-spawn"` and `ratification_reviewer_model: "fable"`
(`.livespec.jsonc`, `spec_governance`). The independent read-only reviewer
that mode requires returned **two blockers** against the exact final bytes.
Both are correct. Neither is a wording nit, and one of them invalidates a
claim this thread had already reported upstream as settled.

Triage is recorded HERE, before any fix, deliberately. A fix authored
in place can create the contradiction the next review round catches, and a
review round is expensive; writing down what was actually wrong first is what
makes the second round about the fix rather than about rediscovering the
problem.

## Blocker 1 — the write-validation clause contradicts the ratified absent-epic path

**What the clause said.** "A surface that writes a mapping-store row MUST
validate that row against the durable-key contract above BEFORE the write. A
row that fails validation MUST be refused with the offending key named."

**Why that blocks.** The contract "above" contains a ratified BCP14 sentence:
the `epic` value "is REQUIRED for any track whose session may be restarted."
Read literally, an assignment row with no `epic` fails that contract, so the
clause requires refusing it — naming `epic` as the offending key — and the
clause's own scoping puts that write in range, because assignment is precisely
the write that INTRODUCES the row.

But two ratified passages require that same write to SUCCEED. `spec.md`
§"Track discovery and the mapping store": a track assigned when the anchor
cannot be read "simply carries no recorded `epic`, which the restart interlock
already handles by refusing the respawn and preserving the declaration."
`contracts.md` §"The restart interlock": "A track with NO recorded epic id is
not respawned at all: the `ready` declaration is PRESERVED and the track
surfaced." Both prescribe accept-and-handle. The amendment prescribed refuse.

**This is the exact defect research/001 and this thread's upstream reports
claimed to have AVOIDED.** The finding that matrix 08's naive form would
contradict a ratified clause was correct and was reported as such; the
proposal was then written believing it had steered clear. It had not. Knowing
the hazard and stating it in the motivation is not the same as encoding the
carve-out in the normative text, and only the byte-level review caught the
difference. Record that as the lesson, not the individual clause.

**The reviewer's sharpening is the part worth keeping**, because it closes the
obvious repair. The one reading that rescues the clause — "an absent `epic`
simply conforms" — DEFEATS THE PROPOSAL'S PURPOSE, because validation as
written is a predicate on the ROW, not on the TRANSITION. If absence conforms,
then a rewrite that STRIPS a recorded `epic` produces a row that validates
perfectly well, and the gate does not fire on the very mutation the whole
proposal exists to stop. So the repair cannot be a one-word carve-out; the
predicate itself has to change shape.

**Disposition: the predicate becomes transition-aware.** An absent `epic`
conforms as an initial state, and a write introducing such a row MUST be
accepted. What MUST be refused is a write that REMOVES or REPLACES a recorded
`epic` on a row that carried one, or that records an `epic` which is not a
ledger epic id. The REQUIRED-for-restart sentence states a precondition for
RESTARTING a track, not a precondition for WRITING its row, and the amended
clause must say so rather than leaving a reader to infer it.

## Blocker 2 — the two new start-intent texts contradict each other on the killed case

**What they said.** `spec.md`: a spawn "that fails, or that does not return at
all, MUST therefore leave an attempted-and-failed record carrying the error."
`contracts.md`: the record "MUST carry the action, the target track, the
invoker, and — once the spawn resolves — its outcome."

**Why that blocks.** For a spawn that never returns, the spawn never resolves,
so the companion attaches no outcome and no error — while `spec.md` demands
the record carry "the error." A surface killed between issuing the spawn and
returning cannot write anything at all. The obligation is unsatisfiable for
exactly the case the new scenario was written to pin, and the scenario itself
quietly sides with the weaker reading: it asserts only that "a start-intent
record written before the spawn is on file."

**Second half of the same blocker.** The SATISFIABLE leg — a spawn that fails
AND returns, whose record is then amended to carry the error — has no scenario
at all, even though the proposal's own motivation calls reconciliation
"required" and "easy to omit." Under this tree's both-clause-and-scenario
rule, that load-bearing MUST is uncovered. The motivation predicted the
omission and the proposal committed it.

**Disposition: split the two cases in the normative text.** A spawn that fails
and RESOLVES: the surface MUST amend the intent record with the failure and
its error. A spawn that does NOT return: the intent record stands with no
outcome, and an intent record carrying no outcome MUST be read as
ATTEMPTED-AND-FAILED — never as live work, and never as evidence that no
attempt was made. That preserves the property matrix 07 actually needs (a dead
attempt is distinguishable from no attempt, and does not read as live) without
demanding a write from a process that no longer exists. Add the missing
scenario for the resolving-failure leg, with its heading-coverage entry.

## What this round cost, and what it bought

One review round, no ratification. The proposal file itself is unchanged and
remains as filed; the repairs land as a `modify` decision, which is the
operation's own mechanism for exactly this — the filed text stays the record
of what was proposed, and the modifications carry what was ratified.

The reviewer also returned six non-blocking observations. Two are worth
carrying: one column-wrap overrun at the `epic`-clause insertion point, and a
note that the `contracts.md` start-intent paragraph landed as a standalone
paragraph rather than as a note in the introductory sentence's set — harmless,
since the final bytes are self-consistent, but recorded so the deviation from
the filed proposal is not mistaken later for drift.

**The attestation is byte-exact, so every one of these repairs stales it.** The
fixed bytes require a FRESH review; the returned verdict cannot be carried
forward across an edit, not even a whitespace one.
