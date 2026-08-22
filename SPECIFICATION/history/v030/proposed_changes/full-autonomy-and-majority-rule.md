---
topic: full-autonomy-and-majority-rule
author: claude-fable-5
created_at: 2026-08-22T00:19:20Z
---

## Proposal: Full autonomy and the panel decision rule: a configured delegation of maintainer authority to the foreman, with majority rule as a lever

### Target specification files

- SPECIFICATION/spec.md

### Summary

Adds a full_autonomy declaration and a decision_rule lever to the foreman's consensus policy in spec.md's foreman preamble. full_autonomy true delegates the maintainer's decision authority to the repo foreman: it forces the consensus disposition, selects the majority decision rule, and makes the locally-owned floor categories panel-decidable, while the cardinal rule, actuator-only mutation, journal-before-act and a security dissent survive unchanged and the floor categories owned by other contracts stay escalated. decision_rule (unanimous by default) replaces the hard-coded unanimity requirement wherever the policy names it, so the majority outcome already shipped by PR #1476 is ratified behind a lever rather than left as drift.

### Motivation

Maintainer direction 2026-08-22, recorded as plan foreman-full-autonomy-option (ledger anchor overseer-3h4s5w, opening research note plan/foreman-full-autonomy-option/research/opening-research-2026-08-22.md, decisions D1-D6 and D11). The maintainer's standing orders for this repository (seat anchor overseer-z5fo4y, 2026-08-20T22:38:36Z, re-issued 2026-08-21T22:38:29Z) delegate full decision authority to the repo foreman and state that contested calls go to the cross-vendor panel and MAJORITY OPINION WINS IN ALL CASES, with a security concern the panel cannot resolve as the only remaining escalation. Those orders exist today only as ledger comments typed into a pane: not a setting, not readable by the daemon, the actuator, the evaluator or the grooming seat, and not portable to another repository. This tree's own text says the floors "MUST NOT be relaxable by any configuration key; relaxing one requires a ratified amendment to this specification" — this proposal IS that amendment.

