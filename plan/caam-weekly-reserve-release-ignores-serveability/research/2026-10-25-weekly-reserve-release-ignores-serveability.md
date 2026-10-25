## The maintainer's statement of what done means

All non-protected accounts should be able to be drained to zero.

## Definition of Done assertions derived from that statement

- With every live-verified account above the weekly reserve unable to serve a request now, a scheduled pass of the account-rotation operation selects a below-reserve unprotected account instead of holding with an empty candidate set.
- With at least one live-verified account above the weekly reserve able to serve a request now, a scheduled pass still excludes every candidate below the weekly reserve.
- A protected account's own protection floor is not released when the weekly reserve is released because no above-reserve account can serve a request now.
- The live caam-anthropic-loop runs every scheduled pass without a CAAM_ROTATE_WEEKLY_RESERVE override in its environment.

# The weekly reserve's release ignores whether the above-reserve accounts can serve

Recorded 2026-10-25 from a live incident on the caam-managed Claude Max fleet.
The problem statement below is the maintainer's report, kept verbatim; the
analysis that follows it was read from the code and the specification in this
repository.

## The problem, as reported (verbatim, measured 2026-10-25)

The caam account-rotation operation (livespec-overseer, overseer/caam_anthropic_loop.py; SPECIFICATION/spec.md section 'Account rotation and quota supervision') has a fleet-wide WEEKLY RESERVE (CAAM_ROTATE_WEEKLY_RESERVE, default 10 percent). The spec clause 'The weekly reserve MUST NOT be forfeited' says: candidates below the reserve MUST be excluded while any candidate is above it, and the reserve MUST be released once every account is below it, 'since at that point it protects nothing'. The release test looks at WEEKLY numbers only. It does not ask whether the above-reserve accounts can actually serve a request right now.

What happened: at 2026-10-25 11:18Z the active account anthropic-0 (weekly 60%) was exhausted: 5-hour window 0% AND its extra-usage monthly spend limit reached ($200.31 of $200.00) so it could serve no request and was not selectable. anthropic-4 (weekly 63%) had 5-hour window 0% until about 14:09Z. Both counted as 'above the reserve', so the reserve did NOT release, and anthropic-1, -2, -3 and -5 (5-hour windows fresh at 100%, but weekly 3, 5, 7, 8 percent, i.e. below the 10 percent reserve, none of them protected) stayed excluded. The loop HELD with 'the candidate set was empty' for hours while the whole factory fleet could not launch (pre-screens failed on the exhausted selected account). The reserve protected nothing, which is exactly the condition under which the spec says it should lift. The same shape occurred at 05:18Z-06:48Z the same day (a4 draining, candidates all under the reserve, a0 at 5-hour 14-15%).

The rule as literally written permits this; its own stated reason argues it is a gap. The code reads the reserve at overseer/caam_decision.py (os.environ CAAM_ROTATE_WEEKLY_RESERVE, default 10). The maintainer's position: all NON-PROTECTED accounts should be able to be drained to zero; only per-account protection floors (e.g. anthropic-0=10%, deliberate, the maintainer's main personal account) are exempt. A protection floor MUST NOT be released by the weekly reserve's release (spec clause 'A protection floor MUST NOT be released...'); that must stay true.

Interim workaround already applied by the operator: CAAM_ROTATE_WEEKLY_RESERVE=0 on every pass of the live loop (per invocation, not persisted). The plan should NOT depend on it.

## The literal spec text (SPECIFICATION/spec.md, section "Account rotation and quota supervision", v069)

The release clause, verbatim:

> **The weekly reserve MUST NOT be forfeited.** Candidates below the reserve
> MUST be excluded while any candidate is above it, and the reserve MUST be
> released once every account is below it, since at that point it protects
> nothing. The release governs the fleet-wide reserve only and MUST NOT be read
> as releasing any per-account protection floor.

The protection-floor clause that must survive any amendment, verbatim:

> **A protection floor MUST NOT be released by the weekly reserve's release.**
> The two floors answer different questions: the weekly reserve protects the
> fleet's ability to keep working and correctly stops protecting anything once
> every account is beneath it, whereas a protection floor is a commitment about
> one account that the operator relies on elsewhere. Releasing the second
> because the first ran out would breach that commitment at exactly the moment
> it was made for. Where every remaining candidate is protected and at or below
> its floor, the operation MUST hold and MUST report which accounts are
> protected and at what floor, rather than breaching a floor silently or
> stalling without a reason.

One existing clause already reaches part of the way, and is the precedent for
the amendment: under the usage-limit refusal trigger, "For the weekly reserve's
release, a refusal-held active account MUST NOT count as an account above the
reserve." That is a serveability carve-out, but only for the active account and
only while it is refusal-held. It did not apply on 2026-10-25, where the two
above-reserve accounts were spend-capped or short-window exhausted rather than
refusal-held.

## Why the literal reading permits the stall

