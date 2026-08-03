---
topic: fail-soft-render-prohibition-scenario
author: claude-opus-5
created_at: 2026-08-03T00:18:00Z
---

## Proposal: The fail-soft rendering prohibition gets the scenario it has never had

### Target specification files

- SPECIFICATION/scenarios.md

### Summary

spec.md §"Fail-soft posture" ratified a rendering PROHIBITION in v004: the daemon MUST NOT render an acting status — a restart-in-progress or any status implying the act will occur — for a track whose act is structurally impossible, and the rendered state names the dead end instead. The v004 scenario set covers the SURFACING of such a declaration and covers the NO-ACT, but nothing covers what is rendered. This proposal adds the one scenario that binds the prohibition itself, plus its behavior-coverage row.

### Motivation

Found by the post-step LLM doctor phase during the foreman proposed-changes pass (2026-08-02; finding 10 in that report), and filed in the ledger as overseer-n7xx67, whose acceptance names this proposal as its landing path.

The gap matters because the prohibition and the surfacing requirement sit in the SAME sentence-group and read as one rule, so covering the surfacing feels like covering both. It is not: a daemon could surface the uncertifiable declaration with full coordinates — satisfying every covered clause — and still paint `restarting` on that row. That renders a promise the interlock will never keep, which is precisely the operator-facing lie the clause was added to forbid. An uncovered prohibition is also the shape most likely to be regressed by a well-meaning render change, because nothing fails when it goes.

This is a COVERAGE addition, not a semantic change. No ratified clause is edited, weakened, or re-scoped; the normative text of §"Fail-soft posture" is untouched.

### Proposed Changes

EDIT 1 — scenarios.md, one new scenario placed with the other fail-soft scenarios:

## Scenario: A structurally impossible act is never rendered as in progress

Given a track carrying a standing `ready` declaration with no open supervision round for it to answer

When the daemon renders the track table

Then no restart-in-progress status and no status implying the act will occur is rendered for that track

And the rendered state names the reason the act is structurally impossible

EDIT 2 — tests/heading-coverage.json (outside the spec target; the atomic behavior-coverage co-edit): add the row linking `## Fail-soft posture` in spec.md to the test that pins the prohibition, with a reason stating that it pins the RENDERING half rather than the surfacing half. The existing `## Fail-soft posture` row pins the unknown-context clause and is retained unchanged — this is an additional row against the same heading, because a heading carrying several distinct clauses needs a row per load-bearing clause rather than one row standing in for all of them.

Composition: self-contained, and deliberately narrow. It does not touch the attention-surface membership that `attention-ownership-superset` amends, and it does not depend on any foreman slice — the clause it covers has been ratified since v004 and the gap is present today regardless of whether the foreman ships. It composes with `gap-invisible-clauses-to-must-form` without conflict: that proposal raises indicative clauses to MUST form and this one adds a scenario against a clause already in MUST NOT form.
