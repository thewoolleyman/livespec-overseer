---
topic: watch-set-held-repo-declaration-and-observability
author: claude-opus-4-8
created_at: 2026-08-31T05:28:16Z
spec_commitments:
  impl_followups:
    - id_hint: watch-set-held-repo-representation-and-surfacing
      description: |
        After this proposal is revised in, file the implementation child under plan epic overseer-zidpiu (work-item overseer-zidpiu.5's realization): parse a `holds` array in the watch-set declaration, exclude held repositories from the watch-set while recording them as a first-class held state, surface each held repository (with reason, declared_at, computed age, and review_by when set) on the status snapshot distinctly from a never-watched repository, and surface a repository declared in both repos and holds as a conflict. Repo change only; no further SPECIFICATION edit — do not mix tiers.
---

## Proposal: Held repositories are declared, unwatched, and observable

### Target specification files

- SPECIFICATION/spec.md
- SPECIFICATION/scenarios.md

### Summary

Give the watch-set declaration a first-class HELD state so a deliberately-unsupervised repository is DECLARED as held rather than represented by deleting its watch-set entry. A held repository stays unwatched exactly as today, but it becomes a recorded, observable fact the operation surfaces on the same operator surface that already reports supervised state — distinguishable from a never-watched repository and from an accidentally-removed one — and its age is surfaced so a hold that is never reviewed cannot hide.

### Motivation

Today a 'hold' on a watched repository is not a mechanism: it is the DELETION of the repository's entry from the watch-set declaration plus a human-only `//` comment. The daemon has no concept of a held repository, cannot report one, and cannot distinguish one from a repository that was never watched or one deleted by accident — absence is overloaded at least three ways (deliberate never-watched, temporary hold, accidental deletion), and only prose separates them. The measured consequence (work-item overseer-zidpiu.5): a repository held from 2026-08-24 ran every one of its sessions unsupervised with ZERO rows on the status snapshot and no attention item anywhere saying so, while the daemon was healthy throughout; a seat diagnosing why it was not restarted formed three hypotheses and all three were wrong, because the only evidence was a `//` comment in a hand-edited file. The hold was declared once, partially lifted the next day WITHOUT including this repository, and forgotten for days — the system was structurally incapable of reminding anyone. The spec section governing the watch-set declaration currently says only that an unadmitted entry is 'silently inert rather than an error'; it has no notion of a deliberately-held-yet-declared repository, which is the gap this proposal closes.

### Proposed Changes

Amend spec.md §"The watch-set declaration" to introduce a first-class HELD state, and add the covering scenarios to scenarios.md with their `tests/heading-coverage.json` links (co-edited atomically per spec.md §"Self-application").

Normative clauses to add:

1. A repository the operator wishes to keep unsupervised MUST be declared as HELD — a recorded entry carrying at minimum the repository path, a non-empty reason, and the timestamp at which the hold was declared — rather than by removing the repository's active watch-set entry. Representing a deliberate non-supervision by deletion alone MUST NOT be the mechanism, because deletion is indistinguishable from a never-watched or an accidentally-removed repository.
2. A held repository MUST NOT be admitted to the watch-set: its supervision behavior is unchanged — it is not watched, no track is discovered for it, and no session of it is restarted. Only its REPRESENTATION changes.
3. A repository MUST NOT be simultaneously an active watch-set entry and a held entry. The DECLARED held-set and the EFFECTIVE watch-set MUST NOT silently disagree: a repository declared in both MUST be surfaced as a conflict rather than silently resolved toward either reading.
4. The operation MUST surface each held repository on the same observability surface that already reports supervised state, as a HELD condition distinguishable from a never-watched repository (declared in neither the watch-set nor the held-set) and from a removed one. 'This repository is deliberately unsupervised' MUST be a fact the machine can state, not one that lives only in a configuration comment.
5. A held entry MAY carry an optional review-by date. Independently of whether one is set, the operation MUST surface the hold's AGE (declared-at to now) wherever it surfaces the held repository, so a hold that is never reviewed becomes more visible over time rather than persisting silently. Where a review-by date is set and has passed, that MUST be surfaced as well.

Scenarios to add to scenarios.md (Given/When/Then), each linked from tests/heading-coverage.json to the clause above it:

- "A held repository is declared and is not watched": Given a watch-set declaration whose held-set names a checkout that exists on disk and contains a plan directory, When the operation discovers tracks, Then no track is discovered for that repository and no session of it is restarted.
- "A held repository is surfaced distinctly from a never-watched one": Given one repository declared held and another named in neither the watch-set nor the held-set, When the operation writes its observability surface, Then the held repository appears as a held condition carrying its reason and declared-at, and the never-watched repository does not appear as held.
- "A repository declared both watched and held is surfaced as a conflict": Given a declaration naming one repository in both the watch-set and the held-set, When the operation resolves the watch-set, Then the disagreement is surfaced rather than silently resolved.
- "A hold's age is surfaced so an unreviewed hold cannot hide": Given a held entry whose declared-at is well in the past and which carries no review-by, When the operation surfaces the held repository, Then the hold's age is surfaced alongside it.

## Proposal: Wire shape for held watch-set entries and their surfacing

### Target specification files

- SPECIFICATION/contracts.md

### Summary

State the wire contract for the held state introduced in spec.md: how a held entry is carried in the hand-edited watch-set declaration file, and how held repositories appear on the status snapshot the daemon rewrites each tick. Keep the same lenient-parse, degrade-not-crash discipline the rest of that file already has.

### Motivation

spec.md gains a held state (companion proposal), but the daemon and any operator surface need a concrete, contract-level shape to read and write. The watch-set declaration is documented in contracts.md §"The watch-set declaration" as `{"repos": […]}`, parsed leniently (comments and trailing commas tolerated; an absent or unparsable declaration degrades to an empty watch-set with a warning). The status snapshot in the same section carries one row per evaluated track and is the surface on which supervised state is already reported — and the surface on which held repositories are invisible today. Both need a stated held shape so the behavior clauses in spec.md are realizable and gap-detectable.

### Proposed Changes

Amend contracts.md §"The watch-set declaration":

1. The declaration document MAY carry a `holds` array alongside `repos`. Each element is an object with REQUIRED string fields `repo` (the checkout path), `reason` (non-empty), and `declared_at` (an ISO-8601 UTC timestamp), and an OPTIONAL string `review_by` (an ISO-8601 date). The `holds` array MUST be parsed with the same leniency as the rest of this hand-edited file: comments and trailing commas are tolerated, and a hold element that is unparsable or missing a required field MUST degrade that ELEMENT to inert with a warning rather than crashing or discarding the whole declaration.
2. A repository named in `holds` MUST NOT be admitted to the watch-set even if it also appears in `repos`; a repository appearing in both MUST be surfaced as a declared/effective conflict per spec.md.

Amend contracts.md §"The status snapshot": the daemon MUST represent held repositories on the status snapshot as a distinct held representation — not as an evaluated-track row — carrying at minimum the `repo`, the `reason`, the `declared_at`, and the computed hold age; and `review_by` when the held entry carries one. A held repository MUST be distinguishable on the snapshot from a repository that is merely absent from the declaration.
