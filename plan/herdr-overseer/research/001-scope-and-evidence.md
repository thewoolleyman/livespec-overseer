# Herdr and tmux supervision parity

The maintainer requests an autonomous plan, hp factory implementation where feasible, Red-FIRST TDD, release rollout, and direct successful exercise in a real herdr session before completion.

## Original maintainer Definition of Done

The initial request stated the completion criterion verbatim:

> Definition of done is that you have run it directly yourself in a herdr session and seen it work (however you have to do to test the CLI, in a test tmux session, container, whatever you need to do, but don't declare done until you have actually used it and it works the same.

The assertions below were derived from that request and the ratified v052 contract
under the maintainer's standing autonomous authorization, then recorded on plan
epic `overseer-uzvcbn` during the 2026-10-05 Definition-of-Done retrofit. Their
order matches the epic's eight assertions and its recorded carrier map. Each is
host-captured at plan level and requires observation against the released build;
factory proofs on child carriers do not discharge the final plan proof. Recording
and independent verification use different identities.

## Definition of Done

- The released overseer runs in a real Herdr operator session with its visible daemon in the top pane and the original Claude Code or Codex agent in the bottom pane, retaining the agent pane identity and focus when bootstrap is repeated.
- The released bootstrap selects the nearest positively verified terminal owner from process ancestry and refuses stale, detached, missing or ambiguous ownership before any pane mutation.
- The released daemon routes every tracked pane to its recorded backend and live server generation, preserves legacy tmux mapping meaning, and refuses to retarget an unavailable instance to a namesake.
- The released daemon delivers escalating wrap-up through bracketed paste with separate verified submission at settled idle, and leaves busy, gated, changing, foreign, ambiguous and undeclared sessions unrestarted.
- A real Claude Code or Codex agent's fresh certifiable ready declaration permits a fresh successor of the same runtime and recorded launch profile in the same Herdr pane, with the declaration consumed only after verified successor continuation.
- After interruption during Herdr replacement, the released daemon retains visible transaction evidence and recovers without repeating predecessor termination or an attempted launch whose outcome is unknown.
- The released overseer preserves the existing tmux top-daemon and bottom-agent lifecycle, including native atomic replacement and preservation of ready authorization when replacement provably fails without replacing the predecessor.
- An operator following the released overseer skill can bootstrap either supported backend and locate an actionable diagnostic's exact server and pane using its displayed instructions.

References: ## Scenario: The nearest verified terminal owns the two-pane overseer, ## Scenario: Stale environment cannot choose an overseer pane, ## Scenario: Backend-qualified coordinates preserve legacy tmux ownership, ## Scenario: Both backends retain supervision and acting guards, ## Scenario: A guarded herdr replacement survives daemon loss without a second kill, ## Scenario: A failed tmux native replacement preserves restart authorization

## Requirement carriers

R1: Support Linux herdr tabs/panes alongside existing tmux behavior; select the containing backend using positively verified parent-process evidence. Inherited environment variables and UI focus alone are not proof of the caller pane.

R2: Preserve the current agent conversation in the bottom pane and run the deterministic daemon visibly in the top pane; repeated bootstrap must be idempotent and preserve unrelated panes.

R3: Preserve discovery, exact target identity, context observation, atomic multi-line input, runtime-specific readiness predicates, and the filesystem-ready restart interlock across both backends. A failed or ambiguous transport action fails closed.

R4: Update the shipped operator skill and runtime entrypoints, docs, packaging, diagnostics, and compatibility with existing tmux mapping records.

R5: Implement using hp Fabro where dispatch-safe, with failing regression tests committed before implementation and verifiable Red-Green-Replay evidence; run focused and full required gates plus tmux regression exercises.

R6: Merge through reviewed PRs, ship the release through the normal plugin/runtime installation path, then directly verify a real herdr top-daemon/bottom-LLM session and supervised ready restart; record commands and observations.

## Initial evidence and design boundaries — observed 2026-10-04

The primary checkout was clean and the planning worktree was created by the repository recipe. At that initial observation, SPECIFICATION/constraints.md Runtime requirements forbade terminal-multiplexer abstraction, establishing the need to ratify a separate spec change before factory implementation; that observation predates the v052 contract used for the derived assertions above. Existing PaneDriver and WindowLayoutDriver protocols were identified as the transport seam; supervision policy should remain shared. Herdr 0.9.3 was installed locally. Observed Codex tool processes were detached from their display pane and inherited stale HERDR_PANE_ID values, making positive process ownership verification essential.

There are no explicit deferrals. The plan stays live until direct herdr verification and rollout are complete.
