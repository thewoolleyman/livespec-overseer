# Plan — supervisor-prompt-quality

**Owning repo:** `livespec-overseer`. **Status: read it from the ledger**
(`list-work-items` / `next`; nothing here stores status). Created
2026-07-26 at maintainer direction, out of the homelab
supervisor-handoff build-out (homelab PR #37, commit `862b4d0`).

**Ledger anchor:** epic **`overseer-byvxlp`** (this repo's beads
tenant) — the full quality bar for what `supervise-plan` GENERATES,
carried in that epic's description. This thread TIES TOGETHER the
existing generated-prompt items so the maintainer can execute them in
order; it does not fork their content.

## The item map (ids cited read-only)

- **`overseer-byvxlp`** (epic, this thread's anchor) — the eight-family
  quality bar: iteration-stable generic form; anti-drift layering +
  Corrections preservation on regeneration; the cold-open generation
  gate; placeholder discipline; classified-remedy preconditions
  (parameterized spawn posture); wait-channel bootstrap; adopter
  parameterization; the full anti-stall playbook beyond the two stall
  modes.
- **`overseer-hbr.16`** (S7, P1) — the FLOOR: both stall modes
  (no-idle/no-silent-block AND never-end-a-turn-without-an-armed-
  re-entry) with fixtures that tell them apart, asserted over GENERATED
  output, each demonstrated RED. Unchanged by this thread. NOTE: beads
  forbids task-blocks-epic edges, so `overseer-byvxlp`'s dependency on
  this item and on `overseer-hbr.4` is PROSE-ONLY — re-check both
  before calling the epic ready to groom-execute.
- **`overseer-hbr.4`** (bug) — executable-commands bar; its fix already
  exists on branch `docs/dod-corrections-pr78` (commit `086ee3a`) and
  is candidate template wording.
- **`overseer-hbr.15`** (S6, P1) — goal-1 acceptance outside this repo;
  depends on S4 + S7 in the ledger. This thread strengthens the bar it
  tests but does NOT gate it.
- **`overseer-fitvmo`** — CLOSED 2026-07-26 as superseded (stall mode 1
  restated in `overseer-hbr.16`; broader bar in `overseer-byvxlp`);
  the close reason carries the full mapping.

## Execution order (the reason this thread exists)

1. **Land `overseer-hbr.4`'s existing fix** (`docs/dod-corrections-pr78`
   @ `086ee3a`) — smallest step, and it is the corrected exemplar the
   template wording draws from.
2. **Execute `overseer-hbr.16`** (day-1-startable per its own text) —
   both stall modes + the tell-them-apart fixtures over generated
   output.
3. **Groom `overseer-byvxlp`** (the maintainer owns the cut).
   Indicative slice shape, not a decision: (a) template rewrite to the
   iteration-stable two-layer form carrying the full playbook; (b) the
   cold-open generation gate + placeholder-substitution lint wired into
   CI and demonstrated RED under injected defects; (c) classified-remedy
   preconditions incl. the parameterized missing-worker spawn posture +
   wait-channel bootstrap; (d) adopter parameterization, proven by one
   adopter-flavored generation (homelab's conventions: `main`,
   squash-merge, POSIX hooks, its own credential wrapper, dispatch-off);
   (e) regenerate a REAL thread's charter in this repo with Corrections
   preserved, passing the gate.
4. **`overseer-hbr.15`** then closes goal 1 on its own ledger
   dependencies.

## Reference material (all verifiable, none of it status)

- **Reference implementation:** homelab @ `862b4d0` —
  `.ai/supervisor-protocol.md` (shared role-level layer) +
  `plan/<slug>/supervisor-handoff.md` ×6 (thin iteration-stable
  binders), synthesized from this repo's charters plus `livespec`,
  `livespec-orchestrator-beads-fabro`, and `livespec-dev-tooling`.
- **The generic form's prior art:** `livespec-dev-tooling`
  `plan/worktree-location-enforcement/supervisor-handoff.md`.
- **The six defect classes the cold-open dry-runs caught** in a prompt
  that already looked complete — the empirical case for the generation
  gate: an unsubstitutable `<workdir>` placeholder (three shell errors
  in one line); a Monitor wait channel whose file was never created nor
  fed; a boot brief that was a comment, not a command; an unbounded
  wait for the agent UI; a HALT precondition with no remedy (a
  guaranteed stall); a false "only placeholder" claim.

## Discipline

Fleet-standard: worktree → PR → rebase-merge; `mise exec -- git …`;
never `--no-verify`; status only from the ledger via the fleet
credential wrapper; this thread archives when `overseer-byvxlp`
closes.
