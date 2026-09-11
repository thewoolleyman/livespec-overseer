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

- Provider, credential kind, purpose, health strategy, provider health adapter,
  selection strategy, SecretStore and ProvisioningTarget MUST remain
  independent implementation axes. The first adapter MAY support Anthropic
  alone, but core selection MUST carry no Anthropic-only assumption.
- Unit tests live BESIDE the product modules, including `llm-provider-manager`;
  repository-wide integration-tier scenario evidence and the staged-package
  integration test MAY instead live beneath `tests/`. All such tests are fully
  hermetic: tmux, the process filesystem, session registries,
  runtime discovery, provider validation probes, SecretStore backends,
  browser control and `/proc` worker liveness are all driven through injected
  test doubles, so the suite runs deterministically with no live provider,
  mailbox, browser, tmux or session access on the host.
- Every protocol behavior in this specification — the interlock, the expiry
  maximum age and the blocked-void grace, the band escalation, the nudge
  lifecycle, the submit retry — is pinned by a deterministic beside-test.
  Timing-sensitive behavior is NEVER verified by hand-driven live loops; the
  deterministic suite owns that coverage.
- Product Python changes land through the fleet's red-green commit ritual:
  a failing test is captured before the implementation that makes it pass,
  in a single amended commit carrying both trailer sets.

## Contracts

- `caam-anthropic-loop` deterministic behavior MUST be implemented as
  importable modules of this repository's package with tests beside them and
  MUST NOT be embedded as program text inside prose or a binding. Configuration
  values that a test varies MUST be resolved when used rather than fixed at
  module import.
- `caam-anthropic-loop` MUST drive terminal panes through this repository's
  existing pane input and output surface and read process attributes through
  its existing process-reader seams rather than introducing parallel
  implementations.
- The manager MUST depend on a replaceable `SecretStore` port supporting get,
  set, atomic conditional-set and list plus metadata; selection
  behavior MUST NOT couple itself to one backend.
- The internal metadata integration MUST keep separate complete-record
  acquisition and lifecycle conditional-set entry points, and direct adapter
  subprocess launch MUST be factored through one shared credential-role
  launcher child that, for a token-bearing role, retrieves its one keyring token
  after fork and immediately replaces itself with the role process, so neither
  the manager nor selection brain handles token bytes. The tokenless target-status
  role MUST use the same launcher without a keyring lookup. The final provisioning
  boundary MUST be one such dedicated child composing the value read and target
  call; raw value bytes remain in that process.
- Lock-descriptor inheritance MUST be implemented through explicit
  close-on-exec control. An acquisition or reacquisition worker receives only
  the provider-account descriptor, retains it until worker exit, and marks it
  close-on-exec before it starts Chrome, the browser-control service or either
  agent role. The browser-control service MUST preserve that exclusion when it
  starts the terminal, and the execution-agent environment inherited by the
  `claude`-spawned MCP proxy MUST already exclude the descriptor; a revalidation
  worker receives no manager lock.
  The final provisioning child and tokenless target-status child each receive
  only the target-reference descriptor and hold it through their respective
  write or status call, so parent timeout or loss cannot let a status query
  overtake a live writer.
- `caam-anthropic-loop` MUST keep exactly one harness-neutral prose contract and
  one thin binding per supported harness. Each caam binding MUST resolve the
  plugin root, read that prose and carry no operation behavior.
- `llm-provider-manager` MUST have exactly one harness-neutral prose contract
  and one thin binding per supported harness. Each manager binding MUST resolve
  and validate the plugin root, delegate to shared importable code and carry no
  operation behavior beyond that required root and manifest validation. The
  operator invocation layer MUST contain only exact argument validation,
  `invalid-request` and pre-exec `internal-bug` construction, prevalidated
  absolute-path executable launch, verbatim result presentation, and the
  permitted secret-free explanation or operator-instruction rendering, not
  manager behavior.
- The installed manager console wrapper MUST resolve to a standard-library-only
  bootstrap module that, before process replacement, imports no product module
  other than the `overseer` package initializer that Python necessarily executes
  to load that bootstrap. Its isolated companion MUST locate the installed product package
  root absolutely and load `<package-root>/__init__.py` as module `overseer`
  through `importlib.util.spec_from_file_location`, with
  `submodule_search_locations` exactly `[<package-root>]`. It MUST NOT add the
  containing environment or site-packages directory to its import path before
  importing manager modules.
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

- The authoritative `llm-provider-manager` implementation MUST live under
  repository-root `overseer/` with the rest of the product package and MUST NOT
  create a second top-level runtime package. The package-installed console path
  MUST load the distribution built from that tree; the plugin executable MUST
  load `.claude-plugin/overseer/`. Under the existing plugin-carrier lockstep
  gate, the two trees' direct-child runtime-package sets — every `.py` file and
  `version.json`, excluding `AGENTS.md`, `SKILL.md`, `marker-protocol.md`,
  `conftest.py` and every `test_*` file — MUST contain the same filenames with
  byte-identical contents and no extra file in that filtered set. Every tracked
  regular file recursively beneath `overseer/_vendor/` MUST additionally have
  the same relative path and byte-identical contents beneath
  `.claude-plugin/overseer/_vendor/`, with no extra tracked file in either
  vendored subtree. Source-only documents, tests and executables are outside
  those sets. The plugin tree is a shipped runtime mirror, not a second
  authoring location.
- The repository is a pin-consuming fleet member: its lint, formatting,
  strict type-checking, and coverage gates come from the fleet enforcement
  suite at a pinned release, and the aggregate check target is the single
  local, pre-push, and CI entry point.
- The product package holds one hundred percent statement AND branch
  coverage; coverage exceptions are individually annotated in source with
  their reasoning, never blanket-excluded.
- The standard-library-only rule (per constraints.md §"Language and
  dependencies") is enforced at review, by the manager's required bootstrap
  into its `-I -S` companion runtime, and by an integration test that stages
  only the product package and exercises every substantive executable path
  with no installed third-party packages. A library vendored in-tree under the
  exemption in that same section is staged with the package by construction
  and does not fail that test.

## Scenarios

- Every scenario heading in `scenarios.md` maps to test evidence through the
  repository's heading-coverage registry; a scenario's evidence is
  integration-tier or better, never a unit-tier test.
- New protocol behavior ships with its scenario and its pinning test in the
  same change, so the scenario file and the deterministic suite cannot
  drift apart.
