---
topic: caam-anthropic-loop-operation
author: claude-opus-5-1m
created_at: 2026-08-20T09:39:21Z
spec_commitments:
  impl_followups:
    - id_hint: caam-decision-core
      description: |
        Implement the pure decision core: the usage record shape, weekly-remaining derivation, the binding-allowance selection, relative eligibility with its zero-weekly and zero-five-hour disqualifiers, the weekly-reserve filter and its release retry, and candidate ranking by soonest weekly reset with unknown reset timestamps sorting last. No I/O; table-driven tests over every branch. Carriers F, G, H of plan/caam-anthropic-loop/research/feature-inventory.md.
    - id_hint: caam-rendering
      description: |
        Implement rendering: duration formatting that drops units from the left, relative reset rendering with its unreadable-timestamp fallback, display-width padding of the CURRENT column, the table header and row format specifiers, the trigger header line, and every hold, trigger, forced, dry-run and switched decision line. Carriers R and S1-S5.
    - id_hint: caam-usage-io
      description: |
        Implement credential reading and usage polling: the claudeAiOauth parse with millisecond expiry conversion, the local expiry skip with its skew margin, the never-raising fetch with its HTTP-error message extraction, the scoped Fable limit extraction, and the unexpected-response-shape guard. Assert that no code path performs an OAuth refresh. Carrier C.
    - id_hint: caam-profiles-state
      description: |
        Implement profile enumeration and the reading cache: vault listing with underscore-prefixed entries excluded, the active profile always present, live versus cached versus dark sourcing with the cache-age bound, and atomic mode-0600 state persistence under a mode-0700 directory. Carrier D.
    - id_hint: caam-active-identity
      description: |
        Implement active-profile identification: prefer the caam status JSON, and fall back to matching the live account UUID against each snapshot when the tool omits the active profile after a token refresh. Carrier E, including a regression test for the refresh case that previously stalled the loop.
    - id_hint: caam-switch
      description: |
        Implement the switch: the non-blocking exclusive lock, the under-lock re-read that abandons a stale decision, the under-lock re-probe of the destination credential, the activate invocation, post-switch stick verification, table re-render against the new active profile, and every associated exit code. Carriers I, J1, S6-S9, T.
    - id_hint: caam-effort-floor
      description: |
        Implement effort re-assertion as a floor rather than an exact value, rewriting only that one settings key atomically and preserving hooks, environment, plugin and MCP configuration, and running even when model enforcement is disabled. Carrier K.
    - id_hint: caam-session-discovery
      description: |
        Implement session discovery and model reading: pane process-tree walk to the Claude session identifier, transcript location by that identifier, tail-bounded model extraction with prefix mapping, the unknown-means-may-need-setting rule, and the bounded per-session set memo. Assert the model is never read from the terminal status line. Carriers M and N.
    - id_hint: caam-picker-driving
      description: |
        Implement picker driving: the idle guard, menu parsing scoped to the menu, name-based row matching with its label-first two-pass order, modular cursor arithmetic for the wrapping menu, the second confirmation dialog, and the invariant that no horizontal navigation key is ever emitted. Preserve the deliberate absence of verification, retry and recovery. Carriers O and P.
    - id_hint: caam-enforcement-orchestration
      description: |
        Implement enforcement orchestration: the four model-precedence rules against the active account's scoped-model balance, exact foreman-suffix matching, per-session and whole-pass failure isolation, the disable flag, and the summary line. Carriers L and Q.
    - id_hint: caam-operation-surfaces
      description: |
        Author the harness-neutral operation prose and bind it into all three harnesses, with manifest versions in lockstep, so the operation is a first-class peer of foreman and grooming. Includes schedule self-installation, invocation-mode resolution and the verbatim-reporting contract. Carriers A and B.
    - id_hint: caam-foreman-model-override
      description: |
        Implement the persisted operator override that pins which model the foreman-suffixed sessions run, overriding the scoped-model precedence rules, together with persisting operation state after enforcement rather than before it. The override exists for a non-quota failure mode that no balance-derived rule can observe. Carriers V and W of plan/caam-anthropic-loop/research/feature-inventory.md.
    - id_hint: caam-completeness-review
      description: |
        Commission and record the independent feature-completeness review that gates plan archival: a reviewer with no role in the implementation walks every carrier against the rebuilt code, treats the originating program as the oracle, and explicitly confirms both that the superseded scoped-model tiering was not re-implemented and that every deliberate absence survived.
