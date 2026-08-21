# Opening research — overseerd observability

ledger anchor `overseer-temi26`

## What is already true, and corrects the premise this plan was opened on

**The daemon already writes its own log.** `overseer/daemon.py:91` wraps the run
in `_native_daemon_stderr(log_path=_default_daemon_log_path())`, whose docstring
reads "Append daemon stderr to its event-history log for bare manual bounces".
The path is `<checkout>/tmp/overseer/daemon.log`; measured 2026-08-21 it is
7.4 MB and actively appended.

So the shell redirect that prompted this plan — `overseerd 2>> tmp/overseer/daemon.log`
— was **redundant**. Nothing needs remembering, because the daemon already does
it. This plan must not "add" a default log that exists.

**The real gaps are FORMAT and DISCOVERABILITY**, not destination:

  - The log is human prose, not events. A current line reads
    `2026-08-21T22:20:22Z overseer[SURFACE]: foreman (livespec) — foreman heartbeat stale: ... 892m; pid 309170;`
    That is unparseable as structured data and cannot be correlated with anything.
  - `--help` does not mention the log path at all. It was found here only by
    reading `daemon.py`. An operator cannot discover the file that already
    contains the daemon's entire event history.

## The constraint that decides the design

**stdout is the live table, not a log stream.** `.claude-plugin/prose/overseer.md:229`:
"The daemon's stdout is the live table in the top pane (it clears + re-renders
each tick)", colour-coded by status.

The redirect that prompted this plan was on **stderr** (fd 2). Routing log events
to stdout would overwrite the operator surface every tick and destroy the top
pane. **Events go to stderr and to OTLP; stdout stays the table.** This is not a
preference, it is the existing contract.

## Consume the fleet exporter; do not write a second one

`livespec-gnjb` (P1, livespec core) is already "Port export-ci-telemetry.sh OTLP
span builder to a tested Python module in core + re-stamp impl-plugin template".
The conventions are set in `livespec/.github/scripts/export-ci-telemetry.sh`:

  - OTLP/HTTP JSON to `https://api.honeycomb.io/v1/traces`
  - `x-honeycomb-team` header carries the key
  - `service.name` selects the Honeycomb dataset; `service.namespace` set alongside
  - spans carry `traceId` / `spanId` / `parentSpanId`, `name`, `kind`, `attributes`

`livespec-s43svm.20` describes this as "matching fleet o11y standards", so a
standard exists and this daemon should join it rather than invent a dialect.

**This plan has a real ordering relationship with `livespec-gnjb`.** Shipping an
independent exporter here would create the second implementation the core port
exists to remove. Whether to block on it or to ship behind the shared module's
interface is the plan's first decision.

## Scope

Emit one event stream, rendered two ways: OTLP spans for Honeycomb, and the same
events line-per-event to the existing `daemon.log`. Identical shape in both, so
the local log is a replayable fallback when the exporter is unreachable and an
operator reading either sees the same thing.

Attributes should carry what the table carries, so Honeycomb can answer the
questions the top pane answers: `topic`, `tmux`, `repo`, `status`,
`session_identity`, `ctx`, `tick_generation`, `daemon_instance_id`. The last two
matter most for the questions that are currently unanswerable — "was this the
daemon that was running before the bounce" and "how many ticks did this state
persist".

Endpoint and key from environment only, never committed. Absent configuration,
the daemon emits locally and does not fail.

`--help` documents all of it: the default log path, the OTEL environment
variables, how to point it at Honeycomb, and the existing `--warn-percent`.

## The control that matters

An exporter that silently drops events is worse than none, because it
manufactures confidence. Whatever ships must have a control proving that a
failed export is REPORTED — not merely that a successful export works. This repo
has a documented family of "checks that cannot fail"; an unverified telemetry
path is the same shape.
