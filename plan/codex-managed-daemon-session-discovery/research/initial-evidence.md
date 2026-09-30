# Codex managed-daemon session discovery failure

## Objective

Make overseer session discovery correct for current Codex process topologies so a live Codex plan cannot be falsely re-pointed to the overseer operator session and rendered `session-gone`. Preserve correct behavior for legacy direct-rollout and per-session-helper topologies, and make any stale mapping self-heal from certifiable live identity evidence.

## Proven incident evidence

Measured on 2026-09-30 against simultaneously live processes on the same host:

- Codex CLI 0.154.0 carriers (PIDs 623146 and 734753) hold their own rollout file descriptors. This is the topology the existing carrier/helper walk can join to a tmux pane correctly.
- Codex CLI 0.159.2 carriers for the operator pane (PID 3812982, tmux `overseerd`) and the plan pane (PID 259333, tmux `llm-provider-manager`) hold no rollout file descriptors.
- One shared Codex 0.159.2 managed app-server (PID 3813389, `codex app-server --listen unix:// --managed-daemon`) is a descendant of the operator carrier and simultaneously holds rollout files for multiple independent sessions, including fresh plan session `01a0f3e7-c326-7fd1-8eb0-37a35e6d787f`.
- The live plan process remained present in tmux `llm-provider-manager`, pane `%542`, with cwd `/data/projects/livespec-overseer`.
- At 2026-09-30T20:57:34Z, overseer logged `re-pointed /data/projects/livespec-overseer::llm-provider-manager tmux llm-provider-manager → overseerd`; the current status row then rendered `runtime: null`, `tmux: null`, `status: session-gone`.

The causal chain is mechanical: `_codex_proc.carrier_rollout_ids` treats descendant helper rollouts as belonging to that carrier; the shared managed daemon violates that ownership premise. The real plan carrier becomes undiscoverable, while the operator carrier can inherit another session's indexed topic. Adoption then sees one apparent live claimant, bypasses the duplicate-key ambiguity guard, and persists a false tmux re-point.

## Required outcomes

1. Model and detect the shared managed-daemon topology without attributing its rollout set to the daemon's historical parent TUI.
2. Join each active Codex session identity to its actual tmux pane using evidence that remains valid with a shared app-server; fail closed when ownership cannot be proved.
3. Never mutate a correct mapping from evidence that is merely process-descendant proximity to a shared daemon.
4. Recover stale rows such as `llm-provider-manager → overseerd` once exact live evidence is available.
5. Add discriminating tests covering direct rollout ownership, per-session helper ownership, a shared daemon holding multiple rollouts, and the false-repoint incident.
6. Live-exercise current Codex with at least two simultaneous tmux sessions and prove both retain distinct mappings across daemon ticks and restart adoption.
7. Record a bounded operator workaround until the fix ships: current sessions may be manually re-pointed from verified tmux facts, and newly launched remediation work uses `codex --no-daemon` so rollout ownership stays session-local.

## Initial scope judgment

This is implementation conformance to the existing supervision contract, not a specification change: the contract already requires correct live session identity, safe mapping, and no action against the wrong pane. The plan should route a factory-safe implementation child after research confirms the replacement identity seam and test matrix.
