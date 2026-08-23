---
topic: caam-clause-refinements
author: caam-anthropic-loop-planner
created_at: 2026-08-23T09:45:00Z
---

## Proposal: Three wording refinements to the account-rotation clauses

### Target specification files

- SPECIFICATION/spec.md — section "Account rotation and quota supervision"

### Summary

Three wording repairs raised as NON-BLOCKING observations by the independent
v028 ratification reviewer. **Every one is wording only.** No behaviour is added,
removed, or altered by any of them, and each is written so a reviewer can confirm
that against the program rather than having to take this proposal's word for it.

### Why a separate cycle rather than an edit

The v028 ratification evidence digest binds that review to the exact bytes
reviewed. Editing the content before ratifying would have ratified something the
reviewer never saw, which is precisely what the digest exists to prevent.
Refining ratified text through a fresh proposed change is the sanctioned path and
keeps the binding honest.

### Refinement 1 — scope "Never refresh" to what is actually prohibited

**The tension.** The clause states the operation MUST NOT perform an OAuth
refresh *under any circumstance*. A later clause mandates *causing* a refresh, by
exercising a stored credential through the agent itself. The keep-warm paragraph
bridges this explicitly and the program has exactly that structure, so the pair
is reconcilable in context — but read literally the two clauses contradict, and a
future implementer could reasonably conclude that credential maintenance is
forbidden.

**The repair.** Scope the prohibition to the act actually being forbidden:
calling the token endpoint directly. Replace

> MUST NOT perform an OAuth refresh under any circumstance

with

> MUST NOT itself invoke the OAuth token endpoint under any circumstance

The reason given in the clause is unchanged and still applies: rotating a refresh
token outside the agent's own control can revoke the whole token family. What
changes is that the prohibition now names the *mechanism*, so delegating a
refresh to the agent — which is mandated elsewhere and is what the program does —
is no longer caught by it.

### Refinement 2 — "spent" excludes the absent case, which behaves identically

**The tension.** The Model enforcement clause reads "when the allowance is spent,
every other agent session MUST also be reset to the general model". In the
program the predicate is that the scoped allowance is present AND below its
limit, so an active account with **no scoped allowance at all** also triggers the
global reset. Strictly read, "spent" excludes the absent case — while the
Observation clause separately establishes absence as a normal condition.

**The repair.** Two words. Replace "when the allowance is spent" with

> when the allowance is spent or absent

**This MUST NOT be read as widening.** The absent case already behaves this way
in the program, and carrier L5 already pins that consequence. The clause is being
made to describe existing behaviour, not to introduce it. A reviewer can confirm
this by checking that the program's predicate is unchanged by this proposal.

### Refinement 3 — say which reading of "without limit" is meant

**The tension.** The keep-warm clause requires a retry backoff such that a
persistently unrefreshable account is "neither abandoned silently nor retried
without limit". The program's mechanism is a fixed per-account minimum interval,
retried indefinitely, with each failure logged. That satisfies the **rate**
reading of "not retried without limit" and not the **count** reading. The program
and carrier X12 both mean the rate reading.

**The repair.** Say so. Replace "nor retried without limit" with

> nor retried without limit on the *rate* at which attempts are made — a fixed
> minimum interval between attempts per account satisfies this, and no bound on
> the total number of attempts is required, since an account that becomes
> refreshable again must be picked up

The added clause states why the count reading is not intended: a bound on total
attempts would permanently abandon an account whose credential later recovers,
which is the failure the surrounding paragraph exists to prevent.

### What this proposal does not do

No behaviour is added, removed, or altered. No new obligation is created. No
carrier changes. If any of the three reads as a behaviour change to a reviewer,
that reading is a defect in this proposal and the refinement should be rejected
rather than reinterpreted.

### A fourth observation, recorded but NOT proposed here

The reviewer also noted that the vps-info source skill's own prose lags its
program, still quoting a retired keep-warm failure string. That is a vps-info
concern, not this repository's, and is recorded so that nobody later reads it as
contradicting the ratified spec.

### Implementation commitments

None. This proposal is wording only; no implementation follows from it.
