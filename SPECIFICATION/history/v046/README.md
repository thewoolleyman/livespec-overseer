# livespec-overseer

This tree is the living specification for livespec-overseer, the
Control-Plane operator tool that keeps long-running agent sessions
productive across context exhaustion: it watches every tracked session's
remaining context headroom, injects an escalating wrap-up as a session
approaches its limit, and atomically restarts a session ONLY once that
session has declared itself ready on the filesystem.

What each file governs:

- `spec.md` — the supervision contract itself: the cardinal rule, the
  out-of-band state declaration, the supervision round, the escalating
  wrap-up, the keep-going nudge, the watch-set declaration, discovery and
  the mapping store, session-name derivation, and the fail-soft posture.
- `contracts.md` — the wire-level surfaces: the state file and its grammar,
  the restart interlock, the injection and nudge obligations, the durable
  stores' shapes, the daemon invocation, and the bootstrap preconditions.
- `constraints.md` — the observable architecture boundaries: the declared
  Linux-plus-tmux requirement, the standard-library-only rule, the
  determinism boundary, filesystem boundaries, atomicity, and acting
  safety.
- `non-functional-requirements.md` — the contributor-facing invariants:
  hermetic beside-tests, the pinned fleet enforcement gates, and the
  disciplines that keep the protocol and its tests in lockstep.
- `scenarios.md` — the operator-observable behaviors as plain Gherkin, one
  guarantee per scenario.

The specification governs the SUPERVISION CONTRACT — what the daemon and
the thin interactive pane guarantee — not the internal composition of the
Python package, and not the interactive pane's operator-cockpit surface.
Deeper maintenance documentation for developers changing the implementation
lives beside the code it describes, in the implementation tree.

Changes to this tree flow through the governed lifecycle: file a proposed
change, then accept or reject it in a revise pass that snapshots the result
as a new version under `history/`.
