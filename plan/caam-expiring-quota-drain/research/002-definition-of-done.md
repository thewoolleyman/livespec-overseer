## The maintainer's statement of what done means

The loop spends weekly quota that is about to expire on its own, without me switching accounts by hand, and the spec says it is allowed to.

## Definition of Done assertions derived from that statement

- A scheduled caam-anthropic-loop pass on a healthy active account rotates, with no operator action, to a live-verified eligible account whose weekly window resets sooner than the active account's and within the configured horizon.
- The SWITCHED line printed for an expiring-quota rotation names the expiring weekly quota, its remaining percentage and its time to reset.
- A scheduled caam-anthropic-loop pass holds on a healthy active account when no eligible account's weekly window resets sooner than the active account's.
- A candidate account whose five-hour window resets within the configured minutes is judged eligible on its projected post-reset five-hour balance rather than its snapshot reading.
- The account-rotation contract in SPECIFICATION/contracts.md names the expiring-quota drain as a rotation trigger, states its no-oscillation property, and states its precedence against the spend-cap, protected-account, scoped-model and weekly-reserve rules.

Recorded 2026-10-13 on attended resume. The epic was filed by hand on 2026-10-12 rather than through
`create_thread`, so it carried no Definition of Done and the resume reported
`plan-definition-of-done: missing`. The maintainer chose the statement above; the assertions were
derived from it and from `001-root-cause-and-decision.md`, and written onto epic `overseer-qgdbsd`.
Assertions 1-4 are carried by the code item `overseer-pk5itu`; assertion 5 by the spec item
`overseer-4oavgh`. Every assertion is host-captured against the released build.
