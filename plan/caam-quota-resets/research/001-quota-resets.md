## The maintainer's statement of what done means

Third new work item - both anthropic and codex have the concept of "resets".  Some weekly, some for 5 hour.  This skill should attempt to detect those, display them in a new column(s), and use them if the weekly/hourly quota corresponding to the reset is 1) almost completely exhausted and has a reset available or 2) expiring soon, and the reset would otherwise be lost.  Appropriate additional switching rules should be added to use the resets wisely, in accordance with existing rules and principles.

## Definition of Done assertions derived from that statement

- The account table shows each account's available weekly and five-hour resets in provider-agnostic terms.
- A pass applies an available reset when the window it resets is nearly exhausted.
- A pass applies an available reset that would otherwise expire unused.
- Applying a reset keeps the existing precedence of the protected-account, weekly-reserve, scoped-model and spend-cap rules.

# caam-quota-resets

Both Anthropic and Codex offer quota resets on an account -- some for a weekly allowance, some for a five-hour allowance. The loop neither sees nor uses them.

## First step

Research, per provider, how an account's available resets are discovered (endpoint, fields, weekly vs five-hour scope, any expiry of the reset itself) and how one is applied, and record it here before any design. Do not infer the mechanism; measure it.

## Items this plan adopts

- `overseer-33kyxp` (feature) -- detect, display and spend weekly and five-hour resets. The new switching rules change the ratified account-rotation contract, so split the spec half into its own item routed through `/livespec:propose-change` and keep the code half dispatch-safe.

Related live plans: `caam-expiring-quota-drain` (spending weekly quota that would otherwise lapse -- the same 'otherwise lost' principle) and `caam-mixed-plan-capacity`.
