---
topic: release-currency
author: claude-sonnet-5-5
created_at: 2026-11-19T03:57:40Z
spec_commitments:
  impl_followups:
    - id_hint: release-currency-newest-run-grading
      description: |
        overseer-ydigho: the release-currency grader judges each check name by its newest completed run (completion time, then run id) and logs the deciding run per name.
    - id_hint: release-currency-bounded-forge-cost
      description: |
        overseer-nerus6: the currency check re-reads the release ref at most once per minute with a stored validator, caches the final verdict per commit for the process lifetime, and resolves the running build once.
---

## Proposal: release-currency

### Target specification files

- SPECIFICATION/spec.md
- SPECIFICATION/scenarios.md

### Summary

Adds one H2, `## Release currency`, to spec.md, immediately before `## First-run onboarding screens`, and three scenarios to scenarios.md. The section states the rules the daemon's self-update gate already implements or must implement: a candidate is adopted only when check-green; check-green is judged per check name from its newest completed run; every unknown fails toward not adopting; a currency failure never stops supervision; and the forge is not read on every tick.

### Motivation

The daemon's self-update gate is a safety guarantee, since it adopts only a tested release, yet SPECIFICATION/ says nothing about it: a grep for release currency, check-green, self-update and check-run finds no governing clause (the only hit is an unrelated line in constraints.md). That left two defects with no heading to govern them. overseer-ydigho: the grader counts every run whose conclusion is not `success`, so v5.66.0 (c01008284930) is refused because three check names each have a skipped run followed by a later success, and no daemon can self-update (both known daemons are stuck on 5.62.1). overseer-nerus6: the blocked verdict is re-resolved from the forge on every tick with three uncached `gh api` calls, about 540 calls per hour per host and about 970 per hour across the two known hosts, which drained the host's GitHub REST budget to 0 at about 02:30Z. Both ran to the factory's dod_gate and failed there because their References line cited `## Supervised runtimes`, which does not govern them. The grading rule is the throughput-plans coordinator's ruling of 2026-11-19, recorded on overseer-ydigho: newest completed run per name, success wins, a lone non-success newest run still blocks, no name allowlist. Specifying it makes the gate's meaning explicit; it does not loosen it, because a name whose newest run is skipped still blocks.

### Proposed Changes

In `SPECIFICATION/spec.md`, insert the following section immediately before the `## First-run onboarding screens` heading (it follows the end of `## Supervised runtimes`):

## Release currency

The daemon replaces its own running build only with a release whose checks are known to have passed. A release that merely exists is not adopted: a release-tag lane that fails for days still publishes releases, so released does not imply green.

- **Candidate.** The candidate is the commit the repository's `release` ref resolves to. The running build is identified by its own release tag, resolved once per process. A candidate equal to the running build is the routine "already current" verdict: it is not a blocked condition and raises no alert.
- **Check-green.** A candidate is eligible only when it is check-green. Check-green is judged per check NAME, from the newest completed run of that name, ordered by completion time and then by run id. A name whose newest completed run concluded `success` is green, whatever older runs of the same name concluded. A name whose newest run concluded anything else (skipped, neutral, cancelled, failed or timed out), or has no conclusion yet because it is still running, is not green. No check name is exempt, so there is no allowlist of names. A candidate that reports no check runs at all is not check-green.
- **Fail toward not adopting.** Every unknown resolves to ineligible: an unresolvable `release` ref, an unreadable check rollup, a check still running, and a candidate with no checks. Declining to update costs one release of staleness; adopting wrongly costs every tracked session. Each ineligible verdict other than "already current" is reported as blocked, and the report names the check names that decided it and, for each, the deciding run (its name, conclusion, and completion time or run id), so a refusal is auditable from the daemon log without re-querying the forge.
- **Fail open for supervision.** No currency failure stops, delays or alters supervision. An unreachable forge, an exhausted rate-limit budget, an unresolvable ref and malformed forge output each leave the daemon on its running build and the tick continuing, consistent with the fail-soft posture.
- **Bounded forge cost.** The currency check reads the forge at most once per minute, whatever the tick length. It re-reads the `release` ref with a conditional request that carries a validator stored from the previous read, so an unchanged ref answers not-modified and consumes no rate-limit budget. It re-resolves the verdict only when that ref's commit changes. The verdict for a commit whose checks are all final is kept for the life of the process and is not re-read. While a candidate's checks are still running, the daemon re-reads them no more often than once per minute. No forge read may rely on a client-side HTTP cache that serves an entry past its stated lifetime or sends no validator, as `gh api --cache` does.


In `SPECIFICATION/scenarios.md`, append the following three scenarios after the last scenario in the file:


## Scenario: A release whose newest run of every check name succeeded is adopted although an older run of one name was skipped

Given the `release` ref resolves to a commit newer than the running build

And one check name has a skipped run followed by a later successful run

And the newest completed run of every other check name succeeded

When the daemon evaluates release currency

Then the release is eligible

And the daemon log names the deciding run for each check name

## Scenario: A release whose newest run of a check name is skipped is not adopted

Given the `release` ref resolves to a commit newer than the running build

And the newest completed run of one check name concluded skipped

When the daemon evaluates release currency

Then the release is not eligible and is reported blocked

And the report names that check name and its deciding run

## Scenario: An unchanged release ref costs no forge read on a later tick

Given the daemon has evaluated release currency at the current commit of the `release` ref

When further ticks pass within one minute and the ref has not moved

Then the daemon makes no forge request on those ticks

And the daemon keeps supervising every track as before

Co-edits outside SPECIFICATION/ that land in the same change: `tests/heading-coverage.json` gains four TODO rows (the new spec.md H2 and the three new scenarios, owned by overseer-ydigho for the H2 and the two grading scenarios and by overseer-nerus6 for the cadence scenario), and `tests/heading-coverage-debt.json` gains the matching four debt rows.
