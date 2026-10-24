---
proposal: factory-routing-retire-legacy.md
decision: accept
revised_at: 2026-10-24T06:20:28Z
author_human: Chad Woolley <thewoolleyman@gmail.com>
author_llm: claude-opus-5-5
---

## Decision and Rationale

Fleet capacity coordinator ruling (2026-10-24): hp-xubuntu's legacy Fabro instance is being retired, so the committed factory table stops declaring `legacy`. The requirement existed to keep legacy-pinned open items resolvable; the petri-factory-on-gmktec seat triaged every such item fleet-wide and none needs a run read from hp, and a pin naming an undeclared factory falls back to `default_factory`. The same change removes the entry from .livespec.jsonc and updates the conformance tests. Independent read-only ratification review (opus) of the exact final bytes: NO BLOCKERS on digest f55fd086.

## Resulting Changes

- constraints.md

## Ratification Review

ratification_review: auto-spawn
reviewer_model: opus
reviewer_identity: opus
separate_reviewer: True
read_only: True
reviewed_at: 2026-10-24T06:18:47Z
verdict: NO BLOCKERS
proposal_stem: factory-routing-retire-legacy
content_digest: f55fd086ad1f50e31899f59062bad66e7fb81ff5923e2a3173d25b2e5434c2af
