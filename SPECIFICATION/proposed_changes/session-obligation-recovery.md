---
topic: session-obligation-recovery
author: codex-gpt-6
created_at: 2026-10-08T00:17:51Z
---

## Proposal: independent-consumed-recovery-after-session-turn-end

### Target specification files

- SPECIFICATION/spec.md
- SPECIFICATION/contracts.md
- SPECIFICATION/scenarios.md

### Summary

Make the existing daemon independently consume authorized obligations and execute bounded safe recovery after actual Codex/Herdr turn completion or owner loss.

### Motivation

Maintainer-approved agent-session-stall-prevention plan bd-ib-jnpvh4 and actual consumer carrier overseer-okf6bu require launch-registered no-wait recovery, distinct receipt/consumption/fulfillment, 60-second actual execution, and OpenTelemetry/Honeycomb observability while preserving the cardinal ready-only restart rule.

### Proposed Changes

Add a contract H2 "Independent recovery of authorized session obligations" in contracts.md and a concise supervision-purpose clause in spec.md. This is an additional duty of the existing daemon, not a new operator skill, seat or daemon. The cardinal restart rule remains unchanged: recovery MUST NOT kill or restart a non-ready coordinator or synthesize its ready declaration. A separate authorized recovery worker may be started through a supported runtime route without replacing or interrupting that coordinator. The terminal owner and repository identity MUST be verified before acting.

The daemon MUST consume unresolved canonical required-result and relay obligations through the orchestrator's supported reader/claim/action interfaces on startup and during ordinary supervision. It MUST discover them independently of coordinator liveness, explicit wait registration and notification delivery. Canonical obligation identity, required-result reference and authoritative result reader, original deadline, epoch, causal recovery attempt identity and target-effect fulfillment belong to livespec-orchestrator-beads-fabro; overseer MUST NOT invent a second result model or reset those values. Repository/tenant reads MUST use the target's configured credential seam. Unreadable authority MUST remain unobservable, not no obligations. Local wait inventory may enrich observation but MUST NOT be the only discovery source.

Before dispatch/delegation is reported protected, the daemon integration MUST expose independently verifiable consumer coverage tied to the host, repository and authorized scope. Missing/unavailable coverage MUST produce an explicit unmonitored finding/refusal, never successful prevention. A mere live PID or submitted notification MUST NOT establish functioning coverage. Service restart and authorized recovery-owner takeover MUST reconcile outstanding obligations from durable state; the production installation MUST demonstrate that this path survives loss of the first consumer and coordinator.

On actual terminal target observation or the original required-result deadline, the daemon MUST execute the supported authorized recovery command within 60 seconds under declared supported host conditions while no legitimate safety barrier applies. The bound includes discovery, claim, worker start and actual command execution; it is NOT met by a notification, queued prompt, receipt, lease, worker PID or report-only attention. The ordinary installed service recovery/takeover path MUST preserve this bound when the first owner dies. The execution adapter MUST preserve a durable effect receipt and resulting authorized next action. An unsupported host or runtime path MUST remain explicitly uncovered with the proof assertion unmet.

Claims MUST use the canonical recovery attempt id with serialized generation-fenced ownership through the orchestrator interface. Duplicate events, concurrent consumers and replacements MUST converge on one observed effect for the supported idempotent recovery command. An ambiguous crash after possible execution MUST trigger authoritative effect lookup before retry; unobservable lookup MUST retain uncertainty without duplicate execution. Notification production, receipt acknowledgment, claim, execution start/evidence, reconciled next action and target fulfillment MUST remain distinct. Execution alone MUST NOT satisfy the original required result; only the canonical reader's authoritative target evidence can do so. No universal exactly-once guarantee for arbitrary shell commands is implied.

Before mutation the consumer MUST re-read current authority, result epoch, safety state, ledger, forge and the run's actual recorded remote factory. A stale completed diagnostic pointer MUST be reconciled instead of blindly repeated. A failed local gate MUST NOT be treated as proof its remote run or merged PR failed. Recovery MUST invoke sanctioned typed operations and preserve admission, spec, proof and lifecycle guards. Expiry MUST trigger diagnosis within existing authority, never invent a human blocker. A genuine missing authorization or decision may route to a person. A declared changed approach or repair-child milestone MUST NOT reset the original obligation deadline.

