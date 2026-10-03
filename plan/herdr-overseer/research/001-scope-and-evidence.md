# Herdr and tmux supervision parity

The maintainer requests an autonomous plan, hp factory implementation where feasible, Red-FIRST TDD, release rollout, and direct successful exercise in a real herdr session before completion.

## Requirement carriers

R1: Support Linux herdr tabs/panes alongside existing tmux behavior; select the containing backend using positively verified parent-process evidence. Inherited environment variables and UI focus alone are not proof of the caller pane.

R2: Preserve the current agent conversation in the bottom pane and run the deterministic daemon visibly in the top pane; repeated bootstrap must be idempotent and preserve unrelated panes.

R3: Preserve discovery, exact target identity, context observation, atomic multi-line input, runtime-specific readiness predicates, and the filesystem-ready restart interlock across both backends. A failed or ambiguous transport action fails closed.

R4: Update the shipped operator skill and runtime entrypoints, docs, packaging, diagnostics, and compatibility with existing tmux mapping records.

R5: Implement using hp Fabro where dispatch-safe, with failing regression tests committed before implementation and verifiable Red-Green-Replay evidence; run focused and full required gates plus tmux regression exercises.

R6: Merge through reviewed PRs, ship the release through the normal plugin/runtime installation path, then directly verify a real herdr top-daemon/bottom-LLM session and supervised ready restart; record commands and observations.

## Initial evidence and design boundaries

The primary checkout was clean and the planning worktree was created by the repository recipe. SPECIFICATION/constraints.md Runtime requirements currently forbids terminal-multiplexer abstraction, so a separately ratified spec change must precede factory implementation. Existing PaneDriver and WindowLayoutDriver protocols are the transport seam; supervision policy should remain shared. Herdr 0.9.3 is installed locally. Current Codex tool processes can be detached from their display pane and inherit stale HERDR_PANE_ID values, making positive process ownership verification essential.

There are no explicit deferrals. The plan stays live until direct herdr verification and rollout are complete.
