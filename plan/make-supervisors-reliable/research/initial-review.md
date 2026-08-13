# Initial review — make supervisors reliable

## Finding

The reported failure is real: the current `supervise-plan` contract tells a
supervisor to never end a turn while an open obligation remains and to arm a
wake source first, but its executable check only recognizes prose realizations.
A conversational agent remains mechanically able to end its turn. Existing
requirements therefore establish intent, not an enforceable completion gate.

## Boundary to preserve

The proposed direction must not make the overseer daemon infer semantic
completion from pane text. The existing specification reserves semantic
judgment to the supervised agent and treats unrecognized state as fail-closed.
The durable supervisor marker is `tmp/overseer/<topic>/.supervisor-state`,
distinct from the daemon's `.overseer-state` marker.

A safe gate can verify declared, structured facts rather than prose: open
obligations, an explicit `plan_complete` declaration, a structured
maintainer-block declaration, and live wake-producer evidence. It must reject
missing, malformed, stale, or unverifiable evidence. It must not parse a final
assistant response to decide whether work is done.

## Requirements carried forward

1. Persist the supervisor objective plus all obligations in the per-topic
   `.supervisor-state` JSON marker.
2. Provide a working Stop/turn-completion gate that fails closed while any
   obligation is open. Completion is permitted only for an explicitly complete
   plan or one recorded, genuinely maintainer-blocking question.
3. Require an armed independent wake source before completion while supervision
   remains active. Validate a live PID and command/producer or an authoritative
   producer identity, not a prose assertion.
4. Define external re-entry: a watcher or daemon wake reads the same marker and
   fresh ledger/forge state, then launches or resumes the supervisor. The ended
   chat turn must not be the wake mechanism.
5. Define additive user-message handling while `supervision_active` is true;
   only explicit `stop supervising <topic>` or `replace supervision objective`
   clears or replaces the state.

## Initial delivery slices

- Ratify the state schema and completion/wake invariants in the governed
  specification, including how the hook distinguishes declared completion from
  an allowed maintainer block.
- Implement the actual Stop-hook/gate and wake-producer verification in the
  Driver-owned control layer that can prevent a turn from ending; prove it with
  negative tests for no hook, stale PID, wrong producer, malformed marker, and
  an open obligation.
- Update `supervise-plan` generation and its fixtures/tests to emit the schema,
  arm a supported producer, and hand an external wake a cold-open marker plus
  fresh ledger/forge reads.
- Exercise a complete supervised cycle with a real external producer and
  capture evidence that user input is additive unless one of the two explicit
  override commands is used.

## First decision

Do not begin by merely strengthening charter prose. First locate the concrete
Driver hook surface and producer APIs, then file the implementation slices
against the repository that owns each executable boundary. This repository
should own only its specification and `supervise-plan` generator/test changes;
a Driver implementation that lives elsewhere must be routed rather than copied.
