# How the gap was found, and why it stayed invisible

Recorded 2026-08-02 and refreshed after the fleet rollout on 2026-08-03. The
measurements are cheap to re-run and the *reasoning* is what is expensive to
redo — that is why this note exists.

## It surfaced from a sentence, not from a check

The supervisor of `codex-parity-and-rollout-safety` had concluded, twice in
writing, that release PR #360 sitting open was **"a human gate by design"**. The
evidence offered was real: all nine of this repo's workflows were enumerated,
none armed auto-merge, and every post-release workflow (`release-tag`,
`fast-forward-release-branch`, `release-dispatch`, `adopter-release-dispatch`)
fired only *after* a release existed. The chain looked deliberately
human-gated at exactly one link.

The maintainer replied: *"I have never manually cut a release ever before on
livespec repos."*

That one sentence outweighed the whole audit, and the reason is worth keeping:
**an absence that was never tested against a comparison is not evidence of
design.** The audit only ever looked inside this repo. One cross-repo query
inverted the conclusion.

## The first measurement settled the repo, not the fleet

```
auto-enable-merge.yml   PRESENT  thewoolleyman/livespec
auto-enable-merge.yml   PRESENT  thewoolleyman/livespec-dev-tooling
auto-enable-merge.yml   ABSENT   thewoolleyman/livespec-overseer
release-please.yml      present in all three     <- CONTROL
```

And the consequence, observed rather than inferred:

```
livespec              0.21.1 / 0.21.2 / 0.21.3 / 0.21.4   merged by app/livespec-pr-bot
livespec-dev-tooling  1.14.3 / 1.14.4 / 1.14.5 / 1.14.6   merged by app/livespec-pr-bot
livespec-overseer     #333 (0.15.0)                        merged by `thewoolleyman`
livespec-overseer     #360 (0.16.0)                        OPEN and merge-ready for 4 days
```

That comparison proved this repo's defect. It did **not** support the stronger
claim that livespec-overseer was the only fleet repo missing the workflow. A
second audit widened the same query to all nine release-please-carrying repos.
Seven `PRESENT` rows supplied the control, while two more parked release trains
appeared:

```
livespec-console-beads-fabro  ABSENT  #404 (0.4.0)   open since 2026-07-23
livespec-runtime              ABSENT  #322 (0.13.1)  open since 2026-07-24
```

Neither repo had ever merged a release-please PR. The owning-tenant carriers
are `livespec-console-beads-fabro-4vo` and `livespec-runtime-2xs`.

The durable correction is stricter than "compare before inferring design":
**the comparison population must cover the claim.** Comparing one repo with two
siblings can prove a local difference, but cannot prove an "only in the fleet"
claim. The unsupported reassuring half of the first audit left two release
trains parked for ten days.

## Why it was invisible: a hand-merge is indistinguishable from automation

`#333` shows `mergedBy: thewoolleyman`. In this fleet agents authenticate with
the maintainer's credentials, so an agent merge and a human merge are the same
string. Combined with the maintainer never having done it by hand, the previous
release was almost certainly merged by an agent in a prior session.

**A gap papered over once by hand looks exactly like a gap that does not
exist.** That is the whole reason four days passed with a merge-ready release PR
and nobody alarmed.

## The fleet had already diagnosed this

From livespec's own copy of the workflow:

> across 2026-06-30..2026-07-03 the fleet's release train stalled in all six
> repos — release-please's App-authored release PRs were never in the author
> allowlist, so auto-merge was never enabled and the release PRs silently
> parked (livespec-c1k9).

This repo was scaffolded 2026-07-21 — *after* that fix — and never received the
workflow. So it is re-living a defect the fleet had already paid for.

Also load-bearing, from the same file: `GITHUB_TOKEN` **cannot** enable
auto-merge. The GraphQL `enablePullRequestAutoMerge` mutation needs admin access
that `github-actions[bot]` lacks regardless of declared `permissions:`. That is
why the original attempt was reverted (`li-8f3` supersedes `li-abl`) and why an
App installation token is required.

## Fleet rollout has three outcomes, not two

Installing the workflow is not equivalent to proving a hands-off release
train. The rollout produced three distinct outcomes:

- **livespec-overseer — proven hands-off.** The workflow landed, release PRs
  were armed by `app/livespec-pr-bot`, and v0.16.1 merged and released without a
  human or agent pressing merge.
- **livespec-runtime — proven hands-off.** Workflow PR #437 merged through the
  App; parked release PR #322 then merged through the App and v0.13.1 became
  that repo's first completed release train.
