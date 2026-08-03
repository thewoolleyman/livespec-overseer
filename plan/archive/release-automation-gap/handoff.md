# release-automation-gap — archived outcome

**Ledger anchor:** epic **`overseer-oijk3d`**, closed 2026-08-03 after every
in-thread obligation was measured and closed. The ledger remains the authority
for item history; this file records the final, forge-verified outcome.

## Read-first chain

1. This file.
2. `plan/archive/release-automation-gap/research/how-the-gap-was-found.md` —
   why the defect remained invisible and why the first fleet audit was too
   narrow.
3. `plan/archive/release-automation-gap/research/what-the-fix-taught.md` — the
   dynamic acceptance population, three-valued fleet result, dual release-gate
   causes, and attempt-level Actions semantics.

That is the whole chain. Detailed implementation evidence is on the closed
items and their PRs.

## Final outcome

### Release PR automation

`overseer-sf0` is closed. PR #520 installed the App-authenticated
`auto-enable-merge.yml`; the workflow armed its own PR. Release PR #516 then
proved the full live bar: `app/livespec-pr-bot` armed and merged it, and v0.16.1
published without a human or agent pressing merge. Release PR #558 repeated the
hands-off result for v0.17.1. The negative control also fired: a run on factory
head `feat/overseer-dtl` skipped, so the author/branch guard does not arm an
arbitrary factory branch.

The widened nine-repo audit found two more missing workflows. Fleet deployment
therefore has three honest outcomes:

| repo | result |
|---|---|
| `livespec-overseer` | workflow and hands-off releases proven |
| `livespec-runtime` | workflow PR #437 and parked release PR #322 merged through the App; v0.13.1 completed that repo's first release train |
| `livespec-console-beads-fabro` | workflow PR #604 and App arming proven; release PR #404 remains blocked by its intentional docs-review lockstep gate |

The console design decision remains in its owning tenant as
`livespec-console-beads-fabro-53t`; it is not unfinished scope here.

### Release-tier enforcement

`overseer-dtl`, population carrier `overseer-gxrnx5`, and the independently
discovered TODO carrier `overseer-0kw` are closed. PR #550 measured the dynamic
LLOC population, decomposed the newly appearing member, and propagated the
source decomposition to the plugin mirror. PR #536 supplied the six real
integration bindings owed by the TODO registry; a synthetic-TODO positive
control still makes the detector fail.

Both exact release-tier commands pass with ceilings, fail levers, exclusions,
and TODO semantics intact:

```sh
LIVESPEC_FAIL_IF_LLOC_SOFT_WARNINGS_EXIST=1 just check-no-lloc-soft-warnings
LIVESPEC_FAIL_IF_HEADING_COVERAGE_TODOS_EXIST=1 just check-no-todo-registry
```

The non-proxy bar passed too. `Release tag` run 30781186392 on v0.17.1 reached
final success at **2026-08-03T03:18:21Z**, the first green since 2026-07-27.
Attempt 1 had all three release gates green and failed only on transient
`export-telemetry`; attempt 2 retried telemetry successfully. Run creation at
03:11:32Z is not the success timestamp.

### Release-ref Codex adoption proof

`overseer-zxy` is closed. Factory run `01KZ2T7YSCST` correctly blocked because
its sandbox had neither Codex nor the host tmux socket; its phantom
`active/fabro` claim was released before host-side work.

An isolated marketplace fixture was registered explicitly at `--ref release`,
matching freshly queried `origin/release` SHA `3a8c6d76316a8b265e1b0c501f8737f2c01eb027`
(plugin 0.17.2). The live TUI picker passed, and the same check failed when the
`overseer` skill was removed from a scratch copy. A dedicated plain-shell tmux
control refused the launcher with exit 1. A real Codex session then resolved
the bare `livespec-overseer:overseer` skill and, in one continuous run, started
a scratch-store daemon that adopted and rendered exactly one named Claude probe.

The bound matters: the launching Codex session rendered as `codex-unindexed`
and was not adopted. The result proves that the daemon can adopt a track when
launched from Codex; it does not claim that Codex tracks are generally
supervised. Real store MD5, real daemon-lock mtime, and acting daemon pane/PID
were identical before and after. The acting daemon in
`tmux livespec-overseer:1.1` was never stopped, killed, or restarted.

## Closed ledger set

`overseer-sf0`, `overseer-3u7bbw`, `overseer-dtl`, `overseer-gxrnx5`,
`overseer-0kw`, `overseer-zxy`, and epic `overseer-oijk3d` are closed. The
archived supervisor binder is historical evidence, not live routing; its stale
enumerations and next actions are superseded by this outcome and the ledger.
