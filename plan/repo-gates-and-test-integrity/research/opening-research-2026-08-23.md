# repo-gates-and-test-integrity — opening research

Thread opened 2026-08-23 by cutting it out of `plan/foreman-actuator-gather-and-roster`
(anchor `overseer-tdfe`). Ledger anchor `overseer-4z97`.

## Why this thread exists

This is the largest cohesive group in the carrier — **14 of its 68 open children** —
and the one least related to the thread that was holding it: **none of it is a foreman
surface at all.** It is the successor population of `plan/test-and-gate-integrity`
(anchor `overseer-hgq4wi`), archived earlier on 2026-08-23; its undischarged
obligations landed in the carrier at archive time and have had no advocate since.

That is the mechanism the carrier convention produces and this cut is undoing: an
archive gate gets its answer by moving residue somewhere with no gate of its own.

## What this thread holds

**The unverified-owner family — one defect, three names.** An enforcement escape hatch
names an owning work-item and then never checks the owner exists or is open:

| item | the hatch |
|---|---|
| `overseer-tdfe.7` | LLOC owner-marker liveness is a hand-maintained allow-list, already green over twelve stale markers |
| `overseer-tdfe.25` | the LLOC soft-band marker accepts a NONEXISTENT work-item — `_probe_marker_liveness` is a no-op — and 27 files now lean on it |
| `overseer-tdfe.20` | `check-no-todo-registry` accepts an entry owned by a CLOSED work-item; 4 of 28 residuals are orphaned and the set is growing |
| `overseer-tdfe.21` | an `unarmed_until` declaration switches a gate OFF pending named ledger work, and nothing verifies that work still exists |

A gate whose escape hatch cannot fail reports green about a premise nobody re-measures.
This repo's `AGENTS.md` records that shape repeatedly under a different heading: a
check that cannot fail, a field that describes the record rather than the world.

**Gates that are reachable from only one path.**

| item | |
|---|---|
| `overseer-x6rhig` | `check-no-lloc-soft-warnings` is enforced ONLY by the pre-push wrapper, so a factory run verifies green under `just check` |
| `overseer-tdfe.23` | retire `check-plan-anchor-declared` from the aggregate and CI (blocked on aggregate-completeness) |

**Evidence integrity of the test suite itself.**

| item | |
|---|---|
| `overseer-tdfe.22` | nothing ever tests the MERGED tree — no merge queue, no base-move re-test; two individually-green PRs reddened master for 70 minutes, 87 seconds apart |
| `overseer-jdo` | the check aggregate is FLAKY under concurrency: a target fails in the full run and passes standalone, observed twice |
| `overseer-awec` | compound-predicate clauses are invisible to the 100% branch-coverage bar; 15 multi-clause predicates unswept |
| `overseer-afaj` | an integration-tier test for the foreman blocking-prompt scenario, replacing its owned TODO coverage entry |
| `overseer-tdfe.1` | prove the un-triaged lane still discriminates — a control for a check that could otherwise pass vacuously |

**The code shape those gates exist to protect.**

| item | |
|---|---|
| `overseer-zc53` | fourteen more functions whose `None` collapses a failure into an absence |
| `overseer-bjrm` | adopt the public-API Result railway so the `pure_trees` un-gating can re-land |
| `overseer-yqza` | `tmp/overseer/` holds 9,953 lines of prose, a groom draft, a staged spec revision and a 22KB patch — the hazard the `tmp/supervisor` rule abolished, in the directory it does not cover |

## Seams with siblings

- **`plan/fleet-plumbing-and-dispatch-reliability`** owns the dispatch path and the
  factory. `overseer-tdfe.22` sits near that seam — a merge queue is CI machinery, and
  the post-merge janitor that surfaced it is dispatch machinery — but the deliverable is
  this repo's own gating, so it is here. If it turns out to need a fleet-wide workflow
  change, hand it over rather than growing a second CI thread.
- **`plan/foreman-actuator-gather-and-roster`** keeps anything whose deliverable is a
  foreman surface. `overseer-afaj` is a test *of* foreman behaviour but its deliverable
  is a test, so it is here.

## Explicit deferrals

- **D1 — the AppArmor / k3s runner work is NOT here.** It is recorded in `AGENTS.md`
  and owned in the `livespec` tenant; a runner-pool change is not this repo's gate.
- **D2 — no SPECIFICATION deliverables are admitted.** Two children in the carrier had
  them and went to `plan/foreman-panel-and-rulings`, which owns those paragraphs. A
  mixed-tier item is split at filing time, never dispatched: the sandbox refuses any
  factory-authored commit touching `SPECIFICATION/` with no escape hatch.

## A caveat on the cut mechanics, stated so it can be falsified

Membership moved by **parent-child edge only** — never a dependency edge, which is the
documented permanently-undispatchable trap. The archive gate additionally matches
children **by id hierarchy** (`plan_child_ids_from_id_hierarchy`, read from the plugin
source): the eight `overseer-tdfe.N` rows above remain gate children of `overseer-tdfe`
regardless of parent, so they are bound to both gates. Expect them to surface in a
sweep of either thread; `overseer-tdfe.9` owns that inconsistency. The genuine finding
would be a child of this anchor that `overseer-tdfe` can archive over.
