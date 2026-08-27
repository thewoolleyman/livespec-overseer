---
topic: protected-accounts-reserve
author: caam-anthropic-loop-planner
created_at: 2026-08-23T08:02:00Z
---

## Proposal: A protected account MUST keep a per-account weekly reserve

### Target specification files

- SPECIFICATION/spec.md — section "Account rotation and quota supervision"

### Summary

Add a per-account protection reserve to the rotation rules: an operator MAY mark
individual accounts as protected, each with its own configurable weekly floor,
and the operation MUST NOT spend a protected account below its floor while any
unprotected account remains usable. Adds three normative rules — a floor applied
to eligibility, a last-resort ordering, and a rotation trigger when the active
account reaches its own floor — and one precedence rule stating that the existing
weekly-reserve release MUST NOT release a protection floor.

### Motivation

**This is a capability the specification currently forbids by omission.** The
ratified rules treat every account as interchangeable capacity: eligibility is a
relative-headroom test, ranking is by soonest reset, and the only floor is a
single fleet-wide weekly reserve that is released once every account is beneath
it. Nothing lets an operator say that one account must remain usable.

**That assumption does not hold for the accounts in question.** The maintainer's
main account is also the one used interactively from a phone and a personal
computer, and a second account serves fabro worker nodes. Rotation spends both to
exhaustion exactly as designed, and the interactive use they exist for fails at
the moment the fleet is busiest. The existing fleet-wide reserve cannot express
this: it applies to every account equally, and it is deliberately released when
all are below it, which is precisely when a protected account most needs its
floor.

**The gap is narrow and the remedy is small,** which is why this is an amendment
rather than a new section: the operation already computes remaining weekly
headroom per account, already filters candidates against a floor, and already
ranks what survives the filter. Protection reuses all three.

### Proposed changes

Add after the paragraph beginning "**The weekly reserve MUST NOT be
forfeited.**":

> **A protected account MUST retain its own weekly floor.** An operator MAY mark
> any account as protected and MUST be able to give each protected account its
> own floor, expressed as a share of its weekly allowance; the floor MUST have a
> configurable default so that marking an account protected is sufficient on its
> own. A protected account's usable headroom MUST be measured net of its floor,
> so that the account is disqualified as a candidate once spending it further
> would breach that floor. A protected account MUST NOT be selected while any
> unprotected account is eligible: protection is an ordering over which accounts
> are spent, not merely a limit on how far. Where the active account is itself
> protected and has reached its floor, that MUST trigger rotation on its own,
> since selection rules alone cannot stop an account being spent while it is the
> one in use.
>
> **A protection floor MUST NOT be released by the weekly reserve's release.**
> The two floors answer different questions: the weekly reserve protects the
> fleet's ability to keep working and correctly stops protecting anything once
> every account is beneath it, whereas a protection floor is a commitment about
> one account that the operator relies on elsewhere. Releasing the second because
> the first ran out would breach that commitment at exactly the moment it was
> made for. Where every remaining candidate is protected and at or below its
> floor, the operation MUST hold and MUST report which accounts are protected and
> at what floor, rather than breaching a floor silently or stalling without a
> reason.

Amend the paragraph beginning "**The weekly reserve MUST NOT be forfeited.**" by
appending one sentence:

> The release governs the fleet-wide reserve only and MUST NOT be read as
> releasing any per-account protection floor.

### Notes on scope

This proposal does not change the eligibility margin, the ranking rule, the
live-verified requirement, or the scoped-model non-influence rule. It is
deliberately silent on how protection is configured and persisted, which is an
implementation concern; the implementation commitments below record the shape
chosen.

### Implementation commitments

- `overseer-54k2za.33` — the decision core: the floor applied to usable headroom,
  the last-resort ordering, the leave-at-the-floor trigger, and the precedence
  rule that the reserve release does not release a protection floor. Pure, with
  table-driven tests over every branch, including a control proving that with no
  account protected every decision is byte-identical to today's.
- `overseer-54k2za.35` — configuration: a repeatable flag naming an account and a
  percentage, a bare name taking the configurable default, persistence in the
  state file beside the existing configuration keys, an invalid value ignored
  with a message and never clearing an existing entry, and reporting on the
  summary line without altering any reproduced table format specifier.
