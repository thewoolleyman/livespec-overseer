# 001 — Charter, baseline measurements, and the consumption surface

Created 2026-08-26 by the `homelab-loop-hardening-overseer` session. This is
the second of two livespec-overseer threads in homelab's
steady-state-loop-hardening program (plan epic `hl-nkuzaz`), commissioned by
the maintainer 2026-08-26. Its sibling is
`session-start-and-registry-integrity` (this repo, plan epic
`overseer-zidpiu`), which carries matrix 07 and 08.

## Charter

Source: `homelab/plan/steady-state-loop-hardening/research/005-proposed-implementation-plans.md`,
Phase III, second row, plus its Phase IV consumer row and its Phase VI docs
row. Read read-only at `/data/projects/homelab`.

This thread carries matrix section 09, the **consumer halves** of sections
03, 10, 11 and 15, the **consumer half** of section 12 (the probe), and doc
audit items D7 and D8.

**Done means** (verbatim from 005):

> `foreman-runtime` computes starvation deterministically from the snapshot
> and emits the typed session-lifecycle remedy; the seat's capacity/wait
> statements come from the snapshot; drain-daemon vocabulary removed from
> prose. Negative control: a daemon-framed escalation on the starvation
> condition is refused by the classifier.

### Riders

- **Probe consumer (matrix 12).** The foreman gates its loop-is-live claim on
  a passing probe and re-runs it periodically. **Gated**: the primitive is the
  orchestrator's Phase IV `full-cycle-probe` thread, which has not shipped.
  This rider is therefore a recorded deferral until that release exists, not
  work this thread can start.
- **Docs D7/D8.** D7: this repo's README cites the retired
  `plan/<topic>/handoff.md` convention; handoffs are ledger-held plan-epic
  comments and the plan operation never authors `handoff.md`. Legacy files may
  be read only as historical migration input. D8: the README documents only
  `overseerd` and the overseer pane, while the foreman and grooming operator
  surfaces — the ones the operating workflow actually runs on — are specified
  in this repo's SPECIFICATION and prose but absent from the README.

### Gate condition

Phase III is gated on the Phase I/II releases the overseer pins. As of
2026-08-26 that gate HOLDS: orchestrator spec v0.72.10, orchestrator
implementation v0.75.0 and advancing; runtime v0.22.0. The Phase IV probe
primitive is separately gated and does NOT hold — see the deferral above.

## The problems, as the matrix states them

### 09 — The foreman escalated a repair of machinery that does not exist

> Seeing a plan starved past its bound while `ready` children aged, the
> foreman seat escalated "start or repair the Dispatcher drain loop" — but no
> resident drain process exists anywhere in this deployment; `loop` is a
> bounded CLI invocation. The remedy inside its own whitelist — `plan_start`
> toward the plan owning the stuck child — was not taken.

Fix row (internal, livespec-overseer): mechanically, `foreman-runtime`
computes the starvation condition deterministically each tick — plan
unactioned past bound + ready children aging (section 10's snapshot item) + no
live session — and emits the typed remedy proposal (`plan_start` /
`work_item_session_start`) in the tick input; the `foreman-act` classifier
refuses an escalation whose subject is that condition, the same way it already
refuses a mismatched proposal. Prose: the foreman skill states what exists in a
session-driven deployment; the drain-daemon vocabulary goes.

### Consumer halves carried here

- **03** — the foreman's tick reads capacity from the snapshot (or
  `loop --dry-run` output) and never asserts slot state from raw ledger
  statuses, in reports, escalations, or panel dossiers.
- **10** — the foreman's tick reads the ready-work-aging attention item as the
  deterministic trigger for 09's remedy routing, instead of composing a private
  attention view.
- **11** — the foreman's own wait states (open picker, raised escalation, panel
  in progress) are published machine-readably rather than living only under
  `tmp/overseer/foreman/` and in panes. **Constrained by the console triage's
  ruling R1** (`homelab/.../009-console-review-triage.md`): these publish as
  LEDGER STATE on the owning plan epics, NOT into the orchestrator's
  `needs-attention` snapshot. The orchestrator stays overseer-unaware, and
  foreman-origin items reach a console inbox only via a fresh console
  propose-change that explicitly revisits its `v040` boundary — never inherited
  as a side effect of an upstream release. This thread must not design toward
  the matrix's original "same snapshot composes them" wording, which R1
  supersedes.
