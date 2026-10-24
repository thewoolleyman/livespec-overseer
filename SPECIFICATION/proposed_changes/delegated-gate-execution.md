---
topic: delegated-gate-execution
author: claude-opus-5-5
created_at: 2026-10-24T22:01:02Z
---

## Proposal: The pre-push gate MAY be delegated to the fleet suite's remote executor without changing what it verifies

### Target specification files

- SPECIFICATION/non-functional-requirements.md

### Summary

Amend non-functional-requirements.md §"Constraints" so a pre-push MAY obtain the aggregate check target's verdict from the fleet enforcement suite's remote executor instead of running the aggregate on the pushing host. The amendment states the delegation properties this repository must hold: an opt-in in version-controlled configuration, local gating on a host without the executor credential, no automatic fallback on an absent verdict, and authority-reading checks run on the pushing host. Delegation changes WHERE the gate runs, never WHAT it verifies. Today the spec says the aggregate is the single local, pre-push and CI entry point, which becomes false the moment this repository opts in.

### Motivation

Plan delegated-gate-fleet-rollout (ledger epic livespec-dev-tooling-mvalxq in livespec-dev-tooling) rolls the delegated pre-push gate out so a push from the VPS gates as a k3s cluster Job instead of running the full local `just check` on the VPS. On 2026-10-24 the maintainer directed, through coordinator gitops-fleet-capacity-monitoring, that the gate be enabled on every livespec repository whose gate the cluster image can run. livespec-overseer is measured ready. Its origin/master gated as a cluster Job (gates/gate-livespec-overseer-bfzgn PASSED, 84 targets, 18:55-18:58Z, with the released v1.130.1 client). A branch-only opt-in push from the VPS also delegated and completed (gates/gate-livespec-overseer-f7fx8 PASSED on tree 3acf7ee6, 19:08-19:12Z). The authority member was skipped in the Job and run on the pushing host in both. What blocks the opt-in is this spec. non-functional-requirements.md §"Constraints" says the aggregate check target is "the single local, pre-push, and CI entry point", so an opt-in carrier has no governing clause to cite and would make the spec false. livespec closed the same gap at its v229 ("Delegated gate execution"). The maintainer accepted that clause's two departures from the 2026-09-08 delegated-gate ruling on 2026-10-23: authority-reading checks on the pushing host, and local gating on a host with no executor credential. This proposal adopts the same contract for this repository, citing it rather than restating it.

### Proposed Changes

Edit `SPECIFICATION/non-functional-requirements.md` §"Constraints".

**Edit 1.** Replace the clause ending of the pin-consuming-fleet-member item, "and the aggregate check target is the single local, pre-push, and CI entry point.", with:

> and the aggregate check target is the single entry point for local, pre-push, and CI runs. Where the repository has delegated its pre-push gate per the next item, a pre-push from a delegating host obtains that same aggregate's verdict from the remote executor against the pushed tree instead of running it on the pushing host. This changes WHERE the aggregate runs and MUST NOT change WHAT it verifies.

**Edit 2.** Insert a new item immediately after that one:

> - The repository MAY delegate its pre-push gate to the remote executor of the fleet enforcement suite's delegation client (livespec-dev-tooling `SPECIFICATION/contracts.md` §"Delegated pre-push gate"). When it does, it MUST conform to the delegation contract livespec ratifies in its `non-functional-requirements.md` **Delegated gate execution** (*The host*, *The tree*, *The set*, *The authority*, *The credential*, *The verdict*). For this repository that means:
>   - Delegation MUST be opted in by the repository's version-controlled configuration. It MUST be withdrawn only by a change to that configuration, never per push or per host. The gate MUST remain runnable on the pushing host by an explicit act whether or not delegation is opted in.
>   - A push MUST delegate only from a host that holds the credential authorizing it to submit to the executor. A host that holds none, such as a factory sandbox, MUST run the repository's gate recipe on that host without delegation. It MUST report that it gated locally.
>   - The pre-push recipe's path for a delegating host MUST run the delegation client in place of the aggregate, and MUST have no branch from the client's result to a local run of the gate. An absent verdict MUST refuse the push. It MUST NOT be treated as a pass, and MUST NOT be replaced by an automatic local run.
>   - A check that declares it reads an authorization held outside the tree MUST run on the pushing host, with that host's credentials, against the same tree. Its result MUST join the delegated verdict.
>   - The delegation client, its verdict handling and the scenarios that pin them belong to the fleet enforcement suite. This repository realizes only the opt-in and the recipe path.

No `## ` heading is added, changed or removed, so `tests/heading-coverage.json` needs no co-edit. No scenario is added to `scenarios.md`. The behaviour is the delegation client's, and its scenarios and tests live in the realizing repository, livespec-dev-tooling, per the cross-repo placement split.
