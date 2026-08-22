# Why a prose-question detector must be forbidden, not merely controlled

Evidence note for `overseer-j2vbcq` criterion 6 (the prohibition on inferring a
pending human decision from the natural-language content of a pane capture).

Measured 2026-08-22. Recorded here rather than on the item because that item
stands at 17,937 bytes against this fleet's 20,252-byte regroom threshold, and
on a dispatchable child the evidence record and the dispatch brief are the same
object.

## The question this note settles

`overseer-j2vbcq` reports that a session parked on a human authorization posed
in PROSE — no picker frame, no numbered-cursor marker, an ordinary free prompt —
is invisible to the attention surface. One tempting remedy is a detector that
recognises a question in the pane text.

The item forbids that. The prohibition looks over-strict, because a heuristic
with a false-positive control is ordinary engineering practice, and the item's
original filer explicitly permitted one. This note records why the control is
not sufficient, so an implementer who reaches for the heuristic anyway can see
the argument rather than re-deriving it.

## The weaker argument, which is true but insufficient

Sibling `overseer-i6eu2k`, filed by the foreman seat at 2026-08-22T00:41Z,
records the daemon marking `picker_open` true for a session that merely QUOTED
picker markers in prose while describing a PEER's picker. The detector matched a
checkbox glyph, a caret-option line and a selection footer — all genuine markers,
all appearing inside a narrative about someone else's pane. The healthy session
was published as `blocked:human` and became unreachable under the foreman's own
rule against sending to a parked row.

That establishes the class: reading a structured marker out of prose already
produces false positives here. Recognising an unstructured QUESTION is strictly
harder, since it has no markers at all.

This argument supports a stronger control. It does not, by itself, support a
prohibition.

## The argument that does: the corpus is written by the behaviour we want

The livespec-overseer foreman seat supplied a live specimen against itself on
2026-08-22 at 10:34Z, and it is the reason the prohibition stands.

On that tick the foreman escalated two force-push pickers. To make each
escalation checkable by whoever received it, it quoted the option text verbatim
into its own record and into three peer messages:

    How should it be landed?
    1. Force-push the rebase
    3. Hand it to the foreman

A prose-question detector reading the foreman's pane at that moment would mark
THE FOREMAN SEAT as awaiting a human. Under the no-send-to-a-parked-row rule,
the seat whose entire function is routing becomes unroutable — and it does so
BY DOING ITS JOB WELL. Quoting the options verbatim is what made the escalation
verifiable rather than a summary the recipient had to trust.

**That is not a false-positive rate. It is an inversion.** The detector's match
rate rises with how thoroughly a session documents the questions it is holding,
and thorough documentation of pending questions is among the behaviours this
fleet most wants to encourage. A control samples the corpus; it cannot fix a
detector whose errors concentrate on the corpus's best-written members.

## Why a control specifically cannot rescue it

A false-positive control proves the detector rejects at least one non-wait that
looks like a wait. That is a statement about a sample. The defect here is
structural and survives any sample:

- The false positives are not randomly distributed. They cluster on escalation
  records, handoff entries, ledger comments, research notes and peer messages —
  precisely the artifacts this fleet produces when supervision is working.
- The cost is asymmetric and lands on the routing layer. A missed wait leaves a
  row looking healthy, which is today's known state. A false wait makes a
  HEALTHY seat unreachable, and the more central the seat, the more likely it is
  to be writing about pending questions.
- The corpus is adversarial by construction, without anyone intending it. This
  repo's guidance already documents the same shape twice — the delimiter-token
  trap, where quoting the failing bytes poisons the report, and the GitHub
  rate-limit guard, where writing prose ABOUT the guard trips it. In each case
  the document describing a hazard becomes an instance of it.

## The adversarial corpus is not historical: a same-day reproduction

The bullet above cites this repo's rate-limit guard as a prior instance of the
same shape. That citation was historical when written. It was reproduced the
same day, twice, by the foreman seat, and the second instance is sharper than
the documented one.

Measured 2026-08-22 at 10:11:51Z and 10:27:20Z. Neither denied command was a
polling loop:

- The first was a short shell loop over two pull-request numbers, invoking the
  GitHub CLI's pull-request view subcommand once per number. It matched because
  the guard requires a GitHub read AND a loop keyword, and both were present --
  a defensible match on a command that was nonetheless not polling anything.

- The second contained **no GitHub invocation at all**. It was a one-line Python
  parse of a file that had already been fetched, and its only match was the word
  `for` appearing inside a list comprehension. The guard reads the command
  string, not the intent, and an ordinary iteration keyword was enough.

Both fired while that seat was investigating a red pull request on another
track's critical path -- which is to say, during exactly the careful work the
guard exists to protect.

**Why this belongs in a note about prose detectors.** It is the same failure in a
different detector: a matcher keyed on surface text, firing on a document or a
command whose only offence is discussing or resembling the thing being matched.
The rate-limit guard has the easier problem -- it matches literal tokens in a
command string rather than intent in free prose -- and it still produces this.
A prose-question detector inherits the same failure with none of the structure.

**This note is not an argument against that guard**, and should not be cited as
one. It does real work against genuine polling, its author's remedies are sound,
and the seat that supplied these two instances said plainly it would not want the
guard weakened. The point is narrower: a text matcher's false positives land on
the people documenting and investigating carefully, and no control removes that
because those people write the corpus.

## What to build instead

`overseer-j2vbcq`'s rewritten acceptance routes around detection entirely:

- The **compliance leg** uses the channel that already exists. `human_wait` is
  `obs.gate or claude_status == "waiting" or obs.blocked is not None`
  (`overseer/_supervisor_progress.py:80-84`), and the third input is the
  session's own state-file declaration (`overseer/_supervisor_observe.py:316`) —
  pane-independent by construction, and therefore immune to everything above.
  `overseer/marker-protocol.md` already mandates `blocked: <reason>` for a human
  wait no structured gate can carry, and `SPECIFICATION/spec.md` forbids
  conditioning that declaration on structured-question capability.

- The **non-declaration leg** addresses the real gap, which is not detection.
  The daemon cannot separate "nothing pending" from "pending but undeclared", so
  a session that answers the idle nudge conversationally without ever declaring
  is unbounded. That leg requires a BOUND, not merely a condition — this epic
  already carries two unbounded-shield defects, `overseer-t6m` and
  `overseer-94fs`, and an unbounded fix here would be the third.

Both legs key on what a session DECLARES, never on what its pane SAYS. That is
the whole design intent of the prohibition.

## Provenance

The inversion argument and the specimen are the livespec-overseer foreman seat's,
offered after it verified the four source claims above in the tree and withdrew
its own causal framing. The prohibition and the acceptance rewrite are this plan
thread's. Neither seat produced this reading alone: the foreman had the specimen
and had permitted the heuristic; this thread had the prohibition and the weaker
argument for it.
