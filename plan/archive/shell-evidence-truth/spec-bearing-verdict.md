# Background-shell evidence is an implementation boundary

Decision recorded 2026-08-03 for the `shell-evidence-truth` planning thread
(epic `overseer-3zbwi3`, defect `overseer-3rk`).

## Verdict

The detector fix is **implementation-only**. No ratified clause defines a
background command as every descendant process whose Linux `comm` is a shell
name, and no ratified clause must narrow for the daemon to stop treating a
session-lifetime MCP launch-chain shell as background work. Therefore this
thread does not open a livespec proposed change before filing the detector
work.

This is a narrow verdict about evidence truth. It does not alter what the
daemon may do once genuine background-command evidence exists. That response
is governed separately, including the proposed suppression narrowing tracked
by `overseer-blccme` / `plan/supervisor-wrapup-citizenship/`.

## Sweep

The required sweep covered `SPECIFICATION/spec.md`,
`SPECIFICATION/contracts.md`, `SPECIFICATION/scenarios.md`, the shipped
operator prose `.claude-plugin/prose/overseer.md`, and
`overseer/marker-protocol.md`.

- `SPECIFICATION/spec.md` defines the fail-soft direction: ambiguous busy
  evidence suppresses action, while bounded attention prevents indefinite
  silence. Its background-command clauses prescribe responses (pair nudge,
  low-context attention, shell-prolonged attention, and action suppression).
  They do not define a `/proc` detector or equate a shell-shaped descendant
  with work.
- `SPECIFICATION/contracts.md` requires `no busy signals` at the restart
  interlock and enumerates attention membership once background-command or
  busy-shielding evidence exists. It does not define how Codex fallback
  evidence distinguishes runtime infrastructure from a task command.
- `SPECIFICATION/scenarios.md` uses the already-classified states `busy` and
  `resumes work`; it contains no background-shell evidence definition.
- `.claude-plugin/prose/overseer.md` describes `working` as active generation
  or "a live background shell under its pane". That ordinary-language claim
  remains true after the fix: an MCP launch-chain shell is live and under the
  pane, but it is not a background shell in the work-signal sense. The fix
  makes the implementation match the prose instead of narrowing the prose.
- `overseer/marker-protocol.md` says restart requires no live background shell
  under the pane. It likewise states an interlock consequence, not the current
  implementation's `comm`-name equivalence. A session-lifetime wrapper holding
  an MCP server is not background work and therefore need not fail that gate.

The only explicit claim that persistent helpers cannot be shells is in
`overseer/claude_sessions.py`: once above `_SHELL_COMMS` and once in
`has_active_subshell`'s docstring. Those implementation claims are false and
must be corrected with the detector.

## Contract the implementation must preserve

Implementation-only does not mean unconstrained. The factory item must keep
all of these boundaries:

1. The known launch-time MCP chain (runtime → sudo/wrapper shell → `op` →
   shell → long-lived MCP node) is not background-work evidence.
2. A genuine shell spawned by a mid-session tool call remains busy evidence,
   including the stale task-shell shape from `overseer-vyjkzw`.
3. Ambiguity still resolves to busy. In particular, a launch chain relaunched
   later in the session is not safely classifiable as startup infrastructure
   from start time alone, so it remains busy unless additional deterministic
   evidence proves otherwise.
4. The chosen startup margin uses `/proc` starttime jiffies, is stated and
   tested, and is injectable through a `starttime_of` seam beside the walk's
   existing `children_of` and `comm_of` seams.
5. Tests cover the Codex fallback/unadopted-pane path that consumes this walk
   and preserve the adopted-Claude registry path's authority.

If implementation work discovers that satisfying this boundary requires a
different meaning for a ratified clause rather than a more truthful detector,
the item must stop and route that newly found semantic change through
`livespec:propose-change`. Nothing in the present evidence requires that
route.

## Operational re-verification still owed

After the fix is released and installed, inspect the
`beads-v1-1-2-upgrade` worker/supervisor pair in
`livespec-orchestrator-beads-fabro`. Its 54-hour shell-prolonged alarms are a
suspected instance, not proof; compare the live process trees and confirm the
released detector clears launch-chain-only evidence without hiding genuine
background terminals.
