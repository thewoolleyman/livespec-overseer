---
topic: servable-pin-survives-fable-exhaustion
author: claude-opus-4-8-1m
created_at: 2026-08-30T06:49:49Z
---

## Proposal: Bound the per-session model-enforcement exception to servability so a servable operator pin survives Fable exhaustion

### Target specification files

- SPECIFICATION/spec.md

### Summary

The ratified v040 clause 'Model enforcement MUST respect an operator-set per-session model' states its Fable-exhaustion exception ambiguously: it names the exception as 'the scoped-model allowance being unavailable on the ACTIVE account -- the same condition under which every other agent session is reset to the general model -- where enforcement MAY move an operator-set session off a model that would block it.' That parenthetical invites a blanket reading, and the shipped implementation (PR #2045) took it, gating operator-set respect globally on fable_left so a Fable-exhausted pass resets even a servable operator pin (e.g. an Opus pin). This tightens the exception to be bounded to the session's OWN model and keyed on servability: enforcement MUST move an operator-set session only when the active account cannot serve that session's own model, and MUST leave a servable operator-set model alone even while the scoped allowance is unavailable.

### Motivation

Maintainer ruling 2026-08-30 and explicit confirmation of the servability-bounded reading: 'UNLESS WE ARE OUT OF FABLE QUOTA, if I have a session set to a NON-DEFAULT/NON-AUTO-ASSIGNED model, LEAVE IT ALONE' -- resolved so that a deliberately-set model the active account can still serve is left alone through a Fable exhaustion, and only a session whose own model becomes unservable is moved. The v040 clause and PR #2045 were authored concurrently and landed the blanket reading; this is the corrective follow-up filed against plan epic overseer-q3cvsv (child overseer-q3cvsv.3), with the implementation tracked as overseer-q3cvsv.4. Filed after confirming on current master that the target clause still reads the MAY-blanket form and no other pending proposed change touches it.

### Proposed Changes

In SPECIFICATION/spec.md, within the clause beginning '**Model enforcement MUST respect an operator-set per-session model.**' (the '## Account rotation and quota supervision' section), REPLACE exactly the single 'single exception' sentence. The current sentence reads:

"The single exception is the scoped-model allowance being unavailable on the ACTIVE account -- the same condition under which every other agent session is reset to the general model -- where enforcement MAY move an operator-set session off a model that would block it, since leaving it there would strand the session rather than honor a serviceable choice."

Replace it with:

"The single exception is bounded to the session's OWN model and keyed on servability, not on the global scoped-allowance-exhausted condition: where the active account cannot serve the model an operator set a session to -- because the scoped allowance that model depends on is spent or absent -- enforcement MUST move that session to the general model rather than strand it on a model the account cannot serve. An operator-set model the active account CAN serve MUST be left alone even while the scoped allowance is unavailable, since no servability concern reaches it; the scoped-allowance-exhausted condition that resets the derived and never-operator-set sessions to the general model MUST NOT, on its own, move an operator-set session whose own model remains serviceable."

No other sentence in the clause changes. The main rule (operator-set sessions MUST be left alone), the KNOWN-observed-model / last-set-record determination, the unknown-model guard, and the closing 'this clause bounds which sessions enforcement drives...' sentence are unchanged. The separate 'Model enforcement.' blanket-reset sentence for derived and never-operator-set sessions ('when the allowance is spent or absent, every other agent session MUST also be reset to the general model') is left as-is: it continues to govern sessions that are NOT operator-set, while this clause's 'Notwithstanding' opener continues to make the operator-set rule win for operator-set sessions. The scoped-model selection clauses and the durable global operator-pin clause are untouched.