---

## Proposal: Specify the account-rotation and quota-supervision operation

### Target specification files

- SPECIFICATION/spec.md

### Summary

The specification governs the supervision contract but says nothing about quota supervision of the Claude accounts the supervised fleet actually spends. A working implementation of that supervision exists outside this repository, is coupled to this repository's own foreman naming convention, and carries a documented instruction to move here and be rebuilt spec-first. This proposal adds the normative behavioral contract for that operation: what it observes, when it MUST rotate the active account, which candidates are eligible, how they are ranked, which safety invariants MUST hold, and how an operator MAY override model enforcement for a failure mode the quota rules cannot observe, so that the operation is specified before it is built rather than described after.

### Motivation

Directed by the maintainer, who owns and wrote the existing implementation, to capture its features and drive a feature-identical rebuild in this repository under red-green discipline, as a plugin operation alongside foreman. The originating repository's own agent guidance closes its section on the skill by stating that it is coupled to livespec-overseer fleet conventions, that it should move to that repository and be rebuilt spec-first with red-green tests, and that the existing pass is deliberately a working best-effort implementation and not the final home. The complete measured feature inventory is held as write-once research at plan/caam-anthropic-loop/research/feature-inventory.md under plan epic overseer-54k2za; that inventory enumerates the carriers this proposal governs.

### Proposed Changes

Add a new top-level section to `spec.md`, `## Account rotation and quota supervision`, carrying the following normative rules.

**Scope.** The operation MUST observe every account tracked by the host's coding-agent account manager, MUST report their remaining quota, and MUST rotate the host-wide active credential when the active account's allowance is nearly spent. It MUST NOT implement, install, or version the account-manager binary itself; that remains a host concern.

**Observation.** The operation MUST derive every quota figure from utilization percentages and MUST NOT depend on the monetary fields of the usage response, which are absent on the subscription plans in use. It MUST poll the active account with the live credential and every other account with that account's stored snapshot. It MUST treat an absent scoped-model allowance as a normal condition and not as an error.

**Never refresh.** The operation MUST perform read-only requests only and MUST NOT perform an OAuth refresh under any circumstance, because rotating a refresh token outside the agent's own control can revoke the whole token family. It MUST detect a locally-expired token and skip the request rather than send it, because the usage endpoint backs off a specific repeatedly-rejected token and a loop that retries a dead token manufactures the error it then reports.

**Identity.** The operation MUST NOT depend solely on the account manager's own report of which profile is active. That report is derived by byte-matching the live credential against each snapshot and therefore becomes unavailable whenever the agent refreshes its own token as normal operation. The operation MUST fall back to matching a stable account identifier that survives token rotation, and MUST fail loudly only when both paths fail.

**Rotation triggers.** The operation MUST rotate when the active account's short-window allowance is at or above a configurable threshold, or when its weekly remaining falls below a configurable reserve. The threshold SHOULD be set high enough that the window is nearly drained before moving, but low enough that heavy fleet use cannot cross the remaining margin between two polls. Candidates MUST be compared on whichever dimension triggered the rotation; comparing on a dimension that is not the reason for leaving MAY select an account that is no better off in the way that matters.

**Eligibility.** A candidate MUST hold at least a configurable margin more headroom than the active account on the triggering dimension. This test MUST be relative rather than absolute: an absolute test strands the fleet once every account sits just above the bar, holding while the active account runs to exhaustion. The margin also makes oscillation impossible, since a switch requires a strict improvement that the reverse move cannot match. A candidate MUST be disqualified when it has no weekly allowance remaining or cannot serve a request immediately.

**The weekly reserve MUST NOT be forfeited.** Candidates below the reserve MUST be excluded while any candidate is above it, and the reserve MUST be released once every account is below it, since at that point it protects nothing.

