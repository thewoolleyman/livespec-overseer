---
proposal: caam-quota-resets.md
decision: accept
revised_at: 2026-10-15T03:18:39Z
author_human: Chad Woolley <thewoolleyman@gmail.com>
author_llm: claude-opus-5-5
---

## Decision and Rationale

Accepted as amended. The proposal adds four rules to the account-rotation section: quota resets are observed and reported in provider-agnostic terms (a client-declined read shows as unreadable); a scheduled pass claims a reset rather than holding at an exhausted window when no candidate survives and the window does not self-reset within the 60-minute self-reset horizon, narrowest reset first; a reset lapsing within the 24-hour expiry horizon is claimed when it refills at least the eligibility margin, without switching; and every claim is bounded by the existing rules (scheduled-only, under the decision lock, one per account per pass, idempotent claim identifier persisted outside the overwritable cache, reported). It is revised after v056 (caam-capacity-aware-rotation), whose refusal and fast-drain triggers it names. At the freeze driver's request (Fable review) it states that a refusal-held account still rotates while any candidate survives, including under the capacity-test release, and claims only where none survives; a first independent opus review found that ending the refusal hold on the claim's re-read conflicted with v056's REFUSAL-HELD definition and would be re-imposed on the next pass, so the proposal now amends that definition: a claim settles the refusal only where the provider reports the reset as used by it and the re-read shows the window fully replenished (a provider-refused claim settles nothing, and no claim settles a rate-limit refusal), the settle time is stored, and the cost of losing it is bounded in Durable store. A separate Fable review on 2026-10-15 returned APPROVE and added one sentence (a lapse claim whose transport fails leaves the rotation decision unchanged and is retried with its recorded identifier); its re-review of the amended bytes blocked a settle rule that did not require the claim to have succeeded, which the success condition above resolves; a third independent opus review found the lapse clause could claim on a refusal-held active account that still had a candidate and so cancel the required rotation, so that rotation is now decided on pre-claim readings and the lapsing reset claimed on the account left; a rate-limit-only refusal causes no exhausted-window claim; the independent opus reviewer recorded below found NO BLOCKERS on these exact resulting bytes. Decision ownership: revise_decision_mode delegated; the human decision is the maintainer's recorded authorization of 2026-10-15 00:08Z (livespec-dev-tooling-dfixhe: the freeze driver may approve spec revises on the maintainer's behalf after a Fable subagent review), exercised by the freeze driver's go for this revise as v057. Code half: overseer-33kyxp under plan caam-quota-resets (epic overseer-pv53ri), held by the 2026-10-14 factory stability freeze.

## Resulting Changes

- contracts.md
- scenarios.md
- spec.md

## Ratification Review

ratification_review: auto-spawn
reviewer_model: opus
reviewer_identity: opus
separate_reviewer: True
read_only: True
reviewed_at: 2026-10-15T03:18:36Z
verdict: NO BLOCKERS
proposal_stem: caam-quota-resets
content_digest: 7179c1e3c9d10b9fad911009ad17851284e48cd8d4beff1e33a58ab73135ea14
