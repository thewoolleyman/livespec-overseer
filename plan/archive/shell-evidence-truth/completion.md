# shell-evidence-truth — completion

Closed 2026-08-03. Epic `overseer-3zbwi3`; original defect
`overseer-3rk`; implementation child `overseer-hqo5lk`.

## Result

The specification sweep recorded in `spec-bearing-verdict.md` found this to
be implementation-only. The ratified specification defines fail-soft
consequences but does not equate every descendant shell process with active
background work, so no proposed-change or specification revision was needed.

PR [#518](https://github.com/thewoolleyman/livespec-overseer/pull/518)
landed the detector fix at merge commit
`f8e56e5b41b361755bfe3da22c9e49c56dac1ea7`. The detector now uses raw
`/proc/<pid>/stat` start-time ticks to distinguish startup wrapper shells from
later task shells. Its 1,000-tick startup margin, injected `starttime_of` seam,
ambiguous-evidence busy fallback, and launch-chain-relaunch boundary are pinned
by beside and repo-level tests. The factory's red/green/replay, sabotage,
janitor, full `just check`, and independent review stages all passed.

Release [v0.16.1](https://github.com/thewoolleyman/livespec-overseer/releases/tag/v0.16.1)
was published from `14d9fab9057381bcf4d95f9d6c71fa28903e7764`.
The `release` branch and tag resolve to that same commit. The sibling fan-out
[run 30773291853](https://github.com/thewoolleyman/livespec-overseer/actions/runs/30773291853)
completed successfully for every eligible fleet member. All fleet marketplace
declarations consume the moving `release` ref, so advancing that ref deploys
the build without a per-repo pin rewrite.

The producer GitHub App is deliberately unauthorized for adopters, so its
adopter dispatch delivered zero events. The consumers' own credential paths
were driven instead: OpenBrain's
[run 30773484696](https://github.com/thewoolleyman/openbrain/actions/runs/30773484696)
landed the concrete `v0.16.1` pin directly, Resume's
[run 30773484384](https://github.com/thewoolleyman/resume/actions/runs/30773484384)
landed the same pin through auto-merged PR
[#19](https://github.com/thewoolleyman/resume/pull/19), and Homelab already
consumes the moving `release` ref. The operator host's Claude cache resolved
the release commit, its Codex plugin was upgraded from 0.16.0 to 0.16.1, and
the exact daemon pane was respawned from its recorded start command so the
long-lived process loaded the new code.

The release-tag workflow's strict LLOC lane remained red for the already-known
repo-wide soft-band debt owned by active P1 work item `overseer-dtl`; telemetry
export also timed out against Honeycomb. Neither failure prevented the release,
release-branch fast-forward, sibling delivery, or adopter updates, and neither
is part of this detector defect.

## Live re-verification

After the daemon reload, the released detector was evaluated against the live
process trees that motivated this thread:

- `beads-v1-1-2-upgrade`: runtime baseline PID 668320; startup `bash` PID
  676020 at +842 ticks; `has_active_subshell=false`.
- `06-resilience-acceptance`: runtime baseline PID 2422094; startup `bash` PID
  2432053 at +759 ticks; `has_active_subshell=false`.
- `livespec-orchestrator-beads-fabro`: a genuine later task shell was present
  beyond the startup margin; `has_active_subshell=true`.

That proves both halves of the regression boundary on real Codex sessions:
session-lifetime MCP launch plumbing no longer suppresses idle handling, while
actual mid-session shell work still counts busy. The focused suite also passed
42 tests across `overseer/test_claude_sessions.py`,
`overseer/test_supervisor_background_subshell_live.py`, and
`tests/test_hqo5lk_shell_launch_chain.py` on merged master.

**CORRECTION 2026-08-03T00:55Z — this section claims more coverage than it
has, and `re-verification.md` records the measurement.** The owed
re-verification named the `beads-v1-1-2-upgrade` worker/supervisor PAIR; the
list above reports the worker only. Re-measured against the released detector,
`beads-v1-1-2-upgrade-supervisor` still returns `has_active_subshell=True` on
pure MCP launch plumbing — the same Cloudflare `mcp-remote` chain as the
ignored startup one, byte-identical argv, relaunched 64 hours into the session
and therefore past the startup margin. That is the mid-session-relaunch hard
case this thread deliberately left resolving to busy, so it is not a defect in
what shipped; it is a residual that is now observed in the fleet rather than
predicted. Tracked as `overseer-q3f`. Read this section as: the worker half
cleared, the supervisor half did not.
