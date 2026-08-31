# Instrument the caam-anthropic-loop with OTel-compatible telemetry

## Why (the motivating incident)

The caam model-enforcement pass drives the `/model` picker into live foreman panes.
On 2026-08-30/31 it repeatedly re-drove `livespec-overseer-foreman` though it was
already on Fable. Root-causing this took hours and reduced to reading ONE ambiguous
line out of terminal scrollback:

    models: foremen want fable (...); livespec-overseer-foreman unknown->fable

`unknown->fable` meant the transcript sensor read the pane's model as `None`
(unknown), so enforcement drove the picker. There was **no queryable record** of:
which session/transcript the sensor resolved, what model it read (and from which
signal), the `want`, the decision (`skip`/`drive`/`would`/`busy`/`operator-set`/
`unknown`), or the outcome. The actual root cause was a stale `.pi/agent` clone
running pre-fix code — invisible from any log because **the caam pass emits nothing
but stdout**. This plan fixes that: full OTel-compatible instrumentation of the caam
loop, following the existing fleet convention, so "why did it read unknown / drive
this pane" is a Honeycomb query rather than scrollback archaeology.

## The fleet telemetry convention (follow this; do NOT invent a new one)

There is **no shared cross-repo telemetry package** — the CONVENTION is shared, each
repo carries its own module. The wire format is **OTLP / HTTP-JSON
`ExportTraceServiceRequest`** (`resourceSpans -> resource.attributes + scopeSpans ->
scope + spans[]`), shipped to Honeycomb `https://api.honeycomb.io/v1/traces` with
header `x-honeycomb-team: <ingest-key>`.

Two existing emission patterns:

1. **Daemon path** — `overseer/_supervisor_diagnostics.log(...)` (`:146`, via
   `EventRequest` `:100`) builds a flat `record` dict (`_event_record` `:114`) and
   BOTH writes one JSON line to stderr (`_write_event` `:133-136`) AND fires
   `sup.otel.exporter.export(...)` (`:138`). The record→span mapping is
   `overseer/_supervisor_otel.py::_payload` (`:138`): `event`->span `name`,
   `ts`->start/end unix-nano, other keys->OTLP-typed attributes (`_attributes` `:170`,
   `_value` `:180`), `status.code`=2 iff an `error` key present else 1. Config from
   env (`config_from_env` `:56`; `OTEL_EXPORTER_OTLP_ENDPOINT`,
   `HONEYCOMB_INGEST_KEY_LIVESPEC`); no endpoint -> `sent=False` no-op (`:75`). Async
   off-tick via `overseer/_supervisor_otel_async.py::OtelAsyncExporter.export` (`:37`,
   bounded queue 64); failure alerting `overseer/_supervisor_otel_report.py` (`:30`).
   The seam lives on the Supervisor: `_supervisor_core.py:146`
   (`otel: OtelSeam = field(default_factory=from_env)`), built by
   `_supervisor_otel_seam.OtelSeam.from_env()` (`:41`).

2. **Dispatcher path** (no Supervisor needed) — per-operation span builders
   (`.claude-plugin/scripts/livespec_orchestrator_beads_fabro/commands/_dispatcher_calibration_span.py`,
   `_dispatcher_review_gate_span.py`, `_reflector_spans.py`) each build an OTLP
   request line with their own `_OTLP_SCOPE_NAME`, append to a `*-spans.jsonl`
   artifact, and ship via `_otel_enrich_export.HoneycombHttpExporter.export(*, spans,
   dataset)` (`:41`, fail-open, dataset from `service.name` via `honeycomb_dataset_for`
   `:53`). Reader/round-trip: `_otel_parse.ingested_spans_from_trace_request` (`:21`).
   Wiring: `_dispatcher_otel_wiring.py`.

3. **CI path** — `.github/scripts/export-ci-telemetry.sh` (job `export-telemetry` in
   `.github/workflows/release-tag.yml:97`, `release-readiness.yml:74`) hand-assembles
   OTLP JSON with `jq`, POSTs, and **fails the job** on HTTP!=200 or
   `partialSuccess.rejectedSpans!=0` (`:141`) — a closed-loop self-verification worth
   copying.

### Naming / attribute conventions (mandatory to match)

