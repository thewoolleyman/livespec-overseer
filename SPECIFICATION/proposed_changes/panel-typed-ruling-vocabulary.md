---
topic: panel-typed-ruling-vocabulary
author: claude-opus-5
created_at: 2026-08-20T10:27:00Z
---

## Proposal: A unanimous panel may authorize a typed ruling, not only an action id

### Target specification files

- SPECIFICATION/spec.md

### Summary

The consensus-decision policy authorizes a unanimous cross-vendor panel to
select "an action drawn from a closed, enumerated vocabulary". The only closed
vocabulary the tree has is the foreman's own actuator whitelist, so a unanimous
panel can authorize nothing the foreman could not already do by itself. The
decisions that actually stall sessions are not action ids at all: answering a
specific picker option, setting a priority, adopting a named basis for a
disputed reading, re-parenting a plan child. This proposal widens the
authorizable vocabulary to admit a second member kind — a TYPED RULING, whose
payload the receiving session executes — while leaving every floor, the
cross-vendor requirement, the unanimity requirement and the journal obligation
exactly as ratified.

### Motivation

Measured 2026-08-20 in the maintainer investigation of the stalled
livespec-dev-tooling fleet, recorded on ledger anchor `overseer-vx4ky3` and
carried by work-item `overseer-vx4ky3.3`.

The panel exists to convert a decision the foreman may not take alone into one
it may take on unanimous cross-vendor evidence. As ratified, it cannot do that.
Its output vocabulary equals the actuator whitelist with the human-valve id
excluded, which means every member of it is an act the foreman was already
authorized to perform under its ordinary disposition. Convening a panel
therefore widens authority by exactly nothing, and a session parked on a
decision the panel is competent to settle stays parked.

One measured instance: a picker whose option was the plan's own
ledger-recorded next action held a session for sixteen hours. A unanimous panel
could not answer it, because "answer option N" is not an action id and no
enumerated member expresses it.

The narrow reading is not a defect in the implementation — the implementation
is faithful to the sentence. The sentence is what is too narrow, so the remedy
is an amendment rather than a code change, and the code must not arm ahead of
ratification.

This proposal deliberately does NOT relax any floor. The two floor categories —
a truly unresolvable decision, and a decision human-gated BY DESIGN — keep
their present force and their present by-reference definition, and a typed
ruling that would dispose of one MUST still escalate. The human-valve id
remains non-authorizable. Widening WHAT a unanimous panel may say is a
different question from widening WHICH decisions it may reach, and only the
first is proposed here.

### Proposed Changes

In `spec.md`, in the paragraph beginning "Under the consensus disposition",
replace the single sentence

> Under the consensus disposition the foreman MAY act on a human valve ONLY
> when a cross-vendor review panel returns a unanimous typed verdict, and only
> for an action drawn from a closed, enumerated vocabulary. A free-form or
> unenumerated action MUST escalate.

with the following, which keeps that sentence's force and adds the second
member kind:

> Under the consensus disposition the foreman MAY act on a human valve ONLY
> when a cross-vendor review panel returns a unanimous typed verdict, and only
> for a member of a closed, enumerated vocabulary. A free-form or unenumerated
> member MUST escalate.
>
> That vocabulary MUST admit two member kinds and no others. The first is an
> ACTION, an act the foreman itself performs, identified by the governing
> orchestrator contract's action id. The second is a TYPED RULING: a decision
> the panel settles and a supervised session then executes, carried as a
> structured payload whose kind is itself drawn from a closed enumeration.
>
> A typed ruling MUST carry, in structured fields rather than in prose, the
> ruling kind and every value the executing session needs to act without
> re-deciding anything. A ruling the session must interpret before it can act
> is a free-form member and MUST escalate.
>
> Admitting typed rulings MUST NOT widen which DECISIONS the panel may reach.
> Every floor stated below applies unchanged to a typed ruling, and a ruling
> that would dispose of a truly unresolvable decision, or of one human-gated BY
> DESIGN, MUST escalate however unanimous and confident the panel is. The
> foreman MUST NOT be authorized to act on a human valve id through a typed
> ruling that a direct action id could not authorize.
>
> A typed ruling MUST be journaled before it is relayed, on the same terms as
> any other authorized act: the governing setting, the panel identities, the
> verdict, and the ruling payload as executed. A failed journal append MUST
> block the relay.
