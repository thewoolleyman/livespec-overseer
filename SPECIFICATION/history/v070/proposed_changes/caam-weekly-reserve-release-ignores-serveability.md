---
topic: caam-weekly-reserve-release-ignores-serveability
author: claude-opus-5-5
created_at: 2026-10-25T16:11:05Z
---

## Proposal: Release the weekly reserve when no account above it can serve a request now

### Target specification files

- SPECIFICATION/spec.md
- SPECIFICATION/scenarios.md

### Summary

Amend the clause 'The weekly reserve MUST NOT be forfeited' in spec.md §'Account rotation and quota supervision' so that the fleet-wide weekly reserve is released when no unprotected account above the reserve is USABLE, not only when every account is below it. CAN SERVE NOW is defined as live-verified, not refusal-held (active or not), not spend-blocked (monthly extra-usage cap reached while the short or weekly window has nothing left), and short-window remaining above the short-window floor. The active account is usable while it can serve now and the fast-drain trigger has not fired on it; any other account while it can serve now and survives every other selection rule on that pass, including the Eligibility margin and the capacity test applied without its refusal-held release. A protected account never keeps the reserve in force. The reserve decision is made first and the capacity test's refusal-held release is evaluated over the resulting candidate set. Two existing sentences are reworded for consistency (the refusal-trigger sentence and the protection-floor rationale); no per-account protection floor is relaxed. Thirteen Given/When/Then scenarios are added to scenarios.md.

### Motivation

