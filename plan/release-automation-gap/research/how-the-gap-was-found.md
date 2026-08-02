# How the gap was found, and why it stayed invisible

Recorded 2026-08-02. The measurements are cheap to re-run and the *reasoning* is
what is expensive to redo — that is why this note exists.

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

## The measurement that settled it

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

## The trap to avoid on the fix

Both halves have an obvious remedy that is a weakening:

- `sf0`: dispatching it to the factory. The factory branch boundary drops
  `.github/workflows/` files and reports success — the fix would appear to land
  and change nothing.
- `dtl`: raising the LLOC soft ceiling or unsetting
  `LIVESPEC_FAIL_IF_LLOC_SOFT_WARNINGS_EXIST`. That converts a working detector
  into one that cannot fail, and ratifies three releases of drift rather than
  repaying it.

Both are the same shape, and it is the shape this repo's threads keep
rediscovering: **making the check stop reporting is not making the condition go
away.**
