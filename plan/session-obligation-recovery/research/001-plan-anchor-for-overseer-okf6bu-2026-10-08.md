## The maintainer's statement of what done means

- **Durable ownership and deadlines:** dispatch creates an obligation that survives the coordinator’s turn ending. An external watcher delivers failures and overdue results to a responsible session.

## Definition of Done assertions derived from that statement

- After a real Codex coordinator in Herdr completes its turn, including FINAL, without arming a wait, a later failed gate on its registered obligation causes the released daemon to execute one authorized recovery command within 60 seconds without a human prompt.
- Losing the coordinator or the first recovery owner preserves the obligation, and the released daemon's installed takeover path executes recovery within 60 seconds while duplicate events produce one command effect.
- A legitimate human HOLD, running commit or open Red-Green pair defers recovery with a recorded deferral and no prohibited mutation, and the still-authorized recovery executes within 60 seconds of actual clearance.
- A monitored parked session whose wait ended unacknowledged appears on the existing operator attention surface within 60 seconds, even with a live ineffective waiter and unavailable telemetry.

# Session-obligation recovery: the plan anchor for `overseer-okf6bu` (2026-10-08)

Status of this note: the opening research note of plan
`session-obligation-recovery`. It exists to give the standalone work-item
`overseer-okf6bu` a plan anchor, so the overseer's half of the fleet's
durable-ownership discipline is tracked as a plan with a Definition of Done and
an archive gate rather than as one orphan item at `pending-approval`.

The Definition of Done assertions above this heading are SESSION-DERIVED. The
maintainer adopted the statement verbatim from the `overseer-herdr-rewrite`
session's proposal on 2026-10-08 and instructed that plans be opened for it; the
assertions were derived by the `factory-reliability` session (Claude Code,
`livespec-orchestrator-beads-fabro`) from `overseer-okf6bu`'s own host-captured
assertions, without the maintainer present to confirm them.

## 1. What this plan is

The orchestrator plan `agent-session-stall-prevention` (`bd-ib-jnpvh4`,
`livespec-orchestrator-beads-fabro`) owns the canonical obligation: a dispatch
or delegation registers a durable obligation with an owner, external run
reference, original deadline and result epoch BEFORE the external effect. The
relay plan `relay-delivery-and-progress-deadline` (`bd-ib-lrik25`) owns the
result reader, the epoch and changed-approach record, and the target-effect
relay. Neither can CONSUME an obligation after a coordinator's turn ends,
because neither is a long-lived process on the host.

The overseer daemon is. `overseer-okf6bu` ("Consume durable session obligations
and execute safe bounded recovery after coordinator exit", filed
2026-10-07T23:11Z, `pending-approval`) makes the EXISTING daemon the independent
consumer: it discovers unresolved obligations independently of coordinator
liveness, waiter liveness and notification delivery; claims one with a
generation-fenced recovery owner; executes the orchestrator's typed recovery
command within 60 seconds of a terminal target or expired deadline; defers at a
legitimate HOLD, running commit or open Red-Green pair; and publishes through
the existing OpenTelemetry/Honeycomb seam. Its contract is proposed, unratified,
in `SPECIFICATION/proposed_changes/session-obligation-recovery.md`
(`codex-gpt-6`, 2026-10-08T00:17Z) with six scenarios.

## 2. Why it needs a plan anchor

- It is the only live carrier of the "durable ownership and deadlines" idea in
  this tenant, and it was filed as a standalone item with no parent, so it is
  invisible to `list-plans`, has no handoff timeline, no carrier map and no
  archive gate — it can be closed without the host-captured proof it demands.
- Its released-host proof (a real Codex coordinator in Herdr completing its
  turn including FINAL, no wait armed, a later failed gate, one authorized
  recovery within 60 seconds) is a PLAN-level outcome: it binds the daemon, the
  orchestrator's reader and action interfaces, and the installed service
  restart path together. A plan Proof of Done is the record that can carry it.
- The spec change it depends on routes through `propose-change`/`revise` in
  THIS repository, and the ratification is a plan event, not an item event.

## 3. What the originating session experienced

From epic `overseer-uzvcbn`: a plugin cache build deleted under a live
`drive.py` (comment 23); retry exhaustion surfaced as `needs_human` with no
coordinator to receive it (comment 39); and the motivating case in the session's
proposal — a coordinator finished its turn with no wait armed, a later gate
failed, and nothing handled it until a human noticed. Older rows in this tenant
describe the same shape: `overseer-tdfe.3` (ready; the daemon does not watch
factory runs), `overseer-94fs` (acceptance; a background shell shields a track
unbounded), `overseer-1hv` (blocked; a caller-killed dispatcher leaves a phantom
`active` claim), `overseer-fs4` (blocked; a permanent failure category is
re-dispatched). Those four are cross-repo observations routed to the
orchestrator and are NOT re-parented here; they are the evidence, not the work.

## 4. Boundary

- Canonical obligation identity, deadline, epoch, reader and recovery command
  are orchestrator-owned (`bd-ib-jnpvh4`, `bd-ib-lrik25`). This plan MUST NOT
  invent a second result model.
- The cardinal restart rule is unchanged: recovery never kills or restarts a
  non-ready coordinator and never synthesizes its ready declaration.
- Steering or cancelling a LIVE run is the orchestrator plan
  `run-control-lease-and-versioned-instructions`; this plan acts only on a
  terminal target or an expired deadline.

## 5. Carrier

Every plan assertion is carried by `overseer-okf6bu`; the plan's own Proof of
Done record discharges them against the released daemon. The item stays at
`pending-approval` behind the spec ratification hold, exactly as filed.

## 6. Next steps for the plan session

1. Ratify the proposal through `propose-change`/`revise`, aligned with the
   orchestrator's `agent-session-stall-prevention` and relay proposals (both
   unratified as of 2026-10-08), and update `overseer-okf6bu`'s `References:`
   line to the ratified scenario.
2. Admit and dispatch `overseer-okf6bu` once the orchestrator's reader and
   action interfaces it consumes have landed (`bd-ib-77dipw`, `bd-ib-zi5ygh`,
   `bd-ib-t3znvw`, `bd-ib-zejlae`, `bd-ib-dle6l3`).
3. Take the released-host capture with a real Codex coordinator in Herdr and
   have a separately started session replay it.