**A scoped-model allowance MUST NOT influence account selection.** It MUST NOT trigger a rotation, MUST NOT disqualify a candidate, and MUST NOT tier or rank candidates. Such an allowance caps how much of the weekly allowance a single model may spend and draws down the general weekly allowance as it is used, so leaving it unspent forfeits no capacity while leaving weekly unspent forfeits it permanently. The allowance MUST inform only which model a session runs.

**Ranking.** Eligible candidates MUST be ranked by soonest weekly reset, so that the most perishable balance is spent first. A candidate whose reset time cannot be read MUST sort last and MUST NOT be treated as imminently resetting.

**Only a live-verified account MAY be switched onto.** A candidate whose own stored credential could not be exercised during the current pass MUST NOT be selected, because that credential is precisely what a switch installs as the host-wide login, and post-switch verification cannot detect the failure: the switch succeeds onto a dead token. The operation MUST accept that this rule can stall rotation entirely when every alternative account has gone dark, and in that case it MUST hold, MUST report which accounts could not be verified, and SHOULD state how to revive them. A stalled rotation costs quota; a bad switch stops every running session on the host.

**Switching.** The decision-and-switch sequence MUST be serialized by a non-blocking host-level lock, and a caller that cannot take the lock MUST hold rather than wait. Holding the lock, the operation MUST re-read the active account and abandon a decision whose premise changed, and MUST re-exercise the destination credential immediately before installing it. After switching it MUST verify the switch took effect and MUST report a failure rather than a success when it did not, since concurrent sessions share the credential file and MAY silently reinstate the previous account.

**Model enforcement.** Sessions whose name carries the foreman suffix MUST be pointed at the scoped model while the active account retains that allowance, and at the general model otherwise; when the allowance is spent, every other agent session MUST also be reset to the general model, and otherwise other sessions MUST be left alone. Suffix matching MUST be exact. Enforcement MUST be advisory and best-effort: a busy session MUST be skipped rather than driven, a failure affecting one session MUST NOT stop the sweep, and no enforcement failure MAY disturb the quota report or the rotation.

**An operator override MUST be able to pin the enforced model, and it MUST persist.** The precedence rules above are all derived from the scoped-model *balance*, so they cannot observe a model that is available but not answering — a model refusing requests for non-quota reasons reads as perfectly healthy, and enforcement goes on pinning sessions to it. The operation MUST therefore accept an explicit operator pin that overrides the foreman precedence rules, MUST leave the rules governing other sessions unaffected by it, and MUST persist the pin in its durable state. Persistence is not a convenience: the operation re-runs on a schedule, so a pin that lasted one run would be reverted by the next tick and would appear to work while doing nothing. The operation MUST provide a way to clear the pin and restore derived behavior, MUST ignore an unrecognized pin value without failing and without disturbing an existing pin, MUST ignore a stored pin value it does not recognize so that corrupt state degrades rather than breaking enforcement, and MUST report when a pin is in effect. Where a pin selects a model whose allowance is exhausted, the operation MUST warn and MUST still honor the pin; the operator is warned, not overruled.

**Operation state MUST be persisted after enforcement, not before it.** Enforcement writes durable state of its own — at minimum the operator pin and the per-session suppression memo. Persisting before enforcement runs discards those writes, which silently defeats both while leaving every observable symptom of a working implementation. The persistence step MUST run even when enforcement itself failed, and MUST NOT be able to fail the run.

**Session identity.** A session's model MUST be determined programmatically and MUST NOT be read from the terminal status line, which truncates in a narrow pane and previously caused affected sessions to be classified as non-agent sessions and excluded from enforcement indefinitely. A session whose model cannot be determined MUST be treated as possibly needing to be set rather than skipped, and repeated attempts against such a session MUST be bounded by a time-based memo.

**Effort MUST be re-asserted as a floor.** Installing an account's snapshot restores a settings file that carries the reasoning-effort key, so a rotation silently overwrites it. The operation MUST restore the configured effort when the live value is lower, MUST leave a deliberately higher value untouched, and MUST rewrite only that key, preserving hook, environment, plugin and integration configuration in the same file.

