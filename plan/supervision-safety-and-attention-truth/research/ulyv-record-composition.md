# `overseer-ulyv`: record composition, the death of run `01M0KAGT6E…`, and the regroom seam

Measured 2026-08-22 by the `supervision-safety-and-attention-truth` session, after the
third dispatch attempt on `overseer-ulyv` died and the foreman blocked the item pending
regroom.

This note exists **in the plan tree rather than on the item** for the reason it documents:
on a dispatchable child, the evidence record and the dispatch brief are the same object, so
adding this analysis to the item would enlarge the very problem it analyses. The item
carries a short pointer here. The plan epic `overseer-6tfncs` is a plan anchor that is never
handed to the factory, so its handoff entries are free.

## 1. The measurement

| quantity | value |
|---|---|
| stored record (`bd show`) | **145,009** chars |
| of which ledger comments | **134,622** chars across **35** comments |
| goal file actually handed to the run | **136,399** chars (`/tmp/fabro-goal-overseer-ulyv.md`) |
| fleet sizing warning fires at | 1,959 chars |
| sibling item blocked for regroom earlier the same night | 20,252 chars (`overseer-3h4s5w.6`) |

The goal file survives from the dead run, so the brief size is a direct observation and not
an estimate from the record.

**Size is invisible to every pre-flight check this fleet runs.** Status, cleared assignee,
delimiter scan, dependency edges, ready-set membership, master CI, current plugin build —
all seven passed on this record. `bd show <id> | wc -c` is now adopted as a pre-flight by
both the foreman seat and this one.

## 2. The cause is NOT settled — a competing explanation

The foreman attributed the death to the record size, explicitly fenced as an **inference,
not a measurement**. That fence was correct and this note does not remove it. It adds a
competing explanation that was not available when it was written.

**A fleet-wide factory disturbance existed in the same window.** Between 00:23Z and 00:51Z,
seven unrelated dispatches failed *instantly* at `fabro-run`:

    overseer-54k2za.13, overseer-54k2za.21, overseer-54k2za.11, overseer-3h4s5w.9,
    overseer-r55y, overseer-au3pt3.15, overseer-temi26.2

None is an oversized item; several went green on re-dispatch within the hour, and the
factory produced greens steadily again from about 01:07Z. This run's sandbox stopped at
**00:15:44Z**, on that window's leading edge, and from 00:17:42Z it emitted
`worker lost canonical run store during append run event` every two minutes.

**One datum excludes the simplest form of the size theory.** The 136KB goal was *accepted*:
fabro parsed it, the run entered `implement`, and it produced events for about seventeen
minutes. It did not fail at goal-assembly or goal-parse time. So "too large to hand over" is
out; only "too large to work with" survives, and nothing here supports or refutes that.

**What is NOT claimed.** This run went quiet at 23:46:52Z, roughly half an hour *before* the
burst, and that gap is unexplained by the disturbance. This is a competing explanation, not
a refutation.

**Why it matters even though the remedy is unchanged.** A 145KB brief is worth cutting on
its own merits, so blocking for regroom is right either way. What would be wrong is
recording size as the *diagnosed* cause: a later reader who regrooms, re-dispatches, and
dies again on a factory-side event would have no reason left to look.

## 3. `fabro ps` was the thing that lied — and so was the verdict file

The foreman's Finding 1 deserves restating because it defeats a discriminator every
dispatch-trap entry in `AGENTS.md` rests on. `fabro ps` listed this zombie as `running` at
296 minutes, four hours after its last event.

**The same lie reached the detached-dispatch verdict file.** This seat armed a watch on
`verdict.env`, which read `status=running` for those same four hours — the helper only
rewrites it when the launched command *exits*, and the launcher was still blocked on a run
that would never finish. A watcher on that file cannot detect a run that dies without its
launcher exiting.

**The discriminator that works** is the run's own newest event timestamp against wall clock.
A run whose newest event is hours old is dead regardless of what any status field advertises.

## 4. What the 134KB is actually made of

Grouping the 35 comments by what they are *about*:

