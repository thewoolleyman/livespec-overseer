# A deferral's successor must be reachable from BOTH ends

Moved verbatim from `AGENTS.md`.

## A deferral's successor must be reachable from BOTH ends, and the fix is on the RECORDING side

Measured 2026-08-23 while archiving `overseer-6s3pk6`, and tested against live data
rather than reasoned about.

**The problem.** A plan defers work and must name a real successor — an unrecorded
deferral is the defect `overseer-l7c6` was filed to cure. But the successor usually
should NOT be a child of the deferring epic: it is deliberately out of that thread's
scope, and a child is enumerated by the archive gate and would BLOCK the very archive
it exists to unblock. So it is filed unparented — and an unparented row tied to a
thread is invisible to a gate that then reads clean, which is its own defect shape.

**The criterion: reference it from BOTH ends, and treat the two directions as
separate facts.** Four shapes, and only one is correct:

| epic→row | row→epic | shape |
|---|---|---|
| yes | yes | **correct** — either end reaches the other |
| no | yes | **invisible** — the gate reads clean and the work is lost |
| yes | no | **one-directional** — an archiver starting at the epic finds it; anyone starting at the row cannot place it |
| no | no | an unrecorded deferral wearing a filed row |

The third shape is easy to miss because it looks fine from the archiver's seat, which
is the seat that usually checks.

**The mechanism is item TEXT, and that is not a weak substitute for an edge — it is the
correct instrument.** Filing thread membership as a `depends_on` is circular by
construction (an epic cannot close before its children) and renders the item
permanently undispatchable; this file documents that trap at length above. Name the
thread in the row's prose and the row in the thread's archive record.

**A criterion is only trustworthy once it has a PASSING control.** This one was run over
eight live epic/row pairs on a fresh 807-row export, including a deliberately
unparented, doubly-referenced successor as the control. Had the rule flagged that row,
it would have been useless — a sweep that cannot distinguish a deliberate decision from
an omission reports both and teaches readers to ignore it. The passing control is what
makes it a criterion rather than a plausible-sounding rule. The same run also collapsed
"three affected threads" into **one** offending row referenced from neither end of the
one thread it belonged to: name the thing to fix, not the places it surfaces.

### A mention is not a reference: it must be a DECLARATION, not a CITATION

**The count-based reading of the table above does not survive contact with real rows,
and the sentence above originally got this wrong** — it said the offending row belonged
to *two* threads. It belongs to one. The apparent second tie was a **provenance
citation**: a comment recording where a measurement had been taken.

The contrast sits inside that single row, which is why it is the right specimen:

| tie | where | text | verdict |
|---|---|---|---|
| → thread A | **title** | "carrier for `<epic>`'s fired deferral" | **declaration** |
| → thread B | a comment | "measured separately today while reviewing `<other-epic>`" | citation |

Counting mentions makes those identical. They are not, and the difference is not subtle
once named: one asserts membership, the other records provenance.

**Two discriminators, both cheap and both available:**

- **WHERE it appears.** A tie in the **title or description** carries weight; a tie in a
  comment mostly does not. Comments are where this fleet records evidence, so they are
  full of other threads' ids by design.
- **WHAT it says.** A carrier, successor, or thread-membership phrase — not a
  measurement note.

**Why an implementer will get this wrong anyway.** The prose above says *reference it
from both ends*, which is correct and is not literally a count. But anyone building a
gate from that table will count mentions, and counting produces a false positive
whenever one thread's row cites another thread while measuring something — which is
routine here. So the gate's two legs must be tightened **symmetrically**. The seat that
found this had already tightened the epic→row leg — excluding anchor epics, requiring
the tie in title or description — and left the row→epic leg counting bare mentions
anywhere, comments included. It had approvingly quoted `test_plan_records_agree`'s own
docstring hours earlier — *being mentioned is not being anchored* — and then applied it
to one leg and not the other.

**Five iterations of this criterion in one evening: unparented-is-the-defect, then
unparented-AND-unreferenced, then the fourth shape where the row names nothing back,
now a citation is not a reference. Every turn came from someone testing the previous
version against a live row. Not one came from re-reading the rule.**

### The transferable half: write the falsifiable expectation into the record

**A sweep cannot tell a deliberate decision from an omission, and that gap is fixed on
the RECORDING side, not the detecting side.** No amount of detector cleverness
distinguishes "this row is unparented because someone thought about it" from "this row
is unparented because nobody did".

So when you make a deliberate structural decision that will look like a defect to a
later sweep, record it **as an expectation a reviewer can disprove**, not as a summary
they must trust:

- state what the next sweep is expected to see (*"this row will surface as unparented;
  that is expected and here is why"*),
- state **what the genuine finding would be instead** (*"the real defect would be this
  entry present and the row absent, or the row present naming no thread"*),
- and give the baseline figures that would falsify it.

This costs a paragraph and converts a recurring false positive into a check. It also
survives the thing socket messages and panes do not: a reviewer that re-verifies rather
than inheriting conclusions — which is the correct posture for a reviewer — will not
have your conversation, only your record.
