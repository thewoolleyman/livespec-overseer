# What actually holds a ledger row — status, dependencies, and the two policy valves

Moved verbatim from `AGENTS.md` §"Lifecycle statuses for `bd update --status`".

### `pending-approval` is NOT a hold here — and LABELS never gate anything

Measured 2026-08-22, from `lane_of`, `is_item_ready` and `_dispatcher_valves.py`,
after two sessions got the generalization wrong in opposite directions.

**THE FINDING.** `pending-approval` does not hold an item in this tenant.
`.livespec.jsonc` sets `auto_approve_ready: true` (maintainer-directed
2026-08-11) and `_dispatcher_loop_selection.is_dispatch_candidate` projects a
`pending-approval` item to `ready` and re-tests it. The config's own comment
records that this repo had been the ONLY governed repo where `pending-approval`
*was* a human valve, so the fleet guidance "pending-approval is not a human
valve" was INVERTED here and had to be special-cased. **That inversion is over.**

**FOR THE READY SET, STATUS IS THE VALVE AND LABELS ARE NOT.**
`is_item_ready` is `lane_of(...).name == "ready"`, and `lane_of`'s docstring is
explicit: the lane IS the stored status with exactly one derived overlay —
stored `blocked` stays blocked, and stored `ready` with any OPEN dependency
renders `blocked:dependency`. **It reads no labels at all.** The
`blocked-reason:` / `admission:` / `acceptance:` labels are a SERIALISATION of
policy fields written by `_store_mutations._work_item_labels`; they annotate,
they never gate. `blocked_reason` is read ONLY to name the reason on an item
already `blocked` — on any other status it is vestigial.

**The empirical control, which is what settles it.** Two independent
tenant-wide scans, run by different seats, each found **seven** items at
`blocked` with NO `needs-human` label, and four carrying `needs-human` while NOT
blocked. (Their totals differed — one counted open rows, the other included
closed — and they reconciled to the same discriminating sets, which is why the
seven are trustworthy and the corpus size is not quoted here.) A "labels are the valve" rule reads all seven
as takeable; `lane_of` holds every one of them on status. One is a 20 KB item
parked awaiting regroom — dispatching it is exactly the mistake that rule
licenses.

**THE TWO VALVES ROUTE ON POLICY FIELDS, NOT ON STATUS OR LABELS.** Per
`_dispatcher_valves.py`, the Dispatcher is the sole enforcer of two valves
bracketing the autonomous middle:

| valve | routes on | scope — read the ONLY, it is load-bearing |
|---|---|---|
| approval `pending-approval → ready` | effective `admission_policy` | gates **that transition ONLY**. `manual` is surfaced for a human, `auto` approved autonomously. **INERT once the row is `ready`** |
| post-merge acceptance `acceptance → done` | effective `acceptance_policy` | `human-only` / `ai-then-human` park until a human confirms; `ai-only` goes autonomously |

**`admission:manual` ON A `ready` ROW HOLDS NOTHING.** The planner's own docstring:
"admission_policy gates only the pending approval transition. Once an item is
ready, admission to active is mechanical." `admission_plan` tests
`item.status == "pending-approval"` and skips the policy branch entirely
otherwise, and `resolve_assignee` returns `item.assignee or DEFAULT_DOER` so it
cannot withhold admission either.

**NO HARMFUL LIVE INSTANCE HAS BEEN DEMONSTRATED, and this note deliberately
does not name one.** A candidate row was put forward and withdrawn: it was
characterised as a maintainer-filed standing decline that the machine would
dispatch anyway, and on inspection it was an ordinary implementation task whose
`ready` status had been set deliberately and reasonably — and which read
`blocked` when checked again an hour later. The mechanism above is read from
source and stands; the demonstration did not. What is established is that the
label is inert, not that the inertness is currently costing anything.

**Do not repair that by finding a better row — the objection is to the FORM, not
to that row.** A state measurement is true of an INSTANT, and a row cited in
durable guidance is a claim that must STAY true. A mechanism read from source
does not rot; a row does. The withdrawn candidate was observed at four different
statuses in one day, twice flipping between `ready` and `blocked` inside four
minutes across two sessions' reads — both correct at their instants, and any
sentence written about it in this file would have been false within the hour.
**Cite the mechanism and give the reader a query; never pin durable guidance to
live mutable state.**

**What IS established, and it is milder: a vestigial hold-reason misleads
people, not machines.** Rows carry `blocked-reason:needs-human` that outlived
its cause — set when a run parked at a human gate, left behind when the row moved
on. `lane_of` ignores it. A human reader does not, and reads the row as held.
That is a records-hygiene defect.

**So check the QUERY, not a row.** A `ready` row carrying `admission:manual` is a
row whose label is inert — look at it, and **if it is genuinely human-held its
status must be `blocked`**, because that is the only thing in this system that
holds a row. A table listing `admission:manual` as a hold without the qualifier
above reproduces that confusion in documentation.

`effective_admission_policy` / `effective_acceptance_policy` apply
per-item-over-global precedence; a non-None `spec_commitment_hint` (spec-change
tier) forces `manual` admission regardless of the repo lever.

**The acceptance default is inverted here, which is what makes the per-item
override load-bearing.** The valve docstring names `ai-then-human` as THE
DEFAULT, and this repo sets `acceptance_mode: "ai-only"` repo-wide — so
post-merge acceptance is autonomous by default, and it is a **per-item
`acceptance_policy` override that RE-ARMS the human leg**. An item at
`acceptance` is therefore not waiting on a person unless it carries that
override.

**SO THE CHECK IS: resolve the effective POLICY for the valve you care about,
and read STATUS plus DEPENDENCIES for the ready set.** Never pattern-match a
label, and never infer a hold from `pending-approval`.

**WHAT PERFORMS THE APPROVAL TRANSITION — and why a row can sit at
`pending-approval` for no reason at all.** Only `admission_plan`, inside a
Dispatcher `dispatch`/`loop` pass, moves an effective-`auto` `pending-approval`
item to `ready` (and may admit it in the same pass). Nothing else does. So an
effective-`auto` item parked at `pending-approval` usually means **no pass has
run** — the dispatcher is gated on master CI being green, among other things.
Do not read such a row as awaiting a human.

**WHY THIS IS RECORDED AT LENGTH: BOTH WRONG RULES SURVIVED REVIEW.** Entries on
`overseer-vr3ym4` justified a wait as "`full_autonomy` is absent from
`.livespec.jsonc` and resolves fail-closed to false" — true of the config, and
not what holds anything. The repair proposed for it, "read the labels instead",
was **also wrong, and wrong in the dangerous direction**: it reads seven blocked
items as takeable. The accurate rule is narrower than either. Same family as the
entries above — `Updated:` is not activity, a PATH's age is not a BEHAVIOUR's
age, a timestamp a session WROTE is not one that was MEASURED — with one
addition: **the repair for an under-specified rule is not a shorter rule.**
