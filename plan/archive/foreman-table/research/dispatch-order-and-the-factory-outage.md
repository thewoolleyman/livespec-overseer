# The child gating order, the ratified full-autonomy correction, and a dispatch failure that is in no trap table

Second research note for `plan/foreman-table`. Written 2026-08-22 after the four
implementation children were filed, when three things landed within about
twenty minutes of each other and changed what "ready to execute" meant.

## 1. The gating order, which is the decision record for this thread

Four children, all P1, all `ready`, all citing
`plan/foreman-table/research/hourly-plan-roster.md` as read-first.

| child | scope | prerequisite | dispatchable |
|---|---|---|---|
| `overseer-2jblyq.1` | roster helper: `plan/`-driven row set, daemon left join, three-way name-identity verdict | none | yes |
| `overseer-2jblyq.3` | prose: placement, columns, budgets, legend, narrow list-once exemption | none | yes |
| `overseer-2jblyq.2` | per-plan unactioned counters, once-per-tick emission guard | `.1` | gated |
| `overseer-2jblyq.4` | column 4 closed set, obligation table, starvation bound | `.2` **and** `overseer-3h4s5w.2` | gated |

Verified from the ranker rather than argued from the edges: `.1` and `.3` are
candidates, `.2` and `.4` are correctly excluded while their prerequisites are
open. Dependency direction was read from the raw JSON — `.1` appears inside
`.2`'s own dependency set, not the reverse.

**A parse artifact nearly became a finding here, and the near-miss is the
transferable part.** The first candidacy probe reported all four as NOT in the
ready set — character for character the signature of a broken dependency edge,
whose documented remedy is to inspect and possibly unset edges. The cause was
that `next.py` returns its rows under `candidates`, and the probe read a
non-existent `actions` key, so zero rows parsed as zero candidates. Believing it
would have led to unsetting four healthy edges. **Prove the query shape before
treating an absence as a finding** — the same rule this repo already records for
`bd` JSON, arriving here through a different tool.

## 2. `full_autonomy` was ratified mid-thread, and it falsified child `.4`

The first research note recorded, measured, that `full_autonomy` had zero
occurrences across all four fleet checkouts, and deferred defining it to the
sibling thread. That deferral was correct and remains correct. What changed is
the deferral's own condition.

Timeline, all 2026-08-22:

- `2c8381b docs(spec): propose full_autonomy and the panel decision rule` — a
  proposal in `SPECIFICATION/proposed_changes/`, 0 occurrences in ratified
  `spec.md`.
- `e20ee6e docs(spec): ratify full_autonomy and the panel decision rule as v030`
  — **ratified**, 13 occurrences in `origin/master:SPECIFICATION/spec.md`.

**The ratified model is two orthogonal axes, and child `.4` had been filed
against one axis.** `.4` modelled full autonomy as a fourth value on the
valve-disposition tier. The ratified text instead makes `full_autonomy` a
BOOLEAN, read fail-closed, which when true forces the effective disposition to
`consensus` and the effective decision rule to `majority` *regardless of the
disposition key* — so the disposition key is consulted only when full autonomy is
false. A configuration declaring full autonomy true alongside an explicit
`report-only` is contradictory, and the contradiction must be SURFACED rather
than silently resolved toward the cautious reading.

The consequence for column 4 is not cosmetic. Under full autonomy the floor
categories this specification OWNS become panel-decidable under the majority
rule, so the admissible answer "human-gated by design" stops being available for
them — the foreman must convene the panel instead. It survives only for the four
floors that hold under full autonomy (the cardinal rule, actuator-only mutation,
the security dissent, journal-before-act) and for floors bound by reference from
another contract.

`.4` was rewritten against the ratified text and re-gated behind
`overseer-3h4s5w.2`, the resolver that exposes the value, the decision rule and
the conflict indicator it must key on.

**The lesson worth carrying past this thread:** a deferral names a condition, and
conditions get met while the deferring work sits in a ready queue. `.4` was filed
correct and became wrong in about forty minutes without anyone touching it.
**Re-read a deferral's condition before dispatching the item that depends on
it**, not only when opening the thread.

## 3. A dispatch failure signature that appears in NO documented trap table

Dispatch was held on 2026-08-22 because the repo's default factory host was at
100 percent disk. Measured from `tmp/fabro-dispatch-journal.jsonl`:

