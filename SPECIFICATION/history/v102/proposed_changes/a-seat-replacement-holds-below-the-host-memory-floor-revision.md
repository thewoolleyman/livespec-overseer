---
proposal: a-seat-replacement-holds-below-the-host-memory-floor.md
decision: accept
revised_at: 2026-11-13T17:26:56Z
author_human: Chad Woolley <thewoolleyman@gmail.com>
author_llm: claude-opus-5-5:herdr-overseer
---

## Decision and Rationale

Accepted unmodified after an independent read-only sonnet ratification review reporting NO BLOCKERS, and a coordinator grade of PASS WITH ONE FIX (FIX 1, per-host floor entries, applied at 6280dd04 before this review). Ratifies the behaviour overseer-uzvcbn.23 will implement: before every seat replacement the daemon reads MemAvailable and memory PSI and holds the replacement (declaration and round preserved, one event on entry and one on release) while the host is below the floor read from its own rendered /etc/livespec/host-load-floor.json. Reviewer non-blocking notes recorded for the implementation item: the `restart-held-by-memory-floor` entry/release events go to the daemon's existing event history (the word 'journal' names no new store); the absent-file no-floor carve-out is deliberate and visible; the hold's release event also fires when the track stops being a ready hold (declaration expiry or session change); preserving the declaration does not pause its ordinary stale-declaration expiry; the reading's bound is an implementation constant; impl tests should cover the pressure, absent-file and unreadable-file cases the normative text specifies.

## Resulting Changes

- spec.md
- scenarios.md

## Ratification Review

ratification_review: auto-spawn
reviewer_model: sonnet
reviewer_identity: sonnet
separate_reviewer: True
read_only: True
reviewed_at: 2026-11-13T17:20:30Z
verdict: NO BLOCKERS
proposal_stem: a-seat-replacement-holds-below-the-host-memory-floor
content_digest: 7072ad6ae8fb54007e09be09ea59fb5a0baea2b887101f18eb88b834724d177c
