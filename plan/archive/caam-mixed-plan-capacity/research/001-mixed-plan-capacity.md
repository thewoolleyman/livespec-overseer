## The maintainer's statement of what done means

OK.  Here's one thing that may have an impact.  -1 and -2 are $200 plans, anbd -2 and -3 are $20 plans.  Very differnt usage.  If you have baked in assumptions for the higher usage then that's a problem we need to fix.  And I want a work item created to add a column to the table that indicates what kind of plan/usage the accdount it (again, provider agnostic, not baked to anthropic).   But for now, we need to get availabilith so we can keep running.  I sugest upgrading -2 to a $200 plan again.  WDYT?

## Definition of Done assertions derived from that statement

- A pass rotates off a small-plan active account that drains faster than one pass interval before that account refuses requests.
- A pass rotates off an active account that is refusing requests for a session or rate limit, whatever the usage API reports.
- Candidate ranking prefers a large-capacity account over a small-capacity one when both are otherwise eligible.
- The account table shows each account's current plan or capacity class in provider-agnostic terms.

# caam-mixed-plan-capacity

The account-rotation loop assumes every account has large-plan capacity and trusts only the usage API percentage. On a small plan the five-hour window can drain inside one 30-minute pass, so the percentage triggers never see it, and the loop has no signal for an account that is already refusing requests. Candidate ranking ignores capacity, and the table gives the operator no way to see each account's plan.

## Evidence (2026-10-13, host hp)

- The maintainer runs mixed plan tiers: anthropic-0 and anthropic-1 are $200 plans, anthropic-2 and
  anthropic-3 are $20 plans (anthropic-2 was upgraded back to $200 at about 23:00Z after this evidence).
- The vault's login-time credential fields (`claudeAiOauth.subscriptionType` / `rateLimitTier`) still read
  `max` / `default_claude_max_20x` for anthropic-2 after its downgrade, so they cannot be trusted as the
  current plan.
- The loop's own output shows the downgrade: at 20:07Z anthropic-2's weekly jumped from 48% to 98% left and
  its Fable column went blank; its five-hour window then fell 75% -> 36% -> 5% within about half an hour,
  where as a $200 plan that morning it fell about 10 points per 30-minute pass.
- anthropic-3 ($20) read LIVE from `/api/oauth/usage` at 48%, 46%, 45%, 45% five-hour left from 21:37Z to
  22:37Z under heavy parallel load; the first session-limit refusal in session transcripts is at
  22:46:22Z, nine minutes after the last 45% read; a dry run at 22:49Z read 0%. The loop held every pass,
  and the maintainer switched to anthropic-1 by hand.

## Items this plan adopts

- `overseer-pffwyp` (bug) -- rotate off an account that is refusing requests, whatever the usage API reports.
- `overseer-ivpkrf` (bug) -- percentage triggers, 30-minute cadence and ranking assume large-plan capacity.
- `overseer-wzw2zw` (feature) -- provider-agnostic plan/capacity column in the account table.

Any change to the ratified rotation triggers or ranking routes through `/livespec:propose-change` first; capacity-weighted ranking is also an open decision on spec item `overseer-4oavgh` (plan `caam-expiring-quota-drain`), so coordinate with that thread rather than deciding it twice.