| read | when | disk-caused outcomes | distinct items |
|---|---|---|---|
| this thread | ~`00:47Z` | 6 | 4 threads, window `00:23:20Z`-`00:41:26Z` |
| `livespec-overseer-foreman` | `00:55:17Z` | **14** | **7 items** |

**Keep both readings with their stamps rather than only the larger one.** They
were taken eight minutes apart on the same instrument, and the earlier one was
correct when taken. The PAIR carries information the larger number alone does
not: the count grew while nothing was being dispatched from either seat, which
shows an outage still in progress rather than a burst that had already ended.
A single later figure would have read as a worse snapshot of the same moment.

Several unrelated threads failing identically inside a short window is what makes
this a host condition rather than an item condition.

**Why it deserves recording: every observable points at your item.** The error
names a per-item run directory, `drive` exits 1, the dispatcher exits 1, no fabro
run is created, and a phantom `active`/`fabro` claim is left behind to release by
hand. Read against this repo's existing dispatch-trap table, that four-way
reading collides with the anchor-as-dependency row, whose remedy is to go looking
at dependency edges — edges that are perfectly healthy. The discriminator is not
in the exit codes at all; it is `os error 28` in the journal outcome, and the
blast radius across unrelated threads.

**The cheap check before diagnosing any dispatch failure**, alongside the
existing "check master CI first" rule:

    grep -c "os error 28" tmp/fabro-dispatch-journal.jsonl

A non-zero count against recent outcomes on unrelated items means the host is
full and no item-level remedy applies. The incident itself is owned by a
dedicated worker; this note records only the SIGNATURE, so the next thread to
meet it spends seconds rather than reproducing four dead dispatches.

Master CI was independently not settled in the same window — a run in progress at
`e20ee6eb` — and the dispatcher refuses when latest master CI is not proven
green, so the hold was correct on two independent grounds.

## 4. A tripwire on this thread's own deferral, which is currently dormant

Recorded because it is a live conditional with an empty domain, and those are
exactly the claims that get lost: it is true, it is unfalsifiable today, and
nothing about the present tree will remind anyone of it.

While correcting child `.4`, this thread warned a peer seat that its recent panel
rulings might be superseded — reasoning that under full autonomy the floor
categories the specification OWNS become panel-decidable, so a ruling resting on
one of them being human-gated would no longer hold.

**The warning was withdrawn, and the mechanism was sound.** What defeats it is
domain, not logic. spec.md v030 states verbatim: *"This specification defines no
floor category of its own at this revision"* — both categories are bound BY
REFERENCE and MUST stay escalated under full autonomy until the owning contract
ratifies a relaxation. The set the warning ranges over is EMPTY, so no ruling
could have rested on a member of it. Verified against the ratified text rather
than taken on report, and independently confirmed on the peer's side by measuring
the affected items' labels — `acceptance:ai-then-human` and a human blocked-reason,
both orchestrator-contract classes bound by reference — which settles it without
reference to how full autonomy is configured.

**THE TRIPWIRE.** v030 also says: *"Should this specification later define a floor
category of its own, that category is panel-decidable under the majority rule
unless the clause defining it says otherwise."* The moment a successor revision
defines such a category, the withdrawn warning becomes LIVE: prior rulings that
disposed of a decision in that category as human-gated need re-examining, and
child `.4`'s prose must gain the handling it was explicitly forbidden from
writing while the set was empty.

    git show origin/master:SPECIFICATION/spec.md | grep -n "defines no floor category"

While that sentence is present, the domain is empty and `.4`'s prose is correct
to say so. When it disappears or is qualified, this section is the reason to look.

**Why this belongs in the record at all.** It is the same shape as this thread's
central lesson, one turn further out. A deferral names a condition and the
condition gets met; here a WITHDRAWN warning names a condition and the condition
may get met later. In both cases the claim was correct when made and the world
moved underneath it. The difference is that a deferral has an item waiting on it,
so someone eventually re-reads it, whereas a withdrawn warning has nothing
watching it by construction — which is precisely why it needs writing down.

## Next action

Dispatch `overseer-2jblyq.1` and `overseer-2jblyq.3` through the `drive`
operation as `impl:<id>`, via `scripts/detached-dispatch.sh` rather than a
foreground timeout, once the factory host has free disk and master CI has
concluded green. Then `.2`, then `.4` as each prerequisite closes.
