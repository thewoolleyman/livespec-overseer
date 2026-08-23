# foreman-panel-and-rulings — opening research

Thread opened 2026-08-23 by cutting it out of `plan/foreman-actuator-gather-and-roster`
(anchor `overseer-tdfe`). Ledger anchor `overseer-764a`.

## Why this thread exists

It revives the subject of `plan/foreman-panel-and-consensus` (anchor `overseer-6l7v`,
closed), cut out of the previous junk drawer on 2026-08-22 and closed since. Its
residue and the findings measured after it closed both landed in the carrier, which
held **68 open children** when this cut was made.

## What this thread holds

**The convene obligation has no producer, so the condition built on it is dead.**

| item | |
|---|---|
| `overseer-tdfe.2` | implement the convene-obligation record producer — the shipped consensus-overdue condition can never fire without it |
| `overseer-a3l6x2` | panel-first discipline: a POSITIVE convene criterion in the contract, plus the report-only consensus-overdue attention condition |
| `overseer-tdfe.17` | cover SPECIFICATION v029's convene-obligation and wait-premise headings with real tests |

**Panel records that misdescribe what the panel did.** These are the same class as the
record-versus-world failures `AGENTS.md` catalogues: the record is read as evidence and
it says something that did not happen.

| item | |
|---|---|
| `overseer-tdfe.26` | a UNANIMOUS needs-human panel is recorded as `non_anthropic_needs_human_dissent` — the reason names which seat tripped the rule, not any disagreement |
| `overseer-pyfn` | a panel that DECIDED is stamped `decision_kind=substantive_non_decision`, because the classifier ends in an unconditional branch |
| `overseer-jsqct5` | the `consensus` valve is INERT where one reviewer leg always returns malformed output — the panel can never clear its own gate |
| `overseer-cif9` | the v026 typed-ruling channel shipped vocabulary-empty, so no ruling can ever be authorized, and nothing tracks the condition that would make it live |

**The SPECIFICATION paragraphs these mechanisms are built on.**

| item | |
|---|---|
| `overseer-9569` | v007 `spec.md` restates the floor member list three lines above forbidding restatement |
| `overseer-ntz1` | v027 follow-ups: condition (b)'s "another library" wording, and recording that the frozen worked-example counts are overcounts |

## The tier split, which is load-bearing and not paperwork

`overseer-9569` and `overseer-ntz1` have **SPECIFICATION deliverables**. They route
through `propose-change` and must never be handed to the factory:
`scripts/check-no-factory-spec-edits.sh` is a hard, no-escape-hatch gate rejecting any
factory-authored commit touching `SPECIFICATION/`, and `just check` runs it in-sandbox.

The measured cost of ignoring this is on record: `overseer-lixhd3.1` spent **four
hours** and two fix-stage passes discovering that its own acceptance criterion required
a file the sandbox forbids. Its text had correctly identified the split and it was
still filed as one unit — accurate analysis, useless as a control. **A mixed-tier item
is not dispatch-safe merely because part of it is.**

`overseer-ntz1` also carries its own reason for having been deferred rather than ridden
on the ratification it came from: fixing it in place would have changed
`proposal_bytes`, invalidated the ratification digest, and forced a third review round
against bytes nobody had reviewed. That reasoning is still correct; the work is
outstanding, not wrong.

## Seams with siblings

- **`plan/foreman-liveness-and-escalation`** owns what happens when a loop is dead or
  escalated. Where an escalation must convene a panel, the convene obligation is ours
  and the escalation policy is theirs.
- **`plan/foreman-wait-premise-conditions`** owns conditions keyed on a wait premise.
  `overseer-tdfe.17` covers headings from BOTH families in one item; it sits here
  because the convene half is the larger part, and its wait-premise half must be
  verified against that thread before it is called done.
- **`plan/supervision-safety-and-attention-truth`** owns the daemon rows. A panel record
  is not a daemon row.

## Explicit deferrals

- **D1 — the `full_autonomy` config key** and what it may delegate is
  `plan/foreman-full-autonomy-option`'s. This thread must not decide what a panel is
  ALLOWED to dispose of; it fixes whether the machinery reports what it did.
- **D2 — no new ruling vocabulary is designed here** beyond making the shipped channel
  usable. Adding ruling kinds is a spec change and goes through `propose-change`.

## A caveat on the cut mechanics, stated so it can be falsified

Membership moved by **parent-child edge only**. The archive gate additionally matches
children by id hierarchy (`plan_child_ids_from_id_hierarchy`, read from the plugin
source), so `overseer-tdfe.2`, `.17` and `.26` remain gate children of `overseer-tdfe`
regardless of parent — bound to both gates. Expect them in a sweep of either thread;
`overseer-tdfe.9` owns that inconsistency. The genuine finding would be a child of this
anchor that `overseer-tdfe` can archive over.

## UPDATE 2026-08-23, ~08:00Z — R1's first premise is CURED, not corrected

**This is an UPDATE, not a correction.** The section above says the convene obligation
has no producer, "so the condition built on it is dead", and that three further rows
describe conditions built on a record nothing writes. That was true when this note was
written at ~06:30Z. It stopped being true about ninety minutes later, and the two facts
are different: nothing here was measured wrongly, the world moved.

**What landed.** `overseer-tdfe.2` merged as PR 1824 (`merge_sha b3971358`), run
`01M0PP3C1QXKWNBXFXNVZ5RW0R` on the hp factory, envelope stage `done` / status `green`
with the post-merge janitor green. `overseer/foreman_convene_obligations.py` is on
`origin/master`, confirmed directly rather than off the envelope.

**And it is LIVE, which is the part that is easy to get wrong.** `git tag --contains
b3971358` returns `v1.45.1` and `v1.45.2`, and the acting daemon reports
`daemon_package.version` `1.45.2` in `~/.livespec-overseer-status.json`. The daemon
self-updates on the release lane, so no bounce was owed.

That last point is worth keeping as method rather than as trivia. The seat that measured
it had first reasoned from a TRUE mechanism — the daemon imports `overseer.*` once and
never hot-reloads — to a FALSE conclusion about the world, without measuring the world,
and posted a correction. The one-command check is `daemon_package.version` against
`git tag --contains <merge-sha>`; prefer it to any argument from process start times, and
certainly to file dates, which are wrong here because this repo splits modules constantly.

**What this changes for the thread.** R1's carrier is discharged; the reader-with-no-writer
condition is closed. The convene criterion (`overseer-a3l6x2`) and the coverage item
(`overseer-tdfe.17`) are now testable against a record that something actually writes.
The rest of the note stands as written — in particular the tier split, which is unchanged.

**The primary record is the ledger.** `overseer-764a`'s timeline carries the merge, its
evidence and the correction above; this section points at it rather than restating it, so
there is one authority and one pointer instead of two accounts to keep in step.
