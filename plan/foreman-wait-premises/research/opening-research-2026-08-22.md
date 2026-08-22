# Wait-premises, the convene obligation, and the consensus-overdue condition

Opening research note for `plan/foreman-wait-premises`. Ledger anchor `overseer-vszm`.

Written 2026-08-22 when this thread was cut out of `plan/foreman-improvements`
(anchor `overseer-au3pt3`) by the grooming drain pass, at the maintainer's
direction and on their selected cut.

## Why this thread exists separately

`overseer-au3pt3` held 38 open children. A dependency scan over all of them found
**exactly three** real `blocks` edges in the whole set — everything else was
parent-child. Two of those three edges are here:

    overseer-au3pt3.5  ->  overseer-au3pt3.6  ->  overseer-au3pt3.8

That chain is the reason this cluster moved as a unit rather than being split
further. `.5` ships the typed wait-premise record (schema + writer + gather
surfacing); `.6` consumes it as a daemon attention condition with remote-aware
re-verification; `.8` aggregates over `.6`'s verification result. Cutting between
them would put a prerequisite in another thread and make the dependent
permanently ungated across a thread boundary.

The other seven children are not edge-coupled to that chain but are the same
SUBJECT — premise hygiene at raise time, premise-file naming, the convene
obligation, and the consensus-overdue condition — which is what makes this a
thread and not a bucket.

## What this thread holds

| child | status at cut | scope |
|---|---|---|
| `overseer-au3pt3.5` | acceptance | typed wait-premise records: schema, writer helper, foreman-gather surfacing |
| `overseer-au3pt3.6` | pending-approval | daemon attention condition `wait-target-missing`, remote-aware re-verification — **blocks on `.5`** |
| `overseer-au3pt3.7` | pending-approval | self-healing evidence-carrying relay on dead wait-premises |
| `overseer-au3pt3.8` | pending-approval | aggregate condition `dispatch-quiet-with-waiters` — **blocks on `.6`** |
| `overseer-au3pt3.9` | ready | picker-premise hygiene at raise time: typed premise embedding + lint |
| `overseer-au3pt3.14` | backlog | cover SPECIFICATION v029's convene-obligation and wait-premise headings with real tests |
| `overseer-au3pt3.15` | ready | ship the report-only consensus-overdue attention condition |
| `overseer-au3pt3.16` | backlog | ship the wait-premise question lint and matching prose update |
| `overseer-r55y` | ready | `wait_premises` filename derivation can silently overwrite a distinct target's record |
| `overseer-a3l6x2` | ready | panel-first discipline: positive convene-criterion + report-only consensus-overdue |

`.15` and `.16` are the implementation halves of `a3l6x2` and of the wait-premise
question lint respectively. Keeping each pair in one thread is deliberate.

## Explicit deferrals — what is NOT in this thread

- **The panel's own failure modes** — reviewer timeouts, empty dossiers, cache
  keys, the typed-ruling vocabulary. Deferred to `plan/foreman-panel-and-consensus`
  (`overseer-6l7v`). This thread decides WHEN a panel must be convened and what a
  waiting premise means; that thread decides how the panel behaves once convened.
  The seam is the convene call.
- **The actuator surface** — `foreman-act`, `plan_start`, `work_item_session_start`.
  Deferred to `plan/foreman-improvements` (`overseer-au3pt3`), which is retained
  as the actuator thread.
- **Seat identity and plan-record parity.** Deferred to
  `plan/foreman-seats-and-plan-records` (`overseer-ow7c`).

## Two acceptance gaps, carried forward deliberately

`overseer-au3pt3.15` and `.16` are the only two open items in this repo with no
acceptance criteria under the merged projection. That is **on purpose** and
predates this thread: both were maintainer-filed with no stated remedy, and `.15`
is a row a previous grooming seat mis-wrote and undertook not to touch again. They
arrive here with that undertaking attached. Do not author bars for them; ask the
maintainer.

## Read first

- `SPECIFICATION/spec.md`, the v029 convene-obligation and wait-premise headings —
  these are the ratified letter `.14` must cover.
- `overseer/AGENTS.md` for the daemon attention-condition mechanics.
- The ledger anchor `overseer-vszm` and each child's own acceptance field.