| bucket | chars | share | carry to a slice? |
|---|---|---|---|
| PR 1348 publish-lane and merge-conflict saga | **37,435** | 28% | **no** — closed PR, deleted branch |
| Consensus-panel record on answering the picker | **13,224** | 10% | **no** — operational decision, not implementation |
| Run/dispatch process records (dispatched, disposed, reaped, gates) | ~16,000 | 12% | **no** |
| Acting-safety design, measurement and verification | ~49,500 | 37% | **yes** |
| Reporting-half evidence | 9,525 | 7% | **yes** |

**The single largest bucket is about an artifact that no longer exists.** Eleven comments —
01:26 through 02:36, plus 04:31 and 07:06 on 2026-08-21 — track a branch that has since been
deliberately closed and deleted. They carry no implementation value for a re-dispatch.

### Supersession — comments that are already answered by later ones

- **10:50 (code-path analysis)** proposes keying the re-send on `input_box_text`. **Explicitly
  withdrawn** by 21:59 — it depends on the same failing `_is_border` predicate. The
  structural point survives; the fix shape must not be implemented.
- **22:07 (orphan reconciliation)** is superseded in part by **22:11**: the orphan set was
  cleared, so the fixture must be *constructed*, not harvested.
- **Exposure figures** in comments before 22:01 count *alerts* (ticks), not keystrokes.
  22:01 corrects them by the factor of 8. Any earlier figure is wrong by an order of
  magnitude.
- **13:37 (Codex cause hold)** is discharged by the 23:28 gate-discharge measurement, which
  excluded the exhausted-window hypothesis.
- **06:36 (disposal ruling)** is subsumed by **07:58 (disposal record)**, which also carries
  the recoverable SHA and what is worth recovering from it.

## 5. The regroom seam

The acceptance splits cleanly along the two defect surfaces the item has always had. The
21:59 design note establishes that the budget, the identity gate and the exhaustion report
are all **predicate-independent**, and `overseer-gdwkdf`'s detector fix is already on master,
so no slice depends on another or on `gdwkdf`.

| slice | criteria | load-bearing comments | est. brief |
|---|---|---|---|
| **A1** episode-scoped keystroke budget | 4, 11, 12 | 21:59 (design A), 22:01 (two-part bound), 04:53 (defect B), 07:58 (recoverable budget design) | ~23K |
| **A2** identity gate, mismatch *and* absent | 8, 9, 10, 13, 14, 15 | 10:53, 22:07, 22:11, 04:53 (defect A), 07:58 (identity plumbing) | ~26K |
| **A3** no keystroke to a progressing pane, exhaustion report | 1, 2, 3 | 10:50 (structure only), 21:45, 21:55, 21:59 (design B) | ~20K |
| **R** reporting half | 5, 6, 7 | 16:30, 17:29 | ~9.5K |

### The prune alone is not sufficient — state this plainly to the groom

Dropping every dead-artifact and process comment takes the record from **145K to roughly
62K**. That is still **three times** the size at which `overseer-3h4s5w.6` was blocked for
regroom the same night. So the regroom cannot be only a supersession prune.

Two comments are needed by *more than one* slice — **21:59 (8,362)** and **04:53 (9,298)**,
17,660 chars between them. Copying either whole into every slice that needs it is exactly the
duplication the foreman warned against. These two are the ones that must be **distilled into
per-slice extracts** rather than carried intact; they are the highest-leverage editing target
in the whole regroom.

## 6. Standing instruction for this thread

This thread is a heavy writer of exactly the kind of long, careful evidence that inflated
this record — this session's own 23:28 comment is 7,082 chars, the second-largest single
comment on the item and about 5% of the brief it then dispatched.

**Long evidence belongs on the plan epic or in this directory. A dispatchable child carries a
short pointer.** The general defect — that the evidence record and the dispatch brief are the
same object, so diligence on the first silently degrades the second — is being carried to the
orchestrator tenant as a goal-assembly question by the `foreman-full-autonomy-option` seat on
`overseer-3h4s5w.6`. "Write less" is the wrong remedy; routing by destination is the right
one.