**Fail loudly.** Every failure path MUST emit a clearly-marked failure line and exit non-zero, including unexpected failures, so that a missing binary or an unwritable state directory can never present as a quiet success.

## Proposal: Specify the account-rotation operation's surfaces, durable store and reporting contract

### Target specification files

- SPECIFICATION/contracts.md

### Summary

The behavioral rules proposed for the specification need a mechanical counterpart: which artifacts constitute the operation, where its durable state lives and under what permissions, how its recurring schedule is established and deduplicated, how an invocation's mode is resolved, and what a caller is obliged to show the operator. This proposal adds that contract so the operation is a first-class plugin operation of this repository rather than a script, and so its completeness is mechanically checkable.

### Motivation

Same directive as the companion proposal. The existing implementation embeds its entire program inside a markdown skill file and has no tests, which is the specific deficiency the rebuild exists to remove. Specifying the surfaces and the durable store is what makes the operation testable and what lets the repository's existing plugin-resolution, skill-invocation-path, and manifest-lockstep gates apply to it. Carriers A, B, D8, S6 through S9, and T of plan/caam-anthropic-loop/research/feature-inventory.md.

### Proposed Changes

Add a new top-level section to `contracts.md`, `## The account-rotation operation`, carrying the following contract.

**Surfaces.** The operation MUST be constituted as a first-class plugin operation, peer to the foreman and grooming operations. It MUST provide exactly one harness-neutral prose contract holding the complete operator-facing behavior, and one thin binding per supported harness that resolves the plugin root and reads that prose. A binding MUST NOT carry operation behavior of its own. Plugin manifest versions MUST be bumped in lockstep across every manifest that declares the operation.

**Implementation location.** The operation's deterministic behavior MUST be implemented as importable modules of this repository's package with tests beside them, and MUST NOT be embedded as program text inside a prose or binding artifact. Configuration values that a test needs to vary MUST be resolved when they are used rather than fixed when the module is imported.

**Reuse.** The operation MUST drive terminal panes through this repository's existing pane input and output surface, and MUST read process attributes through this repository's existing process-reader seams, rather than introducing parallel implementations of either.

**Schedule.** The operation MUST establish its own recurring schedule and MUST check for an existing schedule before creating one, so that a scheduled invocation cannot breed a duplicate. An existing schedule whose prompt lacks the scheduled marker MUST be replaced with one that carries it. The operation MUST NOT be wrapped in a generic looping facility, which would produce a second overlapping schedule. On establishing a schedule the operation MUST disclose its identifier, its interval, that it survives only while the establishing session remains open, that it expires after a bounded period, and how to cancel it.

**Mode resolution.** An invocation carrying the scheduled marker MUST respect the rotation triggers. An invocation without it MUST be treated as an explicit request to rotate now and MUST bypass the triggers, while still refusing any move that would lose headroom and still refusing an exhausted destination. Marking the scheduled side rather than the manual side is deliberate: a lost marker MUST degrade to forcing a rotation, which is observable, rather than to never forcing one, which is silent.

**Reporting.** The caller MUST present the operation's account table to the operator verbatim and MUST NOT summarize or paraphrase its figures. On a reported failure the caller MUST surface it plainly and MUST stop; it MUST NOT retry with a relaxed threshold and MUST NOT attempt a switch by other means.

**Durable store.** The operation's cache and lock MUST live in a host state directory created with owner-only permissions, and the state file MUST be written atomically with owner-only permissions. Concurrent writers MAY overwrite one another, which MUST cost at most a cached reading and MUST NOT be able to corrupt the file. The lock MUST guard the decision, not the credential write, which the account manager already performs atomically.

**Concurrency.** Any number of concurrent callers MUST be able to report safely, since observation is read-only. At most one MAY switch. The contract MUST record, as accepted and unfixed, that a hand-run activation takes no lock, that a decision rests on readings taken moments earlier, and that schedules are not deduplicated across sessions.

**Exit contract.** A completed pass that held, reported, or switched successfully MUST exit zero. Every failure MUST exit non-zero and MUST be preceded by a clearly-marked failure line, including failures arising from unexpected exceptions, which MUST be caught at the top level rather than surfacing as an untrimmed traceback.
