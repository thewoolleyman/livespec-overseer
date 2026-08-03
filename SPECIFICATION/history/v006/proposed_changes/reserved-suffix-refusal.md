---
topic: reserved-suffix-refusal
author: claude-fable-5
created_at: 2026-08-02T06:48:50Z
---

## Proposal: -foreman joins the reserved suffixes; refusal binds the derived name and adoption

### Target specification files

- SPECIFICATION/spec.md
- SPECIFICATION/scenarios.md

### Summary

spec.md §"Session-name derivation" reserves -supervisor and mandates refusal of any derivation that would produce it. This proposal (1) adds -foreman as a second reserved suffix with the same case-insensitive rules, (2) restates the refusal in literal MUST NOT form bound explicitly to the DERIVED name — including the cross-repository collision qualifier's repo-slug-topic form — so the existing implementation gap (a topic-level warning that lets the collision branch derive a reserved name unchecked) cannot survive a literal reading, and (3) extends refusal to ADOPTION: a live session whose registry name carries a reserved suffix is never adopted as a worker.

### Motivation

External review findings O1/O2 (plan/foreman/research/review-findings.md, both independently re-verified): plan/foreman/ is a discovered topic in a watched repo, adoption keys on registry names, and topic foreman under the collision qualifier derives exactly livespec-overseer-foreman — the mandated foreman session name. The shipped tmux_id only WARNS on a reserved topic and never re-checks the derived form; that -supervisor gap is filed as overseer-jgqw7d, and ledger slice overseer-z5fo4y.5 (depending on it) implements the -foreman half this proposal ratifies.

### Proposed Changes

EDIT 1 — spec.md §"Session-name derivation": the reserved-suffix set becomes -supervisor (pair members) and -foreman (the per-repository foreman surface), both compared case-insensitively.

EDIT 2 — spec.md, same section, the refusal restated in literal MUST NOT form bound to the RESULT of derivation, not only the inbound topic: "A worker entity MUST NOT be derived, registered, or accepted under a session name ending in a reserved suffix; the check MUST be applied to the final derived name — including the repo-slug-qualified form the cross-repository collision qualifier produces — and the offending derivation MUST be refused and surfaced by name, never reduced to a warning and never silently skipped." (Silently hiding a reserved-named plan directory would mask a legitimate plan rather than protect it.) This wording deliberately COMPOSES with the pending proposal gap-invisible-clauses-to-must-form (its EDIT 3 raises this same sentence to MUST NOT form): whichever is accepted first, the other applies on top without reverting the voice — if that proposal is accepted, this EDIT re-lands its MUST NOT sentence extended with the derived-name binding and the second suffix; it never reintroduces the indicative voice.

EDIT 3 — spec.md, adoption: the daemon MUST refuse to adopt a live session whose registry name ends in a reserved suffix, so a foreman or supervisor session can never be captured as a plan-thread worker, wrapped up, nudged, or respawned into a plan handoff.

EDIT 4 — scenarios.md, two new scenarios: (a) Given the topic foreman discovered in two watched repositories, When the collision qualifier derives session names, Then the derivation is refused and surfaced by name and no session name is produced; (b) Given a live session registry-named repo-slug-foreman whose cwd is a watched repository holding a plan topic of the same stem, When adoption runs, Then the session is not adopted and no alarm row is manufactured for it.

EDIT 5 — tests/heading-coverage.json (outside the spec target; the atomic behavior-coverage co-edit): link the new clauses to the two scenarios.

Composition: self-contained; overseer-jgqw7d (ledger) implements the refusal mechanism this ratifies, and foreman-scope-governed's naming-contract entry points at these clauses.
