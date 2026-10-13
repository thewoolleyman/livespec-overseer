# caam-mixed-plan-capacity — scope, the capacity ruling, and the live plan source (2026-10-14)

## The conflict this note resolves

Plan assertion 3 as first derived read "Candidate ranking prefers a large-capacity account over a
small-capacity one when both are otherwise eligible." SPECIFICATION v055, ratified 2026-10-13 in
plan `caam-expiring-quota-drain`, says the opposite in `spec.md` §"Account rotation and quota
supervision", **Ranking**: "Ranking MUST NOT weight a candidate by its plan capacity or rate-limit
tier", with scenario "Ranking ignores plan capacity". Its stated reason is that "every trigger
already bounds how far a small account is spent before the operation moves on; a capacity weight
would systematically leave a smaller account's perishable balance to lapse."

The first half of that reason is false today, and this plan's evidence shows it
(`001-mixed-plan-capacity.md`). anthropic-3 ($20) read 45% five-hour left at 22:37Z and was
refusing requests at 22:46Z, and anthropic-2 on a $20 plan fell about 70 points per 30-minute pass.
A percentage trigger checked every 30 minutes doesn't bound a small account's spend. The second
half still holds: weighting ranking by capacity would let small accounts' weekly quota lapse.

## Maintainer ruling (2026-10-14, attended)

Asked how the plan should treat capacity in candidate selection, the maintainer chose
**capacity-aware eligibility**. The v055 soonest-weekly-reset ranking stays, and
assertion 3 is reworded to:

> A pass does not switch onto a candidate that the fleet's current consumption, scaled to that
> candidate's capacity, would drain past the short-window rotation threshold before the next pass.

Rejected alternatives: reversing v055 to weight ranking by capacity, and dropping assertion 3 so
assertions 1 and 2 carry it alone.

Why this fits v055 rather than reversing it: once assertions 1 to 3 hold, the triggers really do
bound how far a small account is spent, so v055's rationale becomes true. Under factory load a
small account is ineligible, because the fleet would drain it within one pass. Under light load it
stays eligible and its perishable quota still gets spent first.

## A live, read-only source for the current plan

The vault's login-time fields (`claudeAiOauth.subscriptionType` / `rateLimitTier`) went stale on
anthropic-2's downgrade (`001`). Anthropic's `GET https://api.anthropic.com/api/oauth/profile`, sent
with an account's own OAuth access token and the `anthropic-beta: oauth-2025-04-20` header, returns
`organization.organization_type` and `organization.rate_limit_tier`. It is read-only and never
touches the token endpoint, so the **Never refresh** clause allows it. Measured 2026-10-14 on host
hp, each account read with its stored snapshot token:

| Profile | Stored (login-time) | Live `/api/oauth/profile` |
|---|---|---|
| anthropic-0 | max / default_claude_max_20x | claude_max / default_claude_max_20x |
| anthropic-1 | max / default_claude_max_20x | claude_max / default_claude_max_20x |
| anthropic-2 | max / default_claude_max_20x | claude_max / default_claude_max_20x |
| anthropic-3 | pro / default_claude_ai | claude_pro / default_claude_ai |
| anthropic-4 | max / default_claude_max_20x | not read: token locally expired |

**Not yet proved:** anthropic-2 was upgraded back to $200 at about 23:00Z on 2026-10-13, so stored
and live values agree again for every account. Nobody has yet seen this endpoint follow a downgrade.
That organization-level field is the provider's own server-side record, so it's the best candidate
source, but it stays a premise until a plan change is seen through it. `overseer-wzw2zw`'s
host-side proof owes that observation.

## Nominal multipliers versus observed burn

Anthropic's plan names imply a 20× ratio between Max 20x and Pro. The loop's own readings on
anthropic-2, same account and similar load, show about 10 five-hour points per pass on the $200 plan
and about 70 on the $20 plan: a ratio near **7×**, not 20×. Its weekly figure also jumped from 48%
to 98% left on the downgrade, so the two windows don't scale together. The eligibility rule must not
hardcode a provider's nominal multiplier. Scaling by observed burn per capacity class, or by a
configurable relative weight per class, is the design question the spec proposal must settle.

## Shape of the spec proposal (to route through `/livespec:propose-change`)

All four pieces land in `spec.md` §"Account rotation and quota supervision" with scenarios, as one
spec-change child. The factory may not edit `SPECIFICATION/`.

1. **Refusal trigger** (assertion 2). If the active account is seen refusing requests for a session
   or rate limit, the pass MUST rotate, whatever the usage figures say, and the switch line MUST
   name the refusal. Open point for drafting: what the loop observes. Candidates are the refusal
   records in tracked sessions' transcripts (no extra request) or a minimal probe on the active
   credential. Either way it is parsed per provider into a provider-agnostic refusal record.
2. **Fast-drain trigger and cadence** (assertion 1). Rotate when the active account's short-window
   remaining, projected at the burn rate seen between its recent readings, would reach the rotation
   threshold before the next scheduled pass. Settle whether the pass interval also shortens while
   the projection is near.
3. **Capacity-scaled eligibility** (assertion 3, worded as ruled above). Settle how a candidate's
   unknown capacity is treated. The default should be conservative, never generous.
4. **Capacity reporting** (assertion 4). The operator report shows each account's capacity class in
   provider-agnostic terms, with the provider's plan name only as detail. The value comes from a
   live read where the provider offers one, never from login-time credential fields, and it shows
   an explicit unknown when the plan can't be read.

The proposal keeps v055's ranking clause and its "Ranking ignores plan capacity" scenario. It
rewords only the ranking rationale sentence, so the sentence claims the trigger bound only where
clauses 1 to 3 establish it.

## The usage-API lag question is a host-side measurement, split out

`overseer-pffwyp` asked whether `/api/oauth/usage`'s five-hour figure lags under load (a flat 48 to
45 for an hour, then 45 to 0 in under twelve minutes). Answering it means polling real credentials
under real load, which no factory sandbox can do. Its acceptance bullet would have deadlocked a
dispatch, so it moves to its own host-side child, and `overseer-pffwyp` keeps only the repository
change. The answer feeds clause 2's design but doesn't block the refusal trigger, which works from
refusals that actually happened, whatever the percentage says.
