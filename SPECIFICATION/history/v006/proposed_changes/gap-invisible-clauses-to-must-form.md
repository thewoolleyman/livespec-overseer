---
topic: gap-invisible-clauses-to-must-form
author: claude-fable-5
created_at: 2026-07-30T10:12:30Z
---

## Proposal: Raise the four gap-invisible ratified clauses to literal MUST form

### Target specification files

- spec.md
- contracts.md

### Summary

Reword four already-ratified v003 obligations — blocked-declaration age-band escalation, the pair nudge with its bounded busy exception, the -supervisor name reservation, and the canonical-state-path rule — into literal BCP14 MUST/MUST NOT form, with no semantic change, so the MUST-keyed mechanical gap detector emits candidates for them and their gap-ledger echo stops being vacuous.

### Motivation

The fleet's detect-impl-gaps detector emits candidates only from sentences carrying the literal token MUST. Four obligations ratified in v003 are written in indicative, RESERVED, or only-when voice and therefore produce no gap id at all, making the epic's gap-ledger closure echo vacuously true for slices overseer-4xfmez.4 and .6 and for .5's reservation and canonical-path halves (measured in the archived research note plan/archive/background-shell-supervision-liveness/research/untracked-obligation-closure.md, items U1-U4). This filing is remedy (a) of that note, directed by the maintainer on 2026-07-30 at epic close. The obligations themselves are implemented, tested, and live; only their detector visibility changes.

### Proposed Changes

Four wording-only edits. Each rewrites an already-ratified v003 obligation into literal BCP14 MUST form with NO semantic change — behavior, guards, and scope are byte-for-byte intent-identical; only the normative voice changes so the MUST-keyed gap detector emits candidates for these clauses. No scenario is added or changed: every behavior below is already ratified and already carried by the scenarios, tests, and heading-coverage rows its implementing slice (overseer-4xfmez.4/.5/.6) landed atomically.

EDIT 1 — spec.md, section "Notify, never block", the age-band sentence. Replace: "Alerts are edge-triggered — one line when a track enters a condition, not one per cycle, plus at most one further line per crossed age band for a standing human-wait, a declared block that persists re-reporting on a small set of rising age boundaries, with a re-declaration starting those bands afresh — and the condition is re-derived from live state on every cycle, so an alert stops on its own once the human acts." With: "Alerts MUST be edge-triggered — one line when a track enters a condition, not one per cycle. A standing human-wait — a declared block that persists — MUST be re-reported at most once per crossed rising age boundary, on a small set of such bands, and a re-declaration MUST start those bands afresh. The condition MUST be re-derived from live state on every cycle, so an alert stops on its own once the human acts."

EDIT 2 — spec.md, section "The keep-going nudge", the pair-nudge paragraphs. (a) Replace "the daemon pastes ONE nudge into the SUPERVISOR, because the supervisor owns direction for the pair. The message names the stall and its duration, names the worker's coordinates, and offers exactly two honest outs:" with "the daemon MUST paste ONE nudge into the SUPERVISOR, because the supervisor owns direction for the pair. The message MUST name the stall and its duration, MUST name the worker's coordinates, and MUST offer exactly two honest outs:". (b) Replace "A pane's displayed TEXT is never progress evidence" with "A pane's displayed TEXT MUST never count as progress evidence". (c) In the bounded-exception paragraph, keep the existing MAY and replace "and only then — at a verified empty and settled input prompt, never while the session is generating, never over a gate or a declared block, never while a round is open or a fresh acknowledgement stands, and only for a runtime whose empty input state is positively verifiable. A runtime whose input box cannot be verified empty is never pair-nudged" with "and only then — at a verified empty and settled input prompt. It MUST NOT land while the session is generating, over a gate or a declared block, or while a round is open or a fresh acknowledgement stands, and it MUST land only for a runtime whose empty input state is positively verifiable. A runtime whose input box cannot be verified empty MUST never be pair-nudged". (d) Replace "The nudge fires at most once per stall episode." with "The nudge MUST fire at most once per stall episode." (e) Replace "the daemon skips the paste and surfaces the pair to the operator, naming both panes" with "the daemon MUST skip the paste and MUST surface the pair to the operator, naming both panes".

EDIT 3 — spec.md, section "Session-name derivation", the reservation sentence. Replace: "No worker entity may be derived, registered, or accepted under a session name ending in `-supervisor` — compared case-insensitively — by discovery, by the cross-repository collision qualifier, or by any operator command; a plan directory or request that would produce one is refused and surfaced by name." With: "A worker entity MUST NOT be derived, registered, or accepted under a session name ending in `-supervisor` — compared case-insensitively — by discovery, by the cross-repository collision qualifier, or by any operator command; a plan directory or request that would produce one MUST be refused and surfaced by name."

EDIT 4 — contracts.md, section "The state file", the canonical-path bullet. Replace: "A declaration is honored for an ACT only when its file's canonicalized path equals that entity's canonical state path — no symlinked parent directories, no symlinked file — compared against an identically canonicalized repository root, so a legitimately symlinked checkout still passes. An aliased path is surfaced by name and treated as NO declaration, so one entity's write can never satisfy another entity's authorization." With: "A declaration MUST NOT be honored for an ACT unless its file's canonicalized path equals that entity's canonical state path — no symlinked parent directories, no symlinked file — compared against an identically canonicalized repository root, so a legitimately symlinked checkout still passes. An aliased path MUST be surfaced by name and treated as NO declaration, so one entity's write can never satisfy another entity's authorization."

