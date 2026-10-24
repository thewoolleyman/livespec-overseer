---
proposal: delegated-gate-execution.md
decision: modify
revised_at: 2026-10-24T22:09:37Z
author_human: Chad Woolley <thewoolleyman@gmail.com>
author_llm: claude-opus-5-5
---

## Decision and Rationale

Accepted with modifications. livespec-overseer's NFR §"Constraints" said the aggregate check target is the single local, pre-push and CI entry point. That becomes false once the repository opts in to the delegated pre-push gate. Overseer is measured ready: master gated as cluster Job gates/gate-livespec-overseer-bfzgn and a branch-only opt-in leg as gates/gate-livespec-overseer-f7fx8, both PASSED on 2026-10-24. The clause adopts, by citation, the contract livespec ratified at v229 (§"Enforcement-suite invocation", Delegated gate execution) and the delegation client's contract (livespec-dev-tooling §"Delegated pre-push gate"), and states the obligations this repository's opt-in and recipe must meet.

DESIGN-RECORD DEPARTURE, ACKNOWLEDGED. The adopted contract departs from the maintainer's 2026-09-08 delegated-gate ruling (design record of plan k3s-on-gmktec-for-vps-usage, epic livespec-sab5gn, research/003) in exactly two classes: (1) a check that reads an authorization held outside the tree runs on the pushing host and joins the delegated verdict; (2) a host holding no executor credential gates locally and says so. The maintainer accepted both explicitly on 2026-10-23 (recorded on ledger epic livespec-dev-tooling-mvalxq, ratified in livespec v229). This clause adopts that accepted departure for livespec-overseer and adds no new one. The maintainer's 2026-10-24 direction to enable the delegated gate on every livespec repository that can run it covers this repository.

NO SCENARIO IN THIS REPOSITORY (split i). The behaviour is the delegation client's, and its scenarios and their tests live in the realizing repository, livespec-dev-tooling, per the cross-repo placement split (iii). This repository realizes only configuration and one recipe branch, which its opt-in carrier verifies with host-captured legs. The neighbouring NFR constraints carry no scenarios either.

## Modifications

M1 (independent ratification review, blocker B1): the §"Delegated pre-push gate" citation failed doctor-no-cross-spec-reference. .livespec.jsonc external_references now allowlists it, committed in the same change (outside SPECIFICATION/, so not in resulting_files). M2 (blocker B1a): the livespec citation is now §"Enforcement-suite invocation", clause Delegated gate execution, allowlisted under "livespec". M3: Edit 1 adds "save the checks the next item places on the pushing host, and except where an explicit local run has already authorized the tree", matching The set and The verdict. M4: the absent-verdict sentence gains livespec's qualifier, "where no explicit run of the entire gate recipe on the pushing host without delegation has authorized it". M5: the authority item adds "A pushing host that cannot evaluate such a check MUST refuse the push as that check's failure", from The authority.

## Resulting Changes

- non-functional-requirements.md

## Ratification Review

ratification_review: auto-spawn
reviewer_model: opus
reviewer_identity: opus
separate_reviewer: True
read_only: True
reviewed_at: 2026-10-24T22:08:52Z
verdict: NO BLOCKERS
proposal_stem: delegated-gate-execution
content_digest: b8a478d453310d8bf5c212ccbf942c1a4770c4de3bcbd240626dd52c5fd0473a
