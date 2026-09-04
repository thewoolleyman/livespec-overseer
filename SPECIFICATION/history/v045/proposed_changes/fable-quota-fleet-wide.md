---
topic: fable-quota-fleet-wide
author: claude-fable-5-1
created_at: 2026-09-04T08:31:40Z
---

## Proposal: Fable quota is fleet-wide: arm the scoped-model rotation trigger for any session on Fable, and move a Fable session to the general model only when no eligible above-floor account can serve it

### Target specification files

- SPECIFICATION/spec.md

### Summary

The ratified v040/v043 text keys the Fable->general-model move on the ACTIVE account's scoped allowance and arms Fable-exhaustion rotation only through a pin naming Fable. That is correct for a single account but wrong fleet-wide: an unpinned session on default Fable is switched to the general model the moment the active account's Fable is spent, even while another eligible account still has Fable, because enforcement consults the active account and no pin exists to trigger rotation. This proposal makes 'quota for the scoped model' fleet-wide -- a session on the scoped model is moved only when NO eligible, above-floor account can serve it, and any session observed on the scoped model arms the rotation trigger so account rotation is the remedy -- while restating that the per-account protection floor outranks serving Fable.

### Motivation

Maintainer ruling 2026-09-04, verbatim: 'The model changing should ONLY be used if quota ran out on that model' and 'Fleet wide, but still the protected account rule still takes precedence over using fable. i.e., if fable only exists on -0 (current protected account) but it is at the limit (currently 15% I think), then it would not switch, and other rules would be used (i.e. 5 hour, weekly, etc as normal precedence).' Verified on master: caam_anthropic_status.write_status invokes enforce_models BEFORE decide(), enforcement passes the active account's fable_left as scoped_servable, and decide() arms the scoped-model trigger via scoped_model_pinned() (global foreman pin or session_models pin only). Corrective reopen of plan respect-operator-model-pins (epic overseer-q3cvsv, child overseer-q3cvsv.5; impl follow-up overseer-q3cvsv.6). The protection-floor precedence is already ratified in v040 ('a candidate at or below its protection floor MUST remain disqualified even to serve the pinned model') and is restated, not changed.

### Proposed Changes

Three coordinated edits in SPECIFICATION/spec.md, all within '## Account rotation and quota supervision'. No other sentence changes; the protection-floor carve-out and anti-oscillation text are left verbatim, and the downstream clauses that say 'the pinned model' need no edit because Amendment A widens the definition they already reference.

AMENDMENT A -- widen what arms the scoped-model trigger. In the paragraph beginning 'An operator pin names the scoped model, for every selection clause in this section', REPLACE its first sentence:

OLD: "An operator pin names the scoped model, for every selection clause in this section, when EITHER the global foreman pin is set to the scoped model OR any per-session operator pin -- a per-session enforced-model entry -- is set to the scoped model."

NEW: "An operator pin names the scoped model, for every selection clause in this section, when EITHER the global foreman pin is set to the scoped model, OR any per-session operator pin -- a per-session enforced-model entry -- is set to the scoped model, OR any tracked session is currently observed running the scoped model, whether it arrived there by pin, by an operator's choice, or as the default; a session observed on the scoped model arms the trigger, the eligibility waiver and the ranking exactly as a pin does, so that the active account being unable to serve the scoped model is a rotation trigger for every session that depends on it, not only for a pinned one."

AMENDMENT B1 -- make the blanket reset fleet-wide. In the '**Model enforcement.**' clause, REPLACE:

OLD: "Sessions whose name carries the foreman suffix MUST be pointed at the scoped model while the active account retains that allowance, and at the general model otherwise; when the allowance is spent or absent, every other agent session MUST also be reset to the general model, and otherwise other sessions MUST be left alone."

NEW: "Sessions whose name carries the foreman suffix MUST be pointed at the scoped model while any selectable account in the fleet can serve it -- selectable meaning an account this section's rotation rules could actually choose: not excluded by a per-account protection floor, the zero-weekly disqualifier, the weekly-reserve rule or the live-verification rule -- and at the general model otherwise; only when NO selectable account can serve the scoped model MUST every other agent session also be reset to the general model, and otherwise other sessions MUST be left alone. An account rotation cannot select does not count as able to serve the scoped model for this purpose, however much scoped allowance it holds: where the scoped model is servable only on such accounts it is unservable, the sessions move to the general model rather than wait on an account that can never be chosen, and account selection proceeds under the normal precedence of the short-window threshold, the weekly reserve and the protection floor."

AMENDMENT B2 -- make the per-session servability exception fleet-wide. In the clause beginning '**Model enforcement MUST respect an operator-set per-session model.**', REPLACE:

OLD: "where the active account cannot serve the model an operator set a session to -- because the scoped allowance that model depends on is spent or absent -- enforcement MUST move that session to the general model rather than strand it on a model the account cannot serve. An operator-set model the active account CAN serve MUST be left alone even while the scoped allowance is unavailable, since no servability concern reaches it; the scoped-allowance-exhausted condition that resets the derived and never-operator-set sessions to the general model MUST NOT, on its own, move an operator-set session whose own model remains serviceable."

NEW: "where NO selectable account in the fleet -- one this section's rotation rules could actually choose, i.e. not excluded by a per-account protection floor, the zero-weekly disqualifier, the weekly-reserve rule or the live-verification rule -- can serve the model an operator set a session to, enforcement MUST move that session to the general model rather than strand it on a model nothing selectable can serve. An operator-set model that ANY selectable account can serve MUST be left alone, even while the ACTIVE account's scoped allowance is unavailable, since rotation rather than a model change is the remedy for an active account that cannot serve it; the active account's scoped allowance being exhausted MUST NOT, on its own, move a session whose own model remains serviceable on a selectable account."

Together: B1 governs a session on the scoped model by default, B2 governs an operator-set one, and A guarantees that whenever either is left on the scoped model while the active account cannot serve it, rotation is armed to move the ACCOUNT rather than the session.
