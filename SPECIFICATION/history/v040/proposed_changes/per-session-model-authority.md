---
topic: per-session-model-authority
author: claude-opus-4-8
created_at: 2026-08-30T03:07:26Z
---

## Proposal: A per-session Fable pin counts as an operator pin for scoped-model selection

### Target specification files

- SPECIFICATION/spec.md

### Summary

Widen the scoped-model selection clauses in the Account rotation and quota supervision section so that 'an operator pin naming the scoped model' includes a per-session pin (any session_models entry naming the scoped model), not only the global foreman pin. Priority is unchanged and restated so it is not lost.

### Motivation

Maintainer ruling, 2026-08-30, verbatim: 'if I tell something to use fable, leave it on fable, unless it is going to exhaust a protected account.' The scoped-model clause currently phrases its selection gate as 'an operator pin' and the shipped gate (caam_foreman_override.scoped_model_pinned) reads the GLOBAL foreman pin only; its own docstring records that per-session exceptions are 'a separate, currently unspecified surface' left to a follow-up proposal, and gt6ne5's unblock comment says widening it 'would change what the spec says rather than conform to it.' The maintainer pins per-session (session_models, e.g. livespec-overseer-foreman=fable), so the current global-only gate never fires for the case actually in use. This proposal fills that gap by ruling that a per-session scoped pin is an operator pin for selection, while preserving the existing precedence and anti-oscillation guarantees.

### Proposed Changes

Amend the scoped-model selection clauses within the '## Account rotation and quota supervision' section of spec.md. The behavioral rule is: wherever these clauses key selection on 'an operator pin [that] names/depends on the scoped model' (the Rotation-triggers clause, the Eligibility clause, the scoped-model clause, and the Ranking clause), the pin that arms selection MUST be understood to include a PER-SESSION operator pin -- any per-session enforced-model entry equal to the scoped model -- and not only the global foreman pin. Concretely:

1. In the scoped-model clause (the paragraph beginning 'A scoped-model allowance MUST NOT be treated as spendable capacity, and MUST influence selection only while an operator pin depends on it.'), add one definitional sentence establishing the meaning of the phrase for the whole section, in this shape: 'Throughout these selection clauses, an operator pin names the scoped model when EITHER the global foreman pin is set to the scoped model OR any per-session operator pin is set to the scoped model; a per-session pin naming the scoped model arms selection exactly as the global pin does.'

2. Restate the unchanged precedence so widening the arming condition cannot be read as changing it. The scoped-model clause's exception already bounds selection to exactly three effects (trigger, eligibility waiver, ranking) and MUST continue to; add, at the point where the precedence is stated, that: (a) a per-account protection floor still outranks the scoped-model pin -- the pin waives the relative-headroom margin ONLY, never a protection floor, so a per-session Fable pin MUST NOT select or retain a protected account past its floor; and (b) the scoped-model pin, whether global or per-session, outranks every other ordinary rotation rule.

3. Preserve anti-oscillation verbatim in effect: where the ACTIVE account CAN already serve the pinned model, the relative-headroom margin MUST apply unwaived, for a per-session pin exactly as for the global pin (the existing Eligibility clause's 'Where the active account CAN already serve the pinned model, the margin MUST apply unwaived' already states this; make explicit that it holds regardless of whether the arming pin is global or per-session).

No other clause changes. The global-pin path is unchanged; a per-session pin is added as an additional way the same gate is armed. The words 'general model', the trigger threshold, the reserve, and the protection-floor clauses are untouched.

## Proposal: Model enforcement leaves an operator-set non-default model alone outside the Fable-exhausted exception

### Target specification files

- SPECIFICATION/spec.md

### Summary

Add a per-session operator-choice rule to the Model enforcement clause: a session observed on a non-default model that enforcement did not itself assign MUST be left alone by model enforcement, with the single exception that the scoped (Fable) allowance being unavailable on the active account permits moving sessions off a model that would block them. An unknown (None) observed model is never evidence of an operator choice.

### Motivation

Maintainer ruling, 2026-08-30, verbatim: 'UNLESS WE ARE OUT OF FABLE QUOTA, if I have a session set to a NON-DEFAULT/NON-AUTO-ASSIGNED model, LEAVE IT ALONE.' Today enforcement computes one wanted model for the foreman population and drives the /model picker into any pane whose observed model differs (or reads unknown), so an operator who deliberately sets a session to a non-default model (e.g. flips the foreman to Opus 5 1M for a long-context task) is yanked back on the next enforcement pass; this was observed live as dozens of forced 'Set model to Fable 5' entries interleaved with the operator's own picks. The code already names this gap (caam_foreman_override.scoped_model_pinned docstring: per-session exceptions are 'a separate, currently unspecified surface' left 'to a follow-up proposal'). This clause fills it.

### Proposed Changes

Amend the '## Account rotation and quota supervision' section of spec.md so the Model enforcement contract respects an operator-set per-session model. Add a MUST clause (adjacent to the existing 'Model enforcement.' clause and the 'An operator override MUST be able to pin the enforced model' clause, which govern the derived-model sweep and the durable global pin respectively). The behavioral rule is:

1. Model enforcement MUST NOT re-drive a session that is observed on a non-default model which enforcement did not itself assign. Enforcement MUST distinguish an operator-set model from an enforcement-set model from its own durable state: enforcement already records which session it set, to what model, and when, so a session whose observed model differs BOTH from the model enforcement currently wants AND from the last model enforcement itself set for that session is operator-set, and MUST be left alone.

2. The single exception: when the scoped (Fable) allowance is unavailable on the active account -- exactly the condition under which the section already resets every other agent session to the general model and warns on a pinned scoped model -- enforcement MAY move an operator-set session off a model that would block it, because leaving it there would strand the session rather than honor a still-serviceable choice. Outside that Fable-unavailable exception, an operator-set non-default model MUST be honored.

3. An unknown observed model (the model could not be read for a session) is NEVER evidence of an operator choice and MUST NOT be treated as one; the operator-set determination requires a KNOWN observed model that differs from both the wanted model and enforcement's own last-set record for that session.

The existing global operator-pin clause and the scoped-model selection clauses are unchanged except that this clause cross-references them; the derived-model sweep for sessions enforcement DID assign, and for sessions never touched by the operator, is unchanged.