Two measured facts make it urgent rather than tidy. First, overseer-5stpf2 (PR #1476, merged 2026-08-21T23:25:11Z as 8f411c7) already lands an UNCONDITIONAL majority outcome for picker answers, so master now drifts from the sentence "ONLY when a cross-vendor review panel returns a unanimous typed verdict"; ratifying the majority outcome behind a decision-rule lever closes that drift and restores unanimity as the default for any repository that declares nothing. Second, four sessions in this repository sat parked on pickers because the matrix had no sanctioned majority path while the orders said majority wins; a directive the tooling cannot express is the stall shape the foreman-improvements plan was opened to remove.

Placement: this is the operator tool's own contract surface (spec.md preamble on the foreman, contracts.md §"The foreman valve disposition", constraints.md fail-closed paragraph, scenarios.md), not livespec core and not the orchestrator. Two floor categories this tree binds to BY REFERENCE — the orchestrator's needs-human disposition set and livespec core's drift acceptance — are deliberately NOT relaxed here; they stay escalated until those contracts ratify a relaxation, and the text says so, which is what keeps binding-by-reference honest.

In-flight alignment (default-align, compatible): the pending proposal the-convene-obligation adds a duty to SEEK a verdict under the consensus disposition and states that it does not relax the unanimity requirement; this proposal changes that requirement into a configured decision rule, and the convene obligation applies unchanged under either rule. When both are revised in, the convene obligation's sentence "to relax the requirement that a verdict be unanimous and typed" SHOULD read "to relax the requirement that a verdict satisfy the effective decision rule and be typed". The pending wait-premise and launch-profile proposals touch unrelated sections.

Implementation children already filed on the plan anchor: overseer-3h4s5w.2 (resolver and CLI), .3 (decision rule in the evaluator and actuator), .4 (conformance gate), .5 (local/foreign floor split). The conformance gate — which makes full_autonomy refuse any sibling autonomy lever below its maximum — is an enforcement mechanism in this repository's toolchain and is deliberately not specified here; it is a contributor-facing gate, not a behaviour a governed consumer inherits.

### Proposed Changes

All edits are to the un-headed foreman preamble of spec.md (the region between the paragraph beginning "The foreman's disposition of an action the governing orchestrator contract classifies as a human valve MUST be selected by configuration" and the heading "### Relay and escalation discipline"). No existing paragraph is moved under a new heading; one new level-three subsection is ADDED immediately after the paragraph beginning "Every act the consensus disposition authorizes MUST be journaled before the act". If the pending proposal the-convene-obligation is revised in the same pass, its subsection "### The convene obligation" and this one are siblings in that region in either order.

EDIT 1 — replace the sentence "Under the consensus disposition the foreman MAY act on a human valve ONLY when a cross-vendor review panel returns a unanimous typed verdict, and only for a member of a closed, enumerated vocabulary." with:

"Under the consensus disposition the foreman MAY act on a human valve ONLY when a cross-vendor review panel returns a typed verdict that SATISFIES THE EFFECTIVE DECISION RULE (§"Full autonomy and the decision rule" below), and only for a member of a closed, enumerated vocabulary."

EDIT 2 — replace the sentence "The foreman MUST escalate, and MUST NOT act, when consensus evidence is unavailable or insufficient, when the panel disagrees, when any reviewer returns an insufficient-information verdict, or when the audit journal append fails." with:

"The foreman MUST escalate, and MUST NOT act, when consensus evidence is unavailable or insufficient, when the panel's verdicts do not satisfy the effective decision rule, when a reviewer verdict the effective decision rule treats as a veto is present, when any reviewer response is structurally unusable (a missing or unpinned identity, a malformed response, a reviewer tool failure or timeout), or when the audit journal append fails."

EDIT 3 — replace the sentence "A dissent that is not vendor-aligned with the majority MUST NOT be overridable by the remaining reviewers." with:

"Under the unanimous decision rule a dissent that is not vendor-aligned with the majority MUST NOT be overridable by the remaining reviewers. Under the majority decision rule the only non-overridable dissent is a SECURITY DISSENT as defined below."

EDIT 4 — in the paragraph beginning "No configuration value MAY authorize the foreman to dispose of a truly unresolvable decision, nor of any decision that is human-gated BY DESIGN", replace its final two sentences "Each of these MUST stay escalated even when the panel is unanimous and fully confident. Such a floor MUST NOT be relaxable by any configuration key; relaxing one requires a ratified amendment to this specification." with:

"Each of these MUST stay escalated even when the panel is unanimous and fully confident, EXCEPT as §"Full autonomy and the decision rule" provides for the categories this specification itself owns. No configuration key other than full_autonomy MAY relax any floor, full_autonomy MAY relax only the locally-owned categories that section enumerates, and every other relaxation requires a ratified amendment to this specification."

EDIT 5 — add the following subsection immediately after the paragraph beginning "Every act the consensus disposition authorizes MUST be journaled before the act":

### Full autonomy and the decision rule

A governed repository MAY declare FULL AUTONOMY in its livespec configuration, as the `full_autonomy` key of this tree's configuration section. The declaration is a delegation by the maintainer of their own decision authority for that repository to the repository's foreman seat — the session named by the reserved `<repo-slug>-foreman` contract — for as long as the key reads true. It is boolean, and it MUST be read fail-closed: an absent, empty, wrong-typed, or non-true value MUST resolve to false, so a tree that declares nothing behaves exactly as it did before this section was ratified.

When full_autonomy resolves to true, the effective valve disposition MUST be consensus and the effective decision rule MUST be majority, REGARDLESS of the value of the valve-disposition key. A configuration that declares full_autonomy true together with an explicit report-only disposition is CONTRADICTORY: full autonomy MUST still win at runtime, because it is the key the maintainer set in order to override the others, AND the contradiction MUST be surfaced to the operator through the same observability the valve disposition already has. A contradiction MUST NOT be resolved silently to the cautious reading.

The DECISION RULE is the lever that states what a panel's verdicts must satisfy before the foreman may act. It is one of exactly two values. `unanimous` is the default and the effective value whenever full_autonomy is false: every reviewer returns the same typed action, and every condition this policy stated before this section was ratified applies unchanged, including the minority-report path and every single-reviewer veto. `majority` is the effective value whenever full_autonomy is true, and under it:

- a typed action held by a strict majority of the constituted reviewers AUTHORIZES that action, for every member of the closed vocabulary this policy admits, whether an action the foreman performs or a typed ruling a session executes;
- an insufficient-information verdict is an ABSTENTION: it neither vetoes nor counts toward any action, and the remaining reviewers decide if a strict majority of the constituted panel still agrees;
- a needs-human verdict, from any vendor, is one vote for escalation and MUST NOT veto on its own;
- a hard-risk dissent is one vote unless it is a SECURITY DISSENT: a needs-human verdict carrying a hard-risk marker whose declared risk kind is security, from ANY reviewer, MUST escalate and MUST NOT be overridable by any majority. Every hard-risk verdict MUST declare its risk kind; a hard-risk verdict that declares none is structurally unusable and MUST escalate as a tooling failure, never as a dissent;
- a panel with no strict majority for any single typed action MUST escalate;
- a structurally unusable reviewer response, a panel of the wrong size, and a failed journal append MUST escalate exactly as under the unanimous rule, because none of them is an opinion.

A verdict MUST record the decision rule it was evaluated under, and an act authorized under the majority rule MUST be journaled and recorded as a majority outcome; it MUST NOT be recorded as unanimous. The pre-act journal entry this policy already requires MUST additionally name the full_autonomy value and the decision rule in force.

Full autonomy relaxes the floors ONLY as follows, and this enumeration is closed. The truly-unresolvable and human-gated-by-design floor categories that THIS specification owns become panel-decidable under the majority rule. The floor categories this specification binds to BY REFERENCE — a disposition of an item the governing orchestrator contract holds for a human, and the acceptance of drift that livespec core's governance holds for a human or for unanimous consensus — MUST stay escalated under full_autonomy until the owning contract ratifies a relaxation, and this specification MUST NOT be read to relax them. Four floors survive full_autonomy verbatim and no configuration value MAY relax them: the cardinal rule stated in §"The cardinal rule"; the rule that every mutation the foreman performs goes through its own actuator and never by keystroking into a structured gate; the security dissent; and journal-before-act.

Full autonomy MUST be observable without running the foreman, on the same surface as the valve disposition, together with the effective decision rule and whether a contradiction was found. The foreman MUST NOT set, clear, or alter full_autonomy or the decision rule: nothing the foreman writes MAY change its own authority. The condition that ends a delegation — the maintainer's own terminating condition for the orders it records — is the maintainer's to apply by changing the key; the foreman MAY report that the condition appears reached and MUST NOT act on that report.

Full autonomy does not change what the daemon does. The daemon's observation-only posture toward the foreman, the cardinal rule, and the surface-only rules of this tree are unaffected by the key.

## Proposal: The foreman valve disposition section of contracts.md names full_autonomy and decision_rule as observable, fail-closed, non-self-settable keys

### Target specification files

- SPECIFICATION/contracts.md

### Summary

Extends contracts.md §"The foreman valve disposition" so the configuration contract covers the two values spec.md now depends on: the full_autonomy boolean and the derived decision_rule. Both MUST be readable without invoking the foreman, both fail closed, the implication and contradiction rules are stated on the wire surface, and neither may be written by the foreman.

### Motivation

Maintainer direction 2026-08-22, recorded as plan foreman-full-autonomy-option (ledger anchor overseer-3h4s5w, opening research note plan/foreman-full-autonomy-option/research/opening-research-2026-08-22.md, decisions D1-D6 and D11). The maintainer's standing orders for this repository (seat anchor overseer-z5fo4y, 2026-08-20T22:38:36Z, re-issued 2026-08-21T22:38:29Z) delegate full decision authority to the repo foreman and state that contested calls go to the cross-vendor panel and MAJORITY OPINION WINS IN ALL CASES, with a security concern the panel cannot resolve as the only remaining escalation. Those orders exist today only as ledger comments typed into a pane: not a setting, not readable by the daemon, the actuator, the evaluator or the grooming seat, and not portable to another repository. This tree's own text says the floors "MUST NOT be relaxable by any configuration key; relaxing one requires a ratified amendment to this specification" — this proposal IS that amendment.

Two measured facts make it urgent rather than tidy. First, overseer-5stpf2 (PR #1476, merged 2026-08-21T23:25:11Z as 8f411c7) already lands an UNCONDITIONAL majority outcome for picker answers, so master now drifts from the sentence "ONLY when a cross-vendor review panel returns a unanimous typed verdict"; ratifying the majority outcome behind a decision-rule lever closes that drift and restores unanimity as the default for any repository that declares nothing. Second, four sessions in this repository sat parked on pickers because the matrix had no sanctioned majority path while the orders said majority wins; a directive the tooling cannot express is the stall shape the foreman-improvements plan was opened to remove.

Placement: this is the operator tool's own contract surface (spec.md preamble on the foreman, contracts.md §"The foreman valve disposition", constraints.md fail-closed paragraph, scenarios.md), not livespec core and not the orchestrator. Two floor categories this tree binds to BY REFERENCE — the orchestrator's needs-human disposition set and livespec core's drift acceptance — are deliberately NOT relaxed here; they stay escalated until those contracts ratify a relaxation, and the text says so, which is what keeps binding-by-reference honest.

In-flight alignment (default-align, compatible): the pending proposal the-convene-obligation adds a duty to SEEK a verdict under the consensus disposition and states that it does not relax the unanimity requirement; this proposal changes that requirement into a configured decision rule, and the convene obligation applies unchanged under either rule. When both are revised in, the convene obligation's sentence "to relax the requirement that a verdict be unanimous and typed" SHOULD read "to relax the requirement that a verdict satisfy the effective decision rule and be typed". The pending wait-premise and launch-profile proposals touch unrelated sections.

Implementation children already filed on the plan anchor: overseer-3h4s5w.2 (resolver and CLI), .3 (decision rule in the evaluator and actuator), .4 (conformance gate), .5 (local/foreign floor split). The conformance gate — which makes full_autonomy refuse any sibling autonomy lever below its maximum — is an enforcement mechanism in this repository's toolchain and is deliberately not specified here; it is a contributor-facing gate, not a behaviour a governed consumer inherits.

### Proposed Changes

Append to contracts.md §"The foreman valve disposition", after its final paragraph ("The setting MUST NOT be settable by the foreman itself. Nothing the foreman writes MAY change its own disposition."):

The same configuration section MAY carry a `full_autonomy` key. It MUST be boolean, and the resolver MUST treat an absent, empty, wrong-typed, or non-true value as false without raising and without coercion. When it resolves to true, the effective disposition MUST be reported as consensus and the effective decision rule as majority whatever the disposition key says; when it resolves to false, the effective disposition MUST be exactly what the disposition key alone resolves to and the effective decision rule MUST be unanimous.

The resolver's output — the same surface that reports the effective disposition — MUST additionally report: the resolved `full_autonomy` value and its source (the configuration path or the default); the effective `decision_rule`, one of `unanimous` or `majority`; and a `conflict` indicator that is true exactly when `full_autonomy` is true and the disposition key is explicitly `report-only` or carries an unrecognized value. A conflict MUST be surfaced to the operator on that surface; it MUST NOT change the effective values, which full autonomy governs.

Neither `full_autonomy` nor the decision rule MAY be written by the foreman. Nothing the foreman writes MAY change its own authority, and no act the foreman journals MAY be read as having changed either value.

## Proposal: The fail-closed constraint covers full_autonomy and states that a contradiction is surfaced, never silently resolved

### Target specification files

- SPECIFICATION/constraints.md

### Summary

Extends the fail-closed paragraph of constraints.md that today covers only the valve disposition, so that full_autonomy resolves false on anything but an explicit true, a contradiction between full_autonomy and the disposition key is surfaced rather than quietly settled, the foreman can never widen its authority by writing either key, and the enumerated surviving floors are named as non-configurable.

### Motivation

Maintainer direction 2026-08-22, recorded as plan foreman-full-autonomy-option (ledger anchor overseer-3h4s5w, opening research note plan/foreman-full-autonomy-option/research/opening-research-2026-08-22.md, decisions D1-D6 and D11). The maintainer's standing orders for this repository (seat anchor overseer-z5fo4y, 2026-08-20T22:38:36Z, re-issued 2026-08-21T22:38:29Z) delegate full decision authority to the repo foreman and state that contested calls go to the cross-vendor panel and MAJORITY OPINION WINS IN ALL CASES, with a security concern the panel cannot resolve as the only remaining escalation. Those orders exist today only as ledger comments typed into a pane: not a setting, not readable by the daemon, the actuator, the evaluator or the grooming seat, and not portable to another repository. This tree's own text says the floors "MUST NOT be relaxable by any configuration key; relaxing one requires a ratified amendment to this specification" — this proposal IS that amendment.

Two measured facts make it urgent rather than tidy. First, overseer-5stpf2 (PR #1476, merged 2026-08-21T23:25:11Z as 8f411c7) already lands an UNCONDITIONAL majority outcome for picker answers, so master now drifts from the sentence "ONLY when a cross-vendor review panel returns a unanimous typed verdict"; ratifying the majority outcome behind a decision-rule lever closes that drift and restores unanimity as the default for any repository that declares nothing. Second, four sessions in this repository sat parked on pickers because the matrix had no sanctioned majority path while the orders said majority wins; a directive the tooling cannot express is the stall shape the foreman-improvements plan was opened to remove.

Placement: this is the operator tool's own contract surface (spec.md preamble on the foreman, contracts.md §"The foreman valve disposition", constraints.md fail-closed paragraph, scenarios.md), not livespec core and not the orchestrator. Two floor categories this tree binds to BY REFERENCE — the orchestrator's needs-human disposition set and livespec core's drift acceptance — are deliberately NOT relaxed here; they stay escalated until those contracts ratify a relaxation, and the text says so, which is what keeps binding-by-reference honest.

In-flight alignment (default-align, compatible): the pending proposal the-convene-obligation adds a duty to SEEK a verdict under the consensus disposition and states that it does not relax the unanimity requirement; this proposal changes that requirement into a configured decision rule, and the convene obligation applies unchanged under either rule. When both are revised in, the convene obligation's sentence "to relax the requirement that a verdict be unanimous and typed" SHOULD read "to relax the requirement that a verdict satisfy the effective decision rule and be typed". The pending wait-premise and launch-profile proposals touch unrelated sections.

Implementation children already filed on the plan anchor: overseer-3h4s5w.2 (resolver and CLI), .3 (decision rule in the evaluator and actuator), .4 (conformance gate), .5 (local/foreign floor split). The conformance gate — which makes full_autonomy refuse any sibling autonomy lever below its maximum — is an enforcement mechanism in this repository's toolchain and is deliberately not specified here; it is a contributor-facing gate, not a behaviour a governed consumer inherits.

### Proposed Changes

In constraints.md, replace the paragraph beginning "The foreman's valve disposition obeys the same fail-closed rule." with:

The foreman's valve disposition and its full-autonomy declaration obey the same fail-closed rule. The disposition's safe default is report-only, and an absent, empty, wrong-typed, malformed or unrecognized disposition value MUST resolve to report-only rather than to the nearest match. The full_autonomy declaration's safe default is false, and an absent, empty, wrong-typed, or non-true value MUST resolve to false rather than to the nearest match. An unrecognized value for either MUST NOT silently enable any act, and MUST be surfaced to the operator rather than accepted quietly. A configuration in which full_autonomy is true and the disposition is explicitly report-only or unrecognized is contradictory: full autonomy governs the effective values, and the contradiction MUST be surfaced, never silently resolved in either direction. The floors stated in spec.md are not configuration beyond the single, closed relaxation spec.md §"Full autonomy and the decision rule" grants to full_autonomy for the categories this tree owns: no setting MAY dispose of a decision a contract this tree binds to by reference holds for a human, no setting MAY relax the cardinal rule, actuator-only mutation, the security dissent, or journal-before-act, and unavailable evidence, a panel that fails the effective decision rule, or a failed journal append always resolve to escalation. The foreman MUST NOT widen its own authority on the basis of any evidence it produced itself, and MUST NOT set its own disposition, its own full-autonomy declaration, or its own decision rule.

## Proposal: Scenarios for full autonomy, the decision rule, the security dissent, the foreign-floor carve-out and the contradiction surface

### Target specification files

- SPECIFICATION/scenarios.md

### Summary

Amends the existing scenario "Unavailable or disagreeing consensus evidence escalates and mutates nothing" to key on the effective decision rule, and adds seven scenarios that pin the new behaviour in both directions: a majority authorizes under full autonomy; the same split escalates under the unanimous rule; an abstention does not veto under majority; a security dissent escalates under majority; a foreign-owned floor category stays escalated under full autonomy; an absent or non-true key resolves to no change; and a contradictory configuration is surfaced while full autonomy governs.

### Motivation

Maintainer direction 2026-08-22, recorded as plan foreman-full-autonomy-option (ledger anchor overseer-3h4s5w, opening research note plan/foreman-full-autonomy-option/research/opening-research-2026-08-22.md, decisions D1-D6 and D11). The maintainer's standing orders for this repository (seat anchor overseer-z5fo4y, 2026-08-20T22:38:36Z, re-issued 2026-08-21T22:38:29Z) delegate full decision authority to the repo foreman and state that contested calls go to the cross-vendor panel and MAJORITY OPINION WINS IN ALL CASES, with a security concern the panel cannot resolve as the only remaining escalation. Those orders exist today only as ledger comments typed into a pane: not a setting, not readable by the daemon, the actuator, the evaluator or the grooming seat, and not portable to another repository. This tree's own text says the floors "MUST NOT be relaxable by any configuration key; relaxing one requires a ratified amendment to this specification" — this proposal IS that amendment.

Two measured facts make it urgent rather than tidy. First, overseer-5stpf2 (PR #1476, merged 2026-08-21T23:25:11Z as 8f411c7) already lands an UNCONDITIONAL majority outcome for picker answers, so master now drifts from the sentence "ONLY when a cross-vendor review panel returns a unanimous typed verdict"; ratifying the majority outcome behind a decision-rule lever closes that drift and restores unanimity as the default for any repository that declares nothing. Second, four sessions in this repository sat parked on pickers because the matrix had no sanctioned majority path while the orders said majority wins; a directive the tooling cannot express is the stall shape the foreman-improvements plan was opened to remove.

Placement: this is the operator tool's own contract surface (spec.md preamble on the foreman, contracts.md §"The foreman valve disposition", constraints.md fail-closed paragraph, scenarios.md), not livespec core and not the orchestrator. Two floor categories this tree binds to BY REFERENCE — the orchestrator's needs-human disposition set and livespec core's drift acceptance — are deliberately NOT relaxed here; they stay escalated until those contracts ratify a relaxation, and the text says so, which is what keeps binding-by-reference honest.

In-flight alignment (default-align, compatible): the pending proposal the-convene-obligation adds a duty to SEEK a verdict under the consensus disposition and states that it does not relax the unanimity requirement; this proposal changes that requirement into a configured decision rule, and the convene obligation applies unchanged under either rule. When both are revised in, the convene obligation's sentence "to relax the requirement that a verdict be unanimous and typed" SHOULD read "to relax the requirement that a verdict satisfy the effective decision rule and be typed". The pending wait-premise and launch-profile proposals touch unrelated sections.

Implementation children already filed on the plan anchor: overseer-3h4s5w.2 (resolver and CLI), .3 (decision rule in the evaluator and actuator), .4 (conformance gate), .5 (local/foreign floor split). The conformance gate — which makes full_autonomy refuse any sibling autonomy lever below its maximum — is an enforcement mechanism in this repository's toolchain and is deliberately not specified here; it is a contributor-facing gate, not a behaviour a governed consumer inherits.

### Proposed Changes

In scenarios.md, amend the existing scenario "## Scenario: Unavailable or disagreeing consensus evidence escalates and mutates nothing" so its When line reads: "When the panel's verdicts fail the effective decision rule, a reviewer verdict that rule treats as a veto is present, the evidence is unavailable, or the journal append fails". Its Given and Then lines are unchanged.

Add, immediately after that scenario, the following seven scenarios. Every Then clause below is stated as a MUST of the foreman.

## Scenario: A strict majority authorizes an action under full autonomy

Given a repository whose livespec configuration declares full_autonomy true

And a human valve whose category is one this specification owns

And a cross-vendor review panel drawn from at least two distinct vendors

When two of three reviewers return the same typed action and the third returns a different typed action with no security dissent

Then the effective decision rule is majority

And the foreman appends an audit journal entry naming the governing settings, the decision rule, the panel identities, and the verdict, recorded as a majority outcome and not as unanimous

And it performs the majority action only after that append has succeeded

## Scenario: The same split escalates under the unanimous decision rule

Given a repository whose foreman valve disposition is set to consensus and whose livespec configuration does not declare full_autonomy true

And a cross-vendor review panel drawn from at least two distinct vendors

When two of three reviewers return the same typed action and the third returns a different typed action

Then the effective decision rule is unanimous

And the foreman escalates the decision to the human with coordinates

And it invokes no action id and mutates nothing

## Scenario: An insufficient-information verdict abstains rather than vetoes under the majority rule

Given a repository whose livespec configuration declares full_autonomy true

When one reviewer returns insufficient-information and the other two return the same typed action

Then the foreman treats the insufficient-information verdict as an abstention

And it journals and performs the action the two agreeing reviewers named

## Scenario: A security dissent escalates under the majority rule and no majority overrides it

Given a repository whose livespec configuration declares full_autonomy true

When one reviewer returns needs-human with a hard-risk marker whose declared risk kind is security and the other two return the same typed action

Then the foreman escalates the decision to the human with coordinates, naming the security dissent

And it invokes no action id and mutates nothing

## Scenario: A floor category owned by another contract stays escalated under full autonomy

Given a repository whose livespec configuration declares full_autonomy true

And a decision whose floor category this specification binds to by reference rather than owns

When a cross-vendor panel returns a unanimous and fully confident verdict to act

Then the foreman escalates the decision to the human with coordinates

And it invokes no action id and mutates nothing

## Scenario: An absent or non-true full_autonomy key changes nothing

Given a livespec configuration in which the full_autonomy key is absent, empty, of the wrong type, or any value other than true

When the effective disposition and decision rule are resolved

Then full_autonomy resolves to false

And the effective disposition is exactly what the valve-disposition key alone resolves to

And the effective decision rule is unanimous

## Scenario: A contradictory configuration is surfaced while full autonomy governs

Given a livespec configuration that declares full_autonomy true and an explicit report-only valve disposition

When the effective disposition and decision rule are resolved

Then the effective disposition is consensus and the effective decision rule is majority

And the resolver reports a conflict to the operator rather than resolving the contradiction silently
