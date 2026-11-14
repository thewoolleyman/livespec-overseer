---
proposal: live-seat-record-survives-epic-writes.md
decision: accept
revised_at: 2026-11-14T15:13:04Z
author_human: Chad Woolley <thewoolleyman@gmail.com>
author_llm: claude-opus-5-5:herdr-overseer
---

## Decision and Rationale

Accepted unchanged. v108 states a load-bearing invariant declaratively: the live-seat record is held apart from the plan epic's own fields, so no write to the epic can alter or erase it. It has no BCP14 keyword and no scenario. That is the doctor-llm-subjective-behavior-coverage finding from the v107/v108 post-step phase. The proposal restates the sentence as a MUST without changing its meaning. It names the two writes that motivate it (a handoff entry and a next-action write; the beads CLI's --set-metadata rewrites the epic's whole metadata column). It adds one Given/When/Then scenario pinning the invariant, placed beside the other live-seat scenarios. The record's location, contents, writers, write moments and readers are unchanged, and the scenario's final step agrees with the atomic conditional write (a take from another machine still fails). legacy-coordinator-agent graded the proposal PASS on #3045, and the independent read-only sonnet ratification review found NO BLOCKERS against these exact resulting bytes. The new scenario heading gets an integration-tier TODO coverage row and a debt row owned by overseer-fnu5gl, the implementation item for the live-seat record store.

## Resulting Changes

- spec.md
- scenarios.md

## Ratification Review

ratification_review: auto-spawn
reviewer_model: sonnet
reviewer_identity: sonnet
separate_reviewer: True
read_only: True
reviewed_at: 2026-11-14T15:13:03Z
verdict: NO BLOCKERS
proposal_stem: live-seat-record-survives-epic-writes
content_digest: 2cca0fc17f410b625b56a6cc800863fc3fae146476061c5ee51e63284af719c5
