# Decision prep — slice-4 upstream one-liners + tvko3z unit-3 home

Prepared 2026-07-24 by the cutover-and-shipping planning session so each
remaining maintainer touch is a cheap yes/no. Anchor texts re-verified
against the target repos' checkouts on 2026-07-24 (re-verify FINDs before
filing — live docs drift).

## Packet A — livespec core one-liner (`NFR:175`)

Target: `livespec` `SPECIFICATION/non-functional-requirements.md`,
§"Planning Lane guidance" → the "**The planning thread.**" paragraph
(line 175 at design time; the section is explicitly NON-normative on
core's contract, so this is a pattern-level sentence, not a new core
requirement). Route: `/livespec:propose-change` in livespec core, then
the maintainer's `/livespec:revise`.

FIND (end of the paragraph's second sentence):

> Only one resumption point may be active per topic; a young thread MAY
> be research-only.

ADD immediately after it (wording keeps the paragraph's "two facets"
literally true — the charter is a supervision artifact BESIDE the two
planning facets, not a third planning facet):

> Beside these two facets, a supervised thread MAY carry the reserved
> filename `plan/<topic>/supervisor-handoff.md` — the durable supervisor
> charter, not a resumption point, created only as an attended, reviewed
> repository change through the repo's own commit discipline (the
> unattended supervision daemon never writes the plan tree; the shipped
> realization is `livespec-overseer`'s attended `supervise-plan` skill).

Design constraint honored: slice 4 is deliberately LAST so the sentence
describes something that EXISTS — `supervise-plan` shipped
(livespec-overseer PR #49) and has two live exercises
(livespec-overseer PR #54, livespec core PR #1717).

## Packet B — orchestrator one-liner (`contracts.md` thread store)

Target: `livespec-orchestrator-beads-fabro` `SPECIFICATION/contracts.md`,
§"The `plan/<topic>/` thread store". Route:
`/livespec:propose-change` in that repo, then its `/livespec:revise`.

FIND:

> A young thread MAY be research-only. A root `research/` tree MUST NOT
> exist.

REPLACE WITH:

> A young thread MAY be research-only. Beside the two facets, a
> supervised thread MAY carry the reserved filename
> `plan/<topic>/supervisor-handoff.md` — the durable supervisor charter,
> authored only as an attended, reviewed repository change (the
> Control-Plane `supervise-plan` skill shipped by `livespec-overseer`);
> it is NOT a handoff, so the one-resumption-point rule is unaffected. A
> root `research/` tree MUST NOT exist.

## tvko3z unit-3 memo — the factory-success-rate-remediation charter home

**Recommendation: migrate the charter into the ORCHESTRATOR repo's
archived thread** as
`plan/archive/factory-success-rate-remediation/supervisor-handoff.md`
(final tmp/ text verbatim plus a one-line provenance header), via that
repo's worktree → PR → rebase-merge, then retire the two tmp/ files with
that track's supervisor's ack.

Evidence (measured 2026-07-24, after the thread closed):

- The track's supervised session runs in
  `/data/projects/livespec-orchestrator-beads-fabro` (its own charter
  header §0), and the overseer daemon's mapping row for the track was
  `livespec-orchestrator-beads-fabro::factory-success-rate-remediation`
  (archive-GC'd 2026-07-24T17:00:48Z on epic close). The thread's OWNING
  repo is the orchestrator — the tvko3z item text's premise
  ("worktree → PR → merge in livespec core for the two tmp/ charters")
  is WRONG for this charter and needs a correcting edit when the block
  is resolved. The tmp/ FILES sit under core's `tmp/` only because the
  supervisor process ran from there.
- The thread is CLOSED and ARCHIVED TODAY: epic `bd-ib-cvgjop` closed,
  orchestrator PR #934 (commit `e868277`) moved the thread to
  `plan/archive/factory-success-rate-remediation/` (handoff.md,
  grooming-cut, research/ — no supervisor charter). The final tmp/
  charter (rewritten ~12:35Z) declares "CAMPAIGN COMPLETE … No active
  supervision loop remains; this file is the record."
- `supervise-plan` correctly does NOT apply: its HALT precondition 4
  requires a live `plan/<topic>/` directory and the skill targets live
  threads. An archived-thread charter migration is a plain records PR —
  the design note's own "the third is already durable in core
  `plan/archive/`" establishes archived-thread charters as a legitimate
  durable home.

Options considered: (1) archive-record migration as above —
RECOMMENDED; (2) recreate a live `plan/factory-success-rate-remediation/`
dir to satisfy the skill — inverts tool/record, the campaign is over;
(3) leave in tmp/ — perpetuates the durability defect tvko3z exists to
close.

The ask, when ruling: resolve tvko3z's needs-human block for this unit
(the archive-record migration + the item-text premise correction), name
the executor (this planning session can, as attended cross-repo work),
and the fleet-pin-propagation tmp/-prompt retirement can ride the same
ruling (its durable copy already landed, core PR #1717).