- Resource: always `service.name` + `service.namespace = "livespec-family"`.
- Scope name: `livespec.<component>.<subsystem>` (e.g. `livespec.overseer.daemon`
  `_supervisor_otel.py:31`, `livespec.dispatcher.calibration`,
  `livespec.github-ci-export`); a semver-ish `version`.
- Span name: dotted namespace (`ci.run`, `ci.job.<name>`, `dispatcher.calibration`);
  the daemon uses its `event` string as the span name.
- Attribute keys: dotted / semconv-aligned for cross-cutting IDs (`service.name`,
  `git.commit.sha`, `work.item.id`, `fabro.run_id`, `fabro.failure.*`); bare
  snake_case for local metrics (`fix_loop_count`, `wall_clock_seconds`). Values are
  OTLP-typed via the `_value`/`_attr` helpers.
- Governing design rationale (READ before designing spans):
  `plan/archive/overseerd-observability/research/` — `event-shape-2026-08-22.md`,
  `traces-not-logs-2026-08-22.md`, `otel-env-names-2026-08-22.md`,
  `export-failure-reporting-2026-08-22.md`. Dispatcher side:
  `livespec-orchestrator-beads-fabro/AGENTS.md`, `plan/archive/codex-factory-telemetry/`.
  There is NO dedicated telemetry README and `SPECIFICATION/` does not govern OTEL.

## Current caam state: CONFIRMED zero telemetry

- `overseer/caam_anthropic_pass.py` output goes only through `PassContext.stdout`
  (a `LineWriter`): `_emit_table` (`:267`), `trigger_header` (`:166`), resolving to
  `caam_anthropic_loop._StdoutLine -> streams.write_stdout` (`caam_anthropic_loop.py:157`).
- `overseer/caam_enforcement.py` and `overseer/caam_sessions.py` import NO
  `_supervisor_otel*` and emit nothing. The enforcement decision
  (`enforce_session_models`, `caam_sessions.py` ~`:132-170`) produces only `messages`
  strings.

## The design tension to resolve in scoping

The caam loop runs via `caam_anthropic_loop.main` — **its own CLI loop, OUTSIDE any
Supervisor** — so it has no `sup` handle and cannot call `_supervisor_diagnostics.log`
as-is. Two viable routes (decide in the plan):

- **(A) Dispatcher-style span builder** — add `overseer/_caam_span.py` with
  `_OTLP_SCOPE_NAME="livespec.overseer.caam"`, `service.name="livespec-overseer"`,
  `service.namespace="livespec-family"`, appending OTLP lines to a
  `*-spans.jsonl` and shipping via the existing Honeycomb exporter. Self-contained,
  no Supervisor dependency, matches the dispatcher precedent. Likely the cleaner fit.
- **(B) Thread an `OtelSeam`** — construct `OtelSeam.from_env()` inside the caam pass
  and emit through the same async exporter the daemon uses, without a full Supervisor.
  Reuses the daemon record->span mapping directly.

## What to instrument (candidate span/attribute set)

- **Pass-level span** `caam.enforcement.pass`: account/profile active, `fable_left`,
  `foreman_want`, pane count, session_models exceptions in effect, outcome summary,
  wall-clock, dry_run.
- **Per-pane decision span/event** `caam.enforcement.pane` (the load-bearing one):
  `caam.session` (tmux session), `caam.session_id` (resolved), `caam.transcript.path`
  (resolved file or none), `model.read` (fable/opus/.../unknown), `model.read.source`
  (assistant-message | model-answer | none), `model.want`,
  `caam.decision` (skip-already-set | skip-recently-set | skip-unknown-verified |
  drive | would | busy | operator-set-kept), `caam.driven` (bool),
  `caam.picker.outcome` (PICKER_ALREADY_SET | switched | escaped | error). This makes
  the exact `unknown->fable` incident a filterable query.
- Optional: warm-scheduling and account-switch spans for the rotation half of the pass.

Emission must be **fail-open** (never break enforcement if the exporter is down) and a
**no-op when unconfigured** (no endpoint/key), exactly like the daemon path.

## Scope boundary

Instrument the caam loop OTel-compatibly and land the spans/events in the standard
shape; wiring an actual Honeycomb destination is NOT required (env-gated, no-op when
unset), matching the daemon's degrade-to-stderr behavior. No `SPECIFICATION/` change
is expected (SPECIFICATION governs the supervisor state machine, not telemetry).