A valid human HOLD MUST retain its authority, reason, owner and release condition. A running commit/hook or open Red-Green pair MUST likewise defer mutation while durable observation and obligation retention continue. The consumer MUST record the named safety deferral within 60 seconds of the trigger, preserve the protected work and original deadline, and execute one still-authorized recovery within 60 seconds after actual legitimate clearance. Ordinary idle state, an unanswered notification and a prose deadline MUST NOT count as a HOLD. The new consumer MUST NOT relax any existing live-input, identity, restart-readiness or terminal-safety interlock.

Durable consumer state MUST use existing daemon store facilities only for service observation/ownership necessary to invoke the canonical orchestrator interfaces; it MUST NOT duplicate canonical result or progress state. Atomic writes and existing locking/fail-closed rules apply. Storage failure MUST surface a diagnostic and prevent a false claim of consumption or functioning coverage. Consumer writes MUST NOT manufacture a supervised session's state declaration.

Observations and numeric measurements MUST publish through the existing overseer OpenTelemetry enrichment/scrub and Honeycomb route when configured, preserving livespec-family namespace and shared obligation/epoch/attempt correlation. Required observations include coverage, notification/receipt, claim, actual execution, safety deferral, reconciliation and resulting action; numeric fields include original deadline age, recovery latency and duplicate/fencing counts. Only curated safe fields may leave the host; raw prompts, commands, transcripts, secrets and credential-bearing paths MUST NOT be exported. Export MUST be bounded asynchronous work; outage/partial rejection/queue loss MUST remain locally visible and MUST NOT block local discovery, wake, execution or safety. Honeycomb is an observation projection, never recovery authority.

Add these Given/When/Then scenarios and co-edit tests/heading-coverage.json with overseer-okf6bu as the owned implementation/proof carrier:

1. "A real Codex coordinator in Herdr resumes authorized recovery after FINAL": Given normal installed releases, a real authenticated Codex coordinator in Herdr and a launch-registered detached gate obligation with no explicit wait, When the coordinator completes its actual turn including FINAL and the gate later fails, Then the independent consumer executes one supported authorized recovery command within 60 seconds without a human prompt and records its effect and resulting next action. Repeat idle and gone coordinator. Neither Claude Stop nor simulation satisfies this assertion; label other runtimes independently. Unsupported Codex no-wait coverage means the actual incident remains uncovered.
2. "Recovery survives waiter notification and consumer loss": Given the same durable obligation, When there is no waiter, a waiter dies, notification is dropped or the first recovery owner dies, Then ordinary installed service reconciliation/takeover preserves the original deadline and performs actual recovery within 60 seconds with stale owners fenced. Missing all independently verified coverage refuses protected launch and cannot pass prevention proof.
3. "Recovery receipt and target fulfillment remain separate": Given receipt/claim without execution, When inspection runs, Then the obligation is unconsumed and unmet. Given actual execution, Then consumption is observable but target fulfillment still requires authoritative evidence. Include original deadline expiry with no new handoff as a trigger and stale completed diagnostic/failed gate with merged remote PR as reconciliation controls.
4. "Duplicate recovery reconciles an ambiguous command effect": Given duplicates, competing generations and a crash after possible command execution, When the replacement recovers, Then durable effect lookup yields one supported effect; uncertain lookup remains unobservable without re-execution.
5. "Legitimate safety barriers defer recovery without killing a coordinator": Given a real human HOLD, active commit/hook or open Red-Green pair, When failure/expiry occurs, Then the specific deferral is recorded within 60 seconds and no prohibited mutation occurs. When actual clearance occurs, Then one authorized recovery executes within 60 seconds. A non-ready coordinator is never killed or restarted to meet the bound, and idle state alone grants no hold.
6. "Consumer telemetry failure cannot suppress local recovery": Given unique obligation/epoch/attempt identities, When recovery and safety transitions occur, Then Honeycomb retrieves the scrubbed identity-linked events and numeric measurements. Repeat with export unavailable, partial rejection and queue overflow; local recovery and safety remain effective with explicit degradation.

Ratification MUST align with the orchestrator's shared relay semantics and stall consumer contract. The released-host capture and independent replay MUST measure actual command effects through normal installed surfaces, including no-wait Codex/Herdr FINAL, first-owner loss and safety negatives. Report-only attention, a referral, a test's existence or a merged implementation item MUST NOT be claimed as autonomous prevention. The filed overseer-okf6bu remains behind spec/admission gates until this contract ratifies and references its governing scenario.