- **15** — the foreman treats a surfaced detection-staleness item as a routing
  target (an attended session for the owning plan, or the grooming charge) and
  never as something to run itself; the grooming charge names detection
  staleness among what a drain pass checks.

## Baseline measurements

Stamped `2026-08-26T00:32:49Z` (`date -u`), read against the working tree at
`5bab4661` and a live daemon (`daemon_package.version` 1.52.0, `tick_generation`
9248).

### The snapshot is already ingested — the gap is downstream of ingestion

`overseer/foreman_gather_collect.py` already defines `read_needs_attention(...)`
and a `default_needs_attention_command(repo=...)`, collects the result into the
gather document under a `needs_attention` key, and carries a source record for
it (with an `embedded_needs_attention` fallback). So the transport for
03/10/11/15's consumer halves EXISTS. What this thread must build is what the
tick DOES with those facts: the deterministic starvation computation, the typed
remedy emission, and the refusal.

### A NAME COLLISION that will mislead an implementer — record it before it costs someone

`grep -rniE 'starv' overseer/` returns a substantial existing subsystem, and
**none of it is matrix 09's starvation**. The existing vocabulary is
`winddown-starved`: a daemon-side liveness condition about a supervised
session failing to complete its wind-down, with `WINDDOWN_STARVED_AFTER = 2 *
3600.0` in `_supervisor_config.py`, a `winddown_starved_episode` in
`_supervisor_records.py`, `surface_starvation_alert` /
`starvation_evidence_note` in `_supervisor_attention_alerts.py`, a
`winddown-starved` condition string and colour in `_supervisor_view.py`, and
`blocked_starvation_decision` in `_supervisor_attention.py`.

Matrix 09's starvation is a different thing entirely: a **plan** unactioned
past its bound while its `ready` children age with no live session. Its
existing carrier is the foreman's per-plan consecutive-unactioned counter —
`consecutive_unactioned_ticks`, written by `foreman_plan_roster_state.py` and
consumed by `foreman_plan_roster.py` / `foreman_plan_roster_cli.py` — with the
bound described in `.claude-plugin/prose/foreman.md` (proposed values:
2 consecutive unactioned ticks when full autonomy resolves false, 1 when true;
maintainer-owned, not foreman-chosen).

Two subsystems, one word, no overlap. Any ratified name for 09's condition must
not be a bare "starvation", and any implementer told to "compute starvation
deterministically" will land in the wrong subsystem first.

### The drain-daemon vocabulary sweep is narrower than expected — and needs care, not a sed

`grep -rniE 'drain (loop|daemon|process)|resident drain|drain daemon'` over
`.claude-plugin/`, `overseer/` and `SPECIFICATION/` returns exactly TWO hits,
both in `.claude-plugin/prose/foreman.md` (around lines 261-266), in a passage
whose actual subject is holds: "A HOLD OVER A SEAT IS NOT A HOLD OVER THE DRAIN
LOOP", and "peer messages ... do not reach the dispatcher's drain loop."

That passage is **substantively correct** — it is about which carriers a
selector reads — and its "drain loop" reads as the dispatcher's selection pass,
not necessarily as a resident daemon. So the D-fix here is a wording repair that
must preserve the hold-carrier semantics, not a deletion. A mechanical removal
of the phrase would damage a correct rule to satisfy a vocabulary sweep. The
same passage's surrounding text (the `dispatcher.wip_cap == 0` repo-wide hold,
the per-item hold, the absent per-factory carrier) is the part worth keeping
intact.

Note also what the sweep did NOT find: no "resident drain process", no "drain
daemon", and no "start or repair the Dispatcher drain loop" string anywhere in
the tree. The incident's escalation wording was authored by a seat at run time,
not read out of prose. That matters for the fix's shape: the mechanical leg (a
classifier refusal) is what actually prevents recurrence; the prose leg reduces
the chance a seat invents the phrase again, but cannot prevent it alone.

## Explicit deferrals recorded at baseline time

- **The probe consumer (matrix 12)** is deferred until the orchestrator's
  `full-cycle-probe` release exists. Reconsidered when that release is pinned
  here.
- **Publishing foreman wait states into any console-visible inbox** is out of
  scope under R1. This thread publishes to ledger state on plan epics only.

## What this note deliberately does not do

It records no ratified design, no condition name, no schema, and no child work
items. The next action is a scope event cutting requirement carriers and
explicit deferrals, after which the behaviors this repository's SPECIFICATION
must state route through `/livespec:propose-change`, and ledger children carry
the implementation and the docs items.
