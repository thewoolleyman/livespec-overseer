# Rung 3, first gate: the corpus measurement

Measured 2026-08-03 for `overseer-oydugu`. The item forbids writing any rule
before the corpus is measured, because *"the false positive was always data or
prose that legitimately RESEMBLES the defect"* is the family that killed four
gates on the originating thread. This note is that measurement. **Read it before
touching the detector; three of its findings contradict the item's own premises.**

## The corpus, and exactly where it is

Two supervisor sessions, both `cwd=/data/projects/livespec-overseer`, both from
the `supervisor-prompt-quality` thread's supervisor pane:

| transcript | span (UTC) | records |
|---|---|---|
| `~/.claude/projects/-data-projects-livespec-overseer/d0bdaa90-adc2-46c8-9335-2ece8011ecf1.jsonl` | 2026-08-02T00:37:15Z → 06:11:28Z | 1479 |
| `~/.claude/projects/-data-projects-livespec-overseer/d09b9e77-a852-4342-8efc-f1069a218bf2.jsonl` | 2026-08-02T06:12:25Z → 21:56:46Z | 833 |

The first holds the whole C20 episode. The named turns:

| role in the acceptance | record | timestamp |
|---|---|---|
| **RED** — four ripe valves as prose | msg at line 756–757 | `03:15:44Z` |
| maintainer's correction | line 760 | `03:17:53Z` |
| the correction, restated with a direct question | line 768 | `03:18:16Z` |
| **GREEN control** — the answering turn | lines 779–780 | `03:18:45Z`–`03:19:50Z` |
| GREEN — three correct pickers, all BEFORE the violation | lines 274, 434, 542 | `00:51`, `02:29`, `02:38` |

Those three are the ones the supervisor itself cited: *"the batched 3-valve call,
the repo-ownership question, the epic-filing consent."*

## Finding 1 — TURN granularity cannot discriminate, and this kills the obvious rule

A "turn" bounded by maintainer inputs is the unit the charter names: *"A ripe
valve is raised in the same turn it becomes ripe."* In an autonomous supervisor
loop a turn is **hours** long. Segmenting `d0bdaa90` on real maintainer inputs
yields seven turns for a 5.5-hour session, and **the turn containing the
violation also contains two correct `AskUserQuestion` calls** (lines 434 and 542,
raised 45 minutes earlier).

So "did this turn contain a picker?" answers **yes** for the RED. A gate written
at turn granularity is not merely imprecise — it is inverted, and it would have
passed the one violation we know about.

## Finding 2 — the STOP MESSAGE is the unit, and it discriminates perfectly

The unit that works is the **stop message**: the last assistant message of a
turn, the one that hands control back to the maintainer. There is exactly one per
turn, and it is where a supervisor either opens a valve or fails to.

Eleven stop messages across both sessions. A detector keying on *"the stop
message contains a heading in which the supervisor declares it is handing a
decision to the maintainer"* fires on **1 of 11** — record 756, the true
violation, on `## What needs your direction`. Ten true negatives, zero false
positives.

## Finding 3 — the feared false positive DOES NOT EXIST, and the item is wrong about it

This is the finding that unblocks the whole slice, and it inverts the item's
central premise. `overseer-oydugu` and charter correction C20 both assert that
the answering turn is *"prose, question marks, no picker, and correct"* — the
control that a naive detector would wrongly flag.

**Measured: that turn contains a picker.** The answering prose (record 779) and
the `AskUserQuestion` call (record 780) share one `message.id`
(`msg_011CddCXJYd55gWx8AXDy9nN`) — they are ONE assistant message. The supervisor
answered in prose and opened the valve in the same breath, which is precisely
what C20 prescribes: *"answer the question in prose, then raise every ripe
decision in one AskUserQuestion."* It did the right thing and then described
itself as having done a risky thing.

So the "prose that legitimately resembles the defect" hazard was inferred from
the rendered text, never measured against the record. At message granularity the
answering turn and the violation are not similar at all: one carries a picker,
the other carries none and stops.

**The load-bearing control is still load-bearing** — it just passes for a
stronger reason than expected, and it is asserted in both directions: the fixture
must CONTAIN that message, and the detector must not flag it. An "empty result is
not a finding": a control that passes because the fixture is missing proves
nothing.

## Finding 4 — what the detector must NOT key on, measured

Six of the ten clean stop messages mention maintainer-owned decisions in passing:
*"Still yours: `overseer-yho.3` … release #360"*; *"that's your call, not mine"*;
*"someone should decide whether that work is wanted"*; *"Say the word if you want
…"*. All six are **correct** — the charter escalates only genuinely BLOCKING
decisions, and these are informational restatements. One says so explicitly:
*"Already surfaced at close — restating, not re-asking."*

So a lexical sweep for second-person decision language flags 7 of 11 and is
useless. **The signal is not that a decision is mentioned. It is that the
supervisor SIGNPOSTS a section as soliciting direction and then stops.** The gate
reads the actor's own declaration of intent rather than inferring intent — which
is why it escapes the "intent is not reliably in the text" objection that the
item raises. When a supervisor writes a heading meaning *these are for you to
decide*, intent is in the text, explicitly, authored by the actor being gated.

## What is NOT established

**Recall is unmeasured, and cannot be measured from this corpus** — exactly one
true positive exists. Precision is 1/1 with ten true negatives; recall is 1/1 of
a sample of size one, which is not evidence. A violation phrased without a
signposting heading is invisible to this detector by construction.

That is a real ceiling and it is stated rather than hidden. It is also the
correct first cut: a precision-first gate that never cries wolf can be widened as
new positives are recorded, whereas a recall-first gate that flags the six benign
mentions above would be discounted within a day — the exact fate the epic's
own record predicts for advisory rules.
