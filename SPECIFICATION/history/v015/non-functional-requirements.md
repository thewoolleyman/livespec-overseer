# livespec-overseer — non-functional requirements

## Boundary

This file carries the contributor-facing invariants — how the repository is
developed, tested, and gated — that are NOT visible at the operator-facing
surface. The decision rule: if an operator running the overseer could
observe a violation, the requirement belongs in `spec.md`, `contracts.md`,
`constraints.md`, or `scenarios.md`; if only a contributor changing this
repository could, it belongs here, in the section mirroring the file it
would otherwise live in.

## Spec

- Tests live BESIDE the supervision modules and are fully hermetic: tmux, the
  process filesystem, session registries, and runtime discovery are all
  driven through injected test doubles, so the suite runs deterministically
  with no live tmux and no live sessions on the host.
- Every protocol behavior in this specification — the interlock, the
  voiding graces, the band escalation, the nudge lifecycle, the submit
  retry — is pinned by a deterministic beside-test. Timing-sensitive
  behavior is NEVER verified by hand-driven live loops; the deterministic
  suite owns that coverage.
- Product Python changes land through the fleet's red-green commit ritual:
  a failing test is captured before the implementation that makes it pass,
  in a single amended commit carrying both trailer sets.

## Contracts

- The injected wrap-up and nudge texts are single-sourced as constants
  beside the daemon, and the module documentation that restates them MUST be
  kept in sync when either changes.
- The injectable seams that make the suite hermetic are TEST-ONLY: neither
  the daemon executable nor the operator commands expose them as flags. The
  invocation surface stays knob-free by design.
- A test that pins a safety routing (for example, that a restart can never
  issue the wrong runtime's launch command) MUST be sabotage-verified when
  touched: break the routing deliberately and confirm the test goes red
  before trusting it green.

## Constraints

- The repository is a pin-consuming fleet member: its lint, formatting,
  strict type-checking, and coverage gates come from the fleet enforcement
  suite at a pinned release, and the aggregate check target is the single
  local, pre-push, and CI entry point.
- The supervision package holds one hundred percent statement AND branch
  coverage; coverage exceptions are individually annotated in source with
  their reasoning, never blanket-excluded.
- The standard-library-only rule (per constraints.md §"Language and
  dependencies") is enforced at review and by the executables' isolated
  launch mode, which would fail on any third-party import.

## Scenarios

- Every scenario heading in `scenarios.md` maps to test evidence through the
  repository's heading-coverage registry; a scenario's evidence is
  integration-tier or better, never a unit-tier test.
- New protocol behavior ships with its scenario and its pinning test in the
  same change, so the scenario file and the deterministic suite cannot
  drift apart.
