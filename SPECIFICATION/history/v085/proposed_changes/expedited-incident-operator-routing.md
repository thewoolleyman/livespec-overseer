---
topic: expedited-incident-operator-routing
author: codex:expedited-incident-response-flag/runtime-applicability
created_at: 2026-11-03T19:18:30Z
---

## Proposal: Receipt-bound incident operator routing with normal factory repayment

### Target specification files

- SPECIFICATION/spec.md
- SPECIFICATION/contracts.md
- SPECIFICATION/scenarios.md

### Summary

Permit only canonical incident repair/revert routing through the existing drain operator, then require same-item normal factory repayment without weakening ordinary supervision or bypass guards.

### Motivation

Ratify the overseer-owned incident-only operator route for the authorized priority-1 expedited incident response plan livespec-dev-tooling-bqnzcm: canonical receipt authorizes local repair/revert; same-item normal factory repayment and ordinary bypass prohibitions remain complete. Current drain-backlog prose has only infra-in-person, factory-path-defect and workflow-only exemptions; a label alone is insufficient authorization. Shared execution and lifecycle mechanisms remain in their owning repositories.

### Proposed Changes

In spec.md, extend the governed observable scope to include only the incident-routing behavior of the existing drain-backlog operator surface described below. This adds no skill, resident seat, daemon, independent incident lifecycle or store.

Append to contracts.md:

## Expedited incident operator routing

The existing drain-backlog operator route MUST distinguish a canonical authorized incident repair or emergency revert from ordinary work before factory admission, credential probing or a green-master precondition. The operator MUST resolve the incident item, attempt, phase, repository and current operation identity through the active implementation orchestrator's supported incident reader, and MUST preserve that identity in the sanctioned dev-tooling invocation. An ambient flag, a retained code marker or a factory-exempt label alone MUST NOT authorize the route. An unavailable or unsupported incident reader MUST report the precise missing capability rather than inventing an exemption or creating another incident identity.

The closed factory exemption enum MAY include factory-exempt:expedited-incident for the exact receipt-bound repair or recorded revert phase. This label MUST be descriptive only: the operator MUST revalidate current canonical phase and ownership before any side effect, preserve cancellation/claim fences supplied by the orchestrator, and route an ordinary item or normal repayment phase through the factory. The operator MUST NOT pass an unrestricted allow-label to retrospective audits or treat a previously valid incident phase as current authorization. New incident intake MUST use the orchestrator's sanctioned fast canonical filing surface; any deferred admission judgement remains attached to that same item.

An authorized repair MUST use the installed mode-aware local worktree, commit and push route and record focused tests, touched-file coverage, manual reproduction and deferred-work receipts through the canonical incident surface. Its emergency revert MUST use the sanctioned recorded inverse route. The operator MUST retain generic prohibitions on --no-verify, LEFTHOOK disabling, primary-checkout mutation, unsafe host mutation and bare-backgrounded gate commands. The incident route MUST NOT dispatch the normal full aggregate or probe the factory merely to authorize local recovery. It MUST use the established detached command and independently verified supervising mechanisms without creating a shell polling loop or treating receipt acknowledgement as completion.

After the canonical observer records normal-master success, the operator MUST request a new unexpedited factory run on the SAME incident item with both flags absent, cumulative original change scope and all deferred evidence/spec obligations. A follow-up-only proof defect MUST be repaired within that normal follow-up without reverting healthy master solely for that finding; a canonically attributed deployed or other-PR regression MUST return to incident recovery under the orchestrator's generation fence. The operator MUST retain the incident obligation until the canonical reader confirms final normal factory, PR and master proof plus repaid debt. Existing plan proof/archive, ready-only restart and independent recovery interlocks remain fully effective. This section supplies operator routing only; the active orchestrator owns lifecycle/fences and dev-tooling owns execution selection. Rollout and development of this feature MUST remain normal and unexpedited.

Append to scenarios.md:

## Scenario: an incident repair returns to normal factory repayment before closure

```gherkin
Feature: Receipt-bound incident routing preserves normal repayment
  Scenario: Authorized repair takes the local incident route
    Given an active orchestrator reader confirms a current authorized incident repair item and attempt
    And installed mode-aware tooling and independently verified supervision are available
    When the drain operator routes that repair while factory admission or normal master health is unavailable
    Then it invokes the sanctioned local incident worktree commit and push route with the same immutable context
    And it records focused verification and deferred work without starting the normal factory or aggregate
    And generic hook bypass and unsafe mutation prohibitions remain effective
  Scenario: A descriptive label cannot authorize ordinary work
    Given an ordinary item or a stale incident attempt carries factory-exempt:expedited-incident
    When the drain operator checks current canonical phase and ownership
    Then the label grants no incident authorization
    And ordinary work keeps its normal factory route
  Scenario: Missing incident support is explicit
    Given the active orchestrator does not expose a readable supported incident context
    When an operator requests expedited incident routing
    Then the operator reports that missing capability and retains the unresolved obligation
    And it creates neither an exemption nor another incident identity
  Scenario: Successful repair retains same-item normal repayment
    Given the canonical incident observer records normal-master success for an expedited repair
    When the drain operator continues that incident
    Then it requests an unexpedited factory run on the same item with both incident flags absent
    And the run receives original cumulative scope and deferred evidence and specification obligations
    And the incident remains incomplete until final normal factory PR and master proof and repaid debt are confirmed
  Scenario: Follow-up findings and deployed regressions route differently
    Given an incident has a normal factory repayment in progress
    When a defect is found only by that deferred factory proof
    Then it is repaired in the follow-up without reverting otherwise healthy master solely for that finding
    When the canonical observer instead attributes a deployed or other-PR regression to the incident
    Then the operator follows the current generation-fenced recovery route on the same incident item
```

At ratification, co-edit tests/heading-coverage.json and its generated debt register for both new H2 headings in the same ordinary revise commit, with the owning implementation carrier. Do not claim the receipt reader or incident route is already shipped.
