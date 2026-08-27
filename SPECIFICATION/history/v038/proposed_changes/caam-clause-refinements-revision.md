---
proposal: caam-clause-refinements.md
decision: accept
revised_at: 2026-08-27T02:24:19Z
author_human: thewoolleyman <chad@thewoolleyman.com>
author_llm: caam-anthropic-loop-planner
---

## Decision and Rationale

ACCEPTED AS PROPOSED, on an independent review that verified every claim against the shipped program rather than against the proposal's prose. All three refinements are wording; the program is not changed by any of them, and each was checked at a named call site. R1: the only endpoint the caam surface contacts is the USAGE endpoint (caam_usage.py:25, issued at :95); a tree-wide search finds no token-endpoint call anywhere, and refresh is CAUSED by running the agent in an isolated config sandbox (caam_warm.py:161,219,232). R2: caam_enforcement.py:99 computes fable_left as present-AND-under-limit, so spent (100.0) and absent (None) yield the identical boolean before any session is examined, and both reach the global reset at :164-167. R3: caam_warm.py:149-150 gates on a fixed per-account minimum interval (warm_retry_s, default 3600 at :33), the memo's ok field is never consulted as a gate, there is no count bound or blacklist, and every failure is logged at :160 -- the rate reading exactly.

ONE THING THE RECORD MUST CARRY, because the reviewer raised it unprompted and it qualifies the proposal's own Summary. R2 IS A CONFORMANCE REPAIR OF THE SPEC TEXT, NOT A SEMANTICS-NEUTRAL EDIT. The program is unchanged, which is what the proposal claims and what was verified. But the OLD clause, read strictly, required non-foreman sessions to be LEFT ALONE when the allowance was absent, while the program resets them. So the edit does change what the SPECIFICATION DEMANDS -- in the direction of what ships. The proposal's sentence 'This MUST NOT be read as widening' is accurate about the program and slightly overstated about the text, and accepted proposals are archived under history/vNNN/proposed_changes/, so that sentence lands in permanent history. Do not let it become the section's remembered meaning.

WHY THAT IS NOT A REJECTION, since the proposal invites rejection of any refinement a reviewer reads as a behaviour change. The old clause was INTERNALLY INCOHERENT rather than merely narrow: its foreman half keys on 'retains that allowance', which is false when the allowance is absent, while only its other-sessions half keyed on 'spent'. The two halves therefore disagreed with each other about the absent case. The Observation clause already establishes absence as a normal condition, and a test (tests/test_caam_session_discovery.py:430) already pins the program's labelling of absent as exhausted. R2 makes the halves agree. The absent case was also checked for flap risk and is NOT a disguised read failure: caam_anthropic_pass.py:191 exits before enforcement runs on a failed poll, so absent means a successfully-read response with no scoped limit.

SCOPE VERIFIED BY CONTROL, not by inspection. Three changed lines, no insertions or deletions, line count unchanged at 1553. Deleting the three lines from each file yields the same MD5 (815f0a5456b633e285d9539fa2303abd), reproduced independently by the decider. No sibling spec file quotes the old wording, so nothing downstream is stranded.

ACCEPTED DESPITE three non-blocking observations, recorded so they are not rediscovered as new. (1) R1 leaves a weaker second tension untouched in the same sentence: 'MUST perform read-only requests only' still stands while the keep-warm clause mandates a billable inference request against an idle account. In scope for a future refinement, not this one. (2) R3's appended clause sits oddly with the word 'backoff' it qualifies, since a fixed interval does not escalate; the appended clause is the more specific and later statement and is what an implementer will conform to. (3) R3 introduces a second em-dash into a sentence that already has one, which can read as a parenthetical pair that is not one; the misparse is self-correcting because the interior reading is ungrammatical. Cosmetic, and it is the proposal's own prescribed wording.

NOT VERIFIED, and named rather than glossed: the proposal cites 'carrier L5' and 'carrier X12', neither of which appears anywhere in the tree. They are presumably ledger work-items and were not queried by the read-only reviewer. This costs the decision nothing, because the code independently confirms both claims those carriers were cited to support.

## Resulting Changes

- spec.md

## Ratification Review

ratification_review: auto-spawn
reviewer_model: opus
reviewer_identity: opus
separate_reviewer: True
read_only: True
reviewed_at: 2026-08-27T02:21:50Z
verdict: NO BLOCKERS
proposal_stem: caam-clause-refinements
content_digest: bf8b91e43be52453bab4f3edc1c8f1f18f9f2efecb67ad7c7aca8cfc2678c3b8
