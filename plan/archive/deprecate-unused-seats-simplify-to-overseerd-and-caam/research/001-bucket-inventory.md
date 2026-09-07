# 001 — Bucket inventory: what leaves, what stays (measured 2026-09-06)

Maintainer ruling, 2026-09-06, recorded as a scope event on the console plan
epic `livespec-console-beads-fabro-pzbdbo` (plan
`retire-overseer-and-redesign-control-plane-around-console`, decision D5
refined into two buckets):

> Specifically, you should not invent new overseerd or caam-anthropic-loop-runner
> work, but I may still improve those in overseerd. Separate those out into
> separate buckets since they are currently still production and used. Leave
> them until they are stable and we have a clear path to move them. All the
> other stuff is unused — foreman, grooming, etc. — and should be deprecated and
> moved sooner than later, to get it done and simplify livespec-overseer to just
> what is left — overseer and caam loop.

## Bucket 1 — production, stays, maintainer-owned (this plan does not touch it)

| surface | skill / prose | package modules (name-pattern count, lines) |
|---|---|---|
| overseerd daemon (registry, tracks, restart, attention rows) | `overseer` / `overseer.md` | `_registry_*`, `_claude_sessions_*`, `_codex_*`, `_supervisor_*` daemon core — the supervisor loop IS the daemon; ~26 + 10 + most of 106 modules |
| caam-anthropic-loop runner | `caam-anthropic-loop` / `caam-anthropic-loop.md` | `_caam_*`: 41 modules, ~6.7k lines |

Their D5 destinations (caam → orchestrator `accounts status | rotate`;
overseerd's re-dispatch on `transient_infra` → dispatcher policy) are
DEFERRED until the maintainer declares both stable with a clear path.

## Bucket 2 — unused, deprecate and move now

| surface | skill / prose | package modules |
|---|---|---|
| foreman seat | `foreman` / `foreman.md` (42 KB) | `_foreman*`, `*_foreman*`, `_registry_stamp_foreman_self_restart`, `_supervisor_foreman*`: 89 modules, ~13.0k lines |
| grooming seat | `grooming` / `grooming.md` (32 KB) | `grooming_conformance*`, `_supervisor_grooming`: 11 modules, ~1.4k lines |
| supervisor seat | `supervise-plan` / `supervise-plan.md` (52 KB) | only what serves the supervise-plan binder/handoff — NOT the daemon's `_supervisor_*` loop; the cut is by consumer, not by name prefix |

The name-pattern counts above are a first sizing (a regex over
`.claude-plugin/overseer/*.py`), not the cut. The cut is: delete what has no
consumer once the three skills and their prose are gone, and keep every module
the `overseer` and `caam-anthropic-loop` skills still reach.

### Bucket-2 epics in this tenant (all open 2026-09-06)

overseer-nbzgrk foreman-codex-pi-runtime-support (blocked; child qmarlj ready),
overseer-1a31 foreman-wait-premise-conditions, overseer-764a
foreman-panel-and-rulings, overseer-ll9d foreman-liveness-and-escalation,
overseer-tdfe (+ .11) foreman-actuator-gather-and-roster, overseer-b1l9 foreman
seat anchor, overseer-ow7c foreman-seats-and-plan-records, overseer-3h4s5w
foreman-full-autonomy-option, overseer-qyli grooming seat anchor,
overseer-au3pt3 foreman-improvements, overseer-7jskz4 foreman attach commands.

Not in bucket 2 (maintainer's or repo/fleet): overseer-zidpiu, -qt3wvu,
-6tfncs (daemon), -4z97 (repo gates), -cajdwp (fleet plumbing).

### Capabilities that transfer by name before their epics close

- starvation (ready-aging fact) → dispatcher loop cadence: orchestrator b5-NOW
  item (source prose: overseer-7ranbh, closed).
- consensus-panel disposition → panel workflow variant under orchestrator b4
  `bd-ib-yqpdrt`, plus the valve-policy enum on attention items (b5-NOW).

Everything else in bucket 2 (pane classification, keystroke answering, seat
registries, heartbeat/ready files, tmux-named sessions) is deleted outright
per D5.

## Ordering

1. Remove the three skills, their prose and their exclusive modules (factory,
   one PR per seat, tests and coverage kept green; the daemon and caam suites
   are the regression guard).
2. Trim the plugin manifests (`plugin.json`, `.codex-plugin`, `.pi-plugin`,
   `marketplace.json`), `AGENTS.md` and `SPECIFICATION/` to overseer +
   caam-anthropic-loop; major version bump (skills removed).
3. Close the bucket-2 epics as superseded-by-transport, naming the orchestrator
   items that carry the two transferred capabilities; archive their `plan/`
   directories.
