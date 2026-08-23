# Why `.3` emits TRACES and not OTLP LOGS, and what the logs design still teaches

ledger anchor `overseer-temi26`, child `overseer-temi26.3`

Recorded 2026-08-22 because the alternative is real, this fleet has already
reasoned about it at length in a sibling repo, and `.3` would otherwise ship a
signal choice with no recorded answer to "why not logs?".

## The alternative, and it is not a strawman

OTLP has a LOGS signal, and a discrete daemon event is a more natural LogRecord
than it is a zero-duration span. The orchestrator repo carries a captured
upstream design —
`livespec-orchestrator-beads-fabro/plan/fabro-otlp-telemetry/research/
quarry-otlp-logs-export-2026-08-02.md` — that chooses exactly that for exactly
this problem shape: "**Scope: logs only.** Metrics and traces are explicitly
deferred", mapping one canonical run event to one OTLP `LogRecord`.

Its central argument transfers here almost word for word. It refuses to export
the developer tracing firehose, on the grounds that levels, messages and fields
are deliberately unstable and "shipping that firehose to a third party turns an
intentionally-unstable developer artifact into an external contract". Instead it
exports a **curated closed catalog** of named events, and notes both reference
implementations converged on the same shape — Codex filters its appender to a
dedicated target prefix so only events through one macro are exported, and Claude
Code publishes a closed catalog of 15 named log events each with a documented
attribute list.

## The decision: traces, and the deciding reason is `.1`, not semantics

**Emit zero-duration spans on the traces signal.** On semantics alone the logs
signal is the better fit, and that is worth admitting plainly. Four things
outweigh it:

1. **`.1` already decided to ship behind the interface `livespec-gnjb` will
   provide, and gnjb is a SPAN builder.** It is the port of
   `export-ci-telemetry.sh`, a trace exporter. Choosing logs would make this
   daemon unable to consume the shared module when it lands — re-creating the
   second-implementation problem `.1` was decided specifically to avoid. This is
   the deciding reason; the rest are corroborating.
2. **The ratified fleet convention is traces.** The CI telemetry NFR and the
   script it governs post to `/v1/traces`. `.1`'s ruling was to take conventions
   rather than invent them, and a different SIGNAL is a bigger invention than a
   different field name.
3. **Honeycomb treats a zero-duration span as an ordinary event.** Nothing
   analytical is lost: `.3`'s acceptance — spans queryable by `topic` and by
   `daemon_instance_id` — is satisfied identically either way, since both signals
   land as attribute-bearing records.
4. **`service.name` selects the dataset on both paths**, so the routing story the
   plan already inherited does not change.

**What is genuinely given up**, recorded so it is not rediscovered as a surprise:
OTLP logs carry a native `SeverityNumber`, which would have expressed this
plan's `severity` field directly instead of as a custom attribute. That is the
one place the traces choice is measurably clumsier, and it is why the event shape
records `severity` as an attribute rather than trying to force it onto
`status.code` — an alert is not an error, and marking a correctly-reported stale
heartbeat as status 2 would make a healthy daemon look broken.

## What the logs design teaches even though its conclusion is not taken

**The curated-catalog principle is an endorsement of the shape already chosen.**
This plan's event vocabulary is the 39 existing `condition` values plus a named
verb per `log` site — a closed catalog with stable names, not the daemon's whole
stderr firehose reinterpreted. That is precisely what Codex, Claude Code and the
fabro design each arrived at independently. It is worth stating as a rule for
`.3`: **exporting a line because it happens to be written is the failure mode;
exporting a named event from a closed catalog is the design.**

**Off by default is the same stance `.3` already holds.** The logs design is
explicit — "No built-in destination, no vendor endpoint compiled into the binary,
no traffic without an explicitly configured endpoint." `.3` already says endpoint
and key come from the environment only and that an unconfigured daemon emits
locally and does not fail. Two independent designs reaching the same default is
worth noticing rather than treating as coincidence.

**A signal choice is reversible; a vocabulary is not.** If the fleet later
standardises on logs for event telemetry, the same closed catalog and the same
attribute keys re-render onto `LogRecord`s with the envelope untouched. That is a
further argument for the field identity `.2` and `.3` are already required to
share, and against letting either child invent names the other does not use.