The release condition is a predicate over WEEKLY remaining alone: "once every
account is below it". On 2026-10-25 11:18Z two accounts (anthropic-0 at 60%
weekly, anthropic-4 at 63% weekly) were above the 10% reserve, so the condition
was false and the reserve stayed in force. Both of those accounts were unable
to serve a request: anthropic-0 was spend-capped (monthly extra-usage limit
reached) with a 0% short window, anthropic-4 had a 0% short window. The four
accounts that COULD serve (fresh 100% short windows) were all below the reserve
and therefore excluded. The candidate set was empty and the pass held.

The clause's own justification is "since at that point it protects nothing".
The reserve exists to keep some weekly allowance available so the fleet can
keep working. When every above-reserve account cannot serve, the reserve is
protecting allowance on accounts that cannot spend it, and withholding the only
accounts that can. That is the condition the justification names, reached by a
route the literal predicate does not see. The rule as written is therefore
consistent with the stall and inconsistent with its own stated reason.

## Where the code implements the literal reading

- `overseer/caam_decision.py`: `weekly_reserve()` reads
  `CAAM_ROTATE_WEEKLY_RESERVE` (default `10`). `eligible_profiles(...)` selects
  with `enforce_reserve=True`; when that set is empty it releases the reserve
  ONLY IF `every_live_account_under_reserve(profiles=...)` is true, which is
  `all(weekly_left(usage) < weekly_reserve() for every live-verified usage)` --
  a weekly-only predicate. Otherwise it returns an empty set with no release.
- `overseer/caam_decision_protection.py`: `candidate_allowed(...)` applies the
  reserve as `weekly_left(usage) >= policy.weekly_reserve` when
  `policy.enforce_reserve` is set, and `is_eligible(...)` carries the
  cannot-serve disqualifiers (`spend_capped`, zero weekly, zero short window)
  on the CANDIDATE side only. Nothing asks whether the accounts that keep the
  reserve in force can themselves serve.
- `overseer/caam_extra_usage.py`: `spend_capped(usage)` is the monthly-spend-cap
  predicate (reached cap AND an included window with nothing left).
- `overseer/caam_decision.py`: `five_hour_remaining_floor()` reads
  `CAAM_ROTATE_FIVE_HOUR_REMAINING` (default `15`), the short-window rotation
  threshold.
- `overseer/caam_release_note.py`: `empty_release_note(...)` words the release
  ("every live-verified account is under the N% weekly reserve -- releasing
  it") and the protected-floor hold.
- `overseer/caam_candidate_diagnosis.py`: `no_candidate_cause(...)` names the
  gate that emptied the set; on 2026-10-25 it reported the spend cap and the
  weekly-reserve margin, which is accurate and still a hold.

## The proposed change (spec tier, human-gated)

Amend the release condition so the weekly reserve is released when NO account
that is ABOVE the reserve can serve a request right now. "Can serve now" means:
live-verified, not blocked by an extra-usage or monthly spend cap, and
short-window remaining above the short-window rotation threshold (not
exhausted). Keep:

- a protection floor is never released by this release (the protection-floor
  clause above stands unchanged);
- the reserve still applies while at least one above-reserve account can serve;
- the cannot-serve-immediately disqualifier, the zero-weekly disqualifier and
  "A candidate MUST be able to carry the current load until the next pass"
  continue to apply to every candidate admitted by the release, exactly as they
  apply today.

Add a scenario to `SPECIFICATION/scenarios.md` (Given/When/Then) covering the
2026-10-25 shape: two above-reserve accounts that cannot serve (one
spend-capped with an exhausted short window, one with an exhausted short
window), four below-reserve unprotected accounts with fresh short windows; when
a scheduled pass runs, the operation rotates to one of the below-reserve
accounts instead of holding.

## Why two children, split by tier

A spec change and a code change cannot share one work item: the factory
sandbox forbids any commit touching `SPECIFICATION/`
(`scripts/check-no-factory-spec-edits.sh`), so a mixed-tier item deadlocks in
the factory (see `.ai/dispatch-traps.md` and the repository `CLAUDE.md`
"Mixed-tier items are not dispatchable at all"). So:

1. A SPEC-CHANGE-TIER child whose deliverable is a `/livespec:propose-change`
   of the clause plus the scenario. It is human-gated (ratified only through
   `/livespec:revise`), is filed with a spec commitment so the plan primitives
   refuse to dispose of it mechanically, and MUST NOT be factory-dispatched.
2. A CODE child, dependent on the spec child landing on master, that changes
   the release logic in the rotation code with tests, under red-green-replay,
   with no `SPECIFICATION/` edit and no host-side act, so it is dispatch-safe.

## Explicit deferrals

- The plan does NOT depend on the interim operator workaround
  (`CAAM_ROTATE_WEEKLY_RESERVE=0` on every pass of the live loop). That
  workaround is per invocation and not persisted; the plan's fourth assertion is
  that the live loop runs without it once the change ships.
- Sandboxing the cron scheduler that invokes the live loop is NOT carried by
  this plan.
- The loop session living on the account being rotated is NOT carried by this
  plan.
- The cron DST wall-clock issue (the 2026-10-25 01:00Z gap in cron fires, as
  recorded in `plan/archive/caam-scheduled-marker-never-lost/`) is NOT carried
  by this plan.

Each is recorded here so it is not lost; none has a child under this epic, and
each would be reconsidered only on a maintainer request or on a recurrence that
names it.
