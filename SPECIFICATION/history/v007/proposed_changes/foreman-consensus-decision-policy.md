---
topic: foreman-consensus-decision-policy
author: claude-opus-5
created_at: 2026-08-04T11:30:51Z
---

## Proposal: Ratify the foreman consensus-decision policy and its inviolable floors

### Target specification files

- SPECIFICATION/spec.md
- SPECIFICATION/constraints.md
- SPECIFICATION/scenarios.md

### Summary

Supplies the consensus-decision policy that spec.md's own report-only clause defers to, so that clause retires by its own terms rather than by reversal. The foreman's valve behavior becomes configuration-selected with a safe default of report-only, bounded by hard floors that no configuration may cross: a truly-unresolvable decision, and any decision human-gated BY DESIGN, MUST stay escalated even under unanimous agreement. Unavailable consensus evidence, panel disagreement, and journal-append failure MUST all escalate, and no auto-disposition may be silent.

### Motivation

spec.md currently reads 'Until a consensus-decision policy is ratified in this specification, every action classified by the governing orchestrator contract as a human valve is report-only for the foreman.' That clause is self-retiring by construction: it defers to a policy that does not yet exist, and 'consensus' appears nowhere else in this tree. Seed requirement 5 of plan/foreman asks for a Fable/Opus/GPT-sol panel whose unanimous verdict can unblock without human attention, and the maintainer ruled on 2026-08-04T07:12Z to build it. The cross-vendor panel now exists and is released in this repo (overseer/foreman_consensus*.py and bin/foreman-consensus), executed from the released cache build under a scrubbed environment. What is missing is the ratified policy that authorizes it to act. This proposal supplies exactly that, and deliberately mirrors the pattern livespec ratified as v193 (a mode key with a safe default, plus a predicate owning hard floors) rather than inventing a second shape. It reverses nothing: the governing orchestrator contract's rule that 'no policy setting MAY auto-dispose a truly-unresolvable decision' is preserved verbatim as a floor here. SCOPE: this tree governs the foreman's own valve path only. The core drift-acceptance lever (livespec's drift-doctrine sentence and its spec_governance.drift_acceptance_mode key) belongs to the livespec repository's plan/spec-side-autonomy thread under epic livespec-jvdvx4 and is cross-linked, not carried here.

### Proposed Changes

Replace the self-retiring paragraph in `spec.md` with the ratified policy.

The foreman's disposition of an action the governing orchestrator contract classifies as a human valve MUST be selected by configuration. The safe default MUST be report-only, and an absent or unreadable setting MUST resolve to report-only, so a tree that declares nothing behaves exactly as it does today.

Under report-only the foreman MUST NOT invoke any such action id, MUST NOT answer a blocked question on a session's behalf, and MUST report the decision to the human with coordinates.

Under the consensus disposition the foreman MAY act on a human valve ONLY when a cross-vendor review panel returns a unanimous typed verdict, and only for an action drawn from a closed, enumerated vocabulary. A free-form or unenumerated action MUST escalate.

HARD FLOORS. No configuration value MAY authorize the foreman to dispose of a truly-unresolvable decision, nor of any decision that is human-gated BY DESIGN — drift acceptance, a spec-change slice, a regroom or backlog bounce, or a human-only acceptance. Each of these MUST stay escalated even when the panel is unanimous and fully confident. A floor MUST NOT be relaxable by any configuration key; relaxing one requires a ratified amendment to this specification.

TERMS. The two floor categories named above — a truly-unresolvable decision, and a decision human-gated BY DESIGN — are DEFINED BY the governing orchestrator contract, not by this tree, and this specification binds to those definitions BY REFERENCE. It MUST NOT restate them, because a duplicated definition is a definition that can drift; a reader resolving whether a decision sits below a floor MUST consult that contract's terminology. Should this tree ever name a floor category the governing contract does not define, that category MUST be defined here before it may bound the foreman's authority.

ESCALATION CONDITIONS. The foreman MUST escalate, and MUST NOT act, when consensus evidence is unavailable or insufficient, when the panel disagrees, when any reviewer returns an insufficient-information verdict, or when the audit journal append fails. Escalation MUST be the outcome of every condition this policy does not explicitly authorize.

PANEL PROPERTIES. The panel MUST draw its reviewers from at least two distinct vendors, because a panel whose members share a vendor is not the independent evidence this policy relies on. A dissent that is not vendor-aligned with the majority MUST NOT be overridable by the remaining reviewers. An outcome reached by overriding a minority report MUST NOT be recorded as unanimous.

AUDIT. Every act the consensus disposition authorizes MUST be journaled before the act, naming the governing setting, the panel identities, and the verdict. No auto-disposition MAY be silent. A failed journal append MUST block the act.

In `constraints.md`, state the floors and the safe default as safety rails: the foreman MUST fail closed on an unknown or malformed disposition value, and MUST NOT widen its own authority on the basis of any evidence it produced itself.

In `scenarios.md`, add Given/When/Then scenarios covering: (a) a unanimous typed verdict under the consensus disposition acts and is journaled first; (b) a decision human-gated BY DESIGN stays escalated under the consensus disposition even with a unanimous panel; (c) unavailable or disagreeing consensus evidence escalates and mutates nothing; (d) a tree declaring no disposition acts on nothing.

## Proposal: Declare the foreman valve-disposition setting on the contract surface

### Target specification files

- SPECIFICATION/contracts.md
- SPECIFICATION/scenarios.md

### Summary

Declares the wire surface for the disposition selected by the policy proposal: the setting's location, its enumerated values, its safe default, and the requirement that an unknown value fails closed rather than being coerced. Keeps the observable contract in contracts.md while the intent and floors stay in spec.md, per this tree's functional/non-functional split.

### Motivation

The policy proposal states WHAT the foreman may do and what it may never do; a reader implementing or configuring it also needs to know WHERE the disposition is declared and WHICH values are legal. Separating the two lets the revise pass accept the policy and its wire surface independently, and keeps the split this tree already applies: user-observable intent in spec.md, user-observable wire contracts in contracts.md. The shape deliberately mirrors the key livespec ratified as v193, whose values are manual, delegated and consensus with a safe default of manual, so an operator moving between the two trees meets one vocabulary rather than two.

### Proposed Changes

In `contracts.md`, declare the foreman valve-disposition setting.

The setting MUST be declared in the governed repository's livespec configuration, alongside the other settings that tree already carries, and MUST be readable without invoking the foreman.

Its value MUST be one of an enumerated set. `report-only` MUST be the safe default and MUST be the effective value when the key is absent, empty, or of the wrong type. `consensus` MUST select the disposition ratified in `spec.md`.

An unrecognized value MUST NOT be coerced to the nearest match and MUST NOT silently enable any act; it MUST resolve to the safe default and MUST be surfaced to the operator. Failing closed on an unknown value is required precisely because this setting is the one that widens authority.

The effective value MUST be observable — an operator MUST be able to read what the foreman will actually do without running it.

The setting MUST NOT be settable by the foreman itself. Nothing the foreman writes MAY change its own disposition.

In `scenarios.md`, add Given/When/Then scenarios covering: an absent key resolving to report-only; an unknown value resolving to report-only AND being surfaced rather than accepted silently; and the effective value being readable without invoking the foreman.
