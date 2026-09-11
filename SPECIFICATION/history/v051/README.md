# livespec-overseer

This tree is the living specification for livespec-overseer, the
Control-Plane operator tool whose governed behavior includes long-running
agent supervision, identity-only account rotation and direct LLM credential
provisioning. The supervision contract watches context headroom and restarts a
session only after its filesystem declaration; the credential contracts keep
account identity, secret lifecycle and isolated consumer provisioning distinct.

What each file governs:

- `spec.md` — the operator-facing behavior: the supervision cardinal rule, the
  out-of-band state declaration, the supervision round, the escalating
  wrap-up, the keep-going nudge, session-name derivation, the fail-soft posture,
  the watch-set declaration, discovery and mapping store, account rotation,
  LLM credential lifecycle and coexistence proof.
- `contracts.md` — the wire-level surfaces and exact security or crash-safety
  mechanisms that make them enforceable: the state file and its grammar, the
  restart interlock, the injection and nudge obligations, the durable stores'
  shapes, bootstrap preconditions, daemon invocation, account publication and
  credential consumer protocol.
- `constraints.md` — the observable architecture boundaries: the declared
  Linux-plus-tmux requirement, the standard-library-only rule, the
  determinism boundary, filesystem boundaries, atomicity, and acting
  safety.
- `non-functional-requirements.md` — the contributor-facing invariants:
  hermetic beside-tests, the pinned fleet enforcement gates, and the
  disciplines that keep the protocol and its tests in lockstep.
- `scenarios.md` — the operator-observable behaviors as plain Gherkin, grouped
  by named behavioral outcome.

The specification governs these observable operator contracts, the exact
security and crash-safety mechanisms expressly required by `contracts.md`, and
the contributor-facing internal-composition constraints stated explicitly in
`non-functional-requirements.md`; it does not otherwise govern the internal
composition of the Python package or the interactive pane's operator-cockpit
presentation. A non-functional restatement of one of those mechanisms defines
its contributor-facing enforcement rather than a second contract. Deeper maintenance documentation for developers changing the
implementation lives beside the code it describes.

Changes to this tree flow through the governed lifecycle: file a proposed
change, then accept or reject it in a revise pass that snapshots the result
as a new version under `history/`.
