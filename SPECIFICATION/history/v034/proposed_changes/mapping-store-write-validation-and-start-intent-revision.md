---
proposal: mapping-store-write-validation-and-start-intent.md
decision: modify
revised_at: 2026-08-26T03:22:18Z
author_human: thewoolleyman <chad@thewoolleyman.com>
author_llm: claude-opus-5
---

## Decision and Rationale

Accepted with modifications required by three rounds of independent ratification review. Round 1 blocked twice: the write-validation clause as filed pointed validation at the durable-key contract, which carries the ratified sentence that epic is REQUIRED for any track whose session may be restarted, so read literally it demanded refusing an assignment row with no epic while ratified spec.md and contracts.md both require that write to succeed and prescribe accept-and-handle; and the two new start-intent texts contradicted each other for a spawn that never returns, demanding a record carrying the error from a surface that cannot write one, with the satisfiable leg uncovered by any scenario. Round 2 confirmed both repairs on the text and blocked once more: the discriminating obligation of the first repair had no scenario, because the sole refusal scenario was row-phrased and a stripped row satisfies the row contract, so an implementation validating the resulting row would have passed every scenario while violating the central obligation. Round 3 returned NO BLOCKERS against these exact bytes. The filed proposal text is left unchanged as the record of what was proposed; the modifications below are what is ratified.

## Modifications

One: the validation predicate is stated over the WRITE — the row as it stands before together with the row as it would stand after — rather than over the resulting row, with an explicit carve-out that an ABSENT epic CONFORMS and that a write introducing such a row MUST be accepted, and with refusal targeted at REMOVING or REPLACING a recorded epic or recording an epic that is not a ledger epic id. The REQUIRED-for-restart sentence is glossed as a precondition for RESTARTING a track, never for WRITING its row. The transition framing is load-bearing rather than stylistic: an epic-stripping rewrite yields a row indistinguishable from a conforming never-assigned one, so a row-only predicate cannot refuse it and the amendment would have protected nothing. Two: removing the ROW ENTIRELY is stated not to be removing its epic, so the ratified garbage collection of archived-or-deleted rows is unaffected. Three: the start-intent obligation splits its two failure cases. A spawn that fails and RESOLVES: the surface MUST amend the intent record with the failure and its error. A spawn that does NOT return: the record stands with no outcome, and an intent record carrying no outcome MUST be read as ATTEMPTED-AND-FAILED, never as live work and never as evidence that no attempt was made. No obligation is placed on a surface that no longer exists to write after its own death. The contracts.md companion states the same rule from the reader side. Four: three scenarios are added beyond those filed — a write that STRIPS a recorded epic refused though the resulting row conforms, a write that REPLACES a recorded epic with a different id refused independently of malformedness, and a spawn that fails and returns having its record amended with the error — each with its heading-coverage entry. The first two exist so the suite can fail for the amendment central obligation, which it previously could not. Five: the heading-coverage entries are NOT carried in resulting_files[]. The revise CLI resolves every resulting_files[].path as spec_target / path and requires the target to exist under the spec target, so tests/heading-coverage.json — which lives outside that tree — cannot ride the payload at all. Those entries land as an ordinary file edit in the same commit. This is a tooling-boundary split, not a content change: independent review confirmed the post-change repository state is byte-identical either way.

## Resulting Changes

- contracts.md
- spec.md
- scenarios.md

## Ratification Review

ratification_review: auto-spawn
reviewer_model: fable
reviewer_identity: fable
separate_reviewer: True
read_only: True
reviewed_at: 2026-08-26T03:21:50Z
verdict: NO BLOCKERS
proposal_stem: mapping-store-write-validation-and-start-intent
content_digest: ea27e6cb476187639aa43b377080655a1562008216fc8d248c5654ad20e316a8
