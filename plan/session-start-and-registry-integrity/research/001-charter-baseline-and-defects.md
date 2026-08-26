# 001 — Charter, baseline measurements, and the two defects

Created 2026-08-26 by the `homelab-loop-hardening-overseer` session. This
thread is the livespec-overseer leg of homelab's steady-state-loop-hardening
program (plan epic `hl-nkuzaz`), commissioned by the maintainer 2026-08-26 as
the fifth and last-staffed sibling of the runtime / orchestrator / console /
core legs.

## Charter

Source: `homelab/plan/steady-state-loop-hardening/research/005-proposed-implementation-plans.md`,
Phase III, first row. Read read-only at `/data/projects/homelab`; nothing is
forked into homelab, and this thread runs entirely through this repository's
own governed livespec lifecycle (plan thread -> propose-change -> revise ->
implement).

This thread carries matrix sections 07 and 08 from
`homelab/plan/steady-state-loop-hardening/research/002-problem-and-fix-matrix.md`.

**Done means** (verbatim from 005):

> `foreman-act` journals start-intent (with invoker) before spawning; failed
> starts are visible records; `overseerd` registry rows validate at write.
> Negative controls: a killed spawn leaves an attempted-and-failed record; a
> malformed row is refused.

The sibling thread `foreman-fact-consumption` carries matrix 09 plus the
consumer halves of 03/10/11/15, the probe consumer (matrix 12), and docs
D7/D8. This thread does not.

### Gate condition

Phase III is gated on the Phase I/II releases the overseer pins. As of
2026-08-26 that gate HOLDS: orchestrator spec v0.72.10, orchestrator
implementation v0.75.0 and advancing; runtime v0.22.0.

## The two problems, as the matrix states them

### 07 — A worker-session start that dies leaves no record it was tried

> Worker sessions are started through `foreman-act` (`plan_start`,
> `work_item_session_start`) which spawns a tmux session that `overseerd`
> then tracks. In the incident, one plan's session start produced a running
> session; a second start attempt left nothing but a `session-gone` row in
> the daemon snapshot — no journal record, no error, no evidence it was
> attempted.

Fix row (internal, livespec-overseer): `foreman-act` journals start-intent
BEFORE spawning (action id, target plan, invoker per section 06), then the
outcome; `overseerd` registers the attempt at intent time, so a spawn that
dies becomes a visible "attempted and failed" record carrying the error —
never a bare `session-gone`.

### 08 — overseerd's restart registry accepts records it cannot act on

> Two registry rows were malformed — the homelab foreman row missing its
> timestamp field, the grooming seat row missing its ledger epic link — and
> each malformation silently disables auto-restart for that session. Nothing
> checks rows when they are written; the loss is discovered only when a
> restart fails to happen.

Fix row (internal, livespec-overseer): validate registry rows against their
schema at write time — refuse the malformed write with the field named — and
compose any row that somehow persists malformed into the attention output
rather than skipping it silently.

## Baseline: reproduce-or-refute the two live motivating cases

The program named two live cases to reproduce as this thread's baseline:

1. The `overseerd` track registry carried NO plan-epic id for the **runtime**
   track (homelab `hl-nkuzaz` handoff 27).
2. The **orchestrator**'s registry row was reported missing its epic id
   AGAIN after verification (handoff 28).

### Measurement

Instrument: direct read of the mapping store `~/.livespec-overseer.jsonl`.
Stamped `2026-08-26T00:32:49Z` (`date -u`), against a live daemon —
`~/.livespec-overseer-status.json` reported `daemon_package.version` 1.52.0,
`tick_generation` 9248, `written_at` 2026-08-26T00:32:40Z.

**Result: both specific cases are REFUTED at the present instant.** All 46
rows in the store carry a non-null `epic`. Specifically:

| row | repo | kind | topic | epic |
|---|---|---|---|---|
| 43 | livespec-runtime | plan | `homelab-loop-hardening-runtime` | `livespec-runtime-mqsxsu` |
| 44 | livespec-orchestrator-beads-fabro | plan | `homelab-loop-hardening-orchestrator` | `bd-ib-ujihbw` |
| 45 | livespec-console-beads-fabro | plan | `homelab-loop-hardening-console` | `livespec-console-beads-fabro-ddfbcx` |

Both named rows were repaired by hand between the handoffs and this reading.

**A refutation of a state claim is not a refutation of the defect.** Per this
repo's own standing rule — a field describes the RECORD, not the WORLD, and a
state measurement is true of an INSTANT — the correct reading is: the ROWS
were repaired; the WRITE PATH was not changed. Handoff 28's report that the
orchestrator row was missing its epic id *again, after verification* is the
strongest available evidence for exactly that: hand repair does not hold,
because nothing refuses the malformed write. That is precisely matrix 08's
claim, and this baseline neither weakens nor strengthens it — it dates it.

### What the code says, which does not rot

Read at the same instant, in `overseer/`:

- `_registry_null_epic_audit.py` (`audit_null_epics`) classifies raw
  `epic: null` rows as `documented-null` (carrying a non-empty
  `epic_null_audit` field) or `undocumented-null`. This is an **audit after
  the fact**, deliberately reading raw rows because `read_valid_mapping`
  projects a raw null plan epic to an unresolved sentinel.
- The upsert write path — `_registry_upsert_fields.apply_upsert_update_fields`
  into `_registry_store_upsert_write.write_upsert_rows` — applies field
  mutations and writes, with no schema validation of the resulting row and no
  refusal. `write_upsert_rows`'s only failure mode is `OSError`.
- `_registry_row_fields.py` decodes fields defensively at READ time: a
  malformed `model_profile` is dropped with a warning and the row survives; a
  non-int `ctx_threshold` silently means "no override". Read-time tolerance is
  correct for its purpose and is the opposite of a write-time gate.

So the audit surface for 08's second clause (compose a persisted malformed row
into attention output) partially exists; the write-time refusal — the first and
load-bearing clause — does not.

### A third row worth naming

Row 34 carries `epic: "legacy-unresolved:model-mismatch-veto-residue"` — a
sentinel string in the epic field, not a ledger id. Whatever schema this
thread ratifies must rule on sentinels explicitly: a validator that accepts any
non-null string admits this row, and one that requires a resolvable ledger id
refuses it. Deciding that is in scope; it is the kind of case a schema written
only against the two motivating rows would miss.

### Scope note recorded at baseline time

`~/.livespec-overseer-repos.json` shows livespec-overseer itself is currently
on the maintainer-declared 2026-08-24 watch HOLD (partially lifted 2026-08-25
for livespec, orchestrator, console, runtime, and homelab). This thread's
deliverables are code and spec in this repository; it does not require this
repo to be watched, and it must not lift that hold as a side effect.

## What this note deliberately does not do

It records no ratified design, no schema, and no child work items. The next
action is a scope event cutting requirement carriers and explicit deferrals,
after which matrix 07 and 08 route through `/livespec:propose-change` for the
behaviors this repository's SPECIFICATION must state, and ledger children
carry the implementation.