Measured 2026-10-25 on the caam-managed Claude Max fleet with the default 10% weekly reserve in force (the maintainer's interim override began only at 13:17Z), from the operation's own scheduled-pass output. 09:48:03Z: the active account anthropic-4 (unprotected, weekly 65%) crossed the short-window threshold at 13% left; anthropic-1, -2, -3 and -5 (unprotected, weekly 3, 5, 7 and 8%, short windows 100%) were excluded only by the reserve, so the pass switched to anthropic-0, the protected main account (weekly 78%, the only account with extra usage, already at its monthly pay-as-you-go spend limit), spending the maintainer's protected account ahead of four unprotected accounts. 11:18:09Z: anthropic-0 was active with a 0% short window and had reached its monthly extra-usage spend limit ($200.31 of $200.00; the program itself alerted that it 'can serve no request and is not selectable'); anthropic-4 (weekly 63%) had a 0% short window; neither could serve, yet both counted as above the reserve, so the pass held with 'the candidate set was empty ... within the weekly reserve' and anthropic-1, -2, -3 and -5 stayed excluded. The hold left the published selection on anthropic-0, so the factory stayed pointed at an unservable account from 11:18Z to 13:10Z, and a factory turn hit 'org monthly spend limit' at 12:23Z (run 01M5S83BWDYG). The same empty-set shape occurred at 05:18Z-06:48Z. The clause's own justification for the release is 'since at that point it protects nothing', and that condition was reached by a route its weekly-only predicate does not see. The maintainer's position, verbatim: 'All non-protected accounts should be able to be drained to zero.' Only per-account protection floors (anthropic-0 at 10%) are exempt. The existing refusal-trigger sentence is the precedent for a serveability carve-out; this proposal generalizes it. WHY ONLY UNPROTECTED ACCOUNTS KEEP THE RESERVE IN FORCE: a protected account counted toward the reserve excludes the unprotected accounts below it, and the protection ordering then selects or keeps the protected account ahead of them, which is exactly what happened at 09:48Z and 11:18Z; its own floor still protects it, unchanged. WHY USABLE RATHER THAN MERELY ABLE TO SERVE: an account that would reach the short-window floor before the next pass, or that the Eligibility margin or capacity test would reject as a candidate, cannot absorb the load, so holding the reserve for it reproduces the stall one pass later. The separate question of what a HOLD publishes while the active account cannot serve is deferred to overseer-occk. Evidence and code map: plan/caam-weekly-reserve-release-ignores-serveability/research/2026-10-25-weekly-reserve-release-ignores-serveability.md (epic overseer-4ri2g2, spec child overseer-ihwtuu, code child overseer-2fjvy6).

### Proposed Changes

1. In SPECIFICATION/spec.md §'Account rotation and quota supervision', replace the paragraph that begins '**The weekly reserve MUST NOT be forfeited.**' in full with:

**The weekly reserve MUST NOT be forfeited.** An account CAN SERVE NOW when it is live-verified; it is not refusal-held, whether or not it is the active account; it is not SPEND-BLOCKED, meaning its monthly extra-usage spend cap is reached while its short window or its weekly window has nothing left; and its short-window remaining is above the short-window floor. Only an UNPROTECTED account above the reserve keeps the reserve in force, and only while it is USABLE. The active account is usable while it can serve now and the trigger under **An account that will reach the floor before the next pass MUST be left now** has not fired on it. Any other account is usable only while it can serve now and also survives, as a candidate on that pass, every other selection rule, namely: the zero-weekly and cannot-serve-immediately disqualifiers; the **Eligibility** margin on each dimension the governing trigger compares, applied without the scoped-model clause's exception to that margin, and with no margin where no trigger governs or the expiring-quota drain governs; and the capacity test defined under **A candidate MUST be able to carry the current load until the next pass**, applied WITHOUT that clause's release for a refusal-held active account. So no account that the fast-drain trigger or the capacity test projects to reach the short-window floor before the next pass keeps the reserve in force, whether it is the active account or not. Candidates below the reserve MUST be excluded while at least one unprotected account above the reserve is usable, and the reserve MUST be released once none is — whether because every unprotected account is below the reserve or because no unprotected account above it is usable — since at that point it protects nothing: it would keep allowance on accounts that cannot spend it while withholding the only unprotected accounts that can. A protected account MUST NOT keep the reserve in force, whatever its weekly remaining and whether or not it is the active account, because counting it would exclude the unprotected accounts below the reserve and so select or keep the protected account ahead of them, inverting the protection ordering. The reserve decision MUST be made first, and the capacity test's release for a refusal-held active account MUST then be evaluated over the candidate set that decision leaves, including every candidate the reserve's release admits. This release is the weekly reserve's own rule rather than a relaxation of it by any trigger, so the clauses stating that a trigger MUST NOT relax the weekly reserve are unaffected. The release governs the fleet-wide reserve only and MUST NOT be read as releasing any per-account protection floor: it MUST NOT relax any per-account protection floor or the protection ordering. Every candidate the release admits MUST still survive the zero-weekly disqualifier, the cannot-serve-immediately disqualifier, the live-verification rule and the capacity test, subject to that test's own release, exactly as any other candidate. The release does not reach the expiring-quota drain, whose condition (d) still keeps a drain off any candidate below the reserve. A switch or hold made under a rotation trigger other than the expiring-quota drain on a pass that released the reserve MUST report that the weekly reserve was released and why: either that no unprotected account is above it, or that no unprotected account above it was usable, in which case the report MUST name those accounts.

2. In the usage-limit refusal trigger paragraph, replace the sentence 'For the weekly reserve's release, a refusal-held active account MUST NOT count as an account above the reserve.' with 'For the weekly reserve's release, a refusal-held active account MUST NOT count as a usable account above the reserve.' so that only the 'no unprotected account above it was usable' report reason applies to it. In the paragraph '**A protection floor MUST NOT be released by the weekly reserve's release.**', replace the phrase 'correctly stops protecting anything once every account is beneath it,' with 'correctly stops protecting anything once no unprotected account above it is usable,' so its rationale names both release routes; the rule in that paragraph is unchanged. The zero-weekly disqualifier, the cannot-serve-immediately disqualifier and the clause 'A candidate MUST be able to carry the current load until the next pass' are not edited and continue to apply to every candidate the release admits.

3. In SPECIFICATION/scenarios.md, insert the following thirteen scenarios immediately after '## Scenario: The capacity test holds when it excludes every candidate and the active account is not refusing' and its body (before '## Scenario: The account table shows each account\'s capacity class'):

## Scenario: The weekly reserve is released when no account above it can serve a request now

Given the active account is unprotected, live-verified and above the weekly reserve, and has reached its monthly spend cap with an exhausted short window

And one other live-verified unprotected account is above the weekly reserve with short-window remaining above zero but at or below the short-window floor

And four live-verified unprotected accounts hold weekly remaining below the weekly reserve but above zero, with fresh short windows

And a fleet load is recorded under which the account at the short-window floor fails the capacity test and at least one of the four passes it

When a scheduled pass runs

Then the operation releases the weekly reserve and rotates to one of the four accounts below the reserve instead of holding with an empty candidate set

And it reports that the weekly reserve was released because no unprotected account above it was usable, naming the two accounts above the reserve

## Scenario: The weekly reserve is released when the protected active account is spend-blocked and every other account above it is exhausted

Given the active account is protected, live-verified, above both the weekly reserve and its own protection floor, and has reached its monthly spend cap with an exhausted short window

And the only unprotected account above the weekly reserve is live-verified with an exhausted short window

And four live-verified unprotected accounts hold weekly remaining below the weekly reserve but above zero, with fresh short windows, and at least one of them passes the capacity test

When a scheduled pass runs

Then the operation releases the weekly reserve and rotates off the protected account to one of the four accounts below the reserve instead of holding with an empty candidate set

And it reports that the weekly reserve was released because no unprotected account above it was usable, naming the exhausted unprotected account

## Scenario: The weekly reserve stays in force while an account above it can serve a request now

Given the active account has crossed the short-window rotation threshold

And one live-verified unprotected account holds weekly remaining above the weekly reserve, can serve a request now, holds the eligibility margin over the active account and passes the capacity test

And other live-verified unprotected accounts hold weekly remaining below the weekly reserve with fresh short windows

When a scheduled pass runs

Then every account below the weekly reserve stays excluded from selection

## Scenario: An account above the reserve that would reach the floor before the next pass does not keep the reserve in force

Given the active account is unprotected, below the weekly reserve, and has crossed the short-window rotation threshold

And the only unprotected account above the weekly reserve can serve a request now but fails the capacity test under the recorded fleet load

And a live-verified unprotected account below the weekly reserve holds weekly remaining above zero and survives every selection rule other than the weekly reserve, including the eligibility margin over the active account and the capacity test

When a scheduled pass runs

Then the operation releases the weekly reserve and rotates to that account below the reserve

And it reports that the weekly reserve was released because no unprotected account above it was usable, naming the account that failed the capacity test

## Scenario: An account above the reserve that lacks the eligibility margin does not keep the reserve in force

Given the active account is protected, above both the weekly reserve and its own protection floor, and its short-window remaining is at or below the short-window floor

And the only unprotected account above the weekly reserve is live-verified, passes the capacity test, and holds short-window remaining above the short-window floor but less than the eligibility margin above the active account's short-window remaining

And a live-verified unprotected account below the weekly reserve holds weekly remaining above zero and survives every selection rule other than the weekly reserve, including the eligibility margin over the active account and the capacity test

When a scheduled pass runs

Then the operation releases the weekly reserve and rotates to that account below the reserve

And it reports that the weekly reserve was released because no unprotected account above it was usable, naming the account that lacked the margin

## Scenario: An active account projected to reach the floor before the next pass does not keep the reserve in force

Given the active account is unprotected, live-verified and above the weekly reserve, with short-window remaining above the short-window floor

And its known short-window burn rate projects it to reach the short-window floor within the projection horizon, so the fast-drain trigger fires

And the active account holds a usable reset that clears its short window

And no other unprotected account is above the weekly reserve

And a live-verified unprotected account below the weekly reserve holds weekly remaining above zero and survives every selection rule other than the weekly reserve, including the eligibility margin over the active account and the capacity test

When a scheduled pass runs

Then the operation releases the weekly reserve and rotates to that account below the reserve rather than claiming a reset on the active account

And it reports that the weekly reserve was released because no unprotected account above it was usable, naming the active account

## Scenario: A refusal-held account above the reserve does not keep the reserve in force

Given the only unprotected account above the weekly reserve is refusal-held and is not the active account, and its readings show a fresh short window

And the active account is below the weekly reserve and has crossed the short-window rotation threshold

And a live-verified unprotected account below the weekly reserve holds weekly remaining above zero and survives every selection rule other than the weekly reserve, including the eligibility margin over the active account and the capacity test

When a scheduled pass runs

Then the operation releases the weekly reserve and rotates to that account below the reserve

And it reports that the weekly reserve was released because no unprotected account above it was usable, naming the refusal-held account

## Scenario: The reserve decision precedes the capacity test's release for a refusal-held active account

Given the active account is unprotected, above the weekly reserve and refusal-held

And the only other unprotected account above the weekly reserve can serve a request now and holds the eligibility margin, but fails the capacity test under the recorded fleet load

And a live-verified unprotected account below the weekly reserve holds weekly remaining above zero and survives every selection rule other than the weekly reserve, including the eligibility margin over the active account and the capacity test

When a scheduled pass runs

Then the operation releases the weekly reserve, does not release the capacity test, and rotates to the account below the reserve

And it reports that the weekly reserve was released because no unprotected account above it was usable, naming the refusal-held active account and the account that failed the capacity test

## Scenario: The capacity test's release reaches candidates the reserve's release admitted

Given the active account is unprotected, above the weekly reserve and refusal-held

And the only other unprotected account above the weekly reserve can serve a request now and holds the eligibility margin, but fails the capacity test under the recorded fleet load

And one live-verified unprotected account below the weekly reserve holds weekly remaining above zero and survives every selection rule other than the weekly reserve and the capacity test, which it also fails

When a scheduled pass runs

Then the operation releases the weekly reserve, then releases the capacity test, and selects whichever of those two candidates **Ranking** places first

And it reports both the weekly reserve's release and the capacity test's release

## Scenario: The scoped-model margin exception does not keep the weekly reserve in force

Given an operator pin names the scoped model, and the active account is protected, live-verified, above both the weekly reserve and its own protection floor, and at or below the scoped-model reserve on the scoped allowance

And the only unprotected account above the weekly reserve can serve a request now, passes the capacity test and holds the scoped allowance above the scoped-model reserve, but lacks the eligibility margin over the active account on the dimension the governing trigger compares

And a live-verified unprotected account below the weekly reserve holds weekly remaining above zero, holds the scoped allowance above the scoped-model reserve, survives every selection rule other than the weekly reserve, including the eligibility margin and the capacity test, and has the earlier weekly reset of the two

When a scheduled pass runs

Then the operation releases the weekly reserve and rotates to the account below the reserve

And it reports that the weekly reserve was released because no unprotected account above it was usable, naming the account above the reserve that lacked the margin

## Scenario: An account above the reserve that is not live-verified does not keep the reserve in force

Given the active account is unprotected, below the weekly reserve, and has crossed the short-window rotation threshold

And the only unprotected account above the weekly reserve is not live-verified

And a live-verified unprotected account below the weekly reserve holds weekly remaining above zero and survives every selection rule other than the weekly reserve, including the eligibility margin over the active account and the capacity test

When a scheduled pass runs

Then the operation releases the weekly reserve and rotates to that account below the reserve

And it reports that the weekly reserve was released because no unprotected account above it was usable, naming the account that is not live-verified

## Scenario: A protected account above the reserve does not keep the reserve in force

Given a live-verified protected account holds weekly remaining above both the weekly reserve and its own protection floor, with a fresh short window

And every unprotected account holds weekly remaining below the weekly reserve

And the active account is unprotected and has crossed the short-window rotation threshold

And another live-verified unprotected account holds weekly remaining above zero and survives every selection rule other than the weekly reserve, including the eligibility margin over the active account and the capacity test

When a scheduled pass runs

Then the operation releases the weekly reserve and rotates to that unprotected account rather than to the protected account

And it reports that the weekly reserve was released because no unprotected account is above it

## Scenario: A release on serveability grounds does not release a protection floor

Given the active account is unprotected, live-verified and above the weekly reserve, its short-window remaining is at or below the short-window floor, and it holds no usable reset

And no other unprotected account is above the weekly reserve

And the only remaining candidates are protected accounts at or below their own protection floors

When a scheduled pass runs

Then the operation holds rather than selecting a protected account at or below its floor

And it reports which accounts are protected and at what floor

And it reports that the weekly reserve was released because no unprotected account above it was usable, naming the active account

4. In tests/heading-coverage.json, add one entry per new scenario heading with spec_file 'scenarios.md', test 'TODO' and work_item 'overseer-2fjvy6' (the code child that will drive each scenario through the shipped rotation pass at integration tier). No other H2 heading changes.
