# Decision — the relationship with `livespec-gnjb`

ledger anchor `overseer-temi26`, child `overseer-temi26.1`

Decided 2026-08-22 by the supervision seat. Recorded here and, per the child's
own acceptance, on the plan epic's ledger.

## The decision

**Do not block on `livespec-gnjb`. Ship the exporter here now, stdlib-only,
behind a narrow local seam, on the fleet's already-ratified wire conventions,
and swap the backing implementation if and when a consumable shared module
exists.**

## Why — four measurements, none of them a status read

**1. The port has not started.** `livespec-gnjb` reads `BACKLOG`, created
2026-06-30. That alone proves nothing (a ledger row is the last thing to move
in this fleet), so the world was checked instead: a grep for `otlp` / `OTLP` /
`honeycomb` across the whole `livespec` tree returns the two shell scripts
(`.github/scripts/export-ci-telemetry.sh` and its
`templates/orchestrator-plugin/` stamp), the NFR that ratifies them, and spec
history — **no Python module anywhere**. No branch and no pull request in
`livespec` names the port. Its parent epic,
`livespec-dev-tooling-9j8`, is **CLOSED** with its planning lane archived at
1/8 children complete: port #1 (`bump-pin-rewrite`) landed, port #2 did not.
So there is no in-flight work to join and no landing date to wait for.

**2. Even landed, the overlap is thin.** `livespec-gnjb`'s deliverable is
CI-shaped end to end: it consumes `gh run view` JSON, derives trace and span
ids deterministically from GitHub run/job integer ids, and emits one `ci.run`
root span with one `ci.job.<name>` child per job. A long-running daemon
emitting per-tick events shares none of that assembly — only the OTLP envelope
and the HTTP POST, which is roughly twenty lines. Blocking a daemon feature on
a CI-exporter port would buy almost no reuse.

**3. The fleet already has a SECOND Python OTLP emitter, and it is not
consumable here.** `livespec_dev_tooling/otel_step_timer.py` (185 lines,
stdlib-only, unit-tested, baked onto the fabro-sandbox image as
`livespec-step-timer`) is much closer in shape to what this plan needs than
`export-ci-telemetry.sh` is. It is still the wrong thing to import, for four
reasons that are facts rather than preferences:

  - Its `__all__` exports `DATASET`, `DEFAULT_ENDPOINT` and `main` only. Its
    module comment records that `build_trace_payload`, `run` and `post_span`
    are internal helpers "measured at ZERO references across all eight sibling
    repos". Consuming them means reaching past a declared private interface.
  - Its `post_span` **deliberately swallows every network failure** — the
    docstring is explicit, "a broken stopwatch never breaks the run". That is
    the correct semantic for a stopwatch wrapping someone else's command, and
    it is the exact negation of child `.4`, which requires a failed or rejected
    export to be REPORTED.
  - It posts to a local collector (`http://172.17.0.1:4318`, no auth header),
    while the ratified Honeycomb convention posts to
    `https://api.honeycomb.io/v1/traces` with `x-honeycomb-team`. Different
    destination shape, not merely a different constant.
  - `livespec-dev-tooling` is a **dev-group** dependency of this repo, and
    `overseer/` is stdlib-only by invariant — `pyproject.toml` says "One
    runtime dependency, deliberately", and `overseer/AGENTS.md` repeats it for
    every new module. A runtime import would break that contract.

**4. So the "second implementation" framing was already inexact.** The fleet
has two OTLP emitters today, and `livespec-gnjb` consolidates the shell one,
not the Python one. That does not make a third free — it means the mitigation
is a seam, not a wait.

## What "behind its intended interface" must mean, concretely

Recorded so a later swap is mechanical rather than a rewrite:

  - **One module** in `overseer/` owns payload construction and transport, with
    the emitter passed in as a seam — the same shape `otel_step_timer.run`
    already uses for its `emit` parameter — so a swap touches one call site and
    the tests keep injecting a recorder.
  - **Wire conventions are taken, not invented**, from
    `export-ci-telemetry.sh`: OTLP/HTTP-JSON POSTed to the endpoint's
    `/v1/traces`; a `service.name` resource attribute selecting the Honeycomb
    dataset with `service.namespace` beside it; spans carrying `traceId`,
    `spanId`, `parentSpanId`, `name`, `kind`, `startTimeUnixNano`,
    `endTimeUnixNano`, `attributes` and `status.code` (1 ok, 2 error); int64
    fields serialized as JSON strings per the proto3-JSON mapping Honeycomb
    expects.
  - **Environment-only configuration**, degrading to local-only when
    unconfigured — no flags, no config file.
  - **Failure is reported, never swallowed.** This is the one place the
    overseer's emitter must diverge from `otel_step_timer` on purpose, and
    child `.4` owns proving it in both directions.

## The reciprocal obligation

A note goes on `livespec-gnjb` itself recording that a second consumer now
exists and what interface it expects, so the port's implementer designs for two
callers rather than one. Prose cross-reference only — no typed cross-tenant
dependency edge, per `AGENTS.md`: thread membership belongs in item text, and
an edge pointing at work that may never start would fail closed forever.

## What this unblocks

Children `.2` through `.5` were all sequenced behind this answer. They are now
orderable: `.2` (reshape `daemon.log` into events) and `.3` (emit OTLP) share
the payload shape above and can proceed together; `.4` gates on `.3`; `.5`
documents whatever `.2` and `.3` settle on.