- **livespec-console-beads-fabro — automation proven, hands-off release not
  proven.** Workflow PR #604 merged through the App and release PR #404 was
  armed, but its only required check fails by construction: release-please
  updates the manifest to 0.4.0 while the source constant
  `DOCS_REVIEWED_AGAINST` remains at its manually reviewed 0.3.0 value. That is
  a real human review gate at a different link. Its design decision is carried
  by `livespec-console-beads-fabro-53t`; this thread does not choose among the
  defensible resolutions.

The third outcome is the mirror image of the original mistake. Here, declaring
"human gate by design" from an absent workflow was false; in console, declaring
"fixed" from a present and firing workflow would also be false. Presence and
absence are both incomplete observations until tested against the repo's actual
release contract.

There is also a timing trap. `auto-enable-merge.yml` uses `pull_request`, so
GitHub reads the workflow from the PR's **head**, not from current master. A
parked release PR whose head predates the workflow will not be armed
retroactively; release-please must rebuild that branch from a master containing
the workflow. "Workflow present on master, old release PR still unarmed" is
therefore not by itself evidence that the workflow is broken.

## The second defect, found while fixing the first

Merging #360 cut v0.16.0 correctly — tag, release, and `origin/release`
advanced with the launcher at 0.16.0. But `Release tag` **failed**, and the
history shows it has failed on every release since 2026-07-30:

```
Release tag        2026-08-02  FAILURE  v0.16.0
                   2026-07-30  FAILURE  v0.15.0
                   2026-07-30  FAILURE  v0.14.0
                   2026-07-27  success        <- last green

Release readiness  2026-08-02  failure
   (daily canary)  2026-08-01  failure
                   2026-07-31  failure
                   2026-07-30  failure
                   2026-07-29  success        <- flipped here
```

The canary did its job. It was built for exactly this — its own header says its
contribution is **severity, not coverage**, re-running per-commit targets with
the fail-mode levers set so "master is currently un-releasable" surfaces daily
instead of at the next release. It surfaced, four days running, and three
releases went out anyway.

**`Fast-forward release branch` succeeds independently of `Release tag`**, so
the release publishes and `origin/release` advances even while the gate is red.
A green-looking release with a red gate is the observable state — which is how
this hid in plain sight.

The red gate had **two independent causes**, not one. Alongside the LLOC check,
`check-no-todo-registry` failed on six registered integration-coverage TODOs.
Those TODOs were honest deferrals owned by the supervisor-wrapup-citizenship
implementation; deleting the rows or clearing the fail lever would have hidden
the debt rather than discharged it. PR #536 supplied the real integration
coverage, and a synthetic-TODO positive control proved the detector still
failed when it should.

The LLOC diagnosis also demonstrated why acceptance cannot be a filed list.
The item named seven files; the release-tier command measured ten. After those
ten were decomposed, a newly grown 201-LLOC module became an eleventh population
member. PR #540 decomposed an enumeration and was closed unmerged; replacement
PR #550 measured the population, split the newly failing concern, propagated
source changes byte-for-byte to the plugin mirror, and made the exact command
green. The acceptance remained:

```
LIVESPEC_FAIL_IF_LLOC_SOFT_WARNINGS_EXIST=1 just check-no-lloc-soft-warnings
LIVESPEC_FAIL_IF_HEADING_COVERAGE_TODOS_EXIST=1 just check-no-todo-registry
```

Even both commands exiting zero are proxies. Only the next `Release tag`
workflow concluding `success` proves the release-tier execution path itself is
green again.

That bar has an asymmetric interpretation: `success` proves the whole workflow,
but `failure` does **not** by itself prove a release gate failed. The v0.17.1 run
had two attempts. On attempt 1, LLOC, TODO, and mutation all passed; only the
non-gate `export-telemetry` job failed on a transient Honeycomb connection
timeout, so the workflow still concluded failure. A maintainer retried the
failed job, telemetry passed in four seconds, and attempt 2 made the same run
conclude success. Read job conclusions and the attempt number, not only the
run's current conclusion: GitHub reports the latest attempt at run level, while
an earlier attempt can tell a materially different story.

## The trap to avoid on the fix

Each defect has an obvious remedy that is a weakening:

- `sf0`: dispatching it to the factory. The factory branch boundary drops
  `.github/workflows/` files and reports success — the fix would appear to land
  and change nothing.
- `dtl`: raising the LLOC soft ceiling or unsetting
  `LIVESPEC_FAIL_IF_LLOC_SOFT_WARNINGS_EXIST`. That converts a working detector
  into one that cannot fail, and ratifies three releases of drift rather than
  repaying it.
- `0kw`: deleting registered TODO rows or unsetting
  `LIVESPEC_FAIL_IF_HEADING_COVERAGE_TODOS_EXIST`. That erases the record or its
  release severity without writing the coverage it names.

All three are the same shape, and it is the shape this repo's threads keep
rediscovering: **making the check stop reporting is not making the condition go
away.**
