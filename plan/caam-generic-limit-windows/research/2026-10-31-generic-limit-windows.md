## The maintainer's statement of what done means

This should also incorporate forward-looking support for other non-Anthropic accounts. Make the 5-hour thing generic but able to handle other types of additional limits that may be throttling or governing it, regardless of where they come from.

## Definition of Done assertions derived from that statement

- A scheduled pass whose active account reports no short-window limit reads that account successfully and evaluates the weekly trigger instead of failing with exit 2.
- An account whose usage response carries no short-window limit appears in the account table with its weekly figures and a statement that it has no short-window limit, and is not reported as dark.
- An account with no short-window limit is eligible as a rotation destination on the dimensions it does have.
- A usage response carrying a limit kind the program does not recognise leaves the account readable and shows the unrecognised limit in the account table.
- An account that gains a temporary short-window limit is evaluated against the short-window trigger on the reading that reports it, and returns to weekly-only evaluation on a reading that does not.
- The specification states how the operation treats an account with no short-window limit and an account carrying additional limits from any provider.

# caam must treat an account's limit windows as a generic, per-account set

Recorded 2026-10-31 from a live incident plus a maintainer ruling the same day.
Everything under "Measured" was observed in the loop session; the Anthropic
statement is quoted from the vendor's own page.

## Maintainer statement (verbatim)

"This should also incorporate forward-looking support for other non-Anthropic
accounts. Make the 5-hour thing generic but able to handle other types of
additional limits that may be throttling or governing it, regardless of where
they come from."

This is a DESIGN CHANGE, not a defect fix. The maintainer's position, confirmed
against the vendor page below: accounts without a 5-hour limit are an intended
provider tier, so the program's assumption that every account has a 5-hour
window is what has aged.

## Measured (2026-10-31)

- Since 2026-10-31T09:21:57Z every scheduled pass fails with exit 2, "FAIL
  cannot read usage for active profile anthropic-5". The loop cannot evaluate
  any trigger for the seat in use.
- The usage reader (`_usage_record`, overseer/caam_usage.py) requires a numeric
  `five_hour.utilization` and `seven_day.utilization`; otherwise it raises and
  the account is reported "dark: unexpected response shape".
- anthropic-1 and anthropic-5 return `five_hour: null`; anthropic-6 joined them
  at 14:21Z (pass 2026-10-31T14:21:58Z). For all three the response `limits`
  list holds only `weekly_all` and `weekly_scoped`; every other account also
  lists `session`. Weekly utilization on all three reads normally.
- Three of seven managed accounts are therefore dropped, including the active
  one and one of the usable rotation destinations.
- The CAPACITY column still reads `default_claude_max_20x` for all three; that
  label comes from profile data, not the usage endpoint.

## Vendor statement

support.claude.com "Use Claude Code with your Pro, Max, or Ultra plan":
"Ultra plans have a weekly limit, and verified Ultra accounts don't have a
five-hour session limit." It also says an Ultra account may have a TEMPORARY
limit, to which the Max wrap-up allowance applies. So a `session` entry can
appear and disappear on the same account: the reader must decide per reading,
never once per account.

## Design direction

1. The usage response's own limits are the authority. An account has a SET of
   limit windows, each with a kind, a remaining/used figure, and a reset time
   where the provider reports one. The short window ("5-hour") is one kind
   among several, not a required field.
2. An absent short window means NO short-window trigger for that reading: the
   weekly trigger (and the other triggers that do not need a short window)
   still apply, the account stays readable, and it remains a rotation
   destination ranked on the dimensions it does have.
3. The reader tolerates additional or unknown limit kinds, from any provider,
   without becoming unreadable: a limit the program does not understand is
   recorded and shown, never fatal. A provider-agnostic limit record carries
   kind, remaining, reset time, and whether it throttles or governs.
4. A limit that is KNOWN and tighter than the rest (a temporary session limit, a
   scoped limit, a throttle from another provider) participates as a trigger
   on the dimension it names, using the existing "compare on the dimension
   that triggered the rotation" rule.
5. Unreadable stays reserved for a response that carries NO usable limit at all
   or is malformed; "this account lacks a window" is a reading, not a failure.

## Spec relationship

SPECIFICATION/spec.md (rotation triggers, short-window floor, burn-rate
projection, refusals, resets) is already worded provider-agnostically ("short
window", "provider-agnostic refusal/reset"), but nothing states what the
operation does when an account has no short window, and "rotation triggers"
reads as if one always exists. That wording is spec-tier and routes through
propose-change as its own child; the factory cannot edit SPECIFICATION/
(scripts/check-no-factory-spec-edits.sh), so the code child and the spec child
are separate items.

## Out of scope / deferrals

- Any non-Anthropic provider adapter itself (this plan only makes the limit
  model generic enough to take one).
- Changing the rotation thresholds, the weekly reserve, or destination ranking.
- Re-labelling the CAPACITY column from the usage endpoint.
