---
topic: caam-decouple-foreman-grooming-model-enforcement
author: caam-anthropic-loop-plan
created_at: 2026-09-06T17:09:31Z
spec_commitments:
  impl_followups:
    - id_hint: caam-decouple-foreman-grooming-impl
      description: |
        Remove the caam code implementing the retired foreman coupling: delete apply_foreman_model_override/ForemanModelChoice and the --foreman-model flag plumbing (caam_foreman_override.py, caam_anthropic_loop.py, caam_anthropic_flags.py, caam_anthropic_status.py, caam_enforcement_options.py), drop the foreman/grooming-suffix branch and the global-foreman arm of scoped_model_pinned, relocate SCOPED_MODEL/WANTED_MODELS/OBSERVED_MODELS_KEY/scoped_model_pinned to a neutral caam_scoped_model module, keep --session-model and the observed-running + per-session arming and the servability reset, and update the caam tests and prose. Landed in the same supervised PR as this revision under plan overseer-54k2za.53.
---

## Proposal: Decouple caam model enforcement from the foreman and grooming seats

### Target specification files

- SPECIFICATION/spec.md

### Summary

In '## Account rotation and quota supervision', remove the foreman/grooming-seat coupling from model enforcement so the caam operation no longer derives any session's enforced model from its name and no longer offers a global foreman model pin, while keeping every rule that is not foreman/grooming-specific. The foreman and grooming operator seats are being retired fleet-wide (sibling plan overseer-5ugiuj); caam's coupling to them is vestigial and is removed here, maintainer-directed on plan overseer-54k2za (2026-09-06).

### Motivation

Maintainer instruction on plan overseer-54k2za (2026-09-06): deprecate the foreman and grooming logic from the caam-anthropic-loop skill without deleting the standalone foreman/grooming skills. The sibling plan overseer-5ugiuj explicitly carved caam's foreman coupling out of its cut (consumer=caam/bucket-1), leaving exactly this gap.

### Proposed Changes

Edit ONLY the section '## Account rotation and quota supervision' in SPECIFICATION/spec.md. Make these changes; touch no other section and do NOT alter the standalone FOREMAN operator surface specified elsewhere.

REMOVE entirely:
1. The paragraph beginning '**Model enforcement.** Sessions whose name carries the foreman suffix MUST be pointed at the scoped model ...' — the foreman-suffix DERIVED-model rule. Its still-relevant, name-independent content (reset to the general model when the scoped model is unservable, and the advisory/best-effort enforcement mechanics) is preserved by the rewritten per-session paragraph below, so the foreman-suffix framing is dropped without losing the servability reset.
2. The paragraph beginning '**An operator override MUST be able to pin the enforced model, and it MUST persist.** ...' — the global --foreman-model operator pin (id_hint caam-foreman-model-override). The whole paragraph goes: there is no longer any name-derived precedence for it to override.

AMEND:
3. In the paragraph beginning 'An operator pin names the scoped model, for every selection clause in this section, when EITHER the global foreman pin is set to the scoped model, OR any per-session operator pin ... OR any tracked session is currently observed running the scoped model ...', DELETE the arm 'the global foreman pin is set to the scoped model, OR' so the definition reads: an operator pin names the scoped model when EITHER any per-session operator pin (a per-session enforced-model entry) is set to the scoped model, OR any tracked session is currently observed running the scoped model. Keep the rest of that paragraph (the observed-session arming, the per-session-pin precedence, the protection-floor and anti-oscillation guarantees) verbatim.

KEEP and lightly REWORD:
4. The paragraph beginning '**Model enforcement MUST respect an operator-set per-session model.** ...' STAYS. Since the foreman-derived-model rule above is gone, rewrite its opening so it no longer refers to 'the derived-model rule above': state that the operation MUST NOT derive any session's enforced model from the session's name, and MUST enforce only an operator-set per-session model; enforcement records which session it set, to which model, and when; a session observed on a non-default model that enforcement did not itself set is operator-set and MUST be left alone. Fold in the name-independent servability reset removed with item 1: when NO selectable account in the fleet (not excluded by a per-account protection floor, the zero-weekly disqualifier, the weekly-reserve rule, or the live-verification rule) can serve the model a session is on, enforcement MUST move that session to the general model rather than strand it; a model that ANY selectable account can serve MUST be left alone even while the ACTIVE account's scoped allowance is unavailable (rotation, not a model change, is the remedy there). Keep the existing 'observed model that cannot be read is never evidence of an operator choice' sentence. Remove any phrasing that pins foreman-suffix sessions or references a global foreman pin.
5. Everything else in the section — Scope, Observation, Never refresh, Identity, Rotation triggers, Eligibility, the weekly reserve, protected accounts, the entire scoped-model selection clause (trigger/eligibility/ranking/hold), Ranking, live-verification, set-maintenance, delegated refresh, Switching, 'Operation state MUST be persisted after enforcement', the operator-facing stale-figure report, and Session identity — STAYS VERBATIM. In particular the scoped-model rotation trigger, its eligibility waiver, ranking, and the scoped-unsatisfiability hold are unchanged; they now arm only via a per-session operator pin or an observed-running session (item 3), which is exactly what the overseer-dyt6 Fable-drain fix relies on, so that behavior MUST NOT regress.
