---
topic: caam-credential-maintenance-honest-guarantee
author: caam-anthropic-loop-planner
created_at: 2026-08-29T02:00:00Z
---

## Proposal: State the honest credential-maintenance guarantee — refresh the instant a credential is known expired, not "before it lapses"

### Target specification files

- SPECIFICATION/spec.md

### Summary

The clause "The set of verifiable accounts MUST be actively maintained, not merely reported on"
requires that "the operation MUST refresh an idle account's stored credential **before it lapses**".
Measured on ledger item `overseer-54k2za.47`, that pre-lapse guarantee is UNSATISFIABLE with the
delegated refresh mechanism the very same clause mandates: the agent will not renew a credential that
has not yet expired. This proposal replaces the unattainable pre-lapse guarantee with the honest one
the mechanism can deliver — detect an expired or absent credential the instant it is knowable,
decoupled from the cached-figure reporting ceiling, and refresh it promptly to minimise the window in
which the account is unselectable — while preserving every other obligation in the clause unchanged.

### Motivation

Filed against `overseer-54k2za.47` (plan `caam-anthropic-loop`, ledger anchor `overseer-54k2za`),
whose comments carry the full measurement. Across nine refresh attempts on three profiles, the
sandboxed agent refreshed a credential only when it had ALREADY expired — five pre-expiry attempts,
five failures; four post-expiry attempts, four successes — and no choice of the pre-expiry margin
changed this. The shipped code therefore cannot conform to "before it lapses" by any tuning.

`overseer-54k2za.47` landed the reachable half: it decoupled "the stored CREDENTIAL is expired"
(known immediately from the token) from "the cached quota FIGURES are too old to render" (a reporting
concern governed by a staleness ceiling), so revive now fires the instant the credential is known
expired rather than up to an hour later. That cut the measured per-cycle unselectable window from
42-61 minutes toward one scheduled tick. This proposal makes the specification state the guarantee
that code now delivers, so the spec and the implementation agree and a future reader is not sent to
satisfy an impossible MUST.

### The change

Within the clause beginning "**The set of verifiable accounts MUST be actively maintained, not merely
reported on.**", replace the sentence (quoted through its retry-rate-floor tail so that tail
reattaches to the rate clause rather than to a new sentence):

> Reporting the condition is not a remedy — the operation MUST refresh an idle account's stored
> credential before it lapses, and MUST do so on a schedule and with a retry backoff such that a
> persistently unrefreshable account is neither abandoned silently nor retried without limit on the
> *rate* at which attempts are made — a fixed minimum interval between attempts per account satisfies
> this, and no bound on the total number of attempts is required, since an account that becomes
> refreshable again must be picked up.

with:

> Reporting the condition is not a remedy — the operation MUST detect an expired or absent stored
> credential the instant it is knowable, independently of any staleness ceiling that governs when the
> cached quota figures may still be rendered, and MUST refresh it promptly and on a schedule so as to
> minimise the window in which the account is unselectable, with a retry backoff such that a
> persistently unrefreshable account is neither abandoned silently nor retried without limit on the
> *rate* at which attempts are made — a fixed minimum interval between attempts per account satisfies
> this, and no bound on the total number of attempts is required, since an account that becomes
> refreshable again must be picked up. A pre-expiry refresh is NOT required and MUST NOT be assumed
> available: where the refresh is delegated to the agent (per the clause below) and the agent will
> renew only a credential that has already expired, refreshing immediately upon expiry and reporting
> the condition satisfies this obligation. What the operation MUST NOT do is defer a refresh it could
> already perform — a credential known expired at poll time MUST NOT wait on an unrelated
> reporting-staleness timer before the refresh is attempted.

The retry-rate-floor tail ("— a fixed minimum interval ... must be picked up.") is preserved verbatim
and kept attached to the rate clause it elaborates; the two new sentences are appended AFTER it. Every
remaining sentence of the clause is unchanged, including: reporting an unrefreshable account,
distinguishing an unrecoverable credential from a transient or policy condition, carrying the
underlying diagnostic, not reporting a still-valid credential as a failure, and establishing
refreshability by attempting it rather than trusting a recorded future expiry.

### Why this does not weaken the contract

The scheduled-refresh and retry-rate-floor obligations remain. The "MUST establish refreshability by
attempting it" obligation remains, and is strengthened in spirit: the attempt is now triggered by the
credential fact the instant it is known rather than deferred behind a reporting timer. The
"Refreshing MUST delegate to the agent, and MUST NOT touch the live credential" clause is untouched.
What is removed is only the guarantee that the refresh happens BEFORE expiry — a guarantee the
delegated mechanism was never able to honor.
