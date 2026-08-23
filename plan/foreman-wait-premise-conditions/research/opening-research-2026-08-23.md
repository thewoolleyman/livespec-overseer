# foreman-wait-premise-conditions — opening research

Thread opened 2026-08-23 by cutting it out of `plan/foreman-actuator-gather-and-roster`
(anchor `overseer-tdfe`). Ledger anchor `overseer-1a31`.

## Why this thread exists

It revives `plan/foreman-wait-premises` (anchor `overseer-vszm`, closed 2026-08-22),
whose undischarged obligations moved into the carrier as successor rows and have had no
advocate since. The carrier held **68 open children** when this cut was made.

**This is the only genuinely COUPLED cluster in the carrier.** Everything else there was
decoupled work that happened to share a holding record — the definition of a junk
drawer. These four are the B, C and D children of one run-premise design plus the lint
that gives them a rule to enforce, and they were cut as a chain on purpose. That is the
whole argument for keeping them together rather than draining them individually.

## The premise, in one sentence

A seat that is waiting must be able to state **what it is waiting for**, and the
machinery must notice when that premise **dies** — otherwise a wait is indistinguishable
from a hang, and the fleet's own guidance that "a silent log is not a silent subsystem"
has no mechanical counterpart.

## What this thread holds

| item | | |
|---|---|---|
| `overseer-tdfe.12` (+3 children) | the wait-premise question lint and its prose rule | implementation half of `overseer-au3pt3.9`, rule already ratified |
| `overseer-tdfe.13` | daemon attention condition `wait-target-missing` with remote-aware re-verification | run-premise child **B** |
| `overseer-tdfe.14` | self-healing evidence-carrying relay on dead wait-premises | run-premise child **C** |
| `overseer-tdfe.15` | aggregate attention condition `dispatch-quiet-with-waiters` | run-premise child **D** |

The chain matters: B establishes the per-target condition, C makes the relay carry its
own evidence, D aggregates. Working D first produces an aggregate over a condition that
does not exist yet.

**Remote-awareness is not optional in B and D.** `AGENTS.md` records the measured reason:
a live run on a remote factory shows *nothing* in local `fabro ps`, so a naive
"target missing" verdict reads a healthy remote run as dead and licenses exactly the
re-dispatch that produces a publish-branch collision with the run's own sibling. Any
verification these conditions perform must resolve the item's dispatch factory first.

## Seams with siblings

- **`plan/supervision-safety-and-attention-truth`** owns general daemon attention-state
  truth. This thread owns only the conditions keyed on a **wait premise** — the seam is
  whether the row is about a pane's state or about a declared premise.
- **`plan/foreman-panel-and-rulings`** holds `overseer-tdfe.17`, which covers
  SPECIFICATION v029's convene-obligation *and* wait-premise headings in one item. Its
  wait-premise half must be verified against this thread before that item is called
  done; it is named here so the coverage claim is not accepted from one side only.
- **`plan/fleet-plumbing-and-dispatch-reliability`** owns the dispatch journal these
  conditions read. A defect in the journal's content is theirs; a defect in what a
  condition concludes from it is ours.

## Explicit deferrals

- **D1 — no new attention vocabulary beyond B and D.** The status vocabulary is a
  contract surface; adding entries outside those two conditions routes through
  `propose-change`.
- **D2 — self-healing does not mean self-dispatching.** `overseer-tdfe.14`'s relay
  repairs its own evidence; it must not acquire the ability to re-dispatch work, which
  is the dispatcher's and is gated by rules this thread does not own.

## A caveat on the cut mechanics, stated so it can be falsified

Membership moved by **parent-child edge only** — never a dependency edge, which for
thread membership is the documented permanently-undispatchable trap. The archive gate
additionally matches children by id hierarchy (`plan_child_ids_from_id_hierarchy`, read
from the plugin source), so **all four** of these rows remain gate children of
`overseer-tdfe` regardless of parent. This thread is therefore entirely double-bound.
Expect that in any sweep; `overseer-tdfe.9` owns the inconsistency, and the genuine
finding would be a child of this anchor that `overseer-tdfe` can archive over.
