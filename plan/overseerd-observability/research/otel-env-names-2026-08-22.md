# The OTEL environment variables, and one credential hazard specific to this daemon

ledger anchor `overseer-temi26`, children `overseer-temi26.3` and `.5`

Written 2026-08-22, before `.3` is implemented, for the same reason the event
shape was settled first: `.5` accepts on "a reader who has never seen the source
can find the log and configure export from `--help` alone", and it cannot
document variable names that `.3` has not chosen. Settling them here keeps the
two children from disagreeing, and surfaces a constraint neither item records.

## The fleet already has a convention — measured, not assumed

Counting env-var occurrences across the three sibling repos:

| name | livespec | dev-tooling | orchestrator |
|---|---|---|---|
| `OTEL_EXPORTER_OTLP_ENDPOINT` | — | — | 24 |
| `OTEL_RESOURCE_ATTRIBUTES` | 2 | — | 26 |
| `OTEL_EXPORTER_OTLP_PROTOCOL` | — | — | 22 |
| `OTEL_EXPORTER_OTLP_HEADERS` | — | — | 20 |
| `OTEL_SERVICE_NAME` | — | — | 7 |
| `HONEYCOMB_INGEST_KEY_LIVESPEC` | 2 | — | 26 |
| `HONEYCOMB_GITHUB_CI_INGEST_KEY_LIVESPEC` | 17 | 5 | — |
| `LIVESPEC_SANDBOX_OTEL_ENDPOINT` | — | 5 | — |

Two readings, and both matter. **The OTLP transport variables are the SPEC
names, not fleet-invented ones** — the orchestrator wires
`OTEL_EXPORTER_OTLP_ENDPOINT` / `_PROTOCOL` / `_HEADERS` / `OTEL_SERVICE_NAME`
exactly as the OpenTelemetry SDK defines them. **The credential is the
exception**: it travels under a fleet-specific name, and there are two of them —
`HONEYCOMB_INGEST_KEY_LIVESPEC` for general fleet export and
`HONEYCOMB_GITHUB_CI_INGEST_KEY_LIVESPEC` for the CI lane specifically.

## Recommended, with the reasoning recorded

**Endpoint and service name: the spec names.** `OTEL_EXPORTER_OTLP_ENDPOINT` and
`OTEL_SERVICE_NAME`. They are already what the fleet uses, they are what any
operator with OpenTelemetry experience will try first, and neither carries a
secret.

**The key: `HONEYCOMB_INGEST_KEY_LIVESPEC`, NOT `OTEL_EXPORTER_OTLP_HEADERS`.**
This is the one place to diverge from the SDK convention, for three reasons:

  1. It is already the fleet's general-export credential name, at 26 occurrences
     in the orchestrator.
  2. The ratified wire convention this plan is told to follow builds the header
     itself. `export-ci-telemetry.sh` sends `x-honeycomb-team: <key>` — so the
     daemon needs the KEY, and packing it into a generic headers string only to
     parse it back out adds a format with nothing to gain.
  3. **The orchestrator has already recorded the headers variable as a conscious
     credential-exposure decision.** Its `plan/fabro-otlp-telemetry/research/
     findings.md` describes passing resolved `OTEL_EXPORTER_OTLP_HEADERS`,
     "including an ingest credential, into worker environment variables", notes
     that "local sandbox commands, some MCP subprocesses, and non-sandbox hooks
     can inherit worker environment", and accepts it with an explicit deny-list
     follow-up. A secret in its own named variable stays greppable and can be
     unset deliberately; a secret inside a generic headers blob gets copied by
     anything copying "the OTEL config".

**Degrade to local-only on absence, per `.3`'s own text.** With no endpoint
configured the daemon emits to `daemon.log` and does not fail. Note the
asymmetry worth testing: an endpoint with NO key is a misconfiguration that will
be REJECTED by Honeycomb, and `.4` requires that rejection to be reported rather
than swallowed — so "unconfigured" must mean the endpoint is absent, not that
the export silently no-ops when the key is missing.

## The hazard neither `.3` nor `.5` records: this daemon's children inherit its
environment

`overseerd` is not a short-lived exporter. It spawns tmux, and it does so with
the environment it is holding.

  - `overseer/tmuxio.py:108` — `_call` invokes `self._run([self._tmux, *args],
    …)` with **no `env=` argument**, so every tmux subcommand the daemon runs
    inherits the daemon's full environment.
  - `overseer/tmuxio.py:321` — `new_session` runs `tmux new-session -d -s <name>
    -c <cwd>` with **no `-e`**, and there is no `update-environment` handling
    anywhere in the package (grepped: zero hits for `-e` as a tmux flag or for
    `update-environment`).

A new tmux session takes its environment from the tmux SERVER. Where a server is
already running, the daemon's own env does not reach it. **But where that
invocation is what STARTS the server, the server inherits the daemon's
environment — and then every session and every pane created under that server,
for the life of the server, carries whatever the daemon was holding.** In this
repo those panes are supervised agent sessions, so the blast radius of exporting
a key into `overseerd`'s environment is potentially every agent the overseer
supervises.

This is not an argument against configuring by environment — `.3` requires
exactly that, and it is the right call for a daemon. It is an argument for three
concrete things, which belong in `.3`'s implementation and `.5`'s documentation:

  1. **Read the key once at startup and do not re-read it**, so its lifetime in
     the process is bounded and explicit.
  2. **Never print it.** Presence, prefix and length identify a credential; the
     fleet rule already says so.
  3. **`--help` must say where the key comes from without implying it is
     harmless to export globally.** An operator who exports it in the shell that
     later starts the tmux server has widened its reach beyond the daemon, and
     nothing in the current code would tell them.

## What `.5` can therefore document

  - the default log path, `<checkout>/tmp/overseer/daemon.log`, which
    `daemon.py` already writes and `--help` does not mention;
  - `OTEL_EXPORTER_OTLP_ENDPOINT` and `OTEL_SERVICE_NAME`, with the
    local-only-when-absent behaviour stated;
  - `HONEYCOMB_INGEST_KEY_LIVESPEC`, with the inheritance caveat above;
  - the existing `--warn-percent`, which `--help` already carries and which `.5`
    names only because the same text should cover it.
