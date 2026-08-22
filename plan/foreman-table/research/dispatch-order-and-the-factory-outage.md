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

- **6** outcomes failed at stage `fabro-run` carrying `os error 28` /
  `No space left on device`
- across **4 distinct plan threads** — `overseer-3h4s5w`, `overseer-54k2za`,
  `overseer-au3pt3`, `overseer-r55y`
- inside an **18-minute window**, `00:23:20Z` to `00:41:26Z`

Four unrelated threads failing identically in eighteen minutes is what makes this
a host condition rather than an item condition.

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

## Next action

Dispatch `overseer-2jblyq.1` and `overseer-2jblyq.3` through the `drive`
operation as `impl:<id>`, via `scripts/detached-dispatch.sh` rather than a
foreground timeout, once the factory host has free disk and master CI has
concluded green. Then `.2`, then `.4` as each prerequisite closes.
