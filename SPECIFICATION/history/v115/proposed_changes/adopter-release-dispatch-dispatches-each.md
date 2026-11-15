---
topic: adopter-release-dispatch-dispatches-each
author: claude-opus-5-5
created_at: 2026-11-15T03:11:39Z
---

## Proposal: adopter-release-dispatch resolves each adopter's owner and authenticates per owner

### Target specification files

- SPECIFICATION/non-functional-requirements.md

### Summary

Add three MUST bullets to non-functional-requirements.md §"Contracts", after the disarm-on-hold-label bullet, so the adopter release dispatch workflow resolves each adopter's repository by the fleet-wide `<adopter.owner or adopter_owner or owner>/<repo>` rule, dispatches `sibling-released` to that resolved repository, mints one App installation token per resolved owner from the App already installed there, and reports an adopter whose owner has no App credential as not authorized (named and counted) while any other dispatch failure fails the run. No new heading is added.

### Motivation

Work item overseer-j4ejek. `.github/workflows/adopter-release-dispatch.yml` mints its App installation token for the repository's own owner, reads only each adopter's `repo` from the fleet manifest, and dispatches `sibling-released` to the repository's own owner joined with that `repo`. After this repository transfers to livespec-ai, its own owner owns no adopter, so every dispatch would target a repository that does not exist, and the workflow's 403/404 branch would report it as "not authorized" and exit 0: the release fan-out would stop with a green run. livespec v247 (livespec#3242) made the adopter resolution `<adopter.owner or adopter_owner or owner>/<repo>` binding on every manifest consumer, and requires every consumer to resolve by it before the manifest sets `adopter_owner`. A measurement on 2026-11-15 (recorded on overseer-j4ejek) found that livespec-ai-factory-bot is a private App installed only on livespec-ai, so it cannot reach the eleven thewoolleyman adopters; thewoolleyman-factory-bot is installed on thewoolleyman for all repositories. mi-homelab has no App installed today and is already reported as not authorized. The decided route, endorsed by legacy-coordinator-agent, mints one token per resolved owner from the App already installed there. Nothing in this spec states the workflow's behaviour today, which is why the item was classified at spec-change tier. This blocks the stale-base org cutover go/no-go on 2026-11-16.

### Proposed Changes

In SPECIFICATION/non-functional-requirements.md §"Contracts", append the following bullets immediately after the bullet that begins "This repository carries `.github/workflows/auto-enable-merge.yml`" (the last bullet of that section). No heading is added or renamed.

- This repository's `.github/workflows/adopter-release-dispatch.yml` MUST
  resolve each adopter's repository from livespec core's fleet manifest as
  `<adopter.owner or adopter_owner or owner>/<repo>`: the adopter entry's own
  `owner` when it carries one, else the manifest's top-level `adopter_owner`
  when the manifest carries one, else the manifest's top-level `owner`. This is
  the fleet-wide adopter resolution rule livespec ratified in its v247
  (livespec#3242). The workflow MUST dispatch `sibling-released` to that
  resolved repository, and MUST NOT dispatch it to the repository's own owner
  joined with the adopter's `repo`.
- The workflow MUST authenticate each dispatch per resolved owner, with a
  GitHub App installation token minted from the App already installed on that
  owner. For an adopter whose resolved owner is `thewoolleyman`, that App is
  `thewoolleyman-factory-bot`, whose credential the workflow reads from a
  second secret pair, `ADOPTER_APP_ID_THEWOOLLEYMAN` and
  `ADOPTER_APP_PRIVATE_KEY_THEWOOLLEYMAN`. For an adopter whose resolved owner
  is `livespec-ai`, it is the repository's own App, read from `APP_ID` and
  `APP_PRIVATE_KEY`.
- An adopter whose resolved owner has no installed App that the workflow
  holds a credential for MUST be reported in the run log as not authorized,
  naming the adopter, and MUST be counted in the run summary; such an adopter
  MUST NOT be skipped silently. A dispatch that fails for any other reason
  MUST fail the run, naming the adopter.

The evidence for these bullets is a run of the released workflow on GitHub Actions against the real adopter repositories (host-captured), as overseer-j4ejek's Definition of Done states.
